# E2 input estimator

TL;DR: All 691 players now have 94 usable, evidence-labeled inputs, and prospects have a standalone estimator.
Observable shot/play frequencies now inform tendencies; weak player-specific priors preserve uncertain distinctions elsewhere.
The output validates under the existing schema; native `prior` status needs the coordinator change described below.

## Stable output contract (component A → component B)

`data/canonical/player_inputs_2026_27.json` is exactly an existing input section:
`{"version": INPUT_VERSION, "registry_version": REGISTRY_VERSION, "players": {canonical_id: PlayerInputs_document}}`.
Each document has `version`, `registry_version`, `player_id`, `inputs` (all 94 registry IDs).
Each record has existing `status`, `value`, `evidence`, `uncertainty`, plus `reason`.
**Schema limitation:** `player_model.py` accepts only unknown/estimated/observed. Therefore populated records use `status: "estimated"`; `reason: "prior"` versus `reason: "estimated"` is the authoritative evidence distinction. Consumers must use `reason` (or `input_estimator.estimation_status(record)`) to display prior versus player-evidence estimate. No schema or registry semantics are changed by E2. Proposed coordinator follow-up: explicitly admit `prior` as a non-null status in `_record`, then migrate the label from `reason` with one coordinated schema decision.
Grade values retain `{grade, scale}`; physical values retain `{measurements, display_grade?}` in registry units; tendencies retain their registry probability/distribution shapes.
`uncertainty.notes` is a JSON-encoded object, readable using `json.loads`, with numeric `interval` (scalar inputs) or `intervals` (distribution outcomes), plus `basis` and `limitations`. These are broad plausibility bands, **not calibrated statistical confidence intervals**. Physical measurements also have native-unit `interval` on each measurement. No extra unsupported schema fields are emitted.
No wall-clock timestamps or random state enter the output. IDs and evidence records are deterministic. The build script writes canonical sorted JSON with a trailing newline.

## Objective and boundaries

All 691 canonical players plus a standalone prospect function; standard library only; no engine, schema, draft, universe or old trait changes. Owned source: `input_estimator.py`, `build_player_inputs.py`, `test_input_estimator.py`, this report, generated output, and the explicitly requested board status update.

## Public functions and adapter handoff

- `InputEstimator.from_local(repo_root).estimate_universe(universe)` returns the complete section described above.
- `InputEstimator.estimate_player_inputs(player, traits=None)` returns an immutable `PlayerInputs`; call `.to_dict()` for the document. Related legacy traits weakly condition priors only. `from_local()` loads canonical legacy traits; an explicit `traits` argument overrides that fallback. `estimate_universe()` uses each player’s canonical trait rows, independent of row order.
- `estimate_prospect_inputs(prospect, traits, scouting)` returns the same `PlayerInputs` type and definitions. Accepts existing draft dataclasses or dictionaries, draft trait rows or a broad-trait mapping, and existing scouting reports or explicit `InputEvidence` observations. True broad traits take precedence over fogged broad scouting. Rank, current overall, projected potential and health are not substituted for current technique.
- `InputEvidence` adds per-player, per-input sources through `InputEstimator(additional_evidence={player_id: [observations]})`. It requires the registry value shape, matching scale/conditions, source and correlation IDs, method, uncertainty band, actual exposure unit and shrinkage exposure. Qualitative evidence explicitly uses an assessment unit rather than invented possession counts. Correlated duplicate observations within the added-source list contribute only the strongest entry; source authors must identify overlap with built-in sources and avoid reintroducing the same sample under a new ID. Distribution evidence must preserve reference opportunities and outcome sets. Physical evidence stays in native units.
- The adapter must not interpret the grade scale as an observed success probability. FT is explicitly a separate percent-conversion proxy. Physical geometry and jump capacity have measurements/estimates in cm or kg; untested other physical families have separate display grades, not fabricated physical trials. T02 is a conditional four-region distribution, not a measured heatmap.

## Method and evidence boundaries

The priors start from declared position and offensive role, without hard skill caps, then weakly condition on that player’s related evidence wherever direct evidence is absent. Fixed technique anchors are 50 functional, 75 strong, 90 exceptional. Smooth rescaling uses `50 + 50*tanh((statistic-reference)/spread)`, with fixed reference/spread values rather than annual extrema or simulation outcomes. Uncontested FT conversion uses `100 × shrunk FTM/FTA`, explicitly declaring that distinct scale. There is no rating clipping.

ESPN joins use explicit IDs. Provider joins use unique normalized exact names, preserving accented-name equivalence but rejecting duplicates; there is no fuzzy match. The later `player_stats.json` snapshot is preferred per available field, then the skill-input snapshot. Completed regular-season career totals use 2025–26, 2024–25 and 2023–24 with exposure weights 1, 0.6 and 0.36. Their shooting sample replaces overlapping provider shooting rather than adding it. Future seasons, ambiguous rows, missing denominators and invalid makes/attempt pairs are excluded. The damaged historical game-box shooting cache is never read.

Shooting shrinks makes/attempts toward position/role priors with 100 effective prior FT attempts and 250 three-point attempts. Provider fallback uses percentage plus approximate per-game attempts × games, halving effective exposure because the windows are mixed. Catch/pull-up/movement shooting shares one broad three-point constraint and an explicitly uncertain mode-difficulty prior; it is not three measured samples. S10 uses mixed close-shot efficiency with a weak, explicitly heuristic exposure; S05/S18/S22 use play-type efficiency only as weak, highly uncertain technique constraints (maximum 35% data weight). Their tools/shot-selection decomposition is **not independently established**. These fixed choices were not fitted to hand packets or game output.

Passing recognition is weakly constrained by assist creation, delivery by the separate provider passing model. Those are not available-read or successful-pass fractions. Provider rates use their own snapshot's minutes with a mixed-window discount; career fallback uses its own weighted window. Up to 55% data weight is shrunk by `minutes/(minutes+750)`. Observed handler/roller/post/transition deployment only establishes relevant context, not intrinsic route willingness or coach-independent opportunity. Unsupported post-entry, lob and skip contexts remain priors unless a specific expert claim exists. Shared family observations retain correlation IDs; the 18 approved passing dimensions remain separate records.

Reported height, wingspan and mass are converted in units, with uncertainty for unknown protocol/date. Unreported span uses height plus a position prior; standing reach uses an explicitly uncertain anthropometric prior. Jump and other untested capacities remain broad priors. Body/age context, observed workload and related legacy traits can weakly condition those priors; mass is not a strength measurement, minutes are not a conditioning trial, and effective navigation is not raw lateral capacity. Sustained workload is a weaker clue to between-effort recovery than to conditioning, so these remain separate prior estimates.

Observed actions do not enumerate every feasible alternative. Available attempt and play-type frequencies now estimate tendencies conditional on retained deployment, with partial/inferred components explicitly identified. Families without available choice evidence remain **conditional player/position/role priors**, with broad bands. Rebound, steal, contest, navigation, communication and responsibility totals do not identify most corresponding raw techniques. Many of these cells also remain priors; no player is claimed to have been measured in 94 ways.

Expert evidence uses only the newest estimated source records from the local research packets, including retained Nerd Sesh source IDs, dates, claims and uncertainty. It ignores scenarios, operational completions and unknown cells. Technique estimates receive a 35% expert adjustment; disagreement widens the band and preserves the original statistics/prior evidence. This is an explicitly provisional judgment, not a claim that expert numerical midpoints are ground truth. No purchases, network access or fresh transcript claims were needed. Workbook-derived fields already retained by the skill bundle are not counted as independent new evidence. No game or season simulations were run.

Prospects use the same input meanings with wider uncertainty. Existing broad draft traits and broad scouting estimates only condition uncertain priors, and stay labeled prior; they are not renamed raw technique measurements. The real 2026 cache has per-36 assists but no retained shot-attempt denominators, so it weakly informs connector recognition while shooting remains prior. If future public prospect data includes games, attempts and FT/three percentages, the function uses quarter effective attempt exposure for competition uncertainty. Explicit dimension-level scouting/evidence can be added through `InputEvidence`. The current generated draft model does not contain 94 independently generated talents; E2 does not invent that missing detail.

## Adapter feedback changes (all four requested follow-ups)

1. **Player-specific priors:** missing direct inputs now condition on related legacy summaries (`legacy_trait_prior`), provider play types and outcomes, observed minutes/workload, defended-position shares, defensive role, and body/age context. Every affected record stays `reason: prior`, low confidence, with broad uncertainty. Uncontested FT and other existing direct statistical estimates are unchanged by this step. No traits are simply renamed as measured raw skills or capacities.

   The update is a small residual in log-odds space around the position/role prior. Maximum residual budgets are 0.60 for the average related legacy signal, 0.40 for average related statistical context, 0.25 for body/age context and 0.20 for defensive-role context. Signals are smoothly bounded with `tanh`; provider context is attenuated by its own `MP/(MP+750)` exposure, or a declared 0.2 weak factor where exposure is unavailable. Correlated metrics are averaged, not counted once each. Recovery uses 55% of the conditioning/workload residual budget, since recovery between efforts is a different capacity. A jump prior changes only in native cm, retains a broad band, and is never presented as a measured jump. Distribution priors update each named outcome and preserve sum-to-one and reference conditions. No random jitter, named-player estimator exception, adapter-correlation target or minimum-spread target enters the ratings.
2. **Wembanyama and join audit:** he already matched both Crafted snapshots and his ESPN ID. His original catch-three estimate used a .34524 weighted career conversion rate and 733.64 weighted attempts; passing used the retained provider assist/passer fields. Near-reference estimates were not a failed join. His release/range priors now respond weakly to related evidence. The reproducible report below lists all high-minute missing joins and his requested input values. A missing skill row cannot remove a player from the audit because eligibility checks all retained 2025–26 minute sources separately.
3. **Spread for every input:** the generated report includes native-unit population standard deviations for all 94 families across 279 players with at least 1,000 retained minutes, including every distribution outcome. Near-zero components are flagged with declared thresholds. Diagnostics are read-only and never feed the estimator. Identical evidence still produces identical values; tests explicitly verify a truly flat synthetic cohort is flagged rather than assigned invented variation.

4. **Observable tendencies and shot volume:** T02 estimates 3PA/FGA from current completed ESPN attempt counts, with valid Crafted rate/attempt fallbacks and 100 prior attempt shrinkage. Actual 2024–25 aggregate shot-bin counts condition the rim/short-paint/midrange mix for the 32 matched reference players; source totals reconcile, two-foot bin boundaries and the older season widen uncertainty. Other players’ unobserved two-point regions retain priors. Three-point accuracy, close-shot efficiency, the damaged game-box cache and the ambiguous `FREQ` field are not repurposed as attempted-shot volume.

   T01/T03 use partial play-type action/mode proxies, T09 observed cut tags, T11 observed roll participation with a broadly inferred roll/pop/slip mix, and T12 an offensive-rebound-rate crash proxy with explicitly uncertain recovery conversion. Transition tags, movement tags, usage and foul exposure inform T05/T10/T08/T18. Exact pass/reset, catch/pull-up and screen-continuation opportunities are not invented: those components retain prior mass or wide proxy uncertainty. All are conditional on retained deployment rather than claiming pure coach-independent willingness. The generated coverage table gives the per-family counts.

## Supplied real-stats scorecard and release target

Claude’s baseline in `docs/agents/tasks/e2-feedback-from-adapter.md`: 1,230 simulated 2025–26 games, 150 high-minute players, mean absolute error per 36 minutes. These are supplied baseline results, not simulations run by E2.

| Stat | Old traits | Previous new inputs | Revised E2 |
|---|---:|---:|---|
| Points | 2.90 | 4.10 | not rerun |
| Field-goal attempts | 1.96 | 2.59 | not rerun |
| Three-point attempts | 0.52 | 1.65 | not rerun |
| Assists | 1.11 | 0.96 | not rerun |

League scorecard baseline: 12 of 18 metrics in band for either supplied run. **Release target:** beat the old-trait error column, while preserving league-level results and the odds scorecard. No revised scorecard pass is claimed here. No game/season simulations were run in E2, and no estimator coefficient was fitted to these errors. Claude owns the integrated scorecard rerun and any engine/adapter corrections it reveals.

The parallel adapter now includes `T02:three` in shooting range and `T02:rim` in rim pressure (confirmed read-only during this revision). The earlier missing-T02 routing observation is superseded; this worker did not edit adapter code. The evidence is now available in the stable record shape for that bridge.

A read-only adapter smoke check on the rebuilt records distinguishes the four previously identical defensive-effort examples: Curry 65.875, Gobert 82.000, Gilgeous-Alexander 66.000 and Wembanyama 71.121 (previous feedback: all 56.0). This confirms the flat-prior failure is addressed; it is not an accuracy target or independent validation, since the prior now explicitly includes weak legacy evidence. No adapter code or simulation behavior was edited.

## Known weak spots and coordinator decisions

1. **Status enum:** the requested native `prior` literal is incompatible with the untouched schema. This deliverable uses the valid, clearly labeled `reason` workaround at the top of this report. Proposed follow-up is to add non-null `prior` support to the central validator and agree the input-version policy, then coordinate producer/adapter/display together. Do not silently display every `status=estimated` record as player evidence.
2. **Sparse raw evidence:** most technique/tool decompositions and every intrinsic tendency are weak. Many defensive and rebounding techniques have weak player-conditioned priors rather than direct observations. This output is complete storage and an estimator foundation, not a claim that those distinctions are well measured enough for Stage 1 release. Prior-heavy defensive rankings deserve review before the adapter or market treats them as precise.
3. **Mode/passing inference:** broad outcome-to-technique mappings and effective exposure factors are declared basketball judgments. They cannot establish causal separation from tools, opportunity or deployment. No nominal confidence level is attached to the plausibility bands.
4. **Shared validation evidence:** final expert-adjusted agreement is descriptive and partly circular. The report also gives differences and band coverage without packet-expert adjustments, retaining weak legacy/statistical prior context. Those checks avoid copying the hand packet adjustment but are not a fully held-out test of skill accuracy. Hand-reference magnitudes remain provisional. One display-only physical descriptor uses an unaligned scale and is excluded from numeric comparison.
5. **Additional evidence:** future Basketball Index, tracking or scouting sources can fill individual dimensions without replacing the estimator. They must declare sample definitions/units and shared lineage; provider effective impact cannot be directly relabeled pure technique.
6. **Runtime and output:** this batch creates a roughly 92 MB canonical file because each conditioned prior carries its source attribution. Nothing is added to a live simulation path. Adapter/load caching and normal-gameplay speed remain the coordinator's integration work.

## Resume state

Complete and ready for coordinator review: all four adapter requests, including the added observable-tendency estimates and supplied scorecard, are folded into E2. Canonical output is rebuilt for all 691 players; schema and value shapes are unchanged. Wembanyama joins both Crafted snapshots and his ESPN ID. All 94 families have reported spread across 279 rotation players; no missing high-minute joins or near-zero components were found at the declared thresholds. Board status: **review**. No commits, engine/adapter/schema edits or game/season simulation runs by this worker. Claude owns the integrated scorecard rerun; no new scorecard result is claimed.

## Verification

- `PYTHONPATH=src .venv/bin/python scripts/build_player_inputs.py` — succeeded: 691 players × 94 inputs; final build/comparison/write **8.021 seconds**, canonical JSON **91.98 MB**.
- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_input_estimator tests.test_player_model_schema tests.test_trait_adapter` — **76 tests passed in 28.495 seconds** (51 estimator checks, 16 existing schema checks and 9 adapter checks).
- Checks include all-player schema/non-null values/uncertainty, no maximum pile-ups, serialized artifact parity, player/source/legacy-row order invariance, separate-process byte equality across hash seeds, direct-stat orderings, ambiguous and missing joins, dated/future/invalid shooting exclusions, weak source-labeled priors that preserve player differences, unchanged direct estimates, no fabricated physical tests, recovery/conditioning separation, all 94 rotation spreads and deliberate flat-cohort flagging, 3PA/FGA-driven shot location, rejected efficiency-as-volume, reconciled historical bins without double counting newer three-point rates, conditional cut/mode/roll/crash proxies, unchanged pass/reset prior mass, source correlation and opportunities, generated dataclasses and all 60 real cached prospects.
- The read-only adapter smoke check above confirms the previously identical effort examples differ. It is descriptive, not a calibration target. Full engine/save tests and game simulations are outside this estimator-only change.

<!-- E2 generated evidence report -->

## Build and coverage

- Method: `e2_evidence_estimator_v3_conditioned_priors_observed_tendencies`. Built **691 × 94 = 64,954** complete records.
- **13,317 player-evidence estimates; 51,637 explicit priors.**
- Local joins: 526 unique skill names, 528 unique later Crafted names, 616 ESPN IDs. Sources are overlapping, never additive player counts.
- Build, validation, comparison without packet experts, serialization and write: **8.021 seconds**; canonical JSON 91.98 MB.
- Skill-grade range 19.588–90.438; exactly 100: 0; at least 99.9: 0. No scale-max clipping.

| Input family | Player-evidence estimates | Priors | Total |
|---|---:|---:|---:|
| Physical tools (12) | 1,758 | 6,534 | 8,292 |
| Shooting (9) | 2,447 | 3,772 | 6,219 |
| Finishing and receiving (6) | 513 | 3,633 | 4,146 |
| Handling and attack recognition (5) | 304 | 3,151 | 3,455 |
| Post craft (3) | 148 | 1,925 | 2,073 |
| Foul craft, routes and screening (5) | 14 | 3,441 | 3,455 |
| Rebounding technique (4) | 0 | 2,764 | 2,764 |
| Defense technique and recognition (14) | 50 | 9,624 | 9,674 |
| Passing recognition (9) | 1,959 | 4,260 | 6,219 |
| Passing execution (9) | 1,881 | 4,338 | 6,219 |
| Conditional tendencies (18) | 4,243 | 8,195 | 12,438 |

## Per-input coverage and hand-reference comparison

Newest estimated source cells from **32 players**, 293 cells; 292 comparable numeric cells. One display-only physical descriptor has no aligned scale and is excluded from numeric agreement. Unknowns do not overwrite earlier estimates. Nov15 uses `proposed_source_input_section`; scenarios, operational profiles and completion suggestions are excluded.

The final estimate includes a 35% adjustment toward sourced expert technique judgments. **This comparison shares expert evidence with the reference; it is not independent validation.** The last two columns rerun the estimator with every packet-expert adjustment disabled, retaining the declared legacy/statistical prior context. No constants were fitted to either comparison. Expert agreement must not be read as accuracy against ground truth. Expert-adjusted bands deliberately retain source disagreement, so they contain the reused hand value by construction; the bands without packet adjustments do not have this guarantee. This is a comparison without those packet adjustments, not a fully held-out test: legacy priors may share related expert/statistical information.

Differences are in each input’s native units: technique grades, FT percentage points, geometry cm or mass kg. Technique comparisons provisionally share the hand packets’ 50/75/90 anchors; FT retains its separately declared conversion-percentage scale. No mixed-unit grand average is reported. “Inside” asks whether the hand midpoint falls inside the estimator’s broad plausibility band, not whether two calibrated confidence intervals overlap. A dash means there is no comparable hand cell.

| Input | Name | Estimated | Prior | Hand cells | Mean absolute difference | Inside band | Difference without experts | Inside without experts |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| P01 | Height | 680 | 11 | 32 | 0.00 | 100.0% | 0.00 | 100.0% |
| P02 | Wingspan | 427 | 264 | 32 | 0.00 | 100.0% | 0.00 | 100.0% |
| P03 | Standing reach | 0 | 691 | 0 | — | — | — | — |
| P04 | Body mass | 651 | 40 | 32 | 0.00 | 100.0% | 0.00 | 100.0% |
| P05 | Acceleration / first step | 0 | 691 | 0 | — | — | — | — |
| P06 | Straight-line speed | 0 | 691 | 0 | — | — | — | — |
| P07 | Lateral mobility / change of direction | 0 | 691 | 0 | — | — | — | — |
| P08 | Functional strength | 0 | 691 | 0 | — | — | — | — |
| P09 | Physical balance / stability | 0 | 691 | 0 | — | — | — | — |
| P10 | Vertical / jump capacity | 0 | 691 | 0 | — | — | — | — |
| P11 | Conditioning | 0 | 691 | 0 | — | — | — | — |
| P12 | Recovery between efforts | 0 | 691 | 0 | — | — | — | — |
| S01 | Catch-and-shoot three-point execution | 531 | 160 | 12 | 11.26 | 100.0% | 17.32 | 100.0% |
| S02 | Pull-up three-point execution | 531 | 160 | 5 | 17.85 | 100.0% | 27.47 | 80.0% |
| S03 | Movement three-point execution | 531 | 160 | 3 | 20.20 | 100.0% | 31.08 | 33.3% |
| S04 | Catch-and-shoot midrange execution | 0 | 691 | 0 | — | — | — | — |
| S05 | Pull-up midrange execution | 310 | 381 | 0 | — | — | — | — |
| S06 | Movement midrange execution | 0 | 691 | 0 | — | — | — | — |
| S07 | Free-throw execution | 542 | 149 | 14 | 2.15 | 100.0% | 2.15 | 100.0% |
| S08 | Release / preparation technique | 1 | 690 | 1 | 4.88 | 100.0% | 7.51 | 100.0% |
| S09 | Distance-extension technique | 1 | 690 | 1 | 21.53 | 100.0% | 33.12 | 100.0% |
| S10 | Layup / close-touch execution | 507 | 184 | 5 | 18.89 | 100.0% | 29.06 | 100.0% |
| S11 | Floater / short-paint touch | 2 | 689 | 2 | 19.10 | 100.0% | 29.38 | 100.0% |
| S12 | Dunk execution | 0 | 691 | 0 | — | — | — | — |
| S13 | Aerial catch-to-finish execution | 0 | 691 | 0 | — | — | — | — |
| S14 | Receiving / catch control | 2 | 689 | 2 | 14.91 | 100.0% | 22.93 | 100.0% |
| S15 | Contact finishing technique | 2 | 689 | 2 | 16.88 | 100.0% | 25.96 | 100.0% |
| S16 | Dribble manipulation | 9 | 682 | 9 | 8.81 | 100.0% | 13.55 | 100.0% |
| S17 | Handle security | 6 | 685 | 6 | 9.56 | 100.0% | 14.71 | 100.0% |
| S18 | Perimeter separation craft | 268 | 423 | 7 | 13.84 | 100.0% | 21.29 | 100.0% |
| S19 | Driving craft | 10 | 681 | 10 | 9.94 | 100.0% | 15.29 | 100.0% |
| S20 | Attack recognition | 11 | 680 | 11 | 9.88 | 100.0% | 15.20 | 100.0% |
| S21 | Post establishment / sealing | 0 | 691 | 0 | — | — | — | — |
| S22 | Post moves / counters | 148 | 543 | 0 | — | — | — | — |
| S23 | Post-specific finish execution | 0 | 691 | 0 | — | — | — | — |
| S24 | Foul-drawing craft | 0 | 691 | 0 | — | — | — | — |
| S25 | Cutting-route execution | 0 | 691 | 0 | — | — | — | — |
| S26 | Relocation / shooting-route execution | 2 | 689 | 2 | 10.65 | 100.0% | 16.39 | 100.0% |
| S27 | Screen execution | 5 | 686 | 5 | 12.73 | 100.0% | 19.59 | 100.0% |
| S28 | Screen-action recognition | 7 | 684 | 7 | 9.52 | 100.0% | 14.65 | 100.0% |
| S29 | Offensive rebound reading / pursuit technique | 0 | 691 | 0 | — | — | — | — |
| S30 | Defensive rebound reading / positioning | 0 | 691 | 0 | — | — | — | — |
| S31 | Box-out technique | 0 | 691 | 0 | — | — | — | — |
| S32 | Rebound control | 0 | 691 | 0 | — | — | — | — |
| S33 | On-ball containment technique | 11 | 680 | 11 | 10.41 | 100.0% | 16.02 | 100.0% |
| S34 | Contact resistance / leverage technique | 4 | 687 | 4 | 14.15 | 100.0% | 21.77 | 100.0% |
| S35 | Screen-navigation technique | 6 | 685 | 6 | 14.67 | 100.0% | 22.57 | 100.0% |
| S36 | Interior positioning | 4 | 687 | 4 | 6.61 | 100.0% | 10.16 | 100.0% |
| S37 | Contest technique | 3 | 688 | 3 | 10.51 | 100.0% | 16.16 | 100.0% |
| S38 | Rotation recognition | 6 | 685 | 6 | 13.23 | 100.0% | 20.35 | 100.0% |
| S39 | Off-ball coverage positioning | 6 | 685 | 6 | 12.74 | 100.0% | 19.60 | 100.0% |
| S40 | Closeout / arrival control | 1 | 690 | 1 | 12.79 | 100.0% | 19.67 | 100.0% |
| S41 | Defensive anticipation | 5 | 686 | 5 | 14.43 | 100.0% | 22.20 | 100.0% |
| S42 | On-ball steal technique | 0 | 691 | 0 | — | — | — | — |
| S43 | Passing-lane interception technique | 0 | 691 | 0 | — | — | — | — |
| S44 | Attention / responsibility execution | 3 | 688 | 3 | 12.02 | 100.0% | 18.50 | 100.0% |
| S45 | Foul-control technique | 1 | 690 | 1 | 0.08 | 100.0% | 0.12 | 100.0% |
| S46 | Defensive communication | 0 | 691 | 0 | — | — | — | — |
| F01.recognition | Connector / swing / reversal — recognition | 547 | 144 | 5 | 13.85 | 100.0% | 21.30 | 80.0% |
| F01.execution | Connector / swing / reversal — execution | 489 | 202 | 5 | 11.94 | 100.0% | 18.37 | 100.0% |
| F02.recognition | Post entry — recognition | 0 | 691 | 0 | — | — | — | — |
| F02.execution | Post entry — execution | 0 | 691 | 0 | — | — | — | — |
| F03.recognition | Pocket / roll feed — recognition | 316 | 375 | 5 | 9.59 | 100.0% | 14.75 | 100.0% |
| F03.execution | Pocket / roll feed — execution | 308 | 383 | 5 | 9.71 | 100.0% | 14.94 | 100.0% |
| F04.recognition | Lob — recognition | 2 | 689 | 2 | 12.46 | 100.0% | 19.17 | 100.0% |
| F04.execution | Lob — execution | 2 | 689 | 2 | 12.72 | 100.0% | 19.58 | 100.0% |
| F05.recognition | Short-roll playmaking — recognition | 244 | 447 | 0 | — | — | — | — |
| F05.execution | Short-roll playmaking — execution | 242 | 449 | 0 | — | — | — | — |
| F06.recognition | Drive-and-kick — recognition | 316 | 375 | 8 | 10.70 | 100.0% | 16.47 | 100.0% |
| F06.execution | Drive-and-kick — execution | 308 | 383 | 8 | 10.26 | 100.0% | 15.79 | 100.0% |
| F07.recognition | Skip / cross-court — recognition | 0 | 691 | 0 | — | — | — | — |
| F07.execution | Skip / cross-court — execution | 0 | 691 | 0 | — | — | — | — |
| F08.recognition | Post playmaking — recognition | 136 | 555 | 1 | 19.45 | 100.0% | 29.92 | 100.0% |
| F08.execution | Post playmaking — execution | 135 | 556 | 1 | 20.43 | 100.0% | 31.44 | 100.0% |
| F09.recognition | Transition / outlet / advance — recognition | 398 | 293 | 0 | — | — | — | — |
| F09.execution | Transition / outlet / advance — execution | 397 | 294 | 0 | — | — | — | — |
| T01 | Shoot / drive / pass / post / reset choices | 422 | 269 | 0 | — | — | — | — |
| T02 | Shot-location preferences | 548 | 143 | 0 | — | — | — | — |
| T03 | Shooting-mode preferences | 415 | 276 | 0 | — | — | — | — |
| T04 | Shot difficulty tolerance | 0 | 691 | 0 | — | — | — | — |
| T05 | Pace / early-attack preference | 397 | 294 | 0 | — | — | — | — |
| T06 | Dribble / possession persistence | 0 | 691 | 0 | — | — | — | — |
| T07 | Passing risk appetite | 0 | 691 | 0 | — | — | — | — |
| T08 | Offensive involvement preference | 513 | 178 | 0 | — | — | — | — |
| T09 | Cutting frequency | 362 | 329 | 0 | — | — | — | — |
| T10 | Relocation / off-ball movement frequency | 294 | 397 | 0 | — | — | — | — |
| T11 | Screen / roll / pop / slip preferences | 289 | 402 | 0 | — | — | — | — |
| T12 | Offensive crash versus retreat | 512 | 179 | 0 | — | — | — | — |
| T13 | Defensive pursuit versus box-out emphasis | 0 | 691 | 0 | — | — | — | — |
| T14 | Steal / disruption gamble frequency | 0 | 691 | 0 | — | — | — | — |
| T15 | Help commitment | 0 | 691 | 0 | — | — | — | — |
| T16 | Contest commitment / stay-down preference | 0 | 691 | 0 | — | — | — | — |
| T17 | Effort allocation | 0 | 691 | 0 | — | — | — | — |
| T18 | Contact-seeking preference | 491 | 200 | 0 | — | — | — | — |

## Ten largest technique disagreements

Sorted within technique grades only; centimeter and kilogram differences are not ranked against grades. Each explanation identifies the evidence limitation rather than treating the hand value as truth.

| Player | Input | Estimator | Hand reference | Difference | Explanation |
|---|---|---:|---:|---:|---|
| Luka Dončić | S02 Pull-up three-point execution | 64.94 | 90.50 | 25.56 | Global three-point outcomes and an uncertain live-dribble difficulty prior understate the expert assessment of elite pull-up shooting. |
| Stephen Curry | S03 Movement three-point execution | 71.25 | 94.50 | 23.25 | The broad baseline retains 65% weight; isolated technique observations are unavailable. |
| Zion Williamson | S10 Layup / close-touch execution | 67.39 | 90.00 | 22.61 | The broad baseline retains 65% weight; isolated technique observations are unavailable. |
| Nikola Jokić | S10 Layup / close-touch execution | 68.11 | 90.00 | 21.89 | The broad baseline retains 65% weight; isolated technique observations are unavailable. |
| Bam Adebayo | F01.recognition Connector / swing / reversal — recognition | 61.14 | 83.00 | 21.86 | The broad baseline retains 65% weight; isolated technique observations are unavailable. |
| Derrick White | S37 Contest technique | 63.38 | 85.00 | 21.62 | The broad baseline retains 65% weight; isolated technique observations are unavailable. |
| Karl-Anthony Towns | S09 Distance-extension technique | 62.47 | 84.00 | 21.53 | No deep-shot mechanics curve; global three-point accuracy cannot identify distance-extension technique. |
| Darius Garland | S11 Floater / short-paint touch | 64.45 | 85.00 | 20.55 | The broad baseline retains 65% weight; isolated technique observations are unavailable. |
| Dylan Harper | S10 Layup / close-touch execution | 64.56 | 85.00 | 20.44 | The broad baseline retains 65% weight; isolated technique observations are unavailable. |
| Nikola Jokić | F08.execution Post playmaking — execution | 74.07 | 94.50 | 20.43 | The broad baseline retains 65% weight; isolated technique observations are unavailable. |

## Observable tendencies and shot locations

T02 now uses player attempt counts: current completed ESPN 3PA/FGA first, then valid provider attempt-rate fields, then dated observed chart counts when no newer ratio exists. The three-point share shrinks by 100 prior field-goal attempts. Retained 2024–25 aggregate chart bins inform conditional two-point locations for matched players; their totals are reconciled, coordinates use the existing basket-relative feet grid, and two-foot bin/season uncertainty stays broad. The older chart does not count again toward a newer three-point ratio.

LT_06 efficiency and the ambiguous FREQ field are not shot-attempt frequencies. They are not used as observed location counts. Missing two-point subregions retain declared player priors. T01 action and T03 mode tags overlap and omit some alternatives; their estimates are explicitly partial proxies, with pass/reset prior mass preserved. Roll participation supports a broad T11 roll/pop proxy, and ORB% supports a broad T12 crash proxy with an explicit assumed recovery conversion, not a claim that rebounds equal crash attempts.

| Tendency | Player-evidence estimates | Priors | Evidence strength |
|---|---:|---:|---|
| T01 partial action mix | 422 | 269 | observed tag/rate with deployment and proxy uncertainty |
| T02 attempt-location mix | 548 | 143 | attempt-count constrained; two-point subregions partly prior |
| T03 shooting modes | 415 | 276 | observed tag/rate with deployment and proxy uncertainty |
| T05 transition frequency | 397 | 294 | observed tag/rate with deployment and proxy uncertainty |
| T08 possession involvement | 513 | 178 | observed tag/rate with deployment and proxy uncertainty |
| T09 cutting | 362 | 329 | observed tag/rate with deployment and proxy uncertainty |
| T10 off-ball movement tags | 294 | 397 | observed tag/rate with deployment and proxy uncertainty |
| T11 screen/roll/pop | 289 | 402 | observed tag/rate with deployment and proxy uncertainty |
| T12 offensive crash | 512 | 179 | observed tag/rate with deployment and proxy uncertainty |
| T18 contact seeking | 491 | 200 | observed tag/rate with deployment and proxy uncertainty |

Families without an observed choice denominator (risk, persistence, help, contest choice, pursuit/box-out emphasis and effort allocation) remain wide player-conditioned priors. All probability rows normalize, every input retains a value, and the source/uncertainty record says which parts are observed or inferred.

## Adapter feedback: joins and player-specific priors

Priors now respond weakly to related legacy traits, provider outcomes/workload, defensive deployment and body/age context. Every such record remains `reason: prior`, with low confidence and broad bands. `legacy_trait_prior` identifies the legacy contribution; those effective summaries are not relabeled as technique measurements. Direct statistical estimates are untouched by prior conditioning. No adapter rankings or simulation results enter these rules.

The audit cohort contains **279 players** with at least 1,000 minutes in any retained 2025–26 skill snapshot, later Crafted snapshot, or unique completed ESPN regular-season row. Taking the maximum selects the audit cohort only; source denominators are never summed. The report does not rely on a skill join to qualify a missing-skill player.

| High-minute player with missing skill row | Retained minutes | Skill snapshot | Later Crafted snapshot | ESPN ID |
|---|---:|---|---|---|
| None | — | all joined | — | — |

High-minute players missing the later Crafted snapshot: none.

**Wembanyama check:** skill snapshot joined; later Crafted snapshot joined; ESPN ID joined. His record did not fail a name/accent join. The earlier near-50 passing and shooting numbers came from the reference scale and conservative estimates, while release speed was a flat prior. No named-player override has been added.

| Requested player input | Value | Evidence label |
|---|---:|---|
| S01 Catch-and-shoot three-point execution | 57.002 | estimated |
| S02 Pull-up three-point execution | 38.429 | estimated |
| S03 Movement three-point execution | 34.946 | estimated |
| S07 Free-throw execution | 80.692 | estimated |
| S08 Release / preparation technique | 59.543 | prior |
| S09 Distance-extension technique | 49.502 | prior |
| F01.recognition Connector / swing / reversal — recognition | 51.000 | estimated |
| F01.execution Connector / swing / reversal — execution | 50.706 | estimated |

## Rotation-player spread: all 94 inputs

Population standard deviation across the audit cohort, in native units. Distribution families show every outcome separately; there is no arbitrary scalar coding of outcomes. A flag marks any component below 1 grade point, 0.5 cm/kg, or 0.01 probability. These are review flags only: no rating is changed to pass a spread threshold, and no jitter is introduced.

**0 input families have a near-zero component.** None of the approved families is flat at these declared thresholds.

| Input | Name | Players | Standard deviation (unit or outcome) | Near-zero components |
|---|---|---:|---|---|
| P01 | Height | 279 | cm: 7.9557 | — |
| P02 | Wingspan | 279 | cm: 9.7730 | — |
| P03 | Standing reach | 279 | cm: 10.7007 | — |
| P04 | Body mass | 279 | kg: 10.6698 | — |
| P05 | Acceleration / first step | 279 | grade: 4.2729 | — |
| P06 | Straight-line speed | 279 | grade: 5.3109 | — |
| P07 | Lateral mobility / change of direction | 279 | grade: 5.6389 | — |
| P08 | Functional strength | 279 | grade: 5.0684 | — |
| P09 | Physical balance / stability | 279 | grade: 4.4777 | — |
| P10 | Vertical / jump capacity | 279 | cm: 2.7098 | — |
| P11 | Conditioning | 279 | grade: 4.3044 | — |
| P12 | Recovery between efforts | 279 | grade: 2.5327 | — |
| S01 | Catch-and-shoot three-point execution | 279 | grade: 11.1181 | — |
| S02 | Pull-up three-point execution | 279 | grade: 11.1893 | — |
| S03 | Movement three-point execution | 279 | grade: 10.9274 | — |
| S04 | Catch-and-shoot midrange execution | 279 | grade: 7.2621 | — |
| S05 | Pull-up midrange execution | 279 | grade: 5.2535 | — |
| S06 | Movement midrange execution | 279 | grade: 7.4875 | — |
| S07 | Free-throw execution | 279 | grade: 6.0788 | — |
| S08 | Release / preparation technique | 279 | grade: 6.8706 | — |
| S09 | Distance-extension technique | 279 | grade: 9.8581 | — |
| S10 | Layup / close-touch execution | 279 | grade: 2.5425 | — |
| S11 | Floater / short-paint touch | 279 | grade: 4.4302 | — |
| S12 | Dunk execution | 279 | grade: 5.4207 | — |
| S13 | Aerial catch-to-finish execution | 279 | grade: 8.0056 | — |
| S14 | Receiving / catch control | 279 | grade: 4.5859 | — |
| S15 | Contact finishing technique | 279 | grade: 5.4508 | — |
| S16 | Dribble manipulation | 279 | grade: 10.6309 | — |
| S17 | Handle security | 279 | grade: 9.1717 | — |
| S18 | Perimeter separation craft | 279 | grade: 7.7227 | — |
| S19 | Driving craft | 279 | grade: 9.1497 | — |
| S20 | Attack recognition | 279 | grade: 9.5545 | — |
| S21 | Post establishment / sealing | 279 | grade: 7.1124 | — |
| S22 | Post moves / counters | 279 | grade: 3.4825 | — |
| S23 | Post-specific finish execution | 279 | grade: 4.3313 | — |
| S24 | Foul-drawing craft | 279 | grade: 5.3150 | — |
| S25 | Cutting-route execution | 279 | grade: 4.4368 | — |
| S26 | Relocation / shooting-route execution | 279 | grade: 4.7868 | — |
| S27 | Screen execution | 279 | grade: 8.2599 | — |
| S28 | Screen-action recognition | 279 | grade: 5.6927 | — |
| S29 | Offensive rebound reading / pursuit technique | 279 | grade: 10.7631 | — |
| S30 | Defensive rebound reading / positioning | 279 | grade: 9.4618 | — |
| S31 | Box-out technique | 279 | grade: 8.4825 | — |
| S32 | Rebound control | 279 | grade: 10.6740 | — |
| S33 | On-ball containment technique | 279 | grade: 5.6017 | — |
| S34 | Contact resistance / leverage technique | 279 | grade: 6.0212 | — |
| S35 | Screen-navigation technique | 279 | grade: 5.6170 | — |
| S36 | Interior positioning | 279 | grade: 9.1969 | — |
| S37 | Contest technique | 279 | grade: 10.8120 | — |
| S38 | Rotation recognition | 279 | grade: 5.2821 | — |
| S39 | Off-ball coverage positioning | 279 | grade: 5.2721 | — |
| S40 | Closeout / arrival control | 279 | grade: 5.1006 | — |
| S41 | Defensive anticipation | 279 | grade: 5.2042 | — |
| S42 | On-ball steal technique | 279 | grade: 5.7863 | — |
| S43 | Passing-lane interception technique | 279 | grade: 4.8964 | — |
| S44 | Attention / responsibility execution | 279 | grade: 5.1395 | — |
| S45 | Foul-control technique | 279 | grade: 4.9411 | — |
| S46 | Defensive communication | 279 | grade: 4.9966 | — |
| F01.recognition | Connector / swing / reversal — recognition | 279 | grade: 6.6631 | — |
| F01.execution | Connector / swing / reversal — execution | 279 | grade: 6.8611 | — |
| F02.recognition | Post entry — recognition | 279 | grade: 8.1729 | — |
| F02.execution | Post entry — execution | 279 | grade: 8.2574 | — |
| F03.recognition | Pocket / roll feed — recognition | 279 | grade: 6.7772 | — |
| F03.execution | Pocket / roll feed — execution | 279 | grade: 7.4257 | — |
| F04.recognition | Lob — recognition | 279 | grade: 8.2646 | — |
| F04.execution | Lob — execution | 279 | grade: 8.3513 | — |
| F05.recognition | Short-roll playmaking — recognition | 279 | grade: 8.3408 | — |
| F05.execution | Short-roll playmaking — execution | 279 | grade: 7.7424 | — |
| F06.recognition | Drive-and-kick — recognition | 279 | grade: 6.8943 | — |
| F06.execution | Drive-and-kick — execution | 279 | grade: 7.5261 | — |
| F07.recognition | Skip / cross-court — recognition | 279 | grade: 8.1729 | — |
| F07.execution | Skip / cross-court — execution | 279 | grade: 8.2574 | — |
| F08.recognition | Post playmaking — recognition | 279 | grade: 8.2313 | — |
| F08.execution | Post playmaking — execution | 279 | grade: 7.9617 | — |
| F09.recognition | Transition / outlet / advance — recognition | 279 | grade: 6.5181 | — |
| F09.execution | Transition / outlet / advance — execution | 279 | grade: 6.7593 | — |
| T01 | Shoot / drive / pass / post / reset choices | 279 | drive: 0.0598; pass: 0.0472; post: 0.0514; reset: 0.0276; shoot: 0.0621 | — |
| T02 | Shot-location preferences | 279 | midrange: 0.0419; rim: 0.1090; short_paint: 0.0592; three: 0.1764 | — |
| T03 | Shooting-mode preferences | 279 | catch: 0.0963; movement: 0.0790; pull_up: 0.1305 | — |
| T04 | Shot difficulty tolerance | 279 | probability: 0.0435 | — |
| T05 | Pace / early-attack preference | 279 | probability: 0.0596 | — |
| T06 | Dribble / possession persistence | 279 | probability: 0.1488 | — |
| T07 | Passing risk appetite | 279 | probability: 0.0585 | — |
| T08 | Offensive involvement preference | 279 | probability: 0.0939 | — |
| T09 | Cutting frequency | 279 | probability: 0.0779 | — |
| T10 | Relocation / off-ball movement frequency | 279 | probability: 0.0988 | — |
| T11 | Screen / roll / pop / slip preferences | 279 | pop: 0.1276; roll: 0.0633; screen: 0.0820; slip: 0.0300 | — |
| T12 | Offensive crash versus retreat | 279 | probability: 0.1478 | — |
| T13 | Defensive pursuit versus box-out emphasis | 279 | box_out: 0.0702; pursue: 0.0702 | — |
| T14 | Steal / disruption gamble frequency | 279 | probability: 0.0535 | — |
| T15 | Help commitment | 279 | probability: 0.0486 | — |
| T16 | Contest commitment / stay-down preference | 279 | conservative_contest: 0.0425; jump: 0.0627; stay_down: 0.0336 | — |
| T17 | Effort allocation | 279 | defense: 0.0644; offense: 0.0636; transition: 0.0212 | — |
| T18 | Contact-seeking preference | 279 | probability: 0.0825 | — |

<!-- E2 end generated evidence report -->
