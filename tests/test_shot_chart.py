import math
import unittest
from unittest.mock import patch

from nba_gm_data.shot_chart import chart_model, combine_team_charts, court_grid, project_player_chart, region_at
from nba_gm_data.spatial import neutral_spatial_profile, player_spatial_profile, team_spatial_profile
from test_spatial import canonical_fixture


class ShotChartTests(unittest.TestCase):
    def test_region_boundaries_and_corner_geometry(self):
        points = [(0, 0, 1), (-7, 10, 2), (0, 12, 3), (7, 10, 4),
                  (-18, 2, 5), (-12, 17, 6), (0, 20, 7), (12, 17, 8), (18, 2, 9),
                  (-23, 1, 10), (-15, 25, 11), (0, 26, 12), (15, 25, 13), (23, 1, 14), (0, 50, 15)]
        for lateral, forward, expected in points:
            self.assertEqual(region_at(lateral, forward), expected)
        self.assertEqual(region_at(0, 41.74), 12)
        self.assertEqual(region_at(0, 41.75), 15)

    def test_reference_is_complete_and_uses_public_league_totals(self):
        model = chart_model()
        self.assertEqual(len(model["profiles"]), 32)
        self.assertEqual(set(model["league_zones"]), {str(i) for i in range(1, 16)})
        self.assertAlmostEqual(sum(row["frequency"] for row in model["league_zones"].values()), 1, places=5)
        self.assertGreater(sum(model["pca"]["explained_variance"]), 0.90)
        self.assertLess(model["validation"]["ratings_neighbors_mean_error"], model["validation"]["sample_mean_error"])
        for row in model["profiles"]:
            self.assertEqual(len(row["density"]), len(court_grid()))
            self.assertTrue(all(math.isfinite(value) and value >= 0 for value in row["density"]))
            self.assertAlmostEqual(sum(row["shares"]), 1, places=3)

    def test_chart_is_deterministic_normalized_and_has_15_regions(self):
        canonical = canonical_fixture()
        profile = player_spatial_profile(canonical, "shooter", include_chart=True)
        chart = profile["shot_chart"]
        self.assertEqual(len(chart["regions"]), 15)
        self.assertEqual(len(chart["cells"]), len(court_grid()))
        self.assertAlmostEqual(sum(region["frequency"] for region in chart["regions"]), 1, places=3)
        self.assertAlmostEqual(sum(cell[4] for cell in chart["cells"]), 1, places=4)
        self.assertEqual(profile, player_spatial_profile(canonical, "shooter"))
        self.assertTrue(all(0 <= region["fg_pct"] <= 100 for region in chart["regions"]))

    def test_real_player_anchors_observed_preference(self):
        model = chart_model()
        curry = next(row for row in model["profiles"] if row["name"] == "Stephen Curry")
        traits = dict(zip(model["feature_keys"], curry["ratings"]))
        profile = neutral_spatial_profile("curry")
        for key, grade in curry["grades"].items():
            profile["offense"][key]["efficiency"] = grade
        result = project_player_chart({"name": "Stephen Curry", "height_inches": curry["ratings"][-1]}, traits, profile)
        self.assertGreater(sum(row["weight"] for row in result["comparables"] if row["name"] == "Stephen Curry"), 0.88)
        self.assertLess(abs(result["regions"][11]["frequency"] - curry["shares"][11]), 0.02)

    def test_generated_archetypes_differ_and_change_with_ratings(self):
        canonical = canonical_fixture()
        shooter = player_spatial_profile(canonical, "shooter", include_chart=True)["shot_chart"]
        protector = player_spatial_profile(canonical, "protector", include_chart=True)["shot_chart"]
        three_share = lambda chart: sum(region["frequency"] for region in chart["regions"] if 10 <= region["id"] <= 14)
        self.assertGreater(three_share(shooter), three_share(protector) + 0.20)
        canonical["traits"] = [{**row, "value": 30} if row["player_id"] == "shooter" and row["trait_key"] == "shooting_range" else row for row in canonical["traits"]]
        revised = player_spatial_profile(canonical, "shooter", include_chart=True)["shot_chart"]
        self.assertNotEqual(shooter["cells"], revised["cells"])

    def test_chart_layer_does_not_change_gameplay_grades(self):
        canonical = canonical_fixture()
        player = dict(canonical["players"][0])
        before = player_spatial_profile(canonical, {**player, "id": "uncached-id"})
        offense = {key: dict(value) for key, value in before["offense"].items()}
        with patch("nba_gm_data.spatial.project_player_chart", return_value={}) as projection:
            player_spatial_profile(canonical, {**player, "id": "uncached-id"})
            projection.assert_not_called()
            after = player_spatial_profile(canonical, {**player, "id": "uncached-id"}, include_chart=True)
            projection.assert_called_once()
        self.assertEqual(before["offense"], offense)
        self.assertEqual(after["offense"], offense)

    def test_team_chart_excludes_injured_and_zero_minutes_players(self):
        canonical = canonical_fixture()
        minutes = {"shooter": 34, "slasher": 32, "protector": 30, "reserve": 0}
        full = team_spatial_profile(canonical, "A", minutes, include_chart=True)
        injured = team_spatial_profile(canonical, "A", minutes, {"shooter": {"availability_status": "out"}}, include_chart=True)
        self.assertNotEqual(full["shot_chart"]["cells"], injured["shot_chart"]["cells"])
        for index, region in enumerate(injured["shot_chart"]["regions"]):
            expected = sum(player_spatial_profile(canonical, name)["shot_chart"]["regions"][index]["frequency"] * weight for name, weight in [("slasher", 32 / 62), ("protector", 30 / 62)])
            self.assertAlmostEqual(region["frequency"], expected, places=5)

    def test_missing_reference_is_explicit_and_safe(self):
        profile = neutral_spatial_profile()
        with patch("nba_gm_data.shot_chart.chart_model", return_value={}):
            result = project_player_chart({}, {}, profile)
        self.assertEqual(result["basis"], "unavailable")
        self.assertTrue(all(region["delta_pp"] == 0 and region["fg_pct"] is None for region in result["regions"]))
        result = combine_team_charts([(profile, 1)])
        self.assertEqual(len(result["regions"]), 15)


if __name__ == "__main__":
    unittest.main()
