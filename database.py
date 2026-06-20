import aiosqlite
from typing import Optional

DATABASE = "bank.db"


async def get_db():
    db = await aiosqlite.connect(DATABASE)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript("""
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
        """)
        await db.commit()
    finally:
        await db.close()


async def get_or_create_user(telegram_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = await cursor.fetchone()
        if not user:
            await db.execute(
                "INSERT INTO users (telegram_id, username, first_name, balance) VALUES (?, ?, ?, 0)",
                (telegram_id, username, first_name),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            user = await cursor.fetchone()
        else:
            needs_update = False
            updates = []
            if username and user["username"] != username:
                updates.append(f"username = '{username}'")
                needs_update = True
            if first_name and user["first_name"] != first_name:
                updates.append(f"first_name = '{first_name}'")
                needs_update = True
            if needs_update:
                await db.execute(
                    "UPDATE users SET username = ?, first_name = ? WHERE telegram_id = ?",
                    (username or user["username"], first_name or user["first_name"], telegram_id),
                )
                await db.commit()
                cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
                user = await cursor.fetchone()
        return dict(user)
    finally:
        await db.close()


async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = await cursor.fetchone()
        return dict(user) if user else None
    finally:
        await db.close()


async def get_user_by_username(username: str) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = await cursor.fetchone()
        return dict(user) if user else None
    finally:
        await db.close()


async def update_balance(telegram_id: int, amount: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
            (amount, telegram_id),
        )
        await db.commit()
    finally:
        await db.close()


async def set_balance(telegram_id: int, amount: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET balance = ? WHERE telegram_id = ?",
            (amount, telegram_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_balance(telegram_id: int) -> int:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return row["balance"] if row else 0
    finally:
        await db.close()


async def add_transaction(type_: str, sender_id: Optional[int], receiver_id: Optional[int], amount: int, description: str = "") -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO transactions (type, sender_telegram_id, receiver_telegram_id, amount, description) VALUES (?, ?, ?, ?, ?)",
            (type_, sender_id, receiver_id, amount, description),
        )
        await db.commit()
    finally:
        await db.close()


async def get_transactions(telegram_id: int, limit: int = 10) -> list:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM transactions WHERE sender_telegram_id = ? OR receiver_telegram_id = ? ORDER BY created_at DESC LIMIT ?",
            (telegram_id, telegram_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def create_credit_request(user_telegram_id: int, amount: int) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO credit_requests (user_telegram_id, amount) VALUES (?, ?)",
            (user_telegram_id, amount),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_credit_requests(status: str = "pending") -> list:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM credit_requests WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_credit_request(request_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM credit_requests WHERE id = ?", (request_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_credit_request(request_id: int, status: str) -> None:
    db = await get_db()
    try:
        await db.execute("UPDATE credit_requests SET status = ? WHERE id = ?", (status, request_id))
        await db.commit()
    finally:
        await db.close()


async def create_deposit_request(user_telegram_id: int, amount: int) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO deposit_requests (user_telegram_id, amount) VALUES (?, ?)",
            (user_telegram_id, amount),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_deposit_requests(status: str = "pending") -> list:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM deposit_requests WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_deposit_request(request_id: int) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM deposit_requests WHERE id = ?", (request_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_deposit_request(request_id: int, status: str) -> None:
    db = await get_db()
    try:
        await db.execute("UPDATE deposit_requests SET status = ? WHERE id = ?", (status, request_id))
        await db.commit()
    finally:
        await db.close()
