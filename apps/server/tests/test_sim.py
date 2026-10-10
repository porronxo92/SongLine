from tests.sim.run_bots import play_game


def test_bot_games_always_finish() -> None:
    reasons = set()
    for seed in range(60):
        room, stats = play_game(seed, check_leaks=True)
        assert room.winners
        reasons.add(stats.reason)
    assert reasons == {"target", "deck_exhausted"}


def test_bots_with_all_team_counts_and_modes() -> None:
    for teams in (2, 3, 4):
        for mode in ("voice", "app"):
            room, _ = play_game(1000 + teams, team_count=teams, mode=mode)
            assert room.phase == "game_over"
