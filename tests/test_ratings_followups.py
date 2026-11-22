"""RATINGS-FOLLOWUPS: thin-sample players, return from a major injury, and replays of last season undoing the
opening-day projection."""
from __future__ import annotations

import gzip
import json
import math
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import build_player_inputs as bpi  # noqa: E402
from nba_gm_data import ratings_model  # noqa: E402

UNIVERSE = json.loads((ROOT / bpi.UNIVERSE_PATH).read_text())
PLAYERS = {p["id"]: p for p in UNIVERSE["players"]}


def _record(grade=60.0):
    return {"value": {"grade": grade}, "status": "estimated",
            "uncertainty": {"notes": json.dumps({"interval": [grade - 10, grade + 10]})},
            "evidence": [{"source": "measured", "notes": "{}"}]}


class ReplayUndoTest(unittest.TestCase):
    def test_projection_is_undone_exactly_and_level_steps_are_kept(self):
        aged = bpi._shifted(_record(60.0), -0.3, {"player_id": "p"}, {"source": "age"}, undo_step="age_projection")
        thin = bpi._shifted(_record(55.0), 0.4, {"player_id": "q"}, {"source": "thin"}, undo_step="thin_sample")
        self.assertLess(aged["value"]["grade"], 60.0)
        league = {"p": {"S01": aged}, "q": {"S01": thin}}
        replay = ratings_model.replay_last_season_inputs(league)
        self.assertEqual(replay["p"]["S01"]["value"]["grade"], 60.0)
        self.assertEqual(replay["q"]["S01"]["value"]["grade"], thin["value"]["grade"])
        everything = ratings_model.replay_last_season_inputs(league, None)
        self.assertEqual(everything["q"]["S01"]["value"]["grade"], 55.0)

    def test_undo_uses_the_earliest_recorded_value(self):
        first = bpi._shifted(_record(60.0), -0.3, {"player_id": "p"}, {"source": "age"}, undo_step="age_projection")
        second = bpi._shifted(first, -0.2, {"player_id": "p"}, {"source": "age"}, undo_step="age_projection")
        self.assertEqual(ratings_model._replay_record(second)["value"]["grade"], 60.0)

    def test_records_without_a_projection_are_untouched(self):
        rec = _record(42.0)
        self.assertIs(ratings_model._replay_record(rec), rec)

    def test_opening_day_switch_keeps_the_projection(self):
        with mock.patch.dict(os.environ, {"NBA_GM_REPLAY_OPENING_DAY": "1"}):
            key, league = ratings_model._replay_keyed(ROOT)
        self.assertNotIn(ratings_model.REPLAY_SUFFIX, key)


class ThinSampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads((ROOT / bpi.THIN_SAMPLE_PATH).read_text())
        cls.targets = bpi.thin_sample_targets(UNIVERSE, ROOT)

    def test_evidence_is_measured_and_cross_validated(self):
        cv = self.evidence["cv_mean_squared_error"]
        best = min(v for k, v in cv.items() if "weighted" in k)
        self.assertLess(best, cv["own number only (no pull)"])
        self.assertTrue(all(g["n"] >= 30 for g in self.evidence["groups"].values()))
        self.assertGreater(self.evidence["minutes_k"], 0)

    def test_only_veterans_with_some_but_little_nba_evidence(self):
        self.assertGreater(len(self.targets), 80)
        for pid, t in self.targets.items():
            self.assertNotEqual(PLAYERS[pid].get("draft_year"), 2026)
            self.assertTrue(0 < t["minutes"] < 1000)

    def test_own_number_counts_by_minutes(self):
        k = self.evidence["minutes_k"]
        for t in self.targets.values():
            self.assertAlmostEqual(t["own_weight"], t["minutes"] / (t["minutes"] + k), places=3)

    def test_pull_moves_toward_the_group_in_both_directions(self):
        above = below = 0
        for t in self.targets.values():
            own_total = t["own_offense"] + t["own_defense"]
            group_total = t["group_offense"] + t["group_defense"]
            above += own_total > group_total + 0.5
            below += own_total < group_total - 0.5
        self.assertGreater(above, 5)
        self.assertGreater(below, 5)

    def test_cryer_is_a_thin_sample(self):
        cryer = self.targets["player_gsw-lj-cryer"]
        self.assertLess(cryer["own_weight"], 0.5)
        self.assertLess(cryer["offense"] + cryer["defense"], -0.5)

    def test_years_in_league_ignore_a_father_with_the_same_name(self):
        harper = self.targets.get("player_bos-ron-harper-jr")
        if harper:
            self.assertLess(harper["years_in_league"], 8)

    def test_older_players_carry_their_own_age(self):
        ages = sorted(self.targets.values(), key=lambda t: t["age"])
        self.assertLess(ages[-1]["age_change_offense"], ages[0]["age_change_offense"])


class InjuryReturnTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads((ROOT / bpi.INJURY_RETURN_PATH).read_text())
        cls.targets = bpi.injury_return_targets(UNIVERSE, ROOT)

    def test_cost_is_measured_from_real_returns(self):
        self.assertGreaterEqual(self.evidence["applied_cost"]["cases_back"], 30)
        pooled = self.evidence["applied_cost"]["pooled"]
        self.assertLess(pooled["offense"] + pooled["defense"], -0.3)
        for case in self.evidence["cases"]:
            self.assertIn(case["injury"], ("achilles", "acl"))

    def test_named_players_carry_the_cost(self):
        for pid in ("player_gsw-jimmy-butler-iii", "player_por-damian-lillard", "player_hou-fred-vanvleet",
                    "player_dal-kyrie-irving"):
            self.assertIn(pid, self.targets)
            self.assertEqual(self.targets[pid]["before_share"], 1.0)
            self.assertLess(self.targets[pid]["offense"], 0.0)

    def test_seasons_played_after_the_injury_reduce_the_cost(self):
        tatum = self.targets["player_bos-jayson-tatum"]
        self.assertTrue(0.5 < tatum["before_share"] < 1.0)
        full = self.evidence["applied_cost"]["achilles under 30"]["offense"]
        self.assertAlmostEqual(tatum["offense"], full * tatum["before_share"], places=3)


class CanonicalInputsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads(gzip.open(ROOT / "data/canonical/player_inputs_2026_27.json.gz").read())["players"]

    def notes(self, pid, iid):
        return [json.loads(e["notes"]) for e in self.inputs[pid]["inputs"][iid]["evidence"]
                if isinstance(e.get("notes"), str) and e["notes"].startswith("{")]

    def test_steps_are_attributed(self):
        sources = {e.get("source") for e in self.inputs["player_gsw-lj-cryer"]["inputs"]["S01"]["evidence"]}
        self.assertIn(bpi.THIN_SAMPLE_PATH, sources)
        sources = {e.get("source") for e in self.inputs["player_gsw-jimmy-butler-iii"]["inputs"]["S01"]["evidence"]}
        self.assertIn(bpi.INJURY_RETURN_PATH, sources)
        self.assertIn(bpi.AGE_PROJECTION_PATH, sources)

    def test_every_projection_records_its_undo(self):
        undo = [n["replay_undo"] for n in self.notes("player_gsw-al-horford", "S10") if "replay_undo" in n]
        self.assertEqual(len(undo), 1)
        self.assertEqual(undo[0]["step"], "age_projection")
        before = undo[0]["before"]
        now = self.inputs["player_gsw-al-horford"]["inputs"]["S10"]["value"]["grade"]
        shifted = 100 / (1 + math.exp(-(math.log(before / (100 - before)) + undo[0]["log_odds_shift"])))
        self.assertAlmostEqual(shifted, now, places=4)

    def test_grades_are_not_clipped(self):
        for doc in self.inputs.values():
            for rec in doc["inputs"].values():
                grade = (rec.get("value") or {}).get("grade")
                if isinstance(grade, (int, float)):
                    self.assertGreater(grade, 0.0)
                    self.assertLess(grade, 100.0)


if __name__ == "__main__":
    unittest.main()
