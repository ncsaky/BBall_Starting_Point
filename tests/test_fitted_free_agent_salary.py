import unittest
from unittest.mock import patch

from nba_gm_data import contract_ai, play
from nba_gm_data.app_actions import free_agent_offer_floors
from nba_gm_data.cap_rules import max_salary


class FittedFreeAgentSalaryTests(unittest.TestCase):
    def setUp(self):
        self.player = {"id": "bench", "age": 26, "draft_year": 2022, "minutes_projection": 12}
        self.valuation = {"player_id": "bench", "on_court_value": 50, "player_value": 47}
        self.active = {"player_asset_valuations": [self.valuation]}
        self.season = "2028-29"
        self.save = {
            "meta": {"season": "2027-28"},
            # FA-REAL slice 2: the contract season follows the date (one switch date), not the phase name.
            "state": {"phase": "free_agency", "current_date": "2028-07-02"},
            "free_agent_player_ids": ["bench"],
            "free_agency_state": {"season": "2027-28", "status": "active", "day": 5},
        }
        self.team = {"id": "team_test", "abbrev": "TST"}
        features = self.enterContext(patch("nba_gm_data.sim.player_feature_vector"))
        features.return_value.features = {}

    def price(self, player=None):
        return contract_ai.fitted_free_agent_ask_millions(self.active, player or self.player, self.season)

    def test_price_rises_with_on_court_value_and_is_flat_across_bench_minutes(self):
        low = self.price()
        self.valuation["on_court_value"] = 53
        self.assertGreater(self.price(), low)
        self.assertEqual(self.price(), self.price({**self.player, "minutes_projection": 5}))

    def test_legal_floor_is_scaled_by_service_and_cap(self):
        with patch.object(contract_ai, "_free_agent_salary_fit", return_value=(-20.0,) + (0.0,) * 7):
            rookie = self.price({**self.player, "draft_year": 2028})
            veteran = self.price({**self.player, "draft_year": 2018})
        self.assertEqual((rookie, veteran), (1.5, 4.2))

    def test_upper_bound_rounds_down_to_legal_bid_increment(self):
        bounds = contract_ai.free_agent_salary_bounds_millions(self.season, 6)
        expected_maximum = max_salary(self.season, 6) / 1_000_000
        self.assertLessEqual(bounds[1], expected_maximum)
        self.assertLess(expected_maximum - bounds[1], 0.1)
        # Force a fitted value above each of the three experience-based maxima.
        coefficients = (0.0,) * 8
        for service in (6, 7, 10):
            with self.subTest(service=service):
                price = contract_ai.free_agent_salary_fit_millions(
                    coefficients, 50, 26, service, "rotation", self.season,
                )
                self.assertEqual(price, contract_ai.free_agent_salary_bounds_millions(self.season, service)[1])

    def test_research_and_star_paths_keep_their_prices(self):
        research = {"projected_aav_millions": 4.6}
        self.assertIs(play.with_star_market_ask(self.active, self.save, self.player, research), research)
        starter = {**self.player, "minutes_projection": 25}
        self.assertIsNone(self.price(starter))
        self.assertEqual(play.seed_free_agency_ask(self.active, self.save, starter, {}), 12.0)
        with patch("nba_gm_data.contract_ai.star_market_ask_millions", return_value=36.5):
            self.assertEqual(play.seed_free_agency_ask(self.active, self.save, starter, {}), 36.5)
        self.assertIsNone(play.free_agency_fitted_bounds(self.save, starter["id"]))

    def test_user_display_and_offer_decision_share_the_stored_price(self):
        ask = play.seed_free_agency_ask(self.active, self.save, self.player, {})
        self.assertEqual(ask, self.price())
        self.assertNotEqual(ask, play.free_agency_initial_ask(self.player, {}))
        with patch.object(play, "free_agency_offer_context_score", return_value={"context_raw": 50.0}):
            floors = free_agent_offer_floors(self.active, self.save, self.player, self.team, 2)
            floor = floors["default"]["guaranteed"]
            with patch.object(play, "load_save", return_value=self.save), patch.object(play, "write_save"):
                self.active["teams"] = [self.team]
                below = play.manual_save_pool_signing(self.active, None, self.player, "TST", 2, round(floor - 0.1, 1), 17)
                at = play.manual_save_pool_signing(self.active, None, self.player, "TST", 2, floor, 17)
                above = play.manual_save_pool_signing(self.active, None, self.player, "TST", 2, 100, 17)
        self.assertEqual(ask, floors["rule"]["ask_millions"])
        self.assertEqual(ask, at["decision"]["market_ask_millions"])
        self.assertEqual(floor, at["decision"]["ask_threshold_millions"])
        self.assertFalse(below["accepted"])
        self.assertTrue(at["accepted"])
        self.assertEqual(above["decision"]["decision"], "outside_salary_bounds")

    def test_weekly_discount_stops_at_the_fitted_minimum(self):
        self.valuation["on_court_value"] = 5
        initial = play.seed_free_agency_ask(self.active, self.save, self.player, {})
        self.assertEqual(play.adjust_free_agent_asks_state(self.save)["ask_adjusted_count"], 0)
        self.assertEqual(self.save["free_agency_state"]["player_asks_millions"]["bench"], initial)


if __name__ == "__main__":
    unittest.main()
