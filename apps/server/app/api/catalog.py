"""Catalog + health routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_services
from app.catalog.repo import catalog_stats
from app.services import Services

router = APIRouter()


@router.get("/catalog/stats")
def stats(svc: Services = Depends(get_services)) -> dict[str, Any]:
    return catalog_stats(svc.songs)


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
