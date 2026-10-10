"""RoomManager: in-memory registry of rooms with 4-digit codes."""

from __future__ import annotations

import asyncio
import logging
import secrets

from app.game.models import Room, Settings, new_room
from app.rooms.runtime import RoomRuntime, RuntimeDeps

log = logging.getLogger(__name__)


class RoomsFull(Exception):
    pass


class RoomManager:
    def __init__(self, deps: RuntimeDeps, idle_ttl_s: float = 2 * 3600) -> None:
        self.deps = deps
        self.idle_ttl_s = idle_ttl_s
        self.rooms: dict[str, RoomRuntime] = {}
        self._gc_task: asyncio.Task[None] | None = None
        deps.on_destroy = self.destroy

    def _new_code(self) -> str:
        if len(self.rooms) >= 10_000:
            raise RoomsFull
        while True:
            code = f"{secrets.randbelow(10_000):04d}"
            if code not in self.rooms:
                return code

    def create(
        self,
        host_hash: str,
        name: str | None = None,
        color: str | None = None,
        settings: Settings | None = None,
    ) -> RoomRuntime:
        room = new_room(self._new_code(), host_hash, name, color, settings)
        rt = RoomRuntime(room, self.deps)
        self.rooms[room.code] = rt
        return rt

    def get(self, code: str) -> RoomRuntime | None:
        return self.rooms.get(code)

    async def destroy(self, code: str) -> None:
        rt = self.rooms.pop(code, None)
        if rt is None:
            return
        rt.shutdown()
        for c in list(rt.conns):
            try:
                await c.ws.close(1000)
            except Exception:  # noqa: BLE001
                pass
        await self.deps.persistence.delete(code)

    async def restore_all(self) -> int:
        snaps = await self.deps.persistence.load_all()
        n = 0
        for code, raw in snaps.items():
            try:
                room = Room.model_validate_json(raw)
            except Exception:  # noqa: BLE001
                log.exception("bad snapshot %s", code)
                continue
            rt = RoomRuntime(room, self.deps)
            self.rooms[code] = rt
            await rt.restored()
            n += 1
        return n

    def start_gc(self, interval_s: float = 60.0) -> None:
        async def loop() -> None:
            while True:
                await asyncio.sleep(interval_s)
                now = self.deps.clock()
                for code, rt in list(self.rooms.items()):
                    if not rt.conns and now - rt.last_activity > self.idle_ttl_s:
                        await self.destroy(code)

        self._gc_task = asyncio.create_task(loop())

    async def shutdown(self) -> None:
        if self._gc_task:
            self._gc_task.cancel()
        for rt in self.rooms.values():
            rt.shutdown()
