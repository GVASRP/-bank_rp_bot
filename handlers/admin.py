import random

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

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
    get_deposit_by_id,
    withdraw_deposit,
    update_credit_interest_rate,
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
    get_house_type,
    get_neighborhood,
    get_all_house_types,
    get_all_neighborhoods,
    create_house_listing,
    get_vehicle,
    buy_vehicle,
    get_available_vehicles,
    create_vehicle,
)
from auto_poster import force_post_one, force_post_house, force_post_trailer, force_post_business
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
        vehicle_id = request.get("vehicle_id", 0) or 0
        credit_id = await create_credit(request["user_telegram_id"], request["amount"], interest, duration_days, vehicle_id)
        await add_transaction("credit", None, request["user_telegram_id"], request["amount"], f"Кредит #{request_id} одобрен админом {message.from_user.full_name} ({interest}%, {duration_days}д)")

        if vehicle_id:
            market = await get_available_vehicles(chat_id=message.chat.id)
            v = next((x for x in market if x.get("id") == vehicle_id or x.get("pos") == vehicle_id), None)
            if v:
                vid = await buy_vehicle(
                    request["user_telegram_id"], v["make"], v["model"], v["year"],
                    v["price"], v["miles"], v["city"], v["vin"], v["license_plate"],
                    v["color"], v["rarity"], message.chat.id,
                )
                await add_transaction("buy_car", request["user_telegram_id"], None, v["price"],
                    f"Автокредит #{credit_id}: {v['year']} {v['make']} {v['model']} #{vid}")
            else:
                await update_balance(request["user_telegram_id"], request["amount"], message.chat.id)
        else:
            await update_balance(request["user_telegram_id"], request["amount"], message.chat.id)

        await update_credit_request(request_id, "approved")
    except Exception as e:
        await message.reply(f"❌ Ошибка при одобрении кредита: {e}")
        return

    extra = "🚗 Авто куплено в кредит!\n" if vehicle_id else "Средства зачислены пользователю.\n"
    await message.reply(
        f"✅ Кредит #{request_id} на <b>{format_amount(request['amount'])}</b> долларов одобрен!\n"
        f"Ставка: <b>{interest}%</b> годовых | Срок: <b>{duration_days}</b> дней\n"
        f"Проценты начисляются ежедневно на остаток тела кредита.\n"
        f"{extra}",
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

    args = message.text.split(maxsplit=3)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!одобрить_вклад id [процент] [дней]</code>", parse_mode="HTML")
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

    duration_days = 30
    if len(args) >= 4:
        try:
            duration_days = int(args[3])
            if duration_days < 1:
                duration_days = 30
        except ValueError:
            await message.reply("❌ Срок должен быть числом (дни)")
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
    await create_deposit_account(request["user_telegram_id"], request["amount"], interest, duration_days)
    await update_balance(request["user_telegram_id"], -request["amount"], message.chat.id)
    await add_transaction("deposit", request["user_telegram_id"], None, request["amount"], f"Вклад #{request_id} одобрен админом {message.from_user.full_name} ({interest}%, {duration_days}д)")

    await message.reply(
        f"✅ Вклад #{request_id} на <b>{format_amount(request['amount'])}</b> долларов одобрен!\n"
        f"Процент: <b>{interest}%</b> | Срок: <b>{duration_days}</b> дней\n"
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
            tag = "🚗 Авто" if (c.get("vehicle_id") or 0) else "💳 Обычный"
            lines.append(f"  #{c['id']} — {name}: {format_amount(c['amount'])} долларов ({tag})")
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
            f"   Выдано: {format_amount(c['amount'])} | {c['interest_rate']}%/день | {c['duration_days']}д\n"
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
            f"   Сумма: {format_amount(d['amount'])} | %: {d['interest_rate']}%/день\n"
            f"   Начислено: +{format_amount(interest)} | К выплате: <b>{format_amount(payout)}</b>"
        )

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("объявления", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_auto_posts(message: Message):
    if not await ensure_admin(message):
        return

    chat_id = message.chat.id
    args = message.text.split(maxsplit=3)

    if len(args) < 2:
        car_enabled = await get_config(f"poster_enabled:{chat_id}")
        car_interval = await get_config(f"poster_interval:{chat_id}") or "120"
        car_status = "✅" if car_enabled == "1" else "❌"
        car_channel = await get_config(f"poster_cars_channel:{chat_id}") or "этот чат"
        car_topic_raw = await get_config(f"poster_cars_topic:{chat_id}")

        house_enabled = await get_config(f"poster_houses_enabled:{chat_id}")
        house_interval = await get_config(f"poster_houses_interval:{chat_id}") or "180"
        house_status = "✅" if house_enabled == "1" else "❌"
        house_channel = await get_config(f"poster_houses_channel:{chat_id}") or "этот чат"
        house_topic_raw = await get_config(f"poster_houses_topic:{chat_id}")

        trailer_enabled = await get_config(f"poster_trailers_enabled:{chat_id}")
        trailer_interval = await get_config(f"poster_trailers_interval:{chat_id}") or "180"
        trailer_status = "✅" if trailer_enabled == "1" else "❌"
        trailer_channel = await get_config(f"poster_trailers_channel:{chat_id}") or "этот чат"
        trailer_topic_raw = await get_config(f"poster_trailers_topic:{chat_id}")

        biz_enabled = await get_config(f"poster_businesses_enabled:{chat_id}")
        biz_interval = await get_config(f"poster_businesses_interval:{chat_id}") or "240"
        biz_status = "✅" if biz_enabled == "1" else "❌"
        biz_channel = await get_config(f"poster_businesses_channel:{chat_id}") or "этот чат"
        biz_topic_raw = await get_config(f"poster_businesses_topic:{chat_id}")

        await message.reply(
            f"📢 <b>Авто-объявления</b>\n\n"
            f"━ 🚗 <b>Машины:</b>\n"
            f"Статус: {car_status} | Интервал: {car_interval} мин | Канал: {car_channel}\n"
            f"━ 🏠 <b>Дома:</b>\n"
            f"Статус: {house_status} | Интервал: {house_interval} мин | Канал: {house_channel}\n"
            f"━ 🚛 <b>Прицепы:</b>\n"
            f"Статус: {trailer_status} | Интервал: {trailer_interval} мин | Канал: {trailer_channel}\n"
            f"━ 🏪 <b>Бизнесы:</b>\n"
            f"Статус: {biz_status} | Интервал: {biz_interval} мин | Канал: {biz_channel}\n\n"
            f"🚗 <b>Команды для машин:</b>\n"
            f"<code>!объявления машины вкл</code> — включить\n"
            f"<code>!объявления машины интервал 1</code> — интервал\n"
            f"<code>!объявления машины тест</code> — тест\n\n"
            f"🏠 <b>Команды для домов:</b>\n"
            f"<code>!объявления дома вкл</code> — включить\n"
            f"<code>!объявления дома интервал 1</code> — интервал\n"
            f"<code>!объявления дома тест</code> — тест\n\n"
            f"🚛 <b>Команды для прицепов:</b>\n"
            f"<code>!объявления прицепы вкл</code> — включить\n"
            f"<code>!объявления прицепы интервал 1</code> — интервал\n"
            f"<code>!объявления прицепы тест</code> — тест\n\n"
            f"🏪 <b>Команды для бизнесов:</b>\n"
            f"<code>!объявления бизнесы вкл</code> — включить\n"
            f"<code>!объявления бизнесы интервал 1</code> — интервал\n"
            f"<code>!объявления бизнесы тест</code> — тест\n\n"
            f"📡 <b>Общее:</b>\n"
            f"<code>!объявления канал @channel</code> — канал для машин\n"
            f"<code>!объявления дома_канал @channel</code> — канал для домов\n"
            f"<code>!объявления прицепы_канал @channel</code> — канал для прицепов\n"
            f"<code>!объявления бизнесы_канал @channel</code> — канал для бизнесов\n"
            f"<code>!объявления топик</code> — сохранить текущий топик (для тем машин)\n"
            f"<code>!объявления дома_топик</code> — сохранить топик для домов\n"
            f"<code>!объявления прицепы_топик</code> — сохранить топик для прицепов\n"
            f"<code>!объявления бизнесы_топик</code> — сохранить топик для бизнесов",
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
                await message.reply("📢 Объявления машин будут поститься в этот чат")
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
                await message.reply("📢 Объявления машин будут поститься в этот чат")
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
                await message.reply("📢 Сейчас объявления машин постятся в этот чат.\n"
                                    "Чтобы задать канал: <code>!объявления канал @channel</code>",
                                    parse_mode="HTML")
    elif action == "дома_канал":
        if len(args) >= 3:
            target_raw = args[2].lower()
            if target_raw in ("этот_чат", "this_chat", "здесь"):
                await set_config(f"poster_houses_channel:{chat_id}", "")
                await set_config(f"poster_houses_topic:{chat_id}", "")
                await message.reply("📢 Объявления домов будут поститься в этот чат")
                return
            try:
                target_id = int(target_raw)
            except ValueError:
                try:
                    chat = await message.bot.get_chat(target_raw)
                    target_id = chat.id
                except Exception:
                    await message.reply("❌ Не могу найти чат", parse_mode="HTML")
                    return
            await set_config(f"poster_houses_channel:{chat_id}", str(target_id))
            await set_config(f"poster_houses_topic:{chat_id}", "")
            await message.reply(f"📢 Объявления домов будут поститься в чат {target_id}")
        else:
            current = await get_config(f"poster_houses_channel:{chat_id}")
            current_topic = await get_config(f"poster_houses_topic:{chat_id}")
            info = f"Чат: <code>{current}</code>" if current else "этот чат"
            if current_topic:
                info += f", Топик: <code>{current_topic}</code>"
            await message.reply(f"📢 Текущий канал домов: {info}", parse_mode="HTML")
    elif action == "топик":
        mid = message.message_thread_id
        if not mid:
            await message.reply("❌ Эта команда работает только внутри топика (темы).")
            return
        await set_config(f"poster_cars_topic:{chat_id}", str(mid))
        await message.reply(f"✅ Сохранён топик ID {mid} для машин.")
    elif action == "дома_топик":
        mid = message.message_thread_id
        if not mid:
            await message.reply("❌ Эта команда работает только внутри топика (темы).")
            return
        await set_config(f"poster_houses_topic:{chat_id}", str(mid))
        await message.reply(f"✅ Сохранён топик ID {mid} для домов.")
    elif action == "прицепы_канал":
        if len(args) >= 3:
            target_raw = args[2].lower()
            if target_raw in ("этот_чат", "this_chat", "здесь"):
                await set_config(f"poster_trailers_channel:{chat_id}", "")
                await set_config(f"poster_trailers_topic:{chat_id}", "")
                await message.reply("📢 Объявления прицепов будут поститься в этот чат")
                return
            try:
                target_id = int(target_raw)
            except ValueError:
                try:
                    chat = await message.bot.get_chat(target_raw)
                    target_id = chat.id
                except Exception:
                    await message.reply("❌ Не могу найти чат", parse_mode="HTML")
                    return
            await set_config(f"poster_trailers_channel:{chat_id}", str(target_id))
            await set_config(f"poster_trailers_topic:{chat_id}", "")
            await message.reply(f"📢 Объявления прицепов будут поститься в чат {target_id}")
        else:
            current = await get_config(f"poster_trailers_channel:{chat_id}")
            current_topic = await get_config(f"poster_trailers_topic:{chat_id}")
            info = f"Чат: <code>{current}</code>" if current else "этот чат"
            if current_topic:
                info += f", Топик: <code>{current_topic}</code>"
            await message.reply(f"📢 Текущий канал прицепов: {info}", parse_mode="HTML")
    elif action == "прицепы_топик":
        mid = message.message_thread_id
        if not mid:
            await message.reply("❌ Эта команда работает только внутри топика (темы).")
            return
        await set_config(f"poster_trailers_topic:{chat_id}", str(mid))
        await message.reply(f"✅ Сохранён топик ID {mid} для прицепов.")
    elif action == "бизнесы_канал":
        if len(args) >= 3:
            target_raw = args[2].lower()
            if target_raw in ("этот_чат", "this_chat", "здесь"):
                await set_config(f"poster_businesses_channel:{chat_id}", "")
                await set_config(f"poster_businesses_topic:{chat_id}", "")
                await message.reply("📢 Объявления бизнесов будут поститься в этот чат")
                return
            try:
                target_id = int(target_raw)
            except ValueError:
                try:
                    chat = await message.bot.get_chat(target_raw)
                    target_id = chat.id
                except Exception:
                    await message.reply("❌ Не могу найти чат", parse_mode="HTML")
                    return
            await set_config(f"poster_businesses_channel:{chat_id}", str(target_id))
            await set_config(f"poster_businesses_topic:{chat_id}", "")
            await message.reply(f"📢 Объявления бизнесов будут поститься в чат {target_id}")
        else:
            current = await get_config(f"poster_businesses_channel:{chat_id}")
            current_topic = await get_config(f"poster_businesses_topic:{chat_id}")
            info = f"Чат: <code>{current}</code>" if current else "этот чат"
            if current_topic:
                info += f", Топик: <code>{current_topic}</code>"
            await message.reply(f"📢 Текущий канал бизнесов: {info}", parse_mode="HTML")
    elif action == "бизнесы_топик":
        mid = message.message_thread_id
        if not mid:
            await message.reply("❌ Эта команда работает только внутри топика (темы).")
            return
        await set_config(f"poster_businesses_topic:{chat_id}", str(mid))
        await message.reply(f"✅ Сохранён топик ID {mid} для бизнесов.")
    elif action == "прицепы" and len(args) >= 3:
        sub = args[2]
        if sub == "вкл":
            await set_config(f"poster_trailers_enabled:{chat_id}", "1")
            chats = await get_config("poster_chats") or ""
            if str(chat_id) not in chats.split(","):
                new_chats = ",".join(filter(None, [*chats.split(","), str(chat_id)]))
                await set_config("poster_chats", new_chats)
            await message.reply("✅ Авто-объявления прицепов включены")
        elif sub == "выкл":
            await set_config(f"poster_trailers_enabled:{chat_id}", "0")
            await message.reply("❌ Авто-объявления прицепов выключены")
        elif sub == "тест":
            t_topic_raw = await get_config(f"poster_trailers_topic:{chat_id}")
            t_topic = int(t_topic_raw) if t_topic_raw else None
            result = await force_post_trailer(message.bot, chat_id, t_topic)
            await message.reply(result, parse_mode="HTML")
        elif sub == "интервал" and len(args) >= 4:
            try:
                minutes = int(args[3])
                await set_config(f"poster_trailers_interval:{chat_id}", str(max(1, minutes)))
                await message.reply(f"✅ Интервал прицепов: {minutes} минут")
            except ValueError:
                await message.reply("❌ Укажите число минут")
        else:
            await message.reply("❌ Использование: <code>!объявления прицепы [вкл|выкл|тест|интервал N]</code>", parse_mode="HTML")
    elif action == "машины" and len(args) >= 3:
        sub = args[2]
        if sub == "вкл":
            await set_config(f"poster_enabled:{chat_id}", "1")
            chats = await get_config("poster_chats") or ""
            if str(chat_id) not in chats.split(","):
                new_chats = ",".join(filter(None, [*chats.split(","), str(chat_id)]))
                await set_config("poster_chats", new_chats)
            await message.reply("✅ Авто-объявления машин включены")
        elif sub == "выкл":
            await set_config(f"poster_enabled:{chat_id}", "0")
            await message.reply("❌ Авто-объявления машин выключены")
        elif sub == "тест":
            topic_raw = await get_config(f"poster_cars_topic:{chat_id}")
            topic = int(topic_raw) if topic_raw else None
            result = await force_post_one(message.bot, chat_id, topic)
            await message.reply(result, parse_mode="HTML")
        elif sub == "интервал" and len(args) >= 4:
            try:
                minutes = int(args[3])
                await set_config(f"poster_interval:{chat_id}", str(max(1, minutes)))
                await message.reply(f"✅ Интервал машин: {minutes} минут")
            except ValueError:
                await message.reply("❌ Укажите число минут")
        else:
            await message.reply("❌ Использование: <code>!объявления машины [вкл|выкл|тест|интервал N]</code>", parse_mode="HTML")
    elif action == "дома" and len(args) >= 3:
        sub = args[2]
        if sub == "вкл":
            await set_config(f"poster_houses_enabled:{chat_id}", "1")
            chats = await get_config("poster_chats") or ""
            if str(chat_id) not in chats.split(","):
                new_chats = ",".join(filter(None, [*chats.split(","), str(chat_id)]))
                await set_config("poster_chats", new_chats)
            await message.reply("✅ Авто-объявления домов включены")
        elif sub == "выкл":
            await set_config(f"poster_houses_enabled:{chat_id}", "0")
            await message.reply("❌ Авто-объявления домов выключены")
        elif sub == "тест":
            topic_raw = await get_config(f"poster_houses_topic:{chat_id}")
            topic = int(topic_raw) if topic_raw else None
            result = await force_post_house(message.bot, chat_id, topic)
            await message.reply(result, parse_mode="HTML")
        elif sub == "интервал" and len(args) >= 4:
            try:
                minutes = int(args[3])
                await set_config(f"poster_houses_interval:{chat_id}", str(max(1, minutes)))
                await message.reply(f"✅ Интервал домов: {minutes} минут")
            except ValueError:
                await message.reply("❌ Укажите число минут")
        else:
            await message.reply("❌ Использование: <code>!объявления дома [вкл|выкл|тест|интервал N]</code>", parse_mode="HTML")
    elif action == "бизнесы" and len(args) >= 3:
        sub = args[2]
        if sub == "вкл":
            await set_config(f"poster_businesses_enabled:{chat_id}", "1")
            chats = await get_config("poster_chats") or ""
            if str(chat_id) not in chats.split(","):
                new_chats = ",".join(filter(None, [*chats.split(","), str(chat_id)]))
                await set_config("poster_chats", new_chats)
            await message.reply("✅ Авто-объявления бизнесов включены")
        elif sub == "выкл":
            await set_config(f"poster_businesses_enabled:{chat_id}", "0")
            await message.reply("❌ Авто-объявления бизнесов выключены")
        elif sub == "тест":
            b_topic_raw = await get_config(f"poster_businesses_topic:{chat_id}")
            b_topic = int(b_topic_raw) if b_topic_raw else None
            result = await force_post_business(message.bot, chat_id, b_topic)
            await message.reply(result, parse_mode="HTML")
        elif sub == "интервал" and len(args) >= 4:
            try:
                minutes = int(args[3])
                await set_config(f"poster_businesses_interval:{chat_id}", str(max(1, minutes)))
                await message.reply(f"✅ Интервал бизнесов: {minutes} минут")
            except ValueError:
                await message.reply("❌ Укажите число минут")
        else:
            await message.reply("❌ Использование: <code>!объявления бизнесы [вкл|выкл|тест|интервал N]</code>", parse_mode="HTML")
    else:
        await message.reply(
            "❌ Неизвестная команда. Используй:\n"
            "<code>!объявления</code> — статус\n"
            "<code>!объявления машины вкл/выкл/тест/интервал N</code>\n"
            "<code>!объявления дома вкл/выкл/тест/интервал N</code>\n"
            "<code>!объявления прицепы вкл/выкл/тест/интервал N</code>\n"
            "<code>!объявления бизнесы вкл/выкл/тест/интервал N</code>",
            parse_mode="HTML",
        )


@router.message(Command("добавить_дом", prefix="!/"))
async def cmd_add_house(message: Message):
    if not await ensure_admin(message):
        return
    parts = message.text.split(maxsplit=8)
    if len(parts) < 8:
        # Show house types list
        hts = await get_all_house_types()
        nbs = await get_all_neighborhoods()
        ht_lines = [f"#{ht['id']} — {ht['type_name']} ({ht['bedrooms']}br, {ht['sqft']}sqft)" for ht in hts]
        nb_lines = [f"#{nb['id']} — {nb['name']}" for nb in nbs]
        await message.reply(
            "❌ Использование: <code>!добавить_дом ID_ТИПА ID_РАЙОНА цена</code>\n\n"
            "📋 <b>Типы домов:</b>\n" + "\n".join(ht_lines[:15]) +
            "\n\n🗺 <b>Районы:</b>\n" + "\n".join(nb_lines),
            parse_mode="HTML",
        )
        return
    try:
        ht_id = int(parts[1])
        nb_id = int(parts[2])
        price = int(parts[3])
    except ValueError:
        await message.reply("❌ ID типа, ID района и цена должны быть числами")
        return
    ht = await get_house_type(ht_id)
    nb = await get_neighborhood(nb_id)
    if not ht or not nb:
        await message.reply("❌ Тип дома или район не найдены. <code>!добавить_дом</code> без параметров — список.", parse_mode="HTML")
        return
    import random
    guid = f"admin_{ht_id}_{nb_id}_{random.randint(100000,999999)}"
    hid = await create_house_listing(message.chat.id, ht_id, nb_id, price, guid)
    await message.reply(
        f"✅ Дом добавлен!\n"
        f"🏠 #{hid} {ht['type_name']}\n"
        f"📍 <b>{nb['name']}</b>\n"
        f"💰 ${price:,} | 🛏 {ht['bedrooms']} | 🛁 {ht['bathrooms']} | 📐 {ht['sqft']} кв.футов",
        parse_mode="HTML",
    )


@router.message(Command("добавить_жилье", prefix="!/"))
async def cmd_add_gov_housing(message: Message):
    if not await ensure_admin(message):
        return

    photo_file_id = ""
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_file_id = message.reply_to_message.photo[-1].file_id

    parts = message.text.split(maxsplit=5)
    if len(parts) < 5:
        hts = await get_all_house_types()
        nbs = await get_all_neighborhoods()
        ht_lines = [f"#{ht['id']} — {ht['type_name']} ({ht['bedrooms']}br, {ht['sqft']}sqft)" for ht in hts]
        nb_lines = [f"#{nb['id']} — {nb['name']}" for nb in nbs]
        await message.reply(
            "❌ Использование: <code>!добавить_жилье ID_ТИПА ID_РАЙОНА цена @user [описание]</code>\n"
            "📸 Прикрепите фото или ответьте на фото\n\n"
            "📋 <b>Типы домов:</b>\n" + "\n".join(ht_lines) +
            "\n\n🗺 <b>Районы:</b>\n" + "\n".join(nb_lines),
            parse_mode="HTML",
        )
        return
    try:
        ht_id = int(parts[1])
        nb_id = int(parts[2])
        price = int(parts[3])
    except ValueError:
        await message.reply("❌ ID типа, ID района и цена должны быть числами")
        return
    ht = await get_house_type(ht_id)
    nb = await get_neighborhood(nb_id)
    if not ht or not nb:
        await message.reply("❌ Тип дома или район не найдены")
        return

    uid, target_name, target_username, _ = await resolve_target(message, [parts[0]] + parts[4:])
    if not uid:
        await message.reply("❌ Укажите пользователя (@username), которому выдаётся жильё")
        return

    desc = parts[5] if len(parts) >= 6 else (ht.get("description") or "")
    import random
    guid = f"gov_{ht_id}_{nb_id}_{random.randint(100000,999999)}"
    hid = await create_house_listing(
        message.chat.id, ht_id, nb_id, price, guid,
        photo_url=photo_file_id, owner_id=uid, desc_override=desc,
    )
    await message.reply(
        f"✅ <b>Гос. жильё выдано!</b>\n"
        f"🏠 #{hid} {ht['type_name']}\n"
        f"📍 <b>{nb['name']}</b>\n"
        f"💰 ${price:,} | 🛏 {ht['bedrooms']} | 🛁 {ht['bathrooms']} | 📐 {ht['sqft']} кв.футов\n"
        f"👤 Жилец: {target_name}",
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


USER_CARS_PER_PAGE = 10


def format_user_cars_page(vehicles: list, page: int, user_display: str) -> str:
    total = len(vehicles)
    start = page * USER_CARS_PER_PAGE
    end = min(start + USER_CARS_PER_PAGE, total)
    page_items = vehicles[start:end]

    lines = [f"🚗 <b>Автомобили пользователя {user_display}:</b> (всего {total})\n"]
    for v in page_items:
        lines.append(
            f"#{v['id']} — {v['year']} {v['make']} {v['model']} ({v['color']})\n"
            f"   Статус: {v['status']} | Цена: ${v['price']:,}"
        )
    return "\n".join(lines)


def user_cars_page_kb(page: int, total_pages: int, uid: int) -> InlineKeyboardMarkup:
    btns = []
    if page > 0:
        btns.append(InlineKeyboardButton(text="◀️", callback_data=f"usercars:стр:{page - 1}:{uid}"))
    btns.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        btns.append(InlineKeyboardButton(text="▶️", callback_data=f"usercars:стр:{page + 1}:{uid}"))
    return InlineKeyboardMarkup(inline_keyboard=[btns])


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
    page = 0
    total_pages = (len(vehicles) + USER_CARS_PER_PAGE - 1) // USER_CARS_PER_PAGE
    text = format_user_cars_page(vehicles, page, args[1])
    kb = user_cars_page_kb(page, total_pages, uid) if total_pages > 1 else None
    await message.reply(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.regexp(r"^usercars:стр:"))
async def user_cars_page_cb(query: CallbackQuery):
    try:
        parts = query.data.split(":")
        page = int(parts[2])
        uid = int(parts[3])
    except (ValueError, IndexError):
        await query.answer("❌ Ошибка данных", show_alert=True)
        return
    try:
        vehicles = await get_all_vehicles_by_owner(uid)
        if not vehicles:
            await query.message.edit_text("📭 У пользователя нет автомобилей")
            await query.answer()
            return
        total_pages = (len(vehicles) + USER_CARS_PER_PAGE - 1) // USER_CARS_PER_PAGE
        if page < 0 or page >= total_pages:
            await query.answer()
            return
        user_display = query.message.text.split("\n")[0].split("</b>")[0].split("пользователя ")[-1] if query.message.text else ""
        text = format_user_cars_page(vehicles, page, user_display)
        page_kb = user_cars_page_kb(page, total_pages, uid) if total_pages > 1 else None
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=page_kb)
        await query.answer()
    except Exception as e:
        await query.answer(f"❌ {e}", show_alert=True)


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
    if not await admin_give_vehicle(vid, uid, chat_id=message.chat.id):
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


@router.message(Command("добавить_авто", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_add_car(message: Message):
    if not await ensure_admin(message):
        return
    parts = message.text.split(maxsplit=6)
    if len(parts) < 5:
        await message.reply(
            "❌ Использование: <code>!добавить_авто Марка Модель Год Цена [пробег] [цвет]</code>\n"
            "Пример: <code>!добавить_авто BMW M3 2020 45000 30000 синий</code>",
            parse_mode="HTML",
        )
        return
    try:
        make = parts[1]
        model = parts[2]
        year = int(parts[3])
        price = int(parts[4])
    except ValueError:
        await message.reply("❌ Год и цена должны быть числами")
        return
    miles = int(parts[5]) if len(parts) > 5 else random.randint(1000, 50000)
    color = parts[6] if len(parts) > 6 else random.choice(["Черный", "Белый", "Синий", "Красный", "Серый", "Серебристый"])
    vin = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=17))
    license_plate = f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))}-{random.randint(100,999)}"
    city = random.choice(["Милуоки", "Мадисон", "Грин-Бей", "Апплтон", "О-Клэр", "Кеноша", "Расин", "Ла-Кросс"])
    vehicle_id = await create_vehicle(make, model, year, price, miles, city, vin, license_plate, color, "common", message.chat.id)
    await message.reply(
        f"✅ <b>Авто добавлено в салон!</b>\n\n"
        f"🚗 <b>{year} {make} {model}</b>\n"
        f"💰 Цена: ${price:,}\n"
        f"📏 Пробег: {miles:,} миль\n"
        f"🎨 Цвет: {color}\n"
        f"📍 Город: {city}\n"
        f"🆔 VIN: <code>{vin}</code>\n"
        f"🔑 Номера: {license_plate}\n"
        f"🏪 Номер в салоне: <b>#{vehicle_id}</b>",
        parse_mode="HTML",
    )


@router.message(Command("вернуть_вклад", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_close_deposit(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!вернуть_вклад ID</code>", parse_mode="HTML")
        return

    try:
        deposit_id = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите числовой ID вклада")
        return

    deposit = await get_deposit_by_id(deposit_id)
    if not deposit:
        await message.reply(f"❌ Вклад #{deposit_id} не найден")
        return
    if deposit["status"] != "active":
        await message.reply(f"❌ Вклад #{deposit_id} уже закрыт (статус: {deposit['status']})")
        return

    payout, interest = calc_deposit_payout(deposit)

    if not await withdraw_deposit(deposit_id):
        await message.reply(f"❌ Ошибка при закрытии вклада #{deposit_id}")
        return

    await update_balance(deposit["user_telegram_id"], payout, message.chat.id)
    await add_transaction(
        "deposit_close", None, deposit["user_telegram_id"], payout,
        f"Вклад #{deposit_id} принудительно закрыт админом {message.from_user.full_name}",
    )

    await message.reply(
        f"✅ Вклад #{deposit_id} закрыт!\n"
        f"💰 Сумма вклада: <b>{format_amount(deposit['amount'])}</b>\n"
        f"📈 Начислено процентов: <b>{format_amount(interest)}</b>\n"
        f"💵 Выплачено: <b>{format_amount(payout)}</b>",
        parse_mode="HTML",
    )


@router.message(Command("пересчет_кредитов", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_recalc_credits(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply(
            "❌ Использование: <code>!пересчет_кредитов СТАРЫЙ_% НОВЫЙ_%</code>\n"
            "Пример: <code>!пересчет_кредитов 10 20</code>",
            parse_mode="HTML",
        )
        return

    try:
        old_rate = float(args[1])
        new_rate = float(args[2])
    except ValueError:
        await message.reply("❌ Проценты должны быть числами")
        return

    credits = await get_all_credits("active")
    matching = [c for c in credits if c["interest_rate"] == old_rate]
    if not matching:
        await message.reply(f"❌ Нет активных кредитов со ставкой {old_rate}%")
        return

    updated = 0
    for c in matching:
        if await update_credit_interest_rate(c["id"], new_rate):
            updated += 1

    await message.reply(
        f"✅ Обновлено кредитов: <b>{updated}</b> из <b>{len(matching)}</b>\n"
        f"📊 Ставка изменена с <b>{old_rate}%</b> на <b>{new_rate}%</b>",
        parse_mode="HTML",
    )
