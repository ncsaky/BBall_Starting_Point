"""FA-REAL slice 4: two-way contracts, Exhibit 10 camp deals, the 21-to-15 cutdown and waivers, sign-and-trades, and
roster repair under a hard cap (two_way, camp, sign_and_trade, save.auto_fill_rosters)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from nba_gm_data import camp, cap_ledger as cl, save as sv, sign_and_trade as snt, two_way as tw

SEASON = "2027-28"
EXPIRING = "2026-27"


def roster(team: str, payroll: float, count: int = 14, season: str = SEASON) -> tuple[list, list]:
    players = [{"id": f"{team}_{i}", "name": f"{team} {i}", "team_id": team, "age": 28, "draft_year": 2018,
                "minutes_projection": 30 - i * 2} for i in range(count)]
    contracts = [{"player_id": p["id"], "seasons": [{"season": season, "salary": payroll / count,
                                                     "guaranteed_salary": payroll / count}]} for p in players]
    return players, contracts


def world(*, today: str = "2027-08-01", phase: str = "offseason", payroll: float = 150e6, count: int = 14,
          user_team: str = "human") -> tuple[dict, dict]:
    players, contracts = roster("t", payroll, count)
    young = [{"id": f"fa_{i}", "name": f"Young {i}", "team_id": None, "age": 22 + i % 3, "draft_year": 2025 + (i % 2),
              "minutes_projection": 4} for i in range(6)]
    vet = {"id": "vet", "name": "Old Vet", "team_id": None, "age": 31, "draft_year": 2017, "minutes_projection": 6}
    league = {"teams": [{"id": "t", "abbrev": "T"}, {"id": "u", "abbrev": "U"}],
              "players": players + young + [vet], "contracts": contracts, "draft_picks": []}
    save = {"version": "league_save_v1", "meta": {"season": EXPIRING, "user_team_id": user_team, "seed": 17},
            "state": {"current_date": today, "phase": phase},
            "free_agent_player_ids": [p["id"] for p in young] + ["vet"], "roster_overrides": {},
            "contract_overrides": {}, "season_schedules": {}}
    return league, save


def player(league: dict, pid: str) -> dict:
    return next(p for p in league["players"] if p["id"] == pid)


class TwoWayRules(unittest.TestCase):
    def test_eligibility_service_and_three_seasons_with_a_team(self):
        league, save = world()
        self.assertTrue(tw.eligibility(save, player(league, "fa_0"), "t", SEASON, 2)["ok"])
        self.assertFalse(tw.eligibility(save, player(league, "vet"), "t", SEASON)["ok"], "10 years of service")
        # Three years in the league: one season is fine, a second season would be his fourth.
        three = {"id": "x", "draft_year": 2024}
        self.assertTrue(tw.eligibility(save, three, "t", SEASON, 1)["ok"])
        self.assertFalse(tw.eligibility(save, three, "t", SEASON, 2)["ok"])
        tw.store(save)["history"]["fa_0"] = {"t": ["2024-25", "2025-26", "2026-27"]}
        reason = tw.eligibility(save, player(league, "fa_0"), "t", SEASON)["reason"]
        self.assertIn("three", reason.replace("3", "three"))
        self.assertTrue(tw.eligibility(save, player(league, "fa_0"), "u", SEASON)["ok"], "another team is fine")

    def test_three_places_pay_outside_the_cap_and_off_the_standard_roster(self):
        league, save = world()
        before = cl.team_payroll(league, save, "t", SEASON)
        for i in range(3):
            tw.sign(save, player(league, f"fa_{i}"), "t", when="2027-08-01")
        with self.assertRaisesRegex(ValueError, "three two-way places"):
            tw.sign(save, player(league, "fa_3"), "t", when="2027-08-01")
        after = cl.team_payroll(league, save, "t", SEASON)
        self.assertEqual(before["cap_payroll"], after["cap_payroll"], "two-way pay is outside team salary")
        self.assertEqual(tw.standard_roster_count(league, save, "t"), 14)
        self.assertNotIn("fa_0", save["free_agent_player_ids"])
        rec = tw.contracts(save)["fa_0"]
        self.assertEqual(rec["seasons"][0]["salary"], tw.pay(SEASON))
        self.assertEqual(tw.pay("2026-27"), 678_882, "half the rookie minimum in 2026-27")

    def test_a_later_signing_gets_prorated_pay_and_games(self):
        league, save = world(today="2028-01-20", phase="regular_season")
        save["meta"]["season"] = SEASON
        save["season_schedules"] = {SEASON: {"games": [{"phase": "regular", "gameDate": "2027-10-21"},
                                                       {"phase": "regular", "gameDate": "2028-04-12"}]}}
        rec = tw.sign(save, player(league, "fa_0"), "t", when="2028-01-20")
        self.assertLess(rec["active_limit"][SEASON], 50)
        self.assertGreater(rec["active_limit"][SEASON], 15)
        self.assertLess(rec["seasons"][0]["salary"], tw.pay(SEASON))

    def test_signing_deadline_is_march_4(self):
        league, save = world(today="2028-03-05", phase="regular_season")
        save["meta"]["season"] = SEASON
        self.assertIn("March 4", tw.eligibility(save, player(league, "fa_0"), "t", SEASON, today="2028-03-05")["reason"])

    def test_call_ups_short_bench_rotation_player_and_the_limit(self):
        league, save = world(today="2027-11-01", phase="regular_season", count=12)
        save["meta"]["season"] = SEASON
        for i in range(2):
            tw.sign(save, player(league, f"fa_{i}"), "t", when="2027-10-01")
        recs = tw.contracts(save)
        recs["fa_0"]["rating"], recs["fa_1"]["rating"] = 60.0, 40.0
        tw.store(save)["team_lines"] = {"t": [[f"t_{i}", 70 - i] for i in range(12)]}
        games = [{"homeTeamId": "1", "awayTeamId": "2"}]
        with patch("nba_gm_data.sim.espn_team_id_map", return_value={"1": {"id": "t"}, "2": {"id": "u"}}):
            dressed = tw.dress_for_games(save, league, games, "2027-11-01")
        # 12 healthy standard players: one short of 13, so the better two-way is called up (and he'd be a
        # rotation option anyway); the other stays with the affiliate.
        self.assertEqual([pid for _, pid in dressed], ["fa_0"])
        self.assertEqual(player(league, "fa_0")["team_id"], "t")
        tw.undress(save, league, dressed, "2027-11-01")
        self.assertIsNone(player(league, "fa_0")["team_id"])
        self.assertEqual(tw.active_games(recs["fa_0"], SEASON), 1)
        recs["fa_0"]["active_games"][SEASON] = 50
        with patch("nba_gm_data.sim.espn_team_id_map", return_value={"1": {"id": "t"}, "2": {"id": "u"}}):
            dressed = tw.dress_for_games(save, league, games, "2027-11-02")
        self.assertEqual([pid for _, pid in dressed], ["fa_1"], "at his limit he stays down; the next one comes up")

    def test_conversion_needs_a_spot_and_fits_the_hard_cap(self):
        league, save = world(today="2027-11-01", phase="regular_season", count=15)
        save["meta"]["season"] = SEASON
        tw.sign(save, player(league, "fa_0"), "t", when="2027-10-01")
        self.assertIn("No standard roster spot", tw.conversion_quote(league, save, "fa_0", when="2027-11-01")["reason"])
        league["players"] = [p for p in league["players"] if p["id"] != "t_14"]
        quote = tw.conversion_quote(league, save, "fa_0", when="2027-11-01")
        self.assertTrue(quote["ok"], quote)
        cl.trigger_hard_cap(save, "t", SEASON, "first_apron", "test")
        apron = cl.team_payroll(league, save, "t", SEASON)["apron_payroll"]
        cl.team_year(save, "t", SEASON)["hard_cap"]["amount"] = apron + 100_000
        self.assertIn("hard cap", tw.conversion_quote(league, save, "fa_0", when="2027-11-01")["reason"])
        cl.team_year(save, "t", SEASON)["hard_cap"] = None
        tw.convert(league, save, "fa_0", when="2027-11-01", by="user")
        self.assertEqual(save["roster_overrides"]["fa_0"], "t")
        self.assertTrue(save["contract_overrides"]["fa_0"]["converted_from_two_way"])
        self.assertFalse(tw.is_two_way(save, "fa_0"))

    def test_two_way_qualifying_offer(self):
        league, save = world(today="2028-06-17", phase="re_signing")
        save["meta"]["season"] = SEASON
        tw.store(save)["contracts"]["fa_0"] = {"player_id": "fa_0", "name": "Young 0", "team_id": "t",
                                                "seasons": [{"season": SEASON, "salary": 1}], "active_games": {}}
        tw.store(save)["history"]["fa_0"] = {"t": [SEASON]}
        save["free_agent_player_ids"].remove("fa_0")
        tw.expire_contracts(save, "2028-29", "2028-06-17")
        self.assertNotIn("fa_0", save["free_agent_player_ids"], "his team holds his rights until it decides")
        row = tw.store(save)["qualifying_offers"]["fa_0"]
        self.assertEqual(row["status"], "pending")
        save["meta"]["user_team_id"] = "t"
        tw.user_qualifying_offer(save, league, "fa_0", False, "2028-06-19")
        self.assertIn("fa_0", save["free_agent_player_ids"])
        tw.user_qualifying_offer(save, league, "fa_0", True, "2028-06-20")
        self.assertNotIn("fa_0", save["free_agent_player_ids"])
        self.assertIn("fa_0", tw.restricted_two_way_ids(save))
        save["state"]["current_date"] = "2028-07-01"
        tw.resolve_qualifying_offers(league, save, "2028-07-01")
        self.assertEqual(tw.two_way_team(save, "fa_0"), "t")
        self.assertEqual(tw.contracts(save)["fa_0"]["how"], "qualifying_offer")


class CampDeals(unittest.TestCase):
    def test_invite_six_at_once_within_twenty_one(self):
        league, save = world(count=14)
        with patch.object(camp, "opening_night", return_value="2027-10-21"):
            row = camp.invite(league, save, player(league, "fa_0"), "t", when="2027-08-01")
            override = save["contract_overrides"]["fa_0"]
            self.assertTrue(override["exhibit_10"])
            self.assertEqual(override["seasons"][0]["guaranteed_salary"], 0, "not guaranteed")
            self.assertEqual(override["seasons"][0]["guarantee_date"], "2028-01-10")
            self.assertGreater(row["bonus"], 90_000)
            for pid in ("fa_1", "fa_2", "fa_3", "fa_4", "fa_5"):
                camp.invite(league, save, player(league, pid), "t", when="2027-08-01")
            quote = camp.invite_quote(league, save, player(league, "vet"), "t", "2027-08-01")
            self.assertIn("6 camp deals", quote["reason"])
            self.assertEqual(tw.standard_room(league, save, "t", "2027-08-01")["open"], 1)

    def test_camp_deal_converts_to_two_way_before_opening(self):
        league, save = world(count=14)
        with patch.object(camp, "opening_night", return_value="2027-10-21"):
            camp.invite(league, save, player(league, "fa_0"), "t", when="2027-08-01")
            camp.convert_to_two_way(league, save, "fa_0", when="2027-10-01")
            self.assertEqual(tw.two_way_team(save, "fa_0"), "t")
            self.assertNotIn("fa_0", save["contract_overrides"])
            self.assertIsNone(save["roster_overrides"]["fa_0"])
            camp.invite(league, save, player(league, "fa_1"), "t", when="2027-08-01")
            with self.assertRaisesRegex(ValueError, "before opening day"):
                camp.convert_to_two_way(league, save, "fa_1", when="2027-10-21")

    def test_waived_camp_deal_clears_and_joins_the_affiliate_with_a_bonus(self):
        league, save = world(count=14)
        save["season_schedules"] = {SEASON: {"games": [{"phase": "regular", "gameDate": "2027-10-21"},
                                                       {"phase": "regular", "gameDate": "2028-04-12"}]}}
        with patch.object(camp, "opening_night", return_value="2027-10-21"):
            camp.invite(league, save, player(league, "fa_0"), "t", when="2027-08-01")
        active = {**league, "players": [dict(p, team_id="t") if p["id"] == "fa_0" else p for p in league["players"]]}
        entry = camp.waive(active, save, "fa_0", "t", "2027-10-17", reason="camp cut")
        self.assertEqual(entry["clearance_date"], "2027-10-19")
        owed = sum(float(r["salary"] or 0) for r in entry["seasons"])
        self.assertEqual(owed, 0.0, "waived before opening night and not guaranteed: nothing owed")
        entry["status"] = "cleared"
        entry["resolved_date"] = "2027-10-19"
        self.assertEqual(camp.record_affiliate_bonuses(save, "2027-10-19"), 1)
        self.assertEqual(camp.store(save)["bonuses"][0]["bonus"], camp.affiliate_bonus(SEASON))

    def test_guarantee_words(self):
        rows = [{"season": SEASON, "salary": 5e6, "guaranteed_salary": 5e6}]
        self.assertEqual(camp.guarantee_words(rows, SEASON)["kind"], "full")
        rows = [{"season": SEASON, "salary": 5e6, "guaranteed_salary": 0, "guarantee_date": "2028-01-10"}]
        self.assertIn("until 2028-01-10", camp.guarantee_words(rows, SEASON)["words"])
        rows = [{"season": SEASON, "salary": 5e6, "guaranteed_salary": 1e6}]
        self.assertEqual(camp.guarantee_words(rows, SEASON)["kind"], "partial")


class SignAndTrade(unittest.TestCase):
    def world(self, *, sender_payroll=170e6, receiver_payroll=180e6, previous=8e6, receiver_count=14):
        s_players, s_contracts = roster("s", sender_payroll, 13)
        r_players, r_contracts = roster("r", receiver_payroll, receiver_count)
        fa = {"id": "fa", "name": "Wing", "team_id": None, "age": 27, "draft_year": 2019, "minutes_projection": 28}
        league = {"teams": [{"id": "s", "abbrev": "S"}, {"id": "r", "abbrev": "R"}],
                  "players": s_players + r_players + [fa],
                  "contracts": s_contracts + r_contracts + [{"player_id": "fa", "seasons": [{"season": EXPIRING, "salary": previous}]}],
                  "draft_picks": []}
        save = {"version": "league_save_v1", "meta": {"season": EXPIRING, "user_team_id": "human", "seed": 17},
                "state": {"current_date": "2027-07-03", "phase": "free_agency"},
                "free_agent_player_ids": ["fa"], "roster_overrides": {}, "contract_overrides": {},
                "re_signing_rights": [{"player_id": "fa", "team_id": "s", "season": EXPIRING}],
                "bird_clocks": {"fa": {"team_id": "s", "since": "2023-24"}}}
        return league, save

    def test_rules_years_matching_apron_and_hard_cap(self):
        league, save = self.world()
        fa = player(league, "fa")
        self.assertIn("3 or 4 seasons", " ".join(snt.quote(league, save, fa, "s", "r", 15e6, 2)["problems"]))
        no_match = snt.quote(league, save, fa, "s", "r", 15e6, 3)
        self.assertFalse(no_match["ok"])
        self.assertTrue(any("send back salary" in p for p in no_match["problems"]))
        terms = snt.quote(league, save, fa, "s", "r", 15e6, 3, outgoing_ids=["r_13"])
        self.assertTrue(terms["ok"], terms["problems"])
        self.assertEqual([r["salary"] for r in terms["schedule"]], [15_000_000, 15_750_000, 16_500_000])
        self.assertTrue(terms["base_year"], "a raise over 20% with Bird rights over the cap")
        self.assertEqual(terms["outgoing_salary"], max(8e6, 7.5e6))
        record = snt.execute(league, save, terms, when="2027-07-03")
        self.assertEqual(save["roster_overrides"]["fa"], "r")
        self.assertEqual(save["roster_overrides"]["r_13"], "s")
        self.assertEqual(cl.hard_cap(save, "r", SEASON)["level"], "first_apron")
        self.assertEqual(save["contract_overrides"]["fa"]["seasons"][0]["guaranteed_salary"], 15_000_000)
        self.assertNotIn("fa", save["free_agent_player_ids"])
        self.assertTrue(record["base_year"])

    def test_a_team_over_the_first_apron_cannot_receive_one(self):
        league, save = self.world(receiver_payroll=220e6)
        terms = snt.quote(league, save, player(league, "fa"), "s", "r", 10e6, 3, outgoing_ids=["r_13"])
        self.assertTrue(any("over the first apron" in p for p in terms["problems"]))

    def test_matching_limits(self):
        small = cl.scaled(snt.MATCH_SMALL_2026, "2026-27")
        self.assertEqual(snt.matching_limit(5e6, "2026-27"), 5e6 * 2 + cl.scaled(snt.MATCH_PLUS_2026, "2026-27"))
        self.assertEqual(snt.matching_limit(20e6, "2026-27"), 20e6 + small)
        self.assertEqual(snt.matching_limit(40e6, "2026-27"), 40e6 * 1.25 + cl.scaled(snt.MATCH_PLUS_2026, "2026-27"))

    def test_no_rights_no_sign_and_trade(self):
        league, save = self.world()
        save["re_signing_rights"] = []
        terms = snt.quote(league, save, player(league, "fa"), "s", "r", 10e6, 3, outgoing_ids=["r_13"])
        self.assertTrue(any("doesn't hold his rights" in p for p in terms["problems"]))


class RosterRepair(unittest.TestCase):
    def test_no_signing_past_a_hard_cap_or_onto_the_users_roster(self):
        league, save = world(count=12, today="2027-10-05", phase="preseason", payroll=200e6)
        league["teams"] = [{"id": "t", "abbrev": "T"}, {"id": "human", "abbrev": "HUM"}]
        save["meta"]["season"] = SEASON
        cl.trigger_hard_cap(save, "t", SEASON, "first_apron", "test")
        cl.team_year(save, "t", SEASON)["hard_cap"]["amount"] = 200e6 + 1_000_000
        with patch.object(sv, "canonical_with_save", return_value=league), \
                patch.object(sv, "reacquisition_blocked", return_value=False, create=True):
            signed = sv.auto_fill_rosters(league, save, list(save["free_agent_player_ids"]), SEASON, 17)
        self.assertEqual(signed, set(), "a minimum contract would pass the hard cap; the human team is never filled")
        self.assertTrue(save["hard_capped_short_rosters"])
        self.assertFalse(any(tid == "human" for tid in save["roster_overrides"].values()))

    def test_user_roster_minimum_gate(self):
        save = {"meta": {"user_team_id": "u"}, "state": {"phase": "regular_season", "current_date": "2027-11-01"}}
        sv.update_user_roster_minimum(save, 13, "2027-11-01")
        self.assertFalse(save["pending_roster_minimum"]["blocking"], "13 players is allowed for two weeks")
        sv.update_user_roster_minimum(save, 13, "2027-11-16")
        self.assertTrue(save["pending_roster_minimum"]["blocking"])
        sv.update_user_roster_minimum(save, 12, "2027-11-01")
        self.assertTrue(save["pending_roster_minimum"]["blocking"])
        sv.update_user_roster_minimum(save, 14, "2027-11-01")
        self.assertNotIn("pending_roster_minimum", save)


if __name__ == "__main__":
    unittest.main()
