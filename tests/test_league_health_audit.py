"""Observer measurements must not confuse exits, rotation and talent change."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import league_health_audit as audit


class LeagueHealthAuditTests(unittest.TestCase):
    def test_deadline_is_reached_then_explicitly_confirmed(self):
        save = {"state": {"phase": "regular_season", "current_date": "2027-02-03"}}
        self.assertEqual(audit.select_advance(save, 7), {"to_date": "2027-02-05"})
        save["state"]["current_date"] = "2027-02-05"
        self.assertEqual(audit.select_advance(save, 7)["trade_deadline_confirmed"], "2027-02-05")

    def test_required_phases_stop_instead_of_faking_a_full_season(self):
        for phase in ("draft", "free_agency", "re_signing", "playoffs"):
            with self.assertRaisesRegex(RuntimeError, "Manual audit checkpoint"):
                audit.select_advance({"state": {"phase": phase, "current_date": "2027-06-25"}}, 7)

    def test_rotation_change_does_not_become_measured_development(self):
        active = {"players": [{"id": "p", "name": "Player", "age": 20, "team_id": "team", "minutes_projection": 5}], "traits": []}
        first = audit.census(active, {})
        active["players"][0]["minutes_projection"] = 30
        second = audit.census(active, {})
        self.assertNotEqual(first["players"][0]["engine"], second["players"][0]["engine"])
        self.assertEqual(first["players"][0]["fixed24_engine"], second["players"][0]["fixed24_engine"])
        self.assertEqual(audit.flow(first, second)["fixed24_engine_change_by_start_age"]["20"]["mean"], 0)

    def test_retired_and_exited_are_not_active_talent_free_agents_are_separate(self):
        players = [{"id": p, "name": p, "age": 21, "team_id": "team"} for p in ("active", "fa", "retired", "exit")]
        result = audit.census({"players": players, "traits": []}, {"retired_player_ids": ["retired"], "league_exit_player_ids": ["exit"], "free_agent_player_ids": ["fa"]})
        self.assertEqual(result["active_pool"]["count"], 2)
        self.assertEqual(result["rostered"]["count"], 1)
        self.assertEqual(result["active_pool"]["by_age_year"]["21"]["count"], 2)

    def test_archived_free_agents_with_retired_flags_are_not_counted_as_retirements(self):
        result = audit.census({"players": [], "traits": []},
                              {"retired_player_ids": ["retired", "exit"], "league_exit_player_ids": ["exit"]})
        self.assertEqual(result["retired_flag_count"], 2)
        self.assertEqual(result["retired_count"], 1)
        self.assertEqual(result["league_exit_count"], 1)

    def test_regular_roster_overflow_excludes_free_agents_and_allows_offseason(self):
        active = {"players": [{"id": str(i), "team_id": "t", "age": 20} for i in range(16)], "traits": []}
        save = {"state": {"phase": "regular_season"}}
        self.assertEqual(audit.census(active, save)["regular_season_roster_overflow"], {"t": 16})
        save["free_agent_player_ids"] = ["0"]
        self.assertEqual(audit.census(active, save)["regular_season_roster_overflow"], {})
        save["free_agent_player_ids"] = []
        save["state"]["phase"] = "preseason"
        self.assertEqual(audit.census(active, save)["regular_season_roster_overflow"], {})

    def test_career_driver_requires_all_regular_games_and_uses_real_phase_actions(self):
        save = {"meta": {"season": "2026-27"}, "state": {"phase": "play_in", "current_date": "2027-04-13"},
                "team_records": {str(i): {"wins": 41, "losses": 41} for i in range(30)}}
        save["team_records"]["0"]["wins"] = 40
        with self.assertRaisesRegex(RuntimeError, "1229/1230"):
            audit.career_action(save, 14, "GSW")
        save["team_records"]["0"]["wins"] = 41
        self.assertEqual(audit.career_action(save, 14, "GSW"), ("simulate_playoff_all", {}))
        save["playoff_state"] = {"status": "completed"}
        self.assertEqual(audit.career_action(save, 14, "GSW")[1]["to_date"], "2027-06-22")
        for phase, action in (("draft_lottery", "draft_reveal_lottery"), ("draft", "draft_sim_all"),
                              ("re_signing", "advance_re_signing"), ("free_agency", "advance_free_agency")):
            save["state"]["phase"] = phase
            self.assertEqual(audit.career_action(save, 14, "GSW")[0], action)

    def test_equal_league_totals_do_not_hide_a_team_with_missing_games(self):
        records = {str(i): {"wins": 41, "losses": 41} for i in range(30)}
        records["0"]["wins"] = 40
        records["1"]["wins"] = 42
        with self.assertRaisesRegex(RuntimeError, "records must balance"):
            audit.regular_complete({"team_records": records})

    def test_same_day_draft_progress_counts_but_identical_replay_does_not(self):
        before = {"date": "2027-06-25", "season": "2026-27", "phase": "draft", "phase_state": {"draft_index": 0}}
        after = {**before, "phase_state": {"draft_index": 60}}
        self.assertNotEqual(audit.state_marker(before), audit.state_marker(after))
        self.assertEqual(audit.state_marker(before), audit.state_marker(dict(before)))

    def test_career_probe_tracks_peak_not_terminal_rating_and_never_overwrites(self):
        generated = {"draft_classes": [{}], "draft_prospects": [{"rank": 1, "current_ability": 45, "potential": 80}]}
        probe = {"players": [{"id": "p", "age": 19}], "traits": []}

        def develop(context, events):
            context["step"] = context.get("step", 0) + 1

        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()), \
                patch.object(audit, "converted_class", return_value=(generated, probe)), \
                patch.object(audit, "input_fingerprint", return_value={}), \
                patch.object(audit, "advance_development", return_value={"events": []}), \
                patch.object(audit, "apply_development_events_to_traits", side_effect=develop), \
                patch.object(audit, "player_display_attribute_summary", side_effect=lambda c, p: {"overall": [70, 91, 86][c.get("step", 0)]}):
            out = Path(folder)
            audit.career_probe({"teams": [{}]}, out, 1, [17], 24, 2)
            report = json.loads((out / "career_probe.json").read_text())
            player = report["players"][0]
            self.assertEqual(player["peak"], 91)
            self.assertEqual(player["peak_month"], 1)
            self.assertEqual(player["first_threshold_months"]["90"], 1)
            self.assertEqual(player["checkpoints"]["2"], 86)
            self.assertEqual(report["by_rank"]["1-3"]["peak_threshold_counts"]["90"], 1)
            with self.assertRaises(FileExistsError):
                audit.career_probe({"teams": [{}]}, out, 1, [17], 24, 2)

    def test_replacement_probe_adds_each_class_once_and_ages_from_entry_date(self):
        canonical = {"teams": [{"id": "t"}], "players": [{"id": "v", "age": 40, "team_id": "t"}], "traits": []}

        def incoming(year, seed, team):
            return {}, {"players": [{"id": str(year), "age": 19, "team_id": "t"}], "traits": []}

        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()), \
                patch.object(audit, "converted_class", side_effect=incoming), \
                patch.object(audit, "input_fingerprint", return_value={}), \
                patch.object(audit, "advance_development", return_value={"events": []}):
            audit.replacement_probe(canonical, Path(folder), 2, 17, 32)
            report = json.loads((Path(folder) / "replacement_probe.json").read_text())
        snapshots = report["snapshots"]
        self.assertEqual([s["active_pool"]["count"] for s in snapshots], [1, 2, 2])
        self.assertEqual({p["id"]: p["age"] for p in snapshots[-1]["players"]}, {"2027": 20, "2028": 19})
        self.assertEqual(canonical["players"][0]["age"], 40)

    def test_career_probe_does_not_advance_age_cutoffs_fractionally(self):
        generated = {"draft_classes": [{}], "draft_prospects": [{"rank": 1, "current_ability": 45, "potential": 80}]}
        probe = {"players": [{"id": "p", "age": 19}], "traits": []}
        observed = []

        def advance(context, month, seed):
            observed.append((month, context["players"][0]["age"]))
            return {"events": []}

        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()), \
                patch.object(audit, "converted_class", return_value=(generated, probe)), \
                patch.object(audit, "input_fingerprint", return_value={}), \
                patch.object(audit, "advance_development", side_effect=advance), \
                patch.object(audit, "player_display_attribute_summary", return_value={"overall": 70}):
            audit.career_probe({"teams": [{}]}, Path(folder), 1, [17], 24, 13)
        self.assertEqual([age for _, age in observed], [19] * 12 + [20])
        self.assertEqual(observed[0][0], "2027-10")
        self.assertEqual(observed[-1][0], "2028-10")

    def test_actual_selection_slot_and_team_are_used_instead_of_prospect_rank(self):
        generated = audit.to_plain(audit.generate_draft_class_records("2028", seed=17))
        generated["selections"] = [
            {"id": p["id"], "prospect_id": p["id"], "draft_year": "2028", "overall_pick": 61 - p["rank"], "team_id": "b"}
            for p in generated["draft_prospects"]]
        _, converted = audit.converted_class(2028, 17, {"id": "a", "abbrev": "A"}, drafted=generated,
                                             teams=[{"id": "a", "abbrev": "A"}, {"id": "b", "abbrev": "B"}])
        player = converted["players"][0]
        self.assertEqual(player["team_id"], "b")
        self.assertEqual(player["overall_pick"], 60)
        self.assertEqual(converted["_audit_draft_metadata"][player["id"]]["prospect_rank"], 1)
        generated["selections"].pop()
        _, converted = audit.converted_class(2028, 17, {"id": "b", "abbrev": "B"}, drafted=generated)
        self.assertEqual(len(converted["players"]), 59)
        self.assertEqual(len({p["overall_pick"] for p in converted["players"]}), 59)

    def test_best_staff_probe_uses_real_model_caps_not_a_growth_override(self):
        from nba_gm_data.health import development_staff_modifiers

        probe = {"players": [{"id": "p", "team_id": "t"}]}
        audit.add_probe_staff(probe, 100)
        modifiers = development_staff_modifiers(probe, "t", 3)
        self.assertEqual(modifiers["development_multiplier"], 1.28)
        self.assertEqual(modifiers["patience_multiplier"], 1.16)

    def test_health_diagnostic_reports_its_reference_and_does_not_write_a_save(self):
        with tempfile.TemporaryDirectory() as folder:
            result = audit.health_blind_spots(Path(folder))
            self.assertEqual(list(Path(folder).iterdir()), [])
        self.assertEqual(result["expected_missed_games"], 1)
        self.assertEqual(result["missed_counter_before_projection"], 1)
        self.assertEqual(result["projected_minutes"], 0)
        self.assertEqual(result["counter_matches_reference"], result["missed_counter_after_projection"] == 1)

    def test_calendar_coverage_survives_rollover_clearing_the_month_list(self):
        snapshots = [
            {"season": "2027-28", "date": "2027-10-01", "phase": "preseason", "development_months": []},
            {"season": "2027-28", "date": "2028-04-12", "phase": "regular_season",
             "development_months": ["2027-11", "2027-12", "2028-01", "2028-02", "2028-03", "2028-04"]},
            {"season": "2028-29", "date": "2028-10-01", "phase": "preseason", "development_months": []},
        ]
        result = audit.calendar_coverage(snapshots)
        cycle = result["completed_cycles"][0]
        self.assertEqual(len(cycle["expected"]), 12)
        self.assertEqual(len(cycle["processed"]), 6)
        self.assertEqual(cycle["missing"], [f"2028-{m:02}" for m in range(5, 11)])
        recovered = audit.calendar_coverage(snapshots, cycle["missing"])
        self.assertEqual(recovered["completed_cycles"][0]["missing"], [])


if __name__ == "__main__":
    unittest.main()
