from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .animation import (
    DEFAULT_BACKGROUND,
    DEFAULT_BG_SATURATION,
    DEFAULT_CELL_ASPECT,
    DEFAULT_FOREGROUND_A,
    DEFAULT_FOREGROUND_B,
    DEFAULT_FPS,
    DEFAULT_PROFILE,
    DEFAULT_RANDOMNESS,
    DEFAULT_SEGMENT_SECONDS,
    DEFAULT_TEXT_INPUT,
)
from .contract_ai import (
    apply_contract_to_save,
    contract_market_report,
    evaluate_signing,
    extension_candidates_report,
    free_agents_report,
    negotiate_extension,
    simulate_free_agency,
)
from .draft import (
    apply_draft_selection_to_save,
    draft_board_report,
    draft_class_payload,
    evaluate_draft_pick,
    find_draft_trade,
    generate_draft_order,
    generate_draft_class_records,
    pick_recommendations,
    project_rookie_contract,
    simulate_draft,
)
from .health import advance_development, health_player_report, health_team_report, simulate_health
from .ingest import build_universe
from .research import refresh_betting_odds_research, refresh_boxscore_research, refresh_coach_reputation_research, refresh_draft_prospect_research, refresh_research
from .save import (
    advance_save,
    advance_through_current_season,
    box_score_view,
    calendar_view,
    complete_offseason_and_rollover,
    create_league_save,
    ensure_league_save_defaults,
    hold_press_conference,
    league_events_view,
    league_leaders,
    league_standings,
    load_save,
    morale_report,
    offseason_status,
    pending_actions_view,
    playoff_picture,
    playoff_leaders,
    process_ai_actions,
    propose_trade_to_save,
    quick_sim_current_season,
    run_draft_lottery,
    save_status,
    simulate_playoff_round,
    social_feed_view,
    start_playoffs,
    team_dashboard,
    write_save,
)
from .play import run_play_session
from .schema import to_plain
from .sim import calibrate_market, coach_ratings, explain_game_probability, player_feature_vector, print_json, sim_game, team_feature_vector, validate, validate_game_probabilities, validate_season_probabilities
from .staff import evaluate_staff_hire, fire_staff_from_save, hire_staff_from_save, negotiate_staff_hire, resolve_team as resolve_staff_team, staff_market_report, staff_team_report
from .storage import JSON_FILENAME, load_universe_json, write_outputs
from .transactions import (
    apply_trade_to_save,
    evaluate_trade,
    find_trade,
    gm_report,
    parse_cli_assets,
    simulate_ai_trades,
    trade_block_report,
)
from .utils import normalize_name


DEFAULT_OUT = Path("data/canonical")


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".", help="Workspace root containing the raw data folders.")
    common.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory for canonical exports.")
    parser = argparse.ArgumentParser(description="Canonical NBA GM data foundation CLI.", parents=[common])
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build deterministic JSON, SQLite, and coverage exports.", parents=[common])
    build_parser.add_argument("--quiet", action="store_true", help="Only print output paths.")

    subparsers.add_parser("audit", help="Print coverage/audit summary from a fresh in-memory build.", parents=[common])

    player_parser = subparsers.add_parser("player", help="Inspect a canonical player by name.", parents=[common])
    player_parser.add_argument("name")
    player_parser.add_argument("--traits", action="store_true", help="Include trait values.")

    team_parser = subparsers.add_parser("team", help="Inspect a canonical team by abbreviation or name.", parents=[common])
    team_parser.add_argument("team")
    team_parser.add_argument("--staff", action="store_true", help="Include real staff context and gameplay staff slots.")

    source_parser = subparsers.add_parser("source", help="Inspect a source evidence record.", parents=[common])
    source_parser.add_argument("source_id")

    play_parser = subparsers.add_parser("play", help="Launch the interactive CLI GM mode.", parents=[common])
    play_parser.add_argument("--save", default=None)
    play_parser.add_argument("--team", default=None)
    play_parser.add_argument("--seed", type=int, default=1)

    new_save_parser = subparsers.add_parser("new-save", help="Create a deterministic league_save_v1 file.", parents=[common])
    new_save_parser.add_argument("--team", required=True)
    new_save_parser.add_argument("--save", required=True)
    new_save_parser.add_argument("--seed", type=int, default=1)
    new_save_parser.add_argument("--ai-difficulty", choices=["easy", "normal", "hard"], default="normal")

    save_status_parser = subparsers.add_parser("save-status", help="Inspect current save date, phase, legal actions, and pending decisions.", parents=[common])
    save_status_parser.add_argument("--save", required=True)

    calendar_parser = subparsers.add_parser("calendar", help="Inspect save calendar games and simulated status.", parents=[common])
    calendar_parser.add_argument("--save", required=True)
    calendar_parser.add_argument("--from", dest="from_date", default=None)
    calendar_parser.add_argument("--through", dest="through_date", default=None)

    box_score_parser = subparsers.add_parser("box-score", help="Inspect one saved simulated game box score.", parents=[common])
    box_score_parser.add_argument("--save", required=True)
    box_score_parser.add_argument("game_id")

    advance_save_parser = subparsers.add_parser("advance-save", help="Advance a league save through the calendar.", parents=[common])
    advance_save_parser.add_argument("--save", required=True)
    advance_save_parser.add_argument("--to", dest="to_date", default=None)
    advance_save_parser.add_argument("--next-event", action="store_true")
    advance_save_parser.add_argument("--seed", type=int, default=None)

    standings_parser = subparsers.add_parser("league-standings", help="Inspect save-state standings.", parents=[common])
    standings_parser.add_argument("--save", required=True)

    leaders_parser = subparsers.add_parser("league-leaders", help="Inspect save-state player stat leaders.", parents=[common])
    leaders_parser.add_argument("--save", required=True)
    leaders_parser.add_argument("--stat", default="points", choices=["points", "pts", "rebounds", "reb", "assists", "ast", "steals", "stl", "blocks", "blk", "fg3m"])
    leaders_parser.add_argument("--limit", type=int, default=10)

    dashboard_parser = subparsers.add_parser("team-dashboard", help="Inspect a save-state team dashboard.", parents=[common])
    dashboard_parser.add_argument("--save", required=True)
    dashboard_parser.add_argument("--team", required=True)

    actions_parser = subparsers.add_parser("save-actions", help="Inspect save-state pending user and AI decisions.", parents=[common])
    actions_parser.add_argument("--save", required=True)

    propose_trade_parser = subparsers.add_parser("propose-trade", help="Evaluate and store a trade proposal in a league save.", parents=[common])
    propose_trade_parser.add_argument("--save", required=True)
    propose_trade_parser.add_argument("--from", dest="from_team", required=True)
    propose_trade_parser.add_argument("--to", dest="to_team", required=True)
    propose_trade_parser.add_argument("--asset", action="append", required=True, help="FROM:player:Name, TO:player:Name, FROM:pick:PICK_ID, or TEAM:player:Name.")
    propose_trade_parser.add_argument("--seed", type=int, default=1)

    process_ai_parser = subparsers.add_parser("process-ai-actions", help="Review or execute conservative pending AI action bundles.", parents=[common])
    process_ai_parser.add_argument("--save", required=True)
    process_ai_parser.add_argument("--seed", type=int, default=1)
    process_ai_parser.add_argument("--limit", type=int, default=5)
    process_ai_parser.add_argument("--execute", action="store_true")

    sim_regular_parser = subparsers.add_parser("sim-regular-season", help="Advance the current save through the regular season.", parents=[common])
    sim_regular_parser.add_argument("--save", required=True)
    sim_regular_parser.add_argument("--seed", type=int, default=1)
    sim_regular_parser.add_argument("--no-ai", action="store_true")

    quick_sim_parser = subparsers.add_parser("quick-sim-season", help="Sim current season, playoffs, lottery, free agency scaffold, optionally rollover.", parents=[common])
    quick_sim_parser.add_argument("--save", required=True)
    quick_sim_parser.add_argument("--seed", type=int, default=1)
    quick_sim_parser.add_argument("--rollover", action="store_true")

    rollover_parser = subparsers.add_parser("rollover-season", help="Archive current season and generate the next season schedule.", parents=[common])
    rollover_parser.add_argument("--save", required=True)
    rollover_parser.add_argument("--seed", type=int, default=1)

    playoff_picture_parser = subparsers.add_parser("playoff-picture", help="Inspect save-state playoff picture.", parents=[common])
    playoff_picture_parser.add_argument("--save", required=True)

    start_playoffs_parser = subparsers.add_parser("start-playoffs", help="Create a playoff bracket from save standings.", parents=[common])
    start_playoffs_parser.add_argument("--save", required=True)
    start_playoffs_parser.add_argument("--seed", type=int, default=1)

    simulate_playoff_parser = subparsers.add_parser("simulate-playoff-round", help="Simulate the current playoff scaffold round.", parents=[common])
    simulate_playoff_parser.add_argument("--save", required=True)
    simulate_playoff_parser.add_argument("--seed", type=int, default=1)

    playoff_leaders_parser = subparsers.add_parser("playoff-leaders", help="Inspect save-state playoff stat leaders and Finals MVP.", parents=[common])
    playoff_leaders_parser.add_argument("--save", required=True)
    playoff_leaders_parser.add_argument("--stat", default="points", choices=["points", "pts", "rebounds", "reb", "assists", "ast", "steals", "stl", "blocks", "blk", "fg3m", "3pm"])
    playoff_leaders_parser.add_argument("--limit", type=int, default=10)

    draft_lottery_parser = subparsers.add_parser("run-draft-lottery", help="Generate and store a draft order from save state.", parents=[common])
    draft_lottery_parser.add_argument("--save", required=True)
    draft_lottery_parser.add_argument("--year", default="2026")
    draft_lottery_parser.add_argument("--seed", type=int, default=1)

    offseason_parser = subparsers.add_parser("offseason-status", help="Inspect save-state offseason scaffolds.", parents=[common])
    offseason_parser.add_argument("--save", required=True)

    morale_parser = subparsers.add_parser("morale", help="Inspect team and player morale in a save.", parents=[common])
    morale_parser.add_argument("--save", required=True)
    morale_parser.add_argument("--team", default=None)

    social_parser = subparsers.add_parser("social-feed", help="Inspect save-state social feed.", parents=[common])
    social_parser.add_argument("--save", required=True)
    social_parser.add_argument("--team", default=None)
    social_parser.add_argument("--limit", type=int, default=20)

    events_parser = subparsers.add_parser("league-events", help="Inspect factual save-state league events separate from social media.", parents=[common])
    events_parser.add_argument("--save", required=True)
    events_parser.add_argument("--kind", default=None)
    events_parser.add_argument("--limit", type=int, default=40)

    press_parser = subparsers.add_parser("hold-press-conference", help="Answer a press question and apply morale/social effects.", parents=[common])
    press_parser.add_argument("--save", required=True)
    press_parser.add_argument("--team", required=True)
    press_parser.add_argument("--topic", required=True)
    press_parser.add_argument("--tone", required=True, choices=["accountable", "optimistic", "deflect", "challenge"])
    press_parser.add_argument("--seed", type=int, default=1)

    staff_parser = subparsers.add_parser("staff", help="Inspect save-state gameplay staff.", parents=[common])
    staff_sub = staff_parser.add_subparsers(dest="staff_kind", required=True)
    staff_team = staff_sub.add_parser("team", help="Inspect one team's real context plus mutable gameplay staff.", parents=[common])
    staff_team.add_argument("team")
    staff_team.add_argument("--save", required=True)

    staff_market_parser = subparsers.add_parser("staff-market", help="Inspect deterministic save-state staff market.", parents=[common])
    staff_market_parser.add_argument("--save", required=True)
    staff_market_parser.add_argument("--slot", default=None)
    staff_market_parser.add_argument("--limit", type=int, default=None)

    evaluate_staff_parser = subparsers.add_parser("evaluate-staff-hire", help="Evaluate hiring a staff candidate into a slot.", parents=[common])
    evaluate_staff_parser.add_argument("staff_id")
    evaluate_staff_parser.add_argument("--team", required=True)
    evaluate_staff_parser.add_argument("--slot", required=True)
    evaluate_staff_parser.add_argument("--save", required=True)

    negotiate_staff_parser = subparsers.add_parser("negotiate-staff", help="Run deterministic staff hiring negotiation.", parents=[common])
    negotiate_staff_parser.add_argument("staff_id")
    negotiate_staff_parser.add_argument("--team", required=True)
    negotiate_staff_parser.add_argument("--slot", required=True)
    negotiate_staff_parser.add_argument("--save", required=True)
    negotiate_staff_parser.add_argument("--seed", type=int, default=1)

    hire_staff_parser = subparsers.add_parser("hire-staff", help="Apply an accepted pending staff negotiation to the save.", parents=[common])
    hire_staff_parser.add_argument("negotiation_id")
    hire_staff_parser.add_argument("--save", required=True)

    fire_staff_parser = subparsers.add_parser("fire-staff", help="Fire save-state staff and create an interim replacement.", parents=[common])
    fire_staff_parser.add_argument("--team", required=True)
    fire_staff_parser.add_argument("--slot", required=True)
    fire_staff_parser.add_argument("--save", required=True)

    research_parser = subparsers.add_parser("research-refresh", help="Fetch public research sources into data/research.", parents=[common])
    research_parser.add_argument("topic", nargs="?", choices=["foundation", "boxscores", "coaches", "odds", "draft-prospects"], default="foundation")
    research_parser.add_argument("--skip-network", action="store_true", help="Only verify cached research files exist.")
    research_parser.add_argument("--skip-staff", action="store_true", help="Refresh contracts and draft picks only.")
    research_parser.add_argument("--limit", type=int, default=None, help="Limit network fetches for research topics that support it.")
    research_parser.add_argument("--secondary-limit", type=int, default=80, help="Limit secondary odds source probes; use -1 for no secondary-source limit.")
    research_parser.add_argument("--full", action="store_true", help="Fetch the full schedule instead of only missing games where supported.")

    features_parser = subparsers.add_parser("features", help="Inspect v0 simulation feature vectors.", parents=[common])
    features_sub = features_parser.add_subparsers(dest="feature_kind", required=True)
    feature_player = features_sub.add_parser("player", help="Inspect player sim features.", parents=[common])
    feature_player.add_argument("name")
    feature_team = features_sub.add_parser("team", help="Inspect team sim features.", parents=[common])
    feature_team.add_argument("team")
    features_sub.add_parser("coaches", help="Inspect coach ratings.", parents=[common])

    sim_parser = subparsers.add_parser("sim-game", help="Simulate one scheduled game.", parents=[common])
    sim_parser.add_argument("game_id")
    sim_parser.add_argument("--mode", choices=["replay-real-minutes", "sandbox-sim"], default="replay-real-minutes")
    sim_parser.add_argument("--seed", type=int, default=1)

    validate_parser = subparsers.add_parser("validate-season", help="Run a replay-real-minutes validation pass.", parents=[common])
    validate_parser.add_argument("--through", default=None)
    validate_parser.add_argument("--seed", type=int, default=1)

    validate_playoffs_parser = subparsers.add_parser("validate-playoffs", help="Run playoff-tagged validation pass where playoff data exists.", parents=[common])
    validate_playoffs_parser.add_argument("--through", default=None)
    validate_playoffs_parser.add_argument("--seed", type=int, default=1)

    game_probs_parser = subparsers.add_parser("validate-game-probabilities", help="Run Monte Carlo probability calibration for one game.", parents=[common])
    game_probs_parser.add_argument("game_id")
    game_probs_parser.add_argument("--runs", type=int, default=1000)
    game_probs_parser.add_argument("--seed", type=int, default=1)
    game_probs_parser.add_argument("--mode", choices=["replay-real-minutes", "sandbox-sim"], default="replay-real-minutes")

    explain_parser = subparsers.add_parser("explain-game-probabilities", help="Explain a game's market-aware sim disagreement.", parents=[common])
    explain_parser.add_argument("game_id")
    explain_parser.add_argument("--runs", type=int, default=200)
    explain_parser.add_argument("--seed", type=int, default=1)
    explain_parser.add_argument("--mode", choices=["replay-real-minutes", "sandbox-sim"], default="replay-real-minutes")

    season_probs_parser = subparsers.add_parser("validate-season-probabilities", help="Run Monte Carlo probability calibration for a set of games.", parents=[common])
    season_probs_parser.add_argument("--through", default=None)
    season_probs_parser.add_argument("--runs", type=int, default=1000)
    season_probs_parser.add_argument("--seed", type=int, default=1)
    season_probs_parser.add_argument("--limit", type=int, default=None)
    season_probs_parser.add_argument("--playoffs", action="store_true")

    calibrate_parser = subparsers.add_parser("calibrate-market", help="Run holdout-aware market calibration diagnostics.", parents=[common])
    calibrate_parser.add_argument("--through", default=None)
    calibrate_parser.add_argument("--holdout-start", default=None)
    calibrate_parser.add_argument("--runs", type=int, default=1000)
    calibrate_parser.add_argument("--seed", type=int, default=1)
    calibrate_parser.add_argument("--limit", type=int, default=None)
    calibrate_parser.add_argument("--playoffs", action="store_true")
    calibrate_parser.add_argument("--scored-only", action="store_true", help="Only include market games with actual final scores.")

    health_parser = subparsers.add_parser("health", help="Inspect canonical player/team health state.", parents=[common])
    health_sub = health_parser.add_subparsers(dest="health_kind", required=True)
    health_player = health_sub.add_parser("player", help="Inspect a player's health profile and state.", parents=[common])
    health_player.add_argument("name")
    health_team = health_sub.add_parser("team", help="Inspect a team's health and performance staff context.", parents=[common])
    health_team.add_argument("team")

    simulate_health_parser = subparsers.add_parser("simulate-health", help="Run deterministic sandbox injuries, fatigue, recovery, and rust.", parents=[common])
    simulate_health_parser.add_argument("--from", dest="from_date", required=True)
    simulate_health_parser.add_argument("--through", dest="through_date", required=True)
    simulate_health_parser.add_argument("--seed", type=int, default=1)

    development_parser = subparsers.add_parser("advance-development", help="Generate deterministic monthly trait development events.", parents=[common])
    development_parser.add_argument("--month", required=True, help="Month in YYYY-MM format.")
    development_parser.add_argument("--seed", type=int, default=1)

    gm_parser = subparsers.add_parser("gm-report", help="Inspect AI GM/front-office strategy reports.", parents=[common])
    gm_sub = gm_parser.add_subparsers(dest="gm_kind", required=True)
    gm_team = gm_sub.add_parser("team", help="Inspect one team's GM report.", parents=[common])
    gm_team.add_argument("team")

    trade_block_parser = subparsers.add_parser("trade-block", help="Inspect inferred trade block entries.", parents=[common])
    trade_block_parser.add_argument("--team", default=None)

    find_trade_parser = subparsers.add_parser("find-trade", help="Generate trade candidates for or around a player.", parents=[common])
    find_trade_parser.add_argument("player")
    find_trade_parser.add_argument("--for-team", required=True)
    find_trade_parser.add_argument("--limit", type=int, default=10)
    find_trade_parser.add_argument("--seed", type=int, default=1)

    evaluate_trade_parser = subparsers.add_parser("evaluate-trade", help="Evaluate a two-team trade proposal.", parents=[common])
    evaluate_trade_parser.add_argument("--from", dest="from_team", required=True)
    evaluate_trade_parser.add_argument("--to", dest="to_team", required=True)
    evaluate_trade_parser.add_argument("--asset", action="append", required=True, help="FROM:player:Name, TO:player:Name, FROM:pick:PICK_ID, or TEAM:player:Name.")
    evaluate_trade_parser.add_argument("--seed", type=int, default=1)

    ai_trades_parser = subparsers.add_parser("simulate-ai-trades", help="Generate deterministic AI-AI trade candidates.", parents=[common])
    ai_trades_parser.add_argument("--from", dest="from_date", required=True)
    ai_trades_parser.add_argument("--through", dest="through_date", required=True)
    ai_trades_parser.add_argument("--seed", type=int, default=1)
    ai_trades_parser.add_argument("--limit", type=int, default=10)

    apply_trade_parser = subparsers.add_parser("apply-trade", help="Apply a pending trade proposal to a save-state ledger.", parents=[common])
    apply_trade_parser.add_argument("proposal_id")
    apply_trade_parser.add_argument("--save", required=True)

    contract_market_parser = subparsers.add_parser("contract-market", help="Inspect a player's contract-market estimate and preferences.", parents=[common])
    contract_market_sub = contract_market_parser.add_subparsers(dest="contract_market_kind", required=True)
    contract_market_player = contract_market_sub.add_parser("player", help="Inspect one player's contract market.", parents=[common])
    contract_market_player.add_argument("name")

    extension_candidates_parser = subparsers.add_parser("extension-candidates", help="Inspect v1 extension candidates.", parents=[common])
    extension_candidates_parser.add_argument("--team", default=None)

    negotiate_extension_parser = subparsers.add_parser("negotiate-extension", help="Run deterministic current-team extension negotiation.", parents=[common])
    negotiate_extension_parser.add_argument("player")
    negotiate_extension_parser.add_argument("--team", required=True)
    negotiate_extension_parser.add_argument("--seed", type=int, default=1)
    negotiate_extension_parser.add_argument("--max-rounds", type=int, default=3)

    free_agents_parser = subparsers.add_parser("free-agents", help="Inspect projected 2026 free agents.", parents=[common])
    free_agents_parser.add_argument("--team", default=None)
    free_agents_parser.add_argument("--position", default=None)

    evaluate_signing_parser = subparsers.add_parser("evaluate-signing", help="Evaluate a free-agent signing offer.", parents=[common])
    evaluate_signing_parser.add_argument("player")
    evaluate_signing_parser.add_argument("--team", required=True)
    evaluate_signing_parser.add_argument("--years", type=int, required=True)
    evaluate_signing_parser.add_argument("--aav", type=float, required=True, help="Annual value in millions unless greater than 1,000,000.")
    evaluate_signing_parser.add_argument("--seed", type=int, default=1)

    simulate_free_agency_parser = subparsers.add_parser("simulate-free-agency", help="Generate deterministic AI free-agent negotiations.", parents=[common])
    simulate_free_agency_parser.add_argument("--from", dest="from_date", required=True)
    simulate_free_agency_parser.add_argument("--through", dest="through_date", required=True)
    simulate_free_agency_parser.add_argument("--seed", type=int, default=1)
    simulate_free_agency_parser.add_argument("--limit", type=int, default=10)

    apply_contract_parser = subparsers.add_parser("apply-contract", help="Apply an accepted extension/signing negotiation to a save-state ledger.", parents=[common])
    apply_contract_parser.add_argument("negotiation_id")
    apply_contract_parser.add_argument("--save", required=True)

    generate_draft_class_parser = subparsers.add_parser("generate-draft-class", help="Generate a deterministic future draft class.", parents=[common])
    generate_draft_class_parser.add_argument("year")
    generate_draft_class_parser.add_argument("--seed", type=int, default=1)

    generate_draft_order_parser = subparsers.add_parser("generate-draft-order", help="Generate a deterministic draft lottery and pick order.", parents=[common])
    generate_draft_order_parser.add_argument("year")
    generate_draft_order_parser.add_argument("--seed", type=int, default=1)
    generate_draft_order_parser.add_argument("--standings", default=None, help="Optional JSON standings/order file for save-state seasons.")

    draft_class_parser = subparsers.add_parser("draft-class", help="Inspect a draft class and optional team scouting reports.", parents=[common])
    draft_class_parser.add_argument("year")
    draft_class_parser.add_argument("--seed", type=int, default=1)
    draft_class_parser.add_argument("--scouted-for", default=None)

    draft_board_parser = subparsers.add_parser("draft-board", help="Inspect a team's draft board.", parents=[common])
    draft_board_parser.add_argument("--team", required=True)
    draft_board_parser.add_argument("--year", default="2026")
    draft_board_parser.add_argument("--limit", type=int, default=20)

    evaluate_draft_pick_parser = subparsers.add_parser("evaluate-draft-pick", help="Evaluate one team/pick/prospect draft decision.", parents=[common])
    evaluate_draft_pick_parser.add_argument("--team", required=True)
    evaluate_draft_pick_parser.add_argument("--pick", required=True)
    evaluate_draft_pick_parser.add_argument("--prospect", required=True)
    evaluate_draft_pick_parser.add_argument("--seed", type=int, default=1)

    rookie_contract_parser = subparsers.add_parser("rookie-contract", help="Project rookie rights and rookie-scale contract from a pick/prospect.", parents=[common])
    rookie_contract_parser.add_argument("--team", required=True)
    rookie_contract_parser.add_argument("--pick", required=True)
    rookie_contract_parser.add_argument("--prospect", required=True)
    rookie_contract_parser.add_argument("--signed", action="store_true")

    pick_recommendations_parser = subparsers.add_parser("pick-recommendations", help="Recommend prospects for a team's pick.", parents=[common])
    pick_recommendations_parser.add_argument("--team", required=True)
    pick_recommendations_parser.add_argument("--pick", required=True)
    pick_recommendations_parser.add_argument("--limit", type=int, default=5)
    pick_recommendations_parser.add_argument("--seed", type=int, default=1)

    find_draft_trade_parser = subparsers.add_parser("find-draft-trade", help="Generate draft-night trade candidates for a pick.", parents=[common])
    find_draft_trade_parser.add_argument("--team", required=True)
    find_draft_trade_parser.add_argument("--pick", required=True)
    find_draft_trade_parser.add_argument("--limit", type=int, default=5)
    find_draft_trade_parser.add_argument("--seed", type=int, default=1)

    simulate_draft_parser = subparsers.add_parser("simulate-draft", help="Simulate a deterministic draft board selection pass.", parents=[common])
    simulate_draft_parser.add_argument("--year", required=True)
    simulate_draft_parser.add_argument("--seed", type=int, default=1)

    apply_draft_selection_parser = subparsers.add_parser("apply-draft-selection", help="Apply a pending draft selection to a save-state ledger.", parents=[common])
    apply_draft_selection_parser.add_argument("selection_id")
    apply_draft_selection_parser.add_argument("--save", required=True)
    apply_draft_selection_parser.add_argument("--sign-rookie", action="store_true", help="Mark the projected rookie contract as signed in the save ledger.")

    animation_parser = subparsers.add_parser("animation-cache", help="Pre-render ignored local MP4s into terminal ASCII loading frames.", parents=[common])
    animation_parser.add_argument("--video", default=None)
    animation_parser.add_argument("--seconds", type=int, default=DEFAULT_SEGMENT_SECONDS)
    animation_parser.add_argument("--segments", type=int, default=1, help="Render several evenly spaced slices from the source video for random loading-screen starts.")
    animation_parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    animation_parser.add_argument("--width", type=int, default=None)
    animation_parser.add_argument("--height", type=int, default=None)
    animation_parser.add_argument("--start", type=int, default=0)
    animation_parser.add_argument("--profile", default=DEFAULT_PROFILE)
    animation_parser.add_argument("--auto-size", action="store_true", help="Size the frame from the current terminal. This is also the default when width/height are omitted.")
    animation_parser.add_argument("--target-cols", type=int, default=None)
    animation_parser.add_argument("--target-rows", type=int, default=None)
    animation_parser.add_argument("--cell-aspect", type=float, default=DEFAULT_CELL_ASPECT)
    animation_parser.add_argument("--foreground-a", default=DEFAULT_FOREGROUND_A)
    animation_parser.add_argument("--foreground-b", default=DEFAULT_FOREGROUND_B)
    animation_parser.add_argument("--background", default=DEFAULT_BACKGROUND)
    animation_parser.add_argument("--bg-gradient", action="store_true", default=True)
    animation_parser.add_argument("--no-bg-gradient", action="store_false", dest="bg_gradient")
    animation_parser.add_argument("--bg-saturation", type=float, default=DEFAULT_BG_SATURATION)
    animation_parser.add_argument("--text-type", default="random-text")
    animation_parser.add_argument("--text-input", default=DEFAULT_TEXT_INPUT)
    animation_parser.add_argument("--threshold", type=int, default=0)
    animation_parser.add_argument("--invert", action="store_true")
    animation_parser.add_argument("--randomness", type=float, default=DEFAULT_RANDOMNESS)
    animation_parser.add_argument("--clear-cache", action="store_true", help="Delete existing animation caches before rendering this one.")

    animation_preview_parser = subparsers.add_parser("animation-preview", help="Preview the cached terminal loading animation.", parents=[common])
    animation_preview_parser.add_argument("--label", default="Previewing loading animation...")
    animation_preview_parser.add_argument("--seed", type=int, default=1)
    animation_preview_parser.add_argument("--seconds", type=float, default=5.0)

    args = parser.parse_args(argv)
    root = Path(args.root)
    out = Path(args.out)

    if args.command == "build":
        universe = build_universe(root)
        paths = write_outputs(universe, out)
        if args.quiet:
            for path in paths.values():
                print(path)
        else:
            print(f"Built {universe.meta['id']}")
            print(f"  JSON:     {paths['json']}")
            print(f"  SQLite:   {paths['sqlite']}")
            print(f"  Coverage: {paths['coverage']}")
            print_summary(universe.coverage_report.summary)
        return 0

    if args.command == "audit":
        universe = build_universe(root)
        print_summary(universe.coverage_report.summary)
        print_top_issues(to_plain(universe.coverage_report)["issues"])
        return 0

    if args.command == "research-refresh":
        if args.topic == "boxscores":
            print(refresh_boxscore_research(root, limit=args.limit, missing_only=not args.full))
            return 0
        if args.topic == "coaches":
            for path in refresh_coach_reputation_research(root):
                print(path)
            return 0
        if args.topic == "odds":
            secondary_limit = None if args.secondary_limit == -1 else args.secondary_limit
            print(refresh_betting_odds_research(root, limit=args.limit, secondary_limit=secondary_limit))
            return 0
        if args.topic == "draft-prospects":
            if args.skip_network:
                from .research import DRAFT_PROSPECTS_FILE

                path = root / DRAFT_PROSPECTS_FILE
                if not path.exists():
                    print(f"Missing cached research file: {path}", file=sys.stderr)
                    return 1
                print(path)
                return 0
            print(refresh_draft_prospect_research(root))
            return 0
        if args.skip_network:
            from .research import COACHES_FILE, CONTRACTS_FILE, DRAFT_PICKS_FILE, DRAFT_PROSPECTS_FILE, FUTURE_PICKS_FILE, GENERAL_MANAGERS_FILE, NBA_OFFICIAL_STAFF_FILE, STAFF_FILE

            for rel in [CONTRACTS_FILE, STAFF_FILE, NBA_OFFICIAL_STAFF_FILE, COACHES_FILE, GENERAL_MANAGERS_FILE, DRAFT_PICKS_FILE, DRAFT_PROSPECTS_FILE, FUTURE_PICKS_FILE]:
                path = root / rel
                if not path.exists():
                    print(f"Missing cached research file: {path}", file=sys.stderr)
                    return 1
                print(path)
            return 0
        for path in refresh_research(root, include_staff=not args.skip_staff):
            print(path)
        return 0

    if args.command == "animation-cache":
        from .animation import default_video_path, render_ascii_cache, segment_start_seconds

        if args.clear_cache:
            shutil.rmtree(root / ".cache" / "ascii_animation", ignore_errors=True)
        video = Path(args.video) if args.video else default_video_path(root)
        if video and not video.is_absolute():
            video = root / video
        starts = segment_start_seconds(video, segment_count=args.segments, seconds=args.seconds) if video else [args.start]
        results = [
            render_ascii_cache(
                root,
                args.video,
                seconds=args.seconds,
                fps=args.fps,
                width=args.width,
                height=args.height,
                start_seconds=start,
                profile=args.profile,
                auto_size=args.auto_size or (args.width is None and args.height is None),
                target_cols=args.target_cols,
                target_rows=args.target_rows,
                cell_aspect=args.cell_aspect,
                foreground_a=args.foreground_a,
                foreground_b=args.foreground_b,
                background=args.background,
                bg_gradient=args.bg_gradient,
                bg_saturation=args.bg_saturation,
                text_type=args.text_type,
                text_input=args.text_input,
                threshold=args.threshold,
                invert=args.invert,
                randomness=args.randomness,
            )
            for start in starts
        ]
        print_json(
            results[0] if args.segments <= 1 else {"status": "rendered_segments", "segments": len(results), "starts": starts, "results": results}
        )
        return 0
    if args.command == "animation-preview":
        from .animation import preview_animation

        preview_animation(root, args.label, seed=args.seed, seconds=args.seconds)
        return 0

    data = load_or_build(root, out)
    if args.command == "player":
        return print_player(data, args.name, include_traits=args.traits)
    if args.command == "team":
        return print_team(data, args.team, include_staff=args.staff)
    if args.command == "source":
        return print_source(data, args.source_id)
    if args.command == "play":
        return run_play_session(root, data, save_path=args.save, team=args.team, seed=args.seed)
    if args.command == "new-save":
        try:
            print_json(create_league_save(root, data, args.team, args.save, seed=args.seed, ai_difficulty=args.ai_difficulty))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "save-status":
        print_json(save_status(root, data, args.save))
        return 0
    if args.command == "calendar":
        print_json(calendar_view(root, data, args.save, from_date=args.from_date, through_date=args.through_date))
        return 0
    if args.command == "box-score":
        try:
            print_json(box_score_view(data, args.save, args.game_id))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "advance-save":
        try:
            print_json(advance_save(root, data, args.save, to_date=args.to_date, next_event=args.next_event, seed=args.seed))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "league-standings":
        print_json(league_standings(data, args.save))
        return 0
    if args.command == "league-leaders":
        print_json(league_leaders(data, args.save, stat=args.stat, limit=args.limit))
        return 0
    if args.command == "team-dashboard":
        try:
            print_json(team_dashboard(root, data, args.save, args.team))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "save-actions":
        print_json(pending_actions_view(data, args.save))
        return 0
    if args.command == "propose-trade":
        try:
            print_json(propose_trade_to_save(data, args.save, args.from_team, args.to_team, args.asset, seed=args.seed))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "process-ai-actions":
        print_json(process_ai_actions(data, args.save, seed=args.seed, execute=args.execute, limit=args.limit))
        return 0
    if args.command == "sim-regular-season":
        print_json(advance_through_current_season(root, data, args.save, seed=args.seed, process_ai=not args.no_ai))
        return 0
    if args.command == "quick-sim-season":
        print_json(quick_sim_current_season(root, data, args.save, seed=args.seed, rollover=args.rollover))
        return 0
    if args.command == "rollover-season":
        print_json(complete_offseason_and_rollover(root, data, args.save, seed=args.seed))
        return 0
    if args.command == "playoff-picture":
        print_json(playoff_picture(data, args.save))
        return 0
    if args.command == "start-playoffs":
        print_json(start_playoffs(data, args.save, seed=args.seed, include_play_in=True))
        return 0
    if args.command == "simulate-playoff-round":
        print_json(simulate_playoff_round(data, args.save, seed=args.seed, root=root))
        return 0
    if args.command == "playoff-leaders":
        print_json(playoff_leaders(data, args.save, stat=args.stat, limit=args.limit))
        return 0
    if args.command == "run-draft-lottery":
        print_json(run_draft_lottery(data, args.save, year=args.year, seed=args.seed))
        return 0
    if args.command == "offseason-status":
        print_json(offseason_status(data, args.save))
        return 0
    if args.command == "morale":
        print_json(morale_report(data, args.save, team_query=args.team))
        return 0
    if args.command == "social-feed":
        print_json(social_feed_view(data, args.save, team_query=args.team, limit=args.limit))
        return 0
    if args.command == "league-events":
        print_json(league_events_view(data, args.save, limit=args.limit, kind=args.kind))
        return 0
    if args.command == "hold-press-conference":
        try:
            print_json(hold_press_conference(data, args.save, args.team, args.topic, args.tone, seed=args.seed))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "staff":
        if args.staff_kind == "team":
            try:
                print_json(staff_team_report(data, ensure_league_save_defaults(load_save(args.save), data), args.team))
                return 0
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
    if args.command == "staff-market":
        print_json(staff_market_report(data, ensure_league_save_defaults(load_save(args.save), data), slot=args.slot, limit=args.limit))
        return 0
    if args.command == "evaluate-staff-hire":
        try:
            print_json(evaluate_staff_hire(data, load_save(args.save), args.staff_id, args.team, args.slot))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "negotiate-staff":
        try:
            save = load_save(args.save)
            result = negotiate_staff_hire(data, save, args.staff_id, args.team, args.slot, seed=args.seed)
            write_save(args.save, save)
            print_json(result)
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "hire-staff":
        save = load_save(args.save)
        result = hire_staff_from_save(save, args.negotiation_id)
        write_save(args.save, save)
        print_json(result)
        return 0
    if args.command == "fire-staff":
        try:
            save = load_save(args.save)
            team = resolve_staff_team(data, args.team)
            result = fire_staff_from_save(save, team["id"], args.slot)
            write_save(args.save, save)
            print_json(result)
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "features":
        return print_features(data, args)
    if args.command == "sim-game":
        print_json(sim_game(root, args.game_id, mode=args.mode, seed=args.seed))
        return 0
    if args.command == "validate-season":
        print_json(validate(root, through_date=args.through, playoffs=False, seed=args.seed))
        return 0
    if args.command == "validate-playoffs":
        print_json(validate(root, through_date=args.through, playoffs=True, seed=args.seed))
        return 0
    if args.command == "validate-game-probabilities":
        print_json(validate_game_probabilities(root, args.game_id, runs=args.runs, seed=args.seed, mode=args.mode))
        return 0
    if args.command == "explain-game-probabilities":
        print_json(explain_game_probability(root, args.game_id, runs=args.runs, seed=args.seed, mode=args.mode))
        return 0
    if args.command == "validate-season-probabilities":
        print_json(validate_season_probabilities(root, through_date=args.through, runs=args.runs, seed=args.seed, playoffs=args.playoffs, limit=args.limit))
        return 0
    if args.command == "calibrate-market":
        print_json(calibrate_market(root, through_date=args.through, holdout_start=args.holdout_start, runs=args.runs, seed=args.seed, playoffs=args.playoffs, limit=args.limit, scored_only=args.scored_only))
        return 0
    if args.command == "health":
        if args.health_kind == "player":
            report = health_player_report(data, args.name)
            if report is None:
                print(f"No player found matching {args.name!r}", file=sys.stderr)
                return 1
            print_json(report)
            return 0
        if args.health_kind == "team":
            report = health_team_report(data, args.team)
            if report is None:
                print(f"No team found matching {args.team!r}", file=sys.stderr)
                return 1
            print_json(report)
            return 0
    if args.command == "simulate-health":
        print_json(simulate_health(root, data, args.from_date, args.through_date, seed=args.seed))
        return 0
    if args.command == "advance-development":
        print_json(advance_development(data, args.month, seed=args.seed))
        return 0
    if args.command == "gm-report":
        if args.gm_kind == "team":
            print_json(gm_report(data, args.team))
            return 0
    if args.command == "trade-block":
        print_json(trade_block_report(data, team_query=args.team))
        return 0
    if args.command == "find-trade":
        print_json(find_trade(data, args.player, args.for_team, limit=args.limit, seed=args.seed))
        return 0
    if args.command == "evaluate-trade":
        try:
            from_assets, to_assets = parse_cli_assets(data, args.from_team, args.to_team, args.asset)
            print_json(evaluate_trade(data, args.from_team, args.to_team, from_assets, to_assets, seed=args.seed))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "simulate-ai-trades":
        print_json(simulate_ai_trades(data, args.from_date, args.through_date, seed=args.seed, limit=args.limit))
        return 0
    if args.command == "apply-trade":
        print_json(apply_trade_to_save(args.save, args.proposal_id))
        return 0
    if args.command == "contract-market":
        if args.contract_market_kind == "player":
            try:
                print_json(contract_market_report(data, args.name))
                return 0
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
    if args.command == "extension-candidates":
        try:
            print_json(extension_candidates_report(data, team_query=args.team))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "negotiate-extension":
        try:
            print_json(negotiate_extension(data, args.player, args.team, seed=args.seed, max_rounds=args.max_rounds))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "free-agents":
        try:
            print_json(free_agents_report(data, team_query=args.team, position=args.position))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "evaluate-signing":
        try:
            print_json(evaluate_signing(data, args.player, args.team, args.years, args.aav, seed=args.seed))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "simulate-free-agency":
        print_json(simulate_free_agency(data, args.from_date, args.through_date, seed=args.seed, limit=args.limit))
        return 0
    if args.command == "apply-contract":
        print_json(apply_contract_to_save(args.save, args.negotiation_id))
        return 0
    if args.command == "generate-draft-class":
        print_json(to_plain(generate_draft_class_records(args.year, seed=args.seed)))
        return 0
    if args.command == "generate-draft-order":
        standings = load_optional_cli_json(args.standings)
        print_json(generate_draft_order(data, args.year, seed=args.seed, standings=standings))
        return 0
    if args.command == "draft-class":
        try:
            print_json(draft_class_payload(data, args.year, seed=args.seed, scouted_for=args.scouted_for))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "draft-board":
        try:
            print_json(draft_board_report(data, args.team, year=args.year, limit=args.limit))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "evaluate-draft-pick":
        try:
            print_json(evaluate_draft_pick(data, args.team, args.pick, args.prospect, seed=args.seed))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "rookie-contract":
        try:
            print_json(project_rookie_contract(data, args.team, args.pick, args.prospect, signed=args.signed))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "pick-recommendations":
        try:
            print_json(pick_recommendations(data, args.team, args.pick, limit=args.limit, seed=args.seed))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "find-draft-trade":
        try:
            print_json(find_draft_trade(data, args.team, args.pick, limit=args.limit, seed=args.seed))
            return 0
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.command == "simulate-draft":
        print_json(simulate_draft(data, args.year, seed=args.seed))
        return 0
    if args.command == "apply-draft-selection":
        print_json(apply_draft_selection_to_save(args.save, args.selection_id, sign_rookie=args.sign_rookie))
        return 0
    return 2


def load_or_build(root: Path, out: Path) -> dict[str, Any]:
    json_path = out / JSON_FILENAME
    if json_path.exists():
        data = load_universe_json(json_path)
        required = ["draft_classes", "draft_prospects", "draft_prospect_traits", "scouting_reports", "draft_board_entries"]
        if all(key in data for key in required):
            return data
    return to_plain(build_universe(root))


def load_optional_cli_json(path: str | None) -> Any | None:
    if not path:
        return None
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def print_summary(summary: dict[str, Any]) -> None:
    print("Coverage summary")
    for key in [
        "team_count",
        "player_count",
        "rotation_relevant_player_count",
        "trait_count",
        "contract_count",
        "contract_manual_review_count",
        "draft_pick_count",
        "verified_draft_pick_count",
        "draft_pick_placeholder_count",
        "draft_class_count",
        "draft_prospect_count",
        "draft_prospect_trait_count",
        "scouting_report_count",
        "draft_board_entry_count",
        "missing_scouting_reports",
        "missing_draft_board_entries",
        "staff_profile_count",
        "verified_staff_profile_count",
        "staff_placeholder_count",
        "gameplay_staff_slot_count",
        "missing_gameplay_staff_slots",
        "player_health_profile_count",
        "player_health_state_count",
        "startup_injury_event_count",
        "development_event_count",
        "front_office_profile_count",
        "team_strategic_state_count",
        "player_asset_valuation_count",
        "player_contract_market_profile_count",
        "player_contract_preference_count",
        "extension_candidate_count",
        "extension_manual_review_count",
        "free_agent_candidate_count",
        "free_agent_manual_review_count",
        "trade_block_entry_count",
        "rotation_missing_critical_fields",
        "rotation_missing_without_fallback",
    ]:
        print(f"  {key}: {summary.get(key)}")
    print(f"  issues_by_severity: {summary.get('issues_by_severity')}")
    print(f"  research_pending: {summary.get('research_pending')}")


def print_top_issues(issues: list[dict[str, Any]], limit: int = 20) -> None:
    print("Top issues")
    priority = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    for issue in sorted(issues, key=lambda item: (priority.get(item["severity"], 9), item["category"], item["entity_id"]))[:limit]:
        print(f"  [{issue['severity']}] {issue['category']} {issue['entity_type']} {issue['entity_id']}: {issue['message']}")


def print_player(data: dict[str, Any], name: str, include_traits: bool) -> int:
    needle = normalize_name(name)
    players = data["players"]
    matches = [player for player in players if needle in normalize_name(player["name"]) or needle == player["normalized_name"]]
    if not matches:
        print(f"No player found matching {name!r}", file=sys.stderr)
        return 1
    player = sorted(matches, key=lambda item: item["minutes_projection"], reverse=True)[0]
    print(json.dumps(player, indent=2, sort_keys=True))
    if include_traits:
        traits = [trait for trait in data["traits"] if trait["player_id"] == player["id"]]
        compact = [
            {
                "trait": trait["trait_key"],
                "value": trait["value"],
                "confidence": trait["confidence"],
                "notes": trait["notes"],
            }
            for trait in sorted(traits, key=lambda item: item["trait_key"])
        ]
        print(json.dumps(compact, indent=2, sort_keys=True))
    return 0


def print_team(data: dict[str, Any], team_query: str, include_staff: bool = False) -> int:
    query = team_query.strip().lower()
    teams = data["teams"]
    exact_matches = [team for team in teams if query == team["abbrev"].lower()]
    matches = exact_matches or [team for team in teams if query in team["name"].lower()]
    if not matches:
        print(f"No team found matching {team_query!r}", file=sys.stderr)
        return 1
    team = matches[0]
    roster = [player for player in data["players"] if player["team_id"] == team["id"]]
    profile = next((profile for profile in data["team_profiles"] if profile["team_id"] == team["id"]), None)
    payload = {
        "team": team,
        "profile": profile,
        "rotation": sorted(
            [
                {
                    "name": player["name"],
                    "position": player["position"],
                    "minutes_projection": player["minutes_projection"],
                    "rotation_priority": player["rotation_priority"],
                    "sim_eligible_raw": player["sim_eligible_raw"],
                    "missing_critical_fields": player["missing_critical_fields"],
                }
                for player in roster
                if player["rotation_priority"] != "fringe"
            ],
            key=lambda item: item["minutes_projection"],
            reverse=True,
        ),
    }
    if include_staff:
        payload["real_staff_context"] = sorted(
            [staff for staff in data.get("staff_profiles", []) if staff["team_id"] == team["id"]],
            key=lambda item: item["role"],
        )
        payload["gameplay_staff_slots"] = sorted(
            [slot for slot in data.get("gameplay_staff_slots", []) if slot["team_id"] == team["id"]],
            key=lambda item: item["slot"],
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def print_source(data: dict[str, Any], source_id: str) -> int:
    source = next((source for source in data["sources"] if source["id"] == source_id), None)
    if not source:
        print(f"No source found with id {source_id!r}", file=sys.stderr)
        return 1
    print(json.dumps(source, indent=2, sort_keys=True))
    return 0


def print_features(data: dict[str, Any], args: argparse.Namespace) -> int:
    if args.feature_kind == "player":
        needle = normalize_name(args.name)
        matches = [player for player in data["players"] if needle in normalize_name(player["name"]) or needle == player["normalized_name"]]
        if not matches:
            print(f"No player found matching {args.name!r}", file=sys.stderr)
            return 1
        player = sorted(matches, key=lambda item: item["minutes_projection"], reverse=True)[0]
        print_json(player_feature_vector(data, player))
        return 0
    if args.feature_kind == "team":
        query = args.team.strip().lower()
        teams = data["teams"]
        matches = [team for team in teams if query == team["abbrev"].lower()] or [team for team in teams if query in team["name"].lower()]
        if not matches:
            print(f"No team found matching {args.team!r}", file=sys.stderr)
            return 1
        print_json(team_feature_vector(data, matches[0]))
        return 0
    if args.feature_kind == "coaches":
        print_json(coach_ratings(data))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
