from __future__ import annotations

from collections import Counter, defaultdict
from .schema import (
    CoverageIssue,
    CoverageReport,
    Contract,
    DevelopmentEvent,
    DraftBoardEntry,
    DraftClass,
    DraftPick,
    DraftProspect,
    DraftProspectTrait,
    FrontOfficeProfile,
    GameplayStaffSlot,
    InjuryEvent,
    Player,
    PlayerAssetValuation,
    PlayerContractMarketProfile,
    PlayerContractPreference,
    PlayerHealthProfile,
    PlayerHealthState,
    ScoutingReport,
    StaffProfile,
    Team,
    TeamProfile,
    TeamStrategicState,
    TraitValue,
    TradeBlockEntry,
    ExtensionCandidate,
    FreeAgentCandidate,
)
from .utils import stable_id


ROTATION_PRIORITIES = {"core_rotation", "rotation", "development_priority"}
CRITICAL_TRAITS = {
    "release_speed",
    "shooting_range",
    "rim_pressure",
    "handle_pressure",
    "passing_reads",
    "defensive_effort",
    "rim_deterrence",
    "portability",
}
GAMEPLAY_STAFF_SLOTS = {
    "head_coach",
    "offensive_coordinator",
    "defensive_coordinator",
    "development_lead",
    "scouting_lead",
    "performance_lead",
}


def build_coverage_report(
    players: list[Player],
    teams: list[Team],
    traits: list[TraitValue],
    contracts: list[Contract],
    draft_picks: list[DraftPick],
    draft_classes: list[DraftClass],
    draft_prospects: list[DraftProspect],
    draft_prospect_traits: list[DraftProspectTrait],
    scouting_reports: list[ScoutingReport],
    draft_board_entries: list[DraftBoardEntry],
    staff_profiles: list[StaffProfile],
    gameplay_staff_slots: list[GameplayStaffSlot],
    team_profiles: list[TeamProfile],
    player_health_profiles: list[PlayerHealthProfile],
    player_health_states: list[PlayerHealthState],
    injury_events: list[InjuryEvent],
    development_events: list[DevelopmentEvent],
    front_office_profiles: list[FrontOfficeProfile],
    team_strategic_states: list[TeamStrategicState],
    player_asset_valuations: list[PlayerAssetValuation],
    player_contract_market_profiles: list[PlayerContractMarketProfile],
    player_contract_preferences: list[PlayerContractPreference],
    extension_candidates: list[ExtensionCandidate],
    free_agent_candidates: list[FreeAgentCandidate],
    trade_block_entries: list[TradeBlockEntry],
    generated_at: str,
) -> CoverageReport:
    issues: list[CoverageIssue] = []
    teams_by_id = {team.id: team for team in teams}
    traits_by_player: dict[str, list[TraitValue]] = defaultdict(list)
    for trait in traits:
        traits_by_player[trait.player_id].append(trait)

    seen_player_ids: set[str] = set()
    for player in players:
        if player.id in seen_player_ids:
            issues.append(issue("P0", "schema", "player", player.id, "Duplicate player id detected.", player.source_ids))
        seen_player_ids.add(player.id)
        if player.team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "player", player.id, f"Player references unknown team {player.team_id}.", player.source_ids))
        uncovered_raw_fields = [field for field in player.missing_critical_fields if field not in player.critical_field_fallbacks]
        if player.rotation_priority in ROTATION_PRIORITIES and uncovered_raw_fields:
            issues.append(
                issue(
                    "P1",
                    "coverage",
                    "player",
                    player.id,
                    f"Rotation-relevant player has missing critical raw fields without fallback: {', '.join(uncovered_raw_fields)}.",
                    player.source_ids,
                )
            )
        elif player.rotation_priority in ROTATION_PRIORITIES and player.missing_critical_fields:
            issues.append(
                issue(
                    "P2",
                    "coverage",
                    "player",
                    player.id,
                    f"Rotation-relevant player has critical raw fields covered by explicit fallbacks: {', '.join(player.missing_critical_fields)}.",
                    player.source_ids + ["src_critical_field_fallback_method_v1"],
                )
            )
        player_trait_keys = {trait.trait_key for trait in traits_by_player.get(player.id, [])}
        missing_traits = sorted(CRITICAL_TRAITS - player_trait_keys)
        if missing_traits:
            issues.append(issue("P0", "schema", "player", player.id, f"Missing critical canonical traits: {', '.join(missing_traits)}.", player.source_ids))
        if player.rotation_priority in ROTATION_PRIORITIES:
            low_conf = [trait.trait_key for trait in traits_by_player[player.id] if trait.trait_key in CRITICAL_TRAITS and trait.confidence < 0.35]
            if low_conf:
                issues.append(issue("P2", "coverage", "player", player.id, f"Rotation-relevant player has low-confidence traits: {', '.join(sorted(low_conf))}.", player.source_ids))

    for contract in contracts:
        if contract.status == "research_pending":
            severity = "P1" if any(player.id == contract.player_id and player.rotation_priority in ROTATION_PRIORITIES for player in players) else "P3"
            issues.append(issue(severity, "ledger", "contract", contract.id, "Contract details are scaffolded but not publicly verified.", contract.source_ids))

    for pick in draft_picks:
        if pick.status == "research_pending":
            issues.append(issue("P2", "ledger", "draft_pick", pick.id, "Draft pick ownership/protections are scaffolded but not publicly verified.", pick.source_ids))

    draft_class_years = {draft_class.season for draft_class in draft_classes}
    prospect_ids = {prospect.id for prospect in draft_prospects}
    if not draft_classes:
        issues.append(issue("P1", "coverage", "draft", "draft_classes", "No draft classes are available for scouting/draft AI.", ["src_draft_model_config_v1"]))
    if not draft_prospects:
        issues.append(issue("P1", "coverage", "draft", "draft_prospects", "No draft prospects are available for scouting/draft AI.", ["src_draft_model_config_v1"]))
    for draft_class in draft_classes:
        if draft_class.prospect_count <= 0:
            issues.append(issue("P1", "coverage", "draft_class", draft_class.id, "Draft class has no prospects.", draft_class.source_ids))
    traits_by_prospect: dict[str, set[str]] = defaultdict(set)
    for trait in draft_prospect_traits:
        traits_by_prospect[trait.prospect_id].add(trait.trait_key)
        if trait.prospect_id not in prospect_ids:
            issues.append(issue("P0", "schema", "draft_prospect_trait", trait.id, "Draft prospect trait references unknown prospect.", trait.source_ids))
        if not 0 <= trait.value <= 100:
            issues.append(issue("P0", "schema", "draft_prospect_trait", trait.id, "Draft prospect trait value is outside 0-100.", trait.source_ids))
    for prospect in draft_prospects:
        if prospect.draft_year not in draft_class_years:
            issues.append(issue("P0", "schema", "draft_prospect", prospect.id, "Draft prospect references unknown draft class year.", prospect.source_ids))
        if not prospect.source_ids:
            issues.append(issue("P0", "schema", "draft_prospect", prospect.id, "Draft prospect has no source IDs.", prospect.source_ids))
        if not prospect.position or prospect.position == "UNK":
            issues.append(issue("P2", "coverage", "draft_prospect", prospect.id, "Draft prospect position is missing or unknown.", prospect.source_ids))
        if len(traits_by_prospect.get(prospect.id, set())) < 8:
            issues.append(issue("P1", "coverage", "draft_prospect", prospect.id, "Draft prospect has too few generated/scouted trait anchors.", prospect.source_ids))

    reports_by_team: dict[str, int] = defaultdict(int)
    for report in scouting_reports:
        if report.team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "scouting_report", report.id, "Scouting report references unknown team.", report.source_ids))
        if report.prospect_id not in prospect_ids:
            issues.append(issue("P0", "schema", "scouting_report", report.id, "Scouting report references unknown prospect.", report.source_ids))
        reports_by_team[report.team_id] += 1
        for field_name, estimate in {"current": report.estimated_current, "potential": report.estimated_potential}.items():
            if estimate.get("low", 0) > estimate.get("mid", 0) or estimate.get("mid", 0) > estimate.get("high", 100):
                issues.append(issue("P0", "schema", "scouting_report", report.id, f"Scouting {field_name} estimate range is invalid.", report.source_ids))
    board_by_team: dict[str, int] = defaultdict(int)
    for entry in draft_board_entries:
        if entry.team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "draft_board_entry", entry.id, "Draft board entry references unknown team.", entry.source_ids))
        if entry.prospect_id not in prospect_ids:
            issues.append(issue("P0", "schema", "draft_board_entry", entry.id, "Draft board entry references unknown prospect.", entry.source_ids))
        board_by_team[entry.team_id] += 1
        if entry.draft_year not in draft_class_years:
            issues.append(issue("P0", "schema", "draft_board_entry", entry.id, "Draft board entry references unknown draft class year.", entry.source_ids))
    expected_2026_prospects = sum(1 for prospect in draft_prospects if prospect.draft_year == "2026")
    missing_scouting_reports = sum(max(0, expected_2026_prospects - reports_by_team.get(team.id, 0)) for team in teams)
    missing_draft_board_entries = sum(max(0, expected_2026_prospects - board_by_team.get(team.id, 0)) for team in teams)
    if missing_scouting_reports:
        issues.append(issue("P1", "coverage", "draft", "scouting_reports", f"Missing {missing_scouting_reports} team/prospect scouting reports.", ["src_draft_model_config_v1"]))
    if missing_draft_board_entries:
        issues.append(issue("P1", "coverage", "draft", "draft_board_entries", f"Missing {missing_draft_board_entries} team/prospect draft board entries.", ["src_draft_model_config_v1"]))

    for staff in staff_profiles:
        if staff.status == "research_pending":
            issues.append(issue("P2", "ledger", "staff", staff.id, "Key staff role is scaffolded but not publicly verified.", staff.source_ids))

    gameplay_slots_by_team: dict[str, set[str]] = defaultdict(set)
    for staff_slot in gameplay_staff_slots:
        if staff_slot.team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "gameplay_staff_slot", staff_slot.id, "Gameplay staff slot references unknown team.", staff_slot.source_ids))
        gameplay_slots_by_team[staff_slot.team_id].add(staff_slot.slot)
        if staff_slot.status != "fictional_gameplay_scaffold":
            issues.append(issue("P2", "coverage", "gameplay_staff_slot", staff_slot.id, "Gameplay staff slot is not marked as fictional gameplay scaffold.", staff_slot.source_ids))
    missing_gameplay_staff_slots = 0
    for team in teams:
        missing_slots = sorted(GAMEPLAY_STAFF_SLOTS - gameplay_slots_by_team.get(team.id, set()))
        missing_gameplay_staff_slots += len(missing_slots)
        if missing_slots:
            issues.append(issue("P1", "coverage", "team", team.id, f"Missing gameplay staff slots: {', '.join(missing_slots)}.", team.source_ids))

    for profile in team_profiles:
        if profile.team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "team_profile", profile.id, "Team profile references unknown team.", profile.source_ids))
        if profile.confidence == 0:
            issues.append(issue("P3", "coverage", "team_profile", profile.id, "Team profile has no manifesto/source coverage yet.", profile.source_ids))

    health_profile_player_ids = {profile.player_id for profile in player_health_profiles}
    health_state_player_ids = {state.player_id for state in player_health_states}
    player_ids = {player.id for player in players}
    for profile in player_health_profiles:
        if profile.player_id not in player_ids:
            issues.append(issue("P0", "schema", "player_health_profile", profile.id, "Health profile references unknown player.", profile.source_ids))
    for state in player_health_states:
        if state.player_id not in player_ids:
            issues.append(issue("P0", "schema", "player_health_state", state.id, "Health state references unknown player.", state.source_ids))
    missing_health_profiles = len(player_ids - health_profile_player_ids)
    missing_health_states = len(player_ids - health_state_player_ids)
    if missing_health_profiles:
        issues.append(issue("P1", "coverage", "health", "player_health_profiles", f"Missing health profiles for {missing_health_profiles} players.", ["src_injury_model_config_v1"]))
    if missing_health_states:
        issues.append(issue("P1", "coverage", "health", "player_health_states", f"Missing health states for {missing_health_states} players.", ["src_injury_model_config_v1"]))

    front_office_team_ids = {profile.team_id for profile in front_office_profiles}
    strategy_team_ids = {state.team_id for state in team_strategic_states}
    valued_player_ids = {valuation.player_id for valuation in player_asset_valuations}
    missing_front_offices = len(set(teams_by_id) - front_office_team_ids)
    missing_strategic_states = len(set(teams_by_id) - strategy_team_ids)
    missing_asset_values = len(player_ids - valued_player_ids)
    market_profile_player_ids = {profile.player_id for profile in player_contract_market_profiles}
    preference_player_ids = {preference.player_id for preference in player_contract_preferences}
    missing_market_profiles = len(player_ids - market_profile_player_ids)
    missing_contract_preferences = len(player_ids - preference_player_ids)
    if missing_front_offices:
        issues.append(issue("P1", "coverage", "transactions", "front_office_profiles", f"Missing front-office profiles for {missing_front_offices} teams.", ["src_transaction_model_config_v1"]))
    if missing_strategic_states:
        issues.append(issue("P1", "coverage", "transactions", "team_strategic_states", f"Missing strategic states for {missing_strategic_states} teams.", ["src_transaction_model_config_v1"]))
    if missing_asset_values:
        issues.append(issue("P1", "coverage", "transactions", "player_asset_valuations", f"Missing player asset valuations for {missing_asset_values} players.", ["src_transaction_model_config_v1"]))
    if missing_market_profiles:
        issues.append(issue("P1", "coverage", "contracts", "player_contract_market_profiles", f"Missing contract market profiles for {missing_market_profiles} players.", ["src_contract_market_config_v1"]))
    if missing_contract_preferences:
        issues.append(issue("P1", "coverage", "contracts", "player_contract_preferences", f"Missing contract preferences for {missing_contract_preferences} players.", ["src_contract_market_config_v1"]))
    for valuation in player_asset_valuations:
        if valuation.player_id not in player_ids:
            issues.append(issue("P0", "schema", "player_asset_valuation", valuation.id, "Player asset valuation references unknown player.", valuation.source_ids))
        if valuation.team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "player_asset_valuation", valuation.id, "Player asset valuation references unknown team.", valuation.source_ids))
    for profile in player_contract_market_profiles:
        if profile.player_id not in player_ids:
            issues.append(issue("P0", "schema", "player_contract_market_profile", profile.id, "Contract market profile references unknown player.", profile.source_ids))
        if profile.team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "player_contract_market_profile", profile.id, "Contract market profile references unknown team.", profile.source_ids))
        if profile.market_aav_low > profile.market_aav_high:
            issues.append(issue("P0", "schema", "player_contract_market_profile", profile.id, "Contract market low AAV exceeds high AAV.", profile.source_ids))
    for preference in player_contract_preferences:
        if preference.player_id not in player_ids:
            issues.append(issue("P0", "schema", "player_contract_preference", preference.id, "Contract preference references unknown player.", preference.source_ids))
    for candidate in extension_candidates:
        if candidate.player_id not in player_ids:
            issues.append(issue("P0", "schema", "extension_candidate", candidate.id, "Extension candidate references unknown player.", candidate.source_ids))
        if candidate.team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "extension_candidate", candidate.id, "Extension candidate references unknown team.", candidate.source_ids))
    for candidate in free_agent_candidates:
        if candidate.player_id not in player_ids:
            issues.append(issue("P0", "schema", "free_agent_candidate", candidate.id, "Free-agent candidate references unknown player.", candidate.source_ids))
        if candidate.current_team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "free_agent_candidate", candidate.id, "Free-agent candidate references unknown team.", candidate.source_ids))
        for team_id in candidate.likely_suitors:
            if team_id not in teams_by_id:
                issues.append(issue("P0", "schema", "free_agent_candidate", candidate.id, f"Free-agent candidate references unknown suitor {team_id}.", candidate.source_ids))
    for entry in trade_block_entries:
        if entry.player_id not in player_ids:
            issues.append(issue("P0", "schema", "trade_block_entry", entry.id, "Trade block entry references unknown player.", entry.source_ids))
        if entry.team_id not in teams_by_id:
            issues.append(issue("P0", "schema", "trade_block_entry", entry.id, "Trade block entry references unknown team.", entry.source_ids))

    counts = Counter(issue.severity for issue in issues)
    rotation_players = [player for player in players if player.rotation_priority in ROTATION_PRIORITIES]
    summary = {
        "team_count": len(teams),
        "player_count": len(players),
        "rotation_relevant_player_count": len(rotation_players),
        "trait_count": len(traits),
        "contract_count": len(contracts),
        "contract_manual_review_count": sum(1 for contract in contracts if contract.status == "manual_research_pending"),
        "draft_pick_count": len(draft_picks),
        "draft_pick_placeholder_count": sum(1 for pick in draft_picks if pick.status == "research_pending"),
        "verified_draft_pick_count": sum(1 for pick in draft_picks if pick.status != "research_pending"),
        "draft_class_count": len(draft_classes),
        "draft_prospect_count": len(draft_prospects),
        "draft_prospect_trait_count": len(draft_prospect_traits),
        "scouting_report_count": len(scouting_reports),
        "draft_board_entry_count": len(draft_board_entries),
        "missing_scouting_reports": missing_scouting_reports,
        "missing_draft_board_entries": missing_draft_board_entries,
        "staff_profile_count": len(staff_profiles),
        "verified_staff_profile_count": sum(1 for staff in staff_profiles if staff.status != "research_pending"),
        "staff_placeholder_count": sum(1 for staff in staff_profiles if staff.status == "research_pending"),
        "gameplay_staff_slot_count": len(gameplay_staff_slots),
        "missing_gameplay_staff_slots": missing_gameplay_staff_slots,
        "team_profile_count": len(team_profiles),
        "player_health_profile_count": len(player_health_profiles),
        "player_health_state_count": len(player_health_states),
        "startup_injury_event_count": len(injury_events),
        "development_event_count": len(development_events),
        "front_office_profile_count": len(front_office_profiles),
        "team_strategic_state_count": len(team_strategic_states),
        "player_asset_valuation_count": len(player_asset_valuations),
        "player_contract_market_profile_count": len(player_contract_market_profiles),
        "player_contract_preference_count": len(player_contract_preferences),
        "extension_candidate_count": len(extension_candidates),
        "extension_manual_review_count": sum(1 for candidate in extension_candidates if candidate.manual_review_required),
        "free_agent_candidate_count": len(free_agent_candidates),
        "free_agent_manual_review_count": sum(1 for candidate in free_agent_candidates if candidate.manual_review_required),
        "trade_block_entry_count": len(trade_block_entries),
        "missing_front_office_profiles": missing_front_offices,
        "missing_team_strategic_states": missing_strategic_states,
        "missing_player_asset_valuations": missing_asset_values,
        "missing_player_contract_market_profiles": missing_market_profiles,
        "missing_player_contract_preferences": missing_contract_preferences,
        "missing_player_health_profiles": missing_health_profiles,
        "missing_player_health_states": missing_health_states,
        "issues_by_severity": dict(sorted(counts.items())),
        "research_pending": {
            "contracts": sum(1 for contract in contracts if contract.status == "research_pending"),
            "draft_picks": sum(1 for pick in draft_picks if pick.status == "research_pending"),
            "draft_prospects": 0 if draft_prospects else 1,
            "scouting_reports": missing_scouting_reports,
            "draft_board_entries": missing_draft_board_entries,
            "staff_profiles": sum(1 for staff in staff_profiles if staff.status == "research_pending"),
            "gameplay_staff_slots": missing_gameplay_staff_slots,
            "team_profiles": sum(1 for profile in team_profiles if profile.confidence == 0),
            "player_health_profiles": missing_health_profiles,
            "player_health_states": missing_health_states,
            "front_office_profiles": missing_front_offices,
            "team_strategic_states": missing_strategic_states,
            "player_asset_valuations": missing_asset_values,
            "player_contract_market_profiles": missing_market_profiles,
            "player_contract_preferences": missing_contract_preferences,
        },
        "sim_eligibility_raw": {
            "eligible": sum(1 for player in players if player.sim_eligible_raw),
            "ineligible": sum(1 for player in players if not player.sim_eligible_raw),
        },
        "rotation_missing_critical_fields": sum(1 for player in rotation_players if player.missing_critical_fields),
        "rotation_missing_without_fallback": sum(1 for player in rotation_players if any(field not in player.critical_field_fallbacks for field in player.missing_critical_fields)),
    }
    return CoverageReport(
        id="coverage_2025_26_preseason",
        generated_at=generated_at,
        summary=summary,
        issues=issues,
    )


def issue(severity: str, category: str, entity_type: str, entity_id: str, message: str, source_ids: list[str]) -> CoverageIssue:
    return CoverageIssue(
        id=stable_id("issue", severity, category, entity_type, entity_id, message[:32]),
        severity=severity,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        source_ids=source_ids,
    )
