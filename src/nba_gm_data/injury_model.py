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

# The source checkout root (data/ lives here); resolved once instead of on every lookup.
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]

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


EVIDENCE_FILE = "data/canonical/injury_player_evidence_v2.json"   # local only (per-player Basketball Index evidence)


@lru_cache(maxsize=4)
def _load_with_evidence(path: str, evidence_path: str) -> dict[str, Any] | None:
    model = _load(path)
    if model is None:
        return None
    evidence = _load(evidence_path) or {}
    return {**model, **{k: v for k, v in evidence.items() if k != "version"}}


def load_model(root: str | Path | None = None) -> dict[str, Any] | None:
    """The fitted model, plus real players' injury history/forecasts/recovery speed when the local evidence file exists."""
    root = Path(root) if root is not None else _PACKAGE_ROOT
    return _load_with_evidence(str(root / MODEL_FILE), str(root / EVIDENCE_FILE))


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


def _days_at(quantiles: list[int], u: float) -> float:
    pos = max(0.0, min(1.0, u)) * (len(quantiles) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(quantiles) - 1)
    return quantiles[lo] + (quantiles[hi] - quantiles[lo]) * (pos - lo)


def sample_recovery(root: str | Path | None, part: str, rng: random.Random) -> dict[str, Any]:
    """Days out from the part's real recovery-time distribution, and a diagnosis typical for that length."""
    model = load_model(root) or {}
    summary = (model.get("recovery_summary") or {}).get(part)
    if not summary:
        return {"label": f"{part} injury", "days": 3, "games": 1, "surgery": 0}
    days = max(1, int(round(_days_at(summary["quantiles"], rng.random()))))
    shares = next((labels for limit, labels in summary["labels_by_days"] if days <= limit), {}) or {f"{part} injury": 1.0}
    marker, running, label = rng.random() * sum(shares.values()), 0.0, next(iter(shares))
    for name, share in shares.items():
        running += share
        if marker <= running:
            label = name
            break
    return {"label": label, "days": days, "games": 0, "surgery": int("surgery" in str(label).lower())}


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


# Return-to-minutes ramp (Basketball Index short-term aftermath, 2025-26: first game back vs the five games before the
# absence, by games missed). The head coach's rotation management decides how closely the evidence ramp is followed:
# an average coach follows it, a poor one rushes players back, a strong one is slightly more careful.
RETURN_FIRST_GAME_DROP = ((1, 0.009), (2, 0.072), (5, 0.099), (10, 0.162), (20, 0.212), (10_000, 0.299))


def return_ramp_length(absence_games: int) -> int:
    return 6 if absence_games <= 5 else 8 if absence_games <= 10 else 10


def return_minutes_multiplier(absence_games: int, games_since_return: int, rotation_star: float = 3.0) -> float:
    if absence_games <= 0:
        return 1.0
    length = return_ramp_length(absence_games)
    if games_since_return >= length:
        return 1.0
    drop = next(value for limit, value in RETURN_FIRST_GAME_DROP if absence_games <= limit)
    careful = max(0.5, min(1.3, 1.0 + 0.2 * (float(rotation_star) - 3.0)))
    return round(1.0 - drop * careful * (1.0 - games_since_return / length), 4)


@lru_cache(maxsize=32)
def _mean_games_out(path: str, part: str) -> float:
    model = _load(path) or {}
    quantiles = ((model.get("recovery_summary") or {}).get(part) or {}).get("quantiles") or []
    if not quantiles:
        return 2.0
    mean_days = sum(_days_at(quantiles, (k + 0.5) / 200.0) for k in range(200)) / 200.0
    return mean_days / 2.4    # the engine's days-to-games conversion (health.expected_games_from_days)


def expected_injury_games_82(model: Mapping[str, Any], player: Mapping[str, Any], traits: Mapping[str, float], minutes: float,
                             history: list[tuple[date, str]], on: date, root: str | Path | None = None) -> float:
    """Games a player is expected to miss to injury over 82 team games under the v2 model (before staff effects)."""
    root = Path(root) if root is not None else _PACKAGE_ROOT
    hazards = part_hazards(model, player, traits, minutes, history, on)
    path = str(root / MODEL_FILE)
    return 82.0 * LEAGUE_RATE_SCALE * sum(h * _mean_games_out(path, part) for part, h in hazards.items())


def health_risk_scores(canonical: Mapping[str, Any], legacy_scores: Mapping[str, float]) -> dict[str, float]:
    """AI injury-risk scores from the v2 model, placed on the legacy score's scale by league rank.

    The AI's thresholds were written for the old 0-34 score, so each player's v2 expected injury games are ranked across
    the league and given the legacy score at the same rank (same technique as impact_value). Only the ordering comes
    from the new model."""
    model = load_model()
    if not model or len(legacy_scores) < 30:
        return dict(legacy_scores)
    from datetime import date as _date
    on = _parse((canonical.get("meta") or {}).get("current_date")) or _date(2026, 10, 20)
    by_player: dict[str, list] = {}
    for event in canonical.get("injury_events", []):
        if event.get("player_id"):
            by_player.setdefault(event["player_id"], []).append(event)
    traits: dict[str, dict[str, float]] = {}
    for row in canonical.get("traits", []):
        if row.get("trait_key") in ("rim_pressure", "offensive_rebounding", "stamina_cardio"):
            traits.setdefault(row["player_id"], {})[row["trait_key"]] = float(row.get("value") or 50.0)
    expected = {}
    for player in canonical.get("players", []):
        pid = player.get("id")
        if pid not in legacy_scores:
            continue
        minutes = max(MIN_MINUTES_FOR_EXPOSURE, float(player.get("minutes_projection") or 0.0))
        history = player_history(model, pid, by_player.get(pid, []))
        expected[pid] = expected_injury_games_82(model, player, traits.get(pid, {}), minutes, history, on)
    if not expected:
        return dict(legacy_scores)

    def ranks(values: Mapping[str, float]) -> dict[str, float]:
        ordered = sorted(values.values())
        n = len(ordered)
        return {pid: (bisect.bisect_left(ordered, v) + bisect.bisect_right(ordered, v) - 1) / 2.0 / max(1, n - 1)
                for pid, v in values.items()}

    model_rank = ranks(expected)
    # Basketball Index's 2026-27 forecast for real players (validated: rank r 0.66 vs outcomes) gets 70% weight in the
    # first season, halving each later season; our model (r 0.52 vs those forecasts) carries the rest and all generated players.
    forecast = {pid: float(v) for pid, v in (model.get("player_forecast_2026_27") or {}).items() if pid in expected}
    forecast_rank = ranks(forecast) if len(forecast) >= 30 else {}
    seasons_on = max(0, on.year - 2026 - (1 if on.month < 7 else 0))
    weight = 0.7 * 0.5 ** seasons_on
    blended = {pid: (1 - weight) * r + weight * forecast_rank[pid] if pid in forecast_rank else r for pid, r in model_rank.items()}
    final_rank = ranks(blended)
    target = sorted(legacy_scores[pid] for pid in expected)
    n = len(target)
    return {pid: round(target[min(n - 1, max(0, int(round(r * (n - 1)))))], 3) for pid, r in final_rank.items()}


# ---- Body map for the player card (2026-11-19) --------------------------------------------------------------------
BODY_MAP_TRAITS = ("rim_pressure", "offensive_rebounding", "stamina_cardio")
BODY_MAP_BASELINE_MPG = 20.0       # "typical rotation player" baseline: league players projected for 20+ minutes
_BASELINE_CACHE: dict[tuple, dict[str, float]] = {}


_LOOKUP_CACHE: dict[tuple, tuple[dict[str, dict[str, float]], dict[str, list]]] = {}


def _league_lookups(canonical: Mapping[str, Any]) -> tuple[dict[str, dict[str, float]], dict[str, list]]:
    """Body-map traits and injury events by player, built once per league state (tables call this per row)."""
    rows, events = canonical.get("traits", []), canonical.get("injury_events", [])
    key = (id(rows), len(rows), id(events), len(events))
    cached = _LOOKUP_CACHE.get(key)
    if cached is not None:
        return cached
    traits: dict[str, dict[str, float]] = {}
    for row in rows:
        if row.get("trait_key") in BODY_MAP_TRAITS:
            traits.setdefault(str(row["player_id"]), {})[row["trait_key"]] = float(row.get("value") or 50.0)
    by_player: dict[str, list] = {}
    for event in events:
        if event.get("player_id"):
            by_player.setdefault(str(event["player_id"]), []).append(event)
    if len(_LOOKUP_CACHE) >= 4:
        _LOOKUP_CACHE.clear()
    _LOOKUP_CACHE[key] = (traits, by_player)
    return traits, by_player


def _games_by_part(model, path, player, traits, minutes, history, on) -> dict[str, float]:
    hazards = part_hazards(model, player, traits, minutes, history, on)
    return {part: 82.0 * LEAGUE_RATE_SCALE * h * _mean_games_out(path, part) for part, h in hazards.items()}


def role_minutes(player: Mapping[str, Any]) -> float:
    """Minutes a game the outlook assumes: the player's current role, or his normal role when the current target is
    low (benched or injured), so the map describes his body rather than this week's rotation."""
    current = float(player.get("minutes_projection") or 0.0)
    normal = min(36.0, float(player.get("prior_minutes") or 0.0) / 82.0)
    return round(max(MIN_MINUTES_FOR_EXPOSURE, current, normal), 1)


def body_risk_map(canonical: Mapping[str, Any], player: Mapping[str, Any], health_state: Mapping[str, Any] | None = None,
                  root: str | Path | None = None) -> dict[str, Any] | None:
    """Per-body-part injury outlook for the player card, straight from the injury model the sim uses.

    For each part: games this player is expected to miss per 82 team games from injuries there (the sim's own
    per-game chance at his projected minutes x the real recovery-time distribution), and how that compares with a
    typical rotation player. A current injury is flagged on its part."""
    model = load_model(root)
    if not model:
        return None
    root = Path(root) if root is not None else _PACKAGE_ROOT
    path = str(root / MODEL_FILE)
    on = _parse((canonical.get("meta") or {}).get("current_date")) or date(2026, 10, 20)
    events = canonical.get("injury_events", [])
    traits, events_by_player = _league_lookups(canonical)
    key = (path, on.isoformat(), len(canonical.get("players", [])), len(events))
    baseline = _BASELINE_CACHE.get(key)
    if baseline is None:
        by_player = events_by_player
        totals: dict[str, float] = {}
        count = 0
        for other in canonical.get("players", []):
            minutes = float(other.get("minutes_projection") or 0.0)
            if not other.get("team_id") or minutes < BODY_MAP_BASELINE_MPG:
                continue
            pid = str(other.get("id"))
            games = _games_by_part(model, path, other, traits.get(pid, {}), minutes,
                                   player_history(model, pid, by_player.get(pid, [])), on)
            for part, value in games.items():
                totals[part] = totals.get(part, 0.0) + value
            count += 1
        baseline = {part: value / max(1, count) for part, value in totals.items()}
        if len(_BASELINE_CACHE) > 8:
            _BASELINE_CACHE.clear()
        _BASELINE_CACHE[key] = baseline
    pid = str(player.get("id"))
    minutes = role_minutes(player)
    history = player_history(model, pid, events_by_player.get(pid, []))
    games = _games_by_part(model, path, player, traits.get(pid, {}), minutes, history, on)
    state = health_state or {}
    current = ""
    if state.get("current_injury_id"):
        current = str(state.get("current_injury_part") or "")
        if not current:   # injuries seeded from real data carry an area on the event, not a part on the state
            event = next((e for e in events_by_player.get(pid, []) if e.get("id") == state.get("current_injury_id")), None)
            current = event_part(event) if event else ""
    recent = {}
    for d, part in history:
        if d <= on and (on - d).days <= 3 * 365:
            recent[part] = recent.get(part, 0) + 1
    parts = []
    for part, value in sorted(games.items(), key=lambda kv: -kv[1]):
        base = baseline.get(part) or 0.0
        parts.append({"part": part, "label": PART_LABELS.get(part, part.title()), "expected_games": round(value, 2),
                      "typical_games": round(base, 2), "relative": round(value / base, 2) if base > 0 else None,
                      "recent_injuries": recent.get(part, 0), "current": part == current})
    return {"parts": parts, "expected_games_total": round(sum(games.values()), 1),
            "typical_games_total": round(sum(baseline.values()), 1), "minutes_basis": round(minutes, 1),
            "current_part": current or None,
            "current_label": (state.get("current_injury_label") or PART_LABELS.get(current, current)) if current else None}


def compact_body_map(body: Mapping[str, Any] | None, highlight: str | None = None) -> dict[str, Any] | None:
    """Small form of body_risk_map for tables: [part, expected games, vs typical] per part, plus the injured part."""
    if not body:
        return None
    return {"p": [[row["part"], row["expected_games"], row["relative"]] for row in body["parts"]],
            "c": highlight or body.get("current_part"), "t": body["expected_games_total"], "y": body["typical_games_total"]}
