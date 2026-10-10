"""Pure state machine: reduce(room, command, now) -> (new_room, effects).

No I/O and no clock reads: `now` is injected (epoch seconds). Randomness comes from the seed in
`Start`. A rejected command raises GameError and leaves the caller's room untouched.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any, Literal

from pydantic import ValidationError

from app.game.commands import (
    AcceptGuess,
    AudioFailed,
    AudioReport,
    AudioUnlocked,
    Broadcast,
    CancelTimer,
    ClaimSlot,
    Command,
    Connected,
    DestroyRoom,
    DeviceReady,
    Disconnected,
    Effect,
    GameError,
    GuessSubmit,
    HonorClaim,
    Kick,
    NextTurn,
    Objection,
    ObjectionPass,
    PersistSnapshot,
    PlaceConfirm,
    PlacePreview,
    PlayRequest,
    PlayResult,
    Rematch,
    Restored,
    SendTo,
    SpotifyPause,
    SpotifyPlay,
    Start,
    StartTimer,
    TimerFired,
    UpdateSettings,
    VoiceConfirm,
)
from app.game.models import (
    EDITABLE_SETTINGS,
    Card,
    PauseInfo,
    PauseReason,
    Phase,
    Room,
    Settings,
    Team,
    TimerRef,
    Turn,
    TurnResult,
)
from app.game.projection import audio_ready, card_public, standings
from app.game.rules import (
    card_count,
    deal_initial,
    insert_sorted,
    line_slot_is_correct,
    pick_winners,
)
from app.game.validate_guess import validate_guess

COUNTDOWN_S = 3.0
REVEAL_MIN_S = 5.0
REVEAL_AUTO_S = 30.0
LOBBY_HOST_S = 30.0
TAP_CHECK_S = 1.5
GAME_OVER_GC_S = 900.0
DECK_LOW = 5
FREEZABLE = ("countdown", "objection", "reveal_auto", "tap_check")
IN_GAME = (
    Phase.COUNTDOWN,
    Phase.TURN_READY,
    Phase.PLACING,
    Phase.GUESSING,
    Phase.OBJECTION,
    Phase.REVEAL,
)
MAX_GUESS_LEN = 120

Fx = list[Effect]


# ------------------------------------------------------------------ helpers


def _require(room: Room, *phases: Phase) -> None:
    if room.phase == Phase.PAUSED:
        raise GameError("paused", "La partida esta en pausa")
    if room.phase not in phases:
        raise GameError("wrong_phase", f"No se puede hacer esto en la fase {room.phase}")


def _require_active(room: Room, sender: int | None) -> Turn:
    turn = room.turn
    if turn is None:
        raise GameError("wrong_phase", "No hay turno en curso")
    if sender is None or sender != turn.team_slot:
        raise GameError("not_your_turn", "No es tu turno")
    return turn


def _require_host(room: Room, sender: int | None) -> None:
    if sender is None or sender != room.host_slot:
        raise GameError("not_host", "Solo el anfitrion puede hacer esto")


def _start_timer(room: Room, fx: Fx, now: float, name: str, delay: float) -> float:
    room.timer_seq += 1
    tid = f"{name}#{room.timer_seq}"
    deadline = now + delay
    room.timers[name] = TimerRef(timer_id=tid, deadline_ts=deadline)
    fx.append(StartTimer(name, tid, delay))
    return deadline


def _cancel_timer(room: Room, fx: Fx, name: str) -> None:
    if name in room.timers:
        del room.timers[name]
        fx.append(CancelTimer(name))


def _cancel_all_timers(room: Room, fx: Fx) -> None:
    for name in list(room.timers):
        _cancel_timer(room, fx, name)
    room.frozen.clear()


def _host_hash(room: Room) -> str | None:
    return room.teams[room.host_slot].session_token_hash


def _reset_audio(room: Room) -> None:
    a = room.audio
    a.sdk_ready = False
    a.unlocked = False
    a.playing = False
    a.device_id = None
    a.provider = None


def _stop_audio(room: Room, fx: Fx) -> None:
    if room.audio.playing or (room.turn is not None and room.turn.started_playing):
        fx.append(SpotifyPause(room.audio.spotify_session_id, room.audio.device_id))
        fx.append(SendTo(room.host_slot, "audio_command", {"action": "stop"}))
    room.audio.playing = False


# ------------------------------------------------------------------ pause logic


def _pause_need(room: Room) -> tuple[PauseReason, int | None] | None:
    host = room.teams[room.host_slot]
    if not host.connected or not audio_ready(room):
        return (PauseReason.AUDIO_HOST_OFFLINE, None)
    ph = room.paused_from if room.phase == Phase.PAUSED else room.phase
    if ph in (Phase.TURN_READY, Phase.PLACING, Phase.GUESSING) and room.turn is not None:
        if not room.teams[room.turn.team_slot].connected:
            return (PauseReason.TEAM_OFFLINE, room.turn.team_slot)
    return None


def _cancel_graces(room: Room, fx: Fx) -> None:
    for name in [n for n in room.timers if n.startswith("grace:")]:
        _cancel_timer(room, fx, name)


def _set_pause(room: Room, fx: Fx, now: float, need: tuple[PauseReason, int | None]) -> None:
    reason, slot = need
    cur = room.pause
    if cur is not None and cur.reason == reason and cur.slot == slot:
        return
    _cancel_graces(room, fx)
    info = PauseInfo(reason=reason, slot=slot)
    if reason == PauseReason.TEAM_OFFLINE and slot is not None:
        info.deadline_ts = _start_timer(
            room, fx, now, f"grace:{slot}", float(room.settings.disconnect_grace_s)
        )
    room.pause = info


def _sync_pause(room: Room, fx: Fx, now: float) -> None:
    if room.phase not in (*IN_GAME, Phase.PAUSED):
        return
    need = _pause_need(room)
    if room.phase != Phase.PAUSED:
        if need is None:
            return
        room.paused_from = room.phase
        room.phase = Phase.PAUSED
        for name in FREEZABLE:
            ref = room.timers.get(name)
            if ref is not None:
                room.frozen[name] = max(0.0, ref.deadline_ts - now)
                _cancel_timer(room, fx, name)
        room.pause = None
        _set_pause(room, fx, now, need)
    elif need is None:
        _cancel_graces(room, fx)
        room.phase = room.paused_from or Phase.TURN_READY
        room.paused_from = None
        room.pause = None
        frozen, room.frozen = room.frozen, {}
        for name, remaining in frozen.items():
            deadline = _start_timer(room, fx, now, name, remaining)
            if name in ("objection", "reveal_auto") and room.turn is not None:
                room.turn.deadline_ts = deadline
    else:
        _set_pause(room, fx, now, need)


# ------------------------------------------------------------------ turn flow


def _enter_turn_ready(room: Room, fx: Fx, now: float, slot: int) -> None:
    room.audio.playing = False
    if not room.deck:
        _game_over(room, fx, now, "deck_exhausted")
        return
    card = room.deck.pop(0)
    if card.song_id not in room.used_song_ids:
        room.used_song_ids.append(card.song_id)
    room.turn = Turn(team_slot=slot, card=card, audio_source=room.settings.audio_source)
    room.phase = Phase.TURN_READY
    if len(room.deck) < DECK_LOW:
        fx.append(Broadcast("deck_low", {"remaining": len(room.deck)}))


def _game_over(room: Room, fx: Fx, now: float, reason: str) -> None:
    _cancel_all_timers(room, fx)
    room.phase = Phase.GAME_OVER
    room.paused_from = None
    room.pause = None
    room.game_over_reason = "target" if reason == "target" else "deck_exhausted"
    room.winners = pick_winners(
        room.teams, only_reached=room.settings.target_cards if reason == "target" else None
    )
    room.turn = None
    room.audio.playing = False
    _start_timer(room, fx, now, "room_gc", GAME_OVER_GC_S)
    fx.append(
        Broadcast(
            "game_over",
            {
                "winners": list(room.winners),
                "reason": room.game_over_reason,
                "standings": [s.model_dump(by_alias=True, mode="json") for s in standings(room)],
            },
        )
    )


def _eligible_objectors(room: Room) -> list[int]:
    assert room.turn is not None
    return [t.slot for t in room.teams if t.claimed and t.slot != room.turn.team_slot and t.tokens > 0]


def _after_guess(room: Room, fx: Fx, now: float) -> None:
    turn = room.turn
    assert turn is not None
    if _eligible_objectors(room):
        room.phase = Phase.OBJECTION
        turn.deadline_ts = _start_timer(room, fx, now, "objection", float(room.settings.objection_window_s))
    else:
        _reveal(room, fx, now)


def _recompute_token(room: Room) -> None:
    turn = room.turn
    assert turn is not None and turn.result is not None
    awarded = turn.result.placed_ok and turn.title_ok and turn.artist_ok  # D5
    active = room.teams[turn.team_slot]
    if awarded and not turn.token_awarded:
        active.tokens += 1
    elif not awarded and turn.token_awarded:
        active.tokens -= 1
    turn.token_awarded = awarded


def _reveal(room: Room, fx: Fx, now: float) -> None:
    turn = room.turn
    assert turn is not None
    _cancel_timer(room, fx, "objection")
    _cancel_timer(room, fx, "tap_check")
    card = turn.card
    active = room.teams[turn.team_slot]
    assert turn.placed_index is not None
    placed_ok = line_slot_is_correct(active.timeline, turn.placed_index, card.year)
    obj_ok: bool | None = None
    obj_slot: int | None = None
    if turn.objection is not None:
        obj_slot = turn.objection[0]
        obj_ok = line_slot_is_correct(active.timeline, turn.objection[1], card.year)
    outcome: Literal["kept", "stolen", "discarded"]
    to_slot: int | None
    if placed_ok:
        active.timeline.insert(turn.placed_index, card)
        outcome, to_slot = "kept", active.slot
    elif obj_slot is not None and obj_ok:
        insert_sorted(room.teams[obj_slot].timeline, card)
        outcome, to_slot = "stolen", obj_slot
    else:
        room.discard.append(card)
        outcome, to_slot = "discarded", None
    turn.result = TurnResult(
        placed_ok=placed_ok,
        objection_slot=obj_slot,
        objection_ok=obj_ok,
        outcome=outcome,
        to_slot=to_slot,
    )
    guess_auto: dict[str, Any] | None = None
    if room.settings.mode == "app" and turn.guessed:
        g = validate_guess(
            turn.guess_title or "",
            turn.guess_artist or "",
            card_title=card.title,
            card_artist=card.artist,
            title_aliases=card.title_aliases,
            artist_aliases=card.artist_aliases,
        )
        turn.title_ok, turn.artist_ok = g.title_ok, g.artist_ok
        guess_auto = {"title_ok": g.title_ok, "artist_ok": g.artist_ok, "score": g.score}
    _recompute_token(room)
    room.phase = Phase.REVEAL
    turn.deadline_ts = _start_timer(room, fx, now, "reveal_auto", REVEAL_AUTO_S)
    turn.reveal_at = now
    fx.append(
        Broadcast(
            "reveal",
            {
                "card": card_public(card).model_dump(by_alias=True, mode="json"),
                "correct_slot": placed_ok,
                "outcome": outcome,
                "to_slot": to_slot,
                "objection_result": (
                    {"slot": obj_slot, "index": turn.objection[1], "correct": obj_ok}
                    if turn.objection is not None and obj_slot is not None
                    else None
                ),
                "guess_auto": guess_auto,
                "reveal_unlocks_at": now + REVEAL_MIN_S,
            },
        )
    )


def _finish_turn(room: Room, fx: Fx, now: float) -> None:
    turn = room.turn
    assert turn is not None and turn.result is not None
    _cancel_timer(room, fx, "reveal_auto")
    _stop_audio(room, fx)
    delta = {str(turn.team_slot): 1 if turn.token_awarded else 0}
    if turn.objection is not None:
        delta[str(turn.objection[0])] = delta.get(str(turn.objection[0]), 0) - 1
    delta = {k: v for k, v in delta.items() if v != 0}
    fx.append(Broadcast("turn_resolved", {"to_slot": turn.result.to_slot, "token_delta": delta}))
    target = room.settings.target_cards
    if any(card_count(t) >= target for t in room.teams):
        _game_over(room, fx, now, "target")
        return
    nxt = (turn.team_slot + 1) % room.settings.team_count
    room.turn = None
    room.turn_no += 1
    _enter_turn_ready(room, fx, now, nxt)
    _sync_pause(room, fx, now)


def _skip_turn(room: Room, fx: Fx, now: float) -> None:
    turn = room.turn
    assert turn is not None
    room.deck.append(turn.card)  # back to the bottom of the deck
    _cancel_all_timers(room, fx)
    _stop_audio(room, fx)
    room.phase = room.paused_from or Phase.TURN_READY
    room.paused_from = None
    room.pause = None
    nxt = (turn.team_slot + 1) % room.settings.team_count
    room.turn = None
    room.turn_no += 1
    _enter_turn_ready(room, fx, now, nxt)
    _sync_pause(room, fx, now)


def _play(room: Room, fx: Fx) -> None:
    turn = room.turn
    assert turn is not None
    turn.started_playing = True
    room.audio.playing = False
    if room.settings.audio_source == "preview" or not room.audio.sdk_ready or room.audio.device_id is None:
        turn.audio_source = "preview"
    if turn.audio_source == "preview":
        fx.append(SendTo(room.host_slot, "audio_command", {"action": "play_preview"}))
        fx.append(Broadcast("audio_status", {"playing": False, "source": "preview"}))
    else:
        fx.append(
            SpotifyPlay(
                room.audio.spotify_session_id,
                room.audio.device_id,
                turn.card.track_id,
                room.settings.start_position_ms,
                turn.card.instance_id,
            )
        )
        fx.append(SendTo(room.host_slot, "audio_command", {"action": "prepare"}))


# ------------------------------------------------------------------ handlers


def _h_claim(room: Room, cmd: ClaimSlot, now: float, fx: Fx) -> None:
    if not 0 <= cmd.slot < len(room.teams):
        raise GameError("invalid_slot", "Hueco inexistente")
    existing = room.slot_of(cmd.session_hash)
    if room.phase != Phase.LOBBY and existing != cmd.slot:
        raise GameError("game_started", "La partida ya ha empezado")
    team = room.teams[cmd.slot]
    if team.claimed and team.session_token_hash != cmd.session_hash:
        raise GameError("slot_taken", "Ese hueco ya esta ocupado")
    name = " ".join(cmd.name.split())[:20]
    if not name:
        raise GameError("invalid_name", "Pon un nombre al equipo")
    if existing is not None and existing != cmd.slot:
        if existing == room.host_slot:
            raise GameError("host_cannot_move", "El anfitrion no puede cambiar de hueco")
        room.teams[existing] = Team(slot=existing)
    team.session_token_hash = cmd.session_hash
    team.name = name
    team.color = cmd.color[:16] if cmd.color else team.color
    team.connected = True


def _h_connected(room: Room, cmd: Connected, now: float, fx: Fx) -> None:
    if not 0 <= cmd.slot < len(room.teams) or not room.teams[cmd.slot].claimed:
        return
    room.teams[cmd.slot].connected = True
    if cmd.slot == room.host_slot:
        _cancel_timer(room, fx, "lobby_host")
    _sync_pause(room, fx, now)


def _h_disconnected(room: Room, cmd: Disconnected, now: float, fx: Fx) -> None:
    if not 0 <= cmd.slot < len(room.teams):
        return
    room.teams[cmd.slot].connected = False
    if cmd.slot == room.host_slot:
        _reset_audio(room)
        if room.phase == Phase.LOBBY:
            _start_timer(room, fx, now, "lobby_host", LOBBY_HOST_S)
    _sync_pause(room, fx, now)


def _h_restored(room: Room, cmd: Restored, now: float, fx: Fx) -> None:
    for t in room.teams:
        t.connected = False
    _reset_audio(room)
    if room.phase == Phase.LOBBY:
        _start_timer(room, fx, now, "lobby_host", LOBBY_HOST_S)
    _sync_pause(room, fx, now)


def _h_kick(room: Room, cmd: Kick, now: float, fx: Fx) -> None:
    _require(room, Phase.LOBBY)
    _require_host(room, cmd.sender)
    if cmd.slot == room.host_slot or not 0 <= cmd.slot < len(room.teams) or not room.teams[cmd.slot].claimed:
        raise GameError("invalid_slot", "No se puede expulsar ese hueco")
    fx.append(SendTo(cmd.slot, "kicked", {"reason": "host"}))
    room.teams[cmd.slot] = Team(slot=cmd.slot)


def _h_update_settings(room: Room, cmd: UpdateSettings, now: float, fx: Fx) -> None:
    _require(room, Phase.LOBBY)
    _require_host(room, cmd.sender)
    bad = set(cmd.changes) - EDITABLE_SETTINGS
    if bad:
        raise GameError("invalid_settings", f"Ajustes no editables: {sorted(bad)}")
    try:
        new = Settings.model_validate({**room.settings.model_dump(), **cmd.changes})
    except ValidationError as e:
        raise GameError("invalid_settings", "Ajustes no validos") from e
    highest = max((t.slot for t in room.teams if t.claimed), default=0)
    if new.team_count < highest + 1:
        raise GameError("invalid_settings", "Hay equipos en huecos que desaparecerian")
    if new.team_count < len(room.teams):
        del room.teams[new.team_count :]
    while len(room.teams) < new.team_count:
        room.teams.append(Team(slot=len(room.teams)))
    room.settings = new


def _h_start(room: Room, cmd: Start, now: float, fx: Fx) -> None:
    _require(room, Phase.LOBBY)
    _require_host(room, cmd.sender)
    if room.occupied != room.settings.team_count:
        raise GameError("teams_incomplete", "Faltan equipos por ocupar su hueco")
    if not all(t.connected for t in room.teams):
        raise GameError("teams_offline", "Hay equipos desconectados")
    if not audio_ready(room):
        raise GameError("audio_not_ready", "El audio del anfitrion no esta listo")
    n_teams = room.settings.team_count
    uniq = {s.id: s for s in cmd.songs}
    avail = [s for sid, s in uniq.items() if sid not in set(room.used_song_ids)]
    if len(avail) < n_teams + room.settings.target_cards:
        avail = list(uniq.values())
        room.used_song_ids = []
    if len(avail) < n_teams + 1:
        raise GameError("catalog_too_small", "No hay canciones suficientes")
    rng = random.Random(cmd.seed)
    ids: set[str] = set()
    cards: list[Card] = []
    for s in avail:
        iid = f"{rng.getrandbits(64):016x}"
        while iid in ids:
            iid = f"{rng.getrandbits(64):016x}"
        ids.add(iid)
        cards.append(
            Card(
                instance_id=iid,
                song_id=s.id,
                title=s.title,
                artist=s.artist,
                year=s.year,
                track_id=s.track_id,
                isrc=s.isrc,
                title_aliases=s.title_aliases,
                artist_aliases=s.artist_aliases,
                note=s.note,
            )
        )
    rng.shuffle(cards)
    initial = deal_initial(cards, n_teams)
    for team, card in zip(room.teams, initial, strict=True):
        team.timeline = [card]
        team.tokens = room.settings.initial_tokens
        room.used_song_ids.append(card.song_id)
    room.deck = cards
    room.discard = []
    room.turn = None
    room.winners = []
    room.game_over_reason = None
    room.turn_no = 0
    room.first_slot = rng.randrange(n_teams)
    room.audio.spotify_session_id = _host_hash(room)
    room.audio.playing = False
    room.phase = Phase.COUNTDOWN
    deadline = _start_timer(room, fx, now, "countdown", COUNTDOWN_S)
    fx.append(Broadcast("countdown", {"deadline_ts": deadline, "first_slot": room.first_slot}))


def _h_device_ready(room: Room, cmd: DeviceReady, now: float, fx: Fx) -> None:
    _require_host(room, cmd.sender)
    a = room.audio
    a.device_id = cmd.device_id
    a.provider = cmd.provider
    a.sdk_ready = cmd.provider != "preview"
    a.premium_ok = cmd.premium_ok
    a.unlocked = a.unlocked or cmd.unlock
    a.spotify_session_id = _host_hash(room)
    _sync_pause(room, fx, now)


def _h_audio_unlocked(room: Room, cmd: AudioUnlocked, now: float, fx: Fx) -> None:
    _require_host(room, cmd.sender)
    room.audio.unlocked = True
    _sync_pause(room, fx, now)


def _h_audio_report(room: Room, cmd: AudioReport, now: float, fx: Fx) -> None:
    _require_host(room, cmd.sender)
    room.audio.playing = cmd.playing
    source = room.turn.audio_source if room.turn else room.settings.audio_source
    fx.append(Broadcast("audio_status", {"playing": cmd.playing, "source": source}))


def _h_audio_failed(room: Room, cmd: AudioFailed, now: float, fx: Fx) -> None:
    _require_host(room, cmd.sender)
    code = cmd.code if cmd.code in ("premium_required", "device_gone", "rate_limited") else "unknown"
    fx.append(Broadcast("audio_error", {"code": code, "retry": code != "premium_required"}))
    if code == "device_gone":
        room.audio.sdk_ready = False
        room.audio.playing = False
    elif code == "premium_required":
        room.audio.premium_ok = False
    _sync_pause(room, fx, now)


def _h_play_request(room: Room, cmd: PlayRequest, now: float, fx: Fx) -> None:
    _require(room, Phase.TURN_READY, Phase.PLACING)
    _require_active(room, cmd.sender)
    room.phase = Phase.PLACING
    _play(room, fx)


def _h_play_result(room: Room, cmd: PlayResult, now: float, fx: Fx) -> None:
    turn = room.turn
    if turn is None or turn.card.instance_id != cmd.instance_id or room.phase != Phase.PLACING:
        return
    if turn.audio_source != "spotify":
        return
    if cmd.ok:
        _start_timer(room, fx, now, "tap_check", TAP_CHECK_S)
        return
    turn.play_failures += 1
    if turn.play_failures < 2:
        fx.append(Broadcast("audio_error", {"code": cmd.code, "retry": True}))
        fx.append(
            SpotifyPlay(
                room.audio.spotify_session_id,
                room.audio.device_id,
                turn.card.track_id,
                room.settings.start_position_ms,
                turn.card.instance_id,
            )
        )
    else:
        turn.audio_source = "preview"  # D7: automatic fallback for this turn
        fx.append(Broadcast("audio_error", {"code": cmd.code, "retry": False}))
        fx.append(SendTo(room.host_slot, "audio_command", {"action": "play_preview"}))
        fx.append(Broadcast("audio_status", {"playing": False, "source": "preview"}))


def _h_place_preview(room: Room, cmd: PlacePreview, now: float, fx: Fx) -> None:
    _require(room, Phase.PLACING)
    turn = _require_active(room, cmd.sender)
    if not 0 <= cmd.index <= len(room.teams[turn.team_slot].timeline):
        raise GameError("invalid_index", "Hueco fuera de rango")
    turn.preview_index = cmd.index


def _h_place_confirm(room: Room, cmd: PlaceConfirm, now: float, fx: Fx) -> None:
    _require(room, Phase.PLACING)
    turn = _require_active(room, cmd.sender)
    if not 0 <= cmd.index <= len(room.teams[turn.team_slot].timeline):
        raise GameError("invalid_index", "Hueco fuera de rango")
    turn.placed_index = cmd.index
    turn.preview_index = cmd.index
    _cancel_timer(room, fx, "tap_check")
    room.phase = Phase.GUESSING


def _h_guess_submit(room: Room, cmd: GuessSubmit, now: float, fx: Fx) -> None:
    _require(room, Phase.GUESSING)
    turn = _require_active(room, cmd.sender)
    if room.settings.mode != "app":
        raise GameError("wrong_mode", "Esta sala juega en modo voz")
    turn.guess_title = cmd.title.strip()[:MAX_GUESS_LEN]
    turn.guess_artist = cmd.artist.strip()[:MAX_GUESS_LEN]
    turn.guessed = True
    _after_guess(room, fx, now)


def _h_voice_confirm(room: Room, cmd: VoiceConfirm, now: float, fx: Fx) -> None:
    _require(room, Phase.GUESSING)
    _require_active(room, cmd.sender)
    if room.settings.mode != "voice":
        raise GameError("wrong_mode", "Esta sala juega en modo app")
    _after_guess(room, fx, now)


def _h_objection(room: Room, cmd: Objection, now: float, fx: Fx) -> None:
    if room.phase == Phase.PAUSED:
        raise GameError("paused", "La partida esta en pausa")
    if room.phase == Phase.REVEAL:
        raise GameError("objection_closed", "La ventana de objecion ya se cerro")
    _require(room, Phase.OBJECTION)
    turn = room.turn
    assert turn is not None
    if turn.objection is not None:
        raise GameError("objection_closed", "La ventana de objecion ya se cerro")
    s = cmd.sender
    if s is None or s == turn.team_slot or not 0 <= s < len(room.teams) or not room.teams[s].claimed:
        raise GameError("not_allowed", "No puedes objetar")
    if room.teams[s].tokens <= 0:
        raise GameError("no_token", "No tienes ficha")
    if not 0 <= cmd.index <= len(room.teams[turn.team_slot].timeline):
        raise GameError("invalid_index", "Hueco fuera de rango")
    if cmd.index == turn.placed_index:
        raise GameError("same_slot", "Elige un hueco distinto al del equipo activo")
    room.teams[s].tokens -= 1  # D2: always spent
    turn.objection = (s, cmd.index)
    _reveal(room, fx, now)


def _h_objection_pass(room: Room, cmd: ObjectionPass, now: float, fx: Fx) -> None:
    if room.phase == Phase.REVEAL:
        raise GameError("objection_closed", "La ventana de objecion ya se cerro")
    _require(room, Phase.OBJECTION)
    turn = room.turn
    assert turn is not None
    if cmd.sender is None or cmd.sender not in _eligible_objectors(room):
        raise GameError("not_allowed", "No puedes objetar")
    if cmd.sender not in turn.passed:
        turn.passed.append(cmd.sender)
    if all(s in turn.passed for s in _eligible_objectors(room)):
        _reveal(room, fx, now)


def _h_honor_claim(room: Room, cmd: HonorClaim, now: float, fx: Fx) -> None:
    _require(room, Phase.REVEAL)
    turn = _require_active(room, cmd.sender)
    if room.settings.mode != "voice":
        raise GameError("wrong_mode", "Esta sala juega en modo app")
    turn.title_ok, turn.artist_ok = cmd.title_ok, cmd.artist_ok
    _recompute_token(room)


def _h_accept_guess(room: Room, cmd: AcceptGuess, now: float, fx: Fx) -> None:
    _require(room, Phase.REVEAL)
    if cmd.sender is None or not room.teams[cmd.sender].claimed:
        raise GameError("not_allowed", "No puedes hacer esto")
    if room.settings.mode != "app":
        raise GameError("wrong_mode", "Esta sala juega en modo voz")
    assert room.turn is not None
    room.turn.title_ok = room.turn.artist_ok = True
    _recompute_token(room)


def _h_next_turn(room: Room, cmd: NextTurn, now: float, fx: Fx) -> None:
    _require(room, Phase.REVEAL)
    turn = _require_active(room, cmd.sender)
    if turn.reveal_at is not None and now < turn.reveal_at + REVEAL_MIN_S:
        raise GameError("too_early", "Espera unos segundos antes de seguir")
    _finish_turn(room, fx, now)


def _h_rematch(room: Room, cmd: Rematch, now: float, fx: Fx) -> None:
    _require(room, Phase.GAME_OVER)
    _require_host(room, cmd.sender)
    _cancel_all_timers(room, fx)
    for t in room.teams:
        t.timeline = []
        t.tokens = 0
    room.deck = []
    room.discard = []
    room.turn = None
    room.winners = []
    room.game_over_reason = None
    room.first_slot = None
    room.turn_no = 0
    room.phase = Phase.LOBBY


def _h_timer(room: Room, cmd: TimerFired, now: float, fx: Fx) -> None:
    ref = room.timers.get(cmd.name)
    if ref is None or ref.timer_id != cmd.timer_id:
        return  # expired / replaced timer
    del room.timers[cmd.name]
    name = cmd.name
    if name == "countdown":
        if room.phase == Phase.COUNTDOWN and room.first_slot is not None:
            _enter_turn_ready(room, fx, now, room.first_slot)
            _sync_pause(room, fx, now)
    elif name == "objection":
        if room.phase == Phase.OBJECTION:
            _reveal(room, fx, now)
    elif name == "reveal_auto":
        if room.phase == Phase.REVEAL:
            _finish_turn(room, fx, now)
    elif name == "tap_check":
        t = room.turn
        if (
            room.phase == Phase.PLACING
            and t is not None
            and t.audio_source == "spotify"
            and not room.audio.playing
        ):
            fx.append(SendTo(room.host_slot, "audio_command", {"action": "tap_required"}))
    elif name.startswith("grace:"):
        if room.phase == Phase.PAUSED and room.pause and room.pause.reason == PauseReason.TEAM_OFFLINE:
            if room.turn is not None:
                _skip_turn(room, fx, now)
    elif name == "lobby_host":
        if room.phase == Phase.LOBBY and not room.teams[room.host_slot].connected:
            cand = next((t for t in room.teams if t.claimed and t.connected), None)
            if cand is not None:
                room.host_slot = cand.slot
                _reset_audio(room)
                room.audio.spotify_session_id = cand.session_token_hash
    elif name == "room_gc":
        fx.append(DestroyRoom())


_HANDLERS: dict[type, Callable[[Room, Any, float, Fx], None]] = {
    ClaimSlot: _h_claim,
    Connected: _h_connected,
    Disconnected: _h_disconnected,
    Restored: _h_restored,
    Kick: _h_kick,
    UpdateSettings: _h_update_settings,
    Start: _h_start,
    DeviceReady: _h_device_ready,
    AudioUnlocked: _h_audio_unlocked,
    AudioReport: _h_audio_report,
    AudioFailed: _h_audio_failed,
    PlayRequest: _h_play_request,
    PlayResult: _h_play_result,
    PlacePreview: _h_place_preview,
    PlaceConfirm: _h_place_confirm,
    GuessSubmit: _h_guess_submit,
    VoiceConfirm: _h_voice_confirm,
    Objection: _h_objection,
    ObjectionPass: _h_objection_pass,
    HonorClaim: _h_honor_claim,
    AcceptGuess: _h_accept_guess,
    NextTurn: _h_next_turn,
    Rematch: _h_rematch,
    TimerFired: _h_timer,
}

_NO_PERSIST = (PlacePreview, AudioReport, PlayResult)


def reduce(room: Room, command: Command, now: float) -> tuple[Room, list[Effect]]:
    """Apply `command` to a copy of `room`. Raises GameError if the command is rejected."""
    new = room.model_copy(deep=True)
    fx: Fx = []
    handler = _HANDLERS[type(command)]
    handler(new, command, now, fx)
    if new != room:
        new.version = room.version + 1
        if room.phase != new.phase or not isinstance(command, _NO_PERSIST):
            fx.append(PersistSnapshot())
    return new, fx
