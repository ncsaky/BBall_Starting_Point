#!/usr/bin/env python3
"""Stage 2 scoring level: replayed and generated games against the same real games (S2-SCHEMES, part 4).

Plays the same 2025-26 regular-season games in both modes, N runs each:
- replay-real-minutes: real availability and real minutes (the betting test);
- sandbox-sim: the game's own rotation (today's minutes model, the injury model),
and compares each team's box (points, possessions, the four factors, free throws, overtime) with the real box of that
very game, so the comparison does not depend on which games were picked.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_level_gap.py --runs 4 [--limit 600] [--tag x] [loop.KEY=V ...]

Writes output/s2schemes/level_gap[_tag].json and prints the decomposition: points per team-game = possessions x points
per possession, and points per possession by shooting (effective FG%), turnovers, offensive rebounds and free throws.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
OUT = ROOT / "output" / "s2schemes"

FIELDS = ("pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "pf", "poss", "ot", "min")


def _apply_overrides(args: list[str]) -> dict:
    from nba_gm_data.stage2 import coach as C, game as G, screens as S
    applied = {}
    for a in args:
        key, value = a.split("=", 1)
        table, name = key.split(".", 1)
        {"loop": G.LOOP, "coach": C.COACH, "screens": S.SCREENS}[table][name] = float(value)
        applied[key] = float(value)
    return applied


def _team_from_lines(team_id: str, lines: list[dict], team_lines: list[dict]) -> dict:
    tl = next((t for t in team_lines if str(t.get("team_id")) == str(team_id)), {})
    g = lambda k: float(tl.get(k) or 0.0)  # noqa: E731
    mins = sum(float(ln.get("minutes") or 0) for ln in lines if str(ln.get("team_id")) == str(team_id))
    out = {"pts": g("points"), "fgm": g("fgm"), "fga": g("fga"), "fg3m": g("fg3m"), "fg3a": g("fg3a"), "ftm": g("ftm"),
           "fta": g("fta"), "orb": g("offensive_rebounds"), "drb": g("defensive_rebounds"), "tov": g("turnovers"),
           "pf": g("personal_fouls"), "min": mins}
    out["poss"] = out["fga"] - out["orb"] + out["tov"] + .44 * out["fta"]
    out["ot"] = 1.0 if mins > 242.5 else 0.0
    return out


def _real_team(game: dict) -> dict[str, dict]:
    from s2_totals_check import _int
    out = {}
    mins = defaultdict(float)
    for p in game.get("players", []):
        mins[p.get("team_abbrev")] += float(p.get("minutes") or 0)
    for t in game.get("teams", []):
        s = t.get("stats", {})
        sp = lambda k: [_int(x) for x in (s.get(k) or "0-0").split("-")]  # noqa: E731
        fgm, fga = sp("fieldGoalsMade-fieldGoalsAttempted")
        ftm, fta = sp("freeThrowsMade-freeThrowsAttempted")
        f3m, f3a = sp("threePointFieldGoalsMade-threePointFieldGoalsAttempted")
        orb = _int(s.get("offensiveRebounds"))
        tov = _int(s.get("totalTurnovers") or s.get("turnovers"))
        m = mins.get(t.get("team_abbrev"), 0.0)
        pts = 2 * fgm + f3m + ftm
        out[str(t.get("team_id"))] = {"pts": pts, "fgm": fgm, "fga": fga, "fg3m": f3m, "fg3a": f3a, "ftm": ftm, "fta": fta,
                                      "orb": orb, "drb": _int(s.get("defensiveRebounds")), "tov": tov,
                                      "pf": _int(s.get("fouls")), "min": m,
                                      "poss": fga - orb + tov + .44 * fta, "ot": 1.0 if m > 245 else 0.0}
    return out


def collect(runs: int, seed: int, limit: int | None, modes: list[str]) -> dict:
    from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    if limit:
        ids = ids[:: max(1, len(ids) // limit)][:limit]
    box = {str(g.get("game_id")): g for g in ctx["boxscores"]}
    sched = {str(s.get("externalGameId")): s for s in ctx["schedule"]}
    rows = []
    t0 = time.time()
    for n, gid in enumerate(ids):
        g = box.get(str(gid))
        if not g:
            continue
        real = _real_team(g)
        game = sched.get(str(gid), {})
        h_espn, a_espn = str(game.get("homeTeamId") or g.get("home_team_id")), str(game.get("awayTeamId") or g.get("away_team_id"))
        if h_espn not in real or a_espn not in real:
            continue
        row = {"game_id": str(gid), "real": {"home": real[h_espn], "away": real[a_espn]}}
        for mode in modes:
            acc = {"home": defaultdict(float), "away": defaultdict(float)}
            for r in range(runs):
                res = sim_game_with_context(ctx, gid, mode=mode, seed=seed + r, engine="stage2")
                for side, tid in (("home", res.home_team_id), ("away", res.away_team_id)):
                    t = _team_from_lines(tid, res.player_lines, res.team_lines)
                    for k, v in t.items():
                        acc[side][k] += v / runs
            row[mode] = {s: dict(v) for s, v in acc.items()}
        rows.append(row)
        if (n + 1) % 200 == 0:
            print(f"  {n + 1}/{len(ids)} games, {time.time() - t0:.0f}s", flush=True)
    return {"runs": runs, "seed": seed, "seconds": round(time.time() - t0, 1), "modes": modes, "games": rows}


def summarise(data: dict) -> dict:
    rows = data["games"]
    out = {}
    for src in ["real", *data["modes"]]:
        tot = defaultdict(float)
        n = 0
        for r in rows:
            for side, other in (("home", "away"), ("away", "home")):
                for k in FIELDS:
                    tot[k] += r[src][side].get(k, 0.0)
                tot["drb_opp"] += r[src][other].get("drb", 0.0)
                n += 1
        m = {k: tot[k] / n for k in (*FIELDS, "drb_opp")}
        poss = m["poss"]
        reg_min = 240.0
        out[src] = {
            "points": round(m["pts"], 2), "possessions": round(poss, 2),
            "pace_per48": round(poss * reg_min / max(1.0, m["min"]) * 1.0, 2),
            "ppp100": round(100 * m["pts"] / poss, 2),
            "efg": round((m["fgm"] + .5 * m["fg3m"]) / m["fga"], 4),
            "tov100": round(100 * m["tov"] / poss, 2), "fta100": round(100 * m["fta"] / poss, 2),
            "ft_pct": round(m["ftm"] / max(1.0, m["fta"]), 4),
            "orb_pct": round(m["orb"] / max(1.0, m["orb"] + m["drb_opp"]), 4),
            "fga100": round(100 * m["fga"] / poss, 2), "fg3a_rate": round(m["fg3a"] / m["fga"], 4),
            "fg3_pct": round(m["fg3m"] / max(1.0, m["fg3a"]), 4),
            "fg2_pct": round((m["fgm"] - m["fg3m"]) / max(1.0, m["fga"] - m["fg3a"]), 4),
            "pf100": round(100 * m["pf"] / poss, 2), "ot_rate": round(m["ot"], 4), "minutes": round(m["min"], 2),
        }
    # Points gap decomposition vs real: possessions part and efficiency part.
    real = out["real"]
    for mode in data["modes"]:
        s = out[mode]
        d_pts = s["points"] - real["points"]
        pace_part = (s["possessions"] - real["possessions"]) * real["ppp100"] / 100
        eff_part = s["possessions"] * (s["ppp100"] - real["ppp100"]) / 100
        s["gap"] = {"points": round(d_pts, 2), "from_possessions": round(pace_part, 2), "from_efficiency": round(eff_part, 2)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="")
    ap.add_argument("--modes", default="replay-real-minutes,sandbox-sim")
    ap.add_argument("--report", default=None, help="summarise an existing file instead of collecting")
    args, rest = ap.parse_known_args()
    if args.report:
        data = json.loads(Path(args.report).read_text())
    else:
        applied = _apply_overrides([a for a in rest if "=" in a])
        data = collect(args.runs, args.seed, args.limit, args.modes.split(","))
        data["overrides"] = applied
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"level_gap{'_' + args.tag if args.tag else ''}.json"
        path.write_text(json.dumps(data))
        print(f"-> {path} ({data['seconds']} s)")
    summ = summarise(data)
    for src, s in summ.items():
        print(f"{src:22s} " + "  ".join(f"{k} {v}" for k, v in s.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
