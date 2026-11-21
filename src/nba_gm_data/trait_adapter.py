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

Both maps (input -> percentile, and composite -> trait) are continuous and have no hard ends
(RATING-CEILING, 2026-11-21). Between league values they interpolate. Past the best (or worst) value in a league
table they continue on the normal-score scale: each table's outer TAIL_SHARE is fitted as value = a + b * z, so a
player who develops a tail-standard-deviation past today's best input sits a tail-standard-deviation past the best
composite and, in turn, past the best trait value (AGENTS.md rule 3: no clipping). Every player in the league
tables maps exactly as before; only values between or beyond league values behave differently.

Weights are written down for review; they are not fitted to simulation outcomes (playoff translation is fitted
to real playoff box production; see its entry).
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from functools import lru_cache
from math import ceil
from statistics import NormalDist
from typing import Any, Iterable, Mapping

from .player_model_registry import definition_registry

ADAPTER_VERSION = "trait_adapter_v5_2026_11_21"

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
    # Legacy passing_reads came from passer rating, assists per 75, box creation and IQ, so it carried passing
    # VOLUME as well as skill (the engine's assist rates read it). Pair the skill inputs with how often a player
    # chooses to pass and how involved he is, as shooting_range pairs skill with three-point share.
    "passing_reads": [
        (PASS_RECOGNITION, 0.35), (PASS_EXECUTION, 0.20), ("S20", 0.10), ("S28", 0.05),
        ("T01:pass", 0.15), ("T08", 0.15),
    ],
    "foot_speed_lateral_agility": [("P07", 0.45), ("P05", 0.25), ("P06", 0.15), ("S33", 0.15)],
    "stamina_cardio": [("P11", 0.60), ("P12", 0.40)],
    "defensive_effort": [
        ("T17:defense", 0.25), ("S44", 0.25), ("T15", 0.15), ("S40", 0.15), ("S41", 0.10), ("S46", 0.10),
    ],
    # Legacy scheme_iq mixed general/offensive IQ (BBallIQ, passer rating) with defensive impact (CraftedDPM),
    # and the engine's passing feature blends it with passing_reads. Half offensive recognition, half defensive.
    "scheme_iq": [
        ("S38", 0.15), ("S39", 0.12), ("S44", 0.12), ("S46", 0.11),
        (PASS_RECOGNITION, 0.25), ("S20", 0.15), ("S28", 0.10),
    ],
    # Fitted to Basketball Index rim evidence (scripts/fit_rim_protection.py, 2026-11-18): the mean z-score of Rim Points
    # Saved, Stable Rim dFG% vs. Expected, Rim Deterrence, Rim Protection, Rim Contests and Block Rate on Contests over
    # 2023-24..2025-26, 491 players, non-negative ridge, out-of-fold r = 0.90. The earlier written recipe averaged
    # league percentiles of generic defensive grades with jump height (P10, where guards out-jump centers) and foul
    # control, so Gilgeous-Alexander and Cunningham rated above Kessler (82.8) and Huff (80.3) and blocks went to wings.
    "rim_deterrence": [("S37", 0.52), ("S36", 0.23), ("P01", 0.14), ("S38", 0.07), ("P02", 0.04)],
    "screen_navigation": [("S35", 0.55), ("P07", 0.15), ("S34", 0.15), ("P05", 0.15)],
    # The engine reads offensive_rebounding as offensive-rebounding production (team offensive rebound rate and extra
    # possessions, each player's rebound share, putbacks, player value). Fitted to Basketball Index offensive-rebounding
    # evidence (scripts/fit_offensive_rebounding.py, 2026-11-18): the mean z-score of Stable Offensive Rebounds Per 75
    # and Offensive Rebounding Talent over 2023-24..2025-26, 491 players, non-negative ridge over rebounding technique,
    # the crash tendency and body inputs, out-of-fold r = 0.87 (the hand-written recipe S29 .40, T12 .20, P10, P03,
    # S32, P08 .10 each: r 0.83, among bigs 0.71 -> 0.78). Production is how often a player crashes (T12) times how well
    # he pursues (S29); the old recipe rated Diabate (97th percentile in offensive rebounds per 75) 83rd percentile.
    "offensive_rebounding": [("T12", 0.64), ("S29", 0.32), ("P02", 0.04)],
    "portability": [
        ("S01", 0.20), ("S14", 0.10), ("S25", 0.10), ("S26", 0.10), ("S33", 0.15), ("S35", 0.10),
        ("S39", 0.10), ("F01.execution", 0.15),
    ],
    # Fitted to real playoff evidence (scripts/fit_playoff_translation.py --groups --blend, 2026-11-19): half recent playoff
    # Game Score per 36, half Basketball Index's playoff offensive talent grades (latest 3-year windows), 227 players,
    # skill-group averages of skill/physical inputs only, non-negative ridge, out-of-fold r = 0.71. The original written
    # recipe ranked Jokic 101st and Giannis 217th; the box-score-only fit ranked Curry 44th and Brunson 135th.
    "playoff_translation": [
        (["S16", "S17", "S18", "S19", "S20", "S24"], 0.307),
        (["S10", "S11", "S12", "S13", "S14", "S15"], 0.283),
        (["S21", "S22", "S23"], 0.162),
        ([f"F0{n}.recognition" for n in range(1, 10)], 0.103),
        (["P01", "P02", "P03", "P04"], 0.077),
        (["S37", "S40", "S43", "S44", "S45", "S46"], 0.068),
    ],
}

LEGACY_TRAITS = tuple(ADAPTER_SPEC)
# Direction is per input, not per unit: a lateral shuttle time (P07) or recovery time (P12) is better when
# lower, but time-to-exhaustion conditioning (P11) is better when higher.
LOWER_IS_BETTER = {("P07", "s"), ("P09", "s"), ("P09", "deg"), ("P12", "s"), ("P12", "bpm")}


_DEFINITIONS: dict[str, dict[str, Any]] | None = None


def _definitions() -> dict[str, dict[str, Any]]:
    """Input definitions by id, parsed once: the registry is a module constant and this module only reads it."""
    global _DEFINITIONS
    if _DEFINITIONS is None:
        _DEFINITIONS = {row["id"]: row for row in definition_registry()["inputs"]}
    return _DEFINITIONS


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


# Share of each league table (at least TAIL_MIN values) whose spread sets the continuation past either end.
TAIL_SHARE = 0.05
TAIL_MIN = 10


def _tail_count(n: int) -> int:
    return min(n - 1, max(TAIL_MIN, ceil(n * TAIL_SHARE)))


def _mid_rank(sorted_values: list[float], value: float) -> float:
    """Mid-rank (in players) of a value present in the table; ties share the middle of their run."""
    return (bisect_left(sorted_values, value) + bisect_right(sorted_values, value)) / 2


def _percentile(sorted_values: list[float], value: float) -> float:
    """Continuous mid-rank percentile inside the league range.

    A value in the table gets its mid-rank share (ties share the same percentile), exactly as the original step map
    did. Between two league values the percentile is interpolated (the step map snapped it to the lower one).
    Beyond either end it stays at the end's percentile; how far beyond is measured by _excess_z."""
    n = len(sorted_values)
    if not n:
        return 0.5
    lo, hi = bisect_left(sorted_values, value), bisect_right(sorted_values, value)
    if hi > lo or n == 1:
        return ((lo + hi) / 2) / n
    if lo == 0:
        return _mid_rank(sorted_values, sorted_values[0]) / n
    if lo == n:
        return _mid_rank(sorted_values, sorted_values[-1]) / n
    a, b = sorted_values[lo - 1], sorted_values[lo]
    ra, rb = _mid_rank(sorted_values, a), _mid_rank(sorted_values, b)
    return (ra + (rb - ra) * (value - a) / (b - a)) / n


_TAIL_CACHE: dict[int, tuple[list[float], tuple[float, float]]] = {}


def _tail_slopes(sorted_values: list[float]) -> tuple[float, float]:
    """(top, bottom) value per normal-score unit: least squares of value on mid-rank normal score over the outer
    TAIL_SHARE of the table (the whole table when a tail has no spread; 0 when the table has none at all).

    League tables are fixed for a save and never edited, so the fit is kept per table object."""
    cached = _TAIL_CACHE.get(id(sorted_values))
    if cached is not None and cached[0] is sorted_values:
        return cached[1]
    n = len(sorted_values)
    slopes = (0.0, 0.0)
    if n >= 3:
        nd = NormalDist()
        zs = [nd.inv_cdf(_mid_rank(sorted_values, v) / n) for v in sorted_values]

        def fit(idx: range) -> float:
            xs = [sorted_values[i] for i in idx]
            zz = [zs[i] for i in idx]
            mz, mx = sum(zz) / len(zz), sum(xs) / len(xs)
            var = sum((z - mz) ** 2 for z in zz)
            return max(0.0, sum((z - mz) * (x - mx) for z, x in zip(zz, xs)) / var) if var else 0.0

        k = _tail_count(n)
        whole = None
        out = []
        for idx in (range(n - 1 - k, n), range(0, k + 1)):
            slope = fit(idx)
            if not slope:
                whole = fit(range(n)) if whole is None else whole
                slope = whole
            out.append(slope)
        slopes = (out[0], out[1])
    _TAIL_CACHE[id(sorted_values)] = (sorted_values, slopes)
    return slopes


def _excess_z(sorted_values: list[float], value: float) -> float:
    """How far past the league's best (positive) or worst (negative) value, in normal-score units of that tail."""
    if not sorted_values or sorted_values[0] <= value <= sorted_values[-1]:
        return 0.0
    top, bottom = _tail_slopes(sorted_values)
    if value > sorted_values[-1]:
        return (value - sorted_values[-1]) / top if top else 0.0
    return (value - sorted_values[0]) / bottom if bottom else 0.0


def uncensor_top(sorted_values: list[float], ceiling: float = 99.5, tail: float = 0.05) -> list[float]:
    """Replace a clipped top plateau with the distribution's own extrapolated tail (rescale, don't clip).

    Several legacy traits were clipped at 100 when they were built (seven players share rim_deterrence 100.0).
    Quantile-mapping onto such a table ties every player whose inputs rank in the top ~1% at exactly 100, so the
    best rim protectors become indistinguishable. When at least two values share a maximum at or above `ceiling`,
    those values are treated as censored: the uncensored upper tail (top `tail` share, at least 10 values) is fitted
    as value = a + b * z on the normal-quantile scale, and the censored ranks continue that line (never below the
    old ceiling, strictly increasing). Tables without a clipped plateau are returned unchanged.
    """
    values = list(sorted_values)
    n = len(values)
    if n < 20:
        return values
    top = values[-1]
    k = n - bisect_left(values, top)
    if k < 2 or top < ceiling:
        return values
    from statistics import NormalDist
    nd = NormalDist()
    lo = max(0, n - k - max(int(n * tail), 2 * k, 10))
    idx = range(lo, n - k)
    zs = [nd.inv_cdf((i + 0.5) / n) for i in idx]
    xs = [values[i] for i in idx]
    mz, mx = sum(zs) / len(zs), sum(xs) / len(xs)
    var = sum((z - mz) ** 2 for z in zs)
    slope = sum((z - mz) * (x - mx) for z, x in zip(zs, xs)) / var if var else 0.0
    out = values[: n - k]
    for i in range(n - k, n):
        value = max(mx + slope * (nd.inv_cdf((i + 0.5) / n) - mz), top)
        if out and value <= out[-1]:
            value = out[-1] + 0.01
        out.append(round(value, 3))
    return out


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


def _composite_parts(scalars: Mapping[str, float], input_tables: Mapping[str, list[float]],
                     trait: str) -> tuple[float, float] | None:
    """(composite, excess): the declared weighted mean of input percentiles inside the league range, and the same
    weighted mean of how far each input sits past the league's best or worst value (normal-score units)."""
    total = excess = weight_sum = 0.0
    for term, weight in ADAPTER_SPEC[trait]:
        pcts, beyond = [], []
        for input_id, outcome in _term_keys(term):
            key = f"{input_id}:{outcome}" if outcome else input_id
            if key in scalars and input_tables.get(key):
                pcts.append(_percentile(input_tables[key], scalars[key]))
                beyond.append(_excess_z(input_tables[key], scalars[key]))
        if pcts:
            total += weight * (sum(pcts) / len(pcts))
            excess += weight * (sum(beyond) / len(beyond))
            weight_sum += weight
    return (total / weight_sum, excess / weight_sum) if weight_sum else None


def _composite(scalars: Mapping[str, float], input_tables: Mapping[str, list[float]], trait: str) -> float | None:
    parts = _composite_parts(scalars, input_tables, trait)
    return parts[0] if parts else None


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
        target_tables[trait] = uncensor_top(sorted(targets))
    return FittedAdapter(input_tables, composite_tables, target_tables)


def derive_traits(inputs: Mapping[str, Any], fitted: FittedAdapter) -> dict[str, float]:
    """Derive all 15 legacy traits for one player from their input records."""
    scalars = _scalars_for_player(inputs, _definitions())
    out: dict[str, float] = {}
    for trait in LEGACY_TRAITS:
        parts = _composite_parts(scalars, fitted.input_tables, trait)
        target = fitted.target_tables[trait]
        if parts is None:
            out[trait] = round(_value_at(target, 0.5), 3)  # no usable inputs: league median, never a crash
            continue
        out[trait] = round(_trait_value(fitted.composite_tables[trait], target, *parts), 3)
    return out


def _trait_value(composites: list[float], target: list[float], composite: float, excess: float) -> float:
    """Composite -> trait. Inside the league's composite range: the target's value at the composite's percentile.
    Inputs past the league's ends move the composite along its own tail (excess tail-standard-deviations at the
    composite tail's rate); a composite past the league's ends continues the target's tail by the same number of
    tail-standard-deviations. Continuous everywhere, and exact for every league member (whose excess is 0)."""
    c_top, c_bottom = _tail_slopes(composites)
    if excess:
        composite += excess * (c_top if excess > 0 else c_bottom)
    if composites[0] <= composite <= composites[-1]:
        return _value_at(target, _percentile(composites, composite))
    end = composites[-1] if composite > composites[-1] else composites[0]
    base = _value_at(target, _percentile(composites, end))
    t_top, t_bottom = _tail_slopes(target)
    if composite > end:
        return base + (t_top * (composite - end) / c_top if c_top else 0.0)
    return base + (t_bottom * (composite - end) / c_bottom if c_bottom else 0.0)


def trait_input_weights(trait: str) -> dict[str, float]:
    """Each input's share of a trait (normalized). Used to route development deltas back onto inputs."""
    return dict(_trait_input_weights(trait))


@lru_cache(maxsize=None)
def _trait_input_weights(trait: str) -> dict[str, float]:
    # ADAPTER_SPEC is a module constant; an unknown trait raises KeyError on every call (not cached).
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
