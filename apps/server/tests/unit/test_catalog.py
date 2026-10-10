from pathlib import Path

from app.catalog.repo import CsvSongRepository, PostgresSongRepository, catalog_stats

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "songs.csv"


async def test_csv_filters_states_and_parses_aliases() -> None:
    songs = await CsvSongRepository(FIXTURE).load_enabled()
    titles = [s.title for s in songs]
    assert titles == ["Despacito", "Bohemian Rhapsody", "Billie Jean", "Hijo de la Luna", "Un año más"]
    by = {s.title: s for s in songs}
    assert by["Bohemian Rhapsody"].year == 1975  # empty Estado = verified
    assert by["Un año más"].title_aliases == ("Un ano mas", "Un año mas")
    assert by["Un año más"].note == "Single de 1988"
    assert by["Despacito"].artist == "Luis Fonsi, Daddy Yankee" and by["Despacito"].track_id == "tr001"
    assert len({s.id for s in songs}) == len(songs)


async def test_missing_csv_gives_empty_catalog(tmp_path: Path) -> None:
    assert await CsvSongRepository(tmp_path / "nope.csv").load_enabled() == []


async def test_stats() -> None:
    stats = catalog_stats(await CsvSongRepository(FIXTURE).load_enabled())
    assert stats["total"] == 5
    assert stats["by_decade"] == {"1970s": 1, "1980s": 3, "2010s": 1}
    assert stats["by_origin"] == {"es": 3, "intl": 2}


def test_postgres_row_mapping() -> None:
    row = {
        "id": 3,
        "csv_id": "X3",
        "title": "T",
        "artist": "A",
        "year": 1999,
        "spotify_track_id": None,
        "isrc": None,
        "title_aliases": ["t2"],
        "artist_aliases": None,
        "genre": None,
        "origin": "es",
        "year_note": None,
    }
    s = PostgresSongRepository.row_to_song(row)
    assert s.title_aliases == ("t2",) and s.artist_aliases == () and s.track_id == ""
