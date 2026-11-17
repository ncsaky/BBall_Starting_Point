#!/usr/bin/env python3
"""Build real-NBA 2025-26 calibration targets (deterministic, local data only)."""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.calibration_targets import (  # noqa: E402
    BAND_STD_MULT, LEAGUE_METRICS, PLAYER_COMPARE_METRICS, PLAYER_COUNT_STATS, league_metrics_from_totals, player_rates,
)

SEASON = "2025-26"
MIN_MINUTES = 500
ALT_MIN_GAMES, ALT_MIN_MPG = 20, 15.0


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def pair(text: str) -> tuple[float, float]:
    a, b = str(text).split("-")
    return float(a), float(b)


def team_totals(games: list[dict]) -> tuple[dict[str, dict[str, float]], dict]:
    """Per-team season totals from ESPN team box stats (player FGM/FGA in this cache are zero: not used)."""
    tot: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    used = 0
    for g in games:
        if g.get("phase") != "regular" or g.get("status") != "STATUS_FINAL" or len(g.get("teams") or []) != 2:
            continue
        mins: dict[str, float] = defaultdict(float)
        for p in g.get("players") or []:
            if not p.get("dnp"):
                mins[p["team_abbrev"]] += float(p.get("minutes") or 0)
        drb = {t["team_abbrev"]: float(t["stats"]["defensiveRebounds"]) for t in g["teams"]}
        used += 1
        for t in g["teams"]:
            s, ab = t["stats"], t["team_abbrev"]
            fgm, fga = pair(s["fieldGoalsMade-fieldGoalsAttempted"])
            m3, a3 = pair(s["threePointFieldGoalsMade-threePointFieldGoalsAttempted"])
            ftm, fta = pair(s["freeThrowsMade-freeThrowsAttempted"])
            r = tot[ab]
            # regulation = 240 team minutes; use box minutes when they look like 240 + 25*OT, else 240
            tm = mins.get(ab, 0.0)
            ot = round((tm - 240) / 25) if tm >= 240 else 0
            r["minutes"] += 240 + 25 * max(0, ot) if abs(tm - (240 + 25 * max(0, ot))) <= 8 else 240
            r["games"] += 1
            r["points"] += ftm + 2 * (fgm - m3) + 3 * m3
            r["fgm"] += fgm; r["fga"] += fga; r["fg3m"] += m3; r["fg3a"] += a3; r["ftm"] += ftm; r["fta"] += fta
            r["orb"] += float(s["offensiveRebounds"])
            r["tov"] += float(s["totalTurnovers"])  # official team TOV includes team turnovers
            r["ast"] += float(s["assists"]); r["stl"] += float(s["steals"]); r["blk"] += float(s["blocks"])
            r["pf"] += float(s["fouls"])
            r["opp_drb"] += sum(v for k, v in drb.items() if k != ab)
    return tot, {"games_used": used}


def build() -> dict:
    box = json.load(open(ROOT / "data/research/game_boxscores_2025_26.json"))
    tot, tinfo = team_totals(box["games"])
    per_team = {ab: league_metrics_from_totals(dict(t)) for ab, t in tot.items()}
    league_sum: dict[str, float] = defaultdict(float)
    for t in tot.values():
        for k, v in t.items():
            league_sum[k] += v
    league_all = league_metrics_from_totals(dict(league_sum))
    league: dict[str, dict] = {}
    for m in LEAGUE_METRICS:
        vals = [pt[m] for pt in per_team.values() if pt.get(m) is not None]
        league[m] = {
            "mean": round(league_all[m], 4) if league_all.get(m) is not None else None,
            "std": round(statistics.pstdev(vals), 4) if len(vals) > 1 else None,
            "team_min": round(min(vals), 4) if vals else None,
            "team_max": round(max(vals), 4) if vals else None,
            "n_teams": len(vals),
        }
        if league[m]["mean"] is None:
            league[m]["reason"] = "not computable from local data"
    # ---- players
    career = json.load(open(ROOT / "data/research/player_career_stats.json"))["players"]
    universe = json.load(open(ROOT / "data/canonical/universe_2026_27_offseason.json"))["players"]
    by_espn = {str(p.get("espn_player_id")): p for p in universe if p.get("espn_player_id")}
    by_name: dict[str, list] = defaultdict(list)
    for p in universe:
        by_name[norm(p["name"])].append(p)
    pstats = json.load(open(ROOT / "Player Stats/player_stats.json"))["rows"]
    pstats_by_name: dict[str, list] = defaultdict(list)
    for r in pstats:
        pstats_by_name[norm(r["player"])].append(r)

    eligible, players, unmatched, matched_by = 0, {}, [], Counter()
    for espn_id, c in career.items():
        season = next((s for s in c.get("seasons", []) if s.get("season") == SEASON), None)
        if not season or not season.get("games") or not season.get("minutes"):
            continue
        g, mn = float(season["games"]), float(season["minutes"])
        if not (mn >= MIN_MINUTES or (g >= ALT_MIN_GAMES and mn / g >= ALT_MIN_MPG)):
            continue
        if not (season.get("fga") and season.get("fga") > 0):
            continue  # guard against the known zero-FGA parser bug
        eligible += 1
        uni = by_espn.get(str(espn_id))
        how = "espn_id"
        if uni is None:
            cands = by_name.get(norm(c["name"]), [])
            if len(cands) == 1:
                uni, how = cands[0], "name"
        if uni is None:
            unmatched.append({"espn_player_id": str(espn_id), "name": c["name"], "minutes": mn})
            continue
        matched_by[how] += 1
        totals = {"games": g, "minutes": mn, "points": season["points"], "fga": season["fga"], "fg3a": season["fg3a"],
                  "fta": season["fta"], "rebounds": season["rebounds"], "assists": season["assists"],
                  "turnovers": season["turnovers"], "steals": season["steals"], "blocks": season["blocks"]}
        rec = {"name": c["name"], "espn_player_id": str(espn_id), "match": how, "games": g, "minutes": mn,
               "fg3m": season["fg3m"], "fg_pct": round(season["fgm"] / season["fga"], 4),
               **{k: round(v, 4) if v is not None else None for k, v in player_rates(totals).items()}}
        rows = pstats_by_name.get(norm(c["name"]), [])
        if len(rows) == 1:
            r = rows[0]
            rec["usage_pct"] = r.get("USGpct")
            rec["orb_pct"] = r.get("ORBpct")
            rec["drb_pct"] = r.get("DRBpct")
        players[uni["id"]] = rec
    spread = {}
    for m in PLAYER_COMPARE_METRICS:
        vals = [p[m] for p in players.values() if p.get(m) is not None]
        spread[m] = round(statistics.pstdev(vals), 4) if len(vals) > 1 else None
    return {
        "meta": {
            "season": SEASON,
            "description": "Real NBA 2025-26 regular-season calibration targets.",
            "possession_formula": "FGA + 0.44*FTA - ORB + TOV (team total, tov includes team turnovers)",
            "band_rule": f"within_band = |sim - mean| <= {BAND_STD_MULT} * std (std = spread of the season value across the 30 teams)",
            "league_source": "data/research/game_boxscores_2025_26.json team box stats (regular season, final games). Player-level FGM/FGA in that cache are 0 (known parser bug), so they are NOT used.",
            "team_games_used": tinfo["games_used"] * 2,
            "league_notes": {
                "pace": "possessions per 48 minutes using each team's own estimate; overtime handled via box minutes when plausible.",
                "tov_pct": "100*TOV/(FGA+0.44*FTA+TOV)",
                "orb_pct": "ORB/(ORB + opponent DRB), same-game opponent",
                "efg_pct": "(FGM + 0.5*3PM)/FGA",
                "ts_pct": "PTS/(2*(FGA+0.44*FTA))",
                "ast_rate": "AST/FGM",
            },
            "player_source": "data/research/player_career_stats.json 2025-26 season totals (ESPN); usage/ORB%/DRB% from Player Stats/player_stats.json (Crafted NBA) when the name matches uniquely.",
            "player_eligibility": f"minutes >= {MIN_MINUTES} OR (games >= {ALT_MIN_GAMES} AND minutes/game >= {ALT_MIN_MPG})",
            "player_usage_note": "usage_pct is the source-provided usage rate (BBRef style), not recomputed; it is not part of compare().",
            "player_keys": "universe_2026_27_offseason players[].id; matched by ESPN id, then unique normalized name",
        },
        "league": league,
        "player_spread": spread,
        "players": players,
        "player_match": {"eligible": eligible, "matched": len(players), "match_rate": round(len(players) / eligible, 4) if eligible else None,
                         "matched_by": dict(matched_by), "unmatched": sorted(unmatched, key=lambda u: -u["minutes"])},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data/calibration/nba_2025_26_targets.json"))
    args = ap.parse_args()
    data = build()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    for k, v in data["league"].items():
        print(f"  {k:<16} mean {v['mean']}  std {v['std']}")
    pm = data["player_match"]
    print(f"players: {pm['matched']}/{pm['eligible']} matched ({pm['match_rate']}); unmatched: {[u['name'] for u in pm['unmatched']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
