#!/usr/bin/env python3
"""Stage 2 team ball-screen schemes (S2-SCHEMES, part 1): fit each coaching staff's scheme on top of its personnel.

The coverage call (stage2.screens) already follows the two defenders in the action: a slow rim protector drops, like-
sized defenders switch. Real teams also differ by coach. The scheme study (data/research/defensive_scheme_evidence.json,
docs/agents/tasks/defensive-scheme-evidence.md) measured, per 2025-26 team:
- ball-screen coverage aggression (Basketball Index, bigs' minutes; how high the big plays the screen: drop low, show and
  trap high). It tracks the bigs' mobility and height (r .68 and -.53) and not switching (r -.14 with guards' time on
  centers). Versatility moves with it (r .91), so the two are one axis here;
- guards' assigned time against centers (NBA matchups), the switching proxy.
Neither has a public conversion to coverage percentages. So the fit works on the engine's own scale:
1. replay the 2025-26 games (real lineups) and record every ball screen's personnel log-odds (game.COVERAGE_TRACE);
2. per team, the engine's personnel-only proxies: the share of its bigs' screens it does not drop (aggression) and the
   share of bigs' screens it switches (a guard ends up on the big);
3. across the 30 teams, the scale (index points per unit of the engine proxy) is the ratio of their spreads (one team
   spread of the measure = one team spread of the proxy); a least-squares line would understate it, because the
   engine proxy measures the real habit with error (r .54 for aggression, .23 for switching), and dividing by an
   understated scale would blow up the tilts. Each team's leftover (observed minus what its personnel predicts on
   that scale) is its staff's scheme;
4. the leftover times a reliability (the share of a team's measure its history predicts in the study's held-out
   season: aggression 1 - (4.00/5.82)^2 = .53 for the teams that kept their coach, switching 1 - (.80/.93)^2 = .26) is
   turned back into a log-odds tilt on the coverage call (drop and trap for aggression, switch for switching) by
   solving for the tilt that moves the team's proxy that far.
The table (src/nba_gm_data/stage2/scheme_table.py) is keyed by head coach, with his team; stage2.schemes reads it.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_scheme_fit.py --runs 2 [--write]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "output" / "s2schemes"
PREFS = ROOT / "src" / "nba_gm_data" / "stage2" / "scheme_table.py"
RELIABILITY = {"aggression": .53, "switching": .26}


def _sig(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def norm(name: str) -> str:
    return unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower().strip()


def proxies(rows: list, agg: float = 0.0, swi: float = 0.0) -> tuple[float, float, dict]:
    """Engine proxies for one team's screens: (share of bigs' screens not dropped among those not switched, share of
    bigs' screens switched, the full mix over all screens)."""
    from nba_gm_data.stage2.screens import probabilities_from_logits
    nd = sw = n = 0.0
    mix = [0.0] * 4
    for big, zs in rows:
        p = probabilities_from_logits(*zs, (agg, swi))
        for k in range(4):
            mix[k] += p[k]
        if big:
            n += 1
            sw += p[0]
            nd += 1.0 - _sig(zs[1] - agg)
    tot = len(rows)
    return nd / n, sw / n, {k: round(v / tot, 4) for k, v in zip(("switch", "drop", "show", "trap"), mix)}


def solve(rows: list, target: float, which: int) -> float:
    lo, hi = -4.0, 4.0
    for _ in range(40):
        mid = (lo + hi) / 2
        v = proxies(rows, mid, 0.0)[0] if which == 0 else proxies(rows, 0.0, mid)[1]
        if v < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def line(x: list, y: list) -> tuple[float, float, float]:
    """Spread-matching line (y = a + b x with b = sd(y) / sd(x)) and the correlation."""
    mx, my = st.fmean(x), st.fmean(y)
    b = st.pstdev(y) / st.pstdev(x)
    return my - b * mx, b, st.correlation(x, y)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--write", action="store_true", help="write the coach table into the package")
    ap.add_argument("--reuse", action="store_true", help="reuse the cached screen trace")
    args = ap.parse_args()
    from nba_gm_data.stage2 import game as G
    from nba_gm_data.stage2 import schemes as SCH
    from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids
    import pickle
    cache = OUT / "coverage_trace.pkl"
    t0 = time.time()
    if args.reuse and cache.exists():
        trace = pickle.loads(cache.read_bytes())
    else:
        SCH.ENABLED = False       # personnel only while measuring
        G.COVERAGE_TRACE = trace = []
        ctx = load_sim_context(ROOT)
        for gid in validation_game_ids(ctx, None, False):
            for r in range(args.runs):
                sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=args.seed + r, engine="stage2")
        G.COVERAGE_TRACE = None
        SCH.ENABLED = True
        OUT.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(pickle.dumps(trace))
    by_team = defaultdict(list)
    for abbrev, big, zs in trace:
        by_team[abbrev].append((big, zs))
    print(f"{len(trace)} ball screens in {time.time() - t0:.0f}s")
    ev = json.loads((ROOT / "data/research/defensive_scheme_evidence.json").read_text())
    obs = ev["teams"]["2025-26"]
    alias = {"BKN": "BKN", "BRK": "BKN", "GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS",
             "PHO": "PHX"}
    teams = []
    for abbrev, rows in by_team.items():
        key = alias.get(abbrev, abbrev)
        o = obs.get(key)
        if not o or o.get("bbi_proxy", {}).get("ball_screen_aggression_index") is None:
            continue
        p_agg, p_sw, mix = proxies(rows)
        teams.append({"team": key, "engine_abbrev": abbrev, "coach": o.get("coach"), "screens": len(rows),
                      "agg_obs": o["bbi_proxy"]["ball_screen_aggression_index"],
                      "gonc_obs": (o.get("nba_assignment_proxy") or {}).get("G_defending_C_partial_possession_pct"),
                      "agg_engine": p_agg, "sw_engine": p_sw, "mix_personnel": mix})
    a0, b0, r0 = line([t["agg_engine"] for t in teams], [t["agg_obs"] for t in teams])
    ts = [t for t in teams if t["gonc_obs"] is not None]
    a1, b1, r1 = line([t["sw_engine"] for t in ts], [t["gonc_obs"] for t in ts])
    res = {"screens": len(trace), "teams": len(teams), "reliability": RELIABILITY,
           "aggression_line": {"intercept": round(a0, 3), "points_per_unit": round(b0, 3), "corr": round(r0, 3)},
           "switch_line": {"intercept": round(a1, 3), "points_per_unit": round(b1, 3), "corr": round(r1, 3)}}
    staffs = json.loads((ROOT / "data/research/staffs_2025_26.json").read_text())["teams"]
    table = {}
    for t in teams:
        rows = by_team[t["engine_abbrev"]]
        t["agg_resid"] = t["agg_obs"] - (a0 + b0 * t["agg_engine"])
        t_agg = 0.0
        if b0 > 0:
            target = min(.97, max(.03, t["agg_engine"] + RELIABILITY["aggression"] * t["agg_resid"] / b0))
            t_agg = solve(rows, target, 0)
        t_sw = 0.0
        if t["gonc_obs"] is not None and b1 > 0:
            t["sw_resid"] = t["gonc_obs"] - (a1 + b1 * t["sw_engine"])
            target = min(.95, max(.02, t["sw_engine"] + RELIABILITY["switching"] * t["sw_resid"] / b1))
            t_sw = solve(rows, target, 1)
        t["tilt"] = {"aggression": round(t_agg, 3), "switching": round(t_sw, 3)}
        t["mix_scheme"] = proxies(rows, t_agg, t_sw)[2]
        coaches = [c["name"] for c in (staffs.get(t["team"]) or {}).get("head_coaches", [])] or [t["coach"]]
        for c in coaches:
            if c:
                table[norm(c)] = {"coach": c, "team": t["team"], "aggression": round(t_agg, 3),
                                  "switching": round(t_sw, 3)}
    res["by_team"] = sorted(teams, key=lambda t: -t["tilt"]["aggression"])
    league = defaultdict(float)
    for t in teams:
        for k, v in t["mix_scheme"].items():
            league[k] += v * t["screens"]
    res["league_mix_scheme"] = {k: round(v / sum(t["screens"] for t in teams), 4) for k, v in league.items()}
    print(json.dumps({k: v for k, v in res.items() if k != "by_team"}, indent=1))
    for t in res["by_team"]:
        print(f"  {t['team']:4s} {str(t['coach'])[:18]:18s} agg obs {t['agg_obs']:6.1f} engine {t['agg_engine']:.3f} "
              f"resid {t['agg_resid']:+5.1f} | G-on-C {t['gonc_obs'] or 0:4.1f} engine {t['sw_engine']:.3f} | "
              f"tilt {t['tilt']['aggression']:+.2f} {t['tilt']['switching']:+.2f} | mix {t['mix_scheme']}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scheme_fit.json").write_text(json.dumps(res, indent=1))
    if args.write:
        lines = ['"""Each 2025-26 head coach\'s ball-screen scheme on top of his personnel (S2-SCHEMES), as log-odds tilts on the',
                 'Stage 2 coverage call: aggression (drop less, trap more) from Basketball Index coverage aggression, switching',
                 "from guards' assigned time on centers (NBA matchups). Leftover after personnel (spread-matched scale) x",
                 "reliability (.53 aggression, .26 switching), fitted on the engine's own replayed 2025-26 screens.",
                 'Written by scripts/research/s2_scheme_fit.py --write (2026-11-24); stage2.schemes reads it."""',
                 "", "COACHES = {"]
        for key, row in sorted(table.items()):
            lines.append(f"    {key!r}: {{\"coach\": {row['coach']!r}, \"team\": {row['team']!r}, "
                         f"\"aggression\": {row['aggression']!r}, \"switching\": {row['switching']!r}}},")
        lines.append("}")
        PREFS.write_text("\n".join(lines) + "\n")
        print(f"wrote {PREFS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
