"""Offseason decisions (FA-REAL slice 2): options, early terminations, rookie-scale options and qualifying offers.

Plain words:
- An **option** is a final contract year that one side may keep or drop. A **player option** is the player's choice; a
  **team option** the team's; an **early termination** lets a veteran end his deal a year early.
- **Rookie-scale options** are the team options in the third and fourth years of a first-round pick's rookie deal.
  They are decided in the autumn before (October 31, or the next weekday).
- A **qualifying offer** is a one-year offer a team sends to its young free agent by June 29. It makes him a
  **restricted free agent**: the team keeps the right to keep him. He may sign it (a one-year bet on himself, then he
  is unrestricted), negotiate a longer deal, or wait until October 1.

Interim rule until offer sheets arrive (slice 3): a restricted free agent negotiates only with his own team, accepts
the qualifying offer, or waits; on October 1 an unsigned one accepts it. Other teams can't sign him.

Where the data comes from:
- Options are read from the contract data: the Basketball-Reference contract table already in the save
  (``contract_protection`` evidence, matched by season and salary) and the game's own rookie deals (``draft.py``).
  Options for seasons up to 2026-27 were decided in real life and count as exercised.
- Every number a decision uses is in ``RULES`` below. They are sized from the research's counts and named examples
  (``docs/agents/tasks/fa-realism-research.md``) and the CBA formulas; refit them when OFFSEASON-DECISIONS-EVIDENCE
  (``data/research/offseason_decisions_2023_2026.json``) is merged.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .offseason_calendar import (
    offseason_dates, rookie_option_deadline, season_label,
)

OPTION_TYPES = ("player_option", "team_option", "early_termination")
FIRST_DECIDED_SEASON = "2026-27"   # options for this season and earlier were decided in real life (exercised)

# ----------------------------------------------------------------------------------------------------------------------
# RULES: every threshold the AI uses for these decisions, in one place. Fitted by OFFSEASON-DECISIONS-EVIDENCE
# (main c19849b: docs/agents/tasks/offseason-decisions-evidence.md, data/research/offseason_decisions_2023_2026.json,
# scripts/research/offseason_decisions_fit.py), each rule checked by predicting one summer from the other three.
RULES: dict[str, dict[str, float]] = {
    # Player options (2023-26: 45 kept, 45 declined). Opt out when his market price is at least ``opt_out_ratio`` of
    # the option (the fits chose 0.8-1.1), with a lower bar at 30 and older; 51 of 90 right against 41 for the baseline.
    # The evidence is weak, so a close call (within ``close_band``) goes to context: full Bird rights with a team
    # that keeps its regulars tilts him to opt out and re-sign longer (Kyrie Irving 2025: $43M option for 3 years and
    # $119M); an injury into next season keeps him in (Lonzo Ball 2024).
    "player_option": {
        "opt_out_ratio": 0.95,
        "opt_out_ratio_30_plus": 0.85,
        "close_band": 0.10,
        "regular_minutes": 24.0,
    },
    # Veteran team options (2023-26: 63 exercised, 68 declined). Exercise when his market price is at least
    # ``exercise_value_ratio`` of the option (fits: 1.2-1.5), or when the year is cheap to keep and cut later (a
    # minimum-level salary); 76 of 131 right against 68.
    "team_option": {
        "exercise_value_ratio": 1.2,
        "cheap_salary_minimums": 1.5,     # an option at or below 1.5x his minimum salary is kept (cheap to cut)
    },
    # Rookie-scale options: the third year is kept almost always (116 of 120); the fourth is declined only for a
    # player under about ``decline_prior_minutes`` last season with replacement-level value (fits: 700-1,000 minutes).
    "rookie_option": {
        "decline_prior_minutes": 850.0,
        # "Replacement level" in the game: his market price is below the option salary (the room's asks for young
        # players start near $5M, so a minimum-based bar never fired: 0 of 46 declined in autumn 2026, real 10 of 59).
        "replacement_value_share": 1.0,
        "first_autumn_games": 60.0,          # a new career has no archived season: projected minutes x 60 games
    },
    # Qualifying offers, standard contracts (2023-26: 47 of 100 sent). Send one to a player who logged about
    # ``tender_prior_minutes`` last season (three folds chose 1,000, one 500), and to an injured rotation player
    # (Indiana and Isaiah Jackson after his Achilles injury); 74 of 100 right against 53. Two-way offers are slice 4.
    "qualifying_offer": {
        "tender_prior_minutes": 1000.0,
        "injured_rotation_minutes": 18.0,
        "regular_minutes": 24.0,          # a tendered regular is kept like a franchise player (KEEP-STARS budget)
        # The talks: his team offers his market price; he holds out for his price plus his belief in himself
        # (0 to 16%, more for 23 and younger), and gives up ``belief_fade`` of his price as the summer goes
        # (``RFA_STAGES``). Real restricted summers are slow (Kuminga and Giddey 2025 signed in late September;
        # Duren 2026 in October) and few take the one-year offer (0-2 a summer).
        "team_offer_share": 1.0,
        # When the owner won't pay his full price, the team offers less in steps (no lower than the qualifying offer)
        # and on October 1 he takes a multi-year deal worth at least ``deadline_take_share`` of his price rather than
        # the one-year offer (Kuminga 2025, Duren 2026 signed below their asks).
        "team_offer_steps": (1.0, 0.9, 0.8),
        "deadline_take_share": 0.75,
        "belief_max": 0.12,
        "belief_young_bonus": 0.04,       # 23 or younger
        "belief_fade": 0.20,
    },
}

# CBA Exhibit B: a first-round pick's qualifying offer adds a percentage of his fourth-year salary that rises with the
# draft slot, from about 30% (No. 1) to 50% (No. 30). Interpolated linearly (checked on 2024 offers: Patrick Williams,
# pick 4, 32.5%; Isaac Okoro, pick 5, 32.6%; Precious Achiuwa, pick 20, 44.4%). Approximation, labeled for refitting.
QO_ROOKIE_PCT_FIRST, QO_ROOKIE_PCT_LAST = 0.30, 0.50
QO_STANDARD_RAISE = 1.35            # other standard contracts: 135% of the previous salary ...
QO_MINIMUM_PLUS = 200_000           # ... or his new minimum plus $200,000, whichever is greater
STARTER_GAMES, STARTER_MINUTES = 41, 2000   # the starter criteria (year four; the year 3-4 average is not tracked)


def _season_start(season: str) -> int:
    return int(str(season)[:4])


def _m(value: float) -> str:
    return f"${float(value) / 1e6:.1f}M"


def store(save: dict[str, Any]) -> dict[str, Any]:
    root = save.setdefault("offseason_decisions", {})
    root.setdefault("options", {})
    root.setdefault("qualifying_offers", {})
    return root


def _key(season: str, player_id: str) -> str:
    return f"{season}:{player_id}"


def _today(save: dict[str, Any]) -> str:
    return str((save.get("state") or {}).get("current_date") or "")


def _user_team_ids(save: dict[str, Any]) -> set[str]:
    from .save import human_controlled_team_ids
    return set(human_controlled_team_ids(save))


def _hash_unit(*parts: Any) -> float:
    digest = hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:8]
    return int(digest, 16) / 0xFFFFFFFF


# ----------------------------------------------------------------------------------------------------------------------
# Options on contracts

def option_kind(player: dict[str, Any], row: dict[str, Any]) -> str | None:
    """'player_option', 'early_termination', 'team_option' or 'rookie_option' (a rookie-scale team option)."""
    kind = str(row.get("option_type") or "")
    if kind not in OPTION_TYPES:
        return None
    if kind == "team_option":
        try:
            years_in = _season_start(row["season"]) - int(player.get("draft_year") or 0)
        except (TypeError, ValueError):
            years_in = -1
        if int(player.get("draft_round") or 0) == 1 and years_in in (2, 3):
            return "rookie_option"
    return kind


def option_deadline(kind: str, season: str) -> str:
    """When the option for ``season`` must be decided."""
    start = _season_start(season)
    if kind == "rookie_option":
        return rookie_option_deadline(start - 1).isoformat()
    return offseason_dates(start)["decisions_deadline"]


def apply_contract_options(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    """Write option years and their decisions onto the contracts of a working league (``canonical_with_save``), so the
    screens, the cap math, waivers and trades all see the same contracts (rule 4).

    - Option years from the contract data (matched by season and salary) on contracts the save hasn't replaced.
    - Options for 2026-27 and earlier were decided in real life: exercised.
    - A decision taken in the game: exercised (the year is guaranteed) or declined (the contract ends before it)."""
    evidence = ((save.get("contract_protection") or {}).get("evidence") or {})
    decisions = (save.get("offseason_decisions") or {}).get("options") or {}
    if not evidence and not decisions:
        return
    overrides = save.get("contract_overrides") or {}
    by_player: dict[str, list[dict[str, Any]]] = {}
    for record in decisions.values():
        if record.get("status") in {"exercised", "declined"}:
            by_player.setdefault(str(record.get("player_id")), []).append(record)
    for contract in canonical.get("contracts", []) or []:
        pid = str(contract.get("player_id") or "")
        rows = contract.get("seasons") or []
        if pid not in overrides:
            proof = evidence.get(pid)
            if proof:
                by_season = {s.get("season"): s for s in proof.get("seasons") or []}
                for row in rows:
                    source = by_season.get(row.get("season")) or {}
                    if (source.get("option_type") in OPTION_TYPES and not row.get("option_type")
                            and source.get("salary") == row.get("salary")):
                        row["option_type"] = source["option_type"]
                        if str(row.get("season")) <= FIRST_DECIDED_SEASON:
                            row["option_exercised"] = True
                            row["option_decision"] = "exercised_before_the_game"
        for record in by_player.get(pid, []):
            target = next((row for row in rows if row.get("season") == record.get("season")
                           and row.get("option_type") and int(row.get("salary") or 0) == int(record.get("salary") or 0)), None)
            if target is None:
                continue
            if record["status"] == "exercised":
                target["option_exercised"] = True
                target["option_decision"] = "exercised"
                target["guaranteed_salary"] = target.get("salary")
            else:
                contract["seasons"] = [row for row in rows if str(row.get("season")) < str(record["season"])]
                contract["option_declined"] = {"season": record["season"], "kind": record.get("kind"),
                                               "salary": record.get("salary")}
                rows = contract["seasons"]


def contract_option_rows(active: dict[str, Any], player: dict[str, Any]) -> list[dict[str, Any]]:
    """The undecided option years on a player's current contract."""
    contract = next((c for c in active.get("contracts", []) if c.get("player_id") == player.get("id")), None) or {}
    out = []
    for row in contract.get("seasons") or []:
        kind = option_kind(player, row)
        if kind and not row.get("option_exercised") and row.get("salary") is not None:
            out.append({**row, "kind": kind})
    return out


def declined_rookie_option(save: dict[str, Any], player_id: str) -> dict[str, Any] | None:
    """A declined rookie-scale option: he becomes an unrestricted free agent, and his old team may pay him at most the
    option's salary in the first year (CBA Art. XI §1(e))."""
    return ((save.get("offseason_decisions") or {}).get("declined_rookie_options") or {}).get(player_id)


def record_option(save: dict[str, Any], player: dict[str, Any], row: dict[str, Any], kind: str, team_id: str | None,
                  status: str, by: str, reason: str, market: float | None = None) -> dict[str, Any]:
    record = {
        "player_id": player["id"], "name": player.get("name"), "team_id": team_id, "season": row["season"],
        "kind": kind, "salary": int(row.get("salary") or 0), "status": status, "decided_by": by,
        "reason": reason, "deadline": option_deadline(kind, row["season"]), "date": _today(save),
        "market_millions": round(float(market) / 1e6, 2) if market is not None else None,
    }
    root = store(save)
    root["options"][_key(row["season"], player["id"])] = record
    declined = root.setdefault("declined_rookie_options", {})
    if kind == "rookie_option" and status == "declined":
        declined[player["id"]] = record
    else:
        declined.pop(player["id"], None)
    return record


# ----------------------------------------------------------------------------------------------------------------------
# What a player is worth on the market (the same asks the free-agency room uses)

def market_values(active: dict[str, Any], save: dict[str, Any], canonical: dict[str, Any],
                  players: list[dict[str, Any]]) -> dict[str, float]:
    """Expected first-year market salary (dollars) per player: the free-agency room's opening ask."""
    if not players:
        return {}
    from .play import canonical_free_agent_market_by_id, free_agency_initial_ask, with_star_market_ask
    from .transactions import with_transaction_context
    priced = with_transaction_context(active)
    by_id = {p.get("id"): p for p in priced.get("players", [])}
    report = canonical_free_agent_market_by_id(canonical)
    out = {}
    for player in players:
        row = by_id.get(player["id"], player)
        try:
            market = with_star_market_ask(priced, save, row, report.get(player["id"]) or {})
            out[player["id"]] = float(free_agency_initial_ask(row, market)) * 1_000_000
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _minutes(player: dict[str, Any]) -> float:
    from .save import display_minutes_projection
    return float(display_minutes_projection(player))


def _age(player: dict[str, Any]) -> float:
    try:
        return float(player.get("display_age", player.get("age")) or 27.0)
    except (TypeError, ValueError):
        return 27.0


def injured_through_opening(save: dict[str, Any], player_id: str, season: str) -> bool:
    opening = offseason_dates(_season_start(season))["opening_night"]
    for state in save.get("health_states", []) or []:
        if state.get("player_id") == player_id and state.get("availability_status") == "out":
            return str(state.get("return_date") or "") > opening
    return False


def decide_player_option(save: dict[str, Any], player: dict[str, Any], row: dict[str, Any], market: float | None,
                         bird_level: str | None) -> tuple[str, str]:
    """(status, reason) for a player option or early termination: the player's own choice."""
    rules = RULES["player_option"]
    option = float(row.get("salary") or 0.0)
    age = _age(player)
    if injured_through_opening(save, player["id"], row["season"]):
        return "exercised", f"He is injured into next season, so he keeps his guaranteed {_m(option)}."
    if not market:
        return "exercised", f"He keeps his {_m(option)} option: no clear market for him."
    bar = option * (rules["opt_out_ratio_30_plus"] if age >= 30 else rules["opt_out_ratio"])
    regular_with_bird = bird_level == "full" and _minutes(player) >= rules["regular_minutes"]
    if market >= bar or (regular_with_bird and market >= bar * (1.0 - rules["close_band"])):
        why = (f"he expects about {_m(market)} a year on the market against his {_m(option)} option"
               + (", and a longer deal (his team holds his full Bird rights)" if market < option else ""))
        return "declined", f"He becomes a free agent: {why}."
    return "exercised", f"He keeps his {_m(option)} option: the market would pay him about {_m(market)}."


def decide_team_option_ai(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], row: dict[str, Any],
                          kind: str, market: float | None) -> tuple[str, str]:
    option = float(row.get("salary") or 0.0)
    value = float(market or 0.0)
    minutes = _minutes(player)
    del minutes
    from .cap_ledger import minimum_salary, years_of_service
    minimum = float(minimum_salary(row["season"], years_of_service(player, row["season"])))
    if kind == "rookie_option":
        rules = RULES["rookie_option"]
        try:
            fourth_year = _season_start(row["season"]) - int(player.get("draft_year") or 0) == 3
        except (TypeError, ValueError):
            fourth_year = False
        prior = prior_season_minutes(save, player["id"], player)
        if (fourth_year and prior < rules["decline_prior_minutes"]
                and value < option * rules["replacement_value_share"]):
            return "declined", (f"The team declines his {_m(option)} fourth-year option: {round(prior)} minutes last "
                                f"season and a replacement-level price (about {_m(value)}).")
        return "exercised", f"The team keeps his {_m(option)} rookie-scale option."
    rules = RULES["team_option"]
    if value >= option * rules["exercise_value_ratio"]:
        return "exercised", f"The team keeps him at {_m(option)}: he is worth about {_m(value)}, a bargain."
    if option <= minimum * rules["cheap_salary_minimums"]:
        return "exercised", f"The team keeps his cheap {_m(option)} year: it can still cut him later."
    return "declined", f"The team declines his {_m(option)} option: he is worth about {_m(value)}."


def prior_season_minutes(save: dict[str, Any], player_id: str, player: dict[str, Any] | None = None) -> float:
    """Minutes in the last completed regular season: this season's totals in the summer, the archived season in
    the autumn (the save starts a new season's totals at rollover)."""
    phase = str((save.get("state") or {}).get("phase") or "")
    if phase in {"re_signing", "draft", "free_agency", "offseason", "training_camp", "playoffs", "play_in"}:
        return float(((save.get("player_season_stats") or {}).get(player_id) or {}).get("minutes") or 0.0)
    history = save.get("season_history") or []
    if not history:
        # The first autumn of a new career: no archived season; his projected role over a season stands in.
        if player is not None:
            return _minutes(player) * RULES["rookie_option"]["first_autumn_games"]
        return float(((save.get("player_season_stats") or {}).get(player_id) or {}).get("minutes") or 0.0)
    return float(((history[-1].get("player_season_stats") or {}).get(player_id) or {}).get("minutes") or 0.0)


def decide_veteran_options(canonical: dict[str, Any], save: dict[str, Any], next_season: str) -> list[dict[str, Any]]:
    """At the start of stop 1 (the day the offseason opens): every player option and early termination for
    ``next_season`` is decided by the player, and AI teams decide their veteran team options. The user's team options
    wait for the user (deadline June 29). Returns the new records."""
    from .save import add_news, canonical_with_save
    active = canonical_with_save(canonical, save)
    users = _user_team_ids(save)
    taken = store(save)["options"]
    todo: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for player in active.get("players", []) or []:
        if not player.get("team_id"):
            continue
        for row in contract_option_rows(active, player):
            if row.get("season") != next_season or row["kind"] == "rookie_option":
                continue
            if _key(next_season, player["id"]) in taken:
                continue
            todo.append((player, row, row["kind"]))
    if not todo:
        return []
    values = market_values(active, save, canonical, [p for p, _, _ in todo])
    from .contract_ai import bird_rights
    expiring = season_label(_season_start(next_season) - 1)
    contracts = {c.get("player_id"): c for c in active.get("contracts", [])}
    made = []
    for player, row, kind in todo:
        team_id = player.get("team_id")
        market = values.get(player["id"])
        if kind in {"player_option", "early_termination"}:
            bird = bird_rights(save, player, team_id, expiring, contracts.get(player["id"]))
            status, reason = decide_player_option(save, player, row, market, bird.get("level"))
            record = record_option(save, player, row, kind, team_id, status, "player", reason, market)
        elif team_id in users:
            record = record_option(save, player, row, kind, team_id, "pending", "user",
                                   "Your decision: keep him for next season at this salary, or let him become a free agent.",
                                   market)
        else:
            status, reason = decide_team_option_ai(active, save, player, row, kind, market)
            record = record_option(save, player, row, kind, team_id, status, "team", reason, market)
        made.append(record)
        if record["status"] == "declined" and (market or 0) >= 8_000_000:
            add_news(save, "free_agency", f"{player.get('name')} becomes a free agent: "
                     f"{'he declined his' if record['decided_by'] == 'player' else 'his team declined the'} "
                     f"{_m(record['salary'])} option.", date_value=_today(save))
    return made


def decide_rookie_options(canonical: dict[str, Any], save: dict[str, Any], day: str) -> list[dict[str, Any]]:
    """Rookie-scale team options for next season, due October 31 (or the next weekday): AI teams decide on the deadline;
    the user's wait for the user (a stop on the deadline day). Runs on any day; does work only on or after the
    deadline of an undecided option."""
    from .save import canonical_with_save
    season = str((save.get("meta") or {}).get("season") or "")
    if not season:
        return []
    start = _season_start(season)
    deadline = rookie_option_deadline(start).isoformat()
    if str(day) < deadline or str(day) > f"{start + 1}-06-16":
        return []
    option_season = season_label(start + 1)
    taken = store(save)["options"]
    if store(save).get("rookie_options_done") == f"{option_season}:{'lapsed' if str(day) > deadline else 'ai'}":
        return []
    active = canonical_with_save(canonical, save)
    users = _user_team_ids(save)
    todo = []
    lapsed = []
    for player in active.get("players", []) or []:
        if not player.get("team_id"):
            continue
        for row in contract_option_rows(active, player):
            if row.get("season") != option_season or row["kind"] != "rookie_option" or _key(option_season, player["id"]) in taken:
                continue
            if player.get("team_id") in users:
                if str(day) > deadline:
                    lapsed.append((player, row))
            else:
                todo.append((player, row))
    made = []
    for player, row in lapsed:
        made.append(record_option(save, player, row, "rookie_option", player.get("team_id"), "declined", "default",
                                  f"Not exercised by {deadline}: the option lapsed (his deal ends after this season)."))
        from .save import add_news
        add_news(save, "contract", f"{player.get('name')}'s rookie-scale option lapsed: his deal ends after this season.",
                 date_value=str(day))
    if todo:
        values = market_values(active, save, canonical, [p for p, _ in todo])
        for player, row in todo:
            status, reason = decide_team_option_ai(active, save, player, row, "rookie_option", values.get(player["id"]))
            made.append(record_option(save, player, row, "rookie_option", player.get("team_id"), status, "team", reason,
                                      values.get(player["id"])))
    store(save)["rookie_options_done"] = f"{option_season}:{'lapsed' if str(day) > deadline else 'ai'}"
    return made


def user_pending_options(canonical: dict[str, Any], save: dict[str, Any], *, active: dict[str, Any] | None = None,
                         kinds: set[str] | None = None) -> list[dict[str, Any]]:
    """The user's team options waiting for a decision (veteran ones recorded at stop 1; rookie-scale ones due this
    autumn, listed from the contracts)."""
    from .save import canonical_with_save
    users = _user_team_ids(save)
    out = [dict(r) for r in store(save)["options"].values() if r.get("status") == "pending" and r.get("team_id") in users]
    season = str((save.get("meta") or {}).get("season") or "")
    if season and (kinds is None or "rookie_option" in kinds):
        start = _season_start(season)
        option_season = season_label(start + 1)
        today = _today(save)
        if today < f"{start + 1}-06-17":
            active = active if active is not None else canonical_with_save(canonical, save)
            taken = store(save)["options"]
            for player in active.get("players", []) or []:
                if player.get("team_id") not in users:
                    continue
                for row in contract_option_rows(active, player):
                    if row.get("season") == option_season and row["kind"] == "rookie_option" and _key(option_season, player["id"]) not in taken:
                        out.append({"player_id": player["id"], "name": player.get("name"), "team_id": player.get("team_id"),
                                    "season": option_season, "kind": "rookie_option", "salary": int(row.get("salary") or 0),
                                    "status": "pending", "decided_by": "user",
                                    "deadline": option_deadline("rookie_option", option_season),
                                    "reason": "Your decision: keep his rookie-scale option for next season, or let his "
                                              "deal end after next season (he would be an unrestricted free agent)."})
    if kinds is not None:
        out = [r for r in out if r.get("kind") in kinds]
    return sorted(out, key=lambda r: (r.get("deadline") or "", -int(r.get("salary") or 0)))


def user_decide_option(canonical: dict[str, Any], save: dict[str, Any], player_id: str, exercise: bool) -> dict[str, Any]:
    """The user keeps (exercises) or declines one of his team options. A declined veteran option during the offseason
    makes the player a free agent at once, with his team holding his Bird rights."""
    from .save import canonical_with_save
    pending = {r["player_id"]: r for r in user_pending_options(canonical, save)}
    record = pending.get(player_id)
    if record is None:
        return {"ok": False, "reason": "That option is not waiting for your decision."}
    active = canonical_with_save(canonical, save)
    player = next((p for p in active.get("players", []) if p.get("id") == player_id), None) or {"id": player_id}
    row = {"season": record["season"], "salary": record["salary"]}
    status = "exercised" if exercise else "declined"
    reason = (f"You kept him at {_m(record['salary'])} for {record['season']}." if exercise
              else f"You declined his {_m(record['salary'])} option.")
    saved = record_option(save, player, row, record["kind"], record.get("team_id"), status, "user", reason,
                          (record.get("market_millions") or 0) * 1e6 if record.get("market_millions") else None)
    if not exercise and record["kind"] != "rookie_option":
        make_free_agent_with_rights(save, player_id, str(record.get("team_id")))
    return {"ok": True, "option": saved}


def make_free_agent_with_rights(save: dict[str, Any], player_id: str, team_id: str) -> None:
    """His contract has ended this offseason: he leaves the roster for the free-agent pool and his team keeps his
    rights (what the June re-signing pass does for every expiring contract)."""
    from .save import add_re_signing_right
    season = str((save.get("meta") or {}).get("season") or "")
    add_re_signing_right(save, season, player_id, team_id)
    save.setdefault("roster_overrides", {})[player_id] = None
    pool = set(save.get("free_agent_player_ids") or [])
    pool.add(player_id)
    save["free_agent_player_ids"] = sorted(pool)


# ----------------------------------------------------------------------------------------------------------------------
# Qualifying offers

def _rookie_scale_fourth_year(pick: int) -> float:
    """The game's first-round scale (draft.py), fourth year, for pick ``pick`` (rookie deals are signed at it)."""
    from .draft import default_draft_model_config
    cfg = default_draft_model_config()["rookie_scale"]
    year_one = max(float(cfg["first_round_floor"]),
                   float(cfg["first_pick_year1_salary"]) * float(cfg["first_round_decay"]) ** max(0, pick - 1))
    return year_one * (1.0 + float(cfg["annual_raise"])) ** 3


def qo_rookie_pct(pick: int) -> float:
    pick = max(1, min(30, int(pick or 30)))
    return QO_ROOKIE_PCT_FIRST + (QO_ROOKIE_PCT_LAST - QO_ROOKIE_PCT_FIRST) * (pick - 1) / 29.0


def starter_criteria(save: dict[str, Any], player_id: str) -> bool:
    """41 starts or 2,000 minutes in the season just finished (the CBA's year-four test)."""
    totals = (save.get("player_season_stats") or {}).get(player_id) or {}
    return int(totals.get("games_started") or 0) >= STARTER_GAMES or float(totals.get("minutes") or 0.0) >= STARTER_MINUTES


def qualifying_offer_terms(save: dict[str, Any], player: dict[str, Any], contract: dict[str, Any] | None,
                           expiring_season: str) -> dict[str, Any]:
    """Whether his team can make him a restricted free agent, and the qualifying offer's amount (CBA Art. XI §1(e))."""
    from .cap_ledger import minimum_salary, true_max_salary, years_of_service
    next_season = season_label(_season_start(expiring_season) + 1)
    try:
        draft_year = int(player.get("draft_year") or 0)
    except (TypeError, ValueError):
        draft_year = 0
    credited = _season_start(expiring_season) - draft_year + 1 if draft_year else years_of_service(player, next_season)
    rows = [r for r in (contract or {}).get("seasons") or [] if r.get("salary") is not None]
    previous = float(next((r["salary"] for r in rows if str(r.get("season")) == str(expiring_season)),
                          rows[-1]["salary"] if rows else 0.0) or 0.0)
    first_round = int(player.get("draft_round") or 0) == 1
    pick = int(player.get("draft_position") or 30) if first_round else 0
    starter = starter_criteria(save, player["id"])
    base = {"player_id": player["id"], "name": player.get("name"), "season": next_season,
            "previous_salary": int(previous), "years_of_service": credited, "starter_criteria": starter}
    if declined_rookie_option(save, player["id"]):
        return {**base, "eligible": False, "reason": "His rookie-scale option was declined: he is unrestricted."}
    if first_round and credited == 4:
        amount = previous * (1.0 + qo_rookie_pct(pick))
        note = f"his fourth-year salary plus {round(qo_rookie_pct(pick) * 100)}% (pick {pick})"
        if starter and pick > 9:
            nine = _rookie_scale_fourth_year(9) * 1.2 * (1.0 + qo_rookie_pct(9))
            if nine > amount:
                amount, note = nine, "the No. 9 pick's offer: he met the starter criteria"
        elif not starter and pick <= 14:
            fifteen = _rookie_scale_fourth_year(15) * 1.2 * (1.0 + qo_rookie_pct(15))
            if fifteen < amount:
                amount, note = fifteen, "the No. 15 pick's offer: he missed the starter criteria"
        maximum = true_max_salary(next_season, credited)
        floor = minimum_salary(next_season, credited) + QO_MINIMUM_PLUS   # never below a standard offer's floor
        if amount < floor:
            amount, note = floor, "his minimum plus $200,000 (his rookie salary was below the scale)"
        return {**base, "eligible": True, "route": "rookie_scale", "amount": int(round(amount)), "basis": note,
                "max_qo_amount": int(round(maximum)), "max_qo_years": 5}
    if credited <= 3:
        minimum = minimum_salary(next_season, credited)
        amount = max(previous * QO_STANDARD_RAISE, minimum + QO_MINIMUM_PLUS)
        note = ("135% of his salary" if previous * QO_STANDARD_RAISE >= minimum + QO_MINIMUM_PLUS
                else "his minimum plus $200,000")
        if starter and not first_round and credited in (2, 3):
            twenty_one = _rookie_scale_fourth_year(21) * (1.0 + qo_rookie_pct(21))
            if twenty_one > amount:
                amount, note = twenty_one, "the No. 21 pick's offer: he met the starter criteria"
        return {**base, "eligible": True, "route": "standard", "amount": int(round(amount)), "basis": note}
    return {**base, "eligible": False, "reason": "Four or more years in the league: he is unrestricted."}


def qo_record(save: dict[str, Any], season: str, player_id: str) -> dict[str, Any] | None:
    return store(save)["qualifying_offers"].get(_key(season, player_id))


def ai_tender_choice(player: dict[str, Any], terms: dict[str, Any], market: float | None,
                     can_pay_market: bool = True, *, prior_minutes: float | None = None,
                     injured: bool = False) -> tuple[bool, str]:
    """An AI team's qualifying-offer choice (the evidence's rule): send one to a player who played about 1,000 minutes
    last season, or to an injured rotation player."""
    del can_pay_market, market
    rules = RULES["qualifying_offer"]
    amount = float(terms["amount"])
    minutes = float(prior_minutes if prior_minutes is not None else 0.0)
    if minutes >= rules["tender_prior_minutes"]:
        return True, (f"He played {round(minutes)} minutes last season: the {_m(amount)} offer keeps the right to "
                      "keep him.")
    if injured and _minutes(player) >= rules["injured_rotation_minutes"]:
        return True, f"An injured rotation player: the team keeps the right to keep him for {_m(amount)}."
    return False, (f"{round(minutes)} minutes last season: no qualifying offer ({_m(amount)}); he becomes an "
                   "unrestricted free agent.")


def prepare_qualifying_offers(canonical: dict[str, Any], save: dict[str, Any], active: dict[str, Any],
                              expiring: list[dict[str, Any]], next_season: str,
                              values: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Stop 1: record every expiring player who can be made a restricted free agent; AI teams tender or not now, the
    user's wait for the user (deadline June 29)."""
    from .save import add_news
    contracts = {c.get("player_id"): c for c in active.get("contracts", [])}
    expiring_season = season_label(_season_start(next_season) - 1)
    users = _user_team_ids(save)
    rows = []
    eligible = []
    for player in expiring:
        if qo_record(save, next_season, player["id"]):
            continue
        terms = qualifying_offer_terms(save, player, contracts.get(player["id"]), expiring_season)
        if terms.get("eligible"):
            eligible.append((player, terms))
    if not eligible:
        return []
    if values is None:
        values = market_values(active, save, canonical, [p for p, _ in eligible])
    deadline = offseason_dates(_season_start(next_season))["decisions_deadline"]
    for player, terms in eligible:
        team_id = player.get("team_id")
        record = {**terms, "team_id": team_id, "deadline": deadline, "date": _today(save),
                  "market_millions": round(values.get(player["id"], 0.0) / 1e6, 2)}
        if team_id in users:
            record.update(status="pending", decided_by="user",
                          reason="Your decision: send the qualifying offer to keep the right to keep him, or let him "
                                 "become an unrestricted free agent.")
        else:
            tender, reason = ai_tender_choice(
                player, terms, values.get(player["id"]), prior_minutes=prior_season_minutes(save, player["id"]),
                injured=injured_through_opening(save, player["id"], next_season)
                or any(s.get("player_id") == player["id"] and s.get("availability_status") == "out"
                       for s in save.get("health_states", []) or []))
            record.update(status="tendered" if tender else "not_tendered", decided_by="team", reason=reason)
            if tender and values.get(player["id"], 0.0) >= 10_000_000:
                add_news(save, "free_agency", f"{player.get('name')} receives a qualifying offer and becomes a "
                         "restricted free agent.", date_value=_today(save))
        store(save)["qualifying_offers"][_key(next_season, player["id"])] = record
        rows.append(record)
    return rows


def restricted_rights_team(save: dict[str, Any], player_id: str, season: str | None = None) -> str | None:
    """The team holding a restricted free agent (a live qualifying offer, rights not renounced), else None."""
    from .cap_ledger import cap_year
    season = season or cap_year(save)
    record = qo_record(save, season, player_id)
    if not record or record.get("status") != "tendered":
        return None
    team_id = record.get("team_id")
    meta = str((save.get("meta") or {}).get("season") or "")
    if not any(r.get("player_id") == player_id and r.get("team_id") == team_id and str(r.get("season")) == meta
               for r in save.get("re_signing_rights", []) or []):
        return None
    if player_id not in set(save.get("free_agent_player_ids") or []):
        return None
    return team_id


def restricted_player_ids(save: dict[str, Any]) -> dict[str, str]:
    """player_id -> rights team, for every live restricted free agent this offseason."""
    from .cap_ledger import cap_year
    season = cap_year(save)
    out = {}
    for record in store(save)["qualifying_offers"].values():
        if record.get("season") == season and record.get("status") == "tendered":
            team = restricted_rights_team(save, record["player_id"], season)
            if team:
                out[record["player_id"]] = team
    return out


def blocked_for_team(save: dict[str, Any], player_id: str, team_id: str | None) -> str | None:
    """Why ``team_id`` can't sign this player now (the interim restricted rule), else None."""
    holder = restricted_rights_team(save, player_id)
    if holder and holder != team_id:
        from .save import team_id_to_abbrev
        return (f"He is a restricted free agent: only {team_id_to_abbrev(holder)} can sign him (it sent him a qualifying "
                "offer). Offer sheets from other teams come later.")
    return None


def user_tender(save: dict[str, Any], player_id: str, tender: bool, *, maximum: bool = False) -> dict[str, Any]:
    from .cap_ledger import cap_year
    season = cap_year(save)
    record = qo_record(save, season, player_id)
    users = _user_team_ids(save)
    if not record or record.get("team_id") not in users:
        return {"ok": False, "reason": "He can't receive a qualifying offer from you."}
    if record.get("status") not in {"pending", "tendered", "not_tendered"}:
        return {"ok": False, "reason": "This qualifying offer is already settled."}
    if _today(save) > record.get("deadline", ""):
        return {"ok": False, "reason": "The June 29 deadline for qualifying offers has passed."}
    if tender:
        record.update(status="tendered", decided_by="user", date=_today(save),
                      maximum=bool(maximum and record.get("max_qo_amount")),
                      reason=f"You sent him a {_m(record['amount'])} qualifying offer: he is a restricted free agent.")
    else:
        record.update(status="not_tendered", decided_by="user", date=_today(save), maximum=False,
                      reason="No qualifying offer: he becomes an unrestricted free agent (you keep his Bird rights).")
    return {"ok": True, "qualifying_offer": dict(record)}


def withdraw_qualifying_offer(save: dict[str, Any], player_id: str) -> dict[str, Any]:
    """Pull a sent qualifying offer. Through July 13 the team keeps his Bird rights; later, withdrawing also gives up
    his rights (CBA Art. XI §4(c))."""
    from .cap_ledger import cap_year, renounce
    season = cap_year(save)
    record = qo_record(save, season, player_id)
    if not record or record.get("status") != "tendered":
        return {"ok": False, "reason": "There is no live qualifying offer to withdraw."}
    cutoff = offseason_dates(_season_start(season))["qualifying_offer_withdrawal"]
    record.update(status="withdrawn", date=_today(save))
    if _today(save) > cutoff:
        renounce(save, str(record.get("team_id")), player_id, by="qualifying_offer_withdrawn")
        record["reason"] = "Withdrawn after July 13: his rights are renounced too."
    else:
        record["reason"] = "Withdrawn: he is an unrestricted free agent; the team keeps his Bird rights."
    return {"ok": True, "qualifying_offer": dict(record)}


def accept_qualifying_offer(canonical: dict[str, Any], save: dict[str, Any], player_id: str, why: str) -> bool:
    """He signs his one-year qualifying offer with his team (a bet on himself; he is unrestricted next summer)."""
    from .cap_ledger import cap_year, commit, trade_eligible_date
    from .contract_ai import keep_bird_clock
    from .save import add_news, canonical_with_save, team_id_to_abbrev
    season = cap_year(save)
    record = qo_record(save, season, player_id)
    team_id = restricted_rights_team(save, player_id, season)
    if not record or not team_id:
        return False
    amount = int(record.get("amount") or 0)
    years = 1
    salaries = [amount]
    if record.get("maximum") and record.get("max_qo_amount"):
        years = int(record.get("max_qo_years") or 5)
        first = int(record["max_qo_amount"])
        salaries = [int(round(first * (1.0 + 0.08 * k))) for k in range(years)]
    start = _season_start(season)
    active = canonical_with_save(canonical, save)
    player = next((p for p in active.get("players", []) if p.get("id") == player_id), {"id": player_id})
    keep_bird_clock(save, player, team_id, season)
    today = _today(save)
    seasons = [{"season": season_label(start + k), "salary": s, "option_type": None,
                "guarantee_status": "qualifying_offer", "guaranteed_salary": s, "protection_basis": "negotiated"}
               for k, s in enumerate(salaries)]
    save.setdefault("contract_overrides", {})[player_id] = {
        "team_id": team_id, "seasons": seasons, "status": "qualifying_offer_accepted",
        "original_contract_years": years, "signed_season": season, "payment_route": "bird",
        "payment_label": "his qualifying offer", "salary_schedule": salaries, "cap_charges": salaries,
        "trade_eligible_date": trade_eligible_date(today, season),
    }
    save.setdefault("roster_overrides", {})[player_id] = team_id
    save["free_agent_player_ids"] = [pid for pid in save.get("free_agent_player_ids") or [] if pid != player_id]
    commit(save, team_id, player_id, {"route": "bird", "amount": salaries[0], "years": years, "season": season})
    record.update(status="accepted", date=today, reason=why)
    save.setdefault("transaction_logs", []).append({
        "id": f"transaction_log_qo_{season}_{player_id}", "date": today, "transaction_type": "qualifying_offer_accepted",
        "status": "applied_to_save_ledger", "teams": [team_id],
        "assets": {"player_id": player_id, "name": player.get("name"), "salary": salaries[0], "years": years},
        "notes": why,
    })
    add_news(save, "free_agent_signing", f"{player.get('name')} signs his qualifying offer with "
             f"{team_id_to_abbrev(team_id)}: {_m(salaries[0])} for one year.", date_value=today)
    for offer in save.get("free_agent_offers", []) or []:
        if offer.get("player_id") == player_id and offer.get("status") == "active":
            offer["status"] = "rejected_player_accepted_qualifying_offer"
    return True


def rfa_belief(save: dict[str, Any], player: dict[str, Any]) -> float:
    """How much more than his market price a restricted free agent believes he is worth (0 to about 16%), fixed per
    player and career."""
    rules = RULES["qualifying_offer"]
    seed = (save.get("meta") or {}).get("seed") or 1
    belief = rules["belief_max"] * _hash_unit(seed, player.get("id"), "rfa_belief")
    if _age(player) <= 23:
        belief += rules["belief_young_bonus"]
    return belief


# How far the summer has gone for a restricted free agent's talks (0 at the Finals, 1 on October 1).
RFA_STAGES = {"june": 0.25, "market_day": 0.05, "late_summer": 0.8, "deadline": 1.0}


def rfa_reservation(save: dict[str, Any], player: dict[str, Any], market: float, stage: float) -> float:
    """What he will take from his team: his market price plus his belief, less ``belief_fade`` of it as the summer
    goes (``stage`` from 0 to 1, ``RFA_STAGES``)."""
    rules = RULES["qualifying_offer"]
    return market * (1.0 + rfa_belief(save, player) - rules["belief_fade"] * max(0.0, min(1.0, stage)))


def rfa_market_price(save: dict[str, Any], player_id: str) -> float:
    """His price in dollars: today's ask in the free-agency room, else the market value recorded with his offer."""
    asks = (save.get("free_agency_state") or {}).get("player_asks_millions") or {}
    if asks.get(player_id):
        return float(asks[player_id]) * 1e6
    from .cap_ledger import cap_year
    record = qo_record(save, cap_year(save), player_id) or {}
    return float(record.get("market_millions") or 0.0) * 1e6


def restricted_market_day(canonical: dict[str, Any], save: dict[str, Any], day: int) -> int:
    """Each first-wave market day, AI teams and their unsigned restricted free agents talk again: the team offers his
    price, and he signs when it meets what he will take that day. Returns the number signed."""
    from .save import canonical_with_save
    held = {pid: team for pid, team in restricted_player_ids(save).items() if team not in _user_team_ids(save)}
    if not held:
        return 0
    stage = RFA_STAGES["june"] + RFA_STAGES["market_day"] * max(1, int(day))
    active = canonical_with_save(canonical, save)
    players = {p["id"]: p for p in active.get("players", [])}
    signed = 0
    for player_id, team_id in sorted(held.items()):
        player = players.get(player_id)
        market = rfa_market_price(save, player_id)
        if not player or not market:
            continue
        if rfa_negotiate(canonical, save, active, player, team_id, market, stage):
            signed += 1
            active = canonical_with_save(canonical, save)
            players = {p["id"]: p for p in active.get("players", [])}
    return signed


def restricted_summer_pass(canonical: dict[str, Any], save: dict[str, Any], *, final: bool) -> dict[str, int]:
    """Late summer (August 1) and the October 1 deadline for unsigned restricted free agents.

    - AI teams make their own offer (market price less a little leverage, through the cap calculator and the owner's
      payroll plan); he signs if it meets what he will take now.
    - On October 1 (``final``) anyone still unsigned accepts his qualifying offer.
    - Before that, a player whose team has made no offer at all and won't (it can't fit him) accepts it too."""
    from .save import canonical_with_save
    held = restricted_player_ids(save)
    if not held:
        return {"signed": 0, "accepted_qualifying_offers": 0}
    users = _user_team_ids(save)
    active = canonical_with_save(canonical, save)
    players = {p["id"]: p for p in active.get("players", [])}
    stage = RFA_STAGES["deadline" if final else "late_summer"]
    signed = accepted = 0
    for player_id, team_id in sorted(held.items()):
        player = players.get(player_id) or {"id": player_id}
        market = rfa_market_price(save, player_id)
        offer = market * RULES["qualifying_offer"]["team_offer_share"]
        if team_id not in users and market and rfa_negotiate(canonical, save, active, player, team_id, market, stage,
                                                              final=final):
            signed += 1
            active = canonical_with_save(canonical, save)
            players = {p["id"]: p for p in active.get("players", [])}
            continue
        if final:
            if accept_qualifying_offer(canonical, save, player_id,
                                       "No long-term deal by October 1: he takes the one-year qualifying offer."):
                accepted += 1
            continue
        if team_id in users or not market:
            continue
        if not rfa_team_can_pay(active, save, player, team_id, offer):
            if accept_qualifying_offer(canonical, save, player_id,
                                       "His team could not fit a long-term deal: he takes the one-year qualifying "
                                       "offer and bets on himself."):
                accepted += 1
    return {"signed": signed, "accepted_qualifying_offers": accepted}


def rfa_negotiate(canonical: dict[str, Any], save: dict[str, Any], active: dict[str, Any], player: dict[str, Any],
                  team_id: str, market: float, stage: float, *, final: bool = False) -> bool:
    """One round of talks between an AI team and its restricted free agent: the team offers his price, or less in
    steps when its owner won't pay that much (never below the qualifying offer); he signs when an offer reaches what
    he will take now (on October 1: at least ``deadline_take_share`` of his price, else the one-year offer)."""
    from .cap_ledger import cap_year
    rules = RULES["qualifying_offer"]
    record = qo_record(save, cap_year(save), player["id"]) or {}
    floor = float(record.get("amount") or 0.0)
    want = rfa_reservation(save, player, market, stage)
    if final:
        want = min(want, max(floor, market * rules["deadline_take_share"]))
    for share in rules["team_offer_steps"]:
        price = max(floor, market * share * rules["team_offer_share"])
        if price < want:
            break
        if rfa_team_signs(canonical, save, active, player, team_id, price):
            return True
    return False


def rfa_team_can_pay(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], team_id: str,
                     salary: float) -> bool:
    from .cap_ledger import cap_year, incumbent_bird, quote
    bird = incumbent_bird(active, save, player, team_id)
    result = quote(active, save, team_id, player, salary, 3, season=cap_year(save), bird=bird, include_reservations=False)
    return bool(result.get("ok"))


def rfa_team_signs(canonical: dict[str, Any], save: dict[str, Any], active: dict[str, Any], player: dict[str, Any],
                   team_id: str, salary: float) -> bool:
    """An AI team signs its restricted free agent at ``salary`` (dollars) through the free-agency signing path."""
    from .play import build_free_agency_offer_record, ai_bid_payment, apply_free_agency_offer_state
    from .cap_ledger import incumbent_bird, reserve
    team = next((t for t in active.get("teams", []) if t.get("id") == team_id), {"id": team_id})
    bird = incumbent_bird(active, save, player, team_id)
    years = 4 if _age(player) <= 26 else 3
    paid = ai_bid_payment(active, save, team, player, round(salary / 1e6, 1), years, 1.0, bird)
    if paid is None:
        return False
    offer = build_free_agency_offer_record(active, save, player, team, paid["years"], paid["aav"],
                                           paid["aav"], int((save.get("meta") or {}).get("seed") or 1), "ai")
    offer["restricted_re_signing"] = True
    reserve(offer, paid["quote"]["payment"])
    save.setdefault("free_agent_offers", []).append(offer)
    result = apply_free_agency_offer_state(canonical, save, offer["id"], int((save.get("meta") or {}).get("seed") or 1),
                                           prepared_active=active)
    if result.get("status") == "applied":
        mark_signed(save, player["id"], team_id)
        return True
    if offer.get("status") == "active":
        offer["status"] = "withdrawn"
    return False


def mark_signed(save: dict[str, Any], player_id: str, team_id: str | None) -> None:
    """A restricted free agent signed a new contract (any path): his qualifying offer is settled."""
    from .cap_ledger import cap_year
    record = qo_record(save, cap_year(save), player_id)
    if record and record.get("status") in {"tendered", "pending"}:
        record.update(status="signed", date=_today(save),
                      reason="He signed a new contract with his team." if team_id == record.get("team_id")
                      else "He signed elsewhere.")


def finalize_stop_one(canonical: dict[str, Any], save: dict[str, Any]) -> list[str]:
    """When stop 1 closes (the market opens): the user's undecided items take their default (a team option lapses:
    declined; no qualifying offer). Returns plain sentences for the news."""
    notes = []
    from .cap_ledger import cap_year
    season = cap_year(save)
    for record in user_pending_options(canonical, save, kinds={"team_option"}):
        result = user_decide_option(canonical, save, record["player_id"], False)
        if result.get("ok"):
            notes.append(f"{record.get('name')}'s team option lapsed: he is a free agent.")
    users = _user_team_ids(save)
    for record in store(save)["qualifying_offers"].values():
        if record.get("season") == season and record.get("team_id") in users and record.get("status") == "pending":
            record.update(status="not_tendered", decided_by="default", date=_today(save),
                          reason="No qualifying offer was sent by June 29: he is an unrestricted free agent.")
            notes.append(f"{record.get('name')} received no qualifying offer: he is unrestricted.")
    return notes


# ----------------------------------------------------------------------------------------------------------------------
# The user's checklists

def stop_one_checklist(canonical: dict[str, Any], save: dict[str, Any], team_id: str,
                       active: dict[str, Any] | None = None) -> dict[str, Any]:
    """Stop 1, "decide who to keep": one list sorted by deadline (options, qualifying offers, own free agents with
    Bird rights, cap holds), plus the dates around it."""
    from .cap_ledger import cap_year, incumbent_bird, team_payroll
    from .contract_ai import bird_rights_text
    from .save import canonical_with_save
    active = active if active is not None else canonical_with_save(canonical, save)
    season = cap_year(save)
    end_year = _season_start(season)
    dates = offseason_dates(end_year, save)
    players = {p["id"]: p for p in active.get("players", [])}
    items: list[dict[str, Any]] = []
    for record in user_pending_options(canonical, save, active=active):
        if record.get("team_id") != team_id:
            continue
        items.append({"kind": "team_option" if record["kind"] != "rookie_option" else "rookie_option",
                      "player_id": record["player_id"], "name": record.get("name"), "deadline": record["deadline"],
                      "salary_millions": round(record["salary"] / 1e6, 2), "season": record["season"],
                      "market_millions": record.get("market_millions"), "status": "pending",
                      "text": record.get("reason"), "default": "Declined if you do nothing."})
    for record in store(save)["options"].values():
        if record.get("team_id") == team_id and record.get("season") == season and record.get("decided_by") == "player":
            items.append({"kind": "player_option_result", "player_id": record["player_id"], "name": record.get("name"),
                          "deadline": record["deadline"], "salary_millions": round(record["salary"] / 1e6, 2),
                          "status": record["status"], "text": record.get("reason"), "season": record["season"]})
        elif (record.get("team_id") == team_id and record.get("season") == season and record.get("decided_by") == "user"
              and record.get("status") in {"exercised", "declined"}):
            items.append({"kind": "team_option", "player_id": record["player_id"], "name": record.get("name"),
                          "deadline": record["deadline"], "salary_millions": round(record["salary"] / 1e6, 2),
                          "status": record["status"], "text": record.get("reason"), "season": record["season"]})
    for record in store(save)["qualifying_offers"].values():
        if record.get("team_id") != team_id or record.get("season") != season:
            continue
        items.append({"kind": "qualifying_offer", "player_id": record["player_id"], "name": record.get("name"),
                      "deadline": record["deadline"], "status": record.get("status"),
                      "amount_millions": round(float(record.get("amount") or 0) / 1e6, 2),
                      "basis": record.get("basis"), "route": record.get("route"),
                      "max_qo_millions": round(float(record.get("max_qo_amount") or 0) / 1e6, 2) or None,
                      "market_millions": record.get("market_millions"), "text": record.get("reason"),
                      "maximum": bool(record.get("maximum")),
                      "default": "No offer if you do nothing: he becomes unrestricted."})
    meta_season = str((save.get("meta") or {}).get("season") or "")
    qo_ids = {i["player_id"] for i in items if i["kind"] == "qualifying_offer" and i.get("status") == "tendered"}
    payroll = team_payroll(active, save, team_id, season)
    holds = {h["player_id"]: h for h in payroll.get("holds") or []}
    for right in save.get("re_signing_rights", []) or []:
        pid = right.get("player_id")
        if right.get("team_id") != team_id or str(right.get("season")) != meta_season or pid not in players:
            continue
        if players[pid].get("team_id"):
            continue
        bird = incumbent_bird(active, save, players[pid], team_id)
        hold = holds.get(pid)
        items.append({"kind": "own_free_agent", "player_id": pid, "name": players[pid].get("name"),
                      "deadline": dates["market_opens"], "status": "restricted" if pid in qo_ids else "free_agent",
                      "bird_level": (bird or {}).get("level"), "text": bird_rights_text(bird) if bird else
                      "You gave up his rights: you can sign him only with cap room or an exception.",
                      "hold_millions": round(float(hold["amount"]) / 1e6, 2) if hold else None,
                      "default": "Other teams can talk to him from June 30."})
    items.sort(key=lambda i: (i.get("deadline") or "", {"team_option": 0, "rookie_option": 0, "qualifying_offer": 1,
                                                        "player_option_result": 2, "own_free_agent": 3}.get(i["kind"], 4),
                              str(i.get("name") or "")))
    pending = sum(1 for i in items if i.get("status") == "pending")
    return {"season": season, "dates": dates, "items": items, "pending_count": pending,
            "cap_room_millions": round(float(payroll.get("cap_room") or 0) / 1e6, 2),
            "holds_millions": round(sum(float(h["amount"]) for h in holds.values()) / 1e6, 2)}


def stop_four_checklist(canonical: dict[str, Any], save: dict[str, Any], team_id: str,
                        active: dict[str, Any] | None = None) -> dict[str, Any]:
    """Stop 4, "set the roster": the count to get to 15, rookie-scale extensions (due the day before opening night),
    rookie options (due October 31 or the next weekday), and restricted free agents still waiting."""
    from .save import ROSTER_SEASON_MAXIMUM, canonical_with_save
    active = active if active is not None else canonical_with_save(canonical, save)
    season = str((save.get("meta") or {}).get("season") or "")
    start = _season_start(season)
    roster = [p for p in active.get("players", []) if p.get("team_id") == team_id]
    extension_ids = rookie_extension_candidates(active, save, team_id)
    items = []
    deadline = offseason_dates(start, save)["roster_deadline"]
    items.append({"kind": "roster", "deadline": deadline, "count": len(roster), "target": ROSTER_SEASON_MAXIMUM,
                  "status": "pending" if len(roster) > ROSTER_SEASON_MAXIMUM else "done",
                  "text": f"{len(roster)} players: cut to {ROSTER_SEASON_MAXIMUM} by {deadline}."})
    for pid in extension_ids:
        player = next((p for p in roster if p["id"] == pid), {})
        items.append({"kind": "rookie_extension", "player_id": pid, "name": player.get("name"), "deadline": deadline,
                      "status": "open", "text": "Entering the last year of his rookie deal: extend him by the deadline, "
                                                "or he becomes a restricted free agent next summer."})
    for record in user_pending_options(canonical, save, active=active, kinds={"rookie_option"}):
        if record.get("team_id") == team_id:
            items.append({"kind": "rookie_option", "player_id": record["player_id"], "name": record.get("name"),
                          "deadline": record["deadline"], "status": "pending",
                          "salary_millions": round(record["salary"] / 1e6, 2), "season": record["season"],
                          "text": record.get("reason")})
    items.sort(key=lambda i: (i.get("deadline") or "", i["kind"]))
    return {"season": season, "items": items, "roster_deadline": deadline,
            "rookie_option_deadline": rookie_option_deadline(start).isoformat(),
            "pending_count": sum(1 for i in items if i.get("status") == "pending")}


def rookie_extension_candidates(active: dict[str, Any], save: dict[str, Any], team_id: str) -> list[str]:
    """First-round picks entering the fourth and last year of their rookie deal (extendable until the day before
    opening night)."""
    season = str((save.get("meta") or {}).get("season") or "")
    start = _season_start(season)
    contracts = {c.get("player_id"): c for c in active.get("contracts", [])}
    out = []
    for player in active.get("players", []):
        if player.get("team_id") != team_id or not is_rookie_scale_final_year(player, contracts.get(player["id"]), start):
            continue
        out.append(player["id"])
    return out


def is_rookie_scale_final_year(player: dict[str, Any], contract: dict[str, Any] | None, season_start: int) -> bool:
    """A first-round pick in the fourth season of his rookie deal (the deal ends with this season)."""
    try:
        draft_year = int(player.get("draft_year") or 0)
    except (TypeError, ValueError):
        return False
    if int(player.get("draft_round") or 0) != 1 or season_start - draft_year != 3:
        return False
    last = max((str(r.get("season")) for r in (contract or {}).get("seasons") or [] if r.get("salary") is not None),
               default="")
    return last == season_label(season_start)
