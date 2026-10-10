"""Runtime configuration (environment variables / .env)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    auth_mode: Literal["spotify", "fake"] = "spotify"
    catalog_source: Literal["postgres", "csv"] = "postgres"
    catalog_csv_path: Path = REPO_ROOT / "catalog" / "songs.csv"
    persistence: Literal["postgres", "none"] = "postgres"
    database_url: str = "postgresql+asyncpg://hitster:hitster@localhost:5432/hitster"
    spotify_client_id: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:5173/api/auth/spotify/callback"
    token_enc_key: str = ""  # Fernet key (urlsafe base64, 32 bytes). Ephemeral if empty.
    public_origin: str = "http://localhost:5173"
    admin_token: str = ""  # >= 32 chars, otherwise /api/admin is disabled
    session_secret: str = ""  # HMAC key for session tokens. Ephemeral (with a warning) if empty.
    rate_auth_start_per_min: int = 10
    ws_max_conns_per_room: int = 12
    ws_max_conns_per_ip: int = 40
    ws_msgs_per_s: float = 20.0
    ws_burst: int = 30
    rate_room_create_per_min: int = 5
    rate_code_attempts_per_min: int = 20
    room_idle_ttl_s: int = 2 * 3600


LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})
ADMIN_TOKEN_MIN_LEN = 32


def is_local_origin(origin: str) -> bool:
    return (urlparse(origin).hostname or "") in LOCAL_HOSTS


def check_startup(cfg: AppConfig) -> None:
    """Refuses unsafe combinations before serving anything."""
    local = is_local_origin(cfg.public_origin)
    if cfg.auth_mode == "fake" and not local:
        raise RuntimeError(
            "AUTH_MODE=fake is only allowed when PUBLIC_ORIGIN is localhost or 127.0.0.1 "
            f"(got {cfg.public_origin!r})"
        )
    if not cfg.session_secret and not local:
        raise RuntimeError("SESSION_SECRET is required when PUBLIC_ORIGIN is not localhost")
