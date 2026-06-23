import asyncio
import logging
import random
import time

import aiohttp

from database import is_listing_posted, mark_listing_posted, get_config, set_config, create_vehicle

logger = logging.getLogger(__name__)

WIKI_SEARCH = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=%s&format=json&srlimit=3"
WIKI_IMAGE = "https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&titles=%s&format=json&pithumbsize=600"

COLORS = [
    "Белый", "Чёрный", "Серебристый", "Серый", "Синий", "Красный",
    "Тёмно-синий", "Зелёный", "Бежевый", "Коричневый", "Бордовый",
    "Золотистый", "Оранжевый", "Жёлтый", "Фиолетовый", "Хаки",
]

COMMON_CARS = [
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

RARE_CARS = [
    ("Porsche", "911 Carrera"), ("Porsche", "Cayenne"),
    ("Lexus", "LC 500"), ("Lexus", "RX 350"),
    ("Jaguar", "F-Type"), ("Jaguar", "XF"),
    ("Maserati", "Ghibli"), ("Maserati", "Levante"),
    ("Alfa Romeo", "Giulia"),
    ("Volvo", "XC90"), ("Volvo", "S90"),
]

LEGENDARY_CARS = [
    ("Ferrari", "F8 Tributo"), ("Ferrari", "SF90 Stradale"), ("Ferrari", "Roma"),
    ("Lamborghini", "Huracan"), ("Lamborghini", "Urus"),
    ("Rolls-Royce", "Ghost"), ("Rolls-Royce", "Cullinan"),
    ("Bentley", "Continental GT"),
    ("McLaren", "720S"),
    ("Aston Martin", "DB11"),
]

YEARS = list(range(2014, 2026))

WI_CITIES_RU = [
    "Милуоки", "Мадисон", "Грин-Бей", "Апплтон", "О-Клэр", "Кеноша",
    "Расин", "Ла-Кросс", "Шебойган", "Восау", "Джейнсвилл",
]

CONDITIONS = ["отличное", "хорошее", "очень хорошее", "обслужена", "без нареканий", "ездит отлично"]
DAMAGED_CONDITIONS = ["битая", "после ДТП", "не на ходу", "тотал", "срочно на запчасти", "гнилая"]

FEATURES = ["климат-контроль", "подогрев сидений", "Bluetooth", "камера заднего вида",
    "кожаный салон", "полный привод (AWD)", "люк", "парктроники",
    "бесключевой доступ", "круиз-контроль", "CarPlay", "сигнализация", "тонировка",
    "новые шины", "ABS, ESP", "датчики дождя и света"]
TITLES = ["чистый", "в наличии", "срочно", "торг уместен", "обмен не интересует"]

DAMAGED_TITLES = ["битый", "нерабочий", "на запчасти", "срочно", "в ремонт"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

RARITY_WEIGHTS = {"common": 80, "damaged": 8, "rare": 9, "legendary": 3}
RARITY_MULTIPLIERS = {"common": 1.0, "damaged": 0.3, "rare": 2.5, "legendary": 8.0}
RARITY_NAMES = {"common": "", "damaged": "💥 Битый", "rare": "⭐ Редкий", "legendary": "🔥🔥🔥 МЕГА-КАР 🔥🔥🔥"}
RARITY_YEARS = {"common": (2014, 2025), "damaged": (2008, 2018), "rare": (2018, 2025), "legendary": (2020, 2025)}


def pick_rarity() -> str:
    roll = random.randint(1, 100)
    cumulative = 0
    for rarity, weight in RARITY_WEIGHTS.items():
        cumulative += weight
        if roll <= cumulative:
            return rarity
    return "damaged"


def generate_car() -> dict:
    rarity = pick_rarity()
    if rarity == "legendary":
        pool = LEGENDARY_CARS
    elif rarity == "rare":
        pool = RARE_CARS
    elif rarity == "damaged":
        pool = COMMON_CARS[:15]
    else:
        pool = COMMON_CARS

    make, model = random.choice(pool)
    yr_lo, yr_hi = RARITY_YEARS[rarity]
    year = random.randint(yr_lo, yr_hi)
    miles = random.randint(5000, 180000)
    base_prices = {2008: 2000, 2009: 2500, 2010: 3000, 2011: 3500, 2012: 4000, 2013: 5000,
                   2014: 6000, 2015: 8000, 2016: 10000, 2017: 13000, 2018: 16000,
                   2019: 19000, 2020: 22000, 2021: 26000, 2022: 30000, 2023: 35000,
                   2024: 40000, 2025: 46000}
    price = int((base_prices.get(year, 15000) + random.randint(-3000, 6000)) * RARITY_MULTIPLIERS[rarity])
    price = max(100, price)
    city = random.choice(WI_CITIES_RU)
    color = random.choice(COLORS)

    if rarity == "damaged":
        condition = random.choice(DAMAGED_CONDITIONS)
        features = random.sample(FEATURES, k=random.randint(0, 2))
        title = random.choice(DAMAGED_TITLES)
        desc = (
            f"{color.lower()} {make} {model} {year}, {miles:,} миль. {condition.capitalize()}, "
            f"{' • '.join(features) + ' • ' if features else ''}{title.capitalize()}."
        )
    else:
        condition = random.choice(CONDITIONS)
        features = random.sample(FEATURES, k=random.randint(3, 6))
        title = random.choice(TITLES)
        color_prefix = f"{color.lower()} " if rarity == "common" else ""
        desc = (
            f"{color_prefix}{make} {model} {year}, {miles:,} миль. {condition.capitalize()}, "
            f"{' • '.join(features)}. {title.capitalize()}."
        )

    vin = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=17))
    license_plate = f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))}-{random.randint(1000,9999)}"
    return {
        "make": make, "model": model, "year": year, "miles": miles,
        "price": price, "city": city, "description": desc, "vin": vin,
        "license_plate": license_plate, "color": color, "rarity": rarity,
        "guid": f"gen_{rarity}_{vin}",
    }


async def fetch_car_image(make: str, model: str) -> bytes | None:
    try:
        full = f"{make} {model}".replace("  ", " ")
        search_url = WIKI_SEARCH % full
        async with aiohttp.ClientSession() as s:
            async with s.get(search_url, headers=HEADERS, timeout=8) as r:
                if r.status != 200:
                    return None
                data = await r.json()
        pages = data.get("query", {}).get("search", [])
        if not pages:
            return None
        title = pages[0]["title"]
        img_url = WIKI_IMAGE % title.replace(" ", "_").replace("-", "_")
        async with aiohttp.ClientSession() as s:
            async with s.get(img_url, headers=HEADERS, timeout=8) as r:
                if r.status != 200:
                    return None
                data2 = await r.json()
        for pid, info in data2.get("query", {}).get("pages", {}).items():
            thumb = info.get("thumbnail", {}).get("source")
            if thumb:
                async with aiohttp.ClientSession() as s:
                    async with s.get(thumb, headers=HEADERS, timeout=10) as r:
                        if r.status == 200:
                            return await r.read()
    except Exception as e:
        logger.warning("Image fetch failed for %s %s: %s", make, model, e)
    return None


def format_caption(car: dict, vehicle_id: int) -> str:
    rarity_prefix = RARITY_NAMES[car["rarity"]]
    rarity_line = f"\n{rarity_prefix}" if rarity_prefix else ""
    return (
        f"🚗 <b>{car['year']} {car['make']} {car['model']}</b>\n"
        f"📍 {car['city']}, WI\n"
        f"💰 ${car['price']:,} | {car['miles']:,} миль\n"
        f"🎨 {car['color']}\n"
        f"🆔 Лот: <b>#{vehicle_id}</b>{rarity_line}\n"
        f"📝 {car['description']}"
    )


async def send_car(bot, chat_id: int, car: dict, message_thread_id: int | None = None) -> bool:
    if await is_listing_posted(car["guid"]):
        return False

    vehicle_id = await create_vehicle(
        car["make"], car["model"], car["year"], car["price"],
        car["miles"], car["city"], car["vin"], car["license_plate"],
        car["color"], car["rarity"],
    )
    caption = format_caption(car, vehicle_id)
    image = await fetch_car_image(car["make"], car["model"])

    try:
        send_args = {"chat_id": chat_id, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id
        if image:
            from aiogram.types import BufferedInputFile
            send_args["photo"] = BufferedInputFile(image, filename="car.jpg")
            await bot.send_photo(**send_args, caption=caption)
        else:
            await bot.send_message(**send_args, text=caption)

        await mark_listing_posted(car["guid"])
        return True
    except Exception as e:
        logger.error("Send error: %s", e)
        if "chat not found" in str(e).lower():
            logger.warning("Chat %s not found — disabling poster for this chat", chat_id)
            try:
                await set_config(f"poster_enabled:{chat_id}", "0")
            except Exception:
                pass
        return False


async def post_new_car(bot, chat_id: int, message_thread_id: int | None = None) -> bool:
    for _ in range(50):
        car = generate_car()
        if not await is_listing_posted(car["guid"]):
            return await send_car(bot, chat_id, car, message_thread_id)
    return False


async def force_post_one(bot, chat_id: int, message_thread_id: int | None = None) -> str:
    car = generate_car()
    vehicle_id = await create_vehicle(
        car["make"], car["model"], car["year"], car["price"],
        car["miles"], car["city"], car["vin"], car["license_plate"],
        car["color"], car["rarity"],
    )
    caption = format_caption(car, vehicle_id)
    image = await fetch_car_image(car["make"], car["model"])
    try:
        send_args = {"chat_id": chat_id, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id
        if image:
            from aiogram.types import BufferedInputFile
            send_args["photo"] = BufferedInputFile(image, filename="car.jpg")
            await bot.send_photo(**send_args, caption=caption)
        else:
            await bot.send_message(**send_args, text=caption)
        await mark_listing_posted(car["guid"])
        badge = RARITY_NAMES[car["rarity"]]
        return f"✅ #{vehicle_id} {car['year']} {car['make']} {car['model']} — {car['city']} {badge}"
    except Exception as e:
        return f"❌ Ошибка: {e}"


async def auto_poster_loop(bot):
    logger.info("Auto-poster loop started (bot=%s)", type(bot).__name__)
    TICK = 15
    errors = 0
    counter = 0

    while True:
        try:
            counter += 1
            if counter % 40 == 0:
                logger.info("Auto-poster heartbeat (tick %s)", counter)

            all_config = await get_config("poster_chats") or ""
            chat_ids = [c for c in all_config.split(",") if c]
            logger.debug("Poster check: %s chats configured", len(chat_ids))

            for cid_str in chat_ids:
                chat_id = int(cid_str)
                enabled = await get_config(f"poster_enabled:{chat_id}")
                if enabled != "1":
                    continue

                interval_raw = await get_config(f"poster_interval:{chat_id}")
                interval_min = int(interval_raw) if interval_raw and interval_raw.isdigit() else 120
                target_raw = await get_config(f"poster_cars_channel:{chat_id}")
                target = int(target_raw) if target_raw else chat_id
                topic_raw = await get_config(f"poster_cars_topic:{chat_id}")
                topic = int(topic_raw) if topic_raw else None

                last_key = f"poster_last_post:{chat_id}"
                last_raw = await get_config(last_key)
                last_ts = float(last_raw) if last_raw else 0.0
                now = time.time()
                elapsed = now - last_ts
                needed = interval_min * 60

                logger.debug("Chat %s: enabled, interval=%s min, elapsed=%.0f/%.0f sec",
                             chat_id, interval_min, elapsed, needed)

                if elapsed >= needed:
                    logger.info("Posting car for chat %s (interval=%s min, elapsed=%.0f sec)",
                                chat_id, interval_min, elapsed)
                    ok = await post_new_car(bot, target, topic)
                    # always update timestamp to prevent spam loop on errors
                    await set_config(last_key, str(now))
                    if ok:
                        errors = 0
                    else:
                        logger.warning("Post failed for chat %s, will retry later", chat_id)
        except Exception as e:
            logger.error("Auto-poster loop error: %s", e, exc_info=True)
            errors += 1
            if errors > 10:
                logger.critical("Too many poster errors, sleeping 5 min")
                await asyncio.sleep(300)
                errors = 0

        await asyncio.sleep(TICK)
