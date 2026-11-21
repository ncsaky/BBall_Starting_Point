#!/usr/bin/env python3
"""Stage 2 rebound and foul spot-check (S2-REBOUND-FOULS): kernels vs today's engine vs real 2025-26 (and 2022-23).

Light job: no season simulation. Optional --replay N runs N real games through today's engine (replay-real-minutes, the
calibration replay) for its league and team numbers. Writes output/stage2/rebound_foul_check.json and prints markdown.
    nice -n 10 .venv/bin/python scripts/research/s2_rebound_foul_spot_check.py [--refit] [--replay 150]
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

from nba_gm_data.stage2 import foul_check as F  # noqa: E402
from nba_gm_data.stage2 import game_contexts as G  # noqa: E402
from nba_gm_data.stage2 import rebound_check as R  # noqa: E402
from nba_gm_data.stage2.fouls import FITTED as FOUL_FITTED, FoulCoefficients  # noqa: E402
from nba_gm_data.stage2.rebounding import FITTED as REB_FITTED, ReboundCoefficients  # noqa: E402

HELD_OUT_SEASON = "2022-23"


def pct(x, d=1):
    return "" if x is None else f"{100 * x:.{d}f}"


def num(x, d=2):
    return "" if x is None else f"{x:.{d}f}"


def today_replay(games: int, seed: int = 1) -> dict:
    """Today's engine over real games with their real minutes: league fouls/free throws and team offensive-rebound %."""
    from nba_gm_data.calibration_targets import aggregate_from_results
    from nba_gm_data.schema import to_plain
    from nba_gm_data.sim import build_sim_indices, load_sim_context, sim_game_with_context
    context = load_sim_context(ROOT)
    context["indices"] = build_sim_indices(context)
    sched = sorted([g for g in context["schedule"] if str(g.get("phase", "regular")) in ("regular", "None", "")],
                   key=lambda g: str(g.get("externalGameId")))
    step = max(1, len(sched) // games)
    picked = sched[::step][:games]
    t0 = time.time()
    results = [to_plain(sim_game_with_context(context, str(g["externalGameId"]), mode="replay-real-minutes", seed=seed))
               for g in picked]
    agg = aggregate_from_results(results)
    return {"games": len(results), "seconds": round(time.time() - t0, 1), "league_totals": agg["league_totals"],
            "results": results}


def _team_orb_from_results(results: list[dict]) -> dict[str, float]:
    """team abbreviation -> offensive-rebound % over the replayed games (team lines: own ORB over own ORB + opp DRB)."""
    team = defaultdict(lambda: [0.0, 0.0])
    for r in results:
        lines = r.get("team_lines") or []
        if len(lines) != 2:
            continue
        for mine, opp in ((lines[0], lines[1]), (lines[1], lines[0])):
            name = str(mine.get("team_abbrev") or mine.get("team_id")).upper()
            team[name][0] += float(mine.get("offensive_rebounds") or 0)
            team[name][1] += float(mine.get("offensive_rebounds") or 0) + float(opp.get("defensive_rebounds") or 0)
    return {k: v[0] / v[1] for k, v in team.items() if v[1]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "output/stage2/rebound_foul_check.json"))
    ap.add_argument("--refit", action="store_true", help="re-run both conversion refits (several minutes)")
    ap.add_argument("--replay", type=int, default=0, help="today's engine over N real games for league/team numbers")
    ap.add_argument("--per-direction", type=int, default=20)
    args = ap.parse_args()
    t0 = time.perf_counter()
    out: dict = {}
    reb = R.ReboundSetup(ROOT, per_direction=args.per_direction)
    out["setup"] = {"games": len(reb.games), "contexts": len(reb.contexts), "minutes_without_inputs": round(reb.missing_minutes, 4),
                    "environment": {k: round(v, 4) for k, v in reb.env.items()}}
    built_r = ReboundCoefficients()
    if args.refit:
        keys = tuple(k for k in R.FIT_KEYS if k not in ("k_jump", "k_box_mass", "anchor"))  # pinned (see rebounding.FITTED)
        fit_r, info = R.refit(reb, REB_FITTED, keys=keys, rounds=30, log=lambda m: print(m, flush=True))
        out["rebound_refit_info"] = info
    else:
        fit_r = REB_FITTED
    rot = R.rotation(reb)
    held = R.rotation(reb, 1)
    res_built = R.evaluate(reb, built_r)
    res_fit = R.evaluate(reb, fit_r)
    today_reb = R.today_rebounds_per36(reb)
    k36_built, k36_fit = R.kernel_per36(reb, res_built), R.kernel_per36(reb, res_fit)
    reb_out = {
        "players": len(rot), "held_out_players": len(held),
        "rates": {"built_all": R.score_rates(reb, res_built, rot), "fit_all": R.score_rates(reb, res_fit, rot),
                  "built_held": R.score_rates(reb, res_built, held), "fit_held": R.score_rates(reb, res_fit, held)},
        "per36": {}, "league": {}, "coefficients_built": built_r.as_dict(), "coefficients_fit": fit_r.as_dict(),
    }
    for label, rows in (("all", rot), ("held", held)):
        for key in ("reb", "oreb", "dreb"):
            reb_out["per36"][f"kernel_built_{key}_{label}"] = R.score_per36(reb, {p: v[key] for p, v in k36_built.items()}, rows, reb.real, key)
            reb_out["per36"][f"kernel_fit_{key}_{label}"] = R.score_per36(reb, {p: v[key] for p, v in k36_fit.items()}, rows, reb.real, key)
        reb_out["per36"][f"today_reb_{label}"] = R.score_per36(reb, today_reb, rows, reb.real, "reb")
    reb_out["league"] = {"real_orb_pct": round(reb.env["orb_pct"], 4), "built_orb_pct": round(res_built["league_orb"], 4),
                         "fit_orb_pct": round(res_fit["league_orb"], 4),
                         "fit_orb_by_miss": {k: round(v, 4) for k, v in res_fit["orb_by_miss"].items()},
                         "built_orb_by_miss": {k: round(v, 4) for k, v in res_built["orb_by_miss"].items()}}
    teams = sorted(reb.team_real)
    real_t = [reb.team_real[t] for t in teams]
    for label, res in (("built", res_built), ("fit", res_fit)):
        pred_t = [res["team_orb"].get(t) for t in teams]
        reb_out["league"][f"team_{label}"] = {"corr": round(statistics.correlation(pred_t, real_t), 3),
                                               "rmse": round(statistics.fmean((p - r) ** 2 for p, r in zip(pred_t, real_t)) ** .5, 4),
                                               "pred_sd": round(statistics.pstdev(pred_t), 4)}
    reb_out["league"]["team_real_sd"] = round(statistics.pstdev(real_t), 4)
    reb_out["league"]["team_table"] = {t: (round(res_fit["team_orb"].get(t, 0), 4), round(reb.team_real[t], 4)) for t in teams}
    reb_out["misses_built"] = R.misses(reb, res_built, rot)
    reb_out["misses_fit"] = R.misses(reb, res_fit, rot)
    reb_out["timing_us"] = R.time_kernel(reb, fit_r)

    # Fouls.
    fs = F.FoulSetup(reb, rebound_rates=res_fit)
    built_f = FoulCoefficients()
    if args.refit:
        fit_contexts = reb.contexts[::3]
        fit_f, infos = built_f, []
        for target, spec in (("fta", F.FTA_SPEC), ("pf", F.PF_SPEC), ("fta", F.FTA_SPEC), ("pf", F.PF_SPEC)):
            fit_f, info = F.refit(fs, fit_f, R.rotation(reb, 0), contexts=fit_contexts, spec=spec, target=target,
                                  log=lambda m: print(m, flush=True))
            infos.append(info)
        out["foul_refit_info"] = infos
    else:
        fit_f = FOUL_FITTED
    real_all = F.real_rates(fs, rot)
    real_held = F.real_rates(fs, held)
    f_built = F.evaluate(fs, built_f)
    f_fit = F.evaluate(fs, fit_f)
    f_today = F.today_predictions(ROOT, list(real_all))
    foul_out = {"players": len(real_all), "held_out_players": len(real_held),
                "built_all": F.score(f_built, real_all), "fit_all": F.score(f_fit, real_all), "today_all": F.score(f_today, real_all),
                "built_held": F.score(f_built, real_held), "fit_held": F.score(f_fit, real_held), "today_held": F.score(f_today, real_held),
                "league": {"real": {k: round(reb.env[k], 4) for k in ("fouls_per100", "fta_per100", "ft_rate")},
                           "built": {k: (round(v, 4) if v is not None else None) for k, v in f_built["league"].items()},
                           "fit": {k: (round(v, 4) if v is not None else None) for k, v in f_fit["league"].items()}},
                "coefficients_built": built_f.as_dict(), "coefficients_fit": fit_f.as_dict(),
                "misses_built": F.misses(fs, f_built, real_all), "misses_fit": F.misses(fs, f_fit, real_all),
                "timing_us": F.time_kernel(fs, fit_f)}

    # Held-out season: both engines predict 2022-23 from today's inputs, kernels in neutral lineups.
    season = G.espn_raw_season(ROOT, HELD_OUT_SEASON)
    ho_players = sorted(p for p, r in season.items() if r["minutes"] >= R.MIN_MINUTES and p in reb.profiles)
    pool = sorted(((p, r["minutes"]) for p, r in reb.real.items() if p in reb.profiles), key=lambda x: x[0])
    neutral = reb._annotate(G.neutral_contexts(ho_players, pool, per_player=60), seed=99)
    res_n_fit = R.evaluate(reb, fit_r, neutral)
    res_n_built = R.evaluate(reb, built_r, neutral)
    k36_n_fit, k36_n_built = R.kernel_per36(reb, res_n_fit), R.kernel_per36(reb, res_n_built)
    season_rows = {p: {"minutes": r["minutes"], "oreb": r["oreb"], "dreb": r["dreb"]} for p, r in season.items()}
    ho = {"season": HELD_OUT_SEASON, "players": len(ho_players), "level_matched": True}
    for key in ("reb", "oreb", "dreb"):
        ho[f"kernel_built_{key}"] = R.score_per36(reb, {p: v[key] for p, v in k36_n_built.items()}, ho_players, season_rows, key, match_level=True)
        ho[f"kernel_fit_{key}"] = R.score_per36(reb, {p: v[key] for p, v in k36_n_fit.items()}, ho_players, season_rows, key, match_level=True)
    ho["today_reb"] = R.score_per36(reb, today_reb, ho_players, season_rows, "reb", match_level=True)
    # In-season numbers on the same players for reference (2025-26 lineups vs 2025-26 real).
    fs_n = F.FoulSetup(reb, rebound_rates=res_n_fit, contexts=neutral)
    real_ho = {p: {"fta": r["fta"], "fga": r["fga"], "minutes": r["minutes"], "pf": r["pf"]} for p, r in season.items()
               if p in ho_players and r["fga"] >= F.MIN_FGA}
    ho["fouls_players"] = len(real_ho)
    ho["kernel_fit_fouls"] = F.score(F.evaluate(fs_n, fit_f), real_ho, match_level=True)
    ho["kernel_built_fouls"] = F.score(F.evaluate(fs_n, built_f), real_ho, match_level=True)
    ho["today_fouls"] = F.score(F.today_predictions(ROOT, list(real_ho)), real_ho, match_level=True)
    out["held_out_season"] = ho

    # Position check: the kernel's offensive working spot vs Basketball Index's average offensive-rebound distance.
    from nba_gm_data.bbi_evidence import _recent_values
    table = _recent_values(ROOT)
    dist = table.get(("2025-26", "Average Offensive Rebounding Distance from Rim"), {})
    pairs = [(reb.profiles[p].spot_m, dist[p][0]) for p in rot if p in dist and dist[p][1] >= R.MIN_MINUTES]
    out["position_check"] = {"players": len(pairs), "corr_spot_vs_bbi_oreb_distance": round(statistics.correlation(*zip(*pairs)), 3) if len(pairs) > 2 else None}

    if args.replay:
        rep = today_replay(args.replay)
        lt = rep["league_totals"]
        team_orb = _team_orb_from_results(rep["results"])
        out["today_replay"] = {"games": rep["games"], "seconds": rep["seconds"],
                               "league_totals": {k: v for k, v in lt.items() if not isinstance(v, (dict, list))}}
        if team_orb:
            common = [t for t in teams if t in team_orb]
            if len(common) > 2:
                out["today_replay"]["team_orb"] = {"teams": len(common),
                                                   "corr": round(statistics.correlation([team_orb[t] for t in common], [reb.team_real[t] for t in common]), 3)}
    out["rebounds"] = reb_out
    out["fouls"] = foul_out
    out["seconds"] = round(time.perf_counter() - t0, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("setup", "seconds")}, indent=1))
    print_tables(out)
    return 0


def print_tables(out: dict) -> None:
    r = out["rebounds"]
    print("\n## Rebounds: per-player rates per chance (2025-26)")
    print("| Rate | Players | Real | Kernel as built | bias | error beyond noise | corr | Kernel refit | bias | error beyond noise | corr |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for scope in ("all", "held"):
        for side, label in (("orb", "Offensive rebound %"), ("drb", "Defensive rebound %")):
            b, f = r["rates"][f"built_{scope}"][side], r["rates"][f"fit_{scope}"][side]
            print(f"| {label} ({scope}) | {b['players']} | {pct(b['real'])} | {pct(b['predicted'])} | {100*b['bias']:+.1f} | {pct(b['excess_rmse'])} | {b['corr']} | "
                  f"{pct(f['predicted'])} | {100*f['bias']:+.1f} | {pct(f['excess_rmse'])} | {f['corr']} |")
    print("\n## Rebounds per 36 (kernel at league chances per minute vs today's fitted rate)")
    print("| Players | Stat | Real | Kernel built (err/corr) | Kernel refit (err/corr) | Today (err/corr) |")
    print("|---|---|---|---|---|---|")
    for scope in ("all", "held"):
        for key in ("reb", "oreb", "dreb"):
            b, f = r["per36"][f"kernel_built_{key}_{scope}"], r["per36"][f"kernel_fit_{key}_{scope}"]
            t = r["per36"].get(f"today_{key}_{scope}")
            tcell = f"{num(t['predicted'])} ({num(t['excess_rmse'])}/{t['corr']})" if t else "—"
            print(f"| {scope} | {key} | {num(b['real'])} | {num(b['predicted'])} ({num(b['excess_rmse'])}/{b['corr']}) | "
                  f"{num(f['predicted'])} ({num(f['excess_rmse'])}/{f['corr']}) | {tcell} |")
    print("\nLeague:", json.dumps(r["league"]["fit_orb_pct"]), "real", r["league"]["real_orb_pct"], "built", r["league"]["built_orb_pct"])
    print("By miss (refit):", r["league"]["fit_orb_by_miss"])
    print("Teams:", r["league"]["team_built"], r["league"]["team_fit"], "real sd", r["league"]["team_real_sd"])
    print("Timing us:", r["timing_us"])
    f = out["fouls"]
    print("\n## Fouls and free throws (2025-26)")
    print("| Stat | Scope | Real | Kernel built (bias/err/corr) | Kernel refit (bias/err/corr) | Today (bias/err/corr) |")
    print("|---|---|---|---|---|---|")
    for scope in ("all", "held"):
        for key in ("fta_per_fga", "pf36"):
            cells = []
            for who in ("built", "fit", "today"):
                s = f[f"{who}_{scope}"][key]
                cells.append(f"{num(s['predicted'], 3)} ({s['bias']:+.3f}/{num(s['excess_rmse'], 3)}/{s['corr']})")
            print(f"| {key} | {scope} | {num(f['built_all'][key]['real'], 3)} | " + " | ".join(cells) + " |")
    print("League:", json.dumps(f["league"]))
    print("Timing us:", f["timing_us"])
    ho = out["held_out_season"]
    print(f"\n## Held-out season {ho['season']} ({ho['players']} players; levels matched)")
    for k, v in ho.items():
        if isinstance(v, dict):
            print(k, json.dumps(v))
    print("\nPosition check:", out["position_check"])
    if "today_replay" in out:
        print("Today replay:", json.dumps(out["today_replay"]))


if __name__ == "__main__":
    raise SystemExit(main())
