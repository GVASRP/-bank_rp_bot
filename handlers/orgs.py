from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    create_org,
    get_org,
    get_user_orgs,
    update_org_balance,
    add_org_member,
    remove_org_member,
    get_org_members,
    is_org_member,
    is_org_owner,
    update_balance,
    add_transaction,
    get_org_vehicles,
    get_org_houses,
    get_org_trailers,
)
from utils import format_amount, parse_amount, resolve_target

router = Router()


@router.message(Command("создать_орг", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_create_org(message: Message):
    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!создать_орг Название</code>", parse_mode="HTML")
        return
    name = args[1].strip()
    if len(name) > 50:
        await message.reply("❌ Название слишком длинное (макс. 50 символов)")
        return
    org_id = await create_org(name, message.from_user.id)
    await message.reply(
        f"✅ Организация <b>{name}</b> создана!\n"
        f"🆔 ID: <code>{org_id}</code>\n"
        f"Используйте <code>!орг {org_id}</code> для просмотра",
        parse_mode="HTML",
    )


@router.message(Command("орги", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_my_orgs(message: Message):
    orgs = await get_user_orgs(message.from_user.id)
    if not orgs:
        await message.reply(
            "❌ У вас нет организаций.\n"
            "Создайте: <code>!создать_орг Название</code>",
            parse_mode="HTML",
        )
        return
    lines = ["📋 <b>Ваши организации:</b>\n"]
    for o in orgs:
        owner = "👑" if o["owner_telegram_id"] == message.from_user.id else ""
        lines.append(f"  #{o['id']} {o['name']} — ${o['balance']:,} {owner}")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("орг", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_org_info(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        orgs = await get_user_orgs(message.from_user.id)
        if orgs:
            ids = " ".join(f"#{o['id']}" for o in orgs)
            await message.reply(
                "❌ Укажите ID организации.\n"
                f"Ваши: {ids}",
                parse_mode="HTML",
            )
        else:
            await message.reply("❌ Использование: <code>!орг ID</code>", parse_mode="HTML")
        return
    try:
        org_id = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    org = await get_org(org_id)
    if not org:
        await message.reply("❌ Организация не найдена")
        return
    if not await is_org_member(org_id, message.from_user.id):
        await message.reply("❌ Вы не участник этой организации")
        return
    members = await get_org_members(org_id)
    member_lines = []
    for m in members:
        icon = "👑" if m["role"] == "owner" else "👤"
        name = m.get("name") or f"id{m['telegram_id']}"
        member_lines.append(f"  {icon} {name}")
    vehicles_count = len(await get_org_vehicles(org_id))
    houses_count = len(await get_org_houses(org_id))
    trailers_count = len(await get_org_trailers(org_id))
    await message.reply(
        f"🏢 <b>{org['name']}</b>\n"
        f"🆔 ID: <code>{org['id']}</code>\n"
        f"💰 Баланс: <b>${org['balance']:,}</b>\n"
        f"🚗 Авто: {vehicles_count} | 🏠 Дома: {houses_count} | 🚛 Прицепы: {trailers_count}\n\n"
        f"👥 <b>Участники ({len(members)}):</b>\n" + "\n".join(member_lines) +
        f"\n\n"
        f"<code>!орг_пополнить {org_id} сумма</code> — пополнить с баланса\n"
        f"<code>!орг_вывести {org_id} сумма</code> — вывести на баланс\n"
        f"<code>!орг_добавить {org_id} @user</code> — добавить участника\n"
        f"<code>!орг_удалить {org_id} @user</code> — удалить участника\n"
        f"<code>!орг_авто {org_id}</code> — имущество (авто)\n"
        f"<code>!орг_дома {org_id}</code> — имущество (дома)\n"
        f"<code>!орг_прицепы {org_id}</code> — имущество (прицепы)",
        parse_mode="HTML",
    )


@router.message(Command("орг_пополнить", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_org_deposit(message: Message):
    args = message.text.strip().split()
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!орг_пополнить ID сумма</code>", parse_mode="HTML")
        return
    try:
        org_id = int(args[1])
        amount = parse_amount(args[2])
    except ValueError:
        await message.reply("❌ ID и сумма должны быть числами")
        return
    if not amount or amount <= 0:
        await message.reply("❌ Сумма должна быть положительным числом")
        return
    org = await get_org(org_id)
    if not org:
        await message.reply("❌ Организация не найдена")
        return
    if not await is_org_member(org_id, message.from_user.id):
        await message.reply("❌ Вы не участник этой организации")
        return
    if not await update_balance(message.from_user.id, -amount, message.chat.id):
        await message.reply(f"❌ Недостаточно средств. Нужно: ${amount:,}")
        return
    await update_org_balance(org_id, amount)
    await add_transaction("org_deposit", message.from_user.id, None, -amount,
                          f"Пополнение {org['name']}: +${amount:,}")
    await message.reply(
        f"✅ ${amount:,} переведено в организацию <b>{org['name']}</b>\n"
        f"💰 Баланс организации: ${org['balance'] + amount:,}",
        parse_mode="HTML",
    )


@router.message(Command("орг_вывести", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_org_withdraw(message: Message):
    args = message.text.strip().split()
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!орг_вывести ID сумма</code>", parse_mode="HTML")
        return
    try:
        org_id = int(args[1])
        amount = parse_amount(args[2])
    except ValueError:
        await message.reply("❌ ID и сумма должны быть числами")
        return
    if not amount or amount <= 0:
        await message.reply("❌ Сумма должна быть положительным числом")
        return
    org = await get_org(org_id)
    if not org:
        await message.reply("❌ Организация не найдена")
        return
    if not await is_org_owner(org_id, message.from_user.id):
        await message.reply("❌ Только владелец может выводить средства")
        return
    if not await update_org_balance(org_id, -amount):
        await message.reply(f"❌ Недостаточно средств в организации. Баланс: ${org['balance']:,}")
        return
    await update_balance(message.from_user.id, amount, message.chat.id)
    await add_transaction("org_withdraw", None, message.from_user.id, amount,
                          f"Вывод из {org['name']}: -${amount:,}")
    await message.reply(
        f"✅ ${amount:,} выведено из организации <b>{org['name']}</b>\n"
        f"💰 Баланс организации: ${org['balance'] - amount:,}",
        parse_mode="HTML",
    )


@router.message(Command("орг_перевести", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_org_transfer(message: Message):
    args = message.text.strip().split(maxsplit=3)
    if len(args) < 4:
        await message.reply("❌ Использование: <code>!орг_перевести ID @user сумма</code>", parse_mode="HTML")
        return
    try:
        org_id = int(args[1])
        amount = parse_amount(args[3])
    except ValueError:
        await message.reply("❌ ID и сумма должны быть числами")
        return
    if not amount or amount <= 0:
        await message.reply("❌ Сумма должна быть положительным числом")
        return
    org = await get_org(org_id)
    if not org:
        await message.reply("❌ Организация не найдена")
        return
    if not await is_org_member(org_id, message.from_user.id):
        await message.reply("❌ Вы не участник этой организации")
        return
    target_id, target_name, target_username, _ = await resolve_target(message, [""] + args[1:])
    if not target_id:
        await message.reply("❌ Пользователь не найден")
        return
    if not await is_org_owner(org_id, message.from_user.id):
        await message.reply("❌ Только владелец может переводить средства участникам")
        return
    if not await update_org_balance(org_id, -amount):
        await message.reply(f"❌ Недостаточно средств в организации. Баланс: ${org['balance']:,}")
        return
    await update_balance(target_id, amount, message.chat.id)
    await add_transaction("org_transfer", message.from_user.id, target_id, -amount,
                          f"Перевод из {org['name']} → {target_name}")
    await message.reply(
        f"✅ ${amount:,} переведено из <b>{org['name']}</b> пользователю {target_name}\n"
        f"💰 Баланс организации: ${org['balance'] - amount:,}",
        parse_mode="HTML",
    )


@router.message(Command("орг_добавить", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_org_add_member(message: Message):
    args = message.text.strip().split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!орг_добавить ID @user</code>", parse_mode="HTML")
        return
    try:
        org_id = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    org = await get_org(org_id)
    if not org:
        await message.reply("❌ Организация не найдена")
        return
    if not await is_org_owner(org_id, message.from_user.id):
        await message.reply("❌ Только владелец может добавлять участников")
        return
    target_id, target_name, target_username, _ = await resolve_target(message, args)
    if not target_id:
        await message.reply("❌ Пользователь не найден")
        return
    ok = await add_org_member(org_id, target_id)
    if not ok:
        await message.reply("❌ Пользователь уже в организации")
        return
    await message.reply(
        f"✅ {target_name} добавлен в организацию <b>{org['name']}</b>",
        parse_mode="HTML",
    )


@router.message(Command("орг_удалить", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_org_remove_member(message: Message):
    args = message.text.strip().split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!орг_удалить ID @user</code>", parse_mode="HTML")
        return
    try:
        org_id = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    org = await get_org(org_id)
    if not org:
        await message.reply("❌ Организация не найдена")
        return
    if not await is_org_owner(org_id, message.from_user.id):
        await message.reply("❌ Только владелец может удалять участников")
        return
    target_id, target_name, target_username, _ = await resolve_target(message, args)
    if not target_id:
        await message.reply("❌ Пользователь не найден")
        return
    if target_id == message.from_user.id:
        await message.reply("❌ Нельзя удалить себя. Передайте организацию другому владельцу")
        return
    ok = await remove_org_member(org_id, target_id)
    if not ok:
        await message.reply("❌ Пользователь не найден или является владельцем")
        return
    await message.reply(
        f"✅ {target_name} удалён из организации <b>{org['name']}</b>",
        parse_mode="HTML",
    )


@router.message(Command("орг_авто", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_org_vehicles(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!орг_авто ID</code>", parse_mode="HTML")
        return
    try:
        org_id = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    if not await is_org_member(org_id, message.from_user.id):
        await message.reply("❌ Вы не участник этой организации")
        return
    org = await get_org(org_id)
    if not org:
        await message.reply("❌ Организация не найдена")
        return
    vehicles = await get_org_vehicles(org_id)
    if not vehicles:
        await message.reply(f"🏢 <b>{org['name']}</b> — нет автомобилей", parse_mode="HTML")
        return
    lines = [f"🏢 <b>{org['name']}</b> — автомобили:\n"]
    for idx, v in enumerate(vehicles, 1):
        lines.append(f"#{idx} {v['year']} {v['make']} {v['model']} — ${v['price']:,}")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("орг_дома", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_org_houses(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!орг_дома ID</code>", parse_mode="HTML")
        return
    try:
        org_id = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    if not await is_org_member(org_id, message.from_user.id):
        await message.reply("❌ Вы не участник этой организации")
        return
    org = await get_org(org_id)
    if not org:
        await message.reply("❌ Организация не найдена")
        return
    houses = await get_org_houses(org_id)
    if not houses:
        await message.reply(f"🏢 <b>{org['name']}</b> — нет домов", parse_mode="HTML")
        return
    lines = [f"🏢 <b>{org['name']}</b> — дома:\n"]
    for idx, h in enumerate(houses, 1):
        lines.append(f"#{idx} {h['type_name']} ({h['neighborhood']}) — ${h['price']:,}")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("орг_прицепы", prefix="!/"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_org_trailers(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!орг_прицепы ID</code>", parse_mode="HTML")
        return
    try:
        org_id = int(args[1])
    except ValueError:
        await message.reply("❌ ID должен быть числом")
        return
    if not await is_org_member(org_id, message.from_user.id):
        await message.reply("❌ Вы не участник этой организации")
        return
    org = await get_org(org_id)
    if not org:
        await message.reply("❌ Организация не найдена")
        return
    trailers = await get_org_trailers(org_id)
    if not trailers:
        await message.reply(f"🏢 <b>{org['name']}</b> — нет прицепов", parse_mode="HTML")
        return
    lines = [f"🏢 <b>{org['name']}</b> — прицепы:\n"]
    for idx, t in enumerate(trailers, 1):
        lines.append(f"#{idx} {t['year']} {t['make']} {t['model']} — ${t['price']:,}")
    await message.reply("\n".join(lines), parse_mode="HTML")
