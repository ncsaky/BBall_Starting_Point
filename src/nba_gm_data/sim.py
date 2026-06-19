from __future__ import annotations

import json
import math
import random
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .research import BETTING_ODDS_FILE, COACH_REPUTATION_FILE, GAME_BOXSCORES_FILE, TRACKING_SOURCES_FILE
from .schema import CoachRating, SimFeatureVector, SimGameResult, ValidationReport, to_plain
from .teams import TEAM_INFO
from .utils import normalize_name, stable_id


SCHEDULE_FILE = Path("NBA Schedule/schedule_v2025_2026.json")
REAL_MINUTES_FILE = Path("NBA Schedule/real_game_minutes_2025_26.json")
SIM_MODES = {"replay-real-minutes", "sandbox-sim"}
MARGIN_DISTRIBUTION_MIN_STD = 12.0
LINEUP_QUALITY_MARGIN_FACTOR = 0.34
LINEUP_QUALITY_EFFECT_CAP = 10.2
PROBABILITY_BETA_ALPHA = 6.0
PROBABILITY_MARGIN_WEIGHT_BASE = 0.90
PROBABILITY_MARGIN_WEIGHT_PER_RUN = 0.003
_SIM_FEATURE_CACHE: dict[int, dict[str, Any]] = {}

COACH_DEFAULTS = {
    "rotation_trust": 3.0,
    "development": 3.0,
    "offensive_structure": 3.0,
    "defensive_structure": 3.0,
    "matchup_adjustments": 3.0,
    "player_buy_in": 3.0,
    "playoff_preparation": 3.0,
    "experimentation": 3.0,
    "hands_on_control": 3.0,
}

COACH_REPUTATION_OVERRIDES = {
    "Erik Spoelstra": {"defensive_structure": 4.8, "matchup_adjustments": 5.0, "playoff_preparation": 5.0, "player_buy_in": 4.6, "offensive_structure": 4.2},
    "Rick Carlisle": {"offensive_structure": 4.8, "matchup_adjustments": 4.7, "playoff_preparation": 4.6, "experimentation": 4.2},
    "Mark Daigneault": {"development": 4.8, "rotation_trust": 4.6, "matchup_adjustments": 4.5, "player_buy_in": 4.7},
    "Tyronn Lue": {"matchup_adjustments": 4.8, "player_buy_in": 4.5, "playoff_preparation": 4.6, "hands_on_control": 4.1},
    "Ime Udoka": {"defensive_structure": 4.7, "player_buy_in": 4.5, "hands_on_control": 4.4, "development": 4.1},
    "Kenny Atkinson": {"development": 4.5, "offensive_structure": 4.1, "player_buy_in": 4.0},
    "Nick Nurse": {"matchup_adjustments": 4.6, "experimentation": 4.5, "defensive_structure": 4.2, "hands_on_control": 4.4},
    "Tom Thibodeau": {"defensive_structure": 4.4, "hands_on_control": 4.8, "rotation_trust": 2.4, "playoff_preparation": 4.0},
    "Steve Kerr": {"offensive_structure": 4.5, "player_buy_in": 4.4, "playoff_preparation": 4.5, "experimentation": 4.0},
    "Billy Donovan": {"development": 4.0, "player_buy_in": 3.8, "rotation_trust": 3.5},
    "Jamahl Mosley": {"development": 4.0, "player_buy_in": 4.0, "defensive_structure": 3.6},
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_sim_context(root: str | Path, canonical: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(root)
    if canonical is None:
        canonical = load_json(root / "data/canonical/universe_2025_26_preseason.json")
    schedule = load_json(root / SCHEDULE_FILE)["games"]
    boxscores = load_optional_research(root, GAME_BOXSCORES_FILE, "games")
    context = {
        "root": root,
        "canonical": canonical,
        "schedule": schedule,
        "real_minutes": load_json(root / REAL_MINUTES_FILE) if (root / REAL_MINUTES_FILE).exists() else {},
        "boxscores": boxscores,
        "odds": load_odds(root),
        "manifestos": load_manifestos(root),
        "sim_cache": {"player_pools": {}, "team_features": {}, "game_contexts": {}},
    }
    context["indices"] = build_sim_indices(context)
    return context


def load_optional_research(root: Path, relative: Path, key: str) -> list[dict[str, Any]]:
    path = root / relative
    if not path.exists():
        return []
    return list(load_json(path).get(key, []))


def load_odds(root: Path) -> dict[str, dict[str, Any]]:
    path = root / BETTING_ODDS_FILE
    if not path.exists():
        return {}
    payload = load_json(path)
    return {str(game["game_id"]): normalize_odds_record(game) for game in payload.get("games", [])}


def load_manifestos(root: Path) -> dict[str, str]:
    directory = root / "Pre-Season manifestos"
    if not directory.exists():
        return {}
    return {path.stem.upper(): path.read_text(encoding="utf-8") for path in sorted(directory.glob("*.txt"))}


def normalize_odds_record(record: dict[str, Any]) -> dict[str, Any]:
    moneyline = dict(record.get("moneyline") or {})
    home_odds = moneyline.get("home_american")
    away_odds = moneyline.get("away_american")
    if home_odds is not None and away_odds is not None:
        home_raw = american_to_implied_probability(float(home_odds))
        away_raw = american_to_implied_probability(float(away_odds))
        no_vig = no_vig_probabilities(home_raw, away_raw)
        moneyline["home_implied_no_vig"] = no_vig["home"]
        moneyline["away_implied_no_vig"] = no_vig["away"]
    return {
        **record,
        "moneyline": moneyline,
        "spread": dict(record.get("spread") or {}),
        "total": dict(record.get("total") or {}),
        "player_props": list(record.get("player_props") or []),
    }


def build_sim_indices(context: dict[str, Any]) -> dict[str, Any]:
    canonical = context["canonical"]
    teams_by_espn_id = espn_team_id_map(canonical)
    espn_id_by_team_id = {team["id"]: espn_id for espn_id, team in teams_by_espn_id.items()}
    schedule_by_game_id = {str(game.get("externalGameId")): game for game in context["schedule"]}
    boxscores_by_game_id = {str(game.get("game_id")): game for game in context["boxscores"]}
    schedule_by_team_espn_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    boxscores_by_team_espn_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for game in context["schedule"]:
        for key in ["homeTeamId", "awayTeamId"]:
            value = game.get(key)
            if value is not None:
                schedule_by_team_espn_id[str(value)].append(game)
    for game in context["boxscores"]:
        for key in ["home_team_id", "away_team_id"]:
            value = game.get(key)
            if value is not None:
                boxscores_by_team_espn_id[str(value)].append(game)
    for games in schedule_by_team_espn_id.values():
        games.sort(key=lambda item: item.get("gameDate") or item.get("date") or "")
    for games in boxscores_by_team_espn_id.values():
        games.sort(key=lambda item: item.get("date") or item.get("gameDate") or "")
    return {
        "schedule_by_game_id": schedule_by_game_id,
        "boxscores_by_game_id": boxscores_by_game_id,
        "teams_by_espn_id": teams_by_espn_id,
        "espn_id_by_team_id": espn_id_by_team_id,
        "players_by_name": {normalize_name(player["name"]): player for player in canonical["players"]},
        "coach_by_team": {rating.team_id: rating for rating in coach_ratings(canonical)},
        "schedule_by_team_espn_id": dict(schedule_by_team_espn_id),
        "boxscores_by_team_espn_id": dict(boxscores_by_team_espn_id),
    }


def canonical_sim_cache(canonical: dict[str, Any]) -> dict[str, Any]:
    key = id(canonical)
    traits = canonical.get("traits", [])
    players = canonical.get("players", [])
    cache = _SIM_FEATURE_CACHE.get(key)
    if cache and cache.get("traits_id") == id(traits) and cache.get("players_id") == id(players):
        return cache
    traits_by_player: dict[str, dict[str, Any]] = defaultdict(dict)
    for trait in traits:
        traits_by_player[trait["player_id"]][trait["trait_key"]] = trait
    cache = {
        "traits_id": id(traits),
        "players_id": id(players),
        "traits_by_player": traits_by_player,
        "player_features": {},
    }
    _SIM_FEATURE_CACHE[key] = cache
    return cache


def player_feature_vector(canonical: dict[str, Any], player: dict[str, Any]) -> SimFeatureVector:
    cache = canonical_sim_cache(canonical)
    feature_key = (
        player.get("id"),
        player.get("rotation_priority"),
        float(player.get("minutes_projection") or 0),
        float(player.get("actual_points") or 0),
    )
    cached = cache["player_features"].get(feature_key)
    if cached:
        return cached
    traits = cache["traits_by_player"].get(player["id"], {})
    get = lambda key, default=50.0: float(traits.get(key, {}).get("value", default))
    synthetic_actual = player.get("rotation_priority") == "actual_boxscore_unmatched"
    defensive_mobility = weighted_average(
        [get("defensive_effort"), get("foot_speed_lateral_agility"), get("screen_navigation")],
        [0.42, 0.36, 0.22],
    )
    impact = player_impact_score(get)
    usage = synthetic_actual_usage(player) if synthetic_actual else projected_usage(player, get, impact)
    scoring_usage = synthetic_actual_usage(player) if synthetic_actual else projected_scoring_usage(player, get, impact)
    features = {
        "impact": impact,
        "usage": usage,
        "shot_creation": shot_creation_value(get),
        "scoring_usage": scoring_usage,
        "spacing": nonlinear_high(get("shooting_range"), 65),
        "rim_pressure": nonlinear_high(get("rim_pressure"), 64),
        "offensive_rebounding": nonlinear_high(get("offensive_rebounding"), 66),
        "defensive_events": defensive_mobility,
        "rim_deterrence": nonlinear_high(get("rim_deterrence"), 68),
        "passing": blend([get("passing_reads"), get("scheme_iq")]),
        "stamina": get("stamina_cardio"),
        "playoff_translation": get("playoff_translation"),
        "defensive_weak_link": nonlinear_low(defensive_mobility, 48),
    }
    rounded = {key: round(value, 3) for key, value in features.items()}
    vector = SimFeatureVector(
        id=stable_id("sim_feature", "player", player["id"]),
        entity_type="player",
        entity_id=player["id"],
        features=dict(rounded),
        confidence=0.62,
        source_ids=["src_trait_method_v1", "src_tracking_sources_2025_26"],
        notes="V0 sim feature vector from canonical hidden traits, roles, and public/raw stat proxies.",
    )
    cache["player_features"][feature_key] = vector
    return vector


def synthetic_actual_usage(player: dict[str, Any]) -> float:
    minutes = float(player.get("minutes_projection") or 0)
    actual_points = float(player.get("actual_points") or 0)
    return clamp(43 + minutes * 0.22 + actual_points * 0.55, 42, 72)


def player_impact_score(get: Any) -> float:
    skill_values = [
        get("shooting_range"),
        get("shot_versatility"),
        get("handle_pressure"),
        get("rim_pressure"),
        get("passing_reads"),
        get("defensive_effort"),
        get("rim_deterrence"),
        get("scheme_iq"),
        get("portability"),
    ]
    balanced_skill = blend(skill_values)
    elite_skill = weighted_top_average(skill_values, [1.0 for _ in skill_values], top_n=3)
    impact = balanced_skill * 0.48 + elite_skill * 0.34 + get("playoff_translation") * 0.18
    return clamp(impact, 1, 99)


def shot_creation_value(get: Any) -> float:
    shot_creation = get("shot_versatility")
    if shot_creation > 5:
        return shot_creation
    return blend([get("handle_pressure"), get("rim_pressure"), get("shooting_range")])


def projected_usage(player: dict[str, Any], get: Any, impact: float) -> float:
    minutes = projected_game_minutes(player)
    shot_creation = shot_creation_value(get)
    handle = get("handle_pressure")
    rim_pressure = get("rim_pressure")
    passing = get("passing_reads")
    shooting_range = get("shooting_range")
    value = (
        40
        + minutes * 0.85
        + (shot_creation - 50) * 0.35
        + max(0.0, handle - 55) * 0.12
        + max(0.0, rim_pressure - 55) * 0.12
        + max(0.0, passing - 55) * 0.08
        + max(0.0, impact - 60) * 0.16
        + max(0.0, shooting_range - 72) * 0.08
        - max(0.0, 48 - impact) * 0.18
        - max(0.0, 45 - passing) * 0.06
    )
    return clamp(value, 8, 92)


def projected_scoring_usage(player: dict[str, Any], get: Any, impact: float) -> float:
    minutes = projected_game_minutes(player)
    shot_creation = shot_creation_value(get)
    handle = get("handle_pressure")
    rim_pressure = get("rim_pressure")
    passing = get("passing_reads")
    shooting_range = get("shooting_range")
    release = get("release_speed")
    connector_discount = max(0.0, passing - 74) * max(0.0, 60 - shot_creation) * 0.006
    value = (
        37
        + minutes * 0.48
        + max(0.0, shot_creation - 45) * 0.26
        + max(0.0, handle - 55) * 0.18
        + max(0.0, rim_pressure - 52) * 0.16
        + max(0.0, shooting_range - 58) * 0.11
        + max(0.0, shooting_range - 84) * max(0.0, release - 84) * 0.010
        + max(0.0, impact - 72) * 0.12
        + max(0.0, passing - 82) * 0.13
        - max(0.0, 50 - shot_creation) * 0.16
        - connector_discount
    )
    return clamp(value, 12, 88)


def team_feature_vector(canonical: dict[str, Any], team: dict[str, Any]) -> SimFeatureVector:
    players = [player for player in canonical["players"] if player["team_id"] == team["id"]]
    player_features = {player["id"]: player_feature_vector(canonical, player).features for player in players}
    weights = {player["id"]: max(1.0, projected_game_minutes(player)) for player in players}
    features = {}
    for key in ["impact", "scoring_usage", "shot_creation", "spacing", "rim_pressure", "offensive_rebounding", "defensive_events", "rim_deterrence", "passing", "stamina", "playoff_translation", "defensive_weak_link"]:
        features[key] = weighted_average([player_features[player["id"]][key] for player in players], [weights[player["id"]] for player in players])
    features.update(age_context_features(players, [weights[player["id"]] for player in players]))
    features["depth"] = sum(1 for player in players if projected_game_minutes(player) >= 12)
    features["creation_burden"] = max([player_features[player["id"]]["usage"] for player in players] or [50])
    usage_values = [player_features[player["id"]]["usage"] for player in players]
    usage_weights = [weights[player["id"]] for player in players]
    features["top_creation"] = weighted_top_average(usage_values, usage_weights, top_n=3)
    features["star_power"] = weighted_top_average([player_star_power_score(player_features[player["id"]]) for player in players], usage_weights, top_n=3)
    features["primary_creator"] = max([primary_creator_score(player_features[player["id"]]) for player in players] or [50])
    features["defensive_anchor"] = max([defensive_anchor_score(player_features[player["id"]]) for player in players] or [50])
    features.update(offensive_feature_summary_from_values(features))
    features.update(defensive_feature_summary_from_values(features))
    return SimFeatureVector(
        id=stable_id("sim_feature", "team", team["id"]),
        entity_type="team",
        entity_id=team["id"],
        features={key: round(value, 3) for key, value in features.items()},
        confidence=0.58,
        source_ids=["src_trait_method_v1", "src_tracking_sources_2025_26"],
        notes="V0 team context vector from projected rotation-weighted player features.",
    )


def coach_ratings(canonical: dict[str, Any]) -> list[CoachRating]:
    ratings = []
    for team in canonical["teams"]:
        head = next((staff for staff in canonical["staff_profiles"] if staff["team_id"] == team["id"] and staff["role"] == "head_coach"), None)
        name = head.get("name") if head else "Unknown Coach"
        values = dict(COACH_DEFAULTS)
        values.update(COACH_REPUTATION_OVERRIDES.get(name, {}))
        ratings.append(
            CoachRating(
                id=stable_id("coach_rating", team["id"], name),
                team_id=team["id"],
                coach_name=name,
                ratings={key: round(float(value), 2) for key, value in values.items()},
                confidence=0.64 if name in COACH_REPUTATION_OVERRIDES else 0.42,
                source_ids=["src_coach_reputation_sources_2025_26"],
                notes="0-5 star v1 coach ratings from public reputation sources plus conservative defaults. Tunable after validation.",
            )
        )
    return ratings


def sim_game(root: str | Path, game_id: str, mode: str = "replay-real-minutes", seed: int = 1) -> SimGameResult:
    return sim_game_with_context(load_sim_context(root), game_id, mode=mode, seed=seed)


def sim_game_with_context(context: dict[str, Any], game_id: str, mode: str = "replay-real-minutes", seed: int = 1) -> SimGameResult:
    if mode not in SIM_MODES:
        raise ValueError(f"Unknown sim mode {mode!r}")
    canonical = context["canonical"]
    game = context.get("indices", {}).get("schedule_by_game_id", {}).get(str(game_id))
    if game is None:
        boxscore_game = context.get("indices", {}).get("boxscores_by_game_id", {}).get(str(game_id))
        if boxscore_game:
            game = {
                "externalGameId": boxscore_game["game_id"],
                "gameDate": boxscore_game["date"],
                "phase": boxscore_game.get("phase"),
                "round": boxscore_game.get("round"),
                "homeTeamId": boxscore_game.get("home_team_id"),
                "awayTeamId": boxscore_game.get("away_team_id"),
            }
    if game is None:
        raise ValueError(f"No scheduled game found for {game_id}")
    teams_by_espn_id = context.get("indices", {}).get("teams_by_espn_id") or espn_team_id_map(canonical)
    home_team = teams_by_espn_id[str(game["homeTeamId"])]
    away_team = teams_by_espn_id[str(game["awayTeamId"])]
    rng = random.Random(f"{seed}:{game_id}:{mode}")
    game_date = game.get("gameDate") or game.get("date")
    home_players = game_player_pool(context, game_id, home_team, mode, game_date=game_date)
    away_players = game_player_pool(context, game_id, away_team, mode, game_date=game_date)
    coach_by_team = context.get("indices", {}).get("coach_by_team") or {rating.team_id: rating for rating in coach_ratings(canonical)}
    if mode == "sandbox-sim":
        home_players = matchup_adjusted_player_pool(
            canonical,
            home_players,
            away_players,
            coach_by_team.get(home_team["id"]),
            game_id,
            seed,
        )
        away_players = matchup_adjusted_player_pool(
            canonical,
            away_players,
            home_players,
            coach_by_team.get(away_team["id"]),
            game_id,
            seed,
        )
    home_features = game_team_features(context, canonical, home_team, home_players, mode)
    away_features = game_team_features(context, canonical, away_team, away_players, mode)
    home_game_context = game_context_for_team(context, game, home_team)
    away_game_context = game_context_for_team(context, game, away_team)
    home_line, home_team_line = simulate_team_line(
        canonical,
        home_team,
        away_team,
        home_players,
        home_features,
        away_features,
        coach_by_team.get(home_team["id"]),
        coach_by_team.get(away_team["id"]),
        rng,
        is_home=True,
        rest_context=home_game_context,
        opp_rest_context=away_game_context,
    )
    away_line, away_team_line = simulate_team_line(
        canonical,
        away_team,
        home_team,
        away_players,
        away_features,
        home_features,
        coach_by_team.get(away_team["id"]),
        coach_by_team.get(home_team["id"]),
        rng,
        is_home=False,
        rest_context=away_game_context,
        opp_rest_context=home_game_context,
    )
    overtime_periods = resolve_overtime_if_tied(home_line, away_line, home_team_line, away_team_line, rng)
    possessions = round((home_team_line["possessions"] + away_team_line["possessions"]) / 2, 1)
    notes = "V0 deterministic sim result. Replay-real-minutes uses actual availability/minutes where available; sandbox-sim uses generated rotation minutes."
    if overtime_periods:
        notes = f"{notes} Overtime resolved over {overtime_periods} period(s)."
    return SimGameResult(
        id=stable_id("sim_game", game_id, mode, seed),
        game_id=str(game_id),
        mode=mode,
        seed=seed,
        home_team_id=home_team["id"],
        away_team_id=away_team["id"],
        home_score=int(home_team_line["points"]),
        away_score=int(away_team_line["points"]),
        possessions=possessions,
        player_lines=home_line + away_line,
        team_lines=[home_team_line, away_team_line],
        source_ids=["src_player_skill_input_2025_26", "src_trait_method_v1", *(["src_injury_model_config_v1"] if mode == "sandbox-sim" else [])],
        notes=notes,
    )


def game_player_pool(context: dict[str, Any], game_id: str, team: dict[str, Any], mode: str, game_date: str | None = None) -> list[dict[str, Any]]:
    cache = context.setdefault("sim_cache", {}).setdefault("player_pools", {})
    cache_key = (str(game_id), team["id"], mode, game_date)
    if cache_key in cache:
        return cache[cache_key]
    canonical = context["canonical"]
    players_by_name = context.get("indices", {}).get("players_by_name") or {normalize_name(player["name"]): player for player in canonical["players"]}
    if mode == "replay-real-minutes":
        actual = actual_players_for_game(context, game_id, team["abbrev"])
        if actual:
            pool = []
            for row in actual:
                player = players_by_name.get(normalize_name(row["player_name"] or row.get("name")))
                if player and not row.get("dnp") and float(row.get("minutes") or 0) > 0:
                    pool.append({"player": player, "minutes": float(row.get("minutes") or 0), "actual": row})
                elif not row.get("dnp") and float(row.get("minutes") or 0) > 0:
                    pool.append({"player": synthetic_actual_player(row, team), "minutes": float(row.get("minutes") or 0), "actual": row})
            if pool:
                cache[cache_key] = normalize_minutes(pool)
                return cache[cache_key]
    roster = [player for player in canonical["players"] if player.get("team_id") == team["id"] and projected_game_minutes(player) > 0]
    top = sorted(roster, key=projected_game_minutes, reverse=True)[:14]
    pool = [{"player": player, "minutes": projected_game_minutes(player), "actual": None} for player in top]
    if mode == "sandbox-sim":
        from .health import sandbox_health_adjusted_pool

        pool = sandbox_health_adjusted_pool(canonical, game_date, pool)
    cache[cache_key] = normalize_minutes(pool)
    return cache[cache_key]


def matchup_adjusted_player_pool(
    canonical: dict[str, Any],
    pool: list[dict[str, Any]],
    opponent_pool: list[dict[str, Any]],
    coach: CoachRating | None,
    game_id: str,
    seed: int,
) -> list[dict[str, Any]]:
    """Small coach-driven game-plan minutes nudges around the shared rotation."""
    if not pool or not opponent_pool or coach is None:
        return pool
    ratings = coach.ratings
    adjustment_skill = (
        (float(ratings.get("matchup_adjustments", 3.0)) - 3.0) * 0.55
        + (float(ratings.get("hands_on_control", 3.0)) - 3.0) * 0.22
    )
    if abs(adjustment_skill) < 0.05:
        return pool

    def weighted_opp_feature(key: str) -> float:
        total = sum(float(item.get("minutes") or 0.0) for item in opponent_pool) or 1.0
        return sum(
            player_feature_vector(canonical, item["player"]).features.get(key, 50.0) * float(item.get("minutes") or 0.0)
            for item in opponent_pool
        ) / total

    opp_creation = weighted_opp_feature("shot_creation")
    opp_spacing = weighted_opp_feature("spacing")
    opp_rim = weighted_opp_feature("rim_deterrence")
    opp_rebounding = weighted_opp_feature("offensive_rebounding")
    rng = random.Random(f"{seed}:{game_id}:{coach.team_id}:matchup_rotation")
    adjusted: list[dict[str, Any]] = []
    deltas: dict[str, float] = {}
    for item in pool:
        player = item["player"]
        features = player_feature_vector(canonical, player).features
        minutes = float(item.get("minutes") or 0.0)
        if minutes <= 0:
            adjusted.append(item)
            continue
        defense_score = (
            max(0.0, opp_creation - 58.0) * (features.get("defensive_events", 50.0) - 50.0) * 0.0024
            + max(0.0, opp_spacing - 60.0) * (features.get("defensive_weak_link", 50.0) - 50.0) * -0.0018
        )
        offense_score = max(0.0, opp_rim - 60.0) * (features.get("spacing", 50.0) - 50.0) * 0.0018
        glass_score = max(0.0, opp_rebounding - 58.0) * (
            features.get("offensive_rebounding", 50.0) + features.get("rim_deterrence", 50.0) - 100.0
        ) * 0.0012
        raw_delta = (defense_score + offense_score + glass_score + rng.uniform(-0.12, 0.12)) * adjustment_skill
        cap = 1.8 if minutes >= 18 else 1.2
        deltas[player["id"]] = clamp(raw_delta, -cap, cap)
        adjusted.append({**item})
    for item in adjusted:
        player_id = item["player"]["id"]
        current = float(item.get("minutes") or 0.0)
        item["minutes"] = clamp(current + deltas.get(player_id, 0.0), max(0.0, current - 2.0), min(42.0, current + 2.0))
    return normalize_minutes(adjusted)


def synthetic_actual_player(row: dict[str, Any], team: dict[str, Any]) -> dict[str, Any]:
    name = row.get("player_name") or row.get("name") or "Unknown Player"
    return {
        "id": stable_id("actual_player", team["id"], name),
        "name": name,
        "normalized_name": normalize_name(name),
        "team_id": team["id"],
        "position": "",
        "minutes_projection": float(row.get("minutes") or 0),
        "actual_points": float(row.get("points") or 0),
        "rotation_priority": "actual_boxscore_unmatched",
    }


def actual_players_for_game(context: dict[str, Any], game_id: str, team_abbrev: str) -> list[dict[str, Any]]:
    boxscore = context.get("indices", {}).get("boxscores_by_game_id", {}).get(str(game_id))
    if boxscore:
        return [player for player in boxscore["players"] if normalize_game_team_abbrev(player.get("team_abbrev")) == team_abbrev]
    minutes = context["real_minutes"].get(str(game_id), {}).get("players", [])
    return [{"player_name": row.get("name"), **row} for row in minutes if normalize_game_team_abbrev(row.get("team_abbr")) == team_abbrev]


def normalize_game_team_abbrev(abbrev: str | None) -> str | None:
    if abbrev is None:
        return None
    return {
        "WSH": "WAS",
        "UTAH": "UTA",
        "GS": "GSW",
        "SA": "SAS",
        "NY": "NYK",
        "NO": "NOP",
        "PHO": "PHX",
        "BRK": "BKN",
        "CHO": "CHA",
    }.get(abbrev, abbrev)


def normalize_minutes(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cap = 48.0
    raw_minutes = [max(0.0, float(item.get("minutes") or 0.0)) for item in pool]
    total = sum(raw_minutes)
    if total <= 0:
        return pool
    minutes = [value * 240.0 / total for value in raw_minutes]
    capped = {idx for idx, value in enumerate(minutes) if value >= cap}
    while capped:
        remaining_total = 240.0 - cap * len(capped)
        uncapped = [idx for idx in range(len(minutes)) if idx not in capped]
        if not uncapped:
            break
        uncapped_raw = sum(raw_minutes[idx] for idx in uncapped)
        if uncapped_raw <= 0:
            break
        changed = False
        for idx in uncapped:
            next_value = raw_minutes[idx] * remaining_total / uncapped_raw
            if next_value >= cap:
                capped.add(idx)
                changed = True
            minutes[idx] = min(cap, next_value)
        if not changed:
            break
    for idx in capped:
        minutes[idx] = cap
    return [{**item, "minutes": round(min(cap, max(0.0, minutes[idx])), 2)} for idx, item in enumerate(pool)]


def projected_game_minutes(player: dict[str, Any]) -> float:
    """Normalize mixed raw minute inputs into a single-game rotation estimate."""
    minutes = float(player.get("minutes_projection") or 0.0)
    if minutes > 80:
        minutes = minutes / 82.0
    return round(clamp(minutes, 0.0, 42.0), 3)


def game_team_features(context: dict[str, Any] | None, canonical: dict[str, Any], team: dict[str, Any], pool: list[dict[str, Any]], mode: str) -> dict[str, float]:
    cache_key = None
    if context is not None:
        pool_key = tuple(
            (
                item["player"]["id"],
                round(float(item.get("minutes") or 0), 3),
                round(float(item.get("health_fatigue") or 0), 3),
                round(float(item.get("health_rust") or 0), 3),
                item.get("health_status"),
            )
            for item in pool
        )
        cache_key = (team["id"], mode, pool_key)
        cache = context.setdefault("sim_cache", {}).setdefault("team_features", {})
        if cache_key in cache:
            return dict(cache[cache_key])
    if pool:
        features = lineup_feature_vector(canonical, pool)
    else:
        features = team_feature_vector(canonical, team).features
    features = apply_availability_dependency_adjustments(canonical, team, pool, features) if pool else features
    features = apply_manifesto_feature_adjustments(context, canonical, team, pool, features)
    if context is not None and cache_key is not None:
        context["sim_cache"]["team_features"][cache_key] = dict(features)
    return features


def apply_manifesto_feature_adjustments(context: dict[str, Any] | None, canonical: dict[str, Any], team: dict[str, Any], pool: list[dict[str, Any]], features: dict[str, float]) -> dict[str, float]:
    text = (context or {}).get("manifestos", {}).get(team["abbrev"], "")
    if not text:
        return features
    low = text.lower()
    adjusted = dict(features)
    notes: list[str] = []
    if any(phrase in low for phrase in ["lack shot creation", "lacked both the shot creation", "no go-to scoring", "bottom 10 offense", "bottom five offense", "missing that presence", "lead creator"]):
        adjusted["primary_creator"] = adjusted.get("primary_creator", 50) - 1.4
        adjusted["top_creation"] = adjusted.get("top_creation", 50) - 1.0
        adjusted["passing"] = adjusted.get("passing", 50) - 0.5
        notes.append("manifesto_shot_creation_drag")
    if any(phrase in low for phrase in ["lack a truly elite passer", "lack passing", "limited passer", "limited passers", "not an elite passer", "no great connective", "weakest part of his offense"]):
        adjusted["passing"] = adjusted.get("passing", 50) - 1.8
        adjusted["top_creation"] = adjusted.get("top_creation", 50) - 0.5
        notes.append("manifesto_passing_drag")
    if any(phrase in low for phrase in ["not a great three-point shooting", "lack floor spacing", "lack of floor spacing", "lack of a consistent outside shot", "lack a jumper", "can't really space", "can't space"]):
        adjusted["spacing"] = adjusted.get("spacing", 50) - 1.5
        notes.append("manifesto_spacing_drag")
    if any(phrase in low for phrase in ["number one defense", "second best defense", "top 10 defense", "suffocating defense", "suffocating defensive", "top tier defense"]):
        adjusted["defensive_events"] = adjusted.get("defensive_events", 50) + 1.0
        adjusted["rim_deterrence"] = adjusted.get("rim_deterrence", 50) + 0.8
        adjusted["defensive_anchor"] = adjusted.get("defensive_anchor", 50) + 1.2
        notes.append("manifesto_defensive_identity")
    if any(phrase in low for phrase in ["league's best offense", "best regular season offense", "best offense", "top three offense", "top 10 offense"]):
        adjusted["primary_creator"] = adjusted.get("primary_creator", 50) + 0.8
        adjusted["spacing"] = adjusted.get("spacing", 50) + 0.6
        notes.append("manifesto_offensive_upside")
    apply_manifesto_expectation_adjustments(low, adjusted, notes)
    for key in ["impact", "scoring_usage", "shot_creation", "spacing", "rim_pressure", "offensive_rebounding", "defensive_events", "rim_deterrence", "passing", "defensive_weak_link", "top_creation", "star_power", "primary_creator", "defensive_anchor"]:
        if key in adjusted:
            adjusted[key] = clamp(float(adjusted[key]), 1, 99)
    adjusted.update(offensive_feature_summary_from_values(adjusted))
    adjusted.update(defensive_feature_summary_from_values(adjusted))
    adjusted["manifesto_dependency_penalty"] = 0.0
    adjusted["manifesto_adjustment_count"] = len(notes)
    return {key: round(value, 3) for key, value in adjusted.items()}


def apply_availability_dependency_adjustments(canonical: dict[str, Any], team: dict[str, Any], pool: list[dict[str, Any]], features: dict[str, float]) -> dict[str, float]:
    adjusted = dict(features)
    rows = availability_dependency_rows(canonical, team, pool)
    if not rows:
        adjusted["availability_dependency_penalty"] = 0.0
        adjusted["availability_dependency_count"] = 0
        for key in ["creation_gap", "spacing_gap", "passing_gap", "anchor_gap", "defensive_event_gap"]:
            adjusted[f"availability_{key}"] = 0.0
        return adjusted
    total_penalty = 0.0
    gap_totals = {"creation_gap": 0.0, "spacing_gap": 0.0, "passing_gap": 0.0, "anchor_gap": 0.0, "defensive_event_gap": 0.0}
    for row in rows:
        penalty = row["penalty"]
        total_penalty += penalty
        for key in gap_totals:
            gap_totals[key] += float(row.get(key) or 0.0)
        adjusted["impact"] = adjusted.get("impact", 50) - penalty * 0.45
        adjusted["primary_creator"] = adjusted.get("primary_creator", 50) - penalty * 0.75 - row["creation_gap"] * 0.035
        adjusted["top_creation"] = adjusted.get("top_creation", 50) - penalty * 0.55 - row["creation_gap"] * 0.025
        adjusted["star_power"] = adjusted.get("star_power", 50) - penalty * 0.5
        adjusted["shot_creation"] = adjusted.get("shot_creation", 50) - penalty * 0.45 - row["creation_gap"] * 0.03
        adjusted["scoring_usage"] = adjusted.get("scoring_usage", 50) - penalty * 0.5 - row["creation_gap"] * 0.04
        adjusted["passing"] = adjusted.get("passing", 50) - row["passing_gap"] * 0.03
        adjusted["spacing"] = adjusted.get("spacing", 50) - row["spacing_gap"] * 0.025
        adjusted["defensive_anchor"] = adjusted.get("defensive_anchor", 50) - penalty * 0.55 - row["anchor_gap"] * 0.035
        adjusted["rim_deterrence"] = adjusted.get("rim_deterrence", 50) - row["anchor_gap"] * 0.025
        adjusted["defensive_events"] = adjusted.get("defensive_events", 50) - row["defensive_event_gap"] * 0.025
    for key in ["impact", "scoring_usage", "shot_creation", "spacing", "rim_pressure", "offensive_rebounding", "defensive_events", "rim_deterrence", "passing", "defensive_weak_link", "top_creation", "star_power", "primary_creator", "defensive_anchor"]:
        if key in adjusted:
            adjusted[key] = clamp(float(adjusted[key]), 1, 99)
    adjusted.update(offensive_feature_summary_from_values(adjusted))
    adjusted.update(defensive_feature_summary_from_values(adjusted))
    adjusted["availability_dependency_penalty"] = round(total_penalty, 3)
    adjusted["availability_dependency_count"] = len(rows)
    for key, value in gap_totals.items():
        adjusted[f"availability_{key}"] = round(value, 3)
    return {key: round(value, 3) for key, value in adjusted.items()}


def availability_dependency_rows(canonical: dict[str, Any], team: dict[str, Any], pool: list[dict[str, Any]]) -> list[dict[str, float]]:
    team_players = [
        player
        for player in canonical["players"]
        if player["team_id"] == team["id"] and projected_game_minutes(player) >= 18
    ]
    if not team_players:
        return []
    available_minutes = {normalize_name(item["player"]["name"]): float(item.get("minutes") or 0) for item in pool}
    available_features = [
        health_adjusted_player_features(player_feature_vector(canonical, item["player"]).features, item)
        for item in pool
        if float(item.get("minutes") or 0) >= 8
    ]
    rows = []
    for player in team_players:
        expected_minutes = projected_game_minutes(player)
        actual_minutes = available_minutes.get(normalize_name(player["name"]), 0.0)
        lost_share = clamp((expected_minutes - actual_minutes) / max(expected_minutes, 1.0), 0.0, 1.0)
        if lost_share < 0.45:
            continue
        player_features = player_feature_vector(canonical, player).features
        primary = primary_creator_score(player_features)
        anchor = defensive_anchor_score(player_features)
        dependency = max(
            player_features.get("impact", 50),
            primary,
            anchor,
            player_features.get("spacing", 50) if player_features.get("spacing", 50) >= 78 else 50,
            player_features.get("passing", 50) if player_features.get("passing", 50) >= 78 else 50,
        )
        if dependency < 65 and expected_minutes < 28:
            continue
        replacement = replacement_context_for_absence(player_features, available_features)
        creation_gap = max(0.0, primary - replacement["primary_creator"])
        anchor_gap = max(0.0, anchor - replacement["defensive_anchor"])
        spacing_gap = max(0.0, player_features.get("spacing", 50) - replacement["spacing"]) if player_features.get("spacing", 50) >= 78 else 0.0
        passing_gap = max(0.0, player_features.get("passing", 50) - replacement["passing"]) if player_features.get("passing", 50) >= 78 else 0.0
        event_gap = max(0.0, player_features.get("defensive_events", 50) - replacement["defensive_events"]) if player_features.get("defensive_events", 50) >= 70 else 0.0
        role_gap = max(creation_gap, anchor_gap, spacing_gap * 0.65, passing_gap * 0.6, event_gap * 0.55)
        penalty = lost_share * clamp((dependency - 60) * 0.035 + role_gap * 0.028 + expected_minutes * 0.012, 0.15, 4.6)
        rows.append(
            {
                "penalty": round(penalty, 3),
                "creation_gap": round(creation_gap * lost_share, 3),
                "anchor_gap": round(anchor_gap * lost_share, 3),
                "spacing_gap": round(spacing_gap * lost_share, 3),
                "passing_gap": round(passing_gap * lost_share, 3),
                "defensive_event_gap": round(event_gap * lost_share, 3),
            }
        )
    return rows


def replacement_context_for_absence(player_features: dict[str, float], available_features: list[dict[str, float]]) -> dict[str, float]:
    if not available_features:
        return {"primary_creator": 50.0, "defensive_anchor": 50.0, "spacing": 50.0, "passing": 50.0, "defensive_events": 50.0}
    return {
        "primary_creator": max(primary_creator_score(features) for features in available_features),
        "defensive_anchor": max(defensive_anchor_score(features) for features in available_features),
        "spacing": weighted_top_average([features.get("spacing", 50) for features in available_features], [1.0 for _ in available_features], top_n=3),
        "passing": max(features.get("passing", 50) for features in available_features),
        "defensive_events": weighted_top_average([features.get("defensive_events", 50) for features in available_features], [1.0 for _ in available_features], top_n=3),
    }


def apply_manifesto_expectation_adjustments(low: str, adjusted: dict[str, float], notes: list[str]) -> None:
    if any(phrase in low for phrase in ["improved upon their biggest weakness", "fix the offense", "added shooting", "added two high level three-point shooters", "much needed floor spacing", "much needed presence as a floor spacer"]):
        adjusted["spacing"] = adjusted.get("spacing", 50) + 1.8
        adjusted["passing"] = adjusted.get("passing", 50) + 0.7
        adjusted["top_creation"] = adjusted.get("top_creation", 50) + 0.7
        adjusted["primary_creator"] = adjusted.get("primary_creator", 50) + 0.6
        adjusted["impact"] = adjusted.get("impact", 50) + 0.4
        notes.append("manifesto_resolved_offensive_weakness")
    if any(phrase in low for phrase in ["best team in basketball", "clear favorites", "clear number one defense", "best defensive teams we've ever seen", "70 wins wouldn't be out of the question"]):
        adjusted["impact"] = adjusted.get("impact", 50) + 1.2
        adjusted["star_power"] = adjusted.get("star_power", 50) + 0.8
        adjusted["defensive_events"] = adjusted.get("defensive_events", 50) + 1.4
        adjusted["rim_deterrence"] = adjusted.get("rim_deterrence", 50) + 1.0
        adjusted["defensive_anchor"] = adjusted.get("defensive_anchor", 50) + 1.2
        adjusted["top_creation"] = adjusted.get("top_creation", 50) + 0.7
        notes.append("manifesto_elite_contender_context")
    if any(phrase in low for phrase in ["winning any less than 50", "pushing 60", "legitimate shot at a championship", "inner circle", "win 50 or more games"]):
        adjusted["impact"] = adjusted.get("impact", 50) + 0.8
        adjusted["star_power"] = adjusted.get("star_power", 50) + 0.6
        adjusted["top_creation"] = adjusted.get("top_creation", 50) + 0.5
        notes.append("manifesto_high_win_expectation")
    if any(phrase in low for phrase in ["clear tanking effort", "dead last", "one of the worst offensive and defensive teams", "shocked if they win more than 20", "only a couple of these guys are legitimate impact players right now"]):
        adjusted["impact"] = adjusted.get("impact", 50) - 2.8
        adjusted["star_power"] = adjusted.get("star_power", 50) - 2.2
        adjusted["primary_creator"] = adjusted.get("primary_creator", 50) - 1.8
        adjusted["top_creation"] = adjusted.get("top_creation", 50) - 1.8
        adjusted["passing"] = adjusted.get("passing", 50) - 0.8
        adjusted["defensive_events"] = adjusted.get("defensive_events", 50) - 1.2
        adjusted["rim_deterrence"] = adjusted.get("rim_deterrence", 50) - 1.0
        adjusted["defensive_anchor"] = adjusted.get("defensive_anchor", 50) - 1.0
        notes.append("manifesto_current_rebuild_drag")
    if any(phrase in low for phrase in ["old age", "extremely old", "prioritizing health", "health over anything else", "take somewhat of a backseat in the regular season"]):
        adjusted["impact"] = adjusted.get("impact", 50) - 1.6
        adjusted["star_power"] = adjusted.get("star_power", 50) - 1.4
        adjusted["top_creation"] = adjusted.get("top_creation", 50) - 1.0
        adjusted["defensive_events"] = adjusted.get("defensive_events", 50) - 1.1
        adjusted["defensive_anchor"] = adjusted.get("defensive_anchor", 50) - 0.8
        adjusted["stamina"] = adjusted.get("stamina", 50) - 2.8
        notes.append("manifesto_regular_season_health_drag")


def lineup_feature_vector(canonical: dict[str, Any], pool: list[dict[str, Any]]) -> dict[str, float]:
    player_features = {
        item["player"]["id"]: health_adjusted_player_features(player_feature_vector(canonical, item["player"]).features, item)
        for item in pool
    }
    weights = {item["player"]["id"]: max(1.0, float(item.get("minutes") or 0)) for item in pool}
    features = {}
    for key in ["impact", "scoring_usage", "shot_creation", "spacing", "rim_pressure", "offensive_rebounding", "defensive_events", "rim_deterrence", "passing", "stamina", "playoff_translation", "defensive_weak_link"]:
        features[key] = weighted_average([player_features[item["player"]["id"]][key] for item in pool], [weights[item["player"]["id"]] for item in pool])
    features.update(age_context_features([item["player"] for item in pool], [weights[item["player"]["id"]] for item in pool]))
    usage_values = [player_features[item["player"]["id"]]["usage"] for item in pool]
    usage_weights = [weights[item["player"]["id"]] for item in pool]
    features["depth"] = sum(1 for item in pool if float(item.get("minutes") or 0) >= 12)
    features["creation_burden"] = max(usage_values or [50])
    features["top_creation"] = weighted_top_average(usage_values, usage_weights, top_n=3)
    features["star_power"] = weighted_top_average([player_star_power_score(player_features[item["player"]["id"]]) for item in pool], usage_weights, top_n=3)
    features["primary_creator"] = max([primary_creator_score(player_features[item["player"]["id"]]) for item in pool] or [50])
    features["defensive_anchor"] = max([defensive_anchor_score(player_features[item["player"]["id"]]) for item in pool] or [50])
    features.update(offensive_feature_summary_from_values(features))
    features.update(defensive_feature_summary_from_values(features))
    return {key: round(value, 3) for key, value in features.items()}


def health_adjusted_player_features(features: dict[str, float], item: dict[str, Any]) -> dict[str, float]:
    fatigue = float(item.get("health_fatigue") or 0.0)
    rust = float(item.get("health_rust") or 0.0)
    if fatigue <= 0 and rust <= 0:
        return features
    fatigue_penalty = clamp(max(0.0, fatigue - 35.0) * 0.065, 0.0, 4.6)
    rust_penalty = clamp(rust * 0.08, 0.0, 4.0)
    penalty = fatigue_penalty + rust_penalty
    adjusted = dict(features)
    weights = {
        "impact": 1.0,
        "usage": 0.5,
        "scoring_usage": 0.7,
        "shot_creation": 0.75,
        "rim_pressure": 0.8,
        "defensive_events": 0.82,
        "rim_deterrence": 0.28,
        "passing": 0.32,
        "stamina": 1.15,
        "playoff_translation": 0.2,
        "defensive_weak_link": -0.62,
    }
    for key, weight in weights.items():
        if key not in adjusted:
            continue
        if weight >= 0:
            adjusted[key] = clamp(float(adjusted[key]) - penalty * weight, 1, 99)
        else:
            adjusted[key] = clamp(float(adjusted[key]) + penalty * abs(weight), 1, 99)
    return {key: round(value, 3) for key, value in adjusted.items()}


def age_context_features(players: list[dict[str, Any]], weights: list[float]) -> dict[str, float]:
    ages = [float(player.get("age") or 0.0) for player in players]
    known = [(age, weight) for age, weight in zip(ages, weights, strict=False) if age > 0]
    if not known:
        return {"average_age": 27.0, "old_core_share": 0.0, "very_old_core_share": 0.0}
    total_weight = sum(weight for _, weight in known)
    average_age = sum(age * weight for age, weight in known) / total_weight if total_weight else 27.0
    old_share = sum(weight for age, weight in known if age >= 34) / total_weight if total_weight else 0.0
    very_old_share = sum(weight for age, weight in known if age >= 37) / total_weight if total_weight else 0.0
    return {
        "average_age": round(average_age, 3),
        "old_core_share": round(old_share, 4),
        "very_old_core_share": round(very_old_share, 4),
    }


def offensive_feature_summary_from_values(features: dict[str, float]) -> dict[str, float]:
    creation = features.get("top_creation", features.get("creation_burden", 50))
    primary_creator = features.get("primary_creator", creation)
    spacing = features.get("spacing", 50)
    passing = features.get("passing", 50)
    rim_pressure = features.get("rim_pressure", 50)
    offensive_rebounding = features.get("offensive_rebounding", 50)
    return {
        "offense_creation": blend([creation, primary_creator, features.get("star_power", 50), passing]),
        "offense_spacing": spacing,
        "offense_pressure": blend([rim_pressure, creation]),
        "offense_possession_extension": offensive_rebounding,
        "offense_balance": blend([spacing, passing, rim_pressure]),
    }


def defensive_feature_summary_from_values(features: dict[str, float]) -> dict[str, float]:
    events = features.get("defensive_events", 50)
    rim = features.get("rim_deterrence", 50)
    anchor = features.get("defensive_anchor", blend([events, rim]))
    weak_link = features.get("defensive_weak_link", 50)
    return {
        "defense_activity": events,
        "defense_rim": rim,
        "defense_integrity": clamp(100 - weak_link, 1, 99),
        "defense_total": blend([events, rim, anchor, clamp(100 - weak_link, 1, 99)]),
    }


def simulate_team_line(
    canonical: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
    pool: list[dict[str, Any]],
    team_features: dict[str, float],
    opp_features: dict[str, float],
    coach: CoachRating | None,
    opp_coach: CoachRating | None,
    rng: random.Random,
    is_home: bool = False,
    rest_context: dict[str, Any] | None = None,
    opp_rest_context: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    coach_mod = scaled_coach_effect(coach, team_features)
    opp_coach_mod = scaled_coach_effect(opp_coach, opp_features)
    availability_mod = availability_gap_effect(team_features)
    opp_availability_mod = availability_gap_effect(opp_features)
    age_mod = age_fatigue_effect(team_features, rest_context)
    opp_age_mod = age_fatigue_effect(opp_features, opp_rest_context)
    shot_diet = team_shot_diet(team_features, opp_features, coach)
    home_mod = 1.9 if is_home else -0.4
    rest_mod = rest_effect(rest_context)
    game_env_mod = game_environment_effect(rest_context, opp_rest_context)
    matchup_total_mod = matchup_total_environment_effect(team_features, opp_features)
    creator_mod = creator_advantage(team_features, opp_features)
    spacing_mod = spacing_creation_interaction(team_features)
    possessions = clamp(
        99.5
        + (team_features["stamina"] - 50) * 0.05
        + (team_features["offensive_rebounding"] - 50) * 0.025
        + coach_mod["tempo"]
        + availability_mod["pace"]
        + rest_mod["pace"]
        + age_mod["pace"]
        + game_env_mod["pace"]
        + matchup_total_mod["pace"]
        - opp_coach_mod["tempo_control"] * 0.25
        + rng.gauss(0, 4.2),
        84,
        120,
    )
    off_rating = (
        114.0
        + lineup_quality_effect(team_features, opp_features)
        + unsupported_creation_effect(team_features)
        + (team_features["offense_creation"] - 50) * 0.16
        + (team_features["offense_spacing"] - 50) * 0.15
        + (team_features["offense_pressure"] - 50) * 0.08
        + (team_features["offense_possession_extension"] - 50) * 0.06
        + coach_mod["offense"]
        + availability_mod["offense"]
        + home_mod
        + rest_mod["offense"]
        + age_mod["offense"]
        + game_env_mod["offense"]
        + matchup_total_mod["offense"]
        + creator_mod
        + spacing_mod
        - (opp_features["defense_rim"] - 50) * 0.085
        - (opp_features["defense_total"] - 50) * 0.055
        - defensive_pressure_effect(team_features, opp_features)
        + opp_availability_mod["defense_leak"]
        + opp_age_mod["defense_leak"]
        - opp_coach_mod["defense"]
        - opponent_targeting_penalty(team_features, opp_features, opp_coach_mod)
        + shot_diet["shot_quality_delta"]
        + rng.gauss(0, 9.2)
    )
    points = max(70, round(possessions * off_rating / 100))
    player_lines = distribute_player_lines(canonical, team, pool, points, possessions, rng)
    team_line = {
        "team_id": team["id"],
        "team_abbrev": team["abbrev"],
        "points": points,
        "possessions": round(possessions, 1),
        "off_rating": round(off_rating, 2),
        "shot_diet": {key: round(value, 3) for key, value in shot_diet.items() if key != "shot_quality_delta"},
        "shot_quality_delta": round(shot_diet["shot_quality_delta"], 3),
        "feature_context": {
            "lineup_weighted": True,
            "home_court_delta": round(home_mod, 3),
            "availability_offense_delta": round(availability_mod["offense"], 3),
            "availability_pace_delta": round(availability_mod["pace"], 3),
            "opponent_availability_defense_leak_delta": round(opp_availability_mod["defense_leak"], 3),
            "rest_offense_delta": round(rest_mod["offense"], 3),
            "rest_pace_delta": round(rest_mod["pace"], 3),
            "rest_context": rest_context or {},
            "age_offense_delta": round(age_mod["offense"], 3),
            "age_pace_delta": round(age_mod["pace"], 3),
            "opponent_age_defense_leak_delta": round(opp_age_mod["defense_leak"], 3),
            "recent_scoring_offense_delta": round(game_env_mod["offense"], 3),
            "recent_scoring_pace_delta": round(game_env_mod["pace"], 3),
            "matchup_total_offense_delta": round(matchup_total_mod["offense"], 3),
            "matchup_total_pace_delta": round(matchup_total_mod["pace"], 3),
            "creator_delta": round(creator_mod, 3),
            "spacing_creation_delta": round(spacing_mod, 3),
            "lineup_quality_delta": round(lineup_quality_effect(team_features, opp_features), 3),
            "unsupported_creation_delta": round(unsupported_creation_effect(team_features), 3),
            "coach_offense_delta": round(coach_mod["offense"], 3),
            "opponent_coach_defense_delta": round(-opp_coach_mod["defense"], 3),
            "defensive_pressure_delta": round(-defensive_pressure_effect(team_features, opp_features), 3),
        },
        "rebounds": sum(line["rebounds"] for line in player_lines),
        "assists": sum(line["assists"] for line in player_lines),
        "turnovers": sum(line["turnovers"] for line in player_lines),
        "steals": sum(line["steals"] for line in player_lines),
        "blocks": sum(line["blocks"] for line in player_lines),
        "fgm": sum(line.get("fgm", 0) for line in player_lines),
        "fga": sum(line.get("fga", 0) for line in player_lines),
        "fg3m": sum(line.get("fg3m", 0) for line in player_lines),
        "fg3a": sum(line.get("fg3a", 0) for line in player_lines),
        "ftm": sum(line.get("ftm", 0) for line in player_lines),
        "fta": sum(line.get("fta", 0) for line in player_lines),
    }
    return player_lines, team_line


def distribute_player_lines(canonical: dict[str, Any], team: dict[str, Any], pool: list[dict[str, Any]], team_points: int, possessions: float, rng: random.Random) -> list[dict[str, Any]]:
    features = {
        item["player"]["id"]: health_adjusted_player_features(player_feature_vector(canonical, item["player"]).features, item)
        for item in pool
    }
    weights = [scoring_weight(item, features[item["player"]["id"]]) for item in pool]
    total_weight = sum(weights) or 1
    point_values = []
    for index, item in enumerate(pool):
        share = weights[index] / total_weight
        minutes = float(item.get("minutes") or 0.0)
        usage = float(features[item["player"]["id"]].get("scoring_usage") or features[item["player"]["id"]].get("usage") or 50)
        role_variance = 4.4 + min(7.8, minutes * 0.16) + max(0.0, usage - 72) * 0.055
        hot_cold_sigma = clamp(0.16 + max(0.0, usage - 60) * 0.0028 + minutes * 0.0018, 0.14, 0.34)
        hot_cold = rng.lognormvariate(-0.5 * hot_cold_sigma * hot_cold_sigma, hot_cold_sigma)
        point_values.append(max(0.0, team_points * share * hot_cold + rng.gauss(0, role_variance)))
    point_values = normalize_point_values(point_values, team_points)
    point_values = cap_and_redistribute_points(pool, features, point_values, team_points, weights, rng)
    lines = []
    for index, item in enumerate(pool):
        player = item["player"]
        points = point_values[index]
        feat = features[player["id"]]
        lines.append(
            {
                "player_id": player["id"],
                "player_name": player["name"],
                "team_id": team["id"],
                "team_abbrev": team["abbrev"],
                "minutes": round(item["minutes"], 2),
                "health_status": item.get("health_status", "actual_or_untracked"),
                "health_fatigue": round(float(item.get("health_fatigue") or 0), 2),
                "health_rust": round(float(item.get("health_rust") or 0), 2),
                "points": points,
                **shooting_line(points, feat, item["minutes"], rng),
                "rim_attempts": max(0, int(round(item["minutes"] * feat["rim_pressure"] / 1150 + rng.random()))),
                "rebounds": max(0, int(round(item["minutes"] * (0.105 + feat["offensive_rebounding"] / 500 + feat["rim_deterrence"] / 1800 + max(0.0, feat["rim_deterrence"] - 92) * 0.0018) + rng.gauss(0.45, 1.35)))),
                "assists": max(0, int(round(item["minutes"] * assist_rate_from_features(feat) + rng.gauss(0.2, 1.12)))),
                "turnovers": max(0, int(round(item["minutes"] * (0.015 + feat["usage"] / 2200) + rng.random() * 0.6))),
                "steals": max(0, int(round(item["minutes"] * feat["defensive_events"] / 2100 + rng.random() * 0.55))),
                "blocks": max(0, int(round(item["minutes"] * (feat["rim_deterrence"] / 2200 + max(0.0, feat["rim_deterrence"] - 88) * 0.0034) + rng.random() * 0.95))),
            }
        )
    return lines


def assist_rate_from_features(feat: dict[str, float]) -> float:
    passing = float(feat.get("passing") or 50.0)
    usage = float(feat.get("usage") or feat.get("scoring_usage") or 50.0)
    creation = float(feat.get("shot_creation") or usage)
    rate = 0.026 + passing / 900.0 + usage / 3300.0
    rate += max(0.0, passing - 74.0) * 0.0032
    rate += max(0.0, passing - 88.0) * 0.0042
    rate += max(0.0, creation - 80.0) * 0.0012
    if passing < 58 and usage < 62:
        rate -= 0.012
    return clamp(rate, 0.035, 0.31)


def shooting_line(points: int, feat: dict[str, float], minutes: float, rng: random.Random) -> dict[str, int]:
    spacing = float(feat.get("spacing") or 50)
    rim_pressure = float(feat.get("rim_pressure") or 50)
    creation = float(feat.get("shot_creation") or feat.get("usage") or 50)
    usage = float(feat.get("usage") or creation)
    ft_rate = clamp(0.13 + max(0.0, rim_pressure - 55) * 0.0028 + max(0.0, creation - 70) * 0.0015, 0.08, 0.34)
    fta = max(0, int(round(points * ft_rate + rng.random() * 1.8)))
    ft_pct = clamp(0.70 + max(0.0, spacing - 55) * 0.0022 + max(0.0, creation - 65) * 0.0012, 0.58, 0.92)
    ftm = min(fta, max(0, int(round(fta * ft_pct + rng.gauss(0, 0.7)))))
    volume_role = clamp(0.45 + max(0.0, usage - 55) * 0.018 + max(0.0, creation - 70) * 0.006, 0.35, 1.08)
    fg3a = max(0, int(round(minutes * (0.048 + spacing / 980 + max(0.0, creation - 70) / 2100 + max(0.0, spacing - 78) * 0.010 * volume_role + max(0.0, creation - 82) * 0.003) + rng.random() * 1.35)))
    fg3_pct = clamp(0.30 + max(0.0, spacing - 50) * 0.0017 + max(0.0, creation - 72) * 0.0009, 0.25, 0.45)
    fg3m = min(fg3a, max(0, int(round(fg3a * fg3_pct + rng.gauss(0, 0.55)))))
    two_points = max(0, points - ftm - fg3m * 3)
    fg2m = int(two_points // 2)
    if two_points % 2:
        ftm = min(fta, ftm + 1)
    fg_pct = clamp(0.45 + max(0.0, rim_pressure - 58) * 0.0017 + max(0.0, creation - 72) * 0.0008 - max(0.0, spacing - 82) * 0.0005, 0.38, 0.62)
    fgm = fg2m + fg3m
    fga = max(fgm, int(round(fgm / fg_pct + rng.random() * 1.4)))
    fg3a = max(fg3a, fg3m)
    fga = max(fga, fg3a)
    return {"fgm": fgm, "fga": fga, "fg3m": fg3m, "fg3a": fg3a, "ftm": ftm, "fta": fta}


def normalize_point_values(values: list[float], team_points: int) -> list[int]:
    if not values:
        return []
    raw_total = sum(values)
    if raw_total <= 0:
        output = [0 for _ in values]
    else:
        output = [max(0, int(round(value * team_points / raw_total))) for value in values]
    diff = int(team_points) - sum(output)
    while diff != 0 and output:
        if diff > 0:
            index = max(range(len(output)), key=lambda idx: values[idx])
            output[index] += 1
            diff -= 1
        else:
            candidates = [idx for idx, value in enumerate(output) if value > 0]
            if not candidates:
                break
            index = max(candidates, key=lambda idx: output[idx])
            output[index] -= 1
            diff += 1
    return output


def cap_and_redistribute_points(
    pool: list[dict[str, Any]],
    features: dict[str, dict[str, float]],
    points: list[int],
    team_points: int,
    weights: list[float],
    rng: random.Random,
) -> list[int]:
    if not points:
        return points
    caps = [
        plausible_point_cap(item, features[item["player"]["id"]])
        for item in pool
    ]
    output = [min(value, caps[idx]) for idx, value in enumerate(points)]
    surplus = int(team_points) - sum(output)
    while surplus > 0:
        candidates = [idx for idx, value in enumerate(output) if value < caps[idx]]
        if not candidates:
            candidates = list(range(len(output)))
        candidate_weights = [max(0.1, weights[idx]) * max(0.25, caps[idx] - output[idx] + 1) for idx in candidates]
        index = weighted_index(candidates, candidate_weights, rng)
        output[index] += 1
        surplus -= 1
    while surplus < 0:
        candidates = [idx for idx, value in enumerate(output) if value > 0]
        if not candidates:
            break
        index = max(candidates, key=lambda idx: output[idx] - caps[idx])
        output[index] -= 1
        surplus += 1
    output = enforce_elite_scoring_floors(pool, features, output)
    return output


def enforce_elite_scoring_floors(pool: list[dict[str, Any]], features: dict[str, dict[str, float]], points: list[int]) -> list[int]:
    output = list(points)
    for idx, item in sorted(enumerate(pool), key=lambda pair: elite_scoring_floor(pair[1], features[pair[1]["player"]["id"]]), reverse=True):
        feat = features[item["player"]["id"]]
        floor = elite_scoring_floor(item, feat)
        if floor <= 0 or output[idx] >= floor:
            continue
        needed = floor - output[idx]
        donors = sorted(
            [
                donor_idx
                for donor_idx, donor in enumerate(pool)
                if donor_idx != idx and output[donor_idx] > role_scoring_floor(donor, features[donor["player"]["id"]])
            ],
            key=lambda donor_idx: output[donor_idx] - role_scoring_floor(pool[donor_idx], features[pool[donor_idx]["player"]["id"]]),
            reverse=True,
        )
        for donor_idx in donors:
            if needed <= 0:
                break
            donor_floor = role_scoring_floor(pool[donor_idx], features[pool[donor_idx]["player"]["id"]])
            transferable = min(needed, max(0, output[donor_idx] - donor_floor))
            if transferable <= 0:
                continue
            output[donor_idx] -= transferable
            output[idx] += transferable
            needed -= transferable
    return output


def elite_scoring_floor(item: dict[str, Any], features: dict[str, float]) -> int:
    minutes = float(item.get("minutes") or 0.0)
    if minutes < 26:
        return 0
    scoring_usage = float(features.get("scoring_usage") or features.get("usage") or 50)
    shot_creation = float(features.get("shot_creation") or scoring_usage)
    spacing = float(features.get("spacing") or 50)
    rim_pressure = float(features.get("rim_pressure") or 50)
    impact = float(features.get("impact") or 50)
    passing = float(features.get("passing") or 50)
    if max(scoring_usage, shot_creation, impact) < 80 and not (impact >= 82 and passing >= 90):
        return 0
    position = str((item.get("player") or {}).get("position") or "").upper()
    ppm = (
        0.54
        + max(0.0, scoring_usage - 72) * 0.012
        + max(0.0, shot_creation - 78) * 0.006
        + max(0.0, spacing - 82) * 0.004
        + max(0.0, rim_pressure - 72) * 0.006
        + max(0.0, impact - 82) * 0.005
    )
    if ("C" in position or "PF" in position) and impact >= 82 and passing >= 90:
        ppm += 0.12 + max(0.0, passing - 90) * 0.006
    if ("PG" in position or "SG" in position) and spacing >= 88 and shot_creation >= 82:
        ppm += 0.08 + max(0.0, spacing - 90) * 0.003
    if rim_pressure >= 86 and shot_creation >= 84:
        ppm += 0.045
    return int(round(minutes * clamp(ppm, 0.0, 0.96)))


def role_scoring_floor(item: dict[str, Any], features: dict[str, float]) -> int:
    minutes = float(item.get("minutes") or 0.0)
    usage = float(features.get("scoring_usage") or features.get("usage") or 50)
    return int(round(minutes * clamp(0.16 + max(0.0, usage - 52) * 0.003, 0.12, 0.35)))


def weighted_index(candidates: list[int], weights: list[float], rng: random.Random) -> int:
    total = sum(max(0.0, weight) for weight in weights)
    if total <= 0:
        return candidates[0]
    mark = rng.random() * total
    running = 0.0
    for candidate, weight in zip(candidates, weights, strict=False):
        running += max(0.0, weight)
        if running >= mark:
            return candidate
    return candidates[-1]


def plausible_point_cap(item: dict[str, Any], features: dict[str, float]) -> int:
    minutes = max(1.0, float(item.get("minutes") or 0))
    scoring_usage = float(features.get("scoring_usage") or features.get("usage") or 50)
    ball_usage = float(features.get("usage") or scoring_usage)
    impact = float(features.get("impact") or 50)
    rim_pressure = float(features.get("rim_pressure") or 50)
    passing = float(features.get("passing") or 50)
    shot_creation = float(features.get("shot_creation") or scoring_usage)
    spacing = float(features.get("spacing") or 50)
    position = str((item.get("player") or {}).get("position") or "").upper()
    ppm = (
        0.60
        + max(0.0, scoring_usage - 60) * 0.010
        + max(0.0, ball_usage - 78) * 0.021
        + max(0.0, impact - 82) * 0.009
        + max(0.0, rim_pressure - 62) * 0.018
    )
    if ("C" in position or "PF" in position) and impact >= 78:
        ppm += max(0.0, passing - 85) * 0.008
    skill_ceiling = (
        0.58
        + max(0.0, scoring_usage - 55) * 0.010
        + max(0.0, shot_creation - 60) * 0.006
        + max(0.0, spacing - 60) * 0.003
        + max(0.0, rim_pressure - 75) * 0.006
        + max(0.0, impact - 78) * 0.004
        + max(0.0, ball_usage - 80) * 0.012
    )
    if shot_creation < 58 and spacing < 55:
        skill_ceiling = min(skill_ceiling, 0.78)
    ppm = min(ppm, skill_ceiling)
    star_cap_bonus = 0.0
    if impact >= 82 and (shot_creation >= 82 or passing >= 90):
        star_cap_bonus += 0.08
    if spacing >= 90 and shot_creation >= 82:
        star_cap_bonus += 0.05
    return max(4, int(round(minutes * clamp(ppm + star_cap_bonus, 0.45, 1.14))))


def resolve_overtime_if_tied(
    home_line: list[dict[str, Any]],
    away_line: list[dict[str, Any]],
    home_team_line: dict[str, Any],
    away_team_line: dict[str, Any],
    rng: random.Random,
) -> int:
    if int(home_team_line["points"]) != int(away_team_line["points"]):
        return 0
    periods = 1
    while int(home_team_line["points"]) == int(away_team_line["points"]) and periods <= 4:
        home_extra = max(4, int(round(rng.gauss(10.2, 3.0))))
        away_extra = max(4, int(round(rng.gauss(10.0, 3.0))))
        if home_extra == away_extra:
            if rng.random() >= 0.5:
                home_extra += 1 + int(rng.random() * 3)
            else:
                away_extra += 1 + int(rng.random() * 3)
        add_overtime_points(home_line, home_extra)
        add_overtime_points(away_line, away_extra)
        home_team_line["points"] = int(home_team_line["points"]) + home_extra
        away_team_line["points"] = int(away_team_line["points"]) + away_extra
        home_team_line["possessions"] = round(float(home_team_line.get("possessions") or 0) + 5.0, 1)
        away_team_line["possessions"] = round(float(away_team_line.get("possessions") or 0) + 5.0, 1)
        home_team_line["overtime_periods"] = periods
        away_team_line["overtime_periods"] = periods
        periods += 1
    return int(home_team_line.get("overtime_periods") or 0)


def add_overtime_points(lines: list[dict[str, Any]], extra_points: int) -> None:
    if not lines or extra_points <= 0:
        return
    weights = [max(1.0, float(line.get("points") or 0) + float(line.get("minutes") or 0) * 0.18) for line in lines]
    extras = normalize_point_values(weights, extra_points)
    for line, points in zip(lines, extras, strict=False):
        line["points"] = int(line.get("points") or 0) + points
        if points >= 3:
            line["fg3m"] = int(line.get("fg3m") or 0) + (1 if points >= 6 else 0)
            line["fg3a"] = int(line.get("fg3a") or 0) + (1 if points >= 6 else 0)
        made = max(1 if points else 0, points // 2)
        line["fgm"] = int(line.get("fgm") or 0) + made
        line["fga"] = int(line.get("fga") or 0) + made + (1 if points >= 5 else 0)


def scoring_weight(item: dict[str, Any], features: dict[str, float]) -> float:
    minutes = max(1.0, float(item.get("minutes") or 0))
    usage = features.get("scoring_usage", features.get("usage", 50))
    ball_usage = features.get("usage", usage)
    impact = features.get("impact", 50)
    shot_creation = features.get("shot_creation", usage)
    creation = features.get("passing", 50)
    spacing = features.get("spacing", 50)
    rim_pressure = features.get("rim_pressure", 50)
    self_creation = 1 + max(0.0, usage - 70) ** 1.13 * 0.019 + max(0.0, shot_creation - 64) * 0.017
    assisted_finishing = 1 + max(0.0, rim_pressure - 60) * 0.006
    spot_up_spacing = 1 + max(0.0, spacing - 70) * 0.0045
    connective_creation = 1 + max(0.0, creation - 60) * 0.003
    role_suppression = 1 - max(0.0, 52 - usage) * 0.01
    connector_discount = 1 - max(0.0, creation - 74) * max(0.0, 58 - shot_creation) * 0.0019
    low_creation_cap = 1 - max(0.0, 54 - shot_creation) * 0.006
    star_floor = 1 + max(0.0, usage - 78) * 0.014 + max(0.0, impact - 82) * 0.004
    minutes_role = clamp((minutes / 32.0) ** 0.8, 0.45, 1.08)
    on_ball_star = 1 + max(0.0, ball_usage - 78) * 0.024 + max(0.0, impact - 80) * 0.008 + max(0.0, rim_pressure - 62) * 0.009
    position = str((item.get("player") or {}).get("position") or "").upper()
    frontcourt_hub = 1.0
    if ("C" in position or "PF" in position) and impact >= 78:
        frontcourt_hub += max(0.0, creation - 88) * 0.019 + max(0.0, ball_usage - 76) * 0.007
    primary_guard_star = 1.0
    if ("PG" in position or "SG" in position) and ball_usage >= 80:
        primary_guard_star += max(0.0, ball_usage - 80) * 0.027 + max(0.0, rim_pressure - 60) * 0.017
    elite_hub = 1.0
    if ball_usage >= 72 and impact >= 76:
        elite_hub += max(0.0, creation - 85) * 0.020 + max(0.0, impact - 80) * 0.017 + max(0.0, ball_usage - 76) * 0.010
    return (
        minutes
        * max(0.32, usage / 62)
        * self_creation
        * assisted_finishing
        * spot_up_spacing
        * connective_creation
        * max(0.48, role_suppression)
        * max(0.66, connector_discount)
        * max(0.72, low_creation_cap)
        * star_floor
        * minutes_role
        * on_ball_star
        * elite_hub
        * frontcourt_hub
        * primary_guard_star
        * (1 + max(0.0, impact - 78) * 0.002)
    )


def validate(root: str | Path, through_date: str | None = None, playoffs: bool = False, seed: int = 1) -> ValidationReport:
    context = load_sim_context(root)
    games = []
    actual_scores = {
        game["game_id"]: game
        for game in context["boxscores"]
        if game.get("status") == "STATUS_FINAL" and (game.get("home_score") or 0) > 0 and (game.get("away_score") or 0) > 0
    }
    source_games = context["boxscores"] if playoffs else context["schedule"]
    for game in source_games:
        game_date = game.get("date") or game.get("gameDate")
        if through_date and game_date > through_date:
            continue
        if playoffs and game.get("phase") != "playoffs":
            continue
        game_id = str(game.get("game_id") or game.get("externalGameId"))
        if game_id not in context["real_minutes"] and game_id not in actual_scores:
            continue
        games.append(game)
    misses = []
    win_error = 0
    scored_games = 0
    for game in games:
        game_id = str(game.get("game_id") or game.get("externalGameId"))
        actual = actual_scores.get(game_id)
        if not actual:
            continue
        result = sim_game_with_context(context, game_id, mode="replay-real-minutes", seed=seed)
        scored_games += 1
        sim_home_win = result.home_score > result.away_score
        actual_home_win = actual["home_score"] > actual["away_score"]
        if sim_home_win != actual_home_win:
            win_error += 1
        margin_error = abs((result.home_score - result.away_score) - (actual["home_score"] - actual["away_score"]))
        misses.append({"game_id": result.game_id, "date": game.get("date") or game.get("gameDate"), "margin_error": margin_error, "sim": [result.away_score, result.home_score], "actual": [actual["away_score"], actual["home_score"]]})
    summary = {
        "available_games": len(games),
        "games_with_actual_scores": scored_games,
        "win_error_rate": round(win_error / scored_games, 3) if scored_games else None,
        "mean_margin_error": round(sum(item["margin_error"] for item in misses) / len(misses), 2) if misses else None,
        "mode_note": "Uses real minutes/availability when available; production is simulated.",
    }
    return ValidationReport(
        id=stable_id("validation", "replay-real-minutes", through_date or "all", seed),
        mode="replay-real-minutes",
        through_date=through_date,
        game_count=len(games),
        summary=summary,
        biggest_misses=sorted(misses, key=lambda item: item["margin_error"], reverse=True)[:20],
        source_ids=["src_espn_game_boxscores_2025_26", "src_trait_method_v1"],
    )


def validate_game_probabilities(root: str | Path, game_id: str, runs: int = 1000, seed: int = 1, mode: str = "replay-real-minutes") -> dict[str, Any]:
    context = load_sim_context(root)
    return validate_game_probabilities_with_context(context, game_id, runs=runs, seed=seed, mode=mode)


def validate_game_probabilities_with_context(context: dict[str, Any], game_id: str, runs: int = 1000, seed: int = 1, mode: str = "replay-real-minutes", include_player_stats: bool = True) -> dict[str, Any]:
    actual = actual_score_for_game(context, game_id)
    odds = context["odds"].get(str(game_id))
    results = [sim_game_with_context(context, game_id, mode=mode, seed=seed + run) for run in range(runs)]
    home_team_id = results[0].home_team_id
    away_team_id = results[0].away_team_id
    home_wins = [1 if result.home_score > result.away_score else 0 for result in results]
    home_margins = [result.home_score - result.away_score for result in results]
    totals = [result.home_score + result.away_score for result in results]
    player_stats = monte_carlo_player_stats(results) if include_player_stats else {}
    raw_home_probability = sum(home_wins) / runs
    beta_home_probability = beta_smoothed_win_probability(sum(home_wins), runs)
    margin_home_probability = margin_distribution_win_probability(home_margins)
    calibrated_home_probability = calibrated_win_probability(sum(home_wins), runs, home_margins)
    report = {
        "game_id": str(game_id),
        "mode": mode,
        "runs": runs,
        "seed": seed,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "sim": {
            "home_win_probability": round(calibrated_home_probability, 4),
            "raw_home_win_probability": round(raw_home_probability, 4),
            "beta_home_win_probability": round(beta_home_probability, 4),
            "margin_home_win_probability": round(margin_home_probability, 4),
            "probability_calibration": "normal_margin_beta_blend_v4_full_season_uncertainty",
            "spread_home_margin": distribution_summary(home_margins),
            "total_points": distribution_summary(totals),
            "player_stats": player_stats,
        },
        "actual": actual,
        "market": odds,
        "calibration": {
            **calibration_metrics(home_wins, home_margins, totals, actual, odds),
            "player_props": player_prop_calibration_metrics(results, odds),
        },
    }
    return report


def validate_season_probabilities(root: str | Path, through_date: str | None = None, runs: int = 1000, seed: int = 1, playoffs: bool = False, limit: int | None = None) -> dict[str, Any]:
    context = load_sim_context(root)
    games = validation_game_ids(context, through_date=through_date, playoffs=playoffs)
    if limit is not None:
        games = games[:limit]
    reports = [validate_game_probabilities_with_context(context, game_id, runs=runs, seed=seed, mode="replay-real-minutes") for game_id in games]
    summary = summarize_market_reports(reports)
    return {
        "mode": "replay-real-minutes",
        "runs_per_game": runs,
        "seed": seed,
        "through_date": through_date,
        "game_count": len(reports),
        "games_with_actuals": summary["games_with_actuals"],
        "games_with_market": summary["games_with_market"],
        "summary": summary,
        "market_disagreements": sorted(
            [report for report in reports if report["calibration"].get("market_vs_sim_home_prob_delta") is not None],
            key=lambda item: abs(item["calibration"]["market_vs_sim_home_prob_delta"]),
            reverse=True,
        )[:20],
        "game_reports": reports[:20],
    }


def calibrate_market(root: str | Path, through_date: str | None = None, holdout_start: str | None = None, runs: int = 1000, seed: int = 1, limit: int | None = None, playoffs: bool = False, scored_only: bool = False) -> dict[str, Any]:
    context = load_sim_context(root)
    game_ids = [game_id for game_id in validation_game_ids(context, through_date=through_date, playoffs=playoffs) if game_id in context["odds"]]
    if scored_only:
        game_ids = [game_id for game_id in game_ids if actual_score_for_game(context, game_id)]
    if limit is not None:
        game_ids = game_ids[:limit]
    reports = [validate_game_probabilities_with_context(context, game_id, runs=runs, seed=seed, mode="replay-real-minutes", include_player_stats=False) for game_id in game_ids]
    tuning_reports = []
    holdout_reports = []
    for report in reports:
        game_date = game_date_for_id(context, report["game_id"])
        if holdout_start and game_date and game_date >= holdout_start:
            holdout_reports.append(report)
        else:
            tuning_reports.append(report)
    return {
        "mode": "replay-real-minutes",
        "runs_per_game": runs,
        "seed": seed,
        "through_date": through_date,
        "holdout_start": holdout_start,
        "scored_only": scored_only,
        "game_count": len(reports),
        "summary": summarize_market_reports(reports),
        "tuning": market_bucket_report(tuning_reports),
        "holdout": market_bucket_report(holdout_reports),
        "edge_candidates": edge_candidates(reports),
        "top_recurring_miss_patterns": recurring_miss_patterns(reports),
        "notes": "Market lines are calibration benchmarks only. Edge candidates are diagnostics, not betting advice.",
    }


def market_bucket_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "game_count": len(reports),
        "summary": summarize_market_reports(reports),
        "top_market_disagreements": sorted(
            [report for report in reports if report["calibration"].get("market_vs_sim_home_prob_delta") is not None],
            key=lambda item: abs(item["calibration"]["market_vs_sim_home_prob_delta"]),
            reverse=True,
        )[:10],
    }


def summarize_market_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [report for report in reports if report["actual"]]
    with_market = [report for report in reports if report.get("market")]
    sim_briers = [report["calibration"].get("brier_score") for report in scored if report["calibration"].get("brier_score") is not None]
    sim_log_losses = [report["calibration"].get("log_loss") for report in scored if report["calibration"].get("log_loss") is not None]
    market_briers = [report["calibration"].get("market_brier_score") for report in scored if report["calibration"].get("market_brier_score") is not None]
    market_log_losses = [report["calibration"].get("market_log_loss") for report in scored if report["calibration"].get("market_log_loss") is not None]
    spread_errors = [report["calibration"].get("spread_error_vs_market") for report in reports if report["calibration"].get("spread_error_vs_market") is not None]
    total_errors = [report["calibration"].get("total_error_vs_market") for report in reports if report["calibration"].get("total_error_vs_market") is not None]
    return {
        "games_with_actuals": len(scored),
        "games_with_market": len(with_market),
        "mean_brier_score": mean_or_none(sim_briers, 4),
        "mean_log_loss": mean_or_none(sim_log_losses, 4),
        "mean_market_brier_score": mean_or_none(market_briers, 4),
        "mean_market_log_loss": mean_or_none(market_log_losses, 4),
        "sim_minus_market_brier": round(mean_or_none(sim_briers, 8) - mean_or_none(market_briers, 8), 4) if sim_briers and market_briers else None,
        "sim_minus_market_log_loss": round(mean_or_none(sim_log_losses, 8) - mean_or_none(market_log_losses, 8), 4) if sim_log_losses and market_log_losses else None,
        "mean_abs_spread_error_vs_market": mean_abs_or_none(spread_errors, 3),
        "mean_abs_total_error_vs_market": mean_abs_or_none(total_errors, 3),
        "probability_buckets": probability_calibration_buckets(scored),
    }


def explain_game_probability(root: str | Path, game_id: str, runs: int = 200, seed: int = 1, mode: str = "replay-real-minutes") -> dict[str, Any]:
    context = load_sim_context(root)
    report = validate_game_probabilities_with_context(context, game_id, runs=runs, seed=seed, mode=mode)
    game = scheduled_game_for_context(context, game_id)
    canonical = context["canonical"]
    by_espn = context.get("indices", {}).get("teams_by_espn_id") or espn_team_id_map(canonical)
    home_team = by_espn[str(game["homeTeamId"])]
    away_team = by_espn[str(game["awayTeamId"])]
    game_date = game.get("gameDate") or game.get("date")
    home_pool = game_player_pool(context, game_id, home_team, mode, game_date=game_date)
    away_pool = game_player_pool(context, game_id, away_team, mode, game_date=game_date)
    home_features = game_team_features(context, canonical, home_team, home_pool, mode)
    away_features = game_team_features(context, canonical, away_team, away_pool, mode)
    coach_by_team = context.get("indices", {}).get("coach_by_team") or {rating.team_id: rating for rating in coach_ratings(canonical)}
    return {
        "game_id": str(game_id),
        "mode": mode,
        "market": report["market"],
        "actual": report["actual"],
        "sim": {
            "home_win_probability": report["sim"]["home_win_probability"],
            "spread_home_margin": report["sim"]["spread_home_margin"],
            "total_points": report["sim"]["total_points"],
        },
        "calibration": report["calibration"],
        "market_vs_sim_vs_actual": market_sim_actual_summary(report),
        "teams": {
            "away": explain_team_context(context, away_team, away_pool, away_features, coach_by_team.get(away_team["id"])),
            "home": explain_team_context(context, home_team, home_pool, home_features, coach_by_team.get(home_team["id"])),
        },
        "feature_deltas_home_minus_away": {
            key: round(home_features.get(key, 0) - away_features.get(key, 0), 3)
            for key in ["impact", "scoring_usage", "shot_creation", "spacing", "rim_pressure", "offensive_rebounding", "defensive_events", "rim_deterrence", "passing", "creation_burden", "top_creation", "primary_creator", "star_power", "defensive_anchor", "depth"]
        },
        "offensive_feature_deltas_home_minus_away": {
            key: round(home_features.get(key, 0) - away_features.get(key, 0), 3)
            for key in ["offense_creation", "offense_spacing", "offense_pressure", "offense_possession_extension", "offense_balance"]
        },
        "defensive_feature_deltas_home_minus_away": {
            key: round(home_features.get(key, 0) - away_features.get(key, 0), 3)
            for key in ["defense_activity", "defense_rim", "defense_integrity", "defense_total"]
        },
        "diagnosis": diagnose_probability_report(report, home_features, away_features),
    }


def scheduled_game_for_context(context: dict[str, Any], game_id: str) -> dict[str, Any]:
    game = context.get("indices", {}).get("schedule_by_game_id", {}).get(str(game_id))
    if game:
        return game
    boxscore_game = context.get("indices", {}).get("boxscores_by_game_id", {}).get(str(game_id))
    if not boxscore_game:
        raise ValueError(f"No scheduled game found for {game_id}")
    return {
        "externalGameId": boxscore_game["game_id"],
        "gameDate": boxscore_game["date"],
        "phase": boxscore_game.get("phase"),
        "round": boxscore_game.get("round"),
        "homeTeamId": boxscore_game.get("home_team_id"),
        "awayTeamId": boxscore_game.get("away_team_id"),
    }


def explain_team_context(context: dict[str, Any], team: dict[str, Any], pool: list[dict[str, Any]], features: dict[str, float], coach: CoachRating | None) -> dict[str, Any]:
    profile = next((profile for profile in context["canonical"].get("team_profiles", []) if profile["team_id"] == team["id"]), None)
    return {
        "team_id": team["id"],
        "abbrev": team["abbrev"],
        "lineup_features": {key: round(features.get(key, 0), 3) for key in ["impact", "scoring_usage", "shot_creation", "spacing", "rim_pressure", "offensive_rebounding", "defensive_events", "rim_deterrence", "passing", "creation_burden", "top_creation", "primary_creator", "star_power", "defensive_anchor", "depth", "average_age", "old_core_share", "very_old_core_share"]},
        "offensive_features": {key: round(features.get(key, 0), 3) for key in ["offense_creation", "offense_spacing", "offense_pressure", "offense_possession_extension", "offense_balance"]},
        "defensive_features": {key: round(features.get(key, 0), 3) for key in ["defense_activity", "defense_rim", "defense_integrity", "defense_total"]},
        "manifesto_feature_adjustments": {
            "dependency_penalty": round(features.get("manifesto_dependency_penalty", 0), 3),
            "adjustment_count": int(features.get("manifesto_adjustment_count", 0)),
        },
        "availability_dependency": {
            "penalty": round(features.get("availability_dependency_penalty", 0), 3),
            "missing_core_count": int(features.get("availability_dependency_count", 0)),
            "creation_gap": round(features.get("availability_creation_gap", 0), 3),
            "spacing_gap": round(features.get("availability_spacing_gap", 0), 3),
            "passing_gap": round(features.get("availability_passing_gap", 0), 3),
            "anchor_gap": round(features.get("availability_anchor_gap", 0), 3),
            "defensive_event_gap": round(features.get("availability_defensive_event_gap", 0), 3),
        },
        "usage_star_load": usage_star_load_summary(context["canonical"], pool),
        "rotation": [
            {
                "player": item["player"]["name"],
                "minutes": round(float(item.get("minutes") or 0), 2),
                "health_status": item.get("health_status", "actual_or_untracked"),
                "fatigue": round(float(item.get("health_fatigue") or 0), 2),
                "rust": round(float(item.get("health_rust") or 0), 2),
            }
            for item in sorted(pool, key=lambda row: row.get("minutes") or 0, reverse=True)[:10]
        ],
        "coach": {
            "name": coach.coach_name if coach else None,
            "ratings": coach.ratings if coach else {},
            "effects": scaled_coach_effect(coach, features),
            "base_effects": coach_effect(coach),
        },
        "manifesto_context": manifesto_context(profile),
    }


def usage_star_load_summary(canonical: dict[str, Any], pool: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    total_weight = 0.0
    for item in pool:
        features = player_feature_vector(canonical, item["player"]).features
        weight = scoring_weight(item, features)
        total_weight += weight
        rows.append(
            {
                "player": item["player"]["name"],
                "minutes": round(float(item.get("minutes") or 0), 2),
                "usage": round(features.get("usage", 0), 2),
                "scoring_usage": round(features.get("scoring_usage", 0), 2),
                "shot_creation": round(features.get("shot_creation", 0), 2),
                "impact": round(features.get("impact", 0), 2),
                "spacing": round(features.get("spacing", 0), 2),
                "rim_pressure": round(features.get("rim_pressure", 0), 2),
                "scoring_weight": weight,
            }
        )
    rows.sort(key=lambda row: row["scoring_weight"], reverse=True)
    for row in rows:
        row["scoring_share_estimate"] = round(row["scoring_weight"] / total_weight, 4) if total_weight else 0
        row["scoring_weight"] = round(row["scoring_weight"], 3)
    top_three_share = sum(row["scoring_share_estimate"] for row in rows[:3])
    return {"top_three_scoring_share_estimate": round(top_three_share, 4), "top_options": rows[:6]}


def market_sim_actual_summary(report: dict[str, Any]) -> dict[str, Any]:
    market = report.get("market") or {}
    sim = report.get("sim") or {}
    actual = report.get("actual")
    calibration = report.get("calibration") or {}
    return {
        "sim_home_win_probability": sim.get("home_win_probability"),
        "market_home_win_probability": calibration.get("market_home_win_probability"),
        "actual_home_win": actual.get("home_win") if actual else None,
        "sim_spread_mean": (sim.get("spread_home_margin") or {}).get("mean"),
        "market_home_spread": (market.get("spread") or {}).get("home_line"),
        "actual_home_margin": actual.get("home_margin") if actual else None,
        "sim_total_mean": (sim.get("total_points") or {}).get("mean"),
        "market_total": (market.get("total") or {}).get("line"),
        "actual_total": actual.get("total") if actual else None,
        "sim_minus_market_log_loss": calibration.get("sim_minus_market_log_loss"),
        "sim_minus_market_brier": calibration.get("sim_minus_market_brier"),
    }


def manifesto_context(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not profile or not profile.get("confidence"):
        return None
    return {
        "identity": profile.get("identity"),
        "offensive_style": profile.get("offensive_style", [])[:5],
        "defensive_style": profile.get("defensive_style", [])[:5],
        "strengths": profile.get("strengths", [])[:3],
        "weaknesses": profile.get("weaknesses", [])[:3],
        "strategic_behavior": profile.get("strategic_behavior", [])[:5],
        "notes": profile.get("notes"),
    }


def diagnose_probability_report(report: dict[str, Any], home_features: dict[str, float], away_features: dict[str, float]) -> list[str]:
    notes = []
    calibration = report.get("calibration") or {}
    market = report.get("market") or {}
    total_error = calibration.get("total_error_vs_market")
    prob_delta = calibration.get("market_vs_sim_home_prob_delta")
    spread_error = calibration.get("spread_error_vs_market")
    if total_error is not None and total_error < -12:
        notes.append("Sim total is materially below market; inspect pace/offensive-rating baseline or lineup offensive efficiency.")
    if total_error is not None and total_error > 12:
        notes.append("Sim total is materially above market; inspect defensive effects, pace, or shot-quality inflation.")
    if prob_delta is not None and abs(prob_delta) > 0.18:
        side = "home" if prob_delta > 0 else "away"
        notes.append(f"Sim is much higher than market on the {side} side.")
    if spread_error is not None and abs(spread_error) > 6:
        notes.append("Spread mean is far from market; check lineup feature deltas and star-creation weighting.")
    if home_features.get("top_creation", 50) - away_features.get("top_creation", 50) > 10 and market.get("moneyline"):
        notes.append("Home top-creation advantage is large in the engine.")
    if away_features.get("top_creation", 50) - home_features.get("top_creation", 50) > 10 and market.get("moneyline"):
        notes.append("Away top-creation advantage is large in the engine.")
    home_unsupported = unsupported_creation_effect(home_features)
    away_unsupported = unsupported_creation_effect(away_features)
    if home_unsupported < -1.0 or away_unsupported < -1.0:
        notes.append("At least one lineup has high creation without enough spacing, passing, or impact support.")
    return notes


def validation_game_ids(context: dict[str, Any], through_date: str | None, playoffs: bool) -> list[str]:
    source_games = context["boxscores"] if playoffs else context["schedule"]
    ids = []
    for game in source_games:
        game_date = game.get("date") or game.get("gameDate")
        if through_date and game_date > through_date:
            continue
        if playoffs and game.get("phase") != "playoffs":
            continue
        game_id = str(game.get("game_id") or game.get("externalGameId"))
        if game_id in context["real_minutes"] or actual_score_for_game(context, game_id):
            ids.append(game_id)
    return ids


def actual_score_for_game(context: dict[str, Any], game_id: str) -> dict[str, Any] | None:
    game = context.get("indices", {}).get("boxscores_by_game_id", {}).get(str(game_id))
    if not game or game.get("status") != "STATUS_FINAL" or not game.get("home_score") or not game.get("away_score"):
        return None
    return {
        "home_score": game["home_score"],
        "away_score": game["away_score"],
        "home_margin": game["home_score"] - game["away_score"],
        "total": game["home_score"] + game["away_score"],
        "home_win": game["home_score"] > game["away_score"],
    }


def calibration_metrics(home_wins: list[int], home_margins: list[int], totals: list[int], actual: dict[str, Any] | None, odds: dict[str, Any] | None) -> dict[str, Any]:
    runs = len(home_wins)
    home_prob = calibrated_win_probability(sum(home_wins), runs, home_margins)
    spread_mean = sum(home_margins) / runs
    total_mean = sum(totals) / runs
    metrics: dict[str, Any] = {}
    if actual:
        outcome = 1 if actual["home_win"] else 0
        metrics["brier_score"] = round((home_prob - outcome) ** 2, 5)
        metrics["log_loss"] = round(-(outcome * math.log(clamp(home_prob, 1e-6, 1 - 1e-6)) + (1 - outcome) * math.log(clamp(1 - home_prob, 1e-6, 1 - 1e-6))), 5)
        metrics["actual_margin_percentile"] = percentile_rank(home_margins, actual["home_margin"])
        metrics["actual_total_percentile"] = percentile_rank(totals, actual["total"])
    if odds:
        market_home_prob = odds.get("moneyline", {}).get("home_implied_no_vig")
        if market_home_prob is not None:
            metrics["market_home_win_probability"] = market_home_prob
            metrics["market_vs_sim_home_prob_delta"] = round(home_prob - market_home_prob, 4)
            if actual:
                outcome = 1 if actual["home_win"] else 0
                metrics["market_brier_score"] = round((market_home_prob - outcome) ** 2, 5)
                metrics["market_log_loss"] = round(-(outcome * math.log(clamp(market_home_prob, 1e-6, 1 - 1e-6)) + (1 - outcome) * math.log(clamp(1 - market_home_prob, 1e-6, 1 - 1e-6))), 5)
                metrics["sim_minus_market_brier"] = round(metrics["brier_score"] - metrics["market_brier_score"], 5) if "brier_score" in metrics else None
                metrics["sim_minus_market_log_loss"] = round(metrics["log_loss"] - metrics["market_log_loss"], 5) if "log_loss" in metrics else None
        home_spread = odds.get("spread", {}).get("home_line")
        if home_spread is not None:
            metrics["spread_error_vs_market"] = round(spread_mean + float(home_spread), 3)
        market_total = odds.get("total", {}).get("line")
        if market_total is not None:
            metrics["total_error_vs_market"] = round(total_mean - float(market_total), 3)
    return metrics


def calibrated_win_probability(home_win_count: int, runs: int, home_margins: list[int] | None = None, alpha: float | None = None) -> float:
    alpha = PROBABILITY_BETA_ALPHA if alpha is None else alpha
    beta_prob = beta_smoothed_win_probability(home_win_count, runs, alpha=alpha)
    if not home_margins:
        return beta_prob
    margin_prob = margin_distribution_win_probability(home_margins)
    margin_weight = clamp(PROBABILITY_MARGIN_WEIGHT_BASE + min(runs, 80) * PROBABILITY_MARGIN_WEIGHT_PER_RUN, 0.58, 0.94)
    return clamp(margin_prob * margin_weight + beta_prob * (1 - margin_weight), 0.025, 0.975)


def beta_smoothed_win_probability(home_win_count: int, runs: int, alpha: float = 6.0) -> float:
    if runs <= 0:
        return 0.5
    return (home_win_count + alpha) / (runs + alpha * 2)


def margin_distribution_win_probability(home_margins: list[int], min_std: float | None = None) -> float:
    if not home_margins:
        return 0.5
    min_std = MARGIN_DISTRIBUTION_MIN_STD if min_std is None else min_std
    mean_margin = sum(home_margins) / len(home_margins)
    spread_std = max(min_std, statistics.pstdev(home_margins) if len(home_margins) > 1 else min_std)
    z = mean_margin / spread_std
    return normal_cdf(z)


def normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def monte_carlo_player_stats(results: list[SimGameResult]) -> dict[str, dict[str, Any]]:
    by_player: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    names = {}
    for result in results:
        for line in result.player_lines:
            player_id = line["player_id"]
            names[player_id] = line["player_name"]
            for key in ["points", "rebounds", "assists", "turnovers", "steals", "blocks", "fg3m"]:
                by_player[player_id][key].append(float(line.get(key, 0)))
            by_player[player_id]["pra"].append(float(line.get("points", 0) + line.get("rebounds", 0) + line.get("assists", 0)))
    summaries = {}
    for player_id, stats in by_player.items():
        summaries[player_id] = {"player_name": names[player_id]}
        for key, values in stats.items():
            summaries[player_id][key] = distribution_summary(values)
    return summaries


def player_prop_calibration_metrics(results: list[SimGameResult], odds: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not odds:
        return []
    props = odds.get("player_props") or []
    if not props:
        return []
    lines_by_player: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    names_by_player: dict[str, str] = {}
    for result in results:
        for line in result.player_lines:
            player_key = normalize_name(line["player_name"])
            names_by_player[player_key] = line["player_name"]
            lines_by_player[player_key]["points"].append(float(line.get("points", 0)))
            lines_by_player[player_key]["rebounds"].append(float(line.get("rebounds", 0)))
            lines_by_player[player_key]["assists"].append(float(line.get("assists", 0)))
            lines_by_player[player_key]["threes"].append(float(line.get("fg3m", 0)))
            lines_by_player[player_key]["steals"].append(float(line.get("steals", 0)))
            lines_by_player[player_key]["blocks"].append(float(line.get("blocks", 0)))
            lines_by_player[player_key]["turnovers"].append(float(line.get("turnovers", 0)))
            lines_by_player[player_key]["pra"].append(float(line.get("points", 0) + line.get("rebounds", 0) + line.get("assists", 0)))
    reports = []
    for prop in props:
        player_key = normalize_name(prop.get("player_name", ""))
        market = normalize_prop_market(prop.get("market"))
        matched_key = match_prop_player_key(player_key, lines_by_player)
        values = lines_by_player.get(matched_key or player_key, {}).get(market)
        line_value = prop.get("line")
        if not values or line_value is None:
            reports.append({"player_name": prop.get("player_name"), "market": prop.get("market"), "status": "player_or_market_not_in_sim_lines"})
            continue
        line_float = float(line_value)
        over_probability = sum(1 for value in values if value > line_float) / len(values)
        under_probability = sum(1 for value in values if value < line_float) / len(values)
        report = {
            "player_name": names_by_player.get(matched_key or player_key, prop.get("player_name")),
            "market_player_name": prop.get("player_name"),
            "market": market,
            "line": line_float,
            "sim_over_probability": round(over_probability, 4),
            "sim_under_probability": round(under_probability, 4),
            "sim_stat": distribution_summary(values),
        }
        over_odds = prop.get("over_american")
        under_odds = prop.get("under_american")
        if over_odds is not None and under_odds is not None:
            over_raw = american_to_implied_probability(float(over_odds))
            under_raw = american_to_implied_probability(float(under_odds))
            no_vig = no_vig_probabilities(over_raw, under_raw)
            report["market_over_probability"] = no_vig["home"]
            report["market_vs_sim_over_prob_delta"] = round(over_probability - no_vig["home"], 4)
        reports.append(report)
    return reports


def match_prop_player_key(player_key: str, lines_by_player: dict[str, Any]) -> str | None:
    if player_key in lines_by_player:
        return player_key
    compact = player_key.replace(" jr", "").replace(" iii", "").replace(" ii", "").strip()
    for candidate in lines_by_player:
        candidate_compact = candidate.replace(" jr", "").replace(" iii", "").replace(" ii", "").strip()
        if compact == candidate_compact or compact in candidate_compact or candidate_compact in compact:
            return candidate
    return None


def normalize_prop_market(market: Any) -> str:
    key = str(market or "").strip().lower().replace("_", " ")
    aliases = {
        "3pm": "threes",
        "three pointers made": "threes",
        "threes made": "threes",
        "pts": "points",
        "reb": "rebounds",
        "ast": "assists",
        "stl": "steals",
        "blk": "blocks",
        "to": "turnovers",
        "pra": "pra",
    }
    return aliases.get(key, key.replace(" ", "_") if key == "turnovers" else key)


def distribution_summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "mean": round(sum(values) / len(values), 3) if values else 0,
        "std": round(statistics.pstdev(values), 3) if len(values) > 1 else 0,
        "p10": percentile_value(ordered, 0.1),
        "p50": percentile_value(ordered, 0.5),
        "p90": percentile_value(ordered, 0.9),
    }


def percentile_value(ordered: list[float], pct: float) -> float:
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return round(ordered[index], 3)


def percentile_rank(values: list[float], actual: float) -> float:
    if not values:
        return 0.0
    return round(sum(1 for value in values if value <= actual) / len(values), 4)


def american_to_implied_probability(odds: float) -> float:
    if odds < 0:
        return round(abs(odds) / (abs(odds) + 100), 6)
    return round(100 / (odds + 100), 6)


def no_vig_probabilities(home_raw: float, away_raw: float) -> dict[str, float]:
    total = home_raw + away_raw
    if total <= 0:
        return {"home": 0.5, "away": 0.5}
    return {"home": round(home_raw / total, 6), "away": round(away_raw / total, 6)}


def game_date_for_id(context: dict[str, Any], game_id: str) -> str | None:
    game = next((item for item in context["schedule"] if str(item.get("externalGameId")) == str(game_id)), None)
    if game:
        return game.get("gameDate")
    game = next((item for item in context["boxscores"] if str(item.get("game_id")) == str(game_id)), None)
    return game.get("date") if game else None


def edge_candidates(reports: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    candidates = []
    for report in reports:
        delta = report["calibration"].get("market_vs_sim_home_prob_delta")
        if delta is None or abs(delta) < 0.12:
            continue
        market = report.get("market") or {}
        candidates.append(
            {
                "game_id": report["game_id"],
                "away_team_abbrev": market.get("away_team_abbrev"),
                "home_team_abbrev": market.get("home_team_abbrev"),
                "diagnostic_only": True,
                "sim_home_win_probability": report["sim"]["home_win_probability"],
                "market_home_win_probability": report["calibration"].get("market_home_win_probability"),
                "probability_delta": delta,
                "spread_error_vs_market": report["calibration"].get("spread_error_vs_market"),
                "total_error_vs_market": report["calibration"].get("total_error_vs_market"),
            }
        )
    return sorted(candidates, key=lambda item: abs(item["probability_delta"]), reverse=True)[:limit]


def recurring_miss_patterns(reports: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    team_counts: Counter[str] = Counter()
    player_prop_counts: Counter[str] = Counter()
    pattern_counts: Counter[str] = Counter()
    for report in reports:
        calibration = report.get("calibration") or {}
        market = report.get("market") or {}
        delta = calibration.get("market_vs_sim_home_prob_delta")
        if delta is not None and abs(delta) > 0.18:
            if delta > 0:
                team_counts[f"sim_high_on_home:{market.get('home_team_abbrev')}"] += 1
            else:
                team_counts[f"sim_high_on_away:{market.get('away_team_abbrev')}"] += 1
        total_error = calibration.get("total_error_vs_market")
        if total_error is not None:
            if total_error < -10:
                pattern_counts["sim_total_low"] += 1
            elif total_error > 10:
                pattern_counts["sim_total_high"] += 1
        for prop in calibration.get("player_props") or []:
            if prop.get("status"):
                continue
            delta_over = prop.get("market_vs_sim_over_prob_delta")
            if delta_over is not None and abs(delta_over) > 0.25:
                player_prop_counts[prop.get("player_name", "unknown")] += 1
    rows = [{"kind": "team_probability", "key": key, "count": count} for key, count in team_counts.most_common(limit)]
    rows += [{"kind": "scoring_total", "key": key, "count": count} for key, count in pattern_counts.most_common(limit)]
    rows += [{"kind": "player_prop", "key": key, "count": count} for key, count in player_prop_counts.most_common(limit)]
    return sorted(rows, key=lambda item: item["count"], reverse=True)[:limit]


def probability_calibration_buckets(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = [
        (0.0, 0.2, "heavy_away_favorite"),
        (0.2, 0.4, "away_favorite"),
        (0.4, 0.6, "coin_flip"),
        (0.6, 0.8, "home_favorite"),
        (0.8, 1.0, "heavy_home_favorite"),
    ]
    rows = []
    for low, high, label in buckets:
        bucket_reports = [
            report
            for report in reports
            if report.get("actual")
            and report["calibration"].get("market_home_win_probability") is not None
            and low <= float(report["calibration"]["market_home_win_probability"]) < (high if high < 1.0 else 1.001)
        ]
        if not bucket_reports:
            continue
        sim_probs = [float(report["sim"]["home_win_probability"]) for report in bucket_reports]
        market_probs = [float(report["calibration"]["market_home_win_probability"]) for report in bucket_reports]
        outcomes = [1.0 if report["actual"]["home_win"] else 0.0 for report in bucket_reports]
        rows.append(
            {
                "bucket": label,
                "count": len(bucket_reports),
                "mean_sim_home_probability": round(sum(sim_probs) / len(sim_probs), 4),
                "mean_market_home_probability": round(sum(market_probs) / len(market_probs), 4),
                "actual_home_win_rate": round(sum(outcomes) / len(outcomes), 4),
                "mean_sim_minus_market": round(sum(sim - market for sim, market in zip(sim_probs, market_probs, strict=False)) / len(sim_probs), 4),
            }
        )
    return rows


def game_context_for_team(context: dict[str, Any], game: dict[str, Any], team: dict[str, Any]) -> dict[str, Any]:
    game_id = str(game.get("externalGameId") or game.get("game_id"))
    cache = context.setdefault("sim_cache", {}).setdefault("game_contexts", {})
    cache_key = (game_id, team["id"])
    if cache_key in cache:
        return dict(cache[cache_key])
    rest = rest_context_for_team(context, game, team)
    value = {**rest, "recent_scoring": recent_scoring_context_for_team(context, game, team)}
    cache[cache_key] = dict(value)
    return value


def rest_context_for_team(context: dict[str, Any], game: dict[str, Any], team: dict[str, Any]) -> dict[str, Any]:
    game_date = game.get("gameDate") or game.get("date")
    if not game_date:
        return {"days_since_previous_game": None, "rest_days": None}
    current = date_from_iso(game_date)
    team_espn_id = context.get("indices", {}).get("espn_id_by_team_id", {}).get(team["id"])
    if not current or not team_espn_id:
        return {"days_since_previous_game": None, "rest_days": None}
    previous_dates = []
    for scheduled in context.get("indices", {}).get("schedule_by_team_espn_id", {}).get(str(team_espn_id), context["schedule"]):
        scheduled_id = str(scheduled.get("externalGameId"))
        if scheduled_id == str(game.get("externalGameId") or game.get("game_id")):
            continue
        scheduled_date = date_from_iso(scheduled.get("gameDate"))
        if scheduled_date and scheduled_date < current:
            previous_dates.append(scheduled_date)
    if not previous_dates:
        return {"days_since_previous_game": None, "rest_days": None, "rest_label": "season_opener_or_unknown"}
    days_since = (current - max(previous_dates)).days
    rest_days = max(0, days_since - 1)
    label = "back_to_back" if rest_days == 0 else "one_day_rest" if rest_days == 1 else "extended_rest" if rest_days >= 3 else "normal_rest"
    return {"days_since_previous_game": days_since, "rest_days": rest_days, "rest_label": label}


def rest_effect(rest_context: dict[str, Any] | None) -> dict[str, float]:
    if not rest_context or rest_context.get("rest_days") is None:
        return {"offense": 0.0, "pace": 0.0}
    rest_days = int(rest_context["rest_days"])
    if rest_days == 0:
        return {"offense": -1.35, "pace": -0.85}
    if rest_days == 1:
        return {"offense": 0.0, "pace": 0.0}
    if rest_days == 2:
        return {"offense": 0.35, "pace": 0.1}
    if rest_days == 3:
        return {"offense": 0.55, "pace": 0.05}
    return {"offense": 0.25, "pace": -0.05}


def availability_gap_effect(team_features: dict[str, float]) -> dict[str, float]:
    penalty = float(team_features.get("availability_dependency_penalty") or 0.0)
    creation_gap = float(team_features.get("availability_creation_gap") or 0.0)
    spacing_gap = float(team_features.get("availability_spacing_gap") or 0.0)
    passing_gap = float(team_features.get("availability_passing_gap") or 0.0)
    anchor_gap = float(team_features.get("availability_anchor_gap") or 0.0)
    event_gap = float(team_features.get("availability_defensive_event_gap") or 0.0)
    if penalty <= 0 and creation_gap <= 0 and anchor_gap <= 0 and event_gap <= 0:
        return {"offense": 0.0, "pace": 0.0, "defense_leak": 0.0}
    offense = -clamp(penalty * 0.18 + creation_gap * 0.09 + spacing_gap * 0.018 + passing_gap * 0.025, 0.0, 4.8)
    pace = -clamp(penalty * 0.06 + creation_gap * 0.012, 0.0, 1.4)
    defense_leak = clamp(penalty * 0.06 + anchor_gap * 0.04 + event_gap * 0.025, 0.0, 3.2)
    return {"offense": round(offense, 4), "pace": round(pace, 4), "defense_leak": round(defense_leak, 4)}


def age_fatigue_effect(team_features: dict[str, float], rest_context: dict[str, Any] | None) -> dict[str, float]:
    old_share = float(team_features.get("old_core_share") or 0.0)
    very_old_share = float(team_features.get("very_old_core_share") or 0.0)
    average_age = float(team_features.get("average_age") or 27.0)
    if old_share <= 0 and average_age < 31:
        return {"offense": 0.0, "pace": 0.0, "defense_leak": 0.0}
    rest_days = (rest_context or {}).get("rest_days")
    rest_multiplier = 1.0
    if rest_days == 0:
        rest_multiplier = 1.65
    elif rest_days == 1:
        rest_multiplier = 1.15
    elif rest_days is not None and rest_days >= 3:
        rest_multiplier = 0.78
    age_pressure = old_share * 2.35 + very_old_share * 3.05 + max(0.0, average_age - 30.5) * 0.18
    return {
        "offense": round(-clamp(age_pressure * rest_multiplier, 0.0, 4.8), 4),
        "pace": round(-clamp((old_share * 1.1 + very_old_share * 1.2) * rest_multiplier, 0.0, 2.5), 4),
        "defense_leak": round(clamp((old_share * 1.65 + very_old_share * 2.05 + max(0.0, average_age - 31.0) * 0.12) * rest_multiplier, 0.0, 4.2), 4),
    }


def recent_scoring_context_for_team(context: dict[str, Any], game: dict[str, Any], team: dict[str, Any], lookback: int = 10) -> dict[str, Any]:
    game_date = game.get("gameDate") or game.get("date")
    current = date_from_iso(game_date)
    team_espn_id = context.get("indices", {}).get("espn_id_by_team_id", {}).get(team["id"])
    if not current or not team_espn_id:
        return {"recent_game_count": 0}
    rows = []
    for boxscore in context.get("indices", {}).get("boxscores_by_team_espn_id", {}).get(str(team_espn_id), context["boxscores"]):
        box_date = date_from_iso(boxscore.get("date"))
        if not box_date or box_date >= current:
            continue
        if boxscore.get("status") != "STATUS_FINAL" or not boxscore.get("home_score") or not boxscore.get("away_score"):
            continue
        is_home = str(boxscore.get("home_team_id")) == str(team_espn_id)
        is_away = str(boxscore.get("away_team_id")) == str(team_espn_id)
        if not is_home and not is_away:
            continue
        team_score = float(boxscore["home_score"] if is_home else boxscore["away_score"])
        opp_score = float(boxscore["away_score"] if is_home else boxscore["home_score"])
        rows.append({"date": box_date, "team_score": team_score, "opp_score": opp_score, "total": team_score + opp_score})
    recent = sorted(rows, key=lambda row: row["date"])[-lookback:]
    if len(recent) < 3:
        return {"recent_game_count": len(recent)}
    mean_for = sum(row["team_score"] for row in recent) / len(recent)
    mean_against = sum(row["opp_score"] for row in recent) / len(recent)
    mean_total = sum(row["total"] for row in recent) / len(recent)
    return {
        "recent_game_count": len(recent),
        "points_for": round(mean_for, 3),
        "points_against": round(mean_against, 3),
        "total": round(mean_total, 3),
        "pace_delta": round(clamp((mean_total - 228.0) * 0.08, -3.0, 3.4), 3),
        "offense_delta": round(clamp((mean_for - 114.0) * 0.1, -3.0, 3.0), 3),
        "defense_allowed_delta": round(clamp((mean_against - 114.0) * 0.1, -3.0, 3.0), 3),
    }


def game_environment_effect(team_context: dict[str, Any] | None, opp_context: dict[str, Any] | None) -> dict[str, float]:
    own = (team_context or {}).get("recent_scoring") or {}
    opp = (opp_context or {}).get("recent_scoring") or {}
    if own.get("recent_game_count", 0) < 3 and opp.get("recent_game_count", 0) < 3:
        return {"offense": 0.0, "pace": 0.0}
    pace = float(own.get("pace_delta") or 0.0) * 0.5 + float(opp.get("pace_delta") or 0.0) * 0.5
    offense = (
        float(own.get("offense_delta") or 0.0) * 0.58
        + float(opp.get("defense_allowed_delta") or 0.0) * 0.48
        + float(own.get("pace_delta") or 0.0) * 0.12
        + float(opp.get("pace_delta") or 0.0) * 0.08
    )
    recent_total = recent_environment_total(team_context, opp_context)
    if recent_total is not None:
        low_total_pressure = max(0.0, 226.0 - recent_total)
        high_total_release = max(0.0, recent_total - 235.0)
        offense += high_total_release * 0.08 - low_total_pressure * 0.12
        pace += high_total_release * 0.05 - low_total_pressure * 0.05
    return {"offense": round(clamp(offense * 1.7, -5.5, 5.5), 4), "pace": round(clamp(pace * 1.8, -4.5, 4.5), 4)}


def recent_environment_total(team_context: dict[str, Any] | None, opp_context: dict[str, Any] | None) -> float | None:
    totals = []
    for context in [team_context or {}, opp_context or {}]:
        recent = context.get("recent_scoring") or {}
        if recent.get("recent_game_count", 0) >= 3 and recent.get("total"):
            totals.append(float(recent["total"]))
    return sum(totals) / len(totals) if totals else None


def matchup_total_environment_effect(team_features: dict[str, float], opp_features: dict[str, float]) -> dict[str, float]:
    own_def = team_features.get("defense_total", 50)
    opp_def = opp_features.get("defense_total", 50)
    own_pressure = team_features.get("offense_pressure", 50)
    opp_pressure = opp_features.get("offense_pressure", 50)
    weak_defense_pace = max(0.0, 52 - own_def) * 0.045 + max(0.0, 52 - opp_def) * 0.045
    weak_rim_pace = max(0.0, 52 - team_features.get("defense_rim", 50)) * 0.025 + max(0.0, 52 - opp_features.get("defense_rim", 50)) * 0.025
    pressure_pace = max(0.0, own_pressure - 58) * 0.025 + max(0.0, opp_pressure - 58) * 0.025
    grind_pace = max(0.0, own_def - 56) * 0.075 + max(0.0, opp_def - 56) * 0.075
    low_pressure_drag = max(0.0, 56 - own_pressure) * 0.025 + max(0.0, 56 - opp_pressure) * 0.025
    raw_pace = weak_defense_pace + weak_rim_pace + pressure_pace - grind_pace - low_pressure_drag

    # Keep this layer as shared total environment; direct offensive-rating edits improved totals
    # but distorted spread calibration in full-sample checks.
    pace = clamp(raw_pace * 1.8, -4.2, 4.4)
    return {"pace": round(pace, 4), "offense": 0.0}


def date_from_iso(value: str | None) -> Any:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None


def defensive_pressure_effect(team_features: dict[str, float], opp_features: dict[str, float]) -> float:
    activity = max(0.0, opp_features.get("defense_activity", opp_features.get("defensive_events", 50)) - 56)
    integrity = max(0.0, opp_features.get("defense_integrity", 50) - 55)
    ball_security = max(0.0, 58 - team_features.get("passing", 50))
    creation_resistance = max(0.0, 72 - team_features.get("top_creation", team_features.get("creation_burden", 50)))
    elite_creator_relief = max(0.0, team_features.get("top_creation", 50) - 78) * 0.035
    pressure = activity * (0.018 + ball_security * 0.0015 + creation_resistance * 0.001) + integrity * 0.012 - elite_creator_relief
    return clamp(pressure, -1.5, 4.0)


def mean_or_none(values: list[float], digits: int = 4) -> float | None:
    return round(sum(values) / len(values), digits) if values else None


def mean_abs_or_none(values: list[float], digits: int = 4) -> float | None:
    return round(sum(abs(value) for value in values) / len(values), digits) if values else None


def espn_team_id_map(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    teams_by_abbrev = {team["abbrev"]: team for team in canonical["teams"]}
    espn_to_abbrev = {
        "1": "ATL", "2": "BOS", "3": "NOP", "4": "CHI", "5": "CLE", "6": "DAL", "7": "DEN", "8": "DET", "9": "GSW", "10": "HOU",
        "11": "IND", "12": "LAC", "13": "LAL", "14": "MIA", "15": "MIL", "16": "MIN", "17": "BKN", "18": "NYK", "19": "ORL", "20": "PHI",
        "21": "PHX", "22": "POR", "23": "SAC", "24": "SAS", "25": "OKC", "26": "UTA", "27": "WAS", "28": "TOR", "29": "MEM", "30": "CHA",
    }
    return {espn_id: teams_by_abbrev[abbrev] for espn_id, abbrev in espn_to_abbrev.items() if abbrev in teams_by_abbrev}


def coach_effect(coach: CoachRating | None) -> dict[str, float]:
    if coach is None:
        return {"offense": 0.0, "defense": 0.0, "tempo": 0.0, "tempo_control": 0.0, "hands_on": 0.0, "playoff": 0.0}
    ratings = coach.ratings
    hands_on = (ratings["hands_on_control"] - 3) * 0.3
    offense = (ratings["offensive_structure"] - 3) * 0.85 + (ratings["matchup_adjustments"] - 3) * 0.45 + hands_on * 0.55
    defense = (ratings["defensive_structure"] - 3) * 0.9 + (ratings["matchup_adjustments"] - 3) * 0.5 + hands_on * 0.55
    tempo = (ratings["experimentation"] - 3) * 0.4 - (ratings["hands_on_control"] - 3) * 0.2
    tempo_control = (ratings["defensive_structure"] - 3) * 0.5 + (ratings["hands_on_control"] - 3) * 0.25
    playoff = (ratings["playoff_preparation"] - 3) * 0.8 + (ratings["matchup_adjustments"] - 3) * 0.35
    return {"offense": clamp(offense, -3.0, 3.0), "defense": clamp(defense, -3.2, 3.2), "tempo": clamp(tempo, -2, 2), "tempo_control": clamp(tempo_control, -1.5, 1.5), "hands_on": hands_on, "playoff": clamp(playoff, -2.5, 2.5)}


def scaled_coach_effect(coach: CoachRating | None, team_features: dict[str, float]) -> dict[str, float]:
    base = coach_effect(coach)
    offense_fit = clamp(
        0.5
        + max(-10.0, team_features.get("offense_balance", 50) - 50) * 0.018
        + max(-10.0, team_features.get("primary_creator", 50) - 65) * 0.012
        + max(0.0, team_features.get("spacing", 50) - 55) * 0.008,
        0.35,
        1.0,
    )
    defense_fit = clamp(
        0.5
        + max(-10.0, team_features.get("defense_total", 50) - 50) * 0.018
        + max(-10.0, team_features.get("defensive_anchor", 50) - 62) * 0.01
        + max(0.0, team_features.get("defensive_events", 50) - 55) * 0.006,
        0.35,
        1.0,
    )
    return {
        **base,
        "offense": round(base["offense"] * offense_fit, 4),
        "defense": round(base["defense"] * defense_fit, 4),
        "tempo_control": round(base["tempo_control"] * defense_fit, 4),
        "offense_fit": round(offense_fit, 4),
        "defense_fit": round(defense_fit, 4),
    }


def primary_creator_score(features: dict[str, float]) -> float:
    return (
        features.get("usage", 50) * 0.62
        + features.get("impact", 50) * 0.23
        + features.get("passing", 50) * 0.1
        + features.get("rim_pressure", 50) * 0.05
    )


def player_star_power_score(features: dict[str, float]) -> float:
    return (
        features.get("impact", 50) * 0.5
        + features.get("usage", 50) * 0.35
        + features.get("playoff_translation", 50) * 0.15
    )


def defensive_anchor_score(features: dict[str, float]) -> float:
    return (
        features.get("rim_deterrence", 50) * 0.45
        + features.get("defensive_events", 50) * 0.3
        + features.get("impact", 50) * 0.15
        + clamp(100 - features.get("defensive_weak_link", 50), 1, 99) * 0.1
    )


def lineup_quality_effect(team_features: dict[str, float], opp_features: dict[str, float]) -> float:
    own_quality = blend([team_features.get("impact", 50), team_features.get("star_power", 50), team_features.get("primary_creator", 50), team_features.get("offense_creation", 50), team_features.get("offense_balance", 50)])
    opp_quality = blend([opp_features.get("impact", 50), opp_features.get("star_power", 50), opp_features.get("defense_total", 50), opp_features.get("defensive_anchor", 50)])
    return clamp((own_quality - opp_quality) * LINEUP_QUALITY_MARGIN_FACTOR, -LINEUP_QUALITY_EFFECT_CAP, LINEUP_QUALITY_EFFECT_CAP)


def unsupported_creation_effect(team_features: dict[str, float]) -> float:
    creation = blend([team_features.get("top_creation", team_features.get("creation_burden", 50)), team_features.get("primary_creator", team_features.get("creation_burden", 50))])
    if creation < 72:
        return 0.0
    support = blend([team_features.get("impact", 50), team_features.get("spacing", 50), team_features.get("passing", 50), team_features.get("offense_balance", 50)])
    penalty = max(0.0, creation - 72) * max(0.0, 58 - support) * 0.03
    bonus = max(0.0, support - 62) * max(0.0, creation - 74) * 0.006
    return clamp(bonus - penalty, -3.4, 1.2)


def creator_advantage(team_features: dict[str, float], opp_features: dict[str, float]) -> float:
    top_creation = blend([team_features.get("top_creation", team_features.get("creation_burden", 50)), team_features.get("primary_creator", team_features.get("creation_burden", 50))])
    star_power = team_features.get("star_power", team_features.get("impact", 50))
    pressure_release = max(0.0, team_features.get("passing", 50) - 55) * 0.025
    creation = max(0.0, top_creation - 70) ** 1.08 * 0.09
    star = max(0.0, star_power - 60) ** 1.12 * 0.08
    defensive_pressure = max(0.0, opp_features.get("defensive_events", 50) - 62) * 0.035
    return clamp(creation + star + pressure_release - defensive_pressure, -3.5, 5.0)


def spacing_creation_interaction(team_features: dict[str, float]) -> float:
    spacing = team_features.get("spacing", 50)
    top_creation = team_features.get("top_creation", team_features.get("creation_burden", 50))
    if spacing < 48 and top_creation > 75:
        return clamp((spacing - 48) * 0.07, -2.5, 0)
    if spacing > 60 and top_creation > 72:
        return clamp((spacing - 60) * 0.14 + (top_creation - 72) * 0.045, 0, 4.2)
    return 0.0


def opponent_targeting_penalty(team_features: dict[str, float], opp_features: dict[str, float], opp_coach_mod: dict[str, float]) -> float:
    weak_link = max(0.0, opp_features.get("defensive_weak_link", 50) - 58)
    creation = max(0.0, team_features.get("top_creation", team_features.get("creation_burden", 50)) - 68)
    coach_activation = 1 + max(0.0, opp_coach_mod.get("defense", 0)) * 0.04
    return clamp(weak_link * creation * 0.0025 / coach_activation, 0, 2.5)


def team_shot_diet(team_features: dict[str, float], opp_features: dict[str, float], coach: CoachRating | None) -> dict[str, float]:
    coach_mod = coach_effect(coach)
    rim_suppression = max(0.0, opp_features["rim_deterrence"] - 60) * 0.0028
    spacing_boost = max(0.0, team_features["spacing"] - 58) * 0.0025
    rim = clamp(0.335 + (team_features["rim_pressure"] - 50) * 0.002 - rim_suppression, 0.18, 0.48)
    pull_up_three = clamp(0.095 + (team_features["creation_burden"] - 55) * 0.0014 + spacing_boost * 0.5, 0.04, 0.2)
    corner_three = clamp(0.105 + spacing_boost + coach_mod["hands_on"] * 0.008, 0.04, 0.21)
    above_break_three = clamp(0.205 + spacing_boost * 0.7, 0.12, 0.34)
    free_throw = clamp(0.165 + (team_features["rim_pressure"] - 50) * 0.0012, 0.08, 0.26)
    midrange = max(0.04, 1.0 - (rim + pull_up_three + corner_three + above_break_three + free_throw))
    total = rim + pull_up_three + corner_three + above_break_three + free_throw + midrange
    diet = {
        "rim": rim / total,
        "midrange": midrange / total,
        "corner_three": corner_three / total,
        "above_break_three": above_break_three / total,
        "pull_up_three": pull_up_three / total,
        "free_throw": free_throw / total,
    }
    shot_quality_delta = (
        (diet["rim"] - 0.32) * 9
        + ((diet["corner_three"] + diet["above_break_three"] + diet["pull_up_three"]) - 0.38) * 7
        + max(0.0, opp_features["defensive_weak_link"] - 55) * 0.025
        - max(0.0, opp_features["rim_deterrence"] - 65) * 0.035
        - max(0.0, opp_features["defensive_events"] - 62) * 0.02
    )
    diet["shot_quality_delta"] = clamp(shot_quality_delta, -4.5, 4.5)
    return diet


def blend(values: list[float]) -> float:
    return sum(values) / len(values) if values else 50.0


def weighted_average(values: list[float], weights: list[float]) -> float:
    total = sum(weights)
    return sum(value * weight for value, weight in zip(values, weights, strict=False)) / total if total else 50.0


def weighted_top_average(values: list[float], weights: list[float], top_n: int = 3) -> float:
    pairs = sorted(zip(values, weights, strict=False), key=lambda item: item[0], reverse=True)[:top_n]
    total = sum(weight for _, weight in pairs)
    return sum(value * weight for value, weight in pairs) / total if total else 50.0


def nonlinear_high(value: float, threshold: float) -> float:
    bonus = max(0.0, value - threshold) ** 1.18
    return clamp(value + bonus * 0.18, 1, 99)


def nonlinear_low(value: float, threshold: float) -> float:
    gap = max(0.0, threshold - value) ** 1.15
    return clamp(50 + gap * 0.55, 1, 99)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def print_json(value: Any) -> None:
    print(json.dumps(to_plain(value), indent=2, sort_keys=True))
