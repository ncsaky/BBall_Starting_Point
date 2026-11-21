import unittest

from nba_gm_data.player_model_registry import definition_registry
from nba_gm_data.trait_adapter import (
    ADAPTER_SPEC, LEGACY_TRAITS, _excess_z, _percentile, _trait_value, derive_traits, fit_adapter, scalar_value, spec_input_ids,
    trait_input_weights, uncensor_top, validate_spec,
)

DEFS = {row["id"]: row for row in definition_registry()["inputs"]}
EVIDENCE = [{"source": "test", "method": "synthetic"}]
UNCERTAINTY = {"confidence": "low", "notes": "{}"}


def grade(v):
    return {"status": "estimated", "value": {"grade": v, "scale": "test"}, "evidence": EVIDENCE, "uncertainty": UNCERTAINTY}


def physical(v, unit):
    return {"status": "estimated", "value": {"measurements": [{"value": v, "unit": unit}]}, "evidence": EVIDENCE,
            "uncertainty": UNCERTAINTY}


def propensity(p):
    return {"status": "estimated", "value": {"probability": p, "reference_conditions": "test"}, "evidence": EVIDENCE,
            "uncertainty": UNCERTAINTY}


def distribution(input_id, lead):
    outcomes = DEFS[input_id]["outcomes"]
    rest = (1 - lead) / (len(outcomes) - 1)
    probs = {o: (lead if i == 0 else rest) for i, o in enumerate(outcomes)}
    return {"status": "estimated", "value": {"reference_conditions": "test", "rows": [{"condition": "base", "probabilities": probs}]},
            "evidence": EVIDENCE, "uncertainty": UNCERTAINTY}


def player(level):
    """A synthetic player whose every input scales with `level` in [0, 1]."""
    out = {}
    for input_id in spec_input_ids():
        kind = DEFS[input_id]["kind"]
        units = DEFS[input_id].get("units") or DEFS[input_id].get("unit") or []
        if kind == "grade":
            out[input_id] = grade(30 + 60 * level)
        elif kind == "propensity":
            out[input_id] = propensity(0.1 + 0.8 * level)
        elif kind == "physical":
            # Time-based inputs where lower is better get shorter times for better players.
            lower_better = (input_id, units[0]) in {("P07", "s"), ("P09", "s"), ("P12", "s")}
            out[input_id] = physical(10 - 5 * level if lower_better else 150 + 80 * level, units[0])
        else:
            out[input_id] = distribution(input_id, 0.2 + 0.6 * level)
    return out


class TraitAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.levels = [i / 20 for i in range(21)]
        cls.league = {f"p{i}": player(level) for i, level in enumerate(cls.levels)}
        cls.traits = {f"p{i}": {t: 40 + i for t in LEGACY_TRAITS} for i in range(21)}
        cls.fitted = fit_adapter(cls.league, cls.traits)

    def test_spec_is_valid_and_covers_all_fifteen_traits(self):
        validate_spec()
        self.assertEqual(len(LEGACY_TRAITS), 15)
        for trait in LEGACY_TRAITS:
            self.assertAlmostEqual(sum(trait_input_weights(trait).values()), 1.0)

    def test_better_inputs_give_better_traits_within_the_current_league_range(self):
        low = derive_traits(self.league["p2"], self.fitted)
        high = derive_traits(self.league["p18"], self.fitted)
        for trait in LEGACY_TRAITS:
            self.assertGreater(high[trait], low[trait], trait)
            self.assertGreaterEqual(low[trait], 40)
            self.assertLessEqual(high[trait], 60)

    def test_one_input_moves_only_the_traits_that_use_it(self):
        base = derive_traits(self.league["p10"], self.fitted)
        boosted_inputs = dict(self.league["p10"], S08=grade(95))
        boosted = derive_traits(boosted_inputs, self.fitted)
        self.assertGreater(boosted["release_speed"], base["release_speed"])
        for trait in LEGACY_TRAITS:
            if "S08" not in trait_input_weights(trait):
                self.assertEqual(boosted[trait], base[trait], trait)

    def test_missing_inputs_fall_back_to_league_median_without_crashing(self):
        derived = derive_traits({}, self.fitted)
        self.assertEqual(derived["release_speed"], 50.0)

    def test_unknown_records_are_ignored_not_treated_as_zero(self):
        unknown = {"status": "unknown", "value": None, "evidence": [], "uncertainty": {"confidence": "unknown", "notes": "x"}}
        self.assertIsNone(scalar_value(DEFS["S08"], unknown))

    def test_time_measurements_count_lower_as_better(self):
        # P12 recovery time: primary unit seconds, lower is better.
        fast = scalar_value(DEFS["P12"], physical(20.0, "s"))
        slow = scalar_value(DEFS["P12"], physical(40.0, "s"))
        self.assertGreater(fast, slow)

    def test_measurements_outside_the_primary_unit_are_not_mixed_in(self):
        # P07's primary unit is m/s; a lone seconds measurement can't be ranked against m/s values.
        self.assertIsNone(scalar_value(DEFS["P07"], physical(2.0, "s")))

    def test_distribution_terms_read_the_named_outcome(self):
        record = distribution("T01", 0.5)
        first = DEFS["T01"]["outcomes"][0]
        self.assertAlmostEqual(scalar_value(DEFS["T01"], record, first), 0.5)
        with self.assertRaises(ValueError):
            scalar_value(DEFS["T01"], record)

    def test_clipped_top_plateau_is_rescaled_not_tied(self):
        # Seven values clipped at 100 (like the legacy rim_deterrence table) become a rising tail above 100.
        values = sorted([i * 0.15 for i in range(500)] + [74.0 + i * 0.3 for i in range(80)] + [100.0] * 7)
        out = uncensor_top(values)
        self.assertEqual(out[:-7], values[:-7])
        top = out[-7:]
        self.assertTrue(all(b > a for a, b in zip(top, top[1:])))
        self.assertGreaterEqual(top[0], 100.0)
        self.assertGreater(top[-1], 101.0)
        # No plateau, or one below the ceiling: unchanged.
        self.assertEqual(uncensor_top([float(i) for i in range(100)]), [float(i) for i in range(100)])
        self.assertEqual(uncensor_top([float(i) for i in range(90)] + [90.0] * 5), [float(i) for i in range(90)] + [90.0] * 5)

    def test_rim_deterrence_recipe_is_rim_technique_and_size_not_jump_height(self):
        weights = trait_input_weights("rim_deterrence")
        # Contest technique and interior positioning lead; standing height and length carry size; jump height (P10),
        # where guards out-jump centers, and generic foul control are no longer in the recipe.
        self.assertGreater(weights["S37"], 0.4)
        self.assertIn("P01", weights)
        self.assertNotIn("P10", weights)
        self.assertNotIn("S45", weights)

    def test_spec_only_names_real_inputs(self):
        self.assertTrue(spec_input_ids() <= set(DEFS))
        self.assertTrue(all(ADAPTER_SPEC[t] for t in LEGACY_TRAITS))


class NoHardTopTests(unittest.TestCase):
    """RATING-CEILING (2026-11-21): the maps from inputs to traits are continuous and keep rising past the league's best."""

    TABLE = sorted([10.0, 20.0, 20.0, 20.0, 35.0, 40.0, 41.0, 55.0, 60.0, 61.0, 70.0, 72.0, 80.0, 81.0, 90.0])

    @staticmethod
    def step_percentile(table, value):
        """The original step map (mid-rank of the run, or the share of values below)."""
        from bisect import bisect_left, bisect_right
        lo, hi = bisect_left(table, value), bisect_right(table, value)
        return ((lo + hi) / 2) / len(table)

    def test_league_values_keep_their_exact_percentile(self):
        for value in self.TABLE:
            self.assertEqual(_percentile(self.TABLE, value), self.step_percentile(self.TABLE, value))

    def test_percentile_is_continuous_and_monotone_inside_the_league(self):
        xs = [10 + x / 4 for x in range(0, 321)]
        ps = [_percentile(self.TABLE, x) for x in xs]
        self.assertTrue(all(b > a for a, b in zip(ps, ps[1:])))
        self.assertLess(max(abs(b - a) for a, b in zip(ps, ps[1:])), 0.03, "no jumps")

    def test_distance_past_the_ends_is_measured_on_the_tail_scale(self):
        self.assertEqual(_excess_z(self.TABLE, 50.0), 0.0)
        beyond = [_excess_z(self.TABLE, 90.0 + d) for d in (0.0, 1.0, 5.0, 20.0)]
        self.assertEqual(beyond[0], 0.0)
        self.assertTrue(all(b > a for a, b in zip(beyond, beyond[1:])))
        below = [_excess_z(self.TABLE, 10.0 - d) for d in (0.0, 1.0, 5.0)]
        self.assertTrue(all(b < a for a, b in zip(below, below[1:])))

    def test_composite_to_trait_is_continuous_monotone_and_unbounded(self):
        composites = sorted(i / 200 for i in range(201))
        target = sorted(40 + 0.3 * i for i in range(201))
        path = [_trait_value(composites, target, c / 400, 0.0) for c in range(-100, 400)]
        path += [_trait_value(composites, target, 1.0, e / 10) for e in range(1, 40)]
        self.assertTrue(all(b > a for a, b in zip(path, path[1:])))
        self.assertLess(max(b - a for a, b in zip(path, path[1:])), 1.0, "no jumps")
        self.assertGreater(path[-1], max(target) + 10)
        self.assertLess(path[0], min(target))

    def test_players_beyond_the_league_best_keep_rising(self):
        levels = [i / 20 for i in range(21)]
        league = {f"p{i}": player(level) for i, level in enumerate(levels)}
        traits = {f"p{i}": {t: 40 + i for t in LEGACY_TRAITS} for i in range(21)}
        fitted = fit_adapter(league, traits)
        best = derive_traits(league["p20"], fitted)
        beyond = [derive_traits(player(level), fitted) for level in (1.05, 1.10, 1.20)]
        for trait in LEGACY_TRAITS:
            path = [best[trait]] + [b[trait] for b in beyond]
            self.assertTrue(all(b > a for a, b in zip(path, path[1:])), (trait, path))
            self.assertGreater(path[-1], max(fitted.target_tables[trait]), trait)   # past the old top
        # League members stay inside the league's own range (exact equality with the old map: test_ratings_model).
        for pid, inputs in league.items():
            derived = derive_traits(inputs, fitted)
            self.assertTrue(all(39.0 <= v <= 61.0 for v in derived.values()), pid)


if __name__ == "__main__":
    unittest.main()
