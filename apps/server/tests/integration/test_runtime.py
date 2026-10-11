"""RoomRuntime/RoomManager without HTTP: locking, timers, effects, snapshots."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.game import commands as C
from app.game.commands import GameError
from app.game.models import Phase
from app.rooms.manager import RoomManager
from app.rooms.runtime import Conn, RoomRuntime, RuntimeDeps
from app.rooms.snapshot import MemoryPersistence
from app.spotify.client import PlayOutcome
from tests.conftest import Clock
from tests.helpers import make_songs, rigged


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.closed: int | None = None

    async def send_json(self, data: Any) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed = code

    def types(self) -> list[str]:
        return [m["type"] for m in self.sent]


class ScriptedBackend:
    def __init__(self, outcomes: list[PlayOutcome] | None = None) -> None:
        self.outcomes = outcomes or []
        self.plays: list[tuple[Any, ...]] = []
        self.pauses = 0

    async def play(self, session_id, device_id, track_id, position_ms, instance_id):  # type: ignore[no-untyped-def]
        self.plays.append((session_id, device_id, track_id, position_ms, instance_id))
        return self.outcomes.pop(0) if self.outcomes else PlayOutcome(True)

    async def pause(self, session_id, device_id):  # type: ignore[no-untyped-def]
        self.pauses += 1


async def settle(n: int = 5) -> None:
    for _ in range(n):
        await asyncio.sleep(0.005)


def make_rt(backend: ScriptedBackend | None = None, scale: float = 0.01, clock: Clock | None = None):  # type: ignore[no-untyped-def]
    clock = clock or Clock()
    persistence = MemoryPersistence()
    deps = RuntimeDeps(backend or ScriptedBackend(), persistence, clock=clock, timer_scale=scale)
    return deps, clock, persistence


async def test_countdown_timer_fires_and_state_is_broadcast_projected() -> None:
    deps, clock, persistence = make_rt()
    mgr = RoomManager(deps)
    rt = mgr.create("hash0", "Host")
    ws0, ws1 = FakeWS(), FakeWS()
    c0, c1 = Conn(ws0, "hash0"), Conn(ws1, "hash1")
    await rt.connect(c0)
    await rt.connect(c1)
    await rt.dispatch(C.ClaimSlot("hash1", 1, "Dos"))
    await rt.dispatch(C.DeviceReady(0, "dev", "sdk", premium_ok=True, unlock=True))
    await rt.dispatch(C.Start(0, make_songs(), 1))
    assert rt.room.phase == Phase.COUNTDOWN and "countdown" in ws1.types()
    await asyncio.sleep(0.1)  # 3 s * 0.01
    assert rt.room.phase == Phase.TURN_READY
    states = [m for m in ws1.sent if m["type"] == "state"]
    assert states[-1]["payload"]["version"] == rt.room.version
    assert states[-1]["payload"]["view"]["you"]["slot"] == 1
    assert rt.room.code in persistence.data
    mgr.rooms[rt.room.code].shutdown()


async def test_concurrent_dispatch_is_serialised_objection_race() -> None:
    deps, clock, _ = make_rt()
    room, now = rigged({0: [1980, 2000], 1: [1985], 2: [2005]}, 1990, tokens={1: 1, 2: 1})
    clock.t = now
    rt = RoomRuntime(room, deps)
    await rt.dispatch(C.PlayRequest(0))
    await rt.dispatch(C.PlaceConfirm(0, 1))
    await rt.dispatch(C.VoiceConfirm(0))
    assert rt.room.phase == Phase.OBJECTION
    res = await asyncio.gather(
        rt.dispatch(C.Objection(1, 0)), rt.dispatch(C.Objection(2, 2)), return_exceptions=True
    )
    errors = [r for r in res if isinstance(r, GameError)]
    assert len(errors) == 1 and errors[0].code == "objection_closed"
    assert sorted(t.tokens for t in rt.room.teams) == [0, 0, 1]  # the winner spent theirs, the loser kept it
    assert rt.room.phase == Phase.REVEAL
    rt.shutdown()


async def test_timer_ids_expire_when_replaced() -> None:
    deps, clock, _ = make_rt(scale=0.01)
    room, now = rigged({0: [1980, 2000], 1: [1985], 2: [2005]}, 1990, tokens={1: 1})
    clock.t = now
    rt = RoomRuntime(room, deps)
    await rt.dispatch(C.PlayRequest(0))
    await rt.dispatch(C.PlaceConfirm(0, 1))
    await rt.dispatch(C.VoiceConfirm(0))  # objection timer: 15 s * 0.01 = 150 ms
    await rt.dispatch(C.Objection(1, 0))  # cancels it, enters REVEAL
    await asyncio.sleep(0.25)
    assert rt.room.phase == Phase.REVEAL  # the old timer did not fire into REVEAL
    rt.shutdown()


async def test_objection_timer_fires_with_injected_clock() -> None:
    deps, clock, _ = make_rt(scale=0.01)
    room, now = rigged({0: [1980, 2000], 1: [1985], 2: [2005]}, 1990, tokens={1: 1})
    clock.t = now
    rt = RoomRuntime(room, deps)
    await rt.dispatch(C.PlayRequest(0))
    await rt.dispatch(C.PlaceConfirm(0, 1))
    await rt.dispatch(C.VoiceConfirm(0))
    deadline = rt.room.timers["objection"].deadline_ts
    assert deadline == now + 15
    clock.t = deadline
    await asyncio.sleep(0.3)
    assert rt.room.phase == Phase.REVEAL and rt.room.turn.objection is None  # type: ignore[union-attr]
    rt.shutdown()


async def test_play_effect_runs_backend_and_failures_fall_back_to_preview() -> None:
    backend = ScriptedBackend([PlayOutcome(False, "device_gone"), PlayOutcome(False, "device_gone")])
    deps, clock, _ = make_rt(backend)
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    clock.t = now
    rt = RoomRuntime(room, deps)
    ws = FakeWS()
    await rt.connect(Conn(ws, room.teams[0].session_token_hash))  # type: ignore[arg-type]
    await rt.dispatch(C.PlayRequest(0))
    await settle(20)
    assert len(backend.plays) == 2  # one automatic retry
    assert backend.plays[0][1:4] == ("dev", rt.room.turn.card.track_id, 15_000)  # type: ignore[union-attr]
    assert rt.room.turn.audio_source == "preview"  # type: ignore[union-attr]
    actions = [m["payload"]["action"] for m in ws.sent if m["type"] == "audio_command"]
    assert actions == ["prepare", "play_preview"]
    assert [m["payload"]["code"] for m in ws.sent if m["type"] == "audio_error"] == [
        "device_gone",
        "device_gone",
    ]
    rt.shutdown()


async def test_pause_effect_on_leaving_reveal() -> None:
    backend = ScriptedBackend()
    deps, clock, _ = make_rt(backend)
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)
    clock.t = now
    rt = RoomRuntime(room, deps)
    for cmd in (C.PlayRequest(0), C.AudioReport(0, True), C.PlaceConfirm(0, 1), C.VoiceConfirm(0)):
        await rt.dispatch(cmd)
    clock.advance(6)
    await rt.dispatch(C.NextTurn(0))
    await settle()
    assert backend.pauses == 1
    rt.shutdown()


async def test_kicked_connection_receives_message_then_closed() -> None:
    deps, clock, _ = make_rt()
    rt = RoomManager(deps).create("hash0", "Host")
    await rt.dispatch(C.ClaimSlot("hash1", 1, "Dos"))
    ws = FakeWS()
    await rt.connect(Conn(ws, "hash1"))
    await rt.dispatch(C.Kick(0, 1))
    assert "kicked" in ws.types() and ws.closed == 4403


async def test_error_does_not_change_state_or_version() -> None:
    deps, clock, _ = make_rt()
    rt = RoomManager(deps).create("hash0", "Host")
    v = rt.room.version
    with pytest.raises(GameError):
        await rt.dispatch(C.Start(0, make_songs(), 1))
    assert rt.room.version == v and rt.room.phase == Phase.LOBBY


async def test_snapshot_restore_pauses_and_resumes_after_reconnect() -> None:
    deps, clock, persistence = make_rt()
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)
    clock.t = now
    rt = RoomRuntime(room, deps)
    await rt.dispatch(C.PlayRequest(0))
    await rt.dispatch(C.PlaceConfirm(0, 1))
    assert persistence.data[room.code]
    rt.shutdown()
    # "restart": a new manager restores from the snapshot
    mgr2 = RoomManager(deps)
    assert await mgr2.restore_all() == 1
    rt2 = mgr2.get(room.code)
    assert rt2 is not None
    assert rt2.room.phase == Phase.PAUSED and rt2.room.paused_from == Phase.GUESSING
    assert rt2.room.pause.reason == "audio_host_offline"  # type: ignore[union-attr]
    h = room.teams[0].session_token_hash
    await rt2.connect(Conn(FakeWS(), h))  # type: ignore[arg-type]
    await rt2.dispatch(C.DeviceReady(0, "dev", "sdk", premium_ok=True, unlock=True))
    assert rt2.room.phase == Phase.GUESSING
    rt2.shutdown()


async def test_restore_reschedules_timers_from_deadline() -> None:
    deps, clock, persistence = make_rt(scale=0.01)
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    clock.t = now
    rt = RoomRuntime(room, deps)
    await rt.dispatch(C.Disconnected(0))
    assert rt.room.phase == Phase.PAUSED
    rt.shutdown()
    mgr2 = RoomManager(deps)
    await mgr2.restore_all()
    assert mgr2.get(room.code).room.phase == Phase.PAUSED  # type: ignore[union-attr]


async def test_manager_codes_and_gc() -> None:
    deps, clock, persistence = make_rt()
    mgr = RoomManager(deps, idle_ttl_s=100)
    codes = {mgr.create(f"h{i}").room.code for i in range(300)}
    assert len(codes) == 300 and all(len(c) == 4 and c.isdigit() for c in codes)
    code = next(iter(codes))
    await mgr.destroy(code)
    assert mgr.get(code) is None
    assert code not in persistence.data
