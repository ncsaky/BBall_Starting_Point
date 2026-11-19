"""Injuries during games, rust and the minutes limit after a return, and coach rest (INJURY-REST, 2026-11-19)."""
import random
import unittest
from datetime import date

from nba_gm_data import game_minutes as gm
from nba_gm_data import health
from nba_gm_data import injury_model as im

STAFF = {"recovery_days_multiplier": 1.0}
CONFIG = health.default_injury_model_config()


def state(**extra):
    return {"player_id": "p", "fatigue": 0.0, "availability_status": "active", "current_injury_id": None, "rust": 0.0,
            "games_missed": 0, **extra}


class InjuryTimingTests(unittest.TestCase):
    def pending(self):
        return state(pending_injury={"id": "inj", "start_date": "2026-11-10", "return_date": "2026-11-20",
                                     "severity": "short", "body_part": "ankle", "diagnosis": "ankle sprain"})

    def test_hurt_player_finishes_his_game_and_misses_from_the_next(self):
        s = self.pending()
        health.advance_state_for_date(s, date(2026, 11, 10), 0, CONFIG, STAFF)   # same day: still active
        self.assertEqual(s["availability_status"], "active")
        health.advance_state_for_date(s, date(2026, 11, 11), 0, CONFIG, STAFF)
        self.assertEqual(s["availability_status"], "out")
        self.assertEqual(s["current_injury_label"], "ankle sprain")
        self.assertNotIn("pending_injury", s)

    def test_event_does_not_block_the_injury_game(self):
        event = {"start_date": "2026-11-10", "return_date": "2026-11-20", "plays_injury_game": True,
                 "in_game_exit": True, "exit_share": 0.3, "diagnosis": "ankle sprain"}
        self.assertIsNone(health.active_injury_event_on_date([event], date(2026, 11, 10)))
        self.assertIs(health.active_injury_event_on_date([event], date(2026, 11, 11)), event)
        canonical = {"player_health_states": [state(player_id="p")], "injury_events": [{**event, "player_id": "p"}]}
        pool = [{"player": {"id": "p"}, "minutes": 30.0}]
        tonight = health.sandbox_health_adjusted_pool(canonical, "2026-11-10", pool)
        self.assertEqual(tonight[0]["health_injury_exit"], 0.3)
        self.assertEqual(health.sandbox_health_adjusted_pool(canonical, "2026-11-11", pool), [])

    def test_in_game_share_rises_with_severity_and_never_for_illness(self):
        shares = [im.in_game_share(days, "ankle") for days in (1, 2, 4, 10, 20, 50, 200)]
        self.assertEqual(shares, sorted(shares))
        self.assertGreater(shares[-1], 0.6)
        self.assertEqual(im.in_game_share(10, "illness"), 0.0)


class ReturnTests(unittest.TestCase):
    def returned(self, missed):
        s = state(current_injury_id="inj", availability_status="out", return_date="2026-12-01", current_absence_games=missed)
        health.advance_state_for_date(s, date(2026, 12, 1), 1, CONFIG, STAFF)
        return s

    def test_rust_by_games_missed(self):
        self.assertEqual(self.returned(1)["rust"], 0.0)
        values = [self.returned(n)["rust"] for n in (2, 4, 8, 15, 30)]
        self.assertEqual(values, sorted(values))
        self.assertGreater(values[0], 0)
        self.assertLessEqual(values[-1] * 0.08, 2.0)   # at most ~1.6 rating points

    def test_rust_fades_per_game_played_not_per_day(self):
        s = self.returned(8)
        start = s["rust"]
        health.advance_state_for_date(s, date(2026, 12, 5), 3, CONFIG, STAFF)   # days pass, no games
        self.assertEqual(s["rust"], start)
        health.advance_return_ramp(s, date(2026, 12, 5), STAFF)                # first game back: full rust
        self.assertEqual(s["rust"], start)
        self.assertEqual(s["games_since_return"], 0)
        health.advance_return_ramp(s, date(2026, 12, 7), STAFF)                # second game
        self.assertEqual(s["games_since_return"], 1)
        self.assertAlmostEqual(s["rust"], start - im.RUST_DECAY_PER_GAME)
        for day in range(9, 30, 2):
            if s.get("return_absence_games"):
                health.advance_return_ramp(s, date(2026, 12, day), STAFF)
        self.assertNotIn("return_absence_games", s)                             # ramp over (8 games)
        self.assertEqual(s["rust"], 0.0)

    def test_minutes_limit_grows_with_absence(self):
        first = [im.return_minutes_multiplier(n, 0) for n in (1, 2, 4, 8, 15, 30)]
        self.assertEqual(first, sorted(first, reverse=True))
        self.assertLess(first[-1], 0.65)

    def test_display_fields(self):
        from nba_gm_data.sim import rust_display
        s = self.returned(8)
        shown = rust_display(s)
        self.assertGreater(shown["rust_penalty"], 0)
        self.assertEqual(shown["minutes_limit_games"], im.return_ramp_length(8))
        self.assertLess(shown["minutes_limit_pct"], 100)
        s["rest_suggestion"] = {"date": "2026-12-02", "reason": "second night of a back-to-back", "kind": "rest"}
        self.assertEqual(rust_display(s)["rest_suggestion"]["kind"], "rest")


class InGameExitTests(unittest.TestCase):
    TARGETS = [36, 33, 31, 29, 27, 24, 21, 16, 12, 8, 3]
    POS = ["PG", "SG", "SF", "PF", "C", "PG", "SG", "SF", "PF", "C", "C"]

    def pool(self, exit_share=None):
        rows = [{"player": {"id": f"p{i}", "position": self.POS[i]}, "minutes": float(m)} for i, m in enumerate(self.TARGETS)]
        if exit_share is not None:
            rows[4] = {**rows[4], "health_injury_exit": exit_share}
        return rows

    def run_game(self, exit_share=None, game=1, margin=3):
        return gm.manage_game_minutes(self.pool(exit_share), [], margin, random.Random(f"g{game}"), random.Random(f"f{game}"))

    def test_injured_player_leaves_and_bench_absorbs(self):
        for game in range(30):
            base, _, _ = self.run_game(None, game)
            hurt, _, _ = self.run_game(0.25, game)
            by_id = {row["player"]["id"]: row for row in hurt}
            self.assertLessEqual(by_id["p4"]["minutes"], 27 * 0.25 + 0.5)
            self.assertTrue(by_id["p4"].get("left_injured"))
            self.assertEqual(sum(round(row["minutes"] * 100) for row in hurt), 24000)
            gains = {row["player"]["id"]: by_id[row["player"]["id"]]["minutes"] - row["minutes"] for row in base}
            # The backup center gains more than the starting point guard.
            self.assertGreater(gains["p9"], gains["p0"])

    def test_no_injury_means_no_change(self):
        for game in range(20):
            a, fa, oa = self.run_game(None, game)
            b, fb, ob = gm.manage_game_minutes(self.pool(None), [], 3, random.Random(f"g{game}"), random.Random(f"f{game}"))
            self.assertEqual([r["minutes"] for r in a], [r["minutes"] for r in b])


class RestTests(unittest.TestCase):
    PLAYER = {"id": "p", "age": 31.0}

    def chance(self, player=None, st=None, **context):
        ctx = {"games_left": 50, "rank": 15, "teams": 30, "win_pct": 0.5, "rested_tonight": 0, "regulars_out": 0, **context}
        return health.rest_chance(player or self.PLAYER, st or state(), ctx)

    def test_back_to_backs_and_age(self):
        b2b, _, reason = self.chance(back_to_back=True)
        other, _, _ = self.chance(back_to_back=False)
        self.assertGreater(b2b, other)
        self.assertIn("back-to-back", reason)
        young, _, _ = self.chance({"id": "y", "age": 22.0}, back_to_back=True)
        self.assertGreater(b2b, young)

    def test_policy_limits(self):
        self.assertEqual(self.chance(back_to_back=True, rested_tonight=1)[0], 0.0)     # one rest per game
        self.assertEqual(self.chance(back_to_back=True, regulars_out=3)[0], 0.0)       # short-handed
        self.assertEqual(self.chance(st=state(games_missed=10, games_rested=4), back_to_back=True)[0], 0.0)  # 65-game rule

    def test_late_season(self):
        late, _, _ = self.chance(games_left=10)
        early, _, _ = self.chance(games_left=40)
        self.assertGreater(late, early)
        final, kind, _ = self.chance(games_left=2, win_pct=0.62, rank=3, rested_tonight=2)
        self.assertEqual((final, kind), (health.REST_FINAL_PLAYOFF, "rest"))
        shut, kind, reason = self.chance(games_left=20, rank=28, win_pct=0.25)
        self.assertEqual(kind, "shutdown")
        self.assertIn("out of the race", reason)
        self.assertEqual(self.chance(games_left=40, rank=28)[1], "rest")

    def test_decision_uses_the_draw(self):
        ctx = {"games_left": 50, "rank": 15, "teams": 30, "back_to_back": True}
        chance, _, _ = health.rest_chance(self.PLAYER, state(), ctx)
        self.assertIsNotNone(health.coach_rest_decision(self.PLAYER, state(), ctx, chance / 2))
        self.assertIsNone(health.coach_rest_decision(self.PLAYER, state(), ctx, min(0.999, chance * 1.5)))
        self.assertEqual(health.rest_draw(7, "g1", "p"), health.rest_draw(7, "g1", "p"))

    def test_rested_player_is_out_of_the_rotation_for_that_night_only(self):
        from nba_gm_data.save import player_unavailable_for_rotation
        s = state(rest_game_id="g1", rest_date="2026-11-10", rest_reason="maintenance day")
        self.assertTrue(player_unavailable_for_rotation(s))
        canonical = {"player_health_states": [s], "injury_events": []}
        pool = [{"player": {"id": "p"}, "minutes": 30.0}]
        self.assertEqual(health.sandbox_health_adjusted_pool(canonical, "2026-11-10", pool), [])
        health.advance_state_for_date(s, date(2026, 11, 11), 0, CONFIG, STAFF)
        self.assertNotIn("rest_game_id", s)
        self.assertFalse(player_unavailable_for_rotation(s))

    def test_standings_context(self):
        records = {"a": {"wins": 30, "losses": 10}, "b": {"wins": 10, "losses": 30}, "c": {"wins": 20, "losses": 20}}
        ctx = health.league_rest_context({"save_team_records": records})
        self.assertEqual((ctx["a"]["rank"], ctx["b"]["rank"]), (1, 3))
        self.assertEqual(ctx["a"]["games_left"], 42)


class UserSuggestionTests(unittest.TestCase):
    def test_user_team_gets_a_suggestion_not_a_rest(self):
        from nba_gm_data import save as sv
        teams = [{"id": "team_bos", "abbrev": "BOS"}, {"id": "team_nyk", "abbrev": "NYK"}]
        players = [{"id": f"b{i}", "team_id": "team_bos", "age": 33.0, "minutes_projection": 30.0} for i in range(6)]
        games = [{"externalGameId": "g1", "gameDate": "2026-11-10", "homeTeamId": "2", "awayTeamId": "18", "phase": "regular"},
                 {"externalGameId": "g2", "gameDate": "2026-11-11", "homeTeamId": "18", "awayTeamId": "2", "phase": "regular"}]
        found = False
        for seed in range(1, 80):
            save = {"meta": {"user_team_id": "team_bos", "season": "2026-27"}, "state": {"phase": "regular_season"},
                    "season_schedules": {"2026-27": {"games": games}},
                    "team_records": {"team_bos": {"wins": 5, "losses": 5}, "team_nyk": {"wins": 5, "losses": 5}},
                    "health_states": [state(player_id=p["id"]) for p in players]}
            sv.attach_rest_suggestions(".", {"teams": teams, "players": players}, save, "2026-11-10", seed)
            notes = [s["rest_suggestion"] for s in save["health_states"] if s.get("rest_suggestion")]
            self.assertLessEqual(len(notes), 1)                       # one rest per game, as for AI teams
            self.assertTrue(all(not s.get("rest_game_id") for s in save["health_states"]))
            if notes:
                found = True
                self.assertEqual(notes[0]["game_id"], "g2")
                self.assertIn("back-to-back", notes[0]["reason"])
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()
