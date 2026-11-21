"""Evaluate and apply contextual player, pick, and pick-right transactions.

Asset value is receiver- and package-dependent, while legality and consent are
separate decisions. Structured pick obligations are shared by valuation,
display, transfer, lockout, and eventual lottery/draft resolution.
"""

from __future__ import annotations

import math

import json
import pickle
import random
import re
import hashlib
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Any

from .schema import (
    CANONICAL_SEASON,
    CANONICAL_START_DATE,
    FrontOfficeProfile,
    PlayerAssetValuation,
    TeamStrategicState,
    TradeBlockEntry,
    TradeEvaluation,
    TradeProposal,
    TransactionLog,
    to_plain,
)
from .spatial import spatial_fit_delta, with_spatial_fit_context
from .utils import clamp, copy_plain, maybe_float, normalize_name, stable_id


FRONT_OFFICE_OVERRIDES_FILE = Path("data/overrides/front_office_overrides.json")
TRANSACTION_MODEL_CONFIG_FILE = Path("data/overrides/transaction_model_config.json")
TRADE_ASSET_KINDS = {"player", "pick", "pick_swap"}
from .cap_rules import TAX_LINE, SECOND_APRON, ANNUAL_CAP_GROWTH_RATE  # noqa: E402,F401  (one shared source)
RECENTLY_TRADED_DAYS = 60
RECENTLY_ACQUIRED_PREMIUM_DAYS = 180
STRATEGY_MODEL_VERSION = 5
RECENTLY_SIGNED_UNLOCK_MONTH = 12
RECENTLY_SIGNED_UNLOCK_DAY = 1
SIGNING_TRANSACTION_TYPES = {
    "free_agent_signing",
    "free_agency",
    "free_agency_signing",
    "ai_free_agent_signing",
    "ai_re_signing",
    "auto_depth_signing",
}
UNSUPPORTED_PICK_CONDITION_RE = re.compile(
    r"\b(swap|favo[u]?rable|least|most|better|worse|higher|lower|then|or\s+swap|conveys?)\b",
    re.IGNORECASE,
)
UNSUPPORTED_PICK_FALLBACK_RE = re.compile(r"\bif\b.+\bconveys?\b", re.IGNORECASE)


def canonical_mapping(canonical: dict[str, Any] | Any) -> dict[str, Any]:
    """Keep prepared dictionaries intact so their read indexes stay reusable."""
    return canonical if isinstance(canonical, dict) else to_plain(canonical)


def parse_iso_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def transaction_reference_date(canonical: dict[str, Any] | None = None, proposal: TradeProposal | dict[str, Any] | None = None, fallback: str = CANONICAL_START_DATE) -> str:
    if proposal is not None:
        proposal_date = getattr(proposal, "date", None) if not isinstance(proposal, dict) else proposal.get("date")
        if proposal_date:
            return str(proposal_date)
    current = ((canonical or {}).get("meta") or {}).get("current_date")
    return str(current or fallback)


def default_transaction_model_config() -> dict[str, Any]:
    return {
        "version": "transaction_ai_v1",
        "salary_matching": {
            "enabled": True,
            "salary_floor": 7500000,
            "incoming_multiplier": 1.25,
            "incoming_plus": 7500000,
            "minimum_roster": 12,
            "maximum_roster": 18,
        },
        "phase_thresholds": {
            "contender_ceiling": 65,
            "playoff_ceiling": 60,
            "high_youth_pipeline": 45,
            "old_core_age": 30.5,
        },
        "valuation_weights": {
            "contract_surplus": 0.42,
            "age_curve": 0.9,
            "development_upside": 0.75,
            "health_risk": 0.55,
            "role_scarcity": 0.55,
            "playoff_value": 0.16,
        },
        "decision": {
            "base_acceptance_threshold": 1.5,
            "contender_need_bonus": 5.5,
            "rebuilder_pick_bonus_rate": 0.14,
            "manual_review_blocks_execution": True,
            "max_bad_gm_overpay": 8.0,
        },
        "notes": "Practical trade AI config. This is value/fit/legal enough for v1 and intentionally defers deep CBA mechanics.",
    }


def load_transaction_model_config(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root)
    config = default_transaction_model_config()
    path = root / TRANSACTION_MODEL_CONFIG_FILE
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            config = deep_merge(config, json.load(handle))
    return config


def load_front_office_overrides(root: str | Path = ".") -> dict[str, Any]:
    path = Path(root) / FRONT_OFFICE_OVERRIDES_FILE
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_front_office_profiles(teams: list[Any], team_profiles: list[Any], overrides: dict[str, Any] | None = None) -> list[FrontOfficeProfile]:
    overrides = overrides or {}
    team_profiles_by_id = {field_value(profile, "team_id"): profile for profile in team_profiles}
    output: list[FrontOfficeProfile] = []
    for team in teams:
        team_id = field_value(team, "id")
        abbrev = field_value(team, "abbrev")
        profile = team_profiles_by_id.get(team_id)
        override = (overrides.get("teams") or {}).get(abbrev, {})
        generated = generated_front_office_values(abbrev, profile)
        values = {**generated, **{key: value for key, value in override.items() if key in generated}}
        source_ids = ["src_transaction_model_config_v1"]
        if override:
            source_ids.append("src_front_office_overrides_v1")
        output.append(
            FrontOfficeProfile(
                id=stable_id("front_office", team_id),
                team_id=team_id,
                archetype=override.get("archetype") or generated["archetype"],
                competence=round_trait(values["competence"]),
                patience=round_trait(values["patience"]),
                risk_tolerance=round_trait(values["risk_tolerance"]),
                aggressiveness=round_trait(values["aggressiveness"]),
                asset_discipline=round_trait(values["asset_discipline"]),
                timeline_honesty=round_trait(values["timeline_honesty"]),
                owner_pressure=round_trait(values["owner_pressure"]),
                star_chasing=round_trait(values["star_chasing"]),
                financial_discipline=round_trait(values["financial_discipline"]),
                confidence=round(clamp(maybe_float(override.get("confidence")) or 0.45, 0.0, 1.0), 3),
                source_ids=source_ids,
                notes=override.get("notes") or "Deterministic v1 front-office personality for bounded AI trade decisions.",
            )
        )
    return output


def generated_front_office_values(abbrev: str, team_profile: Any | None) -> dict[str, Any]:
    profile = to_plain(team_profile) if team_profile else {}
    text = " ".join(
        [
            str(profile.get("timeline") or ""),
            str(profile.get("identity") or ""),
            " ".join(profile.get("strategic_behavior") or []),
            str(profile.get("front_office_pressure") or ""),
        ]
    ).lower()
    base = {
        "archetype": deterministic_pick(
            ["balanced operator", "patient portfolio builder", "aggressive star hunter", "discipline-first steward", "short-window optimizer"],
            abbrev,
            "fo_archetype",
        ),
        "competence": 58 + deterministic_offset(abbrev, "competence"),
        "patience": 58 + deterministic_offset(abbrev, "patience"),
        "risk_tolerance": 56 + deterministic_offset(abbrev, "risk"),
        "aggressiveness": 56 + deterministic_offset(abbrev, "aggression"),
        "asset_discipline": 58 + deterministic_offset(abbrev, "discipline"),
        "timeline_honesty": 58 + deterministic_offset(abbrev, "honesty"),
        "owner_pressure": 52 + deterministic_offset(abbrev, "pressure"),
        "star_chasing": 54 + deterministic_offset(abbrev, "stars"),
        "financial_discipline": 58 + deterministic_offset(abbrev, "money"),
    }
    if "contending" in text or "maximize_star_window" in text:
        base["aggressiveness"] += 7
        base["owner_pressure"] += 7
        base["patience"] -= 5
    if "protect_future_flexibility" in text or "future_upside" in text:
        base["asset_discipline"] += 9
        base["patience"] += 7
        base["star_chasing"] -= 4
    if "rebuild" in text or "developing" in text:
        base["patience"] += 8
        base["asset_discipline"] += 5
        base["aggressiveness"] -= 4
    if "high" in text:
        base["owner_pressure"] += 8
    return base


def build_transaction_context(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None, *, _full_reference: bool = False) -> dict[str, Any]:
    canonical = canonical_mapping(canonical)
    config = config or default_transaction_model_config()
    front_offices = canonical.get("front_office_profiles") or to_plain(build_front_office_profiles(canonical.get("teams", []), canonical.get("team_profiles", []), {}))
    working = {**canonical, "front_office_profiles": front_offices}
    valuations = (build_player_asset_valuations(working, config, _full_features=True) if _full_reference
                  else build_player_asset_valuations(working, config))
    working["player_asset_valuations"] = [to_plain(value) for value in valuations]
    states = (build_team_strategic_states(working, valuations, config, _full_features=True) if _full_reference else
              build_team_strategic_states(working, valuations, config, _final_needs_only=True))
    working["team_strategic_states"] = [to_plain(state) for state in states]
    trade_block = build_trade_block_entries(working, states, valuations, config)
    return {
        "_strategy_model_version": STRATEGY_MODEL_VERSION,
        "front_office_profiles": front_offices,
        "team_strategic_states": [to_plain(state) for state in states],
        "player_asset_valuations": [to_plain(value) for value in valuations],
        "trade_block_entries": [to_plain(entry) for entry in trade_block],
    }


def full_transaction_context_reference(canonical, config=None):
    """Original eager construction, retained as a fresh differential fallback."""
    return build_transaction_context(canonical, config, _full_reference=True)


def build_team_strategic_states(canonical: dict[str, Any] | Any, valuations: list[PlayerAssetValuation] | None = None, config: dict[str, Any] | None = None, *, _final_needs_only: bool = False, _full_features: bool = False) -> list[TeamStrategicState]:
    canonical = canonical_mapping(canonical)
    # All league-relative baselines are still rebuilt. Only their immutable
    # player inputs are shared while constructing this one set of states.
    from .roster_forecast import ForecastSnapshot
    canonical = {**canonical, '_roster_forecast_snapshot': ForecastSnapshot(canonical)}
    config = config or default_transaction_model_config()
    if valuations is None:
        valuations = build_player_asset_valuations(canonical, config, _full_features=_full_features)
    values_by_team: dict[str, list[PlayerAssetValuation]] = {}
    for valuation in valuations:
        values_by_team.setdefault(valuation.team_id, []).append(valuation)
    profiles = {profile["team_id"]: profile for profile in canonical.get("team_profiles", [])}
    front_offices = {profile["team_id"]: profile for profile in canonical.get("front_office_profiles", [])}
    output: list[TeamStrategicState] = []
    for team in canonical.get("teams", []):
        team_values = sorted(values_by_team.get(team["id"], []), key=lambda item: item.player_value, reverse=True)
        players = [player for player in canonical.get("players", []) if player["team_id"] == team["id"]]
        top_players = [player_by_id(canonical, value.player_id) for value in
                       sorted(team_values, key=lambda v: (-v.on_court_value, v.player_id))[:5]]
        top_ages = [float(player.get("display_age", player.get("age"))) for player in top_players
                    if player and player.get("display_age", player.get("age")) is not None]
        core_age = sum(top_ages[:3]) / len(top_ages[:3]) if top_ages[:3] else None
        ceiling = contention_ceiling(canonical, team, team_values)
        youth = youth_pipeline_score(players, team_values)
        pick_inventory = team_pick_inventory(canonical, team["id"])
        health_risk = team_health_risk(canonical, team_values[:6])
        salary = salary_posture(canonical, team["id"])
        profile = profiles.get(team["id"], {})
        front_office = front_offices.get(team["id"], {})
        phase = classify_team_phase(profile, ceiling, core_age, youth, pick_inventory, config)
        # League assessment below reads strength/core/record inputs, never
        # these lists. For a full league they are replaced using the final
        # relative phase; calculate only that consumed result. Tiny leagues
        # retain the original preliminary result, as does the full fallback.
        needs, excesses = ([], []) if _final_needs_only and len(canonical.get('teams', [])) >= 4 else team_needs_and_excesses(canonical, team, players, phase, _full_features=_full_features)
        pressure = strategic_pressure(profile, front_office, phase, core_age)
        output.append(
            TeamStrategicState(
                id=stable_id("team_strategy", team["id"]),
                team_id=team["id"],
                phase=phase,
                timeline=phase,
                contention_ceiling=round(ceiling, 2),
                core_age=round(core_age, 2) if core_age is not None else None,
                health_risk=round(health_risk, 3),
                salary_posture=salary["posture"],
                youth_pipeline=round(youth, 2),
                pick_inventory=pick_inventory,
                needs=needs,
                excesses=excesses,
                pressure=round(pressure, 2),
                confidence=round(0.52 + min(0.18, float(profile.get("confidence") or 0) * 0.15), 3),
                source_ids=["src_transaction_model_config_v1", "src_trait_method_v1", *list(profile.get("source_ids") or [])],
                notes="Live roster strategy from player values, age, health, salary, needs and picks. Imported research timelines do not override the phase.",
            )
        )
    from .team_planning import window_assessments, LEGACY_PHASE
    assessments = window_assessments(canonical, output, valuations)
    if len(output) >= 4:
        revised = []
        for state in output:
            row = assessments[state.team_id]
            phase = LEGACY_PHASE[row['window_phase']]
            if phase == 'contending' and state.youth_pipeline >= 45:
                phase = 'contending_with_future_upside'
            needs, excesses = team_needs_and_excesses(canonical, team_by_id(canonical, state.team_id),
                [p for p in canonical.get('players', []) if p.get('team_id') == state.team_id], phase, _full_features=_full_features)
            revised.append(replace(state, phase=phase, timeline=phase, needs=needs, excesses=excesses,
                window_phase=row['window_phase'], league_rank=row['league_rank'], contender_index=row['contender_index'],
                window_trend=row['trend'], core_candidates=row['core_candidates'],
                contend_distance=row.get('contend_distance', 0.0)))
        return revised
    return output


_VALUATION_FEATURES: dict[bytes, dict[str, float]] = {}


def _valuation_features(canonical: dict[str, Any], player: dict[str, Any], include_spatial: bool) -> dict[str, float]:
    """sim.player_feature_vector(...).features for a transaction context, remembered across contexts.

    Every context build (each market day, each applied trade's live check) re-derives every player's features
    although almost none of them changed. Without zone grids the features read only: the player record, the
    player's trait rows (as the sim cache indexes them), the talent/offense model switches and the player's
    offensive profile in the league meta, and the new-ratings model's mode, table keys and the player's input
    deltas or generated-input key (impact fit, effective inputs). All of that is pickled into the key, so equal
    keys mean equal inputs. Zone-grid (spatial) features are always computed fresh."""
    from .sim import canonical_sim_cache, player_feature_vector
    from . import impact_value
    if include_spatial or impact_value._BUILDING:
        return player_feature_vector(canonical, player, include_spatial=include_spatial).features
    from .ratings_model import MODEL_KEY
    meta = canonical.get("meta") or {}
    model = canonical.get(MODEL_KEY) or {}
    pid = player.get("id")
    try:
        key = pickle.dumps((
            "valuation_features_v1", player, canonical_sim_cache(canonical)["traits_by_player"].get(pid, {}),
            meta.get("talent_model_version"), meta.get("offense_model_version"),
            (meta.get("offensive_profiles") or {}).get(pid),
            [model.get(field) for field in ("mode", "inputs_key", "fitted_key", "impact_tables_key")],
            (model.get("input_deltas") or {}).get(pid), (model.get("generated") or {}).get(pid),
        ), protocol=pickle.HIGHEST_PROTOCOL)
    except (pickle.PicklingError, TypeError, AttributeError):
        return player_feature_vector(canonical, player, include_spatial=False).features
    features = _VALUATION_FEATURES.get(key)
    if features is None or _CONTENTION_AUDIT:
        fresh = player_feature_vector(canonical, player, include_spatial=False).features
        if _CONTENTION_AUDIT and features is not None and features != fresh:
            raise AssertionError(f"valuation feature memo disagrees for {pid}")
        features = fresh
        if len(_VALUATION_FEATURES) >= 20_000:
            _VALUATION_FEATURES.pop(next(iter(_VALUATION_FEATURES)))
        _VALUATION_FEATURES[key] = features
    return features


def build_player_asset_valuations(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None, *, _full_features: bool = False) -> list[PlayerAssetValuation]:
    canonical = canonical_mapping(canonical)
    config = config or default_transaction_model_config()
    from .sim import player_feature_vector

    traits = traits_by_player(canonical)
    contracts = {contract["player_id"]: contract for contract in canonical.get("contracts", [])}
    health_profiles = {profile["player_id"]: profile for profile in canonical.get("player_health_profiles", [])}
    health_states = {state["player_id"]: state for state in canonical.get("player_health_states", [])}
    output: list[PlayerAssetValuation] = []
    fitted_on_court: dict[str, float] = {}
    from .impact_value import remap_on_court
    from .ratings_model import uses_inputs_model
    if uses_inputs_model(canonical):
        # New ratings: the market's on-court values are re-ordered by impact fitted from the hidden ratings
        # (impact_value), keeping the market's own scale so every value cutoff still means the same thing.
        legacy = {}
        for player in canonical.get("players", []):
            features = _valuation_features(canonical, player, _full_features)
            portability = float(traits.get(player["id"], {}).get("portability", {}).get("value", features.get("impact", 50)))
            legacy[player["id"]] = player_on_court_value(features, portability)
        plain_traits = {pid: {k: float(v.get("value", 50)) for k, v in rows.items()} for pid, rows in traits.items()}
        fitted_on_court = remap_on_court(canonical, canonical.get("players", []), plain_traits, legacy)
    # Injury risk: the v2 per-body-part model decides who is riskier; the legacy score supplies the scale the AI's
    # thresholds were written for (rank mapping). Current-injury and rust terms stay on top.
    legacy_risk = {player["id"]: player_health_risk(health_profiles.get(player["id"], {}), {})
                   for player in canonical.get("players", []) if player.get("id")}
    from .injury_model import health_risk_scores
    base_risk = health_risk_scores(canonical, legacy_risk)
    for player in canonical.get("players", []):
        # Valuation consumes scalar basketball/offensive-role features only.
        # Keep minutes and role calculations fresh; zone grids are unused here.
        features = _valuation_features(canonical, player, _full_features)
        contract = contracts.get(player["id"], {})
        salary = current_salary(contract)
        contract_status = "salary_known" if salary is not None else "manual_review_required"
        age = maybe_float(player.get("age")) or 27.0
        portability = float(traits.get(player["id"], {}).get("portability", {}).get("value", features.get("impact", 50)))
        playoff = features.get("playoff_translation", 50.0)
        on_court = fitted_on_court.get(player["id"]) or player_on_court_value(features, portability)
        age_curve = player_age_curve(age)
        development = player_development_upside(player, age, features)
        state = health_states.get(player["id"], {})
        health_risk = clamp(base_risk.get(player["id"], legacy_risk.get(player["id"], 0.0))
                            + (1.25 if state.get("availability_status") not in (None, "active") else 0.0)
                            + float(state.get("rust") or 0) * 0.035, 0, 34)
        scarcity = role_scarcity_score(player, features, traits.get(player["id"], {}))
        surplus = contract_surplus_value(on_court, age_curve, development, salary, contract)
        weights = config.get("valuation_weights", {})
        value = (
            on_court
            + age_curve * float(weights.get("age_curve", 0.9))
            + development * float(weights.get("development_upside", 0.75))
            + surplus * float(weights.get("contract_surplus", 0.42)) * (surplus_quality_factor(on_court) if surplus > 0 else 1.0)
            + scarcity * float(weights.get("role_scarcity", 0.55))
            + (playoff - 50) * float(weights.get("playoff_value", 0.16))
            - health_risk * float(weights.get("health_risk", 0.42))
        )
        value = max(value, drafted_rookie_value_floor(player, ability=maybe_float(player.get("current_ability")) or on_court, potential=maybe_float(player.get("potential")) or on_court))
        if on_court >= 72:
            star_floor = 66.0 + (on_court - 72.0) * 0.58 + max(0.0, playoff - 70.0) * 0.16 + max(0.0, portability - 70.0) * 0.1 - health_risk * 0.035
            value = max(value, star_floor)
        elif on_court >= 66:
            value = max(value, 54.0 + (on_court - 66.0) * 0.52 + max(0.0, playoff - 64.0) * 0.1 - health_risk * 0.025)
        if goat_exception_player(player):
            value = 99.0
            surplus = max(surplus, 0.0)
        output.append(
            PlayerAssetValuation(
                id=stable_id("player_asset_value", player["id"]),
                player_id=player["id"],
                team_id=player["team_id"],
                player_value=round(soft_value_ceiling(value), 2),
                on_court_value=round(on_court, 2),
                contract_surplus=round(surplus, 2),
                age_curve=round(age_curve, 2),
                health_risk=round(health_risk, 2),
                role_scarcity=round(scarcity, 2),
                portability=round(portability, 2),
                playoff_value=round(playoff, 2),
                development_upside=round(development, 2),
                contract_status=contract_status,
                current_salary=salary,
                confidence=round(0.48 + min(0.28, (float(player.get("minutes_projection") or 0) / 36) * 0.2), 3),
                source_ids=["src_transaction_model_config_v1", "src_trait_method_v1", *list(contract.get("source_ids") or [])],
                notes="Asset value v1 combines player impact, portability, age, development, contract value, health risk, role scarcity, and playoff translation.",
            )
        )
    return output


def build_trade_block_entries(
    canonical: dict[str, Any] | Any,
    states: list[TeamStrategicState] | None = None,
    valuations: list[PlayerAssetValuation] | None = None,
    config: dict[str, Any] | None = None,
) -> list[TradeBlockEntry]:
    canonical = canonical_mapping(canonical)
    config = config or default_transaction_model_config()
    if valuations is None:
        valuations = build_player_asset_valuations(canonical, config)
    if states is None:
        states = build_team_strategic_states(canonical, valuations, config)
    state_by_team = {state.team_id: state for state in states}
    value_by_player = {value.player_id: value for value in valuations}
    output: list[TradeBlockEntry] = []
    for player in canonical.get("players", []):
        if not player.get("team_id") or player.get("team_id") not in state_by_team:
            continue
        valuation = value_by_player[player["id"]]
        state = state_by_team[player["team_id"]]
        score, reasons, preferred = trade_block_score(canonical, player, valuation, state)
        from .team_planning import core_commitment
        if core_commitment(canonical, player['team_id'], player['id']):
            continue
        manual_block = canonical.get("team_trade_blocks", {}).get(player["team_id"])
        if manual_block is not None:
            if player["id"] not in manual_block:
                continue
            score = max(score, 75.0)
            reasons = [*reasons, "gm_listed"]
        if player["id"] in set(canonical.get("ai_trade_pressure_player_ids", [])):
            score += 18.0
            reasons = [*reasons, "extension_talks_stalled"]
            preferred = "best_asset_or_young_player"
        if score < 28:
            continue
        output.append(
            TradeBlockEntry(
                id=stable_id("trade_block", player["team_id"], player["id"]),
                team_id=player["team_id"],
                player_id=player["id"],
                block_score=round(clamp(score, 0, 100), 2),
                willingness=block_willingness(score),
                reasons=reasons,
                preferred_return=preferred,
                confidence=0.58,
                source_ids=["src_transaction_model_config_v1"],
                notes="V1 inferred trade-block entry from timeline mismatch, needs/excess, contract value, age, health, and team phase.",
            )
        )
    return sorted(output, key=lambda item: (item.block_score, item.player_id), reverse=True)


def gm_report(canonical: dict[str, Any] | Any, team_query: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_transaction_context(canonical, config)
    team = resolve_team(canonical, team_query)
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team["id"])
    front_office = next(item for item in canonical["front_office_profiles"] if item["team_id"] == team["id"])
    valuations = [item for item in canonical["player_asset_valuations"] if item["team_id"] == team["id"]]
    block = [item for item in canonical["trade_block_entries"] if item["team_id"] == team["id"]]
    players = {player["id"]: player for player in canonical["players"]}
    return {
        "team": team,
        "front_office": front_office,
        "strategic_state": state,
        "top_assets": [
            {**compact_player(players[value["player_id"]]), "player_value": value["player_value"], "contract_surplus": value["contract_surplus"]}
            for value in sorted(valuations, key=lambda item: item["player_value"], reverse=True)[:8]
        ],
        "trade_block": [
            {**compact_player(players[entry["player_id"]]), "block_score": entry["block_score"], "willingness": entry["willingness"], "reasons": entry["reasons"]}
            for entry in sorted(block, key=lambda item: item["block_score"], reverse=True)[:10]
        ],
    }


def trade_block_report(canonical: dict[str, Any] | Any, team_query: str | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_transaction_context(canonical, config)
    teams = {team["id"]: team for team in canonical["teams"]}
    players = {player["id"]: player for player in canonical["players"]}
    entries = canonical["trade_block_entries"]
    if team_query:
        team = resolve_team(canonical, team_query)
        entries = [entry for entry in entries if entry["team_id"] == team["id"]]
    return {
        "team": resolve_team(canonical, team_query) if team_query else None,
        "entry_count": len(entries),
        "entries": [
            {
                "team": teams[entry["team_id"]]["abbrev"],
                **compact_player(players[entry["player_id"]]),
                "block_score": entry["block_score"],
                "willingness": entry["willingness"],
                "preferred_return": entry["preferred_return"],
                "reasons": entry["reasons"],
            }
            for entry in sorted(entries, key=lambda item: item["block_score"], reverse=True)
        ],
    }


def find_trade(
    canonical: dict[str, Any] | Any,
    player_name: str,
    for_team: str,
    limit: int = 10,
    seed: int = 1,
    config: dict[str, Any] | None = None,
    package_result_limit: int = 18,
    package_player_options: int = 9,
) -> dict[str, Any]:
    canonical = with_transaction_context(canonical, config)
    user_team = resolve_team(canonical, for_team)
    canonical = {**canonical, '_human_team_ids': sorted(set(canonical.get('_human_team_ids') or []) | {user_team['id']})}
    target = resolve_player(canonical, player_name)
    candidates: list[dict[str, Any]] = []
    if effectively_untouchable(canonical, target):
        candidates = []
    elif target["team_id"] == user_team["id"]:
        candidates = find_selling_candidates(canonical, user_team, target, seed, package_result_limit, package_player_options)
    else:
        candidates = find_buying_candidates(canonical, user_team, target, seed, package_result_limit, package_player_options)
    candidates = [candidate for candidate in candidates if user_facing_trade_candidate_ok(canonical, candidate, user_team["id"])]
    candidates = sorted(candidates, key=lambda item: candidate_sort_score(item, user_team["id"]), reverse=True)[:limit]
    candidates = [prepare_ai_trade_candidate(canonical, candidate, seed=seed,
                  date=(candidate.get('proposal') or {}).get('date'), config=config)
                  for candidate in candidates]
    return {
        "player": compact_player(target),
        "for_team": user_team,
        "mode": "shop_player" if target["team_id"] == user_team["id"] else "target_player",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "notes": "Candidates are legal executable offers from the opposing GM perspective. User acceptance is still explicit.",
    }


def find_trade_for_assets(
    canonical: dict[str, Any] | Any,
    target_team_query: str,
    target_assets: list[dict[str, Any]],
    for_team: str,
    limit: int = 10,
    seed: int = 1,
    config: dict[str, Any] | None = None,
    buyer_team: str | None = None,
    ai_buyer: bool = False,
) -> dict[str, Any]:
    canonical = with_transaction_context(canonical, config)
    user_team = resolve_team(canonical, for_team)
    if not ai_buyer:
        # The user's finder: the user's own side is the user's call. An AI team searching for itself (ai_buyer)
        # keeps its full AI evaluation, including its own-player price (trade step 1).
        canonical = {**canonical, '_human_team_ids': sorted(set(canonical.get('_human_team_ids') or []) | {user_team['id']})}
    seller = resolve_team(canonical, target_team_query)
    selected_buyer = resolve_team(canonical, buyer_team) if buyer_team else None
    normalized_target = normalize_assets(canonical, seller, target_assets)
    if not normalized_target:
        return {
            "player": {},
            "target_assets": [],
            "for_team": user_team,
            "buyer_team": selected_buyer,
            "mode": "empty_package",
            "candidate_count": 0,
            "candidates": [],
            "notes": "No assets were selected.",
        }
    target_value = asset_package_value(canonical, normalized_target)
    target_salary = asset_package_salary(canonical, normalized_target)
    target_specs = trade_specs_from_normalized(normalized_target)
    selected_player_ids = {asset["id"] for asset in normalized_target if asset.get("kind") == "player"}
    from .trade_finance_search import TradeSearchIntent
    def intent_for(buyer):
        return TradeSearchIntent(seller['id'],buyer['id'],tuple(normalized_target),canonical.get('meta',{}).get('current_date') or CANONICAL_START_DATE,config)
    candidates: list[dict[str, Any]] = []
    if seller["id"] == user_team["id"]:
        if package_is_effectively_untouchable(canonical, normalized_target):
            candidates = []
        else:
            for buyer in buyer_teams_for_asset_package(canonical, seller, normalized_target):
                if buyer["id"] == seller["id"]:
                    continue
                if selected_buyer and buyer["id"] != selected_buyer["id"]:
                    continue
                buyer_context_target_value = package_value_for_team(canonical, normalized_target, buyer["id"])
                for buyer_assets in buyer_offer_packages_for_value(canonical, buyer, seller, buyer_context_target_value, target_salary, seed, selected_player_ids,intent=intent_for(buyer))[:12]:
                    report = evaluate_trade_decision(canonical, seller["abbrev"], buyer["abbrev"], target_specs, buyer_assets, seed=seed, context_ready=True)
                    candidates.append(candidate_from_decision(report))
        mode = "shop_package"
    else:
        for package in buyer_offer_packages_for_value(canonical, user_team, seller, target_value, target_salary, seed, selected_player_ids,intent=intent_for(user_team))[:18]:
            report = evaluate_trade_decision(canonical, user_team["abbrev"], seller["abbrev"], package, target_specs, seed=seed, context_ready=True)
            candidates.append(candidate_from_decision(report))
        mode = "target_package"
    candidates = [candidate for candidate in candidates if user_facing_trade_candidate_ok(canonical, candidate, user_team["id"])]
    candidates = sorted(candidates, key=lambda item: candidate_sort_score(item, user_team["id"]), reverse=True)[:limit]
    candidates = [prepare_ai_trade_candidate(canonical, candidate, seed=seed,
                  date=(candidate.get('proposal') or {}).get('date'), config=config)
                  for candidate in candidates]
    return {
        "player": package_report_subject(canonical, normalized_target, seller),
        "target_assets": normalized_target,
        "for_team": user_team,
        "buyer_team": selected_buyer,
        "mode": mode,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "notes": "Package candidates are legal executable offers from the opposing GM perspective. User acceptance is still explicit.",
    }


def effectively_untouchable(canonical: dict[str, Any], player: dict[str, Any]) -> bool:
    valuation = next((value for value in canonical.get("player_asset_valuations", []) if value.get("player_id") == player.get("id")), fallback_asset_valuation(player))
    block = next((entry for entry in canonical.get("trade_block_entries", []) if entry.get("player_id") == player.get("id")), {})
    market_value = market_trade_target_value(player, valuation)
    state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == player.get("team_id")), {})
    age = maybe_float(player.get("age")) or 27.0
    old_win_now_icon = (
        market_value >= 82.0
        and age >= 32.0
        and state.get("phase") in {"contending", "contending_with_future_upside"}
    )
    return (
        (market_value >= 94.0 or old_win_now_icon)
        and float(valuation.get("health_risk") or 0.0) <= 10.0
        and float(block.get("block_score") or 0.0) < 55.0
    )


def package_is_effectively_untouchable(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> bool:
    players = [player_by_id(canonical, asset.get("id")) for asset in assets if asset.get("kind") == "player"]
    players = [player for player in players if player]
    return bool(players) and any(effectively_untouchable(canonical, player) for player in players) and asset_package_value(canonical, assets) < 95.0


def evaluate_trade(
    canonical: dict[str, Any] | Any,
    from_team_query: str,
    to_team_query: str,
    from_assets: list[dict[str, Any]],
    to_assets: list[dict[str, Any]],
    seed: int = 1,
    date: str = CANONICAL_START_DATE,
    config: dict[str, Any] | None = None,
    context_ready: bool = False,
) -> dict[str, Any]:
    return _evaluate_trade_snapshot(
        canonical,
        from_team_query,
        to_team_query,
        from_assets,
        to_assets,
        seed=seed,
        date=date,
        config=config,
        context_ready=context_ready,
        include_presentation=True,
    )


def evaluate_trade_decision(
    canonical: dict[str, Any] | Any,
    from_team_query: str,
    to_team_query: str,
    from_assets: list[dict[str, Any]],
    to_assets: list[dict[str, Any]],
    seed: int = 1,
    date: str = CANONICAL_START_DATE,
    config: dict[str, Any] | None = None,
    context_ready: bool = False,
    search_only: bool = False,
) -> dict[str, Any]:
    """Evaluate legality and consent without building user-facing explanations."""
    return _evaluate_trade_snapshot(
        canonical,
        from_team_query,
        to_team_query,
        from_assets,
        to_assets,
        seed=seed,
        date=date,
        config=config,
        context_ready=context_ready,
        include_presentation=False,
        search_only=search_only,
    )


def _evaluate_trade_snapshot(
    canonical: dict[str, Any] | Any,
    from_team_query: str,
    to_team_query: str,
    from_assets: list[dict[str, Any]],
    to_assets: list[dict[str, Any]],
    *,
    seed: int,
    date: str,
    config: dict[str, Any] | None,
    context_ready: bool,
    include_presentation: bool,
    proposal_id: str | None = None,
    search_only: bool = False,
) -> dict[str, Any]:
    canonical = canonical if context_ready else canonical if transaction_context_ready(canonical) else with_transaction_context(canonical, config)
    config = config or default_transaction_model_config()
    from_team = resolve_team(canonical, from_team_query)
    to_team = resolve_team(canonical, to_team_query)
    proposal = TradeProposal(
        id=proposal_id or stable_id("trade_proposal", date, from_team["id"], to_team["id"], json.dumps(from_assets, sort_keys=True), json.dumps(to_assets, sort_keys=True)),
        date=date,
        from_team_id=from_team["id"],
        to_team_id=to_team["id"],
        from_assets=normalize_assets(canonical, from_team, from_assets),
        to_assets=normalize_assets(canonical, to_team, to_assets),
        status="evaluated",
        source_ids=["src_transaction_model_config_v1"],
        notes="Two-team v1 trade proposal. From-team assets go to to-team; to-team assets go to from-team.",
    )
    legality = trade_legality(canonical, proposal, config)
    counts = canonical.get('_search_work_counts')
    category = 'legal'
    if search_only:
        if legality['status'] != 'legal':
            category = ('unresolved' if legality['status']=='manual_review_required' else 'terminal')
            if counts is not None: counts['skipped_reports.'+category] += 1
            return {'proposal':to_plain(proposal),'legality':legality,'evaluations':[],
                    'accepted_by_all':False,'evaluation_seed':seed,'evaluation_proposal_id':proposal.id}
        # This authoritative safeguard can reject a complete package before
        # expensive pricing/roster forecasts. It never approves a package.
        if any(premium_return_issue(canonical, tid, incoming, outgoing)
               for tid,outgoing,incoming in trade_team_flows(proposal)):
            if counts is not None: counts['skipped_reports.premium_return'] += 1
            return {'proposal':to_plain(proposal),'legality':legality,'evaluations':[],
                    'accepted_by_all':False,'evaluation_seed':seed,'evaluation_proposal_id':proposal.id}
        if legality['manual_review']: category = 'unresolved'
    if counts is not None: counts['participant_reports.'+('presentation' if include_presentation else category)] += 1
    if canonical.get('_package_search_diagnostics') is not None and not include_presentation:
        canonical['_package_search_diagnostics']['full_evaluations'] += 1
    evaluations = evaluate_trade_participants(canonical, proposal, legality, seed, config,
        include_presentation=include_presentation,early_reject=search_only)
    if search_only and not evaluations:
        if counts is not None:
            counts['participant_reports.'+category] -= 1
            counts['partial_reports.'+category] += 1
        if canonical.get('_package_search_diagnostics') is not None:
            canonical['_package_search_diagnostics']['full_evaluations'] -= 1
        return {'proposal':to_plain(proposal),'legality':legality,'evaluations':[],
                'accepted_by_all':False,'evaluation_seed':seed,'evaluation_proposal_id':proposal.id}
    from_eval = next(e for e in evaluations if e.perspective_team_id == from_team['id'])
    to_eval = next(e for e in evaluations if e.perspective_team_id == to_team['id'])
    if include_presentation:
        from_plain = trade_evaluation_payload(canonical, from_eval, config)
        to_plain_eval = trade_evaluation_payload(canonical, to_eval, config)
    else:
        from_plain = to_plain(from_eval)
        to_plain_eval = to_plain(to_eval)
    proposal_payload = to_plain(proposal)
    result = {
        "proposal": proposal_payload,
        "legality": legality,
        "evaluations": [from_plain, to_plain_eval],
        "accepted_by_all": from_eval.accepted and to_eval.accepted and legality["status"] == "legal",
        "evaluation_seed": seed,
        "evaluation_proposal_id": proposal.id,
    }
    if include_presentation:
        result["value_breakdown"] = trade_value_breakdown(canonical, proposal_payload)
    return result


def private_trade_targets(canonical, excluded, seed, stamp):
    """Unlisted non-core contributors can receive a private offer, not a listing."""
    from .team_planning import core_commitment
    values = player_asset_values_by_id(canonical)
    by_team = {}
    rng = random.Random(f'{seed}:{stamp}:private-trade-targets-v1')
    for player in sorted(canonical.get('players', []), key=lambda p: p['id']):
        tid = player.get('team_id')
        if (not tid or player['id'] in excluded or player.get('_inactive_player')
                or float(player.get('minutes_projection') or 0) < 16
                or core_commitment(canonical, tid, player['id'])):
            continue
        value = float(values.get(player['id'], {}).get('player_value') or 0)
        if 20 <= value < 72:
            by_team.setdefault(tid, []).append((rng.random(), player['id']))
    return [{'player_id': pid, 'block_score': 0, 'private_target': True}
            for tid in sorted(by_team) for _, pid in sorted(by_team[tid])[:2]]


def trade_search_context(canonical: dict[str, Any]) -> dict[str, Any]:
    """One immutable search's player-only forecasts; never retain across settlements."""
    from .roster_forecast import ForecastSnapshot
    forecast = ForecastSnapshot(canonical)
    return {**canonical, '_trade_search_roles': {}, '_trade_search_rosters': {},
            '_trade_financial_facts': {}, '_trade_movement_classes': {}, '_pick_presentation_memo': {},
            '_trade_search_market_values': {}, '_trade_ownership_memo': {}, '_own_departure_states': {},
            '_trade_search_exact_memo': {'base_sources': (canonical.get('players'), canonical.get('draft_picks'),
                                                          canonical.get('pick_obligations'), canonical.get('teams'))},
            '_roster_forecast_snapshot': forecast, '_roster_forecast_stats': forecast.stats}


# Exact memos for one immutable trade search (see trade_search_context; deadline-speed.md). They are attached
# only to search contexts, whose league objects are never edited while the search runs. Each entry keeps the
# objects it was computed from and is used only when the caller passes those very objects again.
def _search_market_value(canonical: dict[str, Any], player: dict[str, Any] | None, valuation: dict[str, Any]) -> float:
    memo = canonical.get('_trade_search_market_values')
    if memo is None or not player:
        return market_trade_target_value(player, valuation)
    entry = memo.get(player.get('id'))
    if entry is not None and entry[0] is player and entry[1] is valuation:
        return entry[2]
    value = market_trade_target_value(player, valuation)
    memo[player.get('id')] = (player, valuation, value)
    return value


def _search_team_rows(canonical: dict[str, Any], team_id: str | None) -> list[dict[str, Any]] | None:
    """The team's player records in league order from the search's forecast index, or None outside a search."""
    forecast = canonical.get('_roster_forecast_snapshot')
    if forecast is None or canonical.get('players') is not forecast.players_source:
        return None
    return [player for _, player in forecast.teams.get(team_id, ())]


def simulate_ai_trades(canonical: dict[str, Any] | Any, from_date: str, through_date: str, seed: int = 1, limit: int = 10, config: dict[str, Any] | None = None, *, search_depth: int = 1, reserve_assets: bool = False, include_private_targets: bool = True, involving_team_ids: set[str] | None = None, review=None, target_search: bool | None = None, focus_team_ids: set[str] | None = None) -> dict[str, Any]:
    canonical = (review.prepare(canonical, config) if review is not None else
                 trade_search_context(with_spatial_fit_context(with_transaction_context(canonical, config))))
    # AI-to-AI markets start from each front office's targets (trade step 2, trade_targets.py). The search for
    # offers to the human team (involving_team_ids) keeps the listed-player search.
    if target_search is None:
        target_search = involving_team_ids is None
    if target_search:
        return target_driven_ai_trades(canonical, from_date, through_date, seed=seed, limit=limit, config=config,
                                       search_depth=search_depth, reserve_assets=reserve_assets,
                                       focus_team_ids=focus_team_ids)
    rng = random.Random(f"{seed}:{from_date}:{through_date}:ai_trades")
    recent_players = recently_traded_player_ids(canonical, through_date)
    entries = sorted(canonical["trade_block_entries"], key=lambda item: item["block_score"], reverse=True)[:120]
    from .trade_wants import wants_for_team
    listed = {entry['player_id'] for entry in entries}
    for tid in sorted(canonical.get('_human_team_ids', [])):
        for want in wants_for_team(canonical, tid):
            pid = want.get('target_player_id') if want.get('kind') == 'upgrade' else None
            target = player_by_id(canonical, pid) if pid else None
            if target and target.get('team_id') == tid and pid not in listed:
                entries.append({'player_id': pid, 'block_score': 0, 'private_target': True})
                listed.add(pid)
    if search_depth > 1 and include_private_targets:
        entries += private_trade_targets(canonical, {r['player_id'] for r in entries}, seed, through_date)
    proposals = []
    diagnostics = {'targets': 0, 'buyers': 0, 'packages': 0, 'illegal': 0, 'declined': 0, 'asset_conflicts': 0,
                   'facilitator_attempts': 0, 'facilitator_agreements': 0}
    from collections import Counter
    from .trade_finance_search import TradeSearchIntent, repair_record
    work = Counter({'participant_reports.'+c:0 for c in ('legal','repairable','unresolved','terminal','presentation')})
    canonical['_search_work_counts'] = work
    blocked = {}
    reserved = set()
    evaluation_snapshots = {}
    for entry in entries:
        player = player_by_id(canonical, entry["player_id"])
        if not player:
            continue
        if player.get("id") in recent_players:
            continue
        if f"player:{player['id']}" in reserved:
            continue
        seller = team_by_id(canonical, player.get("team_id"))
        if not seller:
            continue
        possible_buyers = buyer_teams_for_player(canonical, player)
        if involving_team_ids and seller['id'] not in involving_team_ids:
            possible_buyers = [b for b in possible_buyers if b['id'] in involving_team_ids]
        # Keep the strongest actual fits; the old shuffle discarded them on
        # most days. Explore more packages at the deadline, not looser consent.
        tail = possible_buyers[4:]
        rng.shuffle(tail)
        possible_buyers = possible_buyers[:4] + tail
        diagnostics['targets'] += 1
        accepted_for_player = False
        for buyer in possible_buyers[:18 if search_depth >= 3 else 12 if search_depth > 1 else 6]:
            if buyer["id"] == seller["id"]:
                continue
            diagnostics['buyers'] += 1
            breadth = 24 if search_depth >= 3 else 12 if search_depth > 1 else 5
            repairs = []
            packages = buyer_offer_package_options(canonical, buyer, seller, player, seed, max_results=breadth, max_player_options=12 if search_depth >= 3 else 9 if search_depth > 1 else 6, allow_new_pick_swaps=True,
                financial_search=True,repair_options=repairs,date=through_date,config=config)
            intent = TradeSearchIntent(seller['id'],buyer['id'],({'kind':'player','id':player['id'],'label':player['name']},),through_date,config)
            if search_depth > 1:
                for option in repairs:
                    record = repair_record(canonical,intent,option)
                    pair = tuple(trade_team_ids(record))
                    if pair not in blocked or record['_repair_rank'] < blocked[pair]['_repair_rank']:
                        blocked[pair] = record
                    if len(blocked) > 16:
                        del blocked[max(blocked,key=lambda k:blocked[k]['_repair_rank'])]
                work['repair_quotes_considered'] += len(repairs)
                work['repair_frontier_peak'] = max(work['repair_frontier_peak'],len(blocked))
            for package in packages[:breadth]:
                diagnostics['packages'] += 1
                buyer_assets = package.get("assets") or []
                pick_terms = package.get("pick_obligation_terms") or []
                evaluation_canonical = canonical_with_pending_pick_terms(canonical, pick_terms) if pick_terms else canonical
                report = evaluate_trade_decision(
                    evaluation_canonical,
                    seller["abbrev"],
                    buyer["abbrev"],
                    [{"kind": "player", "value": player["name"]}],
                    buyer_assets,
                    seed=seed,
                    date=through_date,
                    config=config,
                    context_ready=True,
                    search_only=True,
                )
                if pick_terms:
                    report = trade_result_with_pick_terms(report, pick_terms)
                candidate = candidate_from_decision(report)
                if candidate.get('legality', {}).get('status') != 'legal':
                    diagnostics['illegal'] += 1
                elif not ai_trade_candidate_accepted(canonical, candidate):
                    diagnostics['declined'] += 1
                if ai_trade_candidate_accepted(canonical, candidate):
                    proposal = candidate.get('proposal') or {}
                    human = set(canonical.get('_human_team_ids') or [])
                    involves_human = bool(human.intersection(trade_team_ids(proposal)))
                    assets = proposal_asset_identity_keys(candidate)
                    if reserve_assets and not involves_human and assets & reserved:
                        diagnostics['asset_conflicts'] += 1
                        continue
                    candidate = mark_ai_trade_accepted(candidate)
                    if entry.get('private_target'):
                        candidate['target_source'] = 'private_non_core_rotation_inquiry'
                    proposals.append(candidate)
                    evaluation_snapshots[candidate['proposal']['id']] = evaluation_canonical
                    if reserve_assets and not involves_human:
                        reserved |= assets
                    accepted_for_player = True
                    break
            if len(proposals) >= limit or accepted_for_player:
                break
        if len(proposals) >= limit:
            break
    if search_depth > 1:
        from .multi_team_trades import facilitator_candidates
        for failed in sorted(blocked.values(),key=lambda c:c['_repair_rank']):
            if diagnostics['facilitator_attempts'] >= 64:
                break
            for candidate in facilitator_candidates(canonical, failed, seed=seed, date=through_date,
                    limit=min(2, max(1, limit-len(proposals))), diagnostics=diagnostics,
                    include_presentation=False):
                keys = proposal_asset_identity_keys(candidate)
                involves_human = bool(set(canonical.get('_human_team_ids') or []) & set(trade_team_ids(candidate)))
                if reserve_assets and not involves_human and keys & reserved:
                    conflicts = [c for c in proposals if not set(canonical.get('_human_team_ids') or []) & set(trade_team_ids(c))
                                 and keys & proposal_asset_identity_keys(c)]
                    # Let a materially better joint agreement replace one
                    # weaker tentative deal, never two completed agreements.
                    if len(conflicts) != 1 or candidate['combined_score'] <= conflicts[0]['combined_score']+3:
                        continue
                    proposals.remove(conflicts[0])
                    reserved = set().union(*(proposal_asset_identity_keys(c) for c in proposals
                        if not set(canonical.get('_human_team_ids') or []) & set(trade_team_ids(c))))
                    diagnostics['facilitator_replacements'] = diagnostics.get('facilitator_replacements', 0)+1
                if len(proposals) >= limit:
                    continue
                proposals.append(candidate)
                evaluation_snapshots[candidate['proposal']['id']] = canonical
                if reserve_assets and not involves_human:
                    reserved |= keys
                if len(proposals) >= limit:
                    break
            if len(proposals) >= limit:
                break
        if any((c.get('proposal') or {}).get('transfers') for c in proposals):
            # Date-level execution has fewer slots than search. Joint deals
            # compete on approved value, rather than being starved at the end.
            proposals.sort(key=lambda c: (-float(c.get('combined_score') or 0), c['proposal']['id']))
    proposals = [
        prepare_ai_trade_candidate(evaluation_snapshots.get(candidate['proposal']['id'], canonical), candidate,
                                   seed=seed, date=through_date, config=config)
        for candidate in proposals
    ]
    return {
        "from_date": from_date,
        "through_date": through_date,
        "seed": seed,
        "proposal_count": len(proposals),
        "proposals": proposals,
        "search_diagnostics": {**diagnostics, "financial_work": dict(work)},
        "notes": "Deterministic AI-AI trade candidate generation. It suggests plausible proposals; application is separate.",
    }


RAISE_SCAN = 6  # a bidder's packages considered for a raise in each bidding round (TRADE-MARKET)


def target_driven_ai_trades(canonical: dict[str, Any], from_date: str, through_date: str, *, seed: int, limit: int,
                            config: dict[str, Any] | None, search_depth: int, reserve_assets: bool,
                            focus_team_ids: set[str] | None = None) -> dict[str, Any]:
    """AI-to-AI trade search that starts from each front office's targets (trade step 2, trade_targets.py).

    Each AI team's targets are matched to players (preferring players their teams would move), a pairing is pursued
    only when the buyer values the player about as much as the seller's asking price, packages are built toward that
    price and priced quickly from both sides, and only the few best go to the unchanged acceptance check
    (evaluate_trade_decision, then ai_trade_candidate_accepted). Accepted deals carry both teams' reasons.
    """
    from collections import Counter
    from . import trade_targets as tt
    from .trade_finance_search import TradeSearchIntent, repair_record
    config = config or default_transaction_model_config()
    depth = 2 if search_depth > 1 else 1
    rng = random.Random(f"{seed}:{from_date}:{through_date}:ai_trades:targets")
    human = set(canonical.get('_human_team_ids') or [])
    excluded = recently_traded_player_ids(canonical, through_date)
    buyer_ids = [team['id'] for team in sorted(canonical.get('teams', []), key=lambda t: t['id']) if team['id'] not in human]
    work = Counter({'participant_reports.'+c: 0 for c in ('legal', 'repairable', 'unresolved', 'terminal', 'presentation')})
    canonical['_search_work_counts'] = work
    diagnostics = {'targets': 0, 'buyers': 0, 'packages': 0, 'illegal': 0, 'declined': 0, 'asset_conflicts': 0,
                   'facilitator_attempts': 0, 'facilitator_agreements': 0, 'pairings': 0, 'prescreened_out': 0,
                   'team_targets': 0}
    from .multi_team_trades import near_miss, multi_team_repairs, user_absorber_offers, enrich_agreed_deals
    pairings = tt.target_pairings(canonical, buyer_ids, excluded, depth, config, rng)
    if focus_team_ids is not None:
        # TRADE-DEADLINE: the late deadline-day pass looks only at pairings the day's first deals changed (a team that
        # traded is the buyer or the seller): new needs, new salary filler, new room. The rest were priced already.
        pairings = [p for p in pairings if p['buyer_id'] in focus_team_ids or p['row']['team_id'] in focus_team_ids]
    diagnostics['team_targets'] = sum(len(tt.team_trade_targets(canonical, tid)) for tid in buyer_ids)
    # TRADE-MARKET (trade_market.py): dead negotiations and unsolicited offers for contenders' stars are screened out,
    # open negotiations go first, and players with two or more interested teams are shopped (bidding).
    from . import trade_market as tm
    market = tm.SearchMarket(canonical, through_date, depth)
    opinion_pairings = market.opinion_pairings(buyer_ids, excluded, pairings, config)
    if focus_team_ids is not None:
        opinion_pairings = [p for p in opinion_pairings
                            if p['buyer_id'] in focus_team_ids or p['row']['team_id'] in focus_team_ids]
    diagnostics['opinion_pairings'] = len(opinion_pairings)
    pairings = market.filter_pairings(pairings + opinion_pairings, diagnostics)
    diagnostics['pairings'] = len(pairings)
    proposals, evaluation_snapshots, reserved, blocked, satisfied = [], {}, set(), {}, set()
    near_misses = []  # two-team deals a third team might complete (trade step 4)
    from . import trade_counters as tc
    counters_left = [tc.COUNTERS_PER_SEARCH[depth]]

    def finalize(candidate, pairing, order, evaluation_canonical, war=None, sale=False):
        """Record an agreed target deal: both teams' reasons, the counter chain, the market's part. A shopped
        player's sale and the end of a multi-day negotiation go first in the day's deals (TRADE-FOLLOWUPS: an agreed
        market deal is executed the day it is agreed or cancelled with its reason)."""
        counter = candidate.pop('counter', None)
        candidate = mark_ai_trade_accepted(candidate)
        candidate['target_source'] = 'front_office_target'
        candidate['_search_order'] = -1 if (sale or market.open_negotiation(pairing)) else order
        reasons = tt.trade_reasons(canonical, pairing)
        if counter:
            reasons['counter'] = counter
            reasons['text'] = f"{reasons['text']} {counter['text']}"
            diagnostics['counter_deals'] = diagnostics.get('counter_deals', 0) + 1
        match = tc.seller_target_match(canonical, candidate, pairing['row']['team_id'])
        if match:
            reasons['seller_target_match'] = match
        neg = market.open_negotiation(pairing)
        if neg:
            reasons['negotiation'] = {'opened': neg.get('opened'), 'days': len(neg.get('rounds') or []) + 1,
                                      'key': neg.get('key')}
        if war:
            reasons['bidding_war'] = war
        candidate['trade_reasons'] = reasons
        proposals.append(candidate)
        evaluation_snapshots[candidate['proposal']['id']] = evaluation_canonical
        if reserve_assets:
            reserved.update(proposal_asset_identity_keys(candidate))
        satisfied.add(pairing['target']['id'])
        market.deal(pairing, candidate, sale=sale)

    def agreed(candidate, pairing, order, evaluation_canonical, options):
        """An agreed deal: a shopped player's offer goes into the seller's comparison (bidding), others close now."""
        if market.shopped(pairing):
            market.add_bid(pairing, candidate, options, evaluation_canonical, order)
            satisfied.add(pairing['target']['id'])
            diagnostics['market_bids'] = diagnostics.get('market_bids', 0) + 1
            return
        finalize(candidate, pairing, order, evaluation_canonical)

    def accepted_counter(candidate, pairing, order, evaluation_canonical, options=()):
        """A deal agreed after a counter (trade step 3): the pairing's reasons plus the counter in plain words."""
        agreed(candidate, pairing, order, evaluation_canonical, list(options))

    for order, pairing in enumerate(pairings):
        if len(proposals) >= limit:
            break
        row = pairing['row']
        target_id = pairing['target']['id']
        if target_id in satisfied or f"player:{row['id']}" in reserved:
            continue
        buyer = team_by_id(canonical, pairing['buyer_id'])
        seller = team_by_id(canonical, row['team_id'])
        player = row['player']
        diagnostics['targets'] += 1
        diagnostics['buyers'] += 1
        repairs = [] if depth > 1 else None
        intent = TradeSearchIntent(seller['id'], buyer['id'], ({'kind': 'player', 'id': player['id'], 'label': player['name']},),
                                   through_date, config)
        target_salary = current_salary(contract_for_player(canonical, player['id']))
        options = buyer_offer_packages_for_value(
            canonical, buyer, seller, max(1.0, pairing['ask']['ask']), target_salary, seed, {player['id']},
            max_results=24 if depth > 1 else 12, max_player_options=9 if depth > 1 else 6, return_options=True,
            allow_new_pick_swaps=True, intent=intent, repair_options=repairs,
            seller_view_outgoing=[{'kind': 'player', 'id': player['id']}])
        if repairs:
            for option in repairs:
                record = repair_record(canonical, intent, option)
                pair = tuple(trade_team_ids(record))
                if pair not in blocked or record['_repair_rank'] < blocked[pair]['_repair_rank']:
                    blocked[pair] = record
                if len(blocked) > 16:
                    del blocked[max(blocked, key=lambda k: blocked[k]['_repair_rank'])]
            work['repair_quotes_considered'] += len(repairs)
        missed = []
        packages = tt.ranked_packages(canonical, pairing, options, config, tt.PACKAGES_EVALUATED[depth], near=missed)
        diagnostics['prescreened_out'] += len(options) - len(packages)
        countered = None
        if missed and counters_left[0] > 0:
            # Trade step 3: no package met both prices, but the closest one is a near miss. The short side asks for
            # one change (trade_counters); the other side decides with its full check.
            counters_left[0] -= 1
            countered = tc.ai_counter(canonical, tt.near_miss_candidate(canonical, missed[0], config), seed=seed,
                                      date=through_date, config=config, fixed={('player', row['id'])},
                                      diagnostics=diagnostics, check_budget=tc.COUNTER_CHECKS_PER_SEARCH[depth])
        if countered is not None and not (reserve_assets and proposal_asset_identity_keys(countered) & reserved):
            accepted_counter(countered, pairing, order, canonical, options)
            continue
        for miss in missed:
            near_misses.append({'candidate': tt.near_miss_candidate(canonical, miss, config), 'order': order,
                                'trade_reasons': tt.trade_reasons(canonical, pairing)})
            market.observe(pairing, None, quick_nets=miss['nets'])
        for package in packages:
            diagnostics['packages'] += 1
            buyer_assets = package.get('assets') or []
            pick_terms = package.get('pick_obligation_terms') or []
            evaluation_canonical = canonical_with_pending_pick_terms(canonical, pick_terms) if pick_terms else canonical
            report = evaluate_trade_decision(
                evaluation_canonical, seller['abbrev'], buyer['abbrev'], [{'kind': 'player', 'value': player['id']}],
                buyer_assets, seed=seed, date=through_date, config=config, context_ready=True, search_only=True)
            if pick_terms:
                report = trade_result_with_pick_terms(report, pick_terms)
            candidate = candidate_from_decision(report)
            if candidate.get('legality', {}).get('status') != 'legal':
                diagnostics['illegal'] += 1
                continue
            if not ai_trade_candidate_accepted(canonical, candidate):
                diagnostics['declined'] += 1
                market.observe(pairing, candidate)
                countered = None
                if not pick_terms and counters_left[0] > 0 and tc.short_side(candidate, human) is not None:
                    counters_left[0] -= 1
                    countered = tc.ai_counter(canonical, candidate, seed=seed, date=through_date, config=config,
                                              fixed={('player', row['id'])}, diagnostics=diagnostics,
                                              check_budget=tc.COUNTER_CHECKS_PER_SEARCH[depth])
                if countered is not None and not (reserve_assets and proposal_asset_identity_keys(countered) & reserved):
                    accepted_counter(countered, pairing, order, canonical, options)
                    break
                if not pick_terms and near_miss(canonical, candidate):
                    near_misses.append({'candidate': candidate, 'trade_reasons': tt.trade_reasons(canonical, pairing),
                                        'order': order})
                continue
            keys = proposal_asset_identity_keys(candidate)
            if reserve_assets and keys & reserved:
                diagnostics['asset_conflicts'] += 1
                continue
            agreed(candidate, pairing, order, evaluation_canonical, options)
            break
    # TRADE-MARKET: shopped players. The seller compares every bid, the bidders raise in rounds, the best offer wins
    # (or the seller waits for its decision day).

    def bid_evaluate(bid, option):
        pairing = bid['pairing']
        buyer_team = team_by_id(canonical, pairing['buyer_id'])
        seller_team = team_by_id(canonical, pairing['row']['team_id'])
        assets = option.get('assets') or []
        pick_terms = option.get('pick_obligation_terms') or []
        evaluation_canonical = canonical_with_pending_pick_terms(canonical, pick_terms) if pick_terms else canonical
        diagnostics['market_raise_checks'] = diagnostics.get('market_raise_checks', 0) + 1
        report = evaluate_trade_decision(
            evaluation_canonical, seller_team['abbrev'], buyer_team['abbrev'],
            [{'kind': 'player', 'value': pairing['row']['id']}], assets, seed=seed, date=through_date, config=config,
            context_ready=True, search_only=True)
        if pick_terms:
            report = trade_result_with_pick_terms(report, pick_terms)
        result = candidate_from_decision(report)
        if result.get('legality', {}).get('status') != 'legal' or not ai_trade_candidate_accepted(canonical, result):
            return None
        bid['evaluation_canonical'] = evaluation_canonical
        return result

    def bid_raises(bid):
        """The bidder's other built packages, most valuable to the seller first, that its own quick price allows."""
        pairing = bid['pairing']
        seller_id, buyer_id = pairing['row']['team_id'], pairing['buyer_id']
        target = [{'kind': 'player', 'id': pairing['row']['id']}]
        buyer_team = team_by_id(canonical, buyer_id)
        current = proposal_asset_identity_keys(bid['candidate'])
        scored = []
        for index, option in enumerate(bid['options']):
            if index in bid['tried']:
                continue
            try:
                assets = [a for asset in option.get('assets') or [] for a in normalize_assets(canonical, buyer_team, [asset])]
            except ValueError:
                continue
            if not assets or not tt.package_fits_rules(canonical, pairing, assets):
                continue
            if {f"{a['kind']}:{a['id']}" for a in assets} <= current:
                continue
            buyer_raw = tt.quick_net(canonical, buyer_id, target, assets, config)
            if buyer_raw < -9.0 - tt.PRESCREEN_TOLERANCE:
                continue
            seller_raw = tt.quick_net(canonical, seller_id, assets, target, config)
            scored.append((-seller_raw, index, option))
        scored.sort(key=lambda item: item[:2])
        for _, index, _ in scored[:RAISE_SCAN]:
            bid['tried'].add(index)
        return [option for _, _, option in scored[:RAISE_SCAN]]

    for won in market.resolve_bidding(bid_evaluate, bid_raises):
        bid, war = won['bid'], won['war']
        keys = proposal_asset_identity_keys(bid['candidate'])
        if reserve_assets and keys & reserved:
            # TRADE-FOLLOWUPS: a sale is recorded as agreed only when it is one of today's deals. Before, the war was
            # marked sold here and the deal dropped, so the same sale was "agreed" again on later days.
            diagnostics['asset_conflicts'] += 1
            market.hold_sale(war, "the winning offer uses a player or pick already in another deal agreed today")
            continue
        # A sale goes in even past the search limit: it is first in the day's deals (the review keeps only its slots
        # and records a sale it has no room for as held, never as agreed).
        finalize(bid['candidate'], bid['pairing'], -1, bid['evaluation_canonical'],
                 war=war if len(war.get('bidders') or []) >= 2 else None, sale=True)
        war['proposal_id'] = bid['candidate']['proposal'].get('id')
    # Salary dumps (trade 2b): teams over the luxury tax shed salary to teams with room, paying picks if needed.
    dump_limit = max(1, -(-limit // 3))
    dumps_done, dump_teams = 0, set()
    if len(proposals) < limit:
        offers = tt.salary_dump_offers(canonical, buyer_ids, excluded, config)
        if focus_team_ids is not None:
            offers = [o for o in offers if o['seller_id'] in focus_team_ids or o['buyer_id'] in focus_team_ids]
        diagnostics['dump_offers'] = len(offers)
        for offer in offers:
            if len(proposals) >= limit or dumps_done >= dump_limit:
                break
            row = offer['row']
            if (offer['seller_id'] in dump_teams or offer['buyer_id'] in dump_teams
                    or f"player:{row['id']}" in reserved):
                continue
            seller = team_by_id(canonical, offer['seller_id'])
            buyer = team_by_id(canonical, offer['buyer_id'])
            back = offer.get('return') or []
            for assets in offer['packages']:
                seller_net = tt.quick_net(canonical, seller['id'], back, assets, config)
                buyer_net = tt.quick_net(canonical, buyer['id'], assets, back, config)
                if min(seller_net, buyer_net) < -9.0 - tt.PRESCREEN_TOLERANCE or seller_net + buyer_net < -2.0 - tt.PRESCREEN_TOLERANCE:
                    continue  # the absorber needs a bigger sweetener (next package) or the seller gives too much
                diagnostics['packages'] += 1
                specs = [{'kind': a['kind'], 'value': a['id']} for a in assets]
                report = evaluate_trade_decision(canonical, seller['abbrev'], buyer['abbrev'], specs,
                                                 [{'kind': a['kind'], 'value': a['id']} for a in back], seed=seed,
                                                 date=through_date, config=config, context_ready=True, search_only=True)
                candidate = candidate_from_decision(report)
                if candidate.get('legality', {}).get('status') != 'legal':
                    diagnostics['illegal'] += 1
                    continue
                if not ai_trade_candidate_accepted(canonical, candidate):
                    diagnostics['declined'] += 1
                    if near_miss(canonical, candidate):
                        near_misses.append({'candidate': candidate, 'trade_reasons': tt.dump_reasons(canonical, offer, assets),
                                            'order': len(pairings) + dumps_done})
                    seller_eval = next((e for e in candidate.get('evaluations') or []
                                        if e.get('perspective_team_id') == seller['id']), {})
                    if float(seller_eval.get('net_value') or 0.0) < -9.0:
                        break  # the next package only adds picks the seller already will not pay (trade step 4)
                    continue
                keys = proposal_asset_identity_keys(candidate)
                if reserve_assets and keys & reserved:
                    diagnostics['asset_conflicts'] += 1
                    break
                candidate = mark_ai_trade_accepted(candidate)
                candidate['target_source'] = 'salary_dump'
                candidate['_search_order'] = len(pairings) + dumps_done
                candidate['trade_reasons'] = tt.dump_reasons(canonical, offer, assets)
                proposals.append(candidate)
                evaluation_snapshots[candidate['proposal']['id']] = canonical
                if reserve_assets:
                    reserved |= keys
                dump_teams |= {seller['id'], buyer['id']}
                dumps_done += 1
                break
        diagnostics['dumps'] = dumps_done
    # Three- and four-team trades (trade step 4): a team with room absorbs the salary that kept a near-miss from
    # closing, paid in picks. Most-nearly-agreed deals first.
    near_misses.sort(key=lambda item: (-min(float(e.get('net_value') or 0) - float(e.get('acceptance_threshold') or 0)
                                            for e in item['candidate']['evaluations']),
                                       item['candidate']['proposal']['id']))
    diagnostics['near_misses'] = len(near_misses)
    # A team over the tax that is trading anyway may add a salary leg to a team with room (the Saric leg of the real
    # Cleveland / Sacramento / Chicago deal); the deal is replaced only when every team still accepts.
    for index, candidate in enrich_agreed_deals(canonical, proposals, seed=seed, date=through_date, config=config,
                                                depth=depth, diagnostics=diagnostics,
                                                reserved=reserved if reserve_assets else set()).items():
        if proposals[index].get('market_deal'):
            candidate['market_deal'] = proposals[index]['market_deal']  # still the same agreed market deal
        proposals[index] = candidate
        evaluation_snapshots[candidate['proposal']['id']] = canonical
    if len(proposals) < limit and near_misses:
        for candidate in multi_team_repairs(canonical, near_misses, seed=seed, date=through_date, config=config,
                                            depth=depth, diagnostics=diagnostics,
                                            reserved=reserved if reserve_assets else set(),
                                            limit=limit - len(proposals)):
            proposals.append(candidate)
            evaluation_snapshots[candidate['proposal']['id']] = canonical
    # Deals in the order the front offices pursued them: a three-team deal completed from a near-miss takes that
    # pairing's place. The market review keeps only its slots (save.queue_ai_recommendations), so a deal appended
    # last was always cut.
    proposals.sort(key=lambda c: c.get('_search_order', len(pairings) + limit))
    for candidate in proposals:
        candidate.pop('_search_order', None)
    user_offers = []
    if human and near_misses:
        # The same routes, offered to the human team as the team taking the salary (never automatic). Deals the AI
        # teams already made today are left out.
        taken = set().union(*(proposal_asset_identity_keys(c) for c in proposals)) if proposals else set()
        open_misses = [item for item in near_misses if not proposal_asset_identity_keys(item['candidate']) & taken]
        user_offers = user_absorber_offers(canonical, open_misses, seed=seed, date=through_date, config=config,
                                           diagnostics=diagnostics)
    if depth > 1 and len(proposals) < limit:
        from .multi_team_trades import facilitator_candidates
        for failed in sorted(blocked.values(), key=lambda c: c['_repair_rank']):
            if diagnostics['facilitator_attempts'] >= 64 or len(proposals) >= limit:
                break
            for candidate in facilitator_candidates(canonical, failed, seed=seed, date=through_date,
                    limit=min(2, max(1, limit-len(proposals))), diagnostics=diagnostics, include_presentation=False):
                keys = proposal_asset_identity_keys(candidate)
                if reserve_assets and keys & reserved:
                    continue
                proposals.append(candidate)
                evaluation_snapshots[candidate['proposal']['id']] = canonical
                if reserve_assets:
                    reserved |= keys
                if len(proposals) >= limit:
                    break
    proposals = [
        prepare_ai_trade_candidate(evaluation_snapshots.get(candidate['proposal']['id'], canonical), candidate,
                                   seed=seed, date=through_date, config=config)
        for candidate in proposals
    ]
    user_offers = [prepare_ai_trade_candidate(canonical, offer, seed=seed, date=through_date, config=config)
                   for offer in user_offers]
    from .front_office import with_market_reasons
    proposals = [with_market_reasons(canonical, candidate) for candidate in proposals]
    user_offers = [with_market_reasons(canonical, offer) for offer in user_offers]
    return {
        "from_date": from_date,
        "through_date": through_date,
        "seed": seed,
        "proposal_count": len(proposals),
        "proposals": proposals,
        "user_absorber_offers": user_offers,
        "market_updates": market.updates(),
        "search_diagnostics": {**diagnostics, "financial_work": dict(work)},
        "notes": "Target-driven AI-AI trade search: each front office pursues its own targets at the seller's price.",
    }


def ai_trade_candidate_accepted(canonical: dict[str, Any], candidate: dict[str, Any]) -> bool:
    if candidate.get("legality", {}).get("status") != "legal":
        return False
    if multi_team_participation_issues(canonical, candidate):
        return False
    if any(e.get('decision') in {'reject_premium_return', 'reject_roster_plan', 'reject_pick_investment'} for e in candidate.get('evaluations', [])):
        return False
    if (candidate.get('proposal') or {}).get('transfers'):
        ids = set(trade_team_ids(candidate))
        evaluations = candidate.get('evaluations') or []
        return ({e.get('perspective_team_id') for e in evaluations} == ids
                and all(e.get('accepted') for e in evaluations))
    if candidate.get("accepted_by_all"):
        return True
    from .team_planning import core_commitment
    proposal = candidate.get('proposal') or {}
    for side, tid in [('from_assets', proposal.get('from_team_id')), ('to_assets', proposal.get('to_team_id'))]:
        if any(a.get('kind') == 'player' and core_commitment(canonical, tid, a.get('id')) for a in proposal.get(side, [])):
            evaluation = next((e for e in candidate.get('evaluations', []) if e.get('perspective_team_id') == tid), {})
            core_commitment_reason = any(str(reason).startswith('Core commitment:') for reason in evaluation.get('decision_reasons', []))
            if core_commitment_reason or float(evaluation.get('net_value') or 0) < max(12., float(evaluation.get('outgoing_value') or 0)*.20):
                return False
    evaluations = candidate.get("evaluations") or []
    nets = [float(item.get("net_value") or 0.0) for item in evaluations]
    if not nets or min(nets) < -9.0 or sum(nets) < -2.0:
        return False
    # A modest absolute loss can still consume most of a small asset's value.
    # Keep room for disagreement without treating that as a marginal sacrifice.
    for evaluation in evaluations:
        outgoing = float(evaluation.get("outgoing_value") or 0.0)
        if outgoing > 0 and float(evaluation.get("net_value") or 0.0) < -max(1.5, outgoing * .5):
            return False
    proposal = candidate.get("proposal") or {}
    incoming_a = proposal.get("to_assets", [])
    incoming_b = proposal.get("from_assets", [])
    if max_player_value_from_assets(canonical, incoming_a) >= 72 and max_player_value_from_assets(canonical, incoming_b) < 55:
        return False
    if max_player_value_from_assets(canonical, incoming_b) >= 72 and max_player_value_from_assets(canonical, incoming_a) < 55:
        return False
    return True


def mark_ai_trade_accepted(candidate: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("accepted_by_all"):
        return candidate
    updated = json.loads(json.dumps(candidate))
    updated["accepted_by_all"] = True
    updated["ai_acceptance_override"] = {
        "status": "accepted_by_bounded_ai_discretion",
        "notes": "Both AI teams can talk themselves into this legal deal within bounded value-loss tolerance.",
    }
    for evaluation in updated.get("evaluations", []):
        if float(evaluation.get("net_value") or 0.0) >= -9.0:
            already_accepted = bool(evaluation.get('accepted'))
            evaluation["accepted"] = True
            if not already_accepted:
                evaluation["decision"] = "accept_bounded_ai_discretion"
                evaluation.setdefault("reasons", []).append("bounded_ai_discretion")
                evaluation['decision_reasons'] = [reason for reason in evaluation.get('decision_reasons', [])
                    if not reason.startswith('Net value ')]
                evaluation['decision_reasons'].append('Accepts a limited value shortfall within the existing negotiation safeguards.')
                evaluation['notes'] = str(evaluation.get('notes') or '').replace(' rejects:', ' accepts by bounded negotiation:', 1)
    return updated


def trade_evaluation_payload(canonical: dict[str, Any], evaluation: TradeEvaluation, config: dict[str, Any]) -> dict[str, Any]:
    payload = to_plain(evaluation)
    threshold = evaluation.acceptance_threshold
    if threshold is None:
        threshold = acceptance_threshold(canonical, evaluation.perspective_team_id, config)
    gap = round(float(evaluation.net_value) - threshold, 3)
    score = 0.0 if evaluation.legality_status != "legal" else clamp(50.0 + gap * 4.5, 0.0, 100.0)
    payload["team_abbrev"] = team_by_id(canonical, evaluation.perspective_team_id).get("abbrev")
    payload["acceptance_threshold"] = threshold
    payload["acceptance_gap"] = gap
    payload["acceptance_score"] = round(score, 2)
    return payload


def max_player_value_from_assets(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> float:
    values_by_player = player_asset_values_by_id(canonical)
    values = []
    for asset in assets:
        if asset.get("kind") == "player":
            player = player_by_id(canonical, asset.get("id"))
            values.append(float(values_by_player.get(asset.get("id"), fallback_asset_valuation(player)).get("player_value") or 0.0))
    return max(values or [0.0])


def apply_trade_to_save(
    save_path: str | Path,
    proposal_id: str,
    date: str = CANONICAL_START_DATE,
    *,
    canonical: dict[str, Any] | Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    date = date or CANONICAL_START_DATE
    path = Path(save_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            save = json.load(handle)
    else:
        save = {"version": "save_transaction_ledger_v1", "pending_trade_proposals": [], "transaction_logs": []}
    result = apply_trade_to_state(save, proposal_id, date=date, save_label=str(path), canonical=canonical, config=config)
    if result.get("status") == "applied":
        from .save import write_save

        write_save(path, save)
    return result


class _BilateralSettlementMaterialization:
    """One synchronous settlement's private universe, never a search approval.

    canonical_with_save writes these normalization fields on its save input.
    Salary/roster checks must keep those writes private; entitlement validation
    publishes them at the old authoritative overlay boundary, even if a later
    entitlement check rejects the proposal. Keep this list covered by the
    differential normalization tests when overlay helpers acquire new writes.
    """
    _NORMALIZATION_FIELDS = ('generated_health_profiles', 'health_states', 'injury_events',
                             'rotation_baselines', 'rotation_snapshots')

    def __init__(self, canonical, saved):
        self._source = canonical
        self._saved = saved
        self._active = None
        self._normalization = {}

    def active(self):
        if self._active is None:
            from .save import canonical_with_save
            private_save = copy_plain(self._saved)
            active = canonical_with_save(self._source, private_save)
            # Freeze the save effects before any derived validation view can
            # annotate its owned data. Do not retain the whole copied career.
            self._normalization = {
                key: copy_plain(private_save[key]) for key in self._NORMALIZATION_FIELDS
                if key in private_save and (key not in self._saved or private_save[key] != self._saved[key])
            }
            self._active = active
        return self._active

    def entitlement_active(self):
        active = self.active()
        for key, value in self._normalization.items():
            self._saved[key] = copy_plain(value)
        return active


def apply_trade_to_state(
    save: dict[str, Any],
    proposal_id: str,
    date: str = CANONICAL_START_DATE,
    *,
    save_label: str = "in_memory",
    canonical: dict[str, Any] | Any | None = None,
    config: dict[str, Any] | None = None,
    _full_reference: bool = False,
) -> dict[str, Any]:
    """Apply an authorized proposal to an already-loaded save (``_apply_trade_to_state``).

    TRADE-FOLLOWUPS: an agreed market deal (a shopped player's sale, the end of a negotiation, a target deal; tagged
    ``market_deal`` by the search) is either completed here or cancelled with the re-check's reason, recorded in the
    trade market's ledger the same day (trade_market.note_market_execution)."""
    proposal = next((item for item in save.get("pending_trade_proposals", [])
                     if (item.get("proposal") or {}).get("id") == proposal_id or item.get("id") == proposal_id), None)
    result = _apply_trade_to_state(save, proposal_id, date, save_label=save_label, canonical=canonical, config=config,
                                   _full_reference=_full_reference)
    if proposal and proposal.get("market_deal"):
        from .trade_market import note_market_execution
        note_market_execution(save, proposal, result, date)
    return result


def _apply_trade_to_state(
    save: dict[str, Any],
    proposal_id: str,
    date: str = CANONICAL_START_DATE,
    *,
    save_label: str = "in_memory",
    canonical: dict[str, Any] | Any | None = None,
    config: dict[str, Any] | None = None,
    _full_reference: bool = False,
) -> dict[str, Any]:
    """Apply an authorized proposal to an already-loaded save.

    Advancement can process a bundle of AI moves in one transaction without
    reloading and rewriting a multi-season save after every accepted trade.
    """
    date = date or CANONICAL_START_DATE
    proposal = next((item for item in save.get("pending_trade_proposals", []) if item.get("proposal", {}).get("id") == proposal_id or item.get("id") == proposal_id), None)
    if not proposal:
        return {
            "status": "not_found",
            "proposal_id": proposal_id,
            "save": save_label,
            "notes": "No pending proposal with this id exists in the save ledger. Generate/evaluate a proposal and add it to pending_trade_proposals before applying.",
        }
    if (proposal.get('proposal') or proposal).get('transfers'):
        from .multi_team_trades import apply_multi_team_trade_to_state
        return apply_multi_team_trade_to_state(save, proposal, date, canonical=canonical, config=config, save_label=save_label)
    if not trade_apply_authorized(proposal):
        return {
            "status": "not_applied_rejected",
            "proposal_id": proposal_id,
            "save": save_label,
            "notes": "Rejected saved or AI trade proposals cannot be applied. Rebuild or counter the offer instead.",
        }
    proposal_payload = proposal.get("proposal") or proposal
    if save.get("version") == "league_save_v1" and canonical is None:
        from .resource_paths import game_resource_root
        from .storage import JSON_FILENAME, load_universe_json
        try:
            canonical = load_universe_json(game_resource_root() / "data" / "canonical" / JSON_FILENAME)
        except (OSError, ValueError):
            return {
                "status": "not_applied_salary_legality", "proposal_id": proposal_id, "save": save_label,
                "legality": {"status": "manual_review_required", "issues": [],
                             "manual_review": ["Current payroll data is unavailable."]},
                "issues": [], "notes": "Trade was skipped because current payroll data could not be loaded.",
            }
    materialization = None
    if save.get("version") == "league_save_v1":
        validation_payload = {**proposal_payload, "pick_obligation_terms": proposal.get("pick_obligation_terms") or []}
        live_issues = trade_live_validation_issues(save, validation_payload, date)
        if live_issues:
            return {
                "status": "not_applied_stale_assets",
                "proposal_id": proposal_id,
                "save": save_label,
                "issues": live_issues,
                "notes": "Trade was skipped because at least one asset moved, became locked, or recently traded before this offer was applied.",
            }
        if not _full_reference and isinstance(canonical, dict):
            materialization = _BilateralSettlementMaterialization(canonical, save)
        salary_legality = saved_trade_salary_legality(
            save, proposal_payload, canonical, config, _materialization=materialization)
        if salary_legality["status"] != "legal":
            return {
                "status": "not_applied_salary_legality",
                "proposal_id": proposal_id,
                "save": save_label,
                "legality": salary_legality,
                "issues": salary_legality["issues"],
                "notes": "Trade was skipped because current salary legality no longer permits execution.",
            }
        from .trade_roster import live_roster_issues
        roster_issues = live_roster_issues(canonical, save, proposal_payload, candidate=proposal, config=config,
                                          _materialization=materialization)
        if roster_issues:
            return {'status': 'not_applied_roster_plan', 'proposal_id': proposal_id, 'save': save_label,
                    'issues': roster_issues, 'notes': 'An AI team must reconsider this offer against its current roster.'}
    log = TransactionLog(
        id=stable_id("transaction_log", proposal_id, date),
        date=date,
        transaction_type="trade",
        proposal_id=proposal_id,
        status="applied_to_save_ledger",
        teams=[proposal_payload.get("from_team_id"), proposal_payload.get("to_team_id")],
        assets={"from_assets": proposal_payload.get("from_assets", []), "to_assets": proposal_payload.get("to_assets", [])},
        evaluations=proposal.get("evaluations", []),
        source_ids=["src_transaction_model_config_v1"],
        notes="Applied to save ledger only. Canonical preseason data remains immutable.",
    )
    if save.get("version") == "league_save_v1":
        from_team_id = proposal_payload.get("from_team_id")
        to_team_id = proposal_payload.get("to_team_id")
        from .save import canonical_with_save
        from .pick_presentation import materialize_nested_inputs

        live = (materialization.entitlement_active() if materialization is not None
                else canonical_with_save(canonical, save) if canonical is not None else None)
        bundles = materialize_nested_inputs(live) if live is not None else {}
        bundled_ids = {oid for bundle in bundles.values() for oid in bundle["obligation_ids"]}
        for side, offering in (("from_assets", from_team_id), ("to_assets", to_team_id)):
            for asset in proposal_payload.get(side, []):
                if asset.get("kind") == "pick_swap" and asset.get("id") in bundled_ids:
                    return {"status": "not_applied_stale_assets", "issues": ["Trade the nested entitlement as one pick asset; this offer lists a component right."]}
                expected = asset.get("nested_entitlement") or (asset.get("pick_presentation") or {}).get("nested_entitlement")
                current = bundles.get(asset.get("id")) if asset.get("kind") == "pick" else None
                if expected and (not current or expected["obligation_ids"] != current["obligation_ids"]):
                    return {"status": "not_applied_stale_assets", "issues": ["The nested entitlement changed after this offer was created."]}
                if current and current["rights_holder_team_id"] != offering:
                    return {"status": "not_applied_stale_assets", "issues": ["The offering team no longer owns this nested entitlement."]}
        if live is not None:
            live_terms = {row["id"]: row for row in live.get("pick_obligations", [])}
            for row in save.get("pick_obligations", []):
                for field in ("nested_input", "nested_other_input", "nested_other_pick_id", "nested_anchor_pick_id", "allocation_slot_pick_ids"):
                    if field in live_terms.get(row.get("id"), {}):
                        row[field] = deepcopy(live_terms[row["id"]][field])
        def transfer_entitlement(asset, destination):
            bundle = bundles.get(asset["id"])
            if not bundle:
                return
            for obligation_id in bundle["obligation_ids"]:
                update_retraded_pick_swap_obligation(save, obligation_id, destination, date)
        for asset in proposal_payload.get("from_assets", []):
            if asset.get("kind") == "player":
                save.setdefault("roster_overrides", {})[asset["id"]] = to_team_id
            if asset.get("kind") == "pick":
                save.setdefault("draft_pick_overrides", {})[asset["id"]] = to_team_id
                update_retraded_pick_obligation(save, asset["id"], to_team_id, date)
                transfer_entitlement(asset, to_team_id)
            if asset.get("kind") == "pick_swap":
                update_retraded_pick_swap_obligation(save, asset["id"], to_team_id, date)
        for asset in proposal_payload.get("to_assets", []):
            if asset.get("kind") == "player":
                save.setdefault("roster_overrides", {})[asset["id"]] = from_team_id
            if asset.get("kind") == "pick":
                save.setdefault("draft_pick_overrides", {})[asset["id"]] = from_team_id
                update_retraded_pick_obligation(save, asset["id"], from_team_id, date)
                transfer_entitlement(asset, from_team_id)
            if asset.get("kind") == "pick_swap":
                update_retraded_pick_swap_obligation(save, asset["id"], from_team_id, date)
        for team_id in [from_team_id, to_team_id]:
            if team_id:
                save.setdefault("rotation_snapshots", {}).pop(team_id, None)
        apply_pick_obligation_terms_to_save(save, proposal_payload, proposal.get("pick_obligation_terms") or [], date)
        from .save import add_league_event, add_news

        headline = trade_headline_from_payload(proposal_payload)
        add_news(save, "trade", headline, date_value=date)
        add_league_event(
            save,
            "trade",
            headline,
            date_value=date,
            team_ids=[from_team_id, to_team_id],
            player_ids=trade_player_ids(proposal_payload),
            importance=0.74,
            details=trade_event_details_from_payload(proposal_payload),
        )
        queue_press_event_if_user_involved(save, "trade", headline, [from_team_id, to_team_id], date)
    log_record = to_plain(log)
    if proposal.get("trade_reasons"):
        # Why each side made the deal, in plain words (AI target search and draft-night trades, trade step 2).
        log_record["trade_reasons"] = deepcopy(proposal["trade_reasons"])
    save.setdefault("transaction_logs", []).append(log_record)
    save["pending_trade_proposals"] = [
        item
        for item in save.get("pending_trade_proposals", [])
        if (item.get("proposal", {}).get("id") or item.get("id")) != proposal_id
    ]
    pruned = prune_trade_offers_touching_assets(save, proposal_asset_identity_keys(proposal), exclude_proposal_id=proposal_id)
    return {"status": "applied", "save": save_label, "transaction_log": deepcopy(log_record), "pruned": pruned}


def saved_trade_salary_legality(
    save: dict[str, Any],
    proposal: dict[str, Any],
    canonical: dict[str, Any] | Any | None = None,
    config: dict[str, Any] | None = None,
    *,
    _materialization: _BilateralSettlementMaterialization | None = None,
) -> dict[str, Any]:
    """Recheck payroll only, without reconsidering the saved basketball consent."""
    if not any(asset.get("kind") == "player" for side in ("from_assets", "to_assets") for asset in proposal.get(side, [])):
        return {"status": "legal", "issues": [], "manual_review": []}
    if canonical is None:
        # Standalone/legacy callers have no universe argument. Read game data,
        # never a user save directory, and still overlay the current save below.
        from .resource_paths import game_resource_root
        from .storage import JSON_FILENAME, load_universe_json

        try:
            canonical = load_universe_json(game_resource_root() / "data" / "canonical" / JSON_FILENAME)
        except (OSError, ValueError):
            return {"status": "manual_review_required", "issues": [], "manual_review": ["Current payroll data is unavailable."]}
    from .save import canonical_with_save

    # Overlaying a save also refreshes rotation snapshots on its input. Salary
    # validation must not refresh the caller's state when the trade is rejected.
    try:
        active = (_materialization.active() if _materialization is not None
                  else canonical_with_save(canonical, copy_plain(save)))
    except (OSError, ValueError):
        return {"status": "manual_review_required", "issues": [],
                "manual_review": ["Current payroll data is unavailable for this save's starting roster."]}
    current_proposal = TradeProposal(
        id=proposal.get("id", ""), date=proposal.get("date", ""),
        from_team_id=proposal.get("from_team_id"), to_team_id=proposal.get("to_team_id"),
        from_assets=proposal.get("from_assets", []), to_assets=proposal.get("to_assets", []),
        status=proposal.get("status", "evaluated"), source_ids=proposal.get("source_ids", []),
        notes=proposal.get("notes", ""),
    )
    return trade_salary_legality(active, current_proposal, config or default_transaction_model_config())


def trade_apply_authorized(proposal: dict[str, Any]) -> bool:
    if (proposal.get("legality") or {}).get("status") != "legal":
        return False
    if proposal.get("accepted_by_all"):
        return True
    context = proposal.get("offer_context") or {}
    if context.get("status") == "finder_offer_pending_user_acceptance":
        partner_id = context.get("finder_partner_team_id")
        return bool(
            context.get("finder_partner_accepted")
            and partner_id
            and any(
                evaluation.get("perspective_team_id") == partner_id and evaluation.get("accepted")
                for evaluation in proposal.get("evaluations", [])
            )
        )
    return bool(
        context.get("status") == "user_override_pending_apply"
        and context.get("created_by_user")
        and context.get("override_team_id")
    )


def update_retraded_pick_obligation(save: dict[str, Any], pick_id: str, new_owner_team_id: str | None, date: str) -> None:
    if not pick_id or not new_owner_team_id:
        return
    locked = set(save.setdefault("locked_pick_assets", []))
    for obligation in save.get("pick_obligations", []):
        if obligation.get("type") != "protected_pick" or obligation.get("primary_pick_id") != pick_id:
            continue
        if obligation.get("status", "active") not in {"active", "pending_resolution"}:
            continue
        sender = obligation.get("sender_team_id")
        if new_owner_team_id == sender:
            obligation["status"] = "resolved_reacquired_by_sender"
            obligation["resolved_date"] = date
            obligation["notes"] = f"{obligation.get('notes', '')} Sender reacquired protected-pick rights before resolution; fallback unlocked.".strip()
            for fallback_id in obligation.get("fallback_pick_ids") or []:
                locked.discard(fallback_id)
        else:
            obligation["receiver_team_id"] = new_owner_team_id
            obligation["receiver_updated_date"] = date
            obligation["notes"] = f"{obligation.get('notes', '')} Protected-pick rights were re-traded before resolution.".strip()
    save["locked_pick_assets"] = sorted(locked)


def update_retraded_pick_swap_obligation(save: dict[str, Any], obligation_id: str, new_holder_team_id: str | None, date: str) -> bool:
    if not obligation_id or not new_holder_team_id:
        return False
    for obligation in save.get("pick_obligations", []):
        if obligation.get("id") != obligation_id or obligation.get("type") != "pick_swap":
            continue
        if obligation.get("status", "active") not in {"active", "pending_resolution"}:
            return False
        old_holder = obligation.get("current_rights_holder_team_id") or obligation.get("original_rights_holder_team_id")
        obligation["current_rights_holder_team_id"] = new_holder_team_id
        obligation["rights_updated_date"] = date
        history = obligation.setdefault("transfer_history", [])
        history.append({"date": date, "from_team_id": old_holder, "to_team_id": new_holder_team_id})
        obligation["notes"] = f"{obligation.get('notes', '')} Pick-swap right was re-traded before resolution.".strip()
        return True
    return False


def active_pick_obligations(canonical_or_save: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in canonical_or_save.get("pick_obligations", [])
        if item.get("status", "active") in {"active", "pending_resolution"}
    ]


def pick_lookup_for_obligation(canonical_or_save: dict[str, Any], proposal: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    picks = {pick.get("id"): pick for pick in canonical_or_save.get("draft_picks", []) if pick.get("id")}
    for asset in trade_assets(proposal or {}):
        if asset.get("kind") == "pick" and asset.get("id"):
            picks.setdefault(asset.get("id"), asset)
    return picks


def protected_pick_fallback_is_distinct(primary: dict[str, Any] | None, fallback: dict[str, Any] | None) -> bool:
    """Return whether fallback collateral is a different underlying draft asset."""
    if not primary or not fallback:
        return False
    if primary.get("id") == fallback.get("id"):
        return False
    identity = lambda pick: (
        str(pick.get("season") or ""),
        int(pick.get("round") or 0),
        pick.get("original_team_id"),
    )
    primary_identity = identity(primary)
    fallback_identity = identity(fallback)
    return not (
        all(primary_identity)
        and all(fallback_identity)
        and primary_identity == fallback_identity
    )


def pick_obligation_validation_errors(canonical_or_save: dict[str, Any], proposal: dict[str, Any] | None, term: dict[str, Any]) -> list[str]:
    if not term or term.get("type") in {None, "unprotected"}:
        return []
    errors: list[str] = []
    picks = pick_lookup_for_obligation(canonical_or_save, proposal)
    has_pick_table = bool(canonical_or_save.get("draft_picks"))
    locked = set(canonical_or_save.get("locked_pick_assets") or [])
    if term.get("type") == "protected_pick":
        from .pick_rules import protection_bounds

        try:
            protection_bounds(term)
        except ValueError as error:
            errors.append(str(error))
        primary_id = term.get("primary_pick_id")
        fallback_ids = [pick_id for pick_id in term.get("fallback_pick_ids") or [] if pick_id]
        if not primary_id:
            errors.append("protected pick is missing a primary pick")
        if not fallback_ids:
            errors.append("protected pick is missing fallback collateral")
        if len(fallback_ids) != len(set(fallback_ids)):
            errors.append("protected pick has duplicate fallback collateral")
        if primary_id and primary_id in fallback_ids:
            errors.append("protected pick fallback cannot be the same pick")
        primary = picks.get(primary_id)
        if primary_id and not primary and has_pick_table:
            errors.append("protected pick primary does not exist")
        primary_round = int((primary or {}).get("round") or term.get("primary_round") or 0)
        try:
            protection_bounds({**term, "round": primary_round})
        except ValueError as error:
            errors.append(str(error))
        primary_year = pick_season_start(primary or {"season": term.get("season")}) or pick_season_start({"season": term.get("season")}) or 0
        for fallback_id in fallback_ids:
            fallback = picks.get(fallback_id)
            if not fallback:
                if not has_pick_table:
                    continue
                errors.append(f"fallback pick {fallback_id} does not exist")
                continue
            fallback_round = int(fallback.get("round") or 0)
            if primary_round and fallback_round and fallback_round != primary_round:
                errors.append("protected pick fallback must match the primary pick round")
            if primary and not protected_pick_fallback_is_distinct(primary, fallback):
                errors.append("protected pick fallback cannot represent the same underlying draft pick")
            fallback_year = pick_season_start(fallback) or 0
            if primary_year and fallback_year and fallback_year < primary_year:
                errors.append("protected pick fallback cannot be earlier than the primary pick")
            if fallback_id in locked and fallback_id not in set(term.get("_existing_fallback_pick_ids") or []):
                errors.append(f"fallback pick {fallback_id} is already locked")
            if fallback.get("_obligation_locked"):
                errors.append(f"fallback pick {fallback_id} is already locked")
        return sorted(dict.fromkeys(errors))
    if term.get("type") == "pick_swap":
        pick_a_id = term.get("team_a_pick_id") or term.get("primary_pick_id")
        pick_b_id = term.get("team_b_pick_id") or term.get("counterparty_pick_id")
        if not pick_a_id or not pick_b_id:
            errors.append("pick swap requires two subject picks")
        if pick_a_id and pick_b_id and pick_a_id == pick_b_id:
            errors.append("pick swap cannot use the same pick twice")
        pick_a = picks.get(pick_a_id)
        pick_b = picks.get(pick_b_id)
        if pick_a_id and not pick_a and has_pick_table:
            errors.append("pick swap first pick does not exist")
        if pick_b_id and not pick_b and has_pick_table:
            errors.append("pick swap second pick does not exist")
        if pick_a and pick_b:
            if str(pick_a.get("season") or "") != str(pick_b.get("season") or ""):
                errors.append("pick swap picks must be in the same season")
            if int(pick_a.get("round") or 0) != int(pick_b.get("round") or 0):
                errors.append("pick swap picks must be in the same round")
        if not (term.get("current_rights_holder_team_id") or term.get("original_rights_holder_team_id") or term.get("receiver_team_id")):
            errors.append("pick swap is missing a rights holder")
        pool = term.get("comparison_pool_pick_ids") or []
        if pool:
            if len(pool) < 2 or len(pool) != len(set(pool)):
                errors.append("pick comparison pool requires distinct underlying picks")
            for pick_id in pool:
                subject = picks.get(pick_id)
                if not subject and has_pick_table:
                    errors.append("pick comparison pool subject does not exist")
                if subject and pick_a and (str(subject.get("season")) != str(pick_a.get("season")) or int(subject.get("round") or 0) != int(pick_a.get("round") or 0)):
                    errors.append("pick comparison pool must use one season and round")
            if not term.get("comparison_holder_team_id") or not term.get("comparison_counterparty_team_id") or term["comparison_holder_team_id"] == term["comparison_counterparty_team_id"]:
                errors.append("pick comparison pool requires two distinct comparison owners")
        return sorted(dict.fromkeys(errors))
    return []


def validate_pick_obligation_term(canonical_or_save: dict[str, Any], proposal: dict[str, Any] | None, term: dict[str, Any]) -> bool:
    return not pick_obligation_validation_errors(canonical_or_save, proposal, term)


def trade_transfers(proposal: Any) -> list[dict[str, Any]]:
    payload = proposal.get('proposal') or proposal if isinstance(proposal, dict) else vars(proposal)
    if payload.get('transfers'):
        return payload['transfers']
    return [{'from_team_id': payload.get('from_team_id'), 'to_team_id': payload.get('to_team_id'),
             'assets': payload.get('from_assets') or []},
            {'from_team_id': payload.get('to_team_id'), 'to_team_id': payload.get('from_team_id'),
             'assets': payload.get('to_assets') or []}]


def trade_team_ids(proposal: Any) -> list[str]:
    return sorted({t[key] for t in trade_transfers(proposal) for key in ('from_team_id', 'to_team_id') if t.get(key)})


def trade_assets(proposal: Any) -> list[dict[str, Any]]:
    return [a for transfer in trade_transfers(proposal) for a in transfer['assets']]


def trade_offer_fingerprint(offer: dict[str, Any]) -> str:
    """Stable identity for the same exchange, independent of proposal IDs or asset order."""
    payload = offer.get("proposal") or offer
    flows: dict[str, dict[str, list[str]]] = {}
    for transfer in trade_transfers(payload):
        from_team = str(transfer.get("from_team_id") or "")
        to_team = str(transfer.get("to_team_id") or "")
        if not from_team or not to_team:
            continue
        outgoing = flows.setdefault(from_team, {"sends": [], "receives": []})
        incoming = flows.setdefault(to_team, {"sends": [], "receives": []})
        for asset in transfer.get("assets") or []:
            kind = str(asset.get("kind") or "").lower()
            identifier = asset.get("id") or asset.get("player_id") or asset.get("pick_id") or asset.get("value")
            identity = f"{kind}:{identifier}" if kind and identifier is not None else json.dumps(asset, sort_keys=True, separators=(",", ":"), default=str)
            outgoing["sends"].append(identity)
            incoming["receives"].append(identity)
    if not flows:
        return f"proposal:{payload.get('id') or offer.get('id') or id(offer)}"
    normalized_flows = [
        (team_id, tuple(sorted(flow["sends"])), tuple(sorted(flow["receives"])))
        for team_id, flow in sorted(flows.items())
    ]
    terms = payload.get("pick_obligation_terms") or offer.get("pick_obligation_terms") or []
    # Term order is presentation-only; fallback order inside a term is meaningful.
    terms = sorted(terms, key=lambda term: json.dumps(term, sort_keys=True, default=str))
    signature = json.dumps({"flows": normalized_flows, "terms": terms}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()


def trade_team_flows(proposal: Any) -> list[tuple[str, list, list]]:
    transfers = trade_transfers(proposal)
    return [(tid, [a for t in transfers if t['from_team_id'] == tid for a in t['assets']],
             [a for t in transfers if t['to_team_id'] == tid for a in t['assets']]) for tid in trade_team_ids(proposal)]


def multi_team_participation_issues(canonical: dict[str, Any], proposal: Any) -> list[str]:
    payload = proposal.get('proposal') or proposal if isinstance(proposal, dict) else vars(proposal)
    if not payload.get('transfers'):
        return []
    issues = []
    for tid, outgoing, incoming in trade_team_flows(proposal):
        name = (team_by_id(canonical, tid) or {}).get('abbrev', tid)
        if not outgoing:
            issues.append(f'{name} must send at least one asset in a multi-team trade.')
        if not incoming:
            issues.append(f'{name} must receive at least one asset in a multi-team trade.')
    return issues


def trade_player_ids(proposal: dict[str, Any]) -> list[str]:
    return sorted(
        {
            asset.get("id")
            for asset in trade_assets(proposal)
            if asset.get("kind") == "player" and asset.get("id")
        }
    )


def proposal_asset_identity_keys(proposal: dict[str, Any]) -> set[str]:
    payload = proposal.get("proposal") or proposal
    keys: set[str] = set()
    for asset in trade_assets(payload):
        kind = str(asset.get("kind") or "").lower()
        identifier = asset.get("id") or asset.get("player_id") or asset.get("pick_id") or asset.get("value")
        if kind and identifier:
            keys.add(f"{kind}:{identifier}")
    for term in proposal.get('pick_obligation_terms') or []:
        if term.get('type') == 'pick_swap' and term.get('pending_asset_grant'):
            keys.update(f'pick:{pid}' for pid in
                        (term.get('team_a_pick_id'), term.get('team_b_pick_id')) if pid)
        elif term.get('type') == 'protected_pick':
            keys.update(f'pick:{pid}' for pid in term.get('fallback_pick_ids', []) if pid)
    return keys


def prune_trade_offers_touching_assets(save: dict[str, Any], asset_keys: set[str], exclude_proposal_id: str | None = None) -> dict[str, int]:
    if not asset_keys:
        return {"pending_trade_proposals": 0, "user_trade_offers": 0}
    pending_before = len(save.get("pending_trade_proposals", []))
    save["pending_trade_proposals"] = [
        item
        for item in save.get("pending_trade_proposals", [])
        if ((item.get("proposal") or {}).get("id") or item.get("id")) == exclude_proposal_id
        or not proposal_asset_identity_keys(item).intersection(asset_keys)
    ]
    user_pruned = 0
    for offer in save.get("user_trade_offers", []):
        offer_id = ((offer.get("proposal") or {}).get("id") or offer.get("id"))
        if offer_id == exclude_proposal_id:
            continue
        context = offer.setdefault("offer_context", {})
        if context.get("status") != "pending_user_review":
            continue
        if proposal_asset_identity_keys(offer).intersection(asset_keys):
            context["status"] = "stale_asset_moved"
            context["stale_reason"] = "An asset in this offer moved, was waived, or became unavailable."
            user_pruned += 1
    return {"pending_trade_proposals": pending_before - len(save.get("pending_trade_proposals", [])), "user_trade_offers": user_pruned}


def transaction_log_player_ids(log: dict[str, Any]) -> set[str]:
    assets = log.get("assets") or {}
    return {
        asset.get("id")
        for asset in trade_assets(assets)
        if asset.get("kind") == "player" and asset.get("id")
    }


def transaction_log_flows(log: dict[str, Any]) -> list[tuple[str, list, list]]:
    assets = log.get('assets') or {}
    if assets.get('transfers'):
        return trade_team_flows(assets)
    teams = log.get('teams') or []
    return trade_team_flows({**assets, 'from_team_id': teams[0], 'to_team_id': teams[1]}) if len(teams) == 2 else []


def transaction_log_signed_player_ids(log: dict[str, Any]) -> set[str]:
    assets = log.get("assets") or {}
    player_id = assets.get("player_id") or log.get("player_id")
    return {player_id} if player_id else set()


def recently_traded_player_ids(canonical_or_save: dict[str, Any], as_of_date: str | None = None, days: int = RECENTLY_TRADED_DAYS) -> set[str]:
    current = parse_iso_date(as_of_date or ((canonical_or_save.get("meta") or {}).get("current_date")) or CANONICAL_START_DATE)
    if current is None:
        return set()
    recent: set[str] = set()
    for entry in canonical_or_save.get('waiver_wire', []):
        if entry.get('status') == 'claimed':
            claimed = parse_iso_date(entry.get('resolved_date'))
            if claimed is not None:
                start = claimed if claimed.month < 7 or claimed.month >= 10 else date(claimed.year, 10, 1)
                if current < start or (current - start).days < 30:
                    recent.add(entry['player_id'])
    for log in canonical_or_save.get("transaction_logs", []):
        if log.get("transaction_type") != "trade" or log.get("status") not in {"applied_to_save_ledger", "applied"}:
            continue
        traded_on = parse_iso_date(log.get("date"))
        if traded_on is None:
            continue
        elapsed = (current - traded_on).days
        if 0 <= elapsed < int(days):
            recent.update(transaction_log_player_ids(log))
    return recent


# KEEP-STARS: an AI team holds a player it acquired by trade for about six months before trading him again, unless he
# is the centre of a salary-matching deal (the team's highest-paid outgoing player, with at least half his salary
# coming back in players). The real CBA only bars re-trading for 60 days in an aggregated deal (RECENTLY_TRADED_DAYS
# here; Larry Coon's CBA FAQ, "aggregation" rule); real front offices almost never flip a newly acquired player in a
# salary dump, while the two-season test had Kobe Sanders and Jerquarius Stanback moved on after 78 and 117 days.
# Applies only to trades among AI teams; the user's team keeps the real rules.
RE_TRADE_HOLD_DAYS = 182
RE_TRADE_HOLD_SALARY_BACK = 0.5


def re_trade_hold(canonical: dict[str, Any], as_of_date: str | None = None) -> dict[str, str]:
    """{player_id: team_id} for players an AI team acquired by trade in the last 182 days and still has."""
    current = parse_iso_date(as_of_date or ((canonical.get("meta") or {}).get("current_date")) or CANONICAL_START_DATE)
    if current is None:
        return {}
    key = (current.isoformat(), len(canonical.get("transaction_logs") or []))
    memo = canonical.get("_re_trade_hold_memo")
    if memo and memo[0] == key and memo[1] is canonical.get("players"):
        return memo[2]
    human = set(canonical.get("_human_team_ids") or [])
    team_of = {p.get("id"): p.get("team_id") for p in canonical.get("players", [])}
    held: dict[str, str] = {}
    earliest = (current - timedelta(days=RE_TRADE_HOLD_DAYS - 1)).isoformat()
    for log in canonical.get("transaction_logs", []) or []:
        if (log.get("transaction_type") != "trade" or str(log.get("date") or "") < earliest
                or log.get("status") not in {"applied_to_save_ledger", "applied"}):
            continue
        traded_on = parse_iso_date(log.get("date"))
        if traded_on is None or not 0 <= (current - traded_on).days < RE_TRADE_HOLD_DAYS:
            continue
        for team_id, _, incoming in transaction_log_flows(log):
            if team_id in human:
                continue
            for asset in incoming:
                if asset.get("kind") == "player" and team_of.get(asset.get("id")) == team_id:
                    held[asset["id"]] = team_id
    canonical["_re_trade_hold_memo"] = (key, canonical.get("players"), held)
    return held


def re_trade_hold_player_ids(canonical: dict[str, Any], as_of_date: str | None = None) -> set[str]:
    return set(re_trade_hold(canonical, as_of_date))


def re_trade_hold_issues(canonical: dict[str, Any], proposal: Any) -> list[str]:
    """Players moved against the re-trade hold in an all-AI trade (see RE_TRADE_HOLD_DAYS)."""
    if set(trade_team_ids(proposal)) & set(canonical.get("_human_team_ids") or []):
        return []
    held = re_trade_hold(canonical, transaction_reference_date(canonical, proposal))
    if not held:
        return []

    def salary(asset: dict[str, Any]) -> float:
        return float(current_salary(contract_for_player(canonical, asset.get("id"))) or 0.0)

    issues = []
    for team_id, outgoing, incoming in trade_team_flows(proposal):
        players_out = [a for a in outgoing if a.get("kind") == "player"]
        for asset in players_out:
            if held.get(asset.get("id")) != team_id:
                continue
            mine = salary(asset)
            top = mine >= max(salary(a) for a in players_out) - 1.0
            back = sum(salary(a) for a in incoming if a.get("kind") == "player")
            if not (top and back >= RE_TRADE_HOLD_SALARY_BACK * mine):
                issues.append(f"{asset.get('label', asset.get('id'))} was acquired by trade less than six months ago "
                              "and can only be moved as the centre of a salary-matching deal.")
    return issues


def recently_signed_player_ids(canonical_or_save: dict[str, Any], as_of_date: str | None = None) -> set[str]:
    current = parse_iso_date(as_of_date or ((canonical_or_save.get("meta") or {}).get("current_date")) or CANONICAL_START_DATE)
    if current is None:
        return set()
    # FA-REAL: a contract that records the date he can first be traded (cap_ledger.trade_eligible_date: December 15,
    # January 15 after a big Bird raise over the cap, or three months) uses that date. Signings without one keep the
    # older December 1 rule.
    dated: dict[str, str] = {}
    for contract in canonical_or_save.get("contracts", []) or []:
        if contract.get("trade_eligible_date") and contract.get("player_id"):
            dated[str(contract["player_id"])] = str(contract["trade_eligible_date"])
    for player_id, override in (canonical_or_save.get("contract_overrides") or {}).items():
        if override and override.get("trade_eligible_date"):
            dated[str(player_id)] = str(override["trade_eligible_date"])
    restricted: set[str] = {player_id for player_id, eligible in dated.items()
                            if (parse_iso_date(eligible) or current) > current}
    for log in canonical_or_save.get("transaction_logs", []):
        if log.get("transaction_type") not in SIGNING_TRANSACTION_TYPES or log.get("status") not in {"applied_to_save_ledger", "applied"}:
            continue
        signed_on = parse_iso_date(log.get("date"))
        if signed_on is None:
            continue
        unlock = date(signed_on.year, RECENTLY_SIGNED_UNLOCK_MONTH, RECENTLY_SIGNED_UNLOCK_DAY)
        if signed_on <= current < unlock:
            restricted.update(pid for pid in transaction_log_signed_player_ids(log) if str(pid) not in dated)
    return restricted


def trade_live_validation_issues(save: dict[str, Any], proposal: dict[str, Any], date_value: str | None = None) -> list[str]:
    issues: list[str] = []
    roster_overrides = save.get("roster_overrides") or {}
    pick_overrides = save.get("draft_pick_overrides") or {}
    swap_right_holders = {
        obligation.get("id"): obligation.get("current_rights_holder_team_id") or obligation.get("original_rights_holder_team_id") or obligation.get("receiver_team_id")
        for obligation in save.get("pick_obligations", [])
        if obligation.get("type") == "pick_swap" and obligation.get("status", "active") in {"active", "pending_resolution"}
    }
    proposal_swap_grantors: dict[str, str | None] = {}
    for term in proposal.get("pick_obligation_terms") or []:
        if term.get("type") == "pick_swap" and term.get("id"):
            proposal_swap_grantors[term.get("id")] = term.get("sender_team_id") or term.get("counterparty_team_id")
            swap_right_holders.setdefault(
                term.get("id"),
                term.get("current_rights_holder_team_id") or term.get("original_rights_holder_team_id") or term.get("receiver_team_id"),
            )
    locked_picks = set(save.get("locked_pick_assets") or [])
    for term in proposal.get('pick_obligation_terms') or []:
        if term.get('type') != 'pick_swap' or not term.get('pending_asset_grant'):
            continue
        subjects = [(term.get('team_a_pick_id'), term.get('sender_team_id') or term.get('counterparty_team_id')),
                    (term.get('team_b_pick_id'), term.get('receiver_team_id') or term.get('original_rights_holder_team_id'))]
        for pid, owner in subjects:
            if pid in pick_overrides and pick_overrides[pid] != owner:
                issues.append(f'Swap subject {pid} is no longer owned by its granting team.')
            if pid in locked_picks:
                issues.append(f'Swap subject {pid} is now locked as collateral.')
        pair = {pid for pid, _ in subjects if pid}
        if any(o.get('type') == 'pick_swap' and o.get('status', 'active') in {'active', 'pending_resolution'}
               and {o.get('team_a_pick_id'), o.get('team_b_pick_id')} == pair
               for o in save.get('pick_obligations', [])):
            issues.append('This pair of picks already has an active swap grant.')
    for side, expected_team_id in [("from_assets", proposal.get("from_team_id")), ("to_assets", proposal.get("to_team_id"))]:
        for asset in proposal.get(side, []) or []:
            label = asset.get("label") or asset.get("name") or asset.get("id") or "Asset"
            if asset.get("kind") == "player":
                player_id = asset.get("id")
                from .release_planning import reacquisition_blocked
                receiving = proposal.get('to_team_id') if side == 'from_assets' else proposal.get('from_team_id')
                if reacquisition_blocked(save, receiving, player_id, date_value or str(save.get('state', {}).get('current_date') or '')):
                    issues.append(f'{label} cannot return to the team that stretched his contract.')
                if player_id in roster_overrides and roster_overrides.get(player_id) != expected_team_id:
                    issues.append(f"{label} is no longer on the offering team.")
            elif asset.get("kind") == "pick":
                pick_id = asset.get("id")
                if pick_id in pick_overrides and pick_overrides.get(pick_id) != expected_team_id:
                    issues.append(f"{label} is no longer owned by the offering team.")
                if pick_id in locked_picks:
                    issues.append(f"{label} is locked as protection/fallback collateral.")
            elif asset.get("kind") == "pick_swap":
                holder = swap_right_holders.get(asset.get("id"))
                grantor = proposal_swap_grantors.get(asset.get("id"))
                if grantor == expected_team_id:
                    continue
                if not holder:
                    issues.append(f"{label} is no longer an active swap right.")
                elif holder != expected_team_id:
                    issues.append(f"{label} is no longer held by the offering team.")
    recent = recently_traded_player_ids(save, date_value)
    for side in ["from_assets", "to_assets"]:
        for asset in proposal.get(side, []) or []:
            if asset.get("kind") == "player" and asset.get("id") in recent:
                label = asset.get("label") or asset.get("name") or asset.get("id") or "Player"
                issues.append(f"{label} was traded within the last {RECENTLY_TRADED_DAYS} days.")
    recently_signed = recently_signed_player_ids(save, date_value)
    for side in ["from_assets", "to_assets"]:
        for asset in proposal.get(side, []) or []:
            if asset.get("kind") == "player" and asset.get("id") in recently_signed:
                label = asset.get("label") or asset.get("name") or asset.get("id") or "Player"
                issues.append(f"{label} signed recently and cannot be traded until Dec. 1.")
    return sorted(dict.fromkeys(issues))


def trade_event_details_from_payload(proposal: dict[str, Any]) -> dict[str, Any]:
    if proposal.get('transfers'):
        return {'team_ids': trade_team_ids(proposal), 'transfers': deepcopy(proposal['transfers'])}
    return {
        "from_team_id": proposal.get("from_team_id"),
        "to_team_id": proposal.get("to_team_id"),
        "from_assets": to_plain(proposal.get("from_assets") or []),
        "to_assets": to_plain(proposal.get("to_assets") or []),
    }


def apply_pick_obligation_terms_to_save(save: dict[str, Any], proposal: dict[str, Any], terms: list[dict[str, Any]], date: str) -> None:
    if not terms:
        return
    obligations = save.setdefault("pick_obligations", [])
    locked = set(save.setdefault("locked_pick_assets", []))
    existing = {item.get("id") for item in obligations}
    for term in terms:
        if not term or term.get("type") == "unprotected":
            continue
        if not validate_pick_obligation_term(save, proposal, term):
            continue
        obligation = {
            **term,
            "id": term.get("id") or stable_id("pick_obligation", proposal.get("id"), term.get("primary_pick_id"), term.get("type")),
            "proposal_id": proposal.get("id"),
            "date_created": date,
            "status": "active",
        }
        if obligation.get("type") == "pick_swap":
            obligation.setdefault("original_rights_holder_team_id", obligation.get("current_rights_holder_team_id") or obligation.get("receiver_team_id"))
            obligation.setdefault("current_rights_holder_team_id", obligation.get("original_rights_holder_team_id"))
            obligation.setdefault("transfer_history", [])
            obligation.pop("pending_asset_grant", None)
        if obligation["id"] not in existing:
            obligations.append(obligation)
            existing.add(obligation["id"])
        for pick_id in obligation.get("fallback_pick_ids") or []:
            locked.add(pick_id)
    save["locked_pick_assets"] = sorted(locked)


def pick_obligation_fallback_rounds_match(canonical_or_save: dict[str, Any], proposal: dict[str, Any] | None, term: dict[str, Any]) -> bool:
    return validate_pick_obligation_term(canonical_or_save, proposal, term)


def canonical_with_pending_pick_terms(canonical: dict[str, Any], terms: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not terms:
        return canonical
    # Pick-term previews change only pick annotations. Preserve the prepared
    # player/team/trait context and clone the much smaller pick structures.
    working = {
        **canonical,
        "draft_picks": [dict(pick) for pick in canonical.get("draft_picks", [])],
        "pick_obligations": [dict(item) for item in canonical.get("pick_obligations", [])],
        "locked_pick_assets": list(canonical.get("locked_pick_assets") or []),
    }
    working.pop("_transaction_pick_context_signature", None)
    obligations = list(working.get("pick_obligations") or [])
    locked = set(working.get("locked_pick_assets") or [])
    existing = {item.get("id") for item in obligations}
    for term in terms:
        if not term or term.get("type") == "unprotected":
            continue
        if not validate_pick_obligation_term(working, None, term):
            continue
        obligation = {
            **term,
            "id": term.get("id") or stable_id("pick_obligation_preview", term.get("primary_pick_id"), term.get("receiver_team_id"), term.get("label")),
            "status": "active",
        }
        if obligation.get("type") == "pick_swap":
            obligation.setdefault("original_rights_holder_team_id", obligation.get("current_rights_holder_team_id") or obligation.get("receiver_team_id"))
            obligation.setdefault("current_rights_holder_team_id", obligation.get("original_rights_holder_team_id"))
            obligation.setdefault("transfer_history", [])
        if obligation["id"] not in existing:
            obligations.append(obligation)
            existing.add(obligation["id"])
        for pick_id in obligation.get("fallback_pick_ids") or []:
            locked.add(pick_id)
    working["pick_obligations"] = obligations
    working["locked_pick_assets"] = sorted(locked)
    # The table belongs to the immutable review base, never to a terms preview.
    # Cache only annotation deltas, not whole canonical graphs or evaluations.
    cache = working.pop('_trade_search_pick_previews', None)
    stats = canonical.get('_market_review_stats')
    key = json.dumps(terms, sort_keys=True, separators=(',', ':'))
    if cache is not None and key in cache:
        if stats is not None:
            stats['pick_preview_hits'] += 1
        changes, entitlements = pickle.loads(cache[key])
        for index, (updates, removed) in changes.items():
            pick = working['draft_picks'][index]
            for field in removed:
                pick.pop(field, None)
            pick.update(updates)
        working['_nested_entitlements'] = entitlements
        return working
    if stats is not None:
        stats['pick_preview_misses'] += 1
    annotate_pick_obligation_context(working)
    if cache is not None:
        fields = ('_active_season', '_obligations', '_protection_value_factor',
                  '_obligation_locked', 'protection_summary', '_nested_entitlement',
                  '_nested_leaf_picks', '_ranked_entitlement', '_ranked_leaf_picks')
        mutable_fields = {'_obligations', '_nested_entitlement', '_nested_leaf_picks',
                          '_ranked_entitlement', '_ranked_leaf_picks'}
        changes = {}
        for index, (before, after) in enumerate(zip(canonical['draft_picks'], working['draft_picks'])):
            if before == after and mutable_fields.isdisjoint(after):
                continue
            updates = {f: after[f] for f in fields if f in after and
                       (f in mutable_fields or f not in before or before[f] != after[f])}
            removed = [f for f in fields if f in before and f not in after]
            if updates or removed:
                changes[index] = (updates, removed)
        if len(cache) >= 64:
            del cache[next(iter(cache))]
            if stats is not None:
                stats['pick_preview_evictions'] += 1
        # Stored as pickle bytes (produced here, read only here): every hit unpickles a private copy.
        cache[key] = pickle.dumps((changes, working.get('_nested_entitlements', {})), protocol=pickle.HIGHEST_PROTOCOL)
        if stats is not None:
            stats['pick_preview_peak_entries'] = max(stats['pick_preview_peak_entries'], len(cache))
    return working


def trade_result_with_pick_terms(result: dict[str, Any], terms: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not terms:
        return result
    payload = to_plain(result)
    payload["pick_obligation_terms_prompted"] = True
    payload["pick_trade_terms"] = to_plain(terms)
    active_terms = [
        term for term in terms
        if term and term.get("type") != "unprotected" and validate_pick_obligation_term(payload.get("proposal") or {}, payload.get("proposal") or {}, term)
    ]
    if not active_terms:
        return payload
    payload["pick_obligation_terms"] = active_terms
    proposal = payload.get("proposal") or {}
    old_id = proposal.get("id")
    payload.setdefault('evaluation_proposal_id', old_id)
    signature = stable_id("pick_terms", json.dumps(active_terms, sort_keys=True))
    if old_id and proposal.get("pick_terms_signature") != signature:
        new_id = stable_id("trade_proposal", old_id, signature)
        proposal["id"] = new_id
        proposal["pick_terms_signature"] = signature
        for evaluation in payload.get("evaluations", []):
            evaluation["proposal_id"] = new_id
            if evaluation.get("perspective_team_id"):
                evaluation["id"] = stable_id("trade_evaluation", new_id, evaluation.get("perspective_team_id"))
    return payload


def queue_press_event_if_user_involved(save: dict[str, Any], kind: str, headline: str, team_ids: list[str | None], date: str) -> None:
    from .save import queue_aggregated_press_event

    queue_aggregated_press_event(save, kind, headline, team_ids, date)


def trade_headline_from_payload(proposal: dict[str, Any]) -> str:
    if proposal.get('transfers'):
        return 'Trade completed: ' + '; '.join(
            f"{t.get('from_abbrev', t['from_team_id'])} sends {trade_headline_side_label(t['assets'])} to {t.get('to_abbrev', t['to_team_id'])}"
            for t in proposal['transfers']) + '.'
    from_assets = trade_headline_side_label(proposal.get("from_assets", []))
    to_assets = trade_headline_side_label(proposal.get("to_assets", []))
    return f"Trade completed: {from_assets} for {to_assets}."


def trade_headline_side_label(assets: list[dict[str, Any]] | None) -> str:
    labels = []
    for asset in assets or []:
        label = asset.get("label") or asset.get("name") or asset.get("headline_label")
        if not label and asset.get("kind") == "player":
            label = asset.get("player_name") or asset.get("id")
        if not label and asset.get("kind") == "pick":
            label = asset.get("pick_label") or asset.get("id")
        if not label and asset.get("kind") == "pick_swap":
            label = asset.get("swap_label") or asset.get("id")
        if label:
            labels.append(str(label))
    return ", ".join(labels) if labels else "future considerations"


def parse_cli_assets(canonical: dict[str, Any], from_team: str, to_team: str, specs: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from_assets: list[dict[str, Any]] = []
    to_assets: list[dict[str, Any]] = []
    from_team_obj = resolve_team(canonical, from_team)
    to_team_obj = resolve_team(canonical, to_team)
    for spec in specs:
        parts = spec.split(":", 2)
        if len(parts) != 3 or parts[0].lower() not in {"from", "to", from_team_obj["abbrev"].lower(), to_team_obj["abbrev"].lower()}:
            raise ValueError("Assets must look like FROM:player:Name, TO:player:Name, FROM:pick:PICK_ID, or TEAM_ABBREV:player:Name.")
        side, kind, value = parts[0].lower(), parts[1].lower(), parts[2]
        if kind not in TRADE_ASSET_KINDS:
            raise ValueError(f"Unknown asset kind {kind!r}; expected player or pick.")
        asset = {"kind": kind, "value": value}
        if side in {"from", from_team_obj["abbrev"].lower()}:
            from_assets.append(asset)
        else:
            to_assets.append(asset)
    return from_assets, to_assets


def with_transaction_context(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach reusable transaction projections, rebuilding only when stale.

    Callers may evaluate many packages against this object. Cache signatures
    must therefore include every season, record, ownership, and obligation
    input that can alter a projected value.
    """
    if isinstance(canonical, dict) and canonical.get("_allow_internal_caches") and transaction_context_ready(canonical):
        return canonical
    if isinstance(canonical, dict) and canonical.get("_allow_internal_caches") and transaction_context_is_complete(canonical):
        ensure_future_second_round_scaffolds(canonical)
        simplify_unsupported_pick_conditions(canonical)
        ensure_pick_value_context(canonical)
        annotate_pick_obligation_context(canonical)
        mark_pick_value_context_current(canonical)
        return canonical
    if isinstance(canonical, dict):
        # Pick projection helpers annotate their inputs. Isolate only those
        # comparatively small mutable structures instead of recursively
        # cloning a mature league, including years of read-only history.
        canonical = dict(canonical)
        if canonical.get('_strategy_model_version') != STRATEGY_MODEL_VERSION:
            for key in ('player_contract_market_profiles', 'player_contract_preferences',
                        'extension_candidates', 'free_agent_candidates'):
                canonical.pop(key, None)
        canonical["meta"] = dict(canonical.get("meta") or {})
        canonical["draft_picks"] = deepcopy(canonical.get("draft_picks") or [])
        canonical["pick_obligations"] = deepcopy(canonical.get("pick_obligations") or [])
        canonical["locked_pick_assets"] = list(canonical.get("locked_pick_assets") or [])
        canonical.pop("_transaction_pick_context_signature", None)
    else:
        canonical = to_plain(canonical)
    canonical["_allow_internal_caches"] = True
    ensure_future_second_round_scaffolds(canonical)
    simplify_unsupported_pick_conditions(canonical)
    if transaction_context_is_complete(canonical):
        ensure_pick_value_context(canonical)
        annotate_pick_obligation_context(canonical)
        mark_pick_value_context_current(canonical)
        return canonical
    context = build_transaction_context(canonical, config)
    enriched = {**canonical, **context}
    ensure_pick_value_context(enriched)
    annotate_pick_obligation_context(enriched)
    mark_pick_value_context_current(enriched)
    return enriched


def ensure_future_second_round_scaffolds(canonical: dict[str, Any]) -> None:
    """Extend the playable horizon without replacing researched ownership."""
    teams = [team for team in canonical.get("teams", []) if team.get("id")]
    picks = canonical.setdefault("draft_picks", [])
    existing = {
        (str(pick.get("season")), int(pick.get("round") or 0), pick.get("original_team_id"))
        for pick in picks
    }
    active_start = season_start_from_label(str(canonical.get("meta", {}).get("active_season") or CANONICAL_SEASON))
    first_round_horizon = max(
        (int(pick["season"]) for pick in picks if int(pick.get("round") or 0) == 1 and str(pick.get("season", "")).isdigit()),
        default=active_start,
    )
    for team in teams:
        team_id = team["id"]
        abbrev = str(team.get("abbrev") or team_id.replace("team_", "")).lower()
        for year in range(max(2026, active_start + 1), active_start + 8):
            key = (str(year), 2, team_id)
            if key in existing:
                continue
            pick_id = f"pick_future-{abbrev}-{year}-2-own"
            picks.append(
                {
                    "id": pick_id,
                    "season": str(year),
                    "round": 2,
                    "original_team_id": team_id,
                    "current_owner_team_id": team_id,
                    "status": "inferred_future_second_round_scaffold",
                    "confidence": 0.36,
                    "source_ids": ["src_manual_overrides_2025_26"],
                    "notes": "Gameplay scaffold for future own second-round pick. Conditions/protections are deferred in v1.",
                }
            )
            existing.add(key)
        # Only extend beyond the known ledger; gaps inside it can be obligations.
        for year in range(max(active_start + 1, first_round_horizon + 1), active_start + 8):
            key = (str(year), 1, team_id)
            if key in existing:
                continue
            picks.append({
                "id": f"pick_future-{abbrev}-{year}-1-own",
                "season": str(year), "round": 1,
                "original_team_id": team_id, "current_owner_team_id": team_id,
                "status": "inferred_future_first_round_scaffold",
                "confidence": 0.36, "source_ids": ["src_manual_overrides_2025_26"],
                "notes": "Modeled own first-round pick beyond the researched ledger horizon.",
            })
            existing.add(key)


def simplify_unsupported_pick_conditions(canonical: dict[str, Any]) -> None:
    """Normalize unsupported public pick-condition prose into clean, playable assets."""
    for pick in canonical.get("draft_picks", []):
        raw = str(pick.get("protection_summary") or pick.get("protections") or "").strip()
        if not raw:
            continue
        clean = clean_pick_protection_summary(pick)
        if re.search(r"\bfrozen\s+pick\b", raw, flags=re.IGNORECASE):
            pick["protection_summary"] = None
            pick["protections"] = None
            pick["_unsupported_pick_condition_simplified"] = True
            pick["_obligation_locked"] = True
            pick.setdefault("notes", "")
            pick["notes"] = " ".join(
                part for part in [str(pick.get("notes") or "").strip(), "Locked protection backup hidden from tradeable assets."]
                if part
            )
        elif unsupported_pick_backup_condition(raw) and not clean:
            pick["protection_summary"] = None
            pick["protections"] = None
            pick["_unsupported_pick_condition_simplified"] = True
            pick["_obligation_locked"] = True
            pick.setdefault("notes", "")
            pick["notes"] = " ".join(
                part for part in [str(pick.get("notes") or "").strip(), "Unsupported conditional backup removed from tradeable assets."]
                if part
            )
        elif unsupported_pick_condition(raw):
            pick["protection_summary"] = clean or None
            pick["protections"] = clean or None
            pick["_unsupported_pick_condition_simplified"] = True
            pick.setdefault("notes", "")
            pick["notes"] = " ".join(
                part for part in [str(pick.get("notes") or "").strip(), "Unsupported swap/favorable condition simplified to a regular pick."]
                if part
            )
        elif clean and clean != raw:
            pick["protection_summary"] = clean


def unsupported_pick_condition(text: str) -> bool:
    return bool(UNSUPPORTED_PICK_CONDITION_RE.search(str(text or "")))


def unsupported_pick_backup_condition(text: str) -> bool:
    return bool(UNSUPPORTED_PICK_FALLBACK_RE.search(str(text or "")))


def annotate_pick_obligation_context(canonical: dict[str, Any]) -> None:
    locked = set(canonical.get("locked_pick_assets") or [])
    obligations = [item for item in canonical.get("pick_obligations", []) if item.get("status", "active") in {"active", "pending_resolution"}]
    by_pick: dict[str, list[dict[str, Any]]] = {}
    for obligation in obligations:
        subjects = {obligation.get(field) for field in ["primary_pick_id", "team_a_pick_id", "team_b_pick_id"]}
        subjects.update(obligation.get("comparison_pool_pick_ids") or [])
        for pick_id in subjects - {None}:
            by_pick.setdefault(pick_id, []).append(obligation)
        for pick_id in obligation.get("fallback_pick_ids") or []:
            locked.add(pick_id)
            by_pick.setdefault(pick_id, []).append({**obligation, "_fallback_lock": True})
    for pick in canonical.get("draft_picks", []):
        pick["_active_season"] = str(canonical.get("meta", {}).get("active_season") or CANONICAL_SEASON)
        pick.pop("_obligations", None)
        pick.pop("_protection_value_factor", None)
        if not pick.get("_unsupported_pick_condition_simplified") and pick.get("id") not in locked:
            pick.pop("_obligation_locked", None)
        pick_id = pick.get("id")
        if pick_id in locked:
            pick["_obligation_locked"] = True
        obligations_for_pick = by_pick.get(pick_id, [])
        if obligations_for_pick:
            pick["_obligations"] = obligations_for_pick
            pick["_protection_value_factor"] = pick_obligation_value_factor(obligations_for_pick)
            primary = next((item for item in obligations_for_pick if item.get("type") == "protected_pick" and not item.get("_fallback_lock")), None)
            if primary:
                pick["protection_summary"] = pick_obligation_label(primary)


    from .pick_presentation import nested_entitlements, ranked_pool_entitlements

    entitlements = nested_entitlements(canonical)
    canonical["_nested_entitlements"] = entitlements
    for pick in canonical.get("draft_picks", []):
        pick.pop("_nested_entitlement", None)
        pick.pop("_nested_leaf_picks", None)
        pick.pop("_ranked_entitlement", None)
        pick.pop("_ranked_leaf_picks", None)
    # Ranked pools read only owners and terms, never the nested annotations written below, so they can be
    # computed first. That lets the leaf snapshots copy just the picks an entitlement refers to.
    ranked = ranked_pool_entitlements(canonical)
    needed = {pid for item in entitlements.values() for pid in item["underlying_pick_ids"]}
    needed.update(pid for item in ranked.values() for pid in item["pool_pick_ids"])
    snapshots = {pick["id"]: dict(pick) for pick in canonical.get("draft_picks", []) if pick["id"] in needed}
    for anchor, entitlement in entitlements.items():
        pick = next(row for row in canonical["draft_picks"] if row["id"] == anchor)
        pick["_nested_entitlement"] = entitlement
        pick["_nested_leaf_picks"] = {pid: snapshots[pid] for pid in entitlement["underlying_pick_ids"]}
    for pid, entitlement in ranked.items():
        pick = next(row for row in canonical["draft_picks"] if row["id"] == pid)
        pick["_ranked_entitlement"] = entitlement
        pick["_ranked_leaf_picks"] = {leaf: snapshots[leaf] for leaf in entitlement["pool_pick_ids"]}


def pick_obligation_label(obligation: dict[str, Any]) -> str:
    from .pick_rules import protection_bounds

    low, high = protection_bounds(obligation)
    return f"top-{high} protected" if low == 1 else f"picks {low}-{high} protected"


def active_primary_pick_obligation_for_label(pick: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            obligation
            for obligation in pick.get("_obligations", [])
            if obligation.get("type") == "protected_pick" and not obligation.get("_fallback_lock")
        ),
        None,
    )


def team_id_fallback(team_id: str | None) -> str:
    return str(team_id or "TEAM").replace("team_", "").upper()


def pick_short_label(canonical: dict[str, Any], pick: dict[str, Any] | None) -> str:
    if not pick:
        return "fallback pick"
    teams = {team.get("id"): team.get("abbrev") for team in canonical.get("teams", [])}
    original = teams.get(pick.get("original_team_id")) or "TBD"
    return f"{pick.get('season', '----')} R{pick.get('round', '?')} {original}"


def pick_swap_obligations_for_pick(pick: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        obligation
        for obligation in pick.get("_obligations", [])
        if obligation.get("type") == "pick_swap" and not obligation.get("_fallback_lock")
    ]


def pick_swap_display_label(canonical: dict[str, Any], obligation: dict[str, Any]) -> str:
    from .pick_presentation import swap_step_label

    return swap_step_label(canonical, obligation)


def pick_swap_benefit(obligation: dict[str, Any]) -> str:
    benefit = str(obligation.get("benefit") or obligation.get("swap_benefit") or obligation.get("rights_benefit") or "better").lower()
    if benefit in {"worse", "less", "less_favorable", "lower"}:
        return "worse"
    return "better"


def pick_swap_context_note(canonical: dict[str, Any], obligation: dict[str, Any]) -> str:
    return pick_swap_display_label(canonical, obligation)


def pick_swap_asset_value(canonical: dict[str, Any], obligation: dict[str, Any], phase: str = "neutral") -> float:
    pick_a = pick_by_id(canonical, obligation.get("team_a_pick_id") or obligation.get("primary_pick_id"))
    pick_b = pick_by_id(canonical, obligation.get("team_b_pick_id") or obligation.get("counterparty_pick_id"))
    if not pick_a or not pick_b:
        return 0.0
    value_a = pick_asset_value(pick_a, phase)
    value_b = pick_asset_value(pick_b, phase)
    if value_a <= 0 or value_b <= 0:
        return 0.0
    spread = abs(value_a - value_b)
    year = pick_season_start(pick_a) or pick_season_start(pick_b) or 2028
    active_year = season_start_from_label(str(canonical.get("meta", {}).get("active_season") or CANONICAL_SEASON))
    distance = max(0, year - active_year)
    uncertainty = clamp(0.68 - distance * 0.08, 0.34, 0.68)
    base = 3.8 + spread * uncertainty
    if int(pick_a.get("round") or 0) == 1:
        base += 4.0
    else:
        base *= 0.62
    value = round(clamp(base, 1.0, 42.0), 2)
    return -value if pick_swap_benefit(obligation) == "worse" else value


def pick_swap_by_id(canonical: dict[str, Any], obligation_id: str | None) -> dict[str, Any] | None:
    if not obligation_id:
        return None
    return next(
        (
            obligation
            for obligation in canonical.get("pick_obligations", [])
            if obligation.get("id") == obligation_id and obligation.get("type") == "pick_swap"
        ),
        None,
    )


def tradeable_pick_swaps_for_team(canonical: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    from .pick_presentation import nested_entitlements

    bundled = {oid for item in nested_entitlements(canonical).values() for oid in item["obligation_ids"]}
    swaps = []
    for obligation in active_pick_obligations(canonical):
        if obligation.get("id") in bundled:
            continue
        if obligation.get("type") != "pick_swap":
            continue
        if obligation.get("allocation_comparison"):
            # These comparisons settle one already-owned conditional asset;
            # listing each comparison as another swap would mint extra value.
            continue
        holder = obligation.get("current_rights_holder_team_id") or obligation.get("original_rights_holder_team_id") or obligation.get("receiver_team_id")
        if holder != team_id:
            continue
        value = pick_swap_asset_value(canonical, obligation, "neutral")
        swaps.append(
            {
                "kind": "pick_swap",
                "id": obligation.get("id"),
                "label": pick_swap_display_label(canonical, obligation),
                "season": obligation.get("season"),
                "round": obligation.get("round"),
                "current_rights_holder_team_id": holder,
                "team_a_pick_id": obligation.get("team_a_pick_id") or obligation.get("primary_pick_id"),
                "team_b_pick_id": obligation.get("team_b_pick_id") or obligation.get("counterparty_pick_id"),
                "value": value,
            }
        )
    return sorted(swaps, key=lambda item: (str(item.get("season") or ""), int(item.get("round") or 9), str(item.get("id") or "")))


def pick_obligation_context_note(canonical: dict[str, Any], pick: dict[str, Any], include_fallback: bool = True) -> str:
    obligation = active_primary_pick_obligation_for_label(pick)
    from .pick_presentation import pick_presentation

    presentation = pick_presentation(canonical, pick)
    swap_notes = [presentation["label"]] if presentation else []
    if not obligation:
        if pick.get("current_owner_team_id") and pick.get("current_owner_team_id") == pick.get("original_team_id"):
            return "; ".join(swap_notes)
        clean = clean_pick_protection_summary(pick)
        return "; ".join(part for part in [clean, *swap_notes] if part)
    teams = {team.get("id"): team.get("abbrev") for team in canonical.get("teams", [])}
    sender = obligation.get("sender_team_id")
    beneficiary = pick.get("current_owner_team_id") if pick.get("current_owner_team_id") != sender else obligation.get("receiver_team_id")
    parts = [pick_obligation_label(obligation)]
    if sender:
        parts.append(f"{teams.get(sender) or team_id_fallback(sender)} keeps this pick if it lands in the protected range")
    fallback_id = next((pid for pid in obligation.get("fallback_pick_ids") or [] if pid), None)
    fallback = pick_by_id(canonical, fallback_id) if fallback_id else None
    if include_fallback and fallback and protected_pick_fallback_is_distinct(pick, fallback) and beneficiary and beneficiary != sender:
        parts.append(f"{teams.get(beneficiary) or team_id_fallback(beneficiary)} instead receives {pick_short_label(canonical, fallback)}")
    parts.extend(swap_notes)
    return "; ".join(part for part in parts if part)


def pick_display_label(canonical: dict[str, Any], pick: dict[str, Any], include_fallback: bool = True) -> str:
    teams = {team.get("id"): team.get("abbrev") for team in canonical.get("teams", [])}
    ranked = pick.get("_ranked_entitlement")
    if ranked:
        from .pick_rules import ordinal
        names = "/".join(teams.get((pick_by_id(canonical, pid) or {}).get("original_team_id"), "TBD") for pid in ranked["pool_pick_ids"])
        rank, size = ranked["rank"], ranked["pool_size"]
        if rank == 1:
            outcome = "more" if size == 2 else "most"
        elif rank == size:
            outcome = "less" if size == 2 else "least"
        elif rank * 2 >= size + 1:
            outcome = ordinal(size - rank + 1) + " least"
        else:
            outcome = ordinal(rank) + " most"
        recipient = teams.get(pick.get("current_owner_team_id"), "TBD")
        return f"{pick.get('season')} R{pick.get('round')}: {recipient} receives the {outcome} favourable of {names}."
    owner = teams.get(pick.get("current_owner_team_id")) or "TBD"
    original = teams.get(pick.get("original_team_id")) or "TBD"
    ownership = f"owned by {owner}" if owner != original else "own pick"
    note = pick_obligation_context_note(canonical, pick, include_fallback=include_fallback)
    suffix = f"; {note}" if note else ""
    return f"{pick.get('season', '----')} R{pick.get('round', '?')} {original} ({ownership}){suffix}"


def trade_candidate_with_current_asset_labels(canonical: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Refresh mutable pick labels before presenting an offer to the user."""
    refreshed = to_plain(candidate)
    proposal = refreshed.get("proposal") or {}
    groups = [t['assets'] for t in proposal['transfers']] if proposal.get('transfers') else [proposal.get(side, []) for side in ('from_assets', 'to_assets')]
    for assets in groups:
        for asset in assets:
            if asset.get("kind") == "pick":
                pick = pick_by_id(canonical, asset.get("id"))
                if pick:
                    from .pick_presentation import pick_presentation

                    asset["pick_presentation"] = pick_presentation(canonical, pick)
                    asset["label"] = pick_display_label(canonical, pick)
                    asset["protection_summary"] = pick.get("protection_summary") or pick.get("protections")
            elif asset.get("kind") == "pick_swap":
                swap = pick_swap_by_id(canonical, asset.get("id"))
                if swap:
                    from .pick_presentation import swap_presentation

                    asset["pick_presentation"] = swap_presentation(canonical, swap)
                    asset["label"] = pick_swap_display_label(canonical, swap)
    if proposal:
        refreshed["proposal"] = proposal
        refreshed["summary"] = trade_headline_from_payload(proposal) if proposal.get('transfers') else proposal_summary(canonical, proposal)
    return refreshed


def pick_obligation_value_factor(obligations: list[dict[str, Any]]) -> float:
    factor = 1.0
    for obligation in obligations:
        if obligation.get("type") == "protected_pick":
            from .pick_rules import protection_bounds

            _, top_n = protection_bounds(obligation)
        if obligation.get("_fallback_lock"):
            factor *= 0.15
            continue
        if obligation.get("type") == "protected_pick":
            factor *= clamp(1.0 - float(top_n) * 0.018, 0.52, 0.98)
    return round(clamp(factor, 0.05, 1.0), 3)


def transaction_context_is_complete(canonical: dict[str, Any]) -> bool:
    if not (
        canonical.get("_strategy_model_version") == STRATEGY_MODEL_VERSION
        and canonical.get("front_office_profiles")
        and canonical.get("team_strategic_states")
        and canonical.get("player_asset_valuations")
        and canonical.get("trade_block_entries") is not None
    ):
        return False
    valued = {value.get("player_id") for value in canonical.get("player_asset_valuations", [])}
    active_players = {player.get("id") for player in canonical.get("players", []) if player.get("team_id")}
    return active_players.issubset(valued)


def transaction_context_ready(canonical: Any) -> bool:
    return isinstance(canonical, dict) and transaction_context_is_complete(canonical) and pick_value_context_current(canonical)


def ensure_pick_value_context(canonical: dict[str, Any]) -> None:
    signature = transaction_pick_context_signature(canonical)
    if canonical.get("_transaction_pick_context_signature") == signature:
        return
    annotate_pick_value_context(canonical)
    canonical["_transaction_pick_context_signature"] = signature


def mark_pick_value_context_current(canonical: dict[str, Any]) -> None:
    canonical["_transaction_pick_context_signature"] = transaction_pick_context_signature(canonical)


def pick_value_context_current(canonical: dict[str, Any]) -> bool:
    return canonical.get("_transaction_pick_context_signature") == transaction_pick_context_signature(canonical)


def transaction_pick_context_signature(canonical: dict[str, Any]) -> str:
    meta = canonical.get("meta") or {}
    records = canonical.get("save_team_records") or {}
    payload = {
        "active_season": meta.get("active_season"),
        "teams": sorted(
            (
                team.get("id"),
                state.get("phase"),
                maybe_float(state.get("contention_ceiling")),
                maybe_float(state.get("pressure")),
            )
            for team in canonical.get("teams", [])
            for state in [next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == team.get("id")), {})]
        ),
        "records": sorted(
            (
                team_id,
                maybe_float(record.get("wins")) or 0.0,
                maybe_float(record.get("losses")) or 0.0,
            )
            for team_id, record in records.items()
        ),
        "rosters": sorted(
            (player.get("id"), player.get("team_id"))
            for player in canonical.get("players", [])
            if player.get("id")
        ),
        "picks": sorted(
            (
                pick.get("id"),
                str(pick.get("season") or ""),
                int(pick.get("round") or 0),
                pick.get("original_team_id"),
                pick.get("current_owner_team_id"),
                pick.get("status"),
                pick.get("overall_pick"),
                pick.get("protection_summary"),
                pick.get("protections"),
            )
            for pick in canonical.get("draft_picks", [])
            if pick.get("id")
        ),
        "obligations": sorted(
            json.dumps(
                {
                    key: obligation.get(key)
                    for key in [
                        "id",
                        "type",
                        "status",
                        "season",
                        "round",
                        "primary_pick_id",
                        "fallback_pick_ids",
                        "sender_team_id",
                        "receiver_team_id",
                        "current_rights_holder_team_id",
                        "counterparty_team_id",
                        "team_a_pick_id",
                        "team_b_pick_id",
                        "comparison_pool_pick_ids",
                        "comparison_holder_team_id",
                        "comparison_counterparty_team_id",
                        "subject_protected_top_n",
                        "allocation_comparison",
                        "benefit", "nested_input", "nested_other_input", "nested_other_pick_id", "nested_anchor_pick_id", "allocation_slot_pick_ids",
                    ]
                },
                sort_keys=True,
            )
            for obligation in canonical.get("pick_obligations", [])
        ),
        "locked_pick_assets": sorted(canonical.get("locked_pick_assets") or []),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]
    return f"transaction_pick_context_{digest}"


def annotate_pick_value_context(canonical: dict[str, Any]) -> None:
    states = {state.get("team_id"): state for state in canonical.get("team_strategic_states", [])}
    records = canonical.get("save_team_records") or {}
    team_scores: list[tuple[str, float]] = []
    for team in canonical.get("teams", []):
        team_id = team.get("id")
        state = states.get(team_id, {})
        ceiling = maybe_float(state.get("contention_ceiling")) or 52.0
        record = records.get(team_id, {})
        wins = maybe_float(record.get("wins")) or 0.0
        losses = maybe_float(record.get("losses")) or 0.0
        games = wins + losses
        win_pct = wins / games if games > 0 else 0.5
        record_weight = clamp(games / 82.0, 0.0, 0.9)
        badness = (100.0 - ceiling) * (1.0 - record_weight) + (1.0 - win_pct) * 100.0 * record_weight
        team_scores.append((team_id, badness))
    projected_slots = {
        team_id: rank
        for rank, (team_id, _) in enumerate(sorted(team_scores, key=lambda item: item[1], reverse=True), start=1)
    }
    active_season = str(canonical.get("meta", {}).get("active_season") or CANONICAL_SEASON)
    current_start = season_start_from_label(active_season)
    for pick in canonical.get("draft_picks", []):
        original = pick.get("original_team_id")
        if not original:
            continue
        if pick.get("overall_pick"):
            pick["projected_pick_slot"] = int(pick.get("overall_pick") or 30)
            continue
        pick_start = pick_season_start(pick)
        if pick_start is not None and pick_start < current_start:
            continue
        base_slot = int(projected_slots.get(original, 18))
        distance = max(0, (pick_start or current_start + 1) - current_start)
        pick["projected_pick_slot"] = int(round(future_adjusted_pick_slot(canonical, original, base_slot, distance)))
        pick["_future_distance_years"] = distance


def future_adjusted_pick_slot(canonical: dict[str, Any], team_id: str, base_slot: int, distance: int) -> float:
    if distance <= 0:
        return clamp(float(base_slot), 1, 30)
    state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == team_id), {})
    values = {value.get("player_id"): value for value in canonical.get("player_asset_valuations", [])}
    roster = [player for player in canonical.get("players", []) if player.get("team_id") == team_id]
    top_players = sorted(
        roster,
        key=lambda player: float((values.get(player.get("id")) or fallback_asset_valuation(player)).get("player_value") or 0.0),
        reverse=True,
    )[:5]
    top_three = top_players[:3]
    avg_top_age = (
        sum(maybe_float(player.get("age")) or 27.0 for player in top_three) / len(top_three)
        if top_three
        else 27.0
    )
    youth_score = sum(
        max(0.0, float((values.get(player.get("id")) or fallback_asset_valuation(player)).get("development_upside") or 0.0))
        for player in roster
        if (maybe_float(player.get("age")) or 99.0) <= 24.0
    )
    phase = str(state.get("phase") or "balanced")
    mean_pull = min(0.58, distance * 0.10)
    slot = float(base_slot) * (1.0 - mean_pull) + 15.5 * mean_pull
    movement = 0.0
    if base_slot <= 8:
        movement += 0.65 + min(0.95, youth_score / 90.0)
        if phase in {"rebuilding", "developing"}:
            movement += 0.35
        if avg_top_age >= 30.5 and youth_score < 28:
            movement -= 0.35
    elif base_slot >= 23:
        if avg_top_age >= 31.0:
            movement -= 1.15 + min(0.5, (avg_top_age - 31.0) * 0.18)
        elif avg_top_age <= 27.0 or phase == "contending_with_future_upside":
            movement += 0.28
        else:
            movement -= 0.25
    else:
        if avg_top_age <= 25.5 and youth_score >= 36:
            movement += 0.45
        elif avg_top_age >= 31.0:
            movement -= 0.55
    return clamp(slot + movement * distance, 1, 30)


def player_asset_values_by_id(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cached = canonical.get("_player_asset_values_by_id")
    if isinstance(cached, dict):
        return cached
    values = {
        value["player_id"]: value
        for value in canonical.get("player_asset_valuations", [])
        if value.get("player_id")
    }
    if canonical.get("_allow_internal_caches"):
        canonical["_player_asset_values_by_id"] = values
    return values


@lru_cache(maxsize=20000)
def _fallback_asset_valuation_cached(key: tuple[Any, ...]) -> tuple[tuple[str, float], ...]:
    (
        player_id,
        name,
        position,
        minutes_raw,
        ability_raw,
        overall_raw,
        potential_raw,
        age_raw,
        draft_pick,
        overall_pick,
        draft_year,
        active_season,
    ) = key
    player = {
        "id": player_id,
        "name": name,
        "position": position,
        "minutes_projection": minutes_raw,
        "current_ability": ability_raw,
        "overall": overall_raw,
        "potential": potential_raw,
        "age": age_raw,
        "draft_pick": draft_pick,
        "overall_pick": overall_pick,
        "draft_year": draft_year,
        "_active_season": active_season,
    }
    minutes = maybe_float(minutes_raw) or 0.0
    if minutes > 80:
        minutes = minutes / 82.0
    ability = maybe_float(ability_raw) or maybe_float(overall_raw) or (38.0 + minutes * 1.15)
    potential = maybe_float(potential_raw) or ability
    age = maybe_float(age_raw) or 24.0
    development = max(0.0, potential - ability) * (1.0 if age <= 24 else 0.45)
    player_value = clamp(ability * 0.54 + minutes * 1.15 + development * 0.42, 1, 99)
    player_value = max(player_value, drafted_rookie_value_floor(player, ability=ability, potential=potential))
    if goat_exception_player(player):
        player_value = 99.0
    portability = clamp(ability * 0.72 + minutes * 0.6, 1, 99)
    payload = {
        "player_value": round(player_value, 2),
        "on_court_value": round(clamp(ability * 0.65 + minutes * 0.8, 1, 99), 2),
        "contract_surplus": 0.0,
        "age_curve": round(player_age_curve(age), 2),
        "health_risk": 45.0,
        "role_scarcity": 5.0 if str(position or "").upper() in {"C", "PG"} else 2.0,
        "portability": round(portability, 2),
        "playoff_value": round(clamp(ability * 0.72 + minutes * 0.5, 1, 99), 2),
        "development_upside": round(development, 2),
    }
    return tuple(sorted(payload.items()))


_MISSING = object()


def valuation_or_fallback(values: dict[str, Any], player_id: Any, player: dict[str, Any] | None) -> Any:
    """values.get(player_id, fallback_asset_valuation(player)), building the (pure) fallback only when needed."""
    value = values.get(player_id, _MISSING)
    return fallback_asset_valuation(player) if value is _MISSING else value


def fallback_asset_valuation(player: dict[str, Any] | None) -> dict[str, float]:
    if not player:
        return {
            "player_value": 1.0,
            "on_court_value": 1.0,
            "contract_surplus": 0.0,
            "age_curve": 0.0,
            "health_risk": 45.0,
            "role_scarcity": 0.0,
            "portability": 45.0,
            "playoff_value": 45.0,
            "development_upside": 0.0,
        }
    key = (
        player.get("id"),
        player.get("name"),
        player.get("position"),
        player.get("minutes_projection"),
        player.get("current_ability"),
        player.get("overall"),
        player.get("potential"),
        player.get("age"),
        player.get("draft_pick"),
        player.get("overall_pick"),
        player.get("draft_year"),
        player.get("_active_season"),
    )
    return dict(_fallback_asset_valuation_cached(key))


def find_selling_candidates(
    canonical: dict[str, Any],
    user_team: dict[str, Any],
    target: dict[str, Any],
    seed: int,
    package_result_limit: int = 18,
    package_player_options: int = 9,
) -> list[dict[str, Any]]:
    candidates = []
    valuations = player_asset_values_by_id(canonical)
    target_value = market_trade_target_value(target, valuations.get(target.get("id"), fallback_asset_valuation(target)))
    per_buyer_limit = 10 if target_value >= 70 else 4
    for buyer in buyer_teams_for_player(canonical, target):
        if buyer["id"] == user_team["id"]:
            continue
        # Keep looking past illegal packages until this buyer has per_buyer_limit legal ones (it used to cut to the
        # first per_buyer_limit packages before legality, so a user could see "no offers" while legal ones existed).
        legal = 0
        for buyer_assets in buyer_offer_packages(canonical, buyer, user_team, target, seed, max_results=package_result_limit, max_player_options=package_player_options):
            report = evaluate_trade_decision(canonical, user_team["abbrev"], buyer["abbrev"], [{"kind": "player", "value": target["name"]}], buyer_assets, seed=seed, context_ready=True)
            candidate = candidate_from_decision(report)
            if candidate.get("legality", {}).get("status") != "legal":
                continue
            candidates.append(candidate)
            legal += 1
            if legal >= per_buyer_limit:
                break
    return candidates


def find_buying_candidates(
    canonical: dict[str, Any],
    user_team: dict[str, Any],
    target: dict[str, Any],
    seed: int,
    package_result_limit: int = 18,
    package_player_options: int = 9,
) -> list[dict[str, Any]]:
    target_team = team_by_id(canonical, target["team_id"])
    candidates = []
    for package in buyer_offer_packages(canonical, user_team, target_team, target, seed, max_results=package_result_limit, max_player_options=package_player_options):
        report = evaluate_trade_decision(canonical, user_team["abbrev"], target_team["abbrev"], package, [{"kind": "player", "value": target["name"]}], seed=seed, context_ready=True)
        candidates.append(candidate_from_decision(report))
    return candidates


def buyer_offer_assets(canonical: dict[str, Any], buyer: dict[str, Any], seller: dict[str, Any], target: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    packages = buyer_offer_packages(canonical, buyer, seller, target, seed)
    return packages[0] if packages else []


def buyer_offer_package_options(
    canonical: dict[str, Any],
    buyer: dict[str, Any],
    seller: dict[str, Any],
    target: dict[str, Any],
    seed: int,
    max_results: int = 18,
    max_player_options: int = 9,
    allow_new_pick_swaps: bool = False,
    financial_search: bool = False,
    repair_options=None,
    date=None,
    config=None,
) -> list[dict[str, Any]]:
    valuations = player_asset_values_by_id(canonical)
    target_valuation = valuation_or_fallback(valuations, target["id"], target)
    target_value = market_trade_target_value(target, target_valuation)
    target_salary = current_salary(contract_for_player(canonical, target["id"]))
    from .trade_wants import package_preference
    # Seek part of the buyer's stated extra willingness; this is a quote,
    # never an automatic charge or a second acceptance bonus.
    target_value += package_preference(canonical, buyer['id'], [{'kind': 'player', 'id': target['id']}])['adjustment']*.5
    from .trade_finance_search import TradeSearchIntent
    intent = TradeSearchIntent(seller['id'],buyer['id'],({'kind':'player','id':target['id'],'label':target['name']},),
        date or canonical.get('meta',{}).get('current_date') or CANONICAL_START_DATE,config) if financial_search else None
    return buyer_offer_packages_for_value(
        canonical,
        buyer,
        seller,
        target_value,
        target_salary,
        seed,
        {target["id"]},
        max_results=max_results,
        max_player_options=max_player_options,
        return_options=True,
        allow_new_pick_swaps=allow_new_pick_swaps,
        intent=intent,repair_options=repair_options,
    )


def buyer_offer_packages(
    canonical: dict[str, Any],
    buyer: dict[str, Any],
    seller: dict[str, Any],
    target: dict[str, Any],
    seed: int,
    max_results: int = 18,
    max_player_options: int = 9,
) -> list[list[dict[str, Any]]]:
    valuations = player_asset_values_by_id(canonical)
    target_valuation = valuation_or_fallback(valuations, target["id"], target)
    target_value = market_trade_target_value(target, target_valuation)
    from .trade_wants import package_preference
    target_value += package_preference(canonical, buyer['id'], [{'kind': 'player', 'id': target['id']}])['adjustment']*.5
    target_salary = current_salary(contract_for_player(canonical, target["id"]))
    return buyer_offer_packages_for_value(
        canonical,
        buyer,
        seller,
        target_value,
        target_salary,
        seed,
        {target["id"]},
        max_results=max_results,
        max_player_options=max_player_options,
    )


def market_trade_target_value(player: dict[str, Any], valuation: dict[str, Any]) -> float:
    raw = float(valuation.get("player_value") or 0.0)
    if goat_exception_player(player):
        return 112.0
    minutes = trade_value_role_minutes(player, valuation)
    ability = maybe_float(player.get("current_ability")) or maybe_float(player.get("overall")) or (38.0 + minutes * 1.15)
    potential = maybe_float(player.get("potential")) or ability
    upside = max(0.0, potential - ability)
    rookie_floor = drafted_rookie_value_floor(player, ability=ability, potential=potential)
    if rookie_floor:
        raw = max(raw, rookie_floor)
    raw = market_value_after_star_and_surplus_shape(player, valuation, raw)
    saved_stats = player.get("_save_stats") or {}
    logged_games = maybe_float(saved_stats.get("games")) or 0.0
    logged_minutes = maybe_float(saved_stats.get("minutes")) or 0.0
    logged_mpg = logged_minutes / logged_games if logged_games else minutes
    ppg = (maybe_float(saved_stats.get("points")) or 0.0) / logged_games if logged_games else 0.0
    elite_prospect_floor = 0.0
    age = maybe_float(player.get("age")) or 99.0
    if age <= 21 and ability >= 54 and potential >= 80:
        elite_prospect_floor = 38.0 + max(0.0, ability - 54.0) * 1.25 + max(0.0, potential - 80.0) * 0.72
    if minutes < 2 and raw < 74:
        scratch_variation = deterministic_low_role_value_variation(player)
        raw = min(raw, max(elite_prospect_floor, 7.5 + scratch_variation + max(0.0, ability - 48.0) * 0.48 + upside * 0.36 - max(0.0, age - 27.0) * 0.35))
    elif minutes < 8 and raw < 74:
        raw = min(raw, max(elite_prospect_floor, 20.0 + max(0.0, ability - 50.0) * 0.56 + upside * 0.45 + minutes * 0.38))
    elif minutes < 14 and raw < 72:
        raw = min(raw, max(elite_prospect_floor, 28.0 + max(0.0, ability - 52.0) * 0.58 + upside * 0.38 + minutes * 0.32))
    if logged_games >= 8 and logged_mpg < 6 and ppg < 4 and raw < 72:
        raw = min(raw, 19.0 + max(0.0, ability - 52.0) * 0.5 + upside * 0.32)
    cap = market_trade_value_cap(player, valuation, raw)
    if rookie_floor:
        return round(soft_value_ceiling(max(raw, rookie_floor), ceiling=min(cap, 99.0), knee=6.0), 2)
    if raw < 62 or minutes >= 28:
        return round(soft_value_ceiling(raw, ceiling=cap, knee=6.0), 2)
    role_scale = clamp((max(4.0, minutes) / 30.0) ** 1.22, 0.36, 1.0)
    overall_proxy = float(ability)
    compressed = raw * role_scale
    if minutes < 20 and raw >= 70:
        compressed = min(compressed, 24.0 + max(0.0, overall_proxy - 55.0) * 0.5 + minutes * 0.5)
    if minutes < 24:
        compressed = min(compressed, 32.0 + max(0.0, overall_proxy - 55.0) * 0.68 + minutes * 0.43)
    return round(clamp(compressed, 1.0, raw), 2)


def surplus_quality_factor(on_court: float) -> float:
    """How much a cheap contract adds to asset value, by player quality.

    A bargain deal on a great player is a huge asset; the same bargain on a fringe rotation player is worth
    far less. Without this, the capped +34 surplus lifted many ~70 on-court young players to the value
    ceiling alongside MVP-level players (2026-11-16 market review).
    """
    return clamp((on_court - 60.0) / 22.0, 0.3, 1.0)


def soft_value_ceiling(value: float, ceiling: float = 99.0, knee: float = 11.0) -> float:
    """Order-preserving ceiling: values above ceiling-knee are compressed toward the ceiling, never clipped.

    Replaces a hard clamp that made many players tie exactly at the ceiling.
    """
    value = max(1.0, value)
    start = ceiling - knee
    if value <= start:
        return value
    return start + knee * (1.0 - math.exp(-(value - start) / knee))


def market_value_after_star_and_surplus_shape(player: dict[str, Any], valuation: dict[str, Any], raw: float) -> float:
    on_court = float(valuation.get("on_court_value") or raw)
    playoff = float(valuation.get("playoff_value") or 50.0)
    surplus = float(valuation.get("contract_surplus") or 0.0)
    development = float(valuation.get("development_upside") or 0.0)
    minutes = trade_value_role_minutes(player, valuation)
    age = maybe_float(player.get("age")) or 27.0
    # A cheap contract never lowers a player's value. The surplus credit is already scaled by player quality in the
    # asset value (surplus_quality_factor). An older correction here also subtracted (surplus - 16) at 0.82-1.12 per
    # point for anyone below on-court 80, about twice the credit itself, so a rookie deal counted *against* 202
    # players (Harper, Clingan, Ausar Thompson ~ -15; Wembanyama fell 4th -> 10th). Removed 2026-11-19.
    # The superstar floor used to switch on at hard cutoffs (on-court 79, playoff 80): Giannis at 78.2 sat ~25
    # value points below Luka at 79.6 (2026-11-17). It then ramped in over on-court 76-79 and playoff 77-80, but that
    # was still steep: a sub-point rating move swung Giannis ~5 points (2026-11-19). It now ramps in over on-court
    # 73-79 and playoff 74-80; players at or above the old cutoffs are valued exactly as before.
    star_share = clamp((on_court - 73.0) / 6.0, 0.0, 1.0) * clamp((playoff - 74.0) / 6.0, 0.0, 1.0)
    if minutes >= 28.0 and star_share > 0.0:
        superstar_floor = 94.0 + max(0.0, on_court - 79.0) * 1.55 + max(0.0, playoff - 80.0) * 0.66
        if on_court >= 86.0 and playoff >= 84.0:
            superstar_floor += 7.5 + max(0.0, on_court - 88.0) * 0.55
        if raw >= 84.0 and playoff >= 82.0:
            superstar_floor += 8.0 + max(0.0, raw - 85.0) * 0.82
        # Aging superstars keep a floor, but trade markets discount age steeply (was 0.16/yr past 32,
        # which kept 38-year-olds above prime All-NBA players; 2026-11-16 market review).
        superstar_floor -= max(0.0, age - 30.0) * 2.0
        raw = raw + star_share * max(0.0, superstar_floor - raw)
    # (This near-star floor used to be withheld when surplus >= 18, which made a bargain contract cost value.)
    if minutes >= 28.0 and star_share < 1.0 and on_court >= 76.5 and playoff >= 76.0:
        raw = max(raw, 84.0 + max(0.0, on_court - 76.5) * 0.68 + max(0.0, playoff - 76.0) * 0.18)
    return soft_value_ceiling(raw, ceiling=market_trade_value_cap(player, valuation, raw), knee=6.0)


def market_trade_value_cap(player: dict[str, Any], valuation: dict[str, Any], raw: float | None = None) -> float:
    on_court = float(valuation.get("on_court_value") or raw or valuation.get("player_value") or 0.0)
    playoff = float(valuation.get("playoff_value") or 50.0)
    player_value = float(valuation.get("player_value") or raw or 0.0)
    minutes = trade_value_role_minutes(player, valuation)
    if minutes >= 30.0 and on_court >= 86.0 and playoff >= 84.0:
        return 124.0
    if minutes >= 28.0 and player_value >= 84.0 and playoff >= 82.0:
        return 118.0
    if minutes >= 28.0 and on_court >= 82.0 and playoff >= 80.0:
        return 112.0
    return 99.0


def deterministic_low_role_value_variation(player: dict[str, Any]) -> float:
    token = f"{player.get('id')}:{player.get('name')}:{player.get('position')}:{player.get('age')}"
    return round(((sum(ord(char) for char in token) % 900) / 900.0) * 7.0, 2)


def drafted_rookie_value_floor(player: dict[str, Any] | None, ability: float | None = None, potential: float | None = None) -> float:
    if not player:
        return 0.0
    try:
        overall = int(player.get("draft_pick") or player.get("overall_pick") or 0)
    except (TypeError, ValueError):
        overall = 0
    if overall <= 0:
        return 0.0
    floor_factor = 1.0
    try:
        draft_year = int(player.get("draft_year") or 0)
    except (TypeError, ValueError):
        draft_year = 0
    active_season = str(player.get("_active_season") or "")
    if draft_year and active_season:
        seasons_since_draft = season_start_from_label(active_season) - draft_year
        if seasons_since_draft > 3:
            return 0.0
        floor_factor = {0: 1.0, 1: 0.92, 2: 0.82, 3: 0.70}.get(max(0, seasons_since_draft), 1.0)
    else:
        age = maybe_float(player.get("display_age")) or maybe_float(player.get("age"))
        if age is not None and age > 24.5:
            return 0.0
        if age is not None:
            floor_factor = clamp(1.0 - max(0.0, age - 21.0) * 0.1, 0.70, 1.0)
    ability = float(ability if ability is not None else maybe_float(player.get("current_ability")) or maybe_float(player.get("overall")) or 50.0)
    potential = float(potential if potential is not None else maybe_float(player.get("potential")) or ability)
    if overall <= 30:
        base = 83.0 - (overall - 1) * 1.42
        talent = max(0.0, potential - 70.0) * 0.3 + max(0.0, ability - 52.0) * 0.24
        return round(clamp(base + talent, 34.0, 88.0) * floor_factor, 2)
    base = 27.0 - (overall - 31) * 0.32
    talent = max(0.0, potential - 64.0) * 0.18 + max(0.0, ability - 50.0) * 0.12
    return round(clamp(base + talent, 7.0, 32.0) * floor_factor, 2)


def goat_exception_player(player: dict[str, Any] | None) -> bool:
    return normalize_name((player or {}).get("name") or "") == "lebron james"


FILLER_PREFERENCE = 2.0  # shortlist credit per player from the buyer's own "salary I'd move" list (TRADE-DEADLINE)


def buyer_offer_packages_for_value(
    canonical: dict[str, Any],
    buyer: dict[str, Any],
    seller: dict[str, Any],
    target_value: float,
    target_salary: float | None,
    seed: int,
    excluded_player_ids: set[str] | None = None,
    max_results: int = 18,
    max_player_options: int = 9,
    return_options: bool = False,
    allow_new_pick_swaps: bool = False,
    intent=None,
    repair_options=None,
    seller_view_outgoing: list[dict[str, Any]] | None = None,
) -> list[list[dict[str, Any]]] | list[dict[str, Any]]:
    """Build the buyer's candidate packages for a target worth ``target_value``.

    ``seller_view_outgoing`` (the target-driven search, trade step 2): the seller's outgoing assets. Packages are
    then aimed at the seller's own asking price: the buyer's players are tried in order of how much more the seller
    values them than the buyer does (a bench player who would start for the seller is the natural currency), and
    every package is measured with the seller's own values of the players and picks it receives.
    """
    as_of_date = ((canonical.get("meta") or {}).get("current_date")) or CANONICAL_START_DATE
    excluded_player_ids = set(excluded_player_ids or set()) | recently_traded_player_ids(canonical, as_of_date)
    # A held player (re_trade_hold) is never filler in a buyer's package; he can still be the target of a deal.
    excluded_player_ids |= {pid for pid, tid in re_trade_hold(canonical, as_of_date).items() if tid == buyer["id"]}
    valuations = player_asset_values_by_id(canonical)
    buyer_players = [player for player in canonical["players"] if player["team_id"] == buyer["id"]]
    duplicate_names = set()
    if intent is not None:
        names_seen = set()
        for row in buyer_players:
            if row['name'] in names_seen: duplicate_names.add(row['name'])
            names_seen.add(row['name'])
    salary_by_player = {
        player["id"]: current_salary(contract_for_player(canonical, player["id"])) or 0.0
        for player in buyer_players
    }
    block = {entry["player_id"]: entry for entry in canonical["trade_block_entries"] if entry["team_id"] == buyer["id"]}
    from .trade_wants import search_priority
    seller_view = seller_view_outgoing is not None
    if seller_view:
        from .team_planning import core_commitment
        def surplus(player):
            asset = [{'kind': 'player', 'id': player['id']}]
            return (package_value_for_team(canonical, asset, seller['id'], outgoing_assets=seller_view_outgoing)
                    - package_value_for_team(canonical, asset, buyer['id']))
        candidates = sorted(
            [player for player in buyer_players if player["id"] not in excluded_player_ids
             and not player.get('_inactive_player') and not core_commitment(canonical, buyer['id'], player['id'])],
            key=lambda player: (surplus(player), player["name"], player["id"]),
            reverse=True,
        )
    else:
        candidates = sorted(
            [player for player in buyer_players if player["id"] not in excluded_player_ids],
            key=lambda player: (
                block.get(player["id"], {}).get("block_score", 0) + 8*search_priority(canonical, seller['id'], {'kind': 'player', 'id': player['id']}),
                -abs(valuation_or_fallback(valuations, player["id"], player)["player_value"] - target_value * 0.72),
                -abs(salary_by_player.get(player["id"], 0.0) - (target_salary or 0)) / 1_000_000,
                player["name"],
            ),
            reverse=True,
        )
    from .trade_finance_search import classify_movements, unavailable_players
    unavailable = unavailable_players(canonical,intent.date) if intent is not None else frozenset()
    work = canonical.get('_search_work_counts')
    if intent is not None and any(a.get('kind')=='player' and a['id'] in unavailable for a in intent.target_assets):
        if work is not None:work['blocked_target_queries.terminal'] += 1
        return []
    tradable_players = []
    buyer_state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == buyer["id"]), {})
    for player in candidates:
        if player["id"] in unavailable:
            if work is not None:work["filtered_player_options.terminal"] += 1
            continue
        valuation = valuation_or_fallback(valuations, player["id"], player)
        value = float(valuation["player_value"])
        block_score = float(block.get(player["id"], {}).get("block_score") or 0.0)
        if value >= 72 and target_value < 70:
            continue
        if value >= 58 and block_score < 55 and target_value < 68:
            continue
        if value >= 62 and block_score < 62 and team_fit_for_player(player, valuation, buyer_state, canonical) >= 7.0 and target_value < value + 12.0:
            continue
        if value > target_value * (1.08 if target_value >= 70 else 1.24):
            continue
        tradable_players.append(player)
    tradable_players = tradable_players[:max(3, int(max_player_options))]
    filler_ids: dict[str, str] = {}
    if seller_view:
        # TRADE-DEADLINE: the buyer's own "salary I'd move" (trade_targets.salary_filler) is always available to
        # match salary, so it need not give up rotation players it values. The value screens above are skipped for
        # it: they keep a buyer from overpaying in talent, and filler is there for its salary (a team shedding a
        # $30M wing cannot be paid in $2M bench players). The seller still prices every player it takes.
        from .trade_targets import salary_filler
        filler_ids = salary_filler(canonical, buyer['id'])
        present = {player['id'] for player in tradable_players}
        tradable_players = tradable_players + [player for player in candidates if player['id'] in filler_ids
                                               and player['id'] not in present and player['id'] not in unavailable]
    picks = sorted(
        tradeable_picks_for_team(canonical, buyer["id"]),
        key=lambda pick: pick_offer_preference_score(pick, buyer_state.get("phase", "balanced"), target_value)
            + 8*search_priority(canonical, seller['id'], {'kind': 'pick', 'id': pick['id']}),
        reverse=True,
    )[:9]
    firsts = [pick for pick in picks if int(pick.get("round") or 2) == 1]
    seconds = [pick for pick in picks if int(pick.get("round") or 2) == 2]
    max_player_count = 3 if target_value >= 60 and int(max_player_options) > 5 else 2
    movements = {}
    direct_player_groups = intent is None
    if intent is not None:
        for count in range(1,min(max_player_count,len(tradable_players))+1):
            for group in combinations(tradable_players,count):
                key=tuple(p['id'] for p in group)
                movement=classify_movements(canonical,intent,[{'kind':'player','id':pid} for pid in key])
                movements[key]=movement
                if movement.category=='legal' or (movement.category=='unresolved' and
                        not intent.config.get('decision',{}).get('manual_review_blocks_execution',True)):
                    direct_player_groups=True
    if work is not None and not direct_player_groups:
        work['protection_option_queries_skipped'] += len(firsts[:3]) if return_options else 0
    protection_options = {p['id']: ai_pick_protection_options(canonical, buyer, seller, p,
        buyer_state.get('phase', 'neutral')) for p in firsts[:3]} if return_options and direct_player_groups else {}
    swaps = sorted(
        tradeable_pick_swaps_for_team(canonical, buyer["id"]),
        key=lambda swap: pick_swap_asset_value(canonical, swap, buyer_state.get("phase", "neutral")),
        reverse=True,
    )[:3]
    new_swap_options = (
        ai_pick_swap_grant_options(canonical, buyer, seller, target_value, seed, buyer_state.get("phase", "neutral"))
        if allow_new_pick_swaps and direct_player_groups
        else []
    )
    pick_variants = [()]
    pick_variants.extend((pick,) for pick in seconds[:4])
    pick_variants.extend((swap,) for swap in swaps)
    if len(seconds) >= 2:
        pick_variants.extend(combinations(seconds[:4], 2))
    if len(seconds) >= 3:
        pick_variants.append(tuple(seconds[:3]))
    if target_value >= 38:
        pick_variants.extend((pick,) for pick in firsts[:3])
        if target_value >= 70 and len(firsts) >= 2:
            pick_variants.extend(combinations(firsts[:5], 2))
        for first in firsts[:2]:
            for second in seconds[:3]:
                pick_variants.append((first, second))
    elif not seconds and firsts:
        pick_variants.append((firsts[0],))
    from .trade_package_search import PackageShortlist
    metrics = canonical.get('_package_search_diagnostics')
    phase = buyer_state.get('phase', 'neutral')
    seller_state = next(item for item in canonical['team_strategic_states'] if item['team_id'] == seller['id']) if (target_value >= 70 or seller_view) and tradable_players else None
    # Keep separate buyer rough-price and seller quote values. Preserve the
    # original sum grouping and the order of every floating-point addition.
    pick_data = []
    for group in pick_variants:
        assets = [{'kind': p.get('kind', 'pick'), 'value': p['id']} for p in group]
        values = [pick_swap_asset_value(canonical, p, phase) if p.get('kind') == 'pick_swap'
                  else pick_asset_value(p, phase) for p in group]
        risk = sum(far_future_pick_risk(p) for p in group)
        selected = {p['id'] for p in group}
        protections = [(pick_asset_value(p, phase), option) for p in group
                       for option in protection_options.get(p['id'], [])
                       if not selected.intersection(option['term']['fallback_pick_ids'])]
        seller_values = []
        if seller_state is not None:
            for p in group:
                normalized = {'kind': p.get('kind', 'pick'), 'id': p['id'], 'label': p.get('label') or p['id']}
                seller_values.append(pick_swap_asset_value(canonical, pick_swap_by_id(canonical, p['id']) or normalized, seller_state['phase'])
                                     if p.get('kind') == 'pick_swap' else
                                     pick_asset_value(pick_by_id(canonical, p['id']), seller_state['phase']))
        pick_data.append((group, assets, sum(values), risk, protections, seller_values))
    if metrics is not None:
        metrics['pick_variants'] += len(pick_data)
    packages = PackageShortlist(max_results, return_options, metrics)
    repairs = PackageShortlist(max_results, False)
    rough_value_by_player = {
        player["id"]: offer_player_rough_value(canonical, player, target_value, target_salary, valuations)
        for player in tradable_players
    }
    for player_count in range(1, min(max_player_count, len(tradable_players)) + 1):
        for player_group in combinations(tradable_players, player_count):
            player_assets = [{"kind": "player", "value": player["id"] if player["name"] in duplicate_names else player["name"]} for player in player_group]
            player_salary = sum(salary_by_player.get(player["id"], 0.0) for player in player_group)
            movement = movements[tuple(p['id'] for p in player_group)] if intent is not None else None
            if movement is not None and (movement.category=='terminal' or
                    (movement.category=='unresolved' and (intent.config or default_transaction_model_config()).get('decision',{}).get('manual_review_blocks_execution',True))):
                continue
            pool = repairs if movement is not None and movement.category=='repairable' else packages
            player_rough = sum(rough_value_by_player[player['id']] for player in player_group)
            if metrics is not None:
                metrics['player_groups'] += 1
            if seller_state is not None:
                normalized_players = [{'kind':'player', 'id':p['id'], 'label':p['name']} for p in player_group]
                player_total, concentration = package_value_components(canonical, normalized_players, seller['id'],
                                                                       seller_view_outgoing if seller_view else None)
            for pick_group, pick_assets, pick_value, distant_risk, protections, seller_values in pick_data:
                if metrics is not None:
                    metrics['group_variant_pairs'] += 1
                if len(player_assets) + len(pick_group) > 4:
                    continue
                assets = [*player_assets, *pick_assets]
                rough_value = player_rough + pick_value
                candidate_variants = [(assets, [], rough_value, distant_risk)]
                for unprotected_value, option in (protections if pool is packages else []):
                    protected_value = rough_value - unprotected_value + option['value']
                    candidate_variants.append((assets, [option['term']], protected_value, distant_risk+.3))
                if pool is packages and new_swap_options and len(assets) < 4 and target_value >= 34:
                    for swap_option in new_swap_options[:4]:
                        swap_asset = {"kind": "pick_swap", "value": swap_option["id"]}
                        swap_value = float(swap_option.get("value") or 0.0)
                        if swap_value <= 1.5:
                            continue
                        improved_gap = abs((rough_value + swap_value) - target_value) <= abs(rough_value - target_value) + 1.15
                        if not improved_gap and rough_value >= target_value * 0.88:
                            continue
                        candidate_variants.append(
                            (
                                [*assets, swap_asset],
                                [swap_option["term"]],
                                rough_value + swap_value,
                                distant_risk + float(swap_option.get("risk") or 0.0),
                            )
                        )
                for variant_assets, terms, variant_value, variant_risk in candidate_variants:
                    search_value = variant_value
                    if seller_view:
                        # Seller's own values; a protection or new swap moves it by its buyer-side price change.
                        search_value = player_total + concentration + (variant_value - rough_value)
                        for pick_price in seller_values:
                            search_value += pick_price
                    elif target_value >= 70 and not terms:
                        search_value = player_total
                        for pick_price in seller_values:
                            search_value += pick_price
                        search_value += concentration
                    if search_value < target_value * (0.34 if target_value >= 56 else 0.38) or search_value > target_value * 1.48 + 14:
                        continue
                    salary_gap = abs(player_salary - (target_salary or player_salary)) / 1_000_000
                    complexity_cost = max(0, len(variant_assets) - 2) * (0.1 if target_value >= 56 else 0.32)
                    complexity_cost -= FILLER_PREFERENCE * sum(1 for p in player_group if p['id'] in filler_ids)
                    if terms:
                        complexity_cost += 0.22
                    pool.append((abs(search_value - target_value) + salary_gap * 0.22 + complexity_cost + variant_risk, variant_assets, terms))
    # Teams with absorption room need not send a player back. Previously
    # pick-only payment was largely confined to the separate summer dump path.
    season = str(canonical.get('meta', {}).get('active_season') or CANONICAL_SEASON)
    if intent is not None or (target_salary is not None and team_current_salary_total(canonical, buyer['id']) + target_salary <= cap_lines_for_season(season)['tax_line']):
        empty_movement = classify_movements(canonical,intent,[]) if intent is not None else None
        for group, pick_assets, value, risk, _, _ in pick_data:
            if not group:
                continue
            assets = pick_assets
            movement = empty_movement
            if movement is not None and (movement.category=='terminal' or (movement.category=='unresolved' and intent.config.get('decision',{}).get('manual_review_blocks_execution',True))):
                continue
            pool = repairs if movement is not None and movement.category=='repairable' else packages
            if seller_view and seller_state is not None:
                value = sum(pick_asset_value(pick_by_id(canonical, p['id']), seller_state['phase']) if p.get('kind') != 'pick_swap'
                            else pick_swap_asset_value(canonical, p, seller_state['phase']) for p in group)
            if target_value*.38 <= value <= target_value*1.48+14:
                pool.append((abs(value-target_value)+risk, assets, []))
    if not packages and intent is None:
        fallback = fallback_trade_packages(canonical, buyer, seller, tradable_players, seconds, firsts, target_value, target_salary, valuations)
        packages.extend((score, assets, []) for score, assets in fallback)
    if repair_options is not None:
        repair_options.extend({'assets':[dict(a) for a in assets],'_repair_score':score}
                              for score,assets,terms in repairs.ordered())
    unique: list[list[dict[str, Any]]] = []
    unique_options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, assets, terms in packages.ordered():
        key = json.dumps({"assets": assets, "terms": terms}, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        if return_options:
            option = {"assets": [dict(asset) for asset in assets]}
            if terms:
                option["pick_obligation_terms"] = terms
            unique_options.append(option)
            if len(unique_options) >= max(4, int(max_results)):
                break
            continue
        if terms:
            continue
        unique.append([dict(asset) for asset in assets])
        if len(unique) >= max(4, int(max_results)):
            break
    if metrics is not None:
        metrics['shortlisted_packages'] += len(unique_options if return_options else unique)
    return unique_options if return_options else unique


def _protection_quote_view(canonical, primary, terms):
    """Value one independent protection without rebuilding unrelated rights.

    Compilation still validates the full authoritative inventory. Restrict only
    the derived annotation work, and fall back for any connected or ambiguous
    rights. This view is privately owned and never returned as a trade preview.
    """
    if (len(terms) == 1 and terms[0].get('type') == 'protected_pick'
            and terms[0].get('primary_pick_id') == primary['id']
            and len(terms[0].get('fallback_pick_ids') or []) == 1):
        term = terms[0]
        ids = {primary['id'], *(term.get('fallback_pick_ids') or [])}
        picks = [pick for pick in canonical.get('draft_picks', []) if pick.get('id') in ids]
        fields = ('primary_pick_id', 'team_a_pick_id', 'team_b_pick_id', 'counterparty_pick_id',
                  'nested_anchor_pick_id', 'nested_other_pick_id')
        connected = any(
            row.get('id') == term.get('id')
            or ids.intersection(row.get(field) for field in fields)
            or ids.intersection(row.get('fallback_pick_ids') or [])
            or ids.intersection(row.get('comparison_pool_pick_ids') or [])
            or ids.intersection(row.get('allocation_slot_pick_ids') or [])
            or ids.intersection((row.get(field) or {}).get('pick_id')
                                for field in ('nested_input', 'nested_other_input'))
            for row in canonical.get('pick_obligations', []))
        annotations = ('_obligations', '_obligation_locked', '_nested_entitlement', '_nested_leaf_picks',
                       '_ranked_entitlement', '_ranked_leaf_picks', '_unsupported_pick_condition_simplified')
        if (len(picks) == len(ids) and not connected
                and not ids.intersection(canonical.get('locked_pick_assets') or [])
                and not any(pick.get(field) for pick in picks for field in annotations)):
            view = {'meta': dict(canonical.get('meta') or {}), 'teams': canonical.get('teams', []),
                    'draft_picks': deepcopy(picks), 'pick_obligations': [{**deepcopy(term), 'status': 'active'}]}
            annotate_pick_obligation_context(view)
            stats = canonical.get('_market_review_stats')
            if stats is not None:
                stats['protection_quote_scoped'] += 1
            return view
    stats = canonical.get('_market_review_stats')
    if stats is not None:
        stats['protection_quote_fallback'] += 1
    return canonical_with_pending_pick_terms(canonical, terms)


def ai_pick_protection_options(canonical, buyer, seller, primary, phase='neutral', *, _full_reference=False):
    """Bounded top-4/top-10 protection with one real later first as fallback."""
    from .trade_pick_terms import compile_pick_rules, pick_rule_lock_reason
    if primary.get('round') != 1 or pick_rule_lock_reason(primary):
        return []
    fallback = next((p for p in sorted(tradeable_picks_for_team(canonical, buyer['id']),
                       key=lambda p: (str(p.get('season')), p['id']))
                     if p.get('round') == 1 and str(p['season']) > str(primary['season'])
                     and not pick_rule_lock_reason(p)), None)
    if fallback is None:
        return []
    options = []
    for top in (4, 10):
        rule = {'type': 'protected_pick', 'pick_id': primary['id'], 'from': 1, 'through': top,
                'fallback_pick_ids': [fallback['id']]}
        try:
            view, _, terms = compile_pick_rules(canonical, [rule], [
                {'team': buyer['id'], 'recipient': seller['id'], 'assets': [{'kind': 'pick', 'value': primary['id']}]}],
                _materialize=_full_reference)
        except ValueError:
            continue
        if not _full_reference:
            view = _protection_quote_view(canonical, primary, terms)
        options.append({'term': terms[0], 'value': pick_asset_value(pick_by_id(view, primary['id']), phase)})
    return options


def offer_player_rough_value(
    canonical: dict[str, Any],
    player: dict[str, Any],
    target_value: float,
    target_salary: float | None,
    valuations: dict[str, dict[str, Any]],
) -> float:
    valuation = valuation_or_fallback(valuations, player["id"], player)
    value = market_trade_target_value(player, valuation)
    salary = current_salary(contract_for_player(canonical, player["id"])) or 0.0
    filler = target_salary is not None and target_salary >= 8_000_000 and salary >= 5_000_000 and value < target_value * 0.55
    if filler:
        value *= 0.72
    elif target_value >= 56 and value < target_value * 0.62:
        value *= 0.88
    return value


def ai_pick_swap_grant_options(
    canonical: dict[str, Any],
    grantor: dict[str, Any],
    receiver: dict[str, Any],
    target_value: float,
    seed: int,
    phase: str = "neutral",
) -> list[dict[str, Any]]:
    if target_value < 34:
        return []
    active_year = season_start_from_label(str(canonical.get("meta", {}).get("active_season") or CANONICAL_SEASON))
    existing_pairs = {
        tuple(sorted([str(item.get("team_a_pick_id") or item.get("primary_pick_id") or ""), str(item.get("team_b_pick_id") or item.get("counterparty_pick_id") or "")]))
        for item in canonical.get("pick_obligations", [])
        if item.get("type") == "pick_swap" and item.get("status", "active") in {"active", "pending_resolution"}
    }
    grantor_picks = [
        pick
        for pick in tradeable_picks_for_team(canonical, grantor["id"])
        if int(pick.get("round") or 0) == 1
        and not pick.get("_obligation_locked")
        and (pick_season_start(pick) or 0) > active_year
    ]
    receiver_picks = [
        pick
        for pick in tradeable_picks_for_team(canonical, receiver["id"])
        if int(pick.get("round") or 0) == 1
        and not pick.get("_obligation_locked")
        and (pick_season_start(pick) or 0) > active_year
    ]
    options: list[tuple[float, dict[str, Any]]] = []
    for grantor_pick in grantor_picks[:10]:
        grantor_value = pick_asset_value(grantor_pick, phase)
        if grantor_value <= 0:
            continue
        if phase in {"rebuilding", "developing"} and grantor_value >= 72 and target_value < 90:
            continue
        for receiver_pick in receiver_picks[:10]:
            if receiver_pick.get("id") == grantor_pick.get("id"):
                continue
            if str(receiver_pick.get("season") or "") != str(grantor_pick.get("season") or ""):
                continue
            if int(receiver_pick.get("round") or 0) != int(grantor_pick.get("round") or 0):
                continue
            pair_key = tuple(sorted([str(grantor_pick.get("id")), str(receiver_pick.get("id"))]))
            if pair_key in existing_pairs:
                continue
            receiver_value = pick_asset_value(receiver_pick, phase)
            if receiver_value <= 0:
                continue
            if grantor_value + 8.0 < receiver_value:
                continue
            if grantor_value - receiver_value > 38.0 and target_value < 70:
                continue
            term = {
                "id": stable_id("ai_pick_swap", grantor["id"], receiver["id"], grantor_pick.get("id"), receiver_pick.get("id"), seed),
                "type": "pick_swap",
                "season": grantor_pick.get("season"),
                "round": int(grantor_pick.get("round") or 0),
                "team_a_pick_id": grantor_pick.get("id"),
                "team_b_pick_id": receiver_pick.get("id"),
                "original_rights_holder_team_id": receiver["id"],
                "current_rights_holder_team_id": receiver["id"],
                "counterparty_team_id": grantor["id"],
                "receiver_team_id": receiver["id"],
                "sender_team_id": grantor["id"],
                "benefit": "better",
                "label": "pick swap right",
                "pending_asset_grant": True,
                "notes": "AI-created same-season same-round pick-swap sweetener.",
                "transfer_history": [],
            }
            if not validate_pick_obligation_term(canonical, None, term):
                continue
            value = pick_swap_asset_value(canonical, term, phase)
            if value <= 1.5:
                continue
            risk = far_future_pick_risk(grantor_pick) * 0.55 + far_future_pick_risk(receiver_pick) * 0.25
            noise = (sum(ord(char) for char in f"{seed}:{term['id']}") % 100) / 1000.0
            score = abs(value - max(4.0, min(18.0, target_value * 0.14))) + risk - noise
            options.append((score, {"id": term["id"], "term": term, "value": value, "risk": risk}))
    return [option for _, option in sorted(options, key=lambda item: (item[0], item[1]["id"]))[:6]]


def fallback_trade_packages(
    canonical: dict[str, Any],
    buyer: dict[str, Any],
    seller: dict[str, Any],
    tradable_players: list[dict[str, Any]],
    seconds: list[dict[str, Any]],
    firsts: list[dict[str, Any]],
    target_value: float,
    target_salary: float | None,
    valuations: dict[str, dict[str, Any]],
) -> list[tuple[float, list[dict[str, Any]]]]:
    packages: list[tuple[float, list[dict[str, Any]]]] = []
    salary_sorted = sorted(
        tradable_players,
        key=lambda player: (
            abs((current_salary(contract_for_player(canonical, player["id"])) or 0.0) - (target_salary or 0.0)),
            offer_player_rough_value(canonical, player, target_value, target_salary, valuations),
        ),
    )
    for player in salary_sorted[:8]:
        player_value = offer_player_rough_value(canonical, player, target_value, target_salary, valuations)
        pick_pool = seconds[:3]
        if target_value >= 70 and firsts:
            pick_pool = [*firsts[:2], *seconds[:2]]
        elif target_value >= 44 and firsts:
            pick_pool = [*seconds[:2], firsts[0]]
        for pick_count in range(0, min(3, len(pick_pool)) + 1):
            pick_group = tuple(pick_pool[:pick_count])
            assets = [{"kind": "player", "value": player["name"]}, *[{"kind": "pick", "value": pick["id"]} for pick in pick_group]]
            rough = player_value + sum(pick_asset_value(pick, "neutral") for pick in pick_group)
            if rough < max(10.0, target_value * 0.28):
                continue
            if target_value >= 70 and rough < target_value * 0.74:
                continue
            packages.append((abs(rough - target_value) + len(assets) * 0.45 + sum(far_future_pick_risk(pick) for pick in pick_group), assets))
    if target_value >= 70 and firsts:
        player_pairs = list(combinations(salary_sorted[:8], 2))
        for player_group in player_pairs[:18]:
            player_value = sum(offer_player_rough_value(canonical, player, target_value, target_salary, valuations) for player in player_group)
            player_assets = [{"kind": "player", "value": player["name"]} for player in player_group]
            for pick_group in [tuple(firsts[:1]), tuple(firsts[:2]), tuple([*firsts[:1], *seconds[:1]])]:
                if not pick_group:
                    continue
                assets = [*player_assets, *[{"kind": "pick", "value": pick["id"]} for pick in pick_group]]
                if len(assets) > 4:
                    continue
                rough = player_value + sum(pick_asset_value(pick, "neutral") for pick in pick_group)
                if rough < target_value * 0.78:
                    continue
                packages.append((abs(rough - target_value) + len(assets) * 0.38 + sum(far_future_pick_risk(pick) for pick in pick_group), assets))
    return packages


def asset_package_value(canonical: dict[str, Any], assets: list[dict[str, Any]], phase: str = "neutral") -> float:
    values = player_asset_values_by_id(canonical)
    total = 0.0
    for asset in assets:
        if asset.get("kind") == "player":
            player = player_by_id(canonical, asset.get("id"))
            total += market_trade_target_value(player, values.get(asset.get("id"), fallback_asset_valuation(player)))
        elif asset.get("kind") == "pick":
            total += pick_asset_value(pick_by_id(canonical, asset.get("id")), phase)
        elif asset.get("kind") == "pick_swap":
            total += pick_swap_asset_value(canonical, pick_swap_by_id(canonical, asset.get("id")) or asset, phase)
    return round(total, 2)


def asset_package_salary(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> float | None:
    salary = 0.0
    found_player = False
    for asset in assets:
        if asset.get("kind") != "player":
            continue
        found_player = True
        player_salary = current_salary(contract_for_player(canonical, asset.get("id")))
        if player_salary is None:
            return None
        salary += float(player_salary)
    return salary if found_player else None


def trade_specs_from_normalized(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = []
    for asset in assets:
        if asset.get("kind") == "player":
            specs.append({"kind": "player", "value": asset.get("label") or asset.get("id")})
        elif asset.get("kind") == "pick":
            specs.append({"kind": "pick", "value": asset.get("id")})
        elif asset.get("kind") == "pick_swap":
            specs.append({"kind": "pick_swap", "value": asset.get("id")})
    return specs


def package_report_subject(canonical: dict[str, Any], assets: list[dict[str, Any]], seller: dict[str, Any]) -> dict[str, Any]:
    labels = [asset.get("label") or asset.get("id") for asset in assets]
    player_assets = [asset for asset in assets if asset.get("kind") == "player"]
    primary = player_by_id(canonical, player_assets[0]["id"]) if player_assets else None
    if primary:
        subject = compact_player(primary)
    else:
        subject = {
            "player_id": None,
            "name": ", ".join(labels),
            "team_id": seller["id"],
            "team_abbrev": seller["abbrev"],
            "position": "PICK",
            "age": None,
            "minutes_projection": 0,
        }
    subject["package_label"] = ", ".join(labels)
    return subject


def buyer_teams_for_asset_package(canonical: dict[str, Any], seller: dict[str, Any], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    player_assets = [asset for asset in assets if asset.get("kind") == "player"]
    if player_assets:
        teams: dict[str, tuple[float, dict[str, Any]]] = {}
        for asset in player_assets:
            player = player_by_id(canonical, asset.get("id"))
            if not player:
                continue
            for rank, team in enumerate(buyer_teams_for_player(canonical, player)):
                score = 30.0 - rank
                previous = teams.get(team["id"], (0.0, team))
                teams[team["id"]] = (previous[0] + score, team)
        return [team for _, team in sorted(teams.values(), key=lambda item: (item[0], item[1]["abbrev"]), reverse=True)]
    phase_bonus = {"rebuilding": 5.0, "developing": 4.0, "retooling": 2.0}
    ranked = []
    for team in canonical["teams"]:
        if team["id"] == seller["id"]:
            continue
        state = next((item for item in canonical.get("team_strategic_states", []) if item["team_id"] == team["id"]), {})
        ranked.append((phase_bonus.get(state.get("phase"), 0.0), team))
    return [team for _, team in sorted(ranked, key=lambda item: (item[0], item[1]["abbrev"]), reverse=True)]


def single_player_salary_match_ok(canonical: dict[str, Any], outgoing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    outgoing_salary = current_salary(contract_for_player(canonical, outgoing["id"]))
    incoming_salary = current_salary(contract_for_player(canonical, incoming["id"]))
    if outgoing_salary is None or incoming_salary is None:
        return True
    floor = 7_500_000
    multiplier = 1.25
    plus = 7_500_000
    if incoming_salary > floor and incoming_salary > outgoing_salary * multiplier + plus:
        return False
    if outgoing_salary > floor and outgoing_salary > incoming_salary * multiplier + plus:
        return False
    return True


def package_variants(assets: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not assets:
        return []
    variants = [assets]
    if len(assets) > 1:
        variants.append(assets[:1])
    return variants


def buyer_teams_for_player(canonical: dict[str, Any], player: dict[str, Any]) -> list[dict[str, Any]]:
    from .trade_wants import search_priority
    valuations = player_asset_values_by_id(canonical)
    value = valuation_or_fallback(valuations, player["id"], player)
    teams = []
    for team in canonical["teams"]:
        if team["id"] == player["team_id"]:
            continue
        state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team["id"])
        broad_fit = team_fit_for_player(player, value, state, canonical, include_spatial=False)
        broad_fit += search_priority(canonical, team['id'], {'kind': 'player', 'id': player['id']})
        if broad_fit >= 3:
            spatial = spatial_fit_delta(canonical, team["id"], player, cap=3.0)
            teams.append((broad_fit + spatial, team))
    return [team for _, team in sorted(teams, key=lambda item: (item[0], item[1]["abbrev"]), reverse=True)]


def candidate_from_evaluation(canonical: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    evaluations = report["evaluations"]
    combined = sum(item["net_value"] for item in evaluations)
    proposal = report["proposal"]
    from .trade_wants import asset_matches
    wants_matches = [{'team_id': tid, 'asset_id': asset['id'], **match}
                     for tid, _, incoming in trade_team_flows(proposal) for asset in incoming
                     for match in asset_matches(canonical, tid, asset)]
    return {
        "proposal": proposal,
        "legality": report["legality"],
        "evaluations": evaluations,
        "accepted_by_all": report["accepted_by_all"],
        "combined_score": round(combined, 3),
        "summary": proposal_summary(canonical, proposal),
        "value_breakdown": deepcopy(report["value_breakdown"]) if report.get("value_breakdown") is not None else trade_value_breakdown(canonical, proposal),
        "wants_matches": wants_matches,
        **{key: deepcopy(report[key]) for key in
           ('pick_obligation_terms', 'pick_trade_terms', 'pick_obligation_terms_prompted',
            'evaluation_seed', 'evaluation_proposal_id') if key in report},
    }


def candidate_from_decision(report: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields used by search policy until the offer is retained."""
    proposal = report['proposal']
    candidate = {
        'proposal': proposal,
        'legality': report['legality'],
        'evaluations': report['evaluations'],
        'accepted_by_all': report['accepted_by_all'],
        'combined_score': round(sum(item['net_value'] for item in report['evaluations']), 3),
    }
    for key in ('pick_obligation_terms', 'pick_trade_terms', 'pick_obligation_terms_prompted',
                'evaluation_seed', 'evaluation_proposal_id'):
        if key in report:
            candidate[key] = deepcopy(report[key])
    return candidate


def prepare_ai_trade_candidate(
    canonical: dict[str, Any],
    candidate: dict[str, Any],
    *,
    seed: int = 1,
    date: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the public report for a retained offer from its evaluation snapshot."""
    proposal = candidate['proposal']
    evaluation_seed = int(candidate.get('evaluation_seed', seed))
    proposal_date = date or proposal.get('date') or CANONICAL_START_DATE
    if proposal.get('transfers'):
        from .multi_team_trades import evaluate_multi_team_trade, transfers_for_revalidation
        # A pick-swap condition turns its pick into a pick_swap asset in the stored proposal; re-evaluation
        # needs the original pick back (same as the apply and app paths), or compile_pick_rules cannot find it.
        prepared = evaluate_multi_team_trade(
            canonical,
            transfers_for_revalidation(candidate),
            pick_rules=candidate.get('pick_rules'),
            seed=evaluation_seed,
            date=proposal_date,
            config=config,
            proposal_id=proposal.get('id'),
        )
    else:
        from_team = team_by_id(canonical, proposal.get('from_team_id'))
        to_team = team_by_id(canonical, proposal.get('to_team_id'))
        base_proposal_id = candidate.get('evaluation_proposal_id') or proposal.get('id')
        report = _evaluate_trade_snapshot(
            canonical,
            from_team['abbrev'],
            to_team['abbrev'],
            [{'kind': asset['kind'], 'value': asset['id']} for asset in proposal.get('from_assets', [])],
            [{'kind': asset['kind'], 'value': asset['id']} for asset in proposal.get('to_assets', [])],
            seed=evaluation_seed,
            date=proposal_date,
            config=config,
            context_ready=True,
            include_presentation=True,
            proposal_id=base_proposal_id,
        )
        pick_terms = candidate.get('pick_obligation_terms') or candidate.get('pick_trade_terms')
        if pick_terms:
            report = trade_result_with_pick_terms(report, pick_terms)
        prepared = candidate_from_evaluation(canonical, report)

    if candidate.get('ai_acceptance_override'):
        prepared = mark_ai_trade_accepted(prepared)

    presentation_fields = {
        'proposal', 'legality', 'evaluations', 'accepted_by_all', 'combined_score',
        'summary', 'value_breakdown', 'wants_matches', 'pick_obligation_terms',
        'pick_trade_terms', 'pick_obligation_terms_prompted', 'evaluation_seed',
        'evaluation_proposal_id', 'pick_rules',
    }
    for key, value in candidate.items():
        if key not in presentation_fields:
            prepared[key] = deepcopy(value)
    return prepared


def user_facing_trade_candidate_ok(canonical: dict[str, Any], candidate: dict[str, Any], user_team_id: str) -> bool:
    if candidate.get("legality", {}).get("status") != "legal":
        return False
    proposal = candidate.get("proposal") or {}
    evaluations = candidate.get("evaluations") or []
    non_user_evals = [item for item in evaluations if item.get("perspective_team_id") != user_team_id]
    if non_user_evals and not all(item.get("accepted") for item in non_user_evals):
        return False
    user_eval = next((item for item in evaluations if item.get("perspective_team_id") == user_team_id), {})
    if float(user_eval.get("net_value") or 0) < -18.0:
        return False
    if float(user_eval.get("net_value") or 0) > 28:
        return False
    _, outgoing, incoming = next((r for r in trade_team_flows(proposal) if r[0] == user_team_id), (user_team_id, [], []))
    incoming_total = simple_asset_total(canonical, incoming)
    outgoing_total = simple_asset_total(canonical, outgoing)
    incoming_star = max_player_value(canonical, incoming)
    outgoing_star = max_player_value(canonical, outgoing)
    if incoming_star >= 68 and outgoing_star < incoming_star - 15 and outgoing_total < incoming_total * 0.88:
        return False
    return True


def candidate_sort_score(candidate: dict[str, Any], user_team_id: str) -> float:
    evaluations = candidate.get("evaluations") or []
    user_eval = next((item for item in evaluations if item.get("perspective_team_id") == user_team_id), {})
    non_user_eval = next((item for item in evaluations if item.get("perspective_team_id") != user_team_id), {})
    user_net = float(user_eval.get("net_value") or 0.0)
    partner_net = float(non_user_eval.get("net_value") or 0.0)
    return partner_net * 0.65 - abs(user_net) * 0.22 + min(8.0, max(-8.0, user_net)) * 0.08


def simple_asset_total(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> float:
    state = next(iter(canonical.get("team_strategic_states", [])), {"phase": "balanced"})
    total = 0.0
    values = player_asset_values_by_id(canonical)
    for asset in assets:
        if asset.get("kind") == "player":
            player = player_by_id(canonical, asset.get("id"))
            total += market_trade_target_value(player, values.get(asset.get("id"), fallback_asset_valuation(player)))
        elif asset.get("kind") == "pick":
            total += pick_asset_value(pick_by_id(canonical, asset.get("id")), state.get("phase", "balanced"))
        elif asset.get("kind") == "pick_swap":
            total += pick_swap_asset_value(canonical, pick_swap_by_id(canonical, asset.get("id")) or asset, state.get("phase", "balanced"))
    return total


def max_player_value(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> float:
    values = player_asset_values_by_id(canonical)
    return max(
        [
            market_trade_target_value(
                player_by_id(canonical, asset.get("id")),
                values.get(asset.get("id"), fallback_asset_valuation(player_by_id(canonical, asset.get("id")))),
            )
            for asset in assets
            if asset.get("kind") == "player"
        ]
        or [0.0]
    )


def trade_value_breakdown(canonical: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    if proposal.get('transfers'):
        return {'version': 2, 'per_team': {tid: {'receives': package_value_breakdown(canonical, incoming, tid, outgoing),
                                  'sends': package_value_breakdown(canonical, outgoing, tid)}
                             for tid, outgoing, incoming in trade_team_flows(proposal)}}
    return {
        "version": 2,
        "from_team_receives": package_value_breakdown(canonical, proposal.get("to_assets", []), proposal.get("from_team_id"), proposal.get("from_assets", [])),
        "to_team_receives": package_value_breakdown(canonical, proposal.get("from_assets", []), proposal.get("to_team_id"), proposal.get("to_assets", [])),
        # Each team's own price for what it gives up (own-player view: actual role, attachment, tenure, investment).
        "from_team_sends": package_value_breakdown(canonical, proposal.get("from_assets", []), proposal.get("from_team_id")),
        "to_team_sends": package_value_breakdown(canonical, proposal.get("to_assets", []), proposal.get("to_team_id")),
    }


def player_trade_value_components(
    valuation: dict[str, Any],
    player_value: float,
    fit: float,
    multiplier: float,
) -> dict[str, float]:
    """Explain a player's destination value without changing the trade model."""
    weights = default_transaction_model_config().get("valuation_weights", {})
    raw = {
        "quality": float(valuation.get("on_court_value") or 0.0),
        "age_upside": (
            float(valuation.get("age_curve") or 0.0) * float(weights.get("age_curve", 0.9))
            + float(valuation.get("development_upside") or 0.0) * float(weights.get("development_upside", 0.75))
        ),
        "contract": float(valuation.get("contract_surplus") or 0.0) * float(weights.get("contract_surplus", 0.42)),
        "scarcity": float(valuation.get("role_scarcity") or 0.0) * float(weights.get("role_scarcity", 0.55)),
        "playoffs": (float(valuation.get("playoff_value") or 50.0) - 50.0) * float(weights.get("playoff_value", 0.16)),
        "health": -float(valuation.get("health_risk") or 0.0) * float(weights.get("health_risk", 0.55)),
    }
    raw_total = sum(raw.values())
    if abs(raw_total) > 0.001:
        scaled = {key: value * player_value / raw_total for key, value in raw.items()}
    else:
        scaled = {key: 0.0 for key in raw}
        scaled["quality"] = player_value
    scaled["fit"] = fit
    scaled["role"] = (player_value + fit) * (multiplier - 1.0)
    return {key: round(value, 2) for key, value in scaled.items() if abs(value) >= 0.005}


def package_value_breakdown(canonical: dict[str, Any], assets: list[dict[str, Any]], perspective_team_id: str | None,
                            outgoing_assets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    values = player_asset_values_by_id(canonical)
    state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == perspective_team_id), {})
    pieces = {
        "player_quality": 0.0,
        "role_value": 0.0,
        "age_timeline": 0.0,
        "contract": 0.0,
        "lineup_fit": 0.0,
        "health": 0.0,
        "pick_value": 0.0,
        "cap_roster": 0.0,
        "concentration": 0.0,
        "gm_modifier": 0.0,
        "attachment": 0.0,
        "tenure": 0.0,
        "investment": 0.0,
    }
    asset_details: list[dict[str, Any]] = []
    multipliers = destination_role_multipliers(canonical, assets, perspective_team_id, outgoing_assets or [])
    own_ids = own_ai_player_ids(canonical, assets, perspective_team_id) if state else set()
    own_state = own_departure_state(canonical, perspective_team_id, state, own_ids) if own_ids else state
    for asset in assets:
        if asset.get("kind") == "player":
            player = player_by_id(canonical, asset.get("id"))
            valuation = values.get(asset.get("id"), fallback_asset_valuation(player))
            player_value = market_trade_target_value(player, valuation)
            own = asset.get("id") in own_ids
            fit = team_fit_for_player(player, valuation, own_state if own else state, canonical, include_spatial=False) if player and state else 0.0
            multiplier = multipliers.get(asset.get("id"), 1.0)
            health = -max(0.0, float(valuation.get("health_risk") or 0.0) - 12.0) * 0.25
            role_value = (player_value + fit) * multiplier
            # A team far from contending values a veteran's current production less (as package_value_components).
            timeline = (role_value * (veteran_present_factor(state, player) - 1.0)
                        if role_value > 0 and state and perspective_team_id not in set(canonical.get('_human_team_ids') or []) else 0.0)
            premium = (own_player_premium(canonical, player, perspective_team_id, role_value + timeline + health,
                                          market_value=player_value) if own else {})
            retention = 0.0 if own else recently_acquired_player_premium(canonical, player, perspective_team_id, player_value)
            pieces["player_quality"] += player_value
            pieces["role_value"] += (player_value + fit) * (multiplier - 1.0)
            if player and state:
                pieces["lineup_fit"] += fit
            pieces["health"] += health
            pieces["cap_roster"] += retention
            pieces["age_timeline"] += timeline
            components = player_trade_value_components(valuation, player_value, fit, multiplier)
            components["health"] = round(components.get("health", 0) + health, 2)
            if timeline:
                components["rebuild_timeline"] = round(timeline, 2)
            if retention:
                components["retention"] = round(retention, 2)
            for name in ("attachment", "tenure", "investment"):
                if premium.get(name):
                    pieces[name] += premium[name]
                    components[name] = round(premium[name], 2)
            detail = {
                "kind": "player",
                "id": asset.get("id"),
                "label": player.get("name") if player else asset.get("label") or asset.get("id"),
                "raw_value": round(player_value + fit, 2),
                "listed_value": round(player_value, 2),
                "role_multiplier": round(multiplier, 3),
                "adjusted_value": round(role_value + timeline + health + retention + float(premium.get("total") or 0.0), 2),
                "expected_role": role_label_from_multiplier(multiplier),
                "components": components,
            }
            if own:
                detail["own_player_view"] = {
                    "role_minutes": trade_value_role_minutes(player, valuation),
                    **{k: v for k, v in (premium.get("detail") or {}).items() if k not in {"attachment", "tenure", "investment"}},
                }
            asset_details.append(detail)
        elif asset.get("kind") == "pick":
            pick_value = pick_asset_value(pick_by_id(canonical, asset.get("id")), state.get("phase", "balanced"))
            pieces["pick_value"] += pick_value
            asset_details.append(
                {
                    "kind": "pick",
                    "id": asset.get("id"),
                    "label": asset.get("label") or asset.get("id"),
                    "raw_value": round(pick_value, 2),
                    "role_multiplier": 1.0,
                    "adjusted_value": round(pick_value, 2),
                    "expected_role": "draft asset",
                    "components": {"draft_capital": round(pick_value, 2)},
                }
            )
        elif asset.get("kind") == "pick_swap":
            swap = pick_swap_by_id(canonical, asset.get("id")) or asset
            swap_value = pick_swap_asset_value(canonical, swap, state.get("phase", "balanced"))
            pieces["pick_value"] += swap_value
            asset_details.append(
                {
                    "kind": "pick_swap",
                    "id": asset.get("id"),
                    "label": asset.get("label") or pick_swap_display_label(canonical, swap),
                    "raw_value": round(swap_value, 2),
                    "role_multiplier": 1.0,
                    "adjusted_value": round(swap_value, 2),
                    "expected_role": "swap right",
                    "components": {"swap_value": round(swap_value, 2)},
                }
            )
    pieces["concentration"] = package_concentration_adjustment(
        [float(item.get("adjusted_value") or 0.0) for item in asset_details if item.get("kind") == "player"]
    )
    # Manager preferences belong to the decision, not the asset ledger.
    pieces = {key: round(value, 2) for key, value in pieces.items()}
    pieces["total"] = round(sum(pieces.values()), 2)
    pieces["asset_details"] = asset_details
    return pieces


def role_label_from_multiplier(multiplier: float) -> str:
    if multiplier >= 1.08:
        return "star / top option"
    if multiplier >= 0.9:
        return "major starter"
    if multiplier >= 0.68:
        return "rotation piece"
    if multiplier >= 0.48:
        return "bench depth"
    return "fringe depth"


def premium_return_issue(canonical, team_id, incoming_assets, outgoing_assets):
    """A positive sum of depth prices is not a replacement for a core anchor."""
    if team_id in canonical.get('_human_team_ids', []):
        return None
    state = next((s for s in canonical.get('team_strategic_states', []) if s.get('team_id') == team_id), None)
    if not state:
        return None
    competitive = state.get('window_phase') in {'entering', 'peak'} or state.get('phase') in {'contending', 'contending_with_future_upside'}
    values = player_asset_values_by_id(canonical)
    outgoing = [player_by_id(canonical, a['id']) for a in outgoing_assets if a.get('kind') == 'player']
    premium = []
    for player in outgoing:
        if not player:
            continue
        value = values.get(player['id'], {})
        premium_anchor = (float(value.get('on_court_value') or 0) >= 76.5
                          and float(value.get('playoff_value') or 0) >= 76)
        competitive_starter = (competitive and float(value.get('on_court_value') or 0) >= 68
                               and trade_value_role_minutes(player, value) >= 24)
        if ((premium_anchor or competitive_starter)
                and float(value.get('contract_surplus') or 0) > -16
                and float(value.get('health_risk') or 0) < 30):
            premium.append(player)
    if not premium:
        return None
    anchor = max(premium, key=lambda p: float(values[p['id']]['on_court_value']))
    quality = float(values[anchor['id']]['on_court_value'])
    playoff = float(values[anchor['id']].get('playoff_value') or 50)
    price = market_trade_target_value(anchor, values[anchor['id']])
    for asset in incoming_assets:
        if asset.get('kind') != 'player':
            continue
        player = player_by_id(canonical, asset['id'])
        if not player:
            continue
        value = values.get(player['id'], {})
        ability = float(value.get('on_court_value') or 0)
        if ability >= quality-4 and float(value.get('playoff_value') or 0) >= playoff-8:
            return None
        age = float(player.get('display_age', player.get('age')) or 99)
        if (age <= 25 and ability >= max(60, quality-18)
                and float(value.get('development_upside') or 0) >= 12
                and market_trade_target_value(player, value) >= price*.6):
            return None
    plan = canonical.get('team_plans', {}).get(team_id, {})
    reviewing = bool(plan.get('review_exception') or plan.get('route') == 'review_core_ceiling_and_retool_alternatives')
    if not competitive or reviewing:
        firsts = [pick_asset_value(pick_by_id(canonical, pid), state.get('phase', 'neutral'))
                  for pid in sorted({a['id'] for a in incoming_assets if a.get('kind') == 'pick'})
                  if (pick_by_id(canonical, pid) or {}).get('round') == 1]
        if firsts and max(firsts) >= price*.25 and sum(firsts) >= price*.5:
            return None
    return 'Premium player return lacks a comparable contributor or credible young centerpiece' + (
        '; this competing core is not being rebuilt.' if competitive and not reviewing else ' or substantive first-round compensation.')


def evaluate_trade_participants(canonical, proposal, legality, seed, config, *, include_presentation=True, early_reject=False):
    flows = trade_team_flows(proposal)
    calculations = {}
    def evaluate_flow(tid, incoming, outgoing, *, plan_roster):
        kwargs = {'plan_roster': plan_roster, '_calculation_cache': calculations}
        if not include_presentation:
            kwargs['include_presentation'] = False
        return evaluate_trade_for_team(canonical, proposal, tid, incoming, outgoing,
            legality, seed, config, **kwargs)

    preliminary = []
    for tid, outgoing, incoming in flows:
        evaluation = evaluate_flow(tid,incoming,outgoing,plan_roster=False)
        preliminary.append(evaluation)
        if early_reject and ((not evaluation.accepted and evaluation.net_value < -9)
                or any(str(r).startswith('Core commitment:') for r in evaluation.decision_reasons)):
            if canonical.get('_search_work_counts') is not None:
                canonical['_search_work_counts']['skipped_reports.authoritative_preliminary'] += 1
            return []
    human = set(canonical.get('_human_team_ids') or [])
    viable = legality['status'] == 'legal' and all(
        e.perspective_team_id in human or (e.net_value >= -9 and e.decision != 'reject_premium_return'
            and not any(str(reason).startswith('Core commitment:') for reason in e.decision_reasons)) for e in preliminary)
    if not viable:
        return preliminary
    return [e if tid in human else evaluate_flow(tid, incoming, outgoing, plan_roster=True)
            for e, (tid, outgoing, incoming) in zip(preliminary, flows)]


def evaluate_trade_for_team(
    canonical: dict[str, Any],
    proposal: TradeProposal,
    perspective_team_id: str,
    incoming_assets: list[dict[str, Any]],
    outgoing_assets: list[dict[str, Any]],
    legality: dict[str, Any],
    seed: int,
    config: dict[str, Any],
    *, plan_roster: bool = True, include_presentation: bool = True, _calculation_cache=None,
) -> TradeEvaluation:
    if canonical.get('_search_work_counts') is not None:
        canonical['_search_work_counts']['participant_team_calls'] += 1
    if _calculation_cache is not None and perspective_team_id in _calculation_cache:
        if canonical.get('_search_work_counts') is not None:
            canonical['_search_work_counts']['within_proposal_calculation_hits'] += 1
        incoming, outgoing, strategic, wants, space_bonus, tax_term, personality, net, threshold, accepted, committed, commitment_blocked, premium_issue = _calculation_cache[perspective_team_id]
    else:
        incoming = package_value_for_team(canonical, incoming_assets, perspective_team_id, outgoing_assets=outgoing_assets)
        outgoing = package_value_for_team(canonical, outgoing_assets, perspective_team_id)
        strategic = strategic_fit_adjustment(canonical, incoming_assets, outgoing_assets, perspective_team_id, config)
        from .trade_wants import package_preference
        wants = package_preference(canonical, perspective_team_id, incoming_assets, outgoing_assets, config=config)
        strategic += wants['adjustment']
        from .roster_space import sale_bonus
        space_bonus = sale_bonus(canonical, perspective_team_id, incoming_assets, outgoing_assets, outgoing)
        strategic += space_bonus
        from .trade_tax import tax_value
        # Luxury tax saved (or added) is value for an AI team (trade 2b); the human team's own view is unchanged.
        # Trade step 4: salary taken on for players outside the team's rotation is a cost (trade_tax.absorb_cost).
        from .trade_tax import absorb_cost
        tax_term = (tax_value(canonical, perspective_team_id, incoming_assets, outgoing_assets),
                    absorb_cost(canonical, perspective_team_id, incoming_assets, outgoing_assets))
        strategic += tax_term[0] + tax_term[1]
        personality = personality_trade_adjustment(canonical, perspective_team_id, proposal.id, seed,
                                                   incoming=incoming_assets, outgoing=outgoing_assets,
                                                   tax_term=tax_term[0], proposal=proposal)
        net = incoming - outgoing + strategic + personality["total"]
        threshold = contextual_acceptance_threshold(canonical, perspective_team_id, config, incoming_assets, outgoing_assets)
        accepted = net >= threshold and legality["status"] == "legal"
        from .team_planning import core_commitment
        committed = any(a.get('kind') == 'player' and core_commitment(canonical, perspective_team_id, a.get('id')) for a in outgoing_assets)
        commitment_blocked = committed and net < max(12.0, outgoing*.20)
        if commitment_blocked:
            accepted = False
        premium_issue = premium_return_issue(canonical, perspective_team_id, incoming_assets, outgoing_assets)
        if premium_issue:
            accepted = False
        if _calculation_cache is not None:
            _calculation_cache[perspective_team_id] = (incoming, outgoing, strategic, wants, space_bonus, tax_term, personality, net, threshold, accepted, committed, commitment_blocked, premium_issue)
    outlook = None
    if (plan_roster and legality['status'] == 'legal' and net >= -9 and not premium_issue and not commitment_blocked
            and perspective_team_id not in canonical.get('_human_team_ids', [])):
        from .trade_roster import trade_roster_outlook
        outlook = trade_roster_outlook(canonical, perspective_team_id, incoming_assets, outgoing_assets)
        if outlook:
            strategic += outlook['adjustment']
            net += outlook['adjustment']
            accepted = net >= threshold and not outlook['issue']
    decision = "accept" if accepted else "reject"
    if outlook and (outlook['issue'] or (outlook['adjustment'] < 0 and net < threshold)):
        decision = 'reject_roster_plan'
    investment = (outlook or {}).get('pick_investment')
    if investment and (net < -investment['loss_limit'] or ((investment['incoming_rotation_minutes'] < 24 or investment['rotation_gain'] < .25)
            and investment['net_draft_value_spent'] > investment['capital_limit'])):
        accepted = False
        decision = 'reject_pick_investment'
    if premium_issue:
        decision = 'reject_premium_return'
    if legality["status"] == "manual_review_required":
        decision = "manual_review_required"
    if legality["status"] == "illegal":
        decision = "illegal_reject"
    reasons = []
    if commitment_blocked:
        reasons.append('Core commitment: this return does not justify breaking the current trial window.')
    if premium_issue:
        reasons.append(premium_issue)
    if outlook and outlook['issue']:
        reasons.append(outlook['issue'])
    if decision == 'reject_pick_investment':
        reasons.append('Too much draft capital for the projected rotation improvement.')
    if net < threshold:
        reasons.append(f'Net value {net:.2f} is below the required {threshold:.2f}.')
    if legality['status'] != 'legal':
        reasons.extend(legality.get('issues', []) + legality.get('manual_review', []))
    from .trade_tax import tax_note, absorb_note
    state = next((s for s in canonical.get('team_strategic_states', []) if s.get('team_id') == perspective_team_id), {})
    return TradeEvaluation(
        id=stable_id("trade_evaluation", proposal.id, perspective_team_id),
        proposal_id=proposal.id,
        perspective_team_id=perspective_team_id,
        accepted=accepted,
        decision=decision,
        incoming_value=round(incoming + strategic, 3),
        outgoing_value=round(outgoing, 3),
        net_value=round(net, 3),
        legality_status=legality["status"],
        legality_issues=list(legality["issues"]),
        personality_adjustments=personality,
        acceptance_threshold=threshold,
        window_phase=state.get('window_phase'),
        incoming_asset_value=round(incoming, 3),
        strategic_adjustment=round(strategic, 3),
        decision_reasons=reasons,
        notes=(
            evaluation_notes(canonical, perspective_team_id, net, threshold, strategic, personality, legality, accepted=accepted)
            + (' Core commitment: ordinary return does not justify breaking the current trial window.' if commitment_blocked else '')
            + (f' {premium_issue}' if premium_issue else '')
            + (f' Roster-space opportunity credit: {space_bonus:.2f}.' if space_bonus else '')
            + (tax_note(canonical, perspective_team_id, incoming_assets, outgoing_assets, tax_term[0]) if tax_term[0] else '')
            + (absorb_note(canonical, perspective_team_id, incoming_assets, outgoing_assets, tax_term[1]) if tax_term[1] else '')
            + (f" Published wants: {len(wants['matches'])} matching asset(s), additional preference credit {wants['adjustment']:.2f}." if wants['matches'] else '')
            + (f" Final roster: strength {outlook['strength_delta']:+.2f}; incremental waiver cost ${outlook['waiver_cost_millions']:.2f}M. {outlook['issue'] or ''}" if outlook else '')
            + (f" Fit with the current core: the projected rotation gets worse, so {outlook['system_fit_discount']:.1f} of the general fit credit is taken back." if outlook and outlook.get('system_fit_discount') else '')
            + (f" Draft investment: {investment['net_draft_value_spent']:.2f} net value spent; marginal-acquisition capital limit {investment['capital_limit']:.2f}; justified value-loss limit {investment['loss_limit']:.2f}." if investment else '')
            + (f" The limit includes {investment['personality_allowance']:.1f} from {investment['personality_reason']}." if investment and investment.get('personality_reason') else '')
            + personality_note(personality)
            + own_player_value_note(canonical, perspective_team_id, outgoing_assets)
            if include_presentation else ''
        ),
    )


def trade_legality(canonical: dict[str, Any], proposal: TradeProposal, config: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = multi_team_participation_issues(canonical, proposal)
    manual: list[str] = []
    from .pick_presentation import nested_entitlements
    bundled_ids = {oid for item in nested_entitlements(canonical).values() for oid in item["obligation_ids"]}
    for asset in trade_assets(proposal):
        if asset.get("kind") == "pick_swap" and asset.get("id") in bundled_ids:
            issues.append("A nested entitlement must be traded as one pick asset, not as a component swap right.")
    recent_players = recently_traded_player_ids(canonical, transaction_reference_date(canonical, proposal))
    recently_signed = recently_signed_player_ids(canonical, transaction_reference_date(canonical, proposal))
    for team_id, assets, _ in trade_team_flows(proposal):
        for asset in assets:
            if asset["kind"] == "player":
                player = player_by_id(canonical, asset["id"])
                from .release_planning import reacquisition_blocked
                receiving = next(t['to_team_id'] for t in trade_transfers(proposal) if asset in t['assets'])
                if reacquisition_blocked(canonical, receiving, asset['id'], transaction_reference_date(canonical, proposal)):
                    issues.append('A stretched player cannot return to his releasing team before the original contract ends.')
                if not player or player["team_id"] != team_id:
                    issues.append(f"{asset.get('label', asset.get('id'))} is not on {team_by_id(canonical, team_id)['abbrev']}.")
                elif goat_exception_player(player):
                    issues.append("LeBron James is a GOAT exception and cannot be traded.")
                if asset["id"] in recent_players:
                    issues.append(f"{asset.get('label', asset.get('id'))} was traded within the last {RECENTLY_TRADED_DAYS} days.")
                if asset["id"] in recently_signed:
                    issues.append(f"{asset.get('label', asset.get('id'))} signed recently and cannot be traded until Dec. 1.")
            elif asset["kind"] == "pick":
                pick = pick_by_id(canonical, asset["id"])
                if not pick or pick.get("current_owner_team_id") != team_id:
                    issues.append(f"Pick {asset.get('id')} is not owned by {team_by_id(canonical, team_id)['abbrev']}.")
                elif pick.get("status") == "forfeited":
                    issues.append(f"{pick_label(canonical, pick)} was forfeited and cannot be traded.")
                elif pick.get("_obligation_locked"):
                    issues.append(f"{pick_label(canonical, pick)} is locked as protection collateral and cannot be traded.")
            elif asset["kind"] == "pick_swap":
                swap = pick_swap_by_id(canonical, asset["id"])
                if (swap or {}).get("allocation_comparison"):
                    issues.append("A conditional allocation comparison cannot be traded separately from its pick.")
                holder = (swap or {}).get("current_rights_holder_team_id") or (swap or {}).get("original_rights_holder_team_id") or (swap or {}).get("receiver_team_id")
                grantor = (swap or {}).get("sender_team_id") or (swap or {}).get("counterparty_team_id")
                if not swap or (holder != team_id and not (swap.get("pending_asset_grant") and grantor == team_id)):
                    issues.append(f"Pick swap {asset.get('id')} is not held by {team_by_id(canonical, team_id)['abbrev']}.")
    issues.extend(re_trade_hold_issues(canonical, proposal))
    duplicate_assets = duplicate_trade_assets(trade_assets(proposal))
    if duplicate_assets:
        issues.append(f"Duplicate assets in proposal: {', '.join(sorted(duplicate_assets))}.")
    issues.extend(roster_count_issues(canonical, proposal, config))
    salary_legality = trade_salary_legality(canonical, proposal, config)
    issues.extend(salary_legality["issues"])
    manual.extend(salary_legality["manual_review"])
    issues.extend(stepien_guardrail_issues(canonical, proposal))
    if issues:
        status = "illegal"
    elif manual and config.get("decision", {}).get("manual_review_blocks_execution", True):
        status = "manual_review_required"
    else:
        status = "legal"
    return {"status": status, "issues": issues, "manual_review": manual}


def trade_salary_legality(canonical: dict[str, Any], proposal: TradeProposal, config: dict[str, Any]) -> dict[str, Any]:
    """Shared salary rules and the existing unresolved-salary execution policy."""
    manual = []
    issues = []
    for asset in trade_assets(proposal):
        if asset.get("kind") != "player":
            continue
        contract = contract_for_player(canonical, asset["id"])
        if contract_expired_without_rights(contract):
            issues.append(f"{asset.get('label', asset.get('id'))} has an expired contract and no retained rights, so he cannot be traded in this phase.")
        elif current_salary(contract) is None:
            manual.append(f"{asset.get('label', asset.get('id'))} has unresolved salary.")
    team_ids = {team["id"] for team in canonical.get("teams", [])}
    if set(trade_team_ids(proposal)) <= team_ids:
        salary_issue = salary_matching_issue(canonical, proposal, config)
        if salary_issue:
            issues.append(salary_issue)
    else:
        manual.append("Current team payroll context is unavailable.")
    if issues:
        status = "illegal"
    elif manual and config.get("decision", {}).get("manual_review_blocks_execution", True):
        status = "manual_review_required"
    else:
        status = "legal"
    return {"status": status, "issues": issues, "manual_review": manual}


def normalize_assets(canonical: dict[str, Any], team: dict[str, Any], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve asset specs to trade assets. Inside one trade search the same specs are resolved for every package
    (the target for every buyer, each buyer's players and picks), against the same unchanged league lists, so the
    result is kept per (league lists, team, specs). Each caller gets its own asset dicts."""
    memo = canonical.get('_trade_search_exact_memo')
    if memo is None:
        return _normalize_assets(canonical, team, assets)
    base = memo.get('base_sources')
    sources = (canonical.get('players'), canonical.get('draft_picks'), canonical.get('pick_obligations'),
               canonical.get('teams'))
    # Only the search's own league lists (the memo holds them alive); pick-term previews use their own copies.
    if base is None or not all(a is b for a, b in zip(base, sources)):
        return _normalize_assets(canonical, team, assets)
    try:
        key = (team['id'], json.dumps(assets, sort_keys=True))
    except (TypeError, ValueError):
        return _normalize_assets(canonical, team, assets)
    table = memo.setdefault('normalized_assets', {})
    cached = table.get(key)
    if cached is not None:
        return [dict(asset) for asset in cached]
    result = _normalize_assets(canonical, team, assets)
    if len(table) >= 4096:
        table.clear()
    table[key] = [dict(asset) for asset in result]
    return result


def _normalize_assets(canonical: dict[str, Any], team: dict[str, Any], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from .pick_presentation import pick_presentation, swap_presentation

    normalized = []
    for asset in assets:
        kind = asset.get("kind")
        value = asset.get("value") or asset.get("id")
        if kind == "player":
            player = resolve_player(canonical, str(value), team_id=team["id"])
            normalized.append(
                {
                    "kind": "player",
                    "id": player["id"],
                    "label": player["name"],
                    "minutes_projection": display_minutes_projection(player),
                }
            )
        elif kind == "pick":
            pick = pick_by_id(canonical, str(value))
            if not pick:
                raise ValueError(f"No pick found with id {value!r}")
            normalized.append(
                {
                    "kind": "pick",
                    "id": pick["id"],
                    "label": pick_label(canonical, pick),
                    "nested_entitlement": pick.get("_nested_entitlement"),
                    "pick_presentation": pick_presentation(canonical, pick),
                    "season": pick.get("season"),
                    "round": pick.get("round"),
                    "original_team_id": pick.get("original_team_id"),
                    "current_owner_team_id": pick.get("current_owner_team_id"),
                    "protection_summary": pick.get("protection_summary") or pick.get("protections"),
                }
            )
        elif kind == "pick_swap":
            swap = pick_swap_by_id(canonical, str(value))
            if not swap:
                raise ValueError(f"No pick swap found with id {value!r}")
            from .pick_presentation import nested_entitlements
            if any(swap["id"] in item["obligation_ids"] for item in nested_entitlements(canonical).values()):
                raise ValueError("This comparison belongs to a nested pick entitlement; trade the single pick asset instead.")
            normalized.append(
                {
                    "kind": "pick_swap",
                    "id": swap["id"],
                    "label": pick_swap_display_label(canonical, swap),
                    "pick_presentation": swap_presentation(canonical, swap),
                    "season": swap.get("season"),
                    "round": swap.get("round"),
                    "team_a_pick_id": swap.get("team_a_pick_id") or swap.get("primary_pick_id"),
                    "team_b_pick_id": swap.get("team_b_pick_id") or swap.get("counterparty_pick_id"),
                    "current_rights_holder_team_id": swap.get("current_rights_holder_team_id") or swap.get("original_rights_holder_team_id") or swap.get("receiver_team_id"),
                }
            )
        else:
            raise ValueError(f"Unknown trade asset kind {kind!r}")
    return normalized


def player_on_court_value(features: dict[str, float], portability: float) -> float:
    from .offense import valuation_adjustment
    value = (
        features.get("impact", 50) * 0.42
        + features.get("usage", 50) * 0.09
        + features.get("shot_creation", 50) * 0.08
        + features.get("spacing", 50) * 0.08
        + features.get("rim_pressure", 50) * 0.06
        + features.get("passing", 50) * 0.07
        + features.get("defensive_events", 50) * 0.07
        + features.get("rim_deterrence", 50) * 0.07
        + portability * 0.06
        - max(0.0, features.get("defensive_weak_link", 50) - 50.0) * 0.12
    )
    return clamp(value + valuation_adjustment(features), 1, 99)


def player_age_curve(age: float) -> float:
    if age <= 20:
        return 8.0
    if age <= 23:
        return 6.5
    if age <= 26:
        return 3.2
    if age <= 30:
        return 1.0
    if age <= 33:
        return -2.0
    if age <= 36:
        return -5.5
    return -8.5


def player_development_upside(player: dict[str, Any], age: float, features: dict[str, float]) -> float:
    minutes = float(player.get("minutes_projection") or 0)
    if age > 26:
        return 0.0
    upside = max(0.0, 24 - age) * 2.3 + max(0.0, 68 - features.get("impact", 50)) * 0.16
    if player.get("rotation_priority") == "development_priority":
        upside += 4.0
    if minutes >= 18 and age <= 23:
        upside += 2.0
    return clamp(upside, 0, 22)


def player_health_risk(profile: dict[str, Any], state: dict[str, Any]) -> float:
    durability = float(profile.get("durability") or 62)
    risk = max(0.0, 65 - durability) * 0.3
    if profile.get("injury_prone"):
        risk += 4.0
    risk += min(4.0, len(profile.get("major_prior_injuries") or []) * 1.4)
    risk += min(1.5, len(profile.get("body_area_risk_tags") or []) * 0.25)
    if state.get("availability_status") != "active":
        risk += 1.25
    risk += float(state.get("rust") or 0) * 0.035
    return clamp(risk, 0, 34)


def role_scarcity_score(player: dict[str, Any], features: dict[str, float], traits: dict[str, Any]) -> float:
    scarcity = 0.0
    if features.get("shot_creation", 50) >= 78 and features.get("usage", 50) >= 76:
        scarcity += 8.0
    if features.get("spacing", 50) >= 86:
        scarcity += 4.5
    if features.get("rim_deterrence", 50) >= 78:
        scarcity += 6.0
    if features.get("defensive_events", 50) >= 76 and features.get("spacing", 50) >= 64:
        scarcity += 5.5
    if features.get("passing", 50) >= 82:
        scarcity += 3.5
    if features.get("defensive_weak_link", 50) >= 62:
        scarcity -= 4.0
    return clamp(scarcity, -8, 20)


def contract_surplus_value(on_court: float, age_curve: float, development: float, salary: float | None, contract: dict[str, Any]) -> float:
    if salary is None:
        return -4.0
    salary_m = salary / 1_000_000
    expected_salary = max(2.0, (on_court - 44) * 1.65 + development * 0.55 + max(0.0, age_curve) * 0.65)
    surplus = expected_salary - salary_m
    if any((season.get("option_type") or "") == "team_option" for season in contract.get("seasons", [])):
        surplus += 2.0
    if salary_m <= 6 and development > 4:
        surplus += 4.0
    if salary_m >= 50.0 and age_curve < 0.0 and surplus > -2.0:
        surplus = min(surplus, -0.5 - (salary_m - 50.0) * 0.12 + age_curve * 0.35)
    if surplus < 0 and on_court >= 74:
        surplus = max(surplus * 0.18, -8.0)
    elif surplus < 0 and on_court >= 70:
        surplus = max(surplus * 0.28, -12.0)
    elif surplus < 0 and on_court >= 66:
        surplus = max(surplus * 0.42, -16.0)
    elif surplus < 0 and on_court >= 62:
        surplus *= 0.6
    if surplus < 0 and on_court >= 58 and development >= 5:
        surplus *= 0.78
    return clamp(surplus, -32, 34)


def current_salary(contract: dict[str, Any] | None) -> float | None:
    active_season = contract_active_season(contract)
    for season in (contract or {}).get("seasons", []):
        if season.get("season") == active_season and season.get("salary") is not None:
            return maybe_float(season.get("salary"))
    if projected_salary_fallback_allowed(contract):
        seasons = sorted(
            [season for season in (contract or {}).get("seasons", []) if season.get("salary") is not None and season.get("season")],
            key=lambda season: str(season.get("season")),
        )
        for season in seasons:
            if str(season.get("season")) >= active_season:
                return maybe_float(season.get("salary"))
    return None


def contract_active_season(contract: dict[str, Any] | None) -> str:
    return str((contract or {}).get("_active_season") or (contract or {}).get("active_season") or CANONICAL_SEASON)


def projected_salary_fallback_allowed(contract: dict[str, Any] | None) -> bool:
    if not contract:
        return False
    status = str(contract.get("status") or "")
    contract_type = str(contract.get("contract_type") or "")
    if status in {"save_state_contract_override", "signed_rookie_contract", "ai_offseason_signing", "auto_depth_signing"}:
        return True
    if "rookie_scale" in contract_type:
        return True
    return any(str(season.get("guarantee_status") or "") in {"ai_offseason_signing", "minimum_depth_signing"} for season in contract.get("seasons", []))


def contract_expired_without_rights(contract: dict[str, Any] | None) -> bool:
    if not contract:
        return True
    active = contract_active_season(contract)
    seasons = [str(season.get("season")) for season in contract.get("seasons", []) if season.get("season")]
    if any(season >= active for season in seasons):
        return False
    status = str(contract.get("status") or contract.get("rights_status") or contract.get("free_agency_type") or "").lower()
    return not any(marker in status for marker in ["rfa", "restricted", "rights", "qualifying_offer"])


def contention_ceiling(canonical: dict[str, Any], team: dict[str, Any], team_values: list[PlayerAssetValuation]) -> float:
    from .sim import team_feature_vector

    key = _contention_memo_key(canonical, team)
    if key is not None and key in _CONTENTION_MEMO and not _CONTENTION_AUDIT:
        return _CONTENTION_MEMO[key]
    view = strategic_rotation_view(canonical, team['id'])
    # The view carries the strength it was chosen by (non-spatial team features read only the team id).
    value = view.get('_strategic_contention')
    if value is None:
        value = contention_from_features(team_feature_vector(view, team, include_spatial=False).features)
    if key is not None:
        if _CONTENTION_AUDIT and key in _CONTENTION_MEMO and _CONTENTION_MEMO[key] != value:
            raise AssertionError(f"contention memo disagrees for {team['id']}: {_CONTENTION_MEMO[key]} != {value}")
        if len(_CONTENTION_MEMO) >= 4096:
            _CONTENTION_MEMO.pop(next(iter(_CONTENTION_MEMO)))
        _CONTENTION_MEMO[key] = value
    return value


# A team's healthy two-deep contention strength (strategic_rotation_view + non-spatial team features) depends only on
# its roster's player records, their trait values, the league meta it reads (model versions, offensive profiles) and
# the team record. Every transaction context rebuilt it for all 30 teams although most rosters had not changed. The memo is
# keyed by those inputs in full; it is only used with a forecast snapshot (whose views drop every other league key).
# These player fields are written for other readers and never read on this path: season stat lines (spatial and
# trade-value code), the coach note, injured-player trade-value minutes and the role prior (role reassessment).
# The forecast roster replaces minutes_projection with 24. NBA_GM_RUNTIME_AUDIT=1 recomputes every hit and compares.
_CONTENTION_MEMO: dict[bytes, float] = {}
_CONTENTION_AUDIT = __import__("os").environ.get("NBA_GM_RUNTIME_AUDIT") == "1"
_CONTENTION_IGNORED_FIELDS = frozenset({"_save_stats", "rotation_note", "_trade_value_unavailable",
                                        "_trade_value_minutes_projection", "_rotation_role_prior", "minutes_projection"})


def _contention_memo_key(canonical: dict[str, Any], team: dict[str, Any]) -> bytes | None:
    forecast = canonical.get('_roster_forecast_snapshot')
    if forecast is None or canonical.get('players') is not forecast.players_source:
        return None
    roster = [p for _, p in forecast.teams.get(team['id'], ()) if not p.get('_inactive_player')]
    full_meta = canonical.get('meta') or {}
    # League meta read on this path: the two model switches and this roster's offensive profiles (talent.enabled,
    # offense.enabled, offense.offensive_profile). The season labels are added only as a guard.
    profiles = full_meta.get('offensive_profiles') or {}
    meta = [full_meta.get(k) for k in ('talent_model_version', 'offense_model_version', 'season', 'active_season')]
    meta.append([(p['id'], profiles.get(p['id'])) for p in roster] if 'offensive_profiles' in full_meta else None)
    try:
        return pickle.dumps((
            "contention_v1", team,
            [{k: v for k, v in p.items() if k not in _CONTENTION_IGNORED_FIELDS} for p in roster],
            # The path reads only each trait row's value (sim features) and the derived float values.
            [[(k, row.get('value')) for k, row in (forecast.trait_rows.get(p['id']) or {}).items()] for p in roster],
            [list((forecast.trait_values.get(p['id']) or {}).items()) for p in roster],
            meta,
        ), protocol=pickle.HIGHEST_PROTOCOL)
    except (pickle.PicklingError, TypeError, AttributeError):
        return None


def contention_from_features(team_features: dict[str, float]) -> float:
    depth_bonus = min(12.0, float(team_features.get("depth", 0))) * 0.25
    ceiling = (
        team_features.get("impact", 50) * 0.62
        + team_features.get("star_power", 50) * 0.18
        + team_features.get("defense_total", 50) * 0.12
        + team_features.get("primary_creator", 50) * 0.06
        + depth_bonus
    )
    return clamp(ceiling, 1, 99)


def _rotation_strength(forecast: Any, view: dict[str, Any], team: dict[str, Any]) -> float:
    """contention_from_features(team_feature_vector(view, team, include_spatial=False)) for a forecast view.

    Hypothetical trades that leave a team's top rotation unchanged produce the same candidate rotations again
    (about half of all calls at the deadline). Within one forecast snapshot the non-spatial team features depend
    only on the rotation's player records (which carry their minutes), the team id and the league meta; the
    snapshot's own trait and feature tables are fixed. So the strength is kept per (team id, pickled player
    records) and league meta object. Equal pickles mean equal records."""
    from .sim import team_feature_vector
    memo = forecast.__dict__.setdefault('_rotation_strengths', {})
    try:
        key = (team['id'], pickle.dumps(view['players'], protocol=pickle.HIGHEST_PROTOCOL))
    except (pickle.PicklingError, TypeError, AttributeError):
        key = None
    meta = view.get('meta')
    entry = memo.get(key) if key is not None else None
    if entry is not None and entry[0] is meta:
        return entry[1]
    score = contention_from_features(team_feature_vector(view, team, include_spatial=False).features)
    if key is not None:
        if len(memo) >= 20_000:
            memo.clear()
        memo[key] = (meta, score)  # the entry keeps the meta object alive, so the identity check stays sound
    return score


def strategic_rotation_view(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    """Forecast a healthy two-deep roster, not minutes carried from old teams."""
    from .save import ai_role_targets, bounded_minutes_allocation, player_attribute_summary, round_minutes_to_total
    from .sim import team_feature_vector
    from .roster_forecast import ForecastSnapshot
    forecast = canonical.get('_roster_forecast_snapshot') or ForecastSnapshot(canonical)
    if canonical.get('players') is forecast.players_source:
        roster = forecast.roster(team_id)
    else:
        # A previous cut or hypothetical transfer has changed membership.
        roster = [dict(copy_plain(p), minutes_projection=24) for p in canonical.get("players", [])
                  if p.get('team_id') == team_id and not p.get('_inactive_player')]
    trial = forecast.view(canonical, roster)
    if not roster:
        return trial
    targets, selected = ai_role_targets(trial, roster, {})
    backups = sorted(selected[5:], key=lambda pid: (-player_attribute_summary(trial, pid)['overall'], pid))
    order = selected[:5]+backups
    team = team_by_id(canonical, team_id) or {'id': team_id}
    candidates = []
    # A coach may use a tighter rotation; signing a weak reserve does not
    # obligate a competitive roster to dilute its strongest minutes.
    for count in sorted({min(len(order), n) for n in (8, 9, 10)}):
        ids = set(order[:count])
        allocation = bounded_minutes_allocation([
            {'player_id': p['id'], 'desired': targets[p['id']], 'minimum': 0,
             'maximum': 48 if len(ids) <= 5 else 42} for p in roster if p['id'] in ids], 240)
        allocation = round_minutes_to_total(allocation, 240)
        # Nested inputs were isolated when this roster was created. Candidate
        # rotations change only scalars on their own player dictionaries.
        view = forecast.view(trial, [dict(p, minutes_projection=allocation[p['id']])
                                    for p in roster if p['id'] in ids])
        score = _rotation_strength(forecast, view, team)
        candidates.append((score, count, view))
    score, _, chosen = max(candidates, key=lambda row: (row[0], row[1]))
    # Its contention strength, for callers that score this exact view again (trade_roster.roster_projection).
    # forecast.view() drops private keys, so a re-built view never carries it.
    chosen['_strategic_contention'] = score
    return chosen


def youth_pipeline_score(players: list[dict[str, Any]], team_values: list[PlayerAssetValuation]) -> float:
    values = {value.player_id: value for value in team_values}
    young = [player for player in players if (maybe_float(player.get("age")) or 99) <= 24]
    return clamp(sum(values.get(player["id"], empty_value()).development_upside + values.get(player["id"], empty_value()).player_value * 0.12 for player in young), 0, 99)


def team_pick_inventory(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    picks = tradeable_picks_for_team(canonical, team_id)
    firsts = [pick for pick in picks if int(pick.get("round") or 0) == 1]
    seconds = [pick for pick in picks if int(pick.get("round") or 0) == 2]
    meta = canonical.get('meta') or {}
    current = parse_iso_date(meta.get('current_date'))
    start = season_start_from_label(str(meta.get('active_season') or meta.get('season') or CANONICAL_SEASON))
    next_draft = current.year if current and current.month <= 6 else current.year+1 if current else start+1
    return {
        "first_round_count": len(firsts),
        "second_round_count": len(seconds),
        "near_term_firsts": sum(1 for pick in firsts if str(pick.get("season")) in {str(next_draft+i) for i in range(3)}),
        "pick_value": round(sum(pick_asset_value(pick, "neutral") for pick in picks), 2),
    }


def team_health_risk(canonical: dict[str, Any], top_values: list[PlayerAssetValuation]) -> float:
    if not top_values:
        return 0.0
    return sum(value.health_risk for value in top_values) / len(top_values)


def salary_posture(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    from .contract_protection import waived_total
    season = str(canonical.get('meta', {}).get('active_season') or CANONICAL_SEASON)
    total = waived_total(canonical, team_id, season)
    unresolved = 0
    roster_ids = {p['id'] for p in canonical.get('players', []) if p.get('team_id') == team_id}
    for contract in canonical.get("contracts", []):
        if contract.get('player_id') not in roster_ids:
            continue
        salary = current_salary(contract)
        if salary is None:
            unresolved += 1
        else:
            total += salary
    if total >= 190_000_000:
        posture = "expensive_tax_team"
    elif total >= 165_000_000:
        posture = "above_cap_or_tax_watch"
    elif total >= 120_000_000:
        posture = "middle_salary"
    else:
        posture = "flexible_or_incomplete"
    if unresolved:
        posture += "_with_unresolved_contracts"
    return {"posture": posture, "salary_total": total, "unresolved_contract_count": unresolved}


def classify_team_phase(profile: dict[str, Any], ceiling: float, core_age: float | None, youth: float, pick_inventory: dict[str, Any], config: dict[str, Any]) -> str:
    """Classify the live roster; the research profile is not a standing order."""
    thresholds = config.get("phase_thresholds", {})
    if ceiling < float(thresholds.get("contender_ceiling", 69)) and youth >= 75 and (core_age or 30) <= 24.5:
        return "developing"
    if ceiling >= float(thresholds.get("contender_ceiling", 69)):
        return "contending_with_future_upside" if youth >= 45 and (core_age or 30) < 29 else "contending"
    if ceiling >= float(thresholds.get("playoff_ceiling", 60)):
        return "retooling" if (core_age or 28) >= 29.5 else "developing"
    if youth >= 42 or pick_inventory.get("near_term_firsts", 0) >= 3:
        return "developing"
    return "rebuilding"


def team_needs_and_excesses(canonical: dict[str, Any], team: dict[str, Any], players: list[dict[str, Any]], phase: str, *, _full_features: bool = False) -> tuple[list[str], list[str]]:
    from .sim import team_feature_vector

    # Every threshold below uses non-spatial features. The existing lean path
    # preserves player minutes, lineup weights and all summation/rounding order.
    features = team_feature_vector(canonical, team, include_spatial=_full_features).features
    needs = []
    excesses = []
    thresholds = {
        "primary_creator": "primary_creation",
        "spacing": "shooting",
        "rim_pressure": "rim_pressure",
        "rim_deterrence": "rim_protection",
        "defensive_events": "point_of_attack_defense",
        "passing": "passing",
        "offensive_rebounding": "rebounding",
    }
    for feature, label in thresholds.items():
        if features.get(feature, 50) < 56:
            needs.append(label)
        if features.get(feature, 50) > 68:
            excesses.append(f"{label}_depth")
    counts = position_counts(players)
    if counts["guard"] < 4:
        needs.append("guard_depth")
    if counts["wing"] < 4:
        needs.append("wing_depth")
    if counts["big"] < 3:
        needs.append("big_depth")
    if counts["guard"] > 6:
        excesses.append("guard_depth")
    if counts["wing"] > 6:
        excesses.append("wing_depth")
    if counts["big"] > 5:
        excesses.append("big_depth")
    if phase in {"rebuilding", "developing"}:
        needs.append("youth_and_picks")
    if phase in {"contending", "contending_with_future_upside"}:
        needs.append("playoff_rotation")
    return sorted(dict.fromkeys(needs)), sorted(dict.fromkeys(excesses))


def strategic_pressure(profile: dict[str, Any], front_office: dict[str, Any], phase: str, core_age: float | None) -> float:
    pressure = float(front_office.get("owner_pressure") or 55)
    if str(profile.get("front_office_pressure") or "").lower() == "high":
        pressure += 8
    if phase == "contending" and core_age and core_age >= 30:
        pressure += 8
    if phase == "rebuilding":
        pressure -= 6
    return clamp(pressure, 1, 99)


def trade_block_score(canonical: dict[str, Any], player: dict[str, Any], valuation: PlayerAssetValuation, state: TeamStrategicState) -> tuple[float, list[str], list[str]]:
    age = maybe_float(player.get("age")) or 27
    reasons: list[str] = []
    preferred: list[str] = []
    score = 12.0
    if state.phase in {"rebuilding", "developing"} and age >= 29 and valuation.player_value >= 24:
        score += 42
        reasons.append("older_than_team_timeline")
        preferred.extend(["picks", "young_players", "salary_flexibility"])
    if state.phase in {"contending", "contending_with_future_upside"} and valuation.player_value < 36 and valuation.contract_surplus < -4:
        score += 30
        reasons.append("upgradeable_expensive_rotation_slot")
        preferred.extend(["playoff_rotation", "two_way_fit"])
    if valuation.contract_surplus < -12:
        score += 22
        reasons.append("negative_contract_value")
        preferred.append("salary_flexibility")
    if player_position_bucket(player) in " ".join(state.excesses):
        score += 12
        reasons.append("position_surplus")
        if age >= 35:
            score += 6
            reasons.append("veteran_surplus_slot")
    if valuation.health_risk >= 12 and state.phase in {"contending", "contending_with_future_upside"}:
        score += 9
        reasons.append("health_risk_for_win_now_team")
    if age <= 24 and valuation.development_upside >= 8 and float(player.get("minutes_projection") or 0) < 12:
        score += 8
        reasons.append("blocked_prospect")
        preferred.append("clearer_development_path")
    if valuation.player_value >= 72 and state.phase not in {"rebuilding"}:
        score -= 18 if "older_than_team_timeline" in reasons else 62
    if valuation.contract_surplus >= 10 and age <= 25:
        score -= 22
    if state.phase in {"contending", "contending_with_future_upside"} and valuation.on_court_value >= 60 and float(player.get("minutes_projection") or 0) >= 26:
        score -= 35
    if not reasons:
        reasons.append("soft_market_listening")
        preferred.append("value_positive_return")
    from .team_planning import core_commitment
    if core_commitment(canonical, state.team_id, player['id']):
        score -= 75
        reasons.append('committed_core_trial')
    plan = canonical.get('team_plans', {}).get(state.team_id, {})
    if state.team_id not in canonical.get('_human_team_ids', []) and plan.get('retool_candidate_id') == player['id']:
        score = max(score, 62)
        reasons.append('planned_core_retool_not_full_teardown')
        preferred = ['younger_core_fit', 'premium_assets', 'future_flexibility']
    return score, sorted(dict.fromkeys(reasons)), sorted(dict.fromkeys(preferred or ["best_offer"]))


def block_willingness(score: float) -> str:
    if score >= 75:
        return "actively_shopping"
    if score >= 55:
        return "available_for_right_price"
    return "listening_only"


def team_fit_for_player(
    player: dict[str, Any],
    valuation: dict[str, Any],
    state: dict[str, Any],
    canonical: dict[str, Any] | None = None,
    include_spatial: bool = True,
) -> float:
    if not player:
        return 0.0
    fit = 0.0
    age = maybe_float(player.get("age")) or 30
    minutes = maybe_float(player.get("minutes_projection")) or 0.0
    player_value = float(valuation.get("player_value") or 0.0)
    playoff_value = float(valuation.get("playoff_value") or 0.0)
    portability = float(valuation.get("portability") or 0.0)
    development = float(valuation.get("development_upside") or 0.0)
    health_risk = float(valuation.get("health_risk") or 0.0)
    if "playoff_rotation" in state.get("needs", []) and valuation["playoff_value"] >= 62:
        fit += 4
    if "youth_and_picks" in state.get("needs", []) and age <= 24:
        fit += 5
    if "shooting" in state.get("needs", []) and valuation["portability"] >= 64:
        fit += 2
    if state.get("phase") in {"contending", "contending_with_future_upside"} and player_value >= 45:
        fit += 3
    if state.get("phase") in {"contending", "contending_with_future_upside"} and age >= 30 and minutes >= 22 and playoff_value >= 58:
        fit += 2.5
    if state.get("phase") in {"contending", "contending_with_future_upside"} and health_risk >= 16.0:
        fit -= min(5.0, (health_risk - 14.0) * 0.5)
    if state.get("phase") in {"rebuilding", "developing"} and age >= 30:
        fit -= 4
    if state.get("phase") == "rebuilding" and player_value >= 48 and minutes >= 24 and age >= 28:
        fit -= 2
    large_asset = player_value >= 64 or playoff_value >= 68 or development >= 12
    if large_asset:
        needs_text = " ".join(str(item) for item in state.get("needs", []))
        excess_text = " ".join(str(item) for item in state.get("excesses", []))
        if state.get("phase") in {"contending", "contending_with_future_upside"} and playoff_value >= 68:
            fit += 4.5
        if state.get("phase") in {"rebuilding", "developing"} and age <= 24 and development >= 8:
            fit += 5.0
        if state.get("phase") in {"rebuilding", "developing"} and age >= 30 and player_value >= 58:
            fit -= 6.0
        if "shooting" in needs_text and portability >= 70:
            fit += 3.0
        if "primary_creation" in needs_text and player_value >= 68:
            fit += 3.0
        bucket = player_position_bucket(player)
        if f"{bucket}_depth" in needs_text:
            fit += 2.6
        if f"{bucket}_depth" in excess_text and player_value < 72:
            fit -= 3.2
    if include_spatial and canonical and state.get("team_id"):
        fit += spatial_fit_delta(canonical, str(state["team_id"]), player, cap=3.0)
    return round(fit, 3)


def package_value_for_team(
    canonical: dict[str, Any],
    assets: list[dict[str, Any]],
    perspective_team_id: str,
    outgoing_assets: list[dict[str, Any]] | None = None,
) -> float:
    total, concentration = package_value_components(canonical, assets, perspective_team_id, outgoing_assets)
    return total + concentration


def package_value_components(
    canonical: dict[str, Any],
    assets: list[dict[str, Any]],
    perspective_team_id: str,
    outgoing_assets: list[dict[str, Any]] | None = None,
) -> tuple[float, float]:
    values = player_asset_values_by_id(canonical)
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == perspective_team_id)
    multipliers = destination_role_multipliers(canonical, assets, perspective_team_id, outgoing_assets or [])
    own_ids = own_ai_player_ids(canonical, assets, perspective_team_id)
    own_state = own_departure_state(canonical, perspective_team_id, state, own_ids) if own_ids else state
    human_view = perspective_team_id in set(canonical.get('_human_team_ids') or [])
    total = 0.0
    player_adjusted_values: list[float] = []
    for asset in assets:
        if asset["kind"] == "player":
            player = player_by_id(canonical, asset["id"])
            value = valuation_or_fallback(values, asset["id"], player)
            multiplier = multipliers.get(asset["id"], 1.0)
            player_value = _search_market_value(canonical, player, value)
            own = asset["id"] in own_ids
            adjusted = (player_value + team_fit_for_player(player, value, own_state if own else state, canonical, include_spatial=False)) * multiplier
            if adjusted > 0 and not human_view:
                adjusted *= veteran_present_factor(state, player)
            adjusted -= max(0.0, float(value.get("health_risk") or 0.0) - 12.0) * 0.25
            if own:
                adjusted += own_player_premium(canonical, player, perspective_team_id, adjusted, market_value=player_value)["total"]
            else:
                adjusted += recently_acquired_player_premium(canonical, player, perspective_team_id, player_value)
            player_adjusted_values.append(adjusted)
            total += adjusted
        elif asset["kind"] == "pick":
            pick = pick_by_id(canonical, asset["id"])
            total += pick_asset_value(pick, state["phase"])
        elif asset["kind"] == "pick_swap":
            total += pick_swap_asset_value(canonical, pick_swap_by_id(canonical, asset["id"]) or asset, state["phase"])
    # Spatial complement helps the AI choose destinations and separate comparable
    # targets. The final bilateral asset ledger stays value-based so opposing fit
    # preferences cannot manufacture an acceptance swing after package assembly.
    return total, package_concentration_adjustment(player_adjusted_values)


def own_ai_player_ids(canonical: dict[str, Any], assets: list[dict[str, Any]], team_id: str | None) -> set[str]:
    """Players in ``assets`` that an AI team already owns: valued as what it loses (trade step 1)."""
    if not team_id or team_id in set(canonical.get('_human_team_ids') or []):
        return set()
    return {asset['id'] for asset in assets if asset.get('kind') == 'player'
            and (player_by_id(canonical, asset.get('id')) or {}).get('team_id') == team_id}


# A team far from contending values a veteran's current production less (trade 2b). Every team prices a player by
# the minutes he plays for it now, so a rebuilding team valued its 31-year-old starter above what a deeper contender
# would pay, and the most common real trade (a rebuilder selling a veteran to a contender) rarely cleared. The
# discount scales with the team's distance from contending (team_planning: 0 within a point of the 4th-best team, 1
# at six points or more below it; contenders are 0) and with how old the player will be when the team expects to be
# good again: about 3 years away for a deep rebuild, so a 29-year-old counts as a 32-year-old. It ramps in from 29 to
# 33 at that future age. Full size: 30%, so a deep rebuilder values a 29-year-old at about x0.78 and a 30-year-old at
# x0.70 (the step-2 suggestion was about x0.75 at 29+). Grounding: the game's own aging (team_planning counts about
# 0.65 points of decline a year after 29), the real 2025-27 rebuild sales (data/research/real_trades: Dosunmu,
# Vucevic, Conley, Simons, Middleton, Kawhi, LaMelo, Giannis all went from teams resetting to teams competing, for
# younger players and picks rather than equal current production) and the real rebuilders' veteran buys, which were
# expiring salary paid for with picks. Applied to both sides (selling and buying), never to the human team.
VETERAN_DISCOUNT_MAX = 0.30
VETERAN_WINDOW_YEARS = 3.0
VETERAN_AGE_START = 29.0
VETERAN_AGE_FULL = 33.0


def veteran_present_factor(state: dict[str, Any], player: dict[str, Any] | None) -> float:
    distance = float(state.get('contend_distance') or 0.0)
    if not player or distance <= 0.0:
        return 1.0
    age = maybe_float(player.get('display_age', player.get('age'))) or 27.0
    future_age = age + VETERAN_WINDOW_YEARS * distance
    ramp = clamp((future_age - VETERAN_AGE_START) / (VETERAN_AGE_FULL - VETERAN_AGE_START), 0.0, 1.0)
    return round(1.0 - VETERAN_DISCOUNT_MAX * distance * ramp, 4)


_DEPTH_LIMITS = (('guard', 4, 6), ('wing', 4, 6), ('big', 3, 5))


def own_departure_state(canonical: dict[str, Any], team_id: str, state: dict[str, Any], departing_ids: set[str]) -> dict[str, Any]:
    """The team's position needs after its departing players leave.

    The roster's needs and surpluses are counted with the player still on it, so a team's own guard can read as
    "guard surplus" because he is the seventh guard, and losing its fourth guard never shows the hole it leaves.
    For its own departing players the team asks what the roster looks like without them (position depth only; the
    skill needs stay as computed). The same thresholds as team_needs_and_excesses.
    """
    memo = canonical.get('_own_departure_states')
    key = (team_id, tuple(sorted(departing_ids)))
    if memo is not None and key in memo and memo[key][0] is state:
        return memo[key][1]
    rows = _search_team_rows(canonical, team_id)
    roster = [p for p in (canonical.get('players', []) if rows is None else rows) if p.get('team_id') == team_id]
    before = position_counts(roster)
    after = position_counts([p for p in roster if p.get('id') not in departing_ids])
    needs, excesses = list(state.get('needs') or []), list(state.get('excesses') or [])
    for bucket, low, high in _DEPTH_LIMITS:
        flag = f'{bucket}_depth'
        if before[bucket] > high >= after[bucket] and flag in excesses:
            excesses.remove(flag)
        if before[bucket] >= low > after[bucket] and flag not in needs:
            needs.append(flag)
    result = {**state, 'needs': sorted(needs), 'excesses': sorted(excesses)}
    if memo is not None:
        memo[key] = (state, result)
    return result


def own_player_premium(canonical: dict[str, Any], player: dict[str, Any] | None, team_id: str, base_value: float, *,
                       market_value: float | None = None) -> dict[str, Any]:
    from .trade_ownership import own_player_premium as premium
    return premium(canonical, player, team_id, base_value, market_value=market_value)


def own_player_value_note(canonical: dict[str, Any], team_id: str, outgoing_assets: list[dict[str, Any]]) -> str:
    """Plain-language explanation of an AI team's price for its own outgoing players."""
    own_ids = own_ai_player_ids(canonical, outgoing_assets, team_id)
    if not own_ids:
        return ''
    from .trade_ownership import premium_note
    breakdown = package_value_breakdown(canonical, [a for a in outgoing_assets if a.get('id') in own_ids], team_id)
    parts = []
    for row in breakdown.get('asset_details') or []:
        view = row.get('own_player_view') or {}
        components = row.get('components') or {}
        premium = {name: float(components.get(name) or 0.0) for name in ('attachment', 'tenure', 'investment')}
        premium['detail'] = view
        reasons = premium_note(premium)
        parts.append(f"{row.get('label')} valued {float(row.get('adjusted_value') or 0):.1f} in his "
                     f"{float(view.get('role_minutes') or 0):.0f}-minute role" + (f" ({reasons})" if reasons else ''))
    return ' Own-player price: ' + '; '.join(parts) + '.'


def recently_acquired_player_premium(canonical: dict[str, Any], player: dict[str, Any] | None, team_id: str, base_value: float) -> float:
    if not player or player.get("team_id") != team_id:
        return 0.0
    if base_value < 42.0 and float(player.get("minutes_projection") or 0.0) < 22.0:
        return 0.0
    current = parse_iso_date(((canonical.get("meta") or {}).get("current_date")) or CANONICAL_START_DATE)
    if current is None:
        return 0.0
    player_id = player.get("id")
    for log in sorted(canonical.get("transaction_logs", []), key=lambda item: str(item.get("date") or ""), reverse=True):
        if log.get("transaction_type") != "trade":
            continue
        log_date = parse_iso_date(log.get("date"))
        if log_date is None:
            continue
        days = (current - log_date).days
        if days < RECENTLY_TRADED_DAYS or days > RECENTLY_ACQUIRED_PREMIUM_DAYS:
            continue
        incoming = next((incoming for tid, _, incoming in transaction_log_flows(log) if tid == team_id), [])
        if not any(a.get('kind') == 'player' and a.get('id') == player_id for a in incoming):
            continue
        decay = 1.0 - (days - RECENTLY_TRADED_DAYS) / max(1, RECENTLY_ACQUIRED_PREMIUM_DAYS - RECENTLY_TRADED_DAYS)
        quality = clamp((base_value - 40.0) / 42.0, 0.0, 1.0)
        minutes = clamp((float(player.get("minutes_projection") or 0.0) - 18.0) / 16.0, 0.0, 1.0)
        return round((5.0 + 11.0 * max(quality, minutes)) * decay, 2)
    return 0.0


def package_concentration_adjustment(player_values: list[float]) -> float:
    if len(player_values) <= 1:
        return 0.0
    values = sorted([max(0.0, value) for value in player_values], reverse=True)
    top = values[0]
    low_role_count = sum(1 for value in values[1:] if value < 26.0)
    redundancy_penalty = low_role_count * 4.8
    if top >= 58.0:
        redundancy_penalty += max(0, len(values) - 2) * 2.4
    if top < 42.0 and len(values) >= 3:
        redundancy_penalty += 7.0
    concentration_bonus = 3.0 if top >= 70.0 else 1.5 if top >= 60.0 else 0.0
    return concentration_bonus - redundancy_penalty


def destination_role_multipliers(
    canonical: dict[str, Any],
    incoming_assets: list[dict[str, Any]],
    perspective_team_id: str | None,
    outgoing_assets: list[dict[str, Any]] | None = None,
) -> dict[str, float]:
    if not perspective_team_id:
        return {}
    cache = canonical.get('_trade_search_roles')
    cache_key = (perspective_team_id,
                 tuple(sorted((a.get('id') for a in incoming_assets if a.get('kind') == 'player'), key=str)),
                 tuple(sorted({a.get('id') for a in outgoing_assets or [] if a.get('kind') == 'player'}, key=str)))
    if cache is not None and cache_key in cache:
        return dict(cache[cache_key])
    values = player_asset_values_by_id(canonical)
    outgoing_ids = {asset.get("id") for asset in outgoing_assets or [] if asset.get("kind") == "player"}
    incoming_players = [
        player_by_id(canonical, asset.get("id"))
        for asset in incoming_assets
        if asset.get("kind") == "player"
    ]
    incoming_players = [player for player in incoming_players if player]
    if not incoming_players:
        return {}
    incoming_ids = {player['id'] for player in incoming_players}
    moving_ids = outgoing_ids | incoming_ids
    roster_values = []
    team_rows = _search_team_rows(canonical, perspective_team_id)
    for player in (canonical.get("players", []) if team_rows is None else team_rows):
        if player.get("team_id") != perspective_team_id or player.get("id") in moving_ids:
            continue
        valuation = valuation_or_fallback(values, player["id"], player)
        quality = valuation.get('on_court_value')
        roster_values.append((player["id"], float(quality if quality is not None else valuation.get("player_value") or 0.0)))
    incoming_values = []
    for player in incoming_players:
        valuation = valuation_or_fallback(values, player["id"], player)
        # Salary bargains and future potential affect price, not who can play
        # the strongest current minutes. Owned package members appear once.
        quality = valuation.get('on_court_value')
        incoming_values.append((player["id"], float(quality if quality is not None else valuation.get("player_value") or 0.0), display_minutes_projection(player)))
    all_values = roster_values + [(pid, value) for pid, value, _ in incoming_values]
    # Own-player correction (trade step 1): when an AI team prices a player it already has, it knows the role he
    # actually plays. Ranking him only by on-court value against his own teammates can call a 33-minute starter a
    # fringe player and make him look like surplus; the team's loss is at least the role he really fills.
    own_roles = {} if perspective_team_id in set(canonical.get('_human_team_ids') or []) else {
        player['id']: trade_value_role_minutes(player, valuation_or_fallback(values, player['id'], player))
        for player in incoming_players if player.get('team_id') == perspective_team_id}
    output: dict[str, float] = {}
    for player_id, value, current_minutes in incoming_values:
        rank = 1 + sum(1 for other_id, other_value in all_values if other_id != player_id and other_value > value)
        role_minutes = expected_minutes_for_destination_rank(rank)
        expected_minutes = min(36.0, max(role_minutes, min(float(current_minutes or 0.0), role_minutes + 3.0)))
        if player_id in own_roles:
            expected_minutes = min(36.0, max(expected_minutes, own_roles[player_id]))
        minute_weight = (max(2.0, expected_minutes) / 28.0) ** 1.8
        output[player_id] = round(clamp(minute_weight, 0.12, 1.22), 3)
    if cache is not None:
        if len(cache) >= 4096:
            cache.clear()
        cache[cache_key] = dict(output)
    return output


def expected_minutes_for_destination_rank(rank: int) -> float:
    if rank <= 1:
        return 35.0
    if rank <= 2:
        return 32.0
    if rank <= 3:
        return 29.0
    if rank <= 5:
        return 25.0
    if rank <= 7:
        return 17.0
    if rank <= 9:
        return 8.0
    if rank <= 12:
        return 3.5
    return 2.5


def display_minutes_projection(player: dict[str, Any] | None) -> float:
    if not player:
        return 0.0
    for key in ["minutes_projection", "projected_minutes", "mpg", "minutes_per_game"]:
        value = maybe_float(player.get(key))
        if value is not None:
            return round(clamp(value, 0.0, 42.0), 1)
    rotation = str(player.get("rotation_priority") or "")
    return {
        "core_rotation": 28.0,
        "rotation": 18.0,
        "development_priority": 12.0,
    }.get(rotation, 8.0)


def trade_value_role_minutes(player: dict[str, Any] | None, valuation: dict[str, Any] | None = None) -> float:
    if not player:
        return 0.0
    current_minutes = display_minutes_projection(player)
    if current_minutes >= 2.0 or not player.get("_trade_value_unavailable"):
        return current_minutes
    baseline = maybe_float(player.get("_trade_value_minutes_projection"))
    if baseline is None:
        return current_minutes
    valuation = valuation or {}
    long_term_quality = max(
        float(valuation.get("player_value") or 0.0),
        float(valuation.get("on_court_value") or 0.0),
        float(valuation.get("playoff_value") or 0.0),
    )
    rotation = str(player.get("rotation_priority") or "")
    if long_term_quality < 42.0 and rotation not in {"core_rotation", "rotation", "development_priority"}:
        return current_minutes
    return round(clamp(baseline, current_minutes, 42.0), 1)


def strategic_fit_adjustment(canonical: dict[str, Any], incoming: list[dict[str, Any]], outgoing: list[dict[str, Any]], team_id: str, config: dict[str, Any]) -> float:
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team_id)
    adjustment = 0.0
    # Rebuilding and developing teams prize draft capital. The extra is a share of the pick's own value (trade step
    # 2; it was a flat +7 for any pick, so a 2034 second counted as much as a lottery first) and it applies both
    # ways: a rebuilder sending a pick gives up the same extra it would get for receiving it.
    draft_phase = state["phase"] in {"rebuilding", "developing"}
    for sign, assets in ((1.0, incoming), (-1.0, outgoing)):
        for asset in assets:
            if draft_phase and asset["kind"] in {"pick", "pick_swap"}:
                adjustment += sign * rebuilder_draft_bonus(canonical, asset, state.get("phase", "balanced"), config)
    for asset in incoming:
        if asset["kind"] == "player":
            valuation = next(item for item in canonical["player_asset_valuations"] if item["player_id"] == asset["id"])
            if state["phase"] in {"contending", "contending_with_future_upside"} and valuation["playoff_value"] >= 64:
                adjustment += float(config.get("decision", {}).get("contender_need_bonus", 5.5))
    own_view = team_id not in set(canonical.get('_human_team_ids') or [])
    for asset in outgoing:
        if asset["kind"] == "pick" and state["phase"] in {"contending", "contending_with_future_upside"}:
            adjustment -= 1.5
        if asset["kind"] == "player" and own_view and state["phase"] in {"contending", "contending_with_future_upside"}:
            # Own-player correction (trade step 1): a contender values an incoming playoff-level player extra, so
            # losing one of its own costs the same; before, only the incoming side counted and every contender
            # swap of playoff players looked like a gain for both teams.
            valuation = next((item for item in canonical["player_asset_valuations"] if item["player_id"] == asset["id"]), None)
            if valuation and valuation["playoff_value"] >= 64:
                adjustment -= float(config.get("decision", {}).get("contender_need_bonus", 5.5))
        if asset["kind"] == "pick_swap" and state["phase"] in {"contending", "contending_with_future_upside"}:
            swap_value = pick_swap_asset_value(canonical, pick_swap_by_id(canonical, asset.get("id")) or asset, state.get("phase", "balanced"))
            adjustment += -0.6 if swap_value >= 0 else 0.35
    return adjustment


REBUILDER_PICK_BONUS_RATE = 0.14


def rebuilder_draft_bonus(canonical: dict[str, Any], asset: dict[str, Any], phase: str, config: dict[str, Any]) -> float:
    """A rebuilding or developing team's extra value for a pick (or pick swap): a share of the pick's own value.

    The rate (14%) keeps a typical future first-round pick near the old flat +7 (a rebuilder values one at about
    50), while a far-future second (about 8) now adds about 1 instead of 7. A swap that favours the other side has a
    negative value, so it costs instead of adds.
    """
    rate = float(config.get("decision", {}).get("rebuilder_pick_bonus_rate", REBUILDER_PICK_BONUS_RATE))
    if asset.get("kind") == "pick_swap":
        value = pick_swap_asset_value(canonical, pick_swap_by_id(canonical, asset.get("id")) or asset, phase)
    else:
        value = pick_asset_value(pick_by_id(canonical, asset.get("id")), phase)
    return round(rate * value, 3)


def personality_trade_adjustment(canonical: dict[str, Any], team_id: str, proposal_id: str, seed: int, *,
                                 incoming: list[dict[str, Any]] | None = None,
                                 outgoing: list[dict[str, Any]] | None = None, tax_term: float = 0.0,
                                 proposal: Any = None) -> dict[str, Any]:
    """The front office's personality on top of the textbook value (TRADE-MARKET, front_office.py).

    Bounded, explained terms from lasting traits (urgency, savvy and its biases, preferences, player opinions,
    loyalty) and from a live negotiation (concessions as patience runs out). No random draw: until TRADE-MARKET this
    was a per-proposal dice roll (up to about +-2.5) plus constant trait offsets; ``proposal_id`` and ``seed`` are
    kept for the callers' signature only."""
    from .front_office import personality_terms
    return personality_terms(canonical, team_id, list(incoming or []), list(outgoing or []), tax_term=tax_term,
                             proposal=proposal)


def personality_note(personality: dict[str, Any]) -> str:
    """The personality terms in the evaluation notes, in plain words with their size."""
    terms = [f"{term['text']} ({float(term['points']):+.1f})" for term in (personality or {}).get('terms') or []]
    return f" Personality: {'; '.join(terms)}." if terms else ''


def acceptance_threshold(canonical: dict[str, Any], team_id: str, config: dict[str, Any]) -> float:
    """Every front office's acceptance margin: the same for all (TRADE-FOLLOWUPS).

    It used to move about +-2 points with the old hidden front-office profile (asset discipline, competence, owner
    pressure: unsourced flavour values the user never saw). How a front office differs is now only in its visible
    traits (front_office.py: savvy, urgency, patience, loyalty and its habits), each stated in the trade's reasons
    (rule 4)."""
    del canonical, team_id
    return round(float(config.get("decision", {}).get("base_acceptance_threshold", 1.5)), 3)


def contextual_acceptance_threshold(
    canonical: dict[str, Any],
    team_id: str,
    config: dict[str, Any],
    incoming_assets: list[dict[str, Any]],
    outgoing_assets: list[dict[str, Any]],
) -> float:
    threshold = acceptance_threshold(canonical, team_id, config)
    values = player_asset_values_by_id(canonical)

    def max_player_value(assets: list[dict[str, Any]]) -> float:
        best = 0.0
        for asset in assets:
            if asset.get("kind") != "player":
                continue
            player = player_by_id(canonical, asset.get("id"))
            if not player:
                continue
            value = valuation_or_fallback(values, player["id"], player)
            best = max(best, float(value.get("player_value") or 0.0))
        return best

    incoming_star = max_player_value(incoming_assets)
    outgoing_star = max_player_value(outgoing_assets)
    if incoming_star >= 78.0 and incoming_star >= outgoing_star + 8.0:
        state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == team_id), {})
        discount = 0.55
        # TRADE-FOLLOWUPS: the eagerness for a star comes from the visible win-now urgency (front_office.py), not the
        # old hidden owner-pressure and star-chasing fields (a star-chasing habit is its own stated personality term).
        from .front_office import office
        row = office(canonical, team_id)
        if row:
            discount += max(0.0, float(row["urgency"]) - 65.0) * 0.015
        if state.get("phase") in {"contending", "contending_with_future_upside"}:
            discount += 0.25
        threshold -= min(1.3, discount)
    return round(threshold, 3)


def evaluation_notes(canonical: dict[str, Any], team_id: str, net: float, threshold: float, strategic: float, personality: dict[str, float], legality: dict[str, Any], *, accepted: bool | None = None) -> str:
    team = team_by_id(canonical, team_id)
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team_id)
    if legality["status"] != "legal":
        return f"{team['abbrev']} cannot execute without resolving legality status {legality['status']}: {'; '.join(legality['issues'] or legality['manual_review'])}."
    verdict = "accepts" if (net >= threshold if accepted is None else accepted) else "rejects"
    phase = state.get('window_phase') or {'contending': 'peak', 'developing': 'entering', 'retooling': 'exiting'}.get(state.get('phase'), 'rebuilding')
    return f"{team['abbrev']} {verdict}: net {net:.2f} vs threshold {threshold:.2f}. Phase={phase}; strategic fit {strategic:.2f}; personality adjustment {personality['total']:.2f}."


def salary_matching_issue(canonical: dict[str, Any], proposal: TradeProposal, config: dict[str, Any]) -> str | None:
    salary_config = config.get("salary_matching", {})
    if not salary_config.get("enabled", True):
        return None
    season = str(canonical.get('meta', {}).get('active_season') or CANONICAL_SEASON)
    involved = set(trade_team_ids(proposal))   # once per check: the obligation ledger grows every season
    if any(s.get('salary') is None for r in canonical.get('waived_salary_obligations', [])
           if r['team_id'] in involved
           for s in r['seasons'] if s['season'] >= season):
        return 'Waived salary is unresolved; salary matching requires review.'
    floor = float(salary_config.get("salary_floor", 7_500_000))
    multiplier = float(salary_config.get("incoming_multiplier", 1.25))
    plus = min(float(salary_config.get("incoming_plus", 7_500_000)), 5_000_000)
    active_season = str(canonical.get("meta", {}).get("active_season") or CANONICAL_SEASON)
    tax_line = cap_lines_for_season(active_season)["tax_line"]
    flows = trade_team_flows(proposal)
    for team_id, outgoing, incoming in flows:
        outgoing_salary, incoming_salary = package_salary(canonical, outgoing), package_salary(canonical, incoming)
        if outgoing_salary is None or incoming_salary is None:
            continue
        after = team_current_salary_total(canonical, team_id) - outgoing_salary + incoming_salary
        credit = package_matching_credit(canonical, outgoing)
        if incoming_salary > floor and incoming_salary > credit * multiplier + plus and after > tax_line:
            return f"{team_by_id(canonical, team_id)['abbrev']} incoming salary exceeds practical matching tolerance."
    for team_id, outgoing, incoming in flows:
        current_total = team_current_salary_total(canonical, team_id)
        outgoing_salary = package_salary(canonical, outgoing) or 0.0
        incoming_salary = package_salary(canonical, incoming) or 0.0
        after_total = current_total - outgoing_salary + incoming_salary
        hard_cap = cap_lines_for_season(active_season)["hard_cap"]
        if after_total > hard_cap and after_total > current_total + 250_000:
            return f"{team_by_id(canonical, team_id)['abbrev']} would move above the hard-cap/apron guardrail."
    active_start = season_start_from_label(active_season)
    for offset in range(1, 4):
        start = active_start + offset
        season = f"{start}-{str(start + 1)[-2:]}"
        for team_id, outgoing, incoming in flows:
            current_total = team_salary_total_for_season(canonical, team_id, season)
            outgoing_salary = package_salary_for_season(canonical, outgoing, season)
            incoming_salary = package_salary_for_season(canonical, incoming, season)
            if current_total is None or outgoing_salary is None or incoming_salary is None:
                continue
            after_total = current_total - outgoing_salary + incoming_salary
            hard_cap = cap_lines_for_season(season)["hard_cap"]
            # Future payroll can still be trimmed with a fringe/minimum roster
            # move before that league year begins. Block material overages, not
            # a sub-minimum bookkeeping edge that roster cutdown can repair.
            if after_total > hard_cap + 2_500_000 and after_total > current_total + 250_000:
                return f"{team_by_id(canonical, team_id)['abbrev']} would worsen a {season} hard-cap overage."
    return None


def package_matching_credit(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> float:
    """Unprotected outgoing money cannot manufacture matching exceptions."""
    season = str(canonical.get('meta', {}).get('active_season') or CANONICAL_SEASON)
    today = str(canonical.get('meta', {}).get('current_date') or '')
    total = 0.0
    for asset in assets:
        if asset['kind'] != 'player':
            continue
        contract = contract_for_player(canonical, asset['id']) or {}
        row = next((s for s in contract.get('seasons', []) if s.get('season') == season), {})
        salary = float(current_salary(contract) or 0)
        protected = row.get('guaranteed_salary')
        if row.get('guarantee_date') and today >= row['guarantee_date']:
            protected = salary
        total += salary if protected is None else min(salary, max(0, float(protected)))
    return total


def package_salary(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> float | None:
    total = 0.0
    for asset in assets:
        if asset["kind"] != "player":
            continue
        salary = current_salary(contract_for_player(canonical, asset["id"]))
        if salary is None:
            return None
        total += salary
    return total


def contract_salary_for_trade_season(contract: dict[str, Any] | None, season: str) -> float | None:
    if not contract:
        return 0.0
    for row in contract.get("seasons", []):
        if str(row.get("season") or "") != season:
            continue
        salary = row.get("salary")
        return None if salary is None else float(salary)
    return 0.0


def package_salary_for_season(canonical: dict[str, Any], assets: list[dict[str, Any]], season: str) -> float | None:
    total = 0.0
    for asset in assets:
        if asset["kind"] != "player":
            continue
        salary = contract_salary_for_trade_season(contract_for_player(canonical, asset["id"]), season)
        if salary is None:
            return None
        total += salary
    return total


def team_salary_total_for_season(canonical: dict[str, Any], team_id: str, season: str) -> float | None:
    from .trade_finance_search import financial_fact
    return financial_fact(canonical, ('season',team_id,season), lambda: _uncached_team_salary_total_for_season(canonical, team_id, season))


def _uncached_team_salary_total_for_season(canonical: dict[str, Any], team_id: str, season: str) -> float | None:
    from .contract_protection import waived_total
    if any(s.get('salary') is None for r in canonical.get('waived_salary_obligations', [])
           if r['team_id'] == team_id for s in r['seasons'] if s['season'] == season):
        return None
    total = waived_total(canonical, team_id, season)
    for player in canonical.get("players", []):
        if player.get("team_id") != team_id:
            continue
        salary = contract_salary_for_trade_season(contract_for_player(canonical, player["id"]), season)
        if salary is None:
            return None
        total += salary
    return total


def team_current_salary_total(canonical: dict[str, Any], team_id: str) -> float:
    from .trade_finance_search import financial_fact
    return financial_fact(canonical, ('current',team_id), lambda: _uncached_team_current_salary_total(canonical, team_id))


def _uncached_team_current_salary_total(canonical: dict[str, Any], team_id: str) -> float:
    from .contract_protection import waived_total
    total = waived_total(canonical, team_id, str(canonical.get('meta', {}).get('active_season') or CANONICAL_SEASON))
    for player in canonical.get("players", []):
        if player.get("team_id") != team_id:
            continue
        salary = current_salary(contract_for_player(canonical, player["id"]))
        if salary:
            total += salary
    return total


def roster_count_issues(canonical: dict[str, Any], proposal: TradeProposal, config: dict[str, Any]) -> list[str]:
    salary_config = config.get("salary_matching", {})
    minimum = int(salary_config.get("minimum_roster", 12))
    temporary_hard_maximum = int(salary_config.get("temporary_hard_maximum", 24))
    issues = []
    # Human-controlled teams may take on more players than the roster limit: the roster cut-down pop-up makes them
    # trim afterwards (user decision, 2026-11-19). AI teams keep the guardrail.
    human_teams = set(canonical.get("_human_team_ids") or [])
    for team_id, outgoing, incoming in trade_team_flows(proposal):
        from .trade_finance_search import financial_fact
        current = financial_fact(canonical, ('roster',team_id),
            lambda: sum(1 for player in canonical['players'] if player['team_id']==team_id))
        after = current - sum(1 for asset in outgoing if asset["kind"] == "player") + sum(1 for asset in incoming if asset["kind"] == "player")
        if after > temporary_hard_maximum and after > current and team_id not in human_teams:
            issues.append(f"{team_by_id(canonical, team_id)['abbrev']} would exceed temporary roster hard maximum {temporary_hard_maximum}.")
        if after < minimum and after < current:
            issues.append(f"{team_by_id(canonical, team_id)['abbrev']} would fall below roster minimum {minimum}.")
    return issues


def stepien_guardrail_issues(canonical: dict[str, Any], proposal: TradeProposal) -> list[str]:
    issues = []
    for team_id, assets, _ in trade_team_flows(proposal):
        outgoing_first_years = sorted(
            int(pick_by_id(canonical, asset["id"]).get("season"))
            for asset in assets
            if asset["kind"] == "pick"
            and int(pick_by_id(canonical, asset["id"]).get("round") or 0) == 1
            and pick_by_id(canonical, asset["id"]).get("original_team_id") == team_id
            and str(pick_by_id(canonical, asset["id"]).get("season")).isdigit()
        )
        for previous, current in zip(outgoing_first_years, outgoing_first_years[1:], strict=False):
            if current == previous + 1:
                issues.append(f"{team_by_id(canonical, team_id)['abbrev']} trips simple Stepien guardrail by trading consecutive firsts.")
    return issues


def duplicate_trade_assets(assets: list[dict[str, Any]]) -> set[str]:
    seen = set()
    dupes = set()
    for asset in assets:
        key = f"{asset['kind']}:{asset['id']}"
        if key in seen:
            dupes.add(key)
        seen.add(key)
    return dupes


def ranked_pick_asset_value(pick: dict[str, Any], phase: str) -> float:
    """Expected value of exactly one guaranteed order statistic, not a leaf."""
    fields = ("id", "season", "round", "original_team_id", "status", "overall_pick", "projected_pick_slot", "_protection_value_factor")
    leaves = []
    for pid in pick["_ranked_entitlement"]["pool_pick_ids"]:
        row = pick["_ranked_leaf_picks"][pid]
        leaf = {field: row.get(field) for field in fields}
        leaf["current_owner_team_id"] = row.get("original_team_id")
        leaf["_active_season"] = pick.get("_active_season") or row.get("_active_season") or CANONICAL_SEASON
        leaf["_ranked_scenario"] = True
        leaves.append(leaf)
    values = ranked_pool_expected_values(json.dumps(leaves, sort_keys=True), phase)
    return values[pick["_ranked_entitlement"]["rank"] - 1]


@lru_cache(maxsize=2048)
def ranked_pool_expected_values(pool_json: str, phase: str) -> tuple[float, ...]:
    """96 reproducible, paired draft-position scenarios shared by all ranks.

    Farther seasons have wider team-outcome uncertainty. The existing roster
    projection already regresses future slots, so do not regress them twice.
    Actual lottery positions are fixed. No optional-swap premium is added:
    uncertainty enters once through the distribution of selected outcomes.
    """
    leaves = json.loads(pool_json)
    active = season_start_from_label(str(leaves[0].get("_active_season") or CANONICAL_SEASON))
    distance = max(0, (pick_season_start(leaves[0]) or active) - active)
    spread = min(10.0, 2.0 + 1.3 * distance)
    round_no = int(leaves[0].get("round") or 1)
    offset = 30 if round_no == 2 else 0
    means = []
    tables = []
    for leaf in leaves:
        slot = float(leaf.get("overall_pick") or leaf.get("projected_pick_slot") or (15.5 + offset))
        if offset and slot <= 30:
            slot += offset
        means.append(clamp(slot, 1 + offset, 30 + offset))
        tables.append({slot: pick_asset_value({**leaf, "overall_pick": slot}, phase) for slot in range(1 + offset, 31 + offset)})
    seed = hashlib.sha256(":".join(str(leaf["id"]) for leaf in leaves).encode()).hexdigest()
    rng = random.Random(seed)
    totals = [0.0] * len(leaves)
    known = all(leaf.get("overall_pick") for leaf in leaves)
    samples = 1 if known else 96
    for pair in range(1 if known else 48):
        deviations = [0.0 if leaf.get("overall_pick") else rng.gauss(0, spread) for leaf in leaves]
        for direction in ([1] if known else [1, -1]):
            positions = [int(round(clamp(mean + direction * deviation, 1 + offset, 30 + offset))) for mean, deviation in zip(means, deviations)]
            ordered = sorted(range(len(leaves)), key=lambda index: (positions[index], leaves[index]["id"]))
            for rank, index in enumerate(ordered):
                totals[rank] += tables[index][positions[index]]
    return tuple(round(total / samples, 2) for total in totals)


def nested_pick_asset_value(pick: dict[str, Any], phase: str) -> float:
    """One full-pick baseline plus bounded, diminishing selection optionality.

    Reuse projected slots, phase, distance, protection and uncertainty from
    ordinary picks. Never sum leaf pick values or price child rights again.
    """
    leaves = pick["_nested_leaf_picks"]
    values = {pid: pick_asset_value({**row, "_active_season": pick.get("_active_season") or row.get("_active_season")}, phase) for pid, row in leaves.items()}
    active = season_start_from_label(str(pick.get("_active_season") or CANONICAL_SEASON))
    distance = max(0, (pick_season_start(pick) or active) - active)
    uncertainty = clamp(0.68 - distance * 0.08, 0.34, 0.68)
    # The established swap model's fixed optionality, shared by the whole
    # entitlement rather than multiplied by the number of nested comparisons.
    budget = 7.8 if int(pick.get("round") or 2) == 1 else 3.8 * 0.62
    def value(node):
        if node["type"] == "pick":
            return values[node["pick_id"]], 0
        left, depth_a = value(node["left"])
        right, depth_b = value(node["right"])
        depth = max(depth_a, depth_b)
        selected = max(left, right) if node["benefit"] == "better" else min(left, right)
        direction = 1 if node["benefit"] == "better" else -1
        result = left + (selected - left) * uncertainty + direction * budget * (0.5 ** (depth + 1))
        return result, depth + 1
    estimate, _ = value(pick["_nested_entitlement"]["tree"])
    cap = 128.0 if int(pick.get("round") or 2) == 1 else 96.0
    return round(clamp(estimate, max(1.0, min(values.values()) - budget), min(cap, max(values.values()) + budget)), 2)


def pick_asset_value(pick: dict[str, Any], phase: str) -> float:
    if not pick:
        return 0.0
    if pick.get("status") in {"used_draft_pick", "expired_draft_pick"} or not pick.get("current_owner_team_id") or pick.get("_obligation_locked"):
        return 0.0
    if pick.get("_ranked_entitlement"):
        return ranked_pick_asset_value(pick, phase)
    if pick.get("_nested_entitlement"):
        return nested_pick_asset_value(pick, phase)
    round_no = int(pick.get("round") or 2)
    slot = pick.get("overall_pick") or pick.get("projected_pick_slot")
    try:
        slot_value = int(slot) if slot is not None else None
    except (TypeError, ValueError):
        slot_value = None
    active_start = season_start_from_label(str(pick.get("_active_season") or pick.get("active_season") or CANONICAL_SEASON))
    pick_start = pick_season_start(pick) or active_start + 1
    distance = max(0, pick_start - active_start)
    if round_no == 1:
        if slot_value:
            if slot_value == 1:
                value = 126.0
            elif slot_value == 2:
                value = 118.0
            elif slot_value == 3:
                value = 112.0
            elif slot_value <= 5:
                value = 108.0 - (slot_value - 4) * 4.5
            elif slot_value <= 10:
                value = 96.0 - (slot_value - 6) * 3.0
            elif slot_value <= 20:
                value = 87.0 - (slot_value - 10) * 3.1
            else:
                value = 54.0 - (slot_value - 20) * 2.25
            value = clamp(value, 28, 128)
        elif pick.get("status") == "verified_2026_draft_board" and pick.get("id", "").split("-"):
            try:
                pick_no = int(pick["id"].split("-")[2])
            except (ValueError, IndexError):
                pick_no = 18
            if pick_no <= 5:
                value = 98.0 - pick_no * 2.3
            elif pick_no <= 10:
                value = 86.5 - (pick_no - 5) * 1.9
            elif pick_no <= 20:
                value = 77.0 - (pick_no - 10) * 2.5
            else:
                value = 52.0 - (pick_no - 20) * 2.1
            value = clamp(value, 28, 104)
        else:
            value = 43.0
        value -= max(0, distance - 1) * 1.18
    else:
        if slot_value:
            second_slot = slot_value + 30 if slot_value <= 30 else max(31, slot_value)
            value = clamp(24.5 - (second_slot - 31) * 0.32, 8.0, 24.5)
        else:
            value = 9.5
        value -= max(0, distance - 1) * 0.42
    if pick.get("status") == "inferred_future_second_round_scaffold":
        value -= 0.75
    if phase in {"rebuilding", "developing"}:
        value *= 1.18
    if phase in {"contending", "contending_with_future_upside"}:
        value *= 0.88
    distance_noise = 0.0 if pick.get("_ranked_scenario") else deterministic_pick_uncertainty_bonus(pick, distance, round_no)
    value += distance_noise
    value *= float(pick.get("_protection_value_factor") or 1.0)
    return round(clamp(value, 1, 128 if round_no == 1 else 96), 2)


def deterministic_pick_uncertainty_bonus(pick: dict[str, Any], distance: int, round_no: int) -> float:
    if distance <= 1:
        return 0.0
    token = f"{pick.get('season')}:{pick.get('round')}:{pick.get('original_team_id')}:{pick.get('current_owner_team_id')}"
    raw = (sum(ord(char) for char in token) % 1000) / 1000.0 - 0.5
    scale = min(6.5 if round_no == 1 else 2.2, distance * (1.35 if round_no == 1 else 0.45))
    return round(raw * scale, 2)


def pick_offer_preference_score(pick: dict[str, Any], phase: str, target_value: float) -> float:
    value = pick_asset_value(pick, phase)
    year = pick_season_start(pick)
    round_no = int(pick.get("round") or 2)
    distance = max(0, year - 2026) if year else 3
    near_bonus = max(0.0, 5.0 - distance) * 2.2
    second_bonus = 8.0 if round_no == 2 and target_value < 55 else 0.0
    guarded_first_penalty = 10.0 if round_no == 1 and target_value < 38 else 0.0
    distant_penalty = far_future_pick_risk(pick) * 2.8
    return value + near_bonus + second_bonus - guarded_first_penalty - distant_penalty


def far_future_pick_risk(pick: dict[str, Any]) -> float:
    year = pick_season_start(pick)
    if not year:
        return 1.0
    distance = max(0, year - 2026)
    round_no = int(pick.get("round") or 2)
    base = max(0.0, distance - 2) * (2.4 if round_no == 1 else 0.75)
    if pick.get("protections"):
        base *= 0.75
    return round(base, 2)


def pick_season_start(pick: dict[str, Any]) -> int | None:
    try:
        return int(str(pick.get("season") or "").split("-")[0])
    except (TypeError, ValueError):
        return None


def tradeable_picks_for_team(canonical: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    active_season = str(canonical.get("meta", {}).get("active_season") or CANONICAL_SEASON)
    for pick in canonical.get("draft_picks", []):
        if pick.get("current_owner_team_id") != team_id:
            continue
        if pick.get("status") in {"used_draft_pick", "expired_draft_pick", "forfeited"}:
            continue
        if pick.get("_obligation_locked"):
            continue
        key = (
            str(pick.get("season") or ""),
            int(pick.get("round") or 0),
            pick.get("original_team_id"),
            pick.get("current_owner_team_id"),
            pick.get("overall_pick") if pick.get("overall_pick") is not None else None,
            normalize_pick_protection_text(pick),
        )
        pick["_active_season"] = active_season
        previous = deduped.get(key)
        if previous is None or pick_record_sort_key(pick) > pick_record_sort_key(previous):
            deduped[key] = pick
    return sorted(
        deduped.values(),
        key=lambda pick: (
            str(pick.get("season") or ""),
            int(pick.get("round") or 9),
            int(pick.get("overall_pick") or pick.get("projected_pick_slot") or 999),
            pick.get("original_team_id") or "",
            pick.get("id") or "",
        ),
    )


def normalize_pick_protection_text(pick: dict[str, Any]) -> str:
    return " ".join(clean_pick_protection_summary(pick).lower().split())


def pick_record_sort_key(pick: dict[str, Any]) -> tuple[float, int, str]:
    status_rank = {
        "verified_2026_draft_board": 4,
        "verified_future_pick_reference": 3,
        "inferred_future_second_round_scaffold": 2,
        "research_pending": 1,
    }.get(str(pick.get("status") or ""), 0)
    return (float(pick.get("confidence") or 0.0), status_rank, str(pick.get("id") or ""))


def season_start_from_label(season: str | None) -> int:
    try:
        return int(str(season or CANONICAL_SEASON).split("-")[0])
    except (TypeError, ValueError):
        return 2025


def cap_lines_for_season(season: str | None) -> dict[str, float]:
    """The league's cap lines for a season: one shared source (cap_rules), the same lines the screens show.

    Until TRADE-VOLUME this counted cap growth from 2025-26, so the trade AI's 2026-27 tax line was $207.4M
    against the real $200.4M everything else used."""
    from .cap_rules import cap_lines_for_season as shared_lines
    return shared_lines(season)


def best_tradeable_pick(canonical: dict[str, Any], team_id: str) -> dict[str, Any] | None:
    picks = [
        pick for pick in tradeable_picks_for_team(canonical, team_id)
        if int(pick.get("round") or 0) == 1
    ]
    if not picks:
        picks = tradeable_picks_for_team(canonical, team_id)
    if not picks:
        return None
    return sorted(picks, key=lambda pick: pick_asset_value(pick, "neutral"), reverse=True)[0]


def position_counts(players: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"guard": 0, "wing": 0, "big": 0}
    for player in players:
        if float(player.get("minutes_projection") or 0) < 5:
            continue
        counts[player_position_bucket(player)] += 1
    return counts


def player_position_bucket(player: dict[str, Any]) -> str:
    pos = str(player.get("position") or "").upper()
    if "C" in pos or "PF" in pos:
        return "big"
    if "SF" in pos:
        return "wing"
    return "guard"


def resolve_team(canonical: dict[str, Any], query: str | None) -> dict[str, Any]:
    if query is None:
        raise ValueError("Team query is required.")
    low = query.strip().lower()
    matches = [team for team in canonical.get("teams", []) if team["abbrev"].lower() == low or team["id"].lower() == low]
    matches = matches or [team for team in canonical.get("teams", []) if low in team["name"].lower()]
    if not matches:
        raise ValueError(f"No team found matching {query!r}")
    return matches[0]


def resolve_player(canonical: dict[str, Any], query: str, team_id: str | None = None) -> dict[str, Any]:
    needle = normalize_name(query)
    players = canonical.get("players", [])
    if team_id:
        team_rows = _search_team_rows(canonical, team_id)
        players = [player for player in (players if team_rows is None else team_rows) if player["team_id"] == team_id]
    exact = next((p for p in players if p['id'] == query), None)
    if exact is not None:
        return exact
    matches = [player for player in players if needle == player["normalized_name"] or needle in normalize_name(player["name"])]
    if not matches:
        raise ValueError(f"No player found matching {query!r}")
    return sorted(matches, key=lambda item: item.get("minutes_projection") or 0, reverse=True)[0]


def player_by_id(canonical: dict[str, Any], player_id: str) -> dict[str, Any] | None:
    cached = canonical.get("_players_by_id")
    if not isinstance(cached, dict):
        cached = {player["id"]: player for player in canonical.get("players", []) if player.get("id")}
        if canonical.get("_allow_internal_caches"):
            canonical["_players_by_id"] = cached
    return cached.get(player_id)


def team_by_id(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    cached = canonical.get("_teams_by_id")
    if not isinstance(cached, dict):
        cached = {team["id"]: team for team in canonical.get("teams", []) if team.get("id")}
        if canonical.get("_allow_internal_caches"):
            canonical["_teams_by_id"] = cached
    return cached[team_id]


def pick_by_id(canonical: dict[str, Any], pick_id: str) -> dict[str, Any] | None:
    return next((pick for pick in canonical.get("draft_picks", []) if pick["id"] == pick_id), None)


def contract_for_player(canonical: dict[str, Any], player_id: str) -> dict[str, Any] | None:
    cached = canonical.get("_contracts_by_player_id")
    if not isinstance(cached, dict):
        cached = {
            contract["player_id"]: contract
            for contract in canonical.get("contracts", [])
            if contract.get("player_id")
        }
        if canonical.get("_allow_internal_caches"):
            canonical["_contracts_by_player_id"] = cached
    return cached.get(player_id)


def traits_by_player(canonical: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    cached = canonical.get("_transaction_traits_by_player")
    if isinstance(cached, dict):
        return cached
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for trait in canonical.get("traits", []):
        output.setdefault(trait["player_id"], {})[trait["trait_key"]] = trait
    if canonical.get("_allow_internal_caches"):
        canonical["_transaction_traits_by_player"] = output
    return output


def compact_player(player: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": player["id"],
        "name": player["name"],
        "team_id": player["team_id"],
        "team_abbrev": player.get("team_abbrev"),
        "position": player.get("position"),
        "age": player.get("age"),
        "minutes_projection": player.get("minutes_projection"),
    }


def pick_label(canonical: dict[str, Any], pick: dict[str, Any]) -> str:
    return pick_display_label(canonical, pick)


def clean_pick_protection_summary(pick: dict[str, Any]) -> str:
    text = str(pick.get("protection_summary") or pick.get("protections") or "").strip()
    if not text:
        return ""
    if text.lower().strip(". ") in {"protected", "protection", "protected pick", "conditionally protected"}:
        raise ValueError(f"Pick {pick.get('id', '')} has no explicit protection range; it cannot be valued, traded or resolved.")
    compact = " ".join(text.split())
    if re.fullmatch(r"lottery[- ]protected", compact, flags=re.IGNORECASE):
        return "top-14 protected"
    if "..." in compact or "…" in compact:
        return ""
    if re.search(r"\bfrozen\s+pick\b", compact, flags=re.IGNORECASE):
        return ""
    compact = re.sub(r"\s+and\s+if\s+.*$", "", compact, flags=re.IGNORECASE)
    compact = re.sub(r"\s*\(via [^)]+\)", "", compact, flags=re.IGNORECASE)
    if unsupported_pick_backup_condition(compact):
        return ""
    if unsupported_pick_condition(compact):
        return ""
    if compact.upper() == compact and compact.isalpha() and 2 <= len(compact) <= 4:
        return ""
    if re.search(r"\bvia\b", compact, flags=re.IGNORECASE) and not re.search(r"\b(if|protected|protection|top)\b", compact, flags=re.IGNORECASE):
        return ""
    if re.match(r"^from\b", compact, flags=re.IGNORECASE) and not re.search(r"\b(if|protected|protection|top)\b", compact, flags=re.IGNORECASE):
        return ""
    top_match = re.search(r"\btop[- ]?(\d{1,2})\s+protected\b", compact, flags=re.IGNORECASE)
    if top_match:
        return f"top-{int(top_match.group(1))} protected"
    protected_match = re.search(r"\bpicks?\s+(\d{1,2})\s*-\s*(\d{1,2})\s+protected\b", compact, flags=re.IGNORECASE)
    if protected_match:
        start = int(protected_match.group(1))
        end = int(protected_match.group(2))
        return f"top-{end} protected" if start == 1 else f"picks {start}-{end} protected"
    if_match = re.search(r"(?:\b[A-Z]{2,4}\s+)?\bIf\s+(\d{1,2})\s*-\s*(\d{1,2})\b", compact, flags=re.IGNORECASE)
    if if_match:
        start = int(if_match.group(1))
        end = int(if_match.group(2))
        if start > 1:
            return f"top-{start - 1} protected"
        return f"picks {start}-{end} protected"
    if re.search(r"(?:\b[A-Z]{2,4}\s+)?\bIf\s+\d{1,2}\b", compact, flags=re.IGNORECASE):
        return ""
    compact = re.sub(r"^\b[A-Z]{2,4}\s+", "", compact)
    if re.search(r"\bprotect(?:ed|ion)\b", compact, flags=re.IGNORECASE):
        raise ValueError(f"Pick {pick.get('id', '')} requires an explicit protection range.")
    return compact if len(compact) <= 40 else ""


def pick_label_note(pick: dict[str, Any]) -> str:
    compact = clean_pick_protection_summary(pick)
    if not compact:
        return ""
    return f" ({compact})"


def proposal_summary(canonical: dict[str, Any], proposal: dict[str, Any]) -> str:
    if proposal.get('transfers'):
        return trade_headline_from_payload(proposal)
    from_team = team_by_id(canonical, proposal["from_team_id"])["abbrev"]
    to_team = team_by_id(canonical, proposal["to_team_id"])["abbrev"]
    from_assets = ", ".join(asset.get("label", asset["id"]) for asset in proposal["from_assets"])
    to_assets = ", ".join(asset.get("label", asset["id"]) for asset in proposal["to_assets"])
    return f"{from_team} sends: {from_assets or 'future considerations'}. {to_team} sends: {to_assets or 'future considerations'}."


def deterministic_offset(*parts: str) -> int:
    text = "|".join(parts)
    return (sum(ord(char) for char in text) % 31) - 15


def deterministic_pick(values: list[str], *parts: str) -> str:
    if not values:
        return "balanced operator"
    return values[sum(ord(char) for char in "|".join(parts)) % len(values)]


def round_trait(value: Any) -> float:
    return round(clamp(maybe_float(value) or 50.0, 1, 99), 2)


def field_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key)


def empty_value() -> PlayerAssetValuation:
    return PlayerAssetValuation(
        id="empty",
        player_id="",
        team_id="",
        player_value=0,
        on_court_value=0,
        contract_surplus=0,
        age_curve=0,
        health_risk=0,
        role_scarcity=0,
        portability=0,
        playoff_value=0,
        development_upside=0,
        contract_status="missing",
        current_salary=None,
        confidence=0,
        source_ids=[],
        notes="",
    )
