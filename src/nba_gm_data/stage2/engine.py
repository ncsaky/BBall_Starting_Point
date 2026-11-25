"""Entry point for `sim_game_with_context(..., engine="stage2")`: the Stage 2 possession engine plays the whole game.

The game sim's shared preparation hands over the game, both teams and tonight's player pools (who is available and
their planned minutes). From there:
- the same pre-game steps today's engine applies to generated games (sandbox-sim): opponent-adjusted replacement
  minutes, the coach's matchup minutes, the ramp-up for players back from an absence, and human teams' game-day
  rotation; then the starters (the real ones in replayed games, the coach's five otherwise);
- each player's card (stage2.cards) from his 94 inputs as the engine currently uses them; players with no inputs
  (replayed players who are no longer in the league) get the league-median card (documented stand-in);
- team terms from what exists: home court (today's fitted home-court points), the coach's offense/defense/tempo
  ratings (sim.coach_effect) and rest days (sim.rest_effect), as make log-odds and pace;
- stage2.game plays it (clock, possessions, substitutions) and returns today's box-score format.

Normal gameplay never selects this engine (default OFF; AGENTS.md rule 6).
"""
from __future__ import annotations

import random
from typing import Any

from .cards import card_for, flat_for_player, generic_flat, means_for
from .coach import Coach, roles_for
from .game import LOOP, Game, TeamState, box_lines, team_line

NOTE = ("Stage 2 possession engine (S2-COACH v1): every possession played; tonight's plan from today's coach model, "
        "the in-game coach decides who plays at every stoppage.")
_LEAGUE_CONSTANTS: dict[str, dict] = {}
GAME_HOOK = None   # research hook (scripts/research/s2_coach_check.py): called with (game, extra, game_id); None in play


def _group(player: dict[str, Any]) -> str:
    from ..input_estimator import _position
    try:
        return _position(player)
    except Exception:  # noqa: BLE001 - a stand-in group is fine for an unusual position string
        return "wing"


def league_constants(root) -> dict[str, float]:
    """League centres for the lineup indices (so an average lineup has no defense shift), from the league's players
    weighted by their real 2025-26 minutes (targets file), and random five-man lineups drawn the same way."""
    key = str(root)
    if key in _LEAGUE_CONSTANTS:
        return _LEAGUE_CONSTANTS[key]
    import json
    from pathlib import Path
    from .game_contexts import GENERIC, league_flat_inputs
    flats = league_flat_inputs(root)
    means = means_for(root)
    try:
        targets = json.loads((Path(root) / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
        minutes = {pid: float(row.get("minutes") or 0.0) for pid, row in targets.items()}
    except (OSError, ValueError, KeyError):
        minutes = {}
    cards, weights = [], []
    for pid, flat in flats.items():
        if pid == GENERIC:
            continue
        w = minutes.get(pid, 0.0)
        if w <= 0:
            continue
        cards.append(card_for(pid, pid, flat, means))
        weights.append(w)
    total = sum(weights)
    wmean = lambda f: sum(w * f(c) for c, w in zip(cards, weights)) / total  # noqa: E731
    rng = random.Random(20261121)
    rims, press = [], []
    for _ in range(4000):
        five = []
        while len(five) < 5:
            c = rng.choices(cards, weights)[0]
            if c not in five:
                five.append(c)
        r = sorted((c.rim_d for c in five), reverse=True)
        rims.append(.6 * r[0] + .4 * sum(r) / 5)
        press.append(sum(c.press_d for c in five) / 5)
    out = {"rim_center": sum(rims) / len(rims), "press_center": sum(press) / len(press),
           "stl_mean": wmean(lambda c: c.stl_w), "blk_mean": wmean(lambda c: c.blk_w), "ns_mean": wmean(lambda c: c.ns_mult),
           "pace_mean": wmean(lambda c: c.pace), "trans_mean": wmean(lambda c: c.trans_pref),
           "perim_mean": wmean(lambda c: c.perim_d), "create_center": wmean(lambda c: c.create),
           "space_center": wmean(lambda c: c.space),
           # Player-on-player indices (S2-TOTALS-MATCHUPS), centred on the league's minutes-weighted player.
           "closeout_center": wmean(lambda c: c.closeout_d), "onball_center": wmean(lambda c: c.onball_d),
           "length_center": wmean(lambda c: c.length), "burst_center": wmean(lambda c: c.burst),
           "contain_center": wmean(lambda c: c.contain_d), "post_center": wmean(lambda c: c.post_d),
           "rot_center": wmean(lambda c: c.rot_d), "lanes_center": wmean(lambda c: c.lanes_d),
           "fctrl_center": wmean(lambda c: c.foul_ctrl), "press_center_player": wmean(lambda c: c.press_d),
           # Pick-and-roll (S2-COACH): one defender's rim protection, centred on the league's minutes-weighted player.
           "rimd_center": wmean(lambda c: c.rim_d)}
    _LEAGUE_CONSTANTS[key] = out
    return out


def _prepare_pools(context, game, home_team, away_team, home_players, away_players, mode, seed, game_id):
    """Today's pre-game minutes steps (generated games), so both engines start from the same planned minutes."""
    from ..sim import (coach_ratings, coaches_on_date, game_day_rotation, matchup_adjusted_player_pool,
                       return_ramped_player_pool)
    canonical = context["canonical"]
    game_date = game.get("gameDate") or game.get("date")
    coach_by_team = coaches_on_date(context, context.get("indices", {}).get("coach_by_team")
                                    or {rating.team_id: rating for rating in coach_ratings(canonical)}, game_date)
    if mode == "sandbox-sim":
        from ..absence_fill import opponent_adjusted_pool
        home_players, away_players = (opponent_adjusted_pool(canonical, home_players, away_players),
                                      opponent_adjusted_pool(canonical, away_players, home_players))
        home_players = matchup_adjusted_player_pool(canonical, home_players, away_players,
                                                    coach_by_team.get(home_team["id"]), game_id, seed)
        away_players = matchup_adjusted_player_pool(canonical, away_players, home_players,
                                                    coach_by_team.get(away_team["id"]), game_id, seed)
        home_players = return_ramped_player_pool(home_players, coach_by_team.get(home_team["id"]))
        away_players = return_ramped_player_pool(away_players, coach_by_team.get(away_team["id"]))
        if "_human_team_ids" in canonical:
            home_players = game_day_rotation(home_players, home_team["id"], game_id, seed)
            away_players = game_day_rotation(away_players, away_team["id"], game_id, seed)
    return home_players, away_players, coach_by_team


def _team_state(context, team, pool, starters, coach, rest_context, is_home, league, opp_context=None,
                loop: dict | None = None, reserves: list | None = None,
                coach_rng: random.Random | None = None) -> tuple[TeamState, list, list]:
    from ..sim import AWAY_COURT_RATING, HOME_COURT_RATING, coach_effect, game_environment_effect, rest_effect
    from ..utils import clamp
    root = context["root"]
    canonical = context["canonical"]
    means = means_for(root)
    generic = generic_flat(root)
    items = [item for item in pool if float(item.get("minutes") or 0.0) > 0]
    if len(items) < 5:
        items = sorted(pool, key=lambda it: -float(it.get("minutes") or 0.0))[:max(5, len(items))]
    n_plan = len(items)
    # Healthy players outside tonight's rotation (generated games): the coach's garbage-time call-ups (today's
    # game_minutes: at most GARBAGE_EXTRAS_LIMIT, best first).
    used = {item["player"].get("id") for item in items}
    items = items + [{**item, "minutes": 0.0, "_reserve": True} for item in (reserves or [])
                     if item["player"].get("id") not in used]
    cards, players, groups, targets, starter_idx = [], [], [], [], []
    for idx, item in enumerate(items):
        player = item["player"]
        flat = flat_for_player(canonical, player) or generic
        penalty = _health_penalty(item)
        cards.append(card_for(player.get("id") or player.get("name"), player.get("name", ""), flat, means,
                              _group(player), penalty))
        players.append(player)
        groups.append(_group(player))
        targets.append(max(0.5, float(item.get("minutes") or 0.0)) if idx < n_plan else 0.0)
        if player.get("id") in starters and idx < n_plan:
            starter_idx.append(idx)
    ce = coach_effect(coach)
    home_mod = HOME_COURT_RATING if is_home else AWAY_COURT_RATING
    rest = rest_effect(rest_context)
    L = dict(LOOP, **(loop or {}))
    k = L["k_eff"]
    # Recent form (today's engine's game-environment term: both teams' last ten real games' scoring before tonight,
    # in points per 100 and possessions). Scaled by the loop's fitted k_form_off / k_form_pace (0 = off).
    env = (game_environment_effect(rest_context, opp_context) if (L["k_form_off"] or L["k_form_pace"])
           else {"offense": 0.0, "pace": 0.0})
    eff = k * (home_mod + float(ce.get("offense", 0.0)) + float(rest.get("offense", 0.0))
               + L["k_form_off"] * float(env.get("offense", 0.0)))
    eff_def = k * float(ce.get("defense", 0.0))
    tempo = clamp(float(ce.get("tempo", 0.0)) + float(rest.get("pace", 0.0)), -4.0, 4.0)
    state = TeamState(team["id"], team["abbrev"], cards, targets, starter_idx, groups, eff, tempo, league, eff_def=eff_def,
                      coach_matchup=coach_matchup_scale(coach))
    state.form_pace = L["k_form_pace"] * float(env.get("pace", 0.0))
    state.reserve = [idx >= n_plan for idx in range(len(items))]
    if L.get("coach"):
        state.coach = build_coach(state, items, coach_rng or random.Random(f"{team['id']}:stage2-coach"),
                                  replay=bool(items) and all(item.get("actual") for item in items[:n_plan]))
    return state, players, items


def build_coach(state: TeamState, items: list, rng: random.Random, replay: bool = False) -> Coach:
    """Tonight's in-game coach for one team: roles from the plan, the inputs he reads (conditioning, recovery), tonight's
    tired legs and rust, and any in-game injury from the health model (generated games)."""
    n = len(items)
    starters = set(state.starters)
    plans_min = [t / 60.0 for t in state.target_s]
    roles = roles_for([i in starters for i in range(n)], plans_min, [c.usage for c in state.cards], state.reserve)
    fatigue = [float(item.get("health_fatigue") or 0.0) for item in items]
    rust = [float(item.get("health_rust") or 0.0) > 0.0 or float(item.get("return_minutes_factor") or 1.0) < 1.0
            for item in items]
    injury = [item.get("health_injury_exit") for item in items]
    return Coach(state, roles=roles, plan_s=list(state.target_s), flats=[c.flat for c in state.cards], fatigue=fatigue,
                 rust=rust, injury_exit=injury, rng=rng, replay=replay)


def projected_pace_mean(context, league) -> float:
    """Generated games: the league's pace habit weighted by projected minutes. The coaches' rotations give quicker
    players more minutes than real 2025-26 minutes did, which would add possessions to every game now that both fives'
    habits set the pace; the habit should spread teams, not move the league (today's engine does the same,
    sim.league_pace_habit_reference)."""
    cache = context.setdefault("sim_cache", {})
    if "stage2_pace_mean" not in cache:
        canonical = context["canonical"]
        num = den = 0.0
        for player in canonical.get("players", []):
            minutes = float(player.get("minutes_projection") or 0.0)
            if minutes <= 0 or player.get("_inactive_player"):
                continue
            flat = flat_for_player(canonical, player)
            if flat is None:
                continue
            num += minutes * float(flat.get("T05", .5))
            den += minutes
        cache["stage2_pace_mean"] = num / den if den else league["pace_mean"]
    return cache["stage2_pace_mean"]


def coach_matchup_scale(coach) -> float:
    """How much this coach puts his best on-ball stopper on the top scorer: 1 at an average matchup rating (3 of 5),
    0.5-1.5 across the range (stand-in scale; the coach inputs hold no switching or scheme habit)."""
    try:
        r = float((coach.ratings or {}).get("matchup_adjustments", 3.0)) if coach is not None else 3.0
    except (TypeError, ValueError, AttributeError):
        r = 3.0
    return min(1.5, max(.5, 1.0 + .25 * (r - 3.0)))


def _health_penalty(item: dict[str, Any]) -> float:
    fatigue = float(item.get("health_fatigue") or 0.0)
    rust = float(item.get("health_rust") or 0.0)
    if fatigue <= 0 and rust <= 0:
        return 0.0
    from ..sim import FATIGUE_PLAYER_PENALTY, FATIGUE_PLAYER_THRESHOLD, rust_penalty_points
    from ..utils import clamp
    return clamp(max(0.0, fatigue - FATIGUE_PLAYER_THRESHOLD) * FATIGUE_PLAYER_PENALTY, 0.0, 2.5) + rust_penalty_points(rust)


def play_stage2_game(context: dict[str, Any], game: dict[str, Any], home_team: dict[str, Any], away_team: dict[str, Any],
                     home_players: list[dict[str, Any]], away_players: list[dict[str, Any]], *, game_id: str, mode: str,
                     seed: int, loop: dict | None = None) -> tuple[Game, dict]:
    from ..sim import game_context_for_team, game_starters, team_fatigue_excess
    league = league_constants(context["root"])
    if mode == "sandbox-sim":
        league = {**league, "pace_mean": projected_pace_mean(context, league)}
    home_players, away_players, coach_by_team = _prepare_pools(context, game, home_team, away_team, home_players,
                                                               away_players, mode, seed, game_id)
    lineups = context.get("starting_lineups") or {}
    starters = (game_starters(home_players, lineups.get(home_team["id"]), mode)
                | game_starters(away_players, lineups.get(away_team["id"]), mode))
    home_ctx = game_context_for_team(context, game, home_team)
    away_ctx = game_context_for_team(context, game, away_team)
    if mode == "sandbox-sim":
        h, a = team_fatigue_excess(home_players), team_fatigue_excess(away_players)
        if h is not None:
            home_ctx = {**(home_ctx or {}), "team_fatigue": round(h, 3)}
        if a is not None:
            away_ctx = {**(away_ctx or {}), "team_fatigue": round(a, 3)}
    reserves = {"home": [], "away": []}
    if mode == "sandbox-sim":
        from ..sim import available_reserves
        game_date = game.get("gameDate") or game.get("date")
        for side, team, pool in (("home", home_team, home_players), ("away", away_team, away_players)):
            used = {item["player"]["id"] for item in pool}
            reserves[side] = [item for item in available_reserves(context, team, game_id, game_date)
                              if item["player"]["id"] not in used]
    home, hp, hi = _team_state(context, home_team, home_players, starters, coach_by_team.get(home_team["id"]), home_ctx, True,
                               league, away_ctx, loop, reserves["home"],
                               random.Random(f"{seed}:{game_id}:{mode}:stage2-coach:{home_team['id']}"))
    away, ap, ai = _team_state(context, away_team, away_players, starters, coach_by_team.get(away_team["id"]), away_ctx, False,
                               league, home_ctx, loop, reserves["away"],
                               random.Random(f"{seed}:{game_id}:{mode}:stage2-coach:{away_team['id']}"))
    rng = random.Random(f"{seed}:{game_id}:{mode}:stage2")
    g = Game(home, away, rng, loop=loop)
    g.play()
    return g, {"home": (hp, hi), "away": (ap, ai), "starters": starters}


def simulate_stage2_game(context: dict[str, Any], game: dict[str, Any], home_team: dict[str, Any],
                         away_team: dict[str, Any], home_players: list[dict[str, Any]],
                         away_players: list[dict[str, Any]], *, game_id: str, mode: str, seed: int):
    from ..schema import SimGameResult
    from ..utils import stable_id
    g, extra = play_stage2_game(context, game, home_team, away_team, home_players, away_players,
                                game_id=game_id, mode=mode, seed=seed)
    if GAME_HOOK is not None:
        GAME_HOOK(g, extra, game_id)
    starters = extra["starters"]
    home_lines = box_lines(g.home, *extra["home"], home_team["abbrev"], starters)
    away_lines = box_lines(g.away, *extra["away"], away_team["abbrev"], starters)
    home_tl = team_line(g.home, home_lines, g.away)
    away_tl = team_line(g.away, away_lines, g.home)
    overtime = max(0, g.period - 4)
    notes = NOTE + (f" Overtime resolved over {overtime} period(s)." if overtime else "")
    return SimGameResult(
        id=stable_id("sim_game", game_id, mode, seed), game_id=str(game_id), mode=mode, seed=seed,
        home_team_id=home_team["id"], away_team_id=away_team["id"],
        home_score=int(home_tl["points"]), away_score=int(away_tl["points"]),
        possessions=round((g.home.possessions + g.away.possessions) / 2, 1),
        player_lines=home_lines + away_lines, team_lines=[home_tl, away_tl],
        source_ids=["src_player_skill_input_2025_26", "src_stage2_possession_loop_v1"], notes=notes,
        plus_minus_tracking={"status": "live", "version": "stage2_on_court_v1"},
    )
