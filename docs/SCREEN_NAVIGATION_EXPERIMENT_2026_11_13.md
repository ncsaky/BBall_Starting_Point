# On-ball screens versus navigation — November 13, 2026

The bounded screen/navigation extension is implemented inside the existing default-OFF creation/passing event kernel and is ready for coordinator review. A set screen with roll, set-and-hold, or deliberate slip now produces its own navigation delay and receiving opportunity. Gifted screen meters, roll deadlines and roll-defender gaps are bypassed on this path. There is no new scoring engine or app activation.

The approved 94 inputs, 37 capability definitions and 22 role/output definitions are unchanged. The completed milestone-4 recovery remains historical; this work followed `SCREEN_NAVIGATION_ACTIVE_TASK.md`. No settlement, market/contract, UI, preview/server, production-rating or long-season work occurred.

## Audit, provenance and opt-in boundary

Audited the milestone-4 `DriveSetup`, containment, passing, help, shot planning and event attribution before editing. The prior action supplied `screen_separation_m`, `roll_window_s`, a static roll location and `receiver_defender_gap_m`; none was a learned screen or navigation outcome. It already had separate passing reads/delivery, catch quality, clocks and coherent shooting accounting.

Frozen the complete milestone-4 creation, offense, defense, geometry, event-kernel and simulator modules under `output/screen-navigation-2026-11-13/reference/`. Their SHA256 values are authenticated against the pre-edit source inventory in `reference/hashes.json`; older milestone artifacts were preserved. No applicable AGENTS.md was found in the repository or ancestor locations.

`CreationExperiment.screens` defaults to `None`. Its revision includes screen material only when configured, preserving exact old revisions/results with the feature OFF. The new module supplies an action phase to `resolve_drive`; actual handling, passing, receiving, shooting, free throws, rebounds, points and box scores stay in the existing planner/kernel.

Changed existing implementation is limited to `creation_passing.py` and `interior_game.py`. Added `screen_navigation.py`, `experiments/screen_navigation/fixtures.py`, `tests/test_screen_navigation.py`, and `scripts/run_screen_navigation_experiment.py`; this checkpoint/report and bounded outputs are the other owned edits. `sim.py`, `offense_response.py`, `interior_defense.py`, `shot_geometry.py`, approved architecture, coordinator status, historical milestone reports/checkpoint, source packets, ratings and saves were not edited. Research-owned checkpoint changes observed during concurrent research are separately identified in the manifest.

## Mechanism and actual dependencies

One supplied on-ball call identifies creator/screener, initial body/ball/defender positions, a roll endpoint and either `stay` or `show_then_recover` coverage. These are context, not player talents. One-to-one matchups still come from the existing creation setup. The configured helper and roller defender must be separate participants in this bounded coverage slice; overlapping responsibilities are rejected rather than modeled twice.

| Participant / input | Actual consumer |
|---|---|
| Screener S27 | Placement dispersion, time to establish a legal/stable position and effective contact hold. Placement, setting time and legality are components of the same provisional technique response, not independent evidence-derived bonuses. |
| Screener S28 | Notices a slip option separately from preferring it; controls release timing after a set screen or before contact on a slip. It adds no shooting/finishing accuracy bonus. |
| Screener T11 | Exact approved `screen`, `roll`, `pop`, `slip` distribution under the declared `on_ball_screen` condition. `screen` means hold the set screen without releasing to receive. `roll` sets then releases. A preferred slip can be missed and become a set/roll. Nonzero pop is rejected; it is never relabeled F03. |
| Screener P01/P04/P08/P09 | Height in cm maps to an exploratory obstacle radius (`0.12m + 0.0007m/cm × height`); mass in kg affects collision inertia separately from strength/balance capacity. P08/P09 use the declared synthetic capacity scale, not invented force measurements. Body size cannot substitute for screen technique. |
| Navigator S35, S41/S44 | S35 changes route detour/contact escape. S41 × S44 controls action-recognition delay. Neither is treated as measured lateral speed. |
| Navigator P01/P04/P05–P09 | Body geometry/inertia/resistance, dimensional acceleration and speed/lateral limits govern arrival, detour and contact. A faster navigator does not automatically get perfect containment; existing S33/S34 still supply the final control component. |
| Creator existing S16/S19, P05/P06 | Dribble execution and dimensional travel determine screen passage and arrival at the drive decision. The same passage time determines how long a supplied show policy holds its defender; it is not separately awarded as another physical bonus. S20 and security retain their existing decision/loss roles. |
| Roller defender S41/S44, P05/P06/P07 | Recognition and actual movement determine show position, release to recover and pursuit toward the receiving area. Stay can close the opportunity before the creator can deliver. No fixed roll gap or timeout opens it. |
| Existing C27 inputs | The roller defender compiles the same interior profile from the same snapshot: S36/S37/S45, P02/P03/P05/P08/P09/P10 and T16. Explicit supported wingspan is required before simulation for varied contests. Actual catch geometry/reach supplies contest arrival; existing C27 supplies conversion/block/foul response. |
| Existing F03/F04, S14 and finishing | Separate recognition/execution selects and delivers to the moving roller. Placement/travel/catch delay must fit the derived window. Receiving quality/preparation and the appropriate layup/dunk/lob response remain in the same kernel; a good screen cannot guarantee a catch or make. F06 kicks and existing spacing/help remain available. |

Screen projections support explicit `screener`, `navigator` and `coverage` roles. Unused skills remain absent from the projection rather than imputed: a navigator need not invent S27/S28/T11. A screener requires S27/S28, P01/P04/P05/P06/P08/P09 and T11; a navigator requires S35/S41/S44, P01/P04/P05/P06/P07/P08/P09; recovery coverage requires S41/S44 and P05/P06/P07, plus the existing C27 dependencies for its contest. Every participant projection must match the authoritative creation/offense snapshot; stale or manually forged compiled fields are rejected.

Synthetic technique/capacity scales and `interior_scenario_reference_v1` dimensional protocols are explicit compiler contracts. Source technique scales, reported body protocols and missing movement tests are not silently converted into these controls.

## Contact, windows and shared accounting

The intended screen location first determines a possible obstacle. Contact then uses the **screener's actual position at defender arrival**. A screener who has not arrived receives neither a contact benefit nor an illegal-contact foul. Late/unsettled contact weakens both hold and detour and can cause an illegal screen. This corrected a defect found in final review where the intended location alone could have produced a delay.

A deliberate slip has zero contact overlap, hold, detour, contact delay and illegal-contact probability. Its opportunity comes from earlier release and the defender's supplied coverage/recovery, not the full set-screen benefit. Technique, body size, preference, recognition and physical arrival have distinct local tests.

A roll/slip trajectory follows release time and acceleration/speed toward the declared endpoint. Its receiving interval opens as the receiver enters the approach area and closes when the covering defender physically recovers to that area. The endpoint can remain presented while the defender is away; no arbitrary gifted seconds extend it. Moving-target interception is resolved with a bounded iteration; sampled placement/catch delay can still invalidate an initially seen window. Expired windows are typed delivery losses, with no invented FGA or rebound.

The phase runs only on the initial action of a possession. Resets and offensive rebounds use no-screen continuation, with no automatic re-screen, gifted roll or inherited assist. Missing calls likewise use zero screen displacement and no roller, preserving ordinary contained-drive kick/reset alternatives. Initial movement, screen timing, pass/catch preparation and reset costs consume the existing clock. A foul after clock expiry does not get charged as an additional loss.

A modeled illegal screen is a nonshooting **offensive** personal foul and one turnover on the screener. It creates no FT, steal, assist, shot or rebound. The new `offensive_foul_by` ledger field is distinct from existing opponent shooting-foul attribution; team/player foul totals reconcile both sides. All ordinary shooting-foul/FG/FT/rebound rules remain in the shared kernel.

For roll finishes, existing C27 responses evaluate recovering roller coverage and a nearby configured defender/helper. The selected single strongest eligible contest supplies conversion/block/foul effects; full defensive talents are never added. Blocks and contest-sourced fouls use that selected defender, and anchor C36 reports exclude another defender's selected contests. The existing controlled base shooting-foul channel can still attribute a foul independently; no offensive-screen free throws are inferred from it.

## Verification and reproduction

```sh
PYTHONPATH=src:tests:.:scripts .venv/bin/python -m unittest test_screen_navigation test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research -q
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_screen_navigation_experiment.py --output output/screen-navigation-2026-11-13/verified
```

Use a different `--output` to preserve the retained run. The runner is offline, writes experiment artifacts only and starts no server or save/career action. Final actual test/runner results are recorded below and in `verified/tests.txt`, `run.txt` and `summary.json`.

**148 tests passed in 22.353 seconds:** 25 dedicated screen checks plus all 123 creation/passing and prior regressions. Coverage includes technique versus size, navigation versus lateral movement, early/late recognition, preference, contact-free slips, missed/late screens, roll-window denial/expiry, receiving, screen-phase court-side reflection, illegal-screen ownership, clock precedence, absent/zero-exposure participants, missing units/scales, conflicting/forged projections, revisions, JSON input reconstruction, output mutation isolation and root release.

The bounded runner exercises 22 combined games over seeds 17/29: roll, slip, hold, stay, no call, unsettled contact, near-help/no-help, weak/strong passing and near-recovery controls. Each starts with 16 regulation possessions per side; hold/seed29 and unsettled-screen/seed29 also exercise one ten-possession overtime. Scores and loss rates are uncalibrated mechanism outputs, not NBA forecasts. Sixteen additional one-input phase responses isolate S27/S28, height/mass, S35/P07 and anticipation/attention.

The retained corrected run samples 309 roll choices, 287 slips, 84 holds and 670 no-screen continuations/uncalled actions, F03/F04/F06, finishes and resets; 14 actual illegal-screen losses, handling losses, delivery errors, failed catches, shooting fouls and clock losses occur. Near-help cases produce 8/4 timely-help events across seeds 17/29, while matched commitment-zero cases produce 0/0. Near-recovery controls deliberately delay a synthetic creator and use a long recovering defender to exercise real selected roller contests. The near-recovery games select 7/3 roller-defender contests across those seeds. Dedicated action checks cover catch-time expiry; it is not falsely claimed as a naturally sampled game outcome.

Full prior-mode comparisons substitute **all frozen creation/offense/defense/geometry modules**, then load the frozen event kernel, rather than compare two paths sharing a changed resolver. Eight complete real-roster default-off results (SAS/MIN and GSW/BOS, two seeds, both modes) and twelve complete prior interior/coupled/creation results match exactly. The dedicated suite adds sixteen synthetic ordinary/prior comparisons across both modes/seeds. Revisions also remain unchanged with screens OFF.

## Research preservation

The independent research packet was validated unchanged: eleven named source players, 94 IDs each, 949 explicit source unknowns, and nine tiny synthetic sections. Those tiny sections are intentionally not complete gameplay profiles. Named source documents are rejected as complete synthetic-contract screen actors rather than silently filled. The separately researched operational pilot layer was not imported, changed or activated; its scales and dimensional trial mappings require separate review. The ten-player fixtures here are independently labeled synthetic controls complete for these consumers, with their raw assumptions retained in `configuration.json`.

The screen/navigation packet's exact digest and validation counts are retained in `research-preservation.json`. No new broad research pass, source re-extraction, production rating deployment or named-player rank tuning was performed by this backend task.

## Bounded cost and release

Five warm sequential samples per path, after regression tests finish. Game-call timing includes snapshot/projection validation, action/shot planning, diagnostic construction and accounting. Full JSON preparation is measured separately; core payload filtering happens before conversion. There is no instrumented kernel-without-diagnostics or HTTP/production-speed claim. All experimental timing fixtures use 16 regulation possessions per side; the ordinary path retains its existing full-game budget.

| Path | Game median / range (ms) | Full JSON (ms) | Core JSON (ms) | Full / core bytes |
|---|---:|---:|---:|---:|
| Ordinary default | 5.661 / 5.649–5.713 | 0.202 | 0.138 | 7,444 / 7,444 |
| Prior interior | 0.787 / 0.776–0.873 | 0.974 | 0.095 | 46,999 / 4,981 |
| Prior coupled | 3.060 / 2.945–3.997 | 7.241 | 0.103 | 365,745 / 4,981 |
| Prior creation | 8.637 / 8.613–8.983 | 7.841 | 0.098 | 404,069 / 4,973 |
| Screen/navigation | 28.569 / 28.128–30.054 | 10.752 | 0.101 | 497,010 / 4,977 |

Full diagnostic payload cost is deliberately visible; it includes raw input/spatial reports and detailed screen/creation/contest ledgers. No live payload optimization or settlement/performance change is included. Six fresh-fixture same-process memory calls probe owned configs, profiles, input snapshots and results. All 42 roots release before diagnostic GC; no production GC or global experiment cache was added. Exact allocation/RSS observations and their limits are in `memory-release.json`; this short window establishes no long-career/server stability.

In the final sample, screen diagnostics add 492,033 bytes over the core result. Traced peak is 1,981,217 bytes (~1.89 MiB); current allocation is 88,473 bytes before final diagnostic GC and 9,577 after, including probe bookkeeping. RSS spans 78,240–172,336 KiB (~76.41–168.30 MiB), reflecting a short process window and allocator/OS state. These observations do not isolate whole-server retention or predict long-career memory.

## Retained controls and review boundary

Coaching call, initial coordinates, stay/show behavior, roll endpoint, one-to-one assignments, touch exposure, one configured helper, rebound support and clock/reset policies remain supplied. These are not researched player talents. Illegal-screen setting/contact probability, body-radius/contact-capacity maps, navigation/release timing and receiving-area constants are exploratory, not fitted rates or official-rule adjudication.

Pop, off-ball shooting screens, independent cuts/relocations, re-screens, switching/drop/hedge decision engines, overlapping helper/roller-defender responsibility, complete screen legality/bonus/nonshooting-foul administration, and-ones, retained deflections/bobbles, full rotations/foul-outs/workload and complete C17–C19/C25/C29/C31/C32 remain unfinished. Their approved inputs stay stored; none was removed or renamed. F07 cross-court passing retains its prior explicit disabled status.

The feature remains default OFF and unwired to app advancement, calendars, daily/bulk/reload, UI, AI/development and live economics. Exact engine comparisons and input reconstruction do not establish those unwired paths. Stop for coordinator review at this bounded mechanism; no whole-model calibration, pilot readiness or production activation is claimed.
