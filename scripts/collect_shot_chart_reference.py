"""Collect a bounded, reproducible sample of public StatMuse shot-chart facts.

Stores aggregate statistics, not page markup or proprietary visual assets.
Run explicitly to refresh; application runtime never requests StatMuse.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen


PLAYERS = (
    "Stephen Curry", "Luka Doncic", "Shai Gilgeous-Alexander", "Nikola Jokic",
    "Giannis Antetokounmpo", "Kevin Durant", "DeMar DeRozan", "Anthony Edwards",
    "Jalen Brunson", "Donovan Mitchell", "Trae Young", "Tyrese Haliburton",
    "Jalen Suggs", "Pascal Siakam", "Ivica Zubac", "Bam Adebayo",
    "Rudy Gobert", "Brook Lopez", "Karl-Anthony Towns", "Victor Wembanyama",
    "Derrick White", "OG Anunoby", "Mikal Bridges", "Aaron Gordon",
    "Buddy Hield", "Duncan Robinson", "Isaiah Hartenstein", "Jarrett Allen",
    "Moses Moody", "Keegan Murray", "Ajay Mitchell", "Klay Thompson",
)


def decode(value):
    # Astro's public SSR props encode typed values as [type, payload].
    if isinstance(value, dict):
        return {key: decode(item) for key, item in value.items()}
    if isinstance(value, list) and len(value) >= 1 and isinstance(value[0], int):
        payload = value[1] if len(value) > 1 else None
        if value[0] == 1:
            return [decode(item) for item in (payload or [])]
        return decode(payload)
    return value


class ChartParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chart = None

    def handle_starttag(self, tag, attrs):
        if tag != "astro-island":
            return
        props = dict(attrs).get("props")
        if not props:
            return
        decoded = decode(json.loads(props))
        if "nba-shotchart" in dict(attrs).get("component-url", ""):
            self.chart = decoded
        if isinstance(decoded, dict) and isinstance(decoded.get("shots"), list):
            self.chart = decoded


def fetch_chart(player, season):
    slug = f"{player.lower().replace(' ', '-')}-shot-chart-in-{season}"
    url = f"https://www.statmuse.com/nba/ask/{slug}"
    request = Request(url, headers={"User-Agent": "BasketballShotChartResearch/1.0"})
    with urlopen(request, timeout=30) as response:
        parser = ChartParser()
        parser.feed(response.read().decode("utf-8"))
    if not parser.chart:
        raise ValueError("No public shot-chart props found")
    series = parser.chart.get("model", {}).get("series", [])
    if len(series) != 1 or options_season_mismatch(series[0].get("name", ""), season):
        raise ValueError("Chart did not resolve to the requested single season")
    return url, series[0]


def options_season_mismatch(name, season):
    return season not in name


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--inspect", action="store_true")
    args.add_argument("--season", default="2024-25")
    args.add_argument("--output", type=Path, default=Path("data/research/shot_chart_reference.json"))
    options = args.parse_args()
    profiles = []
    failures = []
    for player in PLAYERS[:1] if options.inspect else PLAYERS:
        try:
            url, chart = fetch_chart(player, options.season)
            if options.inspect:
                print(json.dumps({key: value[:2] if isinstance(value, list) else value for key, value in chart.items() if key != "shots"}, indent=2))
                print("shots:", len(chart.get("shots", [])), chart.get("shots", [])[:3])
                return
            shots = chart["shots"]
            bins = Counter()
            makes = Counter()
            zones = Counter()
            for shot in shots:
                x, y, zone = float(shot["X"]), float(shot["Y"]), int(shot["Z"])
                zones[zone] += 1
                # 2-foot bins in native NBA coordinates (tenths of a foot).
                key = (round(x / 20), round(y / 20), zone)
                bins[key] += 1
                makes[key] += int(shot.get("M") or 0)
            profiles.append({
                "name": player, "source_url": url, "attempts": len(shots),
                "zones": chart.get("zones", chart.get("shotZones", [])),
                "zone_counts": dict(sorted(zones.items())),
                "bins": [[x * 2, y * 2, zone, count, makes[(x, y, zone)]] for (x, y, zone), count in sorted(bins.items())],
            })
            print(f"{player}: {len(shots)} attempts, {len(zones)} zones", flush=True)
        except Exception as error:
            failures.append({"name": player, "error": str(error)})
            print(f"{player}: {error}", flush=True)
        time.sleep(0.8)
    options.output.write_text(json.dumps({
        "version": "statmuse_reference_v1", "season": options.season,
        "retrieved_on": date.today().isoformat(), "profiles": profiles,
        "failures": failures,
        "notes": "Bounded archetype sample, not an unbiased league census. Coordinates are aggregate public shot facts. Zone FG baselines come from each public chart, not this sample's player average.",
    }, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
