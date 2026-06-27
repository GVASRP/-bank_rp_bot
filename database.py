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
        for col, default in (("color", "''"), ("rarity", "'common'")):
            try:
                await conn.execute(f"ALTER TABLE vehicles ADD COLUMN {col} TEXT DEFAULT {default}")
            except Exception:
                pass
        for col in (("chat_id", "BIGINT DEFAULT 0"),):
            try:
                await conn.execute(f"ALTER TABLE users ADD COLUMN {col[0]} {col[1]}")
            except Exception:
                pass
        # Remove old UNIQUE on telegram_id, add composite UNIQUE for per-group balances
        for cname in ["users_telegram_id_key", "uq_users_telegram_id"]:
            try:
                await conn.execute(f"ALTER TABLE users DROP CONSTRAINT IF EXISTS {cname}")
            except Exception:
                pass
        try:
            await conn.execute("ALTER TABLE users ADD UNIQUE (telegram_id, chat_id)")
        except Exception:
            pass
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_listings (
                guid TEXT PRIMARY KEY,
                posted_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
        )
""")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id SERIAL PRIMARY KEY,
                make TEXT NOT NULL,
                model TEXT NOT NULL,
                year INTEGER NOT NULL,
                price INTEGER NOT NULL,
                miles INTEGER NOT NULL,
                city TEXT NOT NULL,
                vin TEXT NOT NULL,
                license_plate TEXT NOT NULL,
                color TEXT DEFAULT '',
                rarity TEXT DEFAULT 'common',
                owner_telegram_id BIGINT,
                status TEXT DEFAULT 'available',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS houses (
                id SERIAL PRIMARY KEY,
                type_name TEXT NOT NULL,
                location TEXT NOT NULL,
                price INTEGER NOT NULL,
                bedrooms INTEGER NOT NULL,
                bathrooms REAL NOT NULL,
                sqft INTEGER NOT NULL,
                description TEXT,
                photo_url TEXT,
                owner_telegram_id BIGINT,
                status TEXT DEFAULT 'available',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
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
                    telegram_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    balance INTEGER DEFAULT 0,
                    chat_id INTEGER DEFAULT 0
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
                CREATE TABLE IF NOT EXISTS posted_listings (
                    guid TEXT PRIMARY KEY,
                    posted_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vehicles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    make TEXT NOT NULL,
                    model TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    price INTEGER NOT NULL,
                    miles INTEGER NOT NULL,
                    city TEXT NOT NULL,
                    vin TEXT NOT NULL,
                    license_plate TEXT NOT NULL,
                    color TEXT DEFAULT '',
                    rarity TEXT DEFAULT 'common',
                    owner_telegram_id INTEGER,
                    status TEXT DEFAULT 'available',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS houses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type_name TEXT NOT NULL,
                    location TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    bedrooms INTEGER NOT NULL,
                    bathrooms REAL NOT NULL,
                    sqft INTEGER NOT NULL,
                    description TEXT,
                    photo_url TEXT,
                    owner_telegram_id INTEGER,
                    status TEXT DEFAULT 'available',
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
            # Migration: add chat_id column if missing
            try:
                await conn.execute("ALTER TABLE users ADD COLUMN chat_id INTEGER DEFAULT 0")
            except Exception:
                pass
            # Remove old UNIQUE constraint on telegram_id by recreating table
            cursor = await conn.execute("SELECT COUNT(*) FROM pragma_index_list('users') WHERE name LIKE 'sqlite_autoindex%'")
            row = await cursor.fetchone()
            if row and row[0] > 0:
                await conn.executescript("""
                    CREATE TABLE users_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        balance INTEGER DEFAULT 0,
                        chat_id INTEGER DEFAULT 0
                    );
                    INSERT INTO users_new (id, telegram_id, username, first_name, balance, chat_id)
                        SELECT id, telegram_id, username, first_name, balance, COALESCE(chat_id, 0) FROM users;
                    DROP TABLE users;
                    ALTER TABLE users_new RENAME TO users;
                """)
                await conn.commit()
            # Create unique index for per-group users
            try:
                await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_telegram_chat ON users(telegram_id, chat_id)")
                await conn.commit()
            except Exception:
                pass
        finally:
            await conn.close()


async def get_or_create_user(telegram_id: int, username: Optional[str] = None, first_name: Optional[str] = None, chat_id: int = 0) -> dict:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1 AND chat_id = $2", telegram_id, chat_id)
            if not row:
                row = await conn.fetchrow(
                    "INSERT INTO users (telegram_id, username, first_name, balance, chat_id) VALUES ($1, $2, $3, 0, $4) RETURNING *",
                    telegram_id, username, first_name, chat_id,
                )
            elif username or first_name:
                await conn.execute(
                    "UPDATE users SET username = COALESCE($1, username), first_name = COALESCE($2, first_name) WHERE telegram_id = $3 AND chat_id = $4",
                    username, first_name, telegram_id, chat_id,
                )
                row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1 AND chat_id = $2", telegram_id, chat_id)
            return dict(row)
        else:
            cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id))
            user = await cursor.fetchone()
            if not user:
                await conn.execute(
                    "INSERT INTO users (telegram_id, username, first_name, balance, chat_id) VALUES (?, ?, ?, 0, ?)",
                    (telegram_id, username, first_name, chat_id),
                )
                await conn.commit()
                cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id))
                user = await cursor.fetchone()
            elif (username and user["username"] != username) or (first_name and user["first_name"] != first_name):
                await conn.execute(
                    "UPDATE users SET username = ?, first_name = ? WHERE telegram_id = ? AND chat_id = ?",
                    (username or user["username"], first_name or user["first_name"], telegram_id, chat_id),
                )
                await conn.commit()
                cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id))
                user = await cursor.fetchone()
            return dict(user)
    finally:
        if not _is_pg:
            await conn.close()


async def get_user_by_telegram_id(telegram_id: int, chat_id: int = 0) -> Optional[dict]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1 AND chat_id = $2", telegram_id, chat_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id))
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


async def update_balance(telegram_id: int, amount: int, chat_id: int = 0) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("UPDATE users SET balance = balance + $1 WHERE telegram_id = $2 AND chat_id = $3", amount, telegram_id, chat_id)
        else:
            await conn.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ? AND chat_id = ?", (amount, telegram_id, chat_id))
            await conn.commit()
    finally:
        if not _is_pg:
            await conn.close()


async def set_balance(telegram_id: int, amount: int, chat_id: int = 0) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("UPDATE users SET balance = $1 WHERE telegram_id = $2 AND chat_id = $3", amount, telegram_id, chat_id)
        else:
            await conn.execute("UPDATE users SET balance = ? WHERE telegram_id = ? AND chat_id = ?", (amount, telegram_id, chat_id))
            await conn.commit()
    finally:
        if not _is_pg:
            await conn.close()


async def get_balance(telegram_id: int, chat_id: int = 0) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT balance FROM users WHERE telegram_id = $1 AND chat_id = $2", telegram_id, chat_id)
            return row["balance"] if row else 0
        else:
            cursor = await conn.execute("SELECT balance FROM users WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id))
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


async def is_listing_posted(guid: str) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT 1 FROM posted_listings WHERE guid = $1", guid)
            return row is not None
        else:
            cursor = await conn.execute("SELECT 1 FROM posted_listings WHERE guid = ?", (guid,))
            return cursor.fetchone() is not None
    finally:
        if not _is_pg:
            await conn.close()


async def mark_listing_posted(guid: str) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("INSERT INTO posted_listings (guid) VALUES ($1) ON CONFLICT DO NOTHING", guid)
        else:
            await conn.execute("INSERT OR IGNORE INTO posted_listings (guid) VALUES (?)", (guid,))
            await conn.commit()
    finally:
        if not _is_pg:
            await conn.close()


async def clear_posted_listings() -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute("DELETE FROM posted_listings")
            return int(result.split()[-1]) if result else 0
        else:
            cursor = await conn.execute("DELETE FROM posted_listings")
            await conn.commit()
            return cursor.rowcount
    finally:
        if not _is_pg:
            await conn.close()


async def clear_available_vehicles() -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute("DELETE FROM vehicles WHERE status = 'available'")
            return int(result.split()[-1]) if result else 0
        else:
            cursor = await conn.execute("DELETE FROM vehicles WHERE status = 'available'")
            await conn.commit()
            return cursor.rowcount
    finally:
        if not _is_pg:
            await conn.close()


async def get_config(key: str) -> str | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT value FROM config WHERE key = $1", key)
            return row["value"] if row else None
        else:
            cursor = await conn.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row["value"] if row else None
    finally:
        if not _is_pg:
            await conn.close()


async def set_config(key: str, value: str) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute(
                "INSERT INTO config (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
                key, value,
            )
        else:
            await conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
            await conn.commit()
    finally:
        if not _is_pg:
            await conn.close()


async def create_vehicle(make: str, model: str, year: int, price: int, miles: int,
                         city: str, vin: str, license_plate: str,
                         color: str = "", rarity: str = "common") -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO vehicles (make, model, year, price, miles, city, vin, license_plate, color, rarity) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id",
                make, model, year, price, miles, city, vin, license_plate, color, rarity,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO vehicles (make, model, year, price, miles, city, vin, license_plate, color, rarity) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (make, model, year, price, miles, city, vin, license_plate, color, rarity),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        if not _is_pg:
            await conn.close()


async def get_vehicle(vehicle_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1", vehicle_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        if not _is_pg:
            await conn.close()


async def get_available_vehicles() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM vehicles WHERE status = 'available' ORDER BY created_at DESC")
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE status = 'available' ORDER BY created_at DESC")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def get_user_vehicles(telegram_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM vehicles WHERE owner_telegram_id = $1 ORDER BY created_at DESC", telegram_id)
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE owner_telegram_id = ? ORDER BY created_at DESC", (telegram_id,))
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def buy_vehicle(vehicle_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1 AND status = 'available' FOR UPDATE", vehicle_id)
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = $1, status = 'sold' WHERE id = $2", telegram_id, vehicle_id)
            return True
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE id = ? AND status = 'available'", (vehicle_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = ?, status = 'sold' WHERE id = ?", (telegram_id, vehicle_id))
            await conn.commit()
            return True
    finally:
        if not _is_pg:
            await conn.close()


async def sell_vehicle(vehicle_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' FOR UPDATE",
                vehicle_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, status = 'available' WHERE id = $1", vehicle_id)
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND owner_telegram_id = ? AND status = 'sold'", (vehicle_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, status = 'available' WHERE id = ?", (vehicle_id,))
            await conn.commit()
            return True
    finally:
        if not _is_pg:
            await conn.close()


async def get_all_vehicles_by_owner(telegram_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM vehicles WHERE owner_telegram_id = $1 ORDER BY created_at DESC", telegram_id)
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE owner_telegram_id = ? ORDER BY created_at DESC", (telegram_id,))
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def admin_take_vehicle(vehicle_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1 AND status = 'sold' FOR UPDATE", vehicle_id)
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, status = 'available' WHERE id = $1", vehicle_id)
            return True
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE id = ? AND status = 'sold'", (vehicle_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, status = 'available' WHERE id = ?", (vehicle_id,))
            await conn.commit()
            return True
    finally:
        if not _is_pg:
            await conn.close()


async def admin_give_vehicle(vehicle_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1 AND status = 'available' FOR UPDATE", vehicle_id)
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = $1, status = 'sold' WHERE id = $2", telegram_id, vehicle_id)
            return True
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE id = ? AND status = 'available'", (vehicle_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = ?, status = 'sold' WHERE id = ?", (telegram_id, vehicle_id))
            await conn.commit()
            return True
    finally:
        if not _is_pg:
            await conn.close()


async def create_house(type_name: str, location: str, price: int, bedrooms: int,
                       bathrooms: float, sqft: int, description: str = "", photo_url: str = "") -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO houses (type_name, location, price, bedrooms, bathrooms, sqft, description, photo_url) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id",
                type_name, location, price, bedrooms, bathrooms, sqft, description, photo_url,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO houses (type_name, location, price, bedrooms, bathrooms, sqft, description, photo_url) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (type_name, location, price, bedrooms, bathrooms, sqft, description, photo_url),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        if not _is_pg:
            await conn.close()


async def get_house(house_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM houses WHERE id = $1", house_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM houses WHERE id = ?", (house_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        if not _is_pg:
            await conn.close()


async def get_available_houses() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM houses WHERE status = 'available' ORDER BY created_at DESC")
        else:
            cursor = await conn.execute("SELECT * FROM houses WHERE status = 'available' ORDER BY created_at DESC")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def get_user_houses(telegram_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM houses WHERE owner_telegram_id = $1 ORDER BY created_at DESC", telegram_id)
        else:
            cursor = await conn.execute("SELECT * FROM houses WHERE owner_telegram_id = ? ORDER BY created_at DESC", (telegram_id,))
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        if not _is_pg:
            await conn.close()


async def buy_house(house_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM houses WHERE id = $1 AND status = 'available' FOR UPDATE", house_id)
            if not row:
                return False
            await conn.execute("UPDATE houses SET owner_telegram_id = $1, status = 'sold' WHERE id = $2", telegram_id, house_id)
            return True
        else:
            cursor = await conn.execute("SELECT * FROM houses WHERE id = ? AND status = 'available'", (house_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE houses SET owner_telegram_id = ?, status = 'sold' WHERE id = ?", (telegram_id, house_id))
            await conn.commit()
            return True
    finally:
        if not _is_pg:
            await conn.close()


async def sell_house(house_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' FOR UPDATE",
                house_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute("UPDATE houses SET owner_telegram_id = NULL, status = 'available' WHERE id = $1", house_id)
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE id = ? AND owner_telegram_id = ? AND status = 'sold'", (house_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE houses SET owner_telegram_id = NULL, status = 'available' WHERE id = ?", (house_id,))
            await conn.commit()
            return True
    finally:
        if not _is_pg:
            await conn.close()


async def delete_house(house_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM houses WHERE id = $1 FOR UPDATE", house_id)
            if not row:
                return False
            await conn.execute("DELETE FROM houses WHERE id = $1", house_id)
            return True
        else:
            cursor = await conn.execute("SELECT * FROM houses WHERE id = ?", (house_id,))
            if not cursor.fetchone():
                return False
            await conn.execute("DELETE FROM houses WHERE id = ?", (house_id,))
            await conn.commit()
            return True
    finally:
        if not _is_pg:
            await conn.close()


async def get_all_users_ranked(chat_id: int | None = None) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            if chat_id is not None:
                rows = await conn.fetch("SELECT * FROM users WHERE chat_id = $1 ORDER BY balance DESC", chat_id)
            else:
                rows = await conn.fetch("SELECT * FROM users ORDER BY balance DESC")
        else:
            if chat_id is not None:
                cursor = await conn.execute("SELECT * FROM users WHERE chat_id = ? ORDER BY balance DESC", (chat_id,))
            else:
                cursor = await conn.execute("SELECT * FROM users ORDER BY balance DESC")
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        if not _is_pg:
            await conn.close()
