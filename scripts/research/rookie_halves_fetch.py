#!/usr/bin/env python3
"""ROOKIE-SEASON: fetch real game logs for young players and a veteran comparison group (ESPN public JSON).

Basketball Reference's robots file disallows game-log and split pages, so this uses ESPN's public stats API (the
same endpoints scripts/research/top30_real_seasons.py and import_player_career_stats.py use), one request every
3.1 seconds (under 20 a minute). Everything is cached under output/rookie-season/espn/; reruns fetch nothing new.

Who is fetched, regular seasons 2015-16 .. 2025-26 (ESPN season = the year it ends):
  * first-, second- and third-year players (by ESPN debut year) with 400+ minutes in that season;
  * a veteran comparison group: 25 players a season aged 26-30 with 1,200+ minutes (fixed pseudo-random pick),
    plus the same players' next season (for the summer change).
Also the league standings of each season (team records, for team phase).

    nice -n 10 python3 scripts/research/rookie_halves_fetch.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "output/rookie-season/espn"
BREF = ROOT / "output/rookie-fit-2/bbref"
UA = {"User-Agent": "research-script", "Accept": "application/json"}
SEASONS = list(range(2016, 2027))
PAUSE = 3.1
_last = [0.0]


def fetch(url: str, path: Path, allow: bool = True) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            path.unlink()
    if not allow:
        return {}
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        wait = PAUSE - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as response:
                data = response.read()
            path.write_bytes(data)
            return json.loads(data)
        except urllib.error.HTTPError as error:
            if error.code in (400, 403, 404):
                path.write_text("{}")
                return {}
            time.sleep(5 + attempt * 10)
        except Exception:  # noqa: BLE001 - network hiccups: retry
            time.sleep(5 + attempt * 10)
    return {}


def season_players(year: int, allow: bool = True) -> dict[str, dict]:
    url = ("https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete?region=us&lang=en"
           f"&contentorigin=espn&isqualified=false&page=1&limit=1000&sort=general.avgMinutes:desc&season={year}"
           "&seasontype=2")
    data = fetch(url, CACHE / f"by_{year}.json", allow)
    names = {c["name"]: c["names"] for c in data.get("categories", [])}
    out = {}
    for a in data.get("athletes", []):
        row = {}
        for cat in a.get("categories", []):
            for key, value in zip(names.get(cat["name"], []), cat.get("values", [])):
                try:
                    row[key] = float(value or 0)
                except (TypeError, ValueError):
                    pass
        ath = a["athlete"]
        row.update(name=ath.get("displayName"), age=ath.get("age"), debut=ath.get("debutYear"),
                   team=ath.get("teamShortName"))
        out[str(ath["id"])] = row
    return out


def gamelog(pid: str, year: int, allow: bool = True) -> dict:
    url = f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{pid}/gamelog?season={year}"
    return fetch(url, CACHE / f"gl_{pid}_{year}.json", allow)


def standings(year: int, allow: bool = True) -> dict:
    url = f"https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings?season={year}"
    return fetch(url, CACHE / f"standings_{year}.json", allow)


def norm(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z ]", "", text)
    return " ".join(w for w in text.split() if w not in ("jr", "sr", "ii", "iii", "iv"))


def bref_ages(year: int) -> dict[str, float]:
    """Age that season by normalized name, from Basketball Reference's season totals page (ESPN only has today's age)."""
    path = BREF / f"NBA_{year}_totals.html"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    out = {}
    for name, age in re.findall(r'data-stat="name_display"[^>]*>(?:<a[^>]*>)?([^<]+)(?:</a>)?</td>\s*'
                                r'<td[^>]*data-stat="age"[^>]*>(\d+)</td>', text):
        out.setdefault(norm(html.unescape(name)), float(age))
    return out


def rookie_classes() -> dict[str, int]:
    """Normalized name -> the season (end year) of his rookie year, from Basketball Reference's rookie pages."""
    data = json.loads((ROOT / "data/research/rookie_real_lines.json").read_text())
    out = {}
    for season, rows in data["classes"].items():
        for row in rows:
            out.setdefault(norm(row["name"]), int(season))
    return out


def experience(row: dict, year: int, classes: dict[str, int]) -> int | None:
    rookie = classes.get(norm(row.get("name")))
    return None if rookie is None else year - rookie


def wanted(allow: bool = True) -> list[tuple[str, int, str]]:
    seasons = {year: season_players(year, allow) for year in SEASONS}
    classes = rookie_classes()
    jobs: dict[tuple[str, int], str] = {}
    for year, rows in seasons.items():
        vets = []
        ages = bref_ages(year)
        for pid, row in rows.items():
            exp = experience(row, year, classes)
            minutes = row.get("minutes", 0.0)
            age = ages.get(norm(row.get("name")))
            if exp in (0, 1, 2) and minutes >= 400:
                jobs.setdefault((pid, year), f"year{exp + 1}")
            elif exp is None and age and 26 <= age <= 30 and minutes >= 1200:
                vets.append(pid)
        vets.sort(key=lambda pid: hashlib.sha256(f"vet:{year}:{pid}".encode()).hexdigest())
        for pid in vets[:25]:
            jobs.setdefault((pid, year), "veteran")
            nxt = seasons.get(year + 1, {}).get(pid)
            if nxt and nxt.get("minutes", 0.0) >= 400:
                jobs.setdefault((pid, year + 1), "veteran_next")
    return sorted(((pid, year, kind) for (pid, year), kind in jobs.items()), key=lambda j: (j[1], j[0]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for year in SEASONS:
        standings(year)
    jobs = wanted()
    todo = [j for j in jobs if not (CACHE / f"gl_{j[0]}_{j[1]}.json").exists()]
    counts: dict[str, int] = {}
    for _, _, kind in jobs:
        counts[kind] = counts.get(kind, 0) + 1
    print(f"{len(jobs)} game logs wanted ({counts}); {len(todo)} to fetch (~{len(todo) * PAUSE / 60:.0f} min)", flush=True)
    if args.dry_run:
        return
    for n, (pid, year, _) in enumerate(todo, 1):
        gamelog(pid, year)
        if n % 50 == 0:
            print(f"{n}/{len(todo)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
