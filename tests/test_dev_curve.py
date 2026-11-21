"""DEV-CURVE (2026-11-21): development in the 94-input ratings follows real NBA development."""
import unittest

from nba_gm_data import health
from nba_gm_data import ratings_model as rm


def grade(v):
    return {"status": "estimated", "value": {"grade": v, "scale": "t"},
            "evidence": [{"source": "t", "method": "t"}], "uncertainty": {"confidence": "low", "notes": "{}"}}


def physical(v):
    return {"status": "estimated", "value": {"measurements": [], "display_grade": {"grade": v, "scale": "t"}},
            "evidence": [{"source": "t", "method": "t"}], "uncertainty": {"confidence": "low", "notes": "{}"}}


class GrowthDoesNotDependOnLevel(unittest.TestCase):
    PLAYER = {"id": "player_test_young_star", "age": 22, "minutes_projection": 30}

    def gain(self, current, age=22.0, trait="handle_pressure", **kwargs):
        return health.monthly_trait_delta(self.PLAYER, trait, current, age, 30.0, {}, 0.0, 17, "2026-12", 0.5,
                                          None, expected=True, **kwargs)

    def test_a_star_grows_as_fast_as_an_average_player(self):
        # Real players improve by about the same amount at every level once the level is measured apart from the
        # season being changed; the old rule cut a rating at 88+ to 8% of normal growth.
        self.assertAlmostEqual(self.gain(50.0), self.gain(90.0))
        self.assertAlmostEqual(self.gain(50.0), self.gain(105.0))
        self.assertGreater(self.gain(90.0), 0.0)

    def test_older_ratings_keep_their_level_rule(self):
        legacy = [self.gain(v, curve=health.LEGACY_CURVE) for v in (50.0, 70.0, 88.0)]
        self.assertEqual(legacy, sorted(legacy, reverse=True))
        self.assertLess(legacy[2], legacy[0] * 0.2)

    def test_focus_has_no_level_penalty_in_the_new_ratings(self):
        traits = {k: {"value": 90.0} for k in health.DEVELOPMENT_TRAITS}
        new = health.development_trait_focus(self.PLAYER, {}, traits, 17, "2026-12")
        old = health.development_trait_focus(self.PLAYER, {}, traits, 17, "2026-12", curve=health.LEGACY_CURVE)
        for key in health.DEVELOPMENT_TRAITS:
            self.assertAlmostEqual(old[key], round(new[key] * 0.68, 3), places=2)

    def test_growth_runs_into_the_mid_twenties_then_turns_to_decline(self):
        year = lambda age: sum(self.gain(60.0, age=age + m / 12.0) for m in range(12))
        self.assertGreater(year(20), year(23))
        self.assertGreater(year(23), year(25))
        self.assertGreater(year(24), 0.0)
        self.assertLess(year(31), 0.0)
        self.assertLess(year(35), year(31))


class RoutingByLeagueSpread(unittest.TestCase):
    def test_each_input_moves_by_its_own_league_spread(self):
        steps = rm._development_steps()
        self.assertTrue(steps, "spread table missing: run scripts/research/dev_curve_spread.py")
        # Conditioning varies about a quarter as much across the league as a technique grade, so the same development
        # moves it about a quarter as far (it used to move the same grade points and stamina jumped 10+ in a season).
        self.assertLess(steps["P11"], 0.5 * rm.GRADE_POINTS_PER_TRAIT_POINT)
        inputs = {"P11": physical(50), "P12": physical(50)}
        moved = rm.route_trait_deltas(inputs, {"stamina_cardio": 2.0})
        self.assertAlmostEqual(moved["P11"] / moved["P12"], steps["P11"] / steps["P12"], places=6)

    def test_grades_are_not_clipped_at_100(self):
        out = rm.apply_input_deltas({"S08": grade(99), "S09": grade(1)}, {"S08": 5, "S09": -5})
        self.assertEqual(out["S08"]["value"]["grade"], 104.0)
        self.assertEqual(out["S09"]["value"]["grade"], 0.0)


if __name__ == "__main__":
    unittest.main()
