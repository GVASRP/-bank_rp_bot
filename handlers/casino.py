import random

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import get_or_create_user, get_user_by_telegram_id, update_balance, add_transaction
from utils import format_amount

router = Router()


@router.message(Command("монетка", prefix="!/"))
async def cmd_coinflip(message: Message):
    uid = message.from_user.id
    await get_or_create_user(uid, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("❌ Использование: <code>!монетка 1(орёл)/2(решка) СТАВКА</code>", parse_mode="HTML")
        return
    try:
        choice = int(parts[1])
        bet = int(parts[2])
    except ValueError:
        await message.reply("❌ Номер и ставка должны быть числами")
        return
    if choice not in (1, 2):
        await message.reply("❌ 1 — орёл, 2 — решка")
        return
    if bet < 1:
        await message.reply("❌ Ставка должна быть положительной")
        return

    user = await get_user_by_telegram_id(uid, message.chat.id)
    if not user or user["balance"] < bet:
        await message.reply(f"❌ Недостаточно средств. Баланс: {format_amount(user['balance'] if user else 0)}", parse_mode="HTML")
        return

    await update_balance(uid, -bet, message.chat.id)
    result = random.randint(1, 2)
    win = result == choice
    if win:
        payout = bet * 2
        await update_balance(uid, payout, message.chat.id)
        await add_transaction("casino_win", None, uid, payout, f"Монетка — выигрыш x2 (${payout:,})")
        await message.reply(
            f"🪙 <b>Монетка</b>\n\n"
            f"Ваш выбор: {'орёл' if choice == 1 else 'решка'}\n"
            f"Выпало: {'орёл' if result == 1 else 'решка'}\n\n"
            f"🎉 <b>Вы выиграли ${payout:,}!</b>",
            parse_mode="HTML",
        )
    else:
        await add_transaction("casino_loss", None, uid, -bet, f"Монетка — проигрыш (${bet:,})")
        await message.reply(
            f"🪙 <b>Монетка</b>\n\n"
            f"Ваш выбор: {'орёл' if choice == 1 else 'решка'}\n"
            f"Выпало: {'орёл' if result == 1 else 'решка'}\n\n"
            f"😔 Проигрыш. ${bet:,}.",
            parse_mode="HTML",
        )


@router.message(Command("кости", prefix="!/"))
async def cmd_dice(message: Message):
    uid = message.from_user.id
    await get_or_create_user(uid, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("❌ Использование: <code>!кости 1-6 СТАВКА</code>", parse_mode="HTML")
        return
    try:
        choice = int(parts[1])
        bet = int(parts[2])
    except ValueError:
        await message.reply("❌ Число и ставка должны быть числами")
        return
    if choice < 1 or choice > 6:
        await message.reply("❌ Выберите число от 1 до 6")
        return
    if bet < 1:
        await message.reply("❌ Ставка должна быть положительной")
        return

    user = await get_user_by_telegram_id(uid, message.chat.id)
    if not user or user["balance"] < bet:
        await message.reply(f"❌ Недостаточно средств. Баланс: {format_amount(user['balance'] if user else 0)}", parse_mode="HTML")
        return

    await update_balance(uid, -bet, message.chat.id)
    result = random.randint(1, 6)
    win = result == choice
    if win:
        payout = bet * 6
        await update_balance(uid, payout, message.chat.id)
        await add_transaction("casino_win", None, uid, payout, f"Кости — выигрыш x6 (${payout:,})")
        await message.reply(
            f"🎲 <b>Кости</b>\n\n"
            f"Ваше число: {choice}\n"
            f"Выпало: {result}\n\n"
            f"🎉 <b>Вы выиграли ${payout:,}!</b>",
            parse_mode="HTML",
        )
    else:
        await add_transaction("casino_loss", None, uid, -bet, f"Кости — проигрыш (${bet:,})")
        await message.reply(
            f"🎲 <b>Кости</b>\n\n"
            f"Ваше число: {choice}\n"
            f"Выпало: {result}\n\n"
            f"😔 Проигрыш. ${bet:,}.",
            parse_mode="HTML",
        )
