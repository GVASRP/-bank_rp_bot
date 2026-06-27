from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import random
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
    is_mayor_taken,
    update_balance,
    add_transaction,
)
from database import get_job_category
from utils import format_amount, parse_amount, is_admin, resolve_target

router = Router()

LAW_CATEGORIES = {"law", "legal", "government"}
CRIME_CATEGORIES = {"criminal"}

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
_last_crime = {}


@router.message(Command("работа", prefix="!/"))
async def cmd_jobs(message: Message):
    await seed_jobs(message.chat.id)
    jobs = await get_all_jobs(message.chat.id)
    if not jobs:
        await message.reply("📭 Нет доступных профессий")
        return
    civilian = []
    law = []
    medical = []
    emergency = []
    criminal = []
    for j in jobs:
        cat = get_job_category(j["name"])
        if cat == "law" or cat == "legal" or cat == "government":
            law.append(j)
        elif cat == "medical":
            medical.append(j)
        elif cat == "emergency":
            emergency.append(j)
        elif cat == "criminal":
            criminal.append(j)
        else:
            civilian.append(j)

    lines = ["💼 <b>Доступные профессии:</b>\n"]
    if civilian:
        lines.append("👔 <b>Гражданские:</b>")
        for j in civilian:
            lines.append(f"  • {j['name']} — {format_amount(j['salary'])} $")
        lines.append("")
    if law:
        lines.append("👮 <b>Правоохранители и юристы:</b>")
        for j in law:
            lines.append(f"  • {j['name']} — {format_amount(j['salary'])} $")
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
    if current and current["name"].lower() == job_name.lower():
        await message.reply(f"❌ Вы уже работаете \"{current['name']}\"")
        return
    job = await get_job_by_name(message.chat.id, job_name)
    if not job:
        await message.reply(f"❌ Профессия \"{job_name}\" не найдена. Список: <code>!работа</code>", parse_mode="HTML")
        return

    if job["name"] == "Мэр":
        taken = await is_mayor_taken(message.chat.id)
        if taken:
            await message.reply("❌ Должность мэра уже занята. Дождитесь, пока текущий мэр покинет пост.")
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
    cat = get_job_category(job["name"])
    extra = ""
    if cat in CRIME_CATEGORIES:
        extra = "\n💀 <code>!дело</code> — провернуть криминальное дело (в сессии)"
    elif cat in LAW_CATEGORIES:
        extra = "\n🔍 <code>!расследование</code> — провести расследование (в сессии)"
    if job["name"] == "Дальнобойщик":
        extra = "\n🚛 <code>!доставка</code> — совершить доставку между организациями"
    await message.reply(
        f"💼 <b>Ваша профессия:</b> {job['name']}\n"
        f"💰 <b>Оклад:</b> {format_amount(job['salary'])} $\n"
        f"👑 Зарплату выплачивает админ после сессии: <code>!зп @users</code>{extra}",
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


@router.message(Command("дело", prefix="!/"))
async def cmd_crime(message: Message):
    job = await get_user_job_info(message.from_user.id, message.chat.id)
    if not job:
        await message.reply("❌ У вас нет работы. <code>!работа</code> — посмотреть вакансии", parse_mode="HTML")
        return
    cat = get_job_category(job["name"])
    if cat not in CRIME_CATEGORIES:
        await message.reply("❌ Эта команда только для криминальных профессий")
        return

    now = time.time()
    last = _last_crime.get(message.from_user.id, 0)
    if now - last < 120:
        left = int(120 - (now - last))
        await message.reply(f"⏳ Подождите {left} сек перед следующим делом")
        return
    _last_crime[message.from_user.id] = now

    crime_scenarios = [
        f"Вы проникли в банк Wisconsin Trust через подвал. Взломали сейф и забрали наличные.",
        f"Угнали BMW (BKM) с парковки у Walmart. Тачку уже разобрали на запчасти в порту.",
        f"Перехватили груз фур на трассе I-41. Товар перегрузили на склад №12.",
        f"Взломали сервер мэрии Гринвилл и скачали закрытые документы. Продали информацию.",
        f"Организовали подпольное казино в отеле Greenville Inn. Налёт принёс прибыль.",
        f"Переправили контрабанду через Порт Гринвилл. Таможня ничего не заметила.",
        f"Обчистили дом мэра на Озёрной улице. Забрали украшения и наличку.",
        f"Напоили охранника на заправке BP и украли кассу.",
    ]

    roll = random.randint(1, 100)
    success = roll <= 50
    scenario = random.choice(crime_scenarios)
    lines = [f"💀 <b>Криминальное дело</b>\n"]
    lines.append(f"📋 {scenario}")
    if success:
        lines.append(f"\n✅ <b>Успех!</b> Вы остались незамеченным.")
    else:
        lines.append(f"\n❌ <b>Провал!</b> Пришлось заметать следы. В этот раз не вышло.")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("расследование", prefix="!/"))
async def cmd_investigate(message: Message):
    job = await get_user_job_info(message.from_user.id, message.chat.id)
    if not job:
        await message.reply("❌ У вас нет работы. <code>!работа</code> — посмотреть вакансии", parse_mode="HTML")
        return
    cat = get_job_category(job["name"])
    if cat not in LAW_CATEGORIES:
        await message.reply("❌ Эта команда только для правоохранителей и юристов")
        return

    invest_scenarios = [
        f"Осмотрели место преступления на складе №12. Нашли отпечатки и гильзы.",
        f"Допросили свидетелей у ресторана \"У озера\". Кто-то видел подозрительный фургон.",
        f"Проверили камеры у банка Wisconsin Trust. Засветился угнанный пикап Durant.",
        f"Устроили облаву в порту Гринвилл. Изъяли партию контрабанды.",
        f"Проанализировали цифровые следы — хакер оставил лог на сервере мэрии.",
        f"Проверили алиби подозреваемого. Он был в баре — чисто.",
        f"Нашли схрон оружия в лесу за фермой Джонсона.",
        f"Закрыли подпольную мастерскую по перебивке VIN-номеров.",
    ]
    outcome_scenarios = [
        f"Преступник задержан и передан в суд!",
        f"Улики собраны, дело готово к передаче прокурору.",
        f"Обвиняемый сознался под давлением улик.",
        f"Судья вынес приговор — преступник отправлен в тюрьму.",
    ]

    roll = random.randint(1, 100)
    success = roll <= 55
    scenario = random.choice(invest_scenarios)
    outcome = random.choice(outcome_scenarios)
    lines = [f"🔍 <b>Расследование</b>\n"]
    lines.append(f"📋 {scenario}")
    if success:
        lines.append(f"\n✅ {outcome}")
    else:
        lines.append(f"\n❌ Недостаточно улик. Дело приостановлено.")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("доставка", prefix="!/"))
async def cmd_delivery(message: Message):
    job = await get_user_job_info(message.from_user.id, message.chat.id)
    if not job:
        await message.reply("❌ У вас нет работы. <code>!работа</code> — посмотреть вакансии", parse_mode="HTML")
        return
    if job["name"] != "Дальнобойщик":
        await message.reply("❌ Эта команда только для дальнобойщиков")
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
