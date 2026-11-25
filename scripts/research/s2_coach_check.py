#!/usr/bin/env python3
"""Stage 2 coach check: who plays, how long and when, against real 2025-26 games (S2-COACH).

`collect` plays generated games (sandbox-sim: each team's planned rotation, the coach decides in the game) on one
engine and stores one record per team-game: each player's plan, minutes, fouls, role and starts, the final margin and
overtime, and (Stage 2) the coach's lineup log, from which stints, rests, minutes by quarter and close finishes are
measured the way the rotation study measured real games (data/research/rotation_evidence.json: stints merge across
any break with no change on the floor, halftime included).

`report` compares those records with real 2025-26 box scores (data/research/game_boxscores_2025_26.json) and the
rotation study: minutes per game player by player, starters and bench, the 30+/34+ minute counts, regulars' minutes by
final margin (garbage time), game-to-game spread, depth, foul-outs, hot and cold hands, overtime, and the Stage 2
rotation rhythm. Light: a full 1,230-game season takes about half a minute per engine.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_coach_check.py collect --engine stage2 [--games 1230] [--seed 1]
        [--tag X] [--loop key=value ...]
    PYTHONPATH=src .venv/bin/python scripts/research/s2_coach_check.py report FILE [FILE ...]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "output" / "s2coach"
BUCKETS = ((0, 5), (6, 10), (11, 15), (16, 20), (21, 999))


def bucket(margin: int) -> str:
    m = abs(int(margin))
    for lo, hi in BUCKETS:
        if lo <= m <= hi:
            return f"{lo}-{hi}" if hi < 999 else f"{lo}+"
    return "?"


# ---- collect --------------------------------------------------------------------------------------------------------
def _stints(log: list, n_end: float) -> tuple[dict[int, list[tuple[float, float]]], list]:
    """Player index -> on-floor intervals (merged when contiguous), from the coach's decision log."""
    spans: dict[int, list[list[float]]] = defaultdict(list)
    prev: tuple = ()
    prev_t = 0.0
    timeline = []
    for t, five, margin in log:
        timeline.append((t, five, margin))
        if prev:
            for i in prev:
                sp = spans[i]
                if sp and abs(sp[-1][1] - prev_t) < 1e-6:
                    sp[-1][1] = t
                else:
                    sp.append([prev_t, t])
        prev, prev_t = five, t
    for i in prev:
        sp = spans[i]
        if sp and abs(sp[-1][1] - prev_t) < 1e-6:
            sp[-1][1] = n_end
        else:
            sp.append([prev_t, n_end])
    return {i: [(a, b) for a, b in sp if b > a] for i, sp in spans.items()}, timeline


def stage2_records(game, extra, gid: str) -> list[dict]:
    end = 2880.0 + 300.0 * max(0, game.period - 4)
    out = []
    for side, state, opp in (("home", game.home, game.away), ("away", game.away, game.home)):
        players, items = extra[side]
        coach = state.coach
        rec = {"game": gid, "team": state.abbrev, "margin": state.points - opp.points,
               "ot": max(0, game.period - 4), "players": []}
        for i, item in enumerate(items):
            rec["players"].append({
                "id": players[i].get("id"), "name": players[i].get("name"), "plan": round(state.target_s[i] / 60.0, 2),
                "min": round(state.secs[i] / 60.0, 2), "pf": state.stats[i][13], "pts": state.stats[i][0],
                "ftm": state.stats[i][5], "starter": i in state.starters,
                "role": coach.roles[i] if coach else None, "reserve": state.reserve[i],
                "injured": bool(coach.injured[i]) if coach else False})
        if coach is not None and coach.log is not None:
            spans, timeline = _stints(coach.log, end)
            rec["spans"] = {str(i): sp for i, sp in spans.items()}
            rec["timeline"] = [(t, list(f), m) for t, f, m in timeline]
        out.append(rec)
    return out


def _overrides(args) -> dict:
    from nba_gm_data.stage2 import coach as C
    loop = {}
    for kv in args.loop or []:
        k, v = kv.split("=", 1)
        loop[k] = float(v)
    for kv in args.coach or []:
        k, v = kv.split("=", 1)
        C.COACH[k] = float(v)
    if loop:
        from nba_gm_data.stage2 import game as G
        G.LOOP.update(loop)
    return loop


def run_season(args) -> Path:
    """One headless 2026-27 regular season, all 30 teams AI-coached, injuries on, fixed opening rosters (the harness
    of the heavy-minutes and smart-minutes tasks), on either engine."""
    from collections import defaultdict as dd
    from time import process_time
    from nba_gm_data import health, save, sim, staff
    from nba_gm_data.schema import to_plain
    from nba_gm_data.stage2 import coach as C
    from nba_gm_data.stage2 import engine as E
    loop = _overrides(args)
    C.TRACE = args.engine == "stage2"
    root = ROOT
    context = sim.load_sim_context(root)
    canonical = context["canonical"]
    canonical["_allow_internal_caches"] = True
    canonical["_human_team_ids"] = []
    opening_states = canonical["player_health_states"]
    opening_events = canonical["injury_events"]
    canonical["player_health_states"] = []
    canonical["injury_events"] = []
    s = {"meta": {"season": "2026-27"}, "rotation_baselines": dict(save.initial_rotation_baselines(canonical))}
    games = save.generate_future_schedule(root, "2026-27", 2026)["games"]
    if args.games and args.games < len(games):
        games = games[: args.games]
    context["schedule"] = games
    context["indices"] = sim.build_sim_indices(context)
    seed = args.seed
    s["ai_role_state"] = {}
    s["staff_slots"] = staff.initialize_save_staff_slots(canonical, seed)
    save.align_real_head_coach_names(canonical, s)
    context["indices"]["coach_by_team"] = save.save_coach_ratings(canonical, s)
    first_day = save.new_career_start_date({"games": games})
    s["health_states"] = [dict(state) for state in opening_states]
    s["injury_events"] = [dict(event) for event in opening_events]
    save.initialize_new_career_health(s, first_day)
    canonical["player_health_states"] = s["health_states"]
    canonical["injury_events"] = s["injury_events"]
    canonical["gameplay_staff_slots"] = s["staff_slots"]
    previous = first_day
    by_day = dd(list)
    for game in games:
        by_day[game["gameDate"]].append(game)
    periods = {}
    records: list[dict] = []
    sim_cpu = 0.0
    t0 = time.time()
    hooked: list = []
    E.GAME_HOOK = (lambda g, extra, gid: hooked.extend(stage2_records(g, extra, gid))) if args.engine == "stage2" else None
    for k, game in enumerate(games):
        day = game["gameDate"]
        if day[:7] not in periods:
            save.reassess_ai_roles(canonical, s, day)
            save.apply_save_rotation_projection(canonical, s)
            context["sim_cache"].clear()
            periods[day[:7]] = True
        if day != previous:
            info = health.simulate_health(root, canonical, previous, day, seed=seed, schedule=by_day[day])
            s["health_states"] = canonical["player_health_states"] = info["final_states"]
            s["injury_events"].extend(info["events"])
            save.apply_save_rotation_projection(canonical, s)
            context["sim_cache"].clear()
            previous = day
        gid = str(game["externalGameId"])
        c0 = process_time()
        result = to_plain(sim.sim_game_with_context(context, gid, mode="sandbox-sim", seed=seed, engine=args.engine))
        sim_cpu += process_time() - c0
        if args.engine == "stage2":
            records.extend(hooked)
            hooked.clear()
        else:
            by_team = dd(list)
            for line in result["player_lines"]:
                by_team[line["team_abbrev"]].append(line)
            pts = {t: sum(int(x["points"]) for x in rows) for t, rows in by_team.items()}
            notes = result.get("notes") or ""
            ot = int(notes.split("Overtime resolved over ")[1].split()[0]) if "Overtime resolved over " in notes else 0
            for t, rows in by_team.items():
                opp = next(o for o in by_team if o != t)
                records.append({"game": gid, "team": t, "margin": pts[t] - pts[opp], "ot": ot, "players": [
                    {"id": x["player_id"], "name": x["player_name"], "plan": x.get("planned_minutes"),
                     "min": float(x["minutes"]), "pf": int(x["personal_fouls"]), "pts": int(x["points"]),
                     "ftm": int(x.get("ftm") or 0), "starter": bool(x.get("starter")), "role": None,
                     "reserve": False, "injured": bool(x.get("in_game_injury"))} for x in rows]})
        if (k + 1) % 200 == 0:
            print(f"  {k + 1}/{len(games)} games, {time.time() - t0:.0f}s", flush=True)
    E.GAME_HOOK = None
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"season_{args.engine}{('_' + args.tag) if args.tag else ''}.json"
    meta = {"engine": args.engine, "mode": "season", "seed": seed, "games": len(games), "loop": loop,
            "coach": {kv.split("=")[0]: float(kv.split("=")[1]) for kv in (args.coach or [])},
            "seconds": round(time.time() - t0, 1), "sim_ms_per_game": round(1000 * sim_cpu / max(1, len(games)), 2)}
    path.write_text(json.dumps({"meta": meta, "records": records}))
    print(f"season {args.engine}: {len(games)} games in {meta['seconds']}s (game sim {meta['sim_ms_per_game']} ms of CPU "
          f"a game) -> {path}")
    return path


def collect(args) -> Path:
    from nba_gm_data.sim import build_sim_indices, game_player_pool, load_sim_context, sim_game_with_context
    from nba_gm_data.schema import to_plain
    from nba_gm_data.stage2 import coach as C
    from nba_gm_data.stage2 import engine as E
    from nba_gm_data.stage2.game import LOOP
    loop = _overrides(args)
    context = load_sim_context(ROOT)
    context["indices"] = build_sim_indices(context)
    games = [g for g in context["schedule"] if str(g.get("phase", "regular")) in ("regular", "None", "")]
    games = sorted(games, key=lambda g: str(g.get("externalGameId")))
    step = max(1, len(games) // args.games)
    picked = games[::step][: args.games]
    teams_by_espn = context["indices"]["teams_by_espn_id"]
    records = []
    t0 = time.time()
    sim_s = 0.0
    C.TRACE = args.engine == "stage2"
    for k, g in enumerate(picked):
        gid = str(g["externalGameId"])
        if args.engine == "stage2":
            home_team = teams_by_espn[str(g["homeTeamId"])]
            away_team = teams_by_espn[str(g["awayTeamId"])]
            date = g.get("gameDate") or g.get("date")
            hp = game_player_pool(context, gid, home_team, args.mode, game_date=date)
            ap = game_player_pool(context, gid, away_team, args.mode, game_date=date)
            t1 = time.time()
            game, extra = E.play_stage2_game(context, g, home_team, away_team, hp, ap, game_id=gid, mode=args.mode,
                                             seed=args.seed, loop=loop or None)
            sim_s += time.time() - t1
            records.extend(stage2_records(game, extra, gid))
        else:
            t1 = time.time()
            r = to_plain(sim_game_with_context(context, gid, mode=args.mode, seed=args.seed, engine=args.engine))
            sim_s += time.time() - t1
            by_team = defaultdict(list)
            for line in r["player_lines"]:
                by_team[line["team_abbrev"]].append(line)
            pts = {t: sum(int(x["points"]) for x in rows) for t, rows in by_team.items()}
            ot = max(0, round((sum(float(x["minutes"]) for x in next(iter(by_team.values()))) - 240.0) / 25.0))
            for t, rows in by_team.items():
                opp = next(o for o in by_team if o != t)
                records.append({"game": gid, "team": t, "margin": pts[t] - pts[opp], "ot": ot, "players": [
                    {"id": x["player_id"], "name": x["player_name"], "plan": x.get("planned_minutes"),
                     "min": float(x["minutes"]), "pf": int(x["personal_fouls"]), "pts": int(x["points"]),
                     "ftm": int(x.get("ftm") or 0), "starter": bool(x.get("starter")), "role": None,
                     "reserve": False, "injured": bool(x.get("in_game_injury"))} for x in rows]})
        if (k + 1) % 200 == 0:
            print(f"  {k + 1}/{len(picked)} games, {time.time() - t0:.0f}s", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"coach_{args.engine}{('_' + args.tag) if args.tag else ''}.json"
    meta = {"engine": args.engine, "mode": args.mode, "seed": args.seed, "games": len(picked), "loop": loop,
            "coach": {kv.split("=")[0]: float(kv.split("=")[1]) for kv in (args.coach or [])},
            "seconds": round(time.time() - t0, 1), "sim_ms_per_game": round(1000 * sim_s / max(1, len(picked)), 2)}
    path.write_text(json.dumps({"meta": meta, "records": records}))
    print(f"{args.engine}: {len(picked)} games in {meta['seconds']}s ({meta['sim_ms_per_game']} ms a game) -> {path}")
    return path


# ---- real games -----------------------------------------------------------------------------------------------------
def real_records() -> list[dict]:
    data = json.loads((ROOT / "data/research/game_boxscores_2025_26.json").read_text())
    targets = json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
    by_espn = {str(row.get("espn_player_id")): pid for pid, row in targets.items() if row.get("espn_player_id")}
    out = []
    for g in data["games"]:
        if g.get("phase") != "regular":
            continue
        teams = defaultdict(list)
        for p in g["players"]:
            teams[p["team_abbrev"]].append(p)
        if len(teams) != 2:
            continue
        pts = {t: sum(int(p["points"] or 0) for p in rows) for t, rows in teams.items()}
        mins = {t: sum(float(p["minutes"] or 0) for p in rows) for t, rows in teams.items()}
        for t, rows in teams.items():
            opp = next(o for o in teams if o != t)
            out.append({"game": g["game_id"], "team": t, "margin": pts[t] - pts[opp],
                        "ot": max(0, round((mins[t] - 240.0) / 25.0)), "players": [
                {"id": by_espn.get(str(p["espn_player_id"]), "espn_" + str(p["espn_player_id"])),
                 "name": p["player_name"], "min": float(p["minutes"] or 0), "pf": int(p["pf"] or 0),
                 "pts": int(p["points"] or 0), "ftm": int(p["ftm"] or 0), "starter": bool(p["starter"])}
                for p in rows if not p["dnp"] and float(p["minutes"] or 0) > 0]})
    return out


# ---- metrics --------------------------------------------------------------------------------------------------------
def season(records: list[dict]) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for r in records:
        for p in r["players"]:
            if p["min"] <= 0:
                continue
            x = rows.setdefault(p["id"], {"games": 0, "min": 0.0, "starts": 0, "name": p["name"], "pts": 0, "ftm": 0})
            x["games"] += 1
            x["min"] += p["min"]
            x["starts"] += int(p["starter"])
            x["pts"] += p["pts"]
            x["ftm"] += p.get("ftm", 0)
    for x in rows.values():
        x["mpg"] = x["min"] / x["games"]
    return rows


def metrics(records: list[dict]) -> dict:
    table = season(records)
    q = {pid: r for pid, r in table.items() if r["games"] >= max(10, 0.4 * max(r2["games"] for r2 in table.values()))}
    games = {}
    for r in records:
        games[r["game"]] = (abs(r["margin"]), r["ot"])
    res: dict = {"team_games": len(records)}
    mpg = sorted((r["mpg"] for r in q.values()), reverse=True)
    res["players_qualified"] = len(q)
    for cut in (30, 32, 34, 36):
        res[f"players_{cut}_plus_per_team"] = round(sum(m >= cut for m in mpg) / 30.0, 2)
    res["top30_mpg"] = round(st.mean(mpg[:30]), 2)
    res["max_mpg"] = round(mpg[0], 2)
    res["ot_rate"] = round(sum(ot > 0 for _, ot in games.values()) / len(games), 4)
    res["margin_21_plus_share"] = round(sum(m >= 21 and not ot for m, ot in games.values()) / len(games), 3)
    res["mean_abs_margin"] = round(st.mean(m for m, _ in games.values()), 2)
    regulars = {pid for pid, r in q.items() if r["mpg"] >= 28}
    by_b = defaultdict(list)
    sd = defaultdict(list)
    fouled = []
    pf = []
    starters_min, bench_min = [], []
    depth5, depth1 = [], []
    hot_x, hot_y = [], []
    for r in records:
        ps = [p for p in r["players"] if p["min"] > 0]
        reg_min = 240.0 + 25.0 * r["ot"]
        depth5.append(sum(p["min"] >= 5 for p in ps))
        depth1.append(sum(p["min"] >= 1 for p in ps))
        starters_min.append(sum(p["min"] for p in ps if p["starter"]) / reg_min * 240.0)
        for p in ps:
            if p["id"] not in regulars:
                continue
            row = table[p["id"]]
            sd[p["id"]].append(p["min"])
            fouled.append(p["pf"] >= 6)
            pf.append(p["pf"])
            if r["ot"]:
                continue
            by_b[bucket(r["margin"])].append(p["min"] - row["mpg"])
            if abs(r["margin"]) <= 8 and p["min"] >= 0.5 * row["mpg"] and p["pf"] < 5:
                fgp = (row["pts"] - row["ftm"]) / row["min"]
                res_pts = (p["pts"] - p.get("ftm", 0)) - fgp * p["min"]
                hot_x.append(res_pts / max(1.0, p["min"]) * 10.0)
                hot_y.append(p["min"] - row["mpg"])
    res["regulars"] = len(regulars)
    res["regular_minutes_by_margin"] = {b: round(st.mean(v), 2) for b, v in sorted(by_b.items())}
    close, blow = res["regular_minutes_by_margin"].get("0-5"), res["regular_minutes_by_margin"].get("21+")
    res["close_minus_blowout"] = round(close - blow, 2) if close is not None and blow is not None else None
    res["regular_minutes_sd"] = round(st.mean(st.pstdev(v) for v in sd.values() if len(v) >= 10), 2)
    res["regular_foul_out_rate"] = round(st.mean(fouled), 4) if fouled else None
    res["regular_fouls_per_game"] = round(st.mean(pf), 2) if pf else None
    res["starters_minutes_share"] = round(st.mean(starters_min) / 240.0, 3)
    res["depth_5_min_players"] = round(st.mean(depth5), 2)
    dev = [abs(p["min"] - p["plan"]) for r in records for p in r["players"]
           if p.get("plan") and not p.get("reserve") and not r["ot"]]
    if dev:
        res["minutes_vs_plan_mean_abs"] = round(st.mean(dev), 2)
    res["depth_1_min_players"] = round(st.mean(depth1), 2)
    if len(hot_x) > 50:
        mx, my = st.mean(hot_x), st.mean(hot_y)
        sxx = sum((a - mx) ** 2 for a in hot_x)
        sxy = sum((a - mx) * (b - my) for a, b in zip(hot_x, hot_y))
        res["hot_hand_slope"] = round(sxy / sxx, 3)
        bins = defaultdict(list)
        for a, b in zip(hot_x, hot_y):
            bins[max(-2, min(2, round(a / 2)))].append(b)
        res["hot_hand_bins"] = {f"{2 * k:+d}": round(st.mean(v), 2) for k, v in sorted(bins.items())}
    res["_season"] = table
    return res


def rhythm(records: list[dict]) -> dict:
    """Stage 2 only: stints, rests, opening stint, minutes by quarter, close finishes (rotation study definitions)."""
    out = defaultdict(list)
    for r in records:
        spans = r.get("spans")
        if not spans:
            continue
        roles = {str(i): p["role"] for i, p in enumerate(r["players"])}
        starters = {str(i) for i, p in enumerate(r["players"]) if p["starter"]}
        for i, sp in spans.items():
            role = roles.get(i)
            if role is None or role == "reserve":
                continue
            for k, (a, b) in enumerate(sp):
                if b <= 2880.0:
                    out[f"stint|{role}"].append(b - a)
                if k and a <= 2880.0:
                    out[f"rest|{role}"].append(a - sp[k - 1][1])
            if i in starters and sp and sp[0][0] == 0.0:
                out[f"opening|{role}"].append(sp[0][1])
            for qi in range(4):
                lo, hi = 720.0 * qi, 720.0 * (qi + 1)
                secs = sum(max(0.0, min(b, hi) - max(a, lo)) for a, b in sp)
                if i in starters:
                    out[f"quarter|{role}|Q{qi + 1}"].append(secs)
        # Close finish: within five at 5:00 left in the 4th -> starters' share of floor time in the last five minutes.
        tl = r.get("timeline") or []
        m_at = next((m for t, f, m in reversed(tl) if t <= 2580.0), None)
        if m_at is not None and abs(m_at) <= 5 and not r["ot"]:
            floor = 0.0
            st_floor = 0.0
            star_floor = star_total = 0.0
            for i, sp in spans.items():
                secs = sum(max(0.0, min(b, 2880.0) - max(a, 2580.0)) for a, b in sp)
                floor += secs
                if i in starters:
                    st_floor += secs
                if roles.get(i) == "star":
                    star_floor += secs
                    star_total += 300.0
            if floor > 0:
                out["close_starter_share"].append(st_floor / floor)
            if star_total:
                out["close_star_share"].append(star_floor / star_total)
    res = {}
    for k, v in sorted(out.items()):
        if v:
            res[k] = {"n": len(v), "mean": round(st.mean(v), 1 if max(v) > 2 else 3),
                      "median": round(st.median(v), 1 if max(v) > 2 else 3)}
    return res


REAL_RHYTHM = {
    # Pooled 2023-26 regular seasons (rotation_evidence.json observations.pooled.regular); seconds.
    "stint": {"star": (586.4, 528.0), "starter": (465.0, 427.0), "sixth_man": (430.8, 403.0), "bench": (340.8, 313.0)},
    "rest": {"star": (248.2, 239.0), "starter": (304.4, 277.0), "sixth_man": (368.4, 317.0), "bench": (507.5, 412.0)},
    "opening": {"star": (542.8, 548.0), "starter": (452.1, 449.0)},
    "quarter": {"star": (582.1, 470.0, 588.0, 420.9), "starter": (488.2, 430.0, 477.5, 373.7)},
    "close_starter_share": .736, "close_star_share": .941, "depth_5_min_players": 9.82,
}
REAL_MARGIN = {"0-5": 1.5, "6-10": 1.1, "11-15": 0.3, "16-20": -1.4, "21+": -3.8}   # heavy-minutes.md (regulars)


def compare_minutes(sim_table: dict, real_table: dict, plans: dict | None = None) -> dict:
    pairs = []
    for pid, r in sim_table.items():
        real = real_table.get(pid)
        if real is None or real["games"] < 20 or r["games"] < 10:
            continue
        pairs.append((r["mpg"], real["mpg"], real.get("starts", 0) / real["games"], pid))
    if len(pairs) < 10:
        return {}
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = st.mean(xs), st.mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    corr = cov / math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    groups = {"starters (real 60%+ starts)": [p for p in pairs if p[2] >= .6],
              "bench 20+ real minutes": [p for p in pairs if p[2] < .6 and p[1] >= 20],
              "bench 10-20": [p for p in pairs if p[2] < .6 and 10 <= p[1] < 20],
              "bench under 10": [p for p in pairs if p[2] < .6 and p[1] < 10]}
    out = {"players": len(pairs), "corr": round(corr, 3), "mean_abs_diff": round(st.mean(abs(a - b) for a, b, *_ in pairs), 2),
           "bias": round(mx - my, 2)}
    for k, v in groups.items():
        if v:
            out[k] = {"n": len(v), "sim": round(st.mean(p[0] for p in v), 2), "real": round(st.mean(p[1] for p in v), 2)}
    return out


def report(args) -> None:
    real = real_records()
    rm = metrics(real)
    rows = [("real 2025-26", rm, None)]
    for f in args.files:
        data = json.loads(Path(f).read_text())
        m = metrics(data["records"])
        rows.append((Path(f).stem + f" ({data['meta'].get('sim_ms_per_game')} ms)", m, data))
    keys = ["players_30_plus_per_team", "players_34_plus_per_team", "players_36_plus_per_team", "top30_mpg", "max_mpg",
            "starters_minutes_share", "depth_5_min_players", "depth_1_min_players", "regular_minutes_sd",
            "regular_foul_out_rate", "regular_fouls_per_game", "close_minus_blowout", "margin_21_plus_share",
            "mean_abs_margin", "ot_rate", "hot_hand_slope", "minutes_vs_plan_mean_abs"]
    width = 16
    print("metric".ljust(30) + "".join(name[:width - 1].ljust(width) for name, *_ in rows))
    for k in keys:
        print(k.ljust(30) + "".join(str(m.get(k)).ljust(width) for _, m, _ in rows))
    print("regulars' minutes by final margin (vs own average):")
    for b in ("0-5", "6-10", "11-15", "16-20", "21+"):
        print(("  " + b).ljust(30) + "".join(str(m["regular_minutes_by_margin"].get(b)).ljust(width) for _, m, _ in rows))
    print("hot and cold hands (minutes vs own average by FG points per 10 min above own rate, close games):")
    for b in ("-4", "-2", "+0", "+2", "+4"):
        print(("  " + b).ljust(30) + "".join(str(m.get("hot_hand_bins", {}).get(b)).ljust(width) for _, m, _ in rows))
    print("minutes per game, player by player, against real 2025-26:")
    for name, m, data in rows[1:]:
        print(f"  {name}: {json.dumps(compare_minutes(m['_season'], rm['_season']))}")
    for name, m, data in rows[1:]:
        rh = rhythm(data["records"])
        if not rh:
            continue
        print(f"rotation rhythm, {name} (sim mean/median vs real mean/median, seconds):")
        for kind in ("stint", "rest", "opening"):
            for role, real_v in REAL_RHYTHM[kind].items():
                s = rh.get(f"{kind}|{role}")
                if s:
                    print(f"  {kind:<8}{role:<11} sim {s['mean']:7.1f} / {s['median']:7.1f}   real {real_v[0]:7.1f} / {real_v[1]:7.1f}  (n {s['n']})")
        for role, real_q in REAL_RHYTHM["quarter"].items():
            sim_q = [rh.get(f"quarter|{role}|Q{q}", {}).get("mean") for q in range(1, 5)]
            print(f"  quarter {role:<10} sim {sim_q}  real {list(real_q)}")
        for k in ("close_starter_share", "close_star_share"):
            print(f"  {k:<28} sim {rh.get(k, {}).get('mean')}  real {REAL_RHYTHM[k]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--engine", default="stage2")
    c.add_argument("--games", type=int, default=1230)
    c.add_argument("--seed", type=int, default=1)
    c.add_argument("--mode", default="sandbox-sim")
    c.add_argument("--tag", default="")
    c.add_argument("--loop", nargs="*", help="LOOP overrides, key=value")
    c.add_argument("--coach", nargs="*", help="COACH overrides, key=value")
    se = sub.add_parser("season")
    se.add_argument("--engine", default="stage2")
    se.add_argument("--games", type=int, default=0, help="first N games of the season (0 = all)")
    se.add_argument("--seed", type=int, default=17)
    se.add_argument("--tag", default="")
    se.add_argument("--loop", nargs="*", help="LOOP overrides, key=value")
    se.add_argument("--coach", nargs="*", help="COACH overrides, key=value")
    r = sub.add_parser("report")
    r.add_argument("files", nargs="+")
    args = ap.parse_args()
    if args.cmd == "collect":
        collect(args)
    elif args.cmd == "season":
        run_season(args)
    else:
        report(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
