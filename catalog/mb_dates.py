#!/usr/bin/env python3
"""Fecha cada cancion candidata con MusicBrainz (primera publicacion de la grabacion).

Entrada: CSV con columnas Cancion,Artista,AliasTitulo,AliasArtista,Genero (sin anio).
Salida: filas con el formato de los packs (CSV_HEADER). El anio es el mas antiguo de
`first-release-date` entre las grabaciones cuyo titulo y artista coinciden bien y que no son
directos, remixes, versiones ni demos.

Uso:
    python mb_dates.py candidatas.csv --out salida.csv [--cache cache.json] [--prefix IES]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from import_spotify import (
    CSV_HEADER,
    Throttle,
    artist_similarity,
    fold,
    parse_year,
    request_with_retry,
    split_pipe,
    title_similarity,
    use_system_certificates,
)

MB_RECORDING_URL = "https://musicbrainz.org/ws/2/recording/"
MB_USER_AGENT = "SongLine/0.1 (porronxo92@gmail.com)"
MB_INTERVAL = 1.0
RESULT_LIMIT = 15

MIN_TITLE_SIM = 0.85
MIN_ARTIST_SIM = 0.8
CLEAR_TITLE_SIM = 0.9    # por debajo, la mejor coincidencia se considera floja
CLEAR_ARTIST_SIM = 0.85
MAX_YEAR_GAP = 1

CANDIDATE_COLUMNS = ["Cancion", "Artista", "AliasTitulo", "AliasArtista", "Genero"]

_RE_BAD = re.compile(
    r"\blive\b|en directo|en vivo|\bacustic[oa]?\b|\bacoustic\b|\bdemo\b|\bremix\w*\b"
    r"|\bversion\b|\bedit\b|\bkaraoke\b"
)


def is_bad_version(title: str, disambiguation: str, own_title: str = "") -> bool:
    """Directo, acustico, demo, remix, version, edit o karaoke. Una palabra que ya esta en el
    titulo buscado no cuenta (p. ej. una cancion que se llame «Live»)."""
    own = fold(own_title)
    text = fold(f"{title} || {disambiguation or ''}")
    return any(m.group(0) not in own for m in _RE_BAD.finditer(text))


BAD_SECONDARY = {"Live", "Remix", "Demo", "DJ-mix", "Mixtape/Street", "Spokenword", "Interview", "Audiobook"}
STUDIO_PRIMARY = {"Album", "Single", "EP"}


def _release_ok(rel: dict) -> bool:
    """Lanzamiento oficial de estudio: no directo, remix, demo ni similares."""
    rg = rel.get("release-group") or {}
    return not (set(rg.get("secondary-types") or []) & BAD_SECONDARY)


def only_live_releases(rec: dict) -> bool:
    """True si la grabacion solo aparece en lanzamientos de directo, remix, demo, etc.
    Sin informacion de lanzamientos no se descarta."""
    rels = rec.get("releases") or []
    return bool(rels) and not any(_release_ok(r) for r in rels)


def has_studio_release(rec: dict, year: int) -> bool:
    """La fecha mas antigua esta respaldada por un lanzamiento oficial (album, single o EP) de ese anio."""
    for rel in rec.get("releases") or []:
        rg = rel.get("release-group") or {}
        if (rel.get("status") == "Official" and rg.get("primary-type") in STUDIO_PRIMARY
                and _release_ok(rel) and "Compilation" not in (rg.get("secondary-types") or [])
                and parse_year(rel.get("date")) == year):
            return True
    return False


def credit_names(rec: dict) -> list[str]:
    names: list[str] = []
    for ac in rec.get("artist-credit") or []:
        if not isinstance(ac, dict):
            continue
        name = ac.get("name") or (ac.get("artist") or {}).get("name")
        if name:
            names.append(name)
        sort = (ac.get("artist") or {}).get("name")
        if sort and sort not in names:
            names.append(sort)
    return names


@dataclass
class Match:
    title: str
    date: str
    year: int
    title_sim: float
    artist_sim: float
    mbid: str = ""
    corroborated: bool = False
    has_releases: bool = False


@dataclass
class Dating:
    year: int | None
    status: str
    note: str
    found: bool  # hubo alguna grabacion valida (con o sin fecha)


def valid_matches(recordings: list[dict], row: dict[str, str]) -> tuple[list[Match], int]:
    """Grabaciones validas con fecha, y numero de validas sin fecha."""
    titles = [row["Cancion"], *split_pipe(row.get("AliasTitulo", ""))]
    artists = [row["Artista"], *split_pipe(row.get("AliasArtista", ""))]
    out: list[Match] = []
    undated = 0
    for rec in recordings:
        title = rec.get("title") or ""
        if is_bad_version(title, rec.get("disambiguation") or "", row["Cancion"]) or only_live_releases(rec):
            continue
        t_sim = title_similarity(titles, title)
        a_sim = artist_similarity(artists, credit_names(rec))
        if t_sim < MIN_TITLE_SIM or a_sim < MIN_ARTIST_SIM:
            continue
        date = rec.get("first-release-date") or ""
        year = parse_year(date)
        if year is None:
            undated += 1
            continue
        out.append(Match(title, date, year, t_sim, a_sim, rec.get("id", ""), has_studio_release(rec, year),
                          bool(rec.get("releases"))))
    out.sort(key=lambda m: (m.date, -m.title_sim))
    return out, undated


def date_song(recordings: list[dict], row: dict[str, str]) -> Dating:
    matches, undated = valid_matches(recordings, row)
    if not matches:
        if undated:
            return Dating(None, "disputed", "MusicBrainz: grabaciones sin fecha", True)
        return Dating(None, "disputed", "MusicBrainz: sin coincidencias validas", False)
    first = matches[0]
    note = f"MusicBrainz: primera publicación {first.date}"
    best_t = max(m.title_sim for m in matches)
    best_a = max(m.artist_sim for m in matches)
    if best_t < CLEAR_TITLE_SIM or best_a < CLEAR_ARTIST_SIM:
        return Dating(first.year, "disputed",
                      f"{note}; coincidencia floja (título {best_t:.2f}, artista {best_a:.2f})", True)
    if first.has_releases and not first.corroborated:
        return Dating(first.year, "disputed",
                      f"{note}; sin álbum, single o EP oficial de {first.year} que lo respalde", True)
    if len(matches) > 1:
        second = matches[1]
        if second.year - first.year > MAX_YEAR_GAP and first.corroborated:
            note += f"; confirmada por lanzamiento oficial de {first.year} (otras grabaciones: {second.year})"
        elif second.year - first.year > MAX_YEAR_GAP:
            years = ", ".join(str(m.year) for m in matches[:4])
            return Dating(first.year, "disputed",
                          f"{note}; las dos grabaciones más antiguas difieren ({years})", True)
    return Dating(first.year, "verified", note, True)


class MusicBrainzSearch:
    def __init__(self, http: httpx.Client | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.http = http or httpx.Client(timeout=30.0)
        self.sleep = sleep
        self.throttle = Throttle(MB_INTERVAL, clock, sleep)

    @staticmethod
    def build_query(title: str, artist: str) -> str:
        esc = lambda s: s.replace("\\", " ").replace('"', '\\"')
        return f'recording:"{esc(title)}" AND artist:"{esc(artist)}"'

    def search(self, title: str, artist: str) -> list[dict]:
        resp = request_with_retry(
            self.http, "GET", MB_RECORDING_URL, sleep=self.sleep, throttle=self.throttle,
            headers={"User-Agent": MB_USER_AGENT, "Accept": "application/json"},
            params={"query": self.build_query(title, artist), "fmt": "json", "limit": RESULT_LIMIT},
        )
        resp.raise_for_status()
        return resp.json().get("recordings") or []


def slim(rec: dict) -> dict:
    """Solo los campos que usamos, para que la cache pese poco."""
    out = {k: rec[k] for k in ("id", "title", "disambiguation", "first-release-date") if k in rec}
    out["artist-credit"] = [{"name": a.get("name"), "artist": {"name": (a.get("artist") or {}).get("name")}}
                            for a in rec.get("artist-credit") or [] if isinstance(a, dict)]
    out["releases"] = [
        {"status": r.get("status"), "date": r.get("date"),
         "release-group": {"primary-type": (r.get("release-group") or {}).get("primary-type"),
                           "secondary-types": (r.get("release-group") or {}).get("secondary-types") or []}}
        for r in rec.get("releases") or []
    ]
    return out


def read_candidates(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != CANDIDATE_COLUMNS:
            raise ValueError(f"Cabecera inesperada en {path}: {reader.fieldnames}")
        return [{k: (v or "").strip() for k, v in r.items()} for r in reader]


def to_pack_row(row: dict[str, str], dating: Dating, row_id: str) -> dict[str, str]:
    return {
        "ID": row_id, "Cancion": row["Cancion"], "Artista": row["Artista"],
        "Anio": str(dating.year) if dating.year else "", "Genero": row["Genero"], "Origen": "es",
        "AliasTitulo": row.get("AliasTitulo", ""), "AliasArtista": row.get("AliasArtista", ""),
        "Nota": dating.note, "SpotifyTrackId": "", "ISRC": "", "Estado": dating.status,
    }


def process(rows: list[dict[str, str]], client, cache: dict[str, list[dict]] | None = None,
            save_cache: Callable[[], None] = lambda: None,
            log: Callable[[str], None] = lambda s: None, prefix: str = "MB") -> list[dict[str, str]]:
    cache = cache if cache is not None else {}
    out: list[dict[str, str]] = []
    for n, row in enumerate(rows, 1):
        key = f"{row['Cancion']}|{row['Artista']}"
        if key not in cache:
            try:
                cache[key] = [slim(r) for r in client.search(row["Cancion"], row["Artista"])]
            except httpx.HTTPError as exc:
                log(f"  aviso: {key}: {exc}")
                continue
            save_cache()
        dating = date_song(cache[key], row)
        out.append(to_pack_row(row, dating, f"{prefix}{n:03d}"))
        log(f"[{n}/{len(rows)}] {row['Cancion']} - {row['Artista']}: {dating.year or '-'} {dating.status}")
    return out


def write_pack_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None, client=None) -> int:
    p = argparse.ArgumentParser(description="Fecha canciones candidatas con MusicBrainz.")
    p.add_argument("csv", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cache", type=Path, help="JSON con las respuestas ya descargadas (permite reanudar)")
    p.add_argument("--prefix", default="MB")
    args = p.parse_args(argv)
    if client is None:
        use_system_certificates()
        client = MusicBrainzSearch()
    cache: dict[str, list[dict]] = {}
    if args.cache and args.cache.is_file():
        cache = json.loads(args.cache.read_text(encoding="utf-8"))

    def save() -> None:
        if args.cache:
            args.cache.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    rows = read_candidates(args.csv)
    out = process(rows, client, cache, save, print, args.prefix)
    write_pack_rows(args.out, out)
    verified = sum(r["Estado"] == "verified" for r in out)
    print(f"{len(out)} filas, {verified} verified. Salida en {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
