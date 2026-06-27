from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start", "help", prefix="!/"))
async def cmd_start(message: Message):
    text = (
        "╔══════════════════════════════╗\n"
        "║  🏦 <b>БАНКОВСКАЯ СИСТЕМА RP</b>  ║\n"
        "╚══════════════════════════════╝\n\n"

        "━━━ 🔹 <b>ЗАРПЛАТА</b> ━━━\n"
        "💼 <code>!моя_зп</code> — моя должность и оклад\n"
        "👤 <code>!назначить_зп @user должность сумма</code> (админ)\n"
        "💵 <code>!зп @user1 @user2 ...</code> — выплатить за сессию (админ)\n"
        "📋 <code>!список_зп</code> — штатное расписание (админ)\n\n"

        "━━━━ 🔹 <b>ДЕНЬГИ</b> ━━━━\n"
        "💳 <code>!баланс</code> — баланс\n"
        "💸 <code>!перевести @user сумма</code> — перевод\n"
        "📊 <code>!рейтинг</code> — топ\n\n"

        "━━━ 🔹 <b>КРЕДИТЫ / ВКЛАДЫ</b> ━━━\n"
        "🏦 <code>!запросить_кредит сумма</code>\n"
        "💳 <code>!кредиты</code> / 💵 <code>!погасить id сумма</code>\n"
        "📈 <code>!запросить_вклад сумма</code>\n"
        "🏧 <code>!вклады</code> / 💰 <code>!вывести id</code>\n\n"

        "━━━ 🔹 <b>АВТОМОБИЛИ</b> ━━━\n"
        "🚗 <code>!авто</code> — список\n"
        "ℹ️ <code>!авто_инфо номер</code> — инфо\n"
        "🛒 <code>!купить номер</code> / 💲 <code>!продать_авто номер</code>\n"
        "🚙 <code>!мои_авто</code> — мои авто\n\n"

        "━━━ 🔹 <b>ДОМА</b> ━━━\n"
        "🏠 <code>!дома</code> — список\n"
        "ℹ️ <code>!дом id</code> / 🏡 <code>!купить_дом id</code>\n"
        "🏘️ <code>!мои_дома</code> / 💲 <code>!продать_дом id</code>\n\n"

        "━━━━━ 🔹 <b>АДМИНАМ</b> ━━━━━\n"
        "💰 <code>!начислить</code> / <code>!списать</code> / <code>!установить_баланс</code>\n"
        "💵 <code>!стартовый_баланс [сумма]</code>\n"
        "🔄 <code>!сброс [сумма]</code> — сброс всех балансов\n"
        "🎁 <code>!выдать_стартовый</code> — стартовый баланс юзерам с 0\n"
        "👤 <code>!обновить_имена</code> / 🗑 <code>!очистить_старые</code>\n"
        "📊 <code>!статистика</code> — статистика чата\n"
        "📢 <code>!объявления</code> — настройка постинга\n"
        "🗑️ <code>!очистить_объявления</code>\n"
        "👤 <code>!авто_пользователя @user</code>\n"
        "🚫 <code>!изъять_авто id</code> / 🎁 <code>!выдать_авто @user id</code>\n\n"
        "🏠 <code>!добавить_дом</code> / <code>!удалить_дом id</code>\n"
        "✅ <code>!одобрить_кредит id % дней</code>\n"
        "❌ <code>!отклонить_кредит id</code> / <code>!отклонить_вклад id</code>\n"
        "📋 <code>!заявки</code> / <code>!все_кредиты</code> / <code>!все_вклады</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔐 <i>Админ-команды доступны только администраторам группы</i>"
    )
    await message.reply(text, parse_mode="HTML")
