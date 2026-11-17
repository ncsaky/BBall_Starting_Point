"""Import ESPN player identity and draft metadata without copying headshots.

ESPN's public athlete profiles expose headshot URLs and draft history. ESPN's
support guidance says its photos are generally licensed for ESPN.com only, so
this importer records photo references but does not download or transform them.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.ingest import official_player_key  # noqa: E402


CANONICAL_FILE = ROOT / "data/canonical/universe_2026_27_offseason.json"
OUTPUT_FILE = ROOT / "data/research/espn_nba_player_metadata_2026_10_02.json"
COLLECTION_URL = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes?limit=1000"
PROFILE_URL = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes/{athlete_id}"
SEARCH_URL = "https://site.api.espn.com/apis/search/v2?query={query}&sport=basketball&limit=10"
SOURCE_ID = "src_espn_nba_player_profiles"
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "2nd", "3rd"}


def fetch_json(url: str, retries: int = 5) -> dict[str, Any]:
    for attempt in range(retries):
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "BBall-Starting-Point research importer"},
        )
        try:
            with urlopen(request, timeout=25) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {408, 425, 429, 500, 502, 503, 504} or attempt + 1 == retries:
                raise
        except (TimeoutError, URLError):
            if attempt + 1 == retries:
                raise
        time.sleep(min(8, 0.5 * (2**attempt)))
    raise RuntimeError(f"Unable to fetch {url}")


def athlete_ids() -> list[str]:
    payload = fetch_json(COLLECTION_URL)
    ids = []
    for item in payload.get("items") or []:
        reference = str(item.get("$ref") or "")
        match = re.search(r"/athletes/(\d+)(?:\?|$)", reference)
        if match:
            ids.append(match.group(1))
    return list(dict.fromkeys(ids))


def fetch_profiles(ids: list[str], workers: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    profiles: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {
            executor.submit(fetch_json, PROFILE_URL.format(athlete_id=athlete_id)): athlete_id
            for athlete_id in ids
        }
        for future in as_completed(pending):
            athlete_id = pending[future]
            try:
                profile = future.result()
                if profile.get("id"):
                    profiles.append(profile)
                else:
                    failures.append({"espn_player_id": athlete_id, "reason": "profile_has_no_id"})
            except Exception as error:  # Include every failed profile in the audit report.
                failures.append({"espn_player_id": athlete_id, "reason": str(error)[:240]})
    return profiles, failures


def search_player_athlete(player: dict[str, Any]) -> tuple[str | None, str | None]:
    name = str(player.get("name") or player.get("normalized_name") or "")
    payload = fetch_json(SEARCH_URL.format(query=quote(name)))
    candidates = [
        item
        for group in payload.get("results") or []
        if group.get("type") == "player"
        for item in group.get("contents") or []
        if item.get("sport") == "basketball"
    ]
    key = match_key(name)
    nba_exact = [
        item for item in candidates
        if str(item.get("description") or "").upper() == "NBA"
        and match_key(str(item.get("displayName") or "")) == key
    ]
    exact = nba_exact or [item for item in candidates if match_key(str(item.get("displayName") or "")) == key]
    if not exact:
        nba_loose = [
            item for item in candidates
            if str(item.get("description") or "").upper() == "NBA"
            and suffixless_key(str(item.get("displayName") or "")) == suffixless_key(name)
        ]
        exact = nba_loose or [
            item for item in candidates
            if suffixless_key(str(item.get("displayName") or "")) == suffixless_key(name)
        ]
    athlete_ids = {
        match.group(1)
        for item in exact
        if (match := re.search(r"~a:(\d+)", str(item.get("uid") or "")))
    }
    if len(athlete_ids) != 1:
        return None, f"search_match_count_{len(athlete_ids)}"
    return next(iter(athlete_ids)), None


def match_key(name: str) -> str:
    # ESPN romanizes Serbian đ as d, while the game's source spelling uses đ.
    return official_player_key(name.replace("Đ", "D").replace("đ", "d"))


def search_player_headshot(player: dict[str, Any], expected_athlete_id: str) -> str | None:
    name = str(player.get("name") or player.get("normalized_name") or "")
    payload = fetch_json(SEARCH_URL.format(query=quote(name)))
    key = match_key(name)
    exact = []
    for group in payload.get("results") or []:
        if group.get("type") != "player":
            continue
        for item in group.get("contents") or []:
            athlete_id = re.search(r"~a:(\d+)", str(item.get("uid") or ""))
            image_url = (item.get("image") or {}).get("default")
            if item.get("sport") == "basketball" and athlete_id and image_url and match_key(str(item.get("displayName") or "")) == key:
                exact.append((athlete_id.group(1), image_url))

    expected = [image_url for athlete_id, image_url in exact if athlete_id == expected_athlete_id]
    if expected:
        return expected[0]
    unique_candidates = {athlete_id: image_url for athlete_id, image_url in exact}
    return next(iter(unique_candidates.values())) if len(unique_candidates) == 1 else None


def suffixless_key(name: str) -> str:
    tokens = match_key(name).split()
    if tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def unique_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    unique = {str(row.get("id")): row for row in candidates if row.get("id")}
    if len(unique) == 1:
        return next(iter(unique.values()))
    active = [row for row in unique.values() if row.get("active") is True]
    if len(active) == 1:
        return active[0]
    return None


def index_profiles(profiles: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    exact: dict[str, list[dict[str, Any]]] = {}
    loose: dict[str, list[dict[str, Any]]] = {}
    for profile in profiles:
        names = {
            str(profile.get("displayName") or ""),
            str(profile.get("fullName") or ""),
            " ".join(part for part in (profile.get("firstName"), profile.get("lastName")) if part),
        }
        for name in names:
            if not name.strip():
                continue
            exact.setdefault(match_key(name), []).append(profile)
            loose.setdefault(suffixless_key(name), []).append(profile)
    return exact, loose


def match_profile(
    player: dict[str, Any],
    exact: dict[str, list[dict[str, Any]]],
    loose: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str]:
    names = [str(value) for value in (player.get("name"), player.get("normalized_name")) if value]
    for name in dict.fromkeys(names):
        match = unique_candidate(exact.get(match_key(name)) or [])
        if match:
            return match, "exact"
    for name in dict.fromkeys(names):
        match = unique_candidate(loose.get(suffixless_key(name)) or [])
        if match:
            return match, "suffix_normalized"
    return None, "unmatched"


def profile_metadata(player: dict[str, Any], profile: dict[str, Any] | None, matched_by: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "game_player_id": player["id"],
        "name": player.get("name"),
        "normalized_name": player.get("normalized_name"),
        "espn_player_id": None,
        "espn_profile_url": None,
        "headshot_url": None,
        "headshot_url_source": None,
        "headshot_rights_status": "not_available",
        "headshot_asset_path": None,
        "draft_year": None,
        "draft_round": None,
        "draft_position": None,
        "draft_status": "unknown",
        "match_status": matched_by,
    }
    if not profile:
        return result

    athlete_id = str(profile.get("id"))
    links = profile.get("links") or []
    profile_link = next(
        (link.get("href") for link in links if "playercard" in (link.get("rel") or [])),
        None,
    )
    if not profile_link and profile.get("slug"):
        profile_link = f"https://www.espn.com/nba/player/_/id/{athlete_id}/{profile['slug']}"
    headshot = profile.get("headshot") or {}
    headshot_url = headshot.get("href")
    draft = profile.get("draft")
    result.update(
        {
            "espn_player_id": athlete_id,
            "espn_profile_url": profile_link,
            "headshot_url": headshot_url,
            "headshot_url_source": "espn_core_athlete_profile" if headshot_url else None,
            "headshot_rights_status": "reference_only_not_cleared" if headshot_url else "not_available",
            "draft_year": _optional_int((draft or {}).get("year")),
            "draft_round": _optional_int((draft or {}).get("round")),
            "draft_position": _optional_int((draft or {}).get("selection")),
            "draft_status": "drafted" if draft else "undrafted",
        }
    )
    return result


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_import(canonical: dict[str, Any], profiles: list[dict[str, Any]], failures: list[dict[str, str]]) -> dict[str, Any]:
    exact, loose = index_profiles(profiles)
    rows = []
    unmatched = []
    for player in canonical.get("players") or []:
        profile, matched_by = match_profile(player, exact, loose)
        row = profile_metadata(player, profile, matched_by)
        rows.append(row)
        if not profile:
            unmatched.append({"game_player_id": player.get("id"), "name": player.get("name")})

    matched = [row for row in rows if row.get("espn_player_id")]
    headshot_refs = [row for row in matched if row.get("headshot_url")]
    drafted = [row for row in matched if row.get("draft_status") == "drafted"]
    undrafted = [row for row in matched if row.get("draft_status") == "undrafted"]
    ambiguous_names = sorted(
        key for key, candidates in exact.items()
        if len({str(candidate.get("id")) for candidate in candidates}) > 1
    )
    return {
        "source": {
            "id": SOURCE_ID,
            "title": "ESPN NBA athlete profiles and draft history",
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "athlete_collection_url": COLLECTION_URL,
            "profile_url_template": PROFILE_URL,
            "headshot_url_template": "https://a.espncdn.com/i/headshots/nba/players/full/{espn_player_id}.png",
            "headshot_rights_status": "reference_only_not_cleared",
            "rights_note": "ESPN says photos are generally purchased for use on ESPN.com only; contact the photo rights holder before using copies or derivatives elsewhere.",
        },
        "coverage": {
            "game_player_count": len(rows),
            "espn_profiles_fetched": len(profiles),
            "espn_profile_fetch_failures": len(failures),
            "matched_player_count": len(matched),
            "headshot_reference_count": len(headshot_refs),
            "drafted_count": len(drafted),
            "undrafted_count": len(undrafted),
            "unknown_draft_count": len(matched) - len(drafted) - len(undrafted),
            "unmatched_player_count": len(unmatched),
        },
        "players": rows,
        "unmatched_players": unmatched,
        "profile_fetch_failures": failures,
        "ambiguous_espn_name_keys": ambiguous_names,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=CANONICAL_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--workers", type=int, default=6, help="Concurrent ESPN profile requests (1-10).")
    args = parser.parse_args()
    workers = max(1, min(10, args.workers))

    canonical = json.loads(args.canonical.read_text(encoding="utf-8"))
    ids = athlete_ids()
    profiles, failures = fetch_profiles(ids, workers)
    first_pass = build_import(canonical, profiles, failures)
    already_fetched = {str(profile.get("id")) for profile in profiles}
    unmatched_by_id = {
        str(player.get("id")): player
        for player in canonical.get("players") or []
        if any(item.get("game_player_id") == player.get("id") for item in first_pass["unmatched_players"])
    }
    search_results: dict[str, str | None] = {}
    search_failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {
            executor.submit(search_player_athlete, player): player_id
            for player_id, player in unmatched_by_id.items()
        }
        for future in as_completed(pending):
            player_id = pending[future]
            try:
                athlete_id, reason = future.result()
                search_results[player_id] = athlete_id
                if reason:
                    search_failures.append({"game_player_id": player_id, "reason": reason})
            except Exception as error:
                search_results[player_id] = None
                search_failures.append({"game_player_id": player_id, "reason": str(error)[:240]})

    fallback_ids = list(dict.fromkeys(
        athlete_id for athlete_id in search_results.values()
        if athlete_id and athlete_id not in already_fetched
    ))
    fallback_profiles, fallback_failures = fetch_profiles(fallback_ids, workers)
    profiles.extend(fallback_profiles)
    failures.extend(fallback_failures)
    result = build_import(canonical, profiles, failures)

    players_by_id = {str(player.get("id")): player for player in canonical.get("players") or []}
    rows_by_id = {str(row.get("game_player_id")): row for row in result["players"]}
    missing_headshots = [
        row for row in result["players"]
        if row.get("espn_player_id") and not row.get("headshot_url")
    ]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending_headshots = {
            executor.submit(
                search_player_headshot,
                players_by_id[str(row["game_player_id"])],
                str(row["espn_player_id"]),
            ): str(row["game_player_id"])
            for row in missing_headshots
        }
        for future in as_completed(pending_headshots):
            row = rows_by_id[pending_headshots[future]]
            try:
                image_url = future.result()
            except Exception:
                image_url = None
            if image_url:
                row["headshot_url"] = image_url
                row["headshot_url_source"] = "espn_site_search"
                row["headshot_rights_status"] = "reference_only_not_cleared"

    result["coverage"]["headshot_reference_count"] = sum(
        bool(row.get("headshot_url")) for row in result["players"]
    )
    result["source"]["search_url_template"] = SEARCH_URL
    result["profile_search_failures"] = search_failures
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)

    print(json.dumps({"output": str(args.output), **result["coverage"], "unmatched": result["unmatched_players"]}, ensure_ascii=False, indent=2))
    return 0 if not result["profile_fetch_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
