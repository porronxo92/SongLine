from __future__ import annotations

from collections.abc import Callable

import httpx
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.game import commands as C
from app.game.engine import reduce
from app.game.models import Phase
from app.services import Services
from tests.conftest import FIXTURES, Clock
from tests.helpers import rigged

ADMIN = "a" * 40
MakeApp = Callable[..., tuple[FastAPI, Services]]


def tok(c: TestClient) -> str:
    return str(c.post("/api/session").json()["session_token"])


def hdr(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def test_healthz_session_and_catalog_stats_csv(make_app: MakeApp) -> None:
    app, _ = make_app(catalog_source="csv")
    # use the CSV repo for real here
    from app.catalog.repo import CsvSongRepository

    app.state.services.repo = CsvSongRepository(FIXTURES / "songs.csv")
    app.state.services.fake  # noqa: B018
    with TestClient(app) as c:
        assert c.get("/api/healthz").json() == {"status": "ok"}
        t = c.post("/api/session").json()["session_token"]
        assert len(t) >= 32 and c.post("/api/session").json()["session_token"] != t
        stats = c.get("/api/catalog/stats").json()
        assert stats["total"] == 5 and stats["by_origin"] == {"es": 3, "intl": 2}


def test_create_room_and_prejoin(make_app: MakeApp) -> None:
    app, svc = make_app()
    with TestClient(app) as c:
        assert c.post("/api/rooms", json={}).status_code == 401
        t = tok(c)
        r = c.post(
            "/api/rooms", json={"settings": {"team_count": 3, "mode": "app"}, "name": "Pepe"}, headers=hdr(t)
        )
        body = r.json()
        assert r.status_code == 200 and len(body["code"]) == 4 and body["code"].isdigit()
        assert body["ws_url"] == f"ws://localhost:5173/ws/rooms/{body['code']}" and body["slot"] == 0
        room = svc.manager.get(body["code"]).room  # type: ignore[union-attr]
        assert room.teams[0].name == "Pepe" and room.settings.mode == "app" and len(room.teams) == 3
        info = c.get(f"/api/rooms/{body['code']}").json()
        assert info["status"] == "open" and info["mode"] == "app" and info["your_slot"] is None
        assert info["slots"][0]["taken"] and info["slots"][0]["is_host"] and not info["slots"][1]["taken"]
        assert info["slots"][1]["suggested_color"].startswith("#")
        assert c.get(f"/api/rooms/{body['code']}", headers=hdr(t)).json()["your_slot"] == 0
        assert (
            c.post("/api/rooms", json={"settings": {"start_position_ms": 0}}, headers=hdr(t)).status_code
            == 422
        )
        assert c.post("/api/rooms", json={"settings": {"team_count": 9}}, headers=hdr(t)).status_code == 422
        assert c.get("/api/rooms/0000x").status_code in (404, 429)


def test_room_status_started(make_app: MakeApp) -> None:
    app, svc = make_app()
    with TestClient(app) as c:
        code = c.post("/api/rooms", json={}, headers=hdr(tok(c))).json()["code"]
        rt = svc.manager.get(code)
        assert rt is not None
        rt.room.phase = Phase.PLACING
        assert c.get(f"/api/rooms/{code}").json()["status"] == "started"


def test_room_codes_unique(make_app: MakeApp) -> None:
    app, svc = make_app(rate_room_create_per_min=1000)
    with TestClient(app) as c:
        t = tok(c)
        codes = {c.post("/api/rooms", json={}, headers=hdr(t)).json()["code"] for _ in range(60)}
        assert len(codes) == 60


def test_rate_limits(make_app: MakeApp) -> None:
    app, _ = make_app(rate_room_create_per_min=5, rate_code_attempts_per_min=3)
    with TestClient(app) as c:
        t = tok(c)
        statuses = [c.post("/api/rooms", json={}, headers=hdr(t)).status_code for _ in range(6)]
        assert statuses == [200] * 5 + [429]
        codes = [c.get("/api/rooms/9999").status_code for _ in range(5)]
        assert codes == [404, 404, 404, 429, 429]


def test_fake_auth_endpoints(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c:
        t = tok(c)
        r = c.post("/api/auth/spotify/start", json={"return_to": "/join/1234"}, headers=hdr(t))
        assert r.status_code == 200
        done = c.get(r.json()["url"], follow_redirects=False)  # the cookie jar carries the nonce
        assert done.status_code == 302 and done.headers["location"] == "http://localhost:5173/join/1234"
        r = c.post("/api/auth/spotify/start", json={"return_to": "//evil.com"}, headers=hdr(t))
        done = c.get(r.json()["url"], follow_redirects=False)
        assert done.headers["location"] == "http://localhost:5173/"
        assert c.get("/api/auth/status", headers=hdr(t)).json() == {
            "auth_mode": "fake",
            "logged_in": True,
            "premium_verified": True,
        }
        assert c.get("/api/auth/spotify/token", headers=hdr(t)).json()["access_token"] == "fake-token"
        assert c.get("/api/auth/spotify/token").status_code == 401
        assert c.post("/api/auth/spotify/verify-premium", json={"device_id": "d"}, headers=hdr(t)).json() == {
            "premium": True
        }
        assert c.post("/api/auth/logout", headers=hdr(t)).status_code == 204


def test_turn_audio_proxy_rules_fake(make_app: MakeApp) -> None:
    app, svc = make_app()
    with TestClient(app) as c:
        host, other = tok(c), tok(c)
        code = c.post("/api/rooms", json={}, headers=hdr(host)).json()["code"]
        rt = svc.manager.get(code)
        assert rt is not None
        assert (
            c.get("/api/turn/audio", params={"code": code}, headers=hdr(host)).status_code == 403
        )  # no turn
        room, now = rigged({0: [1980], 1: [1990]}, 1985)
        room.code = code
        room.teams[0].session_token_hash = rt.room.teams[0].session_token_hash
        room, _ = reduce(room, C.PlayRequest(0), now)
        assert room.turn.audio_source == "spotify"  # type: ignore[union-attr]
        rt.room = room
        assert (
            c.get("/api/turn/audio", params={"code": code}, headers=hdr(host)).status_code == 403
        )  # not preview
        room.turn.audio_source = "preview"  # type: ignore[union-attr]
        assert (
            c.get("/api/turn/audio", params={"code": code}, headers=hdr(other)).status_code == 403
        )  # not host
        ok = c.get("/api/turn/audio", params={"code": code}, headers=hdr(host))
        assert ok.status_code == 200 and ok.headers["content-type"] == "audio/wav"
        assert ok.headers["cache-control"] == "no-store" and ok.content[:4] == b"RIFF"
        assert c.get("/api/turn/audio", params={"code": "0000"}, headers=hdr(host)).status_code == 404


def test_admin_guard(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c:
        assert c.get("/api/admin/songs").status_code == 404  # no ADMIN_TOKEN configured
    app, _ = make_app(admin_token=ADMIN)
    with TestClient(app) as c:
        assert c.get("/api/admin/songs").status_code == 401
        assert c.get("/api/admin/songs", headers={"X-Admin-Token": "bad"}).status_code == 401
        assert c.get("/api/admin/songs", headers={"X-Admin-Token": ADMIN}).status_code == 501  # csv catalog


def test_deezer_preview_proxy_streams_without_exposing_url(make_app: MakeApp) -> None:
    app, svc = make_app(auth_mode="spotify", token_enc_key="")
    with respx.mock(assert_all_called=False) as mock, TestClient(app) as c:
        mock.get("https://api.deezer.com/track/isrc:ISRC1").respond(200, json={"id": 77})
        mock.get("https://api.deezer.com/track/77").respond(200, json={"preview": "https://cdn.dz/p.mp3"})
        mock.get("https://cdn.dz/p.mp3").respond(
            200, content=b"MP3DATA", headers={"content-type": "audio/mpeg"}
        )
        host = tok(c)
        code = c.post("/api/rooms", json={}, headers=hdr(host)).json()["code"]
        rt = svc.manager.get(code)
        assert rt is not None
        room, now = rigged({0: [1980], 1: [1990]}, 1985, mystery=None)
        room.turn.card.isrc = "ISRC1"  # type: ignore[union-attr]
        room.code = code
        room.teams[0].session_token_hash = rt.room.teams[0].session_token_hash
        room, _ = reduce(room, C.PlayRequest(0), now)
        room.turn.audio_source = "preview"  # type: ignore[union-attr]
        rt.room = room
        r = c.get("/api/turn/audio", params={"code": code}, headers=hdr(host))
        assert r.status_code == 200 and r.content == b"MP3DATA" and r.headers["content-type"] == "audio/mpeg"
        assert "deezer" not in str(r.headers).lower() and "cdn.dz" not in str(r.headers)
        assert svc.deezer._ids["isrc:ISRC1"] == 77  # id cached
        # second call: id comes from the cache (no new isrc lookup)
        before = mock.routes[0].call_count
        assert c.get("/api/turn/audio", params={"code": code}, headers=hdr(host)).status_code == 200
        assert mock.routes[0].call_count == before


async def test_deezer_search_fallback_by_title_artist() -> None:
    from app.spotify.deezer import DeezerPreview

    with respx.mock() as mock:
        mock.get("https://api.deezer.com/search").respond(200, json={"data": [{"id": 5}]})
        mock.get("https://api.deezer.com/track/5").respond(200, json={"preview": "https://x/y.mp3"})
        async with httpx.AsyncClient() as http:
            d = DeezerPreview(http)
            assert await d.preview_url("", "Title", "Artist") == "https://x/y.mp3"
            assert d._ids == {"q:title|artist": 5}


def test_clock_fixture(clock: Clock) -> None:
    clock.advance(5)
    assert clock() == 10_005.0
