"""Anti-cheat: the card in play never reaches any viewer before REVEAL."""

from __future__ import annotations

import json
import re

import pytest

from app.game import commands as C
from app.game.engine import reduce
from app.game.models import Card, Phase, Room
from app.game.projection import project, view_json
from tests.helpers import go, make_card, rigged

SECRET = Card(
    instance_id="opaque_card_id",
    song_id=424242,
    title="ZZSecretTitleZZ",
    artist="ZZSecretArtistZZ",
    year=1966,
    track_id="TRKSECRET99",
    isrc="ISRCSECRET01",
    title_aliases=("ZZAliasTitle",),
    artist_aliases=("ZZAliasArtist",),
    note="ZZSecretNote",
)
NOW = 1000.0
VIEWERS = [None, 0, 1, 2]


def assert_clean(room: Room) -> None:
    for v in VIEWERS:
        blob = json.dumps(view_json(room, v))
        for s in (
            "ZZSecretTitleZZ",
            "ZZSecretArtistZZ",
            "TRKSECRET99",
            "ISRCSECRET01",
            "ZZAlias",
            "ZZSecretNote",
        ):
            assert s not in blob, f"{s} leaked to viewer {v} in phase {room.phase}"
        assert not re.search(r"(?<![\w.])1966(?![\w.])", blob), f"year leaked to viewer {v} in {room.phase}"
        assert not re.search(r"(?<![\w.])424242(?![\w.])", blob), f"song_id leaked to viewer {v}"
        turn = view_json(room, v)["turn"]
        if turn is not None:
            assert turn["card"] == {"instanceId": "opaque_card_id", "hidden": True}


def base(mode: str = "voice") -> tuple[Room, float]:
    room, _ = rigged(
        {0: [1950 + 10 * i for i in range(3)], 1: [1985, 1995], 2: [2005]},
        1966,
        mode=mode,
        tokens={1: 1},
        mystery=SECRET,
    )
    return room, NOW


def test_hidden_in_every_phase_before_reveal_voice() -> None:
    room, now = base()
    assert room.phase == Phase.TURN_READY
    assert_clean(room)
    room = go(room, now, C.PlayRequest(0))
    assert_clean(room)
    room = go(room, now, C.PlacePreview(0, 2))
    assert_clean(room)
    paused, _ = reduce(room, C.Disconnected(0), now)
    assert paused.phase == Phase.PAUSED
    assert_clean(paused)
    room = go(room, now, C.PlaceConfirm(0, 2))
    assert room.phase == Phase.GUESSING
    assert_clean(room)
    room = go(room, now, C.VoiceConfirm(0))
    assert room.phase == Phase.OBJECTION
    assert_clean(room)
    paused, _ = reduce(room, C.Disconnected(0), now)
    assert_clean(paused)


def test_hidden_in_app_mode_with_wrong_guess() -> None:
    room, now = base("app")
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1))
    assert_clean(room)
    room = go(room, now, C.GuessSubmit(0, "algo distinto", "otro"))
    assert room.phase == Phase.OBJECTION
    assert_clean(room)


def test_countdown_and_lobby_have_no_turn() -> None:
    from tests.helpers import make_songs, setup_lobby

    room = setup_lobby(3)
    assert project(room, 0).turn is None
    room, _ = reduce(room, C.Start(0, make_songs(), 1), 0)
    assert project(room, 1).turn is None  # COUNTDOWN: nothing in play yet


def test_revealed_in_reveal_and_never_track_id_or_song_id() -> None:
    room, now = base()
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 2), C.VoiceConfirm(0))
    room = go(room, now, C.ObjectionPass(1))
    assert room.phase == Phase.REVEAL
    for v in VIEWERS:
        j = view_json(room, v)
        assert j["turn"]["card"]["title"] == "ZZSecretTitleZZ"
        assert j["turn"]["card"]["year"] == 1966
        blob = json.dumps(j)
        assert "TRKSECRET99" not in blob and "ISRCSECRET01" not in blob and "ZZAlias" not in blob
        assert not re.search(r"(?<![\w.])424242(?![\w.])", blob)


def test_pause_during_reveal_keeps_revealed() -> None:
    room, now = base()
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 2), C.VoiceConfirm(0), C.ObjectionPass(1))
    room, _ = reduce(room, C.Disconnected(0), now)
    assert room.phase == Phase.PAUSED
    assert view_json(room, 1)["turn"]["card"]["title"] == "ZZSecretTitleZZ"


def test_guess_visible_only_to_active_until_reveal() -> None:
    room, now = base("app")
    room.teams[1].tokens = 1
    room = go(
        room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.GuessSubmit(0, "mi respuesta", "mi artista")
    )
    assert room.phase == Phase.OBJECTION
    assert view_json(room, 0)["turn"]["guess"] == {"title": "mi respuesta", "artist": "mi artista"}
    for v in (None, 1, 2):
        assert view_json(room, v)["turn"]["guess"] is None
    room = go(room, now, C.ObjectionPass(1))
    assert view_json(room, 2)["turn"]["guess"]["title"] == "mi respuesta"


def test_you_and_deck_only_count() -> None:
    room, _ = base()
    v = view_json(room, 1)
    assert v["you"] == {"slot": 1, "isHost": False}
    assert view_json(room, 0)["you"]["isHost"] is True
    assert view_json(room, None)["you"] == {"slot": None, "isHost": False}
    assert isinstance(v["deckRemaining"], int) and "deck" not in v
    # other cards in the lines are public (they were already revealed)
    assert v["teams"][0]["timeline"][0]["year"] == 1950


@pytest.mark.parametrize("viewer", VIEWERS)
def test_game_over_view_has_standings(viewer: int | None) -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990], 2: [2005]}, 1990, target=3)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    room, _ = reduce(room, C.NextTurn(0), now + 6)
    j = view_json(room, viewer)
    assert j["phase"] == "game_over" and j["winners"] == [0] and j["turn"] is None
    assert j["standings"][0]["slot"] == 0 and j["gameOverReason"] == "target"


def test_make_card_helper_ids_unique() -> None:
    assert len({make_card(i, 1990).instance_id for i in range(100)}) == 100
