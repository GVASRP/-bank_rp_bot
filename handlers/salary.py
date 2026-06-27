from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user,
    seed_jobs,
    get_all_jobs,
    get_job_by_name,
    set_job_salary,
    set_user_job,
    get_user_job_info,
    remove_user_job,
    update_balance,
    add_transaction,
)
from utils import format_amount, parse_amount, get_user_display, resolve_target, is_admin

router = Router()


@router.message(Command("работа", prefix="!/"))
async def cmd_jobs(message: Message):
    await seed_jobs(message.chat.id)
    jobs = await get_all_jobs(message.chat.id)
    if not jobs:
        await message.reply("📭 Нет доступных профессий")
        return
    lines = ["💼 <b>Доступные профессии:</b>\n"]
    for j in jobs:
        lines.append(f"• <b>{j['name']}</b> — {format_amount(j['salary'])} долларов")
    lines.append(f"\n💡 <code>!устроиться Название</code> — выбрать профессию")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("устроиться", prefix="!/"))
async def cmd_take_job(message: Message):
    await seed_jobs(message.chat.id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!устроиться НазваниеПрофессии</code>", parse_mode="HTML")
        return
    job_name = args[1].strip().capitalize()
    current = await get_user_job_info(message.from_user.id, message.chat.id)
    if current and current["name"].lower() == job_name.lower():
        await message.reply(f"❌ Вы уже работаете \"{current['name']}\"")
        return
    job = await get_job_by_name(message.chat.id, job_name)
    if not job:
        await message.reply(f"❌ Профессия \"{job_name}\" не найдена. Список: <code>!работа</code>", parse_mode="HTML")
        return
    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name, chat_id=message.chat.id)
    await set_user_job(message.from_user.id, message.chat.id, job["id"])
    await message.reply(
        f"✅ Вы устроились <b>{job['name']}</b>! Оклад: {format_amount(job['salary'])} долларов",
        parse_mode="HTML",
    )


@router.message(Command("моя_работа", prefix="!/"))
async def cmd_my_job(message: Message):
    job = await get_user_job_info(message.from_user.id, message.chat.id)
    if not job:
        await message.reply("💼 Вы пока безработный. <code>!работа</code> — посмотреть вакансии", parse_mode="HTML")
        return
    await message.reply(
        f"💼 <b>Ваша профессия:</b> {job['name']}\n"
        f"💰 <b>Оклад:</b> {format_amount(job['salary'])} долларов",
        parse_mode="HTML",
    )


@router.message(Command("уволиться", prefix="!/"))
async def cmd_quit_job(message: Message):
    job = await get_user_job_info(message.from_user.id, message.chat.id)
    if not job:
        await message.reply("❌ Вы и так безработный")
        return
    await remove_user_job(message.from_user.id, message.chat.id)
    await message.reply(f"✅ Вы уволились с должности \"{job['name']}\"", parse_mode="HTML")


@router.message(Command("изменить_зп", prefix="!/"))
async def cmd_change_salary(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Использование: <code>!изменить_зп НазваниеПрофессии сумма</code>", parse_mode="HTML")
        return
    job_name = args[1].strip().capitalize()
    amount = parse_amount(args[2])
    if amount is None or amount < 0:
        await message.reply("❌ Укажите корректную сумму")
        return
    ok = await set_job_salary(message.chat.id, job_name, amount)
    if not ok:
        await message.reply(f"❌ Профессия \"{job_name}\" не найдена")
        return
    await message.reply(f"✅ Оклад \"{job_name}\" изменён на {format_amount(amount)} долларов", parse_mode="HTML")


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
        job = await get_user_job_info(target_id, message.chat.id)
        if not job or job["salary"] <= 0:
            not_found.append(target_name)
            continue
        await update_balance(target_id, job["salary"], message.chat.id)
        await add_transaction("salary", None, target_id, job["salary"],
                              f"Зарплата: {job['name']} — {format_amount(job['salary'])}")
        paid.append(f"{target_name} ({job['name']}) — {format_amount(job['salary'])}")

    lines = [f"💵 <b>Выплата зарплаты</b>\n"]
    if paid:
        lines.append("✅ <b>Получили:</b>")
        lines.extend(f"  • {p}" for p in paid)
    if not_found:
        lines.append(f"\n❌ <b>Не найдены/без работы:</b>")
        lines.extend(f"  • {n}" for n in not_found)
    if not paid and not not_found:
        lines.append("Нет пользователей для выплаты")
    await message.reply("\n".join(lines), parse_mode="HTML")
