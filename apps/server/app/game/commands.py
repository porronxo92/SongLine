"""Commands (inputs) and effects (outputs) of the pure engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.game.models import Song

# ---------------------------------------------------------------- effects


@dataclass(frozen=True)
class Broadcast:
    """Ephemeral event for every connection of the room (a `state` message is sent separately)."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SendTo:
    """Ephemeral event for the connections of one slot."""

    slot: int
    type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StartTimer:
    name: str
    timer_id: str
    delay_s: float


@dataclass(frozen=True)
class CancelTimer:
    name: str


@dataclass(frozen=True)
class SpotifyPlay:
    session_id: str | None
    device_id: str | None
    track_id: str
    position_ms: int
    instance_id: str


@dataclass(frozen=True)
class SpotifyPause:
    session_id: str | None
    device_id: str | None


@dataclass(frozen=True)
class PersistSnapshot:
    pass


@dataclass(frozen=True)
class DestroyRoom:
    pass


Effect = (
    Broadcast | SendTo | StartTimer | CancelTimer | SpotifyPlay | SpotifyPause | PersistSnapshot | DestroyRoom
)

# ---------------------------------------------------------------- commands


@dataclass(frozen=True)
class ClaimSlot:
    session_hash: str
    slot: int
    name: str
    color: str | None = None


@dataclass(frozen=True)
class Connected:
    slot: int


@dataclass(frozen=True)
class Disconnected:
    slot: int


@dataclass(frozen=True)
class Restored:
    """The server restarted and restored this room from a snapshot: nobody is connected."""


@dataclass(frozen=True)
class Kick:
    sender: int | None
    slot: int


@dataclass(frozen=True)
class UpdateSettings:
    sender: int | None
    changes: dict[str, Any]


@dataclass(frozen=True)
class Start:
    sender: int | None
    songs: tuple[Song, ...]
    seed: int


@dataclass(frozen=True)
class DeviceReady:
    sender: int | None
    device_id: str
    provider: str
    premium_ok: bool
    unlock: bool = False


@dataclass(frozen=True)
class AudioUnlocked:
    sender: int | None


@dataclass(frozen=True)
class AudioReport:
    sender: int | None
    playing: bool


@dataclass(frozen=True)
class AudioFailed:
    sender: int | None
    code: str


@dataclass(frozen=True)
class AudioControl:
    sender: int | None
    action: str  # "seek" | "pause" | "resume" | "restart"
    delta_ms: int | None = None


@dataclass(frozen=True)
class UseHint:
    sender: int | None
    kind: str  # "artist" | "title"


@dataclass(frozen=True)
class PlayRequest:
    sender: int | None


@dataclass(frozen=True)
class PlayResult:
    instance_id: str
    ok: bool
    code: str = "unknown"
    retry_after_s: float | None = None


@dataclass(frozen=True)
class PlacePreview:
    sender: int | None
    index: int


@dataclass(frozen=True)
class PlaceConfirm:
    sender: int | None
    index: int


@dataclass(frozen=True)
class PlaceCancel:
    sender: int | None


@dataclass(frozen=True)
class GuessSubmit:
    sender: int | None
    title: str
    artist: str


@dataclass(frozen=True)
class VoiceConfirm:
    sender: int | None


@dataclass(frozen=True)
class Objection:
    sender: int | None
    index: int


@dataclass(frozen=True)
class ObjectionPass:
    sender: int | None


@dataclass(frozen=True)
class HonorClaim:
    sender: int | None
    title_ok: bool
    artist_ok: bool


@dataclass(frozen=True)
class AcceptGuess:
    sender: int | None


@dataclass(frozen=True)
class NextTurn:
    sender: int | None


@dataclass(frozen=True)
class Rematch:
    sender: int | None


@dataclass(frozen=True)
class EndGame:
    sender: int | None


@dataclass(frozen=True)
class TimerFired:
    name: str
    timer_id: str


Command = (
    ClaimSlot
    | Connected
    | Disconnected
    | Restored
    | Kick
    | UpdateSettings
    | Start
    | DeviceReady
    | AudioUnlocked
    | AudioReport
    | AudioFailed
    | AudioControl
    | UseHint
    | PlayRequest
    | PlayResult
    | PlacePreview
    | PlaceConfirm
    | PlaceCancel
    | GuessSubmit
    | VoiceConfirm
    | Objection
    | ObjectionPass
    | HonorClaim
    | AcceptGuess
    | NextTurn
    | Rematch
    | EndGame
    | TimerFired
)


class GameError(Exception):
    """A command was rejected. The state is left untouched."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
