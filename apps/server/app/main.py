"""FastAPI application factory. Run: uvicorn app.main:app --port 8000 (1 worker only)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, catalog, rooms
from app.config import ADMIN_TOKEN_MIN_LEN, AppConfig, check_startup
from app.services import Services, build_services
from app.ws.router import router as ws_router

log = logging.getLogger("hitster")
# uvicorn solo configura sus propios loggers: sin esto, los avisos INFO de la app (p. ej. los permisos de Spotify) no salen.
logging.getLogger("app").setLevel(logging.INFO)
if not logging.getLogger("app").handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    logging.getLogger("app").addHandler(_h)


def create_app(config: AppConfig | None = None, services: Services | None = None) -> FastAPI:
    cfg = config or AppConfig()
    check_startup(cfg)
    if cfg.admin_token and len(cfg.admin_token) < ADMIN_TOKEN_MIN_LEN:
        log.warning("ADMIN_TOKEN is shorter than %d characters: /api/admin is disabled", ADMIN_TOKEN_MIN_LEN)
    svc = services or build_services(cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            await svc.reload_songs()
        except Exception:  # noqa: BLE001
            log.exception("could not load the catalog")
        try:
            n = await svc.manager.restore_all()
            if n:
                log.info("restored %d rooms", n)
        except Exception:  # noqa: BLE001
            log.exception("could not restore snapshots")
        svc.manager.start_gc()
        yield
        await svc.manager.shutdown()
        await svc.http.aclose()

    app = FastAPI(title="SongLine", lifespan=lifespan)
    app.state.services = svc
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[svc.config.public_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api = APIRouter(prefix="/api")
    for r in (auth.router, rooms.router, catalog.router, admin.router):
        api.include_router(r)
    app.include_router(api)
    app.include_router(ws_router)
    return app


app = create_app()
