# Existing action-choice consistency — milestone 8

Authorized November 14; completed November 15, 2026. The requested finish/pass/reset connection is implemented and verified, **default OFF**. New callers explicitly select `CreationExperiment(choice_policy="downstream_outcomes_v1", help_response_policy="projected_contest_v1")`. Previous experiment defaults, revisions and ordinary gameplay remain unchanged. This is a bounded completion of the existing action set, not NBA calibration, a full possession planner or a new offensive playbook.

All 94 approved inputs and the existing capability/role catalogue are preserved. The final accepted milestone-7 overlay remains pinned at SHA256 `2ea987d06cabd45ce370fd6b35426bab28d8808938f564d7b9579788fa297a63`. No expanded research-cohort packet was consumed or awaited. Synthetic contrasts have per-field control ledgers; they do not rewrite evidence or create player ratings.

## Demonstrated problems and shared correction

Ten accepted modules, 157 initial file hashes, the pinned inputs and milestone-7 reference results were frozen before editing under `output/action-choice-consistency-2026-11-14/reference/`. The old code's estimate could remain unchanged when its actual supported consequence changed:

- With only a dunk selected by the supplied finish mixture, changing synthetic S12 from 10 to 95 left the old finish utility at 1.27045. The corresponding conditional expected first-event points are 1.10960 and 1.847825. A layup preview cannot represent that alternative.
- With the same perimeter pass opportunity, changing its defender's closeout technique from 10 to 95 left the old pass utility at −.07709. Actual-context projected points change .16765→.13356. The former pass estimate used a reference shooting context rather than the receiver's actual recovery/pressure.
- Reset retained utility .40 with both 24 and .7 seconds remaining, even when its own elapsed cost exhausted the clock. The notice-matched audit now retains an explicit selected reset under both clocks; the new proxy is .08208 and 0 in those contexts.

The utilities and point expectations above have different meanings; the defect is the old utility's insensitivity to a changed physical outcome, not a claim that every utility must numerically equal points. See `authenticated-mismatch-audit.json`. A final runner-only refresh aligned the closeout and reset audit rows' observed notices; that component was rerun successfully and recorded in the source manifest. Physical resolution, empirical measurements, coupled comparisons, timing and test sources were unchanged by that refresh.

`prepare_drive_decision` now supplies the observed decision state. `resolve_candidate` and shared delivery/window preparation handle the supported selected action. The deterministic projection calls those same mechanisms with declared integration branches, rather than implementing a second scoring engine. The shared kernel still samples catch, foul, block, conversion, free throws and rebound outcomes only after selection.

| Existing candidate | What is estimated before selection |
|---|---|
| Self finish | The normalized actual layup/contact-layup/floater/dunk mixture, including execution, contact, achievable dunk fallback, each preparation time and actual eligible contest. No self-lob is invented. |
| F03/F04/F06 pass | Placement-error distribution, inaccurate delivery, late/moving receiving windows, clock precedence, quality-dependent catch and preparation, actual defender recovery/pressure, and the resulting receiver shot. F03/F04 use one strongest eligible C27 contest; helper and primary contests are never summed. |
| Shot after a surviving catch/finish | The kernel's same foul/FT, block and conversion probabilities, immediate expected points, point second moment, zero-point probability and reboundable miss probability. FT proxies keep their shared interpretation. |
| Reset | A bounded one-fresh-attempt continuation proxy described below. It is not an unexplained fixed reward. |

Placement error and the existing unresolved approach-angle prior are integrated with fixed four-point Gauss quadrature. Delivery/route/clock boundaries split probability mass before the shot calculation; clock takes precedence over delivery/catch classification exactly as in the kernel. Eight-point integration is an offline convergence check. No runtime Monte Carlo, recursive game, outcome-draw lookup or extra RNG call is used. Current handling loss is resolved before this decision and is not charged again to conditional candidate values.

A decision-local immutable `ContestBasis` reuses already computed geometry across angle nodes; it references the same authoritative profile and adds no global cache or independent talent snapshot. Lightweight projection avoids repeated raw-input/geometry diagnostics; the actual chosen event retains full diagnostics. The full four-action decision is structurally bounded at 16 shared candidate resolutions and 32 shot-plan evaluations, plus bounded numeric clock-boundary work.

Recognition remains a separate gate: unseen options are not projected or selected. T01 willingness affects spatial threat and selection preference, not a fictional conditional catch/shot failure after the receiver has already been selected. T07 reduces downside aversion; zero-point failure receives no positive risk-taking reward. Skill-driven deliberately bad choices remain, alongside stochastic good-choice selection.

One further demonstrated incompatibility was corrected: the historical clipped cubic assigned equal minimum weight to different negative utilities, masking real pass improvements. The new policy uses a normalized exponential choice rule with a **declared one-point utility scale**. It preserves ordering, responds to utility differences and keeps every noticed option possible. This noise scale and the retained downside-aversion coefficient are exploratory, not fitted NBA decision parameters. Earlier completed clipped-rule evidence/source is preserved under `stage-clipped-choice/` for audit.

## Reset and continuation limits

Reset pays the existing approach/decision plus reset time. Its one-step proxy reuses only a currently noticed nonwindowed finish or F06 chance; expired screen/roll opportunities are not carried forward and continuation does not rescreen. It discounts the reference by remaining-time fraction, future handling retention, future notice/access and the chance of avoiding a deliberately bad choice. It becomes zero when another supported completion cannot fit. There is no recursive search or assumed newly discovered opportunity.

The proxy cannot exceed its reference candidate's expected points. Each actual reset consumes positive clock, so repeated resets cannot create value or loop indefinitely. Causal tests cover those bounds and the sampler/clock gates. This is a bounded approximation, not an empirically calibrated expectation of a whole subsequent possession; future geometry, opportunity discovery and continuation decisions can differ from its reused context.

Shot projections expose reboundable miss probability but assign **zero rebound continuation credit**. The actual shared kernel still resolves real offensive rebounds and subsequent clocks/actions. The projection horizon therefore ends at the first resolved shot/failure event; it must not be labeled full possession value. And-ones and unimplemented foul/action families remain outside the existing mechanism.

## Empirical verification and changed behavior

**213 tests pass in 19.719s: all 189 previous tests unchanged plus 24 new tests.** New checks cover finish mixtures, foul/FT value once, recognition/delivery/receiving separation, spatial/coverage responses, clock precedence, receiving-window expiry, bounded reset continuation, handling once, monotonic imperfect choice, future-draw/RNG independence, angular reuse equivalence, revisions/mutation/release and game accounting. The original delayed-catch sampler regression remains unchanged and passes; actual resolution still calls `sample_delivery`.

The final runner checks 36 conditional candidates across 19 varied contexts, with 8192 actual first-event trials each (294,912 trials). It separately uses the same 512 seeded full first-action opportunities per context under old/new engines. Inputs are fixed within each paired engine comparison. Two screen-stay roll/lob candidates are correctly unavailable; their gates were not loosened to fill the matrix.

| Fixed conditional context / action | Projected first-event points | Empirical mean [95% sampling interval], N=8192 |
|---|---:|---:|
| reference / finish | 1.30325 | 1.29724 [1.27679, 1.31769] |
| reference / F06 | 0.50845 | 0.50562 [0.48133, 0.52990] |
| contact_finish / finish | 1.08251 | 1.08167 [1.06077, 1.10256] |
| screen_show / F03 | 0.62752 | 0.62122 [0.60122, 0.64121] |
| tight_roll_window / F03 | 0.15911 | 0.15173 [0.14029, 0.16317] |
| high_receiving / F03 | 0.41544 | 0.39746 [0.38023, 0.41469] |

All declared point/stage checks passed. The largest point-mean discrepancy was .01798 per conditional event; the largest four/eight-point integration difference was .000858. Acceptance uses four sampling standard errors plus the measured convergence difference and a .01-point numerical allowance. Stage checks use four binomial standard errors, finite-count allowance, convergence difference and .003 numerical allowance. These are explicit simultaneous sampling/numerical checks, not confidence bands on player ability. Not every ordinary 95% interval contains its prediction (the high-receiving F03 case is just outside); no universal exactness claim is made for finite quadrature.

| Same seeded context, N=512 per engine | Reset count, accepted → new | Mean first-event points, accepted → new |
|---|---:|---:|
| reference | 404 → 299 | 0.12695 → 0.20117 |
| weak_dunk | 451 → 460 | 0.07812 → 0.04688 |
| high_delivery | 433 → 442 | 0.10938 → 0.07422 |
| screen_show | 62 → 158 | 0.63477 → 0.46289 |
| screen_stay | 338 → 280 | 0.32227 → 0.29492 |
| spacer_high | 408 → 297 | 0.12695 → 0.20312 |
| short_clock | 404 → 271 | 0.00781 → 0.00781 |

These are first-event results, with a reset credited zero at that event; they are not possession-value, win or player-ranking results. Some means increase and others decrease. The new noise rule explores more choices, and reset continuation is omitted from this immediate-event comparison. Better conditional estimates do not establish superior overall offense or a calibrated decision distribution. The full tables retain event counts, recognition/help stages, choice frequencies, sampling intervals and representative records.

Authentic comparisons retain eight ordinary/default-OFF and 24 previous experimental full results, using frozen compilers/configuration classes/functions. In 448 same-draw held-candidate trials, full selected outcomes/plans remain equal: the engine changes the decision aid and selection, rather than silently changing the shot result to match its prediction. Eight current-policy cases preserve full output and RNG streams before/after the retained milestone-6 validation reuse. Eight small kernel cases pass scoring/loss/foul/rebound accounting.

## Runtime, report size and ownership

| Same-budget fixture | Accepted median [range], ms | New median [range], ms | Full JSON serialization, accepted → new, ms |
|---|---:|---:|---:|
| Native 10 actors | 20.674 [20.133–20.884] | 40.276 [39.400–40.914] | 10.600 → 14.034 |
| Interpreted 6 actors + separate helper | 21.334 [20.977–21.953] | 31.123 [30.437–31.558] | 9.013 → 11.204 |

This is a **material latency increase** in the two measured fixtures, not a speedup. Each uses the same frozen inputs, seed 17, 16 regulation possessions per side; both versions actually realized 16, while action counts may differ intentionally. Five warm samples exclude serialization. This does not establish whole-app/season performance. No further performance campaign or diagnostic removal was performed.

| Instrumented partition, ms | Native accepted | Native new | Helper accepted | Helper new |
|---|---:|---:|---:|---:|
| Preparation/validation + required spatial math | 11.008 | 11.120 | 5.303 | 5.167 |
| Known spatial/reference diagnostics | 2.922 | 2.925 | 2.084 | 2.101 |
| Event work + projection + mandatory ledger | 15.046 | 61.392 | 19.464 | 44.899 |
| Accounting | 0.434 | 0.456 | 0.535 | 0.459 |
| Mixed boundary/final report | 3.230 | 3.248 | 1.839 | 1.732 |
| Instrumented total | 32.641 | 79.141 | 29.225 | 54.358 |

Native raw action calls change 47→51 and helper calls 85→72; the event counts are not held artificially equal. The new native fixture has 49 projected decisions/125 total candidate entries, with at most 12 candidate resolutions / 20 shot plans per decision observed; helper has 66 decisions/127 entries, observed maxima 8/8. Structural tests cover the larger 16/32 all-four-action bound. Full report sizes change 500,396→633,063 and 438,399→560,531 bytes; small core sizes change 4,977→4,976 and 3,514→3,513. Core values can intentionally differ; equal-size or parity claims are not made for the new decisions.

Instrumentation isolates preparation/validation plus required spatial math, known spatial/reference diagnostics, event work including projection and mandatory ledgers, accounting, and a labeled mixed residual. Nested resolver/screen timings are readouts, not extra additive partitions. The projection/report construction inside event work is not falsely called pure basketball. Native validation compiles remain 10/10 and helper compiles 3/3; screen validation reuse is unchanged.

All 24 probed roots released across four fresh fixture/configuration/kernel calls before the final diagnostic GC. Peak traced allocation was 2.291MB; current allocation was 60,496 bytes before diagnostic GC and 6,408 after. The pilot/source packet was prebuilt, so these figures are not setup-inclusive or whole-app stability evidence. No production GC or global cache was added.

## Reproduction and review boundary

```sh
PYTHONPATH=src:tests:.:scripts .venv/bin/python -m unittest test_action_choice_consistency test_pilot_response_calibration test_experimental_input_pilot test_screen_navigation test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research -q
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_action_choice_consistency.py --output output/action-choice-consistency-2026-11-14/verified
```

Use a separate output directory to preserve the retained run. Outputs include authenticated mismatch/parity records, conditional point and typed-stage checks, paired before/after choices, held-candidate equality, validation-reuse RNG digests, accounting results, timing/pstats/report counts and release/source manifests. The final handoff manifest also covers the report/checkpoint and documents the small notice-matched audit refresh.

Remaining calibration questions are the one-point choice-noise scale, downside/tendency utility, reset's reused opportunity/clock discount, future rebound value and absolute response/input uncertainty. Those limits are explicit approximations requested by this bounded action task, not a claim that the full model is calibrated. No source input catalogue, original evidence, new cohort, approved architecture, coordinator status, simulator/game kernel or production setting was edited. No UI/server, live activation, long-season, economics/development work or new basketball subsystem was added. **Complete; stop for coordinator review.**
