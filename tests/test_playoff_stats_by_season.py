"""Each postseason's player stats are their own season's: two seasons through the real postseason, Finals MVP,
rollover, player-page history and the season archive. Only the game itself and unrelated services are stubbed."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data import save as sv, season_archive as sa
from nba_gm_data.career_stats import player_career_seasons

SEASON_ONE, SEASON_TWO = "2026-27", "2027-28"
# Points per game in (the Finals, earlier rounds) for each team's two players. Player A is far ahead over both seasons
# together; player B is the better one in season two's Finals.
POINTS = {SEASON_ONE: {"a": (40, 20), "b": (10, 20)}, SEASON_TWO: {"a": (12, 30), "b": (28, 8)}}


class PlayoffStatsBySeasonTests(unittest.TestCase):
    def setUp(self):
        teams = [{"id": f"{conference}{i}", "abbrev": f"{conference[0]}{i}", "conference": conference}
                 for conference in ("East", "West") for i in range(1, 11)]
        self.canonical = {"teams": teams, "players": []}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(sv, "advance_lifecycle_to", side_effect=self.lifecycle))
        self.stack.enter_context(patch.object(sv, "simulate_playoff_game", side_effect=self.game))
        # The offseason's roster, staff, schedule and presentation work: unrelated to the stats under test.
        stubs = {"ensure_draft_processed": {}, "generate_league_awards": [], "ensure_year_end_recap_safely": None,
                 "offseason_coaching_recommendations": [], "apply_ai_staff_recommendations": None,
                 "build_year_in_review": None, "apply_offseason_roster_transitions": {},
                 "mark_national_tv_safely": None, "clean_free_agency_state": None,
                 "refresh_health_for_new_season": None, "prune_settled_waiver_entries": None,
                 "apply_season_start_injuries": None, "canonical_with_save": self.canonical,
                 "age_staff_contracts": None, "simulate_ai_staff_changes": {}, "refresh_roster_cutdowns": None,
                 "refresh_user_roster_minimum": None, "ensure_preseason_outlook_safely": None}
        for name, result in stubs.items():
            self.stack.enter_context(patch.object(sv, name, return_value=result))
        self.stack.enter_context(patch.object(sv, "generate_future_schedule", return_value={"games": []}))
        self.stack.enter_context(patch.object(sv, "initial_team_records", side_effect=lambda canonical: self.records()))
        self.stack.enter_context(patch("nba_gm_data.offseason_decisions.restricted_summer_pass"))
        self.save = {"version": sv.SAVE_VERSION, "meta": {"id": "playoffs", "season": SEASON_ONE, "seed": 17},
                     "state": {"current_date": "2027-04-13", "phase": "play_in"},
                     "schedule_state": {"simulated_game_ids": []}, "team_records": self.records(),
                     "playoff_player_stats": {}, "season_history": []}

    def records(self):
        return {team["id"]: {"team_id": team["id"], "wins": 60 - i, "losses": 22 + i}
                for i, team in enumerate(self.canonical["teams"])}

    def lifecycle(self, canonical, save, target, seed, root=None, **kwargs):
        save.setdefault("lifecycle_state", {})["through_date"] = target
        sv.set_save_date_phase(save, target)
        return {"active": canonical, "development_events": []}

    def game(self, canonical, save, root, away, home, day, seed, key):
        self.lifecycle(canonical, save, day, seed, root)
        fixture = sv.playoff_game_fixture(canonical, away, home, day, key)
        finals = save["playoff_state"]["round"] == "finals"
        season = save["meta"]["season"]
        lines = [{"player_id": f"{letter}-{team}", "player_name": f"{letter.upper()} {team}", "team_id": team,
                  "team_abbrev": team, "minutes": 32, "points": POINTS[season][letter][0 if finals else 1], "rebounds": 5}
                 for team in (away, home) for letter in ("a", "b")]
        result = {"game_id": fixture["externalGameId"], "away_team_id": away, "home_team_id": home,
                  "away_score": 100, "home_score": 110, "player_lines": lines}
        sv.record_playoff_game_result(save, fixture, result)
        return result

    def play_postseason(self, save):
        end = int(save["meta"]["season"][:4]) + 1
        save["state"] = {"current_date": f"{end}-04-13", "phase": "play_in"}
        sv.advance_save(".", self.canonical, "unused.json", to_date=f"{end}-06-16", prepared_save=save, persist=False)
        self.assertEqual(save["playoff_state"]["status"], "completed")

    def rollover(self, path, save):
        save["state"] = {"current_date": f"{int(save['meta']['season'][:4]) + 1}-09-30", "phase": "offseason"}
        sv.complete_offseason_and_rollover(".", self.canonical, path, prepared_save=save)
        return sv.load_save(path)

    def check_season_totals(self, save, season, totals):
        """Every total is made of that season's games only."""
        state = save["playoff_state"]
        champion = state["champion_team_id"]
        finals = next(series for series in state["series"] if series["round"] == "finals")
        finals_games = len(finals["game_ids"])
        for letter in ("a", "b"):
            row = totals[f"{letter}-{champion}"]
            other_games = row["games"] - finals_games
            in_finals, earlier = POINTS[season][letter]
            self.assertEqual(row["points"], finals_games * in_finals + other_games * earlier)
            self.assertEqual(row["nba_finals"]["games"], finals_games)
            self.assertEqual(row["nba_finals"]["points"], finals_games * in_finals)
            self.assertEqual(row["minutes"], row["games"] * 32)
        return champion, finals_games

    def test_two_seasons(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "career.json"
            self.play_postseason(self.save)
            champion, first_finals = self.check_season_totals(self.save, SEASON_ONE, self.save["playoff_player_stats"])
            player = f"a-{champion}"
            first = deepcopy(self.save["playoff_player_stats"][player])
            self.assertEqual(self.save["finals_mvp"]["player_id"], player)

            save = self.rollover(path, self.save)
            self.assertEqual(save["meta"]["season"], SEASON_TWO)
            self.assertEqual(save["playoff_player_stats"], {})
            self.assertIsNone(save["finals_mvp"])
            kept = save["season_history"][-1]
            self.assertEqual(kept["finals_mvp"]["player_id"], player)
            self.assertEqual(kept["playoff_player_stats"][player],
                             {key: value for key, value in first.items() if key != "game_ids"})

            self.play_postseason(save)
            second_champion, _ = self.check_season_totals(save, SEASON_TWO, save["playoff_player_stats"])
            self.assertEqual(second_champion, champion)   # the same players, so adding up would show
            second = save["playoff_player_stats"][player]
            self.assertEqual(second["games"], len(second["game_ids"]))
            self.assertTrue(all(game_id.startswith("playoff_game_2028") for game_id in second["game_ids"]))
            # Over both Finals together A leads B; in this season's Finals B does.
            self.assertEqual(save["finals_mvp"]["player_id"], f"b-{champion}")
            self.assertEqual(save["finals_mvp"]["season"], SEASON_TWO)
            self.assertEqual(save["finals_mvp"]["finals_line"]["pts"], 28.0)

            leaders = sv.playoff_leaders
            with patch.object(sv, "load_save", return_value=save), \
                 patch.object(sv, "ensure_league_save_defaults", side_effect=lambda s, c: s):
                shown = leaders(self.canonical, path, limit=100)
            self.assertEqual(shown["season"], SEASON_TWO)
            row = next(r for r in shown["leaders"] if r["player_id"] == player)
            self.assertEqual((row["games"], row["points"]), (second["games"], second["points"]))

            def career(state):
                current = {"season": state["meta"]["season"], "games": 0}
                return {r["season"]: r for r in player_career_seasons({"id": player}, state, current, path)}

            def line(entry):
                return entry["games"], entry["ppg"], entry["team_games"]

            expected_first = (first["games"], round(first["points"] / first["games"], 1), first["games"])
            expected_second = (second["games"], round(second["points"] / second["games"], 1), second["games"])
            rows = career(save)
            self.assertEqual(line(rows[SEASON_ONE]["playoffs"]), expected_first)
            self.assertEqual(line(rows[SEASON_TWO]["playoffs"]), expected_second)

            # One more rollover: season one moves to its archive file and the player page still shows both.
            save = self.rollover(path, save)
            oldest = save["season_history"][0]
            self.assertNotIn("playoff_player_stats", oldest)
            self.assertIn(SEASON_ONE, sa.archive_entries(save))
            self.assertEqual(oldest["finals_mvp"]["player_id"], player)
            rows = career(save)
            self.assertEqual(line(rows[SEASON_ONE]["playoffs"]), expected_first)
            self.assertEqual(line(rows[SEASON_TWO]["playoffs"]), expected_second)
            self.assertNotIn("playoffs", rows["2028-29"])

    def test_a_player_outside_the_postseason_has_no_playoff_line(self):
        self.play_postseason(self.save)
        rows = player_career_seasons({"id": "nobody"}, self.save, {"season": SEASON_ONE, "games": 0})
        self.assertNotIn("playoffs", rows[0])


if __name__ == "__main__":
    unittest.main()
