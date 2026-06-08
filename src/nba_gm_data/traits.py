from __future__ import annotations

from typing import Any

from .schema import CANONICAL_START_DATE, TraitValue
from .utils import clamp, confidence_from_fields, mean, maybe_float, percentile, stable_id


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


def weighted_mean(values: list[tuple[float | None, float]]) -> float | None:
    clean = [(float(value), weight) for value, weight in values if value is not None and weight > 0]
    total_weight = sum(weight for _, weight in clean)
    if not clean or total_weight <= 0:
        return None
    return sum(value * weight for value, weight in clean) / total_weight


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
