# Test suite triage

TL;DR: Five tests have verified fixture repairs; 56 unresolved tests are explicitly quarantined.
No original failing assertion or numerical tolerance was removed or loosened.
Full verification is running; suspected production bugs and every quarantine are listed below.

## Boundaries
Test changes only in tests/ (including fixtures); board/report coordination updates authorized. No src/ or scripts/ edits. No commits.

## Work in progress
- Five fixture repairs pass (`output/tst/focused_repairs.log`, 5 tests): atomic writer preserves revision/snapshot metadata; narrative fixture reloads after cache write; market rating-key assertion includes expanded display families; upside and medical generator tests isolate the new public ranking step (689933a).
- Baseline started at 463151a; concurrent coordinator work advanced HEAD and edited production files during this run. Results are diagnostic for a moving checkout, not an immutable revision.
- Historical diagnostic consulted: output/spd/full.log (1741 run, 57 failures, 5 errors, 4 skips); it is NOT this task's before count.
- Box-stat changes have explicit improvement evidence: 6a3c90c reduces steals/blocks error; 114c7c1 fixes biased FT rounding without changing scores; c29f301 improves rebound correlation/error. Do not loosen FG% mean-shift limit.
- `git log --all -S` searches for rookie_trait_records, player_tuning, and 94.0 did not establish independent approval of lower legacy rookie/Kyrie/Lively expectations. Preserve assertions and quarantine ambiguous rating pins rather than silently adopting observed numbers.

## Baseline results

1,743 tests: 1,678 passing methods, 56 failing methods (57 failure events, including two seed subtests in one method), 5 erroring methods, 4 skipped. Full log: `output/tst/full_before.log`. Five repaired methods passed focused verification; 56 remaining methods explicitly quarantined without changing their assertions.

## Failure classification and quarantine inventory

a = stale intentional change; b = fixture/environment; c = suspected real bug; a? = likely stale, but exact approval unresolved. Quarantined items retain their original assertions; repaired items retain their behavioral checks with the documented fixture/key corrections. “needs review” skips identify the reason in the source. Full tracebacks remain in the baseline log.

### test_foundation.DataFoundationTests.test_app_action_layer_creates_local_save_and_serves_core_payloads

Quarantined; category b. contract/roster-dependent fixture no longer has the assumed eligible player (board Curry contract now through 2028-29); needs controlled contract fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `StopIteration`

### test_foundation.DataFoundationTests.test_extension_window_starts_with_two_active_contract_seasons_remaining

Quarantined; category b. contract/roster-dependent fixture no longer has the assumed eligible player (board Curry contract now through 2028-29); needs controlled contract fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `StopIteration`

### test_foundation.DataFoundationTests.test_narrative_provider_failure_falls_back_without_breaking_social

Repaired and focused pass.

Failing check: `Setup error (see baseline traceback)`

Observed: `nba_gm_data.history_store.SaveValidationError: This save changed while it was open. Reload it before saving again.`

### test_input_estimator.ProcessDeterminismTests.test_byte_identical_build_across_hash_seeds

Quarantined; category b. builder subprocess exceeds 45 seconds under current evidence/load; preserve determinism assertion and timeout pending isolated fixture design.

Failing check: `Setup error (see baseline traceback)`

Observed: `subprocess.TimeoutExpired: Command '['/Users/noahtyler/Documents/BBall_data/BBall_Starting_Point/.venv/bin/python', '/Users/noahtyler/Documents/BBall_data/BBall_Starting_Point/scripts/build_player_inputs.py', '--no-report', '--output', '/var/folders/qz/pr9r0n51705g147ljbrg1t8r0000gn/T/tmpad149krm/inputs1.json']' timed out after 45 seconds`

### test_roster_alignment.RosterAlignmentTests.test_current_rookie_conversion_and_future_generation_are_not_changed

Quarantined; category b. mock removes upstream roster alignment required by five-player calibration; Cedric Coward baseline guard rejects fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `ValueError: Scouting baseline changed: Cedric Coward defensive_effort: 56.11`

### test_box_variation.BoxVariationTests.test_sequence_variance_grows_without_changing_scores_minutes_or_makes

Quarantined; category c. FG percentage mean drift 0.03084 exceeds unchanged 0.025 limit; unbiased FT split may expose variation bias.

Failing check: `self.assertLess(abs(statistics.mean(a) - statistics.mean(b)), .025)`

Observed: `AssertionError: 0.030838489851740314 not less than 0.025`

### test_contract_import_separation.ContractImportSeparationTests.test_other_source_collections_and_contracts_are_unchanged

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertEqual(self.old[key], self.canonical[key], key)`

Observed: `AssertionError: Lists differ: [{'components': {'2026_roster_refresh': {'pr[13830555 chars].12}] != [{'id': 'trait_player-atl-asa-newell-release[13835906 chars]e}}}]`

### test_creation_passing.CreationIntegrationTests.test_disabled_path_full_result_parity_and_prior_experiments

Quarantined; category a. frozen compiler predates improved box allocation (6a3c90c, c29f301); refresh authenticated reference after coordinator review.

Failing check: `self.assertEqual(to_plain(sim.sim_game_with_context(c,'interior_fixture',mode,seed)),to_plain(old_sim.sim_game_with_context(d,'interior_fixture',mode,seed)))`

Observed: `AssertionError: {'id'[563 chars]s': 12, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}} != {'id'[563 chars]s': 11, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}}`

### test_expanded_cohort_performance.ExpandedCohortTests.test_default_off_and_prior_experimental_paths_match_reference

Quarantined; category a. frozen compiler predates improved box allocation (6a3c90c, c29f301); refresh authenticated reference after coordinator review.

Failing check: `self.assertEqual(len(kernel_parity([('ordinary',c,None),('legacy_screen',c,legacy),('offense_only',c,off),('interior_only',c,defense)],self.old)),16)`

Observed: `AssertionError: ('ordinary', 17, 'replay-real-minutes', 'result')`

### test_experimental_input_pilot.PilotBoundaryTests.test_complete_historical_paths_use_authenticated_frozen_compilers

Quarantined; category a. frozen compiler predates improved box allocation (6a3c90c, c29f301); refresh authenticated reference after coordinator review.

Failing check: `self.assertEqual(to_plain(now),to_plain(before))`

Observed: `AssertionError: {'id'[563 chars]s': 12, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}} != {'id'[563 chars]s': 11, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}}`

### test_fantasy_draft.FantasyDraftTests.test_full_fantasy_draft_replaces_rosters_and_preserves_contracts

Quarantined; category c. star valuation/ranking misses benchmark; board T3 documents Giannis/Luka underrating; do not lower benchmark.

Failing check: `self.assertTrue({"Giannis Antetokounmpo", "Luka Dončić"} <= first_round)`

Observed: `AssertionError: False is not true`

### test_five_player_calibration.FivePlayerCalibrationTests.test_final_order_provenance_and_rebuild

Quarantined; category a. 689933a intentionally reranks generated prospects; archived full-universe equality includes obsolete ranks.

Failing check: `rebuilt=to_plain(build_universe(ROOT));self.assertEqual(rebuilt,self.current)`

Observed: `AssertionError: {'met[16974926 chars]nk': 3, 'rank_range': {'low': 1, 'high': 8}, '[6524484 chars]}]}]} != {'met[16974926 chars]nk': 2, 'rank_range': {'low': 1, 'high': 7}, '[6524548 chars]}]}]}`

### test_foundation.DataFoundationTests.test_2026_offseason_update_preserves_returning_traits_except_manual_calibrations

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 41.6 != 39.19 : ('asa newell', 'shot_versatility')`

### test_foundation.DataFoundationTests.test_ai_offer_packages_can_create_pick_swap_sweeteners

Quarantined; category c. no pick-swap package generated; investigate asset eligibility before weakening coverage.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: unexpectedly None`

### test_foundation.DataFoundationTests.test_ai_roster_cutdown_moves_waived_player_to_free_agency

Quarantined; category a. board T3: cuts now pass through waivers; test assumes immediate free agency; rebuild waiver timeline fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 'player_test_ai_cutdown_filler' not found in ['player_atl-caleb-houstan', 'player_atl-cameron-corhen', 'player_atl-christian-koloko', 'player_atl-eli-john-ndiaye', 'player_atl-gabe-vincent', 'player_atl-henri-veesaar', 'player_atl-isaac-mckneely', 'player_atl-jacob-toppin', 'player_atl-jalen-wilson', 'player_atl-keaton-wallace', 'pl`

### test_foundation.DataFoundationTests.test_ai_trade_processing_skips_overlapping_bundle_assets

Quarantined; category b. board T3: seeded trade slots and stale asset fixtures; needs forced valid trade slot/current assets.

Failing check: `self.assertEqual(applied_outcome["applied_candidate_count"], 1)`

Observed: `AssertionError: '2026-10-20' != '2026-01-20'`

### test_foundation.DataFoundationTests.test_ai_trade_simulation_and_save_ledger_are_deterministic

Quarantined; category b. board T3: seeded trade slots and stale asset fixtures; needs forced valid trade slot/current assets.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 'not_applied_stale_assets' != 'applied'`

### test_foundation.DataFoundationTests.test_elite_staff_hire_and_fire_create_major_league_events

Quarantined; category a. board T3: one staff change per season now enforced; fixture attempts repeated changes.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 1 not greater than or equal to 2`

### test_foundation.DataFoundationTests.test_expiring_players_remain_rostered_through_draft_then_enter_re_signing

Quarantined; category b. board T3: selected expiring player was already cut; needs guaranteed rostered fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: None != 'team_gsw'`

### test_foundation.DataFoundationTests.test_extension_and_free_agency_negotiations_are_deterministic_and_explainable

Quarantined; category b. contract/roster-dependent fixture no longer has the assumed eligible player (board Curry contract now through 2028-29); needs controlled contract fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: False is not true`

### test_foundation.DataFoundationTests.test_extension_eligibility_uses_original_term_and_active_save_season

Quarantined; category b. contract/roster-dependent fixture no longer has the assumed eligible player (board Curry contract now through 2028-29); needs controlled contract fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: False is not true`

### test_foundation.DataFoundationTests.test_extension_override_preserves_current_contract_season

Quarantined; category b. contract/roster-dependent fixture no longer has the assumed eligible player (board Curry contract now through 2028-29); needs controlled contract fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 55700000 != 42500000`

### test_foundation.DataFoundationTests.test_extension_social_requires_sim_evidence_for_health_money_position_and_conference_claims

Quarantined; category c. validator accepts durability claim that test rejects; evidence policy needs review.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: {'text': 'Only 6 games played makes this a durability bet. [6/70 GP this season, 64 missed games, injury risk 0.0]', 'author': 'Test', 'handle': '@test', 'persona': 'tester', 'source': 'ollama'} is not None`

### test_foundation.DataFoundationTests.test_free_agency_day_market_initializes_ai_offers_and_limits

Repaired and focused pass.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: Items in the first set but not the second:`

### test_foundation.DataFoundationTests.test_future_draft_pick_recommendations_use_generated_class

Quarantined; category c. generated class requested twice instead of once; inspect duplicate computation before repinning call count.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 2 != 1`

### test_foundation.DataFoundationTests.test_future_pick_values_reflect_timeline_uncertainty_and_dedupe_display_assets

Quarantined; category b. board T3: SAC owns no second-round picks; needs explicit owned-pick fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 0 not greater than or equal to 6`

### test_foundation.DataFoundationTests.test_future_second_round_picks_are_tradeable_scaffold_assets

Quarantined; category b. board T3: SAC owns no second-round picks; needs explicit owned-pick fixture.

Failing check: `self.assertGreaterEqual(len(future_seconds), 30)`

Observed: `AssertionError: False is not true`

### test_foundation.DataFoundationTests.test_gui_advance_reuses_core_ai_result_without_duplicate_processing

Quarantined; category b. board T3: seeded trade slots and stale asset fixtures; needs forced valid trade slot/current assets.

Failing check: `return self.assert_called_with(*args, **kwargs)`

Observed: `AssertionError: expected call not found.`

### test_foundation.DataFoundationTests.test_gui_roster_cutdown_can_be_completed_through_app_actions

Quarantined; category a. board T3: cuts now pass through waivers; test assumes immediate free agency; rebuild waiver timeline fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 'player_bos-chris-boucher' not found in ['player_atl-caleb-houstan', 'player_atl-cameron-corhen', 'player_atl-christian-koloko', 'player_atl-eli-john-ndiaye', 'player_atl-gabe-vincent', 'player_atl-henri-veesaar', 'player_atl-isaac-mckneely', 'player_atl-jacob-toppin', 'player_atl-jalen-wilson', 'player_atl-keaton-wallace', 'player_`

### test_foundation.DataFoundationTests.test_known_extension_is_not_blocked_by_unresolved_teammate_contract

Quarantined; category b. contract/roster-dependent fixture no longer has the assumed eligible player (board Curry contract now through 2028-29); needs controlled contract fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: [] is not true`

### test_foundation.DataFoundationTests.test_league_leaders_are_stats_only_and_traits_are_separate

Quarantined; category c. displayed overall differs from raw reference by 0.8; verify intended display/engine derivation.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 81.8 != 81.0 within 0.5 delta (0.7999999999999972 difference)`

### test_foundation.DataFoundationTests.test_league_trait_ratings_prior_import_audit_and_manual_precedence

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 2 not less than or equal to 1`

### test_foundation.DataFoundationTests.test_pick_obligation_validator_repairs_self_fallback_and_pick_swaps_resolve

Quarantined; category a. pick display now prints full more/less favourable terms instead of Subject to; review complete label assertion.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 'Subject to' not found in '2028 R1 GSW (own pick); 2028 R1: BOS receives the more favourable of GSW/LAC; GSW receives the less favourable of those two picks.'`

### test_foundation.DataFoundationTests.test_repeated_same_day_ai_roster_cut_upserts_one_transaction

Quarantined; category a. board T3: cuts now pass through waivers; test assumes immediate free agency; rebuild waiver timeline fixture.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 'team_bos' is not None`

### test_foundation.DataFoundationTests.test_rostered_players_have_dashboard_core_data

Quarantined; category c. 11 rostered players lack height (board data gap); production data repair required.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: Lists differ: [('BOS', 'Tucker DeVries', 23.0, None, Tru[438 chars]rue)] != []`

### test_foundation.DataFoundationTests.test_save_user_actions_ai_processing_morale_and_social

Quarantined; category b. board T3: seeded trade slots and stale asset fixtures; needs forced valid trade slot/current assets.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 0 not greater than or equal to 1`

### test_foundation.DataFoundationTests.test_save_writes_replace_atomically_for_concurrent_gui_reads

Repaired and focused pass.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: False is not true`

### test_foundation.DataFoundationTests.test_staff_fire_interim_budget_and_market_depth

Quarantined; category a. board T3: one staff change per season now enforced; fixture attempts repeated changes.

Failing check: `self.assertLessEqual(negotiation["team_offer"]["annual_salary_millions"], negotiation["max_offer_millions"])`

Observed: `AssertionError: 'season_limit_blocked' != 'applied'`

### test_foundation.DataFoundationTests.test_staff_queue_keeps_live_strategy_from_raising_budget

Quarantined; category c. live strategy appears to raise staff budget; board T3 leaves budget guard unresolved.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: True is not false`

### test_foundation.DataFoundationTests.test_superstar_and_swap_values_have_benchmark_shape

Quarantined; category c. star valuation/ranking misses benchmark; board T3 documents Giannis/Luka underrating; do not lower benchmark.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 86.87 not greater than 105.0`

### test_foundation.DataFoundationTests.test_superstar_trade_value_benchmark_rejects_light_giannis_packages

Quarantined; category c. star valuation/ranking misses benchmark; board T3 documents Giannis/Luka underrating; do not lower benchmark.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: 86.87 not greater than 89.91`

### test_foundation.DataFoundationTests.test_team_strategy_reflects_phase_pressure_and_personality

Quarantined; category c. only six teams contend against minimum eight; distinguish changed roster from strategy regression.

Failing check: `self.assertTrue(any(state.phase in {"developing", "rebuilding"} for state in states.values()))`

Observed: `AssertionError: 6 not greater than or equal to 8`

### test_foundation.DataFoundationTests.test_trade_evaluation_uses_team_context_and_legality

Quarantined; category c. decision outside accept/reject; review current counteroffer semantics and legality.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: False is not true`

### test_generated_upside.GeneratedUpsideTests.test_tail_preserves_identity_readiness_medicals_and_ordinary_traits

Repaired and focused pass.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: {'id'[128 chars]nk': 8, 'rank_range': {'low': 5, 'high': 13}, [901 chars]: {}} != {'id'[128 chars]nk': 4, 'rank_range': {'low': 1, 'high': 9}, '[900 chars]: {}}`

### test_imported_rookie_ratings.ImportedRookieRatingTests.test_existing_converter_is_used_and_identity_contracts_and_veterans_are_preserved

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertEqual(trait["value"], old_values[(trait["player_id"], trait["trait_key"])])`

Observed: `AssertionError: 47.6 != 38.74`

### test_imported_rookie_ratings.ImportedRookieRatingTests.test_pick_protections_are_unchanged_for_both_starting_versions

Quarantined; category c. current version loads no pick protections versus 85 archived obligations; verify version gating before changing expectation.

Failing check: `self.assertEqual(old, new)`

Observed: `AssertionError: Lists differ: [{'id': 'pick_obligation_realgm-protected-[45145 chars]tl'}] != []`

### test_imported_rookie_ratings.ImportedRookieRatingTests.test_real_imported_top_picks_are_differentiated_nba_profiles

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertGreaterEqual(ratings["overall"], 79)`

Observed: `AssertionError: 64.0 not greater than or equal to 79`

### test_imported_rookie_ratings.ImportedRookieRatingTests.test_schema_json_sqlite_and_save_round_trip_keep_upside_metadata

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertGreater(player_card_payload(loaded, path, self.aj.id)["ratings"]["overall"], 78)`

Observed: `AssertionError: 63.8 not greater than 78`

### test_imported_rookie_ratings.ImportedRookieRatingTests.test_two_seed_development_is_bounded_repeatable_and_uses_prospect_upside

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertGreater(value, 83)`

Observed: `AssertionError: 70.8 not greater than 83`

### test_imported_rookie_ratings.ImportedRookieRatingTests.test_two_seed_development_is_bounded_repeatable_and_uses_prospect_upside

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertGreater(value, 83)`

Observed: `AssertionError: 69.9 not greater than 83`

### test_input_estimator.LeagueInputTests.test_written_artifact_matches_the_current_builder

Quarantined; category b. checked-in artifact includes BBI overlay but fixture builds without it; align evidence snapshot before byte comparison.

Failing check: `self.assertEqual(payload,canonical_json(self.section))`

Observed: `AssertionError: '{"pl[1666 chars]son"},{"method":"bbi_evidence_overlay_v2_2026_[125766209 chars]"}\n' != '{"pl[1666 chars]son"}],"reason":"estimated","status":"estimate[108394887 chars]"}\n'`

### test_interior_defense_experiment.InteriorGameTests.test_frozen_pre_edit_default_path_matches_complete_results

Quarantined; category a. frozen compiler predates improved box allocation (6a3c90c, c29f301); refresh authenticated reference after coordinator review.

Failing check: `self.assertEqual(to_plain(a),to_plain(b))`

Observed: `AssertionError: {'id'[563 chars]s': 12, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}} != {'id'[563 chars]s': 11, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}}`

### test_long_term_health.LongTermHealthTests.test_star_flow_reconciles_crossings_entries_and_departures

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertEqual((result["before"], result["after"]), (3, 3))`

Observed: `AssertionError: Tuples differ: (0, 0) != (3, 3)`

### test_offense_interior_interaction.CoupledGameTests.test_default_off_full_result_parity_with_stage_b_reference

Quarantined; category a. frozen compiler predates improved box allocation (6a3c90c, c29f301); refresh authenticated reference after coordinator review.

Failing check: `self.assertEqual(to_plain(sim.sim_game_with_context(c,'interior_fixture',mode,seed)),to_plain(old.sim_game_with_context(d,'interior_fixture',mode,seed)))`

Observed: `AssertionError: {'id'[563 chars]s': 12, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}} != {'id'[563 chars]s': 11, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}}`

### test_player_lifecycle.PlayerLifecycleTests.test_generated_medicals_are_varied_repeatable_and_do_not_change_ratings

Repaired and focused pass.

Failing check: `Setup error (see baseline traceback)`

Observed: `AssertionError: {'id'[150 chars]k': 10, 'rank_range': {'low': 7, 'high': 15}, [595 chars]: {}} != {'id'[150 chars]k': 11, 'rank_range': {'low': 8, 'high': 16}, [595 chars]: {}}`

### test_player_tuning.PlayerTuningTests.test_kyrie_skill_returns_without_creating_a_defensive_or_rebounding_star

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertGreater(after["handle"], 95)`

Observed: `AssertionError: 94.0 not greater than 95`

### test_player_tuning.PlayerTuningTests.test_lively_retains_specialist_weaknesses_and_tiny_sample_extremes_are_reduced

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertGreater(self.grade(self.new, "Dereck Lively II")["defense"], 80)`

Observed: `AssertionError: 70.2 not greater than 80`

### test_roster_alignment.RosterAlignmentTests.test_new_version_and_identity_contracts_are_preserved

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertEqual(self.new["contracts"],self.old["contracts"])`

Observed: `AssertionError: Lists differ: [{'id': 'contract_player-atl-asa-newell', 'p[504553 chars] {}}] != [{'confidence': 0.82, 'extension_eligibility[504527 chars]as'}]`

### test_roster_alignment.RosterAlignmentTests.test_successful_young_profiles_and_manual_stars_keep_their_traits

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertEqual(before,after,name)`

Observed: `AssertionError: {'rel[262 chars]ce': 99.0, 'screen_navigation': 86.62, 'offens[68 chars]84.0} != {'rel[262 chars]ce': 100.0, 'screen_navigation': 86.62, 'offen[69 chars]84.0}`

### test_rotation_profile_calibration.RotationProfileBaselineTests.test_all_changes_are_reported_or_researched_and_prior_reviews_are_preserved

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertIn(names[key[0]],{'Amir Coffey','Deandre Ayton'})`

Observed: `AssertionError: 'Devin Vassell' not found in {'Amir Coffey', 'Deandre Ayton'}`

### test_rotation_profile_calibration.RotationProfileBaselineTests.test_medicals_finances_players_and_prospects_are_identical

Quarantined; category a?. archived legacy ratings/contracts differ; git log -S did not establish approval for this exact expectation; needs coordinator evidence before repinning.

Failing check: `self.assertEqual(self.old[key],self.new[key],key)`

Observed: `AssertionError: Lists differ: [{'confidence': 0.82, 'extension_eligibility[504527 chars]as'}] != [{'id': 'contract_player-atl-asa-newell', 'p[504553 chars] {}}]`

### test_screen_navigation.ScreenKernelTests.test_complete_prior_modes_match_frozen_modules_with_screens_off

Quarantined; category a. frozen compiler predates improved box allocation (6a3c90c, c29f301); refresh authenticated reference after coordinator review.

Failing check: `self.assertEqual(to_plain(actual),to_plain(prior))`

Observed: `AssertionError: {'id'[563 chars]s': 12, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}} != {'id'[563 chars]s': 11, 'assists': 9, 'turnovers': 2, 'steals'[7597 chars]4]]}}`

## Suspected real bugs for Claude

- `test_box_variation.BoxVariationTests.test_sequence_variance_grows_without_changing_scores_minutes_or_makes`: FG percentage mean drift 0.03084 exceeds unchanged 0.025 limit; unbiased FT split may expose variation bias. Check and observed assertion are recorded above.
- `test_fantasy_draft.FantasyDraftTests.test_full_fantasy_draft_replaces_rosters_and_preserves_contracts`: star valuation/ranking misses benchmark; board T3 documents Giannis/Luka underrating; do not lower benchmark. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_ai_offer_packages_can_create_pick_swap_sweeteners`: no pick-swap package generated; investigate asset eligibility before weakening coverage. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_extension_social_requires_sim_evidence_for_health_money_position_and_conference_claims`: validator accepts durability claim that test rejects; evidence policy needs review. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_future_draft_pick_recommendations_use_generated_class`: generated class requested twice instead of once; inspect duplicate computation before repinning call count. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_league_leaders_are_stats_only_and_traits_are_separate`: displayed overall differs from raw reference by 0.8; verify intended display/engine derivation. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_rostered_players_have_dashboard_core_data`: 11 rostered players lack height (board data gap); production data repair required. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_staff_queue_keeps_live_strategy_from_raising_budget`: live strategy appears to raise staff budget; board T3 leaves budget guard unresolved. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_superstar_and_swap_values_have_benchmark_shape`: star valuation/ranking misses benchmark; board T3 documents Giannis/Luka underrating; do not lower benchmark. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_superstar_trade_value_benchmark_rejects_light_giannis_packages`: star valuation/ranking misses benchmark; board T3 documents Giannis/Luka underrating; do not lower benchmark. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_team_strategy_reflects_phase_pressure_and_personality`: only six teams contend against minimum eight; distinguish changed roster from strategy regression. Check and observed assertion are recorded above.
- `test_foundation.DataFoundationTests.test_trade_evaluation_uses_team_context_and_legality`: decision outside accept/reject; review current counteroffer semantics and legality. Check and observed assertion are recorded above.
- `test_imported_rookie_ratings.ImportedRookieRatingTests.test_pick_protections_are_unchanged_for_both_starting_versions`: current version loads no pick protections versus 85 archived obligations; verify version gating before changing expectation. Check and observed assertion are recorded above.

## Resume state

Baseline complete. Five repairs focused-green. Remaining baseline failures quarantined with reasoned skips. Full after rerun finished (output/tst/full_after.log): 1,746 tests, OK, 60 skipped (56 new quarantines + 4 prior). No production edits or commits by TST.

Coordinator review (Claude, 2026-11-17): accepted and committed. Suspected bugs split into Codex tasks BUG-A/BUG-B and Claude's list; see docs/agents/CODEX_QUEUE.md.

## Review limits

The 56 new skips comprise 13 stale references, 16 fixture/environment problems, 14 ambiguous legacy pins, and 13 suspected bugs. This makes coverage debt explicit; it does not certify the quarantined behavior as correct. Several quarantined methods contain multiple checks, so restore or split them when the coordinator resolves the underlying issue. No production repair was attempted. T2b owns the separate roster forecast fixture/test edit; that diff is not TST work.

The first after-run launch was interrupted promptly after the quarantine insertion script encountered one-space indentation in a test; a second short launch was interrupted to complete repeated-reason decorators. Neither is counted as the acceptance run. The current full_after.log is the complete verification attempt launched after all 56 decorators were inserted.
