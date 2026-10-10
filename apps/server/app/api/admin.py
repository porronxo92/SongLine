"""Minimal catalog admin (Postgres only), guarded by the ADMIN_TOKEN env var."""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_services
from app.catalog.repo import PostgresSongRepository
from app.config import ADMIN_TOKEN_MIN_LEN
from app.services import Services

router = APIRouter(prefix="/admin")


def require_admin(
    x_admin_token: str | None = Header(default=None), svc: Services = Depends(get_services)
) -> PostgresSongRepository:
    expected = svc.config.admin_token
    if len(expected) < ADMIN_TOKEN_MIN_LEN:
        raise HTTPException(status_code=404, detail="admin_disabled")
    if not x_admin_token or not secrets.compare_digest(
        x_admin_token.encode("utf-8", "surrogatepass"), expected.encode()
    ):
        raise HTTPException(status_code=401, detail="bad_admin_token")
    if not isinstance(svc.repo, PostgresSongRepository):
        raise HTTPException(status_code=501, detail="admin_requires_postgres_catalog")
    return svc.repo


@router.get("/songs")
async def list_songs(
    status: str | None = None, repo: PostgresSongRepository = Depends(require_admin)
) -> list[dict[str, Any]]:
    return await repo.list_all(status)


Alias = Annotated[str, Field(min_length=1, max_length=200)]


class SongPatch(BaseModel):
    year: int | None = Field(default=None, ge=1900, le=2100)
    year_status: str | None = Field(default=None, max_length=32)
    year_note: str | None = Field(default=None, max_length=500)
    title_aliases: list[Alias] | None = Field(default=None, max_length=20)
    artist_aliases: list[Alias] | None = Field(default=None, max_length=20)
    enabled: bool | None = None


@router.patch("/songs/{song_id}")
async def patch_song(
    song_id: int,
    patch: SongPatch,
    repo: PostgresSongRepository = Depends(require_admin),
    svc: Services = Depends(get_services),
) -> dict[str, Any]:
    row = await repo.update(song_id, patch.model_dump(exclude_none=True))
    if row is None:
        raise HTTPException(status_code=404, detail="song_not_found")
    await svc.reload_songs()
    return row
