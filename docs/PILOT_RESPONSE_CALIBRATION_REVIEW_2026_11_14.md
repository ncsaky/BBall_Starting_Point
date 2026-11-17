# Pilot response plausibility and influential inputs — November 14, 2026

Milestone 7 is complete for coordinator review, **default OFF**. The same named action probes were repeated with authenticated old code and separately pinned proposed inputs. Two demonstrated response problems were corrected in an explicit experimental policy: a binary help bonus used for action choice, and inconsistent arrival/position/bearing at the helper route endpoint. Containment and the physical receiving/clock deadlines were retained. These results do not establish complete player ratings, NBA forecasts or league calibration.

The new policy is `CreationExperiment(help_response_policy="projected_contest_v1")`. Existing callers default to `legacy_timely_v1`, with their previous revisions and results intact. The new runner opts into the corrected policy explicitly. This preserves the reviewed baseline for comparison; neither variant activates normal gameplay. All 94 approved inputs, 37 capabilities and 22 roles remain intact, and shared input interpretation is unchanged.

## Reproduction and causal findings

Ten milestone-6 modules and 151 initial file hashes were frozen under `output/pilot-response-calibration-2026-11-14/reference/`. Original scenario/summary/source artifacts were copied separately. **All 47 complete serialized milestone-6 probe records reproduce exactly** under the authenticated old engine and old inputs. Full reference comparisons use frozen compilers, configuration classes and game kernel. A reference-screen class mismatch found while constructing the harness was corrected by building frozen configurations; validation was retained and a regression test covers the harness.

The final matrix contains four independent quadrants: old engine/old inputs, corrected policy/old inputs, old engine/proposed inputs and corrected policy/proposed inputs. Each repeats the same 47 scenarios, plus 144 arrival-boundary rows, 72 path-endpoint rows, 14 downstream contexts and nine containment contexts. The contexts cover near/early, marginal, far/late, unavailable and declined help, weak/strong spacing, weak/strong finishing, balanced shooting/pass alternatives, and stay/show screen coverage. The counterfactual three-versus-three fixtures have distinct helper and roller defenders and valid assignments. They are not live NBA lineups.

**The help choice cliff was real.** Across White/Castle and .9/1.1/1.3-second synthetic approaches, moving the actual helper arrival from one microsecond before to one microsecond after the decision changed the old finish choice score by **.675**. Its selected-shot conversion reduction changed by less than .0000002. The old rule subtracted .55 from finish value and changed danger from .15 to .65 solely because `help.timely` flipped. A discrete arrival label is legitimate; an unrelated large instantaneous scoring penalty was not supported by the downstream contest.

The corrected policy previews the existing C27 layup candidate at the actual position and residual arrival. If its base conversion is `p`, C27 reduction `r` and block probability `b`, the decision uses `(1-b) × clamp(p-r)` and the resulting extra failure probability. The existing .15 baseline danger remains; the extra contest failure replaces the binary .50 danger increment. No new smoothing coefficient or random noise was fitted. The actual selected shot still applies defense once downstream. The preview is a declared layup proxy: the later finish mix stays explicit, and shooting-foul/rebound value is not calibrated by this decision score.

Across the final matched microsecond sweeps, the largest corrected choice-score difference is **0.000000617**, while the timely label still flips. Helpers arriving after the decision can partially contest during shot preparation; clearly late or unavailable helpers have no such influence. Zero vertical access supplies no contest bonus simply because a helper is timely. Recognition, attention, commitment, physical movement, preparation and contest execution remain separate ingredients.

**The route endpoint also had a real artifact.** At exact position coincidence, `atan2(0,0)` discarded the route bearing. In the retained side/back approach reproduction, a two-micrometre position change altered conversion reduction approximately .041906↔.014667. Separately, arrival already included the S39 positioning-route surcharge while the used point followed the shorter direct path. This could put a helper at the body before its own reported arrival.

The corrected policy uses the same effective route length, `direct distance + .6 × (1-S39)`, for arrival and position progress. That surcharge is not added a second time to arrival. `HelpShotContext` carries the already known immutable route origin to C27, retaining the approach bearing when the point reaches the endpoint. New responses identify `+helper_route_bearing_v1`; legacy context shapes/calls keep their old output. Both direct and positioning-adjusted endpoint centers are tested under both engines at identical coordinates. The largest corrected score difference across those micro-position pairs is **0.000000546**. This is a bounded route projection, not a new motion/orientation subsystem.

The completed first choice-only comparison is preserved under `stage-choice-only/`; its source/hash and the endpoint reproduction remain under `audit/`. Actual selected-shot contests intentionally differ under the final new policy where the old bearing collapsed or its used position disagreed with arrival. We do not claim experimental old/new outcome parity there.

**Containment did not need smoothing.** Its beat probability already follows a smooth logistic response to recovery minus clearance. The old Castle/Luka reference advantage remains 4.92 percentage points, conditional on retaining the ball. The prior opposed-mobility/source-range reversal remains possible; the new help policy does not change containment, pressure or handling-loss formulas. The nine additional matched-lateral/separation contexts trace actual downstream actions as well as access probabilities. A sampled beat outcome is discrete; its probability is continuous. No ratings or movement controls were tuned to preserve a named ordering.

Screen navigation/receiving-window expiration, shot-clock expiration, recognition draws and commitment draws retain their stated discrete event meanings. Their existence alone was not treated as a defect. Prior screen/navigation reversals under overlapping grades and uncertain movement remain assumption-sensitive conditional results.

## Actual choices and contests

Each downstream context samples 512 complete first actions per helper with paired seeds. The runner retains notices, commitment, beat/loss stages, chosen actions, delivery failures, primary arrival, selected C27 contests and shot-conditional means/denominators. Fixed conditional choice readouts supplement sparse realized beat events; they force the declared access/read draws and commitment when eligible, so they are not estimates of how frequently that stratum occurs.

| Old inputs, context | White finish choices, old → corrected /512 | Castle finish choices, old → corrected /512 | Conditional good-choice finish probability, White old → corrected |
|---|---:|---:|---:|
| Balanced near helper, weak finish/strong shooter | 32 → 42 | 35 → 42 | .1203 → .9019 |
| Mixed 1.25s deadline, same scoring alternatives | 23 → 28 | 28 → 28 | .1253 → .9085 |
| Show-and-recover screen context | 82 → 107 | 92 → 108 | Screen legality/route precedes this forced readout |
| Far late helper | 61 → 61 | 61 → 61 | .9968 → .9968 |
| Unavailable helper | 24 → 24 | 24 → 24 | .9968 → .9968 |

The balanced-near White finish rates have Wilson intervals .0446–.0869 before and .0613–.1090 after; those sampling intervals overlap. The deterministic boundary reproduction identifies the formula defect more directly than this small unconditional sample. In the mixed deadline context, the old forced Castle finish probability is .9449 versus White .1253; the corrected values are .9106/.9085. This removes a particular label-driven disparity; it is not a general White/Castle effectiveness conclusion.

Help recognition and timely counts remain unchanged by the policy. Weak/strong shooting and appetite alter the actual helper starting position through the existing spatial-threat pipeline; when starting geometry is held fixed, better shooting changes the pass alternative without awarding extra help coverage. Conditional mean contests can change because selected actions change, so they are not interpreted as isolated defender skill effects.

The new role fixtures require three additional C27 completions per named helper: White S36/S45/T16, Castle S36/S37/T16. These are logged synthetic role controls, not new researched abilities. Supported records and the original unknowns stay preserved. Separate common S36/S37 controls of 50/90 leave balanced-near forced finish probabilities approximately .925/.893 for White and .922/.882 for Castle. This uncertainty is material; no complete help-defense ranking is inferred.

## Pinned evidence and four-way attribution

Research's completed `PILOT_TARGETED_INPUT_UPDATES_2026_11_14` overlay was inspected only for shape while in progress, then consumed **after** its checkpoint/validation marked delivery complete. The final JSON SHA256 is `2ea987d06cabd45ce370fd6b35426bab28d8808938f564d7b9579788fa297a63`; the local frozen copy and pin are in `reference/`. Its expected old effective-layer hash is `831601175343c8253b3e292511b98c8108478387b114f2feb5b1752877d23b87`.

Strict backend application accepts twelve declared records, skips already identical proposals and rejects conflicting priors, changed source/interpretation, undeclared section changes or an absent/wrong hash. It preserves all 846 original records for the nine actors and all passing pairs. Eight proposals are new/revised, including six formerly generic controls; four earlier proposals are inherited unchanged. All are uncertain estimates, not new observed current talents. The original 241-of-319 source-unknown completion fact remains visible; research proposals do not rewrite source status.

| Reference conditional comparison | Old engine / old inputs | Corrected / old inputs | Old engine / proposed inputs | Corrected / proposed inputs |
|---|---:|---:|---:|---:|
| F03 caught, Luka / Harper out of 4096 | 1736 / 1045 | 1736 / 1045 | 1736 / 1213 | 1736 / 1213 |
| F04 caught, Luka / Harper out of 4096 | 1913 / 1127 | 1913 / 1127 | 1913 / 1446 | 1913 / 1446 |
| Handling losses, Luka / Harper out of 4096 | 319 / 124 | 319 / 124 | 165 / 124 | 165 / 124 |
| Zubac minus Gobert called-roll delay | +77.27ms | +77.27ms | +7.25ms | +7.25ms |

These fixed available-window pass/security/screen measurements do not use the changed help decision. Their improvements are **input-only**, not credit for an engine fix. The original six-actor coupled pilot also has no configured helper, so it cannot validate helper behavior; the added matched contexts explicitly fill that gap. The proposed overlay does not numerically revise White/Castle help inputs, and those matched helper comparisons have the same behavioral results under old/proposed inputs for a given policy.

Proposed Harper F03 notice/conditional-delivery gaps shrink from .2375/.1144 to .1710/.0922; F04 gaps shrink from .2423/.1330 to .1473/.0631. Source/prior uncertainty still matters. A coupled source-overlap F03 case (Luka R88/E85, Harper R85/E86) retains a +.0285 notice gap but reverses conditional delivery to **−.00675**. Its paired catch difference is +.00879 (conditional sampling interval .00479–.01278). Thus the earlier relatively stable F03 delivery direction does not survive this expanded evidence envelope. F04 overlapping alternatives yield notice/delivery gaps −.0095/−.05116 and a paired catch difference −.03931 (conditional sampling interval −.04526–−.03335). Neither is evidence of actual Harper superiority.

Luka's proposed S17 reference84 changes the imposed-pressure loss probability from .07884 to .040384, versus Harper .030264. Luka's proposed76–92 alternatives reverse the lower-loss contrast at the high end; no security rank follows. Gobert's inherited S27 correction accounts for the large screen-gap reduction, while the new S28 estimate changes follow-up behavior rather than being called a second screen-contact bonus. Coherent Gobert S27/S28 range alternatives give Zubac-minus-Gobert delays approximately +40.00 to −24.52ms. Screen ordering remains unresolved.

Typed delivery/receiving attribution isolates creator-only and receiver-only changes. In the separate named-receiver F03 probe, with its own fixed seed, Harper→Zubac secured catches progress from 1004 (old) to 1152 (creator-only), 1086 (receiver-only) and 1241 (both), out of 4096; the exact retained table should be used for all pair/family counts. Notice, inaccurate delivery, failed catch and catch are distinct stages. Receiving proposals are not converted into better placement or finishing. No current measured loss/catch denominator is invented.

## Verification, bounded costs and review boundary

**189 tests passed in 14.807s: all 168 previous tests unchanged plus 21 new causal/overlay tests.** Eight ordinary default-OFF and sixteen previous experimental full results match authenticated frozen modules exactly, including frozen compilers. Eight corrected-policy cases preserve full output and RNG streams before/after the retained preparation-local validation reuse. Eight small counterfactual kernel calls pass accounting checks. The new policy's intentional choice/position/bearing differences are reported above, not hidden in a parity assertion.

```sh
PYTHONPATH=src:tests:.:scripts .venv/bin/python -m unittest test_pilot_response_calibration test_experimental_input_pilot test_screen_navigation test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research -q
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_pilot_response_calibration.py --output output/pilot-response-calibration-2026-11-14/verified --overlay output/pilot-response-calibration-2026-11-14/reference/targeted-input-overlay.json --overlay-sha256 2ea987d06cabd45ce370fd6b35426bab28d8808938f564d7b9579788fa297a63
```

Use another output directory to preserve the delivered run. Without an explicitly pinned overlay the runner reports evidence pending and still supports the old-input engine comparison; it never hot-loads the research directory.

| Same-budget fixture, five warm samples | Old engine median [range], ms | Corrected policy median [range], ms | Full JSON serialization old → corrected, ms |
|---|---:|---:|---:|
| Native 10-actor screen | 19.755 [19.389–26.755] | 20.475 [20.179–21.170] | 10.949 → 10.479 |
| Interpreted 6-actor separate helper | 20.001 [19.810–20.477] | 20.498 [19.621–21.724] | 8.966 → 8.594 |

Both before/after fixtures use seed 17 and 16 regulation possessions per side; all samples also realized 16. The observed medians increase by .721ms and .497ms, respectively, with overlapping sample ranges. This is bounded additional projection/report work, not a claimed speedup or a whole-app bound. The native and interpreted fixtures are separate contexts, so their difference is not interpretation-only overhead.

| Instrumented partition, ms | Native old | Native corrected | Helper old | Helper corrected |
|---|---:|---:|---:|---:|
| Preparation/validation + required spatial math | 10.179 | 10.534 | 5.212 | 5.376 |
| Known diagnostics | 2.658 | 2.709 | 1.994 | 1.980 |
| Event work + mandatory ledgers | 14.131 | 14.370 | 18.383 | 20.103 |
| Accounting | 0.431 | 0.430 | 0.485 | 0.546 |
| Mixed boundary/final report | 3.119 | 3.289 | 1.672 | 1.839 |
| Instrumented total | 30.519 | 31.332 | 27.747 | 29.845 |

The partition follows the earlier bounded attribution: known spatial diagnostics exclude required credibility calculations, and reference reports are isolated. Event ledgers and a labeled mixed residual remain; no pure basketball-kernel claim is made. Nested action/screen readouts are not added again. Inclusive resolve-drive means are .270/.273ms for 47 native calls and .190/.208ms for 85 helper-fixture calls. Validation calls remain 10/10 and 3/3. Full payload sizes change 497,010→500,396 and 433,576→438,399 bytes; core sizes remain 4,977 and 3,514. New diagnostic context is retained. Raw pstats/JSON measurements are delivered; no further optimization was attempted.

All 28 probed roots released across four fresh corrected-policy fixture/configuration/kernel calls before diagnostic GC. Peak traced allocation was 2.322MB; current allocation was 68,584 bytes before the final diagnostic GC and 5,644 after. This excludes rebuilding the entire nine-player source/completion audit, so it must not be compared as a memory improvement against milestone 6's larger setup-inclusive probe. No production GC/cache was added; whole-app/long-career stability remains outside this bounded check.

Remaining evidence needs are current responsibility/movement contexts for help, family-specific available-read/placement/catch tags, legal contact/follow-up samples, and credible helper contest inputs. The new choice preview remains a layup proxy and omits foul/rebound value; its absolute action weights and the current C27/physical response coefficients are not NBA-calibrated. The complete action set, live lineup assignment policies and full spatial/role effectiveness remain beyond this pass.

Only minimal experimental backend modules, new tests/experiment runner, this checkpoint/report and retained outputs were changed. Source packets, shared interpretation, the validation-reuse implementation, approved architecture, coordinator status, simulator/game kernel and production settings were preserved. No app activation, GUI/server work, season study, economics/development tuning or new basketball subsystem was added. **Stop for coordinator review.**
