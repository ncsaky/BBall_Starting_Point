#!/usr/bin/env python3
"""Replay a regular season through health.simulate_health (fixed opening rosters) and compare with Basketball Index.

    PYTHONPATH=src .venv/bin/python scripts/research/injury_season_check.py [--seeds 17,29] [--scale 1.0]
"""
import argparse, collections, statistics, sys
from datetime import date
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from nba_gm_data import health, injury_model as im
from nba_gm_data.app_actions import load_app_canonical


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", default="17,29"); ap.add_argument("--scale", type=float, default=None)
    a = ap.parse_args()
    if a.scale is not None:
        im.LEAGUE_RATE_SCALE = a.scale
    canonical = load_app_canonical(ROOT)
    players = {p["id"]: p for p in canonical["players"]}
    for seed in [int(s) for s in a.seeds.split(",")]:
        r = health.simulate_health(ROOT, canonical, "2025-10-21", "2026-04-12", seed=seed)
        ev = r["events"]; teams = len({p["team_id"] for p in players.values() if p.get("team_id")})
        days = sorted(e["expected_days_missed"] for e in ev)
        q = statistics.quantiles(days, n=20) if len(days) > 20 else days
        games = sum(int(s.get("games_missed") or 0) for s in r["final_states"])
        rostered = sum(1 for p in players.values() if p.get("team_id"))
        print(f"seed {seed}: spells {len(ev)} ({len(ev)/teams:.1f}/team)  days p25/50/75/90 = {q[4]}/{q[9]}/{q[14]}/{q[17]}  "
              f"games missed {games} ({82*games/(rostered*82)*1.0:.1f} per player-82 over {rostered} rostered)")
        parts = collections.Counter(e.get("body_part") for e in ev)
        print("   parts:", ", ".join(f"{k} {v}" for k, v in parts.most_common()))
        ages = collections.defaultdict(lambda: [0, 0])
        for s in r["final_states"]:
            p = players.get(s["player_id"]);
            if not p or not p.get("team_id") or float(p.get("minutes_projection") or 0) < 15: continue
            age = float(p.get("age") or 27); band = "<=22" if age <= 22 else "23-25" if age <= 25 else "26-28" if age <= 28 else "29-31" if age <= 31 else "32+"
            ages[band][0] += int(s.get("games_missed") or 0); ages[band][1] += 1
        print("   games missed per player (15+ projected minutes) by age:", {k: round(v[0]/v[1], 1) for k, v in sorted(ages.items())})
        rep = collections.defaultdict(list)
        for e in ev: rep[(e["player_id"], im.PART_AREA.get(e.get("body_part"), "x"))].append(e["start_date"])
        print(f"   players with a repeat in the same area this season: {sum(1 for v in rep.values() if len(v) > 1)} of {len(rep)}")
        print("   lasting-effect injuries:", [(players[e['player_id']]['name'], e['diagnosis']) for e in ev if e.get('lasting_rapm_change')][:8])


if __name__ == "__main__":
    main()
