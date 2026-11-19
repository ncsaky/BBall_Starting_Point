#!/usr/bin/env python3
"""Trade-behaviour metrics for a two-season probe run (scripts/two_season_league_probe.py).

Read-only on the save. Writes <out>/trades_<label>.json / .md (the same trade list as inputs_readiness_report.py)
and <out>/trade_metrics_<label>.json with the measures the trade-AI redesign tracks after each step
(docs/agents/tasks/trade-review-2026-11-19.md, docs/agents/tasks/trade-step1-own-value.md):

- trades per season and by window (deadline week, draft, offseason, in-season)
- players traded 2+ and 3+ times; young players moved; star-for-star swaps
- rebuilding teams taking on 30+ year-olds with $15M+ multi-year contracts
- trades where both teams net more than +5
- the receiving team's value of the assets vs the sending team's own value of the same assets
- trade-search evaluations and CPU time (whole run and the deadline runs), from the probe's progress.jsonl

  PYTHONPATH=src:scripts .venv/bin/python -u scripts/trade_probe_metrics.py \
      --run output/probe/inputs_v1 --label after_inputs_v1 --out output/probe
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import statistics

from inputs_readiness_report import season_of, trade_list, trades_markdown
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.save import canonical_with_save, ensure_league_save_defaults, load_save

STAR_OVERALL = 68.0
STAR_SALARY = 35.0


def window_of(day: str) -> str:
    md = day[5:10]
    year = int(day[:4])
    if "06-01" <= md <= "06-30":
        return "draft"
    if "07-01" <= md <= "10-19":
        return "offseason"
    if md[:2] in {"01", "02"} and 0 <= (date(year, 2, 5) - date.fromisoformat(day[:10])).days <= 6:
        return "deadline_week"  # the game's deadline is February 5 (save.trade_deadline_date)
    return "in_season"


def quantiles(values):
    values = sorted(values)
    if not values:
        return None
    pick = lambda q: round(values[min(len(values) - 1, int(round((len(values) - 1) * q)))], 3)
    return {"n": len(values), "q25": pick(.25), "median": pick(.5), "q75": pick(.75), "mean": round(statistics.fmean(values), 3)}


def is_star(asset) -> bool:
    if asset.get("kind") != "player":
        return False
    salary = (asset.get("contract_at_trade") or {}).get("salary_millions_this_season") or 0
    return (asset.get("overall_end_of_run_neutral") or 0) >= STAR_OVERALL or (salary >= STAR_SALARY and (asset.get("age_at_trade") or 99) <= 33)


def metrics(trades, progress):
    out = {"trades": len(trades)}
    out["by_season"] = dict(sorted(Counter(t["season"] for t in trades).items()))
    out["by_window"] = dict(sorted(Counter(window_of(t["date"]) for t in trades).items()))
    out["by_season_window"] = {season: dict(sorted(Counter(window_of(t["date"]) for t in trades if t["season"] == season).items()))
                               for season in out["by_season"]}
    out["multi_team"] = sum(1 for t in trades if len(t["teams"]) > 2)
    moves = Counter(a["id"] for t in trades for assets in t["sends"].values() for a in assets if a.get("kind") == "player")
    out["players_moved"] = sum(moves.values())
    out["players_traded_2plus"] = sum(1 for n in moves.values() if n >= 2)
    out["players_traded_3plus"] = sum(1 for n in moves.values() if n >= 3)
    names = {a["id"]: a.get("label") for t in trades for assets in t["sends"].values() for a in assets}
    out["traded_3plus_names"] = sorted(names[pid] for pid, n in moves.items() if n >= 3)
    young = [a for t in trades for assets in t["sends"].values() for a in assets
             if a.get("kind") == "player" and (a.get("age_at_trade") or 99) <= 23]
    out["young_players_moved_23_or_younger"] = len(young)
    out["players_moved_25_or_younger"] = sum(1 for t in trades for assets in t["sends"].values() for a in assets
                                             if a.get("kind") == "player" and (a.get("age_at_trade") or 99) <= 25)
    rebuild_vets = []
    star_swaps = []
    both_win = 0
    ratios, asset_ratios = [], []
    for t in trades:
        evals = {e.get("team_abbrev"): e for e in t["evaluations"]}
        if len(t["teams"]) == 2 and all((evals.get(team) or {}).get("net_value", -99) > 5 for team in t["teams"]):
            both_win += 1
        for giver, assets in t["sends"].items():
            receivers = [team for team in t["teams"] if team != giver]
            if len(receivers) != 1:
                continue
            receiver = receivers[0]
            phase = (t["team_context"].get(receiver) or {}).get("phase")
            for a in assets:
                c = a.get("contract_at_trade") or {}
                if (a.get("kind") == "player" and phase == "rebuilding" and (a.get("age_at_trade") or 0) >= 30
                        and (c.get("salary_millions_this_season") or 0) >= 15 and (c.get("years_left_incl_this") or 0) >= 2):
                    rebuild_vets.append({"date": t["date"], "buyer": receiver, "player": a.get("label"),
                                         "age": a.get("age_at_trade"), "salary": c.get("salary_millions_this_season"),
                                         "years": c.get("years_left_incl_this")})
            if len(t["teams"]) == 2:
                g, r = evals.get(giver) or {}, evals.get(receiver) or {}
                if g.get("outgoing_value") and r.get("incoming_value") is not None:
                    ratios.append(float(r["incoming_value"]) / max(1.0, float(g["outgoing_value"])))
                    asset_in = float(r["incoming_value"]) - float(r.get("strategic_adjustment") or 0.0)
                    asset_ratios.append(asset_in / max(1.0, float(g["outgoing_value"])))
        if len(t["teams"]) == 2 and all(any(is_star(a) for a in t["sends"].get(team, [])) for team in t["teams"]):
            star_swaps.append({"date": t["date"], "summary": " / ".join(
                f"{team}: " + ", ".join(a.get("label") for a in t["sends"][team] if a.get("kind") == "player")
                for team in t["teams"])})
    out["both_sides_net_above_5"] = both_win
    out["trades_with_stated_reasons"] = sum(1 for t in trades if t.get("why"))
    out["by_target"] = dict(sorted(Counter(t.get("target_key") or "none" for t in trades).items()))
    out["accepted_by_both_own_evaluations"] = sum(
        1 for t in trades if t["evaluations"] and all(str(e.get("decision") or "").startswith("accept") for e in t["evaluations"]))
    out["draft_trades_accepted_by_both"] = sum(
        1 for t in trades if window_of(t["date"]) == "draft" and t["evaluations"]
        and all(str(e.get("decision") or "").startswith("accept") for e in t["evaluations"]))
    out["rebuilding_buys_30plus_15m_multiyear"] = len(rebuild_vets)
    out["rebuilding_buys_detail"] = rebuild_vets
    out["star_for_star_swaps"] = len(star_swaps)
    out["star_for_star_detail"] = star_swaps
    out["receiver_over_giver_value"] = quantiles(ratios)
    out["receiver_assets_over_giver_value"] = quantiles(asset_ratios)
    steps = [row for row in progress if "to" in row]
    out["search"] = {
        "trade_evaluations_total": sum(int(row.get("trade_evaluations") or 0) for row in steps),
        "cpu_seconds_total": round(sum(float(row.get("cpu_seconds") or 0) for row in steps), 1),
        "wall_seconds_total": round(sum(float(row.get("seconds") or 0) for row in steps), 1),
    }
    deadline_runs = {}
    for row in steps:
        start, end = str(row["from"]), str(row["to"])
        for year in range(int(start[:4]), int(end[:4]) + 1):
            deadline = f"{year}-02-05"
            week_start = f"{year}-01-29"  # deadline week: the 7 days up to and including February 5
            if start < deadline and end > week_start:
                run = deadline_runs.setdefault(deadline, {"actions": 0, "trade_evaluations": 0, "cpu_seconds": 0.0, "wall_seconds": 0.0})
                run["actions"] += 1
                run["trade_evaluations"] += int(row.get("trade_evaluations") or 0)
                run["cpu_seconds"] = round(run["cpu_seconds"] + float(row.get("cpu_seconds") or 0), 1)
                run["wall_seconds"] = round(run["wall_seconds"] + float(row.get("seconds") or 0), 1)
    out["search"]["deadline_runs"] = deadline_runs
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, required=True, help="probe output directory (saves/league.json, progress.jsonl)")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    canonical = load_app_canonical(root)
    save_path = args.run / "saves/league.json"
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    trades = trade_list(save_path, save, active, canonical, args.label)
    progress = [json.loads(line) for line in (args.run / "progress.jsonl").read_text().splitlines() if line.strip()]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"trades_{args.label}.json").write_text(json.dumps(trades, indent=1, default=str) + "\n")
    (args.out / f"trades_{args.label}.md").write_text(trades_markdown(args.label, trades))
    result = {"label": args.label, "date": save["state"]["current_date"], **metrics(trades, progress)}
    (args.out / f"trade_metrics_{args.label}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if not k.endswith("_detail") and k != "traded_3plus_names"}, indent=1))


if __name__ == "__main__":
    main()
