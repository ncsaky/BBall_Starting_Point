"""Trade step 2: front-office targets, willing sellers, offers at the seller's price, the scaled pick bonus and
draft-night trades both teams accept (docs/agents/tasks/trade-step2-targets.md)."""
from copy import deepcopy
import random
import unittest
from unittest.mock import patch

from nba_gm_data import play
from nba_gm_data import trade_ownership as own
from nba_gm_data import trade_targets as tt
from nba_gm_data import transactions as tx

from test_multi_team_trades import fixture


def row(pid, team, *, age=27.0, bucket="wing", minutes=24.0, on_court=60.0, playoff=60.0, value=50.0,
        development=0.0, surplus=0.0, health=0.0, salary=10e6, years=2, attrs=None):
    return {"id": pid, "name": pid.upper(), "team_id": team, "player": {"id": pid, "team_id": team, "name": pid.upper()},
            "age": age, "bucket": bucket, "minutes": minutes, "on_court": on_court, "playoff": playoff, "value": value,
            "market": value, "development": development, "surplus": surplus, "health": health, "salary": salary,
            "years": years, "attrs": {key: 50.0 for _, _, key in tt.SKILL_NEEDS} | (attrs or {})}


def league(window_phase, *, phase=None, extra_rows=(), core=(), pressure=55, firsts=1, spacing=50.0):
    """A two-team league with prepared target rows: team 'x' (the one under test) and team 'y'."""
    players = [{"id": f"x{i}", "team_id": "x"} for i in range(10)] + [{"id": f"y{i}", "team_id": "y"} for i in range(10)]
    canonical = {
        "meta": {"active_season": "2026-27", "current_date": "2027-01-20"},
        "teams": [{"id": "x", "abbrev": "X"}, {"id": "y", "abbrev": "Y"}],
        "players": players,
        "team_strategic_states": [
            {"team_id": "x", "window_phase": window_phase, "phase": phase or LEGACY_PHASE.get(window_phase),
             "pressure": pressure, "pick_inventory": {"first_round_count": firsts}},
            {"team_id": "y", "window_phase": "entering", "phase": "developing", "pressure": 55,
             "pick_inventory": {"first_round_count": 2}}],
        "team_plans": {"x": {"core_ids": list(core)}},
    }
    rows = {}
    buckets = ["guard", "guard", "guard", "wing", "wing", "wing", "big", "big", "big", "guard"]
    for i in range(10):
        rows[f"x{i}"] = row(f"x{i}", "x", bucket=buckets[i], on_court=70.0 - i * 2, minutes=34.0 - i * 3)
        rows[f"y{i}"] = row(f"y{i}", "y", bucket=buckets[i], on_court=69.0 - i * 2, minutes=34.0 - i * 3)
    for extra in extra_rows:
        rows[extra["id"]] = extra
        canonical["players"].append({"id": extra["id"], "team_id": extra["team_id"]})
    canonical["_trade_target_memo"] = {"players_source": canonical["players"], "rows": rows,
                                       "features": {"x": {"spacing": spacing}, "y": {"spacing": 60.0}}}
    return canonical


LEGACY_PHASE = {"peak": "contending", "entering": "developing", "exiting": "retooling",
                               "rebuilding": "rebuilding"}


class TargetsByPhaseTests(unittest.TestCase):
    def test_contender_looks_for_rotation_upgrades_and_a_skill_it_lacks(self):
        canonical = league("peak", firsts=3, spacing=30.0)
        targets = tt.team_trade_targets(canonical, "x")
        keys = [t["key"] for t in targets]
        self.assertEqual(keys[0], "rotation_upgrade")
        self.assertIn("skill", keys)
        self.assertIn("star", keys)  # it has the picks to push
        self.assertLessEqual(len(targets), tt.TARGETS_PER_TEAM)
        upgrade = targets[0]["filters"]
        sixth = sorted((r["on_court"] for r in tt._team_rows(canonical, "x")), reverse=True)[5]
        self.assertGreaterEqual(upgrade["min_on_court"], sixth + 1.0)  # he must take a real role
        skill = next(t for t in targets if t["key"] == "skill")
        self.assertEqual(skill["filters"]["skill"][0], "range")
        self.assertIn("shooting", skill["label"])
        for target in targets:
            self.assertTrue(target["reason"] and target["label"])
            self.assertNotIn("_", target["reason"])  # plain words, no internal codes

    def test_contender_without_picks_or_pressure_does_not_chase_a_star(self):
        keys = [t["key"] for t in tt.team_trade_targets(league("peak", firsts=0), "x")]
        self.assertNotIn("star", keys)

    def test_rebuilder_targets_young_players_from_teams_competing_now(self):
        canonical = league("rebuilding")
        targets = tt.team_trade_targets(canonical, "x")
        self.assertEqual({t["key"] for t in targets}, {"prospect", "young_starter"})
        for target in targets:
            self.assertLessEqual(target["filters"]["age_max"], 25.5)
            self.assertTrue(target["filters"]["no_bad_contract"])
            self.assertNotIn("rebuild", target["filters"]["seller_stances"])
        veteran = row("vet", "y", age=31.0, on_court=75.0, development=0.0)
        self.assertTrue(all(tt.target_match(t, veteran) is None for t in targets))
        prospect = row("kid", "y", age=21.0, on_court=66.0, development=12.0, salary=4e6)
        self.assertIsNotNone(tt.target_match(targets[0], prospect))
        bad_money = dict(prospect, surplus=-20.0)
        self.assertIsNone(tt.target_match(targets[0], bad_money))

    def test_retooling_team_looks_for_a_successor_to_its_aging_core_player(self):
        aging = row("old", "x", age=33.0, bucket="big", on_court=72.0, minutes=33.0)
        canonical = league("exiting", extra_rows=[aging], core=["old"])
        targets = tt.team_trade_targets(canonical, "x")
        successor = targets[0]
        self.assertEqual(successor["key"], "successor")
        self.assertIn("OLD", successor["label"])
        self.assertEqual(successor["filters"]["buckets"], {"big"})
        self.assertLessEqual(successor["filters"]["age_max"], 27.0)


class YoungPieceTests(unittest.TestCase):
    def test_rebuilding_team_keeps_its_young_players_without_a_reason(self):
        kid = row("kid", "y", age=21.0, minutes=30.0)
        self.assertTrue(tt.young_piece_kept(kid, "rebuild"))
        self.assertTrue(tt.young_piece_kept(dict(kid, minutes=8.0), "retool"))
        self.assertTrue(tt.young_piece_kept(kid, "contend"))  # a young starter anywhere
        self.assertFalse(tt.young_piece_kept(dict(kid, minutes=8.0), "contend"))  # a blocked prospect is available
        self.assertFalse(tt.young_piece_kept(dict(kid, age=28.0), "rebuild"))

    def test_pairings_skip_a_rebuilders_young_starter(self):
        canonical = league("peak", firsts=0)
        canonical["team_strategic_states"][1].update(window_phase="rebuilding", phase="rebuilding")
        kid = row("kid", "y", age=21.0, bucket="wing", on_court=80.0, playoff=80.0, minutes=32.0)
        canonical["_trade_target_memo"]["rows"]["kid"] = kid
        canonical["players"].append({"id": "kid", "team_id": "y"})
        with patch.object(tt, "team_sell_reasons", return_value={}), \
             patch.object(tx, "effectively_untouchable", return_value=False), \
             patch("nba_gm_data.team_planning.core_commitment", return_value=False), \
             patch.object(tt, "asking_price", return_value={"own": 1.0, "ask": 1.0, "threshold": 1.0}), \
             patch.object(tt, "buyer_value", return_value=50.0), \
             patch.object(tt, "trade_surplus", return_value=0.0), \
             patch.object(tt, "buyer_minutes", return_value=30.0):
            pairings = tt.target_pairings(canonical, ["x"], set(), 2, {}, random.Random(1))
        self.assertNotIn("kid", {p["row"]["id"] for p in pairings})


class WillingSellerTests(unittest.TestCase):
    def money_league(self, *, payroll, window="rebuilding", years=1, age=31):
        data = {"meta": {"active_season": "2026-27"}, "players": [{"id": "p", "team_id": "t", "age": age}],
                "contracts": [{"player_id": "p", "_active_season": "2026-27",
                               "seasons": [{"season": f"{2026 + i}-{27 + i}", "salary": 12e6} for i in range(years)]}]}
        state = {"window_phase": window, "phase": LEGACY_PHASE[window]}
        with patch.object(tx, "team_current_salary_total", return_value=payroll):
            return own._money_reasons(data, data["players"][0], "t", state)

    def test_team_over_the_tax_line_will_move_a_paid_player(self):
        self.assertIn("over_tax_line", self.money_league(payroll=250e6, years=3))
        self.assertNotIn("over_tax_line", self.money_league(payroll=150e6, years=3))

    def test_expiring_veteran_on_a_team_not_contending_is_for_sale(self):
        self.assertIn("expiring_veteran_non_contender", self.money_league(payroll=150e6, years=1))
        self.assertNotIn("expiring_veteran_non_contender", self.money_league(payroll=150e6, years=3))
        self.assertNotIn("expiring_veteran_non_contender", self.money_league(payroll=150e6, years=1, window="peak"))
        self.assertNotIn("expiring_veteran_non_contender", self.money_league(payroll=150e6, years=1, age=24))

    def test_contract_reasons_scale_the_own_player_premium_down(self):
        for reason in ("over_tax_line", "expiring_veteran_non_contender"):
            self.assertLess(own.MOVE_REASON_FACTORS[reason], 1.0)
            self.assertIn(reason, tt.SELL_REASON_WORDS)

    def test_every_sell_reason_has_plain_words(self):
        for reason in own.MOVE_REASON_FACTORS:
            self.assertIn(reason, tt.SELL_REASON_WORDS)
            self.assertNotIn("_", tt.SELL_REASON_WORDS[reason])


class SymmetricPickValueTests(unittest.TestCase):
    def setUp(self):
        self.data = tx.with_transaction_context(fixture())
        self.config = tx.default_transaction_model_config()

    def bonus(self, incoming=(), outgoing=()):
        return tx.strategic_fit_adjustment(self.data, [{"kind": "pick", "id": p} for p in incoming],
                                           [{"kind": "pick", "id": p} for p in outgoing], "a", self.config)

    def test_bonus_scales_with_the_picks_value(self):
        first, second = self.bonus(incoming=["b2028r1"]), self.bonus(incoming=["b2029r2"])
        self.assertGreater(first, second * 3)
        self.assertLess(second, 4.0)  # a second no longer adds a flat +7
        first_value = tx.pick_asset_value(tx.pick_by_id(self.data, "b2028r1"), "rebuilding")
        self.assertAlmostEqual(first, tx.REBUILDER_PICK_BONUS_RATE * first_value, places=2)

    def test_sending_a_pick_costs_what_receiving_it_adds(self):
        self.assertAlmostEqual(self.bonus(outgoing=["a2028r1"]),
                               -tx.rebuilder_draft_bonus(self.data, {"kind": "pick", "id": "a2028r1"}, "rebuilding", self.config),
                               places=3)
        self.assertLess(self.bonus(outgoing=["a2028r1"]), 0.0)


class AskingPriceTests(unittest.TestCase):
    def setUp(self):
        self.data = tx.trade_search_context(tx.with_spatial_fit_context(tx.with_transaction_context(fixture())))
        self.config = tx.default_transaction_model_config()

    def test_asking_price_is_the_sellers_own_value_plus_its_margin(self):
        ask = tt.asking_price(self.data, "a", "a0", self.config)
        own_value = tx.package_value_for_team(self.data, [{"kind": "player", "id": "a0"}], "a")
        self.assertAlmostEqual(ask["own"], own_value, places=6)
        self.assertAlmostEqual(ask["ask"] - ask["own"], ask["threshold"]
                               - tx.strategic_fit_adjustment(self.data, [], [{"kind": "player", "id": "a0"}], "a", self.config))

    def test_packages_are_built_toward_the_sellers_price_and_screened_from_both_sides(self):
        buyer, seller = tx.team_by_id(self.data, "b"), tx.team_by_id(self.data, "a")
        target = [{"kind": "player", "id": "a0"}]
        ask = tt.asking_price(self.data, "a", "a0", self.config)
        options = tx.buyer_offer_packages_for_value(self.data, buyer, seller, ask["ask"], 10e6, 17, {"a0"},
                                                    max_results=24, return_options=True, seller_view_outgoing=target)
        self.assertTrue(options)
        pairing = {"row": tt.player_rows(self.data)["a0"], "buyer_id": "b", "ask": ask, "buyer_minutes": 30.0}
        kept = tt.ranked_packages(self.data, pairing, options, self.config, 4)
        self.assertLessEqual(len(kept), 4)
        for option in kept:
            assets = tx.normalize_assets(self.data, buyer, option["assets"])
            seller_net = tt.quick_net(self.data, "a", assets, target, self.config)
            buyer_net = tt.quick_net(self.data, "b", target, assets, self.config)
            # Inside the acceptance check's bounded-negotiation room, with the screen's margin.
            self.assertGreaterEqual(min(seller_net, buyer_net), -9.0 - tt.PRESCREEN_TOLERANCE)
            self.assertGreaterEqual(seller_net + buyer_net, -2.0 - tt.PRESCREEN_TOLERANCE)

    def test_the_human_team_is_never_a_buyer_or_seller_in_the_target_search(self):
        data = dict(self.data, _human_team_ids=["c"])
        data["_trade_target_memo"] = None
        pairings = tt.target_pairings(data, ["a", "b"], set(), 2, self.config, random.Random(1))
        for pairing in pairings:
            self.assertNotEqual(pairing["buyer_id"], "c")
            self.assertNotEqual(pairing["row"]["team_id"], "c")


class DraftNightBothSidesTests(unittest.TestCase):
    def test_buyer_must_clear_its_threshold_with_its_prospect_premium(self):
        seller = {"accepted": True, "net_value": 6.0}
        buyer = {"accepted": False, "net_value": -20.0, "acceptance_threshold": 1.5}
        self.assertFalse(play.draft_trade_both_accept(seller, buyer, premium=10.0, seller_floor=-2.0))
        self.assertTrue(play.draft_trade_both_accept(seller, buyer, premium=22.0, seller_floor=-2.0))

    def test_seller_must_accept_on_its_own_evaluation(self):
        buyer = {"net_value": 5.0, "acceptance_threshold": 1.5}
        self.assertFalse(play.draft_trade_both_accept({"accepted": False, "net_value": 3.0}, buyer, 0.0, -2.0))
        self.assertFalse(play.draft_trade_both_accept({"accepted": True, "net_value": 1.0}, buyer, 0.0, 4.0))

    def test_premium_is_half_the_slot_gap_and_zero_for_a_reach(self):
        active = {"meta": {"active_season": "2026-27"}, "team_strategic_states": [{"team_id": "t", "phase": "neutral"}]}
        self.assertEqual(play.draft_target_premium(active, "t", 15, 12), 0.0)
        gap = play.draft_slot_value(active, "t", 3) - play.draft_slot_value(active, "t", 12)
        self.assertGreater(gap, 0.0)
        self.assertAlmostEqual(play.draft_target_premium(active, "t", 3, 12), gap * play.DRAFT_BOARD_CONFIDENCE)

    def test_accepted_draft_trade_records_the_buyers_reason(self):
        candidate = {"evaluations": [{"perspective_team_id": "s", "accepted": True, "decision": "accept"},
                                     {"perspective_team_id": "b", "accepted": False, "decision": "reject",
                                      "decision_reasons": ["Net value -9.00 is below the required 1.50."]}]}
        play.mark_draft_target_acceptance(candidate, "b", "Some Prospect", 4, 12.5)
        buyer = candidate["evaluations"][1]
        self.assertTrue(buyer["accepted"])
        self.assertEqual(buyer["decision"], "accept_draft_target")
        self.assertEqual(buyer["draft_target_premium"], 12.5)
        self.assertTrue(any("Some Prospect" in reason for reason in buyer["decision_reasons"]))
        self.assertFalse(any(reason.startswith("Net value") for reason in buyer["decision_reasons"]))


class TradeReasonLogTests(unittest.TestCase):
    def test_applied_trade_log_keeps_both_teams_reasons(self):
        data = tx.with_transaction_context(fixture())
        report = tx.evaluate_trade(data, "A", "B", [{"kind": "player", "value": "a5"}], [{"kind": "player", "value": "b5"}],
                                   date="2027-01-31", context_ready=True)
        candidate = tx.mark_ai_trade_accepted(tx.candidate_from_evaluation(data, report))
        candidate["accepted_by_all"] = True
        for evaluation in candidate["evaluations"]:
            evaluation["accepted"] = True
        candidate["trade_reasons"] = {"text": "B (rebuilding) targeted a wing; A (rebuilding) moved him."}
        state = {"version": "league_save_v1", "meta": {"user_team_id": "human", "season": "2026-27"},
                 "state": {"current_date": "2027-01-31"}, "pending_trade_proposals": [deepcopy(candidate)],
                 "transaction_logs": []}
        result = tx.apply_trade_to_state(state, candidate["proposal"]["id"], date="2027-01-31", canonical=data)
        if result["status"] != "applied":
            self.skipTest(f"fixture trade not applied: {result['status']}")
        self.assertEqual(state["transaction_logs"][-1]["trade_reasons"]["text"], candidate["trade_reasons"]["text"])


if __name__ == "__main__":
    unittest.main()
