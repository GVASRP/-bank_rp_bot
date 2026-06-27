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
    seed_houses,
    get_house,
    get_available_houses,
    get_user_houses,
    buy_house,
    sell_house,
    update_balance,
    add_transaction,
)
from auto_poster import post_new_car
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
    for v in vehicles:
        status_emoji = "✅" if v["status"] == "sold" else "🔄"
        price_info = f" | Цена: ${v['price']:,}" if v["status"] == "player_listed" else ""
        lines.append(
            f"#{v['id']} {status_emoji} {v['year']} {v['make']} {v['model']}\n"
            f"   🔑 {v['license_plate']} | 📍 {v['city']}{price_info}"
        )
    lines.append("\n💡 <code>!продать ID цена</code> — выставить на продажу игрокам")
    lines.append("💡 <code>!снять_продажу ID</code> — убрать из продажи")
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
        await message.reply("❌ Использование: <code>!продать ID_авто цена</code>\nПример: <code>!продать 5 25000</code>", parse_mode="HTML")
        return
    try:
        vid = int(args[1])
        price = int(args[2])
    except ValueError:
        await message.reply("❌ ID и цена должны быть числами")
        return
    if price <= 0:
        await message.reply("❌ Цена должна быть больше 0")
        return

    v = await get_vehicle(vid)
    if not v:
        await message.reply(f"❌ Авто #{vid} не найдено")
        return
    if v["owner_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш автомобиль")
        return
    if v["status"] != "sold":
        await message.reply("❌ Это авто уже выставлено на продажу или ещё не куплено")
        return

    if not await list_vehicle_for_sale(vid, message.from_user.id, price):
        await message.reply("❌ Ошибка выставления на продажу")
        return

    await message.reply(
        f"✅ {v['year']} {v['make']} {v['model']} выставлен на продажу за ${price:,}!\n"
        f"💡 Другие игроки могут купить его через <code>!купить НОМЕР</code>",
        parse_mode="HTML",
    )


@router.message(Command("снять_продажу", prefix="!/"))
async def cmd_unlist_car(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!снять_продажу ID_авто</code>", parse_mode="HTML")
        return
    try:
        vid = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return

    v = await get_vehicle(vid)
    if not v:
        await message.reply(f"❌ Авто #{vid} не найдено")
        return
    if v["owner_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш автомобиль")
        return
    if v["status"] != "player_listed":
        await message.reply("❌ Это авто не выставлено на продажу")
        return

    if not await unlist_vehicle(vid, message.from_user.id):
        await message.reply("❌ Ошибка снятия с продажи")
        return

    await message.reply(f"✅ {v['year']} {v['make']} {v['model']} снят с продажи", parse_mode="HTML")


@router.message(Command("дома", prefix="!/"))
async def cmd_houses(message: Message):
    await seed_houses(message.chat.id)
    houses = await get_available_houses(message.chat.id)
    if not houses:
        await message.reply("📭 Нет доступных домов")
        return
    lines = ["🏠 <b>Дома в продаже:</b>\n"]
    for h in houses:
        lines.append(
            f"#{h['id']} — {h['type_name']}\n"
            f"   📍 <b>{h['neighborhood']}</b> — {h['location']}\n"
            f"   💰 ${h['price']:,} | 🛏 {h['bedrooms']} | 🛁 {h['bathrooms']} | 📐 {h['sqft']} кв.футов"
        )
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("дом", prefix="!/"))
async def cmd_house_info(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!дом ID</code>", parse_mode="HTML")
        return
    try:
        hid = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    h = await get_house(hid)
    if not h:
        await message.reply(f"❌ Дом #{hid} не найден")
        return
    owner = "В продаже"
    if h["owner_telegram_id"]:
        owner_user = await get_user_by_telegram_id(h["owner_telegram_id"])
        owner = f"Владелец: {get_user_display(owner_user)}"
    await message.reply(
        f"🏠 <b>{h['type_name']}</b>\n"
        f"📍 <b>{h['neighborhood']}</b> — {h['location']}\n"
        f"💰 ${h['price']:,}\n"
        f"🛏 {h['bedrooms']} спальни | 🛁 {h['bathrooms']} ванны | 📐 {h['sqft']} кв.футов\n"
        f"📝 {h['description'] or ''}\n"
        f"📌 Статус: {owner}",
        parse_mode="HTML",
    )


@router.message(Command("купить_дом", prefix="!/"))
async def cmd_buy_house(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!купить_дом ID</code>", parse_mode="HTML")
        return
    try:
        hid = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return

    h = await get_house(hid)
    if not h:
        await message.reply(f"❌ Дом #{hid} не найден")
        return
    if h["status"] != "available":
        await message.reply(f"❌ Дом #{hid} уже продан")
        return

    if not await update_balance(message.from_user.id, -h["price"], message.chat.id):
        await message.reply(
            f"❌ Недостаточно средств. Нужно: ${h['price']:,}",
            parse_mode="HTML",
        )
        return

    if not await buy_house(hid, message.from_user.id):
        await update_balance(message.from_user.id, h["price"], message.chat.id)
        await message.reply(f"❌ Ошибка покупки дома, деньги возвращены")
        return

    await add_transaction("buy_house", message.from_user.id, None, h["price"],
                          f"Покупка дома #{hid} {h['type_name']}")

    await message.reply(
        f"✅ Вы купили <b>{h['type_name']}</b>!\n"
        f"📍 <b>{h['neighborhood']}</b> — {h['location']}\n"
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
    for h in houses:
        lines.append(
            f"#{h['id']} — {h['type_name']}\n"
            f"   📍 <b>{h['neighborhood']}</b> — {h['location']} | 🛏 {h['bedrooms']}"
        )
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("продать_дом", prefix="!/"))
async def cmd_sell_house(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!продать_дом ID</code>", parse_mode="HTML")
        return
    try:
        hid = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return

    h = await get_house(hid)
    if not h:
        await message.reply(f"❌ Дом #{hid} не найден")
        return
    if h["owner_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш дом")
        return

    price = h["price"] // 2
    if not await sell_house(hid, message.from_user.id):
        await message.reply("❌ Ошибка продажи")
        return

    await update_balance(message.from_user.id, price, message.chat.id)
    await add_transaction("sell_house", None, message.from_user.id, price,
                          f"Продажа дома #{hid} {h['type_name']}")

    await message.reply(
        f"✅ Дом #{hid} {h['type_name']} продан!\n"
        f"💰 Выручка: {format_amount(price)} долларов (50% стоимости)",
        parse_mode="HTML",
    )
