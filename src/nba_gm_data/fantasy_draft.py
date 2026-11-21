"""Fantasy-draft setup using the existing player and contract universe.

The fantasy draft is a save-creation phase, not an alternate simulation
engine. Players retain their canonical contracts, traits, health, age, and
development state. Only roster ownership changes when the final pick is made.
"""

from __future__ import annotations

import hashlib
import random
from copy import deepcopy
from typing import Any

from .schema import CANONICAL_START_DATE, to_plain
from .sim import player_feature_vector
from .transactions import build_player_asset_valuations, current_salary
from .utils import clamp, stable_id


FANTASY_DRAFT_VERSION = "fantasy_draft_v3"
FANTASY_PLAYER_PROFILE_VERSION = "fantasy_player_card_v2"
FANTASY_ROSTER_SIZE = 15
FANTASY_FEATURE_KEYS = (
    "impact",
    "shot_creation",
    "spacing",
    "passing",
    "rim_pressure",
    "rim_deterrence",
    "defensive_events",
    "offensive_rebounding",
    "playoff_translation",
)


def normalize_game_mode(value: Any) -> str:
    return "fantasy_draft" if str(value or "").strip().lower() == "fantasy_draft" else "standard"


def initialize_fantasy_draft(canonical: dict[str, Any] | Any, save: dict[str, Any], seed: int) -> dict[str, Any]:
    """Create a seeded snake draft and restore each franchise's own picks."""
    canonical = to_plain(canonical)
    teams = sorted(canonical.get("teams", []), key=lambda row: str(row.get("abbrev") or row.get("id") or ""))
    if len(teams) != 30:
        raise ValueError("Fantasy draft requires the complete 30-team league.")
    save.setdefault("meta", {})["game_mode"] = "fantasy_draft"
    profiles = fantasy_player_profiles(canonical, save)
    target_count = len(teams) * FANTASY_ROSTER_SIZE
    if len(profiles) < target_count:
        raise ValueError(f"Fantasy draft needs at least {target_count} eligible players; found {len(profiles)}.")
    pool = select_fantasy_pool(canonical, save, profiles, target_count)
    rng = random.Random(f"{int(seed)}:fantasy-draft-order")
    order = [team["id"] for team in teams]
    rng.shuffle(order)
    pick_team_ids: list[str] = []
    for round_index in range(FANTASY_ROSTER_SIZE):
        pick_team_ids.extend(order if round_index % 2 == 0 else list(reversed(order)))
    state = {
        "version": FANTASY_DRAFT_VERSION,
        "status": "in_progress",
        "seed": int(seed),
        "roster_size": FANTASY_ROSTER_SIZE,
        "team_order": order,
        "pick_team_ids": pick_team_ids,
        "current_pick_index": 0,
        "total_picks": len(pick_team_ids),
        "available_player_ids": [profile["player_id"] for profile in pool],
        "player_profiles": {profile["player_id"]: profile for profile in pool},
        "selections": [],
        "watchlists": {},
        "started_date": str((save.get("state") or {}).get("current_date") or CANONICAL_START_DATE),
        "completed_date": None,
    }
    save["fantasy_draft_state"] = state
    save.setdefault("state", {})["phase"] = "fantasy_draft"
    save["state"]["legal_actions"] = ["fantasy_draft_pick"]
    restore_original_draft_picks(canonical, save)
    return state


def fantasy_player_profiles(canonical: dict[str, Any], save: dict[str, Any]) -> list[dict[str, Any]]:
    valuations = {
        row.player_id: to_plain(row)
        for row in build_player_asset_valuations(canonical)
    }
    contracts = {row.get("player_id"): row for row in canonical.get("contracts", []) if row.get("player_id")}
    rating_priors = fantasy_overall_rating_priors(canonical)
    retired = set(save.get("retired_player_ids") or [])
    profiles: list[dict[str, Any]] = []
    for player in canonical.get("players", []):
        player_id = player.get("id")
        if not player_id or player_id in retired or player.get("_inactive_player"):
            continue
        valuation = valuations.get(player_id)
        if not valuation:
            continue
        contract = contracts.get(player_id) or {}
        seasons = [
            row
            for row in contract.get("seasons", [])
            if row.get("season") and row.get("salary") is not None
        ]
        features = player_feature_vector(canonical, player).features
        salary = current_salary(contract)
        profile = {
                "player_id": player_id,
                "name": player.get("name") or "Unknown Player",
                "position": player.get("position") or "",
                "age": round(float(player.get("age") or 27.0), 1),
                "height_inches": round(float(player.get("height_inches") or 0.0), 1),
                "original_team_id": player.get("team_id"),
                "minutes_projection": round(float(player.get("minutes_projection") or 0.0), 1),
                "player_value": float(valuation.get("player_value") or 1.0),
                "on_court_value": float(valuation.get("on_court_value") or 1.0),
                "contract_surplus": float(valuation.get("contract_surplus") or 0.0),
                "development_upside": float(valuation.get("development_upside") or 0.0),
                "playoff_value": float(valuation.get("playoff_value") or 50.0),
                "health_risk": float(valuation.get("health_risk") or 0.0),
                "salary_millions": round(float(salary or 0.0) / 1_000_000, 2),
                "contract_years": len(seasons),
                "impact": round(float(features.get("impact") or 50.0), 2),
                "ratings_prior_overall": round(float(rating_priors.get(player_id) or features.get("impact") or 50.0), 2),
                "features": {
                    key: round(float(features.get(key) or 50.0), 2)
                    for key in FANTASY_FEATURE_KEYS
                },
            }
        profile.update(fantasy_player_display_details(canonical, player, contract, profile))
        profiles.append(profile)
    return profiles


def fantasy_player_display_details(
    canonical: dict[str, Any],
    player: dict[str, Any],
    contract: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Build the explanatory layer used by fantasy boards and player cards.

    The asset model's ``development_upside`` is a value signal, not literal
    future OVR. This projection translates age, present rating, role, and that
    signal into a conservative three-year range without changing development
    simulation outcomes.
    """
    from .save import (
        cap_lines_for_season,
        player_attribute_summary,
        player_display_attribute_summary,
        RATING_SCALE,
    )

    player_id = str(player.get("id") or profile.get("player_id") or "")
    engine_attrs = player_attribute_summary(canonical, player_id)
    display_attrs = player_display_attribute_summary(canonical, player_id)
    reviewed_prior = float(profile.get("ratings_prior_overall") or engine_attrs.get("overall") or 50.0)
    engine_overall = float(engine_attrs.get("overall") or 50.0)
    engine_impact = float(profile.get("impact") or 50.0)
    reconciled_quality = engine_overall * 0.72 + reviewed_prior * 0.28
    # A proven elite impact profile may recover more of the reviewed scouting
    # prior. Merely having an old high prior is insufficient after a manual
    # calibration lowers the player's present two-way impact.
    draft_quality_rating = min(
        reviewed_prior,
        reconciled_quality + max(0.0, engine_impact - 76.0) * 4.0,
    )
    trait_values = {
        str(row.get("trait_key")): round(float(row.get("value") or 50.0), 1)
        for row in canonical.get("traits", [])
        if row.get("player_id") == player_id and row.get("trait_key")
    }
    start_year = int(str(CANONICAL_START_DATE)[:4])
    salaries = {
        str(row.get("season")): float(row.get("salary") or 0.0) / 1_000_000
        for row in contract.get("seasons", [])
        if row.get("season")
    }
    contract_seasons = []
    for offset in range(4):
        year = start_year + offset
        season = f"{year}-{str(year + 1)[-2:]}"
        lines = cap_lines_for_season(season)
        contract_seasons.append(
            {
                "season": season,
                "salary_millions": round(salaries.get(season, 0.0), 2),
                "hard_cap_millions": round(float(lines["hard_cap"]) / 1_000_000, 2),
            }
        )
    outlook = fantasy_growth_outlook(
        {
            **profile,
            "engine_overall": float(engine_attrs.get("overall") or 50.0),
            "display_overall": float(display_attrs.get("overall") or 50.0),
        },
        canonical,
    )
    return {
        "profile_version": FANTASY_PLAYER_PROFILE_VERSION,
        "rating_scale": RATING_SCALE,
        "engine_overall": round(float(engine_attrs.get("overall") or 50.0), 1),
        "display_overall": round(float(display_attrs.get("overall") or 50.0), 1),
        "draft_quality_rating": round(draft_quality_rating, 2),
        "ratings": display_attrs,
        "engine_ratings": engine_attrs,
        "trait_ratings": trait_values,
        "contract_seasons": contract_seasons,
        "growth_outlook": outlook,
        "ceiling_overall": outlook["ceiling_overall"],
        "growth_runway": outlook["high_end_growth"],
    }


def ensure_fantasy_profile_details(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    """Backfill richer profile data into drafts created before player cards."""
    state = save.get("fantasy_draft_state") or {}
    profiles = state.get("player_profiles") or {}
    if not profiles or all(row.get("profile_version") == FANTASY_PLAYER_PROFILE_VERSION for row in profiles.values()):
        return
    players = {str(row.get("id")): row for row in canonical.get("players", []) if row.get("id")}
    contracts = {str(row.get("player_id")): row for row in canonical.get("contracts", []) if row.get("player_id")}
    for player_id, profile in profiles.items():
        if profile.get("profile_version") == FANTASY_PLAYER_PROFILE_VERSION:
            continue
        player = players.get(str(player_id))
        if not player:
            continue
        profile.update(fantasy_player_display_details(canonical, player, contracts.get(str(player_id)) or {}, profile))


def fantasy_growth_outlook(profile: dict[str, Any], canonical: dict[str, Any] | None = None) -> dict[str, Any]:
    """Translate value upside into an intelligible good-situation OVR range.

    ``development_upside`` remains the engine's 0-22 asset-value signal. The
    returned OVR growth is a three-year scouting estimate, not guaranteed
    progression; health, staff, minutes, trait caps, and deterministic career
    realization still decide what actually occurs in a save.
    """
    age = float(profile.get("age") or 27.0)
    has_engine_rating = profile.get("engine_overall") is not None
    engine_overall = clamp(
        float(profile.get("engine_overall") or profile.get("display_overall") or profile.get("ratings_prior_overall") or profile.get("impact") or 50.0),
        1.0,
        99.0,
    )
    # The one display scale has no cap (OVERALL-SCALE, 2026-11-21); only the engine-scale number above is bounded.
    display_overall = max(1.0, float(profile.get("display_overall") or engine_overall))
    minutes = clamp(float(profile.get("minutes_projection") or 0.0), 0.0, 36.0)
    value_signal = clamp(float(profile.get("development_upside") or 0.0), 0.0, 22.0)
    age_runway = {
        19: 5.0,
        20: 4.6,
        21: 4.2,
        22: 3.7,
        23: 3.2,
        24: 2.6,
        25: 1.8,
        26: 1.1,
        27: 0.5,
    }.get(int(age), 5.0 if age < 19 else 0.0)
    headroom = clamp((103.0 - engine_overall) / 28.0, 0.28, 1.08)
    signal_multiplier = 0.74 + (value_signal / 22.0) * 0.46
    role_multiplier = 0.88 + (minutes / 36.0) * 0.12
    high_end_growth = clamp(age_runway * headroom * signal_multiplier * role_multiplier, 0.0, 5.0)
    likely_growth = high_end_growth * (0.48 + min(minutes, 30.0) / 250.0)
    engine_ceiling = clamp(engine_overall + high_end_growth, engine_overall, 99.0)
    if has_engine_rating:
        from .save import display_rating_from_summary

        # Growth is worked out on the engine's scale, then shown as the matching change on the display scale, starting
        # from the player's own displayed OVR (the same number as his card).
        def shown(value: float) -> float:
            return display_rating_from_summary(canonical, "overall", value)

        displayed_high_end_growth = max(0.0, shown(engine_ceiling) - shown(engine_overall))
        ceiling = display_overall + displayed_high_end_growth
        likely_engine_overall = clamp(engine_overall + likely_growth, engine_overall, 99.0)
        displayed_likely_growth = max(0.0, shown(likely_engine_overall) - shown(engine_overall))
    else:
        ceiling = engine_ceiling
        displayed_high_end_growth = high_end_growth
        displayed_likely_growth = likely_growth
    if high_end_growth >= 3.5:
        label = "High runway"
    elif high_end_growth >= 2.0:
        label = "Meaningful runway"
    elif high_end_growth >= 0.8:
        label = "Some runway"
    elif age <= 27:
        label = "Near present level"
    else:
        label = "Prime or decline phase"
    return {
        "horizon_years": 3,
        "likely_growth": round(displayed_likely_growth, 1),
        "high_end_growth": round(displayed_high_end_growth, 1),
        "ceiling_overall": round(ceiling, 1),
        "engine_likely_growth": round(likely_growth, 1),
        "engine_high_end_growth": round(high_end_growth, 1),
        "engine_ceiling_overall": round(engine_ceiling, 1),
        "label": label,
        "value_signal": round(value_signal, 1),
        "explanation": "Good-situation three-year estimate; minutes, staff, health, trait caps, and career realization can move the result.",
    }


def fantasy_overall_rating_priors(canonical: dict[str, Any]) -> dict[str, float]:
    """Recover the reviewed OVR prior retained in calibrated trait provenance."""
    values: dict[str, float] = {}
    for trait in canonical.get("traits", []):
        player_id = trait.get("player_id")
        calibration = (trait.get("components") or {}).get("league_trait_rating_calibration") or {}
        for nudge in calibration.get("composite_nudges") or []:
            if nudge.get("column") == "OVR" and nudge.get("csv_value") is not None:
                values[str(player_id)] = float(nudge["csv_value"])
                break
    return values


def select_fantasy_pool(
    canonical: dict[str, Any],
    save: dict[str, Any],
    profiles: list[dict[str, Any]],
    target_count: int,
) -> list[dict[str, Any]]:
    """Keep every active roster player, then fill any source-data gap by value."""
    roster_overrides = save.get("roster_overrides") or {}
    free_agents = set(save.get("free_agent_player_ids") or [])
    players = {row.get("id"): row for row in canonical.get("players", []) if row.get("id")}
    active_ids = {
        player_id
        for player_id, player in players.items()
        if roster_overrides.get(player_id, player.get("team_id")) and player_id not in free_agents
    }
    ranked = sorted(
        profiles,
        key=lambda row: (
            row["player_value"],
            row["on_court_value"],
            row["minutes_projection"],
            row["name"],
        ),
        reverse=True,
    )
    selected = [row for row in ranked if row["player_id"] in active_ids]
    selected_ids = {row["player_id"] for row in selected}
    if len(selected) < target_count:
        selected.extend(row for row in ranked if row["player_id"] not in selected_ids)
    selected = selected[:target_count]
    return sorted(
        selected,
        key=lambda row: (row["player_value"], row["on_court_value"], row["name"]),
        reverse=True,
    )


def restore_original_draft_picks(canonical: dict[str, Any], save: dict[str, Any]) -> dict[str, int]:
    """Give every team one own R1 and R2 in every modeled draft year."""
    teams = sorted(canonical.get("teams", []), key=lambda row: str(row.get("id") or ""))
    years = sorted(
        {
            str(pick.get("season"))
            for pick in canonical.get("draft_picks", [])
            if str(pick.get("season") or "").isdigit()
        }
    )
    if not years:
        years = ["2026", "2027", "2028", "2029", "2030"]
    overrides: dict[str, str] = {
        str(pick["id"]): "used_draft_pick"
        for pick in canonical.get("draft_picks", [])
        if pick.get("id")
    }
    generated = {
        row.get("id"): deepcopy(row)
        for row in save.get("generated_draft_picks", [])
        if row.get("id")
    }
    all_picks = [*canonical.get("draft_picks", []), *generated.values()]
    restored = 0
    created = 0
    for year in years:
        for team in teams:
            for round_number in (1, 2):
                candidates = sorted(
                    [
                        pick
                        for pick in all_picks
                        if str(pick.get("season")) == year
                        and int(pick.get("round") or 0) == round_number
                        and pick.get("original_team_id") == team["id"]
                    ],
                    key=lambda pick: (
                        "gameplay-fallback" in str(pick.get("id") or ""),
                        str(pick.get("id") or ""),
                    ),
                )
                if candidates:
                    pick = candidates[0]
                else:
                    pick_id = stable_id("fantasy_own_pick", year, round_number, team["id"])
                    pick = {
                        "id": pick_id,
                        "season": year,
                        "round": round_number,
                        "original_team_id": team["id"],
                        "current_owner_team_id": team["id"],
                        "status": "fantasy_draft_restored_own_pick",
                        "confidence": 1.0,
                        "source_ids": ["src_fantasy_draft_v1"],
                        "notes": "Own pick created for an even fantasy-draft asset ledger.",
                    }
                    generated[pick_id] = pick
                    all_picks.append(pick)
                    created += 1
                overrides[str(pick["id"])] = str(team["id"])
                restored += 1
    save["generated_draft_picks"] = sorted(generated.values(), key=lambda row: str(row.get("id") or ""))
    save["draft_pick_overrides"] = overrides
    save["pick_obligations"] = []
    save["locked_pick_assets"] = []
    save["draft_rights"] = []
    return {"restored": restored, "created": created}


def fantasy_draft_current_team_id(save: dict[str, Any]) -> str | None:
    state = save.get("fantasy_draft_state") or {}
    index = int(state.get("current_pick_index") or 0)
    picks = state.get("pick_team_ids") or []
    if state.get("status") != "in_progress" or index >= len(picks):
        return None
    return str(picks[index])


def fantasy_draft_pick_number(save: dict[str, Any]) -> int:
    return int((save.get("fantasy_draft_state") or {}).get("current_pick_index") or 0) + 1


def fantasy_draft_team_roster(save: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    state = save.get("fantasy_draft_state") or {}
    profiles = state.get("player_profiles") or {}
    return [
        profiles[row["player_id"]]
        for row in state.get("selections") or []
        if row.get("team_id") == team_id and row.get("player_id") in profiles
    ]


def fantasy_draft_candidate_score(save: dict[str, Any], team_id: str, player_id: str) -> float:
    state = save.get("fantasy_draft_state") or {}
    profile = (state.get("player_profiles") or {}).get(player_id)
    if not profile:
        return -9999.0
    roster = fantasy_draft_team_roster(save, team_id)
    round_number = len(roster) + 1
    archetype = fantasy_team_archetype(team_id, int(state.get("seed") or 1))
    features = profile.get("features") or {}
    age = float(profile.get("age") or 27.0)
    impact = float(profile.get("impact") or (profile.get("features") or {}).get("impact") or 50.0)
    contract_surplus = clamp(float(profile.get("contract_surplus") or 0.0), -24.0, 34.0)
    development_upside = clamp(float(profile.get("development_upside") or 0.0), 0.0, 18.0)
    growth = profile.get("growth_outlook") or fantasy_growth_outlook(profile)
    growth_runway = clamp(float(growth.get("engine_high_end_growth", growth.get("high_end_growth") or 0.0)), 0.0, 5.0)
    ceiling_overall = clamp(float(growth.get("engine_ceiling_overall", growth.get("ceiling_overall") or impact)), impact, 99.0)
    longevity = clamp((31.0 - age) * 0.42, -5.0, 5.0)
    score = (
        float(profile.get("draft_quality_rating") or profile.get("ratings_prior_overall") or impact) * 1.5
        + float(profile.get("on_court_value") or 0.0) * 0.28
        + impact * 0.28
        + float(profile.get("player_value") or 0.0) * 0.12
        + contract_surplus * 0.12
        + development_upside * 0.34
        + growth_runway * 1.35
        + max(0.0, ceiling_overall - impact) * 0.42
        + longevity
        + (float(profile.get("playoff_value") or 50.0) - 50.0) * 0.1
        + min(5, int(profile.get("contract_years") or 0)) * 0.45
        - float(profile.get("health_risk") or 0.0) * 0.1
    )
    if round_number <= 3:
        score += max(0.0, impact - 78.0) * 0.55
        score -= max(0.0, age - 32.0) * 1.65
        score += growth_runway * 1.15
    if archetype == "youth":
        score += max(-5.0, min(8.0, (27.0 - age) * 1.05))
        score += development_upside * 0.48
        score += growth_runway * 1.65
    elif archetype == "win_now":
        score += (float(profile.get("playoff_value") or 50.0) - 50.0) * 0.12
        score -= max(0.0, 21.5 - age) * 0.8
    else:
        score += max(-3.0, min(4.0, (29.0 - age) * 0.35))
    score += fantasy_roster_fit_score(profile, roster, round_number)
    score -= fantasy_salary_pressure(profile, roster, round_number)
    noise_scale = 0.65 if round_number <= 4 else min(3.2, 0.7 + round_number * 0.17)
    score += deterministic_unit(state.get("seed"), team_id, player_id, round_number) * noise_scale
    return round(score, 4)


def fantasy_roster_fit_score(profile: dict[str, Any], roster: list[dict[str, Any]], round_number: int) -> float:
    bucket = position_bucket(profile.get("position"))
    counts = {key: sum(position_bucket(row.get("position")) == key for row in roster) for key in ("guard", "wing", "big")}
    targets = {"guard": 5, "wing": 5, "big": 5}
    fit = max(0, targets[bucket] - counts[bucket]) * (1.4 if round_number >= 6 else 0.65)
    if counts[bucket] >= targets[bucket]:
        fit -= 7.0 + (counts[bucket] - targets[bucket]) * 3.0
    features = profile.get("features") or {}
    roster_features = [row.get("features") or {} for row in roster]
    creators = sum(
        row.get("position", "").upper().startswith("PG")
        and float((row.get("features") or {}).get("passing") or 50) >= 70
        for row in roster
    )
    if profile.get("position", "").upper().startswith("PG") and float(features.get("passing") or 50) >= 70:
        fit += 6.0 if creators == 0 else (1.5 if creators == 1 else -10.0)
    needs = {
        "spacing": 68.0,
        "rim_deterrence": 66.0,
        "passing": 66.0,
        "offensive_rebounding": 62.0,
        "defensive_events": 66.0,
    }
    for key, target in needs.items():
        current = max([float(row.get(key) or 0.0) for row in roster_features] or [0.0])
        candidate = float(features.get(key) or 50.0)
        if current < target and candidate >= target:
            fit += min(6.0, 2.0 + (candidate - target) * 0.16)
    if bucket == "big" and counts["big"] == 0 and round_number >= 5:
        fit += 7.0
    if bucket == "wing" and counts["wing"] < 2 and round_number >= 5:
        fit += 5.0
    return fit


def fantasy_salary_pressure(profile: dict[str, Any], roster: list[dict[str, Any]], round_number: int) -> float:
    payroll = sum(float(row.get("salary_millions") or 0.0) for row in roster)
    salary = float(profile.get("salary_millions") or 0.0)
    projected = payroll + salary
    pressure = max(0.0, projected - 190.0) * (0.05 if round_number <= 6 else 0.11)
    if salary >= 40 and float(profile.get("on_court_value") or 0.0) < 64:
        pressure += (salary - 38.0) * 0.18
    return min(14.0, pressure)


def fantasy_team_archetype(team_id: str, seed: int) -> str:
    value = int(hashlib.sha256(f"{seed}:{team_id}:fantasy-archetype".encode("utf-8")).hexdigest()[:8], 16) % 3
    return ("balanced", "youth", "win_now")[value]


def deterministic_unit(*parts: Any) -> float:
    raw = int(hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:8], 16)
    return (raw / 0xFFFFFFFF) * 2.0 - 1.0


def position_bucket(position: Any) -> str:
    value = str(position or "").upper()
    if "C" in value or value in {"PF/C", "C/PF"}:
        return "big"
    if "PG" in value or value in {"G", "SG/PG", "PG/SG"}:
        return "guard"
    return "wing"


def best_fantasy_draft_player(save: dict[str, Any], team_id: str) -> str:
    state = save.get("fantasy_draft_state") or {}
    available = state.get("available_player_ids") or []
    if not available:
        raise ValueError("No fantasy-draft players remain.")
    return max(
        available,
        key=lambda player_id: (
            fantasy_draft_candidate_score(save, team_id, player_id),
            player_id,
        ),
    )


def apply_fantasy_draft_pick(
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_id: str,
    player_id: str | None = None,
    *,
    auto: bool = False,
) -> dict[str, Any]:
    state = save.get("fantasy_draft_state") or {}
    if state.get("status") != "in_progress":
        return {"status": "completed", "selection": None}
    current_team_id = fantasy_draft_current_team_id(save)
    if current_team_id != team_id:
        raise ValueError("That team is not currently on the fantasy-draft clock.")
    if not player_id:
        player_id = best_fantasy_draft_player(save, team_id)
        auto = True
    if player_id not in set(state.get("available_player_ids") or []):
        raise ValueError("That player is no longer available in the fantasy draft.")
    profile = (state.get("player_profiles") or {}).get(player_id) or {}
    pick_index = int(state.get("current_pick_index") or 0)
    selection = {
        "pick_number": pick_index + 1,
        "round": pick_index // 30 + 1,
        "team_id": team_id,
        "player_id": player_id,
        "player_name": profile.get("name") or player_id,
        "position": profile.get("position"),
        "salary_millions": profile.get("salary_millions"),
        "contract_years": profile.get("contract_years"),
        "score": fantasy_draft_candidate_score(save, team_id, player_id),
        "source": "auto_pick" if auto else "human_pick",
    }
    state.setdefault("selections", []).append(selection)
    state["available_player_ids"] = [value for value in state.get("available_player_ids") or [] if value != player_id]
    for watched_ids in (state.setdefault("watchlists", {})).values():
        if isinstance(watched_ids, list):
            watched_ids[:] = [value for value in watched_ids if value != player_id]
    state["current_pick_index"] = pick_index + 1
    if state["current_pick_index"] >= int(state.get("total_picks") or 0):
        finalize_fantasy_draft(canonical, save)
    return {"status": state.get("status"), "selection": selection}


def fantasy_draft_watchlist(save: dict[str, Any], team_id: str) -> list[str]:
    """Return still-available watched players in the user's chosen order."""
    state = save.get("fantasy_draft_state") or {}
    available = set(state.get("available_player_ids") or [])
    watchlists = state.setdefault("watchlists", {})
    watched = [
        str(player_id)
        for player_id in watchlists.get(team_id) or []
        if player_id in available
    ]
    watchlists[team_id] = watched
    return watched


def toggle_fantasy_draft_watchlist(
    save: dict[str, Any],
    team_id: str,
    player_id: str,
) -> dict[str, Any]:
    state = save.get("fantasy_draft_state") or {}
    if state.get("status") != "in_progress":
        raise ValueError("The fantasy draft is already complete.")
    if player_id not in set(state.get("available_player_ids") or []):
        raise ValueError("That player is no longer available in the fantasy draft.")
    watched = fantasy_draft_watchlist(save, team_id)
    if player_id in watched:
        watched.remove(player_id)
        watching = False
    else:
        watched.append(player_id)
        watching = True
    state.setdefault("watchlists", {})[team_id] = watched
    return {
        "status": "watching" if watching else "removed",
        "player_id": player_id,
        "watching": watching,
        "watchlist_player_ids": watched,
    }


def simulate_fantasy_draft_one(
    canonical: dict[str, Any],
    save: dict[str, Any],
    human_team_ids: set[str],
) -> dict[str, Any]:
    """Simulate exactly one AI selection without skipping a human turn."""
    ensure_fantasy_profile_details(canonical, save)
    state = save.get("fantasy_draft_state") or {}
    if state.get("status") != "in_progress":
        return {"status": "completed", "selection": None}
    team_id = fantasy_draft_current_team_id(save)
    if not team_id:
        return {"status": state.get("status") or "completed", "selection": None}
    if team_id in human_team_ids:
        return {"status": "human_on_clock", "selection": None}
    return apply_fantasy_draft_pick(canonical, save, team_id, auto=True)


def simulate_fantasy_draft_until_human(
    canonical: dict[str, Any],
    save: dict[str, Any],
    human_team_ids: set[str],
) -> list[dict[str, Any]]:
    ensure_fantasy_profile_details(canonical, save)
    applied: list[dict[str, Any]] = []
    while (save.get("fantasy_draft_state") or {}).get("status") == "in_progress":
        team_id = fantasy_draft_current_team_id(save)
        if not team_id or team_id in human_team_ids:
            break
        applied.append(apply_fantasy_draft_pick(canonical, save, team_id, auto=True)["selection"])
    return applied


def simulate_fantasy_draft_all(canonical: dict[str, Any], save: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_fantasy_profile_details(canonical, save)
    applied: list[dict[str, Any]] = []
    while (save.get("fantasy_draft_state") or {}).get("status") == "in_progress":
        team_id = fantasy_draft_current_team_id(save)
        if not team_id:
            break
        applied.append(apply_fantasy_draft_pick(canonical, save, team_id, auto=True)["selection"])
    return applied


def finalize_fantasy_draft(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    state = save.get("fantasy_draft_state") or {}
    if state.get('status') == 'completed':
        return
    selections = state.get("selections") or []
    if len(selections) != int(state.get("total_picks") or 0):
        raise ValueError("Cannot finalize an incomplete fantasy draft.")
    drafted_ids = {row["player_id"] for row in selections}
    profile_ids = set((state.get("player_profiles") or {}).keys())
    roster_overrides = save.setdefault("roster_overrides", {})
    for player_id in profile_ids - drafted_ids:
        roster_overrides[player_id] = None
    for row in selections:
        roster_overrides[row["player_id"]] = row["team_id"]
    save["free_agent_player_ids"] = sorted(
        (set(save.get("free_agent_player_ids") or []) | (profile_ids - drafted_ids)) - drafted_ids
    )
    save["starting_lineups"] = {}
    save["rotation_recommendations"] = {}
    save["pending_roster_cutdowns"] = []
    save["roster_cutdown_baselines"] = {team["id"]: FANTASY_ROSTER_SIZE for team in canonical.get("teams", [])}
    state["status"] = "completed"
    state["completed_date"] = str((save.get("state") or {}).get("current_date") or CANONICAL_START_DATE)
    save.setdefault("state", {})["phase"] = "preseason"
    save["state"]["legal_actions"] = ["trades", "contracts", "staff", "rotation", "advance"]
    if save.get('meta', {}).get('gameplay_start_date'):
        from .save import initialize_new_career_runtime, set_save_date_phase
        # Only newly created, explicitly dated careers use the new entry point.
        # Legacy fantasy setups retain their existing dates and history.
        start = save['meta']['gameplay_start_date']
        set_save_date_phase(save, start)
        state['completed_date'] = start
        initialize_new_career_runtime(canonical, save, start, int(save['meta'].get('seed') or 1))
    save.setdefault("league_events", []).append(
        {
            "id": stable_id("league_event", "fantasy_draft_completed", save.get("meta", {}).get("id")),
            "date": state["completed_date"],
            "kind": "fantasy_draft",
            "headline": "The league-wide fantasy draft is complete.",
            "details": {"selection_count": len(selections), "roster_size": FANTASY_ROSTER_SIZE},
            "importance": 92,
        }
    )


def fantasy_draft_room(canonical: dict[str, Any], save: dict[str, Any], team_query: str) -> dict[str, Any]:
    ensure_fantasy_profile_details(canonical, save)
    state = save.get("fantasy_draft_state") or {}
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    team = resolve_fantasy_team(canonical, team_query)
    current_team_id = fantasy_draft_current_team_id(save)
    current_team = teams.get(current_team_id) if current_team_id else None
    current_roster = fantasy_draft_team_roster(save, current_team_id or team["id"])
    watchlist_player_ids = fantasy_draft_watchlist(save, team["id"])
    watched = set(watchlist_player_ids)
    round_number = len(current_roster) + 1
    available = sorted(
        [
            {
                **(state.get("player_profiles") or {})[player_id],
                "is_watchlisted": player_id in watched,
                "board_score": fantasy_draft_candidate_score(save, current_team_id or team["id"], player_id),
                "fit_score": round(
                    clamp(
                        50.0
                        + fantasy_roster_fit_score(
                            (state.get("player_profiles") or {})[player_id],
                            current_roster,
                            round_number,
                        ),
                        1.0,
                        99.0,
                    ),
                    1,
                ),
            }
            for player_id in state.get("available_player_ids") or []
            if player_id in (state.get("player_profiles") or {})
        ],
        key=lambda row: (row["board_score"], row["player_value"], row["name"]),
        reverse=True,
    )
    selections = state.get("selections") or []
    rosters = {
        team_id: fantasy_draft_team_roster(save, team_id)
        for team_id in teams
    }
    payroll = sum(float(row.get("salary_millions") or 0.0) for row in rosters.get(team["id"], []))
    return {
        "version": FANTASY_DRAFT_VERSION,
        "status": state.get("status") or "unavailable",
        "pick_number": min(int(state.get("current_pick_index") or 0) + 1, int(state.get("total_picks") or 0)),
        "total_picks": int(state.get("total_picks") or 0),
        "round": int(state.get("current_pick_index") or 0) // 30 + 1,
        "roster_size": int(state.get("roster_size") or FANTASY_ROSTER_SIZE),
        "current_team": current_team,
        "viewer_team": team,
        "is_viewer_turn": current_team_id == team["id"],
        "available_count": len(available),
        "available_players": available,
        "viewer_roster": rosters.get(team["id"], []),
        "viewer_payroll_millions": round(payroll, 2),
        "watchlist_player_ids": watchlist_player_ids,
        "watchlist": [
            {
                **(state.get("player_profiles") or {})[player_id],
                "board_score": fantasy_draft_candidate_score(
                    save,
                    current_team_id or team["id"],
                    player_id,
                ),
            }
            for player_id in watchlist_player_ids
            if player_id in (state.get("player_profiles") or {})
        ],
        "recent_picks": list(reversed(selections[-12:])),
        "upcoming": fantasy_upcoming_picks(canonical, save, 10),
        "draft_order": [teams[team_id] for team_id in state.get("team_order") or [] if team_id in teams],
        "completed_rosters": rosters if state.get("status") == "completed" else {},
    }


def fantasy_upcoming_picks(canonical: dict[str, Any], save: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    state = save.get("fantasy_draft_state") or {}
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    index = int(state.get("current_pick_index") or 0)
    return [
        {
            "pick_number": pick_index + 1,
            "round": pick_index // 30 + 1,
            "team": teams.get(team_id),
        }
        for pick_index, team_id in enumerate((state.get("pick_team_ids") or [])[index : index + limit], start=index)
    ]


def resolve_fantasy_team(canonical: dict[str, Any], query: str) -> dict[str, Any]:
    needle = str(query or "").strip().lower()
    for team in canonical.get("teams", []):
        if needle in {str(team.get("id") or "").lower(), str(team.get("abbrev") or "").lower(), str(team.get("name") or "").lower()}:
            return team
    raise ValueError(f"Unknown team {query!r}.")


def strip_fantasy_pick_conditions(pick: dict[str, Any]) -> None:
    for key in (
        "protection_summary",
        "protections",
        "protection",
        "condition",
        "conditions",
        "raw_conditions",
        "_obligation_locked",
        "_protection_value_factor",
        "_pick_obligation",
    ):
        pick.pop(key, None)
    if pick.get("current_owner_team_id"):
        pick["status"] = "fantasy_draft_restored_own_pick"
