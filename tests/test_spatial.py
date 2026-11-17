import unittest

from nba_gm_data.spatial import (
    ZONE_KEYS,
    player_spatial_profile,
    prospect_spatial_profile,
    spatial_fit_delta,
    spatial_matchup_adjustment,
    team_spatial_profile,
    with_spatial_fit_context,
)


def canonical_fixture():
    players = [
        {"id": "shooter", "name": "Elite Shooter", "team_id": "A", "position": "PG", "height_inches": 75, "minutes_projection": 34},
        {"id": "slasher", "name": "Rim Slasher", "team_id": "A", "position": "SF", "height_inches": 79, "minutes_projection": 32},
        {"id": "protector", "name": "Rim Protector", "team_id": "A", "position": "C", "height_inches": 85, "minutes_projection": 30},
        {"id": "reserve", "name": "Reserve", "team_id": "A", "position": "SG", "height_inches": 77, "minutes_projection": 0},
        {"id": "candidate", "name": "Candidate Spacer", "team_id": None, "position": "SG", "height_inches": 76, "minutes_projection": 28},
    ]
    defaults = {
        "shooting_range": 50,
        "shot_versatility": 50,
        "release_speed": 50,
        "rim_pressure": 50,
        "handle_pressure": 50,
        "passing_reads": 50,
        "defensive_effort": 50,
        "scheme_iq": 50,
        "rim_deterrence": 50,
        "screen_navigation": 50,
        "foot_speed_lateral_agility": 50,
        "offensive_rebounding": 50,
        "portability": 50,
    }
    overrides = {
        "shooter": {"shooting_range": 96, "shot_versatility": 90, "release_speed": 95, "portability": 91, "rim_pressure": 38},
        "slasher": {"shooting_range": 28, "shot_versatility": 63, "rim_pressure": 96, "handle_pressure": 79},
        "protector": {"shooting_range": 20, "rim_pressure": 72, "rim_deterrence": 98, "scheme_iq": 88, "defensive_effort": 91},
        "reserve": {"shooting_range": 99, "shot_versatility": 99, "release_speed": 99},
        "candidate": {"shooting_range": 93, "shot_versatility": 87, "release_speed": 92, "portability": 90},
    }
    traits = []
    for player in players:
        values = {**defaults, **overrides.get(player["id"], {})}
        traits.extend({"player_id": player["id"], "trait_key": key, "value": value} for key, value in values.items())
    return {"players": players, "traits": traits}


def group_frequency(profile, groups):
    zone_groups = {row["key"]: row["group"] for row in profile["zones"]}
    return sum(profile["offense"][key]["frequency"] for key in ZONE_KEYS if zone_groups[key] in groups)


class SpatialProfileTests(unittest.TestCase):
    def setUp(self):
        self.canonical = canonical_fixture()

    def test_player_profiles_are_deterministic_and_normalized(self):
        first = player_spatial_profile(self.canonical, "shooter")
        second = player_spatial_profile(self.canonical, "shooter")
        self.assertEqual(first, second)
        self.assertAlmostEqual(sum(row["frequency"] for row in first["offense"].values()), 1.0, places=4)
        self.assertEqual(set(first["offense"]), set(ZONE_KEYS))
        self.assertEqual(set(first["defense"]), set(ZONE_KEYS))
        self.assertGreater(first["creation_volume"], 0)
        self.assertGreater(first["defensive_activity"], 0)
        self.assertGreater(len(first["visual_pockets"]["offense"]), len(ZONE_KEYS))
        self.assertGreater(len(first["visual_pockets"]["defense"]), 0)
        self.assertGreater(len({round(row["x"], 1) for row in first["visual_pockets"]["offense"]}), 8)
        self.assertGreater(len({round(row["y"], 1) for row in first["visual_pockets"]["offense"]}), 12)
        self.assertTrue(all(0 <= row["x"] <= 67 for row in first["visual_pockets"]["offense"]))

    def test_above_break_visual_pockets_follow_the_three_point_arc(self):
        profile = player_spatial_profile(self.canonical, "shooter")
        arc = [
            row for row in profile["visual_pockets"]["offense"]
            if row["zone_key"].startswith("above_break")
        ]
        self.assertGreater(len(arc), 4)
        self.assertTrue(all(45 <= row["x"] <= 66.5 for row in arc))
        center = [row["x"] for row in arc if 40 <= row["y"] <= 60]
        wings = [row["x"] for row in arc if row["y"] < 35 or row["y"] > 65]
        self.assertGreater(max(center), min(wings))

    def test_profile_cache_invalidates_when_trait_inputs_change(self):
        first = player_spatial_profile(self.canonical, "shooter")
        self.canonical["traits"] = [
            {**row, "value": 25 if row["player_id"] == "shooter" and row["trait_key"] == "shooting_range" else row["value"]}
            for row in self.canonical["traits"]
        ]
        second = player_spatial_profile(self.canonical, "shooter")
        self.assertNotEqual(first["input_signature"], second["input_signature"])
        self.assertLess(second["offense"]["above_break_center"]["gravity"], first["offense"]["above_break_center"]["gravity"])

    def test_archetypes_create_distinct_court_shapes(self):
        shooter = player_spatial_profile(self.canonical, "shooter")
        slasher = player_spatial_profile(self.canonical, "slasher")
        protector = player_spatial_profile(self.canonical, "protector")
        shooter_perimeter = group_frequency(shooter, {"corner_three", "above_break_three"})
        slasher_perimeter = group_frequency(slasher, {"corner_three", "above_break_three"})
        self.assertGreater(shooter_perimeter, slasher_perimeter + 0.12)
        self.assertGreater(slasher["offense"]["restricted_area"]["intensity"], shooter["offense"]["restricted_area"]["intensity"])
        self.assertGreater(protector["defense"]["restricted_area"]["suppression"], shooter["defense"]["restricted_area"]["suppression"] + 15)
        self.assertGreater(protector["defensive_activity"], shooter["defensive_activity"])

    def test_team_profile_respects_minutes_and_health(self):
        full = team_spatial_profile(
            self.canonical,
            "A",
            {"shooter": 34, "slasher": 32, "protector": 30, "reserve": 0},
        )
        reserve_profile = player_spatial_profile(self.canonical, "reserve")
        self.assertNotAlmostEqual(
            full["offense"]["above_break_center"]["gravity"],
            reserve_profile["offense"]["above_break_center"]["gravity"],
            places=2,
        )
        without_shooter = team_spatial_profile(
            self.canonical,
            "A",
            {"shooter": 34, "slasher": 32, "protector": 30, "reserve": 0},
            {"shooter": {"availability_status": "out"}},
        )
        self.assertLess(
            without_shooter["offense"]["above_break_center"]["gravity"],
            full["offense"]["above_break_center"]["gravity"],
        )
        source_ids = {row["source_player_id"] for row in full["visual_pockets"]["offense"]}
        self.assertIn("shooter", source_ids)
        self.assertIn("slasher", source_ids)
        self.assertIn("protector", source_ids)
        self.assertNotIn("reserve", source_ids)
        self.assertNotIn("shooter", {
            row["source_player_id"] for row in without_shooter["visual_pockets"]["offense"]
        })

    def test_matchup_and_fit_effects_are_bounded(self):
        offense = team_spatial_profile(self.canonical, "A")
        weak_defense = player_spatial_profile(self.canonical, "shooter")
        adjustment = spatial_matchup_adjustment(offense, weak_defense)
        self.assertLessEqual(abs(adjustment["shot_quality_delta"]), 1.5)
        self.assertTrue(all(abs(value) <= 0.04 for value in adjustment["category_delta"].values()))
        candidate = next(row for row in self.canonical["players"] if row["id"] == "candidate")
        self.assertLessEqual(abs(spatial_fit_delta(self.canonical, "A", candidate, cap=3.0)), 3.0)

    def test_batch_fit_profiles_match_and_refresh_after_roster_changes(self):
        self.canonical["teams"] = [{"id": "A"}]
        candidate = next(row for row in self.canonical["players"] if row["id"] == "candidate")
        batch = with_spatial_fit_context(self.canonical)
        self.assertNotIn("_spatial_fit_team_profiles", self.canonical)
        self.assertEqual(spatial_fit_delta(batch, "A", candidate), spatial_fit_delta(self.canonical, "A", candidate))
        before = batch["_spatial_fit_team_profiles"]["A"]
        self.canonical["players"] = [row for row in self.canonical["players"] if row["id"] != "shooter"]
        refreshed = with_spatial_fit_context(self.canonical)
        self.assertNotEqual(before, refreshed["_spatial_fit_team_profiles"]["A"])
        self.assertEqual(spatial_fit_delta(refreshed, "A", candidate), spatial_fit_delta(self.canonical, "A", candidate))

    def test_fictional_prospect_profile_is_deterministic(self):
        prospect = {"id": "prospect-1", "name": "Created Prospect", "position": "C", "current_ability": 62, "archetype": "rim_protecting_big", "height_inches": 84}
        first = prospect_spatial_profile(self.canonical, prospect)
        second = prospect_spatial_profile(self.canonical, prospect)
        self.assertEqual(first, second)
        self.assertGreater(first["defense"]["restricted_area"]["suppression"], 65)


if __name__ == "__main__":
    unittest.main()
