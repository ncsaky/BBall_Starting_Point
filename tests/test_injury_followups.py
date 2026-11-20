"""Injury countdowns use the roster's schedule."""
from datetime import date
from pathlib import Path
import unittest

from nba_gm_data import health
from nba_gm_data import save as sv

ROOT = Path(__file__).resolve().parents[1]


class InjuryCountdownTests(unittest.TestCase):
    def test_countdown_tracks_unplayed_team_games_before_return(self):
        days = ["2026-10-21", "2026-10-22", "2026-10-23", "2026-10-31"]
        team_id = "team_bos"
        canonical = {"teams": [{"id": team_id, "abbrev": "BOS", "name": "Boston Celtics"}]}
        schedule = [
            {"externalGameId": f"g{i}", "gameDate": day, "homeTeamId": "2", "awayTeamId": "1"}
            for i, day in enumerate(days)
        ]
        schedule.insert(3, {"externalGameId": "other", "gameDate": "2026-10-24",
                            "homeTeamId": "3", "awayTeamId": "1"})
        current = days[1]
        save = {"meta": {"season": "2026-27"}, "state": {"current_date": current},
                "season_schedules": {"2026-27": {"games": schedule}},
                "schedule_state": {"simulated_game_ids": ["g0"]}}
        state = {"availability_status": "out", "current_injury_label": "Ankle sprain",
                 "return_date": health.injury_return_date(days, date.fromisoformat(days[0]), 4).isoformat()}

        pending = sv.remaining_injury_schedule(ROOT, canonical, save, team_id)
        self.assertEqual(sv.player_health_label(state, current, pending)["label"], "Ankle sprain ~2g")
        save["schedule_state"]["simulated_game_ids"].append("g1")
        pending = sv.remaining_injury_schedule(ROOT, canonical, save, team_id)
        self.assertEqual(sv.player_health_label(state, current, pending)["label"], "Ankle sprain ~1g")
        self.assertEqual(sv.player_health_label(state, days[-1], pending)["label"], "Ankle sprain ~0g")


class InjuryRateFitTests(unittest.TestCase):
    def test_fit_uses_within_season_workload_even_with_different_coverage(self):
        import math
        from scripts.build_injury_model import fit_season_rates

        # In the higher-coverage season, players with lower workloads play most of the games.
        # In both seasons, a higher workload doubles the rate at the same exposure.
        seasons = ["early", "early", "late", "late", "uncovered"]
        exposure = [1000, 9000, 9000, 1000, 5000]
        counts = [10, 180, 720, 160, 0]
        features = [[0.0], [1.0], [0.0], [1.0], [1.0]]
        intercepts, (workload,) = fit_season_rates(features, counts, exposure, seasons)
        self.assertAlmostEqual(math.exp(workload), 2.0, delta=0.06)
        self.assertIsNone(intercepts["uncovered"])
        for season, total in (("early", 190), ("late", 880)):
            predicted = sum(gp * math.exp(intercepts[season] + workload * x)
                            for (x,), gp, key in zip(features, exposure, seasons) if key == season)
            self.assertAlmostEqual(predicted, total, places=5)
