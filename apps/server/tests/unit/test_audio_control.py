"""audio_control: who, when, how often, and what reaches the host."""

from __future__ import annotations

import json

import pytest

from app.game import commands as C
from app.game.commands import GameError
from app.game.engine import MAX_AUDIO_COMMANDS_PER_TURN, reduce
from app.game.models import Phase, Room
from app.game.projection import view_json
from tests.helpers import go, rigged

NOW = 1000.0


def err(room: Room, cmd: C.Command) -> str:
    with pytest.raises(GameError) as e:
        reduce(room, cmd, NOW)
    return e.value.code


def playing() -> Room:
    room, _ = rigged({0: [1950, 1970], 1: [1985], 2: [2005]}, 1997, tokens={1: 1})
    return go(room, NOW, C.PlayRequest(0))


def test_each_action_goes_only_to_the_host_without_song_data() -> None:
    room = playing()
    for cmd, payload in (
        (C.AudioControl(0, "seek", -10000), {"action": "seek", "delta_ms": -10000}),
        (C.AudioControl(0, "seek", 10000), {"action": "seek", "delta_ms": 10000}),
        (C.AudioControl(0, "pause"), {"action": "pause"}),
        (C.AudioControl(0, "resume"), {"action": "resume"}),
        (C.AudioControl(0, "restart"), {"action": "restart"}),
    ):
        room, fx = reduce(room, cmd, NOW)
        sends = [e for e in fx if isinstance(e, (C.SendTo, C.Broadcast))]
        assert len(sends) == 1
        e = sends[0]
        assert isinstance(e, C.SendTo) and e.slot == room.host_slot and e.type == "audio_command"
        assert e.payload == payload
        assert not [x for x in fx if isinstance(x, C.SpotifyPlay | C.SpotifyPause)]  # no Web API call


def test_paused_flag_follows_pause_resume_restart() -> None:
    room = playing()
    room = go(room, NOW, C.AudioControl(0, "pause"))
    for v in (None, 0, 1):
        assert view_json(room, v)["audio"]["paused"] is True
    room = go(room, NOW, C.AudioControl(0, "resume"))
    assert view_json(room, 1)["audio"]["paused"] is False
    room = go(room, NOW, C.AudioControl(0, "pause"), C.AudioControl(0, "restart"))
    assert view_json(room, 0)["audio"]["paused"] is False
    room = go(room, NOW, C.AudioControl(0, "pause"), C.AudioReport(0, True))
    assert view_json(room, 0)["audio"]["paused"] is False and view_json(room, 0)["audio"]["playing"] is True


def test_only_the_active_team() -> None:
    room = playing()
    assert err(room, C.AudioControl(1, "pause")) == "not_your_turn"
    assert err(room, C.AudioControl(None, "pause")) == "not_your_turn"


def test_phases() -> None:
    ready, _ = rigged({0: [1950, 1970], 1: [1985], 2: [2005]}, 1997, tokens={1: 1})
    assert err(ready, C.AudioControl(0, "pause")) == "wrong_phase"  # TURN_READY
    room = go(ready, NOW, C.PlayRequest(0))
    g = go(room, NOW, C.PlaceConfirm(0, 2))
    assert g.phase == Phase.GUESSING
    go(g, NOW, C.AudioControl(0, "seek", 10000))
    o = go(g, NOW, C.VoiceConfirm(0))
    assert o.phase == Phase.OBJECTION
    go(o, NOW, C.AudioControl(0, "restart"))
    r = go(o, NOW, C.ObjectionPass(1))
    assert r.phase == Phase.REVEAL
    assert err(r, C.AudioControl(0, "pause")) == "wrong_phase"
    lobby = go(ready, NOW, C.EndGame(0))
    assert err(lobby, C.AudioControl(0, "pause")) == "wrong_phase"
    paused, _ = reduce(room, C.Disconnected(0), NOW)
    assert err(paused, C.AudioControl(0, "pause")) == "paused"


def test_requires_audio_started() -> None:
    room, _ = rigged({0: [1950, 1970], 1: [1985], 2: [2005]}, 1997)
    room.phase = Phase.PLACING  # placing without play (e.g. a restored odd state)
    assert room.turn is not None and not room.turn.started_playing
    assert err(room, C.AudioControl(0, "pause")) == "wrong_phase"


def test_payload_validation_in_engine() -> None:
    room = playing()
    assert err(room, C.AudioControl(0, "seek")) == "bad_payload"
    assert err(room, C.AudioControl(0, "seek", 30001)) == "bad_payload"
    assert err(room, C.AudioControl(0, "seek", -30001)) == "bad_payload"
    assert err(room, C.AudioControl(0, "pause", 5)) == "bad_payload"
    assert err(room, C.AudioControl(0, "volume")) == "bad_payload"
    go(room, NOW, C.AudioControl(0, "seek", 30000), C.AudioControl(0, "seek", -30000))


def test_cap_per_turn_then_reset_next_turn() -> None:
    room = playing()
    for _ in range(MAX_AUDIO_COMMANDS_PER_TURN):
        room = go(room, NOW, C.AudioControl(0, "pause"))
    assert err(room, C.AudioControl(0, "resume")) == "rate_limited"
    assert room.turn is not None and room.turn.audio_commands == MAX_AUDIO_COMMANDS_PER_TURN


def test_view_never_carries_song_data_after_control() -> None:
    room = go(playing(), NOW, C.AudioControl(0, "seek", 10000))
    blob = json.dumps(view_json(room, 1))
    assert room.turn is not None
    assert room.turn.card.title not in blob and room.turn.card.track_id not in blob
