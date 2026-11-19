"""Trade 2b: rebuilding teams and veterans, luxury-tax value and salary dumps, young starters, phase labels that follow
the season, draft-night trade-up prices (docs/agents/tasks/trade-2b-followups.md)."""
from copy import deepcopy
import math
from types import SimpleNamespace as Row
import unittest

from nba_gm_data import play
from nba_gm_data import team_planning as tp
from nba_gm_data import trade_ownership as own
from nba_gm_data import trade_targets as tt
from nba_gm_data import trade_tax as tax
from nba_gm_data import transactions as tx

from test_multi_team_trades import fixture


class VeteranTimelineTests(unittest.TestCase):
    def test_contenders_value_veterans_fully(self):
        for age in (24, 29, 33):
            self.assertEqual(tx.veteran_present_factor({"contend_distance": 0.0}, {"age": age}), 1.0)

    def test_deep_rebuild_discounts_veterans_by_age(self):
        far = {"contend_distance": 1.0}
        self.assertEqual(tx.veteran_present_factor(far, {"age": 25}), 1.0)
        self.assertAlmostEqual(tx.veteran_present_factor(far, {"age": 29}), 0.775, places=3)
        self.assertAlmostEqual(tx.veteran_present_factor(far, {"age": 30}), 0.70, places=3)
        self.assertAlmostEqual(tx.veteran_present_factor(far, {"age": 35}), 0.70, places=3)

    def test_discount_grows_smoothly_with_distance(self):
        factors = [tx.veteran_present_factor({"contend_distance": d}, {"age": 31}) for d in (0, .25, .5, .75, 1)]
        self.assertEqual(factors, sorted(factors, reverse=True))
        self.assertTrue(all(a - b < 0.12 for a, b in zip(factors, factors[1:])))  # no cliff

    def test_both_sides_use_the_discount_and_the_breakdown_matches(self):
        data = tx.with_transaction_context(fixture())
        for state in data["team_strategic_states"]:
            state["contend_distance"] = 1.0 if state["team_id"] == "b" else 0.0
        for player in data["players"]:
            player["age"] = 31
        asset = [{"kind": "player", "id": "a1"}]
        before = tx.package_value_for_team({**data, "team_strategic_states": [
            dict(s, contend_distance=0.0) for s in data["team_strategic_states"]]}, asset, "b")
        after = tx.package_value_for_team(data, asset, "b")
        self.assertLess(after, before)  # a far-off rebuilder pays less for a veteran
        own_asset = [{"kind": "player", "id": "b1"}]
        self.assertAlmostEqual(tx.package_value_breakdown(data, own_asset, "b")["total"],
                               tx.package_value_for_team(data, own_asset, "b"), places=1)

    def test_human_team_view_is_unchanged(self):
        data = tx.with_transaction_context(fixture())
        for state in data["team_strategic_states"]:
            state["contend_distance"] = 1.0
        for player in data["players"]:
            player["age"] = 31
        asset = [{"kind": "player", "id": "a1"}]
        human = {**data, "_human_team_ids": ["b"]}
        flat = {**human, "team_strategic_states": [dict(s, contend_distance=0.0) for s in data["team_strategic_states"]]}
        self.assertEqual(tx.package_value_for_team(human, asset, "b"), tx.package_value_for_team(flat, asset, "b"))


class LuxuryTaxTests(unittest.TestCase):
    def setUp(self):
        data = fixture()
        for contract in data["contracts"]:
            if contract["team_id"] == "a":
                contract["seasons"][0]["salary"] = 17_500_000  # team A: 13 x $17.5M = $227.5M, over the $207.4M line
        self.data = tx.with_transaction_context(data)

    def test_bill_uses_the_real_brackets(self):
        line = tx.cap_lines_for_season("2026-27")["tax_line"]
        bracket = line * tax.BRACKET_SHARE_OF_TAX_LINE
        self.assertEqual(tax.luxury_tax_bill(line - 1, "2026-27"), 0.0)
        self.assertAlmostEqual(tax.luxury_tax_bill(line + bracket, "2026-27"), 1.5 * bracket)
        self.assertAlmostEqual(tax.luxury_tax_bill(line + 5 * bracket, "2026-27"),
                               (1.5 + 1.75 + 2.5 + 3.25 + 3.75) * bracket)

    def test_open_seasons_follow_the_calendar(self):
        self.assertEqual(tax.tax_seasons({"meta": {"current_date": "2027-01-31"}})[0], ("2026-27", 1.0))
        self.assertEqual(tax.tax_seasons({"meta": {"current_date": "2026-11-01"}})[0], ("2026-27", 1.0))
        self.assertEqual(tax.tax_seasons({"meta": {"current_date": "2027-06-25"}})[0], ("2027-28", 1.0))

    def test_shedding_salary_over_the_line_is_value_and_taking_it_over_is_a_cost(self):
        out = [{"kind": "player", "id": "a1"}]
        saving = tax.tax_value(self.data, "a", [], out)
        self.assertGreater(saving, 10.0)
        self.assertLessEqual(saving, tax.TAX_VALUE_CAP)
        self.assertEqual(tax.tax_value(self.data, "b", out, []), 0.0)  # B stays under the line
        heavy = [{"kind": "player", "id": "a1"}, {"kind": "player", "id": "a2"}]
        self.assertGreater(tax.tax_value(self.data, "a", [], heavy), saving)  # more saved, saturating
        self.assertLess(tax.tax_value(self.data, "a", heavy, []), 0.0)

    def test_human_team_gets_no_tax_term(self):
        data = {**self.data, "_human_team_ids": ["a"]}
        self.assertEqual(tax.tax_value(data, "a", [], [{"kind": "player", "id": "a1"}]), 0.0)

    def test_acceptance_check_counts_the_tax_saved(self):
        report = tx.evaluate_trade(self.data, "A", "B", [{"kind": "player", "value": "a1"}], [], date="2027-01-31",
                                   context_ready=True)
        a_eval = next(e for e in report["evaluations"] if e["perspective_team_id"] == "a")
        self.assertIn("Luxury tax", a_eval["notes"])
        saving = tax.tax_value(self.data, "a", [], [{"kind": "player", "id": "a1"}])
        self.assertGreaterEqual(a_eval["strategic_adjustment"], saving - 15.0)

    def test_young_starters_are_never_moved_for_tax_savings(self):
        data = deepcopy(self.data)
        player = tx.player_by_id(data, "a1")
        player.update(age=22, minutes_projection=32)
        self.assertEqual(tax.tax_value(data, "a", [], [{"kind": "player", "id": "a1"}]), 0.0)
        # ... but the cost of taking salary over the line still counts
        self.assertLess(tax.tax_value(data, "a", [{"kind": "player", "id": "b1"}] * 1, []), 0.0)

    def test_salary_dumps_go_from_the_tax_team_to_teams_with_room(self):
        data = tx.trade_search_context(tx.with_spatial_fit_context(self.data))
        offers = tt.salary_dump_offers(data, ["a", "b", "c"], set(), tx.default_transaction_model_config())
        self.assertTrue(offers)
        for offer in offers:
            self.assertEqual(offer["seller_id"], "a")
            self.assertIn(offer["buyer_id"], {"b", "c"})
            self.assertGreater(offer["saved"], 0)
            self.assertEqual(offer["packages"][0], [{"kind": "player", "id": offer["row"]["id"]}])  # cheapest first
        words = tt.dump_reasons(data, offers[0], offers[0]["packages"][0])
        self.assertIn("luxury tax", words["text"])
        self.assertEqual(words["target_key"], "salary_dump")

    def test_no_dumps_for_the_human_team(self):
        data = tx.trade_search_context(tx.with_spatial_fit_context({**self.data, "_human_team_ids": ["a"]}))
        self.assertEqual(tt.salary_dump_offers(data, ["a", "b", "c"], set(), tx.default_transaction_model_config()), [])


class YoungStarterTests(unittest.TestCase):
    def test_money_reasons_alone_do_not_expose_a_young_starter(self):
        self.assertEqual(tt.exposing_reasons(["over_tax_line"]), [])
        self.assertEqual(tt.exposing_reasons(["over_tax_line", "gm_listed"]), ["gm_listed"])

    def test_young_starter_premium_is_not_scaled_down_by_the_tax(self):
        raw = fixture()
        for contract in raw["contracts"]:
            if contract["team_id"] == "a":
                contract["seasons"][0]["salary"] = 17_500_000
        data = tx.with_transaction_context(raw)
        player = tx.player_by_id(data, "a1")
        player.update(age=22, minutes_projection=32)
        rates = own._premium_rates(data, player, "a", None, None)
        self.assertNotIn("over_tax_line", rates["move_reasons"])
        self.assertGreaterEqual(rates["attachment"], own.ATTACHMENT_BASE + own.KEEP_REASON_RATES["young_starter"])
        veteran = tx.player_by_id(data, "a2")
        veteran.update(age=30, minutes_projection=32)
        self.assertIn("over_tax_line", own._premium_rates(data, veteran, "a", None, None)["move_reasons"])


class PhaseLabelTests(unittest.TestCase):
    def league(self, records=None, plans=None, date="2027-02-01"):
        data = {"players": [], "teams": [], "meta": {"current_date": date}, "save_team_records": records or {},
                "team_plans": plans or {}}
        states, values = [], []
        for i in range(20):
            tid = f"t{i}"
            data["teams"].append({"id": tid})
            states.append(Row(team_id=tid, contention_ceiling=70 - i * 0.6))
            for j in range(5):
                pid = f"{tid}p{j}"
                data["players"].append({"id": pid, "team_id": tid, "age": 27})
                values.append(Row(player_id=pid, team_id=tid, on_court_value=80 - i * 1.5, development_upside=0,
                                  health_risk=0))
        return data, states, values

    def records(self, special):
        out = {}
        for i in range(20):
            wins = 30 - i if f"t{i}" not in special else special[f"t{i}"]
            margin = (wins - 23.5) * 0.6
            out[f"t{i}"] = {"wins": wins, "losses": 47 - wins, "points_for": 47 * (110 + margin / 2),
                            "points_against": 47 * (110 - margin / 2)}
        return out

    def test_a_winning_record_lifts_a_team_out_of_the_rebuild(self):
        data, states, values = self.league()
        self.assertEqual(tp.window_assessments(data, states, values)["t19"]["window_phase"], "rebuilding")
        data, states, values = self.league(self.records({"t19": 31}))  # worst roster, 31-16
        row = tp.window_assessments(data, states, values)["t19"]
        self.assertNotEqual(row["window_phase"], "rebuilding")
        self.assertLess(row["league_rank"], 13)

    def test_a_losing_record_drops_a_team(self):
        data, states, values = self.league(self.records({"t5": 8}))
        quiet, _, _ = self.league()
        before = tp.window_assessments(quiet, states, values)["t5"]
        after = tp.window_assessments(data, states, values)["t5"]
        self.assertGreater(after["league_rank"], before["league_rank"])
        self.assertGreater(after["contend_distance"], before["contend_distance"])

    def test_summer_records_count_little(self):
        data, states, values = self.league(self.records({"t19": 31}), date="2027-07-15")
        row = tp.window_assessments(data, states, values)["t19"]
        self.assertLessEqual(row["record_weight"], tp.OFFSEASON_RECORD_WEIGHT)

    def test_labels_have_some_stability(self):
        data, states, values = self.league()
        fresh = tp.window_assessments(data, states, values)
        team = next(t for t, r in fresh.items() if r["window_phase"] == "rebuilding")
        # A team labelled "entering" last review stays so while the new label is within the margin
        plans = {team: {"window_phase": "entering"}}
        data, states, values = self.league(plans=plans)
        first_rebuilder = min((t for t, r in fresh.items() if r["window_phase"] == "rebuilding"),
                              key=lambda t: fresh[t]["league_rank"])
        sticky = tp.window_assessments({**data, "team_plans": {first_rebuilder: {"window_phase": "entering"}}},
                                       states, values)
        self.assertEqual(sticky[first_rebuilder]["window_phase"], "entering")
        far = max(fresh, key=lambda t: fresh[t]["league_rank"])
        moved = tp.window_assessments({**data, "team_plans": {far: {"window_phase": "peak"}}}, states, values)
        self.assertNotEqual(moved[far]["window_phase"], "peak")

    def test_distance_is_zero_for_contenders_and_grows_below_the_top_four(self):
        data, states, values = self.league()
        rows = tp.window_assessments(data, states, values)
        self.assertEqual(rows["t0"]["contend_distance"], 0.0)
        distances = [rows[f"t{i}"]["contend_distance"] for i in range(20)]
        self.assertEqual(distances, sorted(distances))
        self.assertEqual(distances[-1], 1.0)


class DraftNightPriceTests(unittest.TestCase):
    @staticmethod
    def pick(pid, round_no, slot, season="2027"):
        return {"id": pid, "round": round_no, "overall_pick": slot, "current_owner_team_id": "x", "season": season,
                "_active_season": "2026-27"}

    def test_a_short_slide_costs_seconds_not_a_future_first(self):
        value = lambda p: tx.pick_asset_value(p, "neutral")
        target, lower = self.pick("t", 1, 16), self.pick("l", 1, 21)
        seconds = [self.pick(f"s{i}", 2, 35 + i) for i in range(3)]
        firsts = [self.pick("f", 1, None, season="2029") | {"projected_pick_slot": 15}]
        with unittest.mock.patch.object(play, "pick_asset_value", side_effect=lambda p, phase: value(p)):
            offer = play.draft_trade_mid_first_offer([{"kind": "pick", "value": "l"}], value(target), value(lower),
                                                     firsts, sorted(seconds, key=value, reverse=True), True)
        ids = [a["value"] for a in offer]
        self.assertIn("l", ids)
        self.assertNotIn("f", ids)
        self.assertTrue(any(i.startswith("s") for i in ids))
        total = sum(value(p) for p in [lower, *seconds] if p["id"] in ids)
        self.assertGreaterEqual(total, value(target) * play.MID_FIRST_REQUIRED_FACTOR)

    def test_no_lower_pick_uses_the_cheapest_first_that_covers_it(self):
        value = lambda p: tx.pick_asset_value(p, "neutral")
        target = self.pick("t", 1, 24)
        cheap = self.pick("f1", 1, None, season="2029") | {"projected_pick_slot": 22}
        dear = self.pick("f2", 1, None, season="2029") | {"projected_pick_slot": 8}
        with unittest.mock.patch.object(play, "pick_asset_value", side_effect=lambda p, phase: value(p)):
            offer = play.draft_trade_mid_first_offer([], value(target), 0.0, [dear, cheap], [], False)
        self.assertEqual([a["value"] for a in offer][:1], ["f1"])


if __name__ == "__main__":
    unittest.main()
