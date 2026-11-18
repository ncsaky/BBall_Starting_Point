#!/usr/bin/env python3
"""Fit the rim-protection pieces of the engine to Basketball Index rim evidence (local-only data).

Evidence (2023-24..2025-26 Leaderboards "Values", seasons weighted 1.0 / 0.6 / 0.35 times minutes, each metric a
z-score among that season's 500+ minute players): Rim Points Saved Per 75, Stable Rim dFG% vs. Expected (lower is
better), Rim Deterrence, Rim Protection, Rim Contests Per 75, Block Rate on Contests. Their mean is the "rim
evidence composite". Only derived numbers are written; no Basketball Index rows.

Two outputs:
1. ``recipe``: the new-ratings recipe for the rim_deterrence trait (trait_adapter.ADAPTER_SPEC). Predictors are
   league percentiles of defensive technique and size inputs; non-negative ridge (a better input never lowers the
   trait); 5-fold out-of-fold correlation reported. Paste the printed recipe into ADAPTER_SPEC by hand (reviewed).
2. ``response``: data/canonical/rim_response_fit.json, the knots of defense.rim_response. The trait's league rank is
   mapped onto the real distribution of opponents' rim FG% against expectation (Stable Rim dFG% vs. Expected, BBI's
   sample-size-shrunk version; percentage points, sign flipped). The points-per-percentage-point exchange rate is
   fitted where the old response already matched the evidence (the 5th-75th percentile), so most players keep their
   value; the top of the scale now spreads the way the real distribution does instead of flattening at 99.

    PYTHONPATH=src .venv/bin/python scripts/fit_rim_protection.py [--write]
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from fit_impact_value import ridge_nonnegative, wcorr  # noqa: E402
from nba_gm_data.bbi_evidence import SEASON_WEIGHTS, collect_values  # noqa: E402
from nba_gm_data.ratings_model import load_league_inputs  # noqa: E402
from nba_gm_data.trait_adapter import _definitions, _percentile, scalar_value  # noqa: E402

EVIDENCE = (("Rim Points Saved Per 75 Possessions", 1), ("Stable Rim dFG% vs. Expected", -1), ("Rim Deterrence", 1),
            ("Rim Protection", 1), ("Rim Contests Per 75 Possessions", 1), ("Block Rate on Contests", 1))
PHYSICAL_METRIC = "Stable Rim dFG% vs. Expected"
POOL_MINUTES = 500
MIN_MINUTES = 300
CANDIDATES = ("S34", "S36", "S37", "S38", "S40", "S41", "S44", "S45", "S46", "P01", "P02", "P03", "P04", "P08", "P10")
RIDGE = 3.0
MIN_WEIGHT = 0.03
BULK = (0.25, 0.75)          # league-percentile range that sets the exchange rate; the old response is kept below the top
OUT = ROOT / "data/canonical/rim_response_fit.json"


def blended(table, metric, direction=1, z=True):
    """canonical id -> (season-weighted mean of the metric, z-scored per season if z, effective minutes)."""
    acc = {}
    for season, sw in SEASON_WEIGHTS.items():
        rows = table.get((season, metric)) or {}
        pool = [v for v, m, _ in rows.values() if m >= POOL_MINUTES]
        if len(pool) < 30:
            continue
        mu, sd = statistics.fmean(pool), statistics.pstdev(pool) or 1.0
        for v, m, cid in rows.values():
            if not cid or m < MIN_MINUTES:
                continue
            x = direction * ((v - mu) / sd if z else v)
            a = acc.setdefault(cid, [0.0, 0.0, 0.0])
            a[0] += sw * m * x
            a[1] += sw * m
            a[2] += sw * m
    return {cid: (a[0] / a[1], a[2]) for cid, a in acc.items() if a[1] > 0}


def rim_evidence(root: Path = ROOT) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """(composite z, effective minutes, physical metric in percentage points with sign flipped) per canonical id."""
    table = collect_values(root, {m for m, _ in EVIDENCE})
    parts = [blended(table, m, d) for m, d in EVIDENCE]
    composite, minutes = {}, {}
    for cid in set.intersection(*(set(p) for p in parts)):
        composite[cid] = statistics.fmean(p[cid][0] for p in parts)
        minutes[cid] = max(p[cid][1] for p in parts)
    physical = {cid: -100.0 * v for cid, (v, _) in blended(table, PHYSICAL_METRIC, 1, z=False).items()}
    return composite, minutes, physical


def fit_recipe(composite, minutes):
    defs = _definitions()
    inputs = load_league_inputs()
    raw = {pid: {k: scalar_value(defs[k], inp.get(k)) for k in CANDIDATES} for pid, inp in inputs.items()}
    tables = {k: sorted(v[k] for v in raw.values() if v[k] is not None) for k in CANDIDATES}

    def pct(pid, k):
        v = raw[pid][k]
        return 0.5 if v is None else _percentile(tables[k], v)

    ids = [pid for pid in composite if pid in raw]
    X = [[pct(pid, k) for k in CANDIDATES] for pid in ids]
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
    print(f"recipe fit: {len(ids)} players with rim evidence; out-of-fold weighted r = {wcorr(y, oof, w):.3f}")
    print("recipe:", recipe)
    return recipe


def censored_tail(values: list[float], ceiling: float = 99.5) -> list[float]:
    """Sorted league values with a clipped top plateau replaced by the distribution's own extrapolated tail.

    Mirrors trait_adapter.uncensor_top (kept in one place there; imported lazily to stay in sync)."""
    from nba_gm_data.trait_adapter import uncensor_top
    return uncensor_top(values, ceiling)


def fit_response(composite, physical):
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.ratings_model import is_placeholder_trait
    canonical = load_app_canonical(ROOT)
    traits = {t["player_id"]: float(t["value"]) for t in canonical["traits"]
              if t["trait_key"] == "rim_deterrence" and t.get("value") is not None and not is_placeholder_trait(t)}
    ids = [pid for pid in traits if pid in physical and pid in composite]
    league = censored_tail(sorted(traits.values()))
    # The same players' league percentiles. Players clipped at the old ceiling are censored: their true ranks lie
    # somewhere in the plateau, so they are spread evenly over it (only the distribution matters here, not who).
    ceiling = max(traits.values())
    plateau_start = sum(1 for v in traits.values() if v < ceiling) / len(traits)
    clipped = [pid for pid in ids if traits[pid] >= ceiling]
    trait_sorted = sorted([_percentile(league, traits[pid]) for pid in ids if traits[pid] < ceiling]
                          + [plateau_start + (j + 0.5) / len(clipped) * (1 - plateau_start) for j in range(len(clipped))])
    phys_sorted = sorted(physical[pid] for pid in ids)
    n = len(ids)

    def q(sorted_values, u):
        pos = min(max(u * (len(sorted_values) - 1), 0.0), len(sorted_values) - 1.0)
        lo = int(pos)
        hi = min(lo + 1, len(sorted_values) - 1)
        return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)

    from nba_gm_data.defense import legacy_rim_response
    # Grid in league-percentile space: trait value at that league percentile and the evidence quantile at the same
    # rank among the players who have both.
    # Coarse knots (every 5 points, finer at the top) keep the response smooth; the evidence quantile uses mid-ranks
    # so the very top ranks interpolate toward the real maximum instead of all landing on it.
    grid = [0.05 * i for i in range(1, 19)] + [0.925, 0.95, 0.965, 0.98, 0.99, 0.995, 0.999]
    pairs = []
    for u in sorted(grid):
        raw_value = q(league, u)
        below = sum(1 for p in trait_sorted if p < u)
        equal = sum(1 for p in trait_sorted if p == u)
        r = (below + 0.5 * equal) / n
        pairs.append((round(u, 4), raw_value, q(phys_sorted, r * n / (n - 1) - 0.5 / (n - 1))))
    at = {round(u, 4): (raw_value, pp) for u, raw_value, pp in pairs}
    (raw_lo, pp_lo), (raw_hi, pp_hi) = at[BULK[0]], at[BULK[1]]
    # Exchange rate: how many response points the old scale spends per percentage point of real rim FG% against
    # expectation between the 25th and 75th league percentiles (the middle, where the old response matched).
    slope = (legacy_rim_response(raw_hi) - legacy_rim_response(raw_lo)) / (pp_hi - pp_lo)
    anchor = legacy_rim_response(raw_hi)
    print(f"response fit: {n} players; exchange rate {slope:.2f} response points per percentage point of rim FG% "
          f"against expectation (league percentiles {BULK[0]:.0%}-{BULK[1]:.0%}); anchored at the {BULK[1]:.0%} percentile")
    knots = []
    for u, raw_value, pp in pairs:
        if u < BULK[1]:
            continue          # up to the 75th percentile the old response stands
        knots.append([round(raw_value, 3), round(anchor + slope * (pp - pp_hi), 3)])
    # Past the last knot rim_response continues the last segment; give it the top three segments' mean slope so the
    # final interpolation step cannot flatten the very top.
    if len(knots) >= 4:
        (xa, ya), (xb, yb) = knots[-4], knots[-1]
        mean_slope = (yb - ya) / (xb - xa)
        x0, y0 = knots[-2]
        knots[-1][1] = round(max(knots[-1][1], y0 + mean_slope * (knots[-1][0] - x0)), 3)
    clean = []                # strictly increasing in both coordinates (monotone response)
    for x, y in knots:
        if clean and x <= clean[-1][0] + 1e-6:
            continue
        if clean and y <= clean[-1][1]:
            y = clean[-1][1] + 0.01
        clean.append([x, round(y, 3)])
    for u in (0.5, 0.75, 0.85, 0.9, 0.95, 0.97, 0.98, 0.99, 0.995, 0.999):
        raw_value = q(league, u)
        print(f"  league pct {u:6.3f}: trait {raw_value:7.2f}  old response {legacy_rim_response(min(raw_value, 100)):6.2f}  "
              f"new {interp(clean, raw_value) if raw_value > clean[0][0] else legacy_rim_response(raw_value):6.2f}")
    return {"version": "rim_response_fit_v1_2026_11_18", "metric": PHYSICAL_METRIC, "players": n,
            "exchange_rate": round(slope, 4), "anchor_percentile": BULK[1], "anchor_response": round(anchor, 4), "bulk_percentiles": list(BULK),
            "knots": clean}


def interp(knots, x):
    if x <= knots[0][0]:
        (x0, y0), (x1, y1) = knots[0], knots[1]
    elif x >= knots[-1][0]:
        (x0, y0), (x1, y1) = knots[-2], knots[-1]
    else:
        i = next(i for i in range(1, len(knots)) if knots[i][0] >= x)
        (x0, y0), (x1, y1) = knots[i - 1], knots[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def main() -> int:
    composite, minutes, physical = rim_evidence()
    fit_recipe(composite, minutes)
    fit = fit_response(composite, physical)
    if "--write" in sys.argv:
        OUT.write_text(json.dumps(fit, indent=1) + "\n")
        print("wrote", OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
