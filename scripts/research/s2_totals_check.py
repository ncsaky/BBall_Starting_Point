#!/usr/bin/env python3
"""Stage 2 game totals: team pace and scoring level against real 2025-26 and the betting market's totals.

Replays every 2025-26 regular-season game with real availability and minutes (the betting test's mode) on one engine,
N runs a game, and stores per-game numbers (expected total and its spread, possessions, free throws, overtime, the
two teams' points) next to the market total and the real box score (real possessions = FGA - ORB + TOV + .44 FTA).

    PYTHONPATH=src .venv/bin/python scripts/research/s2_totals_check.py collect --engine stage2 --runs 8
    PYTHONPATH=src .venv/bin/python scripts/research/s2_totals_check.py report [--engines stage2,current]

`collect` writes output/stage2/totals_games_<engine>[_<tag>].json; `report` reads those files and prints (and saves
output/stage2/totals_report.json) the decomposition of the total miss: league level, the spread of expected totals
against the market's, team pace and scoring against real, overtime, free throws, and the run-to-run noise share.
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
OUT = ROOT / "output" / "stage2"


def _int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def real_team_box(game: dict) -> dict[str, dict]:
    """team espn id -> real points, possessions estimate, FTA, minutes (from the team box)."""
    out = {}
    mins = defaultdict(float)
    for p in game.get("players", []):
        mins[p.get("team_abbrev")] += float(p.get("minutes") or 0)
    for t in game.get("teams", []):
        s = t.get("stats", {})
        fgm, fga = (s.get("fieldGoalsMade-fieldGoalsAttempted") or "0-0").split("-")
        ftm, fta = (s.get("freeThrowsMade-freeThrowsAttempted") or "0-0").split("-")
        tm3, ta3 = (s.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted") or "0-0").split("-")
        orb = _int(s.get("offensiveRebounds"))
        tov = _int(s.get("totalTurnovers") or s.get("turnovers"))
        poss = _int(fga) - orb + tov + .44 * _int(fta)
        out[str(t.get("team_id"))] = {"poss": poss, "fga": _int(fga), "fta": _int(fta), "fg3a": _int(ta3), "orb": orb,
                                      "tov": tov, "minutes": mins.get(t.get("team_abbrev"), 0.0)}
    return out


def collect(engine: str, runs: int, seed: int, limit: int | None, tag: str) -> Path:
    from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    if limit:
        ids = ids[:: max(1, len(ids) // limit)][:limit]
    box = {str(g.get("game_id")): g for g in ctx["boxscores"]}
    rows = []
    t0 = time.time()
    for n, gid in enumerate(ids):
        totals, homes, aways, poss, ftas, ots, fga = [], [], [], [], [], [], []
        res = None
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=seed + r, engine=engine)
            totals.append(res.home_score + res.away_score)
            homes.append(res.home_score)
            aways.append(res.away_score)
            poss.append(float(res.possessions or 0.0))
            ftas.append(sum(int(tl.get("fta") or 0) for tl in res.team_lines))
            fga.append(sum(int(tl.get("fga") or 0) for tl in res.team_lines))
            home_min = sum(float(ln.get("minutes") or 0) for ln in res.player_lines if ln.get("team_id") == res.home_team_id)
            ots.append(1 if home_min > 242.5 else 0)
        odds = ctx["odds"].get(str(gid)) or {}
        g = box.get(str(gid)) or {}
        real = real_team_box(g) if g else {}
        game = next((s for s in ctx["schedule"] if str(s.get("externalGameId")) == str(gid)), {})
        rows.append({
            "game_id": str(gid), "date": game.get("gameDate") or g.get("date"),
            "home": res.home_team_id, "away": res.away_team_id,
            "home_espn": str(game.get("homeTeamId") or g.get("home_team_id")), "away_espn": str(game.get("awayTeamId") or g.get("away_team_id")),
            "sim_total": statistics.fmean(totals), "sim_total_sd": statistics.pstdev(totals) if runs > 1 else None,
            "sim_margin_sd": statistics.pstdev([h - a for h, a in zip(homes, aways)]) if runs > 1 else None,
            "sim_home": statistics.fmean(homes), "sim_away": statistics.fmean(aways), "sim_poss": statistics.fmean(poss),
            "sim_fta": statistics.fmean(ftas), "sim_fga": statistics.fmean(fga), "sim_ot": statistics.fmean(ots),
            "market_total": (odds.get("total") or {}).get("line"),
            "market_spread": -(odds.get("spread") or {}).get("home_line") if (odds.get("spread") or {}).get("home_line") is not None else None,
            "real_home": g.get("home_score"), "real_away": g.get("away_score"), "real_box": real,
        })
        if (n + 1) % 200 == 0:
            print(f"  {n + 1}/{len(ids)} games, {time.time() - t0:.0f}s", flush=True)
    el = time.time() - t0
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"totals_games_{engine}{'_' + tag if tag else ''}.json"
    path.write_text(json.dumps({"engine": engine, "runs": runs, "seed": seed, "seconds": round(el, 1),
                                "per_game_ms": round(1000 * el / max(1, runs * len(ids)), 2), "games": rows}))
    print(f"{engine}: {len(ids)} games x {runs} runs in {el:.0f}s -> {path}")
    return path


def _corr(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")


def _slope(x, y):
    """slope of x on y (how much x moves per unit of y)."""
    mx, my = statistics.fmean(x), statistics.fmean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / sum((b - my) ** 2 for b in y)


def analyse(data: dict, runs_target: int = 20) -> dict:
    rows = data["games"]
    runs = data["runs"]
    mk = [r for r in rows if r["market_total"] is not None]
    sim = [r["sim_total"] for r in mk]
    mkt = [float(r["market_total"]) for r in mk]
    err = [a - b for a, b in zip(sim, mkt)]
    sd_game = statistics.fmean([r["sim_total_sd"] for r in rows if r["sim_total_sd"] is not None]) if runs > 1 else None
    # Noise in the mean of `runs` runs; remove it to get the systematic part, then add back the 20-run noise.
    noise_var = (sd_game ** 2) * runs / max(1, runs - 1) / runs if sd_game else 0.0
    bias = statistics.fmean(err)
    var_err = statistics.pvariance(err)
    sys_var = max(0.0, var_err - noise_var)
    noise20 = (sd_game ** 2) * runs / max(1, runs - 1) / runs_target if sd_game else 0.0
    # Mean absolute error of a normal with this bias and sd.
    def mae(mu, s):
        if s <= 0:
            return abs(mu)
        z = mu / s
        return s * math.sqrt(2 / math.pi) * math.exp(-z * z / 2) + mu * (1 - 2 * _phi(-z))
    out = {
        "engine": data["engine"], "runs": runs, "games_with_market": len(mk), "per_game_ms": data.get("per_game_ms"),
        "mean_sim_total": round(statistics.fmean(sim), 2), "mean_market_total": round(statistics.fmean(mkt), 2),
        "mean_real_total": round(statistics.fmean([r["real_home"] + r["real_away"] for r in mk if r["real_home"]]), 2),
        "bias_vs_market": round(bias, 2),
        "mae_vs_market_at_these_runs": round(statistics.fmean(abs(e) for e in err), 3),
        "sd_expected_total_sim": round(math.sqrt(max(0.0, statistics.pvariance(sim) - noise_var)), 2),
        "sd_market_total": round(statistics.pstdev(mkt), 2),
        "corr_with_market": round(_corr(sim, mkt), 3),
        "slope_sim_on_market": round(_slope(sim, mkt), 3),
        "systematic_sd_of_error": round(math.sqrt(sys_var), 2),
        "game_to_game_total_sd_in_sim": round(sd_game, 2) if sd_game else None,
        "predicted_mae_at_20_runs": round(mae(bias, math.sqrt(sys_var + noise20)), 3),
        "predicted_mae_at_20_runs_without_bias": round(mae(0.0, math.sqrt(sys_var + noise20)), 3),
        "noise_only_mae_at_20_runs": round(mae(0.0, math.sqrt(noise20)), 3),
        "sim_possessions": round(statistics.fmean(r["sim_poss"] for r in rows), 2),
        "sim_fta_per_game": round(statistics.fmean(r["sim_fta"] for r in rows), 2),
        "sim_ot_rate": round(statistics.fmean(r["sim_ot"] for r in rows), 4),
    }
    # Real possessions and real overtime rate.
    rp, rot, rfta, rtot = [], [], [], []
    for r in rows:
        rb = r["real_box"]
        if len(rb) == 2:
            ps = [v["poss"] for v in rb.values()]
            rp.append(sum(ps) / 2)
            rfta.append(sum(v["fta"] for v in rb.values()))
            rot.append(1 if max(v["minutes"] for v in rb.values()) > 245 else 0)
    out["real_possessions"] = round(statistics.fmean(rp), 2) if rp else None
    out["real_fta_per_game"] = round(statistics.fmean(rfta), 2) if rfta else None
    out["real_ot_rate"] = round(statistics.fmean(rot), 4) if rot else None
    # Team level: points for / against per game and possessions, sim vs real; and the team's average total error.
    tf, ta, tp, rf, ra, rpp, terr = (defaultdict(list) for _ in range(7))
    for r in rows:
        h, a = r["home"], r["away"]
        tf[h].append(r["sim_home"]); ta[h].append(r["sim_away"]); tf[a].append(r["sim_away"]); ta[a].append(r["sim_home"])
        tp[h].append(r["sim_poss"]); tp[a].append(r["sim_poss"])
        if r["real_home"]:
            rf[h].append(r["real_home"]); ra[h].append(r["real_away"]); rf[a].append(r["real_away"]); ra[a].append(r["real_home"])
            rb = r["real_box"]
            if len(rb) == 2:
                p = sum(v["poss"] for v in rb.values()) / 2
                rpp[h].append(p); rpp[a].append(p)
        if r["market_total"] is not None:
            e = r["sim_total"] - float(r["market_total"])
            terr[h].append(e); terr[a].append(e)
    teams = sorted(tf)
    def stat(sd, rd, name):
        s = [statistics.fmean(sd[t]) for t in teams]
        q = [statistics.fmean(rd[t]) for t in teams]
        return {f"{name}_sim_mean": round(statistics.fmean(s), 2), f"{name}_real_mean": round(statistics.fmean(q), 2),
                f"{name}_sim_sd": round(statistics.pstdev(s), 2), f"{name}_real_sd": round(statistics.pstdev(q), 2),
                f"{name}_corr": round(_corr(s, q), 3),
                f"{name}_rmse": round(math.sqrt(statistics.fmean((a - b - (statistics.fmean(s) - statistics.fmean(q))) ** 2
                                                                 for a, b in zip(s, q))), 2)}
    out["team"] = {**stat(tf, rf, "points_for"), **stat(ta, ra, "points_against"), **stat(tp, rpp, "possessions")}
    # Offensive / defensive rating per 100.
    so = {t: 100 * statistics.fmean(tf[t]) / statistics.fmean(tp[t]) for t in teams}
    sdf = {t: 100 * statistics.fmean(ta[t]) / statistics.fmean(tp[t]) for t in teams}
    ro = {t: 100 * statistics.fmean(rf[t]) / statistics.fmean(rpp[t]) for t in teams if rpp[t]}
    rd = {t: 100 * statistics.fmean(ra[t]) / statistics.fmean(rpp[t]) for t in teams if rpp[t]}
    tt = [t for t in teams if t in ro]
    out["team"].update({
        "off_rating_corr": round(_corr([so[t] for t in tt], [ro[t] for t in tt]), 3),
        "off_rating_sim_sd": round(statistics.pstdev([so[t] for t in tt]), 2), "off_rating_real_sd": round(statistics.pstdev([ro[t] for t in tt]), 2),
        "def_rating_corr": round(_corr([sdf[t] for t in tt], [rd[t] for t in tt]), 3),
        "def_rating_sim_sd": round(statistics.pstdev([sdf[t] for t in tt]), 2), "def_rating_real_sd": round(statistics.pstdev([rd[t] for t in tt]), 2),
        "off_rating_sim_mean": round(statistics.fmean(so.values()), 2), "off_rating_real_mean": round(statistics.fmean(ro.values()), 2),
        "team_total_error_sd": round(statistics.pstdev([statistics.fmean(terr[t]) for t in teams if terr[t]]), 2),
    })
    out["team_rows"] = {t: {"sim_pf": round(statistics.fmean(tf[t]), 1), "real_pf": round(statistics.fmean(rf[t]), 1) if rf[t] else None,
                            "sim_pa": round(statistics.fmean(ta[t]), 1), "real_pa": round(statistics.fmean(ra[t]), 1) if ra[t] else None,
                            "sim_poss": round(statistics.fmean(tp[t]), 1), "real_poss": round(statistics.fmean(rpp[t]), 1) if rpp[t] else None,
                            "total_err": round(statistics.fmean(terr[t]), 2) if terr[t] else None} for t in teams}
    return out


def _phi(x: float) -> float:
    return .5 * (1 + math.erf(x / math.sqrt(2)))


def report(files: list[Path]) -> None:
    res = {}
    for f in files:
        data = json.loads(f.read_text())
        a = analyse(data)
        res[f.stem.replace("totals_games_", "")] = a
        print(f"\n== {f.stem} ==")
        for k, v in a.items():
            if k not in ("team_rows",):
                print(f"  {k}: {v}")
    (OUT / "totals_report.json").write_text(json.dumps(res, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--engine", default="stage2")
    c.add_argument("--runs", type=int, default=8)
    c.add_argument("--seed", type=int, default=1001)
    c.add_argument("--limit", type=int, default=None)
    c.add_argument("--tag", default="")
    r = sub.add_parser("report")
    r.add_argument("files", nargs="*")
    args, rest = ap.parse_known_args()
    for a in rest:
        # loop.KEY=V: a Stage 2 LOOP override for the run (research variants, e.g. loop.finishes=0).
        key, value = a.split("=", 1)
        table, name = key.split(".", 1)
        if table != "loop":
            ap.error(f"unknown override {a}")
        from nba_gm_data.stage2 import game as G
        G.LOOP[name] = float(value)
    if args.cmd == "collect":
        collect(args.engine, args.runs, args.seed, args.limit, args.tag)
    else:
        files = [Path(f) for f in args.files] or sorted(OUT.glob("totals_games_*.json"))
        report(files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
