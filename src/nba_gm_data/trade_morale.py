"""What a trade does to morale and chemistry (TRADE-FORECASTS, 2026-11-26).

Stored morale used to move only after games and press answers, so a trade changed nothing. Now every applied trade
(two-team and multi-team, user and AI) moves the stored numbers once, on the day it happens, and the trade room shows
the same numbers beforehand (project_trade_morale): compute_trade_morale works out the effect, apply_trade_morale
writes exactly its "after" values.

Four effects, all small next to a season of games (a win moves team morale 1-3.5 points):

1. Role. Each player on a team in the deal whose projected minutes change (the coach's projection, now and with the
   new rosters: save.team_rotation_projection) moves part of the way to the role satisfaction his new minutes carry,
   on the same minutes-to-role scale the save's opening morale uses (save.initial_player_morale: 28+ minutes 60,
   18+ 56, 10+ 51, less 46), and his overall morale by the same 0.35 weight that scale has there. Basis: role and
   playing time are what players and agents most often cite when a player wants out (judgment; the size is the save's
   own scale, applied 60% at once and left to games to finish). Shifts under 2 minutes are left out.
2. The traded player. He leaves his teammates and city: overall morale -1.0, and his confidence in his team moves
   halfway to his new team's morale. Basis: judgment, kept small.
3. Chemistry. A team's chemistry drops by 8 points times the share of its rotation minutes that turned over (the
   larger of the minutes it lost and the minutes its new players take): a one-for-one starter swap (about 12% of the
   minutes) costs about 1 point, a blockbuster (35%) about 3. Basis: roster continuity (the share of minutes from
   returning players) is a small but real early-season edge in NBA results; chemistry recovers with games.
4. Stars. When one of a team's two best players (by overall rating) who plays 24+ projected minutes leaves, the team's morale
   drops 1.5 and its confidence 2.0, and each teammate who stays loses 2.0 confidence in the team and 0.7 morale;
   a star arriving does the opposite. Basis: judgment, kept modest.

The morale model has no friendships or other player-to-player links, so a traded close friend changes nothing.
Morale is stored and shown; the game engine does not read it (no effect on results).
"""
from __future__ import annotations

from typing import Any

ROLE_LEVELS = ((0.0, 44.0), (10.0, 51.0), (18.0, 56.0), (28.0, 60.0), (36.0, 62.0))
ROLE_SHARE = 0.6
ROLE_MIN_CHANGE = 2.0   # minutes; smaller shifts in the coach's projection are noise, not a new role
OVERALL_PER_ROLE = 0.35
TRADED_OVERALL = -1.0
TRADED_TEAM_CONFIDENCE_SHARE = 0.5
CHEMISTRY_PER_TURNOVER = 8.0
STAR_MINUTES = 24.0   # a regular starter in the coach's projection (it spreads minutes: stars often project 28-32)
STAR_TEAM_OVERALL = 1.5
STAR_TEAM_CONFIDENCE = 2.0
STAR_TEAMMATE_CONFIDENCE = 2.0
STAR_TEAMMATE_OVERALL = 0.7

TEAM_DEFAULT = {"overall": 58.0, "chemistry": 58.0, "confidence": 56.0}   # save.apply_team_morale_delta
PLAYER_DEFAULT = {"overall": 56.0, "role_satisfaction": 55.0, "team_confidence": 55.0, "contract_satisfaction": 55.0}


def role_level(minutes: float) -> float:
    """Role satisfaction a player's minutes carry (save.initial_player_morale's steps, joined by straight lines)."""
    minutes = max(0.0, float(minutes or 0.0))
    for (low_m, low_v), (high_m, high_v) in zip(ROLE_LEVELS, ROLE_LEVELS[1:]):
        if minutes <= high_m:
            return low_v + (high_v - low_v) * (minutes - low_m) / (high_m - low_m)
    return ROLE_LEVELS[-1][1]


def _clamp(value: float) -> float:
    return round(min(100.0, max(0.0, value)), 2)


def trade_moves(canonical: dict[str, Any], proposal: dict[str, Any]) -> dict[str, str]:
    """{player_id: destination team id} for a two-team proposal, a multi-team one (transfers) or the trade room's
    payload ({"moves": [{"to_team", "player_ids"}]}). Players already on the destination are left out."""
    from .save import resolve_team
    payload = proposal.get("proposal") if isinstance(proposal.get("proposal"), dict) else proposal
    players = {player.get("id"): player for player in canonical.get("players", [])}
    moves: dict[str, str] = {}

    def move(player_id: Any, destination: Any) -> None:
        player = players.get(str(player_id))
        if player is not None and destination and player.get("team_id") != destination:
            moves[str(player_id)] = str(destination)

    for leg in payload.get("moves") or []:
        destination = resolve_team(canonical, str(leg.get("to_team")))["id"]
        for player_id in leg.get("player_ids") or []:
            move(player_id, destination)
    for edge in payload.get("transfers") or []:
        for asset in edge.get("assets") or []:
            if asset.get("kind") == "player":
                move(asset.get("id"), edge.get("to_team_id"))
    for side, destination in (("from_assets", payload.get("to_team_id")), ("to_assets", payload.get("from_team_id"))):
        for asset in payload.get(side) or []:
            if asset.get("kind") == "player":
                move(asset.get("id"), destination)
    return moves


def hypothetical_league(canonical: dict[str, Any], moves: dict[str, str]) -> dict[str, Any]:
    """The league with each moved player on his new team (internal caches, keys starting "_", left behind: they
    index the real rosters)."""
    league = {key: value for key, value in canonical.items() if not str(key).startswith("_")}
    league["players"] = [{**player, "team_id": moves[player["id"]]} if player.get("id") in moves else player
                         for player in canonical.get("players", [])]
    return league


def compute_trade_morale(canonical: dict[str, Any], save: dict[str, Any], moves: dict[str, str]) -> dict[str, Any]:
    """The morale and chemistry a trade would store: before and after for each team in it and each player whose
    numbers move, with the reasons in plain words. canonical: the save's league before the trade."""
    from .save import player_attribute_summary, team_rotation_projection
    players = {player.get("id"): player for player in canonical.get("players", [])}
    origin = {player_id: players[player_id].get("team_id") for player_id in moves}
    team_ids: list[str] = []
    for player_id, destination in moves.items():
        for team_id in (origin[player_id], destination):
            if team_id and team_id not in team_ids:
                team_ids.append(team_id)
    if not moves:
        return {"moved_player_ids": [], "teams": [], "players": []}
    after_league = hypothetical_league(canonical, moves)
    before_minutes = {team_id: team_rotation_projection(canonical, save, team_id, integer=False) for team_id in team_ids}
    after_minutes = {team_id: team_rotation_projection(after_league, save, team_id, integer=False) for team_id in team_ids}
    rosters_before = {team_id: [p for p in canonical.get("players", []) if p.get("team_id") == team_id] for team_id in team_ids}
    rosters_after = {team_id: [p for p in after_league["players"] if p.get("team_id") == team_id] for team_id in team_ids}

    def stars(team_id: str, roster: list[dict[str, Any]], minutes: dict[str, float]) -> set[str]:
        ranked = sorted(roster, key=lambda p: (-float(player_attribute_summary(canonical, p["id"]).get("overall") or 0.0), str(p["id"])))
        return {p["id"] for p in ranked[:2] if float(minutes.get(p["id"]) or 0.0) >= STAR_MINUTES}

    team_store = save.get("team_morale") or {}
    player_store = save.get("player_morale") or {}
    team_rows: dict[str, dict[str, Any]] = {}
    star_shift: dict[str, int] = {}
    for team_id in team_ids:
        before = {**TEAM_DEFAULT, **(team_store.get(team_id) or {})}
        after = dict(before)
        reasons: list[str] = []
        total_before = sum(float(v or 0.0) for v in before_minutes[team_id].values()) or 1.0
        total_after = sum(float(v or 0.0) for v in after_minutes[team_id].values()) or 1.0
        lost = sum(float(before_minutes[team_id].get(pid) or 0.0) for pid, dest in moves.items() if origin[pid] == team_id) / total_before
        new = sum(float(after_minutes[team_id].get(pid) or 0.0) for pid, dest in moves.items() if dest == team_id) / total_after
        turnover = max(lost, new)
        if turnover > 0:
            after["chemistry"] = before["chemistry"] - CHEMISTRY_PER_TURNOVER * turnover
            reasons.append(f"{round(turnover * 100)}% of the rotation's minutes change hands")
        gone = {pid for pid in stars(team_id, rosters_before[team_id], before_minutes[team_id]) if moves.get(pid, team_id) != team_id}
        came = {pid for pid in stars(team_id, rosters_after[team_id], after_minutes[team_id]) if pid in moves and moves[pid] == team_id}
        shift = len(came) - len(gone)
        star_shift[team_id] = shift
        if shift:
            after["overall"] = after["overall"] + STAR_TEAM_OVERALL * shift
            after["confidence"] = after["confidence"] + STAR_TEAM_CONFIDENCE * shift
        for pid in sorted(gone):
            reasons.append(f"{players[pid].get('name', pid)} leaves")
        for pid in sorted(came):
            reasons.append(f"{players[pid].get('name', pid)} arrives")
        after = {key: _clamp(value) if key in TEAM_DEFAULT else value for key, value in after.items()}
        team_rows[team_id] = {"team_id": team_id, "before": {k: before[k] for k in TEAM_DEFAULT},
                              "after": {k: after[k] for k in TEAM_DEFAULT}, "rotation_turnover": round(turnover, 3),
                              "reasons": reasons}

    player_rows = []
    seen: set[str] = set()
    for team_id in team_ids:
        for player in rosters_before[team_id] + rosters_after[team_id]:
            player_id = player["id"]
            if player_id in seen:
                continue
            seen.add(player_id)
            old_team = origin.get(player_id, player.get("team_id"))
            new_team = moves.get(player_id, old_team)
            minutes_before = float(before_minutes.get(old_team, {}).get(player_id) or 0.0)
            minutes_after = float(after_minutes.get(new_team, {}).get(player_id) or 0.0)
            before = {**PLAYER_DEFAULT, **(player_store.get(player_id) or {})}
            after = dict(before)
            reasons = []
            role_delta = ROLE_SHARE * (role_level(minutes_after) - role_level(minutes_before))
            if abs(minutes_after - minutes_before) >= ROLE_MIN_CHANGE:
                after["role_satisfaction"] += role_delta
                after["overall"] += OVERALL_PER_ROLE * role_delta
                reasons.append(f"projected minutes {minutes_before:.0f} to {minutes_after:.0f}")
            if player_id in moves:
                after["overall"] += TRADED_OVERALL
                target = team_rows[new_team]["after"]["overall"]
                after["team_confidence"] += TRADED_TEAM_CONFIDENCE_SHARE * (target - after["team_confidence"])
                reasons.append("traded")
            elif star_shift.get(new_team):
                shift = star_shift[new_team]
                after["team_confidence"] += STAR_TEAMMATE_CONFIDENCE * shift
                after["overall"] += STAR_TEAMMATE_OVERALL * shift
                reasons.append("a star arrives" if shift > 0 else "a star leaves")
            if not reasons:
                continue
            after = {key: _clamp(value) if key in PLAYER_DEFAULT else value for key, value in after.items()}
            player_rows.append({
                "player_id": player_id, "name": player.get("name"), "team_id_before": old_team, "team_id_after": new_team,
                "minutes_before": round(minutes_before, 1), "minutes_after": round(minutes_after, 1),
                "before": {k: before[k] for k in PLAYER_DEFAULT}, "after": {k: after[k] for k in PLAYER_DEFAULT},
                "reasons": reasons,
            })
    player_rows.sort(key=lambda row: (team_ids.index(row["team_id_after"]) if row["team_id_after"] in team_ids else 99,
                                      -row["minutes_after"], str(row["name"])))
    return {"moved_player_ids": sorted(moves), "teams": [team_rows[t] for t in team_ids], "players": player_rows}


def apply_trade_morale(save: dict[str, Any], effect: dict[str, Any]) -> None:
    """Store a computed effect: each team's and player's "after" values (other stored fields are kept)."""
    for row in effect.get("teams") or []:
        save.setdefault("team_morale", {}).setdefault(row["team_id"], {}).update(row["after"])
    for row in effect.get("players") or []:
        save.setdefault("player_morale", {}).setdefault(row["player_id"], {}).update(row["after"])


def project_trade_morale(canonical: dict[str, Any], save: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """The morale and chemistry the trade would store if applied now (compute_trade_morale); nothing is saved.

    canonical: the save's league (save.canonical_with_save). proposal: a two-team proposal (from_team_id, to_team_id,
    from_assets, to_assets), a multi-team one (transfers) or the trade room's {"moves": [{"to_team", "player_ids"}]}."""
    return compute_trade_morale(canonical, save, trade_moves(canonical, proposal))
