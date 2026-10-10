"""Room snapshots (JSON). Postgres in production, nothing in dev/tests (PERSISTENCE=none)."""

from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class Persistence(Protocol):
    async def save(self, code: str, state_json: str) -> None: ...
    async def delete(self, code: str) -> None: ...
    async def load_all(self) -> dict[str, str]: ...


class NullPersistence:
    async def save(self, code: str, state_json: str) -> None:
        return None

    async def delete(self, code: str) -> None:
        return None

    async def load_all(self) -> dict[str, str]:
        return {}


class MemoryPersistence:
    """Test helper: keeps snapshots in a dict."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def save(self, code: str, state_json: str) -> None:
        self.data[code] = state_json

    async def delete(self, code: str) -> None:
        self.data.pop(code, None)

    async def load_all(self) -> dict[str, str]:
        return dict(self.data)


class PostgresPersistence:
    """Table `room_snapshots(code PK, state JSONB, updated_at)` (see the Alembic migration)."""

    def __init__(self, database_url: str) -> None:
        from sqlalchemy.ext.asyncio import create_async_engine

        self.engine = create_async_engine(database_url, pool_pre_ping=True)

    async def save(self, code: str, state_json: str) -> None:
        from sqlalchemy import text

        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO room_snapshots (code, state, updated_at) VALUES (:c, CAST(:s AS jsonb), now()) "
                    "ON CONFLICT (code) DO UPDATE SET state = EXCLUDED.state, updated_at = now()"
                ),
                {"c": code, "s": state_json},
            )

    async def delete(self, code: str) -> None:
        from sqlalchemy import text

        async with self.engine.begin() as conn:
            await conn.execute(text("DELETE FROM room_snapshots WHERE code = :c"), {"c": code})

    async def load_all(self) -> dict[str, str]:
        from sqlalchemy import text

        async with self.engine.connect() as conn:
            rows = (await conn.execute(text("SELECT code, state::text AS s FROM room_snapshots"))).all()
        return {r[0]: r[1] for r in rows}
