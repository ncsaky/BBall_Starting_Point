"""Luxury-tax money in AI trade decisions (trade 2b).

12 of the 43 real trades from 2025-26 to 2026-27 (data/research/real_trades/trades_2025_2027.json) were tax moves:
a team over the tax shed salary, often paying second-round picks (Finney-Smith with three seconds, LeVert with two,
Saric absorbed by Chicago for seconds, Isaiah Joe and Aaron Wiggins moved for two seconds each while Oklahoma City cut
its bill), and a team with room took the salary for the picks. The acceptance check had no term for money, so none of
these could happen. Here the tax a trade saves (or costs) a team becomes value for that team.

The game's cap rules (transactions.cap_lines_for_season) have a tax line and a hard cap, and no tax bill. The bill
uses the real NBA rates (2023 collective bargaining agreement): $1.50 per dollar for the first bracket over the line,
$1.75, $2.50, $3.25, then 50 cents more per further bracket; the bracket is about 3.33% of the tax line ($5.685M on a
$170.8M line in 2024-25). The repeater rates (a dollar more per bracket for teams taxed in 3 of the previous 4
seasons) are not used: the save keeps no payroll history, so no team can be identified as a repeater.

The tax is charged on the payroll at the end of the regular season, counting each player's full-season salary, so a
deadline deal saves the full year's tax. Seasons counted: the current one until the regular season ends (weight 1),
the next one at half weight (contracts and free agency can still change it); from mid-April to June only the coming
seasons. Only AI teams get this term; the human team's own evaluations never change.

Money becomes trade value at TAX_POINTS_PER_MILLION points per $1M of tax, scaled by the owner's spending appetite
(the front office's financial discipline) and the team's phase (a contender accepts paying more tax than a rebuilder),
and saturating at TAX_VALUE_CAP points, so a team deep in the tax does not give away good players for nothing. The
rate is calibrated on the real tax moves: in this game a future second-round pick is worth about 15-20 points, and
real teams pay one to three seconds to shed $5-15M of salary that saves them roughly $8-25M in tax, which is about
2-4 points per $1M saved; 3 is used.

Young starters and young core players are never moved for tax savings alone (the user's direction): when the team
sends one out, the tax term can cost it but never pays it.
"""
from __future__ import annotations

import math
from typing import Any

BRACKET_SHARE_OF_TAX_LINE = 0.0333
NON_REPEATER_RATES = (1.50, 1.75, 2.50, 3.25)
RATE_STEP_AFTER = 0.50
TAX_POINTS_PER_MILLION = 3.0
TAX_VALUE_CAP = 40.0
NEXT_SEASON_WEIGHT = 0.5
PHASE_FACTOR = {"peak": 0.75, "entering": 1.0, "exiting": 1.0, "rebuilding": 1.25}
YOUNG_PIECE_AGE = 25.5
YOUNG_STARTER_MINUTES = 24.0


def _tx():
    from . import transactions
    return transactions


def season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def tax_seasons(canonical: dict[str, Any]) -> list[tuple[str, float]]:
    """(season label, weight) for the seasons whose tax a trade made today can still change."""
    tx = _tx()
    meta = canonical.get("meta") or {}
    today = str(meta.get("current_date") or "")
    try:
        year, month, day = int(today[:4]), int(today[5:7]), int(today[8:10])
    except ValueError:
        start = tx.season_start_from_label(str(meta.get("active_season") or tx.CANONICAL_SEASON))
        return [(season_label(start), 1.0), (season_label(start + 1), NEXT_SEASON_WEIGHT)]
    if month >= 7:
        start = year
    elif month < 4 or (month == 4 and day <= 15):
        start = year - 1
    else:  # regular season over: this season's bill is fixed
        return [(season_label(year), 1.0), (season_label(year + 1), NEXT_SEASON_WEIGHT)]
    return [(season_label(start), 1.0), (season_label(start + 1), NEXT_SEASON_WEIGHT)]


def luxury_tax_bill(payroll: float, season: str) -> float:
    """Tax owed (dollars) for a payroll in a season, at the non-repeater rates."""
    tx = _tx()
    line = tx.cap_lines_for_season(season)["tax_line"]
    over = payroll - line
    if over <= 0:
        return 0.0
    bracket = line * BRACKET_SHARE_OF_TAX_LINE
    bill, index = 0.0, 0
    while over > 0:
        rate = (NON_REPEATER_RATES[index] if index < len(NON_REPEATER_RATES)
                else NON_REPEATER_RATES[-1] + RATE_STEP_AFTER * (index - len(NON_REPEATER_RATES) + 1))
        chunk = min(over, bracket)
        bill += chunk * rate
        over -= chunk
        index += 1
    return bill


def _payroll(canonical: dict[str, Any], team_id: str, season: str) -> float:
    # Cached per search context by transactions.team_salary_total_for_season (financial facts).
    return float(_tx().team_salary_total_for_season(canonical, team_id, season) or 0.0)


def _package_salary(canonical: dict[str, Any], assets: list[dict[str, Any]], season: str) -> float:
    tx = _tx()
    total = 0.0
    for asset in assets:
        if asset.get("kind") != "player":
            continue
        salary = tx.contract_salary_for_trade_season(tx.contract_for_player(canonical, asset.get("id")), season)
        total += float(salary or 0.0)
    return total


def tax_saved(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
              outgoing: list[dict[str, Any]]) -> dict[str, Any]:
    """Tax the trade saves the team (dollars; negative = extra tax), weighted over the open seasons."""
    total, rows = 0.0, []
    for season, weight in tax_seasons(canonical):
        before = _payroll(canonical, team_id, season)
        if before <= 0:
            continue
        after = before + _package_salary(canonical, incoming, season) - _package_salary(canonical, outgoing, season)
        saved = luxury_tax_bill(before, season) - luxury_tax_bill(after, season)
        if saved:
            rows.append({"season": season, "payroll_before": before, "payroll_after": after, "saved": saved,
                         "weight": weight})
        total += weight * saved
    return {"saved": total, "seasons": rows}


def _state(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    return next((s for s in canonical.get("team_strategic_states", []) if s.get("team_id") == team_id), {}) or {}


def money_weight(canonical: dict[str, Any], team_id: str) -> float:
    """Points per $1M of tax for this team: the owner's spending appetite and the team's phase."""
    front = next((f for f in canonical.get("front_office_profiles", []) if f.get("team_id") == team_id), {}) or {}
    discipline = float(front.get("financial_discipline") or 58.0)
    owner = max(0.7, min(1.4, 1.0 + (discipline - 58.0) / 40.0))
    state = _state(canonical, team_id)
    window = state.get("window_phase") or {"contending": "peak", "contending_with_future_upside": "peak",
                                           "developing": "entering", "retooling": "exiting"}.get(state.get("phase"), "rebuilding")
    return TAX_POINTS_PER_MILLION * owner * PHASE_FACTOR.get(window, 1.0)


def young_piece_outgoing(canonical: dict[str, Any], team_id: str, outgoing: list[dict[str, Any]]) -> bool:
    """The team sends out a young starter (25 or younger, 24+ minutes) or a young player in its core plan."""
    tx = _tx()
    core = set(((canonical.get("team_plans") or {}).get(team_id) or {}).get("core_ids") or [])
    values = tx.player_asset_values_by_id(canonical)
    for asset in outgoing:
        if asset.get("kind") != "player":
            continue
        player = tx.player_by_id(canonical, asset.get("id"))
        if not player or player.get("team_id") != team_id:
            continue
        age = tx.maybe_float(player.get("display_age", player.get("age"))) or 27.0
        if age > YOUNG_PIECE_AGE:
            continue
        minutes = tx.trade_value_role_minutes(player, tx.valuation_or_fallback(values, player["id"], player))
        if minutes >= YOUNG_STARTER_MINUTES or player["id"] in core:
            return True
    return False


def tax_value(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
              outgoing: list[dict[str, Any]]) -> float:
    """Trade value of the tax a trade saves (positive) or adds (negative) for an AI team; 0 for the human team."""
    if team_id in set(canonical.get("_human_team_ids") or []):
        return 0.0
    saved = tax_saved(canonical, team_id, incoming, outgoing)["saved"]
    if not saved:
        return 0.0
    raw = saved / 1_000_000 * money_weight(canonical, team_id)
    value = math.copysign(TAX_VALUE_CAP * (1.0 - math.exp(-abs(raw) / TAX_VALUE_CAP)), raw)
    if value > 0 and young_piece_outgoing(canonical, team_id, outgoing):
        return 0.0
    return round(value, 3)


def tax_note(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
             outgoing: list[dict[str, Any]], value: float) -> str:
    if not value:
        return ""
    saved = tax_saved(canonical, team_id, incoming, outgoing)["saved"]
    verb = "saves" if saved > 0 else "adds"
    return f" Luxury tax: the deal {verb} about ${abs(saved) / 1e6:.1f}M (value {value:+.1f})."
