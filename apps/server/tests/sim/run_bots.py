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
from app.game.projection import standings, view_json  # noqa: E402
from app.game.rules import hint_seed, is_sorted, mask_text  # noqa: E402

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


def check_result(room: Room) -> None:
    turn = room.turn
    assert turn is not None and turn.result is not None
    r = turn.result
    assert r.placement.ok == r.placed_ok
    assert r.placement.index == turn.placed_index
    assert r.song_year == turn.card.year
    assert (r.placement.valid_from <= r.placement.index <= r.placement.valid_to) == r.placement.ok
    assert r.token.awarded == turn.token_awarded
    if r.objection is not None:
        assert r.objection.ok == r.objection_ok and r.objection.slot == r.objection_slot
        assert r.objection.token_spent
        assert (r.objection.valid_from <= r.objection.index <= r.objection.valid_to) == r.objection.ok
    else:
        assert r.objection_slot is None
    expected = {
        ("kept", False): "kept",
        ("kept", True): "kept_objection_failed",
        ("stolen", True): "stolen",
        ("discarded", False): "discarded",
        ("discarded", True): "discarded_objection_failed",
    }[(r.outcome, r.objection is not None)]
    assert r.headline == expected


def check_hints(room: Room) -> None:
    turn = room.turn
    if "hint" in room.timers or "hint" in room.frozen:
        assert turn is not None and turn.hints_used, "hint timer without hints"
        assert turn.hint_deadline_ts is not None
        assert room.phase in (Phase.PLACING, Phase.GUESSING, Phase.PAUSED)
    if turn is not None:
        assert len(set(turn.hints_used)) == len(turn.hints_used) <= 2
        assert turn.audio_commands >= 0
        assert 0 <= turn.place_changes <= 3
        if room.phase == Phase.PLACING:
            assert turn.placed_index is None and not turn.guessed, "PLACING keeps a placement"
        if room.phase == Phase.GUESSING:
            assert turn.placed_index is not None, "GUESSING without placement"
    if room.phase in (Phase.OBJECTION, Phase.REVEAL, Phase.GAME_OVER, Phase.LOBBY):
        assert "hint" not in room.timers and "hint" not in room.frozen, "hint timer outlived GUESSING"


def check_ranking(room: Room) -> None:
    """Final ranking: by cards only, competition ranks (1, 1, 3), winners = rank 1."""
    rows = standings(room)
    claimed = [t for t in room.teams if t.claimed]
    assert [r.slot for r in rows] == [r.slot for r in sorted(rows, key=lambda r: (r.rank, r.slot))]
    assert {r.slot for r in rows} == {t.slot for t in claimed}
    for r in rows:
        better = sum(1 for o in rows if o.cards > r.cards)
        assert r.rank == better + 1, f"rank {r.rank} != {better + 1} for slot {r.slot}"
        assert all(o.rank == r.rank for o in rows if o.cards == r.cards), "tied teams differ in rank"
    assert sorted(room.winners) == [r.slot for r in rows if r.rank == 1], "winners != rank 1"


def check_invariants(room: Room, expected_total: int) -> None:
    for t in room.teams:
        assert is_sorted(t.timeline), f"timeline of {t.slot} not sorted"
        assert t.tokens >= 0
    if room.phase not in (Phase.LOBBY,):
        assert total_cards(room) == expected_total, "cards not conserved"
    if room.turn is not None and room.turn.result is not None:
        check_result(room)
    ids = [c.instance_id for t in room.teams for c in t.timeline] + [c.instance_id for c in room.deck]
    ids += [c.instance_id for c in room.discard]
    assert len(ids) == len(set(ids)), "duplicate card"
    check_hints(room)
    if room.phase == Phase.GAME_OVER:
        assert room.winners, "no winners"
        check_ranking(room)


def setup_lobby(
    team_count: int = 3,
    mode: str = "voice",
    target: int = 10,
    code: str = "0001",
    objection_window_s: int = 15,
    initial_tokens: int = 0,
    hints_enabled: bool = True,
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
                "initial_tokens": initial_tokens,
                "hints_enabled": hints_enabled,
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
    hints: int = 0
    cancels: int = 0


def play_game(
    seed: int,
    *,
    check_leaks: bool = False,
    team_count: int | None = None,
    mode: str | None = None,
    songs: tuple[Song, ...] | None = None,
    target: int | None = None,
    on_step: Callable[[Room], None] | None = None,
    end_p: float = 0.0,
) -> tuple[Room, GameStats]:
    rng = random.Random(seed)
    end_rng = random.Random(seed + 7919)  # separate stream: other seeds keep their games
    tc = team_count or rng.randint(2, 4)
    md = mode or rng.choice(["voice", "app"])
    tg = target or rng.choice([3, 5, 10])
    songs = songs or make_songs(rng.choice([8, 15, 60]), seed=seed)
    hint_rng0 = random.Random(seed + 104729)
    room = setup_lobby(
        tc, md, tg, initial_tokens=hint_rng0.choice([0, 1, 2, 3]), hints_enabled=hint_rng0.random() < 0.8
    )
    now = 100.0
    room, _ = reduce(room, C.Start(0, songs, seed), now)
    expected_total = len(set(s.id for s in songs)) if len(songs) >= tc + 1 else len(songs)
    skill = rng.choice([0.2, 0.5, 0.9])
    hint_rng = random.Random(seed + 104730)  # separate stream: hints do not change the other games
    hint_p = hint_rng.choice([0.0, 0.2, 0.6])
    hint_expire_p = hint_rng.choice([0.0, 0.3])
    cancel_rng = random.Random(seed + 104731)  # separate stream again
    cancel_p = cancel_rng.choice([0.0, 0.3, 0.7])
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

    def try_hint() -> bool:
        """Maybe ask for a hint; returns True if the state moved or a timer fired (caller re-reads it)."""
        nonlocal now
        t = room.turn
        assert t is not None
        if "hint" in room.timers and hint_rng.random() < hint_expire_p:
            now = max(now, room.timers["hint"].deadline_ts)
            step(fire(room, "hint"))
            return True
        if hint_rng.random() >= hint_p:
            return False
        kind = hint_rng.choice(["artist", "title"])
        before = room.teams[t.team_slot].tokens
        try:
            step(C.UseHint(t.team_slot, kind))
        except GameError as e:
            assert e.code in ("no_tokens", "hint_already_used", "hints_disabled"), e.code
            assert room.teams[t.team_slot].tokens == before
            return False
        assert room.teams[t.team_slot].tokens == before - 1
        stats.hints += 1
        return False

    def try_cancel() -> bool:
        """Maybe go back from GUESSING to PLACING; checks the guards. True if the state moved."""
        t = room.turn
        assert t is not None and room.phase == Phase.GUESSING
        if cancel_rng.random() >= cancel_p:
            return False
        # a stranger can never cancel
        other = next((x.slot for x in room.teams if x.claimed and x.slot != t.team_slot), None)
        if other is not None:
            try:
                reduce(room, C.PlaceCancel(other), now)
                raise AssertionError("place_cancel accepted from another team")
            except GameError as e:
                assert e.code == "not_your_turn", e.code
        allowed = not t.guessed and not t.placed_auto and t.place_changes < 3
        snapshot = room.model_dump()
        before = (t.place_changes, t.preview_index, [tm.tokens for tm in room.teams], list(t.hints_used))
        try:
            step(C.PlaceCancel(t.team_slot))
        except GameError as e:
            assert not allowed, f"rejected {e.code} but allowed"
            assert e.code in ("wrong_phase", "already_guessed", "too_many_changes"), e.code
            assert room.model_dump() == snapshot, "rejected place_cancel changed the state"
            return False
        assert allowed, "accepted but should be rejected"
        t2 = room.turn
        assert t2 is not None and room.phase == Phase.PLACING and t2.placed_index is None
        assert (t2.place_changes, t2.preview_index) == (before[0] + 1, before[1])
        assert ([tm.tokens for tm in room.teams], list(t2.hints_used)) == (before[2], before[3])
        stats.cancels += 1
        return True

    while room.phase != Phase.GAME_OVER:
        if stats.steps > MAX_STEPS:
            raise AssertionError(f"game {seed} did not finish (phase={room.phase})")
        ph = room.phase
        turn = room.turn
        if end_p and end_rng.random() < end_p:
            step(C.EndGame(room.host_slot))  # the host ends the game in any in-game phase
            continue
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
            if try_hint() or room.phase != Phase.PLACING:
                continue
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
            if try_hint() or room.phase != Phase.GUESSING:
                continue
            if try_cancel():
                continue
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
    for viewer in [None, *range(len(room.teams))]:
        t = view_json(room, viewer).get("turn")
        assert t is None or t.get("result") is None, "result leaked before REVEAL"
        assert "songYear" not in json.dumps(t), "songYear leaked before REVEAL"
    c = turn.card
    for viewer in [None, *range(len(room.teams))]:
        view = view_json(room, viewer)
        hints = (view.get("turn") or {}).get("hints")
        if viewer == turn.team_slot and view.get("turn"):
            view["turn"].pop("guess", None)  # the active team sees what it typed itself
            used = {h["kind"]: h["masked"] for h in (hints or {}).get("used", [])}
            assert list(used) == turn.hints_used
            for kind, masked in used.items():
                src = c.artist if kind == "artist" else c.title
                assert masked == mask_text(src, hint_seed(c.instance_id, kind))
        else:
            assert "masked" not in json.dumps(view), "masked hint text sent to a non-active viewer"
            if hints is not None:
                assert all(set(h) == {"kind"} for h in hints["used"])
        blob = json.dumps(view, ensure_ascii=False)
        assert c.title not in blob and c.artist not in blob, "title/artist leaked"
        assert c.track_id not in blob or not c.track_id, "track_id leaked"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int, nargs="?", default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--leaks", action="store_true", help="check the anti-cheat projection at every step")
    ap.add_argument("--end-p", type=float, default=0.0, help="per-step chance that the host ends the game")
    args = ap.parse_args()
    t0 = time.time()
    reasons: dict[str | None, int] = {}
    steps = pauses = skipped = objections = hints = cancels = 0
    for i in range(args.n):
        _, st = play_game(args.seed + i, check_leaks=args.leaks, end_p=args.end_p)
        reasons[st.reason] = reasons.get(st.reason, 0) + 1
        steps += st.steps
        pauses += st.pauses
        skipped += st.skipped
        objections += st.objections
        hints += st.hints
        cancels += st.cancels
    print(
        f"OK: {args.n} games finished in {time.time() - t0:.1f}s | endings={reasons} "
        f"steps={steps} pauses={pauses} skipped_turns={skipped} objections={objections} hints={hints} cancels={cancels}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
