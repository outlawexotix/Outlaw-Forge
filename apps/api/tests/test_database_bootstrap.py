import asyncio

import aiosqlite

from app.db.database import get_db


def test_get_db_initializes_schema_when_lifespan_was_skipped(tmp_path):
    db_path = tmp_path / "bootstrap.db"

    async def exercise():
        connection = get_db(str(db_path))
        async for conn in connection:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            tables = {row[0] for row in await cursor.fetchall()}
            await conn.close()
            return tables

    tables = asyncio.run(exercise())

    assert {
        "projects",
        "source_files",
        "working_models",
        "printer_profiles",
        "operations",
    }.issubset(tables)


def test_get_db_repairs_partial_schema(tmp_path):
    db_path = tmp_path / "partial.db"

    async def create_partial_schema():
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY)")
            await conn.commit()

    async def exercise():
        await create_partial_schema()
        connection = get_db(str(db_path))
        async for conn in connection:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            tables = {row[0] for row in await cursor.fetchall()}
            await conn.close()
            return tables

    tables = asyncio.run(exercise())

    assert "printer_profiles" in tables
