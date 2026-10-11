"""audio_control and use_hint over the real WebSocket (AUTH_MODE=fake)."""

from __future__ import annotations

import json
import time
from contextlib import ExitStack

from fastapi.testclient import TestClient

from app.rooms.runtime import RoomRuntime
from tests.conftest import Clock
from tests.integration.test_ws import MakeApp, Player, hdr, setup_three, start, tok, wait_for


def has_hints(v: dict) -> bool:  # type: ignore[type-arg]
    t = v.get("turn")
    return bool(t and t.get("hints") and t["hints"]["used"])


def begin(
    client: TestClient, stack: ExitStack, svc, *, tokens: int | None = None
) -> tuple[RoomRuntime, list[Player], int]:
    code, players = setup_three(client, stack, target=10)
    if tokens is not None:
        players[0].ok("update_settings", initial_tokens=tokens)
    rt = start(code, players, svc)
    active = rt.room.turn.team_slot  # type: ignore[union-attr]
    players[active].ok("play_request")
    wait_for(lambda: rt.room.phase == "placing")
    return rt, players, active


def test_audio_control_reaches_only_the_host_and_only_from_the_active_team(
    make_app: MakeApp, clock: Clock
) -> None:
    app, svc = make_app(timer_scale=1.0)
    with TestClient(app) as client, ExitStack() as stack:
        code, players = setup_three(client, stack, target=10)
        rt = start(code, players, svc)
        active = rt.room.turn.team_slot  # type: ignore[union-attr]
        other = next(s for s in (1, 2) if s != active)
        # before the song starts: wrong phase
        r = players[active].result(players[active].send("audio_control", action="pause"))
        assert r["payload"]["code"] == "wrong_phase"
        players[active].ok("play_request")
        wait_for(lambda: rt.room.phase == "placing")
        # other teams (and the host when it is not the active team) are refused
        for s in range(3):
            if s != active:
                r = players[s].result(players[s].send("audio_control", action="pause"))
                assert r["payload"]["code"] == "not_your_turn"
        players[active].ok("audio_control", action="seek", delta_ms=-10000)
        players[active].ok("audio_control", action="pause")
        assert players[active].state(lambda v: v["audio"]["paused"] is True)
        # everyone sees the paused flag, nobody else got the command
        assert players[other].state(lambda v: v["audio"]["paused"] is True)
        players[active].ok("audio_control", action="resume")
        time.sleep(0.6)  # the bucket holds 4 per second and the refused phase check above used one
        players[active].ok("audio_control", action="restart")
        for expected in (
            {"action": "seek", "delta_ms": -10000},
            {"action": "pause"},
            {"action": "resume"},
            {"action": "restart"},
        ):
            m = players[0].recv(
                lambda m, e=expected: m["type"] == "audio_command" and m["payload"]["action"] == e["action"]
            )
            assert m["payload"] == expected
        for s in (1, 2):
            if s != 0:
                assert not [m for m in players[s].seen + players[s].buffer if m["type"] == "audio_command"]
        title = rt.room.turn.card.title  # type: ignore[union-attr]
        for m in players[0].seen:
            if m["type"] == "audio_command":
                assert set(m["payload"]) <= {"action", "delta_ms"}
                assert title not in json.dumps(m)
        assert rt.room.version > 0 and svc.manager.get(code) is rt


def test_audio_control_payload_validation_and_limits(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app(timer_scale=1.0)
    with TestClient(app) as client, ExitStack() as stack:
        rt, players, active = begin(client, stack, svc)
        p = players[active]
        bad = [
            {"action": "seek"},
            {"action": "seek", "delta_ms": 30001},
            {"action": "seek", "delta_ms": -30001},
            {"action": "seek", "delta_ms": 1.5},
            {"action": "seek", "delta_ms": "10000"},
            {"action": "seek", "delta_ms": True},
            {"action": "pause", "delta_ms": 10000},
            {"action": "volume"},
            {"action": "pause", "extra": 1},
            {},
        ]
        for payload in bad:
            r = p.result(p.send("audio_control", **payload))
            assert r["type"] == "error" and r["payload"]["code"] == "bad_payload", payload
        p.ok("audio_control", action="seek", delta_ms=30000)
        # frequency: at most 4 per second per connection (burst 4)
        ids = [p.send("audio_control", action="pause") for _ in range(8)]
        results = [p.result(i) for i in ids]
        limited = [r for r in results if r["type"] == "error"]
        assert limited and all(r["payload"]["code"] == "rate_limited" for r in limited)
        assert len(results) - len(limited) <= 4


def test_audio_control_cap_per_turn(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app(timer_scale=1.0)
    with TestClient(app) as client, ExitStack() as stack:
        rt, players, active = begin(client, stack, svc)
        rt.room.turn.audio_commands = 80  # type: ignore[union-attr]
        p = players[active]
        r = p.result(p.send("audio_control", action="pause"))
        assert r["type"] == "error" and r["payload"]["code"] == "rate_limited"


def test_use_hint_text_only_for_the_active_team(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app(timer_scale=1.0)
    with TestClient(app) as client, ExitStack() as stack:
        rt, players, active = begin(client, stack, svc, tokens=2)
        assert rt.room.teams[active].tokens == 2
        turn = rt.room.turn
        assert turn is not None
        p = players[active]
        p.ok("use_hint", kind="artist")
        mine = p.state(has_hints)
        used = mine["turn"]["hints"]["used"]
        assert used[0]["kind"] == "artist" and "_" in used[0]["masked"]
        assert len(used[0]["masked"]) == len(turn.card.artist)
        assert mine["turn"]["hints"]["deadlineTs"] == clock.t + 60
        assert mine["teams"][active]["tokens"] == 1
        r = p.result(p.send("use_hint", kind="artist"))
        assert r["payload"]["code"] == "hint_already_used"
        for s in range(3):
            if s == active:
                continue
            v = players[s].state(has_hints)
            assert v["turn"]["hints"]["used"] == [{"kind": "artist"}]
            note = players[s].recv(lambda m: m["type"] == "hint_used")
            assert note["payload"] == {"slot": active, "kind": "artist"}
            r = players[s].result(players[s].send("use_hint", kind="title"))
            assert r["payload"]["code"] == "not_your_turn"
        p.ok("use_hint", kind="title")
        r = p.result(p.send("use_hint", kind="title"))
        assert r["payload"]["code"] == "hint_already_used"
        # nothing about the masked text outside the active team's own connection
        for s in range(3):
            if s == active:
                continue
            for m in players[s].seen + players[s].buffer:
                blob = json.dumps(m, ensure_ascii=False)
                assert "masked" not in blob
                assert turn.card.title not in blob and turn.card.artist not in blob


def test_use_hint_errors(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app(timer_scale=1.0)
    with TestClient(app) as client, ExitStack() as stack:
        rt, players, active = begin(client, stack, svc, tokens=0)
        p = players[active]
        assert p.result(p.send("use_hint", kind="artist"))["payload"]["code"] == "no_tokens"
        assert p.result(p.send("use_hint", kind="year"))["payload"]["code"] == "bad_payload"
        assert p.result(p.send("use_hint"))["payload"]["code"] == "bad_payload"
        assert rt.room.teams[active].tokens == 0


def test_hints_disabled_and_settings_over_rest_and_ws(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app(timer_scale=1.0)
    with TestClient(app) as client, ExitStack() as stack:
        t = tok(client)
        r = client.post(
            "/api/rooms",
            json={"settings": {"hints_enabled": False, "initial_tokens": 2}, "name": "A"},
            headers=hdr(t),
        )
        assert r.status_code == 200, r.text
        rt = svc.manager.get(r.json()["code"])
        assert rt is not None and rt.room.settings.hints_enabled is False and rt.room.settings.initial_tokens == 2
        bad = client.post("/api/rooms", json={"settings": {"initial_tokens": 4}, "name": "A"}, headers=hdr(t))
        assert bad.status_code == 422
        # defaults for a plain room
        d = client.post("/api/rooms", json={"name": "B"}, headers=hdr(t))
        rt2 = svc.manager.get(d.json()["code"])
        assert rt2 is not None and rt2.room.settings.hints_enabled and rt2.room.settings.initial_tokens == 1

        code, players = setup_three(client, stack, target=10)
        host = players[0]
        assert host.result(host.send("update_settings", initial_tokens=5))["payload"]["code"] == "invalid_settings"
        assert host.result(host.send("update_settings", hints_enabled="maybe"))["payload"]["code"] == "invalid_settings"
        host.ok("update_settings", hints_enabled=False)
        v = host.state(lambda v: v["settings"]["hintsEnabled"] is False)
        assert v["settings"]["initialTokens"] == 1
        rt3 = start(code, players, svc)
        active = rt3.room.turn.team_slot  # type: ignore[union-attr]
        players[active].ok("play_request")
        wait_for(lambda: rt3.room.phase == "placing")
        r2 = players[active].result(players[active].send("use_hint", kind="title"))
        assert r2["payload"]["code"] == "hints_disabled"
        assert players[active].state(lambda v: v["phase"] == "placing")["turn"]["hints"] is None


def test_hint_timer_fires_through_the_runtime(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app()  # timer_scale 0.01: the 62 s timer fires in ~0.6 s
    with TestClient(app) as client, ExitStack() as stack:
        rt, players, active = begin(client, stack, svc, tokens=1)
        players[active].ok("use_hint", kind="title")
        wait_for(lambda: rt.room.phase in ("guessing", "objection", "reveal"), timeout=10)
        wait_for(lambda: rt.room.phase in ("objection", "reveal"), timeout=10)
        assert "hint" not in rt.room.timers
        assert rt.room.turn is not None and rt.room.turn.placed_index is not None


def test_place_cancel_round_trip(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app(timer_scale=1.0)
    with TestClient(app) as client, ExitStack() as stack:
        rt, players, active = begin(client, stack, svc)
        other = next(s for s in range(3) if s != active)
        p = players[active]
        r = p.result(p.send("place_cancel"))  # still PLACING
        assert r["type"] == "error" and r["payload"]["code"] == "wrong_phase"
        p.ok("place_confirm", index=0)
        assert p.state(lambda v: v["phase"] == "guessing")
        r = players[other].result(players[other].send("place_cancel"))
        assert r["payload"]["code"] == "not_your_turn"
        p.ok("place_cancel")
        v = p.state(lambda v: v["phase"] == "placing" and v["turn"]["placeChangesLeft"] == 2)
        assert v["turn"]["placedIndex"] is None
        assert v["turn"]["placeChangesLeft"] == 2 and v["turn"]["placedAuto"] is False
        seen = json.dumps(v)
        turn = rt.room.turn
        assert turn is not None
        for secret in (turn.card.title, turn.card.artist, turn.card.track_id):
            assert secret not in seen
        assert players[other].state(lambda v: v["phase"] == "placing")
        p.ok("place_confirm", index=1)
        assert p.state(lambda v: v["phase"] == "guessing" and v["turn"]["placedIndex"] == 1)
        for _ in range(2):
            p.ok("place_cancel")
            p.ok("place_confirm", index=1)
        r = p.result(p.send("place_cancel"))
        assert r["payload"]["code"] == "too_many_changes"
