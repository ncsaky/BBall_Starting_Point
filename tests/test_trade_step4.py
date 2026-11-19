"""Trade step 4: absorbed salary priced as a cost, repeat taxpayers, three- and four-team deals from near-misses, and
incoming absorber offers to the user's team (docs/agents/tasks/trade-step4-multi-team.md)."""
from copy import deepcopy
import math
import unittest
from unittest.mock import patch

from nba_gm_data import multi_team_trades as mt
from nba_gm_data import trade_targets as tt
from nba_gm_data import trade_tax as tax
from nba_gm_data import transactions as tx

from test_multi_team_trades import fixture

SEASON = "2026-27"
DATE = "2027-01-31"
P = lambda pid: {"kind": "player", "id": pid}


def league(**changes):
    """The three-team test league; a5 is a bench player on A ($15.75M, on-court 40, 8 minutes)."""
    data = fixture()
    for v in data["player_asset_valuations"]:
        if v["player_id"] == "a5":
            v.update(on_court_value=40, player_value=22)
    for p in data["players"]:
        if p["id"] == "a5":
            p["minutes_projection"] = 8
    for key, value in changes.items():
        data[key] = value
    return tx.with_transaction_context(data)


def set_contract(data, pid, seasons):
    for contract in data["contracts"]:
        if contract["player_id"] == pid:
            contract["seasons"] = [{"season": s, "salary": salary} for s, salary in seasons]
    data.pop("_contract_by_player", None)


class AbsorbCostTests(unittest.TestCase):
    def test_salary_for_a_player_outside_the_rotation_is_a_cost(self):
        data = league()
        # On B (eleven 50s), a 40 would be 12th: about 3.5 minutes, so all $15.75M is dead money this season.
        dead = tax.dead_money(data, "b", [P("a5")], [])
        self.assertAlmostEqual(dead["dead"], 15_750_000, delta=1)
        expected = -tax.ABSORB_VALUE_CAP * (1 - math.exp(-15.75 * tax.ABSORB_POINTS_PER_MILLION / tax.ABSORB_VALUE_CAP))
        self.assertAlmostEqual(tax.absorb_cost(data, "b", [P("a5")], []), expected, places=2)

    def test_no_cost_when_he_would_play(self):
        data = league()
        # On C (all 25s) he would start: nothing is dead.
        self.assertEqual(tax.absorb_cost(data, "c", [P("a5")], []), 0.0)

    def test_salary_sent_out_offsets_it(self):
        data = league()
        # b0 earns $15M, so only $0.75M of a5's $15.75M is new money.
        self.assertAlmostEqual(tax.dead_money(data, "b", [P("a5")], [P("b0")])["dead"], 750_000, delta=1)
        self.assertGreater(tax.absorb_cost(data, "b", [P("a5")], [P("b0")]), -5.0)

    def test_human_team_is_never_charged(self):
        data = league(_human_team_ids=["b"])
        self.assertEqual(tax.absorb_cost(data, "b", [P("a5")], []), 0.0)

    def test_rebuilders_count_a_veterans_later_years_as_partly_dead(self):
        data = league()
        set_contract(data, "a1", [(SEASON, 15_750_000), ("2027-28", 15_750_000), ("2028-29", 15_750_000)])
        for p in data["players"]:
            if p["id"] == "a1":
                p["age"] = 32
        for state in data["team_strategic_states"]:
            state["contend_distance"] = 1.0 if state["team_id"] == "c" else 0.0
        # He would start on C, so this season is fine; a deep rebuild still does not want his next two years.
        self.assertLess(tax.absorb_cost(data, "c", [P("a1")], []), -10.0)
        for state in data["team_strategic_states"]:
            state["contend_distance"] = 0.0
        self.assertEqual(tax.absorb_cost(data, "c", [P("a1")], []), 0.0)

    def test_the_evaluation_charges_it_and_says_so(self):
        data = league()
        report = tx.evaluate_trade(data, "A", "B", [{"kind": "player", "value": "a5"}],
                                   [{"kind": "pick", "value": "b2029r2"}], date=DATE)
        b = next(e for e in report["evaluations"] if e["perspective_team_id"] == "b")
        self.assertIn("Absorbed salary", b["notes"])

    def test_more_dead_money_costs_more_but_saturates(self):
        data = league()
        for v in data["player_asset_valuations"]:
            if v["player_id"] == "a6":
                v.update(on_court_value=39)
        data.pop("_absorb_depth_memo", None)
        one = tax.absorb_cost(data, "b", [P("a5")], [])
        two = tax.absorb_cost(data, "b", [P("a5"), P("a6")], [])
        self.assertLess(two, one)
        self.assertGreater(two, -tax.ABSORB_VALUE_CAP)


class RepeatTaxpayerTests(unittest.TestCase):
    def test_repeater_rates_are_a_dollar_higher_per_bracket(self):
        line = tx.cap_lines_for_season(SEASON)["tax_line"]
        bracket = line * tax.BRACKET_SHARE_OF_TAX_LINE
        self.assertAlmostEqual(tax.luxury_tax_bill(line + bracket, SEASON, True)
                               - tax.luxury_tax_bill(line + bracket, SEASON), bracket * 1.0, places=0)

    def test_three_of_the_previous_four_seasons(self):
        history = {s: {"t": {"taxed": True}} for s in ("2023-24", "2024-25")}
        self.assertFalse(tax.is_repeat_taxpayer({"team_payroll_history": history}, "t", SEASON))
        history["2025-26"] = {"t": {"taxed": True}}
        self.assertTrue(tax.is_repeat_taxpayer({"team_payroll_history": history}, "t", SEASON))
        self.assertFalse(tax.is_repeat_taxpayer({"team_payroll_history": history}, "u", SEASON))
        self.assertFalse(tax.is_repeat_taxpayer({}, "t", SEASON))

    def test_repeat_taxpayers_save_more_by_shedding(self):
        data = league()
        for p in data["players"]:
            if p["team_id"] == "a":
                pass
        set_contract(data, "a1", [(SEASON, 30_000_000)])
        plain = tax.tax_saved(data, "a", [], [P("a1")])["saved"]
        data["team_payroll_history"] = {s: {"a": {"taxed": True}} for s in ("2023-24", "2024-25", "2025-26")}
        repeat = tax.tax_saved(data, "a", [], [P("a1")])["saved"]
        self.assertGreater(plain, 0)
        self.assertGreater(repeat, plain)

    def test_payrolls_are_recorded_once_per_season(self):
        data = league()
        save = {"meta": {"season": SEASON}}
        with patch("nba_gm_data.save.canonical_with_save", lambda canonical, s: canonical):
            history = tax.record_season_payrolls(save, data)
            self.assertAlmostEqual(history[SEASON]["a"]["payroll"], 12 * 15_750_000 + 10_000_000, delta=1)
            self.assertFalse(history[SEASON]["a"]["taxed"])
            history[SEASON]["a"]["taxed"] = "kept"
            tax.record_season_payrolls(save, data)
        self.assertEqual(save["team_payroll_history"][SEASON]["a"]["taxed"], "kept")


def multi_candidate(nets, joiners=()):
    """A legal three-team candidate a->b->c->a with the given (net, threshold) per team."""
    transfers = [{"from_team_id": "a", "to_team_id": "b", "assets": [{"kind": "player", "id": "a1"}]},
                 {"from_team_id": "b", "to_team_id": "c", "assets": [{"kind": "player", "id": "b1"}]},
                 {"from_team_id": "c", "to_team_id": "a", "assets": [{"kind": "pick", "id": "c2029r2"}]}]
    evaluations = [{"perspective_team_id": t, "net_value": n, "acceptance_threshold": th, "accepted": n >= th,
                    "decision": "accept" if n >= th else "reject", "outgoing_value": 20.0, "decision_reasons": []}
                   for t, (n, th) in nets.items()]
    return {"proposal": {"id": "x", "transfers": transfers, "team_ids": ["a", "b", "c"]},
            "legality": {"status": "legal", "issues": []}, "evaluations": evaluations}


class MultiTeamAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.data = league()

    def test_main_teams_use_the_two_team_bounds_and_joiners_accept_outright(self):
        ok = multi_candidate({"a": (-5.0, 1.0), "b": (8.0, 1.0), "c": (3.0, 1.0)})
        self.assertTrue(mt.bounded_multi_team_accept(self.data, ok, {"c"}))
        short_joiner = multi_candidate({"a": (5.0, 1.0), "b": (8.0, 1.0), "c": (0.5, 1.0)})
        self.assertFalse(mt.bounded_multi_team_accept(self.data, short_joiner, {"c"}))
        too_short = multi_candidate({"a": (-10.0, 1.0), "b": (20.0, 1.0), "c": (3.0, 1.0)})
        self.assertFalse(mt.bounded_multi_team_accept(self.data, too_short, {"c"}))
        sum_short = multi_candidate({"a": (-6.0, 1.0), "b": (3.0, 1.0), "c": (3.0, 1.0)})
        self.assertFalse(mt.bounded_multi_team_accept(self.data, sum_short, {"c"}))

    def test_hard_rejections_are_never_bounded(self):
        cand = multi_candidate({"a": (5.0, 1.0), "b": (8.0, 1.0), "c": (3.0, 1.0)})
        cand["evaluations"][0]["decision"] = "reject_roster_plan"
        self.assertFalse(mt.bounded_multi_team_accept(self.data, cand, {"c"}))

    def test_marking_records_the_joiners(self):
        cand = mt.mark_multi_team_accepted(multi_candidate({"a": (-5.0, 1.0), "b": (8.0, 1.0), "c": (3.0, 1.0)}), {"c"})
        self.assertTrue(cand["accepted_by_all"])
        self.assertEqual(cand["joiner_team_ids"], ["c"])
        self.assertTrue(all(e["accepted"] for e in cand["evaluations"]))


def absorber_league():
    """B sells b0 to A for a0; A must also send its bench contract a5 to match salary, which B does not want for the
    next three seasons; C has room and would play him."""
    data = league()
    set_contract(data, "a5", [(SEASON, 15_750_000), ("2027-28", 16_000_000), ("2028-29", 16_500_000)])
    for v in data["player_asset_valuations"]:
        if v["player_id"] == "b0":
            v.update(on_court_value=80, player_value=84)
        if v["player_id"] == "a0":
            v.update(player_value=86)
    return data


class RouteTests(unittest.TestCase):
    def two_team(self, data):
        report = tx.evaluate_trade(data, "B", "A", [{"kind": "player", "value": "b0"}],
                                   [{"kind": "player", "value": "a0"}, {"kind": "player", "value": "a5"}], date=DATE)
        return tx.candidate_from_decision(report)

    def test_near_miss_needs_a_legal_deal_without_hard_rejections(self):
        data = absorber_league()
        cand = self.two_team(data)
        self.assertEqual(cand["legality"]["status"], "legal")
        broken = deepcopy(cand)
        broken["evaluations"][0]["decision"] = "reject_pick_investment"
        self.assertFalse(mt.near_miss(data, broken))
        illegal = deepcopy(cand)
        illegal["legality"] = {"status": "illegal", "issues": ["x"]}
        self.assertFalse(mt.near_miss(data, illegal))

    def test_reroute_sends_the_unwanted_contract_to_a_team_with_room_for_picks(self):
        data = absorber_league()
        cand = self.two_team(data)
        short = mt._short_teams(cand, set())
        self.assertEqual(short[0][0], "b")  # B is the team most short: it does not want a5's three years
        config = tx.default_transaction_model_config()
        quick_b = lambda inc: tt.quick_net(data, "b", inc, [P("b0")], config)
        self.assertGreater(quick_b([P("a0")]) - quick_b([P("a0"), P("a5")]), 30.0)  # rerouting a5 fixes most of it
        # Both main teams also value their own player above the other's (step 1), so this small league's deal stays
        # short of the bounds; widen the quick screen to look at the route itself.
        with patch.object(tt, "PRESCREEN_TOLERANCE", 40.0):
            routes = mt.repair_routes(data, cand, config)
        reroutes = [r for r in routes if r["kind"] == "reroute"]
        self.assertTrue(reroutes, routes)
        route = reroutes[0]
        self.assertEqual(route["mover_id"], "a5")
        self.assertEqual(route["absorber_id"], "c")
        legs = {(l["from_team_id"], l["to_team_id"]): [a["value"] for a in l["assets"]] for l in route["legs"]}
        self.assertIn("a5", legs[("a", "c")])
        self.assertNotIn("a5", legs.get(("a", "b"), []))
        self.assertIn(("c", "a"), legs)  # the absorber sends something back (every team sends and receives)

    def test_reasons_name_every_team(self):
        data = absorber_league()
        route = {"kind": "reroute", "mover_id": "a5", "absorber_id": "c", "payer_id": "a", "short_id": "b",
                 "picks": [{"id": "a2029r2", "round": 2}], "legs": [
                     {"from_team_id": "b", "to_team_id": "a", "assets": [{"kind": "player", "value": "b0"}]},
                     {"from_team_id": "a", "to_team_id": "b", "assets": [{"kind": "player", "value": "a0"}]},
                     {"from_team_id": "a", "to_team_id": "c", "assets": [{"kind": "player", "value": "a5"}]},
                     {"from_team_id": "c", "to_team_id": "a", "assets": [{"kind": "pick", "value": "c2029r2"}]}]}
        why = mt.multi_team_reasons(data, route, {"text": "A (contending) targeted b0; B moved him.", "target_key": "x"})
        self.assertEqual(why["target_key"], "three_team_absorber")
        for word in ("A (contending) targeted b0", "C (", "1 second-round pick", "$15.8M"):
            self.assertIn(word, why["text"])
        self.assertIn("C", why["teams"])

    def test_human_team_is_never_an_ai_absorber_but_gets_an_offer(self):
        data = absorber_league()
        data["_human_team_ids"] = ["c"]
        cand = self.two_team(data)
        config = tx.default_transaction_model_config()
        self.assertFalse([r for r in mt.repair_routes(data, cand, config) if r["absorber_id"] == "c"])
        offers = mt.user_absorber_offers(data, [{"candidate": cand, "trade_reasons": {"text": "x"}}], seed=1,
                                         date=DATE, config=config)
        for offer in offers:
            self.assertIn("c", tx.trade_team_ids(offer))
            self.assertEqual(offer["offer_context"]["kind"], "absorb_salary_for_picks")
            self.assertTrue(offer["offer_context"]["payment_pick_ids"])
            ai = [e for e in offer["evaluations"] if e["perspective_team_id"] != "c"]
            self.assertTrue(all(e["accepted"] for e in ai))


class ApplyTests(unittest.TestCase):
    def test_an_ai_only_deal_with_a_joiner_is_rechecked_under_its_own_rule(self):
        data = league()
        cand = multi_candidate({"a": (-5.0, 1.0), "b": (8.0, 1.0), "c": (3.0, 1.0)})
        marked = mt.mark_multi_team_accepted(cand, {"c"})
        self.assertEqual(marked["ai_acceptance_override"]["status"], "accepted_by_bounded_ai_discretion")
        # A forged joiner list cannot make a short joiner acceptable.
        forged = mt.mark_multi_team_accepted(multi_candidate({"a": (5.0, 1.0), "b": (8.0, 1.0), "c": (-3.0, 1.0)}), {"c"})
        fresh = multi_candidate({"a": (5.0, 1.0), "b": (8.0, 1.0), "c": (-3.0, 1.0)})
        self.assertFalse(mt.bounded_multi_team_accept(data, fresh, set(forged["joiner_team_ids"])))


if __name__ == "__main__":
    unittest.main()
