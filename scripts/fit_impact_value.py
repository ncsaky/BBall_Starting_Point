#!/usr/bin/env python3
"""Fit player value (offense / defense / overall) to real impact, from the engine's own hidden ratings.

Target (2026-11-19 value refit): analysts first, impact numbers second.
- Impact: Basketball Index multi-year O-LEBRON / D-LEBRON for 2025-26 (impact per 100 possessions on team success).
- Analysts: ESPN NBA Rank 2026, The Ringer Top 100 and the Nerd Sesh redraft (the ratings-consensus task's sources,
  read from output/ratings-consensus/raw/ by scripts/research/ratings_consensus.py; local only). A player's analyst
  rank is the mean of his ESPN and Ringer ranks (110 when he is missing from one top-100 list) and his redraft pick if
  he was picked. The analysts' order is placed on the impact scale: the analysts' Nth player gets the multi-year LEBRON
  total of the Nth best player in the fit sample.
- Blend: target total = impact + ANALYST_WEIGHT x (analyst value - impact), split between offense and defense in the
  league's own proportion (the regression of each side's LEBRON on the total). ANALYST_WEIGHT = 0.6: the user asked for
  analysts first (so above half), the analyst-first report recommended 50-65%; 0.6 sits inside that range without
  going to its edge, and was not chosen by any scorecard (the fit's results barely move between 0.5 and 0.65).
- Impact only: players no analyst list ranks; players whose analyst rank sits below their impact because of age or
  availability (35 or older, or under 1,000 minutes in 2025-26: analysts discount expected missed games and decline,
  which the injury and aging models already handle; the value measures ability when playing).
- Left out of the fit: 2025 draftees. Their analyst rank is a projection, their multi-year LEBRON is one rookie season,
  and their inputs are still mostly priors; their value still comes from the same formula.
Predictors: the 15 hidden ratings the engine uses (new-ratings mode, derived from the 94 inputs), body measures, the
shooting profile, grouped input grades (defense in three groups: interior, perimeter, help), involvement, involvement x
skill terms (impact_value.INTERACTIONS), offensive rebounding on its real per-75 scale (offense only;
impact_value.orb_per75) and two elite rim-protection terms (defense only; impact_value.ELITE_DEFENSE).
Weighted ridge regression (weight = minutes / (minutes + 800)), non-negative except body measures and involvement,
5-fold cross-validation reported against the blended target and against plain LEBRON.
Writes data/canonical/impact_value_fit.json, read by nba_gm_data.impact_value.

    PYTHONPATH=src .venv/bin/python scripts/fit_impact_value.py [--write] [--analyst-weight 0.6]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

from nba_gm_data import bbi_evidence as be
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.impact_value import (BODY_PREDICTORS, DEFENSE_ONLY, FIT_FILE, OFFENSE_ONLY, ORB_SCALE_FILE, PREDICTORS,
                                      predictor_row)
from nba_gm_data.offense import offensive_profile
from nba_gm_data.ratings_model import effective_inputs, install_inputs_model
from nba_gm_data.save import trait_values_by_player

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"offense": "Multi-Year O-LEBRON", "defense": "Multi-Year D-LEBRON"}
SEASON = "2025-26"
RIDGE = 2.0
ANALYST_WEIGHT = 0.6
OUTSIDE_TOP_100 = 110
ROOKIE_DRAFT_YEAR = 2025          # first NBA season 2025-26
AGE_DISCOUNT = 35.0               # analysts discount age at or above this (only when they rank him below his impact)
AVAILABILITY_MINUTES = 1000.0     # ... or availability below this many 2025-26 minutes
WATCH = ["Nikola Jokić", "Shai Gilgeous-Alexander", "Victor Wembanyama", "Giannis Antetokounmpo", "Luka Dončić",
         "Rudy Gobert", "Domantas Sabonis", "Evan Mobley", "Anthony Davis", "Derrick White", "Jamal Murray",
         "Stephen Curry", "Jayson Tatum", "Anthony Edwards", "Cade Cunningham", "Draymond Green", "Jalen Brunson",
         "Moussa Diabaté", "Neemias Queta", "Luke Kornet", "Brandon Ingram", "Nikola Vučević", "Tyrese Maxey",
         "Jaylen Brown", "Trae Young", "Chet Holmgren", "Bam Adebayo"]


def analyst_ranks(players) -> dict[str, float]:
    """Mean analyst rank per player id (ESPN, Ringer, Nerd Sesh redraft), for players at least one list ranks."""
    sys.path.insert(0, str(ROOT / "scripts" / "research"))
    from ratings_consensus import load_sources, norm, strip_suffix
    lists, redraft, _position = load_sources()
    out = {}
    for player in players:
        key = norm(player["name"])
        look = lambda table: table.get(key, table.get(strip_suffix(key)))
        espn, ringer, pick = look(lists["espn"]), look(lists["ringer"]), look(redraft)
        if not (espn or ringer or pick):
            continue
        ranks = [espn or OUTSIDE_TOP_100, ringer or OUTSIDE_TOP_100] + ([pick] if pick else [])
        out[player["id"]] = statistics.fmean(ranks)
    return out


def blended_targets(rows, analyst, weight):
    """Per row: (offense target, defense target, note). See the module docstring for the rule."""
    totals = sorted((r[3]["offense"] + r[3]["defense"] for r in rows), reverse=True)
    total = [r[3]["offense"] + r[3]["defense"] for r in rows]
    beta_o = statistics.covariance([r[3]["offense"] for r in rows], total) / statistics.variance(total)
    ranked = sorted((i for i, r in enumerate(rows) if r[0] in analyst), key=lambda i: (analyst[rows[i][0]], -total[i]))
    analyst_value = {i: totals[n] for n, i in enumerate(ranked)}
    out = []
    for i, (pid, name, _x, real, minutes, age) in enumerate(rows):
        o, d = real["offense"], real["defense"]
        if i not in analyst_value or weight == 0:
            out.append((o, d, None))
            continue
        gap = analyst_value[i] - total[i]
        if gap < 0 and (age >= AGE_DISCOUNT or minutes < AVAILABILITY_MINUTES):
            out.append((o, d, f"impact only (analysts {gap:+.2f} below impact; age {age:.0f}, {minutes:.0f} minutes)"))
            continue
        out.append((o + weight * gap * beta_o, d + weight * gap * (1 - beta_o), f"analyst rank {ranked.index(i) + 1}"))
    return out, beta_o


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
    ap.add_argument("--analyst-weight", type=float, default=ANALYST_WEIGHT, help="0 = impact numbers only")
    args = ap.parse_args()
    canonical = load_app_canonical(ROOT)
    install_inputs_model(canonical, ROOT)
    traits = trait_values_by_player(canonical)
    players = {p["id"]: p for p in canonical["players"]}
    table = be.collect_values(ROOT, set(TARGETS.values()))
    analyst = analyst_ranks(players.values()) if args.analyst_weight > 0 else {}
    rows = []
    rookies = []
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
            if (player.get("draft_year") or 0) >= ROOKIE_DRAFT_YEAR:
                rookies.append(player["name"])
                continue
            profile = offensive_profile(canonical, player, traits[pid])
            rows.append((pid, player["name"], predictor_row(traits[pid], player, profile, effective_inputs(canonical, pid)),
                         values, minutes, float(player.get("age") or 27.0)))
    targets, beta_o = blended_targets(rows, analyst, args.analyst_weight)
    weights = [r[4] / (r[4] + 800.0) for r in rows]
    X = [[1.0, *r[2]] for r in rows]
    FREE = {1 + PREDICTORS.index(name) for name in (*BODY_PREDICTORS, "in_involvement")}  # not changed by development
    notes = [t[2] for t in targets]
    fit = {"version": "impact_value_fit_v6_analyst_blend_defense_groups_2026_11_19", "season": SEASON, "targets": TARGETS,
           "predictors": PREDICTORS, "ridge": RIDGE, "players": len(rows), "coefficients": {}, "cv_weighted_corr": {},
           "offense_only": list(OFFENSE_ONLY), "defense_only": list(DEFENSE_ONLY),
           "orb_scale": json.loads((ROOT / ORB_SCALE_FILE).read_text())["version"],
           "target_blend": {"analyst_weight": args.analyst_weight,
                            "analyst_sources": ["ESPN NBA Rank 2026", "The Ringer Top 100 (2026-10-14)", "Nerd Sesh redraft (2026-07-31)"],
                            "offense_share_of_gap": round(beta_o, 4),
                            "analyst_ranked": sum(1 for n in notes if n and n.startswith("analyst")),
                            "impact_only_age_or_availability": sorted(rows[i][1] for i, n in enumerate(notes) if n and n.startswith("impact only")),
                            "rookies_left_out": len(rookies)}}
    idx = list(range(len(rows)))
    random.Random(11).shuffle(idx)
    folds = [idx[i::5] for i in range(5)]
    oof_all = {}
    for side in TARGETS:
        y = [t[0] if side == "offense" else t[1] for t in targets]
        # Standardize predictors so the ridge penalty is fair across scales.
        cols = list(zip(*[x[1:] for x in X]))
        mu = [statistics.fmean(c) for c in cols]
        sd = [statistics.pstdev(c) or 1.0 for c in cols]
        Z = [[1.0, *[(v - m) / s for v, m, s in zip(x[1:], mu, sd)]] for x in X]
        # Offense-only predictors (offensive rebounding production) carry no defensive weight, defense-only ones (the
        # defensive groups and elite rim protection) no offensive weight.
        drop = {1 + PREDICTORS.index(name) for name in (OFFENSE_ONLY if side == "defense" else DEFENSE_ONLY)}
        Z = [[0.0 if k in drop else v for k, v in enumerate(z)] for z in Z]
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
    total_target = [t[0] + t[1] for t in targets]
    total_oof = [a + b for a, b in zip(oof_all["offense"], oof_all["defense"])]
    fit["cv_weighted_corr"]["overall"] = round(wcorr(total_target, total_oof, weights), 3)
    fit["cv_weighted_corr"]["overall_vs_lebron"] = round(wcorr(total_real, total_oof, weights), 3)
    for side in TARGETS:
        fit["cv_weighted_corr"][f"{side}_vs_lebron"] = round(wcorr([r[3][side] for r in rows], oof_all[side], weights), 3)
    print(f"{len(rows)} players ({len(rookies)} 2025 draftees left out); offense share of an analyst gap {beta_o:.3f}")
    print(f"out-of-fold weighted correlation: {fit['cv_weighted_corr']}")
    print("impact only (age/availability):", fit["target_blend"]["impact_only_age_or_availability"])
    ranks = {r[1]: n + 1 for n, r in enumerate(sorted(zip(total_oof, [r[1] for r in rows]), key=lambda t: -t[0]))}
    target_ranks = {r[1]: n + 1 for n, r in enumerate(sorted(zip(total_target, [r[1] for r in rows]), key=lambda t: -t[0]))}
    names = [r[1] for r in rows]
    for name in WATCH:
        if name in names:
            i = names.index(name)
            print(f"  {name:24s} LEBRON {total_real[i]:+5.2f} target {total_target[i]:+5.2f} (#{target_ranks[name]})  "
                  f"predicted (out-of-fold) {total_oof[i]:+5.2f} #{ranks[name]}"
                  f"   [O target {targets[i][0]:+.2f} pred {oof_all['offense'][i]:+.2f} | D target {targets[i][1]:+.2f} pred {oof_all['defense'][i]:+.2f}]"
                  f"  {notes[i] or ''}")
    if args.write:
        (ROOT / FIT_FILE).write_text(json.dumps(fit, indent=1) + "\n")
        print("wrote", FIT_FILE)


if __name__ == "__main__":
    main()
