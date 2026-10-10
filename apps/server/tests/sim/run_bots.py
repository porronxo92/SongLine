"""Bot simulator: plays complete games in-process against the pure engine.

Usage (from apps/server):
    .venv/Scripts/python tests/sim/run_bots.py 300 [--seed 0] [--leaks]

Each game uses random team count / mode / skill, random objections, random disconnects of the
active team and of the audio host. Asserts every game ends and that the invariants hold at every step.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # executed as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.game import commands as C  # noqa: E402
from app.game.commands import GameError  # noqa: E402
from app.game.engine import reduce  # noqa: E402
from app.game.models import Phase, Room, Song, new_room  # noqa: E402
from app.game.projection import view_json  # noqa: E402
from app.game.rules import is_sorted  # noqa: E402

MAX_STEPS = 6000


def make_songs(n: int = 60, seed: int = 1) -> tuple[Song, ...]:
    rng = random.Random(seed)
    return tuple(
        Song(
            id=i + 1,
            csv_id=f"S{i}",
            title=f"Cancion Numero {i:03d} {rng.choice('abcdefgh')}",
            artist=f"Artista {i:03d}",
            year=rng.randint(1960, 2023),
            track_id=f"trk{i:03d}x",
        )
        for i in range(n)
    )


def total_cards(room: Room) -> int:
    n = len(room.deck) + len(room.discard) + sum(len(t.timeline) for t in room.teams)
    if room.turn is not None and room.turn.result is None:
        n += 1  # the card in play is in neither pile
    return n


def check_invariants(room: Room, expected_total: int) -> None:
    for t in room.teams:
        assert is_sorted(t.timeline), f"timeline of {t.slot} not sorted"
        assert t.tokens >= 0
    if room.phase not in (Phase.LOBBY,):
        assert total_cards(room) == expected_total, "cards not conserved"
    ids = [c.instance_id for t in room.teams for c in t.timeline] + [c.instance_id for c in room.deck]
    ids += [c.instance_id for c in room.discard]
    assert len(ids) == len(set(ids)), "duplicate card"
    if room.phase == Phase.GAME_OVER:
        assert room.winners, "no winners"


def setup_lobby(
    team_count: int = 3,
    mode: str = "voice",
    target: int = 10,
    code: str = "0001",
    objection_window_s: int = 15,
) -> Room:
    """Lobby with every slot claimed and connected, host audio ready (fake-mode equivalent)."""
    room = new_room(code, "hash0", "Host")
    now = 0.0
    room, _ = reduce(
        room,
        C.UpdateSettings(
            0,
            {
                "team_count": team_count,
                "mode": mode,
                "target_cards": target,
                "objection_window_s": objection_window_s,
            },
        ),
        now,
    )
    for slot in range(1, team_count):
        room, _ = reduce(room, C.ClaimSlot(f"hash{slot}", slot, f"Equipo {slot}", None), now)
    room, _ = reduce(room, C.DeviceReady(0, "dev", "sdk", premium_ok=True, unlock=True), now)
    return room


def start_game(room: Room, songs: tuple[Song, ...], seed: int, now: float = 100.0) -> tuple[Room, float]:
    """Start and run the countdown. Returns (room in TURN_READY, now)."""
    room, _ = reduce(room, C.Start(0, songs, seed), now)
    now = room.timers["countdown"].deadline_ts
    room, _ = reduce(room, fire(room, "countdown"), now)
    return room, now


def fire(room: Room, name: str) -> C.TimerFired:
    return C.TimerFired(name, room.timers[name].timer_id)


@dataclass
class GameStats:
    steps: int
    turns: int
    reason: str | None
    objections: int
    pauses: int
    skipped: int


def play_game(
    seed: int,
    *,
    check_leaks: bool = False,
    team_count: int | None = None,
    mode: str | None = None,
    songs: tuple[Song, ...] | None = None,
    target: int | None = None,
    on_step: Callable[[Room], None] | None = None,
) -> tuple[Room, GameStats]:
    rng = random.Random(seed)
    tc = team_count or rng.randint(2, 4)
    md = mode or rng.choice(["voice", "app"])
    tg = target or rng.choice([3, 5, 10])
    songs = songs or make_songs(rng.choice([8, 15, 60]), seed=seed)
    room = setup_lobby(tc, md, tg)
    now = 100.0
    room, _ = reduce(room, C.Start(0, songs, seed), now)
    expected_total = len(set(s.id for s in songs)) if len(songs) >= tc + 1 else len(songs)
    skill = rng.choice([0.2, 0.5, 0.9])
    obj_p = rng.choice([0.0, 0.5, 1.0])
    drop_p = rng.choice([0.0, 0.05, 0.15])
    stats = GameStats(0, 0, None, 0, 0, 0)

    def step(cmd: C.Command) -> None:
        nonlocal room
        room, _ = reduce(room, cmd, now)
        stats.steps += 1
        check_invariants(room, expected_total)
        if check_leaks:
            assert_no_leak(room)
        if on_step:
            on_step(room)

    while room.phase != Phase.GAME_OVER:
        if stats.steps > MAX_STEPS:
            raise AssertionError(f"game {seed} did not finish (phase={room.phase})")
        ph = room.phase
        turn = room.turn
        if ph == Phase.PAUSED:
            stats.pauses += 1
            assert room.pause is not None
            if room.pause.reason == "audio_host_offline":
                step(C.Connected(room.host_slot))
                step(C.DeviceReady(room.host_slot, "dev", "sdk", premium_ok=True, unlock=True))
            elif rng.random() < 0.5:
                step(C.Connected(room.pause.slot or 0))
            else:
                name = next(n for n in room.timers if n.startswith("grace:"))
                now = room.timers[name].deadline_ts
                stats.skipped += 1
                step(fire(room, name))
            continue
        if ph == Phase.COUNTDOWN:
            now = room.timers["countdown"].deadline_ts
            step(fire(room, "countdown"))
        elif ph == Phase.TURN_READY:
            assert turn is not None
            if drop_p and rng.random() < drop_p:
                step(C.Disconnected(turn.team_slot))
                continue
            if drop_p and rng.random() < drop_p / 3:
                step(C.Disconnected(room.host_slot))
                continue
            step(C.PlayRequest(turn.team_slot))
        elif ph == Phase.PLACING:
            assert turn is not None
            years = [c.year for c in room.teams[turn.team_slot].timeline]
            if rng.random() < skill:
                idx = sum(1 for y in years if y <= turn.card.year)
            else:
                idx = rng.randint(0, len(years))
            if rng.random() < 0.3:
                step(C.PlacePreview(turn.team_slot, rng.randint(0, len(years))))
            step(C.PlaceConfirm(turn.team_slot, idx))
        elif ph == Phase.GUESSING:
            assert turn is not None
            if md == "app":
                good = rng.random() < skill
                step(
                    C.GuessSubmit(
                        turn.team_slot,
                        turn.card.title if good else "zzz",
                        turn.card.artist if good else "",
                    )
                )
            else:
                step(C.VoiceConfirm(turn.team_slot))
        elif ph == Phase.OBJECTION:
            assert turn is not None
            eligible = [t.slot for t in room.teams if t.slot != turn.team_slot and t.tokens > 0]
            if rng.random() < 0.15:
                now = room.timers["objection"].deadline_ts
                step(fire(room, "objection"))
                continue
            for s in rng.sample(eligible, len(eligible)):
                if room.phase != Phase.OBJECTION:
                    # late objection: must be rejected without touching the state
                    try:
                        reduce(room, C.Objection(s, 0), now)
                        raise AssertionError("late objection accepted")
                    except GameError as e:
                        assert e.code == "objection_closed"
                    continue
                n_cards = len(room.teams[turn.team_slot].timeline)
                if rng.random() < obj_p:
                    idx = rng.randint(0, n_cards)
                    if idx == turn.placed_index:
                        step(C.ObjectionPass(s))
                    else:
                        stats.objections += 1
                        step(C.Objection(s, idx))
                else:
                    step(C.ObjectionPass(s))
        elif ph == Phase.REVEAL:
            assert turn is not None
            if md == "voice":
                step(C.HonorClaim(turn.team_slot, rng.random() < skill, rng.random() < skill))
            elif rng.random() < 0.3:
                step(C.AcceptGuess(rng.randrange(tc)))
            stats.turns += 1
            if rng.random() < 0.2:
                now = room.timers["reveal_auto"].deadline_ts
                step(fire(room, "reveal_auto"))
            else:
                now += 6.0
                step(C.NextTurn(turn.team_slot))
        else:  # pragma: no cover
            raise AssertionError(f"unexpected phase {ph}")
    stats.reason = room.game_over_reason
    return room, stats


def assert_no_leak(room: Room) -> None:
    """The card in play must not appear in any viewer's JSON before REVEAL."""
    turn = room.turn
    if turn is None or room.phase in (Phase.REVEAL, Phase.GAME_OVER, Phase.LOBBY):
        return
    if room.phase == Phase.PAUSED and turn.result is not None:
        return
    c = turn.card
    for viewer in [None, *range(len(room.teams))]:
        view = view_json(room, viewer)
        if viewer == turn.team_slot and view.get("turn"):
            view["turn"].pop("guess", None)  # the active team sees what it typed itself
        blob = json.dumps(view, ensure_ascii=False)
        assert c.title not in blob and c.artist not in blob, "title/artist leaked"
        assert c.track_id not in blob or not c.track_id, "track_id leaked"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int, nargs="?", default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--leaks", action="store_true", help="check the anti-cheat projection at every step")
    args = ap.parse_args()
    t0 = time.time()
    reasons: dict[str | None, int] = {}
    steps = pauses = skipped = objections = 0
    for i in range(args.n):
        _, st = play_game(args.seed + i, check_leaks=args.leaks)
        reasons[st.reason] = reasons.get(st.reason, 0) + 1
        steps += st.steps
        pauses += st.pauses
        skipped += st.skipped
        objections += st.objections
    print(
        f"OK: {args.n} games finished in {time.time() - t0:.1f}s | endings={reasons} "
        f"steps={steps} pauses={pauses} skipped_turns={skipped} objections={objections}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
