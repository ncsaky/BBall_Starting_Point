import json
from copy import deepcopy
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

    def test_summed_exposure_is_plays_used_or_created(self):
        table = {("2025-26", "TOV"): {"iso": (2.0, 2000.0, "iso"), "hub": (2.0, 2000.0, "hub")},
                 ("2025-26", "Touches"): {"iso": (50.0, 2000.0, "iso"), "hub": (100.0, 2000.0, "hub")},
                 ("2025-26", "TSA"): {"iso": (25.0, 2000.0, "iso"), "hub": (10.0, 2000.0, "hub")},
                 ("2025-26", "PA"): {"iso": (3.0, 2000.0, "iso"), "hub": (8.0, 2000.0, "hub")}}
        per_touch = be._metric_values(table, "2025-26", {"metric": "TOV", "per": "Touches"})
        per_play = be._metric_values(table, "2025-26", {"metric": "TOV", "per_sum": ["TSA", "TOV", "PA"]})
        self.assertAlmostEqual(per_touch["iso"][0], 0.04)            # the isolation scorer looks worse per touch
        self.assertAlmostEqual(per_touch["hub"][0], 0.02)
        self.assertAlmostEqual(per_play["iso"][0], 2.0 / 30.0)       # ...and better per play used or created
        self.assertAlmostEqual(per_play["hub"][0], 2.0 / 20.0)

    def test_reliability_scales_noisy_metrics_down_and_keeps_repeatable_ones(self):
        self.assertEqual(be.reliability_factor(None), 1.0)
        self.assertEqual(be.reliability_factor(0.9), 1.0)
        self.assertAlmostEqual(be.reliability_factor(be.RELIABILITY_REF / 2), 0.5)
        self.assertEqual(be.reliability_factor(-0.3), 0.0)
        import random
        steady, noisy = {}, {}
        for s, season in enumerate(sorted(be.SEASON_WEIGHTS)):
            order = list(range(60))
            random.Random(s).shuffle(order)
            steady[(season, "m")] = {f"p{i}": (float(i), 2000.0, f"p{i}") for i in range(60)}
            noisy[(season, "m")] = {f"p{i}": (float(order[i]), 2000.0, f"p{i}") for i in range(60)}
        self.assertAlmostEqual(be.metric_reliability(steady, {"metric": "m"}), 1.0)
        self.assertLess(abs(be.metric_reliability(noisy, {"metric": "m"})), 0.5)

    def test_small_pools_are_ignored(self):
        self.assertEqual(be._percentiles({"a": (1.0, 900.0, "a")}, 1), {})


class OverlayTests(unittest.TestCase):
    def _section(self):
        players = {}
        for i in range(60):
            players[f"p{i}"] = {"inputs": {
                "S01": {"status": "estimated", "reason": "prior", "value": {"grade": 50.0}},
                "T06": {"status": "estimated", "reason": "prior", "value": {"probability": 0.2 + i * 0.005}},
                "P06": {"status": "estimated", "reason": "prior", "value": {"display_grade": {"grade": 40.0 + i * 0.3}, "measurements": []}},
                "P01": {"status": "measured", "reason": "measured", "value": {"display_grade": {"grade": 50.0}, "measurements": [{"inches": 80}]}},
            }}
        return {"players": players}

    def test_tendencies_keep_their_scale_and_follow_bbi_rank(self):
        section = self._section()
        before = sorted(d["inputs"]["T06"]["value"]["probability"] for d in section["players"].values())
        fake = {"p0": {"T06": {"grade": 95.0, "z": 2.5, "weight": 5.0, "seasons": {}, "metrics_used": ["m"]},
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
        self.assertGreater(p0["T06"]["value"]["probability"], before[50])
        self.assertLessEqual(p0["T06"]["value"]["probability"], before[-1])
        self.assertEqual(p0["T06"]["reason"], "estimated")
        self.assertGreater(p0["P06"]["value"]["display_grade"]["grade"], 50.0)
        self.assertEqual(p0["P01"]["value"]["display_grade"]["grade"], 50.0)  # measured physicals untouched
        self.assertAlmostEqual(p0["S01"]["value"]["grade"], 65.0)            # equal weights -> halfway
        self.assertEqual(p0["S01"]["reason"], "estimated")
        self.assertEqual(summary["cells_changed"], 3)
        self.assertAlmostEqual(section["players"]["p1"]["inputs"]["T06"]["value"]["probability"], 0.205)  # others untouched

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


class MeasuredTendencyTests(unittest.TestCase):
    def test_estimates_move_onto_measured_scales_and_measurements_blend_in(self):
        import tempfile
        section = {"players": {}}
        for i in range(40):
            pass_share = 0.25 + i * 0.003            # estimator scale: narrow
            section["players"][f"p{i}"] = {"inputs": {
                "T01": {"status": "estimated", "reason": "prior", "value": {"rows": [{"condition": "reference_opportunity",
                        "probabilities": {"drive": 0.2, "pass": pass_share, "post": 0.05, "reset": 0.2, "shoot": 0.55 - pass_share}}]}},
                "T08": {"status": "estimated", "reason": "prior", "value": {"probability": 0.30 + i * 0.008}}}}
        mix = {f"p{i}": {"mix": {"shoot": 0.2, "drive": 0.1, "pass": 0.04 + i * 0.005, "reset": 0.6}, "weight": 2.0}
               for i in range(1, 40)}             # p0 has no measurement
        inv = {f"p{i}": {"value": 0.15 + i * 0.009, "weight": 2.0} for i in range(1, 40)}
        originals = be.measured_action_mix, be.measured_involvement
        be.measured_action_mix, be.measured_involvement = (lambda root: mix), (lambda root: inv)
        try:
            with tempfile.TemporaryDirectory() as root:
                (Path(root) / "data/canonical").mkdir(parents=True)
                counts = be.apply_measured_tendencies(section, Path(root))
                saved = be.load_scale_map(Path(root))
        finally:
            be.measured_action_mix, be.measured_involvement = originals
        self.assertEqual(counts["mapped_only"], 1)
        unmeasured = section["players"]["p0"]["inputs"]
        p0_mix = unmeasured["T01"]["value"]["rows"][0]["probabilities"]
        self.assertLess(p0_mix["pass"], 0.15)                  # translated off the old 0.25 scale
        self.assertAlmostEqual(sum(p0_mix.values()), 1.0, places=5)
        self.assertAlmostEqual(p0_mix["post"], 0.05, places=3)
        self.assertLess(unmeasured["T08"]["value"]["probability"], 0.25)   # lowest estimate -> low measured usage
        top = section["players"]["p39"]["inputs"]
        self.assertGreater(top["T08"]["value"]["probability"], 0.45)
        self.assertEqual(top["T08"]["reason"], "estimated")
        self.assertIn("T08", saved)
        rookie = {"T01": deepcopy(section["players"]["p0"]["inputs"]["T01"]), "T08": {"value": {"probability": 0.30}}}
        rookie["T01"]["value"]["rows"][0]["probabilities"] = {"drive": 0.2, "pass": 0.37, "post": 0.05, "reset": 0.2, "shoot": 0.18}
        be.map_tendency_inputs(rookie, saved)
        self.assertLess(rookie["T01"]["value"]["rows"][0]["probabilities"]["pass"], 0.30)  # same translation for rookies


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

    def test_handle_security_counts_turnovers_per_play_used_or_created(self):
        spec = json.loads(MAPPING.read_text())["inputs"]["S17"]["metrics"]
        counts = [m for m in spec if "Per 75" in m["metric"]]
        self.assertTrue(counts)
        for m in counts:
            self.assertNotIn("per", m)
            self.assertEqual(set(m["per_sum"]), {"True Shot Attempts Per 75 Possessions", "Stable TOV Per 75",
                                                 "Potential Assists Per 75 Possessions"})
        self.assertNotIn("Turnovers Per 100 Touches", {m["metric"] for m in spec})

    def test_defensive_rebound_positioning_leads_with_the_league_wide_grade(self):
        # BBI's defensive crashing skill is measured against a position baseline (centres -1.3, guards +0.3, no link to
        # defensive rebounds per 75), so it may only nudge the positioning grade (overnight ratings review, 2026-11-20).
        spec = {m["metric"]: m["strength"] for m in json.loads(MAPPING.read_text())["inputs"]["S30"]["metrics"]}
        self.assertEqual(spec["Defensive Rebounding Talent"], "primary")
        self.assertEqual(spec["Defensive Rebounding Crashing Skill"], "weak")

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
