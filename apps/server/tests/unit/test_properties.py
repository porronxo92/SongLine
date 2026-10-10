"""Hypothesis properties of the engine."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.game.models import Phase
from app.game.rules import insert_sorted, is_sorted, slot_is_correct
from tests.helpers import make_card
from tests.sim.run_bots import check_invariants, make_songs, play_game


@given(st.lists(st.integers(1950, 2030), max_size=15), st.integers(1950, 2030))
def test_correct_slots_keep_line_sorted(years: list[int], year: int) -> None:
    line = sorted(years)
    ok = [i for i in range(len(line) + 1) if slot_is_correct(line, i, year)]
    assert ok, "there is always at least one correct slot"
    for i in ok:
        new = line[:i] + [year] + line[i:]
        assert new == sorted(new)
    wrong = [i for i in range(len(line) + 1) if i not in ok]
    for i in wrong:
        new = line[:i] + [year] + line[i:]
        assert new != sorted(new)


@given(st.lists(st.integers(1950, 2030), max_size=15), st.integers(1950, 2030))
def test_insert_sorted_keeps_order(years: list[int], year: int) -> None:
    line = [make_card(i, y) for i, y in enumerate(sorted(years))]
    insert_sorted(line, make_card(99, year))
    assert is_sorted(line) and len(line) == len(years) + 1


@pytest.mark.parametrize("mode", ["voice", "app"])
@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(0, 10_000), teams=st.integers(2, 4), n_songs=st.sampled_from([6, 12, 40]))
def test_lines_sorted_cards_conserved_one_winner_set(mode: str, seed: int, teams: int, n_songs: int) -> None:
    songs = make_songs(n_songs, seed=seed)

    def check(room) -> None:  # type: ignore[no-untyped-def]
        check_invariants(room, len({s.id for s in songs}))
        if room.phase == Phase.GAME_OVER and room.game_over_reason == "target":
            reached = [t.slot for t in room.teams if len(t.timeline) >= room.settings.target_cards]
            assert len(reached) <= 1, "two teams reached the target at once"
            assert room.winners == reached

    room, stats = play_game(seed, team_count=teams, mode=mode, songs=songs, on_step=check)
    assert room.phase == Phase.GAME_OVER
