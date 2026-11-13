"""Hint stakes refund their own correct target, independently of placement and bonus."""

import json
from itertools import product

import pytest

from app.game import commands as C
from app.game.engine import reduce
from app.game.models import Phase, Room
from app.game.projection import token_delta, view_json
from tests.helpers import fire, go, make_card, rigged

NOW = 1000.0
CARD = make_card(500, 1990, title="Corazón Partío", artist="Alejandro Sanz")


def prepared(mode="voice", hints=("artist", "title"), placed_ok=True, objector=False):
    room, _ = rigged({0: [1980, 2000], 1: [1985]}, 1990, mode=mode,
                     tokens={0: 2, 1: int(objector)}, mystery=CARD)
    room = go(room, NOW, C.PlayRequest(0))
    for hint in hints:
        room = go(room, NOW, C.UseHint(0, hint))
    return go(room, NOW, C.PlaceConfirm(0, 1 if placed_ok else 0))


def reveal(room, title_ok=False, artist_ok=False):
    if room.settings.mode == "app":
        return go(room, NOW, C.GuessSubmit(0, CARD.title if title_ok else "", CARD.artist if artist_ok else ""))
    room = go(room, NOW, C.VoiceConfirm(0))
    return go(room, NOW, C.HonorClaim(0, title_ok, artist_ok))


@pytest.mark.parametrize("mode", ["voice", "app"])
@pytest.mark.parametrize("hints", [(), ("artist",), ("title",), ("artist", "title")])
@pytest.mark.parametrize("placed_ok,title_ok,artist_ok", list(product([False, True], repeat=3)))
def test_every_answer_placement_and_hint_combination(mode, hints, placed_ok, title_ok, artist_ok):
    room = prepared(mode, hints, placed_ok)
    assert room.teams[0].tokens == 2 - len(hints)  # immediate stake
    room = reveal(room, title_ok, artist_ok)
    bonus = int(placed_ok and title_ok and artist_ok)
    refunds = sum(artist_ok if hint == "artist" else title_ok for hint in hints)
    expected = 2 - len(hints) + refunds + bonus
    assert room.teams[0].tokens == expected
    assert room.turn.token_awarded == bool(bonus)
    result = view_json(room, 1)["turn"]["result"]
    assert result["answersConfirmed"] is True
    assert result["hintRefunds"] == [
        {"kind": hint, "refunded": artist_ok if hint == "artist" else title_ok} for hint in hints
    ]
    assert result["tokenDelta"] == ({"0": expected - 2} if expected != 2 else {})
    _, effects = reduce(room, C.NextTurn(0), NOW + 6)
    resolved = next(e for e in effects if isinstance(e, C.Broadcast) and e.type == "turn_resolved")
    assert resolved.payload["token_delta"] == result["tokenDelta"]


def test_voice_pending_differs_from_confirmed_false_and_reversible_claims():
    room = go(prepared(), NOW, C.VoiceConfirm(0))
    assert not view_json(room, 0)["turn"]["result"]["answersConfirmed"]
    for title_ok, artist_ok, expected in [
        (False, False, 0), (True, True, 3), (True, True, 3),
        (False, True, 1), (True, False, 1), (False, False, 0), (True, True, 3),
    ]:
        room = go(room, NOW, C.HonorClaim(0, title_ok, artist_ok))
        assert room.teams[0].tokens == expected
        assert view_json(room, 0)["turn"]["result"]["answersConfirmed"]
        room = Room.model_validate_json(room.model_dump_json())
        duplicate = go(room, NOW, C.HonorClaim(0, title_ok, artist_ok))
        assert duplicate.teams[0].tokens == expected
        assert duplicate.turn.hint_refunds == room.turn.hint_refunds


@pytest.mark.parametrize("placed_ok", [True, False])
def test_accept_guess_repeated_after_snapshot_does_not_duplicate_bonus_or_refunds(placed_ok):
    room = reveal(prepared("app", placed_ok=placed_ok))
    assert room.teams[0].tokens == 0
    for _ in range(3):
        room = go(Room.model_validate_json(room.model_dump_json()), NOW, C.AcceptGuess(1))
        assert room.teams[0].tokens == 2 + int(placed_ok)
        assert room.turn.hint_refunds == ["artist", "title"]
        assert room.turn.token_awarded == placed_ok


@pytest.mark.parametrize("mode", ["app", "voice"])
def test_timeout_retains_stakes_and_voice_waits_for_explicit_claim(mode):
    room = prepared(mode)
    room, _ = reduce(room, fire(room, "hint"), room.timers["hint"].deadline_ts)
    assert room.phase == Phase.REVEAL
    result = view_json(room, 0)["turn"]["result"]
    assert result["answersConfirmed"] == (mode == "app")
    assert result["hintRefunds"] == [{"kind": k, "refunded": False} for k in ("artist", "title")]
    assert room.teams[0].tokens == 0 and result["tokenDelta"] == {"0": -2}


def test_pre_reveal_projection_never_contains_refunds_or_correctness():
    room = prepared(objector=True)
    phases = [room, go(room, NOW, C.VoiceConfirm(0)), reduce(room, C.Disconnected(0), NOW)[0]]
    for state in phases:
        for viewer in (None, 0, 1):
            public = view_json(state, viewer)
            blob = json.dumps(public)
            assert public["turn"]["result"] is None
            assert "hintRefunds" not in blob and "answersConfirmed" not in blob
            assert "refunded" not in blob and "titleOk" not in blob and "artistOk" not in blob
            assert CARD.title not in blob and CARD.artist not in blob


def test_objection_cost_and_active_net_agree_in_projection_and_effect():
    room = go(prepared(objector=True, placed_ok=False), NOW, C.VoiceConfirm(0), C.Objection(1, 1),
              C.HonorClaim(0, True, False))
    assert token_delta(room) == {"0": -1, "1": -1}
    assert room.teams[0].tokens == 1 and room.teams[1].tokens == 0
    _, effects = reduce(room, C.NextTurn(0), NOW + 6)
    resolved = next(e for e in effects if isinstance(e, C.Broadcast) and e.type == "turn_resolved")
    assert resolved.payload["token_delta"] == token_delta(room)


def test_legacy_snapshot_defaults_and_fresh_turn_and_rematch_clear_ledgers():
    room = go(prepared(), NOW, C.VoiceConfirm(0))
    data = room.model_dump(mode="json")
    data["turn"].pop("hint_refunds")
    data["turn"].pop("honor_claimed")
    room = Room.model_validate(data)
    assert room.turn.hint_refunds == [] and not room.turn.honor_claimed
    assert not view_json(room, 0)["turn"]["result"]["answersConfirmed"]
    room = go(room, NOW, C.HonorClaim(0, True, True))
    room = go(Room.model_validate_json(room.model_dump_json()), NOW, C.HonorClaim(0, True, True))
    assert room.teams[0].tokens == 3
    next_room = go(room, NOW + 6, C.NextTurn(0))
    assert next_room.turn.hint_refunds == [] and next_room.turn.hints_used == []
    assert not next_room.turn.honor_claimed
    over = go(room, NOW, C.EndGame(0), C.Rematch(0))
    assert over.turn is None and all(t.tokens == over.settings.initial_tokens for t in over.teams)


def test_restored_reveal_reconnection_replays_do_not_credit_twice():
    room = reveal(prepared(), True, True)
    room = go(Room.model_validate_json(room.model_dump_json()), NOW + 1, C.Restored())
    assert room.phase == Phase.PAUSED
    assert view_json(room, 1)["turn"]["result"]["hintRefunds"] == [
        {"kind": "artist", "refunded": True}, {"kind": "title", "refunded": True},
    ]
    room = go(room, NOW + 2, C.Connected(0), C.Connected(1),
              C.DeviceReady(0, "device", "sdk", premium_ok=True, unlock=True))
    assert room.phase == Phase.REVEAL
    room = go(room, NOW + 2, C.HonorClaim(0, True, True))
    assert room.teams[0].tokens == 3
    room = go(room, NOW + 2, C.HonorClaim(0, False, False))
    assert room.teams[0].tokens == 0 and room.turn.hint_refunds == []


def test_unresolved_hint_stake_is_not_refunded_on_skip_or_end_game():
    room = prepared(hints=("artist",))
    room.host_slot = 1
    paused = go(room, NOW, C.Disconnected(0))
    grace = next(name for name in paused.timers if name.startswith("grace:"))
    skipped, _ = reduce(paused, fire(paused, grace), paused.timers[grace].deadline_ts)
    assert skipped.teams[0].tokens == 1
    assert skipped.turn.hint_refunds == [] and skipped.turn.hints_used == []
    ended = go(room, NOW, C.EndGame(1))
    assert ended.phase == Phase.GAME_OVER and ended.teams[0].tokens == 1


@pytest.mark.parametrize("mode", ["app", "voice"])
@pytest.mark.parametrize("paused", [False, True])
def test_restoring_legacy_positive_reveal_applies_missing_refunds_once(mode, paused):
    room = reveal(prepared(mode), True, True)
    if paused:
        room = go(room, NOW, C.Disconnected(0))
    legacy = room.model_dump(mode="json")
    legacy["turn"].pop("hint_refunds")
    legacy["turn"].pop("honor_claimed")
    # Old engine had spent both hints and awarded only the ordinary bonus.
    legacy["teams"][0]["tokens"] = 1
    room = Room.model_validate(legacy)
    room = go(room, NOW + 1, C.Restored())
    assert room.teams[0].tokens == 3
    assert room.turn.hint_refunds == ["artist", "title"]
    assert view_json(room, 0)["turn"]["result"]["answersConfirmed"]
    room = go(Room.model_validate_json(room.model_dump_json()), NOW + 2, C.Restored())
    assert room.teams[0].tokens == 3
