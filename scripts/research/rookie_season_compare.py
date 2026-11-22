#!/usr/bin/env python3
"""ROOKIE-FIT-2: simulated rookie season vs real rookie classes (measurement only).

  real classes  data/research/rookie_real_lines.json: drafted rookies' first seasons, 2015-16 .. 2025-26
                (Basketball Reference season totals; a pick who never played counts as 0 minutes)
  real early    the same file's 2026-27 rookies as of the fetch date
  real growth   data/research/game_boxscores_2025_26.json: last season's rookies, first half vs second half
  simulated     <probe dir>/rookies.json from scripts/research/rookie_season_probe.py

    python3 scripts/research/rookie_season_compare.py output/rookie-fit-2/season_v1 [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import real_prospects as rp  # noqa: E402

LINES = ROOT / "data/research/rookie_real_lines.json"
BOX = ROOT / "data/research/game_boxscores_2025_26.json"
HALF = "2027-01-31"           # simulated season split (about half the games)
REAL_HALF = "2026-01-31"


def pct(values, q):
    values = sorted(values)
    if not values:
        return None
    k = (len(values) - 1) * q
    lo, hi = int(k), min(len(values) - 1, int(k) + 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def summarize(rows: list[dict], class_size: int) -> dict:
    """rows: {min, g, pts, reb, ast, fga, fta, pick}; class_size counts picks who never played (0 minutes)."""
    played = [r for r in rows if r["min"] > 0]
    zeros = class_size - len(played)
    mins = [r["min"] for r in played] + [0.0] * max(0, zeros)
    mpg = [r["min"] / r["g"] for r in played if r["g"]]
    ppg = [r["pts"] / r["g"] for r in played if r["g"]] + [0.0] * max(0, zeros)
    real = [r for r in played if r["min"] >= 500]
    p36 = [36 * r["pts"] / r["min"] for r in real]
    r36 = [36 * r["reb"] / r["min"] for r in real]
    a36 = [36 * r["ast"] / r["min"] for r in real]
    ts = [r["pts"] / (2 * (r["fga"] + 0.44 * r["fta"])) for r in real if r["fga"] + r["fta"] > 0]
    q = lambda xs: [round(pct(xs, p), 1) for p in (0.1, 0.25, 0.5, 0.75, 0.9)] if xs else None
    return {
        "class_size": class_size, "played": len(played),
        "minutes_p10_25_50_75_90": q(mins), "mpg_if_played": q(mpg), "ppg": q(ppg),
        "per36_pts_500min": q(p36), "per36_reb_500min": q(r36), "per36_ast_500min": q(a36),
        "ts_500min": [round(x, 3) for x in (pct(ts, 0.25), pct(ts, 0.5), pct(ts, 0.75))] if ts else None,
        "share_15ppg": round(sum(1 for r in played if r["g"] and r["pts"] / r["g"] >= 15) / class_size, 3),
        "share_10ppg": round(sum(1 for r in played if r["g"] and r["pts"] / r["g"] >= 10) / class_size, 3),
        "share_1500min": round(sum(1 for r in played if r["min"] >= 1500) / class_size, 3),
        "share_under_300min": round((sum(1 for r in played if r["min"] < 300) + zeros) / class_size, 3),
        "count_15ppg": sum(1 for r in played if r["g"] and r["pts"] / r["g"] >= 15),
    }


def real_classes() -> dict:
    data = json.loads(LINES.read_text())
    out, pooled, pooled_size = {}, [], 0
    for season, rows in sorted(data["classes"].items()):
        year = int(season) - 1
        drafted = [r for r in rows if r.get("draft_year") == year and r.get("pick")]
        picks = {r["pick"] for r in drafted}
        size = max(58, max(picks) if picks else 60)   # a 58-60 pick draft; undrafted / missing picks count as 0
        if len(picks) < 30:
            continue                                   # draft table not matched for this class
        conv = [{"min": r["mp"], "g": r["g"], "pts": r["pts"], "reb": r["trb"], "ast": r["ast"], "fga": r["fga"],
                 "fta": r["fta"], "pick": r["pick"]} for r in drafted]
        out[season] = summarize(conv, size)
        pooled.extend(conv)
        pooled_size += size
    pooled_summary = summarize(pooled, pooled_size)
    return {"by_class": out, "pooled": pooled_summary, "classes": len(out),
            "mean_count_15ppg_per_class": round(statistics.fmean(v["count_15ppg"] for v in out.values()), 1),
            "range_count_15ppg": [min(v["count_15ppg"] for v in out.values()), max(v["count_15ppg"] for v in out.values())]}


def sim_rows(timeline_entry: dict, base: dict | None = None) -> list[dict]:
    rows = []
    for pid, r in timeline_entry["rookies"].items():
        s = r.get("stats") or {}
        b = ((base or {}).get(pid) or {}).get("stats") or {}
        d = {k: float(s.get(k) or 0) - float(b.get(k) or 0) for k in ("games", "minutes", "points", "rebounds",
                                                                     "assists", "fga", "fta")}
        rows.append({"id": pid, "name": r["name"], "team": r["team"], "pick": r.get("pick"), "ovr": r.get("ovr"),
                     "min": d["minutes"], "g": d["games"], "pts": d["points"], "reb": d["rebounds"],
                     "ast": d["assists"], "fga": d["fga"], "fta": d["fta"]})
    return rows


def nearest(timeline, date):
    best = None
    for entry in timeline:
        if entry["date"] <= date:
            best = entry
    return best


def real_growth() -> dict:
    """Last season's rookies (2025 draft): per-36 points / rebounds / assists and minutes per game, first half of the
    season vs second half (real box scores), players with 300+ minutes in each half."""
    lines = json.loads(LINES.read_text())["classes"]["2026"]
    rookies = {rp.name_key(r["name"]) for r in lines if r.get("draft_year") == 2025}
    box = json.loads(BOX.read_text())["games"]
    halves = {}
    for game in box:
        if game.get("phase") != "regular":
            continue
        half = 0 if game["date"] <= REAL_HALF else 1
        for p in game["players"]:
            k = rp.name_key(p["player_name"])
            if k not in rookies or p.get("dnp") or not p.get("minutes"):
                continue
            h = halves.setdefault(k, [dict(min=0, g=0, pts=0, reb=0, ast=0) for _ in range(2)])[half]
            h["min"] += p["minutes"]; h["g"] += 1; h["pts"] += p["points"]; h["reb"] += p["rebounds"]; h["ast"] += p["assists"]
    return growth_table(halves)


def growth_table(halves: dict) -> dict:
    both = {k: v for k, v in halves.items() if v[0]["min"] >= 300 and v[1]["min"] >= 300}
    out = {"players": len(both)}
    for stat in ("pts", "reb", "ast"):
        diffs = [36 * v[1][stat] / v[1]["min"] - 36 * v[0][stat] / v[0]["min"] for v in both.values()]
        out[f"per36_{stat}_change_median"] = round(statistics.median(diffs), 2) if diffs else None
        out[f"per36_{stat}_change_mean"] = round(statistics.fmean(diffs), 2) if diffs else None
    mp = [v[1]["min"] / v[1]["g"] - v[0]["min"] / v[0]["g"] for v in both.values()]
    out["mpg_change_median"] = round(statistics.median(mp), 2) if mp else None
    out["mpg_change_mean"] = round(statistics.fmean(mp), 2) if mp else None
    out["first_half_mpg_median"] = round(statistics.median(v[0]["min"] / v[0]["g"] for v in both.values()), 1) if both else None
    out["first_half_per36_pts_median"] = round(statistics.median(36 * v[0]["pts"] / v[0]["min"] for v in both.values()), 1) if both else None
    return out


def sim_growth(timeline) -> dict:
    start = next(e for e in timeline if e["date"] >= "2026-10-20")
    mid = nearest(timeline, HALF)
    end = timeline[-1]
    first = {r["id"]: r for r in sim_rows(mid, start["rookies"])}
    second = {r["id"]: r for r in sim_rows(end, mid["rookies"])}
    halves = {pid: [first[pid], second[pid]] for pid in first if pid in second}
    out = growth_table(halves)
    d_ovr = [(end["rookies"][pid]["ovr"] or 0) - (start["rookies"][pid]["ovr"] or 0)
             for pid in start["rookies"] if pid in end["rookies"]]
    out["card_overall_change_season_median"] = round(statistics.median(d_ovr), 2)
    out["card_overall_change_season_mean"] = round(statistics.fmean(d_ovr), 2)
    out["split_dates"] = [start["date"], mid["date"], end["date"]]
    by_month = []
    for e in timeline:
        if e["date"] >= start["date"]:
            vals = [r["ovr"] for r in e["rookies"].values() if r.get("ovr") is not None]
            by_month.append((e["date"], round(statistics.fmean(vals), 2)))
    out["class_mean_overall_by_step"] = by_month
    return out


def early_compare(timeline, as_of: str) -> list[dict]:
    """Simulated rookies at the same date as the real fetch vs their real 2026-27 start (per 36, minutes per game)."""
    data = json.loads(LINES.read_text())["season_2027"]
    real = {rp.name_key(r["name"]): r for r in data["rookies"]}
    start = next(e for e in timeline if e["date"] >= "2026-10-20")
    sim = {rp.name_key(r["name"]): r for r in sim_rows(nearest(timeline, as_of), start["rookies"])}
    rows = []
    for k, s in sim.items():
        r = real.get(k) or real.get(k + " jr")
        if not r:
            continue
        rows.append({"name": s["name"], "pick": s["pick"], "team": s["team"], "ovr": s["ovr"],
                     "sim_mpg": round(s["min"] / s["g"], 1) if s["g"] else 0.0,
                     "real_mpg": round(r["mp"] / r["g"], 1) if r["g"] else 0.0,
                     "sim_p36": round(36 * s["pts"] / s["min"], 1) if s["min"] >= 60 else None,
                     "real_p36": round(36 * r["pts"] / r["mp"], 1) if r["mp"] >= 60 else None,
                     "sim_ppg": round(s["pts"] / s["g"], 1) if s["g"] else 0.0,
                     "real_ppg": round(r["pts"] / r["g"], 1) if r["g"] else 0.0,
                     "real_min": r["mp"], "real_bpm": r.get("bpm"), "real_team": r.get("team"),
                     "real_team_net": (data["teams"].get(r.get("team")) or {}).get("net_rtg")})
    rows.sort(key=lambda x: -x["real_min"])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("probe_dirs", type=Path, nargs="+", help="one or more probe directories (seeds are pooled)")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    real = real_classes()
    as_of = json.loads(LINES.read_text())["season_2027"]["as_of"]
    runs = []
    for d in args.probe_dirs:
        # The rookies' first season only (probes may run on into later seasons).
        timeline = [e for e in json.loads((d / "rookies.json").read_text())["timeline"] if e["date"] <= "2027-04-13"]
        start = next(e for e in timeline if e["date"] >= "2026-10-20")
        rows = sim_rows(timeline[-1], start["rookies"])
        runs.append({"dir": str(d), "through": timeline[-1]["date"], "rows": rows,
                     "season": summarize(rows, len(rows)), "growth": sim_growth(timeline),
                     "early": early_compare(timeline, as_of)})
    pooled_rows = [r for run in runs for r in run["rows"]]
    pooled = summarize(pooled_rows, len(pooled_rows))
    out = {"runs": [{k: v for k, v in run.items() if k != "rows"} for run in runs], "simulated_pooled": pooled,
           "real": real, "growth_real_2025_26": real_growth()}
    print(f"simulated seasons: {len(runs)} ({', '.join(r['dir'] + ' to ' + r['through'] for r in runs)})")
    for key in ("minutes_p10_25_50_75_90", "mpg_if_played", "ppg", "per36_pts_500min", "per36_reb_500min",
                "per36_ast_500min", "ts_500min", "share_15ppg", "share_10ppg", "share_1500min", "share_under_300min"):
        print(f"  {key:26s} sim {pooled[key]}   real (pooled {real['classes']} classes) {real['pooled'][key]}")
    print(f"  15+ ppg rookies per class: sim {[r['season']['count_15ppg'] for r in runs]}, real mean "
          f"{real['mean_count_15ppg_per_class']} (range {real['range_count_15ppg']})")
    print("growth real 2025-26:", out["growth_real_2025_26"])
    for run in runs:
        print("growth simulated:", {k: v for k, v in run["growth"].items() if k != "class_mean_overall_by_step"})
        print("  class mean overall by step:", run["growth"]["class_mean_overall_by_step"])
    # Early season: simulated values averaged over seeds, per rookie.
    merged = {}
    for run in runs:
        for r in run["early"]:
            merged.setdefault(r["name"], []).append(r)
    print(f"\nearly season (as of {as_of}), simulated (mean of seeds) vs real:")
    early = []
    for name, rs in sorted(merged.items(), key=lambda kv: -kv[1][0]["real_min"]):
        mean = lambda k: round(statistics.fmean(x[k] for x in rs if x[k] is not None), 1) if any(x[k] is not None for x in rs) else None
        row = {"name": name, "pick": rs[0]["pick"], "ovr": rs[0]["ovr"], "sim_mpg": mean("sim_mpg"),
               "real_mpg": rs[0]["real_mpg"], "sim_ppg": mean("sim_ppg"), "real_ppg": rs[0]["real_ppg"],
               "sim_p36": mean("sim_p36"), "real_p36": rs[0]["real_p36"], "real_min": rs[0]["real_min"],
               "real_bpm": rs[0]["real_bpm"], "real_team": rs[0]["real_team"], "real_team_net": rs[0]["real_team_net"]}
        early.append(row)
        if row["real_min"] >= 100:
            print(f"  {name[:22]:22s} pick {row['pick']} ovr {row['ovr']}  mpg sim {row['sim_mpg']} real {row['real_mpg']} | "
                  f"ppg sim {row['sim_ppg']} real {row['real_ppg']} | per36 sim {row['sim_p36']} real {row['real_p36']} | "
                  f"real box +/- {row['real_bpm']} {row['real_team']} net {row['real_team_net']}")
    out["early_mean_of_seeds"] = early
    print("\nsimulated full season (first run), top 25 by minutes:")
    for r in sorted(runs[0]["rows"], key=lambda r: -r["min"])[:25]:
        g = r["g"] or 1
        print(f"  {r['name'][:22]:22s} pick {r['pick']} {r['team']} ovr {r['ovr']}  g {r['g']:.0f} mpg {r['min'] / g:4.1f} "
              f"ppg {r['pts'] / g:4.1f} rpg {r['reb'] / g:4.1f} apg {r['ast'] / g:4.1f}")
    out["season_lines"] = {run["dir"]: sorted(run["rows"], key=lambda r: -r["min"]) for run in runs}
    if args.json:
        args.json.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
