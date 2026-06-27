import logging
from datetime import datetime

from aiogram import Bot

logger = logging.getLogger(__name__)
from aiogram.enums import ChatMemberStatus
from aiogram.types import Message

from database import get_user_by_username, get_or_create_user

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

    chat_id = message.chat.id
    username = args[1].lstrip("@") if len(args) > 1 else ""

    # Collect all text_mention entities for cross-reference
    mention_map = {}
    if message.entities:
        for entity in message.entities:
            if entity.type == "text_mention":
                mention_map[entity.user.id] = entity.user

    # Try typed username first
    if username:
        user = await get_user_by_username(username, chat_id)
        if user:
            # If entity has same telegram_id but fresher username, use entity data
            if user["telegram_id"] in mention_map:
                entity_user = mention_map[user["telegram_id"]]
                if entity_user.username and entity_user.username.lower() != (user.get("username") or "").lower():
                    return entity_user.id, entity_user.full_name, entity_user.username, ""
            # Verify current Telegram username via API to catch stale DB data
            try:
                chat = await message.bot.get_chat(user["telegram_id"])
                chat_username = (chat.username or "").lower()
                db_username = (user.get("username") or "").lower()
                if chat_username != db_username:
                    # Stale username — clear it from DB so next lookup won't find it
                    await get_or_create_user(user["telegram_id"], "", chat.first_name or "", chat_id)
                    user = None
            except Exception as e:
                logger.warning(f"resolve_target: get_chat failed for uid {user['telegram_id']}: {e}")
                # Can't verify username — don't trust stale DB data
                user = None
            if user:
                return user["telegram_id"], user.get("first_name") or username, user.get("username"), ""

    # Fallback: use text_mention entity (authoritative telegram_id)
    if mention_map:
        for eid, entity_user in mention_map.items():
            return entity_user.id, entity_user.full_name, entity_user.username, ""

    # Fallback: mention entities → extract username
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention_text = message.text[entity.offset:entity.offset + entity.length]
                entity_username = mention_text.lstrip("@")
                user = await get_user_by_username(entity_username, chat_id)
                if user:
                    return user["telegram_id"], user.get("first_name") or entity_username, user.get("username"), ""

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
