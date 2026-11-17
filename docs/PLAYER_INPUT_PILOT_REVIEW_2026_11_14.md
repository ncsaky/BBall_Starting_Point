# Experimental input interpretation and named action pilot — November 14, 2026

The shared experimental interpretation boundary and bounded named-action pilot are implemented, verified and ready for coordinator review, **default OFF**. All 94 approved inputs, 37 capability definitions and 22 role/output definitions remain intact. The pilot reports conditional mechanism behavior under disclosed assumptions; complete player ratings, NBA forecasts and whole-model calibration remain future work.

The current required envelope contains **319 cells: 78 supported source cells and 241 explicit completions**. The six main actors are Luka Dončić, Dylan Harper, Derrick White, Stephon Castle, Ivica Zubac and Rudy Gobert. Caruso, Davion Mitchell and Ajay Mitchell have only the additional screen/navigation role dependencies needed for supported contrasts. Their inclusion does not create full player profiles or live team lineups.

## Evidence, completion and one authoritative snapshot

Read the active checkpoint and final screen/readiness documents before editing. No applicable AGENTS.md was found. Frozen pre-milestone simulator, game kernel, offense, interaction, interior, screen, geometry and player-input modules, authenticated against 1,188 initial file hashes, are retained under `output/player-input-pilot-2026-11-14/reference/`. Earlier milestone artifacts were preserved.

Initial evidence is pinned to the delivered readiness, creation/passing and screen/navigation JSON packets. The independently delivered assumption review was explicitly read and added as a **separate proposed-evidence alternative**. Full SHA256 values appear in the active checkpoint and `verified/summary.json`: readiness `a5114b08b2a0…`, creation `b973bc8b5c78…`, screen `4e49eb36104b…`, supplementary review `a45ae7df68df…`. No source packet was rewritten or silently refreshed.

| Envelope | Required cells | Supported source cells | Disclosed completions |
|---|---:|---:|---:|
| Delivered six-player base consumers | 272 | 54 | 218 |
| Main six with current screen roles and required roller P02 | 290 | 68 | 222 |
| Caruso screener + Davion/Ajay navigator roles | 29 | 10 | 19 |
| Current combined pilot | 319 | 78 | 241 |

The nine archived source documents contain 846 records, including 747 explicit unknowns. Every supported source row is copied exactly. Only the required unknown envelope is completed; unused unknowns remain unknown. Source records, completed records, inherited readiness assumptions, field origins, interpretation operations and ordered scenario overrides are retained in `initial-readiness-completion-layer.json` and `separate-proposed-evidence-layer.json`. These are separately owned experiment artifacts, not production ratings.

`InterpretedInputs` holds one immutable `PlayerInputs` snapshot and one immutable, versioned `InputInterpretation` contract. Its `to_dict()` returns the original completed records with their original scale/protocol labels, not a second rewritten talent document. All consumer projections for a player receive that same view. Snapshot checks compare both raw input content and interpretation identity; conflicting semantics, stale/forged projections and missing required values are rejected. Variants derive from the authoritative immutable views, and inspection/export copies cannot mutate runtime inputs or silently alter a later variant.

The shared module is `experimental_inputs.py`; the four compilers opt into it only for an explicit view. Historical raw/native and legacy `research_scenario` calls retain their existing validation, mappings and revisions. Combining a common view with legacy interpretation arguments is rejected. No save schema, approved catalogue, production setting or app caller was changed.

## Exact interpretation choices

| Input / representation | Declared interpretation |
|---|---|
| Native technique scale | Preserve the historical `grade/100` response index. |
| Research technique scale | Reuse the existing research consumers' normalization as an explicit **trial**: `clamp(.65 + gain × (grade/100 − .65), 0, 1)`, gain 1 at reference, .85/1.15 sensitivity. This does not assert independently measured equivalence between scales. Raw labels, grades, evidence and uncertainty remain unchanged. |
| FT | `research_FT_conversion_percent_proxy_v1` means `percent/100`; Castle's 73.4 means .734. The native FT technique curve remains `.45 + .50 × index`. Release/range and the research technique gain do not alter proxy FT probability. Blind relabeling would have yielded .817 and is rejected. |
| Reported dimensions | Accept the exact reported metric/unit/protocol variants in these packets. A field called `height_inches` whose stored unit is already cm is an alias of the already converted report; it is not multiplied by 2.54 again. Same for reported kg under old pound-field labels. Unknown protocols/units are not guessed. |
| Repeated physical aliases | P03, P05, P08/P09 and P10 research aliases must agree numerically. They describe one control, not independent tests or repeated bonuses. Conflicting aliases fail. Synthetic quantities remain estimated, and descriptor grades cannot become measured m/s or m/s². |
| Contact/balance capacity | Force control `F/(F+1000N)` and time control `1s/(time+1s)` supply common dimensionless responses: 1000N → .5 and .5s → 2/3. Reference constants belong to the shared contract. A native capacity index supplies its declared response directly and does not invent force/time. If both representations are present they must agree. Competing legacy capacity-reference coefficient overrides are rejected on the common path. |
| Scenario conditions / location | Only explicitly supported standardized-opportunity conditions are interpreted. The two-bin T02 control uses a declared .7 rim fraction within the two-point opportunity; the native three-bin representation stays intact. The split is context, not a new talent estimate. |
| T11 | The delivered .35 screen/.40 roll/.10 pop/.15 slip policy is preserved raw. Explicit `condition_on_supported` policy conditions on the .90 supported mass, producing .388889/.444444/.166667 screen/roll/slip. It makes no prediction for the excluded pop context. Default policy rejects nonzero pop; pop is never silently reassigned or called F03. |
| Geometry alternatives | Matched-body controls use a scenario-only protocol, and the review's 292.10/297.18cm Gobert alternatives retain dated historical protocols. They are not relabeled as measured current reach or unchanged H1 formula outputs. |

Role-specific dependencies remain 9 screener, 10 navigator and 5 recovery-coverage inputs, with the existing C27/P02 envelope for the roller defender. Unused role inputs stay unknown. Nested `prepare_screens → compile_profile` receives the same interpreted snapshot automatically. Offense, interaction, screen and nested interior therefore agree on capacities, movement and technique response semantics without conflicting duplicate measurements.

The four delivered screen-role failures were reproduced using the raw operational packet and then resolved with the explicit view/completion policy. These raw calls remain rejected without the view; no global validation was weakened to make a packet pass.

## Conditional action results

The runner evaluates 47 declared scenarios. Fixed-parameter pass/help/security samples use 4,096 seeded trials per actor/row; screen-phase samples use 512, with paired random draws. Wilson intervals and paired sampling intervals describe repeated simulated events at those fixed choices. Source/prior ranges and coherent alternatives are separate sensitivity cases, not statistical confidence intervals or a probability distribution over true player talent.

The first probes hold uncertain movement, receiver, window or opposing actors common. Alternatives include source-range endpoints; coherent slow/reference/fast motion `(2.5,5.5,2.2)`, `(3,6,2.5)`, `(3.5,6.5,2.8)` in m/s²,m/s,m/s; relative lateral stresses; recognition/attention decompositions; read/execution alternatives; receiving/security/risk controls; supported screen-policy strata; capacity responses; dated reach; mapping gain; and a few combined stresses. No Cartesian all-extreme sweep, coefficient/rating tuning or forced rank ordering was performed.

| Contrast | Reference observation | Sensitivity and interpretation |
|---|---|---|
| Castle / Luka containment | The same synthetic creator has beat probability .15985 versus Castle and .20902 versus Luka: 4.92 percentage points less access against Castle **conditional on retaining the ball**. | Tested conditional differences range −2.44 to +7.66 pp. Narrowing the supported technique contrast and opposing uncertain movement reverses it. This supports a conditional containment mechanism, not a complete defender ranking. |
| White / Castle help | Notice probabilities .7079/.4361, arrivals 1.1133/1.2654s at a 1.25s window. White has 1,453 timely events/4,096; Castle 0. White's sampling interval is .3402–.3695, while Castle's zero-event upper bound is .00094. | The timely difference spans −21.81 to +37.80 pp, with zero where neither arrives. The reversal is an explicitly tight 1.2s/opposed-mobility case; it is not inferred from the common 1.25s case alone. Common attention and competing read-limited/attention-limited stories expose attribution uncertainty. |
| Luka / Harper F03 | Notice .9335/.6960 and accurate delivery given notice .6646/.5502. Secured catches: 1,736/1,045 out of 4,096; paired difference .1687, conditional sampling interval .1572–.1802. | Both notice and conditional-delivery directions remain positive through the tested matched-window/source-envelope alternatives: minima +9.50/+1.31 pp. This is the more stable tested contrast, conditional on the declared available option and common receiver. It does not measure overall creator value. |
| Luka / Harper F04 | Reference notice/delivery differences favor Luka by 24.23/13.30 pp. Harper's initial F04 values are disclosed unknown-skill controls. | A broad strong-Harper-unknown alternative reverses them to −.95/−3.13 pp. The lob ordering is unidentifiable from the present source record, not evidence Harper is actually superior. |
| Zubac / Caruso set screens | In the called-roll stratum, Zubac adds 42.42ms more effective legal navigation delay (paired sampling interval 41.68–43.15ms). | Supported overlapping source alternatives reverse the difference; tested range −13.15 to +45.79ms. Body-normalized controls are reported separately. No unique screen-technique rank follows. |
| Zubac / Gobert screen prior | The initial generic Gobert completion creates a 77.27ms difference. | The separately proposed screening layer shrinks it to 7.25ms; overlapping proposed ranges reverse it to −51.01ms. Gobert's initial 65 was a common unknown prior, not evidence of ordinary/weak screening. Even the proposed estimate remains an uncertain, historically constrained hypothesis. |
| Davion / Ajay navigation | Davion incurs 49.89ms less extra screen delay under common movement and the reference grades. | Tested differences span −56.59 to +21.53ms; overlapping S35 plus ±.3m/s relative lateral uncertainty reverses direction. The source supports a useful navigation contrast, while isolated player ranking remains assumption-sensitive. |

Two Harper F03 explanations illustrate why aggregate outcomes cannot identify the raw cause. R65/E80 yields 1,092 catches, 1,344 missed reads and 1,121 inaccurate deliveries; R78/E65 yields 1,093 catches, 843 missed reads and 1,585 inaccurate deliveries, each out of 4,096. Their catch sampling intervals overlap. Recognition, placement and receiving need tagged observations before choosing one decomposition.

Security is also prior-sensitive. At imposed pressure .8 and one-second exposure, Luka's source-unknown S17 alternatives 65/80/90 imply modeled handling-loss probabilities .07884/.04848/.02824. Harper's source midpoint 89 gives .030264. Seeded loss counts are 319/196/115 versus 124 out of 4,096. These conditional alternatives cannot identify a real security ordering from aggregate turnovers. The small coupled first-action samples produced no handling losses and no changed sampled choices under common risk .35/.65; those observations are **indeterminate**, not proof security or risk is unimportant.

Common strength/balance response changes cancel in the matched screen-contact ratio, leaving those relative delay samples unchanged; they do change the existing C27 response. Under matched contest geometry, the dated Gobert reach alternatives give block probabilities approximately .00202/.00268, versus .00246 under the original H1 prior. Common jump 25/55cm yields approximately .000083/.00401. These are small conditional model responses, not validated block-rate forecasts; jump/arrival/release assumptions remain material.

Coupled first-action probes record advance, notice, choice, pass and help stages alongside typed outcomes. Their named receivers differ, so they are feasibility/context probes rather than isolated creator comparisons. The resolver does not itself sample the catch or made FG; receiving is sampled separately in the fixed-receiver probes and in two eight-regulation-possession counterfactual kernel checks. Those declared three-versus-three pods validate contracts, nested compilation and event accounting; they are not live team ownership or NBA game predictions.

## Verification and reproducibility

```sh
PYTHONPATH=src:tests:.:scripts .venv/bin/python -m unittest test_experimental_input_pilot test_screen_navigation test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research -q
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_player_input_pilot.py --output output/player-input-pilot-2026-11-14/verified
```

Use another output directory to preserve the retained run. The runner is offline and writes only experiment artifacts. **168 tests passed in 24.646s:** 20 new focused checks and all 148 previous tests. Checks cover mappings/units/FT, conflicting aliases/capacity representations, T11, missing inputs, unused roles, mixed interpretations, source preservation, revisions, mutation isolation, effective overlay provenance, reconstruction, accounting and release.

Eight full ordinary real-roster results and sixteen full prior experimental results match authenticated frozen modules exactly. The reference builds profiles through the frozen compilers, not changed shared helpers. Fourteen legacy research-mode profile calls also match fully. Separately, eight native/interpreted cases across both modes/seeds preserve complete results **and RNG seed/draw-stream digests** before versus after the exact local optimization. Detailed digests, records and source hashes are retained in the parity/manifest JSON files.

## Bounded cost attribution and exact optimization

The pre-optimization profile identified repeated screen validation: 30 `compile_screen` calls for 10 immutable participants. The only performance change is a preparation-local set that validates each immutable actor once. Every call still checks participants, exposure, ownership, role eligibility and helper/roller constraints. Each actor still receives the authoritative-snapshot and forged-projection checks. There is no global cache, gameplay/RNG change, diagnostic removal or production GC change.

The original post-interpretation, pre-optimization screen source and its hash are preserved under `cost-audit/`. Identical-budget before/after measurements use the same seed, full inputs, controls, diagnostics and results. Native and interpreted fixtures are separate experiments; their difference is not labeled pure interpretation overhead.

| Same-fixture call (16 regulation possessions/side) | Before median [range], ms | After median [range], ms | Revalidation count |
|---|---:|---:|---:|
| Native, 10 actors | 28.118 [28.010–28.155] | 18.843 [18.596–19.702] | 30 → 10 |
| Interpreted counterfactual, 6 actors | 16.710 [16.431–16.898] | 14.656 [14.277–15.189] | 6 → 4 |

Each row has five warm wall samples, without profiling or serialization. The native median fell 33.0%; the interpreted median fell 12.3%. This bounded observation is not a whole-app or scaling guarantee.

Instrumented attribution separates preparation/validation plus required credibility math, known diagnostic construction, event work including its mandatory ledger, final accounting, and a labeled mixed boundary/final-report residual. The diagnostic slice excludes the required credibility calculation from spatial report construction and includes pure reference reports. Event ledgers and the mixed residual are not falsely called pure basketball or pure diagnostics. Nested screen/action timings are readouts and are not added again to the partition. Wall samples and serialization are outside the profiler.

| Instrumented partition, ms | Native before | Native after | Interpreted before | Interpreted after |
|---|---:|---:|---:|---:|
| Preparation/validation + required spatial math | 20.181 | 9.882 | 10.382 | 8.415 |
| Known diagnostic construction | 2.609 | 2.545 | 2.534 | 2.629 |
| Event work + mandatory ledger | 13.409 | 14.101 | 10.282 | 10.049 |
| Final accounting | 0.388 | 0.398 | 0.521 | 0.560 |
| Mixed boundary/final report | 2.876 | 2.961 | 1.450 | 1.492 |
| Instrumented total | 39.464 | 29.887 | 25.170 | 23.145 |

Native action resolution has 47 calls, averaging .256/.270ms before/after under instrumentation; interpreted has 94 calls, averaging .083/.081ms. The optimization targets preparation, and the action timing difference is not claimed as an improvement. Both cost fixtures realized 16 possessions per side. See `cost-attribution.json` and retained pstats for nested readouts.

The full diagnostic result is retained. Native full/core JSON sizes remain 497,010/4,977 bytes before and after; serialization is measured separately. One-off completion/audit, ledger export and profile-configuration setup are also measured separately from game calls. Remaining opportunities are duplicate spatial-report construction and raw diagnostic conversion; neither was removed or expanded into a performance campaign.

Native full JSON serialization medians are 9.627/9.669ms before/after, versus 0.0984/0.0986ms for the core subset. No diagnostic payload was removed. First observed completion/audit was 92.72ms, effective-ledger export 19.00ms and six-actor configuration compilation 8.69ms. Those separate setup observations include local reads/validation; they are not cold-start guarantees or per-action costs.

All 32 probed roots released in four fresh pilot/configuration/kernel calls before the final diagnostic GC. Traced peak was 11.54MB, including completion and audit work; current traced allocation was 72,031 bytes before diagnostic GC and 18,455 after. Observed process RSS ranged 166,048–170,304KiB. No production GC/cache was added. These four calls establish bounded ownership/release behavior, not whole-app or long-career stability.

## Review boundary and next evidence

The most useful next observations are matched movement/first-step and assignment-tagged help, available-read versus intended-placement/catch failure tags, and legal screen/contact/follow-up samples. Source ranges and plausible raw decompositions should remain separate from model response calibration. The review's proposed Gobert screening/geometry, Zubac short-paint touch and Castle open-shot hypothesis are preserved as explicit overlays with their uncertainty; none establishes a complete player profile.

Calls, starting geometry, coverage policy, route endpoints, opportunity/risk controls, receiving context and the previously bounded action set remain explicit. Pop and F07 remain unsupported in the relevant paths. No new basketball subsystem, UI, server, season study, production rating, economy/development tuning or live activation was added. App/calendar/daily-bulk/reload and live economic parity are unwired and unclaimed. Stop for coordinator review.
