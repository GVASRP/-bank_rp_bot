import random

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user,
    get_user_by_telegram_id,
    get_vehicle,
    get_available_vehicles,
    get_vehicle_by_position,
    get_user_vehicles,
    buy_vehicle,
    sell_vehicle,
    list_vehicle_for_sale,
    unlist_vehicle,
    buy_player_vehicle,
    get_player_listed_vehicles,
    create_vehicle,
    update_balance,
    add_transaction,
    seed_houses,
    get_house,
    get_available_houses,
    get_user_houses,
    buy_house,
    sell_house,
    get_all_neighborhoods,
    get_available_houses_by_neighborhood,
    get_neighborhood,
    get_house_type,
    get_all_house_types,
    list_house_for_sale,
    unlist_house,
    buy_player_house,
    get_player_listed_houses,
    create_house_listing,
    list_house_for_rent,
    unlist_house_rent,
    get_for_rent_houses,
    rent_house,
    get_tenant_house,
    evict_tenant,
)
from auto_poster import post_new_car, generate_car, post_new_house, generate_house
from utils import format_amount, parse_amount, get_user_display

router = Router()


@router.message(Command("авто", prefix="!/"))
async def cmd_vehicles(message: Message):
    market = await get_available_vehicles(chat_id=message.chat.id)
    if not market:
        ok = await post_new_car(message.bot, message.chat.id, message.message_thread_id)
        if ok:
            market = await get_available_vehicles(chat_id=message.chat.id)
    player = await get_player_listed_vehicles()
    if not market and not player:
        await message.reply("📭 Нет доступных автомобилей")
        return
    lines = ["🚗 <b>Автомобили:</b>\n"]
    idx = 1
    if market:
        lines.append(f"🏪 <b>Автосалон ({len(market)} шт.):</b>")
        for v in market[:15]:
            lines.append(
                f"#{idx} — {v['year']} {v['make']} {v['model']}\n"
                f"   💰 ${v['price']:,} | {v['miles']:,} миль | 📍 {v['city']}"
            )
            idx += 1
        lines.append("")
    if player:
        lines.append(f"🤝 <b>Б/У от игроков ({len(player)} шт.):</b>")
        for v in player[:10]:
            seller = await get_user_by_telegram_id(v["owner_telegram_id"])
            seller_name = get_user_display(seller) if seller else "Неизвестно"
            lines.append(
                f"#{idx} — {v['year']} {v['make']} {v['model']}\n"
                f"   💰 ${v['price']:,} | Продавец: {seller_name}"
            )
            idx += 1
        lines.append("")
    lines.append("💡 <code>!купить номер</code> — купить авто")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("авто_инфо", prefix="!/"))
async def cmd_vehicle_info(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!авто_инфо номер</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return
    v = await get_vehicle_by_position(message.chat.id, pos) or await get_vehicle(pos)
    if not v:
        await message.reply(f"❌ Автомобиль #{pos} не найден")
        return
    owner = "В продаже"
    if v["owner_telegram_id"]:
        owner_user = await get_user_by_telegram_id(v["owner_telegram_id"])
        owner = f"Владелец: {get_user_display(owner_user)}"
    await message.reply(
        f"🚗 <b>{v['year']} {v['make']} {v['model']}</b>\n"
        f"📍 {v['city']}, WI\n"
        f"💰 ${v['price']:,} | {v['miles']:,} миль\n"
        f"🆔 VIN: {v['vin']}\n"
        f"🔑 Номера: {v['license_plate']}\n"
        f"📌 Статус: {owner}",
        parse_mode="HTML",
    )


@router.message(Command("купить", prefix="!/"))
async def cmd_buy_car(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!купить номер</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    market = await get_available_vehicles(chat_id=message.chat.id)
    if not market:
        ok = await post_new_car(message.bot, message.chat.id, message.message_thread_id)
        if ok:
            market = await get_available_vehicles(chat_id=message.chat.id)
    player = await get_player_listed_vehicles()
    all_vehicles = (market or []) + (player or [])

    v = None
    if 1 <= pos <= len(all_vehicles):
        v = all_vehicles[pos - 1]
    else:
        v = await get_vehicle(pos)
        if v and v.get("status") not in ("available", "player_listed"):
            v = None
    if not v:
        await message.reply(f"❌ Автомобиль #{pos} не найден")
        return

    if not await update_balance(message.from_user.id, -v["price"], message.chat.id):
        user = await get_user_by_telegram_id(message.from_user.id, message.chat.id)
        await message.reply(
            f"❌ Недостаточно средств. Нужно: ${v['price']:,}, баланс: {format_amount(user['balance'] if user else 0)}",
            parse_mode="HTML",
        )
        return

    if v["status"] == "player_listed":
        result = await buy_player_vehicle(v["id"], message.from_user.id)
        if not result:
            await update_balance(message.from_user.id, v["price"], message.chat.id)
            await message.reply(f"❌ Ошибка покупки, деньги возвращены")
            return
        seller_id, price = result
        await update_balance(seller_id, price, message.chat.id)
        await add_transaction("buy_car", message.from_user.id, seller_id, price,
                              f"Покупка у игрока #{v['id']} {v['year']} {v['make']} {v['model']}")
        seller_name = get_user_display(await get_user_by_telegram_id(seller_id))
        await message.reply(
            f"✅ Вы купили у {seller_name} <b>{v['year']} {v['make']} {v['model']}</b>!\n"
            f"💰 Цена: ${price:,}\n"
            f"🔑 Номера: {v['license_plate']}\n"
            f"🆔 VIN: {v['vin']}",
            parse_mode="HTML",
        )
    else:
        if not await buy_vehicle(v["id"], message.from_user.id):
            await update_balance(message.from_user.id, v["price"], message.chat.id)
            await message.reply(f"❌ Ошибка покупки, деньги возвращены")
            return
        await add_transaction("buy_car", message.from_user.id, None, v["price"],
                              f"Покупка из салона #{v['id']} {v['year']} {v['make']} {v['model']}")
        new_bal = await get_user_by_telegram_id(message.from_user.id, message.chat.id)
        await message.reply(
            f"✅ Вы купили <b>{v['year']} {v['make']} {v['model']}</b>!\n"
            f"💰 Цена: ${v['price']:,}\n"
            f"💳 Остаток: {format_amount(new_bal['balance'])} долларов\n"
            f"🔑 Номера: {v['license_plate']}\n"
            f"🆔 VIN: {v['vin']}",
            parse_mode="HTML",
        )


@router.message(Command("мои_авто", prefix="!/"))
async def cmd_my_cars(message: Message):
    vehicles = await get_user_vehicles(message.from_user.id)
    if not vehicles:
        await message.reply("📭 У вас нет автомобилей")
        return
    lines = ["🚗 <b>Ваши автомобили:</b>\n"]
    for idx, v in enumerate(vehicles, 1):
        status_emoji = "✅" if v["status"] == "sold" else "🔄"
        price_info = f" | Цена: ${v['price']:,}" if v["status"] == "player_listed" else ""
        lines.append(
            f"#{idx} {status_emoji} {v['year']} {v['make']} {v['model']}\n"
            f"   🔑 {v['license_plate']} | 📍 {v['city']}{price_info}"
        )
    lines.append("\n💡 <code>!продать НОМЕР цена</code> — выставить на продажу игрокам")
    lines.append("💡 <code>!снять_продажу НОМЕР</code> — убрать из продажи")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("продать_авто", prefix="!/"))
async def cmd_sell_car(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!продать_авто номер</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    v = await get_vehicle_by_position(message.chat.id, pos) or await get_vehicle(pos)
    if not v:
        await message.reply(f"❌ Автомобиль #{pos} не найден")
        return
    if v["owner_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш автомобиль")
        return

    price = v["price"] // 2
    if not await sell_vehicle(v["id"], message.from_user.id):
        await message.reply("❌ Ошибка продажи")
        return

    await update_balance(message.from_user.id, price, message.chat.id)
    new_bal = await get_user_by_telegram_id(message.from_user.id, message.chat.id)
    await add_transaction("sell_car", None, message.from_user.id, price,
                          f"Продажа авто #{v['id']} {v['year']} {v['make']} {v['model']}")

    await message.reply(
        f"✅ Автомобиль #{v['id']} {v['year']} {v['make']} {v['model']} продан!\n"
        f"💰 Выручка: {format_amount(price)} долларов (50%)\n"
        f"💳 Баланс: {format_amount(new_bal['balance'])} долларов",
        parse_mode="HTML",
    )


@router.message(Command("продать", prefix="!/"))
async def cmd_list_car(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!продать НОМЕР цена</code>\nПример: <code>!продать 5 25000</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
        price = int(args[2])
    except ValueError:
        await message.reply("❌ Номер и цена должны быть числами")
        return
    if price <= 0:
        await message.reply("❌ Цена должна быть больше 0")
        return

    user_vehicles = await get_user_vehicles(message.from_user.id)
    if pos < 1 or pos > len(user_vehicles):
        await message.reply(f"❌ Авто #{pos} не найдено")
        return
    v = user_vehicles[pos - 1]
    vid = v["id"]
    if v["owner_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш автомобиль")
        return
    if v["status"] != "sold":
        await message.reply("❌ Это авто уже выставлено на продажу или ещё не куплено")
        return

    if not await list_vehicle_for_sale(vid, message.from_user.id, price):
        await message.reply("❌ Ошибка выставления на продажу")
        return

    # Calculate position in combined listing for buyer reference
    market = await get_available_vehicles(chat_id=message.chat.id)
    player = await get_player_listed_vehicles()
    all_v = (market or []) + (player or [])
    buy_pos = next((i for i, av in enumerate(all_v, 1) if av["id"] == vid), vid)

    await message.reply(
        f"✅ {v['year']} {v['make']} {v['model']} выставлен на продажу за ${price:,}!\n"
        f"💡 Другие игроки могут купить его через <code>!купить {buy_pos}</code>",
        parse_mode="HTML",
    )


@router.message(Command("снять_продажу", prefix="!/"))
async def cmd_unlist_car(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!снять_продажу НОМЕР</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    user_vehicles = await get_user_vehicles(message.from_user.id)
    if pos < 1 or pos > len(user_vehicles):
        await message.reply(f"❌ Авто #{pos} не найдено")
        return
    v = user_vehicles[pos - 1]
    vid = v["id"]
    if v["status"] != "player_listed":
        await message.reply("❌ Это авто не выставлено на продажу")
        return

    if not await unlist_vehicle(vid, message.from_user.id):
        await message.reply("❌ Ошибка снятия с продажи")
        return

    await message.reply(f"✅ {v['year']} {v['make']} {v['model']} снят с продажи", parse_mode="HTML")


CONTAINER_PRICE = 25_000


@router.message(Command("контейнер", prefix="!/"))
async def cmd_container(message: Message):
    if not await update_balance(message.from_user.id, -CONTAINER_PRICE, message.chat.id):
        user = await get_user_by_telegram_id(message.from_user.id, message.chat.id)
        await message.reply(
            f"❌ Недостаточно средств. Нужно: ${CONTAINER_PRICE:,}, баланс: {format_amount(user['balance'] if user else 0)}",
            parse_mode="HTML",
        )
        return

    for _ in range(100):
        car = generate_car()
        if car["rarity"] == "legendary" and random.random() < 0.92:
            continue
        if car["rarity"] == "rare" and random.random() < 0.60:
            continue
        break
    vehicle_id = await create_vehicle(
        car["make"], car["model"], car["year"], car["price"],
        car["miles"], car["city"], car["vin"], car["license_plate"],
        car["color"], car["rarity"], message.chat.id,
    )
    await buy_vehicle(vehicle_id, message.from_user.id)
    await add_transaction("container", message.from_user.id, None, CONTAINER_PRICE,
                          f"Контейнер: {car['year']} {car['make']} {car['model']}")

    await message.reply(
        f"🎁 <b>Вы открыли контейнер!</b>\n\n"
        f"🚗 {car['year']} {car['make']} {car['model']}\n"
        f"💰 Стоимость: ${car['price']:,} | 📍 {car['city']}\n"
        f"🔑 Номера: {car['license_plate']} | 🆔 VIN: {car['vin']}\n"
        f"📝 {car['description']}",
        parse_mode="HTML",
    )


NEIGHBORHOOD_EMOJIS = {
    "Six Housen't": "🏘", "Lakeville": "🏞", "Greenhills": "🌿",
    "Horton": "🏰", "Farm Area": "🌾", "Greenville Lake": "🏖",
    "Fleetwood Lane": "🌳",
}

CONTAINER_HOUSE_PRICE = 50_000


async def get_house_display(h: dict) -> str:
    nb = h.get("neighborhood", "")
    emoji = NEIGHBORHOOD_EMOJIS.get(nb, "🏠")
    return (
        f"#{h.get('_pos', h['id'])} — {h['type_name']}\n"
        f"   {emoji} <b>{nb}</b> | 💰 ${h['price']:,} | 🛏 {h['bedrooms']} | 🛁 {h['bathrooms']} | 📐 {h['sqft']:,} кв.футов"
    )


@router.message(Command("дома", prefix="!/"))
async def cmd_houses(message: Message):
    await seed_houses(message.chat.id)
    text = message.text.strip()
    args = text.split(maxsplit=1)
    neighborhood_filter = args[1] if len(args) > 1 else None

    if neighborhood_filter:
        nbs = await get_all_neighborhoods()
        match = None
        for nb in nbs:
            if nb["name"].lower() == neighborhood_filter.lower():
                match = nb
                break
        if not match:
            nb_list = ", ".join(nb["name"] for nb in nbs)
            await message.reply(f"❌ Район не найден. Доступны: {nb_list}", parse_mode="HTML")
            return
        houses = await get_available_houses_by_neighborhood(message.chat.id, match["id"])
        title = f"🏠 <b>Дома в районе {match['name']}:</b>\n"
    else:
        houses = await get_available_houses(message.chat.id)
        title = "🏠 <b>Дома в продаже:</b>\n"

    # Also add player-listed houses
    player_houses = await get_player_listed_houses()
    player_houses = [h for h in player_houses if h["chat_id"] == message.chat.id]
    if not houses and not player_houses:
        ok = await post_new_house(message.bot, message.chat.id, message.message_thread_id)
        if ok:
            houses = await get_available_houses(message.chat.id)

    if not houses and not player_houses:
        await message.reply("📭 Нет доступных домов")
        return

    lines = [title]
    idx = 1
    if houses:
        lines.append(f"🏪 <b>Рынок ({len(houses)} шт.):</b>")
        for h in houses:
            h["_pos"] = idx
            lines.append(await get_house_display(h))
            idx += 1
        lines.append("")
    if player_houses:
        lines.append(f"🤝 <b>Б/У от игроков ({len(player_houses)} шт.):</b>")
        for h in player_houses:
            h["_pos"] = idx
            seller = await get_user_by_telegram_id(h["owner_telegram_id"])
            seller_name = get_user_display(seller) if seller else "Неизвестно"
            lines.append(
                f"#{idx} — {h['type_name']}\n"
                f"   💰 ${h['price']:,} | Продавец: {seller_name}"
            )
            idx += 1
        lines.append("")
    lines.append("💡 <code>!дом НОМЕР</code> — инфо | <code>!купить_дом НОМЕР</code>")
    lines.append("💡 <code>!дома [район]</code> — фильтр по району")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("районы", prefix="!/"))
async def cmd_neighborhoods(message: Message):
    nbs = await get_all_neighborhoods()
    if not nbs:
        await message.reply("📭 Нет доступных районов")
        return
    lines = ["🗺 <b>Районы Greenville:</b>\n"]
    for nb in nbs:
        emoji = NEIGHBORHOOD_EMOJIS.get(nb["name"], "🏠")
        lines.append(f"{emoji} <b>{nb['name']}</b>")
    lines.append("\n💡 <code>!дома [район]</code> — показать дома в районе")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("дом", prefix="!/"))
async def cmd_house_info(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!дом НОМЕР</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    # Find house by position in combined listing
    market = await get_available_houses(message.chat.id)
    player = await get_player_listed_houses()
    player = [h for h in player if h["chat_id"] == message.chat.id]
    all_h = (market or []) + (player or [])
    if 1 <= pos <= len(all_h):
        h = all_h[pos - 1]
    else:
        h = await get_house(pos)
    if not h:
        await message.reply(f"❌ Дом #{pos} не найден")
        return
    owner = "В продаже"
    if h["owner_telegram_id"]:
        owner_user = await get_user_by_telegram_id(h["owner_telegram_id"])
        owner = f"Владелец: {get_user_display(owner_user)}"
    nb = h.get("neighborhood", "")
    emoji = NEIGHBORHOOD_EMOJIS.get(nb, "🏠")
    await message.reply(
        f"🏠 <b>{h['type_name']}</b>\n"
        f"{emoji} <b>{nb}</b>\n"
        f"💰 ${h['price']:,}\n"
        f"🛏 {h['bedrooms']} спальни | 🛁 {h['bathrooms']} ванны | 📐 {h['sqft']:,} кв.футов\n"
        f"📝 {h['description'] or ''}\n"
        f"📌 Статус: {owner}",
        parse_mode="HTML",
    )


@router.message(Command("купить_дом", prefix="!/"))
async def cmd_buy_house(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!купить_дом НОМЕР</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    # Find by position in combined listing
    market = await get_available_houses(message.chat.id)
    player = await get_player_listed_houses()
    player = [h for h in player if h["chat_id"] == message.chat.id]
    all_h = (market or []) + (player or [])
    h = None
    if 1 <= pos <= len(all_h):
        h = all_h[pos - 1]
    else:
        h = await get_house(pos)
        if h and h.get("status") not in ("available", "player_listed"):
            h = None
    if not h:
        await message.reply(f"❌ Дом #{pos} не найден")
        return

    if not await update_balance(message.from_user.id, -h["price"], message.chat.id):
        user_bal = await get_user_by_telegram_id(message.from_user.id, message.chat.id)
        await message.reply(
            f"❌ Недостаточно средств. Нужно: ${h['price']:,}, баланс: {format_amount(user_bal['balance'] if user_bal else 0)}",
            parse_mode="HTML",
        )
        return

    hid = h["id"]
    if h["status"] == "player_listed":
        result = await buy_player_house(hid, message.from_user.id)
        if not result:
            await update_balance(message.from_user.id, h["price"], message.chat.id)
            await message.reply(f"❌ Ошибка покупки, деньги возвращены")
            return
        seller_id, price = result
        await update_balance(seller_id, price, message.chat.id)
        await add_transaction("buy_house", message.from_user.id, seller_id, price,
                              f"Покупка дома у игрока #{hid} {h['type_name']}")
        seller_name = get_user_display(await get_user_by_telegram_id(seller_id))
        await message.reply(
            f"✅ Вы купили у {seller_name} <b>{h['type_name']}</b>!\n"
            f"💰 Цена: ${price:,}",
            parse_mode="HTML",
        )
    else:
        if not await buy_house(hid, message.from_user.id):
            await update_balance(message.from_user.id, h["price"], message.chat.id)
            await message.reply(f"❌ Ошибка покупки, деньги возвращены")
            return
        await add_transaction("buy_house", message.from_user.id, None, h["price"],
                              f"Покупка дома #{hid} {h['type_name']}")
        await message.reply(
            f"✅ Вы купили <b>{h['type_name']}</b>!\n"
            f"📍 <b>{h['neighborhood']}</b>\n"
            f"💰 Цена: ${h['price']:,}",
            parse_mode="HTML",
        )


@router.message(Command("мои_дома", prefix="!/"))
async def cmd_my_houses(message: Message):
    houses = await get_user_houses(message.from_user.id, message.chat.id)
    if not houses:
        await message.reply("📭 У вас нет домов")
        return
    lines = ["🏠 <b>Ваши дома:</b>\n"]
    for idx, h in enumerate(houses, 1):
        status_emoji = "✅" if h["status"] == "sold" else "🔄"
        price_info = f" | Цена: ${h['price']:,}" if h["status"] == "player_listed" else ""
        nb = h.get("neighborhood", "")
        emoji = NEIGHBORHOOD_EMOJIS.get(nb, "🏠")
        lines.append(
            f"#{idx} {status_emoji} {h['type_name']}\n"
            f"   {emoji} <b>{nb}</b>{price_info}"
        )
    lines.append("\n💡 <code>!продать_дом НОМЕР</code> — вернуть на рынок (50% стоимости)")
    lines.append("💡 <code>!продать_дом НОМЕР цена</code> — выставить игрокам")
    lines.append("💡 <code>!снять_продажу_дома НОМЕР</code> — убрать из продажи")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("продать_дом", prefix="!/"))
async def cmd_sell_house(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!продать_дом НОМЕР [цена]</code>\n"
                           "Без цены — продажа на рынок за 50%\n"
                           "С ценой — выставление игрокам", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    houses = await get_user_houses(message.from_user.id, message.chat.id)
    if pos < 1 or pos > len(houses):
        await message.reply(f"❌ Дом #{pos} не найден")
        return
    h = houses[pos - 1]
    hid = h["id"]

    if len(args) >= 3:
        # Player-to-player listing
        price = int(args[2])
        if price <= 0:
            await message.reply("❌ Цена должна быть больше 0")
            return
        if h["status"] != "sold":
            await message.reply("❌ Этот дом уже выставлен на продажу или не куплен")
            return
        if not await list_house_for_sale(hid, message.from_user.id, price):
            await message.reply("❌ Ошибка выставления на продажу")
            return
        await message.reply(
            f"✅ {h['type_name']} выставлен на продажу за ${price:,}!\n"
            f"💡 Другие могут купить через <code>!купить_дом {hid}</code>",
            parse_mode="HTML",
        )
    else:
        # Sell back to market
        if h["owner_telegram_id"] != message.from_user.id:
            await message.reply("❌ Это не ваш дом")
            return
        if h["status"] == "player_listed":
            await unlist_house(hid, message.from_user.id)
        price = h["price"] // 2
        if not await sell_house(hid, message.from_user.id):
            await message.reply("❌ Ошибка продажи")
            return
        await update_balance(message.from_user.id, price, message.chat.id)
        await add_transaction("sell_house", None, message.from_user.id, price,
                              f"Продажа дома #{hid} {h['type_name']}")
        await message.reply(
            f"✅ {h['type_name']} продан!\n"
            f"💰 Выручка: {format_amount(price)} долларов (50% стоимости)",
            parse_mode="HTML",
        )


@router.message(Command("снять_продажу_дома", prefix="!/"))
async def cmd_unlist_house(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!снять_продажу_дома НОМЕР</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    houses = await get_user_houses(message.from_user.id, message.chat.id)
    if pos < 1 or pos > len(houses):
        await message.reply(f"❌ Дом #{pos} не найден")
        return
    h = houses[pos - 1]
    if h["status"] != "player_listed":
        await message.reply("❌ Этот дом не выставлен на продажу")
        return
    if not await unlist_house(h["id"], message.from_user.id):
        await message.reply("❌ Ошибка снятия с продажи")
        return
    await message.reply(f"✅ {h['type_name']} снят с продажи", parse_mode="HTML")


HOUSE_CONTAINER_PRICE = 50_000


@router.message(Command("контейнер_дом", prefix="!/"))
async def cmd_house_container(message: Message):
    text = message.text.strip()
    args = text.split(maxsplit=1)
    target_nb = args[1] if len(args) > 1 else None

    if not await update_balance(message.from_user.id, -HOUSE_CONTAINER_PRICE, message.chat.id):
        user = await get_user_by_telegram_id(message.from_user.id, message.chat.id)
        await message.reply(
            f"❌ Недостаточно средств. Нужно: ${HOUSE_CONTAINER_PRICE:,}, баланс: {format_amount(user['balance'] if user else 0)}",
            parse_mode="HTML",
        )
        return

    # Generate house (possibly filtered by neighborhood)
    nbs = await get_all_neighborhoods()
    for _ in range(200):
        house = generate_house()
        if target_nb:
            match = None
            for nb in nbs:
                if nb["name"].lower() == target_nb.lower():
                    match = nb
                    break
            if not match or house["neighborhood_id"] != match["id"]:
                continue
        # Reject low-value houses (avoid giving $40k house for $50k container)
        if house["price"] < HOUSE_CONTAINER_PRICE * 1.5:
            continue
        break

    house_id = await create_house_listing(
        message.chat.id, house["house_type_id"], house["neighborhood_id"],
        house["price"], house["guid"],
    )
    await buy_house(house_id, message.from_user.id)
    await add_transaction("container_house", message.from_user.id, None, HOUSE_CONTAINER_PRICE,
                          f"Контейнер дом: {house['type_name']}")

    nb = house["neighborhood"]
    emoji = NEIGHBORHOOD_EMOJIS.get(nb, "🏠")
    await message.reply(
        f"🎁 <b>Вы открыли контейнер с домом!</b>\n\n"
        f"🏠 {house['type_name']}\n"
        f"{emoji} <b>{nb}</b>\n"
        f"💰 Рыночная стоимость: ${house['price']:,}\n"
        f"🛏 {house['bedrooms']} спальни | 🛁 {house['bathrooms']} ванны | 📐 {house['sqft']:,} кв.футов",
        parse_mode="HTML",
    )


# ─── Rental system ─────────────────────────────────────────────


@router.message(Command("сдать_дом", prefix="!/"))
async def cmd_rent_out_house(message: Message):
    args = message.text.strip().split()
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!сдать_дом НОМЕР цена_в_день</code>", parse_mode="HTML")
        return
    try:
        position = int(args[1])
        rent_price = int(args[2])
    except ValueError:
        await message.reply("❌ Номер дома и цена должны быть числами")
        return
    if rent_price < 100:
        await message.reply("❌ Минимальная цена аренды: $100/день")
        return
    houses = await get_user_houses(message.from_user.id, message.chat.id)
    if position < 1 or position > len(houses):
        await message.reply(f"❌ У вас нет дома с номером {position}")
        return
    h = houses[position - 1]
    if h["status"] != "sold":
        await message.reply("❌ Этот дом уже выставлен на продажу")
        return
    ok = await list_house_for_rent(h["id"], message.from_user.id, rent_price)
    if not ok:
        await message.reply("❌ Не удалось сдать дом. Возможно, он уже сдан или продан")
        return
    await message.reply(
        f"✅ <b>{h['type_name']}</b> сдан в аренду за ${rent_price:,}/день\n"
        f"👥 Игроки могут заселиться через <code>!арендовать {position}</code>",
        parse_mode="HTML",
    )


@router.message(Command("снять_с_аренды", prefix="!/"))
async def cmd_unlist_rent(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!снять_с_аренды НОМЕР</code>", parse_mode="HTML")
        return
    try:
        position = int(args[1])
    except ValueError:
        await message.reply("❌ Номер дома должен быть числом")
        return
    houses = await get_user_houses(message.from_user.id, message.chat.id)
    if position < 1 or position > len(houses):
        await message.reply(f"❌ У вас нет дома с номером {position}")
        return
    h = houses[position - 1]
    ok = await unlist_house_rent(h["id"], message.from_user.id)
    if not ok:
        await message.reply("❌ Дом не сдан в аренду или в нём живут")
        return
    await message.reply(f"✅ <b>{h['type_name']}</b> снят с аренды")


@router.message(Command("арендовать", prefix="!/"))
async def cmd_rent_house(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!арендовать НОМЕР</code>", parse_mode="HTML")
        return
    try:
        position = int(args[1])
    except ValueError:
        await message.reply("❌ Номер дома должен быть числом")
        return
    existing = await get_tenant_house(message.from_user.id, message.chat.id)
    if existing:
        await message.reply(
            f"❌ Вы уже арендуете <b>{existing['type_name']}</b>. Сначала съедьте: <code>!съехать</code>",
            parse_mode="HTML",
        )
        return
    rentals = await get_for_rent_houses(message.chat.id)
    # Include owned houses listed for rent too
    owned_rentals = [h for h in await get_user_houses(message.from_user.id, message.chat.id) if h.get("rent_price", 0) > 0 and h["status"] == "sold" and not h.get("tenant_telegram_id")]
    all_rentals = rentals + owned_rentals
    # Get user's own houses that are for rent to exclude from rentable list
    my_ids = {h["id"] for h in await get_user_houses(message.from_user.id, message.chat.id)}
    rentable = [h for h in all_rentals if h["id"] not in my_ids]
    if position < 1 or position > len(rentable):
        await message.reply(f"❌ Нет дома с номером {position} в списке аренды")
        return
    h = rentable[position - 1]
    ok, msg = await rent_house(h["id"], message.from_user.id)
    if ok:
        nb = h.get("neighborhood", "")
        emoji = NEIGHBORHOOD_EMOJIS.get(nb, "🏠")
        await message.reply(
            f"✅ <b>Вы арендовали дом!</b>\n\n"
            f"🏠 {h['type_name']}\n"
            f"{emoji} <b>{nb}</b>\n"
            f"💰 ${h['rent_price']:,}/день\n"
            f"🛏 {h['bedrooms']} спальни | 🛁 {h['bathrooms']} ванны\n\n"
            f"💡 Плата списывается ежедневно. Проверить: <code>!моя_аренда</code>\n"
            f"🚪 Съехать: <code>!съехать</code>",
            parse_mode="HTML",
        )
    else:
        await message.reply(f"❌ {msg}", parse_mode="HTML")


@router.message(Command("моя_аренда", prefix="!/"))
async def cmd_my_rent(message: Message):
    h = await get_tenant_house(message.from_user.id, message.chat.id)
    if not h:
        await message.reply("❌ Вы не арендуете дом")
        return
    nb = h.get("neighborhood", "")
    emoji = NEIGHBORHOOD_EMOJIS.get(nb, "🏠")
    from datetime import datetime
    paid = h.get("rent_paid_at", "—")
    missed = h.get("rent_missed_days", 0)
    status = "✅ Оплачено"
    if missed and missed > 0:
        status = f"⚠️ Просрочка {missed}/3 дней"
        if missed >= 3:
            status = "❌ Будет выселен"
    await message.reply(
        f"🏠 <b>Ваша аренда</b>\n\n"
        f"🏠 {h['type_name']}\n"
        f"{emoji} <b>{nb}</b>\n"
        f"💰 ${h['rent_price']:,}/день\n"
        f"📅 Последняя оплата: {paid}\n"
        f"📊 Статус: {status}\n\n"
        f"🚪 Съехать: <code>!съехать</code>",
        parse_mode="HTML",
    )


@router.message(Command("съехать", prefix="!/"))
async def cmd_move_out(message: Message):
    h = await get_tenant_house(message.from_user.id, message.chat.id)
    if not h:
        await message.reply("❌ Вы не арендуете дом")
        return
    ok = await evict_tenant(h["id"])
    if not ok:
        await message.reply("❌ Не удалось выселиться")
        return
    await message.reply(f"🚪 Вы съехали из <b>{h['type_name']}</b>", parse_mode="HTML")


@router.message(Command("аренда_дома", prefix="!/"))
async def cmd_rental_houses(message: Message):
    args = message.text.strip().split(maxsplit=1)
    target_nb = args[1] if len(args) > 1 else None
    rentals = await get_for_rent_houses(message.chat.id)
    # Also show own houses that are for rent (but not self-occupied)
    my_ids = {h["id"] for h in await get_user_houses(message.from_user.id, message.chat.id)}
    if target_nb:
        rentals = [h for h in rentals if h["neighborhood"].lower() == target_nb.lower()]
    if not rentals:
        await message.reply("📭 Нет домов в аренду" + (f" в районе {target_nb}" if target_nb else ""))
        return
    lines = ["🏠 <b>Дома в аренду:</b>\n"]
    for idx, h in enumerate(rentals, 1):
        if h["id"] in my_ids:
            continue
        nb = h.get("neighborhood", "")
        emoji = NEIGHBORHOOD_EMOJIS.get(nb, "🏠")
        lines.append(
            f"{idx}. {emoji} <b>{h['type_name']}</b>\n"
            f"   💰 ${h['rent_price']:,}/день | 🛏 {h['bedrooms']} | 🛁 {h['bathrooms']}\n"
        )
    if len(lines) == 1:
        await message.reply("📭 Нет доступных домов в аренду" + (f" в районе {target_nb}" if target_nb else ""))
        return
    await message.reply("\n".join(lines), parse_mode="HTML")
