"""Playoff Stats card payload: real playoff totals, per-playoff-game averages and shooting percentages."""
import unittest
from unittest import mock

from nba_gm_data import save as sv


CANONICAL = {
    "players": [
        {"id": "p1", "name": "Alpha One", "headshot_url": "https://example.test/a.png"},
        {"id": "p2", "name": "Bravo Two"},
    ],
    "teams": [],
}

SAVE = {
    "state": {"current_date": "2027-05-01", "phase": "playoffs"},
    # Regular-season totals must never leak into playoff denominators.
    "player_season_stats": {"p1": {"games": 80, "minutes": 2800, "points": 2000}},
    "playoff_player_stats": {
        "p1": {
            "player_id": "p1", "team_id": "t1", "team_abbrev": "AAA", "games": 4,
            "minutes": 144, "points": 100, "rebounds": 20, "assists": 12, "steals": 4, "blocks": 2,
            "turnovers": 8, "fgm": 36, "fga": 80, "fg3m": 10, "fg3a": 25, "ftm": 18, "fta": 20,
        },
        "p2": {
            "player_id": "p2", "team_id": "t2", "team_abbrev": "BBB", "games": 2,
            "minutes": 40, "points": 30, "fgm": 12, "fga": 20, "ftm": 6, "fta": 8,
        },
    },
}


def run_view(**kwargs):
    with mock.patch.object(sv, "load_save", return_value=SAVE), \
            mock.patch.object(sv, "ensure_league_save_defaults", side_effect=lambda save, canonical: save):
        return sv.playoff_leaders(CANONICAL, "unused.json", **kwargs)


class PlayoffStatsViewTests(unittest.TestCase):
    def test_rows_carry_full_playoff_line_with_playoff_game_denominators(self):
        view = run_view(stat="points", limit=50)
        self.assertEqual([row["player_id"] for row in view["leaders"]], ["p1", "p2"])
        top = view["leaders"][0]
        self.assertEqual(top["player_name"], "Alpha One")
        self.assertEqual(top["headshot_url"], "https://example.test/a.png")
        self.assertEqual(top["games"], 4)
        self.assertEqual(top["points_per_game"], 25.0)
        self.assertEqual(top["minutes_per_game"], 36.0)
        self.assertEqual(top["rebounds_per_game"], 5.0)
        self.assertEqual(top["assists_per_game"], 3.0)
        self.assertEqual(top["steals_per_game"], 1.0)
        self.assertEqual(top["blocks_per_game"], 0.5)
        self.assertEqual(top["fg3m_per_game"], 2.5)
        self.assertEqual(top["fg_pct"], 45.0)
        self.assertEqual(top["fg3_pct"], 40.0)
        self.assertEqual(top["ft_pct"], 90.0)
        self.assertEqual(top["points"], 100.0)

    def test_missing_attempts_give_no_percentage_and_zero_fields(self):
        second = run_view(stat="points", limit=50)["leaders"][1]
        self.assertIsNone(second["fg3_pct"])
        self.assertEqual(second["fg_pct"], 60.0)
        self.assertEqual(second["rebounds_per_game"], 0.0)
        self.assertNotIn("headshot_url", {key for key, value in second.items() if value})

    def test_existing_single_stat_contract_still_holds(self):
        view = run_view(stat="ast", limit=1)
        self.assertEqual(view["stat"], "assists")
        self.assertEqual(len(view["leaders"]), 1)
        self.assertEqual(view["leaders"][0]["assists_per_game"], 3.0)
        self.assertEqual(view["leaders"][0]["player"]["name"], "Alpha One")


if __name__ == "__main__":
    unittest.main()
