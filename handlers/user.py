from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user,
    update_balance,
    add_transaction,
    get_transactions,
    get_all_users_ranked,
    create_credit_request,
    get_user_credits,
    get_credit_by_id,
    repay_credit,
    get_user_deposits,
    get_deposit_by_id,
    withdraw_deposit,
)
from utils import calc_credit_debt, calc_deposit_payout, format_amount, parse_amount, resolve_target

router = Router()


@router.message(Command("баланс", prefix="!/"))
async def cmd_balance(message: Message):
    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.chat.id,
    )
    await message.reply(f"💰 Ваш баланс: <b>{format_amount(user['balance'])}</b> долларов", parse_mode="HTML")


@router.message(Command("перевести", prefix="!/"))
async def cmd_transfer(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply(
            "❌ Использование: <code>!перевести @user сумма</code>\n"
            "Или ответь на сообщение пользователя: <code>!перевести сумма</code>",
            parse_mode="HTML",
        )
        return

    amount = parse_amount(args[2])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму", parse_mode="HTML")
        return

    target_id, target_name, hint = await resolve_target(message, args)
    if target_id is None:
        await message.reply(hint or "❌ Пользователь не найден", parse_mode="HTML")
        return

    if target_id == message.from_user.id:
        await message.reply("❌ Нельзя перевести деньги самому себе")
        return

    sender = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.chat.id,
    )
    if sender["balance"] < amount:
        await message.reply(
            f"❌ Недостаточно средств. Баланс: <b>{format_amount(sender['balance'])}</b> долларов",
            parse_mode="HTML",
        )
        return

    await update_balance(message.from_user.id, -amount, message.chat.id)
    await get_or_create_user(target_id, chat_id=message.chat.id)
    await update_balance(target_id, amount, message.chat.id)
    await add_transaction(
        "transfer",
        message.from_user.id,
        target_id,
        amount,
        f"Перевод от {message.from_user.full_name} к {target_name}",
    )

    await message.reply(
        f"✅ Переведено <b>{format_amount(amount)}</b> долларов пользователю {target_name}",
        parse_mode="HTML",
    )


@router.message(Command("история", prefix="!/"))
async def cmd_history(message: Message):
    await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.chat.id,
    )
    transactions = await get_transactions(message.from_user.id, limit=15)
    if not transactions:
        await message.reply("📭 История операций пуста")
        return

    lines = ["📜 <b>История операций (последние 15):</b>\n"]
    for t in transactions:
        if t["type"] == "transfer":
            lines.append(
                f"{'📤' if t['sender_telegram_id'] == message.from_user.id else '📥'} "
                f"{t['created_at']}"
            )
        elif t["type"] == "credit":
            lines.append(f"💰 Кредит одобрен: +{format_amount(t['amount'])} — {t['created_at']}")
        elif t["type"] == "deposit":
            lines.append(f"🏦 Вклад: -{format_amount(t['amount'])} — {t['created_at']}")
        elif t["type"] == "admin_add":
            lines.append(f"💳 Начислено: +{format_amount(t['amount'])} — {t['created_at']}")
        elif t["type"] == "admin_remove":
            lines.append(f"💳 Списано: -{format_amount(t['amount'])} — {t['created_at']}")

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("рейтинг", prefix="!/"))
async def cmd_ranking(message: Message):
    users = await get_all_users_ranked(chat_id=message.chat.id)
    if not users:
        await message.reply("📭 Пока нет зарегистрированных пользователей")
        return

    lines = ["🏆 <b>Таблица лидеров:</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, user in enumerate(users, 1):
        prefix = medals[i - 1] if i <= 3 else f"{i}."
        name = user.get("first_name") or user.get("username") or f"ID {user['telegram_id']}"
        lines.append(f"{prefix} {name} — <b>{format_amount(user['balance'])}</b> долларов")

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("запросить_кредит", prefix="!/"))
async def cmd_request_credit(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!запросить_кредит сумма</code>", parse_mode="HTML")
        return

    amount = parse_amount(args[1])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму")
        return

    request_id = await create_credit_request(message.from_user.id, amount)
    await message.reply(
        f"📄 Запрос на кредит <b>{format_amount(amount)}</b> долларов отправлен!\n"
        f"Номер заявки: <b>#{request_id}</b>\n"
        f"Ожидайте подтверждения администратора.",
        parse_mode="HTML",
    )


@router.message(Command("запросить_вклад", prefix="!/"))
async def cmd_request_deposit(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!запросить_вклад сумма</code>", parse_mode="HTML")
        return

    amount = parse_amount(args[1])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму")
        return

    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.chat.id,
    )
    if user["balance"] < amount:
        await message.reply(
            f"❌ Недостаточно средств. Баланс: <b>{format_amount(user['balance'])}</b> долларов",
            parse_mode="HTML",
        )
        return

    request_id = await create_deposit_request(message.from_user.id, amount)
    await message.reply(
        f"📄 Запрос на вклад <b>{format_amount(amount)}</b> долларов отправлен!\n"
        f"Номер заявки: <b>#{request_id}</b>\n"
        f"Ожидайте подтверждения администратора.",
        parse_mode="HTML",
    )


@router.message(Command("кредиты", prefix="!/"))
async def cmd_my_credits(message: Message):
    credits = await get_user_credits(message.from_user.id, "active")
    if not credits:
        await message.reply("📭 У вас нет активных кредитов")
        return

    lines = ["💳 <b>Ваши кредиты:</b>\n"]
    for c in credits:
        info = calc_credit_debt(c)
        lines.append(
            f"#{c['id']} — <b>{format_amount(c['amount'])}</b> долларов | {c['interest_rate']}%/год\n"
            f"   Срок: {c['duration_days']} дн. | Остаток тела: {format_amount(info['remaining_principal'])}\n"
            f"   % начислено: +{format_amount(info['total_interest'])} | Оплачено: {format_amount(info['interest_paid'])}\n"
            f"   Долг на сейчас: <b>{format_amount(info['total_debt'])}</b>"
        )

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("погасить", prefix="!/"))
async def cmd_repay_credit(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!погасить id_кредита сумма</code>", parse_mode="HTML")
        return

    try:
        credit_id = int(args[1])
    except ValueError:
        await message.reply("❌ ID кредита должен быть числом")
        return

    amount = parse_amount(args[2])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму")
        return

    credit = await get_credit_by_id(credit_id)
    if not credit:
        await message.reply(f"❌ Кредит #{credit_id} не найден")
        return
    if credit["user_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш кредит")
        return
    if credit["status"] != "active":
        await message.reply("❌ Кредит уже погашен")
        return

    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.chat.id,
    )

    debt_info = calc_credit_debt(credit)
    max_payment = min(user["balance"], debt_info["total_debt"])

    if amount > max_payment:
        amount = max_payment

    if user["balance"] < amount:
        await message.reply(
            f"❌ Недостаточно средств. Баланс: <b>{format_amount(user['balance'])}</b> долларов",
            parse_mode="HTML",
        )
        return

    interest_before = debt_info["interest_due"]
    await update_balance(message.from_user.id, -amount, message.chat.id)
    await repay_credit(credit_id, amount)
    await add_transaction("repay", message.from_user.id, None, amount, f"Погашение кредита #{credit_id}")

    credit = await get_credit_by_id(credit_id)
    if credit["status"] == "paid":
        await message.reply(
            f"✅ Кредит #{credit_id} полностью погашен!\n"
            f"Выплачено: <b>{format_amount(amount)}</b> долларов",
            parse_mode="HTML",
        )
    else:
        info = calc_credit_debt(credit)
        interest_paid_now = min(amount, interest_before)
        await message.reply(
            f"✅ Погашено <b>{format_amount(amount)}</b> долларов по кредиту #{credit_id}\n"
            f"Из них проценты: {format_amount(interest_paid_now)} | Тело: {format_amount(amount - interest_paid_now)}\n"
            f"Остаток тела: <b>{format_amount(info['remaining_principal'])}</b>\n"
            f"Долг на сейчас: <b>{format_amount(info['total_debt'])}</b>",
            parse_mode="HTML",
        )


@router.message(Command("вклады", prefix="!/"))
async def cmd_my_deposits(message: Message):
    deposits = await get_user_deposits(message.from_user.id, "active")
    if not deposits:
        await message.reply("📭 У вас нет активных вкладов")
        return

    lines = ["🏛 <b>Ваши вклады:</b>\n"]
    for d in deposits:
        payout, interest = calc_deposit_payout(d)
        lines.append(
            f"#{d['id']} — <b>{format_amount(d['amount'])}</b> долларов\n"
            f"   Ставка: {d['interest_rate']}%/год | Начислено: +{format_amount(interest)}\n"
            f"   Текущая сумма: <b>{format_amount(payout)}</b>"
        )

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("вывести", prefix="!/"))
async def cmd_withdraw_deposit(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!вывести id_вклада</code>", parse_mode="HTML")
        return

    try:
        deposit_id = int(args[1])
    except ValueError:
        await message.reply("❌ ID вклада должен быть числом")
        return

    deposit = await get_deposit_by_id(deposit_id)
    if not deposit:
        await message.reply(f"❌ Вклад #{deposit_id} не найден")
        return
    if deposit["user_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш вклад")
        return
    if deposit["status"] != "active":
        await message.reply("❌ Вклад уже выведен")
        return

    payout, interest = calc_deposit_payout(deposit)
    await withdraw_deposit(deposit_id)
    await update_balance(message.from_user.id, payout, message.chat.id)
    await add_transaction("withdraw", None, message.from_user.id, payout, f"Вывод вклада #{deposit_id} (начислено %: {interest})")

    await message.reply(
        f"✅ Вклад #{deposit_id} выведен!\n"
        f"Сумма: <b>{format_amount(deposit['amount'])}</b>\n"
        f"Начислено процентов: <b>+{format_amount(interest)}</b>\n"
        f"Итого получено: <b>{format_amount(payout)}</b> долларов",
        parse_mode="HTML",
    )
