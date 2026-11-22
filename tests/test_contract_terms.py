"""CONTRACT-TERMS parts 2-3: salary paths, final-season options, how players value them, option decisions."""
from __future__ import annotations

import unittest
from collections import Counter

from nba_gm_data import cap_ledger
from nba_gm_data.contract_ai import offer_contract_seasons, signing_season_for_date
from nba_gm_data.contract_terms import (
    ai_structure, apply_option, factor_table, option_problem, path_rate, value_factor,
)
from nba_gm_data.offseason_decisions import (
    announce_option, decide_player_option, option_decisions_view, record_option, store,
)
from nba_gm_data.play import user_offer_floor
from nba_gm_data.save import offer_to_contract_seasons


class ValueTests(unittest.TestCase):
    def test_players_prefer_more_money_earlier_and_player_options(self):
        rising = value_factor(4, "rising", "none", 0.08)
        flat = value_factor(4, "flat", "none", 0.08)
        declining = value_factor(4, "declining", "none", 0.08)
        self.assertEqual(rising, 1.0)
        self.assertLess(flat, rising)          # same first year, less total money
        self.assertLess(declining, flat)
        self.assertGreater(value_factor(4, "rising", "player", 0.08), rising)
        self.assertLess(value_factor(4, "rising", "team", 0.08), rising)
        # Against the flat extension reference, a rising extension is worth more to him.
        self.assertEqual(value_factor(5, "flat", "none", 0.08, "flat"), 1.0)
        self.assertGreater(value_factor(5, "rising", "none", 0.08, "flat"), 1.0)
        table = factor_table(0.05)
        self.assertEqual(set(table), {"rising", "flat", "declining"})
        self.assertEqual(table["rising"]["none"]["1"], 1.0)

    def test_option_rules(self):
        self.assertIsNotNone(option_problem(1, "player"))
        self.assertIsNotNone(option_problem(2, "team", bird_level="early"))
        self.assertIsNone(option_problem(3, "team", bird_level="early"))
        self.assertIsNotNone(option_problem(3, "player", offer_sheet=True))
        self.assertIsNone(option_problem(2, "none"))

    def test_lower_floor_for_player_friendly_terms(self):
        terms = {"ask_millions": 10.0, "preferred_years": 3, "bar": 60.0, "salary_bounds_millions": None, "best_rival": None}
        player = {"minutes_projection": 24}
        usual = user_offer_floor(player, 3, True, terms, 50.0, 1.0)
        friendly = user_offer_floor(player, 3, True, terms, 50.0, value_factor(3, "rising", "player", 0.05))
        unfriendly = user_offer_floor(player, 3, True, terms, 50.0, value_factor(3, "declining", "team", 0.05))
        self.assertLess(friendly, usual)
        self.assertGreater(unfriendly, usual)


class ContractRowTests(unittest.TestCase):
    def test_option_marks_the_last_season(self):
        rows = apply_option([{"season": "2027-28", "salary": 1}, {"season": "2028-29", "salary": 1, "guaranteed_salary": 1}], "team")
        self.assertEqual(rows[-1]["option_type"], "team_option")
        self.assertIsNone(rows[-1]["guaranteed_salary"])
        self.assertIsNone(rows[0].get("option_type"))

    def test_ledger_and_save_write_the_shape(self):
        payment = {"schedule": [{"season": "2027-28", "salary": 10e6}, {"season": "2028-29", "salary": 9.2e6}],
                   "option": "player", "raise_rate": -0.08}
        rows = cap_ledger.contract_seasons(payment)
        self.assertEqual([r["salary"] for r in rows], [10_000_000, 9_200_000])
        self.assertEqual(rows[-1]["option_type"], "player_option")
        terms = cap_ledger.contract_terms(payment)
        self.assertEqual((terms["salary_path"], terms["option"]), ("declining", "player"))
        offer = {"years": 2, "annual_salary": 10e6, "start_season": "2027-28", "salary_schedule": [10e6, 9.2e6], "option": "team"}
        self.assertEqual(offer_to_contract_seasons(offer)[-1]["option_type"], "team_option")

    def test_extension_rows_follow_the_salary_path(self):
        rows = offer_contract_seasons({"years": 3, "annual_salary": 10e6, "salary_path": "rising", "max_raise": 0.08,
                                       "option": "player"}, "2027-28", "extension")
        self.assertEqual([r["salary"] for r in rows], [10_000_000, 10_800_000, 11_600_000])
        self.assertEqual(rows[-1]["option_type"], "player_option")
        flat = offer_contract_seasons({"years": 2, "annual_salary": 5e6}, "2027-28", "extension")
        self.assertEqual([r["salary"] for r in flat], [5_000_000, 5_000_000])
        self.assertEqual(path_rate("declining", 0.05), -0.05)

    def test_extension_signing_season_is_the_season_of_the_date(self):
        self.assertEqual(signing_season_for_date("2026-10-20"), "2026-27")
        self.assertEqual(signing_season_for_date("2027-03-01"), "2026-27")


class AIShareTests(unittest.TestCase):
    def test_ai_structures_follow_the_real_shares(self):
        big = Counter()
        cheap = Counter()
        for i in range(1500):
            s = ai_structure(40e6, 4, player_id=f"p{i}", team_id="t", season="2027-28")
            big[s["option"]] += 1
            c = ai_structure(2.5e6, 2, player_id=f"p{i}", team_id="t", season="2027-28")
            cheap[c["option"]] += 1
        self.assertEqual(big["team"], 0)                            # real: no team options at $35M+
        self.assertTrue(0.33 < big["player"] / 1500 < 0.49)          # real: 41%
        self.assertTrue(cheap["team"] / 1500 > 0.6)                 # real: 74% under $3M
        self.assertEqual(ai_structure(40e6, 4, player_id="x", team_id="t", season="2027-28"),
                         ai_structure(40e6, 4, player_id="x", team_id="t", season="2027-28"))
        self.assertEqual(ai_structure(40e6, 1, player_id="x", team_id="t", season="s"), {"path": "rising", "option": "none"})


class OptionDecisionTests(unittest.TestCase):
    def save(self):
        return {"meta": {"season": "2026-27", "user_team_id": "team_gsw", "user_team_abbrev": "GSW"},
                "state": {"current_date": "2027-06-17"}, "league_events": [], "news": []}

    def test_reason_names_money_role_and_age(self):
        # CONTRACT-STRUCTURE-EVIDENCE's held-out rule: he opts out after 1,000 or more minutes the season before.
        save = {**self.save(), "state": {"current_date": "2027-06-17", "phase": "re_signing"},
                "player_season_stats": {"p": {"minutes": 700}, "q": {"minutes": 2100}}}
        player = {"id": "p", "name": "Vet", "age": 33, "minutes_projection": 30}
        status, reason = decide_player_option(save, player, {"season": "2027-28", "salary": 20e6}, 12e6, "full")
        self.assertEqual(status, "exercised")
        self.assertIn("33-year-old starter", reason)
        self.assertIn("700 minutes", reason)
        status, reason = decide_player_option(save, {**player, "id": "q", "age": 26}, {"season": "2027-28", "salary": 10e6}, 18e6, "full")
        self.assertEqual(status, "declined")
        self.assertIn("about $18.0M", reason)
        self.assertIn("2,100 minutes", reason)

    def test_ai_shapes_follow_the_evidence_by_kind_of_deal(self):
        from nba_gm_data.contract_terms import deal_kind
        self.assertEqual(deal_kind("bird", 20e6), "bird")
        self.assertEqual(deal_kind("non_taxpayer_mle", 12e6), "exception")
        self.assertEqual(deal_kind("cap_room", 40e6), "max")
        self.assertEqual(deal_kind(None, 40e6, extension=True), "extension_star")
        stars = Counter(ai_structure(45e6, 5, player_id=f"s{i}", team_id="t", season="x", kind="extension_star")["option"]
                        for i in range(1000))
        self.assertEqual(stars["team"], 0)
        self.assertTrue(0.33 < stars["player"] / 1000 < 0.47)        # real: 25 of 62
        bird = Counter(ai_structure(15e6, 3, player_id=f"b{i}", team_id="t", season="x", kind="bird")["path"]
                       for i in range(1000))
        self.assertTrue(0.32 < bird["flat"] / 1000 < 0.44)            # real: 38% flat

    def test_view_and_wire(self):
        save = self.save()
        mine = {"id": "p1", "name": "Mine", "team_id": "team_gsw"}
        other = {"id": "p2", "name": "Star", "team_id": "team_lal"}
        cheap = {"id": "p3", "name": "Cheap", "team_id": "team_lal"}
        r1 = record_option(save, mine, {"season": "2027-28", "salary": 3e6}, "player_option", "team_gsw", "declined", "player", "He becomes a free agent.")
        r2 = record_option(save, other, {"season": "2027-28", "salary": 30e6}, "player_option", "team_lal", "exercised", "player", "He keeps it.")
        r3 = record_option(save, cheap, {"season": "2027-28", "salary": 2e6}, "team_option", "team_lal", "declined", "team", "Cut.")
        for player, record in ((mine, r1), (other, r2), (cheap, r3)):
            announce_option(save, player, record, {"team_gsw"})
        wire = [e for e in save["league_events"] if e["kind"] == "option_decision"]
        self.assertEqual(len(wire), 2)   # yours, and the notable $30M one; not the cheap one
        view = option_decisions_view({}, save, "team_gsw", active={"players": [], "contracts": []})
        self.assertEqual([r["name"] for r in view["yours"]], ["Mine"])
        self.assertEqual(view["league"][0]["name"], "Star")
        self.assertEqual(view["counts"]["player_opted_out"], 1)
        self.assertTrue(store(save)["options"])


if __name__ == "__main__":
    unittest.main()
