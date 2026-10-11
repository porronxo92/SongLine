"""Pack endpoints and settings over REST and WebSocket (fixtures only, no real catalog)."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.catalog.packs import PackDef
from app.catalog.repo import CsvSongRepository
from app.game.models import Song
from app.services import Services
from tests.integration.test_ws import hdr, setup_three, start, tok

MULTI = Path(__file__).resolve().parents[1] / "fixtures" / "multipack"
MakeApp = Callable[..., tuple[FastAPI, Services]]


def multipack_app(make_app: MakeApp, **kw: object) -> tuple[FastAPI, Services]:
    app, svc = make_app(
        catalog_csv_path=MULTI / "songs.csv", catalog_packs_json=MULTI / "packs.json", **kw
    )
    svc.repo = CsvSongRepository(MULTI / "songs.csv", MULTI / "packs")
    return app, svc


def test_catalog_packs_endpoint_sorted_with_counts(make_app: MakeApp) -> None:
    app, _ = multipack_app(make_app)
    with TestClient(app) as c:
        r = c.get("/api/catalog/packs")
        assert r.status_code == 200  # public: no token
        rows = r.json()
        assert [(p["slug"], p["count"]) for p in rows] == [
            ("mix", 3),
            ("rock-test", 4),
            ("kids-test", 3),
            ("empty-test", 0),
        ]
        assert set(rows[0]) == {"slug", "name", "description", "icon", "count"}
        assert c.get("/api/catalog/stats").json()["total"] == 10


def test_catalog_packs_without_packs_json_lists_mix(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c:
        rows = c.get("/api/catalog/packs").json()
        assert [p["slug"] for p in rows] == ["mix"]


def test_create_room_validates_packs(make_app: MakeApp) -> None:
    app, svc = multipack_app(make_app, rate_room_create_per_min=50)
    with TestClient(app) as c:
        t = tok(c)

        def create(packs: object) -> httpx.Response:
            return c.post("/api/rooms", json={"settings": {"packs": packs}}, headers=hdr(t))

        for bad in ([], ["mix", "mix"], ["nope"], "mix"):
            assert create(bad).status_code == 422, bad
        r = create(["rock-test", "kids-test"])
        assert r.status_code == 200
        rt = svc.manager.get(r.json()["code"])
        assert rt is not None and rt.room.settings.packs == ["rock-test", "kids-test"]
        r = c.post("/api/rooms", json={}, headers=hdr(t))
        rt = svc.manager.get(r.json()["code"])
        assert rt is not None and rt.room.settings.packs == ["mix"]


def test_update_settings_packs_over_ws_and_view(make_app: MakeApp) -> None:
    app, svc = multipack_app(make_app)
    with TestClient(app) as client, ExitStack() as stack:
        _, players = setup_three(client, stack)
        host, p1, _ = players
        assert p1.result(p1.send("update_settings", packs=["mix"]))["payload"]["code"] == "not_host"
        for bad in ([], ["mix", "mix"], ["nope"], "mix", [3]):
            code = host.result(host.send("update_settings", packs=bad))["payload"]["code"]
            assert code == "invalid_settings", bad
        host.ok("update_settings", packs=["rock-test", "mix"])
        v = host.state(lambda v: v["settings"]["packs"] == ["rock-test", "mix"])
        assert v["settings"]["packs"] == ["rock-test", "mix"]
        assert p1.state(lambda v: v["settings"]["packs"] == ["rock-test", "mix"])


def test_game_deck_comes_from_chosen_packs_only(make_app: MakeApp) -> None:
    songs = tuple(
        Song(id=i, title=f"T{i}", artist=f"A{i}", year=1950 + i, track_id=f"x{i}", pack="a" if i <= 10 else "b")
        for i in range(1, 21)
    )
    app, svc = make_app(songs=songs)
    svc.packs += [PackDef(slug="a", name="A"), PackDef(slug="b", name="B")]
    with TestClient(app) as client, ExitStack() as stack:
        code, players = setup_three(client, stack)
        players[0].ok("update_settings", packs=["b"])
        rt = start(code, players, svc)
        ids = {c.song_id for c in rt.room.deck} | {t.timeline[0].song_id for t in rt.room.teams}
        if rt.room.turn is not None:
            ids.add(rt.room.turn.card.song_id)
        assert ids and ids <= set(range(11, 21))
