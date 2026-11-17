from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nba_gm_data import save as engine
from nba_gm_data.app_actions import load_app_canonical

ROOT = Path(__file__).resolve().parents[1]


class RuntimeCopyTests(unittest.TestCase):
    def test_nested_data_is_equal_and_detached_with_aliases_and_cycles_preserved(self):
        shared = {"values": [None, True, False, 1, 1.5, "text", (1, 2)]}
        data = {"a": shared, "b": shared}
        data["self"] = data
        cloned = engine._copy_runtime_tree(data)
        self.assertIs(cloned["self"], cloned)
        self.assertIs(cloned["a"], cloned["b"])
        self.assertIsNot(cloned["a"], shared)
        self.assertEqual(cloned["a"], shared)
        cloned["a"]["values"].append("new")
        self.assertNotIn("new", shared["values"])

    def test_nonserializable_internal_objects_keep_deepcopy_compatibility(self):
        callback = lambda: 1
        source = {"callback": callback, "mutable": [1]}
        cloned = engine._copy_runtime_tree(source)
        self.assertIs(cloned["callback"], callback)
        self.assertIsNot(cloned["mutable"], source["mutable"])

    def test_active_universe_and_save_side_effects_match_deepcopy_reference(self):
        canonical = load_app_canonical(ROOT)
        with TemporaryDirectory() as directory:
            saved = engine.create_league_save(ROOT, canonical, "GSW", Path(directory) / "career.json", seed=17)
            original = deepcopy(canonical)
            fast_save, reference_save = deepcopy(saved), deepcopy(saved)
            fast = engine.canonical_with_save(canonical, fast_save)
            with patch.object(engine, "_copy_runtime_tree", side_effect=deepcopy):
                reference = engine.canonical_with_save(canonical, reference_save)
            self.assertEqual(fast, reference)
            self.assertEqual(fast_save, reference_save)
            self.assertEqual(canonical, original)
            fast["traits"][0]["components"]["test_mutation"] = True
            self.assertNotIn("test_mutation", canonical["traits"][0]["components"])

    def test_non_league_projection_still_preserves_derived_tables(self):
        source = {"players": [], "traits": [], "player_asset_valuations": [{"id": "a", "value": [1]}]}
        actual = engine.canonical_with_save(source, {})
        self.assertEqual(actual["player_asset_valuations"], source["player_asset_valuations"])
        actual["player_asset_valuations"][0]["value"].append(2)
        self.assertEqual(source["player_asset_valuations"][0]["value"], [1])
