"""ROOKIE-FIT and ROOKIE-FIT-2: the 2026 rookies' technique from their final college season; level = day-one ability."""
import copy
import json
import unittest
from pathlib import Path

from nba_gm_data.input_estimator import (
    DEFINITIONS, FT_SCALE, InputEstimator, InputEvidence, ROOKIE_TRANSLATION_PATH, TECHNIQUE_SCALE,
    apply_rookie_involvement, estimation_status, load_rookie_college, scalar_value, uncertainty_details,
)
from scripts.build_player_inputs import estimate_startup_inputs

ROOT = Path(__file__).resolve().parents[1]
ROOKIE = {"id": "rookie", "name": "Rookie", "espn_player_id": "rookie", "position": "PF", "height_inches": 81,
          "weight_lbs": 235, "age": 22, "draft_year": 2026, "draft_status": "drafted"}
OFFENSE_PRIOR_INPUTS = ("S21", "S22", "S25", "S26")      # post and routes: no college evidence, offense family
DEFENSE_PRIOR_INPUTS = ("S33", "S34", "S35", "S40")      # perimeter defense: no college evidence


def college_entry(o=-1.0, d=-0.3, shooting=70.0):
    evidence = [InputEvidence("S01", dict(grade=shooting, scale=TECHNIQUE_SCALE), (shooting - 20, shooting + 20),
                              "barttorvik:final_college_season", "test", "college:rookie", n=1000,
                              prior_exposure=300, reliability=.45, exposure_unit="college_minutes"),
                InputEvidence("S07", dict(grade=82.0, scale=FT_SCALE), (60.0, 100.0),
                              "barttorvik:final_college_season", "test", "college:rookie", n=1000,
                              prior_exposure=300, reliability=.5, exposure_unit="college_minutes")]
    return dict(evidence=evidence, projection=dict(o=o, d=d, lebron=o + d, bpm=-2.0), involvement=[.30, .25],
                name="Rookie", college=dict(minutes=1000.0))


def grades(inputs, ids):
    return [inputs[i]["value"]["grade"] for i in ids]


class CollegeEvidencePathTests(unittest.TestCase):
    def setUp(self):
        self.estimator = InputEstimator()

    def test_college_evidence_becomes_estimated_and_projection_sets_the_level(self):
        low = self.estimator.estimate_player_inputs(ROOKIE, prospect=True, college=college_entry(o=-2.0, d=-1.0)).to_dict()
        high = self.estimator.estimate_player_inputs(ROOKIE, prospect=True, college=college_entry(o=0.5, d=0.5)).to_dict()
        for doc in (low, high):
            inputs = doc["inputs"]
            self.assertNotEqual(estimation_status(inputs["S01"]), "prior")
            self.assertTrue(any(e["source"] == "barttorvik:final_college_season" for e in inputs["S01"]["evidence"]))
            # The old draft-model traits never condition a rookie with college evidence.
            self.assertFalse(any(e["source"] == "legacy_trait_prior" for r in inputs.values() for e in r["evidence"]))
        for a, b in zip(grades(low["inputs"], OFFENSE_PRIOR_INPUTS), grades(high["inputs"], OFFENSE_PRIOR_INPUTS)):
            self.assertLess(a, b)
        for a, b in zip(grades(low["inputs"], DEFENSE_PRIOR_INPUTS), grades(high["inputs"], DEFENSE_PRIOR_INPUTS)):
            self.assertLess(a, b)
        notes = [e for e in high["inputs"]["S33"]["evidence"] if "family_talent" in e["source"]]
        self.assertEqual(len(notes), 1)
        self.assertIn("projected_rookie_defense", notes[0]["notes"])

    def test_offense_projection_never_moves_defense_or_tools_or_choices(self):
        a = self.estimator.estimate_player_inputs(ROOKIE, prospect=True, college=college_entry(o=-2.0)).to_dict()["inputs"]
        b = self.estimator.estimate_player_inputs(ROOKIE, prospect=True, college=college_entry(o=1.0)).to_dict()["inputs"]
        for iid, definition in DEFINITIONS.items():
            if definition["kind"] != "grade" or iid in DEFENSE_PRIOR_INPUTS:
                with self.subTest(input_id=iid):
                    self.assertEqual(a[iid]["value"], b[iid]["value"])

    def test_better_college_shooting_raises_the_shooting_input(self):
        a = self.estimator.estimate_player_inputs(ROOKIE, prospect=True, college=college_entry(shooting=40)).to_dict()["inputs"]
        b = self.estimator.estimate_player_inputs(ROOKIE, prospect=True, college=college_entry(shooting=75)).to_dict()["inputs"]
        self.assertLess(a["S01"]["value"]["grade"], b["S01"]["value"]["grade"])

    def test_startup_builder_uses_college_path_only_for_rookies_with_a_season(self):
        other = dict(ROOKIE, id="other", name="Other", espn_player_id="other")
        veteran = dict(ROOKIE, id="vet", name="Vet", espn_player_id="vet", draft_year=2019)
        universe = {"players": [ROOKIE, other, veteran]}
        entry = college_entry()
        regular = self.estimator.estimate_universe(copy.deepcopy(universe))["players"]
        actual = estimate_startup_inputs(self.estimator, copy.deepcopy(universe), {"rookie": entry})["players"]
        with_college = self.estimator.estimate_player_inputs(ROOKIE, prospect=True, college=entry).to_dict()["inputs"]
        without = self.estimator.estimate_player_inputs(other, prospect=True).to_dict()["inputs"]
        self.assertEqual(actual["vet"], regular["vet"])
        for iid, definition in DEFINITIONS.items():
            with self.subTest(input_id=iid):
                if definition["kind"] == "grade":
                    self.assertEqual(actual["rookie"]["inputs"][iid], with_college[iid])
                    self.assertEqual(actual["other"]["inputs"][iid], without[iid])
                else:
                    self.assertEqual(actual["rookie"]["inputs"][iid], regular["rookie"]["inputs"][iid])

    def test_involvement_blends_college_usage_on_the_measured_scale(self):
        doc = self.estimator.estimate_player_inputs(ROOKIE).to_dict()
        before = doc["inputs"]["T08"]["value"]["probability"]
        section = {"players": {"rookie": doc, "vet": copy.deepcopy(doc)}}
        vet = copy.deepcopy(section["players"]["vet"])
        self.assertEqual(apply_rookie_involvement(section, {"rookie": college_entry()}), 1)
        after = section["players"]["rookie"]["inputs"]["T08"]["value"]["probability"]
        self.assertAlmostEqual(after, .75 * before + .25 * .30, places=7)
        self.assertEqual(section["players"]["vet"], vet)

    def test_involvement_then_this_seasons_usage(self):
        doc = self.estimator.estimate_player_inputs(ROOKIE).to_dict()
        before = doc["inputs"]["T08"]["value"]["probability"]
        section = {"players": {"rookie": doc}}
        entry = dict(college_entry(), involvement_games=[.40, .2])
        apply_rookie_involvement(section, {"rookie": entry})
        college = .75 * before + .25 * .30
        record = section["players"]["rookie"]["inputs"]["T08"]
        self.assertAlmostEqual(record["value"]["probability"], .8 * college + .2 * .40, places=7)
        self.assertEqual(record["evidence"][-1]["source"], "basketball_reference:2026_27_games_so_far")


@unittest.skipUnless((ROOT / ROOKIE_TRANSLATION_PATH).exists(), "rookie translation bundle missing")
class RookieBundleTests(unittest.TestCase):
    def test_bundle_feeds_evidence_for_the_real_class(self):
        college = load_rookie_college(ROOT)
        self.assertGreaterEqual(len(college), 45)
        entry = college["player_gsw-yaxel-lendeborg"]
        self.assertEqual(entry["college"]["team"], "Michigan")
        self.assertAlmostEqual(entry["college"]["bpm"], 15.5, places=1)
        ids = {e.input_id for e in entry["evidence"]}
        for iid in ("S01", "S07", "S29", "S30", "S36", "S41", "F01.recognition"):
            self.assertIn(iid, ids)
        for e in entry["evidence"]:
            low, high = e.interval
            self.assertLessEqual(low, e.value["grade"])
            self.assertLessEqual(e.value["grade"], high)
            self.assertLessEqual(e.reliability, .6)
        self.assertEqual(set(entry["projection"]), {"lebron", "o", "d", "bpm"})
        target, weight = entry["involvement"]
        self.assertTrue(0 < target < 1 and 0 < weight < .6)

    def test_report_answers_slot_and_selection_questions(self):
        bundle = json.loads((ROOT / ROOKIE_TRANSLATION_PATH).read_text())
        self.assertEqual(bundle["method"], "rookie_translation_v2")
        models = bundle["report"]["outcomes"]["lebron"]["models"]
        # College production predicts first-season impact better than draft slot on held-out drafts.
        self.assertGreater(models["college_slot"]["held_out"]["r"], models["slot"]["held_out"]["r"])
        # Who gets minutes: a late second-rounder's ability sits below what the few who play show.
        late = next(b for b in bundle["report"]["pick_bands"] if b["picks"] == "46-60")
        self.assertLess(late["ability_mean"], late["if_played_mean"])

    def test_day_one_ability_is_the_sum_of_labelled_parts(self):
        bundle = json.loads((ROOT / ROOKIE_TRANSLATION_PATH).read_text())
        for pid, entry in bundle["class_2026"].items():
            parts = entry["projection_parts"]
            for side in ("o", "d"):
                with self.subTest(player=entry["name"], side=side):
                    total = parts["college_fit"][side] + parts["readiness"][side] + parts["early_games"][side]
                    self.assertAlmostEqual(entry["projection"][side], total, delta=0.002)
            # This season's games are light evidence: weight minutes / (minutes + 1500), never most of the answer.
            self.assertLess(parts["early_games"]["weight"], 0.4)
            if entry["involvement_games"]:
                self.assertLess(entry["involvement_games"][1], 0.5)


class EarlyGamesTests(unittest.TestCase):
    """ROOKIE-FIT-2: this season's games move a rookie a little, by minutes, and tiny samples not at all."""

    def setUp(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts" / "research"))
        import rookie_fit2
        self.r2 = rookie_fit2
        self.early = {"conversion": {"o": (0.0, 0.5, 0.8), "d": (0.0, 1.0, 0.8)},
                      "usage_line": {"intercept": 0.0, "slope": 0.015}}

    def row(self, minutes, obpm=2.0, dbpm=1.0, usg=25.0):
        return {"mp": minutes, "g": 10, "obpm": obpm, "dbpm": dbpm, "bpm": obpm + dbpm, "pts": 100, "usg_pct": usg}

    def test_weight_grows_with_minutes_and_tiny_samples_are_ignored(self):
        proj = {"o": -1.0, "d": -0.5}
        none, inv = self.r2.games_evidence(proj, self.row(40, obpm=30), self.early)
        self.assertEqual((none["o"], none["d"], inv), (0.0, 0.0, None))
        small, _ = self.r2.games_evidence(proj, self.row(150), self.early)
        big, inv = self.r2.games_evidence(proj, self.row(600), self.early)
        self.assertAlmostEqual(small["o"], 150 / 1650 * (1.0 - -1.0), places=3)
        self.assertGreater(big["o"], small["o"])
        self.assertLess(big["weight"], 0.3)
        self.assertAlmostEqual(inv[0], 0.375, places=6)
        self.assertAlmostEqual(inv[1], 600 / 1600, places=6)

    def test_extreme_box_numbers_are_held_in(self):
        proj = {"o": -1.0, "d": -0.5}
        wild, _ = self.r2.games_evidence(proj, self.row(120, obpm=-40.0), self.early)
        self.assertAlmostEqual(wild["o"], 120 / 1620 * (-5.0 - -1.0), places=3)


if __name__ == "__main__":
    unittest.main()
