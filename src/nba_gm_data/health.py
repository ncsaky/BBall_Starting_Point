from __future__ import annotations

import json
import random
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .schema import (
    CANONICAL_START_DATE,
    DevelopmentEvent,
    InjuryEvent,
    Player,
    PlayerHealthProfile,
    PlayerHealthState,
    TraitValue,
    to_plain,
)
from .utils import clamp, maybe_float, normalize_name, stable_id


SCHEDULE_FILE = Path("NBA Schedule/schedule_v2025_2026.json")
PLAYER_HEALTH_OVERRIDES_FILE = Path("data/overrides/player_health_overrides.json")
INJURY_MODEL_CONFIG_FILE = Path("data/overrides/injury_model_config.json")
PHYSICAL_TRAITS = {"foot_speed_lateral_agility", "stamina_cardio", "rim_pressure", "defensive_effort", "portability"}
DEVELOPMENT_TRAITS = [
    "shooting_range",
    "shot_versatility",
    "handle_pressure",
    "rim_pressure",
    "passing_reads",
    "defensive_effort",
    "foot_speed_lateral_agility",
    "stamina_cardio",
    "scheme_iq",
    "portability",
]


def default_injury_model_config() -> dict[str, Any]:
    return {
        "version": "injury_fatigue_development_v1",
        "season_start": "2025-10-01",
        "season_end": "2026-04-12",
        "severity_bands": {
            "day_to_day": {"min_per_season": 360, "max_per_season": 800, "days": [1, 4], "weight": 0.68, "rust_after_return": 3},
            "short": {"min_per_season": 120, "max_per_season": 210, "days": [3, 10], "weight": 0.22, "rust_after_return": 8},
            "medium": {"min_per_season": 35, "max_per_season": 75, "days": [15, 42], "weight": 0.07, "rust_after_return": 16},
            "long": {"min_per_season": 12, "max_per_season": 26, "days": [43, 90], "weight": 0.025, "rust_after_return": 28},
            "season_ending": {"min_per_season": 0, "max_per_season": 10, "days": [91, 240], "weight": 0.005, "rust_after_return": 45},
        },
        "body_area_weights": {
            "head_illness": 0.16,
            "shoulder_arm_hand": 0.18,
            "back_core": 0.12,
            "hip_groin": 0.13,
            "knee": 0.18,
            "ankle_foot": 0.23,
        },
        "body_area_quota_ranges": {
            "head_illness": {"min_per_season": 40, "max_per_season": 95},
            "shoulder_arm_hand": {"min_per_season": 45, "max_per_season": 100},
            "back_core": {"min_per_season": 28, "max_per_season": 75},
            "hip_groin": {"min_per_season": 32, "max_per_season": 80},
            "knee": {"min_per_season": 35, "max_per_season": 90},
            "ankle_foot": {"min_per_season": 60, "max_per_season": 125},
        },
        "tuning": {
            "base_player_game_injury_rate": 0.021,
            "base_game_fatigue_gain": 4.2,
            "back_to_back_fatigue_gain": 2.8,
            "fatigue_decay_per_rest_day": 6.5,
            "rust_decay_per_game": 7.5,
            "fatigue_performance_penalty_per_point": 0.065,
            "rust_performance_penalty_per_point": 0.08,
            "development_base_growth": 0.08,
        },
        "notes": "Lightweight 2K-style sandbox health model. Quotas guide leaguewide injury frequency while player risk comes from age, workload, stamina, durability, history, and performance staff.",
    }


def load_injury_model_config(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root)
    config = default_injury_model_config()
    path = root / INJURY_MODEL_CONFIG_FILE
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            config = deep_merge(config, json.load(handle))
    return config


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_health_records(
    players: list[Player],
    player_rows: list[dict[str, Any]],
    traits: list[TraitValue],
    health_overrides: dict[str, Any] | None,
    config: dict[str, Any] | None,
) -> tuple[list[PlayerHealthProfile], list[PlayerHealthState], list[InjuryEvent]]:
    config = config or default_injury_model_config()
    overrides = overrides_by_player_name(health_overrides or {})
    trait_values = {(trait.player_id, trait.trait_key): trait.value for trait in traits}
    rows_by_player = {player.id: row for player, row in zip(players, player_rows, strict=False)}
    profiles: list[PlayerHealthProfile] = []
    states: list[PlayerHealthState] = []
    events: list[InjuryEvent] = []
    for player in players:
        row = rows_by_player.get(player.id, {})
        override = overrides.get(player.normalized_name, {})
        durability = maybe_float(override.get("durability"))
        if durability is None:
            durability = generic_durability(player, row, trait_values.get((player.id, "stamina_cardio"), 50.0))
        risk_tags = list(dict.fromkeys([*generic_body_area_tags(player), *list(override.get("body_area_risk_tags") or [])]))
        prior_injuries = list(override.get("major_prior_injuries") or [])
        injury_prone = bool(override.get("injury_prone", durability < 48 or bool(prior_injuries)))
        source_ids = ["src_injury_model_config_v1"]
        if player.source_ids:
            source_ids.append("src_player_skill_input_2025_26")
        if override:
            source_ids.append("src_player_health_overrides_v1")
        confidence = maybe_float(override.get("confidence"))
        profiles.append(
            PlayerHealthProfile(
                id=stable_id("health_profile", player.id),
                player_id=player.id,
                durability=round(clamp(durability, 1, 99), 2),
                injury_prone=injury_prone,
                body_area_risk_tags=risk_tags,
                major_prior_injuries=prior_injuries,
                confidence=round(clamp(confidence if confidence is not None else 0.38, 0.0, 1.0), 3),
                source_ids=list(dict.fromkeys(source_ids)),
                notes=override.get("notes") or "Generic v1 durability profile from age, size, projected workload, stamina proxy, and position risk.",
            )
        )
        current = current_injury_override(player, row, override)
        event_id = None
        return_date = None
        status = "active"
        rust = 0.0
        notes = "Healthy at canonical startup unless a manual override or raw out-for-season flag says otherwise."
        state_sources = ["src_injury_model_config_v1"]
        if current:
            event = startup_injury_event(player, current, config)
            events.append(event)
            event_id = event.id
            return_date = event.return_date
            status = "out"
            rust = float((config.get("severity_bands") or {}).get(event.severity, {}).get("rust_after_return", 25))
            notes = current.get("notes") or "Startup injury seeded from explicit health override or raw out-for-season flag."
            state_sources = list(event.source_ids)
        states.append(
            PlayerHealthState(
                id=stable_id("health_state", player.id, CANONICAL_START_DATE),
                player_id=player.id,
                as_of_date=CANONICAL_START_DATE,
                fatigue=0.0,
                current_injury_id=event_id,
                availability_status=status,
                return_date=return_date,
                rust=round(rust, 2),
                games_missed=0,
                source_ids=list(dict.fromkeys(state_sources)),
                notes=notes,
            )
        )
    return profiles, states, events


def overrides_by_player_name(health_overrides: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        normalize_name(override.get("player_name")): override
        for override in health_overrides.get("players", [])
        if override.get("player_name")
    }


def generic_durability(player: Player, row: dict[str, Any], stamina: float) -> float:
    age = maybe_float(player.age) or 27.0
    minutes = maybe_float(player.minutes_projection) or 0.0
    weight = maybe_float(player.weight_lbs) or 210.0
    value = 68.0
    value += (stamina - 50.0) * 0.18
    value -= max(0.0, age - 30.0) * 1.15
    value -= max(0.0, 21.0 - age) * 0.45
    value -= max(0.0, minutes - 28.0) * 0.35
    value -= max(0.0, weight - 245.0) * 0.045
    if str(player.position or "").upper() in {"C", "PF-C", "C-PF"}:
        value -= 2.0
    if row.get("OutForSeason"):
        value -= 15.0
    return clamp(value, 28.0, 82.0)


def generic_body_area_tags(player: Player) -> list[str]:
    tags: list[str] = []
    position = str(player.position or "").upper()
    age = maybe_float(player.age) or 27.0
    weight = maybe_float(player.weight_lbs) or 210.0
    if any(token in position for token in ["PG", "SG"]):
        tags.append("ankle_foot")
    if any(token in position for token in ["PF", "C"]) or weight >= 240:
        tags.extend(["knee", "back_core"])
    if age >= 33:
        tags.extend(["ankle_foot", "back_core"])
    return sorted(dict.fromkeys(tags))


def current_injury_override(player: Player, row: dict[str, Any], override: dict[str, Any]) -> dict[str, Any] | None:
    current = override.get("current_injury")
    if isinstance(current, dict):
        return {**current, "source_ids": ["src_player_health_overrides_v1"]}
    if row.get("OutForSeason"):
        return {
            "body_area": "ankle_foot",
            "severity": "season_ending",
            "return_date": "2026-07-01",
            "expected_days_missed": days_between(CANONICAL_START_DATE, "2026-07-01"),
            "expected_games_missed": 82,
            "recurrence": True,
            "source_ids": ["src_player_skill_input_2025_26"],
            "notes": "Raw player input marks OutForSeason TRUE. Body area is a conservative generic lower-leg placeholder unless manually overridden.",
        }
    return None


def startup_injury_event(player: Player, current: dict[str, Any], config: dict[str, Any]) -> InjuryEvent:
    severity = current.get("severity") or "medium"
    return_date = current.get("return_date") or date_to_str(parse_date(CANONICAL_START_DATE) + timedelta(days=default_days_for_severity(severity, config)))
    expected_days = int(maybe_float(current.get("expected_days_missed")) or days_between(CANONICAL_START_DATE, return_date))
    return InjuryEvent(
        id=stable_id("injury", player.id, CANONICAL_START_DATE, severity, current.get("body_area") or "unknown"),
        player_id=player.id,
        team_id=player.team_id,
        start_date=CANONICAL_START_DATE,
        return_date=return_date,
        body_area=current.get("body_area") or "unknown",
        severity=severity,
        expected_days_missed=expected_days,
        expected_games_missed=int(maybe_float(current.get("expected_games_missed")) or expected_games_from_days(expected_days)),
        recurrence=bool(current.get("recurrence", False)),
        status=current.get("status") or "known_startup_injury",
        source_ids=list(dict.fromkeys(current.get("source_ids") or ["src_player_health_overrides_v1"])),
        notes=current.get("notes") or "Known or manually seeded startup injury for the canonical preseason snapshot.",
    )


def simulate_health(root: str | Path, canonical: dict[str, Any] | Any, from_date: str, through_date: str, seed: int = 1) -> dict[str, Any]:
    root = Path(root)
    canonical = to_plain(canonical)
    config = load_injury_model_config(root)
    schedule = schedule_games_in_range(root, from_date, through_date)
    team_by_espn = espn_team_id_map_from_canonical(canonical)
    players_by_team = rotation_players_by_team(canonical)
    profiles = {profile["player_id"]: profile for profile in canonical.get("player_health_profiles", [])}
    states = {state["player_id"]: dict(state) for state in canonical.get("player_health_states", [])}
    traits = trait_lookup(canonical)
    last_game_date: dict[str, date] = {}
    severity_counts = {severity: 0 for severity in config.get("severity_bands", {})}
    body_counts = {body: 0 for body in config.get("body_area_weights", {})}
    events: list[dict[str, Any]] = []
    for game in schedule:
        game_date = parse_date(game["gameDate"])
        for espn_id in [str(game.get("awayTeamId")), str(game.get("homeTeamId"))]:
            team = team_by_espn.get(espn_id)
            if not team:
                continue
            rest_days = rest_days_since(last_game_date.get(team["id"]), game_date)
            staff = performance_staff_modifiers(canonical, team["id"])
            for player in players_by_team.get(team["id"], []):
                state = states.setdefault(player["id"], default_state_dict(player["id"], from_date))
                advance_state_for_date(state, game_date, rest_days, config, staff)
                if state["availability_status"] != "active":
                    state["games_missed"] = int(state.get("games_missed") or 0) + 1
                    continue
                minutes = float(player.get("minutes_projection") or 0)
                stamina = traits.get((player["id"], "stamina_cardio"), 50.0)
                add_game_fatigue(state, player, minutes, stamina, rest_days, config, staff)
                risk = injury_risk_for_player(player, profiles.get(player["id"], {}), state, minutes, stamina, config, staff)
                rng = random.Random(f"{seed}:{game['externalGameId']}:{player['id']}:injury")
                if rng.random() < risk:
                    severity = choose_quota_weighted(config.get("severity_bands", {}), severity_counts, rng)
                    if not severity:
                        continue
                    body_area = choose_body_area(config, profiles.get(player["id"], {}), body_counts, rng)
                    if not body_area:
                        continue
                    event = generated_injury_event(player, game_date, severity, body_area, profiles.get(player["id"], {}), config, staff, seed)
                    events.append(to_plain(event))
                    severity_counts[severity] += 1
                    body_counts[body_area] += 1
                    state.update(
                        {
                            "current_injury_id": event.id,
                            "availability_status": "out",
                            "return_date": event.return_date,
                            "rust": float((config.get("severity_bands") or {}).get(severity, {}).get("rust_after_return", 12)),
                            "source_ids": list(dict.fromkeys([*(state.get("source_ids") or []), "src_injury_model_config_v1"])),
                            "notes": f"Generated sandbox injury on {date_to_str(game_date)}.",
                        }
                    )
            last_game_date[team["id"]] = game_date
    through_day = parse_date(through_date)
    players_by_id = {player["id"]: player for player in canonical.get("players", [])}
    for player_id, state in states.items():
        player = players_by_id.get(player_id)
        if not player:
            continue
        staff = performance_staff_modifiers(canonical, player["team_id"])
        advance_state_for_date(state, through_day, rest_days_since(last_game_date.get(player["team_id"]), through_day), config, staff)
    final_states = [state_from_dict(state, through_date) for state in states.values()]
    return {
        "from_date": from_date,
        "through_date": through_date,
        "seed": seed,
        "game_count": len(schedule),
        "event_count": len(events),
        "severity_counts": dict(sorted(severity_counts.items())),
        "body_area_counts": dict(sorted(body_counts.items())),
        "events": sorted(events, key=lambda item: (item["start_date"], item["team_id"], item["player_id"], item["id"])),
        "final_states": sorted(final_states, key=lambda item: item["player_id"]),
        "summary": health_sim_summary(events, final_states, config),
        "notes": "Sandbox health simulation only. Replay-real-minutes validation still uses real game availability and minutes as truth.",
    }


def advance_development(canonical: dict[str, Any] | Any, month: str, seed: int = 1) -> dict[str, Any]:
    canonical = to_plain(canonical)
    month = month[:7]
    traits = traits_by_player(canonical)
    states = {state["player_id"]: state for state in canonical.get("player_health_states", [])}
    coaches = coach_development_by_team(canonical)
    events: list[dict[str, Any]] = []
    for player in canonical.get("players", []):
        age = maybe_float(player.get("age"))
        minutes = float(player.get("minutes_projection") or 0)
        if not should_generate_development_event(player, age, minutes):
            continue
        staff = development_staff_modifiers(canonical, player["team_id"], coaches.get(player["team_id"], 3.0))
        state = states.get(player["id"], {})
        health_drag = development_health_drag(state)
        deltas: dict[str, float] = {}
        for trait_key in DEVELOPMENT_TRAITS:
            current = float(traits.get(player["id"], {}).get(trait_key, {}).get("value", 50.0))
            delta = monthly_trait_delta(player, trait_key, current, age, minutes, staff, health_drag, seed, month)
            if abs(delta) >= 0.015:
                deltas[trait_key] = round(delta, 3)
        if deltas:
            event = DevelopmentEvent(
                id=stable_id("development", month, player["id"], seed),
                player_id=player["id"],
                team_id=player["team_id"],
                month=month,
                trait_deltas=dict(sorted(deltas.items())),
                age=age,
                minutes_context=round(minutes, 2),
                staff_context=staff,
                health_context={
                    "availability_status": state.get("availability_status", "active"),
                    "fatigue": round(float(state.get("fatigue") or 0), 2),
                    "rust": round(float(state.get("rust") or 0), 2),
                    "health_drag": round(health_drag, 3),
                },
                confidence=0.42,
                source_ids=["src_development_model_v1", "src_gameplay_staff_seed_v1"],
                notes="Monthly v1 trait movement from age, role/minutes, staff, coach development context, current trait level, and health. Personality is intentionally deferred.",
            )
            events.append(to_plain(event))
    return {
        "month": month,
        "seed": seed,
        "event_count": len(events),
        "events": sorted(events, key=lambda item: (str(item.get("team_id") or ""), str(item.get("player_id") or ""))),
        "summary": development_summary(events),
    }


def sandbox_health_adjusted_pool(canonical: dict[str, Any], game_date: str | None, pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not game_date or not canonical.get("player_health_states"):
        return pool
    game_day = parse_date(game_date)
    states = {state["player_id"]: state for state in canonical.get("player_health_states", [])}
    events_by_player: dict[str, list[dict[str, Any]]] = {}
    for event in canonical.get("injury_events", []):
        if event.get("player_id"):
            events_by_player.setdefault(event["player_id"], []).append(event)
    adjusted: list[dict[str, Any]] = []
    for item in pool:
        player_id = item["player"]["id"]
        state = states.get(player_id)
        active_event = active_injury_event_on_date(events_by_player.get(player_id, []), game_day)
        if active_event:
            continue
        has_event_history = bool(events_by_player.get(player_id))
        if state and not has_event_history and not player_available_on_date(state, game_day):
            continue
        status = "active" if has_event_history else (state or {}).get("availability_status", "active")
        fatigue = float((state or {}).get("fatigue") or 0.0)
        rust = float((state or {}).get("rust") or 0.0) if state else 0.0
        adjusted.append({**item, "health_fatigue": round(fatigue, 2), "health_rust": round(rust, 2), "health_status": status})
    return adjusted


def active_injury_event_on_date(events: list[dict[str, Any]], game_day: date) -> dict[str, Any] | None:
    for event in events:
        start = event.get("start_date")
        end = event.get("return_date")
        if not start or not end:
            continue
        if parse_date(start) <= game_day < parse_date(end):
            return event
    return None


def health_player_report(canonical: dict[str, Any], name: str) -> dict[str, Any] | None:
    canonical = to_plain(canonical)
    needle = normalize_name(name)
    matches = [player for player in canonical.get("players", []) if needle in normalize_name(player["name"]) or needle == player.get("normalized_name")]
    if not matches:
        return None
    player = sorted(matches, key=lambda item: item.get("minutes_projection") or 0, reverse=True)[0]
    return {
        "player": player,
        "profile": next((profile for profile in canonical.get("player_health_profiles", []) if profile["player_id"] == player["id"]), None),
        "state": next((state for state in canonical.get("player_health_states", []) if state["player_id"] == player["id"]), None),
        "injury_events": [event for event in canonical.get("injury_events", []) if event["player_id"] == player["id"]],
    }


def health_team_report(canonical: dict[str, Any], team_query: str) -> dict[str, Any] | None:
    canonical = to_plain(canonical)
    query = team_query.strip().lower()
    teams = canonical.get("teams", [])
    matches = [team for team in teams if query == team["abbrev"].lower()] or [team for team in teams if query in team["name"].lower()]
    if not matches:
        return None
    team = matches[0]
    states = {state["player_id"]: state for state in canonical.get("player_health_states", [])}
    profiles = {profile["player_id"]: profile for profile in canonical.get("player_health_profiles", [])}
    players = [player for player in canonical.get("players", []) if player["team_id"] == team["id"]]
    return {
        "team": team,
        "performance_staff": performance_staff_modifiers(canonical, team["id"]),
        "players": [
            {
                "name": player["name"],
                "minutes_projection": player.get("minutes_projection"),
                "rotation_priority": player.get("rotation_priority"),
                "profile": profiles.get(player["id"]),
                "state": states.get(player["id"]),
            }
            for player in sorted(players, key=lambda item: item.get("minutes_projection") or 0, reverse=True)
            if player.get("rotation_priority") != "fringe" or states.get(player["id"], {}).get("availability_status") != "active"
        ],
    }


def injury_risk_for_player(
    player: dict[str, Any],
    profile: dict[str, Any],
    state: dict[str, Any],
    minutes: float,
    stamina: float,
    config: dict[str, Any],
    staff: dict[str, float],
) -> float:
    tuning = config.get("tuning", {})
    risk = float(tuning.get("base_player_game_injury_rate", 0.021))
    age = maybe_float(player.get("age")) or 27.0
    durability = float(profile.get("durability") or 60.0)
    fatigue = float(state.get("fatigue") or 0.0)
    risk *= 0.66 + minutes / 23.0
    risk *= 1.0 + max(0.0, fatigue - 18.0) / 70.0
    risk *= 1.0 + max(0.0, 58.0 - durability) / 75.0
    risk *= 1.0 + max(0.0, 54.0 - stamina) / 115.0
    risk *= (
        1.0
        + max(0.0, age - 31.0) * 0.052
        + max(0.0, age - 34.0) * 0.12
        + max(0.0, age - 37.0) * 0.14
    )
    if age >= 34.0 and minutes >= 24.0:
        risk *= 1.0 + min(0.85, (minutes - 24.0) * 0.052)
    if profile.get("injury_prone"):
        risk *= 1.22
    risk *= float(staff.get("injury_risk_multiplier", 1.0))
    return clamp(risk, 0.0005, 0.19)


def performance_staff_modifiers(canonical: dict[str, Any], team_id: str) -> dict[str, float]:
    slot = next((slot for slot in canonical.get("gameplay_staff_slots", []) if slot["team_id"] == team_id and slot["slot"] == "performance_lead"), None)
    traits = (slot or {}).get("skill_traits") or {}
    injury_prevention = float(traits.get("injury_prevention", 60.0))
    conditioning = float(traits.get("conditioning", 60.0))
    recovery = float(traits.get("recovery_planning", 60.0))
    return {
        "injury_prevention": round(injury_prevention, 2),
        "conditioning": round(conditioning, 2),
        "recovery_planning": round(recovery, 2),
        "injury_risk_multiplier": round(clamp(1.0 - (injury_prevention - 60.0) * 0.0035, 0.88, 1.08), 4),
        "fatigue_gain_multiplier": round(clamp(1.0 - (conditioning - 60.0) * 0.0035, 0.88, 1.08), 4),
        "recovery_days_multiplier": round(clamp(1.0 - (recovery - 60.0) * 0.004, 0.86, 1.08), 4),
    }


def development_staff_modifiers(canonical: dict[str, Any], team_id: str, coach_development: float) -> dict[str, Any]:
    slot = next((slot for slot in canonical.get("gameplay_staff_slots", []) if slot["team_id"] == team_id and slot["slot"] == "development_lead"), None)
    traits = (slot or {}).get("skill_traits") or {}
    skill = float(traits.get("skill_development", 60.0))
    patience = float(traits.get("prospect_patience", 60.0))
    feedback = float(traits.get("feedback_clarity", 60.0))
    return {
        "skill_development": round(skill, 2),
        "prospect_patience": round(patience, 2),
        "feedback_clarity": round(feedback, 2),
        "coach_development_rating": round(coach_development, 2),
        "development_multiplier": round(clamp(1.0 + (skill - 60.0) * 0.006 + (feedback - 60.0) * 0.003 + (coach_development - 3.0) * 0.08, 0.82, 1.28), 4),
        "patience_multiplier": round(clamp(1.0 + (patience - 60.0) * 0.004, 0.9, 1.16), 4),
    }


def add_game_fatigue(state: dict[str, Any], player: dict[str, Any], minutes: float, stamina: float, rest_days: int, config: dict[str, Any], staff: dict[str, float]) -> None:
    tuning = config.get("tuning", {})
    age = maybe_float(player.get("age")) or 27.0
    gain = float(tuning.get("base_game_fatigue_gain", 4.2)) * (minutes / 24.0) ** 1.12
    if rest_days <= 0:
        gain += float(tuning.get("back_to_back_fatigue_gain", 2.8))
    gain += max(0.0, age - 32.0) * 0.28 + max(0.0, age - 35.0) * 0.18
    gain += max(0.0, 53.0 - stamina) * 0.04
    state["fatigue"] = round(clamp(float(state.get("fatigue") or 0.0) + gain * float(staff.get("fatigue_gain_multiplier", 1.0)), 0.0, 100.0), 2)


def advance_state_for_date(state: dict[str, Any], game_date: date, rest_days: int, config: dict[str, Any], staff: dict[str, float]) -> None:
    tuning = config.get("tuning", {})
    decay = max(0, rest_days) * float(tuning.get("fatigue_decay_per_rest_day", 6.5)) / max(float(staff.get("recovery_days_multiplier", 1.0)), 0.2)
    state["fatigue"] = round(max(0.0, float(state.get("fatigue") or 0.0) - decay), 2)
    return_date = state.get("return_date")
    if state.get("current_injury_id") and return_date and parse_date(return_date) <= game_date:
        state["current_injury_id"] = None
        state["availability_status"] = "active"
        state["return_date"] = None
    if state.get("availability_status") == "active" and float(state.get("rust") or 0.0) > 0:
        state["rust"] = round(max(0.0, float(state.get("rust") or 0.0) - float(tuning.get("rust_decay_per_game", 7.5)) / max(float(staff.get("recovery_days_multiplier", 1.0)), 0.2)), 2)


def choose_quota_weighted(bands: dict[str, Any], counts: dict[str, int], rng: random.Random) -> str | None:
    choices = []
    weights = []
    for severity, info in bands.items():
        if counts.get(severity, 0) >= int(info.get("max_per_season", 999999)):
            continue
        weight = float(info.get("weight", 1.0))
        if counts.get(severity, 0) < int(info.get("min_per_season", 0)):
            weight *= 1.35
        choices.append(severity)
        weights.append(weight)
    return weighted_choice(choices, weights, rng)


def choose_body_area(config: dict[str, Any], profile: dict[str, Any], counts: dict[str, int], rng: random.Random) -> str | None:
    quota = config.get("body_area_quota_ranges", {})
    choices = []
    weights = []
    tags = set(profile.get("body_area_risk_tags") or [])
    for body, weight in (config.get("body_area_weights") or {}).items():
        if counts.get(body, 0) >= int((quota.get(body) or {}).get("max_per_season", 999999)):
            continue
        adjusted = float(weight)
        if body in tags:
            adjusted *= 1.55
        if counts.get(body, 0) < int((quota.get(body) or {}).get("min_per_season", 0)):
            adjusted *= 1.18
        choices.append(body)
        weights.append(adjusted)
    return weighted_choice(choices, weights, rng)


def weighted_choice(choices: list[str], weights: list[float], rng: random.Random) -> str | None:
    if not choices:
        return None
    total = sum(weights)
    if total <= 0:
        return choices[0]
    marker = rng.random() * total
    running = 0.0
    for choice, weight in zip(choices, weights, strict=False):
        running += weight
        if marker <= running:
            return choice
    return choices[-1]


def generated_injury_event(
    player: dict[str, Any],
    game_date: date,
    severity: str,
    body_area: str,
    profile: dict[str, Any],
    config: dict[str, Any],
    staff: dict[str, float],
    seed: int,
) -> InjuryEvent:
    band = config.get("severity_bands", {}).get(severity, {"days": [7, 14]})
    low, high = [int(value) for value in band.get("days", [7, 14])]
    rng = random.Random(f"{seed}:{player['id']}:{date_to_str(game_date)}:{severity}:{body_area}:days")
    raw_days = rng.randint(low, high)
    expected_days = max(1, int(round(raw_days * float(staff.get("recovery_days_multiplier", 1.0)))))
    recurrence = body_area in set(profile.get("body_area_risk_tags") or []) or bool(profile.get("injury_prone"))
    return InjuryEvent(
        id=stable_id("injury", "generated", player["id"], date_to_str(game_date), severity, body_area, seed),
        player_id=player["id"],
        team_id=player["team_id"],
        start_date=date_to_str(game_date),
        return_date=date_to_str(game_date + timedelta(days=expected_days)),
        body_area=body_area,
        severity=severity,
        expected_days_missed=expected_days,
        expected_games_missed=expected_games_from_days(expected_days),
        recurrence=recurrence,
        status="generated_sandbox_injury",
        source_ids=["src_injury_model_config_v1"],
        notes="Generated by quota-guided sandbox injury model from workload, fatigue, durability, history tags, age, stamina, and performance staff.",
    )


def monthly_trait_delta(
    player: dict[str, Any],
    trait_key: str,
    current: float,
    age: float | None,
    minutes: float,
    staff: dict[str, Any],
    health_drag: float,
    seed: int,
    month: str,
) -> float:
    age = 27.0 if age is None else age
    rng = random.Random(f"{seed}:{month}:{player['id']}:{trait_key}:development")
    age_factor = development_age_factor(age)
    role_factor = clamp(minutes / 24.0, 0.18, 1.18)
    if player.get("rotation_priority") == "development_priority":
        role_factor *= 1.16
    if player.get("rotation_priority") == "fringe":
        role_factor *= 0.72
    cap_room = clamp((92.0 - current) / 42.0, 0.08, 1.0)
    growth = 0.08 * age_factor * role_factor * cap_room * float(staff.get("development_multiplier", 1.0)) * float(staff.get("patience_multiplier", 1.0))
    growth -= health_drag * (0.04 if trait_key in PHYSICAL_TRAITS else 0.022)
    if age >= 33 and trait_key in PHYSICAL_TRAITS:
        growth -= min(0.08, (age - 32.0) * 0.012)
    if age >= 35 and trait_key not in {"scheme_iq", "passing_reads"}:
        growth -= 0.012
    noise = rng.gauss(0, 0.022)
    return clamp(growth + noise, -0.12, 0.24)


def development_age_factor(age: float) -> float:
    if age <= 20:
        return 1.08
    if age <= 23:
        return 0.88
    if age <= 26:
        return 0.38
    if age <= 30:
        return 0.12
    if age <= 32:
        return 0.03
    return 0.0


def development_health_drag(state: dict[str, Any]) -> float:
    drag = max(0.0, float(state.get("fatigue") or 0.0) - 55.0) / 45.0
    drag += float(state.get("rust") or 0.0) / 70.0
    if state.get("availability_status", "active") != "active":
        drag += 0.7
    return clamp(drag, 0.0, 2.0)


def should_generate_development_event(player: dict[str, Any], age: float | None, minutes: float) -> bool:
    if age is not None and age <= 26:
        return True
    if player.get("rotation_priority") == "development_priority":
        return True
    if minutes >= 16:
        return True
    if age is not None and age >= 33 and minutes >= 8:
        return True
    return False


def coach_development_by_team(canonical: dict[str, Any]) -> dict[str, float]:
    try:
        from .sim import coach_ratings

        return {rating.team_id: float(rating.ratings.get("development", 3.0)) for rating in coach_ratings(canonical)}
    except Exception:
        return {team["id"]: 3.0 for team in canonical.get("teams", [])}


def schedule_games_in_range(root: Path, from_date: str, through_date: str) -> list[dict[str, Any]]:
    with (root / SCHEDULE_FILE).open("r", encoding="utf-8") as handle:
        games = json.load(handle).get("games", [])
    return sorted(
        [game for game in games if from_date <= str(game.get("gameDate") or "") <= through_date],
        key=lambda item: (item.get("gameDate") or "", item.get("externalGameId") or ""),
    )


def rotation_players_by_team(canonical: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    players_by_team: dict[str, list[dict[str, Any]]] = {}
    for player in canonical.get("players", []):
        if float(player.get("minutes_projection") or 0.0) >= 8.0:
            players_by_team.setdefault(player["team_id"], []).append(player)
    for team_id, players in players_by_team.items():
        players_by_team[team_id] = sorted(players, key=lambda item: item.get("minutes_projection") or 0, reverse=True)[:11]
    return players_by_team


def trait_lookup(canonical: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {(trait["player_id"], trait["trait_key"]): float(trait.get("value") or 50.0) for trait in canonical.get("traits", [])}


def traits_by_player(canonical: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for trait in canonical.get("traits", []):
        output.setdefault(trait["player_id"], {})[trait["trait_key"]] = trait
    return output


def espn_team_id_map_from_canonical(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    teams_by_abbrev = {team["abbrev"]: team for team in canonical.get("teams", [])}
    espn_to_abbrev = {
        "1": "ATL",
        "2": "BOS",
        "3": "NOP",
        "4": "CHI",
        "5": "CLE",
        "6": "DAL",
        "7": "DEN",
        "8": "DET",
        "9": "GSW",
        "10": "HOU",
        "11": "IND",
        "12": "LAC",
        "13": "LAL",
        "14": "MIA",
        "15": "MIL",
        "16": "MIN",
        "17": "BKN",
        "18": "NYK",
        "19": "ORL",
        "20": "PHI",
        "21": "PHX",
        "22": "POR",
        "23": "SAC",
        "24": "SAS",
        "25": "OKC",
        "26": "UTA",
        "27": "WAS",
        "28": "TOR",
        "29": "MEM",
        "30": "CHA",
    }
    return {espn_id: teams_by_abbrev[abbrev] for espn_id, abbrev in espn_to_abbrev.items() if abbrev in teams_by_abbrev}


def player_available_on_date(state: dict[str, Any], game_day: date) -> bool:
    if state.get("availability_status") == "active" and not state.get("current_injury_id"):
        return True
    return_date = state.get("return_date")
    return bool(return_date and parse_date(return_date) <= game_day)


def default_state_dict(player_id: str, as_of_date: str) -> dict[str, Any]:
    return {
        "id": stable_id("health_state", player_id, as_of_date),
        "player_id": player_id,
        "as_of_date": as_of_date,
        "fatigue": 0.0,
        "current_injury_id": None,
        "availability_status": "active",
        "return_date": None,
        "rust": 0.0,
        "games_missed": 0,
        "source_ids": ["src_injury_model_config_v1"],
        "notes": "Generated default health state.",
    }


def state_from_dict(state: dict[str, Any], as_of_date: str) -> dict[str, Any]:
    return {
        "id": stable_id("health_state", state["player_id"], as_of_date),
        "player_id": state["player_id"],
        "as_of_date": as_of_date,
        "fatigue": round(float(state.get("fatigue") or 0.0), 2),
        "current_injury_id": state.get("current_injury_id"),
        "availability_status": state.get("availability_status", "active"),
        "return_date": state.get("return_date"),
        "rust": round(float(state.get("rust") or 0.0), 2),
        "games_missed": int(state.get("games_missed") or 0),
        "source_ids": list(state.get("source_ids") or ["src_injury_model_config_v1"]),
        "notes": state.get("notes") or "",
    }


def health_sim_summary(events: list[dict[str, Any]], final_states: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "injuries_by_severity": count_by(events, "severity"),
        "injuries_by_body_area": count_by(events, "body_area"),
        "players_out_at_end": sum(1 for state in final_states if state["availability_status"] != "active"),
        "players_with_fatigue_70_plus": sum(1 for state in final_states if float(state.get("fatigue") or 0) >= 70),
        "configured_severity_quota_ranges": {
            severity: {"min": info.get("min_per_season"), "max": info.get("max_per_season")}
            for severity, info in (config.get("severity_bands") or {}).items()
        },
    }


def development_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    trait_totals: dict[str, float] = {}
    for event in events:
        for trait, delta in event.get("trait_deltas", {}).items():
            trait_totals[trait] = trait_totals.get(trait, 0.0) + float(delta)
    return {
        "positive_event_count": sum(1 for event in events if sum(event.get("trait_deltas", {}).values()) > 0),
        "negative_event_count": sum(1 for event in events if sum(event.get("trait_deltas", {}).values()) < 0),
        "trait_delta_totals": {key: round(value, 3) for key, value in sorted(trait_totals.items())},
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def rest_days_since(previous: date | None, current: date) -> int:
    if previous is None:
        return 2
    return max(0, (current - previous).days - 1)


def default_days_for_severity(severity: str, config: dict[str, Any]) -> int:
    days = (config.get("severity_bands") or {}).get(severity, {}).get("days") or [7, 14]
    return int(sum(days) / len(days))


def expected_games_from_days(days: int) -> int:
    return max(1, int(round(days * 82 / 176)))


def parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def date_to_str(value: date) -> str:
    return value.isoformat()


def days_between(start: str, end: str) -> int:
    return max(0, (parse_date(end) - parse_date(start)).days)
