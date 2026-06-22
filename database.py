import os
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_FILE = "bank.db"

_is_pg = DATABASE_URL is not None
_pg_conn = None


async def get_conn():
    global _pg_conn
    if _is_pg:
        try:
            if _pg_conn is None or _pg_conn.is_closed():
                import asyncpg
                _pg_conn = await asyncpg.connect(DATABASE_URL)
            return _pg_conn
        except Exception:
            _pg_conn = None
            raise
    else:
        import aiosqlite
        db = await aiosqlite.connect(DATABASE_FILE)
        db.row_factory = aiosqlite.Row
        return db


async def close_conn():
    global _pg_conn
    if _pg_conn is not None:
        await _pg_conn.close()
        _pg_conn = None


async def init_db():
    if _is_pg:
        conn = await get_conn()
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                balance INTEGER DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                type TEXT NOT NULL,
                sender_telegram_id BIGINT,
                receiver_telegram_id BIGINT,
                amount INTEGER NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS credit_requests (
                id SERIAL PRIMARY KEY,
                user_telegram_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deposit_requests (
                id SERIAL PRIMARY KEY,
                user_telegram_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS credits (
                id SERIAL PRIMARY KEY,
                user_telegram_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                remaining_principal INTEGER NOT NULL,
                interest_rate INTEGER DEFAULT 10,
                interest_paid INTEGER DEFAULT 0,
                duration_days INTEGER DEFAULT 30,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        for col, default in (("remaining_principal", 0), ("interest_paid", 0), ("duration_days", 30)):
            try:
                await conn.execute(f"ALTER TABLE credits ADD COLUMN {col} INTEGER DEFAULT {default}")
            except Exception:
                pass
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                id SERIAL PRIMARY KEY,
                user_telegram_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                interest_rate INTEGER DEFAULT 5,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
    else:
        conn = await get_conn()
        try:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    balance INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    sender_telegram_id INTEGER,
                    receiver_telegram_id INTEGER,
                    amount INTEGER NOT NULL,
                    description TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS credit_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS deposit_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS credits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    remaining_principal INTEGER NOT NULL,
                    interest_rate INTEGER DEFAULT 10,
                    interest_paid INTEGER DEFAULT 0,
                    duration_days INTEGER DEFAULT 30,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_telegram_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    interest_rate INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
            """)
            await conn.commit()
        finally:
            await conn.close()


async def get_or_create_user(telegram_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> dict:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
            if not row:
                row = await conn.fetchrow(
                    "INSERT INTO users (telegram_id, username, first_name, balance) VALUES ($1, $2, $3, 0) RETURNING *",
                    telegram_id, username, first_name,
                )
            elif username or first_name:
                await conn.execute(
                    "UPDATE users SET username = COALESCE($1, username), first_name = COALESCE($2, first_name) WHERE telegram_id = $3",
                    username, first_name, telegram_id,
                )
                row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
            return dict(row)
        else:
            cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            user = await cursor.fetchone()
            if not user:
                await conn.execute(
                    "INSERT INTO users (telegram_id, username, first_name, balance) VALUES (?, ?, ?, 0)",
                    (telegram_id, username, first_name),
                )
                await conn.commit()
                cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
                user = await cursor.fetchone()
            elif (username and user["username"] != username) or (first_name and user["first_name"] != first_name):
                await conn.execute(
                    "UPDATE users SET username = ?, first_name = ? WHERE telegram_id = ?",
                    (username or user["username"], first_name or user["first_name"], telegram_id),
                )
                await conn.commit()
                cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
                user = await cursor.fetchone()
            return dict(user)
    finally:
        if not _is_pg:
            await conn.close()


async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        if not _is_pg:
            await conn.close()


async def get_user_by_username(username: str) -> Optional[dict]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        if not _is_pg:
            await conn.close()


async def update_balance(telegram_id: int, amount: int) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("UPDATE users SET balance = balance + $1 WHERE telegram_id = $2", amount, telegram_id)
        else:
            await conn.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (amount, telegram_id))
            await conn.commit()
    finally:
        if not _is_pg:
            await conn.close()


async def set_balance(telegram_id: int, amount: int) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("UPDATE users SET balance = $1 WHERE telegram_id = $2", amount, telegram_id)
        else:
            await conn.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (amount, telegram_id))
            await conn.commit()
    finally:
        if not _is_pg:
            await conn.close()


async def get_balance(telegram_id: int) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT balance FROM users WHERE telegram_id = $1", telegram_id)
            return row["balance"] if row else 0
        else:
            cursor = await conn.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
            row = await cursor.fetchone()
            return row["balance"] if row else 0
    finally:
        if not _is_pg:
            await conn.close()


async def add_transaction(type_: str, sender_id: Optional[int], receiver_id: Optional[int], amount: int, description: str = "") -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute(
                "INSERT INTO transactions (type, sender_telegram_id, receiver_telegram_id, amount, description) VALUES ($1, $2, $3, $4, $5)",
                type_, sender_id, receiver_id, amount, description,
            )
        else:
            await conn.execute(
                "INSERT INTO transactions (type, sender_telegram_id, receiver_telegram_id, amount, description) VALUES (?, ?, ?, ?, ?)",
                (type_, sender_id, receiver_id, amount, description),
            )
            await conn.commit()
    finally:
        if not _is_pg:
            await conn.close()


async def get_transactions(telegram_id: int, limit: int = 10) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM transactions WHERE sender_telegram_id = $1 OR receiver_telegram_id = $1 ORDER BY created_at DESC LIMIT $2",
                telegram_id, limit,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM transactions WHERE sender_telegram_id = ? OR receiver_telegram_id = ? ORDER BY created_at DESC LIMIT ?",
                (telegram_id, telegram_id, limit),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def create_credit_request(user_telegram_id: int, amount: int) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO credit_requests (user_telegram_id, amount) VALUES ($1, $2) RETURNING id",
                user_telegram_id, amount,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO credit_requests (user_telegram_id, amount) VALUES (?, ?)",
                (user_telegram_id, amount),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        if not _is_pg:
            await conn.close()


async def get_credit_requests(status: str = "pending") -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM credit_requests WHERE status = $1 ORDER BY created_at DESC", status,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM credit_requests WHERE status = ? ORDER BY created_at DESC", (status,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def get_credit_request(request_id: int) -> Optional[dict]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM credit_requests WHERE id = $1", request_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM credit_requests WHERE id = ?", (request_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        if not _is_pg:
            await conn.close()


async def update_credit_request(request_id: int, status: str) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("UPDATE credit_requests SET status = $1 WHERE id = $2", status, request_id)
        else:
            await conn.execute("UPDATE credit_requests SET status = ? WHERE id = ?", (status, request_id))
            await conn.commit()
    finally:
        if not _is_pg:
            await conn.close()


async def create_deposit_request(user_telegram_id: int, amount: int) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO deposit_requests (user_telegram_id, amount) VALUES ($1, $2) RETURNING id",
                user_telegram_id, amount,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO deposit_requests (user_telegram_id, amount) VALUES (?, ?)",
                (user_telegram_id, amount),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        if not _is_pg:
            await conn.close()


async def get_deposit_requests(status: str = "pending") -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM deposit_requests WHERE status = $1 ORDER BY created_at DESC", status,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM deposit_requests WHERE status = ? ORDER BY created_at DESC", (status,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def get_deposit_request(request_id: int) -> Optional[dict]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM deposit_requests WHERE id = $1", request_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM deposit_requests WHERE id = ?", (request_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        if not _is_pg:
            await conn.close()


async def update_deposit_request(request_id: int, status: str) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("UPDATE deposit_requests SET status = $1 WHERE id = $2", status, request_id)
        else:
            await conn.execute("UPDATE deposit_requests SET status = ? WHERE id = ?", (status, request_id))
            await conn.commit()
    finally:
        if not _is_pg:
            await conn.close()


async def create_credit(user_telegram_id: int, amount: int, interest_rate: int = 10, duration_days: int = 30) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO credits (user_telegram_id, amount, remaining_principal, interest_rate, duration_days) VALUES ($1, $2, $2, $3, $4) RETURNING id",
                user_telegram_id, amount, interest_rate, duration_days,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO credits (user_telegram_id, amount, remaining_principal, interest_rate, duration_days) VALUES (?, ?, ?, ?, ?)",
                (user_telegram_id, amount, amount, interest_rate, duration_days),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        if not _is_pg:
            await conn.close()


async def get_user_credits(user_telegram_id: int, status: str = "active") -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM credits WHERE user_telegram_id = $1 AND status = $2 ORDER BY created_at DESC",
                user_telegram_id, status,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM credits WHERE user_telegram_id = ? AND status = ? ORDER BY created_at DESC",
                (user_telegram_id, status),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def get_credit_by_id(credit_id: int) -> Optional[dict]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM credits WHERE id = $1", credit_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM credits WHERE id = ?", (credit_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        if not _is_pg:
            await conn.close()


async def repay_credit(credit_id: int, amount: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM credits WHERE id = $1 FOR UPDATE", credit_id)
            if not row or row["status"] != "active":
                return False
            credit = dict(row)
            from utils import calc_credit_debt
            debt_info = calc_credit_debt(credit)
            interest_due = debt_info["interest_due"]
            pay_interest = min(amount, interest_due)
            pay_principal = amount - pay_interest
            new_interest_paid = (credit.get("interest_paid") or 0) + pay_interest
            new_remaining = (credit.get("remaining_principal") or credit.get("remaining", credit["amount"])) - pay_principal
            if new_remaining <= 0:
                await conn.execute(
                    "UPDATE credits SET remaining_principal = 0, interest_paid = $1, status = 'paid' WHERE id = $2",
                    new_interest_paid, credit_id,
                )
            else:
                await conn.execute(
                    "UPDATE credits SET remaining_principal = $1, interest_paid = $2 WHERE id = $3",
                    new_remaining, new_interest_paid, credit_id,
                )
            return True
        else:
            cursor = await conn.execute("SELECT * FROM credits WHERE id = ?", (credit_id,))
            row = await cursor.fetchone()
            if not row or row["status"] != "active":
                return False
            credit = dict(row)
            from utils import calc_credit_debt
            debt_info = calc_credit_debt(credit)
            interest_due = debt_info["interest_due"]
            pay_interest = min(amount, interest_due)
            pay_principal = amount - pay_interest
            new_interest_paid = (credit.get("interest_paid") or 0) + pay_interest
            new_remaining = (credit.get("remaining_principal") or credit.get("remaining", credit["amount"])) - pay_principal
            if new_remaining <= 0:
                await conn.execute(
                    "UPDATE credits SET remaining_principal = 0, interest_paid = ?, status = 'paid' WHERE id = ?",
                    (new_interest_paid, credit_id),
                )
            else:
                await conn.execute(
                    "UPDATE credits SET remaining_principal = ?, interest_paid = ? WHERE id = ?",
                    (new_remaining, new_interest_paid, credit_id),
                )
            await conn.commit()
            return True
    finally:
        if not _is_pg:
            await conn.close()


async def create_deposit_account(user_telegram_id: int, amount: int, interest_rate: int = 5) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO deposits (user_telegram_id, amount, interest_rate) VALUES ($1, $2, $3) RETURNING id",
                user_telegram_id, amount, interest_rate,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO deposits (user_telegram_id, amount, interest_rate) VALUES (?, ?, ?)",
                (user_telegram_id, amount, interest_rate),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        if not _is_pg:
            await conn.close()


async def get_user_deposits(user_telegram_id: int, status: str = "active") -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM deposits WHERE user_telegram_id = $1 AND status = $2 ORDER BY created_at DESC",
                user_telegram_id, status,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM deposits WHERE user_telegram_id = ? AND status = ? ORDER BY created_at DESC",
                (user_telegram_id, status),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def get_deposit_by_id(deposit_id: int) -> Optional[dict]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM deposits WHERE id = $1", deposit_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        if not _is_pg:
            await conn.close()


async def withdraw_deposit(deposit_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM deposits WHERE id = $1 FOR UPDATE", deposit_id)
            if not row or row["status"] != "active":
                return False
            await conn.execute("UPDATE deposits SET status = 'withdrawn' WHERE id = $1", deposit_id)
            return True
        else:
            cursor = await conn.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
            row = await cursor.fetchone()
            if not row or row["status"] != "active":
                return False
            await conn.execute("UPDATE deposits SET status = 'withdrawn' WHERE id = ?", (deposit_id,))
            await conn.commit()
            return True
    finally:
        if not _is_pg:
            await conn.close()


async def get_all_credits(status: str = "active") -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM credits WHERE status = $1 ORDER BY created_at DESC", status,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM credits WHERE status = ? ORDER BY created_at DESC", (status,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def get_all_deposits(status: str = "active") -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM deposits WHERE status = $1 ORDER BY created_at DESC", status,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM deposits WHERE status = ? ORDER BY created_at DESC", (status,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def get_all_users_ranked() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM users ORDER BY balance DESC")
        else:
            cursor = await conn.execute("SELECT * FROM users ORDER BY balance DESC")
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        if not _is_pg:
            await conn.close()
