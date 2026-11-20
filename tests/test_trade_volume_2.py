"""TRADE-VOLUME-2: trade timing that follows the real calendar, market targets, more draft-night trades
(docs/agents/tasks/trade-volume-2.md)."""
import statistics
import unittest
from unittest.mock import patch

from nba_gm_data import play, save as sv
from nba_gm_data import trade_calendar as cal
from nba_gm_data import trade_targets as tt
from nba_gm_data import transactions as tx

from test_trade_targets import league, row


class CalendarTests(unittest.TestCase):
    def test_free_agency_days_follow_the_real_july_opening(self):
        days = {d: [cal.free_agency_trade_slots(f"2027-07-{d:02}", seed, d) for seed in range(400)] for d in range(1, 6)}
        means = {d: statistics.mean(v) for d, v in days.items()}
        self.assertGreater(means[1], means[3] * 1.8)  # the opening days are the busiest
        self.assertTrue(7.5 < sum(means.values()) < 10.5)  # about 9 over the five days (real Julys 8 and 16)
        self.assertLessEqual(max(max(v) for v in days.values()), cal.FREE_AGENCY_TRADES_PER_DAY)
        self.assertGreater(max(days[1]), 2)  # more than the old two-a-day cap
        self.assertEqual(cal.free_agency_trade_slots("2027-06-30", 17, 1), 0)
        self.assertEqual(cal.free_agency_trade_slots("2027-07-01", 17, 1), cal.free_agency_trade_slots("2027-07-01", 17, 1))

    def test_late_summer_and_september_have_a_few_trades(self):
        late = [cal.late_summer_trade_slots(2027, seed) for seed in range(400)]
        self.assertTrue(3.5 < statistics.mean(late) < 5.5)
        self.assertLessEqual(max(late), cal.LATE_SUMMER_TRADES_MAX)
        september = [cal.market_day(f"2027-09-{d:02}", seed, 2027, "2028-02-05")["slots"]
                     for seed in range(100) for d in range(1, 31)]
        self.assertTrue(1.0 < statistics.mean(september) * 30 < 2.8)  # real Septembers: 1 and 2 trades
        day = cal.market_day("2027-09-10", 3, 2027, "2028-02-05")
        self.assertEqual(day["offer_slots"], 0)
        self.assertEqual(day["review"], bool(day["slots"]))
        self.assertEqual(cal.market_day("2027-08-10", 3, 2027, "2028-02-05"), {"review": False, "slots": 0})

    def test_december_trades_come_after_december_15(self):
        early = late = 0
        for seed in range(150):
            early += sum(cal.market_day(f"2026-12-{d:02}", seed, 2026, "2027-02-05")["slots"] for d in range(1, 15))
            late += sum(cal.market_day(f"2026-12-{d:02}", seed, 2026, "2027-02-05")["slots"] for d in range(15, 32))
        self.assertGreater(late, early * 3)

    def test_trades_are_legal_in_training_camp(self):
        self.assertIn("trades", sv.legal_actions_for_phase("training_camp"))
        self.assertIn("trades", sv.legal_actions_for_date("2027-09-15"))

    def test_draft_night_allows_the_real_number_of_trades(self):
        self.assertGreaterEqual(play.DRAFT_TRADES_PER_DRAFT, 8)  # real: 8 (2025) and 11 (2026) on draft nights
        self.assertGreaterEqual(play.DRAFT_TRADES_PER_SEGMENT * len(play.DRAFT_TRADE_SEGMENTS),
                                play.DRAFT_TRADES_PER_DRAFT)


class MarketTargetTests(unittest.TestCase):
    def test_contender_also_looks_for_proven_players_from_sellers_and_a_backup(self):
        targets = tt.team_trade_targets(league("peak", firsts=0), "x")
        keys = [t["key"] for t in targets]
        self.assertIn("seller_veteran", keys)
        self.assertIn("backup", keys)
        veteran = next(t for t in targets if t["key"] == "seller_veteran")
        self.assertTrue(veteran["filters"]["seller_reason_required"])
        self.assertEqual(veteran["filters"]["seller_stances"], {"rebuild", "retool"})
        backup = next(t for t in targets if t["key"] == "backup")
        self.assertTrue(backup["filters"]["seller_reason_required"])
        self.assertLessEqual(backup["filters"]["max_salary"], 15e6)
        for target in targets:
            self.assertNotIn("_", target["reason"])

    def test_rebuilding_team_does_not_buy_veterans(self):
        keys = [t["key"] for t in tt.team_trade_targets(league("rebuilding"), "x")]
        self.assertNotIn("seller_veteran", keys)
        self.assertNotIn("backup", keys)

    def test_backup_must_be_a_real_upgrade_on_the_current_backup(self):
        canonical = league("peak", firsts=0)
        backup = next(t for t in tt.team_trade_targets(canonical, "x") if t["key"] == "backup")
        bucket = next(iter(backup["filters"]["buckets"]))
        group = sorted((r["on_court"] for r in tt._team_rows(canonical, "x") if r["bucket"] == bucket), reverse=True)
        current_backup = group[tt.SLOT_DEPTH[bucket] - 1]
        self.assertGreaterEqual(backup["filters"]["min_on_court"], current_backup + tt.BACKUP_UPGRADE)

    def test_quick_screen_allows_draft_spending_for_measured_depth_like_the_check(self):
        canonical = league("peak", firsts=0, extra_rows=[row("z1", "y", bucket="big", on_court=66.0, minutes=14.0)])
        target = tt.player_rows(canonical)["z1"]
        pairing = {"row": target, "buyer_id": "x", "buyer_minutes": 14.0}
        gain = tt.backup_gain(canonical, "x", target)
        self.assertGreaterEqual(gain, 10.0)
        pick = [{"kind": "pick", "id": "p"}]
        with patch.object(tx, "premium_return_issue", return_value=None), \
             patch.object(tx, "package_value_for_team", return_value=8.0 + 0.6 * gain - 0.5):
            self.assertTrue(tt.package_fits_rules(canonical, pairing, pick))
        with patch.object(tx, "premium_return_issue", return_value=None), \
             patch.object(tx, "package_value_for_team", return_value=8.0 + 0.6 * gain + 0.5):
            self.assertFalse(tt.package_fits_rules(canonical, pairing, pick))


class RebuildingVeteranSigningTests(unittest.TestCase):
    def test_rebuilding_team_does_not_pay_a_veteran_free_agent_above_the_mid_level(self):
        from nba_gm_data import payroll_plan as pp
        from test_trade_volume import SEASON, league, save_for
        data = league(payroll_a=120_000_000)  # lots of cap room: the old rule (room below the tax) allows anything
        butler = dict(add_salary=36_000_000, minutes=30.0, kind="free_agency", age=38)
        check = pp.payroll_check(data, save_for("2027-07-02", "rebuilding"), "a", SEASON, **butler)
        self.assertFalse(check["ok"])
        self.assertEqual(check["reason"], "rebuilding_team_does_not_pay_veterans")
        self.assertIn("mid-level", pp.plain_words(check))
        cheap = dict(butler, add_salary=pp.veteran_price(SEASON) - 1)
        self.assertTrue(pp.payroll_check(data, save_for("2027-07-02", "rebuilding"), "a", SEASON, **cheap)["ok"])
        self.assertTrue(pp.payroll_check(data, save_for("2027-07-02", "rebuilding"), "a", SEASON,
                                         **dict(butler, age=26))["ok"], "young players are what a rebuild buys")
        self.assertTrue(pp.payroll_check(data, save_for("2027-07-02", "peak"), "a", SEASON, **butler)["ok"])
        self.assertTrue(pp.payroll_check(data, save_for("2027-07-02", "rebuilding"), "a", SEASON,
                                         **dict(butler, kind="re_signing"))["ok"], "its own players are not affected")
        self.assertGreater(pp.veteran_price("2028-29"), pp.veteran_price(SEASON))


class SummerMarketTests(unittest.TestCase):
    def candidate(self, pid, teams=("a", "b"), accepted=True):
        return {"accepted_by_all": accepted, "legality": {"status": "legal"},
                "proposal": {"id": pid, "from_team_id": teams[0], "to_team_id": teams[1]}}

    def test_late_summer_market_applies_ai_deals_up_to_its_slots_and_never_the_users(self):
        saved = {"meta": {"user_team_id": "human", "seed": 17}, "state": {"current_date": "2027-08-01"}}
        proposals = [self.candidate("p1", ("a", "human")), self.candidate("p2"), self.candidate("p3", ("c", "d"), False),
                     self.candidate("p4", ("c", "d")), self.candidate("p5", ("e", "f"))]
        applied = []
        with patch("nba_gm_data.trade_calendar.late_summer_trade_slots", return_value=2), \
             patch.object(tx, "simulate_ai_trades", return_value={"proposals": proposals}) as search, \
             patch.object(play, "canonical_with_save", return_value={}), \
             patch.object(play, "with_transaction_context", side_effect=lambda c: c), \
             patch.object(play, "apply_trade_to_state",
                          side_effect=lambda s, pid, **k: applied.append(pid) or {"status": "applied"}):
            self.assertEqual(play.run_late_summer_ai_trades({}, saved, 17, 2027), 2)
        self.assertEqual(applied, ["p2", "p4"])
        self.assertEqual(search.call_args.kwargs["limit"], 5)

    def test_no_late_summer_search_without_slots(self):
        with patch("nba_gm_data.trade_calendar.late_summer_trade_slots", return_value=0), \
             patch.object(tx, "simulate_ai_trades") as search:
            self.assertEqual(play.run_late_summer_ai_trades({}, {"state": {}}, 17, 2027), 0)
        search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
