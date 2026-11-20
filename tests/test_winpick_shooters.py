"""Who scores can no longer change who wins; spot-up shooters keep their made threes (2026-11-19)."""
from __future__ import annotations

import random
import statistics
import unittest
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import box_rates, box_variation, offense, sim


class ScoreStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(Path(__file__).resolve().parents[1])
        cls.games = sim.validation_game_ids(cls.context, through_date=None, playoffs=False)[:12]

    def scores(self, mode):
        return [(r.home_score, r.away_score) for r in
                (sim.sim_game_with_context(self.context, gid, mode=mode, seed=seed)
                 for gid in self.games for seed in (1, 2, 3))]

    def test_box_score_random_draws_cannot_change_any_score(self):
        original = sim.distribute_player_lines

        def greedy(canonical, team, pool, team_points, possessions, rng):
            for _ in range(17):   # a box score that uses more random numbers than before
                rng.random()
            return original(canonical, team, pool, team_points, possessions, rng)

        for mode in ("replay-real-minutes", "sandbox-sim"):
            before = self.scores(mode)
            with patch.object(sim, "distribute_player_lines", side_effect=greedy):
                after = self.scores(mode)
            self.assertEqual(before, after, mode)

    def test_points_share_fit_cannot_change_any_score(self):
        before = self.scores("replay-real-minutes")
        changed = {**box_rates.POINTS_INPUTS, "log T09": 0.6, "S.three_mode": 0.02}
        with patch.object(box_rates, "POINTS_INPUTS", changed):
            sim.invalidate_sim_cache(self.context["canonical"])
            after = self.scores("replay-real-minutes")
        sim.invalidate_sim_cache(self.context["canonical"])
        self.assertEqual(before, after)


class ShooterPointsTests(unittest.TestCase):
    def test_blend_leaves_non_shooters_alone(self):
        self.assertEqual(box_rates.shot_points_blend(20.0, 0.25, 4.0, .36, .55, .3, .8), 20.0)
        self.assertEqual(box_rates.shot_points_blend(20.0, None, 4.0, .36, .55, .3, .8), 20.0)

    def test_pure_shooter_gets_the_points_his_shots_make(self):
        # AJ Green-like: 8.6 threes per 36 at .415, 85% of his shots from three.
        fit = 11.8
        shots = (3 * 8.6 * .415 + 2 * 8.6 * .15 / .85 * .468) / (1 - .1 * .85 * .98)
        blended = box_rates.shot_points_blend(fit, .85, 8.6, .415, .468, .1, .85)
        self.assertAlmostEqual(blended, shots, places=6)
        shots55 = (3 * 8.6 * .415 + 2 * 8.6 * .45 / .55 * .468) / (1 - .1 * .85 * .98)
        partial = box_rates.shot_points_blend(fit, .55, 8.6, .415, .468, .1, .85)
        self.assertTrue(min(fit, shots55) < partial < max(fit, shots55))


class OwnRateMissesTests(unittest.TestCase):
    def test_two_point_rate_follows_his_points_left_after_threes(self):
        shooter = {"points_per36": 13.0, "three_per36": 8.6, "three_pct": .415, "two_pct": .47, "fta_per_point": .1,
                   "ft_pct": .85}
        big = {"points_per36": 18.0, "three_per36": 0.2, "three_pct": .3, "two_pct": .62, "fta_per_point": .3,
               "ft_pct": .7}
        self.assertLess(box_variation.two_attempts_per36(shooter), 2.0)
        self.assertGreater(box_variation.two_attempts_per36(big), 10.0)
        self.assertIsNone(box_variation.two_attempts_per36({"two_pct": .5}))   # old ratings keep the old rule

    def test_misses_average_his_own_percentage(self):
        # Poisson attempts at rate a, each in with p: the per-make draw thinned by P(at least one make) plus the
        # no-make misses average a x (1 - p) whatever the makes were.
        rng = random.Random(3)
        a, p = 1.2, .47
        thin = 1 - 2.718281828459045 ** (-a * p)
        misses = []
        for _ in range(40000):
            makes = sum(rng.random() < p for _ in range(poisson(rng, a)))
            if makes == 0:
                misses.append(box_variation.poisson(rng, a * (1 - p)))
            else:
                misses.append(box_variation.missed_attempts(rng, makes, p / (p + thin * (1 - p)), upper=.97))
        self.assertAlmostEqual(statistics.fmean(misses), a * (1 - p), delta=.03)


def poisson(rng, mean):
    return box_variation.poisson(rng, mean)


class ThreesFirstTests(unittest.TestCase):
    def test_room_for_threes_keeps_team_total_and_takes_from_teammates(self):
        pool = [{"player": {"id": f"p{i}"}} for i in range(4)]
        points = [6, 20, 12, 8]
        pre = [(9, 4), None, None, (5, 1)]   # p0 made 4 threes (12 points) but was handed 6
        out = sim.make_room_for_threes(pool, {}, points, pre)
        self.assertEqual(sum(out), sum(points))
        self.assertGreaterEqual(out[0], 12)
        self.assertGreaterEqual(out[3], 3)
        self.assertLess(out[1], 20)
        self.assertLess(out[2], 12)
        self.assertEqual(sim.make_room_for_threes(pool, {}, [12, 20, 12, 8], pre), [12, 20, 12, 8])

    def test_shooting_line_keeps_drawn_threes_and_free_throws_give_way(self):
        feat = {"rim_pressure": 40, "shot_creation": 40, "ft_pct": .9, "fta_per_point": .2, "three_per36": 9.0,
                "three_pct": .42, "two_pct": .5}
        for seed in range(200):
            line = offense.shooting_line(12, feat, 30.0, random.Random(seed), 11.0, threes=(8, 4))
            self.assertEqual(line["fg3m"], 4)
            self.assertEqual(line["fg3a"], 8)
            self.assertEqual(3 * line["fg3m"] + 2 * (line["fgm"] - line["fg3m"]) + line["ftm"], 12)


if __name__ == "__main__":
    unittest.main()
