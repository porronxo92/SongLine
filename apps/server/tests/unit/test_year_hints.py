"""Historical year hints: payment, pure selection, persistence and private projection."""

import json
from datetime import date
from itertools import product

import pytest

from app.game import commands as C
from app.game.commands import GameError
from app.game.engine import reduce
from app.game.models import Phase, Room, YearEvent
from app.game.projection import token_delta, view_json
from app.game.rules import year_event_for
from tests.helpers import fire, go, make_card, rigged

NOW = 1000.0
EVENTS = tuple(YearEvent(id=f"event-{n}", year=1990, category="science", text=text,
                         source_url="https://example.org/events", occurred_on=date(1990, 4, n))
               for n, text in enumerate(("Se pone en órbita el telescopio espacial Hubble.",
                                         "Se publica una propuesta para la World Wide Web."), 1))


def placing(mode="voice", tokens=4):
    card = make_card(500, 1990, title="Título secreto", artist="Artista secreto")
    card.year_events = EVENTS
    room, _ = rigged({0: [1980, 2000], 1: [1985]}, 1990, mode=mode,
                     tokens={0: tokens, 1: 0}, mystery=card)
    return go(room, NOW, C.PlayRequest(0))


def reject(room, command, expected):
    before = room.model_dump_json()
    with pytest.raises(GameError) as caught:
        reduce(room, command, NOW)
    assert caught.value.code == expected
    assert room.model_dump_json() == before


def test_year_hint_costs_two_always_and_keeps_existing_deadline():
    room = go(placing(), NOW, C.UseHint(0, "artist"))
    deadline = room.turn.hint_deadline_ts
    room, effects = reduce(room, C.UseHint(0, "year"), NOW + 12)
    assert room.teams[0].tokens == 1
    assert room.turn.hints_used == ["artist", "year"]
    assert room.turn.hint_deadline_ts == deadline
    assert not any(isinstance(e, C.StartTimer) for e in effects)
    assert [e.payload for e in effects if isinstance(e, C.Broadcast)] == [{"slot": 0, "kind": "year"}]
    reject(room, C.UseHint(0, "year"), "hint_already_used")


@pytest.mark.parametrize("mode", ["voice", "app"])
@pytest.mark.parametrize("placed_ok,title_ok,artist_ok", list(product([False, True], repeat=3)))
def test_year_never_refunds_and_bonus_and_other_stakes_remain_independent(mode, placed_ok, title_ok, artist_ok):
    room = go(placing(mode), NOW, C.UseHint(0, "year"), C.UseHint(0, "title"), C.UseHint(0, "artist"),
              C.PlaceConfirm(0, 1 if placed_ok else 0))
    if mode == "voice":
        room = go(room, NOW, C.VoiceConfirm(0), C.HonorClaim(0, title_ok, artist_ok))
    else:
        room = go(room, NOW, C.GuessSubmit(0, "Título secreto" if title_ok else "", "Artista secreto" if artist_ok else ""))
    expected = int(title_ok) + int(artist_ok) + int(placed_ok and title_ok and artist_ok)
    assert room.phase == Phase.REVEAL
    assert room.teams[0].tokens == expected
    assert "year" not in room.turn.hint_refunds
    result = view_json(room, 0)["turn"]["result"]
    assert result["hintRefunds"][0] == {"kind": "year", "refunded": False}
    assert token_delta(room) == {"0": expected - 4}
    room = Room.model_validate_json(room.model_dump_json())
    if mode == "voice":
        room = go(room, NOW, C.HonorClaim(0, title_ok, artist_ok))
    assert room.teams[0].tokens == expected
    _, effects = reduce(room, C.NextTurn(0), NOW + 6)
    resolved = next(e for e in effects if isinstance(e, C.Broadcast) and e.type == "turn_resolved")
    assert resolved.payload["token_delta"] == token_delta(room)


def test_year_guards_are_atomic_and_only_placing_allows_purchase():
    room = placing(tokens=2)
    reject(room, C.UseHint(1, "year"), "not_your_turn")
    reject(room, C.UseHint(None, "year"), "not_your_turn")
    reject(placing(tokens=1), C.UseHint(0, "year"), "no_tokens")
    missing = placing()
    missing.turn.card.year_events = ()
    reject(missing, C.UseHint(0, "year"), "hint_unavailable")
    mismatched = placing()
    mismatched.turn.card.year_events = (EVENTS[0].model_copy(update={"year": 1989}),)
    reject(mismatched, C.UseHint(0, "year"), "hint_unavailable")
    off = placing()
    off.settings.hints_enabled = False
    reject(off, C.UseHint(0, "year"), "hints_disabled")
    guessing = go(room, NOW, C.PlaceConfirm(0, 1))
    reject(guessing, C.UseHint(0, "year"), "wrong_phase")
    paused = go(room, NOW, C.Disconnected(0))
    reject(paused, C.UseHint(0, "year"), "paused")


def test_event_is_private_and_only_after_payment_and_stable_across_snapshot_pause_and_restore():
    room = placing()
    for viewer in (None, 0, 1):
        blob = json.dumps(view_json(room, viewer), ensure_ascii=False)
        assert all(e.text not in blob and e.id not in blob for e in EVENTS)
    assert view_json(room, 0)["turn"]["hints"]["yearAvailable"] is True
    room = go(room, NOW, C.UseHint(0, "year"))
    chosen = year_event_for(room.turn.card)
    assert chosen is not None
    stages = [room, Room.model_validate_json(room.model_dump_json()),
              go(room, NOW, C.Disconnected(0)), go(room, NOW, C.PlaceConfirm(0, 1)),
              go(Room.model_validate_json(room.model_dump_json()), NOW, C.Restored())]
    for stage in stages:
        for viewer in (None, 0, 1):
            hints = view_json(stage, viewer)["turn"]["hints"]
            if viewer == 0:
                assert hints["used"] == [{"kind": "year", "event": {"text": chosen.text, "category": chosen.category}}]
            else:
                assert hints["used"] == [{"kind": "year"}]
                assert hints["yearAvailable"] is None
                assert chosen.text not in json.dumps(view_json(stage, viewer), ensure_ascii=False)
            blob = json.dumps(hints)
            for secret in (chosen.id, chosen.source_url, str(chosen.occurred_on), "1990", "Título secreto", "Artista secreto"):
                assert secret not in blob
    assert all(stage.teams[0].tokens == 2 for stage in stages)


def test_selection_varies_by_card_but_not_repository_order_and_legacy_snapshots_are_safe():
    card = placing().turn.card
    choices = set()
    for n in range(40):
        card.instance_id = f"random-instance-{n}"
        chosen = year_event_for(card)
        choices.add(chosen.id)
        card.year_events = tuple(reversed(card.year_events))
        assert year_event_for(card) == chosen
    assert choices == {e.id for e in EVENTS}
    data = placing().model_dump(mode="json")
    data["turn"]["card"].pop("year_events")
    legacy = Room.model_validate(data)
    assert view_json(legacy, 0)["turn"]["hints"]["yearAvailable"] is False
    reject(legacy, C.UseHint(0, "year"), "hint_unavailable")


def test_year_timer_auto_places_but_never_refunds_even_when_slot_is_correct():
    room = go(placing(tokens=2), NOW, C.UseHint(0, "year"), C.PlacePreview(0, 1))
    room = go(room, room.timers["hint"].deadline_ts, fire(room, "hint"))
    assert room.turn.placed_index == 1 and room.phase == Phase.GUESSING
    room = go(room, room.timers["hint"].deadline_ts, fire(room, "hint"))
    assert room.phase == Phase.REVEAL and room.turn.result.placed_ok
    assert room.teams[0].tokens == 0 and room.turn.hint_refunds == []


def test_year_stays_spent_after_corrected_claims_accept_guess_and_restored_reveal():
    room = go(placing(tokens=2), NOW, C.UseHint(0, "year"), C.PlaceConfirm(0, 1),
              C.VoiceConfirm(0), C.HonorClaim(0, True, True))
    assert room.teams[0].tokens == 1
    room = go(room, NOW, C.HonorClaim(0, False, False), C.HonorClaim(0, False, False))
    assert room.teams[0].tokens == 0 and room.turn.hint_refunds == []
    restored = go(Room.model_validate_json(room.model_dump_json()), NOW, C.Restored())
    assert restored.teams[0].tokens == 0 and restored.turn.hint_refunds == []
    app_room = go(placing("app", tokens=2), NOW, C.UseHint(0, "year"), C.PlaceConfirm(0, 1),
                  C.GuessSubmit(0, "", ""), C.AcceptGuess(1), C.AcceptGuess(1))
    assert app_room.teams[0].tokens == 1 and app_room.turn.hint_refunds == []
