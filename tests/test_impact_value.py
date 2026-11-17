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


if __name__ == "__main__":
    unittest.main()
