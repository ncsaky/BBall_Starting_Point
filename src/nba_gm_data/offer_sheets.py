"""Offer sheets and matching (FA-REAL slice 3): restricted free agency the real way.

Plain words:
- A **restricted free agent** is a young player whose team sent him a qualifying offer (slice 2). Other teams may
  now sign him to an **offer sheet**: a signed contract offer his team can **match** (keep him on exactly those terms)
  or **pass** on (he joins the new team on all of them).
- The bidding team must be able to pay the sheet (cap room or an exception). Its money stays **reserved** until the
  sheet is settled, so it can't promise the same room twice. One sheet per player at a time.
- His team has until the end of the **next day** to decide. It needs Bird rights, room or an exception, and it can't
  go past a hard cap it has already triggered. A matched player can't be traded for a year.

The real rules (``docs/agents/tasks/fa-realism-research.md``, 2023 CBA Article XI §5) and how the game applies them:
- **Terms**: 2 to 4 seasons (at least 3 if his team also made the maximum qualifying offer), raises of up to 5% of the
  first year. The game's contracts have no bonuses, and offer sheets carry no option years and are fully guaranteed,
  so the CBA's limits on bonuses (10% signing bonus) and options (the minimum length excludes option years) are met
  by construction.
- **The Arenas rule** (players with one or two years in the league): the first year can't be above the full mid-level
  amount ($15.044M in 2026-27), year two at most 5% more. If both years are at that limit, year three may jump to what
  his maximum salary would have reached by then (his max plus two 5% raises), year four at most 4.5% more. The bidder
  counts the average every year (it needs cap room for the average); his own team counts the real salaries. No sheet in
  2023-26 used the jump (OFFSEASON-DECISIONS-EVIDENCE), so AI bidders never do; the user may.
- **How the bidder pays**: cap room, the room mid-level, the full or taxpayer mid-level, the bi-annual, or a minimum
  contract for a minimum-salary sheet (all six real sheets in 2023-26 used an exception: Dallas and Memphis the full
  mid-level, Utah the room mid-level, Oklahoma City the taxpayer mid-level, Atlanta and New York the minimum). Never
  Bird rights (the bidder has none).
- **The matching deadline**: after the moratorium a sheet delivered before noon is due 11:59 p.m. the next day, one at
  or after noon two days later; sheets delivered in the moratorium (July 1-6) are due July 7. The game has no clock
  and, by the user's decision, no moratorium (deals are official the moment both sides agree), so every sheet counts
  as delivered in the morning: **his team decides by the end of the next day**. Sheets can be signed from July 1 (the
  new league year), like the real ones.
- **Matching**: the first-year salary must fit his team's Bird rights (full or Early Bird: up to his maximum; Non-Bird:
  its 120% limit), cap room or an exception, never past a hard cap the team triggered. If matched, his team signs him on
  the sheet's salaries year by year and he can't be traded for a year (the game has no player-consent step, so the
  year's block covers "not without his consent" and "never to the bidder"). If not matched (or time runs out), the
  bidder signs him on all terms and its reserved payment is used.

The AI (every decision states its reason, no dice: deterministic hashes per save, season, team and player, so no other
random stream moves):
- **Incumbents** follow the evidence's rule: match unless a hard cap prevents it (5 of 6 right in 2023-26). The miss
  was Golden State passing on Quinten Post, an expensive reserve; so a team passes on a reserve (under
  ``RULES['incumbent']['regular_minutes']`` minutes) when matching costs more tax than its owner pays for him.
- **Bidders** aim at good young restricted players whose teams may not match (a hard cap, the tax, a crowded position,
  a rebuild), with a legal way to pay, a role for him and an owner who accepts the cost. Urgent offices bid more (the
  TRADE-MARKET urgency trait). Calibrated to the real 0-3 sheets a summer (6 in four summers, 4 matched).
- **The player** signs a sheet when its first-year salary reaches what he will take now (his market price plus his
  belief in himself, fading over the summer: ``offseason_decisions.rfa_reservation``) and his qualifying offer.
"""
from __future__ import annotations

from datetime import date, timedelta
import math
from typing import Any

from .offseason_calendar import offseason_dates, season_label

SHEET_ROUTES = ("cap_room", "room_mle", "non_taxpayer_mle", "taxpayer_mle", "bi_annual", "minimum")
MIN_YEARS, MAX_YEARS, MAX_QO_MIN_YEARS = 2, 4, 3
SHEET_RAISE = 0.05
ARENAS_SERVICE = (1, 2)
ARENAS_YEAR_FOUR_RAISE = 0.045
LATE_PASS_MONTH_DAY = (7, 15)
TRACE: list | None = None          # calibration only: set to a list to record each pass's best bidder per player     # the late sheet pass (last day of the free-agency phase), before late summer

RULES: dict[str, dict[str, float]] = {
    # Incumbents (2023-26: 6 sheets, 4 matched; "match unless a hard cap prevents it" 5 of 6 right).
    "incumbent": {
        "regular_minutes": 18.0,          # a regular is always matched when it's legal (Denver and Spencer Jones)
        "cheap_minimums": 2.0,            # a sheet at or below 2x his minimum is always matched (Dallas and Cissé)
    },
    # Bidders. Sized so a summer has 0-3 sheets and about two in three are matched (the replay measures it).
    "bidder": {
        "max_age": 26.0,                  # all six real sheets went to players 25 or younger
        "premium": 1.05,                  # a sheet a little above his market price ...
        "urgent_premium": 0.10,           # ... more from an urgent office (raises the cost of matching)
        "max_over_market": 1.30,          # nobody bids more than 30% over his market price
        "value_scale": 10_000_000.0,      # his market price at which the player counts fully
        "min_value_share": 0.25,
        "older_factor": 0.6,              # 25-26 years old
        "role_minutes": 15.0,             # the bidder's projected minutes for him: a role, or half the appeal
        "weak_cannot": 1.0,               # his team can't legally match
        "weak_pass": 0.75,                # his team would likely pass (an expensive reserve over the tax)
        "weak_match": 0.30,               # his team would likely match (bidders still try: 4 of 6 real sheets)
        "weak_rebuild": 0.10,             # extra when his team is rebuilding or crowded at his position
        "urgency": 0.4,                   # +/- share of appeal at full urgency
        "pass_rate": 0.16,                # chance per pass at full appeal (5 passes a summer: July 1-4 and July 15)
    },
}


def _m(value: float) -> str:
    return f"${float(value) / 1e6:.1f}M"


def _today(save: dict[str, Any]) -> str:
    return str((save.get("state") or {}).get("current_date") or "")


def store(save: dict[str, Any]) -> dict[str, Any]:
    from .offseason_decisions import store as decisions
    return decisions(save).setdefault("offer_sheets", {})


def all_sheets(save: dict[str, Any], season: str | None = None) -> list[dict[str, Any]]:
    rows = list(((save.get("offseason_decisions") or {}).get("offer_sheets") or {}).values())
    return [r for r in rows if season is None or r.get("season") == season]


def pending_sheets(save: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted((r for r in all_sheets(save) if r.get("status") == "pending"), key=lambda r: (r["signed_date"], r["id"]))


def pending_sheet(save: dict[str, Any], player_id: str) -> dict[str, Any] | None:
    return next((r for r in all_sheets(save) if r.get("status") == "pending" and r.get("player_id") == player_id), None)


def match_deadline(signed: str) -> str:
    """The end of the next day (see the module notes)."""
    return (date.fromisoformat(str(signed)[:10]) + timedelta(days=1)).isoformat()


def sheets_open(save: dict[str, Any]) -> bool:
    """Offer sheets can be signed from July 1 (the new league year) through the end of the season's offer-sheet window
    (the game uses the October 1 qualifying-offer deadline; the real final date is March 1)."""
    from .cap_ledger import cap_year
    today = _today(save)
    start = int(cap_year(save)[:4])
    dates = offseason_dates(start)
    return dates["league_year"] <= today < dates["qualifying_offers_expire"]


def _users(save: dict[str, Any]) -> set[str]:
    from .save import human_controlled_team_ids
    return set(human_controlled_team_ids(save))


def _abbrev(team_id: str | None) -> str:
    from .save import team_id_to_abbrev
    return team_id_to_abbrev(team_id)


def _hash_unit(*parts: Any) -> float:
    from .offseason_decisions import _hash_unit as unit
    return unit(*parts)


# ----------------------------------------------------------------------------------------------------------------------
# Terms

def credited_service(save: dict[str, Any], player: dict[str, Any], season: str) -> int:
    """Years in the league as his qualifying offer counted them (the Arenas band uses this)."""
    from .offseason_decisions import qo_record
    record = qo_record(save, season, str(player.get("id") or "")) or {}
    if record.get("years_of_service") is not None:
        return int(record["years_of_service"])
    from .cap_ledger import years_of_service
    return int(years_of_service(player, season))


def sheet_terms(save: dict[str, Any], player: dict[str, Any], first_salary: float, years: int, *,
                season: str | None = None, raise_rate: float = SHEET_RAISE, backload: bool = False) -> dict[str, Any]:
    """The legal salary schedule of an offer sheet, or why it isn't legal. Salaries in dollars.

    Returns ok, reason, salaries (what he is paid), bidder_charges (what the bidder counts: the average under the
    Arenas jump), incumbent_charges (his own team counts the real salaries), arenas (in the band), backloaded."""
    from .cap_ledger import cap_year, exception_amount, minimum_salary, true_max_salary
    from .offseason_decisions import qo_record
    season = str(season or cap_year(save))
    years = int(years)
    first = float(first_salary)
    record = qo_record(save, season, str(player.get("id") or "")) or {}
    service = credited_service(save, player, season)
    arenas = service in ARENAS_SERVICE
    least = MAX_QO_MIN_YEARS if record.get("maximum") else MIN_YEARS
    out = {"ok": False, "season": season, "years": years, "arenas": arenas, "backloaded": False,
           "service": service, "min_years": least}
    if not least <= years <= MAX_YEARS:
        return {**out, "reason": (f"An offer sheet runs {least} to {MAX_YEARS} seasons"
                                  + (" (his team also made the maximum qualifying offer)." if least == 3 else "."))}
    rate = max(0.0, min(SHEET_RAISE, float(raise_rate)))
    minimum = float(minimum_salary(season, service))
    maximum = float(true_max_salary(season, service, float(record.get("previous_salary") or 0.0)))
    if first < minimum - 1:
        return {**out, "reason": f"Below his minimum salary ({_m(minimum)})."}
    if first > maximum + 1:
        return {**out, "reason": f"Above his maximum salary ({_m(maximum)})."}
    mle = float(exception_amount("non_taxpayer_mle", season))
    if arenas and first > mle + 1:
        return {**out, "reason": (f"He has {service} year{'s' if service != 1 else ''} in the league: the first year of "
                                  f"an offer sheet can't be above the full mid-level ({_m(mle)}) (the Arenas rule).")}
    salaries = [int(round(first * (1.0 + rate * k))) for k in range(years)]
    if backload:
        if not arenas:
            return {**out, "reason": "Only a player with one or two years in the league can get a back-loaded sheet."}
        if years < 3:
            return {**out, "reason": "A back-loaded sheet needs at least three seasons."}
        if abs(first - mle) > 1:
            return {**out, "reason": f"A back-loaded sheet starts at the full mid-level ({_m(mle)})."}
        top = float(true_max_salary(season, service)) * (1.0 + 2 * SHEET_RAISE)
        salaries = [int(round(mle)), int(round(mle * (1.0 + SHEET_RAISE))), int(round(top))]
        if years == 4:
            salaries.append(int(round(top * (1.0 + ARENAS_YEAR_FOUR_RAISE))))
        average = int(round(sum(salaries) / len(salaries)))
        bidder = [average] * len(salaries)
        return {**out, "ok": True, "reason": "", "salaries": salaries, "bidder_charges": bidder,
                "incumbent_charges": list(salaries), "backloaded": True, "raise_rate": None}
    return {**out, "ok": True, "reason": "", "salaries": salaries, "bidder_charges": list(salaries),
            "incumbent_charges": list(salaries), "raise_rate": rate}


def _with_schedule(quote: dict[str, Any], salaries: list[int], charges: list[int]) -> dict[str, Any]:
    """Put the sheet's own year-by-year salaries and cap charges on a quote's payment."""
    payment = dict(quote.get("payment") or {})
    seasons = [row["season"] for row in payment.get("schedule") or []]
    if len(seasons) < len(salaries):
        from .cap_ledger import _label, season_start
        seasons = [_label(season_start(payment.get("season") or quote["season"]) + k) for k in range(len(salaries))]
    payment["schedule"] = [{"season": s, "salary": int(sal), "cap_charge": int(ch)}
                           for s, sal, ch in zip(seasons, salaries, charges)]
    payment["salary"] = int(salaries[0])
    payment["amount"] = float(charges[0])
    return {**quote, "payment": payment}


def bidder_quote(active: dict[str, Any], save: dict[str, Any], team_id: str, player: dict[str, Any],
                 terms: dict[str, Any], *, route: str | None = None, payroll: dict[str, Any] | None = None,
                 team_abbrev: str | None = None) -> dict[str, Any]:
    """How the bidding team pays a sheet (cap room or an exception, never Bird rights), or why it can't. Other live
    offers and sheets hold their money (cap_ledger reservations)."""
    from . import cap_ledger
    season = terms["season"]
    years = terms["years"]
    charge = float(terms["bidder_charges"][0])
    routes = [route] if route else list(SHEET_ROUTES)
    if terms.get("backloaded"):
        routes = [r for r in routes if r == "cap_room"]
        if not routes:
            return {"ok": False, "message": "A back-loaded sheet needs cap room for the average salary.", "routes": []}
    if route and route not in SHEET_ROUTES:
        return {"ok": False, "message": "An offer sheet is paid with cap room or an exception, never Bird rights.",
                "routes": []}
    last = None
    for r in routes:
        quote = cap_ledger.quote(active, save, team_id, player, charge, years, season=season, route=r, raise_rate=0.0,
                                 bird=None, include_reservations=True, payroll=payroll, team_abbrev=team_abbrev)
        last = quote
        if quote.get("ok"):
            return _with_schedule(quote, terms["salaries"], terms["bidder_charges"])
    if route or last is None:
        return last or {"ok": False, "message": "No legal way to pay this sheet.", "routes": []}
    sheet_routes = [row for row in last.get("routes") or [] if row["route"] in SHEET_ROUTES]
    reasons = " ".join(f"{row['short']}: {row['reason']}" for row in sheet_routes if row.get("reason"))
    return {**last, "ok": False, "routes": sheet_routes,
            "message": f"{team_abbrev or _abbrev(team_id)} has no cap room or exception to pay this sheet. {reasons}".strip()}


def incumbent_quote(active: dict[str, Any], save: dict[str, Any], sheet: dict[str, Any],
                    player: dict[str, Any] | None = None) -> dict[str, Any]:
    """Can his team match? Bird rights (full or Early Bird up to his maximum; Non-Bird its own limit), cap room or an
    exception, never past a hard cap it triggered. The quote's payment carries the sheet's real salaries."""
    from . import cap_ledger
    team_id = sheet["rights_team_id"]
    player = player or next((p for p in active.get("players", []) if p.get("id") == sheet["player_id"]),
                            {"id": sheet["player_id"]})
    bird = cap_ledger.incumbent_bird(active, save, player, team_id)
    if bird and bird.get("level") in {"full", "early"} and not bird.get("declined_rookie_option"):
        service = cap_ledger.years_of_service(player, sheet["season"])
        bird = {**bird, "limit": cap_ledger.true_max_salary(sheet["season"], service, float(bird.get("previous_salary") or 0))}
    salaries = [int(s) for s in sheet["salaries"]]
    quote = cap_ledger.quote(active, save, team_id, player, float(salaries[0]), len(salaries), season=sheet["season"],
                             raise_rate=0.0, bird=bird, include_reservations=False, team_abbrev=_abbrev(team_id))
    if quote.get("ok") and quote.get("route") == "minimum" and abs(float(salaries[0]) - float(quote["salary"])) > 100_000:
        quote = {**quote, "ok": False}
    if not quote.get("ok"):
        return quote
    return _with_schedule(quote, salaries, list(sheet.get("incumbent_charges") or salaries))


# ----------------------------------------------------------------------------------------------------------------------
# The incumbent's choice

def incumbent_choice(active: dict[str, Any], save: dict[str, Any], sheet: dict[str, Any],
                     player: dict[str, Any] | None = None) -> dict[str, Any]:
    """Match or pass, with the reason (the evidence's rule; see RULES['incumbent']). The same rule is the assistant
    GM's advice to the user."""
    from .cap_ledger import minimum_salary
    from .payroll_plan import owner_tax_budget, projected_end_payroll, tax_cost
    from .save import display_minutes_projection
    rules = RULES["incumbent"]
    player = player or next((p for p in active.get("players", []) if p.get("id") == sheet["player_id"]),
                            {"id": sheet["player_id"]})
    team_id = sheet["rights_team_id"]
    team = _abbrev(team_id)
    quote = incumbent_quote(active, save, sheet, player)
    first = float(sheet["salaries"][0])
    if not quote.get("ok"):
        return {"match": False, "legal": False, "quote": quote, "kind": "cannot",
                "reason": f"{team} can't legally match: {quote.get('message') or 'no way to pay the first year'}"}
    minutes = float(display_minutes_projection(player))
    season = sheet["season"]
    service = credited_service(save, player, season)
    before = projected_end_payroll(active, save, team_id, season)
    cost = tax_cost(save, team_id, season, before, before + first)
    paid = f"paid with {quote['payment'].get('label') or 'Bird rights'}"
    if minutes >= rules["regular_minutes"]:
        extra = f"; it costs about {_m(cost['total'])} in tax" if cost["total"] > 0 else ""
        return {"match": True, "legal": True, "quote": quote, "kind": "regular", "tax_cost": cost["total"],
                "reason": f"{team} matches: he is a regular ({minutes:.0f} minutes) and teams keep their young regulars "
                          f"({paid}{extra})."}
    if first <= rules["cheap_minimums"] * float(minimum_salary(season, service)):
        return {"match": True, "legal": True, "quote": quote, "kind": "cheap", "tax_cost": cost["total"],
                "reason": f"{team} matches: {_m(first)} a year is close to the minimum ({paid})."}
    budget = owner_tax_budget(active, save, team_id, minutes, "re_signing")
    if cost["total"] <= max(0.0, budget):
        words = "no tax" if cost["total"] <= 0 else f"about {_m(cost['total'])} in tax, within what its owner pays"
        return {"match": True, "legal": True, "quote": quote, "kind": "affordable", "tax_cost": cost["total"],
                "reason": f"{team} matches: {paid}, {words}."}
    return {"match": False, "legal": True, "quote": quote, "kind": "expensive_reserve", "tax_cost": cost["total"],
            "reason": f"{team} passes: an expensive reserve ({minutes:.0f} minutes) at {_m(first)} a year would cost "
                      f"about {_m(cost['total'])} in luxury tax (Golden State passed on Quinten Post for the same reason)."}


# ----------------------------------------------------------------------------------------------------------------------
# Signing a sheet

def can_receive_sheet(save: dict[str, Any], player_id: str, team_id: str) -> str | None:
    """Why ``team_id`` can't sign this player to an offer sheet now, else None."""
    from .offseason_decisions import restricted_rights_team
    holder = restricted_rights_team(save, player_id)
    if not holder:
        return "He is not a restricted free agent."
    if holder == team_id:
        return "He is your own restricted free agent: negotiate with him directly."
    if pending_sheet(save, player_id):
        return "He has already signed an offer sheet; his team is deciding whether to match."
    if not sheets_open(save):
        return "Offer sheets can be signed from July 1 (the new league year) until October 1."
    return None


def sign_sheet(save: dict[str, Any], player: dict[str, Any], bidder_id: str, terms: dict[str, Any],
               quote: dict[str, Any], *, by: str, reason: str) -> dict[str, Any]:
    """Record a signed sheet: the bidder's payment is reserved (cap_ledger.reservations) until it is settled."""
    from .offseason_decisions import qo_record, restricted_rights_team
    from .save import add_news
    today = _today(save)
    season = terms["season"]
    holder = restricted_rights_team(save, player["id"])
    payment = quote["payment"]
    record = {
        "id": f"offer_sheet:{season}:{player['id']}:{bidder_id}:{today}",
        "season": season, "player_id": player["id"], "name": player.get("name"),
        "bidder_team_id": bidder_id, "rights_team_id": holder, "signed_date": today,
        "match_deadline": match_deadline(today), "status": "pending", "by": by, "bid_reason": reason,
        "years": terms["years"], "salaries": list(terms["salaries"]),
        "bidder_charges": list(terms["bidder_charges"]), "incumbent_charges": list(terms["incumbent_charges"]),
        "backloaded": bool(terms.get("backloaded")), "arenas": bool(terms.get("arenas")),
        "raise_rate": terms.get("raise_rate"),
        "payment": {k: payment.get(k) for k in ("route", "label", "amount", "salary", "years", "season", "hard_cap",
                                                 "schedule", "raise_rate", "trade_eligible_date")},
        "qualifying_offer": int((qo_record(save, season, player["id"]) or {}).get("amount") or 0),
    }
    store(save)[record["id"]] = record
    total = sum(record["salaries"])
    add_news(save, "offer_sheet", f"{player.get('name')} signs an offer sheet with {_abbrev(bidder_id)}: "
             f"{len(record['salaries'])} years, {_m(total)}. {_abbrev(holder)} has until "
             f"{record['match_deadline']} to match.", date_value=today)
    return record


def player_takes_sheet(save: dict[str, Any], player: dict[str, Any], first_salary: float, stage: float,
                       active: dict[str, Any] | None = None) -> tuple[bool, str]:
    """The player's choice: sign the sheet when its first-year salary reaches what he will take now and his
    qualifying offer (personality-free: the price against his market, which is no more than the most any team could
    offer him: ``leverage_price``)."""
    from .cap_ledger import cap_year
    from .offseason_decisions import qo_record, rfa_market_price, rfa_reservation
    market = rfa_market_price(save, player["id"], active=active)
    qo = float((qo_record(save, cap_year(save), player["id"]) or {}).get("amount") or 0.0)
    want = max(qo, rfa_reservation(save, player, market, stage) if market else qo)
    if float(first_salary) + 1 >= want:
        return True, f"{_m(first_salary)} a year reaches what he wants now ({_m(want)})."
    return False, f"He wants at least {_m(want)} a year now (his market price is {_m(market)})."


def summer_stage(save: dict[str, Any]) -> float:
    """How far the restricted summer has gone for his asking price (offseason_decisions.RFA_STAGES)."""
    from .offseason_decisions import RFA_STAGES
    state = save.get("free_agency_state") or {}
    if str((save.get("state") or {}).get("phase") or "") == "free_agency" and state.get("status") != "completed":
        return RFA_STAGES["june"] + RFA_STAGES["market_day"] * max(1, int(state.get("day") or 1))
    today = _today(save)
    if today[5:] < "07-16":
        return 0.5
    return RFA_STAGES["late_summer"]


# ----------------------------------------------------------------------------------------------------------------------
# What the outside market can pay him (his leverage)

_CAPACITY: dict[tuple, dict[str, float]] = {}


def outside_capacity(active: dict[str, Any], save: dict[str, Any]) -> dict[str, float]:
    """The largest first-year salary each team could put in an offer sheet today (dollars): its cap room left after
    reservations, or its largest available exception (the minimum always). Cached per day and ledger state."""
    from . import cap_ledger
    season = cap_ledger.cap_year(save)
    ledger = ((save.get("cap_ledger") or {}).get("seasons") or {}).get(season) or {}
    key = (_today(save), (save.get("meta") or {}).get("seed"), sum(len(r.get("signings") or []) for r in ledger.values()),
           len(pending_sheets(save)), len(save.get("free_agent_offers") or []))
    if key in _CAPACITY:
        return _CAPACITY[key]
    out = {}
    for team in active.get("teams", []):
        payroll = cap_ledger.team_payroll(active, save, team["id"], season, include_reservations=True)
        room = float(payroll["cap_room"]) - float((payroll.get("reserved") or {}).get("cap_room") or 0.0)
        balances = [float(v["balance"]) for v in payroll["exceptions"].values() if v["available"]]
        out[team["id"]] = max([room, 0.0] + balances)
    _CAPACITY.clear()
    _CAPACITY[key] = out
    return out


def leverage_price(active: dict[str, Any], save: dict[str, Any], player_id: str, market: float) -> float:
    """His price as a restricted free agent: his market price, but no more than the most any other team could pay
    him in an offer sheet today (his only outside leverage), and never below his qualifying offer. Real restricted
    players whose price no team can reach settle for less with their own team (Kuminga and Giddey 2025, Duren 2026)."""
    from .offseason_decisions import qo_record, restricted_rights_team
    from .cap_ledger import cap_year
    holder = restricted_rights_team(save, player_id)
    capacity = outside_capacity(active, save)
    best = max([v for team, v in capacity.items() if team != holder] or [0.0])
    qo = float((qo_record(save, cap_year(save), player_id) or {}).get("amount") or 0.0)
    return max(qo, min(float(market), best)) if market else qo


# ----------------------------------------------------------------------------------------------------------------------
# Settling a sheet

def _write_contract(canonical: dict[str, Any], save: dict[str, Any], sheet: dict[str, Any], team_id: str,
                    payment: dict[str, Any], kind: str, departed: dict[str, Any] | None = None) -> dict[str, Any]:
    from .contract_ai import apply_contract_to_save_state
    from .cap_ledger import contract_terms
    from .utils import stable_id
    today = _today(save)
    salaries = [int(s) for s in sheet["salaries"]]
    negotiation_id = stable_id("contract_negotiation", "offer_sheet", kind, sheet["id"])
    offer = {
        "id": stable_id("contract_offer", negotiation_id), "negotiation_id": negotiation_id, "team_id": team_id,
        "player_id": sheet["player_id"], "offer_type": "free_agent_signing", "guaranteed": True, "round": 1,
        "years": len(salaries), "start_season": sheet["season"], "annual_salary": float(salaries[0]),
        "total_salary": float(sum(salaries)), "role_promise": "market_role", "status": "accepted",
        "notes": "Offer sheet " + ("matched by his team." if kind == "matched" else "signed with the new team."),
        "payment": payment,
    }
    offer.update(contract_terms(payment))
    decision = {"id": stable_id("signing_decision", negotiation_id), "negotiation_id": negotiation_id,
                "player_id": sheet["player_id"], "team_id": team_id, "accepted": True, "decision": "accept",
                "accepted_offer": offer, "reasons": [f"offer_sheet_{kind}"], "source_ids": []}
    save.setdefault("pending_contract_negotiations", []).append({
        "negotiation": {"id": negotiation_id, "negotiation_type": "free_agent_signing", "player_id": sheet["player_id"],
                        "player_name": sheet.get("name"), "team_id": team_id, "date": today, "rounds": 1,
                        "offers": [offer], "final_decision_id": decision["id"], "status": "agreement",
                        "notes": "Offer sheet.", **({"departure": departed} if departed else {})},
        "decision": decision, "accepted": True})
    return apply_contract_to_save_state(save, negotiation_id, date=today)


def settle(canonical: dict[str, Any], save: dict[str, Any], sheet: dict[str, Any], match: bool, *, by: str,
           reason: str, active: dict[str, Any] | None = None) -> dict[str, Any]:
    """Match (his team signs him on the sheet's terms; no trade for a year) or pass (the bidder signs him on all of
    them). Frees the bidder's reservation either way."""
    from .save import add_news, canonical_with_save
    from .offseason_decisions import qo_record
    if sheet.get("status") != "pending":
        return {"ok": False, "reason": "This offer sheet is already settled."}
    active = active if active is not None else canonical_with_save(canonical, save)
    player = next((p for p in active.get("players", []) if p.get("id") == sheet["player_id"]), {"id": sheet["player_id"]})
    today = _today(save)
    holder, bidder = sheet["rights_team_id"], sheet["bidder_team_id"]
    if match:
        quote = incumbent_quote(active, save, sheet, player)
        if not quote.get("ok"):
            return {"ok": False, "reason": f"You can't legally match: {quote.get('message')}"}
        sheet.update(status="matched_pending_write")    # its reservation is released before the contract is written
        result = _write_contract(canonical, save, sheet, holder, quote["payment"], "matched")
        if result.get("status") != "applied":
            sheet.update(status="pending")
            return {"ok": False, "reason": result.get("notes") or "The contract could not be written."}
        unlock = (date.fromisoformat(today) + timedelta(days=365)).isoformat()
        override = (save.get("contract_overrides") or {}).get(sheet["player_id"]) or {}
        override["trade_eligible_date"] = max(str(override.get("trade_eligible_date") or ""), unlock)
        override["offer_sheet"] = {"outcome": "matched", "bidder_team_id": bidder, "date": today,
                                   "trade_rule": f"Matched offer sheet: he can't be traded until {unlock}, and not to "
                                                 f"{_abbrev(bidder)} in that time."}
        sheet.update(status="matched", decided_date=today, decided_by=by, decision_reason=reason,
                     route=quote["payment"].get("route"), route_label=quote["payment"].get("label"),
                     trade_eligible_date=unlock)
        headline = (f"{_abbrev(holder)} matches {_abbrev(bidder)}'s offer sheet and keeps {sheet.get('name')} "
                    f"({len(sheet['salaries'])} years, {_m(sum(sheet['salaries']))}).")
    else:
        terms = {"season": sheet["season"], "years": sheet["years"], "salaries": sheet["salaries"],
                 "bidder_charges": sheet["bidder_charges"], "backloaded": sheet.get("backloaded")}
        sheet.update(status="passed_pending_write")
        route = (sheet.get("payment") or {}).get("route")
        quote = bidder_quote(active, save, bidder, player, terms, route=route)
        payment = quote["payment"] if quote.get("ok") else dict(sheet["payment"])   # the reserved route
        # COACHES-FREE-AGENTS: the signing news says why he changed teams.
        departed = {"from_team_id": holder, "from_abbrev": _abbrev(holder), "key": "offer_sheet", "clear": True,
                    "reason": "after they declined to match his offer sheet", "icon": False, "seasons_with_team": 0}
        result = _write_contract(canonical, save, sheet, bidder, payment, "passed", departed)
        if result.get("status") != "applied":
            sheet.update(status="pending")
            return {"ok": False, "reason": result.get("notes") or "The contract could not be written."}
        save["re_signing_rights"] = [r for r in save.get("re_signing_rights", []) or []
                                     if not (r.get("player_id") == sheet["player_id"] and r.get("team_id") == holder)]
        override = (save.get("contract_overrides") or {}).get(sheet["player_id"]) or {}
        override["offer_sheet"] = {"outcome": "passed", "rights_team_id": holder, "date": today}
        sheet.update(status="passed", decided_date=today, decided_by=by, decision_reason=reason,
                     route=payment.get("route"), route_label=payment.get("label"))
        headline = (f"{_abbrev(holder)} declines to match: {sheet.get('name')} joins {_abbrev(bidder)} "
                    f"({len(sheet['salaries'])} years, {_m(sum(sheet['salaries']))}).")
    record = qo_record(save, sheet["season"], sheet["player_id"])
    if record:
        record.update(status="signed", date=today, reason=headline)
    save.setdefault("transaction_logs", []).append({
        "id": f"transaction_log_{sheet['id']}_{sheet['status']}", "date": today,
        "transaction_type": f"offer_sheet_{sheet['status']}", "status": "applied_to_save_ledger",
        "teams": [holder, bidder], "assets": {"player_id": sheet["player_id"], "name": sheet.get("name"),
                                              "salaries": sheet["salaries"]}, "notes": reason})
    add_news(save, "offer_sheet", headline, date_value=today)
    return {"ok": True, "sheet": dict(sheet), "headline": headline}


def resolve_due(canonical: dict[str, Any], save: dict[str, Any], *, force_ai: bool = False,
                expire_user: bool = False) -> list[dict[str, Any]]:
    """Settle pending sheets: AI teams decide on their deadline day (or at once with ``force_ai``, for background
    passes); a user's sheet is settled only by the user, or passes when time runs out (``expire_user``: the real
    rule, used when the calendar moves past his deadline)."""
    from .save import canonical_with_save
    today = _today(save)
    users = _users(save)
    done = []
    active = None
    for sheet in pending_sheets(save):
        mine = sheet["rights_team_id"] in users
        due = today >= sheet["match_deadline"]
        if mine:
            if not (expire_user and today >= sheet["match_deadline"]):
                continue
            result = settle(canonical, save, sheet, False, by="clock",
                            reason="The deadline passed without a decision: he joins the new team.", active=active)
        else:
            if not (due or force_ai):
                continue
            active = active or canonical_with_save(canonical, save)
            choice = incumbent_choice(active, save, sheet)
            result = settle(canonical, save, sheet, bool(choice["match"]), by="team", reason=choice["reason"],
                            active=active)
            if not result.get("ok") and choice["match"]:
                result = settle(canonical, save, sheet, False, by="team",
                                reason=f"{choice['reason']} The match failed: {result.get('reason')}", active=active)
        active = None
        if result.get("ok"):
            done.append(result["sheet"])
    return done


def user_decisions_due(save: dict[str, Any], *, through: str | None = None) -> list[dict[str, Any]]:
    """The user's sheets still waiting for Match or Pass whose deadline is at or before ``through`` (default today)."""
    when = through or _today(save)
    users = _users(save)
    return [s for s in pending_sheets(save) if s["rights_team_id"] in users and s["match_deadline"] <= when]


def user_pending(save: dict[str, Any]) -> list[dict[str, Any]]:
    users = _users(save)
    return [s for s in pending_sheets(save) if s["rights_team_id"] in users]


def user_decide(canonical: dict[str, Any], save: dict[str, Any], sheet_id: str, match: bool) -> dict[str, Any]:
    sheet = store(save).get(sheet_id) or next((s for s in all_sheets(save) if s.get("player_id") == sheet_id
                                               and s.get("status") == "pending"), None)
    if not sheet or sheet.get("status") != "pending":
        return {"ok": False, "reason": "There is no offer sheet waiting for your decision."}
    if sheet["rights_team_id"] not in _users(save):
        return {"ok": False, "reason": "This offer sheet is not yours to match."}
    reason = ("You matched: he stays on the sheet's terms." if match
              else "You passed: he joins the new team on the sheet's terms.")
    return settle(canonical, save, sheet, match, by="user", reason=reason)


# ----------------------------------------------------------------------------------------------------------------------
# AI bidders

def _phase(active: dict[str, Any], save: dict[str, Any], team_id: str) -> str:
    from .payroll_plan import team_phase
    return team_phase(active, save, team_id)


def ai_sheet_pass(canonical: dict[str, Any], save: dict[str, Any], *, label: str,
                  active: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """One chance for AI teams to sign unsigned restricted free agents to offer sheets (each first-wave market day
    from July 1 and the July 15 pass). Returns the sheets signed."""
    from . import cap_ledger
    from .front_office import urgency_level
    from .offseason_decisions import qo_record, restricted_player_ids, rfa_market_price
    from .payroll_plan import office_row, payroll_check
    from .play import free_agency_offer_context_score
    from .save import canonical_with_save, display_minutes_projection
    if not sheets_open(save):
        return []
    rules = RULES["bidder"]
    held = {pid: team for pid, team in restricted_player_ids(save).items() if not pending_sheet(save, pid)}
    if not held:
        return []
    active = active if active is not None else canonical_with_save(canonical, save)
    users = _users(save)
    season = cap_ledger.cap_year(save)
    seed = (save.get("meta") or {}).get("seed") or 1
    stage = summer_stage(save)
    players = {p["id"]: p for p in active.get("players", [])}
    busy = {s["bidder_team_id"] for s in pending_sheets(save)}
    teams = [t for t in active.get("teams", []) if t.get("id") not in users]
    payrolls: dict[str, dict[str, Any]] = {}
    capacities = outside_capacity(active, save)
    signed = []
    for pid, holder in sorted(held.items()):
        player = players.get(pid)
        market = rfa_market_price(save, pid, active=active)
        if not player or market <= 0:
            continue
        age = float(player.get("display_age", player.get("age")) or 27.0)
        if age > rules["max_age"]:
            continue
        record = qo_record(save, season, pid) or {}
        qo = float(record.get("amount") or 0.0)
        ok, _ = player_takes_sheet(save, player, market * rules["max_over_market"], stage, active)
        if not ok:
            continue          # he wants more than anyone would pay: he waits
        value = max(rules["min_value_share"], min(1.0, market / rules["value_scale"]))
        if age >= 25:
            value *= rules["older_factor"]
        years = MAX_QO_MIN_YEARS if record.get("maximum") else 3
        # What his team would do with a sheet at about this price (bidders know the league's habits).
        guess_terms = sheet_terms(save, player, max(qo, market * rules["premium"]), years, season=season)
        if not guess_terms["ok"]:
            guess_terms = sheet_terms(save, player, min(max(qo, market), float(cap_ledger.exception_amount(
                "non_taxpayer_mle", season))), years, season=season)
        if not guess_terms["ok"]:
            continue
        guess = incumbent_choice(active, save, {**guess_terms, "player_id": pid, "rights_team_id": holder,
                                                "season": season}, player)
        weak = {"cannot": rules["weak_cannot"], "expensive_reserve": rules["weak_pass"]}.get(guess["kind"],
                                                                                            rules["weak_match"])
        if guess["kind"] not in {"cannot", "expensive_reserve"} and _phase(active, save, holder) == "rebuilding":
            weak += rules["weak_rebuild"]
        best = None
        for team in teams:
            team_id = team["id"]
            if team_id == holder or team_id in busy:
                continue
            row = office_row(active, team_id)
            urgency = urgency_level(row) if row else 0.0
            # A little over his price (more from an urgent office), but no more than the team can fund: a "full
            # mid-level sheet" when that is all it has. He must take it (his price now, his qualifying offer).
            capacity = float(capacities.get(team_id) or 0.0)
            price = max(qo, market * (rules["premium"] + rules["urgent_premium"] * max(0.0, urgency)))
            price = min(price, capacity)
            price = math.floor(price / 100_000) * 100_000
            if price < qo:
                continue
            taken, _ = player_takes_sheet(save, player, price, stage, active)
            if not taken:
                stretch = math.floor(min(capacity, market * rules["max_over_market"]) / 100_000) * 100_000
                if stretch <= price or not player_takes_sheet(save, player, stretch, stage, active)[0]:
                    continue
                price = stretch
            terms = sheet_terms(save, player, price, years, season=season)
            if not terms["ok"] and terms.get("arenas"):
                terms = sheet_terms(save, player, float(cap_ledger.exception_amount("non_taxpayer_mle", season)),
                                    years, season=season)
            if not terms["ok"]:
                continue
            if team_id not in payrolls:
                payrolls[team_id] = cap_ledger.team_payroll(active, save, team_id, season, include_reservations=True)
            payroll = payrolls[team_id]
            quote = bidder_quote(active, save, team_id, player, terms, payroll=payroll, team_abbrev=team.get("abbrev"))
            if not quote.get("ok") and years > MIN_YEARS and not record.get("maximum"):
                short = sheet_terms(save, player, terms["salaries"][0], MIN_YEARS, season=season)
                if short["ok"]:
                    quote2 = bidder_quote(active, save, team_id, player, short, payroll=payroll,
                                          team_abbrev=team.get("abbrev"))
                    if quote2.get("ok"):
                        terms, quote = short, quote2
            if not quote.get("ok"):
                continue
            context = free_agency_offer_context_score(active, save, player, team, terms["years"], "ai")
            role = 1.0 if float(context["projected_minutes"]) >= rules["role_minutes"] else 0.5
            plan = payroll_check(active, save, team_id, season, add_salary=terms["bidder_charges"][0],
                                 minutes=display_minutes_projection(player), kind="free_agency", age=age)
            if not plan["ok"]:
                continue
            appeal = value * weak * role * (1.0 + rules["urgency"] * urgency)
            if best is None or appeal > best["appeal"]:
                best = {"appeal": appeal, "team": team, "terms": terms, "quote": quote, "urgency": urgency,
                        "minutes": float(context["projected_minutes"])}
        if TRACE is not None:
            TRACE.append({"label": label, "player": player.get("name"), "holder": _abbrev(holder), "market": market,
                          "guess": guess["kind"], "best": (best["team"].get("abbrev"), round(best["appeal"], 3))
                          if best else None})
        if best is None:
            continue
        draw = _hash_unit(seed, season, label, pid, best["team"]["id"], "offer_sheet")
        if draw >= best["appeal"] * rules["pass_rate"]:
            continue
        terms, team = best["terms"], best["team"]
        why = {"cannot": f"{_abbrev(holder)} can't fit a match under its hard cap",
               "expensive_reserve": f"{_abbrev(holder)} may not pay the tax to keep a reserve"}.get(
            guess["kind"], f"a young player it wants, even if {_abbrev(holder)} is likely to match")
        reason = (f"{team.get('abbrev')} bids: {why}; it sees about {best['minutes']:.0f} minutes for him and pays with "
                  f"{best['quote']['payment'].get('label')}"
                  + (" (an urgent front office)" if best["urgency"] >= 0.5 else "") + ".")
        sheet = sign_sheet(save, player, team["id"], terms, best["quote"], by="ai", reason=reason)
        signed.append(sheet)
        busy.add(team["id"])
        payrolls.pop(team["id"], None)
        capacities = outside_capacity(active, save)
    return signed


def late_pass(canonical: dict[str, Any], save: dict[str, Any], seed: int, root: Any = None) -> dict[str, Any]:
    """July 15 (the last day of the free-agency phase): one more sheet pass; AI teams decide on their sheets at once
    (the rest of the summer runs in the background). Returns the user's sheets still waiting."""
    from .save import advance_lifecycle_to
    from .cap_ledger import cap_year
    start = int(cap_year(save)[:4])
    when = date(start, *LATE_PASS_MONTH_DAY).isoformat()
    if _today(save) < when:
        advance_lifecycle_to(canonical, save, when, seed, root)
    state = save.setdefault("free_agency_state", {})
    if not state.get("late_sheet_pass_done"):
        state["late_sheet_pass_done"] = True
        ai_sheet_pass(canonical, save, label="late")
    resolve_due(canonical, save, force_ai=True)
    return {"user_pending": user_pending(save)}


# ----------------------------------------------------------------------------------------------------------------------
# Screens

def sheet_view(active: dict[str, Any], save: dict[str, Any], sheet: dict[str, Any], viewer_team_id: str | None = None
               ) -> dict[str, Any]:
    """A sheet for the screens (millions, plain words). For the team holding his rights while it is pending: what
    matching does to its cap year by year, the hard cap it would break, and the assistant GM's read."""
    from . import cap_ledger
    m = lambda v: round(float(v) / 1e6, 3)
    seasons = [row["season"] for row in (sheet.get("payment") or {}).get("schedule") or []]
    years = [{"season": s, "salary_millions": m(sal), "bidder_charge_millions": m(b), "your_charge_millions": m(i)}
             for s, sal, b, i in zip(seasons, sheet["salaries"], sheet["bidder_charges"], sheet["incumbent_charges"])]
    view = {
        "id": sheet["id"], "player_id": sheet["player_id"], "name": sheet.get("name"), "season": sheet["season"],
        "status": sheet["status"], "bidder_team_id": sheet["bidder_team_id"],
        "bidder_abbrev": _abbrev(sheet["bidder_team_id"]), "rights_team_id": sheet["rights_team_id"],
        "rights_abbrev": _abbrev(sheet["rights_team_id"]), "signed_date": sheet["signed_date"],
        "match_deadline": sheet["match_deadline"], "years": years, "total_millions": m(sum(sheet["salaries"])),
        "backloaded": bool(sheet.get("backloaded")), "paid_with": (sheet.get("payment") or {}).get("label"),
        "bid_reason": sheet.get("bid_reason"), "decision_reason": sheet.get("decision_reason"),
        "decided_by": sheet.get("decided_by"), "decided_date": sheet.get("decided_date"),
        "trade_eligible_date": sheet.get("trade_eligible_date"),
    }
    if sheet["status"] == "pending" and viewer_team_id and viewer_team_id == sheet["rights_team_id"]:
        choice = incumbent_choice(active, save, sheet)
        quote = choice["quote"]
        table = cap_ledger.cap_table(active, save, viewer_team_id, years=len(sheet["salaries"]))
        effect = []
        for k, row in enumerate(table):
            charge = float(sheet["incumbent_charges"][k]) / 1e6 if k < len(sheet["incumbent_charges"]) else 0.0
            effect.append({
                "season": row["season"], "payroll_millions": row["tax_payroll_millions"], "adds_millions": round(charge, 3),
                "after_millions": round(float(row["tax_payroll_millions"] or 0) + charge, 3),
                "cap_room_after_millions": (round(float(quote["cap_room_after"]) / 1e6, 2) if k == 0 and quote.get("ok")
                                            and quote.get("cap_room_after") is not None
                                            else round(float(row["cap_room_millions"] or 0) - charge, 2)),
                "tax_room_after_millions": round(float(row["room_under_tax_millions"] or 0) - charge, 2),
                "first_apron_room_after_millions": round(float(row["room_under_first_apron_millions"] or 0) - charge, 2),
                "hard_cap": row.get("hard_cap"),
            })
        view.update(
            can_match=bool(quote.get("ok")),
            match_route=(quote.get("payment") or {}).get("label") if quote.get("ok") else None,
            match_blocked=None if quote.get("ok") else quote.get("message"),
            hard_cap=(table[0].get("hard_cap") if table else None),
            cap_effect=effect, tax_cost_millions=round(float(choice.get("tax_cost") or 0.0) / 1e6, 2),
            advice={"match": bool(choice["match"]), "reason": choice["reason"]},
            if_matched=("He stays on these salaries year by year and can't be traded for a year "
                        f"(not to {_abbrev(sheet['bidder_team_id'])} at all in that time)."),
            if_passed=f"He joins {_abbrev(sheet['bidder_team_id'])} on these terms; you get nothing back.",
            days_left=max(0, (date.fromisoformat(sheet["match_deadline"]) - date.fromisoformat(_today(save))).days),
        )
    return view


def room_view(active: dict[str, Any], save: dict[str, Any], team_id: str) -> dict[str, Any]:
    """Offer sheets for the free-agency room: yours to decide, yours as the bidder, and the league's this summer."""
    from .cap_ledger import cap_year
    season = cap_year(save)
    rows = sorted(all_sheets(save, season), key=lambda s: (s["signed_date"], s["id"]))
    for_you = [sheet_view(active, save, s, team_id) for s in rows if s["status"] == "pending"
               and s["rights_team_id"] == team_id]
    return {
        "open": sheets_open(save),
        "for_you": for_you,
        "yours": [sheet_view(active, save, s) for s in rows if s["bidder_team_id"] == team_id],
        "league": [sheet_view(active, save, s) for s in rows],
        "decision_due": [v["id"] for v in for_you if v["match_deadline"] <= _today(save)],
        "rules": {"min_years": MIN_YEARS, "max_years": MAX_YEARS, "max_raise_pct": round(SHEET_RAISE * 100),
                  "routes": list(SHEET_ROUTES),
                  "deadline": "His team decides by the end of the next day."},
    }
