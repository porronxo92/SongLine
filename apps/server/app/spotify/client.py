"""Spotify Web API calls (play / pause / transfer) and the audio backends used by the room runtime."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.spotify.oauth import SpotifyAuth

log = logging.getLogger(__name__)
API = "https://api.spotify.com/v1"


@dataclass(frozen=True)
class PlayOutcome:
    ok: bool
    code: str = "ok"  # premium_required | device_gone | rate_limited | no_session | unknown
    retry_after_s: float | None = None


class AudioBackend(Protocol):
    async def play(
        self, session_id: str | None, device_id: str | None, track_id: str, position_ms: int, instance_id: str
    ) -> PlayOutcome: ...

    async def pause(self, session_id: str | None, device_id: str | None) -> None: ...


def classify(resp: httpx.Response) -> PlayOutcome:
    if resp.status_code in (200, 202, 204):
        return PlayOutcome(True)
    reason = ""
    try:
        reason = str(resp.json().get("error", {}).get("reason", ""))
    except Exception:  # noqa: BLE001
        pass
    if resp.status_code == 403 and reason == "PREMIUM_REQUIRED":
        return PlayOutcome(False, "premium_required")
    if resp.status_code == 404:
        return PlayOutcome(False, "device_gone")
    if resp.status_code == 429:
        try:
            retry = float(resp.headers.get("Retry-After", "1"))
        except ValueError:
            retry = 1.0
        return PlayOutcome(False, "rate_limited", retry)
    return PlayOutcome(False, "unknown")


class SpotifyAudioBackend:
    def __init__(self, auth: SpotifyAuth, http: httpx.AsyncClient) -> None:
        self.auth = auth
        self.http = http

    async def _request(
        self,
        session_id: str,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
    ) -> httpx.Response | None:
        for attempt in (0, 1):
            token = await self.auth.get_access_token(session_id, force_refresh=attempt == 1)
            if token is None:
                return None
            resp = await self.http.request(
                method, f"{API}{path}", params=params, json=json, headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code != 401:
                return resp
        return resp

    async def verify_premium(self, session_id: str, device_id: str) -> tuple[bool, str | None]:
        """PUT /me/player with play:false. 403 PREMIUM_REQUIRED means no Premium."""
        resp = await self._request(
            session_id, "PUT", "/me/player", json={"device_ids": [device_id], "play": False}
        )
        if resp is None:
            return False, "no_session"
        out = classify(resp)
        if out.ok:
            return True, None
        if resp.status_code == 403:
            text = resp.text.lower()
            if "premium" in text:
                return False, "premium_required"
            return False, "user_not_registered"
        return False, out.code

    async def play(
        self, session_id: str | None, device_id: str | None, track_id: str, position_ms: int, instance_id: str
    ) -> PlayOutcome:
        if session_id is None or device_id is None or not track_id:
            return PlayOutcome(False, "no_session")
        resp = await self._request(
            session_id,
            "PUT",
            "/me/player/play",
            params={"device_id": device_id},
            json={"uris": [f"spotify:track:{track_id}"], "position_ms": position_ms},
        )
        if resp is None:
            return PlayOutcome(False, "no_session")
        return classify(resp)

    async def pause(self, session_id: str | None, device_id: str | None) -> None:
        if session_id is None or device_id is None:
            return
        await self._request(session_id, "PUT", "/me/player/pause", params={"device_id": device_id})


class FakeAudioBackend:
    """AUTH_MODE=fake: play is a no-op. Logs ONLY the opaque instance_id."""

    async def play(
        self, session_id: str | None, device_id: str | None, track_id: str, position_ms: int, instance_id: str
    ) -> PlayOutcome:
        log.info("fake play instance_id=%s position_ms=%s", instance_id, position_ms)
        return PlayOutcome(True)

    async def pause(self, session_id: str | None, device_id: str | None) -> None:
        log.info("fake pause")
