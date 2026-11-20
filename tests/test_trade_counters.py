"""TRADE-DEADLINE: salary filler a buyer would move, and counter-offers for near misses (trade step 3)
(docs/agents/tasks/trade-deadline-counters.md)."""
import unittest
from unittest.mock import patch

from nba_gm_data import trade_counters as tc
from nba_gm_data import trade_targets as tt
from nba_gm_data import transactions as tx

from test_trade_targets import league, row


def player(pid):
    return {"kind": "player", "id": pid}


def pick(pid):
    return {"kind": "pick", "id": pid}


class FillerTests(unittest.TestCase):
    def canonical(self, **kwargs):
        extra = [
            row("bad", "x", age=31.0, minutes=8.0, salary=18e6, years=3, surplus=-20.0, on_court=50.0),
            row("hurt", "x", age=29.0, minutes=26.0, salary=22e6, years=2, on_court=64.0),
            row("expiring", "x", age=30.0, minutes=9.0, salary=6e6, years=1, on_court=48.0),
            row("minimum", "x", age=30.0, minutes=4.0, salary=1.2e6, years=1, on_court=44.0),
            row("kid", "x", age=21.0, minutes=26.0, salary=5e6, years=3, development=14.0, on_court=62.0),
            row("corevet", "x", age=33.0, minutes=8.0, salary=30e6, years=2, surplus=-25.0, on_court=60.0),
        ]
        canonical = league("peak", extra_rows=extra, core=("corevet",), **kwargs)
        canonical["player_health_states"] = [{"player_id": "hurt", "availability_status": "out",
                                              "return_date": "2027-03-15"}]
        return canonical

    def filler(self, canonical, reasons):
        with patch.object(tt, "team_sell_reasons", return_value=reasons), \
                patch("nba_gm_data.team_planning.core_commitment", return_value=False):
            return tt.salary_filler(canonical, "x")

    def test_buyer_moves_unwanted_salary_not_its_rotation(self):
        canonical = self.canonical()
        found = self.filler(canonical, {"bad": ["negative_contract_value"], "corevet": ["negative_contract_value"]})
        self.assertEqual(found.get("bad"), "negative_contract_value")
        self.assertEqual(found.get("hurt"), "long_term_injury")  # out for about seven more weeks
        self.assertEqual(found.get("expiring"), "expiring_bench_salary")
        self.assertNotIn("corevet", found)  # never a core player
        self.assertNotIn("kid", found)      # never a young piece the team builds around
        self.assertNotIn("minimum", found)  # a minimum contract matches no salary
        self.assertNotIn("x0", found)       # a healthy rotation player with no reason to move is not filler
        self.assertLessEqual(len(found), tt.FILLER_PER_BUYER)

    def test_recent_draft_pick_is_never_filler(self):
        canonical = self.canonical()
        rows = tt.player_rows(canonical)
        rows["expiring"]["player"]["draft_year"] = 2025
        with patch.object(tx, "season_start_from_label", return_value=2026):
            found = self.filler(canonical, {})
        self.assertNotIn("expiring", found)


class QuickScreenTests(unittest.TestCase):
    def limit(self, minutes, out_salary, in_salary, tax=0.0):
        with patch.object(tt, "backup_gain", return_value=0.0), \
                patch.object(tx, "package_salary", side_effect=[out_salary, in_salary]), \
                patch("nba_gm_data.trade_tax.tax_value", return_value=tax):
            return tt.quick_capital_limit({}, "x", {}, minutes, [], [])

    def test_quick_screen_allows_what_the_full_check_allows(self):
        from nba_gm_data.trade_roster import ROTATION_ROLE_PICK_ALLOWANCE
        self.assertEqual(self.limit(10.0, 5e6, 5e6), 8.0)  # a bench player: the base only
        self.assertAlmostEqual(self.limit(20.0, 5e6, 5e6), 8.0 + ROTATION_ROLE_PICK_ALLOWANCE * 0.5)
        self.assertAlmostEqual(self.limit(10.0, 16e6, 6e6), 8.0 + 20.0)  # $10M of salary shed: 2 per $1M
        self.assertEqual(self.limit(10.0, 9e6, 6e6), 8.0)  # under $5M of relief earns nothing
        self.assertEqual(self.limit(10.0, 5e6, 5e6, tax=12.0), 20.0)


class ChooseCounterTests(unittest.TestCase):
    """Quick prices are replaced by a value table: what each asset is worth to the asking team ('y', the seller)."""

    def setUp(self):
        extra = [
            row("ivey", "x", age=24.0, minutes=14.0, on_court=63.0, development=10.0, salary=9e6),
            row("young", "x", age=21.0, minutes=8.0, on_court=55.0, development=12.0, salary=3e6),
            row("filler", "x", age=31.0, minutes=6.0, on_court=48.0, salary=12e6, years=1),
        ]
        self.canonical = league("peak", extra_rows=extra)
        self.worth = {"ivey": 13.0, "young": 9.0, "filler": 2.0, "p2": 6.0, "p1": 30.0, "y0": 0.0}
        self.base_gap = -10.0  # the seller is 10 short of its price with the original package

    def net(self, canonical, team_id, incoming, outgoing, config):
        gained = sum(self.worth.get(a["id"], 0.0) for a in incoming)
        lost = sum(self.worth.get(a["id"], 0.0) for a in outgoing)
        if team_id == "y":  # the asking seller
            return self.base_gap + gained - 2.0  # the original package (the filler) is worth 2 to it
        return 6.0 - lost * 0.5

    def choose(self, stance="contend", targets=None, giving_is_ai=True):
        with patch.object(tc, "_net", side_effect=self.net), \
                patch.object(tc, "_unavailable", return_value=set()), \
                patch.object(tc, "_stance", side_effect=lambda c, t: stance if t == "y" else "contend"), \
                patch.object(tt, "team_trade_targets", return_value=targets or []), \
                patch.object(tt, "team_sell_reasons", return_value={}), \
                patch.object(tx, "tradeable_picks_for_team", return_value=[{"id": "p2"}, {"id": "p1"}]), \
                patch.object(tx, "goat_exception_player", return_value=False), \
                patch("nba_gm_data.team_planning.core_commitment", return_value=False):
            return tc.choose_counters(self.canonical, "y", "x", [player("y0")], [player("filler")], {},
                                      giving_is_ai=giving_is_ai, fixed={("player", "y0")})

    def test_seller_asks_for_its_target_first(self):
        target = {"id": "y:prospect", "key": "prospect", "label": "a young player who would play",
                  "filters": {"age_max": 25.0, "min_development": 6.0}}
        counters = self.choose(targets=[target])
        self.assertTrue(counters)
        self.assertEqual(counters[0]["kind"], "target_player")
        self.assertIn("ivey", [a["id"] for a in counters[0]["giving_out"]])
        self.assertEqual(counters[0]["target_label"], target["label"])

    def test_without_a_target_a_rebuilder_asks_for_the_closest_pick_not_a_gouge(self):
        self.worth["young"] = 12.0
        counters = self.choose(stance="rebuild")
        self.assertTrue(counters)
        self.assertEqual(counters[0]["kind"], "young_player")  # a second (6) is not enough; the first (25) is too much
        for counter in counters:
            self.assertLessEqual(counter["asking_net"], tc.COUNTER_OVERSHOOT)
            self.assertGreaterEqual(counter["asking_net"], 0.0)

    def test_overshoot_bound(self):
        self.base_gap = -4.0  # now a second closes it (6 - 4 = +2); the first would leave the seller +21
        counters = self.choose(stance="rebuild")
        self.assertEqual(counters[0]["kind"], "pick")
        self.assertIn(pick("p2"), counters[0]["giving_out"])
        self.assertNotIn(pick("p1"), [a for c in counters for a in c["giving_out"]])

    def test_ai_giving_side_must_stay_inside_the_bounded_negotiation(self):
        self.worth["young"] = 9.0
        self.base_gap = -8.0
        with patch.object(self, "net", side_effect=lambda c, t, i, o, cfg: (
                -8.0 + sum(self.worth.get(a["id"], 0.0) for a in i) - 2.0) if t == "y" else -20.0):
            self.assertEqual(self.choose(stance="rebuild"), [])
            self.assertTrue(self.choose(stance="rebuild", giving_is_ai=False))  # the user decides for himself

    def test_tier_order_follows_phase(self):
        self.assertEqual(tc.tier_order("rebuild")[0], "pick")
        self.assertEqual(tc.tier_order("contend")[0], "keep_own")
        self.assertIn("salary_relief", tc.tier_order("retool"))


class DescribeTests(unittest.TestCase):
    def test_counter_text_is_plain_words(self):
        canonical = league("peak", extra_rows=[row("ivey", "x", age=24.0)])
        with patch.object(tx, "team_by_id", side_effect=lambda c, t: {"id": t, "abbrev": t.upper()}), \
                patch.object(tx, "player_by_id", side_effect=lambda c, p: {"id": p, "name": {"ivey": "Jaden Ivey"}.get(p, "Kevin Huerter")}), \
                patch.object(tt, "team_sell_reasons", return_value={"ivey": ["blocked_prospect"]}):
            step = tc.describe(canonical, "y", "x", [player("y0")], [player("x9")],
                               {"kind": "target_player", "asking_out": [player("y0")],
                                "giving_out": [player("ivey")], "target_label": "a young player who would play"})
        self.assertEqual(step["text"], "Y asked for Jaden Ivey (a young player who would play) instead of Kevin Huerter; "
                                       "X agreed: Jaden Ivey was a young player blocked from minutes.")
        self.assertNotIn("_", step["text"])
        self.assertEqual([a["id"] for a in step["added"]], ["ivey"])


def evaluation(team, net, accepted, decision=None, reasons=()):
    return {"perspective_team_id": team, "net_value": net, "acceptance_threshold": 0.0, "accepted": accepted,
            "decision": decision or ("accept" if accepted else "reject"), "decision_reasons": list(reasons)}


def candidate(from_assets, to_assets, evaluations, status="legal"):
    return {"proposal": {"id": "p", "from_team_id": "y", "to_team_id": "x", "from_assets": from_assets,
                         "to_assets": to_assets},
            "legality": {"status": status}, "evaluations": evaluations}


class ShortSideTests(unittest.TestCase):
    def test_only_a_little_short_and_no_hard_rule(self):
        base = [player("y0")], [player("x5")]
        self.assertEqual(tc.short_side(candidate(*base, [evaluation("y", -10, False), evaluation("x", 5, True)]), set())[:2],
                         ("y", "x"))
        self.assertIsNone(tc.short_side(candidate(*base, [evaluation("y", -40, False), evaluation("x", 5, True)]), set()))
        self.assertIsNone(tc.short_side(candidate(*base, [evaluation("y", -5, False), evaluation("x", -5, False)]), set()))
        self.assertIsNone(tc.short_side(candidate(*base, [evaluation("y", -5, False, "reject_premium_return"),
                                                          evaluation("x", 5, True)]), set()))
        self.assertIsNone(tc.short_side(candidate(*base, [evaluation("y", -5, False, reasons=["Core commitment: x"]),
                                                          evaluation("x", 5, True)]), set()))
        self.assertIsNone(tc.short_side(candidate(*base, [evaluation("y", -5, False), evaluation("x", 5, True)],
                                                  status="illegal"), set()))
        # The user's team never asks; its own evaluation is never used.
        self.assertEqual(tc.short_side(candidate(*base, [evaluation("y", -5, False), evaluation("x", -50, False)]),
                                       {"x"})[:2], ("y", "x"))


class AiCounterTests(unittest.TestCase):
    def test_counter_deal_is_the_one_the_full_check_accepted_and_illegal_options_are_skipped(self):
        start = candidate([player("y0")], [player("x5")], [evaluation("y", -10, False), evaluation("x", 5, True)])
        options = [{"kind": "pick", "asking_out": [player("y0")], "giving_out": [player("x5"), pick("bad")],
                    "target_label": None},
                   {"kind": "pick", "asking_out": [player("y0")], "giving_out": [player("x5"), pick("p2")],
                    "target_label": None}]
        sent = []

        def decide(canonical, f, t, from_specs, to_specs, **kwargs):
            sent.append(to_specs)
            illegal = any(s["value"] == "bad" for s in to_specs)
            return candidate([player("y0")], [{"kind": s["kind"], "id": s["value"]} for s in to_specs],
                             [evaluation("y", 2, True), evaluation("x", 1, True)], status="illegal" if illegal else "legal")

        with patch.object(tc, "choose_counters", return_value=options), \
                patch.object(tc, "describe", return_value={"text": "Y asked for a pick as well; X agreed."}), \
                patch.object(tx, "evaluate_trade_decision", side_effect=decide), \
                patch.object(tx, "candidate_from_decision", side_effect=lambda r: r), \
                patch.object(tx, "ai_trade_candidate_accepted", side_effect=lambda c, r: r["legality"]["status"] == "legal"), \
                patch.object(tx, "team_by_id", side_effect=lambda c, t: {"id": t, "abbrev": t.upper()}):
            result = tc.ai_counter({"_human_team_ids": []}, start, seed=1, date="2027-02-05", config={})
        self.assertEqual(len(sent), 2)
        self.assertEqual(result["proposal"]["to_assets"], [player("x5"), pick("p2")])
        self.assertEqual(result["counter"]["rounds"], 1)
        self.assertEqual(result["counter"]["text"], "Y asked for a pick as well; X agreed.")

    def test_no_counter_when_nobody_is_close(self):
        start = candidate([player("y0")], [player("x5")], [evaluation("y", -30, False), evaluation("x", 5, True)])
        self.assertIsNone(tc.ai_counter({"_human_team_ids": []}, start, seed=1, date="2027-02-05", config={}))


class UserCounterTests(unittest.TestCase):
    def test_user_counter_is_the_evaluated_deal_the_partner_accepts(self):
        offer = candidate([player("y0")], [player("x5")], [evaluation("y", -6, False), evaluation("x", 0, False)])
        options = [{"kind": "target_player", "asking_out": [player("y0")], "giving_out": [player("x5"), player("x6")],
                    "target_label": "a young player who would play"}]
        evaluated = candidate([player("y0")], [player("x5"), player("x6")], [evaluation("y", 3, True), evaluation("x", -1, False)])
        with patch.object(tc, "choose_counters", return_value=options) as chosen, \
                patch.object(tc, "describe", return_value={"text": "Y asked for X6 (a young player who would play)."}), \
                patch.object(tx, "evaluate_trade", return_value=evaluated) as full, \
                patch.object(tx, "team_by_id", side_effect=lambda c, t: {"id": t, "abbrev": t.upper()}):
            result = tc.user_counter({"_human_team_ids": ["x"]}, offer, "x", seed=7, date="2027-01-10", config={})
        self.assertIs(result, evaluated)  # exactly the engine's evaluated deal: what Accept executes
        self.assertFalse(chosen.call_args.kwargs["giving_is_ai"])  # the user's own view is never used
        self.assertEqual(full.call_args.args[4], [{"kind": "player", "value": "x5"}, {"kind": "player", "value": "x6"}])
        self.assertTrue(result["counter"]["for_user"])

    def test_no_counter_when_the_partner_accepts_or_is_far_off(self):
        accepted = candidate([player("y0")], [player("x5")], [evaluation("y", 4, True), evaluation("x", 0, False)])
        self.assertIsNone(tc.user_counter({}, accepted, "x", seed=7, date="2027-01-10", config={}))
        far = candidate([player("y0")], [player("x5")], [evaluation("y", -40, False), evaluation("x", 0, False)])
        self.assertIsNone(tc.user_counter({}, far, "x", seed=7, date="2027-01-10", config={}))


class LateDeadlinePassTests(unittest.TestCase):
    def save(self, phase="regular_season"):
        return {"meta": {"user_team_id": "gsw"}, "state": {"phase": phase},
                "transaction_logs": [{"transaction_type": "trade", "date": "2027-02-05", "teams": ["a", "b"]},
                                     {"transaction_type": "trade", "date": "2027-02-05", "teams": ["c", "gsw"]},
                                     {"transaction_type": "trade", "date": "2027-02-04", "teams": ["d", "e"]}]}

    def run_pass(self, save, day="2027-02-05", slots=6, proposals=()):
        from nba_gm_data import save as sv
        calls = {}

        def search(active, start, end, **kwargs):
            calls["search"] = kwargs
            return {"proposals": list(proposals)}

        with patch("nba_gm_data.trade_calendar.market_day", return_value={"slots": slots}), \
                patch.object(sv, "canonical_with_save", return_value={}), \
                patch.object(sv, "human_controlled_team_ids", return_value={"gsw"}), \
                patch("nba_gm_data.transactions.simulate_ai_trades", side_effect=search), \
                patch("nba_gm_data.trade_review.MarketReview"), \
                patch.object(sv, "process_ai_actions_in_memory", return_value={"applied_count": len(proposals)}):
            applied = sv.late_deadline_trade_pass({}, save, day, 17)
        return applied, calls

    def test_runs_once_on_deadline_day_for_teams_that_traded(self):
        save = self.save()
        deal = {"accepted_by_all": True, "legality": {"status": "legal"},
                "proposal": {"id": "p", "from_team_id": "a", "to_team_id": "x",
                             "from_assets": [{"kind": "player", "id": "1"}], "to_assets": [{"kind": "player", "id": "2"}]}}
        applied, calls = self.run_pass(save, proposals=[deal])
        self.assertEqual(applied, 1)
        self.assertEqual(calls["search"]["focus_team_ids"], {"a", "b", "c"})  # never the human team
        self.assertEqual(calls["search"]["limit"], 6 - 2 + 2)  # the open slots plus spares
        self.assertEqual(calls["search"]["search_depth"], 2)
        self.assertTrue(any((a.get("payload") or {}).get("late_pass") for a in save["pending_ai_actions"]))
        self.assertEqual(self.run_pass(save, proposals=[deal]), (0, {}))  # once a day

    def test_not_on_other_days_or_when_the_slots_are_used(self):
        self.assertEqual(self.run_pass(self.save(), day="2027-02-04"), (0, {}))
        self.assertEqual(self.run_pass(self.save(phase="play_in")), (0, {}))
        self.assertEqual(self.run_pass(self.save(), slots=2), (0, {}))


if __name__ == "__main__":
    unittest.main()
