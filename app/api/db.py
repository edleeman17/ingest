import aiosqlite
from pathlib import Path

DB_PATH = Path("/db/synthetic-wall.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                summary TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                done INTEGER DEFAULT 0,
                group_id INTEGER REFERENCES groups(id),
                position INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cols = [r[1] for r in await (await db.execute("PRAGMA table_info(items)")).fetchall()]
        if "group_id" not in cols:
            await db.execute("ALTER TABLE items ADD COLUMN group_id INTEGER REFERENCES groups(id)")
        if "position" not in cols:
            await db.execute("ALTER TABLE items ADD COLUMN position INTEGER")
        await db.commit()


async def insert_item(source: str, raw_text: str, summary: str, tags: list[str]) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO items (source, raw_text, summary, tags) VALUES (?, ?, ?, ?)",
            (source, raw_text, summary, ",".join(tags))
        )
        await db.commit()
        return cursor.lastrowid
