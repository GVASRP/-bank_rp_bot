from aiogram import Bot
from aiogram.enums import ChatMemberStatus

ADMIN_CACHE = {}
ADMIN_CACHE_TTL = 60


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


def get_user_mention(user_id: int, first_name: str = "Пользователь") -> str:
    return f"<a href='tg://user?id={user_id}'>{first_name}</a>"
