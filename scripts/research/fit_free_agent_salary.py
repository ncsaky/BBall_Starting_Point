#!/usr/bin/env python3
"""Fit opening free-agent asks and print player-grouped held-out comparisons.

From the repo root:
  PYTHONPATH=src .venv/bin/python scripts/research/fit_free_agent_salary.py --write-fit
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
import unicodedata

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.cap_rules import max_salary_share
from nba_gm_data.contract_ai import (
    FITTED_FREE_AGENT_TIERS,
    asking_multiplier,
    build_player_contract_market_profiles,
    clamp_salary_to_role,
    contract_role_tier,
    default_contract_market_config,
    free_agent_salary_fit_features,
    free_agent_salary_fit_millions,
    model_expected_aav,
    valuation_for_player,
    years_of_service,
)
from nba_gm_data.ratings_model import install_inputs_model
from nba_gm_data.save import display_minutes_projection
from nba_gm_data.sim import player_feature_vector
from nba_gm_data.transactions import contract_for_player, with_transaction_context

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "data/research/free_agent_contracts_2025_2026.json"
FIT = ROOT / "data/canonical/free_agent_salary_fit.json"
FOLDS = 5
RIDGE_PENALTY = 2.0
FEATURE_NAMES = (
    "intercept", "on_court_value_per_10", "age_per_5", "age_over_32_per_5",
    "service_per_5", "contract_years", "starter_or_higher", "specialist_or_high_end_starter_or_star",
)


def name_key(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name.casefold())
    return "".join(char for char in plain if char.isascii() and char.isalnum()).removesuffix("jr")


def collect_evidence() -> list[dict]:
    research = json.loads(EVIDENCE.read_text())
    canonical = load_app_canonical(ROOT)
    install_inputs_model(canonical, ROOT)
    canonical = with_transaction_context(canonical)
    players = {name_key(player["name"]): player for player in canonical["players"]}
    profiles = {profile.player_id: profile for profile in build_player_contract_market_profiles(canonical)}
    config = default_contract_market_config()
    result = []
    for row in research["contracts"]:
        if row["kind"] != "free_agent_or_resign":
            continue
        player = players[name_key(row["player"])]
        summer = row["summer"]
        season = f"{summer}-{(summer + 1) % 100:02}"
        value = valuation_for_player(canonical, player)
        features = player_feature_vector(canonical, player).features
        tier = contract_role_tier(player, value, features)
        age = round(float(player.get("display_age") or player.get("age") or 27.0)) + summer - 2026
        service = years_of_service({**player, "display_age": age}, season)
        cap = research["cap_rules"][season]["salary_cap"]
        contract = contract_for_player(canonical, player["id"]) or {}
        old_expected = clamp_salary_to_role(model_expected_aav(player, value, features, contract, tier, config), tier, config)
        old_ask = clamp_salary_to_role(old_expected * asking_multiplier(player, value, tier), tier, config)
        # This is the formula inside star_market_ask_millions, applied to all tiers in the benchmark.
        old_ask = round(min(old_ask / 1_000_000, cap * max_salary_share(service)), 1)
        weight = (0.5 if summer == 2025 else 1.0) * (0.25 if row.get("uncertain") else 1.0)
        result.append({
            **row, "age": age, "service": service, "season": season, "cap_millions": cap,
            "tier": tier, "on_court_value": value["on_court_value"], "weight": weight,
            "minutes_rule": round(max(1.8, display_minutes_projection(player) * 0.48), 1),
            "old_formula": old_ask, "old_formula_with_comps": profiles[player["id"]].asking_aav / 1_000_000,
        })
    return result


def fit(rows: list[dict]) -> tuple[float, ...]:
    """Solve the weighted ridge normal equations with an unpenalized intercept."""
    size = len(FEATURE_NAMES)
    system = [[0.0] * (size + 1) for _ in FEATURE_NAMES]
    for index in range(1, size):
        system[index][index] = RIDGE_PENALTY
    for row in rows:
        x = free_agent_salary_fit_features(row["on_court_value"], row["age"], row["service"], row["tier"], row["years"])
        y = math.log(row["aav_millions"] / row["cap_millions"])
        for i, feature in enumerate(x):
            for j, target in enumerate((*x, y)):
                system[i][j] += row["weight"] * feature * target
    for i in range(size):
        diagonal = system[i][i]
        system[i] = [value / diagonal for value in system[i]]
        for j in range(size):
            if j != i:
                factor = system[j][i]
                system[j] = [value - factor * pivot for value, pivot in zip(system[j], system[i])]
    return tuple(row[-1] for row in system)


def fold_for(row: dict) -> int:
    return int.from_bytes(hashlib.sha256(row["player"].encode()).digest()[:4]) % FOLDS


def predict(row: dict, coefficients: tuple[float, ...], *, known_term: bool = False) -> float:
    return free_agent_salary_fit_millions(
        coefficients, row["on_court_value"], row["age"], row["service"], row["tier"], row["season"],
        years=row["years"] if known_term else None, salary_cap=row["cap_millions"] * 1_000_000,
    )


def errors(rows: list[dict]) -> dict:
    results = {}
    for key in ("new_ask", "new_ask_known_term", "minutes_rule", "old_formula", "old_formula_with_comps"):
        error = [abs(row[key] - row["aav_millions"]) for row in rows]
        results[key] = {
            "mae_millions": round(mean(error), 3),
            "rmse_millions": round(math.sqrt(mean(value ** 2 for value in error)), 3),
            "mae_cap_percentage_points": round(100 * mean(value / row["cap_millions"] for value, row in zip(error, rows)), 3),
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-fit", action="store_true")
    args = parser.parse_args()
    rows = collect_evidence()
    held_out = []
    for fold in range(FOLDS):
        coefficients = fit([row for row in rows if fold_for(row) != fold])
        held_out.extend(
            {**row, "fold": fold, "new_ask": predict(row, coefficients),
             "new_ask_known_term": predict(row, coefficients, known_term=True)}
            for row in rows if fold_for(row) == fold
        )
    eligible = [row for row in held_out if row["tier"] in FITTED_FREE_AGENT_TIERS]
    artifact = {
        "version": 1,
        "source": str(EVIDENCE.relative_to(ROOT)),
        "training_count": len(rows),
        "tier_counts": dict(sorted(Counter(row["tier"] for row in rows).items())),
        "ridge_penalty": RIDGE_PENALTY,
        "features": FEATURE_NAMES,
        "coefficients": fit(rows),
    }
    if args.write_fit:
        FIT.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({
        "fit": artifact,
        "all_held_out": errors(held_out),
        "rotation_and_depth_held_out": errors(eligible),
        "rows": held_out,
    }, indent=2))


if __name__ == "__main__":
    main()
