#!/usr/bin/env python3
"""League health, aged scorecards and a trade list for a save produced by scripts/two_season_league_probe.py.

Read-only on the save. Writes <out>/report_<label>.json, <out>/trades_<label>.json and <out>/trades_<label>.md.

  PYTHONPATH=src:scripts .venv/bin/python -u scripts/inputs_readiness_report.py \
      --save output/inputs-readiness/inputs_v1/saves/league.json --label inputs_v1 --out output/inputs-readiness
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import statistics
import tempfile
import time

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.calibration_targets import aggregate_from_results, compare, load_targets
from nba_gm_data.history_store import load_history_records
from nba_gm_data.save import (canonical_with_save, ensure_league_save_defaults, load_save, player_attribute_summary,
                              players_by_id_index, team_cap_summary)
from nba_gm_data.schema import to_plain
from nba_gm_data.sim import build_sim_indices, load_sim_context, load_sim_reference, sim_game_with_context

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "data/calibration/nba_2025_26_targets.json"
NEUTRAL_MINUTES = 24.0
TIERS = (72, 70, 65, 60)


def pct(values, q):
    values = sorted(values)
    if not values:
        return None
    pos = (len(values) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (pos - lo), 2)


def dist(values):
    values = [float(v) for v in values]
    if not values:
        return {"n": 0}
    return {"n": len(values), "mean": round(statistics.fmean(values), 2), "sd": round(statistics.pstdev(values), 2),
            "p10": pct(values, .1), "p50": pct(values, .5), "p90": pct(values, .9), "max": round(max(values), 2),
            "min": round(min(values), 2)}


def neutral_card(active, pid):
    player = players_by_id_index(active)[pid]
    saved = player.get("minutes_projection")
    player["minutes_projection"] = NEUTRAL_MINUTES
    try:
        s = player_attribute_summary(active, pid)
    finally:
        player["minutes_projection"] = saved
    return {k: round(float(s[k]), 1) for k in ("overall", "offense", "defense")}


def age_on(player, when: str):
    birth = player.get("birthdate")
    if birth:
        b = date.fromisoformat(str(birth)[:10])
        d = date.fromisoformat(when[:10])
        return round((d - b).days / 365.25, 1)
    age = player.get("display_age", player.get("age"))
    return round(float(age), 1) if age is not None else None


def season_of(day: str) -> str:
    year = int(day[:4]) - (1 if day[5:7] < "07" else 0)
    return f"{year}-{str(year + 1)[-2:]}"


def classify(player, generated_ids):
    year = str(player.get("draft_year") or "")
    if year and year >= "2027":
        if player.get("college_profile"):
            return "real college prospect"
        return "generated prospect"
    if player.get("id") in generated_ids:
        return "generated (other)"
    return "real player"


def league_view(active, save, label):
    generated_ids = {row.get("id") for row in save.get("generated_players", [])}
    retired = set(save.get("retired_player_ids") or [])
    free_agents = set(save.get("free_agent_player_ids") or [])
    teams = {t["id"]: t["abbrev"] for t in active.get("teams", [])}
    today = save["state"]["current_date"]
    rows = []
    for p in active.get("players", []):
        pid = p.get("id")
        if not pid or pid in retired or p.get("_inactive_player"):
            continue
        rostered = bool(p.get("team_id")) and pid not in free_agents and p.get("team_id") in teams
        card = neutral_card(active, pid)
        rows.append({"id": pid, "name": p.get("name"), "team": teams.get(p.get("team_id")) if rostered else "FA",
                     "rostered": rostered, "age": age_on(p, today), "kind": classify(p, generated_ids),
                     "draft_year": p.get("draft_year"), "pick": p.get("overall_pick") or p.get("draft_position"),
                     "minutes_projection": p.get("minutes_projection"), **card})
    rostered = sorted([r for r in rows if r["rostered"]], key=lambda r: -r["overall"])
    for rank, r in enumerate(rostered, 1):
        r["rank"] = rank
    tiers = {f"{t}+": sum(r["overall"] >= t for r in rostered) for t in TIERS}
    young = [r for r in rostered if r["age"] is not None and r["age"] <= 23.0][:10]
    top100 = rostered[:100]
    draftees = [r for r in rostered if str(r.get("draft_year") or "") >= "2027"]
    roster_sizes = Counter(r["team"] for r in rostered)
    payroll = {}
    for tid, abbrev in teams.items():
        payroll[abbrev] = team_cap_summary(active, save, tid)["salary_total_millions"]
    return {
        "label": label, "date": today, "rostered_players": len(rostered),
        "tiers": tiers,
        "overall": dist(r["overall"] for r in rostered),
        "top30": [{k: r[k] for k in ("rank", "name", "team", "age", "overall", "offense", "defense", "kind")} for r in rostered[:30]],
        "young_top10": [{k: r[k] for k in ("rank", "name", "team", "age", "overall", "kind", "draft_year", "pick")} for r in young],
        "top100_by_kind": dict(Counter(r["kind"] for r in top100)),
        "top100_age": dist(r["age"] for r in top100 if r["age"] is not None),
        "draftees": {
            "count_rostered": len(draftees),
            "by_kind": dict(Counter(r["kind"] for r in draftees)),
            "best": [{k: r[k] for k in ("rank", "name", "team", "age", "overall", "kind", "draft_year", "pick")} for r in draftees[:12]],
        },
        "roster_sizes": {"min": min(roster_sizes.values()), "max": max(roster_sizes.values()),
                         "by_team": dict(sorted(roster_sizes.items()))},
        "payroll_millions": {**dist(payroll.values()), "by_team": dict(sorted(payroll.items(), key=lambda kv: -kv[1]))},
        "_rows": rows,
    }


def minutes_view(stats_by_player, cards):
    """Minutes shape for one completed regular season: stars vs bench."""
    mpg = []
    for pid, s in stats_by_player.items():
        g = int(s.get("games") or 0)
        if g <= 0:
            continue
        mpg.append((pid, float(s.get("minutes") or 0) / g, g, float(s.get("minutes") or 0)))
    ranked = sorted([c for c in cards.items() if c[1].get("rostered")], key=lambda kv: -kv[1]["overall"])
    rank = {pid: i + 1 for i, (pid, _) in enumerate(ranked)}
    stars = [m for pid, m, g, t in mpg if rank.get(pid, 999) <= 30 and g >= 20]
    return {
        "players_30mpg_plus": sum(m >= 30 for _, m, g, _ in mpg if g >= 40),
        "players_34mpg_plus": sum(m >= 34 for _, m, g, _ in mpg if g >= 40),
        "players_1500_minutes": sum(t >= 1500 for *_, t in mpg),
        "max_mpg": round(max((m for _, m, g, _ in mpg if g >= 40), default=0), 1),
        "top30_players_mpg": dist(stars),
    }


def real_minutes_view(targets):
    rows = [p for p in targets["players"].values() if (p.get("games") or 0) > 0]
    return {
        "players_30mpg_plus": sum((p.get("minutes_per_game") or 0) >= 30 for p in rows if p["games"] >= 40),
        "players_34mpg_plus": sum((p.get("minutes_per_game") or 0) >= 34 for p in rows if p["games"] >= 40),
        "players_1500_minutes": sum((p.get("minutes") or 0) >= 1500 for p in rows),
        "max_mpg": max((p.get("minutes_per_game") or 0) for p in rows if p["games"] >= 40),
    }


PER36 = ("points", "rebounds", "assists", "steals", "blocks", "turnovers", "fga", "fg3a", "fta")


def per36_distribution(stats_by_player, min_minutes=1000):
    out = {}
    rows = [s for s in stats_by_player.values() if float(s.get("minutes") or 0) >= min_minutes]
    for key in PER36:
        out[key] = dist(36 * float(s.get(key) or 0) / float(s["minutes"]) for s in rows)
    ts = []
    for s in rows:
        att = float(s.get("fga") or 0) + 0.44 * float(s.get("fta") or 0)
        if att > 0:
            ts.append(float(s.get("points") or 0) / (2 * att))
    out["ts_pct"] = dist(ts)
    out["_n"] = len(rows)
    return out


def real_per36_distribution(targets, min_minutes=1000):
    out = {}
    rows = [p for p in targets["players"].values() if (p.get("minutes") or 0) >= min_minutes]
    for key in PER36:
        out[key] = dist(p.get(f"{key}_per36") for p in rows if p.get(f"{key}_per36") is not None)
    out["ts_pct"] = dist(p.get("ts_pct") for p in rows if p.get("ts_pct") is not None)
    out["_n"] = len(rows)
    return out


def standings_view(team_records):
    wins = [int(r.get("wins") or 0) for r in team_records.values()]
    diff = [(float(r.get("points_for") or 0) - float(r.get("points_against") or 0)) /
            max(1, int(r.get("wins") or 0) + int(r.get("losses") or 0)) for r in team_records.values()]
    return {"wins": dist(wins), "teams_55_plus": sum(w >= 55 for w in wins), "teams_25_or_less": sum(w <= 25 for w in wins),
            "point_diff_per_game": dist(diff)}


def real_standings_view():
    ref = load_sim_reference(ROOT)
    wins, games, diff = Counter(), Counter(), defaultdict(float)
    for g in ref["boxscores"]:
        if str(g.get("phase") or "regular") not in ("regular", "", "None"):
            continue
        hs, as_ = g.get("home_score"), g.get("away_score")
        if hs is None or as_ is None:
            continue
        h, a = g["home_team_id"], g["away_team_id"]
        games[h] += 1
        games[a] += 1
        diff[h] += hs - as_
        diff[a] += as_ - hs
        wins[h if hs > as_ else a] += 1
    scale = {t: 82 / games[t] for t in games}
    w = [wins[t] * scale[t] for t in games]
    return {"games_per_team": dist(games.values()), "wins_per_82": dist(w),
            "teams_55_plus": sum(x >= 55 for x in w), "teams_25_or_less": sum(x <= 25 for x in w),
            "point_diff_per_game": dist(diff[t] / games[t] for t in games)}


def as_played_rates(stats_by_player, team_records):
    team_games = sum(int(r.get("wins") or 0) + int(r.get("losses") or 0) for r in team_records.values())
    tot = Counter()
    for s in stats_by_player.values():
        for k in ("points", "fga", "fgm", "fg3a", "fg3m", "fta", "ftm", "rebounds", "assists", "steals", "blocks", "turnovers"):
            tot[k] += float(s.get(k) or 0)
    per = {k: round(v / team_games, 2) for k, v in tot.items()}
    per["ts_pct"] = round(tot["points"] / (2 * (tot["fga"] + 0.44 * tot["fta"])), 3)
    per["efg_pct"] = round((tot["fgm"] + 0.5 * tot["fg3m"]) / tot["fga"], 3)
    per["fg3a_rate"] = round(tot["fg3a"] / tot["fga"], 3)
    per["ft_rate"] = round(tot["fta"] / tot["fga"], 3)
    per["team_games"] = team_games
    return per


def real_rates(targets):
    lg = targets["league"]
    pace = lg["pace"]["mean"]
    out = {"points": lg["points_per_game"]["mean"]}
    for k, src in (("fga", "fga_per100"), ("fg3a", "fg3a_per100"), ("fta", "fta_per100"), ("assists", "ast_per100"),
                   ("steals", "stl_per100"), ("blocks", "blk_per100"), ("turnovers", "tov_per100")):
        out[k] = round(lg[src]["mean"] * pace / 100, 2)
    for k in ("ts_pct", "efg_pct", "fg3a_rate", "ft_rate"):
        out[k] = lg[k]["mean"]
    return out


def sandbox_scorecard(active, games=150, seed=1):
    targets = load_targets(TARGETS)
    context = load_sim_context(ROOT, canonical=active)
    picked = sorted([g for g in context["schedule"] if str(g.get("phase", "regular")) in ("regular", "None", "")],
                    key=lambda g: str(g.get("externalGameId")))
    step = max(1, len(picked) // games)
    picked = picked[::step][:games]
    t0 = time.time()
    results = [to_plain(sim_game_with_context(context, str(g["externalGameId"]), mode="sandbox-sim", seed=seed)) for g in picked]
    agg = aggregate_from_results(results)
    report = compare(agg["league_totals"], agg["player_lines"], targets, min_sim_games=3)
    league = [{k: m.get(k) for k in ("metric", "sim", "target", "z", "within_band")} for m in report["league"]]
    # Player-level: per-36 spread of the aged league's rotation players vs the real league's.
    lines = [pl for pl in agg["player_lines"].values() if (pl.get("minutes") or 0) >= 15 * 20 and (pl.get("games") or 0) >= 15]
    spread = {}
    for key in ("points_per36", "assists_per36", "rebounds_per36", "fg3a_per36", "fta_per36", "turnovers_per36", "ts_pct"):
        spread[key] = dist(pl[key] for pl in lines if pl.get(key) is not None)
    return {"games": len(results), "seconds": round(time.time() - t0, 1), "league": league,
            "summary": report["league_summary"], "player_per36_spread": spread, "rotation_players": len(lines)}


def real_player_spread(targets):
    rows = [p for p in targets["players"].values() if (p.get("minutes") or 0) >= 1000]
    return {k: dist(p[k] for p in rows if p.get(k) is not None)
            for k in ("points_per36", "assists_per36", "rebounds_per36", "fg3a_per36", "fta_per36", "turnovers_per36", "ts_pct")}


# ---------------------------------------------------------------- trades


def team_records_on(summaries, team_id, day):
    season = season_of(day)
    w = l = 0
    for g in summaries:
        d = str(g.get("date") or "")
        if not d or d >= day or season_of(d) != season or not str(g.get("game_id", "")).startswith("sim_game"):
            continue
        if team_id not in (g.get("home_team_id"), g.get("away_team_id")):
            continue
        home = g["home_team_id"] == team_id
        mine, theirs = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
        w += mine > theirs
        l += mine < theirs
    return f"{w}-{l}"


def contract_on(active, base_contracts, pid, day):
    season = season_of(day)
    contracts = [c for c in active.get("contracts", []) if c.get("player_id") == pid]
    contracts += [c for c in base_contracts.get(pid, [])]
    for c in contracts:
        seasons = c.get("seasons") or []
        if any(s.get("season") == season for s in seasons):
            rest = [s for s in seasons if s.get("season", "") >= season]
            return {"salary_millions_this_season": round(float(next(s for s in seasons if s.get("season") == season).get("salary") or 0) / 1e6, 2),
                    "years_left_incl_this": len(rest),
                    "options": [s.get("option_type") for s in rest if s.get("option_type")],
                    "kind": c.get("contract_type") or c.get("status")}
    return None


def season_minutes_before(logs_by_player, pid, team_id, day):
    season = season_of(day)
    rows = [r for r in logs_by_player.get(pid, []) if str(r.get("date", "")) < day and season_of(str(r.get("date"))) == season
            and r.get("team_id") == team_id]
    if not rows:
        return None
    m = sum(float(r.get("minutes") or 0) for r in rows)
    return {"games": len(rows), "mpg": round(m / len(rows), 1),
            "ppg": round(sum(float(r.get("points") or 0) for r in rows) / len(rows), 1)}


def trade_list(save_path, save, active, base, label):
    logs = load_history_records(save_path, save, "transaction_logs")
    by_id = {r.get("id"): r for r in logs}
    by_id.update({r.get("id"): r for r in save.get("transaction_logs", [])})
    trades = sorted([r for r in by_id.values() if r.get("transaction_type") == "trade"], key=lambda r: (r.get("date"), r.get("id")))
    plogs = defaultdict(list)
    for r in load_history_records(save_path, save, "player_game_logs"):
        plogs[r.get("player_id")].append(r)
    for r in save.get("player_game_logs", []):
        plogs[r.get("player_id")].append(r)
    summaries = save.get("game_result_summaries", [])
    players = players_by_id_index(active)
    base_players = {p["id"]: p for p in base.get("players", [])}
    base_contracts = defaultdict(list)
    for c in base.get("contracts", []):
        base_contracts[c.get("player_id")].append(c)
    values = {v.get("player_id"): v for v in active.get("player_asset_valuations", [])}
    teams = {t["id"]: t["abbrev"] for t in active.get("teams", [])}
    cards = {}
    out = []
    for t in trades:
        day = str(t.get("date"))[:10]
        team_ids = list(t.get("teams") or [])
        evals = {e.get("perspective_team_id"): e for e in t.get("evaluations", [])}
        sides = {}
        # from_assets leave teams[0] for teams[1]; to_assets go the other way.
        for side, giver in (("from_assets", 0), ("to_assets", 1)):
            giver_id = team_ids[giver] if len(team_ids) > giver else None
            assets = []
            for a in (t.get("assets") or {}).get(side, []):
                row = {k: v for k, v in a.items() if v is not None}
                if a.get("kind") == "player":
                    pid = a.get("id")
                    p = players.get(pid) or base_players.get(pid) or {}
                    if pid in players and pid not in cards:
                        cards[pid] = neutral_card(active, pid)
                    v = values.get(pid) or {}
                    row.update({
                        "age_at_trade": age_on(p, day) if p else None,
                        "contract_at_trade": contract_on(active, base_contracts, pid, day),
                        "season_before_trade": season_minutes_before(plogs, pid, giver_id, day),
                        "overall_end_of_run_neutral": (cards.get(pid) or {}).get("overall"),
                        "market_value_end_of_run": v.get("player_value"),
                        "on_court_value_end_of_run": v.get("on_court_value"),
                        "draft_year": p.get("draft_year"),
                    })
                assets.append(row)
            sides[teams.get(giver_id, giver_id)] = assets
        out.append({
            "date": day, "season": season_of(day), "teams": [teams.get(x, x) for x in team_ids],
            "sends": sides,
            "team_context": {teams.get(x, x): {"record_at_trade": team_records_on(summaries, x, day),
                                               "phase": (evals.get(x) or {}).get("window_phase")} for x in team_ids},
            "evaluations": [{k: e.get(k) for k in ("team_abbrev", "decision", "incoming_value", "outgoing_value", "net_value",
                                                   "acceptance_threshold", "strategic_adjustment", "notes", "decision_reasons")}
                            for e in t.get("evaluations", [])],
            "status": t.get("status"),
            "why": (t.get("trade_reasons") or {}).get("text"),
            "target_key": (t.get("trade_reasons") or {}).get("target_key"),
        })
    return out


def trade_shape(trades):
    shape = Counter()
    by_season = Counter(t["season"] for t in trades)
    flows = []
    for t in trades:
        players = [a for assets in t["sends"].values() for a in assets if a.get("kind") == "player"]
        picks = [a for assets in t["sends"].values() for a in assets if a.get("kind") != "player"]
        shape["with_players"] += bool(players)
        shape["picks_only"] += not players
        shape["players_moved"] += len(players)
        shape["picks_moved"] += len(picks)
        young = [p for p in players if (p.get("age_at_trade") or 99) <= 23]
        cheap = [p for p in players if ((p.get("contract_at_trade") or {}).get("salary_millions_this_season") or 99) <= 8]
        shape["young_players_moved"] += len(young)
        shape["cheap_players_moved"] += len(cheap)
        # Star-for-youth: one side sends a 72+ (end-of-run neutral) or $35M+ player and gets back only young/cheap players and picks.
        for team, assets in t["sends"].items():
            sent_star = any((a.get("overall_end_of_run_neutral") or 0) >= 70 or
                            ((a.get("contract_at_trade") or {}).get("salary_millions_this_season") or 0) >= 35
                            for a in assets if a.get("kind") == "player")
            back = [a for other, xs in t["sends"].items() if other != team for a in xs]
            back_players = [a for a in back if a.get("kind") == "player"]
            if sent_star and all((a.get("age_at_trade") or 99) <= 24 for a in back_players):
                shape["star_for_youth_or_picks"] += 1
        flows.append({"date": t["date"], "teams": t["teams"],
                      "summary": " | ".join(f"{team} sends " + ", ".join(
                          (f"{a['label']} ({a.get('age_at_trade')}y, ${(a.get('contract_at_trade') or {}).get('salary_millions_this_season', '?')}M)"
                           if a.get("kind") == "player" else a.get("label", a.get("id")))
                          for a in assets) for team, assets in t["sends"].items())})
    return {"count": len(trades), "by_season": dict(sorted(by_season.items())), **dict(shape)}


def trades_markdown(label, trades):
    lines = [f"# AI trades, {label} (seed 17, GSW hands-off, 2026-10-20 to 2028-11-01)", "",
             "Ages and contracts are at the trade date. 'Before' = that season's games for the sending team before the trade "
             "(only kept for the 2027-28 and 2028-29 seasons; 2026-27 game logs are purged by the save). Overall and market value "
             "are at the END of the run (2028-11-01), not at trade time; the trade-time value is the evaluation's incoming/outgoing total.", "",
             "| Date | Team (record, phase) | Sends | Receiving team's valuation (in / out / net) |", "|---|---|---|---|"]
    for t in trades:
        for team, assets in t["sends"].items():
            ctx = t["team_context"].get(team, {})
            parts = []
            for a in assets:
                if a.get("kind") == "player":
                    c = a.get("contract_at_trade") or {}
                    b = a.get("season_before_trade") or {}
                    parts.append(f"**{a.get('label')}** {a.get('age_at_trade')}y, ${c.get('salary_millions_this_season', '?')}M x{c.get('years_left_incl_this', '?')}"
                                 f", {('%s mpg' % b['mpg']) if b else ('proj %s min' % a.get('minutes_projection'))}"
                                 f", OVR(end) {a.get('overall_end_of_run_neutral')}")
                else:
                    text = str(a.get("label") or a.get("id")) + (f" [{a['protection_summary']}]" if a.get("protection_summary") else "")
                    text = " ".join(text.split()).replace("|", "/")
                    parts.append(text if len(text) <= 160 else text[:157] + "...")
            receiver = next((e for e in t["evaluations"] if e.get("team_abbrev") != team), {})
            lines.append(f"| {t['date']} | {team} ({ctx.get('record_at_trade')}, {ctx.get('phase')}) | {'; '.join(parts) or '-'} | "
                         f"{receiver.get('team_abbrev')}: {receiver.get('incoming_value')} / {receiver.get('outgoing_value')} / {receiver.get('net_value')} |")
        if t.get("why"):
            lines.append(f"| | Why | {t['why']} | |")
    return "\n".join(lines) + "\n"


def baseline_active(canonical, model):
    with tempfile.TemporaryDirectory() as tmp:
        result = dispatch_app_action("create_save", {"team": "GSW", "seed": 17, "save_name": "baseline", "ratings_model": model},
                                     root=ROOT, save_dir=Path(tmp), canonical=canonical)
        save = ensure_league_save_defaults(load_save(result["save_path"]), canonical)
        return canonical_with_save(canonical, save), save


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--save", type=Path, required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sim-games", type=int, default=1230)
    ap.add_argument("--skip-sandbox", action="store_true")
    args = ap.parse_args()
    canonical = load_app_canonical(ROOT)
    save = ensure_league_save_defaults(load_save(args.save), canonical)
    model = save["meta"].get("ratings_model", "legacy_traits")
    active = canonical_with_save(canonical, save)
    targets = load_targets(TARGETS)
    report = {"label": args.label, "model": model, "date": save["state"]["current_date"]}
    t0 = time.time()
    aged = league_view(active, save, "aged")
    base_active, base_save = baseline_active(canonical, model)
    opening = league_view(base_active, base_save, "opening")
    print(f"league views {time.time() - t0:.0f}s", flush=True)
    cards = {r["id"]: r for r in aged.pop("_rows")}
    opening.pop("_rows")
    report["opening"], report["aged"] = opening, aged
    history = {h["season"]: h for h in save.get("season_history", [])}
    report["seasons"] = {}
    for season, h in sorted(history.items()):
        stats = h.get("player_season_stats") or {}
        report["seasons"][season] = {
            "standings": standings_view(h.get("team_records") or {}),
            "as_played_per_team_game": as_played_rates(stats, h.get("team_records") or {}),
            "per36_1000min": per36_distribution(stats),
            "minutes": minutes_view(stats, cards),
            "champion": (h.get("playoff_state") or {}).get("champion_team_id"),
            "mvp": next((a.get("player_name") for a in h.get("awards", []) if a.get("award") == "MVP"), None),
        }
    report["real_2025_26"] = {"standings": real_standings_view(), "per_team_game": real_rates(targets),
                              "per36_1000min": real_per36_distribution(targets), "minutes": real_minutes_view(targets),
                              "player_per36_spread": real_player_spread(targets)}
    trades = trade_list(args.save, save, active, canonical, args.label)
    report["trades"] = trade_shape(trades)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"trades_{args.label}.json").write_text(json.dumps(trades, indent=1, default=str) + "\n")
    (args.out / f"trades_{args.label}.md").write_text(trades_markdown(args.label, trades))
    print(f"trades {len(trades)} {time.time() - t0:.0f}s", flush=True)
    if not args.skip_sandbox:
        report["sandbox_aged"] = sandbox_scorecard(active, args.sim_games)
        print(f"sandbox aged {time.time() - t0:.0f}s", flush=True)
        report["sandbox_opening"] = sandbox_scorecard(base_active, args.sim_games)
        print(f"sandbox opening {time.time() - t0:.0f}s", flush=True)
    (args.out / f"report_{args.label}.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({k: report[k] for k in ("label", "model", "date")}), flush=True)


if __name__ == "__main__":
    main()
