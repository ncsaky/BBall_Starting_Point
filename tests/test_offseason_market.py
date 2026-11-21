"""FA-REAL slice 2: the thin AI market fix (payroll_plan) and the stops (defaults when stop 1 closes, stop names)."""
from __future__ import annotations

import unittest

from nba_gm_data import app_actions as aa, cap_rules, offseason_decisions as od, payroll_plan as pp

from test_trade_volume import SEASON, league, save_for

LINE = cap_rules.cap_lines_for_season(SEASON)["tax_line"]


def with_office(data: dict, team: str, *biases: str, urgency: float = 50.0) -> dict:
    data["front_office_traits"] = {team: {"savvy": 60, "urgency": urgency, "patience": 50, "loyalty": 50,
                                          "biases": [{"key": key} for key in biases]}}
    return data


class MarketFix(unittest.TestCase):
    def test_a_team_keeps_its_regular_with_bird_rights_up_to_the_line(self):
        # Before: a retooling team kept $4M-$8M below the line even to keep its own 30-minute player (DiVincenzo).
        data = league(payroll_a=180_000_000)
        saved = save_for("2027-06-20", "exiting")
        add = LINE - 180_000_000 - 1_500_000
        self.assertTrue(pp.payroll_check(data, saved, "a", SEASON, add_salary=add, minutes=30, kind="re_signing", age=28)["ok"])

    def test_the_mid_level_for_a_rotation_need_goes_up_to_the_line(self):
        data = league(payroll_a=185_000_000)
        saved = save_for("2027-07-01", "entering")
        add = LINE - 185_000_000 - 1_000_000
        self.assertTrue(pp.payroll_check(data, saved, "a", SEASON, add_salary=add, minutes=24, kind="free_agency", age=27)["ok"])
        fringe = pp.payroll_check(data, saved, "a", SEASON, add_salary=add, minutes=8, kind="free_agency", age=27)
        self.assertEqual(fringe["reason"], "keeps_room_below_the_line_for_its_phase", "fringe additions keep room")

    def test_rebuilding_teams_still_keep_trade_room(self):
        data = league(payroll_a=170_000_000)
        saved = save_for("2027-07-01", "rebuilding")
        check = pp.payroll_check(data, saved, "a", SEASON, add_salary=15_000_000, minutes=24, kind="free_agency", age=27)
        self.assertEqual(check["reason"], "keeps_room_below_the_line_for_its_phase")

    def test_front_office_tax_habits(self):
        saved = save_for("2027-07-01", "entering")
        add = LINE - 185_000_000 - 1_000_000
        averse = with_office(league(payroll_a=185_000_000), "a", "tax_averse")
        check = pp.payroll_check(averse, saved, "a", SEASON, add_salary=add, minutes=24, kind="free_agency", age=27)
        self.assertFalse(check["ok"], "an office known to avoid the tax stays $3M under the line")
        self.assertIn("under about", pp.plain_words(check))
        # What the owner accepts in tax: more for an office that pays to win, less for a tax-averse one.
        spender = with_office(league(), "a", "spends_tax")
        self.assertAlmostEqual(pp.personality_tax_factor(spender, saved, "a"), pp.SPENDS_TAX_FACTOR)
        self.assertAlmostEqual(pp.personality_tax_factor(averse, saved, "a"), pp.TAX_AVERSE_FACTOR)
        urgent = with_office(league(), "a", urgency=90)
        self.assertGreater(pp.personality_tax_factor(urgent, saved, "a"), 1.0)
        self.assertEqual(pp.personality_tax_factor(league(), saved, "a"), 1.0, "no traits: the middle of the league")


class Stops(unittest.TestCase):
    def test_stop_names(self):
        self.assertEqual(aa.offseason_stop_name("re_signing", {}), "decide_who_to_keep")
        self.assertEqual(aa.offseason_stop_name("free_agency", {"status": "active"}), "make_offers")
        self.assertEqual(aa.offseason_stop_name("free_agency", {"status": "completed"}), "finalize")

    def test_undecided_items_take_their_defaults_when_stop_one_closes(self):
        save = {"meta": {"season": "2026-27", "user_team_id": "u", "human_team_ids": ["u"]},
                "state": {"current_date": "2027-06-29", "phase": "re_signing"}}
        od.store(save)["qualifying_offers"]["2027-28:y"] = {"player_id": "y", "name": "Young", "team_id": "u",
                                                             "season": "2027-28", "status": "pending",
                                                             "deadline": "2027-06-29"}
        od.store(save)["qualifying_offers"]["2027-28:z"] = {"player_id": "z", "name": "Other", "team_id": "ai",
                                                             "season": "2027-28", "status": "tendered"}
        notes = od.finalize_stop_one({"players": [], "contracts": [], "teams": []}, save)
        self.assertEqual(save["offseason_decisions"]["qualifying_offers"]["2027-28:y"]["status"], "not_tendered")
        self.assertEqual(save["offseason_decisions"]["qualifying_offers"]["2027-28:z"]["status"], "tendered")
        self.assertTrue(any("Young" in note for note in notes))

    def test_a_qualifying_offer_cannot_be_sent_after_june_29(self):
        save = {"meta": {"season": "2026-27", "user_team_id": "u", "human_team_ids": ["u"]},
                "state": {"current_date": "2027-07-02"}}
        od.store(save)["qualifying_offers"]["2027-28:y"] = {"player_id": "y", "team_id": "u", "season": "2027-28",
                                                             "status": "not_tendered", "deadline": "2027-06-29",
                                                             "amount": 5e6}
        self.assertFalse(od.user_tender(save, "y", True)["ok"])
        save["state"]["current_date"] = "2027-06-28"
        self.assertTrue(od.user_tender(save, "y", True)["ok"])


if __name__ == "__main__":
    unittest.main()
