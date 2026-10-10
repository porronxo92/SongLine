from __future__ import annotations

import faulthandler
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

from app.config import AppConfig
from app.game.models import Song
from app.main import create_app
from app.rooms.snapshot import Persistence
from app.services import Services, build_services
from tests.sim.run_bots import make_songs

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True, scope="session")
def _hang_guard() -> Iterator[None]:
    """A hung websocket test would block forever: dump the stack and exit instead."""
    faulthandler.dump_traceback_later(240, exit=True)
    yield
    faulthandler.cancel_dump_traceback_later()


class Clock:
    def __init__(self, t: float = 10_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class ListRepo:
    def __init__(self, songs: tuple[Song, ...]) -> None:
        self.songs = songs

    async def load_enabled(self) -> list[Song]:
        return list(self.songs)


def make_config(**over: Any) -> AppConfig:
    base: dict[str, Any] = {
        "auth_mode": "fake",
        "catalog_source": "csv",
        "catalog_csv_path": FIXTURES / "songs.csv",
        "persistence": "none",
        "public_origin": "http://localhost:5173",
        "admin_token": "",
    }
    base.update(over)
    return AppConfig(_env_file=None, **base)  # type: ignore[arg-type]


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def make_app(clock: Clock) -> Callable[..., tuple[FastAPI, Services]]:
    def _make(
        songs: tuple[Song, ...] | None = None,
        persistence: Persistence | None = None,
        timer_scale: float = 0.01,
        **cfg: Any,
    ) -> tuple[FastAPI, Services]:
        config = make_config(**cfg)
        svc = build_services(
            config,
            repo=ListRepo(songs if songs is not None else make_songs(30)),
            persistence=persistence,
            clock=clock,
            timer_scale=timer_scale,
        )
        return create_app(config, svc), svc

    return _make
