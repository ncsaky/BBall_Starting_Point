"""Regression: leftover box-score units must not always go to the same players.

redistribute_integer_stat used to break ties by player id, so across a season the same players (ids sorting
early, e.g. first names A-D) got zero steals and blocks while teammates with equal chances got all of them.
"""
import unittest
from collections import Counter

from nba_gm_data.sim import redistribute_integer_stat


class TiebreakTests(unittest.TestCase):
    def test_ties_spread_across_players_over_many_games(self):
        wins = Counter()
        for game in range(400):
            lines = [{"player_id": f"player_tm-{name}", "minutes": 24.0, "points": 10 + game % 17, "steals": 1}
                     for name in ("aaron", "bruce", "collin", "zach", "yuri", "xavier")]
            lines[0]["points"] += game  # game-specific box scores
            redistribute_integer_stat(lines, "steals", 3, 1.55)
            self.assertEqual(sum(line["steals"] for line in lines), 3)
            for line in lines:
                wins[line["player_id"]] += line["steals"]
        # Equal chances -> each player gets roughly half the games' steals (3 of 6 per game); none starved.
        for player, count in wins.items():
            self.assertGreater(count, 120, (player, wins))
            self.assertLess(count, 280, (player, wins))

    def test_deterministic_for_the_same_game(self):
        def run():
            lines = [{"player_id": f"p{i}", "minutes": 20.0, "points": i, "blocks": 1} for i in range(8)]
            redistribute_integer_stat(lines, "blocks", 3, 2.0)
            return [line["blocks"] for line in lines]
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()


class ReboundRateTests(unittest.TestCase):
    def test_taller_and_better_rebounders_get_more_chances(self):
        from nba_gm_data.sim import rebound_rate_per_minute
        guard = rebound_rate_per_minute({"height_inches": 75}, {"offensive_rebounding": 40})
        center = rebound_rate_per_minute({"height_inches": 84}, {"offensive_rebounding": 40})
        crasher = rebound_rate_per_minute({"height_inches": 84}, {"offensive_rebounding": 90})
        self.assertLess(guard, center)
        self.assertLess(center, crasher)
        self.assertGreater(guard * 36, 1.4)          # bounded, never zero
        self.assertLess(rebound_rate_per_minute({"height_inches": 92}, {"offensive_rebounding": 99}) * 36, 16.01)


class LeagueOffenseCalibrationTests(unittest.TestCase):
    def test_only_new_ratings_mode_gets_the_scoring_calibration(self):
        from nba_gm_data.sim import INPUTS_OFFENSE_CALIBRATION, league_offense_calibration
        from nba_gm_data.ratings_model import MODEL_KEY, INPUTS_V1
        self.assertEqual(league_offense_calibration({}), 0.0)
        self.assertEqual(league_offense_calibration({MODEL_KEY: {"mode": INPUTS_V1}}), INPUTS_OFFENSE_CALIBRATION)
        self.assertGreater(INPUTS_OFFENSE_CALIBRATION, 0)


class RustDisplayTests(unittest.TestCase):
    def test_display_matches_the_engine_penalty(self):
        from nba_gm_data.sim import health_adjusted_player_features, rust_display, rust_penalty_points
        from nba_gm_data.save import player_health_label
        from nba_gm_data.app_actions import health_label
        state = {"availability_status": "active", "rust": 16.0, "fatigue": 0.0}
        shown = rust_display(state)
        self.assertEqual(shown["rust_penalty"], round(rust_penalty_points(16.0), 1))
        self.assertEqual(shown["rust_days"], 3)
        # The engine lowers in-game impact by exactly that penalty (impact weight 1.0).
        adjusted = health_adjusted_player_features({"impact": 60.0}, {"health_rust": 16.0, "health_fatigue": 0.0})
        self.assertAlmostEqual(60.0 - adjusted["impact"], rust_penalty_points(16.0), places=3)
        self.assertEqual(player_health_label(state, "2026-11-20")["rust_penalty"], shown["rust_penalty"])
        self.assertEqual(health_label(state)["rust_penalty"], shown["rust_penalty"])
        self.assertEqual(rust_display({"availability_status": "out", "rust": 16.0}), {})   # still out: no rust marker
        self.assertNotIn("rust_penalty", health_label({"availability_status": "active", "rust": 0.0}))
