"""Valida los CSV de catalog/packs/*.csv (si existe alguno). Sin red."""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

import pytest

CATALOG = Path(__file__).resolve().parent.parent
PACKS_DIR = CATALOG / "packs"
PACKS_JSON = CATALOG / "packs.json"

HEADER = ["ID", "Cancion", "Artista", "Anio", "Genero", "Origen", "AliasTitulo", "AliasArtista",
          "Nota", "SpotifyTrackId", "ISRC", "Estado"]
ORIGINS = {"es", "intl"}
STATES = {"verified", "disputed", "ambiguous", "pending", ""}
PREFIXES = {
    "rock-poprock": "RPR",
    "indie-rock": "IND",
    "clasicos-espana": "CLE",
    "reggaeton": "REG",
    "disney": "DIS",
}

PACK_FILES = sorted(PACKS_DIR.glob("*.csv")) if PACKS_DIR.is_dir() else []


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s.replace("'", ""))
    return " ".join(s.split())


def read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def test_packs_json_is_well_formed() -> None:
    packs = json.loads(PACKS_JSON.read_text(encoding="utf-8"))
    slugs = [p["slug"] for p in packs]
    assert "mix" in slugs and len(slugs) == len(set(slugs))
    for p in packs:
        assert set(p) == {"slug", "name", "description", "icon", "sort"}, p
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", p["slug"])
        assert p["name"] and p["description"] and p["icon"] and isinstance(p["sort"], int)
    # every pack file has its entry in packs.json
    for f in PACK_FILES:
        assert f.stem in slugs, f"{f.name} no esta en packs.json"


@pytest.mark.parametrize("path", PACK_FILES, ids=[p.stem for p in PACK_FILES])
def test_pack_csv(path: Path) -> None:
    header, rows = read(path)
    assert header == HEADER
    ids = [r["ID"].strip() for r in rows]
    assert len(ids) == len(set(ids)), "IDs repetidos"
    prefix = PREFIXES.get(path.stem)
    for r in rows:
        rid = r["ID"].strip()
        if prefix:
            assert re.fullmatch(prefix + r"\d{3,}", rid), f"ID {rid!r} sin prefijo {prefix}"
        assert r["Cancion"].strip() and r["Artista"].strip(), rid
        assert re.fullmatch(r"\d{4}", r["Anio"].strip()), f"{rid}: Anio no entero"
        assert 1900 <= int(r["Anio"]) <= 2100, f"{rid}: Anio fuera de rango"
        assert r["Origen"].strip().lower() in ORIGINS, f"{rid}: Origen {r['Origen']!r}"
        assert (r["Estado"] or "").strip().lower() in STATES, f"{rid}: Estado {r['Estado']!r}"
    keys = [(norm(r["Cancion"]), norm(r["Artista"])) for r in rows]
    dups = {k for k in keys if keys.count(k) > 1}
    assert not dups, f"cancion+artista repetidos: {sorted(dups)}"


def test_ids_do_not_collide_across_files() -> None:
    seen: dict[str, str] = {}
    files = [CATALOG / "songs.csv", *PACK_FILES]
    for f in files:
        for r in read(f)[1]:
            rid = r["ID"].strip()
            assert rid not in seen, f"{rid} esta en {seen[rid]} y en {f.name}"
            seen[rid] = f.name


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
