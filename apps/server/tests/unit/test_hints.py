"""Hints: mask_text properties, use_hint guards, the 60 s timer and the projection."""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.game import commands as C
from app.game.commands import GameError
from app.game.engine import HINT_FALLBACK_S, HINT_GRACE_S, HINT_LIMIT_S, reduce
from app.game.models import Card, Phase, Room
from app.game.projection import view_json
from app.game.rules import hint_seed, mask_text
from tests.helpers import fire, go, make_songs, rigged, setup_lobby

NOW = 1000.0
ARTIST = "Alejandro Sanz"
TITLE = "Corazón Partío"


def err(room: Room, cmd: C.Command, now: float = NOW) -> str:
    with pytest.raises(GameError) as e:
        reduce(room, cmd, now)
    return e.value.code


def mystery() -> Card:
    return Card(
        instance_id="inst_hint_1", song_id=777, title=TITLE, artist=ARTIST, year=1997, track_id="TRKHINT"
    )


def hint_room(mode: str = "voice", tokens: int = 2) -> Room:
    room, _ = rigged(
        {0: [1950, 1970, 1990], 1: [1985], 2: [2005]},
        1997,
        mode=mode,
        tokens={0: tokens, 1: 1},
        mystery=mystery(),
    )
    return room


def placing(mode: str = "voice", tokens: int = 2) -> Room:
    return go(hint_room(mode, tokens), NOW, C.PlayRequest(0))


# ------------------------------------------------------------------ mask_text


def _letters(s: str) -> list[str]:
    return [c for c in s if c.isalpha()]


texts = st.text(
    alphabet=st.sampled_from(list("abcdefghijklmnñopqrstuvwxyzáéíóúüABCDEFGHÑÁÉ 0123456789-.,!()&")),
    min_size=0,
    max_size=60,
)


@given(text=texts, seed=st.text(max_size=20))
def test_mask_is_deterministic_and_keeps_shape(text: str, seed: str) -> None:
    out = mask_text(text, seed)
    assert out == mask_text(text, seed)
    assert len(out) == len(text)
    for a, b in zip(text, out, strict=True):
        if not a.isalpha():
            assert a == b
        else:
            assert b in (a, "_")


@given(text=texts, seed=st.text(max_size=20))
def test_mask_hides_something_and_ratio_in_bounds(text: str, seed: str) -> None:
    out = mask_text(text, seed)
    letters = _letters(text)
    shown = sum(1 for a, b in zip(text, out, strict=True) if a.isalpha() and a == b)
    if len(letters) >= 2:
        assert "_" in out
        assert 0.25 <= shown / len(letters) <= 0.6
    else:
        assert out == text


@given(text=texts, seed=st.integers())
def test_mask_words_of_three_or_more_show_and_hide(text: str, seed: int) -> None:
    out = mask_text(text, seed)
    i = 0
    while i < len(text):
        if not text[i].isalpha():
            i += 1
            continue
        j = i
        while j < len(text) and text[j].isalpha():
            j += 1
        if j - i >= 3:
            word = out[i:j]
            assert "_" in word and any(c != "_" for c in word), (text, out)
        i = j


def test_mask_example_and_accents() -> None:
    out = mask_text(ARTIST, hint_seed("abc", "artist"))
    assert out[9] == " " and len(out) == len(ARTIST) and "_" in out
    out2 = mask_text(TITLE, 1)
    assert len(out2) == len(TITLE) and out2[7] == " "
    assert mask_text("1999", 3) == "1999"  # no letters: nothing to hide
    assert mask_text("a b", 3).count("_") >= 1  # two letters: something stays hidden


def test_mask_seed_is_per_kind() -> None:
    assert hint_seed("x", "artist") != hint_seed("x", "title")


# ------------------------------------------------------------------ use_hint


def test_use_hint_spends_token_sets_deadline_and_timer() -> None:
    room = placing()
    room2, fx = reduce(room, C.UseHint(0, "artist"), NOW)
    t = room2.turn
    assert t is not None
    assert room2.teams[0].tokens == 1
    assert t.hints_used == ["artist"] and t.hint_deadline_ts == NOW + HINT_LIMIT_S
    start = [e for e in fx if isinstance(e, C.StartTimer) and e.name == "hint"]
    assert len(start) == 1 and start[0].delay_s == HINT_LIMIT_S + HINT_GRACE_S
    note = [e for e in fx if isinstance(e, C.Broadcast) and e.type == "hint_used"]
    assert note and note[0].payload == {"slot": 0, "kind": "artist"}
    # the second hint costs another token and does not restart the timer
    room3, fx3 = reduce(room2, C.UseHint(0, "title"), NOW + 20)
    assert room3.teams[0].tokens == 0
    assert room3.turn is not None and room3.turn.hint_deadline_ts == NOW + HINT_LIMIT_S
    assert not [e for e in fx3 if isinstance(e, C.StartTimer)]


def test_use_hint_guards() -> None:
    room = hint_room()
    assert err(room, C.UseHint(0, "artist")) == "wrong_phase"  # TURN_READY
    room = go(room, NOW, C.PlayRequest(0))
    assert err(room, C.UseHint(1, "artist")) == "not_your_turn"
    assert err(room, C.UseHint(None, "artist")) == "not_your_turn"
    assert err(room, C.UseHint(0, "year")) == "bad_payload"
    h = go(room, NOW, C.UseHint(0, "artist"))
    assert err(h, C.UseHint(0, "artist")) == "hint_already_used"
    assert h.teams[0].tokens == 1  # a rejected hint costs nothing
    assert err(placing(tokens=0), C.UseHint(0, "title")) == "no_tokens"
    off = room.model_copy(deep=True)
    off.settings.hints_enabled = False
    assert err(off, C.UseHint(0, "artist")) == "hints_disabled"
    g = go(placing(), NOW, C.PlaceConfirm(0, 3), C.VoiceConfirm(0))
    assert g.phase == Phase.OBJECTION
    assert err(g, C.UseHint(0, "artist")) == "wrong_phase"


def test_use_hint_in_guessing_and_pause_rejected() -> None:
    g = go(placing(), NOW, C.PlaceConfirm(0, 3))
    assert g.phase == Phase.GUESSING
    g2 = go(g, NOW, C.UseHint(0, "title"))
    assert g2.teams[0].tokens == 1
    paused, _ = reduce(g2, C.Disconnected(0), NOW)
    assert paused.phase == Phase.PAUSED
    assert err(paused, C.UseHint(0, "artist")) == "paused"


# ------------------------------------------------------------------ timer


def test_timer_in_placing_confirms_preview_then_fallback_resolves() -> None:
    room = go(placing(), NOW, C.UseHint(0, "artist"), C.PlacePreview(0, 2))
    at = room.timers["hint"].deadline_ts
    assert at == NOW + HINT_LIMIT_S + HINT_GRACE_S
    room, _ = reduce(room, fire(room, "hint"), at)
    assert room.phase == Phase.GUESSING and room.turn is not None and room.turn.placed_index == 2
    assert room.turn.hint_deadline_ts == at + HINT_FALLBACK_S
    assert "hint" in room.timers  # the last window so the turn cannot stall
    at2 = room.timers["hint"].deadline_ts
    room, _ = reduce(room, fire(room, "hint"), at2)
    assert room.phase == Phase.OBJECTION  # voice_confirm equivalent (team 1 has a token)
    assert "hint" not in room.timers and room.turn is not None and room.turn.hint_deadline_ts is None


def test_timer_in_placing_without_preview_uses_center() -> None:
    room = go(placing(), NOW, C.UseHint(0, "title"))
    room, _ = reduce(room, fire(room, "hint"), room.timers["hint"].deadline_ts)
    assert room.turn is not None and room.turn.placed_index == len(room.teams[0].timeline) // 2


def test_timer_in_guessing_voice_and_app_modes() -> None:
    v = go(placing(), NOW, C.UseHint(0, "artist"), C.PlaceConfirm(0, 3))
    v, _ = reduce(v, fire(v, "hint"), v.timers["hint"].deadline_ts)
    assert v.phase == Phase.OBJECTION
    a = go(placing("app"), NOW, C.UseHint(0, "artist"), C.PlaceConfirm(0, 3))
    a, _ = reduce(a, fire(a, "hint"), a.timers["hint"].deadline_ts)
    assert a.phase == Phase.OBJECTION and a.turn is not None
    assert a.turn.guessed and a.turn.guess_title == "" and a.turn.guess_artist == ""
    # nobody can object: straight to reveal; the empty answer is a "no lo se" and gives no token
    a2 = go(placing("app"), NOW, C.UseHint(0, "artist"), C.PlaceConfirm(0, 3))
    a2.teams[1].tokens = 0
    a2, _ = reduce(a2, fire(a2, "hint"), a2.timers["hint"].deadline_ts)
    assert a2.phase == Phase.REVEAL and a2.turn is not None and not a2.turn.token_awarded
    assert not a2.turn.title_ok and not a2.turn.artist_ok


def test_timer_cancelled_when_leaving_guessing_and_stale_fire_ignored() -> None:
    g = go(placing(), NOW, C.UseHint(0, "artist"), C.PlaceConfirm(0, 3))
    ref = g.timers["hint"]
    done = go(g, NOW + 5, C.VoiceConfirm(0))
    assert "hint" not in done.timers and done.turn is not None and done.turn.hint_deadline_ts is None
    stale, fx = reduce(done, C.TimerFired("hint", ref.timer_id), NOW + 70)
    assert stale == done and not fx
    g.teams[1].tokens = 0  # nobody can object: straight to REVEAL
    rev = go(g, NOW + 5, C.VoiceConfirm(0))
    assert rev.phase == Phase.REVEAL and "hint" not in rev.timers
    nxt, _ = reduce(rev, C.NextTurn(0), NOW + 30)
    assert nxt.turn is not None and nxt.turn.hints_used == [] and "hint" not in nxt.timers


def test_timer_freezes_in_pause_and_resumes_with_remaining() -> None:
    room = go(placing(), NOW, C.UseHint(0, "artist"))
    room.host_slot = 1  # so that losing the active team pauses with a grace period (not the audio host)
    paused, fx = reduce(room, C.Disconnected(0), NOW + 20)
    assert paused.phase == Phase.PAUSED and "hint" not in paused.timers
    assert paused.frozen["hint"] == pytest.approx(HINT_LIMIT_S + HINT_GRACE_S - 20)
    assert any(isinstance(e, C.CancelTimer) and e.name == "hint" for e in fx)
    back, fx2 = reduce(paused, C.Connected(0), NOW + 500)
    assert back.phase == Phase.PLACING
    start = next(e for e in fx2 if isinstance(e, C.StartTimer) and e.name == "hint")
    assert start.delay_s == pytest.approx(HINT_LIMIT_S + HINT_GRACE_S - 20)
    assert back.turn is not None and back.turn.hint_deadline_ts == pytest.approx(NOW + 500 + HINT_LIMIT_S - 20)
    # a skipped turn (grace expired) drops the frozen timer
    grace = next(n for n in paused.timers if n.startswith("grace:"))
    skipped, _ = reduce(paused, fire(paused, grace), NOW + 100)
    assert "hint" not in skipped.frozen and "hint" not in skipped.timers


def test_tokens_are_not_refunded() -> None:
    room = go(
        placing(), NOW, C.UseHint(0, "artist"), C.UseHint(0, "title"), C.PlaceConfirm(0, 3), C.VoiceConfirm(0)
    )
    assert room.teams[0].tokens == 0
    room = go(room, NOW, C.ObjectionPass(1))
    assert room.phase == Phase.REVEAL
    assert room.teams[0].tokens == 0


def test_initial_tokens_setting_range_and_rematch() -> None:
    lobby = setup_lobby(3)
    for bad in (-1, 4, "x"):
        assert err(lobby, C.UpdateSettings(0, {"initial_tokens": bad})) == "invalid_settings"
    assert err(lobby, C.UpdateSettings(1, {"hints_enabled": False})) == "not_host"
    lobby, _ = reduce(lobby, C.UpdateSettings(0, {"initial_tokens": 3, "hints_enabled": False}), 0)
    assert lobby.settings.initial_tokens == 3 and not lobby.settings.hints_enabled
    started, _ = reduce(lobby, C.Start(0, make_songs(), 5), 100.0)
    assert all(t.tokens == 3 for t in started.teams)
    over, _ = reduce(started, C.EndGame(0), 101.0)
    over.teams[0].tokens = 0
    again, _ = reduce(over, C.Rematch(0), 102.0)
    assert all(t.tokens == 3 for t in again.teams)


def test_defaults() -> None:
    from app.game.models import Settings

    s = Settings()
    assert s.hints_enabled is True and s.initial_tokens == 1 and s.start_position_ms == 15_000


# ------------------------------------------------------------------ projection / anti-cheat

VIEWERS = [None, 0, 1, 2]


def test_masked_text_only_for_active_team_in_every_phase() -> None:
    room = hint_room()
    room.teams[2].tokens = 1
    r = go(room, NOW, C.PlayRequest(0), C.UseHint(0, "artist"), C.UseHint(0, "title"))
    r2 = go(r, NOW, C.PlaceConfirm(0, 3))
    r3 = go(r2, NOW, C.VoiceConfirm(0))
    stages = [
        r,
        r2,
        reduce(r2, C.Disconnected(0), NOW)[0],
        r3,
        reduce(r3, C.Disconnected(1), NOW)[0],
    ]
    want = {
        "artist": mask_text(ARTIST, hint_seed("inst_hint_1", "artist")),
        "title": mask_text(TITLE, hint_seed("inst_hint_1", "title")),
    }
    assert want["artist"] != ARTIST and want["title"] != TITLE
    for stage in stages:
        for v in VIEWERS:
            j = view_json(stage, v)
            blob = json.dumps(j, ensure_ascii=False)
            hints = j["turn"]["hints"]
            assert [h["kind"] for h in hints["used"]] == ["artist", "title"]
            if v == 0:
                assert {h["kind"]: h["masked"] for h in hints["used"]} == want
            else:
                assert all(set(h) == {"kind"} for h in hints["used"])
                assert "masked" not in blob
                assert want["artist"] not in blob and want["title"] not in blob
            assert ARTIST not in blob and TITLE not in blob


def test_one_kind_does_not_reveal_the_other() -> None:
    only_artist = go(placing(), NOW, C.UseHint(0, "artist"))
    own = view_json(only_artist, 0)["turn"]["hints"]
    assert [h["kind"] for h in own["used"]] == ["artist"]
    blob = json.dumps(own, ensure_ascii=False)
    title_mask = mask_text(TITLE, hint_seed("inst_hint_1", "title"))
    assert title_mask not in blob and "Corazón" not in blob and "Partío" not in blob
    # letters shown by the title mask are a different set from the artist mask: seeds differ per kind
    a = mask_text("x" * 30, hint_seed("inst_hint_1", "artist"))
    b = mask_text("x" * 30, hint_seed("inst_hint_1", "title"))
    assert a != b


def test_hints_view_shape_and_reveal_clears_it() -> None:
    room = placing()
    assert view_json(room, 1)["turn"]["hints"] == {"deadlineTs": None, "used": []}
    s = view_json(room, 0)["settings"]
    assert s["hintsEnabled"] is True and s["initialTokens"] == 0
    off = room.model_copy(deep=True)
    off.settings.hints_enabled = False
    assert view_json(off, 0)["turn"]["hints"] is None
    room = go(room, NOW, C.UseHint(0, "title"), C.PlaceConfirm(0, 3), C.VoiceConfirm(0), C.ObjectionPass(1))
    assert room.phase == Phase.REVEAL
    for v in VIEWERS:
        assert view_json(room, v)["turn"]["hints"] is None


def test_ephemeral_effects_never_carry_masked_text() -> None:
    room = placing()
    for kind in ("artist", "title"):
        _, fx = reduce(room, C.UseHint(0, kind), NOW)
        blob = json.dumps([e.payload for e in fx if isinstance(e, (C.Broadcast, C.SendTo))], ensure_ascii=False)
        assert "_" not in blob and "masked" not in blob and "Alejandro" not in blob


# ------------------------------------------------------------------ old snapshots


def test_old_snapshot_without_new_fields_still_loads() -> None:
    room = go(placing(), NOW, C.UseHint(0, "artist"))
    data = json.loads(room.model_dump_json())
    data["settings"].pop("hints_enabled")
    data["settings"].pop("initial_tokens")
    for k in ("hints_used", "hint_deadline_ts", "audio_commands", "audio_paused"):
        data["turn"].pop(k)
    old = Room.model_validate_json(json.dumps(data))
    assert old.settings.hints_enabled is True and old.settings.initial_tokens == 1
    assert old.turn is not None and old.turn.hints_used == [] and old.turn.hint_deadline_ts is None
    assert old.turn.audio_commands == 0 and old.turn.audio_paused is False
    again, _ = reduce(old, C.UseHint(0, "title"), NOW)
    assert again.turn is not None and again.turn.hints_used == ["title"]
