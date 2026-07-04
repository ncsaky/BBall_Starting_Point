from __future__ import annotations

import json
import random
from pathlib import Path
from statistics import median
from typing import Any

from .schema import (
    CANONICAL_START_DATE,
    ContractNegotiation,
    ContractOffer,
    ExtensionCandidate,
    FreeAgentCandidate,
    PlayerContractMarketProfile,
    PlayerContractPreference,
    SigningDecision,
    TransactionLog,
    to_plain,
)
from .transactions import (
    compact_player,
    contract_active_season,
    contract_for_player,
    current_salary,
    deep_merge,
    player_by_id,
    player_position_bucket,
    resolve_player,
    resolve_team,
    salary_posture,
    team_by_id,
    team_fit_for_player,
    with_transaction_context,
)
from .utils import clamp, maybe_float, stable_id


CONTRACT_MARKET_CONFIG_FILE = Path("data/overrides/contract_market_config.json")


def default_contract_market_config() -> dict[str, Any]:
    return {
        "version": "contract_market_ai_v1",
        "salary": {
            "minimum_salary": 1_200_000,
            "soft_cap": 154_000_000,
            "tax_line": 188_000_000,
            "midlevel_exception": 14_200_000,
        },
        "role_tier_caps": {
            "franchise_anchor": 62_000_000,
            "all_star_core": 52_000_000,
            "legacy_star": 50_000_000,
            "elite_specialist": 32_000_000,
            "high_end_starter": 38_000_000,
            "starter": 27_000_000,
            "rotation": 16_000_000,
            "depth": 6_000_000,
        },
        "years": {
            "extension_max_years": 5,
            "external_max_years": 4,
            "older_player_age": 34,
            "major_health_risk": 10,
        },
        "negotiation": {
            "player_acceptance_threshold": 68,
            "team_acceptance_threshold": 54,
            "counter_step": 0.32,
            "initial_offer_floor": 0.72,
            "max_bad_gm_overpay_multiplier": 1.11,
        },
        "notes": "Practical contract market and negotiation config. V1 uses salary comps and NBA-style guardrails without complete CBA exception/apron modeling.",
    }


def load_contract_market_config(root: str | Path = ".") -> dict[str, Any]:
    config = default_contract_market_config()
    path = Path(root) / CONTRACT_MARKET_CONFIG_FILE
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            config = deep_merge(config, json.load(handle))
    return config


def build_contract_ai_context(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_transaction_context(canonical)
    config = config or default_contract_market_config()
    market_profiles = build_player_contract_market_profiles(canonical, config)
    preferences = build_player_contract_preferences(canonical, market_profiles, config)
    working = {
        **canonical,
        "player_contract_market_profiles": [to_plain(profile) for profile in market_profiles],
        "player_contract_preferences": [to_plain(preference) for preference in preferences],
    }
    extension_candidates = build_extension_candidates(working, market_profiles, config)
    free_agent_candidates = build_free_agent_candidates(working, market_profiles, config)
    return {
        "player_contract_market_profiles": [to_plain(profile) for profile in market_profiles],
        "player_contract_preferences": [to_plain(preference) for preference in preferences],
        "extension_candidates": [to_plain(candidate) for candidate in extension_candidates],
        "free_agent_candidates": [to_plain(candidate) for candidate in free_agent_candidates],
    }


def with_contract_context(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_transaction_context(canonical)
    if (
        canonical.get("player_contract_market_profiles")
        and canonical.get("player_contract_preferences")
        and canonical.get("extension_candidates") is not None
        and canonical.get("free_agent_candidates") is not None
    ):
        return canonical
    return {**canonical, **build_contract_ai_context(canonical, config)}


def build_player_contract_market_profiles(canonical: dict[str, Any] | Any, config: dict[str, Any] | None = None) -> list[PlayerContractMarketProfile]:
    canonical = with_transaction_context(canonical)
    config = config or default_contract_market_config()
    from .sim import player_feature_vector

    valuations = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
    output: list[PlayerContractMarketProfile] = []
    for player in canonical.get("players", []):
        valuation = valuations.get(player["id"]) or fallback_player_valuation(player)
        features = player_feature_vector(canonical, player).features
        contract = contract_for_player(canonical, player["id"]) or {}
        role_tier = contract_role_tier(player, valuation, features)
        comp_player_ids, comp_summary = contract_comps(canonical, player, valuation, role_tier)
        model_aav = model_expected_aav(player, valuation, features, contract, role_tier, config)
        if comp_summary["comp_count"] >= 3:
            expected = model_aav * 0.74 + float(comp_summary["median_aav"]) * 0.26
        else:
            expected = model_aav
        expected = clamp_salary_to_role(expected, role_tier, config)
        preferred_years, max_years = preferred_contract_years(player, valuation, role_tier, config)
        confidence = market_confidence(player, valuation, comp_summary, contract)
        range_width = 0.18 + (1.0 - confidence) * 0.18
        low = max(float(config["salary"]["minimum_salary"]), expected * (1 - range_width))
        high = clamp_salary_to_role(expected * (1 + range_width), role_tier, config)
        asking = clamp_salary_to_role(expected * asking_multiplier(player, valuation, role_tier), role_tier, config)
        minimum = max(float(config["salary"]["minimum_salary"]), expected * minimum_multiplier(player, valuation, role_tier))
        output.append(
            PlayerContractMarketProfile(
                id=stable_id("contract_market", player["id"]),
                player_id=player["id"],
                team_id=player["team_id"],
                role_tier=role_tier,
                market_aav_low=round(low, 2),
                market_aav_high=round(max(high, low), 2),
                expected_aav=round(expected, 2),
                asking_aav=round(max(asking, low), 2),
                minimum_aav=round(min(minimum, asking), 2),
                preferred_years=preferred_years,
                max_years=max_years,
                comp_player_ids=comp_player_ids,
                comp_summary=comp_summary,
                confidence=confidence,
                source_ids=["src_contract_market_config_v1", "src_transaction_model_config_v1", *list(contract.get("source_ids") or [])],
                notes="Contract market v1 estimate from startup salary comps, asset valuation, role tier, age curve, health risk, upside, scarcity, and current-contract anchor.",
            )
        )
    return sorted(output, key=lambda item: item.player_id)


def build_player_contract_preferences(
    canonical: dict[str, Any] | Any,
    market_profiles: list[PlayerContractMarketProfile] | None = None,
    config: dict[str, Any] | None = None,
) -> list[PlayerContractPreference]:
    canonical = with_transaction_context(canonical)
    market_profiles = market_profiles or build_player_contract_market_profiles(canonical, config)
    profiles = {profile.player_id: profile for profile in market_profiles}
    valuations = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
    output: list[PlayerContractPreference] = []
    for player in canonical.get("players", []):
        valuation = valuations.get(player["id"]) or fallback_player_valuation(player)
        profile = profiles[player["id"]]
        age = maybe_float(player.get("age")) or 27.0
        current = maybe_float(valuation.get("current_salary"))
        role = profile.role_tier
        archetype = contract_preference_archetype(player, valuation, role)
        priorities = {
            "money": 62.0,
            "role": 58.0,
            "winning": 55.0,
            "security": 58.0,
            "loyalty": 50.0,
            "market": 48.0,
            "patience": 54.0,
            "fit": 56.0,
        }
        if role in {"franchise_anchor", "all_star_core", "legacy_star"}:
            priorities["money"] += 12
            priorities["role"] += 10
            priorities["winning"] += 8
            priorities["market"] += 7
        if role == "elite_specialist":
            priorities["winning"] += 12
            priorities["fit"] += 8
            priorities["role"] -= 5
        if age <= 24:
            priorities["security"] += 12
            priorities["role"] += 8
            priorities["winning"] -= 5
            priorities["patience"] += 5
        if age >= 33:
            priorities["winning"] += 13
            priorities["security"] -= 8
            priorities["patience"] -= 5
        if current and current >= 30_000_000:
            priorities["money"] += 5
            priorities["market"] += 4
        deterministic = deterministic_rating_shift(player["id"], "contract_preferences")
        for idx, key in enumerate(priorities):
            priorities[key] = round(clamp(priorities[key] + deterministic[idx % len(deterministic)], 1, 99), 2)
        output.append(
            PlayerContractPreference(
                id=stable_id("contract_preference", player["id"]),
                player_id=player["id"],
                archetype=archetype,
                priorities=priorities,
                confidence=0.46,
                source_ids=["src_contract_market_config_v1"],
                notes="Deterministic inferred player-agency profile for negotiation logic. Public personality research is intentionally deferred in v1.",
            )
        )
    return sorted(output, key=lambda item: item.player_id)


def build_extension_candidates(
    canonical: dict[str, Any] | Any,
    market_profiles: list[PlayerContractMarketProfile] | None = None,
    config: dict[str, Any] | None = None,
) -> list[ExtensionCandidate]:
    canonical = with_transaction_context(canonical)
    market_profiles = market_profiles or build_player_contract_market_profiles(canonical, config)
    profiles = {profile.player_id: profile for profile in market_profiles}
    valuations = {value["player_id"]: value for value in canonical.get("player_asset_valuations", [])}
    output: list[ExtensionCandidate] = []
    for player in canonical.get("players", []):
        contract = contract_for_player(canonical, player["id"]) or {}
        profile = profiles[player["id"]]
        valuation = valuations.get(player["id"]) or fallback_player_valuation(player)
        remaining = salary_seasons_remaining(contract)
        manual = contract_needs_manual_review(contract)
        original_years = int(contract.get("original_contract_years") or 0)
        eligible = not manual and player.get("team_id") is not None and original_years >= 3 and 1 <= remaining <= 3
        if manual:
            status = "manual_review_required"
        elif original_years < 3:
            status = "original_contract_shorter_than_three_years"
        elif remaining > 3:
            status = "not_in_extension_window"
        elif remaining < 1:
            status = "no_salary_seasons_remaining"
        elif eligible:
            status = "eligible_extension_window"
        else:
            status = "not_extension_eligible"
        priority_score, reasons = extension_priority_score(canonical, player, valuation, profile, eligible, manual)
        output.append(
            ExtensionCandidate(
                id=stable_id("extension_candidate", player["team_id"], player["id"]),
                player_id=player["id"],
                team_id=player["team_id"],
                eligible=eligible,
                eligibility_status=status,
                years_remaining=remaining,
                current_salary=current_salary(contract),
                projected_aav=profile.expected_aav,
                projected_years=profile.preferred_years,
                priority=extension_priority_label(priority_score, manual, eligible),
                manual_review_required=manual,
                reasons=reasons,
                confidence=round(min(profile.confidence, 0.7 if eligible else 0.48), 3),
                source_ids=["src_contract_market_config_v1", *list(contract.get("source_ids") or [])],
                notes="Extension candidate v1 uses practical remaining-years/options heuristics rather than full CBA eligibility.",
            )
        )
    return sorted(output, key=lambda item: (item.priority, item.projected_aav, item.player_id), reverse=True)


def build_free_agent_candidates(
    canonical: dict[str, Any] | Any,
    market_profiles: list[PlayerContractMarketProfile] | None = None,
    config: dict[str, Any] | None = None,
) -> list[FreeAgentCandidate]:
    canonical = with_transaction_context(canonical)
    market_profiles = market_profiles or build_player_contract_market_profiles(canonical, config)
    profiles = {profile.player_id: profile for profile in market_profiles}
    output: list[FreeAgentCandidate] = []
    for player in canonical.get("players", []):
        contract = contract_for_player(canonical, player["id"]) or {}
        free_agency_type = free_agency_type_for_contract(player, contract)
        if free_agency_type == "not_projected_2026_free_agent":
            continue
        profile = profiles[player["id"]]
        manual = contract_needs_manual_review(contract)
        suitors = likely_suitors_for_player(canonical, player, profile, limit=6)
        output.append(
            FreeAgentCandidate(
                id=stable_id("free_agent_candidate", player["id"]),
                player_id=player["id"],
                current_team_id=player["team_id"],
                free_agency_type=free_agency_type,
                market_tier=profile.role_tier,
                projected_aav=profile.expected_aav,
                projected_years=profile.preferred_years,
                likely_suitors=[team["id"] for team in suitors],
                manual_review_required=manual,
                confidence=round(min(profile.confidence, 0.72), 3),
                source_ids=["src_contract_market_config_v1", *list(contract.get("source_ids") or [])],
                notes="Projected 2026 free-agent candidate from expiring/options-style contract signals. Restricted FA and exact cap holds are deferred.",
            )
        )
    return sorted(output, key=lambda item: (item.projected_aav, item.player_id), reverse=True)


def contract_market_report(canonical: dict[str, Any] | Any, player_name: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_contract_context(canonical, config)
    player = resolve_player(canonical, player_name)
    profile = next(item for item in canonical["player_contract_market_profiles"] if item["player_id"] == player["id"])
    preference = next(item for item in canonical["player_contract_preferences"] if item["player_id"] == player["id"])
    valuation = valuation_for_player(canonical, player)
    extension = next((item for item in canonical["extension_candidates"] if item["player_id"] == player["id"]), None)
    free_agent = next((item for item in canonical["free_agent_candidates"] if item["player_id"] == player["id"]), None)
    comp_players = [compact_player(player_by_id(canonical, player_id)) for player_id in profile["comp_player_ids"] if player_by_id(canonical, player_id)]
    return {
        "player": compact_player(player),
        "market_profile": profile,
        "preference": preference,
        "asset_valuation": valuation,
        "current_contract": contract_for_player(canonical, player["id"]),
        "extension_candidate": extension,
        "free_agent_candidate": free_agent,
        "comp_players": comp_players,
        "notes": "AAV values are dollars. The market range is a negotiation input, not a legal cap calculation.",
    }


def extension_candidates_report(canonical: dict[str, Any] | Any, team_query: str | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    canonical = with_contract_context(canonical, config)
    team = resolve_team(canonical, team_query) if team_query else None
    players = {player["id"]: player for player in canonical["players"]}
    candidates = canonical["extension_candidates"]
    if team:
        candidates = [candidate for candidate in candidates if candidate["team_id"] == team["id"]]
    candidates = sorted(candidates, key=lambda item: (priority_rank(item["priority"]), item["projected_aav"]), reverse=True)
    return {
        "team": team,
        "candidate_count": len(candidates),
        "candidates": [
            {
                **compact_player(players[candidate["player_id"]]),
                **candidate,
                "projected_aav_millions": round(candidate["projected_aav"] / 1_000_000, 2),
            }
            for candidate in candidates
        ],
    }


def free_agents_report(
    canonical: dict[str, Any] | Any,
    team_query: str | None = None,
    position: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = with_contract_context(canonical, config)
    team = resolve_team(canonical, team_query) if team_query else None
    players = {player["id"]: player for player in canonical["players"]}
    candidates = canonical["free_agent_candidates"]
    if position:
        pos = position.strip().upper()
        candidates = [candidate for candidate in candidates if pos in str(players[candidate["player_id"]].get("position") or "").upper()]
    entries = []
    for candidate in candidates:
        player = players[candidate["player_id"]]
        fit = signing_fit_score(canonical, team["id"], player, valuation_for_player(canonical, player)) if team else None
        entries.append(
            {
                **compact_player(player),
                **candidate,
                "team_fit_score": round(fit, 2) if fit is not None else None,
                "likely_suitors_abbrev": [team_by_id(canonical, team_id)["abbrev"] for team_id in candidate.get("likely_suitors", [])],
                "projected_aav_millions": round(candidate["projected_aav"] / 1_000_000, 2),
            }
        )
    entries = sorted(entries, key=lambda item: (item["team_fit_score"] if item["team_fit_score"] is not None else 0, item["projected_aav"]), reverse=True)
    return {"team": team, "position": position, "candidate_count": len(entries), "candidates": entries}


def negotiate_extension(
    canonical: dict[str, Any] | Any,
    player_name: str,
    team_query: str,
    seed: int = 1,
    max_rounds: int = 3,
    date: str = CANONICAL_START_DATE,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = with_contract_context(canonical, config)
    config = config or default_contract_market_config()
    player = resolve_player(canonical, player_name)
    team = resolve_team(canonical, team_query)
    if player["team_id"] != team["id"]:
        raise ValueError("Extensions can only be negotiated with the player's current team in v1.")
    candidate = next(item for item in canonical["extension_candidates"] if item["player_id"] == player["id"])
    negotiation_id = stable_id("contract_negotiation", "extension", date, team["id"], player["id"], seed, max_rounds)
    if not candidate["eligible"] or candidate["manual_review_required"]:
        negotiation = ContractNegotiation(
            id=negotiation_id,
            negotiation_type="extension",
            player_id=player["id"],
            team_id=team["id"],
            date=date,
            seed=seed,
            rounds=0,
            player_ask=extension_player_ask(canonical, player, team, config),
            team_walkaway={"status": "not_computed"},
            offers=[],
            final_decision_id=None,
            status=candidate["eligibility_status"],
            source_ids=["src_contract_market_config_v1"],
            notes="Extension negotiation blocked by v1 eligibility/manual-review guardrails.",
        )
        payload = to_plain(negotiation)
        payload["current_contract_seasons"] = list((contract_for_player(canonical, player["id"]) or {}).get("seasons") or [])
        return {"negotiation": payload, "decision": None, "candidate": candidate, "accepted": False}
    return negotiate_contract(canonical, player, team, "extension", seed, max_rounds, date, config)


def evaluate_signing(
    canonical: dict[str, Any] | Any,
    player_name: str,
    team_query: str,
    years: int,
    aav: float,
    seed: int = 1,
    date: str = CANONICAL_START_DATE,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = with_contract_context(canonical, config)
    config = config or default_contract_market_config()
    player = resolve_player(canonical, player_name)
    team = resolve_team(canonical, team_query)
    annual_salary = normalize_aav(aav)
    negotiation_id = stable_id("contract_eval", "free_agent", date, team["id"], player["id"], years, round(annual_salary), seed)
    offer = contract_offer(
        negotiation_id,
        team["id"],
        player["id"],
        "free_agent_signing",
        1,
        years,
        annual_salary,
        role_promise_for_team(canonical, team["id"], player),
        "team_evaluated_offer",
        "User/AI supplied signing offer for v1 evaluation.",
    )
    legality = contract_legality(canonical, player, team, offer, "free_agent_signing", config)
    team_score = team_offer_score(canonical, player, team, offer, "free_agent_signing", seed, config)
    player_score, reasons = player_offer_score(canonical, player, team, offer, seed, config)
    decision = signing_decision_from_scores(legality, team_score, player_score, reasons, config)
    signing = SigningDecision(
        id=stable_id("signing_decision", negotiation_id, team["id"], player["id"]),
        negotiation_id=negotiation_id,
        player_id=player["id"],
        team_id=team["id"],
        accepted=decision["accepted"],
        decision=decision["decision"],
        accepted_offer=to_plain(offer) if decision["accepted"] else None,
        player_score=round(player_score, 3),
        team_score=round(team_score, 3),
        competing_offers=[],
        reasons=decision["reasons"],
        source_ids=["src_contract_market_config_v1"],
        notes=decision["notes"],
    )
    return {
        "offer": to_plain(offer),
        "legality": legality,
        "decision": to_plain(signing),
        "accepted_by_all": signing.accepted,
        "notes": "AAV input is interpreted as dollars when greater than one million, otherwise millions.",
    }


def simulate_free_agency(
    canonical: dict[str, Any] | Any,
    from_date: str,
    through_date: str,
    seed: int = 1,
    limit: int = 10,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = with_contract_context(canonical, config)
    config = config or default_contract_market_config()
    rng = random.Random(f"{seed}:{from_date}:{through_date}:free_agency")
    players = {player["id"]: player for player in canonical["players"]}
    candidates = sorted(canonical["free_agent_candidates"], key=lambda item: (item["projected_aav"], item["player_id"]), reverse=True)
    negotiations = []
    for candidate in candidates:
        player = players[candidate["player_id"]]
        negotiation_id = stable_id("contract_negotiation", "free_agent", from_date, through_date, player["id"], seed)
        suitors = [team_by_id(canonical, team_id) for team_id in candidate.get("likely_suitors", [])]
        rng.shuffle(suitors)
        offers = []
        for team in sorted(suitors[:5], key=lambda item: item["abbrev"]):
            offer = generate_team_offer(canonical, player, team, "free_agent_signing", seed, 1, config, negotiation_id=negotiation_id)
            legality = contract_legality(canonical, player, team, offer, "free_agent_signing", config)
            team_score = team_offer_score(canonical, player, team, offer, "free_agent_signing", seed, config)
            player_score, reasons = player_offer_score(canonical, player, team, offer, seed, config)
            offers.append({"offer": to_plain(offer), "legality": legality, "team_score": round(team_score, 3), "player_score": round(player_score, 3), "reasons": reasons})
        if not offers:
            continue
        viable = [offer for offer in offers if offer["legality"]["status"] == "legal" and offer["team_score"] >= float(config["negotiation"]["team_acceptance_threshold"])]
        chosen = max(viable or offers, key=lambda item: (item["player_score"], item["offer"]["annual_salary"], item["offer"]["years"]))
        decision = free_agency_decision(canonical, player, chosen, offers, seed, config, negotiation_id)
        negotiation = ContractNegotiation(
            id=negotiation_id,
            negotiation_type="free_agent_signing",
            player_id=player["id"],
            team_id=chosen["offer"]["team_id"],
            date=from_date,
            seed=seed,
            rounds=1,
            player_ask=free_agent_player_ask(canonical, player, config),
            team_walkaway={"multi_team_market": True},
            offers=[item["offer"] for item in offers],
            final_decision_id=decision.id,
            status="agreement" if decision.accepted else "unresolved_market",
            source_ids=["src_contract_market_config_v1"],
            notes="Deterministic v1 free-agency market simulation. Teams bid from fit, need, posture, and front-office personality; player picks by weighted priorities.",
        )
        negotiations.append({"negotiation": to_plain(negotiation), "decision": to_plain(decision), "accepted": decision.accepted})
        if len(negotiations) >= limit:
            break
    return {
        "from_date": from_date,
        "through_date": through_date,
        "seed": seed,
        "negotiation_count": len(negotiations),
        "negotiations": negotiations,
        "notes": "Generated agreements are not applied to canonical data. Use apply-contract against a save ledger after storing a pending negotiation.",
    }


def apply_contract_to_save(save_path: str | Path, negotiation_id: str, date: str = CANONICAL_START_DATE) -> dict[str, Any]:
    path = Path(save_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            save = json.load(handle)
    else:
        save = {"version": "save_transaction_ledger_v1", "pending_contract_negotiations": [], "transaction_logs": []}
    pending = save.get("pending_contract_negotiations", []) or save.get("pending_contracts", [])
    negotiation = next((item for item in pending if (item.get("negotiation", {}).get("id") or item.get("id")) == negotiation_id), None)
    if not negotiation:
        return {
            "status": "not_found",
            "negotiation_id": negotiation_id,
            "save": str(path),
            "notes": "No pending contract negotiation with this id exists in the save ledger.",
        }
    negotiation_payload = negotiation.get("negotiation") or negotiation
    decision = negotiation.get("decision")
    if decision and not decision.get("accepted"):
        return {
            "status": "not_applied",
            "negotiation_id": negotiation_id,
            "save": str(path),
            "notes": "The pending negotiation does not have an accepted signing decision.",
        }
    accepted_offer = (decision or {}).get("accepted_offer") or accepted_offer_from_negotiation(negotiation_payload)
    if accepted_offer:
        accepted_offer = dict(accepted_offer)
        accepted_offer.setdefault("original_contract_years", int(accepted_offer.get("years") or accepted_offer.get("term_years") or 1))
        accepted_offer.setdefault("signed_season", str(accepted_offer.get("start_season") or extension_start_season_from_date(date)))
    if accepted_offer and negotiation_payload.get("negotiation_type") == "extension":
        accepted_offer.setdefault("start_season", extension_start_season_from_date(date))
        accepted_offer.setdefault("team_id", negotiation_payload.get("team_id"))
        accepted_offer = merge_extension_offer_with_existing_contract(accepted_offer, negotiation_payload)
    log = TransactionLog(
        id=stable_id("transaction_log", "contract", negotiation_id, date),
        date=date,
        transaction_type=negotiation_payload.get("negotiation_type", "contract"),
        proposal_id=negotiation_id,
        status="applied_to_save_ledger",
        teams=[negotiation_payload.get("team_id")],
        assets={"player_id": negotiation_payload.get("player_id"), "contract": accepted_offer},
        evaluations=[decision] if decision else [],
        source_ids=["src_contract_market_config_v1"],
        notes="Contract applied to save ledger only. Canonical preseason data remains immutable.",
    )
    if save.get("version") == "league_save_v1":
        player_id = negotiation_payload.get("player_id")
        team_id = negotiation_payload.get("team_id")
        if player_id:
            save.setdefault("contract_overrides", {})[player_id] = accepted_offer
            if team_id and negotiation_payload.get("negotiation_type") in {"free_agency", "free_agent_signing"}:
                save.setdefault("roster_overrides", {})[player_id] = team_id
                save.setdefault("rotation_snapshots", {}).pop(team_id, None)
                if player_id in set(save.get("free_agent_player_ids", [])):
                    save["free_agent_player_ids"] = [item for item in save.get("free_agent_player_ids", []) if item != player_id]
                if save.get("re_signing_rights"):
                    save["re_signing_rights"] = [
                        item for item in save.get("re_signing_rights", [])
                        if not (item.get("player_id") == player_id and item.get("team_id") == team_id)
                    ]
        player_label = negotiation_payload.get("player_name") or negotiation_payload.get("player_id") or "Player"
        team_label = str(team_id or "").replace("team_", "").upper()
        transaction_kind = negotiation_payload.get("negotiation_type", "contract")
        if transaction_kind == "extension":
            from .save import extension_headline_with_terms

            headline = extension_headline_with_terms(team_label, player_label, accepted_offer)
        else:
            headline = f"{team_label} signs {player_label}."
        from .save import add_league_event, add_news

        add_news(save, transaction_kind, headline, date_value=date)
        annual_salary = float((accepted_offer or {}).get("annual_salary") or (accepted_offer or {}).get("salary") or 0.0)
        add_league_event(
            save,
            transaction_kind,
            headline,
            date_value=date,
            team_ids=[team_id],
            player_ids=[player_id],
            importance=0.74 if annual_salary > 25_000_000 else None,
            details={
                "player_id": player_id,
                "team_id": team_id,
                "contract": accepted_offer or {},
                "annual_salary": annual_salary,
                "aav_millions": round(annual_salary / 1_000_000, 2) if annual_salary else 0.0,
                "years": int((accepted_offer or {}).get("original_contract_years") or (accepted_offer or {}).get("years") or 0),
            },
        )
        queue_press_event_if_user_involved(
            save,
            transaction_kind,
            headline,
            [team_id],
            date,
        )
    save.setdefault("transaction_logs", []).append(to_plain(log))
    save["pending_contract_negotiations"] = [
        item for item in save.get("pending_contract_negotiations", []) if (item.get("negotiation", {}).get("id") or item.get("id")) != negotiation_id
    ]
    if "pending_contracts" in save:
        save["pending_contracts"] = [item for item in save.get("pending_contracts", []) if (item.get("negotiation", {}).get("id") or item.get("id")) != negotiation_id]
    from .save import write_save

    write_save(path, save)
    return {"status": "applied", "save": str(path), "transaction_log": to_plain(log)}


def queue_press_event_if_user_involved(save: dict[str, Any], kind: str, headline: str, team_ids: list[str | None], date: str) -> None:
    from .save import queue_aggregated_press_event

    queue_aggregated_press_event(save, kind, headline, team_ids, date)


def extension_start_season_from_date(date_value: str) -> str:
    try:
        year = int(str(date_value)[:4])
        month = int(str(date_value)[5:7])
    except (ValueError, TypeError):
        year = 2025
        month = 10
    start = year + 1 if month >= 7 else year
    return f"{start}-{str(start + 1)[-2:]}"


def merge_extension_offer_with_existing_contract(offer: dict[str, Any], negotiation_payload: dict[str, Any]) -> dict[str, Any]:
    start_season = str(offer.get("start_season") or extension_start_season_from_date(str(negotiation_payload.get("date") or CANONICAL_START_DATE)))
    requested_start_year = season_start_year_for_contract(start_season)
    existing_paid_years = [
        season_start_year_for_contract(str(season.get("season")))
        for season in negotiation_payload.get("current_contract_seasons", [])
        if season.get("season") and maybe_float(season.get("salary")) and maybe_float(season.get("salary")) > 0
    ]
    latest_existing_year = max(existing_paid_years, default=None)
    if latest_existing_year is not None and latest_existing_year >= requested_start_year:
        start_season = season_label_from_start_year(latest_existing_year + 1)
        offer["start_season"] = start_season
    current_seasons = [
        dict(season)
        for season in negotiation_payload.get("current_contract_seasons", [])
        if season.get("season") and season_start_year_for_contract(str(season.get("season"))) < season_start_year_for_contract(start_season)
    ]
    extension_seasons = offer_contract_seasons(offer, start_season, "extension")
    if current_seasons or extension_seasons:
        merged = {str(season.get("season")): season for season in current_seasons}
        for season in extension_seasons:
            merged[str(season.get("season"))] = season
        offer["seasons"] = [merged[key] for key in sorted(merged)]
        offer["original_contract_years"] = len(extension_seasons)
    return offer


def season_label_from_start_year(start: int) -> str:
    return f"{start}-{str(start + 1)[-2:]}"


def offer_contract_seasons(offer: dict[str, Any], start_season: str, guarantee_status: str) -> list[dict[str, Any]]:
    years = int(offer.get("years") or offer.get("term_years") or 1)
    annual = float(offer.get("annual_salary") or offer.get("salary") or offer.get("aav") or 0.0)
    if annual and annual < 1_000_000:
        annual *= 1_000_000
    try:
        start = int(start_season.split("-")[0])
    except (ValueError, AttributeError):
        start = 2026
    return [
        {
            "season": f"{start + offset}-{str(start + offset + 1)[-2:]}",
            "salary": int(round(annual)),
            "option_type": offer.get("option_type"),
            "guarantee_status": guarantee_status,
        }
        for offset in range(max(1, years))
    ]


def projected_retirement_start_year(player: dict[str, Any], active_start_year: int | None = None) -> int | None:
    age = maybe_float(player.get("display_age", player.get("age"))) or 27.0
    if age < 36:
        return None
    active_start_year = active_start_year or 2025
    digest = sum(ord(char) for char in str(player.get("id") or player.get("name") or "player"))
    if age >= 42:
        years_until = 1
    elif age >= 40:
        years_until = 3
    elif age >= 39:
        years_until = 2 + digest % 2
    elif age >= 38:
        years_until = 2 + digest % 2
    elif age >= 37:
        years_until = 3 + digest % 2
    else:
        years_until = 4 + digest % 2
    if display_minutes_for_contract(player) >= 24 and age < 40:
        years_until += 1
    return active_start_year + years_until


def display_minutes_for_contract(player: dict[str, Any]) -> float:
    return float(player.get("minutes_projection") or player.get("projected_minutes") or 0.0)


def negotiate_contract(
    canonical: dict[str, Any],
    player: dict[str, Any],
    team: dict[str, Any],
    negotiation_type: str,
    seed: int,
    max_rounds: int,
    date: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    negotiation_id = stable_id("contract_negotiation", negotiation_type, date, team["id"], player["id"], seed, max_rounds)
    player_ask = extension_player_ask(canonical, player, team, config) if negotiation_type == "extension" else free_agent_player_ask(canonical, player, config)
    walkaway = team_walkaway_offer(canonical, player, team, negotiation_type, seed, config)
    offers: list[dict[str, Any]] = []
    accepted_decision: SigningDecision | None = None
    current_salary = walkaway["initial_annual_salary"]
    for round_no in range(1, max(1, max_rounds) + 1):
        offer_salary = min(walkaway["max_annual_salary"], current_salary)
        offer_years = min(int(walkaway["max_years"]), int(player_ask["preferred_years"]))
        offer = contract_offer(
            negotiation_id,
            team["id"],
            player["id"],
            negotiation_type,
            round_no,
            offer_years,
            offer_salary,
            role_promise_for_team(canonical, team["id"], player),
            "counter_offer" if round_no > 1 else "opening_offer",
            contract_offer_notes(canonical, team["id"], player, offer_salary, walkaway),
        )
        legality = contract_legality(canonical, player, team, offer, negotiation_type, config)
        team_score = team_offer_score(canonical, player, team, offer, negotiation_type, seed, config)
        player_score, reasons = player_offer_score(canonical, player, team, offer, seed, config)
        offer_payload = {**to_plain(offer), "legality": legality, "team_score": round(team_score, 3), "player_score": round(player_score, 3), "player_reasons": reasons}
        offers.append(offer_payload)
        decision_info = signing_decision_from_scores(legality, team_score, player_score, reasons, config)
        if decision_info["accepted"]:
            accepted_decision = SigningDecision(
                id=stable_id("signing_decision", negotiation_id, team["id"], player["id"], round_no),
                negotiation_id=negotiation_id,
                player_id=player["id"],
                team_id=team["id"],
                accepted=True,
                decision="accept",
                accepted_offer=to_plain(offer),
                player_score=round(player_score, 3),
                team_score=round(team_score, 3),
                competing_offers=[],
                reasons=decision_info["reasons"],
                source_ids=["src_contract_market_config_v1"],
                notes=decision_info["notes"],
            )
            break
        current_salary += (walkaway["max_annual_salary"] - current_salary) * float(config["negotiation"]["counter_step"])
    if accepted_decision is None:
        last = offers[-1] if offers else {}
        accepted_decision = SigningDecision(
            id=stable_id("signing_decision", negotiation_id, team["id"], player["id"], "reject"),
            negotiation_id=negotiation_id,
            player_id=player["id"],
            team_id=team["id"],
            accepted=False,
            decision=last.get("legality", {}).get("status") if last.get("legality", {}).get("status") != "legal" else "walk_away",
            accepted_offer=None,
            player_score=round(float(last.get("player_score") or 0), 3),
            team_score=round(float(last.get("team_score") or 0), 3),
            competing_offers=[],
            reasons=list(last.get("player_reasons") or ["final_offer_below_acceptance_threshold"]),
            source_ids=["src_contract_market_config_v1"],
            notes="No agreement after deterministic v1 negotiation rounds.",
        )
    negotiation = ContractNegotiation(
        id=negotiation_id,
        negotiation_type=negotiation_type,
        player_id=player["id"],
        team_id=team["id"],
        date=date,
        seed=seed,
        rounds=len(offers),
        player_ask=player_ask,
        team_walkaway=walkaway,
        offers=offers,
        final_decision_id=accepted_decision.id,
        status="agreement" if accepted_decision.accepted else "no_agreement",
        source_ids=["src_contract_market_config_v1"],
        notes="Deterministic v1 negotiation with bounded front-office personality effects and inferred player priorities.",
    )
    payload = to_plain(negotiation)
    if negotiation_type == "extension":
        payload["current_contract_seasons"] = list((contract_for_player(canonical, player["id"]) or {}).get("seasons") or [])
    return {"negotiation": payload, "decision": to_plain(accepted_decision), "accepted": accepted_decision.accepted}


def contract_role_tier(player: dict[str, Any], valuation: dict[str, Any], features: dict[str, float]) -> str:
    minutes = float(player.get("minutes_projection") or 0)
    age = maybe_float(player.get("age")) or 27.0
    value = float(valuation.get("player_value") or 0)
    on_court = float(valuation.get("on_court_value") or 0)
    usage = float(features.get("usage") or 50)
    shot_creation = float(features.get("shot_creation") or 50)
    scoring_usage = float(features.get("scoring_usage") or usage)
    portability = float(valuation.get("portability") or 50)
    playoff = float(valuation.get("playoff_value") or 50)
    creator_star = usage >= 80 or shot_creation >= 68 or scoring_usage >= 70
    if minutes < 10:
        return "rotation" if on_court >= 58 and value >= 48 else "depth"
    if minutes < 18:
        if on_court >= 64 and (portability >= 78 or playoff >= 70):
            return "elite_specialist"
        return "rotation" if value >= 38 or float(valuation.get("development_upside") or 0) >= 6 else "depth"
    if age >= 36 and minutes >= 25 and (usage >= 72 or on_court >= 62):
        return "legacy_star"
    if value >= 84 and on_court >= 70 and minutes >= 28 and creator_star:
        return "franchise_anchor"
    if value >= 90 and minutes >= 28 and (creator_star or (age <= 21 and float(valuation.get("development_upside") or 0) >= 10)):
        return "franchise_anchor"
    if usage >= 78 and shot_creation >= 72 and minutes >= 28:
        return "franchise_anchor"
    if value >= 78 and on_court >= 65 and minutes >= 28 and creator_star:
        return "all_star_core"
    if on_court >= 66 and (minutes < 24 or not creator_star) and (portability >= 78 or playoff >= 70):
        return "elite_specialist"
    if on_court >= 61 and minutes >= 24:
        return "high_end_starter"
    if minutes >= 22 or on_court >= 54:
        return "starter"
    if minutes >= 12 or value >= 30:
        return "rotation"
    return "depth"


def contract_comps(canonical: dict[str, Any], player: dict[str, Any], valuation: dict[str, Any], role_tier: str) -> tuple[list[str], dict[str, Any]]:
    valuations = {item["player_id"]: item for item in canonical.get("player_asset_valuations", [])}
    player_age = maybe_float(player.get("age")) or 27.0
    player_minutes = float(player.get("minutes_projection") or 0)
    candidates: list[tuple[float, str, float]] = []
    for other in canonical.get("players", []):
        if other["id"] == player["id"]:
            continue
        other_value = valuations.get(other["id"])
        if not other_value:
            continue
        salary = current_salary(contract_for_player(canonical, other["id"]))
        if salary is None or salary < 1_000_000:
            continue
        other_age = maybe_float(other.get("age")) or 27.0
        other_minutes = float(other.get("minutes_projection") or 0)
        distance = abs(float(other_value["player_value"]) - float(valuation["player_value"])) * 1.1
        distance += abs(float(other_value["on_court_value"]) - float(valuation["on_court_value"])) * 0.65
        distance += abs(other_age - player_age) * 0.55
        distance += abs(other_minutes - player_minutes) * 0.16
        if role_tier in {"franchise_anchor", "all_star_core", "legacy_star"} and float(other_value["on_court_value"]) < 60:
            distance += 12
        candidates.append((distance, other["id"], salary))
    top = sorted(candidates, key=lambda item: (item[0], item[1]))[:8]
    salaries = [salary for _, _, salary in top]
    summary = {
        "comp_count": len(salaries),
        "median_aav": round(median(salaries), 2) if salaries else 0.0,
        "low_aav": round(min(salaries), 2) if salaries else 0.0,
        "high_aav": round(max(salaries), 2) if salaries else 0.0,
    }
    return [player_id for _, player_id, _ in top], summary


def model_expected_aav(
    player: dict[str, Any],
    valuation: dict[str, Any],
    features: dict[str, float],
    contract: dict[str, Any],
    role_tier: str,
    config: dict[str, Any],
) -> float:
    value_signal = float(valuation["player_value"]) * 0.56 + float(valuation["on_court_value"]) * 0.44
    minutes = float(player.get("minutes_projection") or 0)
    if minutes < 18:
        value_signal = min(value_signal, float(valuation["on_court_value"]) * 0.72 + 24 + minutes * 0.45 + float(valuation.get("development_upside") or 0) * 0.4)
    base_m = 1.2
    base_m += max(0.0, value_signal - 32) * 0.62
    base_m += max(0.0, float(features.get("usage") or 50) - 70) * 0.17
    base_m += max(0.0, float(valuation.get("role_scarcity") or 0)) * 0.24
    base_m += max(0.0, float(valuation.get("playoff_value") or 50) - 60) * 0.1
    base_m += max(0.0, float(valuation.get("development_upside") or 0)) * 0.23
    base_m -= max(0.0, float(valuation.get("health_risk") or 0) - 4) * 0.26
    if role_tier == "franchise_anchor":
        base_m += max(0.0, float(valuation.get("player_value") or 0) - 82) * 0.85
        base_m += max(0.0, float(valuation.get("on_court_value") or 0) - 70) * 0.55
    elif role_tier == "all_star_core":
        base_m += max(0.0, float(valuation.get("player_value") or 0) - 78) * 0.45
    multiplier = {
        "franchise_anchor": 1.18,
        "all_star_core": 1.1,
        "legacy_star": 1.0,
        "elite_specialist": 0.88,
        "high_end_starter": 0.94,
        "starter": 0.86,
        "rotation": 0.74,
        "depth": 0.58,
    }[role_tier]
    expected = base_m * multiplier * 1_000_000
    current = current_salary(contract)
    age = maybe_float(player.get("age")) or 27.0
    if current is not None:
        current_weight = 0.18
        if role_tier in {"franchise_anchor", "all_star_core", "legacy_star"}:
            current_weight = 0.3
        if age >= 34:
            current_weight += 0.07
        if current < expected and age <= 25:
            current_weight *= 0.4
        expected = expected * (1 - current_weight) + current * current_weight
    if age >= 38:
        expected *= 0.86
    elif age >= 35:
        expected *= 0.93
    return max(float(config["salary"]["minimum_salary"]), expected)


def clamp_salary_to_role(aav: float, role_tier: str, config: dict[str, Any]) -> float:
    floor = float(config["salary"]["minimum_salary"])
    cap = float(config["role_tier_caps"][role_tier])
    return clamp(aav, floor, cap)


def preferred_contract_years(player: dict[str, Any], valuation: dict[str, Any], role_tier: str, config: dict[str, Any]) -> tuple[int, int]:
    age = maybe_float(player.get("age")) or 27.0
    health = float(valuation.get("health_risk") or 0)
    extension_max = int(config["years"]["extension_max_years"])
    if role_tier in {"franchise_anchor", "all_star_core"} and age <= 30 and health < 8:
        preferred = 5
    elif age <= 25:
        preferred = 4
    elif age >= 36:
        preferred = 1
    elif age >= 33 or health >= float(config["years"]["major_health_risk"]):
        preferred = 2
    elif role_tier in {"elite_specialist", "high_end_starter", "starter"}:
        preferred = 3
    else:
        preferred = 2
    max_years = min(extension_max, max(preferred, 2 if age < 36 else 1))
    return preferred, max_years


def market_confidence(player: dict[str, Any], valuation: dict[str, Any], comp_summary: dict[str, Any], contract: dict[str, Any]) -> float:
    confidence = 0.38
    confidence += min(0.18, float(player.get("minutes_projection") or 0) / 36 * 0.18)
    confidence += min(0.16, int(comp_summary.get("comp_count") or 0) * 0.025)
    confidence += min(0.12, float(valuation.get("confidence") or 0) * 0.12)
    if current_salary(contract) is not None:
        confidence += 0.1
    if contract_needs_manual_review(contract):
        confidence -= 0.18
    return round(clamp(confidence, 0.18, 0.82), 3)


def asking_multiplier(player: dict[str, Any], valuation: dict[str, Any], role_tier: str) -> float:
    mult = 1.08
    if role_tier in {"franchise_anchor", "all_star_core"}:
        mult += 0.06
    if maybe_float(player.get("age")) and float(player["age"]) <= 24:
        mult += 0.04
    if float(valuation.get("health_risk") or 0) >= 10:
        mult -= 0.04
    return mult


def minimum_multiplier(player: dict[str, Any], valuation: dict[str, Any], role_tier: str) -> float:
    mult = 0.82
    if role_tier in {"franchise_anchor", "all_star_core", "legacy_star"}:
        mult = 0.88
    if maybe_float(player.get("age")) and float(player["age"]) >= 34:
        mult -= 0.05
    if float(valuation.get("health_risk") or 0) >= 10:
        mult -= 0.04
    return mult


def contract_preference_archetype(player: dict[str, Any], valuation: dict[str, Any], role_tier: str) -> str:
    age = maybe_float(player.get("age")) or 27.0
    if role_tier in {"franchise_anchor", "all_star_core"}:
        return "star_leverage_balancer"
    if role_tier == "legacy_star" or age >= 34:
        return "late_prime_winning_fit"
    if age <= 24:
        return "security_and_role_growth"
    if role_tier == "elite_specialist":
        return "winning_fit_specialist"
    if float(valuation.get("current_salary") or 0) < 5_000_000 and float(valuation.get("player_value") or 0) >= 45:
        return "first_big_contract_seeker"
    return "balanced_market_actor"


def valuation_for_player(canonical: dict[str, Any], player: dict[str, Any]) -> dict[str, Any]:
    return next(
        (item for item in canonical.get("player_asset_valuations", []) if item.get("player_id") == player.get("id")),
        fallback_player_valuation(player),
    )


def fallback_player_valuation(player: dict[str, Any]) -> dict[str, Any]:
    minutes = float(player.get("minutes_projection") or 0.0)
    if minutes > 80:
        minutes = minutes / 82.0
    age = maybe_float(player.get("age")) or 24.0
    value = clamp(18.0 + minutes * 1.35 + max(0.0, 25.0 - age) * 0.8, 5, 62)
    return {
        "id": stable_id("fallback_asset_valuation", player.get("id")),
        "player_id": player.get("id"),
        "team_id": player.get("team_id"),
        "player_value": round(value, 2),
        "contract_surplus": 0.0,
        "contract_drag": 0.0,
        "age_curve": round(clamp(62 - max(0.0, age - 27) * 2.2 + max(0.0, 24 - age) * 2.0, 25, 82), 2),
        "health_risk": 4.0,
        "role_scarcity": 38.0,
        "portability": 42.0,
        "playoff_value": round(max(20.0, value - 4.0), 2),
        "development_upside": round(clamp(max(0.0, 27.0 - age) * 4.0, 0, 48), 2),
        "current_salary": None,
        "confidence": 0.22,
        "source_ids": ["src_contract_market_config_v1"],
        "notes": "Fallback save-state valuation for generated rookies/replacement players without canonical asset valuation.",
    }


def deterministic_rating_shift(*parts: str) -> list[int]:
    text = "|".join(parts)
    seed = sum(ord(char) for char in text)
    return [((seed + idx * 17) % 13) - 6 for idx in range(8)]


def salary_seasons_remaining(contract: dict[str, Any]) -> int:
    active_season = contract_active_season(contract)
    return sum(1 for season in contract.get("seasons", []) if str(season.get("season", "")) >= active_season and season.get("salary") is not None)


def contract_needs_manual_review(contract: dict[str, Any] | None) -> bool:
    if not contract:
        return True
    if contract.get("status") in {"manual_research_pending", "research_pending"}:
        return True
    return current_salary(contract) is None


def option_status_in_remaining_window(contract: dict[str, Any]) -> str | None:
    for season in contract.get("seasons", []):
        if season.get("season") in {"2025-26", "2026-27", "2027-28"} and season.get("option_type"):
            return str(season.get("option_type"))
    return None


def extension_priority_score(
    canonical: dict[str, Any],
    player: dict[str, Any],
    valuation: dict[str, Any],
    profile: PlayerContractMarketProfile,
    eligible: bool,
    manual: bool,
) -> tuple[float, list[str]]:
    state = next(
        (item for item in canonical["team_strategic_states"] if item["team_id"] == player.get("team_id")),
        {"phase": "free_agent", "salary_posture": "unrostered", "pressure": 50, "contention_ceiling": 50},
    )
    age = maybe_float(player.get("age")) or 27.0
    score = 0.0 if eligible else -20.0
    reasons: list[str] = []
    score += float(valuation.get("player_value") or 0) * 0.5
    score += max(0.0, float(valuation.get("contract_surplus") or 0)) * 0.35
    if age <= 25 and float(valuation.get("development_upside") or 0) >= 5:
        score += 15
        reasons.append("young_upside_retention")
    if state["phase"] in {"contending", "contending_with_future_upside"} and float(valuation.get("playoff_value") or 0) >= 62:
        score += 12
        reasons.append("playoff_fit_retention")
    if state["phase"] in {"rebuilding", "developing"} and age >= 31 and profile.expected_aav >= 18_000_000:
        score -= 18
        reasons.append("older_than_team_timeline")
    if profile.role_tier in {"franchise_anchor", "all_star_core"}:
        score += 18
        reasons.append("core_player")
    if profile.role_tier == "elite_specialist":
        score += 8
        reasons.append("portable_specialist")
    if manual:
        reasons.append("manual_contract_review_required")
    if not player.get("team_id"):
        reasons.append("not_on_current_team")
    if not eligible and not manual:
        reasons.append("not_near_extension_window")
    if not reasons:
        reasons.append("standard_retention_review")
    return score, sorted(dict.fromkeys(reasons))


def extension_priority_label(score: float, manual: bool, eligible: bool) -> str:
    if manual:
        return "manual_review"
    if not eligible:
        return "not_current_priority"
    if score >= 70:
        return "core_priority"
    if score >= 48:
        return "value_dependent"
    return "low_priority"


def free_agency_type_for_contract(player: dict[str, Any], contract: dict[str, Any]) -> str:
    if contract_needs_manual_review(contract):
        return "manual_review_projected_free_agent"
    active_season = contract_active_season(contract)
    salary_seasons = [season for season in contract.get("seasons", []) if season.get("salary") is not None and str(season.get("season", "")) >= active_season]
    if not salary_seasons:
        return "manual_review_projected_free_agent"
    last = max(salary_seasons, key=lambda item: str(item.get("season")))
    option = last.get("option_type")
    if last.get("season") == active_season:
        if (maybe_float(player.get("age")) or 27) <= 25:
            return "restricted_or_young_expiring_proxy"
        return "unrestricted_expiring"
    next_season = f"{int(active_season.split('-')[0]) + 1}-{str(int(active_season.split('-')[0]) + 2)[-2:]}"
    if last.get("season") == next_season and option == "player_option":
        return "player_option_watch"
    if last.get("season") == next_season and option == "team_option":
        return "team_option_watch"
    return "not_projected_2026_free_agent"


def likely_suitors_for_player(canonical: dict[str, Any], player: dict[str, Any], profile: PlayerContractMarketProfile, limit: int = 6) -> list[dict[str, Any]]:
    valuation = valuation_for_player(canonical, player)
    scored = []
    for team in canonical["teams"]:
        fit = signing_fit_score(canonical, team["id"], player, valuation)
        if team["id"] == player["team_id"]:
            fit += 7
        if profile.role_tier in {"franchise_anchor", "all_star_core"}:
            fit += float(next(item for item in canonical["front_office_profiles"] if item["team_id"] == team["id"]).get("star_chasing") or 55) * 0.05
        scored.append((fit, team))
    return [team for _, team in sorted(scored, key=lambda item: (item[0], item[1]["abbrev"]), reverse=True)[:limit]]


def signing_fit_score(canonical: dict[str, Any], team_id: str, player: dict[str, Any], valuation: dict[str, Any]) -> float:
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team_id)
    front = next(item for item in canonical["front_office_profiles"] if item["team_id"] == team_id)
    fit = team_fit_for_player(player, valuation, state) * 4.0
    age = maybe_float(player.get("age")) or 27.0
    position_bucket = player_position_bucket(player)
    if f"{position_bucket}_depth" in state.get("needs", []):
        fit += 8
    if state["phase"] in {"rebuilding", "developing"} and age <= 25:
        fit += 12
    if state["phase"] in {"rebuilding", "developing"} and age >= 31:
        fit -= 16
    if state["phase"] in {"contending", "contending_with_future_upside"} and float(valuation.get("playoff_value") or 0) >= 62:
        fit += 10
    if state["salary_posture"].startswith("expensive"):
        fit -= 5 + max(0.0, float(front.get("financial_discipline") or 55) - 55) * 0.07
    if state["salary_posture"].startswith("flexible"):
        fit += 4
    return clamp(50 + fit, 1, 99)


def priority_rank(priority: str) -> int:
    return {"core_priority": 4, "value_dependent": 3, "manual_review": 2, "low_priority": 1, "not_current_priority": 0}.get(priority, 0)


def extension_player_ask(canonical: dict[str, Any], player: dict[str, Any], team: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    profile = next(item for item in canonical["player_contract_market_profiles"] if item["player_id"] == player["id"])
    preference = next(item for item in canonical["player_contract_preferences"] if item["player_id"] == player["id"])
    loyalty_discount = max(0.0, float(preference["priorities"].get("loyalty", 50)) - 60) * 0.001
    asking = profile["asking_aav"] * (1 - loyalty_discount)
    return {
        "annual_salary": round(asking, 2),
        "aav_millions": round(asking / 1_000_000, 2),
        "preferred_years": min(int(profile["preferred_years"]), int(config["years"]["extension_max_years"])),
        "minimum_annual_salary": profile["minimum_aav"],
        "role_tier": profile["role_tier"],
        "notes": "Current-team extension ask with a small loyalty discount when inferred loyalty is high.",
    }


def free_agent_player_ask(canonical: dict[str, Any], player: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    profile = next(item for item in canonical["player_contract_market_profiles"] if item["player_id"] == player["id"])
    return {
        "annual_salary": profile["asking_aav"],
        "aav_millions": round(profile["asking_aav"] / 1_000_000, 2),
        "preferred_years": min(int(profile["preferred_years"]), int(config["years"]["external_max_years"])),
        "minimum_annual_salary": profile["minimum_aav"],
        "role_tier": profile["role_tier"],
        "notes": "Open-market ask from contract market profile. Competition can move accepted offers above or below this ask.",
    }


def team_walkaway_offer(canonical: dict[str, Any], player: dict[str, Any], team: dict[str, Any], negotiation_type: str, seed: int, config: dict[str, Any]) -> dict[str, Any]:
    profile = next(item for item in canonical["player_contract_market_profiles"] if item["player_id"] == player["id"])
    valuation = valuation_for_player(canonical, player)
    front = next(item for item in canonical["front_office_profiles"] if item["team_id"] == team["id"])
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team["id"])
    fit = signing_fit_score(canonical, team["id"], player, valuation)
    rng = random.Random(f"{seed}:{team['id']}:{player['id']}:{negotiation_type}:walkaway")
    competence = float(front.get("competence") or 55)
    pressure = float(state.get("pressure") or front.get("owner_pressure") or 55)
    noise_window = (100 - competence) * 0.0018 + max(0.0, pressure - 65) * 0.0012
    multiplier = 0.96
    multiplier += (fit - 55) * 0.0028
    multiplier += (float(front.get("aggressiveness") or 55) - 55) * 0.0016
    multiplier += (float(front.get("star_chasing") or 55) - 55) * 0.0013 if profile["role_tier"] in {"franchise_anchor", "all_star_core", "legacy_star"} else 0
    multiplier -= (float(front.get("financial_discipline") or 55) - 55) * 0.0014
    multiplier += rng.uniform(-noise_window, noise_window)
    if negotiation_type == "extension":
        multiplier += 0.04
    if state["phase"] in {"rebuilding", "developing"} and (maybe_float(player.get("age")) or 27) >= 31:
        multiplier -= 0.18
    if state["phase"] in {"contending", "contending_with_future_upside"} and float(valuation.get("playoff_value") or 50) >= 65:
        multiplier += 0.06
    max_overpay = float(config["negotiation"]["max_bad_gm_overpay_multiplier"])
    multiplier = clamp(multiplier, 0.72, max_overpay)
    max_salary = profile["asking_aav"] * multiplier
    max_salary = clamp_salary_to_role(max_salary, profile["role_tier"], config)
    initial_ratio = float(config["negotiation"]["initial_offer_floor"]) + max(0.0, fit - 55) * 0.0015 + (float(front.get("aggressiveness") or 55) - 55) * 0.001
    initial_salary = max(profile["minimum_aav"] * 0.98, min(max_salary, max_salary * clamp(initial_ratio, 0.74, 0.95)))
    max_years = min(int(profile["max_years"]), int(config["years"]["extension_max_years"] if negotiation_type == "extension" else config["years"]["external_max_years"]))
    return {
        "max_annual_salary": round(max_salary, 2),
        "max_aav_millions": round(max_salary / 1_000_000, 2),
        "initial_annual_salary": round(initial_salary, 2),
        "initial_aav_millions": round(initial_salary / 1_000_000, 2),
        "max_years": max_years,
        "fit_score": round(fit, 2),
        "personality_multiplier": round(multiplier, 4),
        "notes": f"{team['abbrev']} walk-away blends fit, phase, pressure, financial discipline, and bounded competence noise.",
    }


def generate_team_offer(
    canonical: dict[str, Any],
    player: dict[str, Any],
    team: dict[str, Any],
    offer_type: str,
    seed: int,
    round_no: int,
    config: dict[str, Any],
    negotiation_id: str | None = None,
) -> ContractOffer:
    walkaway = team_walkaway_offer(canonical, player, team, offer_type, seed, config)
    profile = next(item for item in canonical["player_contract_market_profiles"] if item["player_id"] == player["id"])
    years = min(int(walkaway["max_years"]), int(profile["preferred_years"]))
    return contract_offer(
        negotiation_id or stable_id("contract_negotiation", offer_type, team["id"], player["id"], seed),
        team["id"],
        player["id"],
        offer_type,
        round_no,
        years,
        walkaway["initial_annual_salary"],
        role_promise_for_team(canonical, team["id"], player),
        "market_bid",
        walkaway["notes"],
    )


def contract_offer(
    negotiation_id: str,
    team_id: str,
    player_id: str,
    offer_type: str,
    round_no: int,
    years: int,
    annual_salary: float,
    role_promise: str,
    status: str,
    notes: str,
) -> ContractOffer:
    return ContractOffer(
        id=stable_id("contract_offer", negotiation_id, team_id, player_id, round_no, round(annual_salary)),
        negotiation_id=negotiation_id,
        team_id=team_id,
        player_id=player_id,
        offer_type=offer_type,
        round=round_no,
        years=max(1, int(years)),
        annual_salary=round(annual_salary, 2),
        total_value=round(annual_salary * max(1, int(years)), 2),
        option_type=None,
        guarantee_level="standard_guarantee_unknown",
        role_promise=role_promise,
        status=status,
        notes=notes,
    )


def contract_offer_notes(canonical: dict[str, Any], team_id: str, player: dict[str, Any], offer_salary: float, walkaway: dict[str, Any]) -> str:
    team = team_by_id(canonical, team_id)
    return f"{team['abbrev']} offer at ${offer_salary / 1_000_000:.2f}M AAV vs ${walkaway['max_aav_millions']:.2f}M walk-away."


def role_promise_for_team(canonical: dict[str, Any], team_id: str, player: dict[str, Any]) -> str:
    valuation = valuation_for_player(canonical, player)
    fit = signing_fit_score(canonical, team_id, player, valuation)
    minutes = float(player.get("minutes_projection") or 0)
    if fit >= 72 and minutes >= 28:
        return "featured_core_role"
    if fit >= 65 and minutes >= 20:
        return "closing_rotation_role"
    if fit >= 55:
        return "regular_rotation_role"
    return "depth_or_competition_role"


def contract_legality(canonical: dict[str, Any], player: dict[str, Any], team: dict[str, Any], offer: ContractOffer, offer_type: str, config: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    manual: list[str] = []
    salary_min = float(config["salary"]["minimum_salary"])
    max_years = int(config["years"]["extension_max_years"] if offer_type == "extension" else config["years"]["external_max_years"])
    if offer.years < 1 or offer.years > max_years:
        issues.append(f"Offer years {offer.years} exceed practical v1 maximum {max_years}.")
    if offer.annual_salary < salary_min:
        issues.append("Offer is below practical minimum salary.")
    if offer_type == "extension" and player["team_id"] != team["id"]:
        issues.append("Extension offer is not from player's current team.")
    contract = contract_for_player(canonical, player["id"]) or {}
    if contract_needs_manual_review(contract):
        manual.append("Current contract status or salary requires manual review before execution.")
    if offer_type == "extension":
        candidate = next((item for item in canonical.get("extension_candidates", []) if item["player_id"] == player["id"]), None)
        if candidate and not candidate.get("eligible"):
            manual.append(f"Extension eligibility is {candidate.get('eligibility_status')}.")
        start_label = extension_start_season_from_date(str((canonical.get("meta") or {}).get("current_date") or CANONICAL_START_DATE))
    else:
        start_label = str((canonical.get("meta") or {}).get("active_season") or "2025-26")
    start_year = season_start_year_for_contract(start_label)
    retirement_start = projected_retirement_start_year(player, start_year)
    if retirement_start is not None and retirement_start <= start_year + int(offer.years) - 1:
        issues.append(
            f"{player.get('name', 'Player')} is projected to retire before this {offer.years}-year deal would finish."
        )
    if offer_type != "extension" and not any(item["player_id"] == player["id"] for item in canonical.get("free_agent_candidates", [])):
        manual.append("Player is not in the projected v1 free-agent pool.")
    roster_count = sum(1 for p in canonical["players"] if p["team_id"] == team["id"])
    if offer_type != "extension" and team["id"] != player["team_id"] and roster_count >= 21:
        manual.append("Offseason roster count is at/above practical v1 limit before corresponding cuts.")
    posture = salary_posture(canonical, team["id"])
    if "unresolved_contracts" in posture["posture"]:
        manual.append("Team salary posture includes unresolved contract rows.")
    if issues:
        status = "illegal"
    elif manual:
        status = "manual_review_required"
    else:
        status = "legal"
    return {"status": status, "issues": issues, "manual_review": manual, "salary_posture": posture}


def season_start_year_for_contract(season: str) -> int:
    try:
        return int(str(season).split("-")[0])
    except (TypeError, ValueError):
        return 2025


def team_offer_score(canonical: dict[str, Any], player: dict[str, Any], team: dict[str, Any], offer: ContractOffer, offer_type: str, seed: int, config: dict[str, Any]) -> float:
    valuation = valuation_for_player(canonical, player)
    front = next(item for item in canonical["front_office_profiles"] if item["team_id"] == team["id"])
    profile = next(item for item in canonical["player_contract_market_profiles"] if item["player_id"] == player["id"])
    fit = signing_fit_score(canonical, team["id"], player, valuation)
    over_market_m = max(0.0, (offer.annual_salary - profile["expected_aav"]) / 1_000_000)
    age = maybe_float(player.get("age")) or 27.0
    years_risk = max(0, offer.years - 2) * max(0.0, age - 32) * 1.2
    score = float(valuation.get("player_value") or 0) * 0.48 + fit * 0.42
    score -= over_market_m * (1.25 + max(0.0, float(front.get("financial_discipline") or 55) - 55) * 0.018)
    score -= years_risk
    if offer_type == "extension" and team["id"] == player["team_id"]:
        score += 4
    score += personality_contract_adjustment(canonical, team["id"], player["id"], seed, "team_score")
    return clamp(score, 1, 99)


def player_offer_score(canonical: dict[str, Any], player: dict[str, Any], team: dict[str, Any], offer: ContractOffer, seed: int, config: dict[str, Any]) -> tuple[float, list[str]]:
    profile = next(item for item in canonical["player_contract_market_profiles"] if item["player_id"] == player["id"])
    preference = next(item for item in canonical["player_contract_preferences"] if item["player_id"] == player["id"])
    valuation = valuation_for_player(canonical, player)
    state = next(item for item in canonical["team_strategic_states"] if item["team_id"] == team["id"])
    priorities = preference["priorities"]
    money_score = clamp((offer.annual_salary / max(1.0, profile["asking_aav"])) * 82, 1, 99)
    if offer.annual_salary >= profile["asking_aav"]:
        money_score = clamp(86 + min(12, (offer.annual_salary - profile["asking_aav"]) / 1_000_000), 1, 99)
    security_score = clamp((offer.years / max(1, int(profile["preferred_years"]))) * 78, 1, 99)
    if offer.years >= int(profile["preferred_years"]):
        security_score = min(99, security_score + 12)
    role_score = role_promise_score(offer.role_promise)
    winning_score = clamp(float(state.get("contention_ceiling") or 50), 1, 99)
    loyalty_score = 82 if team["id"] == player["team_id"] else 42
    market_score = team_market_desirability(team)
    fit_score = signing_fit_score(canonical, team["id"], player, valuation)
    components = {
        "money": money_score,
        "role": role_score,
        "winning": winning_score,
        "security": security_score,
        "loyalty": loyalty_score,
        "market": market_score,
        "patience": 100 - float(priorities.get("patience", 54)) * 0.35,
        "fit": fit_score,
    }
    total_weight = sum(float(priorities[key]) for key in components)
    score = sum(components[key] * float(priorities[key]) for key in components) / total_weight
    score += personality_contract_adjustment(canonical, team["id"], player["id"], seed, "player_score") * 0.35
    reasons = player_offer_reasons(components, offer, profile, team)
    return clamp(score, 1, 99), reasons


def signing_decision_from_scores(legality: dict[str, Any], team_score: float, player_score: float, reasons: list[str], config: dict[str, Any]) -> dict[str, Any]:
    if legality["status"] == "illegal":
        return {"accepted": False, "decision": "illegal_reject", "reasons": legality["issues"], "notes": "Contract cannot be executed under v1 practical legality."}
    if legality["status"] == "manual_review_required":
        return {"accepted": False, "decision": "manual_review_required", "reasons": legality["manual_review"], "notes": "Contract needs manual review before execution."}
    team_ok = team_score >= float(config["negotiation"]["team_acceptance_threshold"])
    player_ok = player_score >= float(config["negotiation"]["player_acceptance_threshold"])
    if team_ok and player_ok:
        return {"accepted": True, "decision": "accept", "reasons": reasons, "notes": "Both team and player clear v1 acceptance thresholds."}
    decision = "team_walk_away" if not team_ok else "player_reject"
    return {"accepted": False, "decision": decision, "reasons": reasons, "notes": f"Team score {team_score:.2f}, player score {player_score:.2f}; no agreement."}


def free_agency_decision(
    canonical: dict[str, Any],
    player: dict[str, Any],
    chosen: dict[str, Any],
    offers: list[dict[str, Any]],
    seed: int,
    config: dict[str, Any],
    negotiation_id: str,
) -> SigningDecision:
    offer = chosen["offer"]
    legality = chosen["legality"]
    decision = signing_decision_from_scores(legality, chosen["team_score"], chosen["player_score"], chosen["reasons"], config)
    return SigningDecision(
        id=stable_id("signing_decision", negotiation_id, offer["team_id"], player["id"]),
        negotiation_id=negotiation_id,
        player_id=player["id"],
        team_id=offer["team_id"],
        accepted=decision["accepted"],
        decision=decision["decision"],
        accepted_offer=offer if decision["accepted"] else None,
        player_score=round(float(chosen["player_score"]), 3),
        team_score=round(float(chosen["team_score"]), 3),
        competing_offers=[item["offer"] for item in offers],
        reasons=decision["reasons"],
        source_ids=["src_contract_market_config_v1"],
        notes=decision["notes"],
    )


def personality_contract_adjustment(canonical: dict[str, Any], team_id: str, player_id: str, seed: int, channel: str) -> float:
    front = next(item for item in canonical["front_office_profiles"] if item["team_id"] == team_id)
    rng = random.Random(f"{seed}:{team_id}:{player_id}:{channel}:contract_personality")
    competence = float(front.get("competence") or 55)
    pressure = float(front.get("owner_pressure") or 55)
    window = (100 - competence) * 0.045 + max(0.0, pressure - 65) * 0.035
    noise = rng.uniform(-window, window)
    aggression = (float(front.get("aggressiveness") or 55) - 55) * 0.025
    discipline = (float(front.get("financial_discipline") or 55) - 55) * -0.02
    return clamp(noise + aggression + discipline, -7, 7)


def player_offer_reasons(components: dict[str, float], offer: ContractOffer, profile: dict[str, Any], team: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if offer.annual_salary >= profile["asking_aav"]:
        reasons.append("meets_or_exceeds_asking_aav")
    elif offer.annual_salary < profile["minimum_aav"]:
        reasons.append("below_player_minimum")
    if components["winning"] >= 65:
        reasons.append("strong_winning_context")
    if components["role"] >= 70:
        reasons.append("clear_role_promise")
    if components["loyalty"] >= 75:
        reasons.append("current_team_continuity")
    if components["fit"] >= 68:
        reasons.append("strong_team_fit")
    if components["market"] >= 70:
        reasons.append("desirable_market")
    if not reasons:
        reasons.append(f"{team['abbrev']}_offer_balances_money_role_and_fit")
    return sorted(dict.fromkeys(reasons))


def role_promise_score(role_promise: str) -> float:
    return {
        "featured_core_role": 88,
        "closing_rotation_role": 76,
        "regular_rotation_role": 62,
        "depth_or_competition_role": 42,
    }.get(role_promise, 55)


def team_market_desirability(team: dict[str, Any]) -> float:
    large = {"LAL", "LAC", "NYK", "BKN", "GSW", "MIA", "CHI", "BOS", "PHI", "DAL"}
    medium = {"ATL", "HOU", "PHX", "TOR", "WAS", "DEN"}
    if team["abbrev"] in large:
        return 74
    if team["abbrev"] in medium:
        return 62
    return 52 + (sum(ord(char) for char in team["abbrev"]) % 9) - 4


def normalize_aav(value: float) -> float:
    value = float(value)
    if value < 1_000_000:
        return value * 1_000_000
    return value


def accepted_offer_from_negotiation(negotiation: dict[str, Any]) -> dict[str, Any] | None:
    for offer in negotiation.get("offers", []):
        if offer.get("status") in {"accepted", "agreement"}:
            return offer
    if negotiation.get("offers"):
        return negotiation["offers"][-1]
    return None
