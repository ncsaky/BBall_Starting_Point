"""Logistic fit of single-game absences of regulars (rows from rest_patterns.py --rows). Pure Python (no numpy).

PYTHONPATH=src .venv/bin/python scripts/research/fit_rest_model.py output/smart-rest/real_rows.json [--model NAME]
Prints each factor's odds multiplier with its standard error, and the fit against simpler models.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c and m[r][c]:
                f = m[r][c] / m[c][c]
                for k in range(c, n + 1):
                    m[r][k] -= f * m[c][k]
    return [m[i][n] / m[i][i] for i in range(n)]


def invert(a: list[list[float]]) -> list[list[float]]:
    n = len(a)
    cols = [solve(a, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def logistic_fit(x: list[list[float]], y: list[int], ridge: float = 1e-6, iters: int = 25):
    k = len(x[0])
    beta = [0.0] * k
    beta[0] = math.log(max(1e-6, sum(y) / len(y)) / (1 - sum(y) / len(y)))
    for _ in range(iters):
        h = [[ridge if i == j else 0.0 for j in range(k)] for i in range(k)]
        g = [0.0] * k
        for xi, yi in zip(x, y):
            z = sum(b * v for b, v in zip(beta, xi))
            p = 1 / (1 + math.exp(-z))
            w = p * (1 - p)
            for i in range(k):
                if xi[i]:
                    g[i] += (yi - p) * xi[i]
                    wi = w * xi[i]
                    for j in range(i, k):
                        if xi[j]:
                            h[i][j] += wi * xi[j]
        for i in range(k):
            for j in range(i):
                h[i][j] = h[j][i]
        step = solve(h, g)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-7:
            break
    cov = invert(h)
    ll = sum(yi * math.log(p) + (1 - yi) * math.log(1 - p) for xi, yi in zip(x, y)
             for p in [1 / (1 + math.exp(-sum(b * v for b, v in zip(beta, xi))))])
    return beta, [math.sqrt(max(0.0, cov[i][i])) for i in range(k)], ll


def late_situation(r):
    if r["games_left"] >= 20 or r["games_left"] < 2:
        return None
    if r["best"] > 10 and r["league_rank"] > 22:
        return "out"
    return "race" if r["line_in_play"] else "locked"


FEATURES = {
    "second night of a back-to-back": lambda r: r["b2b"],
    "first night of a back-to-back": lambda r: r["b2b_first"],
    "second night on the road": lambda r: r["b2b"] * (1 - r["home"]),
    "star (top 45)": lambda r: r["star"],
    "opponent weakness (per .100 below .500)": lambda r: (0.5 - r["opp_pct"]) * 10.0,
    "season progress (0 to 1)": lambda r: (r["game_no"] or 41) / 82.0,
    "last 20 games, seed locked": lambda r: int(late_situation(r) == "locked"),
    "last 20 games, out of the race": lambda r: int(late_situation(r) == "out"),
    "opponent strength above .600 (per .100)": lambda r: max(0.0, r["opp_pct"] - 0.6) * 10.0,
    "road trip game 3+": lambda r: int(r["trip"] >= 3),
    "minutes a game (per 5 over 30)": lambda r: (r["mpg"] - 30.0) / 5.0,
    "back-to-back within 5 games of a return": lambda r: r["b2b"] * int(r.get("since_return") is not None and r["since_return"] <= 5),
    # OVERNIGHT-REST-GAMES: national TV games (ESPN, ABC, NBC, Peacock, Prime Video; scripts/research/national_tv.py)
    "national TV (ESPN/ABC/NBC/Peacock/Prime)": lambda r: r.get("tv", 0),
    # OVERNIGHT-REST-GAMES: the age shape (in-sample, the linear age term under-rested 30-33s on back-to-backs and
    # over-rested players under 25)
    "age 30+ on back-to-back nights": lambda r: int((r["age"] or 27.0) >= 30) * max(r["b2b"], r["b2b_first"]),
    "age per year under 27 (down to 21)": lambda r: max(0.0, 27.0 - max(21.0, r["age"] or 27.0)),
}
EXTRA = {
    # the original linear age term (SMART-REST); with the age shape below it adds nothing (x0.99)
    "age over 27 (per year, up to 34)": lambda r: max(0.0, min(34.0, r["age"] or 27.0) - 27.0),
    "back-to-back miles (per 1000)": lambda r: r["b2b"] * r["miles"] / 1000.0,
    "travel miles (per 1000)": lambda r: r["miles"] / 1000.0,
    "time zones crossed": lambda r: abs(r["tz"]),
    "star x opponent weakness": lambda r: r["star"] * (0.5 - r["opp_pct"]) * 10.0,
    "own win pct (per .100 over .500)": lambda r: (r["win_pct"] - 0.5) * 10.0,
    "home (other nights)": lambda r: r["home"] * (1 - r["b2b"]),
    "national TV, star": lambda r: r.get("tv", 0) * r["star"],
    "national TV, not a star": lambda r: r.get("tv", 0) * (1 - r["star"]),
    "NBA TV only": lambda r: r.get("nbatv", 0),
    "age over 27 on back-to-back nights (per year)": lambda r: max(0.0, min(34.0, r["age"] or 27.0) - 27.0) * max(r["b2b"], r["b2b_first"]),
    "age over 27 on second nights (per year)": lambda r: max(0.0, min(34.0, r["age"] or 27.0) - 27.0) * r["b2b"],
    "NBA TV only, star": lambda r: r.get("nbatv", 0) * r["star"],
}


def run(rows, names):
    feats = {**FEATURES, **EXTRA}
    x = [[1.0] + [float(feats[n](r)) for n in names] for r in rows]
    y = [r["miss"] for r in rows]
    beta, se, ll = logistic_fit(x, y)
    return beta, se, ll


if __name__ == "__main__":
    rows = json.loads(Path(sys.argv[1]).read_text())
    rows = [r for r in rows if r.get("age") is not None]
    base = list(FEATURES)
    beta, se, ll = run(rows, base)
    print(f"rows {len(rows)}, absences {sum(r['miss'] for r in rows)}; log-likelihood {ll:.1f}")
    print(f"  {'intercept':<44} {beta[0]:+.3f} (base rate {100 / (1 + math.exp(-beta[0])):.2f}%)")
    for n, b, s in zip(base, beta[1:], se[1:]):
        print(f"  {n:<44} x{math.exp(b):5.2f}  (coef {b:+.3f}, se {s:.3f}, z {b / s if s else 0:+.1f})")
    print("\nAdded one at a time (likelihood-ratio gain; 1.9 = 5% significance):")
    for extra in EXTRA:
        b2, s2, ll2 = run(rows, base + [extra])
        print(f"  {extra:<44} x{math.exp(b2[-1]):5.2f} (se {s2[-1]:.3f}, z {b2[-1] / s2[-1]:+.1f}), LL gain {ll2 - ll:+.2f}")
    print("\nDropped one at a time (likelihood-ratio loss):")
    for name in base:
        _, _, ll3 = run(rows, [n for n in base if n != name])
        print(f"  {name:<44} LL loss {ll - ll3:+.2f}")
    Path(sys.argv[1]).with_suffix(".fit.json").write_text(json.dumps({"features": ["intercept", *base], "coef": beta, "se": se}, indent=1))
