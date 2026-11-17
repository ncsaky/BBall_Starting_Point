"""Expected change in a player's overall rating over the coming months, from the engine's own development model.

Used for the "decline watch" (veterans whose growth runway is 0). It runs the same monthly development function
the season uses (health.monthly_trait_delta) with the same staff, focus and skill-ceiling inputs, but without the
month's random noise and assuming the player stays healthy. In new-ratings mode the changes route through the 94
inputs and the hidden ratings are re-derived, exactly as real development does. The overall rating is then
evaluated with the same formula the player card uses, holding minutes fixed. An expectation, not a guarantee.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .health import (DEVELOPMENT_TRAITS, coach_development_by_team, development_staff_modifiers,
                     development_trait_focus, monthly_trait_delta)
from .utils import maybe_float


def _months_after(start: str, count: int) -> list[str]:
    year, month = int(start[:4]), int(start[5:7])
    out = []
    for _ in range(count):
        month += 1
        if month > 12:
            year, month = year + 1, 1
        out.append(f"{year:04d}-{month:02d}")
    return out


def _overall(active: dict[str, Any], player: dict[str, Any], traits: dict[str, float], model: dict[str, Any] | None) -> float:
    from .ratings_model import MODEL_KEY
    from .save import player_attribute_summary
    context = {"meta": active.get("meta", {}), "players": [player],
               "traits": [{"player_id": player["id"], "trait_key": k, "value": v} for k, v in traits.items()]}
    if model is not None:
        context[MODEL_KEY] = model
    return float(player_attribute_summary(context, player["id"]).get("overall") or 0.0)


def expected_rating_changes(active: dict[str, Any], player: dict[str, Any], months: int = 12,
                            start_month: str | None = None, seed: int = 1) -> dict[str, float] | None:
    """Expected change of each hidden rating over `months` if healthy: the season's own monthly development
    function without its random noise, same staff, focus and skill ceilings, minutes held at today's projection."""
    pid = player.get("id")
    rows = (active.get("_transaction_traits_by_player") or {}).get(pid)
    if rows is None:
        rows = {t["trait_key"]: t for t in active.get("traits", []) if t.get("player_id") == pid}
    if not rows:
        return None
    current = {k: float(r.get("value", 50.0)) for k, r in rows.items() if r.get("value") is not None}
    age = maybe_float(player.get("display_age", player.get("age")))
    minutes = float(player.get("minutes_projection") or 0.0)
    coach = coach_development_by_team(active).get(player.get("team_id"), 3.0)
    staff = development_staff_modifiers(active, player.get("team_id"), coach)
    start = (start_month or str(active.get("meta", {}).get("current_date") or date.today().isoformat()))[:7]
    totals: dict[str, float] = {}
    for index, month in enumerate(_months_after(start, months)):
        month_age = None if age is None else age + (index + 1) / 12.0
        focus = development_trait_focus(player, staff, rows, seed, month)
        for key in DEVELOPMENT_TRAITS:
            if key not in current:
                continue
            context = (rows.get(key, {}).get("components") or {}).get("career_capacity")
            delta = monthly_trait_delta(player, key, current[key], month_age, minutes, staff, 0.0, seed, month,
                                        float(focus.get(key, 0.32)), context, expected=True)
            current[key] += delta
            totals[key] = totals.get(key, 0.0) + delta
    return totals


def decline_summary(totals: dict[str, float] | None) -> dict[str, float] | None:
    """Average expected change per hidden rating, overall and split into athletic vs skill ratings."""
    from .health import PHYSICAL_TRAITS
    if not totals:
        return None
    athletic = [v for k, v in totals.items() if k in PHYSICAL_TRAITS]
    skill = [v for k, v in totals.items() if k not in PHYSICAL_TRAITS]
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else 0.0
    return {"per_year": mean(list(totals.values())), "athletic": mean(athletic), "skill": mean(skill)}


def expected_overall_change(active: dict[str, Any], player: dict[str, Any], months: int = 12,
                            start_month: str | None = None, seed: int = 1) -> float | None:
    """Expected overall change over `months` if healthy (minutes held at today's projection)."""
    from .save import trait_values_by_player
    from .ratings_model import MODEL_KEY, uses_inputs_model
    pid = player.get("id")
    rows = (active.get("_transaction_traits_by_player") or {}).get(pid)
    if rows is None:
        rows = {t["trait_key"]: t for t in active.get("traits", []) if t.get("player_id") == pid}
    if not rows:
        return None
    traits = {k: float(r.get("value", 50.0)) for k, r in rows.items() if r.get("value") is not None}
    age = maybe_float(player.get("display_age", player.get("age")))
    minutes = float(player.get("minutes_projection") or 0.0)
    coach = coach_development_by_team(active).get(player.get("team_id"), 3.0)
    staff = development_staff_modifiers(active, player.get("team_id"), coach)
    start = (start_month or str(active.get("meta", {}).get("current_date") or date.today().isoformat()))[:7]
    totals: dict[str, float] = {}
    current = dict(traits)
    for index, month in enumerate(_months_after(start, months)):
        month_age = None if age is None else age + (index + 1) / 12.0
        focus = development_trait_focus(player, staff, rows, seed, month)
        for key in DEVELOPMENT_TRAITS:
            if key not in current:
                continue
            context = (rows.get(key, {}).get("components") or {}).get("career_capacity")
            delta = monthly_trait_delta(player, key, current[key], month_age, minutes, staff, 0.0, seed, month,
                                        float(focus.get(key, 0.32)), context, expected=True)
            current[key] += delta
            totals[key] = totals.get(key, 0.0) + delta
    model = active.get(MODEL_KEY) if uses_inputs_model(active) else None
    if model is None:
        return round(_overall(active, player, current, None) - _overall(active, player, traits, None), 1)
    from .ratings_model import _FITTED_CACHE, _effective, _player_base_inputs, route_trait_deltas
    from .trait_adapter import derive_traits
    base = _player_base_inputs(model, pid)
    if base is None:
        return round(_overall(active, player, current, None) - _overall(active, player, traits, None), 1)
    accumulated = dict((model.get("input_deltas") or {}).get(pid) or {})
    for input_id, delta in route_trait_deltas(base, totals).items():
        accumulated[input_id] = round(accumulated.get(input_id, 0.0) + delta, 6)
    future_model = {**model, "input_deltas": {**(model.get("input_deltas") or {}), pid: accumulated}}
    fitted = _FITTED_CACHE[tuple(model["fitted_key"])]
    future_traits = derive_traits(_effective(future_model, pid), fitted)
    now_traits = derive_traits(_effective(model, pid), fitted)
    return round(_overall(active, player, future_traits, future_model) - _overall(active, player, now_traits, model), 1)
