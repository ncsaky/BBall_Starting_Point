"""Overnight ratings review (2026-11-20): bench press read net of arm length; rebound weights for the new grade."""
from __future__ import annotations

import math
import random
import unittest

from nba_gm_data import box_rates, physical_evidence as pe


def _synthetic(elasticity: float, n: int = 200, seed: int = 7):
    rng = random.Random(seed)
    raw, body = {}, {}
    for i in range(n):
        wing = rng.gauss(208, 9)
        mass = rng.gauss(100, 10)
        strength = rng.gauss(0, 0.2)   # same distribution for every arm length
        reps = 10 * (wing / 208) ** elasticity * (mass / 100) ** 3 * math.exp(strength)
        raw[f"p{i}"] = reps
        body[f"p{i}"] = {"wingspan": wing, "mass": mass}
    return raw, body


class ArmLengthTests(unittest.TestCase):
    def test_long_arms_gain_reps_and_short_arms_lose_them(self):
        raw, body = _synthetic(-6.0)
        out, report = pe.arm_length_adjusted_reps(raw, body)
        ref = report["reference_wingspan_cm"]
        for pid in raw:
            if body[pid]["wingspan"] > ref + 1:
                self.assertGreater(out[pid], raw[pid])
            elif body[pid]["wingspan"] < ref - 1:
                self.assertLess(out[pid], raw[pid])

    def test_elasticity_is_the_fit_shrunk_toward_physics(self):
        raw, body = _synthetic(-6.0)
        _, report = pe.arm_length_adjusted_reps(raw, body)
        self.assertLess(report["fitted_elasticity"], -4.0)
        used = report["elasticity_used"]
        self.assertTrue(report["fitted_elasticity"] <= used <= pe.ARM_PRIOR, report)

    def test_adjusted_reps_no_longer_follow_arm_length(self):
        raw, body = _synthetic(-6.0, n=400)
        out, report = pe.arm_length_adjusted_reps(raw, body)
        # With a precise fit (large sample) the prior hardly matters and the arm effect is gone.
        x = [[1.0, math.log(body[p]["wingspan"]), math.log(body[p]["mass"])] for p in out]
        beta, _ = pe._ols(x, [math.log(out[p]) for p in out])
        self.assertLess(abs(beta[1]), abs(report["fitted_elasticity"]) * 0.2)
        self.assertAlmostEqual(beta[2], report["mass_elasticity"], places=2)   # mass keeps its effect

    def test_small_samples_are_left_alone(self):
        raw, body = _synthetic(-6.0, n=10)
        out, report = pe.arm_length_adjusted_reps(raw, body)
        self.assertEqual(out, raw)
        self.assertIn("skipped", report)


class ReboundWeightTests(unittest.TestCase):
    def test_positioning_grade_carries_weight(self):
        w = box_rates.REBOUNDS_INPUTS
        self.assertGreater(w["S30"], 0.006)
        self.assertGreater(w["S31"], 0)
        self.assertGreater(w["S32"], 0)


if __name__ == "__main__":
    unittest.main()
