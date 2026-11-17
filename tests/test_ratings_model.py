import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import ratings_model as rm
from nba_gm_data.save import apply_development_events
from nba_gm_data.trait_adapter import derive_traits

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / rm.INPUTS_FILE
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"


def grade(v):
    return {"status": "estimated", "value": {"grade": v, "scale": "t"}, "evidence": [{"source": "t", "method": "t"}],
            "uncertainty": {"confidence": "low", "notes": "{}"}}


class RoutingTests(unittest.TestCase):
    def test_trait_delta_spreads_over_grade_inputs_by_weight(self):
        inputs = {"S08": grade(50), "S03": grade(50), "S02": grade(50), "S01": grade(50)}
        deltas = rm.route_trait_deltas(inputs, {"release_speed": 4.0})
        self.assertAlmostEqual(sum(deltas.values()), 4.0)
        from nba_gm_data.trait_adapter import trait_input_weights
        self.assertAlmostEqual(deltas["S08"], 4.0 * trait_input_weights("release_speed")["S08"] / sum(
            w for i, w in trait_input_weights("release_speed").items() if i in inputs))

    def test_measurements_are_never_moved_by_development(self):
        height = {"status": "estimated", "value": {"measurements": [{"value": 200.0, "unit": "cm"}]},
                  "evidence": [{"source": "t", "method": "t"}], "uncertainty": {"confidence": "low", "notes": "{}"}}
        deltas = rm.route_trait_deltas({"P01": height, "S37": grade(60)}, {"playoff_translation": 3.0})
        self.assertNotIn("P01", deltas)

    def test_grades_stay_inside_the_schema_range(self):
        out = rm.apply_input_deltas({"S08": grade(99)}, {"S08": 5})
        self.assertEqual(out["S08"]["value"]["grade"], 100.0)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            rm.ratings_model_for({"meta": {"ratings_model": "bogus"}})

    def test_default_mode_is_legacy(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NBA_GM_RATINGS_MODEL", None)
            self.assertEqual(rm.ratings_model_for({}), rm.LEGACY)


@unittest.skipUnless((INPUTS.exists() or INPUTS.with_name(INPUTS.name + ".gz").exists()) and UNIVERSE.exists(), "player inputs file not built yet")
class InputsModelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(UNIVERSE.read_text())
        cls.canonical = deepcopy(cls.base)
        rm.install_inputs_model(cls.canonical, ROOT)
        cls.pid = next(p["id"] for p in cls.base["players"] if p["name"] == "Stephen Curry")

    def trait(self, canonical, key):
        return next(t["value"] for t in canonical["traits"] if t["player_id"] == self.pid and t["trait_key"] == key)

    def test_installed_traits_equal_adapter_output_and_model_stays_small(self):
        fitted = rm._FITTED_CACHE[tuple(self.canonical[rm.MODEL_KEY]["fitted_key"])]
        expected = derive_traits(rm.effective_inputs(self.canonical, self.pid), fitted)
        self.assertEqual(self.trait(self.canonical, "shooting_range"), expected["shooting_range"])
        self.assertLess(len(json.dumps(self.canonical[rm.MODEL_KEY], default=str)), 10_000)

    def test_development_moves_inputs_then_traits_and_card_agree(self):
        canonical = deepcopy(self.canonical)
        before_inputs = deepcopy(rm.effective_inputs(canonical, self.pid))
        before = self.trait(canonical, "passing_reads")
        apply_development_events(canonical, [{"player_id": self.pid, "trait_deltas": {"passing_reads": 6.0}}])
        after_inputs = rm.effective_inputs(canonical, self.pid)
        self.assertGreater(after_inputs["S20"]["value"]["grade"], before_inputs["S20"]["value"]["grade"])
        self.assertEqual(after_inputs["P01"], before_inputs["P01"])
        self.assertGreaterEqual(self.trait(canonical, "passing_reads"), before)
        fitted = rm._FITTED_CACHE[tuple(canonical[rm.MODEL_KEY]["fitted_key"])]
        self.assertEqual(self.trait(canonical, "passing_reads"), derive_traits(after_inputs, fitted)["passing_reads"])

    def test_generated_rookie_gets_inputs_and_derived_traits_without_moving_others(self):
        canonical = deepcopy(self.base)
        template = next(p for p in canonical["players"] if p["name"] == "Cooper Flagg")
        rookie = {**template, "id": "rookie_player_test_2027", "name": "Test Rookie", "source_kind": "generated_rookie"}
        canonical["players"].append(rookie)
        legacy = [dict(t, player_id=rookie["id"]) for t in canonical["traits"] if t["player_id"] == template["id"]]
        canonical["traits"].extend(legacy)
        rm.install_inputs_model(canonical, ROOT)
        inputs = rm.effective_inputs(canonical, rookie["id"])
        self.assertIsNotNone(inputs)
        self.assertEqual(len(inputs), 94)
        self.assertTrue(all(record.get("reason") in ("prior", "estimated") for record in inputs.values()))
        # The same adapter tables are used: adding a rookie must not change veterans' derived traits.
        curry = lambda c: {t["trait_key"]: t["value"] for t in c["traits"] if t["player_id"] == self.pid}
        self.assertEqual(curry(canonical), curry(self.canonical))
        # Development of a generated player flows through inputs like everyone else's.
        before = next(t["value"] for t in canonical["traits"] if t["player_id"] == rookie["id"] and t["trait_key"] == "passing_reads")
        apply_development_events(canonical, [{"player_id": rookie["id"], "trait_deltas": {"passing_reads": 5.0}}])
        after = next(t["value"] for t in canonical["traits"] if t["player_id"] == rookie["id"] and t["trait_key"] == "passing_reads")
        self.assertGreaterEqual(after, before)

    def test_development_is_stored_as_small_deltas_not_full_input_copies(self):
        canonical = deepcopy(self.canonical)
        apply_development_events(canonical, [{"player_id": self.pid, "trait_deltas": {"release_speed": 3.0}}])
        stored = canonical[rm.MODEL_KEY]["input_deltas"][self.pid]
        self.assertLessEqual(len(stored), 6)
        self.assertTrue(all(isinstance(v, float) for v in stored.values()))

    def test_legacy_universe_still_uses_the_legacy_development_path(self):
        canonical = deepcopy(self.base)
        before = self.trait(canonical, "passing_reads")
        apply_development_events(canonical, [{"player_id": self.pid, "trait_deltas": {"passing_reads": 2.0}}])
        self.assertAlmostEqual(self.trait(canonical, "passing_reads"), round(before + 2.0, 3))


if __name__ == "__main__":
    unittest.main()
