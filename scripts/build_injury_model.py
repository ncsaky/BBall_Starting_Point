#!/usr/bin/env python3
"""Fit the per-body-part injury model (v2) to Basketball Index Injury Tracker evidence.

Evidence: data/research/bbi/tools/injury_*.json (extracted by scripts/bbi_extract_tools.py from the signed-in tool page).
For each body part, a Poisson model of injuries per game played, fitted on real player-seasons 2015-16..2025-26:

    injuries(part) ~ games_played * exp(b0 + b . features)

features (standardized): age, age^2, height, weight, possessions per game (workload), rim pressure, offensive rebounding,
conditioning (stamina), center, guard, recent same-part injuries (time-decayed) and recent other-part injuries.
Ridge-penalized (intercept free). The same-part term is the compounding effect; age/body/style terms decide which
injuries a player tends to get. Recovery times are not modeled parametrically: the engine samples a real absence for
the drawn part (diagnosis, days, games), weighted toward recent seasons.

    PYTHONPATH=src .venv/bin/python scripts/build_injury_model.py [--write]
Writes data/canonical/injury_model_v2.json.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

B = ROOT / "data/research/bbi/tools"
OUT = ROOT / "data/canonical/injury_model_v2.json"
FIRST_SEASON = "2015-16"
RIDGE = 3.0
HISTORY_DECAY_YEARS = 1.5
PARTS = ["ankle", "knee", "back", "hamstring", "hip", "foot", "calf", "shoulder", "groin", "quadriceps", "toe", "head",
         "wrist", "hand", "achilles", "thumb"]
# Basketball Index's rarer parts folded into the nearest of its 16 risk parts.
MERGE = {"heel": "foot", "finger": "hand", "elbow": "shoulder", "forearm": "wrist", "arm": "shoulder", "leg": "calf",
         "shin": "calf", "neck": "back", "abdomen": "back", "ribs": "back", "chest": "back", "tailbone": "back",
         "eye": "head", "dental": "head"}
FEATURES = ["age", "age2", "height", "weight", "poss_pg", "rim_pressure", "offensive_rebounding", "stamina",
            "center", "guard", "prior_same", "prior_other"]


def rows(name):
    d = json.loads((B / name).read_text())
    return d["rows"] if isinstance(d, dict) and "rows" in d else d


def season_start(season: str) -> date:
    return date(int(season[:4]), 10, 20)


def part_of(h) -> str | None:
    if h.get("cat") == "illness":
        return "illness"
    if h.get("cat") != "injury" or not h.get("part"):
        return None
    p = MERGE.get(h["part"], h["part"])
    return p if p in PARTS else None


def poisson_ridge(X, y, exposure, lam=RIDGE, iters=60):
    """Newton/IRLS for log-link Poisson with offset log(exposure); ridge on all but the intercept."""
    n = len(X[0])
    b = [0.0] * n
    rate = sum(y) / max(1e-9, sum(exposure))
    b[0] = math.log(max(rate, 1e-7))
    for _ in range(iters):
        g = [0.0] * n
        H = [[0.0] * n for _ in range(n)]
        for x, yi, e in zip(X, y, exposure):
            eta = sum(bi * xi for bi, xi in zip(b, x))
            mu = e * math.exp(max(-30.0, min(30.0, eta)))
            r = yi - mu
            for i in range(n):
                g[i] += r * x[i]
                for j in range(i, n):
                    H[i][j] += mu * x[i] * x[j]
        for i in range(1, n):
            g[i] -= lam * b[i]
            H[i][i] += lam
        for i in range(n):
            for j in range(i):
                H[i][j] = H[j][i]
        # Solve H d = g (Gaussian elimination).
        A = [row[:] + [gi] for row, gi in zip(H, g)]
        for i in range(n):
            piv = max(range(i, n), key=lambda r: abs(A[r][i]))
            A[i], A[piv] = A[piv], A[i]
            for r in range(i + 1, n):
                f = A[r][i] / A[i][i]
                for c in range(i, n + 1):
                    A[r][c] -= f * A[i][c]
        d = [0.0] * n
        for i in reversed(range(n)):
            d[i] = (A[i][n] - sum(A[i][k] * d[k] for k in range(i + 1, n))) / A[i][i]
        b = [bi + di for bi, di in zip(b, d)]
        if max(abs(di) for di in d) < 1e-7:
            break
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.save import trait_values_by_player
    canonical = load_app_canonical(ROOT)
    players = {p["id"]: p for p in canonical["players"]}
    traits = trait_values_by_player(canonical)

    history = rows("injury_player_history.json")
    seasons = rows("injury_player_seasons.json")
    by_player = defaultdict(list)
    for h in history:
        part = part_of(h)
        if part and h.get("player_id") and h.get("start"):
            by_player[h["player_id"]].append((date.fromisoformat(h["start"][:10]), part, h))

    data = []   # (pid, season, gp, features_raw dict, Counter of part injuries)
    for r in seasons:
        pid = r.get("player_id")
        if not pid or pid not in players or r["season"] < FIRST_SEASON or (r.get("gp") or 0) < 10:
            continue
        p, t = players[pid], traits.get(pid, {})
        birth = p.get("birthdate") or p.get("birth_date")
        if not birth:
            continue
        start = season_start(r["season"])
        age = (start - date.fromisoformat(str(birth)[:10])).days / 365.25
        in_season = Counter(part for d, part, _ in by_player[pid]
                            if r["season"] == _["season"])
        prior = defaultdict(float)
        for d, part, _ in by_player[pid]:
            if d < start:
                prior[part] += math.exp(-((start - d).days / 365.25) / HISTORY_DECAY_YEARS)
        pos = str(p.get("position") or "")
        data.append((pid, r["season"], r["gp"], {
            "age": age, "height": float(p.get("height_inches") or 78), "weight": float(p.get("weight_lbs") or 215),
            "poss_pg": (r.get("poss") or 0) / max(1, r["gp"]),
            "rim_pressure": float(t.get("rim_pressure", 50)), "offensive_rebounding": float(t.get("offensive_rebounding", 50)),
            "stamina": float(t.get("stamina_cardio", 50)), "center": 1.0 if "C" in pos else 0.0,
            "guard": 1.0 if pos.startswith(("PG", "SG", "G")) else 0.0,
        }, in_season, prior))

    raw_cols = ["age", "height", "weight", "poss_pg", "rim_pressure", "offensive_rebounding", "stamina"]
    mu = {c: statistics.fmean(d[3][c] for d in data) for c in raw_cols}
    sd = {c: statistics.pstdev(d[3][c] for d in data) or 1.0 for c in raw_cols}

    def featurize(f, prior_same, prior_other):
        z = {c: (f[c] - mu[c]) / sd[c] for c in raw_cols}
        return [1.0, z["age"], z["age"] ** 2, z["height"], z["weight"], z["poss_pg"], z["rim_pressure"],
                z["offensive_rebounding"], z["stamina"], f["center"], f["guard"], prior_same, prior_other]

    model = {"version": "injury_model_v2_2026_11_18", "source": "Basketball Index Injury Tracker (data/research/bbi/tools)",
             "first_season": FIRST_SEASON, "player_seasons": len(data), "games": sum(d[2] for d in data),
             "features": FEATURES, "standardization": {"mean": mu, "sd": sd}, "history_decay_years": HISTORY_DECAY_YEARS,
             "parts": {}, "merge": MERGE}
    for part in [*PARTS, "illness"]:
        X, y, e = [], [], []
        for pid, season, gp, f, in_season, prior in data:
            same = prior.get(part, 0.0)
            other = sum(v for k, v in prior.items() if k != part)
            X.append(featurize(f, same, other))
            y.append(in_season.get(part, 0))
            e.append(gp)
        b = poisson_ridge(X, y, e)
        model["parts"][part] = {"intercept": b[0], "coef": dict(zip(FEATURES, b[1:])),
                                "injuries": sum(y), "per_1000_games": round(1000 * sum(y) / sum(e), 3)}
        print(f"{part:11s} n={sum(y):5d} per1000={1000*sum(y)/sum(e):5.2f}  " +
              " ".join(f"{k}={v:+.2f}" for k, v in zip(FEATURES, b[1:]) if abs(v) >= 0.08))

    # Recovery pools: real absences per part (diagnosis, days, games, surgery), most recent seasons first.
    pools = defaultdict(list)
    for h in history:
        part = part_of(h)
        if part and h["season"] >= FIRST_SEASON and h.get("days"):
            pools[part].append({"label": h.get("label"), "days": int(h["days"]), "games": int(h.get("games") or 0),
                                "surgery": int(h.get("surgery") or 0), "season": h["season"],
                                "censored": int(h.get("censored") or 0)})
    model["recovery_pools"] = {k: sorted(v, key=lambda r: r["season"], reverse=True) for k, v in pools.items()}
    model["recurrence_reference"] = {r["bucket"]: r["risk_ratio"] for r in rows("injury_recurrence.json")
                                     if r.get("level") == "body_part" and r.get("risk_ratio")}
    long_term = [r for r in rows("injury_long_term.json") if (r.get("d_rapm_1y_shrunk_ci") or [0, 0])[1] < 0]
    model["lasting_effects"] = [{k: r.get(k) for k in ("level", "bucket", "region", "n_treated", "d_rapm_1y_shrunk",
                                                       "d_rapm_1y_shrunk_ci", "d_rapm_2y", "d_poss_1y_pct")}
                                for r in long_term]
    model["return_ramp"] = rows("injury_short_term.json")
    print("lasting effects (CI below zero):", [(r["level"], r["bucket"], r["d_rapm_1y_shrunk"]) for r in model["lasting_effects"]])
    if args.write:
        OUT.write_text(json.dumps(model, separators=(",", ":")) + "\n")
        print("wrote", OUT, f"{OUT.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
