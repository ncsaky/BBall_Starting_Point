from __future__ import annotations

import json
import hashlib
from collections import Counter, defaultdict
from dataclasses import replace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .audit import build_coverage_report
from .contract_ai import (
    CONTRACT_MARKET_CONFIG_FILE,
    build_extension_candidates,
    build_free_agent_candidates,
    build_player_contract_market_profiles,
    build_player_contract_preferences,
    load_contract_market_config,
)
from .draft import DRAFT_MODEL_CONFIG_FILE, build_draft_context, load_draft_model_config
from .health import build_health_records, load_injury_model_config
from .research import (
    BREF_CONTRACTS_URL,
    BREF_TEAM_URL_TEMPLATE,
    BETTING_ODDS_FILE,
    COACHES_FILE,
    COACH_REPUTATION_FILE,
    CONTRACTS_FILE,
    DRAFT_PICKS_FILE,
    DRAFT_PROSPECTS_FILE,
    ESPN_DRAFT_TEAMS_URL,
    ESPN_COACHES_URL,
    FUTURE_PICKS_FILE,
    FANTASYDATA_NBA_ODDS_URL,
    FOXSPORTS_ARTICLE_URL_TEMPLATE,
    GAME_BOXSCORES_FILE,
    GENERAL_MANAGERS_FILE,
    HOOPSHYPE_TEAM_URL_TEMPLATE,
    NBA_2026_DRAFT_BOARD_URL,
    NBA_OFFICIAL_STAFF_FILE,
    NBA_TEAM_INFO_URL_TEMPLATE,
    SPOTRAC_FUTURE_PICKS_URL,
    ESPN_SUMMARY_URL_TEMPLATE,
    NBA_STATS_TRACKING_QUICKLINKS_URL,
    ROOKIE_SCALE_2026_CONSENSUS_URL,
    TRACKING_SOURCES_FILE,
    STAFF_FILE,
    TANKATHON_2026_MOCK_DRAFT_URL,
    WIKIPEDIA_GENERAL_MANAGERS_URL,
)
from .schema import (
    CANONICAL_SEASON,
    CANONICAL_START_DATE,
    CanonicalUniverse,
    Contract,
    DraftBoardEntry,
    DraftClass,
    DraftPick,
    DraftProspect,
    DraftProspectTrait,
    GameplayStaffSlot,
    Player,
    PlayerContractMarketProfile,
    PlayerContractPreference,
    RosterSlot,
    ScoutingReport,
    SourceEvidence,
    StaffProfile,
    Team,
    TeamProfile,
    to_plain,
)
from .teams import TEAM_INFO
from .traits import (
    LEAGUE_TRAIT_RATINGS_SOURCE_ID,
    PERCENTILE_FIELDS,
    apply_league_trait_calibration,
    build_traits_for_player,
    load_league_trait_ratings,
)
from .transactions import (
    build_front_office_profiles,
    build_player_asset_valuations,
    build_team_strategic_states,
    build_trade_block_entries,
    load_front_office_overrides,
    load_transaction_model_config,
)
from .utils import clamp, maybe_float, normalize_name, parse_inches, percentile_maps, read_text, sentences, slugify, stable_id


RAW_PLAYER_INPUT = Path("Player Stats/player_skill_input_2025_26.json")
RAW_PLAYER_STATS = Path("Player Stats/player_stats.json")
RAW_SCHEDULE = Path("NBA Schedule/schedule_v2025_2026.json")
RAW_MINUTES = Path("NBA Schedule/real_game_minutes_2025_26.json")
RAW_GRAVITY = Path("Computed Stats From Previous Project/player_gravity_profiles_adjusted_2025_26.json")
RAW_MANIFESTOS = Path("Pre-Season manifestos")
OVERRIDES_DIR = Path("data/overrides")
STAFF_OVERRIDES_FILE = OVERRIDES_DIR / "staff_overrides.json"
PLAYER_OVERRIDES_FILE = OVERRIDES_DIR / "player_overrides.json"
TRAIT_OVERRIDES_FILE = OVERRIDES_DIR / "trait_overrides.json"
LEAGUE_TRAIT_RATINGS_FILE = OVERRIDES_DIR / "league_trait_ratings_2026_06_20.csv"
CONTRACT_OVERRIDES_FILE = OVERRIDES_DIR / "contract_overrides.json"
GAMEPLAY_STAFF_SEED_FILE = OVERRIDES_DIR / "gameplay_staff_seed.json"
PLAYER_HEALTH_OVERRIDES_FILE = OVERRIDES_DIR / "player_health_overrides.json"
INJURY_MODEL_CONFIG_FILE = OVERRIDES_DIR / "injury_model_config.json"
FRONT_OFFICE_OVERRIDES_FILE = OVERRIDES_DIR / "front_office_overrides.json"
TRANSACTION_MODEL_CONFIG_FILE = OVERRIDES_DIR / "transaction_model_config.json"
GAMEPLAY_STAFF_SLOTS = [
    "head_coach",
    "offensive_coordinator",
    "defensive_coordinator",
    "development_lead",
    "scouting_lead",
    "performance_lead",
]


def load_json(root: Path, relative: Path) -> Any:
    with (root / relative).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_optional_json(root: Path, relative: Path) -> Any | None:
    path = root / relative
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_universe(root: str | Path = ".") -> CanonicalUniverse:
    root = Path(root).resolve()
    player_input = load_json(root, RAW_PLAYER_INPUT)
    source_generated_at = player_input.get("generatedAt") or CANONICAL_START_DATE
    research_contracts = load_optional_json(root, CONTRACTS_FILE)
    research_staff = load_optional_json(root, STAFF_FILE)
    research_official_staff = load_optional_json(root, NBA_OFFICIAL_STAFF_FILE)
    research_coaches = load_optional_json(root, COACHES_FILE)
    research_general_managers = load_optional_json(root, GENERAL_MANAGERS_FILE)
    research_draft_picks = load_optional_json(root, DRAFT_PICKS_FILE)
    research_draft_prospects = load_optional_json(root, DRAFT_PROSPECTS_FILE)
    research_future_picks = load_optional_json(root, FUTURE_PICKS_FILE)
    staff_overrides = load_optional_json(root, STAFF_OVERRIDES_FILE) or {}
    player_overrides = load_optional_json(root, PLAYER_OVERRIDES_FILE) or {}
    trait_overrides = load_optional_json(root, TRAIT_OVERRIDES_FILE) or {}
    contract_overrides = load_optional_json(root, CONTRACT_OVERRIDES_FILE) or {}
    gameplay_staff_seed = load_optional_json(root, GAMEPLAY_STAFF_SEED_FILE) or {}
    player_health_overrides = load_optional_json(root, PLAYER_HEALTH_OVERRIDES_FILE) or {}
    league_trait_ratings = load_league_trait_ratings(root / LEAGUE_TRAIT_RATINGS_FILE)
    injury_model_config = load_injury_model_config(root)
    front_office_overrides = load_front_office_overrides(root)
    transaction_model_config = load_transaction_model_config(root)
    contract_market_config = load_contract_market_config(root)
    draft_model_config = load_draft_model_config(root)
    player_rows: list[dict[str, Any]] = list(player_input["players"])
    source_ids = build_source_registry(
        root,
        player_input,
        research_contracts,
        research_staff,
        research_official_staff,
        research_coaches,
        research_general_managers,
        research_draft_picks,
        research_draft_prospects,
        research_future_picks,
    )
    teams = build_teams(player_rows)
    players = build_players(player_rows, player_overrides)
    roster_slots = build_roster_slots(players)
    percentiles = percentile_maps(player_rows, PERCENTILE_FIELDS)
    traits = []
    for idx, row in enumerate(player_rows):
        player = players[idx]
        traits.extend(build_traits_for_player(row, idx, player.id, percentiles))
    traits, rating_calibration_report = apply_league_trait_calibration(traits, players, league_trait_ratings)
    traits = apply_trait_overrides(traits, players, trait_overrides)
    contracts = build_contracts(players, research_contracts, contract_overrides)
    draft_picks = build_draft_picks(teams, research_draft_picks, research_future_picks)
    staff_profiles = build_staff_profiles(teams, research_staff, research_official_staff, research_coaches, research_general_managers, staff_overrides)
    team_profiles = build_team_profiles(root, teams, players)
    gameplay_staff_slots = build_gameplay_staff_slots(teams, team_profiles, gameplay_staff_seed)
    player_health_profiles, player_health_states, injury_events = build_health_records(
        players,
        player_rows,
        traits,
        player_health_overrides,
        injury_model_config,
    )
    development_events = []
    front_office_profiles = build_front_office_profiles(teams, team_profiles, front_office_overrides)
    transaction_seed = {
        "teams": to_plain(teams),
        "players": to_plain(players),
        "traits": to_plain(traits),
        "contracts": to_plain(contracts),
        "draft_picks": to_plain(draft_picks),
        "team_profiles": to_plain(team_profiles),
        "player_health_profiles": to_plain(player_health_profiles),
        "player_health_states": to_plain(player_health_states),
        "front_office_profiles": to_plain(front_office_profiles),
    }
    player_asset_valuations = build_player_asset_valuations(transaction_seed, transaction_model_config)
    transaction_seed["player_asset_valuations"] = to_plain(player_asset_valuations)
    team_strategic_states = build_team_strategic_states(transaction_seed, player_asset_valuations, transaction_model_config)
    transaction_seed["team_strategic_states"] = to_plain(team_strategic_states)
    player_contract_market_profiles = build_player_contract_market_profiles(transaction_seed, contract_market_config)
    transaction_seed["player_contract_market_profiles"] = to_plain(player_contract_market_profiles)
    player_contract_preferences = build_player_contract_preferences(transaction_seed, player_contract_market_profiles, contract_market_config)
    transaction_seed["player_contract_preferences"] = to_plain(player_contract_preferences)
    extension_candidates = build_extension_candidates(transaction_seed, player_contract_market_profiles, contract_market_config)
    transaction_seed["extension_candidates"] = to_plain(extension_candidates)
    free_agent_candidates = build_free_agent_candidates(transaction_seed, player_contract_market_profiles, contract_market_config)
    transaction_seed["free_agent_candidates"] = to_plain(free_agent_candidates)
    trade_block_entries = build_trade_block_entries(transaction_seed, team_strategic_states, player_asset_valuations, transaction_model_config)
    transaction_seed["trade_block_entries"] = to_plain(trade_block_entries)
    transaction_seed["gameplay_staff_slots"] = to_plain(gameplay_staff_slots)
    draft_context = build_draft_context(transaction_seed, research_draft_prospects, draft_model_config)
    draft_classes = [DraftClass(**item) for item in draft_context["draft_classes"]]
    draft_prospects = [DraftProspect(**item) for item in draft_context["draft_prospects"]]
    draft_prospect_traits = [DraftProspectTrait(**item) for item in draft_context["draft_prospect_traits"]]
    scouting_reports = [ScoutingReport(**item) for item in draft_context["scouting_reports"]]
    draft_board_entries = [DraftBoardEntry(**item) for item in draft_context["draft_board_entries"]]
    coverage_report = build_coverage_report(
        players=players,
        teams=teams,
        traits=traits,
        contracts=contracts,
        draft_picks=draft_picks,
        draft_classes=draft_classes,
        draft_prospects=draft_prospects,
        draft_prospect_traits=draft_prospect_traits,
        scouting_reports=scouting_reports,
        draft_board_entries=draft_board_entries,
        staff_profiles=staff_profiles,
        gameplay_staff_slots=gameplay_staff_slots,
        team_profiles=team_profiles,
        player_health_profiles=player_health_profiles,
        player_health_states=player_health_states,
        injury_events=injury_events,
        development_events=development_events,
        front_office_profiles=front_office_profiles,
        team_strategic_states=team_strategic_states,
        player_asset_valuations=player_asset_valuations,
        player_contract_market_profiles=player_contract_market_profiles,
        player_contract_preferences=player_contract_preferences,
        extension_candidates=extension_candidates,
        free_agent_candidates=free_agent_candidates,
        trade_block_entries=trade_block_entries,
        generated_at=source_generated_at,
    )
    meta = {
        "id": "universe_2025_26_preseason",
        "season": CANONICAL_SEASON,
        "canonical_start_date": CANONICAL_START_DATE,
        "generated_at": source_generated_at,
        "philosophy": "Public/cited, rotation-first, confidence-aware. Raw inputs are ingestion sources, not canonical truth.",
        "rating_calibration_report": rating_calibration_report,
        "counts": {
            "sources": len(source_ids),
            "teams": len(teams),
            "players": len(players),
            "roster_slots": len(roster_slots),
            "traits": len(traits),
            "contracts": len(contracts),
            "draft_picks": len(draft_picks),
            "draft_classes": len(draft_classes),
            "draft_prospects": len(draft_prospects),
            "draft_prospect_traits": len(draft_prospect_traits),
            "scouting_reports": len(scouting_reports),
            "draft_board_entries": len(draft_board_entries),
            "staff_profiles": len(staff_profiles),
            "gameplay_staff_slots": len(gameplay_staff_slots),
            "team_profiles": len(team_profiles),
            "player_health_profiles": len(player_health_profiles),
            "player_health_states": len(player_health_states),
            "injury_events": len(injury_events),
            "development_events": len(development_events),
            "front_office_profiles": len(front_office_profiles),
            "team_strategic_states": len(team_strategic_states),
            "player_asset_valuations": len(player_asset_valuations),
            "player_contract_market_profiles": len(player_contract_market_profiles),
            "player_contract_preferences": len(player_contract_preferences),
            "extension_candidates": len(extension_candidates),
            "free_agent_candidates": len(free_agent_candidates),
            "trade_block_entries": len(trade_block_entries),
        },
    }
    return CanonicalUniverse(
        meta=meta,
        sources=source_ids,
        teams=teams,
        players=players,
        roster_slots=roster_slots,
        traits=traits,
        contracts=contracts,
        draft_picks=draft_picks,
        draft_classes=draft_classes,
        draft_prospects=draft_prospects,
        draft_prospect_traits=draft_prospect_traits,
        scouting_reports=scouting_reports,
        draft_board_entries=draft_board_entries,
        staff_profiles=staff_profiles,
        gameplay_staff_slots=gameplay_staff_slots,
        team_profiles=team_profiles,
        player_health_profiles=player_health_profiles,
        player_health_states=player_health_states,
        injury_events=injury_events,
        development_events=development_events,
        front_office_profiles=front_office_profiles,
        team_strategic_states=team_strategic_states,
        player_asset_valuations=player_asset_valuations,
        player_contract_market_profiles=player_contract_market_profiles,
        player_contract_preferences=player_contract_preferences,
        extension_candidates=extension_candidates,
        free_agent_candidates=free_agent_candidates,
        trade_block_entries=trade_block_entries,
        coverage_report=coverage_report,
    )


def build_source_registry(
    root: Path,
    player_input: dict[str, Any],
    research_contracts: dict[str, Any] | None,
    research_staff: dict[str, Any] | None,
    research_official_staff: dict[str, Any] | None,
    research_coaches: dict[str, Any] | None,
    research_general_managers: dict[str, Any] | None,
    research_draft_picks: dict[str, Any] | None,
    research_draft_prospects: dict[str, Any] | None,
    research_future_picks: dict[str, Any] | None,
) -> list[SourceEvidence]:
    generated_at = player_input.get("generatedAt")
    sources = [
        SourceEvidence(
            id="src_player_skill_input_2025_26",
            title="Hybrid player skill input 2025-26",
            kind="local_raw_json",
            trust_level="mixed_raw_input",
            path=str((root / RAW_PLAYER_INPUT).resolve()),
            retrieved_at=generated_at,
            notes="Primary raw player corpus. Contains public stat augmentations, roles, physicals, play-type fields, and raw sim eligibility gates.",
        ),
        SourceEvidence(
            id="src_player_stats_json",
            title="Player stats export",
            kind="local_raw_json",
            trust_level="mixed_raw_input",
            path=str((root / RAW_PLAYER_STATS).resolve()),
            notes="Secondary player stats export used as a future reconciliation source.",
        ),
        SourceEvidence(
            id="src_schedule_2025_26",
            title="2025-26 NBA schedule export",
            kind="local_raw_json",
            trust_level="schedule_raw_input",
            path=str((root / RAW_SCHEDULE).resolve()),
            notes="Raw schedule source for future calendar simulation.",
        ),
        SourceEvidence(
            id="src_real_minutes_2025_26",
            title="Real game minutes 2025-26",
            kind="local_raw_json",
            trust_level="validation_raw_input",
            path=str((root / RAW_MINUTES).resolve()),
            notes="Real minutes source for replay/validation checks.",
        ),
        SourceEvidence(
            id="src_previous_gravity_attempt",
            title="Previous adjusted gravity profiles",
            kind="local_raw_json",
            trust_level="context_only_unvalidated",
            path=str((root / RAW_GRAVITY).resolve()),
            notes="Useful basketball context from an earlier attempt, but not canonical until revalidated.",
        ),
        SourceEvidence(
            id="src_manifestos",
            title="Pre-season team manifestos",
            kind="local_written_analysis",
            trust_level="subjective_team_context",
            path=str((root / RAW_MANIFESTOS).resolve()),
            notes="Team identity and narrative context converted into structured profiles where available.",
        ),
        SourceEvidence(
            id="src_bref_contracts_players_2026",
            title="Basketball-Reference 2025-26 NBA Player Contracts",
            kind="public_contract_table",
            trust_level="public_cited_research",
            path=str((root / CONTRACTS_FILE).resolve()) if (root / CONTRACTS_FILE).exists() else None,
            url=BREF_CONTRACTS_URL,
            retrieved_at=(research_contracts or {}).get("source", {}).get("fetched_at"),
            notes="Public salary table used to populate contract seasons, option markers, team, and guaranteed salary. Contract terms still need deeper CBA/legal review before trade validation.",
        ),
        SourceEvidence(
            id="src_hoopshype_salaries_players_2026",
            title="HoopsHype NBA player salaries",
            kind="public_salary_table",
            trust_level="public_cited_research",
            path=str((root / CONTRACTS_FILE).resolve()) if (root / CONTRACTS_FILE).exists() else None,
            url=HOOPSHYPE_TEAM_URL_TEMPLATE,
            retrieved_at=(research_contracts or {}).get("source", {}).get("fetched_at")
            if (research_contracts or {}).get("source", {}).get("id") == "src_hoopshype_salaries_players_2026"
            else None,
            notes="Public team salary pages used as a fallback when Basketball-Reference throttles scripted access. They provide salary years, option markers, and two-way markers, but not guaranteed-money detail.",
        ),
        SourceEvidence(
            id="src_nba_official_team_pages_2026",
            title="NBA.com team info pages",
            kind="official_team_pages",
            trust_level="official_public_research",
            path=str((root / NBA_OFFICIAL_STAFF_FILE).resolve()) if (root / NBA_OFFICIAL_STAFF_FILE).exists() else None,
            url=NBA_TEAM_INFO_URL_TEMPLATE,
            retrieved_at=(research_official_staff or {}).get("source", {}).get("fetched_at"),
            notes="Official NBA.com team pages used for coaching staff groups and background fields such as general manager and head coach.",
        ),
        SourceEvidence(
            id="src_espn_coaches_2026",
            title="ESPN NBA Coaches - 2026",
            kind="public_coaches_page",
            trust_level="public_cited_research",
            path=str((root / COACHES_FILE).resolve()) if (root / COACHES_FILE).exists() else None,
            url=ESPN_COACHES_URL,
            retrieved_at=(research_coaches or {}).get("source", {}).get("fetched_at"),
            notes="Public coaches table used to verify head coach names, experience, team, and current season record where ESPN lists a non-vacant coach.",
        ),
        SourceEvidence(
            id="src_wikipedia_general_managers",
            title="Wikipedia list of NBA general managers",
            kind="public_general_manager_table",
            trust_level="public_cited_research",
            path=str((root / GENERAL_MANAGERS_FILE).resolve()) if (root / GENERAL_MANAGERS_FILE).exists() else None,
            url=WIKIPEDIA_GENERAL_MANAGERS_URL,
            retrieved_at=(research_general_managers or {}).get("source", {}).get("fetched_at"),
            notes="Public table used to verify listed general managers. Because Wikipedia is community-maintained, entries remain lower confidence than official team media guides.",
        ),
        SourceEvidence(
            id="src_bref_team_pages_2026",
            title="Basketball-Reference 2025-26 team pages",
            kind="public_team_pages",
            trust_level="public_cited_research",
            path=str((root / STAFF_FILE).resolve()) if (root / STAFF_FILE).exists() else None,
            url=BREF_TEAM_URL_TEMPLATE,
            retrieved_at=(research_staff or {}).get("source", {}).get("fetched_at"),
            notes="Public team pages used to verify head coach and top executive names.",
        ),
        SourceEvidence(
            id="src_espn_2026_draft_picks",
            title="ESPN 2026 NBA draft team/pick board",
            kind="public_draft_board",
            trust_level="public_cited_research",
            path=str((root / DRAFT_PICKS_FILE).resolve()) if (root / DRAFT_PICKS_FILE).exists() else None,
            url=ESPN_DRAFT_TEAMS_URL,
            retrieved_at=(research_draft_picks or {}).get("source", {}).get("fetched_at"),
            notes="Public 2026 draft board used to populate current 2026 pick owner, original-team inference, and trade notes. It does not replace a complete future-pick ledger.",
        ),
        SourceEvidence(
            id="src_tankathon_2026_mock_draft",
            title="Tankathon 2026 NBA Mock Draft",
            kind="public_draft_prospect_board",
            trust_level="public_cited_research",
            path=str((root / DRAFT_PROSPECTS_FILE).resolve()) if (root / DRAFT_PROSPECTS_FILE).exists() else None,
            url=TANKATHON_2026_MOCK_DRAFT_URL,
            retrieved_at=(research_draft_prospects or {}).get("source", {}).get("fetched_at"),
            notes="Free public mock board used for 2026 prospect order, physicals, school/class context, and public stat snippets. It is a scouting input, not immutable truth.",
        ),
        SourceEvidence(
            id="src_rookie_scale_2026_consensus_board",
            title="Rookie Scale 2026 consensus board",
            kind="public_draft_prospect_board",
            trust_level="public_cited_research",
            path=str((root / DRAFT_PROSPECTS_FILE).resolve()) if (root / DRAFT_PROSPECTS_FILE).exists() else None,
            url=ROOKIE_SCALE_2026_CONSENSUS_URL,
            retrieved_at=(research_draft_prospects or {}).get("source", {}).get("fetched_at"),
            notes="Free public consensus board merged into 2026 prospects where names match. It supports rank ranges, physicals, age, and team/class cross-checks.",
        ),
        SourceEvidence(
            id="src_nba_2026_draft_board",
            title="NBA.com 2026 Draft Board",
            kind="public_draft_prospect_board",
            trust_level="public_cited_research",
            path=str((root / DRAFT_PROSPECTS_FILE).resolve()) if (root / DRAFT_PROSPECTS_FILE).exists() else None,
            url=NBA_2026_DRAFT_BOARD_URL,
            retrieved_at=(research_draft_prospects or {}).get("source", {}).get("fetched_at"),
            notes="Registered free public draft-board source for corroborating/manual review. Automated v1 prospect rows currently come from Tankathon plus Rookie Scale.",
        ),
        SourceEvidence(
            id="src_draft_model_config_v1",
            title="Draft generation, scouting, and AI draft model config v1",
            kind="local_model_config",
            trust_level="inferred_defaulted",
            path=str((root / DRAFT_MODEL_CONFIG_FILE).resolve()) if (root / DRAFT_MODEL_CONFIG_FILE).exists() else None,
            notes="Deterministic future-class generation, scouting fog, team draft-board, BPA/need, rookie-contract value, and draft-night trade tuning constants.",
        ),
        SourceEvidence(
            id="src_spotrac_future_picks",
            title="Spotrac NBA Future Draft Picks",
            kind="public_future_pick_reference",
            trust_level="public_cited_research",
            path=str((root / FUTURE_PICKS_FILE).resolve()) if (root / FUTURE_PICKS_FILE).exists() else None,
            url=SPOTRAC_FUTURE_PICKS_URL,
            retrieved_at=(research_future_picks or {}).get("source", {}).get("fetched_at"),
            notes="Public future-pick reference used to populate 2027-2032 owner-side first-round assets and protection notes. Second-round assignments remain a separate ledger pass.",
        ),
        SourceEvidence(
            id="src_realgm_future_pick_pages",
            title="RealGM future draft pick pages",
            kind="public_future_pick_reference",
            trust_level="manual_research_needed",
            url="https://basketball.realgm.com/nba/draft/future_drafts/team",
            notes="Candidate source for full future-pick protections. Not automatically fetched in this workspace because direct scripted access returned a Cloudflare challenge.",
        ),
        SourceEvidence(
            id="src_critical_field_fallback_method_v1",
            title="Critical field fallback method v1",
            kind="local_method",
            trust_level="inferred_defaulted",
            notes="Heuristic fallback layer for missing raw critical fields. Each fallback carries value, confidence, method, and notes so future sims can use a value without hiding uncertainty.",
        ),
        SourceEvidence(
            id="src_trait_method_v1",
            title="Trait inference method v1",
            kind="local_method",
            trust_level="inferred_defaulted",
            notes="Transparent proxy model that converts public/raw stats into hidden basketball traits with confidence scores.",
        ),
        SourceEvidence(
            id=LEAGUE_TRAIT_RATINGS_SOURCE_ID,
            title="League-wide subjective player trait ratings, June 20 2026",
            kind="local_subjective_trait_prior",
            trust_level="human_reviewed_full_health_prior",
            path=str((root / LEAGUE_TRAIT_RATINGS_FILE).resolve()) if (root / LEAGUE_TRAIT_RATINGS_FILE).exists() else None,
            retrieved_at="2026-06-20",
            notes="Human-eye league ratings prior used only as a full-health calibration layer. Values are quantile-mapped into engine trait space, then manual overrides remain authoritative.",
        ),
        SourceEvidence(
            id="src_manual_overrides_2025_26",
            title="Manual 2025-26 preseason overrides",
            kind="local_manual_override",
            trust_level="authoritative_snapshot_override",
            path=str((root / OVERRIDES_DIR).resolve()) if (root / OVERRIDES_DIR).exists() else None,
            notes="Human-authored corrections for the intended 2025-26 preseason universe, including known snapshot facts and explicit ledger uncertainty.",
        ),
        SourceEvidence(
            id="src_gameplay_staff_seed_v1",
            title="Gameplay staff seed v1",
            kind="local_gameplay_seed",
            trust_level="fictional_gameplay_scaffold",
            path=str((root / GAMEPLAY_STAFF_SEED_FILE).resolve()) if (root / GAMEPLAY_STAFF_SEED_FILE).exists() else None,
            notes="Deterministic seed data for fictional game-facing staff slots. These staff are simulation scaffolds, not claims about real NBA org charts.",
        ),
        SourceEvidence(
            id="src_player_health_overrides_v1",
            title="Player health overrides v1",
            kind="local_manual_override",
            trust_level="confidence_scored_health_context",
            path=str((root / PLAYER_HEALTH_OVERRIDES_FILE).resolve()) if (root / PLAYER_HEALTH_OVERRIDES_FILE).exists() else None,
            notes="Lightweight star-only health history and startup injury flags for the sandbox health model. Non-stars use generic risk from the model config.",
        ),
        SourceEvidence(
            id="src_injury_model_config_v1",
            title="Injury and fatigue model config v1",
            kind="local_model_config",
            trust_level="inferred_defaulted",
            path=str((root / INJURY_MODEL_CONFIG_FILE).resolve()) if (root / INJURY_MODEL_CONFIG_FILE).exists() else None,
            notes="Quota-guided injury severity/body-area ranges and fatigue/recovery tuning constants for 2K-style sandbox health simulation.",
        ),
        SourceEvidence(
            id="src_development_model_v1",
            title="Monthly development model v1",
            kind="local_method",
            trust_level="inferred_defaulted",
            notes="Trait-level monthly growth/regression model from age, minutes, role, staff, coach development context, current trait level, and health. Player personality is deferred.",
        ),
        SourceEvidence(
            id="src_front_office_overrides_v1",
            title="Front office overrides v1",
            kind="local_manual_override",
            trust_level="gameplay_personality_seed",
            path=str((root / FRONT_OFFICE_OVERRIDES_FILE).resolve()) if (root / FRONT_OFFICE_OVERRIDES_FILE).exists() else None,
            notes="Team-specific front-office archetype and competence/personality overrides for bounded AI GM decisions.",
        ),
        SourceEvidence(
            id="src_transaction_model_config_v1",
            title="Transaction AI model config v1",
            kind="local_model_config",
            trust_level="inferred_defaulted",
            path=str((root / TRANSACTION_MODEL_CONFIG_FILE).resolve()) if (root / TRANSACTION_MODEL_CONFIG_FILE).exists() else None,
            notes="Trade valuation, team phase, practical legality, and bounded GM mistake/noise settings for v1 transaction AI.",
        ),
        SourceEvidence(
            id="src_contract_market_config_v1",
            title="Contract market and negotiation model config v1",
            kind="local_model_config",
            trust_level="inferred_defaulted",
            path=str((root / CONTRACT_MARKET_CONFIG_FILE).resolve()) if (root / CONTRACT_MARKET_CONFIG_FILE).exists() else None,
            notes="Salary comp bands, practical contract guardrails, inferred player priorities, and bounded negotiation behavior for extensions and free agency.",
        ),
        SourceEvidence(
            id="src_espn_game_boxscores_2025_26",
            title="ESPN NBA game summary box scores",
            kind="public_game_boxscores",
            trust_level="public_cited_research",
            path=str((root / GAME_BOXSCORES_FILE).resolve()) if (root / GAME_BOXSCORES_FILE).exists() else None,
            url=ESPN_SUMMARY_URL_TEMPLATE,
            notes="Game-level player minutes, DNP status, and traditional box score stats used for availability-aware validation replay.",
        ),
        SourceEvidence(
            id="src_espn_pickcenter_betting_odds_2025_26",
            title="ESPN PickCenter odds from NBA game summary endpoint",
            kind="public_betting_market_snapshot",
            trust_level="public_calibration_input",
            path=str((root / BETTING_ODDS_FILE).resolve()) if (root / BETTING_ODDS_FILE).exists() else None,
            url=ESPN_SUMMARY_URL_TEMPLATE,
            notes="Provider-neutral moneyline, spread, and total cache from ESPN PickCenter when exposed in game summaries. Missing games are recorded explicitly and never inferred.",
        ),
        SourceEvidence(
            id="src_fantasydata_public_nba_odds_2025_26",
            title="FantasyData public NBA odds table",
            kind="public_betting_market_snapshot",
            trust_level="public_calibration_input",
            path=str((root / BETTING_ODDS_FILE).resolve()) if (root / BETTING_ODDS_FILE).exists() else None,
            url=FANTASYDATA_NBA_ODDS_URL,
            notes="Secondary free public odds table used as a gap-filler for game-level consensus spread, moneyline, and total rows where it can be matched to schedule games.",
        ),
        SourceEvidence(
            id="src_foxsports_nba_odds_articles_2025_26",
            title="FOX Sports NBA prediction/odds articles",
            kind="public_betting_market_snapshot",
            trust_level="public_calibration_input",
            path=str((root / BETTING_ODDS_FILE).resolve()) if (root / BETTING_ODDS_FILE).exists() else None,
            url=FOXSPORTS_ARTICLE_URL_TEMPLATE,
            notes="Secondary free public odds articles used as a gap-filler for favorite, spread, total, moneyline, and limited points-prop rows where predictable article URLs resolve.",
        ),
        SourceEvidence(
            id="src_coach_reputation_sources_2025_26",
            title="Coach reputation source bundle 2025-26",
            kind="public_article_bundle",
            trust_level="qualitative_research",
            path=str((root / COACH_REPUTATION_FILE).resolve()) if (root / COACH_REPUTATION_FILE).exists() else None,
            notes="Soft source bundle for 0-5 star coach attributes. Coach effects are intentionally modest and tunable.",
        ),
        SourceEvidence(
            id="src_tracking_sources_2025_26",
            title="NBA tracking source registry 2025-26",
            kind="public_tracking_reference",
            trust_level="proxy_research",
            path=str((root / TRACKING_SOURCES_FILE).resolve()) if (root / TRACKING_SOURCES_FILE).exists() else None,
            url=NBA_STATS_TRACKING_QUICKLINKS_URL,
            notes="Reference registry for tracking categories such as touches, drives, speed/distance, passing, shot dashboards, defense, and hustle.",
        ),
        SourceEvidence(
            id="src_ledger_research_pending",
            title="Franchise ledger research queue",
            kind="research_pending",
            trust_level="not_yet_canonical",
            notes="Contracts, picks, and staff are scaffolded here until each item is researched against public cited sources.",
        ),
    ]
    return sources


def build_teams(player_rows: list[dict[str, Any]]) -> list[Team]:
    team_abbrevs = sorted({str(row.get("teamAbbrev") or row.get("Tm") or "").strip() for row in player_rows if row.get("teamAbbrev") or row.get("Tm")})
    teams: list[Team] = []
    for abbrev in team_abbrevs:
        name, conference, division = TEAM_INFO.get(abbrev, (abbrev, None, None))
        teams.append(
            Team(
                id=stable_id("team", abbrev),
                abbrev=abbrev,
                name=name,
                conference=conference,
                division=division,
                source_ids=["src_player_skill_input_2025_26"],
            )
        )
    return teams


def rotation_priority(row: dict[str, Any]) -> str:
    minutes = maybe_float(row.get("minutes")) or 0.0
    prior_minutes = maybe_float(row.get("2025minutes")) or 0.0
    age = maybe_float(row.get("Age") or row.get("AGE"))
    rookie = bool(row.get("Rookie"))
    if minutes >= 28:
        return "core_rotation"
    if minutes >= 18 or prior_minutes >= 1200:
        return "rotation"
    if minutes >= 10 and ((age is not None and age <= 23) or rookie):
        return "development_priority"
    if minutes >= 8:
        return "deep_rotation"
    return "fringe"


def build_players(player_rows: list[dict[str, Any]], player_overrides: dict[str, Any] | None = None) -> list[Player]:
    players: list[Player] = []
    seen: Counter[str] = Counter()
    for row in player_rows:
        name = str(row.get("name") or row.get("player") or "").strip()
        normalized = normalize_name(row.get("normalizedName") or name)
        team_abbrev = str(row.get("teamAbbrev") or row.get("Tm") or "").strip()
        override = player_override_for(normalized, player_overrides or {})
        if override.get("team_abbrev"):
            team_abbrev = override["team_abbrev"]
        age = maybe_float(override.get("age"))
        if age is None:
            age = maybe_float(row.get("Age") or row.get("AGE"))
        height_inches = maybe_float(override.get("height_inches"))
        if height_inches is None:
            height_inches = parse_inches(row.get("HeightSocks"))
        weight_lbs = maybe_float(override.get("weight_lbs"))
        if weight_lbs is None:
            weight_lbs = maybe_float(row.get("Weight"))
        wingspan_inches = maybe_float(override.get("wingspan_inches"))
        if wingspan_inches is None:
            wingspan_inches = parse_inches(row.get("Wingspan"))
        minutes_projection = maybe_float(override.get("minutes_projection"))
        if minutes_projection is None:
            minutes_projection = maybe_float(row.get("minutes")) or 0.0
        prior_minutes = maybe_float(override.get("prior_minutes"))
        if prior_minutes is None:
            prior_minutes = maybe_float(row.get("2025minutes"))
        base_slug = slugify(name)
        seen_key = f"{team_abbrev}:{base_slug}"
        seen[seen_key] += 1
        suffix = f"-{seen[seen_key]}" if seen[seen_key] > 1 else ""
        player_id = stable_id("player", team_abbrev, f"{base_slug}{suffix}")
        source_ids = ["src_player_skill_input_2025_26"]
        if override:
            source_ids.append("src_manual_overrides_2025_26")
        players.append(
            Player(
                id=player_id,
                name=name,
                normalized_name=normalized,
                slug=base_slug,
                team_id=stable_id("team", team_abbrev),
                team_abbrev=team_abbrev,
                position=row.get("position") or row.get("Pos"),
                age=age,
                birthdate=row.get("Birthdate"),
                height_inches=height_inches,
                weight_lbs=weight_lbs,
                wingspan_inches=wingspan_inches,
                minutes_projection=minutes_projection,
                prior_minutes=prior_minutes,
                primary_off_role=override.get("primary_off_role") or row.get("primaryOffRole"),
                secondary_off_role=override.get("secondary_off_role") or row.get("secondaryOffRole"),
                primary_def_role=override.get("primary_def_role") or row.get("primaryDefRole"),
                sim_eligible_raw=bool(row.get("simEligible")),
                missing_critical_fields=list(row.get("missingCriticalFields") or []),
                critical_field_fallbacks=build_critical_field_fallbacks(row),
                rotation_priority=rotation_priority(row),
                source_ids=source_ids,
            )
        )
    return players


def player_override_for(normalized_name: str, player_overrides: dict[str, Any]) -> dict[str, Any]:
    loose_name = loose_override_name_key(normalized_name)
    for override in player_overrides.get("players", []):
        override_name = normalize_name(override.get("player_name"))
        if override_name == normalized_name or loose_override_name_key(override_name) == loose_name:
            return override
    return {}


def loose_override_name_key(value: str) -> str:
    return normalize_name(value).replace("'", "").replace(" ", "")


def apply_trait_overrides(traits: list[Any], players: list[Player], trait_overrides: dict[str, Any]) -> list[Any]:
    if not trait_overrides.get("players"):
        return traits
    players_by_name = {player.normalized_name: player for player in players}
    players_by_loose_name = {loose_override_name_key(player.normalized_name): player for player in players}
    overrides_by_trait: dict[tuple[str, str], dict[str, Any]] = {}
    for player_override in trait_overrides.get("players", []):
        override_name = normalize_name(player_override.get("player_name"))
        player = players_by_name.get(override_name) or players_by_loose_name.get(loose_override_name_key(override_name))
        if not player:
            continue
        for trait_key, override in (player_override.get("traits") or {}).items():
            if isinstance(override, dict):
                overrides_by_trait[(player.id, trait_key)] = {**override, "player_name": player.name}
    updated = []
    for trait in traits:
        override = overrides_by_trait.get((trait.player_id, trait.trait_key))
        if not override:
            updated.append(trait)
            continue
        value = maybe_float(override.get("value"))
        if value is None:
            updated.append(trait)
            continue
        confidence = maybe_float(override.get("confidence"))
        source_ids = list(dict.fromkeys([*trait.source_ids, "src_manual_overrides_2025_26"]))
        components = {
            **trait.components,
            "manual_calibration": {
                "player_name": override.get("player_name"),
                "previous_value": trait.value,
                "override_value": round(clamp(value), 2),
                "notes": override.get("notes"),
            },
        }
        updated.append(
            replace(
                trait,
                value=round(clamp(value), 2),
                confidence=round(clamp(confidence if confidence is not None else trait.confidence, 0.0, 1.0), 3),
                source_kind="inferred_trait_model_v1_with_manual_calibration",
                source_ids=source_ids,
                notes=override.get("notes") or f"{trait.notes} Manual calibration applied.",
                components=components,
            )
        )
    return updated


def build_critical_field_fallbacks(row: dict[str, Any]) -> dict[str, Any]:
    fallbacks: dict[str, Any] = {}
    missing = list(row.get("missingCriticalFields") or [])
    for field_name in missing:
        fallback = fallback_for_field(row, field_name)
        fallback["source_ids"] = ["src_player_skill_input_2025_26", "src_critical_field_fallback_method_v1"]
        fallbacks[field_name] = fallback
    return fallbacks


def fallback_for_field(row: dict[str, Any], field_name: str) -> dict[str, Any]:
    direct_aliases = {
        "TSpct": ["TS%"],
        "USGpct": ["USG%"],
        "CraftedOPM": ["PCraftedOPM", "COPM", "OBPM", "OLEBRON"],
        "CraftedDPM": ["PCraftedDPM", "CDPM", "DBPM", "DLEBRON"],
        "boxCreationEst": ["BC"],
        "passerRating": ["PR"],
        "offensiveLoad": ["oLoad", "LOAD"],
    }
    for alias in direct_aliases.get(field_name, []):
        value = maybe_float(row.get(alias))
        if value is not None:
            return fallback_payload(value, 0.62, f"alias:{alias}", f"Filled from available alternate source field {alias}.")

    per75_sources = {
        "PTSp75": "PTS",
        "ASTp75": "AST",
        "TOVp75": "TOV",
        "ORBp75": "ORB",
        "DRBp75": "DRB",
        "STLp75": "STL",
        "BLKp75": "BLK",
        "FGAp75": "FGA",
        "3PAp75": "3PA",
        "FTAp75": "FTA",
    }
    if field_name in per75_sources:
        base = maybe_float(row.get(per75_sources[field_name]))
        minutes = maybe_float(row.get("MIN") or row.get("minutes"))
        if base is not None and minutes and minutes > 0:
            return fallback_payload(round(base / minutes * 75, 3), 0.55, "per75_from_minutes", f"Estimated from {per75_sources[field_name]} and minutes.")

    if field_name == "touches":
        minutes = maybe_float(row.get("minutes")) or maybe_float(row.get("MIN")) or 0.0
        role = str(row.get("primaryOffRole") or row.get("O_Role") or "").lower()
        role_rate = 48.0
        if "primary ball" in role:
            role_rate = 82.0
        elif "secondary" in role or "movement ball" in role:
            role_rate = 66.0
        elif "connector" in role or "versatile big" in role:
            role_rate = 54.0
        elif "movement shooter" in role:
            role_rate = 50.0
        elif "spot up" in role:
            role_rate = 38.0
        elif "rollman" in role:
            role_rate = 34.0
        offensive_load = maybe_float(row.get("offensiveLoad") or row.get("oLoad") or row.get("LOAD"))
        if offensive_load is not None:
            role_rate = (role_rate + offensive_load * 1.35) / 2
        return fallback_payload(round(minutes * role_rate, 1), 0.42, "role_minutes_touch_proxy", "Estimated from projected minutes, offensive role, and offensive-load proxy when available.")

    if field_name == "BBallIQ":
        passer = maybe_float(row.get("passerRating") or row.get("PR"))
        age = maybe_float(row.get("Age") or row.get("AGE"))
        role = str(row.get("primaryOffRole") or "") + " " + str(row.get("primaryDefRole") or "")
        value = 50.0
        components = []
        if passer is not None:
            components.append(passer)
        if age is not None:
            components.append(max(30.0, min(70.0, 38.0 + age)))
        if any(word in role.lower() for word in ["connector", "primary ball", "rim protector"]):
            components.append(62.0)
        if components:
            value = sum(components) / len(components)
        return fallback_payload(round(value, 2), 0.38, "role_age_passing_iq_proxy", "Estimated from passer rating, age/experience proxy, and role responsibility.")

    return fallback_payload(50.0, 0.18, "neutral_default", "No reliable proxy was available; defaulted to neutral and flagged low confidence.")


def fallback_payload(value: float, confidence: float, method: str, notes: str) -> dict[str, Any]:
    return {"value": value, "confidence": confidence, "method": method, "notes": notes}


def build_roster_slots(players: list[Player]) -> list[RosterSlot]:
    return [
        RosterSlot(
            id=stable_id("roster", player.team_id, player.id),
            team_id=player.team_id,
            player_id=player.id,
            status="active_or_camp_roster_unverified",
            rotation_priority=player.rotation_priority,
            minutes_projection=player.minutes_projection,
            source_ids=["src_player_skill_input_2025_26"],
        )
        for player in players
    ]


def build_contracts(players: list[Player], research_contracts: dict[str, Any] | None, contract_overrides: dict[str, Any] | None) -> list[Contract]:
    by_name_team: dict[tuple[str, str], dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_id = (research_contracts or {}).get("source", {}).get("id") or "src_ledger_research_pending"
    for contract in (research_contracts or {}).get("contracts", []):
        if contract.get("team_abbrev"):
            by_name_team[(contract["normalized_name"], contract["team_abbrev"])] = contract
        by_name[contract["normalized_name"]].append(contract)

    contracts: list[Contract] = []
    for player in players:
        override = contract_override_for_player(player, contract_overrides or {})
        extension_metadata = extension_metadata_for_player(player, contract_overrides or {})
        if override:
            contracts.append(contract_from_override(player, override, extension_metadata))
            continue
        match = by_name_team.get((player.normalized_name, player.team_abbrev))
        if match is None:
            candidates = by_name.get(player.normalized_name, [])
            if len(candidates) == 1:
                match = candidates[0]
        if match is None:
            match = fuzzy_contract_match(player, by_name_team)
        if match:
            seasons = [
                {
                    "season": season["season"],
                    "salary": season["salary"],
                    "option_type": season.get("option_type"),
                    "guarantee_status": "unknown_from_salary_table",
                }
                for season in match.get("seasons", [])
            ]
            salary_seasons = [season for season in seasons if season.get("salary") is not None]
            original_years = maybe_int(extension_metadata.get("original_contract_years")) or len(salary_seasons)
            signed_season = extension_metadata.get("signed_season") or (min((season["season"] for season in salary_seasons), default=None))
            if match.get("guaranteed") is not None:
                seasons.append({"season": "remaining_total", "guaranteed": match["guaranteed"], "salary": None, "option_type": None})
            contracts.append(
                Contract(
                    id=stable_id("contract", player.id),
                    player_id=player.id,
                    team_id=player.team_id,
                    status="verified_public_salary_table",
                    seasons=seasons,
                    confidence=0.82 if source_id == "src_bref_contracts_players_2026" else 0.72,
                    source_ids=[source_id],
                    notes="Matched to public salary table. Salary/options are cited where available; guarantee mechanics, incentives, cap holds, two-way status, and trade restrictions still need deeper ledger review.",
                    original_contract_years=original_years,
                    signed_season=signed_season,
                    extension_eligibility=extension_metadata,
                )
            )
        else:
            contracts.append(
                Contract(
                    id=stable_id("contract", player.id),
                    player_id=player.id,
                    team_id=player.team_id,
                    status="research_pending",
                    seasons=[],
                    confidence=0.0,
                    source_ids=["src_ledger_research_pending"],
                    notes="Contract years, salary, guarantees, options, and trade restrictions have not yet been matched to public sources.",
                    original_contract_years=maybe_int(extension_metadata.get("original_contract_years")),
                    signed_season=extension_metadata.get("signed_season"),
                    extension_eligibility=extension_metadata,
                )
            )
    return contracts


def contract_override_for_player(player: Player, contract_overrides: dict[str, Any]) -> dict[str, Any] | None:
    for override in contract_overrides.get("contracts", []):
        if override.get("team_abbrev") != player.team_abbrev:
            continue
        if normalize_name(override.get("player_name")) == player.normalized_name:
            return override
    return None


def extension_metadata_for_player(player: Player, contract_overrides: dict[str, Any]) -> dict[str, Any]:
    for metadata in contract_overrides.get("extension_eligibility", []):
        if normalize_name(metadata.get("player_name")) == player.normalized_name:
            return dict(metadata)
    return {}


def maybe_int(value: Any) -> int | None:
    number = maybe_float(value)
    return int(number) if number is not None else None


def contract_from_override(player: Player, override: dict[str, Any], extension_metadata: dict[str, Any] | None = None) -> Contract:
    extension_metadata = extension_metadata or {}
    return Contract(
        id=stable_id("contract", player.id),
        player_id=player.id,
        team_id=player.team_id,
        status=override.get("status") or "manual_research_pending",
        seasons=list(override.get("seasons") or []),
        confidence=maybe_float(override.get("confidence")) or 0.1,
        source_ids=["src_manual_overrides_2025_26"],
        notes=override.get("notes") or "Manual contract override. Exact cap/legal details remain intentionally unresolved.",
        original_contract_years=maybe_int(extension_metadata.get("original_contract_years")) or maybe_int(override.get("original_contract_years")),
        signed_season=extension_metadata.get("signed_season") or override.get("signed_season"),
        extension_eligibility=extension_metadata,
    )


def fuzzy_contract_match(player: Player, contracts_by_name_team: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any] | None:
    player_name = simplify_contract_name(player.normalized_name)
    best_score = 0.0
    best_contract: dict[str, Any] | None = None
    for (contract_name, team_abbrev), contract in contracts_by_name_team.items():
        if team_abbrev != player.team_abbrev:
            continue
        source_name = simplify_contract_name(contract_name)
        if not player_name or not source_name:
            continue
        score = SequenceMatcher(None, player_name, source_name).ratio()
        player_tokens = set(player_name.split())
        source_tokens = set(source_name.split())
        if player_tokens and source_tokens and (player_tokens <= source_tokens or source_tokens <= player_tokens):
            score = max(score, 0.93)
        if score > best_score:
            best_score = score
            best_contract = contract
    return best_contract if best_score >= 0.86 else None


def simplify_contract_name(name: str) -> str:
    text = name.replace("'", " ")
    for suffix in [" jr", " sr", " ii", " iii", " iv"]:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    aliases = {
        "nicolas": "nic",
        "santiago": "santi",
        "schroeder": "schroder",
        "deaaron": "de aaron",
        "kelel": "kel el",
        "dayron": "day ron",
        "ja kobe": "jakobe",
        "jabari smith": "jabari smith",
    }
    for src, dst in aliases.items():
        text = text.replace(src, dst)
    return " ".join(text.split())


def build_draft_picks(teams: list[Team], research_draft_picks: dict[str, Any] | None, research_future_picks: dict[str, Any] | None) -> list[DraftPick]:
    teams_by_abbrev = {team.abbrev: team for team in teams}
    picks: list[DraftPick] = []
    for pick in (research_draft_picks or {}).get("picks", []):
        owner = teams_by_abbrev.get(pick.get("owner_team_abbrev"))
        if not owner:
            continue
        original = teams_by_abbrev.get(pick.get("original_team_abbrev") or "")
        picks.append(
            DraftPick(
                id=stable_id("pick", "2026", pick["round"], pick["overall"], owner.abbrev),
                team_id=owner.id,
                season="2026",
                round=int(pick["round"]),
                status="verified_2026_draft_board",
                original_team_id=original.id if original else None,
                current_owner_team_id=owner.id,
                protections=pick.get("trade_note"),
                confidence=0.78,
                source_ids=["src_espn_2026_draft_picks"],
                notes=f"2026 pick board entry: round {pick['round']}, pick {pick['pick']}, overall {pick['overall']}. Trade note from ESPN: {pick.get('trade_note') or 'own pick inferred'}.",
            )
        )
    covered_future_slots: set[tuple[str, str, int]] = set()
    future_index_counter: Counter[tuple[str, str, int]] = Counter()
    for pick in (research_future_picks or {}).get("picks", []):
        owner = teams_by_abbrev.get(pick.get("owner_team_abbrev"))
        if not owner:
            continue
        season = str(pick.get("season"))
        round_number = int(pick.get("round") or 1)
        if season < "2027" or season > "2032":
            continue
        original = teams_by_abbrev.get(pick.get("original_team_abbrev") or "")
        future_index_counter[(owner.abbrev, season, round_number)] += 1
        asset_index = int(pick.get("asset_index") or future_index_counter[(owner.abbrev, season, round_number)])
        covered_future_slots.add((owner.abbrev, season, round_number))
        description = pick.get("description") or "Future pick asset listed by source."
        picks.append(
            DraftPick(
                id=stable_id("pick", "future", owner.abbrev, season, round_number, asset_index),
                team_id=owner.id,
                season=season,
                round=round_number,
                status="verified_future_pick_reference",
                original_team_id=original.id if original else None,
                current_owner_team_id=owner.id,
                protections=description,
                confidence=0.68,
                source_ids=["src_spotrac_future_picks"],
                notes=f"Owner-side future-pick asset from Spotrac. Description: {description}",
            )
        )
    picks = normalize_future_pick_ledger(picks)
    for team in teams:
        for season in ["2027", "2028", "2029", "2030", "2031", "2032"]:
            for round_number in [1, 2]:
                if (team.abbrev, season, round_number) in covered_future_slots:
                    continue
                second_round_scaffold = round_number == 2
                picks.append(
                    DraftPick(
                        id=stable_id("pick", team.abbrev, season, round_number),
                        team_id=team.id,
                        season=season,
                        round=round_number,
                        status="inferred_future_second_round_scaffold" if second_round_scaffold else "research_pending",
                        original_team_id=team.id,
                        current_owner_team_id=team.id if second_round_scaffold else None,
                        protections=None,
                        confidence=0.35 if second_round_scaffold else 0.0,
                        source_ids=["src_ledger_research_pending"],
                        notes=(
                            "Low-confidence future second-round scaffold: assigned to original team so v1 trades can use normal R2 currency. "
                            "Correct if later public research finds a traded/protected second."
                            if second_round_scaffold
                            else "Placeholder only. Ownership and protections must be researched before transaction logic uses this pick."
                        ),
                    )
                )
    return picks


def normalize_future_pick_ledger(picks: list[DraftPick]) -> list[DraftPick]:
    """Keep one gameplay asset for each underlying future team/year/round pick.

    Spotrac's owner-side lists can show both sides of a conditional obligation. They
    are useful research evidence, but treating each listing as a separate draft pick
    creates duplicate assets and lets a pick become its own fallback. The transferred
    record wins when present because it represents the currently tradeable right.
    """
    grouped: dict[tuple[str, int, str], list[tuple[int, DraftPick]]] = {}
    passthrough: list[tuple[int, DraftPick]] = []
    for index, pick in enumerate(picks):
        original = pick.original_team_id
        if pick.status != "verified_future_pick_reference" or not original:
            passthrough.append((index, pick))
            continue
        key = (str(pick.season), int(pick.round), original)
        grouped.setdefault(key, []).append((index, pick))

    normalized: list[tuple[int, DraftPick]] = list(passthrough)
    for (_, _, _), entries in grouped.items():
        def priority(entry: tuple[int, DraftPick]) -> tuple[int, int, int, float, str]:
            index, pick = entry
            description = str(pick.protections or "").lower()
            transferred = int(bool(pick.current_owner_team_id and pick.current_owner_team_id != pick.original_team_id))
            conditional = int(" if " in f" {description} " or "protected" in description)
            supported = int(not any(word in description for word in ("swap", "favorable", "conveys")))
            return (transferred, conditional, supported, float(pick.confidence or 0.0), f"{999999 - index:06d}")

        retained_index, retained = max(entries, key=priority)
        if len(entries) > 1:
            retained = replace(
                retained,
                notes=" ".join(
                    part
                    for part in [
                        str(retained.notes or "").strip(),
                        f"Gameplay ledger normalized {len(entries)} overlapping owner-side source entries into one underlying pick asset.",
                    ]
                    if part
                ),
            )
        normalized.append((retained_index, retained))
    return [pick for _, pick in sorted(normalized, key=lambda item: item[0])]


def build_staff_profiles(
    teams: list[Team],
    research_staff: dict[str, Any] | None,
    research_official_staff: dict[str, Any] | None,
    research_coaches: dict[str, Any] | None,
    research_general_managers: dict[str, Any] | None,
    staff_overrides: dict[str, Any] | None,
) -> list[StaffProfile]:
    staff_by_team = {entry.get("team_abbrev"): entry for entry in (research_staff or {}).get("teams", [])}
    official_by_team = {entry.get("team_abbrev"): entry for entry in (research_official_staff or {}).get("teams", [])}
    coaches_by_team = {entry.get("team_abbrev"): entry for entry in (research_coaches or {}).get("coaches", []) if entry.get("team_abbrev")}
    gms_by_team = {entry.get("team_abbrev"): entry for entry in (research_general_managers or {}).get("general_managers", [])}
    roles = ["head_coach", "assistant_pool", "front_office_identity"]
    staff: list[StaffProfile] = []
    for team in teams:
        for role in roles:
            override = staff_override_for_role(team.abbrev, role, staff_overrides or {})
            if override:
                staff.append(staff_profile_from_override(team, role, override))
                continue
            researched = staff_by_team.get(team.abbrev)
            official = official_by_team.get(team.abbrev) or {}
            espn_coach = coaches_by_team.get(team.abbrev)
            wiki_gm = gms_by_team.get(team.abbrev)
            official_groups = official.get("coaching_groups") or {}
            official_background = official.get("background") or {}
            if role == "head_coach" and official_groups.get("Head Coach"):
                staff.append(
                    StaffProfile(
                        id=stable_id("staff", team.abbrev, role),
                        team_id=team.id,
                        role=role,
                        name=official_groups["Head Coach"][0],
                        status="verified_official_team_page",
                        traits={"coaching_groups": official_groups, "background": official_background, "source_url": official.get("source_url")},
                        confidence=0.92,
                        source_ids=["src_nba_official_team_pages_2026"],
                        notes="Head coach verified from official NBA.com team page.",
                    )
                )
                continue
            if role == "head_coach" and espn_coach and espn_coach.get("coach"):
                staff.append(
                    StaffProfile(
                        id=stable_id("staff", team.abbrev, role),
                        team_id=team.id,
                        role=role,
                        name=espn_coach["coach"],
                        status="verified_public_coaches_page",
                        traits={"experience": espn_coach.get("experience"), "record": espn_coach.get("record"), "team_name": espn_coach.get("team_name")},
                        confidence=0.82,
                        source_ids=["src_espn_coaches_2026"],
                        notes="Head coach verified from ESPN NBA Coaches - 2026 table.",
                    )
                )
                continue
            if role == "head_coach" and researched and researched.get("coach"):
                coach = researched["coach"]
                staff.append(
                    StaffProfile(
                        id=stable_id("staff", team.abbrev, role),
                        team_id=team.id,
                        role=role,
                        name=coach["name"],
                        status="verified_public_team_page",
                        traits={"source_url": coach.get("url"), "raw": coach.get("raw")},
                        confidence=0.86,
                        source_ids=["src_bref_team_pages_2026"],
                        notes="Head coach verified from Basketball-Reference 2025-26 team page.",
                    )
                )
                continue
            if role == "assistant_pool" and official_groups.get("Assistant Coach"):
                assistants = official_groups["Assistant Coach"]
                staff.append(
                    StaffProfile(
                        id=stable_id("staff", team.abbrev, role),
                        team_id=team.id,
                        role=role,
                        name=", ".join(assistants),
                        status="verified_official_assistant_pool",
                        traits={"assistant_pool": assistants, "all_coaching_groups": official_groups, "source_url": official.get("source_url")},
                        confidence=0.82,
                        source_ids=["src_nba_official_team_pages_2026"],
                        notes="Official NBA.com page lists assistant-coach pool. This is real-world context only; game-facing coaching jobs are represented separately as gameplay staff slots.",
                    )
                )
                continue
            if role == "front_office_identity" and official_background.get("General Manager"):
                staff.append(
                    StaffProfile(
                        id=stable_id("staff", team.abbrev, role),
                        team_id=team.id,
                        role=role,
                        name=official_background["General Manager"],
                        status="verified_official_team_page",
                        traits={"background": official_background, "source_url": official.get("source_url")},
                        confidence=0.9,
                        source_ids=["src_nba_official_team_pages_2026"],
                        notes="General manager verified from official NBA.com team page background section.",
                    )
                )
                continue
            if role == "front_office_identity" and wiki_gm and wiki_gm.get("general_manager"):
                staff.append(
                    StaffProfile(
                        id=stable_id("staff", team.abbrev, role),
                        team_id=team.id,
                        role=role,
                        name=wiki_gm["general_manager"],
                        status="verified_public_general_manager_table",
                        traits={"date_of_hire": wiki_gm.get("date_of_hire"), "college": wiki_gm.get("college"), "team_name": wiki_gm.get("team_name")},
                        confidence=0.68,
                        source_ids=["src_wikipedia_general_managers"],
                        notes="General manager verified from Wikipedia's NBA general managers list. Use official team media guide where available for higher-confidence front-office hierarchy.",
                    )
                )
                continue
            if role == "front_office_identity" and researched and researched.get("executive"):
                executive = researched["executive"]
                staff.append(
                    StaffProfile(
                        id=stable_id("staff", team.abbrev, role),
                        team_id=team.id,
                        role=role,
                        name=executive["name"],
                        status="verified_public_team_page",
                        traits={"source_url": executive.get("url"), "raw": executive.get("raw")},
                        confidence=0.84,
                        source_ids=["src_bref_team_pages_2026"],
                        notes="Top executive verified from Basketball-Reference 2025-26 team page.",
                    )
                )
                continue
            staff.append(
                StaffProfile(
                    id=stable_id("staff", team.abbrev, role),
                    team_id=team.id,
                    role=role,
                    name=None,
                    status="research_pending",
                    traits={},
                    confidence=0.0,
                    source_ids=["src_ledger_research_pending"],
                    notes="Key staff role scaffold. Name, responsibilities, and style traits need public cited verification.",
                )
            )
    return staff


def staff_override_for_role(team_abbrev: str, role: str, staff_overrides: dict[str, Any]) -> dict[str, Any] | None:
    team_overrides = staff_overrides.get("teams", {}).get(team_abbrev, {})
    override = team_overrides.get(role)
    return override if isinstance(override, dict) else None


def staff_profile_from_override(team: Team, role: str, override: dict[str, Any]) -> StaffProfile:
    return StaffProfile(
        id=stable_id("staff", team.abbrev, role),
        team_id=team.id,
        role=role,
        name=override.get("name"),
        status=override.get("status") or "manual_snapshot_override",
        traits=dict(override.get("traits") or {}),
        confidence=maybe_float(override.get("confidence")) or 0.75,
        source_ids=["src_manual_overrides_2025_26"],
        notes=override.get("notes") or "Manual override for the intended 2025-26 preseason snapshot.",
    )


def build_gameplay_staff_slots(teams: list[Team], team_profiles: list[TeamProfile], seed: dict[str, Any] | None) -> list[GameplayStaffSlot]:
    seed = seed or {}
    profiles_by_team = {profile.team_id: profile for profile in team_profiles}
    slots: list[GameplayStaffSlot] = []
    for team in teams:
        profile = profiles_by_team.get(team.id)
        for slot in GAMEPLAY_STAFF_SLOTS:
            slot_seed = gameplay_slot_seed(seed, team.abbrev, slot)
            slots.append(
                GameplayStaffSlot(
                    id=stable_id("gameplay_staff", team.abbrev, slot),
                    team_id=team.id,
                    slot=slot,
                    name=slot_seed["name"],
                    archetype=slot_seed["archetype"],
                    style_tags=gameplay_style_tags(slot, profile, slot_seed),
                    skill_traits=gameplay_skill_traits(slot, team.abbrev, slot_seed),
                    personality_traits=gameplay_personality_traits(team.abbrev, slot, slot_seed),
                    status="fictional_gameplay_scaffold",
                    confidence=0.55,
                    source_ids=["src_gameplay_staff_seed_v1"],
                    notes="Fictional deterministic gameplay staff slot. This drives future sim systems and is not a claim about real NBA staff responsibilities.",
                )
            )
    return slots


def gameplay_slot_seed(seed: dict[str, Any], team_abbrev: str, slot: str) -> dict[str, Any]:
    team_slot = seed.get("teams", {}).get(team_abbrev, {}).get(slot)
    if isinstance(team_slot, dict):
        return {
            "name": team_slot.get("name") or deterministic_pick(seed.get("name_pool", []), team_abbrev, slot, "name"),
            "archetype": team_slot.get("archetype") or deterministic_pick(seed.get("archetypes", {}).get(slot, []), team_abbrev, slot, "archetype"),
            "style_tags": list(team_slot.get("style_tags") or []),
            "skill_biases": dict(team_slot.get("skill_biases") or {}),
            "personality_biases": dict(team_slot.get("personality_biases") or {}),
        }
    return {
        "name": deterministic_pick(seed.get("name_pool", []), team_abbrev, slot, "name"),
        "archetype": deterministic_pick(seed.get("archetypes", {}).get(slot, []), team_abbrev, slot, "archetype"),
        "style_tags": [],
        "skill_biases": {},
        "personality_biases": {},
    }


def deterministic_pick(values: list[Any], *parts: str) -> Any:
    if not values:
        fallback = " ".join(part.replace("_", " ").title() for part in parts[-2:])
        return fallback
    index = sum(ord(char) for char in "|".join(parts)) % len(values)
    return values[index]


def gameplay_style_tags(slot: str, profile: TeamProfile | None, slot_seed: dict[str, Any]) -> list[str]:
    tags = list(slot_seed.get("style_tags") or [])
    if profile:
        if slot in {"head_coach", "offensive_coordinator"}:
            tags.extend(profile.offensive_style[:2])
        if slot in {"head_coach", "defensive_coordinator"}:
            tags.extend(profile.defensive_style[:2])
        if slot == "scouting_lead":
            tags.extend(profile.strategic_behavior[:2])
        if slot == "development_lead" and profile.timeline and profile.timeline != "research_pending":
            tags.append(profile.timeline)
    tags.append(slot)
    return sorted(dict.fromkeys(tag for tag in tags if tag))


def gameplay_skill_traits(slot: str, team_abbrev: str, slot_seed: dict[str, Any]) -> dict[str, float]:
    keys_by_slot = {
        "head_coach": ["rotation_management", "locker_room", "scheme_balance"],
        "offensive_coordinator": ["shot_quality", "spacing_design", "player_usage"],
        "defensive_coordinator": ["coverage_design", "matchup_adjustment", "discipline"],
        "development_lead": ["skill_development", "prospect_patience", "feedback_clarity"],
        "scouting_lead": ["talent_eval", "risk_modeling", "international_coverage"],
        "performance_lead": ["injury_prevention", "conditioning", "recovery_planning"],
    }
    target = deterministic_staff_target(team_abbrev, slot)
    base = {}
    for idx, key in enumerate(keys_by_slot[slot]):
        base[key] = clamp_staff_trait(target + deterministic_staff_noise(team_abbrev, slot, key, idx) * 5.0)
    for key, value in slot_seed.get("skill_biases", {}).items():
        base[key] = clamp_trait(maybe_float(value) or base.get(key, 60))
    return base


def gameplay_personality_traits(team_abbrev: str, slot: str, slot_seed: dict[str, Any]) -> dict[str, float]:
    target = deterministic_staff_target(team_abbrev, slot)
    traits = {
        "adaptability": target + deterministic_staff_noise(team_abbrev, slot, "adaptability", 0) * 5.5,
        "communication": target + deterministic_staff_noise(team_abbrev, slot, "communication", 1) * 5.5,
        "ambition": target + deterministic_staff_noise(team_abbrev, slot, "ambition", 2) * 6.0,
    }
    for key, value in slot_seed.get("personality_biases", {}).items():
        traits[key] = clamp_trait(maybe_float(value) or traits.get(key, 60))
    return {key: clamp_trait(value) for key, value in traits.items()}


def deterministic_offset(*parts: str | int) -> int:
    text = "|".join(str(part) for part in parts)
    return (sum(ord(char) for char in text) % 15) - 7


def deterministic_staff_target(team_abbrev: str, slot: str) -> float:
    primary = deterministic_fraction(team_abbrev, slot, "staff_target")
    secondary = deterministic_fraction(team_abbrev, slot, "staff_target_tail")
    tertiary = deterministic_fraction(team_abbrev, slot, "staff_target_curve")
    bell = (primary + secondary + tertiary) / 3.0
    target = 62.0 + (bell - 0.5) * 34.0
    if primary > 0.94:
        target += 8.0
    elif primary < 0.06:
        target -= 5.0
    return round(max(50.0, min(83.0, target)), 2)


def deterministic_staff_noise(*parts: str | int) -> float:
    return (deterministic_fraction(*parts, "a") + deterministic_fraction(*parts, "b") + deterministic_fraction(*parts, "c")) - 1.5


def deterministic_fraction(*parts: str | int) -> float:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def clamp_trait(value: float) -> float:
    return round(max(1.0, min(99.0, value)), 2)


def clamp_staff_trait(value: float) -> float:
    return round(max(48.0, min(94.0, value)), 2)


def build_team_profiles(root: Path, teams: list[Team], players: list[Player]) -> list[TeamProfile]:
    by_team: dict[str, list[Player]] = defaultdict(list)
    for player in players:
        by_team[player.team_abbrev].append(player)
    profiles: list[TeamProfile] = []
    for team in teams:
        path = root / RAW_MANIFESTOS / f"{team.abbrev}.txt"
        if not path.exists():
            profiles.append(default_team_profile(team))
            continue
        text = read_text(path)
        team_sentences = sentences(text)
        names = detect_swing_players(team_sentences, by_team[team.abbrev])
        profiles.append(
            TeamProfile(
                id=stable_id("team_profile", team.abbrev),
                team_id=team.id,
                timeline=classify_timeline(text),
                identity=classify_identity(text),
                offensive_style=style_tags(text, "offense"),
                defensive_style=style_tags(text, "defense"),
                strengths=extract_sentences(team_sentences, ["elite", "best", "strength", "great", "dominant", "advantage"], limit=5),
                weaknesses=extract_sentences(team_sentences, ["problem", "issue", "weak", "lack", "question", "concern", "struggle"], limit=5),
                swing_players=names,
                front_office_pressure=classify_pressure(text),
                strategic_behavior=strategic_tags(text),
                confidence=0.62,
                source_ids=["src_manifestos"],
                notes="Heuristic v1 extraction from manifesto prose. Needs manual review before driving AI front-office behavior.",
            )
        )
    return profiles


def default_team_profile(team: Team) -> TeamProfile:
    return TeamProfile(
        id=stable_id("team_profile", team.abbrev),
        team_id=team.id,
        timeline="research_pending",
        identity="research_pending",
        offensive_style=[],
        defensive_style=[],
        strengths=[],
        weaknesses=[],
        swing_players=[],
        front_office_pressure="research_pending",
        strategic_behavior=[],
        confidence=0.0,
        source_ids=["src_ledger_research_pending"],
        notes="No manifesto was available for this team in the current corpus.",
    )


def classify_timeline(text: str) -> str:
    low = text.lower()
    if any(word in low for word in ["championship", "contender", "finals", "dynasty", "win now", "ring"]):
        if any(word in low for word in ["young", "future", "prospect", "draft capital"]):
            return "contending_with_future_upside"
        return "contending"
    if any(word in low for word in ["rebuild", "young core", "future", "development", "prospect"]):
        return "developing"
    if any(word in low for word in ["retool", "weird spot", "direction"]):
        return "retooling"
    return "unclear"


def classify_identity(text: str) -> str:
    low = text.lower()
    defense_count = low.count("defense") + low.count("defensive")
    offense_count = low.count("offense") + low.count("offensive")
    elite_defense = any(phrase in low for phrase in ["number one defense", "best defensive", "top 10 defense", "dominant defense", "defense first"])
    elite_offense = any(phrase in low for phrase in ["number one offense", "best offense", "top five offense", "elite offense", "offense first"])
    if elite_defense and elite_offense:
        return "defense_led_two_way_elite"
    if elite_defense:
        return "defense_first"
    if elite_offense:
        return "offense_first"
    if defense_count and offense_count:
        if defense_count > offense_count * 1.25:
            return "defense_first"
        if offense_count > defense_count * 1.25:
            return "offense_first"
        return "two_way_balance"
    if defense_count:
        return "defense_first"
    if offense_count:
        return "offense_first"
    return "research_pending"


def style_tags(text: str, side: str) -> list[str]:
    low = text.lower()
    tags: list[str] = []
    if side == "offense":
        checks = {
            "spacing": ["spacing", "three", "shooter", "shooting"],
            "rim_pressure": ["rim", "downhill", "free throw", "slash"],
            "pick_and_roll": ["pick and roll", "p&r"],
            "transition": ["transition", "pace", "speed"],
            "movement": ["movement", "off screen", "handoff"],
            "hub_big": ["hub", "sabonis", "jokic", "passing big"],
            "shot_creation_concern": ["lack shot creation", "shot creation", "creator"],
        }
    else:
        checks = {
            "rim_protection": ["rim protect", "paint", "shot blocker", "drop"],
            "switchability": ["switch", "versatile", "coverages"],
            "point_of_attack": ["point of attack", "perimeter", "fullcourt", "pressure"],
            "length_activity": ["length", "deflection", "athletic"],
            "scheme_versatility": ["scheme", "coverage", "lineup"],
        }
    for tag, needles in checks.items():
        if any(needle in low for needle in needles):
            tags.append(tag)
    return sorted(set(tags))


def extract_sentences(team_sentences: list[str], keywords: list[str], limit: int) -> list[str]:
    found: list[str] = []
    for sentence in team_sentences:
        low = sentence.lower()
        if any(keyword in low for keyword in keywords):
            found.append(sentence[:320])
        if len(found) >= limit:
            break
    return found


def detect_swing_players(team_sentences: list[str], players: list[Player]) -> list[str]:
    text = " ".join(team_sentences).lower()
    candidates = sorted(players, key=lambda p: p.minutes_projection, reverse=True)
    found: list[str] = []
    for player in candidates:
        pieces = player.name.lower().replace("-", " ").split()
        if not pieces:
            continue
        last = pieces[-1]
        first = pieces[0]
        if player.name.lower() in text or (len(last) > 4 and last in text) or (len(first) > 4 and first in text):
            found.append(player.name)
        if len(found) >= 8:
            break
    return found


def classify_pressure(text: str) -> str:
    low = text.lower()
    if any(word in low for word in ["championship", "ring", "finals", "win now", "curry", "prime"]):
        return "high"
    if any(word in low for word in ["play-in", "playoffs", "compete", "weird spot"]):
        return "medium"
    if any(word in low for word in ["future", "young", "development", "rebuild"]):
        return "low_to_medium"
    return "research_pending"


def strategic_tags(text: str) -> list[str]:
    low = text.lower()
    checks = {
        "protect_future_flexibility": ["future", "draft capital", "young"],
        "seek_primary_creator": ["lead creator", "number one", "shot creation"],
        "prioritize_defensive_identity": ["defense", "rim protect", "point of attack"],
        "manage_health_risk": ["injury", "health", "rehab"],
        "consolidate_depth": ["depth", "too many", "lineup choices"],
        "maximize_star_window": ["curry", "jokic", "championship", "prime"],
    }
    return sorted(tag for tag, needles in checks.items() if any(needle in low for needle in needles))
