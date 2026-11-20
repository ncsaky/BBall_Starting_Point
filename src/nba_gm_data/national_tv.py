"""National TV slate for generated seasons (OVERNIGHT-REST-GAMES, 2026-11-20).

The real 2025-26 slate (data/research/national_tv_2025_26.json, from ESPN's public scoreboard): 246 regular-season
games on ESPN, ABC, NBC, Peacock or Prime Video (20% of the 1,230), plus 63 games on NBA TV alone, which are not
counted here (rest did not drop in them). How the league picks them shows in the team counts: the teams people want to
watch get most of the slate, the rest almost none.
  - New York 35, Oklahoma City 34, Lakers 34, San Antonio 32, Golden State 32, Houston 30, Denver 29, Minnesota 29,
    Boston 29, Cleveland 28 (the top ten: 63% of all national slots); New Orleans 0, Brooklyn 1, Utah, Washington 2,
    Indiana 3 (Haliburton out for the season), Chicago, Toronto 4 (the bottom ten: 7%).
  - Three things drive it: last season's results and the roster's strength (Oklahoma City, Cleveland, Houston, Denver),
    star power (San Antonio with Wembanyama: 34 wins the season before, 32 national games) and market or brand
    (New York, the Lakers, Golden State, Boston; Philadelphia got 18 after a 24-win season).
  - By month: October 16, November 32, December 33 (all five Christmas games), January 48, February 44, March 55,
    April 18. Usually two games a night (94 of 122 nights), never more than four outside Christmas. Fewer second nights
    of back-to-backs: 12.4% of national team-games against 19.5% of the rest.

The game's slate follows the same rule: each team's appeal is its roster strength (blended with last season's record
when there is one), its star power and its market. Teams are ranked by appeal and the k-th most appealing team is given
the k-th largest real count (35, 34, 34, 32 ... 1, 0), so the spread across teams matches 2025-26. Games are then
picked one at a time, always the one that most helps both teams reach their counts (ties: the more appealing matchup,
with a little seeded noise), within each month's real count and two games a night (three at most). Every Christmas game
is national, as in real life. The market weights are a judgment call (no public popularity data was used); everything
else comes from the roster and the standings.
"""
from __future__ import annotations

from datetime import date, timedelta
import random
from statistics import mean, pstdev
from typing import Any

NATIONAL_SHARE = 246 / 1230
MONTH_COUNTS = {10: 16, 11: 32, 12: 33, 1: 48, 2: 44, 3: 55, 4: 18}   # real 2025-26, sums to 246
PER_NIGHT = 2
PER_NIGHT_MAX = 3
CHRISTMAS_MAX = 5
# The league keeps national games off second nights of back-to-backs where it can: 12.4% of real national team-games
# were second nights against 19.5% of the others. Skipping that share of such candidates reproduces it.
SECOND_NIGHT_SKIP = 0.45
# Real 2025-26 national games per team, all 30 (the k-th most appealing team gets the k-th largest).
REAL_TEAM_COUNTS = (35, 34, 34, 32, 32, 30, 29, 29, 29, 28, 22, 20, 19, 18, 17, 14, 12, 9, 8, 7, 7, 6, 5, 4, 4, 3, 2, 2, 1, 0)
# Judgment: national brands get slots whatever their record (New York, the Lakers, Golden State, Boston: 29-35 national
# games in 2025-26); big markets a little more. In units of team-appeal standard deviations.
MARKET_BONUS = {"NYK": 1.0, "LAL": 1.0, "GSW": 0.9, "BOS": 0.7, "PHI": 0.4, "LAC": 0.3, "CHI": 0.3, "MIA": 0.3, "DAL": 0.3}
WEIGHT_STRENGTH = 1.0
WEIGHT_STARS = 0.8
NOISE = 0.35


def _z(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    mu, sd = mean(values.values()), pstdev(values.values()) or 1.0
    return {k: (v - mu) / sd for k, v in values.items()}


def team_appeal(canonical: dict[str, Any], records: dict[str, dict[str, Any]] | None = None,
                overall: dict[str, float] | None = None) -> dict[str, float]:
    """Team id -> appeal (standard-deviation units): roster strength (the best eight players' overall rating, blended
    half and half with last season's winning percentage when given), star power (the best two players) and market."""
    if overall is None:
        from .save import player_attribute_summary
        overall = {}
        for player in canonical.get("players", []):
            if player.get("team_id") and not player.get("_inactive_player"):
                try:
                    overall[player["id"]] = float(player_attribute_summary(canonical, player["id"]).get("overall") or 0.0)
                except Exception:
                    continue
    by_team: dict[str, list[float]] = {}
    for player in canonical.get("players", []):
        if player.get("team_id") and player["id"] in overall:
            by_team.setdefault(player["team_id"], []).append(overall[player["id"]])
    teams = [t["id"] for t in canonical.get("teams", []) if t.get("id")]
    strength = {t: mean(sorted(by_team.get(t, [0.0]), reverse=True)[:8]) for t in teams}
    stars = {t: mean(sorted(by_team.get(t, [0.0]), reverse=True)[:2]) for t in teams}
    strength_z = _z(strength)
    if records:
        pct = {t: (int((records.get(t) or {}).get("wins") or 0) + 5.0)
               / (int((records.get(t) or {}).get("wins") or 0) + int((records.get(t) or {}).get("losses") or 0) + 10.0)
               for t in teams}
        record_z = _z(pct)
        strength_z = _z({t: 0.5 * strength_z[t] + 0.5 * record_z[t] for t in teams})
    stars_z = _z(stars)
    abbrev = {t["id"]: t.get("abbrev") for t in canonical.get("teams", [])}
    return {t: WEIGHT_STRENGTH * strength_z[t] + WEIGHT_STARS * stars_z[t] + MARKET_BONUS.get(str(abbrev.get(t)), 0.0)
            for t in teams}


def mark_national_tv(games: list[dict[str, Any]], appeal_by_espn: dict[str, float], season: str) -> int:
    """Set game["national_tv"] = True on the season's national slate (and drop the flag elsewhere). appeal_by_espn:
    ESPN team id -> team appeal. Deterministic per season. Returns the number of national games."""
    rng = random.Random(f"{season}:national_tv")
    total = round(len(games) * NATIONAL_SHARE)
    scale = total / sum(MONTH_COUNTS.values())
    quota = {m: round(n * scale) for m, n in MONTH_COUNTS.items()}
    teams = sorted(appeal_by_espn, key=lambda t: (-appeal_by_espn[t], t))
    shares = sorted(REAL_TEAM_COUNTS, reverse=True)
    target = {t: shares[min(i, len(shares) - 1)] * scale * len(shares) / max(1, len(teams)) for i, t in enumerate(teams)}
    count = {t: 0 for t in teams}
    per_night: dict[str, int] = {}
    per_month: dict[int, int] = {}
    candidates = []
    ordered = sorted(games, key=lambda g: (str(g.get("gameDate")), str(g.get("externalGameId"))))
    played: dict[str, set[str]] = {}
    for game in ordered:
        for key in ("homeTeamId", "awayTeamId"):
            played.setdefault(str(game.get(key)), set()).add(str(game.get("gameDate"))[:10])
    for game in ordered:
        game.pop("national_tv", None)
        home, away = str(game.get("homeTeamId")), str(game.get("awayTeamId"))
        day = str(game.get("gameDate"))[:10]
        appeal = appeal_by_espn.get(home, 0.0) + appeal_by_espn.get(away, 0.0) + rng.gauss(0.0, NOISE)
        yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        second_night = any(yesterday in played.get(t, ()) for t in (home, away))
        if second_night and rng.random() < SECOND_NIGHT_SKIP and day[5:] != "12-25":
            continue
        if day[5:] != "12-25":
            candidates.append([appeal, game, home, away, day, int(day[5:7])])
        elif per_night.get(day, 0) < CHRISTMAS_MAX:
            game["national_tv"] = True
            per_night[day] = per_night.get(day, 0) + 1
            per_month[12] = per_month.get(12, 0) + 1
            for t in (home, away):
                count[t] = count.get(t, 0) + 1
    chosen = sum(1 for g in games if g.get("national_tv"))
    for cap in (PER_NIGHT, PER_NIGHT_MAX):
        while chosen < total:
            best, best_key = None, None
            for item in candidates:
                appeal, game, home, away, day, month = item
                if game.get("national_tv") or per_month.get(month, 0) >= quota.get(month, 0) or per_night.get(day, 0) >= cap:
                    continue
                need_h = target.get(home, 0.0) - count.get(home, 0)
                need_a = target.get(away, 0.0) - count.get(away, 0)
                if min(need_h, need_a) <= 0.0:
                    continue
                key = (round(min(need_h, need_a) + 0.5 * max(need_h, need_a), 1), appeal)
                if best_key is None or key > best_key:
                    best, best_key = item, key
            if best is None:
                break
            _, game, home, away, day, month = best
            game["national_tv"] = True
            per_night[day] = per_night.get(day, 0) + 1
            per_month[month] = per_month.get(month, 0) + 1
            count[home] = count.get(home, 0) + 1
            count[away] = count.get(away, 0) + 1
            chosen += 1
    return chosen


def mark_schedule_national_tv(schedule: dict[str, Any], canonical: dict[str, Any],
                              records: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Mark a generated season schedule's national TV games from the league as it stands (rosters, and last season's
    records at a rollover). Returns the schedule, with "national_tv_games" set."""
    from .health import espn_team_id_map_from_canonical
    appeal = team_appeal(canonical, records)
    by_espn = {espn: appeal.get(team["id"], 0.0) for espn, team in espn_team_id_map_from_canonical(canonical).items()}
    schedule["national_tv_games"] = mark_national_tv(schedule.get("games") or [], by_espn, str(schedule.get("season") or ""))
    return schedule


def national_tv_counts(games: list[dict[str, Any]]) -> dict[str, int]:
    """ESPN team id -> national TV games (for checks and the report)."""
    out: dict[str, int] = {}
    for game in games:
        if game.get("national_tv"):
            for key in ("homeTeamId", "awayTeamId"):
                out[str(game.get(key))] = out.get(str(game.get(key)), 0) + 1
    return out


__all__ = ["team_appeal", "mark_national_tv", "mark_schedule_national_tv", "national_tv_counts"]
