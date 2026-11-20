"""Game-context refit, shared pace and recorded starters (2026-11-20, docs/agents/tasks/overnight-game-context-margins.md)."""
from __future__ import annotations

import random
import statistics
import unittest
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import save as save_module, sim
from nba_gm_data.season_slides import award_detail
from nba_gm_data.utils import normalize_name


class SharedPaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(Path(__file__).resolve().parents[1])
        cls.games = sim.validation_game_ids(cls.context, through_date=None, playoffs=False)[:6]
        canonical = cls.context["canonical"]
        cls.teams = canonical["teams"][:2]
        pools = [sim.game_player_pool(cls.context, cls.games[0], team, "sandbox-sim") for team in cls.teams]
        cls.feats = [sim.game_team_features(cls.context, canonical, team, pool, "sandbox-sim")
                     for team, pool in zip(cls.teams, pools)]

    def draws(self, shared):
        canonical = self.context["canonical"]
        rng = random.Random(11)
        with patch.object(sim, "SHARED_PACE", shared):
            return [sim.draw_both_scores(canonical, self.feats[0], self.feats[1], None, None, rng, None, None) for _ in range(800)]

    def test_both_teams_share_the_games_possessions(self):
        shared = self.draws(True)
        alone = self.draws(False)
        corr = lambda rows: statistics.correlation([h["possessions"] for h, _ in rows], [a["possessions"] for _, a in rows])
        self.assertGreater(corr(shared), 0.8)
        self.assertLess(abs(corr(alone)), 0.15)
        gaps = [h["possessions"] - a["possessions"] for h, a in shared]
        self.assertLess(statistics.pstdev(gaps), 3.0)
        # sharing pace widens totals and narrows margins
        spread = lambda rows, sign: statistics.pstdev([h["points"] + sign * a["points"] for h, a in rows])
        self.assertGreater(spread(shared, 1), spread(alone, 1))
        self.assertLess(spread(shared, -1), spread(alone, -1))

    def test_expected_pace_is_the_average_of_both_teams(self):
        canonical = self.context["canonical"]
        means = [sim.draw_team_score(canonical, self.feats[0], self.feats[1], None, None, None, is_home=True, mean_only=True),
                 sim.draw_team_score(canonical, self.feats[1], self.feats[0], None, None, None, is_home=False, mean_only=True)]
        expected = (means[0]["expected_possessions"] + means[1]["expected_possessions"]) / 2
        rows = self.draws(True)
        self.assertAlmostEqual(statistics.fmean(h["possessions"] for h, _ in rows), expected, delta=0.6)
        self.assertAlmostEqual(statistics.fmean(a["possessions"] for _, a in rows), expected, delta=0.6)

    def test_replayed_games_are_deterministic(self):
        a = [sim.sim_game_with_context(self.context, gid, seed=4) for gid in self.games[:3]]
        b = [sim.sim_game_with_context(self.context, gid, seed=4) for gid in self.games[:3]]
        self.assertEqual([(r.home_score, r.away_score) for r in a], [(r.home_score, r.away_score) for r in b])


class ContextRefitTests(unittest.TestCase):
    def test_home_court_gap_and_sum(self):
        self.assertAlmostEqual(sim.HOME_COURT_RATING - sim.AWAY_COURT_RATING, 1.75)
        self.assertAlmostEqual(sim.HOME_COURT_RATING + sim.AWAY_COURT_RATING, 1.5)   # league scoring unchanged

    def test_rest_and_age_scales(self):
        b2b = sim.rest_effect({"rest_days": 0})
        self.assertAlmostEqual(b2b["offense"], -1.35 * sim.REST_EFFECT_SCALE, places=4)
        with patch.object(sim, "AGE_FATIGUE_SCALE", 1.0):
            full = sim.age_fatigue_effect({"old_core_share": 0.5, "very_old_core_share": 0.2, "average_age": 31.0}, {"rest_days": 0})
        scaled = sim.age_fatigue_effect({"old_core_share": 0.5, "very_old_core_share": 0.2, "average_age": 31.0}, {"rest_days": 0})
        self.assertAlmostEqual(scaled["offense"], round(full["offense"] * sim.AGE_FATIGUE_SCALE, 4), places=3)

    def test_absence_penalty_off_leaves_features_untouched(self):
        features = {"impact": 60.0, "primary_creator": 70.0}
        out = sim.apply_availability_dependency_adjustments({"players": []}, {"id": "t"}, [], features)
        self.assertEqual(out["impact"], 60.0)
        self.assertEqual(out["availability_dependency_penalty"], 0.0)

    def test_recent_form_ignores_last_seasons_games(self):
        context = {"indices": {"espn_id_by_team_id": {"t": "1"}, "boxscores_by_team_espn_id": {"1": [
            {"date": f"2026-04-{day:02d}", "status": "STATUS_FINAL", "home_team_id": "1", "away_team_id": "2",
             "home_score": 130, "away_score": 100} for day in range(1, 11)]}}, "boxscores": []}
        october = sim.recent_scoring_context_for_team(context, {"gameDate": "2026-10-25"}, {"id": "t"})
        april = sim.recent_scoring_context_for_team(context, {"gameDate": "2026-04-20"}, {"id": "t"})
        self.assertEqual(october["recent_game_count"], 0)
        self.assertEqual(april["recent_game_count"], 10)


class ReplayRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(Path(__file__).resolve().parents[1])

    def test_rotation_is_the_real_seasons_team(self):
        canonical = self.context["canonical"]
        team = next(t for t in canonical["teams"] if t["abbrev"] == "OKC")
        rotation = sim.replay_expected_rotation(self.context, team, "2026-01-15")
        names = {player["name"] for player, _ in rotation}
        self.assertIn("Shai Gilgeous-Alexander", names)
        self.assertTrue(all(0 < minutes <= 48 for _, minutes in rotation))


class StarterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(Path(__file__).resolve().parents[1])
        cls.games = sim.validation_game_ids(cls.context, through_date=None, playoffs=False)[:4]

    def test_every_box_score_has_five_starters_per_team(self):
        for mode in ("replay-real-minutes", "sandbox-sim"):
            for gid in self.games:
                result = sim.sim_game_with_context(self.context, gid, mode=mode, seed=2)
                for team_id in (result.home_team_id, result.away_team_id):
                    starters = [line for line in result.player_lines if line["team_id"] == team_id and line["starter"]]
                    self.assertEqual(len(starters), 5, (mode, gid))

    def test_replayed_games_use_the_real_starters(self):
        gid = self.games[0]
        box = self.context["indices"]["boxscores_by_game_id"][gid]
        real = {normalize_name(row["player_name"]) for row in box["players"] if row.get("starter")}
        result = sim.sim_game_with_context(self.context, gid, seed=1)
        self.assertEqual({normalize_name(line["player_name"]) for line in result.player_lines if line["starter"]}, real)

    def test_coach_lineup_starts_and_open_spots_go_to_planned_minutes(self):
        pool = [{"player": {"id": f"p{i}"}, "minutes": 40 - i * 3, "actual": None} for i in range(9)]
        self.assertEqual(sim.game_starters(pool, None, "sandbox-sim"), {"p0", "p1", "p2", "p3", "p4"})
        # p7 and p8 are the coach's choices; p9 (absent tonight) is replaced by the biggest planned minutes left
        self.assertEqual(sim.game_starters(pool, ["p7", "p8", "p9", "p0", "p1"], "sandbox-sim"), {"p7", "p8", "p0", "p1", "p2"})

    def test_stored_lineup_reaches_the_sim(self):
        save = {"starting_lineups": {"t1": {"slots": {"2": "b", "1": "a", "3": "c", "4": "d", "5": "e"}, "source": "user"}}}
        self.assertEqual(save_module.saved_starting_lineups(save), {"t1": ["a", "b", "c", "d", "e"]})


class SixthManTests(unittest.TestCase):
    def test_starts_counted_from_box_scores(self):
        totals = {}
        save_module.count_award_game(totals, {"player_id": "x", "minutes": 24, "starter": False}, {"y"})
        save_module.count_award_game(totals, {"player_id": "x", "minutes": 30, "starter": True}, {"y"})
        save_module.count_award_game(totals, {"player_id": "x", "minutes": 22, "starter": False}, {"x"})
        counts = save_module.sixth_man_bench_counts(totals)
        self.assertEqual((counts["bench_games"], counts["top_minutes_games"], counts["bench_basis"]), (2, 1, "starts"))
        with patch.object(save_module, "SIXTH_MAN_BENCH_RULE", "top_minutes"):
            old = save_module.sixth_man_bench_counts(totals)
        self.assertEqual((old["bench_games"], old["top_minutes_games"], old["bench_basis"]), (2, 1, "top_minutes"))

    def test_lines_without_starts_fall_back(self):
        totals = {"games_bench": 40, "games_top_minutes": 30}
        counts = save_module.sixth_man_bench_counts(totals)
        self.assertEqual((counts["bench_games"], counts["bench_basis"]), (40, "top_minutes"))

    def test_slide_detail_names_the_rule(self):
        self.assertIn("started 12", award_detail({"award": "SMOY", "bench_games": 60, "top_minutes_games": 12, "bench_basis": "starts"}))
        self.assertIn("top five", award_detail({"award": "SMOY", "bench_games": 60, "top_minutes_games": 12}))


if __name__ == "__main__":
    unittest.main()
