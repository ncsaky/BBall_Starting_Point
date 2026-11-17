"""Fit the offline chart reference; numpy is a build-only dependency."""

from collections import defaultdict
import json
from pathlib import Path

import numpy as np

from nba_gm_data.shot_chart import FEATURE_KEYS, REGIONS, court_grid, rating_vector
from nba_gm_data.spatial import player_spatial_profile
from nba_gm_data.utils import normalize_name


def main():
    root = Path(__file__).resolve().parents[1]
    source = json.loads((root / "data/research/shot_chart_reference.json").read_text())
    canonical = json.loads((root / "data/canonical/universe_2025_26_preseason.json").read_text())
    players = {normalize_name(row["name"]): row for row in canonical["players"]}
    traits = defaultdict(dict)
    for row in canonical["traits"]:
        traits[row["player_id"]][row["trait_key"]] = row["value"]
    grid = court_grid()
    coords = np.array([[(y - 250) / 10, (x - 52.5) / 10] for x, y, _ in grid])
    zone_ids = np.array([zone for _, _, zone in grid])
    reference = []
    league_rows = {int(row["Z"]): row for row in source["profiles"][0]["zones"]}
    league_total = sum(row["lFGA"] for row in league_rows.values())
    for row in source["profiles"]:
        player = players.get(normalize_name(row["name"]))
        if not player:
            raise ValueError(f"No canonical ratings match for {row['name']}")
        bins = np.array(row["bins"], dtype=float)
        distances = np.sum((coords[:, None, :] - bins[None, :, :2]) ** 2, axis=2)
        kernel = np.exp(-distances / (2 * 1.2**2))
        kernel *= zone_ids[:, None] == bins[None, :, 2]
        density = kernel @ bins[:, 3]
        zone_stats = {int(zone["Z"]): zone for zone in row["zones"]}
        deltas = {}
        shares = []
        for region, _, _ in REGIONS:
            mask = zone_ids == region
            observed = zone_stats.get(region, {})
            attempts = observed.get("FGA", 0)
            shares.append(attempts / max(1, row["attempts"]))
            subtotal = density[mask].sum()
            if subtotal:
                density[mask] *= shares[-1] / subtotal
            elif attempts and mask.any():
                density[mask] = shares[-1] / mask.sum()
            # Shrink tiny zone samples toward their own league percentage.
            deltas[str(region)] = round(observed.get("FGPCT_Delta", 0) * attempts / (attempts + 30), 4)
        spatial = player_spatial_profile(canonical, player)
        reference.append({"name": row["name"], "source_url": row["source_url"],
                          "attempts": row["attempts"], "ratings": rating_vector(traits[player["id"]], player["height_inches"]),
                          "density": density, "shares": shares, "deltas": deltas,
                          "grades": {key: value["efficiency"] for key, value in spatial["offense"].items()}})
    pooled = sum(row["density"] * row["attempts"] for row in reference)
    for region, _, _ in REGIONS:
        mask = zone_ids == region
        if not mask.any():
            continue
        pooled[mask] = (pooled[mask] + 0.0001) / (pooled[mask].sum() + mask.sum() * 0.0001) * league_rows[region]["lFGA"] / league_total
    values = np.array([row["shares"] for row in reference])
    transformed = np.log(values + 0.001)
    transformed -= transformed.mean(axis=1, keepdims=True)
    mean = transformed.mean(axis=0)
    _, singular, components = np.linalg.svd(transformed - mean, full_matrices=False)
    variance = singular**2 / sum(singular**2)
    ratings = np.array([row["ratings"] for row in reference])
    scales = np.maximum(ratings.std(axis=0), [8, 8, 8, 8, 8, 8, 8, 3])
    errors, null_errors = [], []
    for index, rating in enumerate(ratings):
        distances = np.mean(((ratings - rating) / scales) ** 2, axis=1)
        distances[index] = np.inf
        neighbors = np.argsort(distances)[:5]
        weights = np.exp(-distances[neighbors] / 0.65)
        weights /= weights.sum()
        prediction = weights @ values[neighbors]
        errors.append(float(np.abs(prediction - values[index]).sum() / 2))
        null_errors.append(float(np.abs(np.delete(values, index, axis=0).mean(axis=0) - values[index]).sum() / 2))
    league_defense = defaultdict(float)
    league_contest = defaultdict(float)
    total_weight = 0
    for player in canonical["players"]:
        weight = max(0, float(player.get("minutes_projection") or 0))
        total_weight += weight
        profile = player_spatial_profile(canonical, player)
        for key, zone in profile["defense"].items():
            league_defense[key] += zone["suppression"] * weight
            league_contest[key] += zone["contest"] * weight
    model = {
        "version": "shot_chart_15_v1", "season": source["season"], "retrieved_on": source["retrieved_on"],
        "feature_keys": FEATURE_KEYS, "feature_scales": scales.round(5).tolist(),
        "profiles": [{**row, "density": row["density"].round(7).tolist()} for row in reference],
        "league_density": pooled.round(7).tolist(),
        "league_zones": {str(key): {"frequency": round(row["lFGA"] / league_total, 7), "fg_pct": row["lFGPCT"]} for key, row in league_rows.items()},
        "league_defense_grades": {key: value / total_weight for key, value in league_defense.items()},
        "league_contest_grades": {key: value / total_weight for key, value in league_contest.items()},
        "pca": {"method": "centered log-ratio shot shares; exploratory, not a ratings-to-accuracy regression",
                "mean": mean.round(6).tolist(), "components": components[:6].round(6).tolist(),
                "explained_variance": variance[:6].round(6).tolist()},
        "validation": {"method": "leave-one-player-out; total variation distance of 15-zone shot shares",
                       "ratings_neighbors_mean_error": round(float(np.mean(errors)), 4),
                       "sample_mean_error": round(float(np.mean(null_errors)), 4)},
        "limitations": ["32-player archetype sample, not an unbiased league census.",
                        "Official chart league totals anchor regional frequency and FG%; within-region league cell density is estimated from the sample.",
                        "Historical 2024-25 shot facts combined with project's calibrated ratings; generated/current season charts are projections.",
                        "Defensive suppression is ratings-based, not scraped opponent FG data."],
    }
    (root / "data/research/shot_chart_model.json").write_text(json.dumps(model, separators=(",", ":")) + "\n")
    print(json.dumps({"players": len(reference), "attempts": sum(row["attempts"] for row in reference),
                      "grid_cells": len(grid), "pca_variance": variance[:6].sum(), "validation": model["validation"]}, indent=2))


if __name__ == "__main__":
    main()
