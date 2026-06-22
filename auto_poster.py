import asyncio
import logging
import random
import re

import feedparser

from database import is_listing_posted, mark_listing_posted, get_config

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

WISCONSIN_CITIES = [
    "appleton", "eauclaire", "greenbay", "janesville",
    "kenosha-racine", "lacrosse", "madison", "milwaukee",
    "sheboygan", "wausau", "northernwi",
]

CITY_NAMES = {
    "newyork": "Нью-Йорк", "losangeles": "Лос-Анджелес", "chicago": "Чикаго",
    "houston": "Хьюстон", "phoenix": "Финикс", "sandiego": "Сан-Диего",
    "dallas": "Даллас", "miami": "Майами", "seattle": "Сиэтл",
    "sfbay": "Сан-Франциско", "boston": "Бостон", "denver": "Денвер",
    "lasvegas": "Лас-Вегас", "portland": "Портленд", "atlanta": "Атланта",
    "wisconsin": "Висконсин",
    "appleton": "Апплтон", "eauclaire": "О-Клэр", "greenbay": "Грин-Бей",
    "janesville": "Джейнсвилл", "kenosha-racine": "Кеноша-Расин", "lacrosse": "Ла-Кросс",
    "madison": "Мадисон", "milwaukee": "Милуоки", "sheboygan": "Шебойган",
    "wausau": "Восау", "northernwi": "Северный Висконсин",
}


def extract_price(text: str) -> str:
    m = re.search(r'\$[\d,]+', text)
    return m.group(0) if m else ""


def clean_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text)


def format_listing(entry, city_name: str) -> str | None:
    title = entry.get("title", "").strip()
    link = entry.get("link", "")
    summary = clean_html(entry.get("summary", ""))[:250]
    price = extract_price(title)

    if not title:
        return None

    msg = f"🚗 <b>{title}</b>\n📍 {city_name}\n"
    if price:
        msg += f"💰 {price}\n"
    if summary:
        msg += f"📝 {summary}\n"
    msg += f"🔗 {link}"
    return msg


async def fetch_entries(city: str) -> list:
    category = "cta"
    url = f"https://{city}.craigslist.org/search/{category}?format=rss&s=0"
    feed = await asyncio.to_thread(feedparser.parse, url, agent=USER_AGENT)
    return [e for e in feed.entries if e.get("title")]


async def post_new_listings(bot, chat_id: int, city: str, city_name: str, max_count: int = 1):
    try:
        entries = await fetch_entries(city)
    except Exception as e:
        logger.warning("RSS fetch error (%s): %s", city, e)
        return

    posted = 0
    for entry in entries:
        if posted >= max_count:
            break
        guid = entry.get("id") or entry.get("link", "")
        if not guid:
            continue
        if await is_listing_posted(guid):
            continue

        text = format_listing(entry, city_name)
        if not text:
            continue

        try:
            await bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True)
            await mark_listing_posted(guid)
            posted += 1
            await asyncio.sleep(2)
        except Exception as e:
            logger.error("Send error: %s", e)


async def auto_poster_loop(bot):
    logger.info("Auto-poster started")
    wi_index = 0
    while True:
        enabled = await get_config("poster_enabled")
        chat_id_raw = await get_config("poster_chat_id")
        interval_raw = await get_config("poster_interval")

        if enabled == "1" and chat_id_raw:
            chat_id = int(chat_id_raw)
            interval = int(interval_raw or "120")
            city = await get_config("poster_city") or "newyork"

            if city == "wisconsin":
                actual_city = WISCONSIN_CITIES[wi_index % len(WISCONSIN_CITIES)]
                wi_index += 1
                city_name = CITY_NAMES.get(actual_city, actual_city)
                await post_new_listings(bot, chat_id, actual_city, city_name, 1)
            else:
                city_name = CITY_NAMES.get(city, city)
                await post_new_listings(bot, chat_id, city, city_name, 1)

            await asyncio.sleep(interval * 60)
        else:
            await asyncio.sleep(60)
