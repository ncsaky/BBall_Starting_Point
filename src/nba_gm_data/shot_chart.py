"""Fifteen-region chart projections, independent of gameplay's spatial grades."""

from functools import lru_cache
import json
import math
from pathlib import Path

from .utils import clamp, normalize_name
from .resource_paths import game_resource_root


MODEL_PATH = game_resource_root() / "data/research/shot_chart_model.json"
FEATURE_KEYS = (
    "shooting_range", "shot_versatility", "handle_pressure", "rim_pressure",
    "passing_reads", "portability", "offensive_rebounding", "height_inches",
)
REGIONS = (
    (1, "Inside 8 feet", "restricted_area"),
    (2, "Short range left", "short_mid_left"),
    (3, "Short range center", "paint_non_ra"),
    (4, "Short range right", "short_mid_right"),
    (5, "Midrange left baseline", "long_mid_left"),
    (6, "Midrange left wing", "long_mid_left"),
    (7, "Midrange center", "long_mid_center"),
    (8, "Midrange right wing", "long_mid_right"),
    (9, "Midrange right baseline", "long_mid_right"),
    (10, "Left corner three", "corner_three_left"),
    (11, "Left wing three", "above_break_left"),
    (12, "Center three", "above_break_center"),
    (13, "Right wing three", "above_break_right"),
    (14, "Right corner three", "corner_three_right"),
    (15, "Backcourt", "above_break_center"),
)
PERIMETER_REGION_IDS = frozenset({10, 11, 12, 13, 14, 15})


def region_at(lateral, forward):
    distance = math.hypot(lateral, forward)
    angle = math.degrees(math.atan2(lateral, max(forward, 0.001)))
    if forward >= 41.75:
        return 15
    if abs(lateral) >= 22 and forward < math.sqrt(23.75**2 - 22**2):
        return 10 if lateral < 0 else 14
    if distance >= 23.75:
        return 11 if angle < -18 else 13 if angle > 18 else 12
    if distance < 8:
        return 1
    if distance < 16:
        return 2 if angle < -30 else 4 if angle > 30 else 3
    return 5 if angle < -54 else 6 if angle < -18 else 9 if angle > 54 else 8 if angle > 18 else 7


@lru_cache(maxsize=1)
def court_grid():
    radius = 12.5
    step = radius * math.sqrt(3)
    cells = []
    row = 0
    y = radius
    while y < 500 - radius:
        x = radius + (step / 2 if row % 2 else 0)
        while x < 470 - radius:
            lateral, forward = (y - 250) / 10, (x - 52.5) / 10
            cells.append((round(x, 3), round(y, 3), region_at(lateral, forward)))
            x += step
        y += radius * 1.5
        row += 1
    return tuple(cells)


def rating_vector(traits, height=78):
    return [float(height) if key == "height_inches" else float(traits.get(key, 50)) for key in FEATURE_KEYS]


@lru_cache(maxsize=1)
def chart_model():
    if not MODEL_PATH.exists():
        return {}
    return json.loads(MODEL_PATH.read_text())


def _neighbors(vector, model):
    candidates = []
    for row in model.get("profiles", []):
        distance = sum(((value - reference) / scale) ** 2 for value, reference, scale in zip(vector, row["ratings"], model["feature_scales"])) / len(vector)
        candidates.append((distance, row))
    nearest = sorted(candidates, key=lambda item: item[0])[:5]
    weights = [math.exp(-distance / 0.65) for distance, _ in nearest]
    total = sum(weights) or 1
    return [(row, weight / total) for (_, row), weight in zip(nearest, weights)]


def project_player_chart(player, traits, profile):
    model = chart_model()
    if not model:
        return fallback_chart(profile)
    vector = rating_vector(traits, player.get("height_inches") or 78)
    neighbors = _neighbors(vector, model)
    matched = next((row for row in model["profiles"] if normalize_name(row["name"]) == normalize_name(player.get("name", ""))), None)
    if matched:
        # Preserve a real player's observed shot preference while allowing
        # development to move the projection toward new ratings neighbors.
        shift = sum(abs(a - b) / scale for a, b, scale in zip(vector, matched["ratings"], model["feature_scales"])) / len(vector)
        observed_weight = clamp(0.88 - shift * 0.30, 0.35, 0.88)
        neighbors = [(row, weight * (1 - observed_weight)) for row, weight in neighbors] + [(matched, observed_weight)]
    cells = [sum(row["density"][index] * weight for row, weight in neighbors) for index in range(len(court_grid()))]
    regions = []
    defense_density = []
    for region, label, key in REGIONS:
        baseline = model["league_zones"][str(region)]
        share = sum(row["shares"][region - 1] * weight for row, weight in neighbors)
        reference_grade = sum(row["grades"][key] * weight for row, weight in neighbors)
        observed_delta = sum(row["deltas"][str(region)] * weight for row, weight in neighbors)
        delta = clamp(observed_delta + (profile["offense"][key]["efficiency"] - reference_grade) * 0.35, -22, 22)
        defense_delta = (profile["defense"][key]["suppression"] - model["league_defense_grades"][key]) * 0.35
        regions.append({
            "id": region, "label": label, "frequency": round(share, 6),
            "league_frequency": baseline["frequency"], "league_fg_pct": baseline["fg_pct"],
            "fg_pct": round(clamp(baseline["fg_pct"] + delta, 0, 100), 2),
            "delta_pp": round(delta, 2), "suppression_delta_pp": round(defense_delta, 2),
        })
    cells, regions = condition_chart_on_season_shot_mix(player, cells, regions)
    region_keys = {region: key for region, _, key in REGIONS}
    for index, cell in enumerate(court_grid()):
        key = region_keys[cell[2]]
        contest_ratio = profile["defense"][key]["contest"] / max(1, model["league_contest_grades"][key])
        defense_density.append(model["league_density"][index] * contest_ratio)
    defense_total = sum(defense_density) or 1
    extra = _influence_layers(player, traits, profile, model, regions, region_keys)
    return {
        "version": model["version"], "regions": regions,
        "cells": [[*cell, round(cells[index], 7), round(defense_density[index] / defense_total, 7), model["league_density"][index],
                   *(round(layer[index], 7) for layer in extra)] for index, cell in enumerate(court_grid())],
        "views": ["scoring", "playmaking", "defense", "onball", "help"] if extra else ["scoring", "defense"],
        "basis": "projected", "reference_season": model["season"],
        "density_basis": "sample-conditioned league estimate",
        "comparables": [{"name": row["name"], "weight": round(weight, 3)} for row, weight in neighbors if weight >= 0.03],
    }


def _influence_layers(player, traits, profile, model, regions, region_keys):
    """Playmaking, on-ball and help-defense layers (court_influence). Adds per-region deltas in place and returns
    three cell-density layers: teammates' shots with him on court, his man's shots, other opponents' shots."""
    from .court_influence import damped, defense_group, help_suppression_delta, reweight, zone_group
    lifts = profile.get("playmaking")
    if not lifts:
        return []
    get = lambda key: float(traits.get(key, 50.0))
    help_delta = help_suppression_delta(get)
    by_region = {}
    for region in regions:
        key = region_keys[region["id"]]
        total = float(region.get("suppression_delta_pp") or 0.0)
        helping = help_delta[defense_group(key)]
        region["playmaking_delta_pp"] = round(float(lifts.get(zone_group(key), 0.0)), 2)
        region["help_delta_pp"] = round(helping, 2)
        region["onball_delta_pp"] = round(total - helping, 2)
        by_region[region["id"]] = region
    grid = court_grid()
    league = model["league_density"]
    playmaking = reweight(league, [damped(by_region[cell[2]]["playmaking_delta_pp"], 0.06) for cell in grid])
    # The man he guards: players his size shoot like players his size (height-neighbour comparables).
    height = float(player.get("height_inches") or 78)
    weights = [math.exp(-((height - row["ratings"][-1]) / 2.5) ** 2) for row in model["profiles"]]
    total_weight = sum(weights) or 1.0
    assignment = [sum(row["density"][index] * w for row, w in zip(model["profiles"], weights)) / total_weight for index in range(len(grid))]
    onball = reweight(assignment, [damped(by_region[cell[2]]["onball_delta_pp"], -0.05) for cell in grid])
    helping = reweight(league, [damped(by_region[cell[2]]["help_delta_pp"], -0.05) for cell in grid])
    return [playmaking, onball, helping]


def condition_chart_on_season_shot_mix(player, cells, regions):
    """Match projected court-volume markers to a reliable current-season sample."""
    stats = player.get("_save_stats") or {}
    try:
        minutes = float(stats.get("minutes") or 0.0)
        attempts = float(stats.get("fga") or 0.0)
        threes = float(stats.get("fg3a") or 0.0)
    except (TypeError, ValueError):
        return cells, regions
    if minutes < 200 or attempts < 50 or threes < 0 or threes > attempts:
        return cells, regions

    target_share = threes / attempts
    grid = court_grid()
    total = sum(max(0.0, density) for density in cells)
    if total <= 0:
        return cells, regions
    perimeter_share = sum(
        max(0.0, density)
        for cell, density in zip(grid, cells)
        if cell[2] in PERIMETER_REGION_IDS
    ) / total
    if perimeter_share <= 0 or perimeter_share >= 1:
        return cells, regions

    perimeter_scale = target_share / perimeter_share
    interior_scale = (1.0 - target_share) / (1.0 - perimeter_share)
    adjusted_cells = [
        max(0.0, density) * (perimeter_scale if cell[2] in PERIMETER_REGION_IDS else interior_scale)
        for cell, density in zip(grid, cells)
    ]
    adjusted_total = sum(adjusted_cells) or 1.0
    adjusted_cells = [density / adjusted_total for density in adjusted_cells]

    region_total = sum(max(0.0, float(region.get("frequency") or 0.0)) for region in regions) or 1.0
    region_perimeter_share = sum(
        max(0.0, float(region.get("frequency") or 0.0))
        for region in regions
        if int(region.get("id") or 0) in PERIMETER_REGION_IDS
    ) / region_total
    if 0 < region_perimeter_share < 1:
        region_perimeter_scale = target_share / region_perimeter_share
        region_interior_scale = (1.0 - target_share) / (1.0 - region_perimeter_share)
        adjusted_regions = [
            {
                **region,
                "frequency": max(0.0, float(region.get("frequency") or 0.0))
                * (region_perimeter_scale if int(region.get("id") or 0) in PERIMETER_REGION_IDS else region_interior_scale),
            }
            for region in regions
        ]
        adjusted_region_total = sum(region["frequency"] for region in adjusted_regions) or 1.0
        regions = [
            {**region, "frequency": round(region["frequency"] / adjusted_region_total, 6)}
            for region in adjusted_regions
        ]
    return adjusted_cells, regions


def fallback_chart(profile):
    regions = []
    cells = court_grid()
    counts = {region: sum(cell[2] == region for cell in cells) for region, _, _ in REGIONS}
    frequencies = {region: float(profile["offense"][key]["frequency"]) for region, _, key in REGIONS}
    total = sum(frequencies.values()) or 1
    for region, label, key in REGIONS:
        regions.append({"id": region, "label": label, "frequency": frequencies[region] / total,
                        "league_frequency": 1 / 15, "league_fg_pct": None, "fg_pct": None,
                        "delta_pp": 0, "suppression_delta_pp": 0})
    return {"version": "shot_chart_fallback", "regions": regions, "basis": "unavailable",
            "cells": [[*cell, frequencies[cell[2]] / total / counts[cell[2]], 1 / len(cells), 1 / len(cells)] for cell in cells]}


def combine_team_charts(weighted):
    total = sum(weight for _, weight in weighted) or 1
    charts = [(profile["shot_chart"], weight / total) for profile, weight in weighted]
    regions = []
    for index, (region, label, _) in enumerate(REGIONS):
        base = charts[0][0]["regions"][index]
        share = sum(chart["regions"][index]["frequency"] * weight for chart, weight in charts)
        # Efficiency must be weighted by attempts in this region, not just
        # minutes; a center's rare threes shouldn't dominate a team zone.
        delta = sum(chart["regions"][index]["delta_pp"] * chart["regions"][index]["frequency"] * weight for chart, weight in charts) / max(share, 1e-9)
        suppression = sum(chart["regions"][index]["suppression_delta_pp"] * weight for chart, weight in charts)
        regions.append({**base, "frequency": round(share, 6), "delta_pp": round(delta, 2),
                        "fg_pct": round(clamp(base["league_fg_pct"] + delta, 0, 100), 2) if base["league_fg_pct"] is not None else None,
                        "suppression_delta_pp": round(suppression, 2)})
    cells = [[*cell, round(sum(chart["cells"][index][3] * weight for chart, weight in charts), 7),
              round(sum(chart["cells"][index][4] * weight for chart, weight in charts), 7), charts[0][0]["cells"][index][5]] for index, cell in enumerate(court_grid())]
    basis = "projected" if any(chart.get("basis") == "projected" for chart, _ in charts) else "unavailable"
    return {"version": charts[0][0]["version"], "basis": basis, "regions": regions, "cells": cells,
            "reference_season": charts[0][0].get("reference_season"), "density_basis": "sample-conditioned league estimate"}
