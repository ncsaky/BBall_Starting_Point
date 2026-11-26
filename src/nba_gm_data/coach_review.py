"""Judging a head coach against what his roster was expected to do (COACHES-FREE-AGENTS, 2026-11-26).

The user's complaint: Golden State fired Steve Kerr after a 38-44 season with two stars hurt, a legendary coach whose
team performed about as expected. A review therefore weighs:

- **Expectation**: set at the season's first review from each healthy roster's strength (the front offices' own
  contention number), mapped to wins on the scale of real preseason win totals.
- **Injuries and departures**: the wins a team's best players are worth, for the games they missed or after they left.
  A preseason forecast already allows for a normal season's injuries, so only the difference from the league's
  typical loss moves a team's expectation (up for a healthy team, down for a battered one).
- **Standing**: titles with the team and as a head coach, years there, a deep playoff run, a second poor season.
- **Direction**: a team that opened as a contender and turned toward rebuilding.

Firing chances rise steeply with the miss; a franchise legend with results near expectations is never fired.
Evidence for the league-wide level (about two in-season and three summer firings a year, a mild effect of wins against
the forecast, none among long-tenured coaches who missed badly): docs/agents/tasks/staff-turnover-evidence.md.
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from typing import Any

from .resource_paths import game_resource_root
from .staff_lifecycle import WINS_PER_STRENGTH_POINT, staff_person_id, staff_win_expectations
from .utils import clamp, normalize_name

KEY_PLAYERS = 6               # whose missed games lower the expectation
KEY_PLAYER_MAX_WINS = 18.0    # one player's worth, wins per 82
LOST_WINS_CAP = 22.0          # all of them together
IN_SEASON_MIN_GAMES = 20

# Firing chance by wins per 82 games against the adjusted expectation: (gap at or below, chance). The summer chance is
# per season, the in-season one per monthly review.
# Weighted toward real misses: a season near or above expectations rarely ends in a firing.
SUMMER_CHANCES = ((-12.0, 0.76), (-7.0, 0.60), (-3.0, 0.38), (3.0, 0.07), (999.0, 0.012))
IN_SEASON_CHANCES = ((-12.0, 0.20), (-7.0, 0.12), (-3.0, 0.052), (3.0, 0.006), (999.0, 0.001))
# A franchise legend is safe unless his team falls this far short (summer, in season).
LEGEND_SAFE_GAP = {True: -10.0, False: -15.0}


@lru_cache(maxsize=1)
def real_coach_standing() -> dict[str, dict[str, Any]]:
    path = game_resource_root() / "data/research/head_coach_standing_2026_27.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("coaches") or {}
    except (OSError, ValueError):
        return {}
    return {normalize_name(name): row for name, row in rows.items()}


def _start_year(label: Any) -> int:
    text = str(label or "")[:4]
    return int(text) if text.isdigit() else 2026


def coach_standing(save: dict[str, Any], staff: dict[str, Any]) -> dict[str, Any]:
    """His years with this team (this season included), titles there and anywhere, and whether he is a legend."""
    season_start = _start_year((save.get("meta") or {}).get("season"))
    team_id = staff.get("team_id")
    abbrev = str(team_id or "").replace("team_", "").upper()
    real = real_coach_standing().get(normalize_name(staff.get("name"))) or {}
    hired = str(staff.get("staff_hired_on") or "")
    if real.get("team") == abbrev and not hired:
        since, with_team = int(real.get("team_since") or 2026), list(real.get("titles_with_team") or [])
    else:
        if len(hired) >= 7 and hired[:4].isdigit():
            since = int(hired[:4]) - (0 if hired[5:7] >= "07" else 1)
        else:
            since = 2026
        with_team = []
    simulated = (save.get("staff_titles") or {}).get(staff_person_id(staff) if staff.get("id") else "", [])
    with_team += [row["season"] for row in simulated if row.get("team_id") == team_id]
    total = (len(real.get("titles_with_team") or []) + int(real.get("titles_elsewhere") or 0) + len(simulated))
    seasons = max(1, season_start - since + 1)
    latest = max((_start_year(s) for s in with_team), default=None)
    return {"seasons_with_team": seasons, "titles_with_team": len(with_team), "titles": max(total, len(with_team)),
            "seasons_since_title": None if latest is None else season_start - latest,
            "legend": len(with_team) >= 2 or (bool(with_team) and seasons >= 6)}


def record_coach_titles(save: dict[str, Any]) -> None:
    """The champion's head coach keeps the title (called at the summer review; calling it again changes nothing)."""
    champion = (save.get("playoff_state") or {}).get("champion_team_id")
    season = str((save.get("meta") or {}).get("season") or "")
    head = next((s for s in save.get("staff_slots", []) or []
                 if s.get("team_id") == champion and s.get("slot") == "head_coach"), None)
    if not (champion and season and head):
        return
    titles = save.setdefault("staff_titles", {}).setdefault(staff_person_id(head), [])
    if not any(row.get("season") == season for row in titles):
        titles.append({"season": season, "team_id": champion})


# --------------------------------------------------------------------------- expectations

def set_season_expectations(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    """Once a season, at its first in-season review: each team's expected wins from its healthy roster, and what each
    of its best players is worth to that figure."""
    season = str((save.get("meta") or {}).get("season") or "")
    store = save.get("staff_season_expectations") or {}
    if not season or season in store or not canonical.get("players") or not canonical.get("teams"):
        return
    from .roster_forecast import ForecastSnapshot
    from .save import player_attribute_summary
    from .transactions import contention_ceiling

    base = {**canonical, "_roster_forecast_snapshot": ForecastSnapshot(canonical)}
    ceilings = {team["id"]: contention_ceiling(base, team, []) for team in canonical["teams"]}
    expected = staff_win_expectations([{"team_id": t, "contention_ceiling": c} for t, c in ceilings.items()])
    plans = save.get("team_plans") or {}
    rows = {}
    for team in canonical["teams"]:
        team_id = team["id"]
        roster = [p for p in canonical["players"] if p.get("team_id") == team_id and not p.get("_inactive_player")]
        best = sorted(roster, key=lambda p: (-float(player_attribute_summary(canonical, p["id"]).get("overall") or 0),
                                             str(p["id"])))[:KEY_PLAYERS]
        worth = {}
        for player in best:
            without = {**base, "players": [p for p in roster if p["id"] != player["id"]]}
            lost = (ceilings[team_id] - contention_ceiling(without, team, [])) * WINS_PER_STRENGTH_POINT
            if lost > 0.05:
                worth[player["id"]] = round(min(KEY_PLAYER_MAX_WINS, lost), 2)
        rows[team_id] = {"phase": (plans.get(team_id) or {}).get("window_phase"), "key_players": worth}
    # Older seasons' rows are not read again.
    save["staff_season_expectations"] = {season: rows}
    save.setdefault("staff_preseason_expectations", {})[season] = expected


def note_departures(canonical: dict[str, Any], save: dict[str, Any], today: str) -> None:
    """Remember when a key player left (trade, waiver) so the rest of the season no longer counts on him."""
    season = str((save.get("meta") or {}).get("season") or "")
    rows = (save.get("staff_season_expectations") or {}).get(season) or {}
    if not rows:
        return
    teams = {p.get("id"): p.get("team_id") for p in canonical.get("players", []) or []}
    for team_id, row in rows.items():
        for player_id in row.get("key_players") or {}:
            if player_id in teams and teams[player_id] != team_id:
                row.setdefault("left", {}).setdefault(player_id, today)


def _season_share_after(day: str, season: str) -> float:
    start = _start_year(season)
    opener, finale = date(start, 10, 22), date(start + 1, 4, 13)
    try:
        left = date.fromisoformat(str(day)[:10])
    except ValueError:
        return 0.0
    return clamp((finale - left).days / (finale - opener).days, 0.0, 1.0)


def lost_wins_by_team(save: dict[str, Any]) -> dict[str, float]:
    """Each team's wins per 82 lost so far to its key players' missed games and departures."""
    season = str((save.get("meta") or {}).get("season") or "")
    rows = (save.get("staff_season_expectations") or {}).get(season) or {}
    if not rows:
        return {}
    missed = {s.get("player_id"): int(s.get("games_missed") or 0) for s in save.get("health_states", []) or []}
    out = {}
    for team_id, detail in rows.items():
        record = (save.get("team_records") or {}).get(team_id) or {}
        games = int(record.get("wins") or 0) + int(record.get("losses") or 0)
        if not games:
            continue
        left = detail.get("left") or {}
        lost = 0.0
        for player_id, worth in (detail.get("key_players") or {}).items():
            share = min(1.0, missed.get(player_id, 0) / games)
            if player_id in left:
                share = min(1.0, share + _season_share_after(left[player_id], season))
            lost += float(worth) * share
        out[team_id] = min(LOST_WINS_CAP, lost)
    return out


def team_review(canonical: dict[str, Any], save: dict[str, Any], team_id: str, expected_pct: float,
                losses_by_team: dict[str, float] | None = None) -> dict[str, Any] | None:
    """The team's season against its expectation, in wins per 82 games, after injuries and departures.
    ``losses_by_team``: lost_wins_by_team(save), when the caller reviews several teams."""
    record = (save.get("team_records") or {}).get(team_id) or {}
    wins, losses = int(record.get("wins") or 0), int(record.get("losses") or 0)
    games = wins + losses
    if not games:
        return None
    season = str((save.get("meta") or {}).get("season") or "")
    detail = ((save.get("staff_season_expectations") or {}).get(season) or {}).get(team_id) or {}
    losses_by_team = lost_wins_by_team(save) if losses_by_team is None else losses_by_team
    typical = sum(losses_by_team.values()) / len(losses_by_team) if losses_by_team else 0.0
    lost = losses_by_team.get(team_id, typical)
    expected = 82 * expected_pct - (lost - typical)
    return {"wins": wins, "losses": games - wins, "games": games, "expected_wins": round(expected, 1),
            "lost_wins": round(lost, 1), "injury_allowance": round(lost - typical, 1),
            "gap": round(82 * wins / games - expected, 2), "opening_phase": detail.get("phase")}


# --------------------------------------------------------------------------- the decision

def changed_direction(save: dict[str, Any], team_id: str, review: dict[str, Any]) -> bool:
    """The team opened the season as a contender or on the rise and now plans to rebuild."""
    now = ((save.get("team_plans") or {}).get(team_id) or {}).get("window_phase")
    return review.get("opening_phase") in {"peak", "entering"} and now in {"exiting", "rebuilding"}


def head_coach_firing_chance(win_gap: float, *, offseason: bool, standing: dict[str, Any] | None = None,
                             previous_gap: float | None = None, recent_success: bool = False,
                             new_direction: bool = False) -> float:
    """The chance this review ends with a firing. ``win_gap``: wins per 82 games against the adjusted expectation."""
    table = SUMMER_CHANCES if offseason else IN_SEASON_CHANCES
    chance = next(value for limit, value in table if win_gap <= limit)
    if standing is None:
        return chance
    seasons, titles_here = standing["seasons_with_team"], standing["titles_with_team"]
    since = standing.get("seasons_since_title")
    if since == 0:
        return 0.0                                   # he just won it
    if standing["legend"]:
        if win_gap > LEGEND_SAFE_GAP[offseason]:
            return 0.0
        chance *= 0.10 if (since is not None and since <= 6) else 0.15
    elif titles_here:
        chance *= 0.3 if (since is not None and since <= 3) else 0.6
    else:
        if standing["titles"]:
            chance *= 0.8                            # a champion elsewhere gets some benefit of the doubt
        if seasons >= 5:
            chance *= 0.75                           # long tenure
        elif seasons <= 1:
            chance *= 0.75                           # a first season is usually allowed to finish
        elif seasons <= 3 and win_gap < -3:
            chance *= 1.3                            # a short tenure without results
    if recent_success:
        chance *= 0.6
    if previous_gap is not None and previous_gap < -5 and win_gap < -3:
        chance *= 1.35                               # a second poor season
    if new_direction and not titles_here and win_gap <= 3:
        chance *= 1.3
    return min(0.85, chance)


def review_context(save: dict[str, Any], staff: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    """Everything beyond the record that head_coach_firing_chance weighs."""
    season = str((save.get("meta") or {}).get("season") or "")
    team_id, person = staff.get("team_id"), staff_person_id(staff)
    previous = [(label, rows.get(team_id)) for label, rows in (save.get("staff_season_review") or {}).items()
                if label < season]
    last = max(previous, key=lambda item: item[0], default=(None, None))[1]
    last = last if last and last.get("coach_id") == person else None
    series = sum(1 for row in (save.get("playoff_state") or {}).get("series", []) or []
                 if row.get("winner_team_id") == team_id)
    return {
        "standing": coach_standing(save, staff),
        "previous_gap": (last or {}).get("gap"),
        "recent_success": series >= 1 or float((last or {}).get("gap") or 0.0) >= 5.0 or
        int((last or {}).get("series_wins") or 0) >= 1,
        "new_direction": changed_direction(save, team_id, review),
    }


def remember_review(save: dict[str, Any], staff: dict[str, Any], review: dict[str, Any]) -> None:
    """Keep the summer's verdict: next summer reads it, and the staff lifecycle grades the coach on the same figure."""
    season = str((save.get("meta") or {}).get("season") or "")
    team_id = staff.get("team_id")
    series = sum(1 for row in (save.get("playoff_state") or {}).get("series", []) or []
                 if row.get("winner_team_id") == team_id)
    reviews = save.setdefault("staff_season_review", {})
    reviews.setdefault(season, {})[team_id] = {**review, "coach_id": staff_person_id(staff), "series_wins": series}
    for label in sorted(reviews)[:-2]:
        del reviews[label]


def firing_reason(review: dict[str, Any], context: dict[str, Any]) -> str:
    record = f"{review['wins']}-{review['losses']}"
    if review.get("games", 82) < 70:      # in season: the record reads as the pace it is judged on
        record += f" (on pace for {82 * review['wins'] / review['games']:.0f} wins)"
    gap, expected = review["gap"], review["expected_wins"]
    if gap > -3:
        standing = "close to" if gap <= 3 else "ahead of"
        return f"{record}, {standing} the {expected:.0f} wins expected of this roster; the owner wanted a change"
    text = (f"{record}, {abs(gap):.0f} wins per 82 games short of the {expected:.0f} expected of this roster"
            + (" even allowing for injuries and departures" if review.get("injury_allowance", 0) >= 2 else ""))
    if context.get("previous_gap") is not None and context["previous_gap"] < -5:
        text += ", a second season well short"
    elif context.get("new_direction"):
        text += ", with the team changing direction"
    elif context["standing"]["seasons_with_team"] in (2, 3) and not context["standing"]["titles_with_team"]:
        text += f", with no breakthrough in {context['standing']['seasons_with_team']} seasons"
    return text
