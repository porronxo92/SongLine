"""Account authentication. Bearer credentials here never authenticate game sessions."""

import asyncio
import logging
import re
import secrets
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from app.accounts.mail import send_reset
from app.accounts.security import DUMMY_HASH, hash_password, token_hash, verify_password
from app.api.deps import bearer_token, client_ip, get_services
from app.services import Services

router = APIRouter(prefix="/account", tags=["account"])
log = logging.getLogger(__name__)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("invalid email")
        return value


class Registration(Credentials):
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(default="", max_length=80)


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    premium = user["plan"] == "premium"
    return {
        "id": str(user["id"]), "email": user["email"], "display_name": user["display_name"],
        "plan": user["plan"], "max_teams": 6 if premium else 2,
        "max_cards": None if premium else 5,
        "pack_slugs": sorted(set(user.get("pack_slugs") or ["mix"]) | {"mix"}),
    }


async def storage(svc: Services = Depends(get_services)):  # type: ignore[no-untyped-def]
    try:
        yield svc.accounts
    except SQLAlchemyError:
        log.exception("account storage unavailable")
        raise HTTPException(status_code=503, detail="account_unavailable") from None


def limit(request: Request, svc: Services) -> None:
    if not svc.account_limiter.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": "60"})


async def issue(repo: Any, user: dict[str, Any], response: Response) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    await repo.add_session(user["id"], token_hash(token))
    response.headers["Cache-Control"] = "no-store"
    return {"token": token, "user": public_user(user)}


@router.post("/register", status_code=201)
async def register(body: Registration, request: Request, response: Response,
                   svc: Services = Depends(get_services), repo: Any = Depends(storage)) -> dict[str, Any]:
    limit(request, svc)
    password_hash = await asyncio.to_thread(hash_password, body.password)
    user = await repo.create(body.email, body.display_name.strip(), password_hash)
    if user is None:
        raise HTTPException(status_code=409, detail="account_exists")
    return await issue(repo, user, response)


@router.post("/login")
async def login(body: Credentials, request: Request, response: Response,
                svc: Services = Depends(get_services), repo: Any = Depends(storage)) -> dict[str, Any]:
    limit(request, svc)
    user = await repo.find_email(body.email)
    valid = await asyncio.to_thread(verify_password, body.password, user["password_hash"] if user else DUMMY_HASH)
    if user is None or not valid:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    return await issue(repo, user, response)


async def current_account(authorization: str | None = Header(default=None),
                          repo: Any = Depends(storage)) -> dict[str, Any]:
    token = bearer_token(authorization)
    user = await repo.session_user(token_hash(token)) if token and len(token) <= 200 else None
    if user is None:
        raise HTTPException(status_code=401, detail="account_required")
    return user


@router.get("/me")
async def me(response: Response, user: dict[str, Any] = Depends(current_account)) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return public_user(user)


@router.post("/logout", status_code=204)
async def logout(authorization: str | None = Header(default=None),
                 user: dict[str, Any] = Depends(current_account), repo: Any = Depends(storage)) -> Response:
    await repo.delete_session(token_hash(bearer_token(authorization) or ""))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


async def optional_account(x_account_token: str | None = Header(default=None),
                           repo: Any = Depends(storage)) -> dict[str, Any] | None:
    """Room requests keep their game bearer and carry the account separately."""
    if x_account_token is None:
        return None
    user = await repo.session_user(token_hash(x_account_token)) if 16 <= len(x_account_token) <= 200 else None
    if user is None:
        raise HTTPException(status_code=401, detail="account_required")
    return user


class RecoveryEmail(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    _normalize = field_validator("email")(Credentials.normalize_email.__func__)


class ResetPassword(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=12, max_length=128)


def deliver_reset(svc: Services, email: str, url: str) -> None:
    try:
        send_reset(svc.config, email, url)
    except Exception:
        # Delivery is background work; no secret URLs or SMTP credentials in logs.
        log.warning("password recovery email delivery failed")


@router.post("/forgot")
async def forgot(body: RecoveryEmail, request: Request, response: Response, background_tasks: BackgroundTasks,
                 svc: Services = Depends(get_services), repo: Any = Depends(storage)) -> dict[str, bool]:
    limit(request, svc)
    if not svc.config.smtp_host or not svc.config.smtp_from:
        raise HTTPException(status_code=503, detail="recovery_unavailable")
    user = await repo.find_email(body.email)
    if user is not None:
        token = secrets.token_urlsafe(32)
        await repo.save_reset(user["id"], token_hash(token))
        url = svc.config.public_origin.rstrip("/") + "/reset-password?token=" + token
        background_tasks.add_task(deliver_reset, svc, body.email, url)
    response.headers["Cache-Control"] = "no-store"
    return {"accepted": True}


@router.post("/reset", status_code=204)
async def reset(body: ResetPassword, request: Request,
                svc: Services = Depends(get_services), repo: Any = Depends(storage)) -> Response:
    limit(request, svc)
    password_hash = await asyncio.to_thread(hash_password, body.password)
    if not await repo.consume_reset(token_hash(body.token), password_hash):
        raise HTTPException(status_code=400, detail="invalid_reset_token")
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
