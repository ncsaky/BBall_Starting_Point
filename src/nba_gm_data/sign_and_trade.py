"""Sign-and-trades (FA-REAL slice 4).

A three-sided agreement: a team re-signs its own free agent and trades him at once to the team he wants to join.
The rules (2023 CBA Art. VII §§2(e), 5(b), 6(j)(5), 8(e), Art. XI §5(m); research
``docs/agents/tasks/fa-realism-research.md``):

- the player finished last season with the sending team (it still holds his rights: Bird or Non-Bird);
- before the regular season; three or four seasons (at least three before any option: the game's deals have none);
- the first season fully guaranteed; raises at most 5% of year one (the ordinary outside-team limit);
- the sending team pays with its rights to him (never the mid-level);
- the receiving team must have room for him: cap room after the trade, or salary going back under the matching rules;
  it is then **hard-capped at the first apron** for the rest of the season, and a team already over the first apron
  can't receive one;
- **base-year compensation:** when the sending team is over the cap and gives him a raise of more than 20% with full or
  Early Bird rights, the salary it sends out counts as the greater of his old salary and half his new one (the
  receiver counts the full new salary). Max Strus: $14.49M in, $7.24M out.

Salary matching for an over-the-cap team (2023 CBA, figures for 2023-24 scaled with the cap): sending out up to $7.5M,
it may take back 200% plus $250K; $7.5M-$29M, plus $7.5M; above $29M, 125% plus $250K. A team under the cap after the
trade needs no matching.

AI teams (``RULES``) use them for the reasons Codex found in 22 real sign-and-trades (2023-2026): a team over the cap
wants a rotation free agent it can't sign directly (no room or exception big enough), and his old team, which isn't
keeping him, gets something back (a second-round pick, or cash) instead of losing him for nothing.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .cap_rules import season_start
from .utils import stable_id

MIN_YEARS = 3
MAX_YEARS = 4
RAISE = 0.05
BYC_RAISE = 0.20

# Matching thresholds, 2023-24 dollars scaled to 2026-27 by the cap (164.961 / 136.021).
MATCH_SMALL_2026 = 9_096_000
MATCH_LARGE_2026 = 35_171_000
MATCH_PLUS_2026 = 303_000
MATCH_MIDDLE_PLUS_2026 = 9_096_000

RULES = {
    # A sign-and-trade candidate is a rotation player (the 22 real ones were starters and rotation players).
    "min_minutes": 18.0,
    "min_ask_millions": 6.0,
    # Receivers: his likely suitors (the market's own ranking), the first few.
    "suitors": 6,
    # How often a legal, wanted sign-and-trade is actually agreed on a given day. Real summers had 3-11 (2023: 3,
    # 2024: 11, 2025: 4, 2026: 4); set on the 2027 replay.
    "agree_rate": 0.35,
    # Filler: bench players (under this many projected minutes) the receiving team sends to match salary.
    "filler_max_minutes": 20.0,
}


def _hash(*parts: Any) -> float:
    digest = hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _m(value: float) -> str:
    return f"${float(value) / 1e6:.2f}M"


def _abbrev(team_id: str | None) -> str:
    return str(team_id or "").replace("team_", "").upper()


def _bird_words(bird: dict[str, Any] | None) -> str:
    from .cap_ledger import ROUTE_LABELS
    if not bird:
        return "rights"
    return ROUTE_LABELS.get(f"bird_{bird.get('level')}", "Bird rights")


def store(save: dict[str, Any]) -> list[dict[str, Any]]:
    return save.setdefault("sign_and_trades", [])


def matching_limit(outgoing: float, season: str) -> float:
    """The most salary an over-the-cap team below the first apron may take back for ``outgoing``."""
    from .cap_ledger import scaled
    small, large = scaled(MATCH_SMALL_2026, season), scaled(MATCH_LARGE_2026, season)
    plus, middle = scaled(MATCH_PLUS_2026, season), scaled(MATCH_MIDDLE_PLUS_2026, season)
    outgoing = float(outgoing)
    if outgoing <= 0:
        return 0.0
    if outgoing <= small:
        return outgoing * 2.0 + plus
    if outgoing <= large:
        return outgoing + middle
    return outgoing * 1.25 + plus


def window_open(save: dict[str, Any], when: str | None = None) -> bool:
    """From the day talks with other teams open (June 30) until opening night."""
    from .offseason_calendar import offseason_dates, opening_night
    when = str(when or (save.get("state") or {}).get("current_date") or "")
    phase = str((save.get("state") or {}).get("phase") or "")
    season = str((save.get("meta") or {}).get("season") or "2026-27")
    start = season_start(season)
    if phase in {"free_agency", "offseason", "training_camp"}:
        return when >= offseason_dates(start + 1, save)["market_opens"]
    if phase == "preseason":
        return when < opening_night(start, save).isoformat()
    return False


def _player_salary(active: dict[str, Any], save: dict[str, Any], player_id: str, season: str) -> float:
    from .cap_ledger import cap_charge, season_row, team_contracts  # noqa: F401
    override = (save.get("contract_overrides") or {}).get(player_id)
    rows = (override or {}).get("seasons") if override else None
    if not rows:
        contract = next((c for c in active.get("contracts", []) if c.get("player_id") == player_id), {})
        rows = contract.get("seasons") or []
    row = next((r for r in rows if r.get("season") == season and r.get("salary") is not None), None)
    return float(cap_charge(row)) if row else 0.0


def quote(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], sender: str, receiver: str,
          salary: float, years: int, *, outgoing_ids: list[str] | None = None, pick_ids: list[str] | None = None,
          when: str | None = None) -> dict[str, Any]:
    """Is this sign-and-trade legal? Every rule checked and explained in plain words, with the numbers.

    ``salary``: first-year salary (dollars); ``outgoing_ids``: players the receiving team sends back (salary
    matching); ``pick_ids``: picks it sends. Returns {ok, problems, notes, schedule, base_year, ...}."""
    from . import cap_ledger
    from .cap_ledger import cap_year, incumbent_bird, raise_schedule, team_payroll, true_max_salary, years_of_service
    when = str(when or (save.get("state") or {}).get("current_date") or "")
    season = cap_year(save)
    pid = str(player["id"])
    outgoing_ids = [str(x) for x in outgoing_ids or []]
    pick_ids = [str(x) for x in pick_ids or []]
    problems: list[str] = []
    notes: list[str] = []
    years = int(years or MIN_YEARS)
    salary = float(salary)
    if not window_open(save, when):
        problems.append("Sign-and-trades happen between the start of free agency (June 30) and opening night.")
    if sender == receiver:
        problems.append("The receiving team must be a different team.")
    if pid not in set(save.get("free_agent_player_ids") or []):
        problems.append(f"{player.get('name')} is not an unsigned free agent.")
    bird = incumbent_bird(active, save, player, sender)
    if not bird:
        problems.append(f"{_abbrev(sender)} doesn't hold his rights (he must have finished last season with them, "
                        "and they must not have renounced him).")
    if not MIN_YEARS <= years <= MAX_YEARS:
        problems.append(f"A sign-and-trade runs {MIN_YEARS} or {MAX_YEARS} seasons.")
    service = years_of_service(player, season)
    previous = float((bird or {}).get("previous_salary") or 0.0)
    maximum = true_max_salary(season, service, previous)
    if salary > maximum + 1:
        problems.append(f"{_m(salary)} is above his maximum salary ({_m(maximum)}).")
    if bird and salary > float(bird.get("limit") or 0.0) + 1:
        problems.append(f"{_abbrev(sender)}'s {_bird_words(bird)} let it pay him at most "
                        f"{_m(float(bird.get('limit') or 0.0))} in the first year.")
    minimum = cap_ledger.minimum_salary(season, service)
    if salary < minimum:
        problems.append(f"The salary is below his minimum ({_m(minimum)}).")
    schedule = raise_schedule(salary, years, RAISE)
    seasons = [cap_ledger._label(season_start(season) + k) for k in range(years)]
    # Sending team's books.
    sender_pay = team_payroll(active, save, sender, season, today=when)
    sender_over_cap = sender_pay["cap_payroll"] - float(next((h["amount"] for h in sender_pay["holds"]
                                                              if h["player_id"] == pid), 0.0)) + salary \
        > sender_pay["lines"]["salary_cap"]
    big_raise = bool(bird) and bird.get("level") in {"full", "early"} and previous > 0 and salary > previous * (1 + BYC_RAISE)
    outgoing_salary = salary
    base_year = None
    if big_raise and sender_over_cap:
        outgoing_salary = max(previous, salary / 2.0)
        base_year = {"previous": previous, "new": salary, "counts_out": outgoing_salary,
                     "words": f"Base-year compensation: his raise is over 20% and {_abbrev(sender)} is over the cap, so "
                              f"he counts {_m(outgoing_salary)} going out (the greater of his old salary and half the "
                              f"new one) and {_m(salary)} coming in."}
        notes.append(base_year["words"])
    # Receiving team's books.
    recv_pay = team_payroll(active, save, receiver, season, today=when)
    lines = recv_pay["lines"]
    back = sum(_player_salary(active, save, x, season) for x in outgoing_ids)
    recv_tax_after = recv_pay["tax_payroll"] - back + salary
    recv_apron_after = recv_pay["apron_payroll"] - back + salary
    if recv_pay["apron_payroll"] > lines["first_apron"]:
        problems.append(f"{_abbrev(receiver)} is over the first apron ({_m(lines['first_apron'])}); a team over it "
                        "can't receive a sign-and-trade.")
    if recv_apron_after > lines["first_apron"] + 1:
        problems.append(f"After the trade {_abbrev(receiver)} would be at {_m(recv_apron_after)}, over the first apron "
                        f"({_m(lines['first_apron'])}), where it would be hard-capped.")
    ceiling = recv_pay.get("hard_cap")
    if ceiling and recv_apron_after > float(ceiling["amount"]) + 1:
        problems.append(f"{_abbrev(receiver)} is hard-capped at {_m(ceiling['amount'])} already.")
    recv_cap_after = recv_pay["cap_payroll"] - back + salary
    via_room = recv_cap_after <= lines["salary_cap"] + 1
    match_limit = matching_limit(back, season)
    if via_room:
        notes.append(f"{_abbrev(receiver)} takes him into cap room (cap payroll after {_m(recv_cap_after)}, under the "
                     f"{_m(lines['salary_cap'])} cap).")
    elif salary > match_limit + 1:
        problems.append(f"{_abbrev(receiver)} is over the cap, so it must send back salary: {_m(back)} going out "
                        f"lets it take back at most {_m(match_limit)}, not {_m(salary)}.")
    else:
        notes.append(f"Salary matching: {_abbrev(receiver)} sends {_m(back)} and may take back up to {_m(match_limit)}.")
    # The sending team's side of matching (it takes back the receiver's players).
    if back > 0:
        sender_cap_after = sender_pay["cap_payroll"] - float(next((h["amount"] for h in sender_pay["holds"]
                                                                  if h["player_id"] == pid), 0.0)) + back
        if sender_cap_after > sender_pay["lines"]["salary_cap"] and back > matching_limit(outgoing_salary, season) + 1:
            problems.append(f"{_abbrev(sender)} would take back {_m(back)}, more than the {_m(matching_limit(outgoing_salary, season))} "
                            f"its {_m(outgoing_salary)} outgoing salary allows.")
        sender_ceiling = sender_pay.get("hard_cap")
        if sender_ceiling and sender_pay["apron_payroll"] + back > float(sender_ceiling["amount"]) + 1:
            problems.append(f"{_abbrev(sender)} is hard-capped and can't take back that salary.")
    # Players and picks are the receiver's to send.
    roster = save.get("roster_overrides") or {}
    players = {p["id"]: p for p in active.get("players", [])}
    from . import two_way
    for x in outgoing_ids:
        team = roster.get(x, (players.get(x) or {}).get("team_id")) if x in roster else (players.get(x) or {}).get("team_id")
        if team != receiver or two_way.is_two_way(save, x):
            problems.append(f"{(players.get(x) or {}).get('name', x)} is not on {_abbrev(receiver)}'s standard roster.")
        elif cap_ledger.newly_signed_trade_block(save, x, when):
            problems.append(f"{(players.get(x) or {}).get('name', x)} signed recently and can't be traded yet.")
    picks = {p["id"]: p for p in active.get("draft_picks", [])}
    overrides = save.get("draft_pick_overrides") or {}
    for x in pick_ids:
        pick = picks.get(x)
        owner = overrides.get(x, (pick or {}).get("current_owner_team_id"))
        if not pick or owner != receiver or pick.get("_obligation_locked"):
            problems.append(f"Pick {x} is not {_abbrev(receiver)}'s to trade.")
    # Rosters after: the sender takes back players, the receiver adds one minus what it sends.
    sender_room = two_way.standard_room(active, save, sender, when)
    if len(outgoing_ids) > sender_room["open"]:
        problems.append(f"{_abbrev(sender)} has no roster room for the players coming back.")
    recv_room = two_way.standard_room(active, save, receiver, when)
    if recv_room["open"] + len(outgoing_ids) < 1:
        problems.append(f"{_abbrev(receiver)} has no roster room for him.")
    notes.append(f"{_abbrev(receiver)} becomes hard-capped at the first apron ({_m(lines['first_apron'])}) for the rest "
                 f"of {season}.")
    return {
        "ok": not problems, "problems": problems, "notes": notes, "season": season, "player_id": pid,
        "player_name": player.get("name"), "sender": sender, "receiver": receiver, "years": years,
        "salary": salary, "schedule": [{"season": s, "salary": a} for s, a in zip(seasons, schedule)],
        "bird": bird, "base_year": base_year, "outgoing_salary": outgoing_salary, "incoming_salary": salary,
        "back_salary": back, "matching_limit": match_limit, "via_room": via_room,
        "receiver_apron_after": recv_apron_after, "receiver_tax_after": recv_tax_after,
        "first_apron": lines["first_apron"], "outgoing_ids": outgoing_ids, "pick_ids": pick_ids,
        "maximum": maximum, "minimum": minimum,
    }


def execute(active: dict[str, Any], save: dict[str, Any], terms: dict[str, Any], *, when: str | None = None,
            by: str = "ai", reasons: dict[str, str] | None = None) -> dict[str, Any]:
    """Carry out a legal sign-and-trade (``terms`` from ``quote``): the sending team signs him with its rights (first
    year guaranteed, 5% raises), trades him to the receiving team at once, takes back any players and picks, and the
    receiver is hard-capped at the first apron."""
    from . import cap_ledger
    if not terms.get("ok"):
        raise ValueError("; ".join(terms.get("problems") or ["Not a legal sign-and-trade."]))
    when = str(when or (save.get("state") or {}).get("current_date") or "")
    pid, sender, receiver, season = terms["player_id"], terms["sender"], terms["receiver"], terms["season"]
    schedule = terms["schedule"]
    bird = terms.get("bird") or {}
    seasons = []
    for k, row in enumerate(schedule):
        seasons.append({"season": row["season"], "salary": int(round(row["salary"])), "option_type": None,
                        "guarantee_status": "sign_and_trade", "protection_basis": "negotiated",
                        "guaranteed_salary": int(round(row["salary"]))})
    trade_date = cap_ledger.trade_eligible_date(when, season)
    save.setdefault("contract_overrides", {})[pid] = {
        "team_id": receiver, "seasons": seasons, "status": "sign_and_trade", "original_contract_years": len(seasons),
        "signed_season": season, "signed_date": when, "payment_route": "bird",
        "payment_label": f"{_abbrev(sender)}'s {_bird_words(bird)} (sign-and-trade)",
        "bird_level": bird.get("level"), "salary_schedule": [s["salary"] for s in seasons],
        "cap_charges": [s["salary"] for s in seasons], "trade_eligible_date": trade_date,
        "sign_and_trade": {"from_team_id": sender, "to_team_id": receiver, "date": when,
                           "outgoing_salary": round(terms["outgoing_salary"]),
                           "base_year_compensation": bool(terms.get("base_year"))}}
    roster = save.setdefault("roster_overrides", {})
    roster[pid] = receiver
    for x in terms["outgoing_ids"]:
        roster[x] = sender
        override = (save.get("contract_overrides") or {}).get(x)
        if override:
            override["team_id"] = sender
    from .transactions import update_retraded_pick_obligation
    for x in terms["pick_ids"]:
        save.setdefault("draft_pick_overrides", {})[x] = sender
        update_retraded_pick_obligation(save, x, sender, when)
    save["free_agent_player_ids"] = sorted(set(save.get("free_agent_player_ids") or []) - {pid})
    save["re_signing_rights"] = [r for r in save.get("re_signing_rights", []) or [] if r.get("player_id") != pid]
    for bid in save.get("free_agent_offers", []) or []:
        if bid.get("player_id") == pid and bid.get("status") == "active":
            bid["status"] = "player_signed_elsewhere"
            cap_ledger.release(bid)
    if terms.get("via_room"):
        cap_ledger.commit(save, receiver, pid, {"route": "cap_room", "season": season, "years": len(seasons),
                                                 "amount": terms["salary"], "salary": terms["salary"]}, when)
    cap_ledger.trigger_hard_cap(save, receiver, season, "first_apron", "receiving a sign-and-trade", when)
    for team in (sender, receiver):
        save.setdefault("rotation_snapshots", {}).pop(team, None)
        save.setdefault("starting_lineups", {}).pop(team, None)
    names = {p["id"]: p.get("name") for p in active.get("players", [])}
    sent_back = [names.get(x, x) for x in terms["outgoing_ids"]]
    back_words = ", ".join(sent_back + ([f"{len(terms['pick_ids'])} pick{'s' if len(terms['pick_ids']) > 1 else ''}"]
                                        if terms["pick_ids"] else []) + (["cash"] if terms.get("cash") else []))
    headline = (f"Sign-and-trade: {_abbrev(sender)} re-signed {terms['player_name']} ({len(seasons)} years, "
                f"{_m(terms['salary'])} to start) and traded him to {_abbrev(receiver)}"
                f"{' for ' + back_words if back_words else ''}.")
    record = {"id": stable_id("sign_and_trade", season, pid, when), "date": when, "season": season, "player_id": pid,
              "name": terms["player_name"], "sender": sender, "receiver": receiver, "years": len(seasons),
              "salary": round(terms["salary"]), "outgoing_salary": round(terms["outgoing_salary"]),
              "base_year": bool(terms.get("base_year")), "via_room": bool(terms.get("via_room")),
              "players_back": terms["outgoing_ids"], "picks_back": terms["pick_ids"], "cash": bool(terms.get("cash")),
              "by": by, "reasons": dict(reasons or {})}
    store(save).append(record)
    log = {"id": stable_id("transaction_log", "sign_and_trade", pid, when), "date": when, "transaction_type": "trade",
           "proposal_id": stable_id("sign_and_trade", season, pid, when), "status": "applied_to_save_ledger",
           "teams": [sender, receiver],
           "assets": {"from_assets": [{"kind": "player", "id": pid, "label": terms["player_name"],
                                       "sign_and_trade": True}],
                      "to_assets": [{"kind": "player", "id": x, "label": names.get(x, x)} for x in terms["outgoing_ids"]]
                      + [{"kind": "pick", "id": x} for x in terms["pick_ids"]]},
           "evaluations": [], "source_ids": ["src_contract_market_config_v1"], "sign_and_trade": True,
           "notes": "Sign-and-trade (FA-REAL slice 4)."}
    if reasons:
        log["trade_reasons"] = {_abbrev(k): v for k, v in reasons.items()}
    save.setdefault("transaction_logs", []).append(log)
    from .save import add_league_event, add_news
    add_news(save, "trade", headline, date_value=when)
    add_league_event(save, "trade", headline, date_value=when, team_ids=[sender, receiver],
                     player_ids=[pid, *terms["outgoing_ids"]], importance=0.66,
                     details={"sign_and_trade": True, "player_id": pid})
    return record


# ---------------------------------------------------------------------------------------------------------------------
# Choosing what goes back

def filler_options(active: dict[str, Any], save: dict[str, Any], receiver: str, needed: float, season: str,
                   when: str) -> list[str] | None:
    """The fewest bench players (and least salary) the receiving team can send so that ``needed`` incoming salary
    matches; None if no such package of up to two players exists."""
    from . import cap_ledger, two_way
    from .save import display_minutes_projection
    from .transactions import goat_exception_player
    core = set(((save.get("team_plans") or {}).get(receiver) or {}).get("core_ids") or [])
    players = {p["id"]: p for p in active.get("players", [])}
    bench = []
    for pid in two_way.standard_roster_ids(active, save, receiver):
        player = players.get(pid)
        if not player or pid in core or goat_exception_player(player):
            continue
        if display_minutes_projection(player) >= float(RULES["filler_max_minutes"]):
            continue
        if cap_ledger.newly_signed_trade_block(save, pid, when):
            continue
        salary = _player_salary(active, save, pid, season)
        if salary > 0:
            bench.append((salary, pid))
    bench.sort()
    for salary, pid in bench:
        if matching_limit(salary, season) >= needed:
            return [pid]
    for i in range(len(bench)):
        for j in range(i + 1, len(bench)):
            total = bench[i][0] + bench[j][0]
            if matching_limit(total, season) >= needed:
                return [bench[i][1], bench[j][1]]
    return None


def second_round_pick(active: dict[str, Any], save: dict[str, Any], team_id: str, season: str) -> str | None:
    """The receiving team's own unprotected future second-round pick to send (a departing free agent's usual price)."""
    overrides = save.get("draft_pick_overrides") or {}
    next_draft = season_start(season) + 1
    options = []
    for pick in active.get("draft_picks", []):
        owner = overrides.get(pick["id"], pick.get("current_owner_team_id"))
        if (owner == team_id and pick.get("original_team_id") == team_id and int(pick.get("round") or 0) == 2
                and not pick.get("protections") and not pick.get("_obligation_locked")
                and str(pick.get("status") or "") not in {"used_draft_pick", "forfeited"}
                and str(pick.get("season") or "").isdigit() and int(pick["season"]) >= next_draft):
            options.append((int(pick["season"]), pick["id"]))
    return sorted(options)[0][1] if options else None


# ---------------------------------------------------------------------------------------------------------------------
# AI

def ai_pass(active: dict[str, Any], save: dict[str, Any], when: str, *, seed: int = 1, day_key: str = "") -> list[dict[str, Any]]:
    """AI sign-and-trades for one market day (see the module notes for the reasons)."""
    from . import cap_ledger
    from .save import display_minutes_projection, human_controlled_team_ids, players_by_id_index
    from .offseason_decisions import restricted_player_ids
    if not window_open(save, when):
        return []
    humans = human_controlled_team_ids(save)
    state = save.get("free_agency_state") or {}
    asks = state.get("player_asks_millions") or {}
    season = cap_ledger.cap_year(save)
    players = players_by_id_index(active)
    restricted = restricted_player_ids(save)
    rights = {}
    for right in save.get("re_signing_rights", []) or []:
        rights.setdefault(right.get("player_id"), right.get("team_id"))
    done = []
    teams = [t for t in active.get("teams", []) if t["id"] not in humans]
    from .play import ai_free_agency_suitors, canonical_free_agent_market_by_id
    market_by_id = canonical_free_agent_market_by_id(active)
    for pid in sorted(save.get("free_agent_player_ids") or []):
        player = players.get(pid)
        sender = rights.get(pid)
        if not player or not sender or sender in humans or pid in restricted:
            continue
        if display_minutes_projection(player) < float(RULES["min_minutes"]):
            continue
        ask = float(asks.get(pid) or 0.0)
        if ask < float(RULES["min_ask_millions"]):
            continue
        if any(o.get("player_id") == pid and o.get("team_id") == sender and o.get("status") == "active"
               for o in save.get("free_agent_offers", []) or []):
            continue   # his team is still trying to keep him
        if not cap_ledger.incumbent_bird(active, save, player, sender):
            continue
        salary = ask * 1_000_000
        age = float(player.get("display_age", player.get("age")) or 27)
        years = MAX_YEARS if age <= 29 else MIN_YEARS
        suitors = [t for t in ai_free_agency_suitors(active, save, player, teams, market_by_id.get(pid) or {}, seed, 9)
                   if t["id"] != sender][:int(RULES["suitors"])]
        for team in suitors:
            receiver = team["id"]
            direct = cap_ledger.quote(active, save, receiver, player, salary, min(years, 4), season=season, bird=None)
            if direct.get("ok"):
                continue   # it can sign him outright; no trade needed
            recv_pay = cap_ledger.team_payroll(active, save, receiver, season, today=when)
            if recv_pay["apron_payroll"] + salary > recv_pay["lines"]["first_apron"] + 15_000_000:
                continue
            outgoing: list[str] = []
            if recv_pay["cap_payroll"] + salary > recv_pay["lines"]["salary_cap"]:
                outgoing = filler_options(active, save, receiver, salary, season, when) or []
                if not outgoing:
                    continue
            pick = second_round_pick(active, save, receiver, season)
            terms = quote(active, save, player, sender, receiver, salary, years, outgoing_ids=outgoing,
                          pick_ids=[pick] if pick else [], when=when)
            if not terms["ok"]:
                continue
            # It must still be able to fill its roster to the minimum under the hard cap the trade triggers (two
            # replays left receivers at 10-11 players, unable to add a minimum contract).
            from . import two_way
            standard_after = two_way.standard_roster_count(active, save, receiver) + 1 - len(outgoing)
            fill = max(0, 15 - standard_after) * float(cap_ledger.minimum_salary(season, 2))
            if terms["receiver_apron_after"] + fill > terms["first_apron"] + 1:
                continue
            from .payroll_plan import payroll_check
            check = payroll_check(active, save, receiver, season, add_salary=salary, remove_salary=terms["back_salary"],
                                  roster_delta=1 - len(outgoing), minutes=display_minutes_projection(player),
                                  kind="free_agency", age=age)
            if not check["ok"]:
                continue
            if _hash(seed, season, pid, receiver, day_key, "sign-and-trade") >= float(RULES["agree_rate"]):
                continue
            terms["cash"] = not pick
            reasons = {
                receiver: (f"wanted {player.get('name')} ({display_minutes_projection(player):.0f} minutes) but had no "
                           f"room or exception big enough to sign him outright"),
                sender: (f"wasn't keeping him and got {'a second-round pick' if pick else 'cash'}"
                         f"{' and salary that matched' if outgoing else ''} instead of losing him for nothing"),
            }
            done.append(execute(active, save, terms, when=when, by="ai", reasons=reasons))
            break
    return done


def user_options(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], user_team: str) -> dict[str, Any]:
    """What the room shows for a sign-and-trade involving this free agent and the user's team: as the sending team
    (your own free agent: the teams he'd join), or as the receiving team (another team's free agent)."""
    from . import cap_ledger
    from .save import players_by_id_index  # noqa: F401
    state = save.get("free_agency_state") or {}
    ask = float((state.get("player_asks_millions") or {}).get(player["id"]) or 0.0)
    rights = next((r.get("team_id") for r in save.get("re_signing_rights", []) or [] if r.get("player_id") == player["id"]), None)
    if not window_open(save) or not rights:
        return {"available": False, "reason": "No sign-and-trade: he has no team holding his rights, or the window is closed."}
    season = cap_ledger.cap_year(save)
    years = MAX_YEARS if float(player.get("display_age", player.get("age")) or 27) <= 29 else MIN_YEARS
    if rights == user_team:
        from .play import ai_free_agency_suitors, canonical_free_agent_market_by_id
        teams = [t for t in active.get("teams", []) if t["id"] != user_team]
        market = canonical_free_agent_market_by_id(active).get(player["id"]) or {}
        rows = []
        for team in ai_free_agency_suitors(active, save, player, teams, market, int((save.get("meta") or {}).get("seed") or 1), 9)[:8]:
            receiver = team["id"]
            outgoing = []
            recv_pay = cap_ledger.team_payroll(active, save, receiver, season)
            if recv_pay["cap_payroll"] + ask * 1e6 > recv_pay["lines"]["salary_cap"]:
                outgoing = filler_options(active, save, receiver, ask * 1e6, season, str(save["state"]["current_date"])) or []
            pick = second_round_pick(active, save, receiver, season)
            terms = quote(active, save, player, user_team, receiver, ask * 1e6, years, outgoing_ids=outgoing,
                          pick_ids=[pick] if pick else [])
            rows.append({"team_id": receiver, "abbrev": team.get("abbrev"), "ok": terms["ok"],
                         "problems": terms["problems"], "notes": terms["notes"], "outgoing_ids": outgoing,
                         "pick_ids": [pick] if pick else [], "salary_millions": ask, "years": years,
                         "schedule": terms["schedule"], "base_year": terms["base_year"]})
        return {"available": True, "role": "sender", "ask_millions": ask, "years": years, "receivers": rows}
    from . import two_way
    from .save import display_minutes_projection
    when = str((save.get("state") or {}).get("current_date") or "")
    players = {p["id"]: p for p in active.get("players", [])}
    bench = []
    for pid in two_way.standard_roster_ids(active, save, user_team):
        player_row = players.get(pid) or {}
        salary = _player_salary(active, save, pid, season)
        if salary <= 0 or cap_ledger.newly_signed_trade_block(save, pid, when):
            continue
        bench.append({"player_id": pid, "name": player_row.get("name"), "salary_millions": round(salary / 1e6, 2),
                      "minutes": display_minutes_projection(player_row)})
    bench.sort(key=lambda row: (row["minutes"], row["salary_millions"]))
    return {"available": True, "role": "receiver", "sender": rights, "sender_abbrev": _abbrev(rights),
            "ask_millions": ask, "years": years, "bench": bench[:14],
            "pick_id": second_round_pick(active, save, user_team, season)}


def ai_answer(active: dict[str, Any], save: dict[str, Any], terms: dict[str, Any], user_team: str) -> dict[str, Any]:
    """Would the AI side(s) and the player agree? The player: a salary at least his ask, with a team among his likely
    suitors. An AI receiver: he fits its payroll plan and it couldn't do better; an AI sender: it isn't keeping him
    (no active bid of its own) and gets something back."""
    from .save import display_minutes_projection, players_by_id_index
    from .payroll_plan import payroll_check, plain_words
    player = players_by_id_index(active).get(terms["player_id"]) or {}
    state = save.get("free_agency_state") or {}
    ask = float((state.get("player_asks_millions") or {}).get(terms["player_id"]) or 0.0) * 1e6
    if terms["salary"] + 1 < ask:
        return {"ok": False, "who": "player", "reason": f"{terms['player_name']} wants at least {_m(ask)} a year."}
    if terms["receiver"] != user_team:
        check = payroll_check(active, save, terms["receiver"], terms["season"], add_salary=terms["salary"],
                              remove_salary=terms["back_salary"], roster_delta=1 - len(terms["outgoing_ids"]),
                              minutes=display_minutes_projection(player), kind="free_agency",
                              age=player.get("display_age", player.get("age")))
        if not check["ok"]:
            return {"ok": False, "who": "receiver", "reason": f"{_abbrev(terms['receiver'])} says no: {plain_words(check)}"}
    if terms["sender"] != user_team:
        keeping = any(o.get("player_id") == terms["player_id"] and o.get("team_id") == terms["sender"]
                      and o.get("status") == "active" for o in save.get("free_agent_offers", []) or [])
        if keeping:
            return {"ok": False, "who": "sender", "reason": f"{_abbrev(terms['sender'])} is still trying to re-sign him."}
        if not terms["pick_ids"] and not terms["outgoing_ids"]:
            return {"ok": False, "who": "sender", "reason": f"{_abbrev(terms['sender'])} wants something back: add a pick."}
    return {"ok": True, "who": "", "reason": "Everyone agrees."}
