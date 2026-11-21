"""Stage 1 ratings model: legacy traits derived from the 94 approved inputs.

Modes:
- "inputs_v1" (default since 2026-11-19): each player's 15 legacy traits are derived from their inputs by
  trait_adapter. Development (still produced as trait-delta events by the existing growth model) is routed onto
  the inputs, and the traits are re-derived, so displayed inputs and engine traits always agree.
- "legacy_traits": the older hand-built ratings, unchanged.

A save records its mode in save["meta"]["ratings_model"] (new saves: the default); a save without one predates the
94-input model and keeps the older ratings. Save-less tools (calibration report, betting-odds validation) use the
default unless the environment variable NBA_GM_RATINGS_MODEL names a mode (e.g. NBA_GM_RATINGS_MODEL=legacy_traits).
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
DEFAULT = INPUTS_V1
INPUTS_FILE = "data/canonical/player_inputs_2026_27.json"
MODEL_KEY = "_ratings_model"
# Development deltas are in trait points. Each movable input moves by the weighted mean of the deltas of the
# traits that use it (an unchanged trait counts as zero), times this many grade points per trait point.
# The routing keeps LEVELS: when every trait gains a point, every input gains the same amount. (It used to split
# each trait's delta across its inputs, so +1 on all 15 traits added ~+0.2 to a typical input and young players
# barely grew in the new ratings.) The value makes a uniform one-point gain move the card overall by about as much
# as in the legacy ratings (median over real players), so both rating sets develop at the size the growth model
# was tuned for. Measured by scripts/research/prospect_realism_routing.py.
GRADE_POINTS_PER_TRAIT_POINT = 0.41
# Each input moves by its own league spread (DEV-CURVE, 2026-11-21). The constant above is the step for an input with
# the reference spread (the median technique grade's); an input with half that spread moves half as far. Physical
# capacity grades (conditioning, recovery, agility, speed) have a league spread of about 3-5 grade points against about
# 14 for a technique grade, so the same grade-point step moved them four times as far relative to the league, and a
# young player's stamina could jump 10+ points in one season. Spreads: scripts/research/dev_curve_spread.py.
INPUT_SPREAD_FILE = "data/canonical/development_input_spread.json"
# Involvement (T08, true usage share) follows offensive skill as a player develops. Real draftees' true usage rises
# a median +3 to +7 points from year 1 to year 4 (Basketball Index leaderboards, 2013-2022 classes) as their games
# grow; veterans' usage falls as their skills fade. Slope: league cross-section of measured true usage on the mean
# of the creation, shooting, finishing and pass-reading grade groups (567 players with measured usage, r = 0.74;
# scripts/research/prospect_realism.py involvement-slope). Only the part explained by skill moves; the rest of a
# player's involvement preference stays his own.
INVOLVEMENT_PER_SKILL_GRADE = 0.0093
INVOLVEMENT_SKILL_GROUPS = (
    tuple(f"S{n:02d}" for n in (16, 17, 18, 19, 20, 24)),      # creation
    tuple(f"S{n:02d}" for n in range(1, 10)),                  # shooting
    tuple(f"S{n:02d}" for n in range(10, 16)),                 # finishing
    tuple(f"F{n:02d}.recognition" for n in range(1, 10)),      # pass reading
)
INVOLVEMENT_BOUNDS = (0.05, 0.65)

# Large, immutable tables live here, not inside the canonical dict, because parts of the game deep-copy
# the active universe; the canonical only carries small cache keys plus developed players' inputs.
_INPUT_CACHE: dict[str, dict[str, dict[str, Any]]] = {}
_FITTED_CACHE: dict[tuple[str, str], FittedAdapter] = {}
_GENERATED_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
# (fitted key, player id, base-inputs identity, sorted input deltas) -> (base inputs, derived traits)
_DERIVED_CACHE: dict[tuple[Any, ...], tuple[dict[str, Any], dict[str, float]]] = {}
_DERIVED_CACHE_LIMIT = 50_000
_EFFECTIVE_CACHE: dict[tuple[Any, ...], tuple[dict[str, Any], dict[str, Any]]] = {}
_EFFECTIVE_CACHE_LIMIT = 8_192


def ratings_model_for(save: Mapping[str, Any] | None = None) -> str:
    """The rating set for a save, or for save-less tools (save=None: the scorecards, fit scripts).

    Every save created since the 94-input model existed records its set, so a save without one was made on the
    older ratings (or is a hand-built test league too small to fit the 94-input model on) and keeps them.
    Save-less tools measure the default set unless NBA_GM_RATINGS_MODEL names one.
    """
    fallback = DEFAULT if save is None else LEGACY
    mode = ((save or {}).get("meta") or {}).get("ratings_model") or os.environ.get("NBA_GM_RATINGS_MODEL") or fallback
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

    Technique grades and physical-capacity grades (speed, agility, strength, balance, vertical, conditioning,
    recovery) move: young players get stronger and better conditioned, veterans lose speed and burst. Body
    dimensions (height, wingspan, reach, mass), propensities and tendency mixes are not changed by growth.
    """
    weighted: dict[str, float] = {}
    for trait, delta in trait_deltas.items():
        try:
            weights = trait_input_weights(trait)
        except KeyError:
            continue
        for input_id, weight in weights.items():
            if _grade_field(input_id, inputs.get(input_id)):
                weighted[input_id] = weighted.get(input_id, 0.0) + float(delta) * weight
    totals = _input_trait_weight_totals()
    step = _development_steps()
    out = {input_id: step.get(input_id, GRADE_POINTS_PER_TRAIT_POINT) * value / totals[input_id]
           for input_id, value in weighted.items() if value and input_id not in DEVELOPS_LIKE}
    # Inputs outside the blended traits (or with only a token share in one) that the box score now reads develop
    # like their closest skill (DEVELOPS_LIKE), scaled to their own spread; strength and jump capacity follow a
    # physical trait's own curve.
    for input_id, like in DEVELOPS_LIKE.items():
        if like in out and _grade_field(input_id, inputs.get(input_id)):
            out[input_id] = (out[like] * step.get(input_id, GRADE_POINTS_PER_TRAIT_POINT)
                             / step.get(like, GRADE_POINTS_PER_TRAIT_POINT))
    for input_id, trait in DEVELOPS_WITH_TRAIT.items():
        delta = float(trait_deltas.get(trait) or 0.0)
        if not delta:
            continue
        if input_id in JUMP_CM_PER_GRADE_POINT and _jump_field(inputs.get(input_id)):
            out[input_id] = step.get(input_id, GRADE_POINTS_PER_TRAIT_POINT * JUMP_CM_PER_GRADE_POINT[input_id]) * delta
        elif _grade_field(input_id, inputs.get(input_id)):
            out[input_id] = step.get(input_id, GRADE_POINTS_PER_TRAIT_POINT) * delta
    involvement = _involvement_delta(inputs, out)
    if involvement:
        out["T08"] = involvement
    return out


_WEIGHT_TOTALS: dict[str, float] = {}
_STEPS: dict[str, float] | None = None


def _development_steps() -> dict[str, float]:
    """Grade points (cm for jump height) that one hidden-rating point of development moves each input: the constant
    step scaled by the input's league spread over the reference spread. Inputs missing from the table keep the
    constant."""
    global _STEPS
    if _STEPS is None:
        path = Path(__file__).resolve().parents[2] / INPUT_SPREAD_FILE
        try:
            table = json.loads(path.read_text())
        except (OSError, ValueError):
            table = None
        _STEPS = ({input_id: GRADE_POINTS_PER_TRAIT_POINT * float(sd) / float(table["reference"])
                   for input_id, sd in table["spread"].items()} if table else {})
    return _STEPS


def _input_trait_weight_totals() -> dict[str, float]:
    """Sum over all 15 traits of each input's share of the trait (the denominator of the level-keeping mean)."""
    if not _WEIGHT_TOTALS:
        from .trait_adapter import LEGACY_TRAITS
        for trait in LEGACY_TRAITS:
            for input_id, weight in trait_input_weights(trait).items():
                _WEIGHT_TOTALS[input_id] = _WEIGHT_TOTALS.get(input_id, 0.0) + weight
    return _WEIGHT_TOTALS


def _involvement_delta(inputs: Mapping[str, Any], grade_deltas: Mapping[str, float]) -> float:
    """Change in involvement (T08) implied by this development's change in offensive skill (see the slope note)."""
    record = inputs.get("T08") or {}
    if not isinstance(record.get("value"), dict) or "probability" not in record["value"]:
        return 0.0
    group_changes = []
    for group in INVOLVEMENT_SKILL_GROUPS:
        present = [i for i in group if _is_grade(inputs.get(i))]
        if present:
            group_changes.append(sum(grade_deltas.get(i, 0.0) for i in present) / len(present))
    if not group_changes:
        return 0.0
    return INVOLVEMENT_PER_SKILL_GRADE * sum(group_changes) / len(group_changes)


def _is_grade(record: Mapping[str, Any] | None) -> bool:
    value = (record or {}).get("value")
    return isinstance(value, dict) and "grade" in value and record.get("status") != "unknown"


# Development for inputs the box score reads that sit outside the 15 blended traits (they never changed over a career
# before 2026-11-19). Each follows the skill whose real aging it matches, measured on Basketball Index's year-to-year
# talent grades by age (output/unused-ratings-2/aging_curves.py, change per year in league standard deviations at
# 19-22 / 23-25 / 26-28 / 29-31 / 32+):
# - defensive rebounding (S30-S32) like offensive rebounding technique (S29): defensive rebounding talent
#   +.11/-.01/-.07/-.11/-.20 vs offensive +.10/+.01/-.06/-.08/-.18;
# - screen setting (S27) like screen-action reads (S28): screening talent +.05/+.03/+.08/-.03/-.02, an experience skill;
# - steal technique (S42, S43) like defensive anticipation (S41): steals per 75 +.09/.00/.00/-.05/+.01;
# - foul control (S45) like attention / responsibility (S44): fouls per 75 -.12/-.06/-.01/+.02/+.04 (fewer fouls while
#   young, slightly more late).
DEVELOPS_LIKE = {"S27": "S28", "S30": "S29", "S31": "S29", "S32": "S29", "S42": "S41", "S43": "S41", "S45": "S44"}
# Strength and jump capacity follow a physical rating's own curve, the same curves physical_evidence uses to age the
# NBA Draft Combine tests: jumping the athletic one (foot speed and agility, declining from about 28), strength the
# general one (declining from about 30).
DEVELOPS_WITH_TRAIT = {"P10": "foot_speed_lateral_agility", "P08": "rim_deterrence"}
# Jump capacity is stored in cm: one grade point of a physical capacity is this many cm of standing jump (league spread
# of standing jump height, 5.28 cm, over league spread of the acceleration grade P05, 4.05; 691 players).
JUMP_CM_PER_GRADE_POINT = {"P10": 1.30}


def _jump_field(record: Mapping[str, Any] | None) -> bool:
    value = (record or {}).get("value")
    return (isinstance(value, dict) and bool(value.get("measurements")) and record.get("status") != "unknown"
            and value["measurements"][0].get("metric") == "jump_height")


# Body dimensions are fixed for development purposes; the other physical families are trainable capacities.
BODY_DIMENSIONS = frozenset({"P01", "P02", "P03", "P04"})


def _grade_field(input_id: str, record: Mapping[str, Any] | None) -> str | None:
    """Which stored grade development moves for this input: a technique "grade", a physical capacity's
    "display_grade" (the value the adapter and the player card read), or None (not moved)."""
    if _is_grade(record):
        return "grade"
    value = (record or {}).get("value")
    if (str(input_id)[:1] == "P" and input_id not in BODY_DIMENSIONS and isinstance(value, dict)
            and isinstance(value.get("display_grade"), dict) and "grade" in value["display_grade"]
            and record.get("status") != "unknown"):
        return "display_grade"
    return None


def apply_input_deltas(inputs: Mapping[str, Any], deltas: Mapping[str, float]) -> dict[str, Any]:
    """Return new input records with grade deltas applied. Grades keep a floor at 0 but have no top (AGENTS.md rule 3,
    no clipping at 100: a star who keeps improving can pass today's best grade, and the rating maps continue past the
    league's best); involvement (T08) moves within INVOLVEMENT_BOUNDS."""
    out = dict(inputs)
    for input_id, delta in deltas.items():
        record = out.get(input_id)
        if input_id == "T08" and delta and isinstance((record or {}).get("value"), dict) and "probability" in record["value"]:
            low, high = INVOLVEMENT_BOUNDS
            current = float(record["value"]["probability"])
            # Bound the move only; a value already outside the bounds is never pushed across them.
            moved = min(max(current + delta, min(low, current)), max(high, current))
            out[input_id] = {**record, "value": {**record["value"], "probability": round(moved, 6)}}
            continue
        if input_id in JUMP_CM_PER_GRADE_POINT and delta and _jump_field(record):
            first = record["value"]["measurements"][0]
            moved = {**first, "value": round(max(0.0, float(first["value"]) + delta), 3)}
            if isinstance(first.get("interval"), list):
                moved["interval"] = [round(max(0.0, float(v) + delta), 3) for v in first["interval"]]
            out[input_id] = {**record, "value": {**record["value"], "measurements": [moved, *record["value"]["measurements"][1:]]}}
            continue
        field = _grade_field(input_id, record)
        if not field or not delta:
            continue
        if field == "grade":
            grade = max(0.0, float(record["value"]["grade"]) + delta)
            out[input_id] = {**record, "value": {**record["value"], "grade": round(grade, 3)}}
        else:
            display = record["value"]["display_grade"]
            grade = max(0.0, float(display["grade"]) + delta)
            out[input_id] = {**record, "value": {**record["value"], "display_grade": {**display, "grade": round(grade, 3)}}}
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


# Player fields input_estimator never reads (checked: no estimator path touches them).
_ESTIMATOR_IGNORED_PLAYER_KEYS = frozenset({"_save_stats"})


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
        # Keyed on everything the estimator could read. The season stats the save attaches to each player
        # (_save_stats) change after every game and are never read by the estimator; keying on them re-estimated
        # every generated player on every league rebuild (a quarter of a month's extra time in an aged league)
        # and grew this cache without bound.
        definition = {k: v for k, v in player.items() if k not in _ESTIMATOR_IGNORED_PLAYER_KEYS}
        key = hashlib.sha256(json.dumps([definition, traits], sort_keys=True, default=str).encode()).hexdigest()
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
    if not deltas:
        return base
    # apply_input_deltas is a pure function of (base inputs, deltas). Base and generated records are cached for the
    # process and never edited (the result is already shared like the base when a player has no deltas), so the
    # result is kept per (base object, delta values) and handed out again. Callers only read these records.
    key = (player_id, tuple(deltas.items()))
    cached = _EFFECTIVE_CACHE.get(key)
    if cached is None or cached[0] is not base:
        cached = (base, apply_input_deltas(base, deltas))
        if len(_EFFECTIVE_CACHE) >= _EFFECTIVE_CACHE_LIMIT:
            _EFFECTIVE_CACHE.pop(next(iter(_EFFECTIVE_CACHE)))
        _EFFECTIVE_CACHE[key] = cached
    return cached[1]


def _rederive(canonical: dict[str, Any], player_ids: Iterable[str]) -> dict[str, dict[str, float]]:
    model = canonical[MODEL_KEY]
    fitted = _FITTED_CACHE[tuple(model["fitted_key"])]
    derived: dict[str, dict[str, float]] = {}
    fitted_key = tuple(model["fitted_key"])
    for pid in {str(p) for p in player_ids}:
        base = _player_base_inputs(model, pid)
        if base is None:
            continue
        # derive_traits is a pure function of (base inputs, this save's deltas, fitted tables). Base and
        # generated input records are cached for the process and never edited, so reuse by identity is exact.
        deltas = (model.get("input_deltas") or {}).get(pid)
        key = (fitted_key, pid, id(base), tuple(sorted(deltas.items())) if deltas else None)
        cached = _DERIVED_CACHE.get(key)
        if cached is None or cached[0] is not base:
            cached = (base, derive_traits(apply_input_deltas(base, deltas) if deltas else base, fitted))
            if len(_DERIVED_CACHE) >= _DERIVED_CACHE_LIMIT:
                _DERIVED_CACHE.pop(next(iter(_DERIVED_CACHE)))
            _DERIVED_CACHE[key] = cached
        derived[pid] = dict(cached[1])
    for trait in canonical.get("traits", []):
        values = derived.get(trait.get("player_id"))
        if values and trait.get("trait_key") in values:
            trait["value"] = values[trait["trait_key"]]
    canonical.pop("_trait_values_by_player", None)
    return derived


_ROUTED_CACHE: dict[tuple[Any, ...], tuple[Mapping[str, Any], dict[str, float]]] = {}


def _routed_deltas(base: Mapping[str, Any], trait_deltas: Mapping[str, float]) -> dict[str, float]:
    """route_trait_deltas for a cached (never edited) base record set, kept per (base object, trait deltas).

    Every league rebuild replays the whole season's development for every player; the routing of the same totals
    onto the same base inputs gives the same grade deltas each time."""
    key = (id(base), tuple(trait_deltas.items()))
    cached = _ROUTED_CACHE.get(key)
    if cached is None or cached[0] is not base:
        cached = (base, route_trait_deltas(base, trait_deltas))
        if len(_ROUTED_CACHE) >= _EFFECTIVE_CACHE_LIMIT:
            _ROUTED_CACHE.pop(next(iter(_ROUTED_CACHE)))
        _ROUTED_CACHE[key] = cached
    return cached[1]


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
        for input_id, delta in _routed_deltas(base, trait_deltas).items():
            accumulated[input_id] = round(accumulated.get(input_id, 0.0) + delta, 6)
        touched.append(pid)
    _rederive(canonical, touched)


def uses_inputs_model(canonical: Mapping[str, Any]) -> bool:
    return (canonical.get(MODEL_KEY) or {}).get("mode") == INPUTS_V1


def effective_inputs(canonical: Mapping[str, Any], player_id: str) -> dict[str, Any] | None:
    """The inputs the engine is currently using for a player (for the new player card)."""
    model = canonical.get(MODEL_KEY) or {}
    return _effective(model, player_id) if model else None
