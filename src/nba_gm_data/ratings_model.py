"""Opt-in Stage 1 ratings model: legacy traits derived from the 94 approved inputs.

Modes:
- "legacy_traits" (default): unchanged behavior.
- "inputs_v1": each player's 15 legacy traits are derived from their inputs by trait_adapter. Development
  (still produced as trait-delta events by the existing growth model) is routed onto the inputs, and the
  traits are re-derived, so displayed inputs and engine traits always agree.

A save opts in with save["meta"]["ratings_model"] = "inputs_v1". Save-less tools (calibration report,
betting-odds validation) can opt in with the environment variable NBA_GM_RATINGS_MODEL=inputs_v1.
Players without input records (e.g. newly generated draftees, until Stage 1 F) keep their legacy traits.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from .trait_adapter import FittedAdapter, derive_traits, fit_adapter, trait_input_weights

LEGACY = "legacy_traits"
INPUTS_V1 = "inputs_v1"
MODES = (LEGACY, INPUTS_V1)
INPUTS_FILE = "data/canonical/player_inputs_2026_27.json"
MODEL_KEY = "_ratings_model"
# Development deltas are in trait points; one trait point maps to this many input grade points per unit of
# that input's share of the trait. 1.0 keeps a growth event's size on the same 0-100 scale.
GRADE_POINTS_PER_TRAIT_POINT = 1.0

# Large, immutable tables live here, not inside the canonical dict, because parts of the game deep-copy
# the active universe; the canonical only carries small cache keys plus developed players' inputs.
_INPUT_CACHE: dict[str, dict[str, dict[str, Any]]] = {}
_FITTED_CACHE: dict[tuple[str, str], FittedAdapter] = {}
_GENERATED_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def ratings_model_for(save: Mapping[str, Any] | None = None) -> str:
    mode = ((save or {}).get("meta") or {}).get("ratings_model") or os.environ.get("NBA_GM_RATINGS_MODEL") or LEGACY
    if mode not in MODES:
        raise ValueError(f"Unknown ratings model {mode!r}; expected one of {MODES}")
    return mode


def _inputs_path(root: Path | None = None) -> Path:
    """The uncompressed build output if present, otherwise the git-tracked .json.gz copy."""
    if root is None:
        from .resource_paths import game_resource_root
        root = game_resource_root()
    path = Path(root) / INPUTS_FILE
    compressed = path.with_name(path.name + ".gz")
    return path if path.exists() or not compressed.exists() else compressed


def _load_inputs_keyed(root: Path | None = None) -> tuple[str, dict[str, dict[str, Any]]]:
    path = _inputs_path(root)
    key = str(path.resolve())
    if key not in _INPUT_CACHE:
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing; build it with scripts/build_player_inputs.py")
        if path.suffix == ".gz":
            import gzip
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                section = json.load(handle)
        else:
            section = json.loads(path.read_text())
        _INPUT_CACHE[key] = {pid: doc["inputs"] for pid, doc in section["players"].items()}
    return key, _INPUT_CACHE[key]


def load_league_inputs(root: Path | None = None) -> dict[str, dict[str, Any]]:
    """player_id -> {input_id: record}, read once per file."""
    return _load_inputs_keyed(root)[1]


def _trait_values(canonical: Mapping[str, Any], *, skip_placeholders: bool = False) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for trait in canonical.get("traits", []):
        if trait.get("value") is None or (skip_placeholders and is_placeholder_trait(trait)):
            continue
        out.setdefault(trait["player_id"], {})[trait["trait_key"]] = float(trait["value"])
    return out


def is_placeholder_trait(trait: Mapping[str, Any]) -> bool:
    """A legacy trait filled with the flat 50.0 default because its source stats were all missing.

    About 1,100 legacy cells (mostly two-way and deep-bench players) are exactly 50.0 with every source
    component empty. They carry no evidence; if they shaped the adapter's target distribution, everyone whose
    inputs rank between roughly the 20th and 36th percentile would collapse onto the same 50.0 value.
    """
    if trait.get("value") != 50.0:
        return False
    detail = trait.get("components")
    parts = detail.get("components") if isinstance(detail, dict) else None
    return isinstance(parts, list) and bool(parts) and all(part is None for part in parts)


def route_trait_deltas(inputs: Mapping[str, Any], trait_deltas: Mapping[str, float]) -> dict[str, float]:
    """Spread trait-point deltas onto the grade inputs behind each trait, by adapter weight.

    Only grade-kind inputs move: measurements (height, wingspan), propensities and tendency mixes are not
    changed by the legacy growth model.
    """
    out: dict[str, float] = {}
    for trait, delta in trait_deltas.items():
        try:
            weights = trait_input_weights(trait)
        except KeyError:
            continue
        movable = {i: w for i, w in weights.items() if _is_grade(inputs.get(i))}
        total = sum(movable.values())
        if not total:
            continue
        for input_id, weight in movable.items():
            out[input_id] = out.get(input_id, 0.0) + float(delta) * GRADE_POINTS_PER_TRAIT_POINT * weight / total
    return out


def _is_grade(record: Mapping[str, Any] | None) -> bool:
    value = (record or {}).get("value")
    return isinstance(value, dict) and "grade" in value and record.get("status") != "unknown"


def apply_input_deltas(inputs: Mapping[str, Any], deltas: Mapping[str, float]) -> dict[str, Any]:
    """Return new input records with grade deltas applied. Grades stay within 0-100 (the schema range)."""
    out = dict(inputs)
    for input_id, delta in deltas.items():
        record = out.get(input_id)
        if not _is_grade(record) or not delta:
            continue
        grade = max(0.0, min(100.0, float(record["value"]["grade"]) + delta))
        out[input_id] = {**record, "value": {**record["value"], "grade": round(grade, 3)}}
    return out


def _sum_trait_deltas(totals: Mapping[str, Mapping[str, float]] | None,
                      events: Iterable[Mapping[str, Any]] | None) -> dict[str, dict[str, float]]:
    combined: dict[str, dict[str, float]] = {
        str(pid): {str(k): float(v or 0.0) for k, v in values.items()} for pid, values in (totals or {}).items()
    }
    for event in events or []:
        pid = str(event.get("player_id"))
        for trait, delta in (event.get("trait_deltas") or {}).items():
            combined.setdefault(pid, {})[trait] = combined.get(pid, {}).get(trait, 0.0) + float(delta)
    return combined


def install_inputs_model(canonical: dict[str, Any], root: Path | None = None) -> None:
    """Fit the adapter on the baseline league and derive every player's traits from inputs.

    Must run on the baseline (pre-development) traits. The adapter is fitted only on players in the
    canonical inputs file, so its league tables stay fixed for the whole save (rookies joining or players
    developing never shift anyone else's ratings). Players without canonical inputs (drafted rookies,
    generated players) get inputs from the estimator's prospect path, using their current legacy traits only
    as weak prior evidence; their traits are then derived from those inputs like everyone else's.
    """
    inputs_key, league_inputs = _load_inputs_keyed(root)
    baseline = _trait_values(canonical)
    # The adapter's target distributions come from evidence-backed legacy values only (placeholders excluded).
    evidence_traits = _trait_values(canonical, skip_placeholders=True)
    fit_traits = {pid: values for pid, values in evidence_traits.items() if pid in league_inputs}
    signature = hashlib.sha256(json.dumps(fit_traits, sort_keys=True).encode()).hexdigest()
    fitted_key = (inputs_key, signature)
    if fitted_key not in _FITTED_CACHE:
        _FITTED_CACHE[fitted_key] = fit_adapter({pid: league_inputs[pid] for pid in fit_traits}, fit_traits)
    canonical[MODEL_KEY] = {"mode": INPUTS_V1, "inputs_key": inputs_key, "fitted_key": list(fitted_key),
                            "input_deltas": {}, "generated": {}}
    generated = _install_generated_players(canonical, baseline, league_inputs, root)
    derived_baseline = _rederive(canonical, [*league_inputs.keys(), *generated])
    _rebase_offensive_profile_anchors(canonical, derived_baseline)
    # Player value (overall / offense / defense) from the hidden ratings fitted to real impact; see impact_value.
    from .impact_value import install_summary_tables
    install_summary_tables(canonical, root)


_SCALE_MAP_CACHE: dict[str, Any] = {}


def _scale_map(root: Path | None) -> dict[str, Any] | None:
    from .bbi_evidence import load_scale_map
    base = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    key = str(base)
    if key not in _SCALE_MAP_CACHE:
        _SCALE_MAP_CACHE[key] = load_scale_map(base)
    return _SCALE_MAP_CACHE[key]


def _install_generated_players(canonical: dict[str, Any], baseline: Mapping[str, Mapping[str, float]],
                               league_inputs: Mapping[str, Any], root: Path | None = None) -> list[str]:
    """Estimate inputs for players missing from the canonical inputs file (e.g. drafted rookies)."""
    from .input_estimator import InputEstimator

    model = canonical[MODEL_KEY]
    estimator = None
    added = []
    for player in canonical.get("players", []):
        pid = str(player.get("id") or "")
        if not pid or pid in league_inputs or pid not in baseline:
            continue
        traits = dict(baseline[pid])
        key = hashlib.sha256(json.dumps([player, traits], sort_keys=True, default=str).encode()).hexdigest()
        if (pid, key) not in _GENERATED_CACHE:
            estimator = estimator or InputEstimator()
            estimated = estimator.estimate_player_inputs(player, traits, prospect=True).to_dict()["inputs"]
            # League inputs carry measured scales for the action mix and involvement; put rookies on the same scales.
            scale_map = _scale_map(root)
            if scale_map:
                from .bbi_evidence import map_tendency_inputs
                map_tendency_inputs(estimated, scale_map)
            _GENERATED_CACHE[(pid, key)] = estimated
        model["generated"][pid] = key
        added.append(pid)
    return added


def _rebase_offensive_profile_anchors(canonical: dict[str, Any], derived: Mapping[str, Mapping[str, float]]) -> None:
    """Re-anchor observed offensive profiles to the input-derived baseline traits.

    offense.offensive_profile starts from a player's frozen observed rates (e.g. threes per 36) and adjusts by
    each trait's change since its "anchor" value. Anchors were legacy trait values; switching models would
    otherwise read as instant development and distort real observed volumes. After rebasing, only genuine
    development (change from the derived baseline) moves the observed rates. The meta dict is copied so a
    shared canonical universe is never mutated.
    """
    meta = canonical.get("meta") or {}
    profiles = meta.get("offensive_profiles")
    if not profiles:
        return
    rebased = {}
    for pid, profile in profiles.items():
        anchors = profile.get("anchors") if isinstance(profile, dict) else None
        values = derived.get(pid)
        if anchors and values:
            profile = {**profile, "anchors": {k: values.get(k, v) for k, v in anchors.items()}}
        rebased[pid] = profile
    canonical["meta"] = {**meta, "offensive_profiles": rebased}


def _base_inputs(model: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return _INPUT_CACHE[model["inputs_key"]]


def _player_base_inputs(model: Mapping[str, Any], player_id: str) -> dict[str, Any] | None:
    base = _base_inputs(model).get(player_id)
    if base is not None:
        return base
    key = (model.get("generated") or {}).get(player_id)
    return _GENERATED_CACHE.get((player_id, key)) if key else None


def _effective(model: Mapping[str, Any], player_id: str) -> dict[str, Any] | None:
    """Base (or generated) inputs plus this save's accumulated development, computed on demand.

    Only the small per-input deltas live in the active universe, which gets deep-copied by parts of the game.
    """
    base = _player_base_inputs(model, player_id)
    if base is None:
        return None
    deltas = (model.get("input_deltas") or {}).get(player_id)
    return apply_input_deltas(base, deltas) if deltas else base


def _rederive(canonical: dict[str, Any], player_ids: Iterable[str]) -> dict[str, dict[str, float]]:
    model = canonical[MODEL_KEY]
    fitted = _FITTED_CACHE[tuple(model["fitted_key"])]
    derived: dict[str, dict[str, float]] = {}
    for pid in {str(p) for p in player_ids}:
        inputs = _effective(model, pid)
        if inputs is not None:
            derived[pid] = derive_traits(inputs, fitted)
    for trait in canonical.get("traits", []):
        values = derived.get(trait.get("player_id"))
        if values and trait.get("trait_key") in values:
            trait["value"] = values[trait["trait_key"]]
    canonical.pop("_trait_values_by_player", None)
    return derived


def apply_development(canonical: dict[str, Any], totals: Mapping[str, Mapping[str, float]] | None,
                      events: Iterable[Mapping[str, Any]] | None) -> None:
    """Inputs-model replacement for the legacy development-to-traits helpers."""
    model = canonical[MODEL_KEY]
    touched = []
    for pid, trait_deltas in _sum_trait_deltas(totals, events).items():
        base = _player_base_inputs(model, pid)
        if base is None:
            continue
        accumulated = model["input_deltas"].setdefault(pid, {})
        for input_id, delta in route_trait_deltas(base, trait_deltas).items():
            accumulated[input_id] = round(accumulated.get(input_id, 0.0) + delta, 6)
        touched.append(pid)
    _rederive(canonical, touched)


def uses_inputs_model(canonical: Mapping[str, Any]) -> bool:
    return (canonical.get(MODEL_KEY) or {}).get("mode") == INPUTS_V1


def effective_inputs(canonical: Mapping[str, Any], player_id: str) -> dict[str, Any] | None:
    """The inputs the engine is currently using for a player (for the new player card)."""
    model = canonical.get(MODEL_KEY) or {}
    return _effective(model, player_id) if model else None
