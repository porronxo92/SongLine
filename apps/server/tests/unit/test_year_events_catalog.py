"""Data boundary checks and graceful failure of the optional historical catalog."""

from collections import Counter
from datetime import date

import pytest
from pydantic import ValidationError

from app.catalog.repo import CsvSongRepository
from app.catalog.year_events import YEAR_EVENTS_PATH, attach_year_events, read_year_events, validate_events
from app.config import REPO_ROOT
from app.game.models import Song
from app.services import build_services
from tests.conftest import ListRepo, make_config


def event(**updates):
    return {"id": "hubble-launched", "year": 1990, "category": "science",
            "text": "Se lanza al espacio el telescopio Hubble.",
            "source_url": "https://example.org/hubble", "occurred_on": "1990-04-24", **updates}


@pytest.mark.parametrize("changes", [
    {"text": "El telescopio Hubble se lanza en 1990."}, {"category": "unknown"},
    {"occurred_on": "1989-04-24"}, {"source_url": "http://example.org"},
    {"year": 2099, "occurred_on": "2099-01-01"},
])
def test_invalid_events_cannot_enter_play(changes):
    with pytest.raises((ValueError, ValidationError)):
        validate_events([event(**changes)])


def test_duplicate_ids_rejected_and_year_attachment_does_not_touch_other_song_data():
    with pytest.raises(ValueError, match="duplicate"):
        validate_events([event(), event()])
    songs = [Song(id=1, title="One", artist="A", year=1990), Song(id=2, title="Two", artist="B", year=1899)]
    attached = attach_year_events(songs, validate_events([event()]))
    assert not songs[0].year_events
    assert attached[0].year_events[0].occurred_on == date(1990, 4, 24)
    assert attached[1].year_events == ()
    assert attached[0].model_dump(exclude={"year_events"}) == songs[0].model_dump(exclude={"year_events"})


async def test_bundled_catalog_covers_every_year_and_all_song_packs():
    events = read_year_events(YEAR_EVENTS_PATH)
    counts = Counter(e.year for e in events)
    assert set(counts) == set(range(1937, 2027))
    assert all(2 <= count <= 3 for count in counts.values())
    songs = await CsvSongRepository(REPO_ROOT / "catalog" / "songs.csv").load_enabled()
    assert min(s.year for s in songs) == 1937 and max(s.year for s in songs) == 2026
    assert all(song.year_events for song in attach_year_events(songs, events))


async def test_event_repository_failure_keeps_the_song_catalog_available():
    class BrokenEvents:
        async def load_enabled(self):
            raise RuntimeError("optional historical data unavailable")

        async def close(self):
            pass

    song = Song(id=1, title="One", artist="A", year=1990)
    svc = build_services(make_config(), repo=ListRepo((song,)), year_event_repo=BrokenEvents())
    try:
        assert await svc.reload_songs() == [song]
        assert svc.year_events == [] and svc.songs[0].year_events == ()
    finally:
        await svc.http.aclose()
        await svc.accounts.close()


async def test_empty_database_catalog_does_not_fall_back_to_bundled_clues():
    class DisabledEvents:
        async def load_enabled(self):
            return []

        async def close(self):
            pass

    song = Song(id=1, title="One", artist="A", year=1990)
    svc = build_services(make_config(), repo=ListRepo((song,)), year_event_repo=DisabledEvents())
    try:
        assert await svc.reload_songs() == [song]
        assert svc.year_events == []
    finally:
        await svc.http.aclose()
        await svc.accounts.close()
