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
PREDICTORS = [*LEGACY_TRAITS, "height_inches", *PROFILE_PREDICTORS]
TABLE_KEY = "_impact_value_tables"
_FIT_CACHE: dict[str, Any] = {}


_PROFILE_DEFAULTS = {"three_per36": 3.0, "three_pct": 0.34, "two_pct": 0.52, "ft_pct": 0.76}


def predictor_row(traits: Mapping[str, float], player: Mapping[str, Any],
                  profile: Mapping[str, float] | None = None) -> list[float]:
    """Hidden ratings, height, and the engine's shooting profile (observed make rates and three-point volume,
    adjusted by development) - the same player representation the game sim scores with."""
    row = [float(traits.get(trait, 50.0)) for trait in LEGACY_TRAITS]
    row.append(float(player.get("height_inches") or 78.0))
    profile = profile or {}
    row.extend(float(profile.get(key, default)) for key, default in _PROFILE_DEFAULTS.items())
    return row


def load_fit(root: Path | None = None) -> dict[str, Any] | None:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    key = str(root / FIT_FILE)
    if key not in _FIT_CACHE:
        path = Path(key)
        _FIT_CACHE[key] = json.loads(path.read_text()) if path.exists() else None
    return _FIT_CACHE[key]


def predict(fit: Mapping[str, Any], traits: Mapping[str, float], player: Mapping[str, Any],
            profile: Mapping[str, float] | None = None) -> dict[str, float]:
    row = predictor_row(traits, player, profile)
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
        side = "overall" if key in ("overall", "on_court") else key
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
        predictions = {p["id"]: predict(fit, traits[p["id"]], p, _profile(canonical, p, traits[p["id"]])) for p in players}
        scales = {k: [s[k] for s in summaries.values() if k in s] for k in ("overall", "offense", "defense")}
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
    prediction = predict(fit, traits, player, profile if profile is not None else _profile(canonical, player, traits))
    return {key: round(mapped(tables, prediction, key), 1) for key in tables}


def remap_on_court(canonical: Mapping[str, Any], players: list[Mapping[str, Any]], traits_by_id: Mapping[str, Mapping[str, float]],
                   legacy_on_court: Mapping[str, float]) -> dict[str, float]:
    """Trade-market on-court values re-ordered by fitted impact on the market's own current scale."""
    fit = load_fit()
    if _model(canonical) is None or fit is None or len(legacy_on_court) < 30:
        return dict(legacy_on_court)
    predictions = {p["id"]: predict(fit, traits_by_id.get(p["id"], {}), p, _profile(canonical, p, traits_by_id.get(p["id"], {})))
                   for p in players if p["id"] in legacy_on_court}
    tables = build_tables(predictions, {"on_court": list(legacy_on_court.values())})
    return {pid: round(mapped(tables, prediction, "on_court"), 4) for pid, prediction in predictions.items()}
