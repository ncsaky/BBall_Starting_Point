# Five-player calibration implementation — November 10, 2026

Installed **all eleven approved trait targets**, including Duren and Kawhi rim components, for **new careers only** as `2026-11-10-five-player-scouting-v11`. No candidate subpart is held. The bounded game gates found meaningful but limited effects, continuous rim-feature transitions and no evidence requiring an unrelated compensation or formula change. This is a reviewed scouting calibration, **not** a measured box-stat refresh or a season-effect estimate.

Latest verified preview: **http://127.0.0.1:8796/**, PID **84101**. An authenticated real `player_card` read on a disposable v11 career reports Kawhi DEF **97.5**. Startup module hashes and the calibration function's bytecode fingerprint are in `output/five-player-calibration-2026-11-10/loaded-backend.json`; `preview.json` records command, version and the idle refresh checks. Other previews and active/playable careers were preserved.

## Installed decisions and provenance

| Player (stable ID suffix) | Absolute targets |
| --- | --- |
| Edwards (`player_min-anthony-edwards`) | defensive_effort **73.89** |
| Vassell (`player_sas-devin-vassell`) | shot_versatility **52.36**, defensive_effort **75.80**, rim_deterrence **60.94** |
| Duren (`player_det-jalen-duren`) | rim_deterrence **90.00**; OREB remains **99.40** |
| Coward (`player_mem-cedric-coward`) | defensive_effort **63.99**, rim_deterrence **60.89**, scheme_iq **56.25**; passing_reads remains **58.83** |
| Kawhi (`player_tor-kawhi-leonard`) | shot_versatility **67.89**, handle_pressure **76.44**, rim_deterrence **74.25** |

The versioned JSON decision file records expected pre-values, stable IDs/names, absolute targets, decision date and the SHA-256 of `FIVE_PLAYER_CALIBRATION_REVIEW.md`. An immutable review copy is retained in the evidence folder. Its cited pre-start scouting judgments, confidence limits and counterevidence remain the basis; the earlier +1.5 proposals were not applied. Source-row refresh alone previously changed zero final traits for these players.

`five_player_calibration.apply_calibration` is a small final-stage hook **after v7/v8**, retaining all previous corrections. Ordinary early manual overrides can skip later whole-profile corrections, so using those earlier stages would risk changing unrelated traits. This hook checks the current exact pre-value and identity, rejects drift, records `five_player_scouting_v11`, caps confidence at .55 and uses absolute targets. Reapplication is identical and never stacks a delta. Baseline preservation is not disabled.

The canonical and v11 archive were rebuilt through the existing importer; the registry adds v11 and retains every previous version. Existing-career selection still uses `baseline_for_save`. The new layer is never applied to saved development or loaded old-career traits. Talent/offense model versions, rating formulas, actual rotations, contracts, roster membership, AI quotas/thresholds, narrative/signing fixes and performance implementations are unchanged.

## Actual feature and gameplay gates

The rim feature is `clamp(raw + .18 × max(0,raw−68)^1.18, 1, 99)`. Defensive anchor mixes rim (45%), activity (30%), impact (15%) and integrity (10%). Team shot diet uses weighted rim defense to reduce rim share and shot quality. Block generation adds a continuous hinge above feature 88; rebound generation also uses rim defense with an additional hinge above 92. Final box normalization, rounding and variation then act. **A feature point is neither a scoreboard point nor a percentage of defensive effectiveness.**

The raw 68–100 sweep in 0.1 steps has a maximum feature increment **0.13748**, with a high-end saturation plateau, not an abrupt numeric jump. Duren **98.99→90** moves feature **99→96.908**, anchor **80.367→79.221**. Kawhi rim-only **89.25→74.25** moves feature **95.881→75.815**, anchor **88.583→79.385**. Rebounding summaries also decline despite unchanged OREB: that cross-skill coupling already exists in this model and was explicitly considered, rather than compensated with an unrelated buff.

### Fixed-roster matchup experiment

Eight identical seeds (17/29/41/53/67/79/83/97), three opponents, healthy fixed canonical rosters and source-minute allocations. The native scoring/box engine runs; only coach matchup minute nudges are disabled in this diagnostic so rotations stay fixed. HOU supplies more interior pressure (rim-pressure feature **56.512**, spacing **51.481**), GSW more spacing (**52.832 / 59.938**), BOS the intermediate comparison (**51.868 / 57.176**). These are the current fictional career's rosters, not claims about real NBA team styles.

There are 288 short game calls across before/candidate cases and Kawhi's separately measured offense-only/rim-only/combined cases. Total probe wall time is **30.87 s**, including canonical copying, contexts and AI valuations, not pure game CPU or a speedup claim. No season simulation ran. Raw per-seed points, blocks, rebounds, player production and opponent control-player lines are in `game-probe.json`.

Mean deltas by opponent HOU / GSW / BOS:

| Candidate | Team points allowed | Target player points | Target player blocks |
| --- | --- | --- | --- |
| Edwards effort | 0 / +.125 / +.250 | 0 / 0 / 0 | 0 / 0 / 0 |
| Vassell combined | +.250 / +.125 / +.125 | +.250 / +.250 / +.250 | 0 / 0 / −.125 |
| Duren rim | 0 / 0 / +.125 | 0 / 0 / −.125 | 0 / 0 / −.500 |
| Coward defense | −.125 / −.125 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Kawhi offense-only | −.500 / +.750 / −1.625 | +1.375 / +1.125 / +1.000 | +.125 / 0 / 0 |
| Kawhi rim-only | +.750 / +.125 / +.875 | 0 / −.125 / 0 | −.500 / −.500 / −.625 |
| Kawhi combined | +.125 / +1.000 / −.625 | +1.375 / +1.125 / +1.000 | −.375 / −.625 / −.750 |

Kawhi combined team scoring rises **+.500 / +.375 / +.625**. His rebounds change **0 / −.625 / −.375**, while team rebounds change **−.625 / −1.375 / −2.500**. Duren's player rebounds change **+.125 / 0 / 0** despite a lower rim trait; team blocks change **+.125 / 0 / 0**. These non-monotone details are retained, not hidden behind a selected average. Full team block/rebound and player results for every case remain in the artifact.

The sample supports direction/scale checks, not a season win estimate. Shared RNG consumption, integer allocation/rounding, box variation and normalization mean a changed offensive input can change opponent results at the same seed. **Kawhi's offense-only allowed-points movement is not evidence of improved defense**. Component changes do not add linearly, and a single seed's discontinuity is not a trait-formula cliff. Rim-only removes center-like influence without a remotely 20-point scoreboard shift here; larger studies might find different means. This evidence does not settle his remaining high effort/navigation ratings.

Paint efficiency is **unavailable** from these result fields: `rim_attempts` is recorded but not corresponding rim makes/paint FG%. Two-point accuracy must not be relabeled paint efficiency. Independent HOU–GSW control games at two seeds are exactly unchanged; unrelated trait values are also unchanged across the entire canonical universe.

### AI effects

Fixed-input asset values before → combined: Edwards **98.20→97.33**, Vassell **84.54→83.40**, Duren **80.77→79.52**, Coward **75.81→77.75**, Kawhi **82.26→77.71**. Creator/anchor and full valuation components are retained per scenario. Kawhi offense-only value is **82.90**; rim-only **77.07**. In particular the rim feature crosses the existing **78** scarcity threshold, removing **6 raw scarcity points** (weighted by .55 in price), in addition to reduced on-court value **83.68→81.79**. This is a deliberate loss of the model's rim-specialist category, not an OVR rounding artifact or a change to premium safeguards. No trade-search policy was edited.

## Real cards versus canonical estimates

These are **observed `player_card` action ratings** from separate real new v10/v11 standard careers at October 20, seeded 17, with actual initial AI roles/health. They are not fixed-source-minute estimates. OVR can differ from the research crosswalk because actual career role minutes differ. Old v10 career card responses remain byte-for-value equal when read with the new canonical, after normal cache invalidation.

| Player | New-career OVR v10 → v11 | OFF v10 → v11 | DEF v10 → v11 |
| --- | --- | --- | --- |
| Edwards | 93.5 → 93.2 | 93.8 → 93.8 | 94.0 → 92.2 |
| Vassell | 85.4 → 85.0 | 81.9 → 82.6 | 91.3 → 88.8 |
| Duren | 85.9 → 85.1 | 80.5 → 80.5 | 90.4 → 88.8 |
| Coward | 74.7 → 75.8 | 75.4 → 75.4 | 76.6 → 80.1 |
| Kawhi | 95.0 → 94.7 | 90.5 → 91.2 | 98.2 → 97.5 |

Small headline changes are not the acceptance criterion: Kawhi's feature/anchor and AI-category effects are substantial. DEF remains high because his effort/navigation/IQ are still high and the presentation transform compresses elite values. No effort/navigation changes or headline formula redesign were smuggled in to force a preferred display balance.

## Verification and reproduction

- **47 targeted checks pass**: exact eleven-cell diff across all numerical traits; contracts/players unchanged; identity/pre-value guards; absolute/idempotent application; full deterministic canonical rebuild; retained prior provenance; old v10 traits with development and model flags; narrative/signing/spatial/calendar/human-rotation regressions.
- **40 additional AI/talent/new-career checks pass**, plus the remaining **two career checks pass** with the required `scripts` import path. Their initial errors were invocation-related missing test-helper imports, not production failures. The initial development-preservation fixture also required an empty event list and was corrected. No production rule was altered to satisfy a test. No other pre-existing failures appeared in this selection; the earlier unrelated foundation rebound-range failure was not rerun here.
- Real v11 bulk/daily/midpoint export-reload actions through October 22 have identical meaningful state and **16 ordered full events**, including transactions and development fields. Existing phase/overflow/deadline tests preserve decision policy. Old/new game results can intentionally differ; old/new gameplay parity is not asserted.
- The preview was gracefully refreshed only after socket/thread/stack evidence showed idle ownership; its real card read confirms v11 data and both prior backend fixes. Only disposable saves were created/read. No GUI, research-document, active-career or dependency change occurred.

Evidence folder: `output/five-player-calibration-2026-11-10/`. The prior canonical, immutable review snapshot, candidate targets, game/control probe, actual cards, action comparisons, test logs, preview identity and source manifests are retained. Re-run tests sequentially:

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest \
  test_five_player_calibration test_narrative_simulation test_released_fa_opportunity \
  test_spatial test_simulation_consistency test_user_rotation_roster \
  test_roster_retention test_talent_balance test_new_career_start -v
```

`probe.py` records the original private candidate experiment; do not rerun it against installed v11 and label that a v10 comparison. Reproduction must load `before-canonical.json` (or the registered v10 archive) and use a fresh output directory. `actions.py` and `controls.py` retain the exact disposable action/control recipes; choose new output subdirectories before rerunning. `test_final_order_provenance_and_rebuild` verifies importer reproduction without replacing production data. Do not rerun the old-PID refresh script. Stop after this batch; no next-player corrections, formula changes or broader input refresh were begun.
