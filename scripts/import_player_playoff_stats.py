"""Import NBA regular-season and postseason box totals for the career cohort."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import fcntl
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from types import ModuleType
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research"
CAREER = RESEARCH / "player_career_stats.json"
REGULAR_CACHE = RESEARCH / "espn_career_raw"
CACHE = ROOT / "output/ply"
OUT = RESEARCH / "player_playoff_stats.json"
SOURCE_URL = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/"
    "athletes/{athlete}/stats?seasontype={season_type}"
)
SEASON_TYPES = {2: "regular", 3: "playoffs"}
FIRST_YEAR = 2014
LAST_YEAR = 2026
COUNT_FIELDS = {
    "points": "points",
    "rebounds": "totalRebounds",
    "offensive_rebounds": "offensiveRebounds",
    "defensive_rebounds": "defensiveRebounds",
    "assists": "assists",
    "steals": "steals",
    "blocks": "blocks",
    "turnovers": "turnovers",
    "personal_fouls": "fouls",
}
SHOT_FIELDS = {
    ("fgm", "fga"): "fieldGoalsMade-fieldGoalsAttempted",
    ("fg3m", "fg3a"): "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
    ("ftm", "fta"): "freeThrowsMade-freeThrowsAttempted",
}
BOX_FIELDS = (*COUNT_FIELDS, *(key for pair_keys in SHOT_FIELDS for key in pair_keys))
BREF_URL = "https://www.basketball-reference.com/{section}/NBA_{year}_totals.html"
BREF_FIELDS = {
    "games": ("games", "g"),
    "points": ("pts",),
    "fgm": ("fg",),
    "ftm": ("ft",),
    "fga": ("fga",),
    "rebounds": ("trb",),
    "assists": ("ast",),
    "offensive_rebounds": ("orb",),
    "defensive_rebounds": ("drb",),
    "steals": ("stl",),
    "blocks": ("blk",),
    "turnovers": ("tov",),
    "personal_fouls": ("pf",),
    "fg3m": ("fg3",),
    "fg3a": ("fg3a",),
    "fta": ("fta",),
}
BREF_NAME_ALIASES = {"ronaldholland": "ronholland"}


def import_career_helpers():
    # The career script runs its import as soon as its module executes.
    # Load just its numeric helpers so its network calls and writes stay off.
    path = Path(__file__).with_name("import_player_career_stats.py")
    tree = ast.parse(path.read_text(), filename=str(path))
    helpers = ast.Module(
        body=[
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in {"number", "pair"}
        ],
        type_ignores=[],
    )
    module = ModuleType("career_stats_helpers")
    exec(compile(helpers, str(path), "exec"), vars(module))
    return module.number, module.pair


number, pair = import_career_helpers()


def write_json(path, value, *, indent=None):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=indent, ensure_ascii=False) + "\n")
    temporary.replace(path)


def load_payload(payload, season_type):
    filters = {item["name"]: item for item in payload["filters"]}
    if filters.get("league", {}).get("value") != "nba":
        raise ValueError("ESPN response is missing the NBA league filter")
    season_filter = filters.get("seasontype")
    if season_filter is None and set(payload) == {"filters"}:
        return payload
    if season_type == 3 and season_filter and season_filter["value"] == "2":
        if {item["value"] for item in season_filter["options"]} == {"2"}:
            return payload
    if not season_filter or season_filter["value"] != str(season_type):
        raise ValueError(f"Unexpected ESPN season filter: {season_filter}")
    if not isinstance(payload["categories"], list):
        raise ValueError("ESPN response is missing its statistics categories")
    return payload


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ESPNCache:
    def __init__(self):
        self.next_request = 0.0
        self.opener = build_opener(NoRedirect())

    @staticmethod
    def read(path, season_type):
        retrieved_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        return load_payload(json.loads(path.read_text()), season_type), retrieved_at.isoformat(timespec="seconds")

    def get(self, athlete, season_type):
        path = CACHE / f"{athlete}-{season_type}.json"
        if path.exists():
            return self.read(path, season_type)
        if season_type == 2:
            existing = REGULAR_CACHE / f"{athlete}.json"
            if existing.exists():
                return self.read(existing, season_type)

        url = SOURCE_URL.format(athlete=athlete, season_type=season_type)
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        for attempt in range(3):
            time.sleep(max(0, self.next_request - time.monotonic()))
            self.next_request = time.monotonic() + 0.51
            try:
                with self.opener.open(request, timeout=25) as response:
                    payload = load_payload(json.load(response), season_type)
                write_json(path, payload)
                return self.read(path, season_type)
            except (URLError, OSError, ValueError, KeyError) as error:
                if attempt == 2 or isinstance(error, HTTPError) and error.code in (401, 403, 404):
                    raise
                delay = 2 ** (attempt + 1)
                if isinstance(error, HTTPError) and error.code == 429:
                    retry_after = error.headers.get("Retry-After", "")
                    delay = max(30, int(retry_after) if retry_after.isdecimal() else 0)
                time.sleep(delay)


def collect(players):
    cache = ESPNCache()
    responses = {}
    failures = {}
    for index, athlete in enumerate(sorted(players), 1):
        for season_type in SEASON_TYPES:
            try:
                responses[athlete, season_type] = cache.get(athlete, season_type)
            except (OSError, ValueError, KeyError) as error:
                failures[f"{athlete}-{season_type}"] = str(error)
        if index % 100 == 0 or index == len(players):
            print(f"Read {index}/{len(players)} athlete histories, {len(failures)} errors", flush=True)
    return responses, failures


def season_label(year):
    return f"{year - 1}-{year % 100:02}"


def category_rows(category):
    rows = {}
    for row in category.get("statistics", []):
        year = int(row["season"]["year"])
        if FIRST_YEAR <= year <= LAST_YEAR:
            key = year, str(row.get("teamId") or ""), str(row.get("teamSlug") or "")
            if key in rows:
                raise ValueError(f"Duplicate ESPN row: {key}")
            rows[key] = dict(zip(category["names"], row["stats"], strict=True))
    return rows


def count(value):
    result = number(value)
    if result is None:
        return None
    if result < 0 or not result.is_integer():
        raise ValueError(f"Invalid count: {value}")
    return int(result)


def count_from_average(value, games):
    if games == 1:
        return count(value)
    # A nonzero integer total in fewer than 20 games cannot round to 0.0.
    if games < 20 and number(value) == 0:
        return 0
    return None


def box_counts(totals, average, games):
    box = {label: count(totals.get(source)) for label, source in COUNT_FIELDS.items()}
    for (made, attempted), source in SHOT_FIELDS.items():
        shots = str(totals.get(source) or "")
        if shots in ("", "--"):
            box[made], box[attempted] = None, None
        else:
            made_value, attempted_value = pair(shots)
            box[made], box[attempted] = count(made_value), count(attempted_value)
    for label, source in COUNT_FIELDS.items():
        if box[label] is None:
            average_key = "avgRebounds" if label == "rebounds" else f"avg{source[0].upper()}{source[1:]}"
            box[label] = count_from_average(average.get(average_key), games)
    for fields, source in SHOT_FIELDS.items():
        if any(box[field] is None for field in fields):
            average_key = "-".join(f"avg{part[0].upper()}{part[1:]}" for part in source.split("-"))
            for field, value in zip(fields, pair(average.get(average_key)), strict=True):
                if box[field] is None:
                    box[field] = count_from_average(value, games)
    return box


def parse_seasons(payload, season_type):
    filters = {item["name"]: item["value"] for item in payload["filters"]}
    if filters.get("seasontype") != str(season_type):
        return []  # An explicit ESPN empty history or regular-season fallback.

    categories = {category["name"]: category for category in payload["categories"]}
    totals = category_rows(categories.get("totals", {}))
    averages = category_rows(categories.get("averages", {}))
    seasons = defaultdict(list)
    for key, average in averages.items():
        year, team_id, slug = key
        games = count(average["gamesPlayed"])
        if not games:
            continue
        avg_minutes = number(average["avgMinutes"])
        seasons[year].append({
            "team_id": team_id,
            "team_slug": slug,
            "games": games,
            "minutes": round(games * avg_minutes, 1) if avg_minutes is not None else None,
            **box_counts(totals.get(key, {}), average, games),
        })

    return [combine_season(year, rows) for year, rows in sorted(seasons.items())]


def combine_season(year, rows):
    stints = [row for row in rows if row["team_id"]]
    combined = [
        row for row in rows
        if not row["team_id"] and row["team_slug"].lower().endswith(" totals")
    ]
    if len(combined) > 1:
        raise ValueError(f"Multiple combined ESPN rows for {year}")
    parts = combined or rows
    season = {
        "season": season_label(year),
        "team_ids": list(dict.fromkeys(row["team_id"] for row in stints)),
    }
    full_stints = combined and stints and sum(row["games"] for row in stints) == combined[0]["games"]
    for field in ("games", "minutes", *BOX_FIELDS):
        values = [row[field] for row in parts]
        if values == [None] and full_stints:
            values = [row[field] for row in stints]
        season[field] = None if None in values else sum(values)
    if season["minutes"] is not None:
        season["minutes"] = round(season["minutes"], 1)
    return season


class ReferenceTable(HTMLParser):
    """Read named cells from Basketball Reference's season totals table."""

    def __init__(self):
        super().__init__()
        self.inside_table = False
        self.cell = None
        self.row = {}
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "totals_stats":
            self.inside_table = True
        if self.inside_table and tag == "tr":
            self.row = {}
        if self.inside_table and tag in ("td", "th"):
            self.cell = attributes.get("data-stat")
            if self.cell:
                self.row[self.cell] = ""

    def handle_endtag(self, tag):
        if tag == "table":
            self.inside_table = False
        if self.inside_table and tag == "tr" and self.row.get("mp") is not None:
            self.rows.append(self.row)
        if tag in ("td", "th"):
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.row[self.cell] += data


def normalize_name(name):
    words = name.casefold().rstrip(".").split()
    if words and words[-1] in {"jr", "sr", "ii", "iii", "iv"}:
        words.pop()
    return "".join(
        character for character in unicodedata.normalize("NFKD", "".join(words))
        if character.isalnum()
    )


def collect_reference_tables():
    tables = {}
    sources = {label: {} for label in SEASON_TYPES.values()}
    next_request = 0.0
    opener = build_opener(NoRedirect())
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        for label in SEASON_TYPES.values():
            section = "leagues" if label == "regular" else "playoffs"
            url = BREF_URL.format(section=section, year=year)
            path = CACHE / f"bref-{label}-{year}.html"
            if path.exists():
                html = path.read_text(encoding="utf-8")
            else:
                time.sleep(max(0, next_request - time.monotonic()))
                next_request = time.monotonic() + 4.1
                with opener.open(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as response:
                    html = response.read().decode("utf-8")
            parser = ReferenceTable()
            parser.feed(html)
            by_name = defaultdict(list)
            for row in parser.rows:
                name = row.get("name_display") or row.get("player")
                if not name:
                    continue
                by_name[normalize_name(name)].append(row)
            if not by_name:
                raise ValueError(f"Could not read Basketball Reference totals at {url}")
            if not path.exists():
                temporary = path.with_suffix(".tmp")
                temporary.write_text(html, encoding="utf-8")
                temporary.replace(path)
            tables[label, season_label(year)] = by_name
            sources[label][season_label(year)] = {
                "source_url": url,
                "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            }
    return tables, sources


def reference_count(row, field):
    return count(next((row[key] for key in BREF_FIELDS[field] if key in row), None))


def reference_minutes(by_name, name, season):
    # The stat line disambiguates traded players' stints and guards identity.
    matches = []
    name_key = normalize_name(name)
    for row in by_name.get(BREF_NAME_ALIASES.get(name_key, name_key), []):
        agreeing = {
            field for field in BREF_FIELDS
            if season[field] is not None and season[field] == reference_count(row, field)
        }
        scoring_line = {"games", "points", "fgm", "ftm"}
        # Some source corrections change made free throws and points.
        other_box_totals = {"games", "fgm", "fga", "rebounds", "assists"}
        if scoring_line <= agreeing or other_box_totals <= agreeing:
            matches.append(count(row["mp"]))
    return matches[0] if len(matches) == 1 else None


def add_kleber_playoff_season(seasons, tables, sources):
    # ESPN's career endpoint omits Kleber's Lakers playoff debut on April 30, 2025.
    # NBA official box score: https://www.nba.com/game/0042400165/box-score
    label = "2024-25"
    index = tables.get(("playoffs", label))
    if index is None or any(season["season"] == label for season in seasons):
        return
    row, = index["maxikleber"]
    if (row.get("team_id") or row.get("team_name_abbr")) != "LAL" or reference_count(row, "games") != 1:
        raise ValueError("Unexpected Basketball Reference playoff row for Maxi Kleber")
    seasons.append({
        "season": label,
        "team_ids": ["13"],
        "games": 1,
        "minutes": count(row["mp"]),
        **{field: reference_count(row, field) for field in BOX_FIELDS},
        "minutes_estimated": False,
        **sources["playoffs"][label],
    })
    seasons.sort(key=lambda row: row["season"])


def coverage_for(records, season_type):
    histories = [record[season_type]["seasons"] for record in records.values()]
    seasons = [season for history in histories for season in history]
    fields = ("minutes", *BOX_FIELDS)
    counts = Counter(season["season"] for season in seasons)
    return {
        "players_with_games": sum(bool(history) for history in histories),
        "players_with_minutes": sum(
            any((season["minutes"] or 0) > 0 for season in history) for history in histories
        ),
        "player_seasons": len(seasons),
        "player_seasons_by_year": {
            label: counts[label]
            for label in map(season_label, range(FIRST_YEAR, LAST_YEAR + 1))
        },
        "missing_fields": {
            field: sum(season[field] is None for season in seasons) for field in fields
        },
        "player_seasons_with_estimated_minutes": sum(season["minutes_estimated"] for season in seasons),
        "player_seasons_without_team": sum(not season["team_ids"] for season in seasons),
    }


def build_dataset(players, responses, reference_tables, reference_sources):
    records = {}
    for athlete, player in players.items():
        record = {key: player[key] for key in (
            "espn_player_id", "name", "draft_year", "draft_position", "draft_status"
        )}
        for season_type, label in SEASON_TYPES.items():
            payload, retrieved_at = responses[athlete, season_type]
            try:
                seasons = parse_seasons(payload, season_type)
            except (KeyError, ValueError) as error:
                raise ValueError(f"{player['name']} ({athlete}), {label}: {error}") from error
            for season in seasons:
                by_name = reference_tables.get((label, season["season"]), {})
                minutes = reference_minutes(by_name, record["name"], season)
                season["minutes_estimated"] = minutes is None and season["minutes"] is not None
                if minutes is not None:
                    season["minutes"] = minutes
            if athlete == "2960236" and label == "playoffs":
                add_kleber_playoff_season(seasons, reference_tables, reference_sources)
            record[label] = {
                "source_url": SOURCE_URL.format(athlete=athlete, season_type=season_type),
                "retrieved_at": retrieved_at,
                "seasons": seasons,
            }
        records[athlete] = record

    return {
        "version": 1,
        "retrieved_at": max(
            [retrieved_at for _, retrieved_at in responses.values()]
            + [row["retrieved_at"] for source in reference_sources.values() for row in source.values()]
        ),
        "source": "ESPN public NBA athlete career statistics",
        "season_range": ["2013-14", "2025-26"],
        "minutes_method": (
            "Basketball Reference whole-minute totals when matched by player name and box totals. "
            "Rows marked minutes_estimated use ESPN's rounded minutes per game times games played."
        ),
        "minutes_sources": reference_sources,
        "players": records,
        "coverage": {
            "cohort_players": len(records),
            **{label: coverage_for(records, label) for label in SEASON_TYPES.values()},
            "fetch_errors": {},
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-only", action="store_true", help="Warm the resumable cache")
    parser.add_argument("--espn-only", action="store_true", help="Use ESPN's estimated minutes throughout")
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    players = json.loads(CAREER.read_text())["players"]
    with (CACHE / "import.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        responses, failures = collect(players)
        if failures:
            write_json(CACHE / "fetch_errors.json", failures, indent=2)
            raise SystemExit("Fetch errors remain; rerun to resume. See output/ply/fetch_errors.json.")
        (CACHE / "fetch_errors.json").unlink(missing_ok=True)
        if not args.fetch_only:
            tables, sources = ({}, {}) if args.espn_only else collect_reference_tables()
            dataset = build_dataset(players, responses, tables, sources)
            write_json(OUT, dataset, indent=2)
            print(json.dumps(dataset["coverage"], indent=2))


if __name__ == "__main__":
    main()
