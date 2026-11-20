"""KEEP-STARS: Bird rights, franchise stars kept, the incumbent's fifth year, and the six-month re-trade hold."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from nba_gm_data import cap_rules, contract_ai as ca, payroll_plan as pp, play, save as sv
from nba_gm_data import transactions as tx

from test_trade_volume import SEASON, league, save_for


def bird(level: str, limit: float, seasons: int = 3) -> dict:
    return {"level": level, "seasons": seasons, "limit": limit, "max_years": cap_rules.bird_max_years(level),
            "raise": cap_rules.bird_raise(level), "previous_salary": 10e6, "since": "2025-26"}


class BirdRuleTests(unittest.TestCase):
    def test_levels_limits_years_and_raises_follow_the_cba(self):
        self.assertEqual(cap_rules.bird_level(3), "full")
        self.assertEqual(cap_rules.bird_level(2), "early")
        self.assertEqual(cap_rules.bird_level(1), "non")
        season, service = "2028-29", 9
        self.assertEqual(cap_rules.bird_salary_limit("full", 5e6, season, service), cap_rules.max_salary(season, service))
        self.assertAlmostEqual(cap_rules.bird_salary_limit("early", 20e6, season, service), 35e6)   # 175%
        self.assertAlmostEqual(cap_rules.bird_salary_limit("non", 20e6, season, service), 24e6)     # 120%
        self.assertLessEqual(cap_rules.bird_salary_limit("early", 40e6, season, service), cap_rules.max_salary(season, service))
        self.assertEqual((cap_rules.bird_max_years("full"), cap_rules.bird_max_years("early"),
                          cap_rules.bird_max_years(None)), (5, 4, 4))
        self.assertEqual((cap_rules.bird_raise("full"), cap_rules.bird_raise("non"), cap_rules.bird_raise(None)),
                         (0.08, 0.05, 0.05))

    def test_the_clock_starts_with_a_new_team_and_survives_re_signings(self):
        player = {"id": "p", "name": "Nobody Real"}
        save = {"contract_overrides": {"p": {"team_id": "a", "signed_season": "2026-27"}}}
        rights = ca.bird_rights(save, player, "a", "2027-28", {"seasons": [{"season": "2027-28", "salary": 8e6}]})
        self.assertEqual((rights["level"], rights["seasons"], rights["previous_salary"]), ("early", 2, 8e6))
        # Re-signed with the same team for one year: the clock keeps running, so a season later he has full Bird rights.
        ca.keep_bird_clock(save, player, "a", "2028-29")
        save["contract_overrides"]["p"] = {"team_id": "a", "signed_season": "2028-29"}
        self.assertEqual(ca.bird_rights(save, player, "a", "2028-29")["level"], "full")
        # Signing somewhere else as a free agent starts it again.
        save["contract_overrides"]["p"] = {"team_id": "b", "signed_season": "2029-30"}
        self.assertEqual(ca.bird_rights(save, player, "b", "2029-30")["level"], "non")

    def test_opening_rosters_use_real_team_history(self):
        jokic = {"id": "player_den-nikola-jokic", "name": "Nikola Jokić", "espn_player_id": "3112335"}
        self.assertLessEqual(ca.opening_bird_since(jokic, "team_den"), "2023-24")
        self.assertEqual(ca.bird_rights({}, jokic, "team_den", "2027-28")["level"], "full")


class BirdReSigningTests(unittest.TestCase):
    def test_ai_team_re_signs_its_own_player_over_the_hard_cap_within_his_bird_rights(self):
        saved = {"meta": {"human_team_ids": []}, "player_season_stats": {}}
        star = {"id": "s", "team_id": "den", "age": 33, "minutes_projection": 34, "_star_ask_millions": 61.8}
        broke = {"hard_cap_space_millions": -20.0}
        with patch.object(sv, "team_cap_summary", return_value=broke):
            self.assertTrue(sv.ai_re_signing_fits_hard_cap({}, saved, {**star, "_bird": bird("full", 62e6)}, "den",
                                                           "2028-29", prepared_active={}))
            self.assertFalse(sv.ai_re_signing_fits_hard_cap({}, saved, {**star, "_bird": bird("non", 30e6, 1)}, "den",
                                                            "2028-29", prepared_active={}),
                             "above his Bird limit the team needs real room")
            self.assertFalse(sv.ai_re_signing_fits_hard_cap({}, saved, star, "den", "2028-29", prepared_active={}))

    def test_signing_check_lets_the_incumbent_go_over_the_tax_and_hard_cap(self):
        broke = {"hard_cap_space_millions": -5.0, "tax_space_millions": -20.0}
        with patch.object(play, "team_cap_summary", return_value=broke), \
             patch.object(play, "resolve_team", return_value={"id": "a", "abbrev": "A"}):
            saved = {"meta": {"season": SEASON}, "state": {"phase": "free_agency"}}
            self.assertFalse(play.signing_cap_check({}, saved, "A", 30.0)["ok"])
            self.assertTrue(play.signing_cap_check({}, saved, "A", 30.0, bird=bird("full", 40e6))["ok"])
            self.assertFalse(play.signing_cap_check({}, saved, "A", 30.0, bird=bird("non", 12e6, 1))["ok"])

    def test_incumbent_rights_come_from_this_offseasons_re_signing_rights(self):
        saved = {"meta": {"season": "2027-28"}, "contract_overrides": {"p": {"team_id": "a", "signed_season": "2024-25"}},
                 "re_signing_rights": [{"player_id": "p", "team_id": "a", "season": "2027-28",
                                        "status": "entered_open_market"}]}
        player = {"id": "p", "name": "Nobody Real"}
        self.assertEqual(play.incumbent_bird_rights({"contracts": []}, saved, player, "a")["level"], "full")
        self.assertIsNone(play.incumbent_bird_rights({"contracts": []}, saved, player, "b"))


class FranchiseStarTests(unittest.TestCase):
    def test_retooling_team_keeps_its_franchise_star_through_its_payroll_room(self):
        # The Denver case: re-signing him leaves the team just under the tax line, inside the room a retooling team
        # keeps below it. A franchise star is kept anyway.
        data = league(payroll_a=150_000_000)
        saved = save_for("2027-06-28", "exiting")
        line = cap_rules.cap_lines_for_season(SEASON)["tax_line"]
        add = line - 150_000_000 - 1_000_000
        plain = pp.payroll_check(data, saved, "a", SEASON, add_salary=add, minutes=34, kind="re_signing", age=33)
        self.assertEqual(plain["reason"], "keeps_room_below_the_line_for_its_phase")
        star = pp.payroll_check(data, saved, "a", SEASON, add_salary=add, minutes=34, kind="re_signing", age=33,
                                franchise_star=True)
        self.assertTrue(star["ok"])
        # It pays real tax for him ($45M here), within the owner's star budget (about $100M), but not any bill at all.
        taxed = pp.payroll_check(league(payroll_a=195_000_000), saved, "a", SEASON, add_salary=25e6, minutes=34,
                                 kind="re_signing", age=33, franchise_star=True)
        self.assertGreater(taxed["cost"], 40e6)
        self.assertTrue(taxed["ok"])
        self.assertFalse(pp.payroll_check(league(payroll_a=195_000_000), saved, "a", SEASON, add_salary=25e6,
                                          minutes=34, kind="re_signing", age=33)["ok"])
        ruinous = pp.payroll_check(league(payroll_a=195_000_000), saved, "a", SEASON, add_salary=45e6, minutes=34,
                                   kind="re_signing", age=33, franchise_star=True)
        self.assertEqual(ruinous["reason"], "tax_cost_above_owner_budget")

    def test_franchise_star_is_kept_at_any_age_unless_the_team_is_rebuilding_and_he_is_31_plus(self):
        saved = {"meta": {"human_team_ids": ["h"]}, "team_records": {}, "player_season_stats": {}}
        star = {"id": "s", "team_id": "den", "age": 34, "minutes_projection": 34, "_star_ask_millions": 50.0,
                "_star_rank": 4, "_team_phase": "exiting"}
        self.assertTrue(sv.should_ai_retain_expiring_player(saved, star, "2027-28", 17))
        self.assertFalse(sv.should_ai_retain_expiring_player(saved, {**star, "_team_phase": "rebuilding"}, "2027-28", 17))
        self.assertTrue(sv.should_ai_retain_expiring_player(saved, {**star, "age": 26, "_team_phase": "rebuilding"},
                                                            "2027-28", 17))
        self.assertFalse(sv.should_ai_retain_expiring_player(saved, {**star, "team_id": "h"}, "2027-28", 17))

    def test_a_young_regular_off_his_rookie_deal_is_kept_at_his_market_price(self):
        # Brandon Miller (24) left Charlotte in the 2027 test: no star-tier price, so a dice roll decided. Real teams
        # match offers for such restricted free agents.
        young = {"id": "m", "team_id": "cha", "age": 24, "minutes_projection": 31, "_restricted": True,
                 "_market_ask_millions": 28.8, "_bird": bird("full", 40e6, seasons=4), "_team_phase": "entering"}
        self.assertTrue(sv.is_franchise_star(young))
        self.assertFalse(sv.is_franchise_star({**young, "_restricted": False}))
        saved = {"meta": {"human_team_ids": []}, "team_records": {}, "player_season_stats": {}}
        self.assertTrue(sv.should_ai_retain_expiring_player(saved, young, "2026-27", 17))
        terms = sv.ai_re_signing_contract_terms(saved, young, "2027-28")
        self.assertEqual((terms["salary"], terms["years"]), (28_800_000, 5))
        order = sv.re_signing_order([{"id": "bench"}, young, {"id": "s", "_star_ask_millions": 40.0}])
        self.assertEqual([p["id"] for p in order], ["s", "m", "bench"])


class IncumbentYearsTests(unittest.TestCase):
    def test_full_bird_gives_a_young_star_a_fifth_year_and_8_percent_raises(self):
        saved = {"player_season_stats": {}}
        star = {"id": "s", "team_id": "a", "age": 25, "minutes_projection": 34, "_star_ask_millions": 33.0,
                "_bird": bird("full", 50e6)}
        terms = sv.ai_re_signing_contract_terms(saved, star, "2028-29")
        self.assertEqual(terms["years"], 5)
        self.assertEqual(terms["seasons"][1]["salary"], round(33e6 * 1.08))
        non = sv.ai_re_signing_contract_terms(saved, {**star, "_bird": bird("non", 50e6, 1)}, "2028-29")
        self.assertEqual(non["years"], 4)
        self.assertEqual(non["seasons"][1]["salary"], round(33e6 * 1.05))
        older = sv.ai_re_signing_contract_terms(saved, {**star, "age": 33}, "2028-29")
        self.assertEqual(older["years"], 3)

    def test_the_offer_screen_mirrors_the_years_rule(self):
        import pathlib
        text = pathlib.Path(play.__file__).with_name("gui").joinpath("app.js").read_text()
        self.assertIn("function freeAgencyMaxYears(", text)
        self.assertIn("bird_rights", text)


class ReTradeHoldTests(unittest.TestCase):
    def canonical(self, days_ago: int, human=()):
        from datetime import date, timedelta
        today = date(2028, 1, 20)
        traded = (today - timedelta(days=days_ago)).isoformat()
        return {
            "meta": {"current_date": today.isoformat()}, "_human_team_ids": list(human),
            "players": [{"id": "p1", "team_id": "x"}, {"id": "p2", "team_id": "x"}, {"id": "q1", "team_id": "y"}],
            "contracts": [{"player_id": pid, "seasons": [{"season": "2027-28", "salary": sal}]}
                          for pid, sal in (("p1", 20e6), ("p2", 5e6), ("q1", 15e6))],
            "transaction_logs": [{"transaction_type": "trade", "status": "applied_to_save_ledger", "date": traded,
                                  "teams": ["z", "x"], "assets": {"from_team_id": "z", "to_team_id": "x",
                                  "from_assets": [{"kind": "player", "id": "p1"}], "to_assets": []}}],
        }

    def proposal(self, sends, gets):
        return {"from_team_id": "x", "to_team_id": "y", "from_assets": [{"kind": "player", "id": i} for i in sends],
                "to_assets": [{"kind": "player", "id": i} for i in gets]}

    def test_a_newly_acquired_player_is_not_moved_in_a_salary_dump(self):
        with patch.object(tx, "contract_active_season", return_value="2027-28"):
            canonical = self.canonical(100)
            self.assertEqual(tx.re_trade_hold(canonical), {"p1": "x"})
            self.assertTrue(tx.re_trade_hold_issues(canonical, self.proposal(["p1"], [])), "a dump")
            self.assertTrue(tx.re_trade_hold_issues(canonical, self.proposal(["p2", "p1"], [])))
            # The centre of a salary-matching deal may move.
            self.assertEqual(tx.re_trade_hold_issues(canonical, self.proposal(["p1"], ["q1"])), [])
            # After six months, or with the user's team in the deal, the hold does not apply.
            self.assertEqual(tx.re_trade_hold_issues(self.canonical(200), self.proposal(["p1"], [])), [])
            self.assertEqual(tx.re_trade_hold_issues(self.canonical(100, human=("y",)), self.proposal(["p1"], [])), [])


if __name__ == "__main__":
    unittest.main()
