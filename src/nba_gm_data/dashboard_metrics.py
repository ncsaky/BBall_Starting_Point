"""Season-start references and live award-watch rankings, separate from award results."""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any


def award_score(award: str, ratings: dict[str, Any], totals: dict[str, Any], win_pct: float) -> float:
    games = max(1, int(totals.get("games") or 0))
    def pg(key: str) -> float:
        return float(totals.get(key) or 0) / games
    overall = float(ratings.get("overall") or 50)
    if award == "DPOY":
        return float(ratings.get("defense") or overall) * .58 + float(ratings.get("rim_deterrence") or overall) * .55 + pg("blocks") * 3.2 + pg("steals") * 2.6 + win_pct * 5
    if award == "ROTY":
        return pg("points") * 1.18 + pg("assists") * .92 + pg("rebounds") * .72 + overall * .48 + pg("minutes") * .18
    return pg("points") * 1.25 + pg("assists") * 1.08 + pg("rebounds") * .66 + overall * .42 + win_pct * 17


def build_award_baselines(active: dict[str, Any], save: dict[str, Any]) -> dict[str, Any]:
    from .save import CANONICAL_SEASON, is_rookie_for_awards, player_attribute_summary

    season = str((save.get("meta") or {}).get("season") or CANONICAL_SEASON)
    previous = next((item for item in reversed(save.get("season_history", [])) if str(item.get("season") or "") < season), {})
    prior_stats = previous.get("player_season_stats") or {}
    previous_awards = {(row.get("award"), row.get("player_id")): float(row.get("score") or 0) for row in previous.get("awards", [])}
    players = [p for p in active.get("players", []) if p.get("team_id")]
    attributes = {p["id"]: player_attribute_summary(active, p["id"]) for p in players}
    strengths = defaultdict(list)
    for player in players:
        strengths[player["team_id"]].append(float(attributes[player["id"]].get("overall") or 50))
    team_strength = {team: sum(sorted(values, reverse=True)[:8]) / min(8, len(values)) for team, values in strengths.items()}
    mean_strength = sum(team_strength.values()) / max(1, len(team_strength))
    result = {}
    for award in ("MVP", "DPOY", "ROTY"):
        scores = {}
        for player in players:
            if award == "ROTY" and not is_rookie_for_awards(player, season, save):
                continue
            ratings = attributes[player["id"]]
            expected_win_pct = max(.2, min(.8, .5 + (team_strength[player["team_id"]] - mean_strength) / 50))
            totals = prior_stats.get(player["id"], {})
            # New leagues and rookies have no vote history: use their preseason rating proxy.
            proxy = award_score(award, ratings, totals, expected_win_pct)
            age = float(player.get("age") or 27)
            growth = max(.92, min(1.08, 1 + (26 - age) * .006))
            prior_votes = previous_awards.get((award, player["id"]), proxy)
            scores[player["id"]] = prior_votes * growth * (.85 + .3 * expected_win_pct)
        ordered = sorted(scores, key=lambda player_id: (-scores[player_id], player_id))
        result[award] = {player_id: {"rank": index + 1, "score": round(scores[player_id], 3)} for index, player_id in enumerate(ordered)}
    return result


AWARD_CARD_STATS = ("points", "rebounds", "assists", "steals", "blocks")


def award_watch_payload(rows: list[dict[str, Any]], save: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    season = str((save.get("meta") or {}).get("season") or "")
    baselines = (save.get("award_preseason_baselines") or {}).get(season, {})
    records = save.get("team_records") or {}
    totals = save.get("player_season_stats") or {}
    season_has_games = any(int(item.get("games") or 0) for item in totals.values())
    current_date = str((save.get("state") or {}).get("current_date") or "")[:10]
    try:
        previous_week_date = (date.fromisoformat(current_date) - timedelta(days=7)).isoformat()
    except ValueError:
        previous_week_date = ""
    races = {}
    for award in ("MVP", "DPOY", "ROTY"):
        candidates = []
        for row in rows:
            if award == "ROTY" and not row.get("rookie"):
                continue
            record = records.get(row["team_id"], {})
            games = int(record.get("wins") or 0) + int(record.get("losses") or 0)
            baseline = baselines.get(award, {}).get(row["player_id"])
            player_totals = totals.get(row["player_id"], {})
            score = award_score(award, row.get("award_ratings", row["values"]), player_totals, float(record.get("wins") or 0) / games if games else .5)
            if not season_has_games:
                score = (baseline or {}).get("score", score)
            candidates.append({key: row[key] for key in ("player_id", "player_name", "headshot_url", "team_id", "team_abbrev")})
            values = row.get("values") or {}
            played = int(player_totals.get("games") or 0) > 0
            candidates[-1].update(
                score=score,
                season_start_rank=(baseline or {}).get("rank"),
                _award_ratings=row.get("award_ratings", row.get("values", {})),
                # Display only (the award cards' stat line): ratings always, per-game numbers once he has played.
                stats={
                    "overall": values.get("overall"),
                    "defense": values.get("defense"),
                    **({key: values.get(key) for key in AWARD_CARD_STATS} if played else {}),
                },
            )
        candidates.sort(key=lambda row: (-row["score"], row["player_id"]))
        previous_ranks = _award_ranks_as_of(award, candidates, save, previous_week_date)
        for rank, row in enumerate(candidates, 1):
            row["rank"] = rank
            previous_rank = previous_ranks.get(row["player_id"])
            row["previous_week_rank"] = previous_rank
            row["rank_change"] = previous_rank - rank if previous_rank is not None else None
            row.pop("_award_ratings", None)
        races[award] = candidates[:10]
    return races


def _award_ranks_as_of(
    award: str,
    candidates: list[dict[str, Any]],
    save: dict[str, Any],
    cutoff: str,
) -> dict[str, int]:
    """Rank this week's candidates using only games completed by the prior week."""
    season = str((save.get("meta") or {}).get("season") or "")
    preseason = ((save.get("award_preseason_baselines") or {}).get(season) or {}).get(award, {})
    if not cutoff:
        return {player_id: int(entry.get("rank") or 0) for player_id, entry in preseason.items() if entry.get("rank")}

    player_logs = [
        log for log in save.get("player_game_logs", []) or []
        if str(log.get("date") or "")[:10] and str(log.get("date") or "")[:10] <= cutoff
    ]
    if not player_logs:
        return {player_id: int(entry.get("rank") or 0) for player_id, entry in preseason.items() if entry.get("rank")}

    prior_totals: dict[str, dict[str, float]] = defaultdict(lambda: {
        "games": 0.0, "minutes": 0.0, "points": 0.0, "rebounds": 0.0,
        "assists": 0.0, "steals": 0.0, "blocks": 0.0,
    })
    prior_team: dict[str, str] = {}
    for log in sorted(player_logs, key=lambda item: (str(item.get("date") or ""), str(item.get("id") or ""))):
        player_id = str(log.get("player_id") or "")
        if not player_id:
            continue
        prior_totals[player_id]["games"] += 1
        for stat in ("minutes", "points", "rebounds", "assists", "steals", "blocks"):
            prior_totals[player_id][stat] += float(log.get(stat) or 0.0)
        if log.get("team_id"):
            prior_team[player_id] = str(log["team_id"])

    team_records: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0})
    for log in save.get("team_game_logs", []) or []:
        if str(log.get("date") or "")[:10] > cutoff:
            continue
        team_id = str(log.get("team_id") or "")
        if not team_id:
            continue
        key = "wins" if str(log.get("result") or "").upper() == "W" else "losses"
        team_records[team_id][key] += 1

    scored = []
    for row in candidates:
        player_id = str(row.get("player_id") or "")
        team_id = prior_team.get(player_id, str(row.get("team_id") or ""))
        record = team_records.get(team_id, {})
        games = int(record.get("wins", 0)) + int(record.get("losses", 0))
        win_pct = record.get("wins", 0) / games if games else 0.5
        score = award_score(
            award,
            row.get("_award_ratings", row.get("award_ratings", row.get("values", {}))),
            prior_totals.get(player_id, {}),
            win_pct,
        )
        scored.append((player_id, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return {player_id: index + 1 for index, (player_id, _score) in enumerate(scored)}
