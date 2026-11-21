import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import ratings_model as rm
from nba_gm_data.save import apply_development_events
from nba_gm_data.trait_adapter import LEGACY_TRAITS, derive_traits

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / rm.INPUTS_FILE
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"


def grade(v):
    return {"status": "estimated", "value": {"grade": v, "scale": "t"}, "evidence": [{"source": "t", "method": "t"}],
            "uncertainty": {"confidence": "low", "notes": "{}"}}


class PlaceholderTraitTests(unittest.TestCase):
    def test_flat_default_with_no_source_data_is_a_placeholder(self):
        empty = {"components": {"fields": ["3PAp75", "3P%"], "components": [None, None]}}
        self.assertTrue(rm.is_placeholder_trait({"value": 50.0, **empty}))
        self.assertFalse(rm.is_placeholder_trait({"value": 51.2, **empty}))   # a real value without notes stays
        self.assertFalse(rm.is_placeholder_trait({"value": 50.0, "components": {"components": [0.4, None]}}))
        self.assertFalse(rm.is_placeholder_trait({"value": 50.0}))

    def test_placeholders_are_left_out_of_the_fit_only(self):
        canonical = {"traits": [
            {"player_id": "a", "trait_key": "t", "value": 50.0, "components": {"components": [None]}},
            {"player_id": "b", "trait_key": "t", "value": 61.0, "components": {"components": [0.3]}},
        ]}
        self.assertEqual(rm._trait_values(canonical), {"a": {"t": 50.0}, "b": {"t": 61.0}})
        self.assertEqual(rm._trait_values(canonical, skip_placeholders=True), {"b": {"t": 61.0}})


def step(input_id):
    return rm._development_steps().get(input_id, rm.GRADE_POINTS_PER_TRAIT_POINT)


class RoutingTests(unittest.TestCase):
    def test_trait_delta_moves_each_input_by_its_share_of_all_traits_using_it(self):
        inputs = {"S08": grade(50), "S03": grade(50), "S02": grade(50), "S01": grade(50)}
        deltas = rm.route_trait_deltas(inputs, {"release_speed": 4.0})
        from nba_gm_data.trait_adapter import trait_input_weights
        totals = rm._input_trait_weight_totals()
        for input_id in inputs:
            share = trait_input_weights("release_speed")[input_id] / totals[input_id]
            self.assertAlmostEqual(deltas[input_id], 4.0 * step(input_id) * share)
        # S08 (release technique) is used only by release_speed, so it takes its full step.
        self.assertAlmostEqual(deltas["S08"], 4.0 * step("S08"))

    def test_uniform_gain_moves_every_movable_input_by_its_own_step(self):
        # Each input's step is the common step scaled by its league spread (DEV-CURVE 2026-11-21), so a uniform
        # gain moves every input by the same share of its own spread.
        from nba_gm_data.trait_adapter import LEGACY_TRAITS
        inputs = {i: grade(50) for i in ("S01", "S08", "S17", "S33", "S37", "F01.recognition")}
        deltas = rm.route_trait_deltas(inputs, {t: 1.0 for t in LEGACY_TRAITS})
        for input_id in inputs:
            self.assertAlmostEqual(deltas[input_id], step(input_id))

    def test_physical_capacities_develop_but_body_dimensions_do_not(self):
        def physical(v):
            return {"status": "estimated", "value": {"measurements": [], "display_grade": {"grade": v, "scale": "t"}},
                    "evidence": [{"source": "t", "method": "t"}], "uncertainty": {"confidence": "low", "notes": "{}"}}
        inputs = {"P11": physical(50), "P12": physical(50), "P04": physical(50)}
        deltas = rm.route_trait_deltas(inputs, {"stamina_cardio": -2.0})
        self.assertLess(deltas["P11"], 0)
        self.assertNotIn("P04", rm.route_trait_deltas(inputs, {"playoff_translation": 2.0}))
        out = rm.apply_input_deltas(inputs, deltas)
        self.assertAlmostEqual(out["P11"]["value"]["display_grade"]["grade"], 50 + deltas["P11"], places=3)

    def test_involvement_follows_offensive_skill_within_bounds(self):
        involvement = {"status": "estimated", "value": {"probability": 0.30, "reference_conditions": "t"},
                       "evidence": [{"source": "t", "method": "t"}], "uncertainty": {"confidence": "low", "notes": "{}"}}
        inputs = {"S17": grade(50), "S16": grade(50), "S01": grade(50), "T08": involvement}
        up = rm.route_trait_deltas(inputs, {"handle_pressure": 3.0})
        self.assertGreater(up["T08"], 0)
        down = rm.route_trait_deltas(inputs, {"handle_pressure": -3.0})
        self.assertAlmostEqual(down["T08"], -up["T08"])
        self.assertNotIn("T08", rm.route_trait_deltas(inputs, {"rim_deterrence": 3.0}))
        capped = rm.apply_input_deltas(inputs, {"T08": 5.0})
        self.assertEqual(capped["T08"]["value"]["probability"], rm.INVOLVEMENT_BOUNDS[1])

    def test_measurements_are_never_moved_by_development(self):
        height = {"status": "estimated", "value": {"measurements": [{"value": 200.0, "unit": "cm"}]},
                  "evidence": [{"source": "t", "method": "t"}], "uncertainty": {"confidence": "low", "notes": "{}"}}
        deltas = rm.route_trait_deltas({"P01": height, "S37": grade(60)}, {"playoff_translation": 3.0})
        self.assertNotIn("P01", deltas)

    def test_grades_have_a_floor_but_no_top(self):
        # DEV-CURVE (2026-11-21): no clipping at 100 (AGENTS.md rule 3).
        out = rm.apply_input_deltas({"S08": grade(99), "S09": grade(2)}, {"S08": 5, "S09": -5})
        self.assertEqual(out["S08"]["value"]["grade"], 104.0)
        self.assertEqual(out["S09"]["value"]["grade"], 0.0)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            rm.ratings_model_for({"meta": {"ratings_model": "bogus"}})

    def test_default_mode_is_inputs_for_new_saves_and_save_less_tools(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NBA_GM_RATINGS_MODEL", None)
            self.assertEqual(rm.ratings_model_for(), rm.INPUTS_V1)          # scorecards and fit scripts
            self.assertEqual(rm.ratings_model_for({}), rm.LEGACY)           # a save that predates the field
            os.environ["NBA_GM_RATINGS_MODEL"] = rm.LEGACY
            self.assertEqual(rm.ratings_model_for(), rm.LEGACY)             # older set still selectable
        import inspect
        from nba_gm_data.save import create_league_save
        self.assertEqual(inspect.signature(create_league_save).parameters["ratings_model"].default, rm.INPUTS_V1)


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
        self.assertTrue(all(record.get("reason") in ("prior", "estimated", "generated") for record in inputs.values()))
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

    def test_todays_players_map_exactly_as_the_original_step_map(self):
        """RATING-CEILING: removing the hidden top changed nothing for anyone in the league tables."""
        from bisect import bisect_left, bisect_right
        from nba_gm_data import trait_adapter as ta

        def step_pct(table, value):
            lo, hi = bisect_left(table, value), bisect_right(table, value)
            return ((lo + hi) / 2) / len(table)

        def step_value_at(table, pct):
            position = min(max(pct, 0.0), 1.0) * (len(table) - 1)
            low = int(position)
            high = min(low + 1, len(table) - 1)
            return table[low] * (1 - (position - low)) + table[high] * (position - low)

        fitted = rm._FITTED_CACHE[tuple(self.canonical[rm.MODEL_KEY]["fitted_key"])]
        for pid, inputs in rm.load_league_inputs(ROOT).items():
            scalars = ta._scalars_for_player(inputs, ta._definitions())
            new = derive_traits(inputs, fitted)
            for trait in ta.LEGACY_TRAITS:
                total = weight_sum = 0.0
                for term, weight in ta.ADAPTER_SPEC[trait]:
                    keys = [f"{i}:{o}" if o else i for i, o in ta._term_keys(term)]
                    pcts = [step_pct(fitted.input_tables[k], scalars[k]) for k in keys if k in scalars and fitted.input_tables.get(k)]
                    if pcts:
                        total += weight * (sum(pcts) / len(pcts))
                        weight_sum += weight
                old = (step_value_at(fitted.target_tables[trait], 0.5) if not weight_sum else
                       step_value_at(fitted.target_tables[trait], step_pct(fitted.composite_tables[trait], total / weight_sum)))
                self.assertEqual(new[trait], round(old, 3), (pid, trait))

    def test_an_elite_player_keeps_rising_past_the_old_top(self):
        """RATING-CEILING: Wembanyama's traits, value and sim impact keep rising as he develops (they stopped at the
        league's opening-day best: value 78.0, sim impact 82.05)."""
        from nba_gm_data.impact_value import installed_tables, player_impact, sim_impact
        from nba_gm_data.save import player_attribute_summary, trait_values_by_player
        pid = next(p["id"] for p in self.base["players"] if p["name"] == "Victor Wembanyama")
        player = next(p for p in self.canonical["players"] if p["id"] == pid)
        tables = installed_tables(self.canonical)
        self.assertIsNotNone(tables)
        rows = []
        for step in (0, 10, 20, 30):
            canonical = deepcopy(self.canonical)
            canonical[rm.MODEL_KEY]["input_deltas"] = {}
            if step:
                rm.apply_development(canonical, {pid: {t: float(step) for t in LEGACY_TRAITS}}, [])
            canonical.pop("_trait_values_by_player", None)
            traits = trait_values_by_player(canonical)[pid]
            rows.append((traits, player_attribute_summary(canonical, pid)["overall"], sim_impact(canonical, player, traits),
                         player_impact(canonical, player)["overall"]))
        for before, after in zip(rows, rows[1:]):
            self.assertGreater(after[1], before[1])            # engine value
            self.assertGreater(after[2], before[2])            # sim impact
            self.assertGreater(after[3], before[3])            # fitted impact
            self.assertTrue(all(after[0][t] >= before[0][t] for t in after[0]))
        self.assertGreater(rows[-1][1], max(tables["overall"]["target"]) + 3.0)
        self.assertGreater(rows[-1][2], max(tables["sim_impact"]["target"]) + 3.0)

    def test_legacy_universe_still_uses_the_legacy_development_path(self):
        canonical = deepcopy(self.base)
        before = self.trait(canonical, "passing_reads")
        apply_development_events(canonical, [{"player_id": self.pid, "trait_deltas": {"passing_reads": 2.0}}])
        self.assertAlmostEqual(self.trait(canonical, "passing_reads"), round(before + 2.0, 3))


if __name__ == "__main__":
    unittest.main()
