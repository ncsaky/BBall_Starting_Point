"""National TV games of the 2025-26 regular season, from ESPN's public scoreboard (OVERNIGHT-REST-GAMES, 2026-11-20).

PYTHONPATH=src .venv/bin/python scripts/research/national_tv.py [--refresh]

For each date in the real box scores (data/research/game_boxscores_2025_26.json) it reads
https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD and keeps each game's
broadcasts in the "national" market (ESPN, ABC, NBC, Peacock, Prime Video, NBA TV; 2025-26 was the first season of
the league's new media deal, so TNT has no games). Writes data/research/national_tv_2025_26.json:
{"games": {ESPN game id: {"date", "home", "away", "national": [networks]}}, ...}. Raw days are cached in
output/overnight-tv/scoreboard/ so a rerun does not refetch.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BOXSCORES = ROOT / "data/research/game_boxscores_2025_26.json"
OUT = ROOT / "data/research/national_tv_2025_26.json"
CACHE = ROOT / "output/overnight-tv/scoreboard"
URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={day}"


def fetch_day(day: str, refresh: bool = False) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{day}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    request = urllib.request.Request(URL.format(day=day), headers={"User-Agent": "research-script"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    path.write_text(json.dumps(data))
    time.sleep(0.4)
    return data


def national_networks(competition: dict) -> list[str]:
    names: list[str] = []
    for row in competition.get("broadcasts") or []:
        if str(row.get("market") or "").lower() == "national":
            names.extend(str(n) for n in row.get("names") or [])
    for row in competition.get("geoBroadcasts") or []:
        if str((row.get("market") or {}).get("type") or "").lower() == "national":
            name = (row.get("media") or {}).get("shortName")
            if name:
                names.append(str(name))
    return sorted(set(names))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    box = json.loads(BOXSCORES.read_text())
    regular = {str(g["game_id"]): g for g in box["games"] if g.get("phase") == "regular"}
    days = sorted({g["date"] for g in regular.values()})
    games: dict[str, dict] = {}
    for day in days:
        data = fetch_day(day.replace("-", ""), args.refresh)
        for event in data.get("events") or []:
            game_id = str(event.get("id"))
            if game_id not in regular:
                continue
            comp = (event.get("competitions") or [{}])[0]
            g = regular[game_id]
            games[game_id] = {"date": g["date"], "home": g["home_team_id"], "away": g["away_team_id"],
                              "national": national_networks(comp)}
    missing = sorted(set(regular) - set(games))
    counts = Counter(n for g in games.values() for n in g["national"])
    OUT.write_text(json.dumps({
        "source": "ESPN public scoreboard API, national-market broadcasts; " + URL.replace("{day}", "YYYYMMDD"),
        "fetched": time.strftime("%Y-%m-%d"),
        "season": "2025-26",
        "game_count": len(games),
        "national_game_count": sum(1 for g in games.values() if g["national"]),
        "network_counts": dict(counts.most_common()),
        "missing_games": missing,
        "games": dict(sorted(games.items())),
    }, indent=0, sort_keys=False))
    print(f"{len(games)} games, {sum(1 for g in games.values() if g['national'])} national; missing {len(missing)}")
    print(dict(counts.most_common()))


if __name__ == "__main__":
    main()
