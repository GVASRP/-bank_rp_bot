from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import (
    get_or_create_user,
    get_user_by_telegram_id,
    get_available_businesses,
    get_user_businesses,
    get_business,
    get_player_listed_businesses,
    buy_business,
    sell_business,
    list_business_for_sale,
    unlist_business,
    buy_player_business,
    create_business_listing,
    get_all_business_types,
    get_business_type,
    set_business_manager,
    get_business_profit,
    order_business_materials,
    confirm_business_delivery,
    update_balance,
    add_transaction,
    pay_from_org,
    get_org,
    is_org_member,
)
from auto_poster import generate_business
from utils import format_amount, parse_amount, get_user_display, resolve_target, parse_org_flag, parse_org_purchase, check_container_cooldown, get_container_min_boost

router = Router()

BUSINESS_CONTAINER_PRICE = 75000
BIZ_PER_PAGE = 10
SELL_REFUND_PCT = 60


def build_business_list(market: list, player: list) -> list:
    combined = []
    seen = set()
    for b in market:
        combined.append(b)
        seen.add(b["id"])
    for b in player:
        if b["id"] not in seen:
            combined.append(b)
            seen.add(b["id"])
    return combined


def format_biz_page(items: list, page: int, market_count: int) -> str:
    total = len(items)
    start = page * BIZ_PER_PAGE
    end = min(start + BIZ_PER_PAGE, total)
    page_items = items[start:end]

    lines = [f"🏪 <b>Бизнесы:</b> (всего {total})\n"]
    if market_count:
        lines.append(f"📋 <b>Гос. предложение ({market_count} шт.):</b>")
    first_on_page = start + 1
    for i, (src, b) in enumerate(page_items, first_on_page):
        cat = b.get("category", b.get("type_name", ""))
        profit = b.get("profit") or b.get("base_profit", 0)
        mat_cost = b.get("materials_cost", 100)
        tag = " (игрок)" if src == "player" else ""
        lines.append(
            f"#{i} — <b>{b['type_name']}</b> ({cat}){tag}\n"
            f"    💰 ${b['price']:,} | 💵 ${profit:,}/доставка | 📦 ${mat_cost:,}/ед."
        )
    lines.append(f"\n💡 <code>!купить_бизнес N</code> — купить бизнес")
    return "\n".join(lines)


def biz_page_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    btns = []
    if page > 0:
        btns.append(InlineKeyboardButton(text="◀️", callback_data=f"biz:стр:{page - 1}"))
    btns.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        btns.append(InlineKeyboardButton(text="▶️", callback_data=f"biz:стр:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[btns])


@router.callback_query(F.data.regexp(r"^biz:стр:"))
async def biz_page_cb(query: CallbackQuery):
    try:
        page = int(query.data.split(":")[2])
    except (ValueError, IndexError):
        await query.answer("❌ Ошибка данных", show_alert=True)
        return
    try:
        market = await get_available_businesses(chat_id=query.message.chat.id) or []
        player = await get_player_listed_businesses() or []
        items = []
        market_count = len(market)
        for b in market:
            items.append(("salon", b))
        for b in player:
            items.append(("player", b))
        total_pages = (len(items) + BIZ_PER_PAGE - 1) // BIZ_PER_PAGE
        if page < 0 or page >= total_pages:
            await query.answer()
            return
        text = format_biz_page(items, page, market_count)
        page_kb = biz_page_kb(page, total_pages) if total_pages > 1 else None
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=page_kb)
        await query.answer()
    except Exception as e:
        await query.answer(f"❌ {e}", show_alert=True)


async def format_my_biz_page(businesses: list, page: int) -> str:
    total = len(businesses)
    start = page * BIZ_PER_PAGE
    end = min(start + BIZ_PER_PAGE, total)
    page_items = businesses[start:end]

    lines = [f"🏪 <b>Ваши бизнесы:</b> (всего {total})\n"]
    first_on_page = start + 1
    for idx, b in enumerate(page_items, first_on_page):
        status_emoji = "✅" if b["status"] == "sold" else "🔄"
        price_info = f" | Цена: ${b['price']:,}" if b["status"] == "player_listed" else ""
        mgr = ""
        if b.get("manager_telegram_id"):
            mgr_user = await get_user_by_telegram_id(b["manager_telegram_id"])
            if mgr_user:
                mgr = f" | Менеджер: {get_user_display(mgr_user)}"
        mat = b.get("materials", 0)
        max_mat = b.get("max_materials", 100)
        is_open = b.get("is_open", "1")
        open_icon = "✅" if is_open == "1" else "❌"
        mat_info = f" | {open_icon} {mat}/{max_mat}"
        profit = b.get("profit") or b.get("base_profit", 0)
        prof_info = f" | 💵 ${profit:,}/доставка"
        cat = b.get("category", "")
        lines.append(
            f"#{idx} {status_emoji} <b>{b['type_name']}</b> ({cat}){prof_info}{price_info}{mgr}{mat_info}"
        )
    lines.append("\n💡 <code>!продать_бизнес НОМЕР</code> — слить в гос (60%)")
    lines.append("💡 <code>!продать_бизнес НОМЕР цена</code> — выставить игрокам")
    lines.append("💡 <code>!снять_продажу_бизнеса НОМЕР</code> — убрать из продажи")
    return "\n".join(lines)


def my_biz_page_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    btns = []
    if page > 0:
        btns.append(InlineKeyboardButton(text="◀️", callback_data=f"mybiz:стр:{page - 1}"))
    btns.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        btns.append(InlineKeyboardButton(text="▶️", callback_data=f"mybiz:стр:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[btns])


@router.callback_query(F.data.regexp(r"^mybiz:стр:"))
async def my_biz_page_cb(query: CallbackQuery):
    try:
        page = int(query.data.split(":")[2])
    except (ValueError, IndexError):
        await query.answer("❌ Ошибка данных", show_alert=True)
        return
    try:
        businesses = await get_user_businesses(query.from_user.id, chat_id=query.message.chat.id)
        if not businesses:
            await query.message.edit_text("📭 У вас нет бизнесов")
            await query.answer()
            return
        total_pages = (len(businesses) + BIZ_PER_PAGE - 1) // BIZ_PER_PAGE
        if page < 0 or page >= total_pages:
            await query.answer()
            return
        text = await format_my_biz_page(businesses, page)
        page_kb = my_biz_page_kb(page, total_pages) if total_pages > 1 else None
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=page_kb)
        await query.answer()
    except Exception as e:
        await query.answer(f"❌ {e}", show_alert=True)


@router.message(Command("бизнесы_помощь", prefix="!/"))
async def cmd_business_help(message: Message):
    await message.reply(
        "🏪 <b>Система бизнесов</b>\n\n"
        "━━ <b>Покупка/продажа</b> ━━\n"
        "🏪 <code>!бизнесы</code> — список в продаже\n"
        "ℹ️ <code>!бизнес N</code> — детали бизнеса\n"
        "🛒 <code>!купить_бизнес N</code> — купить\n"
        "🏘️ <code>!мои_бизнесы</code> — мои бизнесы\n"
        "💲 <code>!продать_бизнес N</code> — слить в гос (60%)\n"
        "🏷 <code>!продать_бизнес N цена</code> — выставить игрокам\n"
        "🚫 <code>!снять_продажу_бизнеса N</code>\n\n"
        "━━ <b>Работа бизнеса</b> ━━\n"
        "💵 Прибыль начисляется автоматически каждую минуту, пока есть сырьё\n"
        "📦 Когда сырьё заканчивается — бизнес закрывается\n\n"
        "━━ <b>Сырьё</b> ━━\n"
        "1️⃣ Владелец: <code>!заказать_сырьё N [кол-во]</code> — оплатить\n"
        "2️⃣ Менеджер: <code>!доставить_сырьё N</code> — подтвердить доставку\n\n"
        "━━ <b>Менеджер</b> ━━\n"
        "👤 <code>!бизнес_менеджер N @user [зарплата]</code> — назначить\n"
        "💸 Зарплата выплачивается админом через <code>!зп @users</code>\n"
        "   — деньги снимаются с владельца бизнеса\n\n"
        "━━ <b>Контейнер</b> ━━\n"
        "🎁 <code>!контейнер_бизнес</code> — купить случайный бизнес",
        parse_mode="HTML",
    )


@router.message(Command("бизнесы", prefix="!/"))
async def cmd_businesses(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    market = await get_available_businesses(chat_id=message.chat.id)
    player = await get_player_listed_businesses()
    items = []
    market_count = len(market)
    for b in market:
        items.append(("salon", b))
    for b in player:
        items.append(("player", b))
    if not items:
        await message.reply("🏪 На рынке сейчас нет бизнесов в продаже. Загляните позже!")
        return
    page = 0
    total_pages = (len(items) + BIZ_PER_PAGE - 1) // BIZ_PER_PAGE
    text = format_biz_page(items, page, market_count)
    kb = biz_page_kb(page, total_pages) if total_pages > 1 else None
    await message.reply(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("бизнес", prefix="!/"))
async def cmd_business_info(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!бизнес НОМЕР</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите номер из списка")
        return

    market = await get_available_businesses(chat_id=message.chat.id)
    player = await get_player_listed_businesses()
    combined = build_business_list(market, player)
    b = None
    if 1 <= pos <= len(combined):
        b = combined[pos - 1]
    else:
        b = await get_business(pos)
    if not b:
        await message.reply(f"❌ Бизнес #{pos} не найден")
        return

    owner = "В продаже"
    if b.get("owner_telegram_id"):
        owner_user = await get_user_by_telegram_id(b["owner_telegram_id"])
        if owner_user:
            owner = f"Владелец: {get_user_display(owner_user)}"
    elif b.get("status") == "available":
        owner = "🏛 В продаже (гос)"

    profit = await get_business_profit(b["id"])
    profit_line = f"💰 Прибыль: ${profit:,}/доставка\n" if profit else ""

    mgr_line = ""
    if b.get("manager_telegram_id"):
        mgr_user = await get_user_by_telegram_id(b["manager_telegram_id"])
        if mgr_user:
            mgr_line = f"👤 Менеджер: {get_user_display(mgr_user)}\n"

    cat = b.get("category", "")
    materials = b.get("materials", 0)
    max_mat = b.get("max_materials", 100)
    pending = b.get("pending_supplies", 0)
    is_open = b.get("is_open", "1")
    open_status = "✅ Открыт" if is_open == "1" else "❌ Закрыт"
    mat_bar = "█" * (materials // max(1, max_mat // 10)) + "░" * (10 - materials // max(1, max_mat // 10))
    mat_cost = b.get("materials_cost", 100)
    mgr_salary = b.get("manager_salary", 0)
    salary_line = f" | 💵 ${mgr_salary:,}/сессия" if mgr_salary else ""
    pending_line = f"\n⏳ Ожидает доставки: {pending}" if pending else ""
    await message.reply(
        f"🏪 <b>{b['type_name']}</b>\n"
        f"📂 Категория: {cat}\n"
        f"💰 Цена: ${b['price']:,}\n"
        f"{profit_line}"
        f"{mgr_line}{salary_line}"
        f"🚚 Доставок: {b.get('delivery_count', 0)}\n"
        f"📦 Материалы: {materials}/{max_mat} {mat_bar}{pending_line}\n"
        f"💵 Стоимость ед. материалов: ${mat_cost:,}\n"
        f"{open_status}\n"
        f"📌 Статус: {owner}",
        parse_mode="HTML",
    )


@router.message(Command("купить_бизнес", prefix="!/"))
async def cmd_buy_business(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    org_id, own_org, clean_text = parse_org_purchase(message.text)
    args = clean_text.strip().split(maxsplit=1)
    if len(args) < 2:
        usage = "<code>!купить_бизнес НОМЕР</code>" if not org_id else "<code>!купить_бизнес НОМЕР орг ID[ вл]</code>"
        await message.reply(f"❌ Использование: {usage}", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите номер из списка")
        return

    if org_id and not await is_org_member(org_id, message.from_user.id):
        await message.reply("❌ Вы не участник этой организации")
        return

    market = await get_available_businesses(chat_id=message.chat.id)
    player = await get_player_listed_businesses()
    combined = build_business_list(market, player)
    if pos < 1 or pos > len(combined):
        await message.reply("❌ Неверный номер")
        return
    b = combined[pos - 1]

    price = b["price"]
    uid = message.from_user.id
    paid_with_org = False

    async def deduct():
        nonlocal paid_with_org
        if org_id:
            if await pay_from_org(org_id, uid, price, message.chat.id,
                                  f"Покупка бизнеса #{b['id']} {b['type_name']}"):
                paid_with_org = True
                return True
            return False
        return await update_balance(uid, -price, message.chat.id)

    if b["status"] == "player_listed":
        if own_org:
            result = await buy_player_business(b["id"], uid, org_id, chat_id=message.chat.id)
        else:
            result = await buy_player_business(b["id"], uid, chat_id=message.chat.id)
        if not result:
            await message.reply("❌ Бизнес уже куплен")
            return
        seller_id, price = result
        if not await deduct():
            if paid_with_org:
                org = await get_org(org_id)
                err = f"❌ Недостаточно средств в организации. Баланс: ${org['balance'] if org else 0:,}"
            else:
                err = "❌ Недостаточно средств"
            await message.reply(err, parse_mode="HTML")
            return
        await update_balance(seller_id, price, message.chat.id)
        await add_transaction("buy_business", None, uid, -price, f"Покупка бизнеса {b['type_name']} у игрока")
        await add_transaction("sell_business", None, seller_id, price, f"Продажа бизнеса {b['type_name']} игроку")
        source = f"🏢 В собственность орг. #{org_id}" if own_org else (f"🏢 Орг. #{org_id}" if paid_with_org else "")
        await message.reply(
            f"✅ <b>Бизнес куплен у игрока</b>\n"
            f"🏪 {b['type_name']}\n"
            f"💰 ${price:,}{' | ' + source if source else ''}",
            parse_mode="HTML",
        )
    else:
        if own_org:
            ok = await buy_business(b["id"], uid, org_id, chat_id=message.chat.id)
        else:
            ok = await buy_business(b["id"], uid, chat_id=message.chat.id)
        if not ok:
            await message.reply("❌ Бизнес уже куплен")
            return
        if not await deduct():
            if paid_with_org:
                org = await get_org(org_id)
                err = f"❌ Недостаточно средств в организации. Баланс: ${org['balance'] if org else 0:,}"
            else:
                err = "❌ Недостаточно средств"
            await message.reply(err, parse_mode="HTML")
            return
        await add_transaction("buy_business", None, uid, -price, f"Покупка бизнеса {b['type_name']}")
        source = f"🏢 В собственность орг. #{org_id}" if own_org else (f"🏢 Орг. #{org_id}" if paid_with_org else "")
        await message.reply(
            f"✅ <b>Бизнес куплен</b>\n"
            f"🏪 {b['type_name']}\n"
            f"💰 ${price:,}{' | ' + source if source else ''}",
            parse_mode="HTML",
        )


@router.message(Command("мои_бизнесы", prefix="!/"))
async def cmd_my_businesses(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    businesses = await get_user_businesses(message.from_user.id, chat_id=message.chat.id)
    if not businesses:
        await message.reply("🏪 У вас нет бизнесов")
        return
    page = 0
    total_pages = (len(businesses) + BIZ_PER_PAGE - 1) // BIZ_PER_PAGE
    text = await format_my_biz_page(businesses, page)
    kb = my_biz_page_kb(page, total_pages) if total_pages > 1 else None
    await message.reply(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("продать_бизнес", prefix="!/"))
async def cmd_sell_business(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!продать_бизнес НОМЕР [цена]</code>\n"
                           "Без цены — слить в гос (60%)\n"
                           "С ценой — выставить игрокам", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    businesses = await get_user_businesses(message.from_user.id, chat_id=message.chat.id)
    if pos < 1 or pos > len(businesses):
        await message.reply(f"❌ Бизнес #{pos} не найден")
        return
    b = businesses[pos - 1]
    bid = b["id"]

    if len(args) >= 3:
        price = parse_amount(args[2])
        if not price or price <= 0:
            await message.reply("❌ Цена должна быть положительной")
            return
        if b["status"] != "sold":
            await message.reply("❌ Этот бизнес уже выставлен на продажу или не куплен")
            return
        if b["owner_telegram_id"] != message.from_user.id:
            await message.reply("❌ Это не ваш бизнес")
            return
        if not await list_business_for_sale(bid, message.from_user.id, price):
            await message.reply("❌ Ошибка выставления на продажу")
            return
        await message.reply(
            f"✅ <b>{b['type_name']}</b> выставлен на продажу за ${price:,}!\n"
            f"💡 Другие могут купить через <code>!купить_бизнес НОМЕР</code>",
            parse_mode="HTML",
        )
    else:
        if b["owner_telegram_id"] != message.from_user.id:
            await message.reply("❌ Это не ваш бизнес")
            return
        if b["status"] == "player_listed":
            await unlist_business(bid, message.from_user.id)
        price = int(b["price"] * SELL_REFUND_PCT / 100)
        if not await sell_business(bid, message.from_user.id):
            await message.reply("❌ Ошибка продажи")
            return
        await update_balance(message.from_user.id, price, message.chat.id)
        await add_transaction("sell_business", None, message.from_user.id, price,
                              f"Продажа бизнеса #{bid} {b['type_name']} ({SELL_REFUND_PCT}%)")
        await message.reply(
            f"✅ <b>{b['type_name']}</b> продан в гос!\n"
            f"💰 Выручка: {format_amount(price)} долларов ({SELL_REFUND_PCT}%)",
            parse_mode="HTML",
        )


@router.message(Command("снять_продажу_бизнеса", prefix="!/"))
async def cmd_unlist_business(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!снять_продажу_бизнеса НОМЕР</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите номер из списка")
        return

    businesses = await get_user_businesses(message.from_user.id, chat_id=message.chat.id)
    if pos < 1 or pos > len(businesses):
        await message.reply(f"❌ Бизнес #{pos} не найден")
        return
    b = businesses[pos - 1]
    if b["status"] != "player_listed":
        await message.reply("❌ Этот бизнес не выставлен на продажу")
        return
    if not await unlist_business(b["id"], message.from_user.id):
        await message.reply("❌ Ошибка снятия с продажи")
        return
    await message.reply(f"✅ <b>{b['type_name']}</b> снят с продажи", parse_mode="HTML")


@router.message(Command("бизнес_менеджер", prefix="!/"))
async def cmd_business_manager(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Использование: <code>!бизнес_менеджер НОМЕР [@user] [зарплата]</code>\n"
                           "С @user — назначить менеджера\n"
                           "С @user и зарплатой — назначить с окладом\n"
                           "Без @user — снять менеджера", parse_mode="HTML")
        return
    try:
        pos = int(parts[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    businesses = await get_user_businesses(message.from_user.id, chat_id=message.chat.id)
    if pos < 1 or pos > len(businesses):
        await message.reply(f"❌ Бизнес #{pos} не найден")
        return
    b = businesses[pos - 1]
    if b["owner_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш бизнес")
        return

    if len(parts) >= 3:
        salary = 0
        target_raw = parts[2]
        if len(parts) >= 4:
            try:
                salary = max(0, int(parts[3]))
            except ValueError:
                await message.reply("❌ Зарплата должна быть числом")
                return
        target_id, target_name, target_username, hint = await resolve_target(message, [target_raw])
        if not target_id:
            await message.reply(hint or "❌ Пользователь не найден")
            return
        await get_or_create_user(target_id, target_username, target_name, chat_id=message.chat.id)
        ok = await set_business_manager(b["id"], target_id, message.chat.id, salary)
        if not ok:
            await message.reply("❌ Ошибка назначения менеджера")
            return
        salary_text = f" с окладом ${salary:,}" if salary else ""
        await message.reply(
            f"✅ Менеджером <b>{b['type_name']}</b> назначен {target_name}{salary_text}",
            parse_mode="HTML",
        )
    else:
        ok = await set_business_manager(b["id"], None, message.chat.id)
        if not ok:
            await message.reply("❌ Ошибка снятия менеджера")
            return
        await message.reply(f"✅ Менеджер <b>{b['type_name']}</b> снят", parse_mode="HTML")


@router.message(Command("доставить_сырьё", prefix="!/"))
async def cmd_confirm_materials(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!доставить_сырьё НОМЕР</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Укажите номер из списка")
        return

    businesses = await get_user_businesses(message.from_user.id, chat_id=message.chat.id)
    if pos < 1 or pos > len(businesses):
        await message.reply(f"❌ Бизнес #{pos} не найден")
        return
    b = businesses[pos - 1]

    if b.get("manager_telegram_id") != message.from_user.id:
        await message.reply("❌ Только менеджер может подтвердить доставку")
        return

    ok, err_msg = await confirm_business_delivery(b["id"], message.from_user.id)
    if not ok:
        await message.reply(err_msg, parse_mode="HTML")
        return

    pending = b.get("pending_supplies", 0)
    new_mat = b.get("materials", 0) + pending
    await message.reply(
        f"✅ Доставка подтверждена для <b>{b['type_name']}</b>!\n"
        f"📦 Добавлено материалов: <b>{pending}</b>\n"
        f"📊 Всего материалов: {new_mat}",
        parse_mode="HTML",
    )


@router.message(Command("заказать_сырьё", prefix="!/"))
async def cmd_order_materials(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!заказать_сырьё НОМЕР [количество]</code>", parse_mode="HTML")
        return
    try:
        pos = int(args[1])
    except ValueError:
        await message.reply("❌ Номер должен быть числом")
        return

    businesses = await get_user_businesses(message.from_user.id, chat_id=message.chat.id)
    if pos < 1 or pos > len(businesses):
        await message.reply(f"❌ Бизнес #{pos} не найден")
        return
    b = businesses[pos - 1]
    if b["owner_telegram_id"] != message.from_user.id:
        await message.reply("❌ Это не ваш бизнес")
        return

    if b.get("manager_telegram_id") is None:
        await message.reply("❌ Сначала назначьте менеджера")
        return

    amount = 10
    if len(args) >= 3:
        try:
            amount = int(args[2])
        except ValueError:
            await message.reply("❌ Количество должно быть числом")
            return
    if amount <= 0:
        await message.reply("❌ Количество должно быть положительным")
        return

    ok, cost = await order_business_materials(b["id"], amount)
    if not ok:
        await message.reply("❌ Склад уже полон или бизнес не найден")
        return

    if not await update_balance(message.from_user.id, -cost, message.chat.id):
        await message.reply(f"❌ Недостаточно средств. Нужно ${cost:,}", parse_mode="HTML")
        return

    unit_cost = cost // amount if amount else 0
    await add_transaction("business_materials", None, message.from_user.id, -cost,
                          f"Заказ сырья для #{b['id']} {b['type_name']} ({amount} ед.)")
    await message.reply(
        f"✅ Заказано <b>{amount}</b> ед. сырья для <b>{b['type_name']}</b>\n"
        f"💵 Цена за ед.: ${unit_cost:,}\n"
        f"💰 Итого: ${cost:,}\n"
        f"⏳ Ожидает подтверждения менеджером",
        parse_mode="HTML",
    )


@router.message(Command("контейнер_бизнес", prefix="!/"))
async def cmd_business_container(message: Message):
    uid = message.from_user.id
    ok, wait = await check_container_cooldown(uid, "business")
    if not ok:
        hrs = int(wait // 3600)
        mins = int((wait % 3600) // 60)
        await message.reply(f"⏳ Вы уже открывали контейнер сегодня. Подождите {hrs}ч {mins}м")
        return

    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    org_id, _ = parse_org_flag(message.text)

    if org_id and not await is_org_member(org_id, message.from_user.id):
        await message.reply("❌ Вы не участник этой организации")
        return

    uid = message.from_user.id
    paid_with_org = False

    if org_id:
        if not await pay_from_org(org_id, uid, BUSINESS_CONTAINER_PRICE, message.chat.id,
                                  "Контейнер с бизнесом"):
            org = await get_org(org_id)
            err = f"❌ Недостаточно средств в организации. Баланс: ${org['balance'] if org else 0:,}"
            await message.reply(err, parse_mode="HTML")
            return
        paid_with_org = True
    else:
        if not await update_balance(uid, -BUSINESS_CONTAINER_PRICE, message.chat.id):
            user = await get_user_by_telegram_id(uid, message.chat.id)
            await message.reply(
                f"❌ Недостаточно средств. Контейнер стоит ${BUSINESS_CONTAINER_PRICE:,}",
                parse_mode="HTML",
            )
            return

    min_boost = await get_container_min_boost()
    for _ in range(200):
        biz = generate_business()
        if min_boost > 0 and biz["price"] < min_boost:
            continue
        break

    biz_id = await create_business_listing(
        message.chat.id, biz["business_type_id"], biz["price"], biz["guid"],
    )
    ok2 = await buy_business(biz_id, uid, chat_id=message.chat.id)
    if not ok2:
        await message.reply("❌ Ошибка при выдаче бизнеса")
        return

    await add_transaction("container_business", uid, None, BUSINESS_CONTAINER_PRICE,
                          f"Контейнер с бизнесом: {biz['type_name']}")
    if paid_with_org:
        await add_transaction("org_payment", uid, None, -BUSINESS_CONTAINER_PRICE,
                              f"Контейнер бизнес из орг. #{org_id}: {biz['type_name']}")

    await message.reply(
        f"🎁 <b>Вы открыли контейнер с бизнесом!</b>\n\n"
        f"🏪 <b>{biz['type_name']}</b>\n"
        f"📂 Категория: {biz.get('category', '')}\n"
        f"💰 Стоимость: ${biz['price']:,}\n"
        f"🆔 ID: #{biz_id}{' | 🏢 Орг.' if paid_with_org else ''}",
        parse_mode="HTML",
    )


@router.message(Command("добавить_бизнес", prefix="!/"))
async def cmd_add_business(message: Message):
    chat_type = message.chat.type
    if chat_type not in ("group", "supergroup"):
        await message.reply("❌ Админ-команды работают только в группах")
        return
    from utils import is_admin
    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Эта команда только для администраторов группы")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bts = await get_all_business_types()
        lines = [f"#{bt['id']} — <b>{bt['name']}</b> ({bt['category']}) | ${bt['min_price']:,}-${bt['max_price']:,}" for bt in bts]
        await message.reply(
            "❌ Использование: <code>!добавить_бизнес ID_ТИПА ЦЕНА</code>\n\n"
            "📋 <b>Типы бизнесов:</b>\n" + "\n".join(lines),
            parse_mode="HTML",
        )
        return
    try:
        bt_id = int(parts[1])
        price = int(parts[2])
    except ValueError:
        await message.reply("❌ ID типа и цена должны быть числами")
        return
    bt = await get_business_type(bt_id)
    if not bt:
        await message.reply("❌ Тип бизнеса не найден")
        return
    import random
    guid = f"admin_{bt_id}_{random.randint(100000, 999999)}"
    try:
        biz_id = await create_business_listing(message.chat.id, bt_id, price, guid)
    except ValueError as e:
        await message.reply(f"❌ {e}")
        return
    await message.reply(
        f"✅ Бизнес добавлен!\n"
        f"🏪 #{biz_id} <b>{bt['name']}</b>\n"
        f"📂 {bt['category']}\n"
        f"💰 ${price:,} | 📈 Прибыль: ${bt['base_profit']:,}/доставка",
        parse_mode="HTML",
    )
