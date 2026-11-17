# Mixed-possession pop validation

Milestone 11, November 16, 2026. Complete; stop for coordinator review. **273 tests pass: all 257 accepted tests plus 16 focused regressions.** Normal gameplay remains OFF. No outcome coefficients or inherited evidence-backed grades were changed.

The ten failed pops in milestone10 reduce to five attempt domains replayed under two input versions. Their unfavorable outcome is reproducible and compatible with the model's conditional failure probabilities. Larger mixed-possession samples produce natural catches, shots and scores without forcing successes. The only runtime correction is an exact reported-measurement protocol alias needed to compile Towns and Holmgren; it does not convert units again or change source values. Absolute pass-loss rates and several important inputs remain uncalibrated.

## References and original failure diagnosis

[Reference](../output/mixed-pop-validation-2026-11-16/reference/) freezes eleven accepted milestone10 runtime modules, 237 initial source/test/experiment/document hashes, prior input layers and the eight original kernel results. The [approved map](PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md), [milestone10 review](PICK_AND_POP_REVIEW_2026_11_15.md) and pinned `screen_pop_research_v1_2026_11_15` packet govern this work. No research document, approved catalogue, coordinator tracker or production data was edited.

All eight original serialized results and all ten selected action records reproduce exactly. JSON comparisons normalize tuples/lists, preserving every serialized value. Original-control and final-research runs share the same attempt RNG streams: **five distinct domains**, each repeated with a different input layer. There are four inaccurate deliveries and one failed catch per layer, rather than ten independent failures.

| Original-control attempt | Delivery error / allowed radius | Result |
|---|---:|---|
| seed17, replay, possession3 |1.054m / .593m|inaccurate delivery|
| seed17, sandbox, possession7 |1.252m / .593m|inaccurate delivery|
| seed17, sandbox, possession23 |.785m / .593m|inaccurate delivery|
| seed29, replay, possession8 |.805m / .595m|inaccurate delivery|
| seed29, replay, possession10 |.175m / .587m|accurate placement, failed receiving gate|

The final-research versions have slightly different windows/error scales but the same uniform draws and outcomes. The [full trace](../output/mixed-pop-validation-2026-11-16/verified/original-failure-trace.json) includes intent/read/choice, wait, drive exit/target, launch/flight, receiving interval, error/quality, catch probability, closeout stage and clock. Unreached stages are explicitly identified; a failed pass does not receive a fictional shot.

For the five fixed original selected states, summed projected counts are1.833 inaccurate deliveries,1.091 failed catches,.028 waiting losses and2.049 shot-stage completions. Holding those states/exposures fixed and independently resampling future outcomes gives a **.0717 probability of no shot-stage completion**; the final-research states give .0601. These are descriptive fixed-state calculations, not a whole-game significance test: selection, overtime exposure and the two paired input versions matter. Expected made field goals are only .695/.729 across those five states. No completion and no made basket are different claims.

Ten conditional resampling checks evaluate the five original states at seeds17/29, 2,048 trials each: **20,480 resolutions using common random numbers across states**. Every branch/point check passes the existing Monte Carlo and quadrature tolerances. Original-state projected EP is .4203–.4298; sampled means are .4131–.4395. [Resampling](../output/mixed-pop-validation-2026-11-16/verified/original-selected-state-resampling.json). These checks do not establish real NBA calibration.

### What the failures mean in this model

Delivery error is an exponential distance in metres; a derived opening sets the allowable radius in metres. Flight, minimum catch delay, error-related catch delay, window limits and release use seconds in one frame. Wait is charged once. Actual receiver/coverage movement continues, and the accepted projector uses the same selected-action resolution. No unit/frame/interception or compounded-probability implementation defect was demonstrated in these attempts.

An error outside the radius is currently a **hard turnover**, with optional steal attribution. It is not a recoverable inaccurate pass, loose ball or reset. Whole-action clock expiry takes precedence when applicable. Inside the radius, quality conditions a separate S14 receiving gate and preparation delay. Those are conditional stages, not independent marginal probabilities that can be added. They can nevertheless produce severe combined losses in this provisional model. The diagnostic `completed_pass` flag is set when a delivery/shot plan is prepared; it is **not proof the later catch gate succeeded**. This audit uses actual event outcomes and catch draws, not that flag.

The hard-turnover policy and uncalibrated error/window/receiving maps may overstate real losses. Matched placement, receiving and recoverable-pass observations are needed to establish that. Ten failed selections do not identify a replacement coefficient or justify raising a player's grade. No cosmetic success-rate adjustment or new recovery action was added.

## Four-actor evidence and the narrow adapter correction

The initial comparison uses the finalized milestone10 source packet, SHA256 `161b9d9e0761699e9f2358a0a020494b62aca0580639926ae40c42ad86ba7ee2`. Turner, Towns, Holmgren and Jokić retain **all94 source fields and all18 passing dimensions**, including supported but unused records. Only actual consumer unknowns are completed. All four use offense, interaction and pop-screener projections, with one shared immutable view per actor. This does not certify complete defense, post or workload roles.

| Actor | Supported / controls in actual50-cell envelope | Important retained source distinctions |
|---|---:|---|
| Turner |6 /44|S01; historical-continuity S26/S28; FT proxy and reported size|
| Towns |4 /46|S01/S09 and reported size; receiving/route/read remain controls initially|
| Holmgren |4 /46|S01/S08; slow preparation remains separate from open execution|
| Jokić |13 /37|receiving, screen/read, touch and F04 support; initial S01/S26 remain controls|

Actual getter tracing matches the declared50-cell union exactly: 200 required cells total,27 source-supported and173 controls. The synthetic nonspacing reference is a separate fully labeled artificial profile, with S01=20 and willingness=.1, not a named player's weak or missing-role grade. Unused unknowns remain unknown; this is not a 94-field completion exercise. [Input layers/control ledger](../output/mixed-pop-validation-2026-11-16/verified/input-layers-and-control-ledger.json), [actual compiler audit](../output/mixed-pop-validation-2026-11-16/verified/actual-compiler-dependencies.json).

Controls include common unknown skills, motion(3m/s²,6m/s,2.5m/s lateral), hypothetical H1 reach, jump/capacity and explicit tactical distributions. H1 uses stored P01/P02 centimetres to construct an uncertain P03 control; it is not a measurement or an additional size bonus. Unknown Towns/Holmgren FT talent uses an explicit .80 probability control. None is relabeled as player evidence.

Before the correction, the accepted runtime rejects Towns/Holmgren's exact reported protocol string at P01. The packet already stores values such as Towns213.36cm and112.490908kg; legacy metric labels include `height_inches`/`weight_lbs`, but the units and conversion notes are explicit. [Pre-correction failures](../output/mixed-pop-validation-2026-11-16/pre-correction-compile-results.json).

`experimental_inputs.py` now accepts that **exact** final packet protocol for the existing height/cm, wingspan/cm and mass/kg aliases. Source records stay byte-for-byte intact; no case-insensitive guessing or second inch/pound conversion occurs. Tests require exact stored values and still reject undeclared protocols/wrong units. All other runtime modules are unchanged, including accepted scalar validation, immutable identity reuse, timing, choice, quadrature and outcome kernels. This adapter defect was separate from the original Turner pass failures.

## Bounded mixed possessions and uncertainty

The prespecified main design has five actor conditions × six coverage/timing/clock contexts. Shared T11 is screen.20/roll.35/slip.10/pop.35, explicitly a tactical opportunity control rather than observed player preference. Each possession starts with supplied Curry involvement, then uses actual imperfect choices, finish/roll/lob/pop/fixed outlet/reset alternatives and accepted offensive-rebound/reset continuations. A pass/shot success is never forced. The experiment's continuation transcription is verified against accepted kernel event streams with identical draws.

Sampling starts at256 possessions per seed17/29 per context. Where eligible pops occur,128/seed increments target40 selected pops, with a768/seed ceiling. Adaptation never depends on makes or a desired named ordering. Structural no-pop contexts stop at the minimum. Final outputs retain per-seed counts, all outcomes, continuations, branch forecasts and nominal Wilson/Monte Carlo intervals. Paired draws across actors/contexts support controlled comparisons; they are not independent extra replications. Intervals describe simulation sampling, not evidence-parameter uncertainty or whole-player value.

The main run completes **30 contexts /26,112 possessions**, followed by16 fixed source/control sensitivities /4,096 and two supplied Jokić passing contexts /512. No context is omitted and no possession hits the20-attempt audit abort. The reference/show results illustrate the denominators:

| Actor | Possessions | Intended pops | Screen reads | Pass eligible | Selected | Accurate deliveries | Shot stage | Made FG | Completion/selected, nominal95% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Turner |1,024|360|256|247|48|34|21|6|43.8% [30.7,57.7]|
| Towns |1,024|360|232|223|44|29|18|3|40.9% [27.7,55.6]|
| Holmgren |1,024|360|232|223|44|29|18|3|40.9% [27.7,55.6]|
| Jokić |768|274|230|222|46|38|29|9|63.0% [48.6,75.5]|
| Synthetic nonspacer |768|274|196|189|43|29|18|2|41.9% [28.4,56.7]|

“Shot stage” includes a shooting foul, block, made FG or missed FG after securing the catch and beating the clock; it is not identical to an FGA. A nonspacer can receive a ball without becoming a good shooter. Different stopping lengths and source/control profiles preclude reading the table as a complete ranking.

Late/stay offers **zero eligible/selected pops for all five conditions**,512 possessions each. Early/show needs real wait/recovery exposure. Under a3s reference clock, Turner has2 shot-stage completions/48 selections, Towns0/46, Holmgren0/46 and Jokić11/45. Other actions and continuations can still score. This is clock/opportunity and preparation behavior, not a requirement to raise a release grade. All selected-pop branch comparisons in the main run lie within the prespecified four-SE/numerical diagnostic bounds. [Complete main results](../output/mixed-pop-validation-2026-11-16/verified/natural-mixed-possession-results.json).

### Controls, source ranges and passing contrasts

The16 fixed sensitivities preserve supported source rows. They vary unknown receiving40/85 for Turner/Towns/Holmgren; sourced Holmgren S08 35/60, Towns S01 82/95 and Turner S26 60/85; coherent common slow/fast motion; and defender closeout50/85. Source endpoints are validated against pinned structured ranges.

- Unknown Turner receiving changes mean selected-pop projected EP .3837→.5062 and shot stages3/13→6/14. Towns .4334→.5732 and Holmgren .3682→.4858 show why hands controls remain consequential. These small samples have wide overlapping intervals.
- Holmgren's sourced release range changes stay-context projected EP .3003→.3222; both samples have2 completions/11 selections and no made pop. Towns' source shooting range changes EP .4835→.5381, with the same4 completions/12 and no makes. Identical small outcomes do not erase the distinct execution/preparation responses.
- Common faster motion changes offense and defense together; it is not a measured athlete-only advantage. Closeout50→85 reduces Holmgren's selected-pop EP .3211→.2960 in the supplied stay context. No narrow source direction is turned into a full-player ranking.

[Sensitivity results](../output/mixed-pop-validation-2026-11-16/verified/source-versus-control-sensitivity.json) retain every override and denominator. No source value was fitted to reverse or suppress a result.

Per-route attribution replays fixed existing256-possession prefixes without changing draws/choices. For Turner reference/show, F03 has17 selections→10 accurate deliveries→6 shot-stage completions; F04 13→8→4; pop14→9→5; fixed F06 outlet101→57→37. These are events across406 action attempts in256 possessions, including continuations, rather than mutually exclusive possession percentages.

Jokić's separate supplied high-post/short-advance context preserves his F04 evidence rather than testing only perimeter shooting. In256 possessions/348 actions, F04 is selected98 times, accurate60, reaches the shot stage41 times and makes27 FG; the fixed outlet is70→48→32. A second supplied geometry gives99→60→41 F04. Target hands, geometry and other completions remain explicit; these scenes do not isolate passer talent or implement post establishment. [Passing contexts](../output/mixed-pop-validation-2026-11-16/verified/supplied-jokic-passing-contrasts.json), [per-route attribution](../output/mixed-pop-validation-2026-11-16/verified/per-route-delivery-catch-outcome-audit.json).

## Separately delivered research comparison

The independent research checkpoint was inspected once after completion, then six final artifacts were frozen under [final-research](../output/mixed-pop-validation-2026-11-16/reference/final-research/). Packet `mixed_pop_input_updates_v1_2026_11_16`, SHA256 `dbabcc349525b440d703e96f24af9ae562633ff904574bc88efd7abb8b060eba`, preserves all376 base records and35 inherited supported records. Nine new low-confidence hypotheses fill old unknowns: Turner S14/S27; Towns S27/S28; Holmgren S14/S26/S28; Jokić S01/S26. Source-known cells become44/376;332 remain unknown. Numeric T11 stays unknown. None is a source correction or evidence from these outcomes.

The separate adapter applies exactly those nine records, reducing required controls173→164. Historical continuity, single-sequence transfer and shared-source limitations remain attached. For example, Towns' defensive “hands” praise is correctly excluded from S14, and positive Holmgren route evidence does not overwrite the inherited preparation limitation. [New layers/attribution](../output/mixed-pop-validation-2026-11-16/verified/separate-final-research-inputs.json), [compile audit](../output/mixed-pop-validation-2026-11-16/verified/separate-final-research-compile-audit.json).

Reference/show is replayed at512 possessions per actor **per leg**, same engine and draws:4,096 additional possessions total. This matches budgets rather than comparing a shorter update run with the longer adaptive baseline.

| Actor | Selected→shot stage, old controls | Selected→shot stage, new evidence | Mean possession points before→after | Paired difference, nominal95% |
|---|---:|---:|---:|---|
| Turner |31→17|31→18|.7324→.7363|+.0039 [-.0038,.0116]|
| Towns |28→14|29→15|.7090→.7207|+.0117 [-.0026,.0260]|
| Holmgren |28→14|31→18|.7109→.7422|+.0313 [.0048,.0577]|
| Jokić |37→24|39→28|.7695→.7813|+.0117 [-.0045,.0279]|

These are effects of independently sourced hypotheses replacing controls in one supplied environment, not measured player improvement or validation of grade precision. Several additions share evidence. Choice/opportunity changes also change the selected-pass population, so completion-rate differences are not pure receiving effects. The final packet was not rerun over every timing/clock/sensitivity context; the original full matrix remains a distinct frozen-input result. Four additional final-source short kernels pass accounting and determinism. [Paired results](../output/mixed-pop-validation-2026-11-16/verified/separate-final-research-paired-results.json), [final-source kernels](../output/mixed-pop-validation-2026-11-16/verified/separate-final-research-kernel-accounting.json).

## Caps, runtime and ownership

The prespecified aggregate cap was60,000 supplied possessions,180,000 event attempts and180s active natural sampling. A zero-counter reporting error interrupted the first run; its log is preserved and3,584 discarded deterministic possessions/6,181 events/3.562s are charged, not hidden. Counters now serialize explicit zeros, with a regression assertion. A final1,536-possession attribution replay observes existing prefixes and is also charged, not counted as independent inference.

Final totals including both replays: **39,936 supplied possessions,61,107 event attempts,39.941s active natural work**. Inference samples total34,816; no cap was raised, no context omitted, no possession truncated. Conditional resampling and short regression/accounting kernels are separately bounded. [Prespecification](../output/mixed-pop-validation-2026-11-16/verified/prespecified-budget-and-contexts.json), [final budget](../output/mixed-pop-validation-2026-11-16/verified/final-aggregate-budget.json).

Same-input old-fixture timings compare authenticated milestone10/current code sequentially, seed17, exactly16 realized possessions/side, one warm-up then seven unprofiled samples/version. Preparation, events, accounting and retained reports are inside the game boundary; compilation, profiling and serialization are outside.

| Fixture | Accepted median ms | Current median ms | Full JSON bytes, unchanged | Serialization ms before→after |
|---|---:|---:|---:|---:|
| native10 |34.085|34.011|633,063|12.883→13.709|
| helper6 |28.755|28.759|560,531|10.853→11.373|
| expanded6 |26.137|25.914|668,998|11.321→11.502|

These small differences are measurement variation, not an optimization claim. Counts, results and payloads are exact. [Samples/profiles](../output/mixed-pop-validation-2026-11-16/verified/legacy-equivalent-budget-costs.json).

A fixed64 supplied-possession audit includes more screen opportunities than the sparse original kernels. Current warm medians are Turner75.236ms, Towns76.916ms, Holmgren73.582ms and Jokić74.808ms, with96–98 actual event attempts. This boundary includes RNG and audit counters, not pure production-engine time. Accepted-code Turner/Jokić are75.767/76.332ms with identical batch digests; a Towns/Holmgren accepted baseline is unavailable because the old compiler rejects their source protocol.

The batches exercise **77–79 interception solves**, versus two in the sparse milestone10 timed pop fixture. Instrumented solver time is1.04–1.13ms inclusive; it is bounded and not the dominant projection cost. Current batches perform1,183–1,195 shot plans and744–760 projected candidate resolutions. Full audit payloads are20,262–21,460 bytes, serializing in about.21–.24ms. Counts distinguish hypothetical plans from actual shots; the short cost prefix selects only two pops and is not used for completion inference. [Fixed-budget workload costs](../output/mixed-pop-validation-2026-11-16/verified/fixed-mixed-possession-costs.json). Diagnostics, candidate diversity and quadrature were retained; no broad optimization was attempted.

Four create/run/release cycles release **56/56 weak roots**. Peak traced allocation26,649,718 bytes; final11,980 bytes includes audit metadata/allocator residue, with no owned input/config graph surviving. Explicit collection is audit-only. [Release evidence](../output/mixed-pop-validation-2026-11-16/verified/ownership-release.json).

## Verification, limitations and handoff

[Final tests](../output/mixed-pop-validation-2026-11-16/verified/tests-final.txt): **273 PASS**. The16 new checks cover original reproduction, duplicate domains, source/94-field preservation, actual compilation/shared ownership, exact aliases/units and rejection, hypothetical reach, protected ranges, hard delivery-loss semantics, accepted event-stream continuation replay, deterministic natural sampling, zero denominators, synthetic identity, release and final evidence integration.

**44 complete accepted result/RNG comparisons** pass across ordinary/prior paths, accepted native/helper/expanded fixtures, both milestone10 pop inputs and applicable mixed Turner/Jokić paths, seeds17/29 and both modes. Frozen classes/compilers include the pop variants and old input types. Old Towns/Holmgren compilation failure is demonstrated rather than bypassed to manufacture parity. All outcome/choice/geometry/timing runtime modules remain hash-identical; scalar validators and identity reuse remain exact. [Accepted-path parity](../output/mixed-pop-validation-2026-11-16/verified/accepted-path-full-result-rng-parity.json).

Sixteen four-actor short kernels pass actual accounting and repeated result/RNG determinism. Three sandbox seed17 cases realize26 possessions/side through overtime; the others16. Four additional final-source kernels are checked separately. [Kernel evidence](../output/mixed-pop-validation-2026-11-16/verified/four-actor-kernel-accounting-rng.json). No whole-season or application speed claim follows.

Full C37 remains missing. It needs perimeter-specific reachable contest geometry, arrival/braking/control and release alignment from S37/S40/S45 and P02/P03/P05–P10 as applicable, integrated once into the same actual/projected shot response. The present primary pressure/arrival curve is partial; perimeter blocks and legal-contest foul detail are not supplied by a second C27 bonus. Future work must avoid counting that existing pressure effect and a new complete contest twice. No C37 implementation is included here.

Other limits remain: uncalibrated pass-error/catch/recoverable-loss maps, hypothetical motion/reach, unknown preparation/range for several actors, partial receiving physics, stationary F01 return, cross-court routes, post establishment/continuation, broader off-ball/coaching/workload and a multi-step future planner. These are mechanism/evidence gaps, not reasons to penalize a missing role or rewrite a supported grade.

Reproduce sequentially with `PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_mixed_pop_validation.py`, then `scripts/run_mixed_pop_research_comparison.py` and `scripts/run_mixed_pop_family_audit.py` using the same prefix. [Summary](../output/mixed-pop-validation-2026-11-16/verified/summary.json), source/integrity/handoff manifests pin inputs, owned changes and outputs. Stop here for coordinator review; no next subsystem or activation is authorized by this delivery.
