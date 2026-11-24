#!/usr/bin/env python3
"""Betting-odds test summary for one engine and seed (the season test, real availability and minutes).

    PYTHONPATH=src .venv/bin/python scripts/research/s2_odds.py ENGINE RUNS SEED [LIMIT|all] [OUT.json] [loop.KEY=V ...]
        [coach.KEY=V ...]

Trailing loop.KEY=V / coach.KEY=V arguments override Stage 2's LOOP / COACH numbers for the run (research variants).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from nba_gm_data.sim import validate_season_probabilities  # noqa: E402

overrides = [a for a in sys.argv[1:] if a.startswith(("loop.", "coach."))]
sys.argv = [a for a in sys.argv if a not in overrides]
applied = {}
for a in overrides:
    key, value = a.split("=", 1)
    table, name = key.split(".", 1)
    if table == "loop":
        from nba_gm_data.stage2 import game as G
        G.LOOP[name] = float(value)
    else:
        from nba_gm_data.stage2 import coach as C
        C.COACH[name] = float(value)
    applied[key] = float(value)
engine, runs, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
limit = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != "all" else None
t0 = time.time()
rep = validate_season_probabilities(ROOT, runs=runs, seed=seed, limit=limit, engine=engine)
s = rep["summary"]
out = {"engine": engine, "runs": runs, "seed": seed, "limit": limit, "overrides": applied, "seconds": round(time.time() - t0, 1),
       "games": rep["game_count"], **{k: v for k, v in s.items() if not isinstance(v, (list, dict))}}
print(json.dumps(out, indent=1))
if len(sys.argv) > 5:
    Path(sys.argv[5]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[5]).write_text(json.dumps(out, indent=1))
