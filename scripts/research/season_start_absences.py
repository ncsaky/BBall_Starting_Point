"""Who starts the season injured, and for how long (OVERNIGHT-REST-GAMES, 2026-11-20).

PYTHONPATH=src .venv/bin/python scripts/research/season_start_absences.py

Reads the Basketball Index injury tracker export (local only: data/research/bbi/tools/injury_player_history.json and
injury_player_seasons.json) and, for 2025-26, the real box scores (data/research/game_boxscores_2025_26.json).

Population: the previous season's regulars (40+ games, about 25+ minutes a game: 55+ possessions a game in the
tracker) who are still in the league. "Out on opening night" means an injury or illness spell (not suspensions or
personal reasons) that began before the opener and ended after it, or was still open. The spell's start is grouped
as: the previous regular season, the previous playoffs (April 15 - June 30), the offseason (July - September) or
training camp (October before the opener). Games missed at the start are counted from the opener to the spell's end
(0.471 team games a day, 82 games in 174 days); spells still open count the whole season when he played no games,
(none played = the whole season). For 2025-26 the box scores give the exact first game; in other seasons spells the
tracker left open (it often loses the return at season end) are not counted, so those seasons are a lower bound.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "data/research/bbi/tools"
OPENERS = {"2016-17": "2016-10-25", "2017-18": "2017-10-17", "2018-19": "2018-10-16", "2019-20": "2019-10-22",
           "2021-22": "2021-10-19", "2022-23": "2022-10-18", "2023-24": "2023-10-24", "2024-25": "2024-10-22",
           "2025-26": "2025-10-21"}
GAMES_PER_DAY = 82 / 174
REGULAR_POSS = 55          # possessions a game in the tracker, about 25 minutes
SKIP_CATS = {"administrative", "non_injury"}


def previous(season: str) -> str:
    y = int(season[:4]) - 1
    return f"{y}-{str(y + 1)[-2:]}"


def phase_of(start: str, opener: str) -> str:
    d, o = date.fromisoformat(start), date.fromisoformat(opener)
    if d >= date(o.year, 10, 1):
        return "training camp"
    if d >= date(o.year, 7, 1):
        return "offseason"
    if d >= date(o.year, 4, 15):
        return "previous playoffs / last week"
    return "previous regular season"


def norm(name: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if ch.isalnum() or ch == " ").replace(" jr", "").replace(" iii", "").replace(" ii", "").strip()


def games_before_first_appearance_2025_26() -> dict[str, int]:
    """Normalized name -> his team's games before his first appearance (the team he first played for)."""
    data = json.loads((ROOT / "data/research/game_boxscores_2025_26.json").read_text())
    team_dates = defaultdict(list)
    first = {}
    for g in sorted(data["games"], key=lambda g: (g["date"], g["game_id"])):
        if g.get("phase") != "regular":
            continue
        for t in g["teams"]:
            team_dates[t["team_abbrev"]].append(g["date"])
        for p in g["players"]:
            if not p["dnp"] and float(p["minutes"] or 0) > 0:
                first.setdefault(norm(p["player_name"]), (g["date"], p["team_abbrev"]))
    return {name: sum(1 for d in team_dates[team] if d < day) for name, (day, team) in first.items()}


def main() -> None:
    exact = {"2025-26": games_before_first_appearance_2025_26()}
    history = json.loads((TOOLS / "injury_player_history.json").read_text())
    seasons = json.loads((TOOLS / "injury_player_seasons.json").read_text())
    row = {(s["player_id"], s["season"]): s for s in seasons}
    spells = defaultdict(list)
    for h in history:
        spells[h["player_id"]].append(h)
    out = {}
    pooled = []
    for season, opener in OPENERS.items():
        prev = previous(season)
        pop = [pid for (pid, s), r in row.items() if s == prev and r["gp"] >= 40 and r["poss"] / max(1, r["gp"]) >= REGULAR_POSS
               and (pid, season) in row]
        cases = []
        for pid in pop:
            now = row[(pid, season)]
            best = None
            for h in spells[pid]:
                if h["cat"] in SKIP_CATS or not h["start"] or h["start"] >= opener:
                    continue
                if (date.fromisoformat(opener) - date.fromisoformat(h["start"])).days > 500:
                    continue
                if h["end"] and h["end"] > opener:
                    games = min(82, round((date.fromisoformat(h["end"]) - date.fromisoformat(opener)).days * GAMES_PER_DAY))
                elif not h["end"] and now["gp"] == 0:
                    games = 82          # still out: missed the whole season
                elif not h["end"] and season in exact:
                    games = exact[season].get(norm(h["player"]), 0)   # box scores: games before his first appearance
                else:
                    # open spells (the tracker often loses the return at season end) are left out of other seasons
                    continue
                if games <= 0:
                    continue
                if best is None or games > best[0]:
                    best = (games, h)
            if best:
                cases.append({"player": best[1]["player"], "games": best[0], "start": best[1]["start"], "end": best[1]["end"],
                              "label": best[1]["label"], "part": best[1]["part"], "phase": phase_of(best[1]["start"], opener)})
        g = [c["games"] for c in cases]
        out[season] = {"population": len(pop), "out_on_opening_night": len(cases),
                       "share": round(len(cases) / max(1, len(pop)), 4),
                       "games_missed_per_regular": round(sum(g) / max(1, len(pop)), 2),
                       "games_when_out_median": median(g) if g else None, "games_when_out_mean": round(mean(g), 1) if g else None,
                       "by_phase": dict(Counter(c["phase"] for c in cases)),
                       "games_by_phase": {k: sum(c["games"] for c in cases if c["phase"] == k) for k in {c["phase"] for c in cases}},
                       "cases": sorted(cases, key=lambda c: -c["games"])}
        pooled.extend((season, len(pop), c) for c in cases)
        print(f"{season}: regulars {len(pop)}, out on opening night {len(cases)} ({100 * len(cases) / max(1, len(pop)):.1f}%), "
              f"games missed at the start per regular {sum(g) / max(1, len(pop)):.2f}, when out: median {out[season]['games_when_out_median']}, "
              f"by phase {out[season]['by_phase']}")
    total_pop = sum(v["population"] for v in out.values())
    allg = [c["games"] for _, _, c in pooled]
    print(f"\npooled: regulars {total_pop}, out {len(allg)} ({100 * len(allg) / total_pop:.1f}%), games per regular {sum(allg) / total_pop:.2f}")
    bins = [(1, 2), (3, 5), (6, 10), (11, 20), (21, 40), (41, 81), (82, 82)]
    for lo, hi in bins:
        n = sum(lo <= x <= hi for x in allg)
        print(f"  {lo}-{hi} games: {n} ({100 * n / len(allg):.0f}%)")
    for phase in sorted({c["phase"] for _, _, c in pooled}):
        sub = [c["games"] for _, _, c in pooled if c["phase"] == phase]
        print(f"  {phase}: {len(sub)} cases ({100 * len(sub) / total_pop:.2f}% of regulars), games per regular {sum(sub) / total_pop:.2f}, median {median(sub)}")
    out["pooled"] = {"population": total_pop, "out": len(allg), "games": sorted(allg)}
    (ROOT / "output/overnight-tv").mkdir(parents=True, exist_ok=True)
    (ROOT / "output/overnight-tv/season_start_absences.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
