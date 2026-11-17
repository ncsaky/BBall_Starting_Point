"""Transitional adapter: the 94 approved player inputs -> the 15 legacy engine traits.

Stage 1 (docs/agents/STAGE1_DESIGN.md). The 94 inputs are the single source of truth about a
player's basketball ability. The legacy engine, AI and every other consumer still read 15 traits,
so this module derives those traits from the inputs. Traits are never edited independently.

How a trait is derived:
1. Each input is reduced to one comparable number (a grade, a measurement in the registry's primary
   unit, a probability, or a named outcome share of a tendency distribution).
2. Each number is converted to a league percentile across all players (so centimetres, grades and
   probabilities combine fairly). Time-based measurements are inverted (faster is better).
3. A trait's composite is a declared weighted mean of input percentiles (ADAPTER_SPEC below).
4. The composite's league percentile is quantile-mapped onto the current league distribution of that
   trait. This keeps the legacy engine's calibrated scale intact while the new evidence decides which
   player sits where. It is engine plumbing, not a ratings adjustment.

Weights are written down for review; they are not fitted to simulation outcomes.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .player_model_registry import definition_registry

ADAPTER_VERSION = "trait_adapter_v1_2026_11_16"

PASS_FAMILIES = [f"F0{i}" for i in range(1, 10)]
PASS_RECOGNITION = [f"{f}.recognition" for f in PASS_FAMILIES]
PASS_EXECUTION = [f"{f}.execution" for f in PASS_FAMILIES]

# A term is (input id, or list of ids averaged together, weight). Distribution inputs use "ID:outcome".
Term = tuple[str | list[str], float]

ADAPTER_SPEC: dict[str, list[Term]] = {
    # Legacy traits mixed skill with usage (e.g. release_speed came from 3PA volume, 3P%, off-screen and
    # handoff usage). The adapter recombines the separated skill and tendency inputs in a similar mix so the
    # legacy engine keeps receiving the information it was calibrated on.
    "release_speed": [("S08", 0.30), ("S03", 0.10), ("S01", 0.10), ("S02", 0.10), ("T02:three", 0.25), ("T10", 0.15)],
    # Legacy shooting_range also sets three-point VOLUME in the engine, so it includes the share of shots a
    # player takes from three (T02 tendency) alongside shooting skill.
    "shooting_range": [("T02:three", 0.55), ("S09", 0.15), ("S01", 0.10), ("S02", 0.10), ("S03", 0.05), ("S07", 0.05)],
    # Legacy shot_versatility counted how many play types a player is used in (a usage signal), so the
    # adapter pairs shot-making breadth with involvement and difficult-shot appetite tendencies.
    "shot_versatility": [
        ("S02", 0.15), ("S05", 0.15), ("S03", 0.05), ("S06", 0.05), ("S11", 0.10), ("S01", 0.05),
        ("S04", 0.05), ("S10", 0.05), ("T08", 0.25), ("T04", 0.10),
    ],
    # Legacy rim pressure drives rim attempts and free throws: self-created drives AND rolls/lobs/dunks.
    "rim_pressure": [
        ("S19", 0.10), ("S10", 0.05), ("S12", 0.05), ("S13", 0.05), ("S15", 0.05), ("S24", 0.15),
        ("P05", 0.05), ("T01:drive", 0.15), ("T02:rim", 0.20), ("T08", 0.15),
    ],
    "handle_pressure": [("S17", 0.25), ("S16", 0.20), ("S18", 0.10), ("S20", 0.10), ("P09", 0.05), ("T08", 0.20), ("T06", 0.10)],
    "passing_reads": [(PASS_RECOGNITION, 0.45), (PASS_EXECUTION, 0.30), ("S20", 0.15), ("S28", 0.10)],
    "foot_speed_lateral_agility": [("P07", 0.45), ("P05", 0.25), ("P06", 0.15), ("S33", 0.15)],
    "stamina_cardio": [("P11", 0.60), ("P12", 0.40)],
    "defensive_effort": [
        ("T17:defense", 0.25), ("S44", 0.25), ("T15", 0.15), ("S40", 0.15), ("S41", 0.10), ("S46", 0.10),
    ],
    "scheme_iq": [("S38", 0.25), ("S39", 0.20), ("S44", 0.15), ("S46", 0.15), ("S28", 0.10), (PASS_RECOGNITION, 0.15)],
    "rim_deterrence": [
        ("S37", 0.20), ("S36", 0.20), ("S38", 0.15), ("P03", 0.15), ("P10", 0.10), ("P02", 0.10), ("S45", 0.10),
    ],
    "screen_navigation": [("S35", 0.55), ("P07", 0.15), ("S34", 0.15), ("P05", 0.15)],
    "offensive_rebounding": [("S29", 0.40), ("T12", 0.20), ("P10", 0.10), ("P03", 0.10), ("S32", 0.10), ("P08", 0.10)],
    "portability": [
        ("S01", 0.20), ("S14", 0.10), ("S25", 0.10), ("S26", 0.10), ("S33", 0.15), ("S35", 0.10),
        ("S39", 0.10), ("F01.execution", 0.15),
    ],
    "playoff_translation": [
        ("S02", 0.15), ("S05", 0.10), ("S18", 0.15), ("S07", 0.10), ("S17", 0.10), ("S33", 0.15),
        ("S37", 0.10), ("S04", 0.10), ("P01", 0.05),
    ],
}

LEGACY_TRAITS = tuple(ADAPTER_SPEC)
# Direction is per input, not per unit: a lateral shuttle time (P07) or recovery time (P12) is better when
# lower, but time-to-exhaustion conditioning (P11) is better when higher.
LOWER_IS_BETTER = {("P07", "s"), ("P09", "s"), ("P09", "deg"), ("P12", "s"), ("P12", "bpm")}


def _definitions() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in definition_registry()["inputs"]}


def term_inputs(term: str | list[str]) -> list[str]:
    ids = term if isinstance(term, list) else [term]
    return [i.split(":", 1)[0] for i in ids]


def scalar_value(definition: Mapping[str, Any], record: Mapping[str, Any] | None, outcome: str | None = None) -> float | None:
    """Reduce one stored input record to a single comparable number (higher = more of the ability)."""
    if not record or record.get("status") == "unknown" or record.get("value") is None:
        return None
    value = record["value"]
    kind = definition["kind"]
    if kind == "grade":
        return float(value["grade"])
    if kind == "propensity":
        return float(value["probability"])
    if kind == "physical":
        if "display_grade" in value:
            return float(value["display_grade"]["grade"])
        # Only the registry's primary unit is ranked, so centimetres are never compared with seconds.
        # A measurement in another unit (without a display grade) is treated as unavailable.
        units = definition.get("units") or definition.get("unit") or []
        primary = units[0] if units else None
        for measure in value.get("measurements") or []:
            if primary is None or measure.get("unit") == primary:
                number = float(measure["value"])
                return -number if (definition["id"], measure.get("unit")) in LOWER_IS_BETTER else number
        return None
    if kind == "distribution":
        rows = value.get("rows") or []
        if not rows:
            return None
        if outcome is None:
            raise ValueError(f"{definition['id']} is a distribution; the adapter term must name an outcome")
        shares = [float(row["probabilities"].get(outcome, 0.0)) for row in rows]
        return sum(shares) / len(shares)
    return None


def _term_keys(term: str | list[str]) -> list[tuple[str, str | None]]:
    ids = term if isinstance(term, list) else [term]
    out = []
    for item in ids:
        input_id, _, outcome = item.partition(":")
        out.append((input_id, outcome or None))
    return out


def _percentile(sorted_values: list[float], value: float) -> float:
    """Mid-rank percentile in [0, 1]; ties share the same percentile."""
    if not sorted_values:
        return 0.5
    lo, hi = bisect_left(sorted_values, value), bisect_right(sorted_values, value)
    return ((lo + hi) / 2) / len(sorted_values)


def _value_at(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        raise ValueError("Empty target distribution")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = min(max(pct, 0.0), 1.0) * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    frac = position - low
    return sorted_values[low] * (1 - frac) + sorted_values[high] * frac


@dataclass(frozen=True)
class FittedAdapter:
    """League reference tables needed to derive traits for any player (including later developed ones)."""

    input_tables: dict[str, list[float]]          # "ID" or "ID:outcome" -> sorted league scalars
    composite_tables: dict[str, list[float]]      # trait -> sorted league composites
    target_tables: dict[str, list[float]]         # trait -> sorted current league trait values
    version: str = ADAPTER_VERSION


def _scalars_for_player(inputs: Mapping[str, Any], definitions: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for terms in ADAPTER_SPEC.values():
        for term, _ in terms:
            for input_id, outcome in _term_keys(term):
                key = f"{input_id}:{outcome}" if outcome else input_id
                if key in out:
                    continue
                value = scalar_value(definitions[input_id], inputs.get(input_id), outcome)
                if value is not None:
                    out[key] = value
    return out


def _composite(scalars: Mapping[str, float], input_tables: Mapping[str, list[float]], trait: str) -> float | None:
    total = weight_sum = 0.0
    for term, weight in ADAPTER_SPEC[trait]:
        pcts = []
        for input_id, outcome in _term_keys(term):
            key = f"{input_id}:{outcome}" if outcome else input_id
            if key in scalars and input_tables.get(key):
                pcts.append(_percentile(input_tables[key], scalars[key]))
        if pcts:
            total += weight * (sum(pcts) / len(pcts))
            weight_sum += weight
    return total / weight_sum if weight_sum else None


def fit_adapter(league_inputs: Mapping[str, Mapping[str, Any]], league_traits: Mapping[str, Mapping[str, float]]) -> FittedAdapter:
    """Build league tables. league_inputs: player_id -> {input_id: record}; league_traits: player_id -> {trait: value}."""
    definitions = _definitions()
    scalars = {pid: _scalars_for_player(inputs, definitions) for pid, inputs in league_inputs.items()}
    input_tables: dict[str, list[float]] = {}
    for values in scalars.values():
        for key, value in values.items():
            input_tables.setdefault(key, []).append(value)
    for key in input_tables:
        input_tables[key].sort()
    composite_tables: dict[str, list[float]] = {}
    target_tables: dict[str, list[float]] = {}
    for trait in LEGACY_TRAITS:
        composites = [c for c in (_composite(s, input_tables, trait) for s in scalars.values()) if c is not None]
        composite_tables[trait] = sorted(composites)
        targets = [float(t[trait]) for t in league_traits.values() if t.get(trait) is not None]
        if not targets:
            raise ValueError(f"No current league values for legacy trait {trait}")
        target_tables[trait] = sorted(targets)
    return FittedAdapter(input_tables, composite_tables, target_tables)


def derive_traits(inputs: Mapping[str, Any], fitted: FittedAdapter) -> dict[str, float]:
    """Derive all 15 legacy traits for one player from their input records."""
    scalars = _scalars_for_player(inputs, _definitions())
    out: dict[str, float] = {}
    for trait in LEGACY_TRAITS:
        composite = _composite(scalars, fitted.input_tables, trait)
        target = fitted.target_tables[trait]
        if composite is None:
            out[trait] = round(_value_at(target, 0.5), 3)  # no usable inputs: league median, never a crash
            continue
        pct = _percentile(fitted.composite_tables[trait], composite)
        out[trait] = round(_value_at(target, pct), 3)
    return out


def trait_input_weights(trait: str) -> dict[str, float]:
    """Each input's share of a trait (normalized). Used to route development deltas back onto inputs."""
    shares: dict[str, float] = {}
    for term, weight in ADAPTER_SPEC[trait]:
        ids = term_inputs(term)
        for input_id in ids:
            shares[input_id] = shares.get(input_id, 0.0) + weight / len(ids)
    total = sum(shares.values())
    return {k: v / total for k, v in shares.items()}


def spec_input_ids() -> set[str]:
    return {i for terms in ADAPTER_SPEC.values() for term, _ in terms for i in term_inputs(term)}


def validate_spec(input_ids: Iterable[str] | None = None) -> None:
    known = set(input_ids) if input_ids is not None else set(_definitions())
    definitions = _definitions()
    for trait, terms in ADAPTER_SPEC.items():
        if abs(sum(w for _, w in terms) - 1.0) > 1e-9:
            raise ValueError(f"{trait} weights must sum to 1")
        for term, _ in terms:
            for input_id, outcome in _term_keys(term):
                if input_id not in known:
                    raise ValueError(f"{trait}: unknown input {input_id}")
                definition = definitions[input_id]
                if definition["kind"] == "distribution":
                    if outcome is None:
                        raise ValueError(f"{trait}: distribution {input_id} needs an outcome")
                    if definition.get("outcomes") and outcome not in definition["outcomes"]:
                        raise ValueError(f"{trait}: {input_id} has no outcome {outcome}")
                elif outcome is not None:
                    raise ValueError(f"{trait}: {input_id} is not a distribution")
