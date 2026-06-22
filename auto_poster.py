import asyncio
import logging
import random

from database import is_listing_posted, mark_listing_posted, get_config

logger = logging.getLogger(__name__)

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

MILES = {
    2014: (80000, 160000), 2015: (70000, 140000), 2016: (60000, 130000),
    2017: (50000, 120000), 2018: (40000, 100000), 2019: (30000, 90000),
    2020: (20000, 80000), 2021: (15000, 60000), 2022: (10000, 45000),
    2023: (5000, 30000), 2024: (1000, 15000), 2025: (100, 5000),
}

WI_CITIES = [
    ("Милуоки", "Milwaukee, WI"), ("Мадисон", "Madison, WI"), ("Грин-Бей", "Green Bay, WI"),
    ("Апплтон", "Appleton, WI"), ("О-Клэр", "Eau Claire, WI"), ("Кеноша", "Kenosha, WI"),
    ("Расин", "Racine, WI"), ("Ла-Кросс", "La Crosse, WI"), ("Шебойган", "Sheboygan, WI"),
    ("Восау", "Wausau, WI"), ("Джейнсвилл", "Janesville, WI"), ("Фонд-дю-Лак", "Fond du Lac, WI"),
]

CONDITIONS = [
    "отличное состояние", "хорошее состояние", "очень хорошее состояние",
    "обслужена", "в идеале", "без нареканий", "ездит отлично",
]

FEATURES = [
    "ABS, подушки безопасности", "климат-контроль", "подогрев сидений",
    "Bluetooth, AUX", "камера заднего вида", "кожаный салон",
    "полный привод (AWD)", "передний привод (FWD)", "люк", "парктроники",
    "бесключевой доступ", "круиз-контроль", "CarPlay/Android Auto",
    "сигнализация", "тонировка", "новые шины", "чистый салон",
]

TITLES = ["чистый", "в наличии", "срочно", "торг уместен", "обмен не интересует"]


def generate_car() -> dict:
    make, model = random.choice(CARS)
    year = random.choice(YEARS)
    miles_range = MILES.get(year, (30000, 100000))
    miles = random.randint(*miles_range)
    base_price = {
        2014: 5000, 2015: 7000, 2016: 9000, 2017: 11000,
        2018: 14000, 2019: 17000, 2020: 20000, 2021: 24000,
        2022: 28000, 2023: 32000, 2024: 38000, 2025: 45000,
    }.get(year, 15000)
    price = base_price + random.randint(-3000, 5000)
    price = max(1000, price)
    city_ru, city_en = random.choice(WI_CITIES)
    condition = random.choice(CONDITIONS)
    features = random.sample(FEATURES, k=random.randint(3, 6))
    title = random.choice(TITLES)

    description = (
        f"{make} {model} {year}, {miles:,} миль. {condition.capitalize()}, "
        f"{' • '.join(features)}. {title.capitalize()}. "
        f"Звоните, пишите — покажу, расскажу."
    )

    vin = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=17))

    return {
        "make": make,
        "model": model,
        "year": year,
        "miles": miles,
        "price": price,
        "city_ru": city_ru,
        "city_en": city_en,
        "condition": condition,
        "features": features,
        "description": description,
        "vin": vin,
        "guid": f"gen_{vin}_{random.randint(1000,9999)}",
    }


def format_car(car: dict) -> str:
    price_str = f"${car['price']:,}"
    miles_str = f"{car['miles']:,} миль"
    return (
        f"🚗 <b>{car['year']} {car['make']} {car['model']}</b>\n"
        f"📍 {car['city_ru']}, WI\n"
        f"💰 {price_str} | {miles_str}\n"
        f"📝 {car['description'][:200]}\n"
        f"🆔 VIN: {car['vin']}"
    )


async def post_new_car(bot, chat_id: int) -> bool:
    for _ in range(5):
        car = generate_car()
        if not await is_listing_posted(car["guid"]):
            text = format_car(car)
            try:
                await bot.send_message(chat_id, text, parse_mode="HTML")
                await mark_listing_posted(car["guid"])
                return True
            except Exception as e:
                logger.error("Send error: %s", e)
                return False
    return False


async def force_post_one(bot, chat_id: int) -> str:
    car = generate_car()
    text = format_car(car)
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
        await mark_listing_posted(car["guid"])
        return f"✅ {car['year']} {car['make']} {car['model']} — {car['city_ru']}"
    except Exception as e:
        return f"❌ Ошибка: {e}"


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
                await post_new_car(bot, chat_id)
                last_post = now

        await asyncio.sleep(TICK)
