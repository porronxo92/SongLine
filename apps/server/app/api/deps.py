"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request

from app.services import Services, hash_token

MIN_TOKEN_LEN = 16


def get_services(request: Request) -> Services:
    svc: Services = request.app.state.services
    return svc


def client_ip(request: Request) -> str:
    """Peer address. Behind Caddy uvicorn (--proxy-headers --forwarded-allow-ips) rewrites it from
    X-Forwarded-For only when the peer is a trusted proxy; the header is never read here."""
    return request.client.host if request.client else "unknown"


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or len(value) < MIN_TOKEN_LEN:
        return None
    return value


def optional_session_hash(
    authorization: str | None = Header(default=None), svc: Services = Depends(get_services)
) -> str | None:
    """None for a missing or unsigned/forged token (anonymous caller)."""
    tok = bearer_token(authorization)
    if tok is None or not svc.signer.verify(tok):
        return None
    return hash_token(tok)


def session_hash(
    authorization: str | None = Header(default=None), svc: Services = Depends(get_services)
) -> str:
    tok = bearer_token(authorization)
    if tok is None:
        raise HTTPException(status_code=401, detail="missing_session")
    if not svc.signer.verify(tok):
        raise HTTPException(status_code=401, detail="invalid_session")
    return hash_token(tok)
