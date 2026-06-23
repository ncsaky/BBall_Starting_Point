from __future__ import annotations

import csv
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from .schema import CANONICAL_START_DATE, TraitValue
from .utils import clamp, confidence_from_fields, mean, maybe_float, normalize_name, percentile, stable_id


TRAIT_LABELS = {
    "release_speed": "Release Speed",
    "shooting_range": "Shooting Range",
    "shot_versatility": "Shot Versatility",
    "rim_pressure": "Rim Pressure",
    "handle_pressure": "Handle Under Pressure",
    "passing_reads": "Passing Reads",
    "foot_speed_lateral_agility": "Foot Speed / Lateral Agility",
    "stamina_cardio": "Stamina / Cardio",
    "defensive_effort": "Defensive Effort",
    "scheme_iq": "Scheme IQ",
    "rim_deterrence": "Rim Deterrence",
    "screen_navigation": "Screen Navigation",
    "offensive_rebounding": "Offensive Rebounding",
    "portability": "Portability",
    "playoff_translation": "Playoff Translation",
}

PERCENTILE_FIELDS = [
    "3PAp75",
    "3P%",
    "threePAr",
    "FTr",
    "LT_06_PCT",
    "boxCreationEst",
    "passerRating",
    "ASTp75",
    "cTOVpct",
    "touches",
    "DEFLECTIONS",
    "STLpct",
    "BLKpct",
    "ORBp75",
    "ORBpct",
    "CraftedOPM",
    "CraftedDPM",
    "DARKO",
    "LEBRON",
    "Portability",
    "minutes",
    "2025minutes",
    "HeightSocks",
    "VersatilityRating",
    "OffScreen%",
    "Handoff%",
    "SpotUp%",
    "Prbh%",
    "Iso%",
    "Post%",
    "Cut%",
    "Transition%",
    "Putback%",
    "PrbhPPP",
    "PnrrPPP",
    "SpotUpPPP",
    "OffScreenPPP",
    "HandoffPPP",
    "CutPPP",
    "PutbackPPP",
    "PostPPP",
    "TransitionPPP",
]

LEAGUE_TRAIT_RATINGS_SOURCE_ID = "src_league_trait_ratings_2026_06_20"

LEAGUE_TRAIT_RATING_COLUMNS = {
    "ReleaseSpeed": "release_speed",
    "ShootingRange": "shooting_range",
    "ShotVersatility": "shot_versatility",
    "RimPressure": "rim_pressure",
    "HandleUnderPressure": "handle_pressure",
    "PassingReads": "passing_reads",
    "FootSpeed": "foot_speed_lateral_agility",
    "Stamina": "stamina_cardio",
    "DefensiveEffort": "defensive_effort",
    "SchemeIQ": "scheme_iq",
    "RimDeterrence": "rim_deterrence",
    "ScreenNavigation": "screen_navigation",
    "OffensiveRebounding": "offensive_rebounding",
    "Portability": "portability",
    "PlayoffTranslation": "playoff_translation",
}

LEAGUE_TRAIT_COMPOSITE_COLUMNS = {
    "OFF": (
        "offense",
        ["release_speed", "shooting_range", "shot_versatility", "rim_pressure", "handle_pressure", "passing_reads"],
        0.3,
    ),
    "DEF": (
        "defense",
        ["defensive_effort", "scheme_iq", "rim_deterrence", "screen_navigation", "foot_speed_lateral_agility"],
        0.3,
    ),
    "REB": (
        "rebounding",
        ["offensive_rebounding", "rim_deterrence", "stamina_cardio"],
        0.28,
    ),
    "OVR": (
        "overall",
        list(TRAIT_LABELS.keys()),
        0.16,
    ),
}

LEAGUE_TRAIT_RATING_ALIASES = {
    "ron holland": "ronald holland ii",
    "carlton carrington": "bub carrington",
}


def weighted_mean(values: list[tuple[float | None, float]]) -> float | None:
    clean = [(float(value), weight) for value, weight in values if value is not None and weight > 0]
    total_weight = sum(weight for _, weight in clean)
    if not clean or total_weight <= 0:
        return None
    return sum(value * weight for value, weight in clean) / total_weight


def load_league_trait_ratings(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle) if row.get("Player")]


def match_league_trait_ratings(players: list[Any], rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    players_by_name: dict[str, list[Any]] = defaultdict(list)
    for player in players:
        players_by_name[normalize_name(_player_get(player, "name"))].append(player)

    matched: dict[str, dict[str, Any]] = {}
    report: dict[str, Any] = {
        "source_rows": len(rows),
        "matched_count": 0,
        "unmatched_csv_rows": [],
        "unmatched_player_rows": [],
        "ambiguous_rows": [],
        "team_mismatches": [],
        "alias_matches": [],
        "duplicate_rows": [],
    }
    for row in rows:
        csv_name = str(row.get("Player") or "").strip()
        normalized = normalize_name(csv_name)
        alias = LEAGUE_TRAIT_RATING_ALIASES.get(normalized)
        lookup = normalize_name(alias or csv_name)
        candidates = players_by_name.get(lookup) or []
        if not candidates:
            report["unmatched_csv_rows"].append(_rating_report_row(row))
            continue
        if len(candidates) > 1:
            csv_team = str(row.get("Team") or "").strip()
            team_matches = [player for player in candidates if _player_get(player, "team_abbrev") == csv_team]
            if len(team_matches) == 1:
                candidates = team_matches
            else:
                report["ambiguous_rows"].append({**_rating_report_row(row), "candidate_count": len(candidates)})
                continue
        player = candidates[0]
        player_id = _player_get(player, "id")
        if player_id in matched:
            report["duplicate_rows"].append({**_rating_report_row(row), "player_id": player_id})
            continue
        matched[player_id] = row
        if alias:
            report["alias_matches"].append({"csv_player": csv_name, "matched_player": _player_get(player, "name")})
        csv_team = str(row.get("Team") or "").strip()
        player_team = str(_player_get(player, "team_abbrev") or "").strip()
        if csv_team and player_team and csv_team != player_team:
            report["team_mismatches"].append(
                {"csv_player": csv_name, "csv_team": csv_team, "canonical_team": player_team}
            )

    matched_ids = set(matched)
    for player in players:
        if _player_get(player, "id") in matched_ids:
            continue
        minutes = _display_minutes(_player_get(player, "minutes_projection"))
        if minutes >= 8.0:
            report["unmatched_player_rows"].append(
                {
                    "player": _player_get(player, "name"),
                    "team": _player_get(player, "team_abbrev"),
                    "minutes": round(minutes, 1),
                }
            )

    report["matched_count"] = len(matched)
    report["unmatched_csv_count"] = len(report["unmatched_csv_rows"])
    report["unmatched_player_count"] = len(report["unmatched_player_rows"])
    report["ambiguous_count"] = len(report["ambiguous_rows"])
    report["team_mismatch_count"] = len(report["team_mismatches"])
    return matched, report


def apply_league_trait_calibration(
    traits: list[TraitValue],
    players: list[Any],
    rows: list[dict[str, Any]],
) -> tuple[list[TraitValue], dict[str, Any]]:
    matched_rows, report = match_league_trait_ratings(players, rows)
    if not matched_rows:
        return traits, report

    players_by_id = {_player_get(player, "id"): player for player in players}
    values_by_player: dict[str, dict[str, float]] = defaultdict(dict)
    trait_by_key: dict[tuple[str, str], TraitValue] = {}
    for trait in traits:
        trait_by_key[(trait.player_id, trait.trait_key)] = trait
        values_by_player[trait.player_id][trait.trait_key] = float(trait.value)

    csv_distributions = {
        column: sorted(float(value) for row in rows if (value := maybe_float(row.get(column))) is not None)
        for column in [*LEAGUE_TRAIT_RATING_COLUMNS.keys(), *LEAGUE_TRAIT_COMPOSITE_COLUMNS.keys()]
    }
    engine_distributions = {
        trait_key: sorted(float(trait.value) for trait in traits if trait.trait_key == trait_key)
        for trait_key in LEAGUE_TRAIT_RATING_COLUMNS.values()
    }
    engine_composite_distributions: dict[str, list[float]] = defaultdict(list)
    for player_id, trait_values in values_by_player.items():
        player = players_by_id.get(player_id)
        composites = _trait_composites(trait_values, _display_minutes(_player_get(player, "minutes_projection")))
        for key, value in composites.items():
            engine_composite_distributions[key].append(value)
    sorted_composite_distributions = {key: sorted(values) for key, values in engine_composite_distributions.items()}

    calibration: dict[tuple[str, str], dict[str, Any]] = {}
    for player_id, row in matched_rows.items():
        player = players_by_id.get(player_id)
        blend_weight = _calibration_blend_weight(player)
        for column, trait_key in LEAGUE_TRAIT_RATING_COLUMNS.items():
            csv_value = maybe_float(row.get(column))
            if csv_value is None or (player_id, trait_key) not in trait_by_key:
                continue
            trait = trait_by_key[(player_id, trait_key)]
            previous = values_by_player[player_id].get(trait_key, 50.0)
            target = _quantile_map(csv_value, csv_distributions.get(column) or [], engine_distributions.get(trait_key) or [])
            target = _engine_target_floor(column, csv_value, target)
            trait_weight = _trait_calibration_weight(blend_weight, trait, previous, target)
            calibrated = previous + (target - previous) * trait_weight
            values_by_player[player_id][trait_key] = round(clamp(calibrated), 2)
            calibration[(player_id, trait_key)] = {
                "player_name": row.get("Player"),
                "csv_team": row.get("Team"),
                "csv_rank": _maybe_int(row.get("Rank")),
                "csv_column": column,
                "csv_value": round(float(csv_value), 2),
                "previous_value": round(previous, 2),
                "engine_target": round(target, 2),
                "blend_weight": round(trait_weight, 3),
                "composite_nudges": [],
            }

        for column, (composite_key, trait_keys, coefficient) in LEAGUE_TRAIT_COMPOSITE_COLUMNS.items():
            csv_value = maybe_float(row.get(column))
            if csv_value is None:
                continue
            current = _trait_composites(
                values_by_player[player_id],
                _display_minutes(_player_get(player, "minutes_projection")),
            ).get(composite_key, 50.0)
            target = _quantile_map(
                csv_value,
                csv_distributions.get(column) or [],
                sorted_composite_distributions.get(composite_key) or [],
            )
            nudge = clamp(target - current, -8.0, 8.0) * float(coefficient)
            if abs(nudge) < 0.05:
                continue
            for trait_key in trait_keys:
                if (player_id, trait_key) not in trait_by_key:
                    continue
                before = values_by_player[player_id].get(trait_key, 50.0)
                values_by_player[player_id][trait_key] = round(clamp(before + nudge), 2)
                calibration.setdefault(
                    (player_id, trait_key),
                    {
                        "player_name": row.get("Player"),
                        "csv_team": row.get("Team"),
                        "csv_rank": _maybe_int(row.get("Rank")),
                        "previous_value": round(before, 2),
                        "blend_weight": round(blend_weight, 3),
                        "composite_nudges": [],
                    },
                )["composite_nudges"].append(
                    {
                        "column": column,
                        "csv_value": round(float(csv_value), 2),
                        "engine_target": round(target, 2),
                        "previous_composite": round(current, 2),
                        "applied_delta": round(nudge, 2),
                    }
                )

    calibrated_traits: list[TraitValue] = []
    adjusted_count = 0
    for trait in traits:
        info = calibration.get((trait.player_id, trait.trait_key))
        if not info:
            calibrated_traits.append(trait)
            continue
        value = values_by_player[trait.player_id][trait.trait_key]
        source_ids = list(dict.fromkeys([*trait.source_ids, LEAGUE_TRAIT_RATINGS_SOURCE_ID]))
        components = {
            **trait.components,
            "league_trait_rating_calibration": {
                **info,
                "final_value": round(value, 2),
                "source": "subjective full-health ratings prior dated 2026-06-20",
            },
        }
        calibrated_traits.append(
            replace(
                trait,
                value=round(clamp(value), 2),
                confidence=round(clamp(max(float(trait.confidence), 0.56 + float(info.get("blend_weight") or 0.0) * 0.22), 0.0, 1.0), 3),
                source_kind="inferred_trait_model_v1_with_league_rating_calibration",
                source_ids=source_ids,
                notes=f"{trait.notes} Calibrated with a subjective full-health 2026-06-20 league ratings prior before manual overrides.",
                components=components,
            )
        )
        adjusted_count += 1

    report["adjusted_trait_count"] = adjusted_count
    report["source_id"] = LEAGUE_TRAIT_RATINGS_SOURCE_ID
    report["trait_columns"] = dict(LEAGUE_TRAIT_RATING_COLUMNS)
    report["composite_columns"] = {
        column: {"composite": spec[0], "traits": spec[1], "coefficient": spec[2]}
        for column, spec in LEAGUE_TRAIT_COMPOSITE_COLUMNS.items()
    }
    return calibrated_traits, report


def _trait_composites(values: dict[str, float], minutes: float) -> dict[str, float]:
    def get(key: str, default: float = 50.0) -> float:
        return float(values.get(key, default))

    def avg(keys: list[str]) -> float:
        return sum(get(key) for key in keys) / max(1, len(keys))

    shooting = avg(["shooting_range", "shot_versatility", "release_speed"])
    creation = avg(["handle_pressure", "passing_reads", "rim_pressure", "shot_versatility"])
    defense = avg(["defensive_effort", "scheme_iq", "screen_navigation", "rim_deterrence"])
    athleticism = avg(["foot_speed_lateral_agility", "stamina_cardio", "rim_pressure"])
    iq = avg(["scheme_iq", "passing_reads", "portability", "playoff_translation"])
    rebounding = get("offensive_rebounding") * 0.66 + get("rim_deterrence") * 0.18 + get("stamina_cardio") * 0.16
    overall = shooting * 0.22 + creation * 0.25 + defense * 0.22 + athleticism * 0.13 + iq * 0.12 + min(6.0, minutes / 7.0)
    offense = shooting * 0.35 + creation * 0.32 + get("passing_reads") * 0.18 + get("rim_pressure") * 0.15
    return {
        "overall": clamp(overall, 1, 99),
        "offense": clamp(offense, 1, 99),
        "defense": clamp(defense, 1, 99),
        "rebounding": clamp(rebounding, 1, 99),
    }


def _quantile_map(value: float, source_values: list[float], target_values: list[float]) -> float:
    if not source_values or not target_values:
        return clamp(value)
    return _value_at_percentile(target_values, _percentile_rank(source_values, value))


def _engine_target_floor(column: str, csv_value: float, target: float) -> float:
    if column == "ShotVersatility" and csv_value >= 70.0:
        return max(target, csv_value * 0.82)
    return target


def _percentile_rank(sorted_values: list[float], value: float) -> float:
    left = bisect_left(sorted_values, value)
    right = bisect_right(sorted_values, value)
    rank = left + max(1, right - left) * 0.5
    return clamp(rank / max(1, len(sorted_values)), 0.0, 1.0)


def _value_at_percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 50.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = clamp(pct, 0.0, 1.0) * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(len(sorted_values) - 1, lower + 1)
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def _calibration_blend_weight(player: Any) -> float:
    minutes = _display_minutes(_player_get(player, "minutes_projection"))
    if minutes >= 28:
        return 0.78
    if minutes >= 18:
        return 0.68
    if minutes >= 10:
        return 0.56
    if minutes >= 4:
        return 0.4
    return 0.24


def _trait_calibration_weight(base_weight: float, trait: TraitValue, previous: float, target: float) -> float:
    weight = float(base_weight)
    confidence = float(trait.confidence or 0.0)
    if confidence <= 0.28:
        weight = max(weight, 0.92)
    elif confidence <= 0.42:
        weight = max(weight, 0.82)
    if previous <= 5.0 and target >= 30.0:
        weight = max(weight, 0.94)
    return clamp(weight, 0.0, 0.96)


def _display_minutes(value: Any) -> float:
    minutes = maybe_float(value) or 0.0
    if minutes > 80:
        minutes = minutes / 82.0
    return clamp(minutes, 0.0, 42.0)


def _player_get(player: Any, key: str) -> Any:
    if player is None:
        return None
    if isinstance(player, dict):
        return player.get(key)
    return getattr(player, key, None)


def _rating_report_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": _maybe_int(row.get("Rank")),
        "player": row.get("Player"),
        "team": row.get("Team"),
        "pos": row.get("Pos"),
    }


def _maybe_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def build_traits_for_player(row: dict[str, Any], row_idx: int, player_id: str, percentiles: dict[str, dict[int, float]]) -> list[TraitValue]:
    role_off = str(row.get("primaryOffRole") or row.get("O_Role") or "")
    role_def = str(row.get("primaryDefRole") or row.get("d_role") or "")
    position = str(row.get("position") or row.get("Pos") or "")

    def p(field: str, inverse: bool = False) -> float | None:
        return percentile(percentiles, field, row_idx, inverse=inverse)

    def raw(field: str) -> float | None:
        return maybe_float(row.get(field))

    def role_boost(*needles: str, amount: float = 12.0) -> float:
        text = f"{role_off} {role_def}".lower()
        return amount if any(needle.lower() in text for needle in needles) else 0.0

    def playtype_pct(field: str) -> float | None:
        value = raw(field)
        if value is None:
            return None
        return clamp(value * 100 if value <= 1 else value)

    offscreen = playtype_pct("OffScreen%")
    handoff = playtype_pct("Handoff%")
    spotup = playtype_pct("SpotUp%")
    prbh = playtype_pct("Prbh%")
    iso = playtype_pct("Iso%")
    post = playtype_pct("Post%")
    cut = playtype_pct("Cut%")
    transition = playtype_pct("Transition%")
    putback = playtype_pct("Putback%")

    trait_specs: dict[str, tuple[float | None, float, list[str], str, dict[str, Any]]] = {}

    release_components = [p("3PAp75"), p("3P%"), p("OffScreen%"), p("Handoff%")]
    release_value = (mean(release_components) or 50.0) + role_boost("movement shooter", amount=18)
    trait_specs["release_speed"] = (
        release_value,
        confidence_from_fields(row, ["3PAp75", "3P%", "OffScreen%", "Handoff%"], base=0.18, cap=0.72),
        ["3PAp75", "3P%", "OffScreen%", "Handoff%"],
        "Inferred from movement-shooting role, three-point volume/accuracy, off-screen usage, and handoff usage.",
        {"components": release_components},
    )

    range_components = [p("3PAp75"), p("threePAr"), p("3P%")]
    range_value = (mean(range_components) or 50.0) + role_boost("movement shooter", "spot up", amount=8)
    trait_specs["shooting_range"] = (
        range_value,
        confidence_from_fields(row, ["3PAp75", "threePAr", "3P%"], base=0.25, cap=0.82),
        ["3PAp75", "threePAr", "3P%"],
        "Inferred from three-point attempt rate, attempts per 75, accuracy, and shooting role.",
        {"components": range_components},
    )

    playtype_values = [v for v in [offscreen, handoff, spotup, prbh, iso, post, cut, transition, putback] if v is not None]
    shot_versatility = clamp((len(playtype_values) / 9) * 55 + (mean(playtype_values) or 0) * 0.45)
    trait_specs["shot_versatility"] = (
        shot_versatility,
        round(min(0.84, 0.18 + len(playtype_values) / 9 * 0.66), 3),
        ["OffScreen%", "Handoff%", "SpotUp%", "Prbh%", "Iso%", "Post%", "Cut%", "Transition%", "Putback%"],
        "Inferred from breadth and usage of available play-type data.",
        {"playtype_count": len(playtype_values), "playtype_values": playtype_values},
    )

    rim_pressure_components = [p("FTr"), p("LT_06_PCT"), p("Prbh%"), p("Transition%"), p("boxCreationEst")]
    trait_specs["rim_pressure"] = (
        mean(rim_pressure_components),
        confidence_from_fields(row, ["FTr", "LT_06_PCT", "Prbh%", "Transition%", "boxCreationEst"], base=0.25, cap=0.8),
        ["FTr", "LT_06_PCT", "Prbh%", "Transition%", "boxCreationEst"],
        "Inferred from foul rate, close-shot efficiency, ball-handler usage, transition pressure, and creation.",
        {"components": rim_pressure_components},
    )

    handle_components = [p("boxCreationEst"), p("cTOVpct", inverse=True), p("PrbhPPP"), p("Prbh%"), p("touches")]
    trait_specs["handle_pressure"] = (
        mean(handle_components),
        confidence_from_fields(row, ["boxCreationEst", "cTOVpct", "PrbhPPP", "Prbh%", "touches"], base=0.18, cap=0.72),
        ["boxCreationEst", "cTOVpct", "PrbhPPP", "Prbh%", "touches"],
        "Inferred from creation, turnover avoidance, pick-and-roll/ball-handler efficiency, usage, and touches.",
        {"components": handle_components},
    )

    passing_components = [p("passerRating"), p("ASTp75"), p("boxCreationEst"), raw("BBallIQ")]
    trait_specs["passing_reads"] = (
        mean(passing_components),
        confidence_from_fields(row, ["passerRating", "ASTp75", "boxCreationEst", "BBallIQ"], base=0.24, cap=0.84),
        ["passerRating", "ASTp75", "boxCreationEst", "BBallIQ"],
        "Inferred from passer rating, assist creation, box creation, and existing basketball-IQ input.",
        {"components": passing_components},
    )

    agility_role = role_boost("on-ball guard", "disruptor", "versatile stopper", amount=10) + role_boost("mobile forward", amount=4)
    agility_components = [p("DEFLECTIONS"), p("STLpct"), p("VersatilityRating"), p("CraftedDPM")]
    trait_specs["foot_speed_lateral_agility"] = (
        (weighted_mean([(agility_components[0], 0.24), (agility_components[1], 0.24), (agility_components[2], 0.22), (agility_components[3], 0.3)]) or 50.0) + agility_role,
        confidence_from_fields(row, ["DEFLECTIONS", "STLpct", "VersatilityRating", "CraftedDPM"], base=0.16, cap=0.58),
        ["DEFLECTIONS", "STLpct", "VersatilityRating", "CraftedDPM", "primaryDefRole"],
        "Low-confidence proxy from defensive playmaking, defensive impact, versatility rating, and defensive role. Manual calibration is preferred for known foot-speed outliers.",
        {"components": agility_components},
    )

    stamina_components = [p("minutes"), p("2025minutes"), role_boost("movement shooter", "movement ball", amount=8)]
    trait_specs["stamina_cardio"] = (
        mean(stamina_components),
        confidence_from_fields(row, ["minutes", "2025minutes"], base=0.22, cap=0.62),
        ["minutes", "2025minutes", "primaryOffRole"],
        "Inferred from projected minutes, prior minutes, and movement-heavy offensive role.",
        {"components": stamina_components},
    )

    effort_boost = role_boost("disruptor", "on-ball", "versatile", amount=12)
    effort_components = [p("DEFLECTIONS"), p("STLpct"), p("CraftedDPM")]
    trait_specs["defensive_effort"] = (
        (mean(effort_components) or 50.0) + effort_boost,
        confidence_from_fields(row, ["DEFLECTIONS", "STLpct", "CraftedDPM"], base=0.24, cap=0.74),
        ["DEFLECTIONS", "STLpct", "CraftedDPM", "primaryDefRole"],
        "Inferred from event creation, defensive impact, and defensive role.",
        {"components": effort_components},
    )

    iq_boost = role_boost("connector", "rim protector", "primary ball handler", amount=8)
    iq_components = [raw("BBallIQ"), p("passerRating"), p("CraftedDPM")]
    trait_specs["scheme_iq"] = (
        (mean(iq_components) or 50.0) + iq_boost,
        confidence_from_fields(row, ["BBallIQ", "passerRating", "CraftedDPM"], base=0.2, cap=0.7),
        ["BBallIQ", "passerRating", "CraftedDPM", "role"],
        "Inferred from existing basketball-IQ input, passing reads, defensive impact, and role responsibility.",
        {"components": iq_components},
    )

    block_pctile = p("BLKpct")
    height_pctile = p("HeightSocks")
    rim_role = 0.0
    if "rim protector" in role_def.lower():
        rim_role = 16.0 if max(block_pctile or 0, height_pctile or 0) >= 82 else 6.0
    rim_components = [block_pctile, height_pctile, p("CraftedDPM"), p("DARKO")]
    trait_specs["rim_deterrence"] = (
        (weighted_mean([(rim_components[0], 0.55), (rim_components[1], 0.24), (rim_components[2], 0.15), (rim_components[3], 0.06)]) or 50.0) + rim_role,
        confidence_from_fields(row, ["BLKpct", "CraftedDPM", "DARKO", "HeightSocks"], base=0.28, cap=0.82),
        ["BLKpct", "CraftedDPM", "DARKO", "HeightSocks", "primaryDefRole"],
        "Inferred primarily from block rate and height, with smaller defensive-impact support. This intentionally separates rim deterrence from broad all-in-one defensive value.",
        {"components": rim_components},
    )

    screen_nav_role = 9 if any(word in role_def.lower() for word in ["guard", "disruptor", "stopper"]) and position != "C" else 0
    screen_nav_components = [p("DEFLECTIONS"), p("STLpct"), p("VersatilityRating"), p("CraftedDPM")]
    trait_specs["screen_navigation"] = (
        (weighted_mean([(screen_nav_components[0], 0.24), (screen_nav_components[1], 0.24), (screen_nav_components[2], 0.2), (screen_nav_components[3], 0.32)]) or 50.0) + screen_nav_role,
        confidence_from_fields(row, ["DEFLECTIONS", "STLpct", "VersatilityRating", "CraftedDPM"], base=0.12, cap=0.48),
        ["DEFLECTIONS", "STLpct", "VersatilityRating", "CraftedDPM", "primaryDefRole"],
        "Low-confidence proxy from guard/wing defensive role, activity, and versatility.",
        {"components": screen_nav_components},
    )

    oreb_components = [p("ORBp75"), p("ORBpct"), p("Putback%")]
    trait_specs["offensive_rebounding"] = (
        (mean(oreb_components) or 50.0) + role_boost("rollman", amount=8),
        confidence_from_fields(row, ["ORBp75", "ORBpct", "Putback%"], base=0.26, cap=0.82),
        ["ORBp75", "ORBpct", "Putback%", "primaryOffRole"],
        "Inferred from offensive rebounding rates, putback usage, and big/roll-man role.",
        {"components": oreb_components},
    )

    portability_components = [p("Portability"), p("threePAr"), p("CraftedDPM")]
    trait_specs["portability"] = (
        (mean(portability_components) or 50.0) + role_boost("spot up", "connector", "versatile", amount=10),
        confidence_from_fields(row, ["Portability", "threePAr", "CraftedDPM"], base=0.3, cap=0.86),
        ["Portability", "threePAr", "CraftedDPM", "role"],
        "Inferred from existing portability score, spacing, defense, and off-ball-friendly roles.",
        {"components": portability_components},
    )

    playoff_components = [
        trait_specs["handle_pressure"][0],
        trait_specs["shooting_range"][0],
        trait_specs["rim_pressure"][0],
        trait_specs["defensive_effort"][0],
        trait_specs["scheme_iq"][0],
        p("DARKO"),
        p("LEBRON"),
    ]
    trait_specs["playoff_translation"] = (
        mean(playoff_components),
        0.38,
        ["inferred_traits", "DARKO", "LEBRON"],
        "Low-confidence composite for whether the skill package is likely to survive targeted playoff game-planning.",
        {"components": playoff_components},
    )

    traits: list[TraitValue] = []
    for key, (value, confidence, fields, notes, components) in trait_specs.items():
        if value is None:
            value = 50.0
            confidence = min(confidence, 0.2)
            notes = f"{notes} Defaulted to neutral because source coverage was insufficient."
        traits.append(
            TraitValue(
                id=stable_id("trait", player_id, key),
                player_id=player_id,
                trait_key=key,
                label=TRAIT_LABELS[key],
                value=round(clamp(value), 2),
                confidence=round(confidence, 3),
                source_kind="inferred_trait_model_v1",
                source_ids=["src_player_skill_input_2025_26", "src_trait_method_v1"],
                last_verified=CANONICAL_START_DATE,
                notes=notes,
                components={"fields": fields, **components},
            )
        )
    return traits
