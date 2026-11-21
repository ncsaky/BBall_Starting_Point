"""AI payroll discipline: free agency, re-signing, waiver claims and in-season signings plan around the tax (TRADE-VOLUME).

Why: with the trade AI on the real tax line, payrolls ran away in year two (21 of 30 teams in the tax, a $26M payout
per team, a 6-trade deadline), because free agency, re-signing and waiver claims checked only the hard cap or let
minimum contracts through. Atlanta got under the line at the 2028 deadline, then claimed Chris Paul off waivers two
days later and went back over. Real front offices plan their end-of-season payroll against the tax line: recent
seasons had about 7-14 teams over the line at the deadline and about 6-8 at season end (Hoops Rumors, "Projected NBA
taxpayers for 2025/26", Feb and Apr 2026: 14 projected before the February 2026 deadline, 7 after it; 10 taxpayers in
2024-25).

The rule, for AI teams only (the user's team is never changed):
- **Projected end-of-season payroll**: the team's salary for the season (active contracts plus dead money) plus the
  minimum contracts it must still sign to reach 14 players. A signing that fills one of those spots replaces a minimum
  contract the team would sign anyway.
- **What going over costs**: the tax bill it adds (real rates, repeat taxpayers at theirs: ``trade_tax.luxury_tax_bill``)
  plus, when it crosses the line, the share of the tax payout the team gives up. The share is the last recorded
  payout per team (``luxury_tax_payouts``), or ``DEFAULT_PAYOUT_SHARE`` before any season is recorded (real shares:
  $11.5M per team for 2024-25, about $4.9M projected for 2025-26 after the deadline).
- **What the owner will pay**: ``PHASE_TAX_BUDGET`` (dollars of tax plus lost payout for one addition) by the team's
  window phase (a contender at its peak pays, a rebuilding team does not), divided by the owner's money factor (the
  front office's visible money preferences, the same factor the trade code uses: ``trade_tax.owner_money_factor``), and
  scaled by how much the player matters: nothing for a player outside the rotation, full for a 28-minute starter, up to
  1.5x for a star. Keeping your own free agent counts 1.5x more (Bird rights: he cannot be replaced from outside while
  over the cap).
- A signing is declined when its cost is above that budget.
- **Room below the line by phase** (``PHASE_KEEP_ROOM``): a team that is not contending keeps some payroll room below
  the line when it adds a veteran in free agency or re-signing ($3M on the rise, $8M retooling, $20M rebuilding), so
  rebuilding teams carry cap-space payrolls and can take on contracts in trades. Half the room for young players (25
  or younger), and half again for re-signing a starter.
- **After the trade deadline** a team under the line never adds salary that would put it over (a trade can no longer
  fix it): the Atlanta case.
- **Franchise stars** (KEEP-STARS): re-signing one of the league's 15 best players skips the room-below-the-line rule
  and is worth up to ``STAR_RETENTION_TAX_BUDGET`` of tax and lost payout (divided by the owner's money factor).

FA-REAL slice 2 (the thin market): the room-below-the-line rule refused most AI bids in the 2027 replay, including
teams' Bird bids for their own regulars (Minnesota and Donte DiVincenzo, Milwaukee and Kyle Kuzma) and mid-level
signings for rotation needs: 502 of the day-one team-player pairs with a legal way to pay (86 got through). Real
front offices keep their regulars with Bird rights when they're worth the tax and use the mid-level when they have one
and a need; the tax itself is the owner's constraint. So:
- **Keeping a regular** (a Bird re-signing of a player of ``REGULAR_MINUTES``+) never keeps room below the line; only
  the tax bill against the owner's budget decides.
- **Room below the line** applies to rotation additions only for rebuilding teams (trade room for absorbing
  contracts), and to fringe additions (under ``REGULAR_MINUTES``) for every team that isn't contending.
- **Personality** (TRADE-MARKET's front-office traits, ``front_office``): an office known to work hard to stay under
  the tax keeps ``TAX_AVERSE_CUSHION`` below the line whatever the move and accepts half the tax; one known to pay the
  tax to win accepts ``SPENDS_TAX_FACTOR`` times as much and keeps no room; an urgent contender or rising team accepts up
  to ``URGENCY_TAX_SHARE`` more (urgency trait), a patient one a little less.
"""
from __future__ import annotations

from typing import Any

ROSTER_MINIMUM = 14                 # save.ROSTER_MINIMUM
FILL_SALARY = 2_250_000             # the minimum contract save.py's roster fills use
DEFAULT_PAYOUT_SHARE = 8_000_000    # before any season is recorded: between the real $4.9M (2025-26) and $11.5M (2024-25)
PHASE_TAX_BUDGET = {"peak": 30_000_000, "entering": 10_000_000, "exiting": 4_000_000, "rebuilding": 0.0}
ROTATION_MINUTES = 12.0             # below this a player matters nothing for the tax decision
STARTER_MINUTES = 28.0              # a full-importance starter
MAX_IMPORTANCE = 1.5
RE_SIGNING_IMPORTANCE = 1.5         # own free agents (Bird rights)
IN_SEASON_KINDS = {"waiver_claim", "in_season_signing"}
# Room below the tax line a team keeps by phase when it adds a veteran in free agency or re-signing. Without it, every
# team with room spent to the line: in the first test with the shared line, 18 of 30 teams ended 2027-28 within $5M
# under it and one had real room, so no team could take a salary dump and the 2028 deadline had 6 trades. The starting
# league (real 2026-27 contracts) has 6 teams $14M+ under the line; rebuilding teams carry cap-space payrolls.
PHASE_KEEP_ROOM = {"peak": 0.0, "entering": 3_000_000, "exiting": 8_000_000, "rebuilding": 20_000_000}
CEILING_KINDS = {"free_agency", "re_signing"}
# KEEP-STARS: keeping a franchise star (a top-15 player, save.is_franchise_star) is worth up to this much tax plus lost
# payout for the season, divided by the owner's money factor (so about $71M-$143M). No room-below-the-line rule
# applies. Denver let Nikola Jokic walk in the 2028 test because re-signing him left it $1.7M under the tax line, inside
# the $4M room a retooling team kept. Real contenders pay large bills to keep stars (Golden State's 2022-23 tax bill was
# about $170M).
STAR_RETENTION_TAX_BUDGET = 100_000_000
YOUNG_PLAYER_AGE = 25.0
# FA-REAL slice 2 (see the module notes).
REGULAR_MINUTES = 18.0          # a regular: Bird re-signings keep no room below the line; additions above it are "needs"
TAX_AVERSE_CUSHION = 3_000_000  # an office known to avoid the tax keeps this much below the line on any addition
# The owner's money factor (``owner_money_factor``, TRADE-FOLLOWUPS) already carries the same visible tax habit (1.25
# for an office that avoids the tax, 0.8 for one that pays it: the budget is divided by it). These multipliers add only
# the rest, so the combined effect is the one slice 2 measured: x0.5 for a tax-averse office, x1.6 for a tax payer.
from .trade_tax import OWNER_FACTOR_SPENDS_TAX, OWNER_FACTOR_TAX_AVERSE  # noqa: E402 (trade_tax imports nothing from here)

TAX_AVERSE_FACTOR = 0.5 * OWNER_FACTOR_TAX_AVERSE    # 0.625 with the owner factor 1.25
SPENDS_TAX_FACTOR = 1.6 * OWNER_FACTOR_SPENDS_TAX    # 1.28 with the owner factor 0.8
URGENCY_TAX_SHARE = 0.4         # +/- share of the owner's budget at full urgency (contending and rising teams only)


def _save():
    from . import save as save_module
    return save_module


def season_payroll(active: dict[str, Any], save: dict[str, Any], team_id: str, season: str) -> tuple[float, int]:
    """(payroll in dollars including dead money, players under contract for the season) for the team."""
    cap = _save().team_cap_summary(active, save, team_id, season=season)
    players = {p["id"] for p in active.get("players", []) if p.get("team_id") == team_id and not p.get("_inactive_player")}
    count = 0
    for contract in active.get("contracts", []):
        if contract.get("player_id") not in players:
            continue
        if any(str(row.get("season")) == str(season) and float(row.get("salary") or 0) > 0
               for row in contract.get("seasons") or []):
            count += 1
    return float(cap.get("salary_total") or 0.0), count


def roster_fill(count: int) -> float:
    return max(0, ROSTER_MINIMUM - count) * FILL_SALARY


def projected_end_payroll(active: dict[str, Any], save: dict[str, Any], team_id: str, season: str) -> float:
    payroll, count = season_payroll(active, save, team_id, season)
    return payroll + roster_fill(count)


def expected_payout_share(save: dict[str, Any], season: str) -> float:
    """The payout a team under the line expects: the latest recorded share per team (at or before ``season``)."""
    payouts = save.get("luxury_tax_payouts") or {}
    recorded = [s for s in payouts if s <= str(season)]
    if not recorded:
        return float(DEFAULT_PAYOUT_SHARE)
    return float((payouts[max(recorded)] or {}).get("share_per_team") or 0.0)


def is_repeater(save: dict[str, Any], team_id: str, season: str) -> bool:
    from .trade_tax import is_repeat_taxpayer
    return is_repeat_taxpayer({"team_payroll_history": save.get("team_payroll_history") or {}}, team_id, season)


def tax_cost(save: dict[str, Any], team_id: str, season: str, before: float, after: float) -> dict[str, float]:
    """Extra tax (dollars) and payout given up when the team's end-of-season payroll moves from before to after."""
    from .trade_tax import luxury_tax_bill
    from .cap_rules import cap_lines_for_season
    line = cap_lines_for_season(season)["tax_line"]
    repeater = is_repeater(save, team_id, season)
    tax = luxury_tax_bill(after, season, repeater) - luxury_tax_bill(before, season, repeater)
    lost = expected_payout_share(save, season) if before <= line < after else 0.0
    return {"tax": max(0.0, tax), "lost_payout": lost, "total": max(0.0, tax) + lost, "tax_line": line}


def team_phase(active: dict[str, Any], save: dict[str, Any], team_id: str) -> str:
    plan = (save.get("team_plans") or {}).get(team_id) or {}
    phase = plan.get("window_phase")
    if not phase:
        state = next((s for s in active.get("team_strategic_states", []) or [] if s.get("team_id") == team_id), {}) or {}
        phase = state.get("window_phase") or {"contending": "peak", "contending_with_future_upside": "peak",
                                                "developing": "entering", "retooling": "exiting"}.get(state.get("phase"))
    return phase if phase in PHASE_TAX_BUDGET else "rebuilding"


def owner_money_factor(active: dict[str, Any], team_id: str) -> float:
    """The trade code's owner factor (trade_tax.owner_money_factor): from the front office's visible money
    preferences (TRADE-FOLLOWUPS; it was the old hidden financial-discipline field)."""
    from .trade_tax import owner_money_factor as trade_factor
    return trade_factor(active, team_id)


def importance(minutes: float, kind: str) -> float:
    value = max(0.0, min(MAX_IMPORTANCE, (float(minutes) - ROTATION_MINUTES) / (STARTER_MINUTES - ROTATION_MINUTES)))
    return value * (RE_SIGNING_IMPORTANCE if kind == "re_signing" else 1.0)


def office_row(active: dict[str, Any], team_id: str) -> dict[str, Any] | None:
    """The team's front-office traits (TRADE-MARKET), or None (human teams, leagues without traits)."""
    from .front_office import office
    try:
        return office(active, team_id)
    except Exception:   # pragma: no cover - a league without the trade-market context
        return None


def personality_tax_factor(active: dict[str, Any], save: dict[str, Any], team_id: str) -> float:
    """How the office's known habits and urgency scale what the owner will pay in tax for one addition."""
    from .front_office import has_bias, urgency_level
    row = office_row(active, team_id)
    if not row:
        return 1.0
    factor = 1.0
    if has_bias(row, "spends_tax"):
        factor *= SPENDS_TAX_FACTOR
    if has_bias(row, "tax_averse"):
        factor *= TAX_AVERSE_FACTOR
    if team_phase(active, save, team_id) in {"peak", "entering"}:
        factor *= 1.0 + URGENCY_TAX_SHARE * urgency_level(row)
    return max(0.2, factor)


def owner_tax_budget(active: dict[str, Any], save: dict[str, Any], team_id: str, minutes: float, kind: str) -> float:
    return (PHASE_TAX_BUDGET[team_phase(active, save, team_id)] / owner_money_factor(active, team_id)
            * importance(minutes, kind) * personality_tax_factor(active, save, team_id))


def phase_payroll_ceiling(active: dict[str, Any], save: dict[str, Any], team_id: str, season: str, kind: str,
                          minutes: float, age: float | None) -> float | None:
    """The payroll a team that is not contending keeps below when it adds a player (None: no ceiling applies).

    Free agency and re-signing only. Half the room for a young player (YOUNG_PLAYER_AGE or younger: what a rebuild
    invests in) and half again for re-signing a starter (Bird rights); minimum roster fills never add payroll (see
    ``payroll_check``). In the first test with this rule young players were exempt, and rebuilding Sacramento signed
    $66M of free agents (Cason Wallace $26.4M among them) up to the line."""
    if kind not in CEILING_KINDS:
        return None
    from .cap_rules import cap_lines_for_season
    from .front_office import has_bias
    row = office_row(active, team_id)
    line = cap_lines_for_season(season)["tax_line"]
    if has_bias(row, "tax_averse"):
        # FA-REAL slice 2: an office known to avoid the tax stays under it on any addition.
        return line - TAX_AVERSE_CUSHION
    if has_bias(row, "spends_tax"):
        return None
    phase = team_phase(active, save, team_id)
    room = PHASE_KEEP_ROOM[phase]
    if room <= 0:
        return None
    regular = float(minutes) >= REGULAR_MINUTES
    if kind == "re_signing" and regular:
        return None    # FA-REAL slice 2: a team keeps its regulars with Bird rights; only the tax bill decides
    if regular and phase != "rebuilding":
        return None    # FA-REAL slice 2: a rotation need (the mid-level's use), up to the line
    if age is not None and float(age) <= YOUNG_PLAYER_AGE:
        room *= 0.5
    if kind == "re_signing" and float(minutes) >= STARTER_MINUTES:
        room *= 0.5
    return line - room


# TRADE-VOLUME-2: a rebuilding team does not spend free-agent money on veterans. Room by phase limits how close to
# the tax line a team gets, not what it buys: the rebuilding Clippers spent about $74M in 2028, Jimmy Butler (38) on a
# one-year $36M deal among it. Real rebuilders signed veterans only on short, cheap deals they could flip or that
# filled the roster; anything above the non-taxpayer mid-level exception ($15.044M in 2026-27, NBA.com cap release)
# went to younger players. Re-signing a team's own players is not affected.
VETERAN_AGE = 30.0
NON_TAXPAYER_MLE = 15_044_000


def veteran_price(season: str) -> float:
    from .cap_rules import growth_factor
    return NON_TAXPAYER_MLE * growth_factor(season)


def after_trade_deadline(save: dict[str, Any]) -> bool:
    """Between the trade deadline and the end of the regular season (no trade can fix the payroll any more)."""
    s = _save()
    today = str((save.get("state") or {}).get("current_date") or "")
    season = str((save.get("meta") or {}).get("season") or "")
    if not today or not season:
        return False
    start = s.season_start_year(season)
    return s.trade_deadline_date(start) < today <= f"{start + 1}-04-20"


def payroll_check(active: dict[str, Any], save: dict[str, Any], team_id: str | None, season: str, *,
                  add_salary: float, remove_salary: float = 0.0, roster_delta: int = 1, minutes: float = 0.0,
                  kind: str = "signing", committed: float = 0.0, committed_players: int = 0,
                  age: float | None = None, franchise_star: bool = False) -> dict[str, Any]:
    """Whether an AI team's front office accepts this payroll move for ``season``.

    ``add_salary`` / ``remove_salary``: this season's salary the move adds and removes (dollars); ``roster_delta``:
    players it adds to the roster; ``committed`` / ``committed_players``: salary and players already agreed but not yet
    in ``active`` (earlier re-signings in the same pass, live free-agent bids). Returns ok, reason and the numbers."""
    if not team_id or team_id in _save().human_controlled_team_ids(save):
        return {"ok": True, "reason": "user_team"}
    payroll, count = season_payroll(active, save, team_id, season)
    payroll += committed
    count += committed_players
    before = payroll + roster_fill(count)
    after = payroll + float(add_salary) - float(remove_salary) + roster_fill(count + roster_delta)
    cost = tax_cost(save, team_id, season, before, after)
    result = {"before": before, "after": after, "tax_line": cost["tax_line"], "tax": cost["tax"],
              "lost_payout": cost["lost_payout"], "cost": cost["total"], "budget": 0.0}
    if (kind == "free_agency" and age is not None and float(age) >= VETERAN_AGE
            and team_phase(active, save, team_id) == "rebuilding" and float(add_salary) > veteran_price(season)):
        return {**result, "ok": False, "reason": "rebuilding_team_does_not_pay_veterans"}
    if franchise_star and kind == "re_signing":
        budget = STAR_RETENTION_TAX_BUDGET / owner_money_factor(active, team_id)
        result.update(ceiling=None, budget=budget)
        if cost["total"] <= budget:
            return {**result, "ok": True, "reason": "keeps_its_franchise_star"}
        return {**result, "ok": False, "reason": "tax_cost_above_owner_budget"}
    ceiling =phase_payroll_ceiling(active, save, team_id, season, kind, minutes, age)
    result["ceiling"] = ceiling
    if ceiling is not None and after > before + 1 and after > ceiling:
        return {**result, "ok": False, "reason": "keeps_room_below_the_line_for_its_phase"}
    if cost["total"] <= 0:
        return {**result, "ok": True, "reason": "under_the_line_or_no_change"}
    if kind in IN_SEASON_KINDS and before <= cost["tax_line"] < after and after_trade_deadline(save):
        return {**result, "ok": False, "reason": "would_cross_the_tax_line_after_the_deadline"}
    budget = owner_tax_budget(active, save, team_id, minutes, kind)
    result["budget"] = budget
    if cost["total"] <= budget:
        return {**result, "ok": True, "reason": "worth_the_tax"}
    return {**result, "ok": False, "reason": "tax_cost_above_owner_budget"}


def plain_words(check: dict[str, Any]) -> str:
    if check.get("ok"):
        return ""
    if check.get("reason") == "would_cross_the_tax_line_after_the_deadline":
        return "It would put the team over the luxury tax line after the trade deadline."
    if check.get("reason") == "rebuilding_team_does_not_pay_veterans":
        return "A rebuilding team does not spend more than the mid-level exception on a veteran free agent."
    if check.get("reason") == "keeps_room_below_the_line_for_its_phase":
        return (f"The team keeps its payroll under about ${float(check.get('ceiling') or 0) / 1e6:.1f}M "
                "while it is not contending (room to take on contracts in trades).")
    return (f"It would cost about ${float(check.get('cost') or 0) / 1e6:.1f}M in luxury tax and lost payout "
            f"(the owner accepts about ${float(check.get('budget') or 0) / 1e6:.1f}M for this player).")
