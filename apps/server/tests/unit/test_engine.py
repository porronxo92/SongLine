from __future__ import annotations

import pytest

from app.game import commands as C
from app.game.commands import GameError
from app.game.engine import REVEAL_AUTO_S, REVEAL_MIN_S, reduce
from app.game.models import PauseReason, Phase, Room, new_room
from app.game.rules import slot_is_correct
from tests.helpers import fire, go, make_card, make_songs, rigged, setup_lobby, start_game, to_guessing


def err(room: Room, cmd: C.Command, now: float = 0.0) -> str:
    with pytest.raises(GameError) as e:
        reduce(room, cmd, now)
    return e.value.code


# ------------------------------------------------------------------ rules


def test_slot_rule_equal_years_valid_both_sides() -> None:
    years = [1980, 1990, 1990, 2000]
    assert slot_is_correct(years, 1, 1990)
    assert slot_is_correct(years, 2, 1990)
    assert slot_is_correct(years, 3, 1990)
    assert not slot_is_correct(years, 0, 1990)
    assert slot_is_correct(years, 0, 1970)
    assert slot_is_correct(years, 4, 2010)
    assert not slot_is_correct(years, 5, 2010)
    assert not slot_is_correct(years, -1, 2010)


# ------------------------------------------------------------------ lobby


def test_claim_slot_and_rules() -> None:
    room = new_room("0001", "h0", "Host")
    room, _ = reduce(room, C.ClaimSlot("h1", 1, "  Rojos  ", "#f00"), 0)
    assert room.teams[1].name == "Rojos" and room.teams[1].connected
    assert err(room, C.ClaimSlot("h2", 1, "X")) == "slot_taken"
    assert err(room, C.ClaimSlot("h2", 5, "X")) == "invalid_slot"
    assert err(room, C.ClaimSlot("h2", 1, "   ")) == "slot_taken"  # taken check comes first
    room, _ = reduce(room, C.UpdateSettings(0, {"team_count": 3}), 0)
    assert err(room, C.ClaimSlot("h0", 2, "X")) == "host_cannot_move"
    # a non-host moves to another free slot, freeing the old one
    room, _ = reduce(room, C.ClaimSlot("h1", 2, "Rojos"), 0)
    assert not room.teams[1].claimed and room.teams[2].claimed


def test_update_settings_guards() -> None:
    room = new_room("0001", "h0", "Host")
    room, _ = reduce(room, C.UpdateSettings(0, {"team_count": 4, "mode": "app", "target_cards": 7}), 0)
    assert len(room.teams) == 4 and room.settings.mode == "app" and room.settings.target_cards == 7
    assert err(room, C.UpdateSettings(1, {"mode": "voice"})) == "not_host"
    assert err(room, C.UpdateSettings(0, {"start_position_ms": 0})) == "invalid_settings"  # D9 fixed
    assert err(room, C.UpdateSettings(0, {"objection_cost": "on_fail"})) == "invalid_settings"  # D2
    assert err(room, C.UpdateSettings(0, {"team_count": 9})) == "invalid_settings"
    room, _ = reduce(room, C.ClaimSlot("h3", 3, "Cuatro"), 0)
    assert err(room, C.UpdateSettings(0, {"team_count": 2})) == "invalid_settings"


def test_kick_only_in_lobby_by_host() -> None:
    room = setup_lobby(3)
    assert err(room, C.Kick(1, 2)) == "not_host"
    assert err(room, C.Kick(0, 0)) == "invalid_slot"
    room2, fx = reduce(room, C.Kick(0, 2), 0)
    assert not room2.teams[2].claimed
    assert any(isinstance(e, C.SendTo) and e.type == "kicked" and e.slot == 2 for e in fx)
    started, _ = start_game(room, make_songs(), 1)
    assert err(started, C.Kick(0, 2)) in ("wrong_phase", "paused")  # D4: no kicks in game


def test_start_guards() -> None:
    songs = make_songs()
    room = new_room("0001", "h0", "Host")
    assert err(room, C.Start(1, songs, 1)) == "not_host"
    assert err(room, C.Start(0, songs, 1)) == "teams_incomplete"
    room, _ = reduce(room, C.ClaimSlot("h1", 1, "B"), 0)
    room, _ = reduce(room, C.Disconnected(1), 0)
    assert err(room, C.Start(0, songs, 1)) == "teams_offline"
    room, _ = reduce(room, C.Connected(1), 0)
    assert err(room, C.Start(0, songs, 1)) == "audio_not_ready"  # D1: needs sdk_ready+premium+unlocked
    room, _ = reduce(room, C.DeviceReady(0, "dev", "sdk", premium_ok=False), 0)
    assert err(room, C.Start(0, songs, 1)) == "audio_not_ready"
    room, _ = reduce(room, C.DeviceReady(0, "dev", "sdk", premium_ok=True), 0)
    assert err(room, C.Start(0, songs, 1)) == "audio_not_ready"  # still locked
    room, _ = reduce(room, C.AudioUnlocked(0), 0)
    assert err(room, C.Start(0, songs[:2], 1)) == "catalog_too_small"
    room, fx = reduce(room, C.Start(0, songs, 1), 0)
    assert room.phase == Phase.COUNTDOWN
    assert any(isinstance(e, C.Broadcast) and e.type == "countdown" for e in fx)
    assert err(room, C.Start(0, songs, 1)) == "wrong_phase"


def test_start_deals_one_initial_card_that_counts_and_spreads_years() -> None:
    room = setup_lobby(4)
    room, _ = reduce(room, C.Start(0, make_songs(60), 3), 0)
    assert all(len(t.timeline) == 1 for t in room.teams)  # D3
    years = sorted(t.timeline[0].year for t in room.teams)
    assert all(b - a >= 5 for a, b in zip(years, years[1:], strict=False))
    assert room.first_slot in range(4)
    ids = {c.song_id for t in room.teams for c in t.timeline} | {c.song_id for c in room.deck}
    assert len(ids) == 60


def test_audio_preview_source_allows_start_without_spotify() -> None:
    room = new_room("0001", "h0", "Host")
    room, _ = reduce(room, C.ClaimSlot("h1", 1, "B"), 0)
    room, _ = reduce(room, C.UpdateSettings(0, {"audio_source": "preview"}), 0)
    room, _ = reduce(room, C.DeviceReady(0, "x", "preview", premium_ok=False), 0)
    room, _ = reduce(room, C.AudioUnlocked(0), 0)
    room, _ = reduce(room, C.Start(0, make_songs(), 1), 0)
    assert room.phase == Phase.COUNTDOWN


def test_lobby_host_migration_after_30s() -> None:
    room = setup_lobby(3)
    room, fx = reduce(room, C.Disconnected(0), 10.0)
    assert not room.audio.sdk_ready
    assert any(isinstance(e, C.StartTimer) and e.name == "lobby_host" for e in fx)
    room, _ = reduce(room, fire(room, "lobby_host"), 40.0)
    assert room.host_slot == 1
    # reconnect before the timer cancels it
    room = setup_lobby(3)
    room, _ = reduce(room, C.Disconnected(0), 10.0)
    room, fx = reduce(room, C.Connected(0), 20.0)
    assert "lobby_host" not in room.timers and any(isinstance(e, C.CancelTimer) for e in fx)


# ------------------------------------------------------------------ turn flow


def test_countdown_then_turn_ready_and_draw() -> None:
    room = setup_lobby(2)
    room, _ = reduce(room, C.Start(0, make_songs(), 5), 100.0)
    assert room.timers["countdown"].deadline_ts == 103.0
    stale = C.TimerFired("countdown", "countdown#999")
    same, _ = reduce(room, stale, 103.0)
    assert same.phase == Phase.COUNTDOWN  # stale id ignored
    room, _ = reduce(room, fire(room, "countdown"), 103.0)
    assert room.phase == Phase.TURN_READY and room.turn is not None
    assert room.turn.team_slot == room.first_slot


def test_play_request_effects_and_guards() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)
    assert err(room, C.PlayRequest(1)) == "not_your_turn"
    assert err(room, C.PlayRequest(None)) == "not_your_turn"
    assert err(room, C.PlaceConfirm(0, 0)) == "wrong_phase"
    room2, fx = reduce(room, C.PlayRequest(0), now)
    assert room2.phase == Phase.PLACING
    plays = [e for e in fx if isinstance(e, C.SpotifyPlay)]
    assert len(plays) == 1 and plays[0].position_ms == 10_000 and plays[0].device_id == "dev"  # D1, D9
    cmds = [e for e in fx if isinstance(e, C.SendTo) and e.type == "audio_command"]
    assert cmds[0].slot == 0 and cmds[0].payload == {"action": "prepare"}  # to the host only
    # "Repetir": play_request again in PLACING
    room3, fx = reduce(room2, C.PlayRequest(0), now)
    assert room3.phase == Phase.PLACING and any(isinstance(e, C.SpotifyPlay) for e in fx)


def test_play_failures_fall_back_to_preview_after_two() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    room, _ = reduce(room, C.PlayRequest(0), now)
    iid = room.turn.card.instance_id  # type: ignore[union-attr]
    room, fx = reduce(room, C.PlayResult(iid, False, "device_gone"), now)
    assert room.turn.audio_source == "spotify" and any(isinstance(e, C.SpotifyPlay) for e in fx)  # retry
    room, fx = reduce(room, C.PlayResult(iid, False, "device_gone"), now)
    assert room.turn.audio_source == "preview"
    assert any(isinstance(e, C.SendTo) and e.payload == {"action": "play_preview"} for e in fx)
    # next turn starts on spotify again
    assert room.settings.audio_source == "spotify"
    # stale result ignored
    same, _ = reduce(room, C.PlayResult("other", False), now)
    assert same == room


def test_play_ok_arms_tap_check_and_asks_for_tap() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    room, _ = reduce(room, C.PlayRequest(0), now)
    room, fx = reduce(room, C.PlayResult(room.turn.card.instance_id, True), now)  # type: ignore[union-attr]
    assert any(isinstance(e, C.StartTimer) and e.name == "tap_check" and e.delay_s == 1.5 for e in fx)
    _, fx = reduce(room, fire(room, "tap_check"), now + 1.5)
    assert any(isinstance(e, C.SendTo) and e.payload == {"action": "tap_required"} for e in fx)
    room, _ = reduce(room, C.AudioReport(0, True), now)
    room, _ = reduce(room, C.PlayResult(room.turn.card.instance_id, True), now)  # type: ignore[union-attr]
    _, fx = reduce(room, fire(room, "tap_check"), now + 1.5)
    assert not any(isinstance(e, C.SendTo) for e in fx)  # already playing


def test_audio_report_broadcasts_status() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    assert err(room, C.AudioReport(1, True)) == "not_host"
    room, fx = reduce(room, C.AudioReport(0, True), now)
    assert room.audio.playing
    assert C.Broadcast("audio_status", {"playing": True, "source": "spotify"}) in fx


def test_place_preview_and_confirm_validation() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)
    room = go(room, now, C.PlayRequest(0))
    assert err(room, C.PlaceConfirm(1, 0)) == "not_your_turn"
    assert err(room, C.PlaceConfirm(0, 3)) == "invalid_index"
    assert err(room, C.PlaceConfirm(0, -1)) == "invalid_index"
    room, _ = reduce(room, C.PlacePreview(0, 2), now)
    assert room.turn.preview_index == 2  # type: ignore[union-attr]
    room, _ = reduce(room, C.PlaceConfirm(0, 1), now)
    assert room.phase == Phase.GUESSING and room.turn.placed_index == 1  # type: ignore[union-attr]


def test_guess_modes() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990, mode="voice")
    room = to_guessing(room, now, 1)
    assert err(room, C.GuessSubmit(0, "a", "b")) == "wrong_mode"
    assert err(room, C.VoiceConfirm(1)) == "not_your_turn"
    room, _ = reduce(room, C.VoiceConfirm(0), now)
    assert room.phase == Phase.REVEAL  # nobody has tokens
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990, mode="app")
    room = to_guessing(room, now, 1)
    assert err(room, C.VoiceConfirm(0)) == "wrong_mode"
    room, _ = reduce(room, C.GuessSubmit(0, "x" * 500, "y"), now)
    assert room.phase == Phase.REVEAL and len(room.turn.guess_title) == 120  # type: ignore[arg-type,union-attr]


# ------------------------------------------------------------------ objection: 4 combos


def objection_case(active_idx: int, obj_idx: int, line: list[int], year: int) -> Room:
    room, now = rigged({0: line, 1: [1985], 2: [2005]}, year, tokens={1: 1})
    room = to_guessing(room, now, active_idx)
    room, _ = reduce(room, C.VoiceConfirm(0), now)
    assert room.phase == Phase.OBJECTION
    assert room.timers["objection"].deadline_ts == now + 15
    room, _ = reduce(room, C.Objection(1, obj_idx), now + 3)
    assert room.phase == Phase.REVEAL
    return room


def test_objection_active_ok_objector_wrong() -> None:
    room = objection_case(1, 0, [1980, 2000], 1990)
    assert [c.year for c in room.teams[0].timeline] == [1980, 1990, 2000]
    assert room.teams[1].tokens == 0 and len(room.teams[1].timeline) == 1  # D2: token spent
    assert room.turn.result.outcome == "kept"  # type: ignore[union-attr]


def test_objection_active_ok_objector_also_ok_equal_years() -> None:
    room = objection_case(0, 2, [1990, 1990], 1990)
    assert len(room.teams[0].timeline) == 3  # the active line wins
    assert room.teams[1].tokens == 0 and len(room.teams[1].timeline) == 1
    assert room.turn.result.objection_ok is True  # type: ignore[union-attr]


def test_objection_active_wrong_objector_ok_steals() -> None:
    room = objection_case(0, 1, [1980, 2000], 1990)
    assert [c.year for c in room.teams[0].timeline] == [1980, 2000]
    assert [c.year for c in room.teams[1].timeline] == [1985, 1990]  # inserted at the right place
    assert room.teams[1].tokens == 0
    assert room.turn.result.outcome == "stolen" and room.turn.result.to_slot == 1  # type: ignore[union-attr]


def test_objection_both_wrong_discards() -> None:
    room = objection_case(0, 2, [1980, 2000], 1990)
    assert [c.year for c in room.teams[0].timeline] == [1980, 2000]
    assert len(room.teams[1].timeline) == 1
    assert room.teams[1].tokens == 0
    assert len(room.discard) == 1 and room.turn.result.outcome == "discarded"  # type: ignore[union-attr]


def test_objection_guards() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1985], 2: [2005]}, 1990, tokens={1: 1, 2: 0})
    room = to_guessing(room, now, 1)
    assert err(room, C.Objection(1, 0)) == "wrong_phase"  # not yet open
    room, _ = reduce(room, C.VoiceConfirm(0), now)
    assert err(room, C.Objection(0, 0)) == "not_allowed"  # the active team
    assert err(room, C.Objection(2, 0)) == "no_token"
    assert err(room, C.Objection(1, 1)) == "same_slot"  # same hueco as the active team
    assert err(room, C.Objection(1, 9)) == "invalid_index"
    assert err(room, C.ObjectionPass(2)) == "not_allowed"
    assert err(room, C.ObjectionPass(0)) == "not_allowed"


def test_late_objection_gets_objection_closed_and_no_token_spent() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1985], 2: [2005]}, 1990, tokens={1: 1, 2: 1})
    room = to_guessing(room, now, 1)
    room, _ = reduce(room, C.VoiceConfirm(0), now)
    room, _ = reduce(room, C.Objection(1, 0), now)
    assert err(room, C.Objection(2, 2)) == "objection_closed"
    assert room.teams[2].tokens == 1
    assert err(room, C.ObjectionPass(2)) == "objection_closed"


def test_objection_timer_and_all_pass() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1985], 2: [2005]}, 1990, tokens={1: 1, 2: 1})
    room = to_guessing(room, now, 1)
    room, _ = reduce(room, C.VoiceConfirm(0), now)
    # timer
    dl = room.timers["objection"].deadline_ts
    r2, _ = reduce(room, fire(room, "objection"), dl)
    assert r2.phase == Phase.REVEAL and r2.teams[1].tokens == 1
    # all pass
    room, _ = reduce(room, C.ObjectionPass(1), now + 1)
    assert room.phase == Phase.OBJECTION
    room, _ = reduce(room, C.ObjectionPass(2), now + 2)
    assert room.phase == Phase.REVEAL
    assert "objection" not in room.timers


# ------------------------------------------------------------------ tokens


def test_token_needs_slot_title_and_artist_voice() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    assert room.phase == Phase.REVEAL and room.teams[0].tokens == 0
    assert err(room, C.HonorClaim(1, True, True)) == "not_your_turn"
    room, _ = reduce(room, C.HonorClaim(0, True, False), now)
    assert room.teams[0].tokens == 0
    room, _ = reduce(room, C.HonorClaim(0, True, True), now)
    assert room.teams[0].tokens == 1
    room, _ = reduce(room, C.HonorClaim(0, False, True), now)  # correctable until leaving REVEAL
    assert room.teams[0].tokens == 0


def test_token_not_given_if_slot_wrong_even_if_title_and_artist_right() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)  # D5
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 0), C.VoiceConfirm(0))
    room, _ = reduce(room, C.HonorClaim(0, True, True), now)
    assert room.teams[0].tokens == 0


def test_token_app_mode_auto_and_accept_guess() -> None:
    card = make_card(500, 1990, title="Despacito", artist="Luis Fonsi")
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990, mode="app", mystery=card)
    room = to_guessing(room, now, 1)
    room, fx = reduce(room, C.GuessSubmit(0, "despasito", "luis fonsi"), now)
    assert room.teams[0].tokens == 1
    reveal = next(e for e in fx if isinstance(e, C.Broadcast) and e.type == "reveal")
    assert reveal.payload["guess_auto"]["title_ok"] is True
    assert err(room, C.HonorClaim(0, True, True)) == "wrong_mode"
    # wrong guess then "dar por bueno" by anyone
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990, mode="app", mystery=card)
    room = to_guessing(room, now, 1)
    room = go(room, now, C.GuessSubmit(0, "nada", "nadie"))
    assert room.teams[0].tokens == 0
    room, _ = reduce(room, C.AcceptGuess(1), now)
    assert room.teams[0].tokens == 1


def test_reveal_next_turn_min_wait_and_auto_timer() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    assert room.timers["reveal_auto"].deadline_ts == now + REVEAL_AUTO_S
    assert err(room, C.NextTurn(0), now + 1) == "too_early"
    assert err(room, C.NextTurn(1), now + 10) == "not_your_turn"
    r2, fx = reduce(room, C.NextTurn(0), now + REVEAL_MIN_S)
    assert r2.phase == Phase.TURN_READY and r2.turn.team_slot == 1  # type: ignore[union-attr]
    assert any(isinstance(e, C.Broadcast) and e.type == "turn_resolved" for e in fx)
    r3, _ = reduce(room, fire(room, "reveal_auto"), now + REVEAL_AUTO_S)
    assert r3.phase == Phase.TURN_READY and r3.turn.team_slot == 1  # type: ignore[union-attr]


# ------------------------------------------------------------------ end of game


def test_target_reached_ends_game() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990, target=3)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    room, fx = reduce(room, C.NextTurn(0), now + 6)
    assert room.phase == Phase.GAME_OVER and room.winners == [0] and room.game_over_reason == "target"
    assert any(isinstance(e, C.Broadcast) and e.type == "game_over" for e in fx)
    assert room.turn is None and "room_gc" in room.timers


def test_deck_exhausted_winner_by_cards_only_ties_shared() -> None:
    def finish(tokens: dict[int, int], lines: dict[int, list[int]]) -> Room:
        room, now = rigged(lines, 1995, tokens=tokens, deck_years=[])
        room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 0), C.VoiceConfirm(0))
        if room.phase == Phase.OBJECTION:
            room = go(room, now, C.ObjectionPass(1))
        room, _ = reduce(room, C.NextTurn(0), now + 6)
        return room

    # team 0 misses (placed wrong) -> keeps 2 cards; team 1 has 2: tie on cards, tokens do not break it
    room = finish({1: 2}, {0: [1980, 2000], 1: [1990, 1991]})
    assert room.phase == Phase.GAME_OVER and room.game_over_reason == "deck_exhausted"
    assert room.winners == [0, 1]
    room = finish({}, {0: [1980, 2000], 1: [1990, 1991]})
    assert room.winners == [0, 1]  # full tie is shared
    room = finish({}, {0: [1980, 2000], 1: [1990, 1991, 1992]})
    assert room.winners == [1]  # more cards


def test_empty_deck_at_turn_ready_is_game_over() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985, deck_years=[])
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    room, _ = reduce(room, C.NextTurn(0), now + 6)
    assert room.phase == Phase.GAME_OVER and room.game_over_reason == "deck_exhausted"


def test_deck_low_warning() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985, deck_years=[1970, 1971, 1972])
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    _, fx = reduce(room, C.NextTurn(0), now + 6)
    assert any(isinstance(e, C.Broadcast) and e.type == "deck_low" for e in fx)


def test_rematch_resets_without_repeating_songs() -> None:
    songs = make_songs(60)
    room = setup_lobby(2, target=3)
    room, now = start_game(room, songs, 11)
    first_game = {c.song_id for t in room.teams for c in t.timeline} | {room.turn.card.song_id}  # type: ignore[union-attr]
    # force the end
    room.teams[0].timeline += [make_card(i, 1990 + i) for i in range(2)]
    room.turn.team_slot = 0  # type: ignore[union-attr]
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 0), C.VoiceConfirm(0))
    room, _ = reduce(room, C.NextTurn(0), now + 6)
    assert room.phase == Phase.GAME_OVER
    assert err(room, C.Rematch(1)) == "not_host"
    room, _ = reduce(room, C.Rematch(0), now + 7)
    assert room.phase == Phase.LOBBY and all(not t.timeline for t in room.teams)
    assert all(t.claimed for t in room.teams) and room.audio.sdk_ready
    room, _ = reduce(room, C.Start(0, songs, 12), now + 8)
    second = {c.song_id for t in room.teams for c in t.timeline} | {c.song_id for c in room.deck}
    assert not (second & first_game)


# ------------------------------------------------------------------ pause / resume


def test_active_team_disconnect_pauses_and_reconnect_resumes() -> None:
    room, now = rigged({0: [1980], 1: [1980, 2000]}, 1990)
    room.turn.team_slot = 1  # type: ignore[union-attr]
    room = go(room, now, C.PlayRequest(1))
    room, fx = reduce(room, C.Disconnected(1), now + 1)
    assert room.phase == Phase.PAUSED and room.paused_from == Phase.PLACING
    assert room.pause.reason == PauseReason.TEAM_OFFLINE and room.pause.slot == 1  # type: ignore[union-attr]
    assert room.pause.deadline_ts == now + 1 + 60  # type: ignore[union-attr]
    assert "grace:1" in room.timers
    assert err(room, C.PlaceConfirm(1, 1)) == "paused"
    room, _ = reduce(room, C.Connected(1), now + 20)
    assert room.phase == Phase.PLACING and room.pause is None and "grace:1" not in room.timers


def test_non_active_disconnect_does_not_pause() -> None:
    room, now = rigged({0: [1980], 1: [1990], 2: [2000]}, 1985)
    room = go(room, now, C.PlayRequest(0), C.Disconnected(2))
    assert room.phase == Phase.PLACING


def test_grace_expiry_skips_turn_and_card_goes_to_bottom() -> None:
    room, now = rigged({0: [1980], 1: [1990], 2: [2000]}, 1985)
    room.turn.team_slot = 1  # type: ignore[union-attr]
    card_id = room.turn.card.instance_id  # type: ignore[union-attr]
    deck_before = len(room.deck)
    room = go(room, now, C.PlayRequest(1))
    room, _ = reduce(room, C.Disconnected(1), now)
    room, _ = reduce(room, fire(room, "grace:1"), now + 60)
    assert room.phase == Phase.TURN_READY and room.turn.team_slot == 2  # type: ignore[union-attr]
    assert room.deck[-1].instance_id == card_id
    assert len(room.deck) == deck_before  # one in, one drawn
    assert not room.pause


def test_turn_ready_for_offline_team_pauses_then_skips() -> None:
    room, now = rigged({0: [1980], 1: [1990], 2: [2000]}, 1985)
    room = go(room, now, C.Disconnected(1), C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    room, _ = reduce(room, C.NextTurn(0), now + 6)
    assert room.phase == Phase.PAUSED and room.pause.slot == 1  # type: ignore[union-attr]
    room, _ = reduce(room, fire(room, "grace:1"), now + 70)
    assert room.phase == Phase.TURN_READY and room.turn.team_slot == 2  # type: ignore[union-attr]


def test_audio_host_offline_pauses_without_skip_timer_and_needs_device_ready() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1))
    assert room.phase == Phase.GUESSING
    # host is team 0 and also the active team here
    room, _ = reduce(room, C.Disconnected(0), now + 1)
    assert room.phase == Phase.PAUSED
    assert room.pause.reason == PauseReason.AUDIO_HOST_OFFLINE  # type: ignore[union-attr]
    assert not any(n.startswith("grace") for n in room.timers)  # no skip timer
    room, _ = reduce(room, C.Connected(0), now + 100)
    assert room.phase == Phase.PAUSED  # connected but audio not ready yet
    room, _ = reduce(room, C.DeviceReady(0, "dev2", "sdk", premium_ok=True), now + 101)
    assert room.phase == Phase.PAUSED  # not unlocked
    room, _ = reduce(room, C.AudioUnlocked(0), now + 102)
    assert room.phase == Phase.GUESSING and room.audio.device_id == "dev2"


def test_audio_host_offline_other_team_active_then_both_return() -> None:
    room, now = rigged({0: [1980], 1: [1990], 2: [2000]}, 1985)
    room.turn.team_slot = 1  # type: ignore[union-attr]
    room = go(room, now, C.PlayRequest(1))
    room, _ = reduce(room, C.Disconnected(1), now)
    assert room.pause.reason == PauseReason.TEAM_OFFLINE  # type: ignore[union-attr]
    room, _ = reduce(room, C.Disconnected(0), now + 1)  # host drops too: audio wins, grace cancelled
    assert room.pause.reason == PauseReason.AUDIO_HOST_OFFLINE  # type: ignore[union-attr]
    assert "grace:1" not in room.timers
    room, _ = reduce(room, C.Connected(0), now + 2)
    room, _ = reduce(room, C.DeviceReady(0, "d", "sdk", premium_ok=True, unlock=True), now + 2)
    assert room.phase == Phase.PAUSED and room.pause.reason == PauseReason.TEAM_OFFLINE  # type: ignore[union-attr]
    room, _ = reduce(room, C.Connected(1), now + 3)
    assert room.phase == Phase.PLACING


def test_device_gone_pauses_game() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    room = go(room, now, C.PlayRequest(0))
    room, fx = reduce(room, C.AudioFailed(0, "device_gone"), now)
    assert room.phase == Phase.PAUSED
    assert any(isinstance(e, C.Broadcast) and e.type == "audio_error" for e in fx)


def test_pause_freezes_objection_timer_and_resumes_remaining() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1985], 2: [2005]}, 1990, tokens={1: 1})
    room = to_guessing(room, now, 1)
    room, _ = reduce(room, C.VoiceConfirm(0), now)  # objection until now+15
    room, fx = reduce(room, C.Disconnected(0), now + 5)  # host (slot 0) drops during OBJECTION
    assert room.phase == Phase.PAUSED and room.paused_from == Phase.OBJECTION
    assert "objection" not in room.timers and room.frozen["objection"] == pytest.approx(10.0)
    assert any(isinstance(e, C.CancelTimer) and e.name == "objection" for e in fx)
    room, _ = reduce(room, C.Connected(0), now + 500)
    room, _ = reduce(room, C.DeviceReady(0, "d", "sdk", premium_ok=True, unlock=True), now + 500)
    assert room.phase == Phase.OBJECTION
    assert room.timers["objection"].deadline_ts == pytest.approx(now + 510)


def test_restored_marks_everyone_offline_and_pauses() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    room = go(room, now, C.PlayRequest(0))
    room, _ = reduce(room, C.Restored(), now + 5)
    assert room.phase == Phase.PAUSED and not any(t.connected for t in room.teams)


# ------------------------------------------------------------------ misc


def test_reduce_is_pure_and_versions_increase() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)
    before = room.model_dump()
    new, _ = reduce(room, C.PlayRequest(0), now)
    assert room.model_dump() == before
    assert new.version == room.version + 1
    with pytest.raises(GameError):
        reduce(new, C.PlayRequest(1), now)
    same, fx = reduce(new, C.TimerFired("nope", "nope#1"), now)
    assert same.version == new.version and fx == []


def test_snapshot_roundtrip_json() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1))
    assert Room.model_validate_json(room.model_dump_json()) == room


def test_persist_effect_on_phase_change() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    _, fx = reduce(room, C.PlayRequest(0), now)
    assert any(isinstance(e, C.PersistSnapshot) for e in fx)
    room = go(room, now, C.PlayRequest(0))
    _, fx = reduce(room, C.PlacePreview(0, 1), now)
    assert not any(isinstance(e, C.PersistSnapshot) for e in fx)


def test_room_gc_timer_destroys() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1990, target=3)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    room, _ = reduce(room, C.NextTurn(0), now + 6)
    _, fx = reduce(room, fire(room, "room_gc"), now + 6 + 900)
    assert any(isinstance(e, C.DestroyRoom) for e in fx)


# ------------------------------------------------------------------ host ends the game


def _assert_ended(room: Room, fx: list[C.Effect]) -> None:
    assert room.phase == Phase.GAME_OVER and room.game_over_reason == "host_ended"
    assert room.turn is None and room.pause is None and room.paused_from is None
    assert set(room.timers) == {"room_gc"} and not room.frozen
    over = [e for e in fx if isinstance(e, C.Broadcast) and e.type == "game_over"]
    assert len(over) == 1 and over[0].payload["reason"] == "host_ended"


def test_end_game_countdown() -> None:
    room, _ = reduce(setup_lobby(3), C.Start(0, make_songs(), 5), 0)
    assert room.phase == Phase.COUNTDOWN
    room, fx = reduce(room, C.EndGame(0), 10.0)
    _assert_ended(room, fx)
    assert any(isinstance(e, C.CancelTimer) and e.name == "countdown" for e in fx)


def test_end_game_in_each_phase_discards_card_in_play() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1985, tokens={1: 1})
    mystery_id = room.turn.card.instance_id  # type: ignore[union-attr]
    snapshots = [("turn_ready", room)]
    room = go(room, now, C.PlayRequest(0))
    snapshots.append(("placing", room))
    room = go(room, now, C.PlaceConfirm(0, 1))
    snapshots.append(("guessing", room))
    room = go(room, now, C.VoiceConfirm(0))
    assert room.phase == Phase.OBJECTION
    snapshots.append(("objection", room))
    paused, _ = reduce(room, C.Disconnected(0), now)
    assert paused.phase == Phase.PAUSED
    snapshots.append(("paused", paused))
    for name, snap in snapshots:
        done, fx = reduce(snap, C.EndGame(0), now + 1)
        _assert_ended(done, fx)
        assert all(c.instance_id != mystery_id for t in done.teams for c in t.timeline), name
        assert [len(t.timeline) for t in done.teams] == [2, 1], name


def test_end_game_in_reveal_keeps_revealed_result() -> None:
    room, now = rigged({0: [1980, 2000], 1: [1990]}, 1985)
    room = go(room, now, C.PlayRequest(0), C.PlaceConfirm(0, 1), C.VoiceConfirm(0))
    assert room.phase == Phase.REVEAL
    room, fx = reduce(room, C.EndGame(0), now + 1)
    _assert_ended(room, fx)
    assert room.winners == [0]  # 3 cards vs 1


def test_end_game_stops_playing_audio() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    room = go(room, now, C.PlayRequest(0))
    room.audio.playing = True
    _, fx = reduce(room, C.EndGame(0), now + 1)
    assert any(isinstance(e, C.SpotifyPause) for e in fx)
    assert any(isinstance(e, C.SendTo) and e.payload == {"action": "stop"} for e in fx)


def test_end_game_rejections() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    assert err(room, C.EndGame(1)) == "not_host"
    assert err(room, C.EndGame(None)) == "not_host"
    assert err(setup_lobby(2), C.EndGame(0)) == "wrong_phase"
    over, _ = reduce(room, C.EndGame(0), now)
    assert err(over, C.EndGame(0)) == "wrong_phase"


def test_end_game_winners_by_cards_only_tokens_do_not_break_ties() -> None:
    def ended(lines: dict[int, list[int]], tokens: dict[int, int]) -> Room:
        room, now = rigged(lines, 1985, tokens=tokens)
        room, _ = reduce(room, C.EndGame(0), now)
        return room

    assert ended({0: [1980], 1: [1990, 1991]}, {}).winners == [1]
    assert ended({0: [1980, 1981], 1: [1990, 1991]}, {1: 1}).winners == [0, 1]
    assert ended({0: [1980, 1981], 1: [1990, 1991]}, {}).winners == [0, 1]


def test_rematch_after_end_game() -> None:
    room, now = rigged({0: [1980], 1: [1990]}, 1985)
    room, _ = reduce(room, C.EndGame(0), now)
    assert err(room, C.Rematch(1)) == "not_host"
    room, _ = reduce(room, C.Rematch(0), now + 1)
    assert room.phase == Phase.LOBBY and room.game_over_reason is None and not room.timers
