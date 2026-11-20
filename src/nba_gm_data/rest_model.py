"""Coach rest decisions for healthy regulars (SMART-REST, 2026-11-19).

Two parts:

1. Schedule context for each team game: days since the last game, back-to-back nights, travel distance and time zones
   crossed since the previous game (arena locations in data/canonical/arenas.json), road-trip length and game density.
   The same code reads the real 2025-26 schedule (scripts/research/rest_patterns.py) and the game's schedules.
2. The rest chance itself (rest_chance): an explainable model fitted to the real 2025-26 box scores, see the constants
   below and docs/agents/tasks/smart-rest.md.
"""
from __future__ import annotations

import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

ARENAS_FILE = Path(__file__).resolve().parents[2] / "data" / "canonical" / "arenas.json"
EARTH_RADIUS_MILES = 3958.8


@lru_cache(maxsize=1)
def arenas() -> dict[str, dict[str, Any]]:
    """ESPN team id -> arena row (abbrev, lat, lon, utc_offset)."""
    try:
        return json.loads(ARENAS_FILE.read_text(encoding="utf-8")).get("teams", {})
    except (OSError, ValueError):
        return {}


def miles_between(a: dict[str, Any] | None, b: dict[str, Any] | None) -> float:
    """Great-circle distance in miles between two arena rows (0 when either is unknown)."""
    if not a or not b:
        return 0.0
    lat1, lon1, lat2, lon2 = map(math.radians, (float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"])))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(h)))


def _day(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def team_schedule_context(games: Iterable[dict[str, Any]], espn_team_id: str) -> dict[str, dict[str, Any]]:
    """Per game id of this team's games: schedule facts known before tip-off.

    days_rest: days since the previous game (None for the first); back_to_back: second night of a back-to-back;
    first_of_b2b: the team also plays tomorrow; miles / tz_change: travel from the previous game's arena (the home
    team's arena; neutral sites count as the home team's); road_trip: games into the current road trip (0 at home);
    games_last_4 / games_last_6: games in the 4 / 6 days ending today (today's included)."""
    team = str(espn_team_id)
    mine = sorted((g for g in games if team in (str(g.get("homeTeamId")), str(g.get("awayTeamId")))),
                  key=lambda g: (str(g.get("gameDate") or ""), str(g.get("externalGameId") or "")))
    where = arenas()
    out: dict[str, dict[str, Any]] = {}
    days = [_day(g["gameDate"]) for g in mine]
    trip = 0
    for i, game in enumerate(mine):
        home = str(game.get("homeTeamId")) == team
        site = where.get(str(game.get("homeTeamId")))
        previous_site = where.get(str(mine[i - 1].get("homeTeamId"))) if i else where.get(team)
        days_rest = (days[i] - days[i - 1]).days if i else None
        trip = 0 if home else trip + 1
        tz_change = (float(site["utc_offset"]) - float(previous_site["utc_offset"])) if site and previous_site else 0.0
        out[str(game.get("externalGameId"))] = {
            "date": days[i].isoformat(),
            "home": home,
            "opponent_espn_id": str(game.get("awayTeamId") if home else game.get("homeTeamId")),
            "days_rest": days_rest,
            "back_to_back": days_rest == 1,
            "first_of_b2b": i + 1 < len(mine) and (days[i + 1] - days[i]).days == 1,
            "miles": round(miles_between(previous_site, site), 1),
            "tz_change": tz_change,
            "road_trip": trip,
            "games_last_4": sum(1 for d in days[: i + 1] if (days[i] - d).days < 4),
            "games_last_6": sum(1 for d in days[: i + 1] if (days[i] - d).days < 6),
            "game_number": i + 1,
            "games_total": len(mine),
        }
    return out


def league_schedule_context(games: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """(game id, ESPN team id) -> team_schedule_context row, for every team in the schedule."""
    teams = {str(g.get(k)) for g in games for k in ("homeTeamId", "awayTeamId") if g.get(k) is not None}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for team in teams:
        for game_id, row in team_schedule_context(games, team).items():
            out[(game_id, team)] = row
    return out


_SCHEDULE_CACHE: dict[tuple, dict[tuple[str, str], dict[str, Any]]] = {}


def cached_league_schedule_context(games: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """league_schedule_context, computed once per schedule (the save passes the same season schedule every day)."""
    if not games:
        return {}
    key = (len(games), str(games[0].get("externalGameId")), str(games[-1].get("externalGameId")),
           str(games[0].get("gameDate")), str(games[-1].get("gameDate")))
    if key not in _SCHEDULE_CACHE:
        if len(_SCHEDULE_CACHE) > 8:
            _SCHEDULE_CACHE.clear()
        _SCHEDULE_CACHE[key] = league_schedule_context(games)
    return _SCHEDULE_CACHE[key]


# ---- Standings: where each team stands in its race ------------------------------------------------------------------

REGULAR_SEASON_GAMES = 82
LATE_WINDOW = 20             # the last 20 games: a locked seed or a finished race changes how coaches rest


def shrunk_win_pct(wins: int, losses: int) -> float:
    """Winning percentage pulled toward .500 by five wins and five losses, so early records are not taken at face value
    (coaches know a 3-0 team is not a 1.000 team)."""
    return (wins + 5.0) / (wins + losses + 10.0)


def seed_movement(team: str, order: list[str], wins: dict[str, int], losses: dict[str, int], total: dict[str, int]) -> dict[str, Any]:
    """How far a team can still move in its conference (by wins and games left): the best and worst places it can still
    finish, and whether a line that changes its postseason (1st, top 4, top 6, top 8, top 10) is still in play."""
    max_wins = {t: wins[t] + max(0, total[t] - wins[t] - losses[t]) for t in order}
    up = sum(1 for t in order if t != team and wins[t] > wins[team] and max_wins[team] >= wins[t])
    down = sum(1 for t in order if t != team and wins[t] <= wins[team] and max_wins[t] >= wins[team])
    rank = order.index(team) + 1
    best, worst = rank - up, rank + down
    line_in_play = any(best <= line < worst for line in (1, 4, 6, 8, 10))
    return {"best": best, "worst": worst, "line_in_play": line_in_play}


def race_situation(movement: dict[str, Any], league_rank: int, teams: int = 30) -> str:
    """'race' (a seed or the play-in line still in play), 'locked' (nothing left to move) or 'out' (a bottom team
    that cannot reach the play-in). The research script and the game use the same rule."""
    if movement["best"] > 10 and league_rank > teams - 8:
        return "out"
    return "race" if movement["line_in_play"] else "locked"


def league_standings(records: dict[str, dict[str, Any]], conference_of: dict[str, str],
                     games_total: dict[str, int] | None = None) -> dict[str, dict[str, Any]]:
    """Per team: wins, losses, games left (tonight's included), shrunk winning percentage, league rank by it (1 = best),
    conference place, the places it can still finish and its situation ('race', 'locked', 'out')."""
    wins = {t: int((r or {}).get("wins") or 0) for t, r in records.items()}
    losses = {t: int((r or {}).get("losses") or 0) for t, r in records.items()}
    total = {t: int((games_total or {}).get(t) or REGULAR_SEASON_GAMES) for t in records}
    pct = {t: shrunk_win_pct(wins[t], losses[t]) for t in records}
    league = sorted(records, key=lambda t: (-pct[t], t))
    by_conf: dict[str, list[str]] = {}
    for t in records:
        by_conf.setdefault(str(conference_of.get(t) or "League"), []).append(t)
    out: dict[str, dict[str, Any]] = {}
    for members in by_conf.values():
        order = sorted(members, key=lambda t: (-(wins[t] - losses[t]), t))
        for t in members:
            movement = seed_movement(t, order, wins, losses, total)
            left = max(0, total[t] - wins[t] - losses[t])
            league_rank = league.index(t) + 1
            out[t] = {"wins": wins[t], "losses": losses[t], "games_left": left, "win_pct": pct[t],
                      "rank": league_rank, "teams": len(league), "conf_rank": order.index(t) + 1,
                      "best_seed": movement["best"], "worst_seed": movement["worst"],
                      "line_in_play": movement["line_in_play"],
                      "situation": race_situation(movement, league_rank, len(league))}
    return out


# ---- The rest chance ------------------------------------------------------------------------------------------------
# Fitted to real 2025-26 box scores (rows: scripts/research/rest_patterns.py; fit: scripts/research/fit_rest_model.py):
# 10,895 games of 170 regulars (25+ minutes a game), 414 single-game absences (a game missed between two played).
# Logistic model: each factor multiplies the odds. Standard errors in docs/agents/tasks/smart-rest.md and
# docs/agents/tasks/overnight-tv-rest-games-played.md.
# Tested and left out because they predicted nothing: travel distance (overall and on back-to-backs), time zones
# crossed, the team's own record, home games on other nights, a star x weak-opponent interaction, national TV for
# stars beyond everyone else, and age per year over 27 once the two age terms below are in.
# OVERNIGHT-REST-GAMES (2026-11-20) refit: national TV games (ESPN, ABC, NBC, Peacock, Prime Video; NBA TV-only games
# are not counted, they showed no drop) and the age shape: rest rises with age up to 27 and then stays flat on ordinary
# nights, while players 30 and over sit much more on back-to-backs (the old straight line under-rested 30-33s on
# back-to-backs, 10.7% fitted against 13.3% real, and over-rested players under 25).
REST_INTERCEPT = -4.129
REST_COEF = {
    "second_night": 0.753,            # second night of a back-to-back                          x2.12
    "first_night": 0.310,             # first night of a back-to-back (rest either night)        x1.36
    "second_night_road": 0.556,       # ... and the second night is on the road                 x1.74
    "age_30_b2b": 0.574,              # age 30+ on either night of a back-to-back               x1.77
    "age_under_27_per_year": -0.097,  # per year under 27 (down to 21): young players sit less   x0.91 a year
    "star": 0.520,                    # league top 45                                            x1.68
    "minutes_per_5": -0.306,          # per 5 minutes a game over 30 (heavy-minute players sit less) x0.74
    "opponent_weak_per_100": 0.255,   # per .100 of opponent winning % below .500                x1.29
    "opponent_elite_per_100": 0.978,  # per .100 above .600 (games against the very best)        x2.66
    "season_progress": 0.710,         # from opening night (0) to the last game (1)              x2.03
    "late_locked": 0.837,             # last 20 games, seed locked                               x2.31
    "late_out": 0.407,                # last 20 games, out of the race                           x1.50
    "road_trip_3": -0.555,            # third game or later of a road trip                       x0.57
    "return_b2b": 0.788,              # back-to-back within 5 games of returning from an absence x2.20
    "national_tv": -0.308,            # nationally televised game (participation policy)        x0.73
}
# Calibration: the fitted rates include one-game absences for injury and illness (the injury model adds its own),
# while the league rules below (two regulars and one star a game, the 65-game rule, short-handed nights) and the
# multi-game absences around some rest nights take some away. In full simulated seasons the two roughly cancel: with
# the model's odds times 1.02, all single-game absences of regulars match real (3.8%; output/smart-rest/).
# INJURIES-2 (2026-11-20): injuries now cost games the way Basketball Index counts them, so one-game injuries are 40%
# of all injuries (was 27-30%) and regulars' single-game absences rose to 4.5-4.6%; at 0.78 they are 4.0% again, the
# same as before the change (real 3.8%; output/injuries-2/compare_smart.py).
REST_COACH_SHARE = 0.78
# Workloads beyond anything real AI schedules produce (a GM playing a star 42+ minutes through a dense stretch):
# above 1.2 times a typical back-to-back's extra fatigue, the odds rise up to 1.5x (judgment; real coaches rest first).
REST_FATIGUE_LOAD_START = 1.2
REST_FATIGUE_LOAD_ODDS = 0.6
FATIGUE_B2B_STEP = 1.0 / 0.62 - 1.0   # a typical back-to-back's tip-off fatigue over a normal night (health.FATIGUE_DAILY_KEEP)
# The season's final two games (real 2025-26, regulars who had played in the five games before):
# last game: seed locked inside the top six 72%, other locked 50%, still racing 29%, out of the race 59%;
# second-to-last: locked 27-30%, racing 25%, out 50%. Chances for healthy players (the real rates include injuries).
REST_FINAL = {1: {"locked_playoff": 0.66, "locked": 0.50, "race": 0.30, "out": 0.50},
              2: {"locked_playoff": 0.28, "locked": 0.28, "race": 0.14, "out": 0.42}}
# League rules and guards.
REST_MIN_MINUTES = 24.0
REST_MISSED_LIMIT = 14               # no rest nights once a player has missed this many games (65-game award rule)
REST_MAX_STARS_PER_GAME = 1          # player participation policy: one star at most
REST_MAX_PER_GAME = 2                # real: 2+ regulars sat the same game in 2.3% of team games, one in 12%
REST_SHORT_HANDED = 3                # no rest nights while this many regulars are already out injured
STAR_COUNT = 45                      # the league counted 45 stars under the participation policy in 2025-26
# Teams out of the race shut players down: in real 2025-26 the eight worst teams' regulars sat an average of 6.8 of
# the final games (74% sat at least one, 46% five or more) against about 1 for other teams.
SHUTDOWN_BOTTOM_TEAMS = 8
SHUTDOWN_GAMES_LEFT = 25
SHUTDOWN_HAZARD = 0.03
SHUTDOWN_REASON = "shut down for the rest of the season (team out of the race)"


def _record(wins: Any, losses: Any) -> str:
    return f"{int(wins or 0)}-{int(losses or 0)}"


def rest_assessment(player: dict[str, Any], state: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """The coach's rest chance for a healthy regular tonight, with the factors behind it.

    Returns {"chance" (of sitting tonight), "shutdown_chance" (the part of it that shuts him down for the season; teams
    out of the race), "kind" (the likelier of "rest" and "shutdown"), "reason" (plain words: the factors that raised the
    chance most), "factors" (odds multiplier per factor)}. rest_decision turns it and the seeded draw into a decision. context keys: games_left (tonight's included), rank, teams, situation,
    worst_seed, back_to_back, first_of_b2b, home, road_trip, game_number, games_total, opp_wins, opp_losses, star,
    national_tv, rested_tonight, stars_rested_tonight, regulars_out, fatigue, fatigue_normal. Missing keys fall back to neutral."""
    teams = int(context.get("teams") or 30)
    rank = int(context.get("rank") or teams // 2)
    games_left = int(context["games_left"]) if context.get("games_left") is not None else REGULAR_SEASON_GAMES
    situation = str(context.get("situation") or "race")
    none = {"chance": 0.0, "shutdown_chance": 0.0, "kind": "rest", "reason": "", "factors": {}}
    if 1 <= games_left <= 2:
        key = "locked_playoff" if situation == "locked" and int(context.get("worst_seed") or 99) <= 6 else situation
        words = {"locked_playoff": "playoff seed locked: rest before the playoffs", "locked": "seed locked, nothing left to play for",
                 "race": "rest in the season's final games", "out": "out of the race: season's final games"}
        return {**none, "chance": REST_FINAL[games_left].get(key, REST_FINAL[games_left]["race"]), "reason": words.get(key, words["race"])}
    # Bottom teams late in the season shut regulars down (a small chance each game), on top of ordinary rest nights.
    shutdown = (SHUTDOWN_HAZARD if games_left <= SHUTDOWN_GAMES_LEFT and rank > teams - SHUTDOWN_BOTTOM_TEAMS and games_left > 0
                else 0.0)
    only_shutdown = {**none, "chance": shutdown, "shutdown_chance": shutdown, "kind": "shutdown" if shutdown else "rest",
                     "reason": SHUTDOWN_REASON if shutdown else ""}
    if int(state.get("games_missed") or 0) + int(state.get("games_rested") or 0) >= REST_MISSED_LIMIT:
        return only_shutdown
    if int(context.get("regulars_out") or 0) >= REST_SHORT_HANDED:
        return only_shutdown
    star = bool(context.get("star"))
    if int(context.get("rested_tonight") or 0) >= REST_MAX_PER_GAME:
        return only_shutdown
    if star and int(context.get("stars_rested_tonight") or 0) >= REST_MAX_STARS_PER_GAME:
        return only_shutdown
    age = float(player.get("age") or 27.0)
    minutes = float(player.get("minutes_projection") or 30.0)
    second = bool(context.get("back_to_back"))
    first = bool(context.get("first_of_b2b")) and not second
    home = bool(context.get("home", True))
    opp_pct = shrunk_win_pct(int(context.get("opp_wins") or 0), int(context.get("opp_losses") or 0))
    games_total = int(context.get("games_total") or REGULAR_SEASON_GAMES)
    game_number = int(context.get("game_number") or (games_total - games_left + 1))
    progress = min(1.0, max(0.0, game_number / float(games_total)))
    returning = int(state.get("return_absence_games") or 0) > 0 and int(state.get("games_since_return") or 0) <= 5
    terms = {
        "second_night": REST_COEF["second_night"] * second,
        "first_night": REST_COEF["first_night"] * first,
        "road": REST_COEF["second_night_road"] * (second and not home),
        "age": REST_COEF["age_30_b2b"] * (age >= 30.0 and (second or first)),
        "young": REST_COEF["age_under_27_per_year"] * max(0.0, 27.0 - max(21.0, age)),
        "star": REST_COEF["star"] * star,
        "minutes": REST_COEF["minutes_per_5"] * (minutes - 30.0) / 5.0,
        "opponent_weak": REST_COEF["opponent_weak_per_100"] * (0.5 - opp_pct) * 10.0,
        "opponent_elite": REST_COEF["opponent_elite_per_100"] * max(0.0, opp_pct - 0.6) * 10.0,
        "season": REST_COEF["season_progress"] * progress,
        "late_locked": REST_COEF["late_locked"] * (games_left < LATE_WINDOW and situation == "locked"),
        "late_out": REST_COEF["late_out"] * (games_left < LATE_WINDOW and situation == "out"),
        "road_trip": REST_COEF["road_trip_3"] * (int(context.get("road_trip") or 0) >= 3),
        "returning": REST_COEF["return_b2b"] * (second and returning),
        "national_tv": REST_COEF["national_tv"] * bool(context.get("national_tv")),
    }
    load = None
    if context.get("fatigue") is not None and context.get("fatigue_normal"):
        ratio = float(context["fatigue"]) / max(1.0, float(context["fatigue_normal"]))
        load = (ratio - 1.0) / FATIGUE_B2B_STEP      # 0 = a normal night, 1 = a typical back-to-back
        if load > REST_FATIGUE_LOAD_START:
            terms["fatigue"] = math.log(1.0 + REST_FATIGUE_LOAD_ODDS * (min(2.0, load) - REST_FATIGUE_LOAD_START))
    odds = math.exp(REST_INTERCEPT + sum(terms.values())) * REST_COACH_SHARE
    chance = odds / (1.0 + odds)
    words = {
        "second_night": "second night of a back-to-back" + ("" if home else " on the road"),
        "first_night": "first night of a back-to-back",
        "age": f"age {age:.0f}",
        "star": "star workload",
        "opponent_weak": f"opponent {_record(context.get('opp_wins'), context.get('opp_losses'))}",
        "opponent_elite": f"opponent {_record(context.get('opp_wins'), context.get('opp_losses'))}, among the league's best",
        "season": "late in the season",
        "late_locked": "seed locked",
        "late_out": "team out of the race",
        "returning": "soon after returning from injury",
        "fatigue": f"heavy recent workload (fatigue {float(context.get('fatigue') or 0):.0f})",
    }
    merged = dict(terms)
    if progress < 0.75:
        merged.pop("season")            # in words only in the last quarter of the season
    merged["second_night"] = merged.get("second_night", 0.0) + merged.pop("road", 0.0)
    if merged.get("opponent_elite", 0.0) > 0:
        merged["opponent_elite"] += merged.pop("opponent_weak", 0.0)
    raised = sorted(((value, key) for key, value in merged.items() if value > 0.25 and key in words), reverse=True)[:3]
    reason = ", ".join(words[key] for _, key in raised) or "maintenance day"
    factors = {key: round(math.exp(value), 2) for key, value in terms.items() if abs(value) > 1e-9}
    total = shutdown + (1.0 - shutdown) * chance
    return {"chance": total, "shutdown_chance": shutdown, "kind": "shutdown" if shutdown > total - shutdown else "rest",
            "reason": reason, "factors": factors}


def rest_decision(assessment: dict[str, Any], draw: float) -> tuple[str, str] | None:
    """The coach's call for tonight from an assessment and the seeded draw: ("shutdown" | "rest", reason) or None."""
    if draw < float(assessment.get("shutdown_chance") or 0.0):
        return "shutdown", SHUTDOWN_REASON
    if assessment["chance"] > 0 and draw < assessment["chance"]:
        return "rest", assessment["reason"] or "maintenance day"
    return None


_STAR_CACHE: dict[tuple[str, int], list[str]] = {}


def star_ids(canonical: dict[str, Any], period: str = "") -> set[str]:
    """The league's top STAR_COUNT rostered players by overall rating. Kept for a period (the save passes the month,
    so development moves players in and out of the group) and recomputed when any player changes teams."""
    rostered = sorted((player["id"], str(player.get("team_id")))
                      for player in canonical.get("players", []) if player.get("team_id") and not player.get("_inactive_player"))
    key = (period, hash(tuple(rostered)))
    if key in _STAR_CACHE:
        return set(_STAR_CACHE[key])
    from .save import player_attribute_summary
    rated = []
    for player_id, _ in rostered:
        try:
            rated.append((float(player_attribute_summary(canonical, player_id).get("overall") or 0.0), player_id))
        except Exception:
            continue
    stars = sorted(pid for _, pid in sorted(rated, reverse=True)[:STAR_COUNT])
    if len(_STAR_CACHE) > 16:
        _STAR_CACHE.clear()
    _STAR_CACHE[key] = stars
    return set(stars)
