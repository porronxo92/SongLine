"""Session + Spotify auth routes (DISENO sections 5 and 7)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from app.api.deps import client_ip, get_services, optional_session_hash, session_hash
from app.services import Services
from app.spotify.oauth import NONCE_COOKIE, NONCE_COOKIE_PATH, STATE_TTL_S, SpotifyAuthError

router = APIRouter()


@router.post("/session")
def create_session(svc: Services = Depends(get_services)) -> dict[str, str]:
    return {"session_token": svc.signer.issue()}


@router.get("/auth/status")
def auth_status(
    svc: Services = Depends(get_services), sh: str | None = Depends(optional_session_hash)
) -> dict[str, Any]:
    logged = svc.fake or (sh is not None and svc.auth.has_session(sh))
    return {
        "auth_mode": svc.config.auth_mode,
        "logged_in": bool(logged),
        "premium_verified": svc.fake or (sh is not None and svc.auth.premium_verified(sh)),
    }


class StartBody(BaseModel):
    return_to: str = Field(default="/", max_length=500)


@router.post("/auth/spotify/start")
def spotify_start(
    body: StartBody,
    request: Request,
    svc: Services = Depends(get_services),
    sh: str = Depends(session_hash),
) -> JSONResponse:
    """Starts the login. Any valid signed session may start it (the login happens before the room is
    created); the CSRF defence is the nonce cookie, set only in the browser that made this call."""
    if not svc.auth_limiter.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="rate_limited")
    state, nonce, challenge = svc.auth.start_login(sh, body.return_to)
    if svc.fake:
        url = f"/api/auth/spotify/callback?{urlencode({'code': 'fake', 'state': state})}"
    else:
        url = svc.auth.build_login_url(state, challenge)
    resp = JSONResponse({"url": url})
    resp.set_cookie(
        NONCE_COOKIE,
        nonce,
        max_age=STATE_TTL_S,
        path=NONCE_COOKIE_PATH,
        httponly=True,
        secure=svc.config.public_origin.startswith("https://"),
        samesite="lax",
    )
    return resp


@router.get("/auth/spotify/callback")
async def spotify_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str | None = Query(default=None),
    svc: Services = Depends(get_services),
) -> Response:
    origin = svc.config.public_origin.rstrip("/")
    nonce = request.cookies.get(NONCE_COOKIE)
    resp: Response
    if error or not code:
        resp = RedirectResponse(origin + "/?auth_error=denied", status_code=302)
    else:
        try:
            if svc.fake:
                return_to = svc.auth.take_pending(state, nonce).return_to
            else:
                return_to = await svc.auth.handle_callback(code, state, nonce)
            resp = RedirectResponse(origin + return_to, status_code=302)
        except SpotifyAuthError as e:
            resp = JSONResponse({"detail": str(e)}, status_code=400)
    resp.delete_cookie(NONCE_COOKIE, path=NONCE_COOKIE_PATH)
    return resp


@router.get("/auth/spotify/token")
async def spotify_token(
    svc: Services = Depends(get_services), sh: str = Depends(session_hash)
) -> dict[str, Any]:
    if svc.fake:
        return {"access_token": "fake-token", "expires_at": svc.clock() + 3600}
    token = await svc.auth.get_access_token(sh)
    if token is None:
        raise HTTPException(status_code=401, detail="not_logged_in")
    return {"access_token": token, "expires_at": svc.auth.expires_at(sh)}


class VerifyPremiumBody(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)


@router.post("/auth/spotify/verify-premium")
async def verify_premium(
    body: VerifyPremiumBody, svc: Services = Depends(get_services), sh: str = Depends(session_hash)
) -> dict[str, Any]:
    if svc.fake:
        return {"premium": True}
    ok, reason = await svc.spotify.verify_premium(sh, body.device_id)
    svc.auth.set_premium_verified(sh, ok)
    if ok:
        return {"premium": True}
    return {"premium": False, "reason": reason}


@router.post("/auth/logout", status_code=204)
def logout(svc: Services = Depends(get_services), sh: str = Depends(session_hash)) -> Response:
    svc.auth.logout(sh)
    return Response(status_code=204)
