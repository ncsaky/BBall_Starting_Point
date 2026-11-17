import json
import unittest
from pathlib import Path

from nba_gm_data import bbi_evidence as be
from nba_gm_data.player_model_registry import definition_registry

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / be.MAPPING_FILE


class GradeScaleTests(unittest.TestCase):
    def test_grade_anchors_match_the_model_scale(self):
        from statistics import NormalDist
        z = NormalDist().inv_cdf
        self.assertAlmostEqual(be._grade_from_z(0.0), 50.0)
        self.assertAlmostEqual(be._grade_from_z(z(0.80)), 75.0, delta=1.0)   # "strong"
        self.assertAlmostEqual(be._grade_from_z(z(0.97)), 92.0, delta=2.5)   # "exceptional"
        self.assertLess(be._grade_from_z(5.0), 100.0)                        # never clipped / never 100
        self.assertGreater(be._grade_from_z(-5.0), 0.0)

    def test_percentiles_respect_direction_and_minutes_pool(self):
        values = {f"p{i}": (float(i), 1000.0, f"p{i}") for i in range(40)}
        values["bench"] = (100.0, 10.0, "bench")  # far above everyone but under the minutes pool
        up = be._percentiles(values, 1)
        down = be._percentiles(values, -1)
        self.assertGreater(up["p39"], up["p0"])
        self.assertLess(down["p39"], down["p0"])
        self.assertGreater(up["bench"], up["p39"])  # ranked against the pool, not part of it
        self.assertLess(up["bench"], 1.0)

    def test_per_exposure_turns_counts_into_rates(self):
        counts = {"creator": (4.0, 2000.0, "creator"), "big": (1.0, 2000.0, "big"), "nodata": (2.0, 2000.0, "nodata")}
        touches = {"creator": (100.0, 2000.0, "creator"), "big": (20.0, 2000.0, "big")}
        rates = be._per_exposure(counts, touches)
        self.assertAlmostEqual(rates["creator"][0], 0.04)
        self.assertAlmostEqual(rates["big"][0], 0.05)   # fewer turnovers, but more per touch
        self.assertNotIn("nodata", rates)

    def test_small_pools_are_ignored(self):
        self.assertEqual(be._percentiles({"a": (1.0, 900.0, "a")}, 1), {})


class OverlayTests(unittest.TestCase):
    def _section(self):
        players = {}
        for i in range(60):
            players[f"p{i}"] = {"inputs": {
                "S01": {"status": "estimated", "reason": "prior", "value": {"grade": 50.0}},
                "T08": {"status": "estimated", "reason": "prior", "value": {"probability": 0.2 + i * 0.005}},
                "P06": {"status": "estimated", "reason": "prior", "value": {"display_grade": {"grade": 40.0 + i * 0.3}, "measurements": []}},
                "P01": {"status": "measured", "reason": "measured", "value": {"display_grade": {"grade": 50.0}, "measurements": [{"inches": 80}]}},
            }}
        return {"players": players}

    def test_tendencies_keep_their_scale_and_follow_bbi_rank(self):
        section = self._section()
        before = sorted(d["inputs"]["T08"]["value"]["probability"] for d in section["players"].values())
        fake = {"p0": {"T08": {"grade": 95.0, "z": 2.5, "weight": 5.0, "seasons": {}, "metrics_used": ["m"]},
                       "P06": {"grade": 95.0, "z": 2.5, "weight": 5.0, "seasons": {}, "metrics_used": ["m"]},
                       "P01": {"grade": 95.0, "z": 2.5, "weight": 5.0, "seasons": {}, "metrics_used": ["m"]},
                       "S01": {"grade": 80.0, "z": 1.0, "weight": 0.35, "seasons": {}, "metrics_used": ["m"]}}}
        original = be.player_input_scores
        be.player_input_scores = lambda root, mapping=None: fake
        try:
            summary = be.apply_overlay(section, ROOT)
        finally:
            be.player_input_scores = original
        p0 = section["players"]["p0"]["inputs"]
        # Lowest-ranked usage becomes near the top, but stays inside the existing range (no new scale).
        self.assertGreater(p0["T08"]["value"]["probability"], before[50])
        self.assertLessEqual(p0["T08"]["value"]["probability"], before[-1])
        self.assertEqual(p0["T08"]["reason"], "estimated")
        self.assertGreater(p0["P06"]["value"]["display_grade"]["grade"], 50.0)
        self.assertEqual(p0["P01"]["value"]["display_grade"]["grade"], 50.0)  # measured physicals untouched
        self.assertAlmostEqual(p0["S01"]["value"]["grade"], 65.0)            # equal weights -> halfway
        self.assertEqual(p0["S01"]["reason"], "estimated")
        self.assertEqual(summary["cells_changed"], 3)
        self.assertAlmostEqual(section["players"]["p1"]["inputs"]["T08"]["value"]["probability"], 0.205)  # others untouched

    def test_mix_choice_is_reranked_and_mix_still_sums_to_one(self):
        section = {"players": {}}
        for i in range(60):
            drive = 0.05 + i * 0.002
            section["players"][f"p{i}"] = {"inputs": {"T01": {"status": "estimated", "reason": "prior", "value": {
                "rows": [{"condition": "reference_opportunity",
                          "probabilities": {"drive": drive, "shoot": 0.5 - drive, "pass": 0.5}}]}}}}
        fake = {"p59": {"T01:drive": {"grade": 5.0, "z": -2.5, "weight": 5.0, "seasons": {}, "metrics_used": ["Drives"]}}}
        original = be.player_input_scores
        be.player_input_scores = lambda root, mapping=None: fake
        try:
            be.apply_overlay(section, ROOT)
        finally:
            be.player_input_scores = original
        mix = section["players"]["p59"]["inputs"]["T01"]["value"]["rows"][0]["probabilities"]
        self.assertLess(mix["drive"], 0.08)                       # top driver by estimate, bottom by BBI
        self.assertAlmostEqual(sum(mix.values()), 1.0, places=5)
        self.assertGreater(mix["pass"], 0.5)                      # untouched choices keep relative size
        self.assertEqual(section["players"]["p59"]["inputs"]["T01"]["reason"], "estimated")

    def test_rank_and_quantile_round_trip(self):
        pool = [float(x) for x in range(100)]
        for x in (0.0, 13.0, 50.0, 99.0):
            self.assertAlmostEqual(be._quantile(pool, be._ND.cdf(be._rank_z(pool, x))), x)


class MeasuredActionMixTests(unittest.TestCase):
    def test_measured_rates_blend_in_and_post_share_is_kept(self):
        section = {"players": {"hub": {"inputs": {"T01": {"status": "estimated", "reason": "prior", "value": {"rows": [
            {"condition": "reference_opportunity",
             "probabilities": {"drive": 0.2, "pass": 0.3, "post": 0.18, "reset": 0.12, "shoot": 0.2}}]}}}}}}
        fake = {"hub": {"mix": {"shoot": 0.17, "drive": 0.04, "pass": 0.18, "reset": 0.55}, "weight": 5.0}}
        original = be.measured_action_mix
        be.measured_action_mix = lambda root: fake
        try:
            summary = be.apply_measured_action_mix(section, ROOT)
        finally:
            be.measured_action_mix = original
        mix = section["players"]["hub"]["inputs"]["T01"]["value"]["rows"][0]["probabilities"]
        self.assertEqual(summary["t01_measured"], 1)
        self.assertAlmostEqual(sum(mix.values()), 1.0, places=5)
        self.assertAlmostEqual(mix["post"], 0.18, places=2)          # no per-touch measure: estimate kept
        self.assertLess(mix["drive"], 0.1)                            # measured: a hub who rarely drives
        self.assertGreater(mix["reset"], 0.35)
        self.assertEqual(section["players"]["hub"]["inputs"]["T01"]["reason"], "estimated")


@unittest.skipUnless(MAPPING.exists(), "BBI mapping not present")
class MappingFileTests(unittest.TestCase):
    def test_mapping_covers_all_inputs_with_valid_entries(self):
        mapping = json.loads(MAPPING.read_text())
        ids = {row["id"] for row in definition_registry()["inputs"]}
        self.assertEqual(set(mapping["inputs"]), ids)
        for iid, spec in mapping["inputs"].items():
            for m in spec.get("metrics", []):
                self.assertIn(int(m["direction"]), (1, -1), (iid, m))
                self.assertIn(m["strength"], be.STRENGTH, (iid, m))

    def test_no_metric_feeds_both_a_skill_and_a_tendency_or_physical_input(self):
        mapping = json.loads(MAPPING.read_text())
        layer = lambda iid: "skill" if iid[0] in "SF" else ("physical" if iid[0] == "P" else "tendency")
        seen = {}
        for iid, spec in mapping["inputs"].items():
            for m in spec.get("metrics", []):
                seen.setdefault(m["metric"], set()).add(layer(iid))
        mixed = {k: v for k, v in seen.items() if "skill" in v and len(v) > 1}
        self.assertEqual(mixed, {})


if __name__ == "__main__":
    unittest.main()
