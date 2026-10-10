"""Pure game rules: slot correctness, insertion, standings."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence

from app.game.models import Card, Team


def slot_is_correct(years: Sequence[int], index: int, year: int) -> bool:
    """Index `i` into a sorted line is correct if years[i-1] <= year <= years[i].

    Equal years are valid on both sides.
    """
    if index < 0 or index > len(years):
        return False
    if index > 0 and years[index - 1] > year:
        return False
    return not (index < len(years) and year > years[index])


def line_slot_is_correct(timeline: Sequence[Card], index: int, year: int) -> bool:
    return slot_is_correct([c.year for c in timeline], index, year)


def insert_sorted(timeline: list[Card], card: Card) -> int:
    """Insert keeping the line ordered by year (after equal years). Returns the index."""
    idx = bisect_right([c.year for c in timeline], card.year)
    timeline.insert(idx, card)
    return idx


def is_sorted(timeline: Sequence[Card]) -> bool:
    return all(a.year <= b.year for a, b in zip(timeline, timeline[1:], strict=False))


def card_count(team: Team) -> int:
    return len(team.timeline)  # D3: the initial card counts


def pick_winners(teams: Sequence[Team], only_reached: int | None = None) -> list[int]:
    """Most cards, then most tokens; a full tie shares the victory."""
    pool = [t for t in teams if t.claimed]
    if only_reached is not None:
        pool = [t for t in pool if card_count(t) >= only_reached] or pool
    if not pool:
        return []
    best = max((card_count(t), t.tokens) for t in pool)
    return [t.slot for t in pool if (card_count(t), t.tokens) == best]


def deal_initial(deck: list[Card], team_count: int, min_gap: int = 5) -> list[Card]:
    """Pick one initial card per team, preferring a minimum year gap between teams.

    Removes the chosen cards from `deck` and returns them in slot order.
    """
    chosen: list[Card] = []
    for _ in range(team_count):
        pick = next((c for c in deck if all(abs(c.year - o.year) >= min_gap for o in chosen)), None)
        if pick is None:
            pick = deck[0]
        deck.remove(pick)
        chosen.append(pick)
    return chosen
