"""Fatigue that builds and recovers, the engine using it, and the GM's rest controls (FATIGUE-REST, 2026-11-19)."""
import json
import tempfile
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import health
from nba_gm_data import save as sv
from nba_gm_data import sim

STAFF = {"recovery_days_multiplier": 1.0, "fatigue_gain_multiplier": 1.0}
CONFIG = health.default_injury_model_config()
TEAMS = [{"id": "team_bos", "abbrev": "BOS"}, {"id": "team_nyk", "abbrev": "NYK"}]
GAMES = [  # BOS: back-to-back on 11-10/11-11, then 11-13
    {"externalGameId": "g1", "gameDate": "2026-11-10", "homeTeamId": "2", "awayTeamId": "18", "phase": "regular"},
    {"externalGameId": "g2", "gameDate": "2026-11-11", "homeTeamId": "18", "awayTeamId": "2", "phase": "regular"},
    {"externalGameId": "g3", "gameDate": "2026-11-13", "homeTeamId": "2", "awayTeamId": "18", "phase": "regular"},
]


def state(pid="p", **extra):
    return {"player_id": pid, "fatigue": 0.0, "availability_status": "active", "current_injury_id": None, "rust": 0.0,
            "games_missed": 0, **extra}


def league(age=27.0, minutes=34.0, human=(), coach_rests=()):
    players = [{"id": f"{abbrev.lower()}{i}", "name": f"{abbrev} {i}", "team_id": team_id, "age": age,
                "minutes_projection": minutes if i < 7 else 2.0}
               for team_id, abbrev in (("team_bos", "BOS"), ("team_nyk", "NYK")) for i in range(9)]
    canonical = {"teams": deepcopy(TEAMS), "players": players, "traits": [], "injury_events": [],
                 "player_health_states": [state(p["id"]) for p in players],
                 "save_team_records": {"team_bos": {"wins": 10, "losses": 10}, "team_nyk": {"wins": 10, "losses": 10}},
                 "_human_team_ids": list(human), "_coach_rest_team_ids": list(coach_rests)}
    return canonical


def run_days(canonical, days, seed=1):
    """The save's daily health pass: one call per calendar day with that day's games."""
    previous = "2026-11-09"
    for day in days:
        games = [g for g in GAMES if g["gameDate"] == day]
        result = health.simulate_health(".", canonical, previous, day, seed=seed, schedule=games)
        canonical["player_health_states"] = result["final_states"]
        previous = day
    return {s["player_id"]: s for s in canonical["player_health_states"]}


class FatigueModelTests(unittest.TestCase):
    PLAYER = {"age": 27.0}

    def test_gain_follows_minutes_age_stamina_and_road(self):
        gain = lambda **kw: health.fatigue_gain({"age": kw.get("age", 27.0)}, kw.get("minutes", 36.0), kw.get("stamina", 50.0),
                                                STAFF, kw.get("away", False))
        self.assertAlmostEqual(gain(), health.FATIGUE_GAIN_PER_36)
        self.assertAlmostEqual(gain(minutes=18.0), gain() / 2)
        self.assertGreater(gain(age=37.0), gain() * 1.25)
        self.assertGreater(gain(stamina=30.0), gain())
        self.assertLess(gain(stamina=80.0), gain())
        self.assertAlmostEqual(gain(away=True), gain() * health.FATIGUE_AWAY_MULTIPLIER)

    def test_recovers_by_calendar_day(self):
        s = state(fatigue=50.0, fatigue_date="2026-11-10")
        self.assertEqual(health.fatigue_on_date(s, "2026-11-10"), 50.0)
        self.assertAlmostEqual(health.fatigue_on_date(s, "2026-11-11"), 31.0, places=1)
        self.assertLess(health.fatigue_on_date(s, "2026-11-13"), 50.0 * 0.25)   # three days clear about three quarters
        better = {"recovery_days_multiplier": 0.86}
        self.assertLess(health.fatigue_on_date(s, "2026-11-12", better), health.fatigue_on_date(s, "2026-11-12"))

    def test_normal_schedule_back_to_back_and_rest_levels(self):
        """36 minutes every other day: about 50 right after a game, about 19 at the next tip-off; a back-to-back starts
        about 31; heavy minutes keep building through a dense stretch."""
        s, day = state(), date(2026, 11, 1)
        for _ in range(12):
            health.advance_state_for_date(s, day, 1, CONFIG, STAFF)
            tipoff = s["fatigue"]
            health.add_game_fatigue(s, self.PLAYER, 36.0, 50.0, 1, CONFIG, STAFF)
            day = date.fromordinal(day.toordinal() + 2)
        self.assertAlmostEqual(s["fatigue"], 50.0, delta=2.0)
        self.assertAlmostEqual(tipoff, 19.4, delta=1.5)
        back_to_back = health.fatigue_on_date(s, date.fromordinal(day.toordinal() - 1))
        self.assertAlmostEqual(back_to_back, 31.0, delta=1.5)
        self.assertAlmostEqual(health.normal_fatigue(self.PLAYER, 36.0), tipoff, delta=1.0)
        # four games in five nights at 40 minutes: deep into the red on the bar
        s = state()
        for offset in (0, 1, 3, 4):
            health.advance_state_for_date(s, date(2026, 12, 1 + offset), 0, CONFIG, STAFF)
            health.add_game_fatigue(s, self.PLAYER, 40.0, 50.0, 0, CONFIG, STAFF)
        self.assertGreater(s["fatigue"], 60.0)

    def test_injury_risk_rises_only_above_normal(self):
        self.assertEqual(health.fatigue_injury_multiplier(0.0), 1.0)
        self.assertEqual(health.fatigue_injury_multiplier(health.FATIGUE_REFERENCE), 1.0)
        self.assertAlmostEqual(health.fatigue_injury_multiplier(31.0), 1.2, delta=0.03)
        self.assertEqual(health.fatigue_injury_multiplier(200.0), health.FATIGUE_INJURY_CAP)

    def test_team_effect_matches_the_schedule_rule_on_a_typical_back_to_back(self):
        pool = lambda f: [{"player": {"id": str(i)}, "minutes": 240 / 8, "health_fatigue": f} for i in range(8)]
        self.assertIsNone(sim.team_fatigue_excess([{"player": {"id": "x"}, "minutes": 30.0}]))   # replays: schedule rule
        normal = sim.rest_effect({"rest_days": 1, "team_fatigue": sim.team_fatigue_excess(pool(sim.FATIGUE_TEAM_REFERENCE))})
        self.assertEqual(normal["offense"], 0.0)
        tired = sim.rest_effect({"rest_days": 0, "team_fatigue": sim.team_fatigue_excess(pool(sim.FATIGUE_TEAM_REFERENCE + 6))})
        self.assertAlmostEqual(tired["offense"], -1.5, delta=0.1)
        rested = sim.rest_effect({"rest_days": 3, "team_fatigue": sim.team_fatigue_excess(pool(0.0))})
        self.assertEqual(rested["offense"], sim.FATIGUE_TEAM_BONUS_CAP)
        self.assertEqual(sim.rest_effect({"rest_days": 0})["offense"], -1.35)

    def test_individual_penalty_only_when_very_tired(self):
        features = {"impact": 60.0}
        self.assertEqual(sim.health_adjusted_player_features(features, {"health_fatigue": 45.0}), features)
        self.assertLess(sim.health_adjusted_player_features(features, {"health_fatigue": 80.0})["impact"], 60.0)

    def test_rest_follows_fatigue(self):
        player = {"age": 31.0}
        base = {"games_left": 50, "rank": 15, "teams": 30, "regulars_out": 0, "rested_tonight": 0, "fatigue_normal": 19.0}
        normal, _, _ = health.rest_chance(player, state(), {**base, "fatigue": 19.0})
        b2b, _, reason = health.rest_chance(player, state(), {**base, "fatigue": 19.0 / health.FATIGUE_DAILY_KEEP, "back_to_back": True})
        heavy, _, heavy_reason = health.rest_chance(player, state(), {**base, "fatigue": 45.0})
        self.assertAlmostEqual(normal, 0.031)
        self.assertAlmostEqual(b2b, 0.095, places=3)        # the fitted back-to-back chance for his age
        self.assertEqual(reason, "second night of a back-to-back")
        self.assertGreater(heavy, b2b)
        self.assertIn("heavy recent workload", heavy_reason)


class EngineUsesFatigueTests(unittest.TestCase):
    def test_game_uses_tip_off_value_and_bar_shows_todays_value(self):
        canonical = league()
        states = run_days(canonical, ["2026-11-10", "2026-11-11"])
        s = states["bos0"]
        self.assertEqual(s["fatigue_game"]["date"], "2026-11-11")
        self.assertEqual(s["fatigue_date"], "2026-11-11")
        self.assertGreater(s["fatigue"], s["fatigue_game"]["value"])       # tonight's minutes added after tip-off
        # second night of a back-to-back: last night's game, recovered for one day
        self.assertGreater(s["fatigue_game"]["value"], 15.0)
        pool = health.sandbox_health_adjusted_pool(canonical, "2026-11-11", [{"player": {"id": "bos0"}, "minutes": 34.0}])
        self.assertEqual(pool[0]["health_fatigue"], s["fatigue_game"]["value"])
        label = sv.player_health_label(s, "2026-11-11")
        self.assertEqual(label["fatigue"], s["fatigue"])
        # a day without a game: recovery shows the next day
        states = run_days(canonical, ["2026-11-12"])
        self.assertAlmostEqual(states["bos0"]["fatigue"], round(s["fatigue"] * health.FATIGUE_DAILY_KEEP, 2), places=1)


class CoachRestToggleTests(unittest.TestCase):
    def rested(self, canonical, seed):
        states = run_days(canonical, ["2026-11-10", "2026-11-11"], seed)
        return sorted(pid for pid, s in states.items() if pid.startswith("bos") and s.get("games_rested"))

    def test_off_never_rests_on_follows_the_ai_rules(self):
        seen = 0
        for seed in range(1, 40):
            ai = self.rested(league(age=35.0), seed)
            self.assertEqual(self.rested(league(age=35.0, human=["team_bos"]), seed), [])                  # toggle off
            self.assertEqual(self.rested(league(age=35.0, human=["team_bos"], coach_rests=["team_bos"]), seed), ai)
            seen += bool(ai)
        self.assertGreater(seen, 0)

    def test_setting_defaults_off_and_feeds_the_engine(self):
        save = {"meta": {"user_team_id": "team_bos"}}
        self.assertFalse(sv.ensure_game_settings(save)["coach_rests_players"])
        self.assertEqual(sv.coach_rest_team_ids(save), [])
        save["game_settings"]["coach_rests_players"] = True
        self.assertEqual(sv.coach_rest_team_ids(save), ["team_bos"])


class UserRestTests(unittest.TestCase):
    def test_sits_next_n_games_recovers_and_comes_back(self):
        canonical = league()
        bos0 = next(s for s in canonical["player_health_states"] if s["player_id"] == "bos0")
        bos0.update(fatigue=40.0, fatigue_date="2026-11-09",
                    user_rest={"games_left": 2, "games": 2, "since": "2026-11-09", "team_id": "team_bos"})
        self.assertTrue(sv.player_unavailable_for_rotation(bos0))
        states = run_days(canonical, ["2026-11-10"])
        s = states["bos0"]
        self.assertEqual((s["user_rest"]["games_left"], s["rest_date"], s["rest_reason"]), (1, "2026-11-10", "rested by the GM"))
        self.assertEqual(health.sandbox_health_adjusted_pool(canonical, "2026-11-10", [{"player": {"id": "bos0"}, "minutes": 34.0}]), [])
        states = run_days(canonical, ["2026-11-11"])
        s = states["bos0"]
        self.assertNotIn("user_rest", s)
        self.assertEqual((s["games_rested"], s["rest_date"]), (2, "2026-11-11"))
        self.assertAlmostEqual(s["fatigue"], 40.0 * health.FATIGUE_DAILY_KEEP ** 2, delta=0.1)   # rested like days off
        self.assertTrue(sv.player_unavailable_for_rotation(s))          # tonight still
        states = run_days(canonical, ["2026-11-12", "2026-11-13"])
        s = states["bos0"]
        self.assertFalse(sv.player_unavailable_for_rotation(s))
        self.assertEqual(s["fatigue_game"]["date"], "2026-11-13")       # he plays again
        pool = health.sandbox_health_adjusted_pool(canonical, "2026-11-13", [{"player": {"id": "bos0"}, "minutes": 34.0}])
        self.assertEqual(len(pool), 1)

    def test_minutes_target_kept_while_resting_and_restored_after(self):
        roster = [{"id": f"p{i}", "name": f"P{i}", "position": pos, "height_inches": h}
                  for i, (pos, h) in enumerate([("PG", 75), ("SG", 77), ("SF", 79), ("PF", 81), ("C", 84),
                                                 ("PG", 74), ("SF", 79), ("C", 83), ("SG", 77), ("PF", 81)])]
        override = {"p0": 34, "p1": 32, "p2": 32, "p3": 30, "p4": 32, "p5": 20, "p6": 20, "p7": 16, "p8": 24, "p9": 0}
        resting = {"p0": state("p0", user_rest={"games_left": 2, "games": 2, "team_id": "t"})}
        canonical = {"players": roster, "teams": [{"id": "t"}], "traits": []}
        with patch.object(sv, "player_attribute_summary", lambda canonical, pid: {"overall": 55.0}):
            during = sv.user_rotation_override_projection(roster, resting, override, canonical=canonical, save={}, team_id="t")
            after = sv.user_rotation_override_projection(roster, {}, override, canonical=canonical, save={}, team_id="t")
        self.assertEqual(during["p0"], 0.0)
        self.assertEqual(sum(during.values()), 240.0)
        self.assertTrue(all(during[pid] >= target for pid, target in override.items() if pid != "p0"))
        self.assertEqual(after, {pid: float(v) for pid, v in override.items()})
        self.assertEqual(override["p0"], 34)


class RestActionTests(unittest.TestCase):
    def setUp(self):
        from nba_gm_data import app_actions as aa
        self.aa = aa
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "s.json"
        self.canonical = {"teams": deepcopy(TEAMS), "players": [
            {"id": "bos0", "name": "Star", "team_id": "team_bos"}, {"id": "nyk0", "name": "Other", "team_id": "team_nyk"}]}
        self.save = {"meta": {"user_team_id": "team_bos"}, "state": {"current_date": "2027-02-10", "phase": "regular_season"},
                     "team_records": {"team_bos": {"wins": 30, "losses": 30}},
                     "player_season_stats": {"bos0": {"games": 45}},
                     "health_states": [state("bos0")]}
        self.path.write_text(json.dumps(self.save))
        for name, value in (("load_save", lambda p: json.loads(Path(p).read_text())),
                            ("ensure_league_save_defaults", lambda s, c: s),
                            ("canonical_with_save", lambda c, s: c),
                            ("write_save", lambda p, s: Path(p).write_text(json.dumps(s))),
                            ("team_dashboard", lambda *a, **k: {"team": "BOS"})):
            patcher = patch.object(aa, name, side_effect=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def act(self, **payload):
        return self.aa.set_player_rest_action(Path("."), self.canonical, self.path, payload)

    def stored(self):
        return json.loads(self.path.read_text())["health_states"][0]

    def test_rest_cancel_and_award_warning(self):
        result = self.act(player_id="bos0", games=2)     # 45 played + 22 left = 67 -> 65 after two games: still fine
        self.assertEqual((result["status"], result["warning"]), ("updated", ""))
        self.assertEqual(self.stored()["user_rest"], {"games_left": 2, "games": 2, "since": "2027-02-10", "team_id": "team_bos"})
        result = self.act(player_id="bos0", games=3)     # 64 at most: under the award rule
        self.assertIn("at most 64 games", result["warning"])
        self.assertIn("65", result["warning"])
        self.act(player_id="bos0", games=0)
        self.assertNotIn("user_rest", self.stored())

    def test_only_own_healthy_players_and_one_to_five_games(self):
        with self.assertRaises(self.aa.AppActionError):
            self.act(player_id="nyk0", games=2)
        with self.assertRaises(self.aa.AppActionError):
            self.act(player_id="bos0", games=6)
        saved = json.loads(self.path.read_text())
        saved["health_states"][0].update(availability_status="out", current_injury_id="x")
        self.path.write_text(json.dumps(saved))
        self.assertEqual(self.act(player_id="bos0", games=2)["status"], "blocked")

    def test_award_outlook_counts_the_rest(self):
        self.assertEqual(sv.award_games_max(45, 60, {}), 67)
        self.assertEqual(sv.award_games_max(45, 60, {"user_rest": {"games_left": 3}}), 64)

    def test_toggle_setting_action(self):
        result = self.aa.update_game_settings_action(self.canonical, self.path, {"coach_rests_players": True})
        self.assertTrue(result["game_settings"]["coach_rests_players"])
        self.assertTrue(json.loads(self.path.read_text())["game_settings"]["coach_rests_players"])


if __name__ == "__main__":
    unittest.main()
