"""TRADE-TAXPOOL: the luxury-tax payout to teams under the line, recent draft picks protected from salary dumps,
bounded acceptance for absorber offers to the user's team, and draft-night spreading and chains
(docs/agents/tasks/trade-taxpool.md)."""
import unittest
from unittest.mock import patch

from nba_gm_data import multi_team_trades as mt
from nba_gm_data import play
from nba_gm_data import trade_targets as tt
from nba_gm_data import trade_tax as tax
from nba_gm_data import transactions as tx

from test_trade_step4 import P, SEASON, league, multi_candidate, set_contract

LINE = tx.cap_lines_for_season(SEASON)["tax_line"]


def taxed_league():
    """B is a taxpayer ($216M, about $8.6M over); A sits just over the line ($208.25M with 13 players)."""
    data = league()
    set_contract(data, "b0", [(SEASON, 190_000_000)])
    set_contract(data, "a1", [(SEASON, 25_000_000)])
    return data


class TaxPoolTests(unittest.TestCase):
    def test_share_is_half_the_other_teams_tax_split_among_teams_under(self):
        data = taxed_league()
        b_bill = tax.luxury_tax_bill(216_000_000, SEASON)
        a_bill = tax.luxury_tax_bill(208_250_000, SEASON)
        self.assertGreater(b_bill, 0)
        # A gets half of B's tax, shared with C (the only other team under): A's own bill never pays A.
        self.assertAlmostEqual(tax.pool_share_if_under(data, "a", SEASON), 0.5 * b_bill / 2, places=0)
        # C would share half of A's and B's tax with nobody else (A and B are both over).
        self.assertAlmostEqual(tax.pool_share_if_under(data, "c", SEASON), 0.5 * (a_bill + b_bill), places=0)

    def test_getting_under_the_line_earns_the_share(self):
        data = taxed_league()
        result = tax.tax_saved(data, "a", [], [P("a5")])
        share = tax.pool_share_if_under(data, "a", SEASON)
        self.assertAlmostEqual(result["pool"], share, places=0)
        self.assertAlmostEqual(result["saved"], result["tax_only"] + share, places=0)
        self.assertIn("get under the luxury tax line", tax.saving_words(result))
        # Moving salary that leaves the team over the line earns no share.
        set_contract(data, "a1", [(SEASON, 60_000_000)])
        self.assertEqual(tax.tax_saved(data, "a", [], [P("a5")])["pool"], 0.0)

    def test_going_over_the_line_loses_the_share(self):
        data = taxed_league()
        # C ($13M) taking B's $205M of b0 and b1 would put it over: it loses the share it expects.
        result = tax.tax_saved(data, "c", [P("b0"), P("b1")], [])
        self.assertAlmostEqual(result["pool"], -tax.pool_share_if_under(data, "c", SEASON), places=0)

    def test_short_roster_must_be_filled_before_it_counts_as_under(self):
        data = league()
        # A at $199.5M with 13 players: under the real $200.4M line today (TRADE-VOLUME: the trade code used $207.4M), but
        # the 14th player's minimum salary puts it over.
        set_contract(data, "a1", [(SEASON, 31_000_000)])
        set_contract(data, "a12", [(SEASON, 1_000_000)])
        payroll = tx.team_salary_total_for_season(data, "a", SEASON)
        self.assertLess(payroll, LINE)
        self.assertGreater(payroll + tax.POOL_FILL_SALARY, LINE)
        set_contract(data, "b0", [(SEASON, 190_000_000)])
        # Shedding a $1M player for nothing does not get A under (it still needs two fills).
        self.assertEqual(tax.tax_saved(data, "a", [], [P("a12")])["pool"], 0.0)
        # Shedding a5 ($15.75M) does.
        self.assertGreater(tax.tax_saved(data, "a", [], [P("a5")])["pool"], 0.0)

    def test_the_trade_value_counts_it_for_ai_teams_only(self):
        data = taxed_league()
        with_pool = tax.tax_value(data, "a", [], [P("a5")])
        with patch.object(tax, "pool_change", return_value=0.0):
            without = tax.tax_value(data, "a", [], [P("a5")])
        self.assertGreater(with_pool, without)
        data["_human_team_ids"] = ["a"]
        self.assertEqual(tax.tax_value(data, "a", [], [P("a5")]), 0.0)

    def test_the_evaluation_note_names_the_payout(self):
        data = taxed_league()
        value = tax.tax_value(data, "a", [], [P("a5")])
        self.assertIn("share of the tax payout", tax.tax_note(data, "a", [], [P("a5")], value))


class PayoutRecordTests(unittest.TestCase):
    def test_payout_recorded_once_with_equal_shares_paid_in_july(self):
        data = taxed_league()
        save = {"meta": {"season": SEASON}, "state": {"current_date": "2027-04-12"}}
        with patch("nba_gm_data.save.canonical_with_save", lambda canonical, s: canonical):
            tax.record_season_payrolls(save, data)
        record = save["luxury_tax_payouts"][SEASON]
        bills = {t: v["tax_bill"] for t, v in record["teams"].items()}
        self.assertEqual(sorted(record["taxpayers"]), ["a", "b"])
        self.assertEqual(record["recipients"], ["c"])
        self.assertAlmostEqual(record["total_tax"], bills["a"] + bills["b"], delta=1)
        self.assertAlmostEqual(record["share_per_team"], 0.5 * record["total_tax"], delta=1)
        self.assertEqual(record["teams"]["c"]["payout"], record["share_per_team"])
        self.assertEqual(record["teams"]["a"]["payout"], 0)
        self.assertEqual(record["paid_on"], "2027-07-15")
        self.assertEqual(record["assessed_on"], "2027-04-12")
        summary = tax.team_tax_payout_summary(save, "c")
        self.assertFalse(summary["paid"])
        save["state"]["current_date"] = "2027-07-20"
        summary = tax.team_tax_payout_summary(save, "c")
        self.assertTrue(summary["paid"])
        self.assertGreater(summary["payout_millions"], 0)
        self.assertGreater(tax.team_tax_payout_summary(save, "b")["tax_bill_millions"], 0)
        self.assertIsNone(tax.team_tax_payout_summary({}, "c"))


class RecentDraftPickTests(unittest.TestCase):
    def test_recent_draft_picks_are_protected_by_years_in_the_league_not_age(self):
        data = league()
        stirtz = {"id": "x", "draft_year": "2026", "age": 24}
        self.assertTrue(tt.recent_draft_pick(data, stirtz))
        self.assertFalse(tt.dump_age_ok(data, stirtz, 24.0))
        veteran_young = {"id": "y", "draft_year": 2022, "age": 23}
        self.assertFalse(tt.recent_draft_pick(data, veteran_young))
        self.assertTrue(tt.dump_age_ok(data, veteran_young, 23.0))  # a fourth-year player is not a fresh pick
        undrafted = {"id": "z", "draft_year": None}
        self.assertFalse(tt.dump_age_ok(data, undrafted, 22.0))
        self.assertTrue(tt.dump_age_ok(data, undrafted, 26.0))

    def test_dump_search_skips_a_recent_draft_pick(self):
        data = taxed_league()
        for p in data["players"]:
            if p["id"] == "a5":
                p["draft_year"] = "2025"
        offers = tt.salary_dump_offers(data, ["a", "b", "c"], set(), tx.default_transaction_model_config())
        self.assertFalse([o for o in offers if o["row"]["id"] == "a5"])


class UserAbsorberOfferTests(unittest.TestCase):
    def test_bounded_offer_is_rechecked_with_the_bounded_rule(self):
        cand = multi_candidate({"a": (-5.0, 1.0), "b": (8.0, 1.0), "c": (-20.0, 1.0)})
        data = league(_human_team_ids=["c"])
        # The two AI teams are within the two-team bounds; the human team's own view is not judged.
        self.assertTrue(mt.bounded_multi_team_accept(data, cand, set()))
        outright = all(e["accepted"] for e in cand["evaluations"] if e["perspective_team_id"] != "c")
        self.assertFalse(outright)


class DraftNightTests(unittest.TestCase):
    def test_every_part_of_the_draft_has_its_own_budget(self):
        self.assertEqual(play.draft_trade_segment(3)[0], "top_10")
        self.assertEqual(play.draft_trade_segment(16)[0], "picks_11_20")
        self.assertEqual(play.draft_trade_segment(26)[0], "picks_21_30")
        self.assertEqual(play.draft_trade_segment(45)[0], "round_2")
        budget = {"segments": {}}
        self.assertFalse(play.draft_trade_quiet_segment(budget, 12))
        self.assertTrue(play.draft_trade_quiet_segment(budget, 16))
        self.assertFalse(play.draft_trade_quiet_segment(budget, 9))  # never loosened in the top 10
        self.assertFalse(play.draft_trade_quiet_segment({"segments": {"picks_11_20": 1}}, 18))
        self.assertEqual(play.DRAFT_TRADE_LAST_PICK, 60)

    def test_second_round_offers_never_include_a_first(self):
        seconds = [{"id": f"s{i}", "round": 2, "season": "2029", "status": "future"} for i in range(4)]
        with patch.object(play, "pick_asset_value", side_effect=lambda pick, phase: 10.0):
            offer = play.draft_trade_second_round_offer([], 15.0, 0.0, seconds, False)
            self.assertEqual([a["value"] for a in offer], ["s0", "s1"])
            lower = [{"kind": "pick", "value": "lower"}]
            self.assertEqual(play.draft_trade_second_round_offer(lower, 15.0, 15.0, seconds, True)[1:],
                             [{"kind": "pick", "value": "s0"}])
            self.assertEqual(play.draft_trade_second_round_offer([], 100.0, 0.0, seconds, False), [])

    def test_pick_destinations_cover_multi_team_deals(self):
        proposal = {"transfers": [{"to_team_id": "a", "assets": [{"kind": "pick", "id": "p16"}]},
                                  {"to_team_id": "b", "assets": [{"kind": "pick", "id": "p21"}]},
                                  {"to_team_id": "c", "assets": [{"kind": "pick", "id": "p27"}, {"kind": "player", "id": "x"}]}]}
        self.assertEqual(play.draft_trade_pick_destinations(proposal), {"p16": "a", "p21": "b", "p27": "c"})
        two = {"from_team_id": "s", "to_team_id": "a", "from_assets": [{"kind": "pick", "id": "p16"}],
               "to_assets": [{"kind": "pick", "value": "p21"}]}
        self.assertEqual(play.draft_trade_pick_destinations(two), {"p16": "a", "p21": "s"})

    def test_chain_needs_the_seller_outright_and_each_buyer_with_its_target(self):
        chain = {"seller_id": "a", "seller_floor": -2.0, "premiums": {"b": 6.0, "c": 4.0}}
        ok = multi_candidate({"a": (3.0, 1.0), "b": (-4.0, 1.0), "c": (-2.0, 1.0)})
        self.assertTrue(mt.draft_chain_accept(ok, chain))
        seller_short = multi_candidate({"a": (0.5, 1.0), "b": (8.0, 1.0), "c": (8.0, 1.0)})
        self.assertFalse(mt.draft_chain_accept(seller_short, chain))
        buyer_short = multi_candidate({"a": (3.0, 1.0), "b": (-4.0, 1.0), "c": (-4.0, 1.0)})
        self.assertFalse(mt.draft_chain_accept(buyer_short, chain))
        illegal = multi_candidate({"a": (3.0, 1.0), "b": (8.0, 1.0), "c": (8.0, 1.0)})
        illegal["legality"] = {"status": "illegal", "issues": ["x"]}
        self.assertFalse(mt.draft_chain_accept(illegal, chain))


if __name__ == "__main__":
    unittest.main()
