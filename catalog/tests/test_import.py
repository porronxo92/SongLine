"""Tests del importador y validacion de songs.csv. Sin red: httpx.MockTransport."""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

import httpx
import pytest

CATALOG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CATALOG))

import import_spotify as imp  # noqa: E402

SONGS_CSV = CATALOG / "songs.csv"


# ---------------------------------------------------------------- helpers

def cand(name="Wonderwall", artists=("Oasis",), album="(What's the Story) Morning Glory?",
         album_type="album", date="1995-10-02", isrc="GBAAA9500001", tid="t1") -> imp.Candidate:
    return imp.Candidate(tid, name, tuple(artists), album, album_type, date, isrc,
                         f"https://open.spotify.com/track/{tid}")


def spotify_item(tid, name, artist, album, album_type, date, isrc="X"):
    return {
        "id": tid, "name": name, "artists": [{"name": artist}],
        "album": {"name": album, "album_type": album_type, "release_date": date},
        "external_ids": {"isrc": isrc},
        "external_urls": {"spotify": f"https://open.spotify.com/track/{tid}"},
    }


class FakeSpotify:
    def __init__(self, table):
        self.table = table  # titulo -> lista de Candidate
        self.calls = []

    def search_candidates(self, title, artist):
        self.calls.append((title, artist))
        return self.table.get(title, [])


class FakeMB:
    def __init__(self, dates):
        self.dates = dates
        self.calls = []

    def first_release(self, isrc):
        self.calls.append(isrc)
        return self.dates.get(isrc)


# ---------------------------------------------------------------- texto

def test_normalize_and_title_similarity():
    assert imp.normalize("Y.M.C.A.") == "y m c a"
    assert imp.title_similarity(["Y.M.C.A.", "YMCA"], "YMCA") == 1.0
    assert imp.title_similarity(["Wonderwall"], "Wonderwall - Remastered 2014") == 1.0
    assert imp.title_similarity(["Cuídate"], "Cuidate") == 1.0


def test_artist_similarity_uses_aliases_and_parts():
    assert imp.artist_similarity(["Fito & Fitipaldis", "Fito"], ["Fito Y Fitipaldis"]) > 0.9
    assert imp.artist_similarity(["Queen & David Bowie"], ["Queen", "David Bowie"]) == 1.0
    assert imp.artist_similarity(["Nirvana"], ["Pink Floyd"]) < 0.4


# ---------------------------------------------------------------- flags

def test_flag_remaster_and_year_mismatch():
    c = cand(name="Wonderwall - Remastered", date="2014-10-06", album_type="compilation",
             album="Oasis Greatest")
    flags = imp.detect_flags(c, "Wonderwall", 1995)
    assert "remaster" in flags
    assert "compilation" in flags
    assert "year_mismatch" in flags


def test_flag_live():
    c = cand(name="Wonderwall - Live at Knebworth", album="Live Forever")
    assert "live" in imp.detect_flags(c, "Wonderwall", 1995)
    c2 = cand(name="Wonderwall (En Directo)")
    assert "live" in imp.detect_flags(c2, "Wonderwall", 1995)


def test_flag_version_and_taylors():
    assert "version" in imp.detect_flags(cand(name="Shake It Off (Taylor's Version)"), "Shake It Off", 2014)
    assert "version" in imp.detect_flags(cand(name="Toxic - Remix"), "Toxic", 1995)


def test_clean_original_has_no_flags():
    assert imp.detect_flags(cand(), "Wonderwall", 1995) == ()


def test_keyword_inside_csv_title_is_ignored():
    c = cand(name="Live and Let Die", artists=("Wings",), date="1973-06-01")
    assert "live" not in imp.detect_flags(c, "Live and Let Die", 1973)


def test_year_mismatch_only_when_year_differs():
    assert "year_mismatch" not in imp.detect_flags(cand(date="1995-01-01"), "Wonderwall", 1995)
    assert "year_mismatch" in imp.detect_flags(cand(date="1996-01-01"), "Wonderwall", 1995)
    assert "year_mismatch" in imp.detect_flags(cand(date=""), "Wonderwall", 1995)


# ---------------------------------------------------------------- puntuacion

def test_perfect_match_scores_with_bonus():
    s = imp.score_candidate(cand(), "Wonderwall", "Oasis", 1995)
    assert s.flags == ()
    assert s.score == pytest.approx(0.45 + 0.35 + 0.20 + 0.10)


def test_year_component_half_point_when_off_by_one():
    s = imp.score_candidate(cand(date="1996-05-05"), "Wonderwall", "Oasis", 1995)
    assert s.score == pytest.approx(0.45 + 0.35 + 0.10 - 0.0, abs=1e-3)  # 0.5*0.2, sin bonus
    assert "year_mismatch" in s.flags


def test_version_penalty_and_compilation_penalty():
    base = imp.score_candidate(cand(), "Wonderwall", "Oasis", 1995).score
    rem = imp.score_candidate(cand(name="Wonderwall - Remastered"), "Wonderwall", "Oasis", 1995).score
    comp = imp.score_candidate(cand(album_type="compilation"), "Wonderwall", "Oasis", 1995).score
    assert rem == pytest.approx(base - 0.3)
    assert comp == pytest.approx(base - 0.10 - 0.15)  # pierde el bonus y recibe la penalizacion


def test_original_ranks_above_remaster_and_live():
    ranked = imp.rank_candidates(
        [
            cand(name="Wonderwall - Remastered", tid="rem", date="2014-01-01", album_type="compilation"),
            cand(name="Wonderwall - Live", tid="live", album="Live"),
            cand(tid="orig"),
        ],
        "Wonderwall", "Oasis", 1995,
    )
    assert [r.candidate.track_id for r in ranked][0] == "orig"


def test_wrong_artist_scores_low():
    ranked = imp.rank_candidates([cand(artists=("Tributo Pop",))], "Wonderwall", "Oasis", 1995)
    assert ranked[0].score >= 0.75  # la formula sola lo dejaria pasar
    assert "low_confidence" in imp.decide(ranked).reasons


def test_rank_dedupes_by_track_id():
    ranked = imp.rank_candidates([cand(tid="a"), cand(tid="a")], "Wonderwall", "Oasis", 1995)
    assert len(ranked) == 1


# ---------------------------------------------------------------- decision

def test_decide_clean_match_is_not_doubtful():
    d = imp.decide(imp.rank_candidates([cand()], "Wonderwall", "Oasis", 1995))
    assert not d.doubtful and d.reasons == () and d.confidence == 1.0


def test_decide_no_results():
    d = imp.decide([])
    assert d.doubtful and d.reasons == ("no_match",) and d.best is None


def test_decide_remaster_year_mismatch_is_doubtful():
    ranked = imp.rank_candidates(
        [cand(name="Wonderwall - Remastered", date="2014-01-01")], "Wonderwall", "Oasis", 1995)
    d = imp.decide(ranked)
    assert d.doubtful
    assert {"remaster", "year_mismatch"} <= set(d.reasons)


def test_decide_low_confidence():
    d = imp.decide(imp.rank_candidates([cand(name="Otra cosa", artists=("Nadie",))],
                                       "Wonderwall", "Oasis", 1995))
    assert "low_confidence" in d.reasons


def test_decide_ambiguous_runner_up_with_other_isrc():
    ranked = imp.rank_candidates(
        [cand(tid="a", isrc="AAA"), cand(tid="b", isrc="BBB")], "Wonderwall", "Oasis", 1995)
    assert "ambiguous" in imp.decide(ranked).reasons


def test_decide_runner_up_same_isrc_is_not_ambiguous():
    ranked = imp.rank_candidates(
        [cand(tid="a", isrc="AAA"), cand(tid="b", isrc="AAA", album="Otro disco")],
        "Wonderwall", "Oasis", 1995)
    assert "ambiguous" not in imp.decide(ranked).reasons


# ---------------------------------------------------------------- estado

def _decision(c=None, **kw):
    ranked = imp.rank_candidates([c or cand()], "Wonderwall", "Oasis", 1995, **kw)
    return imp.decide(ranked)


def test_status_all_three_agree():
    assert imp.year_status("verified", _decision(), 1995, 1995)[0] == "verified"
    assert imp.year_status("verified", _decision(), 1995, None)[0] == "verified"


def test_status_musicbrainz_only_with_remaster_is_verified():
    d = _decision(cand(name="Wonderwall - Remastered", date="2014-01-01", album_type="compilation"))
    assert imp.year_status("verified", d, 1995, 1995)[0] == "verified"
    assert imp.year_status("verified", d, 1995, None)[0] == "disputed"


def test_status_musicbrainz_disagrees_or_curated_disputed():
    assert imp.year_status("verified", _decision(), 1995, 1996)[0] == "disputed"
    assert imp.year_status("disputed", _decision(), 1995, 1995)[0] == "disputed"
    assert imp.year_status("verified", imp.decide([]), 1995, None)[0] == "disputed"


def test_status_live_is_never_verified():
    d = _decision(cand(name="Wonderwall - Live"))
    assert imp.year_status("verified", d, 1995, 1995)[0] == "disputed"


# ---------------------------------------------------------------- HTTP simulado

def make_spotify(handler, sleeps):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return imp.SpotifyClient("id", "secret", "ES", http=http, sleep=sleeps.append,
                             clock=lambda: 0.0)


def test_search_params_and_free_search_fallback():
    seen = []

    def handler(req: httpx.Request):
        if req.url.host == "accounts.spotify.com":
            return httpx.Response(200, json={"access_token": "tok"})
        seen.append(dict(req.url.params))
        assert req.headers["Authorization"] == "Bearer tok"
        items = [spotify_item("a", "Wonderwall", "Oasis", "Morning Glory", "album", "1995-10-02")]
        return httpx.Response(200, json={"tracks": {"items": items}})

    sp = make_spotify(handler, [])
    res = sp.search_candidates("Wonderwall", "Oasis")
    assert len(seen) == 2  # estricta + libre porque hay menos de 3 resultados
    assert seen[0]["q"] == 'track:"Wonderwall" artist:"Oasis"'
    assert seen[0]["limit"] == "10" and seen[0]["market"] == "ES" and seen[0]["type"] == "track"
    assert seen[1]["q"] == "Wonderwall Oasis"
    assert res[0].isrc == "X" and res[0].album_year == 1995


def test_no_free_search_when_enough_results():
    calls = []

    def handler(req):
        if req.url.host == "accounts.spotify.com":
            return httpx.Response(200, json={"access_token": "tok"})
        calls.append(1)
        items = [spotify_item(str(i), "W", "O", "A", "album", "1995-01-01") for i in range(5)]
        return httpx.Response(200, json={"tracks": {"items": items}})

    make_spotify(handler, []).search_candidates("W", "O")
    assert len(calls) == 1


def test_429_respects_retry_after():
    attempts = {"n": 0}

    def handler(req):
        if req.url.host == "accounts.spotify.com":
            return httpx.Response(200, json={"access_token": "tok"})
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        items = [spotify_item(str(i), "W", "O", "A", "album", "1995-01-01") for i in range(4)]
        return httpx.Response(200, json={"tracks": {"items": items}})

    sleeps = []
    res = make_spotify(handler, sleeps).search("q")
    assert 7.0 in sleeps
    assert len(res) == 4


def test_429_with_huge_retry_after_aborts():
    def handler(req):
        if req.url.host == "accounts.spotify.com":
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(429, headers={"Retry-After": "86400"})

    with pytest.raises(imp.RateLimitError):
        make_spotify(handler, []).search("q")


def test_parse_retry_after():
    assert imp.parse_retry_after("3") == 3.0
    assert imp.parse_retry_after(None) == 1.0
    assert imp.parse_retry_after("abc") == 1.0


def test_throttle_spaces_requests():
    t = {"now": 0.0}
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        t["now"] += s

    th = imp.Throttle(1.0, clock=lambda: t["now"], sleep=sleep)
    th.wait()
    t["now"] += 0.25
    th.wait()
    assert sleeps == [pytest.approx(0.75)]


def test_musicbrainz_request_and_parse():
    seen = {}

    def handler(req: httpx.Request):
        seen["ua"] = req.headers["User-Agent"]
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"isrc": "X", "recordings": [
            {"first-release-date": "1995-10-02"}, {"first-release-date": "2014-09-30"}]})

    mb = imp.MusicBrainzClient(http=httpx.Client(transport=httpx.MockTransport(handler)),
                               sleep=lambda s: None, clock=lambda: 0.0)
    assert mb.first_release("GBAAA9500001") == "1995-10-02"
    assert seen["ua"] == "HitsterCasero/0.1 (cremacuadrado@gmail.com)"
    assert "/ws/2/isrc/GBAAA9500001" in seen["url"]


def test_musicbrainz_404_returns_none():
    mb = imp.MusicBrainzClient(
        http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))),
        sleep=lambda s: None, clock=lambda: 0.0)
    assert mb.first_release("ZZZ") is None


# ---------------------------------------------------------------- proceso y CSV

def make_rows():
    base = dict.fromkeys(imp.CSV_HEADER, "")
    r1 = {**base, "ID": "S001", "Cancion": "Wonderwall", "Artista": "Oasis", "Anio": "1995",
          "Genero": "rock", "Origen": "intl", "Estado": "verified"}
    r2 = {**base, "ID": "S002", "Cancion": "Nada", "Artista": "Nadie", "Anio": "1990",
          "Genero": "pop", "Origen": "es", "Estado": "verified"}
    r3 = {**base, "ID": "S003", "Cancion": "Creep", "Artista": "Radiohead", "Anio": "1992",
          "Genero": "rock", "Origen": "intl", "Estado": "verified", "SpotifyTrackId": "keep"}
    return [r1, r2, r3]


def test_process_write_csv_never_changes_year(tmp_path):
    rows = make_rows()
    sp = FakeSpotify({"Wonderwall": [cand(name="Wonderwall - Remastered", date="2014-01-01",
                                          album_type="compilation", isrc="ISRC1")]})
    mb = FakeMB({"ISRC1": "1995-10-02"})
    results = imp.process_rows(rows, sp, mb, only_pending=True)
    assert results[2].skipped and sp.calls == [("Wonderwall", "Oasis"), ("Nada", "Nadie")]
    assert results[0].status == "verified"      # MB coincide y Spotify es posterior con remaster
    assert results[1].status == "disputed"      # sin coincidencia
    out = imp.apply_results(rows, results)
    assert [r["Anio"] for r in out] == ["1995", "1990", "1992"]
    assert out[0]["SpotifyTrackId"] == "t1" and out[0]["ISRC"] == "ISRC1"
    assert out[1]["Estado"] == "disputed" and out[1]["SpotifyTrackId"] == ""
    assert out[2]["SpotifyTrackId"] == "keep" and out[2]["Estado"] == "verified"

    path = tmp_path / "songs.csv"
    imp.write_songs(path, out)
    assert imp.read_songs(path) == out


def test_reports_dudosas_top3_and_mismatch(tmp_path):
    rows = make_rows()[:1]
    sp = FakeSpotify({"Wonderwall": [
        cand(tid="a", name="Wonderwall - Remastered", date="2014-01-01", isrc="A"),
        cand(tid="b", name="Wonderwall - Live", date="1996-01-01", isrc="B"),
        cand(tid="c", name="Wonderwall (Demo)", date="1997-01-01", isrc="C"),
        cand(tid="d", name="Wonderwall Cover", artists=("Otro",), date="2000-01-01", isrc="D"),
    ]})
    results = imp.process_rows(rows, sp)
    summary = imp.write_reports(results, tmp_path)
    assert summary["doubtful"] == 1 and summary["year_mismatch"] == 1
    with open(tmp_path / "dudosas.csv", encoding="utf-8") as f:
        d = list(csv.DictReader(f))
    assert len(d) == 1
    assert d[0]["C1_Enlace"].startswith("https://open.spotify.com/track/")
    assert d[0]["C3_Id"] and d[0]["C2_Enlace"] and d[0]["C3_Enlace"]
    assert "year_mismatch" in d[0]["Motivos"]
    assert (tmp_path / "matches.csv").exists() and (tmp_path / "desajustes_anio.csv").exists()


def test_main_requires_credentials(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    assert imp.main([str(tmp_path / "x.csv")]) == 2


def test_main_end_to_end_with_fakes(tmp_path):
    path = tmp_path / "songs.csv"
    imp.write_songs(path, make_rows()[:1])
    sp = FakeSpotify({"Wonderwall": [cand(isrc="ISRC1")]})
    code = imp.main([str(path), "--out", str(tmp_path / "review"), "--write-csv"], spotify=sp)
    assert code == 0
    out = imp.read_songs(path)
    assert out[0]["SpotifyTrackId"] == "t1" and out[0]["Anio"] == "1995"
    assert (tmp_path / "review" / "dudosas.csv").exists()


# ---------------------------------------------------------------- songs.csv

TARGET = {1970: 25, 1980: 35, 1990: 35, 2000: 30, 2010: 35, 2020: 20}


@pytest.fixture(scope="module")
def songs():
    with open(SONGS_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        rows = list(reader)
    return header, rows


def test_songs_header_exact(songs):
    assert songs[0] == ["ID", "Cancion", "Artista", "Anio", "Genero", "Origen",
                        "AliasTitulo", "AliasArtista", "Nota", "SpotifyTrackId", "ISRC", "Estado"]


def test_songs_count_and_ids(songs):
    rows = songs[1]
    assert len(rows) == 180
    ids = [r["ID"] for r in rows]
    assert len(set(ids)) == 180
    assert ids == [f"S{i:03d}" for i in range(1, 181)]


def test_songs_years_and_decades(songs):
    rows = songs[1]
    years = [int(r["Anio"]) for r in rows]
    assert all(1970 <= y <= 2025 for y in years)
    by_decade = Counter(y // 10 * 10 for y in years)
    for decade, target in TARGET.items():
        assert abs(by_decade[decade] - target) <= 3, (decade, by_decade[decade], target)


def test_songs_max_three_per_artist(songs):
    counts = Counter(r["Artista"] for r in songs[1])
    assert max(counts.values()) <= 3, counts.most_common(3)


def test_songs_enums(songs):
    rows = songs[1]
    assert {r["Genero"] for r in rows} <= {"pop", "rock", "dance", "latin", "indie", "hiphop", "rnb"}
    assert {r["Origen"] for r in rows} <= {"es", "intl"}
    assert {r["Estado"] for r in rows} <= {"verified", "disputed"}
    es = sum(r["Origen"] == "es" for r in rows) / len(rows)
    assert 0.3 <= es <= 0.5


def test_songs_no_duplicates_and_notes(songs):
    rows = songs[1]
    keys = [(imp.normalize(r["Cancion"]), imp.normalize(r["Artista"])) for r in rows]
    assert len(set(keys)) == len(keys)
    for r in rows:
        assert r["Cancion"].strip() and r["Artista"].strip()
        if r["Estado"] == "disputed":
            assert r["Nota"].strip(), f"{r['ID']} disputed sin Nota"
        assert r["SpotifyTrackId"] == "" and r["ISRC"] == ""
