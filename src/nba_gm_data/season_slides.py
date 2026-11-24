"""Season slideshows: the year-end recap (built when the playoffs end) and the preseason outlook (built at the Oct 1
rollover, or when a new career starts). Each is a list of slides of plain data that the browser draws.

Storage (additive save field ``season_slideshows``): {"recaps": {season: recap}, "outlooks": {season: outlook},
"seen": {"recap:2026-27": date, ...}}. A recap is also copied into its season's history entry at the rollover.

Everything shown is read from what the game already decided: the season's awards, standings, box-score totals,
trade logs (each team's own evaluation), staff events, Team Signals and contracts. Nothing here changes a result.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
REAL_SUMMARY_PATH = ROOT / "data/canonical/real_season_summary_2025_26.json"
LOG = logging.getLogger(__name__)

COACHING_SLOTS = ("head_coach", "offensive_coordinator", "defensive_coordinator")
SLOT_LABELS = {"head_coach": "Head Coach", "offensive_coordinator": "Offensive Coordinator",
               "defensive_coordinator": "Defensive Coordinator"}
LEADER_STATS = (("points", "Points"), ("rebounds", "Rebounds"), ("assists", "Assists"), ("steals", "Steals"),
                ("blocks", "Blocks"), ("fg3m", "Three-pointers made"), ("screen_assists", "Screen assists"))
ROUND_RANK = {"lottery": 0, "play_in": 1, "first_round": 2, "conference_semifinals": 3, "conference_finals": 4, "finals": 5,
              "champion": 6}
ROUND_WORDS = {"lottery": "Missed the playoffs", "play_in": "Lost in the play-in", "first_round": "Lost in the first round",
               "conference_semifinals": "Lost in the second round", "conference_finals": "Lost in the conference finals",
               "finals": "Lost in the Finals", "champion": "Won the title"}
PHASE_WORDS = {"peak": "contending", "entering": "on the rise", "exiting": "past its peak", "rebuilding": "rebuilding"}
AWARD_ORDER = ["MVP", "FMVP", "DPOY", "ROTY", "SMOY", "MIP"]
INJURY_SLIDE_MIN_GAMES = 20
REGULAR_SEASON_START = "10-21"


@lru_cache(maxsize=1)
def real_season_summary() -> dict[str, Any]:
    """The real 2025-26 regular season (per-team minutes stints, records, player totals), for a new save's first
    outlook and Most Improved. Built by scripts/research/build_real_season_summary.py."""
    try:
        return json.loads(REAL_SUMMARY_PATH.read_text())
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------------------------------------- storage


def slideshow_store(save: dict[str, Any]) -> dict[str, Any]:
    store = save.setdefault("season_slideshows", {})
    store.setdefault("recaps", {})
    store.setdefault("outlooks", {})
    store.setdefault("seen", {})
    return store


def stored_recap(save: dict[str, Any], season: str) -> dict[str, Any] | None:
    recap = ((save.get("season_slideshows") or {}).get("recaps") or {}).get(season)
    if recap:
        return recap
    entry = next((row for row in save.get("season_history") or [] if str(row.get("season")) == season), None)
    return (entry or {}).get("recap")


def stored_outlook(save: dict[str, Any], season: str) -> dict[str, Any] | None:
    return ((save.get("season_slideshows") or {}).get("outlooks") or {}).get(season)


def available_slideshows(save: dict[str, Any]) -> list[dict[str, str]]:
    """Every slideshow this save can reopen, newest first."""
    seasons_with_recaps = {str(row.get("season")) for row in save.get("season_history") or [] if row.get("recap")}
    store = save.get("season_slideshows") or {}
    seasons_with_recaps |= set((store.get("recaps") or {}).keys())
    rows = [{"kind": "recap", "season": season, "label": f"{season} Year-End Recap"} for season in seasons_with_recaps]
    rows += [{"kind": "outlook", "season": season, "label": f"{season} Preseason Outlook"} for season in (store.get("outlooks") or {})]
    return sorted(rows, key=lambda row: (row["season"], row["kind"] == "outlook"), reverse=True)


def outlook_due(save: dict[str, Any]) -> bool:
    """The preseason outlook belongs to Oct 1 after a rollover, and to a new career's first day."""
    state = save.get("state") or {}
    if state.get("phase") == "preseason":
        return True
    fresh = not (save.get("season_history") or []) and not ((save.get("schedule_state") or {}).get("simulated_game_ids"))
    return fresh and str(state.get("current_date") or "") == str((save.get("meta") or {}).get("gameplay_start_date") or "")


def pending_slideshow(save: dict[str, Any]) -> dict[str, str] | None:
    """The slideshow that should open by itself now (once): the recap once the Finals are over and before the
    lottery, or the outlook at the start of a season."""
    season = str((save.get("meta") or {}).get("season") or "")
    seen = (save.get("season_slideshows") or {}).get("seen") or {}
    playoffs = save.get("playoff_state") or {}
    phase = (save.get("state") or {}).get("phase")
    if (playoffs.get("status") == "completed" and phase in {"play_in", "playoffs", "draft_lottery"}
            and f"recap:{season}" not in seen and stored_recap(save, season)):
        return {"kind": "recap", "season": season}
    if outlook_due(save) and f"outlook:{season}" not in seen:
        return {"kind": "outlook", "season": season}
    return None


def mark_seen(save: dict[str, Any], kind: str, season: str) -> None:
    slideshow_store(save)["seen"][f"{kind}:{season}"] = str((save.get("state") or {}).get("current_date") or "")


# --------------------------------------------------------------------------------------------- shared helpers


def _season_years(season: str) -> tuple[int, int]:
    start = int(str(season)[:4])
    return start, start + 1


def combined_rows(save: dict[str, Any], save_path: str | Path | None, kind: str, *, date_from: str | None = None,
                  date_to: str | None = None, player_id: str | None = None) -> list[dict[str, Any]]:
    """Rows of one history kind from the save file's history database plus the rows still in memory."""
    from .history_store import load_history_records, record_date, record_id

    rows: dict[str, dict[str, Any]] = {}
    if save_path is not None and save.get("history_store"):
        try:
            for row in load_history_records(save_path, save, kind, player_id=player_id, event_date_from=date_from):
                rows[record_id(kind, row)] = row
        except Exception as exc:  # a missing or unreadable history file leaves only in-memory rows
            LOG.warning("slideshow history read failed: %s", exc)
    memory = list(save.get(kind) or []) + list(((save.get("_history_to_archive") or {}).get(kind)) or [])
    for row in memory:
        if not isinstance(row, dict) or (player_id is not None and row.get("player_id") != player_id):
            continue
        rows[record_id(kind, row)] = row
    out = []
    for row in rows.values():
        day = record_date(row)
        if (date_from and day < date_from) or (date_to and day > date_to):
            continue
        out.append(row)
    return sorted(out, key=lambda row: (record_date(row), str(row.get("id") or "")))


def _team_maps(active: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    teams = {team["id"]: team for team in active.get("teams", [])}
    by_abbrev = {team.get("abbrev"): team["id"] for team in teams.values()}
    return teams, by_abbrev


def _team_ref(teams: dict[str, dict[str, Any]], team_id: str | None) -> dict[str, Any]:
    team = teams.get(team_id or "") or {}
    return {"id": team_id, "abbrev": team.get("abbrev") or str(team_id or "").replace("team_", "").upper(),
            "name": team.get("name") or team.get("abbrev") or team_id, "conference": team.get("conference")}


def _player_ref(active: dict[str, Any], player_id: str, fallback_name: str | None = None) -> dict[str, Any]:
    from .save import player_display_attribute_summary

    player = next((row for row in active.get("players", []) if row.get("id") == player_id), None)
    if not player:
        return {"id": player_id, "name": fallback_name or player_id, "team_id": None}
    # The one OVR display scale, the same number as the card and tables (OVERALL-SCALE, 2026-11-21).
    overall = player_display_attribute_summary(active, player_id).get("overall")
    return {"id": player_id, "name": player.get("name") or fallback_name, "team_id": player.get("team_id"),
            "position": player.get("position"), "age": player.get("display_age", player.get("age")),
            "headshot_url": player.get("headshot_url"), "overall": overall,
            "off_role": player.get("primary_off_role"), "def_role": player.get("primary_def_role")}


def _per_game(totals: dict[str, Any], key: str) -> float:
    games = max(1, int(totals.get("games") or 0))
    return round(float(totals.get(key) or 0.0) / games, 1)


def _safe(builder: Callable[[], dict[str, Any]], key: str, title: str) -> dict[str, Any]:
    """One slide; a slide that cannot be built says so instead of breaking the whole slideshow."""
    try:
        return builder()
    except Exception as exc:  # pragma: no cover - logged and shown as an empty slide
        LOG.exception("slideshow slide %s failed", key)
        return {"key": key, "title": title, "unavailable": f"This slide could not be built ({type(exc).__name__})."}


def _record_rows(active: dict[str, Any], records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    teams, _ = _team_maps(active)
    rows = []
    for team_id, record in records.items():
        if team_id not in teams:
            continue
        wins, losses = int(record.get("wins") or 0), int(record.get("losses") or 0)
        games = wins + losses
        rows.append({"team_id": team_id, "wins": wins, "losses": losses, "games": games,
                     "win_pct": round(wins / games, 3) if games else 0.0,
                     "point_diff": round(float(record.get("points_for") or 0) - float(record.get("points_against") or 0), 1),
                     "points_for": float(record.get("points_for") or 0), "points_against": float(record.get("points_against") or 0),
                     "conference": teams[team_id].get("conference")})
    return rows


def _rank_by_record(rows: list[dict[str, Any]], teams: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (-row["win_pct"], -row["point_diff"], teams.get(row["team_id"], {}).get("abbrev", "")))


# --------------------------------------------------------------------------------------------- year-end recap


def team_postseason_results(state: dict[str, Any]) -> dict[str, str]:
    """How far each team went: champion, the round it lost in, or the play-in."""
    out: dict[str, str] = {}
    for conference in (state.get("play_in") or {}).values():
        for team_id in (conference.get("teams") or {}).values():
            out[team_id] = "play_in"
    for series in state.get("series") or []:
        for team_id in series.get("team_ids") or []:
            if ROUND_RANK.get(series.get("round"), 0) >= ROUND_RANK.get(out.get(team_id, "lottery"), 0):
                out[team_id] = series.get("round")
    champion = state.get("champion_team_id")
    if champion:
        out[champion] = "champion"
    return out


def build_year_end_recap(canonical: dict[str, Any], save: dict[str, Any], save_path: str | Path | None = None) -> dict[str, Any]:
    from .save import canonical_with_save

    active = canonical_with_save(canonical, save)
    season = str((save.get("meta") or {}).get("season") or "")
    user_team_id = str((save.get("meta") or {}).get("user_team_id") or "")
    context = {"active": active, "save": save, "save_path": save_path, "season": season, "user": user_team_id,
               "teams": _team_maps(active)[0], "results": team_postseason_results(save.get("playoff_state") or {})}
    slides = [
        _safe(lambda: recap_champion_slide(context), "champion", "Champion"),
        _safe(lambda: recap_standings_slide(context), "standings", "Final standings"),
        _safe(lambda: recap_awards_slide(context), "awards", "Awards"),
        _safe(lambda: recap_leaders_slide(context), "leaders", "League leaders"),
        _safe(lambda: recap_your_season_slide(context), "your_season", "Your season"),
        _safe(lambda: recap_trades_slide(context), "trades", "Biggest trades"),
        _safe(lambda: recap_coaching_slide(context), "coaching", "Biggest coaching changes"),
        _safe(lambda: recap_free_agents_slide(context), "free_agents", "Top upcoming free agents"),
        _safe(lambda: recap_look_ahead_slide(context), "look_ahead", "Looking ahead"),
    ]
    return {"kind": "recap", "season": season, "built_on": (save.get("state") or {}).get("current_date"),
            "user_team_id": user_team_id, "title": f"{season} Year-End Recap", "slides": slides}


def recap_champion_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    save, teams = ctx["save"], ctx["teams"]
    state = save.get("playoff_state") or {}
    champion = state.get("champion_team_id")
    finals = next((row for row in state.get("series") or [] if row.get("round") == "finals"), {})
    opponent = next((team for team in finals.get("team_ids") or [] if team != champion), None)
    wins = finals.get("wins") or {}
    path = []
    for series in sorted((row for row in state.get("series") or [] if champion in (row.get("team_ids") or [])),
                         key=lambda row: ROUND_RANK.get(row.get("round"), 0)):
        other = next((team for team in series.get("team_ids") or [] if team != champion), None)
        path.append({"round": series.get("round"), "opponent": _team_ref(teams, other),
                     "result": f"{int(wins_of(series, champion))}-{int(wins_of(series, other))}"})
    mvp = save.get("finals_mvp") or {}
    record = (save.get("team_records") or {}).get(champion) or {}
    return {
        "key": "champion", "title": "Champion", "kicker": f"{ctx['season']} NBA Finals",
        "champion": _team_ref(teams, champion), "runner_up": _team_ref(teams, opponent),
        "series_result": f"{int(wins.get(champion) or 0)}-{int(wins.get(opponent) or 0)}",
        "regular_season_record": f"{int(record.get('wins') or 0)}-{int(record.get('losses') or 0)}",
        "path": path,
        "finals_mvp": ({**_player_ref(ctx["active"], mvp["player_id"], mvp.get("player_name")),
                        "team_abbrev": mvp.get("team_abbrev"), "finals_line": mvp.get("finals_line"),
                        "why": "Highest total Game Score for the champion across the Finals."} if mvp.get("player_id") else None),
        "user_won": champion == ctx["user"],
    }


def wins_of(series: dict[str, Any], team_id: str | None) -> int:
    return int((series.get("wins") or {}).get(team_id or "") or 0)


def recap_standings_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    active, save, teams = ctx["active"], ctx["save"], ctx["teams"]
    rows = _record_rows(active, save.get("team_records") or {})
    state = save.get("playoff_state") or {}
    play_in_seeds = {}
    for conference, block in (state.get("play_in") or {}).items():
        for seed_no in (7, 8):
            team_id = block.get(f"seed_{seed_no}_team_id")
            if team_id:
                play_in_seeds[team_id] = seed_no
    conferences = {}
    for conference in ("East", "West"):
        ranked = _rank_by_record([row for row in rows if row["conference"] == conference], teams)
        leader = ranked[0] if ranked else None
        conferences[conference] = [{
            "rank": index + 1, "team": _team_ref(teams, row["team_id"]), "wins": row["wins"], "losses": row["losses"],
            "win_pct": row["win_pct"],
            "games_behind": round(((leader["wins"] - row["wins"]) + (row["losses"] - leader["losses"])) / 2, 1) if leader else 0,
            "playoff_seed": play_in_seeds.get(row["team_id"]) or (index + 1 if index < 6 else None),
            "result": ctx["results"].get(row["team_id"], "lottery"),
            "result_label": ROUND_WORDS.get(ctx["results"].get(row["team_id"], "lottery")),
            "is_user": row["team_id"] == ctx["user"],
        } for index, row in enumerate(ranked)]
    return {"key": "standings", "title": "Final standings", "kicker": "Regular season",
            "conferences": conferences,
            "note": "Seeds 7 and 8 went to the play-in winners; ties are broken by point difference."}


def recap_awards_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    from .save import AWARD_CRITERIA, AWARD_LABELS

    rows = [row for row in ctx["save"].get("league_awards") or [] if row.get("season") == ctx["season"]]
    singles = []
    for code in ("MVP", "DPOY", "ROTY", "SMOY", "MIP"):
        row = next((item for item in rows if item.get("award") == code), None)
        if row:
            singles.append({"award": code, "label": AWARD_LABELS[code], "criteria": AWARD_CRITERIA[code],
                            "player": _player_ref(ctx["active"], row["player_id"], row.get("player_name")),
                            "team_abbrev": row.get("team_abbrev"), "stat_line": row.get("stat_line"),
                            "detail": award_detail(row)})
        else:
            singles.append({"award": code, "label": AWARD_LABELS[code], "criteria": AWARD_CRITERIA[code], "player": None,
                            "detail": "No player met this award's rules this season."})
    all_nba = []
    for team_no in (1, 2, 3):
        members = sorted((item for item in rows if item.get("award") == f"ALL_NBA_{team_no}"), key=lambda item: int(item.get("vote_rank") or 0))
        all_nba.append({"label": AWARD_LABELS[f"ALL_NBA_{team_no}"], "players": [
            {**_player_ref(ctx["active"], item["player_id"], item.get("player_name")), "team_abbrev": item.get("team_abbrev"),
             "stat_line": item.get("stat_line")} for item in members]})
    return {"key": "awards", "title": "Awards", "kicker": f"{ctx['season']} season awards", "awards": singles,
            "all_nba": all_nba, "all_nba_criteria": AWARD_CRITERIA["ALL_NBA"],
            "note": "Season awards need 65 games of 20+ minutes (two games of 15-20 minutes also count); Rookie of the Year is exempt, as in the real rule."}


def award_detail(row: dict[str, Any]) -> str:
    if row.get("award") == "SMOY":
        if row.get("bench_basis") == "starts":
            return f"Off the bench in {row.get('bench_games')} games, started {row.get('top_minutes_games')}."
        return f"Off the bench in {row.get('bench_games')} games, among his team's top five in minutes in {row.get('top_minutes_games')}."
    if row.get("award") == "MIP" and row.get("previous_production") is not None:
        return f"Production per game rose from {float(row['previous_production']):.1f} to {float(row.get('production') or 0):.1f}."
    return ""


def season_leaders(stats: dict[str, dict[str, Any]], names: dict[str, str], limit: int = 5,
                   qualifies: Callable[[dict[str, Any]], bool] | None = None) -> list[dict[str, Any]]:
    from .save import AWARD_MIN_GAMES, award_qualifying_games

    qualifies = qualifies or (lambda totals: award_qualifying_games(totals) >= AWARD_MIN_GAMES)
    pool = {pid: totals for pid, totals in stats.items() if qualifies(totals)}
    out = []
    for key, label in LEADER_STATS:
        if not any(float(totals.get(key) or 0) for totals in pool.values()):
            continue
        ordered = sorted(pool, key=lambda pid: (-_per_game(pool[pid], key), -float(pool[pid].get(key) or 0), pid))[:limit]
        out.append({"stat": key, "label": label, "rows": [
            {"player_id": pid, "name": names.get(pid) or pool[pid].get("player_name") or pool[pid].get("name"),
             "team_abbrev": pool[pid].get("team_abbrev") or pool[pid].get("team"), "per_game": _per_game(pool[pid], key),
             "games": int(pool[pid].get("games") or 0)} for pid in ordered]})
    return out


def recap_leaders_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    names = {row["id"]: row.get("name") for row in ctx["active"].get("players", [])}
    return {"key": "leaders", "title": "League leaders", "kicker": "Per game, regular season",
            "categories": season_leaders(ctx["save"].get("player_season_stats") or {}, names,
                                         qualifies=lambda t: int(t.get("games") or 0) >= LEADER_MIN_GAMES),
            "note": "Minimum 30 games."}


def team_stint_minutes(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Minutes and games per (player, team) from game logs: a player traded mid-season has one stint per team."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        player_id, team_id = row.get("player_id"), row.get("team_id")
        minutes = float(row.get("minutes") or 0.0)
        if not player_id or not team_id or minutes <= 0:
            continue
        stint = out.setdefault((player_id, team_id), {"player_id": player_id, "team_id": team_id, "name": row.get("player_name"),
                                                     "minutes": 0.0, "games": 0, "points": 0.0, "rebounds": 0.0, "assists": 0.0,
                                                     "first": row.get("date"), "last": row.get("date")})
        stint["minutes"] += minutes
        stint["games"] += 1
        for key in ("points", "rebounds", "assists"):
            stint[key] += float(row.get(key) or 0.0)
        stint["last"] = max(str(stint["last"] or ""), str(row.get("date") or ""))
    return out


def season_game_logs(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    if "game_logs" not in ctx:
        start, end = _season_years(ctx["season"])
        ctx["game_logs"] = combined_rows(ctx["save"], ctx["save_path"], "player_game_logs",
                                         date_from=f"{start}-07-01", date_to=f"{end}-06-30")
    return ctx["game_logs"]


def recap_your_season_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    from .save import player_attribute_summary

    active, save, teams, user = ctx["active"], ctx["save"], ctx["teams"], ctx["user"]
    rows = _record_rows(active, save.get("team_records") or {})
    mine = next((row for row in rows if row["team_id"] == user), None)
    if not mine:
        return {"key": "your_season", "title": "Your season", "unavailable": "No record for your team."}
    conference_order = _rank_by_record([r for r in rows if r["conference"] == mine["conference"]], teams)
    conference_rank = 1 + next(index for index, row in enumerate(conference_order) if row["team_id"] == user)
    games = max(1, mine["games"])

    def rank(metric: Callable[[dict[str, Any]], float], reverse: bool = True) -> int:
        ordered = sorted(rows, key=metric, reverse=reverse)
        return 1 + next(index for index, row in enumerate(ordered) if row["team_id"] == user)

    stats = [
        {"label": "Points per game", "value": round(mine["points_for"] / games, 1), "rank": rank(lambda r: r["points_for"] / max(1, r["games"]))},
        {"label": "Points allowed per game", "value": round(mine["points_against"] / games, 1), "rank": rank(lambda r: r["points_against"] / max(1, r["games"]), reverse=False)},
        {"label": "Point difference per game", "value": round(mine["point_diff"] / games, 1), "rank": rank(lambda r: r["point_diff"] / max(1, r["games"]))},
        {"label": "Wins", "value": mine["wins"], "rank": rank(lambda r: r["wins"])},
    ]
    stints = team_stint_minutes(season_game_logs(ctx))
    candidates = [stint for (pid, team_id), stint in stints.items() if team_id == user]
    if not candidates:  # no game logs available: season totals of players who finished with the team
        candidates = [{"player_id": pid, "minutes": float(t.get("minutes") or 0), "games": int(t.get("games") or 0),
                       "points": float(t.get("points") or 0), "rebounds": float(t.get("rebounds") or 0),
                       "assists": float(t.get("assists") or 0), "name": t.get("player_name")}
                      for pid, t in (save.get("player_season_stats") or {}).items() if t.get("team_id") == user]
    best, why = None, ""
    if candidates:
        def value(stint: dict[str, Any]) -> float:
            return float(player_attribute_summary(active, stint["player_id"]).get("overall") or 0.0) * float(stint["minutes"])
        best = max(candidates, key=lambda stint: (value(stint), stint["player_id"]))
        ref = _player_ref(active, best["player_id"], best.get("name"))
        g = max(1, int(best["games"]))
        why = (f"The most on-court value times minutes for your team: {round(best['minutes'])} minutes in {g} games at a "
               f"{ref.get('overall')} rating, {best['points'] / g:.1f} points, {best['rebounds'] / g:.1f} rebounds and "
               f"{best['assists'] / g:.1f} assists a game.")
        best = {**ref, "minutes": round(best["minutes"]), "games": g}
    result = ctx["results"].get(user, "lottery")
    return {"key": "your_season", "title": "Your season", "kicker": _team_ref(teams, user)["name"],
            "team": _team_ref(teams, user), "record": f"{mine['wins']}-{mine['losses']}",
            "conference_rank": conference_rank, "conference": mine["conference"], "result": result,
            "result_label": ROUND_WORDS.get(result), "stats": stats, "team_mvp": best, "team_mvp_why": why}


# ---- trades


def trade_receipts(log: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """What each team received in a logged trade (two-team or multi-team)."""
    assets = log.get("assets") or {}
    received: dict[str, list[dict[str, Any]]] = {team: [] for team in log.get("teams") or []}
    if assets.get("format") == "multi_team_v1":
        for edge in assets.get("transfers") or []:
            received.setdefault(edge.get("to_team_id"), []).extend(edge.get("assets") or [])
        return received
    teams = log.get("teams") or []
    if len(teams) == 2:
        received[teams[1]] = list(assets.get("from_assets") or [])
        received[teams[0]] = list(assets.get("to_assets") or [])
    return received


def trade_measures(log: dict[str, Any]) -> dict[str, float]:
    """Value that changed hands (each receiver's own value of what it got) and the value swing (how far the deal
    moved each team by its own evaluation)."""
    evaluations = [row for row in log.get("evaluations") or [] if isinstance(row, dict)]
    involved = sum(max(0.0, float(row.get("incoming_value") or 0.0)) for row in evaluations)
    swing = sum(abs(float(row.get("net_value") or 0.0)) for row in evaluations)
    return {"value_involved": round(involved, 2), "value_swing": round(swing, 2)}


def rank_trades(logs: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """The biggest trades: ranked by value involved and by value swing; each trade takes the better of its two ranks,
    ties broken by the other rank, then value involved."""
    trades = [{"log": log, **trade_measures(log)} for log in logs]
    by_involved = sorted(trades, key=lambda row: (-row["value_involved"], str(row["log"].get("id"))))
    by_swing = sorted(trades, key=lambda row: (-row["value_swing"], str(row["log"].get("id"))))
    for index, row in enumerate(by_involved, start=1):
        row["involved_rank"] = index
    for index, row in enumerate(by_swing, start=1):
        row["swing_rank"] = index
    for row in trades:
        row["best_rank"] = min(row["involved_rank"], row["swing_rank"])
        row["ranked_by"] = "value exchanged" if row["involved_rank"] <= row["swing_rank"] else "value swing"
    trades.sort(key=lambda row: (row["best_rank"], max(row["involved_rank"], row["swing_rank"]), -row["value_involved"],
                                 str(row["log"].get("id"))))
    return trades[:limit]


def season_trade_logs(save: dict[str, Any], season: str, until: str | None = None) -> list[dict[str, Any]]:
    start, end = _season_years(season)
    floor, ceiling = f"{start}-07-01", until or f"{end}-06-30"
    return [log for log in save.get("transaction_logs") or []
            if log.get("transaction_type") == "trade" and floor <= str(log.get("date") or "") <= ceiling
            and log.get("status") in {"applied_to_save_ledger", "applied", None}]


def recap_trades_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    active, save, teams = ctx["active"], ctx["save"], ctx["teams"]
    logs = season_trade_logs(save, ctx["season"], (save.get("state") or {}).get("current_date"))
    logs = combine_trade_logs(ctx, logs)
    ranked = rank_trades(logs)
    stints = team_stint_minutes(season_game_logs(ctx))
    rows = []
    for item in ranked:
        log = item["log"]
        evaluations = {row.get("perspective_team_id"): row for row in log.get("evaluations") or [] if isinstance(row, dict)}
        reasons = (log.get("trade_reasons") or {}).get("text")
        sides = []
        for team_id, assets in trade_receipts(log).items():
            evaluation = evaluations.get(team_id) or {}
            received = []
            for asset in assets:
                entry = {"kind": asset.get("kind"), "label": asset.get("label") or asset.get("id")}
                if asset.get("kind") == "player":
                    entry["player_id"] = asset.get("id")
                    entry["played_out"] = played_out(stints, asset.get("id"), team_id, str(log.get("date") or ""))
                received.append(entry)
            sides.append({"team": _team_ref(teams, team_id), "received": received,
                          "net_value": round(float(evaluation.get("net_value") or 0.0), 1),
                          "phase": PHASE_WORDS.get(evaluation.get("window_phase"), evaluation.get("window_phase"))})
        rows.append({"date": log.get("date"), "sides": sides, "reasons": reasons,
                     "value_involved": item["value_involved"], "value_swing": item["value_swing"],
                     "ranked_by": item["ranked_by"]})
    return {"key": "trades", "title": "Biggest trades", "kicker": f"{len(logs)} trades this season", "trades": rows,
            "note": "Ranked by the value that changed hands or by how far the deal moved each team (each team's own evaluation), whichever ranks the trade higher."}


def combine_trade_logs(ctx: dict[str, Any], hot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Season trades that were already moved to the history file (only logs before the season floor normally are)."""
    start, end = _season_years(ctx["season"])
    rows = {str(log.get("id")): log for log in hot}
    for log in combined_rows(ctx["save"], ctx["save_path"], "transaction_logs", date_from=f"{start}-07-01",
                             date_to=(ctx["save"].get("state") or {}).get("current_date") or f"{end}-06-30"):
        if log.get("transaction_type") == "trade":
            rows.setdefault(str(log.get("id")), log)
    return list(rows.values())


def played_out(stints: dict[tuple[str, str], dict[str, Any]], player_id: str | None, team_id: str, since: str) -> dict[str, Any] | None:
    stint = stints.get((player_id or "", team_id))
    if not stint or str(stint.get("last") or "") < since:
        return None
    games = max(1, int(stint["games"]))
    return {"games": int(stint["games"]), "minutes": round(stint["minutes"] / games, 1), "points": round(stint["points"] / games, 1),
            "rebounds": round(stint["rebounds"] / games, 1), "assists": round(stint["assists"] / games, 1)}


# ---- coaching


def coaching_changes(events: list[dict[str, Any]], season_floor: str, until: str | None = None) -> list[dict[str, Any]]:
    """Pairs each firing with the same team's next hire for that job (or stands alone), scored by the two events'
    importance, then the new coach's grade."""
    rows = [event for event in events if event.get("kind") in {"staff_hire", "staff_fire"}
            and (event.get("details") or {}).get("slot") in COACHING_SLOTS
            and str(event.get("date") or "") >= season_floor and (until is None or str(event.get("date") or "") <= until)]
    rows.sort(key=lambda event: (str(event.get("date") or ""), event.get("kind") != "staff_fire", str(event.get("id"))))
    changes: list[dict[str, Any]] = []
    open_fires: dict[tuple[str, str], dict[str, Any]] = {}
    for event in rows:
        team_id = (event.get("team_ids") or [None])[0]
        slot = (event.get("details") or {}).get("slot")
        key = (team_id, slot)
        if event.get("kind") == "staff_fire":
            change = {"team_id": team_id, "slot": slot, "fire": event, "hire": None, "date": event.get("date")}
            changes.append(change)
            open_fires[key] = change
        else:
            change = open_fires.pop(key, None)
            if change is not None:
                change["hire"] = event
            else:
                changes.append({"team_id": team_id, "slot": slot, "fire": None, "hire": event, "date": event.get("date")})
    for change in changes:
        importance = sum(float((change.get(part) or {}).get("importance") or 0.0) for part in ("fire", "hire"))
        grade = float(((change.get("hire") or {}).get("details") or {}).get("staff_grade") or 0.0)
        change["importance"] = round(importance, 3)
        change["new_grade"] = grade
    changes.sort(key=lambda change: (-change["importance"], -change["new_grade"], str(change.get("date")), str(change.get("team_id"))))
    return changes


def recap_coaching_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    from .staff import coach_star_workload, star_workload_text

    save, teams = ctx["save"], ctx["teams"]
    start, _ = _season_years(ctx["season"])
    events = combined_rows(save, ctx["save_path"], "league_events", date_from=f"{start}-07-01",
                           date_to=(save.get("state") or {}).get("current_date"))
    changes = coaching_changes(events, f"{start}-07-01", (save.get("state") or {}).get("current_date"))
    staff_by_id = {row.get("id"): row for row in save.get("staff_slots") or []}
    rows = []
    for change in changes[:3]:
        fire = (change.get("fire") or {}).get("details") or {}
        hire = (change.get("hire") or {}).get("details") or {}
        new_staff = staff_by_id.get(hire.get("staff_id"))
        style = star_workload_text(coach_star_workload(new_staff)) if change["slot"] == "head_coach" and new_staff else None
        rows.append({"date": change.get("date"), "team": _team_ref(teams, change["team_id"]),
                     "job": SLOT_LABELS.get(change["slot"], change["slot"]),
                     "out": {"name": fire.get("staff_name"), "grade": fire.get("staff_grade") or fire.get("fired_staff_grade"),
                             "reason": fire.get("reason")} if fire else None,
                     "in": {"name": hire.get("staff_name"), "grade": hire.get("staff_grade"), "style": style} if hire else None,
                     "importance": change["importance"]})
    return {"key": "coaching", "title": "Biggest coaching changes", "kicker": f"{len(changes)} coaching changes this season",
            "changes": rows, "note": "Head coaches and coordinators, ranked by how big the league rated the firing and the hire, then the new coach's grade."}


# ---- free agents and the summer


def expiring_players(active: dict[str, Any], season: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    from .save import contract_last_season

    contracts = {row.get("player_id"): row for row in active.get("contracts", [])}
    out = []
    for player in active.get("players", []):
        contract = contracts.get(player.get("id"))
        if player.get("team_id") and contract and contract_last_season(contract) == season:
            out.append((player, contract))
    return out


def recap_free_agents_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    from .contract_ai import build_player_contract_market_profiles
    from .save import contract_salary_for_season

    active, teams, season = ctx["active"], ctx["teams"], ctx["season"]
    expiring = expiring_players(active, season)
    if not expiring:
        return {"key": "free_agents", "title": "Top upcoming free agents", "players": [], "note": "No contracts end this season."}
    subset = {**active, "players": [player for player, _ in expiring]}
    profiles = {profile.player_id: profile for profile in build_player_contract_market_profiles(subset)}
    rows = []
    for player, contract in expiring:
        profile = profiles.get(player["id"])
        if not profile:
            continue
        rows.append((float(profile.expected_aav or 0.0), player, contract))
    rows.sort(key=lambda item: (-item[0], item[1]["id"]))
    players = []
    for value, player, contract in rows[:5]:
        ref = _player_ref(active, player["id"])
        players.append({**ref, "team": _team_ref(teams, player.get("team_id")), "market_value_millions": round(value / 1e6, 1),
                        "current_salary_millions": round(float(contract_salary_for_season(contract, season) or 0.0) / 1e6, 1),
                        "rights": "His team can re-sign him before the open market (Bird rights)."})
    return {"key": "free_agents", "title": "Top upcoming free agents", "kicker": f"{len(expiring)} contracts end this season",
            "players": players, "note": "Contracts that end this season, ranked by what the league's front offices expect him to earn per year."}


def lottery_view(active: dict[str, Any], save: dict[str, Any], season: str, user: str) -> dict[str, Any]:
    from .draft import default_draft_model_config, lottery_odds_by_team

    _, end = _season_years(season)
    order = (save.get("draft_orders") or {}).get(str(end))
    if order:
        pick = next((row for row in order.get("draft_order") or [] if row.get("current_owner_team_id") == user
                     or row.get("team_id") == user), None)
        return {"status": "drawn", "pick": (pick or {}).get("overall_pick") or (pick or {}).get("pick")}
    teams, _ = _team_maps(active)
    results = team_postseason_results(save.get("playoff_state") or {})
    rows = _record_rows(active, save.get("team_records") or {})
    lottery = sorted([row for row in rows if results.get(row["team_id"], "lottery") in {"lottery", "play_in"}],
                     key=lambda row: (row["win_pct"], row["point_diff"], teams[row["team_id"]].get("abbrev", "")))
    odds = lottery_odds_by_team([{"id": row["team_id"]} for row in lottery], default_draft_model_config())
    position = next((index + 1 for index, row in enumerate(lottery) if row["team_id"] == user), None)
    ownership = own_pick_owner(active, str(end), user)
    if position is None:
        playoff = sorted([row for row in rows if row not in lottery], key=lambda row: (row["win_pct"], row["point_diff"]))
        position = len(lottery) + 1 + next((i for i, row in enumerate(playoff) if row["team_id"] == user), 0)
        return {"status": "playoff_team", "projected_pick": position, **ownership}
    return {"status": "lottery", "lottery_position": position, "odds_first_pick": round(100 * odds.get(user, 0.0), 1), **ownership}


def own_pick_owner(active: dict[str, Any], year: str, team_id: str) -> dict[str, Any]:
    """Who holds the team's own first-round pick this year, when it is not the team itself."""
    teams, _ = _team_maps(active)
    pick = next((row for row in active.get("draft_picks") or [] if str(row.get("season")) == year and int(row.get("round") or 0) == 1
                 and (row.get("original_team_id") or row.get("team_id")) == team_id), None)
    owner = (pick or {}).get("current_owner_team_id")
    if not owner or owner == team_id:
        return {}
    return {"pick_owner": teams.get(owner, {}).get("name") or owner, "protection": (pick or {}).get("protections") or None}


def consensus_top(active: dict[str, Any], year: str, team_id: str, limit: int) -> list[dict[str, Any]]:
    from .draft_scouting import class_scouting
    from .faces import prospect_headshot_url

    scouting = class_scouting(active, year)
    order = sorted(scouting["consensus"], key=lambda pid: scouting["consensus"][pid]["rank"])[:limit]
    reports = scouting["reports"].get(team_id) or {}
    rows = []
    for pid in order:
        prospect = scouting["prospects"].get(pid) or {}
        report = reports.get(pid) or {}
        rows.append({"id": pid, "name": prospect.get("name"), "position": prospect.get("position"), "age": prospect.get("age"),
                     "school": prospect.get("source_team") or prospect.get("league"),
                     "consensus_rank": scouting["consensus"][pid]["rank"], "your_rank": report.get("scout_rank"),
                     "scouted_pct": report.get("coverage"),
                     # Round 13 (Prospect watch): the photo and how the league's 30 boards spread on him.
                     "headshot_url": prospect_headshot_url(prospect) if prospect else None,
                     "consensus_best": scouting["consensus"][pid].get("best"),
                     "consensus_worst": scouting["consensus"][pid].get("worst"),
                     "consensus_middle": list(scouting["consensus"][pid].get("middle") or ())})
    return rows


def recap_look_ahead_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    from .save import team_cap_summary

    active, save, season, user = ctx["active"], ctx["save"], ctx["season"], ctx["user"]
    start, end = _season_years(season)
    next_season = f"{end}-{str(end + 1)[-2:]}"
    cap = team_cap_summary(active, save, user, next_season)
    return {"key": "look_ahead", "title": "Looking ahead", "kicker": f"The {end} draft and your summer",
            "draft": lottery_view(active, save, season, user),
            "prospects": consensus_top(active, str(end), user, 5),
            "cap": {"season": next_season, "payroll_millions": cap.get("salary_total_millions"),
                    "tax_line_millions": cap.get("tax_line_millions"), "tax_space_millions": cap.get("tax_space_millions"),
                    "hard_cap_millions": cap.get("hard_cap_millions"), "hard_cap_space_millions": cap.get("hard_cap_space_millions")}}


# --------------------------------------------------------------------------------------------- preseason outlook


def previous_season_label(season: str) -> str:
    start, _ = _season_years(season)
    return f"{start - 1}-{str(start)[-2:]}"


def _name_key(name: Any) -> str:
    """Name match key: lower case, letters and digits only ("Ja'Kobe Walter" and "jakobe walter" match)."""
    return " ".join("".join(ch for ch in word if ch.isalnum()) for word in str(name or "").lower().replace("-", " ").split())


def last_season_context(active: dict[str, Any], save: dict[str, Any], save_path: str | Path | None, season: str) -> dict[str, Any]:
    """Last season, as stints, records, totals and awards: the save's own history when it has one, otherwise the
    real 2025-26 season (a new career)."""
    previous = previous_season_label(season)
    entry = next((row for row in reversed(save.get("season_history") or []) if str(row.get("season")) == previous
                  and row.get("player_season_stats")), None)
    teams, by_abbrev = _team_maps(active)
    if entry:
        start, end = _season_years(previous)
        logs = combined_rows(save, save_path, "player_game_logs", date_from=f"{start}-07-01", date_to=f"{end}-06-30")
        stints = list(team_stint_minutes(logs).values())
        if not stints:  # logs pruned or missing: whole-season totals at the team he finished with
            stints = [{"player_id": pid, "team_id": t.get("team_id"), "name": t.get("player_name"), "minutes": float(t.get("minutes") or 0),
                       "games": int(t.get("games") or 0)} for pid, t in entry["player_season_stats"].items()]
        return {"season": previous, "source": "save", "stints": stints, "records": entry.get("team_records") or {},
                "totals": entry.get("player_season_stats") or {}, "awards": entry.get("awards") or [],
                "note": f"Minutes from your league's {previous} season, counted per team stint."}
    real = real_season_summary()
    by_name = {_name_key(row.get("normalized_name") or row.get("name")): row["id"] for row in active.get("players", [])
               if row.get("normalized_name") or row.get("name")}
    stints = []
    for row in real.get("stints") or []:
        team_id = by_abbrev.get(row["team"])
        if team_id:
            stints.append({"player_id": by_name.get(_name_key(row["key"])) or f"real:{row['key']}", "team_id": team_id, "name": row["name"],
                           "minutes": float(row["minutes"]), "games": int(row["games"])})
    records = {by_abbrev[abbrev]: rec for abbrev, rec in (real.get("teams") or {}).items() if abbrev in by_abbrev}
    totals = {}
    for key, row in (real.get("players") or {}).items():
        pid = by_name.get(_name_key(key)) or f"real:{key}"
        totals[pid] = {**row, "player_name": row["name"], "team_abbrev": row.get("team")}
    return {"season": real.get("season") or previous, "source": "real", "stints": stints, "records": records, "totals": totals,
            "awards": [], "note": "A new league: these are the real 2025-26 NBA minutes (ESPN box scores), counted per team stint."}


def long_injuries(active: dict[str, Any], save: dict[str, Any], min_games: int = INJURY_SLIDE_MIN_GAMES) -> dict[str, dict[str, Any]]:
    """Players out at the start of the season whose expected absence is more than `min_games` of his team's games."""
    from .sim import espn_team_id_map

    season = str((save.get("meta") or {}).get("season") or "")
    today = str((save.get("state") or {}).get("current_date") or "")
    espn = {espn_id: team["id"] for espn_id, team in espn_team_id_map(active).items()} if active.get("teams") else {}
    games_by_team: dict[str, list[str]] = {}
    for game in ((save.get("season_schedules") or {}).get(season) or {}).get("games") or []:
        if game.get("phase") not in {None, "regular"}:
            continue
        for side in ("homeTeamId", "awayTeamId"):
            team_id = espn.get(str(game.get(side)))
            if team_id:
                games_by_team.setdefault(team_id, []).append(str(game.get("gameDate") or ""))
    players = {row["id"]: row for row in active.get("players", [])}
    out = {}
    for state in save.get("health_states") or []:
        player = players.get(state.get("player_id"))
        if not player or not player.get("team_id") or str(state.get("availability_status") or "active") in {"active", "healthy"}:
            continue
        back = str(state.get("return_date") or "")
        missed = sum(1 for day in games_by_team.get(player["team_id"], []) if today <= day < back) if back else 82
        if missed > min_games:
            team_days = games_by_team.get(player["team_id"], [])
            out[player["id"]] = {"games": missed, "return_date": back or None, "injury": state.get("current_injury_label"),
                                 "whole_season": not back or not team_days or back > max(team_days),
                                 "part": state.get("current_injury_part")}
    return out


def continuity_rows(active: dict[str, Any], last: dict[str, Any], injured: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Each team's share of last season's minutes (per team stint) still on the roster: kept (green), kept but out
    long (grey), gone (red); new arrivals listed beside the bar."""
    teams, _ = _team_maps(active)
    current_team = {row["id"]: row.get("team_id") for row in active.get("players", [])}
    names = {row["id"]: row.get("name") for row in active.get("players", [])}
    minutes_anywhere: dict[str, float] = {}
    for stint in last["stints"]:
        minutes_anywhere[stint["player_id"]] = minutes_anywhere.get(stint["player_id"], 0.0) + float(stint["minutes"])
    rows = []
    for team_id in teams:
        stints = [stint for stint in last["stints"] if stint["team_id"] == team_id]
        total = sum(float(stint["minutes"]) for stint in stints) or 0.0
        segments = {"kept": [], "injured": [], "gone": []}
        for stint in sorted(stints, key=lambda row: -float(row["minutes"])):
            if current_team.get(stint["player_id"]) == team_id:
                part = "injured" if stint["player_id"] in injured else "kept"
            else:
                part = "gone"
            segments[part].append({"id": stint["player_id"], "name": names.get(stint["player_id"]) or stint.get("name"),
                                   "minutes": round(float(stint["minutes"]))})
        prior_ids = {stint["player_id"] for stint in stints}
        arrivals = sorted(({"id": pid, "name": names.get(pid), "minutes_last_season": round(minutes_anywhere.get(pid, 0.0)),
                            "rookie": minutes_anywhere.get(pid, 0.0) <= 0}
                           for pid, tid in current_team.items() if tid == team_id and pid not in prior_ids),
                          key=lambda row: (-row["minutes_last_season"], str(row["name"])))
        share = {part: (sum(row["minutes"] for row in seg) / total if total else 0.0) for part, seg in segments.items()}
        rows.append({"team": _team_ref(teams, team_id), "total_minutes": round(total),
                     "kept_pct": round(100 * share["kept"], 1), "injured_pct": round(100 * share["injured"], 1),
                     "gone_pct": round(100 * share["gone"], 1), "continuity_pct": round(100 * (share["kept"] + share["injured"]), 1),
                     "arrivals_pct": round(100 * sum(row["minutes_last_season"] for row in arrivals) / total, 1) if total else 0.0,
                     "kept": segments["kept"], "injured": segments["injured"], "gone": segments["gone"], "arrivals": arrivals})
    rows.sort(key=lambda row: (-row["continuity_pct"], row["team"]["abbrev"]))
    return rows


def build_preseason_outlook(canonical: dict[str, Any], save: dict[str, Any], save_path: str | Path | None = None) -> dict[str, Any]:
    from .save import canonical_with_save

    active = canonical_with_save(canonical, save)
    season = str((save.get("meta") or {}).get("season") or "")
    user = str((save.get("meta") or {}).get("user_team_id") or "")
    last = last_season_context(active, save, save_path, season)
    injured = long_injuries(active, save)
    ctx = {"active": active, "save": save, "save_path": save_path, "season": season, "user": user,
           "teams": _team_maps(active)[0], "last": last, "injured": injured}
    ctx["continuity"] = continuity_rows(active, last, injured)
    slides = [
        _safe(lambda: outlook_power_slide(ctx), "power", "Power rankings"),
        _safe(lambda: outlook_continuity_slide(ctx), "continuity", "Continuity"),
        _safe(lambda: outlook_leaders_slide(ctx), "leaders_revisited", "Last season's leaders"),
        _safe(lambda: outlook_your_team_slide(ctx), "your_team", "Your team"),
        _safe(lambda: outlook_team_profile_slide(ctx), "team_profile", "Team profile"),
        _safe(lambda: outlook_contracts_slide(ctx), "contracts", "Contracts to watch"),
        _safe(lambda: outlook_prospects_slide(ctx), "prospects", "Prospect watch"),
        _safe(lambda: outlook_storylines_slide(ctx), "storylines", "Storylines"),
        _safe(lambda: outlook_injuries_slide(ctx), "injuries", "Stars starting on the sidelines"),
    ]
    return {"kind": "outlook", "season": season, "built_on": (save.get("state") or {}).get("current_date"),
            "user_team_id": user, "title": f"{season} Preseason Outlook", "last_season": last["season"],
            "last_season_source": last["source"], "slides": slides}


def outlook_power_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    from .save import player_attribute_summary, team_identity_report

    active, save, teams = ctx["active"], ctx["save"], ctx["teams"]
    identity = team_identity_report(active, save)
    order = sorted(identity, key=lambda tid: (-float(identity[tid]["metrics"].get("overall") or 0), teams.get(tid, {}).get("abbrev", "")))
    last_rows = _rank_by_record(_record_rows(active, ctx["last"]["records"]), teams)
    last_rank = {row["team_id"]: index + 1 for index, row in enumerate(last_rows)}
    continuity = {row["team"]["id"]: row for row in ctx["continuity"]}
    players = {row["id"]: row for row in active.get("players", [])}
    values: dict[str, float] = {}

    def value(player_id: str) -> float:
        if player_id not in values:
            values[player_id] = float(player_attribute_summary(active, player_id).get("overall") or 0.0) if player_id in players else 0.0
        return values[player_id]

    def draft_year(player_id: str) -> int | None:
        year = (players.get(player_id) or {}).get("draft_year")
        return int(year) if str(year or "").isdigit() else None

    season_start = _season_years(ctx["season"])[0] if ctx["season"] else None
    rows = []
    for index, team_id in enumerate(order, start=1):
        before = last_rank.get(team_id)
        rows.append({"rank": index, "team": _team_ref(teams, team_id), "overall": identity[team_id]["metrics"].get("overall"),
                     "last_finish": before, "change": (before - index) if before else None,
                     "note": roster_note(continuity.get(team_id), value, draft_year, season_start),
                     "is_user": team_id == ctx["user"]})
    ctx["power_rows"] = rows
    return {"key": "power", "title": "Power rankings", "kicker": "Team Signals' overall strength",
            "rows": rows, "note": f"Change compares with each team's {ctx['last']['season']} record finish."}


# A move's weight is how far the player's value sits above a fringe-rotation level, growing faster than linearly so
# one star outweighs several role players (Kawhi Leonard in > Brandon Ingram out). Values are the engine's own player
# value (team "Overall" is built from the same scale); 58 is about a rotation regular.
NOTE_VALUE_FLOOR = 55.0
NOTE_NOTABLE_VALUE = 58.0
# Rookies are named when they would already be a rotation player (about the league's 190th player; Boozer, Graves,
# Lendeborg, Wilson and Ejiofor in the 2026 class) and always get a mention, even beside a bigger move (user, 2026-11-22).
NOTE_DRAFTED_VALUE = 56.5
NOTE_SECOND_SHARE = 0.35      # a second kind of move is named when its total weight is this share of the lead move


def _move_weight(value: float) -> float:
    return max(0.0, value - NOTE_VALUE_FLOOR) ** 1.5


def roster_note(row: dict[str, Any] | None, value: Callable[[str], float] | None = None,
                draft_year: Callable[[str], int | None] | None = None, season_start: int | None = None) -> str:
    """One line on a team's biggest change since last season, by player value: arrivals, departures, players back
    after missing last season, and players starting the season out long. The biggest move leads; a different kind of
    move follows when it is comparable ("Added Kawhi Leonard; lost Brandon Ingram and 1 more")."""
    if not row:
        return ""
    value = value or (lambda _pid: 0.0)
    draft_year = draft_year or (lambda _pid: None)
    moves: dict[str, list[tuple[float, str]]] = {"added": [], "drafted": [], "back": [], "lost": [], "out": []}
    for item in row.get("arrivals") or []:
        pid = item.get("id")
        drafted = draft_year(pid) if pid else None
        if season_start and drafted is not None and drafted >= season_start:
            kind = "drafted"
        elif drafted is not None and not item.get("minutes_last_season"):  # on no team's court last season
            kind = "back"
        else:
            kind = "added"
        moves[kind].append((value(pid) if pid else 0.0, item["name"]))
    for item in row.get("gone") or []:
        moves["lost"].append((value(item["id"]) if item.get("id") else 0.0, item["name"]))
    for item in row.get("injured") or []:
        moves["out"].append((value(item["id"]) if item.get("id") else 0.0, item["name"]))
    for kind in moves:
        floor = NOTE_DRAFTED_VALUE if kind == "drafted" else NOTE_NOTABLE_VALUE
        moves[kind] = sorted((m for m in moves[kind] if m[0] >= floor and m[1]), key=lambda m: (-m[0], m[1]))
    if not any(moves.values()):
        return "Running it back" if row.get("continuity_pct", 0) >= 85 else ""
    weight = {kind: sum(_move_weight(v) for v, _ in items) for kind, items in moves.items()}
    lead = max((kind for kind in moves if moves[kind]), key=lambda kind: (_move_weight(moves[kind][0][0]), weight[kind]))

    def phrase(kind: str, first: bool) -> str:
        items = moves[kind]
        names = [items[0][1]]
        if len(items) > 1 and _move_weight(items[1][0]) >= 0.5 * _move_weight(items[0][0]):
            names.append(items[1][1])
        rest = len(items) - len(names)
        who = " and ".join(names) if not rest else ", ".join(names) + f" and {rest} more"
        text = {"added": f"added {who}", "drafted": f"drafted {who}", "lost": f"lost {who}",
                "back": f"{who} back after missing last season", "out": f"{who} out injured"}[kind]
        return text[0].upper() + text[1:] if first else text

    opposite = {"added": ("lost", "out"), "drafted": ("lost", "out"), "back": ("lost", "out"),
                "lost": ("added", "back", "drafted"), "out": ("added", "back", "drafted")}[lead]
    others = [kind for kind in moves if kind != lead and moves[kind]]
    others.sort(key=lambda kind: (kind not in opposite, -weight[kind]))
    text = phrase(lead, True)
    named = {lead}
    if others and weight[others[0]] >= NOTE_SECOND_SHARE * _move_weight(moves[lead][0][0]):
        text += "; " + phrase(others[0], False)
        named.add(others[0])
    if moves["drafted"] and "drafted" not in named:
        text += "; " + phrase("drafted", False)
    return text


CONTINUITY_NOTE = "Last season's minutes, by whether the player is still on the team."


def outlook_continuity_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    return {"key": "continuity", "title": "Continuity", "kicker": f"Share of {ctx['last']['season']} minutes still on the roster",
            "rows": [{**row, "is_user": row["team"]["id"] == ctx["user"]} for row in ctx["continuity"]],
            "source": ctx["last"]["source"], "note": CONTINUITY_NOTE,
            "legend": {"kept": "Still on the team", "injured": f"Still on the team, out more than {INJURY_SLIDE_MIN_GAMES} games",
                       "gone": "Left the team"}}


# Last season's leaders: nine categories in a 3 x 3 grid, and every qualifying player for "View all" (playtest
# 2026-11-22). Leaders need 30 games (softer than the awards' 65); percentages also need attempts per game.
OUTLOOK_LEADER_STATS = (("points", "Points"), ("rebounds", "Rebounds"), ("assists", "Assists"), ("steals", "Steals"),
                        ("blocks", "Blocks"), ("fg3m", "Threes made"), ("fg3_pct", "Three-point %"),
                        ("ft_pct", "Free-throw %"), ("minutes", "Minutes"))
LEADER_MIN_GAMES = 30
THREE_PCT_MIN_ATTEMPTS = 3.0     # three-point attempts per game
FT_PCT_MIN_ATTEMPTS = 2.0        # free-throw attempts per game


def _leader_line(totals: dict[str, Any]) -> dict[str, Any]:
    games = max(1, int(totals.get("games") or 0))
    line: dict[str, Any] = {key: round(float(totals.get(key) or 0.0) / games, 1)
                            for key in ("points", "rebounds", "assists", "steals", "blocks", "fg3m", "minutes")}
    fg3a, fta = float(totals.get("fg3a") or 0.0), float(totals.get("fta") or 0.0)
    line["fg3_pct"] = (round(100 * float(totals.get("fg3m") or 0) / fg3a, 1)
                       if fg3a and fg3a / games >= THREE_PCT_MIN_ATTEMPTS else None)
    line["ft_pct"] = (round(100 * float(totals.get("ftm") or 0) / fta, 1)
                      if fta and fta / games >= FT_PCT_MIN_ATTEMPTS else None)
    line["games"] = int(totals.get("games") or 0)
    return line


def outlook_leaders_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    from .save import AWARD_LABELS

    active, last, teams = ctx["active"], ctx["last"], ctx["teams"]
    players = {row["id"]: row for row in active.get("players", [])}
    qualifies = lambda t: int(t.get("games") or 0) >= LEADER_MIN_GAMES  # noqa: E731

    def now(pid: str | None) -> dict[str, Any]:
        player = players.get(pid or "")
        if not player:
            return {"team": None, "status": "No longer in the league"}
        if not player.get("team_id"):
            return {"team": None, "status": "Free agent"}
        return {"team": _team_ref(teams, player.get("team_id"))}

    rows = []
    for pid, totals in last["totals"].items():
        if not qualifies(totals):
            continue
        name = (players.get(pid) or {}).get("name") or totals.get("player_name") or totals.get("name")
        rows.append({"player_id": pid, "name": name, "team_abbrev": totals.get("team_abbrev") or totals.get("team"),
                     "now": now(pid), **_leader_line(totals)})
    categories = []
    for key, label in OUTLOOK_LEADER_STATS:
        ranked = sorted((row for row in rows if row.get(key) is not None), key=lambda row: (-row[key], str(row["name"])))
        if ranked and ranked[0][key]:
            categories.append({"stat": key, "label": label,
                               "rows": [{"player_id": row["player_id"], "name": row["name"], "team_abbrev": row["team_abbrev"], "per_game": row[key],
                                         "now": row["now"]} for row in ranked[:3]]})
    winners = [{"label": AWARD_LABELS.get(row.get("award"), row.get("award")), "name": row.get("player_name"),
                "then": row.get("team_abbrev"), "now": now(row.get("player_id"))}
               for row in sorted(last["awards"], key=lambda item: AWARD_ORDER.index(item["award"]) if item.get("award") in AWARD_ORDER else 99)
               if row.get("award") in AWARD_ORDER]
    return {"key": "leaders_revisited", "title": "Last season's leaders", "kicker": f"Where the {last['season']} leaders play now",
            "categories": categories, "players": sorted(rows, key=lambda row: -row["points"]), "award_winners": winners, "note": None}


def _return_penalty(games: int) -> float:
    from .injury_model import return_rust
    from .sim import rust_penalty_points
    return round(rust_penalty_points(return_rust(games)), 1) if games > 0 else 0.0


def outlook_your_team_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    from .save import (contract_salary_for_season, player_display_attribute_summary, player_salary_table,
                       starting_lineup_slots, team_cap_summary, team_identity_report, team_rotation_projection)

    active, save, user, teams = ctx["active"], ctx["save"], ctx["user"], ctx["teams"]
    projection = team_rotation_projection(active, save, user, integer=True)
    contracts = {row.get("player_id"): row for row in active.get("contracts", [])}
    season_start = _season_years(ctx["season"])[0] if ctx["season"] else None
    last_totals = ctx["last"]["totals"]

    def rotation_row(pid: str, minutes: float) -> dict[str, Any]:
        # One row per rotation player: ratings, the coach's minutes, last season's line and the contract (playtest
        # 2026-11-22: fields instead of subtext, sorted by overall).
        ratings = player_display_attribute_summary(active, pid)
        line = last_totals.get(pid) or {}
        games = int(line.get("games") or 0)
        contract = contracts.get(pid)
        years = _years_left(contract, ctx["season"])
        salary = contract_salary_for_season(contract, ctx["season"]) if contract else None
        return {**_player_ref(active, pid), "minutes": round(float(minutes)),
                "offense": ratings.get("offense"), "defense": ratings.get("defense"),
                "points": round(float(line.get("points") or 0) / games, 1) if games else None,
                "rebounds": round(float(line.get("rebounds") or 0) / games, 1) if games else None,
                "assists": round(float(line.get("assists") or 0) / games, 1) if games else None,
                "salary_millions": round(float(salary) / 1e6, 1) if salary else None, "years_left": years}

    rotation = [rotation_row(pid, minutes)
                for pid, minutes in sorted(projection.items(), key=lambda item: (-float(item[1]), item[0])) if float(minutes) > 0][:10]
    # Injured players join the table with how many games they will miss.
    injured = {pid: row for pid, row in long_injuries(active, save, min_games=0).items()
               if (next((p for p in active.get("players", []) if p.get("id") == pid), {}) or {}).get("team_id") == user}
    shown = {row["id"] for row in rotation}
    rotation += [rotation_row(pid, 0) for pid in injured if pid not in shown]
    for row in rotation:
        hurt = injured.get(row["id"])
        row["injury"] = ({"games": hurt["games"], "label": hurt.get("injury"), "return_date": hurt.get("return_date"),
                          "whole_season": hurt.get("whole_season"),
                          # The rust he carries back (the engine's own return rust for this absence), in rating points.
                          "return_penalty": _return_penalty(int(hurt.get("games") or 0))} if hurt else None)
    rotation.sort(key=lambda row: (-float(row.get("overall") or 0), row["name"]))
    # The game's four-season payroll chart: every player's salary by season, and each season's tax line and hard cap.
    horizon = [f"{season_start + offset}-{str(season_start + offset + 1)[-2:]}" for offset in range(4)] if season_start else []
    roster_ids = [p["id"] for p in active.get("players", []) if p.get("team_id") == user]
    names = {p["id"]: p.get("name") for p in active.get("players", [])}
    salary_rows = [{"id": pid, "name": names.get(pid), "salary_by_year": player_salary_table(active, pid)} for pid in roster_ids]
    cap_by_year = {}
    for season_label in horizon:
        summary = team_cap_summary(active, save, user, season_label)
        cap_by_year[season_label] = {key: summary.get(key) for key in ("salary_total_millions", "tax_line_millions", "hard_cap_millions",
                                                                       "waived_salary_millions")}
    identity = team_identity_report(active, save).get(user) or {}
    labels = {"offense": "Offense", "defense": "Defense", "spacing": "Shooting", "creation": "Shot creation",
              "rim_pressure": "Rim pressure", "rebounding": "Rebounding", "athleticism": "Athleticism",
              "defensive_disruption": "Disruption", "rim_protection": "Rim protection", "depth": "Depth",
              "playmaking": "Playmaking", "offensive_rebounding": "Off. rebounding",
              "defensive_rebounding": "Def. rebounding", "on_ball_defense": "On-ball defense",
              "ball_handling": "Ball handling", "basketball_iq": "Basketball IQ", "steal_pressure": "Steals",
              "shot_blocking": "Shot blocking", "switchability": "Switchability", "team_defense": "Team defense"}
    ranked = sorted(((labels[key], rank) for key, rank in (identity.get("ranks") or {}).items() if key in labels), key=lambda item: item[1])
    ranks = identity.get("ranks") or {}
    # Two radars (taste deck round 3): each side drawn from what it is made of, not from the side's own overall
    # ("Offense", "Defense") or neutral traits (depth, athleticism).
    radar = [{"key": key, "label": labels[key], "side": side, "rank": ranks.get(key)}
             for side, keys in (("offense", ("spacing", "creation", "playmaking", "ball_handling", "rim_pressure", "athleticism",
                                             "offensive_rebounding", "basketball_iq")),
                                ("defense", ("rim_protection", "shot_blocking", "defensive_disruption", "steal_pressure",
                                             "on_ball_defense", "switchability", "team_defense", "defensive_rebounding")))
             for key in keys if key in ranks]
    cap = team_cap_summary(active, save, user, ctx["season"])
    payout = cap.get("tax_payout") or {}
    # The slide is a picture of the team, not a table (taste deck 2026-11-23): the projected starting five, the bench,
    # and three numbers that say what kind of team this is.
    starters = [pid for _, pid in sorted(starting_lineup_slots(active, save, user, persist=False).items(), key=lambda item: int(item[0])) if pid]
    shown = {row["id"] for row in rotation}
    for pid in starters:
        if pid not in shown:
            rotation.append({**rotation_row(pid, projection.get(pid) or 0), "injury": None})
    slide = {"key": "your_team", "title": _team_ref(teams, user)["name"], "kicker": "Your team",
            "logo": _team_ref(teams, user)["abbrev"], "team_overall": (identity.get("metrics") or {}).get("overall"),
            "radar": radar, "league_teams": len(teams), "salary_horizon": {"seasons": horizon, "rows": salary_rows, "cap_by_year": cap_by_year},
            "rotation": rotation, "starters": starters, "takeaways": team_takeaways(ctx, identity),
            "overall_rank": (identity.get("ranks") or {}).get("overall"),
            "strengths": [{"label": label, "rank": rank} for label, rank in ranked[:3]],
            "weaknesses": [{"label": label, "rank": rank} for label, rank in ranked[-3:][::-1]],
            "cap": {"payroll_millions": cap.get("salary_total_millions"), "tax_line_millions": cap.get("tax_line_millions"),
                    "tax_space_millions": cap.get("tax_space_millions"), "hard_cap_millions": cap.get("hard_cap_millions"),
                    "hard_cap_space_millions": cap.get("hard_cap_space_millions")},
            "tax_payout": payout or None, "note": None}
    ctx["your_team_slide"] = slide
    return slide


SHAPE_GAP = 8          # league ranks apart before a team reads as top-heavy or deep rather than balanced
SHAPE_LOADED = 8       # top-three and bench both ranked this high or better


def team_shape(top_rank: int | None, depth_rank: int | None) -> str | None:
    """A word for how a team's talent is spread: its best three players' rank against its bench's rank."""
    if not top_rank or not depth_rank:
        return None
    if top_rank <= SHAPE_LOADED and depth_rank <= SHAPE_LOADED:
        return "Loaded"
    if depth_rank - top_rank >= SHAPE_GAP:
        return "Top-heavy"
    if top_rank - depth_rank >= SHAPE_GAP:
        return "Deep"
    return "Balanced"


def _rank_of(values: dict[str, float], team_id: str, *, highest_first: bool) -> int | None:
    if team_id not in values:
        return None
    ordered = sorted(values, key=lambda tid: (-values[tid] if highest_first else values[tid], tid))
    return 1 + ordered.index(team_id)


def team_takeaways(ctx: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    """Three league-relative numbers for the user's team: the rotation's age (weighted by the coach's projected
    minutes), how its talent is spread (best three players against the bench) and its payroll."""
    from .save import player_display_attribute_summary, team_cap_summary, team_rotation_projection

    active, save, user, teams = ctx["active"], ctx["save"], ctx["user"], ctx["teams"]
    players = {row["id"]: row for row in active.get("players", [])}
    ages: dict[str, float] = {}
    top3: dict[str, float] = {}
    payroll: dict[str, float] = {}
    for team_id in teams:
        minutes = {pid: float(m) for pid, m in team_rotation_projection(active, save, team_id, integer=True).items()
                   if float(m) > 0 and pid in players}
        weighted = [(float(players[pid].get("display_age", players[pid].get("age")) or 0), m) for pid, m in minutes.items()]
        total = sum(m for age, m in weighted if age)
        if total:
            ages[team_id] = sum(age * m for age, m in weighted if age) / total
        overalls = sorted((float(player_display_attribute_summary(active, pid).get("overall") or 0)
                           for pid, row in players.items() if row.get("team_id") == team_id), reverse=True)
        if overalls:
            top3[team_id] = sum(overalls[:3]) / len(overalls[:3])
        payroll[team_id] = float(team_cap_summary(active, save, team_id, ctx["season"]).get("salary_total_millions") or 0)
    top_rank = _rank_of(top3, user, highest_first=True)
    depth_rank = (identity.get("ranks") or {}).get("depth")
    return {"teams": len(teams),
            "age": {"value": round(ages[user], 1) if user in ages else None, "rank": _rank_of(ages, user, highest_first=False)},
            "shape": {"label": team_shape(top_rank, depth_rank), "top_rank": top_rank, "depth_rank": depth_rank},
            "payroll": {"value": round(payroll.get(user, 0.0), 1) if user in payroll else None,
                        "rank": _rank_of(payroll, user, highest_first=True)}}


def outlook_team_profile_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    """The team slide's second half, on its own card so each part has room (playtest 2026-11-22): the offense and
    defense radar beside the four-season payroll chart and the cap numbers."""
    team = ctx.get("your_team_slide") or outlook_your_team_slide(ctx)
    keep = ("title", "logo", "overall_rank", "team_overall", "radar", "league_teams", "salary_horizon", "cap", "tax_payout")
    return {"key": "team_profile", "kicker": "Your team", "note": None, **{key: team.get(key) for key in keep}}


def outlook_contracts_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    from .contract_ai import with_extension_context
    from .save import contract_salary_for_season

    active, user, season, teams = ctx["active"], ctx["user"], ctx["season"], ctx["teams"]
    try:
        extension_rows = with_extension_context(active).get("extension_candidates") or []
    except Exception:  # pragma: no cover - the extension model is optional for this slide
        extension_rows = []
    mine = [row for row in extension_rows if row.get("team_id") == user and row.get("eligible")]
    mine.sort(key=lambda row: (-float(row.get("projected_aav") or 0), row.get("player_id")))
    extensions = [{**_player_ref(active, row["player_id"]), "years_left": row.get("years_remaining"),
                   "salary_millions": round(float(row.get("current_salary") or 0) / 1e6, 1),
                   "projected_millions": round(float(row.get("projected_aav") or 0) / 1e6, 1),
                   "projected_years": row.get("projected_years")} for row in mine[:6]]
    expiring = sorted(expiring_players(active, season), key=lambda item: (-float(contract_salary_for_season(item[1], season) or 0), item[0]["id"]))
    biggest = [{**_player_ref(active, player["id"]), "team": _team_ref(teams, player.get("team_id")),
                "salary_millions": round(float(contract_salary_for_season(contract, season) or 0) / 1e6, 1), "years_left": 1}
               for player, contract in expiring[:8]]
    start, end = _season_years(season)
    return {"key": "contracts", "title": "Contracts to watch", "kicker": f"Extensions before Jan 15, {end}; next summer's free agents",
            "extensions": extensions, "expiring": biggest, "movers": trade_candidates(ctx)}


# The front offices' own trade block (transactions.trade_block_score), in plain words. The first reason is the
# biggest one the engine found.
TRADE_REASON_WORDS = {
    "older_than_team_timeline": "Older than his team's timeline", "negative_contract_value": "Paid above his value",
    "upgradeable_expensive_rotation_slot": "Pricey for his role", "position_surplus": "Crowded position",
    "veteran_surplus_slot": "Veteran at a crowded spot", "health_risk_for_win_now_team": "Injury risk for a contender",
    "blocked_prospect": "Blocked young player", "gm_listed": "Listed by his GM", "extension_talks_stalled": "Extension talks stalled",
    "soft_market_listening": "Team is listening",
}
TRADE_CANDIDATE_MIN_OVERALL = 70.0
TRADE_CANDIDATE_LIMIT = 8


def _years_left(contract: dict[str, Any] | None, season: str) -> int | None:
    from .save import contract_last_season

    end = contract_last_season(contract) if contract else None
    if not end or not season:
        return None
    return max(1, _season_years(end)[0] - _season_years(season)[0] + 1)


def trade_candidates(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Players who could be on the move: the league's trade block as the AI front offices see it (older than the
    team's timeline, paid above value, a crowded position...), other teams only, rotation-level players, most
    likely first, then by rating."""
    from .save import contract_salary_for_season
    from .transactions import with_transaction_context

    active, user, season, teams = ctx["active"], ctx["user"], ctx["season"], ctx["teams"]
    try:
        entries = with_transaction_context(active).get("trade_block_entries") or []
    except Exception:  # pragma: no cover - the trade model is optional for this slide
        LOG.exception("slideshow trade block failed")
        return []
    contracts = {row.get("player_id"): row for row in active.get("contracts", [])}
    rows = []
    for entry in entries:
        if entry.get("team_id") == user:
            continue
        ref = _player_ref(active, entry["player_id"])
        if float(ref.get("overall") or 0) < TRADE_CANDIDATE_MIN_OVERALL:
            continue
        contract = contracts.get(entry["player_id"])
        salary = contract_salary_for_season(contract, season) if contract else None
        reasons = [TRADE_REASON_WORDS.get(code, code.replace("_", " ").capitalize()) for code in entry.get("reasons") or []]
        rows.append({**ref, "team": _team_ref(teams, entry.get("team_id")), "block_score": entry.get("block_score"),
                     "salary_millions": round(float(salary) / 1e6, 1) if salary else None,
                     "years_left": _years_left(contract, season), "reason": reasons[0] if reasons else None, "reasons": reasons})
    rows.sort(key=lambda row: (-float(row.get("block_score") or 0), -float(row.get("overall") or 0), row["id"]))
    return rows[:TRADE_CANDIDATE_LIMIT]


def outlook_prospects_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    _, end = _season_years(ctx["season"])
    rows = consensus_top(ctx["active"], str(end), ctx["user"], 10)
    projected = None
    if "power_rows" not in ctx:
        outlook_power_slide(ctx)
    rank = next((row["rank"] for row in ctx["power_rows"] if row.get("is_user")), None)
    if rank:
        projected = 31 - rank
    return {"key": "prospects", "title": "Prospect watch", "kicker": f"The {end} draft class",
            "prospects": rows, "projected_pick": projected,
            "note": "Consensus is the median of all 30 teams' boards; your rank and scouting coverage come from your scouts. Your pick projects from the power rankings (worst team picks first, before the lottery)."}


def outlook_storylines_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    active, save, teams = ctx["active"], ctx["save"], ctx["teams"]
    items = []
    continuity = ctx["continuity"]
    movers = sorted(((row["team"], arrival) for row in continuity for arrival in row["arrivals"]),
                    key=lambda item: -item[1]["minutes_last_season"])
    if movers:
        team, arrival = movers[0]
        mover_id = next((p["id"] for p in active.get("players", []) if p.get("name") == arrival["name"] and p.get("team_id") == team.get("id")), None)
        items.append({"title": "Biggest offseason move", "text": f"{arrival['name']} joins {team['name']} after {arrival['minutes_last_season']} minutes elsewhere last season.",
                      "team": _team_ref(teams, team.get("id")), "players": [_player_ref(active, mover_id)] if mover_id else [],
                      "stat": {"value": arrival["minutes_last_season"], "label": "minutes last season"}})
    stars = []
    for row in continuity:
        for arrival in row["arrivals"]:
            pid = next((p["id"] for p in active.get("players", []) if p.get("name") == arrival["name"] and p.get("team_id") == row["team"]["id"]), None)
            if pid:
                stars.append((_player_ref(active, pid), row["team"]))
    stars.sort(key=lambda item: -float(item[0].get("overall") or 0))
    if stars and (not movers or stars[0][0]["name"] != movers[0][1]["name"]):
        ref, team = stars[0]
        items.append({"title": "A star in a new uniform", "text": f"{ref['name']} ({ref.get('overall')} rating) starts the season with {team['name']}.",
                      "team": _team_ref(teams, team.get("id")), "players": [ref], "stat": {"value": ref.get("overall"), "label": "rating"}})
    young: dict[str, list[tuple[float, str]]] = {}
    for player in active.get("players", []):
        if player.get("team_id") and float(player.get("age") or 99) <= 23:
            young.setdefault(player["team_id"], []).append((float(_player_ref(active, player["id"]).get("overall") or 0), player["id"]))
    if young:
        team_id = max(young, key=lambda tid: (sum(sorted((value for value, _pid in young[tid]), reverse=True)[:4]), tid))
        best = sorted(young[team_id], reverse=True)[:3]
        items.append({"title": "Youth movement", "text": f"{_team_ref(teams, team_id)['name']} has the league's best group of players 23 and under.",
                      "team": _team_ref(teams, team_id), "players": [_player_ref(active, pid) for _value, pid in best],
                      "stat": {"value": len(young[team_id]), "label": "players 23 and under"}})
    last_rows = _rank_by_record(_record_rows(active, ctx["last"]["records"]), teams)
    hot = []
    for row in last_rows[::-1][:10]:
        confidence = (save.get("owner_confidence") or {}).get(row["team_id"])
        value = confidence.get("overall") if isinstance(confidence, dict) else confidence
        if value is not None:
            hot.append((float(value), row))
    if hot:
        value, row = min(hot, key=lambda item: (item[0], item[1]["team_id"]))
        coach = next((slot for slot in save.get("staff_slots") or [] if slot.get("team_id") == row["team_id"] and slot.get("slot") == "head_coach"), None)
        if coach and value < 50:
            items.append({"title": "Coach on the hot seat", "text": f"{coach.get('name')} ({_team_ref(teams, row['team_id'])['name']}) after a {row['wins']}-{row['losses']} season, with owner confidence at {value:.0f}.",
                          "team": _team_ref(teams, row["team_id"]), "players": [], "stat": {"value": round(value), "label": "owner confidence", "tone": "bad"}})
    # Round 14: more stories so the slide fills its card: the title favourite, the biggest climber in the power
    # rankings, the rookie to watch and the veteran still going strong.
    power = ctx.get("power_rows") or []
    if power:
        top = power[0]
        items.append({"title": "Title favourite", "text": f"{top['team']['name']} open the season first in the power rankings.",
                      "team": top["team"], "players": [], "stat": {"value": "#1", "label": "power ranking"}})
        climbers = [row for row in power if row.get("change")]
        if climbers:
            climb = max(climbers, key=lambda row: (row["change"], -row["rank"]))
            if climb["change"] >= 3 and climb is not top:
                items.append({"title": "Biggest climber", "text": f"{climb['team']['name']} move up {climb['change']} places from last season's finish to No. {climb['rank']}.",
                              "team": climb["team"], "players": [], "stat": {"value": f"+{climb['change']}", "label": "places"}})
    season_start = _season_years(ctx["season"])[0] if ctx.get("season") else None
    rookies = [p for p in active.get("players", []) if p.get("team_id") and season_start and str(p.get("draft_year") or "") == str(season_start)]
    if rookies:
        best = max((_player_ref(active, p["id"]) for p in rookies), key=lambda ref: (float(ref.get("overall") or 0), ref["id"]))
        items.append({"title": "Rookie to watch", "text": f"{best['name']} is the highest-rated player in this year's rookie class.",
                      "team": _team_ref(teams, best.get("team_id")), "players": [best], "stat": {"value": best.get("overall"), "label": "rating"}})
    veterans = [p for p in active.get("players", []) if p.get("team_id") and float(p.get("age") or 0) >= 34]
    if veterans:
        vet = max((_player_ref(active, p["id"]) for p in veterans), key=lambda ref: (float(ref.get("overall") or 0), ref["id"]))
        items.append({"title": "Still going strong", "text": f"{vet['name']} is the league's best player aged 34 or older.",
                      "team": _team_ref(teams, vet.get("team_id")), "players": [vet], "stat": {"value": vet.get("age"), "label": "years old"}})
    return {"key": "storylines", "title": "Storylines", "kicker": "What to watch", "items": items[:6]}


def outlook_injuries_slide(ctx: dict[str, Any]) -> dict[str, Any]:
    active, teams, injured = ctx["active"], ctx["teams"], ctx["injured"]
    # Round 14: up to six players so the slide fills its card; when fewer than six are out more than 20 games, the
    # next-longest absences (more than 10 games) fill in.
    if len(injured) < 6:
        injured = {**long_injuries(active, ctx["save"], 10), **injured}
    rows = []
    for pid, info in injured.items():
        ref = _player_ref(active, pid)
        rows.append({**ref, "team": _team_ref(teams, ref.get("team_id")), **info})
    rows.sort(key=lambda row: (-float(row.get("overall") or 0), row["id"]))
    return {"key": "injuries", "title": "Stars starting on the sidelines", "kicker": "Expected to miss more than 10 games",
            "players": rows[:6], "note": "Injured on opening day with an expected return after more than 10 of his team's games, ranked by player rating."}


# --------------------------------------------------------------------------------------------- hooks


def ensure_year_end_recap(canonical: dict[str, Any], save: dict[str, Any], save_path: str | Path | None = None) -> dict[str, Any] | None:
    """Build and store the recap once the Finals are over (idempotent)."""
    if (save.get("playoff_state") or {}).get("status") != "completed":
        return None
    season = str((save.get("meta") or {}).get("season") or "")
    existing = stored_recap(save, season)
    if existing:
        return existing
    recap = build_year_end_recap(canonical, save, save_path)
    slideshow_store(save)["recaps"][season] = recap
    return recap


OUTLOOK_FORMAT = 4   # bump when the outlook's slides change shape; a preseason outlook in an older format is rebuilt


def ensure_preseason_outlook(canonical: dict[str, Any], save: dict[str, Any], save_path: str | Path | None = None) -> dict[str, Any] | None:
    """Build and store the outlook at the start of a season (idempotent)."""
    season = str((save.get("meta") or {}).get("season") or "")
    existing = stored_outlook(save, season)
    stale = existing and existing.get("format") != OUTLOOK_FORMAT and str((save.get("state") or {}).get("phase") or "") == "preseason"
    if existing and not stale:
        return existing
    if not outlook_due(save):
        return None
    outlook = build_preseason_outlook(canonical, save, save_path)
    outlook["format"] = OUTLOOK_FORMAT
    slideshow_store(save)["outlooks"][season] = outlook
    return outlook
