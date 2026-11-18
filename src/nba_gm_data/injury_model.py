"""Per-body-part injury model (v2), fitted to Basketball Index Injury Tracker evidence.

data/canonical/injury_model_v2.json is built by scripts/build_injury_model.py: for each of 16 body parts (plus illness) a
Poisson model of injuries per game played, from real player-seasons 2015-16..2025-26. Inputs: age, height, weight,
workload (possessions per game), rim pressure, offensive rebounding, conditioning (stamina), center/guard, and the
player's own injury history: recent injuries to the same part (the compounding term) and to other parts, both
fading over about 1.5 years. Recovery times are real absences for the drawn part, sampled with recent seasons weighted
more, so diagnoses and durations (including the long tail) follow the evidence instead of hand-set severity bands.
"""
from __future__ import annotations

import bisect
import json
import math
import random
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

MODEL_FILE = "data/canonical/injury_model_v2.json"
POSSESSIONS_PER_MINUTE = 2.1      # a player's on-court possessions per minute at a ~101-possession pace
MIN_MINUTES_FOR_EXPOSURE = 4.0    # deep reserves who barely play still get hurt occasionally (Codex INJ)
# Calibration to Basketball Index's league totals (spells per team-season, games missed per 82) is applied here, once,
# instead of inside the per-part models. 1.0 = the fitted rates as they are.
LEAGUE_RATE_SCALE = 1.0
# Basketball Index logs one real injury as several entries ("out", then "day-to-day"), so a player's recorded history
# overstates how much it predicts new injuries. Calibrated against Basketball Index's own 2026-27 per-player forecasts.
HISTORY_WEIGHT = 0.55
# Severity labels kept for the existing consumers (GUI, news, AI), now derived from the real duration.
SEVERITY_BY_DAYS = ((3, "day_to_day"), (14, "short"), (42, "medium"), (90, "long"))
# Legacy six-area labels (older saves, prospect medicals, profile tags) -> the closest body parts.
LEGACY_AREA_PARTS = {
    "ankle_foot": ("ankle", "foot", "toe", "achilles"), "knee": ("knee",), "back_core": ("back",),
    "hip_groin": ("hip", "groin"), "shoulder_arm_hand": ("shoulder", "wrist", "hand", "thumb"),
    "head_illness": ("head", "illness"),
}
PART_AREA = {part: area for area, parts in LEGACY_AREA_PARTS.items() for part in parts}
PART_AREA.update({"hamstring": "hip_groin", "quadriceps": "knee", "calf": "ankle_foot"})
PART_LABELS = {"ankle": "Ankle", "knee": "Knee", "back": "Back", "hamstring": "Hamstring", "hip": "Hip", "foot": "Foot",
               "calf": "Calf", "shoulder": "Shoulder", "groin": "Groin", "quadriceps": "Quad", "toe": "Toe",
               "head": "Head", "wrist": "Wrist", "hand": "Hand", "achilles": "Achilles", "thumb": "Thumb",
               "illness": "Illness"}


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any] | None:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else None


def load_model(root: str | Path | None = None) -> dict[str, Any] | None:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    return _load(str(root / MODEL_FILE))


def _parse(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def event_part(event: Mapping[str, Any]) -> str:
    """Body part of an injury event (v2 events carry it; legacy area labels map to their first part)."""
    part = str(event.get("body_part") or "")
    if part:
        return part
    area = str(event.get("body_area") or "")
    return area if area in PART_LABELS else (LEGACY_AREA_PARTS.get(area, ("",))[0] or "other")


def player_history(model: Mapping[str, Any], player_id: str, events: Iterable[Mapping[str, Any]]) -> list[tuple[date, str]]:
    """(start date, part) of the player's known injuries: real recent history plus the save's own events."""
    out = []
    for start, part, *_ in (model.get("player_history") or {}).get(player_id, []):
        d = _parse(start)
        if d:
            out.append((d, part))
    seen = {(d, p) for d, p in out}
    for event in events:
        if event.get("player_id") != player_id:
            continue
        d, part = _parse(event.get("start_date")), event_part(event)
        if d and part and part != "illness" and (d, part) not in seen:
            out.append((d, part))
            seen.add((d, part))
    return sorted(out)


def prior_terms(history: list[tuple[date, str]], on: date, decay_years: float) -> dict[str, float]:
    terms: dict[str, float] = {}
    for d, part in history:
        if d < on:
            terms[part] = terms.get(part, 0.0) + math.exp(-((on - d).days / 365.25) / decay_years)
    return terms


def part_hazards(model: Mapping[str, Any], player: Mapping[str, Any], traits: Mapping[str, float], minutes: float,
                 history: list[tuple[date, str]], on: date) -> dict[str, float]:
    """Chance of an injury to each part in one game played (before league calibration and staff/fatigue effects)."""
    std = model["standardization"]
    mean, sd = std["mean"], std["sd"]
    age = float(player.get("age") or 27.0)
    raw = {
        "age": age, "height": float(player.get("height_inches") or 78.0), "weight": float(player.get("weight_lbs") or 215.0),
        "poss_pg": max(0.0, minutes) * POSSESSIONS_PER_MINUTE,
        "rim_pressure": float(traits.get("rim_pressure", 50.0)),
        "offensive_rebounding": float(traits.get("offensive_rebounding", 50.0)),
        "stamina": float(traits.get("stamina_cardio", 50.0)),
    }
    z = {k: (raw[k] - mean[k]) / (sd[k] or 1.0) for k in raw}
    pos = str(player.get("position") or "")
    center = 1.0 if "C" in pos else 0.0
    guard = 1.0 if pos.startswith(("PG", "SG", "G")) else 0.0
    priors = prior_terms(history, on, float(model.get("history_decay_years") or 1.5))
    total_prior = sum(priors.values())
    out = {}
    for part, info in model["parts"].items():
        c = info["coef"]
        same = priors.get(part, 0.0)
        eta = (info["intercept"] + c["age"] * z["age"] + c["age2"] * z["age"] ** 2 + c["height"] * z["height"]
               + c["weight"] * z["weight"] + c["poss_pg"] * z["poss_pg"] + c["rim_pressure"] * z["rim_pressure"]
               + c["offensive_rebounding"] * z["offensive_rebounding"] + c["stamina"] * z["stamina"]
               + c["center"] * center + c["guard"] * guard
               + HISTORY_WEIGHT * (c["prior_same"] * same + c["prior_other"] * (total_prior - same)))
        out[part] = math.exp(max(-20.0, min(2.0, eta)))
    return out


@lru_cache(maxsize=32)
def _pool_index(path: str, part: str) -> tuple[list[float], list[dict[str, Any]]]:
    model = _load(path) or {}
    pool = (model.get("recovery_pools") or {}).get(part) or []
    cumulative, total = [], 0.0
    for r in pool:
        total += float(r.get("w") or 1.0)   # Basketball Index's 6-year half-life recency weight
        cumulative.append(total)
    return cumulative, pool


def sample_recovery(root: str | Path | None, part: str, rng: random.Random) -> dict[str, Any]:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    cumulative, pool = _pool_index(str(root / MODEL_FILE), part)
    if not pool:
        return {"label": f"{part} injury", "days": 3, "games": 1, "surgery": 0}
    marker = rng.random() * cumulative[-1]
    return pool[min(len(pool) - 1, bisect.bisect_left(cumulative, marker))]


def severity_for_days(days: int) -> str:
    for limit, label in SEVERITY_BY_DAYS:
        if days <= limit:
            return label
    return "season_ending" if days > 150 else "long"


def basketball_return_date(start: date, days: int) -> date:
    """Basketball Index counts days out within the basketball calendar; the July-September offseason is skipped."""
    current, left = start, max(0, int(days))
    while True:
        if date(current.year, 7, 1) <= current < date(current.year, 10, 1):
            current = date(current.year, 10, 1)
        season_end = date(current.year + (1 if current.month >= 10 else 0), 7, 1)
        room = (season_end - current).days
        if left <= room:
            return current + timedelta(days=left)
        left -= room
        current = date(season_end.year, 10, 1)


def lasting_effect(model: Mapping[str, Any], label: str | None, part: str) -> float:
    """Evidence-based lasting impact change (RAPM points next season, negative) for this diagnosis, else 0.

    Only diagnoses (or, failing a specific match, body parts) whose Basketball Index long-term estimate has a 90% interval
    entirely below zero count (user decision 2026-11-18)."""
    text = str(label or "").lower()
    specific = [r for r in model.get("lasting_effects") or [] if r.get("level") == "specific"]
    for row in sorted(specific, key=lambda r: -len(str(r.get("bucket") or ""))):
        bucket = str(row.get("bucket") or "").lower()
        if bucket and bucket in text:
            return float(row.get("d_rapm_1y_shrunk") or 0.0)
    return 0.0


# Lasting effects become permanent losses on the four physical ratings. Scale: league spread of overall rating (9.06) vs
# real impact (LEBRON, 1.94) gives 4.67 overall points per impact point; lowering the four physical ratings by 1 lowers
# overall by ~0.30, so one impact point = ~15.7 points on each physical rating (measured 2026-11-18).
LASTING_TRAIT_POINTS_PER_RAPM = 15.7
LASTING_TRAITS = ("foot_speed_lateral_agility", "rim_pressure", "stamina_cardio", "defensive_effort")
STRUCTURAL_WORDS = ("tear", "rupture", "surgery", "fracture")


def lasting_trait_deltas(event: Mapping[str, Any]) -> dict[str, float]:
    """Permanent physical rating changes for an injury with evidence of a lasting decline (empty when none applies).

    Applies to tears, ruptures, fractures and surgeries, or any qualifying diagnosis that kept the player out 14+ days,
    so a minor flare-up with a scary label does not cost ability."""
    change = float(event.get("lasting_rapm_change") or 0.0)
    if change >= 0:
        return {}
    label = str(event.get("diagnosis") or "").lower()
    if not (any(word in label for word in STRUCTURAL_WORDS) or int(event.get("surgery") or 0)
            or int(event.get("expected_days_missed") or 0) >= 14):
        return {}
    return {trait: round(change * LASTING_TRAIT_POINTS_PER_RAPM, 3) for trait in LASTING_TRAITS}
