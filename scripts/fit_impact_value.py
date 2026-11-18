#!/usr/bin/env python3
"""Fit player value (offense / defense / overall) to real impact, from the engine's own hidden ratings.

Target: Basketball Index multi-year O-LEBRON / D-LEBRON for 2025-26 (impact per 100 possessions on team success).
Predictors: the 15 hidden ratings the engine uses (new-ratings mode, derived from the 94 inputs), body measures, the
shooting profile, grouped input grades, involvement, and involvement x skill terms (impact_value.INTERACTIONS).
Weighted ridge regression (weight = minutes / (minutes + 800)), 5-fold cross-validation reported.
Writes data/canonical/impact_value_fit.json, read by nba_gm_data.impact_value.

    PYTHONPATH=src .venv/bin/python scripts/fit_impact_value.py [--write]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

from nba_gm_data import bbi_evidence as be
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.impact_value import BODY_PREDICTORS, FIT_FILE, PREDICTORS, predictor_row
from nba_gm_data.offense import offensive_profile
from nba_gm_data.ratings_model import effective_inputs, install_inputs_model
from nba_gm_data.save import trait_values_by_player

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"offense": "Multi-Year O-LEBRON", "defense": "Multi-Year D-LEBRON"}
SEASON = "2025-26"
RIDGE = 2.0
WATCH = ["Nikola Jokić", "Shai Gilgeous-Alexander", "Victor Wembanyama", "Giannis Antetokounmpo", "Luka Dončić",
         "Rudy Gobert", "Domantas Sabonis", "Evan Mobley", "Anthony Davis", "Derrick White", "Jamal Murray",
         "Stephen Curry", "Jayson Tatum", "Anthony Edwards", "Cade Cunningham", "Draymond Green", "Jalen Brunson"]


def ridge(X, y, w, lam):
    n = len(X[0])
    A = [[sum(wi * r[i] * r[j] for r, wi in zip(X, w)) + (lam if i == j and i > 0 else 0.0) for j in range(n)] for i in range(n)]
    b = [sum(wi * r[i] * t for r, t, wi in zip(X, y, w)) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            f = A[j][i] / A[i][i]
            for k in range(i, n):
                A[j][k] -= f * A[i][k]
            b[j] -= f * b[i]
    coef = [0.0] * n
    for i in reversed(range(n)):
        coef[i] = (b[i] - sum(A[i][k] * coef[k] for k in range(i + 1, n))) / A[i][i]
    return coef


def ridge_nonnegative(X, y, w, lam, free=()):
    """Ridge with every weight except the intercept and the `free` columns held >= 0 (active-set refits).
    A better hidden rating or input must never lower a player's value; free columns (height) can be signed."""
    n = len(X[0])
    active = list(range(n))
    while True:
        cols = active
        coef_sub = ridge([[row[c] for c in cols] for row in X], y, w, lam)
        coef = [0.0] * n
        for c, value in zip(cols, coef_sub):
            coef[c] = value
        negative = [c for c in cols if c != 0 and c not in free and coef[c] < 0]
        if not negative:
            return coef
        worst = min(negative, key=lambda c: coef[c])
        active = [c for c in active if c != worst]


def wcorr(a, b, w):
    sw = sum(w)
    ma, mb = sum(x * v for x, v in zip(a, w)) / sw, sum(x * v for x, v in zip(b, w)) / sw
    cov = sum(v * (x - ma) * (z - mb) for x, z, v in zip(a, b, w))
    return cov / (sum(v * (x - ma) ** 2 for x, v in zip(a, w)) ** .5 * sum(v * (z - mb) ** 2 for z, v in zip(b, w)) ** .5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    canonical = load_app_canonical(ROOT)
    install_inputs_model(canonical, ROOT)
    traits = trait_values_by_player(canonical)
    players = {p["id"]: p for p in canonical["players"]}
    table = be.collect_values(ROOT, set(TARGETS.values()))
    rows = []
    for pid, player in players.items():
        if pid not in traits:
            continue
        values = {}
        minutes = 0.0
        for side, metric in TARGETS.items():
            cell = table.get((SEASON, metric), {}).get(pid)
            if cell:
                values[side] = cell[0]
                minutes = max(minutes, cell[1])
        if len(values) == 2 and minutes >= 200:
            profile = offensive_profile(canonical, player, traits[pid])
            rows.append((pid, player["name"], predictor_row(traits[pid], player, profile, effective_inputs(canonical, pid)),
                         values, minutes))
    weights = [m / (m + 800.0) for *_, m in rows]
    X = [[1.0, *r[2]] for r in rows]
    FREE = {1 + PREDICTORS.index(name) for name in (*BODY_PREDICTORS, "in_involvement")}  # not changed by development
    fit = {"version": "impact_value_fit_v4_involvement_skill_2026_11_18", "season": SEASON, "targets": TARGETS, "predictors": PREDICTORS,
           "ridge": RIDGE, "players": len(rows), "coefficients": {}, "cv_weighted_corr": {}}
    idx = list(range(len(rows)))
    random.Random(11).shuffle(idx)
    folds = [idx[i::5] for i in range(5)]
    oof_all = {}
    for side in TARGETS:
        y = [r[3][side] for r in rows]
        # Standardize predictors so the ridge penalty is fair across scales.
        cols = list(zip(*[x[1:] for x in X]))
        mu = [statistics.fmean(c) for c in cols]
        sd = [statistics.pstdev(c) or 1.0 for c in cols]
        Z = [[1.0, *[(v - m) / s for v, m, s in zip(x[1:], mu, sd)]] for x in X]
        oof = [0.0] * len(rows)
        for f in folds:
            tr = [i for i in idx if i not in f]
            c = ridge_nonnegative([Z[i] for i in tr], [y[i] for i in tr], [weights[i] for i in tr], RIDGE, FREE)
            for i in f:
                oof[i] = sum(a * b for a, b in zip(Z[i], c))
        coef = ridge_nonnegative(Z, y, weights, RIDGE, FREE)
        fit["coefficients"][side] = {"intercept": coef[0], "mean": mu, "sd": sd, "weights": coef[1:]}
        fit["cv_weighted_corr"][side] = round(wcorr(y, oof, weights), 3)
        oof_all[side] = oof
    total_real = [r[3]["offense"] + r[3]["defense"] for r in rows]
    total_oof = [a + b for a, b in zip(oof_all["offense"], oof_all["defense"])]
    fit["cv_weighted_corr"]["overall"] = round(wcorr(total_real, total_oof, weights), 3)
    print(f"{len(rows)} players; out-of-fold weighted correlation: {fit['cv_weighted_corr']}")
    ranks = {r[1]: n + 1 for n, r in enumerate(sorted(zip(total_oof, [r[1] for r in rows]), key=lambda t: -t[0]))}
    names = [r[1] for r in rows]
    for name in WATCH:
        if name in names:
            i = names.index(name)
            print(f"  {name:24s} real {total_real[i]:+5.2f}  predicted (out-of-fold) {total_oof[i]:+5.2f}  rank #{ranks[name]}"
                  f"   [O real {rows[i][3]['offense']:+.2f} pred {oof_all['offense'][i]:+.2f} | D real {rows[i][3]['defense']:+.2f} pred {oof_all['defense'][i]:+.2f}]")
    if args.write:
        (ROOT / FIT_FILE).write_text(json.dumps(fit, indent=1) + "\n")
        print("wrote", FIT_FILE)


if __name__ == "__main__":
    main()
