from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import time

from database import (
    get_or_create_user,
    seed_jobs,
    get_all_jobs,
    get_job_by_name,
    set_job_salary,
    set_user_job,
    get_user_job_info,
    remove_user_job,
    create_job_request,
    get_pending_job_requests,
    approve_job_request,
    reject_job_request,
    get_all_users_with_jobs,
    update_balance,
    add_transaction,
)
from database import get_job_category, is_job_taken
from utils import format_amount, parse_amount, is_admin, resolve_target

router = Router()

LAW_CATEGORIES = {"law"}
CRIME_CATEGORIES = {"criminal"}
DELIVERY_JOBS = {"Дальнобойщик"}

DELIVERY_LOCATIONS = [
    "Shell (ул. Главная, 142)",
    "Walmart Supercenter (ш. Мэдисон, 55)",
    "Ферма Джонсона (Сельская дорога, 7)",
    "Автосервис \"У Боба\" (Индустриальная, 23)",
    "Больница Гринвилл (Медицинский пр., 15)",
    "Аптека \"Здоровье\" (Медицинский пр., 17)",
    "Склад №12 (Логистический пер., 4)",
    "Порт Гринвилл (Набережная, 1)",
    "McDonald's (ш. Мэдисон, 100)",
    "Молочный завод WI (Индустриальная, 50)",
    "Школа Гринвилл (Школьная, 10)",
    "Полицейский участок (Центральная, 30)",
    "Банк Wisconsin Trust (Центральная, 25)",
    "АЗС BP (Окружная, 8)",
    "Ресторан \"У озера\" (Озёрная, 12)",
    "Отель Greenville Inn (Туристическая, 5)",
    "Строительный двор (Строительная, 3)",
    "Ферма Миллера (Олд-Роуд, 15)",
]

DELIVERY_GOODS = [
    "продукты питания", "стройматериалы", "топливо", "медикаменты",
    "мебель", "бытовая техника", "автозапчасти", "зерно",
    "молочная продукция", "одежда", "электроника", "корма для скота",
    "пиломатериалы", "химикаты", "напитки", "консервы",
]

_last_delivery = {}


@router.message(Command("работа", prefix="!/"))
async def cmd_jobs(message: Message):
    await seed_jobs(message.chat.id)
    jobs = await get_all_jobs(message.chat.id)
    if not jobs:
        await message.reply("📭 Нет доступных профессий")
        return
    civilian = []
    law = []
    emergency = []
    medical = []
    criminal = []
    for j in jobs:
        cat = get_job_category(j["name"])
        if cat == "law":
            law.append(j)
        elif cat == "emergency":
            emergency.append(j)
        elif cat == "medical":
            medical.append(j)
        elif cat == "criminal":
            criminal.append(j)
        else:
            civilian.append(j)

    UNIQUE = {"Мэр", "Прокурор"}
    lines = ["💼 <b>Доступные профессии:</b>\n"]
    if law:
        lines.append("👮 <b>Правоохранители и юристы:</b>")
        for j in law:
            suffix = " (1 место)" if j["name"] in UNIQUE else ""
            lines.append(f"  • {j['name']} — {format_amount(j['salary'])} ${suffix}")
        lines.append("")
    if emergency:
        lines.append("🚒 <b>Экстренные службы:</b>")
        for j in emergency:
            lines.append(f"  • {j['name']} — {format_amount(j['salary'])} $")
        lines.append("")
    if medical:
        lines.append("🏥 <b>Медицина:</b>")
        for j in medical:
            lines.append(f"  • {j['name']} — {format_amount(j['salary'])} $")
        lines.append("")
    if criminal:
        lines.append("💀 <b>Криминал:</b>")
        for j in criminal:
            lines.append(f"  • {j['name']} — {format_amount(j['salary'])} $")
        lines.append("")
    if civilian:
        lines.append("👔 <b>Гражданские:</b>")
        for j in civilian:
            lines.append(f"  • {j['name']} — {format_amount(j['salary'])} $")
        lines.append("")
    lines.append("💡 <code>!устроиться Название</code> — подать заявку")
    lines.append("💡 Зарплату выплачивает админ после сессии: <code>!зп @users</code>")
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
    if current:
        if current["name"].lower() == job_name.lower():
            await message.reply(f"❌ Вы уже работаете \"{current['name']}\"")
            return
        await message.reply(f"❌ Вы уже работаете \"{current['name']}\". Сначала увольтесь: <code>!уволиться</code>", parse_mode="HTML")
        return
    job = await get_job_by_name(message.chat.id, job_name)
    if not job:
        await message.reply(f"❌ Профессия \"{job_name}\" не найдена. Список: <code>!работа</code>", parse_mode="HTML")
        return

    if job["name"] in ("Мэр", "Прокурор") and await is_job_taken(message.chat.id, job["name"]):
        await message.reply(f"❌ Место \"{job['name']}\" уже занято. Всего 1 вакансия.", parse_mode="HTML")
        return

    await get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name, chat_id=message.chat.id)
    req_id = await create_job_request(message.from_user.id, message.chat.id, job["id"])
    await message.reply(
        f"✅ Заявка <b>№{req_id}</b> на должность \"{job['name']}\" отправлена админам!",
        parse_mode="HTML",
    )


@router.message(Command("моя_работа", prefix="!/"))
async def cmd_my_job(message: Message):
    job = await get_user_job_info(message.from_user.id, message.chat.id)
    if not job:
        await message.reply("💼 Вы пока безработный. <code>!работа</code> — посмотреть вакансии", parse_mode="HTML")
        return
    extra = ""
    if job["name"] in DELIVERY_JOBS:
        extra = "\n🚛 <code>!доставка</code> — совершить доставку"
    await message.reply(
        f"💼 <b>Ваша профессия:</b> {job['name']}\n"
        f"💰 <b>Оклад:</b> {format_amount(job['salary'])} $\n"
        f"👑 Зарплату выплачивает админ после сессии: <code>!зп @users</code>{extra}",
        parse_mode="HTML",
    )


@router.message(Command("работы", prefix="!/"))
async def cmd_all_jobs(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    rows = await get_all_users_with_jobs(message.chat.id)
    if not rows:
        await message.reply("📭 Никто не работает")
        return
    by_job = {}
    for r in rows:
        by_job.setdefault(r["job_name"], []).append(r)
    lines = ["📋 <b>Все сотрудники:</b>\n"]
    for job_name, users in sorted(by_job.items()):
        lines.append(f"  • <b>{job_name}</b> ({users[0]['salary']} $):")
        for u in users:
            name = u["first_name"] or u["username"] or str(u["telegram_id"])
            lines.append(f"    — {name}")
        lines.append("")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("уволиться", prefix="!/"))
async def cmd_quit_job(message: Message):
    job = await get_user_job_info(message.from_user.id, message.chat.id)
    if not job:
        await message.reply("❌ Вы и так безработный")
        return
    await remove_user_job(message.from_user.id, message.chat.id)
    await message.reply(f"✅ Вы уволились с должности \"{job['name']}\"", parse_mode="HTML")


@router.message(Command("уволить", prefix="!/"))
async def cmd_fire(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!уволить @username</code>", parse_mode="HTML")
        return
    target_id, target_name, target_username, hint = await resolve_target(message, [args[1], args[1]])
    if not target_id:
        await message.reply("❌ Пользователь не найден")
        return
    job = await get_user_job_info(target_id, message.chat.id)
    if not job:
        await message.reply(f"❌ {target_name} и так безработный")
        return
    await remove_user_job(target_id, message.chat.id)
    await message.reply(f"✅ {target_name} уволен с должности \"{job['name']}\"", parse_mode="HTML")


@router.message(Command("заявки_на_работу", prefix="!/"))
async def cmd_list_requests(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    reqs = await get_pending_job_requests(message.chat.id)
    if not reqs:
        await message.reply("📭 Нет pending заявок на работу")
        return
    lines = ["📋 <b>Заявки на работу:</b>\n"]
    for r in reqs:
        lines.append(f"  <b>#{r['id']}</b> — {r['telegram_id']} → {r['job_name']} ({format_amount(r['salary'])} $)")
    lines.append("\n💡 <code>!принять_на_работу ID</code> — одобрить")
    lines.append("💡 <code>!отказать_на_работу ID</code> — отклонить")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("принять_на_работу", prefix="!/"))
async def cmd_approve_request(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!принять_на_работу ID</code>", parse_mode="HTML")
        return
    req_id = parse_amount(args[1])
    if not req_id:
        await message.reply("❌ Укажите номер заявки")
        return
    ok = await approve_job_request(req_id)
    if not ok:
        await message.reply(f"❌ Заявка #{req_id} не найдена или уже обработана")
        return
    await message.reply(f"✅ Заявка #{req_id} одобрена! Пользователь принят на работу.", parse_mode="HTML")


@router.message(Command("отказать_на_работу", prefix="!/"))
async def cmd_reject_request(message: Message):
    if message.chat.type in ("group", "supergroup") and not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Использование: <code>!отказать_на_работу ID</code>", parse_mode="HTML")
        return
    req_id = parse_amount(args[1])
    if not req_id:
        await message.reply("❌ Укажите номер заявки")
        return
    ok = await reject_job_request(req_id)
    if not ok:
        await message.reply(f"❌ Заявка #{req_id} не найдена или уже обработана")
        return
    await message.reply(f"✅ Заявка #{req_id} отклонена.", parse_mode="HTML")


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
    await message.reply(f"✅ Оклад \"{job_name}\" изменён на {format_amount(amount)} $", parse_mode="HTML")


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
                              f"Зарплата за сессию: {job['name']} — {format_amount(job['salary'])}")
        paid.append(f"{target_name} ({job['name']}) — {format_amount(job['salary'])}")

    lines = [f"💵 <b>Выплата зарплаты за сессию</b>\n"]
    if paid:
        lines.append("✅ <b>Получили:</b>")
        lines.extend(f"  • {p}" for p in paid)
    if not_found:
        lines.append(f"\n❌ <b>Не найдены/без работы:</b>")
        lines.extend(f"  • {n}" for n in not_found)
    if not paid and not not_found:
        lines.append("Нет пользователей для выплаты")
    await message.reply("\n".join(lines), parse_mode="HTML")





@router.message(Command("доставка", prefix="!/"))
async def cmd_delivery(message: Message):
    job = await get_user_job_info(message.from_user.id, message.chat.id)
    if not job:
        await message.reply("❌ У вас нет работы. <code>!работа</code> — посмотреть вакансии", parse_mode="HTML")
        return
    if job["name"] not in DELIVERY_JOBS:
        await message.reply("❌ Эта команда только для доставщиков")
        return

    now = time.time()
    last = _last_delivery.get(message.from_user.id, 0)
    if now - last < 180:
        left = int(180 - (now - last))
        await message.reply(f"⏳ Вы уже в рейсе. Вернётесь через {left} сек")
        return
    _last_delivery[message.from_user.id] = now

    origin = random.choice(DELIVERY_LOCATIONS)
    dest = random.choice([l for l in DELIVERY_LOCATIONS if l != origin])
    goods = random.choice(DELIVERY_GOODS)
    distance = random.randint(15, 180)
    weight = random.randint(500, 12000)

    lines = [
        f"🚛 <b>Доставка</b>\n",
        f"📦 <b>Груз:</b> {goods} ({weight} кг)",
        f"📍 <b>Откуда:</b> {origin}",
        f"📍 <b>Куда:</b> {dest}",
        f"🛣 <b>Расстояние:</b> {distance} миль\n",
        f"📋 Отгрузили товар, получили накладную. Выезжаем!",
    ]
    await message.reply("\n".join(lines), parse_mode="HTML")
