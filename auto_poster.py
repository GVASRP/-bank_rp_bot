import asyncio
import logging
import random
import re

import aiohttp
import feedparser

from database import is_listing_posted, mark_listing_posted, get_config

logger = logging.getLogger(__name__)

WI_CITIES = [
    ("milwaukee", "Милуоки"), ("madison", "Мадисон"), ("greenbay", "Грин-Бей"),
    ("appleton-oshkosh-fdl", "Апплтон"), ("eauclaire", "О-Клэр"), ("kenosha-racine", "Кеноша"),
    ("lacrosse", "Ла-Кросс"), ("sheboygan", "Шебойган"), ("wausau", "Восау"),
    ("janesville", "Джейнсвилл"), ("northernwi", "Северный Висконсин"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


async def fetch_rss(city_slug: str) -> list:
    url = f"https://{city_slug}.craigslist.org/search/cta?format=rss&s=0"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS, timeout=15) as resp:
            if resp.status != 200:
                logger.warning("HTTP %s for %s", resp.status, city_slug)
                return []
            text = await resp.text()
    feed = feedparser.parse(text)
    return [e for e in feed.entries if e.get("title")]


def extract_price(text: str) -> str:
    m = re.search(r'\$[\d,]+', text)
    return m.group(0) if m else ""


def extract_image(summary: str) -> str | None:
    m = re.search(r'<img[^>]+src="([^"]+)"', summary)
    return m.group(1) if m else None


def clean_summary(summary: str) -> str:
    return re.sub(r'<[^>]+>', '', summary).strip()[:200]


def build_caption(entry, city_name: str) -> str | None:
    title = entry.get("title", "").strip()
    link = entry.get("link", "")
    price = extract_price(title)
    desc = clean_summary(entry.get("summary", ""))
    if not title:
        return None
    msg = f"🚗 <b>{title}</b>\n📍 {city_name}, WI\n"
    if price:
        msg += f"💰 {price}\n"
    if desc:
        msg += f"📝 {desc}\n"
    msg += f"🔗 {link}"
    return msg


async def send_listing(bot, chat_id: int, entry, city_name: str) -> bool:
    guid = entry.get("id") or entry.get("link", "")
    if await is_listing_posted(guid):
        return False

    caption = build_caption(entry, city_name)
    if not caption:
        return False

    img_url = extract_image(entry.get("summary", ""))

    try:
        if img_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(img_url, headers=HEADERS, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        from aiogram.types import BufferedInputFile
                        photo = BufferedInputFile(data, filename="car.jpg")
                        await bot.send_photo(chat_id, photo, caption=caption, parse_mode="HTML")
                    else:
                        await bot.send_message(chat_id, caption, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await bot.send_message(chat_id, caption, parse_mode="HTML", disable_web_page_preview=True)

        await mark_listing_posted(guid)
        return True
    except Exception as e:
        logger.error("Send error: %s", e)
        return False


async def post_new_car(bot, chat_id: int) -> bool:
    cities = WI_CITIES.copy()
    random.shuffle(cities)

    for city_slug, city_name in cities:
        try:
            entries = await fetch_rss(city_slug)
        except Exception as e:
            logger.debug("Fetch error %s: %s", city_slug, e)
            continue

        for entry in entries:
            if await send_listing(bot, chat_id, entry, city_name):
                return True

    return False


async def force_post_one(bot, chat_id: int) -> str:
    random.shuffle(WI_CITIES)
    for city_slug, city_name in WI_CITIES[:3]:
        try:
            entries = await fetch_rss(city_slug)
        except Exception as e:
            continue
        for entry in entries:
            caption = build_caption(entry, city_name)
            if not caption:
                continue
            try:
                img_url = extract_image(entry.get("summary", ""))
                if img_url:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img_url, headers=HEADERS, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                from aiogram.types import BufferedInputFile
                                photo = BufferedInputFile(data, filename="car.jpg")
                                await bot.send_photo(chat_id, photo, caption=caption, parse_mode="HTML")
                            else:
                                await bot.send_message(chat_id, caption, parse_mode="HTML", disable_web_page_preview=True)
                else:
                    await bot.send_message(chat_id, caption, parse_mode="HTML", disable_web_page_preview=True)

                guid = entry.get("id") or entry.get("link", "")
                if guid:
                    await mark_listing_posted(guid)
                return f"✅ {entry.get('title','')[:60]} — {city_name}"
            except Exception as e:
                return f"❌ Ошибка: {e}"
    return "❌ Нет объявлений (возможно Craigslist блокирует запросы)"


async def auto_poster_loop(bot):
    logger.info("Auto-poster started")
    last_post = 0.0
    TICK = 15

    while True:
        enabled = await get_config("poster_enabled")
        chat_id_raw = await get_config("poster_chat_id")

        if enabled == "1" and chat_id_raw:
            interval_raw = await get_config("poster_interval")
            interval = int(interval_raw or "120")
            now = asyncio.get_event_loop().time()

            if now - last_post >= interval * 60:
                chat_id = int(chat_id_raw)
                ok = await post_new_car(bot, chat_id)
                if not ok:
                    logger.info("No new car listings found this cycle")
                last_post = now

        await asyncio.sleep(TICK)
