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
        # The league playmaking baseline's own cache is keyed by object ids, which Python reuses after other tests'
        # leagues are freed; clear it so identity checks here see one baseline per league (see the report's notes).
        spatial._PLAYMAKING_MEAN_CACHE.clear()

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
        for league in variants:
            league = dict(league)
            who = league["players"][0]
            vector = sim.player_feature_vector(league, who, include_spatial=True)
            self.assertEqual(vector, _fresh(league, who, True))
            self.assertIsNot(vector, reference)

    def test_season_box_totals_do_not_split_vectors(self):
        rng = random.Random(11)
        for meta in ({}, {"offense_model_version": 1}):
            base = _league(rng)
            base["meta"].update(meta)
            player = base["players"][1]
            for include_spatial in (False, True):
                first = sim.player_feature_vector(base, player, include_spatial=include_spatial)
                played = [base["players"][0], dict(player, _save_stats={"games": 4, "minutes": 99.0, "fga": 30, "fg3a": 11})]
                league = dict(base, players=played + base["players"][2:])
                hit = sim.player_feature_vector(league, league["players"][1], include_spatial=include_spatial)
                self.assertIs(hit, first)
                self.assertEqual(hit, _fresh(league, league["players"][1], include_spatial))


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


class StrengthOnlyFeatureTests(unittest.TestCase):
    def test_strength_features_are_the_same_without_zone_grids(self):
        rng = random.Random(13)
        for meta in ({}, {"offense_model_version": 1}):
            league = _league(rng, 8)
            league["meta"].update(meta)
            for player in league["players"]:
                full = _fresh(league, player, True).features
                strength = _fresh(league, player, False).features
                self.assertEqual({k: v for k, v in full.items() if not k.startswith("sp_")}, strength)


def _reference_future_slot(canonical, team_id, base_slot, distance):
    """future_adjusted_pick_slot as written before MONTH-SPEED-2."""
    from nba_gm_data.transactions import clamp, fallback_asset_valuation, maybe_float
    if distance <= 0:
        return clamp(float(base_slot), 1, 30)
    state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == team_id), {})
    values = {value.get("player_id"): value for value in canonical.get("player_asset_valuations", [])}
    roster = [player for player in canonical.get("players", []) if player.get("team_id") == team_id]
    top = sorted(roster, key=lambda p: float((values.get(p.get("id")) or fallback_asset_valuation(p)).get("player_value") or 0.0),
                 reverse=True)[:5][:3]
    age = sum(maybe_float(p.get("age")) or 27.0 for p in top) / len(top) if top else 27.0
    youth = sum(max(0.0, float((values.get(p.get("id")) or fallback_asset_valuation(p)).get("development_upside") or 0.0))
                for p in roster if (maybe_float(p.get("age")) or 99.0) <= 24.0)
    phase = str(state.get("phase") or "balanced")
    pull = min(0.58, distance * 0.10)
    slot = float(base_slot) * (1.0 - pull) + 15.5 * pull
    move = 0.0
    if base_slot <= 8:
        move += 0.65 + min(0.95, youth / 90.0)
        if phase in {"rebuilding", "developing"}:
            move += 0.35
        if age >= 30.5 and youth < 28:
            move -= 0.35
    elif base_slot >= 23:
        if age >= 31.0:
            move -= 1.15 + min(0.5, (age - 31.0) * 0.18)
        elif age <= 27.0 or phase == "contending_with_future_upside":
            move += 0.28
        else:
            move -= 0.25
    else:
        if age <= 25.5 and youth >= 36:
            move += 0.45
        elif age >= 31.0:
            move -= 0.55
    return clamp(slot + move * distance, 1, 30)


class PickSlotTests(unittest.TestCase):
    def test_pick_slots_match_the_per_pick_reference(self):
        from nba_gm_data import transactions as tx
        rng = random.Random(17)
        teams = [f"t{i}" for i in range(6)]
        players = [{"id": f"p{i}", "team_id": rng.choice(teams), "age": rng.choice([19, 21, 23, 24, 27, 31, 34, None])}
                   for i in range(60)]
        league = {
            "meta": {"active_season": "2026-27"}, "teams": [{"id": t} for t in teams], "players": players,
            "player_asset_valuations": [{"player_id": p["id"], "player_value": rng.uniform(0, 80),
                                         "development_upside": rng.uniform(-5, 30)} for p in players if rng.random() < .9],
            "team_strategic_states": [{"team_id": t, "contention_ceiling": rng.uniform(30, 80),
                                       "phase": rng.choice(["rebuilding", "contending", "contending_with_future_upside", None])}
                                      for t in teams],
            "save_team_records": {t: {"wins": rng.randint(0, 40), "losses": rng.randint(0, 40)} for t in teams[:4]},
            "draft_picks": [{"id": f"k{i}", "original_team_id": rng.choice(teams), "season": rng.choice(["2026-27", "2027-28", "2028-29", "2031-32"])}
                            for i in range(40)],
        }
        import copy
        reference = copy.deepcopy(league)
        original = tx.future_adjusted_pick_slot
        tx.future_adjusted_pick_slot = lambda c, t, b, d, **_: _reference_future_slot(c, t, b, d)
        try:
            tx.annotate_pick_value_context(reference)
        finally:
            tx.future_adjusted_pick_slot = original
        tx.annotate_pick_value_context(league)
        self.assertEqual(league["draft_picks"], reference["draft_picks"])
        self.assertTrue(any(p.get("_future_distance_years", 0) > 0 for p in league["draft_picks"]))
        for team in league["teams"]:
            for base in (3, 15, 27):
                for distance in (0, 1, 2, 4):
                    self.assertEqual(tx.future_adjusted_pick_slot(league, team["id"], base, distance),
                                     _reference_future_slot(league, team["id"], base, distance))


class RotationMemoTests(unittest.TestCase):
    def test_remembered_projections_match_fresh_ones_and_follow_inputs(self):
        rng = random.Random(2)
        league = _league(rng, 12)
        save = {"health_states": [{"player_id": "p01", "availability_status": "out", "return_date": "2027-02-20"}],
                "rotation_baselines": {p["id"]: rng.choice([0, 10, 20, 30]) for p in league["players"]},
                "meta": {"season": "2026-27"}}

        def fresh(lg, sv_):
            fills = {}
            health = {h.get("player_id"): h for h in sv_.get("health_states", [])}
            out = sv._team_rotation_projection(lg, sv_, "t1", False, [p for p in lg["players"] if p["team_id"] == "t1"],
                                               health, fills)
            return out, fills

        variants = [save,
                    {**save, "health_states": []},
                    {**save, "rotation_baselines": {**save["rotation_baselines"], "p03": 5}},
                    {**save, "rotation_recommendations": {"p05": {"target_minutes": 30}}},
                    {**save, "staff_slots": [{"team_id": "t1", "slot": "head_coach", "id": "coach-1", "name": "Coach One"}]}]
        for variant in variants + variants:   # the second round hits the memo
            fills = {}
            projection = sv.team_rotation_projection(league, variant, "t1", fill_out=fills)
            self.assertEqual((projection, fills), fresh(league, variant))
        moved = dict(league, players=[dict(p, age=36) if p["id"] == "p03" else p for p in league["players"]])
        self.assertEqual(sv.team_rotation_projection(moved, save, "t1"), fresh(moved, save)[0])


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
