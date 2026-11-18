"""Team-separated imported obligations apply only to new versioned careers."""
from contextlib import ExitStack
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data import contract_imports as ci, save as sv, transactions as tx
from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.contract_protection import waived_total
from nba_gm_data.ingest import build_contracts
from nba_gm_data.schema import to_plain
from test_five_player_calibration import filled_measurements

ROOT = Path(__file__).resolve().parents[1]
PID = "player_por-damian-lillard"
GROSS = 22_516_603


class ContractImportSeparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get("CONTRACT_TEST_CANONICAL", ROOT / "data/canonical/universe_2026_27_offseason.json"))
        cls.canonical = json.loads(path.read_text())
        with gzip.open(ROOT / "data/canonical/baselines/2026-10-27-interior-offense-v9.json.gz", "rt") as handle:
            cls.old = json.load(handle)
        cls.resolutions = json.loads((ROOT / ci.RESOLUTIONS_FILE).read_text())
        cls.research = json.loads((ROOT / "data/research/player_contracts_bref_2026_10_13.json").read_text())
        cls.folder = tempfile.TemporaryDirectory()
        cls.saved = cls.create(cls.canonical, "new")
        cls.old_saved = cls.create(cls.old, "old")
        cls.old_saved["meta"].pop("imported_waived_salary_initialized", None)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    @classmethod
    def create(cls, canonical, name, mode="standard"):
        response = dispatch_app_action("create_save", {"team": "POR", "seed": 17, "save_name": name, "game_mode": mode},
                                       root=ROOT, save_dir=Path(cls.folder.name), canonical=canonical)
        return sv.load_save(response["save_path"], include_history=True)

    def contract(self, canonical):
        return next(row for row in canonical["contracts"] if row["player_id"] == PID)

    def resolve(self, research=None):
        return ci.resolve_contract_imports(self.old["players"], self.old["teams"],
                                          self.research if research is None else research, self.resolutions)

    def test_import_classifies_duplicate_aggregate_and_preserves_evidence(self):
        before = deepcopy(self.research)
        resolved, ledger, reports = self.resolve()
        rows = [row for row in resolved["contracts"] if row.get("normalized_name") == "damian lillard"]
        self.assertEqual([row["record_kind"] for row in rows].count("resolved_aggregate_source"), 2)
        self.assertEqual([row["record_kind"] for row in rows].count("resolved_active_contract"), 1)
        self.assertEqual(self.research, before)
        player = SimpleNamespace(**next(row for row in self.old["players"] if row["id"] == PID))
        contracts = to_plain(build_contracts([player], resolved, {}))
        self.assertEqual(contracts, [self.contract(self.canonical)])
        self.assertEqual(len(ledger), 1)
        self.assertEqual(len(ledger[0]["seasons"]), 5)
        self.assertEqual(len(reports[0]["source_rows"]), 2)

    def test_import_fails_closed_on_changed_or_duplicate_source(self):
        for mode in ("salary", "duplicate", "source"):
            research = deepcopy(self.research)
            row = next(row for row in research["contracts"] if row.get("normalized_name") == "damian lillard")
            if mode == "salary": row["seasons"][0]["salary"] += 1
            if mode == "duplicate": research["contracts"].append(deepcopy(row))
            if mode == "source": research["source"]["id"] = "different"
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.resolve(research)

    def test_original_term_guarantee_and_pending_option(self):
        contract = self.contract(self.canonical)
        self.assertEqual((contract["signed_season"], contract["original_contract_years"]), ("2025-26", 3))
        current, option = contract["seasons"]
        self.assertEqual((current["season"], current["salary"], current["guaranteed_salary"]), ("2026-27", 13_398_800, 13_398_800))
        self.assertEqual((option["season"], option["salary"], option["option_type"]), ("2027-28", 14_104_000, "player_option"))
        self.assertIsNone(option["guaranteed_salary"])
        self.assertNotIn("no_trade_clause", contract)
        self.assertIsNone(sv.contract_salary_for_season(contract, "2028-29"))

    def test_other_source_collections_and_contracts_are_unchanged(self):
        # Later reviewed changes are excluded, not hidden: BUG-B filled 11 players' measurements (filled_measurements keeps every
        # other player difference failing), and v11 five-player calibration (reviewed 2026-11-10) rewrote traits for
        # Edwards, Coward, Vassell, Duren, Kawhi plus Wembanyama's rim anchor (TST-2 plan).
        calibrated = {r["player_id"] for r in json.loads((ROOT / "data/overrides/five_player_calibration_v11.json").read_text())["players"]}
        calibrated.add("player_sas-victor-wembanyama")
        self.assertEqual(len(calibrated), 6)
        self.assertEqual(filled_measurements(self.old["players"], self.canonical["players"]), self.canonical["players"], "players")
        self.assertEqual([r for r in self.old["traits"] if r["player_id"] not in calibrated],
                         [r for r in self.canonical["traits"] if r["player_id"] not in calibrated], "traits")
        for key in ("roster_slots", "player_health_profiles", "player_health_states", "injury_events", "draft_picks"):
            self.assertEqual(self.old[key], self.canonical[key], key)
        old = {row["player_id"]: row for row in self.old["contracts"]}
        changed = [row["player_id"] for row in self.canonical["contracts"] if row != old[row["player_id"]]]
        self.assertEqual(changed, [PID])

    def test_new_ledger_unknown_net_idempotence_and_no_resurrection(self):
        saved = deepcopy(self.saved)
        entry = saved["waived_salary_obligations"][0]
        self.assertEqual(entry["team_id"], "team_mil")
        self.assertIsNone(entry["original_contract_years"])
        self.assertEqual(len(entry["original_stretch_schedule"]), 5)
        self.assertEqual(len(entry["seasons"]), 4)
        self.assertEqual(entry["setoff"]["status"], "unknown_unverified")
        for row in entry["seasons"]:
            self.assertEqual((row["salary"], row["gross_salary"], row["unverified_reserve"]), (GROSS, GROSS, GROSS))
            self.assertIsNone(row["net_salary"])
            self.assertIsNone(row["setoff_amount"])
        original = deepcopy(saved)
        ci.initialize_imported_obligations(saved, self.canonical)
        ci.initialize_imported_obligations(saved, self.canonical)
        self.assertEqual(saved, original)
        saved["waived_salary_obligations"] = []
        ci.initialize_imported_obligations(saved, self.canonical)
        self.assertEqual(saved["waived_salary_obligations"], [])
        fresh = {"meta": {"season": "2026-27", "starting_data_version": self.saved["meta"]["starting_data_version"]}}
        ci.initialize_imported_obligations(fresh, self.canonical)
        self.assertEqual(fresh["waived_salary_obligations"], original["waived_salary_obligations"])
        with self.assertRaises(ValueError): ci.initialize_imported_obligations(deepcopy(self.old_saved), self.canonical)

    def test_real_player_card_and_cap_queries_roundtrip_without_mutation(self):
        path = Path(self.folder.name) / "card.json"
        sv.write_save(path, deepcopy(self.saved))
        before = path.read_bytes()
        card = dispatch_app_action("player_card", {"save_path": str(path), "player_id": PID},
                                   root=ROOT, save_dir=path.parent, canonical=self.canonical)
        self.assertEqual([(row["season"], row["salary_millions"]) for row in card["salary_seasons"] if row["salary_millions"] is not None],
                         [("2026-27", 13.4), ("2027-28", 14.1)])
        new, old = deepcopy(self.saved), deepcopy(self.old_saved)
        active, original = sv.canonical_with_save(self.canonical, new), sv.canonical_with_save(self.old, old)
        snapshot = deepcopy(new)
        for season in ("2026-27", "2027-28", "2028-29", "2029-30", "2030-31"):
            delta = GROSS if season < "2030-31" else 0
            for _ in range(2):
                cap = {team: sv.team_cap_summary(active, new, team, season) for team in ("team_por", "team_mil")}
                prior = {team: sv.team_cap_summary(original, old, team, season) for team in cap}
                self.assertEqual(cap["team_por"]["salary_total"], prior["team_por"]["salary_total"] - delta)
                self.assertEqual(cap["team_mil"]["salary_total"], prior["team_mil"]["salary_total"] + delta)
                self.assertEqual(cap["team_mil"]["unverified_waived_reserve_millions"], round(delta / 1_000_000, 2))
        self.assertEqual(new, snapshot)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sv.load_save(path)["waived_salary_obligations"], self.saved["waived_salary_obligations"])

    def test_old_pinned_careers_preserve_trades_extensions_options_and_waivers(self):
        variants = [deepcopy(self.old_saved) for _ in range(6)]
        variants[1]["roster_overrides"][PID] = "team_was"
        variants[2]["contract_overrides"][PID] = {"seasons": [{"season": "2026-27", "salary": 15_000_000}, {"season": "2027-28", "salary": 17_000_000}]}
        variants[3]["contract_overrides"][PID] = {"seasons": [{"season": "2026-27", "salary": 13_398_800}, {"season": "2027-28", "salary": 14_104_000, "option_exercised": True}]}
        variants[4]["contract_overrides"][PID] = {"seasons": [{"season": "2026-27", "salary": 13_398_800}]}
        variants[5]["roster_overrides"][PID] = None
        variants[5]["waived_salary_obligations"] = [{"id": "user-buyout", "team_id": "team_por", "player_id": PID, "seasons": [{"season": "2026-27", "salary": 5_000_000}]}]
        for i, saved in enumerate(variants):
            with self.subTest(variant=i):
                left = sv.ensure_league_save_defaults(deepcopy(saved), self.old)
                right = sv.ensure_league_save_defaults(deepcopy(saved), self.canonical)
                self.assertEqual(left, right)
                self.assertNotIn("imported_waived_salary_initialized", right["meta"])
                self.assertEqual(sv.canonical_with_save(self.old, left)["contracts"], sv.canonical_with_save(self.canonical, right)["contracts"])
                path = Path(self.folder.name) / f"legacy-{i}.json"
                sv.write_save(path, saved)
                before = path.read_bytes()
                def card(canonical):
                    return dispatch_app_action("player_card", {"save_path": str(path), "player_id": PID}, root=ROOT, save_dir=path.parent, canonical=canonical)
                self.assertEqual(card(self.old), card(self.canonical))
                self.assertEqual(path.read_bytes(), before)

    def test_option_override_and_actual_expiry_leave_former_team_debt_intact(self):
        for option in ("pending", "exercised", "declined"):
            saved = deepcopy(self.saved)
            terms = deepcopy(self.contract(self.canonical)["seasons"])
            if option == "declined": terms = terms[:1]
            if option == "exercised": terms[1].update(option_type=None, option_exercised=True, guaranteed_salary=14_104_000)
            saved["contract_overrides"][PID] = {"seasons": terms}
            debt = deepcopy(saved["waived_salary_obligations"])
            # Keep actual expiry/rights/ownership behavior, isolate unrelated AI
            # roster activity and retirement from this contract boundary test.
            with ExitStack() as stack:
                for name, result in (("should_retire", False), ("strategic_free_agent_signings", set()), ("auto_fill_rosters", set()), ("archive_excess_free_agents", [])):
                    stack.enter_context(patch.object(sv, name, return_value=result))
                for current, following in (("2026-27", "2027-28"), ("2027-28", "2028-29")):
                    saved["meta"]["season"] = current
                    sv.apply_offseason_roster_transitions(self.canonical, saved, current, following, 17)
                    owner = sv.canonical_with_save(self.canonical, saved)
                    player = next(row for row in owner["players"] if row["id"] == PID)
                    self.assertEqual(player.get("team_id") is None, option == "declined" or following == "2028-29")
            self.assertEqual(saved["waived_salary_obligations"], debt)
            self.assertEqual(waived_total(saved, "team_mil", "2029-30"), GROSS)
            self.assertEqual(waived_total(saved, "team_mil", "2030-31"), 0)

    def test_actual_trade_moves_only_active_contract_not_milwaukee_debt(self):
        saved = deepcopy(self.saved)
        saved["meta"]["human_team_ids"] = ["team_por", "team_was"]
        active = sv.canonical_with_save(self.canonical, saved)
        other = next(row for row in active["players"] if row.get("team_id") == "team_was")
        saved["contract_overrides"][other["id"]] = {"seasons": [{"season": "2026-27", "salary": 13_398_800}]}
        offer = {"accepted_by_all": True, "legality": {"status": "legal"}, "evaluations": [],
                 "proposal": {"id": "ownership-test", "date": saved["state"]["current_date"], "from_team_id": "team_por", "to_team_id": "team_was",
                              "from_assets": [{"kind": "player", "id": PID}], "to_assets": [{"kind": "player", "id": other["id"]}]}}
        saved["pending_trade_proposals"] = [offer]
        debt = deepcopy(saved["waived_salary_obligations"])
        result = tx.apply_trade_to_state(saved, "ownership-test", date=saved["state"]["current_date"], canonical=self.canonical)
        self.assertEqual(result["status"], "applied", result)
        active = sv.canonical_with_save(self.canonical, saved)
        self.assertEqual(next(row["team_id"] for row in active["players"] if row["id"] == PID), "team_was")
        self.assertEqual(self.contract(active)["seasons"][0]["salary"], 13_398_800)
        self.assertEqual(saved["waived_salary_obligations"], debt)
        self.assertEqual(waived_total(saved, "team_mil", "2026-27"), GROSS)

    def test_fantasy_initialization_has_one_fixed_former_team_obligation(self):
        saved = self.create(self.canonical, "fantasy", "fantasy_draft")
        self.assertEqual(len(saved["waived_salary_obligations"]), 1)
        self.assertEqual(saved["waived_salary_obligations"][0]["team_id"], "team_mil")
        saved["roster_overrides"][PID] = "team_bos"
        ci.initialize_imported_obligations(saved, self.canonical)
        self.assertEqual(len(saved["waived_salary_obligations"]), 1)
        self.assertEqual(sv.canonical_with_save(self.canonical, saved)["waived_salary_obligations"][0]["team_id"], "team_mil")

    def test_completed_fantasy_draft_preserves_separate_contract_and_ledger(self):
        created = dispatch_app_action("create_save", {"team": "POR", "seed": 17,
                                      "save_name": "completed-fantasy", "game_mode": "fantasy_draft"},
                                      root=ROOT, save_dir=Path(self.folder.name), canonical=self.canonical)
        path = Path(created["save_path"])
        saved = sv.load_save(path)
        debt = deepcopy(saved["waived_salary_obligations"])
        dispatch_app_action("fantasy_draft_sim_all", {"save_path": str(path)},
                            root=ROOT, save_dir=path.parent, canonical=self.canonical)
        saved = sv.load_save(path)
        active = sv.canonical_with_save(self.canonical, saved)
        self.assertIsNotNone(next(row["team_id"] for row in active["players"] if row["id"] == PID))
        self.assertEqual(self.contract(active)["seasons"], self.contract(self.canonical)["seasons"])
        self.assertEqual(saved["waived_salary_obligations"], debt)


if __name__ == "__main__":
    unittest.main()
