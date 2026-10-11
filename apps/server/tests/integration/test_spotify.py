"""Spotify OAuth (PKCE), token refresh, verify-premium and play, with recorded responses (respx)."""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from urllib.parse import parse_qs, urlparse

import httpx
import respx
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services import Services, hash_token
from app.spotify.client import SpotifyAudioBackend
from app.spotify.crypto import TokenCipher
from app.spotify.oauth import SpotifyAuth, new_pkce_pair, safe_return_to
from tests.conftest import Clock

MakeApp = Callable[..., tuple[FastAPI, Services]]
TOKEN_URL = "https://accounts.spotify.com/api/token"


def test_pkce_pair_is_s256() -> None:
    v, ch = new_pkce_pair()
    assert ch == base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    assert 43 <= len(v) <= 128


def test_safe_return_to() -> None:
    assert safe_return_to("/join/1234") == "/join/1234"
    for bad in ("//evil.com", "https://evil.com", "evil", "/\\evil"):
        assert safe_return_to(bad) == "/"


def test_login_callback_token_flow_over_http(make_app: MakeApp, clock: Clock) -> None:
    key = Fernet.generate_key().decode()
    app, svc = make_app(
        auth_mode="spotify", token_enc_key=key, spotify_client_id="CID", spotify_redirect_uri="https://x/cb"
    )
    with respx.mock(assert_all_called=False) as mock, TestClient(app) as c:
        token_route = mock.post(TOKEN_URL).respond(
            200, json={"access_token": "ACCESS1", "refresh_token": "REFRESH1", "expires_in": 3600, "scope": "streaming user-read-email user-read-private user-read-playback-state user-modify-playback-state"}
        )
        t = str(c.post("/api/session").json()["session_token"])
        r = c.post(
            "/api/auth/spotify/start",
            json={"return_to": "/join/1234"},
            headers={"Authorization": f"Bearer {t}"},
        )
        assert r.status_code == 200
        u = urlparse(r.json()["url"])
        q = parse_qs(u.query)
        assert u.netloc == "accounts.spotify.com" and q["code_challenge_method"] == ["S256"]
        assert q["client_id"] == ["CID"] and q["redirect_uri"] == ["https://x/cb"]
        assert "streaming" in q["scope"][0] and "client_secret" not in u.query
        state = q["state"][0]
        cb = c.get(
            "/api/auth/spotify/callback", params={"code": "abc", "state": state}, follow_redirects=False
        )
        assert cb.status_code == 302 and cb.headers["location"] == "http://localhost:5173/join/1234"
        sent = token_route.calls.last.request.content.decode()
        assert "grant_type=authorization_code" in sent and "code_verifier=" in sent and "code=abc" in sent
        # tokens are stored encrypted
        stored = svc.auth._tokens[hash_token(t)]
        assert b"ACCESS1" not in stored.access_enc
        assert TokenCipher(key).decrypt(stored.access_enc) == "ACCESS1"
        assert c.get("/api/auth/status", headers={"Authorization": f"Bearer {t}"}).json()["logged_in"] is True
        tk = c.get("/api/auth/spotify/token", headers={"Authorization": f"Bearer {t}"}).json()
        assert tk["access_token"] == "ACCESS1" and tk["expires_at"] == clock() + 3600
        # bad state is refused
        assert c.get("/api/auth/spotify/callback", params={"code": "c", "state": "nope"}).status_code == 400
        # state is single use
        assert c.get("/api/auth/spotify/callback", params={"code": "abc", "state": state}).status_code == 400
        # refresh when < 5 min left
        mock.post(TOKEN_URL).respond(200, json={"access_token": "ACCESS2", "expires_in": 3600})
        clock.advance(3400)
        tk = c.get("/api/auth/spotify/token", headers={"Authorization": f"Bearer {t}"}).json()
        assert tk["access_token"] == "ACCESS2"
        assert svc.auth.cipher.decrypt(svc.auth._tokens[hash_token(t)].refresh_enc) == "REFRESH1"  # kept
        assert c.post("/api/auth/logout", headers={"Authorization": f"Bearer {t}"}).status_code == 204
        assert c.get("/api/auth/spotify/token", headers={"Authorization": f"Bearer {t}"}).status_code == 401


async def _backend(clock: Clock) -> tuple[SpotifyAudioBackend, SpotifyAuth, str, httpx.AsyncClient]:
    http = httpx.AsyncClient()
    auth = SpotifyAuth("CID", "https://x/cb", TokenCipher(), http, clock)
    sid = "sess"
    auth._store(sid, {"access_token": "A1", "refresh_token": "R1", "expires_in": 3600}, None)
    return SpotifyAudioBackend(auth, http), auth, sid, http


async def test_verify_premium_ok_and_403(clock: Clock) -> None:
    backend, auth, sid, http = await _backend(clock)
    with respx.mock() as mock:
        route = mock.put("https://api.spotify.com/v1/me/player").respond(204)
        assert await backend.verify_premium(sid, "dev1") == (True, None)
        req = route.calls.last.request
        assert req.headers["authorization"] == "Bearer A1"
        assert req.content == b'{"device_ids":["dev1"],"play":false}'
        mock.put("https://api.spotify.com/v1/me/player").respond(
            403,
            json={
                "error": {
                    "status": 403,
                    "message": "Player command failed: Premium required",
                    "reason": "PREMIUM_REQUIRED",
                }
            },
        )
        assert await backend.verify_premium(sid, "dev1") == (False, "premium_required")
        mock.put("https://api.spotify.com/v1/me/player").respond(
            403, json={"error": {"status": 403, "message": "User not registered in the Developer Dashboard"}}
        )
        assert await backend.verify_premium(sid, "dev1") == (False, "user_not_registered")
    await http.aclose()


async def test_play_sends_uri_and_position_and_maps_errors(clock: Clock) -> None:
    backend, auth, sid, http = await _backend(clock)
    with respx.mock() as mock:
        route = mock.put("https://api.spotify.com/v1/me/player/play").respond(204)
        out = await backend.play(sid, "dev1", "TRK", 10_000, "inst")
        assert out.ok
        r = route.calls.last.request
        assert r.url.params["device_id"] == "dev1"
        assert r.content == b'{"uris":["spotify:track:TRK"],"position_ms":10000}'
        mock.put("https://api.spotify.com/v1/me/player/play").respond(
            404, json={"error": {"reason": "NO_ACTIVE_DEVICE"}}
        )
        assert (await backend.play(sid, "dev1", "TRK", 0, "i")).code == "device_gone"
        mock.put("https://api.spotify.com/v1/me/player/play").respond(
            403, json={"error": {"reason": "PREMIUM_REQUIRED"}}
        )
        assert (await backend.play(sid, "dev1", "TRK", 0, "i")).code == "premium_required"
        mock.put("https://api.spotify.com/v1/me/player/play").respond(429, headers={"Retry-After": "7"})
        out = await backend.play(sid, "dev1", "TRK", 0, "i")
        assert out.code == "rate_limited" and out.retry_after_s == 7.0
        mock.put("https://api.spotify.com/v1/me/player/play").respond(500)
        assert (await backend.play(sid, "dev1", "TRK", 0, "i")).code == "unknown"
        assert (await backend.play(None, "dev1", "TRK", 0, "i")).code == "no_session"
        assert (await backend.play(sid, "dev1", "", 0, "i")).code == "no_session"
    await http.aclose()


async def test_play_refreshes_token_once_on_401(clock: Clock) -> None:
    backend, auth, sid, http = await _backend(clock)
    with respx.mock() as mock:
        mock.post(TOKEN_URL).respond(200, json={"access_token": "A2", "expires_in": 3600})
        calls = mock.put("https://api.spotify.com/v1/me/player/play").mock(
            side_effect=[httpx.Response(401), httpx.Response(204)]
        )
        assert (await backend.play(sid, "d", "T", 0, "i")).ok
        assert [c.request.headers["authorization"] for c in calls.calls] == ["Bearer A1", "Bearer A2"]
    await http.aclose()


async def test_fake_backend_logs_only_instance_id(caplog) -> None:  # type: ignore[no-untyped-def]
    import logging

    from app.spotify.client import FakeAudioBackend

    with caplog.at_level(logging.INFO):
        out = await FakeAudioBackend().play("s", "d", "SECRET_TRACK", 10_000, "inst-123")
    assert out.ok and "inst-123" in caplog.text and "SECRET_TRACK" not in caplog.text


def test_callback_rejects_token_without_streaming_scope(make_app: MakeApp) -> None:
    """Regresion: sin `streaming` el SDK fallaba despues con 403 'Token does not satisfy scope'."""
    app, svc = make_app(
        auth_mode="spotify", token_enc_key="", spotify_client_id="CID", spotify_redirect_uri="https://x/cb"
    )
    with respx.mock(assert_all_called=False) as mock, TestClient(app) as c:
        mock.post(TOKEN_URL).respond(
            200,
            json={
                "access_token": "A",
                "refresh_token": "R",
                "expires_in": 3600,
                "scope": "streaming user-read-private user-read-playback-state",  # falta user-read-email
            },
        )
        t = str(c.post("/api/session").json()["session_token"])
        r = c.post("/api/auth/spotify/start", json={"return_to": "/"}, headers={"Authorization": f"Bearer {t}"})
        state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
        cb = c.get("/api/auth/spotify/callback", params={"code": "abc", "state": state}, follow_redirects=False)
        assert cb.status_code == 400 and cb.json()["detail"] == "missing_scope"
        assert svc.auth.has_session(hash_token(t)) is False
