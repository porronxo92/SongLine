"""Spotify OAuth (Authorization Code + PKCE), brokered by the backend, and the token store."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.spotify.crypto import TokenCipher

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
log = logging.getLogger(__name__)

# El Web Playback SDK exige streaming + user-read-email + user-read-private; sin los tres, check_scope da 403.
SCOPES = "streaming user-read-email user-read-private user-read-playback-state user-modify-playback-state"
SDK_REQUIRED_SCOPES = ("streaming", "user-read-email", "user-read-private")
STATE_TTL_S = 600
MAX_PENDING = 200
NONCE_COOKIE = "hc_oauth_nonce"
NONCE_COOKIE_PATH = "/api/auth/spotify"
REFRESH_MARGIN_S = 300


def new_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def safe_return_to(value: str) -> str:
    """Only same-origin absolute paths (blocks open redirects)."""
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


@dataclass
class PendingAuth:
    verifier: str
    session_hash: str
    return_to: str
    created: float
    nonce: str


@dataclass
class StoredTokens:
    access_enc: bytes
    refresh_enc: bytes
    expires_at: float
    premium_verified: bool = False


class SpotifyAuthError(Exception):
    pass


class SpotifyAuth:
    def __init__(
        self,
        client_id: str,
        redirect_uri: str,
        cipher: TokenCipher,
        http: httpx.AsyncClient,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.cipher = cipher
        self.http = http
        self.clock = clock
        self._pending: dict[str, PendingAuth] = {}
        self._tokens: dict[str, StoredTokens] = {}

    # -- login flow
    def start_login(self, session_hash: str, return_to: str) -> tuple[str, str, str]:
        """Registers a pending login. Returns (state, nonce, pkce_challenge)."""
        self._gc()
        while len(self._pending) >= MAX_PENDING:  # hard cap: drop the oldest
            del self._pending[next(iter(self._pending))]
        verifier, challenge = new_pkce_pair()
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        self._pending[state] = PendingAuth(
            verifier, session_hash, safe_return_to(return_to), self.clock(), nonce
        )
        return state, nonce, challenge

    def build_login_url(self, state: str, challenge: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
            "scope": SCOPES,
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    def take_pending(self, state: str, nonce: str | None) -> PendingAuth:
        """Single use. The browser cookie must carry the nonce bound to this state (login CSRF)."""
        self._gc()
        pending = self._pending.pop(state, None)
        if pending is None:
            # Estado desconocido: caducado (> STATE_TTL_S), ya usado, o el servidor se reinicio tras /start.
            log.warning("login rechazado: state desconocido (pendientes en memoria: %d)", len(self._pending))
            raise SpotifyAuthError("invalid_state")
        if not nonce:
            log.warning("login rechazado: el navegador no envio la cookie de nonce")
            raise SpotifyAuthError("invalid_state")
        if not secrets.compare_digest(nonce.encode("utf-8", "surrogatepass"), pending.nonce.encode()):
            log.warning("login rechazado: la cookie de nonce no coincide con este state")
            raise SpotifyAuthError("invalid_state")
        return pending

    async def handle_callback(self, code: str, state: str, nonce: str | None) -> str:
        """Exchanges the code; returns the `return_to` path."""
        pending = self.take_pending(state, nonce)
        resp = await self.http.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "code_verifier": pending.verifier,
            },
        )
        if resp.status_code != 200:
            raise SpotifyAuthError("token_exchange_failed")
        data = resp.json()
        granted = set(str(data.get("scope", "")).split())
        log.info("spotify login: scopes concedidos = %s", sorted(granted))
        missing = [sc for sc in SDK_REQUIRED_SCOPES if sc not in granted]
        if missing:
            # Sin ellos el Web Playback SDK falla despues con 403 "Token does not satisfy scope".
            log.warning("spotify login rechazado: faltan scopes %s", missing)
            raise SpotifyAuthError("missing_scope")
        self._store(pending.session_hash, data, previous_refresh=None)
        return pending.return_to

    # -- tokens
    def _store(self, session_hash: str, data: dict[str, object], previous_refresh: str | None) -> None:
        refresh = str(data.get("refresh_token") or previous_refresh or "")
        prev = self._tokens.get(session_hash)
        self._tokens[session_hash] = StoredTokens(
            access_enc=self.cipher.encrypt(str(data["access_token"])),
            refresh_enc=self.cipher.encrypt(refresh),
            expires_at=self.clock() + float(str(data.get("expires_in", 3600))),
            premium_verified=prev.premium_verified if prev else False,
        )

    def has_session(self, session_hash: str) -> bool:
        return session_hash in self._tokens

    def expires_at(self, session_hash: str) -> float | None:
        t = self._tokens.get(session_hash)
        return t.expires_at if t else None

    async def get_access_token(self, session_hash: str, force_refresh: bool = False) -> str | None:
        t = self._tokens.get(session_hash)
        if t is None:
            return None
        if force_refresh or t.expires_at - self.clock() < REFRESH_MARGIN_S:
            refresh = self.cipher.decrypt(t.refresh_enc)
            resp = await self.http.post(
                TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": self.client_id},
            )
            if resp.status_code != 200:
                return None
            self._store(session_hash, resp.json(), previous_refresh=refresh)
            t = self._tokens[session_hash]
        return self.cipher.decrypt(t.access_enc)

    def set_premium_verified(self, session_hash: str, ok: bool) -> None:
        t = self._tokens.get(session_hash)
        if t:
            t.premium_verified = ok

    def premium_verified(self, session_hash: str) -> bool:
        t = self._tokens.get(session_hash)
        return bool(t and t.premium_verified)

    def logout(self, session_hash: str) -> None:
        self._tokens.pop(session_hash, None)

    def _gc(self) -> None:
        """`_pending` is insertion-ordered by creation time: pop expired entries from the front."""
        now = self.clock()
        while self._pending:
            k = next(iter(self._pending))
            if now - self._pending[k].created <= STATE_TTL_S:
                break
            del self._pending[k]
