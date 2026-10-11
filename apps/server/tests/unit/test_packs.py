"""Genre packs: loading, settings validation, filtered/deduplicated deck, rematch, projection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.packs import load_pack_defs, pack_listing
from app.catalog.repo import CsvSongRepository
from app.game import commands as C
from app.game.commands import GameError
from app.game.engine import reduce
from app.game.models import Phase, Room, Settings, Song
from app.game.projection import project, view_json
from tests.sim.run_bots import fire, setup_lobby

MULTI = Path(__file__).resolve().parents[1] / "fixtures" / "multipack"


def song(i: int, pack: str, *, title: str | None = None, artist: str | None = None, track: str = "") -> Song:
    return Song(
        id=i,
        title=title or f"Titulo {i:03d}",
        artist=artist or f"Artista {i:03d}",
        year=1960 + i,
        track_id=track or f"trk{i:03d}",
        pack=pack,
    )


def err(room: Room, cmd: C.Command) -> str:
    with pytest.raises(GameError) as e:
        reduce(room, cmd, 0.0)
    return e.value.code


def start(room: Room, songs: list[Song], seed: int = 3) -> Room:
    room, _ = reduce(room, C.Start(0, tuple(songs), seed), 100.0)
    return room


def with_packs(packs: list[str]) -> Room:
    room = setup_lobby(2, "voice", 3)
    room, _ = reduce(room, C.UpdateSettings(0, {"packs": packs}), 0.0)
    return room


def deck_song_ids(room: Room) -> set[int]:
    cards = list(room.deck) + [c for t in room.teams for c in t.timeline]
    return {c.song_id for c in cards}


# ------------------------------------------------------------------ catalog loading


async def test_csv_repo_loads_songs_csv_as_mix_and_every_pack_file() -> None:
    songs = await CsvSongRepository(MULTI / "songs.csv", MULTI / "packs").load_enabled()
    by_pack: dict[str, list[str]] = {}
    for s in songs:
        by_pack.setdefault(s.pack, []).append(s.csv_id)
    assert by_pack == {
        "mix": ["M001", "M002", "M003"],  # M004 is disputed
        "kids-test": ["K001", "K002", "K003"],
        "rock-test": ["R001", "R002", "R003", "R007"],  # bad year, year < 1900, ambiguous skipped
    }
    assert len({s.id for s in songs}) == len(songs)
    assert min(s.year for s in songs) == 1937


async def test_csv_repo_without_packs_dir_is_just_mix(tmp_path: Path) -> None:
    (tmp_path / "songs.csv").write_text((MULTI / "songs.csv").read_text(encoding="utf-8"), encoding="utf-8")
    songs = await CsvSongRepository(tmp_path / "songs.csv").load_enabled()
    assert {s.pack for s in songs} == {"mix"} and len(songs) == 3


def test_pack_defs_sorted_and_fallback(tmp_path: Path) -> None:
    defs = load_pack_defs(MULTI / "packs.json")
    assert [d.slug for d in defs] == ["mix", "rock-test", "kids-test", "empty-test"]
    assert [d.slug for d in load_pack_defs(tmp_path / "nope.json")] == ["mix"]
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert [d.slug for d in load_pack_defs(bad)] == ["mix"]
    dup = tmp_path / "dup.json"
    dup.write_text(json.dumps([{"slug": "a", "name": "A"}, {"slug": "a", "name": "B"}]), encoding="utf-8")
    assert [d.name for d in load_pack_defs(dup)] == ["A"]


async def test_pack_listing_counts_and_keeps_empty_packs() -> None:
    songs = await CsvSongRepository(MULTI / "songs.csv", MULTI / "packs").load_enabled()
    rows = pack_listing(load_pack_defs(MULTI / "packs.json"), songs)
    assert [(r["slug"], r["count"]) for r in rows] == [
        ("mix", 3),
        ("rock-test", 4),
        ("kids-test", 3),
        ("empty-test", 0),
    ]
    assert set(rows[0]) == {"slug", "name", "description", "icon", "count"}


# ------------------------------------------------------------------ settings validation


def test_settings_default_and_validation() -> None:
    assert Settings().packs == ["mix"]
    assert Settings(packs=["a", "b-2"]).packs == ["a", "b-2"]
    for bad in ([], ["a", "a"], ["Bad Slug"], ["../x"], [""], [str(i) for i in range(30)]):
        with pytest.raises(ValidationError):
            Settings(packs=bad)
    with pytest.raises(ValidationError):
        Settings.model_validate({"packs": "mix"})


def test_update_settings_packs() -> None:
    room = setup_lobby(2, "voice", 3)
    room, _ = reduce(room, C.UpdateSettings(0, {"packs": ["rock", "mix"]}), 0.0)
    assert room.settings.packs == ["rock", "mix"]
    for bad in ([], ["mix", "mix"], "mix", [1], ["Mayus"]):
        assert err(room, C.UpdateSettings(0, {"packs": bad})) == "invalid_settings"
    assert err(room, C.UpdateSettings(1, {"packs": ["mix"]})) == "not_host"
    assert room.settings.packs == ["rock", "mix"]


# ------------------------------------------------------------------ deck


def test_deck_only_from_chosen_packs() -> None:
    songs = [song(i, "a") for i in range(1, 8)] + [song(i, "b") for i in range(10, 17)]
    room = start(with_packs(["b"]), songs)
    ids = deck_song_ids(room)
    assert ids == {s.id for s in songs if s.pack == "b"}
    room = start(with_packs(["a", "b"]), songs)
    assert deck_song_ids(room) == {s.id for s in songs}


def test_default_pack_is_mix() -> None:
    songs = [song(i, "mix") for i in range(1, 6)] + [song(i, "other") for i in range(10, 15)]
    room = setup_lobby(2, "voice", 3)
    assert deck_song_ids(start(room, songs)) == {1, 2, 3, 4, 5}


def test_song_in_two_packs_appears_once_by_track_id_and_by_title_artist() -> None:
    songs = [
        song(1, "a", title="Despacito", artist="Luis Fonsi", track="same"),
        song(2, "b", title="Otro nombre", artist="Otro", track="same"),  # same track id
        song(3, "a", title="Billie Jean", artist="Michael Jackson", track="t3"),
        song(4, "b", title="BILLIE JEAN!", artist="michael jackson", track="t4"),  # same normalized text
        song(5, "b", title="Four", artist="X", track="t5"),
        song(6, "b", title="Five", artist="Y", track="t6"),
        song(7, "b", title="Six", artist="Z", track=""),
    ]
    room = start(with_packs(["a", "b"]), songs)
    ids = deck_song_ids(room)
    assert ids == {1, 3, 5, 6, 7}  # the first listed pack wins
    room = start(with_packs(["b", "a"]), songs)
    assert deck_song_ids(room) == {2, 4, 5, 6, 7}


def test_catalog_too_small_with_a_small_pack() -> None:
    songs = [song(i, "big") for i in range(1, 20)] + [song(30, "tiny"), song(31, "tiny")]
    room = with_packs(["tiny"])
    assert err_start(room, songs) == "catalog_too_small"
    # the same game works when the big pack is also chosen
    room = with_packs(["tiny", "big"])
    assert start(room, songs).phase == Phase.COUNTDOWN


def err_start(room: Room, songs: list[Song]) -> str:
    return err(room, C.Start(0, tuple(songs), 1))


def test_catalog_too_small_counts_after_dedupe() -> None:
    songs = [song(1, "a", track="x"), song(2, "b", track="x"), song(3, "a", track="y"), song(4, "b", track="y")]
    assert err_start(with_packs(["a", "b"]), songs) == "catalog_too_small"  # only 2 unique, 2 teams need 3


def test_rematch_keeps_packs_and_deck_stays_filtered() -> None:
    songs = [song(i, "a") for i in range(1, 10)] + [song(i, "b") for i in range(20, 29)]
    room = start(with_packs(["b"]), songs)
    now = room.timers["countdown"].deadline_ts
    room, _ = reduce(room, fire(room, "countdown"), now)
    room, _ = reduce(room, C.EndGame(0), now + 1)
    assert room.phase == Phase.GAME_OVER
    room, _ = reduce(room, C.Rematch(0), now + 2)
    assert room.phase == Phase.LOBBY and room.settings.packs == ["b"]
    room = start(room, songs, seed=9)
    assert deck_song_ids(room) <= {s.id for s in songs if s.pack == "b"}


# ------------------------------------------------------------------ projection / anti-cheat


def test_packs_visible_in_settings_but_current_card_never_exposes_pack() -> None:
    songs = [song(i, "a", title=f"Secreto{i}") for i in range(1, 10)]
    room = with_packs(["a"])
    assert project(room, 0).settings.packs == ["a"]
    room = start(room, songs)
    now = room.timers["countdown"].deadline_ts
    room, _ = reduce(room, fire(room, "countdown"), now)
    assert room.turn is not None
    for slot in range(len(room.teams)):
        view = view_json(room, slot)
        raw = json.dumps(view)
        turn = view["turn"]
        assert "pack" not in json.dumps(turn).lower()
        assert room.turn.card.title not in raw
