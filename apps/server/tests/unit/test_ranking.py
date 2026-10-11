from __future__ import annotations

import pytest

from app.game.models import Team
from app.game.rules import pick_winners, rank_standings
from tests.helpers import make_card


def teams(cards: list[int], tokens: list[int] | None = None, claimed: list[bool] | None = None) -> list[Team]:
    out: list[Team] = []
    n = 0
    for slot, k in enumerate(cards):
        t = Team(slot=slot, name=f"T{slot}", session_token_hash="h" if (claimed or [True] * len(cards))[slot] else None)
        for _ in range(k):
            n += 1
            t.timeline.append(make_card(n, 1950 + n))
        t.tokens = (tokens or [0] * len(cards))[slot]
        out.append(t)
    return out


def ranks(cards: list[int], tokens: list[int] | None = None) -> list[int]:
    r = rank_standings(teams(cards, tokens))
    return [r[s] for s in range(len(cards))]


@pytest.mark.parametrize(
    ("cards", "expected", "winners"),
    [
        ([3, 5, 4], [3, 1, 2], [1]),  # no tie
        ([5, 5, 3], [1, 1, 3], [0, 1]),  # tie for 1st
        ([5, 3, 3], [1, 2, 2], [0]),  # tie for 2nd
        ([4, 4, 4], [1, 1, 1], [0, 1, 2]),  # three tied
        ([4, 2, 4, 2], [1, 3, 1, 3], [0, 2]),  # 1, 1, 3, 3
        ([4, 4, 4, 4], [1, 1, 1, 1], [0, 1, 2, 3]),
        ([2, 3, 1, 3], [3, 1, 4, 1], [1, 3]),
    ],
)
def test_competition_ranking(cards: list[int], expected: list[int], winners: list[int]) -> None:
    assert ranks(cards) == expected
    assert pick_winners(teams(cards)) == winners


def test_tokens_never_change_the_position() -> None:
    assert ranks([3, 3, 2], [0, 5, 9]) == [1, 1, 3]
    assert pick_winners(teams([3, 3], [0, 4])) == [0, 1]
    assert ranks([2, 3], [9, 0]) == [2, 1]


def test_unclaimed_teams_are_ignored() -> None:
    ts = teams([3, 9, 3, 1], claimed=[True, False, True, True])
    assert rank_standings(ts) == {0: 1, 2: 1, 3: 3}
    assert pick_winners(ts) == [0, 2]


def test_no_teams() -> None:
    assert rank_standings([]) == {} and pick_winners([]) == []
