from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user,
    get_vehicle,
    get_available_vehicles,
    get_user_vehicles,
    buy_vehicle,
    sell_vehicle,
    get_house,
    get_available_houses,
    get_user_houses,
    buy_house,
    sell_house,
    update_balance,
    add_transaction,
)
from utils import format_amount, parse_amount

router = Router()


@router.message(Command("авто", prefix="!/"))
async def cmd_vehicles(message: Message):
    vehicles = await get_available_vehicles()
    if not vehicles:
        await message.reply("📭 Нет доступных автомобилей")
        return
    lines = ["🚗 <b>Автомобили в продаже:</b>\n"]
    for v in vehicles:
        lines.append(
            f"#{v['id']} — {v['year']} {v['make']} {v['model']}\n"
            f"   💰 ${v['price']:,} | {v['miles']:,} миль | 📍 {v['city']}"
        )
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("авто_инфо", prefix="!/"))
async def cmd_vehicle_info(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!авто_инфо ID</code>", parse_mode="HTML")
        return
    try:
        vid = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    v = await get_vehicle(vid)
    if not v:
        await message.reply(f"❌ Автомобиль #{vid} не найден")
        return
    owner = "В продаже" if not v["owner_telegram_id"] else f"Владелец ID {v['owner_telegram_id']}"
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
        await message.reply("❌ Использование: <code>!купить ID_авто</code>", parse_mode="HTML")
        return
    try:
        vid = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return

    v = await get_vehicle(vid)
    if not v:
        await message.reply(f"❌ Автомобиль #{vid} не найден")
        return
    if v["status"] != "available":
        await message.reply(f"❌ Автомобиль #{vid} уже продан")
        return

    user = await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    if user["balance"] < v["price"]:
        await message.reply(
            f"❌ Недостаточно средств. Нужно: ${v['price']:,}, баланс: {format_amount(user['balance'])}",
            parse_mode="HTML",
        )
        return

    if not await buy_vehicle(vid, message.from_user.id):
        await message.reply(f"❌ Ошибка покупки")
        return

    await update_balance(message.from_user.id, -v["price"])
    await add_transaction("buy_car", message.from_user.id, None, v["price"],
                          f"Покупка авто #{vid} {v['year']} {v['make']} {v['model']}")

    await message.reply(
        f"✅ Вы купили <b>{v['year']} {v['make']} {v['model']}</b>!\n"
        f"💰 Цена: ${v['price']:,}\n"
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
        lines.append(
            f"#{v['id']} — {v['year']} {v['make']} {v['model']}\n"
            f"   🔑 {v['license_plate']} | 📍 {v['city']}"
        )
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("продать_авто", prefix="!/"))
async def cmd_sell_car(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!продать_авто ID</code>", parse_mode="HTML")
        return
    try:
        vid = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return

    v = await get_vehicle(vid)
    if not v:
        await message.reply(f"❌ Автомобиль #{vid} не найден")
        return
    if v["owner_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш автомобиль")
        return

    price = v["price"] // 2
    if not await sell_vehicle(vid, message.from_user.id):
        await message.reply("❌ Ошибка продажи")
        return

    await update_balance(message.from_user.id, price)
    await add_transaction("sell_car", None, message.from_user.id, price,
                          f"Продажа авто #{vid} {v['year']} {v['make']} {v['model']}")

    await message.reply(
        f"✅ Автомобиль #{vid} {v['year']} {v['make']} {v['model']} продан!\n"
        f"💰 Выручка: {format_amount(price)} долларов (50% стоимости)",
        parse_mode="HTML",
    )


@router.message(Command("дома", prefix="!/"))
async def cmd_houses(message: Message):
    houses = await get_available_houses()
    if not houses:
        await message.reply("📭 Нет доступных домов")
        return
    lines = ["🏠 <b>Дома в продаже:</b>\n"]
    for h in houses:
        lines.append(
            f"#{h['id']} — {h['type_name']}\n"
            f"   📍 {h['location']} | 💰 ${h['price']:,}\n"
            f"   🛏 {h['bedrooms']} | 🛁 {h['bathrooms']} | 📐 {h['sqft']} кв.футов"
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
    owner = "В продаже" if not h["owner_telegram_id"] else f"Владелец ID {h['owner_telegram_id']}"
    await message.reply(
        f"🏠 <b>{h['type_name']}</b>\n"
        f"📍 {h['location']}\n"
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

    user = await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    if user["balance"] < h["price"]:
        await message.reply(
            f"❌ Недостаточно средств. Нужно: ${h['price']:,}, баланс: {format_amount(user['balance'])}",
            parse_mode="HTML",
        )
        return

    if not await buy_house(hid, message.from_user.id):
        await message.reply(f"❌ Ошибка покупки")
        return

    await update_balance(message.from_user.id, -h["price"])
    await add_transaction("buy_house", message.from_user.id, None, h["price"],
                          f"Покупка дома #{hid} {h['type_name']}")

    await message.reply(
        f"✅ Вы купили <b>{h['type_name']}</b>!\n"
        f"📍 {h['location']}\n"
        f"💰 Цена: ${h['price']:,}",
        parse_mode="HTML",
    )


@router.message(Command("мои_дома", prefix="!/"))
async def cmd_my_houses(message: Message):
    houses = await get_user_houses(message.from_user.id)
    if not houses:
        await message.reply("📭 У вас нет домов")
        return
    lines = ["🏠 <b>Ваши дома:</b>\n"]
    for h in houses:
        lines.append(
            f"#{h['id']} — {h['type_name']}\n"
            f"   📍 {h['location']} | 🛏 {h['bedrooms']}"
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

    await update_balance(message.from_user.id, price)
    await add_transaction("sell_house", None, message.from_user.id, price,
                          f"Продажа дома #{hid} {h['type_name']}")

    await message.reply(
        f"✅ Дом #{hid} {h['type_name']} продан!\n"
        f"💰 Выручка: {format_amount(price)} долларов (50% стоимости)",
        parse_mode="HTML",
    )
