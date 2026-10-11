"""WebSocket endpoint /ws/rooms/{code}. Auth is the first message (`hello`), never the URL."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.game import commands as C
from app.game.commands import GameError
from app.rooms.runtime import Conn, RoomRuntime, envelope
from app.services import Services, hash_token
from app.ws import protocol as P

log = logging.getLogger(__name__)
router = APIRouter()

PREVIEW_MIN_INTERVAL_S = 0.1
HELLO_TIMEOUT_S = 5.0
MAX_MESSAGE_CHARS = 16384

CLOSE_BAD_SESSION = 4401
CLOSE_NOT_FOUND = 4404
CLOSE_RATE = 4429
CLOSE_TOO_BIG = 1009


def ws_ip(ws: WebSocket) -> str:
    """Peer address (uvicorn --proxy-headers rewrites it for trusted proxies only; never read XFF here)."""
    return ws.client.host if ws.client else "unknown"


class TokenBucket:
    def __init__(self, rate: float, burst: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.rate = rate
        self.burst = float(burst)
        self.clock = clock
        self.level = float(burst)
        self.last = clock()

    def take(self) -> bool:
        now = self.clock()
        self.level = min(self.burst, self.level + (now - self.last) * self.rate)
        self.last = now
        if self.level < 1.0:
            return False
        self.level -= 1.0
        return True


async def _error(rt: RoomRuntime, conn: Conn, ref_id: str, code: str, message: str) -> None:
    await rt._send(conn, envelope("error", {"ref_id": ref_id, "code": code, "message": message}))


def build_command(
    svc: Services, rt: RoomRuntime, conn: Conn, env: P.Envelope, m: BaseModel
) -> C.Command | None:
    """Maps a client message to an engine command. The sender slot comes from the token, never the payload."""
    sender = rt.slot_of(conn)
    t = env.type
    if t == "claim_slot":
        assert isinstance(m, P.ClaimSlotMsg)
        return C.ClaimSlot(conn.session_hash, m.slot, m.name, m.color)
    if t == "device_ready":
        assert isinstance(m, P.DeviceReadyMsg)
        fake = svc.fake
        premium = fake or svc.auth.premium_verified(conn.session_hash)
        return C.DeviceReady(sender, m.device_id, m.provider, premium_ok=premium, unlock=fake)
    if t == "audio_unlocked":
        return C.AudioUnlocked(sender)
    if t == "audio_report":
        assert isinstance(m, P.AudioReportMsg)
        return C.AudioReport(sender, m.playing)
    if t == "audio_failed":
        assert isinstance(m, P.AudioFailedMsg)
        return C.AudioFailed(sender, m.code)
    if t == "kick":
        assert isinstance(m, P.KickMsg)
        return C.Kick(sender, m.slot)
    if t == "update_settings":
        changes = m.model_dump()
        packs = changes.get("packs")
        if isinstance(packs, list) and not all(isinstance(p, str) and p in svc.pack_slugs for p in packs):
            raise GameError("invalid_settings", "Pack desconocido")
        return C.UpdateSettings(sender, changes)
    if t == "start_game":
        return C.Start(sender, tuple(svc.songs), secrets.randbits(62))
    if t == "play_request":
        return C.PlayRequest(sender)
    if t == "place_preview":
        assert isinstance(m, P.IndexMsg)
        now = time.monotonic()
        if now - conn.last_preview_at < PREVIEW_MIN_INTERVAL_S:
            return None  # throttled
        conn.last_preview_at = now
        return C.PlacePreview(sender, m.index)
    if t == "place_confirm":
        assert isinstance(m, P.IndexMsg)
        return C.PlaceConfirm(sender, m.index)
    if t == "guess_submit":
        assert isinstance(m, P.GuessSubmitMsg)
        return C.GuessSubmit(sender, m.title, m.artist)
    if t == "voice_confirm":
        return C.VoiceConfirm(sender)
    if t == "objection":
        assert isinstance(m, P.IndexMsg)
        return C.Objection(sender, m.index)
    if t == "objection_pass":
        return C.ObjectionPass(sender)
    if t == "honor_claim":
        assert isinstance(m, P.HonorClaimMsg)
        return C.HonorClaim(sender, m.title_ok, m.artist_ok)
    if t == "accept_guess":
        return C.AcceptGuess(sender)
    if t == "next_turn":
        return C.NextTurn(sender)
    if t == "rematch":
        return C.Rematch(sender)
    if t == "end_game":
        return C.EndGame(sender)
    raise P.ProtocolError("unknown_type", t)


async def handle_message(svc: Services, rt: RoomRuntime, conn: Conn, raw: Any) -> None:
    try:
        env, model = P.parse_client_message(raw)
    except P.ProtocolError as e:
        ref = raw.get("id", "") if isinstance(raw, dict) else ""
        await _error(rt, conn, str(ref), e.code, e.message)
        return
    except RecursionError:
        await _error(rt, conn, "", "bad_message", "Mensaje mal formado")
        return
    try:
        if env.type == "ping":
            assert isinstance(model, P.PingMsg)
            await rt._send(conn, envelope("pong", {"t": model.t, "server_ts": svc.clock()}))
            return
        if env.type == "hello":
            assert isinstance(model, P.Hello)
            if hash_token(model.session_token) != conn.session_hash:
                raise GameError("bad_token", "Token de sesion distinto al de la conexion")
            await rt._send(conn, envelope("ack", {"ref_id": env.id}))
            await rt.send_state(conn)
            return
        cmd = build_command(svc, rt, conn, env, model)
        if cmd is None:
            await rt._send(conn, envelope("ack", {"ref_id": env.id}))
            return
        await rt.dispatch(cmd, ack=(conn, env.id))
    except GameError as e:
        await _error(rt, conn, env.id, e.code, e.message)
    except Exception:  # noqa: BLE001
        log.exception("ws handler failed for %s", env.type)
        await _error(rt, conn, env.id, "internal", "Error interno")


async def _close(ws: WebSocket, code: int) -> None:
    """Closes, ignoring a peer that already left."""
    with suppress(RuntimeError, WebSocketDisconnect):
        await ws.close(code=code)


async def _read(ws: WebSocket) -> Any:
    """Next client frame as parsed JSON. Raises WebSocketDisconnect, ValueError (bad JSON) or
    OverflowError (frame too large). Binary frames count as bad JSON."""
    msg = await ws.receive()
    if msg["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(msg.get("code", 1000))
    text = msg.get("text")
    if text is None:
        raise ValueError("binary frame")
    if len(text) > MAX_MESSAGE_CHARS:
        raise OverflowError("message too large")
    try:
        return json.loads(text)
    except RecursionError as e:  # deeply nested payload
        raise ValueError("nesting too deep") from e


async def _handshake(svc: Services, ws: WebSocket) -> tuple[str, str] | None:
    """Waits for `hello{session_token}`. Returns (token, hello_id) or None after closing with 4401."""
    try:
        raw = await asyncio.wait_for(_read(ws), HELLO_TIMEOUT_S)
        env, model = P.parse_client_message(raw)
    except (TimeoutError, ValueError, OverflowError, P.ProtocolError, WebSocketDisconnect):
        return None
    if env.type != "hello" or not isinstance(model, P.Hello) or not svc.signer.verify(model.session_token):
        return None
    return model.session_token, env.id


@router.websocket("/ws/rooms/{code}")
async def ws_room(ws: WebSocket, code: str) -> None:
    """The token never travels in the URL: accept, then the first message must be `hello` (<= 5 s)."""
    svc: Services = ws.app.state.services
    cfg = svc.config
    ip = ws_ip(ws)
    await ws.accept()
    if svc.code_limiter.blocked(ip) or svc.ws_per_ip.get(ip, 0) >= cfg.ws_max_conns_per_ip:
        await _close(ws, CLOSE_RATE)
        return
    svc.ws_per_ip[ip] = svc.ws_per_ip.get(ip, 0) + 1
    try:
        await _serve(svc, ws, code, ip)
    finally:
        left = svc.ws_per_ip.get(ip, 1) - 1
        if left > 0:
            svc.ws_per_ip[ip] = left
        else:
            svc.ws_per_ip.pop(ip, None)


async def _serve(svc: Services, ws: WebSocket, code: str, ip: str) -> None:
    cfg = svc.config
    rt = svc.manager.get(code)
    if rt is None:
        svc.code_limiter.allow(ip)  # records a failed attempt
        await _close(ws, CLOSE_NOT_FOUND)
        return
    hello = await _handshake(svc, ws)
    if hello is None:
        svc.code_limiter.allow(ip)
        await _close(ws, CLOSE_BAD_SESSION)
        return
    token, hello_id = hello
    if len(rt.conns) >= cfg.ws_max_conns_per_room:
        await _close(ws, CLOSE_RATE)
        return
    conn = Conn(ws, hash_token(token))
    bucket = TokenBucket(cfg.ws_msgs_per_s, cfg.ws_burst)
    try:
        await rt._send(conn, envelope("ack", {"ref_id": hello_id}))
        await rt.connect(conn)
        while True:
            try:
                raw = await _read(ws)
            except OverflowError:
                await _close(ws, CLOSE_TOO_BIG)
                return
            except ValueError:
                raw = None
            if not bucket.take():
                await _close(ws, CLOSE_RATE)
                return
            if raw is None:
                await _error(rt, conn, "", "bad_message", "JSON no valido")
                continue
            await handle_message(svc, rt, conn, raw)
    except WebSocketDisconnect:
        pass
    finally:
        await rt.disconnect(conn)
