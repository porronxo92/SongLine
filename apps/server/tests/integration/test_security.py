"""Regression tests for the security review (docs/SECURITY-REVIEW.md, H1-H5, H9, H10)."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import ExitStack
from urllib.parse import parse_qs, urlparse

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.api.admin import SongPatch
from app.config import AppConfig, check_startup
from app.main import create_app
from app.ratelimit import RateLimiter
from app.services import Services
from app.sessions import SessionSigner
from app.ws import router as ws_router
from app.ws.router import TokenBucket
from tests.conftest import Clock, make_config
from tests.integration.test_ws import hdr, open_ws, setup_three, tok

MakeApp = Callable[..., tuple[FastAPI, Services]]
TOKEN_URL = "https://accounts.spotify.com/api/token"


def spotify_app(make_app: MakeApp, **over: object) -> tuple[FastAPI, Services]:
    return make_app(
        auth_mode="spotify",
        token_enc_key="",
        spotify_client_id="cid",
        spotify_redirect_uri="https://x/cb",
        **over,
    )


def start_login(c: TestClient, t: str, return_to: str = "/") -> tuple[str, str]:
    """Returns (spotify authorize url, state)."""
    r = c.post("/api/auth/spotify/start", json={"return_to": return_to}, headers=hdr(t))
    assert r.status_code == 200, r.text
    url = str(r.json()["url"])
    return url, parse_qs(urlparse(url).query)["state"][0]


def ws_close_code(client: TestClient, code: str, *first: dict[str, object]) -> int:
    """Opens the WS, sends `first` frames, and returns the close code the server ends with."""
    with client.websocket_connect(f"/ws/rooms/{code}") as ws:
        for f in first:
            ws.send_json(f)
        with pytest.raises(WebSocketDisconnect) as ei:
            ws.receive_json()
    return int(ei.value.code)


def hello(token: str) -> dict[str, object]:
    return {"type": "hello", "id": "h1", "payload": {"session_token": token}}


# ------------------------------------------------------------------ H1: login CSRF


def test_h1_start_needs_a_valid_signed_session(make_app: MakeApp) -> None:
    app, _ = spotify_app(make_app)
    with TestClient(app) as c:
        assert c.post("/api/auth/spotify/start", json={}).status_code == 401
        forged = "A" * 43 + "." + "B" * 43
        r = c.post("/api/auth/spotify/start", json={}, headers=hdr(forged))
        assert r.status_code == 401 and r.json()["detail"] == "invalid_session"
        # the old GET entry point (session token in the query string) is gone
        assert c.get("/api/auth/spotify/login", params={"session_token": forged}).status_code in (404, 405)


def test_h1_cookie_is_httponly_lax_scoped(make_app: MakeApp) -> None:
    app, _ = spotify_app(make_app, public_origin="http://localhost:5173")
    with TestClient(app) as c:
        r = c.post("/api/auth/spotify/start", json={}, headers=hdr(tok(c)))
        cookie = r.headers["set-cookie"].lower()
        assert "hc_oauth_nonce=" in cookie and "httponly" in cookie
        assert "samesite=lax" in cookie and "path=/api/auth/spotify" in cookie


def test_h1_secure_flag_follows_the_public_origin(make_app: MakeApp) -> None:
    app, _ = spotify_app(make_app, public_origin="https://localhost")
    with TestClient(app) as c:
        r = c.post("/api/auth/spotify/start", json={}, headers=hdr(tok(c)))
        assert "secure" in r.headers["set-cookie"].lower()


def test_h1_attacker_login_link_does_not_log_the_victim_in(make_app: MakeApp) -> None:
    """The attacker starts a login with his own session and hands the Spotify URL to the victim."""
    app, _ = spotify_app(make_app)
    with respx.mock(assert_all_called=False) as mock, TestClient(app) as attacker:
        mock.post(TOKEN_URL).respond(
            200, json={"access_token": "VICTIM", "refresh_token": "R", "expires_in": 3600}
        )
        a_tok = tok(attacker)
        _, state = start_login(attacker, a_tok)
        victim = TestClient(app)  # another browser: it never received the nonce cookie
        assert (
            victim.get("/api/auth/spotify/callback", params={"code": "x", "state": state}).status_code == 400
        )
        assert attacker.get("/api/auth/spotify/token", headers=hdr(a_tok)).status_code == 401
        # the state was burned: even the attacker's own browser cannot reuse it
        r = attacker.get("/api/auth/spotify/callback", params={"code": "x", "state": state})
        assert r.status_code == 400
        assert not mock.calls  # Spotify was never contacted


def test_h1_wrong_nonce_is_refused_and_right_one_is_single_use(make_app: MakeApp) -> None:
    app, _ = spotify_app(make_app)
    with respx.mock(assert_all_called=False) as mock, TestClient(app) as c:
        mock.post(TOKEN_URL).respond(
            200, json={"access_token": "A", "refresh_token": "R", "expires_in": 3600}
        )
        t = tok(c)
        _, state = start_login(c, t, "/anfitrion/audio")
        c.cookies.clear()
        c.cookies.set("hc_oauth_nonce", "forged", domain="testserver.local", path="/api/auth/spotify")
        assert c.get("/api/auth/spotify/callback", params={"code": "x", "state": state}).status_code == 400
        c.cookies.clear()
        _, state2 = start_login(c, t, "/anfitrion/audio")  # fresh cookie
        ok = c.get(
            "/api/auth/spotify/callback", params={"code": "x", "state": state2}, follow_redirects=False
        )
        assert ok.status_code == 302 and ok.headers["location"].endswith("/anfitrion/audio")
        assert (
            "hc_oauth_nonce" in ok.headers["set-cookie"] and "max-age=0" in ok.headers["set-cookie"].lower()
        )
        assert c.get("/api/auth/spotify/token", headers=hdr(t)).json()["access_token"] == "A"


def test_h1_fake_mode_start_returns_internal_url(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c:
        url = c.post("/api/auth/spotify/start", json={"return_to": "/x"}, headers=hdr(tok(c))).json()["url"]
        assert url.startswith("/api/auth/spotify/callback?")
        assert c.get(url, follow_redirects=False).headers["location"] == "http://localhost:5173/x"
        # without the cookie even the fake flow is refused
        url2 = c.post("/api/auth/spotify/start", json={}, headers=hdr(tok(c))).json()["url"]
        assert TestClient(app).get(url2).status_code == 400


# ------------------------------------------------------------------ H2: no token in the URL


def test_h2_handshake_hello_required_and_query_token_ignored(
    make_app: MakeApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ws_router, "HELLO_TIMEOUT_S", 0.3)
    app, _ = make_app()
    with TestClient(app) as c:
        t = tok(c)
        code = c.post("/api/rooms", json={}, headers=hdr(t)).json()["code"]
        # a valid token in the query string no longer authenticates; silence ends in 4401
        with (
            c.websocket_connect(f"/ws/rooms/{code}?token={t}") as ws,
            pytest.raises(WebSocketDisconnect) as ei,
        ):
            ws.receive_json()
        assert ei.value.code == 4401
        # a first message that is not `hello` also fails
        assert ws_close_code(c, code, {"type": "ping", "id": "1", "payload": {}}) == 4401


def test_h2_bad_tokens_get_4401_and_unknown_room_4404(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c:
        t = tok(c)
        code = c.post("/api/rooms", json={}, headers=hdr(t)).json()["code"]
        for bad in ("short", "x" * 60, "é" * 60, t[:-1] + ("A" if t[-1] != "A" else "B")):
            assert ws_close_code(c, code, hello(bad)) == 4401, bad
        assert ws_close_code(c, "9999", hello(t)) == 4404


def test_h2_valid_hello_connects_and_sends_ack_then_state(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c, ExitStack() as stack:
        t = tok(c)
        code = c.post("/api/rooms", json={}, headers=hdr(t)).json()["code"]
        p = open_ws(c, stack, code, t)
        assert p.recv(lambda m: m["type"] == "ack")["payload"]["ref_id"] == f"{t[:4]}-1"
        assert p.state()["you"] == {"slot": 0, "isHost": True}


def test_h2_code_guessing_still_rate_limited(make_app: MakeApp) -> None:
    app, _ = make_app(rate_code_attempts_per_min=3)
    with TestClient(app) as c:
        t = tok(c)
        codes = [ws_close_code(c, "9999", hello(t)) for _ in range(5)]
        assert codes == [4404, 4404, 4404, 4429, 4429]


# ------------------------------------------------------------------ H3: pending OAuth growth


def test_h3_start_is_rate_limited_per_ip(make_app: MakeApp) -> None:
    app, _ = spotify_app(make_app, rate_auth_start_per_min=3)
    with TestClient(app) as c:
        t = tok(c)
        statuses = [c.post("/api/auth/spotify/start", json={}, headers=hdr(t)).status_code for _ in range(5)]
        assert statuses == [200, 200, 200, 429, 429]


def test_h3_pending_is_capped_dropping_oldest(make_app: MakeApp) -> None:
    app, svc = spotify_app(make_app, rate_auth_start_per_min=10_000)
    with TestClient(app) as c:
        t = tok(c)
        _, first = start_login(c, t)
        for _ in range(450):
            start_login(c, t)
        assert len(svc.auth._pending) == 200
        assert first not in svc.auth._pending


# ------------------------------------------------------------------ H4: WS limits


def test_h4_oversized_message_closes_1009(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c, ExitStack() as stack:
        t = tok(c)
        code = c.post("/api/rooms", json={}, headers=hdr(t)).json()["code"]
        p = open_ws(c, stack, code, t)
        p.state()
        p.ws.send_json({"type": "ping", "id": "1", "payload": {"t": "x" * 20_000}})
        with pytest.raises(WebSocketDisconnect) as ei:
            while True:
                p.ws.receive_json()
        assert ei.value.code == 1009


def test_h4_ping_echo_is_bounded_and_deep_json_does_not_crash(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c, ExitStack() as stack:
        t = tok(c)
        code = c.post("/api/rooms", json={}, headers=hdr(t)).json()["code"]
        p = open_ws(c, stack, code, t)
        p.state()
        r = p.result(p.send("ping", t="x" * 500))
        assert r["type"] == "error" and r["payload"]["code"] == "bad_payload"
        # ~16 KB of nested arrays: json.loads hits RecursionError, the server answers and lives on
        p.ws.send_text("[" * 16_000)
        assert p.recv(lambda m: m["type"] == "error")["payload"]["code"] == "bad_message"
        p.ws.send_text(json.dumps({"type": "ping", "id": "n", "payload": {"t": 1}}))
        assert p.recv(lambda m: m["type"] == "pong")["payload"]["t"] == 1


def test_h4_message_flood_closes_4429(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c, ExitStack() as stack:
        t = tok(c)
        code = c.post("/api/rooms", json={}, headers=hdr(t)).json()["code"]
        p = open_ws(c, stack, code, t)
        p.state()
        for i in range(400):
            p.ws.send_json({"type": "ping", "id": str(i), "payload": {}})
        with pytest.raises(WebSocketDisconnect) as ei:
            while True:
                p.ws.receive_json()
        assert ei.value.code == 4429


def test_h4_token_bucket_refills_over_time() -> None:
    clock = Clock(0.0)
    b = TokenBucket(rate=20, burst=5, clock=clock)
    assert [b.take() for _ in range(6)] == [True] * 5 + [False]
    clock.advance(0.1)  # 2 tokens
    assert [b.take() for _ in range(3)] == [True, True, False]


def test_h4_connections_per_room_are_capped(make_app: MakeApp) -> None:
    app, _ = make_app(ws_max_conns_per_room=2)
    with TestClient(app) as c, ExitStack() as stack:
        toks = [tok(c) for _ in range(3)]
        code = c.post("/api/rooms", json={}, headers=hdr(toks[0])).json()["code"]
        for t in toks[:2]:
            open_ws(c, stack, code, t).state()
        assert ws_close_code(c, code, hello(toks[2])) == 4429


def test_h4_connections_per_ip_are_capped_and_released(make_app: MakeApp) -> None:
    app, svc = make_app(ws_max_conns_per_ip=2)
    with TestClient(app) as c, ExitStack() as stack:
        toks = [tok(c) for _ in range(3)]
        code = c.post("/api/rooms", json={}, headers=hdr(toks[0])).json()["code"]
        a = open_ws(c, stack, code, toks[0])
        a.state()
        b = open_ws(c, stack, code, toks[1])
        b.state()
        assert ws_close_code(c, code, hello(toks[2])) == 4429
        a.ws.close()
        b.ws.close()
    assert svc.ws_per_ip == {}  # counters are released


# ------------------------------------------------------------------ H5: client IP and limiter


def test_h5_spoofed_forwarded_for_does_not_evade_the_limiter(make_app: MakeApp) -> None:
    app, svc = make_app(rate_code_attempts_per_min=3)
    with TestClient(app) as c:
        codes = [
            c.get("/api/rooms/9999", headers={"x-forwarded-for": f"10.0.0.{i}"}).status_code for i in range(8)
        ]
        assert codes == [404, 404, 404] + [429] * 5
        assert len(svc.code_limiter._events) == 1


def test_h5_limiter_creates_no_keys_when_querying_and_purges_expired() -> None:
    clock = Clock(0.0)
    rl = RateLimiter(2, 60.0, clock)
    for i in range(500):
        assert rl.blocked(f"k{i}") is False
    assert rl._events == {}
    assert rl.allow("a") and rl.allow("a") and not rl.allow("a") and rl.blocked("a")
    clock.advance(61)
    assert rl.blocked("a") is False and rl._events == {}  # expired key removed
    for i in range(2000):
        rl.allow(f"x{i}")
    clock.advance(61)
    rl.allow("fresh")
    assert set(rl._events) == {"fresh"}  # the sweep dropped the stale ones


# ------------------------------------------------------------------ H9: validation and signed sessions


def test_h9_session_tokens_are_server_signed() -> None:
    s = SessionSigner("secret-one")
    t = s.issue()
    body, _, sig = t.partition(".")
    assert s.verify(t) and len(body) == 43 and sig
    assert not s.verify(body + "." + "A" * len(sig))  # forged signature
    assert not s.verify("x" * 40) and not s.verify("") and not s.verify(body)
    assert not s.verify("é" * 30 + "." + "é" * 30)  # non-ASCII must not raise
    assert not SessionSigner("secret-two").verify(t)  # another key
    assert SessionSigner("secret-one").verify(t)  # same key after a restart


def test_h9_unsigned_tokens_are_rejected_over_rest_and_ws(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c:
        arbitrary = "attacker-chosen-token-" + "A" * 30
        assert c.post("/api/rooms", json={}, headers=hdr(arbitrary)).status_code == 401
        t = tok(c)
        code = c.post("/api/rooms", json={}, headers=hdr(t)).json()["code"]
        # a forged token reads as anonymous
        assert c.get(f"/api/rooms/{code}", headers=hdr(arbitrary)).json()["your_slot"] is None
        assert c.get(f"/api/rooms/{code}", headers=hdr(t)).json()["your_slot"] == 0
        assert ws_close_code(c, code, hello(arbitrary)) == 4401


def test_h9_color_is_validated(make_app: MakeApp) -> None:
    app, _ = make_app()
    with TestClient(app) as c, ExitStack() as stack:
        t = tok(c)
        for bad in ("red", "#12345", "#GGGGGG", "javascript:alert(1)", "#1234567", "url(x)"):
            r = c.post("/api/rooms", json={"color": bad}, headers=hdr(t))
            assert r.status_code == 422, bad
        assert c.post("/api/rooms", json={"color": "#aB09fF"}, headers=hdr(t)).status_code == 200
        _, players = setup_three(c, stack)
        p = players[1]
        r2 = p.result(p.send("claim_slot", slot=1, name="X", color="red;background:url(x)"))
        assert r2["payload"]["code"] == "bad_payload"


def test_h9_song_patch_ranges() -> None:
    SongPatch(year=1985, title_aliases=["a"])
    for bad in (
        {"year": 3},
        {"year": 99999},
        {"year_note": "x" * 501},
        {"title_aliases": ["x"] * 21},
        {"artist_aliases": ["x" * 201]},
        {"year_status": "x" * 33},
    ):
        with pytest.raises(ValidationError):
            SongPatch(**bad)  # type: ignore[arg-type]


def test_h9_admin_non_ascii_token_is_401_and_short_token_disables_admin(make_app: MakeApp) -> None:
    good = "g" * 40
    app, _ = make_app(admin_token=good)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/admin/songs", headers={"X-Admin-Token": bytes([0x63, 0xE9, 0xFF])})
        assert r.status_code == 401
        assert c.get("/api/admin/songs", headers={"X-Admin-Token": good}).status_code == 501
    app, _ = make_app(admin_token="short-but-correct")
    with TestClient(app) as c:
        r = c.get("/api/admin/songs", headers={"X-Admin-Token": "short-but-correct"})
        assert r.status_code == 404 and r.json()["detail"] == "admin_disabled"


# ------------------------------------------------------------------ H10: startup guard


def test_h10_fake_mode_is_refused_outside_localhost() -> None:
    for origin in ("https://hitster.example.com", "http://192.168.1.5:5173", "", "http://localhost.evil.com"):
        with pytest.raises(RuntimeError, match="AUTH_MODE=fake"):
            check_startup(make_config(auth_mode="fake", public_origin=origin))
        with pytest.raises(RuntimeError):
            create_app(make_config(auth_mode="fake", public_origin=origin))
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost"):
        check_startup(make_config(auth_mode="fake", public_origin=origin))


def test_h10_real_deployment_needs_a_session_secret() -> None:
    kw = {"_env_file": None, "auth_mode": "spotify", "public_origin": "https://hitster.example.com"}
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        check_startup(AppConfig(**kw))  # type: ignore[arg-type]
    check_startup(AppConfig(session_secret="s" * 32, **kw))  # type: ignore[arg-type]
