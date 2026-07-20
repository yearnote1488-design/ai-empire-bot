import aiosqlite

DB_NAME = "database/database.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                requests INTEGER DEFAULT 0,
                plan TEXT DEFAULT 'FREE'
            )
        """)
        await db.commit()


async def add_user(telegram_id, username, first_name):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users
            (telegram_id, username, first_name)
            VALUES (?, ?, ?)
        """, (telegram_id, username, first_name))
        await db.commit()


async def get_user(telegram_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT first_name, username, requests, plan
            FROM users
            WHERE telegram_id = ?
        """, (telegram_id,))

        user = await cursor.fetchone()
        return user