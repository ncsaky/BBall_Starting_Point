"""Postseason games share the calendar controls, without skipping play-in."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data import app_actions as aa, history_store as hs, save as sv


class PostseasonCalendarTests(unittest.TestCase):
    def setUp(self):
        self.canonical = {"teams": [
            {"id": f"{conf}{i}", "abbrev": f"{conf[0]}{i}", "conference": conf}
            for conf in ("East", "West") for i in range(1, 11)
        ], "players": []}
        self.save = {"meta": {"season": "2026-27", "seed": 17},
                     "state": {"current_date": "2027-04-13", "phase": "play_in"},
                     "schedule_state": {"simulated_game_ids": []},
                     "team_records": {t["id"]: {"team_id": t["id"], "wins": 60-i, "losses": 22+i}
                                      for i, t in enumerate(self.canonical["teams"])}}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(sv, "advance_lifecycle_to", side_effect=self.lifecycle))
        self.stack.enter_context(patch.object(sv, "simulate_playoff_game", side_effect=self.game))

    def lifecycle(self, canonical, save, target, seed, root=None, **kwargs):
        cursor = save.setdefault("lifecycle_state", {}).get("through_date", save["state"]["current_date"])
        self.assertGreaterEqual(target, cursor)
        save["lifecycle_state"]["through_date"] = target
        sv.set_save_date_phase(save, target)
        return {"active": canonical, "development_events": []}

    def game(self, canonical, save, root, away, home, day, seed, key):
        self.lifecycle(canonical, save, day, seed, root)
        fixture = sv.playoff_game_fixture(canonical, away, home, day, key)
        result = {"game_id": fixture["externalGameId"], "away_team_id": away, "home_team_id": home,
                  "away_score": 100 + seed % 3, "home_score": 110,
                  "player_lines": [{"player_id": f"p-{team}", "team_id": team, "minutes": 32,
                                    "points": 20, "rebounds": 6, "assists": 4, "turnovers": 2}
                                   for team in (away, home)]}
        sv.record_playoff_game_result(save, fixture, result)
        return result

    def advance(self, save, target=None, **kwargs):
        return sv.advance_save(".", self.canonical, "unused.json", to_date=target,
                               prepared_save=save, persist=False, **kwargs)

    def test_bracket_is_ready_at_zero_and_next_event_is_one_play_in_stage(self):
        sv.initialize_postseason(self.canonical, self.save, "", 17)
        self.assertEqual(self.save["playoff_state"]["games"], [])
        self.assertEqual(self.save["playoff_state"]["play_in"]["West"]["teams"]["7"], "West7")
        self.advance(self.save, next_event=True)
        self.assertEqual(self.save["state"]["current_date"], "2027-04-13")
        self.assertEqual(len(self.save["playoff_state"]["games"]), 2)
        self.advance(self.save, next_event=True)
        self.assertEqual(self.save["state"]["current_date"], "2027-04-14")
        self.assertEqual(len(self.save["playoff_state"]["games"]), 4)
        self.advance(self.save, next_event=True)
        self.assertEqual(self.save["state"]["current_date"], "2027-04-16")
        state = self.save["playoff_state"]
        self.assertEqual(len(state["series"]), 8)
        self.assertTrue(all(max(s["wins"].values()) == 0 for s in state["series"]))
        self.assertEqual(state["play_in"]["West"]["seed_7_team_id"], "West7")
        self.assertEqual(state["play_in"]["West"]["seed_8_team_id"], "West8")

    def test_daily_week_month_and_reload_preserve_results_and_no_duplicate_stats(self):
        for seed in (3, 17, 82):
            with self.subTest(seed=seed):
                daily, weekly, bulk = (deepcopy(self.save) for _ in range(3))
                for save in (daily, weekly, bulk):
                    save["meta"]["seed"] = seed
                day = "2027-04-13"
                while day < "2027-05-14":
                    day = sv.next_date_str(day, 1)
                    self.advance(daily, day)
                    daily = json.loads(json.dumps(daily))
                for target in ("2027-04-20", "2027-04-27", "2027-05-04", "2027-05-11", "2027-05-14"):
                    self.advance(weekly, target)
                self.advance(bulk, "2027-05-14")
                self.assertEqual(daily, bulk)
                self.assertEqual(weekly, bulk)
                before = deepcopy(bulk)
                self.advance(bulk, "2027-05-14")
                self.assertEqual(bulk, before)
                self.assertEqual(len(bulk["playoff_state"]["games"]), len(set(bulk["schedule_state"]["simulated_game_ids"])))
                totals = bulk["playoff_player_stats"]["p-West7"]
                self.assertEqual(totals["minutes"], totals["games"] * 32)
                self.assertEqual(totals["points"], totals["games"] * 20)
                self.assertNotIn("player_season_stats", bulk)

    def test_championship_does_not_overshoot_month_endpoint(self):
        self.advance(self.save, "2027-06-20")
        self.assertEqual(self.save["state"]["current_date"], "2027-06-20")
        self.assertEqual(self.save["playoff_state"]["status"], "completed")
        self.assertEqual(sv.next_event_date(".", self.canonical, self.save), "2027-06-22")
        def day(root, canonical, path, save, current, target, seed):
            sv.set_save_date_phase(save, target)
            return {"ai_applied_count":0, "inseason_free_agent_signings":0}
        with patch.object(sv, "advance_save_day", side_effect=day) as advanced:
            result = self.advance(self.save, "2027-07-01")
        self.assertEqual(result["through_date"], "2027-06-22")
        self.assertEqual(advanced.call_count, 1)

    def test_unplayed_matchups_are_visible_without_persisting_a_read(self):
        before = deepcopy(self.save)
        with patch.object(aa, "load_save", return_value=deepcopy(self.save)), patch.object(aa, "ensure_league_save_defaults", side_effect=lambda s, c:s):
            room = aa.playoff_room_payload(self.canonical, Path("unused.json"))
        self.assertEqual(len(room["series"]), 8)
        self.assertEqual(room["series"][0]["score"], [0, 0])
        self.assertEqual(room["series"][0]["teams"][0]["id"], "East1")
        self.assertIsNone(room["series"][0]["teams"][1])
        self.assertEqual(room["series"][0]["pending_seed"], "8")
        self.assertEqual(room["play_in"]["West"]["teams"]["10"]["id"], "West10")
        self.assertEqual(self.save, before)

    def test_legacy_bracket_shows_play_in_matchups_without_fabricating_results(self):
        sv.initialize_postseason(self.canonical, self.save, "", 17, include_play_in=False)
        before = deepcopy(self.save)
        with patch.object(aa, "load_save", return_value=deepcopy(self.save)), patch.object(aa, "ensure_league_save_defaults", side_effect=lambda s, c:s):
            room = aa.playoff_room_payload(self.canonical, Path("unused.json"))
        self.assertEqual(room["play_in"]["West"]["status"], "not_recorded")
        self.assertEqual(room["play_in"]["West"]["teams"]["7"]["id"], "West7")
        self.assertEqual(room["play_in"]["West"]["games"], [])
        self.assertEqual(self.save, before)

    def test_advancement_pairs_feeder_branches_not_alphabetical_winners(self):
        sv.initialize_postseason(self.canonical, self.save, "", 17, include_play_in=False)
        state = self.save["playoff_state"]
        winners = []
        for conf in ("East", "West"):
            first = [s for s in state["series"] if s["conference"] == conf]
            for source, winner in zip(first, (f"{conf}8", f"{conf}4", f"{conf}6", f"{conf}2")):
                source.update(winner_team_id=winner, status="completed")
                winners.append(winner)
        # Explicit slots must survive storage order changes and caller ordering.
        state["series"].reverse()
        semis = sv.next_round_series(self.canonical, state, list(reversed(winners)), "conference_semifinals")
        for conf in ("East", "West"):
            rows = [s for s in semis if s["conference"] == conf]
            self.assertEqual([s["team_ids"] for s in rows], [[f"{conf}4", f"{conf}8"], [f"{conf}2", f"{conf}6"]])
            first = sorted([s for s in state["series"] if s["conference"] == conf], key=lambda s:s["bracket_slot"])
            self.assertEqual(rows[0]["source_series_ids"], [s["id"] for s in first[:2]])
            self.assertEqual(rows[1]["source_series_ids"], [s["id"] for s in first[2:]])
        for s in semis:
            s.update(winner_team_id=s["team_ids"][1], status="completed")
        state["series"].extend(reversed(semis))
        conf_finals = sv.next_round_series(self.canonical, state, [s["winner_team_id"] for s in semis], "conference_finals")
        for s in conf_finals:
            sources = [p for p in semis if p["conference"] == s["conference"]]
            self.assertEqual(s["source_series_ids"], [p["id"] for p in sources])
            s.update(winner_team_id=s["team_ids"][0], status="completed")
        state["series"].extend(conf_finals)
        finals = sv.next_round_series(self.canonical, state, [s["winner_team_id"] for s in conf_finals], "finals")
        self.assertEqual(len(finals), 1)
        self.assertEqual(finals[0]["source_series_ids"], [s["id"] for conf in ("East", "West") for s in conf_finals if s["conference"] == conf])

    def test_legacy_play_in_destinations_follow_original_bracket_not_new_standings(self):
        sv.initialize_postseason(self.canonical, self.save, "", 17, include_play_in=False)
        first = [s for s in self.save["playoff_state"]["series"] if s["conference"] == "West"]
        for slot, qualifier in ((0,"West7"),(3,"West8")):
            first[slot]["lower_seed_team_id"] = qualifier
            first[slot]["team_ids"][1] = qualifier
        before = deepcopy(self.save)
        with patch.object(aa,"load_save",return_value=deepcopy(self.save)), patch.object(aa,"ensure_league_save_defaults",side_effect=lambda s,c:s):
            room = aa.playoff_room_payload(self.canonical, Path("unused.json"))
        self.assertEqual(room["play_in"]["West"]["seed_8_team_id"],"West7")
        self.assertEqual(room["play_in"]["West"]["seed_7_team_id"],"West8")
        self.assertEqual(self.save,before)

    def test_only_wholly_unplayed_legacy_rounds_are_repaired(self):
        sv.initialize_postseason(self.canonical, self.save, "", 17, include_play_in=False)
        state = self.save["playoff_state"]
        first = deepcopy(state["series"])
        bad = []
        for conf in ("East", "West"):
            sources = [s for s in first if s["conference"] == conf]
            winners = []
            for s in sources:
                s.update(status="completed", winner_team_id=s["team_ids"][0], game_ids=[f"played-{s['id']}"])
                winners.append(s["winner_team_id"])
            winners.sort()
            bad.extend(sv.playoff_series_record(conf, "conference_semifinals", *winners[i:i+2]) for i in (0,2))
        state.update(round="conference_semifinals", series=first+deepcopy(bad))
        started = deepcopy(state)
        started["series"][-1]["game_ids"] = ["already-played"]
        before = deepcopy(started)
        self.assertFalse(sv.repair_unplayed_playoff_round(started))
        self.assertEqual(started,before)
        self.assertTrue(sv.repair_unplayed_playoff_round(state))
        self.assertEqual(state["series"][:8],first)
        for conf in ("East","West"):
            pairs = [s["team_ids"] for s in state["series"] if s["round"] == "conference_semifinals" and s["conference"] == conf]
            self.assertEqual(pairs, [[f"{conf}1", f"{conf}4"], [f"{conf}2", f"{conf}3"]])
        repeat = deepcopy(state)
        self.assertFalse(sv.repair_unplayed_playoff_round(state))
        self.assertEqual(state,repeat)

    def test_season_end_checkpoint_is_required_and_confirmation_survives_reload(self):
        self.save["state"] = {"current_date": "2027-04-12", "phase": "regular_season"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text("{}")
            stored = deepcopy(self.save)

            def write(path, save):
                nonlocal stored
                stored = deepcopy(save)

            def snapshot(*args, **kwargs):
                return {"home":{"save": deepcopy(stored["state"])}}

            with patch.object(aa, "normalized_read_save", side_effect=lambda *args:deepcopy(stored)), \
                 patch.object(sv, "write_save", side_effect=write), \
                 patch.object(sv, "refresh_roster_cutdowns"), \
                 patch.object(aa, "dashboard_snapshot_payload", side_effect=snapshot):
                first = aa.advance_action(Path("."), self.canonical, path, {"days":31})
                self.assertEqual(first["status"], "postseason")
                self.assertEqual(stored["state"]["current_date"], "2027-04-13")
                self.assertEqual(stored["playoff_state"]["games"], [])
                again = aa.advance_action(Path("."), self.canonical, path, {"next_event":True, "postseason_confirmed":"2026-04-13"})
                self.assertEqual(again["status"], "postseason")
                self.assertEqual(stored["playoff_state"]["games"], [])
                confirmed = aa.advance_action(Path("."), self.canonical, path, {"next_event":True, "postseason_confirmed":"2027-04-13"})
                self.assertEqual(confirmed["status"], "advanced")
                self.assertEqual(len(stored["playoff_state"]["games"]), 2)
                self.assertEqual(stored["postseason_entry_confirmed"], "2027-04-13")
                aa.advance_action(Path("."), self.canonical, path, {"next_event":True})
                self.assertEqual(len(stored["playoff_state"]["games"]), 4)
                stored.pop("postseason_entry_confirmed")
                legacy = aa.advance_action(Path("."), self.canonical, path, {"next_event":True})
                self.assertEqual(legacy["status"], "advanced")
                self.assertEqual(len(stored["playoff_state"]["games"]), 6)

    def test_playoff_menu_modes_resolve_games_series_and_entire_postseason(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text("{}")
            stored = deepcopy(self.save)

            def write(path, save):
                nonlocal stored
                stored = deepcopy(save)

            def load(*args):
                return deepcopy(stored)

            def snapshot(*args, **kwargs):
                return {"home":{"save":deepcopy(stored["state"])}}

            with patch.object(aa, "normalized_read_save", side_effect=load), \
                 patch.object(aa, "load_save", side_effect=load), \
                 patch.object(sv, "load_save", side_effect=load), \
                 patch.object(sv, "ensure_league_save_defaults", side_effect=lambda s, c:s), \
                 patch.object(aa, "ensure_league_save_defaults", side_effect=lambda s, c:s), \
                 patch.object(sv, "write_save", side_effect=write), \
                 patch.object(aa, "write_save", side_effect=write), \
                 patch.object(aa, "dashboard_snapshot_payload", side_effect=snapshot):
                def action(mode, **kwargs):
                    return aa.advance_action(Path("."), self.canonical, path, {"postseason_sim":mode, **kwargs})

                paused = action("game")
                self.assertEqual(paused["status"], "postseason")
                self.assertFalse(stored["playoff_state"]["games"])
                action("game", postseason_confirmed="2027-04-13")
                self.assertEqual(len(stored["playoff_state"]["games"]), 2)
                action("series")
                self.assertEqual(len(stored["playoff_state"]["games"]), 6)
                self.assertEqual(stored["playoff_state"]["round"], "first_round")
                action("game")
                self.assertTrue(all(len(s["game_ids"]) == 1 for s in stored["playoff_state"]["series"]))
                action("series")
                self.assertEqual(stored["playoff_state"]["round"], "conference_semifinals")
                self.assertTrue(all(s["status"] == "completed" for s in stored["playoff_state"]["series"] if s["round"] == "first_round"))
                action("all")
                self.assertEqual(stored["playoff_state"]["status"], "completed")
                self.assertLess(stored["state"]["current_date"], "2027-06-22")
                self.assertEqual(stored["state"]["phase"], "playoffs")
                completed = deepcopy(stored)
                held = action("game")
                self.assertEqual(held["status"],"postseason_complete")
                self.assertEqual(stored,completed)

                def day(root, canonical, path, save, current, target, seed):
                    sv.set_save_date_phase(save, target)
                    return {"ai_applied_count":0, "inseason_free_agent_signings":0}

                with patch.object(sv, "advance_save_day", side_effect=day):
                    aa.advance_action(Path("."), self.canonical, path, {"postseason_exit":True})
                    self.assertEqual(stored["state"]["current_date"],"2027-06-22")
                    self.assertFalse(sv.postseason_exit_required(stored))
                    self.assertEqual(stored["playoff_state"],completed["playoff_state"])
                    with self.assertRaisesRegex(ValueError,"Reveal the lottery"):
                        aa.advance_action(Path("."), self.canonical, path, {"draft_enter":True})
                    stored["draft_orders"] = {"2027":{"draft_order":[]}}
                    aa.advance_action(Path("."), self.canonical, path, {"draft_enter":True})
                    self.assertEqual(stored["state"]["current_date"],"2027-06-25")
                    self.assertEqual(stored["state"]["phase"],"draft")

    def test_playoff_menu_advances_after_real_history_archival_and_reload(self):
        # Older history-backed careers can have every box score archived.
        self.stack.enter_context(patch.dict(hs.HOT_TAIL_LIMITS, {"game_results": 0}))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            initial = deepcopy(self.save)
            initial["version"] = sv.SAVE_VERSION
            sv.write_save(path, initial)

            def snapshot(*args, **kwargs):
                return {"home": {"save": deepcopy(sv.load_save(path)["state"])}}

            with patch.object(aa, "normalized_read_save", side_effect=lambda c, p: sv.load_save(p)), \
                 patch.object(sv, "ensure_league_save_defaults", side_effect=lambda s, c: s), \
                 patch.object(aa, "ensure_league_save_defaults", side_effect=lambda s, c: s), \
                 patch.object(aa, "dashboard_snapshot_payload", side_effect=snapshot):
                def action(mode, **kwargs):
                    return aa.advance_action(Path("."), self.canonical, path, {"postseason_sim": mode, **kwargs})

                for index, day in enumerate(("2027-04-13", "2027-04-14", "2027-04-16"), start=1):
                    action("game", postseason_confirmed="2027-04-13")
                    saved = sv.load_save(path)
                    self.assertEqual(saved["state"]["current_date"], day)
                    self.assertEqual(len(saved["playoff_state"]["games"]), index * 2)
                    self.assertEqual(saved["game_results"], [])
                    self.assertEqual(len(saved["game_result_summaries"]), index * 2)

                action("game")
                saved = sv.load_save(path)
                self.assertTrue(all(len(s["game_ids"]) == 1 for s in saved["playoff_state"]["series"]))
                action("series")
                self.assertEqual(sv.load_save(path)["playoff_state"]["round"], "conference_semifinals")
                action("all")
                saved = sv.load_save(path, include_history=True)
                self.assertEqual(saved["playoff_state"]["status"], "completed")
                ids = [g["externalGameId"] for g in saved["playoff_state"]["games"]]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(set(ids), {g["game_id"] for g in saved["game_results"]})
                for totals in saved["playoff_player_stats"].values():
                    self.assertEqual(totals["minutes"], totals["games"] * 32)
                before = sv.load_save(path)
                self.assertEqual(action("game")["status"], "postseason_complete")
                self.assertEqual(sv.load_save(path), before)


class PostseasonHistoryLookupTests(unittest.TestCase):
    def test_archived_playoff_result_is_not_resimulated(self):
        canonical = {"teams": []}
        fixture = sv.playoff_game_fixture(canonical, "away", "home", "2027-04-13", "East:7v8")
        for game_id in (fixture["externalGameId"], sv.stable_id("playoff_game", "East:7v8", "away", "home")):
            with self.subTest(game_id=game_id):
                summary = {"game_id": game_id, "away_team_id": "away", "home_team_id": "home",
                           "away_score": 101, "home_score": 99}
                saved = {"game_results": [], "game_result_summaries": [summary]}
                before = deepcopy(saved)
                with patch.object(sv, "advance_lifecycle_to") as lifecycle:
                    result = sv.simulate_playoff_game(canonical, saved, None, "away", "home",
                                                      "2027-04-13", 17, "East:7v8")
                self.assertEqual(result, summary)
                self.assertEqual(saved, before)
                lifecycle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
