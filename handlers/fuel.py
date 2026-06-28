from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import get_config, set_config, update_balance, add_transaction
from utils import format_amount, parse_amount, is_admin

router = Router()


@router.message(Command("цена_топлива", prefix="!/"))
async def cmd_fuel_price(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        current = await get_config(f"fuel_price:{message.chat.id}")
        if current:
            await message.reply(f"⛽ Текущая цена топлива: ${int(current):,}/ед")
        else:
            await message.reply("❌ Цена топлива не установлена. Использование: <code>!цена_топлива сумма</code>", parse_mode="HTML")
        return
    amount = parse_amount(args[1])
    if not amount or amount <= 0:
        await message.reply("❌ Укажите корректную сумму")
        return
    await set_config(f"fuel_price:{message.chat.id}", str(amount))
    await message.reply(f"✅ Цена топлива установлена: ${amount:,}/ед")


@router.message(Command("заправить", prefix="!/"))
async def cmd_refuel(message: Message):
    fuel_price = await get_config(f"fuel_price:{message.chat.id}")
    if not fuel_price:
        await message.reply("❌ Цена топлива ещё не установлена администратором")
        return
    fuel_price = int(fuel_price)

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply(f"⛽ Цена топлива: ${fuel_price:,}/ед\nИспользование: <code>!заправить количество</code>", parse_mode="HTML")
        return
    units = parse_amount(args[1])
    if not units or units <= 0:
        await message.reply("❌ Укажите корректное количество")
        return

    total = units * fuel_price
    balance = await update_balance(message.from_user.id, -total, message.chat.id)
    if balance is None:
        await message.reply("❌ Недостаточно средств")
        return

    await add_transaction("fuel", None, message.from_user.id, -total,
                          f"Заправка: {units} ед × ${fuel_price}")

    await message.reply(
        f"⛽ <b>Заправка</b>\n"
        f"📊 {units} ед × ${fuel_price:,} = ${total:,}\n"
        f"💰 Остаток: ${balance:,}",
        parse_mode="HTML",
    )
