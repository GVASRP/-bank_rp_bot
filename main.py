import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, BOT_PROXY
from database import init_db
from handlers import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)


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

    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot, allowed_updates=["message"])
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
