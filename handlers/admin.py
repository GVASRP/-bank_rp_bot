from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user,
    get_user_by_telegram_id,
    update_balance,
    set_balance,
    add_transaction,
    get_credit_request,
    update_credit_request,
    get_credit_requests,
    create_credit,
    get_all_credits,
    get_deposit_request,
    update_deposit_request,
    get_deposit_requests,
    get_all_deposits,
    create_deposit_account,
    get_config,
    set_config,
    create_house,
    get_house,
    get_all_vehicles_by_owner,
    get_all_owned_vehicles,
    admin_take_vehicle,
    admin_give_vehicle,
    clear_user_vehicles,
    clear_posted_listings,
    clear_available_vehicles,
    reset_all_balances,
    cleanup_orphan_vehicles,
    apply_start_balance_to_poor,
    get_chat_stats,
    get_all_users_ranked,
)
from auto_poster import force_post_one
from utils import calc_credit_debt, calc_deposit_payout, format_amount, parse_amount, is_admin, get_user_mention, get_user_display, resolve_target

router = Router()


async def ensure_admin(message: Message) -> bool:
    chat_type = message.chat.type
    if chat_type not in ("group", "supergroup"):
        await message.reply("❌ Админ-команды работают только в группах")
        return False
    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Эта команда только для администраторов группы")
        return False
    return True


@router.message(Command("начислить", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_add_balance(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!начислить @user сумма</code>", parse_mode="HTML")
        return

    amount = parse_amount(args[2])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму")
        return

    target_id, target_name, target_username, hint = await resolve_target(message, args)
    if target_id is None:
        await message.reply(hint or "❌ Пользователь не найден")
        return

    await get_or_create_user(target_id, target_username, target_name, chat_id=message.chat.id)
    await update_balance(target_id, amount, message.chat.id)
    await add_transaction("admin_add", None, target_id, amount, f"Начислено админом {message.from_user.full_name}")

    await message.reply(
        f"✅ Начислено <b>{format_amount(amount)}</b> долларов пользователю {target_name}",
        parse_mode="HTML",
    )


@router.message(Command("списать", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_remove_balance(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!списать @user сумма</code>", parse_mode="HTML")
        return

    amount = parse_amount(args[2])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму")
        return

    target_id, target_name, target_username, hint = await resolve_target(message, args)
    if target_id is None:
        await message.reply(hint or "❌ Пользователь не найден")
        return

    user = await get_or_create_user(target_id, target_username, target_name, chat_id=message.chat.id)
    if user["balance"] < amount:
        await message.reply(
            f"❌ У пользователя недостаточно средств. Баланс: <b>{format_amount(user['balance'])}</b> долларов",
            parse_mode="HTML",
        )
        return

    await update_balance(target_id, -amount, message.chat.id)
    await add_transaction("admin_remove", None, target_id, amount, f"Списано админом {message.from_user.full_name}")

    await message.reply(
        f"✅ Списано <b>{format_amount(amount)}</b> долларов у пользователя {target_name}",
        parse_mode="HTML",
    )


@router.message(Command("установить_баланс", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_set_balance(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!установить_баланс @user сумма</code>", parse_mode="HTML")
        return

    amount = parse_amount(args[2])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму")
        return

    target_id, target_name, target_username, hint = await resolve_target(message, args)
    if target_id is None:
        await message.reply(hint or "❌ Пользователь не найден")
        return

    await get_or_create_user(target_id, target_username, target_name, chat_id=message.chat.id)
    old_balance = (await get_user_by_telegram_id(target_id, message.chat.id))["balance"]
    await set_balance(target_id, amount, message.chat.id)
    await add_transaction("admin_set", None, target_id, amount, f"Баланс установлен админом {message.from_user.full_name} (было {old_balance})")

    await message.reply(
        f"✅ Баланс пользователя {target_name} установлен на <b>{format_amount(amount)}</b> долларов",
        parse_mode="HTML",
    )


@router.message(Command("одобрить_кредит", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_approve_credit(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=3)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!одобрить_кредит id [процент] [срок_дней]</code>\n"
            "Пример: <code>!одобрить_кредит 1 20 30</code> — 20% годовых на 30 дней",
            parse_mode="HTML")
        return

    try:
        request_id = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите числовой ID заявки")
        return

    interest = 10
    if len(args) >= 3:
        try:
            interest = int(args[2])
            if interest < 0:
                interest = 10
        except ValueError:
            await message.reply("❌ Процент должен быть числом (например: 10)")
            return

    duration_days = 30
    if len(args) >= 4:
        try:
            duration_days = int(args[3])
            if duration_days < 1:
                duration_days = 30
        except ValueError:
            await message.reply("❌ Срок должен быть числом (дни)")
            return

    request = await get_credit_request(request_id)
    if not request:
        await message.reply(f"❌ Заявка #{request_id} не найдена")
        return
    if request["status"] != "pending":
        await message.reply(f"❌ Заявка #{request_id} уже обработана (статус: {request['status']})")
        return

    try:
        credit_id = await create_credit(request["user_telegram_id"], request["amount"], interest, duration_days)
        await update_balance(request["user_telegram_id"], request["amount"], message.chat.id)
        await add_transaction("credit", None, request["user_telegram_id"], request["amount"], f"Кредит #{request_id} одобрен админом {message.from_user.full_name} ({interest}%, {duration_days}д)")
        await update_credit_request(request_id, "approved")
    except Exception as e:
        await message.reply(f"❌ Ошибка при одобрении кредита: {e}")
        return

    await message.reply(
        f"✅ Кредит #{request_id} на <b>{format_amount(request['amount'])}</b> долларов одобрен!\n"
        f"Ставка: <b>{interest}%</b> годовых | Срок: <b>{duration_days}</b> дней\n"
        f"Проценты начисляются ежедневно на остаток тела кредита.\n"
        f"Средства зачислены пользователю.",
        parse_mode="HTML",
    )


@router.message(Command("отклонить_кредит", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_reject_credit(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!отклонить_кредит id</code>", parse_mode="HTML")
        return

    try:
        request_id = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите числовой ID заявки")
        return

    request = await get_credit_request(request_id)
    if not request:
        await message.reply(f"❌ Заявка #{request_id} не найдена")
        return
    if request["status"] != "pending":
        await message.reply(f"❌ Заявка #{request_id} уже обработана (статус: {request['status']})")
        return

    await update_credit_request(request_id, "rejected")

    await message.reply(
        f"❌ Кредит #{request_id} на <b>{format_amount(request['amount'])}</b> долларов отклонён",
        parse_mode="HTML",
    )


@router.message(Command("одобрить_вклад", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_approve_deposit(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!одобрить_вклад id [процент]</code>", parse_mode="HTML")
        return

    try:
        request_id = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите числовой ID заявки")
        return

    interest = 5
    if len(args) >= 3:
        try:
            interest = int(args[2])
            if interest < 0:
                interest = 5
        except ValueError:
            await message.reply("❌ Процент должен быть числом (например: 5)")
            return

    request = await get_deposit_request(request_id)
    if not request:
        await message.reply(f"❌ Заявка #{request_id} не найдена")
        return
    if request["status"] != "pending":
        await message.reply(f"❌ Заявка #{request_id} уже обработана (статус: {request['status']})")
        return

    user = await get_user_by_telegram_id(request["user_telegram_id"], message.chat.id)
    if not user or user["balance"] < request["amount"]:
        await update_deposit_request(request_id, "rejected")
        await message.reply(
            f"❌ Заявка #{request_id} отклонена — у пользователя недостаточно средств для вклада",
            parse_mode="HTML",
        )
        return

    await update_deposit_request(request_id, "approved")
    await create_deposit_account(request["user_telegram_id"], request["amount"], interest)
    await update_balance(request["user_telegram_id"], -request["amount"], message.chat.id)
    await add_transaction("deposit", request["user_telegram_id"], None, request["amount"], f"Вклад #{request_id} одобрен админом {message.from_user.full_name} ({interest}%)")

    await message.reply(
        f"✅ Вклад #{request_id} на <b>{format_amount(request['amount'])}</b> долларов одобрен!\n"
        f"Процент: <b>{interest}%</b>\n"
        f"Средства списаны со счёта пользователя.",
        parse_mode="HTML",
    )


@router.message(Command("отклонить_вклад", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_reject_deposit(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!отклонить_вклад id</code>", parse_mode="HTML")
        return

    try:
        request_id = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите числовой ID заявки")
        return

    request = await get_deposit_request(request_id)
    if not request:
        await message.reply(f"❌ Заявка #{request_id} не найдена")
        return
    if request["status"] != "pending":
        await message.reply(f"❌ Заявка #{request_id} уже обработана (статус: {request['status']})")
        return

    await update_deposit_request(request_id, "rejected")

    await message.reply(
        f"❌ Вклад #{request_id} на <b>{format_amount(request['amount'])}</b> долларов отклонён",
        parse_mode="HTML",
    )


@router.message(Command("заявки", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_list_requests(message: Message):
    if not await ensure_admin(message):
        return

    credits = await get_credit_requests("pending")
    deposits = await get_deposit_requests("pending")

    if not credits and not deposits:
        await message.reply("📭 Нет ожидающих заявок")
        return

    lines = ["📋 <b>Ожидающие заявки:</b>\n"]

    if credits:
        lines.append("<b>Кредиты:</b>")
        for c in credits:
            user = await get_user_by_telegram_id(c["user_telegram_id"], message.chat.id)
            name = get_user_display(user, f"ID {c['user_telegram_id']}")
            lines.append(f"  #{c['id']} — {name}: {format_amount(c['amount'])} долларов")
        lines.append("")

    if deposits:
        lines.append("<b>Вклады:</b>")
        for d in deposits:
            user = await get_user_by_telegram_id(d["user_telegram_id"], message.chat.id)
            name = get_user_display(user, f"ID {d['user_telegram_id']}")
            lines.append(f"  #{d['id']} — {name}: {format_amount(d['amount'])} долларов")

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("все_кредиты", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_all_credits(message: Message):
    if not await ensure_admin(message):
        return

    credits = await get_all_credits("active")
    if not credits:
        await message.reply("📭 Нет активных кредитов")
        return

    lines = ["💳 <b>Все активные кредиты:</b>\n"]
    for c in credits:
        user = await get_user_by_telegram_id(c["user_telegram_id"], message.chat.id)
        name = get_user_display(user, f"ID {c['user_telegram_id']}")
        info = calc_credit_debt(c)
        lines.append(
            f"#{c['id']} — {name}\n"
            f"   Выдано: {format_amount(c['amount'])} | {c['interest_rate']}%/год | {c['duration_days']}д\n"
            f"   Тело: {format_amount(info['remaining_principal'])} | %: +{format_amount(info['interest_due'])}\n"
            f"   Долг: <b>{format_amount(info['total_debt'])}</b>"
        )

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("все_вклады", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_all_deposits(message: Message):
    if not await ensure_admin(message):
        return

    deposits = await get_all_deposits("active")
    if not deposits:
        await message.reply("📭 Нет активных вкладов")
        return

    lines = ["🏛 <b>Все активные вклады:</b>\n"]
    for d in deposits:
        user = await get_user_by_telegram_id(d["user_telegram_id"], message.chat.id)
        name = get_user_display(user, f"ID {d['user_telegram_id']}")
        payout, interest = calc_deposit_payout(d)
        lines.append(
            f"#{d['id']} — {name}\n"
            f"   Сумма: {format_amount(d['amount'])} | %: {d['interest_rate']}%/год\n"
            f"   Начислено: +{format_amount(interest)} | К выплате: <b>{format_amount(payout)}</b>"
        )

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("объявления", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_auto_posts(message: Message):
    if not await ensure_admin(message):
        return

    chat_id = message.chat.id
    args = message.text.split(maxsplit=2)

    if len(args) < 2:
        enabled = await get_config(f"poster_enabled:{chat_id}")
        interval = await get_config(f"poster_interval:{chat_id}") or "120"
        status = "✅ Включены" if enabled == "1" else "❌ Выключены"
        channel_raw = await get_config(f"poster_cars_channel:{chat_id}")
        topic_raw = await get_config(f"poster_cars_topic:{chat_id}")
        channel_info = f"🚗 Канал: {channel_raw}" if channel_raw else "🚗 Канал: этот чат"
        if topic_raw:
            channel_info += f" (топик {topic_raw})"
        last_key = f"poster_last_post:{chat_id}"
        last_raw = await get_config(last_key)
        last_info = f", последний пост: {last_raw}" if last_raw else ", постов не было"
        await message.reply(
            f"📢 <b>Авто-объявления</b>\n"
            f"Статус: {status}\n"
            f"Интервал: {interval} мин\n"
            f"{channel_info}{last_info}\n\n"
            f"Команды:\n"
            f"<code>!объявления вкл</code> — включить\n"
            f"<code>!объявления выкл</code> — выключить\n"
            f"<code>!объявления интервал 1</code> — интервал в минутах\n"
            f"<code>!объявления канал @channel</code> — канал для авто\n"
            f"<code>!объявления топик</code> — сохранить текущий топик (для тем)\n"
            f"<code>!объявления тест</code> — показать 1 объявление\n\n"
            f"🚗 Реальные авто из Висконсина с фото (Wikipedia)",
            parse_mode="HTML",
        )
        return

    action = args[1]

    if action == "канал":
        if len(args) >= 3:
            target_raw = args[2].lower()
            if target_raw in ("этот_чат", "this_chat", "здесь"):
                await set_config(f"poster_cars_channel:{chat_id}", "")
                await set_config(f"poster_cars_topic:{chat_id}", "")
                await message.reply("📢 Объявления будут поститься в этот чат")
                return
            try:
                target_id = int(target_raw)
            except ValueError:
                try:
                    chat = await message.bot.get_chat(target_raw)
                    target_id = chat.id
                except Exception:
                    await message.reply(
                        "❌ Не могу найти чат. Используй:\n"
                        "• ID канала (напр. -1001234567890) — узнать через @getmyid_bot\n"
                        "• @username канала (бот должен быть админом в канале)",
                        parse_mode="HTML",
                    )
                    return
            if target_id == message.chat.id:
                await set_config(f"poster_cars_channel:{chat_id}", "")
                await set_config(f"poster_cars_topic:{chat_id}", "")
                await message.reply("📢 Объявления будут поститься в этот чат")
            else:
                await set_config(f"poster_cars_channel:{chat_id}", str(target_id))
                await set_config(f"poster_cars_topic:{chat_id}", "")
                await message.reply(f"📢 Объявления машин будут поститься в чат {target_id}")
        else:
            current = await get_config(f"poster_cars_channel:{chat_id}")
            current_topic = await get_config(f"poster_cars_topic:{chat_id}")
            if current or current_topic:
                info = f"Чат: <code>{current}</code>" if current else ""
                if current_topic:
                    info += f", Топик ID: <code>{current_topic}</code>"
                await message.reply(f"📢 Текущий канал машин: {info}\n"
                                    f"Чтобы сбросить: <code>!объявления канал этот_чат</code>",
                                    parse_mode="HTML")
            else:
                await message.reply("📢 Сейчас объявления постятся в этот чат.\n"
                                    "Чтобы задать канал: <code>!объявления канал @channel</code>",
                                    parse_mode="HTML")
    elif action == "топик":
        mid = message.message_thread_id
        if not mid:
            await message.reply("❌ Эта команда работает только внутри топика (темы).\n"
                                "Зайди в нужный топик и отправь команду там.")
            return
        await set_config(f"poster_cars_topic:{chat_id}", str(mid))
        await message.reply(f"✅ Сохранён топик ID {mid}. Объявления будут поститься сюда.")
    elif action == "вкл":
        await set_config(f"poster_enabled:{chat_id}", "1")
        chats = await get_config("poster_chats") or ""
        if str(chat_id) not in chats.split(","):
            new_chats = ",".join(filter(None, [*chats.split(","), str(chat_id)]))
            await set_config("poster_chats", new_chats)
        await message.reply("✅ Авто-объявления включены")
    elif action == "выкл":
        await set_config(f"poster_enabled:{chat_id}", "0")
        await message.reply("❌ Авто-объявления выключены")
    elif action == "интервал" and len(args) >= 3:
        try:
            minutes = int(args[2])
            if minutes < 1:
                minutes = 1
            await set_config(f"poster_interval:{chat_id}", str(minutes))
            await message.reply(f"✅ Интервал: {minutes} минут")
        except ValueError:
            await message.reply("❌ Укажите число минут")
    elif action == "тест":
        topic_raw = await get_config(f"poster_cars_topic:{chat_id}")
        topic = int(topic_raw) if topic_raw else None
        result = await force_post_one(message.bot, chat_id, topic)
        await message.reply(result, parse_mode="HTML")
    else:
        await message.reply("❌ Неизвестная команда. Используй: вкл, выкл, интервал, тест")


@router.message(Command("добавить_дом", prefix="!/"))
async def cmd_add_house(message: Message):
    if not await ensure_admin(message):
        return
    parts = message.text.split(maxsplit=8)
    if len(parts) < 8:
        await message.reply(
            "❌ Использование: <code>!добавить_дом тип_жилья район локация цена комнаты ванны площадь [описание]</code>\n"
            "Пример: <code>!добавить_дом \"Mobile Home\" \"Six Housen't\" \"Greenville,WI\" 65000 3 2.5 900 \"Описание\"</code>",
            parse_mode="HTML",
        )
        return
    type_name = parts[1]
    neighborhood = parts[2]
    location = parts[3]
    try:
        price = int(parts[4])
        bedrooms = int(parts[5])
        bathrooms = int(parts[6])
        sqft = int(parts[7])
    except ValueError:
        await message.reply("❌ Цена, комнаты, ванны, площадь — должны быть числами")
        return
    description = parts[8] if len(parts) > 8 else None
    hid = await create_house(message.chat.id, type_name, neighborhood, location, price, bedrooms, bathrooms, sqft, description or "")
    await message.reply(
        f"✅ Дом добавлен!\n"
        f"🏠 #{hid} {type_name}\n"
        f"📍 <b>{neighborhood}</b> — {location}\n"
        f"💰 ${price:,} | 🛏 {bedrooms} | 🛁 {bathrooms} | 📐 {sqft} кв.футов",
        parse_mode="HTML",
    )


@router.message(Command("удалить_дом", prefix="!/"))
async def cmd_delete_house(message: Message):
    if not await ensure_admin(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!удалить_дом ID</code>", parse_mode="HTML")
        return
    try:
        hid = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    h = await get_house(hid)
    if not h:
        await message.reply(f"❌ Дом #{hid} не найден")
        return
    from database import delete_house
    await delete_house(hid)
    await message.reply(f"✅ Дом #{hid} {h['type_name']} удалён")


@router.message(Command("авто_пользователя", prefix="!/"))
async def cmd_user_cars(message: Message):
    if not await ensure_admin(message):
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!авто_пользователя @user</code>", parse_mode="HTML")
        return
    uid, _, _, _ = await resolve_target(message, args)
    if uid is None:
        await message.reply("❌ Пользователь не найден")
        return
    vehicles = await get_all_vehicles_by_owner(uid)
    if not vehicles:
        await message.reply("📭 У пользователя нет автомобилей")
        return
    lines = [f"🚗 <b>Автомобили пользователя {args[1]}:</b>\n"]
    for v in vehicles:
        lines.append(
            f"#{v['id']} — {v['year']} {v['make']} {v['model']} ({v['color']})\n"
            f"   Статус: {v['status']} | Цена: ${v['price']:,}"
        )
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("изъять_авто", prefix="!/"))
async def cmd_take_car(message: Message):
    if not await ensure_admin(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!изъять_авто ID</code>", parse_mode="HTML")
        return
    try:
        vid = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    v = await get_vehicle(vid)
    if not v:
        await message.reply(f"❌ Авто #{vid} не найдено")
        return
    if v["status"] != "sold":
        await message.reply(f"❌ Авто #{vid} ещё не продано (статус: {v['status']})")
        return
    if not await admin_take_vehicle(vid):
        await message.reply(f"❌ Ошибка изъятия")
        return
    await message.reply(f"✅ Авто #{vid} {v['year']} {v['make']} {v['model']} изъято и выставлено в продажу")


@router.message(Command("выдать_авто", prefix="!/"))
async def cmd_give_car(message: Message):
    if not await ensure_admin(message):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("❌ Использование: <code>!выдать_авто @user ID</code>", parse_mode="HTML")
        return
    uid, _, _, _ = await resolve_target(message, parts)
    if uid is None:
        await message.reply("❌ Пользователь не найден")
        return
    try:
        vid = int(parts[2])
    except ValueError:
        await message.reply("❌ ID авто должен быть числом")
        return
    v = await get_vehicle(vid)
    if not v:
        await message.reply(f"❌ Авто #{vid} не найдено")
        return
    if v["status"] != "available":
        await message.reply(f"❌ Авто #{vid} недоступно (статус: {v['status']})")
        return
    if not await admin_give_vehicle(vid, uid):
        await message.reply(f"❌ Ошибка выдачи")
        return
    await message.reply(f"✅ Авто #{vid} {v['year']} {v['make']} {v['model']} выдано пользователю {parts[1]}")


@router.message(Command("все_авто", prefix="!/"))
async def cmd_all_cars(message: Message):
    if not await ensure_admin(message):
        return
    vehicles = await get_all_owned_vehicles()
    if not vehicles:
        await message.reply("📭 Нет купленных автомобилей")
        return
    lines = [f"🚗 <b>Все купленные авто ({len(vehicles)} шт.):</b>\n"]
    for v in vehicles:
        owner = await get_user_by_telegram_id(v["owner_telegram_id"])
        owner_name = get_user_display(owner) if owner else "Неизвестно"
        status = "🔄 в продаже" if v["status"] == "player_listed" else "✅"
        lines.append(
            f"#{v['id']} {v['year']} {v['make']} {v['model']}\n"
            f"   👤 {owner_name} | {status}"
        )
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("очистить_авто", prefix="!/"))
async def cmd_clear_user_cars(message: Message):
    if not await ensure_admin(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("❌ Использование: <code>!очистить_авто @user</code>", parse_mode="HTML")
        return
    uid, _, _, _ = await resolve_target(message, parts)
    if uid is None:
        await message.reply("❌ Пользователь не найден")
        return
    count = await clear_user_vehicles(uid)
    await message.reply(f"✅ Очищено <b>{count}</b> автомобилей пользователя", parse_mode="HTML")


@router.message(Command("очистить_объявления", prefix="!/"))
async def cmd_clear_listings(message: Message):
    if not await ensure_admin(message):
        return
    posted = await clear_posted_listings()
    avail = await clear_available_vehicles()
    await message.reply(
        f"🗑 Очищено:\n"
        f"• {posted} записей в архиве объявлений\n"
        f"• {avail} непроданных автомобилей\n\n"
        f"Авто-постер начнёт генерировать новые объявления.", parse_mode="HTML",
    )


@router.message(Command("стартовый_баланс", prefix="!/"))
async def cmd_start_balance(message: Message):
    if not await ensure_admin(message):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        current = await get_config("start_balance") or "1000"
        await message.reply(f"💰 Стартовый баланс: <b>{format_amount(int(current))}</b> долларов\n"
                            f"Использование: <code>!стартовый_баланс сумма</code>", parse_mode="HTML")
        return
    amount = parse_amount(args[1])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму")
        return
    await set_config("start_balance", str(amount))
    await message.reply(f"✅ Стартовый баланс установлен: <b>{format_amount(amount)}</b> долларов",
                        parse_mode="HTML")


@router.message(Command("выдать_стартовый", prefix="!/"))
async def cmd_give_start(message: Message):
    if not await ensure_admin(message):
        return
    count = await apply_start_balance_to_poor(chat_id=message.chat.id)
    await message.reply(f"✅ Выдан стартовый баланс <b>{count}</b> пользователям с балансом ≤ 0",
                        parse_mode="HTML")


@router.message(Command("сброс", prefix="!/"))
async def cmd_reset_balances(message: Message):
    if not await ensure_admin(message):
        return
    args = message.text.split(maxsplit=1)
    amount = 0
    if len(args) >= 2:
        parsed = parse_amount(args[1])
        if parsed is not None:
            amount = parsed
    count = await reset_all_balances(chat_id=message.chat.id, new_balance=amount)
    await message.reply(f"✅ Сброшено балансов: <b>{count}</b> → {format_amount(amount)}\n"
                        f"Новые пользователи будут получать: <code>!стартовый_баланс</code>",
                        parse_mode="HTML")


@router.message(Command("обновить_имена", prefix="!/"))
async def cmd_update_names(message: Message):
    if not await ensure_admin(message):
        return
    users = await get_all_users_ranked(chat_id=message.chat.id)
    updated = 0
    for u in users:
        if not u.get("first_name") and not u.get("username"):
            try:
                chat_member = await message.bot.get_chat_member(message.chat.id, u["telegram_id"])
                user_info = chat_member.user
                await get_or_create_user(u["telegram_id"], user_info.username, user_info.first_name, chat_id=message.chat.id)
                updated += 1
            except Exception:
                pass
    await message.reply(f"✅ Обновлено имён: <b>{updated}</b>", parse_mode="HTML")


@router.message(Command("очистить_старые", prefix="!/"))
async def cmd_cleanup_old(message: Message):
    if not await ensure_admin(message):
        return
    count = await cleanup_orphan_vehicles()
    await message.reply(f"🗑 Удалено старых машин: <b>{count}</b>", parse_mode="HTML")


@router.message(Command("статистика", prefix="!/"))
async def cmd_stats(message: Message):
    stats = await get_chat_stats(message.chat.id)
    top = await get_all_users_ranked(chat_id=message.chat.id, limit=3)
    top_lines = []
    for i, u in enumerate(top, 1):
        top_lines.append(f"{i}. {get_user_display(u)} — {format_amount(u['balance'])}")
    await message.reply(
        f"📊 <b>Статистика чата</b>\n"
        f"👥 Пользователей: <b>{stats['users']}</b>\n"
        f"💰 Общий баланс: <b>{format_amount(stats['total_balance'])}</b>\n"
        f"🚗 Машин в продаже: <b>{stats['available_cars']}</b>\n"
        f"🏠 Домов в продаже: <b>{stats['available_houses']}</b>\n"
        f"🏆 <b>Топ-3:</b>\n" + "\n".join(top_lines),
        parse_mode="HTML",
    )
