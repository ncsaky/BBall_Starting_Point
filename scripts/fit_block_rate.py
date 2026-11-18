#!/usr/bin/env python3
"""Fit the box-score block rate (sim.block_rate_per36) to real 2025-26 blocks per 36 minutes.

Real rates: data/calibration/nba_2025_26_targets.json (players with 500+ minutes). Features: the engine's effective
rim protection (defense.rim_response of the rim_deterrence trait) and, in the new-ratings model, the player's
contest-commitment tendency (T16 "jump" share: whether he chooses to leave his feet to contest). Blocks are skill
times choice: Jokic positions well but rarely jumps at shots; Huff jumps at everything.

Model: blocks per 36 = exp(a + b * rim + c * jump) - 0.05, least squares on log(blocks + 0.05), minutes-weighted,
intercept then shifted so the minutes-weighted mean matches the real one (league blocks stay right).
Prints coefficients for both rating sets; they are pasted into defense.block_rate_per36 (reviewed), like
sim.rebound_rate_per_minute. In use: legacy ratings take the rim-only line from `--quadratic` (adds a (rim/100)^2 term,
weighted r 0.77 vs 0.76); new ratings take the linear rim + contest-jump line from a plain run (r 0.86).

    PYTHONPATH=src .venv/bin/python scripts/fit_block_rate.py
"""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from fit_impact_value import ridge, wcorr  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.defense import rim_response  # noqa: E402
from nba_gm_data.ratings_model import effective_inputs, install_inputs_model  # noqa: E402
from nba_gm_data.defense import contest_jump_share  # noqa: E402

MIN_MINUTES = 500
OFFSET = 0.05


def rows_for(canonical, targets, with_jump):
    traits = {}
    for t in canonical["traits"]:
        traits.setdefault(t["player_id"], {})[t["trait_key"]] = float(t.get("value") or 50.0)
    out = []
    for pid, real in targets.items():
        if pid not in traits or (real.get("minutes") or 0) < MIN_MINUTES or real.get("blocks_per36") is None:
            continue
        rim = rim_response(traits[pid].get("rim_deterrence", 50.0))
        feats = [1.0, rim, (rim / 100.0) ** 2] if "--quadratic" in sys.argv else [1.0, rim]
        if with_jump:
            jump = contest_jump_share(effective_inputs(canonical, pid))
            if jump is None:
                continue
            feats.append(jump)
        out.append((pid, feats, real["blocks_per36"], real["minutes"]))
    return out


def fit(rows, label):
    X = [r[1] for r in rows]
    y = [math.log(r[2] + OFFSET) for r in rows]
    w = [r[3] for r in rows]
    coef = ridge(X, y, w, 1e-6)
    real = [r[2] for r in rows]
    # Smearing: exp(mean log) underestimates the mean, so shift the intercept until minutes-weighted means agree.
    for _ in range(50):
        pred = [max(0.0, math.exp(sum(a * b for a, b in zip(c, coef))) - OFFSET) for c in X]
        ratio = sum(t * v for t, v in zip(real, w)) / sum(q * v for q, v in zip(pred, w))
        if abs(ratio - 1.0) < 1e-7:
            break
        coef[0] += math.log(ratio)
    mae = sum(abs(p - t) * v for p, t, v in zip(pred, real, w)) / sum(w)
    bias = sum((p - t) * v for p, t, v in zip(pred, real, w)) / sum(w)
    print(f"{label}: {len(rows)} players; coefficients {[round(c, 6) for c in coef]}; weighted r {wcorr(real, pred, w):.3f}; "
          f"weighted mean abs error {mae:.3f} per 36; bias {bias:+.3f}")
    return coef


def main() -> int:
    targets = json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
    base = load_app_canonical(ROOT)
    fit(rows_for(copy.deepcopy(base), targets, False), "legacy ratings (rim only)")
    install_inputs_model(base, ROOT)
    fit(rows_for(base, targets, False), "new ratings (rim only)")
    fit(rows_for(base, targets, True), "new ratings (rim + contest jump share)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
