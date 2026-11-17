# Defensive-role prototype — November 11, 2026

**Current-task checkpoint: executable offline prototype complete; input-calibration dependency remains explicit.** Do not resume completed settlement tasks. Production code, player inputs, GUI, coaches and rotations are unchanged. The parallel player-input review was not present when this evidence was completed; the coordinator has redirected research to finish it. No unsupported numerical correction was shipped. This is an implemented/tested prototype, not a new production defense engine or a claim that current player estimates are accurate.

Latest installed production remains **http://127.0.0.1:8798/**. The prototype is **not installed there**. No preview was restarted; old previews and saves were preserved. All 71 recorded pre-existing Python/backend/GUI/input hashes match the frozen reference and current loaded preview fingerprints. Existing performance improvements remain intact.

## Working implementation and meaning

- `experiments/defensive_roles/model.py`: pure, deterministic six-job estimates, explicit evidence coverage, reasons/limitations, primary/secondary suggestions, context-specific deployment and constrained lineup allocation. It is outside `src/` and no production module imports it.
- `scripts/run_defensive_role_prototype.py`: executable JSON/Markdown report for **all 691 canonical players**, four opponent contexts, five contrasting lineups, same-identity replacements, sensitivity and bounded timing/allocation observations.
- `tests/test_defensive_role_prototype.py`: **17 passing focused tests**. Reference input/backend, file manifests and evidence are in `output/defensive-role-prototype-2026-11-11/`.

Six active jobs are POA (on-ball containment), chaser (screen/cutter pursuit), wing stopper (bigger perimeter creation), helper (rotations), mobile big (aggressive screen coverage), and anchor big (deep coverage/rim protection). Low activity/sheltering is reduced exposure, with **no skill score**. BBI's public method describes jobs from deployment/matchup information; it does not establish talent, and deployment may change by season. We use its vocabulary, **not its role-lab correlations as causal simulator weights**. [BBI methodology](https://www.bball-index.com/defensive-roles/)

Every player gets all six scores; a selected label never grants ability. Imported `primary_def_role` is preserved only as an explicitly unverified source label. It is not a measured matchup share or ground truth of best job. Optional reviewed deployment notes cannot change scores. Suggested jobs are the highest estimates *within that player*, not proof the player is good at them or should perform them in a real lineup. Inferred suggestions are labeled accordingly.

Interpretive score anchors: **0 modeled inability, 25 weak, 50 functional neutral reference, 75 strong, 90 exceptional hypothesis, 100 ideal endpoint**. These are common numerical anchors, not peer percentiles, probabilities, empirically calibrated points prevented or interchangeable absolute impact between jobs. A90 anchor and90 chaser need not prevent equal points. Current production DEF is shown separately and is never replaced by a max role score.

## Transparent recipes and uncertainty

The first version deliberately uses existing inputs to expose their limits. E=effort, L=lateral agility, N=navigation, Q=scheme IQ, R=current shared effective-rim response.

| Job | Declared proxy blend | Critical channels |
|---|---|---|
| POA | .45L + .25E + .20N + .10Q | L |
| Chaser | .50N + .30L + .20E | N, L |
| Wing stopper | .35L + .35Q + .20E + .10N | L, Q |
| Helper | .45Q + .25R + .20E + .10L | Q |
| Mobile big | .40L + .25R + .25Q + .10E | L, R |
| Anchor big | .60R + .30Q + .10E | R, Q |

Each score is the lesser of its blend and its weakest critical channel +20. This prevents elite rim estimates from proving mobile containment, or excellent IQ from erasing very poor feet. The allowance and coefficients are **interpretability hypotheses**, not fitted causal estimates. The output exposes uncapped values, binding weaknesses, +10/+20/+30 cap sensitivities, and mixtures between the stated weights and equal channel weights. A binding weakness can intentionally stop a score increasing when a different skill rises; this is disclosed, not a production rim plateau.

**Weight robustness is limited:** only 348 of 691 primary suggestions stay unchanged across the stated/half-uniform/fully-uniform blends (343 change). This is a diagnostic warning against installing the suggestions as factual best jobs. The selected Wembanyama/White/Castle/Barnes/Caruso primaries remain stable in that particular test, which still does not validate them.

These choices give more weight to the actual named job, not to a player's identity or desired rank. They remain unvalidated. Current navigation/lateral/effort estimates share correlated events, impact and role priors. Scheme includes passing/general-IQ evidence. They are not independent measured containment, contact resistance, help timing or recovery range. That is why a neat six-column table is not itself accurate player calibration.

Each job reports weighted input coverage and inherited source-confidence metadata, plus **direct job measurement coverage=0**. Known model inputs are generally complete for the selected cohort, but source confidence around0.7–0.83 is not a calibrated probability the role estimate is correct. Missing traits use disclosed prior35 and confidence0; missing critical channels cap otherwise elite combinations at55. Missing data cannot count as excellent. Confidence is not multiplied into talent or converted to a stealth rating penalty.

**Rejected preliminary dependency:** the first chaser version used .25 broad stamina and made it critical. Source inspection shows stamina is inferred mainly from projected/prior minutes and movement-heavy *offense*. This penalized Caruso using a45.08 workload proxy rather than defensive pursuit evidence. Final chaser suitability uses navigation/mobility/activity, while sustained workload remains a separate future exposure question. No production stamina was changed. `original-prototype/` retains this rejected first experiment; `final/` is authoritative.

Rim already represents effective ability, including size evidence. Neither intrinsic job scoring nor anchor deployment adds another height bonus. There are no PG/SG/C bans. An optional wing-contact scenario applies a disclosed soft mismatch penalty after a four-inch gap, two percent per extra inch, capped at30%; it affects deployment only, never base skill or rim. This is an unvalidated sensitivity hypothesis, not a claim small or unusual defenders cannot succeed. Missing size is labeled unknown fit, not verified compatibility. Availability can also be supplied as an explicit hypothetical deployment factor; this does not replace production health/fatigue handling.

## Readable current-input score selection

All scores below are **provisional trait-proxy estimates**. Current DEF is the shared raw-trait reference, before save-specific health/role conditions; it is not a newly measured live-game impact. Full JSON includes all 691 players, coverage, reasons, limitations and sensitivities.

| Player | POA | Chaser | Wing | Helper | Mobile | Anchor | Current DEF | Suggested jobs |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Victor Wembanyama | 77.5 | 80.7 | 78.3 | 85.0 | 81.5 | 92.2 | 86.8 | anchor_big / helper |
| Rudy Gobert | 76.7 | 76.4 | 79.6 | 88.6 | 82.3 | 94.4 | 86.7 | anchor_big / helper |
| Derrick White | 83.6 | 83.9 | 82.5 | 75.6 | 76.3 | 67.1 | 73.8 | chaser / poa |
| Stephon Castle | 77.6 | 78.2 | 76.4 | 76.5 | 77.0 | 77.6 | 78.8 | chaser / poa |
| Scottie Barnes | 83.6 | 83.3 | 81.5 | 83.2 | 85.0 | 87.7 | 88.5 | anchor_big / mobile_big |
| Evan Mobley | 86.9 | 86.2 | 87.9 | 91.7 | 90.2 | 95.0 | 91.6 | anchor_big / helper |
| Bam Adebayo | 85.2 | 86.1 | 85.2 | 88.8 | 86.6 | 92.1 | 90.3 | anchor_big / helper |
| Alex Caruso | 92.8 | 93.6 | 91.4 | 83.3 | 81.8 | 73.0 | 81.0 | chaser / poa |
| Stephen Curry | 69.7 | 67.2 | 74.9 | 69.1 | 56.1 | 54.9 | 55.1 | wing_stopper / poa |
| Luka Dončić | 39.1 | 36.0 | 47.7 | 53.6 | 45.0 | 50.4 | 39.0 | helper / anchor_big |
| Nick Richards | 49.4 | 49.2 | 52.3 | 67.8 | 60.9 | 79.8 | 70.2 | anchor_big / helper |
| Isaiah Stewart | 60.3 | 59.6 | 63.1 | 76.0 | 70.2 | 87.7 | 76.9 | anchor_big / helper |
| Clint Capela | 52.3 | 50.7 | 55.6 | 69.8 | 65.7 | 84.0 | 71.0 | anchor_big / helper |
| Jay Huff | 31.9 | 29.4 | 38.8 | 59.2 | 48.0 | 76.6 | 57.4 | anchor_big / helper |
| Brook Lopez | 43.6 | 41.3 | 46.7 | 63.8 | 56.9 | 73.7 | 66.8 | anchor_big / helper |
| Myles Turner | 37.6 | 36.5 | 40.4 | 57.4 | 54.7 | 67.6 | 61.7 | anchor_big / helper |

Do not read this as a validated ranking. Specific warning signs remain:

- Wembanyama anchor92.2 is below Gobert94.4 and Mobley95.0. His old activity/scheme inputs and absent independent range representation still matter. Merely selecting “anchor” does not repair them.
- White exceeds Castle in every listed job except rim-heavy ones. Castle's suggested chaser over POA partly reflects correlated inputs, despite retained scouting emphasizing on-ball containment. Independent containment/navigation distinctions are still missing.
- Barnes receives anchor as his top proxy job because his current rim is high; that is not evidence he should replace a center. Curry's wing suggestion and Turner's weak mobile/anchor results likewise expose missing contact/matchup evidence and questionable scheme/activity priors.
- Richards/Stewart/Capela/Huff/Lopez/Turner still have raw rim100. Other channels differentiate these estimates, but that does **not validate** any of their input magnitudes. No automatic six-player downgrade was applied.

Those are reasons to hold production integration, not tune weights until the table matches reputations.

## Usage, opportunity and lineup constraints

For each five-player context, each player has one responsibility unit and shares across six jobs plus shelter sum to one. Opponent scenario demands total five units. The reference allocator uses deterministic exact min-cost flow over one-percent units, with fixed tie order. Fractions represent hybrid duties over time, not two simultaneous credits for the same player. The separation into exclusive buckets is bookkeeping; real help/containment actions can overlap.

The summary shows two separate outputs: a straight usage-weighted mean, and a coverage index that caps credit at demand for each job. Excess anchor supply cannot cover missing POA/chasing. Both normalize by the full five-player budget; shelter contributes no skill credit and cannot inflate OVR. Five players on easy jobs cannot look superior by dropping difficult obligations. This is a transparent constrained reference, **not a calibrated points-prevented model or proposed coach behavior**. Real low-activity assignments can have communication value that this conservative reference does not model.

Balanced demands (POA/chaser/wing/helper/mobile/anchor) are1/.7/.8/1/.6/.9 units. Movement shooting raises chasing to1.5 and lowers anchoring to.3; interior pressure uses.3 chasing/1.5 anchoring. A large-wing case raises wing duty to1.5. These are declared opponent counterfactuals, not imported observed possession frequencies or causal role-value coefficients.

| Lineup diagnostic | Balanced | Movement shooting | Interior pressure | Large-wing switching |
|---|---:|---:|---:|---:|
| White/Curry/Castle/Barnes/Gobert | 82.14 | 82.01 | 82.02 | 80.52 |
| Same four/Wembanyama | 81.67 | 81.38 | 81.58 | 79.89 |
| Five anchors: Gobert/Richards/Capela/Huff/Lopez | 65.09 | 60.75 | 69.39 | 61.54 |
| White/Curry/Castle/Caruso/Luka, no anchor | 75.29 | 76.28 | 73.80 | 74.01 |

These are reference coverage grades, not score predictions or real competitive lineups. The five-anchor group fares relatively better under interior demand and worse against movement. The perimeter group loses more under interior pressure. Replacing Gobert's availability by a hypothetical0.5 lowers the balanced index82.14→72.91, while his base scores stay fixed.

Balanced Wembanyama-lineup shares demonstrate hybrids: White100%POA; Curry80%wing/20%helper; Castle70%chaser/30%helper; Barnes40%helper/60%mobile; Wembanyama10%helper/90%anchor. Each row sums to one. This mathematically optimized allocation is not a realistic recommendation—the Curry wing assignment is another visible limitation of proxy inputs/soft physical assumptions. Five fully sheltered players score0; assigning the mixed Gobert lineup entirely to anchor produces13.74 with uncovered duties, versus82.14 when constrained allocation fills the declared demand. No max-role or duplicate credit is stacked.

The runner also replaces the same fifth player's defensive inputs while holding ID, body, teammates and context fixed, for all 16 displayed players across four contexts. These controls isolate input consequences from changing labels/size; they do not establish causal talent.

## Calibration comparison and disposition

The frozen reference preserves current backend plus compressed canonical. Three lanes remain explicit:

1. Original inputs/current engine: current shared activity/rim/DEF.
2. Trial inputs/current engine: only private proposed trait values change.
3. Trial inputs/offline prototype: independent job vector and context summaries; never applied as production DEF.

A private experiment reproduces **the older held Castle candidate**, effort79.44→85.44 and rim76.96→61.96, from the existing [decision sheet](ratings-evidence-2026-10-29/NEXT_RATING_BATCH_DECISION_SHEET.md). It is not an approved correction. Current-engine DEF changes78.762→73.317; prototype POA77.58→79.08, chaser78.21→79.41, helper76.47→73.32, anchor77.58→67.74. Every other player's complete private output is identical. This shows that correcting input shape can express containment/help differences without first changing the production engine. It does not establish that +6 effort measures containment or that61.96 is the right rim target.

**Supported for shipping now: none.** Wembanyama's already-installed rim100 is not repeated as another cosmetic patch. No evidence supports automatically cutting all six rim endpoints. Castle's paired magnitudes remain held, and generic effort is an imperfect containment surrogate. White/Barnes/Gobert and contrasts retain current inputs. The named November11 research sheet was absent at evidence completion; the coordinator has resumed that specific dependency, requiring no new human basketball decision. Consult it before any later production correction, preserve counterevidence and independently verify exact magnitudes.

No production numerical behavior changed, so new matchup simulations, salary negotiations, market searches and daily/bulk/reload campaigns were **not run**. Before/after production game/economic evidence in this pass is therefore not claimed. The71-file source/input equality and loaded-preview fingerprints prove this prototype did not alter those calculations; prior scale-pass verification remains historical evidence. If input corrections arrive later, their own fresh asks/bids/extensions, retention, core/premium/pick-investment guards, a single bounded paired game sample, cards/Finder/Wants and daily/bulk/reload checks are still required before shipping.

## Tests, overhead and ownership

Seventeen focused tests pass: anchors/bounds, missing critical inputs, monotonic components, bottlenecks, weight sensitivity, no cardio-derived intrinsic skill, physical controls/no duplicated rim size, observed-label independence, same-input determinism/RNG purity, no mutation/output alias, snapshot release, hybrid capacity, opponent/teammate changes, health separation, shelter/duplicate-credit counterexamples and invalid inputs. A five-role case checks the optimizer against all 120 possible pure assignments.

Seven short offline sweeps score all 691 players in **26.23 ms median**, range **25.72–27.08 ms**. One five-player assignment plus summary costs **0.613 ms median**, range **0.605–0.840 ms**. This is an isolated prototype cost, not a production speedup or a measured app-action regression. No production runtime imports it, so installed overhead is zero.

Separate allocation tracing streams three score sweeps without retaining outputs:192 bytes remain, peak4,772 bytes. Retaining one691-result score batch uses about4.99MB; explicitly releasing it leaves21.6KB in that tracing window. This excludes input loading and full JSON reporting; it is not whole-process RSS or a resolution of previous memory concerns. No global cache/production GC exists, frozen input objects cannot be edited, and retained output does not keep the private Player snapshot alive. The final JSON report is about6MB because it deliberately includes explanations and sensitivities; it is an offline artifact, not an app response.

## Recommendation and reproduction

**Keep roles offline for now.** The useful implemented result is a complete, explainable vector and a constrained usage reference that exposes missing inputs. It does not yet justify replacing production DEF, feeding OVR from a maximum, changing rotations or introducing coaches. Next bounded milestone: finish the player-input sheet for the named cohort, test supported corrections in the current engine first, then re-run these same controls. Only a specific residual deficiency after corrected inputs should motivate an engine change—for example independently measured containment/help/recovery inputs—rather than repurposing height or broad IQ to force ranks. Actual deployment/coach changes remain last.

From repository root, choose **new** disposable output directories:

```sh
PYTHONPATH=src:.:tests .venv/bin/python -m unittest test_defensive_role_prototype -v
PYTHONPATH=src:. .venv/bin/python scripts/run_defensive_role_prototype.py --output /tmp/defensive-roles-new
PYTHONPATH=src:. .venv/bin/python scripts/run_defensive_role_prototype.py --trial-inputs experiments/defensive_roles/castle_research_sensitivity.json --output /tmp/defensive-roles-castle-new
.venv/bin/python output/defensive-role-prototype-2026-11-11/verify.py
```

The last command only consolidates retained evidence and checks fingerprints. `--observations` accepts separately reviewed name-keyed deployment notes/jobs that never change scores. No dependency install, long-season run, preview interruption, distribution work or further production framework was added. Stop at this prototype milestone; the calibration dependency remains explicit.
