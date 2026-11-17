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

    def test_small_pools_are_ignored(self):
        self.assertEqual(be._percentiles({"a": (1.0, 900.0, "a")}, 1), {})


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
