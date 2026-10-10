"""Title/artist validation for app mode (DISENO section 8). Pure."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

STOPWORDS = frozenset({"the", "a", "an", "el", "la", "los", "las", "un", "una", "lo"})


@dataclass(frozen=True)
class Thresholds:
    ratio: float = 88.0
    token_set: float = 92.0
    token_set_len: float = 0.6
    dist_divisor: int = 5


DEFAULT_THRESHOLDS = Thresholds()

_ARTIST_SPLIT = re.compile(
    r"\s*(?:,|&|;|\bfeat\.?(?=\s|$)|\bft\.?(?=\s|$)|\bfeaturing\b|\bwith\b|\bcon\b|\by\b|\band\b|\bx\b)\s*",
    re.IGNORECASE,
)


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = re.split(r"\s+-\s+", s)[0]
    s = re.sub(r"\b(feat|ft|featuring|con|with)\b\.?.*$", " ", s)
    s = s.replace("&", " y ").replace(" and ", " y ")
    s = s.replace("'n'", " y ")
    s = re.sub(r"\bn'(?=\s|$)", " y ", s)  # Guns N' Roses
    s = s.replace("'", "").replace(".", "")  # don't -> dont, Y.M.C.A. -> ymca
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(t for t in s.split() if t not in STOPWORDS)


def _close(ng: str, nc: str, th: Thresholds) -> bool:
    if ng == nc:
        return True
    d = Levenshtein.distance(ng, nc)
    return d <= max(1, len(nc) // th.dist_divisor) or fuzz.ratio(ng, nc) >= th.ratio


def match_title(
    guess: str, canonical: str, aliases: Iterable[str] = (), th: Thresholds = DEFAULT_THRESHOLDS
) -> bool:
    ng = normalize(guess)
    if not ng:
        return False
    for c in (canonical, *aliases):
        nc = normalize(c)
        if not nc:
            continue
        if _close(ng, nc, th):
            return True
        if fuzz.token_set_ratio(ng, nc) >= th.token_set and len(ng) >= th.token_set_len * len(nc):
            return True
    return False


def artist_variants(canonical: str) -> list[str]:
    variants = [canonical]
    variants.extend(p for p in _ARTIST_SPLIT.split(canonical) if p.strip())
    return variants


def match_artist(
    guess: str, canonical: str, aliases: Iterable[str] = (), th: Thresholds = DEFAULT_THRESHOLDS
) -> bool:
    """Any main artist is enough; a guess made of tokens of the artist name also counts."""
    ng = normalize(guess)
    if not ng:
        return False
    gtokens = set(ng.split())
    for c in (canonical, *aliases):
        for v in artist_variants(c):
            nv = normalize(v)
            if not nv:
                continue
            if _close(ng, nv, th):
                return True
            if len(ng) >= 4 and gtokens <= set(nv.split()):
                return True
    return False


@dataclass(frozen=True)
class GuessResult:
    title_ok: bool
    artist_ok: bool
    score: float


def validate_guess(
    title: str,
    artist: str,
    *,
    card_title: str,
    card_artist: str,
    title_aliases: Iterable[str] = (),
    artist_aliases: Iterable[str] = (),
    th: Thresholds = DEFAULT_THRESHOLDS,
) -> GuessResult:
    t_ok = match_title(title, card_title, title_aliases, th)
    a_ok = match_artist(artist, card_artist, artist_aliases, th)
    score = (
        fuzz.ratio(normalize(title), normalize(card_title)) / 200
        + fuzz.ratio(normalize(artist), normalize(card_artist)) / 200
    )
    return GuessResult(t_ok, a_ok, round(score, 3))
