"""Player value from the engine's hidden ratings, fitted to real impact (new-ratings mode).

The legacy overall/offense/defense summary is a hand-weighted skill average: no rebounding, defense 60%
perimeter mobility. Honest input-derived ratings exposed that it ranks big men far too low (Gobert ~250th).
This module predicts offensive and defensive impact per 100 possessions (Basketball Index multi-year
O-/D-LEBRON, fitted by scripts/fit_impact_value.py) from the same 15 hidden ratings plus height, then maps each
prediction onto the EXISTING summary scale by league rank. Who ranks where comes from the fit; the spread of
values is unchanged, so every AI cutoff written for the old scale keeps working. Ratings themselves are not
changed (ratings-first rule); only how the engine values them.
"""
from __future__ import annotations

import bisect
import json
from pathlib import Path
from typing import Any, Mapping

from .trait_adapter import LEGACY_TRAITS

FIT_FILE = "data/canonical/impact_value_fit.json"
PROFILE_PREDICTORS = ("three_per36", "three_pct", "two_pct", "ft_pct")
# Grouped technique grades and involvement from the 94 inputs: the 15 hidden ratings saturate for star guards
# (several sit at the 96th-100th percentile), so the inputs' finer detail is what separates them.
INPUT_GROUPS = {
    "in_shooting": [f"S{n:02d}" for n in range(1, 10)],
    "in_finishing": [f"S{n:02d}" for n in range(10, 16)],
    "in_creation": [f"S{n:02d}" for n in (16, 17, 18, 19, 20, 24)],
    "in_post": ["S21", "S22", "S23"],
    "in_offball": [f"S{n:02d}" for n in range(25, 29)],
    "in_rebounding": [f"S{n:02d}" for n in range(29, 33)],
    "in_defense": [f"S{n:02d}" for n in range(33, 47)],
    "in_pass_reading": [f"F{n:02d}.recognition" for n in range(1, 10)],
}
BODY_PREDICTORS = ("height_inches", "weight_lbs", "wingspan_inches")   # fixed body measures (sign-free in the fit)
# Involvement pays off in proportion to the skill and efficiency behind it. A purely additive fit gave every heavy-usage
# player the same credit for usage, so it under-predicted the stars' offense (Brunson O-LEBRON +4.97 predicted +3.14,
# Gilgeous-Alexander +6.06 -> +4.98) and over-credited heavy-usage scorers whose real impact is modest. Each term is
# involvement (T08 share) times the skill's distance from a fixed centre, so with non-negative weights a better skill
# never lowers value, while more involvement with below-average skill can (2026-11-18 ratings audit).
INTERACTIONS = {"in_shooting": (50.0, 10.0), "in_creation": (50.0, 10.0), "in_finishing": (50.0, 10.0), "two_pct": (0.52, 0.04)}
# Offensive rebounding on its real production scale (offensive rebounds per 75 implied by the offensive_rebounding
# rating's league rank; knots fitted by scripts/fit_offensive_rebounding.py). On the rating's own rank scale the top
# crashers (5-8 per 75) sit a few points above good-not-elite rebounders (3 per 75), so a linear fit could not credit
# what the extra possessions are worth: energy bigs (Diabate, Queta, Kornet) were predicted well below their own
# O-LEBRON (2026-11-18 energy-bigs task). Offensive rebounding is offense only: the fit holds the defensive weight of
# both the rating and its production scale at zero (the rating is mostly how often a player crashes, which is not a
# defensive skill; left free, it picked up defensive weight as a stand-in for "plays center").
ORB_SCALE_FILE = "data/canonical/offensive_rebound_scale.json"
OFFENSE_ONLY = ("offensive_rebounding", "orb_per75")
PREDICTORS = [*LEGACY_TRAITS, *BODY_PREDICTORS, *PROFILE_PREDICTORS, *INPUT_GROUPS, "in_involvement",
              *(f"involvement_x_{name}" for name in INTERACTIONS), "orb_per75"]
TABLE_KEY = "_impact_value_tables"
_FIT_CACHE: dict[str, Any] = {}
_DEFAULT_ROOT: Path | None = None
_ORB_KNOTS: list[list[float]] | None = None


def orb_per75(rating: float) -> float:
    """Offensive rebounds per 75 implied by the offensive_rebounding rating (piecewise linear between the fitted knots;
    beyond the ends the end segments continue, so the top keeps separating and nothing is clipped)."""
    global _ORB_KNOTS
    if _ORB_KNOTS is None:
        path = Path(__file__).resolve().parents[2] / ORB_SCALE_FILE
        # The knots ship with the repo; a straight line through the league's typical range keeps a stripped checkout
        # working (rating 0 -> 0.3 per 75, rating 100 -> 6.5 per 75).
        _ORB_KNOTS = json.loads(path.read_text())["knots"] if path.exists() else [[0.0, 0.3], [100.0, 6.5]]
    knots = _ORB_KNOTS
    if rating <= knots[0][0]:
        (x0, y0), (x1, y1) = knots[0], knots[1]
    elif rating >= knots[-1][0]:
        (x0, y0), (x1, y1) = knots[-2], knots[-1]
    else:
        i = bisect.bisect_left([k[0] for k in knots], rating)
        (x0, y0), (x1, y1) = knots[i - 1], knots[i]
    return y0 + (y1 - y0) * (rating - x0) / (x1 - x0)


_PROFILE_DEFAULTS = {"three_per36": 3.0, "three_pct": 0.34, "two_pct": 0.52, "ft_pct": 0.76}


# input_features is read for every player in every game, valuation and summary. The records handed out by
# ratings_model are shared, read-only objects, so the features are kept per record object (by identity, holding a
# reference so the id stays unique; bounded, oldest first). A copy is returned, so callers can never edit the cache.
_FEATURE_CACHE: dict[int, tuple[Mapping[str, Any], tuple[float, ...]]] = {}
_FEATURE_CACHE_LIMIT = 4096


def input_features(inputs: Mapping[str, Any] | None) -> list[float]:
    """Mean technique grade per group plus involvement (T08); league-typical values when inputs are missing."""
    if inputs is None:
        return _input_features(inputs)
    cached = _FEATURE_CACHE.get(id(inputs))
    if cached is None or cached[0] is not inputs:
        cached = (inputs, tuple(_input_features(inputs)))
        if len(_FEATURE_CACHE) >= _FEATURE_CACHE_LIMIT:
            _FEATURE_CACHE.pop(next(iter(_FEATURE_CACHE)))
        _FEATURE_CACHE[id(inputs)] = cached
    return list(cached[1])


def _input_features(inputs: Mapping[str, Any] | None) -> list[float]:
    out = []
    for ids in INPUT_GROUPS.values():
        grades = [float(inputs[i]["value"]["grade"]) for i in ids
                  if inputs and isinstance((inputs.get(i) or {}).get("value"), dict) and "grade" in inputs[i]["value"]]
        out.append(sum(grades) / len(grades) if grades else 50.0)
    try:
        out.append(float(inputs["T08"]["value"]["probability"]))
    except (KeyError, TypeError, ValueError):
        out.append(0.45)
    return out


def predictor_row(traits: Mapping[str, float], player: Mapping[str, Any],
                  profile: Mapping[str, float] | None = None, inputs: Mapping[str, Any] | None = None) -> list[float]:
    """Hidden ratings, height, the engine's shooting profile (observed make rates and three-point volume,
    adjusted by development) and grouped input grades - the same player the game sim plays with."""
    row = [float(traits.get(trait, 50.0)) for trait in LEGACY_TRAITS]
    height = float(player.get("height_inches") or 78.0)
    row.append(height)
    row.append(float(player.get("weight_lbs") or (215.0 + (height - 78.0) * 7.0)))
    row.append(float(player.get("wingspan_inches") or (height + 3.0)))
    profile = profile or {}
    row.extend(float(profile.get(key, default)) for key, default in _PROFILE_DEFAULTS.items())
    row.extend(input_features(inputs))
    named = dict(zip(PREDICTORS, row))
    involvement = named["in_involvement"]
    row.extend(involvement * (named[name] - centre) / scale for name, (centre, scale) in INTERACTIONS.items())
    row.append(orb_per75(named["offensive_rebounding"]))
    return row


def load_fit(root: Path | None = None) -> dict[str, Any] | None:
    if root is None:
        global _DEFAULT_ROOT
        if _DEFAULT_ROOT is None:
            _DEFAULT_ROOT = Path(__file__).resolve().parents[2]
        root = _DEFAULT_ROOT
    key = str(Path(root) / FIT_FILE)
    if key not in _FIT_CACHE:
        path = Path(key)
        _FIT_CACHE[key] = json.loads(path.read_text()) if path.exists() else None
    return _FIT_CACHE[key]


def predict(fit: Mapping[str, Any], traits: Mapping[str, float], player: Mapping[str, Any],
            profile: Mapping[str, float] | None = None, inputs: Mapping[str, Any] | None = None) -> dict[str, float]:
    row = predictor_row(traits, player, profile, inputs)
    out = {}
    for side in ("offense", "defense"):
        c = fit["coefficients"][side]
        out[side] = c["intercept"] + sum(w * (v - m) / s for w, v, m, s in zip(c["weights"], row, c["mean"], c["sd"]))
    out["overall"] = out["offense"] + out["defense"]
    return out


def _pct(sorted_values: list[float], x: float) -> float:
    n = len(sorted_values)
    lo, hi = bisect.bisect_left(sorted_values, x), bisect.bisect_right(sorted_values, x)
    return ((lo + hi) / 2 + 0.5) / (n + 1)


def _value_at(sorted_values: list[float], u: float) -> float:
    n = len(sorted_values)
    pos = min(max(u * (n + 1) - 1.0, 0.0), n - 1.0)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def build_tables(predictions: Mapping[str, Mapping[str, float]], scale_values: Mapping[str, list[float]]) -> dict[str, Any]:
    """Source (predicted impact) and target (existing scale) distributions per key, fixed at the baseline."""
    tables = {}
    for key, target in scale_values.items():
        side = "overall" if key in ("overall", "on_court", "sim_impact") else key
        source = sorted(p[side] for p in predictions.values())
        tables[key] = {"side": side, "source": source, "target": sorted(target)}
    return tables


def mapped(tables: Mapping[str, Any], prediction: Mapping[str, float], key: str) -> float:
    """A prediction placed on the existing scale by its league rank (beyond the baseline range, the extremes)."""
    table = tables[key]
    return _value_at(table["target"], _pct(table["source"], prediction[table["side"]]))


def _profile(canonical: Mapping[str, Any], player: Mapping[str, Any], traits: Mapping[str, float]) -> Mapping[str, float]:
    from .offense import enabled as offense_enabled, offensive_profile
    return offensive_profile(canonical, player, traits) if offense_enabled(canonical) else {}


def _inputs(canonical: Mapping[str, Any], player: Mapping[str, Any]) -> Mapping[str, Any] | None:
    from .ratings_model import effective_inputs
    return effective_inputs(canonical, player["id"])


_TABLE_CACHE: dict[tuple, dict[str, Any]] = {}
_BUILDING = False


def _model(canonical: Mapping[str, Any]) -> Mapping[str, Any] | None:
    from .ratings_model import MODEL_KEY, INPUTS_V1
    model = canonical.get(MODEL_KEY)
    return model if isinstance(model, Mapping) and model.get("mode") == INPUTS_V1 else None


def install_summary_tables(canonical: dict[str, Any], root: Path | None = None) -> None:
    """Rank tables for the summary (overall / offense / defense), fixed at the league baseline (cached).

    Called by ratings_model.install_inputs_model after the baseline traits are derived. The target scale is
    the existing legacy summary formula's league distribution, so thresholds written for it stay valid."""
    global _BUILDING
    model = _model(canonical)
    fit = load_fit(root)
    if model is None or fit is None:
        return
    key = (tuple(model.get("fitted_key") or ()), fit.get("version"))
    if key not in _TABLE_CACHE:
        from .save import _uncached_player_attribute_summary, trait_values_by_player
        traits = trait_values_by_player(canonical)
        players = [p for p in canonical.get("players", []) if p.get("id") in traits]
        _BUILDING = True
        try:
            summaries = {p["id"]: _uncached_player_attribute_summary(canonical, p["id"]) for p in players}
        finally:
            _BUILDING = False
        predictions = {p["id"]: predict(fit, traits[p["id"]], p, _profile(canonical, p, traits[p["id"]]), _inputs(canonical, p))
                       for p in players}
        scales = {k: [s[k] for s in summaries.values() if k in s] for k in ("overall", "offense", "defense")}
        # The game sim's own player impact feature (sim.player_impact_score), same baseline players: its league
        # distribution is the target scale for sim_impact, so team-strength calibrations keep their meaning.
        from .sim import player_impact_score
        from .talent import enabled as talent_enabled
        role_aware = talent_enabled(canonical)
        scales["sim_impact"] = [player_impact_score(lambda k, t=traits[p["id"]]: float(t.get(k, 50.0)), p.get("position"),
                                                    role_aware=role_aware) for p in players]
        _TABLE_CACHE[key] = build_tables(predictions, {k: v for k, v in scales.items() if v})
    model["impact_tables_key"] = list(key[0]) + [key[1]]
    canonical.pop("_trait_values_by_player", None)


def summary_override(canonical: Mapping[str, Any], player: Mapping[str, Any], traits: Mapping[str, float],
                     profile: Mapping[str, float] | None = None) -> dict[str, float] | None:
    """Overall / offense / defense on the existing scale from fitted impact, in new-ratings mode only."""
    if _BUILDING:
        return None
    model = _model(canonical)
    if model is None or not model.get("impact_tables_key") or not traits:
        return None
    key_list = model["impact_tables_key"]
    tables = _TABLE_CACHE.get((tuple(key_list[:-1]), key_list[-1]))
    fit = load_fit()
    if tables is None or fit is None:
        return None
    prediction = predict(fit, traits, player, profile if profile is not None else _profile(canonical, player, traits),
                         _inputs(canonical, player))
    return {key: round(mapped(tables, prediction, key), 1) for key in tables}


def sim_impact(canonical: Mapping[str, Any], player: Mapping[str, Any], traits: Mapping[str, float],
               profile: Mapping[str, float] | None = None) -> float | None:
    """The game sim's player impact in new-ratings mode: fitted real impact placed on the sim's impact scale by rank.

    The hand-weighted impact blend (sim.player_impact_score) averages nine skills, rim deterrence among them. While the
    rim rating mixed in general defensive grades, it also carried perimeter and help defense; once rim deterrence was
    fitted to real rim evidence (2026-11-18), elite non-rim defenders (Anunoby, Draymond Green, Adebayo) lost sim
    impact and team strength followed. The fitted value (offense + defense, Basketball Index multi-year LEBRON, the same
    model the card shows) reads every defensive input directly. Same league distribution as the blend; only the order
    comes from the fit. None outside new-ratings mode.
    """
    if _BUILDING:
        return None
    model = _model(canonical)
    if model is None or not model.get("impact_tables_key") or not traits:
        return None
    key_list = model["impact_tables_key"]
    tables = _TABLE_CACHE.get((tuple(key_list[:-1]), key_list[-1]))
    fit = load_fit()
    if not tables or "sim_impact" not in tables or fit is None:
        return None
    prediction = predict(fit, traits, player, profile if profile is not None else _profile(canonical, player, traits),
                         _inputs(canonical, player))
    return mapped(tables, prediction, "sim_impact")


def remap_on_court(canonical: Mapping[str, Any], players: list[Mapping[str, Any]], traits_by_id: Mapping[str, Mapping[str, float]],
                   legacy_on_court: Mapping[str, float]) -> dict[str, float]:
    """Trade-market on-court values re-ordered by fitted impact on the market's own current scale."""
    fit = load_fit()
    if _model(canonical) is None or fit is None or len(legacy_on_court) < 30:
        return dict(legacy_on_court)
    predictions = {p["id"]: predict(fit, traits_by_id.get(p["id"], {}), p, _profile(canonical, p, traits_by_id.get(p["id"], {})),
                                    _inputs(canonical, p))
                   for p in players if p["id"] in legacy_on_court}
    tables = build_tables(predictions, {"on_court": list(legacy_on_court.values())})
    return {pid: round(mapped(tables, prediction, "on_court"), 4) for pid, prediction in predictions.items()}
