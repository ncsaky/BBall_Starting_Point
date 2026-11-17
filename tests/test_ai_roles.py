"""Role renewal belongs to simulation dates, not refreshes or user overrides."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from nba_gm_data import health, save as sv


class AiRoleTests(unittest.TestCase):
    def fixture(self):
        canonical = {"teams": [{"id": "ai", "abbrev": "AI"}, {"id": "human", "abbrev": "HUM"}],
                     "players": [], "traits": [], "contracts": []}
        saved = {"meta": {"season": "2036-37", "user_team_id": "human"},
                 "state": {"current_date": "2036-10-01", "phase": "preseason"},
                 "rotation_baselines": {}, "rotation_overrides": {}, "rotation_snapshots": {},
                 "rotation_recommendations": {}, "health_states": []}
        for team in ("ai", "human"):
            for index in range(15):
                pos = ["PG", "SG", "SF", "PF", "C"][index % 5]
                pid = f"{team}{index:02}"
                quality = 72 if index < 5 else 66 if index < 10 else 50
                if team == "ai" and index == 1:
                    quality = 40
                if team == "ai" and index == 6:
                    quality = 88
                canonical["players"].append({"id": pid, "name": pid, "team_id": team, "age": 27,
                                              "position": pos, "height_inches": 74 + index % 5 * 2.5,
                                              "minutes_projection": 32 if index < 5 else 8 if index < 10 else 0})
                canonical["traits"].extend({"player_id": pid, "trait_key": key, "value": quality} for key in health.DEVELOPMENT_TRAITS)
        saved["rotation_baselines"] = sv.initial_rotation_baselines(canonical)
        return canonical, saved

    def test_talent_can_overturn_a_stale_role_with_bounded_continuity(self):
        canonical, saved = self.fixture()
        human_before = {p["id"]: saved["rotation_baselines"][p["id"]] for p in canonical["players"] if p["team_id"] == "human"}
        self.assertEqual(sv.reassess_ai_roles(canonical, saved, "2036-10-02"), ["ai"])
        projection = sv.team_rotation_projection(canonical, saved, "ai")
        self.assertGreater(projection["ai06"], projection["ai01"] + 10)
        self.assertAlmostEqual(sum(projection.values()), 240, delta=.1)
        self.assertEqual(human_before, {pid: saved["rotation_baselines"][pid] for pid in human_before})
        self.assertNotIn("human", saved["ai_role_state"])

    def test_reloads_same_day_refreshes_and_months_do_not_reroll_roles(self):
        canonical, saved = self.fixture()
        sv.reassess_ai_roles(canonical, saved, "2036-10-02")
        baseline = deepcopy(saved["rotation_baselines"])
        saved = json.loads(json.dumps(saved))
        self.assertEqual(sv.reassess_ai_roles(canonical, saved, "2036-10-02"), [])
        self.assertEqual(sv.reassess_ai_roles(canonical, saved, "2036-10-25"), [])
        self.assertEqual(sv.reassess_ai_roles(canonical, saved, "2036-09-01"), [])
        sv.apply_save_rotation_projection(canonical, saved)
        sv.apply_save_rotation_projection(canonical, saved)
        self.assertEqual(saved["rotation_baselines"], baseline)
        self.assertEqual(sv.reassess_ai_roles(canonical, saved, "2036-11-01", calendar=False), [])
        self.assertEqual(sv.reassess_ai_roles(canonical, saved, "2036-11-01"), ["ai"])

    def test_roster_change_triggers_even_in_same_month(self):
        canonical, saved = self.fixture()
        sv.reassess_ai_roles(canonical, saved, "2036-10-02")
        canonical["players"] = [p for p in canonical["players"] if p["id"] != "ai14"]
        self.assertEqual(sv.reassess_ai_roles(canonical, saved, "2036-10-03", calendar=False), ["ai"])
        self.assertEqual(saved["ai_role_state"]["ai"]["through_date"], "2036-10-03")

    def test_all_human_teams_and_explicit_overrides_are_protected(self):
        canonical, saved = self.fixture()
        saved["meta"]["human_team_ids"] = ["ai", "human"]
        before = deepcopy(saved)
        self.assertEqual(sv.reassess_ai_roles(canonical, saved, "2036-10-02"), [])
        self.assertEqual(saved, before)
        saved["meta"]["human_team_ids"] = ["human"]
        saved["rotation_overrides"]["ai"] = {"ai06": 40}
        before = deepcopy(saved)
        self.assertEqual(sv.reassess_ai_roles(canonical, saved, "2036-10-02"), [])
        self.assertEqual(saved, before)

    def test_injuries_change_available_minutes_not_the_healthy_role(self):
        canonical, healthy = self.fixture()
        injured = deepcopy(healthy)
        injured["health_states"] = [{"player_id": "ai06", "availability_status": "out"}]
        sv.reassess_ai_roles(canonical, healthy, "2036-10-02")
        sv.reassess_ai_roles(canonical, injured, "2036-10-02")
        self.assertEqual(healthy["rotation_baselines"], injured["rotation_baselines"])
        projection = sv.team_rotation_projection(canonical, injured, "ai")
        self.assertEqual(projection["ai06"], 0)
        self.assertAlmostEqual(sum(projection.values()), 240, delta=.1)
        injured["health_states"] = []
        self.assertGreater(sv.team_rotation_projection(canonical, injured, "ai")["ai06"], 25)

    def test_explicit_coach_recommendations_are_not_rewritten(self):
        canonical, saved = self.fixture()
        saved["rotation_recommendations"] = {"ai06": {"team_id": "ai", "target_minutes": 36, "coach_commitment": 1}}
        original = deepcopy(saved["rotation_recommendations"])
        sv.reassess_ai_roles(canonical, saved, "2036-10-02")
        self.assertEqual(saved["rotation_recommendations"], original)
        self.assertGreaterEqual(sv.team_rotation_projection(canonical, saved, "ai")["ai06"], 36)

    def test_exactly_five_available_ai_players_can_play_48_each(self):
        canonical, saved = self.fixture()
        sv.reassess_ai_roles(canonical, saved, "2036-10-02")
        saved["health_states"] = [{"player_id": f"ai{i:02}", "availability_status": "out"} for i in range(5,15)]
        projection = sv.team_rotation_projection(canonical, saved, "ai")
        self.assertEqual(sum(projection.values()), 240)
        self.assertEqual([projection[f"ai{i:02}"] for i in range(5)], [48] * 5)

    def test_six_or_seven_available_players_still_cover_the_game(self):
        for count in (6, 7):
            canonical, saved = self.fixture()
            sv.reassess_ai_roles(canonical, saved, "2036-10-02")
            saved["health_states"] = [{"player_id": f"ai{i:02}", "availability_status": "out"} for i in range(count,15)]
            projection = sv.team_rotation_projection(canonical, saved, "ai")
            self.assertAlmostEqual(sum(projection.values()), 240, delta=.1)
            self.assertLessEqual(max(projection.values()), 42)

    def test_position_fit_keeps_two_deep_frontcourt_and_backcourt(self):
        canonical, saved = self.fixture()
        sv.reassess_ai_roles(canonical, saved, "2036-10-02")
        selected = saved["ai_role_state"]["ai"]["rotation_player_ids"]
        by_id = {p["id"]: p for p in canonical["players"]}
        self.assertEqual(len(selected), 10)
        for group in (selected[:5], selected[5:]):
            for slot, pid in enumerate(group, 1):
                fits = sv.STARTING_FIVE_SLOT_FITS[str(slot)]
                self.assertGreater(max(fits.get(pos, 0) for pos in sv.player_position_tokens(by_id[pid])), 0)
                self.assertFalse(sv.starting_slot_hard_violation(str(slot), sv.player_height_inches(by_id[pid]), sv.player_position_tokens(by_id[pid])))

    def test_shuffled_inputs_do_not_change_assignment_or_roles(self):
        canonical, saved = self.fixture()
        other, second = deepcopy(canonical), deepcopy(saved)
        other["players"].reverse()
        sv.reassess_ai_roles(canonical, saved, "2036-10-02")
        sv.reassess_ai_roles(other, second, "2036-10-02")
        self.assertEqual(saved, second)

    def test_lifecycle_checks_roles_after_development_and_before_return(self):
        canonical, saved = self.fixture()
        saved["lifecycle_state"] = {"through_date": "2036-10-31"}
        order = []
        with patch.object(sv, "canonical_with_save", return_value=canonical), \
                patch.object(sv, "refresh_active_runtime_state", return_value=canonical), \
                patch.object(sv, "simulate_health", return_value={}), \
                patch.object(sv, "merge_health_results"), \
                patch.object(sv, "process_development_months", side_effect=lambda *a: order.append("development") or []), \
                patch.object(sv, "reassess_ai_roles", side_effect=lambda *a, **k: order.append("roles") or []):
            sv.advance_lifecycle_to(canonical, saved, "2036-11-01", 17)
        self.assertEqual(order, ["development", "roles"])

    def test_daily_and_bulk_lifecycle_with_midway_reload_match(self):
        from datetime import date, timedelta
        canonical, daily = self.fixture()
        daily["state"]["current_date"] = "2036-10-28"
        daily["lifecycle_state"] = {"through_date": "2036-10-28"}
        bulk = deepcopy(daily)
        with patch.object(sv, "simulate_health", return_value={}), patch.object(sv, "merge_health_results"):
            for offset in range(1, 8):
                target = (date(2036, 10, 28) + timedelta(days=offset)).isoformat()
                sv.advance_lifecycle_to(canonical, daily, target, 17)
                if offset == 3:
                    daily = json.loads(json.dumps(daily))
            sv.advance_lifecycle_to(canonical, bulk, "2036-11-04", 17)
        self.assertEqual(daily, bulk)


if __name__ == "__main__":
    unittest.main()
