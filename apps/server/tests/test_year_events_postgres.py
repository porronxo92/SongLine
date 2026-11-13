"""Opt-in checks against a disposable database migrated through 0004.

TEST_DATABASE_URL=postgresql+asyncpg://... pytest tests/test_year_events_postgres.py
"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.catalog.year_events import PostgresYearEventRepository, read_year_events


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="requires disposable PostgreSQL")
async def test_seeded_catalog_constraints_and_enabled_filter_survive_new_connection():
    repo = PostgresYearEventRepository(os.environ["TEST_DATABASE_URL"])
    test_id = f"integration-{uuid4()}"
    try:
        events = await repo.load_enabled()
        assert {e.id for e in read_year_events()} <= {e.id for e in events}
        assert min(e.year for e in events) == 1937 and max(e.year for e in events) == 2026
        insert = text("INSERT INTO year_events(id,year,category,text,source_url,occurred_on,enabled) "
                      "VALUES (:id,1990,'science',:hint,'https://example.org',:occurred,false)")
        from datetime import date

        for hint, occurred in (("En 1990 ocurrió un acontecimiento.", date(1990, 1, 1)),
                               ("Texto correcto sin un año explícito.", date(1991, 1, 1))):
            with pytest.raises(IntegrityError):
                async with repo.engine.begin() as conn:
                    await conn.execute(insert, {"id": test_id, "hint": hint, "occurred": occurred})
        async with repo.engine.begin() as conn:
            await conn.execute(insert, {"id": test_id, "hint": "Un acontecimiento oculto para comprobar el filtro.", "occurred": date(1990, 1, 1)})
        other = PostgresYearEventRepository(os.environ["TEST_DATABASE_URL"])
        try:
            assert test_id not in {e.id for e in await other.load_enabled()}
        finally:
            await other.close()
    finally:
        async with repo.engine.begin() as conn:
            await conn.execute(text("DELETE FROM year_events WHERE id = :id"), {"id": test_id})
        await repo.close()
