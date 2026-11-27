"""What a long injury takes off a trade target's price (AI-TRADES-SENSE).

The season review had San Antonio pay a first-round pick, a second and Luke Kornet on January 30 for Kristaps
Porzingis, who had been ruled out through June before opening night. A long injury only marked a player as salary
filler (trade_targets.salary_filler); it never lowered what a buyer would pay, and the buyer's rotation projection
counted him as playing. Real buyers price an injured player by the time he will miss: a player out for the season is
bought for his contract and his later seasons, not this season's games.

The discount, for an AI buyer pricing a player it does not own who is out LONG_INJURY_DAYS or more:
- **This season**: the share of the rest of this season (through the end of the playoffs, mid-June) he will miss,
  times how much of a player's price is this season's play for the buyer. That share follows the buyer's window:
  a contender buys for now (PRESENT_SHARE["peak"] 0.55), a rebuilder for later (0.2).
- **Next season**: days out past this season's end, as a share of a whole season, times NEXT_SEASON_SHARE (0.25).
- At most MAX_DISCOUNT (0.85) of his price: he still has a contract and a future.
The seller's own view of its player is unchanged (a contender doesn't sell its hurt star cheaply), and the human
team's evaluations are unchanged.

The same missed share decides how much the incoming player counts in the buyer's projected rotation
(trade_roster.trade_roster_outlook): a player out for the season adds nothing to it.
"""
from __future__ import annotations

from datetime import date
from typing import Any

LONG_INJURY_DAYS = 30
SEASON_END_MONTH_DAY = (6, 15)    # the Finals end in mid-June
SEASON_START_MONTH_DAY = (10, 20)  # opening night
FULL_SEASON_DAYS = 238             # opening night to mid-June
PRESENT_SHARE = {"peak": 0.55, "entering": 0.4, "exiting": 0.45, "rebuilding": 0.2}
NEXT_SEASON_SHARE = 0.25
MAX_DISCOUNT = 0.85


def _tx():
    from . import transactions
    return transactions


def _today(canonical: dict[str, Any]) -> date | None:
    return _tx().parse_iso_date((canonical.get("meta") or {}).get("current_date"))


def return_dates(canonical: dict[str, Any]) -> dict[str, date]:
    """{player_id: return date} for players out LONG_INJURY_DAYS or more (memoized per health rows and date)."""
    rows = canonical.get("player_health_states") or []
    today = _today(canonical)
    memo = canonical.get("_long_injury_memo")
    if memo and memo[0] is rows and memo[1] == today:
        return memo[2]
    found: dict[str, date] = {}
    if today is not None:
        for health in rows:
            if health.get("availability_status") != "out":
                continue
            end = _tx().parse_iso_date(health.get("return_date"))
            if end and (end - today).days >= LONG_INJURY_DAYS:
                found[str(health.get("player_id"))] = end
    canonical["_long_injury_memo"] = (rows, today, found)
    return found


def missed_shares(canonical: dict[str, Any], player_id: str) -> tuple[float, float]:
    """(share of the rest of this season he misses, share of next season he misses); (0, 0) when not long-injured."""
    end = return_dates(canonical).get(str(player_id))
    today = _today(canonical)
    if end is None or today is None:
        return 0.0, 0.0
    finish_year = today.year + 1 if today.month >= 7 else today.year
    season_end = date(finish_year, *SEASON_END_MONTH_DAY)
    start = max(today, date(finish_year - 1, *SEASON_START_MONTH_DAY))
    remaining = max(1, (season_end - start).days)
    this = max(0.0, min(1.0, (min(end, season_end) - start).days / remaining))
    next_start = date(finish_year, *SEASON_START_MONTH_DAY)
    following = max(0.0, min(1.0, (end - next_start).days / FULL_SEASON_DAYS))
    return this, following


def injury_discount(canonical: dict[str, Any], player_id: str, team_id: str) -> float:
    """Share of the player's price an AI buyer takes off for the time he will miss (0 for the human team)."""
    if team_id in set(canonical.get("_human_team_ids") or []):
        return 0.0
    this, following = missed_shares(canonical, player_id)
    if not this and not following:
        return 0.0
    state = next((s for s in canonical.get("team_strategic_states", []) if s.get("team_id") == team_id), {}) or {}
    present = PRESENT_SHARE.get(str(state.get("window_phase") or "rebuilding"), 0.3)
    return min(MAX_DISCOUNT, present * this + NEXT_SEASON_SHARE * following)
