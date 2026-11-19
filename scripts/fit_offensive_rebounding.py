#!/usr/bin/env python3
"""Fit the new-ratings recipe of the offensive_rebounding trait to Basketball Index offensive-rebounding evidence.

The engine reads offensive_rebounding as offensive-rebounding PRODUCTION: each team's offensive rebound rate and extra
possessions (sim.offensive_feature_summary_from_values, team offensive rebound rate), every player's share of his
team's rebounds (sim.rebound_rate_per_minute), putback finishing (offense.finishing_multiplier) and the player value
model (impact_value). The original recipe was written by hand (S29 0.40, T12 0.20, P10, P03, S32, P08 0.10 each) and
tracked real offensive rebounds per 75 only at r 0.73 league-wide and 0.50 among bigs, so high-volume crashers such as
Moussa Diabate (97th percentile in offensive rebounds per 75) rated 78 while Jarrett Allen (3.3 per 75) rated 62
(energy-bigs task, 2026-11-18).

Evidence (2023-24..2025-26 Leaderboards "Values", seasons weighted 1.0 / 0.6 / 0.35 times minutes, each metric a
z-score among that season's 500+ minute players): Stable Offensive Rebounds Per 75 (volume, shrunk for sample size)
and Offensive Rebounding Talent (Basketball Index's grade of positioning plus conversion). Their mean is the
"offensive-rebounding evidence composite". Predictors are league percentiles of the rebounding technique, crash
tendency and body inputs; non-negative ridge (a better input never lowers the trait); 5-fold out-of-fold
correlation reported. Only derived numbers are printed; paste the recipe into trait_adapter.ADAPTER_SPEC by hand.

Second output (--write): data/canonical/offensive_rebound_scale.json, knots from the trait's value to real offensive
rebounds per 75 (fit_scale), read by the player value model.

    PYTHONPATH=src .venv/bin/python scripts/fit_offensive_rebounding.py [--write]
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from fit_impact_value import ridge_nonnegative, wcorr  # noqa: E402
from fit_rim_protection import blended  # noqa: E402
from nba_gm_data.bbi_evidence import collect_values  # noqa: E402
from nba_gm_data.ratings_model import load_league_inputs  # noqa: E402
from nba_gm_data.trait_adapter import _definitions, _percentile, scalar_value  # noqa: E402

EVIDENCE = (("Stable Offensive Rebounds Per 75", 1), ("Offensive Rebounding Talent", 1))
# Rebounding technique (S29 pursuit, S31 box-out, S32 control), the crash-versus-retreat tendency (T12) and body
# inputs (height, wingspan, reach, mass, acceleration, strength, vertical).
CANDIDATES = ("S29", "S31", "S32", "T12", "P01", "P02", "P03", "P04", "P05", "P08", "P10")
RIDGE = 3.0
MIN_WEIGHT = 0.03
HAND_WRITTEN = {"S29": 0.40, "T12": 0.20, "P10": 0.10, "P03": 0.10, "S32": 0.10, "P08": 0.10}   # recipe before 2026-11-18
SCALE_METRIC = "Stable Offensive Rebounds Per 75"
SCALE_OUT = ROOT / "data/canonical/offensive_rebound_scale.json"


def evidence(root: Path = ROOT) -> tuple[dict[str, float], dict[str, float]]:
    table = collect_values(root, {m for m, _ in EVIDENCE})
    parts = [blended(table, m, d) for m, d in EVIDENCE]
    composite, minutes = {}, {}
    for cid in set.intersection(*(set(p) for p in parts)):
        composite[cid] = statistics.fmean(p[cid][0] for p in parts)
        minutes[cid] = max(p[cid][1] for p in parts)
    return composite, minutes


def percentiles(keys):
    defs = _definitions()
    inputs = load_league_inputs()
    raw = {pid: {k: scalar_value(defs[k], inp.get(k)) for k in keys} for pid, inp in inputs.items()}
    tables = {k: sorted(v[k] for v in raw.values() if v[k] is not None) for k in keys}
    return {pid: {k: (0.5 if raw[pid][k] is None else _percentile(tables[k], raw[pid][k])) for k in keys} for pid in raw}


def composite_score(pct: dict[str, float], recipe) -> float:
    return sum(w * pct[k] for k, w in recipe.items())


def fit_recipe(composite, minutes):
    pct = percentiles(CANDIDATES)
    ids = sorted(pid for pid in composite if pid in pct)   # sorted: fold assignment must not depend on set order
    X = [[pct[pid][k] for k in CANDIDATES] for pid in ids]
    y = [composite[pid] for pid in ids]
    w = [minutes[pid] / (minutes[pid] + 800.0) for pid in ids]
    mu = [statistics.fmean(c) for c in zip(*X)]
    sd = [statistics.pstdev(c) or 1.0 for c in zip(*X)]
    Z = [[1.0, *[(v - m) / s for v, m, s in zip(x, mu, sd)]] for x in X]
    order = list(range(len(ids)))
    random.Random(7).shuffle(order)
    oof = [0.0] * len(ids)
    for fold in (order[i::5] for i in range(5)):
        held = set(fold)
        train = [i for i in order if i not in held]
        c = ridge_nonnegative([Z[i] for i in train], [y[i] for i in train], [w[i] for i in train], RIDGE)
        for i in fold:
            oof[i] = sum(a * b for a, b in zip(Z[i], c))
    coef = ridge_nonnegative(Z, y, w, RIDGE)
    raw_w = {k: c / s for k, c, s in zip(CANDIDATES, coef[1:], sd) if c > 0}
    total = sum(raw_w.values())
    recipe = {k: v / total for k, v in raw_w.items() if v / total >= MIN_WEIGHT}
    t2 = sum(recipe.values())
    recipe = {k: round(v / t2, 2) for k, v in sorted(recipe.items(), key=lambda kv: -kv[1])}
    drift = round(1.0 - sum(recipe.values()), 2)
    if drift:
        top = next(iter(recipe))
        recipe[top] = round(recipe[top] + drift, 2)
    print(f"recipe fit: {len(ids)} players with offensive-rebounding evidence; out-of-fold weighted r = {wcorr(y, oof, w):.3f}")
    print("recipe:", recipe)
    # How well each recipe's composite (before the league quantile map, which keeps order) follows the evidence.
    old = HAND_WRITTEN
    old_pct = percentiles(tuple(old))
    for label, rec, table in (("hand-written", old, old_pct), ("fitted recipe", recipe, pct)):
        xs = [composite_score(table[pid], rec) for pid in ids]
        print(f"  {label:15} weighted r with the evidence composite: {wcorr(y, xs, w):.3f}")
    return recipe


def fit_scale(min_minutes: float = 500.0) -> dict:
    """Knots from the trait's value to real offensive rebounds per 75 (same players, matched by rank).

    The player value model (impact_value) reads offensive rebounding on this production scale: the rating's league
    rank says WHO rebounds more, the real distribution says HOW MUCH more. On the trait's own rank scale the top crashers
    (5-8 per 75) sit within a few points of good-not-elite rebounders (3 per 75), and a linear value fit cannot see the
    difference. Run after the recipe is in trait_adapter.ADAPTER_SPEC (the knots read the current traits)."""
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.ratings_model import install_inputs_model
    from nba_gm_data.save import trait_values_by_player
    canonical = load_app_canonical(ROOT)
    install_inputs_model(canonical, ROOT)
    traits = {pid: t["offensive_rebounding"] for pid, t in trait_values_by_player(canonical).items() if "offensive_rebounding" in t}
    table = collect_values(ROOT, {SCALE_METRIC})
    real = {cid: v for cid, (v, m) in blended(table, SCALE_METRIC, 1, z=False).items() if m >= min_minutes}
    ids = [pid for pid in traits if pid in real]
    xs, ys = sorted(traits[pid] for pid in ids), sorted(real[pid] for pid in ids)
    n = len(ids)

    def q(values, u):
        pos = min(max(u * (n - 1), 0.0), n - 1.0)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)

    knots = []
    for u in [0.0, 0.02, 0.05] + [0.1 * i for i in range(1, 10)] + [0.95, 0.98, 1.0]:
        x, y = round(q(xs, u), 3), round(q(ys, u), 3)
        if knots and x <= knots[-1][0] + 1e-6:
            continue
        if knots and y < knots[-1][1]:
            y = knots[-1][1]
        knots.append([x, y])
    weights = [1.0] * n
    print(f"scale fit: {n} players with {min_minutes:.0f}+ effective minutes; rank correlation of the rating with real "
          f"offensive rebounds per 75: {wcorr(_ranks([traits[p] for p in ids]), _ranks([real[p] for p in ids]), weights):.3f}")
    print("knots (rating -> offensive rebounds per 75):", knots)
    return {"version": "offensive_rebound_scale_v1_2026_11_18", "metric": SCALE_METRIC, "players": n, "knots": knots}


def _ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    for r, i in enumerate(order):
        out[i] = float(r)
    return out


def main() -> int:
    composite, minutes = evidence()
    fit_recipe(composite, minutes)
    scale = fit_scale()
    if "--write" in sys.argv:
        SCALE_OUT.write_text(json.dumps(scale, indent=1) + "\n")
        print("wrote", SCALE_OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
