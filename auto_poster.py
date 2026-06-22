import asyncio
import logging
import random
import re

import aiohttp

from database import is_listing_posted, mark_listing_posted, get_config, set_config, create_vehicle

logger = logging.getLogger(__name__)

WIKI_URL = "https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&titles=%s&format=json&pithumbsize=600"

CARS = [
    ("Honda", "Civic"), ("Honda", "Accord"), ("Honda", "CR-V"), ("Honda", "Pilot"),
    ("Toyota", "Camry"), ("Toyota", "Corolla"), ("Toyota", "RAV4"), ("Toyota", "Tacoma"),
    ("Ford", "F-150"), ("Ford", "Escape"), ("Ford", "Explorer"), ("Ford", "Mustang"),
    ("Chevrolet", "Silverado"), ("Chevrolet", "Equinox"), ("Chevrolet", "Tahoe"),
    ("BMW", "3 Series"), ("BMW", "5 Series"), ("BMW", "X3"),
    ("Mercedes-Benz", "C-Class"), ("Mercedes-Benz", "E-Class"), ("Mercedes-Benz", "GLC"),
    ("Audi", "A4"), ("Audi", "Q5"), ("Audi", "Q7"),
    ("Subaru", "Outback"), ("Subaru", "Forester"), ("Subaru", "Crosstrek"),
    ("Jeep", "Wrangler"), ("Jeep", "Grand Cherokee"), ("Jeep", "Cherokee"),
    ("Nissan", "Altima"), ("Nissan", "Rogue"), ("Nissan", "Frontier"),
    ("Volkswagen", "Jetta"), ("Volkswagen", "Passat"), ("Volkswagen", "Tiguan"),
    ("Hyundai", "Elantra"), ("Hyundai", "Tucson"), ("Hyundai", "Santa Fe"),
    ("Kia", "Forte"), ("Kia", "Soul"), ("Kia", "Sorento"),
    ("Mazda", "CX-5"), ("Mazda", "Mazda3"), ("Mazda", "CX-9"),
    ("Dodge", "Charger"), ("Dodge", "Durango"), ("Ram", "1500"),
    ("GMC", "Sierra"), ("GMC", "Yukon"), ("GMC", "Terrain"),
]

YEARS = list(range(2014, 2026))

WI_CITIES_RU = [
    "Милуоки", "Мадисон", "Грин-Бей", "Апплтон", "О-Клэр", "Кеноша",
    "Расин", "Ла-Кросс", "Шебойган", "Восау", "Джейнсвилл",
]

CONDITIONS = ["отличное", "хорошее", "очень хорошее", "обслужена", "без нареканий", "ездит отлично"]
FEATURES = ["климат-контроль", "подогрев сидений", "Bluetooth", "камера заднего вида",
    "кожаный салон", "полный привод (AWD)", "люк", "парктроники",
    "бесключевой доступ", "круиз-контроль", "CarPlay", "сигнализация", "тонировка",
    "новые шины", "ABS, ESP", "датчики дождя и света"]
TITLES = ["чистый", "в наличии", "срочно", "торг уместен", "обмен не интересует"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def generate_car() -> dict:
    make, model = random.choice(CARS)
    year = random.choice(YEARS)
    miles = random.randint(10000, 160000)
    base_prices = {2014: 6000, 2015: 8000, 2016: 10000, 2017: 13000, 2018: 16000,
                   2019: 19000, 2020: 22000, 2021: 26000, 2022: 30000, 2023: 35000,
                   2024: 40000, 2025: 46000}
    price = base_prices.get(year, 15000) + random.randint(-3000, 6000)
    price = max(1000, price)
    city = random.choice(WI_CITIES_RU)
    condition = random.choice(CONDITIONS)
    features = random.sample(FEATURES, k=random.randint(3, 6))
    title = random.choice(TITLES)
    vin = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=17))
    desc = (
        f"{make} {model} {year}, {miles:,} миль. {condition.capitalize()}, "
        f"{' • '.join(features)}. {title.capitalize()}."
    )
    license_plate = f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))}-{random.randint(1000,9999)}"
    return {
        "make": make, "model": model, "year": year, "miles": miles,
        "price": price, "city": city, "description": desc, "vin": vin,
        "license_plate": license_plate,
        "guid": f"gen_{vin}",
    }


async def fetch_car_image(make: str, model: str) -> bytes | None:
    search = f"{make}_{model.replace(' ','_')}".replace("-","_")
    url = WIKI_URL % search
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=HEADERS, timeout=8) as r:
                if r.status != 200:
                    return None
                data = await r.json()
        pages = data.get("query", {}).get("pages", {})
        for pid, info in pages.items():
            thumb = info.get("thumbnail", {}).get("source")
            if thumb:
                async with aiohttp.ClientSession() as s:
                    async with s.get(thumb, headers=HEADERS, timeout=10) as r:
                        if r.status == 200:
                            return await r.read()
    except Exception:
        pass
    return None


def format_caption(car: dict, vehicle_id: int) -> str:
    return (
        f"🚗 <b>{car['year']} {car['make']} {car['model']}</b>\n"
        f"📍 {car['city']}, WI\n"
        f"💰 ${car['price']:,} | {car['miles']:,} миль\n"
        f"🆔 ID: <b>#{vehicle_id}</b>\n"
        f"📝 {car['description']}\n"
        f"🔑 Номера: {car['license_plate']}"
    )


async def send_car(bot, chat_id: int, car: dict) -> bool:
    if await is_listing_posted(car["guid"]):
        return False

    vehicle_id = await create_vehicle(
        car["make"], car["model"], car["year"], car["price"],
        car["miles"], car["city"], car["vin"], car["license_plate"],
    )
    caption = format_caption(car, vehicle_id)
    image = await fetch_car_image(car["make"], car["model"])

    try:
        if image:
            from aiogram.types import BufferedInputFile
            photo = BufferedInputFile(image, filename="car.jpg")
            await bot.send_photo(chat_id, photo, caption=caption, parse_mode="HTML")
        else:
            await bot.send_message(chat_id, caption, parse_mode="HTML")

        await mark_listing_posted(car["guid"])
        return True
    except Exception as e:
        logger.error("Send error: %s", e)
        return False


async def post_new_car(bot, chat_id: int) -> bool:
    for _ in range(10):
        car = generate_car()
        if not await is_listing_posted(car["guid"]):
            return await send_car(bot, chat_id, car)
    return False


async def force_post_one(bot, chat_id: int) -> str:
    car = generate_car()
    vehicle_id = await create_vehicle(
        car["make"], car["model"], car["year"], car["price"],
        car["miles"], car["city"], car["vin"], car["license_plate"],
    )
    caption = format_caption(car, vehicle_id)
    image = await fetch_car_image(car["make"], car["model"])
    try:
        if image:
            from aiogram.types import BufferedInputFile
            photo = BufferedInputFile(image, filename="car.jpg")
            await bot.send_photo(chat_id, photo, caption=caption, parse_mode="HTML")
        else:
            await bot.send_message(chat_id, caption, parse_mode="HTML")
        await mark_listing_posted(car["guid"])
        return f"✅ #{vehicle_id} {car['year']} {car['make']} {car['model']} — {car['city']}"
    except Exception as e:
        return f"❌ Ошибка: {e}"


async def auto_poster_loop(bot):
    logger.info("Auto-poster started")
    last_post = {}
    TICK = 15

    while True:
        all_config = await get_config("poster_chats") or ""
        chat_ids = [c for c in all_config.split(",") if c]

        for cid_str in chat_ids:
            chat_id = int(cid_str)
            enabled = await get_config(f"poster_enabled:{chat_id}")
            if enabled != "1":
                continue
            interval_raw = await get_config(f"poster_interval:{chat_id}")
            interval = int(interval_raw or "120")
            now = asyncio.get_event_loop().time()
            last = last_post.get(chat_id, 0.0)
            if now - last >= interval * 60:
                await post_new_car(bot, chat_id)
                last_post[chat_id] = now

        await asyncio.sleep(TICK)
