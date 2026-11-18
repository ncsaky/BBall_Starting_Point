import unittest

from nba_gm_data.input_estimator import DEFINITIONS, InputEstimator
from scripts.build_player_inputs import estimate_startup_inputs


class StartupRookieTechniqueTests(unittest.TestCase):
    def test_only_drafted_2026_players_without_a_completed_season_get_rookie_technique(self):
        rookie = {
            "id": "rookie",
            "name": "Rookie",
            "espn_player_id": "rookie",
            "position": "SG",
            "draft_year": 2026,
            "draft_status": "drafted",
        }
        played = dict(rookie, id="played", name="Played", espn_player_id="played")
        earlier_pick = dict(rookie, id="earlier", name="Earlier", draft_year=2025)
        undrafted = dict(rookie, id="undrafted", name="Undrafted", draft_status="undrafted")
        universe = {"players": [rookie, played, earlier_pick, undrafted]}
        estimator = InputEstimator(career_players={
            "rookie": {"seasons": [{"season": "2026-27", "games": 4}]},
            "played": {"seasons": [{"season": "2025-26", "games": 4}]},
        })

        regular = estimator.estimate_universe(universe)["players"]
        actual = estimate_startup_inputs(estimator, universe)["players"]
        prospect = estimator.estimate_player_inputs(rookie, prospect=True).to_dict()["inputs"]

        for player in (played, earlier_pick, undrafted):
            self.assertEqual(actual[player["id"]], regular[player["id"]])
        for iid, definition in DEFINITIONS.items():
            with self.subTest(input_id=iid):
                expected = prospect if definition["kind"] == "grade" else regular["rookie"]["inputs"]
                self.assertEqual(actual["rookie"]["inputs"][iid], expected[iid])
        self.assertNotEqual(actual["rookie"]["inputs"]["S01"], regular["rookie"]["inputs"]["S01"])
