"""Four Factors for any roster: the engine's expected box score, worked out without simulating games.

A season's Four Factors (effective field-goal %, turnover %, offensive rebound %, free-throw rate) come from the box
scores the game engine writes. This module works out what those box scores average for a roster, from the same pieces
the engine uses and in the same order:

1. The team's features (sim.game_team_features) over the coach's projected minutes, as tonight's pool would carry them
   (top 14 by minutes, scaled to 240 like sim.normalize_minutes).
2. Against every other team at home and away: both teams' expected possessions (shared pace, the average of the two)
   and each side's expected offensive rating (sim.draw_team_score with mean_only), so expected points.
3. Each player's share of the points (his fitted points per 36 x minutes), free throws (points x fitted free throws per
   point x offense.FT_LEVEL), threes (minutes x fitted threes per 36, at his percentage), the two-point makes that are
   left, and his own two-point misses against this opponent's rim protection (box_variation.vary_box_score).
4. Turnovers: his fitted rate x minutes, moved by the opponent's ball pressure and his team's passing
   (box_variation.vary_box_score).
5. Field-goal attempts: two-point misses filled most of the way (box_variation.MISS_FILL) toward the possessions the
   score leaves, plus the opponent's rim protection term (box_variation.vary_box_score).
6. Offensive rebounds: the team's rebound share from its offensive rebounding (box_variation.vary_box_score), which is
   also its Four Factors offensive rebound % (the opponent's defensive rebounds are the rest of the same misses).

Nothing random is drawn and nothing is saved. Season totals are summed over the opponents before the rates are taken,
the way the Profile tab sums a season's box scores (app_actions.dashboard_four_factors).
"""
from __future__ import annotations

from typing import Any

FACTOR_KEYS = ("efg", "tov", "oreb", "ftr")
POOL_SIZE = 14   # sim.game_player_pool: the top 14 by projected minutes make tonight's pool
# Free throws the engine keeps. A player's points are set before his shots, and on a night his made threes need more of
# his points than his free throws leave, free throws give way (offense.shooting_line, `drop`). Measured 2026-11-26 on
# the engine itself (real 2025-26 rosters and minutes, 6,960 games, the same pools as this projection): the box scores
# held 95.2% of the free throws their points imply. Without it the projection ran 1.3 above the engine's free-throw
# rate. tests/test_four_factor_projection.py checks the projection against the engine, so a change there shows.
FREE_THROWS_KEPT = 0.952


def _sim():
    from . import sim
    return sim


def projection_pool(roster_minutes: list[tuple[dict[str, Any], float]]) -> list[dict[str, Any]]:
    """Tonight's pool for (player, projected minutes): the top 14 with minutes, scaled to 240 (sim.game_player_pool)."""
    sim = _sim()
    rows = [(player, float(minutes)) for player, minutes in roster_minutes if float(minutes or 0.0) > 0]
    rows.sort(key=lambda row: (-row[1], str(row[0].get("id"))))
    pool = [{"player": player, "minutes": round(sim.clamp(minutes, 0.0, 42.0), 3), "actual": None}
            for player, minutes in rows[:POOL_SIZE]]
    return sim.normalize_minutes(pool)


def team_side(canonical: dict[str, Any], team: dict[str, Any], pool: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A team's pool, team features and players' engine features. None without new-ratings box rates."""
    sim = _sim()
    if not pool:
        return None
    players = []
    for item in pool:
        feat = sim.health_adjusted_player_features(sim.player_feature_vector(canonical, item["player"]).features, item)
        if feat.get("points_per36") is None or feat.get("three_per36") is None or not feat.get("two_pct"):
            return None
        players.append((item, feat))
    features = sim.game_team_features(None, canonical, team, pool, "sandbox-sim")
    return {"team": team, "pool": pool, "features": features, "players": players}


def oreb_rate(features: dict[str, float]) -> float:
    """The team's share of its own misses (box_variation.vary_box_score)."""
    return min(.38, max(.16, .24 + (float(features.get("offensive_rebounding", 50)) - 50) * .0022))


def expected_line(offense: dict[str, Any], defense: dict[str, Any], points: float, possessions: float) -> dict[str, float]:
    """One game's expected box-score totals for `offense` scoring `points` in `possessions` against `defense`."""
    sim = _sim()
    from .box_variation import MISS_FILL
    from .offense import FT_LEVEL
    own, opp = offense["features"], defense["features"]
    pressure = (float(opp.get("defensive_events", 60)) - 60) / 40
    rim = (float(opp.get("defense_rim", opp.get("rim_deterrence", 60))) - 60) / 40
    passing = (float(own.get("passing", 60)) - 60) / 40
    weights = [max(0.0, float(item.get("minutes") or 0.0)) * float(feat["points_per36"]) / 36.0
               for item, feat in offense["players"]]
    weight_total = sum(weights) or 1.0
    fta = ftm = fg3a = fg3m = turnovers = 0.0
    rooms, chances = [], []
    for (item, feat), weight in zip(offense["players"], weights):
        minutes = max(0.0, float(item.get("minutes") or 0.0))
        player_points = points * weight / weight_total
        player_fta = player_points * float(feat.get("fta_per_point") or 0.0) * FT_LEVEL * FREE_THROWS_KEPT
        player_ftm = player_fta * float(feat.get("ft_pct") or .75)
        player_fg3a = minutes * float(feat["three_per36"]) / 36.0
        player_fg3m = player_fg3a * float(feat.get("three_pct") or .35)
        fta += player_fta
        ftm += player_ftm
        fg3a += player_fg3a
        fg3m += player_fg3m
        rooms.append(max(0.0, player_points - player_ftm - 3 * player_fg3m))
        paint_share = float(feat.get("roll_share", .15)) + float(feat.get("post_share", .15))
        chances.append(min(.82, max(.25, float(feat.get("two_pct") or .51) - rim * (.020 + paint_share * .025))))
        turnovers += minutes * sim.turnover_rate_per_minute(feat) * max(.5, 1 + pressure * .22 - passing * .12)
    # Two-point makes are what the team's points leave after its free throws and threes (the points hold the threes:
    # sim.make_room_for_threes), shared like each player's own room.
    fg2m = max(0.0, points - ftm - 3 * fg3m) / 2
    room_total = sum(rooms) or 1.0
    own_misses = sum(fg2m * room / room_total * (1 - chance) / chance for room, chance in zip(rooms, chances))
    rate = oreb_rate(own)
    fgm = fg2m + fg3m
    mandatory = fg3a + fg2m
    target_fga = max(mandatory, (possessions - turnovers - .44 * fta - rate * fgm) / (1 - rate))
    misses = max(0.0, own_misses + MISS_FILL * (target_fga - mandatory - own_misses) + rim * 2.0)
    fga = mandatory + misses
    return {"points": points, "possessions": possessions, "fgm": fgm, "fga": fga, "fg3m": fg3m, "fg3a": fg3a,
            "fta": fta, "ftm": ftm, "turnovers": turnovers, "oreb_rate": rate, "misses": fga - fgm}


def game_lines(canonical: dict[str, Any], home: dict[str, Any], away: dict[str, Any], home_coach: Any,
               away_coach: Any) -> tuple[dict[str, float], dict[str, float]]:
    """Expected home and away lines for one game (sim.draw_both_scores with SHARED_PACE, without the draws)."""
    sim = _sim()
    hf, af = home["features"], away["features"]
    home_mean = sim.draw_team_score(canonical, hf, af, home_coach, away_coach, None, is_home=True, mean_only=True)
    away_mean = sim.draw_team_score(canonical, af, hf, away_coach, home_coach, None, is_home=False, mean_only=True)
    if sim.SHARED_PACE:
        pace = (home_mean["expected_possessions"] + away_mean["expected_possessions"]) / 2.0
        home_pace = away_pace = pace
    else:
        home_pace, away_pace = home_mean["expected_possessions"], away_mean["expected_possessions"]
    home_pace, away_pace = sim.clamp(home_pace, 84, 120), sim.clamp(away_pace, 84, 120)
    home_line = expected_line(home, away, home_pace * home_mean["mean_off_rating"] / 100, home_pace)
    away_line = expected_line(away, home, away_pace * away_mean["mean_off_rating"] / 100, away_pace)
    return home_line, away_line


def factors(lines: list[dict[str, float]], opponent_lines: list[dict[str, float]]) -> dict[str, float]:
    """Four Factors (fractions) of summed lines, the way dashboard_four_factors sums a season's box scores."""
    total = {key: sum(line[key] for line in lines) for key in ("fgm", "fga", "fg3m", "fta", "turnovers")}
    oreb = sum(line["misses"] * line["oreb_rate"] for line in lines)
    # The defense rebounds the rest of the same misses (box_variation.vary_box_score; both carry the same player share).
    opponent_dreb = sum(line["misses"] * (1 - line["oreb_rate"]) for line in lines)
    fga = max(1.0, total["fga"])
    return {
        "efg": (total["fgm"] + 0.5 * total["fg3m"]) / fga,
        "tov": total["turnovers"] / max(1.0, total["fga"] + 0.44 * total["fta"] + total["turnovers"]),
        "oreb": oreb / max(1.0, oreb + opponent_dreb),
        "ftr": total["fta"] / fga,
    }


def season_projection(canonical: dict[str, Any], team_id: str, sides: dict[str, dict[str, Any]],
                      coaches: dict[str, Any]) -> dict[str, Any] | None:
    """`team_id`'s offense and defense over one home and one away game against every other team in `sides`."""
    side = sides.get(team_id)
    if side is None:
        return None
    offense, defense = [], []
    for other_id in sorted(sides):
        if other_id == team_id:
            continue
        other = sides[other_id]
        for home, away in ((side, other), (other, side)):
            home_line, away_line = game_lines(canonical, home, away, coaches.get(home["team"]["id"]),
                                              coaches.get(away["team"]["id"]))
            mine, theirs = (home_line, away_line) if home is side else (away_line, home_line)
            offense.append(mine)
            defense.append(theirs)
    if not offense:
        return None
    games = len(offense)
    possessions = sum(line["possessions"] for line in offense) / games
    return {
        "offense": factors(offense, defense),
        "defense": factors(defense, offense),
        "games": games,
        "possessions": possessions,
        "offensive_rating": sum(line["points"] for line in offense) / max(1.0, sum(line["possessions"] for line in offense)) * 100,
        "defensive_rating": sum(line["points"] for line in defense) / max(1.0, sum(line["possessions"] for line in defense)) * 100,
    }


def display(values: dict[str, float]) -> dict[str, float]:
    """The Profile tab's scale: percent with one decimal (free-throw rate as attempts per 100 field-goal attempts)."""
    return {key: round(float(values[key]) * 100.0, 1) for key in FACTOR_KEYS}


def league_sides(canonical: dict[str, Any], save: dict[str, Any],
                 rosters: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, dict[str, Any]]:
    """Every team's projection side in a save's league: its roster (or `rosters[team_id]`, whose players then leave
    any other team) over the minutes the coach projects for it (save.team_rotation_projection)."""
    from .save import team_rotation_projection
    rosters = rosters or {}
    claimed = {player.get("id"): team_id for team_id, roster in rosters.items() for player in roster}
    by_team: dict[str, list[dict[str, Any]]] = {}
    for player in canonical.get("players", []):
        team_id = player.get("team_id")
        if team_id in rosters or player.get("id") in claimed:
            continue
        by_team.setdefault(team_id, []).append(player)
    sides: dict[str, dict[str, Any]] = {}
    for team in canonical.get("teams", []):
        team_id = team["id"]
        roster = list(rosters[team_id]) if team_id in rosters else by_team.get(team_id, [])
        projection = team_rotation_projection(canonical, save, team_id, integer=False, _roster=roster) if roster else {}
        side = team_side(canonical, team, projection_pool([(player, projection.get(player["id"], 0.0))
                                                           for player in roster]))
        if side is not None:
            sides[team_id] = side
    return sides


def _projection_payload(canonical: dict[str, Any], team_id: str, sides: dict[str, dict[str, Any]],
                        coaches: dict[str, Any]) -> dict[str, Any] | None:
    season = season_projection(canonical, team_id, sides, coaches)
    if season is None:
        return None
    return {
        "team_id": team_id,
        "source": "roster_projection",
        "offense": display(season["offense"]),
        "defense": display(season["defense"]),
        "offensive_rating": round(season["offensive_rating"], 1),
        "defensive_rating": round(season["defensive_rating"], 1),
        "net_rating": round(season["offensive_rating"] - season["defensive_rating"], 1),
        "possessions": round(season["possessions"], 1),
        "games": season["games"],
        "minutes": [{"player_id": item["player"]["id"], "name": item["player"].get("name"),
                     "minutes": round(float(item["minutes"]), 1)} for item in sides[team_id]["pool"]],
        "fractions": {"offense": dict(season["offense"]), "defense": dict(season["defense"])},
    }


def project_four_factors(canonical: dict[str, Any], save: dict[str, Any], team_id: str,
                         roster: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Projected Four Factors for `team_id` with `roster` (default: its players in `canonical`), offense and defense.

    canonical: the save's league (save.canonical_with_save). The coach's projected minutes for that roster weight the
    engine's own player inputs; the season is one home and one away game against every other team as it stands.
    Returns None when the league has no new-ratings box rates (older rating set)."""
    from .save import save_coach_ratings
    sides = league_sides(canonical, save, {team_id: roster} if roster is not None else None)
    return _projection_payload(canonical, team_id, sides, save_coach_ratings(canonical, save))


def project_league_four_factors(canonical: dict[str, Any], save: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """project_four_factors for every team at once (one set of team features)."""
    from .save import save_coach_ratings
    sides = league_sides(canonical, save)
    coaches = save_coach_ratings(canonical, save)
    payloads = {team_id: _projection_payload(canonical, team_id, sides, coaches) for team_id in sides}
    return {team_id: payload for team_id, payload in payloads.items() if payload is not None}
