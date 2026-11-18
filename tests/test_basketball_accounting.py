import copy
from collections import Counter
import random
import unittest

from nba_gm_data import sim


def assert_shooting(test, row):
    test.assertEqual(row["points"], 2*row["fgm"]+row["fg3m"]+row["ftm"])
    test.assertTrue(0 <= row["ftm"] <= row["fta"])
    test.assertTrue(0 <= row["fg3m"] <= row["fg3a"] <= row["fga"])
    test.assertTrue(0 <= row["fgm"]-row["fg3m"] <= row["fga"]-row["fg3a"])


class BasketballAccountingTests(unittest.TestCase):
    def test_reconstructed_shooting_keeps_profile_without_inventing_missed_volume(self):
        rng = random.Random(23)
        totals = Counter()
        for _ in range(300):
            for points, minutes in [(0,5),(2,8),(5,12),(8,18),(12,25),(20,32),(30,36)]:
                for rating in [40,70,90]:
                    feat = {"spacing":rating,"rim_pressure":rating,"shot_creation":rating,"usage":rating}
                    totals.update(sim.shooting_line(points, feat, minutes, rng))
        # Internal model guardrails, not a claim of real-world league calibration.
        self.assertTrue(.40 < totals["fgm"] / totals["fga"] < .46)
        self.assertTrue(.32 < totals["fg3m"] / totals["fg3a"] < .37)
        self.assertTrue(.74 < totals["ftm"] / totals["fta"] < .82)

    def test_shooting_counts_reconcile_for_low_and_high_scoring_profiles(self):
        for seed in range(20):
            for points in range(81):
                for rating in [30, 70, 99]:
                    feat = {"spacing":rating,"rim_pressure":rating,"shot_creation":rating,"usage":rating}
                    row = {"points":points, **sim.shooting_line(points, feat, 36, random.Random(seed))}
                    with self.subTest(seed=seed, points=points, rating=rating):
                        assert_shooting(self, row)

    def fixture(self):
        lines = [{"player_id":str(i),"points":20,"minutes":48,"fgm":8,"fga":16,
                  "fg3m":2,"fg3a":6,"ftm":2,"fta":2} for i in range(5)]
        team = {"points":100,"possessions":100,"off_rating":100,
                **{key:sum(row[key] for row in lines) for key in ["fgm","fga","fg3m","fg3a","ftm","fta"]}}
        return lines, team

    def test_overtime_increments_have_valid_shooting_for_every_point_remainder(self):
        for points in range(21):
            lines = [{"points":0,"minutes":48,"fgm":0,"fga":0,"fg3m":0,"fg3a":0,"ftm":0,"fta":0}]
            sim.add_overtime_points(lines, points)
            assert_shooting(self, lines[0])
            self.assertEqual(lines[0]["points"], points)

    def test_game_day_rotation_varies_targets_without_adding_players_or_minutes(self):
        targets = [40, 37, 34, 30, 29, 25, 21, 15, 8, 1, 0]
        self.assertEqual(sum(targets), 240)
        pool = [{"minutes": minutes} for minutes in targets]
        games = [sim.game_day_rotation(pool, "home", f"game-{i}", 17) for i in range(100)]
        for players in games:
            self.assertEqual(sum(round(item["minutes"] * 100) for item in players), 24000)
            self.assertEqual(players[-1]["minutes"], 0)
            self.assertTrue(all(0 <= item["minutes"] <= 48 for item in players))
        self.assertEqual([item["minutes"] for item in pool], targets)
        self.assertEqual(games[0], sim.game_day_rotation(pool, "home", "game-0", 17))
        lead_minutes = [players[0]["minutes"] for players in games]
        self.assertGreater(max(lead_minutes) - min(lead_minutes), 6)
        self.assertAlmostEqual(sum(lead_minutes) / len(games), 40, delta=.75)

    def test_short_handed_rotation_keeps_five_full_game_players(self):
        pool = [{"minutes": 48}] * 5
        self.assertEqual(sim.game_day_rotation(pool, "home", "game-1", 17), pool)

    def test_overtime_updates_minutes_team_shooting_and_efficiency(self):
        for seed in range(50):
            home, home_team = self.fixture()
            away, away_team = self.fixture()
            periods = sim.resolve_overtime_if_tied(home, away, home_team, away_team, random.Random(seed))
            self.assertEqual(periods,1)
            self.assertNotEqual(home_team["points"],away_team["points"])
            for lines, team in [(home,home_team),(away,away_team)]:
                self.assertEqual(sum(row["minutes"] for row in lines),265)
                self.assertTrue(all(row["minutes"]<=53 for row in lines))
                self.assertEqual(sum(row["points"] for row in lines),team["points"])
                for row in [*lines,team]:
                    assert_shooting(self,row)
                for key in ["fgm","fga","fg3m","fg3a","ftm","fta"]:
                    self.assertEqual(team[key],sum(row[key] for row in lines))
                self.assertEqual(team["off_rating"],round(team["points"]/team["possessions"]*100,2))

    def test_overtime_minutes_round_to_exact_team_total_and_leave_dnp_unchanged(self):
        lines = [{"minutes":value} for value in [42,38,36,32,30,24,18,12,8,0]]
        before = sum(row["minutes"] for row in lines)
        sim.add_overtime_minutes(lines)
        self.assertAlmostEqual(sum(row["minutes"] for row in lines),before+25)
        self.assertEqual(lines[-1]["minutes"],0)
        self.assertTrue(all(row["minutes"]<=53 for row in lines))

    def test_non_tied_games_are_not_changed(self):
        home, home_team = self.fixture()
        away, away_team = self.fixture()
        home_team["points"] = 101
        before = copy.deepcopy((home,away,home_team,away_team))
        rng = random.Random(7)
        rng_before = rng.getstate()
        self.assertEqual(sim.resolve_overtime_if_tied(home,away,home_team,away_team,rng),0)
        self.assertEqual((home,away,home_team,away_team),before)
        self.assertEqual(rng.getstate(),rng_before)

    def test_overtime_rounding_does_not_give_capped_players_more_than_five_minutes(self):
        values = [48,48,45.52,42.84,25.29,15.17,15.17]
        lines = [{"minutes":value} for value in values]
        sim.add_overtime_minutes(lines)
        self.assertAlmostEqual(sum(row["minutes"] for row in lines),sum(values)+25)
        self.assertTrue(all(row["minutes"]<=53 for row in lines))
        self.assertTrue(all(row["minutes"]-value<=5.000001 for row,value in zip(lines,values)))


if __name__ == "__main__":
    unittest.main()
