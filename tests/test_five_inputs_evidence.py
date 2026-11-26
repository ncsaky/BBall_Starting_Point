"""RATINGS-FIVE-INPUTS: measured two-point split (T02), NBA.com transition share (T17), contact seeking per shot (T18)."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from nba_gm_data import bbi_evidence as be
from nba_gm_data import playtype_evidence as pe

ROOT = Path(__file__).resolve().parents[1]


def _dist(probs):
    return {"status": "estimated", "reason": "prior",
            "value": {"rows": [{"condition": "reference_opportunity", "probabilities": dict(probs)}]}}


def _probs(record):
    return record["value"]["rows"][0]["probabilities"]


class ShotMixTests(unittest.TestCase):
    def test_nonrim_distance_takes_rim_shots_out_of_the_average(self):
        self.assertAlmostEqual(be._nonrim_distance(8.0, 0.5), (8.0 - be.RIM_SHOT_DISTANCE_FT * 0.5) / 0.5)
        self.assertIsNone(be._nonrim_distance(2.0, 0.99))

    def test_two_point_split_is_measured_and_three_share_kept(self):
        section = {"players": {
            "big": {"inputs": {"T02": _dist({"rim": .38, "short_paint": .19, "midrange": .16, "three": .27})}},
            "none": {"inputs": {"T02": _dist({"rim": .27, "short_paint": .19, "midrange": .16, "three": .38})}}}}
        before_none = deepcopy(section["players"]["none"])
        measured = {"big": {"twos": {"rim": .80, "short_paint": .18, "midrange": .02}, "attempts": 900.0, "seasons": 3}}
        originals = be.fit_short_paint_share, be.measured_shot_mix
        be.fit_short_paint_share = lambda root: {"players": 32, "a": 5.5, "b": -0.42}
        be.measured_shot_mix = lambda root, fit: measured
        try:
            counts = be.apply_measured_shot_mix(section, Path("."))
        finally:
            be.fit_short_paint_share, be.measured_shot_mix = originals
        self.assertEqual(counts["t02_measured"], 1)
        p = _probs(section["players"]["big"]["inputs"]["T02"])
        self.assertAlmostEqual(p["three"], .27, places=6)                  # three share untouched
        self.assertAlmostEqual(sum(p.values()), 1.0, places=5)
        share = 900 / (900 + be.T02_PRIOR_TWOS)
        expected_rim = (1 - .27) * (share * .80 + (1 - share) * .38 / .73)
        self.assertAlmostEqual(p["rim"], expected_rim, places=5)
        self.assertGreater(p["rim"], .55)                                    # far wider than the .38 prior
        self.assertEqual(section["players"]["none"], before_none)            # no evidence: unchanged

    @unittest.skipUnless(all((ROOT / f).exists() for f in (be.SHOT_CHART_FILE, f"{be.CACHE_DIR}/{be.RECENT_CACHE}",
                                                            f"{be.CACHE_DIR}/normalized.json")),
                         "shot chart or Basketball Index data not present")
    def test_short_paint_share_falls_with_distance_on_the_charted_players(self):
        fit = be.fit_short_paint_share(ROOT)
        self.assertGreaterEqual(fit["players"], 25)
        self.assertLess(fit["b"], 0)                                         # longer twos -> less short paint


class TransitionTests(unittest.TestCase):
    def _data(self):
        players = {}
        for i in range(60):
            players[f"p{i}"] = {"name": f"P{i}", "total_poss": 400.0 + 10 * i,
                                "types": {"Transition": [(400.0 + 10 * i) * (0.05 + 0.004 * i), 0, 0, 0, 0],
                                          "Spotup": [100.0, 0, 0, 0, 0]}}
        players["gap"] = {"name": "Gap", "total_poss": 1000.0, "types": {"Spotup": [300.0, 0, 0, 0, 0]}}
        return {"players": players}

    def test_absent_from_the_transition_table_is_unmeasured_not_zero(self):
        measured = pe.measured_transition(self._data())
        self.assertNotIn("gap", measured)
        self.assertAlmostEqual(measured["p10"]["share"], 0.09, places=6)

    def test_prior_strength_reflects_true_spread_against_sampling_noise(self):
        k = pe.prior_strength(pe.measured_transition(self._data()))
        self.assertGreater(k, 0)
        self.assertLess(k, 100)          # shares spread far more than sampling noise: own numbers dominate

    def test_transition_share_measured_defense_kept_and_rookies_mapped(self):
        data = self._data()
        section = {"players": {pid: {"inputs": {"T17": _dist({"offense": .50, "defense": .30 + .001 * i,
                                                                 "transition": .20 - .001 * i})}}
                               for i, pid in enumerate([*data["players"], "rookie"])}}
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "data/research").mkdir(parents=True)
            (Path(root) / "data/canonical").mkdir(parents=True)
            (Path(root) / pe.PLAYTYPE_FILE).write_text(json.dumps(data))
            (Path(root) / be.SCALE_MAP_FILE).write_text(json.dumps({"version": "x", "T08": {"source": [0, 1], "target": [0, 1]}}))
            counts = pe.apply_transition_evidence(section, Path(root))
            saved = be.load_scale_map(Path(root))
        self.assertEqual(counts["t17_transition_measured"], 60)
        self.assertIn("T08", saved)                                          # extends, never replaces, the map
        self.assertIn("T17:transition_share", saved)
        for i, pid in enumerate(data["players"]):
            p = _probs(section["players"][pid]["inputs"]["T17"])
            self.assertAlmostEqual(sum(p.values()), 1.0, places=5)
            self.assertAlmostEqual(p["defense"], .30 + .001 * i, places=6)
        lo, hi = (_probs(section["players"][pid]["inputs"]["T17"]) for pid in ("p0", "p59"))
        self.assertGreater(hi["transition"] / (1 - hi["defense"]), 0.25)    # measured runner
        self.assertLess(lo["transition"] / (1 - lo["defense"]), 0.08)
        rookie = {"T17": _dist({"offense": .50, "defense": .35, "transition": .15})}
        be.map_tendency_inputs(rookie, saved)
        p = _probs(rookie["T17"])
        self.assertAlmostEqual(p["defense"], .35, places=6)
        self.assertAlmostEqual(sum(p.values()), 1.0, places=5)


@unittest.skipUnless((ROOT / be.MAPPING_FILE).exists(), "BBI mapping not present")
class ContactSeekingMappingTests(unittest.TestCase):
    def test_contact_seeking_counts_are_per_shot_attempt(self):
        spec = json.loads((ROOT / be.MAPPING_FILE).read_text())["inputs"]["T18"]["metrics"]
        for m in spec:
            if "Per 75" in m["metric"]:
                self.assertEqual(set(m.get("per_sum", [])), {"Stable 2PTA Per 75", "3PT FGA Per 75 Possessions"}, m)


if __name__ == "__main__":
    unittest.main()
