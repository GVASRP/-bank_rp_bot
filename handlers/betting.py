from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_or_create_user, get_user_by_telegram_id, update_balance, add_transaction,
    create_betting_event, get_betting_event, get_active_betting_events,
    set_betting_event_status, add_betting_option, get_betting_options,
    set_winning_option, place_bet, settle_betting_event,
    get_event_bets_by_user, get_betting_history,
    get_all_event_bets, delete_bet, cancel_bet,
)
from utils import format_amount, is_admin, get_user_mention

router = Router()


def format_event(ev: dict) -> str:
    status_icon = {"open": "🟢", "closed": "🔴", "settled": "✅"}
    return f"{status_icon.get(ev['status'], '❓')} <b>#{ev['id']} {ev['title']}</b> — {ev['status']}"


@router.message(Command("ставки", prefix="!/"))
async def cmd_betting(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    args = message.text.split(maxsplit=2)
    chat_id = message.chat.id
    is_adm = await is_admin(message.bot, chat_id, message.from_user.id)

    if len(args) >= 2:
        action = args[1].lower()

        # ── создать ──
        if action == "создать":
            if not is_adm:
                await message.reply("❌ Только для администраторов")
                return
            title = args[2] if len(args) >= 3 else None
            if not title:
                await message.reply("❌ Использование: <code>!ставки создать НАЗВАНИЕ [комиссия%]</code>", parse_mode="HTML")
                return
            parts = title.rsplit(maxsplit=1)
            comm = 5
            if len(parts) == 2 and parts[1].lstrip("-").isdigit():
                comm = max(0, min(50, int(parts[1])))
                title = parts[0]
            eid = await create_betting_event(chat_id, title, comm)
            await message.reply(
                f"✅ Событие <b>#{eid}</b> создано!\n"
                f"📌 <b>{title}</b>\n"
                f"📊 Комиссия: {comm}%\n"
                f"➕ Добавьте исходы: <code>!ставки исход {eid} НАЗВАНИЕ</code>",
                parse_mode="HTML",
            )
            return

        # ── исход ──
        if action == "исход":
            if not is_adm:
                await message.reply("❌ Только для администраторов")
                return
            parts = message.text.split(maxsplit=3)
            if len(parts) < 4:
                await message.reply("❌ Использование: <code>!ставки исход ID_СОБЫТИЯ НАЗВАНИЕ</code>", parse_mode="HTML")
                return
            try:
                eid = int(parts[2])
            except ValueError:
                await message.reply("❌ ID события должен быть числом")
                return
            label = parts[3]
            ev = await get_betting_event(eid)
            if not ev or ev["chat_id"] != chat_id:
                await message.reply("❌ Событие не найдено")
                return
            oid = await add_betting_option(eid, label)
            await message.reply(f"✅ Исход <b>#{oid} {label}</b> добавлен к <b>{ev['title']}</b>", parse_mode="HTML")
            return

        # ── закрыть ──
        if action == "закрыть":
            if not is_adm:
                await message.reply("❌ Только для администраторов")
                return
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                await message.reply("❌ Использование: <code>!ставки закрыть ID_СОБЫТИЯ</code>", parse_mode="HTML")
                return
            try:
                eid = int(parts[2])
            except ValueError:
                await message.reply("❌ ID события должен быть числом")
                return
            ev = await get_betting_event(eid)
            if not ev or ev["chat_id"] != chat_id:
                await message.reply("❌ Событие не найдено")
                return
            if ev["status"] != "open":
                await message.reply("❌ Событие уже закрыто или рассчитано")
                return
            await set_betting_event_status(eid, "closed")
            await message.reply(f"🔴 Приём ставок на <b>{ev['title']}</b> закрыт", parse_mode="HTML")
            return

        # ── результат ──
        if action == "результат":
            if not is_adm:
                await message.reply("❌ Только для администраторов")
                return
            parts = message.text.split(maxsplit=3)
            if len(parts) < 4:
                await message.reply("❌ Использование: <code>!ставки результат ID_СОБЫТИЯ ID_ИСХОДА</code>", parse_mode="HTML")
                return
            try:
                eid = int(parts[2])
                oid = int(parts[3])
            except ValueError:
                await message.reply("❌ ID события и исхода должны быть числами")
                return
            ev = await get_betting_event(eid)
            if not ev or ev["chat_id"] != chat_id:
                await message.reply("❌ Событие не найдено")
                return
            ok = await set_winning_option(eid, oid)
            if not ok:
                await message.reply("❌ Исход не найден в этом событии")
                return
            opts = await get_betting_options(eid)
            winner = next((o for o in opts if o["id"] == oid), None)
            await message.reply(f"✅ Победитель: <b>{winner['label']}</b>\n💸 <code>!ставки выплатить {eid}</code> — выплатить", parse_mode="HTML")
            return

        # ── выплатить ──
        if action == "выплатить":
            if not is_adm:
                await message.reply("❌ Только для администраторов")
                return
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                await message.reply("❌ Использование: <code>!ставки выплатить ID_СОБЫТИЯ</code>", parse_mode="HTML")
                return
            try:
                eid = int(parts[2])
            except ValueError:
                await message.reply("❌ ID события должен быть числом")
                return
            result = await settle_betting_event(eid)
            if not result["ok"]:
                await message.reply(f"❌ {result['error']}")
                return
            lines = [
                f"💰 <b>Выплата по событию #{eid}</b>",
                f"💵 Общий пул: ${result['total_pool']:,}",
                f"🎰 Призовой фонд (x9): ${result['prize_pool']:,}",
                f"👑 Победителей: {len(result['payouts'])}",
            ]
            if result["payouts"]:
                total_win = sum(p["amount"] for p in result["payouts"])
                avg = total_win // len(result["payouts"])
                lines.append(f"💎 Выплачено всего: ${total_win:,} (среднее ${avg:,})")
            await message.reply("\n".join(lines), parse_mode="HTML")
            return

        # ── список ──
        if action == "список":
            if not is_adm:
                await message.reply("❌ Только для администраторов")
                return
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                await message.reply("❌ Использование: <code>!ставки список ID_СОБЫТИЯ</code>", parse_mode="HTML")
                return
            try:
                eid = int(parts[2])
            except ValueError:
                await message.reply("❌ ID события должен быть числом")
                return
            ev = await get_betting_event(eid)
            if not ev or ev["chat_id"] != chat_id:
                await message.reply("❌ Событие не найдено")
                return
            all_bets = await get_all_event_bets(eid)
            if not all_bets:
                await message.reply(f"📭 На событие <b>{ev['title']}</b> нет ставок", parse_mode="HTML")
                return
            lines = [f"📋 <b>Ставки на: {ev['title']}</b> (всего {len(all_bets)})\n"]
            for b in all_bets:
                lines.append(
                    f"<b>#{b['id']}</b> | "
                    f"id{get_user_mention(b['user_id'], str(b['user_id']))} | "
                    f"{b['label']} | ${b['amount']:,}"
                )
            await message.reply("\n".join(lines), parse_mode="HTML")
            return

        # ── кто ──
        if action == "кто":
            if not is_adm:
                await message.reply("❌ Только для администраторов")
                return
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                await message.reply("❌ Использование: <code>!ставки кто ID_СОБЫТИЯ</code>", parse_mode="HTML")
                return
            try:
                eid = int(parts[2])
            except ValueError:
                await message.reply("❌ ID события должен быть числом")
                return
            ev = await get_betting_event(eid)
            if not ev or ev["chat_id"] != chat_id:
                await message.reply("❌ Событие не найдено")
                return
            all_bets = await get_all_event_bets(eid)
            if not all_bets:
                await message.reply(f"📭 На событие <b>{ev['title']}</b> нет ставок", parse_mode="HTML")
                return
            opts = await get_betting_options(eid)
            lines = [f"📋 <b>{ev['title']}</b> (всего ставок: {len(all_bets)})\n"]
            for o in opts:
                o_bets = [b for b in all_bets if b["option_id"] == o["id"]]
                if not o_bets:
                    continue
                total = sum(b["amount"] for b in o_bets)
                lines.append(f"━━ <b>{o['label']}</b> — ${total:,} ({(total*100)//(sum(b['amount'] for b in all_bets) or 1)}%)")
                for b in o_bets:
                    lines.append(f"  <b>#{b['id']}</b> id{get_user_mention(b['user_id'], str(b['user_id']))} | ${b['amount']:,}")
                lines.append("")
            await message.reply("\n".join(lines), parse_mode="HTML")
            return

        # ── удалить ──
        if action == "удалить":
            if not is_adm:
                await message.reply("❌ Только для администраторов")
                return
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                await message.reply("❌ Использование: <code>!ставки удалить ID_СТАВКИ</code>", parse_mode="HTML")
                return
            try:
                bid = int(parts[2])
            except ValueError:
                await message.reply("❌ ID ставки должен быть числом")
                return
            ok = await delete_bet(bid)
            if not ok:
                await message.reply("❌ Ставка не найдена")
                return
            await message.reply(f"✅ Ставка <b>#{bid}</b> удалена (без возврата)", parse_mode="HTML")
            return

    # ── Список активных событий ──
    events = await get_active_betting_events(chat_id)
    if not events:
        await message.reply(
            "🏟 <b>Ставки на спорт</b>\n\n"
            "Нет активных событий. Ждите новых заездов!\n\n"
            "━━ <b>Команды админа:</b> ━━\n"
            "<code>!ставки создать НАЗВАНИЕ [комиссия%]</code>\n"
            "<code>!ставки исход ID НАЗВАНИЕ</code>\n"
            "<code>!ставки закрыть ID</code>\n"
            "<code>!ставки результат ID ID_ИСХОДА</code>\n"
            "<code>!ставки выплатить ID</code>\n"
            "<code>!ставки список ID</code> — все ставки\n"
            "<code>!ставки кто ID</code> — ставки по исходам\n"
            "<code>!ставки удалить ID</code> — удалить ставку без возврата",
            parse_mode="HTML",
        )
        return

    lines = ["🏟 <b>Ставки на спорт</b>\n"]
    for ev in events:
        opts = await get_betting_options(ev["id"])
        opt_lines = []
        total_bets = 0
        for o in opts:
            bets_list = await get_event_bets_by_user(ev["id"], 0)  # won't use
            total_bets += 1
            winner_mark = "👑" if o.get("is_winner") or o.get("is_winner") == 1 else ""
            opt_lines.append(f"  {winner_mark}#{o['id']} — {o['label']}")
        lines.append(f"{format_event(ev)}")
        lines.extend(opt_lines)
        lines.append(f"  📊 Исходов: {len(opts)}")
        lines.append("")
    lines.append("━━ <b>Как играть</b> ━━")
    lines.append("🎯 <code>!ставка ID_СОБЫТИЯ ID_ИСХОДА СУММА</code> — сделать ставку")
    lines.append("↩️ <code>!отменить_ставку ID</code> — отменить свою ставку")
    lines.append("📊 Общий пул ×9, делится пропорционально ставке")
    lines.append("━━ <b>Админ:</b> ━━")
    lines.append("👁 <code>!ставки кто ID</code> — кто на что поставил")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("отменить_ставку", prefix="!/"))
async def cmd_cancel_bet(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Использование: <code>!отменить_ставку ID</code>", parse_mode="HTML")
        return
    try:
        bid = int(parts[1])
    except ValueError:
        await message.reply("❌ ID ставки должен быть числом")
        return
    result = await cancel_bet(bid, message.from_user.id)
    if not result["ok"]:
        await message.reply(f"❌ {result['error']}")
        return
    await message.reply(
        f"✅ Ставка <b>#{bid}</b> отменена\n"
        f"🏟 {result['title']}\n"
        f"💰 ${result['amount']:,} возвращены на баланс",
        parse_mode="HTML",
    )


@router.message(Command("удалить_ставку", prefix="!/"))
async def cmd_delete_bet(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Только для администраторов")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Использование: <code>!удалить_ставку ID</code>", parse_mode="HTML")
        return
    try:
        bid = int(parts[1])
    except ValueError:
        await message.reply("❌ ID ставки должен быть числом")
        return
    ok = await delete_bet(bid)
    if not ok:
        await message.reply("❌ Ставка не найдена")
        return
    await message.reply(f"✅ Ставка <b>#{bid}</b> удалена (без возврата)", parse_mode="HTML")


@router.message(Command("ставка", prefix="!/"))
async def cmd_place_bet(message: Message):
    await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "", message.chat.id)
    parts = message.text.split()
    if len(parts) < 4:
        await message.reply("❌ Использование: <code>!ставка ID_СОБЫТИЯ ID_ИСХОДА СУММА</code>", parse_mode="HTML")
        return
    try:
        eid = int(parts[1])
        oid = int(parts[2])
        amount = int(parts[3])
    except ValueError:
        await message.reply("❌ ID и сумма должны быть числами")
        return
    if amount < 1:
        await message.reply("❌ Сумма должна быть положительной")
        return

    ev = await get_betting_event(eid)
    if not ev or ev["chat_id"] != message.chat.id:
        await message.reply("❌ Событие не найдено")
        return
    if ev["status"] != "open":
        await message.reply("❌ Приём ставок на это событие закрыт")
        return

    opts = await get_betting_options(eid)
    if not any(o["id"] == oid for o in opts):
        await message.reply("❌ Исход не найден")
        return

    user_balance = await get_user_by_telegram_id(message.from_user.id, message.chat.id)
    balance = user_balance["balance"] if user_balance else 0
    if balance < amount:
        await message.reply(f"❌ Недостаточно средств. Баланс: {format_amount(balance)}", parse_mode="HTML")
        return

    ok, err = await place_bet(eid, oid, message.from_user.id, amount)
    if not ok:
        await message.reply(err)
        return

    await update_balance(message.from_user.id, -amount, message.chat.id)
    opt = next(o for o in opts if o["id"] == oid)
    await add_transaction("bet", None, message.from_user.id, -amount,
                          f"Ставка на {ev['title']}: {opt['label']} (${amount:,})")
    await message.reply(
        f"✅ Ставка принята!\n"
        f"🏟 <b>{ev['title']}</b>\n"
        f"🎯 {opt['label']}\n"
        f"💰 Сумма: ${amount:,}",
        parse_mode="HTML",
    )
