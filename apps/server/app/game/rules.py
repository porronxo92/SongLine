"""Pure game rules: slot correctness, insertion, standings."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence

from app.game.models import Card, SlotExplanation, SlotReason, Team


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


def explain_slot(years: Sequence[int], index: int, year: int) -> SlotExplanation:
    """Explain slot correctness; `ok` always agrees with `slot_is_correct`."""
    left = years[index - 1] if 0 < index <= len(years) else None
    right = years[index] if 0 <= index < len(years) else None
    ok = slot_is_correct(years, index, year)
    reason: SlotReason
    if ok:
        eq_l, eq_r = left == year, right == year
        reason = "equal_both" if eq_l and eq_r else "equal_left" if eq_l else "equal_right" if eq_r else "inside"
    else:
        reason = "too_early" if left is not None and year < left else "too_late"
    return SlotExplanation(
        index=index,
        left_year=left,
        right_year=right,
        ok=ok,
        reason=reason,
        valid_from=bisect_left(years, year),
        valid_to=bisect_right(years, year),
    )


def insert_sorted(timeline: list[Card], card: Card) -> int:
    """Insert keeping the line ordered by year (after equal years). Returns the index."""
    idx = bisect_right([c.year for c in timeline], card.year)
    timeline.insert(idx, card)
    return idx


def is_sorted(timeline: Sequence[Card]) -> bool:
    return all(a.year <= b.year for a, b in zip(timeline, timeline[1:], strict=False))


def card_count(team: Team) -> int:
    return len(team.timeline)  # D3: the initial card counts


def rank_standings(teams: Sequence[Team]) -> dict[int, int]:
    """Competition ranking by card count only: 1, 1, 3. Tokens never break ties.

    Maps each claimed team's slot to its position (>= 1).
    """
    claimed = sorted((t for t in teams if t.claimed), key=lambda t: (-card_count(t), t.slot))
    ranks: dict[int, int] = {}
    for i, t in enumerate(claimed):
        prev = claimed[i - 1] if i else None
        ranks[t.slot] = ranks[prev.slot] if prev and card_count(prev) == card_count(t) else i + 1
    return ranks


def pick_winners(teams: Sequence[Team]) -> list[int]:
    """Winners are the teams in position 1 (most cards; tied teams share it)."""
    ranks = rank_standings(teams)
    return sorted(slot for slot, r in ranks.items() if r == 1)


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
