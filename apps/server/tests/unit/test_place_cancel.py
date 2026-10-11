"""place_cancel: go back from GUESSING to PLACING before answering."""

from __future__ import annotations

import json

import pytest

from app.game import commands as C
from app.game.commands import GameError
from app.game.engine import reduce
from app.game.models import Phase, Room
from app.game.projection import view_json
from app.game.rules import MAX_PLACE_CHANGES_PER_TURN
from tests.helpers import fire, go, rigged

NOW = 1000.0


def err(room: Room, cmd: C.Command, now: float = NOW) -> str:
    with pytest.raises(GameError) as e:
        reduce(room, cmd, now)
    return e.value.code


def room_for(mode: str = "voice") -> Room:
    room, _ = rigged({0: [1950, 1970, 1990], 1: [1985], 2: [2005]}, 1997, mode=mode, tokens={0: 2, 1: 1})
    return room


def guessing(mode: str = "voice") -> Room:
    return go(room_for(mode), NOW, C.PlayRequest(0), C.PlacePreview(0, 1), C.PlaceConfirm(0, 2))


@pytest.mark.parametrize("mode", ["voice", "app"])
def test_cancel_in_guessing_returns_to_placing_keeping_preview(mode: str) -> None:
    room = guessing(mode)
    assert room.phase == Phase.GUESSING
    room = go(room, NOW, C.PlaceCancel(0))
    t = room.turn
    assert room.phase == Phase.PLACING and t is not None
    assert t.placed_index is None and t.preview_index == 2 and t.place_changes == 1
    assert not t.guessed and t.guess_title is None and t.guess_artist is None


def test_cancel_does_not_touch_tokens_or_hints_and_leaves_the_hint_timer() -> None:
    room = go(room_for(), NOW, C.PlayRequest(0), C.UseHint(0, "artist"), C.PlaceConfirm(0, 2))
    before = (room.timers["hint"].deadline_ts, [tm.tokens for tm in room.teams], list(room.turn.hints_used))  # type: ignore[union-attr]
    room = go(room, NOW + 5, C.PlaceCancel(0))
    assert room.timers["hint"].deadline_ts == before[0]
    assert [tm.tokens for tm in room.teams] == before[1] and room.turn.hints_used == before[2]  # type: ignore[union-attr]


def test_hint_timer_still_confirms_after_going_back() -> None:
    room = go(room_for(), NOW, C.PlayRequest(0), C.UseHint(0, "artist"), C.PlaceConfirm(0, 2), C.PlaceCancel(0))
    room, _ = reduce(room, fire(room, "hint"), room.timers["hint"].deadline_ts)
    assert room.phase == Phase.GUESSING and room.turn is not None
    assert room.turn.placed_index == 2 and room.turn.placed_auto
    # automatic confirmation is final
    assert err(room, C.PlaceCancel(0)) == "wrong_phase"


def test_rejected_after_auto_placement_even_with_zero_changes() -> None:
    room = go(room_for(), NOW, C.PlayRequest(0), C.UseHint(0, "title"))
    room, _ = reduce(room, fire(room, "hint"), room.timers["hint"].deadline_ts)
    assert room.phase == Phase.GUESSING
    assert err(room, C.PlaceCancel(0)) == "wrong_phase"


@pytest.mark.parametrize("mode", ["voice", "app"])
def test_rejected_after_answering(mode: str) -> None:
    room = guessing(mode)
    answer: C.Command = C.VoiceConfirm(0) if mode == "voice" else C.GuessSubmit(0, "x", "y")
    room = go(room, NOW, answer)
    assert room.phase != Phase.GUESSING
    assert err(room, C.PlaceCancel(0)) == "wrong_phase"


def test_already_guessed_when_an_answer_is_stored_in_guessing() -> None:
    room = guessing("app")
    assert room.turn is not None
    room.turn.guessed = True  # defensive guard: an answer exists while still in GUESSING
    assert err(room, C.PlaceCancel(0)) == "already_guessed"


def test_rejected_for_other_team_spectator_and_wrong_phase() -> None:
    room = guessing()
    assert err(room, C.PlaceCancel(1)) == "not_your_turn"
    assert err(room, C.PlaceCancel(None)) == "not_your_turn"
    assert room.phase == Phase.GUESSING
    placing = go(room_for(), NOW, C.PlayRequest(0))
    assert err(placing, C.PlaceCancel(0)) == "wrong_phase"
    assert err(room_for(), C.PlaceCancel(0)) == "wrong_phase"


def test_limit_of_three_changes() -> None:
    room = go(room_for(), NOW, C.PlayRequest(0))
    for i in range(MAX_PLACE_CHANGES_PER_TURN):
        room = go(room, NOW, C.PlaceConfirm(0, i), C.PlaceCancel(0))
    room = go(room, NOW, C.PlaceConfirm(0, 3))
    assert err(room, C.PlaceCancel(0)) == "too_many_changes"
    assert room.phase == Phase.GUESSING and room.turn is not None and room.turn.placed_index == 3


def test_full_flow_after_going_back() -> None:
    room = go(guessing(), NOW, C.PlaceCancel(0), C.PlaceConfirm(0, 3), C.VoiceConfirm(0))
    assert room.phase == Phase.OBJECTION and room.turn is not None
    assert room.turn.placed_index == 3
    # a new turn resets the counters
    room, _ = reduce(room, fire(room, "objection"), room.timers["objection"].deadline_ts)
    assert room.phase == Phase.REVEAL and room.turn is not None
    assert room.turn.result is not None and room.turn.result.placed_ok  # 1997 goes after 1990


def test_cancel_in_app_mode_clears_nothing_visible_and_leaks_no_song() -> None:
    room = go(guessing("app"), NOW, C.PlaceCancel(0))
    assert room.turn is not None
    blob = json.dumps([view_json(room, s) for s in (0, 1, 2, None)], ensure_ascii=False)
    assert '"placeChangesLeft": 3' in blob or 'placeChangesLeft' in blob
    c = room.turn.card
    for secret in (c.title, c.artist, c.track_id, str(c.song_id)):
        assert secret not in blob


def test_projection_exposes_changes_left_and_placed_auto_to_everyone() -> None:
    room = go(room_for(), NOW, C.PlayRequest(0))
    for viewer in (0, 1, None):
        t = view_json(room, viewer)["turn"]
        assert t["placeChangesLeft"] == 3 and t["placedAuto"] is False
    room = go(room, NOW, C.PlaceConfirm(0, 1), C.PlaceCancel(0), C.PlaceConfirm(0, 1), C.PlaceCancel(0))
    for viewer in (0, 1, 2, None):
        t = view_json(room, viewer)["turn"]
        assert t["placeChangesLeft"] == 1 and t["placedAuto"] is False
        assert set(t) >= {"placeChangesLeft", "placedAuto"}
    auto = go(room_for(), NOW, C.PlayRequest(0), C.UseHint(0, "title"))
    auto, _ = reduce(auto, fire(auto, "hint"), auto.timers["hint"].deadline_ts)
    for viewer in (0, 1, None):
        assert view_json(auto, viewer)["turn"]["placedAuto"] is True
