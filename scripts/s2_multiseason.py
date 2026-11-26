#!/usr/bin/env python3
"""S2-MULTISEASON: play several seasons of a fresh save with one game engine, then compare two such runs.

  run      Create a fresh save in --out and play --seasons seasons through the same app actions the GUI uses
           (scripts/ten_season_soak.py: regular season, play-in and playoffs, draft, free agency, offseason). The
           engine comes from --engine, which sets the research switch NBA_GM_SAVE_ENGINE for this process only.
           Each month of the regular season is timed; every game the save records is logged to games.jsonl.gz; the
           user team gets a fixed nine-man minutes plan each season, to check that targets are respected.
  compare  Read two or more run folders and write a season-by-season comparison (markdown + JSON).

  PYTHONPATH=src .venv/bin/python scripts/s2_multiseason.py run --engine stage2 --seasons 4 --out output/s2ms/stage2
  PYTHONPATH=src .venv/bin/python scripts/s2_multiseason.py compare output/s2ms/current output/s2ms/stage2 \
      --out output/s2ms/comparison.md
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import statistics
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Nine-man plan for the user team (starters first): what a GM might type in. Totals 240.
USER_PLAN = (36, 34, 32, 30, 28, 24, 22, 18, 16)


# --------------------------------------------------------------------------------------------------------- run ----

def compact_line(line: dict[str, Any]) -> list[Any]:
    return [line.get("player_id"), line.get("player_name"), line.get("team_abbrev"), round(float(line.get("minutes") or 0), 2),
            *(int(line.get(k) or 0) for k in ("points", "rebounds", "assists", "steals", "blocks", "turnovers", "fga", "fgm",
                                               "fg3a", "fg3m", "fta", "ftm", "personal_fouls", "offensive_rebounds")),
            bool(line.get("starter")), line.get("in_game_injury") or ""]


LINE_KEYS = ("player_id", "name", "team", "minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers",
             "fga", "fgm", "fg3a", "fg3m", "fta", "ftm", "personal_fouls", "offensive_rebounds", "starter", "injury")


def compact_game(kind: str, game: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    teams = {}
    for tl in result.get("team_lines") or []:
        teams[tl.get("team_id")] = {k: tl.get(k) for k in ("team_abbrev", "points", "fga", "fgm", "fg3a", "fg3m", "fta", "ftm",
                                                            "turnovers", "offensive_rebounds", "defensive_rebounds",
                                                            "assists", "steals", "blocks", "personal_fouls", "possessions",
                                                            "overtime_periods")}
    return {"kind": kind, "date": game.get("gameDate"), "game_id": result.get("game_id"),
            "home": result.get("home_team_id"), "away": result.get("away_team_id"),
            "home_score": result.get("home_score"), "away_score": result.get("away_score"),
            "possessions": result.get("possessions"), "teams": teams,
            "lines": [compact_line(line) for line in result.get("player_lines") or []]}


class GameLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.rows: list[dict[str, Any]] = []

    def flush(self) -> None:
        if not self.rows:
            return
        with gzip.open(self.path, "at", encoding="utf-8") as handle:
            for row in self.rows:
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
        self.rows = []


def install_game_logger(log: GameLog) -> None:
    from nba_gm_data import save as save_module
    regular, playoff = save_module.record_game_result, save_module.record_playoff_game_result
    seen: set[str] = set()

    def record_game_result(save, canonical, game, result):
        if str(result.get("game_id")) not in seen:
            seen.add(str(result.get("game_id")))
            log.rows.append(compact_game("regular", game, result))
        return regular(save, canonical, game, result)

    def record_playoff_game_result(save, game, result):
        if str(result.get("game_id")) not in seen:
            seen.add(str(result.get("game_id")))
            log.rows.append(compact_game("playoff", game, result))
        return playoff(save, game, result)

    save_module.record_game_result = record_game_result
    save_module.record_playoff_game_result = record_playoff_game_result


def run(args: argparse.Namespace) -> int:
    """Hands-off GM through every phase, with the maintained season driver the speed harness uses
    (overnight_market_health.select_action: trade-deadline confirmation, playoffs, lottery, draft, re-signing, free
    agency, training camp and rollover), plus the soak's audits at the end of each regular season and each rollover."""
    os.environ["NBA_GM_SAVE_ENGINE"] = args.engine
    import ten_season_soak as soak
    from overnight_market_health import marker, select_action
    from nba_gm_data import save as save_module
    from nba_gm_data.save import canonical_with_save, team_rotation_projection

    # The GUI's lottery reveal draws from system randomness on purpose; pin it so runs repeat (harness only, as in
    # check_month_parity.py).
    save_module.lottery_seed = lambda seed=None: int(seed) if seed is not None else 20270622
    # This runner writes its own season payloads; the soak's markdown report expects its own shape, so skip it.
    soak.markdown_report = lambda payload: "(see the s2_multiseason compare report)\n"
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "games.jsonl.gz").unlink(missing_ok=True)
    log = GameLog(out / "games.jsonl.gz")
    install_game_logger(log)
    timings: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    crashes: list[dict[str, Any]] = []
    runner = soak.SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(out), seed=args.seed, team=args.team,
                                                save_name=f"s2ms_{args.engine}", checkpoint_days=31, resume=False,
                                                seasons=args.seasons))

    def write_meta() -> None:
        log.flush()
        (out / "run_meta.json").write_text(json.dumps({
            "engine": args.engine, "seed": args.seed, "team": args.team, "seasons": args.seasons,
            "timings": timings, "user_plans": plans, "crashes": crashes,
            "runtime_seconds": round(time.monotonic() - runner.started, 1)}, indent=1) + "\n")

    def set_user_plan(season: str) -> None:
        save = runner.load()
        active = canonical_with_save(runner.canonical, save)
        team_id = save["meta"]["user_team_id"]
        projection = team_rotation_projection(active, save, team_id, integer=True)
        lineup = (save.get("starting_lineups") or {}).get(team_id) or []
        ordered = [pid for pid in lineup if pid in projection]
        ordered += [pid for pid, _ in sorted(projection.items(), key=lambda kv: -kv[1]) if pid not in ordered]
        chosen = ordered[:len(USER_PLAN)]
        if len(chosen) < len(USER_PLAN):
            plans.append({"season": season, "status": "skipped", "reason": "fewer than nine players", "plan": {}})
            return
        minutes = {pid: m for pid, m in zip(chosen, USER_PLAN)}
        minutes.update({pid: 0 for pid in projection if pid not in minutes})
        result = runner.action("set_rotation_minutes", save_path=runner.payload["save_path"], team=args.team,
                               minutes=minutes, locked_player_ids=chosen)
        plans.append({"season": season, "status": result.get("status"), "reason": result.get("reason"), "plan": minutes})

    until = f"{2026 + args.seasons + 1}-06-30"
    try:
        runner.create()
        seasons_done = 0
        season = str(runner.load()["meta"]["season"])
        start_save = runner.load()
        start_audit = soak.audit_snapshot(runner.canonical, start_save, f"{season} start")
        regular_audit: dict[str, Any] | None = None
        stats: dict[str, Any] = {}
        champion: str | None = None
        planned: set[str] = set()
        print(f"[{args.engine}] {season} starts", flush=True)
        while seasons_done < args.seasons:
            runner.resolve_user_staff_retention()
            runner.resolve_user_roster_cutdown()
            before = runner.load()
            phase = before["state"]["phase"]
            if phase in {"preseason", "regular_season"} and season not in planned:
                planned.add(season)
                set_user_plan(season)
                before = runner.load()
            if phase in {"play_in", "playoffs"} and regular_audit is None:
                regular_audit = soak.audit_snapshot(runner.canonical, before, f"{season} regular season complete")
                stats = soak.regular_season_stats(before)
                runner.snapshot_save(f"season_{seasons_done + 1:02d}_regular_end.json")
            action, payload = select_action(before, until)
            payload = {**payload, "seed": args.seed}
            if "team" in payload:
                payload["team"] = args.team
            games_before = len((before.get("schedule_state") or {}).get("simulated_game_ids") or [])
            started = time.monotonic()
            runner.action(action, save_path=runner.payload["save_path"], **payload)
            seconds = time.monotonic() - started
            after = runner.load()
            if marker(before) == marker(after):
                raise RuntimeError(f"No calendar/phase progress: {action} {payload} at {before['state']}")
            champion_id = (after.get("playoff_state") or {}).get("champion_team_id")
            if champion_id:
                champion = next((t["abbrev"] for t in canonical_with_save(runner.canonical, after)["teams"]
                                 if t["id"] == champion_id), champion_id)
            games = len((after.get("schedule_state") or {}).get("simulated_game_ids") or []) - games_before
            timings.append({"season": season, "phase": phase, "action": action,
                            "payload": {k: v for k, v in payload.items() if k != "seed"},
                            "from": before["state"]["current_date"], "to": after["state"]["current_date"],
                            "games": games, "seconds": round(seconds, 2)})
            print(f"   {phase:15s} {action:20s} {before['state']['current_date']} -> {after['state']['current_date']}"
                  f" {games:4d} games {seconds:6.1f}s", flush=True)
            write_meta()
            if str(after["meta"]["season"]) != season:
                # Rollover committed: record the finished season like the soak does.
                soak_index = seasons_done
                end_audit = soak.audit_snapshot(runner.canonical, after, f"{season} rollover")
                end_active = canonical_with_save(runner.canonical, after)
                deltas = soak.development_deltas(start_audit["overall_by_player"], end_audit["overall_by_player"],
                                                 start_audit["age_by_player"], end_active, after)
                awards = {str(row.get("award")): str(row.get("player_name") or row.get("player_id") or "-")
                          for row in after.get("league_awards", []) if str(row.get("season")) == season}
                regular_audit = regular_audit or {}
                runner.payload["seasons"].append({
                    "season": season, "champion": champion, "stats": stats, "awards": awards,
                    "rookies": soak.rookie_snapshot(runner.canonical, after, str(int(season[:4]) + 1)),
                    "transactions": soak.transaction_counts(after, season),
                    "injuries": regular_audit.get("injuries"), "start_talent": start_audit["talent"],
                    "end_talent": end_audit["talent"], "development_deltas": deltas,
                    "overall_start": start_audit["overall_by_player"], "overall_end": end_audit["overall_by_player"],
                    "errors": sorted(set(regular_audit.get("errors", []) + end_audit["errors"])),
                    "warnings": sorted(set(soak.non_cap_warnings(regular_audit) if regular_audit else [])
                                       | set(soak.non_cap_warnings(end_audit)))})
                for message in regular_audit.get("errors", []) + end_audit["errors"]:
                    runner.payload["errors"].append(f"{season}: {message}")
                runner.payload["errors"] = sorted(set(runner.payload["errors"]))
                runner.checkpoint()
                runner.snapshot_save(f"season_{soak_index + 1:02d}_rollover.json")
                seasons_done += 1
                print(f"[{args.engine}] {season} done: champion {champion}, errors {len(end_audit['errors'])}", flush=True)
                season = str(after["meta"]["season"])
                start_save, start_audit = after, end_audit
                regular_audit, stats, champion = None, {}, None
                from nba_gm_data.utils import clear_utility_caches
                clear_utility_caches()
    except Exception as exc:  # noqa: BLE001 - a crash is a finding; record it and stop
        state = None
        try:
            state = runner.load().get("state")
        except Exception:  # noqa: BLE001
            pass
        crashes.append({"error": repr(exc), "traceback": traceback.format_exc()[-4000:], "state": state})
        print(traceback.format_exc(), flush=True)
    finally:
        runner.checkpoint()
        write_meta()
    return 1 if crashes else 0


# ----------------------------------------------------------------------------------------------------- compare ----

def season_of(day: str) -> str:
    year = int(day[:4]) - (1 if day[5:7] < "07" else 0)
    return f"{year}-{str(year + 1)[-2:]}"


def load_games(folder: Path) -> list[dict[str, Any]]:
    path = folder / "games.jsonl.gz"
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(row) for row in handle if row.strip()]


def mean(values) -> float:
    values = list(values)
    return statistics.fmean(values) if values else float("nan")


def league_rates(games: list[dict[str, Any]]) -> dict[str, float]:
    tot: Counter[str] = Counter()
    n = 0
    ot = 0
    margins = []
    for g in games:
        poss = float(g.get("possessions") or 0)
        periods = max([int(t.get("overtime_periods") or 0) for t in g["teams"].values()] or [0])
        ot += periods > 0
        margins.append(abs(int(g["home_score"]) - int(g["away_score"])))
        for t in g["teams"].values():
            n += 1
            for k in ("points", "fga", "fgm", "fg3a", "fg3m", "fta", "ftm", "turnovers", "offensive_rebounds",
                      "defensive_rebounds", "assists", "steals", "blocks", "personal_fouls"):
                tot[k] += float(t.get(k) or 0)
            tot["poss"] += float(t.get("possessions") or poss)
            # pace per 48 minutes: possessions scaled by regulation share of the game's length
            tot["pace"] += float(t.get("possessions") or poss) * 48.0 / (48.0 + 5.0 * periods)
    if not n:
        return {}
    per100 = lambda k: 100.0 * tot[k] / tot["poss"]  # noqa: E731
    return {
        "teams_games": n, "points_per_game": tot["points"] / n, "pace": tot["pace"] / n,
        "off_rating": per100("points"), "fga_per100": per100("fga"), "fg3a_per100": per100("fg3a"),
        "fg3a_rate": tot["fg3a"] / tot["fga"], "fta_per100": per100("fta"), "ft_rate": tot["fta"] / tot["fga"],
        "efg_pct": (tot["fgm"] + .5 * tot["fg3m"]) / tot["fga"],
        "ts_pct": tot["points"] / (2 * (tot["fga"] + .44 * tot["fta"])),
        "tov_per100": per100("turnovers"), "ast_per100": per100("assists"), "stl_per100": per100("steals"),
        "blk_per100": per100("blocks"), "pf_per100": per100("personal_fouls"),
        "orb_pct": tot["offensive_rebounds"] / max(1.0, tot["offensive_rebounds"] + tot["defensive_rebounds"]) * 100,
        "overtime_share": ot / max(1, n // 2), "avg_abs_margin": mean(margins),
        "close_1_3": sum(1 for m in margins if 1 <= m <= 3) / max(1, len(margins)),
        "blowouts_20": sum(1 for m in margins if m >= 20) / max(1, len(margins)),
    }


def team_spread(games: list[dict[str, Any]]) -> dict[str, Any]:
    wins: Counter[str] = Counter()
    played: Counter[str] = Counter()
    margin: Counter[str] = Counter()
    for g in games:
        h, a = g["home"], g["away"]
        diff = int(g["home_score"]) - int(g["away_score"])
        played[h] += 1
        played[a] += 1
        margin[h] += diff
        margin[a] -= diff
        wins[h if diff > 0 else a] += 1
    win_list = sorted(wins.get(t, 0) * 82.0 / played[t] for t in played)
    net = sorted(margin[t] / played[t] for t in played)
    home_wins = sum(1 for g in games if int(g["home_score"]) > int(g["away_score"]))
    return {"best_wins": max(win_list), "worst_wins": min(win_list), "wins_sd": statistics.pstdev(win_list),
            "teams_50_plus": sum(1 for w in win_list if w >= 50), "teams_25_minus": sum(1 for w in win_list if w <= 25),
            "net_sd": statistics.pstdev(net), "best_net": max(net), "worst_net": min(net),
            "home_win_pct": home_wins / max(1, len(games))}


def player_seasons(games: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for g in games:
        for raw in g["lines"]:
            line = dict(zip(LINE_KEYS, raw))
            row = out.setdefault(line["player_id"], {"name": line["name"], "team": line["team"], "games": 0,
                                                     "starts": 0, "max_minutes": 0.0, "max_points": 0,
                                                     **{k: 0.0 for k in LINE_KEYS[3:18]}})
            row["games"] += 1
            row["starts"] += bool(line["starter"])
            row["team"] = line["team"]
            row["max_minutes"] = max(row["max_minutes"], float(line["minutes"]))
            row["max_points"] = max(row["max_points"], int(line["points"]))
            for k in LINE_KEYS[3:18]:
                row[k] += float(line[k] or 0)
    return out


def leaders(players: dict[str, dict[str, Any]], key: str, n: int = 5, min_games: int = 58) -> list[str]:
    rows = [(p[key] / p["games"], p) for p in players.values() if p["games"] >= min_games]
    rows.sort(key=lambda r: -r[0])
    return [f"{p['name']} ({p['team']}) {v:.1f}" for v, p in rows[:n]]


def oddities(games: list[dict[str, Any]], players: dict[str, dict[str, Any]]) -> list[str]:
    notes = []
    for g in games:
        for raw in g["lines"]:
            line = dict(zip(LINE_KEYS, raw))
            if line["points"] >= 60 or line["rebounds"] >= 28 or line["assists"] >= 22 or line["minutes"] > 53 \
                    or line["blocks"] >= 10 or line["steals"] >= 9 or line["fg3m"] >= 14:
                notes.append(f"{g['date']} {line['name']} ({line['team']}): {line['minutes']:.0f} min, {line['points']} pts, "
                             f"{line['rebounds']} reb, {line['assists']} ast, {line['steals']} stl, {line['blocks']} blk, "
                             f"{line['fg3m']} threes")
            if line["fgm"] > line["fga"] or line["fg3m"] > line["fg3a"] or line["ftm"] > line["fta"] \
                    or line["fg3a"] > line["fga"] or line["personal_fouls"] > 6:
                notes.append(f"{g['date']} {line['name']}: impossible line {raw}")
            if line["points"] != 2 * line["fgm"] + line["fg3m"] + line["ftm"]:
                notes.append(f"{g['date']} {line['name']}: points do not add up {raw}")
        for t in g["teams"].values():
            pts = int(t.get("points") or 0)
            if pts < 75 or pts > 155:
                notes.append(f"{g['date']} {t.get('team_abbrev')} scored {pts}")
    for p in players.values():
        if p["games"] >= 20:
            mpg = p["minutes"] / p["games"]
            if mpg > 40.0:
                notes.append(f"{p['name']} ({p['team']}) averaged {mpg:.1f} minutes over {p['games']} games")
    return notes


def minutes_profile(players: dict[str, dict[str, Any]], team_games: int) -> dict[str, Any]:
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in players.values():
        by_team[p["team"]].append(p)
    top1, top3, rot8 = [], [], []
    for rows in by_team.values():
        mpg = sorted((p["minutes"] / p["games"] for p in rows if p["games"] >= 30), reverse=True)
        if len(mpg) >= 8:
            top1.append(mpg[0])
            top3.append(mean(mpg[:3]))
            rot8.append(mpg[7])
    eligible = [p for p in players.values() if p["games"] >= 20]
    return {"team_top_mpg": mean(top1), "team_top3_mpg": mean(top3), "team_8th_mpg": mean(rot8),
            "players_36_plus_mpg": sum(1 for p in eligible if p["minutes"] / p["games"] >= 36),
            "players_34_plus_mpg": sum(1 for p in eligible if p["minutes"] / p["games"] >= 34),
            "players_30_plus_mpg": sum(1 for p in eligible if p["minutes"] / p["games"] >= 30),
            "players_70_plus_games": sum(1 for p in players.values() if p["games"] >= 70),
            "max_mpg": max((p["minutes"] / p["games"] for p in eligible), default=0.0)}


def star_minutes(players: dict[str, dict[str, Any]], names: list[str]) -> list[str]:
    by_name = {p["name"]: p for p in players.values()}
    out = []
    for name in names:
        p = by_name.get(name)
        if p:
            out.append(f"{name} {p['games']} gp, {p['minutes'] / p['games']:.1f} mpg, {p['points'] / p['games']:.1f} ppg")
    return out


def user_plan_check(games: list[dict[str, Any]], plan: dict[str, int], team_abbrev: str) -> list[dict[str, Any]]:
    rows = []
    mins: dict[str, list[float]] = defaultdict(list)
    names = {}
    for g in games:
        for raw in g["lines"]:
            line = dict(zip(LINE_KEYS, raw))
            if line["team"] == team_abbrev and line["player_id"] in plan:
                mins[line["player_id"]].append(float(line["minutes"]))
                names[line["player_id"]] = line["name"]
    for pid, target in sorted(plan.items(), key=lambda kv: -kv[1]):
        if target <= 0:
            continue
        values = mins.get(pid) or []
        # Games played without an injury exit, so a night cut short does not count against the plan.
        rows.append({"player": names.get(pid, pid), "target": target, "games": len(values),
                     "avg": mean(values) if values else float("nan"),
                     "sd": statistics.pstdev(values) if len(values) > 1 else float("nan")})
    return rows


def injuries(save: dict[str, Any], season: str) -> dict[str, Any]:
    events = [row for row in save.get("injury_events", []) if season_of(str(row.get("start_date") or "1900-01-01")) == season]
    missed = [float(row.get("expected_games_missed") or 0) for row in events]
    return {"events": len(events), "players": len({row.get("player_id") for row in events}),
            "expected_games_missed": round(sum(missed), 0),
            "long_41_plus": sum(1 for m in missed if m >= 41),
            "in_game_exits": None}


def read_save(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    from nba_gm_data.save import load_save
    return load_save(path)


def real_reference() -> dict[str, Any]:
    """Real 2025-26 player references from the calibration targets (players with 500+ minutes, or 20+ games at 15+)."""
    rows = list(json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())["players"].values())
    el = [p for p in rows if p["games"] >= 20]
    keys = {"points": "points_per_game", "rebounds": "rebounds_per_game", "assists": "assists_per_game",
            "steals": "steals_per_game", "blocks": "blocks_per_game"}
    leaders_real = {}
    for key, col in keys.items():
        top = sorted((p for p in rows if p["games"] >= 58), key=lambda p: -p[col])[:5]
        leaders_real[key] = [f"{p['name']} {p[col]:.1f}" for p in top]
    return {"minutes": {"players_36_plus_mpg": sum(p["minutes_per_game"] >= 36 for p in el),
                        "players_34_plus_mpg": sum(p["minutes_per_game"] >= 34 for p in el),
                        "players_30_plus_mpg": sum(p["minutes_per_game"] >= 30 for p in el),
                        "players_70_plus_games": sum(p["games"] >= 70 for p in rows),
                        "max_mpg": max(p["minutes_per_game"] for p in el)},
            "leaders": leaders_real}


def compare(args: argparse.Namespace) -> int:
    targets = json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())["league"]
    real_ref = real_reference()
    runs = []
    for folder in args.runs:
        folder = Path(folder).resolve()
        meta = json.loads((folder / "run_meta.json").read_text())
        audit = json.loads((folder / "soak_audit.json").read_text()) if (folder / "soak_audit.json").exists() else {}
        games = load_games(folder)
        runs.append({"folder": folder, "meta": meta, "audit": audit, "games": games, "label": meta["engine"]})
    seasons = sorted({season_of(g["date"]) for r in runs for g in r["games"]})
    lines: list[str] = []
    data: dict[str, Any] = {"seasons": {}}
    w = lines.append
    labels = [r["label"] for r in runs]
    w("# S2-MULTISEASON comparison\n")
    w("Runs: " + ", ".join(f"{r['label']} (seed {r['meta']['seed']}, {r['meta']['team']}, "
                            f"{len({season_of(g['date']) for g in r['games']})} seasons logged, "
                            f"{r['meta'].get('runtime_seconds', 0) / 60:.0f} min)" for r in runs) + "\n")
    for r in runs:
        if r["meta"].get("crashes"):
            w(f"**{r['label']} crashed:** {r['meta']['crashes'][0]['error']}\n")
    rate_keys = [("points_per_game", "Points per team game", "{:.1f}"), ("pace", "Pace (possessions per 48)", "{:.1f}"),
                 ("off_rating", "Points per 100 possessions", "{:.1f}"), ("fg3a_rate", "Share of shots that are threes", "{:.3f}"),
                 ("fg3a_per100", "Three-point tries per 100", "{:.1f}"), ("ft_rate", "Free-throw tries per shot", "{:.3f}"),
                 ("fta_per100", "Free-throw tries per 100", "{:.1f}"), ("efg_pct", "Effective shooting", "{:.3f}"),
                 ("ts_pct", "True shooting", "{:.3f}"), ("tov_per100", "Turnovers per 100", "{:.1f}"),
                 ("ast_per100", "Assists per 100", "{:.1f}"), ("stl_per100", "Steals per 100", "{:.1f}"),
                 ("blk_per100", "Blocks per 100", "{:.1f}"), ("pf_per100", "Fouls per 100", "{:.1f}"),
                 ("orb_pct", "Offensive rebound %", "{:.1f}"), ("overtime_share", "Games to overtime", "{:.3f}"),
                 ("avg_abs_margin", "Average final margin", "{:.1f}"), ("close_1_3", "Finishes by 1-3 points", "{:.3f}"),
                 ("blowouts_20", "Finishes by 20+", "{:.3f}")]
    real_rows = [{"home": g["home_team_id"], "away": g["away_team_id"], "home_score": g["home_score"],
                  "away_score": g["away_score"]}
                 for g in json.loads((ROOT / "data/research/game_boxscores_2025_26.json").read_text())["games"]
                 if g.get("phase") == "regular" and g.get("status") == "STATUS_FINAL"]
    real_spread = team_spread(real_rows)
    real_margins = [abs(int(g["home_score"]) - int(g["away_score"])) for g in real_rows]
    # Overtime share: 4.4% (S2-FINISHES, real play-by-play); margins from the real 2025-26 box scores.
    real_extra = {"overtime_share": .044, "avg_abs_margin": mean(real_margins),
                  "close_1_3": sum(1 for m in real_margins if 1 <= m <= 3) / len(real_margins),
                  "blowouts_20": sum(1 for m in real_margins if m >= 20) / len(real_margins)}
    for season in seasons:
        w(f"\n## {season}\n")
        per = {}
        for r in runs:
            sg = [g for g in r["games"] if season_of(g["date"]) == season]
            reg = [g for g in sg if g["kind"] == "regular"]
            po = [g for g in sg if g["kind"] == "playoff"]
            players = player_seasons(reg)
            per[r["label"]] = {"reg": reg, "po": po, "rates": league_rates(reg), "spread": team_spread(reg) if reg else {},
                               "players": players, "minutes": minutes_profile(players, len(reg))}
        data["seasons"][season] = {label: {k: v for k, v in item.items() if k in ("rates", "spread", "minutes")}
                                   for label, item in per.items()}
        w("### League play (regular season)\n")
        w("| | " + " | ".join(labels) + " | Real 2025-26 |")
        w("|---|" + "---|" * (len(labels) + 1))
        w("| Games | " + " | ".join(str(len(per[l]["reg"])) for l in labels) + " | 1230 |")
        for key, name, fmt in rate_keys:
            real = targets.get(key, {}).get("mean") if key in targets else real_extra.get(key)
            w(f"| {name} | " + " | ".join(fmt.format(per[l]["rates"].get(key, float('nan'))) for l in labels)
              + f" | {fmt.format(real) if real is not None else '-'} |")
        w("\n### Team records and margins\n")
        w("| | " + " | ".join(labels) + " | Real 2025-26 |")
        w("|---|" + "---|" * (len(labels) + 1))
        for key, name, fmt in [("best_wins", "Best record (wins per 82)", "{:.0f}"), ("worst_wins", "Worst record", "{:.0f}"),
                               ("wins_sd", "Spread of wins (std. dev.)", "{:.1f}"), ("teams_50_plus", "Teams with 50+ wins", "{}"),
                               ("teams_25_minus", "Teams with 25 or fewer", "{}"), ("net_sd", "Spread of point margin per game", "{:.2f}"),
                               ("best_net", "Best point margin per game", "{:+.1f}"), ("worst_net", "Worst point margin per game", "{:+.1f}"),
                               ("home_win_pct", "Home teams' win share", "{:.3f}")]:
            w(f"| {name} | " + " | ".join(fmt.format(per[l]["spread"].get(key, float('nan'))) for l in labels)
              + f" | {fmt.format(real_spread[key])} |")
        w("")
        w("### Minutes\n")
        w("| | " + " | ".join(labels) + " | Real 2025-26 |")
        w("|---|" + "---|" * (len(labels) + 1))
        for key, name, fmt in [("team_top_mpg", "Each team's top minutes (avg)", "{:.1f}"),
                               ("team_top3_mpg", "Each team's top three (avg)", "{:.1f}"),
                               ("team_8th_mpg", "Each team's 8th man", "{:.1f}"),
                               ("players_36_plus_mpg", "Players at 36+ minutes (20+ games)", "{}"),
                               ("players_34_plus_mpg", "Players at 34+ minutes (20+ games)", "{}"),
                               ("players_30_plus_mpg", "Players at 30+ minutes (20+ games)", "{}"),
                               ("players_70_plus_games", "Players with 70+ games", "{}"),
                               ("max_mpg", "Highest minutes per game", "{:.1f}")]:
            ref = real_ref["minutes"].get(key)
            w(f"| {name} | " + " | ".join(fmt.format(per[l]["minutes"].get(key, float('nan'))) for l in labels)
              + f" | {fmt.format(ref) if ref is not None else '-'} |")
        stars = ["Nikola Jokić", "Shai Gilgeous-Alexander", "Luka Dončić", "Giannis Antetokounmpo", "Anthony Edwards",
                 "Victor Wembanyama", "Jayson Tatum", "Stephen Curry", "LeBron James", "Tyrese Haliburton"]
        w("### Stars\n")
        for l in labels:
            w(f"- **{l}:** " + "; ".join(star_minutes(per[l]["players"], stars)))
        w("\n### Stat leaders (58+ games)\n")
        for key, name in [("points", "Points"), ("rebounds", "Rebounds"), ("assists", "Assists"), ("steals", "Steals"),
                          ("blocks", "Blocks"), ("fg3m", "Threes made")]:
            for l in labels:
                w(f"- {name}, {l}: " + "; ".join(leaders(per[l]["players"], key)))
            if key in real_ref["leaders"]:
                w(f"- {name}, real 2025-26: " + "; ".join(real_ref["leaders"][key]))
        w("\n### Lines that look impossible or extreme\n")
        for l in labels:
            notes = oddities(per[l]["reg"] + per[l]["po"], per[l]["players"])
            w(f"- **{l}** ({len(notes)}): " + ("; ".join(notes[:12]) if notes else "none"))
        w("\n### User team's minutes plan (MIA, nine-man plan set at the start of the season)\n")
        for r in runs:
            plan = next((p for p in r["meta"].get("user_plans", []) if p["season"] == season), None)
            if not plan or plan.get("status") not in ("saved", "updated", "ok", None) and not plan.get("plan"):
                w(f"- {r['label']}: no plan ({plan})")
                continue
            rows = user_plan_check(per[r["label"]]["reg"], plan["plan"], r["meta"]["team"])
            w(f"- {r['label']} (plan status {plan.get('status')}): " + "; ".join(
                f"{row['player']} target {row['target']} -> {row['avg']:.1f} (sd {row['sd']:.1f}, {row['games']} gp)" for row in rows))
        w("\n### Playoffs\n")
        for r in runs:
            season_payload = next((s for s in r["audit"].get("seasons", []) if s.get("season") == season), {})
            po = per[r["label"]]["po"]
            po_rates = league_rates(po)
            w(f"- {r['label']}: champion {season_payload.get('champion') or '-'}; {len(po)} play-in/playoff games; "
              f"{po_rates.get('points_per_game', float('nan')):.1f} points a team, pace {po_rates.get('pace', float('nan')):.1f}; "
              f"awards {season_payload.get('awards') or '-'}")
        w("\n### Injuries (regular season audit)\n")
        for r in runs:
            season_payload = next((s for s in r["audit"].get("seasons", []) if s.get("season") == season), {})
            inj = season_payload.get("injuries") or {}
            exits = sum(1 for g in per[r["label"]]["reg"] for raw in g["lines"] if raw[-1])
            w(f"- {r['label']}: {inj.get('events_in_season', '-')} injuries to {inj.get('unique_players', '-')} players, "
              f"{inj.get('expected_games_missed_total', '-')} expected games missed, bands {inj.get('severity_bands', '-')}; "
              f"{exits} players left a game hurt")
        w("\n### Development and ratings\n")
        for r in runs:
            season_payload = next((s for s in r["audit"].get("seasons", []) if s.get("season") == season), {})
            dev = season_payload.get("development_deltas") or {}
            end = (season_payload.get("end_talent") or {}).get("overall") or {}
            counts = (season_payload.get("end_talent") or {}).get("counts") or {}
            w(f"- {r['label']}: rostered overall mean {end.get('mean', '-')} (p90 {end.get('p90', '-')}, max {end.get('max', '-')}), "
              f"80+ {counts.get('80', '-')}, 90+ {counts.get('90', '-')}; change by age: "
              + ", ".join(f"{k} {v.get('mean', 0):+.2f}" for k, v in dev.items() if k in ("22_and_under", "23_to_27", "28_to_31", "32_plus")))
        w("\n### Speed (AI front offices included)\n")
        w("| | " + " | ".join(labels) + " |")
        w("|---|" + "---|" * len(labels))
        rows = defaultdict(dict)
        for r in runs:
            steps = [t for t in r["meta"].get("timings", []) if t["season"] == season]
            reg = [t for t in steps if t["phase"] in ("preseason", "regular_season") and t["action"] == "advance_save"
                   and t["games"] > 0]
            days = sum((date.fromisoformat(t["to"]) - date.fromisoformat(t["from"])).days for t in reg)
            secs = sum(t["seconds"] for t in reg)
            month_steps = [t for t in reg if (date.fromisoformat(t["to"]) - date.fromisoformat(t["from"])).days >= 20]
            rows["Regular season: seconds per 30 days"][r["label"]] = f"{30 * secs / max(1, days):.1f}"
            rows["Slowest month-long step"][r["label"]] = (
                max((f"{t['seconds']:.0f}s ({t['from']} to {t['to']}, {t['games']} games)" for t in month_steps),
                    key=lambda text: float(text.split("s")[0])) if month_steps else "-")
            rows["Seconds per regular-season game"][r["label"]] = f"{secs / max(1, sum(t['games'] for t in reg)):.3f}"
            for phase_name in ("play_in", "playoffs", "draft_lottery", "draft", "re_signing", "free_agency", "training_camp"):
                phase_steps = [t for t in steps if t["phase"] == phase_name]
                if phase_steps:
                    rows[f"{phase_name.replace('_', ' ')} (total)"][r["label"]] = f"{sum(t['seconds'] for t in phase_steps):.0f}s"
            rows["Whole season (total)"][r["label"]] = f"{sum(t['seconds'] for t in steps) / 60:.1f} min"
        for name, cells in rows.items():
            w(f"| {name} | " + " | ".join(cells.get(l, "-") for l in labels) + " |")
    w("\n## Errors and warnings from the soak audit\n")
    for r in runs:
        w(f"- **{r['label']}**: {len(r['audit'].get('errors', []))} errors, {len(r['audit'].get('warnings', []))} warnings. "
          + "; ".join(r["audit"].get("errors", [])[:8]))
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path(args.out).with_suffix(".json").write_text(json.dumps(data, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


def speed(args: argparse.Namespace) -> int:
    """Clean speed check: from each season's opening save of a finished run (a fresh save for season 1, the rollover
    saves after that), play Oct 20 -> Nov 30 with each engine, one after another, and report seconds per 30 days.
    Same league state for both engines; run it on a quiet machine."""
    import shutil
    import subprocess
    run_dir = Path(args.run).resolve()
    work = Path(args.out).resolve()
    work.mkdir(parents=True, exist_ok=True)
    starts = [None] + sorted((run_dir / "phase_saves").glob("season_*_rollover.json"))
    rows = []
    for index, start in enumerate(starts[:args.seasons]):
        for engine in args.engines:
            folder = work / f"s{index + 1}_{engine}"
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(parents=True)
            if start is not None:
                save = json.loads(start.read_text())
                db = (save.get("history_store") or {}).get("path")
                shutil.copy2(start, folder / start.name)
                if db:
                    shutil.copy2(start.parent / db, folder / db)
                for entry in ((save.get("season_archive") or {}).get("seasons") or {}).values():
                    shutil.copy2(start.parent / entry["file"], folder / entry["file"])
                save_path = folder / start.name
            else:
                save_path = None
            cmd = [sys.executable, __file__, "speed-one", "--engine", engine, "--folder", str(folder),
                   "--seed", str(args.seed), "--team", args.team] + (["--save", str(save_path)] if save_path else [])
            out = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "NBA_GM_SAVE_ENGINE": engine})
            line = (out.stdout.strip().splitlines() or ["{}"])[-1]
            try:
                row = json.loads(line)
            except ValueError:
                row = {}
            if "seconds" not in row:
                row = {"error": (out.stderr or out.stdout)[-1500:]}
            row.update({"season_index": index + 1, "engine": engine})
            rows.append(row)
            print(json.dumps(row), flush=True)
            shutil.rmtree(folder, ignore_errors=True)
    (work / "speed.json").write_text(json.dumps(rows, indent=1) + "\n")
    return 0


def speed_one(args: argparse.Namespace) -> int:
    from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
    from nba_gm_data.save import load_save
    from nba_gm_data import save as save_module
    save_module.lottery_seed = lambda seed=None: int(seed) if seed is not None else 20270622
    canonical = load_app_canonical(ROOT)
    folder = Path(args.folder)

    def act(name: str, **payload: Any) -> dict[str, Any]:
        return dispatch_app_action(name, payload, root=ROOT, save_dir=folder, canonical=canonical)

    if args.save:
        save_path = Path(args.save)
    else:
        created = act("create_save", team=args.team, seed=args.seed, save_name="speed")
        save_path = Path(created["save_path"])
        act("set_starting_five", save_path=str(save_path), team=args.team, auto=True)

    import ten_season_soak as soak
    soak.markdown_report = lambda payload: ""
    runner = soak.SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(folder / "runner"), seed=args.seed,
                                                team=args.team))
    runner.payload["save_path"] = str(save_path)
    runner.save_dir = folder

    def advance_to(target: str) -> int:
        games = 0
        for _ in range(12):
            runner.resolve_user_staff_retention()
            runner.resolve_user_roster_cutdown()
            save = load_save(save_path)
            if save["state"]["current_date"] >= target:
                break
            before = len((save.get("schedule_state") or {}).get("simulated_game_ids") or [])
            act("advance_save", save_path=str(save_path), to_date=target, checkpoint_days=31, seed=args.seed)
            after = load_save(save_path)
            games += len((after.get("schedule_state") or {}).get("simulated_game_ids") or []) - before
        return games

    year = int(load_save(save_path)["state"]["current_date"][:4])
    advance_to(f"{year}-10-20")
    started = time.monotonic()
    games = advance_to(f"{year}-11-30")
    seconds = time.monotonic() - started
    print(json.dumps({"from": f"{year}-10-20", "to": load_save(save_path)["state"]["current_date"], "games": games,
                      "seconds": round(seconds, 1), "seconds_per_30_days": round(seconds * 30 / 41, 1)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--engine", choices=("current", "stage2"), required=True)
    p_run.add_argument("--seasons", type=int, default=4)
    p_run.add_argument("--seed", type=int, default=20261125)
    p_run.add_argument("--team", default="MIA")
    p_run.add_argument("--checkpoint-days", type=int, default=31)
    p_run.add_argument("--out", required=True)
    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("runs", nargs="+")
    p_cmp.add_argument("--out", required=True)
    p_speed = sub.add_parser("speed")
    p_speed.add_argument("run", help="a finished run folder (its phase_saves are the season starts)")
    p_speed.add_argument("--engines", nargs="+", default=["current", "stage2"])
    p_speed.add_argument("--seasons", type=int, default=4)
    p_speed.add_argument("--seed", type=int, default=20261125)
    p_speed.add_argument("--team", default="MIA")
    p_speed.add_argument("--out", required=True)
    p_one = sub.add_parser("speed-one")
    p_one.add_argument("--engine", required=True)
    p_one.add_argument("--folder", required=True)
    p_one.add_argument("--save")
    p_one.add_argument("--seed", type=int, default=20261125)
    p_one.add_argument("--team", default="MIA")
    args = parser.parse_args()
    if args.command == "speed":
        return speed(args)
    if args.command == "speed-one":
        return speed_one(args)
    if args.command == "run":
        import gc
        gc.disable()   # same reason as ten_season_soak: JSON trees only, cyclic GC adds long pauses
        return run(args)
    return compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
