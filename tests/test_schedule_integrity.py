"""New seasons are balanced; persisted seasons and raw evidence stay intact."""
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

from nba_gm_data import save as engine


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"401809839", "401810384", "401810499", "401810507", "401810506"}
MAKEUPS = {"401850920", "401857824", "401858694", "401858693"}


class ScheduleIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.raw = engine.load_schedule(ROOT)
        self.corrected = engine.regular_schedule_template(ROOT)

    def test_source_corrections_remove_only_superseded_games_and_cup_final(self):
        before = (ROOT / engine.SCHEDULE_FILE).read_bytes()
        raw_ids = {game["externalGameId"] for game in self.raw}
        corrected_ids = {game["externalGameId"] for game in self.corrected}
        self.assertEqual(raw_ids - corrected_ids, EXCLUDED)
        self.assertTrue(MAKEUPS <= corrected_ids)
        self.assertTrue({str(value) for value in range(401809833,401809839)} <= corrected_ids)
        self.assertEqual(self.raw, engine.load_schedule(ROOT))
        self.assertEqual(before, (ROOT / engine.SCHEDULE_FILE).read_bytes())

    def test_eleven_seasons_have_82_games_per_team_and_deterministic_dates(self):
        for year in range(2026,2037):
            season = f"{year}-{str(year+1)[-2:]}"
            first = engine.generate_future_schedule(ROOT,season,year)
            self.assertEqual(first,engine.generate_future_schedule(ROOT,season,year))
            self.assertEqual(first["game_count"],1230)
            counts = Counter(str(team) for game in first["games"] for team in [game["homeTeamId"],game["awayTeamId"]])
            self.assertEqual(counts,{str(team):82 for team in range(1,31)})
            engine.validate_regular_season_schedule(first["games"])
            self.assertTrue(all(f"{year}-10-21" <= game["gameDate"] <= f"{year+1}-04-12" for game in first["games"]))
            self.assertEqual(len({game["externalGameId"] for game in first["games"]}),1230)

    def test_existing_saved_schedule_and_played_results_are_not_repaired_on_read(self):
        legacy = {"meta":{"season":"2026-27"},
                  "season_schedules":{"2026-27":{"games":deepcopy(self.raw),"game_count":1235}},
                  "schedule_state":{"simulated_game_ids":["401810384"]},
                  "game_results":[{"game_id":"401810384","home_score":100,"away_score":90}]}
        before = deepcopy(legacy)
        with patch.object(engine,"generate_future_schedule",side_effect=AssertionError("Must not regenerate saved seasons")):
            self.assertEqual(engine.schedule_for_save(ROOT,legacy),self.raw)
            self.assertCountEqual(engine.scheduled_games_between(ROOT,legacy,"2026-01-07","2026-01-08"),
                                  [game for game in self.raw if game["gameDate"]=="2026-01-08"])
        self.assertEqual(legacy,before)

    def test_missing_makeup_is_rejected_instead_of_silently_deleting_a_game(self):
        raw = [game for game in self.raw if game["externalGameId"]!="401850920"]
        with patch.object(engine,"load_schedule",return_value=raw):
            with self.assertRaisesRegex(ValueError,"missing valid makeup"):
                engine.regular_schedule_template(ROOT)

    def test_legacy_rollover_keeps_the_old_schedule_and_archives_played_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"legacy.json"
            result = {"game_id":"401810384","home_team_id":"team_chi","away_team_id":"team_mia",
                      "home_score":100,"away_score":90,"team_lines":[],"player_lines":[]}
            legacy = {"version":engine.SAVE_VERSION,"meta":{"id":"legacy","season":"2025-26"},
                      "state":{"current_date":"2026-09-30"},
                      "season_schedules":{"2025-26":{"games":deepcopy(self.raw),"game_count":1235}},
                      "game_results":[result],"team_game_logs":[],"player_game_logs":[]}
            engine.write_save(path,legacy)
            replacements = {"ensure_draft_processed":{},"generate_league_awards":{},
                            "build_year_in_review":{},"apply_offseason_roster_transitions":{},
                            "initial_team_records":{},"clean_free_agency_state":None,
                            "refresh_health_for_new_season":None,"age_staff_contracts":None}
            with ExitStack() as stack:
                for name, value in replacements.items():
                    stack.enter_context(patch.object(engine,name,return_value=value))
                engine.complete_offseason_and_rollover(ROOT,{},path,prepared_save=engine.load_save(path))
            saved = engine.load_save(path,include_history=True)
            self.assertEqual(saved["season_schedules"]["2025-26"]["games"],self.raw)
            self.assertEqual(saved["season_schedules"]["2026-27"]["game_count"],1230)
            self.assertEqual(saved["game_results"],[result])

    def test_correction_guards_against_changed_template_identity(self):
        raw = deepcopy(self.raw)
        next(game for game in raw if game["externalGameId"]=="401810384")["awayTeamId"] = "2"
        with patch.object(engine,"load_schedule",return_value=raw):
            with self.assertRaisesRegex(ValueError,"no longer matches"):
                engine.regular_schedule_template(ROOT)

    def test_invalid_new_schedules_fail_validation(self):
        cases = []
        cases.append((self.corrected[:-1],"82 per team"))
        duplicate = deepcopy(self.corrected)
        duplicate[1]["externalGameId"] = duplicate[0]["externalGameId"]
        cases.append((duplicate,"duplicate game ID"))
        self_game = deepcopy(self.corrected)
        self_game[0]["awayTeamId"] = self_game[0]["homeTeamId"]
        cases.append((self_game,"invalid opponents"))
        unknown = deepcopy(self.corrected)
        unknown[0]["awayTeamId"] = "99"
        cases.append((unknown,"invalid opponents"))
        double = deepcopy(self.corrected)
        first = double[0]
        other = next(game for game in double if game["gameDate"]!=first["gameDate"] and first["homeTeamId"] in [game["homeTeamId"],game["awayTeamId"]])
        other["gameDate"] = first["gameDate"]
        cases.append((double,"double-books"))
        phase = deepcopy(self.corrected)
        phase[0]["phase"] = "cup_final"
        cases.append((phase,"Non-regular"))
        for games, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError,message):
                engine.validate_regular_season_schedule(games)

    def test_missing_resource_root_uses_existing_source_fallback(self):
        self.assertEqual(engine.generate_future_schedule(ROOT/"not-a-resource-directory","2026-27",2026),
                         engine.generate_future_schedule(ROOT,"2026-27",2026))


if __name__ == "__main__":
    unittest.main()
