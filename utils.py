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


async def resolve_target(message: Message, args: list) -> tuple[int | None, str | None, str]:
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        return target.id, target.full_name, ""

    if message.entities:
        for entity in message.entities:
            if entity.type == "text_mention":
                return entity.user.id, entity.user.full_name, ""

    username = ""
    if len(args) > 1:
        username = args[1].lstrip("@")
        user = await get_user_by_username(username)
        if user:
            return user["telegram_id"], user.get("first_name") or username, ""

    hint = ""
    if username:
        hint = (
            f"Пользователь @{username} не найден в базе.\n"
            f"Варианты:\n"
            f"1️⃣ Ответь на сообщение пользователя и напиши команду\n"
            f"2️⃣ Набери @ и выбери пользователя из списка (inline-упоминание)\n"
            f"3️⃣ Попроси пользователя написать /баланс — он зарегистрируется"
        )
    return None, None, hint


def get_user_mention(user_id: int, first_name: str = "Пользователь") -> str:
    return f"<a href='tg://user?id={user_id}'>{first_name}</a>"
