"""When each real contract was signed and how long it originally ran (CONTRACT-TERMS part 1).

The public salary tables the league is built from list only the seasons a contract still has to run. A player in the
last season of a four-year deal therefore looked like he had signed a one-year deal this summer, and the extension rules
(a contract must cover three or more seasons, and two years must have passed since signing) refused him. Brandin
Podziemski, the 19th pick in 2023 entering year four of his rookie deal, was listed as extendable and then refused.

This module rebuilds each real contract's history from evidence, in this order:

1. ``rookie_scale``: a first-round pick from the 2023-2026 drafts still on his rookie deal. Rookie-scale contracts run
   four seasons (two guaranteed, then two team options) from the draft year (CBA Art. VIII).
2. ``reported``: the deal appears in the reported-signings research (offseason decisions 2023-2026, free-agent and
   extension trackers 2025-2026) with its signing summer and length, and its last season matches the salary table.
3. ``new_2026``: the 2025-26 preseason salary table shows a different deal (or no NBA deal), so this contract started in
   2026-27 and every season of it is listed.
4. ``extended_since_2025``: the 2025-26 table shows the same deal for the first seasons and different seasons after
   them: an extension signed during 2025-26 or in summer 2026 (its length is known, the exact signing season is not).
   ``rookie_2025``: the same deal was running in 2025-26 and 2025-26 was his first NBA season, so he signed it then.
5. ``running_since_2025`` (length unknown): the same deal was already running in 2025-26 and nothing says when it was
   signed. The length is stored as unknown (``original_contract_years`` None) with the seasons we can confirm
   (``original_contract_years_min``); nothing is guessed.

``scripts/build_contract_history.py`` writes the result to ``data/canonical/contract_history_2026_27.json``;
``apply_contract_history`` puts it on the universe's contracts when the universe is loaded (``storage.load_universe_json``)
and when it is built (``ingest``), so the GUI, the text game and the scripts all read the same fields.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

HISTORY_FILE = "data/canonical/contract_history_2026_27.json"
ROOKIE_SCALE_YEARS = 4
MAX_DEAL_SEASONS = 6  # the longest deal from signing: a designated veteran extension (CBA Art. VII)
SNAPSHOT_SEASON = "2025-26"

KIND_WORDS = {
    "rookie_scale": "first-round rookie-scale deal from the {draft_year} draft (four seasons: two guaranteed, two team options)",
    "reported": "reported signing: {years} seasons, signed in {signed_season}",
    "new_2026": "new deal starting 2026-27 (the 2025-26 salary table shows a different deal or none)",
    "extended_since_2025": "extended after the 2025-26 salary table ({years} new seasons from {first_season}); signed during 2025-26 or in summer 2026",
    "rookie_2025": "signed in 2025-26, his first NBA season",
    "running_since_2025": "already running in 2025-26; signing date not on record (at least {min_years} seasons)",
}


def season_label(start: int) -> str:
    return f"{start}-{str(start + 1)[-2:]}"


def season_start(label: Any) -> int:
    return int(str(label)[:4])


def name_key(name: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name or "").casefold().replace("jr.", "").replace(" iii", "").replace(" ii", ""))


def salary_rows(contract: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Paid seasons in season order (qualifying offers and the 'remaining_total' row are not contract seasons)."""
    rows = [r for r in (contract or {}).get("seasons") or []
            if r.get("salary") is not None and str(r.get("season") or "")[:4].isdigit()
            and r.get("option_type") != "qualifying_offer"]
    return sorted(rows, key=lambda r: str(r.get("season")))


SAME_SALARY_TOLERANCE = 0.06  # the two tables differ by bonuses they count (Aaron Gordon +5.3% every season)


def matching_prefix(current_rows: list[dict[str, Any]], older: dict[str, Any] | None) -> int:
    """How many of the current seasons, from the first, the 2025-26 table lists at the same salary (within 6%,
    the gap between the two public tables' bonus counting). All of them = the same contract; some = the same contract
    extended later; none = a different contract."""
    old = {str(r.get("season")): float(r.get("salary") or 0) for r in salary_rows(older)}
    if not current_rows or SNAPSHOT_SEASON not in old:
        return 0
    count = 0
    for row in current_rows:
        before = old.get(str(row["season"]))
        if before is None or abs(before - float(row["salary"])) > max(5.0, SAME_SALARY_TOLERANCE * float(row["salary"])):
            break
        count += 1
    return count


def same_deal(current_rows: list[dict[str, Any]], older: dict[str, Any] | None) -> bool:
    return bool(current_rows) and matching_prefix(current_rows, older) == len(current_rows)


def research_deals(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Reported signings by player name key: {signed_start, years, start (first salary season), source}."""
    deals: dict[str, list[dict[str, Any]]] = {}

    def add(name: Any, signed_start: int, years: int, starts: list[int], source: str) -> None:
        if years and years > 0:
            deals.setdefault(name_key(name), []).append(
                {"signed_start": signed_start, "years": int(years), "starts": starts, "source": source})

    try:
        decisions = json.loads((root / "data/research/offseason_decisions_2023_2026.json").read_text())
    except (OSError, ValueError):
        decisions = {}
    for row in decisions.get("salary_comparables") or []:
        add(row.get("player"), int(row["summer"]), int(row.get("new_deal_years") or 0), [int(row["summer"])],
            "offseason decisions research (salary comparables)")
    for row in (decisions.get("decisions") or {}).get("early_terminations_and_returns") or []:
        if row.get("new_deal_years"):
            add(row.get("player"), int(row["summer"]), int(row["new_deal_years"]), [int(row["summer"])],
                "offseason decisions research (option and return records)")
    for row in (decisions.get("decisions") or {}).get("rookie_scale_extensions") or []:
        start = row.get("extension_salary_start_season")
        years = (row.get("terms") or {}).get("years")
        if row.get("decision") == "extended" and start and years:
            add(row.get("player"), int(start) - 1, int(years), [int(start)], "rookie-scale extension records")
    try:
        market = json.loads((root / "data/research/free_agent_contracts_2025_2026.json").read_text())
    except (OSError, ValueError):
        market = {}
    for row in market.get("contracts") or []:
        summer = int(row.get("summer") or 0)
        if not summer:
            continue
        starts = [summer + 1, summer + 2] if row.get("kind") == "extension" else [summer]
        add(row.get("player"), summer, int(row.get("years") or 0), starts, "free-agent and extension tracker 2025-26")
    return deals


def match_reported(deals: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A reported deal whose seasons end where the salary table ends (latest signing wins). Seasons listed before
    an extension's first season belong to the deal it extended."""
    if not rows:
        return None
    last = season_start(rows[-1]["season"])
    for deal in sorted(deals, key=lambda d: -d["signed_start"]):
        for start in deal["starts"]:
            if start + deal["years"] - 1 == last:
                return {**deal, "start": start}
    return None


def build_contract_history(universe: dict[str, Any], snapshot: dict[str, Any], root: Path,
                           bird_since: Callable[[dict[str, Any], str | None], str] | None = None,
                           first_nba_start: Callable[[dict[str, Any]], int | None] | None = None,
                           ) -> dict[str, dict[str, Any]]:
    """One history record per real contract with salary rows, keyed by player id."""
    from .schema import CANONICAL_SEASON
    base = season_start(CANONICAL_SEASON)
    deals = research_deals(root)
    snap_players = {p.get("id"): p for p in snapshot.get("players") or []}
    snap_by_name: dict[str, dict[str, Any]] = {}
    for contract in snapshot.get("contracts") or []:
        player = snap_players.get(contract.get("player_id"))
        if player:
            snap_by_name[name_key(player.get("name"))] = contract
    snap_names = {name_key(p.get("name")) for p in snapshot.get("players") or []}
    players = {p.get("id"): p for p in universe.get("players") or []}
    out: dict[str, dict[str, Any]] = {}
    for contract in universe.get("contracts") or []:
        player = players.get(contract.get("player_id")) or {}
        rows = salary_rows(contract)
        if not rows or not player:
            continue
        key = name_key(player.get("name"))
        first, last = season_start(rows[0]["season"]), season_start(rows[-1]["season"])
        listed = last - first + 1
        older = snap_by_name.get(key)
        running = same_deal(rows, older)
        record: dict[str, Any]
        try:
            draft_year = int(player.get("draft_year") or 0)
        except (TypeError, ValueError):
            draft_year = 0
        rookie = (int(player.get("draft_round") or 0) == 1 and base - 3 <= draft_year <= base
                  and last <= draft_year + ROOKIE_SCALE_YEARS - 1 and first >= draft_year
                  and (running or draft_year == base or older is None))
        reported = match_reported(deals.get(key) or [], rows)
        prefix = matching_prefix(rows, older)
        if rookie:
            record = {"kind": "rookie_scale", "original_contract_years": ROOKIE_SCALE_YEARS,
                      "signed_season": season_label(draft_year), "draft_year": draft_year,
                      "evidence": f"first-round pick No. {player.get('draft_position')} in the {draft_year} draft"}
            if last < draft_year + ROOKIE_SCALE_YEARS - 1:
                record["option_declined"] = True
        elif reported:
            record = {"kind": "reported", "original_contract_years": reported["years"],
                      "signed_season": season_label(reported["signed_start"]),
                      "first_season": season_label(reported["start"]), "evidence": reported["source"]}
        elif 0 < prefix < len(rows):
            # The 2025-26 deal is still running and new seasons were added after that table: an extension signed
            # during 2025-26 or in summer 2026. Its length is known; the exact signing season is not.
            record = {"kind": "extended_since_2025", "original_contract_years": len(rows) - prefix,
                      "signed_season": None, "signed_season_earliest": SNAPSHOT_SEASON,
                      "signed_season_latest": season_label(base), "first_season": rows[prefix]["season"],
                      "evidence": "the 2025-26 salary table shows the same deal through "
                                  f"{rows[prefix - 1]['season']} and different seasons after it"}
        elif not running:
            record = {"kind": "new_2026", "original_contract_years": listed, "signed_season": season_label(base),
                      "evidence": ("2025-26 salary table shows a different deal" if older else
                                   "no 2025-26 NBA salary record" if key in snap_names else "not in the 2025-26 league")}
        else:
            min_years = last - season_start(SNAPSHOT_SEASON) + 1
            since = bird_since(player, player.get("team_id")) if bird_since else None
            rookie_2025 = draft_year == season_start(SNAPSHOT_SEASON) or (
                first_nba_start is not None and first_nba_start(player) == season_start(SNAPSHOT_SEASON))
            if rookie_2025:
                record = {"kind": "rookie_2025", "original_contract_years": min_years, "signed_season": SNAPSHOT_SEASON,
                          "evidence": "his first NBA season was 2025-26, so this deal was signed then"}
            else:
                record = {"kind": "running_since_2025", "original_contract_years": None,
                          "original_contract_years_min": min_years, "signed_season": None,
                          "signed_season_earliest": season_label(last - MAX_DEAL_SEASONS + 1),
                          "signed_season_latest": SNAPSHOT_SEASON,
                          "evidence": "same deal in the 2025-26 salary table"
                                      + (f"; with this team since {since}" if since else "")}
        record.setdefault("signed_season_earliest", record.get("signed_season"))
        record.setdefault("signed_season_latest", record.get("signed_season"))
        record["player_name"] = player.get("name")
        record["listed_seasons"] = [str(r["season"]) for r in rows]
        out[str(contract.get("player_id"))] = record
    return out


def history_words(record: dict[str, Any] | None) -> str:
    """One plain sentence describing what the game knows about when the contract was signed."""
    if not record:
        return "Contract history not on record."
    template = KIND_WORDS.get(str(record.get("kind")), "")
    try:
        return template.format(years=record.get("original_contract_years"), min_years=record.get("original_contract_years_min"),
                               signed_season=record.get("signed_season"), draft_year=record.get("draft_year"),
                               first_season=record.get("first_season"))
    except (KeyError, IndexError):
        return template


@lru_cache(maxsize=4)
def _load_history(path_text: str, mtime: int) -> dict[str, dict[str, Any]]:
    try:
        return dict(json.loads(Path(path_text).read_text()).get("contracts") or {})
    except (OSError, ValueError):
        return {}


def load_history(root: Path | None = None) -> dict[str, dict[str, Any]]:
    from .resource_paths import game_resource_root
    path = (root or game_resource_root()) / HISTORY_FILE
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return {}
    return _load_history(str(path), mtime)


def apply_contract_history(universe: dict[str, Any], root: Path | None = None) -> int:
    """Write the evidence-based signing season and original length onto the universe's real contracts (idempotent).
    Only contracts whose listed seasons still match the history record are changed. Returns the number changed."""
    history = load_history(root)
    if not history:
        return 0
    changed = 0
    for contract in universe.get("contracts") or []:
        record = history.get(str(contract.get("player_id") or ""))
        if not record or contract.get("status") == "save_state_contract_override":
            continue
        if [str(r["season"]) for r in salary_rows(contract)] != list(record.get("listed_seasons") or []):
            continue
        contract["original_contract_years"] = record.get("original_contract_years")
        contract["signed_season"] = record.get("signed_season")
        contract["contract_history"] = {k: v for k, v in record.items() if k not in {"player_name", "listed_seasons"}}
        changed += 1
    return changed
