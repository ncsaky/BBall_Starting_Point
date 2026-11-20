"""Rest decisions fitted to real 2025-26 patterns, travel from arena locations, and fatigue from the minutes actually
played (SMART-REST, 2026-11-19)."""
import unittest
from copy import deepcopy

from nba_gm_data import health
from nba_gm_data import rest_model as rm
from nba_gm_data import save as sv

TEAMS = [{"id": "team_bos", "abbrev": "BOS", "conference": "East"}, {"id": "team_nyk", "abbrev": "NYK", "conference": "East"}]
GAMES = [  # BOS: home 11-10, at NY 11-11 (back-to-back), at LAL 11-13, at GS 11-14, at POR 11-16
    {"externalGameId": "g1", "gameDate": "2026-11-10", "homeTeamId": "2", "awayTeamId": "18", "phase": "regular"},
    {"externalGameId": "g2", "gameDate": "2026-11-11", "homeTeamId": "18", "awayTeamId": "2", "phase": "regular"},
    {"externalGameId": "g3", "gameDate": "2026-11-13", "homeTeamId": "13", "awayTeamId": "2", "phase": "regular"},
    {"externalGameId": "g4", "gameDate": "2026-11-14", "homeTeamId": "9", "awayTeamId": "2", "phase": "regular"},
    {"externalGameId": "g5", "gameDate": "2026-11-16", "homeTeamId": "22", "awayTeamId": "2", "phase": "regular"},
]
PLAYER = {"id": "p", "age": 29.0, "minutes_projection": 32.0}
BASE = {"games_left": 50, "rank": 15, "teams": 30, "situation": "race", "opp_wins": 15, "opp_losses": 15, "home": True,
        "rested_tonight": 0, "regulars_out": 0}


def state(pid="p", **extra):
    return {"player_id": pid, "fatigue": 0.0, "availability_status": "active", "current_injury_id": None, "rust": 0.0,
            "games_missed": 0, **extra}


def chance(player=PLAYER, st=None, **context):
    return rm.rest_assessment(player, st or state(), {**BASE, **context})["chance"]


class TravelTests(unittest.TestCase):
    def test_all_thirty_arenas(self):
        arenas = rm.arenas()
        self.assertEqual(len(arenas), 30)
        self.assertTrue(all(-9 <= a["utc_offset"] <= -4 and 24 < a["lat"] < 50 for a in arenas.values()))

    def test_distances(self):
        a = rm.arenas()
        self.assertAlmostEqual(rm.miles_between(a["2"], a["13"]), 2600, delta=40)      # Boston to Los Angeles
        self.assertLess(rm.miles_between(a["17"], a["18"]), 10)                          # Brooklyn to Madison Square Garden
        self.assertEqual(rm.miles_between(a["2"], a["2"]), 0.0)

    def test_schedule_context(self):
        ctx = rm.team_schedule_context(GAMES, "2")
        self.assertEqual(ctx["g1"]["miles"], 0.0)
        self.assertTrue(ctx["g1"]["first_of_b2b"] and not ctx["g1"]["back_to_back"])
        self.assertTrue(ctx["g2"]["back_to_back"] and not ctx["g2"]["home"])
        self.assertAlmostEqual(ctx["g2"]["miles"], 190, delta=10)
        self.assertEqual(ctx["g3"]["tz_change"], -3.0)                                    # New York to Los Angeles
        self.assertEqual([ctx[g]["road_trip"] for g in ("g1", "g2", "g3", "g4", "g5")], [0, 1, 2, 3, 4])
        self.assertEqual(ctx["g4"]["games_last_4"], 3)
        self.assertEqual(ctx["g2"]["opponent_espn_id"], "18")


class RestModelTests(unittest.TestCase):
    def test_back_to_back_nights(self):
        other, first, second = chance(), chance(first_of_b2b=True), chance(back_to_back=True)
        self.assertLess(other, first)
        self.assertLess(first, second)
        self.assertGreater(chance(back_to_back=True, home=False), second)                 # road second nights more

    def test_opponent_strength(self):
        weak = chance(opp_wins=10, opp_losses=40)
        middle = chance(opp_wins=33, opp_losses=17)                                       # a good playoff team: least rest
        best = chance(opp_wins=45, opp_losses=5)                                          # the very best: more again
        self.assertGreater(weak, middle * 1.5)
        self.assertGreater(best, middle)

    def test_player_factors(self):
        self.assertGreater(chance({**PLAYER, "age": 34.0}), chance({**PLAYER, "age": 24.0}))
        self.assertGreater(chance(star=True), chance(star=False))
        self.assertLess(chance({**PLAYER, "minutes_projection": 37.0}), chance({**PLAYER, "minutes_projection": 27.0}))
        back = state(return_absence_games=4, games_since_return=2)
        self.assertGreater(chance(st=back, back_to_back=True), 1.8 * chance(back_to_back=True))
        self.assertEqual(chance(st=back), chance())                                        # only on back-to-backs

    def test_season_and_race(self):
        self.assertGreater(chance(games_left=30), chance(games_left=70))
        self.assertGreater(chance(games_left=12, situation="locked"), 2 * chance(games_left=12, situation="race"))
        self.assertLess(chance(road_trip=3, home=False), chance(road_trip=1, home=False))

    def test_travel_does_not_change_the_chance(self):
        self.assertEqual(chance(back_to_back=True, home=False, miles=2500.0, tz_change=-3.0),
                         chance(back_to_back=True, home=False, miles=100.0, tz_change=0.0))

    def test_rules(self):
        self.assertGreater(chance(rested_tonight=1), 0.0)                                 # a second regular can sit
        self.assertEqual(chance(rested_tonight=2), 0.0)
        self.assertEqual(chance(star=True, stars_rested_tonight=1, rested_tonight=1), 0.0)   # one star a game
        self.assertGreater(chance(star=False, stars_rested_tonight=1, rested_tonight=1), 0.0)
        self.assertEqual(chance(regulars_out=3), 0.0)
        self.assertEqual(chance(st=state(games_missed=10, games_rested=4)), 0.0)           # 65-game award rule

    def test_final_games_and_shutdowns(self):
        self.assertEqual(chance(games_left=1, situation="locked", worst_seed=3), rm.REST_FINAL[1]["locked_playoff"])
        self.assertEqual(chance(games_left=1, situation="race"), rm.REST_FINAL[1]["race"])
        self.assertEqual(chance(games_left=2, situation="locked", worst_seed=9), rm.REST_FINAL[2]["locked"])
        shut = rm.rest_assessment(PLAYER, state(), {**BASE, "games_left": 20, "rank": 28, "situation": "out"})
        self.assertEqual(shut["shutdown_chance"], rm.SHUTDOWN_HAZARD)
        self.assertGreater(shut["chance"], rm.SHUTDOWN_HAZARD)                            # ordinary rest nights too
        self.assertEqual(rm.rest_decision(shut, 0.01)[0], "shutdown")
        self.assertEqual(rm.rest_decision(shut, (rm.SHUTDOWN_HAZARD + shut["chance"]) / 2)[0], "rest")
        self.assertIsNone(rm.rest_decision(shut, shut["chance"] + 0.001))
        blocked = rm.rest_assessment(PLAYER, state(games_missed=14), {**BASE, "games_left": 20, "rank": 28})
        self.assertEqual(blocked["chance"], rm.SHUTDOWN_HAZARD)                            # shutdowns are not rest nights

    def test_reason_in_plain_words(self):
        result = rm.rest_assessment({**PLAYER, "age": 33.0}, state(),
                                    {**BASE, "back_to_back": True, "home": False, "opp_wins": 12, "opp_losses": 40})
        self.assertTrue(result["reason"].startswith("second night of a back-to-back on the road"))
        self.assertIn("opponent 12-40", result["reason"])
        self.assertIn("age 33", result["reason"])
        self.assertEqual(rm.rest_assessment(PLAYER, state(), {**BASE, "games_left": 75})["reason"], "maintenance day")

    def test_heavy_workload_beyond_a_back_to_back(self):
        normal = chance(fatigue=19.0, fatigue_normal=19.0)
        heavy = rm.rest_assessment(PLAYER, state(), {**BASE, "fatigue": 50.0, "fatigue_normal": 19.0})
        self.assertGreater(heavy["chance"], normal * 1.3)
        self.assertIn("heavy recent workload", heavy["reason"])
        self.assertEqual(chance(fatigue=19.0 / 0.62, fatigue_normal=19.0), normal)         # a typical back-to-back load: no extra


class StandingsTests(unittest.TestCase):
    def test_situations(self):
        conf = {t: "East" for t in "abcdefghijkl"}
        # 80 of 82 games played: 'a' has clinched first; 'l' cannot reach tenth; the middle is still racing
        wins = dict(zip("abcdefghijkl", [65, 55, 50, 49, 48, 46, 45, 44, 43, 42, 30, 20]))
        records = {t: {"wins": w, "losses": 80 - w} for t, w in wins.items()}
        st = rm.league_standings(records, conf)
        self.assertEqual(st["a"]["situation"], "locked")
        self.assertEqual(st["a"]["worst_seed"], 1)
        self.assertEqual(st["e"]["situation"], "race")
        self.assertEqual(st["l"]["games_left"], 2)
        self.assertEqual(st["l"]["best_seed"], 12)
        self.assertEqual(st["l"]["situation"], "out")           # cannot reach tenth and in the bottom eight
        records_30 = {f"t{i}": {"wins": 60 - 2 * i, "losses": 20 + 2 * i} for i in range(30)}
        conf_30 = {f"t{i}": "East" if i % 2 else "West" for i in range(30)}
        st30 = rm.league_standings(records_30, conf_30)
        self.assertEqual(st30["t29"]["situation"], "out")


class BoxScoreFatigueTests(unittest.TestCase):
    def league(self):
        players = [{"id": f"bos{i}", "team_id": "team_bos", "age": 27.0, "minutes_projection": 34.0 if i < 7 else 2.0}
                   for i in range(9)] + [{"id": f"nyk{i}", "team_id": "team_nyk", "age": 27.0, "minutes_projection": 34.0 if i < 7 else 2.0}
                                         for i in range(9)]
        return {"teams": deepcopy(TEAMS), "players": players, "traits": [], "injury_events": [],
                "player_health_states": [state(p["id"]) for p in players]}

    def test_fatigue_from_minutes_played(self):
        canonical = self.league()
        result = health.simulate_health(".", canonical, "2026-11-09", "2026-11-10", seed=1, schedule=GAMES[:1], box_score_fatigue=True)
        states = result["final_states"]
        by_id = {s["player_id"]: s for s in states}
        self.assertEqual(by_id["bos0"]["fatigue"], 0.0)                         # planned minutes no longer add fatigue
        self.assertEqual(by_id["bos0"]["fatigue_game"]["date"], "2026-11-10")
        box = {"game_id": "g1", "away_team_id": "team_nyk", "player_lines": [
            {"player_id": "bos0", "team_id": "team_bos", "minutes": 46.0},     # overtime
            {"player_id": "bos1", "team_id": "team_bos", "minutes": 24.0},     # sat the fourth quarter of a blowout
            {"player_id": "bos7", "team_id": "team_bos", "minutes": 0.0},
            {"player_id": "nyk0", "team_id": "team_nyk", "minutes": 24.0}]}
        self.assertEqual(health.add_box_score_fatigue(canonical, states, box, "2026-11-10"), 3)
        gain = lambda m, away=False: health.fatigue_gain({"age": 27.0}, m, 50.0, health.performance_staff_modifiers(canonical, "team_bos"), away)
        self.assertAlmostEqual(by_id["bos0"]["fatigue"], gain(46.0), places=1)
        self.assertAlmostEqual(by_id["bos1"]["fatigue"], gain(24.0), places=1)
        self.assertEqual(by_id["bos7"]["fatigue"], 0.0)
        self.assertGreater(by_id["nyk0"]["fatigue"], by_id["bos1"]["fatigue"])  # road game
        before = by_id["bos0"]["fatigue"]
        health.add_box_score_fatigue(canonical, states, box, "2026-11-10")      # the same game twice adds nothing
        self.assertEqual(by_id["bos0"]["fatigue"], before)
        # next day: recovered by one day before tonight's tip-off
        canonical["player_health_states"] = states
        nxt = health.simulate_health(".", canonical, "2026-11-10", "2026-11-11", seed=1, schedule=GAMES[1:2], box_score_fatigue=True)
        s = {x["player_id"]: x for x in nxt["final_states"]}["bos0"]
        self.assertAlmostEqual(s["fatigue_game"]["value"], before * health.FATIGUE_DAILY_KEEP, places=1)

    def test_planned_minutes_without_box_scores(self):
        canonical = self.league()
        states = health.simulate_health(".", canonical, "2026-11-09", "2026-11-10", seed=1, schedule=GAMES[:1])["final_states"]
        self.assertGreater({s["player_id"]: s for s in states}["bos0"]["fatigue"], 20.0)


class LogTests(unittest.TestCase):
    def test_rest_decisions_are_logged_with_reasons(self):
        save = {}
        rows = [{"date": "2026-11-11", "game_id": "g2", "team_id": "team_bos", "player_id": "bos0", "kind": "rest",
                 "reason": "second night of a back-to-back on the road", "chance": 0.08, "factors": {"second_night": 2.58}}]
        sv.record_rest_decisions(save, rows)
        sv.record_rest_decisions(save, rows)
        self.assertEqual(len(save["rest_log"]), 1)
        self.assertEqual(save["rest_log"][0]["reason"], "second night of a back-to-back on the road")
        self.assertNotIn("factors", save["rest_log"][0])
        sv.record_rest_decisions(save, [{**rows[0], "date": "2027-11-02", "game_id": "g9"}])  # a new season clears the old one
        self.assertEqual([r["game_id"] for r in save["rest_log"]], ["g9"])


if __name__ == "__main__":
    unittest.main()
