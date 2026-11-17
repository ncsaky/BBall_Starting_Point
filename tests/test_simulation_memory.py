"""Temporary simulation universes must not accumulate in process-wide indexes."""
from copy import deepcopy
import gc
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data import save, sim, spatial


class TrackedRow(dict):
    pass


class SimulationMemoryTests(unittest.TestCase):
    def setUp(self):
        sim._SIM_FEATURE_CACHE.clear()
        spatial._SPATIAL_INDEX_CACHE.clear()
        sim._reference_json_bytes.cache_clear()

    tearDown = setUp

    def fixture(self, value=80, owned=True):
        return {"_allow_internal_caches": owned, "meta": {},
                "players": [{"id": "p", "name": "Player", "position": "SG", "minutes_projection": 24}],
                "traits": [TrackedRow(player_id="p", trait_key="shooting_range", value=value)]}

    def fill(self, active):
        vector = sim.player_feature_vector(active, active["players"][0])
        traits = spatial._trait_index(active)
        return vector, traits

    def test_owned_universes_release_their_traits_without_global_retention(self):
        refs = []
        for _ in range(40):
            active = self.fixture()
            refs.append(weakref.ref(active["traits"][0]))
            self.fill(active)
            del active
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))
        self.assertEqual(sim._SIM_FEATURE_CACHE, {})
        self.assertEqual(spatial._SPATIAL_INDEX_CACHE, {})

    def test_plain_input_fallback_is_bounded_and_does_not_annotate_callers(self):
        refs = []
        for _ in range(40):
            active = self.fixture(owned=False)
            original = deepcopy(active)
            refs.append(weakref.ref(active["traits"][0]))
            self.fill(active)
            self.assertEqual(active, original)
            del active, original
        gc.collect()
        self.assertLessEqual(len(sim._SIM_FEATURE_CACHE), sim._SIM_FEATURE_CACHE_LIMIT)
        self.assertLessEqual(len(spatial._SPATIAL_INDEX_CACHE), spatial._SPATIAL_INDEX_CACHE_LIMIT)
        self.assertLessEqual(sum(ref() is not None for ref in refs), 8)

    def test_cache_hits_and_rebuilds_have_identical_results(self):
        for owned in (False, True):
            active = self.fixture(owned=owned)
            first = self.fill(active)
            self.assertIs(first[0], self.fill(active)[0])
            self.assertIs(first[1], self.fill(active)[1])
            sim.invalidate_sim_cache(active)
            spatial.invalidate_spatial_cache(active)
            rebuilt = self.fill(active)
            self.assertEqual(first, rebuilt)
            self.assertIsNot(first[0], rebuilt[0])
            self.assertIsNot(first[1], rebuilt[1])

    def test_source_replacement_invalidates_both_indexes(self):
        for owned in (False, True):
            active = self.fixture(owned=owned)
            before, _ = self.fill(active)
            active["traits"] = [dict(active["traits"][0], value=20)]
            after, traits = self.fill(active)
            self.assertNotEqual(before.features["spacing"], after.features["spacing"])
            self.assertEqual(traits["p"]["shooting_range"], 20)

    def test_in_place_trait_changes_require_and_respect_existing_invalidation(self):
        for owned in (False, True):
            active = self.fixture(owned=owned)
            self.fill(active)
            active["traits"][0]["value"] = 20
            sim.invalidate_sim_cache(active)
            spatial.invalidate_spatial_cache(active)
            vector, traits = self.fill(active)
            fresh = self.fixture(value=20, owned=owned)
            self.assertEqual(vector, self.fill(fresh)[0])
            self.assertEqual(traits["p"]["shooting_range"], 20)

    def test_shallow_copies_do_not_share_owner_specific_cache_state(self):
        original = self.fixture()
        self.fill(original)
        copied = dict(original)
        self.fill(copied)
        self.assertIsNot(original["_sim_feature_cache"], copied["_sim_feature_cache"])
        self.assertIsNot(original["_spatial_trait_index"], copied["_spatial_trait_index"])
        sim.invalidate_sim_cache(copied)
        spatial.invalidate_spatial_cache(copied)
        self.assertIn("_sim_feature_cache", original)
        self.assertIn("_spatial_trait_index", original)

    def test_plain_cache_eviction_does_not_change_features(self):
        active = self.fixture(owned=False)
        expected = self.fill(active)
        others = [self.fixture(value=n, owned=False) for n in range(20, 40)]
        for other in others:
            self.fill(other)
        self.assertEqual(self.fill(active), expected)

    def test_players_and_talent_model_are_part_of_sim_cache_validity(self):
        active = self.fixture()
        first = sim.canonical_sim_cache(active)
        active["players"] = list(active["players"])
        second = sim.canonical_sim_cache(active)
        self.assertIsNot(first, second)
        active["meta"]["talent_model_version"] = 2
        self.assertIsNot(second, sim.canonical_sim_cache(active))

    def test_runtime_caches_do_not_change_new_save_fingerprints(self):
        active = self.fixture()
        before = save.canonical_hash(active)
        self.fill(active)
        self.assertEqual(save.canonical_hash(active), before)
        sim.invalidate_sim_cache(active)
        spatial.invalidate_spatial_cache(active)
        self.assertEqual(save.canonical_hash(active), before)

    def test_reference_reads_reuse_parsing_but_return_detached_data(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reference.json"
            path.write_text(json.dumps({"games": [{"score": 12}]}))
            with patch.object(sim, "load_json", wraps=sim.load_json) as parser:
                first = sim.load_reference_json(path)
                first["games"][0]["score"] = -1
                second = sim.load_reference_json(path)
                self.assertEqual(second, {"games": [{"score": 12}]})
                self.assertEqual(parser.call_count, 1)

    def test_reference_edits_same_size_and_mtime_and_atomic_replacement_refresh(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reference.json"
            path.write_text('{"n":12}')
            stamp = path.stat()
            self.assertEqual(sim.load_reference_json(path), {"n": 12})
            path.write_text('{"n":13}')
            # Windows ctime is creation time, not the POSIX change clock.
            if os.name != "nt":
                os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            self.assertEqual(sim.load_reference_json(path), {"n": 13})
            replacement = path.with_suffix(".new")
            replacement.write_text('{"n":14}')
            os.utime(replacement, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            replacement.replace(path)
            self.assertEqual(sim.load_reference_json(path), {"n": 14})

    def test_reference_roots_eviction_missing_and_invalid_files_remain_independent(self):
        with TemporaryDirectory() as directory:
            for index in range(12):
                path = Path(directory) / f"{index}.json"
                path.write_text(json.dumps({"n": index}))
                self.assertEqual(sim.load_reference_json(path), {"n": index})
            self.assertLessEqual(sim._reference_json_bytes.cache_info().currsize, 4)
            path = Path(directory) / "0.json"
            self.assertEqual(sim.load_reference_json(path), {"n": 0})
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                sim.load_reference_json(path)
            path.write_text("not json")
            with self.assertRaises(json.JSONDecodeError):
                sim.load_reference_json(path)

    def test_oversized_reference_files_bypass_the_snapshot_cache(self):
        with patch.object(Path, "stat", return_value=SimpleNamespace(st_size=33 * 1024 * 1024)), \
                patch.object(sim, "load_json", return_value={"large": True}) as parser:
            self.assertEqual(sim.load_reference_json(Path("large.json")), {"large": True})
        self.assertEqual(parser.call_count, 1)
        self.assertEqual(sim._reference_json_bytes.cache_info().currsize, 0)


if __name__ == "__main__":
    unittest.main()
