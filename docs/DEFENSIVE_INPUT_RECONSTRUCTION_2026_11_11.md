# Defensive input reconstruction — November 11, 2026

**Current-task checkpoint: working league-wide experiment and verification complete; no production installation.** This supersedes the three-name-patch direction. Roles remain experimental. No production source, canonical data, GUI, coach, rotation, prospect/growth algorithm, save or preview was edited. Do not resume settlement tasks. All 75 frozen pre-existing files are preserved. The installed backend remains **http://127.0.0.1:8798/**; none of these experiments runs there.

**Decision: no complete five-trait candidate is accepted.** Fixed headroom solves clipping but not evidential validity. The evidence-separating alternative is a useful next construction hypothesis, but it cannot identify containment, navigation and help execution from the available inputs, and its rim proxy fails a small-sample control. This is a measured blocker, not a request for a paid subscription or a generic audit handoff.

## What works and where to inspect it

The executable experiment covers **all 691 current players / 3,455 defensive trait records**, including the 526 original source players and 165 later roster rows. It replays the trait pipeline only, not market construction or full-universe simulation. **Every current value, component object, source ID list, source kind and confidence matches canonical exactly.** Seventeen focused tests pass.

| Artifact / implementation | Contents |
|---|---|
| `experiments/defensive_inputs/model.py` | Uncapped equation reconstruction, frozen-reference lookup, fixed tail mapping, evidence-channel alternative and explicit override/unknown handling |
| `scripts/run_defensive_input_reconstruction.py` | Private pipeline replay, real pre-clamp observation, league counterfactuals and distribution/dependency/rank/stability reports |
| `output/defensive-input-reconstruction-2026-11-11/audited/stages.csv` | All 3,455 raw/intermediate/current/candidate rows through 12 recorded stages |
| `audited/players.json` in that directory | Raw original fields, exact source contributions, role boosts, current provenance, per-stage values, subjective preclip traces, unknowns, override statuses and attribution/weight sensitivities |
| `audited/summary.json` | All-five-trait distributions by position, source role, size and source-sample group; ties/ranks; source overlap; research-hold conflicts; generated-scale diagnostics |
| `audited/existing_prospect_conversion.json` | Pure conversion of the 60 already-existing prospects; no new class or growth run |

The [delivered player-input review](ratings-evidence-2026-10-29/DEFENSIVE_ROLE_PLAYER_INPUT_REVIEW_2026_11_11.md) and [role prototype](DEFENSIVE_ROLE_PROTOTYPE_2026_11_11.md) were read. Research-owned files were not edited. The original March source, current canonical and source files are frozen by hash; Python reference files and compressed original canonical are retained in the output directory.

## Trace and limits of recovery

Recorded stages are initial inference; subjective trait/composite calibration; preservation; returning-player manual overrides; rookie conversion; newcomer overrides; roster alignment; stamina repair (no defensive change); post-alignment manual overrides; v7 evidence checks; v8 rotation-profile checks; v11 scouting. Health construction does not change these five trait values and is not rebuilt. Current source/parser semantics—including mixed numeric strings—are reproduced, not silently corrected. The historical baseline is read solely to reproduce current construction; no old-save compatibility work is added.

**Physical overlay is explicit:** before inference, official roster data changes 378 source heights and 26 position labels. Available heights rise 433→501. Recomputing the base cohort's height percentiles changes 500 of 526 initial rim preclips, including some players whose own height did not change. That is a construction-context effect, not new defensive evidence. `original_March_source_fields`, `roster_overlay_changes` and `pre_roster_initial` retain both sides. Candidate references stay frozen to the original source; evaluation uses explicitly overlaid current physical fields. Footwear/measurement-definition compatibility remains an anchor question, not an assumed skill improvement.

The initial equations retain real values such as **103.46,106.70,108.51**, calculated from actual available fields and the documented role bonus. During subjective calibration a private observer records the actual full-precision pre-clamp arguments, while returning the original clamp result. The 53 imported rookie conversions also retain all 265 actual pre-trait-bound values from the conversion function; no capped value is inverted. Upstream historical college/generator latent states are not claimed recovered. No production instrumentation is installed.

Current provenance contains 1,991 subjective-calibration markers, 2,845 preservation markers, 496 roster-alignment markers, 265 rookie priors, 142 manual overrides and 8 v11 defensive decisions. Markers overlap; do not add them. Preservation often replaces newly calibrated numbers with older values. A historical preserved100 does **not** uniquely reveal its former latent value. The 2,845 preserved records explicitly retain that unrecoverable-history warning. The 165 newcomers' initial defaults/conversion priors are not March NBA observations; missing original-source estimates are held and labeled.

There is an additional semantic mismatch: import `_trait_composites` still uses the old average of effort/scheme/navigation/rim for its DEF nudge, excluding lateral, while runtime DEF uses `.60*(.42 effort+.36 lateral+.22 navigation)+.40 effective_rim`. Its DEF adjustment nevertheless moves all five traits; REB and OVR nudges can move them again. A prior's broad subjective DEF or OVR judgment is not five independently measured skill corrections. The experiment records these effects rather than retuning them.

## Numeric range is one problem, not the whole problem

| Trait | Initial preclip >100 | Max preclip | Current100 | Range-only100 | A 100 | B 100 |
|---|---:|---:|---:|---:|---:|---:|
| Effort | 20 | 110.58 | 1 | 0 | 0 | 1 |
| Lateral | 7 | 108.40 | 1 | 0 | 0 | 1 |
| Navigation | 6 | 107.34 | 1 | 0 | 0 | 1 |
| Scheme | 1 | 107.20 | 0 | 0 | 0 | 0 |
| Rim | 36 | 114.65 | 7 | 1 | 1 | 1 |

Initial counts use the 526 original source players; final counts include all 691 with explicit holds/overrides. Rim starts with36 clipped initial estimates, falls to6 endpoints after subjective calibration/preservation, and becomes 7 after the reviewed Wembanyama post-alignment override. The current endpoints therefore arise from **different layers**, not one universal cap bug.

For example, Richards initial95.33 becomes 100 through the subjective prior/nudges and preservation. Huff108.51, Capela106.70, Lopez103.46 and Turner103.26 genuinely exceed100 at initial inference. Stewart101.91 has independent contest evidence against reflex downgrading. An unclipped108 is not automatically better real rim defense than103.

The three comparison lanes isolate distinct questions:

1. **Range-only replay diagnostic:** apply the fixed tail transform to actual reconstructed initial preclip values, then reapply recorded reviewed overrides/holds. It deliberately inherits original ordinal/cohort inputs and is not a stable rollout policy.
2. **A, fixed-reference legacy evidence:** keep current proxy equations and role bonuses, but evaluate raw fields against one frozen526-row reference with equal-value midranks and tail headroom; apply the same fixed trait transform. Bypass subjective/cohort nudges and historical preservation, then explicitly restore recorded overrides and unsupported-source holds. It is therefore a new builder, not merely an exact clipping repair.
3. **B, evidence separation:** keep one event-disruption proxy (steal/deflection evidence), one provisional protection proxy (`.85 block-reference grade+.15 height-reference grade`), and general defensive-impact context separately. Do not reuse those as new measurements of effort, feet, screen technique or help IQ. Only the rim hypothesis gets a comparable experimental replacement; the other four current traits are held, not validated. B's weights are sensitivity hypotheses, not points-prevented coefficients.

The common fixed transform is identity through 80, then `80+20*(1−2^(-(x−80)/20))`: anchors **0→0,50→50,80→80,100→90,120→95,140→97.5**. Ordinary inputs retain tail separation; extreme safety bounds remain. These anchors are declared model examples, **not independently validated skill anchors**. No current-roster maximum, annual reranking, positional percentile inflation or star quota is used. Source lookup uses the same frozen field reference for every role/position, occupying 1–99 with continuous monotone outer tails. A retains legacy role/position-dependent bonuses as an explicit contrast; B protection does not.

Reordering, repeated evaluation, subset membership and an added extreme outlier leave every original candidate result identical when the reference is reused. Omitting `--reference` deliberately creates a new experiment version, not a proposed annual policy. The reference SHA is `e194a0cc75126b852906f77c28a4e7d2802340f3e49059fa4c2bfb26f53a9015`.

**A second numeric defect:** current `percentile_maps` assigns ordinal ranks even to equal raw observations. Identical zero block rates span **13.64 percentile points**; the worst tied steal-rate and DPM groups span 6.92/6.94. Of 507 block-rate rows, 484 belong to tied groups. The candidate's equal-value mapping removes input-order distinctions; real equal observations still tie, appropriately. This does not imply present roster additions already rerank veterans: production explicitly freezes its base cohort for added roster rows. A changed future raw cohort remains a separate reference-version issue.

## Shared evidence, not five independent measurements

Initial effort uses deflections/steals/DPM; lateral and navigation reuse deflections/steals/versatility/DPM with nearly identical weights; scheme uses passing/BBallIQ/DPM; rim uses block rate/height/DPM/generic DARKO. Role text adds further boosts: 251 source players get effort+12; 318 get lateral+4/+10; 213 get navigation+9; 235 get scheme+8; 105 get rim+6/+16. Scheme's role helper checks **offensive and defensive labels**, so an offensive ball-handler/connector label can raise inferred defensive IQ. Rim's role bonus jumps ten points at a source percentile threshold 82.

Mean structural shared-weight mass is **.981 lateral/navigation**, **.800 effort/lateral**, **.816 effort/navigation**, and about .159 rim/event-channel overlaps. This is the sum of common source-weight minima, not outcome correlation, causal overlap or 98% accuracy. Missing fields can redistribute remaining weights. Before clamps, later calibration and nonlinear rim response, the source dependency allocated through the current activity/rim blend averages approximately **26.74% DPM,16.51% deflections,16.61% steals,6.51% versatility,21.58% blocks,9.56% height,2.49% DARKO**. These are construction dependencies, not causal basketball effects.

Real mobility/coordination can help several jobs; shared biological ability is not an error. But a steal/impact proxy reused three times does not independently measure engagement, foot speed and screen technique. B's smallest defensible *source* separation is event disruption, limited interior protection evidence, and contextual general impact. Even these are not statistically independent—impact models may themselves contain events—and are not summed as independent observations. Containment, screen technique, help execution/recovery and aligned sample reliability remain **unknown**. They need separate evidence or explicitly reviewed priors, not new names for the same signal.

Original March source coverage is incomplete: deflections 505/526, steals 507, versatility 454, DPM 520, BBallIQ 444, passing 488, blocks 507, height 433, DARKO 515. After the separately recorded physical overlay, height coverage is 501/526. Protection requires both block and height evidence; B has 485 pre-override source estimates, 454 actual experimental replacements, 31 absolute reviewed rim overrides and 206 held/unidentified cases. Missing block evidence cannot turn height or a role label into excellent rim defense.

## Representative changes and counterexamples

All candidate numbers below are offline hypotheses, not approved targets. Recorded reviewed overrides are explicitly restored, including Wembanyama 100 and White 58.

| Player | Actual initial rim preclip | Current rim | A rim | B rim |
|---|---:|---:|---:|---:|
| Mo Bamba | 114.65 | 58.00 | 93.80 | 89.40 |
| Nick Richards | 95.33 | 100.00 | 88.58 | 86.84 |
| Isaiah Stewart | 101.91 | 100.00 | 90.71 | 87.24 |
| Clint Capela | 106.70 | 100.00 | 92.07 | 87.73 |
| Jay Huff | 108.51 | 100.00 | 92.43 | 89.38 |
| Brook Lopez | 103.46 | 100.00 | 91.02 | 87.86 |
| Myles Turner | 103.26 | 100.00 | 90.96 | 87.07 |
| Rudy Gobert | 108.36 | 99.01 | 92.37 | 85.09 |
| Evan Mobley | 106.95 | 97.51 | 92.17 | 85.79 |
| Scottie Barnes | 70.10 | 90.32 | 68.97 | 76.76 |
| Jrue Holiday | 49.29 | 81.90 | 48.85 | 48.68 |
| Jalen Suggs | 42.73 | 77.38 | 42.77 | 42.32 |
| Stephen Curry | 47.22 | 36.09 | 48.06 | 43.93 |
| Derrick White | 63.84 | 58.00 | 58.00 | 58.00 |
| Stephon Castle | 45.64 | 76.96 | 44.76 | 39.56 |
| Victor Wembanyama | 112.54 | 100.00 | 100.00 | 100.00 |

A/B split the six unreviewed endpoints, but that is insufficient validation. **Mo Bamba's source is 2 games/6 minutes**, yet A 93.80 and B 89.40 make him an unreviewed standout. The current 58 includes older evidence/policy layers that A/B intentionally bypass. This invalidates accepting either builder merely because tail separation improved. Current Thybulle has effort/lateral/navigation 100 from a retained 10-game/122-minute context; A becomes 92.83/92.26/91.97 while B correctly admits it has not reconstructed those skills and leaves them held. No name-specific fix was introduced.

Across 138,075 original-source player pairs, rim A reverses 26,070 current rank comparisons and splits 154 current ties; B reverses 28,292 and splits 152. B also creates 377 new pair ties because correlated aggregate raw observations can coincide. Those are discovery diagnostics, not improvements proved by a new ranking. A mean absolute changes are effort 9.13, lateral 7.98, navigation 8.22, scheme 6.55, rim 7.98 points; B rim 9.30, with other four traits held.

All-player height groups show persistent structural differences: rim medians current/A/B are **44.67/36.99/36.00 below 77 in**, **50.44/50.00/50.00 at 77–81 in**, **73.04/81.94/77.54 at 82+in**. Group sizes 185/361/134; 11 lack height. This is not proof those differences are calibrated, nor a reason to impose equal position distributions. Source GP groups have 96 below 20, 226 at 20–49, 187 at 50+, 182 unknown (including newcomers). Rate windows/denominators are not established consistently; final-season ESPN minutes must not be silently used as the denominator of March hybrid rates. No fabricated sample shrinkage or bench-player quota is applied.

The 11 explicit research HOLD cases, including Gobert/Barnes/Mobley/Curry/Luka and the six endpoints, are reported as conflicts when counterfactual grades move. They are not silently erased. **150 recorded defensive overrides** (142 manual+8 v11) are reapplied exactly. This also exposes a rollout inconsistency: unchanged absolute reviewed grades can sit far above a newly compressed unreviewed scale. Keeping them visible is required; it does not prove all layers now have common absolute meaning.

Wembanyama/White/Castle remain small diagnostic controls only. `review-controls.json` records the delivered research proposals, not the older Castle numbers: Wembanyama effort 88 yields current-function DEF88.330; White navigation 87 gives 74.324 (scheme 84 alone does not change scalar DEF); Castle effort 85.5/rim 62 gives 73.348 while increasing activity. No proposal is installed or used to force podcast order.

## Consequences and integration gate

Display currently uses direct model grades; any accepted raw change propagates visibly. `defense.py`/`sim.py`/`spatial.py` translate activity, effective rim, help/contest and shot-diet consequences. Scheme also affects nondefensive IQ/passing consumers. `save.py` feeds OVR, role forecasts and retention; `transactions.py` valuation/scarcity/core/premium/pick-investment and fresh participant decisions consume those outputs. `contract_ai.py` fresh asks/bids/comps/extensions require regenerated derived profiles, not stale stored asks. No economic behavior was retuned or benchmarked here.

The existing 60 prospects' pure current conversion has median effort 54.20, lateral 51.03, navigation 53.62, scheme 54.75, rim 49.44; rim range 14.12–80.74. It uses talent/archetype/current-ability anchoring, size/rim blends and bounded conversion, not the imported event/role/quantile construction. Similar medians do not prove equivalent skill meanings. Rebuilding only imports could manufacture turnover/cohort gaps. Eventual integration must check imported/generated common anchors, reviewed overrides and capacity interpretation **before** changing development. No new prospects, classes or growth mechanics were generated/retuned.

The role allocator's earlier sheltered-player limitation is unchanged: its five responsibility units must all be filled, so hiding one player leaves duties for teammates or uncovered gaps. Its optimizer forces meaningful duties, including questionable Curry wing work, because it lacks actual low-demand opponent assignments and independent matchup suitability. That is a documented reference-model limitation; this task does not expand it into a coaching engine.

**Next gate, bounded:** validate one evidence-separating *rim-only* construction before a full five-trait replacement. First establish field units/as-of windows and aligned attempt/minute denominators, then fixed cross-role anchors against a small broad guard/wing/big validation set with contest/avoidance/volume evidence and uncertainty. The Mo Bamba small-sample case must cease being an unexplained standout; Stewart/Huff counterevidence and all research HOLD conflicts must be resolved without arbitrary caps. Keep general impact out of duplicated skill measurements. Explicitly decide whether stale composite nudges are removed or rebuilt around the actual trait definitions; do not reapply them blindly.

Once that candidate is accepted offline, a private integration gate must reapply expected-value-guarded reviewed overrides, validate generated/imported anchors, rebuild economic/strategic projections, and run a single bounded paired game sample plus asks/bids/extensions/retention and core/premium/pick safeguards. Cards/Finder/Wants and daily/bulk/reload must agree within the new model; old/new outcomes need not match an intentional recalibration. No coach/rotation/growth changes or legacy-save framework are part of that gate. This is the precise evidence blocker and next experiment, not permission to install A/B now.

## Verification, cost and commands

Seventeen focused tests cover equation parity, real preclip recovery, known-zero fallback, fixed anchors/headroom, equal-input ties, same-scale position/role controls, normal-range monotonicity, subset/order/outlier/repeat stability, missing data, source overlap, offensive-label boosts, explicit override/hold handling and input/output/RNG purity. Full private replay additionally matches all 3,455 current values and their source/component/confidence metadata.

Untraced A+B evaluation of 526 original rows, seven sequential short samples, costs **27.41 ms median (27.16–28.05 ms)**. Separate tracing retains 4.39 MB for the result batch and 21.3 KB after release, with no forced GC; candidate-only process peak is 47.8 MB. The full diagnostic replay/report process peaks 444.9 MB and takes 2.748 s in the final recorded run. Its initial inference/subjective observer/preservation/later layers cost roughly 0.122/0.226/0.071/0.128 s; these are separate diagnostic phase timings, not additive cumulative profiler rows or real-app latency. Earlier development runs varied in I/O/work; no claim of a production speedup or long-lived memory resolution. No global career cache or runtime import was added.

```sh
PYTHONPATH=src:.:tests .venv/bin/python -m unittest test_defensive_input_reconstruction -v
PYTHONPATH=src:. .venv/bin/python scripts/run_defensive_input_reconstruction.py --reference output/defensive-input-reconstruction-2026-11-11/run1/fixed_reference.json --output /tmp/defensive-inputs-new
PYTHONPATH=src:. .venv/bin/python scripts/benchmark_defensive_input_experiment.py --reference output/defensive-input-reconstruction-2026-11-11/run1/fixed_reference.json --rows output/defensive-input-reconstruction-2026-11-11/audited/evaluated_source_rows.json --output /tmp/defensive-inputs-timing-new.json
```

Use new disposable output paths and run samples sequentially. Source-provenance snapshots are separate from performance samples. `.venv/bin/python output/defensive-input-reconstruction-2026-11-11/verify.py` consolidates retained evidence and checks untouched production/prototype hashes without simulations. No season, app-action/economic campaign, preview restart or production installation occurred. Stop at this offline reconstruction milestone.
