import unittest

from nba_gm_data.player_model_registry import definition_registry
from nba_gm_data.trait_adapter import (
    ADAPTER_SPEC, LEGACY_TRAITS, derive_traits, fit_adapter, scalar_value, spec_input_ids,
    trait_input_weights, validate_spec,
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

    def test_spec_only_names_real_inputs(self):
        self.assertTrue(spec_input_ids() <= set(DEFS))
        self.assertTrue(all(ADAPTER_SPEC[t] for t in LEGACY_TRAITS))


if __name__ == "__main__":
    unittest.main()
