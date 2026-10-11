"""RoomRuntime: one asyncio.Lock per room, executes engine effects, owns timers and connections."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.game.commands import (
    Broadcast,
    CancelTimer,
    Command,
    Connected,
    DestroyRoom,
    Disconnected,
    GameError,
    PersistSnapshot,
    PlayResult,
    Restored,
    SendTo,
    SpotifyPause,
    SpotifyPlay,
    StartTimer,
    TimerFired,
)
from app.game.engine import reduce
from app.game.models import Room
from app.game.projection import view_json
from app.rooms.snapshot import Persistence
from app.spotify.client import AudioBackend

log = logging.getLogger(__name__)


class Socket(Protocol):
    async def send_json(self, data: Any) -> None: ...
    async def close(self, code: int = 1000) -> None: ...


@dataclass(eq=False)
class Conn:
    ws: Socket
    session_hash: str
    last_preview_at: float = 0.0
    audio_bucket: Any = None  # TokenBucket for audio_control (4/s), created lazily by the router


@dataclass
class RuntimeDeps:
    backend: AudioBackend
    persistence: Persistence
    clock: Callable[[], float] = time.time
    timer_scale: float = 1.0  # tests shrink timer delays
    on_destroy: Callable[[str], Coroutine[Any, Any, None]] | None = None


def envelope(type_: str, payload: dict[str, Any], id_: str | None = None) -> dict[str, Any]:
    import uuid

    return {"type": type_, "id": id_ or str(uuid.uuid4()), "payload": payload}


@dataclass
class RoomRuntime:
    room: Room
    deps: RuntimeDeps
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    conns: list[Conn] = field(default_factory=list)
    tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    last_activity: float = 0.0

    def __post_init__(self) -> None:
        self.last_activity = self.deps.clock()

    # ------------------------------------------------------------ connections
    def slot_of(self, conn: Conn) -> int | None:
        return self.room.slot_of(conn.session_hash)

    def _has_other_conn(self, conn: Conn) -> bool:
        return any(c is not conn and c.session_hash == conn.session_hash for c in self.conns)

    async def connect(self, conn: Conn) -> None:
        self.conns.append(conn)
        slot = self.slot_of(conn)
        if slot is not None:
            await self.dispatch(Connected(slot))
        await self.send_state(conn)

    async def disconnect(self, conn: Conn) -> None:
        if conn in self.conns:
            self.conns.remove(conn)
        slot = self.slot_of(conn)
        if slot is not None and not self._has_other_conn(conn):
            try:
                await self.dispatch(Disconnected(slot))
            except GameError:
                pass

    async def send_state(self, conn: Conn) -> None:
        msg = envelope(
            "state",
            {"version": self.room.version, "view": view_json(self.room, self.slot_of(conn))},
        )
        await self._send(conn, msg)

    async def _send(self, conn: Conn, msg: dict[str, Any]) -> None:
        try:
            await conn.ws.send_json(msg)
        except Exception:  # noqa: BLE001 - dead socket
            if conn in self.conns:
                self.conns.remove(conn)

    # ------------------------------------------------------------ dispatch
    async def dispatch(
        self,
        cmd: Command,
        *,
        ack: tuple[Conn, str] | None = None,
    ) -> Room:
        """Serialised by the room lock. Raises GameError if the engine rejects the command."""
        async with self.lock:
            now = self.deps.clock()
            old = self.room
            new, fx = reduce(old, cmd, now)  # GameError propagates, state untouched
            self.room = new
            self.last_activity = now
            if ack is not None:
                await self._send(ack[0], envelope("ack", {"ref_id": ack[1]}))
            old_slots = {id(c): old.slot_of(c.session_hash) for c in self.conns}
            if new.version != old.version:
                for c in list(self.conns):
                    await self.send_state(c)
            await self._run_effects(fx, old_slots)
        return new

    async def _run_effects(self, fx: list[Any], old_slots: dict[int, int | None]) -> None:
        for e in fx:
            if isinstance(e, Broadcast):
                for c in list(self.conns):
                    await self._send(c, envelope(e.type, e.payload))
            elif isinstance(e, SendTo):
                kicked = e.type == "kicked"
                for c in list(self.conns):
                    slot = old_slots.get(id(c)) if kicked else self.slot_of(c)
                    if slot == e.slot:
                        await self._send(c, envelope(e.type, e.payload))
                        if kicked:
                            self.conns.remove(c)
                            try:
                                await c.ws.close(4403)
                            except Exception:  # noqa: BLE001
                                pass
            elif isinstance(e, StartTimer):
                self._start_task(e)
            elif isinstance(e, CancelTimer):
                self._cancel_task(e.name)
            elif isinstance(e, SpotifyPlay):
                asyncio.create_task(self._do_play(e))
            elif isinstance(e, SpotifyPause):
                asyncio.create_task(self._do_pause(e))
            elif isinstance(e, PersistSnapshot):
                try:
                    await self.deps.persistence.save(self.room.code, self.room.model_dump_json())
                except Exception:  # noqa: BLE001
                    log.exception("snapshot save failed for room %s", self.room.code)
            elif isinstance(e, DestroyRoom) and self.deps.on_destroy is not None:
                asyncio.create_task(self.deps.on_destroy(self.room.code))

    # ------------------------------------------------------------ timers
    def _cancel_task(self, name: str) -> None:
        t = self.tasks.pop(name, None)
        if t is not None and t is not asyncio.current_task():
            t.cancel()

    def _start_task(self, e: StartTimer) -> None:
        self._cancel_task(e.name)
        self.tasks[e.name] = asyncio.create_task(self._timer(e.name, e.timer_id, e.delay_s))

    async def _timer(self, name: str, timer_id: str, delay: float) -> None:
        await asyncio.sleep(max(0.0, delay * self.deps.timer_scale))
        try:
            await self.dispatch(TimerFired(name, timer_id))
        except GameError:
            pass
        except Exception:  # noqa: BLE001
            log.exception("timer %s failed", name)

    def schedule_from_state(self) -> None:
        """After a restore: re-arm every running timer from its deadline_ts."""
        now = self.deps.clock()
        for name, ref in self.room.timers.items():
            self._start_task(StartTimer(name, ref.timer_id, max(0.0, ref.deadline_ts - now)))

    async def restored(self) -> None:
        self.schedule_from_state()
        await self.dispatch(Restored())

    def shutdown(self) -> None:
        for name in list(self.tasks):
            t = self.tasks.pop(name)
            if t is not asyncio.current_task():
                t.cancel()

    # ------------------------------------------------------------ audio
    async def _do_play(self, e: SpotifyPlay) -> None:
        try:
            out = await self.deps.backend.play(
                e.session_id, e.device_id, e.track_id, e.position_ms, e.instance_id
            )
        except Exception:  # noqa: BLE001
            log.exception("play failed")
            out = None
        ok = bool(out and out.ok)
        code = out.code if out else "unknown"
        try:
            await self.dispatch(PlayResult(e.instance_id, ok, code, out.retry_after_s if out else None))
        except GameError:
            pass

    async def _do_pause(self, e: SpotifyPause) -> None:
        try:
            await self.deps.backend.pause(e.session_id, e.device_id)
        except Exception:  # noqa: BLE001
            log.exception("pause failed")
