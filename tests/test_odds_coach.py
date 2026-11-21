"""ODDS-COACH (2026-11-20): the replayed 2025-26 season uses that season's real coaches, rated by the save staff model.

Saves are untouched: they pass their own canonical, get no replay staff, and install their staff's ratings."""
import json
from copy import deepcopy
from pathlib import Path
import unittest

from nba_gm_data import sim
from nba_gm_data.save import save_coach_ratings
from nba_gm_data.staff import HEAD_COACH_REPUTATION_GRADES, apply_head_coach_reputation, neutral_starting_coordinator, normalize_name

ROOT = Path(__file__).resolve().parents[1]
STAFFS = json.loads((ROOT / sim.REPLAY_STAFFS_FILE).read_text())
ABBREVS = sorted(STAFFS["teams"])
EMPTY_REFERENCE = {"schedule": [], "real_minutes": {}, "boxscores": [], "odds": {}, "manifestos": {}}


def slot(team_id, name, traits, personality):
    return {"id": f"{team_id}-{name}", "team_id": team_id, "slot": name, "name": f"Scaffold {name}",
            "skill_traits": traits, "personality_traits": personality, "status": "fictional_gameplay_scaffold"}


def fake_canonical():
    """Thirty teams with distinct starting staff slots, 2026-27 head coaches in staff_profiles (as the universe has)."""
    teams, slots, profiles = [], [], []
    for index, abbrev in enumerate(ABBREVS):
        team_id = f"team_{abbrev.lower()}"
        teams.append({"id": team_id, "abbrev": abbrev})
        bump = index % 7
        slots += [
            slot(team_id, "head_coach", {"rotation_management": 55 + bump, "locker_room": 60, "scheme_balance": 62 - bump},
                 {"adaptability": 58 + bump, "communication": 61, "ambition": 60}),
            slot(team_id, "offensive_coordinator", {"shot_quality": 50 + 3 * bump, "spacing_design": 60, "player_usage": 64},
                 {"adaptability": 60, "communication": 60, "ambition": 60}),
            slot(team_id, "defensive_coordinator", {"coverage_design": 70 - 2 * bump, "matchup_adjustment": 61, "discipline": 57},
                 {"adaptability": 60, "communication": 60, "ambition": 60}),
        ]
        profiles.append({"team_id": team_id, "role": "head_coach", "name": "Sean Sweeney" if abbrev == "ORL" else "Somebody"})
    return {"teams": teams, "players": [], "gameplay_staff_slots": slots, "staff_profiles": profiles}


class ReplayStaffTests(unittest.TestCase):
    def setUp(self):
        self.canonical = fake_canonical()
        self.stints = sim.replay_staff_stints(self.canonical, ROOT)

    def coach(self, abbrev, date=None):
        context = {"canonical": self.canonical, "replay_staff_stints": self.stints}
        context["indices"] = sim.replay_coach_indices(context)
        return sim.coaches_on_date(context, context["indices"]["coach_by_team"], date)[f"team_{abbrev.lower()}"]

    def test_every_team_has_its_2025_26_coach(self):
        self.assertEqual(len(ABBREVS), 30)
        self.assertEqual(len(self.stints), 30)
        # 2026-27 hires (Sweeney, Jenkins, May, Nori, Splitter in Chicago) are not 2025-26 coaches.
        self.assertEqual(self.coach("ORL").coach_name, "Jamahl Mosley")
        self.assertEqual(self.coach("MIL").coach_name, "Doc Rivers")
        self.assertEqual(self.coach("DAL").coach_name, "Jason Kidd")
        self.assertEqual(self.coach("CHI").coach_name, "Billy Donovan")

    def test_in_season_changes_follow_the_game_date(self):
        self.assertEqual(self.coach("POR", "2025-10-22").coach_name, "Chauncey Billups")
        self.assertEqual(self.coach("POR", "2025-10-24").coach_name, "Tiago Splitter")
        self.assertEqual(self.coach("NOP", "2025-11-14").coach_name, "Willie Green")
        self.assertEqual(self.coach("NOP", "2025-11-16").coach_name, "James Borrego")
        self.assertEqual(self.coach("NOP", "2026-04-12T19:00Z").coach_name, "James Borrego")

    def test_ratings_come_from_the_save_staff_model(self):
        rating = self.coach("ORL")
        self.assertTrue(set(sim.STAFF_EFFECT_KEYS) <= set(rating.ratings))
        self.assertEqual(sim.coach_effect(rating).get("staff_model"), 1.0)
        # Same numbers a new save gives Mosley on Orlando's starting slots.
        # Coordinators start neutral, as in a new save (NEUTRAL-COORDINATORS, 2026-11-21).
        slots = [neutral_starting_coordinator(deepcopy(s)) for s in self.canonical["gameplay_staff_slots"] if s["team_id"] == "team_orl"]
        head = next(s for s in slots if s["slot"] == "head_coach")
        head["name"] = "Jamahl Mosley"
        apply_head_coach_reputation(head, "Jamahl Mosley")
        expected = save_coach_ratings({"teams": [{"id": "team_orl"}]}, {"staff_slots": slots})["team_orl"]
        self.assertEqual(rating.ratings, expected.ratings)

    def test_every_coach_is_graded_or_documented(self):
        documented = {normalize_name(name) for name in STAFFS["unrated_coach_grades"]}
        for abbrev, entry in STAFFS["teams"].items():
            for coach in entry["head_coaches"]:
                name = normalize_name(coach["name"])
                self.assertTrue(name in HEAD_COACH_REPUTATION_GRADES or name in documented, coach["name"])
                self.assertIn(coach["source"], {source["id"] for source in STAFFS["sources"]})

    def test_documented_grade_matches_the_table_rule(self):
        unknown = slot("t", "head_coach", {"rotation_management": 50, "locker_room": 50, "scheme_balance": 50}, {})
        untouched = deepcopy(unknown)
        apply_head_coach_reputation(untouched, "James Borrego")
        self.assertEqual(untouched, unknown)  # the table has no grade for him: a save would leave the slot alone
        apply_head_coach_reputation(unknown, "James Borrego", grade=60.0)
        self.assertEqual(unknown["reputation_grade_target"], 60.0)
        known, explicit = deepcopy(untouched), deepcopy(untouched)
        apply_head_coach_reputation(known, "Steve Kerr")
        apply_head_coach_reputation(explicit, "Steve Kerr", grade=HEAD_COACH_REPUTATION_GRADES["steve kerr"])
        self.assertEqual(known, explicit)


class SaveContextTests(unittest.TestCase):
    def test_a_save_context_gets_no_replay_staff(self):
        canonical = fake_canonical()
        context = sim.load_sim_context(ROOT, canonical, reference=EMPTY_REFERENCE)
        self.assertNotIn("replay_staff_stints", context)
        self.assertNotIn("coach_changes_by_team", context["indices"])
        legacy = {rating.team_id: rating for rating in sim.coach_ratings(canonical)}
        self.assertEqual(context["indices"]["coach_by_team"], legacy)
        coaches = context["indices"]["coach_by_team"]
        self.assertIs(sim.coaches_on_date(context, coaches, "2025-11-20"), coaches)


if __name__ == "__main__":
    unittest.main()
