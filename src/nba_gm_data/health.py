from __future__ import annotations

import hashlib
import json
import random
from copy import deepcopy
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
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
from .talent import trait_ceiling


SCHEDULE_FILE = Path("NBA Schedule/schedule_v2025_2026.json")
PLAYER_HEALTH_OVERRIDES_FILE = Path("data/overrides/player_health_overrides.json")
INJURY_MODEL_CONFIG_FILE = Path("data/overrides/injury_model_config.json")
PHYSICAL_TRAITS = {"foot_speed_lateral_agility", "stamina_cardio", "rim_pressure", "defensive_effort", "portability"}
DEVELOPMENT_TRAITS = [
    "release_speed",
    "shooting_range",
    "shot_versatility",
    "handle_pressure",
    "rim_pressure",
    "passing_reads",
    "offensive_rebounding",
    "defensive_effort",
    "foot_speed_lateral_agility",
    "screen_navigation",
    "rim_deterrence",
    "stamina_cardio",
    "scheme_iq",
    "portability",
    "playoff_translation",
]
OFFENSIVE_AGING_TRAITS = frozenset({
    "release_speed", "shooting_range", "shot_versatility", "handle_pressure",
    "rim_pressure", "offensive_rebounding",
})
EXPERIENCE_TRAITS = frozenset({"scheme_iq", "passing_reads", "portability"})
# Size of each player's good-or-bad-year draw. User decision 2026-11-19: about two-thirds of Basketball Index's
# year-to-year spread (part of the real spread is measurement noise and role change, not ability). The 94-input
# route compresses rating changes when it re-derives traits, so the older trait set needs a smaller draw to land in
# the same place (Codex DEV-TUNE measured 0.60 at -42%..+36% inputs and -54%..+49% legacy of the starting spread,
# 500+ minutes; target about -40%..+30%).
# Re-measured 2026-11-19 after the level-keeping 94-input routing (ratings_model) removed most of that compression:
# 0.47 gave -52%..+46% (500+) and -62%..+52% (1,500+); 0.28 gives -32%..+28% and -39%..+32%, the same bands main
# had at 0.47 before the routing change (output/prospect-realism/measure_spread.py).
DEVELOPMENT_SEASON_VOLATILITY = 0.28          # 94-input ratings (default)
LEGACY_DEVELOPMENT_SEASON_VOLATILITY = 0.36   # older trait-only ratings
SEASON_FORM_TRAIT_WEIGHTS = {
    "foot_speed_lateral_agility": 0.35,
    "passing_reads": 0.55,
    "portability": 0.55,
    "rim_pressure": 0.70,
    "scheme_iq": 0.55,
    "shot_versatility": 0.75,
    "stamina_cardio": 0.0,
}


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


def generated_prospect_medical_profile(prospect_id: str, year: str, seed: int) -> dict[str, Any]:
    """Fictional medical background; independent of the basketball-rating RNG."""
    rng = random.Random(f"{seed}:{year}:{prospect_id}:medical_v1")
    prone = rng.random() < 0.14
    durability = round(clamp(rng.gauss(47 if prone else 73, 8), 28, 92), 2)
    body = rng.choice(["ankle_foot", "knee", "back_core", "shoulder_arm_hand"])
    history = []
    if prone or rng.random() < 0.22:
        history.append({"body_area": body, "severity": "medium" if prone else "short", "season": str(int(year) - 1), "status": "recovered"})
    current = None
    if history and rng.random() < 0.22:
        start = date(int(year), 6, 10)
        current = {"body_area": body, "severity": "medium", "start_date": start.isoformat(), "return_date": (start + timedelta(days=rng.randint(35, 100))).isoformat()}
    return {"durability": durability, "injury_prone": prone, "body_area_risk_tags": [body] if history else [], "major_prior_injuries": history, "current_injury": current, "origin": "fictional_generated_prospect_v1"}


def prospect_medical_penalty(prospect: dict[str, Any]) -> float:
    medical = prospect.get("medical_profile") or {}
    if not medical:
        return 0.0
    return round(min(9.0, max(0.0, 65 - float(medical.get("durability", 70))) * 0.12 + 1.5 * bool(medical.get("injury_prone")) + min(2, len(medical.get("major_prior_injuries") or [])) * 0.7 + 2 * bool(medical.get("current_injury"))), 2)


def ensure_generated_player_health(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    """Persist profiles once; never reapply a healed entry injury on reload."""
    profiles = save.setdefault("generated_health_profiles", {})
    existing = {p["player_id"] for p in canonical.get("player_health_profiles", [])}
    states = {s["player_id"] for s in save.get("health_states", [])}
    traits = trait_lookup(canonical)
    as_of = str(save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
    seed = save.get("meta", {}).get("seed", 1)
    for player in save.get("generated_players", []):
        pid = player["id"]
        if pid in existing:
            continue
        if pid not in profiles:
            medical = deepcopy(player.get("medical_profile") or {})
            body = SimpleNamespace(**{k: player.get(k) for k in ("age", "minutes_projection", "weight_lbs", "position")})
            rng = random.Random(f"{seed}:{pid}:durability_v1")
            durability = float(medical.get("durability", clamp(generic_durability(body, {}, traits.get((pid, "stamina_cardio"), 50)) + rng.gauss(0, 8), 28, 92)))
            profiles[pid] = {"id": stable_id("health_profile", pid), "player_id": pid, "durability": durability, "injury_prone": bool(medical.get("injury_prone", durability < 52)), "body_area_risk_tags": medical.get("body_area_risk_tags", generic_body_area_tags(body)), "major_prior_injuries": medical.get("major_prior_injuries", []), "confidence": 0.46, "source_ids": ["src_injury_model_config_v1"], "notes": "Persistent generated-player medical profile."}
            if pid not in states:
                state = default_state_dict(pid, as_of)
                injury = medical.get("current_injury") or {}
                if str(injury.get("return_date") or "") > as_of:
                    event_id = stable_id("prospect_entry_injury", pid)
                    state.update(current_injury_id=event_id, availability_status="out", return_date=injury["return_date"], rust=16.0)
                    days = (date.fromisoformat(injury["return_date"]) - date.fromisoformat(injury["start_date"])).days
                    save.setdefault("injury_events", []).append({"id": event_id, "player_id": pid, "team_id": player.get("team_id"), **injury, "expected_days_missed": days, "expected_games_missed": max(1, round(days / 2.4)), "recurrence": False, "status": "active", "source_ids": ["src_injury_model_config_v1"], "notes": "Fictional prospect injury carried into NBA onboarding."})
                save.setdefault("health_states", []).append(state)
                states.add(pid)
        canonical.setdefault("player_health_profiles", []).append(deepcopy(profiles[pid]))
        existing.add(pid)


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
    start_date = current.get("start_date") or CANONICAL_START_DATE
    return_date = current.get("return_date") or date_to_str(parse_date(CANONICAL_START_DATE) + timedelta(days=default_days_for_severity(severity, config)))
    expected_days = int(maybe_float(current.get("expected_days_missed")) or days_between(start_date, return_date))
    return InjuryEvent(
        id=stable_id("injury", player.id, start_date, severity, current.get("body_area") or "unknown"),
        player_id=player.id,
        team_id=player.team_id,
        start_date=start_date,
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


def simulate_health(
    root: str | Path,
    canonical: dict[str, Any] | Any,
    from_date: str,
    through_date: str,
    seed: int = 1,
    schedule: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    config = load_injury_model_config(root)
    schedule = schedule_games_in_range(root, from_date, through_date, games=schedule)
    team_by_espn = espn_team_id_map_from_canonical(canonical)
    from . import injury_model as im
    model = im.load_model(root)
    # v2 (per-body-part, evidence-fitted): deep reserves can get hurt too; no league-wide quotas.
    players_by_team = (rotation_players_by_team(canonical, im.MIN_MINUTES_FOR_EXPOSURE, 14) if model
                       else rotation_players_by_team(canonical))
    history_cache: dict[str, list] = {}
    rotation_star = {slot["team_id"]: float((slot.get("skill_traits") or {}).get("rotation_management", 60.0)) / 20.0
                     for slot in canonical.get("gameplay_staff_slots", []) if slot.get("slot") == "head_coach"}
    profiles = {profile["player_id"]: profile for profile in canonical.get("player_health_profiles", [])}
    states = {state["player_id"]: dict(state) for state in canonical.get("player_health_states", [])}
    selected = {p["id"] for players in players_by_team.values() for p in players}
    for player in canonical.get("players", []):
        if player.get("team_id") and not player.get("_inactive_player") and player["id"] not in selected and states.get(player["id"], {}).get("availability_status", "active") != "active":
            players_by_team.setdefault(player["team_id"], []).append(player)
    traits = trait_lookup(canonical)
    last_game_date: dict[str, date] = {}
    season_start_year = season_start_year_for_health_date(from_date)
    season_floor = f"{season_start_year}-07-01"
    season_ceiling = f"{season_start_year + 1}-06-30"
    existing_season_events = [
        event
        for event in canonical.get("injury_events", [])
        if season_floor <= str(event.get("start_date") or "")[:10] <= season_ceiling
    ]
    severity_counts = {
        severity: sum(str(event.get("severity") or "") == severity for event in existing_season_events)
        for severity in config.get("severity_bands", {})
    }
    body_counts = {
        body: sum(str(event.get("body_area") or "") == body for event in existing_season_events)
        for body in config.get("body_area_weights", {})
    }
    events: list[dict[str, Any]] = []
    # Coach rest (AI teams only; the user's coach suggests, see save.attach_rest_suggestions). Needs league standings,
    # so it runs inside a save (or a harness that keeps records), not in standalone health replays.
    rest_ready = bool(model) and bool(canonical.get("save_team_records"))
    standings = league_rest_context(canonical) if rest_ready else {}
    human_teams = set(canonical.get("_human_team_ids") or [])
    rested_tonight: dict[tuple[str, str], int] = {}
    regulars_out: dict[str, int] = {}
    if rest_ready:
        for team_id, team_players in players_by_team.items():
            regulars_out[team_id] = sum(1 for p in team_players if states.get(p["id"], {}).get("availability_status", "active") != "active"
                                        and float(p.get("_trade_value_minutes_projection") or p.get("minutes_projection") or 0) >= REST_MIN_MINUTES)
    for game in schedule:
        game_date = parse_date(game["gameDate"])
        rest_on = rest_ready and str(game.get("phase") or "regular") == "regular"
        for espn_id in [str(game.get("awayTeamId")), str(game.get("homeTeamId"))]:
            team = team_by_espn.get(espn_id)
            if not team:
                continue
            team_rest_days = rest_days_since(last_game_date.get(team["id"]), game_date)
            staff = performance_staff_modifiers(canonical, team["id"])
            for player in players_by_team.get(team["id"], []):
                state = states.setdefault(player["id"], default_state_dict(player["id"], from_date))
                # Days off since this player's team last played. The save advances health one day at a time, so the
                # date is carried on the state (otherwise every first game of a call looked like two days' rest and
                # back-to-backs never added fatigue).
                previous_game = state.get("last_team_game")
                rest_days = (rest_days_since(parse_date(previous_game), game_date) if previous_game and previous_game < date_to_str(game_date)
                             else team_rest_days)
                state["last_team_game"] = date_to_str(game_date)
                advance_state_for_date(state, game_date, rest_days, config, staff)
                if state["availability_status"] != "active":
                    state["games_missed"] = int(state.get("games_missed") or 0) + 1
                    state["current_absence_games"] = int(state.get("current_absence_games") or 0) + 1
                    continue
                minutes = float(player.get("minutes_projection") or 0)
                if rest_on:
                    shutdown = state.get("rest_shutdown")
                    if shutdown and shutdown.get("team_id") != team["id"]:
                        state.pop("rest_shutdown", None)   # traded: his new team decides
                        shutdown = None
                    if shutdown:
                        state["games_rested"] = int(state.get("games_rested") or 0) + 1
                        continue
                    if team["id"] not in human_teams and minutes >= REST_MIN_MINUTES:
                        context = {**standings.get(team["id"], {}), "back_to_back": rest_days == 0 and bool(previous_game),
                                   "rested_tonight": rested_tonight.get((team["id"], game["externalGameId"]), 0),
                                   "regulars_out": regulars_out.get(team["id"], 0)}
                        decision = coach_rest_decision(player, state, context, rest_draw(seed, game["externalGameId"], player["id"]))
                        if decision:
                            kind, reason = decision
                            key = (team["id"], game["externalGameId"])
                            rested_tonight[key] = rested_tonight.get(key, 0) + 1
                            state["games_rested"] = int(state.get("games_rested") or 0) + 1
                            state.update({"rest_game_id": str(game["externalGameId"]), "rest_date": date_to_str(game_date),
                                          "rest_reason": reason})
                            if kind == "shutdown":
                                state["rest_shutdown"] = {"team_id": team["id"], "since": date_to_str(game_date), "reason": reason}
                            continue
                if int(state.get("return_absence_games") or 0) > 0:
                    advance_return_ramp(state, game_date, staff)
                if minutes < (im.MIN_MINUTES_FOR_EXPOSURE if model else 8):
                    continue
                stamina = traits.get((player["id"], "stamina_cardio"), 50.0)
                add_game_fatigue(state, player, minutes, stamina, rest_days, config, staff)
                rng = random.Random(f"{seed}:{game['externalGameId']}:{player['id']}:injury")
                if model:
                    # A player on a return-to-minutes ramp carries a lighter workload, so a careful coach lowers re-injury risk.
                    ramp = im.return_minutes_multiplier(int(state.get("return_absence_games") or 0),
                                                        int(state.get("games_since_return") or 0), rotation_star.get(team["id"], 3.0))
                    event = v2_injury_draw(root, model, canonical, player, traits, state, profiles.get(player["id"], {}),
                                           minutes * ramp, game_date, staff, seed, rng, history_cache, events)
                    if event:
                        # He plays tonight's game (leaving partway through when the injury happens during play); the
                        # absence starts with the team's next game (activated by advance_state_for_date).
                        if rng.random() < im.in_game_share(int(event["expected_days_missed"]), event["body_part"]):
                            event["in_game_exit"] = True
                            event["exit_share"] = round(rng.random(), 3)
                        event["plays_injury_game"] = True
                        events.append(event)
                        severity_counts[event["severity"]] = severity_counts.get(event["severity"], 0) + 1
                        body_counts[event["body_area"]] = body_counts.get(event["body_area"], 0) + 1
                        state["pending_injury"] = {key: event[key] for key in (
                            "id", "start_date", "return_date", "severity", "body_part", "diagnosis")}
                        state.update({
                            "source_ids": list(dict.fromkeys([*(state.get("source_ids") or []), "src_injury_model_v2"])),
                            "notes": f"{event['diagnosis']} on {date_to_str(game_date)}.",
                        })
                    continue
                risk = injury_risk_for_player(player, profiles.get(player["id"], {}), state, minutes, stamina, config, staff)
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
                            "games_missed": int(state.get("games_missed") or 0) + 1,
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
        # Fatigue recovers on the next game day (rest days are counted there); this pass only moves the calendar on.
        advance_state_for_date(state, through_day, 0, config, staff)
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
    # This function only reads its input. Avoid recursively copying every trait
    # and accumulated note on each monthly development checkpoint.
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    month = month[:7]
    traits = traits_by_player(canonical)
    states = {state["player_id"]: state for state in canonical.get("player_health_states", [])}
    coaches = coach_development_by_team(canonical)
    from .ratings_model import uses_inputs_model
    volatility = DEVELOPMENT_SEASON_VOLATILITY if uses_inputs_model(canonical) else LEGACY_DEVELOPMENT_SEASON_VOLATILITY
    events: list[dict[str, Any]] = []
    for player in canonical.get("players", []):
        if player.get("_inactive_player"):
            continue
        age = maybe_float(player.get("age"))
        minutes = float(player.get("minutes_projection") or 0)
        if not should_generate_development_event(player, age, minutes):
            continue
        staff = development_staff_modifiers(canonical, player["team_id"], coaches.get(player["team_id"], 3.0))
        state = states.get(player["id"], {})
        health_drag = development_health_drag(state)
        deltas: dict[str, float] = {}
        focus = development_trait_focus(player, staff, traits.get(player["id"], {}), seed, month)
        for trait_key in DEVELOPMENT_TRAITS:
            current = float(traits.get(player["id"], {}).get(trait_key, {}).get("value", 50.0))
            trait_context = (traits.get(player["id"], {}).get(trait_key, {}).get("components") or {}).get("career_capacity")
            delta = monthly_trait_delta(player, trait_key, current, age, minutes, staff, health_drag, seed, month, float(focus.get(trait_key, 0.32)), trait_context,
                                        season_volatility=volatility)
            if abs(delta) >= 0.015:
                deltas[trait_key] = round(delta, 3)
        # An evaluated plateau is still a processed player-month. Keep the
        # sparse delta threshold, but do not make it look like a skipped month.
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
            notes=("Monthly evaluation completed with no reportable trait movement."
                   if not deltas else "Monthly trait movement from age, role/minutes, staff, current trait level, health, and stable prospect upside/realization/timing. Personality is intentionally deferred."),
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
        player_events = events_by_player.get(player_id, [])
        active_event = active_injury_event_on_date(player_events, game_day)
        if active_event:
            continue
        if ((state or {}).get("rest_game_id") and (state or {}).get("rest_date") == game_date[:10]) or (state or {}).get("rest_shutdown"):
            continue   # the coach rests him tonight, or has shut him down (AI teams; coach_rest_decision)
        has_event_history = bool(player_events)
        if state and not has_event_history and not player_available_on_date(state, game_day):
            continue
        status = "active" if has_event_history else (state or {}).get("availability_status", "active")
        fatigue = float((state or {}).get("fatigue") or 0.0)
        rust = float((state or {}).get("rust") or 0.0) if state else 0.0
        extra = {}
        hurt = injury_game_event_on_date(player_events, game_day)
        if hurt and hurt.get("in_game_exit"):
            # Hurt during tonight's game: he leaves after this share of his minutes (game_minutes.manage_game_minutes).
            extra = {"health_injury_exit": float(hurt.get("exit_share") or 0.0), "health_injury_label": hurt.get("diagnosis")}
        adjusted.append({**item, "health_fatigue": round(fatigue, 2), "health_rust": round(rust, 2), "health_status": status,
                         "health_return_absence": int((state or {}).get("return_absence_games") or 0),
                         "health_games_since_return": int((state or {}).get("games_since_return") or 0), **extra})
    return adjusted


def active_injury_event_on_date(events: list[dict[str, Any]], game_day: date) -> dict[str, Any] | None:
    for event in events:
        start = event.get("start_date")
        end = event.get("return_date")
        if not start or not end:
            continue
        if parse_date(start) <= game_day < parse_date(end):
            if event.get("plays_injury_game") and parse_date(start) == game_day:
                continue   # hurt in (or after) tonight's game: he still plays it
            return event
    return None


def injury_game_event_on_date(events: list[dict[str, Any]], game_day: date) -> dict[str, Any] | None:
    """The injury a player suffers in tonight's game, if any."""
    for event in events:
        if event.get("plays_injury_game") and event.get("start_date") and parse_date(event["start_date"]) == game_day:
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


V2_FATIGUE_SLOPE = 1.0 / 140.0   # extra risk per fatigue point above 25 (back-to-backs, heavy recent minutes)


def v2_injury_draw(root, model, canonical, player, traits, state, profile, minutes, game_date, staff, seed, rng,
                   history_cache, new_events) -> dict[str, Any] | None:
    """One game's injury draw under the per-body-part model. Returns the injury event dict, or None."""
    from . import injury_model as im
    pid = player["id"]
    if pid not in history_cache:
        history_cache[pid] = im.player_history(model, pid, canonical.get("injury_events", []))
    history = history_cache[pid] + [(parse_date(e["start_date"]), e["body_part"]) for e in new_events
                                    if e.get("player_id") == pid and e.get("body_part") != "illness"]
    player_traits = {key: traits.get((pid, key), 50.0) for key in ("rim_pressure", "offensive_rebounding", "stamina_cardio")}
    hazards = im.part_hazards(model, player, player_traits, minutes, history, game_date)
    scale = im.LEAGUE_RATE_SCALE * float(staff.get("injury_risk_multiplier", 1.0))
    scale *= 1.0 + max(0.0, float(state.get("fatigue") or 0.0) - 25.0) * V2_FATIGUE_SLOPE
    if profile.get("injury_prone"):
        scale *= 1.22   # generated prospects' medical flag (real players' history is already in the model)
    total = sum(hazards.values()) * scale
    if rng.random() >= min(0.25, total):
        return None
    marker, running, part = rng.random() * sum(hazards.values()), 0.0, "ankle"
    for name, value in sorted(hazards.items()):
        running += value
        if marker <= running:
            part = name
            break
    case = im.sample_recovery(root, part, rng)
    personal = 1.0 + float((model.get("player_recovery_pct") or {}).get(pid, 0.0)) / 100.0
    days = max(1, int(round(int(case.get("days") or 1) * personal * float(staff.get("recovery_days_multiplier", 1.0)))))
    return_day = im.basketball_return_date(game_date, days)
    severity = im.severity_for_days(days)
    label = str(case.get("label") or f"{part} injury")
    area = im.PART_AREA.get(part, "head_illness")
    lasting = im.lasting_effect(model, label, part)
    recurrence = any(p == part and (game_date - d).days <= 548 for d, p in history)
    event = to_plain(InjuryEvent(
        id=stable_id("injury", "v2", pid, date_to_str(game_date), part, label, seed),
        player_id=pid, team_id=player["team_id"], start_date=date_to_str(game_date), return_date=date_to_str(return_day),
        body_area=area, severity=severity, expected_days_missed=days,
        expected_games_missed=expected_games_from_days((return_day - game_date).days),
        recurrence=recurrence, status="generated_injury_v2", source_ids=["src_injury_model_v2"],
        notes=f"{label} ({im.PART_LABELS.get(part, part)}); duration from a real {part} absence.",
    ))
    event.update({"body_part": part, "diagnosis": label, "surgery": int(case.get("surgery") or 0),
                  "lasting_rapm_change": round(lasting, 3)})
    return event


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
    if state.get("rest_date") and state["rest_date"] < date_to_str(game_date):
        for key in ("rest_game_id", "rest_date", "rest_reason"):   # last night's rest is over
            state.pop(key, None)
    pending = state.get("pending_injury")
    if pending and parse_date(pending["start_date"]) < game_date:
        activate_pending_injury(state)
    return_date = state.get("return_date")
    if state.get("current_injury_id") and return_date and parse_date(return_date) <= game_date:
        state["current_injury_id"] = None
        state["availability_status"] = "active"
        state["return_date"] = None
        for key in ("current_injury_severity", "current_injury_part", "current_injury_label"):
            state.pop(key, None)
        absence = int(state.pop("current_absence_games", 0) or 0)
        if absence > 0:
            from .injury_model import return_rust
            state["return_absence_games"] = absence
            state["games_since_return"] = 0
            state["return_rust"] = return_rust(absence)
            state["rust"] = state["return_rust"]
    if state.get("availability_status") == "active" and float(state.get("rust") or 0.0) > 0 and state.get("return_rust") is None:
        # Older states: rust fades by the calendar. Returns from injury now fade it per game played (advance_return_ramp).
        state["rust"] = round(max(0.0, float(state.get("rust") or 0.0) - float(tuning.get("rust_decay_per_game", 7.5)) / max(float(staff.get("recovery_days_multiplier", 1.0)), 0.2)), 2)


def activate_pending_injury(state: dict[str, Any]) -> None:
    """The injury from his last game: the absence starts now (he played the game he was hurt in). Called on the next
    health pass, or by the save right after the day's games so the injury shows at once."""
    pending = state.pop("pending_injury", None)
    if not pending:
        return
    for key in ("return_absence_games", "games_since_return", "return_rust", "ramp_last_game", "rest_suggestion"):
        state.pop(key, None)
    state.update({
        "current_injury_id": pending["id"], "availability_status": "out", "return_date": pending["return_date"],
        "current_injury_severity": pending["severity"], "current_injury_part": pending["body_part"],
        "current_injury_label": pending["diagnosis"], "rust": 0.0, "current_absence_games": 0,
    })


def advance_return_ramp(state: dict[str, Any], game_date: date, staff: dict[str, float]) -> None:
    """A game day for a player back from an absence: count the games he has played since returning (not counting
    tonight's), and set tonight's rust. Rust fades with each game played, faster with a better recovery planner; the
    minutes limit (sim.return_ramped_player_pool) follows the same count."""
    from .injury_model import RUST_DECAY_PER_GAME, return_ramp_length
    today = date_to_str(game_date)
    last = state.get("ramp_last_game")
    if last and last < today:
        state["games_since_return"] = int(state.get("games_since_return") or 0) + 1
    played = int(state.get("games_since_return") or 0)
    if played >= return_ramp_length(int(state["return_absence_games"])):
        for key in ("return_absence_games", "games_since_return", "return_rust", "ramp_last_game"):
            state.pop(key, None)
        state["rust"] = 0.0
        return
    state["ramp_last_game"] = today
    decay = RUST_DECAY_PER_GAME / max(float(staff.get("recovery_days_multiplier", 1.0)), 0.2)
    state["rust"] = round(max(0.0, float(state.get("return_rust") or 0.0) - decay * played), 2)


# ---- Coach rest and load management (INJURY-REST, 2026-11-19) ------------------------------------------------------
# AI coaches sit healthy regulars on some nights. Fitted to real 2025-26 box scores (output/injury-rest/real_rest.py):
# players averaging 25+ minutes missed 3.2% of their team's games as single-game absences (7.2% on the second night
# of a back-to-back, 2.4% otherwise), rising with age (back-to-backs: 5% under 25, 7% at 25-29, 10% at 30-33, 11% at
# 34+) and late in the season (last 15 games: 4-5% vs 3%); minutes played made no difference among regulars. The
# chances below are those rates minus the one-game injury and illness absences the injury model already produces.
# The box scores rarely say why (most inactive players are not listed), so the "other nights" chance also stands in
# for one-game absences that never reach an injury report: personal reasons, minor knocks, suspensions.
# Rules from the league's player participation policy (2023): a team rests at most one regular in a game (outside the
# last two games), and a player stays on course for the 65 games that award eligibility needs.
REST_MIN_MINUTES = 24.0
# (age upper bound, chance on the second night of a back-to-back, chance on other nights)
REST_BY_AGE = ((24.99, 0.050, 0.011), (29.99, 0.070, 0.016), (33.99, 0.095, 0.031), (99.0, 0.11, 0.032))
REST_RETURNING_BACK_TO_BACK = 0.15   # judgment: teams often keep a player just back from injury out of back-to-backs
REST_LATE_GAMES = 15                 # the stretch run: every team rests a little more
REST_LATE_EXTRA = 0.03
REST_LATE_TOP_EXTRA = 0.008          # teams with a playoff spot secured (top 8 records) a little more again
# Last two games: regulars sit (real 2025-26: 60% of the best eight teams' regulars and 46% of the middle teams' sat at
# least one of their final games). Winning teams rest for the playoffs; the others because little is left to play for.
REST_FINAL_GAMES = 2
REST_FINAL_PLAYOFF = 0.35
REST_FINAL_OTHERS = 0.25
REST_FINAL_MIN_WIN_PCT = 0.5
REST_MISSED_LIMIT = 14               # no rest nights once a player has missed this many games (65-game rule)
REST_MAX_PER_GAME = 1
REST_SHORT_HANDED = 3                # no rest nights while this many regulars are already out injured
# Teams out of the race shut players down: in real 2025-26 the eight worst teams' regulars sat an average of 6.8 of
# the final games (74% sat at least one, 46% five or more) against about 1 for other teams.
SHUTDOWN_BOTTOM_TEAMS = 8
SHUTDOWN_GAMES_LEFT = 25
SHUTDOWN_HAZARD = 0.03
REGULAR_SEASON_GAMES = 82


def league_rest_context(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per team: games left, league rank by winning percentage (1 = best) and winning percentage, from the save's
    standings."""
    records = canonical.get("save_team_records") or {}
    rows = []
    for team_id, record in records.items():
        wins, losses = int(record.get("wins") or 0), int(record.get("losses") or 0)
        played = wins + losses
        rows.append((team_id, wins / played if played else 0.5, played))
    order = sorted(rows, key=lambda row: (-row[1], row[0]))
    return {team_id: {"games_left": max(0, REGULAR_SEASON_GAMES - played), "win_pct": pct, "rank": rank + 1, "teams": len(order)}
            for rank, (team_id, pct, played) in enumerate(order)}


def rest_draw(seed: int, game_id: Any, player_id: str) -> float:
    return random.Random(f"{seed}:{game_id}:{player_id}:coach-rest").random()


def rest_chance(player: dict[str, Any], state: dict[str, Any], context: dict[str, Any]) -> tuple[float, str, str]:
    """Chance the coach sits this healthy regular tonight, the kind ("rest" or "shutdown") and the reason in words."""
    games_left = int(context.get("games_left") if context.get("games_left") is not None else REGULAR_SEASON_GAMES)
    teams = int(context.get("teams") or 30)
    rank = int(context.get("rank") or teams // 2)
    age = float(player.get("age") or 27.0)
    if games_left <= SHUTDOWN_GAMES_LEFT and rank > teams - SHUTDOWN_BOTTOM_TEAMS and games_left > 0:
        return SHUTDOWN_HAZARD, "shutdown", "shut down for the rest of the season (team out of the race)"
    if int(state.get("games_missed") or 0) + int(state.get("games_rested") or 0) >= REST_MISSED_LIMIT:
        return 0.0, "rest", ""
    if games_left <= REST_FINAL_GAMES:
        if float(context.get("win_pct") or 0.0) >= REST_FINAL_MIN_WIN_PCT:
            return REST_FINAL_PLAYOFF, "rest", "rest before the playoffs"
        return REST_FINAL_OTHERS, "rest", "rest in the season's final games"
    if int(context.get("rested_tonight") or 0) >= REST_MAX_PER_GAME or int(context.get("regulars_out") or 0) >= REST_SHORT_HANDED:
        return 0.0, "rest", ""
    b2b_chance, other_chance = next((b, o) for limit, b, o in REST_BY_AGE if age <= limit)
    if context.get("back_to_back"):
        chance, reason = b2b_chance, "second night of a back-to-back"
        if int(state.get("return_absence_games") or 0) > 0:
            chance, reason = chance + REST_RETURNING_BACK_TO_BACK, "back-to-back soon after returning from injury"
    else:
        chance, reason = other_chance, "maintenance day"
    if games_left <= REST_LATE_GAMES:
        chance += REST_LATE_EXTRA + (REST_LATE_TOP_EXTRA if rank <= 8 else 0.0)
        if not context.get("back_to_back"):
            reason = "rest during the stretch run"
    return chance, "rest", reason


def coach_rest_decision(player: dict[str, Any], state: dict[str, Any], context: dict[str, Any], draw: float) -> tuple[str, str] | None:
    chance, kind, reason = rest_chance(player, state, context)
    return (kind, reason) if chance > 0 and draw < chance else None


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


@lru_cache(maxsize=8192)
def _development_season_form(seed: int, player_id: str, season: int) -> float:
    rng = random.Random(f"{seed}:{player_id}:{season}:development_season")
    return clamp(rng.gauss(0.0, 1.0), -2.5, 2.5)


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
    focus_multiplier: float = 1.0,
    trait_context: dict[str, Any] | None = None,
    expected: bool = False,
    season_volatility: float | None = None,
) -> float:
    """Change in one hidden rating over a month. Expected changes omit season form and monthly noise."""
    age = 27.0 if age is None else age
    age_factor = development_age_factor(age, player=player, seed=seed)
    role_factor = clamp(minutes / 24.0, 0.18, 1.18)
    if player.get("rotation_priority") == "development_priority":
        role_factor *= 1.16
    if player.get("rotation_priority") == "fringe":
        role_factor *= 0.72
    cap_room = clamp((92.0 - current) / 42.0, 0.08, 1.0)
    focus_multiplier = clamp(focus_multiplier, 0.12, 1.45)
    upside_multiplier = development_upside_multiplier(player, seed)
    realization = prospect_development_realization(player, seed)
    ceiling = trait_ceiling(player, trait_key, trait_context, realization, seed) if trait_context else None
    learning = 0.0
    raw_learning = 0.0
    window = 0.0
    if ceiling is not None and age < 30:
        potential = float(trait_context["potential"])
        fulfillment = clamp((realization - .8) / .48, 0, 1)
        aptitude = clamp((float(trait_context["aptitude"]) - .35) / .7, 0, 1)
        learning = clamp((potential - 70) / 20, 0, 1) * fulfillment * aptitude
        raw_learning = (clamp((potential - float(trait_context["ability"]) - 30) / 15, 0, 1)
                        * clamp((potential - 75) / 15, 0, 1)
                        * clamp((realization - .8) / .32, 0, 1) * aptitude)
        # Promising skills need a runway into the mid/late twenties. Limited
        # game minutes reduce learning, but do not eliminate practice growth.
        window = .4 if age <= 23 else 1.0 if age <= 26 else .75 if age <= 28 else .3
        age_factor += .75 * learning * window
        if learning:
            role_factor = max(role_factor, min(.55, .18 + .5 * learning + .4 * raw_learning))
    growth_rate = 0.20
    youth_boost = 0.24 if trait_key in OFFENSIVE_AGING_TRAITS else 0.14
    if ceiling is not None:
        # A drafted prospect's career capacity adds its own ceiling and practice runway below. It used to replace
        # the youth curve entirely, so generated rookies grew more slowly than real rookies of the same age once
        # they played. Now the youth growth arrives with real minutes (Basketball Index: early gains are tied to
        # opportunity; low-minute young players gain less and less consistently).
        youth_boost *= clamp((minutes - 6.0) / 14.0, 0.0, 1.0)
    growth_rate += youth_boost * clamp((24.0 - age) / 2.0, 0.0, 1.0)
    growth = growth_rate * age_factor * role_factor * cap_room * float(staff.get("development_multiplier", 1.0)) * float(staff.get("patience_multiplier", 1.0)) * focus_multiplier * upside_multiplier
    if ceiling is not None:
        entry = float(trait_context["entry_value"])
        growth *= clamp((ceiling - current) / max(2, (ceiling - entry) * .30), 0, 1)
        elite = clamp((float(trait_context["potential"]) - 80) / 15, 0, 1)
        fulfillment = clamp((realization - .8) / .48, 0, 1)
        aptitude = clamp((float(trait_context["aptitude"]) - .35) / .7, 0, 1)
        growth *= 1 + .45 * elite * fulfillment * aptitude + 1.25 * learning
        # Raw high-upside players have farther to travel than ready-made picks;
        # learn toward their own skill capacity, never a draft-slot OVR target.
        growth += (max(0.0, ceiling - current) * .05 * raw_learning * window
                   * role_factor * focus_multiplier * float(staff.get("development_multiplier", 1.0))
                   * float(staff.get("patience_multiplier", 1.0)))
    health_penalty = health_drag * (0.04 if trait_key in PHYSICAL_TRAITS else 0.022)
    if age <= 30:
        # Short injuries interrupt development; they should not permanently
        # reverse a young player's skill curve by themselves.
        growth -= min(max(0.0, growth) * 0.88, health_penalty)
    else:
        growth -= health_penalty
    if trait_key in OFFENSIVE_AGING_TRAITS:
        growth -= min(0.45, 0.033 * max(0.0, age - 25.5) + 0.030 * max(0.0, age - 32.0))
    elif trait_key in PHYSICAL_TRAITS:
        growth -= min(0.36, 0.021 * max(0.0, age - 28.5) + 0.028 * max(0.0, age - 32.0))
    elif trait_key not in EXPERIENCE_TRAITS:
        growth -= min(0.24, 0.019 * max(0.0, age - 29.5) + 0.022 * max(0.0, age - 32.0))
    noise = 0.0
    season_change = 0.0
    if not expected:
        rng = random.Random(f"{seed}:{month}:{player['id']}:{trait_key}:development")
        noise_scale = 0.012 if ceiling is not None else 0.008
        noise = rng.gauss(0.0, noise_scale * (1.0 + focus_multiplier))
        season = int(month[:4]) - (int(month[5:7]) < 7)
        form = _development_season_form(seed, player["id"], season)
        last_form = _development_season_form(seed, player["id"], season - 1)
        earlier_form = _development_season_form(seed, player["id"], season - 2)
        # Fade past form over two years. The three weights sum to zero, so
        # the draws themselves do not accumulate without bound.
        volatility = DEVELOPMENT_SEASON_VOLATILITY if season_volatility is None else season_volatility
        season_change = volatility * (form - 0.65 * last_form - 0.35 * earlier_form)
        # Role and form move game execution more than conditioning or reads.
        season_change *= SEASON_FORM_TRAIT_WEIGHTS.get(trait_key, 1.0)
        if ceiling is not None:
            # Drafted prospects get full good and bad years once they play real minutes (it was 16% of the
            # league's swing): real draftees' three-year changes run from clear regressions to huge jumps.
            # A prospect who barely plays has no form to show.
            season_change *= clamp((minutes - 6.0) / 14.0, 0.0, 1.0)
        elif player.get("rotation_priority") in {"fringe", "rookie_depth", "deep_rotation"}:
            season_change *= 0.45
    growth_cap = .36 + .45 * raw_learning if upside_multiplier > 1.0 else .24
    delta = min(growth + noise, growth_cap) + season_change
    if delta <= 0.0:
        return delta
    # Slow gains near the top of the stored scale before the writer's bound.
    delta *= clamp((100.0 - current) / 10.0, 0.0, 1.0)
    return min(delta, max(0.0, ceiling - current)) if ceiling is not None else delta


def development_upside_multiplier(player: dict[str, Any], seed: int) -> float:
    """Convert explicit prospect upside into stable career growth variance.

    Established players without draft upside metadata retain the calibrated
    1.0 multiplier. Prospects can become busts or breakouts, but the outcome is
    fixed by save seed and player id so reloads never reroll a career arc.
    """
    potential = maybe_float(player.get("potential"))
    ability = maybe_float(player.get("current_ability"))
    if potential is None or ability is None:
        return 1.0
    upside = max(0.0, potential - ability)
    base = clamp(0.75 + upside / 18.0, 0.65, 2.35)
    realization = prospect_development_realization(player, seed)
    # Only successful high-upside careers get extra headroom. Ordinary and
    # low-realization prospects keep their existing development rates.
    elite_upside = clamp((potential - 65.0) / 20.0, 0.0, 1.0)
    fulfillment = clamp((realization - 0.80) / 0.48, 0.0, 1.0)
    headroom = 1.0 + 0.85 * elite_upside * fulfillment
    return round(min(clamp(base * realization, 0.45, 2.8) * headroom, 3.8), 4)


def prospect_development_realization(player: dict[str, Any], seed: int) -> float:
    marker = int(
        hashlib.sha256(f"{seed}:{player.get('id')}:development_realization".encode("utf-8")).hexdigest()[:8],
        16,
    ) / 0xFFFFFFFF
    if marker < 0.12:
        return 0.55
    elif marker < 0.30:
        return 0.80
    elif marker < 0.78:
        return 1.0
    elif marker < 0.94:
        return 1.12
    return 1.28


def development_trait_focus(player: dict[str, Any], staff: dict[str, Any], player_traits: dict[str, Any], seed: int, month: str) -> dict[str, float]:
    position = str(player.get("position") or "").upper()
    archetype = str(player.get("primary_off_role") or player.get("archetype") or "").lower()
    age = maybe_float(player.get("age")) or 27.0
    minutes = maybe_float(player.get("minutes_projection")) or 0.0
    weights = {trait: 0.22 for trait in DEVELOPMENT_TRAITS}
    if "PG" in position or "guard" in archetype or "creator" in archetype:
        for trait in ["handle_pressure", "passing_reads", "release_speed", "shot_versatility"]:
            weights[trait] += 0.42
    if "SG" in position or "shooter" in archetype or "wing" in archetype:
        for trait in ["release_speed", "shooting_range", "shot_versatility", "foot_speed_lateral_agility"]:
            weights[trait] += 0.34
    if "SF" in position or "PF" in position or "forward" in archetype:
        for trait in ["defensive_effort", "foot_speed_lateral_agility", "portability", "rim_pressure"]:
            weights[trait] += 0.3
    if "C" in position or "big" in archetype:
        for trait in ["rim_deterrence", "offensive_rebounding", "screen_navigation", "scheme_iq"]:
            weights[trait] += 0.38
    if age <= 23:
        for trait in ["handle_pressure", "shot_versatility", "foot_speed_lateral_agility", "stamina_cardio", "scheme_iq"]:
            weights[trait] += 0.22
    elif age >= 31:
        for trait in ["scheme_iq", "passing_reads", "portability", "playoff_translation"]:
            weights[trait] += 0.26
        for trait in PHYSICAL_TRAITS:
            weights[trait] *= 0.72
    if minutes >= 26:
        for trait in ["stamina_cardio", "scheme_iq", "playoff_translation"]:
            weights[trait] += 0.18
    if float(staff.get("skill_development") or 60.0) >= 68:
        for trait in ["shooting_range", "shot_versatility", "handle_pressure", "rim_pressure"]:
            weights[trait] += 0.1
    if float(staff.get("feedback_clarity") or 60.0) >= 68:
        for trait in ["scheme_iq", "screen_navigation", "passing_reads", "portability"]:
            weights[trait] += 0.12
    rng = random.Random(f"{seed}:{month}:{player.get('id')}:development_focus")
    chosen = set()
    pool = list(DEVELOPMENT_TRAITS)
    for _ in range(4 if age <= 25 else 3):
        total = sum(weights[trait] for trait in pool)
        draw = rng.random() * total
        running = 0.0
        for trait in pool:
            running += weights[trait]
            if draw <= running:
                chosen.add(trait)
                pool.remove(trait)
                break
    output = {}
    for trait in DEVELOPMENT_TRAITS:
        value = 1.0 if trait in chosen else 0.2 + rng.random() * 0.18
        current = float((player_traits.get(trait) or {}).get("value", 50.0))
        if current >= 84:
            value *= 0.68
        output[trait] = round(value, 3)
    return output


def development_age_factor(age: float, *, player: dict[str, Any] | None = None, seed: int = 1) -> float:
    """Vary promising prospects' maturation, never delay veteran decline."""
    pace = 1.0
    if (player is not None and age < 30
            and maybe_float(player.get("current_ability")) is not None
            and (maybe_float(player.get("potential")) or 0) >= 70
            and prospect_development_realization(player, seed) >= 1.0):
        timing = int(hashlib.sha256(f"{seed}:{player.get('id')}:development_timing".encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
        if timing < 0.20:
            age, pace = age + 1.0, 1.12
        elif timing >= 0.80:
            age, pace = age - 2.0, 0.88
    if age <= 20:
        return 1.25 * pace
    if age <= 23:
        return pace
    if age <= 26:
        return 0.45 * pace
    if age <= 30:
        return 0.10 * pace
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
    if age is not None and age >= 31:
        return True
    if player.get("rotation_priority") == "development_priority":
        return True
    if minutes >= 16:
        return True
    if age is not None and age >= 33 and minutes >= 8:
        return True
    return False


def coach_development_by_team(canonical: dict[str, Any]) -> dict[str, float]:
    """Head coach's share of player development (stars, 3 = average).

    In a save the coach is the save's own head coach (player relations: locker room + communication), so hiring and
    firing matter (coaching overhaul 2026-11-18; this used to read a static real-name table). Save-less tools keep the
    reputation table."""
    heads = [slot for slot in canonical.get("gameplay_staff_slots", []) if slot.get("slot") == "head_coach" and slot.get("skill_traits")]
    if heads:
        out = {team["id"]: 3.0 for team in canonical.get("teams", [])}
        for slot in heads:
            skills, personality = slot.get("skill_traits") or {}, slot.get("personality_traits") or {}
            relations = (float(skills.get("locker_room", 60.0)) + float(personality.get("communication", 60.0))) / 2.0
            out[slot["team_id"]] = round(clamp(relations / 20.0, 0.0, 5.0), 3)
        return out
    try:
        from .sim import coach_ratings

        return {rating.team_id: float(rating.ratings.get("development", 3.0)) for rating in coach_ratings(canonical)}
    except Exception:
        return {team["id"]: 3.0 for team in canonical.get("teams", [])}


def schedule_games_in_range(
    root: Path,
    from_date: str,
    through_date: str,
    games: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if games is None:
        with (root / SCHEDULE_FILE).open("r", encoding="utf-8") as handle:
            games = json.load(handle).get("games", [])
    return sorted(
        [game for game in games if from_date <= str(game.get("gameDate") or "") <= through_date],
        key=lambda item: (item.get("gameDate") or "", item.get("externalGameId") or ""),
    )


def season_start_year_for_health_date(value: str) -> int:
    day = parse_date(value)
    return day.year if day.month >= 7 else day.year - 1


def rotation_players_by_team(canonical: dict[str, Any], min_minutes: float = 8.0, depth: int = 11) -> dict[str, list[dict[str, Any]]]:
    players_by_team: dict[str, list[dict[str, Any]]] = {}
    for player in canonical.get("players", []):
        if player.get("team_id") and not player.get("_inactive_player") and float(player.get("minutes_projection") or 0.0) >= min_minutes:
            players_by_team.setdefault(player["team_id"], []).append(player)
    for team_id, players in players_by_team.items():
        players_by_team[team_id] = sorted(players, key=lambda item: item.get("minutes_projection") or 0, reverse=True)[:depth]
    return players_by_team


def trait_lookup(canonical: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {
        (trait["player_id"], trait["trait_key"]): float(trait.get("value") if trait.get("value") is not None else 50.0)
        for trait in canonical.get("traits", [])
    }


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
        # The current injury's diagnosis, body part and severity while the player is out (v2 model); empty when healthy.
        **({key: state.get(key) for key in ("current_injury_severity", "current_injury_part", "current_injury_label")
            if state.get(key)} if state.get("current_injury_id") else {}),
        # Absence bookkeeping for the return-to-minutes ramp (kept only while it matters).
        **{key: int(state[key]) for key in ("current_absence_games", "return_absence_games", "games_since_return")
           if state.get(key) is not None and (key != "games_since_return" or state.get("return_absence_games"))},
        **({"return_rust": float(state["return_rust"])} if state.get("return_absence_games") and state.get("return_rust") is not None else {}),
        **({key: state[key] for key in ("last_team_game", "ramp_last_game", "pending_injury", "rest_game_id", "rest_date", "rest_reason",
                                         "games_rested", "rest_suggestion", "rest_shutdown")
            if state.get(key) is not None}),
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
