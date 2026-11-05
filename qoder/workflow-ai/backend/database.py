import aiosqlite
from datetime import datetime
from backend.config import DATABASE_PATH
import os


async def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS work_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '[]',
                date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weekly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                report TEXT NOT NULL,
                summary TEXT NOT NULL,
                statistics TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def create_work_log(title: str, content: str, category: str, tags: list, date: str) -> int:
    now = datetime.now().isoformat()
    import json
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO work_logs (title, content, category, tags, date, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, content, category, json.dumps(tags, ensure_ascii=False), date, now, now)
        )
        await db.commit()
        return cursor.lastrowid


async def get_work_log(log_id: int) -> dict | None:
    import json
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM work_logs WHERE id = ?", (log_id,))
        row = await cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "category": row["category"],
                "tags": json.loads(row["tags"]),
                "date": row["date"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None


async def list_work_logs(limit: int = 50, offset: int = 0, category: str = None, date_from: str = None, date_to: str = None) -> list[dict]:
    import json
    query = "SELECT * FROM work_logs WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    query += " ORDER BY date DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "category": row["category"],
                "tags": json.loads(row["tags"]),
                "date": row["date"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
            for row in rows
        ]


async def update_work_log(log_id: int, **kwargs) -> bool:
    import json
    now = datetime.now().isoformat()
    sets = []
    params = []
    for key, value in kwargs.items():
        if key == "tags":
            sets.append("tags = ?")
            params.append(json.dumps(value, ensure_ascii=False))
        else:
            sets.append(f"{key} = ?")
            params.append(value)
    sets.append("updated_at = ?")
    params.append(now)
    params.append(log_id)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(f"UPDATE work_logs SET {', '.join(sets)} WHERE id = ?", params)
        await db.commit()
        return True


async def delete_work_log(log_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM work_logs WHERE id = ?", (log_id,))
        await db.commit()
        return True


async def get_work_logs_by_date_range(start_date: str, end_date: str) -> list[dict]:
    import json
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM work_logs WHERE date >= ? AND date <= ? ORDER BY date ASC, created_at ASC",
            (start_date, end_date)
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "category": row["category"],
                "tags": json.loads(row["tags"]),
                "date": row["date"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
            for row in rows
        ]


async def get_statistics(start_date: str, end_date: str) -> dict:
    import json
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) as total, COUNT(DISTINCT date) as active_days, category FROM work_logs WHERE date >= ? AND date <= ? GROUP BY category",
            (start_date, end_date)
        )
        rows = await cursor.fetchall()
        total = 0
        active_days = 0
        categories = {}
        for row in rows:
            total += row[0]
            active_days = max(active_days, row[1])
            categories[row[2]] = row[0]

        cursor2 = await db.execute(
            "SELECT COUNT(*) FROM work_logs WHERE date >= ? AND date <= ?",
            (start_date, end_date)
        )
        total = (await cursor2.fetchone())[0]

        return {
            "total_logs": total,
            "active_days": active_days,
            "categories": categories
        }
