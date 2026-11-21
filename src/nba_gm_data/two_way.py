"""Two-way contracts (FA-REAL slice 4).

A two-way contract lets a young player split the season between his NBA team and its development-league (G League)
affiliate. The rules (2023 CBA Art. II §11, Art. VII §4, Art. XXIX; research ``docs/agents/tasks/fa-realism-research.md``):

- **Three places of their own**, outside the 15 standard roster spots (and outside the 21-player offseason maximum
  only in so far as that maximum counts everyone: two-ways count toward the 21 in the summer).
- **Who may sign one:** a player with fewer than four years of NBA service in every season the deal covers, and at
  most three seasons on two-way deals with the same team.
- **Pay:** half the rookie minimum ($678,882 in 2026-27), prorated after opening night, and **outside team salary**
  (no cap, tax or apron charge).
- **Length:** one or two seasons, no options.
- **50 NBA active games** a full season (prorated for a later signing). A game counts when he is on the active list,
  even if he never leaves the bench.
- **Conversion** to a standard contract (the minimum, or a permitted new deal) any time before the team's last
  regular-season game; only then is he eligible for the playoffs. It needs a standard roster spot and must fit any hard
  cap the team has triggered.
- The last day to sign a two-way for the season is March 4 (real calendar), the same day in the game.

**How the game models it.** Two-way players are kept off the 15-player standard roster entirely: they are not in the
team's payroll, trades, or standard roster counts. They live in ``save["two_way"]``. On a game day the head coach calls
a two-way up (puts him on the active list) when the team has fewer than 13 healthy standard players, or when he is
good enough to be one of the team's 12 best healthy players (the Spencer Jones case); each call-up counts one active
game, and a player at his limit stays with the affiliate. Everything here is a fixed rule with a stated reason, from
Codex's 2023-2026 evidence (``docs/agents/tasks/roster-edge-evidence.md``): no random draws.

AI teams (``RULES``):
- fill their three places through the summer (late second-round picks first, then the best young free agents; most
  clubs complete their opening trio in September or October), and refill an empty place in season until March 4;
- promote (convert) mostly from February on, when a teammate is out injured and the two-way is good enough to play, or
  when he is about to reach his active-game limit, and before the last game for playoff eligibility.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta
from typing import Any

from .cap_rules import season_start
from .utils import stable_id

TWO_WAY_SLOTS = 3
ACTIVE_GAME_LIMIT = 50
SERVICE_LIMIT = 4            # the deal may not cover a season in which he has 4+ years of service
TEAM_SEASON_LIMIT = 3        # at most three seasons on two-way deals with the same team
SIGNING_DEADLINE_MONTH_DAY = (3, 4)
STANDARD_ROSTER_MAXIMUM = 15
OFFSEASON_ROSTER_MAXIMUM = 21

# Every number the AI uses, with the evidence behind it (roster-edge-evidence.md).
RULES = {
    # Call-ups: the coach dresses a two-way when fewer than this many standard players are healthy ...
    "callup_healthy_floor": 13,
    # ... or when he is better than the team's Nth best healthy standard player by overall rating (a real rotation
    # option: Spencer Jones started 34 of 46 games on his Denver two-way). Set so that about 15-20 two-ways a season
    # reach the 50-game limit (at least 5, 13 and 14 were confirmed in 2023-2025 with incomplete inactive lists).
    "callup_rank": 10,
    # The minutes the coach plans for a called-up two-way (his own projection, at most this; a body for a short
    # bench gets the end-of-bench share). The game's in-game coach then decides.
    "callup_rotation_minutes": 10.0,
    "callup_bench_minutes": 4.0,
    # Second-round picks: "a later pick is more likely to get a two-way; the fit chose pick 40 in three folds and
    # pick 43 in the 2026 test" (10-14 of 28-30 second-rounders opened on a two-way).
    "draft_pick_two_way_from": 41,
    # Summer fill: the number of places an AI team fills by each date. In 2023-2026, 8-12 clubs had completed their
    # opening trio by the end of August, 13-18 more did so in September or October; 23-28 of 30 opened with three.
    "summer_targets": (("07-06", 1), ("08-01", 2), ("09-20", 3)),
    # On September 20 a team with a two-way-eligible camp deal keeps its third place open for him at this rate.
    "camp_hold_rate": 0.45,
    # ... and the share of clubs that leave an open place unfilled at opening (keeping it for a later signing).
    "leave_open_rate": 0.12,
    # The day before the roster deadline: last fill (camp-deal conversions first, camp.py).
    # Promotions: 76 of 87 came from February 1 on; 79 of 82 had a teammate out injured. A team promotes when it has
    # an open standard spot, the hard cap allows the minimum, and the player is good enough to play (top-N by rating).
    "promotion_from_month_day": (2, 1),
    "promotion_rank": 11,
    # A player within this many games of his limit who plays (dressed by rating) is promoted if a spot is open.
    "limit_warning_games": 4,
    # Before the last regular-season game a playoff team with an open spot keeps its best two-way for the playoffs.
    "playoff_eligibility_days": 10,
    # In-season, an empty place is refilled after this many days (55-59 signings after opening a season, 2023-2025).
    "refill_after_days": 7,
    # Two-way qualifying offers: AI teams tender players good enough to keep (top two of the team's two-ways by
    # rating, or anyone under 24 with prior production). Two-way QO acceptances were 1-4 a summer (2023-2026).
    "qualifying_offer_keep": 2,
}


# ---------------------------------------------------------------------------------------------------------------------
# Store and simple reads

def store(save: dict[str, Any]) -> dict[str, Any]:
    root = save.setdefault("two_way", {})
    root.setdefault("version", 1)
    root.setdefault("contracts", {})
    root.setdefault("history", {})
    root.setdefault("log", [])
    root.setdefault("qualifying_offers", {})
    return root


def contracts(save: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return ((save.get("two_way") or {}).get("contracts") or {})


def _label(start: int) -> str:
    return f"{start}-{str(start + 1)[-2:]}"


def current_season(save: dict[str, Any]) -> str:
    """The contract season a two-way counts in today (the one contract-season switch, June 17)."""
    from .cap_ledger import cap_year
    return cap_year(save)


def _today(save: dict[str, Any]) -> str:
    return str((save.get("state") or {}).get("current_date") or "")


def is_two_way(save: dict[str, Any], player_id: str) -> bool:
    return str(player_id) in contracts(save)


def two_way_team(save: dict[str, Any], player_id: str) -> str | None:
    rec = contracts(save).get(str(player_id))
    return rec.get("team_id") if rec else None


def two_way_ids(save: dict[str, Any]) -> set[str]:
    return set(contracts(save))


def team_two_ways(save: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    return sorted((rec for rec in contracts(save).values() if rec.get("team_id") == team_id),
                  key=lambda rec: (rec.get("signed_date") or "", rec["player_id"]))


def open_places(save: dict[str, Any], team_id: str) -> int:
    return max(0, TWO_WAY_SLOTS - len(team_two_ways(save, team_id)))


def pay(season: str) -> int:
    """A full season's two-way pay: half the rookie (no-service) minimum, $678,882 in 2026-27."""
    from .cap_ledger import minimum_salary
    return int(round(minimum_salary(season, 0) / 2.0))


def season_fraction_left(save: dict[str, Any], season: str, today: str) -> float:
    """The share of the regular season still to play on ``today`` (1.0 before opening night)."""
    from .contract_protection import season_window
    first, last = season_window(save, season)
    if not first or not last:
        return 1.0
    day = date.fromisoformat(str(today)[:10])
    if day <= first:
        return 1.0
    if day > last:
        return 0.0
    return max(0.0, ((last - day).days + 1) / ((last - first).days + 1))


def active_limit(save: dict[str, Any], season: str, signed: str) -> int:
    """50 active games for a full season, prorated for a signing after opening night."""
    return int(round(ACTIVE_GAME_LIMIT * season_fraction_left(save, season, signed)))


def active_games(rec: dict[str, Any], season: str) -> int:
    return int((rec.get("active_games") or {}).get(season) or 0)


def games_left(rec: dict[str, Any], season: str) -> int:
    limit = int((rec.get("active_limit") or {}).get(season, ACTIVE_GAME_LIMIT))
    return max(0, limit - active_games(rec, season))


def team_seasons(save: dict[str, Any], player_id: str, team_id: str) -> list[str]:
    return list(((store(save)["history"].get(str(player_id)) or {}).get(str(team_id)) or []))


def years_of_service(player: dict[str, Any], season: str) -> int:
    from .cap_ledger import years_of_service as service
    return service(player, season)


def eligibility(save: dict[str, Any], player: dict[str, Any], team_id: str, season: str, years: int = 1,
                *, today: str | None = None) -> dict[str, Any]:
    """May he sign a two-way with this team for these seasons? {ok, reason} in plain words."""
    years = max(1, min(2, int(years or 1)))
    today = str(today or _today(save))
    seasons = [_label(season_start(season) + k) for k in range(years)]
    service = years_of_service(player, season)
    if service + years - 1 >= SERVICE_LIMIT:
        return {"ok": False, "reason": f"He has {service} years in the league; a two-way may not cover a season with "
                                       f"{SERVICE_LIMIT} or more."}
    used = set(team_seasons(save, player["id"], team_id))
    if len(used | set(seasons)) > TEAM_SEASON_LIMIT:
        return {"ok": False, "reason": f"He has already spent {len(used)} seasons on two-way deals with this team "
                                       f"(the limit is {TEAM_SEASON_LIMIT})."}
    md = (int(today[5:7]), int(today[8:10])) if len(today) >= 10 else (7, 1)
    if today and season_start(season) + 1 == int(today[:4]) and SIGNING_DEADLINE_MONTH_DAY < md < (6, 17):
        return {"ok": False, "reason": "The last day to sign a two-way this season was March 4."}
    rec = contracts(save).get(str(player["id"]))
    if rec and rec.get("team_id") != team_id:
        return {"ok": False, "reason": "He is on another team's two-way contract."}
    return {"ok": True, "reason": "", "service": service, "seasons": seasons}


def _player_lookup(active: dict[str, Any]) -> dict[str, dict[str, Any]]:
    from .save import players_by_id_index
    return players_by_id_index(active)


def overall(active: dict[str, Any], player_id: str) -> float:
    from .save import player_attribute_summary
    try:
        return float(player_attribute_summary(active, player_id).get("overall") or 0.0)
    except Exception:  # pragma: no cover - a player missing ratings ranks last
        return 0.0


# ---------------------------------------------------------------------------------------------------------------------
# Signing, releasing, converting

def _log(save: dict[str, Any], kind: str, rec: dict[str, Any], when: str, **extra: Any) -> None:
    store(save)["log"].append({"kind": kind, "player_id": rec.get("player_id"), "name": rec.get("name"),
                               "team_id": rec.get("team_id"), "date": when, **extra})


def _transaction(save: dict[str, Any], kind: str, team_id: str, player: dict[str, Any], when: str, notes: str) -> None:
    save.setdefault("transaction_logs", []).append({
        "id": stable_id("transaction_log", kind, when, team_id, player["id"]),
        "date": when, "transaction_type": kind, "proposal_id": stable_id(kind, when, team_id, player["id"]),
        "status": "applied_to_save_ledger", "teams": [team_id],
        "assets": {"player_id": player["id"], "name": player.get("name")}, "evaluations": [],
        "source_ids": ["src_contract_market_config_v1"], "notes": notes})


def sign(save: dict[str, Any], player: dict[str, Any], team_id: str, *, years: int = 1, how: str = "signed",
         when: str | None = None, by: str = "ai", news: bool = True) -> dict[str, Any]:
    """Sign ``player`` to a two-way with ``team_id`` (raises ValueError when it is not allowed). He leaves the free-agent
    pool and any standard contract he held with this team (a camp deal converted, or a drafted rookie signed to a
    two-way instead of a standard deal)."""
    when = str(when or _today(save))
    season = current_season(save)
    pid = str(player["id"])
    years = max(1, min(2, int(years or 1)))
    check = eligibility(save, player, team_id, season, years, today=when)
    if not check["ok"]:
        raise ValueError(check["reason"])
    if open_places(save, team_id) <= 0 and two_way_team(save, pid) != team_id:
        raise ValueError("All three two-way places are filled.")
    from .waivers import pending_ids
    if pid in pending_ids(save):
        raise ValueError("He is on waivers.")
    roster = save.get("roster_overrides") or {}
    current_team = roster.get(pid, player.get("team_id"))
    if current_team and current_team != team_id:
        raise ValueError("He is under contract with another team.")
    seasons = check["seasons"]
    fraction = season_fraction_left(save, season, when)
    full = pay(season)
    rec = {
        "player_id": pid, "name": player.get("name"), "team_id": team_id, "signed_date": when, "how": how, "by": by,
        "seasons": [{"season": s, "salary": int(round(full * fraction)) if k == 0 else pay(s)}
                    for k, s in enumerate(seasons)],
        "active_limit": {seasons[0]: active_limit(save, seasons[0], when)},
        "active_games": {},
        "service": check["service"],
    }
    root = store(save)
    root["contracts"][pid] = rec
    history = root["history"].setdefault(pid, {}).setdefault(team_id, [])
    for s in seasons:
        if s not in history:
            history.append(s)
    # Off the standard roster and out of the free-agent pool.
    if current_team == team_id:
        save.setdefault("roster_overrides", {})[pid] = None
        (save.get("contract_overrides") or {}).pop(pid, None)
    save.setdefault("roster_overrides", {})[pid] = None
    save["free_agent_player_ids"] = sorted(set(save.get("free_agent_player_ids") or []) - {pid})
    released = (save.get("released_free_agents") or {}).get(pid)
    if released and released.get("status") == "available":
        released.update(status="signed", signed_team_id=team_id, signed_date=when)
    for bid in save.get("free_agent_offers", []) or []:
        if bid.get("player_id") == pid and bid.get("status") == "active":
            bid["status"] = "player_signed_elsewhere"
            from .cap_ledger import release as release_bid
            release_bid(bid)
    _log(save, "signed", rec, when, how=how, by=by)
    abbrev = str(team_id).replace("team_", "").upper()
    _transaction(save, "two_way_signing", team_id, player, when,
                 f"Two-way contract ({years} season{'s' if years > 1 else ''}, {how}).")
    if news:
        from .save import add_news
        words = {"converted_camp_deal": "converted his camp deal to a two-way contract",
                 "draft": "signed its draft pick to a two-way contract",
                 "qualifying_offer": "re-signed him on his two-way qualifying offer"}.get(how, "signed him to a two-way contract")
        add_news(save, "roster_move", f"{abbrev} {words}: {player.get('name')}.", date_value=when)
    return rec


def release(save: dict[str, Any], player_id: str, *, when: str | None = None, by: str = "ai",
            reason: str = "") -> dict[str, Any] | None:
    """Release a two-way player: he becomes a free agent and his place opens. (Real two-ways also go through 48-hour
    waivers; claims of two-ways are rare and the game lets him go straight to the market.)"""
    when = str(when or _today(save))
    rec = store(save)["contracts"].pop(str(player_id), None)
    if rec is None:
        return None
    save["free_agent_player_ids"] = sorted(set(save.get("free_agent_player_ids") or []) | {str(player_id)})
    save.setdefault("released_free_agents", {})[str(player_id)] = {
        "player_id": str(player_id), "player_name": rec.get("name"), "waived_by_team_id": rec.get("team_id"),
        "release_date": when, "status": "available", "reason": "two_way_release"}
    rec = {**rec, "released_date": when}
    _log(save, "released", rec, when, by=by, reason=reason)
    _transaction(save, "two_way_release", rec["team_id"], {"id": rec["player_id"], "name": rec.get("name")}, when,
                 f"Two-way contract released. {reason}".strip())
    store(save).setdefault("open_since", {})[rec["team_id"]] = when
    return rec


def conversion_quote(active: dict[str, Any], save: dict[str, Any], player_id: str, *, years: int | None = None,
                     when: str | None = None) -> dict[str, Any]:
    """What converting his two-way to a standard contract costs and whether it is allowed: a standard roster spot, the
    last regular-season game not passed, and a minimum contract that fits any hard cap. {ok, reason, payment}."""
    when = str(when or _today(save))
    rec = contracts(save).get(str(player_id))
    if not rec:
        return {"ok": False, "reason": "He is not on a two-way contract."}
    team_id = rec["team_id"]
    season = current_season(save)
    from .contract_protection import season_window
    first, last = season_window(save, season)
    if last and date.fromisoformat(when[:10]) >= last:
        return {"ok": False, "reason": "Two-way players can be converted only before the team's last regular-season game."}
    room = standard_room(active, save, team_id, when, converting=str(player_id))
    if room["open"] <= 0:
        return {"ok": False, "reason": room["reason"]}
    player = _player_lookup(active).get(str(player_id)) or {"id": str(player_id), "name": rec.get("name")}
    service = years_of_service(player, season)
    years = int(years or (2 if float(player.get("display_age", player.get("age")) or 27) < 26 else 1))
    years = max(1, min(2, years))
    from .save import minimum_contract_payment
    from .cap_ledger import team_payroll
    payment = minimum_contract_payment(player, season, years)
    fraction = season_fraction_left(save, season, when)
    if fraction < 1.0:
        # An in-season signing is prorated: he is paid (and counts) for the days left.
        for row in payment["schedule"][:1]:
            row["salary"] = int(round(float(row["salary"]) * fraction))
            row["cap_charge"] = int(round(float(row["cap_charge"]) * fraction))
        payment["salary"] = payment["schedule"][0]["salary"]
        payment["amount"] = payment["schedule"][0]["cap_charge"]
    payroll = team_payroll(active, save, team_id, season, today=when)
    ceiling = payroll.get("hard_cap")
    if ceiling and payroll["apron_payroll"] + float(payment["amount"]) > float(ceiling["amount"]) + 1:
        return {"ok": False, "reason": f"A minimum contract would take the team past its hard cap "
                                       f"(${float(ceiling['amount']) / 1e6:.1f}M); it must cut or trade salary first.",
                "payment": payment}
    payment["trade_eligible_date"] = None
    return {"ok": True, "reason": "", "payment": payment, "years": years, "service": service,
            "salary_millions": round(float(payment["salary"]) / 1e6, 3)}


def convert(active: dict[str, Any], save: dict[str, Any], player_id: str, *, years: int | None = None,
            when: str | None = None, by: str = "ai", reason: str = "") -> dict[str, Any]:
    """Convert a two-way to a standard minimum contract (raises ValueError when not allowed)."""
    when = str(when or _today(save))
    quote = conversion_quote(active, save, player_id, years=years, when=when)
    if not quote["ok"]:
        raise ValueError(quote["reason"])
    rec = store(save)["contracts"].pop(str(player_id))
    team_id = rec["team_id"]
    season = current_season(save)
    payment = quote["payment"]
    from .cap_ledger import commit, contract_seasons, contract_terms
    seasons = contract_seasons(payment, status="two_way_conversion")
    save.setdefault("roster_overrides", {})[str(player_id)] = team_id
    save.setdefault("contract_overrides", {})[str(player_id)] = {
        "team_id": team_id, "seasons": seasons, "status": "two_way_conversion",
        "original_contract_years": len(seasons), "signed_season": season, "signed_date": when,
        "converted_from_two_way": True, **contract_terms(payment)}
    commit(save, team_id, str(player_id), payment, when)
    rec = {**rec, "converted_date": when}
    store(save).setdefault("conversions", []).append(
        {"player_id": rec["player_id"], "name": rec.get("name"), "team_id": team_id, "date": when, "season": season,
         "active_games": active_games(rec, season), "by": by, "reason": reason})
    store(save).setdefault("open_since", {})[team_id] = when
    _log(save, "converted", rec, when, by=by, reason=reason)
    _transaction(save, "two_way_conversion", team_id, {"id": rec["player_id"], "name": rec.get("name")}, when,
                 f"Two-way converted to a standard contract. {reason}".strip())
    from .save import add_news
    add_news(save, "roster_move", f"{str(team_id).replace('team_', '').upper()} converted {rec.get('name')} from a "
                                  f"two-way to a standard contract{': ' + reason if reason else ''}.", date_value=when)
    return {"status": "converted", "player_id": str(player_id), "payment": payment}


# ---------------------------------------------------------------------------------------------------------------------
# Standard roster counts (two-ways never count)

def standard_roster_ids(active: dict[str, Any], save: dict[str, Any], team_id: str) -> list[str]:
    roster = save.get("roster_overrides") or {}
    ids = set()
    for player in active.get("players", []):
        pid = player.get("id")
        if not pid or player.get("_inactive_player"):
            continue
        tid = roster.get(pid, player.get("team_id")) if pid in roster else player.get("team_id")
        if tid == team_id:
            ids.add(pid)
    for pid, tid in roster.items():
        if tid == team_id:
            ids.add(pid)
    retired = set(save.get("retired_player_ids") or [])
    return sorted(ids - retired - two_way_ids(save))


def standard_roster_count(active: dict[str, Any], save: dict[str, Any], team_id: str) -> int:
    return len(standard_roster_ids(active, save, team_id))


def in_season_limits(save: dict[str, Any], when: str | None = None) -> bool:
    """True from the roster deadline (the day before opening night) through the playoffs: 15 standard players. Before it,
    in the offseason, teams may carry 21 players in all, two-ways included."""
    from .offseason_calendar import roster_deadline
    when = str(when or _today(save))
    phase = str((save.get("state") or {}).get("phase") or "")
    if phase in {"regular_season", "play_in", "playoffs"}:
        return True
    if phase != "preseason":
        return False
    season = str((save.get("meta") or {}).get("season") or "2026-27")
    return when >= roster_deadline(season_start(season), save).isoformat()


def standard_room(active: dict[str, Any], save: dict[str, Any], team_id: str, when: str | None = None, *,
                  converting: str | None = None) -> dict[str, Any]:
    """Open standard roster spots: up to 15 standard players in season; in the offseason up to 21 players in all
    (two-ways count toward the 21). ``converting``: a two-way moving to the standard roster (already in the 21)."""
    standard = standard_roster_count(active, save, team_id)
    two_ways = len(team_two_ways(save, team_id))
    if in_season_limits(save, when):
        open_spots = STANDARD_ROSTER_MAXIMUM - standard
        reason = f"No standard roster spot: {standard} of {STANDARD_ROSTER_MAXIMUM} are filled."
    else:
        total = standard + two_ways - (1 if converting and is_two_way(save, converting) else 0)
        open_spots = OFFSEASON_ROSTER_MAXIMUM - total
        reason = f"The roster is full: {total} of the {OFFSEASON_ROSTER_MAXIMUM} offseason places are filled."
    return {"open": max(0, open_spots), "standard": standard, "two_way": two_ways, "reason": reason}


# ---------------------------------------------------------------------------------------------------------------------
# Game days: who is on the active list

def _health_out(save: dict[str, Any]) -> set[str]:
    from .save import player_unavailable_for_rotation
    return {str(s.get("player_id")) for s in save.get("health_states", []) or []
            if s.get("player_id") and player_unavailable_for_rotation(s)}


def _teams_in_games(runtime: dict[str, Any], games: list[dict[str, Any]]) -> set[str]:
    from .sim import espn_team_id_map
    teams_by_espn = espn_team_id_map(runtime)
    teams: set[str] = set()
    for game in games:
        for side in ("homeTeamId", "awayTeamId"):
            team = teams_by_espn.get(str(game.get(side)))
            if team:
                teams.add(team["id"])
    return teams


def dress_for_games(save: dict[str, Any], runtime: dict[str, Any], games: list[dict[str, Any]], day: str
                    ) -> list[tuple[str, str]]:
    """Put the two-ways the coach calls up today on their teams in the day's league view (``runtime``) so the game
    simulation can use them, and return (team_id, player_id) pairs; ``undress`` counts the games and sends them back.

    The coach calls a two-way up when fewer than 13 standard players are healthy (best two-way first), or when he is
    better than the team's 12th best healthy standard player (a real rotation option). A player at his active-game
    limit stays with the affiliate."""
    recs = contracts(save)
    if not recs or not games:
        return []
    if str((save.get("state") or {}).get("phase") or "") != "regular_season":
        return []
    season = current_season(save)
    teams_today = _teams_in_games(runtime, games)
    lines = store(save).get("team_lines") or {}
    players = _player_lookup(runtime)
    out = _health_out(save)
    team_by_id = {t["id"]: t for t in runtime.get("teams", [])}
    standard_by_team: dict[str, list[str]] = {}
    for player in runtime.get("players", []):
        tid = player.get("team_id")
        if tid in teams_today and not player.get("_inactive_player") and player["id"] not in recs:
            standard_by_team.setdefault(tid, []).append(player["id"])
    dressed: list[tuple[str, str]] = []
    for tid in sorted(teams_today):
        mine = [rec for rec in recs.values() if rec.get("team_id") == tid]
        if not mine:
            continue
        candidates = []
        for rec in mine:
            pid = rec["player_id"]
            player = players.get(pid)
            if player is None or pid in out or player.get("_inactive_player") or games_left(rec, season) <= 0:
                continue
            candidates.append((float(rec.get("rating") or 0.0), pid, player))
        if not candidates:
            continue
        candidates.sort(key=lambda row: (-row[0], row[1]))
        standard = standard_by_team.get(tid, [])
        healthy = [pid for pid in standard if pid not in out]
        need = max(0, int(RULES["callup_healthy_floor"]) - len(healthy))
        rated = dict(lines.get(tid) or [])
        healthy_ratings = sorted((float(rated.get(pid, 0.0)) for pid in healthy), reverse=True)
        rank = int(RULES["callup_rank"])
        cutoff = healthy_ratings[rank - 1] if len(healthy_ratings) >= rank else -1.0
        for index, (rating, pid, player) in enumerate(candidates):
            short_bench = index < need
            if not short_bench and rating <= cutoff:
                continue
            team = team_by_id.get(tid) or {}
            player["team_id"] = tid
            player["team_abbrev"] = team.get("abbrev")
            player["_two_way_called_up"] = True
            # The coach's plan for him: a rotation option gets at most a backup's minutes, a body for a short bench
            # the end-of-bench share (his own projection is from a different team and role).
            planned = (float(RULES["callup_bench_minutes"]) if short_bench and rating <= cutoff
                       else min(float(player.get("minutes_projection") or 0.0), float(RULES["callup_rotation_minutes"])))
            player["_two_way_minutes_before"] = player.get("minutes_projection")
            player["minutes_projection"] = max(1.0, planned)
            dressed.append((tid, pid))
    return dressed


def undress(save: dict[str, Any], runtime: dict[str, Any], dressed: list[tuple[str, str]], day: str) -> None:
    """Count one active game for every two-way the coach called up today and send them back to the affiliate."""
    if not dressed:
        return
    season = current_season(save)
    players = _player_lookup(runtime)
    recs = contracts(save)
    for tid, pid in dressed:
        player = players.get(pid)
        if player is not None:
            player["team_id"] = None
            player["team_abbrev"] = "FA"
            player.pop("_two_way_called_up", None)
            if "_two_way_minutes_before" in player:
                player["minutes_projection"] = player.pop("_two_way_minutes_before")
        rec = recs.get(pid)
        if rec is None:
            continue
        games = rec.setdefault("active_games", {})
        games[season] = int(games.get(season) or 0) + 1
        rec["last_active"] = day
        if games_left(rec, season) == 0 and not rec.get("limit_reached"):
            rec["limit_reached"] = day
            store(save).setdefault("limit_reached", []).append(
                {"player_id": pid, "name": rec.get("name"), "team_id": tid, "season": season, "date": day,
                 "active_games": games[season]})
            from .save import add_news
            add_news(save, "roster_move", f"{rec.get('name')} has reached his two-way active-game limit "
                                          f"({games[season]} games); he stays with the G League affiliate unless "
                                          f"{str(tid).replace('team_', '').upper()} converts his contract.",
                     date_value=day)


def refresh_ratings(active: dict[str, Any], save: dict[str, Any], *, teams: set[str] | None = None) -> None:
    """Store each two-way's overall rating and each team's standard players' ratings (for the coach's call-ups on game
    days, without recomputing ratings every game). Refreshed weekly and after signings."""
    recs = contracts(save)
    if not recs:
        return
    root = store(save)
    lines = root.setdefault("team_lines", {})
    for rec in recs.values():
        rec["rating"] = round(overall(active, rec["player_id"]), 2)
    wanted = teams or {rec["team_id"] for rec in recs.values()}
    for tid in sorted(wanted):
        lines[tid] = [[pid, round(overall(active, pid), 2)] for pid in standard_roster_ids(active, save, tid)]


# ---------------------------------------------------------------------------------------------------------------------
# AI: who to sign, who to promote

def _hash(*parts: Any) -> float:
    digest = hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def candidate_score(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], team_id: str,
                    season: str) -> float:
    """How much an AI team wants this free agent on a two-way: his rating now, youth (development room), and his own
    team's knowledge of him (a prior two-way with this team; "prior two-way experience" was common in the evidence)."""
    rating = overall(active, player["id"])
    age = float(player.get("display_age", player.get("age")) or 25.0)
    youth = max(0.0, 25.0 - age) * 0.8
    potential = float(player.get("potential") or 0.0)
    ability = float(player.get("current_ability") or 0.0)
    upside = max(0.0, potential - ability) * 0.15 if potential and ability else 0.0
    familiar = 2.0 if team_seasons(save, player["id"], team_id) else 0.0
    return rating + youth + upside + familiar


def eligible_free_agents(active: dict[str, Any], save: dict[str, Any], season: str, today: str) -> list[dict[str, Any]]:
    from .waivers import pending_ids
    from .offseason_decisions import restricted_player_ids
    players = _player_lookup(active)
    blocked = pending_ids(save) | set(restricted_player_ids(save)) | set(save.get("retired_player_ids") or [])
    blocked |= restricted_two_way_ids(save)
    rows = []
    for pid in save.get("free_agent_player_ids") or []:
        player = players.get(pid)
        if not player or pid in blocked or player.get("_inactive_player"):
            continue
        if years_of_service(player, season) >= SERVICE_LIMIT:
            continue
        age = float(player.get("display_age", player.get("age")) or 27.0)
        if age > 27.5:
            continue
        rows.append(player)
    return rows


def ai_fill(active: dict[str, Any], save: dict[str, Any], today: str, target: int, *, seed: int = 1,
            teams: list[str] | None = None, camp_hold: bool = False) -> list[dict[str, Any]]:
    """Each AI team fills its two-way places up to ``target``: first its own late second-round picks from this
    summer's draft (moved off their standard rookie deal), then the best eligible young free agent it wants.
    ``camp_hold``: a team with a two-way-eligible camp deal may keep its last place open for him (camp.ai_cutdown
    converts him; 8-14 camp deals became two-ways each year, about one club in three)."""
    from .save import human_controlled_team_ids
    season = current_season(save)
    humans = human_controlled_team_ids(save)
    signed: list[dict[str, Any]] = []
    team_ids = teams or sorted(t["id"] for t in active.get("teams", []))
    pool = None
    taken: set[str] = set()
    draft_year = str(season_start(season))
    rookies = [r for r in save.get("incoming_rookies", []) or []
               if str(r.get("draft_year")) == draft_year and r.get("player_id")
               and int(r.get("overall_pick") or r.get("pick") or 0) >= int(RULES["draft_pick_two_way_from"])]
    players = _player_lookup(active)
    roster = save.get("roster_overrides") or {}
    rating_cache: dict[str, float] = {}
    for tid in team_ids:
        if tid in humans:
            continue
        have = len(team_two_ways(save, tid))
        team_target = int(target)
        if camp_hold and team_target >= TWO_WAY_SLOTS and _hash(seed, season, tid, "camp-hold") < float(RULES["camp_hold_rate"]):
            overrides = save.get("contract_overrides") or {}
            if any((overrides.get(pid) or {}).get("exhibit_10") and tid_ == tid
                   and eligibility(save, players.get(pid) or {"id": pid}, tid, season, 1, today=today)["ok"]
                   for pid, tid_ in roster.items()):
                team_target = TWO_WAY_SLOTS - 1
        target_here = min(TWO_WAY_SLOTS, team_target)
        if have >= target_here:
            continue
        # Late second-round picks of this draft, still on the team's standard rookie deal.
        for rookie in sorted(rookies, key=lambda r: -int(r.get("overall_pick") or 0)):
            if have >= target_here:
                break
            pid = str(rookie["player_id"])
            if rookie.get("team_id") != tid or roster.get(pid) != tid or pid in taken or is_two_way(save, pid):
                continue
            player = players.get(pid)
            if not player or not eligibility(save, player, tid, season, 2, today=today)["ok"]:
                continue
            if (store(save).get("draft_decided") or {}).get(pid):
                continue
            store(save).setdefault("draft_decided", {})[pid] = today
            try:
                signed.append(sign(save, player, tid, years=2, how="draft", when=today))
            except ValueError:
                continue
            taken.add(pid)
            have += 1
        if have >= target_here:
            continue
        if pool is None:
            pool = eligible_free_agents(active, save, season, today)
        while have < target_here:
            best = None
            for player in pool:
                if player["id"] in taken or is_two_way(save, player["id"]):
                    continue
                if not eligibility(save, player, tid, season, 1, today=today)["ok"]:
                    continue
                if player["id"] not in rating_cache:
                    rating_cache[player["id"]] = candidate_score(active, save, player, tid, season) - (
                        2.0 if team_seasons(save, player["id"], tid) else 0.0)
                familiar = 2.0 if team_seasons(save, player["id"], tid) else 0.0
                score = rating_cache[player["id"]] + familiar + _hash(seed, season, tid, player["id"]) * 1.5
                if best is None or score > best[0]:
                    best = (score, player)
            if best is None:
                break
            player = best[1]
            years = 2 if float(player.get("display_age", player.get("age")) or 25) <= 23 else 1
            if not eligibility(save, player, tid, season, years, today=today)["ok"]:
                years = 1
            try:
                signed.append(sign(save, player, tid, years=years, how="signed", when=today))
            except ValueError:
                taken.add(player["id"])
                continue
            taken.add(player["id"])
            have += 1
    if signed:
        refresh_ratings(active, save)
    return signed


def ai_promotions(active: dict[str, Any], save: dict[str, Any], today: str, *, final_call: bool = False
                  ) -> list[dict[str, Any]]:
    """AI teams convert a two-way to a standard contract when the evidence says real teams do: from February on with a
    teammate out injured and the two-way good enough to play (among the team's best healthy players), or when a playing
    two-way is about to reach his active-game limit; before the last regular-season game a team keeps its best playing
    two-way for the playoffs. Always with an open standard spot and a minimum that fits any hard cap."""
    from .save import human_controlled_team_ids
    humans = human_controlled_team_ids(save)
    season = current_season(save)
    md = (int(today[5:7]), int(today[8:10]))
    in_window = md >= tuple(RULES["promotion_from_month_day"]) and md < (6, 17)
    out = _health_out(save)
    done = []
    by_team: dict[str, list[dict[str, Any]]] = {}
    for rec in contracts(save).values():
        if rec.get("team_id") not in humans:
            by_team.setdefault(rec["team_id"], []).append(rec)
    for tid in sorted(by_team):
        standard = standard_roster_ids(active, save, tid)
        if len(standard) >= STANDARD_ROSTER_MAXIMUM:
            continue
        ratings = sorted((overall(active, pid) for pid in standard if pid not in out), reverse=True)
        line = ratings[int(RULES["promotion_rank"]) - 1] if len(ratings) >= int(RULES["promotion_rank"]) else -1.0
        injured = any(pid in out for pid in standard)
        best = None
        for rec in by_team[tid]:
            rating = float(rec.get("rating") or overall(active, rec["player_id"]))
            plays = rating > line
            near_limit = games_left(rec, season) <= int(RULES["limit_warning_games"])
            reason = None
            if plays and near_limit and active_games(rec, season) > 0:
                reason = f"he is about to reach his two-way limit ({active_games(rec, season)} active games) and plays"
            elif in_window and plays and injured:
                reason = "a teammate is out injured and he is good enough to play"
            elif final_call and plays:
                reason = "so he is eligible for the playoffs"
            if reason and (best is None or rating > best[0]):
                best = (rating, rec, reason)
        if best is None:
            continue
        rating, rec, reason = best
        try:
            done.append(convert(active, save, rec["player_id"], when=today, by="ai", reason=reason))
        except ValueError:
            continue
    return done


# ---------------------------------------------------------------------------------------------------------------------
# Expiry and two-way qualifying offers

def restricted_two_way_ids(save: dict[str, Any]) -> set[str]:
    return {pid for pid, row in (store(save)["qualifying_offers"] or {}).items() if row.get("status") == "tendered"}


def expire_contracts(save: dict[str, Any], season: str, today: str) -> list[dict[str, Any]]:
    """At the contract-season switch, two-way deals that covered only earlier seasons end. His team may send a two-way
    qualifying offer (a one-year two-way he may accept) by the June 29 deadline; until it decides, his rights stay with
    it (he joins the free-agent pool when it doesn't tender one)."""
    ended = []
    root = store(save)
    for pid, rec in list(root["contracts"].items()):
        if any(str(row.get("season")) >= season for row in rec.get("seasons") or []):
            continue
        root["contracts"].pop(pid)
        _log(save, "expired", rec, today)
        root["qualifying_offers"][pid] = {"player_id": pid, "name": rec.get("name"), "team_id": rec["team_id"],
                                          "season": season, "status": "pending", "date": today}
        ended.append(rec)
    return ended


def qualifying_offer_terms(save: dict[str, Any], player: dict[str, Any], team_id: str, season: str) -> dict[str, Any]:
    """The two-way qualifying offer: one more two-way season at two-way pay; when he can't sign another two-way with
    this team (three seasons, or four years of service) it is a one-year standard minimum instead (CBA Art. XI §1(e))."""
    check = eligibility(save, player, team_id, season, 1)
    if check["ok"]:
        return {"kind": "two_way", "salary": pay(season), "words": f"one more two-way season at ${pay(season) / 1e3:,.0f}K"}
    from .cap_ledger import minimum_salary
    amount = minimum_salary(season, years_of_service(player, season))
    return {"kind": "standard_minimum", "salary": amount,
            "words": f"a one-year standard minimum contract (${amount / 1e6:.2f}M): {check['reason']}"}


def decide_qualifying_offers(active: dict[str, Any], save: dict[str, Any], today: str) -> list[dict[str, Any]]:
    """AI teams decide their two-way qualifying offers (at the June 29 deadline): tender the players they want back
    (their best two by rating, if still young enough to develop), else let them go."""
    from .save import human_controlled_team_ids
    humans = human_controlled_team_ids(save)
    root = store(save)
    by_team: dict[str, list[dict[str, Any]]] = {}
    for row in root["qualifying_offers"].values():
        if row.get("status") == "pending":
            by_team.setdefault(row["team_id"], []).append(row)
    decided = []
    players = _player_lookup(active)
    for tid, rows in sorted(by_team.items()):
        if tid in humans:
            continue
        ranked = sorted(rows, key=lambda r: -overall(active, r["player_id"]))
        for index, row in enumerate(ranked):
            player = players.get(row["player_id"])
            if not player:
                row["status"] = "not_tendered"
                _to_pool(save, row["player_id"])
                continue
            terms = qualifying_offer_terms(save, player, tid, row["season"])
            age = float(player.get("display_age", player.get("age")) or 25)
            keep = index < int(RULES["qualifying_offer_keep"]) and age <= 26 and terms["kind"] == "two_way"
            row.update(status="tendered" if keep else "not_tendered", decided=today, terms=terms, by="ai",
                       reason=("one of the two best two-way players it had; it wants him back" if keep else
                               "it is not bringing him back"))
            if not keep:
                _to_pool(save, row["player_id"])
            decided.append(row)
    return decided


def user_qualifying_offer(save: dict[str, Any], active: dict[str, Any], player_id: str, tender: bool,
                          today: str) -> dict[str, Any]:
    row = store(save)["qualifying_offers"].get(str(player_id))
    if not row or row.get("status") not in {"pending", "tendered", "not_tendered"}:
        raise ValueError("No two-way qualifying offer decision for this player.")
    if today > f"{season_start(row['season'])}-06-29":
        raise ValueError("The qualifying-offer deadline (June 29) has passed.")
    player = _player_lookup(active).get(str(player_id)) or {"id": str(player_id), "name": row.get("name")}
    row.update(status="tendered" if tender else "not_tendered", decided=today, by="user",
               terms=qualifying_offer_terms(save, player, row["team_id"], row["season"]))
    if tender:
        save["free_agent_player_ids"] = sorted(set(save.get("free_agent_player_ids") or []) - {str(player_id)})
    else:
        _to_pool(save, str(player_id))
    return row


def _to_pool(save: dict[str, Any], player_id: str) -> None:
    if str(player_id) not in set(save.get("retired_player_ids") or []):
        save["free_agent_player_ids"] = sorted(set(save.get("free_agent_player_ids") or []) | {str(player_id)})


def resolve_qualifying_offers(active: dict[str, Any], save: dict[str, Any], today: str) -> list[dict[str, Any]]:
    """When talks open (June 30, before the market's first day): a tendered player takes his qualifying offer and is
    back with his team (two-way qualifying offers were accepted 1-4 times a summer; the game has no outside bidding for
    two-way players, so a tendered player always takes it). A pending one that nobody decided lapses."""
    root = store(save)
    done = []
    players = _player_lookup(active)
    for pid, row in sorted(root["qualifying_offers"].items()):
        if row.get("status") == "pending":
            row["status"] = "not_tendered"
            row["decided"] = today
            row["reason"] = "the deadline passed without a decision"
            _to_pool(save, pid)
            continue
        if row.get("status") != "tendered":
            continue
        player = players.get(pid)
        if player is None or pid in set(save.get("retired_player_ids") or []):
            row["status"] = "lapsed"
            _to_pool(save, pid)
            continue
        terms = row.get("terms") or qualifying_offer_terms(save, player, row["team_id"], row["season"])
        if terms.get("kind") == "two_way" and open_places(save, row["team_id"]) > 0:
            try:
                sign(save, player, row["team_id"], years=1, how="qualifying_offer", when=today,
                     by=row.get("by") or "ai")
                row["status"] = "accepted"
                done.append(row)
                continue
            except ValueError as error:
                row["status"] = "lapsed"
                row["reason"] = str(error)
                _to_pool(save, pid)
                continue
        row["status"] = "lapsed"
        row["reason"] = row.get("reason") or "no two-way place for him"
        _to_pool(save, pid)
    return done


# ---------------------------------------------------------------------------------------------------------------------
# The daily hook (save.advance_lifecycle_to)

def daily(canonical: dict[str, Any], save: dict[str, Any], day: str, active_factory, *, seed: int = 1) -> bool:
    """Date-driven two-way work (called once per calendar day by ``save.advance_lifecycle_to``); returns True when
    rosters changed. Cheap on most days."""
    from .offseason_calendar import offseason_dates, roster_deadline
    phase = str((save.get("state") or {}).get("phase") or "")
    season_label = str((save.get("meta") or {}).get("season") or "2026-27")
    start = season_start(season_label)
    md = day[5:]
    changed = False
    root = store(save)
    done = root.setdefault("passes", {})

    def once(key: str) -> bool:
        if done.get(key) is not None:
            return False
        done[key] = day
        return True

    if phase in {"playoffs", "play_in", "re_signing", "draft", "free_agency", "offseason", "training_camp"}:
        dates = offseason_dates(start + 1, save)
        if day >= dates["offseason_opens"] and once(f"expire:{start + 1}"):
            changed |= bool(expire_contracts(save, _label(start + 1), day))
        if day >= dates["decisions_deadline"] and once(f"qo:{start + 1}"):
            decide_qualifying_offers(active_factory(), save, day)
        if day >= dates["market_opens"] and once(f"qo-resolve:{start + 1}"):
            changed |= bool(resolve_qualifying_offers(active_factory(), save, day))
        if phase in {"free_agency", "offseason", "training_camp"}:
            for month_day, target in RULES["summer_targets"]:
                if md >= month_day and day[:4] == str(start + 1) and once(f"fill:{start + 1}:{month_day}"):
                    changed |= bool(ai_fill(active_factory(), save, day, target, seed=seed,
                                            camp_hold=target >= TWO_WAY_SLOTS))
    elif phase == "preseason":
        deadline = roster_deadline(start, save)
        if day >= (deadline - timedelta(days=1)).isoformat() and once(f"fill-final:{start}"):
            # A few clubs open with a place still open (23-28 of 30 opened with three in 2023-2026).
            teams = sorted(t["id"] for t in active_factory().get("teams", [])
                           if _hash(seed, start, t["id"], "leave-open") >= float(RULES["leave_open_rate"]))
            changed |= bool(ai_fill(active_factory(), save, day, TWO_WAY_SLOTS, seed=seed, teams=teams))
    elif phase == "regular_season":
        if once(f"ratings:{start}") or date.fromisoformat(day).weekday() == 0:
            active = active_factory()
            refresh_ratings(active, save)
            if date.fromisoformat(day).weekday() == 0:
                # Refill an empty place (until March 4) a week after it opened.
                if (int(day[:4]), int(day[5:7]), int(day[8:10])) <= (start + 1, *SIGNING_DEADLINE_MONTH_DAY):
                    open_since = root.setdefault("open_since", {})
                    ready = sorted(tid for tid, since in open_since.items() if since and
                                   (date.fromisoformat(day) - date.fromisoformat(since[:10])).days
                                   >= int(RULES["refill_after_days"]))
                    if ready and ai_fill(active, save, day, TWO_WAY_SLOTS, seed=seed, teams=ready):
                        changed = True
                    for tid in ready:
                        if open_places(save, tid) == 0:
                            open_since.pop(tid, None)
                if ai_promotions(active, save, day):
                    changed = True
        from .contract_protection import season_window
        first, last = season_window(save, season_label)
        if last and 0 <= (last - date.fromisoformat(day)).days <= int(RULES["playoff_eligibility_days"]) \
                and once(f"playoff-call:{start}"):
            if ai_promotions(active_factory(), save, day, final_call=True):
                changed = True
    return changed


# ---------------------------------------------------------------------------------------------------------------------
# New careers: the real 2026-27 opening two-ways

def seed_opening_two_ways(canonical: dict[str, Any], save: dict[str, Any]) -> set[str]:
    """A new career opens on October 20, 2026 with each team's real opening-night two-way players (the NBA's released
    lists, Codex's roster-edge evidence, ``data/research/roster_edge_2023_2026.json``: 83 players, all 30 teams).
    They are placed in the two-way places, not the 15 standard spots. Returns their ids."""
    import json
    from .resource_paths import game_resource_root
    from .utils import normalize_name
    path = game_resource_root() / "data/research/roster_edge_2023_2026.json"
    try:
        rows = json.loads(path.read_text()).get("decisions", {}).get("two_way_roster_snapshots") or []
    except (OSError, ValueError):
        return set()
    teams = {t.get("abbrev"): t["id"] for t in canonical.get("teams", [])}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for player in canonical.get("players", []):
        by_name.setdefault(normalize_name(player.get("name") or ""), []).append(player)
    season = str((save.get("meta") or {}).get("season") or "2026-27")
    placed: set[str] = set()
    root = store(save)
    for row in rows:
        if row.get("summer") != 2026 or row.get("stage") != "opening" or row.get("team") not in teams:
            continue
        team_id = teams[row["team"]]
        for item in row.get("players") or []:
            matches = by_name.get(normalize_name(item.get("player") or "")) or []
            if len(matches) != 1 or len(team_two_ways(save, team_id)) >= TWO_WAY_SLOTS:
                continue
            player = matches[0]
            pid = player["id"]
            root["contracts"][pid] = {
                "player_id": pid, "name": player.get("name"), "team_id": team_id,
                "signed_date": item.get("signed_date") or "2026-10-20", "how": "opening_roster", "by": "data",
                "seasons": [{"season": season, "salary": pay(season)}],
                "active_limit": {season: ACTIVE_GAME_LIMIT}, "active_games": {},
                "service": years_of_service(player, season)}
            history = root["history"].setdefault(pid, {}).setdefault(team_id, [])
            if season not in history:
                history.append(season)
            save.setdefault("roster_overrides", {})[pid] = None
            placed.add(pid)
    return placed


# ---------------------------------------------------------------------------------------------------------------------
# Views

def view_rows(active: dict[str, Any], save: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    season = current_season(save)
    players = _player_lookup(active)
    rows = []
    for rec in team_two_ways(save, team_id):
        player = players.get(rec["player_id"]) or {}
        limit = int((rec.get("active_limit") or {}).get(season, ACTIVE_GAME_LIMIT))
        rows.append({
            "player_id": rec["player_id"], "name": rec.get("name") or player.get("name"),
            "position": player.get("position"), "age": player.get("display_age", player.get("age")),
            "headshot_url": player.get("headshot_url"),
            "overall": round(overall(active, rec["player_id"]), 1),
            "seasons": [{"season": r["season"], "salary_millions": round(float(r["salary"]) / 1e6, 3)}
                        for r in rec.get("seasons") or []],
            "pay_words": "two-way pay, outside the salary cap",
            "active_games": active_games(rec, season), "active_limit": limit,
            "games_left": max(0, limit - active_games(rec, season)),
            "signed_date": rec.get("signed_date"), "how": rec.get("how"),
            "seasons_with_team": len(team_seasons(save, rec["player_id"], team_id)),
        })
    return rows


def opening_counts(active: dict[str, Any], save: dict[str, Any]) -> dict[str, Any]:
    teams = sorted(t["id"] for t in active.get("teams", []))
    counts = {tid: len(team_two_ways(save, tid)) for tid in teams}
    return {"teams_with_three": sum(1 for v in counts.values() if v >= 3), "two_way_players": sum(counts.values()),
            "by_team": counts}


def ceil_div(a: int, b: int) -> int:
    return int(math.ceil(a / b))
