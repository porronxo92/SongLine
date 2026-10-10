"""Shared test helpers for engine tests."""

from __future__ import annotations

from app.game import commands as C
from app.game.engine import reduce
from app.game.models import Card, Phase, Room
from tests.sim.run_bots import fire, make_songs, setup_lobby, start_game

__all__ = ["make_card", "rigged", "step", "fire", "make_songs", "setup_lobby", "start_game", "go"]


def make_card(n: int, year: int, title: str | None = None, artist: str | None = None) -> Card:
    return Card(
        instance_id=f"inst_{chr(97 + n % 26)}{chr(97 + n // 26)}",
        song_id=1000 + n,
        title=title or f"Titulo {n:03d}",
        artist=artist or f"Artista {n:03d}",
        year=year,
        track_id=f"trk{n:03d}z",
    )


def rigged(
    lines: dict[int, list[int]],
    mystery_year: int,
    *,
    mode: str = "voice",
    tokens: dict[int, int] | None = None,
    team_count: int | None = None,
    deck_years: list[int] | None = None,
    target: int = 10,
    mystery: Card | None = None,
) -> tuple[Room, float]:
    """A room in TURN_READY with hand-made timelines, slot 0 active. Returns (room, now)."""
    tc = team_count or max(max(lines) + 1, 2)
    room = setup_lobby(tc, mode, target)
    room, now = start_game(room, make_songs(40), seed=7)
    n = 0
    for slot, years in lines.items():
        room.teams[slot].timeline = []
        for y in years:
            n += 1
            room.teams[slot].timeline.append(make_card(n, y))
    for slot, k in (tokens or {}).items():
        room.teams[slot].tokens = k
    # replace the deck and the card in play with controlled cards
    n += 1
    card = mystery or make_card(n, mystery_year)
    room.deck = []
    for y in deck_years if deck_years is not None else [1970, 1971, 1972, 1973, 1974, 1975, 1976]:
        n += 1
        room.deck.append(make_card(n, y))
    assert room.turn is not None
    room.turn.card = card
    room.turn.team_slot = 0
    room.first_slot = 0
    room.used_song_ids = []
    return room, now


def step(room: Room, cmd: C.Command, now: float) -> tuple[Room, list[C.Effect]]:
    return reduce(room, cmd, now)


def go(room: Room, now: float, *cmds: C.Command) -> Room:
    for c in cmds:
        room, _ = reduce(room, c, now)
    return room


def to_guessing(room: Room, now: float, index: int) -> Room:
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, index))
    assert room.phase == Phase.GUESSING
    return room
