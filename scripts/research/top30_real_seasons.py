"""The best players' games played and missed games, real seasons 2021-22 to 2025-26 (TOP30-GAMES, 2026-11-20).

    PYTHONPATH=src .venv/bin/python scripts/research/top30_real_seasons.py [--fetch] [--json OUT]

Sources (cached under output/top30-games/espn/, git-ignored):
- ESPN league player stats by season (`.../statistics/byathlete?season=YYYY`): picks the top 30.
- ESPN player game logs (`.../athletes/{id}/gamelog?season=YYYY`): the regular-season games each one played.
- ESPN team schedules (`.../teams/{id}/schedule?season=YYYY&seasontype=2`): his team's games.
- Basketball Index injury tracker (local only, data/research/bbi/tools/injury_player_history.json): why he missed them.

Who counts as the top 30 in a season: the 30 best by the previous season's Game Score per game (Hollinger's box-score
composite, ESPN per-game averages, 30+ games). That picks players by what was known before the season, the way the game
picks its top 30 by rating at the start of a season, so the group is not selected on the season's own health. A second
pick (same season, 20+ games) is shown as a check. For 2025-26 the game's own top 30 (their real 2025-26 seasons) is
shown too.

Missed games are split by where they fall (before his first game, single games, 2-10 and 11+ game stretches, after his
last game, the whole season) and by the tracker's reason (injury, illness, rest, health and safety protocols, other or
no entry).
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from functools import lru_cache
import json
from pathlib import Path
from statistics import mean, median
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "output/top30-games/espn"
SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
UA = {"User-Agent": "research-script"}


def espn_year(season: str) -> int:
    return int(season[:4]) + 1


def fetch(url: str, path: Path, allow_fetch: bool) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    if not allow_fetch:
        return {}
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as response:
                data = response.read()
            break
        except urllib.error.HTTPError as error:
            if error.code in (403, 404):
                return {}
            time.sleep(2 + attempt * 3)
        except Exception:  # noqa: BLE001 - network hiccups: retry
            time.sleep(2 + attempt * 3)
    else:
        return {}
    path.write_bytes(data)
    time.sleep(0.35)
    return json.loads(data)


@lru_cache(maxsize=16)
def league_stats(year: int, allow_fetch: bool) -> dict[str, dict]:
    url = ("https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete?region=us&lang=en"
           f"&contentorigin=espn&isqualified=false&page=1&limit=1000&sort=general.avgMinutes:desc&season={year}"
           "&seasontype=2")
    data = fetch(url, CACHE / f"by_{year}.json", allow_fetch)
    names = {c["name"]: c["names"] for c in data.get("categories", [])}
    out = {}
    for a in data.get("athletes", []):
        row = {}
        for cat in a.get("categories", []):
            for key, value in zip(names.get(cat["name"], []), cat.get("values", [])):
                row[key] = float(value or 0)
        ath = a["athlete"]
        row["name"] = ath.get("displayName")
        row["age"] = ath.get("age")
        out[str(ath["id"])] = row
    return out


def game_score(r: dict) -> float:
    """Hollinger Game Score per game from ESPN per-game averages; rebounds at 0.4 (the usual offensive/defensive mix)."""
    return (r.get("avgPoints", 0) + 0.4 * r.get("avgFieldGoalsMade", 0) - 0.7 * r.get("avgFieldGoalsAttempted", 0)
            - 0.4 * (r.get("avgFreeThrowsAttempted", 0) - r.get("avgFreeThrowsMade", 0)) + 0.4 * r.get("avgRebounds", 0)
            + r.get("avgSteals", 0) + 0.7 * r.get("avgAssists", 0) + 0.7 * r.get("avgBlocks", 0)
            - 0.4 * r.get("avgFouls", 0) - r.get("avgTurnovers", 0))


def pick_top30(season: str, allow_fetch: bool, mode: str = "prior") -> list[str]:
    year = espn_year(season)
    if mode == "prior":
        stats, min_games = league_stats(year - 1, allow_fetch), 30
    else:
        stats, min_games = league_stats(year, allow_fetch), 20
    ranked = sorted((pid for pid, r in stats.items() if r.get("gamesPlayed", 0) >= min_games),
                    key=lambda pid: -game_score(stats[pid]))
    return ranked[:30]


def game_log(pid: str, year: int, allow_fetch: bool) -> list[dict]:
    url = f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{pid}/gamelog?season={year}"
    data = fetch(url, CACHE / f"gl_{pid}_{year}.json", allow_fetch)
    events = data.get("events") or {}
    out = []
    for st in data.get("seasonTypes", []):
        if "Regular Season" not in st.get("displayName", ""):
            continue
        for cat in st.get("categories", []):
            if cat.get("type") != "event":
                continue
            for e in cat.get("events", []):
                meta = events.get(e["eventId"]) or {}
                minutes = float(e["stats"][0] or 0) if e.get("stats") else 0.0
                if minutes <= 0:
                    continue
                out.append({"game": e["eventId"], "team": str((meta.get("team") or {}).get("id") or ""),
                            "date": str(meta.get("gameDate") or ""),
                            "minutes": minutes})
    out.sort(key=lambda g: g["date"])   # ESPN lists months newest first
    return out


def team_schedule(team: str, year: int, allow_fetch: bool) -> list[dict]:
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/schedule?season={year}&seasontype=2"
    data = fetch(url, CACHE / f"sched_{team}_{year}.json", allow_fetch)
    out = []
    for e in data.get("events", []):
        comp = e["competitions"][0]
        if comp.get("status", {}).get("type", {}).get("name") != "STATUS_FINAL":
            continue
        if (e.get("seasonType") or {}).get("type") not in (2, None):
            continue
        # US Eastern calendar date (the tracker's dates are local game days).
        when = datetime.fromisoformat(e["date"].replace("Z", "+00:00")) - timedelta(hours=5)
        out.append({"game": str(e["id"]), "date": when.date().isoformat()})
    out.sort(key=lambda g: (g["date"], g["game"]))
    return out


def tracker_spells() -> dict[str, list[dict]]:
    path = ROOT / "data/research/bbi/tools/injury_player_history.json"
    if not path.exists():
        return {}
    by_espn: dict[str, list[dict]] = defaultdict(list)
    sys.path.insert(0, str(ROOT / "src"))
    from nba_gm_data.app_actions import load_app_canonical
    canonical = load_app_canonical(ROOT)
    espn_of = {p["id"]: str(p.get("espn_player_id")) for p in canonical["players"] if p.get("espn_player_id")}
    for h in json.loads(path.read_text()):
        espn = espn_of.get(h.get("player_id"))
        if espn and h.get("start"):
            by_espn[espn].append(h)
    return by_espn


def reason_group(h: dict | None) -> str:
    if not h:
        return "no entry"
    cat, label = h.get("cat"), str(h.get("label") or "")
    if cat == "injury":
        return "injury"
    if cat == "illness":
        return "illness"
    if label == "rest":
        return "rest"
    if label == "health protocols":
        return "health protocols"
    return "other"


def covering_spell(spells: list[dict], day: str) -> dict | None:
    best = None
    for h in spells:
        start = h["start"][:10]
        end = (h.get("end") or "")[:10]
        if not end:   # no logged return: his days out from the first missed game
            span = max(1, int(h.get("days") or 0), 2 * int(h.get("games") or 0))
            end = (date.fromisoformat(start) + timedelta(days=span)).isoformat()
        if start <= day and (day < end or (end == start and day == start)):
            if best is None or start > best["start"][:10]:
                best = h
    return best


def player_season(pid: str, season: str, allow_fetch: bool, tracker: dict) -> dict | None:
    year = espn_year(season)
    log = game_log(pid, year, allow_fetch)
    played = {g["game"] for g in log}
    # Teams in the order he played for them; a team with one stray game (a neutral-site tournament game listed under
    # another id) is ignored unless it is a real stop.
    counts = Counter(g["team"] for g in log if g["team"])
    teams = []
    for g in log:
        if g["team"] and counts[g["team"]] >= 2 and g["team"] not in teams:
            teams.append(g["team"])
    if not teams:
        return None   # whole season out: handled by the caller with the previous team
    timeline = []     # (date, game, played?) on the teams he was with, in order
    last_date = None
    for i, team in enumerate(teams):
        sched = team_schedule(team, year, allow_fetch)
        mine = [k for k, g in enumerate(sched) if g["game"] in played]
        if not mine:
            continue
        lo = 0 if i == 0 else next((k for k, g in enumerate(sched) if last_date and g["date"] > last_date), mine[0])
        hi = len(sched) - 1 if i == len(teams) - 1 else mine[-1]
        for k in range(lo, hi + 1):
            timeline.append((sched[k]["date"], sched[k]["game"], sched[k]["game"] in played))
        last_date = sched[hi]["date"]
    return summarize_timeline(timeline, tracker.get(pid, []))


def summarize_timeline(timeline: list[tuple[str, str, bool]], spells: list[dict]) -> dict:
    out = {"games": len(timeline), "played": sum(1 for _, _, p in timeline if p), "where": Counter(), "why": Counter(),
           "why_by_where": defaultdict(Counter), "stretches": []}
    idx = [k for k, (_, _, p) in enumerate(timeline) if p]
    if not idx:
        out["where"]["whole season"] = len(timeline)
        for day, _, _ in timeline:
            out["why"][reason_group(covering_spell(spells, day))] += 1
        return out
    first, last = idx[0], idx[-1]
    run: list[int] = []
    for k in range(len(timeline) + 1):
        if k < len(timeline) and not timeline[k][2]:
            run.append(k)
            continue
        if run:
            if run[0] == 0:
                where = "season start"
            elif run[-1] == len(timeline) - 1:
                where = "after last game"
            else:
                where = "single" if len(run) == 1 else "2-10" if len(run) <= 10 else "11+"
            out["where"][where] += len(run)
            whys = Counter(reason_group(covering_spell(spells, timeline[j][0])) for j in run)
            for why, n in whys.items():
                out["why"][why] += n
                out["why_by_where"][where][why] += n
            labels = Counter(str((covering_spell(spells, timeline[j][0]) or {}).get("label")) for j in run)
            out["stretches"].append({"where": where, "games": len(run), "start": timeline[run[0]][0],
                                     "why": whys.most_common(1)[0][0], "label": labels.most_common(1)[0][0]})
        run = []
    return out


def season_report(season: str, ids: list[str], allow_fetch: bool, tracker: dict, stats: dict) -> dict:
    rows = []
    for pid in ids:
        r = player_season(pid, season, allow_fetch, tracker)
        if r is None:
            # Whole season out: count his previous team's 82 games, all missed.
            r = {"games": 82, "played": 0, "where": Counter({"whole season": 82}), "why": Counter(),
                 "why_by_where": defaultdict(Counter), "stretches": []}
            spells = tracker.get(pid, [])
            year = espn_year(season)
            prev = game_log(pid, year - 1, allow_fetch)
            team = prev[-1]["team"] if prev else None
            for g in team_schedule(team, year, allow_fetch) if team else []:
                r["why"][reason_group(covering_spell(spells, g["date"]))] += 1
            missing = 82 - sum(r["why"].values())
            if missing > 0:
                r["why"]["no entry"] += missing
        r["id"] = pid
        r["name"] = (stats.get(pid) or {}).get("name")
        r["in_tracker"] = pid in tracker
        rows.append(r)
    gp = [r["played"] for r in rows]
    n = len(rows)
    where = Counter()
    why = Counter()
    why_by_where = defaultdict(Counter)
    for r in rows:
        where.update(r["where"])
        why.update(r["why"])
        for w, c in r["why_by_where"].items():
            why_by_where[w].update(c)
    tracked = [r for r in rows if r["in_tracker"]]
    return {
        "season": season, "n": n, "median_gp": median(gp), "mean_gp": round(mean(gp), 1),
        "under_60": sum(g < 60 for g in gp), "under_40": sum(g < 40 for g in gp),
        "where": {k: round(where[k] / n, 2) for k in ("season start", "single", "2-10", "11+", "after last game",
                                                       "whole season")},
        "why_share": {k: round(v / max(1, sum(why.values())), 3) for k, v in why.most_common()},
        "why_2_10": {k: round(v / max(1, sum(why_by_where["2-10"].values())), 3)
                     for k, v in why_by_where["2-10"].most_common()},
        "tracked": len(tracked),
        "players": [{"id": r["id"], "name": r["name"], "played": r["played"], "games": r["games"],
                     "where": dict(r["where"]), "stretches": r["stretches"]} for r in rows],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--json", default=str(ROOT / "output/top30-games/real_top30.json"))
    args = ap.parse_args()
    tracker = tracker_spells()
    game_top30 = ROOT / "output/injury-rest/top30_espn.json"
    result = {}
    for season in SEASONS:
        stats = league_stats(espn_year(season), args.fetch)
        stats.update({k: v for k, v in league_stats(espn_year(season) - 1, args.fetch).items() if k not in stats})
        picks = {"prior": pick_top30(season, args.fetch, "prior"), "same": pick_top30(season, args.fetch, "same")}
        if season == "2025-26" and game_top30.exists():
            picks["game"] = json.loads(game_top30.read_text())
        result[season] = {}
        for mode, ids in picks.items():
            rep = season_report(season, ids, args.fetch, tracker, stats)
            result[season][mode] = rep
            print(f"{season} {mode:5} median {rep['median_gp']:>5} mean {rep['mean_gp']:>5} under60 {rep['under_60']:>2} "
                  f"| missed/player: " + ", ".join(f"{k} {v:.1f}" for k, v in rep["where"].items())
                  + f" | tracked {rep['tracked']}/30")
            print("      why (all missed):", rep["why_share"])
            print("      why (2-10 stretches):", rep["why_2_10"])
    Path(args.json).write_text(json.dumps(result, indent=1))
    # Pooled over the five seasons, prior-season pick.
    for mode in ("prior", "same"):
        reps = [result[s][mode] for s in SEASONS]
        allgp = [p["played"] for r in reps for p in r["players"]]
        print(f"POOLED {mode}: median {median(allgp)}, mean {mean(allgp):.1f}, "
              + ", ".join(f"{k} {mean(r['where'][k] for r in reps):.2f}" for k in reps[0]["where"]))


if __name__ == "__main__":
    main()
