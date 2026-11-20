"""Injury kinds and lengths in games, real against simulated (INJURIES-2, 2026-11-20).

PYTHONPATH=src .venv/bin/python scripts/research/injury_lengths.py real bbi output/injuries-2/base_s17 [...]

Each argument is a source:
- `real`: the 2025-26 box scores (data/research/game_boxscores_2025_26.json). A spell is a run of a player's consecutive
  team games with an injury or illness reason (rest, coach's decisions, suspensions, personal reasons and not with team
  are left out); its body part comes from the first reason.
- `bbi`: the Basketball Index tracker history (local only), 2021-22 to 2024-25, games missed per logged absence.
- a path prefix PREFIX: a simulated season from the season harness (PREFIX_teamgames.json, with "INJURY" labels, and
  PREFIX_events.json for the body part).

Measures: spells per team by body part; share by length band (1, 2-5, 6-10, 11-20, 21+ games); season-ending share
(the spell reaches the team's last game); for heavy-minute players (30+ minutes a game, 10+ games) the games missed per
player in single games, 2-10 game runs and 11+ game runs (any absence, as in the TV-rest report's games-played measure);
and games played by the 30 best-rated players (real: output/injury-rest/top30_espn.json when present).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
from statistics import mean, median
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
from opening_night_injuries import is_injury_reason, part_of  # noqa: E402

# Regulars only (20+ minutes a game over 20+ games for the team): deep reserves' gaps in the real box scores are mostly
# G League trips and inactive lists, not injuries.
REGULAR_MPG = 20.0
REGULAR_GAMES = 20
BANDS = ((1, "1"), (5, "2-5"), (10, "6-10"), (20, "11-20"), (10_000, "21+"))
PART_GROUPS = {"ankle": "ankle/foot/toe", "foot": "ankle/foot/toe", "toe": "ankle/foot/toe",
               "knee": "knee", "quadriceps": "thigh", "hamstring": "thigh", "calf": "calf/achilles",
               "achilles": "calf/achilles", "hip": "hip/groin", "groin": "hip/groin", "back": "back",
               "shoulder": "arm/hand", "wrist": "arm/hand", "hand": "arm/hand", "thumb": "arm/hand",
               "head": "head", "illness": "illness", "unlisted": "unlisted", "rest": "rest"}
GROUP_ORDER = ["ankle/foot/toe", "knee", "thigh", "calf/achilles", "hip/groin", "back", "arm/hand", "head", "illness",
               "unlisted", "rest", "other"]


def band_of(games: int) -> str:
    return next(label for limit, label in BANDS if games <= limit)


def real_team_games() -> list[dict]:
    data = json.loads((ROOT / "data/research/game_boxscores_2025_26.json").read_text())
    out = []
    for g in sorted(data["games"], key=lambda g: (g["date"], g["game_id"])):
        if g.get("phase") != "regular":
            continue
        rows = defaultdict(list)
        for p in g["players"]:
            rows[p["team_abbrev"]].append(p)
        for abbrev, players in rows.items():
            out.append({
                "game": g["game_id"], "date": g["date"], "team": abbrev,
                "players": [[p["espn_player_id"], float(p["minutes"] or 0)] for p in players
                            if not p["dnp"] and float(p["minutes"] or 0) > 0],
                "dnp": [p["espn_player_id"] for p in players if p["dnp"] and not is_injury_reason(p.get("comment"))
                        and str(p.get("comment") or "").upper() == "COACH'S DECISION"],
                "labels": {p["espn_player_id"]: str(p.get("comment") or "") for p in players
                           if p["dnp"] and str(p.get("comment") or "").upper() != "COACH'S DECISION"},
            })
    return out


def spells(team_games: list[dict], injured, part_for) -> list[dict]:
    """In-season absences: runs of a player's consecutive team games without playing (coach's decisions aside), between
    two games he played for that team. The ESPN box scores list most injured players in no way at all (in 2025-26, 7,225
    unlisted games against 1,190 with a reason), so an unlisted run counts as an injury unless every listed reason in it
    is rest, a suspension, personal or not with team. injured(label) -> bool; part_for(pid, labels, date) -> part."""
    by_team = defaultdict(list)
    for tg in team_games:
        by_team[tg["team"]].append(tg)
    out = []
    for team, games in by_team.items():
        games.sort(key=lambda t: (t["date"], t["game"]))
        played, minutes_total = defaultdict(set), defaultdict(float)
        for i, tg in enumerate(games):
            for pid, minutes in tg["players"]:
                played[pid].add(i)
                minutes_total[pid] += float(minutes)
        for pid, idx in played.items():
            if len(idx) < REGULAR_GAMES or minutes_total[pid] / len(idx) < REGULAR_MPG:
                continue
            run: list[int] = []
            for i in range(min(idx), max(idx) + 2):
                if i <= max(idx) and i not in idx and pid not in (games[i].get("dnp") or []):
                    run.append(i)
                    continue
                if run:
                    labels = [games[k]["labels"][pid] for k in run if pid in (games[k].get("labels") or {})]
                    if not labels or any(injured(label) for label in labels):
                        hurt = [label for label in labels if injured(label)]
                        out.append({"team": team, "pid": pid, "games": len(run), "date": games[run[0]]["date"],
                                    "part": part_for(pid, hurt, games[run[0]]["date"]) or "other",
                                    "label": hurt[0] if hurt else None, "season_ending": False})
                run = []
    return out


NOT_ABSENCE_WORDS = ("SUSPEND", "PERSONAL", "NOT WITH TEAM", "G LEAGUE", "TWO-WAY", "BEREAVEMENT")


def real_absence(label: str) -> bool:
    """Real box-score view: every absence counts (injuries, illness and rest, since most rest days are unlisted
    there too), except suspensions, personal reasons, not with team and G League assignments."""
    return not any(word in str(label or "").upper() for word in NOT_ABSENCE_WORDS)


def sim_source(prefix: str):
    tgs = json.loads(Path(f"{prefix}_teamgames.json").read_text())
    events = json.loads(Path(f"{prefix}_events.json").read_text())
    by_player = defaultdict(list)
    for e in events:
        by_player[e["player_id"]].append(e)
    from nba_gm_data.injury_model import event_part

    def part_for(pid, labels, day):
        if labels and all(label == "REST" for label in labels):
            return "rest"
        best = None
        for e in by_player.get(pid, []):
            if str(e.get("start_date")) <= day and (not e.get("return_date") or day < str(e["return_date"])):
                if best is None or str(e["start_date"]) > str(best["start_date"]):
                    best = e
        return event_part(best) if best else "other"

    meta_path = Path(f"{prefix}_players.json")
    top30 = json.loads(meta_path.read_text()).get("top30") if meta_path.exists() else None
    return tgs, events, part_for, top30


def real_source():
    tgs = real_team_games()
    top_path = ROOT / "output/injury-rest/top30_espn.json"
    top30 = json.loads(top_path.read_text()) if top_path.exists() else None
    return tgs, (lambda pid, labels, day: part_of(" ".join(labels)) if labels else "unlisted"), top30


def sim_event_spells(tgs: list[dict], events: list[dict]) -> list[dict]:
    """Event view of a simulated season (every player, injuries only, as the tracker logs them): each in-season injury's
    games missed, counted on his team's schedule (he plays the game he is hurt in; out until the return date). An
    injury still running after the team's last game is season-ending."""
    from nba_gm_data.injury_model import event_part
    by_abbrev = defaultdict(set)
    for tg in tgs:
        by_abbrev[tg["team"]].add(tg["date"])
    out = []
    first_day = min(tg["date"] for tg in tgs)
    for e in events:
        if e.get("status") == "season_start_injury" or str(e.get("start_date")) < first_day:
            continue
        team = str(e.get("team_id") or "").replace("team_", "").upper()
        days = sorted(by_abbrev.get(team) or [])
        if not days:
            continue
        start, back = str(e["start_date"]), str(e.get("return_date") or "9999")
        games = sum(1 for d in days if start < d < back)
        if games <= 0:
            continue
        out.append({"team": team, "pid": e["player_id"], "games": games, "part": event_part(e),
                    "season_ending": back > days[-1], "label": e.get("diagnosis")})
    return out


def games_played(tgs: list[dict], top30) -> dict:
    """The TV-rest report's games-played measure (output/overnight-tv/gp.py): heavy-minute players' missed games by
    where they happen, and the 30 best players' games played."""
    by_team = defaultdict(list)
    for t in tgs:
        by_team[t["team"]].append(t)
    games, mins = defaultdict(int), defaultdict(float)
    first_date = {}
    for t in sorted(tgs, key=lambda t: t["date"]):
        for pid, m in t["players"]:
            games[pid] += 1
            mins[pid] += m
            first_date.setdefault(pid, t["date"])
    mpg = {p: mins[p] / games[p] for p in games}
    heavy = [p for p in mpg if mpg[p] >= 30 and games[p] >= 10]
    start_missed, single, mid, long_ = {}, defaultdict(int), defaultdict(int), defaultdict(int)
    for team, ts in by_team.items():
        ts.sort(key=lambda t: (t["date"], t["game"]))
        seen = defaultdict(list)
        for i, t in enumerate(ts):
            for pid, _ in t["players"]:
                seen[pid].append(i)
        for pid, idx in seen.items():
            if pid not in mpg or mpg[pid] < 30 or games[pid] < 10:
                continue
            if ts[idx[0]]["date"] == first_date[pid]:
                start_missed[pid] = idx[0]
            played = set(idx)
            run = 0
            for i in range(idx[0], idx[-1] + 2):
                if i <= idx[-1] and i not in played and pid not in (ts[i].get("dnp") or []):
                    run += 1
                    continue
                if run == 1:
                    single[pid] += 1
                elif 2 <= run <= 10:
                    mid[pid] += run
                elif run > 10:
                    long_[pid] += run
                run = 0
    n = max(1, len(heavy))
    res = {"heavy_n": len(heavy), "heavy_median": median(games[p] for p in heavy) if heavy else None,
           "heavy_mean": round(mean(games[p] for p in heavy), 1) if heavy else None,
           "season_start": round(sum(min(start_missed.get(p, 0), 82) for p in heavy) / n, 2),
           "single": round(sum(single[p] for p in heavy) / n, 2),
           "runs_2_10": round(sum(mid[p] for p in heavy) / n, 2),
           "runs_11_plus": round(sum(long_[p] for p in heavy) / n, 2)}
    if top30:
        g = [games.get(p, 0) for p in top30]
        res.update(top30_median=median(g), top30_mean=round(mean(g), 1), top30_under_60=sum(x < 60 for x in g))
    return res


def bbi_spells() -> list[dict]:
    path = ROOT / "data/research/bbi/tools/injury_player_history.json"
    data = json.loads(path.read_text())
    rows = data["rows"] if isinstance(data, dict) and "rows" in data else data
    merge = {"heel": "foot", "finger": "hand", "elbow": "shoulder", "forearm": "wrist", "arm": "shoulder", "leg": "calf",
             "shin": "calf", "neck": "back", "abdomen": "back", "ribs": "back", "chest": "back", "tailbone": "back",
             "eye": "head", "dental": "head"}
    out = []
    for h in rows:
        if not ("2021-22" <= str(h.get("season")) <= "2024-25") or h.get("cat") not in ("injury", "illness"):
            continue
        games = int(h.get("games") or 0)
        if games <= 0:
            continue
        part = "illness" if h["cat"] == "illness" else merge.get(h.get("part"), h.get("part")) or "other"
        out.append({"team": f"{h['season']}:{h.get('team')}", "games": games, "part": part,
                    "season_ending": bool(h.get("censored")), "label": h.get("label")})
    return out


def summarize(name: str, runs: list[dict], team_seasons: int) -> dict:
    groups = Counter(PART_GROUPS.get(r["part"], "other") for r in runs)
    bands = Counter(band_of(r["games"]) for r in runs)
    by_group = defaultdict(list)
    for r in runs:
        by_group[PART_GROUPS.get(r["part"], "other")].append(r["games"])
    games_lost = sum(r["games"] for r in runs)
    return {
        "name": name, "spells": len(runs), "per_team": round(len(runs) / team_seasons, 1),
        "games_lost_per_team": round(games_lost / team_seasons, 1),
        "bands": {label: round(100 * bands[label] / max(1, len(runs)), 1) for _, label in BANDS},
        "band_games": {label: round(sum(r["games"] for r in runs if band_of(r["games"]) == label) / team_seasons, 1)
                       for _, label in BANDS},
        "season_ending_pct": round(100 * sum(1 for r in runs if r.get("season_ending")) / max(1, len(runs)), 1),
        "parts": {g: {"per_team": round(groups[g] / team_seasons, 2),
                      "median": median(by_group[g]) if by_group[g] else None,
                      "bands": {label: round(100 * sum(1 for x in by_group[g] if band_of(x) == label) / len(by_group[g]))
                                for _, label in BANDS} if by_group[g] else {}}
                  for g in GROUP_ORDER if groups[g]},
    }


def print_summary(s: dict) -> None:
    print(f"\n== {s['name']}: {s['spells']} spells, {s['per_team']} per team, {s['games_lost_per_team']} games lost per team")
    print("   length bands (% of spells):", "  ".join(f"{k} {v}%" for k, v in s["bands"].items()),
          f"| season-ending {s['season_ending_pct']}%")
    print("   games lost per team by band:", "  ".join(f"{k} {v}" for k, v in s["band_games"].items()))
    for g, row in s["parts"].items():
        print(f"   {g:15} {row['per_team']:5.2f}/team  median {row['median']}  " +
              " ".join(f"{k}:{v}%" for k, v in row["bands"].items()))
    if s.get("gp"):
        print("   games played:", json.dumps(s["gp"]))


def main() -> None:
    results = []
    for arg in sys.argv[1:] or ["real", "bbi"]:
        if arg == "bbi":
            runs = bbi_spells()
            team_seasons = len({r["team"] for r in runs})
            batch = [summarize("events: Basketball Index tracker 2021-22 to 2024-25 (all players)", runs, team_seasons)]
        elif arg == "real":
            tgs, part_for, top30 = real_source()
            s = summarize("box scores: real 2025-26 regulars, all absences", spells(tgs, real_absence, part_for), 30)
            s["gp"] = games_played(tgs, top30)
            batch = [s]
        else:
            tgs, events, part_for, top30 = sim_source(arg)
            teams = len({t["team"] for t in tgs})
            s = summarize(f"box scores: {arg} regulars, all absences", spells(tgs, lambda label: True, part_for), teams)
            s["gp"] = games_played(tgs, top30)
            batch = [s, summarize(f"events: {arg} (all players)", sim_event_spells(tgs, events), teams)]
        for s in batch:
            print_summary(s)
            results.append(s)
    out = ROOT / "output/injuries-2/lengths_last.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
