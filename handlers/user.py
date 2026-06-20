from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user,
    get_user_by_telegram_id,
    get_user_by_username,
    update_balance,
    add_transaction,
    get_transactions,
    create_credit_request,
    create_deposit_request,
    get_balance,
)
from utils import format_amount, parse_amount

router = Router()


async def resolve_target(message: Message, args: list) -> tuple[int | None, str | None]:
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        return target.id, target.full_name
    if message.entities:
        for entity in message.entities:
            if entity.type == "text_mention":
                return entity.user.id, entity.user.full_name
    if len(args) > 1:
        username = args[1].lstrip("@")
        user = await get_user_by_username(username)
        if user:
            return user["telegram_id"], user.get("first_name") or username
        return None, username
    return None, None


@router.message(Command("баланс"))
async def cmd_balance(message: Message):
    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    await message.reply(f"💰 Ваш баланс: <b>{format_amount(user['balance'])}</b> монет", parse_mode="HTML")


@router.message(Command("перевести"))
async def cmd_transfer(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply(
            "❌ Использование: <code>/перевести @user сумма</code>\n"
            "Или ответь на сообщение пользователя: <code>/перевести сумма</code>",
            parse_mode="HTML",
        )
        return

    amount = parse_amount(args[2])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму (целое положительное число)", parse_mode="HTML")
        return

    target_id, target_name = await resolve_target(message, args)
    if target_id is None:
        await message.reply(
            "❌ Пользователь не найден. Упомяните его через @, используйте встроенное упоминание Telegram "
            "или ответьте на его сообщение.",
            parse_mode="HTML",
        )
        return

    if target_id == message.from_user.id:
        await message.reply("❌ Нельзя перевести деньги самому себе")
        return

    sender = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    if sender["balance"] < amount:
        await message.reply(
            f"❌ Недостаточно средств. Баланс: <b>{format_amount(sender['balance'])}</b> монет",
            parse_mode="HTML",
        )
        return

    await update_balance(message.from_user.id, -amount)
    await update_balance(target_id, amount)
    await add_transaction(
        "transfer",
        message.from_user.id,
        target_id,
        amount,
        f"Перевод от {message.from_user.full_name} к {target_name}",
    )

    await message.reply(
        f"✅ Переведено <b>{format_amount(amount)}</b> монет пользователю {target_name}",
        parse_mode="HTML",
    )


@router.message(Command("история"))
async def cmd_history(message: Message):
    await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    transactions = await get_transactions(message.from_user.id, limit=15)
    if not transactions:
        await message.reply("📭 История операций пуста")
        return

    lines = ["📜 <b>История операций (последние 15):</b>\n"]
    for t in transactions:
        sign = "+" if t["receiver_telegram_id"] == message.from_user.id else "-"
        if t["type"] == "transfer":
            lines.append(
                f"{'📤' if t['sender_telegram_id'] == message.from_user.id else '📥'} "
                f"{sign}{format_amount(t['amount'])} — {t['created_at']}"
            )
        elif t["type"] == "credit":
            lines.append(f"💰 +{format_amount(t['amount'])} (кредит) — {t['created_at']}")
        elif t["type"] == "deposit":
            lines.append(f"🏦 -{format_amount(t['amount'])} (вклад) — {t['created_at']}")
        elif t["type"] == "admin_add":
            lines.append(f"💳 +{format_amount(t['amount'])} (начислено) — {t['created_at']}")
        elif t["type"] == "admin_remove":
            lines.append(f"💳 -{format_amount(t['amount'])} (списано) — {t['created_at']}")

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("запросить_кредит"))
async def cmd_request_credit(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>/запросить_кредит сумма</code>", parse_mode="HTML")
        return

    amount = parse_amount(args[1])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму")
        return

    request_id = await create_credit_request(message.from_user.id, amount)
    await message.reply(
        f"📄 Запрос на кредит <b>{format_amount(amount)}</b> монет отправлен!\n"
        f"Номер заявки: <b>#{request_id}</b>\n"
        f"Ожидайте подтверждения администратора.",
        parse_mode="HTML",
    )


@router.message(Command("запросить_вклад"))
async def cmd_request_deposit(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>/запросить_вклад сумма</code>", parse_mode="HTML")
        return

    amount = parse_amount(args[1])
    if amount is None:
        await message.reply("❌ Укажите корректную сумму")
        return

    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    if user["balance"] < amount:
        await message.reply(
            f"❌ Недостаточно средств. Баланс: <b>{format_amount(user['balance'])}</b> монет",
            parse_mode="HTML",
        )
        return

    request_id = await create_deposit_request(message.from_user.id, amount)
    await message.reply(
        f"📄 Запрос на вклад <b>{format_amount(amount)}</b> монет отправлен!\n"
        f"Номер заявки: <b>#{request_id}</b>\n"
        f"Ожидайте подтверждения администратора.",
        parse_mode="HTML",
    )
