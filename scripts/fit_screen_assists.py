#!/usr/bin/env python3
"""Fit each player's screen assists per 36 to the screening inputs (Basketball Index 2023-24..2025-26).

Target: Basketball Index "Screen Assists Per 75 Possessions" (screens that directly lead to a teammate's made shot),
minutes- and recency-weighted over three seasons (weights 1, .5, .25), players with 500+ minutes, converted to per 36
minutes at the league pace (75 possessions ~ 36 minutes at ~100 possessions per 48). The model is log-linear like the
other box-score rate fits (box_rates.py): screen execution (S27), screen-action recognition (S28), how often a player is
the screener (T11 screen and roll shares) and body mass (P04, display grade). Weighted least squares with a minutes
weight, five-fold out-of-fold correlation reported. Writes the coefficients to stdout (paste into box_rates.py).

Usage: PYTHONPATH=src .venv/bin/python scripts/fit_screen_assists.py
"""
from __future__ import annotations

import gzip
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.box_rates import flatten_inputs  # noqa: E402
from nba_gm_data.ratings_model import load_league_inputs  # noqa: E402

FEATURES = ("S27", "S28", "log T11.screen", "log T11.roll", "P04")
# 36 minutes at the league pace (~102 possessions per 48 minutes) is ~76 possessions, so per 75 ~ per 36.
PER75_TO_PER36 = 102.0 / 48.0 * 36.0 / 75.0


def weighted_metric(table, name, seasons=("2025-26", "2024-25", "2023-24"), weights=(1.0, 0.5, 0.25)):
    acc = {}
    for season, w in zip(seasons, weights):
        for _key, (value, minutes, cid) in table.get(f"{season}|{name}", {}).items():
            if not cid or minutes <= 0:
                continue
            a = acc.setdefault(cid, [0.0, 0.0, 0.0])
            a[0] += value * minutes * w
            a[1] += minutes * w
            a[2] += minutes
    return {pid: (a[0] / a[1], a[2]) for pid, a in acc.items() if a[1] > 0}


def design(flat):
    row = [1.0]
    for key in FEATURES:
        name = key[4:] if key.startswith("log ") else key
        value = flat.get(name)
        if value is None:
            return None
        if key.startswith("log "):
            if value <= 0:
                return None
            value = math.log(value)
        row.append(value)
    return row


def wls(X, y, w):
    k = len(X[0])
    A = [[sum(w[n] * X[n][i] * X[n][j] for n in range(len(X))) for j in range(k)] for i in range(k)]
    b = [sum(w[n] * X[n][i] * y[n] for n in range(len(X))) for i in range(k)]
    for i in range(k):
        A[i][i] += 1e-6
    for i in range(k):
        for j in range(i + 1, k):
            f = A[j][i] / A[i][i]
            for c in range(i, k):
                A[j][c] -= f * A[i][c]
            b[j] -= f * b[i]
    beta = [0.0] * k
    for i in reversed(range(k)):
        beta[i] = (b[i] - sum(A[i][j] * beta[j] for j in range(i + 1, k))) / A[i][i]
    return beta


def corr(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / ((sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** .5)


def main() -> int:
    table = json.loads(gzip.decompress((ROOT / "data/research/bbi/values_recent.json.gz").read_bytes()))["table"]
    target = weighted_metric(table, "Screen Assists Per 75 Possessions")
    inputs = load_league_inputs()
    X, y, w, ids = [], [], [], []
    for pid, (value, minutes) in sorted(target.items()):
        if minutes < 500 or pid not in inputs:
            continue
        row = design(flatten_inputs(inputs[pid]))
        if row is None:
            continue
        X.append(row)
        y.append(math.log(max(value, 0.03) * PER75_TO_PER36))
        w.append(min(minutes, 6000.0))
        ids.append(pid)
    beta = wls(X, y, w)
    folds = 5
    oof = [0.0] * len(X)
    for f in range(folds):
        train = [i for i in range(len(X)) if i % folds != f]
        b = wls([X[i] for i in train], [y[i] for i in train], [w[i] for i in train])
        for i in range(len(X)):
            if i % folds == f:
                oof[i] = sum(c * v for c, v in zip(b, X[i]))
    real = [math.exp(v) for v in y]
    # A log fit predicts the geometric mean; shift the constant so the minutes-weighted mean matches the real one.
    pred = [math.exp(sum(c * v for c, v in zip(beta, row))) for row in X]
    beta[0] += math.log(sum(a * b for a, b in zip(w, real)) / sum(a * b for a, b in zip(w, pred)))
    print(f"minutes-weighted real mean {sum(a * b for a, b in zip(w, real)) / sum(w):.3f} per 36")
    print(f"players {len(X)}; out-of-fold r (per 36, raw scale) {corr([math.exp(v) for v in oof], real):.3f}; log scale {corr(oof, y):.3f}")
    for name, c in zip(("constant", *FEATURES), beta):
        print(f"  {name:<16} {c:+.5f}")
    print("SCREEN_ASSISTS_INPUTS =", json.dumps({name: round(c, 5) for name, c in zip(("constant", *FEATURES), beta)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
