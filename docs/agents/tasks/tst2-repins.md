# TST-2: restore the 27 "stale" quarantined tests

Run AFTER BUG-A and BUG-B are committed (BUG-B fills heights for 11 players and regenerates `data/canonical/universe_2026_27_offseason.json`, which several of these comparisons depend on).

Review (Claude subagent, 2026-11-17): all 27 tests in categories "a" and "a?" of `tst-suite-triage.md` are deliberate changes, none a real bug. Rules: remove the skip, apply the repin, run the test; never loosen a tolerance just to pass.

## Three causes

1. **Box-score fixes** (6a3c90c tie-break, 114c7c1 free throws, a1e87ee fouls, c29f301 rebounds): only per-player assists, personal fouls, rebounds and steals differ; scores, points, free throws, blocks and minutes are identical. Affects the six frozen-reference tests: test_creation_passing (disabled path), test_expanded_cohort_performance (default off), test_experimental_input_pilot (frozen compilers), test_interior_defense_experiment (frozen pre-edit), test_offense_interior_interaction (stage b), test_screen_navigation (prior modes). Fix: compare with those four columns neutralized on both sides (preferred, since the frozen `sim.py.reference` lives in git-ignored output/), or refresh the reference.
2. **Display scale is now direct, not percentile-anchored** (rule 3: rescale, don't clamp). Old threshold X converts through the old anchor table (80 -> raw 60, 95 -> raw 80):
   - imported_rookie top_picks: overall 79-88 -> 59-70 (current 64.0)
   - imported_rookie schema_json_sqlite_roundtrip: > 78 -> > 58 (current 63.8)
   - imported_rookie two_seed_development: > 83 -> > 63.75 (current 70.8 / 69.9)
   - long_term_health star_flow: use fixture ratings 95 for the 80s and 60 for the 60
   - player_tuning Kyrie: handle > 95 -> > 80, portability > 85 -> > 66.25, defense < 70 -> < 50
   - player_tuning Lively: defense > 80 -> > 60
3. **Five-player calibration (v11, reviewed 2026-11-10) and the Lillard contract fix (v10)**:
   - roster_alignment successful_young_profiles: Wembanyama rim_deterrence expected 100.0
   - rotation_profile all_changes_reported: allow Edwards, Coward, Vassell, Duren, Kawhi, Wembanyama; check against the five-player payload targets instead of evidence_urls
   - rotation_profile medicals_finances_identical: exclude Lillard's contract and draft-prospect rank / rank_range / rookie_contract_value (689933a); exclude BUG-B's 11 players
   - roster_alignment new_version_and_identity: exclude Lillard's contract (assert equals the v10 baseline); exclude BUG-B's 11 players
   - contract_import_separation other_source_collections: exclude those 6 players' trait rows; BUG-B exclusion for players and roster_slots

## Others (test_foundation)

- pick_obligation_validator: line ~3317 `assertIn("receives the more favourable of", pick_label(...))` instead of "Subject to" (verified passing).
- league_trait_ratings_prior_import: exact check that the difference is 2 and the unmatched set is {Trey Lyles, Cole Swider} (added 2026-10-13 after calibration; verified passing).
- 2026_offseason_update_preserves_returning_traits: compare against the 2026-10-13 archive; preserved counts 622 players / 9330 traits.
- imported_rookie existing_converter: compare against `self.unconverted` for both comparisons; BUG-B exclusion.
- ai_roster_cutdown, gui_roster_cutdown: cuts now go through waivers. Assert a pending waiver_wire entry, run `process_waivers`, then assert free agency.
- repeated_same_day_ai_roster_cut: use a genuinely over-full roster for both cuts (don't put the waived player back on BOS).
- elite_staff_hire_and_fire, staff_fire_interim: one change per slot per season is deliberate (`staff_change_permission`). Fire first, then hire, or assert `season_limit_blocked`.
- five_player_calibration final_order: regenerate canonical JSON + SQLite after BUG-B and 689933a; keep the assertion.

## BUG-B's 11 players (height/weight/wingspan filled)
Tucker DeVries, Wyatt Fricks, Jaylin Sellers, Rashaun Agee, Carson Cooper, Josh Dix, Christoph Tilly, Andrew Holifield, Aaron Nkrumah, Nimari Burnett, Mohamed Wague.

## Resume state
Not started. Owner: Claude (or a Codex chat once BUG-A/B are committed).
