#!/usr/bin/env python3
"""Refresh the checked-in July 2026 NBA roster, contract, draft, and pick snapshot.

Roster identity and physical data come from each official NBA team page. Contract
salary columns come from Basketball Reference because NBA/team announcements do
not consistently disclose salary amounts. Future-pick ownership comes from
Spotrac's public owner-side ledger. The generated files are build inputs; the
game never needs network access at runtime.
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nba_gm_data.research import (  # noqa: E402
    SPOTRAC_FUTURE_PICKS_URL,
    fetch_url,
    parse_spotrac_future_pick_html,
)
from nba_gm_data.utils import normalize_name  # noqa: E402


SNAPSHOT_DATE = "2026-07-28"
NBA_TEAM_URL = "https://www.nba.com/team/{team_id}/{slug}"
NBA_DRAFT_URL = "https://www.nba.com/news/2026-nba-draft-order"
NBA_DRAFT_PROSPECTS_URL = "https://www.nba.com/draft/2026/prospects"
BREF_CONTRACTS_URL = "https://www.basketball-reference.com/contracts/players.html"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)

TEAMS: dict[str, tuple[int, str]] = {
    "ATL": (1610612737, "hawks"),
    "BOS": (1610612738, "celtics"),
    "BKN": (1610612751, "nets"),
    "CHA": (1610612766, "hornets"),
    "CHI": (1610612741, "bulls"),
    "CLE": (1610612739, "cavaliers"),
    "DAL": (1610612742, "mavericks"),
    "DEN": (1610612743, "nuggets"),
    "DET": (1610612765, "pistons"),
    "GSW": (1610612744, "warriors"),
    "HOU": (1610612745, "rockets"),
    "IND": (1610612754, "pacers"),
    "LAC": (1610612746, "clippers"),
    "LAL": (1610612747, "lakers"),
    "MEM": (1610612763, "grizzlies"),
    "MIA": (1610612748, "heat"),
    "MIL": (1610612749, "bucks"),
    "MIN": (1610612750, "timberwolves"),
    "NOP": (1610612740, "pelicans"),
    "NYK": (1610612752, "knicks"),
    "OKC": (1610612760, "thunder"),
    "ORL": (1610612753, "magic"),
    "PHI": (1610612755, "sixers"),
    "PHX": (1610612756, "suns"),
    "POR": (1610612757, "blazers"),
    "SAC": (1610612758, "kings"),
    "SAS": (1610612759, "spurs"),
    "TOR": (1610612761, "raptors"),
    "UTA": (1610612762, "jazz"),
    "WAS": (1610612764, "wizards"),
}

TEAM_NAME_TO_ABBREV = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "LA Clippers": "LAC",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

BREF_TEAM_ALIASES = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}
CONTRACT_SEASONS = {
    "y1": "2026-27",
    "y2": "2027-28",
    "y3": "2028-29",
    "y4": "2029-30",
    "y5": "2030-31",
    "y6": "2031-32",
}
PLAYER_NAME_ALIASES = {
    "bobby portis jr": "bobby portis",
    "labaron philon jr": "labaron philon",
    "morez johnson jr": "morez johnson",
}
ROSTER_DATA_CORRECTIONS = {
    "alpha diallo": {
        "position": "F",
        "height": "6-7",
        "weight_lbs": 210,
        "birthdate": "JUN 29, 1997",
        "age": 29,
        "correction_source_url": (
            "https://www.cbssports.com/nba/teams/DEN/denver-nuggets/roster/"
        ),
        "correction_notes": (
            "NBA team page carried placeholder 1900/age-126 data on the "
            "snapshot date; corrected from a current public roster listing."
        ),
    }
}


def loose_name(value: Any) -> str:
    normalized = normalize_name(value)
    normalized = PLAYER_NAME_ALIASES.get(normalized, normalized)
    return re.sub(r"[^a-z0-9]", "", normalized)


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def next_data(page: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        page,
        flags=re.S,
    )
    if not match:
        raise ValueError("NBA page did not contain __NEXT_DATA__")
    return json.loads(match.group(1))


def official_draft_profiles() -> dict[str, dict[str, Any]]:
    page = next_data(fetch(NBA_DRAFT_PROSPECTS_URL))
    rows = page["props"]["pageProps"]["page"]["prospects"]
    return {
        loose_name(row.get("displayName")): {
            "position": row.get("position"),
            "height": row.get("heightFeetInches")
            or (row.get("height") or {}).get("feetAndInches"),
            "weight_lbs": row.get("weightLbs"),
            "birthdate": row.get("birthday"),
            "age": row.get("age"),
            "school": row.get("school"),
            "profile_url": row.get("profileLink"),
        }
        for row in rows
        if row.get("displayName")
    }


def official_rosters(
    draft_profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    teams = []
    seen_names: dict[str, str] = {}
    duplicates = []
    for abbrev, (team_id, slug) in TEAMS.items():
        url = NBA_TEAM_URL.format(team_id=team_id, slug=slug)
        payload = next_data(fetch(url))["props"]["pageProps"]["team"]
        roster = []
        for row in payload.get("roster") or []:
            normalized = PLAYER_NAME_ALIASES.get(
                normalize_name(row.get("PLAYER")), normalize_name(row.get("PLAYER"))
            )
            if normalized in seen_names and seen_names[normalized] != abbrev:
                duplicates.append(
                    {
                        "normalized_name": normalized,
                        "teams": sorted({seen_names[normalized], abbrev}),
                    }
                )
            seen_names[normalized] = abbrev
            roster_row = {
                    "nba_player_id": row.get("PLAYER_ID"),
                    "name": row.get("PLAYER"),
                    "normalized_name": normalized,
                    "team_abbrev": abbrev,
                    "position": row.get("POSITION"),
                    "height": row.get("HEIGHT"),
                    "weight_lbs": _integer(row.get("WEIGHT")),
                    "birthdate": row.get("BIRTH_DATE"),
                    "age": _number(row.get("AGE")),
                    "experience": row.get("EXP"),
                    "school": row.get("SCHOOL"),
                    "how_acquired": row.get("HOW_ACQUIRED"),
                    "supplemental_status": int(row.get("SUPPLEMENTAL_STATUS") or 0),
                }
            profile = (draft_profiles or {}).get(loose_name(row.get("PLAYER")))
            if profile:
                for field in (
                    "position",
                    "height",
                    "weight_lbs",
                    "birthdate",
                    "age",
                    "school",
                ):
                    if not roster_row.get(field):
                        roster_row[field] = profile.get(field)
                roster_row["draft_profile_url"] = profile.get("profile_url")
            correction = ROSTER_DATA_CORRECTIONS.get(normalized)
            if correction:
                roster_row.update(correction)
            roster.append(roster_row)
        teams.append(
            {
                "team_id": team_id,
                "team_abbrev": abbrev,
                "team_name": payload.get("info", {}).get("fullName")
                or payload.get("info", {}).get("name")
                or abbrev,
                "source_url": url,
                "roster": roster,
            }
        )
    return {
        "source": {
            "id": "src_nba_official_rosters_2026_07_28",
            "title": "NBA.com official team roster pages",
            "url_template": NBA_TEAM_URL,
            "retrieved_at": _timestamp(),
        },
        "snapshot_date": SNAPSHOT_DATE,
        "team_count": len(teams),
        "player_count": sum(len(team["roster"]) for team in teams),
        "duplicate_cross_team_rows": duplicates,
        "teams": teams,
    }


def draft_results(rosters: dict[str, Any]) -> dict[str, Any]:
    payload = next_data(fetch(NBA_DRAFT_URL))
    article = payload["props"]["pageProps"]["article"]
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in html.unescape(article["contentText"]).splitlines()
        if re.match(r"^\d+\.", line.strip())
    ]
    official_players = {
        loose_name(player["normalized_name"]): player
        for team in rosters["teams"]
        for player in team["roster"]
        if player.get("experience") == "R"
    }
    research = json.loads(
        (ROOT / "data/research/draft_prospects_2026.json").read_text(encoding="utf-8")
    )
    known_names = {
        loose_name(row["player"]): row["player"]
        for row in research.get("prospects", [])
    }
    known_names.update(
        {
            loose_name(player["normalized_name"]): player["name"]
            for player in official_players.values()
        }
    )
    picks = []
    unmatched = []
    for line in lines:
        overall = int(line.split(".", 1)[0])
        normalized_line = loose_name(line)
        matching = [
            (normalized, name)
            for normalized, name in known_names.items()
            if normalized and normalized in normalized_line
        ]
        if not matching:
            unmatched.append(line)
            continue
        normalized, name = max(matching, key=lambda item: len(item[0]))
        roster_player = official_players.get(normalized)
        original_text = line.split(".", 1)[1].split(name, 1)[0]
        original_team = next(
            (
                abbrev
                for team_name, abbrev in TEAM_NAME_TO_ABBREV.items()
                if team_name in original_text
            ),
            None,
        )
        final_team = roster_player.get("team_abbrev") if roster_player else original_team
        picks.append(
            {
                "overall": overall,
                "round": 1 if overall <= 30 else 2,
                "name": name,
                "normalized_name": normalize_name(name),
                "original_team_abbrev": original_team,
                "final_team_abbrev": final_team,
                "transaction_text": line,
                "signed_or_rights_listed": bool(roster_player),
            }
        )
    return {
        "source": {
            "id": "src_nba_official_2026_draft_results",
            "title": article.get("title") or "2026 NBA Draft Results: Picks 1-60",
            "url": NBA_DRAFT_URL,
            "retrieved_at": _timestamp(),
        },
        "draft_year": "2026",
        "pick_count": len(picks),
        "unmatched_lines": unmatched,
        "picks": sorted(picks, key=lambda item: item["overall"]),
    }


def current_contracts() -> dict[str, Any]:
    page = fetch(BREF_CONTRACTS_URL)
    table_match = re.search(
        r'<table[^>]+id="player-contracts".*?</table>',
        page,
        flags=re.S,
    )
    if not table_match:
        raise ValueError("Basketball Reference player contracts table was not found")
    contracts = []
    for row_html in re.findall(r"<tr[^>]*>.*?</tr>", table_match.group(0), flags=re.S):
        player = _cell(row_html, "player")
        team = _cell(row_html, "team_id")
        if (
            not player
            or not team
            or player == "Player"
            or BREF_TEAM_ALIASES.get(team, team) not in TEAMS
        ):
            continue
        seasons = []
        for key, season in CONTRACT_SEASONS.items():
            cell = _cell_html(row_html, key)
            if cell is None:
                continue
            salary_match = re.search(r'csk="(\d+)"', cell)
            salary = int(salary_match.group(1)) if salary_match else _money(_strip_tags(cell))
            if salary is not None:
                seasons.append({"season": season, "salary": salary})
        contracts.append(
            {
                "player_name": player,
                "normalized_name": normalize_name(player),
                "team_abbrev": BREF_TEAM_ALIASES.get(team, team),
                "seasons": seasons,
                "remaining_guaranteed": _money(_cell(row_html, "remain_gtd")),
            }
        )
    return {
        "source": {
            "id": "src_bref_contracts_players_2027",
            "title": "2026-27 NBA Player Contracts",
            "url": BREF_CONTRACTS_URL,
            "retrieved_at": _timestamp(),
            "notes": (
                "Public salary ledger used because NBA/team transaction releases "
                "do not consistently disclose annual salary."
            ),
        },
        "season": "2026-27",
        "contract_count": len(contracts),
        "contracts": contracts,
    }


def _cell_html(row_html: str, data_stat: str) -> str | None:
    match = re.search(
        rf'<t[dh][^>]*data-stat="{re.escape(data_stat)}"[^>]*>(.*?)</t[dh]>',
        row_html,
        flags=re.S,
    )
    return match.group(0) if match else None


def _cell(row_html: str, data_stat: str) -> str | None:
    value = _cell_html(row_html, data_stat)
    return _strip_tags(value) if value else None


def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()


def _money(value: str | None) -> int | None:
    digits = re.sub(r"[^\d]", "", value or "")
    return int(digits) if digits else None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {path.relative_to(ROOT)}")


def main() -> None:
    rosters = official_rosters(official_draft_profiles())
    draft = draft_results(rosters)
    contracts = current_contracts()
    future_picks = {
        "source": {
            "id": "src_spotrac_future_picks",
            "title": "Spotrac NBA Future Draft Picks",
            "url": SPOTRAC_FUTURE_PICKS_URL,
            "fetched_via": SPOTRAC_FUTURE_PICKS_URL,
            "retrieved_at": _timestamp(),
        },
        "coverage_note": (
            "Machine-ingested owner-side first- and second-round future-pick "
            "assets from Spotrac's public future picks page."
        ),
        "picks": parse_spotrac_future_pick_html(fetch_url(SPOTRAC_FUTURE_PICKS_URL)),
    }
    future_picks["pick_count"] = len(future_picks["picks"])
    write_json(
        ROOT / "data/research/nba_official_rosters_2026_07_28.json",
        rosters,
    )
    write_json(ROOT / "data/research/nba_official_draft_2026.json", draft)
    write_json(
        ROOT / "data/research/contracts_public_players_2027.json",
        contracts,
    )
    write_json(
        ROOT / "data/research/future_picks_spotrac_2027_plus.json",
        future_picks,
    )


if __name__ == "__main__":
    main()
