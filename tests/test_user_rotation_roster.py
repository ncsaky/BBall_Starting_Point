from copy import deepcopy
import unittest

from nba_gm_data import save as sv


class UserRotationRosterTests(unittest.TestCase):
    def fixture(self):
        players = [{"id": f"home{i}", "name": f"Home {i}", "team_id": "home", "minutes_projection": 24}
                   for i in range(10)]
        players += [{"id": f"incoming{i}", "name": f"Incoming {i}", "team_id": "other", "minutes_projection": 32}
                    for i in range(3)]
        canonical = {"teams": [{"id": "home", "abbrev": "HOM"}, {"id": "other", "abbrev": "OTH"}], "players": players}
        desired = {**{f"home{i}": 24 for i in range(6)}, "home6": 0,
                   **{f"incoming{i}": 32 for i in range(3)}}
        saved = {"meta": {"user_team_id": "home"}, "rotation_overrides": {"home": desired},
                 "roster_overrides": {**{f"incoming{i}": "home" for i in range(3)},
                                      **{f"home{i}": "other" for i in range(7, 10)}},
                 "rotation_locked_player_ids": {"home": list(desired)},
                 "health_states": [{"player_id": "home6", "availability_status": "out"}]}
        return canonical, saved

    def test_zero_minute_injury_does_not_erase_traded_players_or_restore_departed_players(self):
        canonical, saved = self.fixture()
        before = deepcopy(canonical)
        expected = deepcopy(saved["rotation_overrides"])
        sv.normalize_user_rotation_for_injuries(saved, canonical)
        self.assertEqual(saved["rotation_overrides"], expected)
        self.assertEqual(canonical, before)
        self.assertTrue(all(f"incoming{i}" in saved["rotation_locked_player_ids"]["home"] for i in range(3)))
        self.assertIn("home6", saved["rotation_locked_player_ids"]["home"])

    def test_departed_players_injury_cannot_change_the_current_rotation(self):
        canonical, saved = self.fixture()
        saved["health_states"] = [{"player_id": "home9", "availability_status": "out"}]
        before = deepcopy(saved)
        sv.normalize_user_rotation_for_injuries(saved, canonical)
        self.assertEqual(saved, before)

    def test_real_injury_redistributes_only_across_the_current_roster(self):
        canonical, saved = self.fixture()
        saved["health_states"].append({"player_id": "home0", "availability_status": "out"})
        requested = deepcopy(saved["rotation_overrides"])
        sv.normalize_user_rotation_for_injuries(saved, canonical)
        self.assertEqual(saved["rotation_overrides"], requested)
        active = {**canonical, "players": sv.active_players_for_roster_checks(canonical, saved)}
        minutes = sv.team_rotation_projection(active, saved, "home")
        self.assertEqual(sum(minutes.values()), 240)
        self.assertEqual(minutes["home0"], 0)
        self.assertEqual(minutes["home6"], 0)
        self.assertTrue(all(minutes[f"incoming{i}"] >= 32 for i in range(3)))
        self.assertTrue(all(f"home{i}" not in minutes for i in range(7, 10)))
        self.assertTrue(all(0 <= value <= 48 for value in minutes.values()))
        saved["health_states"] = []
        sv.normalize_user_rotation_for_injuries(saved, canonical)
        self.assertEqual(saved["rotation_overrides"], requested)
        self.assertEqual(sv.team_rotation_projection(active, saved, "home"), requested["home"])

    def test_generated_roster_members_survive_and_retired_members_do_not_return(self):
        canonical, saved = self.fixture()
        saved["generated_players"] = [{"id": "rookie", "name": "Rookie", "team_id": "home", "minutes_projection": 24}]
        saved["retired_player_ids"] = ["home0"]
        saved["rotation_overrides"]["home"].pop("home0")
        saved["rotation_overrides"]["home"]["rookie"] = 24
        expected = deepcopy(saved["rotation_overrides"])
        sv.normalize_user_rotation_for_injuries(saved, canonical)
        self.assertEqual(saved["rotation_overrides"], expected)

    def test_prepared_active_and_baseline_inputs_produce_the_same_idempotent_result(self):
        canonical, first = self.fixture()
        second = deepcopy(first)
        active = {**canonical, "players": sv.active_players_for_roster_checks(canonical, first)}
        sv.normalize_user_rotation_for_injuries(first, canonical)
        sv.normalize_user_rotation_for_injuries(second, active)
        self.assertEqual(first, second)
        prior = deepcopy(first)
        sv.normalize_user_rotation_for_injuries(first, canonical)
        self.assertEqual(first, prior)

    def test_absent_manual_rotations_remain_absent(self):
        canonical, saved = self.fixture()
        saved["rotation_overrides"] = {}
        before = deepcopy(saved)
        sv.normalize_user_rotation_for_injuries(saved, canonical)
        self.assertEqual(saved, before)


if __name__ == "__main__":
    unittest.main()
