"""Speed caches for the 94-input ratings give exactly the uncached results.

Covers the per-process caches that make league rebuilds and per-player reads cheap: estimated inputs for players
outside the inputs file (keyed on everything but the daily season stats), the impact model's grouped input
features and the box-score rates (both kept per shared, read-only input record).
"""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from nba_gm_data import box_rates, impact_value
from nba_gm_data import input_estimator
from nba_gm_data import ratings_model as rm

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"
INPUTS = ROOT / rm.INPUTS_FILE
FICTIONAL_ID = "generated_player_cache-test"


def _clear_caches():
    for cache in (rm._GENERATED_CACHE, rm._DERIVED_CACHE, rm._EFFECTIVE_CACHE, rm._ROUTED_CACHE,
                  impact_value._FEATURE_CACHE, box_rates._FLAT_CACHE):
        cache.clear()
    input_estimator._generated_definition_inputs.cache_clear()


def _with_fictional_player(base):
    """The league plus one generated (fictional) player, who has no record in the inputs file."""
    canonical = deepcopy(base)
    template = next(p for p in canonical["players"] if p["name"] == "Stephen Curry")
    player = {**deepcopy(template), "id": FICTIONAL_ID, "name": "Cache Test", "league": "generated",
              "source_kind": "generated_prospect", "current_ability": 52.0, "potential": 70.0, "seed": 4242}
    canonical["players"].append(player)
    canonical["traits"].extend({**t, "player_id": FICTIONAL_ID} for t in base["traits"] if t["player_id"] == template["id"])
    return canonical


def _state(canonical):
    traits = {(t["player_id"], t["trait_key"]): t["value"] for t in canonical["traits"]}
    inputs = {pid: rm.effective_inputs(canonical, pid) for pid in (FICTIONAL_ID, "player_den-nikola-jokic")}
    return traits, inputs


@unittest.skipUnless((INPUTS.exists() or INPUTS.with_name(INPUTS.name + ".gz").exists()) and UNIVERSE.exists(),
                     "player inputs file not built yet")
class InputsCacheParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        cls.base = json.loads(UNIVERSE.read_text())

    def test_daily_season_stats_do_not_re_estimate_generated_players(self):
        _clear_caches()
        first = _with_fictional_player(self.base)
        rm.install_inputs_model(first, ROOT)
        self.assertIn(FICTIONAL_ID, first[rm.MODEL_KEY]["generated"])
        cached_inputs = rm.effective_inputs(first, FICTIONAL_ID)
        # A later league rebuild: the player has played games since (the save attaches his season stats).
        second = _with_fictional_player(self.base)
        next(p for p in second["players"] if p["id"] == FICTIONAL_ID)["_save_stats"] = {"games": 12, "points": 101}
        with patch.object(input_estimator.InputEstimator, "estimate_player_inputs",
                          side_effect=AssertionError("re-estimated")):
            rm.install_inputs_model(second, ROOT)
        self.assertIs(rm.effective_inputs(second, FICTIONAL_ID), cached_inputs)
        # ... and exactly what a cold process computes for the same rebuild.
        warm = _state(second)
        _clear_caches()
        cold = _with_fictional_player(self.base)
        next(p for p in cold["players"] if p["id"] == FICTIONAL_ID)["_save_stats"] = {"games": 12, "points": 101}
        rm.install_inputs_model(cold, ROOT)
        self.assertEqual(warm, _state(cold))

    def test_a_changed_generator_definition_is_re_estimated(self):
        _clear_caches()
        first = _with_fictional_player(self.base)
        rm.install_inputs_model(first, ROOT)
        changed = _with_fictional_player(self.base)
        next(p for p in changed["players"] if p["id"] == FICTIONAL_ID)["current_ability"] = 60.0
        rm.install_inputs_model(changed, ROOT)
        self.assertNotEqual(rm.effective_inputs(first, FICTIONAL_ID), rm.effective_inputs(changed, FICTIONAL_ID))

    def test_feature_and_rate_caches_match_uncached_values(self):
        canonical = deepcopy(self.base)
        rm.install_inputs_model(canonical, ROOT)
        players = [p["id"] for p in canonical["players"] if rm.effective_inputs(canonical, p["id"]) is not None][:200]
        self.assertGreater(len(players), 100)
        models = ((box_rates.POINTS_INPUTS, 3.0, 40.0), (box_rates.TURNOVERS_INPUTS, 0.4, 7.0),
                  (box_rates.ASSISTS_INPUTS, 0.5, 16.0), (box_rates.STEALS_INPUTS, 0.2, 4.0),
                  (box_rates.FTA_PER_POINT_INPUTS, 0.03, 0.75))
        for _ in range(2):   # cold, then warm
            for pid in players:
                record = rm.effective_inputs(canonical, pid)
                self.assertEqual(impact_value.input_features(record), impact_value._input_features(record))
                for model, low, high in models:
                    rate = box_rates._log_linear(model, box_rates.flatten_inputs(record))
                    expected = None if rate is None else round(box_rates.clamp(rate, low, high), 4)
                    self.assertEqual(box_rates._from_inputs(model, record, low, high), expected)
        # The returned feature list is the caller's own: editing it never reaches the cache.
        record = rm.effective_inputs(canonical, players[0])
        impact_value.input_features(record).append(99.0)
        self.assertEqual(impact_value.input_features(record), impact_value._input_features(record))


if __name__ == "__main__":
    unittest.main()
