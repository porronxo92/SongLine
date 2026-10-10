"""Room REST routes + the host-only preview audio proxy."""

from __future__ import annotations

import io
import wave
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.deps import client_ip, get_services, optional_session_hash, session_hash
from app.game.models import EDITABLE_SETTINGS, Phase, Settings
from app.rooms.manager import RoomsFull
from app.services import Services
from app.ws.protocol import COLOR_PATTERN

router = APIRouter()

SUGGESTED_COLORS = ["#E63946", "#2A9D8F", "#F4A261", "#7B2CBF"]


class CreateRoomBody(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)
    name: str | None = Field(default=None, max_length=20)
    color: str | None = Field(default=None, pattern=COLOR_PATTERN)


@router.post("/rooms")
def create_room(
    body: CreateRoomBody,
    request: Request,
    svc: Services = Depends(get_services),
    sh: str = Depends(session_hash),
) -> dict[str, Any]:
    if not svc.room_limiter.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="rate_limited")
    bad = set(body.settings) - EDITABLE_SETTINGS
    if bad:
        raise HTTPException(status_code=422, detail=f"settings not editable: {sorted(bad)}")
    try:
        settings = Settings.model_validate(body.settings)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail="invalid settings") from e
    try:
        rt = svc.manager.create(sh, (body.name or "").strip() or "Equipo 1", body.color, settings)
    except RoomsFull as e:
        raise HTTPException(status_code=503, detail="rooms_full") from e
    code = rt.room.code
    ws_origin = svc.config.public_origin.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
    return {"code": code, "ws_url": f"{ws_origin}/ws/rooms/{code}", "ws_path": f"/ws/rooms/{code}", "slot": 0}


@router.get("/rooms/{code}")
def get_room(
    code: str,
    request: Request,
    svc: Services = Depends(get_services),
    sh: str | None = Depends(optional_session_hash),
) -> dict[str, Any]:
    ip = client_ip(request)
    if svc.code_limiter.blocked(ip):
        raise HTTPException(status_code=429, detail="rate_limited")
    rt = svc.manager.get(code)
    if rt is None:
        svc.code_limiter.allow(ip)  # records a failed attempt
        raise HTTPException(status_code=404, detail="room_not_found")
    room = rt.room
    slots = [
        {
            "slot": t.slot,
            "taken": t.claimed,
            "name": t.name if t.claimed else None,
            "color": t.color if t.claimed else None,
            "suggested_color": SUGGESTED_COLORS[t.slot % len(SUGGESTED_COLORS)],
            "is_host": t.claimed and t.slot == room.host_slot,
        }
        for t in room.teams
    ]
    if room.phase != Phase.LOBBY:
        status = "started"
    elif all(s["taken"] for s in slots):
        status = "full"
    else:
        status = "open"
    return {
        "status": status,
        "mode": room.settings.mode,
        "team_count": room.settings.team_count,
        "target_cards": room.settings.target_cards,
        "slots": slots,
        "your_slot": room.slot_of(sh) if sh else None,
    }


def _silence_wav(seconds: float = 3.0, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(rate)
        w.writeframes(b"\x80" * int(seconds * rate))
    return buf.getvalue()


@router.get("/turn/audio")
async def turn_audio(
    code: str = Query(min_length=4, max_length=4),
    svc: Services = Depends(get_services),
    sh: str = Depends(session_hash),
) -> Response:
    """Deezer preview proxy (D7). Only the host, only while the current turn uses the preview source."""
    rt = svc.manager.get(code)
    if rt is None:
        raise HTTPException(status_code=404, detail="room_not_found")
    room = rt.room
    if room.teams[room.host_slot].session_token_hash != sh:
        raise HTTPException(status_code=403, detail="host_only")
    turn = room.turn
    if (
        turn is None
        or not turn.started_playing
        or turn.audio_source != "preview"
        or room.phase
        not in (
            Phase.PLACING,
            Phase.GUESSING,
            Phase.OBJECTION,
        )
    ):
        raise HTTPException(status_code=403, detail="no_preview_turn")
    headers = {"Cache-Control": "no-store"}
    if svc.fake:
        return Response(_silence_wav(), media_type="audio/wav", headers=headers)
    card = turn.card
    url = await svc.deezer.preview_url(card.isrc, card.title, card.artist)
    if url is None:
        raise HTTPException(status_code=404, detail="preview_unavailable")
    req = svc.http.build_request("GET", url)
    upstream = await svc.http.send(req, stream=True)
    if upstream.status_code != 200:
        await upstream.aclose()
        raise HTTPException(status_code=502, detail="preview_upstream_error")

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        except httpx.HTTPError:
            return
        finally:
            await upstream.aclose()

    return StreamingResponse(body(), media_type="audio/mpeg", headers=headers)
