"""Coaching overhaul (2026-11-18): every head-coach and coordinator rating drives its own effect."""
import unittest

from nba_gm_data.health import coach_development_by_team
from nba_gm_data.save import save_coach_ratings
from nba_gm_data.schema import CoachRating
from nba_gm_data.sim import STAFF_EFFECT_KEYS, assign_personal_fouls, scaled_coach_effect

AVERAGE = {key: 3.0 for key in STAFF_EFFECT_KEYS} | {"experimentation": 3.0, "hands_on_control": 3.0}
TEAM = {"spacing": 60.0, "primary_creator": 70.0}


def effect(team=TEAM, **changes):
    rating = CoachRating(id="c", team_id="t", coach_name="Test", ratings=AVERAGE | changes, confidence=1.0, source_ids=[], notes="")
    return scaled_coach_effect(rating, team)


class CoachingEffectTests(unittest.TestCase):
    def test_average_staff_is_neutral(self):
        base = effect()
        self.assertEqual((base["offense"], base["defense"], base["playoff"]), (0.0, 0.0, 0.0))

    def test_coordinators_each_move_their_own_side(self):
        self.assertGreater(effect(shot_quality=5.0)["offense"], 0.5)
        self.assertEqual(effect(shot_quality=5.0)["defense"], 0.0)
        self.assertGreater(effect(coverage_design=5.0)["defense"], 0.5)
        self.assertEqual(effect(coverage_design=5.0)["offense"], 0.0)
        self.assertGreater(effect(matchup_scheming=5.0)["defense"], 0.0)
        self.assertGreater(effect(discipline=5.0)["defense"], 0.0)

    def test_spacing_and_creator_designs_depend_on_the_roster(self):
        shooters, no_shooters = {"spacing": 70.0, "primary_creator": 50.0}, {"spacing": 40.0, "primary_creator": 50.0}
        self.assertGreater(effect(shooters, spacing_design=5.0)["offense"], 2 * effect(no_shooters, spacing_design=5.0)["offense"])
        creator, none = {"spacing": 50.0, "primary_creator": 75.0}, {"spacing": 50.0, "primary_creator": 45.0}
        self.assertGreater(effect(creator, creator_usage=5.0)["offense"], 2 * effect(none, creator_usage=5.0)["offense"])

    def test_head_coach_ratings(self):
        relations = effect(player_relations=5.0)
        self.assertGreater(relations["offense"], 0)
        self.assertGreater(relations["defense"], 0)
        manager = effect(game_management=5.0)
        self.assertGreater(manager["playoff"], 1.0)
        self.assertGreater(effect(rotation_management=5.0)["rotation"], 0)

    def test_discipline_lowers_fouls(self):
        import random
        lines = [{"minutes": 36.0} for _ in range(400)]
        loose = [dict(line) for line in lines]
        assign_personal_fouls(lines, random.Random(1), rate_multiplier=0.92)
        assign_personal_fouls(loose, random.Random(1), rate_multiplier=1.08)
        self.assertLess(sum(l["personal_fouls"] for l in lines), sum(l["personal_fouls"] for l in loose))

    def test_development_uses_the_saves_head_coach(self):
        def canonical(locker_room):
            return {"teams": [{"id": "t"}], "gameplay_staff_slots": [
                {"team_id": "t", "slot": "head_coach", "skill_traits": {"locker_room": locker_room},
                 "personality_traits": {"communication": 70.0}}]}
        self.assertGreater(coach_development_by_team(canonical(90.0))["t"], coach_development_by_team(canonical(40.0))["t"])

    def test_save_staff_ratings_have_one_star_per_rating(self):
        slots = [{"team_id": "t", "slot": slot, "skill_traits": traits, "personality_traits": {"communication": 60, "adaptability": 60, "ambition": 60}}
                 for slot, traits in (("head_coach", {"rotation_management": 80, "locker_room": 60, "scheme_balance": 60}),
                                      ("offensive_coordinator", {"shot_quality": 40, "spacing_design": 60, "player_usage": 60}),
                                      ("defensive_coordinator", {"coverage_design": 60, "matchup_adjustment": 60, "discipline": 60}))]
        ratings = save_coach_ratings({"teams": [{"id": "t"}]}, {"staff_slots": slots})["t"].ratings
        self.assertTrue(set(STAFF_EFFECT_KEYS) <= set(ratings))
        self.assertEqual(ratings["rotation_management"], 4.0)
        self.assertEqual(ratings["shot_quality"], 2.0)


if __name__ == "__main__":
    unittest.main()
