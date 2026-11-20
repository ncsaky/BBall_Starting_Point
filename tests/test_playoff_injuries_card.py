"""Playoff Injuries card payload: who is listed (teams still alive, out or easing back), and that every field comes
from the engine's own health state."""
import unittest
from pathlib import Path
from unittest import mock

from nba_gm_data import app_actions as aa


TEAMS = [{"id": t, "abbrev": t.upper()} for t in ("t1", "t2", "t3", "t4", "t5")]
PLAYERS = [
    {"id": "out_star", "name": "Out Star", "team_id": "t1", "position": "Guard", "headshot_url": "h.png"},
    {"id": "rusty", "name": "Rusty Back", "team_id": "t2", "position": "Center"},
    {"id": "healthy", "name": "Healthy Guy", "team_id": "t1", "position": "Forward"},
    {"id": "eliminated", "name": "Gone Home", "team_id": "t3", "position": "Guard"},
    {"id": "lottery", "name": "Not In It", "team_id": "t5", "position": "Guard"},
]
STATE = {
    "round": "conference_semifinals",
    "series": [
        {"team_ids": ["t1", "t3"], "winner_team_id": "t1"},
        {"team_ids": ["t2", "t4"], "winner_team_id": None},
    ],
    "play_in": {},
}
SAVE = {
    "meta": {"user_team_id": "t2"},
    "state": {"current_date": "2027-05-01"},
    "playoff_state": STATE,
    "health_states": [
        {"player_id": "out_star", "availability_status": "out", "injury_severity": "moderate",
         "current_injury_label": "ankle sprain", "return_date": "2027-05-08", "games_missed": 2},
        {"player_id": "rusty", "availability_status": "active", "rust": 4.0, "games_missed": 6},
        {"player_id": "healthy", "availability_status": "active"},
        {"player_id": "eliminated", "availability_status": "out", "return_date": "2027-05-20"},
        {"player_id": "lottery", "availability_status": "out", "return_date": "2027-05-20"},
    ],
}
RATINGS = {"out_star": {"overall": 74.2, "offense": 77.0, "defense": 60.1}, "rusty": {"overall": 61.0, "offense": 55.0, "defense": 70.0}}


def payload():
    context = {"save": SAVE, "active": {"players": PLAYERS, "teams": TEAMS}}
    with mock.patch.object(aa, "dashboard_read_context", return_value=context), \
            mock.patch.object(aa, "player_display_attribute_summary", side_effect=lambda active, pid: RATINGS.get(pid, {})):
        return aa.playoff_injuries_payload({}, Path("unused.json"))


class PlayoffInjuriesCardTests(unittest.TestCase):
    def test_alive_teams_only_and_eliminated_teams_drop_off(self):
        teams, alive = aa.postseason_team_ids(STATE)
        self.assertEqual(teams, {"t1", "t2", "t3", "t4"})
        self.assertEqual(alive, {"t1", "t2", "t4"})
        names = [row["name"] for row in payload()["players"]]
        self.assertEqual(names, ["Out Star", "Rusty Back"], "sorted by OVR; healthy, eliminated and non-playoff players left out")

    def test_out_player_carries_engine_injury_and_return(self):
        row = payload()["players"][0]
        self.assertEqual(row["status"], "out")
        self.assertEqual(row["injury"], "ankle sprain")
        self.assertEqual(row["return_date"], "2027-05-08")
        self.assertEqual(row["days_left"], 7)
        self.assertEqual(row["games_estimate"], 3)
        self.assertEqual((row["overall"], row["offense"], row["defense"]), (74.2, 77.0, 60.1))
        self.assertEqual(row["team_abbrev"], "T1")
        self.assertFalse(row["user_team"])

    def test_returning_player_shows_rust_from_the_sim(self):
        from nba_gm_data.sim import rust_display
        row = payload()["players"][1]
        expected = rust_display(SAVE["health_states"][1])
        self.assertEqual(row["status"], "returning")
        self.assertEqual(row["rust_penalty"], expected["rust_penalty"])
        self.assertEqual(row["rust_games"], expected["rust_games"])
        self.assertIsNone(row["return_date"])
        self.assertTrue(row["user_team"])

    def test_play_in_losers_are_out_once_the_play_in_is_done(self):
        state = {"series": [], "locked_seeds": {"East": {"1": "a"}},
                 "play_in": {"East": {"status": "completed", "teams": {"7": "b", "8": "c", "9": "d", "10": "e"},
                                      "seed_7_team_id": "b", "seed_8_team_id": "d"}}}
        _teams, alive = aa.postseason_team_ids(state)
        self.assertEqual(alive, {"a", "b", "d"})

    def test_action_is_registered(self):
        status = aa.runtime_status(Path("."), Path("."))
        self.assertIn("playoff_injuries", status["actions"])


if __name__ == "__main__":
    unittest.main()
