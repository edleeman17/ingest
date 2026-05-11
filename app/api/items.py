import aiosqlite
from api.db import DB_PATH


async def list_items(done=None, source=None, limit=50, offset=0):
    conditions, params = [], []
    if done is not None:
        conditions.append("done = ?"); params.append(done)
    if source:
        conditions.append("source = ?"); params.append(source)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            f"SELECT id,source,raw_text,summary,tags,created_at,done,group_id,position FROM items {where} ORDER BY done ASC, id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )).fetchall()
        count = (await (await db.execute(f"SELECT COUNT(*) FROM items {where}", params)).fetchone())[0]
    return [dict(r) for r in rows], count


async def list_sources():
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (await db.execute("SELECT DISTINCT source FROM items ORDER BY source")).fetchall()
    return [r[0] for r in rows]


async def set_done(item_id: int, done: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE items SET done=? WHERE id=?", (1 if done else 0, item_id))
        await db.commit()


async def set_group(item_id: int, group_id: int | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE items SET group_id=?, position=NULL WHERE id=?", (group_id, item_id))
        await db.commit()


async def set_positions(group_id: int, ordered_ids: list[int]):
    async with aiosqlite.connect(DB_PATH) as db:
        for pos, item_id in enumerate(ordered_ids):
            await db.execute(
                "UPDATE items SET position=? WHERE id=? AND group_id=?",
                (pos, item_id, group_id)
            )
        await db.commit()


async def list_groups():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        groups = await (await db.execute(
            "SELECT id, name, created_at FROM groups ORDER BY id ASC"
        )).fetchall()
        result = []
        for g in groups:
            items = await (await db.execute(
                "SELECT id,source,raw_text,summary,tags,created_at,done,group_id,position FROM items WHERE group_id=? ORDER BY done ASC, CASE WHEN position IS NULL THEN 1 ELSE 0 END, position ASC, id DESC",
                (g["id"],)
            )).fetchall()
            result.append({**dict(g), "items": [dict(i) for i in items]})
    return result


async def create_group(name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO groups (name) VALUES (?)", (name,))
        await db.commit()
        return cursor.lastrowid


async def rename_group(group_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE groups SET name=? WHERE id=?", (name, group_id))
        await db.commit()


async def delete_group(group_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE items SET group_id=NULL, position=NULL WHERE group_id=?", (group_id,))
        await db.execute("DELETE FROM groups WHERE id=?", (group_id,))
        await db.commit()
