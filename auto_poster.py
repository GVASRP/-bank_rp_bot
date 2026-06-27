import asyncio
import logging
import random
import time
from io import BytesIO

import aiohttp
from PIL import Image, ImageDraw, ImageFont

from database import is_listing_posted, mark_listing_posted, get_config, set_config, create_vehicle

logger = logging.getLogger(__name__)

WIKI_SEARCH = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=%s&format=json&srlimit=3"
WIKI_IMAGE = "https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&titles=%s&format=json&pithumbsize=600"

BRAND_TO_REAL = {
    "Arrow": "Pontiac", "Avanta": "Fictional", "Bandit": "Ford",
    "Barchetta": "Maserati", "BKM": "BMW", "Brawnson": "GMC",
    "BullHorn": "Dodge", "Caline": "Saleen", "Celestial": "Tesla",
    "Chevlon": "Chevrolet", "Chryslus": "Chrysler", "Colt": "Fictional",
    "Combi": "Kia", "DejaVu": "Fisker", "Durant": "Chevrolet",
    "Elgrand": "Infiniti", "Falcon": "Ford", "Ferdinand": "Porsche",
    "Globe": "Geo", "Horlock": "BlueBird", "Jupiter": "Saturn",
    "Leland": "Cadillac", "Mauntley": "Bentley", "Mayflower": "Plymouth",
    "Mazuku": "Mazda", "Mizushima": "Mitsubishi", "Navara": "Nissan",
    "Newcar": "Oldsmobile", "Normouth": "Rivian", "Oakura": "Fictional",
    "Origin": "Genesis", "Overland": "Jeep", "Revver": "Hummer",
    "Sentinel": "Lincoln", "Shizuoka": "Honda", "Silhouette": "Lamborghini",
    "Simple": "Lucid", "SirRodgers": "Rolls-Royce", "Sir Rodgers": "Rolls-Royce",
    "Stuttgart": "Mercedes-Benz", "Sumo": "Subaru", "Surrey": "McLaren",
    "Tuscani": "Hyundai", "Valley": "Holden", "Viking": "Volvo",
    "Vision": "Toyota", "Volzhsky": "Lada", "VSV": "HSV",
    "Western": "Fictional", "Wolfsburg": "Volkswagen",
    "Caseus": "Fictional", "Cobalt": "Carbon Motors", "Maverick": "Mercury",
    "Explorer": "International", "Marlin Motors": "Aston Martin", "BITSY": "MINI",
    "Beam": "NIO", "Bellco": "Shelby", "Eezee": "EZ-GO",
    "GIGA": "Lynk&Co", "Romalpha": "Alfa Romeo", "Acadia": "Mitsubishi",
    "Aikawa": "Isuzu", "Idea": "Smart", "Takeo": "Acura",
    "Century": "Lexus", "Bovine": "Dodge",
}

COLORS = [
    "Белый", "Чёрный", "Серебристый", "Серый", "Синий", "Красный",
    "Тёмно-синий", "Зелёный", "Бежевый", "Коричневый", "Бордовый",
    "Золотистый", "Оранжевый", "Жёлтый", "Фиолетовый", "Хаки",
]

GREENVILLE_CARS_BUDGET = [
    ("Mayflower", "Rage"), ("Leland", "Series 67 Skyview"), ("Chevlon", "Amigo"),
    ("Brawnson", "Noble Sport"), ("BullHorn", "Prancer"), ("Durant", "L/M 1500"),
    ("Falcon", "Pony"), ("Navara", "Star"), ("BKM", "W10"),
    ("Ferdinand", "Rapido"), ("BullHorn", "Canaveral"), ("Chevlon", "Monaco"),
    ("Arrow", "Phoenix"), ("Avanta", "Zeta"), ("Silhouette", "Attraente"),
    ("Ferdinand", "Tourer"), ("Mazuku", "Laguna"), ("Overland", "Iroquois"),
    ("Oakura", "300RS"), ("Overland", "Navajo"), ("Western", "Mamba"),
    ("Viking", "Torslanda"), ("Globe", "City AeroPod"), ("Newcar", "Falcata"),
    ("BullHorn", "Vivid"), ("Falcon", "Advance"), ("Falcon", "Traveller"),
    ("BullHorn", "Convoy"), ("Falcon", "Stallion"), ("BullHorn", "Dash"),
    ("Falcon", "Aquarius"), ("Jupiter", "Electron"), ("Chevlon", "Inferno"),
    ("Combi", "Satisfaction"), ("Falcon", "Distinct"), ("Chevlon", "Corbeta"),
    ("Chryslus", "Puma"), ("Falcon", "Wanderer"), ("Arrow", "Trybe"),
    ("BKM", "Regen"), ("Chevlon", "Platoro"), ("Chryslus", "FT Stroller"),
    ("Falcon", "Breeze"), ("Falcon", "Departure"), ("Horlock", "Patriot"),
    ("Aikawa", "Maxim"), ("Overland", "Apache"), ("Falcon", "Heritage"),
    ("Mizushima", "Yari"), ("Chevlon", "Zafiro"), ("Chryslus", "Comercio"),
    ("Shizuoka", "Chief"), ("Sumo", "Ota"), ("BullHorn", "Value"),
    ("Caline", "C281"), ("Falcon", "Prime"), ("Arrow", "Boomerang"),
    ("BKM", "Hofmeister"), ("Chryslus", "Aurora"), ("Chryslus", "Champion"),
    ("Elgrand", "Horizon"), ("Falcon", "Angle"), ("Mazuku", "Hofu"),
    ("Viking", "Gothenburg"), ("Wolfsburg", "Glide"), ("Revver", "Sport"),
    ("BKM", "Regen Coupe"), ("BKM", "Series10"), ("DejaVu", "Tradition"),
    ("Navara", "Imperium Coupe"), ("Chevlon", "Platoro"),
    ("Falcon", "Distinct"), ("Falcon", "Scavenger"), ("BKM", "Risen"),
    ("Brawnson", "Noble Sedan"), ("BKM", "Ziggy"),
    ("Chryslus", "Lotela"), ("Ferdinand", "Rapido"),
    ("BullHorn", "Buffalo"), ("BKM", "Munich"), ("BKM", "Rosenheim"),
    ("Durant", "Manta"), ("Brawnson", "Eminence"), ("Combi", "Karive"),
    ("Ferdinand", "Cajun"), ("Sumo", "Climax"),
    ("Brawnson", "Arlington"), ("Century", "Active"),
    ("Colt", "Okami"), ("Combi", "Karman"), ("Colt", "Riolu"),
    ("Acadia", "Yari"), ("Mazuku", "Sendai"),
]

GREENVILLE_CARS_MID = [
    ("Arrow", "Boomerang"), ("Falcon", "Stallion"), ("BullHorn", "Canaveral Champion"),
    ("BullHorn", "Conqueror"), ("Durant", "L/M 2500"), ("BKM", "Rheine"),
    ("Avanta", "Zeta Coupe"), ("Chryslus", "Empire"), ("Mazuku", "Sankakkei"),
    ("BullHorn", "Ninja"), ("Jupiter", "B.C."), ("Mizushima", "Syzygy"),
    ("Sentinel", "Parliament"), ("Chevlon", "Camion"), ("Sentinel", "Eurus"),
    ("BKM", "Gottfrieding"), ("Brawnson", "Boxy"), ("Ferdinand", "Roadster"),
    ("Maverick", "Criminal"), ("BKM", "Dingolfing"), ("Leland", "DeRoute"),
    ("Maverick", "Valiant"), ("Ferdinand", "Ultima"),
    ("Explorer", "Dependable 4300"), ("Marlin Motors", "Velindre"),
    ("Maverick", "Aristocrat"), ("Stuttgart", "GT Surrey"),
    ("BullHorn", "Bullet"), ("Chryslus", "Suburbia"), ("Idea", "Twofer"),
    ("Viking", "Kompakt"),
    ("Eezee", "GML"), ("Barchetta", "GrandTourer"),
    ("BKM", "Regen M Coupe"), ("Silhouette", "Gioiosa"), ("Cobalt", "Pursuiter"),
    ("Falcon", "Fission"), ("Surrey", "Renaissance"), ("Vision", "Prima"),
    ("Marlin Motors", "Swan"), ("Sentinel", "Adventurer"), ("Valley", "Admiral"),
    ("Avanta", "Rho"), ("BullHorn", "Vengence"),
    ("Bellco", "SixtySix"), ("BullHorn", "Location"),
    ("Mizushima", "Yari Evolution"), ("Stuttgart", "Kecskemét"),
    ("Stuttgart", "Vance"), ("Brawnson", "Noble Wagon"),
    ("Surrey", "LT-500"), ("Vision", "Puremia"),
    ("BullHorn", "SFP Python"), ("Falcon", "Advance Pro"),
    ("Stuttgart", "Essen"), ("Stuttgart", "Executive"),
    ("Stuttgart", "GT Surrey 722"), ("Vision", "Rainier"),
    ("VSV", "Admiral"), ("Acadia", "TSR"), ("Falcon", "Impact"),
    ("Marlin Motors", "Swan V8"), ("Sumo", "Woodlands"), ("BKM", "Dingolfing Coupé"),
    ("BKM", "Rosenheim Coupé"), ("Brawnson", "Cicada"), ("Leland", "LCS"),
    ("BKM", "Olympia"), ("BKM", "Risen"), ("Caseus", "E2"),
    ("Durant", "Voyager"), ("Leland", "LTS6"), ("Mizushima", "Fantasy"),
    ("Navara", "Compact"), ("Navara", "Senses"), ("Overland", "Apache"),
    ("Surrey", "Speedlet"), ("Vision", "Prairie"),
    ("Combi", "Portofino"), ("Marlin Motors", "Bristol"),
    ("Marlin Motors", "London"), ("Mazuku", "Hiro"), ("Navara", "Boundary"),
    ("Origin", "Busan"), ("Sir Rodgers", "Specter"), ("Stuttgart", "Bruecke"),
    ("BKM", "Köln"),
    ("BKM", "Munich M"), ("Combi", "Pandora"),
    ("Elgrand", "Immense"), ("Falcon", "Rampage"),
    ("Mauntley", "National GT"), ("Overland", "Apache L"),
    ("Sentinel", "Raider"),
    ("Beam", "SB7"),
    ("Brawnson", "Arlington XL"), ("Chevlon", "Corbeta Manta"),
    ("Falcon", "Cowboy"), ("Ferdinand", "Snapper"), ("Ferdinand", "Vivo"),
    ("Leland", "Vault"), ("Normouth", "SN-1"), ("Origin", "Ulsan"),
    ("Takeo", "Experience"), ("Viking", "Kiruna"), ("Vision", "Pioneer"),
    ("Western", "Kobold"), ("Colt", "Vulpes"),
    ("Silhouette", "Tifon"), ("SirRodgers", "Appiration"),
    ("BKM", "e70"), ("BKM", "eMX"),
]

GREENVILLE_CARS_PREMIUM = [
    ("Wolfsburg", "Van"), ("Volzhsky", "Rocket"), ("Sunray", "Thrust EV"),
    ("BullHorn", "Bufallo 1500"), ("BKM", "Munich"), ("Falcon", "Fowarder"),
    ("BITSY", "Classic Trophy Truck"), ("Tuscani", "Euphoria"),
    ("Celestial", "Type-1"), ("Navara", "Imperium"),
    ("Wolfsburg", "Crouton"), ("Revver", "Sport Utility"),
    ("Celestial", "Type-5"), ("BullHorn", "Determinator"),
    ("Bandit", "Predator"), ("Stuttgart", "Essen Coupe"),
    ("Stuttgart", "Koblenz"), ("BKM", "Olympia Coupé"),
    ("Celestial", "Type-5"), ("Western", "Kaiju"),
    ("Acadia", "Syzygy"), ("BKM", "Leipzig"), ("BKM", "Y60"),
    ("Celestial", "Type-7"), ("Navara", "Swindler"),
    ("Sentinel", "Platinum"), ("Viking", "Ghent"),
    ("BKM", "Donner Coupé"), ("BKM", "Donner M Coupé"),
    ("Overland", "Combatant"), ("Stuttgart", "Landschaft"),
    ("Stuttgart", "Sondergeland"), ("Stuttgart", "Vaihingen"),
    ("Western", "Sergal"),
    ("BKM", "eProton"), ("BKM", "Spartanburg"),
    ("Elgrand", "Percepttion"), ("Navara", "Squadron"),
    ("Revver", "EV"), ("Stuttgart", "ES"),
    ("Tuscani", "Maricopa"), ("Viking", "Blixt"),
    ("Western", "Protogen"), ("Western", "Synth LEU"),
    ("Leland", "LTS5 V"), ("Leland", "Vault K Edition"),
    ("Navara", "Territory"), ("Normouth", "TN-1"),
    ("Simple", "Atmos"), ("Vision", "Riptide"),
    ("BKM", "Series70"),
    ("BKM", "W70"), ("Chevlon", "Corbeta Manta E-Ray"),
    ("Normouth", "VN-1"), ("Tuscani", "Euphoria M"),
    ("Celestial", "Type-FS"), ("Celestial", "Type-FT"),
    ("DIRECT", "D3"),
]

GREENVILLE_CARS_LEGENDARY = [
    ("Stuttgart", "Munster"), ("Chryslus", "Jetstream"),
    ("BITSY", "8000 Roadster"), ("BullHorn", "Prancer TR Classic"),
    ("Leland", "Diamante"), ("Stuttgart", "Uhlenhaut"),
    ("Silhouette", "Gioiosa Super Corsa Speciale"),
    ("Arrow", "Phoenix Dimensional Traveler"),
    ("Navara", "Summit"), ("Navara", "Horizon GT-R Series-II"),
    ("BKM", "Regen M CSL"), ("Navara", "Horizon GT-R Navmo Z-Tune"),
    ("Chevlon", "Platoro 1500 The Oppressor"),
    ("BullHorn", "Grand Convoy"), ("Valley", "Admiral Sportback"),
    ("Stuttgart", "Kecskemét 45"), ("VSV", "Admiral GTSR W1"),
    ("Stuttgart", "Essen 63 Coupe"), ("Durant", "Manta H1300"),
    ("BKM", "Zoom"), ("BullHorn", "SuperCarrier"),
    ("Durant", "Camion HEEN"), ("Overland", "Apache SFP Heen H1000"),
    ("Sir Rodgers", "Constellation"), ("Overland", "Combatant Ghoul 6x6"),
    ("Stuttgart", "Vaihingen 63"),
    ("Surrey", "Grand Tourer"), ("Wolfsburg", "Symphony"),
    ("Elgrand", "Smyrna"), ("Ferdinand", "Rapido GT3"),
    ("GIGA", "G3"), ("SirRodgers", "Constellation K-Edition"),
    ("Western", "Protogen-X"), ("Celestial", "FCT"),
    ("Chevlon", "Corbeta Manta Z06"), ("Falcon", "Advance Beast Rawr"),
    ("Ferdinand", "Snapper GT4"), ("Silhouette", "Rinoceronte"),
    ("Stuttgart", "Wilhelm Munster"), ("Simple", "Atmos Sapphire"),
    ("Western", "Leviathan"),
]

LICENSED_CARS = [
    ("Audi", "A3"), ("Audi", "A4"), ("Audi", "A6"), ("Audi", "Q5"), ("Audi", "Q7"), ("Audi", "e-tron GT"),
    ("Renault", "5"),
    ("Jaguar", "F-Type"), ("Jaguar", "F-Pace"), ("Jaguar", "XF"), ("Jaguar", "XJ"), ("Jaguar", "E-Pace"),
    ("Land Rover", "Range Rover"), ("Land Rover", "Discovery"), ("Land Rover", "Defender 110"),
    ("Land Rover", "Range Rover Sport"), ("Land Rover", "Evoque"),
    ("Lotus", "Emira"), ("Lotus", "Evija"), ("Lotus", "Elise"),
    ("Pagani", "Huayra"), ("Pagani", "Utopia"), ("Pagani", "Zonda"),
    ("Fiat", "500"), ("Fiat", "500X"),
    ("Abarth", "595"), ("Abarth", "695"),
    ("Alfa Romeo", "Giulia"), ("Alfa Romeo", "Stelvio"), ("Alfa Romeo", "Tonale"),
    ("Alfa Romeo", "4C"), ("Alfa Romeo", "8C"), ("Alfa Romeo", "Spider"),
    ("Lancia", "Stratos"), ("Lancia", "Delta HF"),
    ("Saleen", "S1"), ("Saleen", "S7"),
]

LICENSED_BRANDS = {"Audi", "Renault", "Jaguar", "Land Rover", "Lotus", "Pagani", "Fiat", "Abarth", "Alfa Romeo", "Lancia", "Saleen"}

COMMON_CARS = GREENVILLE_CARS_BUDGET
RARE_CARS = GREENVILLE_CARS_MID + GREENVILLE_CARS_PREMIUM
LEGENDARY_CARS = GREENVILLE_CARS_LEGENDARY

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


def get_real_brand(make: str) -> str | None:
    return BRAND_TO_REAL.get(make)


def get_car_title(make: str, model: str) -> str:
    if make in LICENSED_BRANDS:
        return f"{make} {model}"
    real = get_real_brand(make)
    if real and real != "Fictional":
        return f"{make} {model} ({real} {model})"
    return f"{make} {model}"


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

    if rarity != "damaged" and random.random() < 0.30:
        make, model = random.choice(LICENSED_CARS)
    else:
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
    license_plate = f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))}-{random.randint(1000,9994)}"
    return {
        "make": make, "model": model, "year": year, "miles": miles,
        "price": price, "city": city, "description": desc, "vin": vin,
        "license_plate": license_plate, "color": color, "rarity": rarity,
        "guid": f"gen_{rarity}_{vin}",
    }


async def _search_wiki_image(search_term: str) -> bytes | None:
    try:
        search_url = WIKI_SEARCH % search_term
        async with aiohttp.ClientSession() as s:
            async with s.get(search_url, headers=HEADERS, timeout=8) as r:
                if r.status != 200:
                    return None
                data = await r.json()
        pages = data.get("query", {}).get("search", [])
        if not pages:
            return None
        title = pages[0]["title"]
        img_url = WIKI_IMAGE % title.replace(" ", "_")
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
        logger.warning("Wiki image search failed for '%s': %s", search_term, e)
    return None


def generate_placeholder_image(car: dict) -> bytes:
    width, height = 800, 500
    img = Image.new("RGB", (width, height), (20, 30, 55))
    draw = ImageDraw.Draw(img)

    try:
        ftitle = ImageFont.truetype("C:\\Windows\\Fonts\\Arial.ttf", 44)
        fsub = ImageFont.truetype("C:\\Windows\\Fonts\\Arial.ttf", 28)
        finfo = ImageFont.truetype("C:\\Windows\\Fonts\\Arial.ttf", 20)
    except Exception:
        try:
            ftitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
            fsub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
            finfo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except Exception:
            ftitle = fsub = finfo = ImageFont.load_default()

    draw.rectangle([0, 0, width, 6], fill=(60, 120, 255))
    draw.text((40, 25), "Greenville, Wisconsin", fill=(100, 140, 220), font=fsub)
    draw.text((40, 75), f"{car['year']} {car['make']} {car['model']}", fill=(255, 255, 255), font=ftitle)
    price_color = (80, 255, 120) if car["rarity"] != "damaged" else (255, 100, 80)
    draw.text((40, 140), f"${car['price']:,}", fill=price_color, font=fsub)
    y = 215
    for label, val in [("Пробег", f"{car['miles']:,} миль"), ("Цвет", car["color"]),
                        ("VIN", car["vin"]), ("Локация", car["city"] + ", WI")]:
        draw.text((40, y), f"{label}: {val}", fill=(180, 190, 210), font=finfo)
        y += 32
    rarity_colors = {"common": (100, 200, 255), "rare": (255, 200, 80), "legendary": (255, 80, 80), "damaged": (120, 120, 120)}
    rc = rarity_colors.get(car["rarity"], (200, 200, 200))
    draw.rectangle([width - 180, height - 55, width - 20, height - 25], fill=rc)
    rtxt = car["rarity"].upper()
    tw, _ = draw.textbbox((0, 0), rtxt, font=finfo)[2:4]
    draw.text((width - 100 - tw // 2, height - 48), rtxt, fill=(255, 255, 255), font=finfo)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


async def fetch_car_image(make: str, model: str) -> bytes | None:
    real_brand = get_real_brand(make)
    if real_brand:
        img = await _search_wiki_image(f"{real_brand} {model}")
        if img:
            return img
    img = await _search_wiki_image(f"{make} {model}")
    if img:
        return img
    return None


def format_caption(car: dict, vehicle_id: int) -> str:
    rarity_prefix = RARITY_NAMES[car["rarity"]]
    rarity_line = f"\n{rarity_prefix}" if rarity_prefix else ""
    title = get_car_title(car["make"], car["model"])
    real_brand = get_real_brand(car["make"])
    disclaimer = ""
    if car["make"] in LICENSED_BRANDS:
        disclaimer = "\n✅ Лицензионный дилер"
    elif real_brand and real_brand != "Fictional":
        disclaimer = f"\n📸 {real_brand} {car['model']} (для примера)"
    return (
        f"🚗 <b>{car['year']} {title}</b>\n"
        f"📍 {car['city']}, WI\n"
        f"💰 ${car['price']:,} | {car['miles']:,} миль\n"
        f"🎨 {car['color']}\n"
        f"🆔 Лот: <b>#{vehicle_id}</b>{rarity_line}{disclaimer}\n"
        f"📝 {car['description']}"
    )


async def send_car(bot, chat_id: int, car: dict, message_thread_id: int | None = None) -> bool:
    if await is_listing_posted(car["guid"]):
        return False

    vehicle_id = await create_vehicle(
        car["make"], car["model"], car["year"], car["price"],
        car["miles"], car["city"], car["vin"], car["license_plate"],
        car["color"], car["rarity"], chat_id,
    )
    caption = format_caption(car, vehicle_id)
    image = await fetch_car_image(car["make"], car["model"])

    try:
        from aiogram.types import BufferedInputFile
        send_args = {"chat_id": chat_id, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id

        if image:
            send_args["photo"] = BufferedInputFile(image, filename="car.jpg")
            await bot.send_photo(**send_args, caption=caption)
        else:
            send_args["text"] = caption
            await bot.send_message(**send_args)

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
        car["color"], car["rarity"], chat_id,
    )
    caption = format_caption(car, vehicle_id)
    image = await fetch_car_image(car["make"], car["model"])
    try:
        from aiogram.types import BufferedInputFile
        send_args = {"chat_id": chat_id, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id

        if image:
            send_args["photo"] = BufferedInputFile(image, filename="car.jpg")
            await bot.send_photo(**send_args, caption=caption)
        else:
            send_args["text"] = caption
            await bot.send_message(**send_args)

        await mark_listing_posted(car["guid"])
        badge = RARITY_NAMES[car["rarity"]]
        title = get_car_title(car["make"], car["model"])
        return f"✅ #{vehicle_id} {car['year']} {title} — {car['city']} {badge}"
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
