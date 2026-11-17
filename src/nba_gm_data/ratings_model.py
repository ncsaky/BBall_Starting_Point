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


def _trait_values(canonical: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for trait in canonical.get("traits", []):
        if trait.get("value") is not None:
            out.setdefault(trait["player_id"], {})[trait["trait_key"]] = float(trait["value"])
    return out


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
    """Fit the adapter on the baseline league and derive every input-backed player's traits.

    Must run on the baseline (pre-development) traits: the fitted league tables then stay fixed for the
    whole save, so a player's ratings never drift because other players developed.
    """
    inputs_key, league_inputs = _load_inputs_keyed(root)
    baseline = _trait_values(canonical)
    signature = hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()
    fitted_key = (inputs_key, signature)
    if fitted_key not in _FITTED_CACHE:
        _FITTED_CACHE[fitted_key] = fit_adapter({pid: ins for pid, ins in league_inputs.items() if pid in baseline}, baseline)
    canonical[MODEL_KEY] = {"mode": INPUTS_V1, "inputs_key": inputs_key, "fitted_key": list(fitted_key),
                            "effective_inputs": {}}
    derived_baseline = _rederive(canonical, league_inputs.keys())
    _rebase_offensive_profile_anchors(canonical, derived_baseline)


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


def _rederive(canonical: dict[str, Any], player_ids: Iterable[str]) -> dict[str, dict[str, float]]:
    model = canonical[MODEL_KEY]
    fitted = _FITTED_CACHE[tuple(model["fitted_key"])]
    base = _base_inputs(model)
    wanted = {str(p) for p in player_ids}
    derived: dict[str, dict[str, float]] = {}
    for pid in wanted:
        inputs = model["effective_inputs"].get(pid) or base.get(pid)
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
    combined = _sum_trait_deltas(totals, events)
    touched = []
    base = _base_inputs(model)
    for pid, trait_deltas in combined.items():
        current = model["effective_inputs"].get(pid) or base.get(pid)
        if current is None:
            continue
        model["effective_inputs"][pid] = apply_input_deltas(current, route_trait_deltas(current, trait_deltas))
        touched.append(pid)
    _rederive(canonical, touched)


def uses_inputs_model(canonical: Mapping[str, Any]) -> bool:
    return (canonical.get(MODEL_KEY) or {}).get("mode") == INPUTS_V1


def effective_inputs(canonical: Mapping[str, Any], player_id: str) -> dict[str, Any] | None:
    """The inputs the engine is currently using for a player (for the new player card)."""
    model = canonical.get(MODEL_KEY) or {}
    if not model:
        return None
    return (model.get("effective_inputs") or {}).get(player_id) or _base_inputs(model).get(player_id)
