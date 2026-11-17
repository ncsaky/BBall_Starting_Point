import unittest
from pathlib import Path

from nba_gm_data.calibration_targets import aggregate_from_results, compare, load_targets

TARGETS = Path(__file__).resolve().parents[1] / "data/calibration/nba_2025_26_targets.json"


def fake_result(gid, home, away, scale=1):
    def team(tid, pts):
        return {"team_id": tid, "points": pts, "possessions": 100.0, "fgm": 40, "fga": 90, "fg3m": 12, "fg3a": 35, "ftm": 18,
                "fta": 24, "offensive_rebounds": 10, "defensive_rebounds": 30, "rebounds": 40, "assists": 24, "turnovers": 13,
                "steals": 8, "blocks": 5, "personal_fouls": 20}
    def pl(pid, tid):
        return {"player_id": pid, "player_name": pid, "team_id": tid, "minutes": 48.0, "points": 24, "fga": 18, "fgm": 9, "fg3a": 6,
                "fta": 4, "ftm": 3, "rebounds": 8, "assists": 6, "turnovers": 2, "steals": 1, "blocks": 1}
    return {"game_id": gid, "team_lines": [team(home, 110), team(away, 104)],
            "player_lines": [pl("p_" + home, home), pl("p_" + away, away)]}


class CalibrationTargetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = load_targets(TARGETS)

    def test_league_ranges_sane(self):
        L = self.t["league"]
        self.assertTrue(95 <= L["pace"]["mean"] <= 105)
        self.assertTrue(105 <= L["off_rating"]["mean"] <= 122)
        self.assertTrue(0.30 <= L["fg3a_rate"]["mean"] <= 0.50)
        self.assertTrue(0.50 <= L["ts_pct"]["mean"] <= 0.62)
        for name, row in L.items():
            self.assertIsNotNone(row["mean"], name)
            self.assertGreater(row["std"], 0, name)

    def test_players_present(self):
        self.assertGreater(len(self.t["players"]), 250)
        self.assertGreaterEqual(self.t["player_match"]["match_rate"], 0.9)
        p = next(iter(self.t["players"].values()))
        self.assertIn("points_per36", p)

    def test_compare_on_exact_targets_is_all_within_band(self):
        league = {k: v["mean"] for k, v in self.t["league"].items()}
        players = {pid: {**p, "games": 40} for pid, p in self.t["players"].items()}
        rep = compare(league, players, self.t)
        self.assertTrue(rep["league_summary"]["all_within_band"])
        self.assertEqual(rep["players_compared"], 150)
        self.assertEqual(len(rep["largest_player_misses"]), 20)
        self.assertAlmostEqual(rep["largest_player_misses"][0]["z"], 0.0)

    def test_compare_flags_out_of_band(self):
        league = {k: v["mean"] for k, v in self.t["league"].items()}
        league["pace"] += 10 * self.t["league"]["pace"]["std"]
        rep = compare(league, {}, self.t)
        row = next(r for r in rep["league"] if r["metric"] == "pace")
        self.assertFalse(row["within_band"])
        self.assertFalse(rep["league_summary"]["all_within_band"])

    def test_aggregate_from_results(self):
        agg = aggregate_from_results([fake_result("g1", "A", "B"), fake_result("g2", "B", "A")])
        lg = agg["league_totals"]
        # possessions per team-game = 90 + 0.44*24 - 10 + 13 = 103.56
        self.assertAlmostEqual(lg["pace"], 103.56, places=2)
        self.assertAlmostEqual(lg["off_rating"], 100 * 107 / 103.56, places=2)
        self.assertAlmostEqual(lg["points_per_game"], 107.0)
        self.assertAlmostEqual(lg["fg3a_rate"], 35 / 90)
        self.assertAlmostEqual(lg["orb_pct"], 100 * 10 / 40)
        self.assertAlmostEqual(lg["ast_rate"], 24 / 40)
        pa = agg["player_lines"]["p_A"]
        self.assertEqual(pa["games"], 2)
        self.assertAlmostEqual(pa["points_per36"], 36 * 48 / 96)
        self.assertAlmostEqual(pa["ts_pct"], 48 / (2 * (36 + 0.44 * 8)))


if __name__ == "__main__":
    unittest.main()
