"""TRADE-FOLLOWUPS (docs/agents/tasks/trade-followups.md): agreed market sales are executed once or cancelled with a
reason; young rotation pieces stay off the market; front-office reads on team pages; summer market days keep the
negotiation ledger; no hidden front-office profile field moves a trade decision."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from nba_gm_data import front_office as fo
from nba_gm_data import trade_market as tm
from nba_gm_data import trade_targets as tt
from nba_gm_data import trade_tax
from nba_gm_data import transactions as tx

from test_trade_market import league, office_row, player


def sold_war(buyer="a", seller="b", pid="b1", bidders=("a", "c"), day="2027-02-03"):
    return {"player_id": pid, "player_name": pid.upper(), "seller_id": seller, "date": day, "bidders": sorted(bidders),
            "rounds": [{"round": 1, "bids": {}, "leader": buyer}], "winner": buyer,
            "key": tm.negotiation_key(buyer, seller, pid), "winning_margin": 9.0, "winning_offer": None,
            "decide_by": day, "status": "sold"}


def agreed_day(day="2027-02-03", war=None):
    war = war or sold_war(day=day)
    key = war["key"]
    return {"date": day, "deals": [{"key": key, "player_id": war["player_id"], "proposal_id": "p1", "kind": "sale"}],
            "shopping": [{"player_id": war["player_id"], "player_name": "B1", "seller_id": war["seller_id"],
                          "reasons": ["over_tax_line"], "interested": list(war["bidders"]), "decide_by": day}],
            "wars": [war], "waiting": [], "negotiations": [], "unsolicited": []}


def tagged(war, day="2027-02-03"):
    return {"proposal": {"id": "p1"}, "market_deal": {
        "key": war["key"], "buyer_id": war["winner"], "seller_id": war["seller_id"], "player_id": war["player_id"],
        "player_name": "B1", "date": day, "kind": "sale", "seller_reasons": ["over_tax_line"],
        "seller_stance": "retool"}}


class AgreedSalesTests(unittest.TestCase):
    """Fix 1: Josh Hart was "sold" to the Lakers on seven market days before Houston got him."""

    def test_an_agreed_sale_that_fails_the_final_check_is_cancelled_with_its_reason(self):
        active = league(date="2027-02-03")
        save = {}
        war = sold_war()
        tm.apply_market_updates(save, agreed_day(war=war), active, chosen={war["key"]})
        entry = save["trade_market"]["shopping"]["b1"]
        self.assertEqual(entry["status"], "agreed")
        tm.note_market_execution(save, tagged(war), {"status": "not_applied_roster_plan",
                                                     "issues": ["A: Draft-asset overpayment is not justified."]},
                                 "2027-02-03")
        entry = save["trade_market"]["shopping"]["b1"]
        self.assertEqual(entry["status"], "cancelled")
        self.assertIn("reconsidered the deal", entry["cancel_reason"])
        self.assertIn("Draft-asset overpayment", entry["cancel_reason"])
        neg = save["trade_market"]["negotiations"][war["key"]]
        self.assertEqual(neg["status"], "dead")
        self.assertEqual(neg["cooldown_until"], "2027-03-05")
        self.assertIn("reconsidered", neg["death"]["cancelled"])
        self.assertEqual(save["trade_market"]["wars"][-1]["status"], "cancelled")
        self.assertEqual(save["trade_market"]["stats"]["2026-27"]["agreed_cancelled"], 1)
        # The next market day the same buyer cannot agree the same deal again ...
        market = tm.SearchMarket({**active, "trade_market_ledger": tm.ledger_view(save)}, "2027-02-04", 2)
        same = {"buyer_id": "a", "row": {"id": "b1", "team_id": "b", "value": 55.0}, "reasons": ["over_tax_line"],
                "rank": 0, "target": {"id": "t:a"}}
        other = {**same, "buyer_id": "c", "target": {"id": "t:c"}}
        with patch.object(fo, "player_opinion", return_value=None):
            kept = market.filter_pairings([same, other], {})
        self.assertEqual([p["buyer_id"] for p in kept], ["c"])
        # ... while other teams may still bid: the cancelled sale is a finished record, a new shopping entry starts.
        tm.apply_market_updates(save, {"date": "2027-02-04", "shopping": [
            {"player_id": "b1", "player_name": "B1", "seller_id": "b", "reasons": ["over_tax_line"],
             "interested": ["c", "d"], "decide_by": "2027-02-05"}]}, active)
        self.assertEqual(save["trade_market"]["shopping"]["b1"]["status"], "shopping")
        self.assertEqual(save["trade_market"]["shopping"]["b1"]["started"], "2027-02-04")

    def test_a_completed_sale_is_sold_once(self):
        active = league(date="2027-02-03")
        save = {}
        war = sold_war()
        tm.apply_market_updates(save, agreed_day(war=war), active, chosen={war["key"]})
        tm.note_market_execution(save, tagged(war), {"status": "applied"}, "2027-02-03")
        entry = save["trade_market"]["shopping"]["b1"]
        self.assertEqual((entry["status"], entry["moved_to"], entry["sold_date"]), ("sold", "a", "2027-02-03"))
        self.assertEqual(save["trade_market"]["stats"]["2026-27"]["agreed_executed"], 1)

    def test_a_sale_the_review_has_no_room_for_is_held_not_agreed(self):
        active = league(date="2027-02-03")
        save = {}
        war = sold_war()
        tm.apply_market_updates(save, agreed_day(war=war), active, chosen=set())
        entry = save["trade_market"]["shopping"]["b1"]
        self.assertEqual(entry["status"], "bidding")
        self.assertEqual(entry["held"]["reason"], tm.HELD_NO_ROOM)
        self.assertEqual(save["trade_market"].get("wars") or [], [])  # never recorded as a sale
        self.assertEqual(save["trade_market"]["stats"]["2026-27"]["agreed_not_chosen"], 1)

    def test_an_agreement_never_completed_is_cancelled_the_next_market_day(self):
        active = league(date="2027-02-03")
        save = {}
        war = sold_war()
        tm.apply_market_updates(save, agreed_day(war=war), active, chosen={war["key"]})
        tm.refresh_ledger(save, active, "2027-02-04")  # b1 is still on team b
        self.assertEqual(save["trade_market"]["shopping"]["b1"]["status"], "cancelled")

    def test_the_apply_step_records_the_answer_for_a_tagged_deal(self):
        war = sold_war()
        save = {"pending_trade_proposals": [tagged(war)]}
        with patch.object(tx, "_apply_trade_to_state", return_value={"status": "not_applied_salary_legality",
                                                                      "issues": ["Over the second apron."]}), \
                patch.object(tm, "note_market_execution") as noted:
            tx.apply_trade_to_state(save, "p1", "2027-02-03")
        noted.assert_called_once()
        self.assertEqual(noted.call_args.args[2]["status"], "not_applied_salary_legality")
        self.assertIn("cap rules", tm.failure_reason(noted.call_args.args[2]))

    def test_the_final_check_sees_the_concession_the_sides_agreed_with(self):
        active = league(office_row("A", patience=10.0), office_row("B"), date="2027-01-20")
        save = {}
        update = {"date": "2027-01-18", "negotiations": [{"key": "a|b|b1", "buyer_id": "a", "seller_id": "b",
                                                          "player_id": "b1", "player_name": "B1",
                                                          "gaps": {"a": -2.0, "b": -2.0}, "offer": None}]}
        tm.apply_market_updates(save, update, active)
        tm.apply_market_updates(save, {"date": "2027-01-20", "deals": [{"key": "a|b|b1", "player_id": "b1",
                                                                         "proposal_id": "p1"}]}, active)
        self.assertEqual(save["trade_market"]["negotiations"]["a|b|b1"]["status"], "agreed")
        canonical = {**active, "trade_market_ledger": tm.ledger_view(save)}
        term = tm.concession_term(canonical, "a", {"from_team_id": "b", "to_team_id": "a"}, [player("b1")], [])
        self.assertIsNotNone(term)  # the apply-time evaluation keeps the agreed concession

    def test_release_turns_an_unused_agreement_back_into_talks(self):
        active = league(date="2027-07-02")
        save = {}
        war = sold_war(day="2027-07-02")
        tm.apply_market_updates(save, agreed_day(day="2027-07-02", war=war), active, chosen={war["key"]})
        self.assertEqual(tm.release_agreements(save, [tagged(war, "2027-07-02")], "2027-07-02"), 1)
        self.assertEqual(save["trade_market"]["shopping"]["b1"]["status"], "bidding")
        self.assertEqual(save["trade_market"]["wars"][-1]["status"], "held")


class SummerMarketTests(unittest.TestCase):
    """Fix 4: summer market days keep the ledger; a decision day between summer market days is kept, not lapsed."""

    def test_summer_talks_continue_on_the_next_market_day(self):
        active = league(office_row("A", patience=50.0), office_row("B", patience=50.0), date="2027-07-01")
        save = {}
        row = {"key": "a|b|b1", "buyer_id": "a", "seller_id": "b", "player_id": "b1", "player_name": "B1",
               "gaps": {"a": -2.0, "b": -3.0}, "offer": None}
        tm.begin_market_day(save, active, "2027-07-01", {"market_updates": {"date": "2027-07-01", "negotiations": [row]}}, [])
        tm.begin_market_day(save, active, "2027-07-02", {"market_updates": {"date": "2027-07-02", "negotiations": [row]}}, [])
        neg = save["trade_market"]["negotiations"]["a|b|b1"]
        self.assertEqual(len(neg["rounds"]), 2)
        canonical = {**active, "meta": {**active["meta"], "current_date": "2027-07-03"},
                     "trade_market_ledger": tm.ledger_view(save)}
        size, _ = tm.concession_size(canonical, "a", neg)
        self.assertGreater(size, 0.0)

    def test_a_summer_decision_day_passed_between_markets_is_decided_at_the_next(self):
        entry = {"player_id": "b1", "seller_id": "b", "status": "bidding", "decide_by": "2027-07-06",
                 "last_date": "2027-07-03", "bids": [{"date": "2027-07-03", "margin": 3.0}]}
        save = {"trade_market": {**tm.empty_ledger(), "shopping": {"b1": deepcopy(entry)}}}
        active = league(date="2027-08-01")
        tm.refresh_ledger(save, active, "2027-08-01")
        self.assertEqual(save["trade_market"]["shopping"]["b1"]["status"], "bidding")
        market = tm.SearchMarket({**active, "trade_market_ledger": tm.ledger_view(save)}, "2027-08-01", 2)
        self.assertEqual(market.current_decision_day("b1", "b"), "2027-08-01")
        # In season the same overdue entry lapses (the next search starts a fresh one).
        season ={"trade_market": {**tm.empty_ledger(), "shopping": {"b1": {**entry, "decide_by": "2027-01-10",
                                                                            "last_date": "2027-01-09"}}}}
        tm.refresh_ledger(season, league(date="2027-01-21"), "2027-01-21")
        self.assertEqual(season["trade_market"]["shopping"]["b1"]["status"], "lapsed")


def team_rows(rows):
    by_team = {}
    for row in rows:
        by_team.setdefault(row["team_id"], []).append(row)
    for team in by_team.values():
        for rank, row in enumerate(sorted(team, key=lambda r: (-r["minutes"], r["id"])), start=1):
            row["minutes_rank"] = rank
        for rank, row in enumerate(sorted(team, key=lambda r: (-r["on_court"], r["id"])), start=1):
            row["on_court_rank"] = rank
    return rows


def young(pid, *, age=23.0, minutes=20.0, on_court=60.0, value=60.0):
    return {"id": pid, "team_id": "m", "age": age, "minutes": minutes, "on_court": on_court, "value": value}


class YoungRotationGuardTests(unittest.TestCase):
    """Fix 2: rising Memphis sold Javon Small (23, its second-best player on the court, 20 minutes) for two seconds."""

    def roster(self, *extra):
        vets = [young(f"v{i}", age=29.0, minutes=32.0 - i * 3, on_court=66.0 - i * 2, value=50.0) for i in range(7)]
        return team_rows(vets + list(extra))

    def test_a_young_rotation_player_who_is_one_of_the_better_players_is_kept(self):
        small = young("small", minutes=19.8, on_court=64.7, value=80.6)
        self.roster(small)
        self.assertLess(small["minutes"], tt.YOUNG_STARTER_MINUTES)
        self.assertLess(small["on_court"], tt.YOUNG_CORE_ON_COURT)
        self.assertTrue(tt.young_piece_kept(small, "rise"))
        self.assertTrue(tt.young_piece_kept(small, "contend"))

    def test_role_and_value_are_both_needed(self):
        bench = young("bench", minutes=6.0, on_court=64.0, value=80.0)    # good, but no real role
        role = young("role", minutes=20.0, on_court=48.0, value=55.0)     # a role, but not one of the better players
        self.roster(bench, role)
        self.assertFalse(tt.young_piece_kept(bench, "rise"))
        self.assertFalse(tt.young_piece_kept(role, "rise"))
        upside = young("upside", age=21.0, minutes=16.0, on_court=50.0, value=74.0)  # a real role and a core asset
        self.roster(upside)
        self.assertTrue(tt.young_piece_kept(upside, "contend"))
        self.assertFalse(tt.young_piece_kept(dict(upside, age=27.0), "contend"))

    def test_a_listing_or_blocked_reason_still_exposes_him(self):
        self.assertTrue(tt.exposing_reasons(["gm_listed"]))
        self.assertFalse(tt.exposing_reasons(["over_tax_line"]))  # money alone never puts a young piece on the market


class HiddenProfileTests(unittest.TestCase):
    """Fix 5: no hidden front-office profile field moves a trade decision (rule 4)."""

    def test_every_office_has_the_same_acceptance_margin(self):
        config = tx.default_transaction_model_config()
        canonical = {"front_office_profiles": [
            {"team_id": "a", "asset_discipline": 94, "competence": 92, "owner_pressure": 54},
            {"team_id": "b", "asset_discipline": 42, "competence": 58, "owner_pressure": 88}]}
        self.assertEqual(tx.acceptance_threshold(canonical, "a", config), tx.acceptance_threshold(canonical, "b", config))
        self.assertEqual(tx.acceptance_threshold(canonical, "a", config), 1.5)

    def test_the_owner_money_factor_comes_from_visible_money_preferences(self):
        canonical = league(office_row("A", biases=("tax_averse",)), office_row("B", biases=("spends_tax",)))
        canonical["front_office_profiles"] = [{"team_id": "a", "financial_discipline": 34},
                                              {"team_id": "b", "financial_discipline": 84}]
        self.assertEqual(trade_tax.owner_money_factor(canonical, "a"), trade_tax.OWNER_FACTOR_TAX_AVERSE)
        self.assertEqual(trade_tax.owner_money_factor(canonical, "b"), trade_tax.OWNER_FACTOR_SPENDS_TAX)
        plain = league()
        plain["front_office_profiles"] = [{"team_id": "a", "financial_discipline": 84}]
        self.assertEqual(trade_tax.owner_money_factor(plain, "a"), 1.0)
        hints = fo.office_hints(canonical, "a", 3)
        self.assertTrue(any("luxury tax" in line["text"] for line in hints["lines"]))

    def test_a_star_hunt_follows_the_visible_urgency(self):
        hot = league(office_row("A", urgency=80.0))
        cool = league(office_row("A", urgency=60.0))
        for canonical in (hot, cool):
            canonical["team_strategic_states"][0]["pressure"] = 95  # the old hidden field no longer matters
        self.assertTrue(tt._urgent(hot, "a"))
        self.assertFalse(tt._urgent(cool, "a"))
        self.assertIn("playoff-level starters", fo._level_words("urgency", 80.0))


class TeamPageReadTests(unittest.TestCase):
    """Fix 3: the team page shows the same read as the trade window, sharpening with dealings."""

    def test_the_team_page_read_is_the_trade_window_read(self):
        from pathlib import Path
        from nba_gm_data import app_actions
        canonical = league(office_row("A", patience=20.0))
        save = {"front_office_traits": {"teams": {}}, "trade_market": {"dealings": {"a": {"count": 2, "days": []}}}}
        with patch.object(app_actions, "load_save", return_value=save), \
                patch.object(app_actions, "ensure_league_save_defaults", side_effect=lambda s, c: s), \
                patch.object(app_actions, "resolve_team", return_value={"id": "a", "abbrev": "A"}), \
                patch("nba_gm_data.save.human_controlled_team_ids", return_value={"u"}), \
                patch.object(app_actions, "canonical_with_save", return_value=canonical):
            read = app_actions.team_front_office_read(canonical, Path("x.json"), "A")
        self.assertEqual(read, fo.office_hints(canonical, "a", 2))
        self.assertEqual(read["precision"], "rough")
        self.assertTrue(any("impatient" in line["text"] for line in read["lines"]))


if __name__ == "__main__":
    unittest.main()
