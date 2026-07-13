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
        try:
            await conn.execute("ALTER TABLE credit_requests ADD COLUMN vehicle_id INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await conn.execute("ALTER TABLE credits ADD COLUMN vehicle_id INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await conn.execute("ALTER TABLE deposits ADD COLUMN duration_days INTEGER DEFAULT 30")
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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                owner_telegram_id BIGINT NOT NULL,
                balance INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS org_members (
                id SERIAL PRIMARY KEY,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                telegram_id BIGINT NOT NULL,
                role TEXT DEFAULT 'member'
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_org_members_org ON org_members (org_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members (telegram_id)
        """)
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
        for col in (("rent_price", "INTEGER DEFAULT 0"), ("tenant_telegram_id", "BIGINT"), ("rent_paid_at", "TEXT"), ("rent_missed_days", "INTEGER DEFAULT 0")):
            try:
                await conn.execute(f"ALTER TABLE vehicles ADD COLUMN {col[0]} {col[1]}")
            except Exception:
                pass
        try:
            await conn.execute("ALTER TABLE vehicles ADD COLUMN vehicle_type TEXT DEFAULT 'car'")
        except Exception:
            pass
        try:
            await conn.execute("ALTER TABLE vehicles ADD COLUMN org_id BIGINT DEFAULT NULL")
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
        try:
            await seed_businesses()
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
                org_id BIGINT DEFAULT NULL,
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
                org_id BIGINT DEFAULT NULL,
                status TEXT DEFAULT 'available',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS business_types (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                min_price INTEGER NOT NULL DEFAULT 0,
                max_price INTEGER NOT NULL DEFAULT 0,
                base_profit INTEGER NOT NULL DEFAULT 0,
                description TEXT DEFAULT ''
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL DEFAULT 0,
                business_type_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                price INTEGER NOT NULL,
                profit INTEGER NOT NULL DEFAULT 0,
                owner_telegram_id BIGINT,
                org_id BIGINT DEFAULT NULL,
                status TEXT DEFAULT 'available',
                manager_telegram_id BIGINT,
                last_delivery TEXT,
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
        for col in (("chat_id", "BIGINT DEFAULT 0"), ("neighborhood", "TEXT DEFAULT ''"), ("house_type_id", "INTEGER"), ("neighborhood_id", "INTEGER"), ("guid", "TEXT"), ("rent_price", "INTEGER DEFAULT 0"), ("tenant_telegram_id", "BIGINT"), ("rent_paid_at", "TEXT"), ("rent_missed_days", "INTEGER DEFAULT 0")):
            try:
                await conn.execute(f"ALTER TABLE houses ADD COLUMN {col[0]} {col[1]}")
            except Exception:
                pass
        try:
            await conn.execute("ALTER TABLE houses ADD COLUMN org_id BIGINT DEFAULT NULL")
        except Exception:
            pass
        for col, default in (("delivery_count", 0), ("total_profit_earned", 0), ("materials", 0), ("max_materials", 100), ("materials_cost", 0), ("total_customers", 0), ("manager_salary", 0), ("pending_supplies", 0)):
            try:
                await conn.execute(f"ALTER TABLE businesses ADD COLUMN {col} INTEGER DEFAULT {default}")
            except Exception:
                pass
        for col in ("is_open",):
            try:
                await conn.execute(f"ALTER TABLE businesses ADD COLUMN {col} TEXT DEFAULT '1'")
            except Exception:
                pass
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS betting_events (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL DEFAULT 0,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                commission_pct INTEGER DEFAULT 5,
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
                settled_at TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS betting_options (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES betting_events(id),
                label TEXT NOT NULL,
                is_winner BOOLEAN DEFAULT FALSE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES betting_events(id),
                option_id INTEGER NOT NULL REFERENCES betting_options(id),
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS insurance (
                id SERIAL PRIMARY KEY,
                vehicle_id INTEGER NOT NULL,
                owner_telegram_id BIGINT NOT NULL,
                coverage_type TEXT DEFAULT 'standard',
                coverage_percent INTEGER NOT NULL DEFAULT 80,
                premium_paid INTEGER NOT NULL DEFAULT 0,
                vehicle_value INTEGER NOT NULL DEFAULT 0,
                start_date TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
                end_date TEXT,
                status TEXT DEFAULT 'active'
            )
        """)
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
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    vehicle_id INTEGER DEFAULT 0
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
                    org_id INTEGER DEFAULT NULL,
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
                    org_id INTEGER DEFAULT NULL,
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
                CREATE TABLE IF NOT EXISTS organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    owner_telegram_id INTEGER NOT NULL,
                    balance INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS org_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL REFERENCES organizations(id),
                    telegram_id INTEGER NOT NULL,
                    role TEXT DEFAULT 'member'
                );
                CREATE INDEX IF NOT EXISTS idx_org_members_org ON org_members (org_id);
                CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members (telegram_id);
                DROP TABLE IF EXISTS user_salary;
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS business_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    min_price INTEGER NOT NULL DEFAULT 0,
                    max_price INTEGER NOT NULL DEFAULT 0,
                    base_profit INTEGER NOT NULL DEFAULT 0,
                    description TEXT DEFAULT ''
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS businesses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL DEFAULT 0,
                    business_type_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    location TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    profit INTEGER NOT NULL DEFAULT 0,
                    owner_telegram_id INTEGER,
                    org_id INTEGER DEFAULT NULL,
                    status TEXT DEFAULT 'available',
                    manager_telegram_id INTEGER,
                    last_delivery TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS betting_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL DEFAULT 0,
                    title TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    commission_pct INTEGER DEFAULT 5,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    settled_at TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS betting_options (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    is_winner INTEGER DEFAULT 0
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    option_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS insurance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL,
                    owner_telegram_id INTEGER NOT NULL,
                    coverage_type TEXT DEFAULT 'standard',
                    coverage_percent INTEGER NOT NULL DEFAULT 80,
                    premium_paid INTEGER NOT NULL DEFAULT 0,
                    vehicle_value INTEGER NOT NULL DEFAULT 0,
                    start_date TEXT DEFAULT (datetime('now', 'localtime')),
                    end_date TEXT,
                    status TEXT DEFAULT 'active'
                )
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
            # Migration: add chat_id, rent columns to vehicles
            for col in ("chat_id INTEGER DEFAULT 0", "rent_price INTEGER DEFAULT 0", "tenant_telegram_id INTEGER", "rent_paid_at TEXT", "rent_missed_days INTEGER DEFAULT 0"):
                try:
                    await conn.execute(f"ALTER TABLE vehicles ADD COLUMN {col}")
                    await conn.commit()
                except Exception:
                    pass
            try:
                await conn.execute("ALTER TABLE vehicles ADD COLUMN vehicle_type TEXT DEFAULT 'car'")
                await conn.commit()
            except Exception:
                    pass
            try:
                await conn.execute("ALTER TABLE vehicles ADD COLUMN org_id INTEGER DEFAULT NULL")
                await conn.commit()
            except Exception:
                pass
            # Migration: add chat_id, neighborhood, house_type_id, neighborhood_id, guid, rent columns to houses
            for col in ("chat_id INTEGER DEFAULT 0", "neighborhood TEXT DEFAULT ''", "house_type_id INTEGER", "neighborhood_id INTEGER", "guid TEXT", "rent_price INTEGER DEFAULT 0", "tenant_telegram_id INTEGER", "rent_paid_at TEXT", "rent_missed_days INTEGER DEFAULT 0", "org_id INTEGER DEFAULT NULL"):
                try:
                    await conn.execute(f"ALTER TABLE houses ADD COLUMN {col}")
                    await conn.commit()
                except Exception:
                    pass
            for col in ("delivery_count INTEGER DEFAULT 0", "total_profit_earned INTEGER DEFAULT 0",
                         "materials INTEGER DEFAULT 0", "max_materials INTEGER DEFAULT 100",
                         "materials_cost INTEGER DEFAULT 0", "total_customers INTEGER DEFAULT 0",
                         "manager_salary INTEGER DEFAULT 0", "pending_supplies INTEGER DEFAULT 0",
                         "is_open TEXT DEFAULT '1'"):
                try:
                    await conn.execute(f"ALTER TABLE businesses ADD COLUMN {col}")
                    await conn.commit()
                except Exception:
                    pass
            # Migration: add duration_days to deposits
            try:
                await conn.execute("ALTER TABLE deposits ADD COLUMN duration_days INTEGER DEFAULT 30")
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
            try:
                await seed_businesses()
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


async def create_credit_request(user_telegram_id: int, amount: int, vehicle_id: int = 0) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO credit_requests (user_telegram_id, amount, vehicle_id) VALUES ($1, $2, $3) RETURNING id",
                user_telegram_id, amount, vehicle_id,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO credit_requests (user_telegram_id, amount, vehicle_id) VALUES (?, ?, ?)",
                (user_telegram_id, amount, vehicle_id),
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


async def create_credit(user_telegram_id: int, amount: int, interest_rate: int = 10, duration_days: int = 30, vehicle_id: int = 0) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO credits (user_telegram_id, amount, remaining, remaining_principal, interest_rate, duration_days, vehicle_id) VALUES ($1, $2, $2, $2, $3, $4, $5) RETURNING id",
                user_telegram_id, amount, interest_rate, duration_days, vehicle_id,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO credits (user_telegram_id, amount, remaining_principal, interest_rate, duration_days, vehicle_id) VALUES (?, ?, ?, ?, ?, ?)",
                (user_telegram_id, amount, amount, interest_rate, duration_days, vehicle_id),
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


async def create_deposit_account(user_telegram_id: int, amount: int, interest_rate: int = 5, duration_days: int = 30) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO deposits (user_telegram_id, amount, interest_rate, duration_days) VALUES ($1, $2, $3, $4) RETURNING id",
                user_telegram_id, amount, interest_rate, duration_days,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO deposits (user_telegram_id, amount, interest_rate, duration_days) VALUES (?, ?, ?, ?)",
                (user_telegram_id, amount, interest_rate, duration_days),
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


async def update_credit_interest_rate(credit_id: int, new_rate: float) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute(
                "UPDATE credits SET interest_rate = $1 WHERE id = $2 AND status = 'active'",
                new_rate, credit_id,
            )
            return result is not None
        else:
            await conn.execute(
                "UPDATE credits SET interest_rate = ? WHERE id = ? AND status = 'active'",
                (new_rate, credit_id),
            )
            await conn.commit()
            return True
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


async def clear_available_vehicles(vehicle_type: str | None = None) -> int:
    conn = await get_conn()
    try:
        where = " WHERE status = 'available'"
        if vehicle_type:
            where += f" AND vehicle_type = '{vehicle_type}'"
        if _is_pg:
            result = await conn.execute(f"DELETE FROM vehicles{where}")
            return int(result.split()[-1]) if result else 0
        else:
            cursor = await conn.execute(f"DELETE FROM vehicles{where}")
            await conn.commit()
            return cursor.rowcount
    finally:
        await conn.close()


async def clear_available_houses() -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute("DELETE FROM houses WHERE status = 'available'")
            return int(result.split()[-1]) if result else 0
        else:
            cursor = await conn.execute("DELETE FROM houses WHERE status = 'available'")
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
                         color: str = "", rarity: str = "common", chat_id: int = 0,
                         rent_price: int = 0) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO vehicles (make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id, rent_price) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING id",
                make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id, rent_price,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO vehicles (make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id, rent_price) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id, rent_price),
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


async def get_available_vehicles(chat_id: int | None = None, vehicle_type: str = 'car') -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            if chat_id is not None:
                rows = await conn.fetch("SELECT * FROM vehicles WHERE status = 'available' AND chat_id = $1 AND vehicle_type = $2 ORDER BY created_at DESC", chat_id, vehicle_type)
            else:
                rows = await conn.fetch("SELECT * FROM vehicles WHERE status = 'available' AND vehicle_type = $1 ORDER BY created_at DESC", vehicle_type)
        else:
            if chat_id is not None:
                cursor = await conn.execute("SELECT * FROM vehicles WHERE status = 'available' AND chat_id = ? AND vehicle_type = ? ORDER BY created_at DESC", (chat_id, vehicle_type))
            else:
                cursor = await conn.execute("SELECT * FROM vehicles WHERE status = 'available' AND vehicle_type = ? ORDER BY created_at DESC", (vehicle_type,))
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_user_vehicles(telegram_id: int, vehicle_type: str = 'car', chat_id: int = 0) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            if chat_id:
                rows = await conn.fetch("SELECT * FROM vehicles WHERE owner_telegram_id = $1 AND vehicle_type = $2 AND chat_id = $3 ORDER BY id ASC", telegram_id, vehicle_type, chat_id)
            else:
                rows = await conn.fetch("SELECT * FROM vehicles WHERE owner_telegram_id = $1 AND vehicle_type = $2 ORDER BY id ASC", telegram_id, vehicle_type)
        else:
            if chat_id:
                cursor = await conn.execute("SELECT * FROM vehicles WHERE owner_telegram_id = ? AND vehicle_type = ? AND chat_id = ? ORDER BY id ASC", (telegram_id, vehicle_type, chat_id))
            else:
                cursor = await conn.execute("SELECT * FROM vehicles WHERE owner_telegram_id = ? AND vehicle_type = ? ORDER BY id ASC", (telegram_id, vehicle_type))
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
    "IRS-CI Agent": "law", "Deputy Sheriff": "law",
    # Emergency
    "Пожарный": "emergency", "Фельдшер": "emergency",
    # Medical
    "Врач": "medical", "Медсестра": "medical",
    # Criminal
    "Хакер": "criminal", "Наркоторговец": "criminal",
    "Контрабандист": "criminal", "Угонщик": "criminal",
    "Вор": "criminal", "Бандит": "criminal",
    "Сотрудник DOT (Дорожный департамент)": "civilian",
    "Автомеханик": "civilian", "Грузоперевозчик": "civilian", "Инкассатор": "civilian",
}

DEFAULT_JOBS = [
    # Law Enforcement
    ("Мэр", 5000), ("Судья", 3500), ("Шериф", 4500),
    ("Прокурор", 3800), ("Адвокат", 2200),
    ("Заместитель шерифа", 3200),
    ("Офицер дорожной полиции", 2000), ("Полицейский", 2000),
    ("Городской клерк", 1500),
    ("IRS-CI Agent", 3500), ("Deputy Sheriff", 2800),
    # Emergency
    ("Пожарный", 1600), ("Фельдшер", 1800),
    # Medical
    ("Врач", 1800), ("Медсестра", 1600),
    # Criminal
    ("Хакер", 3000), ("Наркоторговец", 2800),
    ("Контрабандист", 2500), ("Угонщик", 2400),
    ("Вор", 2200), ("Бандит", 2000),
    # Civilian
    ("Банкир", 2800), ("Автодилер", 2000),
    ("Дальнобойщик", 1700), ("Механик", 1600),
    ("Фермер", 1500), ("Строитель", 1500),
    ("Сотрудник DOT (Дорожный департамент)", 1600),
    ("Водитель автобуса", 1400), ("Бармен", 1200),
    ("Таксист", 1200), ("Кассир", 1000),
    ("Работник заправки", 900), ("Официант", 800),
    ("Автомеханик", 1500), ("Грузоперевозчик", 1400), ("Инкассатор", 1300),
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


UNIQUE_JOBS = {"Мэр", "Прокурор", "Заместитель шерифа", "IRS-CI Agent"}

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


async def buy_player_vehicle(vehicle_id: int, buyer_id: int, org_id: int | None = None, chat_id: int = 0) -> tuple | bool:
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
                "UPDATE vehicles SET owner_telegram_id = $1, org_id = $2, status = 'sold', chat_id = $3 WHERE id = $4",
                buyer_id, org_id, chat_id, vehicle_id,
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
                "UPDATE vehicles SET owner_telegram_id = ?, org_id = ?, status = 'sold', chat_id = ? WHERE id = ?",
                (buyer_id, org_id, chat_id, vehicle_id),
            )
            await conn.commit()
            return seller_id, price
    finally:
        await conn.close()


async def get_player_listed_vehicles(chat_id: int = 0, vehicle_type: str = 'car') -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM vehicles WHERE status = 'player_listed' AND vehicle_type = $1 ORDER BY created_at DESC",
                vehicle_type,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE status = 'player_listed' AND vehicle_type = ? ORDER BY created_at DESC",
                (vehicle_type,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ── Trailer functions ──────────────────────────────────────


async def get_available_trailers(chat_id: int | None = None) -> list:
    return await get_available_vehicles(chat_id=chat_id, vehicle_type='trailer')


async def get_user_trailers(telegram_id: int, chat_id: int = 0) -> list:
    return await get_user_vehicles(telegram_id, vehicle_type='trailer', chat_id=chat_id)


async def get_player_listed_trailers(chat_id: int = 0) -> list:
    return await get_player_listed_vehicles(chat_id=chat_id, vehicle_type='trailer')


async def get_trailer_by_position(chat_id: int, position: int) -> dict | None:
    trailers = await get_available_trailers(chat_id=chat_id)
    if position < 1 or position > len(trailers):
        return None
    return trailers[position - 1]


async def create_trailer(make: str, model: str, year: int, price: int, miles: int,
                         city: str, vin: str, license_plate: str,
                         color: str = "", rarity: str = "common", chat_id: int = 0) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO vehicles (make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id, vehicle_type) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'trailer') RETURNING id",
                make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO vehicles (make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id, vehicle_type) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,'trailer')",
                (make, model, year, price, miles, city, vin, license_plate, color, rarity, chat_id),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        await conn.close()


async def buy_trailer(vehicle_id: int, telegram_id: int, org_id: int | None = None, chat_id: int = 0) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND status = 'available' AND vehicle_type = 'trailer' FOR UPDATE",
                vehicle_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = $1, org_id = $2, status = 'sold', chat_id = $3 WHERE id = $4",
                telegram_id, org_id, chat_id, vehicle_id,
            )
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND status = 'available' AND vehicle_type = 'trailer'",
                (vehicle_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = ?, org_id = ?, status = 'sold', chat_id = ? WHERE id = ?",
                (telegram_id, org_id, chat_id, vehicle_id),
            )
            await conn.commit()
            return True
    finally:
        await conn.close()


async def sell_trailer(vehicle_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' AND vehicle_type = 'trailer' FOR UPDATE",
                vehicle_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = NULL, status = 'available' WHERE id = $1",
                vehicle_id,
            )
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND owner_telegram_id = ? AND status = 'sold' AND vehicle_type = 'trailer'",
                (vehicle_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = NULL, status = 'available' WHERE id = ?",
                (vehicle_id,),
            )
            await conn.commit()
            return True
    finally:
        await conn.close()


async def list_trailer_for_sale(vehicle_id: int, telegram_id: int, price: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' AND vehicle_type = 'trailer' FOR UPDATE",
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
                "SELECT * FROM vehicles WHERE id = ? AND owner_telegram_id = ? AND status = 'sold' AND vehicle_type = 'trailer'",
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


async def unlist_trailer(vehicle_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND owner_telegram_id = $2 AND status = 'player_listed' AND vehicle_type = 'trailer' FOR UPDATE",
                vehicle_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET status = 'sold' WHERE id = $1", vehicle_id)
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND owner_telegram_id = ? AND status = 'player_listed' AND vehicle_type = 'trailer'",
                (vehicle_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET status = 'sold' WHERE id = ?", (vehicle_id,))
            await conn.commit()
            return True
    finally:
        await conn.close()


async def buy_player_trailer(vehicle_id: int, buyer_id: int, org_id: int | None = None, chat_id: int = 0) -> tuple | bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND status = 'player_listed' AND vehicle_type = 'trailer' FOR UPDATE",
                vehicle_id,
            )
            if not row:
                return False
            seller_id = row["owner_telegram_id"]
            price = row["price"]
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = $1, org_id = $2, status = 'sold', chat_id = $3 WHERE id = $4",
                buyer_id, org_id, chat_id, vehicle_id,
            )
            return seller_id, price
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND status = 'player_listed' AND vehicle_type = 'trailer'",
                (vehicle_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            seller_id = row["owner_telegram_id"]
            price = row["price"]
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = ?, org_id = ?, status = 'sold', chat_id = ? WHERE id = ?",
                (buyer_id, org_id, chat_id, vehicle_id),
            )
            await conn.commit()
            return seller_id, price
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


async def buy_vehicle(vehicle_id: int, telegram_id: int, org_id: int | None = None, chat_id: int = 0) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1 AND status = 'available' FOR UPDATE", vehicle_id)
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = $1, org_id = $2, status = 'sold', chat_id = $3 WHERE id = $4",
                telegram_id, org_id, chat_id, vehicle_id,
            )
            return True
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE id = ? AND status = 'available'", (vehicle_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET owner_telegram_id = ?, org_id = ?, status = 'sold', chat_id = ? WHERE id = ?",
                (telegram_id, org_id, chat_id, vehicle_id),
            )
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
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, org_id = NULL, status = 'available', chat_id = 0 WHERE id = $1", vehicle_id)
            return True
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE id = ? AND status = 'sold'", (vehicle_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, org_id = NULL, status = 'available', chat_id = 0 WHERE id = ?", (vehicle_id,))
            await conn.commit()
            return True
    finally:
        await conn.close()


async def admin_give_vehicle(vehicle_id: int, telegram_id: int, chat_id: int = 0) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1 AND status = 'available' FOR UPDATE", vehicle_id)
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = $1, org_id = NULL, status = 'sold', chat_id = $2 WHERE id = $3", telegram_id, chat_id, vehicle_id)
            return True
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE id = ? AND status = 'available'", (vehicle_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET owner_telegram_id = ?, org_id = NULL, status = 'sold', chat_id = ? WHERE id = ?", (telegram_id, chat_id, vehicle_id))
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
    (28, "Studio Apartment", 1, 1.0, 400, "Микро-студия. Самое дешёвое жильё."),
    (29, "Tiny House", 1, 1.0, 300, "Миниатюрный домик на колёсах."),
    (30, "Cabin", 2, 1.0, 700, "Небольшая деревенская хижина."),
    (31, "Small Ranch House", 2, 1.5, 1000, "Маленький ранчо с участком."),
]

HOUSE_PRICES = [65000, 145000, 120000, 165000, 110000, 200000, 350000, 195000, 480000,
                150000, 135000, 250000, 155000, 380000, 210000, 175000, 40000, 185000,
                170000, 195000, 160000, 165000, 190000, 180000, 230000, 200000, 220000,
                20000, 25000, 30000, 35000]

NEIGHBORHOODS = ["Six Housen't", "Lakeville", "Greenhills", "Horton", "Farm Area", "Greenville Lake", "Fleetwood Lane"]

# Which house types are available in which neighborhoods (0-indexed neighborhood IDs)
HOUSE_TYPE_NEIGHBORHOODS = {
    1: [0], 2: [1], 3: [2], 4: [2], 5: [1], 6: [0, 1],
    7: [0, 1, 2, 3, 4, 5, 6],  # Mansion #1 — все районы
    8: [4], 9: [5], 10: [0, 1], 11: [3], 12: [6], 13: [0],
    14: [3], 15: [1], 16: [2, 3], 17: [0], 18: [2],
    19: [1, 2], 20: [2], 21: [1], 22: [0], 23: [2],
    24: [0], 25: [3], 26: [2], 27: [4],
    28: [0], 29: [0], 30: [4], 31: [4],
}


# All business types sourced from https://greenville-wisconsin.fandom.com/wiki/Category:Locations
BUSINESS_TYPES = [
    # ── Gas Stations ──
    ("AG Gas Station", "gas_station", 60000, 90000, 2000, "Сеть заправок с круглосуточным обслуживанием. Есть магазин, автомойка и зарядки для электромобилей.", 450),
    ("Clam Gas Station", "gas_station", 45000, 75000, 1500, "Небольшая заправочная станция. Удобное расположение для быстрой остановки.", 350),

    # ── Convenience Stores / Markets ──
    ("Greenville Market", "convenience_store", 80000, 120000, 2500, "Продуктовый рынок в центре Гринвилля. Широкий ассортимент свежих продуктов.", 550),
    ("Quick Dollar", "convenience_store", 40000, 70000, 1200, "Магазин низких цен. Всё по одному доллару!", 250),
    ("The Bulk Priced Food Shoppe", "convenience_store", 100000, 150000, 2800, "Оптовый продуктовый магазин. Выгодные цены на крупные партии.", 650),
    ("Just Buy", "convenience_store", 50000, 80000, 1500, "Небольшой универсальный магазин. Есть всё необходимое.", 350),

    # ── Restaurants ──
    ("Bill's Diner", "restaurant", 60000, 90000, 1800, "Классический американский дайнер. Уютная атмосфера и домашняя еда.", 400),
    ("Bobahaus", "restaurant", 50000, 80000, 1500, "Модное кафе с чаем и закусками. Популярно среди молодёжи.", 350),
    ("British Fish & Chips", "restaurant", 55000, 85000, 1700, "Британская закусочная с традиционной рыбой с картошкой фри.", 400),
    ("Brookmere Brew", "restaurant", 70000, 100000, 2000, "Крафтовая пивоварня с собственной кухней. Живая музыка по выходным.", 450),
    ("Burger Knight", "restaurant", 90000, 130000, 2500, "Сетевой ресторан быстрого питания. Знаменитые бургеры и картошка фри.", 550),
    ("Burgerhaus", "restaurant", 90000, 130000, 2500, "Премиальная бургерная. Сочные стейки и авторские бургеры.", 550),
    ("Caffeine Street Coffee Co.", "restaurant", 50000, 80000, 1500, "Кофейня на главной улице. Свежая обжарка и домашняя выпечка.", 350),
    ("Connor's", "restaurant", 60000, 90000, 1800, "Ирландский паб с традиционной кухней и большим выбором пива.", 400),
    ("Crispi Cookies", "restaurant", 30000, 50000, 1000, "Пекарня с хрустящим печеньем. Аромат свежей выпечки на всю улицу.", 200),
    ("Dysku", "restaurant", 50000, 80000, 1500, "Современное кафе с интернациональной кухней.", 350),
    ("Farnsworth's", "restaurant", 80000, 120000, 2300, "Семейный ресторан с классической американской кухней.", 500),
    ("Fiesta Rodeo Mexican", "restaurant", 65000, 95000, 1900, "Мексиканский ресторан. Острые буррито и свежая сальса.", 450),
    ("Holey Smokes!", "restaurant", 70000, 100000, 2000, "Барбекю-ресторан. Копчёное мясо и домашние соусы.", 450),
    ("Home Barn American Grill", "restaurant", 90000, 130000, 2500, "Стейк-хаус в деревенском стиле. Отборное мясо на гриле.", 550),
    ("Hunty's Pizza Palace", "restaurant", 75000, 110000, 2300, "Пиццерия с толстым тестом. Доставка по всему Гринвиллю.", 500),
    ("Jimbo's Subs & Wraps", "restaurant", 55000, 85000, 1700, "Сэндвичная с огромными порциями. Свежие ингредиенты каждый день.", 400),
    ("JOGGIE'S", "restaurant", 40000, 65000, 1200, "Киоск с чипсами и закусками. Знаменитые чипсы со вкусом 'воздуха'.", 250),
    ("Kat's Kafe", "restaurant", 50000, 80000, 1500, "Уютное кафе с десертами. Любимое место для завтраков.", 350),
    ("Leo's Diner", "restaurant", 60000, 90000, 1800, "Круглосуточный дайнер. Завтрак подают в любое время.", 400),
    ("Noodle", "restaurant", 50000, 80000, 1500, "Азиатская лапшичная. Быстро, вкусно, дёшево.", 350),
    ("Noodles and Starblox", "restaurant", 70000, 100000, 2000, "Сетевое кафе с лапшой и кофе. Популярное место встреч.", 450),
    ("Ol' Texas", "restaurant", 90000, 130000, 2600, "Техасский стейк-хаус. Гигантские порции мяса и ковбойская атмосфера.", 600),
    ("Sonu Indian Cuisine", "restaurant", 70000, 100000, 2000, "Индийский ресторан с традиционными специями и карри.", 450),
    ("Superwich", "restaurant", 50000, 80000, 1500, "Закусочная с сэндвичами и сабми. Быстрое питание на ходу.", 350),
    ("Taco Castillo", "restaurant", 60000, 90000, 1800, "Мексиканское кафе с такос и начос. Острый соус входит в комплект.", 400),
    ("The Bread Shack", "restaurant", 45000, 70000, 1400, "Пекарня-булочная. Свежий хлеб и выпечка каждый час.", 300),
    ("The Ice Box", "restaurant", 35000, 55000, 1100, "Кафе-мороженое. Более 20 вкусов холодного десерта.", 250),
    ("The Ice Cream Station", "restaurant", 40000, 60000, 1200, "Киоск с мягким мороженым и молочными коктейлями.", 250),
    ("The Red Chopstick", "restaurant", 80000, 120000, 2300, "Китайский ресторан. Авторские блюда в классическом стиле.", 500),
    ("The Station", "restaurant", 65000, 95000, 1900, "Ресторан при ж/д станции. Атмосфера старых вокзалов.", 450),
    ("The Twist", "restaurant", 45000, 70000, 1400, "Кафе-мороженое с мягким сервисом. Любимое место детей.", 300),
    ("Vasitos", "restaurant", 60000, 90000, 1800, "Средиземноморский ресторан. Греческие салаты и свежие морепродукты.", 400),
    ("Visitors Sports Grill", "restaurant", 90000, 130000, 2500, "Спорт-бар с большими экранами. Болеем за местные команды!", 550),
    ("Zumoqa Mexican Grill", "restaurant", 70000, 100000, 2000, "Мексиканский гриль. Фахитас и кесадильи на углях.", 450),

    # ── Auto Services ──
    ("Brookmere Autos", "auto_service", 80000, 120000, 2500, "Автосервис в Брукмире. Диагностика и ремонт любых автомобилей.", 550),
    ("Dom's Service", "auto_service", 50000, 80000, 1500, "Небольшая автомастерская. Замена масла и мелкий ремонт.", 350),
    ("Fastlane", "auto_service", 60000, 90000, 1800, "Станция быстрого обслуживания. Шиномонтаж и замена жидкостей.", 400),
    ("Gary's Collision & Restoration", "auto_service", 100000, 160000, 3000, "Кузовной ремонт и реставрация. Вернём вашей машине былой блеск.", 700),
    ("Hurricane Car Wash", "auto_service", 50000, 80000, 1500, "Автомойка самообслуживания и бесконтактная мойка.", 350),
    ("Ignition Motor Parts", "auto_service", 80000, 120000, 2500, "Магазин автозапчастей и аксессуаров. Всё для тюнинга.", 550),
    ("Rapid Wash", "auto_service", 40000, 70000, 1200, "Экспресс-мойка. Чистота вашей машины за 5 минут.", 250),
    ("Roadmap Used Cars", "auto_service", 150000, 250000, 5000, "Автосалон подержанных автомобилей. Гарантия на каждый авто.", 1100),
    ("Ron Rivers Auto Group", "auto_service", 200000, 350000, 6000, "Крупный автодилер с новыми и подержанными авто.", 1400),
    ("Tires Plus", "auto_service", 60000, 100000, 2000, "Шиномонтаж и продажа шин. Сезонное хранение резины.", 450),
    ("Truck Planet", "auto_service", 100000, 160000, 3000, "Сервис грузовых автомобилей. Ремонт и обслуживание фур.", 700),

    # ── Entertainment ──
    ("Greenville Movie Theater", "entertainment", 200000, 300000, 5000, "Кинотеатр с 3D и IMAX залами. Премьеры каждую пятницу.", 1100),
    ("Timberwolf Drive-In Theater", "entertainment", 120000, 200000, 3500, "Автокинотеатр под открытым небом. Романтика на колёсах.", 800),
    ("Greenville Drag Strip", "entertainment", 250000, 400000, 6000, "Драг-полоса для уличных гонок. Ночные заезды по выходным.", 1400),
    ("Willowbend Circuit", "entertainment", 300000, 500000, 7000, "Гоночная трасса с извилистыми поворотами. Трекинговые заезды.", 1600),
    ("Wonder Waters", "entertainment", 150000, 250000, 4000, "Аквапарк с горками и бассейнами. Лучший отдых в жаркий день.", 900),
    ("Fox Campgrounds", "entertainment", 80000, 140000, 2500, "Кемпинг с местами для палаток и домиков. Отдых на природе.", 550),

    # ── Retail & Services ──
    ("Celestial Outlet Mall", "other", 300000, 500000, 8000, "Торговый центр с брендовыми магазинами. Скидки до 70%!", 1800),
    ("Greenville Fan Store", "other", 40000, 70000, 1200, "Магазин сувениров и мерча Гринвилля.", 250),
    ("Ivy Accessories", "other", 40000, 65000, 1200, "Магазин аксессуаров и бижутерии. Модные украшения.", 250),
    ("Pear Store", "other", 80000, 150000, 2500, "Магазин электроники Pear. Смартфоны, планшеты и аксессуары.", 550),
    ("Craig's Sporting Goods", "other", 80000, 120000, 2500, "Спортивные товары и снаряжение. Одежда для активного отдыха.", 550),
    ("William's Paints", "other", 50000, 80000, 1500, "Магазин красок и строительных материалов. Ремонт под ключ.", 350),
    ("HeenerG", "other", 60000, 100000, 2000, "Магазин техники и электроники. Бытовая техника по низким ценам.", 450),
    ("Minato", "other", 70000, 120000, 2200, "Магазин японских товаров. Сувениры, сладости и манга.", 500),
    ("Seoul", "other", 70000, 120000, 2200, "Корейский магазин косметики и товаров для дома.", 500),
    ("Zerab", "other", 50000, 80000, 1500, "Студия подарков и сувениров. Индивидуальный подход к каждому.", 350),
    ("Verwire", "other", 60000, 100000, 2000, "Магазин техники и гаджетов. Всё для геймеров.", 450),
    ("ERCKO", "other", 50000, 80000, 1500, "Студия дизайна и интерьера.", 350),
    ("Crane Industries", "other", 200000, 350000, 5500, "Промышленное предприятие. Производство стройматериалов.", 1300),
    ("Factory Pulse", "other", 250000, 400000, 6500, "Завод по производству электроники. Высокотехнологичное оборудование.", 1500),
    ("ASAUSA", "other", 70000, 120000, 2200, "Логистическая компания. Грузоперевозки и складские услуги.", 500),

    # ── Personal Services ──
    ("Beyond Beauty", "other", 40000, 70000, 1200, "Салон красоты. Стрижки, маникюр и косметология.", 250),
    ("The Barbers Chair", "other", 30000, 50000, 1000, "Мужская парикмахерская. Классические стрижки и бритьё.", 200),
    ("Enderson Cleaners", "other", 35000, 55000, 1100, "Химчистка и прачечная. Чистота вашей одежды.", 250),
    ("FluffyPaws Doggy Daycare", "other", 40000, 65000, 1200, "Дневной присмотр за собаками. Ваш питомец в надёжных руках.", 250),
    ("Heritage Animal Hospital", "other", 80000, 140000, 2500, "Ветеринарная клиника. Лечение и уход за домашними животными.", 550),
    ("Fox Mountain Medical Center", "other", 350000, 550000, 9000, "Медицинский центр. Круглосуточная помощь и диагностика.", 2000),
    ("Infinity Health Center", "other", 100000, 180000, 3000, "Фитнес-центр с тренажёрным залом и бассейном.", 700),
    ("Karate Wisconsin", "other", 40000, 70000, 1200, "Школа карате. Тренировки для детей и взрослых.", 250),
    ("Nerd Squad", "other", 40000, 65000, 1200, "Ремонт компьютеров и настройка техники. Помощь в любое время.", 250),
    ("Little Ones Daycare Center", "other", 50000, 80000, 1500, "Детский сад и центр развития. Присмотр за детьми.", 350),
    ("Mini Tots", "other", 45000, 70000, 1300, "Детский центр раннего развития.", 300),
    ("WORK-IT", "other", 50000, 80000, 1500, "Тренажёрный зал. Фитнес и кроссфит.", 350),
    ("Greenville's Finest Fireworks", "other", 50000, 80000, 1500, "Магазин фейерверков. Салюты и пиротехника.", 350),

    # ── Financial & Legal ──
    ("Allen Insurance Agency", "other", 60000, 100000, 2000, "Страховое агентство. Страхование жизни, авто и недвижимости.", 450),
    ("Family Insurance", "other", 50000, 90000, 1800, "Семейное страховое агентство. Доступные тарифы для всех.", 400),
    ("Fox Mountain Community Bank", "other", 300000, 500000, 8000, "Банк с полным спектром услуг. Кредиты и вклады.", 1800),
    ("Moat & Castle Credit Union", "other", 200000, 350000, 6000, "Кредитный союз. Выгодные ставки и бонусы для членов.", 1400),
    ("Pivora Banking Credit", "other", 250000, 400000, 7000, "Банковское учреждение. Инвестиции и финансовое планирование.", 1600),
    ("John Jones Investments", "other", 100000, 180000, 3000, "Инвестиционная фирма. Управление капиталом.", 700),
    ("North Charleston Accounting & Tax Services", "other", 50000, 80000, 1500, "Бухгалтерские услуги и налоговое консультирование.", 350),
    ("Tax Office", "other", 60000, 100000, 2000, "Налоговое управление. Оформление и консультации.", 450),
    ("Rajkumar's Realtors", "other", 80000, 140000, 2500, "Риелторское агентство. Покупка и продажа недвижимости.", 550),

    # ── Hotels & Accommodation ──
    ("Highway Motel", "other", 150000, 250000, 4000, "Придорожный мотель. Уютные номера и бесплатная парковка.", 900),
    ("Visit 24/7 Motel", "other", 120000, 200000, 3500, "Круглосуточный мотель. Заезд в любое время.", 800),

    # ── Storage & Misc ──
    ("Seal Storage Solutions", "other", 40000, 70000, 1200, "Склад индивидуального хранения. Безопасность 24/7.", 250),
    ("Store-All Storage", "other", 40000, 70000, 1200, "Складские помещения для аренды. Разные размеры боксов.", 250),
    ("Denver Atwood Camping Supplies", "other", 50000, 80000, 1500, "Магазин туристического снаряжения. Палатки, спальники, горелки.", 350),
    ("Inview", "other", 60000, 100000, 2000, "Студия видеонаблюдения и безопасности.", 450),
    ("NextStop", "other", 50000, 80000, 1500, "Туристическое агентство. Планирование поездок и экскурсий.", 350),
    ("Greenville Post Office", "other", 60000, 100000, 2000, "Почтовое отделение. Отправка писем и посылок.", 450),
    ("Pearphone XIII", "other", 60000, 100000, 2000, "Ремонт и продажа смартфонов. Аксессуары и запчасти.", 450),
    ("Lent", "other", 50000, 80000, 1500, "Ломбард. Быстрые займы под залог вещей.", 350),
    ("Richfield", "other", 70000, 120000, 2200, "Заправочная станция с магазином. Полный бак и горячий кофе.", 500),
    ("Ridgeview", "other", 70000, 120000, 2200, "Станция техосмотра и обслуживания автомобилей.", 500),
    ("Just Water", "other", 30000, 50000, 1000, "Магазин питьевой воды. Чистая вода на разлив.", 200),
]

async def seed_businesses() -> None:
    conn = await get_conn()
    try:
        if _is_pg:
            existing = await conn.fetchval("SELECT COUNT(*) FROM business_types")
        else:
            cursor = await conn.execute("SELECT COUNT(*) FROM business_types")
            row = await cursor.fetchone()
            existing = row[0] if row else 0
        if existing:
            return
        for i, bt in enumerate(BUSINESS_TYPES, 1):
            name, category, min_price, max_price, base_profit, desc, mat_cost = bt
            if _is_pg:
                await conn.execute(
                    "INSERT INTO business_types (id, name, category, min_price, max_price, base_profit, description) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                    i, name, category, min_price, max_price, base_profit, desc,
                )
            else:
                await conn.execute(
                    "INSERT INTO business_types (id, name, category, min_price, max_price, base_profit, description) VALUES (?,?,?,?,?,?,?)",
                    (i, name, category, min_price, max_price, base_profit, desc),
                )
        if not _is_pg:
            await conn.commit()
    finally:
        await conn.close()


async def seed_house_types() -> None:
    conn = await get_conn()
    try:
        for ht in HOUSE_TYPES:
            hid, name, beds, baths, sqft, desc = ht
            if _is_pg:
                await conn.execute(
                    "INSERT INTO house_types (id, type_name, bedrooms, bathrooms, sqft, description) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (id) DO NOTHING",
                    hid, name, beds, baths, sqft, desc,
                )
            else:
                try:
                    await conn.execute(
                        "INSERT OR IGNORE INTO house_types (id, type_name, bedrooms, bathrooms, sqft, description) VALUES (?,?,?,?,?,?)",
                        (hid, name, beds, baths, sqft, desc),
                    )
                except Exception:
                    pass
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


async def create_house_listing(chat_id: int, house_type_id: int, neighborhood_id: int, price: int, guid: str, rent_price: int = 0, photo_url: str = "", owner_id: int | None = None, desc_override: str = "") -> int:
    ht = await get_house_type(house_type_id)
    nb = await get_neighborhood(neighborhood_id)
    if not ht or not nb:
        raise ValueError("Invalid house_type_id or neighborhood_id")
    conn = await get_conn()
    try:
        loc = f"{nb['name']}, Greenville, WI"
        desc = desc_override or ht["description"]
        status = "sold" if owner_id else "available"
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO houses (chat_id, house_type_id, neighborhood_id, guid, type_name, neighborhood, location, price, bedrooms, bathrooms, sqft, description, rent_price, photo_url, owner_telegram_id, status) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16) RETURNING id",
                chat_id, house_type_id, neighborhood_id, guid,
                ht["type_name"], nb["name"], loc, price,
                ht["bedrooms"], ht["bathrooms"], ht["sqft"], desc, rent_price,
                photo_url, owner_id, status,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO houses (chat_id, house_type_id, neighborhood_id, guid, type_name, neighborhood, location, price, bedrooms, bathrooms, sqft, description, rent_price, photo_url, owner_telegram_id, status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (chat_id, house_type_id, neighborhood_id, guid,
                 ht["type_name"], nb["name"], loc, price,
                 ht["bedrooms"], ht["bathrooms"], ht["sqft"], desc, rent_price,
                 photo_url, owner_id, status),
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


async def buy_player_house(house_id: int, buyer_id: int, org_id: int | None = None, chat_id: int = 0):
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
                "UPDATE houses SET owner_telegram_id = $1, org_id = $2, status = 'sold', chat_id = $3 WHERE id = $4",
                buyer_id, org_id, chat_id, house_id,
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
                "UPDATE houses SET owner_telegram_id = ?, org_id = ?, status = 'sold', chat_id = ? WHERE id = ?",
                (buyer_id, org_id, chat_id, house_id),
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


async def get_user_houses(telegram_id: int, chat_id: int = 0) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            if chat_id:
                rows = await conn.fetch(
                    "SELECT * FROM houses WHERE owner_telegram_id = $1 AND chat_id = $2 ORDER BY created_at DESC",
                    telegram_id, chat_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM houses WHERE owner_telegram_id = $1 ORDER BY created_at DESC",
                    telegram_id,
                )
        else:
            if chat_id:
                cursor = await conn.execute(
                    "SELECT * FROM houses WHERE owner_telegram_id = ? AND chat_id = ? ORDER BY created_at DESC",
                    (telegram_id, chat_id),
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM houses WHERE owner_telegram_id = ? ORDER BY created_at DESC",
                    (telegram_id,),
                )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def buy_house(house_id: int, telegram_id: int, org_id: int | None = None, chat_id: int = 0) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM houses WHERE id = $1 AND status = 'available' FOR UPDATE", house_id)
            if not row:
                return False
            await conn.execute(
                "UPDATE houses SET owner_telegram_id = $1, org_id = $2, status = 'sold', chat_id = $3 WHERE id = $4",
                telegram_id, org_id, chat_id, house_id,
            )
            return True
        else:
            cursor = await conn.execute("SELECT * FROM houses WHERE id = ? AND status = 'available'", (house_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE houses SET owner_telegram_id = ?, org_id = ?, status = 'sold', chat_id = ? WHERE id = ?",
                (telegram_id, org_id, chat_id, house_id),
            )
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


# ─── Rental system ─────────────────────────────────────────────


async def list_house_for_rent(house_id: int, owner_id: int, rent_price: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' AND (rent_price IS NULL OR rent_price = 0) FOR UPDATE",
                house_id, owner_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE houses SET rent_price = $1 WHERE id = $2",
                rent_price, house_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE id = ? AND owner_telegram_id = ? AND status = 'sold' AND (rent_price IS NULL OR rent_price = 0)",
                (house_id, owner_id),
            )
            if not cursor.fetchone():
                return False
            await conn.execute(
                "UPDATE houses SET rent_price = ? WHERE id = ?",
                (rent_price, house_id),
            )
            await conn.commit()
        return True
    finally:
        await conn.close()


async def unlist_house_rent(house_id: int, owner_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE id = $1 AND owner_telegram_id = $2 AND tenant_telegram_id IS NULL AND rent_price > 0 FOR UPDATE",
                house_id, owner_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE houses SET rent_price = 0 WHERE id = $1",
                house_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE id = ? AND owner_telegram_id = ? AND tenant_telegram_id IS NULL AND rent_price > 0",
                (house_id, owner_id),
            )
            if not cursor.fetchone():
                return False
            await conn.execute(
                "UPDATE houses SET rent_price = 0 WHERE id = ?",
                (house_id,),
            )
            await conn.commit()
        return True
    finally:
        await conn.close()


async def get_for_rent_houses(chat_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM houses WHERE chat_id = $1 AND rent_price > 0 AND tenant_telegram_id IS NULL ORDER BY rent_price ASC",
                chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE chat_id = ? AND rent_price > 0 AND tenant_telegram_id IS NULL ORDER BY rent_price ASC",
                (chat_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def rent_house(house_id: int, tenant_id: int) -> tuple[bool, str]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE id = $1 AND rent_price > 0 AND tenant_telegram_id IS NULL FOR UPDATE",
                house_id,
            )
            if not row:
                return False, "Дом недоступен для аренды"
            h = dict(row)
            bal_row = await conn.fetchrow(
                "SELECT balance FROM users WHERE telegram_id = $1 AND chat_id = $2",
                tenant_id, h["chat_id"],
            )
            if not bal_row or bal_row["balance"] < h["rent_price"]:
                return False, f"Недостаточно средств. Аренда: ${h['rent_price']:,}/день"
            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE telegram_id = $2 AND chat_id = $3",
                h["rent_price"], tenant_id, h["chat_id"],
            )
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE telegram_id = $2 AND chat_id = $3",
                h["rent_price"], h["owner_telegram_id"], h["chat_id"],
            )
            await conn.execute(
                "UPDATE houses SET tenant_telegram_id = $1, rent_paid_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), rent_missed_days = 0 WHERE id = $2",
                tenant_id, house_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE id = ? AND rent_price > 0 AND tenant_telegram_id IS NULL",
                (house_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False, "Дом недоступен для аренды"
            h = dict(row)
            cur2 = await conn.execute(
                "SELECT balance FROM users WHERE telegram_id = ? AND chat_id = ?",
                (tenant_id, h["chat_id"]),
            )
            bal_row = cur2.fetchone()
            if not bal_row or bal_row[0] < h["rent_price"]:
                return False, f"Недостаточно средств. Аренда: ${h['rent_price']:,}/день"
            await conn.execute(
                "UPDATE users SET balance = balance - ? WHERE telegram_id = ? AND chat_id = ?",
                (h["rent_price"], tenant_id, h["chat_id"]),
            )
            await conn.execute(
                "UPDATE users SET balance = balance + ? WHERE telegram_id = ? AND chat_id = ?",
                (h["rent_price"], h["owner_telegram_id"], h["chat_id"]),
            )
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await conn.execute(
                "UPDATE houses SET tenant_telegram_id = ?, rent_paid_at = ?, rent_missed_days = 0 WHERE id = ?",
                (tenant_id, now_str, house_id),
            )
            await conn.commit()
        return True, f"✅ Вы арендовали {h['type_name']} (${h['rent_price']:,}/день)"
    finally:
        await conn.close()


async def get_tenant_house(telegram_id: int, chat_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE tenant_telegram_id = $1 AND chat_id = $2",
                telegram_id, chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE tenant_telegram_id = ? AND chat_id = ?",
                (telegram_id, chat_id),
            )
            row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def evict_tenant(house_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE id = $1 AND tenant_telegram_id IS NOT NULL FOR UPDATE",
                house_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE houses SET tenant_telegram_id = NULL, rent_paid_at = NULL, rent_missed_days = 0 WHERE id = $1",
                house_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE id = ? AND tenant_telegram_id IS NOT NULL",
                (house_id,),
            )
            if not cursor.fetchone():
                return False
            await conn.execute(
                "UPDATE houses SET tenant_telegram_id = NULL, rent_paid_at = NULL, rent_missed_days = 0 WHERE id = ?",
                (house_id,),
            )
            await conn.commit()
        return True
    finally:
        await conn.close()


async def get_all_rented_houses() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM houses WHERE tenant_telegram_id IS NOT NULL",
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE tenant_telegram_id IS NOT NULL",
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def collect_rent(house_id: int) -> dict:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM houses WHERE id = $1 AND tenant_telegram_id IS NOT NULL FOR UPDATE",
                house_id,
            )
            if not row:
                return {"ok": False, "reason": "not_rented"}
            h = dict(row)
            from datetime import datetime
            if h.get("rent_paid_at") and h["rent_paid_at"].startswith(datetime.now().strftime("%Y-%m-%d")):
                return {"ok": True, "action": "skipped", "price": 0}
            bal_row = await conn.fetchrow(
                "SELECT balance FROM users WHERE telegram_id = $1 AND chat_id = $2",
                h["tenant_telegram_id"], h["chat_id"],
            )
            if bal_row and bal_row["balance"] >= h["rent_price"]:
                await conn.execute(
                    "UPDATE users SET balance = balance - $1 WHERE telegram_id = $2 AND chat_id = $3",
                    h["rent_price"], h["tenant_telegram_id"], h["chat_id"],
                )
                await conn.execute(
                    "UPDATE users SET balance = balance + $1 WHERE telegram_id = $2 AND chat_id = $3",
                    h["rent_price"], h["owner_telegram_id"], h["chat_id"],
                )
                await conn.execute(
                    "UPDATE houses SET rent_paid_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), rent_missed_days = 0 WHERE id = $1",
                    house_id,
                )
                return {"ok": True, "action": "collected", "price": h["rent_price"]}
            else:
                missed = (h["rent_missed_days"] or 0) + 1
                if missed >= 3:
                    await conn.execute(
                        "UPDATE houses SET tenant_telegram_id = NULL, rent_paid_at = NULL, rent_missed_days = 0 WHERE id = $1",
                        house_id,
                    )
                    return {"ok": True, "action": "evicted", "missed": missed}
                else:
                    await conn.execute(
                        "UPDATE houses SET rent_missed_days = $1 WHERE id = $2",
                        missed, house_id,
                    )
                    return {"ok": True, "action": "missed", "missed": missed}
        else:
            from datetime import datetime
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE id = ? AND tenant_telegram_id IS NOT NULL",
                (house_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {"ok": False, "reason": "not_rented"}
            h = dict(row)
            if h.get("rent_paid_at") and h["rent_paid_at"].startswith(datetime.now().strftime("%Y-%m-%d")):
                await conn.commit()
                return {"ok": True, "action": "skipped", "price": 0}
            cur2 = await conn.execute(
                "SELECT balance FROM users WHERE telegram_id = ? AND chat_id = ?",
                (h["tenant_telegram_id"], h["chat_id"]),
            )
            bal_row = cur2.fetchone()
            if bal_row and bal_row[0] >= h["rent_price"]:
                await conn.execute(
                    "UPDATE users SET balance = balance - ? WHERE telegram_id = ? AND chat_id = ?",
                    (h["rent_price"], h["tenant_telegram_id"], h["chat_id"]),
                )
                await conn.execute(
                    "UPDATE users SET balance = balance + ? WHERE telegram_id = ? AND chat_id = ?",
                    (h["rent_price"], h["owner_telegram_id"], h["chat_id"]),
                )
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await conn.execute(
                    "UPDATE houses SET rent_paid_at = ?, rent_missed_days = 0 WHERE id = ?",
                    (now_str, house_id),
                )
                await conn.commit()
                return {"ok": True, "action": "collected", "price": h["rent_price"]}
            else:
                missed = (h["rent_missed_days"] or 0) + 1
                if missed >= 3:
                    await conn.execute(
                        "UPDATE houses SET tenant_telegram_id = NULL, rent_paid_at = NULL, rent_missed_days = 0 WHERE id = ?",
                        (house_id,),
                    )
                    await conn.commit()
                    return {"ok": True, "action": "evicted", "missed": missed}
                else:
                    await conn.execute(
                        "UPDATE houses SET rent_missed_days = ? WHERE id = ?",
                        (missed, house_id),
                    )
                    await conn.commit()
                    return {"ok": True, "action": "missed", "missed": missed}
    finally:
        await conn.close()


# ─── Car rental system ─────────────────────────────────────────


async def list_car_for_rent(vehicle_id: int, owner_id: int, rent_price: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' AND (rent_price IS NULL OR rent_price = 0) FOR UPDATE",
                vehicle_id, owner_id,
            )
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET rent_price = $1 WHERE id = $2", rent_price, vehicle_id)
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND owner_telegram_id = ? AND status = 'sold' AND (rent_price IS NULL OR rent_price = 0)",
                (vehicle_id, owner_id),
            )
            if not cursor.fetchone():
                return False
            await conn.execute("UPDATE vehicles SET rent_price = ? WHERE id = ?", (rent_price, vehicle_id))
            await conn.commit()
        return True
    finally:
        await conn.close()


async def unlist_car_rent(vehicle_id: int, owner_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND owner_telegram_id = $2 AND tenant_telegram_id IS NULL AND rent_price > 0 FOR UPDATE",
                vehicle_id, owner_id,
            )
            if not row:
                return False
            await conn.execute("UPDATE vehicles SET rent_price = 0 WHERE id = $1", vehicle_id)
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND owner_telegram_id = ? AND tenant_telegram_id IS NULL AND rent_price > 0",
                (vehicle_id, owner_id),
            )
            if not cursor.fetchone():
                return False
            await conn.execute("UPDATE vehicles SET rent_price = 0 WHERE id = ?", (vehicle_id,))
            await conn.commit()
        return True
    finally:
        await conn.close()


async def get_for_rent_cars(chat_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM vehicles WHERE chat_id = $1 AND rent_price > 0 AND tenant_telegram_id IS NULL ORDER BY rent_price ASC",
                chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE chat_id = ? AND rent_price > 0 AND tenant_telegram_id IS NULL ORDER BY rent_price ASC",
                (chat_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def rent_car(vehicle_id: int, tenant_id: int) -> tuple[bool, str]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND rent_price > 0 AND tenant_telegram_id IS NULL FOR UPDATE",
                vehicle_id,
            )
            if not row:
                return False, "Авто недоступно для аренды"
            v = dict(row)
            bal_row = await conn.fetchrow(
                "SELECT balance FROM users WHERE telegram_id = $1 AND chat_id = $2",
                tenant_id, v["chat_id"],
            )
            if not bal_row or bal_row["balance"] < v["rent_price"]:
                return False, f"Недостаточно средств. Аренда: ${v['rent_price']:,}/день"
            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE telegram_id = $2 AND chat_id = $3",
                v["rent_price"], tenant_id, v["chat_id"],
            )
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE telegram_id = $2 AND chat_id = $3",
                v["rent_price"], v["owner_telegram_id"], v["chat_id"],
            )
            await conn.execute(
                "UPDATE vehicles SET tenant_telegram_id = $1, rent_paid_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), rent_missed_days = 0 WHERE id = $2",
                tenant_id, vehicle_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND rent_price > 0 AND tenant_telegram_id IS NULL",
                (vehicle_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False, "Авто недоступно для аренды"
            v = dict(row)
            cur2 = await conn.execute(
                "SELECT balance FROM users WHERE telegram_id = ? AND chat_id = ?",
                (tenant_id, v["chat_id"]),
            )
            bal_row = cur2.fetchone()
            if not bal_row or bal_row[0] < v["rent_price"]:
                return False, f"Недостаточно средств. Аренда: ${v['rent_price']:,}/день"
            await conn.execute(
                "UPDATE users SET balance = balance - ? WHERE telegram_id = ? AND chat_id = ?",
                (v["rent_price"], tenant_id, v["chat_id"]),
            )
            await conn.execute(
                "UPDATE users SET balance = balance + ? WHERE telegram_id = ? AND chat_id = ?",
                (v["rent_price"], v["owner_telegram_id"], v["chat_id"]),
            )
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await conn.execute(
                "UPDATE vehicles SET tenant_telegram_id = ?, rent_paid_at = ?, rent_missed_days = 0 WHERE id = ?",
                (tenant_id, now_str, vehicle_id),
            )
            await conn.commit()
        return True, f"✅ Вы арендовали {v.get('make', '')} {v.get('model', '')} (${v['rent_price']:,}/день)"
    finally:
        await conn.close()


async def get_tenant_car(telegram_id: int, chat_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE tenant_telegram_id = $1 AND chat_id = $2",
                telegram_id, chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE tenant_telegram_id = ? AND chat_id = ?",
                (telegram_id, chat_id),
            )
            row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def evict_car_tenant(vehicle_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND tenant_telegram_id IS NOT NULL FOR UPDATE",
                vehicle_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE vehicles SET tenant_telegram_id = NULL, rent_paid_at = NULL, rent_missed_days = 0 WHERE id = $1",
                vehicle_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND tenant_telegram_id IS NOT NULL",
                (vehicle_id,),
            )
            if not cursor.fetchone():
                return False
            await conn.execute(
                "UPDATE vehicles SET tenant_telegram_id = NULL, rent_paid_at = NULL, rent_missed_days = 0 WHERE id = ?",
                (vehicle_id,),
            )
            await conn.commit()
        return True
    finally:
        await conn.close()


async def get_all_rented_cars() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM vehicles WHERE tenant_telegram_id IS NOT NULL")
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE tenant_telegram_id IS NOT NULL")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def collect_car_rent(vehicle_id: int) -> dict:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM vehicles WHERE id = $1 AND tenant_telegram_id IS NOT NULL FOR UPDATE",
                vehicle_id,
            )
            if not row:
                return {"ok": False, "reason": "not_rented"}
            v = dict(row)
            from datetime import datetime
            if v.get("rent_paid_at") and v["rent_paid_at"].startswith(datetime.now().strftime("%Y-%m-%d")):
                return {"ok": True, "action": "skipped", "price": 0}
            bal_row = await conn.fetchrow(
                "SELECT balance FROM users WHERE telegram_id = $1 AND chat_id = $2",
                v["tenant_telegram_id"], v["chat_id"],
            )
            if bal_row and bal_row["balance"] >= v["rent_price"]:
                await conn.execute(
                    "UPDATE users SET balance = balance - $1 WHERE telegram_id = $2 AND chat_id = $3",
                    v["rent_price"], v["tenant_telegram_id"], v["chat_id"],
                )
                await conn.execute(
                    "UPDATE users SET balance = balance + $1 WHERE telegram_id = $2 AND chat_id = $3",
                    v["rent_price"], v["owner_telegram_id"], v["chat_id"],
                )
                await conn.execute(
                    "UPDATE vehicles SET rent_paid_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), rent_missed_days = 0 WHERE id = $1",
                    vehicle_id,
                )
                return {"ok": True, "action": "collected", "price": v["rent_price"]}
            else:
                missed = (v["rent_missed_days"] or 0) + 1
                if missed >= 3:
                    await conn.execute(
                        "UPDATE vehicles SET tenant_telegram_id = NULL, rent_paid_at = NULL, rent_missed_days = 0 WHERE id = $1",
                        vehicle_id,
                    )
                    return {"ok": True, "action": "evicted", "missed": missed}
                else:
                    await conn.execute(
                        "UPDATE vehicles SET rent_missed_days = $1 WHERE id = $2",
                        missed, vehicle_id,
                    )
                    return {"ok": True, "action": "missed", "missed": missed}
        else:
            from datetime import datetime
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE id = ? AND tenant_telegram_id IS NOT NULL",
                (vehicle_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {"ok": False, "reason": "not_rented"}
            v = dict(row)
            if v.get("rent_paid_at") and v["rent_paid_at"].startswith(datetime.now().strftime("%Y-%m-%d")):
                await conn.commit()
                return {"ok": True, "action": "skipped", "price": 0}
            cur2 = await conn.execute(
                "SELECT balance FROM users WHERE telegram_id = ? AND chat_id = ?",
                (v["tenant_telegram_id"], v["chat_id"]),
            )
            bal_row = cur2.fetchone()
            if bal_row and bal_row[0] >= v["rent_price"]:
                await conn.execute(
                    "UPDATE users SET balance = balance - ? WHERE telegram_id = ? AND chat_id = ?",
                    (v["rent_price"], v["tenant_telegram_id"], v["chat_id"]),
                )
                await conn.execute(
                    "UPDATE users SET balance = balance + ? WHERE telegram_id = ? AND chat_id = ?",
                    (v["rent_price"], v["owner_telegram_id"], v["chat_id"]),
                )
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await conn.execute(
                    "UPDATE vehicles SET rent_paid_at = ?, rent_missed_days = 0 WHERE id = ?",
                    (now_str, vehicle_id),
                )
                await conn.commit()
                return {"ok": True, "action": "collected", "price": v["rent_price"]}
            else:
                missed = (v["rent_missed_days"] or 0) + 1
                if missed >= 3:
                    await conn.execute(
                        "UPDATE vehicles SET tenant_telegram_id = NULL, rent_paid_at = NULL, rent_missed_days = 0 WHERE id = ?",
                        (vehicle_id,),
                    )
                    await conn.commit()
                    return {"ok": True, "action": "evicted", "missed": missed}
                else:
                    await conn.execute(
                        "UPDATE vehicles SET rent_missed_days = ? WHERE id = ?",
                        (missed, vehicle_id),
                    )
                    await conn.commit()
                    return {"ok": True, "action": "missed", "missed": missed}
    finally:
        await conn.close()


# ─── Organization accounts ──────────────────────────────────────


async def create_org(name: str, owner_telegram_id: int) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO organizations (name, owner_telegram_id) VALUES ($1, $2) RETURNING id",
                name, owner_telegram_id,
            )
            org_id = row["id"]
            await conn.execute(
                "INSERT INTO org_members (org_id, telegram_id, role) VALUES ($1, $2, 'owner')",
                org_id, owner_telegram_id,
            )
        else:
            cursor = await conn.execute(
                "INSERT INTO organizations (name, owner_telegram_id) VALUES (?, ?)",
                (name, owner_telegram_id),
            )
            org_id = cursor.lastrowid
            await conn.execute(
                "INSERT INTO org_members (org_id, telegram_id, role) VALUES (?, ?, 'owner')",
                (org_id, owner_telegram_id),
            )
            await conn.commit()
        return org_id
    finally:
        await conn.close()


async def get_org(org_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM organizations WHERE id = $1", org_id)
        else:
            cursor = await conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
            row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_all_orgs() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT o.*, (SELECT COUNT(*) FROM org_members WHERE org_id = o.id) as member_count FROM organizations o ORDER BY o.id")
        else:
            cursor = await conn.execute(
                "SELECT o.*, (SELECT COUNT(*) FROM org_members WHERE org_id = o.id) as member_count FROM organizations o ORDER BY o.id",
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_user_orgs(telegram_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT o.* FROM organizations o JOIN org_members m ON o.id = m.org_id WHERE m.telegram_id = $1",
                telegram_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT o.* FROM organizations o JOIN org_members m ON o.id = m.org_id WHERE m.telegram_id = ?",
                (telegram_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def update_org_balance(org_id: int, amount: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute(
                "UPDATE organizations SET balance = balance + $1 WHERE id = $2 AND balance + $1 >= 0",
                amount, org_id,
            )
            return "UPDATE 1" in (result or "")
        else:
            cursor = await conn.execute(
                "UPDATE organizations SET balance = balance + ? WHERE id = ? AND balance + ? >= 0",
                (amount, org_id, amount),
            )
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def add_org_member(org_id: int, telegram_id: int, role: str = "member") -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            try:
                await conn.execute(
                    "INSERT INTO org_members (org_id, telegram_id, role) VALUES ($1, $2, $3)",
                    org_id, telegram_id, role,
                )
                return True
            except Exception:
                return False
        else:
            try:
                await conn.execute(
                    "INSERT INTO org_members (org_id, telegram_id, role) VALUES (?, ?, ?)",
                    (org_id, telegram_id, role),
                )
                await conn.commit()
                return True
            except Exception:
                return False
    finally:
        await conn.close()


async def remove_org_member(org_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute(
                "DELETE FROM org_members WHERE org_id = $1 AND telegram_id = $2 AND role != 'owner'",
                org_id, telegram_id,
            )
            return "DELETE 1" in (result or "")
        else:
            cursor = await conn.execute(
                "DELETE FROM org_members WHERE org_id = ? AND telegram_id = ? AND role != 'owner'",
                (org_id, telegram_id),
            )
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def get_org_members(org_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT DISTINCT m.*, COALESCE(u.username, u.first_name, '') as name "
                "FROM org_members m LEFT JOIN users u ON m.telegram_id = u.telegram_id "
                "WHERE m.org_id = $1",
                org_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT DISTINCT m.*, COALESCE(u.username, u.first_name, '') as name "
                "FROM org_members m LEFT JOIN users u ON m.telegram_id = u.telegram_id "
                "WHERE m.org_id = ?",
                (org_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def is_org_member(org_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT 1 FROM org_members WHERE org_id = $1 AND telegram_id = $2",
                org_id, telegram_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT 1 FROM org_members WHERE org_id = ? AND telegram_id = ?",
                (org_id, telegram_id),
            )
            row = cursor.fetchone()
        return row is not None
    finally:
        await conn.close()


async def is_org_owner(org_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT 1 FROM org_members WHERE org_id = $1 AND telegram_id = $2 AND role = 'owner'",
                org_id, telegram_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT 1 FROM org_members WHERE org_id = ? AND telegram_id = ? AND role = 'owner'",
                (org_id, telegram_id),
            )
            row = cursor.fetchone()
        return row is not None
    finally:
        await conn.close()


async def delete_org(org_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("DELETE FROM org_members WHERE org_id = $1", org_id)
            result = await conn.execute("DELETE FROM organizations WHERE id = $1", org_id)
            return "DELETE 1" in (result or "")
        else:
            await conn.execute("DELETE FROM org_members WHERE org_id = ?", (org_id,))
            cursor = await conn.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def force_delete_org(org_id: int) -> dict:
    conn = await get_conn()
    try:
        org = await get_org(org_id)
        if not org:
            return {"ok": False, "error": "Организация не найдена"}

        if _is_pg:
            rows = await conn.fetch("SELECT vehicle_type FROM vehicles WHERE org_id = $1 AND status = 'sold'", org_id)
            cars = sum(1 for r in rows if r["vehicle_type"] == "car")
            trailers = sum(1 for r in rows if r["vehicle_type"] == "trailer")
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, org_id = NULL, status = 'available', chat_id = 0 WHERE org_id = $1", org_id)

            rows = await conn.fetch("SELECT id FROM houses WHERE org_id = $1 AND status = 'sold'", org_id)
            houses = len(rows)
            await conn.execute("UPDATE houses SET owner_telegram_id = NULL, org_id = NULL, status = 'available', chat_id = 0 WHERE org_id = $1", org_id)

            rows = await conn.fetch("SELECT id FROM businesses WHERE org_id = $1", org_id)
            businesses = len(rows)
            await conn.execute("UPDATE businesses SET org_id = NULL WHERE org_id = $1", org_id)

            await conn.execute("DELETE FROM org_members WHERE org_id = $1", org_id)
            await conn.execute("DELETE FROM organizations WHERE id = $1", org_id)
        else:
            cursor = await conn.execute("SELECT vehicle_type FROM vehicles WHERE org_id = ? AND status = 'sold'", (org_id,))
            rows = await cursor.fetchall()
            cars = sum(1 for r in rows if r["vehicle_type"] == "car")
            trailers = sum(1 for r in rows if r["vehicle_type"] == "trailer")
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, org_id = NULL, status = 'available', chat_id = 0 WHERE org_id = ?", (org_id,))

            cursor = await conn.execute("SELECT id FROM houses WHERE org_id = ? AND status = 'sold'", (org_id,))
            rows = await cursor.fetchall()
            houses = len(rows)
            await conn.execute("UPDATE houses SET owner_telegram_id = NULL, org_id = NULL, status = 'available', chat_id = 0 WHERE org_id = ?", (org_id,))

            cursor = await conn.execute("SELECT id FROM businesses WHERE org_id = ?", (org_id,))
            rows = await cursor.fetchall()
            businesses = len(rows)
            await conn.execute("UPDATE businesses SET org_id = NULL WHERE org_id = ?", (org_id,))

            await conn.execute("DELETE FROM org_members WHERE org_id = ?", (org_id,))
            cursor = await conn.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
            await conn.commit()

        return {
            "ok": True,
            "org_name": org["name"],
            "balance_lost": org.get("balance", 0),
            "counts": {
                "cars": cars,
                "trailers": trailers,
                "houses": houses,
                "businesses": businesses,
            },
        }
    finally:
        await conn.close()


async def transfer_asset(item_type: str, item_id: int, new_owner_id: int | None = None, new_org_id: int | None = None, chat_id: int = 0) -> bool:
    conn = await get_conn()
    try:
        if item_type == "vehicle":
            table = "vehicles"
        elif item_type == "house":
            table = "houses"
        else:
            return False
        if _is_pg:
            result = await conn.execute(
                f"UPDATE {table} SET owner_telegram_id = $1, org_id = $2, chat_id = $3 WHERE id = $4",
                new_owner_id, new_org_id, chat_id, item_id,
            )
            return "UPDATE 1" in (result or "")
        else:
            cursor = await conn.execute(
                f"UPDATE {table} SET owner_telegram_id = ?, org_id = ?, chat_id = ? WHERE id = ?",
                (new_owner_id, new_org_id, chat_id, item_id),
            )
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def pay_from_org(org_id: int, user_id: int, amount: int, chat_id: int, description: str = "") -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT 1 FROM org_members WHERE org_id = $1 AND telegram_id = $2 FOR UPDATE",
                org_id, user_id,
            )
            if not row:
                return False
            org = await conn.fetchrow(
                "SELECT * FROM organizations WHERE id = $1 FOR UPDATE",
                org_id,
            )
            if not org or org["balance"] < amount:
                return False
            await conn.execute(
                "UPDATE organizations SET balance = balance - $1 WHERE id = $2",
                amount, org_id,
            )
            await conn.execute(
                "INSERT INTO transactions (type, sender_telegram_id, amount, description) VALUES ($1, $2, $3, $4)",
                "org_payment", user_id, -amount, description,
            )
        else:
            cursor = await conn.execute(
                "SELECT 1 FROM org_members WHERE org_id = ? AND telegram_id = ?",
                (org_id, user_id),
            )
            if not cursor.fetchone():
                return False
            cursor = await conn.execute(
                "SELECT * FROM organizations WHERE id = ?",
                (org_id,),
            )
            org = cursor.fetchone()
            if not org or org["balance"] < amount:
                return False
            await conn.execute(
                "UPDATE organizations SET balance = balance - ? WHERE id = ? AND balance - ? >= 0",
                (amount, org_id, amount),
            )
            if cursor.rowcount == 0:
                return False
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await conn.execute(
                "INSERT INTO transactions (type, sender_telegram_id, amount, description, created_at) VALUES (?, ?, ?, ?, ?)",
                ("org_payment", user_id, -amount, description, now_str),
            )
            await conn.commit()
        return True
    except Exception:
        return False
    finally:
        await conn.close()


async def refund_org(org_id: int, user_id: int, amount: int, chat_id: int, description: str = "") -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute(
                "UPDATE organizations SET balance = balance + $1 WHERE id = $2",
                amount, org_id,
            )
            await conn.execute(
                "INSERT INTO transactions (type, sender_telegram_id, amount, description) VALUES ($1, $2, $3, $4)",
                "org_refund", user_id, amount, description,
            )
        else:
            await conn.execute(
                "UPDATE organizations SET balance = balance + ? WHERE id = ?",
                (amount, org_id),
            )
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await conn.execute(
                "INSERT INTO transactions (type, sender_telegram_id, amount, description, created_at) VALUES (?, ?, ?, ?, ?)",
                ("org_refund", user_id, amount, description, now_str),
            )
            await conn.commit()
        return True
    except Exception:
        return False
    finally:
        await conn.close()


async def get_org_vehicles(org_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM vehicles WHERE org_id = $1 AND status = 'sold' AND vehicle_type = 'car'",
                org_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE org_id = ? AND status = 'sold' AND vehicle_type = 'car'",
                (org_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_org_houses(org_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM houses WHERE org_id = $1 AND status = 'sold'",
                org_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM houses WHERE org_id = ? AND status = 'sold'",
                (org_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_org_trailers(org_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM vehicles WHERE org_id = $1 AND status = 'sold' AND vehicle_type = 'trailer'",
                org_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM vehicles WHERE org_id = ? AND status = 'sold' AND vehicle_type = 'trailer'",
                (org_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ────────────────────────────────────────────────────────────────


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


# ── Business functions ──────────────────────────────────────


BUSINESS_SELECT = """
    SELECT b.*, bt.name as type_name, bt.category as category,
           bt.base_profit, bt.description as type_description
    FROM businesses b
    JOIN business_types bt ON bt.id = b.business_type_id
"""


async def get_business_type(type_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM business_types WHERE id = $1", type_id)
            return dict(row) if row else None
        else:
            cursor = await conn.execute("SELECT * FROM business_types WHERE id = ?", (type_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()


async def get_all_business_types() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch("SELECT * FROM business_types ORDER BY id")
        else:
            cursor = await conn.execute("SELECT * FROM business_types ORDER BY id")
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_available_businesses(chat_id: int = 0) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            if chat_id:
                rows = await conn.fetch(
                    BUSINESS_SELECT + " WHERE b.chat_id = $1 AND b.status = 'available' ORDER BY b.created_at DESC",
                    chat_id,
                )
            else:
                rows = await conn.fetch(
                    BUSINESS_SELECT + " WHERE b.status = 'available' ORDER BY b.created_at DESC"
                )
        else:
            if chat_id:
                cursor = await conn.execute(
                    BUSINESS_SELECT + " WHERE b.chat_id = ? AND b.status = 'available' ORDER BY b.created_at DESC",
                    (chat_id,),
                )
            else:
                cursor = await conn.execute(
                    BUSINESS_SELECT + " WHERE b.status = 'available' ORDER BY b.created_at DESC"
                )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_user_businesses(telegram_id: int, chat_id: int = 0) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            if chat_id:
                rows = await conn.fetch(
                    BUSINESS_SELECT + " WHERE b.owner_telegram_id = $1 AND b.chat_id = $2 ORDER BY b.created_at DESC",
                    telegram_id, chat_id,
                )
            else:
                rows = await conn.fetch(
                    BUSINESS_SELECT + " WHERE b.owner_telegram_id = $1 ORDER BY b.created_at DESC",
                    telegram_id,
                )
        else:
            if chat_id:
                cursor = await conn.execute(
                    BUSINESS_SELECT + " WHERE b.owner_telegram_id = ? AND b.chat_id = ? ORDER BY b.created_at DESC",
                    (telegram_id, chat_id),
                )
            else:
                cursor = await conn.execute(
                    BUSINESS_SELECT + " WHERE b.owner_telegram_id = ? ORDER BY b.created_at DESC",
                    (telegram_id,),
                )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_player_listed_businesses() -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                BUSINESS_SELECT + " WHERE b.status = 'player_listed' ORDER BY b.created_at DESC"
            )
        else:
            cursor = await conn.execute(
                BUSINESS_SELECT + " WHERE b.status = 'player_listed' ORDER BY b.created_at DESC"
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_business(business_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                BUSINESS_SELECT + " WHERE b.id = $1", business_id,
            )
            return dict(row) if row else None
        else:
            cursor = await conn.execute(
                BUSINESS_SELECT + " WHERE b.id = ?", (business_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()


async def create_business_listing(chat_id: int, business_type_id: int, price: int, guid: str) -> int:
    bt = await get_business_type(business_type_id)
    if not bt:
        raise ValueError("Invalid business_type_id")
    if price < bt["min_price"] or price > bt["max_price"]:
        raise ValueError(f"Price must be between {bt['min_price']} and {bt['max_price']} for {bt['name']}")
    mat_cost = BUSINESS_TYPES[business_type_id - 1][6] if 1 <= business_type_id <= len(BUSINESS_TYPES) else 100
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO businesses (chat_id, business_type_id, name, location, price, profit, materials_cost) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
                chat_id, business_type_id, bt["name"], bt["name"], price, bt["base_profit"], mat_cost,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO businesses (chat_id, business_type_id, name, location, price, profit, materials_cost) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (chat_id, business_type_id, bt["name"], bt["name"], price, bt["base_profit"], mat_cost),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        await conn.close()


async def buy_business(business_id: int, telegram_id: int, org_id: int | None = None, chat_id: int = 0) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM businesses WHERE id = $1 AND status = 'available' FOR UPDATE",
                business_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE businesses SET owner_telegram_id = $1, org_id = $2, status = 'sold', chat_id = $3 WHERE id = $4",
                telegram_id, org_id, chat_id, business_id,
            )
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM businesses WHERE id = ? AND status = 'available'",
                (business_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE businesses SET owner_telegram_id = ?, org_id = ?, status = 'sold', chat_id = ? WHERE id = ?",
                (telegram_id, org_id, chat_id, business_id),
            )
            await conn.commit()
            return True
    finally:
        await conn.close()


async def sell_business(business_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM businesses WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' FOR UPDATE",
                business_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE businesses SET owner_telegram_id = NULL, status = 'available' WHERE id = $1",
                business_id,
            )
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM businesses WHERE id = ? AND owner_telegram_id = ? AND status = 'sold'",
                (business_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE businesses SET owner_telegram_id = NULL, status = 'available' WHERE id = ?",
                (business_id,),
            )
            await conn.commit()
            return True
    finally:
        await conn.close()


async def list_business_for_sale(business_id: int, telegram_id: int, price: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM businesses WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold' FOR UPDATE",
                business_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE businesses SET status = 'player_listed', price = $1 WHERE id = $2",
                price, business_id,
            )
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM businesses WHERE id = ? AND owner_telegram_id = ? AND status = 'sold'",
                (business_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE businesses SET status = 'player_listed', price = ? WHERE id = ?",
                (price, business_id),
            )
            await conn.commit()
            return True
    finally:
        await conn.close()


async def unlist_business(business_id: int, telegram_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM businesses WHERE id = $1 AND owner_telegram_id = $2 AND status = 'player_listed' FOR UPDATE",
                business_id, telegram_id,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE businesses SET status = 'sold' WHERE id = $1", business_id,
            )
            return True
        else:
            cursor = await conn.execute(
                "SELECT * FROM businesses WHERE id = ? AND owner_telegram_id = ? AND status = 'player_listed'",
                (business_id, telegram_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE businesses SET status = 'sold' WHERE id = ?", (business_id,),
            )
            await conn.commit()
            return True
    finally:
        await conn.close()


async def buy_player_business(business_id: int, buyer_id: int, org_id: int | None = None, chat_id: int = 0):
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM businesses WHERE id = $1 AND status = 'player_listed' FOR UPDATE",
                business_id,
            )
            if not row:
                return False
            seller_id = row["owner_telegram_id"]
            price = row["price"]
            await conn.execute(
                "UPDATE businesses SET owner_telegram_id = $1, org_id = $2, status = 'sold', chat_id = $3 WHERE id = $4",
                buyer_id, org_id, chat_id, business_id,
            )
            return seller_id, price
        else:
            cursor = await conn.execute(
                "SELECT * FROM businesses WHERE id = ? AND status = 'player_listed'", (business_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            seller_id = row["owner_telegram_id"]
            price = row["price"]
            await conn.execute(
                "UPDATE businesses SET owner_telegram_id = ?, org_id = ?, status = 'sold', chat_id = ? WHERE id = ?",
                (buyer_id, org_id, chat_id, business_id),
            )
            await conn.commit()
            return seller_id, price
    finally:
        await conn.close()


async def get_business_by_position(chat_id: int, position: int) -> dict | None:
    businesses = await get_available_businesses(chat_id=chat_id)
    if position < 1 or position > len(businesses):
        return None
    return businesses[position - 1]


async def get_business_type_by_name(name: str) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT * FROM business_types WHERE LOWER(name) = LOWER($1)", name,
            )
            return dict(row) if row else None
        else:
            cursor = await conn.execute(
                "SELECT * FROM business_types WHERE LOWER(name) = LOWER(?)", (name,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()


async def set_business_manager(business_id: int, manager_id: int | None, chat_id: int = 0, salary: int = 0) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute(
                "UPDATE businesses SET manager_telegram_id = $1, manager_salary = $2 WHERE id = $3",
                manager_id, salary, business_id,
            )
            return "UPDATE 1" in (result or "")
        else:
            cursor = await conn.execute(
                "UPDATE businesses SET manager_telegram_id = ?, manager_salary = ? WHERE id = ?",
                (manager_id, salary, business_id),
            )
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def get_businesses_by_manager(manager_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                BUSINESS_SELECT + " WHERE b.manager_telegram_id = $1 AND b.manager_salary > 0",
                manager_id,
            )
        else:
            cursor = await conn.execute(
                BUSINESS_SELECT + " WHERE b.manager_telegram_id = ? AND b.manager_salary > 0",
                (manager_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def record_business_delivery(business_id: int) -> tuple[bool, str]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT materials, is_open FROM businesses WHERE id = $1 FOR UPDATE",
                business_id,
            )
            if not row:
                return False, "❌ Бизнес не найден"
            if row["is_open"] == "0":
                return False, "❌ Бизнес закрыт — нет материалов"
            if (row["materials"] or 0) <= 0:
                await conn.execute("UPDATE businesses SET is_open = '0' WHERE id = $1", business_id)
                return False, "❌ Материалы закончились, бизнес закрыт"
            await conn.execute(
                "UPDATE businesses SET materials = materials - 1, delivery_count = delivery_count + 1, "
                "last_delivery = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id = $1",
                business_id,
            )
            return True, ""
        else:
            cursor = await conn.execute(
                "SELECT materials, is_open FROM businesses WHERE id = ?",
                (business_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False, "❌ Бизнес не найден"
            if row["is_open"] == "0":
                return False, "❌ Бизнес закрыт — нет материалов"
            if (row["materials"] or 0) <= 0:
                await conn.execute("UPDATE businesses SET is_open = '0' WHERE id = ?", (business_id,))
                await conn.commit()
                return False, "❌ Материалы закончились, бизнес закрыт"
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await conn.execute(
                "UPDATE businesses SET materials = materials - 1, delivery_count = delivery_count + 1, last_delivery = ? WHERE id = ?",
                (now_str, business_id),
            )
            await conn.commit()
            return True, ""
    finally:
        await conn.close()


async def get_business_profit(business_id: int) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT b.profit, b.delivery_count, bt.base_profit FROM businesses b "
                "JOIN business_types bt ON bt.id = b.business_type_id WHERE b.id = $1",
                business_id,
            )
            if not row:
                return 0
            return row["base_profit"] + (row["delivery_count"] or 0) * int(row["base_profit"] * 0.1)
        else:
            cursor = await conn.execute(
                "SELECT b.profit, b.delivery_count, bt.base_profit FROM businesses b "
                "JOIN business_types bt ON bt.id = b.business_type_id WHERE b.id = ?",
                (business_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return 0
            return row["base_profit"] + (row["delivery_count"] or 0) * int(row["base_profit"] * 0.1)
    finally:
        await conn.close()


async def purchase_business_materials(business_id: int, amount: int) -> tuple[bool, int, int]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT materials, max_materials, materials_cost FROM businesses WHERE id = $1 FOR UPDATE",
                business_id,
            )
            if not row:
                return False, 0, 0
            materials = row["materials"] or 0
            max_mat = row["max_materials"] or 100
            cost_per_unit = row["materials_cost"] or 0
            space = max_mat - materials
            if space <= 0:
                return False, 0, 0
            can_buy = min(amount, space)
            total_cost = can_buy * (cost_per_unit or 100)
            await conn.execute(
                "UPDATE businesses SET materials = materials + $1, materials_cost = $2, is_open = '1' WHERE id = $3",
                can_buy, cost_per_unit or 100, business_id,
            )
            return True, can_buy, total_cost
        else:
            cursor = await conn.execute(
                "SELECT materials, max_materials, materials_cost FROM businesses WHERE id = ?",
                (business_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False, 0, 0
            materials = row["materials"] or 0
            max_mat = row["max_materials"] or 100
            cost_per_unit = row["materials_cost"] or 0
            space = max_mat - materials
            if space <= 0:
                return False, 0, 0
            can_buy = min(amount, space)
            total_cost = can_buy * (cost_per_unit or 100)
            await conn.execute(
                "UPDATE businesses SET materials = materials + ?, materials_cost = ?, is_open = '1' WHERE id = ?",
                (can_buy, cost_per_unit or 100, business_id),
            )
            await conn.commit()
            return True, can_buy, total_cost
    finally:
        await conn.close()


async def order_business_materials(business_id: int, amount: int) -> tuple[bool, int]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT materials_cost, max_materials, pending_supplies FROM businesses WHERE id = $1 FOR UPDATE",
                business_id,
            )
            if not row:
                return False, 0
            max_mat = row["max_materials"] or 100
            pending = row["pending_supplies"] or 0
            cost_per_unit = row["materials_cost"] or 0
            space = max_mat - pending
            if space <= 0:
                return False, 0
            can_buy = min(amount, space)
            total = can_buy * cost_per_unit
            await conn.execute(
                "UPDATE businesses SET pending_supplies = pending_supplies + $1 WHERE id = $2",
                can_buy, business_id,
            )
            return True, total
        else:
            cursor = await conn.execute(
                "SELECT materials_cost, max_materials, pending_supplies FROM businesses WHERE id = ?",
                (business_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False, 0
            max_mat = row["max_materials"] or 100
            pending = row["pending_supplies"] or 0
            cost_per_unit = row["materials_cost"] or 0
            space = max_mat - pending
            if space <= 0:
                return False, 0
            can_buy = min(amount, space)
            total = can_buy * cost_per_unit
            await conn.execute(
                "UPDATE businesses SET pending_supplies = pending_supplies + ? WHERE id = ?",
                (can_buy, business_id),
            )
            await conn.commit()
            return True, total
    finally:
        await conn.close()


async def confirm_business_delivery(business_id: int, manager_id: int) -> tuple[bool, str]:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT pending_supplies, manager_telegram_id, is_open FROM businesses WHERE id = $1 FOR UPDATE",
                business_id,
            )
            if not row:
                return False, "❌ Бизнес не найден"
            if row["manager_telegram_id"] != manager_id:
                return False, "❌ Вы не менеджер этого бизнеса"
            pending = row["pending_supplies"] or 0
            if pending <= 0:
                return False, "❌ Нет ожидающих поставок"
            await conn.execute(
                "UPDATE businesses SET materials = materials + $1, pending_supplies = 0, is_open = '1' WHERE id = $2",
                pending, business_id,
            )
            return True, ""
        else:
            cursor = await conn.execute(
                "SELECT pending_supplies, manager_telegram_id, is_open FROM businesses WHERE id = ?",
                (business_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return False, "❌ Бизнес не найден"
            if row["manager_telegram_id"] != manager_id:
                return False, "❌ Вы не менеджер этого бизнеса"
            pending = row["pending_supplies"] or 0
            if pending <= 0:
                return False, "❌ Нет ожидающих поставок"
            await conn.execute(
                "UPDATE businesses SET materials = materials + ?, pending_supplies = 0, is_open = '1' WHERE id = ?",
                (pending, business_id),
            )
            await conn.commit()
            return True, ""
    finally:
        await conn.close()


async def process_business_profit_tick() -> int:
    conn = await get_conn()
    total = 0
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT id, profit, owner_telegram_id FROM businesses WHERE is_open = '1' AND materials > 0 FOR UPDATE"
            )
            for row in rows:
                profit = row["profit"] or 0
                if profit <= 0 or not row["owner_telegram_id"]:
                    continue
                await conn.execute(
                    "UPDATE businesses SET materials = materials - 1, delivery_count = delivery_count + 1, "
                    "total_profit_earned = total_profit_earned + $1 WHERE id = $2",
                    profit, row["id"],
                )
                await conn.execute(
                    "UPDATE users SET balance = balance + $1 WHERE telegram_id = $2",
                    profit, row["owner_telegram_id"],
                )
                total += profit
            if rows:
                await conn.execute(
                    "UPDATE businesses SET is_open = '0' WHERE is_open = '1' AND materials <= 0"
                )
        else:
            cursor = await conn.execute(
                "SELECT id, profit, owner_telegram_id FROM businesses WHERE is_open = '1' AND materials > 0"
            )
            rows = await cursor.fetchall()
            for row in rows:
                profit = row["profit"] or 0
                if profit <= 0 or not row["owner_telegram_id"]:
                    continue
                await conn.execute(
                    "UPDATE businesses SET materials = materials - 1, delivery_count = delivery_count + 1, "
                    "total_profit_earned = total_profit_earned + ? WHERE id = ?",
                    (profit, row["id"]),
                )
                await conn.execute(
                    "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
                    (profit, row["owner_telegram_id"]),
                )
                total += profit
            await conn.execute(
                "UPDATE businesses SET is_open = '0' WHERE is_open = '1' AND materials <= 0"
            )
            await conn.commit()
        return total
    finally:
        await conn.close()



# ── Betting functions ──

async def create_betting_event(chat_id: int, title: str, commission_pct: int = 5) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO betting_events (chat_id, title, commission_pct) VALUES ($1, $2, $3) RETURNING id",
                chat_id, title, commission_pct,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO betting_events (chat_id, title, commission_pct) VALUES (?, ?, ?)",
                (chat_id, title, commission_pct),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        await conn.close()


async def get_betting_event(event_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM betting_events WHERE id = $1", event_id)
        else:
            cursor = await conn.execute("SELECT * FROM betting_events WHERE id = ?", (event_id,))
            row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_active_betting_events(chat_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM betting_events WHERE chat_id = $1 AND status IN ('open', 'closed') ORDER BY created_at DESC",
                chat_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM betting_events WHERE chat_id = ? AND status IN ('open', 'closed') ORDER BY created_at DESC",
                (chat_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def set_betting_event_status(event_id: int, status: str) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute("UPDATE betting_events SET status = $1 WHERE id = $2", status, event_id)
            return "UPDATE 1" in (result or "")
        else:
            cursor = await conn.execute("UPDATE betting_events SET status = ? WHERE id = ?", (status, event_id))
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def add_betting_option(event_id: int, label: str) -> int:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO betting_options (event_id, label) VALUES ($1, $2) RETURNING id",
                event_id, label,
            )
            return row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO betting_options (event_id, label) VALUES (?, ?)",
                (event_id, label),
            )
            await conn.commit()
            return cursor.lastrowid
    finally:
        await conn.close()


async def get_betting_options(event_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM betting_options WHERE event_id = $1 ORDER BY id", event_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM betting_options WHERE event_id = ? ORDER BY id", (event_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def set_winning_option(event_id: int, option_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            await conn.execute("UPDATE betting_options SET is_winner = FALSE WHERE event_id = $1", event_id)
            result = await conn.execute("UPDATE betting_options SET is_winner = TRUE WHERE id = $1 AND event_id = $2", option_id, event_id)
            return "UPDATE 1" in (result or "")
        else:
            await conn.execute("UPDATE betting_options SET is_winner = 0 WHERE event_id = ?", (event_id,))
            cursor = await conn.execute("UPDATE betting_options SET is_winner = 1 WHERE id = ? AND event_id = ?", (option_id, event_id))
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def place_bet(event_id: int, option_id: int, user_id: int, amount: int) -> tuple[bool, str]:
    conn = await get_conn()
    try:
        if _is_pg:
            ev = await conn.fetchrow("SELECT status FROM betting_events WHERE id = $1 FOR UPDATE", event_id)
            if not ev:
                return False, "❌ Событие не найдено"
            if ev["status"] != "open":
                return False, "❌ Приём ставок закрыт"
            opt = await conn.fetchrow("SELECT id FROM betting_options WHERE id = $1 AND event_id = $2", option_id, event_id)
            if not opt:
                return False, "❌ Исход не найден"
            await conn.execute(
                "INSERT INTO bets (event_id, option_id, user_id, amount) VALUES ($1, $2, $3, $4)",
                event_id, option_id, user_id, amount,
            )
        else:
            cursor = await conn.execute("SELECT status FROM betting_events WHERE id = ?", (event_id,))
            ev = await cursor.fetchone()
            if not ev:
                return False, "❌ Событие не найдено"
            if ev["status"] != "open":
                return False, "❌ Приём ставок закрыт"
            cursor = await conn.execute("SELECT id FROM betting_options WHERE id = ? AND event_id = ?", (option_id, event_id))
            opt = await cursor.fetchone()
            if not opt:
                return False, "❌ Исход не найден"
            await conn.execute(
                "INSERT INTO bets (event_id, option_id, user_id, amount) VALUES (?, ?, ?, ?)",
                (event_id, option_id, user_id, amount),
            )
            await conn.commit()
        return True, ""
    finally:
        await conn.close()


async def settle_betting_event(event_id: int) -> dict:
    conn = await get_conn()
    try:
        ev = await get_betting_event(event_id)
        if not ev:
            return {"ok": False, "error": "Событие не найдено"}
        if ev["status"] == "settled":
            return {"ok": False, "error": "Событие уже рассчитано"}
        options = await get_betting_options(event_id)
        winner = [o for o in options if o.get("is_winner") or o.get("is_winner") == 1]
        if not winner:
            return {"ok": False, "error": "Не указан победитель"}

        total_pool = 0
        win_pool = 0
        win_bets = []
        for opt in options:
            bets_list = await get_bets_by_option(event_id, opt["id"])
            opt_total = sum(b["amount"] for b in bets_list)
            total_pool += opt_total
            if opt["id"] == winner[0]["id"]:
                win_pool = opt_total
                win_bets = bets_list

        if total_pool <= 0:
            await set_betting_event_status(event_id, "settled")
            if _is_pg:
                await conn.execute(
                    "UPDATE betting_events SET settled_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id = $1",
                    event_id,
                )
            else:
                await conn.execute(
                    "UPDATE betting_events SET settled_at = datetime('now', 'localtime') WHERE id = ?",
                    (event_id,),
                )
                await conn.commit()
            return {"ok": True, "total_pool": 0, "payouts": [], "commission": 0, "net_pool": 0}

        commission = total_pool * ev["commission_pct"] // 100
        net_pool = total_pool - commission

        payouts = []
        if win_pool > 0 and win_bets:
            for b in win_bets:
                share = b["amount"] * net_pool // win_pool
                if share > 0:
                    await update_balance(b["user_id"], share, ev["chat_id"])
                    payouts.append({"user_id": b["user_id"], "amount": share, "bet": b["amount"]})

        if _is_pg:
            await conn.execute(
                "UPDATE betting_events SET status = 'settled', settled_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id = $1",
                event_id,
            )
        else:
            await conn.execute(
                "UPDATE betting_events SET status = 'settled', settled_at = datetime('now', 'localtime') WHERE id = ?",
                (event_id,),
            )
            await conn.commit()

        return {
            "ok": True,
            "total_pool": total_pool,
            "commission": commission,
            "net_pool": net_pool,
            "win_pool": win_pool,
            "payouts": payouts,
        }
    finally:
        await conn.close()


async def get_bets_by_option(event_id: int, option_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM bets WHERE event_id = $1 AND option_id = $2", event_id, option_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM bets WHERE event_id = ? AND option_id = ?", (event_id, option_id),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_betting_history(chat_id: int, limit: int = 5) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT * FROM betting_events WHERE chat_id = $1 AND status = 'settled' ORDER BY settled_at DESC LIMIT $2",
                chat_id, limit,
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM betting_events WHERE chat_id = ? AND status = 'settled' ORDER BY settled_at DESC LIMIT ?",
                (chat_id, limit),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def delete_bet(bet_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute("DELETE FROM bets WHERE id = $1", bet_id)
            return "DELETE 1" in (result or "")
        else:
            cursor = await conn.execute("DELETE FROM bets WHERE id = ?", (bet_id,))
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def get_all_event_bets(event_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT b.id, b.user_id, b.amount, b.option_id, bo.label FROM bets b JOIN betting_options bo ON bo.id = b.option_id WHERE b.event_id = $1 ORDER BY b.id",
                event_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT b.id, b.user_id, b.amount, b.option_id, bo.label FROM bets b JOIN betting_options bo ON bo.id = b.option_id WHERE b.event_id = ? ORDER BY b.id",
                (event_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_event_bets_by_user(event_id: int, user_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT b.*, bo.label FROM bets b JOIN betting_options bo ON bo.id = b.option_id WHERE b.event_id = $1 AND b.user_id = $2",
                event_id, user_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT b.*, bo.label FROM bets b JOIN betting_options bo ON bo.id = b.option_id WHERE b.event_id = ? AND b.user_id = ?",
                (event_id, user_id),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ── Insurance functions ──

COVERAGE_TYPES = {
    "базовый": {"pct": 50, "cost_pct": 5},
    "стандарт": {"pct": 80, "cost_pct": 10},
    "премиум": {"pct": 100, "cost_pct": 20},
}


async def buy_insurance(vehicle_id: int, user_id: int, coverage_type: str) -> dict:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1 AND owner_telegram_id = $2 AND status = 'sold'", vehicle_id, user_id)
        else:
            cursor = await conn.execute("SELECT * FROM vehicles WHERE id = ? AND owner_telegram_id = ? AND status = 'sold'", (vehicle_id, user_id))
            row = await cursor.fetchone()
        if not row:
            return {"ok": False, "error": "Авто не найдено или не принадлежит вам"}
        v = dict(row)

        ct = COVERAGE_TYPES.get(coverage_type)
        if not ct:
            return {"ok": False, "error": "Тип страховки: базовый/стандарт/премиум"}

        if _is_pg:
            existing = await conn.fetchrow("SELECT id FROM insurance WHERE vehicle_id = $1 AND status = 'active'", vehicle_id)
        else:
            cursor = await conn.execute("SELECT id FROM insurance WHERE vehicle_id = ? AND status = 'active'", (vehicle_id,))
            existing = await cursor.fetchone()
        if existing:
            return {"ok": False, "error": "На это авто уже есть активная страховка"}

        premium = v["price"] * ct["cost_pct"] // 100
        if premium < 1:
            premium = 1

        if _is_pg:
            row = await conn.fetchrow(
                "INSERT INTO insurance (vehicle_id, owner_telegram_id, coverage_type, coverage_percent, premium_paid, vehicle_value, end_date) "
                "VALUES ($1, $2, $3, $4, $5, $6, to_char(NOW() + INTERVAL '30 days', 'YYYY-MM-DD HH24:MI:SS')) RETURNING id",
                vehicle_id, user_id, coverage_type, ct["pct"], premium, v["price"],
            )
            ins_id = row["id"]
        else:
            cursor = await conn.execute(
                "INSERT INTO insurance (vehicle_id, owner_telegram_id, coverage_type, coverage_percent, premium_paid, vehicle_value, end_date) "
                "VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+30 days'))",
                (vehicle_id, user_id, coverage_type, ct["pct"], premium, v["price"]),
            )
            await conn.commit()
            ins_id = cursor.lastrowid

        return {
            "ok": True,
            "ins_id": ins_id,
            "vehicle": f"{v['year']} {v['make']} {v['model']}",
            "coverage": f"{coverage_type} ({ct['pct']}%)",
            "premium": premium,
            "value": v["price"],
        }
    finally:
        await conn.close()


async def get_user_insurances(user_id: int) -> list:
    conn = await get_conn()
    try:
        if _is_pg:
            rows = await conn.fetch(
                "SELECT i.*, v.make, v.model, v.year FROM insurance i JOIN vehicles v ON v.id = i.vehicle_id WHERE i.owner_telegram_id = $1 ORDER BY i.id DESC",
                user_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT i.*, v.make, v.model, v.year FROM insurance i JOIN vehicles v ON v.id = i.vehicle_id WHERE i.owner_telegram_id = ? ORDER BY i.id DESC",
                (user_id,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_insurance(insurance_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT i.*, v.make, v.model, v.year FROM insurance i JOIN vehicles v ON v.id = i.vehicle_id WHERE i.id = $1",
                insurance_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT i.*, v.make, v.model, v.year FROM insurance i JOIN vehicles v ON v.id = i.vehicle_id WHERE i.id = ?",
                (insurance_id,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def process_insurance_payout(insurance_id: int) -> dict:
    conn = await get_conn()
    try:
        ins = await get_insurance(insurance_id)
        if not ins:
            return {"ok": False, "error": "Страховка не найдена"}
        if ins["status"] != "active":
            return {"ok": False, "error": f"Статус: {ins['status']}"}

        payout = ins["vehicle_value"] * ins["coverage_percent"] // 100
        user_id = ins["owner_telegram_id"]
        vehicle_id = ins["vehicle_id"]

        if _is_pg:
            await conn.execute("UPDATE insurance SET status = 'claimed' WHERE id = $1", insurance_id)
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, org_id = NULL, status = 'available', chat_id = 0 WHERE id = $1 AND status = 'sold'", vehicle_id)
        else:
            await conn.execute("UPDATE insurance SET status = 'claimed' WHERE id = ?", (insurance_id,))
            await conn.execute("UPDATE vehicles SET owner_telegram_id = NULL, org_id = NULL, status = 'available', chat_id = 0 WHERE id = ? AND status = 'sold'", (vehicle_id,))
            await conn.commit()

        veh_chat_id = 0
        if _is_pg:
            row = await conn.fetchrow("SELECT chat_id FROM vehicles WHERE id = $1", vehicle_id)
            if row:
                veh_chat_id = row["chat_id"]
        else:
            cursor = await conn.execute("SELECT chat_id FROM vehicles WHERE id = ?", (vehicle_id,))
            row = await cursor.fetchone()
            if row:
                veh_chat_id = row["chat_id"]

        await update_balance(user_id, payout, veh_chat_id)
        await add_transaction("insurance_payout", None, user_id, payout,
                              f"Страховая выплата #{insurance_id} — {ins.get('year','')} {ins.get('make','')} {ins.get('model','')} (${payout:,})")

        return {
            "ok": True,
            "ins_id": insurance_id,
            "user_id": user_id,
            "vehicle": f"{ins.get('year','')} {ins.get('make','')} {ins.get('model','')}",
            "payout": payout,
            "coverage_pct": ins["coverage_percent"],
        }
    finally:
        await conn.close()


async def delete_insurance(insurance_id: int) -> bool:
    conn = await get_conn()
    try:
        if _is_pg:
            result = await conn.execute("DELETE FROM insurance WHERE id = $1", insurance_id)
            return "DELETE 1" in (result or "")
        else:
            cursor = await conn.execute("DELETE FROM insurance WHERE id = ?", (insurance_id,))
            await conn.commit()
            return cursor.rowcount > 0
    finally:
        await conn.close()


async def get_vehicle_insurance(vehicle_id: int) -> dict | None:
    conn = await get_conn()
    try:
        if _is_pg:
            row = await conn.fetchrow(
                "SELECT i.*, v.make, v.model, v.year FROM insurance i JOIN vehicles v ON v.id = i.vehicle_id WHERE i.vehicle_id = $1 AND i.status = 'active'",
                vehicle_id,
            )
        else:
            cursor = await conn.execute(
                "SELECT i.*, v.make, v.model, v.year FROM insurance i JOIN vehicles v ON v.id = i.vehicle_id WHERE i.vehicle_id = ? AND i.status = 'active'",
                (vehicle_id,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()
