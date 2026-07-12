import random
import time

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import get_or_create_user, get_user_by_telegram_id, update_balance, add_transaction, get_config, set_config
from utils import format_amount

router = Router()

SLOT_EMOJIS = ["🍒", "🍋", "🍊", "🍇", "💎", "🎰"]
SLOT_WEIGHTS = [30, 25, 20, 15, 8, 2]

SLOT_PAYOUTS = {
    (5, 5, 5): ("JACKPOT", None),
    (4, 4, 4): (50, "💎💎💎 — x50"),
    (3, 3, 3): (20, "🍇🍇🍇 — x20"),
    (2, 2, 2): (15, "🍊🍊🍊 — x15"),
    (1, 1, 1): (10, "🍋🍋🍋 — x10"),
    (0, 0, 0): (5, "🍒🍒🍒 — x5"),
}

JACKPOT_FUND_PCT = 5


def weighted_choice() -> int:
    r = random.randint(1, sum(SLOT_WEIGHTS))
    cum = 0
    for i, w in enumerate(SLOT_WEIGHTS):
        cum += w
        if r <= cum:
            return i
    return 0


async def get_jackpot() -> int:
    raw = await get_config("casino_jackpot")
    return int(raw) if raw else 0


async def get_max_bet() -> int:
    raw = await get_config("casino_max_bet")
    return int(raw) if raw else 100_000


async def get_cooldown() -> float:
    raw = await get_config("casino_cooldown")
    return float(raw) if raw else 3.0


_last_bet: dict[int, float] = {}


async def check_cooldown(uid: int) -> float | None:
    cd = await get_cooldown()
    last = _last_bet.get(uid, 0)
    remaining = cd - (time.time() - last)
    if remaining > 0:
        return remaining
    return None


async def deduct_jackpot_fund(loss: int):
    fund = loss * JACKPOT_FUND_PCT // 100
    if fund > 0:
        cur = await get_jackpot()
        await set_config("casino_jackpot", str(cur + fund))


@router.message(Command("казино", prefix="!/"))
async def cmd_casino(message: Message):
    jackpot = await get_jackpot()
    max_bet = await get_max_bet()
    await message.reply(
        f"🎰 <b>Казино GreenVegas</b>\n\n"
        f"━━ <b>Игры</b> ━━\n"
        f"🪙 <code>!монетка N СТАВКА</code> — орёл/решка (x2, шанс 50%)\n"
        f"🎲 <code>!кости N СТАВКА</code> — угадай число (x6, шанс 16.6%)\n"
        f"🎰 <code>!слот N СТАВКА</code> — слот (x5..x50 + джекпот)\n\n"
        f"━━ <b>Правила</b> ━━\n"
        f"📌 Макс. ставка: ${max_bet:,}\n"
        f"💎 Джекпот: ${jackpot:,}\n"
        f"📊 {JACKPOT_FUND_PCT}% каждого проигрыша уходит в джекпот\n"
        f"⏳ Задержка между ставками: {await get_cooldown():.0f} сек",
        parse_mode="HTML",
    )


@router.message(Command("монетка", prefix="!/"))
async def cmd_coinflip(message: Message):
    uid = message.from_user.id
    remaining = await check_cooldown(uid)
    if remaining:
        await message.reply(f"⏳ Подождите {remaining:.0f} сек перед новой ставкой")
        return

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
    max_bet = await get_max_bet()
    if bet < 1 or bet > max_bet:
        await message.reply(f"❌ Ставка от $1 до ${max_bet:,}", parse_mode="HTML")
        return

    if not await update_balance(uid, -bet, message.chat.id):
        user = await get_user_by_telegram_id(uid, message.chat.id)
        await message.reply(f"❌ Недостаточно средств. Баланс: {format_amount(user['balance'] if user else 0)}", parse_mode="HTML")
        return

    _last_bet[uid] = time.time()
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
        await deduct_jackpot_fund(bet)
        await add_transaction("casino_loss", None, uid, -bet, f"Монетка — проигрыш (${bet:,})")
        await message.reply(
            f"🪙 <b>Монетка</b>\n\n"
            f"Ваш выбор: {'орёл' if choice == 1 else 'решка'}\n"
            f"Выпало: {'орёл' if result == 1 else 'решка'}\n\n"
            f"😔 Проигрыш. ${bet:,} ушло в казино.",
            parse_mode="HTML",
        )


@router.message(Command("кости", prefix="!/"))
async def cmd_dice(message: Message):
    uid = message.from_user.id
    remaining = await check_cooldown(uid)
    if remaining:
        await message.reply(f"⏳ Подождите {remaining:.0f} сек перед новой ставкой")
        return

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
    max_bet = await get_max_bet()
    if bet < 1 or bet > max_bet:
        await message.reply(f"❌ Ставка от $1 до ${max_bet:,}", parse_mode="HTML")
        return

    if not await update_balance(uid, -bet, message.chat.id):
        user = await get_user_by_telegram_id(uid, message.chat.id)
        await message.reply(f"❌ Недостаточно средств. Баланс: {format_amount(user['balance'] if user else 0)}", parse_mode="HTML")
        return

    _last_bet[uid] = time.time()
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
        await deduct_jackpot_fund(bet)
        await add_transaction("casino_loss", None, uid, -bet, f"Кости — проигрыш (${bet:,})")
        await message.reply(
            f"🎲 <b>Кости</b>\n\n"
            f"Ваше число: {choice}\n"
            f"Выпало: {result}\n\n"
            f"😔 Проигрыш. ${bet:,} ушло в казино.",
            parse_mode="HTML",
        )


@router.message(Command("слот", prefix="!/"))
async def cmd_slot(message: Message):
    uid = message.from_user.id
    remaining = await check_cooldown(uid)
    if remaining:
        await message.reply(f"⏳ Подождите {remaining:.0f} сек перед новой ставкой")
        return

    await get_or_create_user(uid, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Использование: <code>!слот СТАВКА</code>", parse_mode="HTML")
        return
    try:
        bet = int(parts[1])
    except ValueError:
        await message.reply("❌ Ставка должна быть числом")
        return
    max_bet = await get_max_bet()
    if bet < 1 or bet > max_bet:
        await message.reply(f"❌ Ставка от $1 до ${max_bet:,}", parse_mode="HTML")
        return

    if not await update_balance(uid, -bet, message.chat.id):
        user = await get_user_by_telegram_id(uid, message.chat.id)
        await message.reply(f"❌ Недостаточно средств. Баланс: {format_amount(user['balance'] if user else 0)}", parse_mode="HTML")
        return

    _last_bet[uid] = time.time()
    reels = [weighted_choice() for _ in range(3)]
    emojis = [SLOT_EMOJIS[r] for r in reels]
    line = "".join(emojis)

    key = tuple(reels)
    if key in SLOT_PAYOUTS:
        multiplier, display_name = SLOT_PAYOUTS[key]
        if multiplier == "JACKPOT":
            jackpot = await get_jackpot()
            payout = jackpot + bet * 2
            await update_balance(uid, payout, message.chat.id)
            await set_config("casino_jackpot", "0")
            await add_transaction("casino_jackpot", None, uid, payout, f"Слот — ДЖЕКПОТ (${payout:,})")
            await message.reply(
                f"🎰 <b>Слот</b>\n\n"
                f"<code>{line}</code>\n\n"
                f"👑👑👑 <b>ДЖЕКПОТ!</b> 👑👑👑\n"
                f"🎉 <b>Вы выиграли ${payout:,}!</b>",
                parse_mode="HTML",
            )
        else:
            payout = bet * multiplier
            await update_balance(uid, payout, message.chat.id)
            await add_transaction("casino_win", None, uid, payout, f"Слот — {display_name} (${payout:,})")
            await message.reply(
                f"🎰 <b>Слот</b>\n\n"
                f"<code>{line}</code>\n\n"
                f"{display_name}\n"
                f"🎉 <b>Вы выиграли ${payout:,}!</b>",
                parse_mode="HTML",
            )
    else:
        two = reels[:]
        two.sort()
        same = two[0] if two[0] == two[1] else two[1] if two[1] == two[2] else None
        if same is not None:
            if same >= 4:
                multiplier = 10
            elif same >= 3:
                multiplier = 5
            else:
                multiplier = 2
            payout = bet * multiplier
            await update_balance(uid, payout, message.chat.id)
            await add_transaction("casino_win", None, uid, payout, f"Слот — две {SLOT_EMOJIS[same]} (x{multiplier})")
            await message.reply(
                f"🎰 <b>Слот</b>\n\n"
                f"<code>{line}</code>\n\n"
                f"Две {SLOT_EMOJIS[same]} — x{multiplier}\n"
                f"🎉 <b>Вы выиграли ${payout:,}!</b>",
                parse_mode="HTML",
            )
        else:
            await deduct_jackpot_fund(bet)
            await add_transaction("casino_loss", None, uid, -bet, f"Слот — проигрыш (${bet:,})")
            await message.reply(
                f"🎰 <b>Слот</b>\n\n"
                f"<code>{line}</code>\n\n"
                f"😔 Проигрыш. ${bet:,} ушло в казино.",
                parse_mode="HTML",
            )
