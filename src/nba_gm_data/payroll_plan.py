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
  front office's financial discipline, the same factor the trade code uses: ``trade_tax.owner_money_factor``), and
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
YOUNG_PLAYER_AGE = 25.0


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
    """The trade code's owner factor (financial discipline 58 -> 1.0; 0.7 to 1.4), built when the context lacks it."""
    from .trade_tax import owner_money_factor as trade_factor
    if active.get("front_office_profiles"):
        return trade_factor(active, team_id)
    from .transactions import generated_front_office_values
    team = next((t for t in active.get("teams", []) if t.get("id") == team_id), {}) or {}
    profile = next((p for p in active.get("team_profiles", []) or [] if p.get("team_id") == team_id), None)
    discipline = float(generated_front_office_values(str(team.get("abbrev") or ""), profile)["financial_discipline"])
    return max(0.7, min(1.4, 1.0 + (discipline - 58.0) / 40.0))


def importance(minutes: float, kind: str) -> float:
    value = max(0.0, min(MAX_IMPORTANCE, (float(minutes) - ROTATION_MINUTES) / (STARTER_MINUTES - ROTATION_MINUTES)))
    return value * (RE_SIGNING_IMPORTANCE if kind == "re_signing" else 1.0)


def owner_tax_budget(active: dict[str, Any], save: dict[str, Any], team_id: str, minutes: float, kind: str) -> float:
    return PHASE_TAX_BUDGET[team_phase(active, save, team_id)] / owner_money_factor(active, team_id) * importance(minutes, kind)


def phase_payroll_ceiling(active: dict[str, Any], save: dict[str, Any], team_id: str, season: str, kind: str,
                          minutes: float, age: float | None) -> float | None:
    """The payroll a team that is not contending keeps below when it adds a player (None: no ceiling applies).

    Free agency and re-signing only. Half the room for a young player (YOUNG_PLAYER_AGE or younger: what a rebuild
    invests in) and half again for re-signing a starter (Bird rights); minimum roster fills never add payroll (see
    ``payroll_check``). In the first test with this rule young players were exempt, and rebuilding Sacramento signed
    $66M of free agents (Cason Wallace $26.4M among them) up to the line."""
    if kind not in CEILING_KINDS:
        return None
    room = PHASE_KEEP_ROOM[team_phase(active, save, team_id)]
    if room <= 0:
        return None
    if age is not None and float(age) <= YOUNG_PLAYER_AGE:
        room *= 0.5
    if kind == "re_signing" and float(minutes) >= STARTER_MINUTES:
        room *= 0.5
    from .cap_rules import cap_lines_for_season
    return cap_lines_for_season(season)["tax_line"] - room


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
                  age: float | None = None) -> dict[str, Any]:
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
    ceiling = phase_payroll_ceiling(active, save, team_id, season, kind, minutes, age)
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
    if check.get("reason") == "keeps_room_below_the_line_for_its_phase":
        return (f"The team keeps its payroll under about ${float(check.get('ceiling') or 0) / 1e6:.1f}M "
                "while it is not contending (room to take on contracts in trades).")
    return (f"It would cost about ${float(check.get('cost') or 0) / 1e6:.1f}M in luxury tax and lost payout "
            f"(the owner accepts about ${float(check.get('budget') or 0) / 1e6:.1f}M for this player).")
