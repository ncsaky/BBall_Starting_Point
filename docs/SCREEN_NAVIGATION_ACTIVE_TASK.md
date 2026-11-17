# Active backend task: screens, navigation and roll/slip openings

This supersedes the completed milestone-4 recovery assignment. After interruption or compaction, reread this file AND the current user assignment before editing. Do not resume settlement optimization, restart previews or redo completed recovery work. Update the resume section after each stage. Stop for coordinator review after this bounded milestone.

## Starting state

Creation/passing milestone 4 is complete within its experimental scope, default OFF. Coordinator independently reran 123 tests (28 creation/passing + 95 previous) in 5.370 seconds. The prior report documents additional differentials and cost/release checks; the coordinator did not rerun that entire campaign. See `CREATION_PASSING_DEFENSE_EXPERIMENT_2026_11_13.md` and `CREATION_PASSING_RECOVERY_CHECKPOINT.md` for historical detail, not the active assignment.

## Objective

Replace gifted screen separation and roll/slip availability for a bounded on-ball screen action with outcomes from the approved screen technique, screen-action recognition, physical tools and defensive navigation inputs. Feed those openings into the SAME creation/passing/receiving/shot/accounting kernel. Test combined effects with existing spacing, help and passing; no isolated final calibration.

Authoritative architecture: `PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md`. Retain all 94 inputs, 37 derived definitions and 22 role/output definitions. Relevant skills include S27 screen execution, S28 screen-action recognition, S35 navigation, S41 anticipation and S44 attention. Use relevant size/strength/balance/movement inputs once, with declared units and mappings. T11 is a conditional action mix, not a technique grade. Screen quality must not become another shooting-accuracy bonus.

## Bounded implementation

- Audit current `DriveSetup` separation/window/gap fields and the resolver before changing them. Freeze authentic previous-mode references without overwriting earlier artifacts or unrelated edits.
- Implement one bounded on-ball screen -> roll/slip action family with supplied coaching call, participants, initial positions and coverage policy. Derive usable separation, defender delay/reattachment, receiver trajectory timing and receiving-window bounds from supported mechanisms. Distinguish starting geometry from skill-produced outcomes. Explicitly retain any supplied coverage behavior; do not claim a complete switching/drop/coaching engine.
- Strong navigation can reduce a screen-created opening without automatically giving perfect containment. Screen placement/technique must differ from body size/strength. A slip avoids contact but should not receive the full contact-screen benefit. Recognizing an option differs from preferring it and executing it.
- At minimum support a properly set screen with a roll and a deliberate slip. Treat off-ball shooting screens, independent cutting/relocation, re-screens and pop routes as deferred unless needed for a correct bounded chain. Do not mislabel a pop pass as F03 or enable an unsupported route just to fill out the menu. Persist all deferred approved skills/tendencies.
- Use existing F03/F04 reads/delivery and receiver finishing, with actual navigation/help/recovery timing. No guaranteed completed pass or gifted roll gap on the new path. Preserve no-screen and contained-drive alternatives.
- Handle legal versus illegal screen contact if legal positioning is part of the implemented S27 response: coherent nonshooting offensive foul/turnover accounting, no free throws or automatic steal. Keep all unsupported foul rules explicit; do not pretend existing shooting-foul accounting covers an illegal screen.
- Preserve prior modes with new feature OFF. Reject missing required dependencies rather than fabricate source measurements. Synthetic fixtures and broad research estimates remain explicitly distinct. One authoritative player snapshot and versioned derived state.

## Verification and delivery

- [x] Audit, freeze reference, list current assumptions and exact dependencies.
- [x] Implement bounded action inside shared kernel.
- [x] Add local mechanism tests AND seeded short combined games: screen skill versus body size, navigation versus lateral movement, early versus late recognition, roll versus slip, spacing and helper commitment, weak versus strong passer, unavailable participants and zero/no-screen cases. Confirm each intended branch really executes. Include court-side/coordinate symmetry where applicable.
- [x] Verify all event/box-score accounting, no duplicate possession loss, attribution, clocks/resets, stale configuration and snapshot mutation rejection. Prior OFF/prior experiment results must match full references, not two paths sharing changed code. No app daily/bulk claim while unwired.
- [x] Rerun 123 baseline tests plus the new suite. Measure short-run cost, report-size overhead and release; no long seasons or blanket league tuning.
- [x] Write `docs/SCREEN_NAVIGATION_EXPERIMENT_2026_11_13.md` with commands/results, consumed inputs and remaining controls. Retain outputs under `output/screen-navigation-2026-11-13/`; complete this checkpoint and stop.

Own minimal backend/experiment modules, tests, this checkpoint and the report. Do not edit coordinator status, approved architecture, research-owned packets, UI, live ratings, servers or unrelated files. Research works independently; synthetic mechanism tests need not wait for it. No production activation or whole-model readiness claim.

## Resume state

Active task is bounded on-ball screening/navigation → roll/slip. Implementation and all bounded verification/delivery stages are COMPLETE. STOP for coordinator review; default OFF. No unresolved failures. Do not start settlement/performance/preview/app activation/pilot calibration work. This checkpoint supersedes historical stage next-actions below and remains subordinate to a newer user assignment. After interruption/compaction reread this file AND the current assignment before editing.

## Audit completed

Active task confirmed: bounded on-ball screening/navigation → roll/slip, not recovery/settlement. No applicable AGENTS.md was found. Frozen the completed milestone-4 `creation_passing`, `interior_game`, `offense_response`, `shot_geometry`, `interior_defense` and `sim` modules plus 1,175 existing source/test/docs hashes under `output/screen-navigation-2026-11-13/reference/`; never overwrite earlier outputs.

Current `DriveSetup` gifts `screen_separation_m`, a roll endpoint/deadline and `receiver_defender_gap_m`; the same resolver already separates F03/F04 reads/delivery, help, catching, clock and shared accounting. New feature will default to None on `CreationExperiment`, preserving OFF revisions/results. With the feature ON, gifted screen separation and roll gaps/deadlines must be bypassed, including uncalled/no-screen continuations. New screen phase runs at most once per possession's initial action (no re-screen after a reset/OREB).

Planned exact dependencies: S27 technique/legal setting, S28 follow-up recognition/release timing, S35 navigation, S41/S44 defensive recognition; P01 cm for explicitly mapped obstacle radius, P04 kg for collision inertia, P05/P06/P07 dimensional movement, P08/P09 declared synthetic capacities for contact stability; T11's approved screen/roll/pop/slip distribution under one declared on-ball opportunity. Pop remains rejected/deferred, not relabeled as F03. Existing creator S16/S19, containment, F03/F04, receiving and finishing inputs are reused at their own steps. No body-size-only technique surrogate or shooting bonus. Synthetic controls proceed independently of research-owned files.

Historical next action (completed): implement a small versioned `screen_navigation.py` phase and opt-in hooks in creation/shared accounting; then dedicated causal and game tests. That historical action is complete; see final stage below.

## Shared-kernel implementation stage completed

Added `src/nba_gm_data/screen_navigation.py`, `experiments/screen_navigation/fixtures.py`, `tests/test_screen_navigation.py`; changed only opt-in hooks in `creation_passing.py` and shared accounting/attribution in `interior_game.py`. `CreationExperiment.screens` defaults None and adds revision material only when configured. Supplied calls produce a set/hold, roll or read-dependent slip; technique-dependent placement/legal setting, dimensional obstacle/contact response, navigation delay, moving receiver trajectory and a receiving window closed by defensive recovery feed existing F03/F04 and shot planning. No contact benefit on slips. Stay/show policy is explicit. Screen and configured helper/roller-defender roles must be distinct for this bounded coverage slice. Pop/off-ball screens/re-screens deferred. No screen repeats after reset/OREB. Offensive screen fouls charge the screener one turnover and personal foul, with no FT/steal.

Recovering roller coverage and the configured helper are evaluated using the existing C27 response; select one eligible contest rather than add full defensive talents. Its actual defender owns blocks/shooting fouls; anchor reports exclude another defender's selected contests. Role-specific screen projections can leave unused source fields unknown, and stale/forged compiled projections are rejected. Gifted screen meters/roll gap/deadline are ignored in the new mode; no-call actions retain no-screen drive/kick/reset alternatives.

Baseline command (same eight suites as milestone 4) passed 123 tests in 5.292s after initial wiring. First dedicated run found a frozen-reference loader type mismatch (fixed by loading the entire frozen module map before the reference kernel) and an overstrict stay-window assertion (a 7ms early window existed, but was already closed before the decision). Repaired tests passed 17 checks in 3.033s. Additional accounting/expiry/role/snapshot/contest tests are now in progress.

Historical next action (completed): finish dedicated checks, full 123+new regression run, bounded combined-game/reference/cost/release runner; then report and review-only handoff. New research files appeared independently; do not modify or silently complete their named-player records.

## Verification stage progress

Dedicated suite expanded to 24 tests and the first full run exercised 147 tests. One newly added assertion incorrectly assumed all eligible contests must be the roller defender's; the configured anchor may also be the nearby on-ball defender even with help commitment 0. Narrowed the assertion to require actual roller contests rather than forbid a valid alternative contest. Final code review additionally corrected a genuine timing defect: contact now checks the screener's body position at defender arrival, not just the intended screen location, and unsettled late contact weakens both hold and detour. Added a no-arrival/no-contact/no-foul causal check; illegal-screen fixture now uses an actually arrived but unsettled screener. No unsupported teleport-to-screen benefit remains in this bounded phase.

First bounded runner completed 22 short games, 16 local response controls, all screen/hold/roll/slip/no-screen branches, actual illegal screens and existing creation/pass/receive/shot losses. 8 real-roster OFF comparisons and 12 prior experimental comparisons matched complete frozen-module results; all 42 memory probes released. These preliminary output timings/results will be overwritten by the final corrected run. New research packet validated without modification: 11 source players, 949 unknowns, 9 tiny synthetic sections; no source/operational pilot completion or scale adapter was applied.

Historical next action (completed): final 123+25 suite, then run the bounded experiment sequentially for clean cost samples, finish report/checkpoint with actual results and stop for review. No new app/day/economic parity claim.


Finalization note: after the date-context update, reread this checkpoint and the current screen/navigation assignment; active task explicitly reconfirmed. Final metadata now distinguishes derived windows/routes from historical supplied controls, and missing P02 is rejected before a roller contest can first execute. Verification remains under the assigned November 13 filenames.


## Final bounded stage completed — STOP for coordinator review

The active screen/navigation assignment is complete within its requested backend scope; no activation/whole-model acceptance is implied. Final report: `docs/SCREEN_NAVIGATION_EXPERIMENT_2026_11_13.md`. Final evidence: `output/screen-navigation-2026-11-13/verified/`.

Exact final test command: `PYTHONPATH=src:tests:.:scripts .venv/bin/python -m unittest test_screen_navigation test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research -q` — **148 tests passed in 22.353s** (25 dedicated + all 123 baseline). Final log: `verified/tests.txt`. All initial failures were resolved; source correction uses actual body arrival for contact, and unavailable/missing-span/forged participant projections are rejected before gameplay. No pending test failure.

Exact final runner: `PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_screen_navigation_experiment.py --output output/screen-navigation-2026-11-13/verified` — exit 0, run sequentially after regression tests. **22 short combined games**, seeds 17/29, 16 regulation possessions per side (hold/29 and unsettled-screen/29 each add one ten-possession overtime). 16 local single-input responses. Sampled 309 rolls, 287 slips, 84 holds, 670 no-screen continuations/uncalled actions, all F03/F04/F06/finish/reset choices, and **14 actual illegal-screen losses**. Near-help 8/4 timely events versus commitment-zero 0/0; near-recovery selects 7/3 roller-defender contests. All ledger/box assertions passed. Late catch expiry is verified by dedicated action tests, not falsely claimed as a naturally sampled game event.

**8 complete ordinary real-roster OFF comparisons + 12 complete prior interior/coupled/creation comparisons are exact**, using authenticated frozen creation/offense/defense/geometry modules and the frozen kernel. Dedicated tests add 16 synthetic ordinary/prior comparisons. No comparison shares the changed resolver with its reference. Screen OFF revisions remain identical.

Bounded cost stage complete: 5 warm samples/path, game cost includes validation/planning/reports/accounting; JSON cost measured separately. Final screen median **28.569ms** (28.128–30.054ms), full JSON **10.752ms**, core JSON **0.101ms**, **497,010 / 4,977 bytes**. Ordinary path uses its own full-game budget; all experimental timing fixtures use 16 regulation possessions. No kernel-only/server-performance claim. Six fresh-fixture memory calls release all **42** probed roots before diagnostic GC. Peak traced 1,981,217 bytes; current before/after diagnostic GC 88,473/9,577 bytes. No production GC/cache change.

Research preserved unchanged: source packet SHA256 `4e49eb36104bbbdfa8f8fab2d6c8f6dd8cbcb32b11723338e3696c0f67cf842d`, 11 source players/all 94 IDs, 949 unknowns, 9 tiny scenario sections. Source/operational pilot values are not silently filled, mapped or activated. Synthetic fixtures are complete only for tested consumers. Independent research checkpoint changes are identified separately in the source manifest, not overwritten.

Owned source changes: existing `src/nba_gm_data/creation_passing.py`, `src/nba_gm_data/interior_game.py`; new `src/nba_gm_data/screen_navigation.py`, `experiments/screen_navigation/fixtures.py`, `tests/test_screen_navigation.py`, `scripts/run_screen_navigation_experiment.py`; this checkpoint/report and bounded outputs. `sim.py`, offense/defense/geometry source modules, historical milestone artifacts, approved architecture, coordinator status, UI, source packets, live ratings and saves remain unchanged by this backend task. Final source/handoff hashes document ownership.

Retained limitations: supplied call/initial geometry, stay/show policy, route endpoint, touch/rebound/clock support, separate configured helper/roller-defender responsibility; exploratory response coefficients; no pop/off-ball routes/re-screens/switch/drop/coaching/rotation engine, full illegal/nonshooting-foul rule administration, or complete approved capability catalogue. F07 stays disabled. No app/calendar/daily-bulk/reload/live economic parity or calibrated named-player/league forecast is claimed. Experiment default OFF.

Next action: coordinator review only. A later user assignment may supersede this STOP; do not infer a different task from historical chat titles or backlog reports.
