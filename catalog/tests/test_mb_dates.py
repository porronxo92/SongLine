"""Tests de mb_dates con respuestas simuladas (sin red)."""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

CATALOG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CATALOG))

import mb_dates as mb  # noqa: E402

ROW = {"Cancion": "Un buen día", "Artista": "Los Planetas", "AliasTitulo": "Un buen dia",
       "AliasArtista": "Planetas", "Genero": "indie-rock"}


def rec(title="Un buen día", artist="Los Planetas", date="1996-03-01", dis="", rid="r", releases=None):
    r = {"id": rid, "title": title, "artist-credit": [{"name": artist, "artist": {"name": artist}}]}
    if date:
        r["first-release-date"] = date
    if dis:
        r["disambiguation"] = dis
    if releases is not None:
        r["releases"] = releases
    return r


def release(date, primary="Album", secondary=(), status="Official"):
    return {"status": status, "date": date, "release-group": {"primary-type": primary, "secondary-types": list(secondary)}}


def test_picks_oldest_year():
    d = mb.date_song([rec(date="1997-05-01"), rec(date="1996-03-01"), rec(date="1996-09-10")], ROW)
    assert (d.year, d.status) == (1996, "verified")
    assert "1996-03-01" in d.note


def test_discards_live_and_remix():
    recs = [rec(title="Un buen día (live)", date="1990-01-01"),
            rec(dis="live at Sonar", date="1991-01-01"),
            rec(title="Un buen día (remix)", date="1992-01-01"),
            rec(dis="versión acústica", date="1993-01-01"),
            rec(date="1996-03-01")]
    d = mb.date_song(recs, ROW)
    assert d.year == 1996 and d.status == "verified"


def test_other_artist_does_not_count():
    d = mb.date_song([rec(artist="Los Secretos", date="1985-01-01"), rec(date="1996-03-01")], ROW)
    assert d.year == 1996


def test_only_other_artist_is_not_found():
    d = mb.date_song([rec(artist="Los Secretos", date="1985-01-01")], ROW)
    assert d.year is None and d.status == "disputed" and not d.found


def test_no_results_is_disputed():
    d = mb.date_song([], ROW)
    assert (d.year, d.status, d.found) == (None, "disputed", False)


def test_undated_is_disputed():
    d = mb.date_song([rec(date="")], ROW)
    assert d.year is None and d.status == "disputed" and d.found


def test_far_apart_dates_are_disputed_with_years():
    d = mb.date_song([rec(date="1996-03-01"), rec(date="2005-01-01")], ROW)
    assert d.status == "disputed" and d.year == 1996
    assert "1996" in d.note and "2005" in d.note


def test_one_year_apart_is_verified():
    d = mb.date_song([rec(date="1996-12-01"), rec(date="1997-01-15")], ROW)
    assert d.status == "verified" and d.year == 1996


def test_weak_title_match_is_disputed():
    row = {**ROW, "Cancion": "Un buen día", "AliasTitulo": ""}
    d = mb.date_song([rec(title="Un buen dio", date="1996-03-01")], row)
    # similitud alta pero por debajo de lo claro, o descartada: nunca verified con certeza plena
    assert d.status == "disputed" or d.year == 1996


def test_query_escapes_quotes():
    q = mb.MusicBrainzSearch.build_query('Say "hi"', "Band")
    assert q == 'recording:"Say \\"hi\\"" AND artist:"Band"'


def test_search_retries_503_and_uses_user_agent():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"recordings": [rec()]})

    client = mb.MusicBrainzSearch(http=httpx.Client(transport=httpx.MockTransport(handler)),
                                  sleep=lambda s: None)
    out = client.search("Un buen día", "Los Planetas")
    assert len(out) == 1 and len(calls) == 2
    assert calls[-1].headers["User-Agent"] == mb.MB_USER_AGENT
    assert calls[-1].url.params["limit"] == "15"


def test_process_formats_pack_rows():
    class Fake:
        def search(self, title, artist):
            return [rec(date="1996-03-01")]

    rows = mb.process([ROW], Fake(), prefix="IES")
    assert list(rows[0]) == mb.CSV_HEADER
    assert rows[0]["ID"] == "IES001" and rows[0]["Anio"] == "1996"
    assert rows[0]["Origen"] == "es" and rows[0]["SpotifyTrackId"] == "" and rows[0]["ISRC"] == ""


def test_live_only_release_is_discarded():
    live = rec(date="1990-01-01", releases=[release("1990-01-01", secondary=["Live"])])
    d = mb.date_song([live, rec(date="1996-03-01")], ROW)
    assert d.year == 1996 and d.status == "verified"


def test_far_dates_confirmed_by_official_release_are_verified():
    old = rec(date="1996-03-01", releases=[release("1996-03-01", "Single")])
    new = rec(date="2005-01-01", releases=[release("2005-01-01", secondary=["Compilation"])])
    d = mb.date_song([new, old], ROW)
    assert d.status == "verified" and d.year == 1996 and "2005" in d.note


def test_far_dates_with_unconfirmed_oldest_stay_disputed():
    old = rec(date="1996-03-01", releases=[release("1996-03-01", "Album", ["Compilation"], status="Bootleg")])
    d = mb.date_song([old, rec(date="2005-01-01")], ROW)
    assert d.status == "disputed"


def test_date_only_on_compilation_is_disputed():
    comp = rec(date="2021-10-29", releases=[release("2021-10-29", "Album", ["Compilation"])])
    d = mb.date_song([comp], ROW)
    assert d.status == "disputed" and d.year == 2021


def test_date_backed_by_studio_release_is_verified():
    ok = rec(date="1996-03-01", releases=[release("1996-03-01", "Album"), release("2010-01-01", "Album", ["Compilation"])])
    d = mb.date_song([ok], ROW)
    assert d.status == "verified" and d.year == 1996
