from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user,
    get_available_trailers,
    get_user_trailers,
    get_trailer_by_position,
    get_player_listed_trailers,
    buy_trailer,
    sell_trailer,
    list_trailer_for_sale,
    unlist_trailer,
    buy_player_trailer,
    create_trailer,
    update_balance,
    add_transaction,
    get_vehicle,
)
from auto_poster import generate_trailer, format_trailer_caption
from utils import format_amount, parse_amount, resolve_target

router = Router()

SELL_REFUND_PCT = 60


def build_trailer_list(market: list, player: list) -> list:
    combined = []
    seen = set()
    for v in market:
        combined.append(v)
        seen.add(v["id"])
    for v in player:
        if v["id"] not in seen:
            combined.append(v)
            seen.add(v["id"])
    return combined


@router.message(Command("прицепы", prefix="!/"))
async def cmd_trailers(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    market = await get_available_trailers(chat_id=message.chat.id)
    if not market:
        await message.reply("🏪 На Truck Planet сейчас нет прицепов в продаже. Загляните позже!")
        return
    lines = ["🏪 <b>Truck Planet — Прицепы в наличии:</b>\n"]
    for i, v in enumerate(market, 1):
        lines.append(f"{i}. <b>{v['year']} {v['make']} {v['model']}</b> — ${v['price']:,}")
    player = await get_player_listed_trailers()
    if player:
        lines.append(f"\n💰 <b>Прицепы от игроков:</b>")
        offset = len(market)
        for i, v in enumerate(player, offset + 1):
            lines.append(f"{i}. <b>{v['year']} {v['make']} {v['model']}</b> — ${v['price']:,} (игрок)")
    lines.append(f"\n🛒 <code>!купить_прицеп НОМЕР</code> — купить")
    lines.append(f"🎁 <code>!контейнер_прицеп</code> — открыть контейнер ($25,000)")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("купить_прицеп", prefix="!/"))
async def cmd_buy_trailer(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!купить_прицеп НОМЕР</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите номер из списка")
        return

    market = await get_available_trailers(chat_id=message.chat.id)
    player = await get_player_listed_trailers()
    combined = build_trailer_list(market, player)
    if pos < 1 or pos > len(combined):
        await message.reply("❌ Неверный номер")
        return
    vehicle = combined[pos - 1]

    price = vehicle["price"]
    uid = message.from_user.id

    if vehicle["status"] == "player_listed":
        result = await buy_player_trailer(vehicle["id"], uid)
        if not result:
            await message.reply("❌ Прицеп уже куплен")
            return
        seller_id, price = result
        ok = await update_balance(uid, -price, message.chat.id)
        if ok is None:
            await message.reply("❌ Недостаточно средств")
            return
        await update_balance(seller_id, price, message.chat.id)
        name = f"{vehicle['make']} {vehicle['model']}"
        await add_transaction("buy_trailer", None, uid, -price, f"Покупка прицепа {name} у игрока")
        await add_transaction("sell_trailer", None, seller_id, price, f"Продажа прицепа {name} игроку")
        await message.reply(
            f"✅ <b>Прицеп куплен у игрока</b>\n"
            f"🚛 {vehicle['year']} {vehicle['make']} {vehicle['model']}\n"
            f"💰 ${price:,}",
            parse_mode="HTML",
        )
    else:
        ok = await buy_trailer(vehicle["id"], uid)
        if not ok:
            await message.reply("❌ Прицеп уже куплен")
            return
        ok = await update_balance(uid, -price, message.chat.id)
        if ok is None:
            await message.reply("❌ Недостаточно средств")
            return
        name = f"{vehicle['make']} {vehicle['model']}"
        await add_transaction("buy_trailer", None, uid, -price, f"Покупка прицепа {name} на Truck Planet")
        await message.reply(
            f"✅ <b>Прицеп куплен</b>\n"
            f"🚛 {vehicle['year']} {vehicle['make']} {vehicle['model']}\n"
            f"💰 ${price:,}",
            parse_mode="HTML",
        )


@router.message(Command("прицеп_инфо", prefix="!/"))
async def cmd_trailer_info(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!прицеп_инфо НОМЕР</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите номер из списка")
        return

    market = await get_available_trailers(chat_id=message.chat.id)
    player = await get_player_listed_trailers()
    combined = build_trailer_list(market, player)
    if pos < 1 or pos > len(combined):
        await message.reply("❌ Неверный номер")
        return
    v = combined[pos - 1]
    rarity_line = "\n⭐ Редкий (Public Services)" if v.get("rarity") == "rare" else ""
    await message.reply(
        f"🚛 <b>{v['year']} {v['make']} {v['model']}</b>\n"
        f"📄 {v.get('city', v.get('description', ''))}\n"
        f"💰 ${v['price']:,} | {v.get('miles', 0):,} миль\n"
        f"🎨 {v.get('color', '-')}\n"
        f"🆔 ID: <b>#{v['id']}</b>{rarity_line}",
        parse_mode="HTML",
    )


@router.message(Command("мои_прицепы", prefix="!/"))
async def cmd_my_trailers(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    trailers = await get_user_trailers(message.from_user.id)
    if not trailers:
        await message.reply("🚛 У вас нет прицепов")
        return
    lines = [f"🚛 <b>Ваши прицепы ({len(trailers)}):</b>\n"]
    for v in trailers:
        status = ""
        if v["status"] == "player_listed":
            status = " (в продаже)"
        lines.append(f"#{v['id']} {v['year']} {v['make']} {v['model']}{status}")
    lines.append(f"\n💲 <code>!продать_прицеп ID</code> — слить в Truck Planet ({SELL_REFUND_PCT}%)")
    lines.append(f"🏷 <code>!продать_прицеп_игроку ID цена</code> — продать игроку")
    lines.append(f"🚫 <code>!снять_продажу_прицепа ID</code> — убрать из продажи")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("продать_прицеп", prefix="!/"))
async def cmd_sell_trailer(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!продать_прицеп ID</code>", parse_mode="HTML")
        return
    try:
        trailer_id = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите ID прицепа")
        return
    v = await get_vehicle(trailer_id)
    if not v or v.get("owner_telegram_id") != message.from_user.id or v.get("status") != "sold" or v.get("vehicle_type") != "trailer":
        await message.reply("❌ Прицеп не найден или не принадлежит вам")
        return
    refund = int(v["price"] * SELL_REFUND_PCT / 100)
    ok = await sell_trailer(trailer_id, message.from_user.id)
    if not ok:
        await message.reply("❌ Не удалось продать прицеп")
        return
    await update_balance(message.from_user.id, refund, message.chat.id)
    name = f"{v['make']} {v['model']}"
    await add_transaction("sell_trailer", None, message.from_user.id, refund, f"Продажа прицепа {name} на Truck Planet ({SELL_REFUND_PCT}%)")
    await message.reply(
        f"✅ <b>Прицеп продан</b>\n"
        f"🚛 {v['year']} {v['make']} {v['model']}\n"
        f"💰 Выручка: ${refund:,} ({SELL_REFUND_PCT}%)",
        parse_mode="HTML",
    )


@router.message(Command("продать_прицеп_игроку", prefix="!/"))
async def cmd_list_trailer(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!продать_прицеп_игроку ID цена</code>", parse_mode="HTML")
        return
    try:
        trailer_id = int(args[1])
        price = parse_amount(args[2])
    except ValueError:
        await message.reply("❌ Укажите ID и цену")
        return
    if not price or price <= 0:
        await message.reply("❌ Цена должна быть положительной")
        return

    v = await get_vehicle(trailer_id)
    if not v or v.get("owner_telegram_id") != message.from_user.id or v.get("status") != "sold" or v.get("vehicle_type") != "trailer":
        await message.reply("❌ Прицеп не найден или не принадлежит вам")
        return

    ok = await list_trailer_for_sale(trailer_id, message.from_user.id, price)
    if not ok:
        await message.reply("❌ Не удалось выставить прицеп на продажу")
        return
    await message.reply(
        f"✅ <b>Прицеп выставлен на продажу</b>\n"
        f"🚛 {v['year']} {v['make']} {v['model']}\n"
        f"💰 Цена: ${price:,}",
        parse_mode="HTML",
    )


@router.message(Command("снять_продажу_прицепа", prefix="!/"))
async def cmd_unlist_trailer(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!снять_продажу_прицепа ID</code>", parse_mode="HTML")
        return
    try:
        trailer_id = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите ID прицепа")
        return
    ok = await unlist_trailer(trailer_id, message.from_user.id)
    if not ok:
        await message.reply("❌ Прицеп не найден или не в продаже")
        return
    await message.reply(f"✅ Прицеп #{trailer_id} снят с продажи")


@router.message(Command("контейнер_прицеп", prefix="!/"))
async def cmd_trailer_container(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    CONTAINER_PRICE = 5000
    ok = await update_balance(message.from_user.id, -CONTAINER_PRICE, message.chat.id)
    if ok is None:
        await message.reply(f"❌ Недостаточно средств. Контейнер стоит ${CONTAINER_PRICE:,}")
        return

    trailer = generate_trailer()
    vehicle_id = await create_trailer(
        trailer["make"], trailer["model"], trailer["year"], trailer["price"],
        trailer["miles"], trailer["description"], trailer["vin"], trailer["license_plate"],
        trailer["color"], trailer["rarity"], message.chat.id,
    )

    ok2 = await buy_trailer(vehicle_id, message.from_user.id)
    if not ok2:
        await message.reply("❌ Ошибка при выдаче прицепа")
        return

    name = f"{trailer['year']} {trailer['make']} {trailer['model']}"
    await add_transaction("container_trailer", None, message.from_user.id, -CONTAINER_PRICE, f"Контейнер с прицепом: {name}")

    await message.reply(
        f"🎁 <b>Вы открыли контейнер с прицепом!</b>\n\n"
        f"🚛 {name}\n"
        f"💰 Оценка: ${trailer['price']:,}\n"
        f"🆔 ID: #{vehicle_id}",
        parse_mode="HTML",
    )
