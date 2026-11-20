"""National TV games, the refitted age shape of rest, and season-start injuries (OVERNIGHT-REST-GAMES, 2026-11-20)."""
from collections import Counter
from pathlib import Path
import unittest
from unittest.mock import patch

from nba_gm_data import health
from nba_gm_data import national_tv as tv
from nba_gm_data import rest_model as rm
from nba_gm_data import save as sv

ROOT = Path(__file__).resolve().parents[1]
PLAYER = {"id": "p", "age": 28.0, "minutes_projection": 32.0}
BASE = {"games_left": 50, "rank": 15, "teams": 30, "situation": "race", "opp_wins": 15, "opp_losses": 15, "home": True,
        "rested_tonight": 0, "regulars_out": 0}


def state(**extra):
    return {"player_id": "p", "fatigue": 0.0, "availability_status": "active", "current_injury_id": None, "rust": 0.0,
            "games_missed": 0, **extra}


def odds(player=PLAYER, **context):
    p = rm.rest_assessment(player, state(), {**BASE, **context})["chance"]
    return p / (1.0 - p)


class NationalTvRestTests(unittest.TestCase):
    def test_national_tv_lowers_rest(self):
        ratio = odds(national_tv=True) / odds()
        self.assertAlmostEqual(ratio, 0.735, delta=0.01)          # real 2025-26: x0.73
        self.assertLess(odds(back_to_back=True, national_tv=True), odds(back_to_back=True))

    def test_reason_never_cites_tv(self):
        reason = rm.rest_assessment(PLAYER, state(), {**BASE, "back_to_back": True, "national_tv": True})["reason"]
        self.assertNotIn("TV", reason)

    def test_game_context_reads_the_schedule_flag(self):
        game = {"externalGameId": "g1", "gameDate": "2026-11-10", "homeTeamId": "2", "awayTeamId": "18", "national_tv": True}
        ctx = health.game_rest_context({}, {}, game, "2", "team_bos", "team_nyk")
        self.assertTrue(ctx["national_tv"])
        self.assertFalse(health.game_rest_context({}, {}, {**game, "national_tv": False}, "2", "team_bos", "team_nyk")["national_tv"])


class AgeShapeTests(unittest.TestCase):
    def test_thirty_and_over_rest_more_on_back_to_backs_only(self):
        young, old = {**PLAYER, "age": 28.0}, {**PLAYER, "age": 31.0}
        self.assertAlmostEqual(odds(old) / odds(young), 1.0, places=6)                       # ordinary nights: flat after 27
        self.assertAlmostEqual(odds(old, back_to_back=True) / odds(young, back_to_back=True), 1.775, delta=0.01)
        self.assertAlmostEqual(odds(old, first_of_b2b=True) / odds(young, first_of_b2b=True), 1.775, delta=0.01)

    def test_young_players_rest_less(self):
        self.assertAlmostEqual(odds({**PLAYER, "age": 23.0}) / odds({**PLAYER, "age": 27.0}), 0.678, delta=0.01)   # x0.91 a year
        self.assertAlmostEqual(odds({**PLAYER, "age": 19.0}), odds({**PLAYER, "age": 21.0}), places=9)

    def test_older_back_to_back_reason(self):
        reason = rm.rest_assessment({**PLAYER, "age": 33.0}, state(), {**BASE, "back_to_back": True, "home": False})["reason"]
        self.assertIn("second night of a back-to-back on the road", reason)
        self.assertIn("age 33", reason)


class NationalTvSlateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = sv.generate_future_schedule(ROOT, "2026-27", 2026)["games"]
        # ESPN team 1 most appealing ... team 30 least
        cls.appeal = {str(i): (30 - i) / 10.0 for i in range(1, 31)}

    def test_slate_size_shape_and_determinism(self):
        games = [dict(g) for g in self.games]
        chosen = tv.mark_national_tv(games, self.appeal, "2026-27")
        self.assertEqual(chosen, sum(1 for g in games if g.get("national_tv")))
        self.assertAlmostEqual(chosen, 246, delta=6)
        counts = tv.national_tv_counts(games)
        ranked = sorted((counts.get(str(i), 0) for i in range(1, 31)), reverse=True)
        self.assertGreater(sum(ranked[:10]) / sum(ranked), 0.55)                                    # real: 63%
        self.assertLess(sum(ranked[-10:]) / sum(ranked), 0.12)                                       # real: 7%
        self.assertGreater(counts.get("1", 0), counts.get("30", 0) + 20)
        nights = Counter(g["gameDate"] for g in games if g.get("national_tv"))
        self.assertTrue(all(n <= 3 for day, n in nights.items() if not day.endswith("12-25")))
        self.assertTrue(all(g.get("national_tv") for g in games if g["gameDate"].endswith("12-25")))
        again = [dict(g) for g in self.games]
        tv.mark_national_tv(again, self.appeal, "2026-27")
        self.assertEqual([g.get("national_tv") for g in games], [g.get("national_tv") for g in again])

    def test_market_and_roster_appeal(self):
        teams = [{"id": "team_nyk", "abbrev": "NYK"}, {"id": "team_uta", "abbrev": "UTA"}, {"id": "team_okc", "abbrev": "OKC"}]
        players = [{"id": f"{t}_{k}", "team_id": t} for t in ("team_nyk", "team_uta", "team_okc") for k in range(8)]
        overall = {p["id"]: (80.0 if p["team_id"] == "team_okc" else 60.0) for p in players}
        appeal = tv.team_appeal({"teams": teams, "players": players}, overall=overall)
        self.assertGreater(appeal["team_okc"], appeal["team_nyk"])      # the best roster first
        self.assertGreater(appeal["team_nyk"], appeal["team_uta"])      # same roster, bigger market
        records = {"team_nyk": {"wins": 20, "losses": 62}, "team_uta": {"wins": 62, "losses": 20}, "team_okc": {"wins": 41, "losses": 41}}
        with_records = tv.team_appeal({"teams": teams, "players": players}, records, overall=overall)
        self.assertGreater(with_records["team_uta"], appeal["team_uta"])

    def test_save_calendar_shows_the_flag(self):
        game = {"externalGameId": "g1", "gameDate": "2026-11-10", "homeTeamId": "2", "awayTeamId": "18", "phase": "regular",
                "national_tv": True}
        canonical = {"teams": [{"id": "team_bos", "abbrev": "BOS"}, {"id": "team_nyk", "abbrev": "NYK"}]}
        save = {"meta": {"season": "2026-27"}, "state": {"current_date": "2026-11-01"},
                "season_schedules": {"2026-27": {"games": [game]}}}
        view = sv.calendar_view(ROOT, canonical, "unused.json", "2026-11-01", "2026-11-30", prepared_save=save)
        self.assertTrue(view["games"][0]["national_tv"])


TEAMS = [{"id": "team_bos", "abbrev": "BOS"}, {"id": "team_nyk", "abbrev": "NYK"}]
SCHEDULE = [{"externalGameId": f"g{i}", "gameDate": f"2026-10-{20 + i:02d}", "homeTeamId": "2" if i % 2 else "18",
             "awayTeamId": "18" if i % 2 else "2", "phase": "regular"} for i in range(1, 9)]
PLAYERS = [{"id": "star", "team_id": "team_bos", "age": 27.0, "minutes_projection": 34.0, "position": "SF"},
           {"id": "bench", "team_id": "team_nyk", "age": 24.0, "minutes_projection": 12.0, "position": "PG"},
           {"id": "free", "team_id": None, "age": 30.0, "minutes_projection": 0.0}]


def start_model(offseason=0.0, carried=0.0, cases=((3, "ankle"),)):
    return {"offseason_rate": offseason, "carried_rate": carried, "regular_minutes": 25.0,
            "offseason_cases": [list(c) for c in cases], "carried_cases": [list(c) for c in cases]}


class SeasonStartInjuryTests(unittest.TestCase):
    def run_start(self, model, carried=True, seed=7):
        canonical = {"teams": TEAMS, "players": PLAYERS, "traits": [], "injury_events": []}
        states = [{"player_id": "star", "availability_status": "active", "current_injury_id": None}]
        with patch.object(health, "_season_start_model", return_value=model):
            events = health.season_start_injuries(ROOT, canonical, states, SCHEDULE, "2026-27", seed, carried=carried)
        return events, {s["player_id"]: s for s in states}

    def test_out_for_exactly_the_drawn_games(self):
        events, states = self.run_start(start_model(offseason=5.0))
        self.assertEqual(sorted(e["player_id"] for e in events), ["bench", "star"])    # rostered players only
        star = next(e for e in events if e["player_id"] == "star")
        self.assertEqual(star["expected_games_missed"], 3)
        self.assertEqual(star["return_date"], "2026-10-24")          # his team's fourth game: misses the first three
        self.assertLess(star["start_date"], "2026-10-21")
        self.assertEqual(star["season_start"], "offseason")
        self.assertEqual(states["star"]["availability_status"], "out")
        self.assertEqual(states["star"]["current_injury_id"], star["id"])
        self.assertFalse(health.player_available_on_date(states["star"], health.parse_date("2026-10-23")))
        self.assertTrue(health.player_available_on_date(states["star"], health.parse_date("2026-10-24")))

    def test_whole_season_and_carried_only_for_a_new_career(self):
        events, _ = self.run_start(start_model(carried=5.0, cases=((82, "achilles"),)))
        self.assertTrue(events and all(e["season_start"] == "carried" and e["return_date"] == "2027-06-30" for e in events))
        none, _ = self.run_start(start_model(carried=5.0), carried=False)
        self.assertEqual(none, [])

    def test_seeded_and_rare_at_real_rates(self):
        a, _ = self.run_start(start_model(offseason=0.5), seed=3)
        b, _ = self.run_start(start_model(offseason=0.5), seed=3)
        self.assertEqual([e["id"] for e in a], [e["id"] for e in b])
        nobody, _ = self.run_start(start_model())
        self.assertEqual(nobody, [])

    def test_already_injured_players_are_left_alone(self):
        canonical = {"teams": TEAMS, "players": PLAYERS, "traits": [], "injury_events": []}
        states = [{"player_id": "star", "availability_status": "out", "current_injury_id": "inj_old", "return_date": "2026-11-30"}]
        with patch.object(health, "_season_start_model", return_value=start_model(offseason=5.0)):
            events = health.season_start_injuries(ROOT, canonical, states, SCHEDULE, "2026-27", 1, carried=True)
        self.assertNotIn("star", [e["player_id"] for e in events])
        self.assertEqual(states[0]["current_injury_id"], "inj_old")

    def test_real_rates_file(self):
        model = health._season_start_model(str(ROOT / health.SEASON_START_FILE))
        self.assertAlmostEqual(model["offseason_rate"], 0.033, places=3)
        self.assertAlmostEqual(model["carried_rate"], 0.046, places=3)
        self.assertEqual(len(model["offseason_cases"]), len(model["carried_cases"]))
        self.assertTrue(all(1 <= g <= 82 for g, _ in model["offseason_cases"] + model["carried_cases"]))


if __name__ == "__main__":
    unittest.main()
