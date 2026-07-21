#!/usr/bin/env python3
"""One-time migration script: Render PostgreSQL -> Supabase.

Usage:
  python migrate.py
  
Requires SUPABASE_URL or DATABASE_URL environment variable set.
"""
import asyncio, os, logging, sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("migrate")

DUMP_FILE = os.path.join(os.path.dirname(__file__), "migrate_supabase.sql")


async def run():
    url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        log.error("SUPABASE_URL or DATABASE_URL not set")
        return False
    if not os.path.exists(DUMP_FILE):
        log.error("Dump file not found at %s", DUMP_FILE)
        return False

    import asyncpg
    conn = await asyncpg.connect(url)
    try:
        log.info("Connected, reading dump file...")
        with open(DUMP_FILE, "r", encoding="utf-8") as f:
            sql = f.read()

        statements = sql.split(";")
        total = len(statements)
        ok = 0
        for i, stmt in enumerate(statements):
            stmt = stmt.strip()
            if not stmt or stmt.startswith("--"):
                continue
            try:
                await conn.execute(stmt)
                ok += 1
            except Exception as e:
                log.warning("Stmt %d/%d failed: %s", i + 1, total, e)

        log.info("Done: %d/%d statements executed", ok, total)
        return True
    finally:
        await conn.close()


if __name__ == "__main__":
    success = asyncio.run(run())
    sys.exit(0 if success else 1)
