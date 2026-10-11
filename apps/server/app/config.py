"""Runtime configuration (environment variables / .env)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


def normalize_database_url(url: str) -> str:
    """Accepts a provider URL (Neon: `postgresql://...?sslmode=require&channel_binding=require`).

    Switches the driver to asyncpg and turns `sslmode` into asyncpg's `ssl`; drops `channel_binding`,
    which asyncpg does not take as a connect argument.
    """
    parts = urlparse(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode and sslmode != "disable" and "ssl" not in query:
        query["ssl"] = "require"
    return urlunparse(parts._replace(scheme=scheme, query=urlencode(query)))


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore", case_sensitive=False)

    auth_mode: Literal["spotify", "fake"] = "spotify"
    catalog_source: Literal["postgres", "csv"] = "postgres"
    catalog_csv_path: Path = REPO_ROOT / "catalog" / "songs.csv"
    catalog_packs_dir: Path | None = None  # default: <catalog_csv_path dir>/packs
    catalog_packs_json: Path | None = None  # default: <catalog_csv_path dir>/packs.json
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

    @property
    def packs_dir(self) -> Path:
        return self.catalog_packs_dir or self.catalog_csv_path.parent / "packs"

    @property
    def packs_json(self) -> Path:
        return self.catalog_packs_json or self.catalog_csv_path.parent / "packs.json"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        return normalize_database_url(v)


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
