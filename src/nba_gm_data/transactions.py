from __future__ import annotations

import json
import random
import re
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any

from .schema import (
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
from .utils import clamp, maybe_float, normalize_name, stable_id


FRONT_OFFICE_OVERRIDES_FILE = Path("data/overrides/front_office_overrides.json")
TRANSACTION_MODEL_CONFIG_FILE = Path("data/overrides/transaction_model_config.json")
TRADE_ASSET_KINDS = {"player", "pick", "pick_swap"}
TAX_LINE = 187_895_000
SECOND_APRON = 207_824_000
ANNUAL_CAP_GROWTH_RATE = 0.035
RECENTLY_TRADED_DAYS = 60
RECENTLY_ACQUIRED_PREMIUM_DAYS = 180
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
            "rebuilder_pick_bonus": 7.0,
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


def build_transaction_context(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = to_plain(canonical)
    config = config or default_transaction_model_config()
    front_offices = canonical.get("front_office_profiles") or to_plain(build_front_office_profiles(canonical.get("teams", []), canonical.get("team_profiles", []), {}))
    working = {**canonical, "front_office_profiles": front_offices}
    valuations = build_player_asset_valuations(working, config)
    working["player_asset_valuations"] = [to_plain(value) for value in valuations]
    states = build_team_strategic_states(working, valuations, config)
    working["team_strategic_states"] = [to_plain(state) for state in states]
    trade_block = build_trade_block_entries(working, states, valuations, config)
    return {
        "front_office_profiles": front_offices,
        "team_strategic_states": [to_plain(state) for state in states],
        "player_asset_valuations": [to_plain(value) for value in valuations],
        "trade_block_entries": [to_plain(entry) for entry in trade_block],
    }


def build_team_strategic_states(canonical: dict[str, Any] | Any, valuations: list[PlayerAssetValuation] | None = None, config: dict[str, Any] | None = None) -> list[TeamStrategicState]:
    canonical = to_plain(canonical)
    config = config or default_transaction_model_config()
    if valuations is None:
        valuations = build_player_asset_valuations(canonical, config)
    values_by_team: dict[str, list[PlayerAssetValuation]] = {}
    for valuation in valuations:
        values_by_team.setdefault(valuation.team_id, []).append(valuation)
    profiles = {profile["team_id"]: profile for profile in canonical.get("team_profiles", [])}
    front_offices = {profile["team_id"]: profile for profile in canonical.get("front_office_profiles", [])}
    output: list[TeamStrategicState] = []
    for team in canonical.get("teams", []):
        team_values = sorted(values_by_team.get(team["id"], []), key=lambda item: item.player_value, reverse=True)
        players = [player for player in canonical.get("players", []) if player["team_id"] == team["id"]]
        top_players = [player_by_id(canonical, value.player_id) for value in team_values[:5]]
        top_ages = [float(player.get("age")) for player in top_players if player and player.get("age") is not None]
        core_age = sum(top_ages[:3]) / len(top_ages[:3]) if top_ages[:3] else None
        ceiling = contention_ceiling(canonical, team, team_values)
        youth = youth_pipeline_score(players, team_values)
        pick_inventory = team_pick_inventory(canonical, team["id"])
        health_risk = team_health_risk(canonical, team_values[:6])
        salary = salary_posture(canonical, team["id"])
        profile = profiles.get(team["id"], {})
        front_office = front_offices.get(team["id"], {})
        phase = classify_team_phase(profile, ceiling, core_age, youth, pick_inventory, config)
        needs, excesses = team_needs_and_excesses(canonical, team, players, phase)
        pressure = strategic_pressure(profile, front_office, phase, core_age)
        output.append(
            TeamStrategicState(
                id=stable_id("team_strategy", team["id"]),
                team_id=team["id"],
                phase=phase,
                timeline=str(profile.get("timeline") or phase),
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
                notes="Strategic v1 state from team profile context, player values, age curve, health, salary, needs, and pick inventory.",
            )
        )
    return output


def build_player_asset_valuations(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> list[PlayerAssetValuation]:
    canonical = to_plain(canonical)
    config = config or default_transaction_model_config()
    from .sim import player_feature_vector

    traits = traits_by_player(canonical)
    contracts = {contract["player_id"]: contract for contract in canonical.get("contracts", [])}
    health_profiles = {profile["player_id"]: profile for profile in canonical.get("player_health_profiles", [])}
    health_states = {state["player_id"]: state for state in canonical.get("player_health_states", [])}
    output: list[PlayerAssetValuation] = []
    for player in canonical.get("players", []):
        features = player_feature_vector(canonical, player).features
        contract = contracts.get(player["id"], {})
        salary = current_salary(contract)
        contract_status = "salary_known" if salary is not None else "manual_review_required"
        age = maybe_float(player.get("age")) or 27.0
        portability = float(traits.get(player["id"], {}).get("portability", {}).get("value", features.get("impact", 50)))
        playoff = features.get("playoff_translation", 50.0)
        on_court = player_on_court_value(features, portability)
        age_curve = player_age_curve(age)
        development = player_development_upside(player, age, features)
        health_risk = player_health_risk(health_profiles.get(player["id"], {}), health_states.get(player["id"], {}))
        scarcity = role_scarcity_score(player, features, traits.get(player["id"], {}))
        surplus = contract_surplus_value(on_court, age_curve, development, salary, contract)
        weights = config.get("valuation_weights", {})
        value = (
            on_court
            + age_curve * float(weights.get("age_curve", 0.9))
            + development * float(weights.get("development_upside", 0.75))
            + surplus * float(weights.get("contract_surplus", 0.42))
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
                player_value=round(clamp(value, 1, 99), 2),
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
    canonical = to_plain(canonical)
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
) -> dict[str, Any]:
    canonical = with_transaction_context(canonical, config)
    user_team = resolve_team(canonical, for_team)
    seller = resolve_team(canonical, target_team_query)
    normalized_target = normalize_assets(canonical, seller, target_assets)
    if not normalized_target:
        return {
            "player": {},
            "target_assets": [],
            "for_team": user_team,
            "mode": "empty_package",
            "candidate_count": 0,
            "candidates": [],
            "notes": "No assets were selected.",
        }
    target_value = asset_package_value(canonical, normalized_target)
    target_salary = asset_package_salary(canonical, normalized_target)
    target_specs = trade_specs_from_normalized(normalized_target)
    selected_player_ids = {asset["id"] for asset in normalized_target if asset.get("kind") == "player"}
    candidates: list[dict[str, Any]] = []
    if seller["id"] == user_team["id"]:
        if package_is_effectively_untouchable(canonical, normalized_target):
            candidates = []
        else:
            for buyer in buyer_teams_for_asset_package(canonical, seller, normalized_target):
                if buyer["id"] == seller["id"]:
                    continue
                buyer_context_target_value = package_value_for_team(canonical, normalized_target, buyer["id"])
                for buyer_assets in buyer_offer_packages_for_value(canonical, buyer, seller, buyer_context_target_value, target_salary, seed, selected_player_ids)[:5]:
                    report = evaluate_trade(canonical, seller["abbrev"], buyer["abbrev"], target_specs, buyer_assets, seed=seed)
                    candidates.append(candidate_from_evaluation(canonical, report))
        mode = "shop_package"
    else:
        for package in buyer_offer_packages_for_value(canonical, user_team, seller, target_value, target_salary, seed, selected_player_ids)[:10]:
            report = evaluate_trade(canonical, user_team["abbrev"], seller["abbrev"], package, target_specs, seed=seed)
            candidates.append(candidate_from_evaluation(canonical, report))
        mode = "target_package"
    candidates = [candidate for candidate in candidates if user_facing_trade_candidate_ok(canonical, candidate, user_team["id"])]
    candidates = sorted(candidates, key=lambda item: candidate_sort_score(item, user_team["id"]), reverse=True)[:limit]
    return {
        "player": package_report_subject(canonical, normalized_target, seller),
        "target_assets": normalized_target,
        "for_team": user_team,
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
) -> dict[str, Any]:
    canonical = with_transaction_context(canonical, config)
    config = config or default_transaction_model_config()
    from_team = resolve_team(canonical, from_team_query)
    to_team = resolve_team(canonical, to_team_query)
    proposal = TradeProposal(
        id=stable_id("trade_proposal", date, from_team["id"], to_team["id"], json.dumps(from_assets, sort_keys=True), json.dumps(to_assets, sort_keys=True)),
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
    from_eval = evaluate_trade_for_team(canonical, proposal, from_team["id"], proposal.to_assets, proposal.from_assets, legality, seed, config)
    to_eval = evaluate_trade_for_team(canonical, proposal, to_team["id"], proposal.from_assets, proposal.to_assets, legality, seed, config)
    from_plain = trade_evaluation_payload(canonical, from_eval, config)
    to_plain_eval = trade_evaluation_payload(canonical, to_eval, config)
    proposal_payload = to_plain(proposal)
    return {
        "proposal": proposal_payload,
        "legality": legality,
        "evaluations": [from_plain, to_plain_eval],
        "accepted_by_all": from_eval.accepted and to_eval.accepted and legality["status"] == "legal",
        "value_breakdown": trade_value_breakdown(canonical, proposal_payload),
    }


def simulate_ai_trades(canonical: dict[str, Any] | Any, from_date: str, through_date: str, seed: int = 1, limit: int = 10, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_transaction_context(canonical, config)
    rng = random.Random(f"{seed}:{from_date}:{through_date}:ai_trades")
    recent_players = recently_traded_player_ids(canonical, through_date)
    entries = sorted(canonical["trade_block_entries"], key=lambda item: item["block_score"], reverse=True)[:120]
    proposals = []
    for entry in entries:
        player = player_by_id(canonical, entry["player_id"])
        if not player:
            continue
        if player.get("id") in recent_players:
            continue
        seller = team_by_id(canonical, player.get("team_id"))
        if not seller:
            continue
        possible_buyers = buyer_teams_for_player(canonical, player)
        rng.shuffle(possible_buyers)
        accepted_for_player = False
        for buyer in possible_buyers[:6]:
            if buyer["id"] == seller["id"]:
                continue
            packages = buyer_offer_packages(canonical, buyer, seller, player, seed, max_results=5, max_player_options=6)
            for buyer_assets in packages[:5]:
                report = evaluate_trade(
                    canonical,
                    seller["abbrev"],
                    buyer["abbrev"],
                    [{"kind": "player", "value": player["name"]}],
                    buyer_assets,
                    seed=seed,
                    date=through_date,
                    config=config,
                )
                candidate = candidate_from_evaluation(canonical, report)
                if ai_trade_candidate_accepted(canonical, candidate):
                    candidate = mark_ai_trade_accepted(candidate)
                    proposals.append(candidate)
                    accepted_for_player = True
                    break
            if len(proposals) >= limit or accepted_for_player:
                break
        if len(proposals) >= limit:
            break
    return {
        "from_date": from_date,
        "through_date": through_date,
        "seed": seed,
        "proposal_count": len(proposals),
        "proposals": proposals,
        "notes": "Deterministic AI-AI trade candidate generation. It suggests plausible proposals; application is separate.",
    }


def ai_trade_candidate_accepted(canonical: dict[str, Any], candidate: dict[str, Any]) -> bool:
    if candidate.get("legality", {}).get("status") != "legal":
        return False
    if candidate.get("accepted_by_all"):
        return True
    evaluations = candidate.get("evaluations") or []
    nets = [float(item.get("net_value") or 0.0) for item in evaluations]
    if not nets or min(nets) < -9.0 or sum(nets) < -2.0:
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
            evaluation["accepted"] = True
            evaluation["decision"] = "accept_bounded_ai_discretion"
            evaluation.setdefault("reasons", []).append("bounded_ai_discretion")
    return updated


def trade_evaluation_payload(canonical: dict[str, Any], evaluation: TradeEvaluation, config: dict[str, Any]) -> dict[str, Any]:
    payload = to_plain(evaluation)
    threshold = acceptance_threshold(canonical, evaluation.perspective_team_id, config)
    gap = round(float(evaluation.net_value) - threshold, 3)
    score = 0.0 if evaluation.legality_status != "legal" else clamp(50.0 + gap * 4.5, 0.0, 100.0)
    payload["team_abbrev"] = team_by_id(canonical, evaluation.perspective_team_id).get("abbrev")
    payload["acceptance_threshold"] = threshold
    payload["acceptance_gap"] = gap
    payload["acceptance_score"] = round(score, 2)
    return payload


def max_player_value_from_assets(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> float:
    values_by_player = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
    values = []
    for asset in assets:
        if asset.get("kind") == "player":
            player = player_by_id(canonical, asset.get("id"))
            values.append(float(values_by_player.get(asset.get("id"), fallback_asset_valuation(player)).get("player_value") or 0.0))
    return max(values or [0.0])


def apply_trade_to_save(save_path: str | Path, proposal_id: str, date: str = CANONICAL_START_DATE) -> dict[str, Any]:
    date = date or CANONICAL_START_DATE
    path = Path(save_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            save = json.load(handle)
    else:
        save = {"version": "save_transaction_ledger_v1", "pending_trade_proposals": [], "transaction_logs": []}
    proposal = next((item for item in save.get("pending_trade_proposals", []) if item.get("proposal", {}).get("id") == proposal_id or item.get("id") == proposal_id), None)
    if not proposal:
        return {
            "status": "not_found",
            "proposal_id": proposal_id,
            "save": str(path),
            "notes": "No pending proposal with this id exists in the save ledger. Generate/evaluate a proposal and add it to pending_trade_proposals before applying.",
        }
    if not trade_apply_authorized(proposal):
        return {
            "status": "not_applied_rejected",
            "proposal_id": proposal_id,
            "save": str(path),
            "notes": "Rejected saved or AI trade proposals cannot be applied. Rebuild or counter the offer instead.",
        }
    proposal_payload = proposal.get("proposal") or proposal
    if save.get("version") == "league_save_v1":
        validation_payload = {**proposal_payload, "pick_obligation_terms": proposal.get("pick_obligation_terms") or []}
        live_issues = trade_live_validation_issues(save, validation_payload, date)
        if live_issues:
            save["pending_trade_proposals"] = [
                item
                for item in save.get("pending_trade_proposals", [])
                if (item.get("proposal", {}).get("id") or item.get("id")) != proposal_id
            ]
            prune_result = prune_trade_offers_touching_assets(save, proposal_asset_identity_keys(proposal_payload), exclude_proposal_id=proposal_id)
            from .save import write_save

            write_save(path, save)
            return {
                "status": "not_applied_stale_assets",
                "proposal_id": proposal_id,
                "save": str(path),
                "issues": live_issues,
                "pruned": prune_result,
                "notes": "Trade was skipped because at least one asset moved, became locked, or recently traded before this offer was applied.",
            }
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
        for asset in proposal_payload.get("from_assets", []):
            if asset.get("kind") == "player":
                save.setdefault("roster_overrides", {})[asset["id"]] = to_team_id
            if asset.get("kind") == "pick":
                save.setdefault("draft_pick_overrides", {})[asset["id"]] = to_team_id
                update_retraded_pick_obligation(save, asset["id"], to_team_id, date)
            if asset.get("kind") == "pick_swap":
                update_retraded_pick_swap_obligation(save, asset["id"], to_team_id, date)
        for asset in proposal_payload.get("to_assets", []):
            if asset.get("kind") == "player":
                save.setdefault("roster_overrides", {})[asset["id"]] = from_team_id
            if asset.get("kind") == "pick":
                save.setdefault("draft_pick_overrides", {})[asset["id"]] = from_team_id
                update_retraded_pick_obligation(save, asset["id"], from_team_id, date)
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
    save.setdefault("transaction_logs", []).append(to_plain(log))
    save["pending_trade_proposals"] = [
        item
        for item in save.get("pending_trade_proposals", [])
        if (item.get("proposal", {}).get("id") or item.get("id")) != proposal_id
    ]
    pruned = prune_trade_offers_touching_assets(save, proposal_asset_identity_keys(proposal_payload), exclude_proposal_id=proposal_id)
    from .save import write_save

    write_save(path, save)
    return {"status": "applied", "save": str(path), "transaction_log": to_plain(log), "pruned": pruned}


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
    for asset in [*((proposal or {}).get("from_assets") or []), *((proposal or {}).get("to_assets") or [])]:
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
        return sorted(dict.fromkeys(errors))
    return []


def validate_pick_obligation_term(canonical_or_save: dict[str, Any], proposal: dict[str, Any] | None, term: dict[str, Any]) -> bool:
    return not pick_obligation_validation_errors(canonical_or_save, proposal, term)


def trade_player_ids(proposal: dict[str, Any]) -> list[str]:
    return sorted(
        {
            asset.get("id")
            for asset in [*(proposal.get("from_assets") or []), *(proposal.get("to_assets") or [])]
            if asset.get("kind") == "player" and asset.get("id")
        }
    )


def proposal_asset_identity_keys(proposal: dict[str, Any]) -> set[str]:
    payload = proposal.get("proposal") or proposal
    keys: set[str] = set()
    for asset in [*(payload.get("from_assets") or []), *(payload.get("to_assets") or [])]:
        kind = str(asset.get("kind") or "").lower()
        identifier = asset.get("id") or asset.get("player_id") or asset.get("pick_id") or asset.get("value")
        if kind and identifier:
            keys.add(f"{kind}:{identifier}")
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
        for asset in [*(assets.get("from_assets") or []), *(assets.get("to_assets") or [])]
        if asset.get("kind") == "player" and asset.get("id")
    }


def transaction_log_signed_player_ids(log: dict[str, Any]) -> set[str]:
    assets = log.get("assets") or {}
    player_id = assets.get("player_id") or log.get("player_id")
    return {player_id} if player_id else set()


def recently_traded_player_ids(canonical_or_save: dict[str, Any], as_of_date: str | None = None, days: int = RECENTLY_TRADED_DAYS) -> set[str]:
    current = parse_iso_date(as_of_date or ((canonical_or_save.get("meta") or {}).get("current_date")) or CANONICAL_START_DATE)
    if current is None:
        return set()
    recent: set[str] = set()
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


def recently_signed_player_ids(canonical_or_save: dict[str, Any], as_of_date: str | None = None) -> set[str]:
    current = parse_iso_date(as_of_date or ((canonical_or_save.get("meta") or {}).get("current_date")) or CANONICAL_START_DATE)
    if current is None:
        return set()
    restricted: set[str] = set()
    for log in canonical_or_save.get("transaction_logs", []):
        if log.get("transaction_type") not in SIGNING_TRANSACTION_TYPES or log.get("status") not in {"applied_to_save_ledger", "applied"}:
            continue
        signed_on = parse_iso_date(log.get("date"))
        if signed_on is None:
            continue
        unlock = date(signed_on.year, RECENTLY_SIGNED_UNLOCK_MONTH, RECENTLY_SIGNED_UNLOCK_DAY)
        if signed_on <= current < unlock:
            restricted.update(transaction_log_signed_player_ids(log))
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
    for side, expected_team_id in [("from_assets", proposal.get("from_team_id")), ("to_assets", proposal.get("to_team_id"))]:
        for asset in proposal.get(side, []) or []:
            label = asset.get("label") or asset.get("name") or asset.get("id") or "Asset"
            if asset.get("kind") == "player":
                player_id = asset.get("id")
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
    working = to_plain(canonical)
    if not terms:
        return working
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
    annotate_pick_obligation_context(working)
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
    canonical = to_plain(canonical)
    ensure_future_second_round_scaffolds(canonical)
    simplify_unsupported_pick_conditions(canonical)
    if transaction_context_is_complete(canonical):
        annotate_pick_value_context(canonical)
        annotate_pick_obligation_context(canonical)
        return canonical
    context = build_transaction_context(canonical, config)
    enriched = {**canonical, **context}
    annotate_pick_value_context(enriched)
    annotate_pick_obligation_context(enriched)
    return enriched


def ensure_future_second_round_scaffolds(canonical: dict[str, Any]) -> None:
    """Add practical own-second scaffolds because current public ledger is first-heavy."""
    teams = [team for team in canonical.get("teams", []) if team.get("id")]
    picks = canonical.setdefault("draft_picks", [])
    existing = {
        (str(pick.get("season")), int(pick.get("round") or 0), pick.get("original_team_id"))
        for pick in picks
    }
    active_start = season_start_from_label(str(canonical.get("meta", {}).get("active_season") or "2025-26"))
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
        for field in ["primary_pick_id", "team_a_pick_id", "team_b_pick_id"]:
            pick_id = obligation.get(field)
            if pick_id:
                by_pick.setdefault(pick_id, []).append(obligation)
        for pick_id in obligation.get("fallback_pick_ids") or []:
            locked.add(pick_id)
            by_pick.setdefault(pick_id, []).append({**obligation, "_fallback_lock": True})
    for pick in canonical.get("draft_picks", []):
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


def pick_obligation_label(obligation: dict[str, Any]) -> str:
    label = str(obligation.get("label") or "").strip()
    if label:
        return label
    protected = obligation.get("protected_range") or {}
    low = int(protected.get("from") or 1)
    high = int(protected.get("through") or obligation.get("protected_top_n") or 0)
    if low == 1 and high:
        return f"top-{high} protected"
    if low and high:
        return f"picks {low}-{high} protected"
    return "protected"


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
    teams = {team.get("id"): team.get("abbrev") for team in canonical.get("teams", [])}
    pick_a = pick_by_id(canonical, obligation.get("team_a_pick_id") or obligation.get("primary_pick_id"))
    pick_b = pick_by_id(canonical, obligation.get("team_b_pick_id") or obligation.get("counterparty_pick_id"))
    right_holder = obligation.get("current_rights_holder_team_id") or obligation.get("original_rights_holder_team_id") or obligation.get("receiver_team_id")
    holder = teams.get(right_holder) or team_id_fallback(right_holder)
    benefit = pick_swap_benefit(obligation)
    if pick_a and pick_b:
        season = pick_a.get("season") or pick_b.get("season") or obligation.get("season") or "----"
        round_no = pick_a.get("round") or pick_b.get("round") or obligation.get("round") or "?"
        a_original = teams.get(pick_a.get("original_team_id")) or "TBD"
        b_original = teams.get(pick_b.get("original_team_id")) or "TBD"
        if benefit == "worse":
            return f"{season} R{round_no} swap obligation: {holder} receives less favorable of {a_original}/{b_original}; other team receives better"
        return f"{season} R{round_no} swap right: {holder} may receive better of {a_original}/{b_original}; other team receives less favorable"
    return str(obligation.get("label") or "pick swap right")


def pick_swap_benefit(obligation: dict[str, Any]) -> str:
    benefit = str(obligation.get("benefit") or obligation.get("swap_benefit") or obligation.get("rights_benefit") or "better").lower()
    if benefit in {"worse", "less", "less_favorable", "lower"}:
        return "worse"
    return "better"


def pick_swap_context_note(canonical: dict[str, Any], obligation: dict[str, Any]) -> str:
    label = pick_swap_display_label(canonical, obligation)
    return f"Subject to {label}"


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
    active_year = season_start_from_label(str(canonical.get("meta", {}).get("active_season") or "2025-26"))
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
    swaps = []
    for obligation in active_pick_obligations(canonical):
        if obligation.get("type") != "pick_swap":
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
    swap_notes = [pick_swap_context_note(canonical, item) for item in pick_swap_obligations_for_pick(pick)]
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
    for side in ("from_assets", "to_assets"):
        for asset in proposal.get(side, []) or []:
            if asset.get("kind") == "pick":
                pick = pick_by_id(canonical, asset.get("id"))
                if pick:
                    asset["label"] = pick_display_label(canonical, pick)
                    asset["protection_summary"] = pick.get("protection_summary") or pick.get("protections")
            elif asset.get("kind") == "pick_swap":
                swap = pick_swap_by_id(canonical, asset.get("id"))
                if swap:
                    asset["label"] = pick_swap_display_label(canonical, swap)
    if proposal:
        refreshed["proposal"] = proposal
        refreshed["summary"] = proposal_summary(canonical, proposal)
    return refreshed


def pick_obligation_value_factor(obligations: list[dict[str, Any]]) -> float:
    factor = 1.0
    for obligation in obligations:
        if obligation.get("_fallback_lock"):
            factor *= 0.15
            continue
        if obligation.get("type") == "protected_pick":
            top_n = maybe_float(obligation.get("protected_top_n"))
            if top_n is None:
                protected = obligation.get("protected_range") or {}
                top_n = maybe_float(protected.get("through") or protected.get("max"))
            if top_n is not None:
                factor *= clamp(1.0 - float(top_n) * 0.018, 0.52, 0.98)
    return round(clamp(factor, 0.05, 1.0), 3)


def transaction_context_is_complete(canonical: dict[str, Any]) -> bool:
    if not (
        canonical.get("front_office_profiles")
        and canonical.get("team_strategic_states")
        and canonical.get("player_asset_valuations")
        and canonical.get("trade_block_entries") is not None
    ):
        return False
    valued = {value.get("player_id") for value in canonical.get("player_asset_valuations", [])}
    active_players = {player.get("id") for player in canonical.get("players", []) if player.get("team_id")}
    return active_players.issubset(valued)


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
    active_season = str(canonical.get("meta", {}).get("active_season") or "2025-26")
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
    minutes = maybe_float(player.get("minutes_projection")) or 0.0
    if minutes > 80:
        minutes = minutes / 82.0
    ability = maybe_float(player.get("current_ability")) or maybe_float(player.get("overall")) or (38.0 + minutes * 1.15)
    potential = maybe_float(player.get("potential")) or ability
    age = maybe_float(player.get("age")) or 24.0
    development = max(0.0, potential - ability) * (1.0 if age <= 24 else 0.45)
    player_value = clamp(ability * 0.54 + minutes * 1.15 + development * 0.42, 1, 99)
    player_value = max(player_value, drafted_rookie_value_floor(player, ability=ability, potential=potential))
    if goat_exception_player(player):
        player_value = 99.0
    portability = clamp(ability * 0.72 + minutes * 0.6, 1, 99)
    return {
        "player_value": round(player_value, 2),
        "on_court_value": round(clamp(ability * 0.65 + minutes * 0.8, 1, 99), 2),
        "contract_surplus": 0.0,
        "age_curve": round(player_age_curve(age), 2),
        "health_risk": 45.0,
        "role_scarcity": 5.0 if str(player.get("position") or "").upper() in {"C", "PG"} else 2.0,
        "portability": round(portability, 2),
        "playoff_value": round(clamp(ability * 0.72 + minutes * 0.5, 1, 99), 2),
        "development_upside": round(development, 2),
    }


def find_selling_candidates(
    canonical: dict[str, Any],
    user_team: dict[str, Any],
    target: dict[str, Any],
    seed: int,
    package_result_limit: int = 18,
    package_player_options: int = 9,
) -> list[dict[str, Any]]:
    candidates = []
    valuations = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
    target_value = market_trade_target_value(target, valuations.get(target.get("id"), fallback_asset_valuation(target)))
    per_buyer_limit = 10 if target_value >= 70 else 4
    for buyer in buyer_teams_for_player(canonical, target):
        if buyer["id"] == user_team["id"]:
            continue
        for buyer_assets in buyer_offer_packages(canonical, buyer, user_team, target, seed, max_results=package_result_limit, max_player_options=package_player_options)[:per_buyer_limit]:
            report = evaluate_trade(canonical, user_team["abbrev"], buyer["abbrev"], [{"kind": "player", "value": target["name"]}], buyer_assets, seed=seed)
            candidates.append(candidate_from_evaluation(canonical, report))
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
        report = evaluate_trade(canonical, user_team["abbrev"], target_team["abbrev"], package, [{"kind": "player", "value": target["name"]}], seed=seed)
        candidates.append(candidate_from_evaluation(canonical, report))
    return candidates


def buyer_offer_assets(canonical: dict[str, Any], buyer: dict[str, Any], seller: dict[str, Any], target: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    packages = buyer_offer_packages(canonical, buyer, seller, target, seed)
    return packages[0] if packages else []


def buyer_offer_packages(
    canonical: dict[str, Any],
    buyer: dict[str, Any],
    seller: dict[str, Any],
    target: dict[str, Any],
    seed: int,
    max_results: int = 18,
    max_player_options: int = 9,
) -> list[list[dict[str, Any]]]:
    valuations = {value["player_id"]: value for value in canonical["player_asset_valuations"]}
    target_valuation = valuations.get(target["id"], fallback_asset_valuation(target))
    target_value = market_trade_target_value(target, target_valuation)
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
    minutes = display_minutes_projection(player)
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
        return round(clamp(max(raw, rookie_floor), 1.0, min(cap, 99.0)), 2)
    if raw < 62 or minutes >= 28:
        return round(clamp(raw, 1.0, cap), 2)
    role_scale = clamp((max(4.0, minutes) / 30.0) ** 1.22, 0.36, 1.0)
    overall_proxy = float(ability)
    compressed = raw * role_scale
    if minutes < 20 and raw >= 70:
        compressed = min(compressed, 24.0 + max(0.0, overall_proxy - 55.0) * 0.5 + minutes * 0.5)
    if minutes < 24:
        compressed = min(compressed, 32.0 + max(0.0, overall_proxy - 55.0) * 0.68 + minutes * 0.43)
    return round(clamp(compressed, 1.0, raw), 2)


def market_value_after_star_and_surplus_shape(player: dict[str, Any], valuation: dict[str, Any], raw: float) -> float:
    on_court = float(valuation.get("on_court_value") or raw)
    playoff = float(valuation.get("playoff_value") or 50.0)
    surplus = float(valuation.get("contract_surplus") or 0.0)
    development = float(valuation.get("development_upside") or 0.0)
    minutes = display_minutes_projection(player)
    age = maybe_float(player.get("age")) or 27.0
    if surplus > 16.0 and on_court < 80.0 and development < 13.5:
        penalty_rate = 0.82 if on_court >= 74.0 else 1.12
        raw -= max(0.0, surplus - 16.0) * penalty_rate
        if age >= 31.0:
            raw -= min(7.5, (age - 30.0) * 1.05)
    if minutes >= 28.0 and on_court >= 79.0 and playoff >= 80.0:
        superstar_floor = 94.0 + max(0.0, on_court - 79.0) * 1.55 + max(0.0, playoff - 80.0) * 0.66
        if on_court >= 86.0 and playoff >= 84.0:
            superstar_floor += 7.5 + max(0.0, on_court - 88.0) * 0.55
        if raw >= 84.0 and playoff >= 82.0:
            superstar_floor += 8.0 + max(0.0, raw - 85.0) * 0.82
        superstar_floor -= max(0.0, age - 32.0) * 0.16
        raw = max(raw, superstar_floor)
    elif minutes >= 28.0 and on_court >= 76.5 and playoff >= 76.0 and surplus < 18.0:
        raw = max(raw, 84.0 + max(0.0, on_court - 76.5) * 0.68 + max(0.0, playoff - 76.0) * 0.18)
    return clamp(raw, 1.0, market_trade_value_cap(player, valuation, raw))


def market_trade_value_cap(player: dict[str, Any], valuation: dict[str, Any], raw: float | None = None) -> float:
    on_court = float(valuation.get("on_court_value") or raw or valuation.get("player_value") or 0.0)
    playoff = float(valuation.get("playoff_value") or 50.0)
    player_value = float(valuation.get("player_value") or raw or 0.0)
    minutes = display_minutes_projection(player)
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
    ability = float(ability if ability is not None else maybe_float(player.get("current_ability")) or maybe_float(player.get("overall")) or 50.0)
    potential = float(potential if potential is not None else maybe_float(player.get("potential")) or ability)
    if overall <= 30:
        base = 83.0 - (overall - 1) * 1.42
        talent = max(0.0, potential - 70.0) * 0.3 + max(0.0, ability - 52.0) * 0.24
        return round(clamp(base + talent, 34.0, 88.0), 2)
    base = 27.0 - (overall - 31) * 0.32
    talent = max(0.0, potential - 64.0) * 0.18 + max(0.0, ability - 50.0) * 0.12
    return round(clamp(base + talent, 7.0, 32.0), 2)


def goat_exception_player(player: dict[str, Any] | None) -> bool:
    return normalize_name((player or {}).get("name") or "") == "lebron james"


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
) -> list[list[dict[str, Any]]]:
    as_of_date = ((canonical.get("meta") or {}).get("current_date")) or CANONICAL_START_DATE
    excluded_player_ids = set(excluded_player_ids or set()) | recently_traded_player_ids(canonical, as_of_date)
    valuations = {value["player_id"]: value for value in canonical["player_asset_valuations"]}
    buyer_players = [player for player in canonical["players"] if player["team_id"] == buyer["id"]]
    block = {entry["player_id"]: entry for entry in canonical["trade_block_entries"] if entry["team_id"] == buyer["id"]}
    candidates = sorted(
        [player for player in buyer_players if player["id"] not in excluded_player_ids],
        key=lambda player: (
            block.get(player["id"], {}).get("block_score", 0),
            -abs(valuations.get(player["id"], fallback_asset_valuation(player))["player_value"] - target_value * 0.72),
            -abs((current_salary(contract_for_player(canonical, player["id"])) or 0) - (target_salary or 0)) / 1_000_000,
            player["name"],
        ),
        reverse=True,
    )
    tradable_players = []
    buyer_state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == buyer["id"]), {})
    for player in candidates:
        valuation = valuations.get(player["id"], fallback_asset_valuation(player))
        value = float(valuation["player_value"])
        block_score = float(block.get(player["id"], {}).get("block_score") or 0.0)
        if value >= 72 and target_value < 70:
            continue
        if value >= 58 and block_score < 55 and target_value < 68:
            continue
        if value >= 62 and block_score < 62 and team_fit_for_player(player, valuation, buyer_state) >= 7.0 and target_value < value + 12.0:
            continue
        if value > target_value * (1.08 if target_value >= 70 else 1.24):
            continue
        tradable_players.append(player)
    tradable_players = tradable_players[:max(3, int(max_player_options))]
    picks = sorted(
        tradeable_picks_for_team(canonical, buyer["id"]),
        key=lambda pick: pick_offer_preference_score(pick, buyer_state.get("phase", "balanced"), target_value),
        reverse=True,
    )[:9]
    firsts = [pick for pick in picks if int(pick.get("round") or 2) == 1]
    seconds = [pick for pick in picks if int(pick.get("round") or 2) == 2]
    swaps = sorted(
        tradeable_pick_swaps_for_team(canonical, buyer["id"]),
        key=lambda swap: pick_swap_asset_value(canonical, swap, buyer_state.get("phase", "neutral")),
        reverse=True,
    )[:3]
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
    packages: list[tuple[float, list[dict[str, Any]]]] = []
    max_player_count = 3 if target_value >= 60 and int(max_player_options) > 5 else 2
    for player_count in range(1, min(max_player_count, len(tradable_players)) + 1):
        for player_group in combinations(tradable_players, player_count):
            player_assets = [{"kind": "player", "value": player["name"]} for player in player_group]
            player_salary = sum(current_salary(contract_for_player(canonical, player["id"])) or 0.0 for player in player_group)
            for pick_group in pick_variants:
                if len(player_assets) + len(pick_group) > 4:
                    continue
                assets = [
                    *player_assets,
                    *[
                        {"kind": pick.get("kind", "pick"), "value": pick["id"]}
                        for pick in pick_group
                    ],
                ]
                rough_value = sum(offer_player_rough_value(canonical, player, target_value, target_salary, valuations) for player in player_group)
                rough_value += sum(
                    pick_swap_asset_value(canonical, pick, buyer_state.get("phase", "neutral"))
                    if pick.get("kind") == "pick_swap"
                    else pick_asset_value(pick, buyer_state.get("phase", "neutral"))
                    for pick in pick_group
                )
                search_value = rough_value
                if target_value >= 70:
                    normalized_assets = [
                        *[
                            {"kind": "player", "id": player["id"], "label": player["name"]}
                            for player in player_group
                        ],
                        *[
                            {
                                "kind": pick.get("kind", "pick"),
                                "id": pick["id"],
                                "label": pick.get("label") or pick.get("id"),
                            }
                            for pick in pick_group
                        ],
                    ]
                    search_value = package_value_for_team(canonical, normalized_assets, seller["id"])
                if search_value < target_value * (0.34 if target_value >= 56 else 0.38) or search_value > target_value * 1.48 + 14:
                    continue
                salary_gap = abs(player_salary - (target_salary or player_salary)) / 1_000_000
                complexity_cost = max(0, len(assets) - 2) * (0.1 if target_value >= 56 else 0.32)
                distant_risk = sum(far_future_pick_risk(pick) for pick in pick_group)
                packages.append((abs(search_value - target_value) + salary_gap * 0.22 + complexity_cost + distant_risk, assets))
    if not packages:
        fallback = fallback_trade_packages(canonical, buyer, seller, tradable_players, seconds, firsts, target_value, target_salary, valuations)
        packages.extend(fallback)
    unique: list[list[dict[str, Any]]] = []
    seen: set[str] = set()
    for _, assets in sorted(packages, key=lambda item: (item[0], json.dumps(item[1], sort_keys=True))):
        key = json.dumps(assets, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(assets)
        if len(unique) >= max(4, int(max_results)):
            break
    return unique


def offer_player_rough_value(
    canonical: dict[str, Any],
    player: dict[str, Any],
    target_value: float,
    target_salary: float | None,
    valuations: dict[str, dict[str, Any]],
) -> float:
    valuation = valuations.get(player["id"], fallback_asset_valuation(player))
    value = market_trade_target_value(player, valuation)
    salary = current_salary(contract_for_player(canonical, player["id"])) or 0.0
    filler = target_salary is not None and target_salary >= 8_000_000 and salary >= 5_000_000 and value < target_value * 0.55
    if filler:
        value *= 0.72
    elif target_value >= 56 and value < target_value * 0.62:
        value *= 0.88
    return value


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
    values = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
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
    valuations = {value["player_id"]: value for value in canonical["player_asset_valuations"]}
    value = valuations.get(player["id"], fallback_asset_valuation(player))
    teams = []
    for team in canonical["teams"]:
        if team["id"] == player["team_id"]:
            continue
        state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team["id"])
        fit = team_fit_for_player(player, value, state)
        if fit >= 3:
            teams.append((fit, team))
    return [team for _, team in sorted(teams, key=lambda item: (item[0], item[1]["abbrev"]), reverse=True)]


def candidate_from_evaluation(canonical: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    evaluations = report["evaluations"]
    combined = sum(item["net_value"] for item in evaluations)
    proposal = report["proposal"]
    return {
        "proposal": proposal,
        "legality": report["legality"],
        "evaluations": evaluations,
        "accepted_by_all": report["accepted_by_all"],
        "combined_score": round(combined, 3),
        "summary": proposal_summary(canonical, proposal),
        "value_breakdown": trade_value_breakdown(canonical, proposal),
    }


def user_facing_trade_candidate_ok(canonical: dict[str, Any], candidate: dict[str, Any], user_team_id: str) -> bool:
    if candidate.get("legality", {}).get("status") != "legal":
        return False
    proposal = candidate.get("proposal") or {}
    evaluations = candidate.get("evaluations") or []
    non_user_evals = [item for item in evaluations if item.get("perspective_team_id") != user_team_id]
    if non_user_evals and not any(item.get("accepted") for item in non_user_evals):
        return False
    user_eval = next((item for item in evaluations if item.get("perspective_team_id") == user_team_id), {})
    if float(user_eval.get("net_value") or 0) < -18.0:
        return False
    if float(user_eval.get("net_value") or 0) > 28:
        return False
    incoming = proposal.get("to_assets", []) if proposal.get("from_team_id") == user_team_id else proposal.get("from_assets", [])
    outgoing = proposal.get("from_assets", []) if proposal.get("from_team_id") == user_team_id else proposal.get("to_assets", [])
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
    values = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
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
    values = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
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
    return {
        "from_team_receives": package_value_breakdown(canonical, proposal.get("to_assets", []), proposal.get("from_team_id")),
        "to_team_receives": package_value_breakdown(canonical, proposal.get("from_assets", []), proposal.get("to_team_id")),
    }


def package_value_breakdown(canonical: dict[str, Any], assets: list[dict[str, Any]], perspective_team_id: str | None) -> dict[str, Any]:
    values = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
    state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == perspective_team_id), {})
    front = next((item for item in canonical.get("front_office_profiles", []) if item.get("team_id") == perspective_team_id), {})
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
    }
    asset_details: list[dict[str, Any]] = []
    multipliers = destination_role_multipliers(canonical, assets, perspective_team_id, [])
    for asset in assets:
        if asset.get("kind") == "player":
            player = player_by_id(canonical, asset.get("id"))
            valuation = values.get(asset.get("id"), fallback_asset_valuation(player))
            player_value = market_trade_target_value(player, valuation)
            fit = team_fit_for_player(player, valuation, state) if player and state else 0.0
            multiplier = multipliers.get(asset.get("id"), 1.0)
            pieces["player_quality"] += player_value
            pieces["role_value"] += (player_value + fit) * (multiplier - 1.0)
            pieces["age_timeline"] += float(valuation.get("age_curve") or 0.0) * 0.22
            pieces["contract"] += float(valuation.get("contract_surplus") or 0.0) * 0.34
            if player and state:
                pieces["lineup_fit"] += fit * 1.4
            pieces["health"] -= max(0.0, float(valuation.get("health_risk") or 0.0) - 12.0) * 0.25
            pieces["cap_roster"] += max(-4.0, min(4.0, float(valuation.get("contract_surplus") or 0.0) * 0.12))
            asset_details.append(
                {
                    "kind": "player",
                    "id": asset.get("id"),
                    "label": player.get("name") if player else asset.get("label") or asset.get("id"),
                    "raw_value": round(player_value + fit, 2),
                    "role_multiplier": round(multiplier, 3),
                    "adjusted_value": round((player_value + fit) * multiplier, 2),
                    "expected_role": role_label_from_multiplier(multiplier),
                }
            )
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
                }
            )
    pressure = float(front.get("owner_pressure") or state.get("pressure") or 55.0)
    discipline = float(front.get("asset_discipline") or 55.0)
    pieces["concentration"] = package_concentration_adjustment(
        [float(item.get("adjusted_value") or 0.0) for item in asset_details if item.get("kind") == "player"]
    )
    pieces["gm_modifier"] = (pressure - 55.0) * 0.025 - (discipline - 55.0) * 0.02
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


def evaluate_trade_for_team(
    canonical: dict[str, Any],
    proposal: TradeProposal,
    perspective_team_id: str,
    incoming_assets: list[dict[str, Any]],
    outgoing_assets: list[dict[str, Any]],
    legality: dict[str, Any],
    seed: int,
    config: dict[str, Any],
) -> TradeEvaluation:
    incoming = package_value_for_team(canonical, incoming_assets, perspective_team_id, outgoing_assets=outgoing_assets)
    outgoing = package_value_for_team(canonical, outgoing_assets, perspective_team_id)
    strategic = strategic_fit_adjustment(canonical, incoming_assets, outgoing_assets, perspective_team_id, config)
    personality = personality_trade_adjustment(canonical, perspective_team_id, proposal.id, seed)
    net = incoming - outgoing + strategic + personality["total"]
    threshold = acceptance_threshold(canonical, perspective_team_id, config)
    accepted = net >= threshold and legality["status"] == "legal"
    decision = "accept" if accepted else "reject"
    if legality["status"] == "manual_review_required":
        decision = "manual_review_required"
    if legality["status"] == "illegal":
        decision = "illegal_reject"
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
        notes=evaluation_notes(canonical, perspective_team_id, net, threshold, strategic, personality, legality),
    )


def trade_legality(canonical: dict[str, Any], proposal: TradeProposal, config: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    manual: list[str] = []
    recent_players = recently_traded_player_ids(canonical, transaction_reference_date(canonical, proposal))
    recently_signed = recently_signed_player_ids(canonical, transaction_reference_date(canonical, proposal))
    for team_id, assets in [(proposal.from_team_id, proposal.from_assets), (proposal.to_team_id, proposal.to_assets)]:
        for asset in assets:
            if asset["kind"] == "player":
                player = player_by_id(canonical, asset["id"])
                if not player or player["team_id"] != team_id:
                    issues.append(f"{asset.get('label', asset.get('id'))} is not on {team_by_id(canonical, team_id)['abbrev']}.")
                elif goat_exception_player(player):
                    issues.append("LeBron James is a GOAT exception and cannot be traded.")
                if asset["id"] in recent_players:
                    issues.append(f"{asset.get('label', asset.get('id'))} was traded within the last {RECENTLY_TRADED_DAYS} days.")
                if asset["id"] in recently_signed:
                    issues.append(f"{asset.get('label', asset.get('id'))} signed recently and cannot be traded until Dec. 1.")
                contract = contract_for_player(canonical, asset["id"])
                if contract_expired_without_rights(contract):
                    issues.append(f"{asset.get('label', asset.get('id'))} has an expired contract and no retained rights, so he cannot be traded in this phase.")
                    continue
                salary = current_salary(contract)
                if salary is None:
                    manual.append(f"{asset.get('label', asset.get('id'))} has unresolved salary.")
            elif asset["kind"] == "pick":
                pick = pick_by_id(canonical, asset["id"])
                if not pick or pick.get("current_owner_team_id") != team_id:
                    issues.append(f"Pick {asset.get('id')} is not owned by {team_by_id(canonical, team_id)['abbrev']}.")
                elif pick.get("_obligation_locked"):
                    issues.append(f"{pick_label(canonical, pick)} is locked as protection collateral and cannot be traded.")
            elif asset["kind"] == "pick_swap":
                swap = pick_swap_by_id(canonical, asset["id"])
                holder = (swap or {}).get("current_rights_holder_team_id") or (swap or {}).get("original_rights_holder_team_id") or (swap or {}).get("receiver_team_id")
                grantor = (swap or {}).get("sender_team_id") or (swap or {}).get("counterparty_team_id")
                if not swap or (holder != team_id and not (swap.get("pending_asset_grant") and grantor == team_id)):
                    issues.append(f"Pick swap {asset.get('id')} is not held by {team_by_id(canonical, team_id)['abbrev']}.")
    duplicate_assets = duplicate_trade_assets([*proposal.from_assets, *proposal.to_assets])
    if duplicate_assets:
        issues.append(f"Duplicate assets in proposal: {', '.join(sorted(duplicate_assets))}.")
    issues.extend(roster_count_issues(canonical, proposal, config))
    salary_issue = salary_matching_issue(canonical, proposal, config)
    if salary_issue:
        issues.append(salary_issue)
    issues.extend(stepien_guardrail_issues(canonical, proposal))
    if issues:
        status = "illegal"
    elif manual and config.get("decision", {}).get("manual_review_blocks_execution", True):
        status = "manual_review_required"
    else:
        status = "legal"
    return {"status": status, "issues": issues, "manual_review": manual}


def normalize_assets(canonical: dict[str, Any], team: dict[str, Any], assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            normalized.append(
                {
                    "kind": "pick_swap",
                    "id": swap["id"],
                    "label": pick_swap_display_label(canonical, swap),
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
    return clamp(value, 1, 99)


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
    return str((contract or {}).get("_active_season") or (contract or {}).get("active_season") or "2025-26")


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

    team_features = team_feature_vector(canonical, team).features
    depth_bonus = min(12.0, float(team_features.get("depth", 0))) * 0.25
    ceiling = (
        team_features.get("impact", 50) * 0.62
        + team_features.get("star_power", 50) * 0.18
        + team_features.get("defense_total", 50) * 0.12
        + team_features.get("primary_creator", 50) * 0.06
        + depth_bonus
    )
    return clamp(ceiling, 1, 99)


def youth_pipeline_score(players: list[dict[str, Any]], team_values: list[PlayerAssetValuation]) -> float:
    values = {value.player_id: value for value in team_values}
    young = [player for player in players if (maybe_float(player.get("age")) or 99) <= 24]
    return clamp(sum(values.get(player["id"], empty_value()).development_upside + values.get(player["id"], empty_value()).player_value * 0.12 for player in young), 0, 99)


def team_pick_inventory(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    picks = tradeable_picks_for_team(canonical, team_id)
    firsts = [pick for pick in picks if int(pick.get("round") or 0) == 1]
    seconds = [pick for pick in picks if int(pick.get("round") or 0) == 2]
    return {
        "first_round_count": len(firsts),
        "second_round_count": len(seconds),
        "near_term_firsts": sum(1 for pick in firsts if str(pick.get("season")) in {"2026", "2027", "2028"}),
        "pick_value": round(sum(pick_asset_value(pick, "neutral") for pick in picks), 2),
    }


def team_health_risk(canonical: dict[str, Any], top_values: list[PlayerAssetValuation]) -> float:
    if not top_values:
        return 0.0
    return sum(value.health_risk for value in top_values) / len(top_values)


def salary_posture(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    total = 0.0
    unresolved = 0
    for contract in canonical.get("contracts", []):
        if contract.get("team_id") != team_id:
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
    timeline = str(profile.get("timeline") or "").lower()
    has_timeline_signal = bool(timeline and timeline != "research_pending")
    thresholds = config.get("phase_thresholds", {})
    if "contending_with_future" in timeline:
        return "contending_with_future_upside"
    if "contending" in timeline:
        if youth >= float(thresholds.get("high_youth_pipeline", 45)):
            return "contending_with_future_upside"
        return "contending"
    if "rebuild" in timeline:
        return "rebuilding"
    if not has_timeline_signal and ceiling < 67 and youth >= 75 and (core_age or 30) <= 24.5:
        return "developing"
    if ceiling >= float(thresholds.get("contender_ceiling", 69)):
        return "contending_with_future_upside" if youth >= 45 and (core_age or 30) < 29 else "contending"
    if ceiling >= float(thresholds.get("playoff_ceiling", 60)):
        return "retooling" if (core_age or 28) >= 29.5 else "developing"
    if youth >= 42 or pick_inventory.get("near_term_firsts", 0) >= 3:
        return "developing"
    return "rebuilding"


def team_needs_and_excesses(canonical: dict[str, Any], team: dict[str, Any], players: list[dict[str, Any]], phase: str) -> tuple[list[str], list[str]]:
    from .sim import team_feature_vector

    features = team_feature_vector(canonical, team).features
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
    return score, sorted(dict.fromkeys(reasons)), sorted(dict.fromkeys(preferred or ["best_offer"]))


def block_willingness(score: float) -> str:
    if score >= 75:
        return "actively_shopping"
    if score >= 55:
        return "available_for_right_price"
    return "listening_only"


def team_fit_for_player(player: dict[str, Any], valuation: dict[str, Any], state: dict[str, Any]) -> float:
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
    return fit


def package_value_for_team(
    canonical: dict[str, Any],
    assets: list[dict[str, Any]],
    perspective_team_id: str,
    outgoing_assets: list[dict[str, Any]] | None = None,
) -> float:
    values = {value["player_id"]: value for value in canonical["player_asset_valuations"]}
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == perspective_team_id)
    multipliers = destination_role_multipliers(canonical, assets, perspective_team_id, outgoing_assets or [])
    total = 0.0
    player_adjusted_values: list[float] = []
    for asset in assets:
        if asset["kind"] == "player":
            player = player_by_id(canonical, asset["id"])
            value = values.get(asset["id"], fallback_asset_valuation(player))
            multiplier = multipliers.get(asset["id"], 1.0)
            player_value = market_trade_target_value(player, value)
            adjusted = (player_value + team_fit_for_player(player, value, state)) * multiplier
            adjusted -= max(0.0, float(value.get("health_risk") or 0.0) - 12.0) * 0.25
            adjusted += recently_acquired_player_premium(canonical, player, perspective_team_id, player_value)
            player_adjusted_values.append(adjusted)
            total += adjusted
        elif asset["kind"] == "pick":
            pick = pick_by_id(canonical, asset["id"])
            total += pick_asset_value(pick, state["phase"])
        elif asset["kind"] == "pick_swap":
            total += pick_swap_asset_value(canonical, pick_swap_by_id(canonical, asset["id"]) or asset, state["phase"])
    return total + package_concentration_adjustment(player_adjusted_values)


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
        teams = list(log.get("teams") or [])
        if len(teams) < 2:
            continue
        from_team, to_team = teams[0], teams[1]
        assets = log.get("assets") or {}
        destination = None
        if any(asset.get("kind") == "player" and asset.get("id") == player_id for asset in assets.get("from_assets", [])):
            destination = to_team
        elif any(asset.get("kind") == "player" and asset.get("id") == player_id for asset in assets.get("to_assets", [])):
            destination = from_team
        if destination != team_id:
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
    values = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
    outgoing_ids = {asset.get("id") for asset in outgoing_assets or [] if asset.get("kind") == "player"}
    incoming_players = [
        player_by_id(canonical, asset.get("id"))
        for asset in incoming_assets
        if asset.get("kind") == "player"
    ]
    incoming_players = [player for player in incoming_players if player]
    if not incoming_players:
        return {}
    roster_values = []
    for player in canonical.get("players", []):
        if player.get("team_id") != perspective_team_id or player.get("id") in outgoing_ids:
            continue
        valuation = values.get(player["id"], fallback_asset_valuation(player))
        roster_values.append((player["id"], float(valuation.get("player_value") or 0.0)))
    incoming_values = []
    for player in incoming_players:
        valuation = values.get(player["id"], fallback_asset_valuation(player))
        incoming_values.append((player["id"], float(valuation.get("player_value") or 0.0), display_minutes_projection(player)))
    all_values = roster_values + [(pid, value) for pid, value, _ in incoming_values]
    output: dict[str, float] = {}
    for player_id, value, current_minutes in incoming_values:
        rank = 1 + sum(1 for other_id, other_value in all_values if other_id != player_id and other_value > value)
        role_minutes = expected_minutes_for_destination_rank(rank)
        expected_minutes = min(36.0, max(role_minutes, min(float(current_minutes or 0.0), role_minutes + 3.0)))
        minute_weight = (max(2.0, expected_minutes) / 28.0) ** 1.8
        output[player_id] = round(clamp(minute_weight, 0.12, 1.22), 3)
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


def strategic_fit_adjustment(canonical: dict[str, Any], incoming: list[dict[str, Any]], outgoing: list[dict[str, Any]], team_id: str, config: dict[str, Any]) -> float:
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team_id)
    adjustment = 0.0
    for asset in incoming:
        if asset["kind"] == "pick" and state["phase"] in {"rebuilding", "developing"}:
            adjustment += float(config.get("decision", {}).get("rebuilder_pick_bonus", 7.0))
        if asset["kind"] == "pick_swap" and state["phase"] in {"rebuilding", "developing"}:
            swap_value = pick_swap_asset_value(canonical, pick_swap_by_id(canonical, asset.get("id")) or asset, state.get("phase", "balanced"))
            adjustment += float(config.get("decision", {}).get("rebuilder_pick_bonus", 7.0)) * (0.38 if swap_value >= 0 else -0.22)
        if asset["kind"] == "player":
            valuation = next(item for item in canonical["player_asset_valuations"] if item["player_id"] == asset["id"])
            if state["phase"] in {"contending", "contending_with_future_upside"} and valuation["playoff_value"] >= 64:
                adjustment += float(config.get("decision", {}).get("contender_need_bonus", 5.5))
    for asset in outgoing:
        if asset["kind"] == "pick" and state["phase"] in {"contending", "contending_with_future_upside"}:
            adjustment -= 1.5
        if asset["kind"] == "pick_swap" and state["phase"] in {"contending", "contending_with_future_upside"}:
            swap_value = pick_swap_asset_value(canonical, pick_swap_by_id(canonical, asset.get("id")) or asset, state.get("phase", "balanced"))
            adjustment += -0.6 if swap_value >= 0 else 0.35
    return adjustment


def personality_trade_adjustment(canonical: dict[str, Any], team_id: str, proposal_id: str, seed: int) -> dict[str, float]:
    front = next(item for item in canonical["front_office_profiles"] if item["team_id"] == team_id)
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team_id)
    rng = random.Random(f"{seed}:{proposal_id}:{team_id}:personality")
    competence = float(front.get("competence") or 55)
    pressure = float(state.get("pressure") or front.get("owner_pressure") or 55)
    mistake_window = (100 - competence) * 0.055 + max(0.0, pressure - 65) * 0.045
    noise = rng.uniform(-mistake_window, mistake_window)
    aggression = (float(front.get("aggressiveness") or 55) - 55) * 0.035
    star_chasing = (float(front.get("star_chasing") or 55) - 55) * 0.025
    discipline = (float(front.get("asset_discipline") or 55) - 55) * -0.02
    total = clamp(noise + aggression + star_chasing + discipline, -8, 8)
    return {
        "bounded_noise": round(noise, 3),
        "aggressiveness": round(aggression, 3),
        "star_chasing": round(star_chasing, 3),
        "asset_discipline": round(discipline, 3),
        "total": round(total, 3),
    }


def acceptance_threshold(canonical: dict[str, Any], team_id: str, config: dict[str, Any]) -> float:
    front = next(item for item in canonical["front_office_profiles"] if item["team_id"] == team_id)
    base = float(config.get("decision", {}).get("base_acceptance_threshold", 1.5))
    base += (float(front.get("asset_discipline") or 55) - 55) * 0.04
    base += (float(front.get("competence") or 55) - 55) * 0.025
    base -= (float(front.get("owner_pressure") or 55) - 55) * 0.03
    return round(base, 3)


def evaluation_notes(canonical: dict[str, Any], team_id: str, net: float, threshold: float, strategic: float, personality: dict[str, float], legality: dict[str, Any]) -> str:
    team = team_by_id(canonical, team_id)
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team_id)
    if legality["status"] != "legal":
        return f"{team['abbrev']} cannot execute without resolving legality status {legality['status']}: {'; '.join(legality['issues'] or legality['manual_review'])}."
    verdict = "accepts" if net >= threshold else "rejects"
    return f"{team['abbrev']} {verdict}: net {net:.2f} vs threshold {threshold:.2f}. Phase={state['phase']}; strategic fit {strategic:.2f}; personality adjustment {personality['total']:.2f}."


def salary_matching_issue(canonical: dict[str, Any], proposal: TradeProposal, config: dict[str, Any]) -> str | None:
    salary_config = config.get("salary_matching", {})
    if not salary_config.get("enabled", True):
        return None
    from_out = package_salary(canonical, proposal.from_assets)
    to_out = package_salary(canonical, proposal.to_assets)
    if from_out is None or to_out is None:
        return None
    floor = float(salary_config.get("salary_floor", 7_500_000))
    multiplier = float(salary_config.get("incoming_multiplier", 1.25))
    plus = min(float(salary_config.get("incoming_plus", 7_500_000)), 5_000_000)
    active_season = str(canonical.get("meta", {}).get("active_season") or "2025-26")
    tax_line = cap_lines_for_season(active_season)["tax_line"]
    from_current = team_current_salary_total(canonical, proposal.from_team_id)
    to_current = team_current_salary_total(canonical, proposal.to_team_id)
    from_after = from_current - from_out + to_out
    to_after = to_current - to_out + from_out
    from_can_absorb = from_after <= tax_line
    to_can_absorb = to_after <= tax_line
    if to_out > floor and to_out > from_out * multiplier + plus and not from_can_absorb:
        return f"{team_by_id(canonical, proposal.from_team_id)['abbrev']} incoming salary exceeds practical matching tolerance."
    if from_out > floor and from_out > to_out * multiplier + plus and not to_can_absorb:
        return f"{team_by_id(canonical, proposal.to_team_id)['abbrev']} incoming salary exceeds practical matching tolerance."
    for team_id, outgoing, incoming in [
        (proposal.from_team_id, proposal.from_assets, proposal.to_assets),
        (proposal.to_team_id, proposal.to_assets, proposal.from_assets),
    ]:
        current_total = team_current_salary_total(canonical, team_id)
        outgoing_salary = package_salary(canonical, outgoing) or 0.0
        incoming_salary = package_salary(canonical, incoming) or 0.0
        after_total = current_total - outgoing_salary + incoming_salary
        hard_cap = cap_lines_for_season(active_season)["hard_cap"]
        if after_total > hard_cap and after_total > current_total + 250_000:
            return f"{team_by_id(canonical, team_id)['abbrev']} would move above the hard-cap/apron guardrail."
    return None


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


def team_current_salary_total(canonical: dict[str, Any], team_id: str) -> float:
    total = 0.0
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
    for team_id, outgoing, incoming in [
        (proposal.from_team_id, proposal.from_assets, proposal.to_assets),
        (proposal.to_team_id, proposal.to_assets, proposal.from_assets),
    ]:
        current = sum(1 for player in canonical["players"] if player["team_id"] == team_id)
        after = current - sum(1 for asset in outgoing if asset["kind"] == "player") + sum(1 for asset in incoming if asset["kind"] == "player")
        if after > temporary_hard_maximum and after > current:
            issues.append(f"{team_by_id(canonical, team_id)['abbrev']} would exceed temporary roster hard maximum {temporary_hard_maximum}.")
        if after < minimum and after < current:
            issues.append(f"{team_by_id(canonical, team_id)['abbrev']} would fall below roster minimum {minimum}.")
    return issues


def stepien_guardrail_issues(canonical: dict[str, Any], proposal: TradeProposal) -> list[str]:
    issues = []
    for team_id, assets in [(proposal.from_team_id, proposal.from_assets), (proposal.to_team_id, proposal.to_assets)]:
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


def pick_asset_value(pick: dict[str, Any], phase: str) -> float:
    if not pick:
        return 0.0
    if pick.get("status") in {"used_draft_pick", "expired_draft_pick"} or not pick.get("current_owner_team_id") or pick.get("_obligation_locked"):
        return 0.0
    round_no = int(pick.get("round") or 2)
    slot = pick.get("overall_pick") or pick.get("projected_pick_slot")
    try:
        slot_value = int(slot) if slot is not None else None
    except (TypeError, ValueError):
        slot_value = None
    active_start = season_start_from_label(str(pick.get("_active_season") or pick.get("active_season") or "2025-26"))
    pick_start = pick_season_start(pick) or active_start + 1
    distance = max(0, pick_start - active_start)
    if round_no == 1:
        if slot_value:
            if slot_value <= 5:
                value = 111.0 - slot_value * 2.2
            elif slot_value <= 10:
                value = 99.0 - (slot_value - 5) * 2.4
            elif slot_value <= 20:
                value = 87.0 - (slot_value - 10) * 3.1
            else:
                value = 54.0 - (slot_value - 20) * 2.25
            value = clamp(value, 28, 108)
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
    distance_noise = deterministic_pick_uncertainty_bonus(pick, distance, round_no)
    value += distance_noise
    value *= float(pick.get("_protection_value_factor") or 1.0)
    return round(clamp(value, 1, 108 if round_no == 1 else 96), 2)


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
    active_season = str(canonical.get("meta", {}).get("active_season") or "2025-26")
    for pick in canonical.get("draft_picks", []):
        if pick.get("current_owner_team_id") != team_id:
            continue
        if pick.get("status") in {"used_draft_pick", "expired_draft_pick"}:
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
        return int(str(season or "2025-26").split("-")[0])
    except (TypeError, ValueError):
        return 2025


def cap_lines_for_season(season: str | None) -> dict[str, float]:
    elapsed = max(0, season_start_from_label(season) - 2025)
    factor = (1.0 + ANNUAL_CAP_GROWTH_RATE) ** elapsed
    return {
        "tax_line": round(TAX_LINE * factor / 100_000) * 100_000,
        "hard_cap": round(SECOND_APRON * factor / 100_000) * 100_000,
    }


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
        players = [player for player in players if player["team_id"] == team_id]
    matches = [player for player in players if needle == player["normalized_name"] or needle in normalize_name(player["name"]) or player["id"] == query]
    if not matches:
        raise ValueError(f"No player found matching {query!r}")
    return sorted(matches, key=lambda item: item.get("minutes_projection") or 0, reverse=True)[0]


def player_by_id(canonical: dict[str, Any], player_id: str) -> dict[str, Any] | None:
    return next((player for player in canonical.get("players", []) if player["id"] == player_id), None)


def team_by_id(canonical: dict[str, Any], team_id: str) -> dict[str, Any]:
    return next(team for team in canonical.get("teams", []) if team["id"] == team_id)


def pick_by_id(canonical: dict[str, Any], pick_id: str) -> dict[str, Any] | None:
    return next((pick for pick in canonical.get("draft_picks", []) if pick["id"] == pick_id), None)


def contract_for_player(canonical: dict[str, Any], player_id: str) -> dict[str, Any] | None:
    return next((contract for contract in canonical.get("contracts", []) if contract["player_id"] == player_id), None)


def traits_by_player(canonical: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for trait in canonical.get("traits", []):
        output.setdefault(trait["player_id"], {})[trait["trait_key"]] = trait
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
    compact = " ".join(text.split())
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
    return compact if len(compact) <= 40 else ""


def pick_label_note(pick: dict[str, Any]) -> str:
    compact = clean_pick_protection_summary(pick)
    if not compact:
        return ""
    return f" ({compact})"


def proposal_summary(canonical: dict[str, Any], proposal: dict[str, Any]) -> str:
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
