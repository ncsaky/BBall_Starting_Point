from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.ingest import build_universe
from nba_gm_data.save import canonical_with_save, create_league_save, load_save, player_display_attribute_summary, write_save
from nba_gm_data.schema import to_plain
from nba_gm_data.sim import player_feature_vector

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"Kyrie Irving", "Dereck Lively II", "Collin Murray-Boyles", "Keyonte George"}


class PlayerTuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This suite protects the published V3 correction independently of later models.
        with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-player-tuning-v3.json.gz", "rt") as handle:
            cls.new = json.load(handle)
        with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-roster-v2.json.gz", "rt") as handle:
            cls.old = json.load(handle)
        cls.ids = {p["name"]: p["id"] for p in cls.new["players"] if p["name"] in NAMES}
        cls.overrides = [row for row in json.loads((ROOT / "data/overrides/trait_overrides.json").read_text())["post_alignment_players"]
                         if row["player_name"] in NAMES]

    def values(self, universe, name):
        return {t["trait_key"]: t["value"] for t in universe["traits"] if t["player_id"] == self.ids[name]}

    def grade(self, universe, name):
        context = {"players": [{**p, "minutes_projection": 24} for p in universe["players"]],
                   "traits": universe["traits"], "_allow_internal_caches": True}
        return player_display_attribute_summary(context, self.ids[name])

    def test_only_four_targeted_profiles_change_and_sources_are_attached(self):
        self.assertEqual(set(self.ids), NAMES)
        old = {(t["player_id"], t["trait_key"]): t for t in self.old["traits"]}
        allowed = {(self.ids[row["player_name"]], key): (value, row["evidence_urls"])
                   for row in self.overrides for key, value in row["traits"].items()}
        self.assertEqual(len(old), len(self.new["traits"]))
        for trait in self.new["traits"]:
            key = trait["player_id"], trait["trait_key"]
            if key in allowed:
                value, urls = allowed[key]
                self.assertEqual(trait["value"], value["value"], key)
                self.assertEqual(trait["components"]["manual_calibration"]["evidence_urls"], urls)
            else:
                self.assertEqual(trait, old[key], key)

    def test_players_finances_picks_health_and_prospects_are_unchanged(self):
        for key in ("players", "contracts", "draft_picks", "roster_slots", "player_health_states",
                    "player_health_profiles", "injury_events", "draft_classes", "draft_prospects",
                    "draft_prospect_traits"):
            self.assertEqual(self.new[key], self.old[key], key)

    def test_kyrie_skill_returns_without_creating_a_defensive_or_rebounding_star(self):
        before, after = self.grade(self.old, "Kyrie Irving"), self.grade(self.new, "Kyrie Irving")
        self.assertGreater(after["shooting"], before["shooting"] + 15)
        self.assertGreater(after["handle"], 80)  # direct display scale: old > 95 -> > 80 (TST-2 plan)
        self.assertGreater(after["portability"], 66.25)  # direct display scale: old > 85 -> > 66.25 (TST-2 plan)
        self.assertLess(after["defense"], 50)  # direct display scale: old < 70 -> < 50 (TST-2 plan)
        self.assertLess(after["rebounding"], before["rebounding"])

    def test_lively_retains_specialist_weaknesses_and_tiny_sample_extremes_are_reduced(self):
        before, after = self.values(self.old, "Dereck Lively II"), self.values(self.new, "Dereck Lively II")
        for key in ("shooting_range", "release_speed", "handle_pressure", "passing_reads"):
            self.assertEqual(before[key], after[key])
        for key in ("rim_pressure", "stamina_cardio", "shot_versatility"):
            self.assertGreater(after[key], before[key])
        for key in ("rim_deterrence", "offensive_rebounding", "scheme_iq"):
            self.assertLess(after[key], before[key])
        self.assertGreater(self.grade(self.new, "Dereck Lively II")["defense"], 60)  # direct display scale: old > 80 -> > 60 (TST-2 plan)

    def test_cmb_defense_improves_without_gifting_him_offensive_skills(self):
        before, after = self.values(self.old, "Collin Murray-Boyles"), self.values(self.new, "Collin Murray-Boyles")
        for key in ("shooting_range", "release_speed", "rim_pressure", "handle_pressure", "passing_reads"):
            self.assertEqual(before[key], after[key])
        self.assertGreater(self.grade(self.new, "Collin Murray-Boyles")["defense"],
                           self.grade(self.old, "Collin Murray-Boyles")["defense"] + 5)

    def test_george_defense_is_a_liability_but_creation_and_tools_are_preserved(self):
        before, after = self.values(self.old, "Keyonte George"), self.values(self.new, "Keyonte George")
        for key in ("shooting_range", "release_speed", "rim_pressure", "handle_pressure", "passing_reads",
                    "stamina_cardio", "foot_speed_lateral_agility"):
            self.assertEqual(before[key], after[key])
        self.assertLess(self.grade(self.new, "Keyonte George")["defense"],
                        self.grade(self.old, "Keyonte George")["defense"] - 20)

    def test_v2_career_keeps_all_four_players_and_earned_development(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "old.json"
            saved = create_league_save(ROOT, deepcopy(self.old), "GSW", path, seed=17)
            saved["development_trait_totals"] = {pid: {"passing_reads": 2.5} for pid in self.ids.values()}
            write_save(path, saved)
            fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
            before = canonical_with_save(deepcopy(self.old), load_save(path))
            after = canonical_with_save(deepcopy(self.new), load_save(path))
            for key in ("players", "traits", "contracts", "draft_picks", "player_health_states"):
                self.assertEqual(before[key], after[key], key)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), fingerprint)

    def test_corrections_reach_simulation_features_not_only_display_grades(self):
        features = {}
        for label, canonical in (("before", self.old), ("after", self.new)):
            features[label] = {
                name: player_feature_vector(canonical, next(p for p in canonical["players"]
                                                           if p["id"] == self.ids[name])).features
                for name in NAMES}
        before, after = features["before"], features["after"]
        self.assertGreater(after["Kyrie Irving"]["spacing"], before["Kyrie Irving"]["spacing"])
        self.assertGreater(after["Dereck Lively II"]["rim_pressure"], before["Dereck Lively II"]["rim_pressure"])
        self.assertGreater(after["Collin Murray-Boyles"]["defensive_events"], before["Collin Murray-Boyles"]["defensive_events"])
        self.assertGreater(after["Keyonte George"]["defensive_weak_link"], before["Keyonte George"]["defensive_weak_link"])
        self.assertEqual(after["Keyonte George"]["shot_creation"], before["Keyonte George"]["shot_creation"])
        self.assertEqual(after["Keyonte George"]["spacing"], before["Keyonte George"]["spacing"])

    def test_new_game_action_selects_new_baseline(self):
        with TemporaryDirectory() as directory:
            result = dispatch_app_action("create_save", {"team": "DAL", "seed": 17, "save_name": "tuning",
                                                           "ratings_model": "legacy_traits"},
                                         root=ROOT, save_dir=Path(directory), canonical=deepcopy(self.new))
            saved = load_save(result["save_path"])
            self.assertEqual(saved["meta"]["starting_data_version"], "2026-10-23-player-tuning-v3")
            actual = canonical_with_save(deepcopy(self.new), saved)
            for name in NAMES:
                self.assertEqual(self.values(actual, name), self.values(self.new, name))
