#!/usr/bin/env python3
"""What makes up the spread miss (S2-FINISHES, part 2): Stage 2 against today's engine.

Reads per-game files from `s2_totals_check.py collect` (8+ runs a game, every 2025-26 game, real availability and
minutes) and splits the betting test's spread miss (|mean of 20 runs' home margin - market spread|) into:
- the league home-court level (mean of the expected margins against the market's);
- how far the expected margins move with the market's (slope, correlation);
- team-by-team errors (each team's average error over its games, home and away);
- run-to-run noise (each game's margin spread across runs, divided by the 20 runs of the test);
and predicts the 20-run miss from the systematic part plus noise.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_spread_check.py output/stage2/totals_games_stage2_x.json \
        output/stage2/totals_games_current_x.json
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def _phi(z: float) -> float:
    return .5 * (1 + math.erf(z / math.sqrt(2)))


def mae(mu: float, s: float) -> float:
    if s <= 0:
        return abs(mu)
    z = mu / s
    return s * math.sqrt(2 / math.pi) * math.exp(-z * z / 2) + mu * (1 - 2 * _phi(-z))


def corr(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy)


def slope(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / sum((b - my) ** 2 for b in y)


def analyse(path: Path, runs_target: int = 20) -> dict:
    data = json.loads(path.read_text())
    runs = data["runs"]
    rows = [r for r in data["games"] if r.get("market_spread") is not None]
    sim = [r["sim_home"] - r["sim_away"] for r in rows]
    mkt = [float(r["market_spread"]) for r in rows]
    real = [r["real_home"] - r["real_away"] for r in rows if r.get("real_home") is not None]
    err = [a - b for a, b in zip(sim, mkt)]
    sd_game = math.sqrt(statistics.fmean([r["sim_margin_sd"] ** 2 for r in rows])) * math.sqrt(runs / (runs - 1))
    noise_n = sd_game ** 2 / runs
    sys_var = max(0.0, statistics.pvariance(err) - noise_n)
    bias = statistics.fmean(err)
    # Team-by-team: each team's mean error as home (err) and as away (-err), shrunk by its noise.
    team_err = defaultdict(list)
    for r, e in zip(rows, err):
        team_err[r["home"]].append(e)
        team_err[r["away"]].append(-e)
    team_mean = {t: statistics.fmean(v) for t, v in team_err.items()}
    team_sd = statistics.pstdev(list(team_mean.values()))
    # Residual after the league bias, the slope against the market and team terms.
    b = slope(sim, mkt)
    fitted = [statistics.fmean(sim) + b * (m - statistics.fmean(mkt)) for m in mkt]
    resid_slope = [s - f for s, f in zip(sim, fitted)]
    out = {
        "file": path.name, "engine": data["engine"], "runs": runs, "games": len(rows),
        "home_margin_sim": round(statistics.fmean(sim), 2), "home_margin_market": round(statistics.fmean(mkt), 2),
        "home_margin_real": round(statistics.fmean(real), 2),
        "corr_with_market": round(corr(sim, mkt), 3), "slope_on_market": round(b, 3),
        "sd_expected_margin": round(statistics.pstdev(sim), 2), "sd_market": round(statistics.pstdev(mkt), 2),
        "corr_with_real": round(corr([r["sim_home"] - r["sim_away"] for r in rows if r.get("real_home") is not None],
                                     real), 3),
        "run_sd_of_margin": round(sd_game, 2),
        "noise_sd_at_20_runs": round(sd_game / math.sqrt(runs_target), 2),
        "systematic_sd": round(math.sqrt(sys_var), 2),
        "team_error_sd": round(team_sd, 2),
        "after_slope_sd": round(math.sqrt(max(0.0, statistics.pvariance(resid_slope) - noise_n)), 2),
        "miss_at_runs": round(statistics.fmean(abs(e) for e in err), 3),
        "predicted_miss_20": round(mae(bias, math.sqrt(sys_var + sd_game ** 2 / runs_target)), 3),
        "predicted_miss_20_no_bias": round(mae(0.0, math.sqrt(sys_var + sd_game ** 2 / runs_target)), 3),
        "predicted_miss_infinite_runs": round(mae(bias, math.sqrt(sys_var)), 3),
        "worst_teams": sorted(((t, round(v, 2)) for t, v in team_mean.items()), key=lambda x: -abs(x[1]))[:8],
    }
    return out


def main() -> int:
    res = [analyse(Path(p)) for p in sys.argv[1:]]
    keys = [k for k in res[0] if k not in ("file", "worst_teams")]
    print(f"{'':32}" + "".join(f"{r['engine'][:10]:>14}" for r in res))
    for k in keys:
        print(f"{k:32}" + "".join(f"{str(r[k]):>14}" for r in res))
    for r in res:
        print(r["engine"], "worst teams (mean error, home-side points):", r["worst_teams"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
