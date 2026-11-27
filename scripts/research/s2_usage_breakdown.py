#!/usr/bin/env python3
"""Who takes the shots (S2-USAGE): each player's scoring broken down layer by layer, engine against real 2025-26.

Replays every 2025-26 regular-season game (the betting test's replay mode: real availability and minutes) RUNS times per
engine and adds up, per player: minutes, the box score, and for Stage 2 every shot try by kind (stage2.game.SHOT_TRACE:
tries, attempts, makes, shooting-foul trips, their free throws, and-ones). Then compares, per 36 minutes:

- usage (FGA + .44 FTA + TOV), points, FGA, threes, free throws, turnovers, assists (real: the calibration targets file,
  data/calibration/nba_2025_26_targets.json, ESPN season totals);
- shot mix by zone and action against Basketball Index 2025-26 (data/research/bbi/values_recent.json.gz, main checkout):
  rim attempts, unassisted rim attempts, midrange attempts, threes, pull-up threes, cuts, roll-man possessions, drives,
  putback points, free throws, assists; per-75 values put on a per-36 footing with each player's own ratio of real box
  points per 36 to Basketball Index points per 75;
- make rates by zone (rim, other twos, threes) and free-throw percentage.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_usage_breakdown.py --runs 4 --out output/s2usage/breakdown.json

Research only: no rating, no engine number is changed here.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
BBI_FILE = "data/research/bbi/values_recent.json.gz"
BOX = ("points", "fga", "fgm", "fg3a", "fg3m", "fta", "ftm", "assists", "turnovers", "rebounds", "offensive_rebounds",
       "rim_attempts")
BBI_METRICS = {
    "pts75": "Points Per 75 Possessions", "rim75": "Rim Shot Attempts Per 75 Possessions",
    "rim_unast75": "Unassisted Rim Shot Attempts Per 75 Possessions", "mid75": "Midrange FGA Per 75",
    "three75": "3PT FGA Per 75 Possessions", "pull3_75": "3PT Pull Up FGA Per 75", "pullmid75": "Midrange Pull Up FGA Per 75",
    "cuts75": "Cuts Per 75 Possessions", "roll75": "Roll Man Poss Per 75 Possessions", "drives75": "Drives Per 75 Possessions",
    "putpts75": "Stable Putback Points Per 75", "putppp": "Stable Putbacks PPP", "fta75": "Stable FTA Per 75",
    "ast75": "Assists Per 75 Possessions", "rim_fg": "Rim FG%", "fg3": "3PT %", "ft": "Free Throw Percentage",
    "offscreen75": "Off-Ball Screen Possessions Per 75 Possessions", "paint75": "Paint Touches Per 75 Possessions",
    "oreb75": "Offensive Rebounds Per 75 Possessions", "self_oreb75": "Stable Self Offensive Rebounds Per 75",
    "usage": "Usage Rate", "true_usage": "Stable True Usage%", "spot_up": "Spot Up%", "trans_freq": "Transition Frequency Impact",
    "trans_ppp": "Stable Transition PPP", "cut_ppp": "Stable Cut PPP", "roll_ppp": "Stable P&R Roll Man PPP",
}


def bbi_table(root: Path) -> dict[str, dict[str, float]]:
    path = root / BBI_FILE
    if not path.exists():   # worktrees: the capture lives in the main checkout
        for parent in root.parents:
            if (parent / BBI_FILE).exists():
                path = parent / BBI_FILE
                break
    table = json.load(gzip.open(path))["table"]
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for key, metric in BBI_METRICS.items():
        for pid, row in (table.get(f"2025-26|{metric}") or {}).items():
            if pid.startswith("player_") and row and row[0] is not None:
                out[pid][key] = float(row[0])
    return dict(out)


def replay(ctx, engine: str, runs: int, seed: int) -> tuple[dict, dict]:
    from nba_gm_data.sim import sim_game_with_context, validation_game_ids
    from nba_gm_data.stage2 import game as G
    G.SHOT_TRACE = {} if engine == "stage2" else None
    box = {str(g["game_id"]) for g in ctx["boxscores"]}
    tot: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for gid in validation_game_ids(ctx, None, False):
        if gid not in box:
            continue
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=seed + r, engine=engine)
            for ln in res.player_lines:
                a = tot[ln["player_id"]]
                a["minutes"] += float(ln.get("minutes") or 0) / runs
                a["games"] += 1.0 / runs
                for k in BOX:
                    a[k] += float(ln.get(k) or 0) / runs
    trace = G.SHOT_TRACE or {}
    G.SHOT_TRACE = None
    shots = {pid: [[v / runs for v in row] for row in rows] for pid, rows in trace.items()}
    return {k: dict(v) for k, v in tot.items()}, shots


def per36(a: dict, key: str) -> float:
    return 36.0 * a.get(key, 0.0) / max(1.0, a.get("minutes", 0.0))


def corr(x, y):
    if len(x) < 3:
        return None
    mx, my = statistics.fmean(x), statistics.fmean(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return round(sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy), 3) if vx > 0 and vy > 0 else None


def build_rows(root: Path, s2: dict, s2shots: dict, cur: dict, min_minutes: float) -> dict[str, dict]:
    from nba_gm_data.stage2.cards import KINDS, KIND_INDEX, card_for, means_for
    from nba_gm_data.stage2.game_contexts import league_flat_inputs
    targets = json.loads((root / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
    bbi = bbi_table(root)
    flats = league_flat_inputs(root)
    means = means_for(root)
    rows = {}
    for pid, t in targets.items():
        a = s2.get(pid)
        if a is None or a.get("minutes", 0) < min_minutes or float(t.get("minutes") or 0) < min_minutes:
            continue
        m = float(t["minutes"])
        fga = t["fga_per36"]
        fgm = t["fg_pct"] * fga
        f3a = t["fg3a_per36"]
        f3m = 36.0 * float(t.get("fg3m") or 0) / m
        pts = t["points_per36"]
        ftm = max(0.0, pts - 2 * fgm - f3m)
        real = {"pts": pts, "fga": fga, "fgm": fgm, "fg3a": f3a, "fg3m": f3m, "fta": t["fta_per36"], "ftm": ftm,
                "ast": t["assists_per36"], "tov": t["turnovers_per36"], "reb": t["rebounds_per36"],
                "usage": fga + .44 * t["fta_per36"] + t["turnovers_per36"]}
        b = bbi.get(pid, {})
        scale = pts / b["pts75"] if b.get("pts75") else None   # per-75 -> per-36 for this player
        if scale:
            for k in ("rim75", "rim_unast75", "mid75", "three75", "pull3_75", "pullmid75", "cuts75", "roll75",
                      "drives75", "putpts75", "fta75", "ast75", "offscreen75", "paint75", "oreb75", "self_oreb75"):
                if k in b:
                    real["bbi_" + k[:-2]] = b[k] * scale
        for k in ("rim_fg", "fg3", "ft", "putppp", "usage", "true_usage", "spot_up", "trans_freq", "trans_ppp",
                  "cut_ppp", "roll_ppp"):
            if k in b:
                real["bbi_" + k] = b[k]
        eng = {"pts": per36(a, "points"), "fga": per36(a, "fga"), "fgm": per36(a, "fgm"), "fg3a": per36(a, "fg3a"),
               "fg3m": per36(a, "fg3m"), "fta": per36(a, "fta"), "ftm": per36(a, "ftm"), "ast": per36(a, "assists"),
               "tov": per36(a, "turnovers"), "reb": per36(a, "rebounds"), "oreb": per36(a, "offensive_rebounds")}
        eng["usage"] = eng["fga"] + .44 * eng["fta"] + eng["tov"]
        sh = s2shots.get(pid)
        if sh:
            f = 36.0 / a["minutes"]
            by = {k[0]: [v * f for v in sh[KIND_INDEX[k[0]]]] for k in KINDS}
            eng["kinds"] = {k: [round(v, 3) for v in vals] for k, vals in by.items()}
            rim_k = ("rim_drive", "rim_finish", "putback", "trans_rim")
            eng["rim_fga"] = sum(by[k][1] for k in rim_k)
            eng["rim_fgm"] = sum(by[k][2] for k in rim_k)
            eng["rim_unast_fga"] = by["rim_drive"][1]
            eng["mid_fga"] = sum(by[k][1] for k in ("floater", "hook", "short_finish", "short_jumper", "mid_catch", "mid_pull"))
            eng["mid_fgm"] = sum(by[k][2] for k in ("floater", "hook", "short_finish", "short_jumper", "mid_catch", "mid_pull"))
            eng["pull3_fga"] = by["three_pull"][1]
            eng["pullmid_fga"] = by["mid_pull"][1]
            eng["putback_pts"] = 2 * by["putback"][2] + by["putback"][4] * .7
            eng["putback_tries"] = by["putback"][0]
            eng["trans_tries"] = by["trans_rim"][0] + by["trans_three"][0]
            eng["finish_tries"] = by["rim_finish"][0]
            eng["drive_tries"] = by["rim_drive"][0] + by["floater"][0]
            eng["post_tries"] = by["hook"][0]
            eng["catch_tries"] = sum(by[k][0] for k in ("mid_catch", "three_corner", "three_catch"))
            eng["pull_tries"] = sum(by[k][0] for k in ("short_jumper", "mid_pull", "three_pull"))
            eng["shot_ft"] = sum(by[k][4] for k in by)
        c = cur.get(pid)
        today = None
        if c and c.get("minutes", 0) > 0:
            today = {"pts": per36(c, "points"), "fga": per36(c, "fga"), "fg3a": per36(c, "fg3a"), "fta": per36(c, "fta"),
                     "ast": per36(c, "assists"), "fg3m": per36(c, "fg3m")}
        flat = flats.get(pid)
        card = None
        if flat is not None:
            cd = card_for(pid, pid, flat, means)
            card = {"usage_w": round(cd.usage, 4), "T08": flat.get("T08"), "T09": flat.get("T09"),
                    "T11.roll": flat.get("T11.roll"), "T11.slip": flat.get("T11.slip"), "T17.transition": flat.get("T17.transition"),
                    "T01.shoot": flat.get("T01.shoot"), "T01.drive": flat.get("T01.drive"), "T01.post": flat.get("T01.post"),
                    "T01.pass": flat.get("T01.pass"), "T02": [round(flat.get(f"T02.{r}", 0), 3) for r in ("rim", "short_paint", "midrange", "three")],
                    "T03.pull_up": flat.get("T03.pull_up"), "T12": flat.get("T12"), "T05": flat.get("T05"),
                    "make_rim_finish": round(1 / (1 + math.exp(-cd.make_logit[KIND_INDEX["rim_finish"]])), 3),
                    "make_rim_drive": round(1 / (1 + math.exp(-cd.make_logit[KIND_INDEX["rim_drive"]])), 3),
                    "make_three_catch": round(1 / (1 + math.exp(-cd.make_logit[KIND_INDEX["three_catch"]])), 3)}
        rows[pid] = {"name": t.get("name"), "minutes": round(m), "real": {k: round(v, 3) for k, v in real.items()},
                     "stage2": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in eng.items()},
                     "today": {k: round(v, 3) for k, v in today.items()} if today else None, "inputs": card}
    return rows


def summarize(rows: dict[str, dict]) -> dict:
    """Minutes-weighted league summary and per-layer misses (engine minus real, per 36), with correlations."""
    def stat(get_e, get_r, who=None):
        pairs = []
        for pid, r in rows.items():
            e, x = get_e(r), get_r(r)
            if e is None or x is None:
                continue
            pairs.append((e, x, r["minutes"]))
        if not pairs:
            return None
        w = sum(p[2] for p in pairs)
        return {"n": len(pairs), "engine": round(sum(p[0] * p[2] for p in pairs) / w, 3),
                "real": round(sum(p[1] * p[2] for p in pairs) / w, 3),
                "mae": round(sum(abs(p[0] - p[1]) * p[2] for p in pairs) / w, 3),
                "corr": corr([p[0] for p in pairs], [p[1] for p in pairs])}

    S = lambda k: (lambda r: r["stage2"].get(k))  # noqa: E731
    R = lambda k: (lambda r: r["real"].get(k))    # noqa: E731
    T = lambda k: (lambda r: (r["today"] or {}).get(k))  # noqa: E731
    out = {}
    for k in ("usage", "pts", "fga", "fg3a", "fta", "ast", "tov", "reb"):
        out[k] = {"stage2": stat(S(k), R(k)), "today": stat(T(k), R(k)) if k in ("pts", "fga", "fg3a", "fta", "ast") else None}
    out["rim_fga_vs_bbi"] = stat(S("rim_fga"), R("bbi_rim"))
    out["rim_unassisted_vs_bbi"] = stat(S("rim_unast_fga"), R("bbi_rim_unast"))
    out["assisted_rim_vs_bbi"] = stat(lambda r: (r["stage2"].get("rim_fga") or 0) - (r["stage2"].get("rim_unast_fga") or 0),
                                      lambda r: (r["real"].get("bbi_rim") - r["real"].get("bbi_rim_unast"))
                                      if "bbi_rim" in r["real"] and "bbi_rim_unast" in r["real"] else None)
    out["mid_fga_vs_bbi"] = stat(S("mid_fga"), R("bbi_mid"))
    out["three_vs_bbi"] = stat(S("fg3a"), R("bbi_three"))
    out["pull3_vs_bbi"] = stat(S("pull3_fga"), R("bbi_pull3_"))
    out["putback_pts_vs_bbi"] = stat(S("putback_pts"), R("bbi_putpts"))
    out["finish_tries_vs_cuts_plus_rolls"] = stat(S("finish_tries"), lambda r: (r["real"].get("bbi_cuts") or 0) + (r["real"].get("bbi_roll") or 0)
                                                  if "bbi_cuts" in r["real"] else None)
    out["drive_tries_vs_drives"] = stat(S("drive_tries"), R("bbi_drives"))
    out["fg_rim_vs_bbi"] = stat(lambda r: (r["stage2"].get("rim_fgm") or 0) / r["stage2"]["rim_fga"] if r["stage2"].get("rim_fga", 0) > .5 else None,
                                lambda r: r["real"].get("bbi_rim_fg") / 100 if r["real"].get("bbi_rim_fg") else None)
    out["fg3_pct"] = stat(lambda r: r["stage2"]["fg3m"] / r["stage2"]["fg3a"] if r["stage2"]["fg3a"] > 1 else None,
                          lambda r: r["real"]["fg3m"] / r["real"]["fg3a"] if r["real"]["fg3a"] > 1 else None)
    out["fg_pct"] = stat(lambda r: r["stage2"]["fgm"] / r["stage2"]["fga"] if r["stage2"]["fga"] > 1 else None,
                         lambda r: r["real"]["fgm"] / r["real"]["fga"] if r["real"]["fga"] > 1 else None)
    return out


def decompose(r: dict) -> dict:
    """Engine minus real points per 36, split into: two-point attempts, two-point make rate, three attempts, three make
    rate, free throws."""
    e, x = r["stage2"], r["real"]
    e2a, x2a = e["fga"] - e["fg3a"], x["fga"] - x["fg3a"]
    e2m, x2m = e["fgm"] - e["fg3m"], x["fgm"] - x["fg3m"]
    e2p = e2m / e2a if e2a > 0 else 0
    x2p = x2m / x2a if x2a > 0 else 0
    e3p = e["fg3m"] / e["fg3a"] if e["fg3a"] > 0 else 0
    x3p = x["fg3m"] / x["fg3a"] if x["fg3a"] > 0 else 0
    return {"pts": round(e["pts"] - x["pts"], 2), "two_volume": round(2 * (e2a - x2a) * x2p, 2),
            "two_pct": round(2 * e2a * (e2p - x2p), 2), "three_volume": round(3 * (e["fg3a"] - x["fg3a"]) * x3p, 2),
            "three_pct": round(3 * e["fg3a"] * (e3p - x3p), 2), "ft": round(e["ftm"] - x["ftm"], 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--engines", default="stage2,current")
    ap.add_argument("--min-minutes", type=float, default=500)
    ap.add_argument("--out", default="output/s2usage/breakdown.json")
    args, rest = ap.parse_known_args()
    from nba_gm_data.stage2 import cards as C
    from nba_gm_data.stage2 import game as G
    for a in rest:
        key, value = a.split("=", 1)
        mod, name = key.split(".", 1)
        {"LOOP": G.LOOP, "MENU": C.MENU, "ASSISTS": C.ASSISTS, "USAGE": C.USAGE}[mod][name] = float(value)
    from nba_gm_data.sim import load_sim_context
    ctx = load_sim_context(ROOT)
    t0 = time.time()
    s2, shots = replay(ctx, "stage2", args.runs, args.seed)
    cur = replay(ctx, "current", args.runs, args.seed)[0] if "current" in args.engines else {}
    rows = build_rows(ROOT, s2, shots, cur, args.min_minutes)
    for r in rows.values():
        r["decomp"] = decompose(r)
    summary = summarize(rows)
    print(json.dumps(summary, indent=1))
    print("seconds", round(time.time() - t0))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
