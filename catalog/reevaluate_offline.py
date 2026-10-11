"""Reevalua un pack con los informes de `import_spotify.py` (catalog/review/<pack>/), sin llamar a Spotify.

Sirve cuando Spotify bloquea la cuota y la regla de verificacion se ha recalibrado: los candidatos ya
estan guardados en `matches.csv` (mejor candidato) y `dudosas.csv` (3 mejores).

Modos:
  ignore-year   Perfil por defecto sin el anio del album. Rescata filas cuyo mejor candidato tiene el titulo y el
                artista casi identicos y solo falla el anio del album (reediciones, recopilatorios). Sigue
                excluyendo directos, versiones, remasters y recopilatorios.
  soundtrack    Pack Disney: acepta un candidato si su album menciona la pelicula (columna Nota) y el titulo
                coincide. Puede cambiar el track_id por otro de los 3 mejores candidatos guardados.

El anio del juego es siempre el del CSV: este script nunca lo toca.

Uso (con el python de apps/server, que tiene acceso a la BD):
    apps/server/.venv/Scripts/python catalog/reevaluate_offline.py --pack clasicos-espana --mode ignore-year [--write-db]
Sin --write-db solo informa.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_spotify as imp  # noqa: E402

CATALOG = Path(__file__).resolve().parent
BAD_FLAGS_IGNORE_YEAR = {"live", "version", "remaster", "compilation"}
NEW_CONFIDENCE_MIN = imp.RELAXED_MIN_CONFIDENCE


def _flags(raw: str) -> set[str]:
    return {f.strip() for f in (raw or "").replace(";", ",").split(",") if f.strip()}


def rescue_ignore_year(match: dict[str, str]) -> bool:
    """True si el mejor candidato pasaria la regla relajada quitando el componente del anio del album."""
    if match["EstadoNuevo"] == "verified" or match["EstadoCurado"] != "verified" or not match["SpotifyTrackId"]:
        return False
    if _flags(match["Flags"]) & BAD_FLAGS_IGNORE_YEAR or "no coinciden" in match["Motivo"]:
        return False
    conf = float(match["Confianza"] or 0)
    year_c = imp.year_component(imp.parse_year(match["AlbumFecha"]), int(match["Anio"]))
    base = conf - 0.2 * year_c  # 0.45*titulo + 0.35*artista (el bonus de original no aplica si el anio no coincide)
    return base / 0.8 >= NEW_CONFIDENCE_MIN


def soundtrack_pick(
    match: dict[str, str], doubt: dict[str, str] | None, pack_row: dict[str, str]
) -> tuple[str, str, bool] | None:
    """Mejor candidato guardado que cumple el perfil soundtrack: (track_id, album, es_el_actual) o None."""
    if match["EstadoCurado"] != "verified":
        return None
    films = imp.film_names(pack_row)
    titles = [pack_row["Cancion"], *imp.split_pipe(pack_row.get("AliasTitulo", ""))]
    cands = [(match["SpotifyTrackId"], match["Cancion"], match["Album"], match["Flags"])]
    if match["Motivo"] and "no coinciden" in match["Motivo"]:
        cands = []  # el titulo del mejor candidato no es el de la cancion: no hay nombre fiable que reevaluar
    for i in (1, 2, 3):
        if doubt and doubt.get(f"C{i}_Id"):
            cands.append((doubt[f"C{i}_Id"], doubt[f"C{i}_Nombre"], doubt[f"C{i}_Album"], doubt.get(f"C{i}_Flags", "")))
    best: tuple[float, str, str] | None = None
    for tid, name, album, flags in cands:
        if not tid or _flags(flags) & imp.SOUNDTRACK_BAD_FLAGS:
            continue
        if not imp.album_mentions_film(album, films):
            continue
        t = imp.title_similarity(titles, name)
        if t < imp.MB_MIN_TITLE_SIM:
            continue
        if best is None or t > best[0] or (t == best[0] and tid == match["SpotifyTrackId"]):
            best = (t, tid, album)
    if best is None:
        return None
    return best[1], best[2], best[1] == match["SpotifyTrackId"]


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def plan(pack: str, mode: str) -> list[dict[str, object]]:
    review = CATALOG / "review" / pack
    matches = read(review / "matches.csv")
    doubts = {r["ID"]: r for r in read(review / "dudosas.csv")} if (review / "dudosas.csv").exists() else {}
    pack_rows = {r["ID"]: r for r in read(CATALOG / "packs" / f"{pack}.csv")}
    out: list[dict[str, object]] = []
    for m in matches:
        if m["EstadoNuevo"] == "verified":
            continue
        if mode == "ignore-year":
            if rescue_ignore_year(m):
                out.append({"csv_id": m["ID"], "track_id": m["SpotifyTrackId"], "isrc": m["ISRC"] or None,
                            "title": m["Cancion"], "album": m["Album"], "changed": False})
        else:
            pick = soundtrack_pick(m, doubts.get(m["ID"]), pack_rows[m["ID"]])
            if pick:
                tid, album, same = pick
                out.append({"csv_id": m["ID"], "track_id": tid, "isrc": (m["ISRC"] or None) if same else None,
                            "title": m["Cancion"], "album": album, "changed": not same})
    return out


UPDATE = """
    UPDATE songs SET spotify_track_id = :track_id, isrc = :isrc, year_status = 'verified', enabled = true,
                     updated_at = now()
    WHERE csv_id = :csv_id AND pack = :pack
"""


def write_db(pack: str, rows: list[dict[str, object]]) -> int:
    import asyncio

    sys.path.insert(0, str(CATALOG.parent / "apps" / "server"))
    imp.load_dotenv(CATALOG.parent / ".env")
    from app.config import AppConfig  # noqa: PLC0415
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    params = [{"csv_id": r["csv_id"], "track_id": r["track_id"], "isrc": r["isrc"], "pack": pack} for r in rows]

    async def run() -> int:
        engine = create_async_engine(AppConfig().database_url)
        async with engine.begin() as conn:
            res = await conn.execute(text(UPDATE), params)
            n = res.rowcount if res.rowcount and res.rowcount > 0 else len(params)
        await engine.dispose()
        return n

    return asyncio.run(run())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--mode", choices=("ignore-year", "soundtrack"), required=True)
    ap.add_argument("--write-db", action="store_true")
    args = ap.parse_args(argv)
    rows = plan(args.pack, args.mode)
    print(f"{args.pack} ({args.mode}): {len(rows)} canciones se habilitarian; "
          f"{sum(bool(r['changed']) for r in rows)} cambian de track_id.")
    for r in rows[:8]:
        print(f"  + {r['csv_id']} {str(r['title'])[:34]:34} | {str(r['album'])[:40]}{'  [otro track]' if r['changed'] else ''}")
    if args.write_db and rows:
        print(f"BD: {write_db(args.pack, rows)} filas actualizadas.")
    elif not args.write_db:
        print("(simulacion: no se escribe nada; añade --write-db para aplicar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
