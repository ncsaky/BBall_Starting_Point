"""The money calculator (FA-REAL slice 1): for any team and any move, is it legal, how is it paid for, and what does
it lock in.

One answer for the offer builder, AI bids, the AI re-signing pass, roster repair, waivers and the save (AGENTS.md rule
4). Real rules: the 2023 collective bargaining agreement as summarised in docs/agents/tasks/fa-realism-research.md
(Article VII for the cap, exceptions, holds and hard caps; Article II §§6-7 and Exhibit C for maximum and minimum
salaries; Article VII §8 for when a new signing can be traded).

Three numbers per team, each counting what the real rules count:
- **cap payroll**: signed salaries (the cap charge, so a veteran's one-year minimum counts at the two-year minimum),
  dead money, cap holds for free agents whose rights the team still holds, unsigned first-round picks and, from July 1
  to opening night, a rookie minimum for each empty roster spot below 12. Cap room is the salary cap minus this.
- **tax payroll**: signed salaries and dead money (no holds). The luxury tax is measured on this.
- **apron payroll**: the tax payroll plus outstanding qualifying offers (slice 3; unlikely bonuses don't exist in the
  game).

Ways to pay for a signing (``ROUTES``): Bird rights (his own team), cap room, the minimum, the room mid-level, the
full (non-taxpayer) mid-level, the taxpayer mid-level and the bi-annual exception. Each exception is a yearly budget
that can be split across players. Using the full mid-level or the bi-annual hard-caps the team at the first apron for
the rest of the cap year; the taxpayer mid-level hard-caps it at the second apron. Bird rights can take a team past
either apron, but never past a hard cap it has already triggered.

The save keeps each team's cap year in ``save["cap_ledger"]["seasons"][season][team_id]``: exception money used, the
signings, whether it used cap room, the hard cap it triggered and the holds it renounced. Signing quotes (``quote``)
are pure; ``commit`` records a signing; ``reserve`` / ``release`` let an outstanding offer (an AI or user bid) hold its
money until it resolves: a bid's ``payment`` is counted as reserved while the bid is active, and a signed offer sheet's
payment while it is pending (slice 3, ``offer_sheets``), so the same room or exception cannot be promised twice.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .cap_rules import (
    AVERAGE_SALARY_CAP_SHARE,
    BASE_SEASON,
    bird_max_years,
    bird_raise,
    cap_lines_for_season,
    growth_factor,
    max_salary,
    season_start,
)

# ---------------------------------------------------------------------------------------------------------------------
# Fixed amounts for 2026-27 (NBA cap announcement, nba.com "NBA salary cap 2026-27 season"; Hoops Rumors 2026-27
# minimum salary scale). Later seasons grow with the cap (the CBA ties all of them to the cap).

MINIMUM_SCALE_2026 = (
    1_357_763, 2_185_116, 2_449_421, 2_537_526, 2_625_627, 2_845_883,
    3_066_143, 3_286_399, 3_506_659, 3_524_115, 3_876_529,
)
EXCEPTION_AMOUNTS_2026 = {
    "non_taxpayer_mle": 15_044_000,
    "taxpayer_mle": 6_064_000,
    "room_mle": 9_366_000,
    "bi_annual": 5_477_000,
}
EXCEPTION_MAX_YEARS = {"non_taxpayer_mle": 4, "taxpayer_mle": 2, "room_mle": 3, "bi_annual": 2, "minimum": 2}
OUTSIDE_RAISE = 0.05
AI_HARD_CAP_ROSTER_FILL = 14                # AI-TRADES-SENSE: see quote()
MINIMUM_ROSTER_FOR_CAP = 12                 # empty spots below 12 carry a rookie-minimum charge from July 1
VETERAN_MINIMUM_SERVICE = 3                 # one-year minimums for 3+ years of service are partly reimbursed
VETERAN_MINIMUM_CAP_SERVICE = 2             # ... and count at the two-year minimum
BIG_BIRD_RAISE = 0.20                       # a Bird re-signing raise above 20% over the cap moves Dec 15 to Jan 15

ROUTES = ("bird", "cap_room", "minimum", "room_mle", "non_taxpayer_mle", "taxpayer_mle", "bi_annual")
EXCEPTION_ROUTES = ("room_mle", "non_taxpayer_mle", "taxpayer_mle", "bi_annual")
ROUTE_LABELS = {
    "bird_full": "full Bird rights",
    "bird_early": "Early Bird rights",
    "bird_non": "Non-Bird rights",
    "bird": "Bird rights",
    "cap_room": "cap room",
    "minimum": "a minimum contract",
    "room_mle": "the room mid-level exception",
    "non_taxpayer_mle": "the full mid-level exception",
    "taxpayer_mle": "the taxpayer mid-level exception",
    "bi_annual": "the bi-annual exception",
}
ROUTE_SHORT = {
    "bird": "Bird rights", "cap_room": "Cap room", "minimum": "Minimum", "room_mle": "Room mid-level",
    "non_taxpayer_mle": "Full mid-level", "taxpayer_mle": "Taxpayer mid-level", "bi_annual": "Bi-annual",
}
HARD_CAP_LEVELS = ("first_apron", "second_apron")
HARD_CAP_WORDS = {"first_apron": "the first apron", "second_apron": "the second apron"}
ROUTE_HARD_CAP = {"non_taxpayer_mle": "first_apron", "bi_annual": "first_apron", "taxpayer_mle": "second_apron"}


def _label(start: int) -> str:
    return f"{start}-{str(start + 1)[-2:]}"


def _m(value: float) -> str:
    return f"${float(value) / 1_000_000:.1f}M"


def scaled(amount_2026: float, season: str | None) -> int:
    """A 2026-27 dollar figure grown with the cap to ``season``."""
    return int(round(float(amount_2026) * growth_factor(season)))


def exception_amount(route: str, season: str | None) -> int:
    return scaled(EXCEPTION_AMOUNTS_2026[route], season)


def minimum_salary(season: str | None, years_of_service: int) -> int:
    """The minimum salary for a player with this many years in the league (CBA Exhibit C, first season)."""
    return scaled(MINIMUM_SCALE_2026[max(0, min(10, int(years_of_service)))], season)


def minimum_schedule(season: str, years_of_service: int, years: int) -> list[int]:
    """A minimum contract's salaries: each later year is his minimum with one more year of service, in that year's
    scale (the scale's later-year columns, approximated by the next service column)."""
    start = season_start(season)
    return [minimum_salary(_label(start + k), int(years_of_service) + k) for k in range(max(1, int(years)))]


def minimum_cap_charge(season: str | None, years_of_service: int, years: int) -> int:
    """A one-year minimum for a veteran (3+ years of service) counts at the two-year minimum: the league reimburses
    the rest (CBA Art. VII §4(h)). Salary and cap charge therefore differ."""
    if int(years) == 1 and int(years_of_service) >= VETERAN_MINIMUM_SERVICE:
        return minimum_salary(season, VETERAN_MINIMUM_CAP_SERVICE)
    return minimum_salary(season, years_of_service)


def true_max_salary(season: str | None, years_of_service: int, previous_salary: float = 0.0) -> float:
    """25/30/35% of the cap by service, or 105% of his previous salary if higher (CBA Art. II §7)."""
    return max_salary(season, years_of_service, previous_salary)


def raise_schedule(first_salary: float, years: int, rate: float) -> list[int]:
    """Each year adds ``rate`` of the FIRST year's salary (CBA Art. VII §5: raises are percentage points of year one,
    not compounded). $30M at 8% is $30M, $32.4M, $34.8M."""
    return [int(round(float(first_salary) * (1.0 + float(rate) * k))) for k in range(max(1, int(years)))]


def average_salary(season: str | None) -> float:
    """The league's average salary (an estimate, cap_rules.AVERAGE_SALARY_CAP_SHARE), for the previous season."""
    previous = _label(season_start(season) - 1)
    return cap_lines_for_season(previous)["salary_cap"] * AVERAGE_SALARY_CAP_SHARE


def years_of_service(player: dict[str, Any], season: str) -> int:
    from .contract_ai import years_of_service as service
    return service(player or {}, season)


# ---------------------------------------------------------------------------------------------------------------------
# Dates

def cap_year(save: dict[str, Any]) -> str:
    """The cap year a signing made today counts in: the one contract-season switch (FA-REAL slice 2,
    offseason_calendar.contract_season): the next season from the day the offseason opens (June 17) through rollover,
    else the current season. Before, this switched on June 22 or by phase name."""
    from .offseason_calendar import contract_season
    return contract_season({"meta": {"season": str((save.get("meta") or {}).get("season") or BASE_SEASON)},
                            "state": {"current_date": str((save.get("state") or {}).get("current_date") or "")}})


def _today(save: dict[str, Any], when: str | None = None) -> str:
    return str(when or (save.get("state") or {}).get("current_date") or f"{season_start(BASE_SEASON)}-10-20")


def offseason_window(season: str, today: str) -> tuple[bool, bool]:
    """(holds count, empty-roster charges count) on ``today`` for cap year ``season``: player holds from the day the
    offseason opens (the contract-season switch, June 17) to opening night, roster charges from July 1 (the league
    year) to opening night."""
    start = season_start(season)
    from .offseason_calendar import OFFSEASON_OPENS_MONTH_DAY
    holds = f"{start}-{OFFSEASON_OPENS_MONTH_DAY[0]:02}-{OFFSEASON_OPENS_MONTH_DAY[1]:02}" <= today < f"{start}-10-21"
    charges = f"{start}-07-01" <= today < f"{start}-10-21"
    return holds, charges


def trade_eligible_date(signed: str, season: str, *, route: str | None = None, bird_level: str | None = None,
                        previous_salary: float = 0.0, first_salary: float = 0.0, over_cap_after: bool = False) -> str:
    """When a newly signed free agent can be traded (CBA Art. VII §8): the later of three months after signing and
    December 15 of the cap year. A Full or Early Bird re-signing with a raise above 20% that leaves the team over the
    cap waits until January 15 instead of December 15 (not for minimum contracts)."""
    start = season_start(season)
    signed_day = date.fromisoformat(str(signed)[:10])
    three_months = _add_months(signed_day, 3)
    anchor = date(start, 12, 15)
    if (route == "bird" and bird_level in {"full", "early"} and over_cap_after and previous_salary > 0
            and float(first_salary) > float(previous_salary) * (1.0 + BIG_BIRD_RAISE)):
        anchor = date(start + 1, 1, 15)
    return max(three_months, anchor).isoformat()


def _add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    for back in range(4):
        try:
            return date(year, month, day.day - back)
        except ValueError:
            continue
    return day + timedelta(days=30 * months)


def newly_signed_trade_block(save: dict[str, Any], player_id: str, today: str | None = None) -> str | None:
    """For the trade code (hook-up left to the coordinator): the date a newly signed player becomes tradable, or None
    if he can be traded today. Reads ``trade_eligible_date`` from his contract (written at signing). Separate from the
    AI's own six-month re-trade habit (transactions.py)."""
    override = (save.get("contract_overrides") or {}).get(str(player_id)) or {}
    eligible = override.get("trade_eligible_date")
    if not eligible:
        return None
    return str(eligible) if _today(save, today) < str(eligible) else None


def trade_blocked_player_ids(save: dict[str, Any], today: str | None = None) -> set[str]:
    """Every newly signed player who can't be traded yet (his contract's ``trade_eligible_date`` is after today). For
    transactions.recently_signed_player_ids to use instead of its fixed December 1 unlock."""
    now = _today(save, today)
    return {str(pid) for pid, override in (save.get("contract_overrides") or {}).items()
            if override and override.get("trade_eligible_date") and now < str(override["trade_eligible_date"])}


# ---------------------------------------------------------------------------------------------------------------------
# The team's cap year in the save

def ledger_root(save: dict[str, Any]) -> dict[str, Any]:
    return save.setdefault("cap_ledger", {"version": 1, "seasons": {}})


def team_year(save: dict[str, Any], team_id: str, season: str, *, create: bool = False) -> dict[str, Any]:
    seasons = (save.get("cap_ledger") or {}).get("seasons") or {}
    row = (seasons.get(str(season)) or {}).get(str(team_id))
    if row is not None or not create:
        return row or {}
    root = ledger_root(save)
    return root["seasons"].setdefault(str(season), {}).setdefault(str(team_id), {
        "used": {}, "signings": [], "used_room": False, "hard_cap": None, "renounced": []})


def hard_cap(save: dict[str, Any], team_id: str, season: str) -> dict[str, Any] | None:
    """The ceiling the team triggered this cap year, if any: {level, amount, trigger, date}."""
    return team_year(save, team_id, season).get("hard_cap") or None


def trigger_hard_cap(save: dict[str, Any], team_id: str, season: str, level: str, trigger: str,
                     when: str | None = None) -> dict[str, Any]:
    """Record a hard cap for the rest of the cap year; the tightest one wins. For the trade code too (receiving a
    sign-and-trade: first apron; aggregating salaries or sending cash: second apron) once it is hooked up."""
    amount = float(cap_lines_for_season(season)[level])
    row = team_year(save, team_id, season, create=True)
    current = row.get("hard_cap")
    if not current or amount < float(current.get("amount") or 0.0):
        row["hard_cap"] = {"level": level, "amount": amount, "trigger": trigger, "date": _today(save, when)}
    return row["hard_cap"]


def renounced_ids(save: dict[str, Any], team_id: str, season: str) -> set[str]:
    return set(team_year(save, team_id, season).get("renounced") or [])


# ---------------------------------------------------------------------------------------------------------------------
# Who is on the books

_INDEX: dict[int, tuple[Any, int, int, dict[str, Any]]] = {}
_INDEX_SIZE = 3   # each entry keeps a whole league view alive


def _index(active: dict[str, Any], *, rescan: bool = False) -> dict[str, Any]:
    """Players, contracts and players by team for one prepared league view, cached while that view lives.

    ``rescan`` rebuilds players by team from the view (for callers that may have moved players in place); the cached
    map plus the save's roster overrides (``team_contracts(fresh=True)``) covers every move the game writes."""
    players_list = active.get("players", []) or []
    contracts_list = active.get("contracts", []) or []
    cached = _INDEX.get(id(active))
    if (cached is not None and cached[0] is active and cached[1] == len(players_list)
            and cached[2] == len(contracts_list)):
        base = cached[3]
    else:
        base = {"players": {p["id"]: p for p in players_list if p.get("id")},
                "contracts": {c.get("player_id"): c for c in contracts_list if c.get("player_id")},
                "by_team": _players_by_team(players_list)}
        while len(_INDEX) >= _INDEX_SIZE:
            _INDEX.pop(next(iter(_INDEX)))
        _INDEX[id(active)] = (active, len(players_list), len(contracts_list), base)
    if rescan:
        return {**base, "by_team": _players_by_team(players_list)}
    return base


def _players_by_team(players_list: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_team: dict[str, list[str]] = {}
    for player in players_list:
        team = player.get("team_id")
        if team and not player.get("_inactive_player"):
            by_team.setdefault(team, []).append(player["id"])
    return by_team


def _override_seasons(override: dict[str, Any]) -> list[dict[str, Any]]:
    seasons = override.get("seasons")
    if seasons:
        return list(seasons)
    from .save import offer_to_contract_seasons
    return offer_to_contract_seasons(dict(override))


def team_contracts(active: dict[str, Any], save: dict[str, Any], team_id: str, *, fresh: bool = True
                   ) -> list[tuple[str, list[dict[str, Any]]]]:
    """(player_id, contract seasons) for the team's roster. ``fresh``: also apply roster and contract changes written
    to the save after ``active`` was prepared (a day's earlier signings), so a quote never uses stale books."""
    index = _index(active, rescan=not fresh)
    members = set(index["by_team"].get(team_id, []))
    overrides = save.get("contract_overrides") or {}
    fresh_contract: set[str] = set()
    if fresh:
        for pid, tid in (save.get("roster_overrides") or {}).items():
            if tid == team_id:
                if pid not in members:
                    members.add(pid)
                    fresh_contract.add(pid)
            elif pid in members:
                members.discard(pid)
    rows = []
    for pid in sorted(members):
        contract = index["contracts"].get(pid)
        override = overrides.get(pid) if fresh else None
        if override and (pid in fresh_contract or contract is None
                         or override.get("signed_season") != contract.get("signed_season")
                         or len(override.get("seasons") or []) != len(contract.get("seasons") or [])):
            seasons = _override_seasons(override)
        else:
            seasons = list((contract or {}).get("seasons") or [])
        rows.append((pid, seasons))
    return rows


def season_row(seasons: list[dict[str, Any]], season: str) -> dict[str, Any] | None:
    for row in seasons:
        if row.get("season") == season and row.get("salary") is not None:
            return row
    return None


def cap_charge(row: dict[str, Any]) -> float:
    value = row.get("cap_charge")
    return float(value if value is not None else row.get("salary") or 0.0)


# ---------------------------------------------------------------------------------------------------------------------
# Cap holds

def _previous_salary(contract_seasons: list[dict[str, Any]], season: str) -> float:
    rows = [r for r in contract_seasons or [] if r.get("salary") is not None]
    at = [r for r in rows if str(r.get("season")) == season] or rows[-1:]
    return float(at[-1].get("salary") or 0.0) if at else 0.0


def hold_amount(level: str, previous_salary: float, season: str, service: int, *, rookie_scale: bool = False,
                previous_season: str | None = None) -> float:
    """A free agent's cap hold (CBA Art. VII §4(a)(2)): Full Bird 190% of his previous salary below the league average,
    150% at or above (300% / 250% coming off a first-round rookie deal), Early Bird 130%, Non-Bird 120%. Never above
    his maximum or below his minimum; a player coming off a minimum salary holds at the minimum."""
    previous = max(0.0, float(previous_salary or 0.0))
    minimum = float(minimum_cap_charge(season, service, 1))
    prior_min = float(minimum_salary(previous_season or _label(season_start(season) - 1), max(0, service - 1)))
    if previous <= prior_min * 1.02:
        return minimum
    if level == "full":
        below = previous < average_salary(season)
        share = (3.0 if below else 2.5) if rookie_scale else (1.9 if below else 1.5)
    elif level == "early":
        share = 1.3
    else:
        share = 1.2
    return max(minimum, min(share * previous, true_max_salary(season, service, previous)))


_BIRD_CACHE: dict[tuple, dict[str, Any]] = {}


def _cached_bird_rights(save: dict[str, Any], player: dict[str, Any], team_id: str, expiring: str,
                        contract: dict[str, Any] | None) -> dict[str, Any]:
    from .contract_ai import bird_rights
    override = (save.get("contract_overrides") or {}).get(str(player.get("id"))) or {}
    clock = (save.get("bird_clocks") or {}).get(str(player.get("id"))) or {}
    key = (str(player.get("id")), team_id, expiring, str(override.get("signed_season") or ""),
           str(clock.get("since") or ""), str(player.get("draft_year") or player.get("age") or ""),
           tuple((r.get("season"), r.get("salary")) for r in (contract or {}).get("seasons") or []))
    hit = _BIRD_CACHE.get(key)
    if hit is None:
        if len(_BIRD_CACHE) > 5000:
            _BIRD_CACHE.clear()
        hit = bird_rights(save, player, team_id, expiring, contract)
        _BIRD_CACHE[key] = hit
    return dict(hit)


def team_holds(active: dict[str, Any], save: dict[str, Any], team_id: str, season: str) -> list[dict[str, Any]]:
    """The free agents whose rights the team still holds for cap year ``season``, with their hold."""
    expiring = _label(season_start(season) - 1)
    index = _index(active)
    renounced = renounced_ids(save, team_id, season)
    owners = save.get("roster_overrides") or {}
    holds = []
    seen = set()
    for right in save.get("re_signing_rights", []) or []:
        pid = str(right.get("player_id") or "")
        if right.get("team_id") != team_id or str(right.get("season")) != expiring or pid in seen or pid in renounced:
            continue
        player = index["players"].get(pid)
        if player is None:
            continue
        if owners.get(pid, player.get("team_id")):
            continue          # he signed somewhere
        seen.add(pid)
        contract = index["contracts"].get(pid)
        bird = _cached_bird_rights(save, player, team_id, expiring, contract)
        service = years_of_service(player, season)
        rookie_scale = (str((contract or {}).get("status") or "") == "signed_rookie_contract"
                        or (int(player.get("draft_round") or 0) == 1 and service == 4))
        amount = hold_amount(bird["level"], bird["previous_salary"], season, service,
                             rookie_scale=rookie_scale, previous_season=expiring)
        # FA-REAL slice 2: a restricted free agent holds the greater of his hold and his qualifying offer (CBA Art.
        # VII §4(d)); a declined rookie-scale option caps it at the option's salary.
        from .offseason_decisions import declined_rookie_option, qo_record
        qo = qo_record(save, season, pid)
        if qo and qo.get("status") == "tendered":
            amount = max(amount, float((qo.get("max_qo_amount") if qo.get("maximum") else qo.get("amount")) or 0.0))
        declined = declined_rookie_option(save, pid)
        if declined:
            amount = min(amount, float(declined.get("salary") or amount))
        restricted = bool(qo and qo.get("status") == "tendered")
        holds.append({"player_id": pid, "name": player.get("name"), "kind": f"{bird['level']}_bird",
                      "bird": bird, "previous_salary": bird["previous_salary"], "amount": round(amount),
                      "years_of_service": service, "restricted": restricted,
                      # FA-REAL slice 3: apron salary counts an outstanding qualifying offer (CBA Art. VII §2(e)).
                      "qualifying_offer": round(float((qo.get("max_qo_amount") if qo.get("maximum") else qo.get("amount"))
                                                      or 0.0)) if restricted else 0})
    holds.sort(key=lambda h: (-h["amount"], str(h["name"])))
    return holds


def unsigned_pick_holds(save: dict[str, Any], team_id: str, season: str) -> list[dict[str, Any]]:
    """First-round picks drafted but not yet signed: 120% of their scale salary (the game signs most picks on draft
    night, so this is usually empty)."""
    start = season_start(season)
    rows = []
    for rookie in save.get("incoming_rookies", []) or []:
        if rookie.get("team_id") != team_id or rookie.get("roster_status") == "signed_rookie":
            continue
        if int(rookie.get("round") or rookie.get("draft_round") or 2) != 1 or int(rookie.get("draft_year") or 0) != start:
            continue
        salary = float(rookie.get("scale_salary") or rookie.get("projected_salary") or 0.0)
        if salary <= 0:
            continue
        rows.append({"player_id": rookie.get("player_id") or rookie.get("prospect_id"), "name": rookie.get("name"),
                     "kind": "first_round_pick", "amount": round(1.2 * salary)})
    return rows


# ---------------------------------------------------------------------------------------------------------------------
# Reservations: outstanding offers hold their money until they resolve

def reserve(offer: dict[str, Any], payment: dict[str, Any]) -> dict[str, Any]:
    """Attach a quote's payment to an outstanding offer; while the offer is active its money is held."""
    offer["payment"] = {k: payment.get(k) for k in ("route", "bird_level", "amount", "salary", "years", "season")}
    return offer


def release(offer: dict[str, Any]) -> None:
    """An outstanding offer resolved without a signing: its money is free again (status already inactive)."""
    offer.pop("payment", None)


def reservations(save: dict[str, Any], team_id: str, season: str, *, exclude_player_id: str | None = None
                 ) -> dict[str, float]:
    """Money held by the team's active offers this cap year, by route, plus 'apron' (everything but minimums)."""
    held: dict[str, float] = {}
    for offer in save.get("free_agent_offers", []) or []:
        if offer.get("status") != "active" or offer.get("team_id") != team_id:
            continue
        if exclude_player_id and offer.get("player_id") == exclude_player_id:
            continue
        payment = offer.get("payment") or {}
        if payment.get("season") and payment.get("season") != season:
            continue
        route = payment.get("route") or "unknown"
        amount = float(payment.get("amount") or float(offer.get("aav_millions") or 0.0) * 1_000_000)
        held[route] = held.get(route, 0.0) + amount
        if route != "minimum":
            held["apron"] = held.get("apron", 0.0) + amount
    # FA-REAL slice 3: a signed offer sheet keeps the bidder's room or exception money reserved until his team matches
    # or passes (CBA Art. XI §5(e): the bidder must keep enough Room until the sheet is settled).
    sheets = ((save.get("offseason_decisions") or {}).get("offer_sheets") or {}).values()
    for sheet in sheets:
        if sheet.get("status") != "pending" or sheet.get("bidder_team_id") != team_id:
            continue
        if exclude_player_id and sheet.get("player_id") == exclude_player_id:
            continue
        payment = sheet.get("payment") or {}
        if payment.get("season") and payment.get("season") != season:
            continue
        route = payment.get("route") or "cap_room"
        amount = float(payment.get("amount") or 0.0)
        held[route] = held.get(route, 0.0) + amount
        if route != "minimum":
            held["apron"] = held.get("apron", 0.0) + amount
    return held


# ---------------------------------------------------------------------------------------------------------------------
# The payroll breakdown

def team_payroll(active: dict[str, Any], save: dict[str, Any], team_id: str, season: str | None = None, *,
                 today: str | None = None, fresh: bool = True, include_reservations: bool = False,
                 exclude_player_id: str | None = None) -> dict[str, Any]:
    """Every number the rules use for one team and cap year (dollars)."""
    season = str(season or cap_year(save))
    today = _today(save, today)
    lines = cap_lines_for_season(season)
    players = []
    signed_salary = signed_charge = 0.0
    unresolved = 0
    index = _index(active)
    for pid, seasons in team_contracts(active, save, team_id, fresh=fresh):
        row = season_row(seasons, season)
        if row is None:
            if any(r.get("season") == season and r.get("salary") is None for r in seasons):
                unresolved += 1
            continue
        salary = float(row.get("salary") or 0.0)
        charge = cap_charge(row)
        signed_salary += salary
        signed_charge += charge
        players.append({"player_id": pid, "name": (index["players"].get(pid) or {}).get("name"),
                        "salary": salary, "cap_charge": charge})
    from .contract_protection import waived_total
    dead = float(waived_total(save, team_id, season))
    holds_on, charges_on = offseason_window(season, today)
    holds = team_holds(active, save, team_id, season) if holds_on else []
    holds += unsigned_pick_holds(save, team_id, season) if holds_on else []
    hold_total = float(sum(h["amount"] for h in holds))
    counted = len(players) + len(holds)
    empty = max(0, MINIMUM_ROSTER_FOR_CAP - counted) if charges_on else 0
    roster_charge = empty * float(minimum_salary(season, 0))
    tax_payroll = signed_charge + dead
    cap_payroll = tax_payroll + hold_total + roster_charge
    # FA-REAL slice 3: apron salary also counts outstanding qualifying offers (CBA Art. VII §2(e): the greater of the
    # qualifying offer, the maximum qualifying offer or a match notice), so a team can't use an exception that
    # hard-caps it below the cost of keeping a restricted free agent it tendered. Ordinary holds don't count.
    qualifying_total = float(sum(float(h.get("qualifying_offer") or 0.0) for h in holds))
    state = team_year(save, team_id, season)
    previous = team_year(save, team_id, _label(season_start(season) - 1))
    held = reservations(save, team_id, season, exclude_player_id=exclude_player_id) if include_reservations else {}
    ceiling = state.get("hard_cap") or None
    payroll = {
        "team_id": team_id,
        "season": season,
        "date": today,
        "lines": lines,
        "players": players,
        "roster_count": len(players),
        "signed_salary": signed_salary,
        "signed_cap_charge": signed_charge,
        "dead_money": dead,
        "holds": holds,
        "hold_total": hold_total,
        "empty_roster_spots": empty,
        "roster_charge": roster_charge,
        "cap_payroll": cap_payroll,
        "tax_payroll": tax_payroll,
        "apron_payroll": tax_payroll + qualifying_total,
        "qualifying_offer_total": qualifying_total,
        "cap_room": lines["salary_cap"] - cap_payroll,
        "room_under_tax": lines["tax_line"] - tax_payroll,
        "room_under_first_apron": lines["first_apron"] - tax_payroll,
        "room_under_second_apron": lines["second_apron"] - tax_payroll,
        "floor_shortfall": max(0.0, lines["salary_floor"] - tax_payroll),
        "hard_cap": ceiling,
        "room_under_hard_cap": (float(ceiling["amount"]) - tax_payroll) if ceiling else None,
        "used_room": bool(state.get("used_room")),
        "used": dict(state.get("used") or {}),
        "renounced": list(state.get("renounced") or []),
        "bi_annual_used_last_year": float((previous.get("used") or {}).get("bi_annual") or 0.0) > 0,
        "reserved": held,
        "unresolved_contract_count": unresolved,
    }
    payroll["_signings"] = list(state.get("signings") or [])
    payroll["exceptions"] = exception_status(payroll)
    return payroll


def _ntmle_reclassifiable(signings: list[dict[str, Any]], season: str) -> bool:
    """Small, short full mid-level signings (at most the taxpayer amount, two years) can later count as taxpayer use
    (CBA Art. VII §6(f)(5))."""
    used = [s for s in signings if s.get("route") == "non_taxpayer_mle"]
    return (sum(float(s.get("amount") or 0.0) for s in used) <= exception_amount("taxpayer_mle", season) + 1
            and all(int(s.get("years") or 1) <= 2 for s in used))


def exception_status(payroll: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Each exception's budget for the cap year: amount, used, held by outstanding offers, balance, and whether the
    team may use it at all (the per-signing apron test is in ``quote``)."""
    season = payroll["season"]
    used = payroll["used"]
    held = payroll.get("reserved") or {}
    used_room = payroll["used_room"]
    any_mle = sum(float(used.get(r) or 0.0) for r in ("non_taxpayer_mle", "taxpayer_mle", "bi_annual")) > 0
    room_mle_used = float(used.get("room_mle") or 0.0) > 0
    signings = payroll.get("_signings") or []
    out: dict[str, dict[str, Any]] = {}
    for route in EXCEPTION_ROUTES:
        amount = float(exception_amount(route, season))
        spent = float(used.get(route) or 0.0)
        reason = ""
        if route == "room_mle":
            if any_mle:
                reason = "Not available after using the full or taxpayer mid-level or the bi-annual this season."
            elif not used_room:
                reason = "Only for a team that has used its cap room this season."
        else:
            if used_room or room_mle_used:
                reason = "Not available after using cap room this season (the room mid-level replaces it)."
            if route in {"non_taxpayer_mle", "taxpayer_mle"}:
                spent = float(used.get("non_taxpayer_mle") or 0.0) + float(used.get("taxpayer_mle") or 0.0)
                if route == "taxpayer_mle" and float(used.get("non_taxpayer_mle") or 0.0) > 0 and \
                        not _ntmle_reclassifiable(signings, season):
                    reason = reason or "The full mid-level was already used beyond the taxpayer amount."
            if route == "bi_annual" and payroll.get("bi_annual_used_last_year"):
                reason = reason or "The bi-annual can't be used two seasons in a row."
        reserved = float(held.get(route) or 0.0)
        if route in {"non_taxpayer_mle", "taxpayer_mle"}:
            reserved = float(held.get("non_taxpayer_mle") or 0.0) + float(held.get("taxpayer_mle") or 0.0)
        balance = max(0.0, amount - spent - reserved)
        out[route] = {"amount": amount, "used": spent, "reserved": reserved, "balance": balance,
                      "available": not reason and balance > 0, "reason": reason or ("Budget used up." if balance <= 0 else ""),
                      "max_years": EXCEPTION_MAX_YEARS[route], "hard_cap": ROUTE_HARD_CAP.get(route),
                      "label": ROUTE_LABELS[route], "short": ROUTE_SHORT[route]}
    return out


def cap_table(active: dict[str, Any], save: dict[str, Any], team_id: str, *, years: int = 5,
              today: str | None = None) -> list[dict[str, Any]]:
    """The cap table year by year from this cap year (holds only count in the first)."""
    first = cap_year(save)
    rows = []
    for k in range(max(1, years)):
        season = _label(season_start(first) + k)
        p = team_payroll(active, save, team_id, season, today=today)
        rows.append(summary_millions(p))
    return rows


def summary_millions(p: dict[str, Any]) -> dict[str, Any]:
    """The payroll in millions for screens."""
    def m(v: float | None) -> float | None:
        return None if v is None else round(float(v) / 1_000_000, 2)
    lines = p["lines"]
    return {
        "season": p["season"],
        "signed_millions": m(p["signed_cap_charge"]),
        "signed_salary_millions": m(p["signed_salary"]),
        "dead_millions": m(p["dead_money"]),
        "holds_millions": m(p["hold_total"]),
        "holds": [{"player_id": h["player_id"], "name": h.get("name"), "kind": h["kind"],
                   "amount_millions": m(h["amount"]), "previous_salary_millions": m(h.get("previous_salary") or 0.0)}
                  for h in p["holds"]],
        "empty_roster_spots": p["empty_roster_spots"],
        "roster_charge_millions": m(p["roster_charge"]),
        "roster_count": p["roster_count"],
        "cap_payroll_millions": m(p["cap_payroll"]),
        "tax_payroll_millions": m(p["tax_payroll"]),
        "apron_payroll_millions": m(p["apron_payroll"]),
        "cap_room_millions": m(p["cap_room"]),
        "room_under_tax_millions": m(p["room_under_tax"]),
        "room_under_first_apron_millions": m(p["room_under_first_apron"]),
        "room_under_second_apron_millions": m(p["room_under_second_apron"]),
        "floor_shortfall_millions": m(p["floor_shortfall"]),
        "salary_cap_millions": m(lines["salary_cap"]),
        "tax_line_millions": m(lines["tax_line"]),
        "first_apron_millions": m(lines["first_apron"]),
        "second_apron_millions": m(lines["second_apron"]),
        "salary_floor_millions": m(lines["salary_floor"]),
        "hard_cap": ({**p["hard_cap"], "amount_millions": m(p["hard_cap"]["amount"]),
                      "words": HARD_CAP_WORDS.get(p["hard_cap"]["level"])} if p.get("hard_cap") else None),
        "used_room": p["used_room"],
        "exceptions": {k: {"label": v["label"], "short": v["short"], "amount_millions": m(v["amount"]),
                           "used_millions": m(v["used"]), "reserved_millions": m(v["reserved"]),
                           "balance_millions": m(v["balance"]), "available": v["available"], "reason": v["reason"],
                           "max_years": v["max_years"], "hard_cap": v["hard_cap"]}
                       for k, v in p["exceptions"].items()},
    }


# ---------------------------------------------------------------------------------------------------------------------
# Quoting a signing

def player_previous_salary(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], season: str) -> float:
    contract = _index(active)["contracts"].get(player.get("id")) or {}
    seasons = contract.get("seasons") or []
    return _previous_salary(seasons, _label(season_start(season) - 1))


def _route_years_limit(route: str, bird: dict[str, Any] | None) -> int:
    if route == "bird":
        return bird_max_years((bird or {}).get("level"))
    if route == "cap_room":
        return bird_max_years((bird or {}).get("level")) if bird else 4
    return EXCEPTION_MAX_YEARS.get(route, 4)


def _route_raise(route: str, bird: dict[str, Any] | None) -> float:
    if route == "bird" or (route == "cap_room" and bird):
        return bird_raise((bird or {}).get("level"))
    return OUTSIDE_RAISE


def quote(active: dict[str, Any], save: dict[str, Any], team_id: str, player: dict[str, Any], salary: float,
          years: int, *, season: str | None = None, route: str | None = None, raise_rate: float | None = None,
          bird: dict[str, Any] | None | str = "auto", include_reservations: bool = True, today: str | None = None,
          payroll: dict[str, Any] | None = None, team_abbrev: str | None = None) -> dict[str, Any]:
    """Is this signing legal for this team, how would it be paid for, and what would it lock in?

    ``salary`` is the first-year salary (dollars). ``route`` forces one way to pay (else the first legal one in
    ``ROUTES`` order, the way real teams choose: Bird rights, room, the minimum, then the exceptions). ``bird``: the
    team's Bird rights for him (``"auto"`` looks them up). ``raise_rate``: annual raise as a share of year one (None:
    the largest legal raise). The result's ``payment`` is what ``commit`` records."""
    season = str(season or cap_year(save))
    today = _today(save, today)
    years = max(1, int(years))
    pid = str(player.get("id") or "")
    if bird == "auto":
        bird = incumbent_bird(active, save, player, team_id)
    if payroll is None:
        payroll = team_payroll(active, save, team_id, season, today=today, include_reservations=include_reservations,
                               exclude_player_id=pid or None)
    lines = payroll["lines"]
    service = years_of_service(player, season)
    previous = float((bird or {}).get("previous_salary") or 0.0) or player_previous_salary(active, save, player, season)
    maximum = true_max_salary(season, service, previous)
    minimum = float(minimum_salary(season, service))
    salary = float(salary)
    is_minimum = salary <= minimum + 100_000 and years <= EXCEPTION_MAX_YEARS["minimum"]
    held = payroll.get("reserved") or {}
    ceiling = payroll.get("hard_cap")
    own_hold = next((h for h in payroll["holds"] if h["player_id"] == pid), None)
    # His own outstanding qualifying offer leaves apron salary when his new contract replaces it.
    apron_now = (payroll["apron_payroll"] + float(held.get("apron") or 0.0)
                 - float((own_hold or {}).get("qualifying_offer") or 0.0))
    team_label = team_abbrev or str(team_id).replace("team_", "").upper()
    results: list[dict[str, Any]] = []

    def cap_after(charge: float) -> float:
        # His contract replaces his own hold; a new player fills one empty roster spot.
        cap = payroll["cap_payroll"] + charge + float(held.get("cap_room") or 0.0)
        if own_hold:
            cap -= float(own_hold["amount"])
        elif payroll["empty_roster_spots"] > 0:
            cap -= float(minimum_salary(season, 0))
        return cap

    # AI-TRADES-SENSE: an AI team never signs its way into a hard cap it can't fill a roster under. The season review
    # had Minnesota use the mid-level and the bi-annual, hard-capping itself at the first apron, and open the next
    # season with 11 players because even a minimum contract no longer fit. Under a hard cap (one it has or the one
    # this way of paying would trigger) an AI team keeps room for minimum contracts up to AI_HARD_CAP_ROSTER_FILL
    # players after this signing. The user's team keeps the plain rule.
    from .save import human_controlled_team_ids
    fill_reserve = 0.0
    if team_id not in human_controlled_team_ids(save):
        fill_reserve = (max(0, AI_HARD_CAP_ROSTER_FILL - int(payroll.get("roster_count") or 0) - 1)
                        * float(minimum_salary(season, 0)))

    def check_ceiling(charge: float, own_level: str | None = None) -> str:
        after = apron_now + charge
        if ceiling and after > float(ceiling["amount"]) + 1:
            return (f"{team_label} is hard-capped at {HARD_CAP_WORDS[ceiling['level']]} ({_m(ceiling['amount'])}) "
                    f"after {ceiling.get('trigger') or 'an earlier move'}; this would take it to {_m(after)}.")
        if own_level and after > float(lines[own_level]) + 1:
            return (f"Using it requires staying under {HARD_CAP_WORDS[own_level]} ({_m(lines[own_level])}); "
                    f"this would take {team_label} to {_m(after)}.")
        caps = ([float(ceiling["amount"])] if ceiling else []) + ([float(lines[own_level])] if own_level else [])
        limit = min(caps) if caps else None
        if fill_reserve and limit is not None and after + fill_reserve > limit + 1:
            return (f"{team_label} would be left without room under its hard cap ({_m(limit)}) to fill a "
                    f"{AI_HARD_CAP_ROSTER_FILL}-man roster with minimum contracts.")
        return ""

    def legal_schedule(r: str, first: float) -> tuple[list[int], list[int], float]:
        if r == "minimum":
            sal = minimum_schedule(season, service, years)
            charges = list(sal)
            charges[0] = minimum_cap_charge(season, service, years)
            return sal, charges, 0.0
        top = _route_raise(r, bird)
        rate = top if raise_rate is None else max(-top, min(top, float(raise_rate)))
        sal = raise_schedule(first, years, rate)
        return sal, list(sal), rate

    for r in ROUTES:
        reason = ""
        first = minimum if r == "minimum" else salary
        charge = float(minimum_cap_charge(season, service, years)) if r == "minimum" else first
        if r != "minimum" and salary > maximum + 1:
            reason = f"Above his maximum salary ({_m(maximum)})."
        elif r != "minimum" and salary < minimum - 1:
            reason = f"Below his minimum salary ({_m(minimum)})."
        elif years > _route_years_limit(r, bird):
            reason = f"At most {_route_years_limit(r, bird)} years with {ROUTE_LABELS[r]}."
        elif r == "bird":
            if not bird:
                reason = "You don't hold his Bird rights."
            elif salary > float(bird.get("limit") or 0.0) + 1:
                reason = f"Above his {ROUTE_LABELS['bird_' + bird['level']]} limit ({_m(bird['limit'])})."
            elif bird.get("level") == "early" and years < 2:
                reason = "Early Bird rights need a contract of at least two years."
            else:
                reason = check_ceiling(charge)
        elif r == "cap_room":
            room = lines["salary_cap"] - (cap_after(0.0))
            if any(float(payroll["used"].get(x) or 0.0) > 0 for x in ("non_taxpayer_mle", "taxpayer_mle", "bi_annual")):
                reason = "Already used an over-the-cap exception this season, so it can't use room."
            elif cap_after(charge) > lines["salary_cap"] + 1:
                reason = f"Not enough cap room ({_m(max(0.0, room))} after holds and offers)."
            else:
                reason = check_ceiling(charge)
        elif r == "minimum":
            if not is_minimum:
                reason = f"Not a minimum contract (his minimum is {_m(minimum)}, up to two years)."
            else:
                reason = check_ceiling(charge)
        else:
            status = payroll["exceptions"][r]
            if not status["available"] and status["reason"] and status["reason"] != "Budget used up.":
                reason = status["reason"]
            elif salary > status["balance"] + 1:
                reason = f"{ROUTE_SHORT[r]} has {_m(status['balance'])} left."
            else:
                level = ROUTE_HARD_CAP.get(r)
                if r == "taxpayer_mle":
                    # The taxpayer mid-level is for teams that would end above the first apron (smaller teams use
                    # the full one); it hard-caps at the second apron.
                    reason = check_ceiling(charge, "second_apron")
                else:
                    reason = check_ceiling(charge, level)
        sal, charges, rate = legal_schedule(r, first)
        results.append({"route": r, "ok": not reason, "reason": reason, "label": ROUTE_LABELS[r],
                        "short": ROUTE_SHORT[r], "salary": first, "cap_charge": charges[0],
                        "schedule": sal, "cap_charges": charges, "raise_rate": rate})

    by_route = {row["route"]: row for row in results}
    chosen = None
    if route:
        chosen = by_route.get("bird" if str(route).startswith("bird") else route)
        if chosen and not chosen["ok"]:
            chosen = None
    else:
        chosen = next((row for row in results if row["ok"]), None)
    out: dict[str, Any] = {
        "ok": chosen is not None,
        "team_id": team_id,
        "player_id": pid,
        "season": season,
        "years": years,
        "salary": salary,
        "max_salary": maximum,
        "min_salary": minimum,
        "bird": bird or None,
        "routes": results,
        "payroll": summary_millions(payroll),
        "hard_cap_now": ceiling,
    }
    if chosen is None:
        if route:
            reason = (by_route.get("bird" if str(route).startswith("bird") else route) or {}).get("reason") or "Unknown way to pay."
            out["message"] = f"Can't pay him with {ROUTE_LABELS.get(route, route)}: {reason}"
        else:
            out["message"] = no_route_message(results, team_label)
        return out
    r = chosen["route"]
    level = (bird or {}).get("level") if r == "bird" else None
    trigger = ROUTE_HARD_CAP.get(r)
    charge = float(chosen["cap_charge"])
    over_cap_after = cap_after(charge) > lines["salary_cap"]
    seasons = [_label(season_start(season) + k) for k in range(years)]
    payment = {
        "route": r,
        "bird_level": level,
        "label": ROUTE_LABELS["bird_" + level] if level else chosen["label"],
        "season": season,
        "years": years,
        "salary": chosen["salary"],
        "amount": charge,
        "raise_rate": chosen["raise_rate"],
        "schedule": [{"season": s, "salary": sal, "cap_charge": ch}
                     for s, sal, ch in zip(seasons, chosen["schedule"], chosen["cap_charges"])],
        "hard_cap": trigger,
        "trade_eligible_date": trade_eligible_date(today, season, route=r, bird_level=level,
                                                   previous_salary=previous, first_salary=chosen["salary"],
                                                   over_cap_after=over_cap_after),
    }
    out.update(payment=payment, route=r, label=payment["label"], message="",
               locks=lock_text(r, trigger, lines, ceiling, season, team_label),
               cap_room_after=lines["salary_cap"] - cap_after(charge),
               apron_after=apron_now + charge)
    return out


def no_route_message(results: list[dict[str, Any]], team_label: str) -> str:
    over_max = next((row["reason"] for row in results if "maximum salary" in row["reason"]), "")
    if over_max:
        return over_max
    reasons = [f"{row['short']}: {row['reason']}" for row in results
               if row["reason"] and row["route"] != "minimum" and not row["reason"].startswith("You don't hold")]
    return f"{team_label} has no legal way to pay this. " + " ".join(reasons)


def lock_text(route: str, trigger: str | None, lines: dict[str, float], ceiling: dict[str, Any] | None, season: str,
              team_label: str) -> str | None:
    if route == "bird":
        if ceiling:
            return (f"Bird rights don't add a hard cap, but {team_label} must stay under "
                    f"{HARD_CAP_WORDS[ceiling['level']]} ({_m(ceiling['amount'])}) for the rest of {season}.")
        return "Bird rights let you go over the cap and both aprons; no hard cap."
    if route == "cap_room":
        return ("Using cap room gives up the full and taxpayer mid-level and the bi-annual for "
                f"{season}; the smaller room mid-level ({_m(exception_amount('room_mle', season))}) becomes available.")
    if route == "room_mle":
        return f"Uses the room mid-level; no hard cap."
    if route == "minimum":
        return "Minimum contracts never add a hard cap." + (
            f" {team_label} must still stay under {HARD_CAP_WORDS[ceiling['level']]}." if ceiling else "")
    if trigger:
        words = HARD_CAP_WORDS[trigger]
        if ceiling and float(ceiling["amount"]) <= float(lines[trigger]):
            return f"{team_label} is already hard-capped at {HARD_CAP_WORDS[ceiling['level']]} for {season}."
        return (f"Using {ROUTE_LABELS[route]} hard-caps {team_label} at {words} ({_m(lines[trigger])}) for the rest "
                f"of {season}.")
    return None


def incumbent_bird(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], team_id: str
                   ) -> dict[str, Any] | None:
    """The team's Bird rights for its own free agent (it still holds his rights and hasn't renounced them)."""
    if not team_id or not player.get("id"):
        return None
    meta_season = str((save.get("meta") or {}).get("season") or BASE_SEASON)
    if not any(r.get("player_id") == player["id"] and r.get("team_id") == team_id and r.get("season") == meta_season
               for r in save.get("re_signing_rights", []) or []):
        return None
    season = cap_year(save)
    if player["id"] in renounced_ids(save, team_id, season):
        return None
    contract = _index(active)["contracts"].get(player["id"])
    rights = _cached_bird_rights(save, player, team_id, meta_season, contract)
    # FA-REAL slice 2: after a declined rookie-scale option his old team may pay him at most the option's salary in
    # the first year (CBA Art. XI §1(e)).
    from .offseason_decisions import declined_rookie_option
    declined = declined_rookie_option(save, player["id"])
    if declined and rights:
        rights = {**rights, "limit": min(float(rights.get("limit") or 0.0), float(declined.get("salary") or 0.0)),
                  "declined_rookie_option": True}
    return rights


# ---------------------------------------------------------------------------------------------------------------------
# Committing

def commit(save: dict[str, Any], team_id: str, player_id: str, payment: dict[str, Any], when: str | None = None) -> None:
    """Record a signing paid as ``payment`` (from ``quote``): exception money used, cap room used, the hard cap it
    triggers. Call once, when the contract is written."""
    if not payment or not team_id:
        return
    season = str(payment.get("season") or cap_year(save))
    row = team_year(save, team_id, season, create=True)
    route = str(payment.get("route") or "")
    amount = float(payment.get("amount") or 0.0)
    signing = {"player_id": player_id, "route": route, "amount": round(amount), "years": int(payment.get("years") or 1),
               "date": _today(save, when)}
    if any(s.get("player_id") == player_id and s.get("route") == route and s.get("date") == signing["date"]
           for s in row["signings"]):
        return
    row["signings"].append(signing)
    if route in EXCEPTION_ROUTES:
        row["used"][route] = float(row["used"].get(route) or 0.0) + amount
    if route in {"cap_room", "room_mle"}:
        row["used_room"] = True
    trigger = payment.get("hard_cap")
    if trigger:
        trigger_hard_cap(save, team_id, season, trigger, f"using {ROUTE_LABELS.get(route, route)}", when)


def contract_seasons(payment: dict[str, Any], *, status: str = "save_state_offer",
                     guaranteed: bool | None = True) -> list[dict[str, Any]]:
    """Contract season rows written to the save, year by year (no more flat salaries)."""
    rows = []
    for item in payment.get("schedule") or []:
        salary = int(round(float(item["salary"])))
        row = {"season": item["season"], "salary": salary, "option_type": None, "guarantee_status": status}
        if item.get("cap_charge") is not None and int(round(float(item["cap_charge"]))) != salary:
            row["cap_charge"] = int(round(float(item["cap_charge"])))
        if guaranteed is not None:
            row["guaranteed_salary"] = salary if guaranteed else 0
            row["protection_basis"] = "negotiated"
        rows.append(row)
    # CONTRACT-TERMS: a player or team option on the final season (contract_terms.apply_option).
    from .contract_terms import apply_option
    return apply_option(rows, payment.get("option") or "none")


def contract_terms(payment: dict[str, Any]) -> dict[str, Any]:
    """Fields a contract override carries so the save, the screens and the trade code agree."""
    return {
        "payment_route": payment.get("route"),
        "payment_label": payment.get("label"),
        "bird_level": payment.get("bird_level"),
        "salary_schedule": [int(round(float(s["salary"]))) for s in payment.get("schedule") or []],
        "cap_charges": [int(round(float(s.get("cap_charge") if s.get("cap_charge") is not None else s["salary"])))
                        for s in payment.get("schedule") or []],
        "trade_eligible_date": payment.get("trade_eligible_date"),
        # CONTRACT-TERMS: the contract's shape (salary path and final-season option).
        "salary_path": payment.get("salary_path") or _path_of(payment),
        "option": payment.get("option") or "none",
    }


def _path_of(payment: dict[str, Any]) -> str:
    rate = float(payment.get("raise_rate") or 0.0)
    return "rising" if rate > 0 else "declining" if rate < 0 else "flat"


# ---------------------------------------------------------------------------------------------------------------------
# Renouncing a hold

def renounce(save: dict[str, Any], team_id: str, player_id: str, *, season: str | None = None,
             when: str | None = None, by: str = "user") -> bool:
    """Give up a free agent's rights: his cap hold disappears, and so do the team's Bird rights for him (it can still
    sign him with room or an exception, like any other team)."""
    season = str(season or cap_year(save))
    expiring = _label(season_start(season) - 1)
    rights = save.get("re_signing_rights", []) or []
    had = any(r.get("team_id") == team_id and r.get("player_id") == player_id and str(r.get("season")) == expiring
              for r in rights)
    if not had:
        return False
    save["re_signing_rights"] = [r for r in rights if not (r.get("team_id") == team_id and r.get("player_id") == player_id)]
    row = team_year(save, team_id, season, create=True)
    if player_id not in row["renounced"]:
        row["renounced"].append(player_id)
    row.setdefault("renounce_log", []).append({"player_id": player_id, "date": _today(save, when), "by": by})
    return True


def renounce_preview(active: dict[str, Any], save: dict[str, Any], team_id: str, player_id: str,
                     *, season: str | None = None) -> dict[str, Any]:
    """Cap room before and after renouncing one hold (millions), for the Renounce button."""
    season = str(season or cap_year(save))
    before = team_payroll(active, save, team_id, season)
    hold = next((h for h in before["holds"] if h["player_id"] == player_id), None)
    if hold is None:
        return {"ok": False, "reason": "No cap hold for this player."}
    spot = 0.0
    if before["empty_roster_spots"] > 0 or (offseason_window(season, before["date"])[1]
                                           and before["roster_count"] + len(before["holds"]) - 1 < MINIMUM_ROSTER_FOR_CAP):
        spot = float(minimum_salary(season, 0))
    after_room = before["cap_room"] + float(hold["amount"]) - spot
    return {"ok": True, "player_id": player_id, "name": hold.get("name"), "kind": hold["kind"],
            "hold_millions": round(hold["amount"] / 1e6, 2),
            "cap_room_before_millions": round(before["cap_room"] / 1e6, 2),
            "cap_room_after_millions": round(after_room / 1e6, 2),
            "empty_spot_charge_millions": round(spot / 1e6, 2),
            "loses": f"You lose his {ROUTE_LABELS['bird_' + hold['bird']['level']]}: you could only re-sign him with "
                     "cap room or an exception, like any other team."}


def ai_renounce_for_room(active: dict[str, Any], save: dict[str, Any], team_id: str, keep_ids: set[str],
                         *, season: str | None = None, threshold: float | None = None) -> list[str]:
    """A front office gives up holds on players it is not trying to keep when that opens real cap room: at least the
    full mid-level's worth (a team that stays over the cap keeps its mid-level and bi-annual instead, and keeps the
    holds so it can still re-sign them). Returns the renounced player ids."""
    season = str(season or cap_year(save))
    p = team_payroll(active, save, team_id, season)
    if p["used"] or p["used_room"]:
        return []
    drop = [h for h in p["holds"] if h["player_id"] not in keep_ids and h["kind"].endswith("_bird")]
    if not drop:
        return []
    kept_count = p["roster_count"] + len(p["holds"]) - len(drop)
    spots = max(0, MINIMUM_ROSTER_FOR_CAP - kept_count) if offseason_window(season, p["date"])[1] else 0
    room_after = p["lines"]["salary_cap"] - (p["tax_payroll"] + p["hold_total"] - sum(h["amount"] for h in drop)
                                            + spots * float(minimum_salary(season, 0)))
    needed = float(threshold if threshold is not None else exception_amount("non_taxpayer_mle", season))
    if room_after < needed:
        return []
    done = []
    for h in drop:
        if renounce(save, team_id, h["player_id"], season=season, by="ai"):
            done.append(h["player_id"])
    return done


# ---------------------------------------------------------------------------------------------------------------------
# Taking on an existing contract (waiver claims)

def absorb_route(active: dict[str, Any], save: dict[str, Any], team_id: str, salary: float, added: float, years: int,
                 *, minimum: bool = False, season: str | None = None, exceptions: bool = True) -> dict[str, Any]:
    """How a team can take on an existing contract by waiver claim (CBA Art. VII §6 and Exhibit A): cap room, the
    minimum exception for a minimum contract, or (since 2024-25) the full or room mid-level or the bi-annual when the
    remaining years fit the exception, never past a hard cap it has triggered. ``salary`` is the contract's salary
    this season, ``added`` the payroll change after any player cut to make room."""
    season = str(season or cap_year(save))
    p = team_payroll(active, save, team_id, season)
    lines = p["lines"]
    ceiling = p.get("hard_cap")
    after = p["apron_payroll"] + float(added)
    if ceiling and after > float(ceiling["amount"]) + 1:
        return {"ok": False, "route": None,
                "reason": f"Hard-capped at {HARD_CAP_WORDS[ceiling['level']]} ({_m(ceiling['amount'])}) this season."}

    def done(route: str) -> dict[str, Any]:
        payment = {"route": route, "season": season, "years": int(years), "salary": float(salary),
                   "amount": float(salary), "hard_cap": ROUTE_HARD_CAP.get(route), "label": ROUTE_LABELS[route]}
        return {"ok": True, "route": route, "reason": "", "payment": payment}

    if minimum:
        return done("minimum")
    if p["cap_payroll"] + float(added) <= lines["salary_cap"] + 1 and not p["used"]:
        return done("cap_room")
    for route in ("room_mle", "non_taxpayer_mle", "bi_annual") if exceptions else ():
        status = p["exceptions"][route]
        level = ROUTE_HARD_CAP.get(route)
        if (status["available"] and float(salary) <= status["balance"] + 1 and int(years) <= status["max_years"]
                and (not level or after <= float(lines[level]) + 1)):
            return done(route)
    return {"ok": False, "route": None, "reason": "Not enough cap room or exception money to take on the contract."}
