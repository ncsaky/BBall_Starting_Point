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
