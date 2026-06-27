from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user,
    set_user_salary,
    get_user_salary,
    get_all_salaries,
    update_balance,
    add_transaction,
)
from utils import format_amount, parse_amount, get_user_display, resolve_target, is_admin

router = Router()


@router.message(Command("назначить_зп", prefix="!/"))
async def cmd_set_salary(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.reply("❌ Использование: <code>!назначить_зп @user должность сумма</code>", parse_mode="HTML")
        return
    target_id, target_name, target_username, hint = await resolve_target(message, args)
    if target_id is None:
        await message.reply(hint or "❌ Пользователь не найден")
        return
    job_title = args[2].strip().capitalize()
    amount = parse_amount(args[3])
    if amount is None or amount <= 0:
        await message.reply("❌ Укажите корректную сумму")
        return
    await get_or_create_user(target_id, target_username, target_name, chat_id=message.chat.id)
    await set_user_salary(target_id, message.chat.id, job_title, amount)
    await message.reply(
        f"✅ <b>{target_name}</b> назначен \"{job_title}\" с окладом {format_amount(amount)} долларов",
        parse_mode="HTML",
    )


@router.message(Command("зп", prefix="!/"))
async def cmd_pay_salary(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!зп @user1 @user2 ...</code>", parse_mode="HTML")
        return

    paid = []
    not_found = []
    for arg in args[1:]:
        target_id, target_name, target_username, hint = await resolve_target(message, [arg, arg])
        if target_id is None:
            not_found.append(arg)
            continue
        salary_info = await get_user_salary(target_id, message.chat.id)
        if not salary_info or salary_info["salary"] <= 0:
            not_found.append(target_name)
            continue
        await update_balance(target_id, salary_info["salary"], message.chat.id)
        await add_transaction("salary", None, target_id, salary_info["salary"],
                              f"Зарплата: {salary_info['job_title']} — {format_amount(salary_info['salary'])}")
        paid.append(f"{target_name} ({salary_info['job_title']}) — {format_amount(salary_info['salary'])}")

    lines = [f"💵 <b>Выплата зарплаты</b>\n"]
    if paid:
        lines.append("✅ <b>Получили:</b>")
        lines.extend(f"  • {p}" for p in paid)
    if not_found:
        lines.append(f"\n❌ <b>Не найдены/нет ставки:</b>")
        lines.extend(f"  • {n}" for n in not_found)
    if not paid and not not_found:
        lines.append("Нет пользователей для выплаты")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("моя_зп", prefix="!/"))
async def cmd_my_salary(message: Message):
    salary_info = await get_user_salary(message.from_user.id, message.chat.id)
    if not salary_info or salary_info["salary"] <= 0:
        await message.reply("💼 У вас нет назначенной зарплаты")
        return
    await message.reply(
        f"💼 <b>Ваша должность:</b> {salary_info['job_title']}\n"
        f"💰 <b>Оклад:</b> {format_amount(salary_info['salary'])} долларов",
        parse_mode="HTML",
    )


@router.message(Command("список_зп", prefix="!/"))
async def cmd_salary_list(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    salaries = await get_all_salaries(message.chat.id)
    if not salaries:
        await message.reply("📭 Нет назначенных зарплат")
        return
    lines = ["💼 <b>Штатное расписание:</b>\n"]
    for s in salaries:
        name = get_user_display(s)
        lines.append(f"• {name} — <b>{s['job_title']}</b> — {format_amount(s['salary'])}")
    await message.reply("\n".join(lines), parse_mode="HTML")
