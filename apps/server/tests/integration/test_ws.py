"""WebSocket integration with the Starlette TestClient (AUTH_MODE=fake)."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import ExitStack
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from app.rooms.runtime import RoomRuntime
from app.services import Services
from tests.conftest import Clock

MakeApp = Callable[..., tuple[FastAPI, Services]]


class Player:
    def __init__(self, ws: WebSocketTestSession, token: str) -> None:
        self.ws = ws
        self.token = token
        self.buffer: list[dict[str, Any]] = []
        self.seen: list[dict[str, Any]] = []  # every message ever received
        self._n = 0

    def send(self, type_: str, **payload: Any) -> str:
        self._n += 1
        mid = f"{self.token[:4]}-{self._n}"
        self.ws.send_json({"type": type_, "id": mid, "payload": payload})
        return mid

    def recv(self, pred: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        for i, m in enumerate(self.buffer):
            if pred(m):
                return self.buffer.pop(i)
        while True:
            m = self.ws.receive_json()
            self.seen.append(m)
            if pred(m):
                return m
            self.buffer.append(m)

    def result(self, mid: str) -> dict[str, Any]:
        return self.recv(lambda m: m["type"] in ("ack", "error") and m["payload"]["ref_id"] == mid)

    def ok(self, type_: str, **payload: Any) -> None:
        r = self.result(self.send(type_, **payload))
        assert r["type"] == "ack", r

    def state(self, pred: Callable[[dict[str, Any]], bool] = lambda v: True) -> dict[str, Any]:
        return self.recv(lambda m: m["type"] == "state" and pred(m["payload"]["view"]))["payload"]["view"]


def wait_for(cond: Callable[[], bool], timeout: float = 5.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.005)
    raise AssertionError("timeout waiting for condition")


def open_ws(client: TestClient, stack: ExitStack, code: str, token: str) -> Player:
    """Connects without a token in the URL and authenticates with the first-message `hello`."""
    ws = stack.enter_context(client.websocket_connect(f"/ws/rooms/{code}"))
    p = Player(ws, token)
    p.send("hello", session_token=token)
    return p


def tok(client: TestClient) -> str:
    return str(client.post("/api/session").json()["session_token"])


def hdr(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def setup_three(
    client: TestClient, stack: ExitStack, target: int = 3, mode: str = "voice"
) -> tuple[str, list[Player]]:
    tokens = [tok(client) for _ in range(3)]
    r = client.post(
        "/api/rooms",
        json={"settings": {"team_count": 3, "target_cards": target, "mode": mode}, "name": "Anfitrion"},
        headers=hdr(tokens[0]),
    )
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    players = [open_ws(client, stack, code, t) for t in tokens]
    host = players[0]
    first = host.state()
    assert first["you"] == {"slot": 0, "isHost": True} and first["phase"] == "lobby"
    for i in (1, 2):
        v = players[i].state()
        assert v["you"]["slot"] is None
        players[i].ok("claim_slot", slot=i, name=f"Equipo {i}", color="#123456")
        assert players[i].state(lambda v, i=i: v["you"]["slot"] == i)["teams"][i]["name"] == f"Equipo {i}"
    host.ok("device_ready", device_id="fake-device", provider="sdk")
    return code, players


def start(code: str, players: list[Player], svc: Services) -> RoomRuntime:
    players[0].ok("start_game")
    rt = svc.manager.get(code)
    assert rt is not None
    wait_for(lambda: rt.room.phase == "turn_ready")
    return rt


def correct_index(rt: RoomRuntime) -> int:
    t = rt.room.turn
    assert t is not None
    return sum(1 for c in rt.room.teams[t.team_slot].timeline if c.year <= t.card.year)


def play_to_guessing(rt: RoomRuntime, players: list[Player], clock: Clock, wrong: bool = False) -> int:
    t = rt.room.turn
    assert t is not None
    active = t.team_slot
    players[active].ok("play_request")
    players[0].recv(lambda m: m["type"] == "audio_command" and m["payload"]["action"] == "prepare")
    idx = correct_index(rt)
    if wrong:
        n = len(rt.room.teams[active].timeline)
        idx = next(i for i in range(n + 1) if i != correct_index(rt) and not _also_ok(rt, i))
    players[active].ok("place_confirm", index=idx)
    return active


def _also_ok(rt: RoomRuntime, i: int) -> bool:
    from app.game.rules import line_slot_is_correct

    t = rt.room.turn
    assert t is not None
    return line_slot_is_correct(rt.room.teams[t.team_slot].timeline, i, t.card.year)


def test_full_flow_create_join_reconnect_and_short_game(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app()
    with TestClient(app) as client, ExitStack() as stack:
        code, players = setup_three(client, stack)
        info = client.get(f"/api/rooms/{code}", headers=hdr(players[1].token)).json()
        assert info["status"] == "full" and info["your_slot"] == 1 and info["mode"] == "voice"

        # reconnect with the same token: same slot, back to connected
        old = players[1]
        old.ws.close()
        rt = svc.manager.get(code)
        assert rt is not None
        wait_for(lambda: not rt.room.teams[1].connected)
        players[1] = open_ws(client, stack, code, old.token)
        v = players[1].state()
        assert (
            v["you"]["slot"] == 1
            and v["teams"][1]["connected"] is True
            and v["teams"][1]["name"] == "Equipo 1"
        )
        r = players[1].result(players[1].send("hello", session_token=old.token, last_version=0))
        assert r["type"] == "ack"
        r = players[1].result(players[1].send("hello", session_token="x" * 40))
        assert r["type"] == "error" and r["payload"]["code"] == "bad_token"

        rt = start(code, players, svc)
        game_turns = 0
        while rt.room.phase not in ("game_over",):
            game_turns += 1
            assert game_turns < 40
            active = play_to_guessing(rt, players, clock)
            players[active].ok("voice_confirm")
            if rt.room.phase == "objection":
                for s in range(3):
                    if s != active and rt.room.teams[s].tokens > 0:
                        players[s].ok("objection_pass")
            wait_for(lambda: rt.room.phase == "reveal")
            players[active].ok("honor_claim", title_ok=True, artist_ok=True)
            clock.advance(6)
            players[active].ok("next_turn")
            wait_for(lambda: rt.room.phase in ("turn_ready", "game_over"))
        assert rt.room.game_over_reason in ("target", "deck_exhausted")
        for p in players:
            go = p.recv(lambda m: m["type"] == "game_over")
            assert go["payload"]["winners"]
            # anti-cheat on the wire: pre-reveal states never carry the card data
            for m in p.seen:
                if m["type"] != "state":
                    continue
                view = m["payload"]["view"]
                if view["turn"] and view["phase"] in ("turn_ready", "placing", "guessing", "objection"):
                    assert view["turn"]["card"].keys() == {"instanceId", "hidden"}
            hidden_audio = [m for m in p.seen if m["type"] == "audio_command"]
            assert (len(hidden_audio) > 0) == (p is players[0])  # audio_command only to the host
        players[0].ok("rematch")
        assert players[0].state(lambda v: v["phase"] == "lobby")["teams"][1]["timeline"] == []


def test_concurrent_objections_one_wins_other_gets_objection_closed(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app()
    with TestClient(app) as client, ExitStack() as stack:
        code, players = setup_three(client, stack, target=10)
        rt = start(code, players, svc)
        active = rt.room.turn.team_slot  # type: ignore[union-attr]
        others = [s for s in range(3) if s != active]
        for s in others:
            rt.room.teams[s].tokens = 1
        play_to_guessing(rt, players, clock, wrong=True)
        players[active].ok("voice_confirm")
        wait_for(lambda: rt.room.phase == "objection")
        placed = rt.room.turn.placed_index  # type: ignore[union-attr]
        n = len(rt.room.teams[active].timeline)
        idx = next(i for i in range(n + 1) if i != placed)
        a, b = players[others[0]], players[others[1]]
        ida = a.send("objection", index=idx)
        idb = b.send("objection", index=idx)
        ra, rb = a.result(ida), b.result(idb)
        kinds = sorted([ra["type"], rb["type"]])
        assert kinds == ["ack", "error"]
        loser = ra if ra["type"] == "error" else rb
        assert loser["payload"]["code"] == "objection_closed"
        winner_slot = others[0] if ra["type"] == "ack" else others[1]
        loser_slot = others[1] if winner_slot == others[0] else others[0]
        assert rt.room.phase == "reveal"
        assert rt.room.turn.objection[0] == winner_slot  # type: ignore[index,union-attr]
        assert rt.room.teams[winner_slot].tokens == 0 and rt.room.teams[loser_slot].tokens == 1


def test_permissions_and_errors_over_ws(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app()
    with TestClient(app) as client, ExitStack() as stack:
        code, players = setup_three(client, stack)
        host, p1, p2 = players
        assert p1.result(p1.send("start_game"))["payload"]["code"] == "not_host"
        assert p1.result(p1.send("kick", slot=2))["payload"]["code"] == "not_host"
        assert host.result(host.send("play_request"))["payload"]["code"] == "wrong_phase"
        assert host.result(host.send("nope"))["payload"]["code"] == "unknown_type"
        assert host.result(host.send("place_confirm", index="x"))["payload"]["code"] == "bad_payload"
        assert p1.result(p1.send("update_settings", mode="app"))["payload"]["code"] == "not_host"
        host.ok("update_settings", mode="app")
        assert (
            host.result(host.send("update_settings", start_position_ms=0))["payload"]["code"]
            == "invalid_settings"
        )
        host.ok("update_settings", mode="voice")
        r = p2.result(p2.send("claim_slot", slot=1, name="Intruso"))
        assert r["payload"]["code"] == "slot_taken"
        host.send("ping", t=5)
        pong = host.recv(lambda m: m["type"] == "pong")
        assert pong["payload"]["t"] == 5 and "server_ts" in pong["payload"]
        # kick p2 -> kicked message + slot freed + socket closed
        host.ok("kick", slot=2)
        k = p2.recv(lambda m: m["type"] == "kicked")
        assert k["payload"]["reason"] == "host"
        assert not svc.manager.get(code).room.teams[2].claimed  # type: ignore[union-attr]
        # game started: late claim rejected
        p2b = open_ws(client, stack, code, p2.token)
        p2b.state()
        p2b.ok("claim_slot", slot=2, name="Vuelvo")
        start(code, players[:2] + [p2b], svc)
        late = open_ws(client, stack, code, tok(client))
        late.state()
        assert late.result(late.send("claim_slot", slot=1, name="Tarde"))["payload"]["code"] in (
            "game_started",
        )


def test_host_offline_pauses_for_all_and_resumes(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app()
    with TestClient(app) as client, ExitStack() as stack:
        code, players = setup_three(client, stack)
        rt = start(code, players, svc)
        players[0].ws.close()
        wait_for(lambda: rt.room.phase == "paused")
        v = players[1].state(lambda v: v["phase"] == "paused")
        assert v["pause"]["reason"] == "audio_host_offline"
        host = open_ws(client, stack, code, players[0].token)
        host.state()
        assert rt.room.phase == "paused"
        host.ok("device_ready", device_id="fake2", provider="sdk")  # fake mode unlocks too
        wait_for(lambda: rt.room.phase == "turn_ready")


def test_end_game_over_ws_host_only_and_no_leak(make_app: MakeApp, clock: Clock) -> None:
    app, svc = make_app()
    with TestClient(app) as client, ExitStack() as stack:
        code, players = setup_three(client, stack)
        # En el lobby no se puede terminar: wrong_phase, tambien para el anfitrion.
        assert players[0].result(players[0].send("end_game"))["payload"]["code"] == "wrong_phase"
        rt = start(code, players, svc)
        active = rt.room.turn.team_slot  # type: ignore[union-attr]
        secret = rt.room.turn.card  # type: ignore[union-attr]
        players[active].ok("play_request")
        # Un equipo que no es anfitrion no puede terminar.
        r = players[1].result(players[1].send("end_game"))
        assert r["type"] == "error" and r["payload"]["code"] == "not_host"
        assert rt.room.phase != "game_over"
        # El anfitrion termina a mitad de turno.
        players[0].ok("end_game")
        v = players[1].state(lambda v: v["phase"] == "game_over")
        assert v["phase"] == "game_over"
        go = players[2].recv(lambda m: m["type"] == "game_over")["payload"]
        assert go["reason"] == "host_ended"
        # La carta en curso no se revela a nadie.
        blob = str(players[1].seen) + str(players[2].seen)
        for secret_text in (secret.title, secret.artist, secret.track_id):
            assert secret_text not in blob
        # Ya terminada: no se puede volver a terminar.
        assert players[0].result(players[0].send("end_game"))["payload"]["code"] == "wrong_phase"
        # La revancha sigue funcionando.
        players[0].ok("rematch")
        wait_for(lambda: rt.room.phase == "lobby")
