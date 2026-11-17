# Shooting, spacing and finishing versus interior defense — November 13, 2026

**Stage B is implemented and verified, default OFF, using the existing experimental event kernel.** It connects raw shooting, willingness, finishes and varied geometry to defensive opportunities and actual points. This is introductory integrated mechanism work, not final tuning of interior defense, player rankings or league balance. Stage A's historical shooting correction was independently verified first; see `HISTORICAL_SHOOTING_IMPORT_FIX_2026_11_13.md`.

All 94 approved input dimensions, 37 capability definitions and 22 role/output definitions remain intact. No production numeric deployment, normal-game activation, market/contract-policy change, actual rotation change, GUI work, package installation or preview restart occurred.

## Implemented chain

`offense_response.py` compiles immutable validated input snapshots and supplies response functions to **the same** `interior_game.py` possession loop. There is no third scoring engine or fixed-score shooting reconstruction. `InteriorExperiment.offense` must explicitly receive a `CombinedOffense`; its default remains `None`. The prior interior-only experiment and ordinary full production fallback retain their behavior.

| Mechanism | Actual new consumer and boundary |
|---|---|
| Catch, pull-up and movement shooting | S01–S06 select exactly one mode-specific execution skill at the relevant distance. Movement and catch labels do not stack two accuracy talents. These are partial C01–C03 responses. |
| FT | S07 alone supplies C04 conversion. Synthetic technique mapping and research's observed-percent proxy have separate explicit contracts. Release/range never improve FT talent. |
| Preparation and distance | S08 controls preparation time and a controlled primary-contest window; S09 controls loss beyond reference distance. Partial C05 readouts are part of these same curves, not extra global bonuses. |
| Willingness and spatial threat | The shooting part of T01, T02's conditional locations and T03's modes determine attempted-shot mix and credible perimeter points per opportunity. Partial C31 exposes response curves, deployment and preferences separately. Full action recognition/choice remains unimplemented. |
| Available finishes | S10 layup, S11 floater, S12 dunk, S13 aerial coordination, S14 receiving and S15 contact control have distinct local effects. P03/P10 constrain available dunk/lob execution; P08/P09 supply declared capacity controls. These are partial C10–C13 responses. They do not create a drive or pass opportunity. |
| Interior coverage | C27/interior C32 now use shot/defender coordinates, release height, approach angle, dimensional travel, arrival and available reach. C36 summarizes those same deployed responses and adds no bonus. R18 stays partial. |

The kernel sums points from resolved FGs and FTs. Foul/block/miss/reception outcomes determine whether an FGA exists, whether a rebound is available and whether another attack follows an offensive rebound. A failed receive is a turnover, not a fake attempt or rebound. The shared accounting checks continue through overtime. Old shooting/rim/impact values do not contribute on top of new responses: a test sets every legacy trait to 1 and obtains identical complete coupled results.

## Endogenous spacing and varied geometry

Perimeter credibility is expected points under a declared shooting opportunity: ability × willingness × perimeter preference. It is a response readout, not an independently added gravity talent. A controlled opponent assignment identifies whom the anchor is responsible for; the actual pull toward that player's perimeter deployment follows that player's credible threat. The old manually supplied `ArrivalContext.spacing` knob is ignored in coupled mode. Anchors can be pulled away from a rim chance, while remaining anchors can discourage a rim attempt into a genuine willing perimeter outlet with its own reception and shooting response.

Assignment/coaching and primary perimeter defense are still controlled context. This does **not** complete C37, POA, passing or all five-player help choices. Interior changes cannot improve every perimeter shot: C27's conversion/block/foul/avoidance response is zero for the perimeter region. Faster shot preparation interacts with the explicitly supplied primary contest/arrival context instead.

`shot_geometry.py` replaces the narrow single-release-height response in the coupled branch. It combines standing reach and jump with a continuous vertical-access response; wingspan supports horizontal coverage in a coupled geometric envelope rather than another additive vertical bonus. Release heights, finish distances, approach angles and starting defender positions vary. An unreachable ball cannot be blocked; late or remote arrival removes useful coverage. The old scalar reference is retained only under `legacy_scalar_reference`. The coupled report's C27/C32 and C36 refer to actual geometric responses in the opponent attack ledger, including avoided opportunities before redirects. C36 is a labeled small deployed-sample readout, not a calibrated intrinsic grade.

Both offensive and defensive projections of a player must use **one identical authoritative input snapshot**. A discovered fixture inconsistency was corrected and a runtime gate/test now rejects different talents or physical values for one player. Contexts and coefficients may differ by task; the underlying inputs may not. No player estimates were changed to compensate for a surrounding-system limitation.

## Source evidence versus controls

Read the November 13 research packet `ratings-evidence-2026-10-29/OFFENSE_INTERIOR_INTERACTION_INPUTS_2026_11_13.json` and its report. Exact packet hash is recorded in `summary.json`/`verification.json`. All twelve nested schema sections validate. **All 132 scenario/player profiles compile with exact raw-document preservation.** The source section's 352 explicit unknowns remain unknown, with the remaining approved inputs unknown by omission. Incomplete source-only players fail compilation rather than receiving default grades.

The packet's S07 scale is explicitly 100×validated FT conversion, not the generic technique scale. The consumer maps that proxy to probability by dividing by 100; it does not apply the synthetic technique curve. Source FT counts/uncertainty remain attached. Research's two-bin T02 does not identify a rim/midrange split: scenario compilation requires an explicit controlled two-point rim fraction, .65 in these probes. Physical fixture protocols and unvalidated reach hypotheses remain labeled synthetic; no scouting claim becomes an observed physical test.

The 132 research profiles are response/sensitivity probes, **not coupled forecasts for NBA players**. Actual coupled games use ten unnamed synthetic players and no imported historical FGM/FGA. The raw historical cache remains untouched. Research's additional bounded Chicago source check still leaves a team/player inconsistency unresolved; no residual was assigned to a player.

`configuration.json` retains one raw input map, deployments, assignment, exploratory coefficients and support assumptions. Delivery quality, primary perimeter pressure/arrival, finish opportunity mix, assist credit and offensive-rebound rate are explicit controls. Equal minutes supply attribution weights; unknown passing/rebounding talents are not filled with 50. New creation/access, passing delivery, routes/screens, T18 contact choice, full POA/help, rebound technique and physiology remain unfinished. Current availability/minute preparation is reused, but the new attacking curves are healthy-reference responses, not a completed fatigue/injury model.

## Changed opportunities and outcomes

Three controlled attacking profiles use jump-shooting grades 90 or 35 and willingness .9 or .1, holding FT and finish inputs fixed. This is a mechanism contrast, not a grade recommendation. Listed perimeter attempts and scores below are **regulation only**, with 96 possessions per side.

| Attacking team B / seed | B perimeter FGA | Regulation A–B score | Anchor position, metres |
|---|---:|---:|---|
| Strong, willing / 17 | 37 | 118–124 | (2.50, 4.62) |
| Strong, reluctant / 17 | 13 | 118–118 | (0.41, 1.60) |
| Weak, willing / 17 | 37 | 118–98 | (1.62, 3.35) |
| Strong, willing / 29 | 31 | 115–137 | (2.50, 4.62) |
| Strong, reluctant / 29 | 12 | 115–124 | (0.41, 1.60) |
| Weak, willing / 29 | 33 | 115–92 | (1.62, 3.35) |

The reluctant seed-17 case then reaches overtime and finishes 131–132 with 106 possessions; that final score is not compared as equal exposure to a 96-possession case. Willingness is not forced to monotonically increase every final score. In seed 17, strong versus weak willing shooting changes B's made threes 16→8 at the same 37 perimeter attempts, and B's points 124→98. Reluctance leaves the anchor nearer the paint, producing more blocked/redirected opportunities; all subsequent misses, fouls and rebounds remain linked to the ledger. Source game files preserve full probabilities, geometry and event ordering.

Bounded evidence includes eight skill/willingness/controlled-POA game cases, 54 geometry cases, 24 single-input response cases and eight independent ±25% coefficient game cases. Local tests distinguish floater touch, contact layup control and available dunk/lob execution without pretending that finishing skill creates the chance. Release/range, reach/angle and POA/arrival effects depend on context. These checks establish causal reach and accounting, not final response magnitudes, a universal ordering of finish types or whole-model calibration.

## Verification and ownership

**95 focused checks pass:** 22 new coupled-mechanism tests, the prior 56 schema/interior/defense/narrative checks, and 17 Stage A parser/research checks. Eight full default-off real-roster results match the Stage B frozen reference across two exhibition matchups, seeds 17/29 and both existing modes. Four synthetic default-off cases also match. Two exact differentials preserve the prior interior-only event path. Tests cover local skill effects, unsupported units/scales/missing inputs, source preservation, one input snapshot, input/context/coefficient revisions, changed outcomes, accounting, reception failures, C36 non-feedback and isolation.

JSON input reconstruction produces identical results at the actual Python game boundary. There is **no app-action activation**, so no experimental daily/bulk/midway career-reload, user-stop or browser-playback claim is made. Ordinary behavior remains on its exact existing fallback. Full app/calendar/reload/event verification is still required before any live activation.

`output/offense-interior-interaction-2026-11-13/` retains the fresh post-Stage-A reference, default-off comparisons, complete synthetic game ledgers, source/version hashes, response/sensitivity matrices, timing, profile and memory evidence. Source edits in Stage B are limited to the existing experimental defense/game modules and new response/geometry modules; `sim.py`'s normal entry point is unchanged from the prior milestone. The only additional pre-existing-file change is Stage A's parser correction. A conservative Stage A recovery follow-up also excluded 60 ambiguous zero-minute legacy rows and was separately retested. No source cache, canonical player, research output, GUI, approved map, coordinator file, playable save or preview was changed.

## Runtime and memory

Five sequential warm samples of the same short, prepared ten-player fixture, measured separately from attribution/allocation tracing:

| Path | Median / range | JSON preparation median |
|---|---:|---:|
| Prior interior-only experiment | 3.10 ms / 3.06–3.39 | 2.35 ms |
| Coupled experiment | 8.37 ms / 8.02–8.77 | 11.68 ms |
| Ordinary default, experiment disabled | 6.02 ms / 5.94–6.20 | 0.23 ms |

These are local engine observations, not HTTP latency, cold start or an equivalent-outcome production speed comparison. The coupled path implements different behavior and deliberately emits large diagnostic ledgers/raw input reports. Profiling separately identifies attack planning, geometry and report construction/serialization as remaining costs; overlapping cumulative rows are not added. Future live payload scope needs its own measurement.

Six warm same-process calls release all 18 probed result/config/combined-context roots. RSS is approximately 293.30–293.33 MiB in the retained run; traced incremental peak is ~1.11 MiB, with ~36 KiB current before diagnostic GC and ~15 KiB after, including probe bookkeeping. No production GC or global experimental cache was added. This small window does not resolve whole-server RSS behavior or demonstrate long-career stability.

## Reproduction and next boundary

```sh
PYTHONPATH=src:tests:.:scripts .venv/bin/python -m unittest test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research -v
PYTHONPATH=src:. .venv/bin/python scripts/run_offense_interior_interaction.py --output output/offense-interior-recheck
```

The runner uses offline retained evidence and in-memory fixtures. It does not start a server, write a save or retrieve data. Keep the frozen reference under the original output directory; rechecks use a separate output path. Stage A has its own commands/report and remains independently reproducible.

Stop for review at this coherent coupled shooting/spacing-plus-finish chain. Next connect new creation, passing and POA/help/responsibility inputs to the same opportunity/accounting model, then complete consistent display, AI value, contract/negotiation/retention and development consumers. Current live consumers do not read these coupled profiles; the prior arbitrary economic bridge is not a validated new-model conversion. Evaluate those systems jointly before final player/role scales or league calibration. No normal-game activation or long-career study is recommended from these isolated samples.
