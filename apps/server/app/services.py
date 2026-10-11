"""Dependency container, built once per app (and per test)."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from app.catalog.packs import PackDef, load_pack_defs
from app.catalog.repo import CsvSongRepository, PostgresSongRepository, SongRepository
from app.config import AppConfig
from app.game.models import Song
from app.ratelimit import RateLimiter
from app.rooms.manager import RoomManager
from app.rooms.runtime import RuntimeDeps
from app.rooms.snapshot import NullPersistence, Persistence, PostgresPersistence
from app.sessions import SessionSigner
from app.spotify.client import AudioBackend, FakeAudioBackend, SpotifyAudioBackend
from app.spotify.crypto import TokenCipher
from app.spotify.deezer import DeezerPreview
from app.spotify.oauth import SpotifyAuth

log = logging.getLogger(__name__)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Services:
    config: AppConfig
    manager: RoomManager
    auth: SpotifyAuth
    backend: AudioBackend
    spotify: SpotifyAudioBackend
    deezer: DeezerPreview
    repo: SongRepository
    http: httpx.AsyncClient
    clock: Callable[[], float]
    room_limiter: RateLimiter
    code_limiter: RateLimiter
    auth_limiter: RateLimiter
    signer: SessionSigner
    ws_per_ip: dict[str, int] = field(default_factory=dict)
    songs: list[Song] = field(default_factory=list)
    packs: list[PackDef] = field(default_factory=list)

    @property
    def pack_slugs(self) -> frozenset[str]:
        return frozenset(p.slug for p in self.packs)

    @property
    def fake(self) -> bool:
        return self.config.auth_mode == "fake"

    async def reload_songs(self) -> list[Song]:
        songs = await self.repo.load_enabled()
        if not self.fake:
            songs = [s for s in songs if s.track_id]  # Spotify needs a track id
        self.songs = songs
        log.info("catalog loaded: %d songs", len(songs))
        return songs


def build_services(
    config: AppConfig,
    *,
    http: httpx.AsyncClient | None = None,
    repo: SongRepository | None = None,
    persistence: Persistence | None = None,
    clock: Callable[[], float] = time.time,
    timer_scale: float = 1.0,
) -> Services:
    http = http or httpx.AsyncClient(timeout=10.0)
    if repo is None:
        repo = (
            CsvSongRepository(config.catalog_csv_path, config.packs_dir)
            if config.catalog_source == "csv"
            else PostgresSongRepository(config.database_url)
        )
    if persistence is None:
        persistence = (
            NullPersistence() if config.persistence == "none" else PostgresPersistence(config.database_url)
        )
    auth = SpotifyAuth(
        config.spotify_client_id, config.spotify_redirect_uri, TokenCipher(config.token_enc_key), http, clock
    )
    spotify = SpotifyAudioBackend(auth, http)
    backend: AudioBackend = FakeAudioBackend() if config.auth_mode == "fake" else spotify
    deps = RuntimeDeps(backend=backend, persistence=persistence, clock=clock, timer_scale=timer_scale)
    return Services(
        config=config,
        manager=RoomManager(deps, idle_ttl_s=config.room_idle_ttl_s),
        auth=auth,
        backend=backend,
        spotify=spotify,
        deezer=DeezerPreview(http),
        repo=repo,
        http=http,
        clock=clock,
        room_limiter=RateLimiter(config.rate_room_create_per_min),
        code_limiter=RateLimiter(config.rate_code_attempts_per_min),
        auth_limiter=RateLimiter(config.rate_auth_start_per_min),
        signer=SessionSigner(config.session_secret),
        packs=load_pack_defs(config.packs_json),
    )
