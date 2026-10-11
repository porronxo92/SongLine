"""explain_slot and the structured turn result (why a slot was right or wrong)."""

from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from app.game import commands as C
from app.game.projection import view_json
from app.game.rules import explain_slot, slot_is_correct
from tests.helpers import go, rigged

NOW = 1000.0


def test_left_edge_inside_and_equal() -> None:
    e = explain_slot([2000, 2010], 0, 1990)
    assert (e.left_year, e.right_year, e.ok, e.reason) == (None, 2000, True, "inside")
    assert (e.valid_from, e.valid_to) == (0, 0)
    e = explain_slot([2000, 2010], 0, 2000)
    assert (e.ok, e.reason, e.valid_from, e.valid_to) == (True, "equal_right", 0, 1)


def test_right_edge() -> None:
    e = explain_slot([2000, 2010], 2, 2020)
    assert (e.left_year, e.right_year, e.ok, e.reason) == (2010, None, True, "inside")
    e = explain_slot([2000, 2010], 2, 2010)
    assert (e.ok, e.reason, e.valid_from, e.valid_to) == (True, "equal_left", 1, 2)


def test_single_card_line() -> None:
    assert explain_slot([2000], 0, 1990).reason == "inside"
    assert explain_slot([2000], 1, 2010).reason == "inside"
    e = explain_slot([2000], 1, 1990)
    assert (e.ok, e.reason, e.valid_from, e.valid_to) == (False, "too_early", 0, 0)
    e = explain_slot([2000], 0, 2010)
    assert (e.ok, e.reason, e.valid_from, e.valid_to) == (False, "too_late", 1, 1)
    e = explain_slot([2000], 0, 2000)
    assert (e.ok, e.reason, e.valid_from, e.valid_to) == (True, "equal_right", 0, 1)


def test_equal_left_and_right_in_the_middle() -> None:
    e = explain_slot([2012, 2015], 1, 2012)
    assert (e.left_year, e.right_year, e.reason, e.valid_from, e.valid_to) == (2012, 2015, "equal_left", 0, 1)
    assert explain_slot([2012, 2015], 1, 2015).reason == "equal_right"


def test_equal_both() -> None:
    e = explain_slot([2000, 2000], 1, 2000)
    assert (e.ok, e.reason, e.valid_from, e.valid_to) == (True, "equal_both", 0, 2)


def test_too_early_and_too_late() -> None:
    e = explain_slot([1990, 2000, 2010], 2, 1995)
    assert (e.ok, e.reason, e.valid_from, e.valid_to) == (False, "too_early", 1, 1)
    e = explain_slot([1990, 2000, 2010], 1, 2005)
    assert (e.ok, e.reason, e.valid_from, e.valid_to) == (False, "too_late", 2, 2)


def test_three_equal_cards_range() -> None:
    years = [1990, 2000, 2000, 2000, 2010]
    for i in range(1, 5):
        e = explain_slot(years, i, 2000)
        assert e.ok and (e.valid_from, e.valid_to) == (1, 4)
    assert [explain_slot(years, i, 2000).reason for i in range(1, 5)] == [
        "equal_right", "equal_both", "equal_both", "equal_left",
    ]
    assert not explain_slot(years, 0, 2000).ok and explain_slot(years, 0, 2000).reason == "too_late"
    assert not explain_slot(years, 5, 2000).ok and explain_slot(years, 5, 2000).reason == "too_early"


@given(st.lists(st.integers(1950, 1960), max_size=8), st.integers(1948, 1962))
def test_explain_agrees_with_slot_is_correct(raw: list[int], year: int) -> None:
    years = sorted(raw)
    valid = [i for i in range(len(years) + 1) if slot_is_correct(years, i, year)]
    for i in range(len(years) + 1):
        e = explain_slot(years, i, year)
        assert e.ok == (i in valid)
        assert (e.valid_from, e.valid_to) == (valid[0], valid[-1])


# --- engine ----------------------------------------------------------------------------------


def test_equal_to_left_neighbour_is_explained() -> None:
    room, now = rigged({0: [2012, 2015], 1: [2000], 2: [2005]}, 2012)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    room = go(room, now, C.HonorClaim(0, True, True))
    r = room.turn.result  # type: ignore[union-attr]
    assert r is not None
    assert r.song_year == 2012 and r.headline == "kept" and r.objection is None
    p = r.placement
    assert (p.index, p.left_year, p.right_year, p.ok, p.reason) == (1, 2012, 2015, True, "equal_left")
    assert (p.valid_from, p.valid_to) == (0, 1)
    assert r.token.awarded and r.token.reason == "awarded"


def test_objection_steals_and_is_explained() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990, 2010], 2: [2005]}, 1990, tokens={1: 1})
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 2), C.VoiceConfirm(0))
    room = go(room, now, C.Objection(1, 1))
    r = room.turn.result  # type: ignore[union-attr]
    assert r is not None
    assert r.headline == "stolen" and r.outcome == "stolen" and r.to_slot == 1
    assert (r.placement.ok, r.placement.reason, r.placement.valid_from, r.placement.valid_to) == (
        False, "too_early", 1, 1,
    )
    o = r.objection
    assert o is not None
    assert (o.slot, o.index, o.ok, o.token_spent, o.left_year, o.right_year) == (1, 1, True, True, 1980, 2000)
    assert r.token.awarded is False and r.token.reason == "wrong_slot"


def test_objection_failed_and_discard_headlines() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990], 2: [2005]}, 1990, tokens={1: 1})
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0), C.Objection(1, 2))
    r = room.turn.result  # type: ignore[union-attr]
    assert r is not None and r.headline == "kept_objection_failed"  # 1990 between 1980 and 2000
    assert r.objection is not None and not r.objection.ok and r.objection.reason == "too_early"

    room, now = rigged({0: [1980, 2000], 1: [1990], 2: [2005]}, 1990, tokens={1: 1})
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 2), C.VoiceConfirm(0), C.Objection(1, 0))
    r = room.turn.result  # type: ignore[union-attr]
    assert r is not None and r.headline == "discarded_objection_failed" and r.to_slot is None

    room, now = rigged({0: [1980, 2000], 1: [1990], 2: [2005]}, 1990)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 2), C.VoiceConfirm(0))
    r = room.turn.result  # type: ignore[union-attr]
    assert r is not None and r.headline == "discarded" and r.objection is None


def test_token_reasons_voice_mode() -> None:
    cases = [
        (True, True, "awarded"),
        (False, True, "title_wrong"),
        (True, False, "artist_wrong"),
        (False, False, "title_and_artist_wrong"),
    ]
    for title_ok, artist_ok, reason in cases:
        room, now = rigged({0: [1980, 2000], 1: [1990], 2: [2005]}, 1990)
        room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
        assert room.phase.value == "reveal"
        room = go(room, now, C.HonorClaim(0, title_ok, artist_ok))
        t = room.turn.result.token  # type: ignore[union-attr]
        assert t.reason == reason and t.awarded == (reason == "awarded")


def test_result_hidden_until_reveal_and_visible_after() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1995], 2: [2005]}, 1990, tokens={1: 1})
    steps = [C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0)]
    for cmd in steps:
        room = go(room, now, cmd)
        for v in (None, 0, 1, 2):
            t = view_json(room, v)["turn"]
            assert t["result"] is None and "songYear" not in json.dumps(t)
    room = go(room, now, C.ObjectionPass(1))
    for v in (None, 0, 1, 2):
        res = view_json(room, v)["turn"]["result"]
        assert res["songYear"] == 1990 and res["headline"] == "kept"
        assert res["placement"]["reason"] == "inside" or res["placement"]["reason"].startswith("too")
        assert set(res["placement"]) == {
            "index", "leftYear", "rightYear", "ok", "reason", "validFrom", "validTo",
        }
