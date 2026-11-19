#!/usr/bin/env python3
"""Fit the box-score allocation rates in ``nba_gm_data.box_rates`` to real 2025-26 per-36 rates.

Each rate is a log-linear model (log rate = constant + sum of coefficients x inputs) fitted by weighted least
squares to the 2025-26 rotation players in ``data/calibration/nba_2025_26_targets.json`` (500+ minutes,
weight = minutes capped at 2000). The constant is then shifted so the minutes-weighted league mean matches the
real mean (a log fit otherwise predicts the geometric mean, a few percent low). Ten-fold out-of-fold
correlation and mean absolute error are printed next to the formula the engine used before.

New-ratings models read the approved inputs (data/canonical/player_inputs_2026_27.json); old-ratings models
read the 15 legacy traits of the canonical universe. Standard library only. Usage:

    PYTHONPATH=src .venv/bin/python scripts/fit_box_stat_rates.py
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data import box_rates  # noqa: E402
from nba_gm_data.ratings_model import load_league_inputs  # noqa: E402

MIN_MINUTES = 500
FOLDS = 10


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting (small dense systems)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(n):
            if r != col and m[col][col]:
                f = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def wls(x: list[list[float]], y: list[float], w: list[float]) -> list[float]:
    k = len(x[0])
    xtx = [[sum(w[i] * x[i][p] * x[i][q] for i in range(len(y))) for q in range(k)] for p in range(k)]
    xty = [sum(w[i] * x[i][p] * y[i] for i in range(len(y))) for p in range(k)]
    return solve(xtx, xty)


def predict(beta: list[float], row: list[float]) -> float:
    return math.exp(sum(b * v for b, v in zip(beta, row)))


def fit(rows, columns, target, *, scale_key=None):
    """columns: list of (name, function(row) -> value). target: function(row) -> real rate (>0)."""
    data = [(r, [1.0] + [f(r) for _, f in columns], target(r)) for r in rows]
    data = [(r, x, y) for r, x, y in data if y and y > 0]
    x = [d[1] for d in data]
    y = [math.log(d[2]) for d in data]
    w = [min(2000.0, d[0]["minutes"]) for d in data]
    beta = wls(x, y, w)

    def calibrate(beta, subset):
        # Shift the constant so the minutes-weighted mean (or, for a per-point rate, the minutes x points weighted
        # mean) of the prediction equals the real one.
        weights = [d[0]["minutes"] * (d[0][scale_key] if scale_key else 1.0) for d in subset]
        real = sum(wt * d[2] for wt, d in zip(weights, subset))
        pred = sum(wt * predict(beta, d[1]) for wt, d in zip(weights, subset))
        return [beta[0] + math.log(real / pred)] + beta[1:]

    beta = calibrate(beta, data)
    oof = [0.0] * len(data)
    for fold in range(FOLDS):
        train = [i for i in range(len(data)) if i % FOLDS != fold]
        b = wls([x[i] for i in train], [y[i] for i in train], [w[i] for i in train])
        b = calibrate(b, [data[i] for i in train])
        for i in range(len(data)):
            if i % FOLDS == fold:
                oof[i] = predict(b, x[i])
    real = [d[2] for d in data]
    return {
        "beta": dict(zip(["constant"] + [n for n, _ in columns], [round(v, 5) for v in beta])),
        "n": len(data),
        "oof_r": round(statistics.correlation(oof, real), 3),
        "oof_mae": round(statistics.mean(abs(a - b) for a, b in zip(oof, real)), 3),
        "pred_sd": round(statistics.pstdev(oof), 3),
        "real_sd": round(statistics.pstdev(real), 3),
        "data": data,
        "oof": oof,
    }


def compare(name, data, formula):
    vals = [(formula(d[0]), d[2]) for d in data]
    vals = [(a, b) for a, b in vals if a is not None]
    a, b = zip(*vals) if vals else ((), ())
    if len(vals) < 3 or statistics.pstdev(a) == 0:
        return f"    {name}: n/a (coefficients not set)"
    return f"    {name}: r {statistics.correlation(a, b):.3f}  sd {statistics.pstdev(a):.3f}"


def main() -> int:
    targets = json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
    inputs = load_league_inputs()
    from nba_gm_data.sim import canonical_sim_cache, load_sim_context
    os.environ.setdefault("NBA_GM_RATINGS_MODEL", "legacy_traits")  # this fit reads the older traits
    canonical = load_sim_context(ROOT)["canonical"]
    traits = canonical_sim_cache(canonical)["traits_by_player"]
    rows = []
    for pid, t in targets.items():
        if t.get("minutes", 0) < MIN_MINUTES or pid not in inputs:
            continue
        row = {"id": pid, "name": t["name"], "minutes": float(t["minutes"]),
               "inputs": inputs[pid],
               "flat": box_rates.flatten_inputs(inputs[pid]),
               "traits": {k: float(v.get("value", 50.0)) for k, v in traits.get(pid, {}).items()}}
        for key, value in t.items():
            if key.endswith("_per36"):
                row[key] = float(value)
        rows.append(row)
    print(f"{len(rows)} rotation players with inputs ({MIN_MINUTES}+ minutes)\n")

    def inp(key, log=False):
        return (("log " if log else "") + key,
                (lambda r: math.log(max(1e-3, r["flat"][key]))) if log else (lambda r: r["flat"][key]))

    def trait(key):
        return key, lambda r: r["traits"].get(key, 50.0)

    specs = [
        ("turnovers per 36 (new ratings)", [inp("T08", True), inp("T07", True), inp("S16"), inp("S17")],
         lambda r: r["turnovers_per36"], None, lambda r: box_rates.turnovers_per36_from_inputs(r["inputs"])),
        ("assists per 36 (new ratings)", [inp("T01.pass", True), inp("T08", True), inp("F.execution"), inp("T07", True), inp("T01.post", True)],
         lambda r: r["assists_per36"], None, lambda r: box_rates.assists_per36_from_inputs(r["inputs"])),
        ("steals per 36 (new ratings)", [inp("S43"), inp("S42")],
         lambda r: r["steals_per36"], None, lambda r: box_rates.steals_per36_from_inputs(r["inputs"])),
        ("free-throw attempts per point (new ratings)", [inp("T18", True), inp("S24"), inp("T08", True)],
         lambda r: r["fta_per36"] / r["points_per36"] if r["points_per36"] else None, "points_per36",
         lambda r: box_rates.fta_per_point_from_inputs(r["inputs"])),
        ("points per 36 (new ratings)", [inp("T08", True), inp("T01.pass", True), inp("T01.shoot", True), inp("S10"), inp("T18", True)],
         lambda r: r["points_per36"], None, lambda r: box_rates.points_per36_from_inputs(r["inputs"])),
        ("points per 36 (old ratings)", [trait("handle_pressure"), trait("shot_versatility"), trait("rim_pressure"), trait("shooting_range")],
         lambda r: r["points_per36"], None, lambda r: box_rates.points_per36_from_traits(r["traits"])),
        ("turnovers per 36 (old ratings)", [trait("passing_reads"), trait("rim_pressure"), trait("scheme_iq")],
         lambda r: r["turnovers_per36"], None, lambda r: box_rates.turnovers_per36_from_traits(r["traits"])),
        ("steals per 36 (old ratings)", [trait("defensive_effort"), trait("screen_navigation"), trait("rim_deterrence")],
         lambda r: r["steals_per36"], None, lambda r: box_rates.steals_per36_from_traits(r["traits"])),
        ("free-throw attempts per point (old ratings)", [trait("rim_pressure"), trait("shooting_range")],
         lambda r: r["fta_per36"] / r["points_per36"] if r["points_per36"] else None, "points_per36",
         lambda r: box_rates.fta_per_point_from_traits(r["traits"])),
    ]
    for title, columns, target, scale_key, engine in specs:
        result = fit(rows, columns, target, scale_key=scale_key)
        print(title)
        print(f"  coefficients {json.dumps(result['beta'])}")
        print(f"  out-of-fold r {result['oof_r']}  mean abs error {result['oof_mae']}  "
              f"(prediction sd {result['pred_sd']} vs real {result['real_sd']}, n {result['n']})")
        print(compare("box_rates (engine) with its stored coefficients", result["data"], engine))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
