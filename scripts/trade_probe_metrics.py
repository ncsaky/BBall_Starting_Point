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


def _win_share(record):
    try:
        wins, losses = (int(x) for x in str(record or "").split("-"))
    except ValueError:
        return None, 0
    games = wins + losses
    return (wins / games if games else None), games


def trade_2b_metrics(trades):
    """Measures added for trade 2b (docs/agents/tasks/trade-2b-followups.md)."""
    out = {}
    rebuild_sales, tax_moves, young_starters, odd_labels = [], [], [], []
    for t in trades:
        ctx = t.get("team_context") or {}
        notes = " ".join(str(e.get("notes") or "") for e in t.get("evaluations") or [])
        why = str(t.get("why") or "")
        if (t.get("target_key") == "salary_dump" or "Luxury tax: the deal saves" in notes
                or "luxury tax" in why.lower()):
            tax_moves.append({"date": t["date"], "teams": t["teams"], "why": why or None,
                              "dump": t.get("target_key") == "salary_dump"})
        for giver, assets in t["sends"].items():
            receivers = [team for team in t["teams"] if team != giver]
            giver_phase = (ctx.get(giver) or {}).get("phase")
            for a in assets:
                if a.get("kind") != "player":
                    continue
                age = a.get("age_at_trade") or 0
                mpg = ((a.get("season_before_trade") or {}).get("mpg") or 0)
                if (len(receivers) == 1 and giver_phase in {"rebuilding", "exiting"} and age >= 28
                        and (ctx.get(receivers[0]) or {}).get("phase") in {"peak", "entering"}):
                    rebuild_sales.append({"date": t["date"], "seller": giver, "seller_phase": giver_phase,
                                          "buyer": receivers[0], "player": a.get("label"), "age": age})
                if age and age <= 25.5 and mpg >= 24:
                    young_starters.append({"date": t["date"], "seller": giver, "seller_phase": giver_phase,
                                           "player": a.get("label"), "age": age, "mpg": mpg, "why": why or None,
                                           "target_key": t.get("target_key")})
        for team, row in ctx.items():
            share, games = _win_share(row.get("record_at_trade"))
            phase = row.get("phase")
            if share is None or games < 25:
                continue
            if (phase == "rebuilding" and share >= .55) or (phase in {"peak", "entering"} and share <= .38):
                odd_labels.append({"date": t["date"], "team": team, "phase": phase, "record": row.get("record_at_trade")})
    out["rebuild_sales"] = len(rebuild_sales)
    out["rebuild_sales_detail"] = rebuild_sales
    out["tax_moves"] = len(tax_moves)
    out["salary_dumps"] = sum(1 for m in tax_moves if m["dump"])
    out["tax_moves_detail"] = tax_moves
    out["young_starters_moved"] = len(young_starters)
    out["young_starters_moved_detail"] = young_starters
    team_contexts = sum(1 for t in trades for row in (t.get("team_context") or {}).values()
                        if _win_share(row.get("record_at_trade"))[1] >= 25)
    out["odd_phase_labels"] = {"count": len(odd_labels), "of_team_contexts_25_plus_games": team_contexts}
    out["odd_phase_labels_detail"] = odd_labels
    return out


BIG_BAD_SALARY = 20.0     # $M this season, 2+ years left, on-court value under 60 at the end of the run


def step4_metrics(trades):
    """Measures added for trade step 4 (docs/agents/tasks/trade-step4-multi-team.md)."""
    out = {}
    multi = [t for t in trades if len(t["teams"]) > 2]
    deadline = [t for t in trades if window_of(t["date"]) == "deadline_week"]
    out["multi_team_share"] = round(len(multi) / max(1, len(trades)), 3)
    out["multi_team_deadline"] = sum(1 for t in deadline if len(t["teams"]) > 2)
    out["multi_team_deadline_share"] = round(out["multi_team_deadline"] / max(1, len(deadline)), 3)
    out["four_team"] = sum(1 for t in multi if len(t["teams"]) >= 4)
    out["multi_team_by_kind"] = dict(sorted(Counter(t.get("target_key") or "none" for t in multi).items()))
    out["multi_team_detail"] = [{"date": t["date"], "teams": t["teams"], "why": t.get("why"),
                                 "sends": {team: [f"{a.get('label') or a.get('id')} -> {a.get('to')}" for a in assets]
                                           for team, assets in t["sends"].items()}} for t in multi]
    dumps_with_picks, dumps = 0, 0
    for t in trades:
        if t.get("target_key") != "salary_dump":
            continue
        dumps += 1
        if any(a.get("kind") != "player" for a in t["sends"].get(t["teams"][0], [])):
            dumps_with_picks += 1
    out["salary_dumps_with_picks"] = dumps_with_picks
    out["salary_dumps_two_team"] = dumps
    absorbed = [t for t in multi if str(t.get("target_key") or "").startswith(("three_team_absorber", "three_team_tax", "four"))]
    out["absorber_trades"] = len(absorbed)
    bad = []
    for t in trades:
        for giver, assets in t["sends"].items():
            for a in assets:
                c = a.get("contract_at_trade") or {}
                if (a.get("kind") == "player" and (c.get("salary_millions_this_season") or 0) >= BIG_BAD_SALARY
                        and (c.get("years_left_incl_this") or 0) >= 2 and (a.get("on_court_value_end_of_run") or 99) < 60):
                    bad.append({"date": t["date"], "from": giver, "player": a.get("label"),
                                "salary": c.get("salary_millions_this_season"), "years": c.get("years_left_incl_this"),
                                "teams": t["teams"]})
    out["big_contracts_low_value_moved"] = len(bad)
    out["big_contracts_low_value_moved_detail"] = bad
    return out


def metrics(trades, progress):
    out = {"trades": len(trades)}
    out["by_season"] = dict(sorted(Counter(t["season"] for t in trades).items()))
    out["by_window"] = dict(sorted(Counter(window_of(t["date"]) for t in trades).items()))
    out["by_season_window"] = {season: dict(sorted(Counter(window_of(t["date"]) for t in trades if t["season"] == season).items()))
                               for season in out["by_season"]}
    out["multi_team"] = sum(1 for t in trades if len(t["teams"]) > 2)
    out.update(step4_metrics(trades))
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
    out["both_sides_net_above_5_share"] = round(both_win / max(1, len(trades)), 3)
    out.update(trade_2b_metrics(trades))
    out["trades_with_stated_reasons"] = sum(1 for t in trades if t.get("why"))
    # TRADE-DEADLINE: counter-offers (trade step 3) and sellers receiving a player that matches their own targets.
    countered = [t for t in trades if t.get("counter")]
    out["counter_trades"] = len(countered)
    out["counter_share"] = round(len(countered) / max(1, len(trades)), 3)
    out["counter_by_kind"] = dict(sorted(Counter(s.get("kind") for t in countered
                                                 for s in (t["counter"].get("steps") or [])).items()))
    out["counter_two_rounds"] = sum(1 for t in countered if int(t["counter"].get("rounds") or 1) >= 2)
    out["counter_rounds_distribution"] = dict(sorted(Counter(int(t["counter"].get("rounds") or 1) for t in countered).items()))
    out["seller_got_target_match"] = sum(1 for t in trades if t.get("seller_target_match"))
    # How far above its own price the last asking team ended in the full check (a fair ask stays close to 0).
    asking_nets = []
    for t in countered:
        last = (t["counter"].get("steps") or [{}])[-1]
        e = next((e for e in t["evaluations"] if e.get("team_abbrev") == last.get("asking_team")), None)
        if e and e.get("net_value") is not None:
            asking_nets.append(float(e["net_value"]) - float(e.get("acceptance_threshold") or 0.0))
    out["counter_asking_net_over_price"] = quantiles(asking_nets)
    out["counter_detail"] = [{"date": t["date"], "teams": t["teams"], "text": t["counter"].get("text")} for t in countered]
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


def _pick_slots(save):
    """pick id -> overall slot, from the save's draft orders (every draft the run reached)."""
    slots = {}
    for order in (save.get("draft_orders") or {}).values():
        rows = (order.get("draft_order") or order.get("picks")) if isinstance(order, dict) else order
        for index, row in enumerate(rows or []):
            if not isinstance(row, dict):
                continue
            pid = row.get("pick_id") or row.get("id")
            overall = row.get("overall_pick") or row.get("overall") or index + 1
            if pid:
                slots[pid] = int(overall)
    return slots


def taxpool_metrics(save, active, trades):
    """Measures added for TRADE-TAXPOOL (docs/agents/tasks/trade-taxpool.md): draft-night spread and chains, teams over
    the tax line entering and leaving deadline week, and the recorded tax payouts."""
    out = {}
    slots = _pick_slots(save)
    draft = []
    for t in trades:
        if window_of(t["date"]) != "draft":
            continue
        picks = sorted(slots[a["id"]] for assets in t["sends"].values() for a in assets
                       if a.get("kind") == "pick" and a.get("id") in slots and str(a.get("season")) == t["date"][:4])
        draft.append({"date": t["date"], "teams": t["teams"], "slots": picks, "why": t.get("why"),
                      "target_key": t.get("target_key")})
    out["draft_night_detail"] = draft
    out["draft_night_top_slot"] = [d["slots"][0] if d["slots"] else None for d in draft]
    buckets = Counter()
    for d in draft:
        top = d["slots"][0] if d["slots"] else None
        buckets["unknown" if top is None else "1-10" if top <= 10 else "11-20" if top <= 20 else "21-30" if top <= 30
                else "31-60"] += 1
    out["draft_night_by_part"] = dict(sorted(buckets.items()))
    out["draft_night_multi_team"] = sum(1 for d in draft if len(d["teams"]) > 2)
    # Teams over the line entering deadline week, estimated from the payroll recorded at the end of the regular season
    # minus the salary each team took on in deadline-week trades (signings after the deadline are not removed).
    teams = {t["id"]: t["abbrev"] for t in active.get("teams", [])}
    history = save.get("team_payroll_history") or {}
    deadline = {}
    for season, rows in sorted(history.items()):
        end_year = int(season[:4]) + 1
        net = Counter()
        for t in trades:
            if t["date"][:4] != str(end_year) or window_of(t["date"]) != "deadline_week":
                continue
            for giver, assets in t["sends"].items():
                for a in assets:
                    if a.get("kind") != "player":
                        continue
                    salary = (a.get("contract_at_trade") or {}).get("salary_millions_this_season") or 0
                    receiver = a.get("to") or next((x for x in t["teams"] if x != giver), None)
                    net[giver] -= salary
                    net[receiver] += salary
        over_before, over_after, got_under = [], [], []
        for tid, row in rows.items():
            abbrev = teams.get(tid, tid)
            line = float(row.get("tax_line") or 0) / 1e6
            end = float(row.get("payroll") or 0) / 1e6
            start = end - net.get(abbrev, 0.0)
            if start > line:
                over_before.append(abbrev)
            if end > line:
                over_after.append(abbrev)
            if start > line >= end:
                got_under.append(abbrev)
        deadline[season] = {"over_entering_deadline_week": sorted(over_before),
                            "over_at_season_end": sorted(over_after), "got_under_in_deadline_week": sorted(got_under)}
    out["tax_line_at_deadline"] = deadline
    out["tax_payouts"] = {season: {k: rec.get(k) for k in ("total_tax", "distributed", "share_per_team")}
                          | {"taxpayers": [teams.get(t, t) for t in rec.get("taxpayers") or []]}
                          for season, rec in sorted((save.get("luxury_tax_payouts") or {}).items())}
    return out


def payroll_metrics(save, active, trades):
    """TRADE-VOLUME: taxpayers and the payout recounted at the real tax line (cap_rules) for every run, so runs made
    before the shared line (whose save recorded the trade code's $207.4M line) compare on the same line; and
    free-agency outcomes from the transaction log and the latest market's offers."""
    from nba_gm_data.cap_rules import cap_lines_for_season
    from nba_gm_data.trade_tax import luxury_tax_bill, is_repeat_taxpayer, POOL_DISTRIBUTED_SHARE
    teams = {t["id"]: t["abbrev"] for t in active.get("teams", [])}
    out = {}
    history = save.get("team_payroll_history") or {}
    real = {}
    for season, rows in sorted(history.items()):
        line = cap_lines_for_season(season)["tax_line"]
        end_year = int(season[:4]) + 1
        net = Counter()
        for t in trades:
            if t["date"][:4] != str(end_year) or window_of(t["date"]) != "deadline_week":
                continue
            for giver, assets in t["sends"].items():
                for a in assets:
                    if a.get("kind") != "player":
                        continue
                    salary = (a.get("contract_at_trade") or {}).get("salary_millions_this_season") or 0
                    receiver = a.get("to") or next((x for x in t["teams"] if x != giver), None)
                    net[giver] -= salary * 1e6
                    net[receiver] += salary * 1e6
        over_before, over_after, bills = [], [], {}
        for tid, row in rows.items():
            abbrev = teams.get(tid, tid)
            end = float(row.get("payroll") or 0)
            if end - net.get(abbrev, 0.0) > line:
                over_before.append(abbrev)
            if end > line:
                over_after.append(abbrev)
            bills[abbrev] = luxury_tax_bill(end, season, is_repeat_taxpayer(active, tid, season))
        recipients = len(rows) - len(over_after)
        total = sum(bills.values())
        payrolls = sorted(float(r.get("payroll") or 0) / 1e6 for r in rows.values())
        real[season] = {"tax_line_millions": round(line / 1e6, 1),
                        "over_entering_deadline_week": len(over_before), "over_at_season_end": len(over_after),
                        "taxpayers_at_season_end": sorted(over_after),
                        "payout_per_team_millions": round(POOL_DISTRIBUTED_SHARE * total / recipients / 1e6, 2) if recipients else None,
                        "median_payroll_millions": round(payrolls[len(payrolls) // 2], 1) if payrolls else None}
    out["real_line_taxpayers"] = real
    # Free agency: signings by kind and offseason, and the latest market's accepted offers against the ask.
    kinds = {"free_agent_signing": "market", "ai_re_signing": "ai_re_signing", "ai_free_agent_signing": "ai_strategic",
             "auto_depth_signing": "minimum_fill", "waiver_claim": "waiver_claim"}
    by_year = {}
    for log in save.get("transaction_logs") or []:
        kind = kinds.get(log.get("transaction_type"))
        if not kind:
            continue
        year = str(log.get("date") or "")[:4]
        row = by_year.setdefault(year, Counter())
        row[kind] += 1
    out["signings_by_year"] = {y: dict(c) for y, c in sorted(by_year.items())}
    players = {p["id"]: p for p in active.get("players", [])}
    accepted = [o for o in save.get("free_agent_offers") or [] if o.get("status") == "accepted"]
    rows = []
    for o in accepted:
        ask = float(o.get("ask_millions") or 0)
        rows.append({"player": (players.get(o["player_id"]) or {}).get("name"), "team": teams.get(o.get("team_id")),
                     "source": o.get("source"), "aav": o.get("aav_millions"), "ask": ask, "years": o.get("years"),
                     "share_of_ask": round(float(o.get("aav_millions") or 0) / ask, 3) if ask else None})
    rows.sort(key=lambda r: -float(r["ask"] or 0))
    out["latest_market_signings"] = {"season": (save.get("free_agency_state") or {}).get("season"),
                                     "count": len(rows), "top_by_ask": rows[:15],
                                     "share_of_ask": quantiles([r["share_of_ask"] for r in rows if r["share_of_ask"]]),
                                     }
    asks = (save.get("free_agency_state") or {}).get("player_asks_millions") or {}
    market_ids = {o["player_id"]: o for o in accepted}
    top = sorted(asks.items(), key=lambda kv: -float(kv[1]))[:20]
    out["latest_market_top20_by_ask"] = {
        "signed_anywhere": sum(1 for pid, _ in top if (players.get(pid) or {}).get("team_id")),
        "signed_in_market": sum(1 for pid, _ in top if pid in market_ids),
        "players": [{"player": (players.get(pid) or {}).get("name"), "ask_end": ask,
                     "team": teams.get((players.get(pid) or {}).get("team_id")),
                     "market_aav": (market_ids.get(pid) or {}).get("aav_millions")} for pid, ask in top]}
    return out


GRADE_POINTS = (10.0, 12.0, 15.0)  # value points of difference between the two teams' textbook nets per letter grade
HEAD_SCRATCHER_LETTERS = 1.5


def market_metrics(save, trades):
    """TRADE-MARKET measures (docs/agents/tasks/trade-market.md): grade gaps with the textbook value model as the
    analyst (each team's net minus its personality terms), head-scratchers and the trait that explains each, bidding
    wars, final offers, days of negotiation, unsolicited offers for contenders' stars, personality reasons."""
    out = {}
    two = []
    for t in trades:
        if len(t["teams"]) != 2:
            continue
        evals = {e.get("team_abbrev"): e for e in t["evaluations"]}
        if not all(team in evals and evals[team].get("net_value") is not None for team in t["teams"]):
            continue
        textbook = {team: float(evals[team]["net_value"]) - float(evals[team].get("personality_total") or 0.0)
                    for team in t["teams"]}
        a, b = (textbook[team] for team in t["teams"])
        loser = min(textbook, key=textbook.get)
        terms = [term for term in evals[loser].get("personality_terms") or [] if float(term.get("points") or 0) >= 1.0]
        two.append({"date": t["date"], "teams": t["teams"], "gap": abs(a - b), "loser": loser,
                    "loser_textbook_net": round(textbook[loser], 2),
                    "loser_personality": round(float(evals[loser].get("personality_total") or 0.0), 2),
                    "loser_traits": [term.get("text") for term in terms], "why": t.get("why")})
    gaps = {}
    for k in GRADE_POINTS:
        gaps[f"points_per_letter_{int(k)}"] = {
            "one_letter_or_more": round(sum(r["gap"] >= k for r in two) / max(1, len(two)), 3),
            "one_and_a_half_or_more": round(sum(r["gap"] >= HEAD_SCRATCHER_LETTERS * k for r in two) / max(1, len(two)), 3)}
    out["grade_gaps"] = {"two_team_trades": len(two), **gaps, "real": {"one_letter_or_more": 0.59, "one_and_a_half_or_more": 0.21}}
    lopsided = [r for r in two if r["gap"] >= HEAD_SCRATCHER_LETTERS * GRADE_POINTS[0]]
    explained = [r for r in lopsided if r["loser_traits"]]
    out["head_scratchers"] = {"count": len(lopsided), "share": round(len(lopsided) / max(1, len(two)), 3),
                              "explained_by_a_trait": len(explained),
                              "textbook_only": len(lopsided) - len(explained)}
    out["head_scratchers_detail"] = lopsided
    book = save.get("trade_market") or {}
    wars = [w for w in book.get("wars") or [] if len(w.get("bidders") or []) >= 2]
    out["bidding_wars"] = len({(w.get("player_id"), str(w.get("date"))[:4]) for w in wars})
    out["bidding_war_days"] = len(wars)
    out["bidding_wars_detail"] = [{"date": w.get("date"), "player": w.get("player_name"), "seller": w.get("seller_id"),
                                   "bidders": w.get("bidders"), "rounds": len(w.get("rounds") or []),
                                   "winner": w.get("winner"), "winning_margin_over_price": w.get("winning_margin"),
                                   "rounds_detail": w.get("rounds")} for w in wars]
    out["trades_after_bidding_war"] = sum(1 for t in trades if t.get("bidding_war"))
    finals = [t for t in trades if t.get("final_offer")]
    out["trades_on_final_offers"] = len(finals)
    stats = book.get("stats") or {}
    out["market_stats_by_season"] = stats
    out["final_offers_refused"] = sum(int(v.get("final_offers_refused") or 0) for v in stats.values())
    days = [int((t.get("negotiation") or {}).get("days") or 1) for t in trades]
    out["negotiation_days_per_trade"] = dict(sorted(Counter(days).items()))
    negotiations = list((book.get("negotiations") or {}).values())
    out["ledger_negotiations_by_status"] = dict(Counter(n.get("status") for n in negotiations))
    out["ledger_rounds_per_negotiation"] = dict(sorted(Counter(len(n.get("rounds") or []) for n in negotiations).items()))
    out["unsolicited_star_offers"] = sum(int(v.get("unsolicited_star_offers") or 0) for v in stats.values())
    out["unsolicited_refused"] = sum(int(v.get("unsolicited_refused") or 0) for v in stats.values())
    out["unsolicited_detail"] = book.get("unsolicited") or []
    with_terms = [t for t in trades if t.get("personality")]
    out["trades_with_personality_reasons"] = len(with_terms)
    out["personality_terms_by_kind"] = dict(Counter(term.get("key") for t in with_terms for term in t["personality"]))
    picks_out = Counter()
    for t in trades:
        for giver, assets in t["sends"].items():
            picks_out[giver] += sum(1 for a in assets if a.get("kind") != "player")
    out["most_picks_traded_away"] = picks_out.most_common(5)
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
    result = {"label": args.label, "date": save["state"]["current_date"], **metrics(trades, progress),
              **taxpool_metrics(save, active, trades), **payroll_metrics(save, active, trades),
              **market_metrics(save, trades)}
    (args.out / f"trade_metrics_{args.label}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if not k.endswith("_detail") and k != "traded_3plus_names"}, indent=1))


if __name__ == "__main__":
    main()
