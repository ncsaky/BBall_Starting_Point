"""Measured dunk evidence (S12), volume-weighted shot-type evidence and the free-throw unit guard (ratings-consensus)."""
import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from nba_gm_data import bbi_evidence as be
from nba_gm_data import public_shot_evidence as pse

ROOT = Path(__file__).resolve().parents[1]


def _measure(value):
    return {"value": {"measurements": [{"value": value}]}}


def _league(n=120):
    """Players of three sizes; within each size, dunk rate rises with index, and the S12 estimate starts at 50."""
    universe, section, shooting = {"players": []}, {"players": {}}, {"players": {}}
    for i in range(n):
        size = i % 3                                   # 0 guard, 1 wing, 2 big
        height, wing, mass = 190 + 12 * size, 198 + 14 * size, 88 + 15 * size
        base = (0.03, 0.15, 0.45)[size]
        rate = min(0.9, base * (0.5 + (i // 3) / (n // 3)))
        pid = f"p{i}"
        universe["players"].append({"id": pid, "name": f"Player {i}"})
        section["players"][pid] = {"inputs": {"P01": _measure(height), "P02": _measure(wing), "P04": _measure(mass),
                                              "S12": {"status": "estimated", "reason": "prior", "value": {"grade": 50.0},
                                                      "evidence": [], "uncertainty": {"notes": "{}"}}}}
        shooting["players"][pid] = {"name": f"Player {i}", "seasons": {"2025-26": {
            "fga": 600.0, "pct_fga_00_03": 0.3 + 0.15 * size, "pct_fga_dunk": rate * (0.3 + 0.15 * size), "dunks": 10}}}
    return universe, section, shooting


class DunkEvidenceTests(unittest.TestCase):
    def _apply(self):
        universe, section, shooting = _league()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / pse.DATA_FILE
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(shooting))
            summary = pse.apply_dunk_evidence(section, Path(tmp), universe)
        return section, summary

    def test_dunk_grade_compares_players_with_others_their_size(self):
        section, summary = self._apply()
        self.assertGreater(summary["dunk_evidence"]["players_measured"], 100)
        grade = lambda i: section["players"][f"p{i}"]["inputs"]["S12"]["value"]["grade"]
        # Same size, more dunks -> higher; the biggest dunker among guards beats an average big.
        self.assertGreater(grade(117), grade(0))      # guard: most vs fewest dunks
        self.assertGreater(grade(119), grade(2))      # big: most vs fewest dunks
        self.assertGreater(grade(117), grade(59))     # top guard vs a middling big
        record = section["players"]["p117"]["inputs"]["S12"]
        self.assertEqual(record["reason"], "estimated")
        self.assertIn("bref_dunk_evidence", record["evidence"][-1]["method"])

    def test_grades_stay_inside_the_open_scale(self):
        section, _ = self._apply()
        grades = [d["inputs"]["S12"]["value"]["grade"] for d in section["players"].values()]
        self.assertTrue(all(0 < g < 100 for g in grades))

    def test_missing_data_file_leaves_inputs_alone(self):
        universe, section, _ = _league(60)
        with TemporaryDirectory() as tmp:
            summary = pse.apply_dunk_evidence(section, Path(tmp), universe)
        self.assertIn("skipped", summary["dunk_evidence"])
        self.assertEqual({d["inputs"]["S12"]["value"]["grade"] for d in section["players"].values()}, {50.0})


class VolumeWeightTests(unittest.TestCase):
    """A shot-type percentage on a handful of attempts must not outweigh the player's shooting as a whole."""

    def test_low_volume_pull_up_shooter_follows_his_overall_shooting(self):
        mapping = {"inputs": {"S02": {"kind": "grade", "metrics": [
            {"metric": "PU%", "direction": 1, "strength": "primary", "volume": {"per75": "PU att", "half": 40}},
            {"metric": "All3", "direction": 1, "strength": "weak"}]}}}
        table = {}
        for season in be.SEASON_WEIGHTS:
            table[(season, "PU%")] = {f"p{i}": (float(i), 2000.0, f"p{i}") for i in range(40)}
            table[(season, "All3")] = {f"p{i}": (float(i), 2000.0, f"p{i}") for i in range(40)}
            table[(season, "PU att")] = {f"p{i}": (5.0, 2000.0, f"p{i}") for i in range(40)}
            # p0: worst shooter overall, best pull-up % but on ~1 pull-up per season
            table[(season, "PU%")]["p0"] = (99.0, 2000.0, "p0")
            table[(season, "PU att")]["p0"] = (0.01, 2000.0, "p0")
        with mock.patch.object(be, "collect_values", lambda root, metrics: table):
            scores = be.player_input_scores(Path("."), mapping)
        self.assertLess(scores["p0"]["S02"]["z"], 0)                      # judged by his overall shooting
        self.assertLess(scores["p0"]["S02"]["weight"], scores["p39"]["S02"]["weight"])
        self.assertGreater(scores["p39"]["S02"]["z"], 1.0)


class FreeThrowUnitTests(unittest.TestCase):
    def test_free_throw_percentage_is_not_blended_with_percentile_grades(self):
        section = {"players": {f"p{i}": {"inputs": {"S07": {"status": "estimated", "reason": "estimated", "evidence": [],
                    "value": {"grade": 78.0, "scale": "research_FT_conversion_percent_proxy_v1"}}}} for i in range(40)}}
        fake = {"p0": {"S07": {"grade": 10.0, "z": -1.5, "weight": 3.0, "seasons": {}, "metrics_used": ["Stable FT%"]}}}
        with mock.patch.object(be, "player_input_scores", lambda root, mapping=None: fake):
            be.apply_overlay(section, Path("."))
        self.assertEqual(section["players"]["p0"]["inputs"]["S07"]["value"]["grade"], 78.0)


@unittest.skipUnless((ROOT / pse.DATA_FILE).exists(), "Basketball-Reference shooting file not built")
class ShootingFileTests(unittest.TestCase):
    def test_file_has_three_seasons_and_dunk_fields(self):
        data = json.loads((ROOT / pse.DATA_FILE).read_text())
        seasons = {s for p in data["players"].values() for s in p["seasons"]}
        self.assertEqual(seasons, set(pse.SEASON_WEIGHTS))
        rates = pse.dunk_rates(data)
        self.assertGreater(len(rates), 500)
        self.assertTrue(all(0 < r["rate"] < 1 and math.isfinite(r["close"]) for r in rates.values()))


if __name__ == "__main__":
    unittest.main()
