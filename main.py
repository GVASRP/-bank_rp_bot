import asyncio
import logging
import os
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, BOT_PROXY
from database import set_config, get_or_create_user, set_balance
from database import init_db, close_conn
from handlers import router
from auto_poster import auto_poster_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)


async def health_check(request):
    return web.Response(text="OK")


async def run_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    port = int(os.getenv("PORT", "8000"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Веб-сервер для хелс-чеков запущен на порту %d", port)


async def on_startup(bot):
    logger.info("Auto-poster: creating background task")
    asyncio.create_task(auto_poster_loop(bot))
    await set_config("container_min_boost", "3000000")

    bot_me = await bot.get_me()
    bot_id = bot_me.id
    existing = await get_or_create_user(bot_id, bot_me.username or "", bot_me.first_name or "", 0)
    if existing and existing.get("balance", 0) == 0:
        await set_balance(bot_id, 50000, 0)
        logger.info("Bot user @%s (id=%d) registered with starting balance", bot_me.username, bot_id)
    else:
        logger.info("Bot user @%s (id=%d) already registered, balance=%s", bot_me.username, bot_id, existing.get("balance", 0) if existing else "?")


async def main():
    logger.info("Инициализация базы данных...")
    await init_db()

    kwargs = {"token": BOT_TOKEN, "default": DefaultBotProperties(parse_mode=ParseMode.HTML)}
    if BOT_PROXY:
        logger.info("Используется прокси: %s", BOT_PROXY)
        kwargs["proxy"] = BOT_PROXY
    bot = Bot(**kwargs)
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)

    await run_web_server()

    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await bot.session.close()
        await close_conn()


if __name__ == "__main__":
    asyncio.run(main())
