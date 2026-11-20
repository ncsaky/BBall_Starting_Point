"""What predicts a healthy regular sitting a single game: real 2025-26 box scores (SMART-REST, 2026-11-19).

PYTHONPATH=src .venv/bin/python scripts/research/rest_patterns.py [--rows OUT.json]

A "single-game absence" is a game a regular (25+ minutes a game over 20+ games) missed while playing his team's
previous and next games, not as a coach's decision DNP (dressed but unused). That is how rest nights look in a box
score (most are not labelled: ESPN lists inactive players only sometimes). Multi-game absences (injuries) are not
opportunities. The same row builder runs on simulated seasons (output/smart-rest/sim_season.py writes team games
in this format), so sim and real are measured the same way.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from nba_gm_data.rest_model import league_schedule_context, seed_movement, shrunk_win_pct  # noqa: E402

EAST = {"ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DET", "IND", "MIA", "MIL", "NY", "ORL", "PHI", "TOR", "WSH"}
REGULAR_MPG = 25.0
STAR_COUNT = 45          # the league counted 45 "stars" under the participation policy in 2025-26 (Hoops Rumors)


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if ch.isalnum() or ch == " ").replace(" jr", "").replace(" iii", "").replace(" ii", "").strip()


def game_score(p: dict) -> float:
    g = lambda k: float(p.get(k) or 0)  # noqa: E731
    return (g("points") + 0.4 * g("fgm") - 0.7 * g("fga") - 0.4 * (g("fta") - g("ftm")) + 0.7 * g("oreb") + 0.3 * g("dreb")
            + g("steals") + 0.7 * g("assists") + 0.7 * g("blocks") - 0.4 * g("pf") - g("turnovers"))


def real_team_games() -> tuple[list[dict], list[dict], dict[str, float]]:
    """Team games in the shared format, the schedule (ESPN ids) and ages by ESPN player id."""
    data = json.loads((ROOT / "data/research/game_boxscores_2025_26.json").read_text())
    uni = json.loads((ROOT / "data/canonical/universe_2025_26_preseason.json").read_text())
    born = {norm(p["name"]): date.fromisoformat(p["birthdate"][:10]) for p in uni["players"] if p.get("birthdate")}
    schedule, team_games, ages = [], [], {}
    for g in sorted(data["games"], key=lambda g: (g["date"], g["game_id"])):
        if g.get("phase") != "regular":
            continue
        schedule.append({"externalGameId": g["game_id"], "gameDate": g["date"], "homeTeamId": g["home_team_id"],
                         "awayTeamId": g["away_team_id"]})
        espn_by_abbrev = {t["team_abbrev"]: t["team_id"] for t in g["teams"]}
        pts = {t["team_abbrev"]: 0 for t in g["teams"]}
        rows = defaultdict(list)
        for p in g["players"]:
            rows[p["team_abbrev"]].append(p)
            pts[p["team_abbrev"]] = pts.get(p["team_abbrev"], 0) + int(p["points"] or 0)
            b = born.get(norm(p["player_name"]))
            if b:
                ages[p["espn_player_id"]] = (date(int(g["date"][:4]) if int(g["date"][5:7]) >= 7 else int(g["date"][:4]) - 1, 10, 21) - b).days / 365.25
        for abbrev, players in rows.items():
            opp = next(a for a in rows if a != abbrev) if len(rows) == 2 else None
            if opp is None:
                continue
            labelled = {}
            for p in players:
                if p["dnp"] and str(p.get("comment") or "").upper() != "COACH'S DECISION":
                    labelled[p["espn_player_id"]] = str(p.get("comment") or "").upper()
            team_games.append({
                "game": g["game_id"], "date": g["date"], "team": abbrev, "espn": espn_by_abbrev[abbrev],
                "opp": opp, "opp_espn": espn_by_abbrev[opp], "home": int(espn_by_abbrev[abbrev] == g["home_team_id"]),
                "margin": pts[abbrev] - pts[opp],
                "players": [[p["espn_player_id"], float(p["minutes"] or 0)] for p in players if not p["dnp"] and float(p["minutes"] or 0) > 0],
                "dnp": [p["espn_player_id"] for p in players if p["dnp"] and str(p.get("comment") or "").upper() == "COACH'S DECISION"],
                "labels": labelled,
                "gmsc": {p["espn_player_id"]: round(game_score(p), 2) for p in players if not p["dnp"] and float(p["minutes"] or 0) > 0},
            })
    return team_games, schedule, ages


def standings_before(team_games: list[dict]) -> dict[tuple[str, str], dict]:
    """(game, team) -> record before the game, conference rank, games left and the race around the team."""
    by_date = defaultdict(list)
    for tg in team_games:
        by_date[tg["date"]].append(tg)
    wins, losses = defaultdict(int), defaultdict(int)
    teams = sorted({tg["team"] for tg in team_games})
    total = defaultdict(int)
    for tg in team_games:
        total[tg["team"]] += 1
    out = {}
    for day in sorted(by_date):
        for tg in by_date[day]:
            out[(tg["game"], tg["team"])] = race_context(tg["team"], teams, wins, losses, total)
        for tg in by_date[day]:
            if tg["margin"] > 0:
                wins[tg["team"]] += 1
            else:
                losses[tg["team"]] += 1
    return out


def race_context(team: str, teams: list[str], wins, losses, total) -> dict:
    def pct(t):
        return shrunk_win_pct(wins[t], losses[t])   # shrunk early in the season
    conf = [t for t in teams if (t in EAST) == (team in EAST)]
    order = sorted(conf, key=lambda t: (-(wins[t] - losses[t]), t))
    rank = order.index(team) + 1
    league_order = sorted(teams, key=lambda t: (-pct(t), t))
    left = total[team] - wins[team] - losses[team]
    return {"wins": wins[team], "losses": losses[team], "win_pct": pct(team), "conf_rank": rank,
            "league_rank": league_order.index(team) + 1, "games_left": left,
            "seed_movement": seed_movement(team, order, wins, losses, total)}


MAJOR_NETWORKS = {"ESPN", "ABC", "NBC", "Peacock", "Prime Video", "NBCSN"}


def national_tv_games() -> dict[str, str]:
    """ESPN game id -> "major" (ESPN, ABC, NBC, Peacock, Prime Video) or "nbatv" (NBA TV only), from
    data/research/national_tv_2025_26.json (scripts/research/national_tv.py). Empty when the file is missing."""
    path = ROOT / "data/research/national_tv_2025_26.json"
    if not path.exists():
        return {}
    out = {}
    for game_id, g in json.loads(path.read_text())["games"].items():
        nets = set(g.get("national") or [])
        if nets & MAJOR_NETWORKS:
            out[game_id] = "major"
        elif "NBA TV" in nets:
            out[game_id] = "nbatv"
    return out


def build_rows(team_games: list[dict], schedule: list[dict], ages: dict[str, float], stars: set[str] | None = None,
               national: dict[str, str] | None = None) -> list[dict]:
    ctx = league_schedule_context(schedule)
    national = national_tv_games() if national is None else national
    stand = standings_before(team_games)
    by_team = defaultdict(list)
    for tg in team_games:
        by_team[tg["team"]].append(tg)
    games, minutes, gmsc = defaultdict(int), defaultdict(float), defaultdict(float)
    for tg in team_games:
        for pid, m in tg["players"]:
            games[pid] += 1
            minutes[pid] += m
            gmsc[pid] += tg.get("gmsc", {}).get(pid, 0.0)
    mpg = {p: minutes[p] / games[p] for p in games}
    regs = {p for p in mpg if mpg[p] >= REGULAR_MPG and games[p] >= 20}
    if stars is None:
        ranked = sorted((p for p in games if games[p] >= 30), key=lambda p: -gmsc[p] / games[p])
        stars = set(ranked[:STAR_COUNT])
    final = {}
    for team, tgs in by_team.items():
        w = sum(tg["margin"] > 0 for tg in tgs)
        final[team] = w / len(tgs)
    rows = []
    for team, tgs in by_team.items():
        tgs.sort(key=lambda t: (t["date"], t["game"]))
        seen = defaultdict(list)
        for i, tg in enumerate(tgs):
            for pid, _ in tg["players"]:
                seen[pid].append(i)
        for pid, idx in seen.items():
            if pid not in regs:
                continue
            lo, hi = idx[0], idx[-1]
            played = set(idx)
            for i in range(lo + 1, hi):
                tg = tgs[i]
                if pid in tg["dnp"]:
                    continue
                miss = i not in played
                if miss and ((i - 1) not in played or (i + 1) not in played):
                    continue   # part of a multi-game absence
                sc = ctx.get((tg["game"], tg["espn"])) or {}
                st = stand[(tg["game"], tg["team"])]
                ost = stand[(tg["game"], tg["opp"])]
                prev_played = (i - 1) in played
                # games played since the end of his last 2+ game absence (None when there was none in the last 10)
                since = None
                j, count = i - 1, 0
                while j > lo and count <= 10:
                    if j in played:
                        count += 1
                        j -= 1
                        continue
                    k = j
                    while k > lo and k not in played and pid not in tgs[k]["dnp"]:
                        k -= 1
                    since = count if j - k >= 2 else None
                    break
                rows.append({
                    "pid": pid, "team": team, "game": tg["game"], "date": tg["date"], "miss": int(miss),
                    "label": tg["labels"].get(pid, "") if miss else "",
                    "age": ages.get(pid), "mpg": round(mpg[pid], 1), "star": int(pid in stars),
                    "home": tg["home"], "b2b": int(bool(sc.get("back_to_back"))), "b2b_first": int(bool(sc.get("first_of_b2b"))),
                    "miles": sc.get("miles", 0.0), "tz": sc.get("tz_change", 0.0), "trip": sc.get("road_trip", 0),
                    "g4": sc.get("games_last_4", 1), "g6": sc.get("games_last_6", 1), "days_rest": sc.get("days_rest"),
                    "game_no": sc.get("game_number"), "games_left": st["games_left"],
                    "win_pct": round(st["win_pct"], 3), "league_rank": st["league_rank"], "conf_rank": st["conf_rank"],
                    "opp_pct": round(ost["win_pct"], 3), "opp_final": round(final[tg["opp"]], 3), "team_final": round(final[team], 3),
                    "line_in_play": int(st["seed_movement"]["line_in_play"]),
                    "best": st["seed_movement"]["best"], "worst": st["seed_movement"]["worst"],
                    "prev_played": int(prev_played), "since_return": since,
                    "tv": int(national.get(str(tg["game"])) == "major"), "nbatv": int(national.get(str(tg["game"])) == "nbatv"),
                    "tv_flag": int(bool(tg.get("national_tv"))),
                })
    return rows


def rate_table(rows: list[dict], key, label: str) -> None:
    groups = defaultdict(lambda: [0, 0])
    for r in rows:
        k = key(r)
        if k is None:
            continue
        groups[k][0] += r["miss"]
        groups[k][1] += 1
    print(f"\n{label}")
    for k in sorted(groups, key=str):
        m, n = groups[k]
        print(f"  {str(k):<28} {100 * m / n:5.2f}%  ({m} of {n})")


def report(rows: list[dict]) -> None:
    print(f"opportunities {len(rows)}, single-game absences {sum(r['miss'] for r in rows)} "
          f"({100 * sum(r['miss'] for r in rows) / len(rows):.2f}%), regulars {len({r['pid'] for r in rows})}")
    labels = defaultdict(int)
    for r in rows:
        if r["miss"]:
            lab = r["label"]
            kind = ("none listed" if not lab else "rest" if lab == "REST" or "LOAD" in lab else
                    "injury management" if "MANAGEMENT" in lab else "illness" if "ILLNESS" in lab else
                    "personal/not with team" if "PERSONAL" in lab or "NOT WITH TEAM" in lab else
                    "suspension" if "SUSPEND" in lab else "injury")
            labels[kind] += 1
    print("labels on single-game absences:", dict(labels))
    early = lambda r: r["games_left"] > 15  # noqa: E731
    rate_table(rows, lambda r: ("2nd night b2b" if r["b2b"] else "1st night b2b" if r["b2b_first"] else "other"), "Back-to-back night")
    rate_table([r for r in rows if r["b2b"]], lambda r: ("home" if r["home"] else "road"), "Second night: home vs road")
    rate_table([r for r in rows if r["b2b_first"]], lambda r: ("home" if r["home"] else "road"), "First night: home vs road")
    rate_table(rows, lambda r: ("home" if r["home"] else "road"), "Home vs road")
    mb = lambda m: "0-1" if m < 1 else "<500" if m < 500 else "500-1000" if m < 1000 else "1000-1500" if m < 1500 else "1500+"  # noqa: E731
    rate_table(rows, lambda r: mb(r["miles"]), "Miles since previous game")
    rate_table([r for r in rows if r["b2b"]], lambda r: mb(r["miles"]), "Miles, second night of b2b")
    rate_table([r for r in rows if not r["b2b"]], lambda r: mb(r["miles"]), "Miles, not b2b")
    rate_table(rows, lambda r: ("east 2+" if r["tz"] >= 2 else "east 1" if r["tz"] >= 1 else "west 2+" if r["tz"] <= -2 else "west 1" if r["tz"] <= -1 else "same"), "Time zones (east = later clock)")
    rate_table([r for r in rows if not r["home"]], lambda r: min(r["trip"], 5), "Road trip game number (road games)")
    rate_table(rows, lambda r: r["g4"], "Games in last 4 days (incl. today)")
    rate_table(rows, lambda r: r["g6"], "Games in last 6 days")
    ab = lambda a: None if a is None else "<25" if a < 25 else "25-29" if a < 30 else "30-33" if a < 34 else "34+"  # noqa: E731
    rate_table(rows, lambda r: ab(r["age"]), "Age")
    rate_table([r for r in rows if r["b2b"]], lambda r: ab(r["age"]), "Age, second night")
    rate_table([r for r in rows if not r["b2b"]], lambda r: ab(r["age"]), "Age, other nights")
    rate_table(rows, lambda r: "34+" if r["mpg"] >= 34 else "30-34" if r["mpg"] >= 30 else "25-30", "Minutes a game")
    rate_table(rows, lambda r: ("star" if r["star"] else "role"), "Star (top 45 by game score) vs other regulars")
    rate_table([r for r in rows if r["b2b"]], lambda r: ("star" if r["star"] else "role"), "Star, second night")
    ob = lambda p: "<.350" if p < .35 else ".350-.500" if p < .5 else ".500-.650" if p < .65 else ".650+"  # noqa: E731
    rate_table(rows, lambda r: ob(r["opp_pct"]), "Opponent win% to date (shrunk)")
    rate_table(rows, lambda r: ob(r["opp_final"]), "Opponent final win%")
    rate_table([r for r in rows if r["star"]], lambda r: ob(r["opp_final"]), "Stars: opponent final win%")
    rate_table([r for r in rows if r["b2b"]], lambda r: ob(r["opp_final"]), "Second night: opponent final win%")
    rate_table([r for r in rows if not r["b2b"]], lambda r: ob(r["opp_final"]), "Other nights: opponent final win%")
    rate_table(rows, lambda r: ob(r["win_pct"]), "Own win% to date")
    rate_table(rows, lambda r: ob(r["team_final"]), "Own final win%")
    rate_table(rows, lambda r: ("last 2" if r["games_left"] < 2 else "last 15" if r["games_left"] < 15 else "15-30 left" if r["games_left"] < 30 else "earlier"), "Games left (before this one)")
    late = [r for r in rows if r["games_left"] < 20]
    def sit(r):
        if r["games_left"] < 2:
            return None
        if r["best"] > 10 and r["league_rank"] > 22:
            return "out of race (bottom)"
        if r["line_in_play"]:
            return "line in play"
        return "locked"
    rate_table(late, sit, "Last 20 games (excl. final 2): team situation")
    rate_table([r for r in late if r["star"]], sit, "Last 20 games, stars: team situation")
    rate_table(rows, lambda r: r["date"][:7], "Month")
    tvk = lambda r: "national (major)" if r["tv"] else "NBA TV only" if r["nbatv"] else "local"  # noqa: E731
    rate_table(rows, tvk, "National TV")
    rate_table([r for r in rows if r["star"]], tvk, "Stars: national TV")
    rate_table([r for r in rows if not r["star"]], tvk, "Other regulars: national TV")
    rate_table([r for r in rows if r["b2b"]], tvk, "Second night: national TV")
    rate_table([r for r in rows if r["b2b"] and r["star"]], tvk, "Stars, second night: national TV")
    rate_table([r for r in rows if r["tv_flag"] or r["tv"]], lambda r: "star" if r["star"] else "role", "National games (sim flag or real): star vs other")
    rate_table(rows, lambda r: ("after missing prev" if not r["prev_played"] else None), "check")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows")
    args = ap.parse_args()
    tgs, schedule, ages = real_team_games()
    rows = build_rows(tgs, schedule, ages)
    report(rows)
    if args.rows:
        Path(args.rows).write_text(json.dumps(rows))
