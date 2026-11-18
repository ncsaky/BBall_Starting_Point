"""Fit the playmaking (teammate shot-making) model behind the player card's Playmaking court chart.

Target: Basketball Index "Offensive eFG% Impact on Teammates" (percentage points of teammates' effective FG% with the
player on the court), minutes-weighted over 2023-24..2025-26 seasons of 500+ minutes. Features: the game's own traits
(inputs ratings model) and height, so generated players get the same treatment as real ones.

Writes data/canonical/court_influence_fit.json: coefficients and scaling only (derived; no Basketball Index rows).
Also prints a check of the engine's existing defensive suppression against Basketball Index's
"Defensive Impact on Opponent Shot Quality" (report only; the defense charts split the engine's existing values).

Run: PYTHONPATH=src .venv/bin/python scripts/fit_court_influence.py
"""
from __future__ import annotations

import gzip
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.ratings_model import install_inputs_model  # noqa: E402

TARGET = "Offensive eFG% Impact on Teammates"
DEFENSE_CHECK = ("Defensive Impact on Opponent Shot Quality", "Help Effectiveness Rating")
SEASONS = ("2023-24", "2024-25", "2025-26")
MIN_MINUTES = 500
FEATURES = ("passing_reads", "rim_pressure", "shooting_range", "handle_pressure", "shot_versatility", "height")
RIDGE = 8.0
OUT = ROOT / "data/canonical/court_influence_fit.json"


def bbi_values(metrics: set[str]) -> dict[str, dict[str, list[tuple[float, float]]]]:
    out: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    for path in sorted((ROOT / "data/research/bbi/normalized").glob("*.json.gz")):
        for row in json.load(gzip.open(path)):
            if row.get("metric_name") not in metrics or row.get("season") not in SEASONS or not row.get("canonical_player_id"):
                continue
            try:
                value, minutes = float(row["raw_value"]), float(row.get("minutes") or 0)
            except (TypeError, ValueError):
                continue
            if minutes >= MIN_MINUTES:
                out[row["canonical_player_id"]][row["metric_name"]].append((value, minutes))
    return out


def weighted(values: list[tuple[float, float]]) -> float:
    return sum(v * m for v, m in values) / sum(m for _, m in values)


def solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(n):
            if r != col:
                factor = a[r][col] / a[col][col]
                a[r] = [x - factor * y for x, y in zip(a[r], a[col])]
    return [a[i][n] / a[i][i] for i in range(n)]


def ridge(xs: list[list[float]], ys: list[float], ws: list[float]) -> tuple[float, list[float]]:
    k = len(xs[0])
    total = sum(ws)
    ybar = sum(w * y for w, y in zip(ws, ys)) / total
    xtx = [[sum(w * x[i] * x[j] for x, w in zip(xs, ws)) / total + (RIDGE / len(xs) if i == j else 0.0) for j in range(k)] for i in range(k)]
    xty = [sum(w * x[i] * (y - ybar) for x, y, w in zip(xs, ys, ws)) / total for i in range(k)]
    return ybar, solve(xtx, xty)


def main() -> None:
    canonical = load_app_canonical(ROOT)
    install_inputs_model(canonical, ROOT)
    traits: dict[str, dict[str, float]] = defaultdict(dict)
    for row in canonical["traits"]:
        traits[str(row["player_id"])][row["trait_key"]] = float(row.get("value") or 50.0)
    players = {str(p["id"]): p for p in canonical["players"]}
    evidence = bbi_values({TARGET, *DEFENSE_CHECK})

    rows = []
    for pid, metrics in evidence.items():
        if pid not in players or TARGET not in metrics:
            continue
        raw = {key: traits[pid].get(key, 50.0) for key in FEATURES if key != "height"}
        raw["height"] = float(players[pid].get("height_inches") or 78.0)
        rows.append((pid, raw, weighted(metrics[TARGET]), sum(m for _, m in metrics[TARGET])))
    means = {key: statistics.fmean(r[1][key] for r in rows) for key in FEATURES}
    sds = {key: statistics.pstdev(r[1][key] for r in rows) or 1.0 for key in FEATURES}
    xs = [[(r[1][key] - means[key]) / sds[key] for key in FEATURES] for r in rows]
    ys = [r[2] for r in rows]
    ws = [min(r[3], 6000.0) for r in rows]
    intercept, coef = ridge(xs, ys, ws)

    # Five-fold out-of-sample check.
    preds = [0.0] * len(rows)
    for fold in range(5):
        train = [i for i in range(len(rows)) if i % 5 != fold]
        b0, b = ridge([xs[i] for i in train], [ys[i] for i in train], [ws[i] for i in train])
        for i in range(len(rows)):
            if i % 5 == fold:
                preds[i] = b0 + sum(c * x for c, x in zip(b, xs[i]))
    fitted = [intercept + sum(c * x for c, x in zip(coef, x_row)) for x_row in xs]
    r_in = statistics.correlation(fitted, ys)
    r_out = statistics.correlation(preds, ys)
    print(f"players {len(rows)}  intercept {intercept:+.3f}  r in-sample {r_in:.3f}  out-of-fold {r_out:.3f}")
    for key, c in zip(FEATURES, coef):
        print(f"  {key:18s} {c:+.3f} pp per SD  (mean {means[key]:.1f}, sd {sds[key]:.1f})")
    ranked = sorted(zip(fitted, rows), key=lambda t: -t[0])
    print("top fitted:", ", ".join(f"{players[r[0]].get('name')} {f:+.2f} (BBI {r[2]:+.2f})" for f, r in ranked[:12]))
    print("bottom fitted:", ", ".join(f"{players[r[0]].get('name')} {f:+.2f} (BBI {r[2]:+.2f})" for f, r in ranked[-6:]))

    # Report-only check of the engine's existing zone defense against Basketball Index.
    from nba_gm_data.defense import zone_defense
    for metric in DEFENSE_CHECK:
        pairs = []
        for pid, metrics in evidence.items():
            if pid in players and metric in metrics:
                get = lambda key, default=50.0, t=traits[pid]: float(t.get(key, default))
                zones = zone_defense(get)
                pairs.append(((zones["rim"][0] + zones["midrange"][0] + zones["perimeter"][0]) / 3, weighted(metrics[metric])))
        if len(pairs) > 30:
            print(f"engine overall suppression vs {metric}: r {statistics.correlation(*zip(*pairs)):.3f} (n {len(pairs)})")

    OUT.write_text(json.dumps({
        "version": "court_influence_fit_v1",
        "target": TARGET, "seasons": list(SEASONS), "min_minutes": MIN_MINUTES, "players": len(rows),
        "intercept": round(intercept, 4),
        "features": {key: {"mean": round(means[key], 3), "sd": round(sds[key], 3), "pp_per_sd": round(c, 4)}
                     for key, c in zip(FEATURES, coef)},
        "r_in_sample": round(r_in, 3), "r_out_of_fold": round(r_out, 3),
        "note": "Teammates' effective FG% change (percentage points) with the player on the court; derived coefficients only.",
    }, indent=1) + "\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
