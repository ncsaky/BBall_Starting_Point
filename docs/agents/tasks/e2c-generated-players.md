# E2c generated-player inputs

TL;DR: Fictional players now express their generator's ability and skill profile through all 94 inputs.
Copied-save top-five median display OVR rises from 27.1 to 57.9, versus 61.1 for real 2024–25 top-five picks; the lowest lottery OVR is 37.0.
Real-player inputs remain byte-identical, real prospects retain their evidence path, and no model or experimental-engine switch changes.

## Objective and boundaries

Implement the user's E2c assignment in `input_estimator.py`, its tests and this report. No ratings-model implementation, draft, adapter, save, GUI or canonical-artifact edits; no commits. The user additionally authorized the single reason-label assertion change in `tests/test_ratings_model.py`. The E2b estimator/test/artifact changes present at task start remain in place; their review status and failed real-stat gate are not superseded by this task.

Read AGENTS.md, BOARD.md, STAGE1_DESIGN.md (including F) and ratings_model._install_generated_players first. Copied every supplied `inputs_save.*` file, with original names and history sidecars, to `output/e2c/scratch/`. The supplied save has already passed the 2027 draft/rollover: 60 signed rookies plus one generated replacement. Validation uses the existing ratings-model installation and player-profile functions on that copy; no save migration is introduced.

## What changed

An explicit fictional-player branch now handles `generated_rookie`, `generated_prospect`, other `generated_` source kinds, future draft dataclasses with `league: generated`, and replacement players identified by their `generated_player_` IDs. The latter have no player-level source_kind. Rookie signing also labels real 2026 draftees generated_rookie, so that class is deliberately excluded; real prospect records with public stats continue through the existing evidence path.

For fictional definitions, supplied 15 rookie traits provide the skill shape directly. Supplied 12 draft traits use the existing draft conversion, with the draft archetype's existing biases. Missing broad details receive stable variation from SHA-256 of player ID, optional seed and input ID. This does not draw from any simulation or global random stream. Height and weight remain native-unit body definitions; inferred reach, other tools and choice tendencies stay separate from technique. Tendency mixes normalize to one and describe fictional choices, without fabricating observed opportunity counts. Potential is retained in provenance, the existing draft conversion and future-upside definition; the interpolation adds no separate potential bonus to current technique.

Each scalar skill/tool is calibrated against the existing input records of **256 real players with explicit current_ability and legacy traits**. For each input, select the 24 closest real players using squared distance in current ability (8-point bandwidth), the mean of linked legacy traits (10-point bandwidth), and position family (penalty 2 for a different family). The linked traits use the estimator's existing declared per-input relationships; generated archetypes enter through their generator-defined skill shape and role choice priors. Gaussian distance weights interpolate real native-unit input values. Add 12% of the local standard deviation times stable player-specific detail; grades use a smooth log-odds transformation rather than clipping. These are declared smoothing assumptions, not inferred technique measurements or coefficients fitted to display targets, pick slots, simulations or betting results.

Reference coordinates are computed once, lazily, from packaged real inputs (JSON or gzip). A bounded 256-definition cache excludes daily box stats, team changes and coach minutes, so routine save rebuilds cannot reinterpret those fields as new player talent or repeat the calibration. Returned PlayerInputs snapshots are immutable. Generated records retain their individual neighbor IDs/weights and the generator definition used for calibration in provenance.

## Schema decision

The schema already accepts arbitrary textual `reason`, so no schema change is needed. All 94 fictional records use **status: estimated, reason: generated, evidence source: draft_model, method: generated_real_input_neighbors_v1**. They do not claim observed evidence about a real person. Native units and existing input shapes remain unchanged. One existing ratings-model integration assertion hardcoded only the old reasons; the user authorized adding generated to that assertion. No edit to `ratings_model.py` or `draft.py` was necessary.

## Copied-save acceptance comparison

Baseline is the actual E2b-containing working tree at task start, so it differs from the earlier numbers in the task prompt. Real comparators are the canonical 2024 and 2025 draft classes, positions 1–5, using the same current real-input file and unchanged profile display scale.

| 2027 pick | Generated role | Current ability | Before OVR | After OVR |
|---|---|---:|---:|---:|
| 1, Keon Vasquez | Rim protector | 47.80 | 26.6 | 54.0 |
| 2, Simeon Rojas Cabral | Scoring wing | 53.00 | 27.1 | 57.9 |
| 3, Milan Hayes | Two-way wing | 44.00 | 8.4 | 38.3 |
| 4, Amari Rhodes | Versatile forward | 58.57 | 30.3 | 64.0 |
| 5, Rocco Mathis | Rim protector | 52.10 | 34.9 | 59.4 |

- Top-five median: **27.1 → 57.9**. Real 2024 top five: **57.6**; real 2025 top five: **63.8**; combined 10-player median: **61.1**. Median model ability is **52.1 generated versus 53.37 real**. The generated median is 3.2 display points below the combined real cohort, within that cohort's observed spread.
- Lottery minimum: **37.0**. No near-zero lottery ratings. Pick 3 remains relatively weak because its actual current ability is 44, despite high potential; no pick-slot floor or individual-player override is applied.
- Across all 60 rookies, current ability versus derived display OVR Pearson correlation: **0.9022**. Shape and physical differences remain visible rather than forcing draft-order rankings.
- All 60 rookies and the one replacement have **94 inputs each (5,734 total)**. **Zero** mismatches between adapter output from effective inputs and the engine's actual 15 traits. The profile reads those same effective inputs.
- Complete inputs, including attribution, are byte-identical across fresh processes with PYTHONHASHSEED=1 and 29. Final digest: `3c762712ed01f46ac6c6ba399e07307dd4f8c7b0438f7fe439777f54e3c64d42`.

## Verification and performance

- Focused model suite: **134 tests pass in 58.673 s** (`PYTHONPATH=src .venv/bin/python -m unittest tests.test_input_estimator tests.test_bbi_import tests.test_player_model_schema tests.test_trait_adapter tests.test_ratings_model tests.test_player_profile`). Covers estimator, BBI, native schema, adapter, ratings model and player profile. New checks cover empirical reference use, supplied draft and legacy profiles, current-ability progression, potential separation, real 2026 prospect/signing isolation, native body dimensions, replacement identities, all 94 inputs, lottery floors, normalized choices, traversal independence, global RNG preservation, process determinism reuse across daily save-field changes and explicit generated identities with attached stats.
- Rebuilt all 691 real players into `output/e2c/real_inputs_rebuilt.json`: **byte-identical JSON and gzip** to the pre-existing working-tree canonical artifacts. JSON SHA-256: `38305db58760760b6dd97e4f5ea8abb7e933178fc0c2416dfa9c723dccb12fe9`; gzip: `fd5ce85c2bc56bb7c04bbe0cc0a7e812c559bfbb6d3c79a80367e79ea379a43b`. Canonical files were not rewritten by E2c.
- Full repository diagnostic: ran the prescribed `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests`, then interrupted it after about 16 minutes in the older foundation/free-agency tests. It had already emitted multiple failure markers and one error marker; **no completed full-suite result or all-green claim is made**. A separate pre-E2c dispatch check reproduced the known box-variation failure: mean FG% shift **0.026424 > 0.025**. That check disables only the two new generated dispatches and leaves all pre-existing estimator/data changes intact. Eight other sampled candidates passed in isolation, so those markers are not asserted to be proven baseline failures; suite ordering/subtests make progress-marker attribution unreliable. Logs are retained. The required focused model suite is complete and green; this task edits no shared engine/save implementation and does not undertake the board's broader test-repair work.
- Copied-save benchmark, common league I/O/adapter prewarmed: old estimator path **1.38 s**; new path first conversion of all 61 generated definitions **3.11 s**; subsequent rebuild after invalidating the outer ratings-model cache **1.00 s**, with 61 definition-cache hits. First conversion has extra real-reference loading/calibration cost; repeated daily stats do not incur that cost. These are local timings, not a new month-simulation benchmark. No per-possession work is added.
- Generated ratings and therefore generated-player gameplay intentionally change. Real-player inputs, RNG code and default switches do not. Simulation scorecards were not used as calibration targets. E2b's separate real-stat gate remains unresolved.

Artifacts and reproducer: `output/e2c/verify_save.py`, `save-validation.json`, `save-validation-1.log`, `save-validation-29.log`, `before.json`, `benchmark.py`, `benchmark.json`, `model-tests.log`, `full-suite.log`, `baseline-failure-check.log`, `rebuild.log` and the copied scratch save/sidecars. Large files stay in ignored output/.

## Resume state

Implementation, final 134-test focused run, real-input byte-parity rebuild, copied-save comparison, performance check and two-process deterministic replay complete. Broader repository diagnostic stopped with failures as documented above. E2c is ready for coordinator review; no commits. Ratings-model and draft implementation files remain untouched. Concurrent coordinator edits to other board rows were preserved.
