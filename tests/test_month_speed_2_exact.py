"""Exactness checks for the second month-speed pass (docs/agents/tasks/month-speed-2.md)."""
from __future__ import annotations

import random
import unittest

from nba_gm_data import sim
from nba_gm_data import spatial
from nba_gm_data import talent
from nba_gm_data import save as sv

POSITIONS = ["PG", "SG", "SF", "PF", "C", "G-F", "F-C", None]
TRAITS = ["shooting_range", "rim_pressure", "passing_reads", "handle_pressure", "defensive_effort", "rim_deterrence",
          "offensive_rebounding", "scheme_iq", "foot_speed_lateral_agility", "shot_versatility", "release_speed",
          "portability", "screen_navigation", "stamina_cardio", "playoff_translation"]


def _league(rng, size=6):
    players = [{"id": f"p{i:02d}", "team_id": "t1", "name": f"Player {i}", "position": rng.choice(POSITIONS),
                "height_inches": rng.choice([72, 76, 78, 80, 84]), "weight_lbs": 220, "age": 25,
                "minutes_projection": rng.choice([0, 12, 24, 33]), "_save_stats": {"games": 3, "minutes": 70.0,
                                                                                  "fga": 21, "fg3a": 8}}
               for i in range(size)]
    traits = [{"player_id": p["id"], "trait_key": key, "value": float(rng.randint(30, 90))} for p in players for key in TRAITS]
    return {"meta": {"current_date": "2027-01-30"}, "teams": [{"id": "t1", "abbrev": "ONE"}],
            "players": players, "traits": traits, "contracts": [], "_allow_internal_caches": True}


def _fresh(league, player, include_spatial):
    league = dict(league)
    return sim._compute_player_feature_vector(league, sim.canonical_sim_cache(league), player, include_spatial)


class FeatureMemoTests(unittest.TestCase):
    def setUp(self):
        sim._FEATURE_MEMO.clear()

    def test_hits_across_league_views_equal_fresh_vectors(self):
        rng = random.Random(3)
        base = _league(rng)
        for include_spatial in (False, True):
            for player in base["players"]:
                first = sim.player_feature_vector(base, player, include_spatial=include_spatial)
                again = dict(base, players=[dict(p) for p in base["players"]])   # a rebuilt league view
                twin = next(p for p in again["players"] if p["id"] == player["id"])
                hit = sim.player_feature_vector(again, twin, include_spatial=include_spatial)
                self.assertIs(hit, first)
                self.assertEqual(hit, _fresh(again, twin, include_spatial))

    def test_every_input_change_is_a_miss(self):
        rng = random.Random(9)
        base = _league(rng)
        player = base["players"][0]
        reference = sim.player_feature_vector(base, player, include_spatial=True)
        variants = []
        moved = [dict(player, minutes_projection=37.5)] + base["players"][1:]
        variants.append(dict(base, players=moved))
        traits = [dict(t, value=t["value"] + 6) if t["player_id"] == player["id"] else t for t in base["traits"]]
        variants.append(dict(base, traits=traits))
        variants.append(dict(base, meta={**base["meta"], "talent_model_version": talent.MODEL_VERSION}))
        variants.append(dict(base, meta={**base["meta"], "offense_model_version": 1}))
        stats = [dict(player, _save_stats={"games": 9, "minutes": 260.0, "fga": 70, "fg3a": 40})] + base["players"][1:]
        variants.append(dict(base, players=stats))
        for league in variants:
            league = dict(league)
            who = league["players"][0]
            vector = sim.player_feature_vector(league, who, include_spatial=True)
            self.assertEqual(vector, _fresh(league, who, True))
            self.assertIsNot(vector, reference)

    def test_season_box_totals_do_not_split_the_strength_only_vectors(self):
        rng = random.Random(11)
        base = _league(rng)
        player = base["players"][1]
        first = sim.player_feature_vector(base, player, include_spatial=False)
        played = [base["players"][0], dict(player, _save_stats={"games": 4, "minutes": 99.0, "fga": 30, "fg3a": 11})]
        league = dict(base, players=played + base["players"][2:])
        self.assertIs(sim.player_feature_vector(league, league["players"][1], include_spatial=False), first)


class SpatialSignatureMemoTests(unittest.TestCase):
    def _signature(self, league, player):
        """The profile's cache key computed the long way (memo cleared first)."""
        spatial._SIGNATURE_BY_INPUTS.clear()
        profile = spatial.player_spatial_profile(dict(league), player)
        return profile["input_signature"]

    def test_hits_return_the_profile_the_signature_path_returns(self):
        rng = random.Random(4)
        for meta in ({}, {"offense_model_version": 1}):
            base = _league(rng)
            base["meta"].update(meta)
            for player in base["players"]:
                first = spatial.player_spatial_profile(base, player)
                again = dict(base, players=[dict(p) for p in base["players"]])
                twin = next(p for p in again["players"] if p["id"] == player["id"])
                self.assertIs(spatial.player_spatial_profile(again, twin), first)
                self.assertEqual(first["input_signature"], self._signature(again, twin))

    def test_input_changes_change_the_profile(self):
        rng = random.Random(8)
        base = _league(rng)
        base["meta"]["offense_model_version"] = 1
        player = base["players"][0]
        reference = spatial.player_spatial_profile(base, player)
        changed = [
            dict(base, players=[dict(player, _save_stats={"games": 9, "minutes": 300.0, "fga": 80, "fg3a": 30})] + base["players"][1:]),
            dict(base, traits=[dict(t, value=t["value"] + 5) if t["player_id"] == player["id"] else t for t in base["traits"]]),
            dict(base, players=[dict(player, height_inches=88)] + base["players"][1:]),
        ]
        for league in changed:
            who = league["players"][0]
            profile = spatial.player_spatial_profile(dict(league), who)
            self.assertNotEqual(profile["input_signature"], reference["input_signature"])
            self.assertEqual(profile["input_signature"], self._signature(league, who))


class ZoneGridTests(unittest.TestCase):
    def test_zone_grids_and_matchup_match_the_full_profile(self):
        rng = random.Random(21)
        for _ in range(40):
            features = {}
            for key in spatial.ZONE_KEYS:
                for metric in ("frequency", "efficiency", "gravity", "intensity"):
                    if rng.random() < .8:
                        features[f"sp_off_{key}_{metric}"] = rng.uniform(0, 99) if metric != "frequency" else rng.random()
                for metric in ("frequency_influence", "contest", "suppression", "intensity"):
                    if rng.random() < .8:
                        features[f"sp_def_{key}_{metric}"] = rng.uniform(0, 99)
            full = spatial.spatial_profile_from_features(features, "offense")
            zones = spatial.spatial_zones_from_features(features)
            self.assertEqual(zones["offense"], full["offense"])
            self.assertEqual(zones["defense"], full["defense"])
            other = dict(features, **{k: v + 1 for k, v in features.items() if k.startswith("sp_def")})
            self.assertEqual(
                spatial.spatial_matchup_adjustment(zones, spatial.spatial_zones_from_features(other)),
                spatial.spatial_matchup_adjustment(full, spatial.spatial_profile_from_features(other, "defense")))


class GameLogIdTests(unittest.TestCase):
    def test_shared_log_ids_match_a_fresh_scan(self):
        game = {"externalGameId": "g1", "gameDate": "2026-11-02"}
        lines = [{"player_id": "a", "team_id": "t1", "points": 10}, {"player_id": "b", "team_id": "t1", "points": 4},
                 {"player_id": "a", "team_id": "t1", "points": 10}]
        fresh, shared = {"player_game_logs": [{"id": "old"}]}, {"player_game_logs": [{"id": "old"}]}
        ids = {item.get("id") for item in shared["player_game_logs"]}
        for line in lines:
            sv.update_player_stats(fresh, line, game, set())
            sv.update_player_stats(shared, line, game, set(), log_ids=ids)
        self.assertEqual(fresh, shared)
        self.assertEqual(ids, {item["id"] for item in shared["player_game_logs"]})


if __name__ == "__main__":
    unittest.main()
