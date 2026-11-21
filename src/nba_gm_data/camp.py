"""Training camp: Exhibit 10 camp deals, the 21-to-15 cutdown, and the thinning late market (FA-REAL slice 4).

The rules (2023 CBA Art. II §§3(r)-(s), 11(h), Art. VII §4(k), Art. XXIX, Exhibit A; research
``docs/agents/tasks/fa-realism-research.md``):

- **Exhibit 10** is a camp contract: one season at the player's minimum salary, not guaranteed. A team may carry six at
  once, within the 21-player offseason maximum (two-ways count toward the 21). Before opening day the team may convert
  it to a two-way contract. If the team waives him before opening day and he joins its G League affiliate (and stays
  60 days), he earns a bonus of up to about $91,000 (2026-27; grown with the cap after). The game records the bonus
  when he clears waivers and joins the affiliate (modelled simply: no 60-day check).
- **The cutdown:** teams carry up to 21 players through camp and must be down to at most 15 standard players and three
  two-ways by the roster deadline, the day before opening night (offseason_calendar.roster_deadline). Waivers last 48
  hours; a player waived two days before the deadline clears before opening night, so his non-guaranteed salary is never
  owed; a later cut owes the days until he clears (contract_protection.waiver_projection already prices this). Claims go
  by worst record (previous season through November 30), paid with cap room, the minimum or an exception (waivers.py).

AI behaviour, from Codex's 2023-2026 evidence (``docs/agents/tasks/roster-edge-evidence.md``): about seven or eight
camp deals per team each summer (median 7-8, range 0-12), signed in waves from August through camp, some waived early so
the affiliate gets their rights; at the cutdown "keep everyone except players on a known Exhibit 10 deal" (85% hit rate),
then depth and guaranteed money; very few camp signees open on the standard roster (0-1 a year on the same deal); about
one in three clubs converts one camp deal to a two-way (8-14 a year). Fringe veterans who go unsigned leave for overseas
clubs with a named reason, mostly limited-minute players (22-47 a summer).

Nothing here signs anyone onto a human team's roster.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

from .cap_rules import season_start
from .utils import stable_id

EXHIBIT_10_MAXIMUM = 6
AFFILIATE_BONUS_2026 = 91_000           # "about $91,000 in 2026-27" (the CBA's $75,000 base scaled with the cap)
GUARANTEE_DATE_MONTH_DAY = "01-10"      # standard contracts become guaranteed on January 10

RULES = {
    # Waves of AI camp invites (month-day, the roster total to fill to, how many camp deals to waive first). The waived
    # ones join the affiliate (their rights are what many camp deals are for). Together: about 7-8 deals a team.
    # Each wave keeps a team's best two camp deals and waives the rest to the affiliate first, then signs new ones.
    "invite_waves": (("07-16", 21, None), ("08-01", 21, 2), ("08-25", 21, 2), ("09-15", 21, 2), ("09-28", 21, None)),
    # Candidates: fringe free agents (a rotation player waits for a real offer).
    "invite_max_minutes": 15.0,
    "invite_max_age": 30.0,
    # At the cutdown a camp deal stays on the standard roster only if he is among the team's best N players (the same
    # deal made an opening standard roster 0-1 times a year: Horton-Tucker 2024, Diawara 2025).
    "keep_camp_deal_rank": 9,
    # The AI cutdown happens this many days before the deadline, so the cuts clear waivers before opening night.
    "cut_days_before_deadline": 2,
    # Overseas: an unsigned veteran with limited NBA minutes (under 14 a game) aged 24-33 leaves with this chance at
    # each pass (Aug 1, Sep 15). Calibrated on the evidence's 22-47 documented overseas movers a summer.
    "overseas_max_minutes": 14.0,
    "overseas_ages": (24.0, 33.0),
    "overseas_passes": ("08-01", "09-15"),
    "overseas_rate": 0.18,
}

# Real clubs that signed NBA free agents in 2023-2026 (Hoops Rumors overseas trackers), with the usual reason.
OVERSEAS_CLUBS = (
    ("Real Madrid", "Spain"), ("FC Barcelona", "Spain"), ("Panathinaikos", "Greece"), ("Olympiacos", "Greece"),
    ("Fenerbahce", "Turkey"), ("Anadolu Efes", "Turkey"), ("Hapoel Tel Aviv", "Israel"), ("Maccabi Tel Aviv", "Israel"),
    ("Bayern Munich", "Germany"), ("AS Monaco", "France"), ("Partizan", "Serbia"), ("Crvena zvezda", "Serbia"),
    ("Virtus Bologna", "Italy"), ("Olimpia Milano", "Italy"), ("Zalgiris", "Lithuania"), ("Melbourne United", "Australia"),
    ("Sydney Kings", "Australia"), ("Shanghai Sharks", "China"), ("Guangdong Southern Tigers", "China"),
    ("Alvark Tokyo", "Japan"), ("Dubai Basketball", "UAE"), ("Paris Basketball", "France"),
)
OVERSEAS_REASONS = (
    "a guaranteed contract and a starting role, which no NBA team offered",
    "more money than an NBA camp invite",
    "a bigger role than the end of an NBA bench",
    "a two-year guaranteed deal close to his NBA salary",
)


def _hash(*parts: Any) -> float:
    digest = hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def store(save: dict[str, Any]) -> dict[str, Any]:
    root = save.setdefault("camp", {})
    root.setdefault("version", 1)
    root.setdefault("signings", [])
    root.setdefault("bonuses", [])
    root.setdefault("conversions", [])
    root.setdefault("cuts", [])
    root.setdefault("submitted", {})
    root.setdefault("overseas", [])
    root.setdefault("passes", {})
    return root


def _today(save: dict[str, Any]) -> str:
    return str((save.get("state") or {}).get("current_date") or "")


def _season(save: dict[str, Any]) -> str:
    from .cap_ledger import cap_year
    return cap_year(save)


def affiliate_bonus(season: str) -> int:
    from .cap_ledger import scaled
    return scaled(AFFILIATE_BONUS_2026, season)


def is_camp_deal(save: dict[str, Any], player_id: str) -> bool:
    override = (save.get("contract_overrides") or {}).get(str(player_id)) or {}
    return bool(override.get("exhibit_10"))


def camp_deal_ids(save: dict[str, Any], team_id: str) -> list[str]:
    roster = save.get("roster_overrides") or {}
    return sorted(pid for pid, override in (save.get("contract_overrides") or {}).items()
                  if override and override.get("exhibit_10") and roster.get(pid) == team_id)


def opening_night(save: dict[str, Any]) -> str:
    """The next opening night: this season's if it is still ahead (preseason), else next season's."""
    from .offseason_calendar import opening_night as opening
    season = str((save.get("meta") or {}).get("season") or "2026-27")
    phase = str((save.get("state") or {}).get("phase") or "")
    start = season_start(season) if phase == "preseason" else season_start(season) + 1
    return opening(start, save).isoformat()


def roster_deadline(save: dict[str, Any]) -> str:
    return (date.fromisoformat(opening_night(save)) - timedelta(days=1)).isoformat()


def clear_by(save: dict[str, Any]) -> str:
    """The last day to waive a player so he clears waivers (48 hours) before opening night."""
    return (date.fromisoformat(opening_night(save)) - timedelta(days=2)).isoformat()


def camp_open(save: dict[str, Any], when: str | None = None) -> bool:
    """Camp deals can be signed from the new league year (July 1) until opening night."""
    when = str(when or _today(save))
    phase = str((save.get("state") or {}).get("phase") or "")
    if phase in {"regular_season", "play_in", "playoffs", "draft", "re_signing"}:
        return False
    if phase == "free_agency" and when[5:] < "07-01":
        return False
    return when < opening_night(save)


# ---------------------------------------------------------------------------------------------------------------------
# Signing a camp deal

def invite_quote(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], team_id: str,
                 when: str | None = None) -> dict[str, Any]:
    """Can this team sign him to a camp deal today? {ok, reason, payment, bonus}."""
    from . import two_way
    when = str(when or _today(save))
    pid = str(player.get("id"))
    if not camp_open(save, when):
        return {"ok": False, "reason": "Camp deals are signed between July 1 and opening night."}
    if pid not in set(save.get("free_agent_player_ids") or []):
        return {"ok": False, "reason": "He is not a free agent."}
    from .waivers import pending_ids
    from .offseason_decisions import restricted_player_ids
    if pid in pending_ids(save):
        return {"ok": False, "reason": "He is on waivers."}
    if pid in set(restricted_player_ids(save)) or pid in two_way.restricted_two_way_ids(save):
        return {"ok": False, "reason": "He is a restricted free agent; his team holds his rights."}
    if len(camp_deal_ids(save, team_id)) >= EXHIBIT_10_MAXIMUM:
        return {"ok": False, "reason": f"A team may carry {EXHIBIT_10_MAXIMUM} camp deals at once."}
    room = two_way.standard_room(active, save, team_id, when)
    if room["open"] <= 0:
        return {"ok": False, "reason": room["reason"]}
    season = _season(save)
    from .save import minimum_contract_payment
    from .cap_ledger import team_payroll
    payment = minimum_contract_payment(player, season, 1)
    payment["trade_eligible_date"] = None
    payroll = team_payroll(active, save, team_id, season, today=when)
    ceiling = payroll.get("hard_cap")
    if ceiling and payroll["apron_payroll"] + float(payment["amount"]) > float(ceiling["amount"]) + 1:
        return {"ok": False, "reason": f"Hard-capped at ${float(ceiling['amount']) / 1e6:.1f}M: even a camp deal counts "
                                       "on the payroll."}
    bonus = affiliate_bonus(season)
    return {"ok": True, "reason": "", "payment": payment, "bonus": bonus, "season": season,
            "salary_millions": round(float(payment["salary"]) / 1e6, 3),
            "words": (f"One season at his minimum (${float(payment['salary']) / 1e6:.2f}M), not guaranteed until "
                      f"January 10. Waive him before opening night and he can join your G League affiliate for a "
                      f"bonus of up to ${bonus / 1e3:,.0f}K; or convert it to a two-way before opening day.")}


def invite(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], team_id: str, *,
           when: str | None = None, by: str = "ai") -> dict[str, Any]:
    """Sign a camp deal (raises ValueError when not allowed)."""
    when = str(when or _today(save))
    quote = invite_quote(active, save, player, team_id, when)
    if not quote["ok"]:
        raise ValueError(quote["reason"])
    pid = str(player["id"])
    season = quote["season"]
    payment = quote["payment"]
    from .cap_ledger import commit, contract_seasons, contract_terms
    seasons = contract_seasons(payment, status="exhibit_10", guaranteed=False)
    for row in seasons:
        row["guarantee_date"] = f"{season_start(row['season']) + 1}-{GUARANTEE_DATE_MONTH_DAY}"
        row["guarantee_status"] = "non_guaranteed"
    save.setdefault("roster_overrides", {})[pid] = team_id
    save.setdefault("contract_overrides", {})[pid] = {
        "team_id": team_id, "seasons": seasons, "status": "exhibit_10", "original_contract_years": 1,
        "signed_season": season, "signed_date": when, **contract_terms(payment),
        "exhibit_10": {"bonus": quote["bonus"], "signed_date": when, "by": by}}
    commit(save, team_id, pid, payment, when)
    save["free_agent_player_ids"] = sorted(set(save.get("free_agent_player_ids") or []) - {pid})
    released = (save.get("released_free_agents") or {}).get(pid)
    if released and released.get("status") == "available":
        released.update(status="signed", signed_team_id=team_id, signed_date=when)
    for bid in save.get("free_agent_offers", []) or []:
        if bid.get("player_id") == pid and bid.get("status") == "active":
            bid["status"] = "player_signed_elsewhere"
            from .cap_ledger import release as release_bid
            release_bid(bid)
    row = {"player_id": pid, "name": player.get("name"), "team_id": team_id, "date": when, "season": season,
           "by": by, "salary": int(payment["salary"]), "bonus": quote["bonus"]}
    store(save)["signings"].append(row)
    save.setdefault("transaction_logs", []).append({
        "id": stable_id("transaction_log", "camp_signing", when, team_id, pid), "date": when,
        "transaction_type": "camp_signing", "proposal_id": stable_id("camp_signing", when, team_id, pid),
        "status": "applied_to_save_ledger", "teams": [team_id], "assets": {"player_id": pid, "name": player.get("name")},
        "evaluations": [], "source_ids": ["src_contract_market_config_v1"],
        "notes": "Exhibit 10 camp deal: one season at the minimum, not guaranteed."})
    return row


def convert_to_two_way(active: dict[str, Any], save: dict[str, Any], player_id: str, *, when: str | None = None,
                       by: str = "ai") -> dict[str, Any]:
    """Convert a camp deal (or, for the team's own drafted rookie this summer, his rookie deal) to a two-way before
    opening day (raises ValueError when not allowed)."""
    from . import two_way
    when = str(when or _today(save))
    pid = str(player_id)
    override = (save.get("contract_overrides") or {}).get(pid) or {}
    team_id = (save.get("roster_overrides") or {}).get(pid)
    if not team_id:
        raise ValueError("He is not on a roster.")
    if when >= opening_night(save):
        raise ValueError("A camp deal can be converted to a two-way only before opening day.")
    draft_pick = own_draft_pick(save, pid, team_id)
    if not override.get("exhibit_10") and not draft_pick:
        raise ValueError("Only a camp deal (Exhibit 10) or this summer's draft pick can become a two-way.")
    player = next((p for p in active.get("players", []) if p.get("id") == pid), None) or {"id": pid}
    how = "converted_camp_deal" if override.get("exhibit_10") else "draft"
    years = 1 if override.get("exhibit_10") else 2
    if not two_way.eligibility(save, player, team_id, two_way.current_season(save), years, today=when)["ok"]:
        years = 1
    rec = two_way.sign(save, player, team_id, years=years, how=how, when=when, by=by)
    if override.get("exhibit_10"):
        store(save)["conversions"].append({"player_id": pid, "name": player.get("name"), "team_id": team_id,
                                           "date": when, "season": two_way.current_season(save), "by": by})
    return rec


def own_draft_pick(save: dict[str, Any], player_id: str, team_id: str) -> dict[str, Any] | None:
    """This summer's draft pick of ``team_id`` still on his rookie deal (may be signed to a two-way instead)."""
    from . import two_way
    season = two_way.current_season(save)
    year = str(season_start(season))
    return next((r for r in save.get("incoming_rookies", []) or []
                 if r.get("player_id") == player_id and r.get("team_id") == team_id
                 and str(r.get("draft_year")) == year), None)


# ---------------------------------------------------------------------------------------------------------------------
# Waivers: the affiliate bonus

def record_affiliate_bonuses(save: dict[str, Any], day: str) -> int:
    """A camp-deal player waived before opening day who clears waivers joins his team's G League affiliate and is owed
    the bonus written into his deal (recorded, paid outside the salary cap). He stays a free agent for NBA purposes,
    with the affiliate noted, so any team can still sign him."""
    root = store(save)
    seen = {row["waiver_id"] for row in root["bonuses"]}
    camp_cuts = {row.get("waiver_id"): row for row in root["cuts"] if row.get("camp_deal") and row.get("waiver_id")}
    added = 0
    for entry in save.get("waiver_wire", []) or []:
        if entry.get("status") != "cleared" or entry.get("id") in seen:
            continue
        cut = camp_cuts.get(entry.get("id"))
        bonus = (cut or {}).get("bonus") or ((entry.get("contract") or {}).get("exhibit_10") or {}).get("bonus")
        if not bonus:
            continue
        pid = entry["player_id"]
        from .cap_ledger import years_of_service  # noqa: F401  (veterans rarely report to an affiliate)
        root["bonuses"].append({"waiver_id": entry["id"], "player_id": pid, "name": entry.get("player_name"),
                                "team_id": entry.get("team_id"), "date": entry.get("resolved_date") or day,
                                "bonus": int(bonus), "status": "joined_affiliate"})
        released = (save.get("released_free_agents") or {}).get(pid)
        if released is not None:
            released["affiliate_team_id"] = entry.get("team_id")
        added += 1
    return added


# ---------------------------------------------------------------------------------------------------------------------
# AI: camp invites and the cutdown

def _value(active: dict[str, Any], player_id: str) -> float:
    from . import two_way
    return two_way.overall(active, player_id)


def invite_candidates(active: dict[str, Any], save: dict[str, Any]) -> list[dict[str, Any]]:
    from .waivers import pending_ids
    from .offseason_decisions import restricted_player_ids
    from .save import display_minutes_projection, players_by_id_index
    from . import two_way
    players = players_by_id_index(active)
    blocked = pending_ids(save) | set(restricted_player_ids(save)) | two_way.restricted_two_way_ids(save)
    blocked |= set(save.get("retired_player_ids") or [])
    rows = []
    for pid in save.get("free_agent_player_ids") or []:
        player = players.get(pid)
        if not player or pid in blocked or player.get("_inactive_player"):
            continue
        age = float(player.get("display_age", player.get("age")) or 27.0)
        if age > float(RULES["invite_max_age"]) or display_minutes_projection(player) >= float(RULES["invite_max_minutes"]):
            continue
        rows.append(player)
    return rows


def invite_score(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], team_id: str, seed: int) -> float:
    """A camp invite goes to the fringe player a team wants a look at: his rating, prior NBA experience (the evidence's
    best single predictor of a camp deal turning into a two-way), youth, and a small team-specific taste."""
    rating = _value(active, player["id"])
    age = float(player.get("display_age", player.get("age")) or 25.0)
    nba = 1.5 if float(player.get("prior_minutes") or 0.0) > 0 else 0.0
    youth = max(0.0, 26.0 - age) * 0.3
    return rating + nba + youth + _hash(seed, team_id, player["id"], "camp-taste") * 3.0


def ai_invites(active: dict[str, Any], save: dict[str, Any], day: str, fill_to: int, keep: int | None, *,
               seed: int = 1) -> dict[str, int]:
    """One wave of AI camp invites: keep the best ``keep`` camp deals and waive the others (they join the affiliate;
    None: waive nobody), then sign camp deals until the roster reaches ``fill_to`` players (two-ways counted) or six
    camp deals."""
    from .save import human_controlled_team_ids
    from . import two_way
    humans = human_controlled_team_ids(save)
    signed = waived = 0
    pool = None
    taken: set[str] = set()
    for team in sorted(active.get("teams", []), key=lambda t: t["id"]):
        tid = team["id"]
        if tid in humans:
            continue
        camp = camp_deal_ids(save, tid)
        if keep is not None and len(camp) > int(keep):
            weakest = sorted(camp, key=lambda pid: (_value(active, pid), pid))[:len(camp) - int(keep)]
            for pid in weakest:
                if waive(active, save, pid, tid, day, reason="assigned to the affiliate before camp cuts"):
                    waived += 1
        while True:
            room = two_way.standard_room(active, save, tid, day)
            total = room["standard"] + room["two_way"]
            if total >= int(fill_to) or len(camp_deal_ids(save, tid)) >= EXHIBIT_10_MAXIMUM:
                break
            if pool is None:
                pool = invite_candidates(active, save)
            best = None
            for player in pool:
                if player["id"] in taken:
                    continue
                score = invite_score(active, save, player, tid, seed)
                if best is None or score > best[0]:
                    best = (score, player)
            if best is None:
                break
            player = best[1]
            taken.add(player["id"])
            try:
                invite(active, save, player, tid, when=day, by="ai")
                signed += 1
            except ValueError:
                continue
    return {"signed": signed, "waived": waived}


def waive(active: dict[str, Any], save: dict[str, Any], player_id: str, team_id: str, day: str, *,
          reason: str = "") -> dict[str, Any] | None:
    from .waivers import request_waiver
    from .save import players_by_id_index
    player = dict(players_by_id_index(active).get(player_id) or {})
    if not player:
        return None
    player["team_id"] = team_id
    # The view may be older than the save's books (today's earlier signings): read the contract from the save.
    override = (save.get("contract_overrides") or {}).get(player_id)
    view = active
    if override and not any(c.get("player_id") == player_id and c.get("seasons") == override.get("seasons")
                            for c in active.get("contracts", []) or []):
        view = {**active, "contracts": [c for c in active.get("contracts", []) if c.get("player_id") != player_id]
                + [{**override, "player_id": player_id, "id": stable_id("save_contract", player_id)}]}
    try:
        entry = request_waiver(view, save, player, team_id, day)
    except ValueError:
        return None
    store(save)["cuts"].append({"player_id": player_id, "name": player.get("name"), "team_id": team_id, "date": day,
                                "camp_deal": bool((override or {}).get("exhibit_10")), "reason": reason,
                                "waiver_id": entry.get("id"),
                                "bonus": int(((override or {}).get("exhibit_10") or {}).get("bonus") or 0),
                                "owed_millions": round(sum(float(r.get("salary") or 0) - float(r.get("earned_salary") or 0)
                                                           for r in entry.get("seasons") or []) / 1e6, 3)})
    from .save import add_news
    add_news(save, "roster_cut", f"{str(team_id).replace('team_', '').upper()} waived {player.get('name')}"
                                 f"{' (' + reason + ')' if reason else ''}.", date_value=day)
    save.setdefault("transaction_logs", []).append({
        "id": stable_id("transaction_log", "camp_cut", day, team_id, player_id), "date": day,
        "transaction_type": "roster_cut", "proposal_id": stable_id("camp_cut", day, team_id, player_id),
        "status": "applied_to_save_ledger", "teams": [team_id],
        "assets": {"player_id": player_id, "name": player.get("name"), "waived_by_team_id": team_id},
        "evaluations": [], "source_ids": ["src_contract_market_config_v1"], "notes": reason or "Camp cut."})
    return entry


def ai_cutdown(canonical: dict[str, Any], save: dict[str, Any], day: str) -> dict[str, int]:
    """Each AI team gets to at most 15 standard players: first it converts its best eligible camp deal to a two-way if a
    two-way place is open, then waives its camp deals (keeping one only if he is among its 13 best players), then, if
    still over 15, the players its roster-retention score values least (which already counts guaranteed money)."""
    from .save import (ai_roster_retention_score, canonical_with_save, human_controlled_team_ids,
                       roster_retention_context)
    from . import two_way
    humans = human_controlled_team_ids(save)
    active = canonical_with_save(canonical, save)
    counts = {"converted": 0, "waived_camp": 0, "waived_other": 0}
    context = None
    for team in sorted(active.get("teams", []), key=lambda t: t["id"]):
        tid = team["id"]
        if tid in humans:
            continue
        camp = camp_deal_ids(save, tid)
        # Convert the best eligible camp deal into an open two-way place.
        while camp and two_way.open_places(save, tid) > 0:
            eligible = [pid for pid in camp
                        if two_way.eligibility(save, next((p for p in active["players"] if p["id"] == pid), {"id": pid}),
                                               tid, two_way.current_season(save), 1, today=day)["ok"]]
            if not eligible:
                break
            best = max(eligible, key=lambda pid: (_value(active, pid), pid))
            try:
                convert_to_two_way(active, save, best, when=day, by="ai")
                counts["converted"] += 1
            except ValueError:
                break
            camp = [pid for pid in camp if pid != best]
        standard = two_way.standard_roster_ids(active, save, tid)
        if context is None:
            context = roster_retention_context(canonical, save)
        players = {p["id"]: p for p in context.get("players", [])}
        scores = {pid: ai_roster_retention_score(context, save, players[pid]) if pid in players else 0.0
                  for pid in standard}
        ranked = sorted(standard, key=lambda pid: (-scores[pid], pid))
        keep_line = set(ranked[:int(RULES["keep_camp_deal_rank"])])
        for pid in camp:
            if pid in keep_line and len(standard) <= two_way.STANDARD_ROSTER_MAXIMUM:
                continue
            if waive(active, save, pid, tid, day, reason="camp cut"):
                counts["waived_camp"] += 1
                standard = [p for p in standard if p != pid]
        over = len(standard) - two_way.STANDARD_ROSTER_MAXIMUM
        if over > 0:
            for pid in sorted(standard, key=lambda pid: (scores.get(pid, 0.0), pid))[:over]:
                if waive(active, save, pid, tid, day, reason="cut to reach the 15-player limit"):
                    counts["waived_other"] += 1
    return counts


# ---------------------------------------------------------------------------------------------------------------------
# The late market: overseas departures

def overseas_pass(active: dict[str, Any], save: dict[str, Any], day: str, *, seed: int = 1) -> list[dict[str, Any]]:
    """Unsigned veterans with limited NBA roles sign with clubs abroad (22-47 documented each summer, median age
    26-28, mostly limited-minute players). Each leaves with the club's name and his reason; he is out of the NBA pool."""
    from .save import display_minutes_projection, players_by_id_index
    from .waivers import pending_ids
    from .offseason_decisions import restricted_player_ids
    players = players_by_id_index(active)
    blocked = pending_ids(save) | set(restricted_player_ids(save)) | set(save.get("retired_player_ids") or [])
    low, high = RULES["overseas_ages"]
    gone = []
    for pid in sorted(save.get("free_agent_player_ids") or []):
        player = players.get(pid)
        if not player or pid in blocked:
            continue
        age = float(player.get("display_age", player.get("age")) or 27.0)
        minutes = display_minutes_projection(player)
        if not (low <= age <= high) or minutes >= float(RULES["overseas_max_minutes"]):
            continue
        if float(player.get("prior_minutes") or 0.0) <= 0 and not player.get("draft_year"):
            continue
        roll = _hash(seed, day[:4], pid, "overseas", day[5:])
        if roll >= float(RULES["overseas_rate"]):
            continue
        club, country = OVERSEAS_CLUBS[int(_hash(seed, pid, "club") * len(OVERSEAS_CLUBS)) % len(OVERSEAS_CLUBS)]
        reason = OVERSEAS_REASONS[int(_hash(seed, pid, "reason") * len(OVERSEAS_REASONS)) % len(OVERSEAS_REASONS)]
        row = {"id": stable_id("overseas", day, pid), "player_id": pid, "name": player.get("name"), "date": day,
               "club": club, "country": country, "reason": reason, "age": round(age, 1),
               "minutes_projection": minutes}
        gone.append(row)
    if gone:
        ids = {row["player_id"] for row in gone}
        save["free_agent_player_ids"] = sorted(set(save.get("free_agent_player_ids") or []) - ids)
        save["retired_player_ids"] = sorted(set(save.get("retired_player_ids") or []) | ids)
        save["league_exit_player_ids"] = sorted(set(save.get("league_exit_player_ids") or []) | ids)
        records = save.setdefault("league_exit_records", [])
        from .save import add_news
        for row in gone:
            records.append({**row, "reason": "signed_overseas", "reason_words": row["reason"],
                            "season": str((save.get("meta") or {}).get("season") or "")})
            store(save)["overseas"].append(row)
            add_news(save, "free_agency", f"{row['name']} signed with {row['club']} ({row['country']}): "
                                          f"{row['reason']}.", date_value=day)
    return gone


# ---------------------------------------------------------------------------------------------------------------------
# The daily hook

def daily(canonical: dict[str, Any], save: dict[str, Any], day: str, active_factory, *, seed: int = 1) -> bool:
    """Date-driven camp work (once per calendar day, from save.advance_lifecycle_to). True when rosters changed."""
    from .offseason_calendar import roster_deadline as deadline_for
    phase = str((save.get("state") or {}).get("phase") or "")
    season_label = str((save.get("meta") or {}).get("season") or "2026-27")
    start = season_start(season_label)
    root = store(save)
    done = root["passes"]
    changed = False
    md = day[5:]

    def once(key: str) -> bool:
        if done.get(key) is not None:
            return False
        done[key] = day
        return True

    if record_affiliate_bonuses(save, day):
        pass
    if phase in {"free_agency", "offseason", "training_camp"} and day[:4] == str(start + 1):
        for month_day, fill_to, keep in RULES["invite_waves"]:
            if md >= month_day and once(f"invite:{start + 1}:{month_day}"):
                result = ai_invites(active_factory(), save, day, fill_to, keep, seed=seed)
                changed |= bool(result["signed"] or result["waived"])
        for month_day in RULES["overseas_passes"]:
            if md >= month_day and once(f"overseas:{start + 1}:{month_day}"):
                changed |= bool(overseas_pass(active_factory(), save, day, seed=seed))
    if phase == "preseason":
        deadline = deadline_for(start, save)
        cut_day = (deadline - timedelta(days=int(RULES["cut_days_before_deadline"]))).isoformat()
        if day >= cut_day and once(f"cutdown:{start}"):
            counts = ai_cutdown(canonical, save, day)
            root.setdefault("cutdown_counts", {})[str(start)] = counts
            changed = True
        if day >= deadline.isoformat() and once(f"deadline:{start}"):
            # Anyone still over (a claim or a late signing): cut again on the deadline itself.
            ai_cutdown(canonical, save, day)
            submit_roster(save, None, day, auto=True)
            changed = True
    return changed


# ---------------------------------------------------------------------------------------------------------------------
# The user's opening roster

def roster_view(active: dict[str, Any], save: dict[str, Any], team_id: str) -> dict[str, Any]:
    """The 21-to-15 view: counts, deadlines, each player's guarantee and waiver-clear date, the two-way places."""
    from . import two_way
    today = _today(save)
    standard = two_way.standard_roster_ids(active, save, team_id)
    in_season = two_way.in_season_limits(save, today)
    deadline = roster_deadline(save)
    camp = set(camp_deal_ids(save, team_id))
    season = _season(save)
    return {
        "season": season,
        "standard_count": len(standard),
        "standard_limit": two_way.STANDARD_ROSTER_MAXIMUM,
        "two_way_count": len(two_way.team_two_ways(save, team_id)),
        "two_way_limit": two_way.TWO_WAY_SLOTS,
        "offseason_total": len(standard) + len(two_way.team_two_ways(save, team_id)),
        "offseason_limit": two_way.OFFSEASON_ROSTER_MAXIMUM,
        "camp_deal_count": len(camp),
        "camp_deal_limit": EXHIBIT_10_MAXIMUM,
        "in_season_limits": in_season,
        "roster_deadline": deadline,
        "opening_night": opening_night(save),
        "clear_by": clear_by(save),
        "two_ways": two_way.view_rows(active, save, team_id),
        "submitted": (store(save)["submitted"].get(season) or {}).get(team_id),
        "legal": len(standard) <= two_way.STANDARD_ROSTER_MAXIMUM and len(two_way.team_two_ways(save, team_id)) <= 3,
        "affiliate_bonus": affiliate_bonus(season),
    }


def guarantee_words(contract_seasons: list[dict[str, Any]], season: str, *, camp_deal: bool = False) -> dict[str, Any]:
    """This season's guarantee in plain words, from the contract the save holds."""
    row = next((r for r in contract_seasons or [] if r.get("season") == season and r.get("salary") is not None), None)
    if row is None:
        return {"kind": "none", "words": "No salary this season"}
    salary = float(row.get("salary") or 0.0)
    protected = row.get("guaranteed_salary")
    if protected is None and row.get("guarantee_status") in {"guaranteed", "fully_guaranteed"}:
        protected = salary
    if protected is None and row.get("guarantee_status") in {"non_guaranteed", "not_guaranteed", "exhibit_10"}:
        protected = 0.0
    if camp_deal:
        return {"kind": "camp", "words": "Camp deal: not guaranteed", "guaranteed": 0.0}
    if protected is None:
        return {"kind": "unknown", "words": "Guarantee unverified (counted in full)", "guaranteed": salary}
    protected = float(protected)
    if protected >= salary - 1:
        return {"kind": "full", "words": "Fully guaranteed", "guaranteed": salary}
    if protected <= 0:
        when = row.get("guarantee_date")
        return {"kind": "none", "words": f"Not guaranteed{' until ' + when if when else ''}", "guaranteed": 0.0}
    return {"kind": "partial", "words": f"${protected / 1e6:.2f}M guaranteed", "guaranteed": protected}


def submit_roster(save: dict[str, Any], team_id: str | None, day: str, *, auto: bool = False,
                  active: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Record a team's opening roster (the user's "Submit roster" step; AI teams and an unsubmitted legal user roster
    are submitted on the deadline)."""
    season = _season(save) if team_id else str((save.get("meta") or {}).get("season") or "")
    root = store(save)["submitted"].setdefault(season, {})
    if team_id is None:
        return None
    row = {"team_id": team_id, "date": day, "auto": auto}
    if active is not None:
        from . import two_way
        row["standard"] = len(two_way.standard_roster_ids(active, save, team_id))
        row["two_way"] = len(two_way.team_two_ways(save, team_id))
    root[team_id] = row
    return row


# ---------------------------------------------------------------------------------------------------------------------
# Roster minimums under a hard cap

def minimum_fits_hard_cap(active: dict[str, Any], save: dict[str, Any], team_id: str, player: dict[str, Any],
                          season: str) -> dict[str, Any]:
    """Can the team add a one-year minimum without passing a hard cap it triggered? {ok, payment, reason}."""
    from .save import minimum_contract_payment
    from .cap_ledger import team_payroll
    payment = minimum_contract_payment(player, season, 1)
    payroll = team_payroll(active, save, team_id, season)
    ceiling = payroll.get("hard_cap")
    if ceiling and payroll["apron_payroll"] + float(payment["amount"]) > float(ceiling["amount"]) + 1:
        return {"ok": False, "payment": payment,
                "reason": f"a minimum contract would pass its hard cap (${float(ceiling['amount']) / 1e6:.1f}M); "
                          "it must cut or trade salary first"}
    return {"ok": True, "payment": payment, "reason": ""}
