"""Deterministic court-zone profiles shared by simulation, AI fit, and UI.

The semantic zone values are gameplay inputs. Rendering texture is derived from
the stable profile seed so visual distinctiveness never introduces game noise.
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from .utils import clamp, normalize_name
from .defense import COMPONENT_VERSION, zone_defense
from .shot_chart import combine_team_charts, fallback_chart, project_player_chart
from .court_influence import GROUPS as PLAYMAKING_GROUPS, playmaking_by_group, team_playmaking_grade, zone_group as playmaking_group


SPATIAL_PROFILE_VERSION = "spatial_profile_v1"
OFFICIAL_SPATIAL_PRIORS_FILE = Path(__file__).resolve().parents[2] / "data/research/player_shot_zones_2025_26.json"

ZONE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"key": "restricted_area", "label": "Restricted area", "x": 11, "y": 50, "group": "rim"},
    {"key": "paint_non_ra", "label": "Paint (non-RA)", "x": 23, "y": 50, "group": "rim"},
    {"key": "short_mid_left", "label": "Short mid left", "x": 29, "y": 31, "group": "midrange"},
    {"key": "short_mid_right", "label": "Short mid right", "x": 29, "y": 69, "group": "midrange"},
    {"key": "long_mid_left", "label": "Long mid left", "x": 43, "y": 23, "group": "midrange"},
    {"key": "long_mid_center", "label": "Long mid center", "x": 49, "y": 50, "group": "midrange"},
    {"key": "long_mid_right", "label": "Long mid right", "x": 43, "y": 77, "group": "midrange"},
    {"key": "corner_three_left", "label": "Left corner three", "x": 13, "y": 6, "group": "corner_three"},
    {"key": "above_break_left", "label": "Above-break three left", "x": 54, "y": 25, "group": "above_break_three"},
    {"key": "above_break_center", "label": "Above-break three center", "x": 62, "y": 50, "group": "above_break_three"},
    {"key": "above_break_right", "label": "Above-break three right", "x": 54, "y": 75, "group": "above_break_three"},
    {"key": "corner_three_right", "label": "Right corner three", "x": 13, "y": 94, "group": "corner_three"},
)
ZONE_KEYS = tuple(zone["key"] for zone in ZONE_DEFINITIONS)
ZONE_BY_KEY = {zone["key"]: zone for zone in ZONE_DEFINITIONS}
_SPATIAL_INDEX_CACHE: dict[int, dict[str, Any]] = {}
_SPATIAL_INDEX_CACHE_LIMIT = 4
_PLAYER_PROFILE_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_TEAM_PROFILE_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def invalidate_spatial_cache(canonical: dict[str, Any]) -> None:
    """Drop the mutable active universe's trait index after development."""
    _SPATIAL_INDEX_CACHE.pop(id(canonical), None)
    canonical.pop("_spatial_trait_index", None)


def _stable_unit(*parts: Any) -> float:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def _visual_pocket_position(entity_id: str, key: str, index: int, side: str) -> tuple[float, float, float, float]:
    """Place a deterministic local pocket inside a basketball-realistic zone."""
    zone = ZONE_BY_KEY[key]
    group = zone["group"]
    horizontal = _stable_unit(entity_id, side, key, index, "horizontal")
    vertical = _stable_unit(entity_id, side, key, index, "vertical")
    if group == "above_break_three":
        y = clamp(float(zone["y"]) + (vertical - 0.5) * 16.0, 10.0, 90.0)
        lateral_feet = (y - 50.0) * 0.5
        radius_feet = 23.75 + (horizontal - 0.5) * 2.2
        forward_feet = math.sqrt(max(0.0, radius_feet * radius_feet - lateral_feet * lateral_feet))
        x = clamp((5.25 + forward_feet) / 47.0 * 100.0, 45.0, 66.5)
        return x, y, 2.8, 5.2
    if group == "corner_three":
        x = clamp(float(zone["x"]) + (horizontal - 0.5) * 8.0, 7.0, 19.0)
        y = clamp(float(zone["y"]) + (vertical - 0.5) * 5.0, 2.5, 97.5)
        return x, y, 3.6, 3.0
    spread_x = 5.2 if group == "rim" else 5.8
    spread_y = 7.0 if group == "rim" else 7.8
    x = clamp(float(zone["x"]) + (horizontal - 0.5) * spread_x * 1.8, 4.0, 67.0)
    y = clamp(float(zone["y"]) + (vertical - 0.5) * spread_y * 1.8, 4.0, 96.0)
    return x, y, spread_x, spread_y


def _player_visual_pockets(
    player_id: str,
    offense: dict[str, dict[str, float]],
    defense: dict[str, dict[str, float]],
    creation_volume: float,
    defensive_activity: float,
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {"offense": [], "defense": []}
    for key in ZONE_KEYS:
        zone = ZONE_BY_KEY[key]
        shot_share = float(offense[key]["frequency"])
        offense_count = max(1, min(6, round(shot_share * 30)))
        defense_count = max(1, min(4, round(float(defense[key]["contest"]) / 27)))
        for side, count in (("offense", offense_count), ("defense", defense_count)):
            for index in range(count):
                x, y, spread_x, spread_y = _visual_pocket_position(player_id, key, index, side)
                texture = (_stable_unit(player_id, side, key, index, "grade") - 0.5) * 13.0
                if side == "offense":
                    frequency = shot_share / count * (0.35 + creation_volume / 92.0)
                    grade = clamp(float(offense[key]["efficiency"]) + texture, 1, 99)
                else:
                    frequency = (
                        float(defense[key]["contest"]) / 99.0 / len(ZONE_KEYS) / count
                        * (0.35 + defensive_activity / 92.0)
                    )
                    grade = clamp(float(defense[key]["suppression"]) + texture, 1, 99)
                output[side].append({
                    "zone_key": key,
                    "label": zone["label"],
                    "x": round(x, 3),
                    "y": round(y, 3),
                    "spread_x": round(spread_x, 3),
                    "spread_y": round(spread_y, 3),
                    "frequency": round(max(0.0001, frequency), 6),
                    "efficiency": round(grade, 2),
                    "source_player_id": player_id,
                })
    return output


def _trait_index(canonical: dict[str, Any]) -> dict[str, dict[str, float]]:
    cache_key = id(canonical)
    traits = canonical.get("traits", [])
    owned = canonical.get("_allow_internal_caches")
    cached = canonical.get("_spatial_trait_index") if owned else _SPATIAL_INDEX_CACHE.get(cache_key)
    if cached and cached.get("owner_id") == cache_key and cached.get("traits_source") is traits:
        return cached["traits"]
    output: dict[str, dict[str, float]] = {}
    for row in canonical.get("traits", []):
        player_id = str(row.get("player_id") or "")
        key = str(row.get("trait_key") or "")
        if player_id and key:
            output.setdefault(player_id, {})[key] = float(row.get("value") or 50.0)
    cached = {"owner_id": cache_key, "traits_source": traits, "traits": output}
    if owned:
        canonical["_spatial_trait_index"] = cached
    else:
        # Plain caller dictionaries stay unmodified, with a small bounded
        # fallback rather than retaining 128 whole trait collections.
        if len(_SPATIAL_INDEX_CACHE) >= _SPATIAL_INDEX_CACHE_LIMIT:
            _SPATIAL_INDEX_CACHE.pop(next(iter(_SPATIAL_INDEX_CACHE)))
        _SPATIAL_INDEX_CACHE[cache_key] = cached
    return output


_PLAYMAKING_MEAN_CACHE: dict[tuple, dict[str, float]] = {}


def league_playmaking_mean(canonical: dict[str, Any]) -> dict[str, float]:
    """Minutes-weighted playmaking of every rostered player (weighted the way team profiles weight them): the zero
    point, so the playmaking term moves teams relative to each other without shifting league scoring."""
    traits = _trait_index(canonical)
    players = canonical.get("players", [])
    key = (id(traits), len(players), str((canonical.get("meta") or {}).get("current_date")))
    cached = _PLAYMAKING_MEAN_CACHE.get(key)
    if cached is not None:
        return cached
    totals = {group: 0.0 for group in PLAYMAKING_GROUPS}
    weight_total = 0.0
    for player in players:
        minutes = float(player.get("minutes_projection") or 0.0)
        if not player.get("team_id") or minutes <= 0:
            continue
        row = traits.get(str(player.get("id")), {})
        lifts = playmaking_by_group(lambda name, row=row: float(row.get(name, 50.0)), float(player.get("height_inches") or 78.0))
        for group in PLAYMAKING_GROUPS:
            totals[group] += lifts[group] * minutes
        weight_total += minutes
    mean = {group: round(totals[group] / weight_total, 3) if weight_total else 0.0 for group in PLAYMAKING_GROUPS}
    if len(_PLAYMAKING_MEAN_CACHE) >= 8:
        _PLAYMAKING_MEAN_CACHE.clear()
    _PLAYMAKING_MEAN_CACHE[key] = mean
    return mean


@lru_cache(maxsize=1)
def official_spatial_priors() -> dict[str, dict[str, Any]]:
    # The current research artifact documents sources but contains no matched
    # profiles. Runtime file access was therefore pure overhead, and on a
    # file-provider-backed workspace could stall a simulation for tens of
    # seconds. Future matched priors belong in the canonical build artifact.
    return {}


def player_spatial_profile(canonical: dict[str, Any], player: dict[str, Any] | str, *, include_chart: bool = False) -> dict[str, Any]:
    if isinstance(player, str):
        player = next((row for row in canonical.get("players", []) if str(row.get("id")) == player), {})
    player_id = str(player.get("id") or player.get("player_id") or player.get("name") or "unknown")
    traits = _trait_index(canonical).get(player_id, {})
    get = lambda key, default=50.0: float(traits.get(key, default))
    shooting = (get("shooting_range") * 0.45 + get("shot_versatility") * 0.35 + get("release_speed") * 0.20)
    creation = (get("handle_pressure") * 0.48 + get("shot_versatility") * 0.37 + get("passing_reads") * 0.15)
    rim_pressure = get("rim_pressure")
    portability = get("portability")
    defense_effort = get("defensive_effort")
    scheme = get("scheme_iq")
    lateral = get("foot_speed_lateral_agility")
    navigation = get("screen_navigation")
    rim_defense = get("rim_deterrence")
    height = float(player.get("height_inches") or 78.0)
    position = str(player.get("position") or "").upper()
    usage = clamp(35 + float(player.get("minutes_projection") or player.get("prior_minutes") or 18) * 1.1 + (creation - 50) * 0.22, 20, 92)
    prior = official_spatial_priors().get(normalize_name(player.get("name", "")))
    season_stats = player.get("_save_stats") or {}
    season_shot_sample = {
        key: season_stats.get(key)
        for key in ("games", "minutes", "fga", "fg3a")
    }
    from .offense import enabled as offense_enabled, offensive_profile
    offensive = offensive_profile(canonical, player, traits) if offense_enabled(canonical) else None
    playmaking_zero = league_playmaking_mean(canonical)
    signature = hashlib.sha256(json.dumps({
        "version": SPATIAL_PROFILE_VERSION,
        "defensive_components": COMPONENT_VERSION,
        "playmaking_zero": playmaking_zero,
        "player_id": player_id,
        "position": position,
        "height": height,
        "role_minutes": float(player.get("minutes_projection") or player.get("prior_minutes") or 18),
        "age": player.get("age"),
        "traits": sorted((key, round(float(value), 3)) for key, value in traits.items()),
        "prior": prior,
        "season_shot_sample": season_shot_sample,
        **({'offensive_profile': offensive} if offensive else {}),
    }, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    cache_key = (player_id, signature)
    if cache_key in _PLAYER_PROFILE_CACHE:
        cached = _PLAYER_PROFILE_CACHE[cache_key]
        if include_chart and "shot_chart" not in cached:
            cached["shot_chart"] = project_player_chart(player, traits, cached)
        return cached

    weights: dict[str, float] = {}
    for key in ZONE_KEYS:
        side = (_stable_unit(player_id, key, "side") - 0.5) * 3.2
        if key == "restricted_area":
            value = 14 + rim_pressure * 0.46 + max(0.0, height - 78) * 0.8 - shooting * 0.07
        elif key == "paint_non_ra":
            value = 9 + rim_pressure * 0.19 + get("offensive_rebounding") * 0.08 + max(0.0, height - 80) * 0.45
        elif key.startswith("short_mid"):
            value = 7 + get("shot_versatility") * 0.12 + creation * 0.05 + side
        elif key.startswith("long_mid"):
            value = 5 + get("shot_versatility") * 0.11 + creation * 0.07 - shooting * 0.025 + side
        elif key.startswith("corner_three"):
            value = 4 + shooting * 0.15 + portability * 0.07 - max(0.0, creation - 72) * 0.025 + side
        else:
            value = 5 + shooting * 0.18 + creation * 0.075 + max(0.0, usage - 62) * 0.045 + side
        if ZONE_BY_KEY[key]["group"] in {"corner_three", "above_break_three"}:
            value *= clamp((shooting - 25) / 65, 0.12, 1.16)
        if "C" in position and key.startswith("above_break"):
            value -= max(0.0, 64 - shooting) * 0.08
        weights[key] = max(0.5, value)

    source_ids = ["src_trait_method_v1", "src_spatial_model_v1"]
    confidence = 0.58
    if prior:
        prior_frequency = prior.get("frequency", {})
        for key in ZONE_KEYS:
            if key in prior_frequency:
                weights[key] = weights[key] * 0.35 + max(0.0, float(prior_frequency[key])) * 100.0 * 0.65
        source_ids.extend(prior.get("source_ids") or ["src_nba_stats_shot_zones_2025_26"])
        confidence = 0.82
    if offensive:
        threes = [k for k in ZONE_KEYS if ZONE_BY_KEY[k]['group'] in {'corner_three', 'above_break_three'}]
        three_share = clamp(offensive['three_per36']/16, 0, .72)
        three_total = sum(weights[k] for k in threes) or 1
        other_total = sum(weights[k] for k in ZONE_KEYS if k not in threes) or 1
        weights = {k: weights[k]*three_share/three_total if k in threes
                   else weights[k]*(1-three_share)/other_total for k in ZONE_KEYS}
    total = sum(weights.values()) or 1.0
    frequency = {key: weights[key] / total for key in ZONE_KEYS}

    offense: dict[str, dict[str, float]] = {}
    defense: dict[str, dict[str, float]] = {}
    defensive_zones = zone_defense(get)
    for key in ZONE_KEYS:
        jitter = (_stable_unit(player_id, key, SPATIAL_PROFILE_VERSION) - 0.5) * 5.0
        group = ZONE_BY_KEY[key]["group"]
        if group == "rim":
            efficiency = 31 + rim_pressure * 0.55 + max(0.0, height - 78) * 0.65 + jitter
            if offensive:
                if key == 'paint_non_ra':
                    efficiency = 30+.40*offensive['post_creation']+.18*offensive['assisted_finishing']+jitter
                else:
                    efficiency = 35+.50*offensive['assisted_finishing']+max(0, height-78)*.5+jitter
            gravity = 24 + rim_pressure * 0.58 + creation * 0.18 + usage * 0.12 + jitter * 0.35
        elif group == "midrange":
            efficiency = 25 + get("shot_versatility") * 0.47 + creation * 0.17 + jitter
            gravity = 25 + get("shot_versatility") * 0.35 + creation * 0.26 + usage * 0.08 + jitter * 0.35
        else:
            efficiency = 20 + shooting * 0.66 + get("shot_versatility") * 0.08 + jitter
            gravity = 18 + shooting * 0.58 + creation * 0.14 + portability * 0.12 + jitter * 0.35
        suppression, contest = defensive_zones[group if group in {'rim', 'midrange'} else 'perimeter']
        suppression += jitter * .25
        offense[key] = {
            "frequency": round(frequency[key], 5),
            "efficiency": round(clamp(efficiency, 1, 99), 2),
            "gravity": round(clamp(gravity, 1, 99), 2),
            "intensity": round(clamp(efficiency * 0.46 + gravity * 0.36 + min(99.0, frequency[key] * 700) * 0.18, 1, 99), 2),
        }
        defense[key] = {
            "frequency_influence": round(clamp(50 + (suppression - 50) * -0.34, 1, 99), 2),
            "contest": round(clamp(contest, 1, 99), 2),
            "suppression": round(clamp(suppression, 1, 99), 2),
            "intensity": round(clamp(suppression * 0.62 + contest * 0.38, 1, 99), 2),
        }
    creation_volume = clamp(
        usage * 0.52
        + creation * 0.28
        + sum(row["gravity"] for row in offense.values()) / len(offense) * 0.20,
        10,
        99,
    )
    defensive_activity = clamp(
        defense_effort * 0.35
        + scheme * 0.20
        + lateral * 0.15
        + navigation * 0.15
        + rim_defense * 0.15,
        10,
        99,
    )
    visual_pockets = _player_visual_pockets(
        player_id,
        offense,
        defense,
        creation_volume,
        defensive_activity,
    )
    result = {
        "version": SPATIAL_PROFILE_VERSION,
        "entity_type": "player",
        "entity_id": player_id,
        "seed": signature[:16],
        "input_signature": signature,
        "zones": list(ZONE_DEFINITIONS),
        "offense": offense,
        "defense": defense,
        "creation_volume": round(creation_volume, 2),
        "defensive_activity": round(defensive_activity, 2),
        "visual_pockets": visual_pockets,
        "playmaking": {group: round(value - playmaking_zero[group], 3) for group, value in playmaking_by_group(get, height).items()},
        "confidence": confidence,
        "source_ids": sorted(dict.fromkeys(source_ids)),
    }
    if include_chart:
        result["shot_chart"] = project_player_chart(player, traits, result)
    if len(_PLAYER_PROFILE_CACHE) >= 4096:
        _PLAYER_PROFILE_CACHE.clear()
    _PLAYER_PROFILE_CACHE[cache_key] = result
    return result


def prospect_spatial_profile(canonical: dict[str, Any], prospect: dict[str, Any], *, include_chart: bool = False) -> dict[str, Any]:
    ability = float(prospect.get("current_ability") or prospect.get("now") or 50.0)
    archetype = str(prospect.get("archetype") or "").lower()
    position = str(prospect.get("position") or "SF")
    traits = {
        "shooting_range": ability,
        "shot_versatility": ability,
        "release_speed": ability,
        "rim_pressure": ability,
        "handle_pressure": ability,
        "passing_reads": ability,
        "defensive_effort": ability,
        "scheme_iq": ability,
        "rim_deterrence": ability,
        "screen_navigation": ability,
        "foot_speed_lateral_agility": ability,
        "offensive_rebounding": ability,
        "portability": ability,
    }
    boosts = {
        "movement_shooter": {"shooting_range": 18, "release_speed": 16, "portability": 12},
        "stretch_big": {"shooting_range": 14, "rim_deterrence": 8},
        "lead_creator": {"handle_pressure": 16, "passing_reads": 14, "shot_versatility": 12},
        "scoring_wing": {"shot_versatility": 14, "rim_pressure": 8, "shooting_range": 8},
        "rim_pressure_guard": {"rim_pressure": 18, "handle_pressure": 10},
        "rim_protecting_big": {"rim_deterrence": 20, "offensive_rebounding": 12},
        "two_way_wing": {"defensive_effort": 14, "screen_navigation": 12, "portability": 10},
    }.get(archetype, {})
    for key, boost in boosts.items():
        traits[key] = clamp(traits[key] + boost, 1, 99)
    player_id = str(prospect.get("id") or prospect.get("name") or "prospect")
    # Prospect profiles only consume the synthetic traits above. Carrying the
    # full league trait ledger here forced a fresh 10k-row index for every
    # prospect/team fit comparison during draft generation.
    local = {
        "traits": [
            {"player_id": player_id, "trait_key": key, "value": value}
            for key, value in traits.items()
        ],
        "_allow_internal_caches": True,
    }
    return player_spatial_profile(local, {
        "id": player_id,
        "name": prospect.get("name"),
        "position": position,
        "height_inches": prospect.get("height_inches"),
        "minutes_projection": 24,
    }, include_chart=include_chart)


def team_spatial_profile(
    canonical: dict[str, Any],
    team_id: str,
    minutes: dict[str, float] | None = None,
    health_states: Iterable[dict[str, Any]] | dict[str, dict[str, Any]] | None = None,
    roster: list[dict[str, Any]] | None = None,
    *,
    include_chart: bool = False,
) -> dict[str, Any]:
    roster = roster if roster is not None else [row for row in canonical.get("players", []) if str(row.get("team_id")) == str(team_id)]
    health_by_player = health_states if isinstance(health_states, dict) else {
        str(row.get("player_id")): row for row in (health_states or canonical.get("player_health_states", []))
    }
    weighted: list[tuple[dict[str, Any], float]] = []
    for player in roster:
        player_id = str(player.get("id") or "")
        state = health_by_player.get(player_id, {}) if isinstance(health_by_player, dict) else {}
        if str(state.get("availability_status") or "active").lower() not in {"active", "available", "healthy"}:
            continue
        weight = float((minutes or {}).get(player_id, player.get("minutes_projection") or player.get("prior_minutes") or 0.0))
        if weight > 0:
            weighted.append((player_spatial_profile(canonical, player, include_chart=include_chart), weight))
    if not weighted:
        weighted = [(neutral_spatial_profile(team_id), 1.0)]
    total_weight = sum(weight for _, weight in weighted) or 1.0
    signature = hashlib.sha256(json.dumps({
        "version": SPATIAL_PROFILE_VERSION,
        "team_id": team_id,
        "rotation": sorted((profile.get("input_signature") or profile.get("entity_id"), round(weight, 3)) for profile, weight in weighted),
    }, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    cache_key = (str(team_id), signature)
    if cache_key in _TEAM_PROFILE_CACHE:
        cached = _TEAM_PROFILE_CACHE[cache_key]
        if include_chart and "shot_chart" not in cached:
            cached["shot_chart"] = combine_team_charts(weighted)
        return cached
    offense: dict[str, dict[str, float]] = {}
    defense: dict[str, dict[str, float]] = {}
    non_shooter_share = sum(
        weight for profile, weight in weighted
        if _perimeter_average(profile, "offense", "gravity") < 48
    ) / total_weight
    perimeter_gravity = sum(_perimeter_average(profile, "offense", "gravity") * weight for profile, weight in weighted) / total_weight
    creators = sum(1 for profile, weight in weighted if weight >= 14 and _perimeter_average(profile, "offense", "gravity") >= 62)
    creation_volume = sum(float(profile.get("creation_volume", 50.0)) * weight for profile, weight in weighted) / total_weight
    defensive_activity = sum(float(profile.get("defensive_activity", 50.0)) * weight for profile, weight in weighted) / total_weight
    # Rotation-weighted team averages naturally bunch together. Expand their
    # practical range for the visual frequency channel without touching the
    # semantic zone values consumed by simulation and AI fit.
    creation_volume = clamp(20 + (creation_volume - 40) * 2.5, 10, 99)
    defensive_activity = clamp(20 + (defensive_activity - 40) * 2.5, 10, 99)
    # Playmaking: each player's effect on his teammates' shooting by zone (court_influence) while he plays.
    playmaking_lifts = [(profile.get("playmaking") or {}, weight) for profile, weight in weighted]
    playmaking_grade = {group: team_playmaking_grade(playmaking_lifts, total_weight, group) for group in PLAYMAKING_GROUPS}
    for key in ZONE_KEYS:
        frequency = sum(profile["offense"][key]["frequency"] * weight for profile, weight in weighted) / total_weight
        efficiency = sum(profile["offense"][key]["efficiency"] * weight for profile, weight in weighted) / total_weight
        gravity = sum(profile["offense"][key]["gravity"] * weight for profile, weight in weighted) / total_weight
        suppression = sum(profile["defense"][key]["suppression"] * weight for profile, weight in weighted) / total_weight
        contest = sum(profile["defense"][key]["contest"] * weight for profile, weight in weighted) / total_weight
        group = ZONE_BY_KEY[key]["group"]
        efficiency += playmaking_grade[playmaking_group(key)]
        if group == "rim":
            efficiency -= clamp((non_shooter_share - 0.38) * 12.0, 0, 5.0)
            gravity -= clamp((non_shooter_share - 0.42) * 10.0, 0, 4.0)
        elif group in {"corner_three", "above_break_three"}:
            gravity += clamp((perimeter_gravity - 55) * 0.10 + max(0, creators - 2) * 0.7, -2.5, 4.0)
        offense[key] = {
            "frequency": round(frequency, 5),
            "efficiency": round(clamp(efficiency, 1, 99), 2),
            "gravity": round(clamp(gravity, 1, 99), 2),
            "intensity": round(clamp(efficiency * 0.46 + gravity * 0.36 + min(99.0, frequency * 700) * 0.18, 1, 99), 2),
        }
        defense[key] = {
            "frequency_influence": round(clamp(50 + (suppression - 50) * -0.34, 1, 99), 2),
            "contest": round(clamp(contest, 1, 99), 2),
            "suppression": round(clamp(suppression, 1, 99), 2),
            "intensity": round(clamp(suppression * 0.62 + contest * 0.38, 1, 99), 2),
        }
    frequency_total = sum(row["frequency"] for row in offense.values()) or 1.0
    for row in offense.values():
        row["frequency"] = round(row["frequency"] / frequency_total, 5)
    visual_pockets: dict[str, list[dict[str, Any]]] = {"offense": [], "defense": []}
    for profile, weight in weighted:
        rotation_share = weight / total_weight
        profile_pockets = profile.get("visual_pockets", {})
        for side in ("offense", "defense"):
            for pocket in profile_pockets.get(side, []):
                row = dict(pocket)
                row["frequency"] = round(float(row.get("frequency") or 0.0) * rotation_share, 7)
                row["rotation_share"] = round(rotation_share, 5)
                visual_pockets[side].append(row)
    for side in ("offense", "defense"):
        visual_pockets[side].sort(key=lambda row: float(row.get("frequency") or 0.0), reverse=True)
        visual_pockets[side] = visual_pockets[side][:180]
    result = {
        "version": SPATIAL_PROFILE_VERSION,
        "entity_type": "team",
        "entity_id": team_id,
        "seed": signature[:16],
        "input_signature": signature,
        "zones": list(ZONE_DEFINITIONS),
        "offense": offense,
        "defense": defense,
        "creation_volume": round(clamp(creation_volume, 10, 99), 2),
        "defensive_activity": round(clamp(defensive_activity, 10, 99), 2),
        "visual_pockets": visual_pockets,
        "rotation_minutes": round(total_weight, 2),
        "confidence": round(sum(profile.get("confidence", 0.5) * weight for profile, weight in weighted) / total_weight, 3),
        "source_ids": sorted({source for profile, _ in weighted for source in profile.get("source_ids", [])}),
    }
    if include_chart:
        result["shot_chart"] = combine_team_charts(weighted)
    if len(_TEAM_PROFILE_CACHE) >= 1024:
        _TEAM_PROFILE_CACHE.clear()
    _TEAM_PROFILE_CACHE[cache_key] = result
    return result


def neutral_spatial_profile(entity_id: str = "neutral") -> dict[str, Any]:
    frequency = 1.0 / len(ZONE_KEYS)
    offense = {key: {"frequency": frequency, "efficiency": 50.0, "gravity": 50.0, "intensity": 50.0} for key in ZONE_KEYS}
    defense = {key: {"frequency_influence": 50.0, "contest": 50.0, "suppression": 50.0, "intensity": 50.0} for key in ZONE_KEYS}
    result = {
        "version": SPATIAL_PROFILE_VERSION,
        "entity_type": "neutral",
        "entity_id": entity_id,
        "zones": list(ZONE_DEFINITIONS),
        "offense": offense,
        "defense": defense,
        "creation_volume": 50.0,
        "defensive_activity": 50.0,
        "visual_pockets": _player_visual_pockets(entity_id, offense, defense, 50.0, 50.0),
        "confidence": 0.2,
        "source_ids": ["src_spatial_model_v1"],
    }
    result["shot_chart"] = fallback_chart(result)
    return result


def flatten_spatial_profile(profile: dict[str, Any]) -> dict[str, float]:
    flat: dict[str, float] = {}
    for key in ZONE_KEYS:
        for metric in ("frequency", "efficiency", "gravity", "intensity"):
            flat[f"sp_off_{key}_{metric}"] = float(profile["offense"][key][metric])
        for metric in ("frequency_influence", "contest", "suppression", "intensity"):
            flat[f"sp_def_{key}_{metric}"] = float(profile["defense"][key][metric])
    return flat


def spatial_profile_from_features(features: dict[str, float], entity_id: str = "features") -> dict[str, Any]:
    profile = neutral_spatial_profile(entity_id)
    for key in ZONE_KEYS:
        for metric in profile["offense"][key]:
            feature_key = f"sp_off_{key}_{metric}"
            if feature_key in features:
                profile["offense"][key][metric] = float(features[feature_key])
        for metric in profile["defense"][key]:
            feature_key = f"sp_def_{key}_{metric}"
            if feature_key in features:
                profile["defense"][key][metric] = float(features[feature_key])
    profile["creation_volume"] = float(features.get("sp_off_creation_volume", 50.0))
    profile["defensive_activity"] = float(features.get("sp_def_activity", 50.0))
    profile["visual_pockets"] = _player_visual_pockets(
        entity_id,
        profile["offense"],
        profile["defense"],
        profile["creation_volume"],
        profile["defensive_activity"],
    )
    profile["shot_chart"] = fallback_chart(profile)
    return profile


def spatial_matchup_adjustment(offense: dict[str, Any], defense: dict[str, Any]) -> dict[str, Any]:
    group_values: dict[str, list[tuple[float, float]]] = {"rim": [], "midrange": [], "corner_three": [], "above_break_three": []}
    quality = 0.0
    for key in ZONE_KEYS:
        off = offense["offense"][key]
        deff = defense["defense"][key]
        advantage = (float(off["efficiency"]) - 50) * 0.018 + (float(off["gravity"]) - 50) * 0.010 - (float(deff["suppression"]) - 50) * 0.016
        share_delta = clamp(advantage * 0.004, -0.01, 0.01)
        group_values[ZONE_BY_KEY[key]["group"]].append((share_delta, float(off["frequency"])))
        quality += advantage * float(off["frequency"])
    category_delta = {
        group: round(clamp(sum(delta * max(0.5, share * len(values)) for delta, share in values), -0.04, 0.04), 5)
        for group, values in group_values.items()
    }
    return {"category_delta": category_delta, "shot_quality_delta": round(clamp(quality * 0.19, -1.5, 1.5), 4)}


def with_spatial_fit_context(canonical: dict[str, Any]) -> dict[str, Any]:
    """Prepare team profiles for one immutable batch of trade evaluations.

    Keep these on a disposable view: later roster or health changes must start
    a new batch rather than reusing these profiles.
    """
    return {**canonical, "_spatial_fit_team_profiles": {
        str(team["id"]): team_spatial_profile(canonical, str(team["id"]))
        for team in canonical.get("teams", [])
    }}


def spatial_fit_delta(canonical: dict[str, Any], team_id: str, player: dict[str, Any], cap: float = 3.0) -> float:
    team = (canonical.get("_spatial_fit_team_profiles") or {}).get(str(team_id))
    if team is None:
        team = team_spatial_profile(canonical, team_id)
    candidate = player_spatial_profile(canonical, player)
    perimeter_need = max(0.0, 58 - _perimeter_average(team, "offense", "gravity"))
    rim_need = max(0.0, 58 - _group_average(team, "defense", "suppression", "rim"))
    perimeter_value = _perimeter_average(candidate, "offense", "gravity") - 50
    rim_value = _group_average(candidate, "defense", "suppression", "rim") - 50
    general_offense_gap = max(0.0, 55 - _all_average(team, "offense", "intensity"))
    general_defense_gap = max(0.0, 55 - _all_average(team, "defense", "intensity"))
    value = (
        perimeter_need * perimeter_value * 0.0045
        + rim_need * rim_value * 0.0045
        + general_offense_gap * (_all_average(candidate, "offense", "intensity") - 50) * 0.0025
        + general_defense_gap * (_all_average(candidate, "defense", "intensity") - 50) * 0.0025
    )
    if perimeter_need < 2 and perimeter_value > 18:
        value -= (perimeter_value - 18) * 0.018
    return round(clamp(value, -cap, cap), 3)


def prospect_spatial_fit_delta(canonical: dict[str, Any], team_id: str, prospect: dict[str, Any], cap: float = 6.0) -> float:
    profile = prospect_spatial_profile(canonical, prospect)
    team = team_spatial_profile(canonical, team_id)
    perimeter_need = max(0.0, 58 - _perimeter_average(team, "offense", "gravity"))
    rim_need = max(0.0, 58 - _group_average(team, "defense", "suppression", "rim"))
    value = perimeter_need * (_perimeter_average(profile, "offense", "gravity") - 50) * 0.009
    value += rim_need * (_group_average(profile, "defense", "suppression", "rim") - 50) * 0.009
    return round(clamp(value, -cap, cap), 3)


def _group_average(profile: dict[str, Any], side: str, metric: str, group: str) -> float:
    keys = [key for key in ZONE_KEYS if ZONE_BY_KEY[key]["group"] == group]
    return sum(float(profile[side][key][metric]) for key in keys) / max(1, len(keys))


def _perimeter_average(profile: dict[str, Any], side: str, metric: str) -> float:
    keys = [key for key in ZONE_KEYS if ZONE_BY_KEY[key]["group"] in {"corner_three", "above_break_three"}]
    return sum(float(profile[side][key][metric]) for key in keys) / max(1, len(keys))


def _all_average(profile: dict[str, Any], side: str, metric: str) -> float:
    return sum(float(profile[side][key][metric]) for key in ZONE_KEYS) / len(ZONE_KEYS)
