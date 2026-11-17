# Player model schema implementation — November 12, 2026

Milestone 1 is implemented: a versioned, validated, optional input store and complete definition/coverage registry. **All new inputs are dormant.** Nothing is populated in canonical players or normal new careers. There is no old-trait conversion, gameplay adapter, second development system, numeric calibration or UI change.

The approval contract is `PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md`. This work preserves 64 skills: S01–S46 and both recognition/execution fields for each F01–F09. Together with P01–P12 and T01–T18, these are 94 separate input dimensions/families. All C01–C37 and R01–R22 are registered as derived, independently nontrainable outputs. Registration does not implement their formulas or establish coefficients.

## Implemented surface

| File | Responsibility |
|---|---|
| `src/nba_gm_data/player_model_registry.py` | Authoritative, versioned definitions, meanings, representations, physical inclusion, units and dependency edges. Public reads return private copies. |
| `src/nba_gm_data/player_model.py` | Validated immutable `PlayerInputs` snapshot, explicit serialization and optional save-section access. |
| `src/nba_gm_data/save.py` | Seven-line optional validation hook in existing read/write manifest validation. Absent section short-circuits without importing the new model. |
| `tests/test_player_model_schema.py` | Sixteen focused contract, persistence, isolation and release tests. |
| `scripts/verify_player_model_schema.py` | Reproducible machine-readable registry/coverage export and disposable real app-action probe. |

Artifacts are under `output/player-model-schema-2026-11-12/`. `registry.json` is a generated inspection copy of the Python registry, not a second editable authority. `coverage.json` is keyed by all 94 input IDs and all 59 derived/role IDs. Each input separates definition, evidence/estimation, optional storage, planned dependencies, actual gameplay consumers, actual presentation consumers and tests. Every actual new-model gameplay/presentation consumer is currently empty; every overall input-completion flag is false. Research evidence is a separate workstream; no unavailable evidence was replaced by a number.

## Storage and validation contract

The optional save key is `player_performance_inputs`. Both the section and each player document declare `version: player_performance_inputs_v1` and `registry_version: player_performance_registry_v1`. Section `players` maps stable player IDs to player documents containing `player_id` and a sparse `inputs` map. For example, `inputs["F01.recognition"]` and `inputs["F01.execution"]` are distinct keys, never one family average.

Use `PlayerInputs(document)` to validate and own a snapshot, `to_dict()` to obtain its private plain JSON representation, and `put_player_inputs` / `get_player_inputs` for optional save access. The existing JSON save writer, load validator, backup/checksum, export and restore paths carry the section. No new save format, sidecar or automatic migration is introduced. Imported and generated player IDs use the same schema; resolving identity against a future import pipeline remains that pipeline's responsibility.

A missing input means unknown. Explicit unknown records require `status: unknown`, a null value, an explanatory reason and unknown confidence. Known estimates require provenance and uncertainty notes. Evidence supports source, method, date, sample size, exposure and shared-evidence IDs; shared evidence does not claim independent observations. No default 0, 50, uniform distribution or inferred measurement is generated.

Representation decisions are storage contracts, not calibrated mechanisms:

- Skill grades retain fractional 0–100 values plus a declared scale ID. These are storage bounds, not approved anchors. Technique definitions exclude separately modeled physical advantages; effective source statistics cannot become technique-only talents merely by using this container.
- Physical families hold protocol-labeled measurements/estimates in allowed physical units. Height/span/reach/jump use cm; mass kg; movement m/s, m/s² or protocol timing; strength/balance/conditioning/recovery retain appropriate test units. Explicit unit conversion/import mapping is future work. Capacity display grades have their own scale and field. Geometry and mass cannot be supplied only as a display grade. Multiple lateral/COD observations remain inside P07; COD is without the ball. Intervals use their measurement's unit.
- T01/T02/T03/T11/T13/T16/T17 use conditional probability distributions with declared reference conditions. T02 also declares its spatial reference. Other tendencies use reference-conditioned propensities in [0,1]. Outcomes and row conditions are validated; probabilities must sum to one and are never silently normalized. These shapes do not activate action choice or prescribe future distribution calibration.

Unsupported versions, extra fields, unknown/derived input IDs, mismatched player keys, invalid types/units/ranges, booleans as numeric values, nonfinite numbers, malformed dates and invalid distributions fail validation before publication. There is no independent C/R value store or growth API. Conditional distribution uncertainty beyond confidence/notes is not yet a fitted statistical model.

## Dependency and ownership findings

The registry validates exact approved ID sets, known dependencies, acyclicity, derived nontrainability and no summary feedback. C16 expands all 18 passing fields; C33 uses nine recognition fields. C31 excludes free throws; R21 explicitly includes C04. C36 reads C27/C32 and never feeds R18 or an action capability as another bonus. The spatial contract retains action responses, routes, timing/coverage, possession opportunities, preferences, reference conditions and evidence; shooting heatmap frequency/efficiency remain separate from defensive coverage.

R21's listed dependencies are an explicitly provisional envelope of action capabilities C01–C33 plus C37. The approved map does not enumerate a finalized R21 formula. No coefficient or additive interpretation follows from this envelope. All derived definitions still need technical and single-variable verification before activation.

`PlayerInputs` owns only immutable serialized JSON. It retains neither source records nor a save/career graph. Returned dictionaries and save attachment are private copies. A weak-reference test proves the snapshot releases immediately after the caller drops it, even while its serialized input section remains in a save; no forced GC or global player cache is involved. The fixed catalogue is bounded immutable definition data, not a review cache.

## Verification

**16/16 new tests pass.** The focused combined run has **65 passing checks out of 67**. Its two failures reproduce against the frozen pre-edit `save.py`: existing `load_save` adds `staff_season_changes`, while two legacy persistence tests assert their original dictionaries remain unchanged. See `pre-edit-known-failures.txt`; this pass does not change that unrelated behavior. Save recovery tests include normal app dispatch and HTTP recovery coverage.

The actual disposable action probe creates a GSW career with seed 17, reads Stephen Curry's complete card, attaches a private synthetic partial record, writes/loads, performs the normal settings action, exports, restores and reads the card again. The records round-trip exactly, the settings action preserves them, and all three full card payloads match. The deliberately synthetic passing estimate is not a real player estimate and exists only in the deleted temporary career. Date/phase do not advance. The attached player document is 844 bytes in this probe; this is not a league-population memory estimate.

Only `save.py` changes among the 107 pre-existing production/GUI/canonical/approval files in the fresh manifest; its exact diff is retained. All other tracked hashes match. All probe careers and their history/backup files are removed. No playable save, research file, approved map, coordinator status file or GUI file changed. No long simulation or timing claim is made. No server restart was needed or authorized for this milestone; the existing preview was preserved, and it is not claimed to have loaded this new dormant validation code.

Reproduce from the repository root:

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest test_player_model_schema -v
PYTHONPATH=src:tests .venv/bin/python -m unittest test_player_model_schema test_save_persistence test_save_recovery -v
PYTHONPATH=src .venv/bin/python scripts/verify_player_model_schema.py --output output/player-model-schema-recheck
```

The second command currently has the two documented pre-existing failures. The third uses only a temporary career and writes new evidence; it does not refresh a server or mutate canonical players. `verification.json` records final hashes, artifact counts, test totals and unchanged-file findings. The frozen save reference is retained for differential failure reproduction without replacing shared source files.

## Recommended next complete interior-defense chain — not implemented

Implement S36/S37/S45 with the relevant physical tools and T16 into C27, then the interior portion of C32 under explicit starting position, responsibility and opportunity conditions. Keep recognition/help dependencies visible where arrival matters. Produce R18 and the C36 summary from that same response, with no second rim-deterrence bonus. Use the approved contrasting cohort and source/inference distinctions; do not populate unsupported raw decomposition from an effective block percentage.

The first consumer change must reach actual attempts and scoring: `spatial.py: player_spatial_profile`, `team_spatial_profile`, `spatial_matchup_adjustment`; `sim.py: player_feature_vector`, `team_shot_diet`, `simulate_team_line`. Audit `distribute_player_lines` so contests/blocks/fouls reflect the same resolved opportunities rather than adding decorative blocks after predetermined points. This is a bounded interior slice, not a possession-engine rewrite.

Complete the chain through consistent player summaries (`save.py: player_attribute_summary`), AI on-court/roster value (`transactions.py: player_on_court_value` and its feature inputs), and dependent contract/retention decisions. Keep actual rotations unchanged. Before activation, test positioning versus contest technique versus reach, foul-control and stay-down consequences, reference versus deployed responsibility, and C36 non-additivity. Require coherent expected attempts/points/blocks/fouls plus deterministic bounded game/action daily/bulk/reload tests and measured overhead. Retire the corresponding old rim contribution at cutover; do not grow/edit both models. Numerical anchors and response coefficients require review, not invention in this schema milestone.
