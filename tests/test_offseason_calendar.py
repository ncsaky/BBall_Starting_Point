"""FA-REAL slice 2: the offseason calendar and the one contract-season switch date (offseason_calendar)."""
from __future__ import annotations

import unittest

from nba_gm_data import cap_ledger as cl, play, save as sv
from nba_gm_data.offseason_calendar import (
    contract_season, draft_dates, lottery_date, offseason_dates, opening_night, rookie_option_deadline,
)


class RealCalendar(unittest.TestCase):
    def test_2026_dates_match_the_real_calendar(self):
        dates = offseason_dates(2026)
        self.assertEqual(dates["lottery"], "2026-05-10", "the lottery runs in May during the playoffs")
        self.assertEqual((dates["draft_round_one"], dates["draft_round_two"]), ("2026-06-23", "2026-06-24"))
        self.assertEqual(dates["decisions_deadline"], "2026-06-29", "options and qualifying offers")
        self.assertEqual(dates["market_opens"], "2026-06-30", "talks with other teams' free agents")
        self.assertEqual(dates["league_year"], "2026-07-01")
        self.assertEqual(dates["qualifying_offer_withdrawal"], "2026-07-13")
        self.assertEqual(dates["qualifying_offers_expire"], "2026-10-01")
        self.assertEqual(dates["rookie_option_deadline"], "2026-11-02", "October 31 was a Saturday")

    def test_the_offseason_opens_after_the_games_latest_finals_game(self):
        # The game's Finals start June 4 with games every other day: game 7 is June 16.
        self.assertEqual(sv.playoff_round_start_date(2027, "finals").isoformat(), "2027-06-04")
        self.assertEqual(offseason_dates(2027)["offseason_opens"], "2027-06-17")

    def test_later_seasons_compute_their_own_dates(self):
        self.assertEqual(lottery_date(2027).isoformat(), "2027-05-09")
        self.assertEqual([d.isoformat() for d in draft_dates(2028)], ["2028-06-27", "2028-06-28"])
        self.assertEqual(rookie_option_deadline(2027).isoformat(), "2027-11-01")
        self.assertEqual(rookie_option_deadline(2028).isoformat(), "2028-10-31")

    def test_roster_and_rookie_extension_deadline_is_the_day_before_opening_night(self):
        save = {"season_schedules": {"2027-28": {"games": [
            {"phase": "regular", "gameDate": "2027-10-19"}, {"phase": "regular", "gameDate": "2027-10-21"}]}}}
        self.assertEqual(opening_night(2027, save).isoformat(), "2027-10-19")
        self.assertEqual(offseason_dates(2027, save)["roster_deadline"], "2027-10-18")
        self.assertEqual(offseason_dates(2027, save)["rookie_extension_deadline"], "2027-10-18")
        # The generated schedules open October 21: the deadline is October 20 (October 19 in the real 2026 calendar,
        # whose opening night was October 20: the same rule).
        self.assertEqual(offseason_dates(2026)["roster_deadline"], "2026-10-20")


class Phases(unittest.TestCase):
    def test_offseason_phases_in_the_real_order(self):
        expected = {
            "2027-05-09": "playoffs", "2027-06-16": "playoffs", "2027-06-17": "re_signing", "2027-06-21": "re_signing",
            "2027-06-22": "draft", "2027-06-23": "draft", "2027-06-24": "re_signing", "2027-06-29": "re_signing",
            "2027-06-30": "free_agency", "2027-07-15": "free_agency", "2027-07-16": "offseason",
            "2027-09-01": "training_camp", "2027-10-01": "preseason", "2027-10-21": "regular_season",
        }
        for day, phase in expected.items():
            self.assertEqual(sv.phase_for_date(day), phase, day)

    def test_no_lottery_stop_any_more(self):
        self.assertNotIn("draft_lottery", {sv.phase_for_date(f"2027-06-{d:02}") for d in range(1, 31)})

    def test_next_events_are_the_stops(self):
        save = {"meta": {"season": "2026-27"}, "state": {"current_date": "2027-06-17"},
                "schedule_state": {"simulated_game_ids": []}, "season_schedules": {"2026-27": {"games": []}}}
        events = []
        for _ in range(5):
            day = sv.next_event_date(".", {}, save)
            events.append(day)
            save["state"]["current_date"] = day
        self.assertEqual(events[:4], ["2027-06-22", "2027-06-24", "2027-06-30", "2027-09-01"])

    def test_the_draft_must_finish_and_stop_one_must_close_before_the_market(self):
        save = {"meta": {"season": "2026-27"}, "state": {"current_date": "2027-06-22", "phase": "draft"},
                "draft_state": {}, "free_agency_state": {}}
        with self.assertRaisesRegex(ValueError, "draft"):
            sv.guard_required_phase_actions(save, "2027-06-23", "2027-06-24")
        save["draft_state"] = {"status": "completed", "completed_year": "2027"}
        sv.guard_required_phase_actions(save, "2027-06-23", "2027-06-24")
        with self.assertRaisesRegex(ValueError, "after-draft checklist"):
            sv.guard_required_phase_actions(save, "2027-06-23", "2027-07-01")
        save["state"] = {"current_date": "2027-06-29", "phase": "re_signing"}
        with self.assertRaisesRegex(ValueError, "deciding who to keep"):
            sv.guard_required_phase_actions(save, "2027-06-29", "2027-06-30")
        save["free_agency_state"] = {"re_signing_status": "completed"}
        sv.guard_required_phase_actions(save, "2027-06-29", "2027-06-30")


class OneContractSeasonSwitch(unittest.TestCase):
    def test_everything_switches_on_the_day_the_offseason_opens(self):
        for day, season in (("2027-06-16", "2026-27"), ("2027-06-17", "2027-28"), ("2027-08-10", "2027-28"),
                            ("2027-09-30", "2027-28")):
            save = {"meta": {"season": "2026-27"}, "state": {"current_date": day, "phase": sv.phase_for_date(day)}}
            self.assertEqual(contract_season(save), season, day)
            self.assertEqual(sv.save_active_contract_season(save), season, day)
            self.assertEqual(cl.cap_year(save), season, day)
            self.assertEqual(play.contract_start_season_for_signing(save), season, day)
        after_rollover = {"meta": {"season": "2027-28"}, "state": {"current_date": "2027-10-01"}}
        self.assertEqual(contract_season(after_rollover), "2027-28")

    def test_the_phase_name_no_longer_switches_the_signing_season(self):
        # Before, a signing in a "free_agency" phase counted next season whatever the date.
        save = {"meta": {"season": "2026-27"}, "state": {"current_date": "2027-03-01", "phase": "free_agency"}}
        self.assertEqual(cl.cap_year(save), "2026-27")

    def test_cap_holds_count_from_the_switch(self):
        self.assertEqual(cl.offseason_window("2027-28", "2027-06-16"), (False, False))
        self.assertEqual(cl.offseason_window("2027-28", "2027-06-17"), (True, False))
        self.assertEqual(cl.offseason_window("2027-28", "2027-07-01"), (True, True), "empty-spot charges: league year")


if __name__ == "__main__":
    unittest.main()
