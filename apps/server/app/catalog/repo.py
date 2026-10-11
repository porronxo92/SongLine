"""Song repositories: Postgres (table `songs`) and CSV (`catalog/songs.csv`)."""

from __future__ import annotations

import csv
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from app.game.models import Song

log = logging.getLogger(__name__)

EXCLUDED_CSV_STATES = frozenset({"ambiguous", "disputed"})


class SongRepository(Protocol):
    async def load_enabled(self) -> list[Song]: ...


def _split_aliases(raw: str) -> tuple[str, ...]:
    return tuple(a.strip() for a in raw.split("|") if a.strip())


def parse_csv(path: Path, pack: str = "mix", start_id: int = 1) -> list[Song]:
    """Parse `ID,Cancion,Artista,Anio,Genero,Origen,AliasTitulo,AliasArtista,Nota,SpotifyTrackId,ISRC,Estado`.

    Empty `Estado` counts as verified. `ambiguous` and `disputed` rows are excluded.
    Song ids are `start_id + row index`, so several files can share one id space.
    """
    songs: list[Song] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=1):
            state = (row.get("Estado") or "").strip().lower() or "verified"
            if state in EXCLUDED_CSV_STATES:
                continue
            title = (row.get("Cancion") or "").strip()
            artist = (row.get("Artista") or "").strip()
            try:
                year = int((row.get("Anio") or "").strip())
            except ValueError:
                log.warning("%s row %s skipped: invalid year", path.name, n)
                continue
            if not title or not artist or not 1900 <= year <= 2100:
                log.warning("%s row %s skipped: incomplete", path.name, n)
                continue
            songs.append(
                Song(
                    id=start_id + n - 1,
                    csv_id=(row.get("ID") or str(n)).strip(),
                    pack=pack,
                    title=title,
                    artist=artist,
                    year=year,
                    track_id=(row.get("SpotifyTrackId") or "").strip(),
                    isrc=(row.get("ISRC") or "").strip(),
                    title_aliases=_split_aliases(row.get("AliasTitulo") or ""),
                    artist_aliases=_split_aliases(row.get("AliasArtista") or ""),
                    genre=(row.get("Genero") or "").strip(),
                    origin=(row.get("Origen") or "").strip().lower(),
                    note=(row.get("Nota") or "").strip(),
                )
            )
    return songs


class CsvSongRepository:
    """`songs.csv` is the `mix` pack; every `<packs_dir>/<slug>.csv` is the pack `<slug>`."""

    def __init__(self, path: Path, packs_dir: Path | None = None) -> None:
        self.path = path
        self.packs_dir = packs_dir if packs_dir is not None else path.parent / "packs"

    async def load_enabled(self) -> list[Song]:
        sources: list[tuple[str, Path]] = []
        if self.path.exists():
            sources.append(("mix", self.path))
        else:
            log.warning("catalog csv not found: %s", self.path)
        if self.packs_dir.is_dir():
            sources.extend((p.stem, p) for p in sorted(self.packs_dir.glob("*.csv")) if p.stem != "mix")
        songs: list[Song] = []
        for pack, path in sources:
            songs.extend(parse_csv(path, pack, start_id=max((s.id for s in songs), default=0) + 1))
        return songs


class PostgresSongRepository:
    """Reads the `songs` table of DISENO 2.1 (`enabled = true`)."""

    def __init__(self, database_url: str) -> None:
        from sqlalchemy.ext.asyncio import create_async_engine

        self.engine = create_async_engine(database_url, pool_pre_ping=True)

    @staticmethod
    def row_to_song(r: Any) -> Song:
        return Song(
            id=r["id"],
            csv_id=r["csv_id"],
            title=r["title"],
            artist=r["artist"],
            year=r["year"],
            track_id=r["spotify_track_id"] or "",
            isrc=r["isrc"] or "",
            title_aliases=tuple(r["title_aliases"] or ()),
            artist_aliases=tuple(r["artist_aliases"] or ()),
            genre=r["genre"] or "",
            origin=r["origin"] or "",
            note=r["year_note"] or "",
            pack=r.get("pack") or "mix",
        )

    async def load_enabled(self) -> list[Song]:
        from sqlalchemy import text

        q = text(
            "SELECT id, csv_id, title, artist, year, spotify_track_id, isrc, title_aliases, "
            "artist_aliases, genre, origin, year_note, pack FROM songs WHERE enabled = true"
        )
        async with self.engine.connect() as conn:
            rows = (await conn.execute(q)).mappings().all()
        return [self.row_to_song(r) for r in rows]

    async def list_all(self, status: str | None = None) -> list[dict[str, Any]]:
        from sqlalchemy import text

        sql = "SELECT * FROM songs"
        params: dict[str, Any] = {}
        if status:
            sql += " WHERE year_status = :s"
            params["s"] = status
        async with self.engine.connect() as conn:
            rows = (await conn.execute(text(sql + " ORDER BY id"), params)).mappings().all()
        return [dict(r) for r in rows]

    async def update(self, song_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        from sqlalchemy import text

        allowed = {"year", "year_status", "year_note", "title_aliases", "artist_aliases", "enabled"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return None
        assign = ", ".join(f"{k} = :{k}" for k in sets)
        async with self.engine.begin() as conn:
            res = await conn.execute(
                text(f"UPDATE songs SET {assign}, updated_at = now() WHERE id = :id RETURNING *"),
                {**sets, "id": song_id},
            )
            row = res.mappings().first()
        return dict(row) if row else None


def catalog_stats(songs: list[Song]) -> dict[str, Any]:
    by_decade = Counter(f"{s.year // 10 * 10}s" for s in songs)
    by_origin = Counter(s.origin or "unknown" for s in songs)
    return {
        "total": len(songs),
        "by_decade": dict(sorted(by_decade.items())),
        "by_origin": dict(by_origin),
    }
