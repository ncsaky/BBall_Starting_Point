# Recovery projection cost review — November16,2026

Milestone13 proposes exact candidate-local reuse and conservative search pruning. It reduces representative detailed-recovery batch time by **17–20%**, with identical predictions, decisions, full results, RNG traces and diagnostics in the checked states. **The performance gate remains unmet:** recovery still costs about10.5–10.7× the same hard-window batches. A separately named cheaper projection was about2.9× faster again, but failed the prospective accuracy limits and is **rejected for promotion**. Ordinary gameplay remains OFF.

All320 tests pass (303 baseline +17 new;40.079s). Supported player records, all94 dimensions, outcome coefficients and selected-pass physical rules remain fixed. No C37, new basketball system, production activation, UI/server or season work is included. Independent perimeter research was not consulted or awaited.

## Reference, work boundary and exact changes

The authentic milestone12 reference contains12 frozen runtime modules,255 pre-edit file hashes and16 accepted input/result pins, including all eight accepted short kernel results, source/input audit and full prior cost samples. The new authenticated loader reconstructs the original detailed recovery configuration; it does not substitute a hard-window policy as the recovery baseline. Prior milestone12 artifacts and consumed budgets remain untouched. Coordinator's prior independent303-test pass is context; this delivery runs its own expanded320-test suite.

Baseline reproduction and all timings are sequential, with preparation/config compilation outside the timed boundaries, one warm call and five unprofiled samples per version. Profiling and complete-result JSON serialization are separate. The same three16-possession-per-side kernels and the same seeded Turner/Jokic16 supplied-possession batches preserve the original expensive benchmark. An additional3s-clock batch, twelve prepared boundary predictions and24 full selected-pass resolutions separate prediction from actual resolution. These are bounded fixtures, not app latency or equivalent shots/season throughput.

The baseline profile identifies prediction as the dominant cost: a Turner16-possession batch makes3553 candidate resolver calls,3371 recovery geometry calls and47,064 inner feasibility checks. Repeated immutable decoding is a small share (the accepted snapshot optimizations remain). The proposed changes are:

- Build receiver/assigned-defender nominal positions, directional axes, physical limits, velocity and gather constants once per candidate projection. The basis lives only on a copied private frame. A new time, route, creator, defender or reset constructs a new basis; shared source/config/possession state is not modified.
- Before searching, bound all horizontal ball positions by their swept rectangle. Distance from the receiver to that rectangle is a lower bound on distance to every trajectory point. Grant full horizontal reach, no vertical/takeoff cost and the entire horizon for travel. If even that optimistic case cannot succeed, every original search sample must fail. The rectangle/time bounds are conservatively expanded for roundoff. Survivors use the original search steps, bisections and arithmetic ordering. This prunes proven failures; it does not approximate a catch boundary or grant extra reach.
- Below standing reach, the old vertical fraction is exactly0 and reach multiplier exactly1; use those values directly. Keep the elevated branch unchanged. Reuse the already computed delivery record rather than decode the same radial error twice.
- Memoize identical compact shot-plan requests within one candidate. The key includes player, zone, draws16–19, defending team, anchor-profile identity, immutable arrival/action contexts and outlet flag. Coupled snapshot identity is enforced. No future delivery/catch draws enter the key. Return a fresh outer plan because resolution attaches its selected-contest fields; nested offense/response values are read-only in the resolver/integrator. Actual selected full-detail planning uses its existing path.

There is no global/unbounded cache. Candidate work, summation order, quadrature panels/orders, six-direction prior, clocks, securing gates, reset semantics, physical coefficients and public diagnostic fields are preserved. Logical node/shot-plan-request diagnostic counts therefore stay equal; profiler counts separately expose fewer actual plan constructions. No diagnostic content is removed to claim a speedup.

## Exact performance and remaining cost

| Same workload | Frozen detailed/prior ms | Proposed exact ms | Time reduction | Equal JSON bytes |
|---|---:|---:|---:|---:|
|native10|35.265|35.367|-0.3%|633063|
|helper6|28.039|28.211|-0.6%|560531|
|expanded6|25.541|25.378|0.6%|668998|
|turner_hard|16.480|16.581|-0.6%|1476|
|jokic_hard|18.957|19.349|-2.1%|1531|
|turner_recovery|213.061|174.266|18.2%|38754|
|jokic_recovery|248.820|206.383|17.1%|38748|
|clock3_recovery|165.085|132.914|19.5%|27758|
|boundary12_predictions|95.748|79.288|17.2%|67247|
|selected24_full_resolution|3.149|3.532|-12.2%|171876|

Medians are from five warm samples, not profiler wall time. The unchanged three kernels differ by−0.6% to+0.6%; hard-window batches by about+0.6%/+2.1%. Those small differences are not a speed claim. In the same final timing campaign, detailed recovery versus hard-window overhead changes from12.93×→10.51× (Turner),13.13×→10.67× (Jokic). This does not redefine the original12.86–13.39× milestone12 benchmark; host/session noise differs.

Turner plan constructions fall2775→1833, inner feasibility checks47,064→32,988 and nominal receiving-position calls3371→38. Jokic has3431→2319 plans,52,996→37,254 inner checks and3778→41 nominal-position calls. Full resolver calls remain3553/3991; all original quadrature nodes are still evaluated. The3s-clock batch improves19.5%; the twelve sideline/clock/close-defender predictions improve17.2%.

The separate24 full selected-pass resolutions are **12.2% slower** (3.149→3.532ms per batch, about0.016ms extra per resolution), with identical171,876-byte diagnostics. Eager invariant-basis construction on the cold selected path has a small cost; the measured gain comes from repeated prediction work. This regression is retained and disclosed rather than hidden in the larger possession improvement.

All exact benchmark payload hashes/byte counts match. For Turner/Jokic recovery batches, JSON remains38,754/38,748 bytes and median serialization.665→.673ms/.651→.692ms. Accepted kernel payloads remain0.56–0.67MB. Full timing samples, serialization samples, profiles and counts are in `costs.json`, `detail-costs.json` and adjacent profiles. The first geometry-only attempt achieved~10% and is preserved with its code snapshots/profile/cost artifacts under `verified/attempt1/`.

## Numerical and behavioral verification

Forty-eight complete-result/full-event-RNG comparisons match the authenticated detailed reference exactly: three accepted benchmarks, four actors under hard-window and recovery policies, ordinary behavior, two seeds and both simulation modes. Experimental kernels pass accounting. Separately, all1536 supplied mixed possessions (four actors×show/stay/3s×seed17/29×32×two versions) produce identical full sampler results, including point vectors, choice counts, receipt categories, paid continuations and diagnostics. The twelve paired state summaries are retained; these are exact implementation checks, not new estimates of real basketball rates.

The17 new tests cover2304 explicit geometry cases,144 alternative trajectory-control cases,24 same-state predictions at each of orders4/8, actual selected-pass full diagnostics, new time/position/defender/creator snapshots, repeated receiver transfer/reset state, conservative reach boundaries, plan-key segregation, fresh outer-plan mutation isolation, snapshot ownership, release and future-draw/RNG independence. All comparisons use exact equality, not float tolerances. Existing recovery tests retain one-time securing, clock/accounting and rebound/reset limitations. The complete320-test run repeats deterministic verification normally; no Monte Carlo is used in decisions.

A test initially requested an unavailable F03 under stay coverage. It was corrected to an eligible3s-clock state; the failed log is retained. The parity harness initially called experimental-ledger validation on an ordinary game result, which has no such ledger. The harness now validates experimental results only and resumed already retained comparisons; no runtime/accounting fix was needed. StageB preflight corrected a scalar wrongly treated as a coordinate and excluded the declared ordinary-reset value proxy from branch normalization because that proxy has no branch table; its value/choice errors are still evaluated. No numerical tolerance or candidate was changed in response to results. Progress/error logs remain available.

## Explicit cheaper-projection experiment: reject

The prospective ledger `stage-B-prespecified-criteria.json` predates evaluation. One experiment-only identifier, `coarse_recovery_decision_panel1_v1`, uses one rather than four radial panels, retaining order4, the clean channel, six directional strata and analytic tails. Its scoped harness replaces prediction only. Detailed selected-pass resolution receives the original frame, physical coefficients, geometry, receiving gates and diagnostics. The scope restores the exact predictor on normal or exceptional exit; there is no runtime config switch or promotion.

Acceptance budgets were maximum absolute errors≤.01 expected points,≤.01 per branch,≤.01 effective choice probability and≤.02 choice total variation, with no omitted branch having reference probability≥.005. These are explicit engineering review limits, not empirically calibrated basketball tolerances: .01 expected points corresponds to3 points per300 repeated identical immediate opportunities; .01 probability to one category displacement per100 repeated states. They do not establish real-world validity. The cost gate required≥2.5× speedup over optimized exact and≤4× hard-window. No tolerance relaxation, second coarse candidate or player fitting was permitted.

The48 declared states use Turner/Jokic as development and Towns/Holmgren as held-out actors, each across pop/F03/F04 and reference/receipt-preparation-clock/sideline-translation/close-assigned-defender contexts. Translation moves the relevant ball/receiver/defender/deployment scene together while keeping court/rim fixed; the clock and defender cases alter declared opportunity geometry/time, not grades or response coefficients. All candidates actually offered by each state are compared, plus effective imperfect-choice distributions; the family label identifies the scene, not a restriction on error inspection.

| Coarse tradeoff | Measured | Prospective criterion | Decision |
|---|---:|---:|---|
| Maximum expected-points error |.019573|≤.010|Fail|
| Maximum branch probability error |.033575|≤.010|Fail|
| Maximum effective-choice error |.058500|≤.010|Fail|
| Maximum choice total variation |.058500|≤.020|Fail|
| Omitted material branch instances |6|0|Fail|
| Turner/Jokic speedup over optimized exact |2.86× /2.94×|≥2.5×|Pass|
| Turner/Jokic cost versus hard-window |about3.71× /3.67×|≤4×|Pass|

Thirty-three of48 states fail; both development and held-out groups fail. For example, the held-out Towns clock-boundary scene omits a reference F04 `recovery_defended` mass.033575. Small value changes can also change which action receives the existing bad-choice probability, producing a larger choice-distribution change. Normalized total probability alone is insufficient.

A separately capped whole-mixed audit used256 supplied possessions (four actors×show/stay×two seeds×8×two policies). Seven state pairs have equal point vectors/choice counts; Jokic/show differs by−.0625 points per supplied possession over16 observations per policy and changed choice counts. This small outcome audit does not validate the approximation or quantify league effects. Direct same-draw selected-pass parity and a coarse-scope actual-kernel reproducibility/accounting test pass, establishing that the changed decisions, rather than changed physical response rules, produce divergence.

The combined StageA/StageB natural workload totals1792 supplied possessions,2530 event attempts and16.5613 active seconds, within2048/8192/60 caps. No further boundary natural samples or tuning were used. Projection/timing/functional checks are deterministic separately bounded workloads; repeated warm measurements are not independent inference samples. All supported input/output pins remain unchanged.

## Memory, delivery and recommendation

The candidate memo trades bounded temporary memory for fewer repeated plans. In a symmetric warm, prepared Turner/pop projection boundary, peak traced bytes rise30,838→139,205 (about108KB extra); both versions retain224 traced bytes after four projections with returned results deleted. The initial cold memory measurement included lazy module/class imports; it is retained separately alongside allocation diagnostics, and the warm correction is explicit. This is not a claim of zero process allocation or a proof about indefinitely long runs.

The independent four-cycle fixture/config release check releases all52 tracked roots. Post-cycle traced live bytes79,790→83,895, final84,023, peak26,722,153 are retained in `release.json`; pool construction dominates that broader boundary. No runtime garbage-collection calls or global cache were added. Source/config isolation and private-frame disposal are tested.

The final integrity audit compares255 pre-edit file hashes: only `pass_recovery.py` and its one-line compact-planning hook in `creation_passing.py` change;253 remain identical. All16 accepted input/result pins remain unchanged, including supported source records, approved map/schema/registry and milestone12 evidence. New tests, experiment-only coarse harness, runner, checkpoint, report, frozen modules, raw measurements and owned-code diff are enumerated in `handoff-manifest.json`. The existing host Xcode-license condition prevents `git status`; no license/host changes were attempted. Independent SHA256 verification supplies the file-level check.

Reproduce from the repository root using `PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_recovery_projection_cost.py STAGE`: `baseline`, `costs`, `parity`, `mixed`, `approximation`, `detail_costs`, `local_memory`, `release`, `tests`, then `finalize` after report/checkpoint completion. Baseline precedes edits; authenticated frozen/current comparison remains available. Natural stages are single-use guarded and must not be rerun over consumed budgets. Exact outputs live under `output/recovery-projection-cost-2026-11-16/verified/`; references are separate. No research polling or cross-chat messages occurred.

Recommend reviewing the exact reuse/pruning change on its measured merits. **Reject the coarse experiment for promotion and retain the detailed predictor.** Wider practical performance remains unresolved; this delivery does not claim a sufficient solution to the original13× overhead. A future separately authorized numerical design would need explicit boundary/error control and choice-discontinuity checks, rather than another silent panel reduction. Stop for coordinator review; no automatic next milestone or activation.
