"""Player time must advance through postseason/offseason, including saved medicals."""
from copy import deepcopy
import gc
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data import app_actions as aa, draft, health, save as sv
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.schema import to_plain, InjuryEvent
from nba_gm_data import spatial

ROOT = Path(__file__).resolve().parents[1]


class PlayerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.was_gc = gc.isenabled()
        gc.disable()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.canonical = load_app_canonical(ROOT)
        cls.base = sv.create_league_save(ROOT, cls.canonical, "GSW", Path(cls.tmp.name) / "base.json", seed=17)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        if cls.was_gc:
            gc.enable()

    def fixture(self, day="2027-04-12"):
        saved = deepcopy(self.base)
        sv.set_save_date_phase(saved, day)
        saved.pop("lifecycle_state", None)
        saved["applied_development_months"] = []
        return saved

    def test_full_player_year_has_twelve_months_and_repeat_is_noop(self):
        saved = self.fixture("2026-10-01")
        sv.advance_lifecycle_to(self.canonical, saved, "2027-10-01", 17, ROOT)
        expected = [f"2026-{m:02}" for m in (11, 12)] + [f"2027-{m:02}" for m in range(1, 11)]
        self.assertEqual(saved["applied_development_months"], expected)
        before = deepcopy(saved)
        sv.advance_lifecycle_to(self.canonical, saved, "2027-10-01", 17, ROOT)
        self.assertEqual(saved, before)

    def test_month_boundary_partition_and_serialized_reload_are_equal(self):
        for seed in (0, 17, 29):
            with self.subTest(seed=seed):
                bulk = self.fixture("2027-06-28")
                daily = deepcopy(bulk)
                sv.advance_lifecycle_to(self.canonical, bulk, "2027-07-03", seed, ROOT)
                for day in ("2027-06-29", "2027-06-30", "2027-07-01", "2027-07-02", "2027-07-03"):
                    daily = json.loads(json.dumps(daily))
                    sv.advance_lifecycle_to(self.canonical, daily, day, seed, ROOT)
                self.assertEqual(bulk, daily)
                self.assertEqual(bulk["applied_development_months"], ["2027-07"])

    def test_zero_minute_injured_veteran_still_declines_but_inactive_does_not(self):
        active = sv.canonical_with_save(self.canonical, self.fixture())
        veteran = next(p for p in active["players"] if float(p.get("age") or 0) >= 35 and p.get("team_id"))
        veteran["minutes_projection"] = 0
        active["player_health_states"] = [{**health.default_state_dict(veteran["id"], "2027-04-30"), "availability_status": "out", "current_injury_id": "injured", "return_date": "2027-08-01"}]
        result = health.advance_development(active, "2027-05", seed=17)
        event = next(e for e in result["events"] if e["player_id"] == veteran["id"])
        self.assertLess(event["trait_deltas"]["stamina_cardio"], 0)
        veteran["_inactive_player"] = True
        self.assertNotIn(veteran["id"], {e["player_id"] for e in health.advance_development(active, "2027-05", seed=17)["events"]})

    def test_monthly_events_use_roster_at_that_time_and_do_not_backfill_rookies(self):
        saved = self.fixture("2027-04-30")
        sv.advance_lifecycle_to(self.canonical, saved, "2027-05-01", 17, ROOT)
        veteran = next(p for p in self.canonical["players"] if p.get("team_id") == "team_gsw" and float(p.get("age") or 0) >= 31)
        saved["roster_overrides"][veteran["id"]] = "team_bos"
        pid = "rookie_after_may"
        saved["generated_players"].append({"id": pid, "name": "Late Arrival", "team_id": "team_gsw", "age": 19, "position": "SG", "minutes_projection": 20})
        sv.advance_lifecycle_to(self.canonical, saved, "2027-06-01", 17, ROOT)
        events = saved["development_events"]
        self.assertEqual({e["team_id"] for e in events if e["player_id"] == veteran["id"] and e["month"] == "2027-05"}, {"team_gsw"})
        self.assertEqual({e["team_id"] for e in events if e["player_id"] == veteran["id"] and e["month"] == "2027-06"}, {"team_bos"})
        self.assertEqual({e["month"] for e in events if e["player_id"] == pid}, {"2027-06"})

    def test_rotation_refresh_does_not_feed_minutes_back_into_its_own_rating(self):
        saved = self.fixture()
        active = sv.canonical_with_save(self.canonical, saved)
        first = deepcopy(saved["rotation_snapshots"])
        for _ in range(4):
            sv.refresh_active_runtime_state(active, saved)
        self.assertEqual(first, saved["rotation_snapshots"])

    def test_re_signing_jump_and_day_close_with_the_same_completed_counter(self):
        saved = {"meta": {"season": "2026-27"}, "state": {"current_date": "2027-06-27", "phase": "re_signing"},
                 "free_agency_state": {"re_signing_day": 1, "re_signing_day_count": 2}}
        states = {"bulk": deepcopy(saved), "daily": deepcopy(saved)}
        def tick(canonical, saved, target, *args):
            sv.set_save_date_phase(saved, target)
        with patch("nba_gm_data.play.initialize_free_agency_market"), \
             patch.object(aa, "load_save", side_effect=lambda p: states[str(p)]), \
             patch.object(aa, "ensure_league_save_defaults", side_effect=lambda s, c: s), \
             patch.object(aa, "canonical_with_save", return_value={}), \
             patch.object(aa, "resolve_team", return_value={"id": "team_gsw"}), \
             patch.object(aa, "free_agency_room_payload", return_value={}), \
             patch.object(aa, "advance_lifecycle_to", side_effect=tick), patch.object(aa, "write_save"):
            aa.advance_re_signing_action({}, Path("bulk"), {"team": "GSW", "mode": "open_market"})
            aa.advance_re_signing_action({}, Path("daily"), {"team": "GSW", "mode": "day"})
            aa.advance_re_signing_action({}, Path("daily"), {"team": "GSW", "mode": "open_market"})
        self.assertEqual(states["bulk"], states["daily"])
        self.assertEqual(states["bulk"]["free_agency_state"]["re_signing_day"], 2)

    def test_out_player_missed_games_and_same_day_health_are_idempotent(self):
        saved = self.fixture("2027-04-17")
        player = next(p for p in self.canonical["players"] if p.get("team_id") == "team_gsw")
        pid = player["id"]
        state = next(s for s in saved["health_states"] if s["player_id"] == pid)
        state.update(availability_status="out", current_injury_id="test", return_date="2027-05-01", games_missed=0)
        saved.setdefault("rotation_recommendations", {})[pid] = 0
        game = sv.playoff_game_fixture(self.canonical, "team_gsw", "team_bos", "2027-04-18", "test")
        sv.advance_lifecycle_to(self.canonical, saved, "2027-04-18", 17, ROOT, games=[game])
        self.assertEqual(next(s for s in saved["health_states"] if s["player_id"] == pid)["games_missed"], 1)
        before = deepcopy(saved)
        sv.advance_lifecycle_to(self.canonical, saved, "2027-04-18", 17, ROOT, games=[game])
        self.assertEqual(saved, before)

    def test_playoff_round_and_day_calls_match_including_health_and_months(self):
        for seed in (17, 29):
            with self.subTest(seed=seed):
                saved = self.fixture("2027-04-30")
                state = {"year": "2027", "seed": seed, "round": "conference_semifinals", "status": "in_progress", "games": [],
                         "series": [sv.playoff_series_record("West", "conference_semifinals", "team_gsw", "team_lal"), sv.playoff_series_record("East", "conference_semifinals", "team_bos", "team_mia")]}
                saved["playoff_state"] = state
                path = Path(self.tmp.name) / f"round-{seed}.json"
                sv.write_save(path, deepcopy(saved))
                sv.simulate_playoff_round(self.canonical, path, seed=seed)
                bulk = sv.load_save(path)
                daily = deepcopy(saved)
                while daily["playoff_state"]["round"] == "conference_semifinals":
                    sv.simulate_playoff_day(self.canonical, daily, daily["playoff_state"], seed, None)
                    sv.update_save_date_to_latest_playoff_game(daily)
                    daily = json.loads(json.dumps(daily))
                for key in ("health_states", "injury_events", "development_events", "applied_development_months", "playoff_state", "lifecycle_state"):
                    self.assertEqual(bulk[key], daily[key], key)
                self.assertEqual(bulk["applied_development_months"], ["2027-05"])
                dates = [g["gameDate"] for g in daily["playoff_state"]["games"]]
                self.assertEqual(dates, sorted(dates))

    def test_playoff_game_ids_are_season_unique_and_legacy_replays_are_noops(self):
        first = sv.playoff_game_fixture(self.canonical, "team_gsw", "team_bos", "2027-06-04", "finals:g1")
        second = sv.playoff_game_fixture(self.canonical, "team_gsw", "team_bos", "2028-06-04", "finals:g1")
        self.assertNotEqual(first["externalGameId"], second["externalGameId"])
        saved = self.fixture()
        legacy = {"game_id": sv.stable_id("playoff_game", "finals:g1", "team_gsw", "team_bos"), "home_score": 100}
        saved["game_results"] = [legacy]
        before = deepcopy(saved)
        self.assertEqual(sv.simulate_playoff_game(self.canonical, saved, ROOT, "team_gsw", "team_bos", "2027-06-04", 17, "finals:g1"), legacy)
        self.assertEqual(saved, before)

    def test_generated_medicals_are_varied_repeatable_and_do_not_change_ratings(self):
        first = to_plain(draft.generate_draft_class_records("2030", seed=17))
        second = to_plain(draft.generate_draft_class_records("2030", seed=17))
        self.assertEqual(first, second)
        profiles = [p["medical_profile"] for p in first["draft_prospects"]]
        self.assertTrue(any(p["injury_prone"] for p in profiles))
        self.assertTrue(any(p["major_prior_injuries"] for p in profiles))
        self.assertTrue(any(not p["major_prior_injuries"] for p in profiles))
        self.assertGreater(len({p["durability"] for p in profiles}), 30)
        with patch.object(draft, "generated_prospect_medical_profile", return_value={}):
            healthy = to_plain(draft.generate_draft_class_records("2030", seed=17))
        for a, b in zip(first["draft_prospects"], healthy["draft_prospects"]):
            self.assertEqual({k: v for k, v in a.items() if k != "medical_profile"}, {k: v for k, v in b.items() if k != "medical_profile"})
        self.assertEqual(first["draft_prospect_traits"], healthy["draft_prospect_traits"])

    def test_medical_risk_discounts_but_does_not_disqualify_elite_talent(self):
        healthy = {"id": "p", "potential": 90, "current_ability": 80, "floor": 70, "ceiling": 98, "volatility": 15}
        risky = {**healthy, "medical_profile": {"durability": 35, "injury_prone": True, "major_prior_injuries": [{"body_area": "knee"}], "current_injury": {"return_date": "2030-09-01"}}}
        self.assertLess(draft.generated_bpa_grade(risky), draft.generated_bpa_grade(healthy))
        self.assertGreater(draft.generated_bpa_grade(risky), draft.generated_bpa_grade({**healthy, "potential": 55, "current_ability": 45, "ceiling": 65, "floor": 35}))
        entry = {"risk_adjusted_grade": 75, "prospect_id": "p"}
        score = lambda p: draft.draft_selection_score({}, entry, p, "team_gsw", 1, 17, 0.6)
        self.assertLess(score(risky), score(healthy))
        self.assertLessEqual(score(healthy) - score(risky), 9)
        with patch.object(draft, "prospect_team_fit", return_value=50), patch.object(draft, "prospect_cap_value", return_value=50):
            ranked = draft.rank_generated_prospects_for_team({}, "team_gsw", [{**risky, "id": "risky"}, {**healthy, "id": "healthy"}])
        self.assertEqual([p["id"] for p in ranked], ["healthy", "risky"])

    def test_medical_carryover_recovery_and_reload_do_not_reinjure(self):
        saved = self.fixture("2030-06-28")
        pid = "rookie_medical_test"
        medical = {"durability": 39, "injury_prone": True, "major_prior_injuries": [{"body_area": "knee"}], "current_injury": {"body_area": "knee", "severity": "medium", "start_date": "2030-06-10", "return_date": "2030-07-03"}}
        saved["generated_players"].append({"id": pid, "name": "Medical Test", "age": 20, "position": "SG", "team_id": "team_gsw", "minutes_projection": 20, "medical_profile": medical})
        active = sv.canonical_with_save(self.canonical, saved)
        profile = next(p for p in active["player_health_profiles"] if p["player_id"] == pid)
        self.assertEqual(profile["durability"], 39)
        self.assertEqual(profile["major_prior_injuries"], medical["major_prior_injuries"])
        event = next(e for e in saved["injury_events"] if e["player_id"] == pid)
        InjuryEvent(**event)
        self.assertEqual(next(s for s in saved["health_states"] if s["player_id"] == pid)["availability_status"], "out")
        sv.advance_lifecycle_to(self.canonical, saved, "2030-07-04", 17, ROOT)
        saved = json.loads(json.dumps(saved))
        saved["roster_overrides"][pid] = "team_bos"
        sv.canonical_with_save(self.canonical, saved)
        self.assertEqual(next(s for s in saved["health_states"] if s["player_id"] == pid)["availability_status"], "active")
        self.assertEqual(len([e for e in saved["injury_events"] if e["player_id"] == pid]), 1)

    def test_precomputed_medical_boards_are_idempotent_and_real_history_untouched(self):
        active = draft.with_draft_context(self.canonical)
        again = draft.with_draft_context(active)
        self.assertEqual(active["draft_prospects"], again["draft_prospects"])
        self.assertEqual(active["draft_board_entries"], again["draft_board_entries"])
        original = {p["id"]: p for p in self.canonical["draft_prospects"]}
        for p in active["draft_prospects"]:
            if p.get("league") != "generated":
                self.assertEqual(p.get("medical_profile") or {}, original[p["id"]].get("medical_profile") or {})

    def test_discarded_universe_trait_cache_cannot_poison_a_new_draft(self):
        rows = [{"player_id": "p", "trait_key": "shooting_range", "value": 90}]
        active = {"traits": rows}
        spatial._SPATIAL_INDEX_CACHE[id(active)] = {"traits_id": id(rows), "traits_source": [], "traits": {"p": {"shooting_range": 20}}}
        try:
            self.assertEqual(spatial._trait_index(active)["p"]["shooting_range"], 90)
        finally:
            spatial.invalidate_spatial_cache(active)

    def test_roster_cap_is_not_bypassed_by_rookie_protection_or_legacy_limit(self):
        saved = self.fixture("2027-11-01")
        players = [{"id": f"p{i}", "name": f"Player {i}", "team_id": "ai", "minutes_projection": i, "age": 20} for i in range(18)]
        canonical = {"players": players, "teams": [{"id": "ai", "abbrev": "AI"}]}
        saved["incoming_rookies"] = [{"player_id": p["id"], "draft_year": "2027"} for p in players]
        saved["roster_cutdown_baselines"] = {"ai": 18}
        with patch.object(sv, "active_players_for_roster_checks", return_value=players):
            sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(sum(saved["roster_overrides"].get(p["id"], "ai") == "ai" for p in players), 15)
        saved["pending_roster_cutdowns"] = [{"team_abbrev": "GSW", "current_count": 16, "target_count": 15}]
        with self.assertRaisesRegex(ValueError, "Cut to 15"):
            sv.guard_required_phase_actions(saved, "2027-11-01", "2027-11-02")

    def test_legacy_overflow_is_visible_without_a_saved_flag_or_disk_mutation(self):
        saved = self.fixture("2027-11-01")
        candidates = [p for p in self.canonical["players"] if p.get("team_id") == "team_bos"][:2]
        for player in candidates:
            saved["roster_overrides"][player["id"]] = "team_gsw"
            saved["free_agent_player_ids"] = [pid for pid in saved["free_agent_player_ids"] if pid != player["id"]]
        saved["pending_roster_cutdowns"] = []
        path = Path(self.tmp.name) / "legacy-overflow.json"
        sv.write_save(path, saved)
        before = path.read_bytes()
        overrides = deepcopy(saved["roster_overrides"])
        status = sv.save_status(ROOT, self.canonical, path, prepared_save=saved)
        self.assertEqual(status["pending_counts"]["cutdowns"], 1)
        self.assertEqual(saved["roster_overrides"], overrides)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
