"""Domain models of a room. Pure data: no I/O. Server-side only (cards hold secrets)."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Phase(StrEnum):
    LOBBY = "lobby"
    COUNTDOWN = "countdown"
    TURN_READY = "turn_ready"
    PLACING = "placing"
    GUESSING = "guessing"
    OBJECTION = "objection"
    REVEAL = "reveal"
    PAUSED = "paused"
    GAME_OVER = "game_over"


class PauseReason(StrEnum):
    AUDIO_HOST_OFFLINE = "audio_host_offline"
    TEAM_OFFLINE = "team_offline"


class Song(BaseModel, frozen=True):
    """Catalog entry handed to the engine when a game starts."""

    id: int
    csv_id: str = ""
    title: str
    artist: str
    year: int
    track_id: str = ""
    isrc: str = ""
    title_aliases: tuple[str, ...] = ()
    artist_aliases: tuple[str, ...] = ()
    genre: str = ""
    origin: str = ""
    note: str = ""
    pack: str = "mix"  # catalog pack slug; server-only, never projected


PACK_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,39}$"
MAX_PACKS = 20


class Settings(BaseModel):
    team_count: int = Field(default=2, ge=2, le=4)
    mode: Literal["app", "voice"] = "voice"
    target_cards: int = Field(default=10, ge=3, le=30)
    initial_card_counts: Literal[True] = True  # D3
    initial_tokens: int = 0
    objection_window_s: int = Field(default=15, ge=5, le=60)
    objection_cost: Literal["always"] = "always"  # D2
    token_requires_correct_slot: Literal[True] = True  # D5
    placement_timeout_s: None = None  # D8
    disconnect_grace_s: int = 60
    start_position_ms: int = 10_000  # D9
    audio_source: Literal["spotify", "preview"] = "spotify"  # D7
    packs: list[str] = Field(default_factory=lambda: ["mix"], max_length=MAX_PACKS)

    @field_validator("packs")
    @classmethod
    def _check_packs(cls, v: list[str]) -> list[str]:
        """Shape only (pure). Whether each slug exists is checked at the boundary against the catalog."""
        if not v:
            raise ValueError("at least one pack")
        if len(set(v)) != len(v):
            raise ValueError("duplicate packs")
        if not all(re.fullmatch(PACK_SLUG_PATTERN, p) for p in v):
            raise ValueError("invalid pack slug")
        return v


# Settings the host may change from the lobby. Everything else is fixed by D1-D9.
EDITABLE_SETTINGS = frozenset({"team_count", "mode", "target_cards", "objection_window_s", "audio_source", "packs"})


class AudioHost(BaseModel):
    """D1: the host phone is the only audio output."""

    spotify_session_id: str | None = None  # sha256 of the host session token
    device_id: str | None = None
    provider: str | None = None
    sdk_ready: bool = False
    premium_ok: bool = False
    unlocked: bool = False
    playing: bool = False


class Card(BaseModel):
    """Server-only. `instance_id` is opaque and random per game (never the song id)."""

    instance_id: str
    song_id: int
    title: str
    artist: str
    year: int
    track_id: str = ""
    isrc: str = ""
    title_aliases: tuple[str, ...] = ()
    artist_aliases: tuple[str, ...] = ()
    note: str = ""


class Team(BaseModel):
    slot: int
    name: str | None = None
    color: str | None = None
    session_token_hash: str | None = None
    connected: bool = False
    timeline: list[Card] = Field(default_factory=list)
    tokens: int = 0

    @property
    def claimed(self) -> bool:
        return self.session_token_hash is not None


SlotReason = Literal["inside", "equal_left", "equal_right", "equal_both", "too_early", "too_late"]
TokenReason = Literal[
    "awarded", "wrong_slot", "title_wrong", "artist_wrong", "title_and_artist_wrong"
]
Headline = Literal["kept", "kept_objection_failed", "stolen", "discarded", "discarded_objection_failed"]


class SlotExplanation(BaseModel):
    """Why a slot in a sorted line is (in)correct for a given year.

    `valid_from..valid_to` is the inclusive range of slot indexes that would have been correct.
    """

    index: int
    left_year: int | None
    right_year: int | None
    ok: bool
    reason: SlotReason
    valid_from: int
    valid_to: int


class ObjectionExplanation(SlotExplanation):
    slot: int  # objector team
    token_spent: bool = True  # D2: the objection token is always spent


class TokenOutcome(BaseModel):
    awarded: bool = False
    reason: TokenReason = "wrong_slot"


class TurnResult(BaseModel):
    placed_ok: bool
    objection_slot: int | None = None
    objection_ok: bool | None = None
    outcome: Literal["kept", "stolen", "discarded"]
    to_slot: int | None = None
    song_year: int
    placement: SlotExplanation
    objection: ObjectionExplanation | None = None
    token: TokenOutcome = Field(default_factory=TokenOutcome)
    headline: Headline


class Turn(BaseModel):
    team_slot: int
    card: Card
    audio_source: Literal["spotify", "preview"] = "spotify"
    play_failures: int = 0
    started_playing: bool = False
    placed_index: int | None = None
    preview_index: int | None = None
    guess_title: str | None = None
    guess_artist: str | None = None
    guessed: bool = False
    objection: tuple[int, int] | None = None  # (objector slot, index in the active line)
    passed: list[int] = Field(default_factory=list)
    deadline_ts: float | None = None
    title_ok: bool = False
    artist_ok: bool = False
    token_awarded: bool = False
    reveal_at: float | None = None
    result: TurnResult | None = None


class TimerRef(BaseModel):
    timer_id: str
    deadline_ts: float


class PauseInfo(BaseModel):
    reason: PauseReason
    slot: int | None = None
    deadline_ts: float | None = None


class Room(BaseModel):
    code: str
    host_slot: int = 0
    settings: Settings = Field(default_factory=Settings)
    audio: AudioHost = Field(default_factory=AudioHost)
    phase: Phase = Phase.LOBBY
    paused_from: Phase | None = None
    pause: PauseInfo | None = None
    teams: list[Team] = Field(default_factory=list)
    deck: list[Card] = Field(default_factory=list)
    discard: list[Card] = Field(default_factory=list)
    used_song_ids: list[int] = Field(default_factory=list)
    turn: Turn | None = None
    first_slot: int | None = None
    turn_no: int = 0
    timers: dict[str, TimerRef] = Field(default_factory=dict)
    frozen: dict[str, float] = Field(default_factory=dict)  # timers frozen by PAUSED: remaining seconds
    timer_seq: int = 0
    version: int = 0
    winners: list[int] = Field(default_factory=list)
    game_over_reason: Literal["target", "deck_exhausted", "host_ended"] | None = None

    def team(self, slot: int) -> Team:
        return self.teams[slot]

    def slot_of(self, session_hash: str) -> int | None:
        for t in self.teams:
            if t.session_token_hash == session_hash:
                return t.slot
        return None

    @property
    def occupied(self) -> int:
        return sum(1 for t in self.teams if t.claimed)


def new_room(
    code: str,
    host_hash: str,
    name: str | None = None,
    color: str | None = None,
    settings: Settings | None = None,
) -> Room:
    st = settings or Settings()
    teams = [Team(slot=i) for i in range(st.team_count)]
    teams[0].session_token_hash = host_hash
    teams[0].name = name
    teams[0].color = color
    teams[0].connected = True
    return Room(code=code, settings=st, teams=teams)
