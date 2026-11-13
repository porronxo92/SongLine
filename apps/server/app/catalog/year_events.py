"""Curated historical events, loaded once outside the pure game engine."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import REPO_ROOT
from app.game.models import Song, YearEvent

YEAR_EVENTS_PATH = REPO_ROOT / "catalog" / "year_events.json"


def validate_events(raw: list[dict]) -> list[YearEvent]:  # type: ignore[type-arg]
    events = [YearEvent.model_validate(row) for row in raw]
    seen: set[str] = set()
    for event in events:
        if event.id in seen:
            raise ValueError(f"duplicate year event: {event.id}")
        seen.add(event.id)
        if event.occurred_on.year != event.year or event.occurred_on > date.today():
            raise ValueError(f"event date is inconsistent or in the future: {event.id}")
        if re.search(r"\b\d{4}\b", event.text):
            raise ValueError(f"event hint contains an explicit year: {event.id}")
    return events


def read_year_events(path: Path = YEAR_EVENTS_PATH) -> list[YearEvent]:
    return validate_events(json.loads(path.read_text(encoding="utf-8")))


def attach_year_events(songs: list[Song], events: list[YearEvent]) -> list[Song]:
    by_year: dict[int, list[YearEvent]] = defaultdict(list)
    for event in events:
        by_year[event.year].append(event)
    return [song.model_copy(update={"year_events": tuple(by_year[song.year])}) for song in songs]


class YearEventRepository(Protocol):
    async def load_enabled(self) -> list[YearEvent]: ...
    async def close(self) -> None: ...


class JsonYearEventRepository:
    def __init__(self, path: Path = YEAR_EVENTS_PATH) -> None:
        self.path = path

    async def load_enabled(self) -> list[YearEvent]:
        return read_year_events(self.path)

    async def close(self) -> None:
        pass


class PostgresYearEventRepository:
    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url, pool_pre_ping=True)

    async def load_enabled(self) -> list[YearEvent]:
        async with self.engine.connect() as conn:
            rows = (await conn.execute(text(
                "SELECT id, year, category, text, source_url, occurred_on FROM year_events "
                "WHERE enabled = true ORDER BY year, id"
            ))).mappings().all()
        return validate_events([dict(row) for row in rows])

    async def close(self) -> None:
        await self.engine.dispose()
