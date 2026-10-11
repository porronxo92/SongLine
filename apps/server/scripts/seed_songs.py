"""Carga el catálogo en las tablas `packs` y `songs` (upsert por `csv_id`).

Uso (desde apps/server, con el .env de la raíz):
    .venv/Scripts/python scripts/seed_songs.py [ruta.csv ...] [--dry-run]

Sin argumentos siembra `catalog/songs.csv` como pack `mix` y cada `catalog/packs/<slug>.csv` como
pack `<slug>`, más la tabla `packs` desde `catalog/packs.json`. Con rutas, siembra solo esos ficheros
(`songs.csv` es el pack `mix`; otro fichero usa su nombre sin extensión como pack).

Es idempotente. Al repetirlo actualiza título, artista, año, alias, notas y pack, pero no borra
`spotify_track_id` ni `isrc` ya guardados si el CSV los trae vacíos.
`enabled` es true solo si `year_status = 'verified'`, igual que el modo CSV de la API. Las canciones que el importador ya procesó
(tienen `spotify_track_id`) conservan su `year_status` y su `enabled`.
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import REPO_ROOT, AppConfig

VALID_STATES = {"pending", "verified", "ambiguous", "disputed"}
CATALOG = REPO_ROOT / "catalog"

UPSERT = text(
    """
    INSERT INTO songs (csv_id, title, artist, year, year_status, year_note, title_aliases,
                       artist_aliases, genre, origin, spotify_track_id, isrc, enabled, pack)
    VALUES (:csv_id, :title, :artist, :year, :year_status, :year_note, :title_aliases,
            :artist_aliases, :genre, :origin, :track_id, :isrc, :enabled, :pack)
    ON CONFLICT (csv_id) DO UPDATE SET
        title = EXCLUDED.title,
        artist = EXCLUDED.artist,
        year = EXCLUDED.year,
        -- Una canción ya procesada por el importador (tiene track_id) conserva su estado y su `enabled`:
        -- volver a sembrar no debe rehabilitar lo que el importador descartó.
        year_status = CASE WHEN songs.spotify_track_id IS NOT NULL THEN songs.year_status ELSE EXCLUDED.year_status END,
        year_note = EXCLUDED.year_note,
        title_aliases = EXCLUDED.title_aliases,
        artist_aliases = EXCLUDED.artist_aliases,
        genre = EXCLUDED.genre,
        origin = EXCLUDED.origin,
        spotify_track_id = COALESCE(EXCLUDED.spotify_track_id, songs.spotify_track_id),
        isrc = COALESCE(EXCLUDED.isrc, songs.isrc),
        enabled = CASE WHEN songs.spotify_track_id IS NOT NULL THEN songs.enabled ELSE EXCLUDED.enabled END,
        pack = EXCLUDED.pack,
        updated_at = now()
    """
)

UPSERT_PACK = text(
    """
    INSERT INTO packs (slug, name, description, icon, sort)
    VALUES (:slug, :name, :description, :icon, :sort)
    ON CONFLICT (slug) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        icon = EXCLUDED.icon,
        sort = EXCLUDED.sort
    """
)


def _aliases(raw: str) -> list[str]:
    return [a.strip() for a in raw.split("|") if a.strip()]


def read_rows(path: Path, pack: str = "mix") -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for n, r in enumerate(csv.DictReader(fh), start=2):
            state = (r.get("Estado") or "").strip().lower() or "verified"
            if state not in VALID_STATES:
                raise ValueError(f"{path.name} fila {n}: Estado inválido {state!r}")
            rows.append(
                {
                    "csv_id": r["ID"].strip(),
                    "title": r["Cancion"].strip(),
                    "artist": r["Artista"].strip(),
                    "year": int(r["Anio"]),
                    "year_status": state,
                    "year_note": (r.get("Nota") or "").strip() or None,
                    "title_aliases": _aliases(r.get("AliasTitulo") or ""),
                    "artist_aliases": _aliases(r.get("AliasArtista") or ""),
                    "genre": (r.get("Genero") or "").strip() or None,
                    "origin": (r.get("Origen") or "").strip().lower() or None,
                    "track_id": (r.get("SpotifyTrackId") or "").strip() or None,
                    "isrc": (r.get("ISRC") or "").strip() or None,
                    "enabled": state == "verified",
                    "pack": pack,
                }
            )
    return rows


def read_pack_defs(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return [
        {
            "slug": p["slug"],
            "name": p["name"],
            "description": p.get("description", ""),
            "icon": p.get("icon", "music"),
            "sort": int(p.get("sort", 100)),
        }
        for p in raw
    ]


def pack_of(path: Path) -> str:
    return "mix" if path.name == "songs.csv" else path.stem


def default_sources(catalog: Path = CATALOG) -> list[Path]:
    sources = [catalog / "songs.csv"]
    packs_dir = catalog / "packs"
    if packs_dir.is_dir():
        sources.extend(sorted(p for p in packs_dir.glob("*.csv") if p.stem != "mix"))
    return sources


async def main(paths: list[Path], dry_run: bool, packs_json: Path = CATALOG / "packs.json") -> None:
    defs = read_pack_defs(packs_json) if not paths else []
    rows: list[dict[str, object]] = []
    for path in paths or default_sources():
        part = read_rows(path, pack_of(path))
        by_state: dict[str, int] = {}
        for r in part:
            by_state[str(r["year_status"])] = by_state.get(str(r["year_status"]), 0) + 1
        print(f"{pack_of(path)}: {len(part)} canciones {by_state}")
        rows.extend(part)
    ids = [str(r["csv_id"]) for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("hay csv_id repetidos entre ficheros")
    print(f"Total: {len(rows)} canciones, {len(defs)} packs")
    if dry_run:
        print("--dry-run: no se escribe nada")
        return
    engine = create_async_engine(AppConfig().database_url)
    async with engine.begin() as conn:
        if defs:
            await conn.execute(UPSERT_PACK, defs)
        if rows:
            await conn.execute(UPSERT, rows)
        total = (await conn.execute(text("SELECT count(*) FROM songs"))).scalar()
        enabled = (await conn.execute(text("SELECT count(*) FROM songs WHERE enabled"))).scalar()
    await engine.dispose()
    print(f"BD: {total} canciones en total, {enabled} habilitadas")


if __name__ == "__main__":
    args = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(args, "--dry-run" in sys.argv))
