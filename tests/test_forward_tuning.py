from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.ingest import build_universe
from nba_gm_data.save import canonical_with_save, create_league_save, load_save, write_save
from nba_gm_data.schema import to_plain
from nba_gm_data.sim import espn_team_id_map, load_sim_context, sim_game_with_context
from verify_forward_tuning import NAMES, ROOT, VERSION, measurements, previous, verify_scope


class ForwardTuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = previous()
        # Historical V5 scope must not absorb subsequent starting-data updates.
        with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-forward-tuning-v5.json.gz", "rt") as handle:
            cls.new = json.load(handle)
        cls.before = measurements(cls.old)
        cls.after = measurements(cls.new)
        cls.ids = {p["name"]: p["id"] for p in cls.new["players"] if p["name"] in NAMES}

    def test_exact_two_player_scope_with_prospects_health_finances_and_other_traits_unchanged(self):
        self.assertEqual(verify_scope(self.old, self.new), 30)

    def test_meaningful_gap_is_not_a_cosmetic_overall_or_all_trait_nerf(self):
        gordon, randle = self.after["Aaron Gordon"], self.after["Julius Randle"]
        for key in ("display", "fixed24_display"):
            self.assertGreater(gordon[key]["overall"] - randle[key]["overall"], 3.5)
            self.assertLess(gordon[key]["overall"] - randle[key]["overall"], 7)
            self.assertGreater(gordon[key]["defense"], randle[key]["defense"] + 15)
            self.assertGreater(randle[key]["creation"], gordon[key]["creation"] + 5)
            self.assertGreater(randle[key]["passing"], gordon[key]["passing"])
        for key in ("rebounding", "stamina", "rim_pressure"):
            self.assertGreater(randle["display"][key], self.before["Julius Randle"]["display"][key])
        self.assertLess(gordon["display"]["rim_deterrence"], self.before["Aaron Gordon"]["display"]["rim_deterrence"])

    def test_simulation_retains_randle_creation_and_passing_while_gordon_defends_and_fits(self):
        gordon, randle = self.after["Aaron Gordon"]["sim"], self.after["Julius Randle"]["sim"]
        self.assertGreater(gordon["impact"], randle["impact"] + 5)
        self.assertGreater(gordon["defensive_events"], randle["defensive_events"] + 20)
        self.assertGreater(gordon["spacing"], randle["spacing"])
        self.assertGreater(randle["shot_creation"], gordon["shot_creation"])
        self.assertGreater(randle["passing"], gordon["passing"])
        self.assertGreater(gordon["impact"], self.before["Aaron Gordon"]["sim"]["impact"])
        self.assertLess(randle["impact"], self.before["Julius Randle"]["sim"]["impact"])

    def test_ai_on_court_values_change_but_health_risk_does_not(self):
        self.assertGreater(self.after["Aaron Gordon"]["asset"]["on_court_value"],
                           self.before["Aaron Gordon"]["asset"]["on_court_value"])
        self.assertLess(self.after["Julius Randle"]["asset"]["on_court_value"],
                        self.before["Julius Randle"]["asset"]["on_court_value"])
        for name in NAMES:
            self.assertEqual(self.before[name]["asset"]["health_risk"], self.after[name]["asset"]["health_risk"])

    def test_v4_career_and_earned_development_survive_v5_entry_and_reload(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "career.json"
            saved = create_league_save(ROOT, deepcopy(self.old), "DEN", path, seed=17)
            saved["development_trait_totals"] = {pid: {"passing_reads": 2.5} for pid in self.ids.values()}
            write_save(path, saved)
            fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
            before = canonical_with_save(deepcopy(self.old), load_save(path))
            after = canonical_with_save(deepcopy(self.new), load_save(path))
            for key in ("players", "traits", "contracts", "draft_picks", "pick_obligations",
                        "player_health_states", "player_health_profiles"):
                self.assertEqual(before[key], after[key], key)
            values = {(t["player_id"], t["trait_key"]): t["value"] for t in after["traits"]}
            for pid in self.ids.values():
                original = next(t["value"] for t in self.old["traits"]
                                if t["player_id"] == pid and t["trait_key"] == "passing_reads")
                self.assertEqual(values[pid, "passing_reads"], original + 2.5)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), fingerprint)

    def test_new_game_action_uses_v5_without_losing_pick_terms(self):
        from nba_gm_data.save import load_pick_obligation_overrides
        with TemporaryDirectory() as directory:
            result = dispatch_app_action("create_save", {"team": "DEN", "seed": 17, "save_name": "forward"},
                                         root=ROOT, save_dir=Path(directory), canonical=deepcopy(self.new))
            saved = load_save(result["save_path"])
            self.assertEqual(saved["meta"]["starting_data_version"], VERSION)
            old_terms = load_pick_obligation_overrides(ROOT, self.old)
            new_terms = load_pick_obligation_overrides(ROOT, self.new)
            self.assertGreater(len(old_terms), 0)
            self.assertEqual(old_terms, new_terms)
            self.assertTrue({row["id"] for row in new_terms}.issubset({row["id"] for row in saved["pick_obligations"]}))
            active = canonical_with_save(deepcopy(self.new), saved)
            for name, pid in self.ids.items():
                actual = {t["trait_key"]: t["value"] for t in active["traits"] if t["player_id"] == pid}
                expected = {t["trait_key"]: t["value"] for t in self.new["traits"] if t["player_id"] == pid}
                self.assertEqual(actual, expected, name)

    def test_rebuild_is_deterministic(self):
        self.assertEqual(to_plain(build_universe(ROOT)), to_plain(build_universe(ROOT)))

    def test_seeded_full_game_smoke_is_replayable_and_uses_corrected_profiles(self):
        contexts = [load_sim_context(ROOT, deepcopy(data)) for data in (self.old, self.new)]
        current_teams = {p["team_id"] for p in self.new["players"] if p["id"] in self.ids.values()}
        team_ids = {key for key, team in espn_team_id_map(self.new).items() if team["id"] in current_teams}
        game = next(game for game in contexts[0]["schedule"]
                    if {str(game["homeTeamId"]), str(game["awayTeamId"])} == team_ids)
        changed = 0
        for seed in (17, 29, 41):
            before, after = [to_plain(sim_game_with_context(context, str(game["externalGameId"]),
                                                          mode="sandbox-sim", seed=seed)) for context in contexts]
            repeat = to_plain(sim_game_with_context(contexts[1], str(game["externalGameId"]), mode="sandbox-sim", seed=seed))
            self.assertEqual(after, repeat)
            self.assertGreater(after["home_score"], 0)
            self.assertGreater(after["away_score"], 0)
            self.assertTrue(set(self.ids.values()).issubset({p["player_id"] for p in after["player_lines"]}))
            changed += before["player_lines"] != after["player_lines"]
        self.assertGreater(changed, 0)
