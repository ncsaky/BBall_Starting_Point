"""RATINGS-AUDIT-GSW: veterans' opening-day level (age projection, no NBA track record) and the Lendeborg claims."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import build_player_inputs as bpi  # noqa: E402

UNIVERSE = json.loads((ROOT / bpi.UNIVERSE_PATH).read_text())
PLAYERS = {p["id"]: p for p in UNIVERSE["players"]}


class AgeCurveTest(unittest.TestCase):
    def setUp(self):
        self.curve = json.loads((ROOT / bpi.AGE_PROJECTION_PATH).read_text())

    def total(self, age):
        return self.curve["shift"]["offense"][str(age)] + self.curve["shift"]["defense"][str(age)]

    def test_young_players_gain_and_old_players_lose(self):
        self.assertGreater(self.total(20), 0.3)
        self.assertGreater(self.total(23), 0.15)
        self.assertLess(abs(self.total(27)), 0.1)
        self.assertLess(self.total(33), -0.2)
        self.assertLess(self.total(38), -0.45)

    def test_curve_falls_with_age_from_21_to_38(self):
        totals = [self.total(a) for a in range(21, 39)]
        self.assertTrue(all(b <= a + 1e-9 for a, b in zip(totals, totals[1:])), totals)

    def test_curve_records_its_evidence(self):
        self.assertIn("Basketball Index", " ".join(self.curve["sources"]))
        self.assertEqual(self.curve["season_weights"], [1.0, 0.7, 0.45])
        self.assertGreater(self.curve["raw"]["offense"]["lag"]["30"][1], 100)   # player-seasons behind one age


class AgeTargetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.targets = bpi.age_projection_targets(UNIVERSE, ROOT)

    def test_rookies_are_left_to_the_rookie_forecast(self):
        self.assertFalse([p for p in self.targets if PLAYERS[p].get("draft_year") == 2026])

    def test_league_average_player_does_not_move(self):
        for side in ("offense", "defense"):
            weights = {p: float(PLAYERS[p].get("minutes_projection") or 0) for p in self.targets}
            mean = sum(self.targets[p][side] * w for p, w in weights.items()) / sum(weights.values())
            self.assertAlmostEqual(mean, 0.0, places=3)

    def test_suffix_names_match_basketball_reference(self):
        butler = self.targets.get("player_gsw-jimmy-butler-iii")
        self.assertIsNotNone(butler)
        self.assertEqual(butler["missed"], 0)
        self.assertLess(butler["offense"] + butler["defense"], -0.4)

    def test_older_teammate_projects_below_younger_one(self):
        horford = self.targets["player_gsw-al-horford"]
        podziemski = self.targets["player_gsw-brandin-podziemski"]
        self.assertLess(horford["offense"] + horford["defense"], 0)
        self.assertGreater(podziemski["offense"] + podziemski["defense"], 0)

    def test_a_missed_season_adds_a_season_of_change(self):
        missed = [t for t in self.targets.values() if t["missed"] >= 1 and t["age"] >= 33]
        self.assertTrue(missed)
        curve = json.loads((ROOT / bpi.AGE_PROJECTION_PATH).read_text())
        t = missed[0]
        base = curve["shift"]["offense"][str(t["age"])]
        self.assertLess(t["uncentred_offense"], base)


class NoTrackRecordTest(unittest.TestCase):
    def test_only_veterans_without_recent_nba_minutes(self):
        ids = bpi.no_track_record_players(UNIVERSE, ROOT)
        self.assertGreater(len(ids), 30)
        for pid in ids:
            p = PLAYERS[pid]
            self.assertNotEqual(p.get("draft_year"), 2026)
            self.assertFalse((p.get("draft_position") or 99) <= 30)
        self.assertNotIn("player_gsw-jimmy-butler-iii", ids)
        self.assertNotIn("player_gsw-lj-cryer", ids)          # 292 measured minutes: his measurements stand
        targets = bpi.age_projection_targets(UNIVERSE, ROOT)
        self.assertFalse(set(ids) & set(targets))

    def test_level_is_below_established_players(self):
        data = json.loads((ROOT / bpi.NO_TRACK_RECORD_PATH).read_text())
        level = data["level"]["offense"] + data["level"]["defense"]
        established = data["groups"]["2000+"]
        self.assertLess(level, established["offense"] + established["defense"] - 1.0)


class LendeborgClaimsTest(unittest.TestCase):
    def test_claims_are_attributed_and_cover_strengths_and_weaknesses(self):
        claims = [c for c in json.loads((ROOT / "data/research/analyst_claims_2026.json").read_text())["claims"]
                  if c.get("player_id") == "player_gsw-yaxel-lendeborg" and c.get("url")]
        self.assertGreaterEqual(len(claims), 6)
        levels = {c["level"] for c in claims}
        self.assertTrue({"below_average", "above_average"} <= levels)
        for c in claims:
            self.assertTrue(c["url"].startswith("https://"))
            self.assertRegex(c["published"], r"^2026-\d\d-\d\d$")


class CanonicalInputsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gzip
        cls.inputs = json.loads(gzip.open(ROOT / "data/canonical/player_inputs_2026_27.json.gz").read())["players"]

    def test_steps_are_recorded_on_the_moved_inputs(self):
        horford = self.inputs["player_gsw-al-horford"]["inputs"]["S10"]
        self.assertTrue(any(e.get("source") == bpi.AGE_PROJECTION_PATH for e in horford["evidence"]))

    def test_grades_are_not_clipped(self):
        for doc in self.inputs.values():
            for rec in doc["inputs"].values():
                grade = (rec.get("value") or {}).get("grade")
                if isinstance(grade, (int, float)):
                    self.assertGreater(grade, 0.0)
                    self.assertLess(grade, 100.0)


if __name__ == "__main__":
    unittest.main()
