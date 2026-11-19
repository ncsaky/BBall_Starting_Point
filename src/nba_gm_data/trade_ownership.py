"""How an AI front office values players it already owns: attachment, tenure and investment.

Step 1 of the trade-AI redesign (docs/agents/TRADE_AI_DIRECTION.md, docs/agents/tasks/trade-step1-own-value.md).
Everything here is "context" on top of a player's value; nothing changes ratings or the game simulation, and the
human team's own valuations are never touched (callers skip human teams).

Two parts:

1. A small per-save ledger, ``save["player_tenure"]``: for each player, the team he is with, since when, how he got
   there (draft, trade, signing, waiver claim), whether the team drafted and kept him ("homegrown"), and the recent
   investments the team made in him (draft slot and whether it traded up for that pick, the value it gave up in a
   trade, the size of a contract it signed him to). The starting league is seeded from the real career data in the
   repo (season-by-team rows, draft data, and the real 2025-27 trade list); after that the ledger is folded forward
   from the save's own transaction logs whenever the save is written, so every trade, signing, draft pick and
   waiver claim is recorded with its date.

2. ``own_player_premium``: the extra value a team puts on a player it is being asked to give up. Three parts:
   attachment (ordinary loss aversion about one's own players), tenure (years with the team, more for players it
   drafted and kept), and investment (recent, large costs that fade over about two seasons). The sum is then scaled
   down when the team has a stated reason to move the player (the trade-block reasons: rebuilding team with a
   veteran, bad contract, position surplus, contract talks stalled, planned retool, GM listing).

The functions are pure (they read the league and ledger, never write them) so the step-2 target search can ask a
seller for its asking price with the same numbers the trade evaluation uses.
"""
from __future__ import annotations

from datetime import date
import re
import unicodedata
from types import SimpleNamespace
from typing import Any


LEDGER_KEY = "player_tenure"
LEDGER_VERSION = 1

# ---------------------------------------------------------------------------------------------------------------
# Sizes. All rates are fractions of the team's own value for the player (what it loses in his current role), so a
# premium is always proportional to the player and never manufactures value for a fringe player.
#
# Why these sizes (details and sources in docs/agents/tasks/trade-step1-own-value.md):
# - Laboratory endowment studies find owners ask about twice what buyers bid (Kahneman, Knetsch & Thaler 1990),
#   but experienced, professional traders show little of it (List 2003). Front offices are professionals, so the
#   base attachment is small: 4% of the player's value, up to 8% for players the team has a reason to keep.
# - NBA teams escalate commitment to players they invested in: higher draft picks get more minutes and stay longer
#   than their play alone explains (Staw & Hoang 1995; Camerer & Weber 1999). The user's framework asks for the
#   investment memory to fade over one to two seasons; it does, and it stays a few percent of value, so context can
#   still override it (the real Nique Clifford sale, 17 months after Sacramento traded up for him).
# - Tenure is the largest piece only for long-tenured, good players (a franchise player of 8+ seasons: about 10%,
#   12% if homegrown), and fades out for players 33 and older and halves for a rebuilding team.
# - The whole premium is capped at 30% of the player's own value before the move-reason scaling.
# ---------------------------------------------------------------------------------------------------------------
ATTACHMENT_BASE = 0.04
KEEP_REASON_RATES = {
    "planned_core": 0.03,      # in the team's current core plan
    "young_starter": 0.06,     # 25 or younger and playing starter minutes (24+); 0.02 before trade 2b
    "top_of_rotation": 0.01,   # one of the team's main players (30+ minutes)
}
KEEP_REASON_CAP = 0.04
# Young starters and young core players are highly valuable to their teams (the user's direction, trade 2b): their
# keep reasons may add up to 8% instead of 4%, and money reasons (the tax, an expiring deal) never scale their premium
# down. They can still be traded for fair value or a clear upgrade.
YOUNG_KEEP_REASON_CAP = 0.08
YOUNG_PIECE_AGE = 25.5
MONEY_REASONS = frozenset({"over_tax_line", "expiring_veteran_non_contender"})
TENURE_RATE_PER_YEAR = 0.012
TENURE_YEARS_CAP = 8.0
HOMEGROWN_RATE = 0.02
TENURE_AGE_FADE_START = 32.0   # tenure attachment fades linearly to zero at 35
TENURE_AGE_FADE_END = 35.0
REBUILDING_TENURE_FACTOR = 0.5
INVESTMENT_FULL_DAYS = 90      # an investment counts in full for its first ~3 months ...
INVESTMENT_ZERO_DAYS = 730     # ... then fades linearly to nothing after two seasons
DRAFT_SLOT_RATES = ((3, 0.10), (10, 0.08), (20, 0.05), (30, 0.035), (99, 0.01))
TRADED_UP_RATE = 0.04
TRADE_INVESTMENT_RATE = 0.07   # scaled by what was given up relative to the player's value (0.3x to 1.5x)
SIGNING_INVESTMENT_RATE = 0.05  # scaled by annual salary relative to $30M (0 to 1.5x); contracts under $5M ignored
INVESTMENT_CAP = 0.15
TOTAL_RATE_CAP = 0.30
# Reasons the team itself has for moving the player (the trade-block reasons). The strongest one present scales
# the whole premium down; a team with a reason to sell is not loss-averse about that player.
MOVE_REASON_FACTORS = {
    "gm_listed": 0.3,
    "extension_talks_stalled": 0.3,     # the closest the game has to "player wants out"
    "older_than_team_timeline": 0.35,   # rebuilding team, veteran 29+ (0.8 for a team that is only "developing")
    "planned_core_retool_not_full_teardown": 0.5,
    "negative_contract_value": 0.5,
    "upgradeable_expensive_rotation_slot": 0.6,
    "veteran_surplus_slot": 0.6,
    "position_surplus": 0.75,
    "blocked_prospect": 0.75,
    "health_risk_for_win_now_team": 0.75,
    # Contract reasons (trade step 2, _money_reasons): an expiring veteran on a team that is not contending would
    # leave for nothing; a team over the luxury tax saves real money moving a paid non-core player.
    "expiring_veteran_non_contender": 0.6,
    "over_tax_line": 0.75,
}
DEVELOPING_TIMELINE_FACTOR = 0.8
# Roster-shape reasons never apply to a player in the team's core plan, and a position surplus only counts if the
# position is still over-full after he leaves (the roster's surplus is counted with him on it).
ROSTER_SHAPE_REASONS = {"position_surplus", "veteran_surplus_slot", "blocked_prospect"}
DRAFT_TRADE_UP_WINDOW_DAYS = 40
LEDGER_LOG_WINDOW_DAYS = 400

# Real draft-night trade-ups in the starting league (data/research/real_trades/trades_2025_2027.json): the team that
# moved up for the named pick. Clifford is the user's reference case (Sacramento sent a protected first to move up).
REAL_DRAFT_TRADE_UPS = {
    ("nique clifford", "SAC"): "2025-06-25",
    ("alex karaban", "SAC"): "2026-06-23",
    ("tarris reed jr.", "SAS"): "2026-06-23",
    ("bennett stirtz", "OKC"): "2026-06-23",
    ("ebuka okorie", "DET"): "2026-06-23",
    ("cameron carr", "LAL"): "2026-06-23",
}
REAL_TRADES_PATH = "data/research/real_trades/trades_2025_2027.json"
SEASON_OPEN_DAY = "10-01"


# --------------------------------------------------------------------------- small helpers

def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _days_between(earlier: Any, later: Any) -> int | None:
    a, b = _date(earlier), _date(later)
    return None if a is None or b is None else (b - a).days


def _norm_name(name: Any) -> str:
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().casefold()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def investment_fade(days: int | None) -> float:
    """1.0 for the first ~3 months, then linear to 0 at two seasons."""
    if days is None or days < 0:
        return 0.0
    if days <= INVESTMENT_FULL_DAYS:
        return 1.0
    return _clamp(1.0 - (days - INVESTMENT_FULL_DAYS) / (INVESTMENT_ZERO_DAYS - INVESTMENT_FULL_DAYS), 0.0, 1.0)


def draft_slot_rate(pick: Any) -> float:
    try:
        number = int(pick)
    except (TypeError, ValueError):
        return 0.0
    if number <= 0:
        return 0.0
    return next(rate for limit, rate in DRAFT_SLOT_RATES if number <= limit)


# --------------------------------------------------------------------------- seeding the starting league

def _team_ids_by_abbrev(canonical: dict[str, Any]) -> dict[str, str]:
    return {str(team.get("abbrev")): str(team.get("id")) for team in canonical.get("teams", []) if team.get("id")}


def _real_trade_arrivals(canonical: dict[str, Any], root) -> dict[str, tuple[str, str]]:
    """Player id -> (date, receiving team id) for players acquired in the real 2025-26 and 2026 offseason trades."""
    import json
    from pathlib import Path

    path = Path(root) / REAL_TRADES_PATH
    if not path.exists():
        return {}
    try:
        trades = json.loads(path.read_text(encoding="utf-8")).get("trades", [])
    except (OSError, ValueError):
        return {}
    by_name = {}
    for player in canonical.get("players", []):
        by_name.setdefault(_norm_name(player.get("name")), player)
    teams = _team_ids_by_abbrev(canonical)
    arrivals: dict[str, tuple[str, str]] = {}
    for trade in sorted(trades, key=lambda row: str(row.get("date") or "")):
        day = str(trade.get("date") or "")[:10]
        for asset in trade.get("assets", []):
            if asset.get("kind") != "player":
                continue
            player = by_name.get(_norm_name(asset.get("name_or_desc")))
            team_id = teams.get(str(asset.get("to")))
            if player and team_id and player.get("team_id") == team_id:
                arrivals[player["id"]] = (day, team_id)
    return arrivals


def _consecutive_seasons_with(record: dict[str, Any], abbrev: str, espn_to_abbrev: dict[str, str]) -> tuple[float, int | None, bool]:
    """Seasons in a row with this team counting back from his latest NBA season (2024-25 or later, so a player who
    missed 2025-26 injured still counts), the first such season's start year, and whether that is his whole career."""
    seasons = sorted(record.get("seasons") or [], key=lambda row: str(row.get("season") or ""), reverse=True)
    if not seasons or str(seasons[0].get("season") or "")[:4] < "2024":
        return 0.0, None, False
    count = 0.0
    first_year = None
    for row in seasons:
        teams = {espn_to_abbrev.get(str(team)) for team in row.get("team_ids") or []}
        if abbrev not in teams:
            break
        try:
            first_year = int(str(row["season"]).split("-")[0])
        except (KeyError, ValueError):
            break
        if len(teams) > 1:
            count += 0.5  # traded during that season: count half of it and stop
            break
        count += 1.0
    all_career = count > 0 and count == float(len(seasons))
    return count, first_year, all_career


def seed_player_tenure(canonical: dict[str, Any], *, game_mode: str = "standard", root=None) -> dict[str, Any]:
    """The opening ledger for a new save of the 2026-27 league, from real career and draft data in the repo.

    Tenure: consecutive seasons with his current team in the ESPN season-by-team rows. Homegrown: drafted, and every
    NBA season with this team. Arrivals by trade from June 2025 on come from the real trade list (date known); other
    players who joined before 2025-26 are marked "joined" (trade or signing, not known). Players new to the team in
    the 2026 offseason with no recorded trade are free-agent signings, with their contract as the investment.
    """
    ledger = {"version": LEDGER_VERSION, "players": {}, "folded_log_ids": [], "folded_since": ""}
    if str(game_mode or "") == "fantasy_draft":
        return ledger  # every roster is redrafted: nobody has tenure with his fantasy team
    from .career_stats import career_record
    from .research import ESPN_TEAM_ID_TO_ABBREV
    from .resource_paths import game_resource_root

    root = root or game_resource_root()
    arrivals = _real_trade_arrivals(canonical, root)
    contracts = {c.get("player_id"): c for c in canonical.get("contracts", [])}
    players: dict[str, Any] = {}
    for player in canonical.get("players", []):
        team_id = player.get("team_id")
        abbrev = player.get("team_abbrev")
        if not team_id or not abbrev:
            continue
        record = career_record(player) or {}
        seasons, first_year, all_career = _consecutive_seasons_with(record, str(abbrev), ESPN_TEAM_ID_TO_ABBREV)
        draft_year = player.get("draft_year")
        drafted = str(player.get("draft_status") or "") == "drafted" and draft_year is not None
        arrival = arrivals.get(player["id"])
        entry: dict[str, Any] = {"team_id": team_id, "how": "joined", "homegrown": False, "draft": None, "investments": []}
        if seasons > 0 and first_year is not None:
            entry["since"] = f"{first_year}-{SEASON_OPEN_DAY}"
            if drafted and all_career and int(draft_year) >= first_year - 2:
                entry.update(how="draft", homegrown=True)
            elif arrival:
                entry.update(how="trade", since=max(entry["since"], arrival[0]))
        elif drafted and int(draft_year) == 2026:
            entry.update(since="2026-06-24", how="draft", homegrown=True)
        elif arrival:
            entry.update(since=arrival[0], how="trade")
        else:
            # New to the team in the 2026 offseason with no recorded trade: a free-agent signing.
            entry.update(since="2026-07-06", how="signing")
            contract = contracts.get(player["id"]) or {}
            seasons_rows = contract.get("seasons") or []
            salary = float((seasons_rows[0] or {}).get("salary") or 0.0) if seasons_rows else 0.0
            if salary:
                entry["investments"].append({"kind": "signing", "date": entry["since"], "annual_salary": salary,
                                             "years": len(seasons_rows), "source": "starting_contract"})
        if arrival and entry["how"] == "trade":
            entry["investments"].append({"kind": "trade", "date": arrival[0], "package_value": None,
                                         "package_player_ids": [player["id"]], "source": "real_trade_list"})
        if entry["homegrown"]:
            traded_up = REAL_DRAFT_TRADE_UPS.get((_norm_name(player.get("name")), str(abbrev)))
            entry["draft"] = {"year": int(draft_year), "pick": player.get("draft_position"),
                              "date": traded_up or f"{int(draft_year)}-06-25", "traded_up": bool(traded_up)}
        players[player["id"]] = entry
    ledger["players"] = players
    return ledger


# --------------------------------------------------------------------------- folding transaction logs forward

def _log_contract_terms(log: dict[str, Any]) -> tuple[str | None, str | None, float, int]:
    assets = log.get("assets") or {}
    contract = assets.get("contract") or {}
    player_id = assets.get("player_id") or contract.get("player_id")
    teams = log.get("teams") or []
    team_id = contract.get("team_id") or contract.get("accepted_team_id") or (teams[0] if teams else None)
    annual = float(contract.get("annual_salary") or assets.get("salary") or 0.0)
    years = int(contract.get("years") or contract.get("original_contract_years") or assets.get("years") or 0)
    return player_id, team_id, annual, years


def _trade_flows(log: dict[str, Any]) -> list[tuple[str, list, list]]:
    from .transactions import transaction_log_flows

    try:
        return transaction_log_flows(log)
    except Exception:  # a malformed log must never stop a save from being written
        return []


def _pick_traded_up(logs: list[dict[str, Any]], team_id: str, pick_id: str, selection_date: str) -> bool:
    for log in logs:
        if log.get("transaction_type") != "trade":
            continue
        days = _days_between(log.get("date"), selection_date)
        if days is None or days < 0 or days > DRAFT_TRADE_UP_WINDOW_DAYS:
            continue
        for tid, _outgoing, incoming in _trade_flows(log):
            if tid == team_id and any(a.get("kind") == "pick" and a.get("id") == pick_id for a in incoming):
                return True
    return False


def _new_stint(team_id: str, day: str, how: str) -> dict[str, Any]:
    return {"team_id": team_id, "since": day, "how": how, "homegrown": False, "draft": None, "investments": []}


def _with_investment(entry: dict[str, Any], investment: dict[str, Any], day: str) -> dict[str, Any]:
    kept = [row for row in entry.get("investments") or []
            if (_days_between(row.get("date"), day) or 0) < INVESTMENT_ZERO_DAYS]
    return {**entry, "investments": [*kept, investment]}


def fold_transaction_logs(ledger: dict[str, Any] | None, logs: list[dict[str, Any]],
                          incoming_rookies: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return the ledger with every not-yet-folded log applied (copy on write; the input is not changed)."""
    ledger = ledger or {"version": LEDGER_VERSION, "players": {}, "folded_log_ids": [], "folded_since": ""}
    folded = set(ledger.get("folded_log_ids") or [])
    since = str(ledger.get("folded_since") or "")
    pending = sorted(
        (log for log in logs if isinstance(log, dict) and log.get("id") not in folded
         and str(log.get("date") or "")[:10] >= since),
        key=lambda log: (str(log.get("date") or "")[:10], str(log.get("id") or "")))
    if not pending:
        return ledger
    players = dict(ledger.get("players") or {})
    rookies = {row.get("prospect_id"): row for row in incoming_rookies or [] if row.get("prospect_id")}
    for log in pending:
        day = str(log.get("date") or "")[:10]
        kind = log.get("transaction_type")
        if kind == "trade" and str(log.get("status") or "").startswith("applied"):
            values = {e.get("perspective_team_id"): e for e in log.get("evaluations") or []}
            for team_id, _outgoing, incoming in _trade_flows(log):
                arriving = [a.get("id") for a in incoming if a.get("kind") == "player" and a.get("id")]
                given = (values.get(team_id) or {}).get("outgoing_value")
                for player_id in arriving:
                    entry = _new_stint(team_id, day, "trade")
                    players[player_id] = _with_investment(entry, {
                        "kind": "trade", "date": day, "package_value": None if given is None else round(float(given), 2),
                        "package_player_ids": arriving}, day)
        elif kind == "draft_selection":
            assets = log.get("assets") or {}
            rookie = rookies.get(assets.get("prospect_id")) or {}
            player_id, team_id = rookie.get("player_id"), rookie.get("team_id")
            if player_id and team_id:
                entry = _new_stint(team_id, day, "draft")
                entry["homegrown"] = True
                entry["draft"] = {"year": int(str(rookie.get("draft_year") or day[:4])[:4]), "pick": rookie.get("overall_pick"),
                                  "date": day, "traded_up": _pick_traded_up(logs, team_id, str(assets.get("pick_id")), day)}
                players[player_id] = entry
        elif kind in {"free_agent_signing", "ai_free_agent_signing", "ai_re_signing", "re_signing", "extension",
                      "rookie_extension", "auto_depth_signing"}:
            player_id, team_id, annual, years = _log_contract_terms(log)
            if not player_id or not team_id:
                continue
            entry = players.get(player_id)
            if not entry or entry.get("team_id") != team_id:
                entry = _new_stint(team_id, day, "signing")
            if annual >= 5_000_000:
                entry = _with_investment(entry, {"kind": "extension" if "extension" in kind else "signing", "date": day,
                                                 "annual_salary": annual, "years": years}, day)
            players[player_id] = entry
        elif kind == "waiver_claim":
            teams = log.get("teams") or []
            player_id = (log.get("assets") or {}).get("player_id")
            if player_id and len(teams) >= 2:
                players[player_id] = _new_stint(teams[1], day, "waiver_claim")
        elif kind in {"roster_cut", "buyout", "waiver_clearance", "release"}:
            player_id = (log.get("assets") or {}).get("player_id")
            if player_id in players:
                players[player_id] = {**players[player_id], "team_id": None}
    latest = max(str(log.get("date") or "")[:10] for log in pending)
    window_start = (date.fromisoformat(latest).toordinal() - LEDGER_LOG_WINDOW_DAYS) if _date(latest) else None
    new_since = date.fromordinal(window_start).isoformat() if window_start else since
    keep_ids = {log.get("id") for log in logs if isinstance(log, dict) and str(log.get("date") or "")[:10] >= new_since}
    folded_ids = sorted((folded & keep_ids) | {log.get("id") for log in pending if log.get("id")})
    return {"version": LEDGER_VERSION, "players": players, "folded_log_ids": folded_ids, "folded_since": max(since, new_since)}


def tenure_ledger_view(save: dict[str, Any]) -> dict[str, Any]:
    """The save's ledger with its newest logs applied, without changing the save."""
    return fold_transaction_logs(save.get(LEDGER_KEY), save.get("transaction_logs") or [], save.get("incoming_rookies") or [])


def commit_tenure_ledger(save: dict[str, Any]) -> None:
    """Fold the save's logs into its ledger (called when the save is written, before old logs are archived)."""
    if LEDGER_KEY not in save:
        return
    save[LEDGER_KEY] = tenure_ledger_view(save)


# --------------------------------------------------------------------------- reading the ledger

def ownership_profile(canonical: dict[str, Any], player: dict[str, Any], team_id: str) -> dict[str, Any]:
    """Years with this team, homegrown flag, how he arrived and his still-active investments (faded)."""
    ledger = canonical.get(LEDGER_KEY) or {}
    entry = (ledger.get("players") or {}).get(player.get("id"))
    today = str((canonical.get("meta") or {}).get("current_date") or "")
    if not entry or entry.get("team_id") != team_id or not today:
        return {"known": False, "years": 0.0, "homegrown": False, "how": "unknown", "investments": []}
    days = _days_between(entry.get("since"), today)
    years = max(0.0, (days or 0) / 365.25)
    investments = []
    draft = entry.get("draft")
    if draft and entry.get("homegrown"):
        fade = investment_fade(_days_between(draft.get("date"), today))
        rate = draft_slot_rate(draft.get("pick")) + (TRADED_UP_RATE if draft.get("traded_up") else 0.0)
        if fade > 0 and rate > 0:
            investments.append({"kind": "draft", "date": draft.get("date"), "pick": draft.get("pick"),
                                "traded_up": bool(draft.get("traded_up")), "fade": round(fade, 3), "rate": rate})
    for row in entry.get("investments") or []:
        fade = investment_fade(_days_between(row.get("date"), today))
        if fade > 0:
            investments.append({**row, "fade": round(fade, 3)})
    return {"known": True, "years": round(years, 2), "homegrown": bool(entry.get("homegrown")), "how": entry.get("how"),
            "since": entry.get("since"), "investments": investments}


def _trade_investment_rate(canonical: dict[str, Any], row: dict[str, Any], player_id: str, market_value: float) -> float:
    package = row.get("package_value")
    if package is None:
        share_factor = 1.0  # starting-league trades: assume a fair price was paid
    else:
        from .transactions import player_asset_values_by_id

        values = player_asset_values_by_id(canonical)
        ids = [pid for pid in row.get("package_player_ids") or [player_id] if pid]
        weights = {pid: max(1.0, float((values.get(pid) or {}).get("player_value") or 0.0)) for pid in ids}
        share = float(package) * weights.get(player_id, 1.0) / max(1.0, sum(weights.values()))
        share_factor = _clamp(share / max(10.0, market_value), 0.3, 1.5)
    return TRADE_INVESTMENT_RATE * share_factor


def _signing_investment_rate(row: dict[str, Any]) -> float:
    annual = float(row.get("annual_salary") or 0.0)
    if annual < 5_000_000:
        return 0.0
    return SIGNING_INVESTMENT_RATE * _clamp(annual / 30_000_000, 0.0, 1.5)


def _rebuilding(state: dict[str, Any]) -> bool:
    return state.get("phase") == "rebuilding" or state.get("window_phase") == "rebuilding"


# Fields the trade-block reasons read. Every league valuation has them; a partial record (a test stand-in, or a player
# priced before his valuation row exists) reads as neutral instead of failing.
VALUATION_DEFAULTS = {"player_value": 0.0, "contract_surplus": 0.0, "health_risk": 0.0, "development_upside": 0.0}


def move_reasons(canonical: dict[str, Any], player: dict[str, Any], team_id: str, *, core: bool = False) -> dict[str, float]:
    """The team's own reasons to move this player, each with how far it scales the premium down.

    The trade-block reasons (transactions.trade_block_score), plus a GM listing and stalled contract talks. Two
    corrections so the reasons describe the team, not the player's own presence on the roster: "older than the team
    timeline" is a full reason only for a rebuilding team (a team that is merely "developing" around a 31-year-old
    franchise player is not selling him), and roster-shape reasons do not apply to core players; a position surplus
    counts only if the position is still over-full after he leaves.
    """
    from .transactions import (own_departure_state, player_asset_values_by_id, player_position_bucket, trade_block_score,
                               valuation_or_fallback)

    state = next((s for s in canonical.get("team_strategic_states", []) if s.get("team_id") == team_id), None)
    if not state:
        return {}
    valuation = valuation_or_fallback(player_asset_values_by_id(canonical), player["id"], player)
    _score, reasons, _preferred = trade_block_score(
        canonical, player, SimpleNamespace(**{**VALUATION_DEFAULTS, **valuation}),
        SimpleNamespace(team_id=team_id, phase=state.get("phase"), excesses=list(state.get("excesses") or [])))
    reasons = list(reasons)
    if player["id"] in set((canonical.get("team_trade_blocks") or {}).get(team_id) or []):
        reasons.append("gm_listed")
    if player["id"] in set(canonical.get("ai_trade_pressure_player_ids") or []):
        reasons.append("extension_talks_stalled")
    if "position_surplus" in reasons:
        after = own_departure_state(canonical, team_id, state, {player["id"]})
        if f"{player_position_bucket(player)}_depth" not in (after.get("excesses") or []):
            reasons = [r for r in reasons if r not in {"position_surplus", "veteran_surplus_slot"}]
    if not core:
        reasons.extend(_money_reasons(canonical, player, team_id, state))
    out = {}
    for reason in reasons:
        if reason not in MOVE_REASON_FACTORS or (core and reason in ROSTER_SHAPE_REASONS):
            continue
        factor = MOVE_REASON_FACTORS[reason]
        if reason == "older_than_team_timeline" and not _rebuilding(state):
            factor = DEVELOPING_TIMELINE_FACTOR
        out[reason] = factor
    return out


def _money_reasons(canonical: dict[str, Any], player: dict[str, Any], team_id: str, state: dict[str, Any]) -> list[str]:
    """Contract reasons to move a non-core player (trade step 2): the team is over the luxury tax and he is paid
    $5M+, or he is a veteran (28+) on an expiring deal and the team is not contending (it would lose him for
    nothing). Real sellers cited tax savings in 12 of the 43 trades in data/research/real_trades."""
    from .transactions import (CANONICAL_SEASON, cap_lines_for_season, contract_for_player, current_salary,
                               maybe_float, team_current_salary_total)

    season = str((canonical.get("meta") or {}).get("active_season") or CANONICAL_SEASON)
    contract = contract_for_player(canonical, player["id"]) or {}
    salary = current_salary(contract) or 0.0
    out = []
    if salary >= 5_000_000 and team_current_salary_total(canonical, team_id) > cap_lines_for_season(season)["tax_line"]:
        out.append("over_tax_line")
    seasons = [s for s in contract.get("seasons", []) if float(s.get("salary") or 0) > 0 and str(s.get("season") or "") >= season]
    contending = state.get("window_phase") == "peak" or state.get("phase") in {"contending", "contending_with_future_upside"}
    age = maybe_float(player.get("display_age", player.get("age"))) or 27.0
    if salary > 0 and len(seasons) <= 1 and age >= 28.0 and not contending:
        out.append("expiring_veteran_non_contender")
    return out


def own_player_premium(canonical: dict[str, Any], player: dict[str, Any] | None, team_id: str, base_value: float,
                       *, market_value: float | None = None, role_minutes: float | None = None) -> dict[str, Any]:
    """Extra value an AI team puts on its own player when asked to give him up (0 for anyone else's player).

    ``base_value`` is the team's own value for him in his current role (his value to this team). Returns the
    components in value points plus the rates, reasons and ledger facts behind them, for explanations.
    """
    empty = {"attachment": 0.0, "tenure": 0.0, "investment": 0.0, "total": 0.0}
    if not player or player.get("team_id") != team_id or team_id in set(canonical.get("_human_team_ids") or []):
        return empty
    if base_value <= 0:
        return empty
    memo = canonical.get("_trade_ownership_memo")
    key = (team_id, player.get("id"))
    rates = memo.get(key) if memo is not None else None
    if rates is None:
        rates = _premium_rates(canonical, player, team_id, market_value, role_minutes)
        if memo is not None:
            memo[key] = rates
    scale = rates["context_factor"]
    out = {name: round(base_value * rates[name] * scale, 3) for name in ("attachment", "tenure", "investment")}
    out["total"] = round(sum(out.values()), 3)
    out["detail"] = rates
    return out


def _premium_rates(canonical, player, team_id, market_value, role_minutes) -> dict[str, Any]:
    from .transactions import (_search_market_value, maybe_float, player_asset_values_by_id, trade_value_role_minutes,
                               valuation_or_fallback)

    valuation = valuation_or_fallback(player_asset_values_by_id(canonical), player["id"], player)
    if market_value is None:
        market_value = _search_market_value(canonical, player, valuation)
    if role_minutes is None:
        role_minutes = trade_value_role_minutes(player, valuation)
    age = maybe_float(player.get("age")) or 27.0
    state = next((s for s in canonical.get("team_strategic_states", []) if s.get("team_id") == team_id), {}) or {}
    plan = (canonical.get("team_plans") or {}).get(team_id) or {}
    keep = []
    if player["id"] in set(plan.get("core_ids") or []):
        keep.append("planned_core")
    if age <= 25 and role_minutes >= 24:
        keep.append("young_starter")
    if role_minutes >= 30:
        keep.append("top_of_rotation")
    young_piece = age <= YOUNG_PIECE_AGE and ("young_starter" in keep or "planned_core" in keep)
    attachment = ATTACHMENT_BASE + min(YOUNG_KEEP_REASON_CAP if young_piece else KEEP_REASON_CAP,
                                       sum(KEEP_REASON_RATES[name] for name in keep))
    profile = ownership_profile(canonical, player, team_id)
    quality = _clamp((market_value - 35.0) / 35.0, 0.0, 1.0)
    tenure = TENURE_RATE_PER_YEAR * min(TENURE_YEARS_CAP, profile["years"]) * quality
    if profile["homegrown"] and profile["years"] >= 2:
        tenure += HOMEGROWN_RATE * quality
    if age > TENURE_AGE_FADE_START:
        tenure *= _clamp((TENURE_AGE_FADE_END - age) / (TENURE_AGE_FADE_END - TENURE_AGE_FADE_START), 0.0, 1.0)
    if _rebuilding(state):
        tenure *= REBUILDING_TENURE_FACTOR
    investment = 0.0
    for row in profile["investments"]:
        if row["kind"] == "draft":
            rate = row["rate"]
        elif row["kind"] == "trade":
            rate = _trade_investment_rate(canonical, row, player["id"], market_value)
        else:
            rate = _signing_investment_rate(row)
        investment += rate * row["fade"]
    investment = min(INVESTMENT_CAP, investment)
    total = attachment + tenure + investment
    if total > TOTAL_RATE_CAP:
        shrink = TOTAL_RATE_CAP / total
        attachment, tenure, investment = attachment * shrink, tenure * shrink, investment * shrink
    reasons = move_reasons(canonical, player, team_id, core="planned_core" in keep)
    if young_piece:
        reasons = {name: factor for name, factor in reasons.items() if name not in MONEY_REASONS}
    return {"attachment": round(attachment, 4), "tenure": round(tenure, 4), "investment": round(investment, 4),
            "context_factor": min(reasons.values()) if reasons else 1.0, "keep_reasons": keep,
            "move_reasons": sorted(reasons),
            "years_with_team": profile["years"], "homegrown": profile["homegrown"], "arrived_by": profile["how"],
            "investments": [{k: row.get(k) for k in ("kind", "date", "pick", "traded_up", "fade") if row.get(k) is not None}
                            for row in profile["investments"]]}


def premium_note(premium: dict[str, Any]) -> str:
    """The premium's parts in plain words for the evaluation notes ('' when there is none)."""
    detail = premium.get("detail") or {}
    parts = []
    if premium.get("attachment"):
        parts.append(f"attachment +{premium['attachment']:.1f}")
    if premium.get("tenure"):
        years = detail.get("years_with_team") or 0
        parts.append(f"tenure +{premium['tenure']:.1f} ({years:.1f} yrs{', homegrown' if detail.get('homegrown') else ''})")
    if premium.get("investment"):
        kinds = ", ".join(sorted({row.get("kind") + (" traded up" if row.get("traded_up") else "")
                                  for row in detail.get("investments") or []}))
        parts.append(f"investment +{premium['investment']:.1f} ({kinds})")
    if not parts:
        return ""
    text = ", ".join(parts)
    if detail.get("move_reasons"):
        text += f" (scaled x{detail.get('context_factor', 1.0):.2f}: {', '.join(r.replace('_', ' ') for r in detail['move_reasons'])})"
    return text
