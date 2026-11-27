"""AI-TRADES-SENSE: champions keep their core, firsts buy real players, picks don't bounce, long injuries lower the
price, useful players aren't given away, and hard-capped AI teams keep room to fill a roster
(docs/agents/tasks/ai-trades-sense.md)."""
import unittest

from nba_gm_data import team_planning as tp
from nba_gm_data import trade_injury as ti
from nba_gm_data import trade_roster as tr
from nba_gm_data import trade_tax as tax
from nba_gm_data import transactions as tx

from test_trade_step4 import P, SEASON, league, set_contract


def taxed(data):
    """A over the tax line: a0 on $60M."""
    set_contract(data, "a0", [(SEASON, 60_000_000)])
    return data


class ContenderCoreTests(unittest.TestCase):
    def test_contender_gets_no_tax_credit_for_a_top_three_player(self):
        data = taxed(league())
        self.assertGreater(tax.tax_value(data, "a", [], [P("a0")]), 0)  # rebuilding: tax savings count
        for state in data["team_strategic_states"]:
            if state["team_id"] == "a":
                state["window_phase"] = "peak"
        self.assertEqual(tax.tax_value(data, "a", [], [P("a0")]), 0.0)
        # A bench contract still saves tax for the contender.
        bench = tax._depth_chart(data, "a")[-1][1]
        self.assertGreater(tax.tax_value(data, "a", [], [P(bench)]), 0)

    def test_champion_counts_as_contender_while_its_core_stays(self):
        data = taxed(league())
        data["meta"]["current_date"] = "2027-07-01"
        data["team_plans"] = {"a": {"postseason_outcomes": [
            {"year": "2027", "rounds_won": 4, "core_ids": ["a0", "a1", "a2"]}]}}
        self.assertEqual(tp.latest_postseason_rounds(data, "a"), 4)
        self.assertEqual(tax.tax_value(data, "a", [], [P("a0")]), 0.0)
        # Last year's title no longer counts once a new postseason has passed.
        data["meta"]["current_date"] = "2028-07-01"
        self.assertEqual(tp.latest_postseason_rounds(data, "a"), 0)
        # Nor once most of that core has left.
        data["meta"]["current_date"] = "2027-07-01"
        for player in data["players"]:
            if player["id"] in {"a1", "a2"}:
                player["team_id"] = "b"
        self.assertEqual(tp.latest_postseason_rounds(data, "a"), 0)


class FirstRoundPurposeTests(unittest.TestCase):
    FIRST = {"kind": "pick", "id": "x", "round": 1}
    SECOND = {"kind": "pick", "id": "y", "round": 2}

    def purpose(self, **kw):
        args = dict(incoming=[P("p")], draft_in=[], draft_out=[self.FIRST], incoming_minutes=9.0, growth=2.0,
                    tax_saving=0.0, relief=0.0)
        args.update(kw)
        return tr.first_round_pick_purpose({}, "a", **args)

    def test_a_first_for_bench_depth_has_no_purpose(self):
        self.assertFalse(self.purpose())
        self.assertTrue(tr.pick_investment_overspent({"first_round_purpose": False}))

    def test_rotation_role_upside_or_money_justify_it(self):
        from unittest.mock import patch
        with patch.object(tx, "trade_value_role_minutes", return_value=24.0):
            self.assertTrue(self.purpose(incoming_minutes=22.0))
        with patch.object(tx, "trade_value_role_minutes", return_value=12.0):
            self.assertFalse(self.purpose(incoming_minutes=22.0))  # a 12-minute player now: the projection is hope
        self.assertTrue(self.purpose(growth=9.0))
        self.assertTrue(self.purpose(tax_saving=15.0))
        self.assertTrue(self.purpose(relief=10.0))

    def test_seconds_and_pick_swaps_for_picks_are_untouched(self):
        self.assertTrue(self.purpose(draft_out=[self.SECOND]))
        self.assertTrue(self.purpose(draft_in=[dict(self.FIRST, id="z")]))
        self.assertTrue(self.purpose(incoming=[]))


class PickHoldTests(unittest.TestCase):
    def log(self, day, frm, to, asset):
        return {"transaction_type": "trade", "status": "applied_to_save_ledger", "date": day, "teams": [frm, to],
                "assets": {"from_team_id": frm, "to_team_id": to, "from_assets": [asset], "to_assets": []}}

    def test_a_pick_just_acquired_cannot_be_flipped_between_ai_teams(self):
        data = league()
        pick = {"kind": "pick", "id": "b2028r1", "label": "B 2028 first"}
        data["transaction_logs"] = [self.log("2027-01-07", "b", "a", pick)]
        self.assertEqual(tx.re_trade_hold_picks(data, "2027-01-31"), {"b2028r1": "a"})
        proposal = {"from_team_id": "a", "to_team_id": "c", "from_assets": [pick], "to_assets": [P("c1")],
                    "date": "2027-01-31"}
        self.assertTrue(any("acquired by trade" in i for i in tx.re_trade_hold_issues(data, proposal)))
        self.assertEqual(tx.re_trade_hold_picks(data, "2027-04-20"), {})  # 90 days later it may move
        data["_human_team_ids"] = ["c"]
        self.assertEqual(tx.re_trade_hold_issues(data, proposal), [])  # the user's trades keep the real rules


class InjuryTests(unittest.TestCase):
    def data(self, return_date, phase="peak"):
        return {"meta": {"current_date": "2027-01-30"},
                "player_health_states": [{"player_id": "kp", "availability_status": "out", "return_date": return_date}],
                "team_strategic_states": [{"team_id": "s", "window_phase": phase}]}

    def test_out_for_the_season_costs_a_contender_most_of_this_seasons_share(self):
        this, following = ti.missed_shares(self.data("2027-06-30"), "kp")
        self.assertEqual((this, following), (1.0, 0.0))
        self.assertAlmostEqual(ti.injury_discount(self.data("2027-06-30"), "kp", "s"), ti.PRESENT_SHARE["peak"])
        self.assertAlmostEqual(ti.injury_discount(self.data("2027-06-30", "rebuilding"), "kp", "s"),
                               ti.PRESENT_SHARE["rebuilding"])

    def test_short_absences_and_the_human_team_are_untouched(self):
        self.assertEqual(ti.injury_discount(self.data("2027-02-10"), "kp", "s"), 0.0)
        human = dict(self.data("2027-06-30"), _human_team_ids=["s"])
        self.assertEqual(ti.injury_discount(human, "kp", "s"), 0.0)

    def test_missing_next_season_adds_to_the_discount(self):
        value = ti.injury_discount(self.data("2028-02-15"), "kp", "s")
        self.assertGreater(value, ti.PRESENT_SHARE["peak"])
        self.assertLessEqual(value, ti.MAX_DISCOUNT)

    def test_buyer_prices_an_injured_target_lower(self):
        data = league()
        healthy = tx.package_value_for_team(data, [P("b0")], "a")
        data = league(player_health_states=[{"player_id": "b0", "availability_status": "out",
                                             "return_date": "2027-06-30"}])
        self.assertLess(tx.package_value_for_team(data, [P("b0")], "a"), healthy * 0.85)
        # The seller's own price for him is unchanged.
        self.assertAlmostEqual(tx.package_value_for_team(data, [P("b0")], "b"),
                               tx.package_value_for_team(league(), [P("b0")], "b"), places=3)


class GiveawayTests(unittest.TestCase):
    def candidate(self, given, taken, back=()):
        return {"proposal": {"from_team_id": "o", "to_team_id": "m", "from_assets": [P("isaac")],
                             "to_assets": list(back)},
                "evaluations": [{"perspective_team_id": "o", "outgoing_value": given},
                                {"perspective_team_id": "m", "incoming_asset_value": taken}]}

    def test_useful_player_for_nothing_is_refused(self):
        self.assertTrue(tx.useful_player_for_nothing(self.candidate(42.0, 31.0)))
        self.assertFalse(tx.ai_trade_candidate_accepted({}, {**self.candidate(42.0, 31.0),
                                                          "legality": {"status": "legal"}, "accepted_by_all": True}))

    def test_minimum_bench_player_or_a_deal_with_a_return_is_fine(self):
        self.assertFalse(tx.useful_player_for_nothing(self.candidate(3.0, 4.0)))
        self.assertFalse(tx.useful_player_for_nothing(self.candidate(42.0, 31.0, back=[{"kind": "pick", "id": "s"}])))


class HardCapTests(unittest.TestCase):
    def test_trade_must_leave_room_to_fill_the_roster(self):
        data = league()
        set_contract(data, "b0", [(SEASON, 29_000_000)])
        current = tx.team_current_salary_total(data, "a")
        # A (13 players) sends two $14.75M players for one $29M player: payroll falls $0.5M, but A then needs two
        # minimum contracts to reach 14 players instead of one.
        proposal = tx.TradeProposal(id="u", from_team_id="a", to_team_id="b", from_assets=[P("a7"), P("a8")],
                                    to_assets=[P("b0")], date="2027-01-31", status="proposed",
                                    source_ids=[], notes="")
        config = tx.default_transaction_model_config()
        data["triggered_hard_caps"] = {"a": current + 5_000_000}
        self.assertIsNone(tx.salary_matching_issue(data, proposal, config))
        data["triggered_hard_caps"] = {"a": current + 1_000_000}
        issue = tx.salary_matching_issue(data, proposal, config)
        self.assertIsNotNone(issue)
        self.assertIn("fill its roster", issue)
        data["_human_team_ids"] = ["a"]
        self.assertIsNone(tx.salary_matching_issue(data, proposal, config))


class HardCapSigningTests(unittest.TestCase):
    def test_ai_team_keeps_room_under_the_hard_cap_for_minimums(self):
        from test_cap_ledger import LINES, league as cap_league, outsider, summer
        from nba_gm_data import cap_ledger as cl
        payroll = LINES["first_apron"] - 9e6 - 2e6    # the mid-level fits with $2M to spare...
        data, save = cap_league(payroll, count=10, extra=[(outsider("a"), None)]), summer()
        quote = cl.quote(data, save, "t", data["players"][-1], 9e6, 3, route="non_taxpayer_mle")
        self.assertFalse(quote["ok"])                  # ... but 10 + 1 players leave three minimums to sign
        self.assertIn("fill a 14-man roster", quote["routes"][-1]["reason"] + str(quote.get("message")))
        human, save = cap_league(payroll, team="human", count=10, extra=[(outsider("a"), None)]), summer()
        self.assertTrue(cl.quote(human, save, "human", human["players"][-1], 9e6, 3, route="non_taxpayer_mle")["ok"])


if __name__ == "__main__":
    unittest.main()
