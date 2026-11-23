"""INPUT-DATA-FIXES (2026-11-23): the evidence bugs found by the input data audit stay fixed."""
from __future__ import annotations

import json
import random
import unittest
from pathlib import Path

from nba_gm_data import bbi_evidence as be
from nba_gm_data import input_estimator as ie

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / be.MAPPING_FILE
SEASONS = sorted(be.SEASON_WEIGHTS)


class RepeatabilityTieTests(unittest.TestCase):
    def test_tied_values_share_their_rank(self):
        self.assertEqual(be._average_ranks([3.0, 1.0, 1.0, 2.0]), [3.0, 0.5, 0.5, 2.0])

    def test_mostly_zero_column_is_not_read_as_repeatable(self):
        # 57 of 60 players at zero every season, three random non-zero values: the old screen ranked the tied zeros in
        # the same sort order each season and read near-perfect repeatability.
        table = {}
        for s, season in enumerate(SEASONS):
            rng = random.Random(s)
            values = {f"p{i}": 0.0 for i in range(60)}
            for i in rng.sample(range(60), 3):
                values[f"p{i}"] = rng.random()
            table[(season, "m")] = {k: (v, 2000.0, k) for k, v in values.items()}
        self.assertLess(be.metric_reliability(table, {"metric": "m"}), 0.5)

    def test_constant_column_has_no_repeatability(self):
        table = {(season, "m"): {f"p{i}": (0.0, 2000.0, f"p{i}") for i in range(60)} for season in SEASONS}
        self.assertIsNone(be.metric_reliability(table, {"metric": "m"}))


class EvidenceReadTests(unittest.TestCase):
    def _scores(self, table, metrics):
        mapping = {"inputs": {"S32": {"kind": "grade", "metrics": metrics}}}
        original = be.collect_values
        be.collect_values = lambda root, names: table
        try:
            return be.player_input_scores(ROOT, mapping)
        finally:
            be.collect_values = original

    def test_near_copies_in_a_vote_group_count_once(self):
        # a and b rank players the same way (copies); c ranks them the opposite way. As two votes, a/b outweigh c two
        # to one; as one group the two directions balance.
        table = {}
        for season in SEASONS:
            table[(season, "a")] = {f"p{i}": (float(i), 2000.0, f"p{i}") for i in range(60)}
            table[(season, "b")] = {f"p{i}": (float(i) + 0.01, 2000.0, f"p{i}") for i in range(60)}
            table[(season, "c")] = {f"p{i}": (float(-i), 2000.0, f"p{i}") for i in range(60)}
        plain = [{"metric": m, "direction": 1, "strength": "primary"} for m in "abc"]
        grouped = [dict(m, vote_group="ab") if m["metric"] in "ab" else m for m in plain]
        self.assertGreater(self._scores(table, plain)["p59"]["S32"]["z"], 0.3)
        self.assertAlmostEqual(self._scores(table, grouped)["p59"]["S32"]["z"], 0.0, places=6)

    def test_impossible_rates_are_not_read(self):
        table = {(season, "rate"): {**{f"p{i}": (float(i), 2000.0, f"p{i}") for i in range(60)},
                                    "odd": (125.0, 2000.0, "odd")} for season in SEASONS}
        metric = {"metric": "rate", "direction": 1, "strength": "primary", "valid_range": [0, 100]}
        self.assertNotIn("odd", be._metric_values(table, SEASONS[-1], metric))
        scores = self._scores(table, [metric])
        self.assertNotIn("odd", scores)
        self.assertIn("p59", scores)


@unittest.skipUnless(MAPPING.exists(), "BBI mapping not present")
class MappingFixTests(unittest.TestCase):
    def setUp(self):
        self.mapping = json.loads(MAPPING.read_text())

    def metrics(self, iid):
        return {m["metric"]: m for m in self.mapping["inputs"][iid]["metrics"]}

    def test_copied_paint_columns_do_not_vote_for_short_paint_touch(self):
        s11 = self.metrics("S11")
        self.assertNotIn("Paint Shot Making Efficiency", s11)
        self.assertNotIn("Paint Shooting Talent", s11)
        self.assertEqual(s11["Floater Shot Making Efficiency"]["strength"], "primary")
        used = {m["metric"] for spec in self.mapping["inputs"].values() for m in spec.get("metrics", [])}
        self.assertFalse(used & {"Paint Shot Making Efficiency", "Paint Shooting Talent", "Movement Distance Rating"})

    def test_movement_distance_rating_does_not_vote(self):
        self.assertNotIn("Movement Distance Rating", self.metrics("T17"))
        excluded = {e["metric"] for e in self.mapping["excluded"]}
        self.assertTrue({"Movement Distance Rating", "Paint Shooting Talent", "Paint Shot Making Efficiency"} <= excluded)

    def test_near_duplicate_pairs_share_one_vote(self):
        s37, t06 = self.metrics("S37"), self.metrics("T06")
        self.assertEqual(s37["Stable Rim dFG% vs. Expected"].get("vote_group"),
                         s37["Stable Defensive FG% at Rim"].get("vote_group"))
        self.assertIsNotNone(s37["Stable Defensive FG% at Rim"].get("vote_group"))
        self.assertIsNone(s37["Rim dFG% vs Expected"].get("vote_group"))   # the raw rate is a different signal (r 0.43)
        self.assertEqual(t06["Average Dribbles Per Touch"].get("vote_group"),
                         t06["Average Seconds Per Touch"].get("vote_group"))
        self.assertIsNotNone(t06["Average Seconds Per Touch"].get("vote_group"))

    def test_rebound_rates_have_a_possible_range(self):
        s32 = self.metrics("S32")
        for name in ("Adjusted Offensive Rebounding Success Rate", "Adjusted Defensive Rebounding Success Rate",
                     "Percentage of Offensive Rebounds Contested", "Percentage of Defensive Rebounds Contested"):
            self.assertEqual(s32[name]["valid_range"], [0, 100])


class CraftedReaderTests(unittest.TestCase):
    def test_percent_unit_play_type_rows_become_fractions(self):
        row = ie._share_units({"prbh_pct": 22.0, "pnrr_pct": 1.0, "post_pct": 0.2, "PTS": 9.0})
        self.assertAlmostEqual(row["prbh_pct"], 0.22)
        self.assertAlmostEqual(row["pnrr_pct"], 0.01)     # 1% roll man, not 100%
        self.assertAlmostEqual(row["post_pct"], 0.002)
        self.assertEqual(row["PTS"], 9.0)
        fractions = {"prbh_pct": 0.22, "pnrr_pct": 1.0}    # a fraction row (even a pure roll man) is unchanged
        self.assertEqual(ie._share_units(fractions), fractions)

    def test_march_impact_text_is_not_parsed_and_numeric_alias_leads(self):
        # March snapshot cell: impact with an appended percentile; CDPM is the verified numeric value.
        row = {"name": "Test Player", "MP": "1500.0", "CraftedDPM": "0.5 68%", "CDPM": "-0.9", "DLEBRON": "-0.5"}
        self.assertIsNone(ie._number(row["CraftedDPM"]))
        estimator = ie.InputEstimator(skill_rows=[row])
        context = estimator._family_context({"name": "Test Player"}, "rebounding")
        self.assertEqual(context[0]["fields"]["CDPM"], -0.9)
        self.assertNotIn("CraftedDPM", context[0]["fields"])


if __name__ == "__main__":
    unittest.main()
