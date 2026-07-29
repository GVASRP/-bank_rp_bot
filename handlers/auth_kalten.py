import aiohttp
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from config import KALTENGRAM_WEB_URL

router = Router()


async def verify_code(code: str, tg_id: str, username: str, first_name: str) -> tuple[bool, str]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{KALTENGRAM_WEB_URL}/api/auth/telegram/verify",
                json={
                    "code": code,
                    "telegram_id": tg_id,
                    "username": username,
                    "first_name": first_name,
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if resp.ok:
                    return True, "✅ You're logged in! Go back to the browser."
                else:
                    return False, f"❌ {data.get('error', 'Invalid or expired code')}. Try again from web app."
    except Exception:
        return False, "❌ Server error. Try again later."


@router.callback_query(F.data.regexp(r"^kalten:allow:"))
async def kalten_allow_cb(query: CallbackQuery):
    await query.answer()
    code = query.data.split(":", 2)[2]
    ok, msg = await verify_code(
        code,
        str(query.from_user.id),
        query.from_user.username or "",
        query.from_user.first_name or "",
    )
    await query.edit_message_text(msg)


@router.callback_query(F.data == "kalten:cancel")
async def kalten_cancel_cb(query: CallbackQuery):
    await query.answer()
    await query.edit_message_text("Login cancelled.")


@router.message(Command("auth", prefix="!/"))
async def kalten_auth_command(message: Message):
    code = message.text.split(maxsplit=1)
    if len(code) < 2 or not code[1].strip():
        await message.reply("Usage: /auth CODE")
        return

    ok, msg = await verify_code(
        code[1].strip(),
        str(message.from_user.id),
        message.from_user.username or "",
        message.from_user.first_name or "",
    )
    await message.reply(msg)
