"""Differential coverage against the pre-optimization exhaustive search."""
import copy
import random
import unittest
from itertools import permutations
from unittest.mock import patch

from nba_gm_data import save as engine


def reference_auto_starting_five(canonical, save, team_id):
    projection = engine.team_rotation_projection(canonical, save, team_id, integer=False)
    unavailable = engine.unavailable_player_ids_for_starting_five(save)
    roster = [p for p in canonical.get("players", [])
              if p.get("team_id") == team_id and p.get("id") not in unavailable]
    candidates = []
    for player in roster:
        minutes = float(projection.get(player.get("id"), engine.display_minutes_projection(player)))
        attrs = engine.player_attribute_summary(canonical, player.get("id"))
        base = minutes * 1.3 + float(attrs.get("overall") or 50.0) * 0.5
        candidates.append((base, minutes, player.get("name") or "", player, attrs))
    candidates = sorted(candidates, key=lambda row: (row[0], row[1], row[2]), reverse=True)[:9]
    slots = ["1", "2", "3", "4", "5"][:min(5, len(candidates))]
    best_score, best = -1_000_000.0, None
    for assignment in permutations(candidates, len(slots)):
        total = 0.0
        for slot, row in zip(slots, assignment, strict=False):
            total += engine.starting_slot_score(row[3], slot, row[1], row[4])
        if total > best_score:
            best_score, best = total, assignment
    return {} if not best else {slot: row[3]["id"] for slot, row in zip(slots, best, strict=False) if row[3].get("id")}


class LineupPerformanceTests(unittest.TestCase):
    def fixture(self, count, seed=0, tied=False):
        rng = random.Random(seed)
        players = [{"id": f"p{i}", "team_id": "team", "name": "Same" if tied else f"Player {i}",
                    "position": "SG" if tied else rng.choice(["PG", "SG", "SF", "PF", "C", "PG-SG", "PF/C"]),
                    "height_inches": 78 if tied else rng.uniform(72, 88)} for i in range(count)]
        attrs = {p["id"]: {key: 75 if tied else rng.uniform(30, 99) for key in
                          ["overall", "creation", "passing", "spacing", "defense", "rebounding", "rim_protection"]} for p in players}
        minutes = {p["id"]: 20 if tied else rng.uniform(0, 38) for p in players}
        return {"players": players}, {}, attrs, minutes

    def compare(self, count, seed=0, tied=False, unavailable=()):
        canonical, save, attrs, minutes = self.fixture(count, seed, tied)
        before = copy.deepcopy((canonical, save))
        with patch.object(engine, "team_rotation_projection", return_value=minutes), \
             patch.object(engine, "player_attribute_summary", side_effect=lambda _, pid: attrs[pid]), \
             patch.object(engine, "unavailable_player_ids_for_starting_five", return_value=set(unavailable)):
            expected = reference_auto_starting_five(canonical, save, "team")
            with patch.object(engine, "starting_slot_score", wraps=engine.starting_slot_score) as score:
                self.assertEqual(engine.auto_starting_five(canonical, save, "team"), expected)
                candidates = min(9, count-len(unavailable))
                self.assertEqual(score.call_count, candidates * min(5, candidates))
        self.assertEqual((canonical, save), before)

    def test_differential_varied_rosters_and_candidate_cap(self):
        for seed in range(6):
            for count in [0, 1, 4, 5, 7, 9, 12]:
                with self.subTest(seed=seed, count=count):
                    self.compare(count, seed)

    def test_ties_keep_original_enumeration_and_injuries_filter_candidates(self):
        self.compare(9, tied=True)
        self.compare(12, seed=19, unavailable=("p0", "p5", "p11"))

    def test_complete_manual_lineup_skips_search_and_preserves_user_choices(self):
        canonical, save, _, _ = self.fixture(9)
        slots = {str(i+1): f"p{i}" for i in range(5)}
        save["starting_lineups"] = {"team": {"slots": slots.copy(), "source": "user"}}
        before = copy.deepcopy(save)
        with patch.object(engine, "auto_starting_five", side_effect=AssertionError("unnecessary search")):
            self.assertEqual(engine.starting_lineup_slots(canonical, save, "team"), slots)
        self.assertEqual(save, before)

    def test_injured_manual_starter_temporarily_fills_then_returns(self):
        canonical, save, _, _ = self.fixture(9)
        slots = {str(i+1): f"p{i}" for i in range(5)}
        save["starting_lineups"] = {"team": {"slots": slots.copy(), "source": "user"}}
        with patch.object(engine, "unavailable_player_ids_for_starting_five", return_value={"p0"}), \
             patch.object(engine, "auto_starting_five", return_value={"1": "p5", "2": "p1", "3": "p2", "4": "p3", "5": "p4"}) as auto:
            self.assertEqual(engine.starting_lineup_slots(canonical, save, "team")["1"], "p5")
            auto.assert_called_once()
        self.assertEqual(save["starting_lineups"]["team"]["slots"], slots)
        with patch.object(engine, "auto_starting_five", side_effect=AssertionError("unnecessary search")):
            self.assertEqual(engine.starting_lineup_slots(canonical, save, "team"), slots)

    def test_scores_are_recomputed_when_minutes_or_ratings_change(self):
        canonical, save, attrs, minutes = self.fixture(9)
        with patch.object(engine, "team_rotation_projection", return_value=minutes), \
             patch.object(engine, "player_attribute_summary", side_effect=lambda _, pid: attrs[pid]):
            for change in range(3):
                minutes["p0"] = change * 18
                attrs["p1"]["overall"] = change * 45
                self.assertEqual(engine.auto_starting_five(canonical, save, "team"),
                                 reference_auto_starting_five(canonical, save, "team"))


if __name__ == "__main__":
    unittest.main()
