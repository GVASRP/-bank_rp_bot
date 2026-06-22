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
)
from utils import calc_credit_debt, calc_deposit_payout, format_amount, parse_amount, is_admin, get_user_mention, resolve_target

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

    target_id, target_name, hint = await resolve_target(message, args)
    if target_id is None:
        await message.reply(hint or "❌ Пользователь не найден")
        return

    await get_or_create_user(target_id)
    await update_balance(target_id, amount)
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

    target_id, target_name, hint = await resolve_target(message, args)
    if target_id is None:
        await message.reply(hint or "❌ Пользователь не найден")
        return

    user = await get_or_create_user(target_id)
    if user["balance"] < amount:
        await message.reply(
            f"❌ У пользователя недостаточно средств. Баланс: <b>{format_amount(user['balance'])}</b> долларов",
            parse_mode="HTML",
        )
        return

    await update_balance(target_id, -amount)
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

    target_id, target_name, hint = await resolve_target(message, args)
    if target_id is None:
        await message.reply(hint or "❌ Пользователь не найден")
        return

    await get_or_create_user(target_id)
    old_balance = (await get_user_by_telegram_id(target_id))["balance"]
    await set_balance(target_id, amount)
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
        await update_balance(request["user_telegram_id"], request["amount"])
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

    user = await get_user_by_telegram_id(request["user_telegram_id"])
    if not user or user["balance"] < request["amount"]:
        await update_deposit_request(request_id, "rejected")
        await message.reply(
            f"❌ Заявка #{request_id} отклонена — у пользователя недостаточно средств для вклада",
            parse_mode="HTML",
        )
        return

    await update_deposit_request(request_id, "approved")
    await create_deposit_account(request["user_telegram_id"], request["amount"], interest)
    await update_balance(request["user_telegram_id"], -request["amount"])
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
            user = await get_user_by_telegram_id(c["user_telegram_id"])
            name = user.get("first_name") or f"ID {c['user_telegram_id']}" if user else f"ID {c['user_telegram_id']}"
            lines.append(f"  #{c['id']} — {name}: {format_amount(c['amount'])} долларов")
        lines.append("")

    if deposits:
        lines.append("<b>Вклады:</b>")
        for d in deposits:
            user = await get_user_by_telegram_id(d["user_telegram_id"])
            name = user.get("first_name") or f"ID {d['user_telegram_id']}" if user else f"ID {d['user_telegram_id']}"
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
        user = await get_user_by_telegram_id(c["user_telegram_id"])
        name = user.get("first_name") or f"ID {c['user_telegram_id']}" if user else f"ID {c['user_telegram_id']}"
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
        user = await get_user_by_telegram_id(d["user_telegram_id"])
        name = user.get("first_name") or f"ID {d['user_telegram_id']}" if user else f"ID {d['user_telegram_id']}"
        payout, interest = calc_deposit_payout(d)
        lines.append(
            f"#{d['id']} — {name}\n"
            f"   Сумма: {format_amount(d['amount'])} | %: {d['interest_rate']}%/год\n"
            f"   Начислено: +{format_amount(interest)} | К выплате: <b>{format_amount(payout)}</b>"
        )

    await message.reply("\n".join(lines), parse_mode="HTML")
