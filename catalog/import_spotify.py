#!/usr/bin/env python3
"""Importa el banco de canciones: busca cada fila de songs.csv en Spotify,
puntua candidatos, marca las dudosas y (opcional) verifica el anio con MusicBrainz.

Ver docs/DISENO.md, seccion 6 bis. El anio del CSV es la fuente de verdad: este
script NUNCA modifica la columna Anio, solo la contrasta y senala desajustes.

Uso:
    python import_spotify.py songs.csv --market ES --out review/ \
        [--only-pending] [--musicbrainz] [--write-csv]

Variables de entorno: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import os
import re
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

import httpx

CSV_HEADER = [
    "ID", "Cancion", "Artista", "Anio", "Genero", "Origen",
    "AliasTitulo", "AliasArtista", "Nota", "SpotifyTrackId", "ISRC", "Estado",
]

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"
MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/isrc/{isrc}"
MB_USER_AGENT = "HitsterCasero/0.1 (cremacuadrado@gmail.com)"

SEARCH_LIMIT = 10  # maximo actual de Spotify
MIN_RESULTS_BEFORE_FREE_SEARCH = 3
SPOTIFY_RATE = 3.0  # peticiones por segundo
MB_MIN_INTERVAL = 1.0  # segundos entre peticiones
MAX_RETRIES = 5
MAX_RETRY_AFTER = 300.0

CONFIDENCE_THRESHOLD = 0.75
AMBIGUITY_MARGIN = 0.05
ARTIST_MIN_SIM = 0.6  # con un artista distinto la formula puede pasar de 0.75 por titulo y anio
MB_MIN_TITLE_SIM = 0.85
RELAXED_MIN_CONFIDENCE = 0.9  # regla relajada: coincidencia clara basta para habilitar
VERSION_PENALTY = 0.3
COMPILATION_PENALTY = 0.15
ORIGINAL_BONUS = 0.1

# Patrones sobre texto sin tildes y en minusculas.
_RE_REMASTER = re.compile(
    r"remaster\w*|\bmono\b|\b(?:19|20)\d{2}\s+(?:remaster\w*|mix|edit|version)\b"
    r"|\b(?:remaster\w*|mix|edit|version)\s+(?:19|20)\d{2}\b"
)
_RE_LIVE = re.compile(r"\blive\b|en directo|en vivo|\bunplugged\b")
_RE_VERSION = re.compile(
    r"\bacoustic\b|\bacustic[oa]\b|\bversion\b|\bremix\b|\bedit\b|\bmix\b|\bdemo\b"
    r"|karaoke|instrumental|re-recorded|taylor's version"
)

VERSION_FLAGS = frozenset({"remaster", "live", "version"})


# --------------------------------------------------------------------------
# Texto y similitud (funciones puras)
# --------------------------------------------------------------------------

def fold(text: str) -> str:
    """Minusculas y sin tildes."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def normalize(text: str) -> str:
    """Minusculas, sin tildes ni puntuacion, espacios colapsados."""
    folded = fold(text).replace("&", " and ")
    folded = re.sub(r"[^a-z0-9]+", " ", folded)
    return folded.strip()


def base_title(title: str) -> str:
    """Quita sufijos tipo ' - Remastered 2011' y parentesis antes de comparar."""
    t = re.sub(r"\s+-\s+.*$", "", title)
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t)
    return t


def split_pipe(value: str) -> list[str]:
    return [p.strip() for p in (value or "").split("|") if p.strip()]


def split_artists(artist: str) -> list[str]:
    parts = re.split(r"\s*(?:&|,|/|\bfeat\.?|\bft\.?|\bfeaturing\b|\bx\b|\by\b)\s+", artist, flags=re.I)
    return [p.strip() for p in parts if p.strip()]


def ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def title_similarity(csv_titles: list[str], candidate_name: str) -> float:
    cand = normalize(base_title(candidate_name))
    best = 0.0
    for t in csv_titles:
        best = max(best, ratio(normalize(base_title(t)) or normalize(t), cand))
        best = max(best, ratio(normalize(t), normalize(candidate_name)))
    return best


def normalize_artist(text: str) -> str:
    """Como normalize, ignorando conectores (y, and, the)."""
    return " ".join(t for t in normalize(text).split() if t not in {"y", "and", "the"})


def artist_similarity(csv_artists: list[str], candidate_artists: list[str]) -> float:
    """Mejor similitud entre cualquier forma del artista del CSV y el artista
    principal o el conjunto de artistas del candidato."""
    if not candidate_artists:
        return 0.0
    cand_forms = {normalize_artist(candidate_artists[0]), normalize_artist(" ".join(candidate_artists))}
    cand_forms |= {normalize_artist(a) for a in candidate_artists}
    cand_forms.discard("")
    csv_forms: set[str] = set()
    for a in csv_artists:
        csv_forms.add(normalize_artist(a))
        csv_forms.update(normalize_artist(p) for p in split_artists(a))
    csv_forms.discard("")
    best = 0.0
    for c in csv_forms:
        for k in cand_forms:
            best = max(best, ratio(c, k))
    return best


def parse_year(date: str | None) -> int | None:
    if not date:
        return None
    m = re.match(r"^(\d{4})", date)
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------
# Modelo y puntuacion
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Candidate:
    track_id: str
    name: str
    artists: tuple[str, ...]
    album_name: str
    album_type: str
    release_date: str
    isrc: str = ""
    url: str = ""

    @property
    def album_year(self) -> int | None:
        return parse_year(self.release_date)


@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    score: float
    flags: tuple[str, ...]
    title_sim: float = 0.0
    artist_sim: float = 0.0


def parse_track(item: dict) -> Candidate:
    """Convierte un objeto track de la API de Spotify en Candidate."""
    album = item.get("album") or {}
    tid = item.get("id") or ""
    return Candidate(
        track_id=tid,
        name=item.get("name") or "",
        artists=tuple(a.get("name", "") for a in item.get("artists", [])),
        album_name=album.get("name") or "",
        album_type=album.get("album_type") or "",
        release_date=album.get("release_date") or "",
        isrc=((item.get("external_ids") or {}).get("isrc") or ""),
        url=(item.get("external_urls") or {}).get("spotify") or f"https://open.spotify.com/track/{tid}",
    )


def detect_flags(
    candidate: Candidate, csv_title: str, csv_year: int
) -> tuple[str, ...]:
    """Flags: remaster, live, version, compilation, year_mismatch.

    Una palabra clave no cuenta si ya aparece en el titulo del CSV (p. ej. una
    cancion que se llama 'Live and Let Die')."""
    own = fold(csv_title)
    text = fold(f"{candidate.name} || {candidate.album_name}")

    def hit(pattern: re.Pattern[str]) -> bool:
        return any(m.group(0) not in own for m in pattern.finditer(text))

    flags: list[str] = []
    if hit(_RE_REMASTER):
        flags.append("remaster")
    if hit(_RE_LIVE):
        flags.append("live")
    if hit(_RE_VERSION):
        flags.append("version")
    if candidate.album_type == "compilation":
        flags.append("compilation")
    year = candidate.album_year
    if year is None or abs(year - csv_year) >= 1:
        flags.append("year_mismatch")
    return tuple(flags)


def year_component(album_year: int | None, csv_year: int) -> float:
    if album_year is None:
        return 0.0
    diff = abs(album_year - csv_year)
    if diff == 0:
        return 1.0
    if diff <= 1:
        return 0.5
    return 0.0


def score_candidate(
    candidate: Candidate,
    title: str,
    artist: str,
    csv_year: int,
    alias_titles: list[str] | None = None,
    alias_artists: list[str] | None = None,
) -> Scored:
    """0.45*sim(titulo) + 0.35*sim(artista) + 0.20*anio, con penalizaciones y bonus."""
    t_sim = title_similarity([title, *(alias_titles or [])], candidate.name)
    a_sim = artist_similarity([artist, *(alias_artists or [])], list(candidate.artists))
    y = year_component(candidate.album_year, csv_year)
    score = 0.45 * t_sim + 0.35 * a_sim + 0.20 * y
    flags = detect_flags(candidate, title, csv_year)
    if VERSION_FLAGS & set(flags):
        score -= VERSION_PENALTY
    if "compilation" in flags:
        score -= COMPILATION_PENALTY
    if candidate.album_type in ("album", "single") and candidate.album_year == csv_year:
        score += ORIGINAL_BONUS
    return Scored(candidate, round(score, 4), flags, t_sim, a_sim)


def rank_candidates(
    candidates: list[Candidate],
    title: str,
    artist: str,
    csv_year: int,
    alias_titles: list[str] | None = None,
    alias_artists: list[str] | None = None,
) -> list[Scored]:
    seen: set[str] = set()
    scored: list[Scored] = []
    for c in candidates:
        if not c.track_id or c.track_id in seen:
            continue
        seen.add(c.track_id)
        scored.append(score_candidate(c, title, artist, csv_year, alias_titles, alias_artists))
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


@dataclass(frozen=True)
class Decision:
    best: Scored | None
    confidence: float
    doubtful: bool
    reasons: tuple[str, ...]

    @property
    def flags(self) -> tuple[str, ...]:
        return self.best.flags if self.best else ()


def decide(ranked: list[Scored]) -> Decision:
    """Dudosa si: sin resultados, confianza < 0.75, flags de version/recopilatorio,
    anio distinto, o el segundo candidato esta a menos de 0.05 (se ignoran los
    candidatos con el mismo ISRC que el mejor: es la misma grabacion en otro disco)."""
    if not ranked:
        return Decision(None, 0.0, True, ("no_match",))
    best = ranked[0]
    confidence = max(0.0, min(1.0, best.score))
    reasons: list[str] = []
    if confidence < CONFIDENCE_THRESHOLD:
        reasons.append("low_confidence")
    if best.artist_sim < ARTIST_MIN_SIM and "low_confidence" not in reasons:
        reasons.append("low_confidence")
    reasons.extend(f for f in best.flags if f in VERSION_FLAGS | {"compilation"})
    if "year_mismatch" in best.flags:
        reasons.append("year_mismatch")
    for other in ranked[1:]:
        same_recording = bool(best.candidate.isrc) and other.candidate.isrc == best.candidate.isrc
        if same_recording:
            continue
        if best.score - other.score < AMBIGUITY_MARGIN:
            reasons.append("ambiguous")
        break
    return Decision(best, confidence, bool(reasons), tuple(reasons))


def year_status(
    curated_status: str,
    decision: Decision,
    csv_year: int,
    mb_year: int | None,
    strict: bool = False,
) -> tuple[str, str]:
    """Estado final ('verified' | 'disputed') y motivo.

    Regla relajada (por defecto): el anio lo fija la curacion del CSV. Spotify da el anio del album
    y MusicBrainz el de la primera edicion del ISRC, y ambos fallan con reediciones y recopilatorios.
    Basta con una coincidencia clara: titulo y artista parecidos, confianza >= 0.9 y que no sea
    directo ni version. Los desajustes de anio no bloquean; quedan en desajustes_anio.csv.

    Regla estricta (strict=True): ademas exige que Spotify o MusicBrainz confirmen el anio.

    - Una fila que la persona curadora marco como 'disputed' nunca se promociona.
    - Sin MusicBrainz: verified solo si la coincidencia no es dudosa.
    - Con MusicBrainz: verified si MB coincide con el CSV y Spotify coincide, o
      Spotify es posterior con flag de remaster/recopilatorio (lo esperado).
    """
    if curated_status != "verified":
        return "disputed", "marcada como disputed en el CSV"
    if decision.best is None:
        return "disputed", "sin coincidencia en Spotify"
    flags = set(decision.flags)
    best = decision.best
    if not strict:
        if flags & {"live", "version"}:
            return "disputed", "directo, version o remix"
        if best.title_sim < MB_MIN_TITLE_SIM or best.artist_sim < ARTIST_MIN_SIM:
            return "disputed", "titulo o artista no coinciden"
        if decision.confidence < RELAXED_MIN_CONFIDENCE:
            return "disputed", f"confianza {decision.confidence:.2f} < {RELAXED_MIN_CONFIDENCE}"
        return "verified", ""
    if mb_year is None and "low_confidence" in decision.reasons:
        return "disputed", "confianza baja"
    if mb_year is not None and (best.title_sim < MB_MIN_TITLE_SIM or best.artist_sim < ARTIST_MIN_SIM):
        return "disputed", "titulo o artista no coinciden"
    if "ambiguous" in decision.reasons:
        return "disputed", "candidatos ambiguos"
    if flags & {"live", "version"}:
        return "disputed", "directo, version o remix"
    sp_year = decision.best.candidate.album_year
    if mb_year is None:
        if decision.doubtful:
            return "disputed", ",".join(decision.reasons)
        return "verified", ""
    if mb_year != csv_year:
        return "disputed", f"MusicBrainz dice {mb_year}"
    if sp_year == csv_year:
        return "verified", ""
    if sp_year is not None and sp_year > csv_year and flags & {"remaster", "compilation"}:
        return "verified", ""
    return "disputed", f"el anio de Spotify ({sp_year}) no cuadra"


# --------------------------------------------------------------------------
# Esperas, reintentos y clientes HTTP
# --------------------------------------------------------------------------

def parse_retry_after(value: str | None, default: float = 1.0) -> float:
    try:
        wait = float(value) if value is not None else default
    except ValueError:
        return default
    return max(0.0, wait)


class RateLimitError(RuntimeError):
    pass


class Throttle:
    """Garantiza un intervalo minimo entre peticiones."""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            remaining = self.min_interval - (now - self._last)
            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()
        self._last = now


def request_with_retry(
    http: httpx.Client,
    method: str,
    url: str,
    *,
    sleep: Callable[[float], None],
    throttle: Throttle | None = None,
    on_unauthorized: Callable[[], dict[str, str]] | None = None,
    **kwargs,
) -> httpx.Response:
    """Peticion que respeta 429 con Retry-After y reintenta 5xx puntuales."""
    refreshed = False
    for attempt in range(MAX_RETRIES + 1):
        if throttle:
            throttle.wait()
        resp = http.request(method, url, **kwargs)
        if resp.status_code == 429:
            wait = parse_retry_after(resp.headers.get("Retry-After"))
            if wait > MAX_RETRY_AFTER:
                raise RateLimitError(f"Retry-After de {wait:.0f}s en {url}; abortando")
            sleep(wait)
            continue
        if resp.status_code == 401 and on_unauthorized and not refreshed:
            refreshed = True
            kwargs["headers"] = {**kwargs.get("headers", {}), **on_unauthorized()}
            continue
        if resp.status_code in (502, 503, 504) and attempt < MAX_RETRIES:
            sleep(min(2 ** attempt, 30))
            continue
        return resp
    raise RateLimitError(f"demasiados reintentos en {url}")


class SpotifyLike(Protocol):
    def search_candidates(self, title: str, artist: str) -> list[Candidate]: ...


class MusicBrainzLike(Protocol):
    def first_release(self, isrc: str) -> str | None: ...


class SpotifyClient:
    """Client Credentials + busqueda."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        market: str = "ES",
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.market = market
        self.http = http or httpx.Client(timeout=20.0)
        self.sleep = sleep
        self.throttle = Throttle(1.0 / SPOTIFY_RATE, clock, sleep)
        self._token: str | None = None

    def _fetch_token(self) -> str:
        resp = request_with_retry(
            self.http, "POST", SPOTIFY_TOKEN_URL, sleep=self.sleep,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        token = self._token or self._fetch_token()
        return {"Authorization": f"Bearer {token}"}

    def _refresh_headers(self) -> dict[str, str]:
        self._token = None
        return self._auth_headers()

    def search(self, query: str) -> list[Candidate]:
        resp = request_with_retry(
            self.http, "GET", SPOTIFY_SEARCH_URL, sleep=self.sleep, throttle=self.throttle,
            on_unauthorized=self._refresh_headers,
            headers=self._auth_headers(),
            params={"q": query, "type": "track", "market": self.market, "limit": SEARCH_LIMIT},
        )
        resp.raise_for_status()
        items = (resp.json().get("tracks") or {}).get("items") or []
        return [parse_track(i) for i in items if i]

    def search_candidates(self, title: str, artist: str) -> list[Candidate]:
        main_artist = (split_artists(artist) or [artist])[0]
        clean = lambda s: s.replace('"', " ")
        results = self.search(f'track:"{clean(title)}" artist:"{clean(main_artist)}"')
        if len(results) < MIN_RESULTS_BEFORE_FREE_SEARCH:
            results = results + self.search(f"{title} {artist}")
        return results


def parse_mb_first_release(payload: dict) -> str | None:
    """Fecha mas antigua (YYYY[-MM[-DD]]) entre las grabaciones del ISRC."""
    dates: list[str] = []
    for rec in payload.get("recordings", []) or []:
        d = rec.get("first-release-date")
        if d:
            dates.append(d)
        for rel in rec.get("releases", []) or []:
            if rel.get("date"):
                dates.append(rel["date"])
    dates = [d for d in dates if re.match(r"^\d{4}", d)]
    return min(dates) if dates else None


class MusicBrainzClient:
    def __init__(
        self,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.http = http or httpx.Client(timeout=30.0)
        self.sleep = sleep
        self.throttle = Throttle(MB_MIN_INTERVAL, clock, sleep)

    def first_release(self, isrc: str) -> str | None:
        if not isrc:
            return None
        try:
            resp = request_with_retry(
                self.http, "GET", MUSICBRAINZ_URL.format(isrc=isrc), sleep=self.sleep,
                throttle=self.throttle,
                headers={"User-Agent": MB_USER_AGENT, "Accept": "application/json"},
                params={"inc": "releases", "fmt": "json"},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # MusicBrainz es solo una verificación extra: un fallo puntual no debe abortar 180 canciones.
            print(f"  aviso: MusicBrainz no respondió para {isrc}: {exc}", file=sys.stderr)
            return None
        return parse_mb_first_release(resp.json())


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------

def read_songs(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != CSV_HEADER:
            raise ValueError(f"Cabecera inesperada en {path}: {reader.fieldnames}")
        return [dict(r) for r in reader]


def write_songs(path: Path, rows: list[dict[str, str]]) -> None:
    fd, tmp = tempfile.mkstemp(suffix=".csv", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_HEADER, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# --------------------------------------------------------------------------
# Proceso
# --------------------------------------------------------------------------

@dataclass
class RowResult:
    row: dict[str, str]
    ranked: list[Scored] = field(default_factory=list)
    decision: Decision | None = None
    mb_first_release: str | None = None
    status: str = "disputed"
    status_reason: str = ""
    skipped: bool = False

    @property
    def year_notes(self) -> list[str]:
        csv_year = int(self.row["Anio"])
        notes = []
        if self.decision and self.decision.best:
            y = self.decision.best.candidate.album_year
            if y is not None and y != csv_year:
                notes.append(f"spotify={y}")
        mb = parse_year(self.mb_first_release)
        if mb is not None and mb != csv_year:
            notes.append(f"musicbrainz={mb}")
        return notes


def process_rows(
    rows: list[dict[str, str]],
    spotify: SpotifyLike,
    mb: MusicBrainzLike | None = None,
    only_pending: bool = False,
    log: Callable[[str], None] = lambda s: None,
    strict: bool = False,
    skip_ids: frozenset[str] = frozenset(),
    results: list[RowResult] | None = None,
) -> list[RowResult]:
    """Procesa las filas. `skip_ids`: IDs ya resueltos (p. ej. en la BD) que no se vuelven a buscar.

    `results` permite recuperar lo ya procesado si una excepcion (RateLimitError) corta la ejecucion.
    """
    results = results if results is not None else []
    for n, row in enumerate(rows, 1):
        if (only_pending and row.get("SpotifyTrackId")) or row.get("ID") in skip_ids:
            results.append(RowResult(row=row, skipped=True, status=row.get("Estado", "")))
            continue
        csv_year = int(row["Anio"])
        title, artist = row["Cancion"], row["Artista"]
        cands = spotify.search_candidates(title, artist)
        ranked = rank_candidates(
            cands, title, artist, csv_year,
            split_pipe(row.get("AliasTitulo", "")), split_pipe(row.get("AliasArtista", "")),
        )
        decision = decide(ranked)
        mb_date = None
        if mb is not None and decision.best and decision.best.candidate.isrc:
            mb_date = mb.first_release(decision.best.candidate.isrc)
        status, reason = year_status(
            row.get("Estado", "verified"), decision, csv_year, parse_year(mb_date) if mb is not None else None,
            strict=strict,
        )
        res = RowResult(row, ranked, decision, mb_date, status, reason)
        results.append(res)
        log(f"[{n}/{len(rows)}] {row['ID']} {title} - {artist}: {status}"
            f" ({decision.confidence:.2f}{' ' + ','.join(decision.reasons) if decision.reasons else ''})")
    return results


def apply_results(rows: list[dict[str, str]], results: list[RowResult]) -> list[dict[str, str]]:
    """Copia de las filas con SpotifyTrackId, ISRC y Estado actualizados. Anio intacto."""
    out: list[dict[str, str]] = []
    for i, row in enumerate(rows):
        res = results[i] if i < len(results) else None
        if res is None:  # resultados parciales: las filas sin procesar quedan igual
            out.append(dict(row))
            continue
        new = dict(row)
        if not res.skipped:
            best = res.decision.best if res.decision else None
            new["SpotifyTrackId"] = best.candidate.track_id if best else ""
            new["ISRC"] = best.candidate.isrc if best else ""
            new["Estado"] = res.status
        out.append(new)
    return out


def build_db_updates(results: list[RowResult]) -> list[dict]:
    """Parámetros para actualizar la tabla `songs` por csv_id. No toca el año curado.

    `enabled` solo es true si el estado es verified y hay track_id: sin ID no se puede reproducir.
    """
    updates: list[dict] = []
    for res in results:
        if res.skipped:
            continue
        best = res.decision.best if res.decision else None
        track_id = best.candidate.track_id if best else ""
        updates.append({
            "csv_id": res.row["ID"],
            "track_id": track_id or None,
            "isrc": (best.candidate.isrc if best else "") or None,
            "album_date": (best.candidate.release_date if best else "") or None,
            "mb_date": res.mb_first_release or None,
            "confidence": float(res.decision.confidence) if res.decision else None,
            "flags": list(res.decision.flags) if res.decision else [],
            "status": res.status,
            "enabled": res.status == "verified" and bool(track_id),
        })
    return updates


UPDATE_SONGS_SQL = """
    UPDATE songs SET spotify_track_id = :track_id, isrc = :isrc, spotify_album_date = :album_date,
                     mb_first_release = :mb_date, match_confidence = :confidence, match_flags = :flags,
                     year_status = :status, enabled = :enabled, updated_at = now()
    WHERE csv_id = :csv_id
"""


def write_db(results: list[RowResult]) -> tuple[int, int]:
    """Actualiza `songs` en la base del .env (Neon). Devuelve (filas actualizadas, habilitadas)."""
    import asyncio

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "server"))
    from app.config import AppConfig  # noqa: PLC0415
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    updates = build_db_updates(results)

    async def run() -> int:
        engine = create_async_engine(AppConfig().database_url)
        async with engine.begin() as conn:
            res = await conn.execute(text(UPDATE_SONGS_SQL), updates)
            n = res.rowcount if res.rowcount and res.rowcount > 0 else len(updates)
        await engine.dispose()
        return n

    return asyncio.run(run()), sum(1 for u in updates if u["enabled"])


MATCH_COLUMNS = [
    "ID", "Cancion", "Artista", "Anio", "SpotifyTrackId", "ISRC", "Album", "AlbumFecha",
    "Confianza", "Flags", "MbPrimeraFecha", "EstadoCurado", "EstadoNuevo", "Motivo",
]
DOUBT_COLUMNS = ["ID", "Cancion", "Artista", "Anio", "Motivos", "EstadoNuevo"] + [
    f"C{i}_{k}" for i in (1, 2, 3) for k in ("Id", "Nombre", "Album", "Fecha", "Puntos", "Flags", "Enlace")
]
MISMATCH_COLUMNS = ["ID", "Cancion", "Artista", "AnioCsv", "Spotify", "MusicBrainz", "Nota"]


def _write(path: Path, columns: list[str], rows: list[list]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        w.writerows(rows)


def write_reports(results: list[RowResult], out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    matches, doubts, mismatches = [], [], []
    for r in results:
        if r.skipped:
            continue
        row = r.row
        best = r.decision.best if r.decision else None
        c = best.candidate if best else None
        matches.append([
            row["ID"], row["Cancion"], row["Artista"], row["Anio"],
            c.track_id if c else "", c.isrc if c else "", c.album_name if c else "",
            c.release_date if c else "", f"{r.decision.confidence:.2f}" if r.decision else "0.00",
            ",".join(best.flags) if best else "", r.mb_first_release or "",
            row.get("Estado", ""), r.status, r.status_reason,
        ])
        reasons = list(r.decision.reasons) if r.decision else []
        if r.status != "verified" or reasons:
            cells: list = []
            for s in r.ranked[:3]:
                cc = s.candidate
                cells += [cc.track_id, cc.name, cc.album_name, cc.release_date, s.score,
                          ",".join(s.flags), cc.url]
            cells += [""] * (21 - len(cells))
            doubts.append([row["ID"], row["Cancion"], row["Artista"], row["Anio"],
                           ";".join(reasons + ([r.status_reason] if r.status_reason else [])),
                           r.status, *cells])
        if r.year_notes:
            sp = best.candidate.album_year if best else ""
            mbv = parse_year(r.mb_first_release) or ""
            mismatches.append([row["ID"], row["Cancion"], row["Artista"], row["Anio"], sp, mbv,
                               "El CSV manda: revisar a mano; el script no cambia Anio"])
    _write(out_dir / "matches.csv", MATCH_COLUMNS, matches)
    _write(out_dir / "dudosas.csv", DOUBT_COLUMNS, doubts)
    _write(out_dir / "desajustes_anio.csv", MISMATCH_COLUMNS, mismatches)
    return {"processed": len(matches), "doubtful": len(doubts), "year_mismatch": len(mismatches)}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Importa songs.csv a Spotify y genera review/.")
    p.add_argument("csv", type=Path, help="ruta de songs.csv")
    p.add_argument("--market", default="ES")
    p.add_argument("--out", type=Path, default=Path("review"))
    p.add_argument("--only-pending", action="store_true", help="solo filas sin SpotifyTrackId")
    p.add_argument("--musicbrainz", action="store_true", help="verifica el anio por ISRC")
    p.add_argument("--write-csv", action="store_true",
                   help="reescribe SpotifyTrackId, ISRC y Estado (nunca Anio)")
    p.add_argument("--resume", action="store_true",
                   help="con --write-db: no vuelve a buscar las canciones que ya tienen spotify_track_id en la BD")
    p.add_argument("--strict-years", action="store_true",
                   help="exige que Spotify o MusicBrainz confirmen el anio (por defecto basta una coincidencia clara)")
    p.add_argument("--write-db", action="store_true",
                   help="actualiza la tabla songs de DATABASE_URL (track_id, ISRC, estado, enabled; nunca el anio). "
                        "Requiere el python de apps/server/.venv")
    return p


def load_dotenv(path: Path) -> None:
    """Carga CLAVE=valor del .env de la raíz sin pisar variables ya definidas en el entorno."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def ids_resolved_in_db() -> frozenset[str]:
    """csv_id de las canciones que ya tienen spotify_track_id en la base del .env."""
    import asyncio

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "server"))
    from app.config import AppConfig  # noqa: PLC0415
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    async def run() -> frozenset[str]:
        engine = create_async_engine(AppConfig().database_url)
        async with engine.connect() as conn:
            rows = (await conn.execute(text("SELECT csv_id FROM songs WHERE spotify_track_id IS NOT NULL"))).scalars().all()
        await engine.dispose()
        return frozenset(rows)

    return asyncio.run(run())


def use_system_certificates() -> None:
    """Usa los certificados de Windows/macOS si `truststore` está instalado.

    Hace falta tras un proxy corporativo que re-firma el HTTPS con su propia CA. La verificación
    sigue activa: solo cambia qué almacén de CA se consulta.
    """
    try:
        import truststore  # noqa: PLC0415
    except ImportError:
        return
    truststore.inject_into_ssl()


def main(argv: list[str] | None = None, spotify: SpotifyLike | None = None,
         mb: MusicBrainzLike | None = None) -> int:
    args = build_parser().parse_args(argv)
    if spotify is None:
        use_system_certificates()
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        cid, secret = os.environ.get("SPOTIFY_CLIENT_ID"), os.environ.get("SPOTIFY_CLIENT_SECRET")
        if not cid or not secret:
            print("Faltan SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET (en el entorno o en el .env de la raíz).", file=sys.stderr)
            return 2
        spotify = SpotifyClient(cid, secret, market=args.market)
    if args.musicbrainz and mb is None:
        mb = MusicBrainzClient()
    rows = read_songs(args.csv)
    skip_ids: frozenset[str] = frozenset()
    if args.resume:
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        skip_ids = ids_resolved_in_db()
        print(f"--resume: {len(skip_ids)} canciones ya resueltas en la BD, se saltan.")
    results: list[RowResult] = []
    interrupted: RateLimitError | None = None
    try:
        process_rows(rows, spotify, mb if args.musicbrainz else None,
                     only_pending=args.only_pending, log=print, strict=args.strict_years,
                     skip_ids=skip_ids, results=results)
    except RateLimitError as exc:
        # Spotify corta la ejecucion: se conserva y se guarda lo ya procesado.
        interrupted = exc
        done = sum(not r.skipped for r in results)
        print(f"AVISO: {exc}. Se guarda lo procesado ({done} canciones). "
              "Vuelve a ejecutar con --resume cuando pase el bloqueo.", file=sys.stderr)
    summary = write_reports(results, args.out)
    if args.write_csv:
        write_songs(args.csv, apply_results(rows, results))
    if args.write_db:
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        updated, enabled = write_db(results)
        print(f"BD actualizada: {updated} canciones, {enabled} habilitadas (verified con track_id).")
    print(f"Procesadas {summary['processed']}, dudosas {summary['doubtful']}, "
          f"desajustes de anio {summary['year_mismatch']}. Informes en {args.out}/")
    return 3 if interrupted else 0


if __name__ == "__main__":
    sys.exit(main())
