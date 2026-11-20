"""Luxury-tax money in AI trade decisions (trade 2b).

12 of the 43 real trades from 2025-26 to 2026-27 (data/research/real_trades/trades_2025_2027.json) were tax moves:
a team over the tax shed salary, often paying second-round picks (Finney-Smith with three seconds, LeVert with two,
Saric absorbed by Chicago for seconds, Isaiah Joe and Aaron Wiggins moved for two seconds each while Oklahoma City cut
its bill), and a team with room took the salary for the picks. The acceptance check had no term for money, so none of
these could happen. Here the tax a trade saves (or costs) a team becomes value for that team.

The game's cap rules (transactions.cap_lines_for_season) have a tax line and a hard cap, and no tax bill. The bill
uses the real NBA rates (2023 collective bargaining agreement): $1.50 per dollar for the first bracket over the line,
$1.75, $2.50, $3.25, then 50 cents more per further bracket; the bracket is about 3.33% of the tax line ($5.685M on a
$170.8M line in 2024-25). Repeat taxpayers (taxed in at least 3 of the previous 4 seasons) pay a dollar more per
bracket ($2.50, $2.75, $3.50, $4.25, ...). Trade step 4 records each team's payroll when the regular season ends
(``record_season_payrolls``, kept in the save as ``team_payroll_history``), so a team becomes a repeater after its
third taxed season in the game; seasons before the save started are not known and count as untaxed.

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

Absorbing salary a team does not want (trade step 4, ``absorb_cost``). A team with room took bench salary for free in
trade 2b, because it valued any bench player a little above zero, so salary dumps almost never carried picks. Real
teams charge for it when the player is outside their plans: Charlotte took Dorian Finney-Smith ($13.3M, one year) with
three seconds, Chicago took Dario Saric (about $5.4M) for two seconds, Milwaukee took Caris LeVert ($28.9M over two
years, two smaller contracts back) with two seconds, Brooklyn took Julius Randle with the #28 pick. When the player
would play for the absorber, the absorber pays instead (Detroit gave two seconds for Isaiah Joe, Atlanta two for Aaron
Wiggins). So an AI team now prices the salary it takes on for players outside its rotation as a cost:
- **Dead money**: for each incoming player, the share of his salary that buys nothing: all of it when he would be
  out of the receiving team's rotation (8 minutes or less by his place on its depth chart), none when he would play
  18 minutes or more, in between linearly. For a team far from contending, later seasons of a veteran's contract are
  also partly dead (up to half, by its distance from contending and the player's age then, from 29 to 32). The first
  $2M a season of each player is free: the roster spot would cost about a minimum salary anyway.
- **Net of what leaves**: salary the team sends out in the same trade offsets it, season by season, so ordinary
  salary-matched trades cost little; the cost bites when a team takes on net money.
- **Seasons**: the current season at full weight until the regular season ends, later seasons at half weight (as the
  tax counts next season).
- **Price**: ABSORB_POINTS_PER_MILLION points per $1M of dead money, the same money rate as the tax (a dollar of
  salary costs an owner what a dollar of tax does), scaled by the owner's spending appetite and saturating at
  ABSORB_VALUE_CAP. With a future second worth about 18-22 points here, the absorber charges about half a second for
  $5M of dead money, one to two seconds for $13M, two for $25M and about a late first (the cap) for $60M or more: a
  little below the real prices above, which leaves room for the deal (the tax team saves $1.50 to $3.25 of tax per
  dollar of salary, so the same money rate on both sides still leaves a surplus to share).
Only AI teams get this term; the human team's own evaluations never change.
"""
from __future__ import annotations

import math
from typing import Any

BRACKET_SHARE_OF_TAX_LINE = 0.0333
NON_REPEATER_RATES = (1.50, 1.75, 2.50, 3.25)
REPEATER_RATES = (2.50, 2.75, 3.50, 4.25)
REPEATER_TAXED_SEASONS = 3              # taxed in at least 3 ...
REPEATER_LOOKBACK = 4                   # ... of the previous 4 seasons
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


def luxury_tax_bill(payroll: float, season: str, repeater: bool = False) -> float:
    """Tax owed (dollars) for a payroll in a season; repeat taxpayers pay the higher rates."""
    tx = _tx()
    line = tx.cap_lines_for_season(season)["tax_line"]
    over = payroll - line
    if over <= 0:
        return 0.0
    rates = REPEATER_RATES if repeater else NON_REPEATER_RATES
    bracket = line * BRACKET_SHARE_OF_TAX_LINE
    bill, index = 0.0, 0
    while over > 0:
        rate = rates[index] if index < len(rates) else rates[-1] + RATE_STEP_AFTER * (index - len(rates) + 1)
        chunk = min(over, bracket)
        bill += chunk * rate
        over -= chunk
        index += 1
    return bill


# ------------------------------------------------------------------------------------- payroll history (step 4)
def record_season_payrolls(save: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
    """Store every team's payroll for the season whose regular season just ended (called once, when the postseason
    starts). Additive save field ``team_payroll_history``: {season: {team_id: {payroll, tax_line, taxed}}}."""
    tx = _tx()
    from .save import canonical_with_save
    season = str((save.get("meta") or {}).get("season") or "")
    history = save.setdefault("team_payroll_history", {})
    if not season or season in history:
        return history
    active = canonical_with_save(canonical, save)
    line = tx.cap_lines_for_season(season)["tax_line"]
    rows = {}
    for team in active.get("teams", []):
        payroll = tx.team_salary_total_for_season(active, team["id"], season)
        if payroll is None:
            continue
        rows[team["id"]] = {"payroll": round(float(payroll)), "tax_line": line, "taxed": float(payroll) > line}
    history[season] = rows
    return history


def is_repeat_taxpayer(canonical: dict[str, Any], team_id: str, season: str) -> bool:
    """Taxed in at least 3 of the 4 seasons before ``season`` (recorded seasons only)."""
    history = canonical.get("team_payroll_history") or {}
    if not history:
        return False
    start = _tx().season_start_from_label(season)
    taxed = sum(1 for back in range(1, REPEATER_LOOKBACK + 1)
                if ((history.get(season_label(start - back)) or {}).get(team_id) or {}).get("taxed"))
    return taxed >= REPEATER_TAXED_SEASONS


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
        repeater = is_repeat_taxpayer(canonical, team_id, season)
        saved = luxury_tax_bill(before, season, repeater) - luxury_tax_bill(after, season, repeater)
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


# ------------------------------------------------------------------------------------- absorbed salary (step 4)
ABSORB_POINTS_PER_MILLION = 3.0         # the same money rate as the tax: a dollar of salary is a dollar of tax
ABSORB_VALUE_CAP = 60.0
ABSORB_FUTURE_WEIGHT = 0.5              # later seasons count like the tax's next season (rosters and plans change)
ABSORB_FREE_SALARY = 2_000_000          # a roster spot costs about a minimum salary anyway; only the rest is dead
ABSORB_ROTATION_MINUTES = 18.0
ABSORB_DEAD_MINUTES = 8.0
ABSORB_MAX_FUTURE_SEASONS = 4
REBUILD_VETERAN_DEAD_SHARE = 0.5
REBUILD_VETERAN_AGE_START = 29.0
REBUILD_VETERAN_AGE_FULL = 32.0


def absorb_seasons(canonical: dict[str, Any]) -> list[tuple[str, float]]:
    """(season, weight): the current season until its regular season ends, then later seasons at half weight."""
    first, _ = tax_seasons(canonical)[0]
    start = _tx().season_start_from_label(first)
    return [(first, 1.0)] + [(season_label(start + k), ABSORB_FUTURE_WEIGHT)
                             for k in range(1, ABSORB_MAX_FUTURE_SEASONS + 1)]


def _depth_chart(canonical: dict[str, Any], team_id: str) -> list[tuple[float, str]]:
    """The team's players by on-court value (memoized per league state)."""
    memo = canonical.get("_absorb_depth_memo")
    if memo is None or memo.get("source") is not canonical.get("players"):
        memo = {"source": canonical.get("players")}
        canonical["_absorb_depth_memo"] = memo
    if team_id not in memo:
        tx = _tx()
        values = tx.player_asset_values_by_id(canonical)
        rows = []
        for player in canonical.get("players", []):
            if player.get("team_id") != team_id or player.get("_inactive_player"):
                continue
            valuation = tx.valuation_or_fallback(values, player["id"], player)
            rows.append((float(valuation.get("on_court_value") or 0.0), player["id"]))
        memo[team_id] = sorted(rows, reverse=True)
    return memo[team_id]


def _on_court(canonical: dict[str, Any], player_id: str) -> float:
    tx = _tx()
    values = tx.player_asset_values_by_id(canonical)
    player = tx.player_by_id(canonical, player_id)
    return float(tx.valuation_or_fallback(values, player_id, player).get("on_court_value") or 0.0)


def expected_minutes_on_team(canonical: dict[str, Any], team_id: str, player_id: str,
                             incoming: list[dict[str, Any]], outgoing: list[dict[str, Any]]) -> float:
    """Minutes the player would get on the receiving team from his place on its depth chart after the trade."""
    tx = _tx()
    mine = _on_court(canonical, player_id)
    leaving = {a.get("id") for a in outgoing if a.get("kind") == "player"} | {player_id}
    better = sum(1 for value, pid in _depth_chart(canonical, team_id) if pid not in leaving and value > mine)
    better += sum(1 for a in incoming if a.get("kind") == "player" and a.get("id") != player_id
                  and _on_court(canonical, a.get("id")) > mine)
    return tx.expected_minutes_for_destination_rank(better + 1)


def dead_share(minutes: float) -> float:
    span = ABSORB_ROTATION_MINUTES - ABSORB_DEAD_MINUTES
    return max(0.0, min(1.0, (ABSORB_ROTATION_MINUTES - minutes) / span))


def dead_money(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
               outgoing: list[dict[str, Any]]) -> dict[str, Any]:
    """Weighted dead salary (dollars) the team takes on, net of the salary it sends out, with per-player detail."""
    tx = _tx()
    players = [a for a in incoming if a.get("kind") == "player"]
    if not players:
        return {"dead": 0.0, "players": []}
    distance = float(_state(canonical, team_id).get("contend_distance") or 0.0)
    shares = {}
    for asset in players:
        player = tx.player_by_id(canonical, asset.get("id")) or {}
        minutes = expected_minutes_on_team(canonical, team_id, asset.get("id"), incoming, outgoing)
        age = tx.maybe_float(player.get("display_age", player.get("age"))) or 27.0
        shares[asset.get("id")] = (dead_share(minutes), age, minutes)
    total, detail = 0.0, {}
    for index, (season, weight) in enumerate(absorb_seasons(canonical)):
        dead_in = 0.0
        for asset in players:
            share, age, _ = shares[asset["id"]]
            if index and distance > 0:
                ramp = (age + index - REBUILD_VETERAN_AGE_START) / (REBUILD_VETERAN_AGE_FULL - REBUILD_VETERAN_AGE_START)
                share = max(share, REBUILD_VETERAN_DEAD_SHARE * distance * max(0.0, min(1.0, ramp)))
            salary = float(tx.contract_salary_for_trade_season(tx.contract_for_player(canonical, asset["id"]), season) or 0.0)
            salary = max(0.0, salary - ABSORB_FREE_SALARY)
            if share and salary:
                dead_in += share * salary
                detail[asset["id"]] = detail.get(asset["id"], 0.0) + weight * share * salary
        if not dead_in:
            continue
        total += weight * max(0.0, dead_in - _package_salary(canonical, outgoing, season))
    return {"dead": total, "players": [{"player_id": pid, "dead": round(v), "minutes": shares[pid][2]}
                                         for pid, v in sorted(detail.items())]}


def owner_money_factor(canonical: dict[str, Any], team_id: str) -> float:
    front = next((f for f in canonical.get("front_office_profiles", []) if f.get("team_id") == team_id), {}) or {}
    discipline = float(front.get("financial_discipline") or 58.0)
    return max(0.7, min(1.4, 1.0 + (discipline - 58.0) / 40.0))


def absorb_cost(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
                outgoing: list[dict[str, Any]]) -> float:
    """Trade value lost by taking on salary for players outside the team's plans (<= 0); 0 for the human team."""
    if team_id in set(canonical.get("_human_team_ids") or []):
        return 0.0
    if not any(a.get("kind") == "player" for a in incoming):
        return 0.0
    dead = dead_money(canonical, team_id, incoming, outgoing)["dead"]
    if dead <= 0:
        return 0.0
    raw = dead / 1_000_000 * ABSORB_POINTS_PER_MILLION * owner_money_factor(canonical, team_id)
    return round(-ABSORB_VALUE_CAP * (1.0 - math.exp(-raw / ABSORB_VALUE_CAP)), 3)


def money_value(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
                outgoing: list[dict[str, Any]]) -> float:
    """The trade's money term for an AI team: tax saved or added, plus the cost of absorbed dead salary."""
    return round(tax_value(canonical, team_id, incoming, outgoing) + absorb_cost(canonical, team_id, incoming, outgoing), 3)


def absorb_note(canonical: dict[str, Any], team_id: str, incoming: list[dict[str, Any]],
                outgoing: list[dict[str, Any]], value: float) -> str:
    if not value:
        return ""
    dead = dead_money(canonical, team_id, incoming, outgoing)["dead"]
    return f" Absorbed salary: about ${dead / 1e6:.1f}M of it buys no rotation minutes (value {value:+.1f})."
