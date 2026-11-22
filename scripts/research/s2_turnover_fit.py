#!/usr/bin/env python3
"""Stage 2: refit the turnover rule (cards.TURNOVER) on expected turnovers in replayed games (fit half vs held half).

Why: the card rule was fitted to real turnovers per used possession, as if every player met the same game. In the loop
the same rule meets the game's own terms: the league level, the defence's ball pressure (his own man's and the five's),
transition, and how many chances his usage gives him. High-usage creators meet the most pressure and get the most
chances, so they ended up 30-70% above their real turnovers (Brown 6.5 per 36 against 3.8) even where their card rate
was close (RATINGS-FT-TOV follow-up, 2026-11-21).

How: replay every 2025-26 game once (real availability and minutes) with stage2.game.TO_TRACE set. Each turnover chance
records its terms outside the card rule (penalty, level, pressure, transition). For any setting of the rule's
coefficients, a player's expected turnovers are then sum over his chances of logistic(card rule + recorded terms),
without replaying. The coefficients (same terms as before) are fitted by damped Gauss-Newton on the fit half of
rotation players (the fixed hash of the other Stage 2 checks) against real 2025-26 turnovers per 36 at his replayed
minutes (weights = minutes, capped at 2000), and scored on the held-out half. The league level comes out of the fit's
constant (the loop's to_shift is unchanged). Players' inputs are never changed (rule 1).

    PYTHONPATH=src .venv/bin/python scripts/research/s2_turnover_fit.py [--runs 1] [--write-json]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids  # noqa: E402
from nba_gm_data.stage2 import cards as C  # noqa: E402
from nba_gm_data.stage2 import game as G  # noqa: E402
from nba_gm_data.stage2 import loop_fit as LF  # noqa: E402
from nba_gm_data.stage2.game_contexts import league_flat_inputs, split_half  # noqa: E402

TERMS = LF.TURNOVER_TERMS
BINS = 40
NAMED = ["player_phi-jaylen-brown", "player_orl-paolo-banchero", "player_det-cade-cunningham", "player_por-deni-avdija",
         "player_lal-luka-doncic", "player_cle-james-harden", "player_okc-shai-gilgeous-alexander",
         "player_nyk-jalen-brunson", "player_chi-josh-giddey", "player_den-nikola-jokic"]


def sig(z: float) -> float:
    return 1 / (1 + math.exp(-z)) if z > -30 else 0.0


def collect(runs: int):
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    G.TO_TRACE = {}
    box = defaultdict(lambda: [0.0, 0.0])   # minutes, turnovers
    for gid in ids:
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=1 + r, engine="stage2")
            for ln in res.player_lines:
                b = box[str(ln["player_id"])]
                b[0] += float(ln.get("minutes") or 0)
                b[1] += float(ln.get("turnovers") or 0)
    trace, G.TO_TRACE = G.TO_TRACE, None
    return trace, box, len(ids) * runs


def compress(offsets: list[float]) -> list[float]:
    """Equal-count quantile points of a player's recorded terms (the sum over chances is BINS x mean over points)."""
    s = sorted(offsets)
    n = len(s)
    return [s[min(n - 1, int((i + .5) * n / BINS))] for i in range(BINS)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--write-json", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    trace, box, games = collect(args.runs)
    flats = league_flat_inputs(ROOT)
    real = LF.real_rotation(ROOT)
    data = []
    for pid, row in real.items():
        offs = trace.get(pid)
        mins, sim_tov = box.get(pid, (0.0, 0.0))
        if not offs or mins < 200:
            continue
        x = [1.0] + [LF._value(flats[pid], t) for t in TERMS]
        data.append({"pid": pid, "name": row.get("name", pid), "x": x, "n": len(offs), "pts": compress(offs),
                     "minutes": mins, "real36": float(row["turnovers_per36"]), "sim36": 36 * sim_tov / mins,
                     "w": min(2000.0, float(row["minutes"])), "half": split_half(pid)})
    beta0 = [C.TURNOVER["constant"]] + [C.TURNOVER.get(t, 0.0) for t in TERMS]

    def per36(d, beta):
        z = sum(b * v for b, v in zip(beta, d["x"]))
        return 36 * d["n"] * statistics.fmean(sig(z + o) for o in d["pts"]) / d["minutes"]

    def grad36(d, beta):
        z = sum(b * v for b, v in zip(beta, d["x"]))
        dp = statistics.fmean(sig(z + o) * (1 - sig(z + o)) for o in d["pts"])
        scale = 36 * d["n"] / d["minutes"]
        return [scale * dp * v for v in d["x"]]

    fit = [d for d in data if d["half"] == 0]
    # Damped Gauss-Newton (Levenberg-Marquardt: the diagonal scaling copes with the different column scales).
    k = len(beta0)
    beta = list(beta0)
    lam = 1.0

    def loss(b):
        return sum(d["w"] * (per36(d, b) - d["real36"]) ** 2 for d in fit)

    current = loss(beta)
    for _ in range(60):
        a = [[0.0] * k for _ in range(k)]
        g = [0.0] * k
        for d in fit:
            r = per36(d, beta) - d["real36"]
            j = grad36(d, beta)
            for i in range(k):
                g[i] += d["w"] * j[i] * r
                for m in range(k):
                    a[i][m] += d["w"] * j[i] * j[m]
        improved = False
        for _ in range(10):
            aa = [[a[i][m] * (1 + lam if i == m else 1) for m in range(k)] for i in range(k)]
            delta = _solve(aa, [-v for v in g])
            trial = [b + s for b, s in zip(beta, delta)]
            new = loss(trial)
            if new < current:
                beta, current, lam, improved = trial, new, max(lam / 3, 1e-6), True
                break
            lam *= 4
        if not improved or abs(sum(abs(s) for s in delta)) < 1e-7:
            break

    def score(rows, b, sim=False):
        pred = [d["sim36"] if sim else per36(d, b) for d in rows]
        real = [d["real36"] for d in rows]
        w = [d["w"] for d in rows]
        return {"players": len(rows), "corr": round(statistics.correlation(pred, real), 3),
                "mean_abs": round(sum(abs(p - r) for p, r in zip(pred, real)) / len(rows), 3),
                "bias": round(sum(wi * (p - r) for p, r, wi in zip(pred, real, w)) / sum(w), 3)}

    held = [d for d in data if d["half"] == 1]
    out = {"games": games, "runs": args.runs, "seconds": round(time.time() - t0, 1),
           "replayed (current rule)": {"fit": score(fit, beta0, sim=True), "held": score(held, beta0, sim=True)},
           "expected, current rule": {"fit": score(fit, beta0), "held": score(held, beta0)},
           "expected, refitted rule": {"fit": score(fit, beta), "held": score(held, beta)},
           "rule": {"constant": round(beta[0], 5), **{t: round(b, 5) for t, b in zip(TERMS, beta[1:])}},
           "named": {d["name"]: {"real": d["real36"], "replayed": round(d["sim36"], 2),
                                 "expected_current": round(per36(d, beta0), 2), "expected_refit": round(per36(d, beta), 2)}
                     for d in data if d["pid"] in NAMED}}
    # High-usage creators (top quarter by chances per 36): where the old rule went wrong.
    top = sorted(data, key=lambda d: -d["n"] / d["minutes"])[: len(data) // 4]
    out["top usage quarter"] = {"current": score(top, beta0), "refit": score(top, beta)}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    if args.write_json:
        path = ROOT / "output/stage2/turnover_fit.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        if abs(m[col][col]) < 1e-15:
            continue
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] if abs(m[i][i]) > 1e-15 else 0.0 for i in range(n)]


if __name__ == "__main__":
    raise SystemExit(main())
