import os
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_FILE = "bank.db"

_is_pg = DATABASE_URL is not None
_pg_pool = None
_start_balance_cache = None


async def get_conn():
    global _pg_pool
    if _is_pg:
        import asyncpg
        if _pg_pool is None:
            _pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        return await _pg_pool.acquire()
    else:
        import aiosqlite
        db = await aiosqlite.connect(DATABASE_FILE)
        db.row_factory = aiosqlite.Row
        return db


async def close_conn():
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None


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
                interest_rate REAL DEFAULT 1.0,
                interest_paid INTEGER DEFAULT 0,
                duration_days INTEGER DEFAULT 30,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        for col, default in (("remaining_principal", 0), ("interest_paid", 0), ("duration_days", 30), ("remaining", 0)):
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
        # Migrate interest_rate from annual INTEGER to daily REAL
        for table in ("deposits", "credits"):
            try:
                await conn.execute(f"ALTER TABLE {table} ALTER COLUMN interest_rate TYPE REAL")
            except Exception:
                pass
        try:
            await conn.execute("UPDATE deposits SET interest_rate = interest_rate / 365.0 WHERE interest_rate > 10")
        except Exception:
            pass
        try:
            await conn.execute("UPDATE credits SET interest_rate = interest_rate / 365.0 WHERE interest_rate > 30")
        except Exception:
            pass
        for col in (("chat_id", "BIGINT DEFAULT 0"),):
            try:
                await conn.execute(f"ALTER TABLE vehicles ADD COLUMN {col[0]} {col[1]}")
            except Exception:
                pass
        try:
            await seed_house_types()
        except Exception:
            pass
        try:
            await seed_neighborhoods()
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
            CREATE TABLE IF NOT EXISTS recent_posted_models (
                make TEXT NOT NULL,
                model TEXT NOT NULL,
                posted_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_recent_models_make_model
            ON recent_posted_models (make, model)
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
                chat_id BIGINT NOT NULL DEFAULT 0,
                type_name TEXT NOT NULL,
                location TEXT NOT NULL,
                neighborhood TEXT NOT NULL DEFAULT '',
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
                interest_rate REAL DEFAULT 0.5,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS house_types (
                id SERIAL PRIMARY KEY,
                type_name TEXT NOT NULL,
                bedrooms INTEGER NOT NULL,
                bathrooms REAL NOT NULL,
                sqft INTEGER NOT NULL,
                description TEXT,
                photo_url TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS neighborhoods (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        for col in (("chat_id", "BIGINT DEFAULT 0"), ("neighborhood", "TEXT DEFAULT ''"), ("house_type_id", "INTEGER"), ("neighborhood_id", "INTEGER"), ("guid", "TEXT")):
            try:
                await conn.execute(f"ALTER TABLE houses ADD COLUMN {col[0]} {col[1]}")
            except Exception:
                pass
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS job_roles (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL DEFAULT 0,
                name TEXT NOT NULL,
                salary INTEGER NOT NULL DEFAULT 0,
                UNIQUE(chat_id, name)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_jobs (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL DEFAULT 0,
                job_id INTEGER NOT NULL REFERENCES job_roles(id),
                last_payout TIMESTAMP,
                UNIQUE(telegram_id, chat_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS job_requests (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL DEFAULT 0,
                job_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("DROP TABLE IF EXISTS user_salary")
        try:
            await conn.execute("ALTER TABLE user_jobs ADD COLUMN IF NOT EXISTS last_payout TIMESTAMP")
        except Exception:
            pass
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
                    interest_rate REAL DEFAULT 1.0,
                    interest_paid INTEGER DEFAULT 0,
                    duration_days INTEGER DEFAULT 30,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS posted_listings (
                    guid TEXT PRIMARY KEY,
                    posted_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS recent_posted_models (
                    make TEXT NOT NULL,
                    model TEXT NOT NULL,
                    posted_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE INDEX IF NOT EXISTS idx_recent_models_make_model
                    ON recent_posted_models (make, model);
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
                    chat_id INTEGER NOT NULL DEFAULT 0,
                    type_name TEXT NOT NULL,
                    location TEXT NOT NULL,
                    neighborhood TEXT NOT NULL DEFAULT '',
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
                    interest_rate REAL DEFAULT 0.5,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS house_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type_name TEXT NOT NULL,
                    bedrooms INTEGER NOT NULL,
                    bathrooms REAL NOT NULL,
                    sqft INTEGER NOT NULL,
                    description TEXT,
                    photo_url TEXT
                );
                CREATE TABLE IF NOT EXISTS neighborhoods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL DEFAULT 0,
                    name TEXT NOT NULL,
                    salary INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(chat_id, name)
                );
                CREATE TABLE IF NOT EXISTS user_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL DEFAULT 0,
                    job_id INTEGER NOT NULL REFERENCES job_roles(id),
                    last_payout TEXT,
                    UNIQUE(telegram_id, chat_id)
                );
                CREATE TABLE IF NOT EXISTS job_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL DEFAULT 0,
                    job_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                DROP TABLE IF EXISTS user_salary;
            """)
            try:
                await conn.execute("ALTER TABLE user_jobs ADD COLUMN last_payout TEXT")
            except Exception:
                pass
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
            # Migration: add chat_id to vehicles
            try:
                await conn.execute("ALTER TABLE vehicles ADD COLUMN chat_id INTEGER DEFAULT 0")
                await conn.commit()
            except Exception:
                pass
            # Migration: add chat_id, neighborhood, house_type_id, neighborhood_id, guid to houses
            for col in ("chat_id INTEGER DEFAULT 0", "neighborhood TEXT DEFAULT ''", "house_type_id INTEGER", "neighborhood_id INTEGER", "guid TEXT"):
                try:
                    await conn.execute(f"ALTER TABLE houses ADD COLUMN {col}")
                    await conn.commit()
                except Exception:
                    pass
            # Seed house_types and neighborhoods
            try:
                await seed_house_types()
            except Exception:
                pass
            try:
                await seed_neighborhoods()
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
                start_balance = await get_start_balance()
                row = await conn.fetchrow(
                    "INSERT INTO users (telegram_id, username, first_name, balance, chat_id) VALUES ($1, $2, $3, $4, $5) RETURNING *",
                    telegram_id, username, first_name, start_balance, chat_id,
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
                start_balance = await get_start_balance()
                await conn.execute(
                    "INSERT INTO users (telegram_id, username, first_name, balance, chat_id) VALUES (?, ?, ?, ?, ?)",
                    (telegram_id, username, first_name, start_balance, chat_id),
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
        await conn.close()


async def clear_user_username(telegram_id: int, chat_id: int) -> None:
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE users SET username = '' WHERE telegram_id = $1 AND chat_id = $2" if _is_pg
            else "UPDATE users SET username = ? WHERE telegram_id = ? AND chat_id = ?",
            (telegram_id, chat_id) if _is_pg else ("", telegram_id, chat_id),
        )
        if not _is_pg:
            await conn.commit()
    finally:
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
        await conn.close()


async def get_user_by_username(username: str, chat_id: int = 0) -> Optional[dict]:
    conn = await get_conn()
    try:
        if _is_pg:
            if chat_id:
                row = await conn.fetchrow("SELECT * FROM users WHERE username = $1 AND chat_id = $2", username, chat_id)
            else:
                row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
            return dict(row) if row else None
        else:
            if chat_id:
                cursor = await conn.execute("SELECT * FROM users WHERE username = ? AND chat_id = ? ORDER BY id DESC", (username, chat_id))
            else:
                cursor = await conn.execute("SELECT * FROM users WHERE username = ? ORDER BY id DESC", (username,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()


async def update_balance(telegram_id: int, amount: int, chat_id: int = 0) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE telegram_id = $2 AND chat_id = $3 AND balance + $1 >= 0",
                amount, telegram_id, chat_id,
            )
            return "UPDATE 1" in (result or "")  # asyncpg returns "UPDATE N"
        else:
            cursor = await conn.execute(
                "UPDATE users SET balance = balance + ? WHERE telegram_id = ? AND chat_id = ? AND balance + ? >= 0",
                (amount, telegram_id, chat_id, amount),
            )
            await conn.commit()
            return cursor.rowcount > 0
    finally:
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
        await conn.close()


async def create_credit(user_telegram_id: int, amount: int, interest_rate: int = 10, duration_days: int = 30) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO credits (user_telegram_id, amount, remaining, remaining_principal, interest_rate, duration_days) VALUES ($1, $2, $2, $2, $3, $4) RETURNING id",
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
        await conn.close()


async def is_model_recently_posted(make: str, model: str, hours: int = 48) -> bool:
    """Check if a make+model was posted within the last N hours."""
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT 1 FROM recent_posted_models WHERE make = $1 AND model = $2 "
                "AND posted_at > to_char(NOW() - interval '1 hour' * $3, 'YYYY-MM-DD HH24:MI:SS')",
                make, model, hours,
            )
            return row is not None
        else:
            cursor = await conn.execute(
                "SELECT 1 FROM recent_posted_models WHERE make = ? AND model = ? "
                "AND posted_at > datetime('now', ?)",
                (make, model, f'-{hours} hours'),
            )
            return cursor.fetchone() is not None
    finally:
        await conn.close()


async def mark_model_posted(make: str, model: str) -> None:
    """Record that a make+model was posted now."""
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute(
                "INSERT INTO recent_posted_models (make, model) VALUES ($1, $2)",
                make, model,
            )
        else:
            await conn.execute(
                "INSERT INTO recent_posted_models (make, model) VALUES (?, ?)",
                (make, model),
            )
            await conn.commit()
    finally:
        await conn.close()


async def clean_old_model_posts(hours: int = 72) -> int:
    """Remove model post records older than N hours."""
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute(
                "DELETE FROM recent_posted_models WHERE posted_at < "
                "to_char(NOW() - interval '1 hour' * $1, 'YYYY-MM-DD HH24:MI:SS')",
                hours,
            )
            return int(result.split()[-1]) if result else 0
        else:
            cursor = await conn.execute(
                "DELETE FROM recent_posted_models WHERE posted_at < datetime('now', ?)",
                (f'-{hours} hours',),
            )
            await conn.commit()
            return cursor.rowcount
    finally:
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
        await conn.close()


async def get_start_balance() -> int:
    global _start_balance_cache
    if _start_balance_cache is not None:
        return _start_balance_cache
    raw = await get_config("start_balance")
    val = int(raw) if raw else 1000
    _start_balance_cache = val
    return val


async def set_config(key: str, value: str) -> None:
    global _start_balance_cache
    if key == "start_balance":
        _start_balance_cache = None
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
        await conn.close()


async def create_vehicle(make: str, model: str, year: int, price: int, miles: int,
                         city: str, vin: str, license_plate: str,
                         color: str = "", rarity: str = "common", chat_id: int = 0) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO vehicles (make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id",
                make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO vehicles (make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
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
        await conn.close()


async def get_available_vehicles(chat_id: int | None = None) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            if chat_id is not None:
                rows = await conn.fetch("SELECT * FROM vehicles WHERE status = 'available' AND chat_id = $1 ORDER BY created_at DESC", chat_id)
            else:
                rows = await conn.fetch("SELECT * FROM vehicles WHERE status = 'available' ORDER BY created_at DESC")
        else:
            if chat_id is not None:
                cursor = await conn.execute("SELECT * FROM vehicles WHERE status = 'available' AND chat_id = ? ORDER BY created_at DESC", (chat_id,))
            else:
                cursor = await conn.execute("SELECT * FROM vehicles WHERE status = 'available' ORDER BY created_at DESC")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_user_vehicles(telegram_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM vehicles WHERE owner_telegram_id = $1 ORDER BY id ASC", telegram_id)
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE owner_telegram_id = ? ORDER BY id ASC", (telegram_id,))
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def cleanup_orphan_vehicles() -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute("DELETE FROM vehicles WHERE chat_id = 0 AND status = 'available'")
            count = int(result.split()[-1]) if result else 0
        else:
            cursor = await conn.execute("DELETE FROM vehicles WHERE chat_id = 0 AND status = 'available'")
            await conn.commit()
            count = cursor.rowcount
        return count
    finally:
        await conn.close()


async def apply_start_balance_to_poor(chat_id: int) -> int:
    conn = await get_conn()
    try:
        start_balance = await get_start_balance()
        if _is_pg:
            result = await conn.execute(
                "UPDATE users SET balance = $1 WHERE chat_id = $2 AND balance <= 0",
                start_balance, chat_id,
            )
            count = 0
            if result and "UPDATE" in str(result):
                parts = str(result).split()
                if len(parts) >= 2 and parts[-1].isdigit():
                    count = int(parts[-1])
            return count
        else:
            cursor = await conn.execute(
                "UPDATE users SET balance = ? WHERE chat_id = ? AND balance <= 0",
                (start_balance, chat_id),
            )
            await conn.commit()
            return cursor.rowcount
    finally:
        await conn.close()


async def get_chat_stats(chat_id: int) -> dict:
    conn = await get_conn()
    try:
        if _is_pg:
            users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE chat_id = $1", chat_id)
            total_bal = await conn.fetchval("SELECT COALESCE(SUM(balance), 0) FROM users WHERE chat_id = $1", chat_id)
            cars = await conn.fetchval("SELECT COUNT(*) FROM vehicles WHERE chat_id = $1 AND status = 'available'", chat_id)
            houses = await conn.fetchval("SELECT COUNT(*) FROM houses WHERE chat_id = $1 AND status = 'available'", chat_id)
        else:
            cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE chat_id = ?", (chat_id,))
            row = await cursor.fetchone()
            users = row[0] if row else 0
            cursor = await conn.execute("SELECT COALESCE(SUM(balance), 0) FROM users WHERE chat_id = ?", (chat_id,))
            row = await cursor.fetchone()
            total_bal = row[0] if row else 0
            cursor = await conn.execute("SELECT COUNT(*) FROM vehicles WHERE chat_id = ? AND status = 'available'", (chat_id,))
            row = await cursor.fetchone()
            cars = row[0] if row else 0
            cursor = await conn.execute("SELECT COUNT(*) FROM houses WHERE chat_id = ? AND status = 'available'", (chat_id,))
            row = await cursor.fetchone()
            houses = row[0] if row else 0
        return {"users": users, "total_balance": total_bal, "available_cars": cars, "available_houses": houses}
    finally:
        await conn.close()


# ── Jobs ──────────────────────────────────────────────────

JOB_CATEGORIES = {
    # Law Enforcement
    "Мэр": "law", "Судья": "law", "Шериф": "law", "Прокурор": "law",
    "Адвокат": "law", "Заместитель шерифа": "law",
    "Офицер дорожной полиции": "law", "Полицейский": "law",
    "Городской клерк": "law",
    # Emergency
    "Пожарный": "emergency", "Фельдшер": "emergency",
    # Medical
    "Врач": "medical", "Медсестра": "medical",
    # Criminal
    "Хакер": "criminal", "Наркоторговец": "criminal",
    "Контрабандист": "criminal", "Угонщик": "criminal",
    "Вор": "criminal", "Бандит": "criminal",
}

DEFAULT_JOBS = [
    # Law Enforcement
    ("Мэр", 4000), ("Судья", 3500), ("Шериф", 3000),
    ("Прокурор", 2800), ("Адвокат", 2400),
    ("Заместитель шерифа", 2400),
    ("Офицер дорожной полиции", 2000), ("Полицейский", 1800),
    ("Городской клерк", 1500),
    # Emergency
    ("Пожарный", 2000), ("Фельдшер", 1800),
    # Medical
    ("Врач", 2500), ("Медсестра", 1600),
    # Criminal
    ("Хакер", 3000), ("Наркоторговец", 2800),
    ("Контрабандист", 2500), ("Угонщик", 2400),
    ("Вор", 2200), ("Бандит", 2000),
    # Civilian
    ("Банкир", 2800), ("Автодилер", 2000),
    ("Дальнобойщик", 1700), ("Механик", 1600),
    ("Фермер", 1500), ("Строитель", 1500),
    ("Водитель автобуса", 1400), ("Бармен", 1200),
    ("Таксист", 1200), ("Кассир", 1000),
    ("Работник заправки", 900), ("Официант", 800),
]

# (type_name, neighborhood, location, price, beds, baths, sqft, description)
DEFAULT_HOUSES = [
    ("Mobile Home", "Six Housen't", "Six Housen't, Greenville, WI", 65000, 3, 2.5, 900,
     "Самый бюджетный вариант. 3 спальни, 2.5 ванны. Построен между 1940 и 1980."),
    ("90's 2-Story House", "Lakeville", "Lakeville, Greenville, WI", 145000, 3, 2.5, 1600,
     "Двухэтажный дом среднего класса. 3 спальни, 2.5 ванны. Бильярд на втором этаже. 1987–2010."),
    ("Average Suburban House", "Greenhills", "Greenhills, Greenville, WI", 120000, 3, 2.5, 1400,
     "Стандартный пригородный дом. 3 спальни, 2.5 ванны, 5 шкафов. 1956–1982."),
    ("Modern Average Suburban House", "Greenhills", "Greenhills, Greenville, WI", 165000, 3, 2.5, 1700,
     "Современный пригородный дом на 3 спальни, 2.5 ванны. Гараж на 3 машины. 1988–2003."),
    ("Upper-Class 90's Bungalow", "Lakeville", "Lakeville, Greenville, WI", 110000, 2, 1.5, 1100,
     "Небольшой бунгало верхнего среднего класса. 2 спальни, 1.5 ванны. 1989–1998."),
    ("Average 2-Story House", "Six Housen't", "Six Housen't, Greenville, WI", 200000, 4, 3.5, 2200,
     "Двухэтажный дом в фермерском стиле. 4 спальни, 3.5 ванны. 2 гостиные, 2 столовые. 1975–1995."),
    ("Mansion #1", "Horton", "Horton, Greenville, WI", 350000, 5, 3.5, 4000,
     "Особняк! 5 спальни, 3.5 ванны. 2 гостиные, 2 столовые, огромная кухня. 1990–наши дни."),
    ("Old Farmhouse", "Farm Area", "Ферма у Visitors Sports Grill, Greenville, WI", 195000, 4, 2.5, 2500,
     "Старый фермерский дом с камином, верандой, кабинетом и отдельным гаражом на 2 машины. 1890–1945."),
    ("Lakeside Lodge", "Greenville Lake", "Greenville Lake, Greenville, WI", 480000, 4, 3.5, 3800,
     "Дом на озере с пирсом и двумя балконами. Цокольный этаж с бильярдом. Гараж отдельно. 2005–наши дни."),
    ("Average 2-Story Suburban House", "Lakeville", "Lakeville, Greenville, WI", 150000, 3, 3, 1800,
     "Пригородный двухэтажный дом. 3 спальни, 3 ванны. Кабинет, прачечная, гараж. 1965–1980."),
    ("Old Suburban House", "Horton", "Horton, Greenville, WI", 135000, 4, 4, 2000,
     "Старый пригородный дом. 4 спальни, 4 ванны. 2 гостиные, прачечная, гараж. 1920–1959."),
    ("Original 2-Story Suburban House", "Fleetwood Lane", "Fleetwood Lane, Greenville, WI", 250000, 3, 3, 1800,
     "Редчайший дом! Единственный экземпляр в игре. Оригинал из бета-версии Greenville. 1982."),
    ("Average 2-Story Suburban House #3", "Six Housen't", "Six Housen't, Greenville, WI", 155000, 3, 2.5, 1700,
     "Пригородный двухэтажный дом с гостиной, прачечной и гаражом. 1960–1980."),
    ("Mansion #2", "Horton", "Horton, Greenville, WI", 380000, 4, 3.5, 4200,
     "Второй особняк. 4 спальни, 3.5 ванны. Бильярд, фойе, гардеробная. 1990–наши дни."),
    ("Large 2-Story Suburban House", "Lakeville", "Lakeville, Greenville, WI", 210000, 3, 3, 2400,
     "Большой двухэтажный пригородный дом. 3 спальни, 3 ванны. Бильярд, лофт, веранда. 1980–2010."),
    ("Average Suburban House", "Greenhills", "Greenhills, Greenville, WI", 175000, 5, 3, 2300,
     "Просторный пригородный дом. 5 спальни, 3 ванны. Игровая зона наверху. 1990–наши дни."),
    ("Mobile Home", "Six Housen't", "Six Housen't, Greenville, WI", 40000, 1, 1, 500,
     "Маленький мобильный дом на одну спальню. Самый дешёвый вариант. 2005–наши дни."),
    ("Modern Triangle House", "Greenhills", "Greenhills, Greenville, WI", 185000, 3, 2, 1600,
     "Современный треугольный дом. 3 спальни, 2 ванны. Лофт наверху, прачечная. 2015–наши дни."),
    ("Modern House", "Lakeville", "Lakeville, Greenville, WI", 170000, 3, 2, 1500,
     "Современный дом в минималистичном стиле."),
    ("2-Story Modern House", "Greenhills", "Greenhills, Greenville, WI", 195000, 3, 2.5, 1900,
     "Двухэтажный современный дом."),
    ("Mid-Century Modern House", "Lakeville", "Lakeville, Greenville, WI", 160000, 3, 2, 1500,
     "Дом середины века в стиле модерн. Оригинал 1960–1975, реновирован в 2015."),
    ("Modern House", "Six Housen't", "Six Housen't, Greenville, WI", 165000, 3, 2, 1500,
     "Современный дом."),
    ("Cozy Rustic Suburban House", "Greenhills", "Greenhills, Greenville, WI", 190000, 3, 3, 2000,
     "Уютный деревенский пригородный дом. 3 спальни, 3 ванны. Кабинет, патио, гараж. v1.62.0."),
    ("Average Suburban Family House", "Six Housen't", "Six Housen't, Greenville, WI", 180000, 4, 3, 2200,
     "Средний семейный дом. 4 спальни, 3 ванны. Кабинет, кладовая, две веранды. v1.62.0."),
    ("Large 2-Story House", "Horton", "Horton, Greenville, WI", 230000, 3, 3, 2500,
     "Большой двухэтажный дом. 3 спальни, 3 ванны. 2 гостиные, кабинет, веранды. v1.62.0."),
    ("2-Story Suburban House", "Greenhills", "Greenhills, Greenville, WI", 200000, 4, 3, 2300,
     "Двухэтажный пригородный дом. 4 спальни, 3 ванны. Кабинет, кладовая, фойе. v1.62.0."),
    ("2-Story Farm-Style House", "Farm Area", "Ферма, Greenville, WI", 220000, 3, 3, 2400,
     "Двухэтажный фермерский дом с лофтом над гостиной. Кладовка, гараж, две веранды. 2015–наши дни."),
]


def get_job_category(job_name: str) -> str:
    return JOB_CATEGORIES.get(job_name, "civilian")


async def seed_jobs(chat_id: int) -> None:
    conn = await get_conn()
    try:
        existing = await get_all_jobs(chat_id)
        existing_names = {j["name"] for j in existing}
        new_names = {j[0] for j in DEFAULT_JOBS}

        for name, salary in DEFAULT_JOBS:
            if name in existing_names:
                continue
            if _is_pg:
                await conn.execute(
                    "INSERT INTO job_roles (chat_id, name, salary) VALUES ($1, $2, $3) "
                    "ON CONFLICT (chat_id, name) DO NOTHING",
                    chat_id, name, salary,
                )
            else:
                await conn.execute(
                    "INSERT OR IGNORE INTO job_roles (chat_id, name, salary) VALUES (?, ?, ?)",
                    (chat_id, name, salary),
                )

        orphan_names = existing_names - new_names
        if orphan_names:
            for name in orphan_names:
                if _is_pg:
                    row = await conn.fetchrow(
                        "SELECT j.id FROM job_roles j WHERE j.chat_id = $1 AND j.name = $2",
                        chat_id, name,
                    )
                else:
                    cursor = await conn.execute(
                        "SELECT j.id FROM job_roles j WHERE j.chat_id = ? AND j.name = ?",
                        (chat_id, name),
                    )
                    row = await cursor.fetchone()
                if row:
                    job_id = row["id"]
                    if _is_pg:
                        used = await conn.fetchval(
                            "SELECT 1 FROM user_jobs WHERE job_id = $1", job_id,
                        )
                    else:
                        cursor = await conn.execute(
                            "SELECT 1 FROM user_jobs WHERE job_id = ?", (job_id,),
                        )
                        used = cursor.fetchone()
                    if not used:
                        if _is_pg:
                            await conn.execute("DELETE FROM job_roles WHERE id = $1", job_id)
                        else:
                            await conn.execute("DELETE FROM job_roles WHERE id = ?", (job_id,))

        if not _is_pg:
            await conn.commit()
    finally:
        await conn.close()


async def get_all_jobs(chat_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM job_roles WHERE chat_id = $1 ORDER BY salary DESC", chat_id)
        else:
            cursor = await conn.execute("SELECT * FROM job_roles WHERE chat_id = ? ORDER BY salary DESC", (chat_id,))
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_job_by_name(chat_id: int, name: str) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM job_roles WHERE chat_id = $1 AND LOWER(name) = LOWER($2)", chat_id, name)
        else:
            cursor = await conn.execute("SELECT * FROM job_roles WHERE chat_id = ? AND LOWER(name) = LOWER(?)", (chat_id, name))
            row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def set_job_salary(chat_id: int, name: str, new_salary: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute(
                "UPDATE job_roles SET salary = $1 WHERE chat_id = $2 AND LOWER(name) = LOWER($3)",
                new_salary, chat_id, name,
            )
            return "UPDATE 1" in (result or "")
        else:
            cursor = await conn.execute("UPDATE job_roles SET salary = ? WHERE chat_id = ? AND LOWER(name) = LOWER(?)", (new_salary, chat_id, name))
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def set_user_job(telegram_id: int, chat_id: int, job_id: int) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute(
                "INSERT INTO user_jobs (telegram_id, chat_id, job_id) VALUES ($1, $2, $3) "
                "ON CONFLICT (telegram_id, chat_id) DO UPDATE SET job_id = $3",
                telegram_id, chat_id, job_id,
            )
        else:
            await conn.execute(
                "INSERT INTO user_jobs (telegram_id, chat_id, job_id) VALUES (?, ?, ?) "
                "ON CONFLICT(telegram_id, chat_id) DO UPDATE SET job_id = excluded.job_id",
                (telegram_id, chat_id, job_id),
            )
            await conn.commit()
    finally:
        await conn.close()


async def get_user_job_info(telegram_id: int, chat_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT j.* FROM user_jobs uj JOIN job_roles j ON j.id = uj.job_id WHERE uj.telegram_id = $1 AND uj.chat_id = $2",
                telegram_id, chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT j.* FROM user_jobs uj JOIN job_roles j ON j.id = uj.job_id WHERE uj.telegram_id = ? AND uj.chat_id = ?",
                (telegram_id, chat_id),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def remove_user_job(telegram_id: int, chat_id: int) -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("DELETE FROM user_jobs WHERE telegram_id = $1 AND chat_id = $2", telegram_id, chat_id)
        else:
            await conn.execute("DELETE FROM user_jobs WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id))
            await conn.commit()
    finally:
        await conn.close()


async def create_job_request(telegram_id: int, chat_id: int, job_id: int) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO job_requests (telegram_id, chat_id, job_id) VALUES ($1, $2, $3) RETURNING id",
                telegram_id, chat_id, job_id,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO job_requests (telegram_id, chat_id, job_id) VALUES (?, ?, ?)",
                (telegram_id, chat_id, job_id),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        await conn.close()


async def get_pending_job_requests(chat_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT r.*, j.name as job_name, j.salary FROM job_requests r "
                "JOIN job_roles j ON j.id = r.job_id "
                "WHERE r.chat_id = $1 AND r.status = 'pending' ORDER BY r.created_at",
                chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT r.*, j.name as job_name, j.salary FROM job_requests r "
                "JOIN job_roles j ON j.id = r.job_id "
                "WHERE r.chat_id = ? AND r.status = 'pending' ORDER BY r.created_at",
                (chat_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_job_request(request_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT r.*, j.name as job_name, j.salary FROM job_requests r "
                "JOIN job_roles j ON j.id = r.job_id WHERE r.id = $1", request_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT r.*, j.name as job_name, j.salary FROM job_requests r "
                "JOIN job_roles j ON j.id = r.job_id WHERE r.id = ?", (request_id,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


UNIQUE_JOBS = {"Мэр", "Прокурор"}

async def approve_job_request(request_id: int) -> bool:
    conn = await get_conn()
    try:
        req = await get_job_request(request_id)
        if not req or req["status"] != "pending":
            return False

        if req["job_name"] in UNIQUE_JOBS:
            existing = await get_job_holder_info(req["chat_id"], req["job_name"])
            if existing:
                return False

        if _is_pg:
            await conn.execute(
                "DELETE FROM user_jobs WHERE telegram_id = $1 AND chat_id = $2",
                req["telegram_id"], req["chat_id"],
            )
            await conn.execute(
                "INSERT INTO user_jobs (telegram_id, chat_id, job_id) VALUES ($1, $2, $3)",
                req["telegram_id"], req["chat_id"], req["job_id"],
            )
            await conn.execute("UPDATE job_requests SET status = 'approved' WHERE id = $1", request_id)
        else:
            await conn.execute("DELETE FROM user_jobs WHERE telegram_id = ? AND chat_id = ?",
                               (req["telegram_id"], req["chat_id"]))
            await conn.execute("INSERT INTO user_jobs (telegram_id, chat_id, job_id) VALUES (?, ?, ?)",
                               (req["telegram_id"], req["chat_id"], req["job_id"]))
            await conn.execute("UPDATE job_requests SET status = 'approved' WHERE id = ?", (request_id,))
            await conn.commit()
        return True
    finally:
        await conn.close()


# ── Player-to-player vehicle marketplace ────────────────────

async def list_vehicle_for_sale(vehicle_id: int, telegram_id: int, price: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' FOR UPDATE",
                vehicle_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET status = 'player_listed', price = $1 WHERE id = $2",
                price, vehicle_id,
            )
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND owner_telegram_id = ? AND status = 'sold'",
                (vehicle_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET status = 'player_listed', price = ? WHERE id = ?",
                (price, vehicle_id),
            )
            await conn.commit()
            return True
    finally:
        await conn.close()


async def unlist_vehicle(vehicle_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND owner_telegram_id = $2 AND status = 'player_listed' FOR UPDATE",
                vehicle_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET status = 'sold' WHERE id = $1", vehicle_id,
            )
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND owner_telegram_id = ? AND status = 'player_listed'",
                (vehicle_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET status = 'sold' WHERE id = ?", (vehicle_id,),
            )
            await conn.commit()
            return True
    finally:
        await conn.close()


async def buy_player_vehicle(vehicle_id: int, buyer_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND status = 'player_listed' FOR UPDATE",
                vehicle_id,
            )
            if not row:
                return False
            seller_id = row["owner_telegram_id"]
            price = row["price"]
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = $1, status = 'sold' WHERE id = $2",
                buyer_id, vehicle_id,
            )
            return seller_id, price
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND status = 'player_listed'", (vehicle_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            seller_id = row["owner_telegram_id"]
            price = row["price"]
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = ?, status = 'sold' WHERE id = ?",
                (buyer_id, vehicle_id),
            )
            await conn.commit()
            return seller_id, price
    finally:
        await conn.close()


async def get_player_listed_vehicles(chat_id: int = 0) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM vehicles WHERE status = 'player_listed' ORDER BY created_at DESC",
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE status = 'player_listed' ORDER BY created_at DESC",
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def reject_job_request(request_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute("UPDATE job_requests SET status = 'rejected' WHERE id = $1 AND status = 'pending'", request_id)
            return "UPDATE 1" in (result or "")
        else:
            cursor = await conn.execute("UPDATE job_requests SET status = 'rejected' WHERE id = ? AND status = 'pending'", (request_id,))
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def is_job_taken(chat_id: int, job_name: str) -> bool:
    conn = await get_conn()
    try:
        job_id_q = "SELECT id FROM job_roles WHERE chat_id = $1 AND name = $2" if _is_pg else \
                   "SELECT id FROM job_roles WHERE chat_id = ? AND name = ?"
        if _is_pg:
            row = await conn.fetchrow(job_id_q, chat_id, job_name)
        else:
            cursor = await conn.execute(job_id_q, (chat_id, job_name))
            row = await cursor.fetchone()
        if not row:
            return False
        job_id = row["id"]
        if _is_pg:
            r = await conn.fetchrow(
                "SELECT 1 FROM user_jobs WHERE chat_id = $1 AND job_id = $2", chat_id, job_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT 1 FROM user_jobs WHERE chat_id = ? AND job_id = ?", (chat_id, job_id),
            )
            r = await cursor.fetchone()
        return r is not None
    finally:
        await conn.close()


async def get_job_holder_info(chat_id: int, job_name: str) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT uj.*, j.name as job_name, j.salary FROM user_jobs uj "
                "JOIN job_roles j ON j.id = uj.job_id "
                "WHERE uj.chat_id = $1 AND j.name = $2", chat_id, job_name,
            )
        else:
            cursor = await conn.execute(
                "SELECT uj.*, j.name as job_name, j.salary FROM user_jobs uj "
                "JOIN job_roles j ON j.id = uj.job_id "
                "WHERE uj.chat_id = ? AND j.name = ?", (chat_id, job_name),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_all_users_with_jobs(chat_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT u.telegram_id, u.username, u.first_name, "
                "j.name as job_name, j.salary "
                "FROM user_jobs uj "
                "JOIN job_roles j ON j.id = uj.job_id "
                "JOIN users u ON u.telegram_id = uj.telegram_id AND u.chat_id = uj.chat_id "
                "WHERE uj.chat_id = $1 ORDER BY j.name", chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT u.telegram_id, u.username, u.first_name, "
                "j.name as job_name, j.salary "
                "FROM user_jobs uj "
                "JOIN job_roles j ON j.id = uj.job_id "
                "JOIN users u ON u.telegram_id = uj.telegram_id AND u.chat_id = uj.chat_id "
                "WHERE uj.chat_id = ? ORDER BY j.name", (chat_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ── Vehicle ───────────────────────────────────────────────

async def get_vehicle_by_position(chat_id: int, position: int) -> dict | None:
    vehicles = await get_available_vehicles(chat_id=chat_id)
    if position < 1 or position > len(vehicles):
        return None
    return vehicles[position - 1]


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
        await conn.close()


async def get_all_owned_vehicles() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM vehicles WHERE owner_telegram_id IS NOT NULL ORDER BY id ASC")
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE owner_telegram_id IS NOT NULL ORDER BY id ASC")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
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
        await conn.close()


async def clear_user_vehicles(telegram_id: int) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = NULL, status = 'available' WHERE owner_telegram_id = $1",
                telegram_id,
            )
            return result.split()[-1] if hasattr(result, 'split') else 0
        else:
            cursor = await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = NULL, status = 'available' WHERE owner_telegram_id = ?",
                (telegram_id,),
            )
            await conn.commit()
            return cursor.rowcount
    finally:
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
        await conn.close()


# ── House types (27 wiki styles) ────────────────────────────

HOUSE_TYPES = [
    (1, "Mobile Home", 3, 2.5, 900, "Самый бюджетный вариант. 3 спальни, 2.5 ванны. Построен между 1940 и 1980."),
    (2, "90's 2-Story House", 3, 2.5, 1600, "Двухэтажный дом среднего класса. 3 спальни, 2.5 ванны. Бильярд на втором этаже. 1987–2010."),
    (3, "Average Suburban House", 3, 2.5, 1400, "Стандартный пригородный дом. 3 спальни, 2.5 ванны, 5 шкафов. 1956–1982."),
    (4, "Modern Average Suburban House", 3, 2.5, 1700, "Современный пригородный дом на 3 спальни, 2.5 ванны. Гараж на 3 машины. 1988–2003."),
    (5, "Upper-Class 90's Bungalow", 2, 1.5, 1100, "Небольшое бунгало. 2 спальни, 1.5 ванны. 1989–1998."),
    (6, "Average 2-Story House", 4, 3.5, 2200, "Двухэтажный дом в фермерском стиле. 4 спальни, 3.5 ванны. 1975–1995."),
    (7, "Mansion #1", 5, 3.5, 4000, "Особняк! 5 спален, 3.5 ванны. 2 гостиные, 2 столовые, огромная кухня. 1990–наши дни."),
    (8, "Old Farmhouse", 4, 2.5, 2500, "Старый фермерский дом с камином, верандой, кабинетом и гаражом. 1890–1945."),
    (9, "Lakeside Lodge", 4, 3.5, 3800, "Дом на озере с пирсом и балконами. Цокольный этаж с бильярдом. 2005–наши дни."),
    (10, "Average 2-Story Suburban House", 3, 3.0, 1800, "Пригородный двухэтажный дом. 3 спальни, 3 ванны. 1965–1980."),
    (11, "Old Suburban House", 4, 4.0, 2000, "Старый пригородный дом. 4 спальни, 4 ванны. 1920–1959."),
    (12, "Original 2-Story Suburban House", 3, 3.0, 1800, "Редчайший дом! Оригинал из бета-версии Greenville. 1982."),
    (13, "Average 2-Story Suburban House #3", 3, 2.5, 1700, "Пригородный двухэтажный дом с гостиной, прачечной и гаражом. 1960–1980."),
    (14, "Mansion #2", 4, 3.5, 4200, "Второй особняк. 4 спальни, 3.5 ванны. Бильярд, фойе, гардеробная. 1990–наши дни."),
    (15, "Large 2-Story Suburban House", 3, 3.0, 2400, "Большой двухэтажный пригородный дом. 3 спальни, 3 ванны. 1980–2010."),
    (16, "Average Suburban House", 5, 3.0, 2300, "Просторный пригородный дом. 5 спален, 3 ванны. 1990–наши дни."),
    (17, "Mobile Home", 1, 1.0, 500, "Маленький мобильный дом на одну спальню. Самый дешёвый вариант. 2005–наши дни."),
    (18, "Modern Triangle House", 3, 2.0, 1600, "Современный треугольный дом. 3 спальни, 2 ванны. 2015–наши дни."),
    (19, "Modern House", 3, 2.0, 1500, "Современный дом в минималистичном стиле."),
    (20, "2-Story Modern House", 3, 2.5, 1900, "Двухэтажный современный дом."),
    (21, "Mid-Century Modern House", 3, 2.0, 1500, "Дом середины века в стиле модерн. 1960–1975, реновирован в 2015."),
    (22, "Modern House", 3, 2.0, 1500, "Современный дом."),
    (23, "Cozy Rustic Suburban House", 3, 3.0, 2000, "Уютный деревенский пригородный дом. 3 спальни, 3 ванны. v1.62.0."),
    (24, "Average Suburban Family House", 4, 3.0, 2200, "Средний семейный дом. 4 спальни, 3 ванны. v1.62.0."),
    (25, "Large 2-Story House", 3, 3.0, 2500, "Большой двухэтажный дом. 3 спальни, 3 ванны. v1.62.0."),
    (26, "2-Story Suburban House", 4, 3.0, 2300, "Двухэтажный пригородный дом. 4 спальни, 3 ванны. v1.62.0."),
    (27, "2-Story Farm-Style House", 3, 3.0, 2400, "Двухэтажный фермерский дом с лофтом над гостиной. 2015–наши дни."),
]

HOUSE_PRICES = [65000, 145000, 120000, 165000, 110000, 200000, 350000, 195000, 480000,
                150000, 135000, 250000, 155000, 380000, 210000, 175000, 40000, 185000,
                170000, 195000, 160000, 165000, 190000, 180000, 230000, 200000, 220000]

NEIGHBORHOODS = ["Six Housen't", "Lakeville", "Greenhills", "Horton", "Farm Area", "Greenville Lake", "Fleetwood Lane"]

# Which house types are available in which neighborhoods (0-indexed neighborhood IDs)
HOUSE_TYPE_NEIGHBORHOODS = {
    1: [0], 2: [1], 3: [2], 4: [2], 5: [1], 6: [0, 1],
    7: [0, 1, 2, 3, 4, 5, 6],  # Mansion #1 — все районы
    8: [4], 9: [5], 10: [0, 1], 11: [3], 12: [6], 13: [0],
    14: [3], 15: [1], 16: [2, 3], 17: [0], 18: [2],
    19: [1, 2], 20: [2], 21: [1], 22: [0], 23: [2],
    24: [0], 25: [3], 26: [2], 27: [4],
}


async def seed_house_types() -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            existing = await conn.fetchval("SELECT COUNT(*) FROM house_types")
        else:
            cursor = await conn.execute("SELECT COUNT(*) FROM house_types")
            row = await cursor.fetchone()
            existing = row[0] if row else 0
        if existing:
            return
        for ht in HOUSE_TYPES:
            hid, name, beds, baths, sqft, desc = ht
            if _is_pg:
                await conn.execute(
                    "INSERT INTO house_types (id, type_name, bedrooms, bathrooms, sqft, description) VALUES ($1,$2,$3,$4,$5,$6)",
                    hid, name, beds, baths, sqft, desc,
                )
            else:
                await conn.execute(
                    "INSERT INTO house_types (id, type_name, bedrooms, bathrooms, sqft, description) VALUES (?,?,?,?,?,?)",
                    (hid, name, beds, baths, sqft, desc),
                )
        if not _is_pg:
            await conn.commit()
    finally:
        await conn.close()


async def seed_neighborhoods() -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            existing = await conn.fetchval("SELECT COUNT(*) FROM neighborhoods")
        else:
            cursor = await conn.execute("SELECT COUNT(*) FROM neighborhoods")
            row = await cursor.fetchone()
            existing = row[0] if row else 0
        if existing:
            return
        for i, name in enumerate(NEIGHBORHOODS, 1):
            if _is_pg:
                await conn.execute(
                    "INSERT INTO neighborhoods (id, name) VALUES ($1, $2)", i, name,
                )
            else:
                await conn.execute(
                    "INSERT INTO neighborhoods (id, name) VALUES (?, ?)", (i, name),
                )
        if not _is_pg:
            await conn.commit()
    finally:
        await conn.close()


async def get_house_type(house_type_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM house_types WHERE id = $1", house_type_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM house_types WHERE id = ?", (house_type_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()


async def get_all_house_types() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM house_types ORDER BY id")
        else:
            cursor = await conn.execute("SELECT * FROM house_types ORDER BY id")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_neighborhood(neighborhood_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM neighborhoods WHERE id = $1", neighborhood_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM neighborhoods WHERE id = ?", (neighborhood_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()


async def get_all_neighborhoods() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM neighborhoods ORDER BY id")
        else:
            cursor = await conn.execute("SELECT * FROM neighborhoods ORDER BY id")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_available_houses_by_neighborhood(chat_id: int, neighborhood_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM houses WHERE chat_id = $1 AND status = 'available' AND neighborhood_id = $2 ORDER BY created_at DESC",
                chat_id, neighborhood_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE chat_id = ? AND status = 'available' AND neighborhood_id = ? ORDER BY created_at DESC",
                (chat_id, neighborhood_id),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def create_house_listing(chat_id: int, house_type_id: int, neighborhood_id: int, price: int, guid: str) -> int:
    ht = await get_house_type(house_type_id)
    nb = await get_neighborhood(neighborhood_id)
    if not ht or not nb:
        raise ValueError("Invalid house_type_id or neighborhood_id")
    conn = await get_conn()
    try:
        loc = f"{nb['name']}, Greenville, WI"
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO houses (chat_id, house_type_id, neighborhood_id, guid, type_name, neighborhood, location, price, bedrooms, bathrooms, sqft, description) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING id",
                chat_id, house_type_id, neighborhood_id, guid,
                ht["type_name"], nb["name"], loc, price,
                ht["bedrooms"], ht["bathrooms"], ht["sqft"], ht["description"],
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO houses (chat_id, house_type_id, neighborhood_id, guid, type_name, neighborhood, location, price, bedrooms, bathrooms, sqft, description) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (chat_id, house_type_id, neighborhood_id, guid,
                 ht["type_name"], nb["name"], loc, price,
                 ht["bedrooms"], ht["bathrooms"], ht["sqft"], ht["description"]),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        await conn.close()


# ── Player-to-player house marketplace ─────────────────────

async def list_house_for_sale(house_id: int, telegram_id: int, price: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' FOR UPDATE",
                house_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE houses SET status = 'player_listed', price = $1 WHERE id = $2",
                price, house_id,
            )
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE id = ? AND owner_telegram_id = ? AND status = 'sold'",
                (house_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE houses SET status = 'player_listed', price = ? WHERE id = ?",
                (price, house_id),
            )
            await conn.commit()
            return True
    finally:
        await conn.close()


async def unlist_house(house_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE id = $1 AND owner_telegram_id = $2 AND status = 'player_listed' FOR UPDATE",
                house_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute("UPDATE houses SET status = 'sold' WHERE id = $1", house_id)
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE id = ? AND owner_telegram_id = ? AND status = 'player_listed'",
                (house_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE houses SET status = 'sold' WHERE id = ?", (house_id,))
            await conn.commit()
            return True
    finally:
        await conn.close()


async def buy_player_house(house_id: int, buyer_id: int):
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE id = $1 AND status = 'player_listed' FOR UPDATE",
                house_id,
            )
            if not row:
                return False
            seller_id = row["owner_telegram_id"]
            price = row["price"]
            await conn.execute(
                "UPDATE houses SET owner_telegram_id = $1, status = 'sold' WHERE id = $2",
                buyer_id, house_id,
            )
            return seller_id, price
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE id = ? AND status = 'player_listed'", (house_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            seller_id = row["owner_telegram_id"]
            price = row["price"]
            await conn.execute(
                "UPDATE houses SET owner_telegram_id = ?, status = 'sold' WHERE id = ?",
                (buyer_id, house_id),
            )
            await conn.commit()
            return seller_id, price
    finally:
        await conn.close()


async def get_player_listed_houses() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM houses WHERE status = 'player_listed' ORDER BY created_at DESC")
        else:
            cursor = await conn.execute("SELECT * FROM houses WHERE status = 'player_listed' ORDER BY created_at DESC")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def seed_houses(chat_id: int) -> None:
    conn = await get_conn()
    try:
        existing = await get_available_houses(chat_id)
        if existing:
            return
        for h in DEFAULT_HOUSES:
            type_name, neighborhood, location, price, beds, baths, sqft, desc = h
            if _is_pg:
                await conn.execute(
                    "INSERT INTO houses (chat_id, type_name, location, neighborhood, price, bedrooms, bathrooms, sqft, description) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                    chat_id, type_name, location, neighborhood, price, beds, baths, sqft, desc,
                )
            else:
                await conn.execute(
                    "INSERT INTO houses (chat_id, type_name, location, neighborhood, price, bedrooms, bathrooms, sqft, description) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (chat_id, type_name, location, neighborhood, price, beds, baths, sqft, desc),
                )
        if not _is_pg:
            await conn.commit()
    finally:
        await conn.close()


async def create_house(chat_id: int, type_name: str, neighborhood: str, location: str, price: int,
                       bedrooms: int, bathrooms: float, sqft: int, description: str = "") -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO houses (chat_id, type_name, location, neighborhood, price, bedrooms, bathrooms, sqft, description) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id",
                chat_id, type_name, location, neighborhood, price, bedrooms, bathrooms, sqft, description,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO houses (chat_id, type_name, location, neighborhood, price, bedrooms, bathrooms, sqft, description) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (chat_id, type_name, location, neighborhood, price, bedrooms, bathrooms, sqft, description),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
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
        await conn.close()


async def get_available_houses(chat_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM houses WHERE chat_id = $1 AND status = 'available' ORDER BY created_at DESC", chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE chat_id = ? AND status = 'available' ORDER BY created_at DESC", (chat_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_user_houses(telegram_id: int, chat_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM houses WHERE owner_telegram_id = $1 AND chat_id = $2 ORDER BY created_at DESC",
                telegram_id, chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE owner_telegram_id = ? AND chat_id = ? ORDER BY created_at DESC",
                (telegram_id, chat_id),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
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
        await conn.close()


async def reset_all_balances(chat_id: int | None = None, new_balance: int = 0) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            if chat_id is not None:
                result = await conn.execute("UPDATE users SET balance = $1 WHERE chat_id = $2", new_balance, chat_id)
            else:
                result = await conn.execute("UPDATE users SET balance = $1", new_balance)
            return int(result.split()[-1]) if result else 0
        else:
            if chat_id is not None:
                cursor = await conn.execute("UPDATE users SET balance = ? WHERE chat_id = ?", (new_balance, chat_id))
            else:
                cursor = await conn.execute("UPDATE users SET balance = ?", (new_balance,))
            await conn.commit()
            return cursor.rowcount
    finally:
        await conn.close()
