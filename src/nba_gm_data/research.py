from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from .teams import TEAM_INFO
from .utils import normalize_name


RESEARCH_DIR = Path("data/research")
CONTRACTS_FILE = RESEARCH_DIR / "contracts_public_players_2026.json"
STAFF_FILE = RESEARCH_DIR / "staff_bref_team_pages_2026.json"
NBA_OFFICIAL_STAFF_FILE = RESEARCH_DIR / "staff_nba_team_pages_2026.json"
COACHES_FILE = RESEARCH_DIR / "coaches_espn_2026.json"
GENERAL_MANAGERS_FILE = RESEARCH_DIR / "general_managers_wikipedia.json"
DRAFT_PICKS_FILE = RESEARCH_DIR / "draft_picks_espn_2026.json"
DRAFT_PROSPECTS_FILE = RESEARCH_DIR / "draft_prospects_2026.json"
FUTURE_PICKS_FILE = RESEARCH_DIR / "future_picks_spotrac_2027_plus.json"
GAME_BOXSCORES_FILE = RESEARCH_DIR / "game_boxscores_2025_26.json"
BETTING_ODDS_FILE = RESEARCH_DIR / "betting_odds_2025_26.json"
COACH_REPUTATION_FILE = RESEARCH_DIR / "coach_reputation_sources_2025_26.json"
TRACKING_SOURCES_FILE = RESEARCH_DIR / "tracking_sources_2025_26.json"

BREF_CONTRACTS_URL = "https://www.basketball-reference.com/contracts/players.html"
BREF_TEAM_URL_TEMPLATE = "https://www.basketball-reference.com/teams/{team}/2026.html"
ESPN_DRAFT_TEAMS_URL = "https://www.espn.com/nba/draft/teams/_/name/okc/oklahoma-city-thunder"
TANKATHON_2026_MOCK_DRAFT_URL = "https://www.tankathon.com/mock_draft"
ROOKIE_SCALE_2026_CONSENSUS_URL = "https://www.rookiescale.com/2026-consensus-board/"
NBA_2026_DRAFT_BOARD_URL = "https://www.nba.com/draft/2026/draft-board"
SPOTRAC_FUTURE_PICKS_URL = "https://www.spotrac.com/nba/draft/future/"
SPOTRAC_FUTURE_PICKS_JINA_URL = "https://r.jina.ai/http://r.jina.ai/http://www.spotrac.com/nba/draft/future/"
ESPN_SUMMARY_URL_TEMPLATE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
ESPN_SCOREBOARD_URL_TEMPLATE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
FANTASYDATA_NBA_ODDS_URL = "https://fantasydata.com/nba/odds"
FOXSPORTS_ARTICLE_URL_TEMPLATE = "https://www.foxsports.com/articles/nba/{slug}-prediction-odds-picks-{month_day}"
NBA_STATS_TRACKING_QUICKLINKS_URL = "https://www-ng.nba.com/stats/quicklinks"
ESPN_COACHES_URL = "https://www.espn.com/nba/coaches"
SI_COACH_RANKINGS_URL = "https://www.si.com/nba/ranking-the-top-five-nba-coaches-for-2025-26"
CBS_COACH_TIERS_URL = "https://www.cbssports.com/nba/news/nba-coach-rankings-all-30-coaches-split-into-eight-tiers-as-2025-26-season-begins/amp/"
BREF_COACHES_URL = "https://www.basketball-reference.com/leagues/NBA_2026_coaches.html"
WIKIPEDIA_GENERAL_MANAGERS_URL = "https://en.wikipedia.org/wiki/List_of_NBA_general_managers"
NBA_TEAM_INFO_URL_TEMPLATE = "https://www.nba.com/team/{team_id}/franchise-leaders"
HOOPSHYPE_SALARIES_URL = "https://hoopshype.com/salaries/players/"
HOOPSHYPE_TEAM_URL_TEMPLATE = "https://hoopshype.com/salaries/{team_slug}/"

BREF_SEASONS = {
    "y1": "2025-26",
    "y2": "2026-27",
    "y3": "2027-28",
    "y4": "2028-29",
    "y5": "2029-30",
    "y6": "2030-31",
}

BREF_TEAM_ABBREV = {
    "BKN": "BRK",
    "CHA": "CHO",
    "PHX": "PHO",
}

HOOPSHYPE_TEAM_SLUG = {
    "ATL": "atlanta_hawks",
    "BOS": "boston_celtics",
    "BKN": "brooklyn_nets",
    "CHA": "charlotte_hornets",
    "CHI": "chicago_bulls",
    "CLE": "cleveland_cavaliers",
    "DAL": "dallas_mavericks",
    "DEN": "denver_nuggets",
    "DET": "detroit_pistons",
    "GSW": "golden_state_warriors",
    "HOU": "houston_rockets",
    "IND": "indiana_pacers",
    "LAC": "los_angeles_clippers",
    "LAL": "los_angeles_lakers",
    "MEM": "memphis_grizzlies",
    "MIA": "miami_heat",
    "MIL": "milwaukee_bucks",
    "MIN": "minnesota_timberwolves",
    "NOP": "new_orleans_pelicans",
    "NYK": "new_york_knicks",
    "OKC": "oklahoma_city_thunder",
    "ORL": "orlando_magic",
    "PHI": "philadelphia_76ers",
    "PHX": "phoenix_suns",
    "POR": "portland_trail_blazers",
    "SAC": "sacramento_kings",
    "SAS": "san_antonio_spurs",
    "TOR": "toronto_raptors",
    "UTA": "utah_jazz",
    "WAS": "washington_wizards",
}

ESPN_TEAM_ID_TO_ABBREV = {
    "1": "ATL",
    "2": "BOS",
    "3": "NOP",
    "4": "CHI",
    "5": "CLE",
    "6": "DAL",
    "7": "DEN",
    "8": "DET",
    "9": "GSW",
    "10": "HOU",
    "11": "IND",
    "12": "LAC",
    "13": "LAL",
    "14": "MIA",
    "15": "MIL",
    "16": "MIN",
    "17": "BKN",
    "18": "NYK",
    "19": "ORL",
    "20": "PHI",
    "21": "PHX",
    "22": "POR",
    "23": "SAC",
    "24": "SAS",
    "25": "OKC",
    "26": "UTA",
    "27": "WAS",
    "28": "TOR",
    "29": "MEM",
    "30": "CHA",
}

TEAM_NICKNAME_SLUG = {
    "ATL": ("Hawks", "hawks"),
    "BOS": ("Celtics", "celtics"),
    "BKN": ("Nets", "nets"),
    "CHA": ("Hornets", "hornets"),
    "CHI": ("Bulls", "bulls"),
    "CLE": ("Cavaliers", "cavaliers"),
    "DAL": ("Mavericks", "mavericks"),
    "DEN": ("Nuggets", "nuggets"),
    "DET": ("Pistons", "pistons"),
    "GSW": ("Warriors", "warriors"),
    "HOU": ("Rockets", "rockets"),
    "IND": ("Pacers", "pacers"),
    "LAC": ("Clippers", "clippers"),
    "LAL": ("Lakers", "lakers"),
    "MEM": ("Grizzlies", "grizzlies"),
    "MIA": ("Heat", "heat"),
    "MIL": ("Bucks", "bucks"),
    "MIN": ("Timberwolves", "timberwolves"),
    "NOP": ("Pelicans", "pelicans"),
    "NYK": ("Knicks", "knicks"),
    "OKC": ("Thunder", "thunder"),
    "ORL": ("Magic", "magic"),
    "PHI": ("76ers", "76ers"),
    "PHX": ("Suns", "suns"),
    "POR": ("Trail Blazers", "trail-blazers"),
    "SAC": ("Kings", "kings"),
    "SAS": ("Spurs", "spurs"),
    "TOR": ("Raptors", "raptors"),
    "UTA": ("Jazz", "jazz"),
    "WAS": ("Wizards", "wizards"),
}

NBA_TEAM_ID = {
    "ATL": "1610612737",
    "BOS": "1610612738",
    "BKN": "1610612751",
    "CHA": "1610612766",
    "CHI": "1610612741",
    "CLE": "1610612739",
    "DAL": "1610612742",
    "DEN": "1610612743",
    "DET": "1610612765",
    "GSW": "1610612744",
    "HOU": "1610612745",
    "IND": "1610612754",
    "LAC": "1610612746",
    "LAL": "1610612747",
    "MEM": "1610612763",
    "MIA": "1610612748",
    "MIL": "1610612749",
    "MIN": "1610612750",
    "NOP": "1610612740",
    "NYK": "1610612752",
    "OKC": "1610612760",
    "ORL": "1610612753",
    "PHI": "1610612755",
    "PHX": "1610612756",
    "POR": "1610612757",
    "SAC": "1610612758",
    "SAS": "1610612759",
    "TOR": "1610612761",
    "UTA": "1610612762",
    "WAS": "1610612764",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh cached public research sources.")
    parser.add_argument("--root", default=".", help="Workspace root.")
    parser.add_argument("--skip-network", action="store_true", help="Validate parsers against existing cached files only.")
    parser.add_argument("--skip-staff", action="store_true", help="Refresh contracts and draft picks only.")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if args.skip_network:
        for rel in [CONTRACTS_FILE, STAFF_FILE, NBA_OFFICIAL_STAFF_FILE, COACHES_FILE, GENERAL_MANAGERS_FILE, DRAFT_PICKS_FILE, DRAFT_PROSPECTS_FILE, FUTURE_PICKS_FILE]:
            path = root / rel
            if not path.exists():
                raise SystemExit(f"Missing cached research file: {path}")
            print(path)
        return 0
    paths = refresh_research(root, include_staff=not args.skip_staff)
    for path in paths:
        print(path)
    return 0


def refresh_research(root: Path, include_staff: bool = True) -> list[Path]:
    out_dir = root / RESEARCH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    contracts = fetch_contracts()
    write_json(root / CONTRACTS_FILE, contracts)
    draft_picks = fetch_espn_draft_picks()
    write_json(root / DRAFT_PICKS_FILE, draft_picks)
    draft_prospects = fetch_2026_draft_prospects()
    write_json(root / DRAFT_PROSPECTS_FILE, draft_prospects)
    future_picks = fetch_spotrac_future_picks()
    write_json(root / FUTURE_PICKS_FILE, future_picks)
    coaches = fetch_espn_coaches()
    write_json(root / COACHES_FILE, coaches)
    general_managers = fetch_wikipedia_general_managers()
    write_json(root / GENERAL_MANAGERS_FILE, general_managers)
    official_staff = fetch_nba_official_staff()
    write_json(root / NBA_OFFICIAL_STAFF_FILE, official_staff)
    if include_staff:
        staff = fetch_staff()
        write_json(root / STAFF_FILE, staff)
    return [root / CONTRACTS_FILE, root / STAFF_FILE, root / NBA_OFFICIAL_STAFF_FILE, root / COACHES_FILE, root / GENERAL_MANAGERS_FILE, root / DRAFT_PICKS_FILE, root / DRAFT_PROSPECTS_FILE, root / FUTURE_PICKS_FILE]


def refresh_boxscore_research(root: Path, limit: int | None = None, missing_only: bool = True) -> Path:
    out_dir = root / RESEARCH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = fetch_game_boxscores(root, limit=limit, missing_only=missing_only)
    path = root / GAME_BOXSCORES_FILE
    write_json(path, payload)
    return path


def refresh_coach_reputation_research(root: Path) -> list[Path]:
    out_dir = root / RESEARCH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    coach_path = root / COACH_REPUTATION_FILE
    tracking_path = root / TRACKING_SOURCES_FILE
    write_json(coach_path, build_coach_reputation_sources())
    write_json(tracking_path, build_tracking_source_registry())
    return [coach_path, tracking_path]


def refresh_betting_odds_research(root: Path, limit: int | None = None, secondary_limit: int | None = 80) -> Path:
    out_dir = root / RESEARCH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = fetch_espn_betting_odds(root, limit=limit, secondary_limit=secondary_limit)
    path = root / BETTING_ODDS_FILE
    write_json(path, payload)
    return path


def refresh_draft_prospect_research(root: Path) -> Path:
    out_dir = root / RESEARCH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = fetch_2026_draft_prospects()
    path = root / DRAFT_PROSPECTS_FILE
    write_json(path, payload)
    return path


def fetch_url(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="ignore")
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(0.4 * (attempt + 1))
    assert last_error is not None
    raise last_error


def fetch_url_once(url: str, timeout: int = 10) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def fetched_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def fetch_contracts() -> dict[str, Any]:
    try:
        raw = fetch_url(BREF_CONTRACTS_URL)
        rows = parse_bref_contracts(raw)
        return {
            "source": {
                "id": "src_bref_contracts_players_2026",
                "title": "Basketball-Reference 2025-26 NBA Player Contracts",
                "url": BREF_CONTRACTS_URL,
                "fetched_at": fetched_at(),
            },
            "row_count": len(rows),
            "contracts": rows,
        }
    except urllib.error.HTTPError as exc:
        if exc.code != 429:
            raise
        rows = fetch_hoopshype_team_salaries()
        return {
            "source": {
                "id": "src_hoopshype_salaries_players_2026",
                "title": "HoopsHype NBA team salary pages",
                "url_template": HOOPSHYPE_TEAM_URL_TEMPLATE,
                "fetched_at": fetched_at(),
                "fallback_reason": f"Basketball-Reference returned HTTP {exc.code}: {exc.reason}",
            },
            "row_count": len(rows),
            "contracts": rows,
        }


def parse_bref_contracts(raw: str) -> list[dict[str, Any]]:
    table = extract_html_table(raw, "player-contracts")
    contracts: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr\b.*?</tr>", table, flags=re.S):
        cells = parse_cells(row_html)
        player_cell = cells.get("player")
        team_cell = cells.get("team_id")
        if not player_cell or not team_cell:
            continue
        player = player_cell["text"]
        if not player or player == "Player":
            continue
        seasons: list[dict[str, Any]] = []
        for key, season in BREF_SEASONS.items():
            cell = cells.get(key)
            salary = money_from_cell(cell)
            if salary is None:
                continue
            seasons.append(
                {
                    "season": season,
                    "salary": salary,
                    "option_type": option_type(cell or {}),
                    "raw": (cell or {}).get("text", ""),
                }
            )
        contracts.append(
            {
                "player": player,
                "normalized_name": normalize_name(player),
                "team_abbrev": team_cell["text"],
                "bref_id": player_cell.get("data_append_csv"),
                "seasons": seasons,
                "guaranteed": money_from_cell(cells.get("remain_gtd")),
                "source_url": BREF_CONTRACTS_URL,
            }
        )
    return contracts


def parse_hoopshype_salaries(raw: str) -> list[dict[str, Any]]:
    seasons = ["2025-26", "2026-27", "2027-28", "2028-29"]
    contracts: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr\b.*?</tr>", raw, flags=re.S):
        if "/salaries/players/" not in row_html:
            continue
        name_match = re.search(r'<a[^>]+href="(?P<href>/salaries/players/[^"]+)"[^>]*>.*?<div[^>]*>(?P<name>.*?)</div>', row_html, flags=re.S)
        if not name_match:
            continue
        player = clean_html(name_match.group("name"))
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.S)
        salary_cells = cells[2:6]
        player_seasons: list[dict[str, Any]] = []
        for season, cell in zip(seasons, salary_cells, strict=False):
            salary = money_from_text(clean_html(cell))
            if salary is None:
                continue
            player_seasons.append(
                {
                    "season": season,
                    "salary": salary,
                    "option_type": option_type_from_sup(cell),
                    "raw": clean_html(cell),
                }
            )
        contracts.append(
            {
                "player": player,
                "normalized_name": normalize_name(player),
                "team_abbrev": None,
                "source_player_path": name_match.group("href"),
                "seasons": player_seasons,
                "guaranteed": None,
                "source_url": HOOPSHYPE_SALARIES_URL,
            }
        )
    return contracts


def fetch_hoopshype_team_salaries() -> list[dict[str, Any]]:
    contracts_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for team_abbrev in sorted(HOOPSHYPE_TEAM_SLUG):
        url = HOOPSHYPE_TEAM_URL_TEMPLATE.format(team_slug=HOOPSHYPE_TEAM_SLUG[team_abbrev])
        raw = fetch_url(url)
        for contract in parse_hoopshype_team_contracts(raw, team_abbrev, url):
            contracts_by_key[(contract["normalized_name"], team_abbrev)] = contract
        time.sleep(0.2)
    return list(contracts_by_key.values())


def parse_hoopshype_team_contracts(raw: str, team_abbrev: str, source_url: str) -> list[dict[str, Any]]:
    try:
        entries = json.loads(extract_json_array(raw, '"contracts":'))
    except ValueError:
        return parse_hoopshype_salaries(raw)
    contracts: list[dict[str, Any]] = []
    for entry in entries:
        player = entry.get("playerName")
        if not player:
            continue
        seasons: list[dict[str, Any]] = []
        for season in sorted(entry.get("seasons", []), key=lambda item: item.get("season") or 0):
            salary = season.get("salary")
            year = int(season["season"])
            if year < 2025 or salary in (None, 0) or season.get("terminated"):
                continue
            option_type = None
            if season.get("playerOption"):
                option_type = "player_option"
            elif season.get("teamOption"):
                option_type = "team_option"
            elif season.get("qualifyingOffer"):
                option_type = "qualifying_offer"
            seasons.append(
                {
                    "season": f"{year}-{str(year + 1)[-2:]}",
                    "salary": int(salary),
                    "option_type": option_type,
                    "two_way_contract": bool(season.get("twoWayContract")),
                    "notes": season.get("notes") or "",
                }
            )
        if not seasons:
            continue
        contracts.append(
            {
                "player": player,
                "normalized_name": normalize_name(player),
                "team_abbrev": team_abbrev,
                "hoopshype_player_id": entry.get("playerID"),
                "update_date": entry.get("updateDate"),
                "seasons": seasons,
                "guaranteed": None,
                "source_url": source_url,
            }
        )
    return contracts


def fetch_staff() -> dict[str, Any]:
    teams: list[dict[str, Any]] = []
    fetched = fetched_at()
    for team_abbrev in sorted(TEAM_INFO):
        bref_abbrev = BREF_TEAM_ABBREV.get(team_abbrev, team_abbrev)
        url = BREF_TEAM_URL_TEMPLATE.format(team=bref_abbrev)
        try:
            raw = fetch_url(url)
            teams.append(parse_bref_team_staff(raw, team_abbrev, url))
        except urllib.error.HTTPError as exc:
            teams.append({"team_abbrev": team_abbrev, "source_url": url, "coach": None, "executive": None, "error": f"HTTP {exc.code}: {exc.reason}"})
            if exc.code == 429:
                time.sleep(5)
        except Exception as exc:
            teams.append({"team_abbrev": team_abbrev, "source_url": url, "coach": None, "executive": None, "error": f"{type(exc).__name__}: {exc}"})
        time.sleep(1.25)
    return {
        "source": {
            "id": "src_bref_team_pages_2026",
            "title": "Basketball-Reference 2025-26 team pages",
            "url_template": BREF_TEAM_URL_TEMPLATE,
            "fetched_at": fetched,
        },
        "team_count": len(teams),
        "teams": teams,
    }


def parse_bref_team_staff(raw: str, team_abbrev: str, url: str) -> dict[str, Any]:
    return {
        "team_abbrev": team_abbrev,
        "source_url": url,
        "coach": extract_labeled_anchor(raw, "Coach"),
        "executive": extract_labeled_anchor(raw, "Executive"),
    }


def fetch_espn_draft_picks() -> dict[str, Any]:
    raw = fetch_url(ESPN_DRAFT_TEAMS_URL)
    picks = json.loads(extract_json_array(raw, '"picks":'))
    team_map = parse_espn_team_map(raw)
    normalized = []
    for pick in picks:
        owner_abbrev = team_map.get(str(pick.get("teamId")))
        trade_note = pick.get("tradeNote")
        original_abbrev = infer_original_team(owner_abbrev, trade_note)
        normalized.append(
            {
                "season": "2026",
                "round": int(pick["round"]),
                "pick": int(pick["pick"]),
                "overall": int(pick["overall"]),
                "owner_team_abbrev": owner_abbrev,
                "original_team_abbrev": original_abbrev,
                "trade_note": trade_note,
                "status": pick.get("status"),
                "source_url": ESPN_DRAFT_TEAMS_URL,
            }
        )
    return {
        "source": {
            "id": "src_espn_2026_draft_picks",
            "title": "ESPN 2026 NBA draft team/pick board",
            "url": ESPN_DRAFT_TEAMS_URL,
            "fetched_at": fetched_at(),
        },
        "pick_count": len(normalized),
        "picks": normalized,
    }


def fetch_2026_draft_prospects() -> dict[str, Any]:
    fetched = fetched_at()
    tankathon_raw = fetch_url(TANKATHON_2026_MOCK_DRAFT_URL)
    prospects = parse_tankathon_mock_draft(tankathon_raw)
    rookie_scale_rows: list[dict[str, Any]] = []
    rookie_scale_error = None
    try:
        rookie_scale_rows = parse_rookie_scale_consensus(fetch_url(ROOKIE_SCALE_2026_CONSENSUS_URL))
    except Exception as exc:  # noqa: BLE001
        rookie_scale_error = f"{type(exc).__name__}: {exc}"
    consensus_by_name = {normalize_name(row["player"]): row for row in rookie_scale_rows}
    for prospect in prospects:
        consensus = consensus_by_name.get(prospect["normalized_name"])
        if not consensus:
            continue
        prospect["consensus_rank"] = consensus["rank"]
        prospect["rank_range"] = {
            "low": int(min(prospect["mock_rank"], consensus["rank"])),
            "high": int(max(prospect["mock_rank"], consensus["rank"])),
        }
        prospect["source_ids"] = sorted(dict.fromkeys([*prospect["source_ids"], "src_rookie_scale_2026_consensus_board"]))
        prospect["source_team"] = prospect.get("source_team") or consensus.get("source_team")
        prospect["age"] = prospect.get("age") if prospect.get("age") is not None else consensus.get("age")
        prospect["height"] = prospect.get("height") or consensus.get("height")
        prospect["weight_lbs"] = prospect.get("weight_lbs") or consensus.get("weight_lbs")
        prospect["notes"] = f"{prospect['notes']} Consensus board rank {consensus['rank']}."
    return {
        "source": {
            "id": "src_tankathon_2026_mock_draft",
            "title": "Tankathon 2026 NBA Mock Draft",
            "url": TANKATHON_2026_MOCK_DRAFT_URL,
            "fetched_at": fetched,
        },
        "sources": [
            {
                "id": "src_tankathon_2026_mock_draft",
                "title": "Tankathon 2026 NBA Mock Draft",
                "url": TANKATHON_2026_MOCK_DRAFT_URL,
            },
            {
                "id": "src_rookie_scale_2026_consensus_board",
                "title": "Rookie Scale 2026 NBA Draft Consensus Big Board",
                "url": ROOKIE_SCALE_2026_CONSENSUS_URL,
                "row_count": len(rookie_scale_rows),
                "error": rookie_scale_error,
            },
            {
                "id": "src_nba_2026_draft_board",
                "title": "NBA.com 2026 Draft Board",
                "url": NBA_2026_DRAFT_BOARD_URL,
                "notes": "Registered as a free public draft-board source for manual/corroborating review. V1 automated rows come from Tankathon and Rookie Scale because their HTML is consistently parseable.",
            },
        ],
        "prospect_count": len(prospects),
        "coverage_note": "V1 real 2026 prospect cache. Tankathon supplies mock order, physicals, class/team, and stat snippets; Rookie Scale consensus ranks are merged when matched by name. NBA.com draft board is registered for corroboration/manual review.",
        "prospects": prospects,
    }


def parse_tankathon_mock_draft(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_html in raw.split('<div class="mock-row">')[1:]:
        pick_match = re.search(r'class="mock-row-pick-number">(\d+)', row_html)
        name_match = re.search(r'<div class="mock-row-name">(.*?)</div>', row_html, flags=re.S)
        school_pos_match = re.search(r'<div class="mock-row-school-position">(.*?)</div>', row_html, flags=re.S)
        if not pick_match or not name_match or not school_pos_match:
            continue
        pick_no = int(pick_match.group(1))
        if pick_no > 60:
            continue
        name = clean_html(name_match.group(1))
        position, source_team = parse_tankathon_school_position(clean_html(school_pos_match.group(1)))
        measurement_match = re.search(r'<div class="mock-row-measurements">(.*?)</div>\s*</div>\s*<div class="mock-row-stats">', row_html, flags=re.S)
        measurement_values = re.findall(r"<div>(.*?)</div>", measurement_match.group(1), flags=re.S) if measurement_match else []
        measurement_text = [clean_html(value) for value in measurement_values]
        height = measurement_text[0] if len(measurement_text) > 0 else None
        weight = maybe_int((measurement_text[1] if len(measurement_text) > 1 else "").replace("lbs", "").strip())
        class_year = measurement_text[2] if len(measurement_text) > 2 else None
        age = maybe_number_or_none((measurement_text[3] if len(measurement_text) > 3 else "").replace("yrs", "").strip())
        rows.append(
            {
                "mock_rank": pick_no,
                "consensus_rank": None,
                "rank_range": {"low": pick_no, "high": pick_no},
                "player": name,
                "normalized_name": normalize_name(name),
                "position": position,
                "source_team": source_team,
                "league": "International" if class_year == "International" else "NCAA",
                "class_year": class_year,
                "age": age,
                "height": height,
                "weight_lbs": weight,
                "public_stats": parse_tankathon_stats(row_html),
                "source_ids": ["src_tankathon_2026_mock_draft"],
                "source_url": TANKATHON_2026_MOCK_DRAFT_URL,
                "notes": "Parsed from Tankathon 2026 mock draft public page.",
            }
        )
    return sorted(rows, key=lambda item: item["mock_rank"])


def parse_tankathon_school_position(text: str) -> tuple[str, str | None]:
    if "|" not in text:
        return text.strip() or "UNK", None
    position, source_team = text.split("|", 1)
    return position.strip() or "UNK", source_team.strip() or None


def parse_tankathon_stats(row_html: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for section_name, section_key in [("stats-per-game", "per_game"), ("stats-per-36", "per_36"), ("stats-advanced", "advanced")]:
        section_html = tankathon_stats_section(row_html, section_name)
        if not section_html:
            continue
        stats: dict[str, float] = {}
        for stat_match in re.finditer(r'<div class="stat [^"]+">.*?<div class="value[^"]*">(.*?)</div>\s*<div class="label">(.*?)</div>', section_html, flags=re.S):
            value = maybe_number_or_none(clean_html(stat_match.group(1)))
            label = clean_html(stat_match.group(2)).lower().replace("%", "pct")
            if value is not None:
                stats[label] = value
        output[section_key] = stats
    return output


def tankathon_stats_section(row_html: str, section_name: str) -> str:
    marker = f'<div class="{section_name}"'
    start = row_html.find(marker)
    if start < 0:
        return ""
    content_start = row_html.find(">", start)
    if content_start < 0:
        return ""
    content_start += 1
    next_sections = [idx for idx in [row_html.find('<div class="stats-', content_start)] if idx >= 0]
    stats_end = row_html.find("</div></div> </div>", content_start)
    if stats_end >= 0:
        next_sections.append(stats_end)
    end = min(next_sections) if next_sections else len(row_html)
    return row_html[content_start:end]


def parse_rookie_scale_consensus(raw: str) -> list[dict[str, Any]]:
    body_match = re.search(r"<tbody>(.*?)</tbody>", raw, flags=re.S)
    if not body_match:
        return []
    rows: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr>(.*?)</tr>", body_match.group(1), flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.S)
        if len(cells) < 8:
            continue
        player = clean_html(cells[1])
        if not player:
            continue
        rows.append(
            {
                "rank": int(clean_html(cells[0])),
                "player": player,
                "normalized_name": normalize_name(player),
                "age": maybe_number_or_none(clean_html(cells[2])),
                "source_team": clean_html(cells[3]),
                "class_year": clean_html(cells[4]),
                "position": clean_html(cells[5]),
                "height": clean_html(cells[6]),
                "weight_lbs": maybe_int(clean_html(cells[7])),
                "source_url": ROOKIE_SCALE_2026_CONSENSUS_URL,
            }
        )
    return rows


def fetch_spotrac_future_picks() -> dict[str, Any]:
    raw = fetch_url(SPOTRAC_FUTURE_PICKS_JINA_URL)
    picks = parse_spotrac_future_picks(raw)
    return {
        "source": {
            "id": "src_spotrac_future_picks",
            "title": "Spotrac NBA Future Draft Picks",
            "url": SPOTRAC_FUTURE_PICKS_URL,
            "fetched_via": SPOTRAC_FUTURE_PICKS_JINA_URL,
            "fetched_at": fetched_at(),
        },
        "pick_count": len(picks),
        "coverage_note": "Machine-ingested owner-side first-round future-pick assets from Spotrac's public future picks page. Second-round ownership remains scaffolded unless separately researched.",
        "picks": picks,
    }


def parse_spotrac_future_picks(raw: str) -> list[dict[str, Any]]:
    team_names = {name: abbrev for abbrev, (name, _, _) in TEAM_INFO.items()}
    starts: list[tuple[int, str, str]] = []
    for name, abbrev in team_names.items():
        marker = f"\n{name}\n"
        idx = raw.find(marker)
        if idx >= 0:
            starts.append((idx + 1, name, abbrev))
    starts.sort()

    picks: list[dict[str, Any]] = []
    for index, (start, name, owner_abbrev) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(raw)
        block = raw[start:end]
        year_matches = list(re.finditer(r"(?m)^(202[6-9]|203[0-3])$", block))
        for year_index, match in enumerate(year_matches):
            year = match.group(1)
            next_start = year_matches[year_index + 1].start() if year_index + 1 < len(year_matches) else len(block)
            if year < "2027" or year > "2032":
                continue
            entries = parse_spotrac_year_entries(block[match.end() : next_start])
            for entry_index, entry in enumerate(entries, start=1):
                original_abbrev = normalize_spotrac_abbrev(first_abbrev_token(entry))
                picks.append(
                    {
                        "season": year,
                        "round": 1,
                        "asset_index": entry_index,
                        "owner_team_abbrev": owner_abbrev,
                        "original_team_abbrev": original_abbrev,
                        "description": entry,
                        "source_url": SPOTRAC_FUTURE_PICKS_URL,
                    }
                )
    return picks


def parse_spotrac_year_entries(text: str) -> list[str]:
    groups: list[str] = []
    current: list[str] = []
    for raw_line in text.splitlines():
        line = clean_html(raw_line).strip()
        if not line:
            if current:
                groups.append(" ".join(current))
                current = []
            continue
        if is_spotrac_pick_number_header(line) or re.fullmatch(r"\d+(?:\s*\+\s*\d+)?", line):
            continue
        current.append(line)
    if current:
        groups.append(" ".join(current))
    return [re.sub(r"\s+", " ", group).strip(" ;") for group in groups if group.strip(" ;")]


def is_spotrac_pick_number_header(line: str) -> bool:
    tokens = line.replace("\t", " ").split()
    return tokens == [str(number) for number in range(1, 31)]


def first_abbrev_token(text: str) -> str | None:
    match = re.search(r"\b[A-Z]{2,3}\b", text)
    return match.group(0) if match else None


def normalize_spotrac_abbrev(abbrev: str | None) -> str | None:
    if not abbrev:
        return None
    return {
        "BRK": "BKN",
        "GOS": "GSW",
        "SAN": "SAS",
        "UTH": "UTA",
    }.get(abbrev, abbrev)


def fetch_game_boxscores(root: Path, limit: int | None = None, missing_only: bool = True) -> dict[str, Any]:
    schedule = json.loads((root / "NBA Schedule/schedule_v2025_2026.json").read_text(encoding="utf-8"))["games"]
    minutes_path = root / "NBA Schedule/real_game_minutes_2025_26.json"
    existing_minutes = json.loads(minutes_path.read_text(encoding="utf-8")) if minutes_path.exists() else {}
    existing_boxscores = existing_game_boxscores(root) if missing_only else {}
    candidates = [game for game in schedule if not missing_only or str(game["externalGameId"]) not in existing_boxscores]
    if limit is not None:
        candidates = candidates[:limit]
    games_by_id: dict[str, dict[str, Any]] = dict(existing_boxscores)
    failures: list[dict[str, str]] = []
    seen_game_ids: set[str] = set(existing_boxscores)
    for game in candidates:
        game_id = str(game["externalGameId"])
        try:
            raw = fetch_url(ESPN_SUMMARY_URL_TEMPLATE.format(game_id=game_id))
            games_by_id[game_id] = parse_espn_summary_boxscore(raw, game)
            seen_game_ids.add(game_id)
            time.sleep(0.05)
        except Exception as exc:  # noqa: BLE001
            failures.append({"game_id": game_id, "error": f"{type(exc).__name__}: {exc}"})
    playoff_events = fetch_espn_scoreboard_events(date(2026, 4, 18), min(date.today(), date(2026, 6, 30)))
    if limit is not None:
        playoff_events = playoff_events[: max(0, limit - len(candidates))]
    for event in playoff_events:
        game_id = str(event.get("id"))
        if game_id in seen_game_ids:
            continue
        try:
            raw = fetch_url(ESPN_SUMMARY_URL_TEMPLATE.format(game_id=game_id))
            games_by_id[game_id] = parse_espn_summary_boxscore(raw, schedule_game_from_espn_event(event))
            seen_game_ids.add(game_id)
            time.sleep(0.05)
        except Exception as exc:  # noqa: BLE001
            failures.append({"game_id": game_id, "error": f"{type(exc).__name__}: {exc}"})
    games = sorted(games_by_id.values(), key=lambda item: (item.get("date") or "", str(item.get("game_id") or "")))
    return {
        "source": {
            "id": "src_espn_game_boxscores_2025_26",
            "title": "ESPN NBA game summary box scores",
            "url_template": ESPN_SUMMARY_URL_TEMPLATE,
            "fetched_at": fetched_at(),
        },
        "mode": "missing_only" if missing_only else "full_schedule",
        "schedule_game_count": len(schedule),
        "existing_minutes_game_count": len(existing_minutes),
        "existing_boxscore_game_count": len(existing_boxscores),
        "attempted_game_count": len(candidates),
        "game_count": len(games),
        "failure_count": len(failures),
        "playoff_event_count": len(playoff_events),
        "failures": failures,
        "games": games,
    }


def existing_game_boxscores(root: Path) -> dict[str, dict[str, Any]]:
    path = root / GAME_BOXSCORES_FILE
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(game["game_id"]): game for game in payload.get("games", []) if game.get("game_id")}


def fetch_espn_betting_odds(root: Path, limit: int | None = None, secondary_limit: int | None = 80) -> dict[str, Any]:
    candidates = betting_odds_candidates(root)
    if limit is not None:
        candidates = candidates[:limit]
    games_by_id: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    for candidate in candidates:
        game_id = str(candidate["externalGameId"])
        try:
            raw = fetch_url(ESPN_SUMMARY_URL_TEMPLATE.format(game_id=game_id))
            record = parse_espn_summary_betting_odds(raw, candidate)
            if record:
                games_by_id[game_id] = record
            time.sleep(0.04)
        except Exception as exc:  # noqa: BLE001
            failures.append({"game_id": game_id, "error": f"{type(exc).__name__}: {exc}"})
    preserved_existing_records = merge_existing_odds(root, games_by_id)
    fantasydata_rows = fetch_fantasydata_nba_odds(root, candidates)
    filled_from_fantasydata = 0
    augmented_from_fantasydata = 0
    for record in fantasydata_rows:
        game_id = str(record["game_id"])
        existing = games_by_id.get(game_id)
        if not existing:
            games_by_id[game_id] = record
            filled_from_fantasydata += 1
        elif odds_record_is_less_complete(existing, record):
            games_by_id[game_id] = merge_odds_records(existing, record)
            augmented_from_fantasydata += 1
    fox_candidates = [candidate for candidate in candidates if str(candidate["externalGameId"]) not in games_by_id or not games_by_id[str(candidate["externalGameId"])].get("favorite_team_abbrev")]
    if secondary_limit is not None:
        fox_candidates = fox_candidates[:secondary_limit]
    fox_rows = fetch_foxsports_odds(fox_candidates)
    filled_from_fox = 0
    augmented_from_fox = 0
    for record in fox_rows:
        game_id = str(record["game_id"])
        existing = games_by_id.get(game_id)
        if not existing:
            games_by_id[game_id] = record
            filled_from_fox += 1
        elif odds_record_is_less_complete(existing, record) or (record.get("player_props") and not existing.get("player_props")):
            games_by_id[game_id] = merge_odds_records(existing, record)
            augmented_from_fox += 1
    missing = missing_betting_odds(candidates, games_by_id)
    games = list(games_by_id.values())
    return {
        "format": "provider_neutral_v1",
        "source": {
            "id": "src_espn_pickcenter_betting_odds_2025_26",
            "title": "ESPN PickCenter odds from NBA game summary endpoint",
            "url_template": ESPN_SUMMARY_URL_TEMPLATE,
            "fetched_at": fetched_at(),
        },
        "sources": [
            {
                "id": "src_espn_pickcenter_betting_odds_2025_26",
                "title": "ESPN PickCenter odds from NBA game summary endpoint",
                "url_template": ESPN_SUMMARY_URL_TEMPLATE,
            },
            {
                "id": "src_fantasydata_public_nba_odds_2025_26",
                "title": "FantasyData public NBA odds table",
                "url": FANTASYDATA_NBA_ODDS_URL,
            },
            {
                "id": "src_foxsports_nba_odds_articles_2025_26",
                "title": "FOX Sports NBA prediction/odds articles",
                "url_template": FOXSPORTS_ARTICLE_URL_TEMPLATE,
            },
        ],
        "attempted_game_count": len(candidates),
        "game_count": len(games),
        "missing_game_count": len(missing),
        "failure_count": len(failures),
        "fantasydata_row_count": len(fantasydata_rows),
        "filled_from_fantasydata_count": filled_from_fantasydata,
        "augmented_from_fantasydata_count": augmented_from_fantasydata,
        "preserved_existing_record_count": preserved_existing_records,
        "foxsports_row_count": len(fox_rows),
        "foxsports_attempted_game_count": len(fox_candidates),
        "foxsports_secondary_limit": secondary_limit,
        "filled_from_foxsports_count": filled_from_fox,
        "augmented_from_foxsports_count": augmented_from_fox,
        "coverage_note": "Odds are cached from free public sources only when real rows are exposed. ESPN PickCenter is the primary layer; FantasyData's public odds table and FOX Sports odds articles are secondary gap-fillers. Missing games are tracked explicitly rather than inferred.",
        "games": sorted(games, key=lambda item: (item.get("date") or "", str(item["game_id"]))),
        "missing_games": missing,
        "failures": failures,
    }


def betting_odds_candidates(root: Path) -> list[dict[str, Any]]:
    schedule_path = root / "NBA Schedule/schedule_v2025_2026.json"
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))["games"] if schedule_path.exists() else []
    candidates_by_id: dict[str, dict[str, Any]] = {}
    for game in schedule:
        candidates_by_id[str(game["externalGameId"])] = {
            "externalGameId": str(game["externalGameId"]),
            "gameDate": game.get("gameDate"),
            "phase": game.get("phase") or "regular",
            "homeTeamId": game.get("homeTeamId"),
            "awayTeamId": game.get("awayTeamId"),
        }
    boxscore_path = root / GAME_BOXSCORES_FILE
    if boxscore_path.exists():
        for game in json.loads(boxscore_path.read_text(encoding="utf-8")).get("games", []):
            game_id = str(game["game_id"])
            candidates_by_id.setdefault(
                game_id,
                {
                    "externalGameId": game_id,
                    "gameDate": game.get("date"),
                    "phase": game.get("phase"),
                    "round": game.get("round"),
                    "homeTeamId": game.get("home_team_id"),
                    "awayTeamId": game.get("away_team_id"),
                },
            )
    return sorted(candidates_by_id.values(), key=lambda item: (item.get("gameDate") or "", str(item["externalGameId"])))


def merge_existing_odds(root: Path, games_by_id: dict[str, dict[str, Any]]) -> int:
    path = root / BETTING_ODDS_FILE
    if not path.exists():
        return 0
    try:
        existing_games = json.loads(path.read_text(encoding="utf-8")).get("games", [])
    except json.JSONDecodeError:
        return 0
    preserved = 0
    for record in existing_games:
        game_id = str(record.get("game_id"))
        existing = games_by_id.get(game_id)
        if not existing:
            games_by_id[game_id] = record
            preserved += 1
        elif odds_record_is_less_complete(existing, record) or (record.get("player_props") and not existing.get("player_props")):
            games_by_id[game_id] = merge_odds_records(existing, record)
            preserved += 1
    return preserved


def parse_espn_summary_betting_odds(raw: str, schedule_game: dict[str, Any]) -> dict[str, Any] | None:
    data = json.loads(raw)
    pick = first_pickcenter_entry(data)
    if not pick:
        return None
    home_odds = pick.get("homeTeamOdds") or {}
    away_odds = pick.get("awayTeamOdds") or {}
    home_abbrev = odds_team_abbrev(home_odds) or team_abbrev_from_espn_id(schedule_game.get("homeTeamId"))
    away_abbrev = odds_team_abbrev(away_odds) or team_abbrev_from_espn_id(schedule_game.get("awayTeamId"))
    home_moneyline = maybe_int(home_odds.get("moneyLine"))
    away_moneyline = maybe_int(away_odds.get("moneyLine"))
    favorite_home = bool(home_odds.get("favorite"))
    favorite_away = bool(away_odds.get("favorite"))
    if not favorite_home and not favorite_away and home_moneyline is not None and away_moneyline is not None:
        favorite_home = home_moneyline < away_moneyline
        favorite_away = away_moneyline < home_moneyline
    favorite_abbrev = home_abbrev if favorite_home else away_abbrev if favorite_away else None
    underdog_abbrev = away_abbrev if favorite_home else home_abbrev if favorite_away else None
    spread = maybe_number_or_none(pick.get("spread"))
    spread_payload = {}
    if spread is not None and favorite_abbrev:
        favorite_line = -abs(float(spread))
        underdog_line = abs(float(spread))
        spread_payload = {
            "home_line": favorite_line if favorite_home else underdog_line,
            "away_line": favorite_line if favorite_away else underdog_line,
        }
    elif spread is not None:
        spread_payload = {"home_line": float(spread), "away_line": -float(spread)}
    total_payload = {}
    total_line = maybe_number_or_none(pick.get("overUnder"))
    if total_line is not None:
        total_payload = {
            "line": total_line,
            "over_american": maybe_int(pick.get("overOdds")),
            "under_american": maybe_int(pick.get("underOdds")),
        }
    return {
        "game_id": str(schedule_game["externalGameId"]),
        "date": schedule_game.get("gameDate"),
        "phase": schedule_game.get("phase") or phase_from_competition(data),
        "round": schedule_game.get("round"),
        "provider": "espn_pickcenter",
        "book": (pick.get("provider") or {}).get("name") or "ESPN PickCenter",
        "source_ids": ["src_espn_pickcenter_betting_odds_2025_26"],
        "open_timestamp": None,
        "close_timestamp": None,
        "home_team_abbrev": home_abbrev,
        "away_team_abbrev": away_abbrev,
        "favorite_team_abbrev": favorite_abbrev,
        "underdog_team_abbrev": underdog_abbrev,
        "moneyline": {"home_american": home_moneyline, "away_american": away_moneyline},
        "spread": spread_payload,
        "total": total_payload,
        "player_props": [],
        "raw_details": pick.get("details"),
        "source_url": ESPN_SUMMARY_URL_TEMPLATE.format(game_id=schedule_game["externalGameId"]),
    }


def fetch_fantasydata_nba_odds(root: Path, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        raw = fetch_url(FANTASYDATA_NBA_ODDS_URL)
    except Exception:
        return []
    by_matchup = candidate_matchup_index(candidates)
    rows = []
    for row in parse_fantasydata_odds_rows(raw):
        game = by_matchup.get((row["date"], row["away_team_abbrev"], row["home_team_abbrev"]))
        if not game:
            continue
        rows.append(
            {
                "game_id": str(game["externalGameId"]),
                "date": row["date"],
                "phase": game.get("phase") or "regular",
                "round": game.get("round"),
                "provider": "fantasydata_public_table",
                "book": "FantasyData Consensus",
                "source_ids": ["src_fantasydata_public_nba_odds_2025_26"],
                "open_timestamp": None,
                "close_timestamp": None,
                "home_team_abbrev": row["home_team_abbrev"],
                "away_team_abbrev": row["away_team_abbrev"],
                "favorite_team_abbrev": row["favorite_team_abbrev"],
                "underdog_team_abbrev": row["underdog_team_abbrev"],
                "moneyline": {"home_american": row["home_moneyline"], "away_american": row["away_moneyline"]},
                "spread": {"home_line": row["home_spread"], "away_line": row["away_spread"]},
                "total": {"line": row["total"], "over_american": row["over_american"], "under_american": row["under_american"]},
                "player_props": [],
                "raw_details": row["raw"],
                "source_url": FANTASYDATA_NBA_ODDS_URL,
            }
        )
    return rows


def fetch_foxsports_odds(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for candidate in candidates:
        for url in foxsports_candidate_urls(candidate):
            try:
                raw = fetch_url_once(url, timeout=8)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    continue
                continue
            except Exception:
                continue
            record = parse_foxsports_odds_article(raw, candidate, url)
            if record:
                rows.append(record)
                break
            time.sleep(0.03)
        time.sleep(0.03)
    return rows


def foxsports_candidate_urls(candidate: dict[str, Any]) -> list[str]:
    game_date = candidate.get("gameDate")
    away = team_abbrev_from_espn_id(candidate.get("awayTeamId"))
    home = team_abbrev_from_espn_id(candidate.get("homeTeamId"))
    if not game_date or not away or not home:
        return []
    try:
        parsed_date = datetime.fromisoformat(game_date).date()
    except ValueError:
        return []
    month_day = f"{parsed_date.strftime('%b').lower()}-{parsed_date.day}"
    away_slug = TEAM_NICKNAME_SLUG[away][1]
    home_slug = TEAM_NICKNAME_SLUG[home][1]
    slugs = [f"{away_slug}-vs-{home_slug}", f"{home_slug}-vs-{away_slug}"]
    return [FOXSPORTS_ARTICLE_URL_TEMPLATE.format(slug=slug, month_day=month_day) for slug in slugs]


def parse_foxsports_odds_article(raw: str, candidate: dict[str, Any], source_url: str) -> dict[str, Any] | None:
    away = team_abbrev_from_espn_id(candidate.get("awayTeamId"))
    home = team_abbrev_from_espn_id(candidate.get("homeTeamId"))
    if not away or not home:
        return None
    table_match = re.search(r"<caption>.*?Betting</a> Information</caption>.*?<tbody>\s*<tr>(?P<row>.*?)</tr>", raw, flags=re.S)
    if not table_match:
        return None
    cells = re.findall(r"<td\b[^>]*>(.*?)</td>", table_match.group("row"), flags=re.S)
    if len(cells) < 9:
        return None
    favorite_name = clean_html(cells[0])
    favorite_abbrev = foxsports_favorite_abbrev(favorite_name, [away, home])
    if not favorite_abbrev:
        return None
    underdog_abbrev = home if favorite_abbrev == away else away
    favorite_spread = parse_signed_float(clean_html(cells[1]))
    favorite_spread_odds = maybe_int(clean_html(cells[2]))
    underdog_spread_odds = maybe_int(clean_html(cells[3]))
    total = parse_signed_float(clean_html(cells[4]))
    over_american = maybe_int(clean_html(cells[5]))
    under_american = maybe_int(clean_html(cells[6]))
    favorite_moneyline = maybe_int(clean_html(cells[7]))
    underdog_moneyline = maybe_int(clean_html(cells[8]))
    home_is_favorite = favorite_abbrev == home
    return {
        "game_id": str(candidate["externalGameId"]),
        "date": candidate.get("gameDate"),
        "phase": candidate.get("phase") or "regular",
        "round": candidate.get("round"),
        "provider": "foxsports_article",
        "book": "FOX Sports/Sportradar",
        "source_ids": ["src_foxsports_nba_odds_articles_2025_26"],
        "open_timestamp": None,
        "close_timestamp": None,
        "home_team_abbrev": home,
        "away_team_abbrev": away,
        "favorite_team_abbrev": favorite_abbrev,
        "underdog_team_abbrev": underdog_abbrev,
        "moneyline": {
            "home_american": favorite_moneyline if home_is_favorite else underdog_moneyline,
            "away_american": favorite_moneyline if not home_is_favorite else underdog_moneyline,
        },
        "spread": {
            "home_line": favorite_spread if home_is_favorite else -favorite_spread if favorite_spread is not None else None,
            "away_line": favorite_spread if not home_is_favorite else -favorite_spread if favorite_spread is not None else None,
            "home_american": favorite_spread_odds if home_is_favorite else underdog_spread_odds,
            "away_american": favorite_spread_odds if not home_is_favorite else underdog_spread_odds,
        },
        "total": {"line": total, "over_american": over_american, "under_american": under_american},
        "player_props": parse_foxsports_points_props(raw, source_url),
        "raw_details": f"{TEAM_NICKNAME_SLUG[favorite_abbrev][0]} {favorite_spread}" if favorite_spread is not None else None,
        "source_url": source_url,
    }


def foxsports_favorite_abbrev(favorite_name: str, team_abbrevs: list[str]) -> str | None:
    normalized = normalize_name(favorite_name)
    for abbrev in team_abbrevs:
        nickname = TEAM_NICKNAME_SLUG[abbrev][0]
        if normalize_name(nickname) == normalized:
            return abbrev
    return None


def parse_foxsports_points_props(raw: str, source_url: str) -> list[dict[str, Any]]:
    props = []
    sections = re.findall(r"<h2[^>]*>[^<]*Player Props</h2>.*?<tbody>(?P<tbody>.*?)</tbody>", raw, flags=re.S)
    for section in sections:
        for row in re.findall(r"<tr>\s*(.*?)</tr>", section, flags=re.S):
            name_match = re.search(r"<th\b[^>]*>(?P<name>.*?)</th>", row, flags=re.S)
            cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.S)
            if not name_match or len(cells) < 2:
                continue
            player_name = clean_html(name_match.group("name"))
            line = parse_signed_float(clean_html(cells[0]))
            over_american = maybe_int(clean_html(cells[1]))
            if player_name and line is not None:
                props.append(
                    {
                        "player_name": player_name,
                        "market": "points",
                        "line": line,
                        "over_american": over_american,
                        "under_american": None,
                        "source_url": source_url,
                    }
                )
    return props


def parse_fantasydata_odds_rows(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    table_start = raw.find("<tbody>")
    table_end = raw.find("</tbody>", table_start)
    if table_start < 0 or table_end < 0:
        return rows
    table = raw[table_start:table_end]
    for row_html in re.findall(r"<tr\b.*?</tr>", table, flags=re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.S)
        if len(cells) < 14:
            continue
        away = fantasydata_team_abbrev(cells[0])
        home = fantasydata_team_abbrev(cells[1])
        game_date = parse_fantasydata_date(clean_html(cells[2]))
        if not away or not home or not game_date:
            continue
        away_spread = parse_signed_float(clean_html(cells[5]))
        away_spread_pay = maybe_int(clean_html(cells[6]))
        home_spread = parse_signed_float(clean_html(cells[7]))
        home_spread_pay = maybe_int(clean_html(cells[8]))
        away_moneyline = maybe_int(clean_html(cells[9]))
        home_moneyline = maybe_int(clean_html(cells[10]))
        total = parse_signed_float(clean_html(cells[11]))
        over_american = maybe_int(clean_html(cells[12]))
        under_american = maybe_int(clean_html(cells[13]))
        favorite = None
        underdog = None
        if away_moneyline is not None and home_moneyline is not None:
            favorite = away if away_moneyline < home_moneyline else home
            underdog = home if favorite == away else away
        rows.append(
            {
                "date": game_date,
                "away_team_abbrev": away,
                "home_team_abbrev": home,
                "away_spread": away_spread,
                "away_spread_pay": away_spread_pay,
                "home_spread": home_spread,
                "home_spread_pay": home_spread_pay,
                "away_moneyline": away_moneyline,
                "home_moneyline": home_moneyline,
                "favorite_team_abbrev": favorite,
                "underdog_team_abbrev": underdog,
                "total": total,
                "over_american": over_american,
                "under_american": under_american,
                "raw": clean_html(row_html),
            }
        )
    return rows


def candidate_matchup_index(candidates: list[dict[str, Any]]) -> dict[tuple[str, str | None, str | None], dict[str, Any]]:
    return {
        (candidate.get("gameDate"), team_abbrev_from_espn_id(candidate.get("awayTeamId")), team_abbrev_from_espn_id(candidate.get("homeTeamId"))): candidate
        for candidate in candidates
    }


def fantasydata_team_abbrev(cell: str) -> str | None:
    match = re.search(r"<span class=['\"]md-show['\"]>([A-Z]{2,4})</span>", cell)
    if match:
        return normalize_espn_abbrev(match.group(1))
    text = clean_html(cell)
    match = re.search(r"\b([A-Z]{2,4})$", text)
    return normalize_espn_abbrev(match.group(1)) if match else None


def parse_fantasydata_date(value: str) -> str | None:
    try:
        return datetime.strptime(value, "%b %d, %Y").date().isoformat()
    except ValueError:
        return None


def parse_signed_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace("+", ""))
    except ValueError:
        return None


def odds_record_is_less_complete(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    existing_fields = count_odds_fields(existing)
    candidate_fields = count_odds_fields(candidate)
    return candidate_fields > existing_fields


def count_odds_fields(record: dict[str, Any]) -> int:
    fields = [
        record.get("favorite_team_abbrev"),
        record.get("underdog_team_abbrev"),
        (record.get("moneyline") or {}).get("home_american"),
        (record.get("moneyline") or {}).get("away_american"),
        (record.get("spread") or {}).get("home_line"),
        (record.get("spread") or {}).get("away_line"),
        (record.get("total") or {}).get("line"),
        (record.get("total") or {}).get("over_american"),
        (record.get("total") or {}).get("under_american"),
    ]
    return sum(value is not None for value in fields)


def merge_odds_records(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key in ["favorite_team_abbrev", "underdog_team_abbrev"]:
        if not merged.get(key) and candidate.get(key):
            merged[key] = candidate[key]
    for key in ["moneyline", "spread", "total"]:
        merged_payload = dict(merged.get(key) or {})
        for sub_key, value in (candidate.get(key) or {}).items():
            if merged_payload.get(sub_key) is None and value is not None:
                merged_payload[sub_key] = value
        merged[key] = merged_payload
    merged["source_ids"] = sorted(set((merged.get("source_ids") or []) + (candidate.get("source_ids") or [])))
    merged["secondary_sources"] = sorted(set((merged.get("secondary_sources") or []) + [candidate.get("provider")]))
    return merged


def missing_betting_odds(candidates: list[dict[str, Any]], games_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    missing = []
    for candidate in candidates:
        game_id = str(candidate["externalGameId"])
        record = games_by_id.get(game_id)
        if record and record.get("favorite_team_abbrev") and record.get("underdog_team_abbrev"):
            continue
        missing.append(
            {
                "game_id": game_id,
                "date": candidate.get("gameDate"),
                "home_team_abbrev": team_abbrev_from_espn_id(candidate.get("homeTeamId")),
                "away_team_abbrev": team_abbrev_from_espn_id(candidate.get("awayTeamId")),
                "reason": "missing_favorite_underdog_from_free_sources" if record else "no_odds_exposed_by_free_sources",
            }
        )
    return missing


def first_pickcenter_entry(data: dict[str, Any]) -> dict[str, Any] | None:
    for entry in data.get("pickcenter") or []:
        if entry.get("homeTeamOdds") or entry.get("awayTeamOdds") or entry.get("spread") is not None:
            return entry
    return None


def odds_team_abbrev(team_odds: dict[str, Any]) -> str | None:
    team_id = team_odds.get("teamId") or team_odds.get("team", {}).get("id")
    return team_abbrev_from_espn_id(team_id)


def team_abbrev_from_espn_id(team_id: Any) -> str | None:
    if team_id is None:
        return None
    return ESPN_TEAM_ID_TO_ABBREV.get(str(team_id))


def maybe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def maybe_number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_espn_scoreboard_events(start: date, end: date) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    current = start
    while current <= end:
        payload = json.loads(fetch_url(ESPN_SCOREBOARD_URL_TEMPLATE.format(date=current.strftime("%Y%m%d"))))
        for event in payload.get("events", []):
            if str(event.get("season", {}).get("type")) == "3":
                events.append(event)
        current += timedelta(days=1)
        time.sleep(0.03)
    return events


def schedule_game_from_espn_event(event: dict[str, Any]) -> dict[str, Any]:
    competitors = (event.get("competitions") or [{}])[0].get("competitors") or []
    by_home_away = {competitor.get("homeAway"): competitor for competitor in competitors}
    return {
        "externalGameId": str(event["id"]),
        "gameDate": str(event.get("date", ""))[:10],
        "phase": "playoffs",
        "round": event.get("name") or event.get("shortName"),
        "homeTeamId": by_home_away.get("home", {}).get("team", {}).get("id"),
        "awayTeamId": by_home_away.get("away", {}).get("team", {}).get("id"),
        "status": event.get("status", {}).get("type", {}).get("name"),
    }


def parse_espn_summary_boxscore(raw: str, schedule_game: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(raw)
    players: list[dict[str, Any]] = []
    teams: list[dict[str, Any]] = []
    for team_entry in data.get("boxscore", {}).get("teams", []):
        team = team_entry.get("team", {})
        stats = {item.get("name") or item.get("label"): item.get("displayValue") for item in team_entry.get("statistics", [])}
        teams.append({"team_abbrev": team.get("abbreviation"), "team_id": team.get("id"), "display_name": team.get("displayName"), "home_away": team_entry.get("homeAway"), "stats": stats})
    for team_block in data.get("boxscore", {}).get("players", []):
        team_abbrev = team_block.get("team", {}).get("abbreviation")
        for stat_group in team_block.get("statistics", []):
            keys = stat_group.get("keys") or stat_group.get("names") or []
            for athlete in stat_group.get("athletes", []):
                row = dict(zip(keys, athlete.get("stats", []), strict=False))
                player = athlete.get("athlete", {})
                players.append(
                    {
                        "player_name": player.get("displayName"),
                        "espn_player_id": player.get("id"),
                        "team_abbrev": team_abbrev,
                        "starter": bool(athlete.get("starter")),
                        "dnp": bool(athlete.get("didNotPlay")) or (not bool(athlete.get("active", True)) and parse_minutes(row.get("minutes") or row.get("MIN")) == 0),
                        "comment": athlete.get("reason"),
                        **parse_boxscore_stat_row(row),
                    }
                )
    competition = (data.get("header", {}).get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []
    return {
        "game_id": str(schedule_game["externalGameId"]),
        "date": schedule_game["gameDate"],
        "phase": schedule_game.get("phase") or phase_from_competition(data),
        "round": schedule_game.get("round"),
        "home_team_id": str(schedule_game.get("homeTeamId")),
        "away_team_id": str(schedule_game.get("awayTeamId")),
        "status": competition.get("status", {}).get("type", {}).get("name") or schedule_game.get("status"),
        "home_score": score_for_home_away(competitors, "home"),
        "away_score": score_for_home_away(competitors, "away"),
        "teams": teams,
        "players": players,
    }


def parse_boxscore_stat_row(row: dict[str, str]) -> dict[str, Any]:
    fgm, fga = parse_made_attempt(row.get("fg") or row.get("FG"))
    fg3m, fg3a = parse_made_attempt(row.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted") or row.get("3PT"))
    ftm, fta = parse_made_attempt(row.get("freeThrowsMade-freeThrowsAttempted") or row.get("FT"))
    return {
        "minutes": parse_minutes(row.get("minutes") or row.get("MIN")),
        "points": parse_int(row.get("points") or row.get("PTS")),
        "rebounds": parse_int(row.get("rebounds") or row.get("REB")),
        "assists": parse_int(row.get("assists") or row.get("AST")),
        "turnovers": parse_int(row.get("turnovers") or row.get("TO")),
        "steals": parse_int(row.get("steals") or row.get("STL")),
        "blocks": parse_int(row.get("blocks") or row.get("BLK")),
        "oreb": parse_int(row.get("offensiveRebounds") or row.get("OREB")),
        "dreb": parse_int(row.get("defensiveRebounds") or row.get("DREB")),
        "pf": parse_int(row.get("fouls") or row.get("PF")),
        "fgm": fgm,
        "fga": fga,
        "fg3m": fg3m,
        "fg3a": fg3a,
        "ftm": ftm,
        "fta": fta,
        "plus_minus": parse_int(row.get("plusMinus") or row.get("+/-")),
    }


def parse_minutes(value: str | None) -> float:
    if not value or value == "--":
        return 0.0
    if ":" in value:
        minutes, seconds = value.split(":", 1)
        return round((float(minutes or 0) + float(seconds or 0) / 60), 2)
    return maybe_number(value)


def parse_int(value: str | None) -> int:
    if not value or value == "--":
        return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def parse_made_attempt(value: str | None) -> tuple[int, int]:
    if not value or value == "--" or "-" not in value:
        return 0, 0
    made, attempted = value.split("-", 1)
    return parse_int(made), parse_int(attempted)


def maybe_number(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return round(float(value), 2)
    except ValueError:
        return 0.0


def score_for_home_away(competitors: list[dict[str, Any]], home_away: str) -> int | None:
    for competitor in competitors:
        if competitor.get("homeAway") == home_away:
            return parse_int(competitor.get("score"))
    return None


def phase_from_competition(data: dict[str, Any]) -> str:
    season_type = str(data.get("header", {}).get("season", {}).get("type") or "")
    if season_type == "3":
        return "playoffs"
    if season_type == "2":
        return "regular"
    return "unknown"


def build_coach_reputation_sources() -> dict[str, Any]:
    return {
        "source": {"id": "src_coach_reputation_sources_2025_26", "title": "Coach reputation source bundle 2025-26", "fetched_at": fetched_at()},
        "rating_scale": "0_to_5_stars",
        "attributes": ["rotation_trust", "development", "offensive_structure", "defensive_structure", "matchup_adjustments", "player_buy_in", "playoff_preparation", "experimentation", "hands_on_control"],
        "sources": [
            {"id": "src_si_coach_rankings_2025_26", "title": "Sports Illustrated NBA 100 coach rankings", "url": SI_COACH_RANKINGS_URL},
            {"id": "src_cbs_coach_tiers_2025_26", "title": "CBS Sports NBA coach tiers", "url": CBS_COACH_TIERS_URL},
            {"id": "src_bref_coaches_2025_26", "title": "Basketball-Reference 2025-26 NBA coaches", "url": BREF_COACHES_URL},
        ],
        "notes": "Soft reputation inputs for coach ratings. Ratings are intentionally modest and tunable; they should influence scheme, rotations, and development without overpowering player quality.",
    }


def build_tracking_source_registry() -> dict[str, Any]:
    return {
        "source": {"id": "src_tracking_sources_2025_26", "title": "NBA tracking source registry 2025-26", "url": NBA_STATS_TRACKING_QUICKLINKS_URL, "fetched_at": fetched_at()},
        "categories": ["touches", "drives", "speed_distance", "passing", "defensive_impact", "shot_dashboard", "hustle", "catch_and_shoot", "pull_up_shooting", "rebounding"],
        "notes": "Registry for tracking/stat dashboards that should feed future feature extraction where accessible. Current v0 feature vectors use local canonical traits plus available public/raw stat proxies.",
    }


def fetch_espn_coaches() -> dict[str, Any]:
    raw = fetch_url(ESPN_COACHES_URL)
    coaches = parse_espn_coaches(raw)
    return {
        "source": {
            "id": "src_espn_coaches_2026",
            "title": "ESPN NBA Coaches - 2026",
            "url": ESPN_COACHES_URL,
            "fetched_at": fetched_at(),
        },
        "coach_count": len(coaches),
        "coaches": coaches,
    }


def parse_espn_coaches(raw: str) -> list[dict[str, Any]]:
    teams_by_name = {name: abbrev for abbrev, (name, _, _) in TEAM_INFO.items()}
    coaches: list[dict[str, Any]] = []
    row_pattern = re.compile(r"<tr class=\"(?:oddrow|evenrow)\"><td>(?P<name>.*?)</td><td>(?P<exp>.*?)</td><td>(?P<record>.*?)</td><td>(?P<team>.*?)</td></tr>", re.S)
    for match in row_pattern.finditer(raw):
        name = clean_html(match.group("name"))
        team_text = clean_html(match.group("team"))
        team_abbrev = teams_by_name.get(team_text)
        href_match = re.search(r"/name/(?P<abbr>[a-z]+)/", match.group("team"))
        if team_abbrev is None and href_match:
            team_abbrev = normalize_espn_abbrev(href_match.group("abbr").upper())
        if not team_abbrev or name.lower() == "vacant":
            status = "vacant"
        else:
            status = "verified_public_coaches_page"
        coaches.append(
            {
                "team_abbrev": team_abbrev,
                "team_name": team_text,
                "coach": None if name.lower() == "vacant" else name,
                "status": status,
                "experience": clean_html(match.group("exp")),
                "record": clean_html(match.group("record")),
                "source_url": ESPN_COACHES_URL,
            }
        )
    return coaches


def fetch_wikipedia_general_managers() -> dict[str, Any]:
    raw = fetch_url(WIKIPEDIA_GENERAL_MANAGERS_URL)
    general_managers = parse_wikipedia_general_managers(raw)
    return {
        "source": {
            "id": "src_wikipedia_general_managers",
            "title": "Wikipedia list of NBA general managers",
            "url": WIKIPEDIA_GENERAL_MANAGERS_URL,
            "fetched_at": fetched_at(),
        },
        "general_manager_count": len(general_managers),
        "general_managers": general_managers,
    }


def parse_wikipedia_general_managers(raw: str) -> list[dict[str, Any]]:
    teams_by_name = {name: abbrev for abbrev, (name, _, _) in TEAM_INFO.items()}
    table_idx = raw.find('class="wikitable sortable"')
    if table_idx < 0:
        return []
    table_start = raw.rfind("<table", 0, table_idx)
    table_end = raw.find("</table>", table_idx)
    table = raw[table_start : table_end + len("</table>")]
    entries: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr\b.*?</tr>", table, flags=re.S):
        cells = re.findall(r"<(?:td|th)\b[^>]*>(.*?)</(?:td|th)>", row_html, flags=re.S)
        if len(cells) < 2:
            continue
        team_name = clean_html(cells[0])
        gm_name = clean_html(cells[1])
        team_abbrev = teams_by_name.get(team_name)
        if not team_abbrev or not gm_name or gm_name == "General Manager":
            continue
        entries.append(
            {
                "team_abbrev": team_abbrev,
                "team_name": team_name,
                "general_manager": gm_name,
                "date_of_hire": clean_html(cells[4]) if len(cells) > 4 else "",
                "college": clean_html(cells[5]) if len(cells) > 5 else "",
                "source_url": WIKIPEDIA_GENERAL_MANAGERS_URL,
            }
        )
    return entries


def fetch_nba_official_staff() -> dict[str, Any]:
    teams: list[dict[str, Any]] = []
    fetched = fetched_at()
    for team_abbrev, team_id in sorted(NBA_TEAM_ID.items()):
        url = NBA_TEAM_INFO_URL_TEMPLATE.format(team_id=team_id)
        try:
            raw = fetch_url(url)
            teams.append(parse_nba_official_team_staff(raw, team_abbrev, url))
        except Exception as exc:
            teams.append({"team_abbrev": team_abbrev, "source_url": url, "coaching_groups": {}, "background": {}, "error": f"{type(exc).__name__}: {exc}"})
        time.sleep(0.15)
    return {
        "source": {
            "id": "src_nba_official_team_pages_2026",
            "title": "NBA.com team info pages",
            "url_template": NBA_TEAM_INFO_URL_TEMPLATE,
            "fetched_at": fetched,
        },
        "team_count": len(teams),
        "teams": teams,
    }


def parse_nba_official_team_staff(raw: str, team_abbrev: str, url: str) -> dict[str, Any]:
    coaching_groups: dict[str, list[str]] = {}
    section_idx = raw.find("COACHING STAFF")
    if section_idx >= 0:
        section_end = raw.find("FANTASY NEWS", section_idx)
        section = raw[section_idx : section_end if section_end > section_idx else section_idx + 12000]
        group_pattern = re.compile(r'<h3[^>]*>(?P<role>.*?)</h3><ul[^>]*>(?P<items>.*?)</ul>', re.S)
        for match in group_pattern.finditer(section):
            role = clean_html(match.group("role"))
            names = [clean_html(item) for item in re.findall(r"<li[^>]*>(.*?)</li>", match.group("items"), re.S)]
            if role and names:
                coaching_groups[role] = names
    background: dict[str, str] = {}
    bg_idx = raw.find("BACKGROUND")
    if bg_idx >= 0:
        bg_end = raw.find("</dl>", bg_idx)
        bg = raw[bg_idx : bg_end if bg_end > bg_idx else bg_idx + 5000]
        pairs = re.findall(r"<dt[^>]*>(.*?)</dt><dd[^>]*>(.*?)</dd>", bg, re.S)
        for key, value in pairs:
            background[clean_html(key)] = clean_html(value)
    return {"team_abbrev": team_abbrev, "source_url": url, "coaching_groups": coaching_groups, "background": background}


def parse_espn_team_map(raw: str) -> dict[str, str]:
    mapping: dict[str, str] = dict(ESPN_TEAM_ID_TO_ABBREV)
    pattern = re.compile(r'"id":"(?P<id>\d+)","abbreviation":"(?P<abbr>[A-Z]{2,3})"')
    for match in pattern.finditer(raw):
        abbr = normalize_espn_abbrev(match.group("abbr"))
        if abbr in TEAM_INFO:
            mapping[match.group("id")] = abbr
    return mapping


def normalize_espn_abbrev(abbrev: str | None) -> str | None:
    if abbrev == "NO":
        return "NOP"
    if abbrev == "SA":
        return "SAS"
    if abbrev == "GS":
        return "GSW"
    if abbrev == "NY":
        return "NYK"
    if abbrev == "UTAH":
        return "UTA"
    return abbrev


def infer_original_team(owner_abbrev: str | None, trade_note: str | None) -> str | None:
    if not trade_note:
        return owner_abbrev
    note = trade_note.upper().replace(".", "")
    # ESPN writes notes like "via LAC" or "from OKC via WSH and PHI".
    match = re.search(r"\bFROM\s+([A-Z]{2,4})\b", note)
    if not match:
        match = re.search(r"\bVIA\s+([A-Z]{2,4})\b", note)
    if match:
        return normalize_espn_abbrev(match.group(1))
    return None


def extract_html_table(raw: str, table_id: str) -> str:
    marker = f'id="{table_id}"'
    idx = raw.find(marker)
    if idx < 0:
        raise ValueError(f"Could not find table {table_id}")
    start = raw.rfind("<table", 0, idx)
    end = raw.find("</table>", idx)
    if start < 0 or end < 0:
        raise ValueError(f"Could not extract table {table_id}")
    return raw[start : end + len("</table>")]


def parse_cells(row_html: str) -> dict[str, dict[str, Any]]:
    cells: dict[str, dict[str, Any]] = {}
    pattern = re.compile(r"<(?P<tag>td|th)\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>", flags=re.S)
    for match in pattern.finditer(row_html):
        attrs = match.group("attrs")
        stat_match = re.search(r'data-stat="([^"]+)"', attrs)
        if not stat_match:
            continue
        stat = stat_match.group(1)
        csk_match = re.search(r'csk="([^"]*)"', attrs)
        csv_match = re.search(r'data-append-csv="([^"]*)"', attrs)
        class_match = re.search(r'class="([^"]*)"', attrs)
        cells[stat] = {
            "text": clean_html(match.group("body")),
            "csk": csk_match.group(1) if csk_match else None,
            "data_append_csv": csv_match.group(1) if csv_match else None,
            "class": class_match.group(1) if class_match else "",
        }
    return cells


def money_from_cell(cell: dict[str, Any] | None) -> int | None:
    if not cell:
        return None
    csk = cell.get("csk")
    if csk and re.fullmatch(r"-?\d+", csk):
        return int(csk)
    text = cell.get("text") or ""
    digits = re.sub(r"[^0-9-]", "", text)
    if not digits:
        return None
    return int(digits)


def money_from_text(text: str) -> int | None:
    digits = re.sub(r"[^0-9-]", "", text)
    if not digits or digits == "-":
        return None
    return int(digits)


def option_type(cell: dict[str, Any]) -> str | None:
    classes = cell.get("class", "")
    if "salary-pl" in classes:
        return "player_option"
    if "salary-tm" in classes:
        return "team_option"
    return None


def option_type_from_sup(fragment: str) -> str | None:
    sup = re.search(r"<sup[^>]*>(.*?)</sup>", fragment, flags=re.S)
    if not sup:
        return None
    marker = clean_html(sup.group(1)).upper()
    if marker == "P":
        return "player_option"
    if marker == "T":
        return "team_option"
    return None


def clean_html(fragment: str) -> str:
    fragment = re.sub(r"<!--.*?-->", "", fragment, flags=re.S)
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(re.sub(r"\s+", " ", text).strip())


def extract_labeled_anchor(raw: str, label: str) -> dict[str, str] | None:
    pattern = re.compile(rf"<strong>{re.escape(label)}:</strong>\s*(?P<body>.*?)</p>", re.S)
    match = pattern.search(raw)
    if not match:
        return None
    body = match.group("body")
    anchor = re.search(r'<a href=["\'](?P<href>[^"\']+)["\']>(?P<name>.*?)</a>', body, re.S)
    if anchor:
        href = anchor.group("href")
        if href.startswith("/"):
            href = f"https://www.basketball-reference.com{href}"
        return {"name": clean_html(anchor.group("name")), "url": href, "raw": clean_html(body)}
    text = clean_html(body)
    return {"name": text, "url": "", "raw": text} if text else None


def extract_json_array(raw: str, key: str) -> str:
    key_idx = raw.find(key)
    if key_idx < 0:
        raise ValueError(f"Could not find JSON array key {key}")
    start = raw.find("[", key_idx)
    if start < 0:
        raise ValueError(f"Could not find JSON array start for {key}")
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(raw)):
        char = raw[idx]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return raw[start : idx + 1]
    raise ValueError(f"Could not find JSON array end for {key}")


if __name__ == "__main__":
    raise SystemExit(main())
