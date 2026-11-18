"""Player value fitted to real impact keeps the existing rating scale and follows the fitted order."""
import unittest
from pathlib import Path

from nba_gm_data import impact_value as iv

ROOT = Path(__file__).resolve().parents[1]


class MappingTests(unittest.TestCase):
    def test_rank_mapping_keeps_the_target_scale_and_the_prediction_order(self):
        predictions = {f"p{i}": {"offense": i * 0.1, "defense": -i * 0.05, "overall": i * 0.05} for i in range(100)}
        target = [40.0 + i * 0.3 for i in range(100)]          # existing scale, e.g. legacy overall
        tables = iv.build_tables(predictions, {"overall": target, "defense": target})
        mapped = [iv.mapped(tables, predictions[f"p{i}"], "overall") for i in range(100)]
        self.assertEqual(mapped, sorted(mapped))                  # order follows the prediction
        self.assertGreaterEqual(min(mapped), min(target))         # stays inside the existing range
        self.assertLessEqual(max(mapped), max(target))
        self.assertAlmostEqual(sorted(mapped)[50], sorted(target)[50], delta=0.5)   # same middle
        defense = [iv.mapped(tables, predictions[f"p{i}"], "defense") for i in range(100)]
        self.assertEqual(defense, sorted(defense, reverse=True))  # defense side used for defense


@unittest.skipUnless((ROOT / iv.FIT_FILE).exists(), "impact fit not present")
class FitFileTests(unittest.TestCase):
    def test_fit_has_both_sides_and_reasonable_validation(self):
        fit = iv.load_fit(ROOT)
        self.assertEqual(set(fit["coefficients"]), {"offense", "defense"})
        for side in ("offense", "defense"):
            self.assertEqual(len(fit["coefficients"][side]["weights"]), len(iv.PREDICTORS))
        self.assertGreater(fit["cv_weighted_corr"]["overall"], 0.7)

    def test_rim_protector_beats_small_guard_on_defense(self):
        fit = iv.load_fit(ROOT)
        big = {t: 50.0 for t in iv.LEGACY_TRAITS}; big.update(rim_deterrence=95.0, defensive_effort=85.0)
        guard = {t: 50.0 for t in iv.LEGACY_TRAITS}; guard.update(rim_deterrence=20.0, defensive_effort=40.0)
        self.assertGreater(iv.predict(fit, big, {"height_inches": 85})["defense"],
                           iv.predict(fit, guard, {"height_inches": 74})["defense"])

    def test_involvement_pays_off_with_skill_and_better_skill_never_lowers_value(self):
        fit = iv.load_fit(ROOT)
        traits = {t: 50.0 for t in iv.LEGACY_TRAITS}

        def inputs(grade, involvement):
            ids = [i for group in ("in_shooting", "in_creation", "in_finishing") for i in iv.INPUT_GROUPS[group]]
            out = {i: {"value": {"grade": grade}} for i in ids}
            out["T08"] = {"value": {"probability": involvement}}
            return out

        def offense(grade, involvement):
            return iv.predict(fit, traits, {"height_inches": 78}, {}, inputs(grade, involvement))["offense"]

        for involvement in (0.12, 0.30, 0.50):
            values = [offense(g, involvement) for g in (30, 45, 60, 75, 90)]
            self.assertEqual(values, sorted(values), involvement)            # monotone in skill at every usage level
        # Taking on more of the offense is worth more to a skilled creator than to an unskilled one.
        self.assertGreater(offense(80, 0.45) - offense(80, 0.20), offense(40, 0.45) - offense(40, 0.20))

    def test_offensive_rebounding_adds_offense_only(self):
        fit = iv.load_fit(ROOT)
        traits = {t: 50.0 for t in iv.LEGACY_TRAITS}
        values = []
        for rating in (20.0, 60.0, 85.0, 95.0, 99.0):
            values.append(iv.predict(fit, {**traits, "offensive_rebounding": rating}, {"height_inches": 83}, {}, {}))
        offense = [v["offense"] for v in values]
        self.assertEqual(offense, sorted(offense))                       # a better rebounder never loses value
        self.assertGreater(offense[-1] - offense[2], 0.2)                # the top crashers separate (production scale)
        self.assertEqual(len({round(v["defense"], 9) for v in values}), 1)   # no defensive credit for crashing

    def test_rebound_production_scale_is_monotone_and_not_clipped(self):
        points = [iv.orb_per75(x) for x in range(0, 111, 5)]
        self.assertEqual(points, sorted(points))
        self.assertGreater(iv.orb_per75(108.0), iv.orb_per75(103.0))  # beyond the last knot the top keeps rising


if __name__ == "__main__":
    unittest.main()
