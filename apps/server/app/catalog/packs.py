"""Pack definitions (`catalog/packs.json`): the list of genre packs a room can pick."""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from app.game.models import Song

log = logging.getLogger(__name__)

DEFAULT_PACK = "mix"


class PackDef(BaseModel, frozen=True):
    slug: str
    name: str
    description: str = ""
    icon: str = "music"
    sort: int = 100


def load_pack_defs(path: Path) -> list[PackDef]:
    """Reads packs.json sorted by `sort`. A missing or broken file leaves only the `mix` pack."""
    fallback = [PackDef(slug=DEFAULT_PACK, name="Mix variado", icon="disc-3", sort=10)]
    if not path.exists():
        log.warning("packs.json not found: %s (only the %s pack is available)", path, DEFAULT_PACK)
        return fallback
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        defs = [PackDef.model_validate(p) for p in raw]
    except (ValueError, TypeError, ValidationError):
        log.exception("invalid packs.json: %s", path)
        return fallback
    seen: set[str] = set()
    unique: list[PackDef] = []
    for d in defs:
        if d.slug not in seen:
            seen.add(d.slug)
            unique.append(d)
    return sorted(unique, key=lambda d: (d.sort, d.slug))


def pack_listing(defs: list[PackDef], songs: list[Song]) -> list[dict[str, Any]]:
    """Public view: every pack (even empty ones) with its count of enabled songs."""
    counts = Counter(s.pack for s in songs)
    return [
        {"slug": d.slug, "name": d.name, "description": d.description, "icon": d.icon, "count": counts[d.slug]}
        for d in defs
    ]
