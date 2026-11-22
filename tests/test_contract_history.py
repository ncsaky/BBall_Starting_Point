"""CONTRACT-TERMS part 1: real contracts' signing history and the CBA extension rules."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from nba_gm_data.contract_ai import (
    extension_contract_window,
    extension_deadline_for,
    extension_first_year_limit,
    extension_window_open_on,
)
from nba_gm_data.contract_history import build_contract_history, load_history, matching_prefix, salary_rows
from nba_gm_data.save import legal_actions_for_date

ROOT = Path(__file__).resolve().parents[1]


def contract(seasons, *, signed=None, years=None, history=None, active="2026-27", salary=10_000_000):
    rows = [{"season": s, "salary": salary} for s in seasons]
    out = {"player_id": "p1", "seasons": rows, "signed_season": signed, "original_contract_years": years,
           "_active_season": active}
    if history is not None:
        out["contract_history"] = history
    return out


class ExtensionRuleTests(unittest.TestCase):
    def test_rookie_scale_final_year_is_eligible(self):
        history = {"kind": "rookie_scale", "signed_season": "2023-24", "draft_year": 2023}
        c = contract(["2026-27"], signed="2023-24", years=4, history=history)
        w = extension_contract_window(c, {"draft_year": 2023, "draft_round": 1})
        self.assertTrue(w["eligible"])
        self.assertEqual((w["extension_kind"], w["max_new_years"]), ("rookie_scale", 5))

    def test_rookie_scale_before_final_year_waits(self):
        history = {"kind": "rookie_scale", "signed_season": "2024-25", "draft_year": 2024}
        c = contract(["2026-27", "2027-28"], signed="2024-25", years=4, history=history)
        w = extension_contract_window(c, {"draft_year": 2024, "draft_round": 1})
        self.assertEqual(w["eligibility_status"], "rookie_scale_not_final_year")

    def test_game_drafted_first_rounder_counts_as_rookie_scale(self):
        c = contract(["2029-30"], signed="2026-27", years=4, active="2029-30")
        player = {"draft_year": "2026", "overall_pick": 12}   # game-drafted players carry overall_pick, no round
        self.assertEqual(extension_contract_window(c, player)["eligibility_status"], "eligible_rookie_scale")

    def test_one_or_two_season_deals_cannot_extend(self):
        c = contract(["2026-27", "2027-28"], signed="2026-27", years=2, history={"kind": "new_2026", "signed_season": "2026-27"})
        self.assertEqual(extension_contract_window(c)["eligibility_status"], "original_contract_shorter_than_three_years")

    def test_second_anniversary_for_three_and_four_season_deals(self):
        h = {"kind": "reported", "signed_season": "2024-25"}
        four = contract(["2026-27", "2027-28"], signed="2024-25", years=4, history=h)
        self.assertTrue(extension_contract_window(four)["eligible"])
        self.assertEqual(extension_contract_window(four)["max_new_years"], 3)   # five seasons including this one
        early = contract(["2026-27", "2027-28", "2028-29"], signed="2025-26", years=4, history={"kind": "reported", "signed_season": "2025-26"})
        self.assertEqual(extension_contract_window(early)["eligibility_status"], "not_in_extension_window")

    def test_third_anniversary_for_five_season_deals(self):
        h = {"kind": "reported", "signed_season": "2024-25"}
        five = contract(["2026-27", "2027-28", "2028-29"], signed="2024-25", years=5, history=h)
        self.assertEqual(extension_contract_window(five)["eligibility_status"], "not_in_extension_window")
        five_later = dict(five, _active_season="2027-28")
        self.assertTrue(extension_contract_window(five_later)["eligible"])

    def test_unknown_signing_date_uses_the_last_two_seasons_rule_and_says_so(self):
        h = {"kind": "running_since_2025", "signed_season": None, "signed_season_earliest": "2022-23",
             "signed_season_latest": "2025-26", "original_contract_years_min": 3}
        w = extension_contract_window(contract(["2026-27", "2027-28"], history=h), {})
        self.assertEqual(w["eligibility_status"], "eligible_history_unknown")
        self.assertFalse(w["history_known"])
        self.assertIn("isn't on record", w["eligibility_text"])
        three_left = contract(["2026-27", "2027-28", "2028-29"], history=dict(h, original_contract_years_min=4))
        self.assertEqual(extension_contract_window(three_left)["eligibility_status"], "not_in_extension_window")

    def test_first_year_limit_is_140_percent_or_the_average(self):
        c = contract(["2026-27"], salary=10_000_000)
        limit = extension_first_year_limit(c, {"draft_year": 2018}, "2027-28")
        from nba_gm_data.cap_rules import AVERAGE_SALARY_CAP_SHARE, cap_lines_for_season
        average = cap_lines_for_season("2027-28")["salary_cap"] * AVERAGE_SALARY_CAP_SHARE
        self.assertAlmostEqual(limit, 1.4 * max(10_000_000, average), delta=1)
        star = contract(["2026-27"], salary=50_000_000)
        self.assertLess(extension_first_year_limit(star, {"draft_year": 2012}, "2027-28"), 1.4 * 50_000_000)

    def test_window_dates_and_deadlines(self):
        self.assertFalse(extension_window_open_on("2027-06-20"))
        self.assertFalse(extension_window_open_on("2027-07-05"))
        self.assertTrue(extension_window_open_on("2027-07-06"))
        self.assertTrue(extension_window_open_on("2027-03-20"))   # a final-year veteran can extend in season
        self.assertIn("extensions", legal_actions_for_date("2027-03-20"))
        self.assertNotIn("extensions", legal_actions_for_date("2027-06-20"))
        h = {"kind": "reported", "signed_season": "2023-24"}
        final_year = contract(["2026-27"], signed="2023-24", years=4, history=h)
        self.assertEqual(extension_deadline_for(final_year, {}, 2026), "2027-06-16")
        two_left = contract(["2026-27", "2027-28"], signed="2023-24", years=5, history=h)
        self.assertEqual(extension_deadline_for(two_left, {}, 2026), "2026-10-20")


class ContractHistoryDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = load_history(ROOT)
        cls.universe = json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text())

    def record(self, name):
        return next(v for v in self.history.values() if v.get("player_name") == name)

    def test_podziemski_is_a_rookie_scale_deal_from_2023(self):
        r = self.record("Brandin Podziemski")
        self.assertEqual((r["kind"], r["original_contract_years"], r["signed_season"]), ("rookie_scale", 4, "2023-24"))
        stored = next(c for c in self.universe["contracts"] if c["player_id"] == "player_gsw-brandin-podziemski")
        self.assertEqual((stored["original_contract_years"], stored["signed_season"]), (4, "2023-24"))

    def test_unknown_lengths_are_left_unknown(self):
        unknown = [v for v in self.history.values() if v["kind"] == "running_since_2025"]
        self.assertTrue(unknown)
        for r in unknown:
            self.assertIsNone(r["original_contract_years"])
            self.assertIsNone(r["signed_season"])
            self.assertGreaterEqual(r["original_contract_years_min"], len(r["listed_seasons"]) + 1)

    def test_extension_after_the_2025_table_is_recognised(self):
        older = {"seasons": [{"season": "2025-26", "salary": 5}, {"season": "2026-27", "salary": 6}]}
        rows = salary_rows({"seasons": [{"season": "2026-27", "salary": 6}, {"season": "2027-28", "salary": 9}]})
        self.assertEqual(matching_prefix(rows, older), 1)

    def test_builder_reproduces_the_stored_file(self):
        snapshot = json.loads((ROOT / "data/canonical/universe_2025_26_preseason.json").read_text())
        rebuilt = build_contract_history(self.universe, snapshot, ROOT)
        # Without the career/bird callables only the rookie_2025 refinement can differ.
        for pid, record in self.history.items():
            if record["kind"] in {"rookie_2025", "running_since_2025"}:
                continue
            self.assertEqual(rebuilt[pid]["kind"], record["kind"], record["player_name"])
            self.assertEqual(rebuilt[pid]["original_contract_years"], record["original_contract_years"])


class SaveConsistencyTests(unittest.TestCase):
    """The Set The Roster list and the extension screen agree (the Podziemski report)."""

    def test_listed_rookie_extensions_are_accepted_by_the_extension_screen(self):
        from nba_gm_data.app_actions import extension_room_payload
        from nba_gm_data.offseason_decisions import stop_four_checklist
        from nba_gm_data.save import canonical_with_save, create_league_save, load_save
        from nba_gm_data.storage import load_universe_json
        canonical = load_universe_json(ROOT / "data/canonical/universe_2026_27_offseason.json")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "gsw.json"
            create_league_save(ROOT, canonical, "GSW", path, seed=7)
            save = load_save(path)
            active = canonical_with_save(canonical, save)
            listed = [i["player_id"] for i in stop_four_checklist(canonical, save, "team_gsw", active=active)["items"]
                      if i["kind"] == "rookie_extension"]
            self.assertIn("player_gsw-brandin-podziemski", listed)
            room = extension_room_payload(canonical, path, "GSW")
            eligible = {c["player_id"] for c in room["candidates"] if c["eligible"]}
            self.assertTrue(set(listed) <= eligible)
            pod = next(c for c in room["candidates"] if c["player_id"] == "player_gsw-brandin-podziemski")
            self.assertIsNone(pod["eligibility_reason"])
            self.assertEqual(pod["safe_years"], 5)


if __name__ == "__main__":
    unittest.main()
