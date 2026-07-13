from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user, get_user_by_telegram_id, update_balance, add_transaction,
    buy_insurance, get_user_insurances, get_insurance,
    process_insurance_payout, delete_insurance, get_vehicle_insurance,
    COVERAGE_TYPES,
)
from utils import format_amount, is_admin

router = Router()


COVERAGE_NAMES = {"базовый": "Базовый", "стандарт": "Стандарт", "премиум": "Премиум"}


def fmt_ins(ins: dict) -> str:
    status_icon = {"active": "🟢", "expired": "🔴", "claimed": "✅", "cancelled": "❌"}
    return (
        f"{status_icon.get(ins['status'], '❓')} <b>#{ins['id']}</b> "
        f"{ins['year']} {ins['make']} {ins['model']} | "
        f"{COVERAGE_NAMES.get(ins['coverage_type'], ins['coverage_type'])} ({ins['coverage_percent']}%) | "
        f"${ins['vehicle_value']:,}"
    )


@router.message(Command("страховка", prefix="!/"))
async def cmd_insurance(message: Message):
    uid = message.from_user.id
    await get_or_create_user(uid, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=3)

    if len(args) >= 2:
        vehicle_arg = args[1]
        try:
            vehicle_id = int(vehicle_arg)
        except ValueError:
            await message.reply("❌ ID авто должен быть числом")
            return

        coverage_type = "стандарт"
        if len(args) >= 3:
            ct = args[2].lower()
            if ct in COVERAGE_TYPES:
                coverage_type = ct
            else:
                await message.reply("❌ Тип: базовый / стандарт / премиум")
                return

        user = await get_user_by_telegram_id(uid, message.chat.id)
        balance = user["balance"] if user else 0
        ct_info = COVERAGE_TYPES[coverage_type]

        # Check if user owns the vehicle first to estimate premium
        result = await buy_insurance(vehicle_id, uid, coverage_type)
        if not result["ok"]:
            if "не принадлежит" in result["error"] or "не найдено" in result["error"]:
                await message.reply("❌ Это авто не найдено или не принадлежит вам")
            elif "уже есть" in result["error"]:
                await message.reply("❌ На это авто уже есть активная страховка")
            else:
                await message.reply(f"❌ {result['error']}")
            return

        premium = result["premium"]
        if balance < premium:
            # Rollback - delete the just-created insurance
            await delete_insurance(result["ins_id"])
            await message.reply(
                f"❌ Недостаточно средств. Нужно ${premium:,}, у вас {format_amount(balance)}\n"
                f"💰 Страховка <b>{COVERAGE_NAMES[coverage_type]}</b> стоит {ct_info['cost_pct']}% от цены авто",
                parse_mode="HTML",
            )
            return

        await update_balance(uid, -premium, message.chat.id)
        await add_transaction("insurance_buy", None, uid, -premium,
                              f"Страховка #{result['ins_id']} на {result['vehicle']} ({coverage_type})")
        await message.reply(
            f"✅ <b>Страховка оформлена!</b>\n"
            f"🚗 {result['vehicle']}\n"
            f"📄 Тип: {COVERAGE_NAMES[coverage_type]} ({result['coverage']})\n"
            f"💰 Стоимость: ${premium:,}\n"
            f"💎 Покрытие: до ${result['value'] * ct_info['pct'] // 100:,}\n"
            f"📅 Действует 30 дней",
            parse_mode="HTML",
        )
        return

    # Show user's insurances
    insurances = await get_user_insurances(uid)
    if not insurances:
        await message.reply(
            "📋 <b>Страхование авто</b>\n\n"
            "У вас нет активных страховок.\n\n"
            "━━ <b>Как оформить:</b> ━━\n"
            "<code>!страховка ID_АВТО [базовый|стандарт|премиум]</code>\n\n"
            "━━ <b>Типы</b> ━━\n"
            "🟡 Базовый — 50% стоимости, премия 5%\n"
            "🟠 Стандарт — 80% стоимости, премия 10%\n"
            "🔴 Премиум — 100% стоимости, премия 20%\n"
            "📅 Срок действия: 30 дней\n\n"
            "━━ <b>Админ:</b> ━━\n"
            "<code>!страховая_выплата ID</code> — выплатить\n"
            "<code>!страховка_удалить ID</code> — удалить запись",
            parse_mode="HTML",
        )
        return

    lines = ["📋 <b>Мои страховки</b>\n"]
    active = [i for i in insurances if i["status"] == "active"]
    other = [i for i in insurances if i["status"] != "active"]
    for i in active:
        lines.append(fmt_ins(i))
    if other:
        lines.append("\n━━ <b>Архив</b> ━━")
        for i in other:
            lines.append(fmt_ins(i))
    lines.append(f"\n━━ Всего: {len(insurances)} (активных: {len(active)})")
    lines.append("<code>!страховка ID_АВТО [тип]</code> — купить")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("страховая_выплата", prefix="!/"))
async def cmd_insurance_payout(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Использование: <code>!страховая_выплата ID_СТРАХОВКИ</code>", parse_mode="HTML")
        return
    try:
        ins_id = int(parts[1])
    except ValueError:
        await message.reply("❌ ID страховки должен быть числом")
        return
    result = await process_insurance_payout(ins_id)
    if not result["ok"]:
        await message.reply(f"❌ {result['error']}")
        return
    await message.reply(
        f"✅ <b>Страховая выплата произведена!</b>\n"
        f"🚗 {result['vehicle']}\n"
        f"💰 Выплачено: ${result['payout']:,} ({result['coverage_pct']}%)\n"
        f"🏷 Авто возвращено в продажу",
        parse_mode="HTML",
    )


@router.message(Command("страховка_удалить", prefix="!/"))
async def cmd_delete_insurance(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Использование: <code>!страховка_удалить ID</code>", parse_mode="HTML")
        return
    try:
        ins_id = int(parts[1])
    except ValueError:
        await message.reply("❌ ID страховки должен быть числом")
        return
    ins = await get_insurance(ins_id)
    if not ins:
        await message.reply("❌ Страховка не найдена")
        return
    await delete_insurance(ins_id)
    await message.reply(
        f"✅ Страховка <b>#{ins_id}</b> удалена\n"
        f"🚗 {ins['year']} {ins['make']} {ins['model']}",
        parse_mode="HTML",
    )
