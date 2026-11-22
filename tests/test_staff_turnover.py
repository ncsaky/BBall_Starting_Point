from copy import deepcopy
import unittest
from unittest.mock import patch

from nba_gm_data.save import age_staff_contracts, apply_ai_staff_recommendations, queue_ai_recommendations
from nba_gm_data.staff import (
    COACHING_SLOTS,
    COORDINATOR_SLOTS,
    coordinator_departure_target,
    current_staff_slot,
    head_coach_firing_chance,
    interim_staff,
    is_interim_staff,
    offseason_coaching_recommendations,
    remember_opening_coaching_staff,
    simulate_ai_staff_changes,
    staff_change_permission,
    staff_grade,
)
from tests.test_staff_lifecycle import make_staff


class StaffTurnoverTests(unittest.TestCase):
    def setUp(self):
        teams = ("team_bos", "team_nyk", "team_gsw", "team_tor")
        self.canonical = {
            "teams": [{"id": team, "abbrev": team[5:].upper(), "name": team} for team in teams],
            "team_strategic_states": [{"team_id": team, "contention_ceiling": 55} for team in teams],
        }
        self.save = {
            "meta": {"seed": 17, "season": "2026-27", "user_team_id": "team_gsw", "human_team_ids": ["team_tor"]},
            "state": {"current_date": "2027-01-01", "phase": "regular_season"},
            "team_records": {team: {"wins": 20, "losses": 20} for team in teams},
            "staff_slots": [make_staff(f"{team}_{slot}", 40, slot, team) for team in teams for slot in COACHING_SLOTS],
            "staff_preseason_expectations": {"2026-27": dict.fromkeys(teams, 0.5)},
        }
        remember_opening_coaching_staff(self.save)

    def test_head_coach_review_uses_forecast_and_skips_every_human_team(self):
        for team in self.save["team_records"]:
            self.save["staff_preseason_expectations"]["2026-27"][team] = 0.65
        self.save["staff_preseason_expectations"]["2026-27"]["team_nyk"] = 0.4
        with patch("nba_gm_data.staff.staff_turnover_draw", return_value=0.02):
            payload = simulate_ai_staff_changes(self.canonical, self.save, "2026-12-31", "2027-01-01")
            self.assertEqual([rec["team_id"] for rec in payload["recommendations"]], ["team_bos"])
            self.assertEqual(payload["recommendations"][0]["action"], "fire_only")
            self.assertLess(payload["recommendations"][0]["wins_vs_preseason_per_82"], -8)
            apply_ai_staff_recommendations(self.canonical, self.save, payload, 17)
            self.assertTrue(is_interim_staff(current_staff_slot(self.save, "team_bos", "head_coach")))
            self.assertEqual(self.save["staff_firing_history"][0]["review_period"], "in_season")
            for team in ("team_gsw", "team_tor"):
                self.assertEqual(current_staff_slot(self.save, team, "head_coach")["id"], f"{team}_head_coach")
            second = simulate_ai_staff_changes(self.canonical, self.save, "2027-01-31", "2027-02-01")
            self.assertFalse(second["recommendations"])

    def test_empty_trade_review_cannot_skip_staff_review(self):
        self.save["staff_preseason_expectations"]["2026-27"]["team_bos"] = 0.65
        self.save["state"]["current_date"] = "2027-02-01"
        market_day = {"review": True, "slots": 0, "offer_slots": 0}
        with (
            patch("nba_gm_data.save.process_ai_extensions", return_value={}),
            patch("nba_gm_data.trade_calendar.market_day", return_value=market_day),
            patch("nba_gm_data.staff.staff_turnover_draw", return_value=0.02),
        ):
            queue_ai_recommendations(self.canonical, self.save, "2027-01-31", "2027-02-01", 17)
        self.assertTrue(is_interim_staff(current_staff_slot(self.save, "team_bos", "head_coach")))

    def test_summer_bench_review_counts_head_coach_retirement(self):
        self.save["state"].update(current_date="2027-09-30", phase="training_camp")
        self.save["team_records"] = {team: {"wins": 41, "losses": 41} for team in self.save["team_records"]}
        head = current_staff_slot(self.save, "team_bos", "head_coach")
        head["age"] = 79
        with patch("nba_gm_data.staff.staff_turnover_draw", return_value=0.6):
            recs = offseason_coaching_recommendations(self.canonical, self.save)
        self.assertEqual({rec["slot"] for rec in recs}, set(COORDINATOR_SLOTS))
        self.assertEqual({rec["team_id"] for rec in recs}, {"team_bos"})
        self.assertEqual(head["age"], 79)

    def test_summer_reviews_do_not_require_a_losing_record_or_a_market_upgrade(self):
        self.save["state"].update(current_date="2027-09-30", phase="training_camp")
        for team in self.save["team_records"]:
            self.save["team_records"][team] = {"wins": 52, "losses": 30}
        self.save["staff_preseason_expectations"]["2026-27"]["team_bos"] = 0.70
        with patch("nba_gm_data.staff.staff_turnover_draw", return_value=0.07):
            recs = offseason_coaching_recommendations(self.canonical, self.save)
        self.assertEqual([(rec["team_id"], rec["slot"]) for rec in recs], [("team_bos", "head_coach")])
        self.assertEqual(recs[0]["review_period"], "offseason")
        self.assertLess(recs[0]["wins_vs_preseason_per_82"], -3)
        self.assertGreater(head_coach_firing_chance(10, offseason=True), 0)

    def test_bench_review_counts_earlier_turnover_under_a_new_head(self):
        self.save["state"].update(current_date="2027-09-30", phase="training_camp")
        self.save["team_records"] = {team: {"wins": 41, "losses": 41} for team in self.save["team_records"]}
        current_staff_slot(self.save, "team_bos", "head_coach")["id"] = "new-head"
        self.save["staff_firing_history"] = [
            {"team_id": "team_bos", "slot": COORDINATOR_SLOTS[0], "season": "2026-27"},
        ]
        with patch("nba_gm_data.staff.staff_turnover_draw", return_value=0.6):
            recs = offseason_coaching_recommendations(self.canonical, self.save)
        self.assertEqual([(rec["team_id"], rec["slot"]) for rec in recs], [("team_bos", COORDINATOR_SLOTS[1])])
        self.assertEqual(coordinator_departure_target(0.97, False), 2)
        self.assertEqual(coordinator_departure_target(0.80, False), 1)
        self.assertEqual(coordinator_departure_target(0.21, True), 1)

    def test_neutral_coordinator_retains_at_expiry_after_a_losing_season(self):
        slot = current_staff_slot(self.save, "team_bos", COORDINATOR_SLOTS[0])
        slot["skill_traits"] = dict.fromkeys(slot["skill_traits"], 60.0)
        slot["personality_traits"] = dict.fromkeys(slot["personality_traits"], 36.0)
        slot["contract"]["years_remaining"] = 1
        self.assertLess(staff_grade(slot), 60)
        self.save["team_records"]["team_bos"] = {"wins": 20, "losses": 62}
        age_staff_contracts(self.save, self.canonical)
        renewed = current_staff_slot(self.save, "team_bos", COORDINATOR_SLOTS[0])
        self.assertEqual(renewed["id"], slot["id"])
        self.assertEqual(renewed["contract"]["years_remaining"], 2)

    def test_offseason_vacancy_hire_does_not_use_in_season_change(self):
        self.save["staff_slots"] = [s for s in self.save["staff_slots"] if s["slot"] == "head_coach"]
        self.save["meta"]["season"] = "2027-28"
        self.save["state"].update(current_date="2027-10-01", phase="preseason")
        self.save["staff_slots"].remove(current_staff_slot(self.save, "team_nyk", "head_coach"))
        self.save["staff_slots"].append(interim_staff("team_nyk", "head_coach", "2027-10-01"))
        payload = simulate_ai_staff_changes(
            self.canonical, self.save, "2027-10-01", "2027-10-01", vacancies_only=True,
        )
        before = deepcopy(current_staff_slot(self.save, "team_nyk", "head_coach"))
        result = apply_ai_staff_recommendations(
            self.canonical, self.save, payload, 17, offseason_appointment=True,
        )
        self.assertEqual(result["applied_count"], 1)
        self.assertNotEqual(current_staff_slot(self.save, "team_nyk", "head_coach")["id"], before["id"])
        self.assertTrue(staff_change_permission(self.save, "team_nyk", "head_coach")["can_fire"])


if __name__ == "__main__":
    unittest.main()
