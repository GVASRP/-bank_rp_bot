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
    get_deposit_request,
    update_deposit_request,
    get_deposit_requests,
)
from utils import format_amount, parse_amount, is_admin, get_user_mention, resolve_target

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


@router.message(Command("начислить", prefixes="/!"), F.chat.type.in_({"group", "supergroup"}))
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


@router.message(Command("списать", prefixes="/!"), F.chat.type.in_({"group", "supergroup"}))
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


@router.message(Command("установить_баланс", prefixes="/!"), F.chat.type.in_({"group", "supergroup"}))
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


@router.message(Command("одобрить_кредит", prefixes="/!"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_approve_credit(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!одобрить_кредит id</code>", parse_mode="HTML")
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

    await update_credit_request(request_id, "approved")
    await update_balance(request["user_telegram_id"], request["amount"])
    await add_transaction("credit", None, request["user_telegram_id"], request["amount"], f"Кредит #{request_id} одобрен админом {message.from_user.full_name}")

    await message.reply(
        f"✅ Кредит #{request_id} на <b>{format_amount(request['amount'])}</b> долларов одобрен!\n"
        f"Средства зачислены пользователю.",
        parse_mode="HTML",
    )


@router.message(Command("отклонить_кредит", prefixes="/!"), F.chat.type.in_({"group", "supergroup"}))
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


@router.message(Command("одобрить_вклад", prefixes="/!"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_approve_deposit(message: Message):
    if not await ensure_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!одобрить_вклад id</code>", parse_mode="HTML")
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

    user = await get_user_by_telegram_id(request["user_telegram_id"])
    if not user or user["balance"] < request["amount"]:
        await update_deposit_request(request_id, "rejected")
        await message.reply(
            f"❌ Заявка #{request_id} отклонена — у пользователя недостаточно средств для вклада",
            parse_mode="HTML",
        )
        return

    await update_deposit_request(request_id, "approved")
    await update_balance(request["user_telegram_id"], -request["amount"])
    await add_transaction("deposit", request["user_telegram_id"], None, request["amount"], f"Вклад #{request_id} одобрен админом {message.from_user.full_name}")

    await message.reply(
        f"✅ Вклад #{request_id} на <b>{format_amount(request['amount'])}</b> долларов одобрен!\n"
        f"Средства списаны со счёта пользователя.",
        parse_mode="HTML",
    )


@router.message(Command("отклонить_вклад", prefixes="/!"), F.chat.type.in_({"group", "supergroup"}))
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


@router.message(Command("заявки", prefixes="/!"), F.chat.type.in_({"group", "supergroup"}))
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
