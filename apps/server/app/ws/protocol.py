"""Pydantic models of every WebSocket message (DISENO section 4, adapted to D1).

Envelope: {"type": str, "id": str, "payload": {...}}. Payload keys are snake_case, except the
`view` inside `state` and the cards inside `reveal`, which are camelCase (see docs/PROTOCOL.md).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator

from app.game.projection import CardPublic


class Envelope(BaseModel):
    type: str = Field(max_length=40)
    id: str = Field(default="", max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class Empty(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------- client -> server


COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class Hello(BaseModel):
    session_token: str = Field(max_length=200)
    last_version: int | None = None


class ClaimSlotMsg(BaseModel):
    slot: int
    name: str = Field(min_length=1, max_length=40)
    color: str | None = Field(default=None, pattern=COLOR_PATTERN)


class DeviceReadyMsg(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)
    provider: Literal["sdk", "connect", "preview", "fake"]


class AudioReportMsg(BaseModel):
    playing: bool


class AudioFailedMsg(BaseModel):
    code: Literal["premium_required", "device_gone", "rate_limited", "unknown"] = "unknown"


class KickMsg(BaseModel):
    slot: int


class UpdateSettingsMsg(BaseModel):
    """Partial<Settings>. Editable keys: team_count, mode, target_cards, objection_window_s, audio_source,
    packs, hints_enabled, initial_tokens."""

    model_config = ConfigDict(extra="allow")


class AudioControlMsg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["seek", "pause", "resume", "restart"]
    delta_ms: StrictInt | None = Field(default=None, ge=-30000, le=30000)

    @model_validator(mode="after")
    def _delta_only_for_seek(self) -> AudioControlMsg:
        if (self.action == "seek") != (self.delta_ms is not None):
            raise ValueError("delta_ms is required for seek and forbidden otherwise")
        return self


class UseHintMsg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["artist", "title"]


class IndexMsg(BaseModel):
    index: int


class GuessSubmitMsg(BaseModel):
    title: str = Field(default="", max_length=200)
    artist: str = Field(default="", max_length=200)


class HonorClaimMsg(BaseModel):
    title_ok: bool
    artist_ok: bool


class PingMsg(BaseModel):
    t: Annotated[float, Field(allow_inf_nan=False)] | int | Annotated[str, Field(max_length=64)] | None = None


CLIENT_MESSAGES: dict[str, type[BaseModel]] = {
    "hello": Hello,
    "claim_slot": ClaimSlotMsg,
    "device_ready": DeviceReadyMsg,
    "audio_unlocked": Empty,
    "audio_report": AudioReportMsg,
    "audio_failed": AudioFailedMsg,
    "audio_control": AudioControlMsg,
    "use_hint": UseHintMsg,
    "kick": KickMsg,
    "update_settings": UpdateSettingsMsg,
    "start_game": Empty,
    "play_request": Empty,
    "place_preview": IndexMsg,
    "place_confirm": IndexMsg,
    "place_cancel": Empty,
    "guess_submit": GuessSubmitMsg,
    "voice_confirm": Empty,
    "objection": IndexMsg,
    "objection_pass": Empty,
    "honor_claim": HonorClaimMsg,
    "accept_guess": Empty,
    "next_turn": Empty,
    "rematch": Empty,
    "end_game": Empty,
    "ping": PingMsg,
}


class ProtocolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def parse_client_message(raw: Any) -> tuple[Envelope, BaseModel]:
    try:
        env = Envelope.model_validate(raw)
    except ValidationError as e:
        raise ProtocolError("bad_message", "Mensaje mal formado") from e
    model = CLIENT_MESSAGES.get(env.type)
    if model is None:
        raise ProtocolError("unknown_type", f"Tipo desconocido: {env.type}")
    try:
        return env, model.model_validate(env.payload)
    except ValidationError as e:
        raise ProtocolError("bad_payload", "Payload no valido") from e


# ---------------------------------------------------------------- server -> client


class StatePayload(BaseModel):
    version: int
    view: dict[str, Any]


class CountdownPayload(BaseModel):
    deadline_ts: float
    first_slot: int


class AudioCommandPayload(BaseModel):
    """Only sent to the host phone. Never carries a URI."""

    action: Literal["prepare", "tap_required", "play_preview", "stop", "seek", "pause", "resume", "restart"]
    delta_ms: int | None = None  # only with action "seek"


class HintUsedPayload(BaseModel):
    """Public notice. Never carries the masked text."""

    slot: int
    kind: Literal["artist", "title"]


class AudioStatusPayload(BaseModel):
    playing: bool
    source: Literal["spotify", "preview"]


class AudioErrorPayload(BaseModel):
    code: Literal["premium_required", "device_gone", "rate_limited", "unknown"]
    retry: bool


class ObjectionResult(BaseModel):
    slot: int
    index: int
    correct: bool | None


class GuessAuto(BaseModel):
    title_ok: bool
    artist_ok: bool
    score: float


class RevealPayload(BaseModel):
    card: CardPublic
    correct_slot: bool
    outcome: Literal["kept", "stolen", "discarded"]
    to_slot: int | None
    objection_result: ObjectionResult | None
    guess_auto: GuessAuto | None
    reveal_unlocks_at: float


class TurnResolvedPayload(BaseModel):
    to_slot: int | None
    token_delta: dict[str, int]


class KickedPayload(BaseModel):
    reason: str


class DeckLowPayload(BaseModel):
    remaining: int


class Standing(BaseModel):
    slot: int
    name: str | None
    cards: int
    tokens: int
    rank: int


class GameOverPayload(BaseModel):
    winners: list[int]
    reason: Literal["target", "deck_exhausted", "host_ended"]
    standings: list[Standing]


class ErrorPayload(BaseModel):
    ref_id: str
    code: str
    message: str


class AckPayload(BaseModel):
    ref_id: str


class PongPayload(BaseModel):
    t: float | int | str | None
    server_ts: float


SERVER_MESSAGES: dict[str, type[BaseModel]] = {
    "state": StatePayload,
    "countdown": CountdownPayload,
    "audio_command": AudioCommandPayload,
    "audio_status": AudioStatusPayload,
    "hint_used": HintUsedPayload,
    "audio_error": AudioErrorPayload,
    "reveal": RevealPayload,
    "turn_resolved": TurnResolvedPayload,
    "kicked": KickedPayload,
    "deck_low": DeckLowPayload,
    "game_over": GameOverPayload,
    "error": ErrorPayload,
    "ack": AckPayload,
    "pong": PongPayload,
}
