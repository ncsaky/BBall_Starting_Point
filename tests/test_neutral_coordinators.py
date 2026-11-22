"""NEUTRAL-COORDINATORS (2026-11-21): a new save's starting offensive and defensive coordinators have neutral ratings.

Their made-up starting ratings pushed real teams' results the wrong way (docs/agents/tasks/odds-coach.md); the user
decided no real coordinators are needed. Head coaches keep their evidence-based ratings; coordinators hired later from
the market can still be better or worse; the betting test's 2025-26 replay starts coordinators the same way."""
from copy import deepcopy
from pathlib import Path
import unittest

from nba_gm_data import sim
from nba_gm_data.save import save_coach_ratings
from nba_gm_data.staff import (
    COORDINATOR_SLOTS, NEUTRAL_STAFF_RATING, SLOT_SKILLS, generated_staff_candidates, initialize_save_staff_slots,
    neutral_starting_coordinator, staff_effect_rows, staff_effect_summary,
)

from test_odds_coach import fake_canonical

ROOT = Path(__file__).resolve().parents[1]
COORDINATOR_TERMS = ("offense_core", "spacing_term", "creator_term", "defense_core", "matchup_term", "discipline_term")


class NewSaveCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.canonical = fake_canonical()
        self.slots = initialize_save_staff_slots(self.canonical, seed=11)
        self.seeded = {(slot["team_id"], slot["slot"]): slot for slot in self.canonical["gameplay_staff_slots"]}

    def test_every_starting_coordinator_is_neutral(self):
        coordinators = [slot for slot in self.slots if slot["slot"] in COORDINATOR_SLOTS]
        self.assertEqual(len(coordinators), 60)
        for slot in coordinators:
            self.assertEqual(slot["skill_traits"], {key: NEUTRAL_STAFF_RATING for key in SLOT_SKILLS[slot["slot"]]})
            self.assertEqual(slot["starting_ratings"], "neutral")

    def test_identity_and_personality_stay(self):
        for slot in self.slots:
            seeded = self.seeded[(slot["team_id"], slot["slot"])]
            for field in ("id", "personality_traits", "status"):
                self.assertEqual(slot[field], seeded[field], field)
            if slot["slot"] in COORDINATOR_SLOTS:
                self.assertEqual(neutral_starting_coordinator(deepcopy(seeded))["name"], seeded["name"])
            self.assertGreater(slot["contract"]["annual_salary_millions"], 0)
            self.assertIn("age", slot)

    def test_head_coaches_are_unchanged(self):
        for slot in self.slots:
            if slot["slot"] == "head_coach":
                self.assertEqual(slot["skill_traits"], self.seeded[(slot["team_id"], "head_coach")]["skill_traits"])
                self.assertNotIn("starting_ratings", slot)

    def test_coordinator_effects_are_zero_and_head_coach_effects_remain(self):
        ratings = save_coach_ratings(self.canonical, {"staff_slots": self.slots})
        head_effects = []
        for team in self.canonical["teams"]:
            effect = sim.coach_effect(ratings[team["id"]])
            for term in COORDINATOR_TERMS:
                self.assertEqual(effect[term], 0.0, (team["abbrev"], term))
            self.assertEqual(sim.foul_rate_multiplier(ratings[team["id"]]), 1.0)
            head_effects.append(effect["rotation"])
        self.assertGreater(len(set(head_effects)), 1)  # head coaches still differ

    def test_staff_screen_shows_the_neutral_ratings(self):
        for slot in self.slots:
            if slot["slot"] not in COORDINATOR_SLOTS:
                continue
            rows = staff_effect_rows(slot)
            self.assertEqual([row["value"] for row in rows], [60.0, 60.0, 60.0, 60.0])
            self.assertEqual(rows[0]["stars"], 3.0)
            self.assertEqual(staff_effect_summary(slot), {"coach_star_equivalent": 3.0})

    def test_market_coordinators_still_vary(self):
        for slot in COORDINATOR_SLOTS:
            candidates = generated_staff_candidates(11, slot)
            stars = [staff_effect_rows(candidate)[0]["stars"] for candidate in candidates]
            self.assertGreater(max(stars), 3.3)
            self.assertLess(min(stars), 2.7)

    def test_other_slots_pass_through(self):
        slot = deepcopy(self.seeded[(self.canonical["teams"][0]["id"], "head_coach")])
        self.assertEqual(neutral_starting_coordinator(deepcopy(slot)), slot)


class ReplayCoordinatorTests(unittest.TestCase):
    def test_replay_coordinators_are_neutral_like_a_new_save(self):
        canonical = fake_canonical()
        stints = sim.replay_staff_stints(canonical, ROOT)
        self.assertEqual(len(stints), 30)
        for entries in stints.values():
            for _first_date, rating in entries:
                effect = sim.coach_effect(rating)
                for term in COORDINATOR_TERMS:
                    self.assertEqual(effect[term], 0.0)
                for key in ("shot_quality", "spacing_design", "creator_usage", "coverage_design", "matchup_scheming", "discipline"):
                    self.assertEqual(rating.ratings[key], 3.0)


if __name__ == "__main__":
    unittest.main()
