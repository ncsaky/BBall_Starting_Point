"""Second pass on inputs the game ignored (2026-11-19): fouls, pace, shooting mode, cutting, made threes, development
of the newly used inputs, and the combine-based strength and jump capacity."""
from __future__ import annotations

import copy
import datetime as dt
import random
import statistics
import unittest

from nba_gm_data import box_rates, game_minutes, offense, physical_evidence, ratings_model
from nba_gm_data.ratings_model import load_league_inputs
from nba_gm_data.sim import assign_personal_fouls, pace_habit_possessions

QUETA = "player_bos-neemias-queta"


def bumped(inputs, key, delta=None, factor=None):
    out = dict(inputs)
    record = copy.deepcopy(out[key])
    value = record["value"]
    if "grade" in value:
        value["grade"] = float(value["grade"]) + delta
    elif "probability" in value:
        value["probability"] = float(value["probability"]) * factor
    out[key] = record
    return out


class FoulTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_league_inputs()[QUETA]

    def test_foul_rate_follows_foul_control_and_gambling(self):
        base = box_rates.fouls_per36_from_inputs(self.inputs)
        self.assertLess(box_rates.fouls_per36_from_inputs(bumped(self.inputs, "S45", 15)), base * 0.85)
        self.assertGreater(box_rates.fouls_per36_from_inputs(bumped(self.inputs, "T14", factor=1.3)), base * 1.15)

    def test_replayed_fouls_follow_each_players_rate(self):
        lines = [{"player_id": "careful", "minutes": 32.0}, {"player_id": "hacker", "minutes": 32.0}]
        totals = {"careful": 0, "hacker": 0}
        outs = 0
        rng = random.Random(4)
        for _ in range(2000):
            game = copy.deepcopy(lines)
            assign_personal_fouls(game, rng, player_rates={"careful": 0.6, "hacker": 1.6})
            for line in game:
                totals[line["player_id"]] += line["personal_fouls"]
                outs += line["personal_fouls"] >= 6
                self.assertLessEqual(line["personal_fouls"], 6)
        self.assertGreater(totals["hacker"], 2.0 * totals["careful"])
        self.assertLess(outs / 4000, 0.10)   # foul-outs stay rare even for a foul-prone big

    def test_foul_prone_players_get_into_more_foul_trouble(self):
        pool = [{"player": {"id": f"p{i}", "position": "C" if i == 0 else "SG"}, "minutes": 34.0 if i < 5 else 14.0}
                for i in range(8)]
        lost = {1.0: 0.0, 1.8: 0.0}
        for rate in lost:
            for game in range(400):
                managed, _, _ = game_minutes.manage_game_minutes(pool, [], 2, random.Random(f"g{game}"),
                                                                 random.Random(f"f{game}"), 1.0, {"p0": rate})
                lost[rate] += 34.0 - next(m["minutes"] for m in managed if m["player"]["id"] == "p0")
        self.assertGreater(lost[1.8], lost[1.0] * 1.5)


class PaceTests(unittest.TestCase):
    def test_pace_habit_is_game_level_and_bounded(self):
        fast, slow = {"pace_habit": 0.43}, {"pace_habit": 0.38}
        self.assertAlmostEqual(pace_habit_possessions(fast, slow), pace_habit_possessions(slow, fast))
        self.assertGreater(pace_habit_possessions(fast, fast), 0)
        self.assertLess(pace_habit_possessions(slow, slow), 0)
        self.assertEqual(pace_habit_possessions({}, fast), 0.0)
        self.assertLessEqual(abs(pace_habit_possessions({"pace_habit": 1.0}, {"pace_habit": 1.0})), 4.0)


class ShootingTests(unittest.TestCase):
    def test_shooting_mode_weights_the_three_point_grades(self):
        inputs = load_league_inputs()[QUETA]
        flat = box_rates.flatten_inputs(inputs)
        self.assertIn("S.three_mode", flat)
        lo, hi = sorted((flat["S01"], flat["S02"], flat["S03"]))[::2]
        self.assertTrue(lo - 1e-9 <= flat["S.three_mode"] <= hi + 1e-9)

    def test_night_three_chance_keeps_the_season_percentage(self):
        self.assertAlmostEqual(offense.night_three_pct(0.38, 10, 10), 0.38)
        self.assertEqual(offense.night_three_pct(0.38, 10, None), 0.38)
        self.assertLess(offense.night_three_pct(0.38, 4, 10), 0.38)
        q = offense.night_three_pct(0.40, 9, 9, attempts=8, cap=2)
        self.assertAlmostEqual(offense._capped_binomial_mean(8, q, 2), min(8 * 0.40, 2), places=2)

    def test_made_threes_track_points_on_average(self):
        # A pure shooter handed his normal points: made threes average close to attempts x his percentage.
        feat = {"ft_pct": 0.85, "fta_per_point": 0.08, "three_per36": 9.0, "three_pct": 0.40, "two_pct": 0.52,
                "rim_pressure": 40, "shot_creation": 40}
        rng = random.Random(7)
        made, tried = 0, 0
        for _ in range(3000):
            points = max(0, int(rng.gauss(12, 5)))
            line = offense.shooting_line(points, feat, 30.0, rng, expected_points=12.0)
            made += line["fg3m"]
            tried += line["fg3a"]
        self.assertGreater(made / tried, 0.37)


class DevelopmentRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_league_inputs()[QUETA]

    def test_newly_used_inputs_follow_their_closest_skill(self):
        deltas = ratings_model.route_trait_deltas(self.inputs, {"offensive_rebounding": 2.0, "scheme_iq": 1.0,
                                                                "passing_reads": 1.0, "defensive_effort": -1.0,
                                                                "foot_speed_lateral_agility": -1.0, "rim_deterrence": 1.0})
        steps = ratings_model._development_steps()
        for orphan, like in ratings_model.DEVELOPS_LIKE.items():
            # Same curve as the closest skill, on the orphan's own league spread (DEV-CURVE 2026-11-21).
            ratio = steps.get(orphan, 1.0) / steps.get(like, 1.0) if steps else 1.0
            self.assertAlmostEqual(deltas[orphan], deltas[like] * ratio)
        self.assertLess(deltas["P10"], 0)    # jump capacity (cm) follows foot speed
        self.assertGreater(deltas["P08"], 0)  # strength follows the general curve (rim protection here)

    def test_jump_capacity_moves_in_centimetres(self):
        moved = ratings_model.apply_input_deltas(self.inputs, {"P10": -2.0})
        before = self.inputs["P10"]["value"]["measurements"][0]["value"]
        self.assertAlmostEqual(moved["P10"]["value"]["measurements"][0]["value"], round(before - 2.0, 3))


class PhysicalEvidenceTests(unittest.TestCase):
    def test_aging_curve_grows_young_and_declines_old(self):
        self.assertGreater(physical_evidence.expected_rating_change("foot_speed_lateral_agility", 20.0, 23.0), 0)
        self.assertLess(physical_evidence.expected_rating_change("foot_speed_lateral_agility", 31.0, 34.0), 0)

    def test_combine_match_needs_a_plausible_year(self):
        universe = {"players": [{"id": "a", "name": "Steven Adams", "birthdate": "1993-07-20", "draft_year": 2013},
                                {"id": "b", "name": "Steven Adams", "birthdate": "2003-07-20", "draft_year": 2024}]}
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        matches = physical_evidence.combine_matches(universe, root)
        self.assertEqual(matches["a"]["year"], 2013)
        self.assertNotIn("b", matches)


if __name__ == "__main__":
    unittest.main()
