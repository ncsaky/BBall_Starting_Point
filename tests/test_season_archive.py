"""Finished seasons move to per-season archive files; the live save keeps what the game reads (SEASON-ARCHIVE)."""

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from nba_gm_data import save as save_module
from nba_gm_data import season_archive as sa
from nba_gm_data.career_stats import player_career_seasons
from nba_gm_data.contract_protection import _uncached_season_window
from nba_gm_data.injury_model import player_history
from nba_gm_data.offseason_calendar import opening_night
from nba_gm_data.save_recovery import create_export, recover_previous_save, restore_export
from nba_gm_data.season_slides import available_slideshows, stored_outlook, stored_recap

SEASONS = ("2026-27", "2027-28", "2028-29")


def schedule(label):
    start = int(label[:4])
    games = [{"externalGameId": f"sim_game_{label}-{n:04d}", "gameDate": f"{start}-1{n % 2}-2{n % 9}",
              "phase": "regular", "homeTeamId": "1", "awayTeamId": "2"} for n in range(12)]
    games.append({"externalGameId": f"sim_game_{label}-late", "gameDate": f"{start + 1}-04-12", "phase": "regular"})
    games.append({"externalGameId": f"sim_game_{label}-early", "date": f"{start}-10-19", "phase": "regular"})
    return {"season": label, "game_count": len(games), "template": "t", "games": games}


def fixture():
    save = {
        "version": save_module.SAVE_VERSION,
        "meta": {"id": "archive-fixture", "season": "2029-30", "user_team_id": "team_a", "season_start_year": 2029},
        "state": {"current_date": "2029-10-01", "phase": "preseason"},
        "season_history": [], "season_schedules": {}, "game_result_summaries": [], "injury_events": [],
        "season_slideshows": {"recaps": {}, "outlooks": {}, "seen": {}}, "award_preseason_baselines": {},
        "playoff_player_stats": {"p1": {"player_id": "p1", "games": 0, "game_ids": [], "points": 0.0}},
        "health_states": [{"player_id": "p2", "current_injury_id": "inj-open"}],
    }
    for label in (*SEASONS, "2029-30"):
        start = int(label[:4])
        save["season_schedules"][label] = schedule(label)
        save["season_slideshows"]["outlooks"][label] = {"season": label, "slides": [label] * 3}
        save["award_preseason_baselines"][label] = {"MVP": {"p1": 1.0}}
        save["game_result_summaries"].append({"game_id": f"sim_game_{label}-0001", "date": f"{start}-11-02",
                                              "home_score": 100, "away_score": 90})
        save["game_result_summaries"].append({"game_id": f"playoff_game_{start + 1}-east-7v8-a-b", "date": None,
                                              "home_score": 101, "away_score": 99})
        if label == "2029-30":
            continue
        save["season_history"].append({
            "season": label, "completed_on": f"{start + 1}-09-30", "team_records": {"team_a": {"wins": 50, "losses": 32}},
            "player_season_stats": {"p1": {"player_id": "p1", "games": 70, "minutes": 2100.0, "points": 1400.0,
                                           "team_id": "team_a", "team_abbrev": "AAA", "game_ids": ["g"] * 3}},
            "playoff_state": {"champion_team_id": "team_a", "games": [{"id": label}]},
            "draft_order": {"draft_order": [{"overall_pick": 1}]}, "draft_result": {"picks": 60},
            "awards": [{"award": "MVP", "player_id": "p1", "season": label}],
            "recap": {"season": label, "slides": ["recap"]}, "transaction_count": 9, "development_months": [],
        })
        save["playoff_player_stats"]["p1"]["game_ids"].append(f"playoff_game_{start + 1}-east-first-round-g1")
        for n, (month, back) in enumerate((("11", "12-01"), ("02", "03-15"))):
            year = start if month == "11" else start + 1
            save["injury_events"].append({
                "id": f"inj-{label}-{n}", "player_id": "p1", "team_id": "team_a", "start_date": f"{year}-{month}-03",
                "return_date": f"{year}-{back}", "status": "healed", "severity": "short", "body_part": "ankle",
                "body_area": "ankle_foot", "source_ids": ["src_injury_model_v2"], "expected_games_missed": 8,
                "plays_injury_game": True, "diagnosis": "Left Ankle Sprain", "notes": "long text " * 10,
                "lasting_rapm_change": -0.1, "was_starter": True,
            })
    save["injury_events"].append({"id": "inj-open", "player_id": "p2", "team_id": "team_a", "start_date": "2027-02-01",
                                  "return_date": "2030-02-01", "status": "out", "body_part": "achilles",
                                  "diagnosis": "Achilles Tear", "source_ids": []})
    save["injury_events"].append({"id": "inj-never-closed", "player_id": "p3", "start_date": "2026-12-01",
                                  "body_part": "knee", "source_ids": []})
    return save


class SeasonArchiveSplitTests(unittest.TestCase):
    def test_game_id_and_date_seasons(self):
        self.assertEqual(sa.season_of_game_id("playoff_game_2028-east-9v10-team-ind-team-atl"), "2027-28")
        self.assertEqual(sa.season_of_game_id("sim_game_2027-28-401809243"), "2027-28")
        self.assertIsNone(sa.season_of_game_id("401809243"))
        self.assertEqual(sa.season_of_date("2028-06-30"), "2027-28")
        self.assertEqual(sa.season_of_date("2028-07-01"), "2028-29")

    def test_split_keeps_last_season_whole_and_engine_answers_unchanged(self):
        save = fixture()
        before = deepcopy(save)
        payloads = sa.split_finished_seasons(save)
        self.assertEqual(sorted(payloads), ["2026-27", "2027-28"])   # 2028-29 (last season) stays whole
        history = {row["season"]: row for row in save["season_history"]}
        self.assertEqual(history["2028-29"], before["season_history"][2])
        for label in ("2026-27", "2027-28"):
            self.assertEqual(set(history[label]) & set(sa.HISTORY_DETAIL_KEYS), set())
            self.assertEqual(history[label]["team_records"], {"team_a": {"wins": 50, "losses": 32}})
            self.assertEqual(history[label]["awards"][0]["award"], "MVP")
            self.assertNotIn(label, save["season_slideshows"]["outlooks"])
            self.assertNotIn(label, save["award_preseason_baselines"])
        self.assertEqual(len(save["season_history"]), 3)
        # Season windows and opening nights read the same dates from the schedule stubs.
        for label in (*SEASONS, "2029-30"):
            self.assertEqual(_uncached_season_window(save, label), _uncached_season_window(before, label))
            self.assertEqual(opening_night(int(label[:4]), save), opening_night(int(label[:4]), before))
        self.assertEqual(save["season_schedules"]["2026-27"][sa.SCHEDULE_MARKER], 14)
        self.assertEqual(save["season_schedules"]["2026-27"]["game_count"], 14)
        self.assertEqual(save["season_schedules"]["2028-29"], before["season_schedules"]["2028-29"])
        # Score lines of the current and last season stay; playoff game ids of archived seasons move.
        self.assertEqual({sa.season_of_date(r["date"]) or sa.season_of_game_id(r["game_id"])
                          for r in save["game_result_summaries"]}, {"2028-29", "2029-30"})
        self.assertEqual(save["playoff_player_stats"]["p1"]["game_ids"], ["playoff_game_2029-east-first-round-g1"])
        # Injury history: the engine's weights for every player are unchanged; open and unclosed injuries stay whole.
        for player_id in ("p1", "p2", "p3"):
            self.assertEqual(player_history({}, player_id, save["injury_events"]),
                             player_history({}, player_id, before["injury_events"]))
        events = {row["id"]: row for row in save["injury_events"]}
        self.assertEqual(events["inj-open"], before["injury_events"][-2])
        self.assertEqual(events["inj-never-closed"], before["injury_events"][-1])
        self.assertEqual(events["inj-2026-27-0"][sa.INJURY_MARKER], "2026-27")
        self.assertNotIn("diagnosis", events["inj-2026-27-0"])
        self.assertIn("diagnosis", events["inj-2028-29-0"])
        self.assertEqual([row["id"] for row in save["injury_events"]], [row["id"] for row in before["injury_events"]])
        # Nothing is left to move the second time.
        self.assertEqual(sa.split_finished_seasons(save), {})

    def test_first_two_seasons_move_nothing(self):
        save = fixture()
        save["meta"]["season"] = "2027-28"
        save["season_history"] = save["season_history"][:1]
        self.assertEqual(sa.split_finished_seasons(save), {})


class SeasonArchiveFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "league.json"
        self.original = fixture()
        save_module.write_save(self.path, deepcopy(self.original))
        self.saved = save_module.load_save(self.path)

    def assert_history_views_match(self, path, saved):
        original = self.original
        self.assertEqual(sa.full_season_history(path, saved), original["season_history"])
        self.assertEqual(sa.full_injury_events(path, saved), original["injury_events"])
        for label in SEASONS:
            self.assertEqual(stored_recap(saved, label, path), stored_recap(original, label))
            self.assertEqual(stored_outlook(saved, label, path), stored_outlook(original, label))
        self.assertEqual(available_slideshows(saved), available_slideshows(original))
        player, current = {"id": "p1", "name": "Archive Fixture Player"}, {"season": "2029-30", "games": 0}
        self.assertEqual(player_career_seasons(player, saved, dict(current), path),
                         player_career_seasons(player, original, dict(current)))

    def test_write_moves_old_seasons_to_files_and_history_views_match(self):
        files = sorted(p.name for p in self.path.parent.glob("league.season-*.json.gz"))
        self.assertEqual(len(files), 2)
        self.assertEqual(sorted(sa.archive_entries(self.saved)), ["2026-27", "2027-28"])
        self.assertTrue(all(sa.load_season_archive(self.path, self.saved, label) for label in ("2026-27", "2027-28")))
        self.assertLess(self.path.stat().st_size, len(json.dumps(self.original)))
        self.assert_history_views_match(self.path, self.saved)

    def test_second_write_changes_nothing(self):
        before = sorted(p.name for p in self.path.parent.glob("*.json.gz"))
        manifest = deepcopy(self.saved[sa.ARCHIVE_KEY])
        save_module.write_save(self.path, self.saved)
        again = save_module.load_save(self.path)
        self.assertEqual(sorted(p.name for p in self.path.parent.glob("*.json.gz")), before)
        self.assertEqual(again[sa.ARCHIVE_KEY], manifest)

    def test_later_rows_of_an_archived_season_are_added_to_a_new_file(self):
        self.saved["game_result_summaries"].append({"game_id": "sim_game_2026-27-late-add", "date": "2027-03-03"})
        old_name = self.saved[sa.ARCHIVE_KEY]["seasons"]["2026-27"]["file"]
        save_module.write_save(self.path, self.saved)
        again = save_module.load_save(self.path)
        entry = again[sa.ARCHIVE_KEY]["seasons"]["2026-27"]
        self.assertNotEqual(entry["file"], old_name)
        self.assertTrue((self.path.parent / old_name).exists())   # an earlier manifest's file is never changed
        rows = sa.archived_tables(self.path, again, "2026-27")["game_result_summaries"]
        self.assertIn("sim_game_2026-27-late-add", {row["game_id"] for row in rows})
        self.assertEqual(sa.full_season_history(self.path, again), self.original["season_history"])

    def test_rows_rebuilt_from_the_history_database_are_not_archived_twice(self):
        # A view that loads the whole history database and writes rebuilds old score lines in the live save.
        entry = deepcopy(self.saved[sa.ARCHIVE_KEY]["seasons"]["2026-27"])
        archived = sa.archived_tables(self.path, self.saved, "2026-27")["game_result_summaries"]
        self.saved["game_result_summaries"] = deepcopy(archived) + self.saved["game_result_summaries"]
        save_module.write_save(self.path, self.saved)
        again = save_module.load_save(self.path)
        self.assertEqual(again[sa.ARCHIVE_KEY]["seasons"]["2026-27"], entry)   # same file, no rewrite
        self.assertNotIn("sim_game_2026-27-0001", {row["game_id"] for row in again["game_result_summaries"]})
        # A rebuilt row that differs replaces the archived one (as it replaced the live row before).
        changed = {**archived[0], "home_score": 77}
        again["game_result_summaries"].append(changed)
        save_module.write_save(self.path, again)
        latest = save_module.load_save(self.path)
        rows = sa.archived_tables(self.path, latest, "2026-27")["game_result_summaries"]
        self.assertEqual([row for row in rows if row["game_id"] == changed["game_id"]], [changed])
        self.assertEqual(len(rows), len(archived))

    def test_export_restore_and_previous_save_recovery_keep_archives(self):
        target = Path(self.tmp.name) / "copy" / "restored.json"
        target.parent.mkdir()
        restore_export(target, create_export(self.path))
        restored = save_module.load_save(target)
        names = {entry["file"] for entry in sa.archive_entries(restored).values()}
        self.assertTrue(all(name.startswith("restored.season-") for name in names))
        self.assertTrue(all((target.parent / name).is_file() for name in names))
        self.assert_history_views_match(target, restored)
        # The local previous-save backup leaves the write-once archive files beside the save.
        save_module.write_save(self.path, self.saved)
        recover_previous_save(self.path)
        self.assert_history_views_match(self.path, save_module.load_save(self.path))

    def test_missing_archive_only_empties_history_detail(self):
        for path in self.path.parent.glob("league.season-*.json.gz"):
            path.unlink()
        sa._CACHE.clear()
        saved = save_module.load_save(self.path)   # play never needs an archive
        self.assertIsNone(sa.load_season_archive(self.path, saved, "2026-27"))
        self.assertIsNone(stored_outlook(saved, "2026-27", self.path))
        self.assertEqual(len(sa.full_season_history(self.path, saved)), 3)
        save_module.write_save(self.path, saved)

    def test_damaged_archive_is_not_trusted(self):
        entry = self.saved[sa.ARCHIVE_KEY]["seasons"]["2027-28"]
        (self.path.parent / entry["file"]).write_bytes(b"not an archive")
        sa._CACHE.clear()
        self.assertIsNone(sa.load_season_archive(self.path, self.saved, "2027-28"))


if __name__ == "__main__":
    unittest.main()
