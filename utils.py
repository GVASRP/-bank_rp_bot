from datetime import datetime

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import Message

from database import get_user_by_username

ADMIN_CACHE = {}


def format_amount(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def parse_amount(text: str) -> int | None:
    text = text.replace(" ", "").replace(",", ".").strip()
    try:
        amount = int(float(text))
        if amount <= 0:
            return None
        return amount
    except (ValueError, TypeError):
        return None


async def is_admin(bot: Bot, chat_id: int, user_id: int, force_refresh: bool = False) -> bool:
    cache_key = (chat_id, user_id)
    if not force_refresh and cache_key in ADMIN_CACHE:
        return ADMIN_CACHE[cache_key]
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        result = member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
        ADMIN_CACHE[cache_key] = result
        return result
    except Exception:
        return False


async def resolve_target(message: Message, args: list) -> tuple[int | None, str | None, str | None, str]:
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        return target.id, target.full_name, target.username, ""

    if message.entities:
        for entity in message.entities:
            if entity.type == "text_mention":
                return entity.user.id, entity.user.full_name, entity.user.username, ""

    username = ""
    if len(args) > 1:
        username = args[1].lstrip("@")
        user = await get_user_by_username(username)
        if user:
            return user["telegram_id"], user.get("first_name") or username, user.get("username"), ""

    hint = ""
    if username:
        hint = (
            f"Пользователь @{username} не найден в базе.\n"
            f"Варианты:\n"
            f"1️⃣ Ответь на сообщение пользователя и напиши команду\n"
            f"2️⃣ Набери @ и выбери пользователя из списка (inline-упоминание)\n"
            f"3️⃣ Попроси пользователя написать /баланс — он зарегистрируется"
        )
    return None, None, None, hint


def get_user_mention(user_id: int, first_name: str = "Пользователь") -> str:
    return f"<a href='tg://user?id={user_id}'>{first_name}</a>"


def get_user_display(user: dict | None, default: str = "Пользователь") -> str:
    if not user:
        return default
    username = user.get("username")
    first_name = user.get("first_name")
    if username:
        return f"@{username}"
    return first_name or default


def calc_deposit_payout(deposit: dict) -> tuple:
    try:
        created = datetime.strptime(deposit["created_at"], "%Y-%m-%d %H:%M:%S")
        delta = datetime.now() - created
        days_held = delta.total_seconds() / 86400
        if days_held < 1:
            days_held = 1
        interest = int(deposit["amount"] * deposit["interest_rate"] * days_held / 36500)
    except (ValueError, KeyError):
        interest = 0
    payout = deposit["amount"] + interest
    return payout, interest


def calc_credit_debt(credit: dict) -> dict:
    try:
        created = datetime.strptime(credit["created_at"], "%Y-%m-%d %H:%M:%S")
        delta = datetime.now() - created
        days_held = delta.total_seconds() / 86400
        if days_held < 1:
            days_held = 1
        total_interest = int(credit["amount"] * credit["interest_rate"] * days_held / 36500)
    except (ValueError, KeyError):
        total_interest = 0
    interest_paid = credit.get("interest_paid", 0)
    interest_due = total_interest - interest_paid
    if interest_due < 0:
        interest_due = 0
    remaining_principal = credit.get("remaining_principal", credit.get("remaining", credit["amount"]))
    total_debt = remaining_principal + interest_due
    return {
        "remaining_principal": remaining_principal,
        "interest_paid": interest_paid,
        "interest_due": interest_due,
        "total_interest": total_interest,
        "total_debt": total_debt,
    }
