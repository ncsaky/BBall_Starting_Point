from __future__ import annotations

import json
import random
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
TRADE_ASSET_KINDS = {"player", "pick"}
SECOND_APRON = 207_824_000


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
            - health_risk * float(weights.get("health_risk", 0.55))
        )
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
        if score < 34:
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


def find_trade(canonical: dict[str, Any] | Any, player_name: str, for_team: str, limit: int = 10, seed: int = 1, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_transaction_context(canonical, config)
    user_team = resolve_team(canonical, for_team)
    target = resolve_player(canonical, player_name)
    candidates: list[dict[str, Any]] = []
    if effectively_untouchable(canonical, target):
        candidates = []
    elif target["team_id"] == user_team["id"]:
        candidates = find_selling_candidates(canonical, user_team, target, seed)
    else:
        candidates = find_buying_candidates(canonical, user_team, target, seed)
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
                for buyer_assets in buyer_offer_packages_for_value(canonical, buyer, seller, target_value, target_salary, seed, selected_player_ids)[:5]:
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
    return (
        float(valuation.get("player_value") or 0.0) >= 70.0
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
    entries = sorted(canonical["trade_block_entries"], key=lambda item: item["block_score"], reverse=True)[:80]
    proposals = []
    for entry in entries:
        player = player_by_id(canonical, entry["player_id"])
        if not player:
            continue
        possible_buyers = buyer_teams_for_player(canonical, player)
        rng.shuffle(possible_buyers)
        for buyer in possible_buyers[:4]:
            report = find_trade(canonical, player["name"], buyer["abbrev"], limit=1, seed=seed, config=config)
            if not report["candidates"]:
                continue
            candidate = report["candidates"][0]
            if ai_trade_candidate_accepted(canonical, candidate):
                candidate = mark_ai_trade_accepted(candidate)
                proposals.append(candidate)
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
    if not nets or min(nets) < -6.5 or sum(nets) < 4.0:
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
        if float(evaluation.get("net_value") or 0.0) >= -6.5:
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
    proposal_payload = proposal.get("proposal") or proposal
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
        for asset in proposal_payload.get("to_assets", []):
            if asset.get("kind") == "player":
                save.setdefault("roster_overrides", {})[asset["id"]] = from_team_id
            if asset.get("kind") == "pick":
                save.setdefault("draft_pick_overrides", {})[asset["id"]] = from_team_id
        from .save import add_news

        add_news(save, "trade", trade_headline_from_payload(proposal_payload), date_value=date)
        queue_press_event_if_user_involved(save, "trade", trade_headline_from_payload(proposal_payload), [from_team_id, to_team_id], date)
    save.setdefault("transaction_logs", []).append(to_plain(log))
    save["pending_trade_proposals"] = [
        item
        for item in save.get("pending_trade_proposals", [])
        if (item.get("proposal", {}).get("id") or item.get("id")) != proposal_id
    ]
    from .save import write_save

    write_save(path, save)
    return {"status": "applied", "save": str(path), "transaction_log": to_plain(log)}


def queue_press_event_if_user_involved(save: dict[str, Any], kind: str, headline: str, team_ids: list[str | None], date: str) -> None:
    user_team_id = save.get("meta", {}).get("user_team_id")
    if not user_team_id or user_team_id not in set(team_ids):
        return
    event = {
        "id": stable_id("press_event", kind, headline, date),
        "date": date,
        "kind": kind,
        "headline": headline,
        "question": f"You just made this move: {headline}. Was this about fit, money, timeline, or pressure?",
        "status": "pending",
    }
    save.setdefault("pending_press_events", [])
    if event["id"] not in {item.get("id") for item in save["pending_press_events"]}:
        save["pending_press_events"].append(event)


def trade_headline_from_payload(proposal: dict[str, Any]) -> str:
    from_assets = ", ".join(asset.get("label") or asset.get("name") or asset.get("id", "") for asset in proposal.get("from_assets", [])) or "assets"
    to_assets = ", ".join(asset.get("label") or asset.get("name") or asset.get("id", "") for asset in proposal.get("to_assets", [])) or "assets"
    return f"Trade completed: {from_assets} for {to_assets}."


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
    if transaction_context_is_complete(canonical):
        return canonical
    context = build_transaction_context(canonical, config)
    return {**canonical, **context}


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


def find_selling_candidates(canonical: dict[str, Any], user_team: dict[str, Any], target: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    candidates = []
    for buyer in buyer_teams_for_player(canonical, target):
        if buyer["id"] == user_team["id"]:
            continue
        for buyer_assets in buyer_offer_packages(canonical, buyer, user_team, target, seed)[:4]:
            report = evaluate_trade(canonical, user_team["abbrev"], buyer["abbrev"], [{"kind": "player", "value": target["name"]}], buyer_assets, seed=seed)
            candidates.append(candidate_from_evaluation(canonical, report))
    return candidates


def find_buying_candidates(canonical: dict[str, Any], user_team: dict[str, Any], target: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    target_team = team_by_id(canonical, target["team_id"])
    candidates = []
    for package in buyer_offer_packages(canonical, user_team, target_team, target, seed):
        report = evaluate_trade(canonical, user_team["abbrev"], target_team["abbrev"], package, [{"kind": "player", "value": target["name"]}], seed=seed)
        candidates.append(candidate_from_evaluation(canonical, report))
    return candidates


def buyer_offer_assets(canonical: dict[str, Any], buyer: dict[str, Any], seller: dict[str, Any], target: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    packages = buyer_offer_packages(canonical, buyer, seller, target, seed)
    return packages[0] if packages else []


def buyer_offer_packages(canonical: dict[str, Any], buyer: dict[str, Any], seller: dict[str, Any], target: dict[str, Any], seed: int) -> list[list[dict[str, Any]]]:
    valuations = {value["player_id"]: value for value in canonical["player_asset_valuations"]}
    target_value = valuations.get(target["id"], fallback_asset_valuation(target))["player_value"]
    target_salary = current_salary(contract_for_player(canonical, target["id"]))
    return buyer_offer_packages_for_value(canonical, buyer, seller, target_value, target_salary, seed, {target["id"]})


def buyer_offer_packages_for_value(
    canonical: dict[str, Any],
    buyer: dict[str, Any],
    seller: dict[str, Any],
    target_value: float,
    target_salary: float | None,
    seed: int,
    excluded_player_ids: set[str] | None = None,
) -> list[list[dict[str, Any]]]:
    excluded_player_ids = excluded_player_ids or set()
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
    for player in candidates:
        value = float(valuations.get(player["id"], fallback_asset_valuation(player))["player_value"])
        block_score = float(block.get(player["id"], {}).get("block_score") or 0.0)
        if value >= 72 and target_value < 70:
            continue
        if value >= 58 and block_score < 55 and target_value < 68:
            continue
        if value > target_value * (1.08 if target_value >= 70 else 1.24):
            continue
        tradable_players.append(player)
    tradable_players = tradable_players[:8]
    picks = sorted(
        [pick for pick in canonical.get("draft_picks", []) if pick.get("current_owner_team_id") == buyer["id"]],
        key=lambda pick: (pick_asset_value(pick, "neutral"), -int(pick.get("round") or 2), str(pick.get("season") or "")),
        reverse=True,
    )[:5]
    pick_variants = [()]
    pick_variants.extend((pick,) for pick in picks[:3])
    if len(picks) >= 2:
        pick_variants.append((picks[0], picks[1]))
    packages: list[tuple[float, list[dict[str, Any]]]] = []
    for player_count in range(1, min(3, len(tradable_players)) + 1):
        for player_group in combinations(tradable_players, player_count):
            player_assets = [{"kind": "player", "value": player["name"]} for player in player_group]
            player_salary = sum(current_salary(contract_for_player(canonical, player["id"])) or 0.0 for player in player_group)
            for pick_group in pick_variants:
                if len(player_assets) + len(pick_group) > 4:
                    continue
                assets = [*player_assets, *[{"kind": "pick", "value": pick["id"]} for pick in pick_group]]
                rough_value = sum(offer_player_rough_value(canonical, player, target_value, target_salary, valuations) for player in player_group)
                rough_value += sum(pick_asset_value(pick, "neutral") for pick in pick_group)
                if rough_value < target_value * (0.42 if target_value >= 56 else 0.48) or rough_value > target_value * 1.34 + 10:
                    continue
                salary_gap = abs(player_salary - (target_salary or player_salary)) / 1_000_000
                complexity_cost = max(0, len(assets) - 2) * (0.15 if target_value >= 56 else 0.55)
                packages.append((abs(rough_value - target_value) + salary_gap * 0.22 + complexity_cost, assets))
    unique: list[list[dict[str, Any]]] = []
    seen: set[str] = set()
    for _, assets in sorted(packages, key=lambda item: (item[0], json.dumps(item[1], sort_keys=True))):
        key = json.dumps(assets, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(assets)
        if len(unique) >= 10:
            break
    return unique


def offer_player_rough_value(
    canonical: dict[str, Any],
    player: dict[str, Any],
    target_value: float,
    target_salary: float | None,
    valuations: dict[str, dict[str, Any]],
) -> float:
    value = float(valuations.get(player["id"], fallback_asset_valuation(player))["player_value"])
    salary = current_salary(contract_for_player(canonical, player["id"])) or 0.0
    filler = target_salary is not None and target_salary >= 8_000_000 and salary >= 5_000_000 and value < target_value * 0.55
    if filler:
        value *= 0.72
    elif target_value >= 56 and value < target_value * 0.62:
        value *= 0.88
    return value


def asset_package_value(canonical: dict[str, Any], assets: list[dict[str, Any]], phase: str = "neutral") -> float:
    values = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
    total = 0.0
    for asset in assets:
        if asset.get("kind") == "player":
            player = player_by_id(canonical, asset.get("id"))
            total += float(values.get(asset.get("id"), fallback_asset_valuation(player)).get("player_value") or 0.0)
        elif asset.get("kind") == "pick":
            total += pick_asset_value(pick_by_id(canonical, asset.get("id")), phase)
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
    if non_user_evals and not any(item.get("accepted") or float(item.get("net_value") or 0) >= -1.0 for item in non_user_evals):
        return False
    user_eval = next((item for item in evaluations if item.get("perspective_team_id") == user_team_id), {})
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
            total += float(values.get(asset.get("id"), fallback_asset_valuation(player)).get("player_value") or 0.0)
        elif asset.get("kind") == "pick":
            total += pick_asset_value(pick_by_id(canonical, asset.get("id")), state.get("phase", "balanced"))
    return total


def max_player_value(canonical: dict[str, Any], assets: list[dict[str, Any]]) -> float:
    values = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
    return max(
        [
            float(values.get(asset.get("id"), fallback_asset_valuation(player_by_id(canonical, asset.get("id")))).get("player_value") or 0.0)
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
            player_value = float(valuation.get("player_value") or 0.0)
            fit = team_fit_for_player(player, valuation, state) if player and state else 0.0
            multiplier = multipliers.get(asset.get("id"), 1.0)
            pieces["player_quality"] += player_value
            pieces["role_value"] += (player_value + fit) * (multiplier - 1.0)
            pieces["age_timeline"] += float(valuation.get("age_curve") or 0.0) * 0.22
            pieces["contract"] += float(valuation.get("contract_surplus") or 0.0) * 0.34
            if player and state:
                pieces["lineup_fit"] += fit * 1.4
            pieces["health"] -= max(0.0, float(valuation.get("health_risk") or 0.0) - 45.0) * 0.08
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
    for team_id, assets in [(proposal.from_team_id, proposal.from_assets), (proposal.to_team_id, proposal.to_assets)]:
        for asset in assets:
            if asset["kind"] == "player":
                player = player_by_id(canonical, asset["id"])
                if not player or player["team_id"] != team_id:
                    issues.append(f"{asset.get('label', asset.get('id'))} is not on {team_by_id(canonical, team_id)['abbrev']}.")
                salary = current_salary(contract_for_player(canonical, asset["id"]))
                if salary is None:
                    manual.append(f"{asset.get('label', asset.get('id'))} has unresolved salary.")
            elif asset["kind"] == "pick":
                pick = pick_by_id(canonical, asset["id"])
                if not pick or pick.get("current_owner_team_id") != team_id:
                    issues.append(f"Pick {asset.get('id')} is not owned by {team_by_id(canonical, team_id)['abbrev']}.")
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
            normalized.append({"kind": "player", "id": player["id"], "label": player["name"]})
        elif kind == "pick":
            pick = pick_by_id(canonical, str(value))
            if not pick:
                raise ValueError(f"No pick found with id {value!r}")
            normalized.append({"kind": "pick", "id": pick["id"], "label": pick_label(canonical, pick)})
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
    risk = max(0.0, 65 - durability) * 0.5
    if profile.get("injury_prone"):
        risk += 6.5
    risk += min(6.0, len(profile.get("major_prior_injuries") or []) * 2.2)
    risk += min(3.0, len(profile.get("body_area_risk_tags") or []) * 0.45)
    if state.get("availability_status") != "active":
        risk += 12.0
    risk += float(state.get("rust") or 0) * 0.08
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
    picks = [pick for pick in canonical.get("draft_picks", []) if pick.get("current_owner_team_id") == team_id]
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
    thresholds = config.get("phase_thresholds", {})
    if "contending_with_future" in timeline:
        return "contending_with_future_upside"
    if "contending" in timeline:
        if youth >= float(thresholds.get("high_youth_pipeline", 45)):
            return "contending_with_future_upside"
        return "contending"
    if "rebuild" in timeline:
        return "rebuilding"
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
    if valuation.health_risk >= 12 and state.phase in {"contending", "contending_with_future_upside"}:
        score += 9
        reasons.append("health_risk_for_win_now_team")
    if age <= 24 and valuation.development_upside >= 8 and float(player.get("minutes_projection") or 0) < 12:
        score += 8
        reasons.append("blocked_prospect")
        preferred.append("clearer_development_path")
    if valuation.player_value >= 72 and state.phase not in {"rebuilding"}:
        score -= 62
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
    if "playoff_rotation" in state.get("needs", []) and valuation["playoff_value"] >= 62:
        fit += 4
    if "youth_and_picks" in state.get("needs", []) and (maybe_float(player.get("age")) or 30) <= 24:
        fit += 5
    if "shooting" in state.get("needs", []) and valuation["portability"] >= 64:
        fit += 2
    if state.get("phase") in {"contending", "contending_with_future_upside"} and valuation["player_value"] >= 45:
        fit += 3
    if state.get("phase") == "rebuilding" and (maybe_float(player.get("age")) or 30) >= 30:
        fit -= 4
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
            adjusted = (value["player_value"] + team_fit_for_player(player, value, state)) * multiplier
            player_adjusted_values.append(adjusted)
            total += adjusted
        elif asset["kind"] == "pick":
            pick = pick_by_id(canonical, asset["id"])
            total += pick_asset_value(pick, state["phase"])
    return total + package_concentration_adjustment(player_adjusted_values)


def package_concentration_adjustment(player_values: list[float]) -> float:
    if len(player_values) <= 1:
        return 0.0
    values = sorted([max(0.0, value) for value in player_values], reverse=True)
    top = values[0]
    low_role_count = sum(1 for value in values[1:] if value < 24.0)
    redundancy_penalty = low_role_count * 3.2
    if top >= 58.0:
        redundancy_penalty += max(0, len(values) - 2) * 1.6
    if top < 42.0 and len(values) >= 3:
        redundancy_penalty += 5.0
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
        minute_weight = (max(2.0, expected_minutes) / 28.0) ** 1.55
        output[player_id] = round(clamp(minute_weight, 0.18, 1.2), 3)
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
        return 19.0
    if rank <= 9:
        return 11.0
    if rank <= 12:
        return 6.0
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
        if asset["kind"] == "player":
            valuation = next(item for item in canonical["player_asset_valuations"] if item["player_id"] == asset["id"])
            if state["phase"] in {"contending", "contending_with_future_upside"} and valuation["playoff_value"] >= 64:
                adjustment += float(config.get("decision", {}).get("contender_need_bonus", 5.5))
    for asset in outgoing:
        if asset["kind"] == "pick" and state["phase"] in {"contending", "contending_with_future_upside"}:
            adjustment -= 1.5
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
    if to_out > floor and to_out > from_out * multiplier + plus:
        return f"{team_by_id(canonical, proposal.from_team_id)['abbrev']} incoming salary exceeds practical matching tolerance."
    if from_out > floor and from_out > to_out * multiplier + plus:
        return f"{team_by_id(canonical, proposal.to_team_id)['abbrev']} incoming salary exceeds practical matching tolerance."
    for team_id, outgoing, incoming in [
        (proposal.from_team_id, proposal.from_assets, proposal.to_assets),
        (proposal.to_team_id, proposal.to_assets, proposal.from_assets),
    ]:
        current_total = team_current_salary_total(canonical, team_id)
        outgoing_salary = package_salary(canonical, outgoing) or 0.0
        incoming_salary = package_salary(canonical, incoming) or 0.0
        after_total = current_total - outgoing_salary + incoming_salary
        if after_total > SECOND_APRON and after_total > current_total + 250_000:
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
    round_no = int(pick.get("round") or 2)
    if round_no == 1:
        if pick.get("status") == "verified_2026_draft_board" and pick.get("id", "").split("-"):
            try:
                pick_no = int(pick["id"].split("-")[2])
            except (ValueError, IndexError):
                pick_no = 18
            value = clamp(72 - pick_no * 1.35, 26, 72)
        else:
            value = 38.0
    else:
        value = 8.0
    if pick.get("protections"):
        value -= 4.0
    if phase in {"rebuilding", "developing"}:
        value *= 1.18
    if phase in {"contending", "contending_with_future_upside"}:
        value *= 0.88
    return round(clamp(value, 1, 80), 2)


def best_tradeable_pick(canonical: dict[str, Any], team_id: str) -> dict[str, Any] | None:
    picks = [pick for pick in canonical.get("draft_picks", []) if pick.get("current_owner_team_id") == team_id and int(pick.get("round") or 0) == 1]
    if not picks:
        picks = [pick for pick in canonical.get("draft_picks", []) if pick.get("current_owner_team_id") == team_id]
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
    owner = team_by_id(canonical, pick["current_owner_team_id"])["abbrev"] if pick.get("current_owner_team_id") else "UNK"
    original = team_by_id(canonical, pick["original_team_id"])["abbrev"] if pick.get("original_team_id") else "UNK"
    return f"{pick['season']} R{pick['round']} {original} pick owned by {owner}"


def proposal_summary(canonical: dict[str, Any], proposal: dict[str, Any]) -> str:
    from_team = team_by_id(canonical, proposal["from_team_id"])["abbrev"]
    to_team = team_by_id(canonical, proposal["to_team_id"])["abbrev"]
    from_assets = ", ".join(asset.get("label", asset["id"]) for asset in proposal["from_assets"])
    to_assets = ", ".join(asset.get("label", asset["id"]) for asset in proposal["to_assets"])
    return f"{from_team} sends {from_assets or 'nothing'} to {to_team}; {to_team} sends {to_assets or 'nothing'} to {from_team}."


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
