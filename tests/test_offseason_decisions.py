"""FA-REAL slice 2: options, early terminations, rookie-scale options and qualifying offers (offseason_decisions)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from nba_gm_data import cap_ledger as cl, offseason_decisions as od, play

NEXT = "2027-28"
EXPIRING = "2026-27"


def player(pid: str, *, draft_year: int, round_: int = 1, pick: int = 10, age: float = 23.0, team: str = "t",
           minutes: float = 26.0) -> dict:
    return {"id": pid, "name": pid.title(), "draft_year": draft_year, "draft_round": round_, "draft_position": pick,
            "age": age, "team_id": team, "minutes_projection": minutes}


def contract(pid: str, salaries: dict[str, float], options: dict[str, str] | None = None) -> dict:
    return {"player_id": pid, "seasons": [{"season": s, "salary": v, "option_type": (options or {}).get(s)}
                                          for s, v in salaries.items()]}


def summer_save(**extra) -> dict:
    return {"meta": {"season": EXPIRING, "user_team_id": "human", "seed": 17},
            "state": {"current_date": "2027-06-17", "phase": "re_signing"}, **extra}


class QualifyingOfferAmounts(unittest.TestCase):
    def test_first_rounder_after_year_four_gets_his_salary_plus_the_slot_percentage(self):
        rookie = player("miller", draft_year=2023, pick=2)
        starter = {"player_season_stats": {"miller": {"games_started": 70, "minutes": 2300}}}
        terms = od.qualifying_offer_terms(starter, rookie, contract("miller", {EXPIRING: 15_104_626}), EXPIRING)
        self.assertTrue(terms["eligible"])
        self.assertEqual(terms["route"], "rookie_scale")
        self.assertEqual(terms["amount"], round(15_104_626 * (1 + od.qo_rookie_pct(2))))
        self.assertAlmostEqual(od.qo_rookie_pct(1), 0.30)
        self.assertAlmostEqual(od.qo_rookie_pct(30), 0.50)
        # Checked against real 2024 offers: pick 20 about 44% (Precious Achiuwa), pick 5 about 33% (Isaac Okoro).
        self.assertAlmostEqual(od.qo_rookie_pct(20), 0.443, delta=0.015)
        self.assertAlmostEqual(od.qo_rookie_pct(5), 0.326, delta=0.01)
        self.assertGreater(terms["max_qo_amount"], terms["amount"], "the optional maximum offer: five max years")

    def test_starter_criteria_move_the_offer(self):
        late = player("late", draft_year=2023, pick=22)
        stats = {"player_season_stats": {"late": {"games_started": 60, "minutes": 2400}}}
        plain = od.qualifying_offer_terms({}, late, contract("late", {EXPIRING: 3_000_000}), EXPIRING)
        starter = od.qualifying_offer_terms(stats, late, contract("late", {EXPIRING: 3_000_000}), EXPIRING)
        self.assertGreater(starter["amount"], plain["amount"], "a pick outside the top nine who starts gets No. 9's offer")
        self.assertIn("No. 9", starter["basis"])
        high = player("high", draft_year=2023, pick=3)
        missed = od.qualifying_offer_terms({}, high, contract("high", {EXPIRING: 12_000_000}), EXPIRING)
        self.assertIn("No. 15", missed["basis"], "a top-14 pick who misses gets the lesser No. 15 offer")
        self.assertLess(missed["amount"], round(12_000_000 * (1 + od.qo_rookie_pct(3))))

    def test_other_young_players_get_135_percent_or_the_minimum_plus_200k(self):
        second = player("second", draft_year=2024, round_=2, pick=45)
        cheap = od.qualifying_offer_terms({}, second, contract("second", {EXPIRING: 2_000_000}), EXPIRING)
        self.assertEqual(cheap["route"], "standard")
        self.assertEqual(cheap["amount"], round(max(2_000_000 * 1.35, cl.minimum_salary(NEXT, 3) + 200_000)))
        paid = od.qualifying_offer_terms({}, second, contract("second", {EXPIRING: 6_000_000}), EXPIRING)
        self.assertEqual(paid["amount"], 8_100_000, "135% of $6M")

    def test_eligibility(self):
        veteran = player("vet", draft_year=2019, age=29)
        self.assertFalse(od.qualifying_offer_terms({}, veteran, contract("vet", {EXPIRING: 9e6}), EXPIRING)["eligible"])
        rookie_year_three = player("r3", draft_year=2024, pick=12)   # three seasons in: eligible by service
        self.assertTrue(od.qualifying_offer_terms({}, rookie_year_three, contract("r3", {EXPIRING: 4e6}), EXPIRING)["eligible"])
        declined = summer_save(offseason_decisions={"options": {}, "qualifying_offers": {},
                                                    "declined_rookie_options": {"r4": {"salary": 5e6}}})
        r4 = player("r4", draft_year=2023, pick=8)
        terms = od.qualifying_offer_terms(declined, r4, contract("r4", {EXPIRING: 5e6}), EXPIRING)
        self.assertFalse(terms["eligible"], "a declined rookie-scale option makes him unrestricted")


class Options(unittest.TestCase):
    def test_options_are_read_from_the_contract_data_and_old_ones_count_as_exercised(self):
        save = summer_save(contract_protection={"evidence": {"p": {"seasons": [
            {"season": "2026-27", "salary": 10e6, "option_type": "team_option"},
            {"season": "2027-28", "salary": 12e6, "option_type": "player_option"}]}}})
        league = {"contracts": [contract("p", {"2026-27": 10e6, "2027-28": 12e6})]}
        od.apply_contract_options(league, save)
        rows = league["contracts"][0]["seasons"]
        self.assertEqual([r["option_type"] for r in rows], ["team_option", "player_option"])
        self.assertTrue(rows[0].get("option_exercised"), "2026-27 options were decided in real life")
        self.assertFalse(rows[1].get("option_exercised"))

    def test_a_decision_is_written_onto_the_contract(self):
        save = summer_save(offseason_decisions={"options": {
            "2027-28:p": {"player_id": "p", "season": "2027-28", "salary": 12e6, "status": "declined", "kind": "player_option"},
            "2027-28:q": {"player_id": "q", "season": "2027-28", "salary": 8e6, "status": "exercised", "kind": "team_option"},
        }, "qualifying_offers": {}})
        league = {"contracts": [contract("p", {"2026-27": 10e6, "2027-28": 12e6}, {"2027-28": "player_option"}),
                                contract("q", {"2026-27": 7e6, "2027-28": 8e6}, {"2027-28": "team_option"})]}
        od.apply_contract_options(league, save)
        self.assertEqual([r["season"] for r in league["contracts"][0]["seasons"]], ["2026-27"], "declined: he is expiring")
        self.assertTrue(league["contracts"][1]["seasons"][1]["option_exercised"])
        self.assertEqual(league["contracts"][1]["seasons"][1]["guaranteed_salary"], 8e6)

    def test_a_new_contract_is_not_touched_by_an_old_decision(self):
        save = summer_save(offseason_decisions={"options": {
            "2027-28:p": {"player_id": "p", "season": "2027-28", "salary": 12e6, "status": "declined", "kind": "player_option"}},
            "qualifying_offers": {}})
        league = {"contracts": [contract("p", {"2027-28": 20e6, "2028-29": 21e6})]}   # he opted out and re-signed
        od.apply_contract_options(league, save)
        self.assertEqual(len(league["contracts"][0]["seasons"]), 2)

    def test_rookie_scale_options_are_told_apart_from_veteran_ones(self):
        flagg = player("flagg", draft_year=2025, pick=1)
        self.assertEqual(od.option_kind(flagg, {"season": "2027-28", "option_type": "team_option"}), "rookie_option")
        vet = player("vet", draft_year=2018)
        self.assertEqual(od.option_kind(vet, {"season": "2027-28", "option_type": "team_option"}), "team_option")
        self.assertEqual(od.option_deadline("rookie_option", "2027-28"), "2026-11-02")
        self.assertEqual(od.option_deadline("team_option", "2027-28"), "2027-06-29")

    def test_player_option_rule(self):
        save = summer_save()
        young = player("young", draft_year=2020, age=26)
        row = {"season": NEXT, "salary": 10e6}
        self.assertEqual(od.decide_player_option(save, young, row, 14e6, "non")[0], "declined", "market clearly beats it")
        self.assertEqual(od.decide_player_option(save, young, row, 9e6, "non")[0], "exercised")
        veteran = player("veteran", draft_year=2014, age=33, minutes=28)
        # Near the option at 33: four guaranteed years and full Bird rights make opting out worth it (Irving, Harden).
        self.assertEqual(od.decide_player_option(save, veteran, {"season": NEXT, "salary": 30e6}, 28e6, "full")[0], "declined")
        self.assertEqual(od.decide_player_option(save, veteran, {"season": NEXT, "salary": 50e6}, 30e6, "full")[0], "exercised")
        hurt = summer_save(health_states=[{"player_id": "young", "availability_status": "out", "return_date": "2027-12-01"}])
        status, reason = od.decide_player_option(hurt, young, row, 20e6, "non")
        self.assertEqual(status, "exercised")
        self.assertIn("injured", reason)

    def test_team_option_rules(self):
        save = summer_save()
        p = player("p", draft_year=2018, age=29, minutes=18)
        with patch("nba_gm_data.payroll_plan.team_phase", return_value="entering"):
            self.assertEqual(od.decide_team_option_ai({}, save, p, {"salary": 10e6}, "team_option", 9e6)[0], "exercised")
            self.assertEqual(od.decide_team_option_ai({}, save, p, {"salary": 10e6}, "team_option", 5e6)[0], "declined")
        bust = player("bust", draft_year=2024, pick=4, age=22, minutes=6)
        self.assertEqual(od.decide_team_option_ai({}, save, bust, {"salary": 9e6}, "rookie_option", 2e6)[0], "declined")
        prospect = player("prospect", draft_year=2025, pick=4, age=20, minutes=6)
        self.assertEqual(od.decide_team_option_ai({}, save, prospect, {"salary": 9e6}, "rookie_option", 2e6)[0],
                         "exercised", "a 20-year-old keeps his option")


class Restricted(unittest.TestCase):
    def restricted_save(self, team: str = "t") -> dict:
        save = summer_save(free_agent_player_ids=["rfa"],
                           re_signing_rights=[{"player_id": "rfa", "team_id": team, "season": EXPIRING,
                                               "status": "exclusive_review_window"}])
        od.store(save)["qualifying_offers"]["2027-28:rfa"] = {
            "player_id": "rfa", "team_id": team, "season": NEXT, "status": "tendered", "amount": 9_000_000,
            "deadline": "2027-06-29"}
        return save

    def test_only_his_team_can_sign_a_restricted_free_agent(self):
        save = self.restricted_save()
        self.assertEqual(od.restricted_rights_team(save, "rfa"), "t")
        self.assertIsNone(od.blocked_for_team(save, "rfa", "t"))
        self.assertIn("restricted free agent", od.blocked_for_team(save, "rfa", "other"))
        league = {"teams": [{"id": "t", "abbrev": "T"}, {"id": "other", "abbrev": "OTH"}], "players": [], "contracts": []}
        check = play.signing_cap_check(league, save, "OTH", 10.0, player={"id": "rfa", "age": 24}, years=3)
        self.assertFalse(check["ok"])
        self.assertEqual(check["reason"], "restricted_free_agent")

    def test_renouncing_or_withdrawing_ends_the_restriction(self):
        save = self.restricted_save()
        save["state"]["current_date"] = "2027-07-10"
        result = od.withdraw_qualifying_offer(save, "rfa")
        self.assertTrue(result["ok"])
        self.assertIsNone(od.restricted_rights_team(save, "rfa"))
        self.assertTrue(any(r["player_id"] == "rfa" for r in save["re_signing_rights"]), "before July 14: rights kept")
        late = self.restricted_save()
        late["state"]["current_date"] = "2027-07-20"
        od.withdraw_qualifying_offer(late, "rfa")
        self.assertFalse(any(r["player_id"] == "rfa" for r in late["re_signing_rights"]), "after July 13: renounced")

    def test_holds_take_the_qualifying_offer_when_larger(self):
        save = self.restricted_save()
        save["state"]["current_date"] = "2027-07-03"
        league = {"teams": [{"id": "t", "abbrev": "T"}],
                  "players": [{"id": "rfa", "name": "Rfa", "team_id": None, "age": 24, "draft_year": 2023, "draft_round": 2}],
                  "contracts": [contract("rfa", {EXPIRING: 2_000_000})]}
        holds = cl.team_holds(league, save, "t", NEXT)
        self.assertEqual(holds[0]["amount"], 9_000_000)
        self.assertTrue(holds[0]["restricted"])

    def test_the_player_waits_or_signs(self):
        save = summer_save()
        young = player("y", draft_year=2023, age=22)
        belief = od.rfa_belief(save, young)
        self.assertGreaterEqual(belief, od.RULES["qualifying_offer"]["belief_young_bonus"])
        self.assertGreater(od.rfa_reservation(save, young, 10e6, 0.0), od.rfa_reservation(save, young, 10e6, 1.0))
        self.assertAlmostEqual(od.rfa_reservation(save, young, 10e6, 1.0), 10e6 * (1 + belief - 0.2))
        # By October 1 everyone takes his team's offer of his market price (the belief is at most 16%).
        self.assertLessEqual(od.rfa_reservation(save, young, 10e6, od.RFA_STAGES["deadline"]), 10e6)
        # In June only the players who believe in themselves least sign at once.
        self.assertGreater(od.rfa_reservation(save, young, 10e6, od.RFA_STAGES["june"]), 10e6)

    def test_ai_tender_rule(self):
        p = player("p", draft_year=2023, minutes=8)
        self.assertTrue(od.ai_tender_choice(p, {"amount": 5e6}, 6e6)[0])
        self.assertFalse(od.ai_tender_choice(p, {"amount": 8e6}, 3e6)[0])
        rotation = player("r", draft_year=2023, minutes=22)
        self.assertTrue(od.ai_tender_choice(rotation, {"amount": 8e6}, 6e6)[0], "a rotation player at a modest premium")


if __name__ == "__main__":
    unittest.main()
