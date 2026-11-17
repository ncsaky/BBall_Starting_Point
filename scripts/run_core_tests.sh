#!/usr/bin/env bash
# Fast core regression subset (target: a few minutes). The full suite is ~37 minutes.
# Covers: saves/persistence, sim + box-score accounting, schedule, transactions/trades/contracts,
# roster rules, and the app action/API layer.
# Usage: scripts/run_core_tests.sh [extra unittest args]
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src:scripts:tests  # tests/ on the path: some tests import sibling test modules (as unittest discover does)
PY=.venv/bin/python

MODULES=(
  # saves / persistence
  test_save_persistence test_save_recovery test_new_career_start test_rollover_history
  # sim and box-score accounting
  test_basketball_accounting test_box_score_reconciliation test_plus_minus test_simulation_consistency
  test_simulation_progress
  # schedule / calendar
  test_schedule_integrity test_postseason_calendar
  # transactions, trades, contracts
  test_block_contract_terms test_contract_protection test_trade_salary_application test_trade_salary_boundaries
  test_trade_payloads test_trade_offer_duplicates test_trade_roster test_free_agency_bids
  test_draft_application_duplicates test_settlement_materialization
  # roster rules
  test_roster_floor test_roster_space test_roster_retention test_user_rotation_roster test_waivers
  # app action / API layer
  test_api_security test_dashboard_metrics test_gui_concept71 test_gui_concept74
  test_roster_forecast_performance
)

args=()
for m in "${MODULES[@]}"; do args+=("tests.$m"); done
exec "$PY" -m unittest "${args[@]}" "$@"
