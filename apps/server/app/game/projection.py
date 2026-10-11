"""The ONLY place that decides what a client sees. Everything is whitelisted explicitly.

`project(room, viewer_slot) -> RoomView` never touches the title, artist, year, track_id or
song_id of the card in play unless the room is in REVEAL (or GAME_OVER, where there is no card in play).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.game.models import Card, Phase, Room, Team
from app.game.rules import card_count, rank_standings


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CardPublic(CamelModel):
    instance_id: str
    year: int
    title: str
    artist: str
    note: str | None = None


class MysteryCard(CamelModel):
    instance_id: str
    hidden: Literal[True] = True


class SettingsView(CamelModel):
    team_count: int
    mode: str
    target_cards: int
    initial_card_counts: bool
    initial_tokens: int
    objection_window_s: int
    objection_cost: str
    token_requires_correct_slot: bool
    placement_timeout_s: None
    disconnect_grace_s: int
    start_position_ms: int
    audio_source: str
    packs: list[str]


class YouView(CamelModel):
    slot: int | None
    is_host: bool


class TeamView(CamelModel):
    slot: int
    name: str | None
    color: str | None
    claimed: bool
    connected: bool
    is_host: bool
    timeline: list[CardPublic]
    tokens: int
    card_count: int


class ObjectionView(CamelModel):
    slot: int
    index: int


class GuessView(CamelModel):
    title: str
    artist: str


class SlotCheckView(CamelModel):
    index: int
    left_year: int | None
    right_year: int | None
    ok: bool
    reason: str
    valid_from: int
    valid_to: int


class ObjectionCheckView(SlotCheckView):
    slot: int
    token_spent: bool


class TokenView(CamelModel):
    awarded: bool
    reason: str


class ResultView(CamelModel):
    placed_ok: bool
    objection_slot: int | None
    objection_ok: bool | None
    outcome: str
    to_slot: int | None
    title_ok: bool
    artist_ok: bool
    token_awarded: bool
    token_delta: dict[str, int]
    song_year: int
    placement: SlotCheckView
    objection: ObjectionCheckView | None
    token: TokenView
    headline: str


class TurnView(CamelModel):
    team_slot: int
    card: MysteryCard | CardPublic
    placed_index: int | None = None
    preview_index: int | None = None
    objection: ObjectionView | None = None
    eligible_objectors: list[int] | None = None
    deadline_ts: float | None = None
    guess: GuessView | None = None
    audio_source: str
    started_playing: bool
    result: ResultView | None = None  # only in REVEAL
    reveal_unlocks_at: float | None = None  # only in REVEAL: earliest `next_turn`


class PauseView(CamelModel):
    reason: str
    slot: int | None
    deadline_ts: float | None
    resume_phase: str | None


class AudioView(CamelModel):
    host_ready: bool
    playing: bool
    source: str


class StandingView(CamelModel):
    slot: int
    name: str | None
    cards: int
    tokens: int
    rank: int


class RoomView(CamelModel):
    code: str
    phase: Phase
    settings: SettingsView
    you: YouView
    teams: list[TeamView]
    turn: TurnView | None = None
    deck_remaining: int
    audio: AudioView
    pause: PauseView | None = None
    winners: list[int] | None = None
    game_over_reason: str | None = None
    standings: list[StandingView] | None = None


def card_public(card: Card) -> CardPublic:
    return CardPublic(
        instance_id=card.instance_id,
        year=card.year,
        title=card.title,
        artist=card.artist,
        note=card.note or None,
    )


def token_delta(room: Room) -> dict[str, int]:
    turn = room.turn
    if turn is None:
        return {}
    delta: dict[str, int] = {}
    if turn.token_awarded:
        delta[str(turn.team_slot)] = delta.get(str(turn.team_slot), 0) + 1
    if turn.objection is not None:
        delta[str(turn.objection[0])] = delta.get(str(turn.objection[0]), 0) - 1
    return delta


def standings(room: Room) -> list[StandingView]:
    ranks = rank_standings(room.teams)
    rows = [
        StandingView(slot=t.slot, name=t.name, cards=card_count(t), tokens=t.tokens, rank=ranks[t.slot])
        for t in room.teams
        if t.claimed
    ]
    return sorted(rows, key=lambda r: (r.rank, r.slot))


def eligible_objectors(room: Room) -> list[int]:
    turn = room.turn
    if turn is None:
        return []
    return [t.slot for t in room.teams if t.claimed and t.slot != turn.team_slot and t.tokens > 0]


def _team_view(team: Team, room: Room) -> TeamView:
    return TeamView(
        slot=team.slot,
        name=team.name,
        color=team.color,
        claimed=team.claimed,
        connected=team.connected,
        is_host=team.slot == room.host_slot and team.claimed,
        timeline=[card_public(c) for c in team.timeline],
        tokens=team.tokens,
        card_count=card_count(team),
    )


def audio_ready(room: Room) -> bool:
    a = room.audio
    if not a.unlocked:
        return False
    return room.settings.audio_source == "preview" or (a.sdk_ready and a.premium_ok)


def _turn_view(room: Room, viewer_slot: int | None) -> TurnView | None:
    turn = room.turn
    if turn is None:
        return None
    revealed = room.phase == Phase.REVEAL or (room.phase == Phase.PAUSED and turn.result is not None)
    card: MysteryCard | CardPublic = (
        card_public(turn.card) if revealed else MysteryCard(instance_id=turn.card.instance_id)
    )
    guess: GuessView | None = None
    if turn.guessed and turn.guess_title is not None:
        if revealed or viewer_slot == turn.team_slot:
            guess = GuessView(title=turn.guess_title, artist=turn.guess_artist or "")
    result: ResultView | None = None
    if revealed and turn.result is not None:
        r = turn.result
        result = ResultView(
            placed_ok=r.placed_ok,
            objection_slot=r.objection_slot,
            objection_ok=r.objection_ok,
            outcome=r.outcome,
            to_slot=r.to_slot,
            title_ok=turn.title_ok,
            artist_ok=turn.artist_ok,
            token_awarded=turn.token_awarded,
            token_delta=token_delta(room),
            song_year=r.song_year,
            placement=SlotCheckView(**r.placement.model_dump()),
            objection=ObjectionCheckView(**r.objection.model_dump()) if r.objection else None,
            token=TokenView(**r.token.model_dump()),
            headline=r.headline,
        )
    return TurnView(
        team_slot=turn.team_slot,
        card=card,
        placed_index=turn.placed_index,
        preview_index=turn.preview_index if room.phase == Phase.PLACING else None,
        objection=(
            ObjectionView(slot=turn.objection[0], index=turn.objection[1]) if turn.objection else None
        ),
        eligible_objectors=eligible_objectors(room) if room.phase == Phase.OBJECTION else None,
        deadline_ts=turn.deadline_ts,
        guess=guess,
        audio_source=turn.audio_source,
        started_playing=turn.started_playing,
        result=result,
        reveal_unlocks_at=(turn.reveal_at + 5.0) if (revealed and turn.reveal_at is not None) else None,
    )


def project(room: Room, viewer_slot: int | None) -> RoomView:
    s = room.settings
    is_host = viewer_slot is not None and viewer_slot == room.host_slot
    game_over = room.phase == Phase.GAME_OVER
    pause: PauseView | None = None
    if room.phase == Phase.PAUSED and room.pause is not None:
        pause = PauseView(
            reason=str(room.pause.reason),
            slot=room.pause.slot,
            deadline_ts=room.pause.deadline_ts,
            resume_phase=str(room.paused_from) if room.paused_from else None,
        )
    return RoomView(
        code=room.code,
        phase=room.phase,
        settings=SettingsView(**s.model_dump()),
        you=YouView(slot=viewer_slot, is_host=is_host),
        teams=[_team_view(t, room) for t in room.teams],
        turn=_turn_view(room, viewer_slot),
        deck_remaining=len(room.deck),
        audio=AudioView(
            host_ready=audio_ready(room) and room.teams[room.host_slot].connected,
            playing=room.audio.playing,
            source=room.turn.audio_source if room.turn else s.audio_source,
        ),
        pause=pause,
        winners=list(room.winners) if game_over else None,
        game_over_reason=room.game_over_reason if game_over else None,
        standings=standings(room) if game_over else None,
    )


def view_json(room: Room, viewer_slot: int | None) -> dict[str, Any]:
    return project(room, viewer_slot).model_dump(by_alias=True, mode="json")
