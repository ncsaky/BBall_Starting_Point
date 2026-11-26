"""Franchise ties, championship rings and stated motives for free agents (COACHES-FREE-AGENTS, 2026-11-26).

The user's rule: loyal players should usually stay with the team they are tied to, a franchise icon most of all,
unless a clear motive outweighs it, and when a player does leave the game says why ("chasing his first championship").

- **Tie** to a team: seasons there (real career plus every simulated season), whether it drafted him, and whether he
  was a scorer there. An *icon* is a long-time star of the franchise; a *loyal* player has real roots there.
- **Rings**: real champions since 2003-04 (data/research/nba_champions.json) plus champions of simulated seasons.
- **Motives**: a title chase for a veteran (above all one without a ring), a much bigger contract, a bigger role, a
  poor fit, a rebuilding team, or his old team making no offer.

``save["franchise_ledger"]`` keeps one small row per simulated season (each player's last team, the scorers and the
champion), because older season stats move out of the save file (season_archive). ``save["free_agent_origins"]``
remembers whom each expiring player left, so the signing news can name the team and the reason.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .resource_paths import game_resource_root

LEDGER_KEY = "franchise_ledger"
ORIGIN_KEY = "free_agent_origins"

STAR_PPG = 18.0                # a season this big makes him a star in that team's memory
STAR_MIN_GAMES = 20
ICON_LONG_SEASONS = 10         # this long with one team makes him an icon on tenure alone
ICON_STAR_SEASONS = 8          # a star with this many seasons there is an icon
ICON_HOMEGROWN_SEASONS = 7     # a homegrown player needs one season fewer if he has starred there this often
ICON_HOMEGROWN_STAR_SEASONS = 4
LOYAL_SEASONS = 5
LOYAL_HOMEGROWN_SEASONS = 3

# Context points (free_agency_offer_context_score) a player gives the team he is tied to, on top of the 8-14 every
# own team already gets. One point is 0.42 interest points; interest also counts 52 for salary at his full price, so
# 10 points weigh like about 8% of his asking salary.
TENURE_POINTS_PER_SEASON = 1.5
TENURE_POINTS_CAP = 9.0
ICON_POINTS = 14.0
REBUILD_LOYALTY_SHARE = 0.5    # a veteran on a rebuilding team feels half the pull
REBUILD_AGE = 29.0

# Title chase: context points for an outside team that is a better shot at a ring than his old team.
CHASE_AGE = 32.0               # a ringless star starts looking
CHASE_LATE_AGE = 34.0          # now or never
ANOTHER_RING_AGE = 35.0
CHASE_POINTS = {               # (profile) -> {contender level: points}; level 2 is the defending champion
    "ringless_star_late": {2: 30.0, 1: 20.0},
    "ringless_star": {2: 20.0, 1: 12.0},
    "ringless_veteran": {2: 14.0, 1: 10.0},
    "another_ring": {2: 10.0, 1: 6.0},
}
CONTENDER_WIN_PCT = 0.60

MUCH_MORE_MONEY = 1.15         # first-year salary against his old team's best offer
BIGGER_ROLE_MINUTES = 5.0
BENCHED_MINUTES = 15.0         # played under this last season and gets BIGGER_ROLE_MINUTES+3 more: a poor fit
# Motives strong enough to take a loyal player away from a live offer by the team he is tied to.
CLEAR_MOTIVES = frozenset({"ring_chase", "no_offer", "bigger_contract", "bigger_role", "poor_fit", "rebuilding"})
# A loyal player takes his own team's offer slightly below his usual bar for the day.
ICON_THRESHOLD_DISCOUNT = 8.0
LOYAL_THRESHOLD_DISCOUNT = 4.0

# June (should_ai_retain_expiring_player): a ringless veteran icon on a team that is not contending tests the market
# about half the time instead of re-signing at once.
ICON_CHASE_TEST_AGE = 33.0
ICON_CHASE_TEST_CHANCE = 0.5
ICON_KEEP_MINUTES = 12.0
ICON_KEEP_MAX_AGE = 40.0
LOYAL_KEEP_BONUS = 0.12        # added to the ordinary June keep chance
# His own team's July bid may fall this far below his price (a hometown discount he will at least hear).
ICON_BID_FLOOR_SHARE = 0.65


def _abbrev(team_id: str | None) -> str:
    return str(team_id or "").replace("team_", "").upper()


def _age(player: dict[str, Any]) -> float:
    return float(player.get("display_age", player.get("age")) or 27.0)


@lru_cache(maxsize=1)
def real_champions() -> dict[str, str]:
    path = game_resource_root() / "data/research/nba_champions.json"
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")).get("champions") or {})
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=2)
def _playoff_teams(path: str, modified: int) -> dict[str, dict[str, str]]:
    from .research import ESPN_TEAM_ID_TO_ABBREV
    records = json.loads(Path(path).read_text(encoding="utf-8")).get("players", {})
    out: dict[str, dict[str, str]] = {}
    for espn_id, row in records.items():
        seasons = {}
        for season in (row.get("playoffs") or {}).get("seasons", []):
            teams = season.get("team_ids") or []
            if teams and season.get("games"):
                seasons[str(season.get("season"))] = ESPN_TEAM_ID_TO_ABBREV.get(str(teams[-1]), "")
        out[str(espn_id)] = seasons
        out.setdefault(str(row.get("name", "")).casefold(), seasons)
    return out


def _real_playoffs(player: dict[str, Any]) -> tuple[dict[str, str] | None, str]:
    """His real playoff teams by season (None when the playoff file lacks him) and that file's first season."""
    path = game_resource_root() / "data/research/player_playoff_stats.json"
    if not path.exists():
        return None, "9999"
    table = _playoff_teams(str(path), path.stat().st_mtime_ns)
    row = table.get(str(player.get("espn_player_id")))
    if row is None:
        row = table.get(str(player.get("name", "")).casefold())
    return row, "2013-14"


def _career_seasons(player: dict[str, Any]) -> list[dict[str, Any]]:
    """Real regular seasons: ``{season, teams (abbreviations, in order), ppg, games}``."""
    from .career_stats import career_record
    from .research import ESPN_TEAM_ID_TO_ABBREV
    rows = []
    for row in (career_record(player) or {}).get("seasons") or []:
        games = int(row.get("games") or 0)
        rows.append({"season": str(row.get("season")), "games": games,
                     "ppg": float(row.get("points") or 0.0) / games if games else 0.0,
                     "teams": [ESPN_TEAM_ID_TO_ABBREV.get(str(t), "") for t in row.get("team_ids") or []]})
    return rows


# --------------------------------------------------------------------------- the save's own history

def record_season(save: dict[str, Any]) -> None:
    """Keep the season just played (called when the offseason opens; calling it again changes nothing)."""
    season = str((save.get("meta") or {}).get("season") or "")
    stats = save.get("player_season_stats") or {}
    if not season or not stats:
        return
    champion = (save.get("playoff_state") or {}).get("champion_team_id")
    teams: dict[str, str] = {}
    stars: list[str] = []
    for player_id, row in stats.items():
        games = int(row.get("games") or 0)
        abbrevs = row.get("team_abbrevs") or ([row["team_abbrev"]] if row.get("team_abbrev") else [])
        if not games or not abbrevs:
            continue
        teams[player_id] = str(abbrevs[-1])
        if games >= STAR_MIN_GAMES and float(row.get("points") or 0.0) / games >= STAR_PPG:
            stars.append(player_id)
    save.setdefault(LEDGER_KEY, {})[season] = {
        "champion": _abbrev(champion) if champion else None, "teams": teams, "stars": sorted(stars)}


def remember_origin(save: dict[str, Any], season: str, player_id: str, team_id: str | None) -> None:
    """Whom an expiring player is leaving this offseason (kept even if the team later renounces his rights)."""
    if player_id and team_id:
        save.setdefault(ORIGIN_KEY, {})[player_id] = {"team_id": team_id, "season": season}


def origin_team(save: dict[str, Any], player_id: str | None) -> str | None:
    """The team he is a free agent from this offseason (None for in-season releases and older free agents)."""
    row = (save.get(ORIGIN_KEY) or {}).get(player_id or "")
    if not row or row.get("season") != (save.get("meta") or {}).get("season"):
        return None
    return row.get("team_id")


def franchise_tie(save: dict[str, Any], player: dict[str, Any], team_id: str | None) -> dict[str, Any]:
    abbrev, player_id = _abbrev(team_id), player.get("id")
    seasons: set[str] = set()
    starred: set[str] = set()
    for row in _career_seasons(player):
        if abbrev in row["teams"]:
            seasons.add(row["season"])
            if row["games"] >= STAR_MIN_GAMES and row["ppg"] >= STAR_PPG:
                starred.add(row["season"])
    for season, entry in (save.get(LEDGER_KEY) or {}).items():
        if (entry.get("teams") or {}).get(player_id) == abbrev:
            seasons.add(season)
            if player_id in (entry.get("stars") or []):
                starred.add(season)
    if not abbrev:
        seasons, starred = set(), set()
    from .play import drafted_by_team
    drafted = bool(team_id) and drafted_by_team(save, player) == team_id
    count, star = len(seasons), bool(starred)
    icon = (count >= ICON_LONG_SEASONS or (star and count >= ICON_STAR_SEASONS)
            or (drafted and count >= ICON_HOMEGROWN_SEASONS and len(starred) >= ICON_HOMEGROWN_STAR_SEASONS))
    loyal = icon or count >= LOYAL_SEASONS or (drafted and count >= LOYAL_HOMEGROWN_SEASONS)
    return {"team_id": team_id, "seasons": count, "drafted": drafted, "star": star, "icon": icon, "loyal": loyal}


def championship_rings(save: dict[str, Any], player: dict[str, Any]) -> int:
    won: set[str] = set()
    playoffs, first_covered = _real_playoffs(player)
    career = {row["season"]: row for row in _career_seasons(player)}
    for season, champion in real_champions().items():
        if playoffs is not None and season >= first_covered:
            if playoffs.get(season) == champion:
                won.add(season)
        elif (career.get(season) or {}).get("teams") and career[season]["teams"][-1] == champion:
            won.add(season)
    for season, entry in (save.get(LEDGER_KEY) or {}).items():
        if entry.get("champion") and (entry.get("teams") or {}).get(player.get("id")) == entry["champion"]:
            won.add(season)
    return len(won)


def has_been_a_star(save: dict[str, Any], player: dict[str, Any]) -> bool:
    if any(row["games"] >= STAR_MIN_GAMES and row["ppg"] >= STAR_PPG for row in _career_seasons(player)):
        return True
    return any(player.get("id") in (entry.get("stars") or []) for entry in (save.get(LEDGER_KEY) or {}).values())


# --------------------------------------------------------------------------- how good the teams are

def defending_champion(save: dict[str, Any]) -> str | None:
    champion = (save.get("playoff_state") or {}).get("champion_team_id")
    if champion:
        return champion
    history = save.get("season_history") or []
    if history:
        return (history[-1].get("playoff_state") or {}).get("champion_team_id")
    real = real_champions()
    return f"team_{real[max(real)].lower()}" if real else None


def _last_record(save: dict[str, Any], team_id: str) -> tuple[int, float]:
    """(games, win share) of the most recent season with a real sample: this one, else the last one."""
    for records in (save.get("team_records") or {},
                    ((save.get("season_history") or [{}])[-1].get("team_records") or {})):
        row = records.get(team_id) or {}
        games = int(row.get("wins") or 0) + int(row.get("losses") or 0)
        if games >= 20:
            return games, int(row.get("wins") or 0) / games
    return 0, 0.5


def _phase(active: dict[str, Any] | None, save: dict[str, Any], team_id: str) -> str | None:
    plan = (save.get("team_plans") or {}).get(team_id) or {}
    if plan.get("window_phase"):
        return plan["window_phase"]
    state = next((s for s in (active or {}).get("team_strategic_states", []) or []
                  if s.get("team_id") == team_id), None)
    if not state:
        return None
    return state.get("window_phase") or {"contending": "peak", "contending_with_future_upside": "peak",
                                         "developing": "entering", "retooling": "exiting",
                                         "rebuilding": "rebuilding"}.get(state.get("phase"))


def contender_level(active: dict[str, Any] | None, save: dict[str, Any], team_id: str | None) -> int:
    """2: the defending champion. 1: a contender (60% winner last season, or at its peak). 0: neither."""
    if not team_id:
        return 0
    if defending_champion(save) == team_id:
        return 2
    games, share = _last_record(save, team_id)
    if (games and share >= CONTENDER_WIN_PCT) or _phase(active, save, team_id) == "peak":
        return 1
    return 0


def rebuilding(active: dict[str, Any] | None, save: dict[str, Any], team_id: str | None) -> bool:
    return bool(team_id) and _phase(active, save, team_id) == "rebuilding"


# --------------------------------------------------------------------------- what pulls him where

def chase_profile(save: dict[str, Any], player: dict[str, Any]) -> str | None:
    """Which kind of title chaser he is (a CHASE_POINTS key), or None."""
    age = _age(player)
    if age < CHASE_AGE:
        return None
    star = has_been_a_star(save, player)
    if championship_rings(save, player) == 0:
        if star:
            return "ringless_star_late" if age >= CHASE_LATE_AGE else "ringless_star"
        return "ringless_veteran" if age >= CHASE_LATE_AGE else None
    return "another_ring" if star and age >= ANOTHER_RING_AGE else None


def chase_points(active: dict[str, Any] | None, save: dict[str, Any], player: dict[str, Any], team_id: str) -> float:
    """What a better shot at a ring than his old team is worth to him."""
    level = contender_level(active, save, team_id)
    if not level:
        return 0.0
    origin = origin_team(save, player.get("id")) or player.get("team_id")
    if origin == team_id or (origin and contender_level(active, save, origin) >= level):
        return 0.0
    profile = chase_profile(save, player)
    return CHASE_POINTS[profile][level] if profile else 0.0


def loyalty_points(active: dict[str, Any] | None, save: dict[str, Any], player: dict[str, Any], team_id: str,
                   base: float) -> float:
    """Context points for the team he is a free agent from: ``base`` (the ordinary own-team pull) plus tenure and
    icon standing, halved for a veteran whose team is rebuilding."""
    tie = franchise_tie(save, player, team_id)
    points = base + min(TENURE_POINTS_CAP, max(0, tie["seasons"] - 2) * TENURE_POINTS_PER_SEASON)
    if tie["icon"]:
        points += ICON_POINTS
    if _age(player) >= REBUILD_AGE and rebuilding(active, save, team_id):
        points *= REBUILD_LOYALTY_SHARE
    return points


def tests_market_before_returning(save: dict[str, Any], player: dict[str, Any], team_id: str, seed: int,
                                  season: str) -> bool:
    """June: a ringless veteran icon whose team is not contending may look for a ring before saying yes."""
    if _age(player) < ICON_CHASE_TEST_AGE or contender_level(None, save, team_id):
        return False
    profile = chase_profile(save, player)
    if not profile or profile == "another_ring":
        return False
    digest = hashlib.sha256(f"{seed}:{season}:{player.get('id')}:icon_title_chase".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF < ICON_CHASE_TEST_CHANCE


# --------------------------------------------------------------------------- the stated reason

def _best_offer(save: dict[str, Any], player_id: str, team_id: str) -> dict[str, Any] | None:
    season = (save.get("free_agency_state") or {}).get("season")
    offers = [o for o in save.get("free_agent_offers", []) or []
              if o.get("player_id") == player_id and o.get("team_id") == team_id
              and (not season or not o.get("season") or o.get("season") == season)]
    return max(offers, key=lambda o: (float(o.get("aav_millions") or 0), str(o.get("id"))), default=None)


def departure(active: dict[str, Any] | None, save: dict[str, Any], player: dict[str, Any], new_team_id: str | None,
              *, aav_millions: float, years: int, new_minutes: float | None = None,
              own_offer: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Why this signing takes him away from the team he was a free agent from (None when it doesn't).
    ``own_offer``: that team's offer, when the caller holds it (else its best one recorded this summer)."""
    origin = origin_team(save, player.get("id"))
    if not origin or not new_team_id or origin == new_team_id:
        return None
    old = _abbrev(origin)
    own = own_offer or _best_offer(save, player.get("id"), origin)
    own_money = float(own.get("aav_millions") or 0.0) if own else None
    own_minutes = ((own or {}).get("interest_context") or {}).get("projected_minutes")
    level_new, level_old = contender_level(active, save, new_team_id), contender_level(active, save, origin)
    profile = chase_profile(save, player)
    games = (save.get("player_season_stats") or {}).get(player.get("id")) or {}
    last_minutes = (float(games.get("minutes") or 0.0) / int(games["games"])) if games.get("games") else None
    aav = float(aav_millions or 0.0)

    if profile and level_new > level_old:
        key = "ring_chase"
        reason = "chasing one more championship" if profile == "another_ring" else "chasing his first championship"
    elif own is None:
        key = "no_offer"
        reason = "to join a contender, with no offer to stay" if level_new else "with no offer to stay"
    elif aav >= own_money * MUCH_MORE_MONEY and aav - own_money >= 1.0:
        key = "bigger_contract"
        reason = f"for a much bigger contract (${aav:.1f}M a year against {old}'s ${own_money:.1f}M offer)"
    elif new_minutes is not None and own_minutes is not None and new_minutes - float(own_minutes) >= BIGGER_ROLE_MINUTES:
        key, reason = "bigger_role", "for a bigger role"
    elif (new_minutes is not None and last_minutes is not None and last_minutes < BENCHED_MINUTES
          and new_minutes >= last_minutes + BIGGER_ROLE_MINUTES + 3):
        key, reason = "poor_fit", f"looking for a better fit after playing {last_minutes:.0f} minutes a night there"
    elif _age(player) >= 27 and rebuilding(active, save, origin) and not rebuilding(active, save, new_team_id):
        key = "rebuilding"
        reason = "for a contender, away from the rebuild" if level_new else "to get away from the rebuild"
    elif level_new > level_old:
        key, reason = "contender", "to join a contender"
    elif aav > own_money + 0.2:
        key, reason = "more_money", f"for more money (${aav:.1f}M a year against {old}'s ${own_money:.1f}M offer)"
    elif int(years or 1) > int(own.get("years") or 1):
        key, reason = "longer_contract", "for a longer contract"
    else:
        key, reason = "fresh_start", "for a fresh start"
    tie = franchise_tie(save, player, origin)
    return {"from_team_id": origin, "from_abbrev": old, "key": key, "reason": reason, "clear": key in CLEAR_MOTIVES,
            "icon": tie["icon"], "seasons_with_team": tie["seasons"],
            "own_offer_millions": None if own_money is None else round(own_money, 1)}


def departure_text(save: dict[str, Any], player_id: str, from_team_id: str) -> str | None:
    """The stated reason on the signing that took him from ``from_team_id`` (None when none was recorded)."""
    for log in reversed(save.get("transaction_logs", []) or []):
        row = (log.get("assets") or {}).get("departure")
        if row and row.get("from_team_id") == from_team_id and log["assets"].get("player_id") == player_id:
            return departure_clause(row)
    return None


def departure_clause(departed: dict[str, Any]) -> str:
    """"leaving POR after 12 seasons, chasing his first championship"."""
    stay = f" after {departed['seasons_with_team']} seasons there," if departed.get("icon") else ""
    return f"leaving {departed['from_abbrev']}{stay} {departed['reason']}"
