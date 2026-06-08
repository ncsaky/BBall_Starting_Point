from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


CANONICAL_SEASON = "2025-26"
CANONICAL_START_DATE = "2025-10-01"


@dataclass(frozen=True)
class SourceEvidence:
    id: str
    title: str
    kind: str
    trust_level: str
    path: str | None = None
    url: str | None = None
    retrieved_at: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class Team:
    id: str
    abbrev: str
    name: str
    conference: str | None = None
    division: str | None = None
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Player:
    id: str
    name: str
    normalized_name: str
    slug: str
    team_id: str
    team_abbrev: str
    position: str | None
    age: float | None
    birthdate: str | None
    height_inches: float | None
    weight_lbs: float | None
    wingspan_inches: float | None
    minutes_projection: float
    prior_minutes: float | None
    primary_off_role: str | None
    secondary_off_role: str | None
    primary_def_role: str | None
    sim_eligible_raw: bool
    missing_critical_fields: list[str]
    critical_field_fallbacks: dict[str, Any]
    rotation_priority: str
    source_ids: list[str]


@dataclass(frozen=True)
class RosterSlot:
    id: str
    team_id: str
    player_id: str
    status: str
    rotation_priority: str
    minutes_projection: float
    source_ids: list[str]


@dataclass(frozen=True)
class TraitValue:
    id: str
    player_id: str
    trait_key: str
    label: str
    value: float
    confidence: float
    source_kind: str
    source_ids: list[str]
    last_verified: str
    notes: str
    components: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Contract:
    id: str
    player_id: str
    team_id: str
    status: str
    seasons: list[dict[str, Any]]
    confidence: float
    source_ids: list[str]
    notes: str
    original_contract_years: int | None = None
    signed_season: str | None = None
    extension_eligibility: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DraftPick:
    id: str
    team_id: str
    season: str
    round: int
    status: str
    original_team_id: str | None
    current_owner_team_id: str | None
    protections: str | None
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftClass:
    id: str
    season: str
    class_type: str
    seed: int | None
    class_strength: float
    top_end_strength: float
    depth_strength: float
    prospect_count: int
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftProspect:
    id: str
    draft_year: str
    name: str
    normalized_name: str
    rank: int
    rank_range: dict[str, int]
    position: str
    source_team: str | None
    league: str
    class_year: str | None
    age: float | None
    height_inches: float | None
    weight_lbs: float | None
    archetype: str
    current_ability: float
    potential: float
    floor: float
    ceiling: float
    development_curve: str
    volatility: float
    rookie_contract_value: float
    public_stats: dict[str, Any]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftProspectTrait:
    id: str
    prospect_id: str
    trait_key: str
    value: float
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class ScoutingReport:
    id: str
    team_id: str
    prospect_id: str
    scouted_grade: float
    estimated_current: dict[str, float]
    estimated_potential: dict[str, float]
    trait_estimates: dict[str, dict[str, float]]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftBoardEntry:
    id: str
    team_id: str
    prospect_id: str
    draft_year: str
    board_rank: int
    bpa_grade: float
    fit_grade: float
    need_fit: float
    cap_value: float
    risk_adjusted_grade: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftPickDecision:
    id: str
    pick_id: str
    team_id: str
    prospect_id: str
    decision: str
    bpa_rank: int
    team_board_rank: int
    grade_gap_to_bpa: float
    reasons: list[str]
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftSelection:
    id: str
    pick_id: str
    team_id: str
    prospect_id: str
    draft_year: str
    overall_pick: int
    status: str
    decision_id: str
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftTradeCandidate:
    id: str
    pick_id: str
    from_team_id: str
    to_team_id: str
    target_prospect_id: str | None
    trade_type: str
    proposal: dict[str, Any]
    evaluation: dict[str, Any]
    score: float
    reasons: list[str]
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftLotteryResult:
    id: str
    draft_year: str
    seed: int
    draw_count: int
    pre_lottery_order: list[str]
    lottery_draw: list[str]
    final_lottery_order: list[str]
    odds_by_team: dict[str, float]
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftOrderPick:
    id: str
    draft_year: str
    round: int
    overall_pick: int
    original_team_id: str
    current_owner_team_id: str
    pre_lottery_rank: int | None
    lottery_slot: int | None
    status: str
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DraftRights:
    id: str
    selection_id: str
    prospect_id: str
    team_id: str
    draft_year: str
    rights_status: str
    roster_status: str
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class RookieContractProjection:
    id: str
    selection_id: str
    prospect_id: str
    team_id: str
    draft_year: str
    contract_type: str
    status: str
    seasons: list[dict[str, Any]]
    cap_hold: float
    total_salary: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class StaffProfile:
    id: str
    team_id: str
    role: str
    name: str | None
    status: str
    traits: dict[str, Any]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class GameplayStaffSlot:
    id: str
    team_id: str
    slot: str
    name: str
    archetype: str
    style_tags: list[str]
    skill_traits: dict[str, float]
    personality_traits: dict[str, float]
    status: str
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class GameAvailability:
    id: str
    game_id: str
    player_name: str
    team_abbrev: str
    minutes: float
    dnp: bool
    comment: str | None
    source_ids: list[str]


@dataclass(frozen=True)
class PlayerGameActual:
    id: str
    game_id: str
    player_name: str
    team_abbrev: str
    minutes: float
    points: int
    rebounds: int
    assists: int
    turnovers: int
    steals: int
    blocks: int
    fgm: int
    fga: int
    fg3m: int
    fg3a: int
    ftm: int
    fta: int
    dnp: bool
    comment: str | None
    source_ids: list[str]


@dataclass(frozen=True)
class PlayerHealthProfile:
    id: str
    player_id: str
    durability: float
    injury_prone: bool
    body_area_risk_tags: list[str]
    major_prior_injuries: list[dict[str, Any]]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class PlayerHealthState:
    id: str
    player_id: str
    as_of_date: str
    fatigue: float
    current_injury_id: str | None
    availability_status: str
    return_date: str | None
    rust: float
    games_missed: int
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class InjuryEvent:
    id: str
    player_id: str
    team_id: str
    start_date: str
    return_date: str
    body_area: str
    severity: str
    expected_days_missed: int
    expected_games_missed: int
    recurrence: bool
    status: str
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class DevelopmentEvent:
    id: str
    player_id: str
    team_id: str
    month: str
    trait_deltas: dict[str, float]
    age: float | None
    minutes_context: float
    staff_context: dict[str, Any]
    health_context: dict[str, Any]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class FrontOfficeProfile:
    id: str
    team_id: str
    archetype: str
    competence: float
    patience: float
    risk_tolerance: float
    aggressiveness: float
    asset_discipline: float
    timeline_honesty: float
    owner_pressure: float
    star_chasing: float
    financial_discipline: float
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class TeamStrategicState:
    id: str
    team_id: str
    phase: str
    timeline: str
    contention_ceiling: float
    core_age: float | None
    health_risk: float
    salary_posture: str
    youth_pipeline: float
    pick_inventory: dict[str, Any]
    needs: list[str]
    excesses: list[str]
    pressure: float
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class PlayerAssetValuation:
    id: str
    player_id: str
    team_id: str
    player_value: float
    on_court_value: float
    contract_surplus: float
    age_curve: float
    health_risk: float
    role_scarcity: float
    portability: float
    playoff_value: float
    development_upside: float
    contract_status: str
    current_salary: float | None
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class PlayerContractMarketProfile:
    id: str
    player_id: str
    team_id: str
    role_tier: str
    market_aav_low: float
    market_aav_high: float
    expected_aav: float
    asking_aav: float
    minimum_aav: float
    preferred_years: int
    max_years: int
    comp_player_ids: list[str]
    comp_summary: dict[str, Any]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class PlayerContractPreference:
    id: str
    player_id: str
    archetype: str
    priorities: dict[str, float]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class ExtensionCandidate:
    id: str
    player_id: str
    team_id: str
    eligible: bool
    eligibility_status: str
    years_remaining: int
    current_salary: float | None
    projected_aav: float
    projected_years: int
    priority: str
    manual_review_required: bool
    reasons: list[str]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class FreeAgentCandidate:
    id: str
    player_id: str
    current_team_id: str
    free_agency_type: str
    market_tier: str
    projected_aav: float
    projected_years: int
    likely_suitors: list[str]
    manual_review_required: bool
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class TradeBlockEntry:
    id: str
    team_id: str
    player_id: str
    block_score: float
    willingness: str
    reasons: list[str]
    preferred_return: list[str]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class TradeProposal:
    id: str
    date: str
    from_team_id: str
    to_team_id: str
    from_assets: list[dict[str, Any]]
    to_assets: list[dict[str, Any]]
    status: str
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class TradeEvaluation:
    id: str
    proposal_id: str
    perspective_team_id: str
    accepted: bool
    decision: str
    incoming_value: float
    outgoing_value: float
    net_value: float
    legality_status: str
    legality_issues: list[str]
    personality_adjustments: dict[str, float]
    notes: str


@dataclass(frozen=True)
class ContractOffer:
    id: str
    negotiation_id: str
    team_id: str
    player_id: str
    offer_type: str
    round: int
    years: int
    annual_salary: float
    total_value: float
    option_type: str | None
    guarantee_level: str
    role_promise: str
    status: str
    notes: str


@dataclass(frozen=True)
class SigningDecision:
    id: str
    negotiation_id: str
    player_id: str
    team_id: str
    accepted: bool
    decision: str
    accepted_offer: dict[str, Any] | None
    player_score: float
    team_score: float
    competing_offers: list[dict[str, Any]]
    reasons: list[str]
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class ContractNegotiation:
    id: str
    negotiation_type: str
    player_id: str
    team_id: str
    date: str
    seed: int
    rounds: int
    player_ask: dict[str, Any]
    team_walkaway: dict[str, Any]
    offers: list[dict[str, Any]]
    final_decision_id: str | None
    status: str
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class TransactionLog:
    id: str
    date: str
    transaction_type: str
    proposal_id: str
    status: str
    teams: list[str]
    assets: dict[str, Any]
    evaluations: list[dict[str, Any]]
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class CoachRating:
    id: str
    team_id: str
    coach_name: str
    ratings: dict[str, float]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class SimFeatureVector:
    id: str
    entity_type: str
    entity_id: str
    features: dict[str, float]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class SimGameResult:
    id: str
    game_id: str
    mode: str
    seed: int
    home_team_id: str
    away_team_id: str
    home_score: int
    away_score: int
    possessions: float
    player_lines: list[dict[str, Any]]
    team_lines: list[dict[str, Any]]
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class ValidationReport:
    id: str
    mode: str
    through_date: str | None
    game_count: int
    summary: dict[str, Any]
    biggest_misses: list[dict[str, Any]]
    source_ids: list[str]


@dataclass(frozen=True)
class TeamProfile:
    id: str
    team_id: str
    timeline: str
    identity: str
    offensive_style: list[str]
    defensive_style: list[str]
    strengths: list[str]
    weaknesses: list[str]
    swing_players: list[str]
    front_office_pressure: str
    strategic_behavior: list[str]
    confidence: float
    source_ids: list[str]
    notes: str


@dataclass(frozen=True)
class CoverageIssue:
    id: str
    severity: str
    category: str
    entity_type: str
    entity_id: str
    message: str
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CoverageReport:
    id: str
    generated_at: str
    summary: dict[str, Any]
    issues: list[CoverageIssue]


@dataclass(frozen=True)
class CanonicalUniverse:
    meta: dict[str, Any]
    sources: list[SourceEvidence]
    teams: list[Team]
    players: list[Player]
    roster_slots: list[RosterSlot]
    traits: list[TraitValue]
    contracts: list[Contract]
    draft_picks: list[DraftPick]
    draft_classes: list[DraftClass]
    draft_prospects: list[DraftProspect]
    draft_prospect_traits: list[DraftProspectTrait]
    scouting_reports: list[ScoutingReport]
    draft_board_entries: list[DraftBoardEntry]
    staff_profiles: list[StaffProfile]
    gameplay_staff_slots: list[GameplayStaffSlot]
    team_profiles: list[TeamProfile]
    player_health_profiles: list[PlayerHealthProfile]
    player_health_states: list[PlayerHealthState]
    injury_events: list[InjuryEvent]
    development_events: list[DevelopmentEvent]
    front_office_profiles: list[FrontOfficeProfile]
    team_strategic_states: list[TeamStrategicState]
    player_asset_valuations: list[PlayerAssetValuation]
    player_contract_market_profiles: list[PlayerContractMarketProfile]
    player_contract_preferences: list[PlayerContractPreference]
    extension_candidates: list[ExtensionCandidate]
    free_agent_candidates: list[FreeAgentCandidate]
    trade_block_entries: list[TradeBlockEntry]
    coverage_report: CoverageReport


def to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_plain(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [to_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    return value
