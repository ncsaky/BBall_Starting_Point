# Simulation Speed: First Verified Pass

## Results

Real `advance_save` actions, isolated exports of existing development saves, identical endpoints/seeds. The reference mode disables only this pass's optimizations. No source career was modified.

| Workload | Reference | Optimized | Time reduction |
| --- | --- | --- | --- |
| Busy day, seed 17, February 3-4 | 58.13 s | 37.60 s | 35.3% |
| Four days across October/November, seed 17 | 39.68 s | 32.11 s | 19.1% |
| Busy day, seed 29, February 3-4 | 57.97 s | 37.78 s | 34.8% |

Complete meaningful saved state matched in all three pairs, including transaction/offer ledgers, roster and contract state, game results, injuries, development and planning state. Only incidental paths, timestamps and save revisions are excluded by the established comparison helper.

The emitted animation events also matched exactly, in order: eight frames/seven games in each busy-day pair; 32 frames/28 games across the month boundary. No frontend code, animation duration, event scheduling, simulation quota, AI search breadth or acceptance policy changed.

These are single-machine samples, not a repeated isolated benchmark. The month and seed-29 optimized jobs overlapped, so their timings include contention. The exploratory initial baseline overlapped a profiler and is not used for the headline comparison. Results are not a guarantee of a uniform speedup on every computer or game phase.

## Where Time Went

A real busy-day cProfile found roughly 163 of 209 instrumented seconds in AI trade recommendation searches. It evaluated 6,300 bilateral proposals plus multi-team work. Frequently repeated costs included role ranking, roster forecasts and full team/player spatial feature expansion. The 209-second profile includes substantial profiler overhead and must NOT be compared directly to the unprofiled optimized times.

## Changes

1. Private strength forecasts can request non-spatial feature vectors. They keep every input used by the existing strength formula but do not build unused heatmap expansions. Actual games, player cards, heatmaps and normal feature-vector calls retain the full calculation by default. Full/lean player cache entries are distinct.
2. Each immutable AI market search owns bounded role and roster-forecast memo tables. Repeated player flows reuse forecasts. New searches receive new tables, so real trades, injuries, date changes and updated player data cannot reuse forecasts from an earlier search. Pick-term previews may share these player-only forecasts; pick valuations and financial/eligibility checks remain separate.
3. Candidate construction reuses its already computed chart ledger instead of calculating it twice, with an independent copy so callers cannot mutate the original report's chart.

No permanent global cache of whole leagues was added. Role memoization is capped at 4,096 entries; roster memoization at approximately 1,024, preserving small baseline entries when trimming. The existing mutation-sensitive forecast path remains available outside immutable searches.

## Verification

- 169 focused backend tests passed, including search-cache scope, roster/pick/wants rules, multi-team settlement, memory/lineup behavior, simulation consistency, plus-minus, box-score accounting and team planning.
- Real-team tests cover all 30 teams: healthy forecast rotations, all non-spatial feature values and resulting strength scores agree with the full reference calculation. Normal game calls still return spatial fields after a lean call.
- Five stream/playback tests pass. Of four additional existing GUI motion tests, two pass and two fail source-shape assertions in unchanged frontend code: one expects `season-opponent-result-header`, and one expects direct calendar assignment rather than the current merge call. These failures were not hidden or changed by this backend pass.
- Three paired real-action runs prove whole-business-state and event-stream equality. Source JSON hashes remain unchanged. This is bounded verification, not a new ten-season run or a claim that every phase is now fast.

Evidence: `output/simulation-speed-2026-10-29/comparison.json`, per-run reports/business snapshots, and `profile-before/profile.txt`.

## Reproduce

Use a new output directory for each invocation:

```sh
env PYTHONPATH=src:scripts .venv/bin/python scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/speed-check-new
```

Add `--reference-search` for the old computation path or `--profile` for instrumented attribution. Run timing comparisons sequentially without other heavy simulations. `scripts/summarize_simulation_speed.py` verifies the recorded comparison pairs before printing reductions.

## Remaining Cost

Busy market dates still perform thousands of evaluations. A later pass can prioritize salary-feasible construction and defer rejected-candidate presentation work, but must prove that doing so preserves useful facilitator searches and does not silently remove trades. Larger architectural changes, reduced animation fidelity and weakened AI decisions were not needed for this improvement.

## Performance Task 1: Separate Trade Decisions from Presentation

The follow-up keeps legality, valuation, acceptance, ranking, salary safeguards, and facilitator search in the candidate loop, while deferring full evaluation notes, trade charts, summaries, and candidate payloads until a candidate is retained or displayed. Public trade evaluation remains fully prepared by default. The trade finder and draft finder also rank compact candidates and prepare only the returned results. Multi-team facilitator probes preserve the original salary-blocking details used to form a route. Retained reports are rebuilt against their original canonical snapshot, including pending pick terms.

### Results

Unprofiled real `advance_save` actions compared the pre-edit source snapshot with the final code. The seed-17 February day was repeated; the seed-29 February day and October/November interval each had one sample.

| Workload | Pre-edit reference | Task 1 | Change |
| --- | ---: | ---: | ---: |
| February 3–4, seed 17 (median of 2) | 37.35 s | 36.40 s | 2.6% faster |
| February 3–4, seed 29 | 36.65 s | 35.50 s | 3.1% faster |
| October 28–November 1, seed 17 | 31.51 s | 32.30 s | 2.5% slower |

Timing samples are short and vary by a few percent; the month-boundary result does not show a wall-time improvement. The bounded change is most clear in presentation-call counts on the profiled seed-17 busy day:

| Presentation builder | Before | After |
| --- | ---: | ---: |
| `trade_value_breakdown` | 6,428 | 30 |
| `package_value_breakdown` | 13,368 | 76 |
| `trade_evaluation_payload` | 12,600 | 52 |
| `candidate_from_evaluation` | 6,300 | 26 |
| `evaluation_notes` | 14,176 | 119 |
| `proposal_summary` | 6,302 | 28 |

These are cProfile call counts, not timings. Profiled end-to-end time was 110.59 seconds before and 107.13 seconds after; profiler overhead is substantial, so these figures are not compared with the unprofiled wall times.

The full meaningful saved-state snapshots matched for every pair, including trade proposals, participant decisions, offers, transaction logs, and other business state. Ordered progress events matched exactly: eight frames across seven games for each February pair and 32 frames across 28 games at the month boundary. All disposable source saves remained unchanged.

The new tests cover discarded bilateral offers without presentation calls, retained charts and explanations with protected-pick terms, facilitator probes and route metadata, incoming offers, and public finder presentation compatibility. The focused run passed 104 tests. Remaining cost is concentrated in package generation, legality and acceptance evaluation, roster forecasts, and role selection; those decision paths are intentionally unchanged here.

### Evidence and Reproduction

Artifacts, including the preserved pre-edit backend source snapshot, isolated fixtures, per-run business snapshots, reports, and profiles, are in `output/trade-presentation-task-1/`. Recheck parity and call counts with:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/summarize_trade_presentation_speed.py
```

The February seed-17 source is the stable save already listed above. The seed-29 fixture is a disposable copy of it with only `meta.seed` changed to 29. The October 28 seed-17 fixture is `output/trade-presentation-task-1/fixtures/month17/trade_month.json`, republished to a disposable history sidecar from `output/simulation-memory-2026-10-24/fixtures/month-17.nbagm.json`.

Run a final-code action with a fresh disposable output directory:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/trade-presentation-task-1/reproduction-seed17
```

Run the matching pre-edit action from the preserved backend snapshot:

```sh
PYTHONPATH=output/trade-presentation-task-1/reference/src:output/trade-presentation-task-1/reference/scripts \
  .venv/bin/python output/trade-presentation-task-1/reference/scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/trade-presentation-task-1/reproduction-reference-seed17
```

Use a new `--output` path for every run. Add `--profile` for attribution; do not compare profiled seconds to unprofiled measurements.


## Performance Task 2: Reuse Within an Immutable Market Review

Task 1's compact evaluation and retained presentation behavior are preserved. `MarketReview` now owns one prepared transaction/spatial context for the league and incoming-offer searches in `queue_ai_recommendations`. It shares the existing bounded player-flow role and roster forecasts and their player/team/trait indexes. A full source-state digest, including planning, wants, health, ratings, contracts, picks, control permissions and configuration, is checked at each search boundary. In-place changes invalidate the context and rebuild indexes and strategic baselines. A new review never inherits these tables; the queue closes the review before offers are queued or transactions are settled.

Exact ordered pick terms against that immutable base can reuse annotation and entitlement results. The FIFO table holds at most 64 sparse annotation deltas, not canonical graphs or financial conclusions. Every preview still constructs its own pick structures and validates terms; nested previews cannot inherit the base's terms table. Cached annotations and roster projections are copied on return to prevent mutations leaking between proposals. Terms-specific prices, salary checks, Stepien checks, wants, strategic adjustments, pick-investment safeguards and all authoritative settlement approvals remain fresh. No RNG-dependent decisions are cached.

### Measured Results

The pre-edit backend snapshot for THIS task is `output/market-review-task-2/reference/`, with a SHA-256 manifest. It includes task 1 and all earlier optimizations. `--reference-search` is not this task's baseline. Failed setup and exploratory cache artifacts are excluded; the final evidence is in `before-*`, `after-*`, `profile-before`, `profile-after`, and `comparison.json`.

Each wall-time workload has two sequential samples per version. Values below are median seconds, with minimum–maximum in parentheses. No benchmark or profiler jobs overlapped one another. Existing preview servers were left running.

| Workload | Pre-edit median (range) | Task 2 median (range) | Median reduction |
| --- | ---: | ---: | ---: |
| February 3–4, seed 17 | 36.39 (36.35–36.43) | 35.06 (34.91–35.22) | 3.6% |
| February 3–4, seed 29 | 35.59 (35.53–35.66) | 34.51 (34.22–34.79) | 3.0% |
| October 28–November 1, seed 17 | 31.36 (30.97–31.75) | 28.04 (27.45–28.63) | 10.6% |

These bounded samples demonstrate modest busy-day gains; they do not establish a uniform season-wide improvement. Profiled attribution was 108.01 seconds before and 102.08 seconds after, including diagnostic/profiler overhead. Cumulative times overlap and must not be added or compared with the unprofiled wall times.

The bounded diagnostic probe recorded 4,262 repeated term inputs among 6,066 preview calls and 2,130 repeated player flows among 2,736 roster calls. Repeated terms alone were diagnostic evidence, not the cache key's state guarantee; production reuse requires the same review base.

| Calculation / cache evidence | Before | After |
| --- | ---: | ---: |
| Search contexts | 2 | 1 |
| Transaction-context builds, whole action | 10 | 9 |
| Strategic rotation calculations | 1,059 | 898 |
| Roster-cache hits / misses | 1,967 / 769 | 2,098 / 638 |
| Pick annotation calculations | 6,070 | 2,591 |
| Exact review pick-preview hits / misses | — | 3,478 / 2,577 |
| Pending-term preview calls | 6,066 | 6,066 |
| Package generators | 659 | 659 |
| Compact bilateral evaluations | 6,300 | 6,300 |
| Legality checks | 6,458 | 6,458 |
| Authoritative trade application calls | 5 | 5 |
| Retained chart builders | 30 | 30 |

The pick cache evicted 2,513 entries rather than growing past 64. At review close, the role, roster and pick tables contained 1,765, 606 and 64 entries, respectively, with a combined measured size of 3,781,433 bytes. The diagnostic weak-reference probe was released after close; no review graph was retained by the review object. Process peak RSS was 506,609,664 bytes before and 504,922,112 after in the profiled diagnostic pair. RSS includes the entire fixture, interpreter, diagnostics and profiler; this is not a claim of a meaningful overall memory reduction.

Package generation remains a measured bottleneck: 659 calls took 25.51 cumulative profiled seconds after this change. Pick-rule compilation still runs 3,264 times (8.76 cumulative seconds), preserving transfer-dependent validation. No broader package or strategic-result cache was added. Roster projection remains 15.33 cumulative seconds; these values overlap other profile rows.

### Verification

All six unprofiled pairs and the profiled pair have identical full meaningful business snapshots, including offers, transaction ledgers, participant decisions, rosters, contracts and picks. Ordered animation/progress events match exactly: eight frames/seven games in February, and 32 frames/28 games across the month boundary. All benchmark reports confirm source JSON unchanged. Fixtures are disposable exports; seed 29 uses the task-1 February copy with its seed changed, and the October fixture is the archived checkpoint already documented above.

Daily, bulk and midpoint export/reload paths reach the same November 1 endpoint with identical business state and the same 32 ordered events. The reload check exports on October 30, restores to a new path and reloads canonical data before continuing. `checkpoints.json` records both comparisons.

The primary focused suite passed 109 tests. The supplementary safeguard suite exercised 95 cases: 93 passed immediately; two existing roster test doubles lacked task 1's `decision_reasons` field and also failed against the preserved backend. Those test fixtures were corrected, and all 11 roster tests then passed. Thus all 204 selected cases are verified. Coverage includes identical-player/different-pick packages, protected picks, swaps, facilitator searches, independent preview mutations, roster/health/rating/contract/ownership/planning/wants/control invalidation, new review isolation, salary application, pick investment, and the existing public presentation compatibility tests. No meaningful state or event mismatch remains.

### Reproduce

Run from the repository root. The recorded sample runner is resumable and runs missing samples sequentially:

```sh
.venv/bin/python scripts/run_market_review_benchmarks.py
.venv/bin/python scripts/summarize_market_review_speed.py
```

For a fresh wall-time pair, choose unused output paths:

```sh
PYTHONPATH=output/market-review-task-2/reference/src:output/market-review-task-2/reference/scripts \
  .venv/bin/python output/market-review-task-2/reference/scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/task2-new-before
PYTHONPATH=src:scripts .venv/bin/python scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/task2-new-after
```

Use `output/trade-presentation-task-1/fixtures/seed29/trade_year.json` for seed 29. For the month case use `output/trade-presentation-task-1/fixtures/month17/trade_month.json` and `--target 2026-11-01`. Repeat sequentially with fresh output paths. Diagnostics are a separate instrumented run:

```sh
PYTHONPATH=output/market-review-task-2/reference/src:scripts \
  .venv/bin/python scripts/diagnose_market_review.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/task2-new-profile-before --profile
PYTHONPATH=src:scripts .venv/bin/python scripts/diagnose_market_review.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/task2-new-profile-after --profile
PYTHONPATH=src:scripts .venv/bin/python scripts/verify_market_review_checkpoints.py \
  --output output/task2-new-checkpoints \
  --bulk-reference output/market-review-task-2/after-month17
```

The diagnostic input sets are capped at 8,192 keys, and do not retain canonical objects. `diagnostics.json` records hit/miss counts, cache inventory, release probes and process RSS. Use the benchmark without diagnostics or `--profile` for wall timings.

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest \
  test_market_review_performance test_multi_team_trades test_trade_presentation \
  test_trade_search_performance test_trade_payloads test_trade_pick_terms test_trade_wants \
  test_trade_market_analysis test_trade_calendar test_trade_impact_stress test_draft_sources test_roster_space \
  test_pick_investment test_trade_roster test_trade_roles test_contract_protection test_team_planning \
  test_trade_salary_application test_trade_salary_boundaries test_pick_horizon test_trade_discretion test_premium_trade_returns
```

The verified development preview was refreshed after verification at `http://127.0.0.1:8780/`, using `output/market-review-task-2/preview-saves`. The previous isolated preview had no saves, active leagues or established connections. Normal save servers were not interrupted. HTTP 200 was confirmed.


## Performance Task 3: Exact Package Construction (Stage A)

**Stage A is implemented and verified.** At this stage's completion, Stage B was a design handoff because salary-aware construction needed complete target flows in the value-only package API and explicit repair records. The subsequent explicitly requested Stage B implementation is recorded separately below, with its own preserved Stage A baseline and changed-discovery audit. Stage A's exact-result claims apply only to Stage A.

### Implementation

The pre-edit backend containing tasks 1 and 2 is preserved in `output/package-search-task-3/reference/`, including a SHA-256 source manifest. This is the baseline; `--reference-search` is not used.

Within each package-generation call, buyer pick-group values, future risk, applicable protection alternatives, seller pick contributions and player-group rough values are calculated once. Elite-target quotes reuse each player group's exact ordered contribution prefix and concentration adjustment. Each seller pick contribution is still added individually, followed by concentration, preserving the old floating-point operation order rather than rearranging the sum.

`PackageShortlist` retains the exact best K unique packages by the original `(score, JSON assets, JSON terms)` rank. Its insertion and eviction rules preserve ties, later improved duplicates and the first identical tied occurrence. K remains `max(4, requested results)`. All player groups and variants are still enumerated. Hidden terms in plain-assets mode still prevent fallback when they would have made the old candidate pool nonempty. Returned pick asset dictionaries are independent between packages. The public package ledger remains compatible through `package_value_components`; no financial, valuation, premium-return, acceptance, application or animation policy changed.

Only `transactions.py` changed among existing backend files; `trade_package_search.py` is new. Tasks 1 and 2, including snapshot-based retained presentations and review-local invalidation, are preserved.

### Backend Wall Time and Memory

Each headline workload has two sequential, unprofiled samples per version. Values are median seconds, with minimum–maximum in parentheses. Benchmark and profile jobs were never overlapped with one another. Existing normal-save preview servers were left running, including their background clocks; the timing environment is not a dedicated benchmark machine.

| Workload | Task 2 reference median (range) | Stage A median (range) | Median reduction |
| --- | ---: | ---: | ---: |
| February 3–4, seed 17 | 36.09 (35.95–36.23) | 35.52 (35.00–36.05) | 1.6% |
| February 3–4, seed 29 | 34.74 (34.65–34.84) | 34.05 (32.31–35.79) | 2.0% |
| October 28–November 1, seed 17 | 27.93 (27.79–28.07) | 27.04 (26.89–27.18) | 3.2% |

These final wall-time gains are small and variable. They do **not** establish a material reduction in overall simulation waiting time. Earlier exploratory seed-17 Stage A samples were about 33 seconds; final reruns after an empty-player-group guard were 35.00–36.05 seconds. Those earlier versions remain under `early-*` and are excluded from headline comparisons. No candidate budgets, quotas, activity frequencies or asset types were reduced to manufacture a gain.

Separate instrumented/profiled attribution was 111.18 seconds before and 99.21 after. The package generator's cumulative time was 29.91 → 17.20 seconds in those instrumented runs. Do not compare these numbers with unprofiled wall time or add overlapping cumulative rows.

Single-process peak RSS in that diagnostic/profile pair was 498,581,504 → 484,278,272 bytes (498.6 → 484.3 MB). This includes the career, interpreter, profiler and diagnostic identity sets. It is not a repeated measurement or a general memory-reduction guarantee. The production selector's retained pool is bounded by K and does not keep the entire generated pool; per-call quote data and the selector expire with the generator call. No new global or persistent market cache was added.

### Counts: Same Search, Less Recalculation and Retention

The busy-day diagnostic pair records:

| Quantity | Before | Stage A |
| --- | ---: | ---: |
| Generator calls | 659 | 659 |
| Player groups | 8,947 | 8,947 |
| Pick-group variants across calls | 8,225 | 8,225 |
| Player-group / pick-group pairs visited | 147,204 | 147,204 |
| Generated value-qualified packages | 165,432 | 165,432 |
| Unique packages | 165,432 | 165,432 |
| Shortlisted packages | 6,507 | 6,507 |
| Full compact evaluations | 6,300 | 6,300 |
| Peak packages retained for ranking | 3,509 | 12 |
| Pick value calls | 362,686 | 79,164 |
| Far-future pick risk calls | 153,347 | 23,041 |
| Valuation body calls | 71,555 | 35,252 |

The last row compares the old `package_value_for_team` body with the extracted `package_value_components` body. The new public wrapper is also called 31,688 times; these wrapper calls are not additional valuation bodies and must not be added to the component count. The diagnostic collector uses exact transient identity sets to count unique generated packages; these are disabled for wall-time runs. Raw generated score streams are checked bit-for-bit in the elite fixture, including the original sum grouping.

The next measured cost is full participant evaluation: 26.35 cumulative profiled seconds after Stage A. Roster projection remains 15.94 seconds and pick-rule compilation 9.34 seconds. These costs overlap other rows. Useful salary-aware construction could address rejected proposals, but the current results are not evidence that the unimplemented Stage B is safe or faster.

### Discovery, Rights and Actual Packages

Each bounded checkpoint probe uses `simulate_ai_trades(limit=6, search_depth=2, reserve_assets=True)`, with seeds 17 and 29 on October 28 regular-season, February 3 deadline and July 1 offseason checkpoints. The ordinary seed-29 case is a disposable seed variation of the October seed-17 checkpoint; the two July cases are separate archived careers. These probes inspect the general search, not a season-long activity study.

Every ordered package query, complete visible offer and rejection-reason counter matches the preserved backend. Full per-query packages, offers and reason ledgers are in `markets-before` and `markets-stage-a`. All participants satisfy the authoritative multi-team consideration checks. Protected/swapped counts below refer to rights in retained offers; larger shortlisted variant counts are also recorded in the reports.

| Phase / seed | Direct / multi-team offers | Approved packages | Protected / swapped rights | Illegal / declined packages | Lost / gained proposals |
| --- | ---: | ---: | ---: | ---: | ---: |
| regular / 17 | 6 / 0 | 6 | 1 / 0 | 779 / 204 | 0 / 0 |
| regular / 29 | 6 / 0 | 6 | 1 / 0 | 841 / 328 | 0 / 0 |
| deadline / 17 | 6 / 0 | 6 | 3 / 1 | 1633 / 847 | 0 / 0 |
| deadline / 29 | 6 / 0 | 6 | 4 / 0 | 1821 / 973 | 0 / 0 |
| offseason / 17 | 6 / 0 | 6 | 1 / 2 | 1938 / 434 | 0 / 0 |
| offseason / 29 | 6 / 0 | 6 | 0 / 2 | 1714 / 114 | 0 / 0 |

Across these probes, 36 approved direct packages, ten protected rights and five swapped rights are preserved. No multi-team offer was retained inside these six general-search probes; that does not establish multi-team parity on its own. The real busy-day seed-17 app action separately preserves **three new incoming multi-team offers**, plus five settled bilateral trades. Seed 29 preserves three new direct incoming offers and four settled trades. The existing actual facilitator-search fixture continues to find all-party-approved routes, and tests reject a participant sending or receiving nothing.

Examples preserved exactly (quoted proposals, not claims that every offer was executed):

- Regular season: MIA's Simone Fontecchio for CLE's Nae'Qwan Tomlin.
- Deadline, seed 29: TOR's Kyle Anderson for CLE's Nae'Qwan Tomlin, Craig Porter Jr. and the 2028 CLE first, top-4 protected; TOR receives the 2030 CLE first if the protection is triggered.
- Offseason, seed 29: MEM's Bobby Portis for IND's T.J. McConnell and a 2030 first-round swap right: MEM receives the more favourable of IND/GSW, IND the less favourable.
- Real incoming facilitator offer, seed 17: CHI sends Norman Powell to GSW; GSW sends Gui Santos, its 2027 first and 2030 second to CHI, and Moses Moody to PHX; PHX sends its owned 2027 MIN first to GSW. Each participant sends and receives consideration.

The rejection ledgers include practical salary-matching tolerance, hard caps/roster limits, recent-signing restrictions, ordinary value rejection and premium-return refusal. For example, the regular seed-17 probe preserves 779 illegal and 204 declined packages; its NYK matching-tolerance issue occurs 153 times. The deadline seed-29 probe preserves 1,821 illegal and 973 declined packages; BOS matching-tolerance issues occur 278 times. Rejections were not converted into approvals to improve speed or activity.

There were no lost valid proposals to sample in Stage A: exact ordered package and complete offer comparisons produced empty lost and gained lists for every case. Stage B had not run at that point. Its subsequent implementation and proposal-by-proposal discovery audit are recorded below.

### Verification and Reproduction

All six final unprofiled app-action pairs and the instrumented/profiled pair match full meaningful business state, offers, transactions, decisions and ordered progress/animation events. Busy days match eight frames/seven games; the October–November interval matches 32 frames/28 games. Daily, bulk and October 30 midpoint export/restore/reload reach identical November 1 endpoints with all 32 events in order. No additional incidental fields were excluded beyond the established comparison helper. Source save JSON hashes remained unchanged; all work uses disposable exports.

The 215-case focused backend suite passed. The final eight package tests passed, including two further cases added afterward; 217 distinct selected cases are verified across those runs. Coverage includes frozen old/new package lists, exact score bits, randomized ties/duplicates, duplicate protection/swap variants, empty/fallback inputs, independent returned assets, legal pick-only absorption, 90/92/96 premium anchors rejecting up to eight weak depth players, salary/current and future hard-cap application checks, role/roster/planning/wants safeguards, facilitator consideration and presentation compatibility. Current supported rules contain no standalone second-apron aggregation ban; no approximate new rule was introduced in the search.

Evidence root: `output/package-search-task-3/`. `comparison.json` verifies state, package, offer, rejection and event equality before reporting numbers. `reference/source-sha256.json` and `source-after-sha256.json` identify backend sources. `early-*` samples and exploratory test output are not final evidence.

Run from the repository root. The sample runner resumes only missing final samples:

```sh
.venv/bin/python scripts/run_package_search_benchmarks.py
.venv/bin/python scripts/summarize_package_search_speed.py
```

For fresh sequential samples, choose unused output paths; repeat each command with fresh paths:

```sh
PYTHONPATH=output/package-search-task-3/reference/src:output/package-search-task-3/reference/scripts \
  .venv/bin/python output/package-search-task-3/reference/scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/task3-new-before
PYTHONPATH=src:scripts .venv/bin/python scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/task3-new-stage-a
```

Use the task-1 `fixtures/seed29/trade_year.json` for seed 29, or `fixtures/month17/trade_month.json` with target `2026-11-01` for the month case. Diagnostics and profiler attribution are separate from wall timings:

```sh
PYTHONPATH=output/package-search-task-3/reference/src:scripts \
  .venv/bin/python scripts/diagnose_package_search.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/task3-new-profile-before --profile
PYTHONPATH=src:scripts .venv/bin/python scripts/diagnose_package_search.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/task3-new-profile-stage-a --profile
PYTHONPATH=output/package-search-task-3/reference/src:scripts \
  .venv/bin/python scripts/audit_package_search_markets.py --output output/task3-new-markets-before
PYTHONPATH=src:scripts .venv/bin/python scripts/audit_package_search_markets.py \
  --output output/task3-new-markets-stage-a
PYTHONPATH=src:scripts .venv/bin/python scripts/verify_market_review_checkpoints.py \
  --output output/task3-new-checkpoints --bulk-reference output/package-search-task-3/stage-a-month17
```

The before-side counter instrumentation is an AST-instrumented copy of the preserved generator, adding loop counters and a list subclass with identical append/extend behavior. It does not alter the reference source snapshot or ranking logic. Package list/offer equality and uninstrumented action parity are checked independently.

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest \
  test_trade_package_search test_market_review_performance test_multi_team_trades test_trade_presentation \
  test_trade_search_performance test_trade_payloads test_trade_pick_terms test_trade_wants \
  test_trade_market_analysis test_trade_calendar test_trade_impact_stress test_draft_sources test_roster_space \
  test_pick_investment test_trade_roster test_trade_roles test_contract_protection test_team_planning \
  test_trade_salary_application test_trade_salary_boundaries test_pick_horizon test_trade_discretion \
  test_premium_trade_returns test_summer_trade_reviews
```

After verification, the isolated development preview was refreshed at `http://127.0.0.1:8780/` using `output/package-search-task-3/preview-saves`; HTTP 200 was confirmed. The prior isolated preview had no save files, active leagues or established connections. Normal save servers and their simulations were left running.

## Performance Task 3: Stage B Implemented

Stage B is enabled. It deliberately changes discovery while preserving search breadth settings, action frequency, market slots, participant approval standards and settlement safeguards. Busy-day state differs from Stage A; this is not an exact-result optimization. Tasks 1 and 2, Stage A's value-only public generator, public evaluation payloads and unrelated edits are preserved. Among existing backend files, only `transactions.py` and `multi_team_trades.py` changed; `trade_finance_search.py` is new. `save.py`, review invalidation, ratings, actual rotations, animation code and frontend code are unchanged.

The pre-edit reference for this implementation is `output/salary-search-stage-b/reference/`, with `source-sha256.json`. It contains completed tasks 1/2/Stage A. Do not use `--reference-search` as this baseline. `comparison.json`, `source-after-sha256.json`, source patches, market ledgers and test logs in that evidence root identify the verified result. Pilot, `pre-identity-*`, incomplete capture and initial failed test artifacts are exploratory and excluded from final measurements.

### Implementation and safety boundary

Internal callers supply actual normalized target assets through `TradeSearchIntent`; multi-asset finder requests carry all selected assets. With no intent, the public value-only generator retains Stage A's exact ordering, duplicates, ties and fallback behavior. Duplicate teammate names use actual player IDs in the financial search so the classified contract and evaluated contract agree.

Before expanding pick variants, identical ordered player movements are classified using **the existing** `trade_salary_legality` and `roster_count_issues`. Payroll totals, including unresolved values and waived obligations, roster counts, exact name indexes and eligibility sets are calculated once where review inputs are unchanged. The original payroll arithmetic and supported matching-credit, current/future hard-cap and roster helpers remain authoritative. No separate approximate financial formula or additional NBA aggregation rule was introduced. Guaranteed matching credit, guarantee dates, partial guarantees, unresolved contracts and three future seasons retain existing behavior.

Financially feasible groups fill the existing direct shortlist. Blocked salary/cap/roster groups feed a separate bounded repair shortlist and 16-directed-pair frontier. Supported matching, hard-cap and excess-roster routes receive priority over minimum-only seeds that the existing router often cannot repair. Quote score and stable seed identity guide that frontier; they never establish willingness, adequate premium return or approval. The 64-completion total and 24-per-seed budgets are unchanged. Pick ownership, protections, swaps, fallback rights, Stepien and investment remain complete-package checks. Repair-only groups avoid compiling new protection/swap grants they cannot use; previously owned complex rights and completed route terms remain supported.

In the internal AI search, fresh complete legality and the existing premium-return safeguard can reject before participant work. An actual preliminary participant rejection below the existing bounded-discretion floor, or an actual core-commitment block, stops further work on that candidate. Custom accepted thresholds below the usual floor remain supported. A per-proposal memo reuses identical deterministic pricing between that proposal's preliminary and roster passes. It does not share terms-specific financial/strategic conclusions between packages or cache decisions across proposals. Completed facilitator routes evaluate every participant fully; invalid consideration is still rejected. Public/explicit evaluation continues producing full reports. Retained presentations use task 1's evaluation snapshot and pending terms. Settlement rebuilds against current state and retains fresh authoritative approval; a stale-payroll-cache application test verifies that boundary.

The existing `MarketReview` state digest detects roster, health, ratings, contract, ownership, planning, wants and control changes at search boundaries. Its caches close before settlement. Raw financial facts are capped at 256 entries and movement classes at 2,048, clearing at the bound; no global cache or persistent career graph was added. Diagnostic counters are bounded aggregate integers, without timing measurements in saved state.

### Backend wall time and memory

Two sequential unprofiled real `advance_save` app-action samples per workload/version, using disposable exported saves. All jobs ran sequentially; existing normal preview servers and their clocks were left running. This is a bounded experiment on a shared machine, not a season-wide guarantee. Final Stage B samples were rerun after the duplicate-name identity guard.

| Workload | Stage A median seconds (range) | Stage B median seconds (range) | Reduction |
| --- | ---: | ---: | ---: |
| February 3–4, seed 17 | 34.48 (34.25–34.70) | 27.15 (27.08–27.21) | 21.3% |
| February 3–4, seed 29 | 34.63 (34.51–34.75) | 26.05 (25.59–26.52) | 24.8% |
| October 28–November 1, seed 17 | 28.65 (28.20–29.10) | 24.02 (22.69–25.34) | 16.2% |

The useful experimental 25% busy-day target was approached, not uniformly achieved. Separate profiler/diagnostic actions took 93.42 → 70.96 seconds. Their overlapping cumulative rows must not be added together or compared with the unprofiled headline wall times.

In the separate **unprofiled instrumented** pair, classification added 0.418 seconds, and participant work measured 8.533 → 6.334 seconds; total instrumented action time was 35.93 → 27.60 seconds. In the profiled pair, classification was 1.653 seconds and participant work 25.103 → 20.100 seconds. Instrumentation and profiler overhead differ, so these attribution measurements are not independent additive savings.

Profiled process peak RSS was 539.0 → 509.7 MB. The unprofiled instrumented pair was 580.8 → 577.4 MB. These are single high-water pairs including interpreter, fixture and diagnostics, not evidence of a general memory reduction. Added review caches measured 629,272 bytes at close (176 raw facts and 983 movement classes); the movement table reached its 2,048-entry bound and reset. This is close-time object size, not peak cache bytes. The weak-reference release probe passed after review close; no review graph remained retained.

### Work avoided, with physical evaluation counts

The seed-17 busy action includes both league-wide and incoming searches. Counts below come from separate bounded instrumented runs that reproduce each version's uninstrumented business state.

| Work | Stage A | Stage B |
| --- | ---: | ---: |
| Generator calls | 659 | 638 |
| Player groups enumerated | 8,947 | 8,515 |
| Pick variants across calls | 8,225 | 7,890 |
| Group/variant pairs visited | 147,204 | 138,585 |
| Value-qualified direct packages generated | 165,432 | 57,471 |
| Shortlisted direct packages | 6,507 | 3,977 |
| Compact bilateral evaluation requests | 6,300 | 3,775 |
| Candidates with every participant priced, legal bilateral | 2,938 | 1,960 |
| Candidates with every participant priced, blocked/repair route provenance | 3,490 | 94 |
| Candidates with every participant priced, unresolved | 0 | 0 |
| Candidates with every participant priced, terminally blocked | 0 | 0 |
| Total every-participant pricing, excluding presentation | 6,428 | 2,054 |
| Legal candidates stopped before pricing every participant | 0 | 1,807 |
| Actual individual-team pricing-body executions, including presentation | 14,287 | 6,073 |
| Retained chart builders | 30 | 31 |

The original profile's team-method total is 14,291: four application calls lie outside the observed participant wrapper, whose pricing-body total is 14,287. Stage B's participant wrapper sees 7,103 method calls, with 1,030 per-proposal memo hits, yielding 6,073 pricing bodies. Its profile total is 7,107 including four application calls. These are separate scopes, not conflicting counts.

“Repair route provenance” counts completed multi-team routes under the repair bucket; those routes still must be legal. It does not mean 94 illegal routes received approval. Thirty-four illegal completed routes skipped participant work. The observed busy fixture contains no unresolved cases; synthetic unresolved/manual-policy tests exercise them independently. Seven complete packages were stopped by the authoritative premium guard, and one by terminal legality. The aggregate search counter named `full_evaluations` is **emitted complete reports** (600), not physical every-participant pricing: early rejection may occur after both participants have been priced. The diagnostic observer above measures physical work and avoids exaggerating savings.

There were 9,175 classification misses and 4,758 exact movement hits across the two searches, 126,288 raw-fact hits, and 176 raw-fact misses. The repair frontier reached 16 pairs; both searches used all 64 completion attempts. Fewer generator/target visits reflect different first approvals and filled slots, not smaller configured buyer/target breadth or package limits.

### Discovery audit and concrete losses/gains

Six paired checkpoint probes cover ordinary season (October 28), deadline (February 3) and offseason (July 1), seeds 17/29, with six retained proposals per probe. Each side retained six approved direct proposals; neither side found a multi-team proposal in these six particular limited probes. The separate real incoming audit below supplies multi-team evidence. All 15 lost and all 15 gained checkpoint offers were re-evaluated authoritatively against their **original input snapshot**, including pending terms and original proposal seed/identity. All remain approved by the existing policy. Every lost bilateral is financially legal: losses are shortlist, earlier-selection/reservation or exploration displacement, not incorrect financial rejection. Full legs, terms, evaluations and attribution are in `discovery-comparison.json`.

| Checkpoint / seed | Lost / gained / unchanged | Protected rights A → B | Swap rights A → B |
| --- | ---: | ---: | ---: |
| Ordinary / 17 | 2 / 2 / 4 | 1 → 1 | 0 → 1 |
| Ordinary / 29 | 2 / 2 / 4 | 1 → 1 | 0 → 1 |
| Deadline / 17 | 2 / 2 / 4 | 3 → 2 | 1 → 1 |
| Deadline / 29 | 3 / 3 / 3 | 4 → 3 | 0 → 0 |
| Offseason / 17 | 4 / 4 / 2 | 1 → 3 | 2 → 1 |
| Offseason / 29 | 2 / 2 / 4 | 0 → 1 | 2 → 1 |

Representative previously approved losses: PHX Devin Booker for GSW Jimmy Butler III and Gui Santos (buyer exploration displaced); SAC Domantas Sabonis for SAS Jerami Grant, Steven Adams and NOP's 2028 second (still shortlisted, another package selected); WAS Khris Middleton for GSW Georges Niang, Gary Payton II and a top-four-protected 2027 first/fallback 2028 (deadline seed 29). All still pass fresh approval. These are genuine discovery losses, not invalid offers being removed.

Representative gains: UTA Jusuf Nurkić for GSW Niang, Brandon Williams and a 2029 GSW/MIN swap; CHI Norman Powell for GSW De'Anthony Melton, Brandin Podziemski, Gui Santos and a 2029 first; HOU Kevin Durant for DEN Jamal Murray and a 2031 DEN/HOU swap. Another gained offseason offer exchanges PHI Joel Embiid for BOS Paul George, Ron Harper Jr. and GSW's 2028 second. The existing premium guard approves the latter fixture, whose aged/injured Embiid has on-court value 81.37, playoff value 71.16 and health risk 13.65; this is not a healthy 92+ anchor fixture. Durant has on-court value 76.70 versus Murray's 73.02. The ledger records actual guard inputs, rather than treating rough quote totals as adequate premium returns. Separate healthy 90/92/96 tests reject accumulated weak depth up to eight players.

The real seed-17 February incoming review was captured immediately before market search, after games, on a disposable app-action copy. Reproduction includes inbox duplicate merging: Stage A adds three multi-team inbox offers; Stage B adds two multi-team plus two direct offers. All three old graphs were freshly approved against that exact snapshot. Two Norman Powell/GSW/PHX variants are lost because a different seed package is routed for the same pair; the DET Kevin Huerter graph is lost because earlier repair seeds consume the unchanged completion budget. These are explicit facilitator discovery losses. The new approved three-way Kornet route sends SAS Luke Kornet to GSW; GSW sends Niang, Dalen Terry and its 2028 first to SAS, and Moses Moody to PHX; PHX sends its 2030 first (or the owned MIN 2027 first in the alternate) to GSW. Every participant sends and receives valid consideration. Direct Middleton and Max Strus offers fill the other incoming slots. The seed-29 action changes from three direct incoming offers to two direct and one multi-team offer.

Actual settled bilateral trade counts were 5 → 5 (seed 17) and 4 → 3 (seed 29); neither side settled a multi-team trade during these one-day windows. Quotas and market slots were unchanged; one fewer settlement in seed 29 is another observed search consequence, not hidden behind proposal totals. Tests independently execute approved facilitator routes. Rejection ledgers preserve roster-plan, pick-investment, core/premium and ordinary value refusals; for example deadline seed 29 retains 129 participant pick-investment and 80 roster-plan rejection reports. Early-stopped candidates have no full report, so raw rejection-report counts are not equivalent old/new populations.

### Regression and consistency

The 261-test focused suite passed, followed by 23 package/finance tests including three additional cases: **264 distinct selected cases verified**. Coverage includes matching tolerance boundaries, tax/cap-room and pick-only absorption, guaranteed credit/dates and aggregate credits under supported rules, unresolved current/future obligations, three future hard caps, roster minimum/maximum, salary-reducing moves while over cap, protections/swaps/Stepien, independently approved facilitator repair from an illegal bilateral seed, valid consideration, premium/core/pick-investment safeguards, presentation payload equality, cache mutation isolation/invalidation, duplicate names and fresh settlement after payroll changes. The final added case exercises the financial generator itself: pick-only absorption above tax remains legal at the supported salary floor, while one cent above routes to repair. A frozen Stage A evaluator comparison verifies identical per-proposal pricing, decisions and full explanations after the local memo change. Public value-only frozen generator tests still pass. Existing simulation tests retain user-decision/deadline stops and progress behavior.

Repeated samples within Stage B have identical full meaningful saved business state and ordered events. Daily versus bulk and October 30 midpoint export/restore/reload agree at November 1, including offers, transactions and all 32 ordered frames (28 games). Busy-day repeats preserve eight ordered frames/seven games. Busy-day Stage A/B business state differs intentionally; the month fixture happens to match across versions. Source JSON hashes remained unchanged. All simulation work used disposable copies; no full-season or ten-season run was launched.

### Reproduce and remaining bottlenecks

From repository root, run samples sequentially. The resumable runner skips existing final outputs; use fresh paths for additional measurements. Do not overlap it with diagnostic/profile jobs.

```sh
.venv/bin/python scripts/run_salary_search_benchmarks.py
.venv/bin/python scripts/summarize_salary_search_speed.py

PYTHONPATH=output/salary-search-stage-b/reference/src:output/salary-search-stage-b/reference/scripts \
  .venv/bin/python output/salary-search-stage-b/reference/scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/stage-b-new-reference
PYTHONPATH=src:scripts .venv/bin/python scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/stage-b-new-current
```

Repeat with unused output paths. Seed 29 uses `output/trade-presentation-task-1/fixtures/seed29/trade_year.json`; month uses `output/trade-presentation-task-1/fixtures/month17/trade_month.json` and target `2026-11-01`. Diagnostic commands below are separate runs; omit `--profile` for the instrumented physical-count/classification-cost pair.

```sh
PYTHONPATH=output/salary-search-stage-b/reference/src:scripts \
  .venv/bin/python scripts/diagnose_salary_search.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/stage-b-new-profile-reference --profile
PYTHONPATH=src:scripts .venv/bin/python scripts/diagnose_salary_search.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/stage-b-new-profile-current --profile
PYTHONPATH=output/salary-search-stage-b/reference/src:scripts \
  .venv/bin/python scripts/audit_package_search_markets.py --output output/stage-b-new-markets-reference
PYTHONPATH=src:scripts .venv/bin/python scripts/audit_package_search_markets.py \
  --output output/stage-b-new-markets-current
PYTHONPATH=src:scripts .venv/bin/python scripts/compare_salary_search_discovery.py
PYTHONPATH=src:scripts .venv/bin/python scripts/verify_market_review_checkpoints.py \
  --output output/stage-b-new-checkpoints --bulk-reference output/salary-search-stage-b/stage-b-month17-1
```

The discovery comparator intentionally reads the fixed evidence-root market ledgers; copy new paired probe outputs into a separate evidence tree or change its BASE before comparing new probes. To reproduce the real incoming audit against its recorded exact snapshot:

```sh
PYTHONPATH=output/salary-search-stage-b/reference/src:scripts \
  .venv/bin/python scripts/audit_salary_incoming.py --version stage-a
PYTHONPATH=src:scripts .venv/bin/python scripts/audit_salary_incoming.py --version stage-b
PYTHONPATH=src:scripts .venv/bin/python scripts/compare_salary_incoming.py
```

To recapture that input, run `capture_salary_review_snapshot.py` under the Stage A PYTHONPATH with the busy seed-17 source, target February 4 and an unused `--output`; it restores its disposable interrupted copy afterward. Its output must replace the comparator's `incoming-snapshot` path to audit a newly captured input. No later roster is used to reconstruct historical explanations.

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest \
  test_salary_search_stage_b test_trade_package_search test_market_review_performance \
  test_multi_team_trades test_trade_presentation test_trade_search_performance \
  test_trade_payloads test_trade_pick_terms test_trade_wants test_trade_market_analysis \
  test_trade_calendar test_trade_impact_stress test_draft_sources test_roster_space \
  test_pick_investment test_trade_roster test_trade_roles test_contract_protection \
  test_team_planning test_trade_salary_application test_trade_salary_boundaries \
  test_pick_horizon test_trade_discretion test_premium_trade_returns test_summer_trade_reviews \
  test_simulation_progress test_simulation_consistency test_simulation_memory
```

Remaining measured bottlenecks are roster forecasts and fresh strategic/application context. In the final Stage B profile, `trade_roster_outlook` is 16.77 cumulative seconds, `roster_projection` 14.95, `build_transaction_context` 14.23, `apply_trade_to_state` 14.60 and package generation 11.83. These rows overlap and are **not additive**. Settlement's fresh checks remain intentional. This task stops here; no broader cache, search redesign or concurrency was added.

After verification, the isolated preview was refreshed at **http://127.0.0.1:8780/** with `output/salary-search-stage-b/preview-saves`; HTTP 200 was confirmed. The old isolated server had zero save JSON files, zero leagues and zero established client connections before replacement. Normal-save servers and active simulations were not interrupted. `output/salary-search-stage-b/preview.json` records the actual URL, process and save directory.

## Bounded Roster Forecast and Fresh Validation Pass

This pass preserves tasks 1/2, both package-search stages, all search budgets/order/policy and unrelated edits. It changes computation, with **exact Stage B outcome parity required**. The pre-edit backend, scripts and SHA-256 manifest are in `output/roster-forecast-pass/reference/`; `--reference-search` is not the baseline. Existing backend changes are confined to `trade_roster.py`, `transactions.py`, `save.py` and `contract_protection.py`; `roster_forecast.py` is new. Actual coaching rotations, game feature formulas, ratings/development, frontend, animations, quotas and approval rules are unchanged.

### Implemented reuse and dependency audit

1. A private `ForecastSnapshot` prepares player/team membership, ordered per-player trait rows, numeric trait values, contracts and health indexes once for a valid immutable market review. Relevant player IDs produce trial rosters in their **original league collection order**, preserving summation and tie behavior. Each trial owns copied player records. Its player index points at that trial's records, including after cuts; no stale source-player index is carried into a changed roster. The existing role assignment, 8/9/10-player rotation comparisons, center constraint and minutes-weighted team aggregation still run. Returned projection/cut data and attribute dictionaries remain independent of memo entries and authoritative state.
2. Private views share exact player-feature and attribute calculations and exact season-date windows used by cut retention/waiver costs. Feature keys retain the existing player ID, rotation priority, actual-points, exact minutes and spatial-mode inputs inside a snapshot with fixed traits, player identity/position and model metadata. Attributes are keyed by player ID and the same displayed minutes used by the authoritative calculation. A new minute allocation recomputes team-dependent weighting and any missing exact player vector; no rounded invariant is substituted into a formula. Season windows use the original schedule-derived first/last dates, including missing windows. Guaranteed, earned, injury-protected and dead money still run through the existing waiver calculation. No financial or approval conclusion is cached.

The existing review digest remains the invalidation boundary: player ownership, traits, health, contracts, plans, wants, controls, schedules and other public/private planning inputs must match. Generic mutation-sensitive projections outside that review retain their signature check and create a local snapshot for a cache miss. Fresh `build_team_strategic_states` shares one local snapshot while rebuilding **every team's** strategic baseline, not just participant teams. Bounded memo limits are 8,192 exact feature vectors, 4,096 attribute summaries and 32 season windows, with clearing at each bound. They are owned by the review or a single fresh validation call, never a global or saved career cache.

`live_roster_issues` still deep-copies the current save, overlays it, builds the complete fresh transaction context, and applies pending terms. Only then does it create a **new** forecast snapshot shared across that validation's participant/cut/investment checks. Each subsequent applied transaction gets another current-state overlay/context/snapshot. Search approvals and their memo tables are never used for settlement.

A lightweight participant-only settlement context was **not enabled**. `window_assessments` depends on all teams' strength ranks, league quality, contender mass and records; those phases affect roster-loss and acceptance decisions. Pick values depend on external teams, ownership, obligations and future conditions. Also, the save overlay writes rotation baselines/snapshots and can initialize generated health/protection inputs. Replacing its full save copy or limiting the league context without a wider dependency contract would risk stale state. This pass keeps that authoritative construction and improves the identical forecast work inside it. The existing full path remains production behavior and the frozen pre-edit implementation remains the differential reference.

### Repeated unprofiled app-action wall time

Two sequential samples per workload/version, using disposable exported saves. No benchmark/profile/test jobs competed with these samples. Existing normal-save preview servers and their clocks were left running; the machine is shared. These fresh Stage B baseline measurements, rather than timings from an earlier task, are used below.

| Workload | Pre-edit Stage B median seconds (range) | This pass median seconds (range) | Reduction |
| --- | ---: | ---: | ---: |
| February 3–4, seed 17 | 27.04 (26.41–27.67) | 22.10 (21.97–22.22) | 18.3% |
| February 3–4, seed 29 | 24.72 (24.59–24.84) | 20.51 (19.77–21.26) | 17.0% |
| October 28–November 1, seed 17 | 22.37 (22.29–22.46) | 19.96 (19.73–20.19) | 10.8% |

Every paired meaningful business snapshot matches exactly, including offers, decisions, settled transactions, explanations, injuries, development, planning and roster/contract/pick state. Each version's repeats also match. Ordered events match: eight frames/seven games in February; 32 frames/28 games at the month boundary. Original source hashes are unchanged. No discovery difference, lost/gained proposal or new incidental exclusion is introduced by this pass.

### Attribution and actual work

Separate final diagnostic/profile actions took 69.17 → 60.87 seconds, including instrumentation. The after diagnostic spends about 3.33 seconds recursively measuring cache inventory; this is diagnostic work, absent from wall samples. Profile times and overlapping cumulative rows below are not additive and must not be compared with unprofiled wall time.

| Function / physical calculation | Before | After |
| --- | ---: | ---: |
| `roster_projection` calls / cumulative profiled seconds | 2,268 / 15.26 | 2,268 / 5.96 |
| `strategic_rotation_view` calls / cumulative seconds | 861 / 13.58 | 861 / 6.06 |
| `live_roster_issues` calls / cumulative seconds | 5 / 10.40 | 5 / 8.71 |
| Full `build_transaction_context` calls / cumulative seconds | 9 / 13.70 | 9 / 10.93 |
| `apply_trade_to_state` calls / cumulative seconds | 5 / 13.84 | 5 / 12.44 |
| Attribute-summary requests | 41,283 | 41,283 |
| Attribute calculation bodies | 41,283 | 22,139 |
| Sim trait-index builds | 2,729 | 19 |
| Trait rows traversed by those sim-index builds | 8,930,415 | 196,935 |
| Season-window requests | 9,540 | 9,540 |
| Actual season-window calculation/sorts | 9,540 | 183 |
| Compact bilateral evaluation requests | 3,775 | 3,775 |
| Retained trade chart builders | 31 | 31 |

Snapshot indexing is additional work, not hidden in the sim-index row: 15 snapshots index 10,365 trait rows apiece on this fixture (155,475 additional row visits). Thus sim-index plus snapshot preparation still traverses far fewer trait rows; this does not count every other read of traits in the action. The observer's `input_rows_available` field describes input sizes, **not** actual row visits or CPU savings.

The market review records 17,248 exact feature hits / 2,675 misses, 17,408 attribute hits / 1,157 misses, and 9,159 season-window hits / six misses. All role/rotation and participant forecast request counts remain unchanged. Full context builds remain nine, including five in fresh roster settlement validation. The main copy path is deliberately retained: the scoped save/result deepcopy time inside fresh validation remains approximately 0.41 profiled seconds. Other trial player-copy work is included in total profile costs; no overall copy-time reduction is claimed.

Memory is a measured tradeoff. At review close, the new indexes/memos add **8,940,707 bytes** after excluding already-owned source player/trait/contract/health graphs. They contain 2,675 feature vectors, 1,157 attribute summaries and six season windows. Their total reachable size is 51,139,165 bytes, including shared source rows; reachable size is not incremental memory. All **15/15** snapshot weak-reference probes and both review-lifetime probes were released after close. Bound/eviction tests also pass.

Profiled process peak RSS was **506,773,504 → 571,801,600 bytes**, including recursive inventory overhead. A separate unprofiled app-action pair without inventory still increased **598,343,680 → 689,864,704 bytes** (598.3 → 689.9 MB), while reproducing each side's state/events. Thus the 8.9 MB measured cache size is not the entire process high-water cost, and this pass makes no memory-reduction claim. RSS includes export/restore, the full fixture, allocator/GC behavior and backend work; these are single memory pairs, not a universal retained-memory bound. The unprofiled memory pair took 25.02 → 20.96 seconds and is kept separate from the repeated headline wall samples.

### Exact regressions, mature checkpoint and consistency

The focused suite passed **306 tests**. A subsequently added archived-2036 case also passed, giving **307 distinct selected cases verified**. Eleven new differential/ownership tests use frozen pre-edit Stage B functions in `tests/fixtures/*roster*stage_b.py` and `trade_roster_stage_b.py`. They cover all 30 starting teams with baseline/outgoing/incoming/multiple-player flows, February checkpoint rosters with injuries and redundant centers, oversized rosters/cuts, core plans, insurance and pick-investment conclusions, exact minutes/features, independent returned data, bounded memos and release. Complete fresh strategic context matches the reference for every starting and February team. Fresh validation matches after sequential ownership/contract/health/plan/rotation changes and for real pending protected-pick/swap terms, without editing the authoritative save.

The extra 2036 case uses six generated-player team rosters and all four flow variants, with injury states, from the archived November 1, 2036 checkpoint. It **does not advance that career**. `prepare_roster_forecast_fixture.py` streams the existing 565 MB historical business snapshot into an approximately 17.8 MB roster-dependency fixture. It preserves generated players/traits/medical profiles, contracts, ownership, schedules, rotations and effective development: 73,788 hot development events are folded into archived totals in the original per-event floating-point addition order. The archived source hash remains unchanged. This is forecast equivalence on the recorded roster inputs, not a new ten-season or full mature-career app-action study.

The broader regression suite covers sequential settlements, stale ownership/proposals, guaranteed/dead salary and health changes, all-party multi-team consideration/approval, premium/core/pick-investment safeguards, human-controlled rotations and user-decision stops. Daily versus bulk and October 30 midpoint export/restore/reload reach identical November 1 meaningful state and all 32 ordered events. Production forecasts/validation show no meaningful mismatch. The failed initial reference setup lacked the schedule resource link; its disposable save was restored and the output is excluded as `incomplete-reference-setup`. Early pilot/profile artifacts are excluded from final evidence.

### Evidence, reproduction and next cost

Evidence root: `output/roster-forecast-pass/`. `comparison.json` asserts complete parity before reporting medians; `profile-final-before/after`, `roster-diagnostics.json`, `regression.txt`, `mature2036-test.txt`, fixture provenance and source patches record the verified scope.

From the repository root, run sequentially. The sample runner and profiler stages skip completed output; fresh experiments need unused output paths. The verification script runs profiles, regressions, separate unprofiled RSS samples and daily/reload checks in sequence.

```sh
.venv/bin/python scripts/prepare_roster_forecast_fixture.py
.venv/bin/python scripts/run_roster_forecast_benchmarks.py
.venv/bin/python scripts/verify_roster_forecast_pass.py
.venv/bin/python scripts/summarize_roster_forecast_speed.py
```

For a fresh wall pair, repeat each command with unused paths; do not overlap them:

```sh
PYTHONPATH=output/roster-forecast-pass/reference/src:output/roster-forecast-pass/reference/scripts \
  .venv/bin/python output/roster-forecast-pass/reference/scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/roster-new-before
PYTHONPATH=src:scripts .venv/bin/python scripts/benchmark_advance_speed.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/roster-new-after
```

Use the task-1 seed-29 fixture and month fixture already listed above for the other two workloads. Profile each version separately by invoking `scripts/diagnose_roster_forecasts.py` with the same `--save`, `--target`, unused `--output` and `--profile`, selecting the before/current backend with the corresponding PYTHONPATH. For RSS without recursive inventory overhead, use `scripts/measure_roster_forecast_memory.py` with those same arguments and omit `--profile`.

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest test_roster_forecast_performance \
  test_market_review_performance test_trade_roster test_trade_roles test_pick_investment \
  test_multi_team_trades test_contract_protection test_trade_salary_boundaries \
  test_trade_presentation test_user_rotation_roster
```

Full selected modules are recorded in `scripts/verify_roster_forecast_pass.py`. The next measured costs are package generation (11.28 cumulative profiled seconds), the retained full transaction-context builds (10.93), fresh roster validation (8.71), feature extraction (7.15), save overlays (6.37) and pending pick previews (5.63). These rows overlap. This pass stops at the demonstrated forecast reuse; no further market-policy or context-framework redesign is included.

After verification, the new isolated preview was started at **http://127.0.0.1:8781/** using `output/roster-forecast-pass/preview-saves`; HTTP 200 and its listening process were confirmed. Port 8780 now contains a playable save, so that server was left running. No existing preview or active simulation was interrupted. `output/roster-forecast-pass/preview.json` records the actual URL, process and isolation directory.

## Transaction Context Demand and Long-Lived Memory Gate

This pass preserves all prior optimizations, market policy, quotas, RNG behavior, ratings, actual rotations, animations and unrelated edits. The pre-edit roster-pass backend and source manifest are preserved in `output/context-demand-pass/reference/`. `--reference-search` is not this baseline. Only three existing backend files changed: `transactions.py`, `team_planning.py` and `app_actions.py`. No backend cache or context framework was added.

### Actual callers and consumed outputs

The initial bounded busy-day diagnostic recorded nine complete context builds, each with its call stack, exact replayable canonical input, SHA-256, output counts and component timings. The nine input states were distinct. Compressed inputs are in `attribution-before-inputs/`; the per-build ledger is `attribution-before/context-builds.json`. All calls use the literal default configuration from the pinned `transactions.py`, also copied into `default-config.json`.

| Caller | Before builds | Required outputs | Decision |
| --- | ---: | --- | --- |
| Initial plan review | 1 | Player values, all team states, front offices | Keep fresh initial construction |
| Wants refresh immediately after plan review | 1 | Same values/states, updated plans, controls | Reuse the already calculated invariant outputs |
| League/incoming market review | 1 | Values, states, front offices, trade blocks, pick context | Keep full fresh construction |
| Sequential roster settlement checks | 5 | Values, all team states, front offices and pick context | Keep every fresh build |
| Dashboard read context | 1 | All four public derived collections | Keep full construction; bound its ownership lifetime |

`context-consumers.json` records the audited groups and evidence. The observer's `observed_reads` counts are **lower bounds**: dictionary copies can escape its top-level read observer. An empty read count is not evidence that a caller needs nothing. The complete outputs of all nine captured inputs were replayed against the full fresh fallback; every field matches. A poison-list test verifies that protected-pick and swap roster validation do not consume trade-block entries.

Trade-block creation was only 0.018 seconds across all nine builds, including 0.010 seconds across five settlements. Removing it would save little while complicating completeness and pending-term preparation. No partial settlement context was enabled. Player valuation, every team's strategy and league-relative assessment, pick annotations, consideration and investment checks remain fresh before application, including after preceding trades. Save overlays and copying remain authoritative.

### Implemented changes

Planning now refreshes wants from the freshly computed values/states plus the newly written plans. The only intervening authoritative change is intent: player/trait/health/contract/record/pick inputs to those calculations are unchanged. Wants do not consume trade blocks. The reused context stays inside that synchronous refresh; `active` remains invalidated so the subsequent market search still rebuilds blocks against the new commitments. No search approval is reused for settlement, and date alone is never a reuse key.

Full league construction now computes needs/excesses only after the final league-relative phase is known. Previously it calculated preliminary lists for every team and immediately replaced them. `window_assessments` consumes strength, records and core inputs, not those lists. Small leagues with fewer than four teams preserve the original preliminary path. All final values, phases, ranks, needs, pressure and public schemas are identical. The explicit internal `_final_needs_only` switch selects this work; `full_transaction_context_reference` retains the original eager path as a fresh differential reference/fallback. Direct public team-state construction keeps its old default behavior.

The memory investigation identified an **existing unbounded dashboard read cache**, keyed by every visited career path. Its entries own a save, active universe, full derived context and rendered read payloads. The cache now keeps the two most recently used careers. Hits promote recency under the existing guard; revision/component validation and invalidation are unchanged. Evicted graphs release when no in-flight reader owns them. This bounds an existing owner rather than adding another persistent cache. No production `gc.collect`, animation change or simulation concurrency was introduced.

### Uninstrumented wall time

Two sequential real app-action samples per version/workload, using disposable exports. Diagnostic, memory and test jobs did not overlap these timing jobs. Existing preview servers were left running; this is a shared machine. Response capture keeps only an extra reference to the benchmark's already-owned result and serializes it **after** the existing timer stops.

| Workload | Pre-edit median seconds (range) | Current median seconds (range) | Median reduction |
| --- | ---: | ---: | ---: |
| February 3–4, seed 17 | 20.61 (20.45–20.78) | 20.03 (19.89–20.17) | 2.8% |
| February 3–4, seed 29 | 19.97 (19.54–20.41) | 19.55 (19.15–19.94) | 2.1% |
| October 28–November 1, seed 17 | 19.38 (19.33–19.42) | 18.41 (18.38–18.44) | 5.0% |

These are modest gains, not a claim of a large or universal reduction in waiting time. Busy-day medians improve by approximately 0.58 and 0.43 seconds; the month fixture improves by 0.96 seconds. Reduced build counts alone are not the result being claimed.

### Separate attribution

Component attribution is an independent instrumented action, without cProfile. Input snapshot serialization occurs outside the measured builder span. The rows below sum distinct sequential builder invocations for each caller; nested component rows overlap and must not be added to these totals.

| Caller | Before seconds / builds | Current seconds / builds | Measured time saved |
| --- | ---: | ---: | ---: |
| Planning and wants | 1.045 / 2 | 0.678 / 1 | 0.367 s |
| Market preparation | 0.422 / 1 | 0.399 / 1 | 0.023 s |
| Fresh settlement construction | 1.857 / 5 | 1.780 / 5 | 0.077 s |
| Dashboard construction | 0.400 / 1 | 0.408 / 1 | −0.008 s |
| All context construction | 3.724 / 9 | 3.265 / 8 | 0.459 s |

The dashboard's tiny increase is within these short diagnostic samples; no dashboard speedup is claimed. Player-valuation component time was 1.453 → 1.365 seconds; team-strategy construction 2.125 → 1.755; needs/excesses requests 540 → 240 and their nested time 1.048 → 0.780; league-relative assessments 0.0082 → 0.0081; trade blocks 0.0180 → 0.0169. These component times overlap. The before ledger separately records 21 save overlays, generally 0.15–0.25 seconds apiece, plus runtime-tree copying. Those overlays were not removed. The same five fresh sequential settlement builds remain, each against a different current state.

### Long-lived memory: retained growth found and fixed

`probe_context_action_memory.py` performs six bounded real busy-day actions in **one process**, each from an identical disposable career export. It keeps digests and bounded weak probes, not response/state/event payloads. A serial child verifies persisted meaningful state after memory sampling, so comparison copies cannot inflate the long-lived parent's graph. RSS is sampled after completion; process peak RSS and allocated Python blocks are recorded. No forced collection occurs between the six actions; a final collection is diagnostic only.

Before the fix, allocated blocks rose from 3,048,491 after action one to 7,992,790 after action six—about one million blocks per additional career. Final GC left 7,977,947 blocks. The source was strongly retained read contexts, not unreleased forecast snapshots or progress events. Current code reaches 4,040,478 blocks at action two, then stays between **4,040,608 and 4,040,704** over actions three through six. Final GC leaves 4,025,902. The read cache stays at two entries; owner inspection links the remaining current-context probe directly to `dashboard_active` in that cache. A current read context is intentionally retained; completed outer action responses/events and all sampled trial views/snapshots release before GC.

| Six distinct careers in one process | Pre-edit | Current |
| --- | ---: | ---: |
| Cached careers after action six | 6 | 2 |
| Allocated Python blocks after action six, before GC | 7,992,790 | 4,040,704 |
| Allocated blocks after final diagnostic GC | 7,977,947 | 4,025,902 |
| Final post-GC resident memory | 818.3 MB | 661.1 MB |
| Process peak across six actions | 993.4 MB | 828.6 MB |

Independent tracemalloc probes perform six real dashboard reads in one process, discarding the returned payload after each read. After diagnostic GC, pre-edit retained Python allocations grow **101.0 → 443.5 MB** across six careers. Current allocations plateau at approximately **169.6 MB** after cache warm-up; reads four through six differ by only 1,530 bytes. Most pre-edit retention originates in save runtime-tree copies (336.8 MB in the sixth-read snapshot), with additional loaded save records, materialized development and spatial data. The game cache retained those graphs; the harness did not retain their responses.

Two controls establish the boundary. Repeatedly restoring/advancing **one career path** for three actions stabilizes in both versions: final post-GC block counts are 3,037,643 before and 3,037,699 current. A read probe using the **pre-roster-pass backend** also retains one extra context per path: 100.95 → 237.96 MB across three reads, nearly identical to the first three pre-edit readings here. Thus this unbounded owner predates the roster optimization. The previous forecast snapshot release probes were valid; they did not audit the unrelated dashboard read-cache owner.

RSS is not fully explained by retained Python objects. In the revised six-action series, completion RSS varies from 562.0–707.4 MB after warm-up, and the process high-water mark still reaches 828.6 MB. The earlier isolated **598 → 690 MB peak-RSS difference is not fully attributable from these probes**; it must not be labeled a proven leak or harmless allocator behavior. What is demonstrated is the old strongly retained multi-career growth, its bounded replacement, stable retained Python allocations in these repeated workflows, and release of transient forecast/action graphs. This six-action gate is not a universal byte bound for arbitrary career sizes or a long-season study. The entry-count limit is two, not a fixed memory budget.

### Exact regression and app-action parity

**345 tests passed.** Nine new tests cover full fallback equality on every captured context input; contracts, health, ownership, plans, wants and pick changes; external-team changes to league ranks; tiny leagues; demand for final rather than discarded needs; old-versus-new planning/wants refresh; real pending protection/swap terms; unused trade blocks during fresh roster validation; and LRU eviction, revision replacement and in-flight reader ownership. Existing all-30-team and archived-2036 forecast cases, sequential/stale settlements, consideration, premium/core/pick-investment safeguards, human rotations, save recovery and decision stops also pass.

All six timing pairs match complete meaningful saved state, offers, decisions, transactions, explanations and ordered events; source saves remain unchanged. Both repeats within each version match too. Five captured before/after API-response pairs match every key/type/value after replacing only `dashboard_snapshot.revision` (the file-mtime cache token) and `result.save` (the disposable path). Other revision fields, save-status dictionaries and all public data remain compared. No additional meaningful saved-state fields were excluded. February emits eight frames/seven games; month boundary emits 32 frames/28 games. Daily/bulk and October 30 midpoint export/restore/reload reach identical November 1 state and all 32 ordered events. No meaningful mismatch remains.

### Evidence and reproduction

Evidence root: `output/context-demand-pass/`. `comparison.json` verifies timings, response/state/event parity and memory gates. It includes all raw memory series, including non-monotonic RSS readings; they were not reduced to only favorable endpoint numbers. `context-consumers.json`, per-build ledgers, compressed inputs, default configuration, response captures and test logs record the dependency audit.

Run serially from the repository root. The timing runner and control/verification scripts skip completed evidence; choose fresh output paths for new standalone samples. Do not overlap memory/tracing, profile, regression or timing jobs.

```sh
.venv/bin/python scripts/run_context_demand_benchmarks.py
.venv/bin/python scripts/verify_context_memory_gate.py
.venv/bin/python scripts/verify_context_demand_pass.py
.venv/bin/python scripts/summarize_context_demand_speed.py
```

The two main six-action memory series precede the control script and are reproduced separately with unused output paths:

```sh
PYTHONPATH=output/context-demand-pass/reference/src:scripts \
  .venv/bin/python scripts/probe_context_action_memory.py --output output/context-new-memory-before
PYTHONPATH=src:scripts .venv/bin/python scripts/probe_context_action_memory.py \
  --output output/context-new-memory-after
```

Add `--same-path --actions 3` for the one-career control. The default collects only after the final action; `--gc-each` is a separate diagnostic variant, not used for the primary series. For retained-allocation attribution, run `probe_read_context_retention.py --output UNUSED` with the before/current PYTHONPATH; use `output/roster-forecast-pass/reference/src:scripts` and `--reads 3` for the pre-roster control. None of these probes launches a full-season or ten-season advancement.

For fresh attribution, select the before/current backend using PYTHONPATH and run:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/diagnose_context_builds.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/context-new-attribution
```

For uninstrumented timings use `capture_benchmark_response.py` with the same save/target/unused output arguments; it runs the established `benchmark_advance_speed.py` timer. Use the existing task-1 seed-29 and month fixtures for the other cases. The first reference seed-17 sample predates response capture; the second supplies that workload's full response comparison. Full selected tests are listed in `verify_context_demand_pass.py`; the focused new suite is:

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest \
  test_context_demand_performance test_team_planning test_trade_wants test_save_recovery
```

Remaining measured costs include the necessary full league state/valuation construction, repeated authoritative save overlays/copying, package generation and pick previews. Fresh settlement construction alone remains about 1.78 instrumented seconds. Skipping its 0.01-second trade-block work would not materially change waiting time. This pass stops at the measured duplicate/intermediate calculation removal and the proven retention-owner fix.

The latest verified backend now runs at **http://127.0.0.1:8781/** with `output/context-demand-pass/preview-saves`; HTTP 200 and the listening process were confirmed. The previous isolated 8781 preview had no save JSON, no leagues and no established client connections before replacement. The playable 8780 preview and all other servers were left running. `output/context-demand-pass/preview.json` records the actual URL, process, isolation directory and hashes of the three changed backend sources.

## October 30: end-to-end latency investigation (no optimization)

The bounded HTTP/browser investigation is documented in [SIMULATION_LATENCY_2026_10_30.md](SIMULATION_LATENCY_2026_10_30.md), including reproduction commands, exclusive backend phases, first-use caveats and the one proposed next implementation task. Evidence is in `output/end-to-end-latency/summary.json`. Production Python and shared GUI files were unchanged; the UI chat paused its tests during measurement and was explicitly released afterward.

On the already-running clean control server, final-result receipt / controls usable were **1.65 / 2.81 seconds** for a warm user off-day, **1.54 / 2.80** for an ordinary user-game day, **18.95 / 20.53** for the busy market checkpoint (two samples), and **17.91 / 19.18** for the four-day month boundary (two samples). Busy controls ranged 20.49–20.57 seconds; month controls 19.01–19.36. First meaningful progress arrived at 0.26/0.32/0.76/3.00 seconds respectively. Native animations finished before final bytes in all clean warm cases; asynchronous computation/playback already works. The separate roughly one-second post-result control lock comes from two `team_wants` requests sharing the global busy counter, not animations. Server writes/flushes consumed only about 1–3 ms per action.

Separate attribution assigns the busy checkpoint 10.97 seconds to market work, 4.90 to settlement, 2.21 to lifecycle/games, 0.26 to persistence and 0.96 to response/dashboard preparation. These exclusive owners exclude separately measured diagnostic hashing. Nested whole-input hashes prove **ten duplicate overlays across five distinct settlements, costing 1.53 seconds**: salary, roster and entitlement checks each materialize an identical snapshot before the same trade. Successive trades differ and must remain fresh. The recommended next task is a private per-settlement materialization shared by those checks, retaining the full reference/fallback and all fresh league-relative evaluation. The demonstrated addressable cost is 1.53 seconds on this five-trade case, not the entire market phase or a promised 25% gain.

The initial browser sample had a 33.50-second receipt time and a meaningful preflight starting-lineup normalization difference. It is excluded from equivalent-state comparisons. That large first-use delay was not reproduced in the next fresh diagnostic process and remains unattributed. Both busy and both month browser states match their HTTP replays and prior verified meaningful state/full ordered events; warm off-day also matches HTTP. The ordinary game sample was not independently repeated. Original saves/backend hashes remain unchanged. No broad suite, season study, optimization, persistent cache or playback change was introduced.

## October 30: bounded bilateral settlement materialization

Implemented only the per-settlement reuse recommended above. The pre-edit backend and scripts are preserved in `output/settlement-materialization-pass/reference/`; `pre-edit.json` records hashes. Tasks 1/2, Stage A/B, roster forecasts and context-demand improvements remain in that reference. The only changed production files are `transactions.py` and `trade_roster.py`. No GUI, strategy, quota, RNG policy, animation or concurrent execution change was made.

### Ownership and normalization audit

`_BilateralSettlementMaterialization` is a private, lazy owner created after stale-asset validation for one bilateral application. It materializes the authoritative source against one deep-copied save, then shares that active universe with salary validation, fresh roster validation and entitlement validation. Each subsequent transaction creates a new owner against the preceding trade's effects. Nothing is stored in offers, responses, saves or global caches.

The original copied-save and authoritative-save calls have different effects. `ensure_generated_player_health` can write `generated_health_profiles`, `health_states` and `injury_events`; `apply_save_rotation_projection` writes `rotation_baselines` and `rotation_snapshots`. The other overlay helpers mutate the owned universe rather than additional save fields. The owner captures deep-copied changes to those five fields **before** derived checks run. Salary and roster rejection keep them private. At the old authoritative entitlement-overlay boundary, it publishes only those normalization changes. A later entitlement rejection therefore retains the same normalization effects as the old implementation; this task does not silently change rejection semantics. Tests compare complete saves, including field presence and generated injured-rookie normalization.

Fresh league-wide valuation/strategy construction remains mandatory. `live_roster_issues` still builds its full fresh context, checks current human permissions and recalculates pick investment. Pending protected/swap terms remain isolated in the existing terms view. Differential tests show salary, roster and pending-term preparation leave the shared public base unchanged; entitlement annotation uses that base, rather than a terms-enriched forecast. Actual rotations, health, contract/guarantee/dead-salary data, wants/plans and league-relative dependencies are preserved. Search approval is not reused as settlement approval.

`apply_trade_to_state(..., _full_reference=True)` retains the three-overlay path. Standalone salary/roster calls retain their original default behavior. Multi-team application returns through its existing full path before any bilateral owner is constructed. Pick-only trades retain the salary fast path and lazily materialize only when a later check needs it.

### Sequential unprofiled app-action timings

Two samples per version/workload, using `benchmark_advance_speed.py` through `capture_benchmark_response.py`, with disposable exported careers. Each pair alternates order: before/after, then after/before. Imports/source loading and export/restore precede the established timer; response serialization follows it. No profiler, attribution, memory probe or regression job competed with timing. UI and research confirmed no overlapping probes for the specific **03:37–03:43 America/Toronto** window; timings finished and the window was explicitly released by 03:42:57. Development had no blanket hold. Existing desktop applications/idle previews remained running.

| Workload | Before median seconds (range) | Current median seconds (range) | Saved seconds |
| --- | ---: | ---: | ---: |
| Feb 3–4, seed 17 | 20.66 (20.52–20.80) | 18.74 (18.49–19.00) | 1.91 / 9.3% |
| Feb 3–4, seed 29 | 19.12 (18.82–19.42) | 18.03 (17.95–18.10) | 1.10 / 5.7% |
| Oct 28–Nov 1, seed 17 | 18.31 (18.18–18.45) | 18.54 (18.39–18.68) | −0.22 / −1.2% |

Both busy-day ranges improve. The month interval has no applied trades and shows **no benefit**; its measured median is 0.22 seconds slower. These short samples do not establish a universal percentage or a month-boundary speedup. The optimization is retained for the demonstrated busy-day improvement with exact parity. These are backend app-action times, not a new browser playback study.

### Separate attribution and call counts

An independent instrumented seed-17 action records five sequential settlements. These owner durations do not overlap each other; the nested rows below overlap the owner/context totals and must not be added together.

| Measurement | Before | Current |
| --- | ---: | ---: |
| Settlement applications / fresh settlement contexts | 5 / 5 | 5 / 5 |
| Settlement save overlays | 15 | 5 |
| All action save overlays | 21 | 11 |
| All full transaction-context builds | 8 | 8 |
| Five settlement owners, seconds | 4.912 | 2.845 |
| Nested settlement overlays, seconds | 2.405 | 0.701 |
| Nested fresh settlement contexts, seconds | 1.702 | 1.610 |
| All overlays, nested seconds | 3.351 | 1.591 |
| All context construction, nested seconds | 3.131 | 3.070 |

The prior investigation's **1.53-second addressable duplicate-overlay cost** is the opportunity estimate, not the measured wall-time saving or the entire settlement phase. This independent run observes 1.70 seconds less nested overlay work and 2.07 seconds less settlement-owner time; it also avoids the second private-save deep copy. Run-to-run variation affects those attribution differences. The small fresh-context timing change is not a separate optimization claim. The uninstrumented wall savings above, including the smaller seed-29 result, are the end result being claimed.

### Memory and release gate

Four real busy-day advances per version ran sequentially in the **same process**, restoring identical disposable careers at distinct paths and discarding action results/events. There is no forced collection between actions; only the final collection is diagnostic. Read-cache ownership remains bounded to two careers. All **20/20** sampled new settlement owners and **20/20** active-graph sentinels release before GC. Sampled forecast snapshots, trial views, progress events and completed responses also release; only the existing bounded dashboard contexts remain owned.

| Whole-action memory observation | Before | Current |
| --- | ---: | ---: |
| Completion RSS, actions 1–4, MB | 459.6, 809.3, 977.4, 1237.7 | 475.7, 755.5, 952.5, 1051.8 |
| Process peak over four actions, MB | 1274.4 | 1061.4 |
| Allocated Python blocks, action 2 → 4 | 4,040,654 → 4,040,866 | 4,040,760 → 4,040,966 |
| Allocated blocks after final diagnostic GC | 4,026,034 | 4,026,133 |

Allocation counts plateau after the second read-cache entry, with a few hundred harness/report blocks. RSS **does not stabilize in this four-action series in either version** and final GC does not materially reduce it. The lower current peak is a sample observation, not a universal memory-reduction claim. The broader RSS high-water behavior remains unresolved; this evidence must not be presented as proof of harmless allocator behavior or an additional retained whole-career leak.

A separate small tracemalloc control replays one captured real settlement four times after warming immutable source/config loading, discarding its save/result each time and collecting diagnostically. Both versions retain **96, 376, 656 and 936 bytes**, consistent with the growing four-row report, rather than a retained universe. This checks allocation **sizes**, supplementing block counts and weak ownership probes. It is not a substitute for the full-action RSS series. No production GC, persistent cache or state-management framework was added.

### Exact regression and endpoints

**201 tests passed:** 112 focused settlement/salary/roster/multi-team/pick-investment/premium-return/contract/human-rotation regressions, one added pick-only protection/swap test, and 88 planning/wants/presentation/progress/consistency/retention/context regressions. Ten new tests cover the five archived real trades, sequential queue insertion/application, stale replay, injury/contract/ownership/wants/plan/dead-salary/control changes, external-team strategy changes, early rejection purity, entitlement-rejection effects, generated injured rookies, pending-term isolation, fallback routing and release. Two initial test-harness failures were corrected: sequential proposals must be inserted as the real queue inserts them, and a mock's call ledger must not retain the owner whose lifetime it observes. No production parity failure was found.

All six before/after timing pairs match meaningful saved state, proposals/offers, transactions, decisions, chart/explanation payloads and full ordered progress events. Full responses match after changing **only** `dashboard_snapshot.revision` (file revision) and `result.save` (disposable path), preserving every other key/type/value. Established business-state incidental metadata exclusions are unchanged. Both repeats within each version match too. Busy actions retain eight events/seven games; the month case retains all 32 events/28 games. Daily versus bulk and the Oct 30 midpoint export/restore/reload reach identical Nov 1 meaningful state and ordered events. Source saves remain unchanged.

### Evidence and reproduction

Evidence root: `output/settlement-materialization-pass/`. `comparison.json` verifies all timing pairs, responses, ownership, memory and checkpoint parity before reporting gains. `inputs/` contains the five pre-edit settlement inputs and canonical source; `pre-edit.json` hashes the frozen backend. The initial capture action includes gzip snapshot overhead and is **not** a timing sample. `timing-window.json` records the coordinated window and explicit release. No full-season or ten-season advancement was run.

Run serially, coordinating a new short quiet window before timings. The runners skip completed evidence. For new independent samples, pass unused output paths to the leaf scripts and preserve the recorded reference:

```sh
.venv/bin/python scripts/run_settlement_benchmarks.py
.venv/bin/python scripts/verify_settlement_materialization.py
PYTHONPATH=src:scripts .venv/bin/python scripts/verify_market_review_checkpoints.py \
  --output output/settlement-new-checkpoints \
  --bulk-reference output/settlement-materialization-pass/after-month17-1
PYTHONPATH=src:scripts .venv/bin/python scripts/summarize_settlement_materialization.py
```

The checkpoint verifier requires a fresh output directory when rerunning. To reproduce standalone before/after wall samples, choose unused paths:

```sh
PYTHONPATH=output/settlement-materialization-pass/reference/src:scripts \
  .venv/bin/python scripts/capture_benchmark_response.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/settlement-new-before
PYTHONPATH=src:scripts .venv/bin/python scripts/capture_benchmark_response.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/settlement-new-after
```

The other sources are `output/trade-presentation-task-1/fixtures/seed29/trade_year.json` with the same target, and `output/trade-presentation-task-1/fixtures/month17/trade_month.json` targeting `2026-11-01`. Repeat in reverse order. Attribution uses `diagnose_settlement_materialization.py` with the same leaf arguments, separately from wall timing. `verify_settlement_materialization.py` also runs four-action `probe_settlement_action_memory.py` series for each backend. For the traced retention control, run `probe_settlement_retention.py --output UNUSED` once with each backend PYTHONPATH. Regression module lists are recorded by the logs; the focused new suite is:

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest test_settlement_materialization
```

Remaining costs include unchanged market search (approximately 11 seconds in the preceding latency attribution), eight necessary full contexts (3.07 nested seconds here), and the five fresh settlement contexts (1.61 nested seconds). The post-result wants/control tail and the unresolved first-use/RSS observations from the latency study were not changed. This task stops at settlement-local reuse.

The verified latest backend runs at **http://127.0.0.1:8792/**, PID 47218, with `output/settlement-materialization-pass/preview-saves`. It serves a disposable copy of the verified Nov 1 endpoint. HTTP 200 and the real `dashboard_snapshot` action/date were verified; `preview.json` records the process, isolation directory and loaded-source hashes. Existing 8780/8781 previews were left running, preserving any playable saves or active sessions. Shared GUI files were not edited.

### November 13 continuation: completion audit

The settlement implementation, paired action runs, memory gate and endpoint comparisons above were already complete when this task resumed. No new optimization or production/GUI edit was made. The original timings remain historical results for the recorded source versions, not measurements of all subsequent model changes. The next measured costs and unresolved whole-action RSS behavior above remain the limits of this pass.

Fresh focused verification passes **10/10 tests** with the current backend, comparing optimized settlement against its full fresh `_full_reference=True` fallback, including exact results and complete saved effects. Two historical test assertions initially failed because `settlement-2.json.gz` is now rejected by **both** paths: `BOS: Draft spending exceeds the rotation, depth, upside, injury-cover and salary benefits of this marginal acquisition.` The tests now allow that authoritative roster veto, require its issues and unchanged save, and verify the reduced overlay count when entitlement validation is never reached. Sequential coverage still requires multiple successful settlements, a fresh owner for each attempt and owner release. Approval standards were not changed to make an archived offer execute.

A direct replay through the archived pre-edit backend still applies all five original offers. An initial attempt to run the modern owner-specific unit harness against that pre-edit API fails on missing `_full_reference`/owner interfaces; this is a harness incompatibility, not product evidence. Its log is retained separately. The supported direct replay and the current differential suite are the valid checks. Evidence: `output/settlement-materialization-pass/resume-2026-11-13/{current-tests.txt,frozen-input-replay.json}`; the initial incompatible run is `frozen-reference-tests.txt`. The pre-resumption test file is retained alongside these records.

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest test_settlement_materialization -v
```

No new wall-time campaign or quiet-window hold was needed for this completion audit. The original explicitly released timing window and original 201-test, six-pair state/response/event parity and daily/bulk/reload evidence are preserved, without claiming they were rerun against later numerical-model changes.

The earlier recorded previews were no longer listening. A new isolated current-backend preview runs at **http://127.0.0.1:8792/**, PID **46332**, using `output/settlement-materialization-pass/resume-2026-11-13/preview-saves`. The November 1 endpoint was exported/restored into this disposable directory; the source save is unchanged. Startup module/code fingerprints and authenticated HTTP verification are recorded in `preview-loaded.json` and `preview-verification.json` there. No existing process was stopped and no simulation advancement was requested. This refresh confirms the current backend's focused settlement behavior; it does not activate the separate default-off experimental kernels.

## October 30: scoped protection quotes in unchanged market searches

Implemented one exact-output optimization: **validate protected-pick terms against the full inventory, then prepare only the two pick records needed to price an independent protection option**. This removes repeated league entitlement preparation from `ai_pick_protection_options`; it does not change the market search or add a cache. The fresh pre-edit backend in `output/market-repeat-pass/reference/src/` includes every prior performance pass, settlement reuse, pre-opening career entry and v10 contract separation. `pre-edit.json` records hashes; canonical data and the baseline registry remain unchanged.

The initial bounded diagnostic recorded 1,706 `compile_pick_rules` calls costing 4.62 **profiled** seconds inside 897 protection-option queries. Compilation was building full league pick previews so the caller could read one primary pick's value. Before editing, the stated addressable estimate was roughly 1–2 wall seconds, requiring validation. Additional caching was rejected: only 297/897 protection queries repeated exactly, and duplicate inventory/package-value work was small in absolute time. The optimization instead removes unrelated preparation on both new and repeated quotes.

### Implementation and dependency boundary

`trade_pick_terms.compile_pick_rules(..., _materialize=False)` is a private opt-in that retains the complete existing ownership, collateral, lock, protection-range and structured-term validation, asset output and deterministic term IDs. Public callers keep the full view by default. The AI quote caller uses that validated result, then `_protection_quote_view` invokes the **same** `annotate_pick_obligation_context` and `pick_asset_value` functions on owned copies of the primary and fallback. No valuation formula or financial rule was duplicated.

The scoped path requires one protected term with one fallback, both physical picks present, no lock or complex annotation, and no existing obligation touching either pick. The dependency guard includes raw primary/swap/counterparty/fallback/pool/allocation/nested references, including inactive obligations and stale term-ID collisions. Connected or ambiguous cases retain the full existing preview. Swaps and actual candidate evaluation/presentation still use full views. `ai_pick_protection_options(..., _full_reference=True)` retains the complete previous quote path for differential tests. The two production changes are limited to `transactions.py` and `trade_pick_terms.py`; `production.patch` records the diff.

Quotes own two pick copies and one term, live for one call, and are never placed in a save, offer, response or global table. There is no new snapshot or persistent cache. Fresh settlement validation and league-relative strategic checks are unchanged. The full participants, premium/core/pick-investment safeguards, search breadth/order, quotas, RNG, actual rotations, animation frames and human stops remain intact. GUI and research files were not edited.

### Sequential unprofiled app-action timings

Two samples per version/workload; order before/after, then after/before. Real `advance_save` actions use exported disposable checkpoints with normal invalidation and current authoritative data. Source loading/export/restore precede the established timer. Response capture/serialization follows it. Profiling, memory gates and regression jobs ran separately. Research explicitly finished its disposable card probe before wall sampling; process observations showed idle previews and no competing simulation job. No generic UI hold or preview restart was requested. Background desktop activity remains a limitation of these short samples.

| Workload | Pre-edit median seconds (range) | Current median seconds (range) | Saved seconds |
| --- | ---: | ---: | ---: |
| Feb 3–4, seed 17 | 18.39 (18.14–18.64) | 17.21 (17.17–17.25) | 1.18 |
| Feb 3–4, seed 29 | 17.89 (17.45–18.33) | 16.69 (16.68–16.69) | 1.20 |
| Oct 28–Nov 1, seed 17 | 18.43 (18.39–18.47) | 16.30 (16.23–16.38) | 2.13 |

Each of the six pairs improves, by 0.75–2.16 seconds. These are backend wall samples, not browser/playback measurements or a promised universal percentage. `wall-window-*.json` records the observed sampling intervals; all wall sampling finished at 18:14:57 America/Toronto. There was no blanket measurement hold during development.

### Separate attribution and unchanged search work

A separately profiled seed-17 replay confirms the mechanism. Cumulative rows below overlap and **must not be added together**. Total instrumented action time was 48.37 → 46.81 seconds; neither value is compared to the unprofiled table.

| Work | Before | Current |
| --- | ---: | ---: |
| Market searches / package-generation queries | 2 / 638 | 2 / 638 |
| Protection-option queries / full rule compilations | 897 / 1,706 | 897 / 1,706 |
| Full pick-preview calls | 3,019 | 1,443 |
| New independent quotes using two owned picks | 0 | 1,576 |
| All annotation calls | 1,530 | 2,237 |
| Annotation calls over the full pick inventory | 1,530 | 661 |
| Compact evaluation snapshots / participant evaluations | 3,804 / 7,107 | 3,804 / 7,107 |
| Full fresh transaction contexts | 8 | 8 |
| Nested protection-option time, profiled seconds | 4.83 | 1.55 |
| Nested package-generation time, profiled seconds | 10.56 | 7.33 |

Total annotation calls **increase** because the existing annotator now runs on two records for the 1,576 quotes. The 661 remaining full-table calls and all validation still run. `_protection_quote_view`, including its conservative dependency guard, costs 0.49 cumulative profiled seconds. No real-case quote required fallback in this checkpoint; dedicated tests exercise the connected/ambiguous fallback. Existing preview-cache capacity remains 64; hits/misses/evictions change from 1,489/1,517/1,453 to 782/648/584 as unnecessary previews disappear. Lower call counts alone are not the speedup claim; the unprofiled wall table is.

`repeat-diagnostics.json` bounds duplicate-input bookkeeping at 4,096 keys per function. The first observer accidentally counted package-generator context identity as query equivalence; that figure is explicitly excluded, with the initial report retained separately. Package-value duplicate counts are lower bounds because their key set reaches the cap. None of these diagnostic identity keys was adopted as a production cache key.

### Exact parity, regressions and memory

**80 focused tests pass**, including six new quote tests. They cover default public compilation, full validation in terms-only mode, exact values/float bits across phases/seasons/projected slots, mutation isolation, ownership/lock/condition changes, complex/inactive/nested/ranked fallback and immediate release. Existing package-list/tie/fallback tests, Stage B salary classification, premium returns, protected/swapped terms, incoming offers and approved multi-team routes also pass. Exploratory logs retain a corrected test-only integer `.hex()` assumption and an initially mistyped test-module name; no production parity failure occurred.

All six timing pairs match complete meaningful state, proposals/offers, transactions, approvals, explanations and ordered events. Full response comparisons replace only established incidental `dashboard_snapshot.revision` and `result.save`; every other value remains compared. Repeats also match within each version. Busy days retain eight frames/seven games. The month interval retains 32 frames/28 games; daily/bulk and October 30 midpoint export/reload reach identical November 1 meaningful state and ordered events. All source manifests remain unchanged. `comparison.json` verifies these gates before reporting savings.

Three bounded busy actions per version ran in the **same process**, restoring equivalent careers at distinct paths and discarding responses/events. GC was diagnostic at the initial/final boundaries, never between actions. Retained read contexts remain bounded to two. All sampled forecast snapshots, trial views, completed responses and progress events release. For the new quote path, **768/768** sampled quote views release before GC across 4,728 quote invocations. No new cache is retained.

| Whole-action memory | Pre-edit | Current |
| --- | ---: | ---: |
| Completion RSS over actions 1–3, MB | 537.6, 708.2, 783.8 | 544.5, 677.2, 735.3 |
| Process peak RSS, MB | 826.6 | 827.7 |
| Allocated Python blocks, action 2 → 3 | 4,979,401 → 4,979,537 | 4,979,702 → 4,979,836 |

The handful of additional current blocks includes bounded weak-probe/report bookkeeping. Allocation counts plateau after the read cache fills; the sampled transient objects release. RSS still rises across this short series in both versions and the peaks are effectively unchanged. This does **not** resolve the previously reported RSS high-water behavior or prove it harmless. No production GC or cache-size increase was added to obtain the result.

### Evidence, reproduction and preview

Evidence: `output/market-repeat-pass/`, especially `comparison.json`, `profile-counts.json`, `diagnostic-before/`, `diagnostic-after/`, `response-parity.json`, `memory-before/`, `memory-after/`, `checkpoints/` and `pre-edit.json`. Benchmark/verification runners skip completed evidence. Run serially with no competing simulation job:

```sh
.venv/bin/python scripts/run_market_repeat_benchmarks.py
.venv/bin/python scripts/verify_market_repeat_pass.py
.venv/bin/python scripts/summarize_market_repeat_pass.py
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest \
  test_protection_quote_performance test_market_review_performance \
  test_trade_pick_terms test_trade_package_search test_salary_search_stage_b \
  test_premium_trade_returns test_multi_team_trades -v
```

For fresh standalone samples, use unused output paths with `capture_benchmark_response.py --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json --target 2027-02-04 --output UNUSED`, selecting `PYTHONPATH=output/market-repeat-pass/reference/src:scripts` versus `PYTHONPATH=src:scripts`. The other inputs are the existing task-1 seed-29 `trade_year.json` with the same endpoint and month-17 `trade_month.json` targeting `2026-11-01`. Use `diagnose_market_repeats.py` with those leaf arguments and `--profile` separately. `probe_market_quote_memory.py --actions 3 --output UNUSED` runs the three-action memory gate with the selected backend; `verify_market_review_checkpoints.py --bulk-reference output/market-repeat-pass/after-month17-1 --output UNUSED` checks daily/bulk/reload. No full-season or ten-season run was launched.

The remaining profile is headed by compact participant evaluation and necessary roster/role forecasts: 3,775 decision evaluations, 1,043 roster outlooks and eight fresh full contexts remain. These cumulative costs overlap; this pass does not claim an exclusive wall partition for them. The lower-payoff duplicate inventory/package-price calculations were left alone. This task stops after the scoped quote optimization.

The verified latest backend runs at **http://127.0.0.1:8795/**, PID 41738, with `output/market-repeat-pass/preview-saves`. Real HTTP dashboard verification reaches the verified November 1 endpoint. A separate disposable new-career v10 save retains the corrected Lillard card; HTTP verification confirms $13.4m / $14.1m. `preview.json` records backend hashes and the actual URL. The older 8794 contract preview and other active previews were preserved without interruption.

## October 31: request only consumed transaction features

Implemented one exact-output feature-construction pass. `build_player_asset_valuations` and `team_needs_and_excesses` now request the **existing non-spatial** player/team feature vectors. Their consumers never read `sp_off_*` or `sp_def_*` fields. The complete scalar calculation, minutes-dependent usage/scoring, offensive roles, lineup weighting, selection, summation order and rounding remain unchanged. No new cache, compiled career graph, snapshot type, production GC or cross-transaction reuse was added.

The fresh pre-edit backend is `output/feature-input-pass/reference/src/`; `pre-edit.json` records all Python backend and canonical/registry hashes. It contains every earlier optimization, scoped protection quotes, pre-opening entry and v10 contract separation. Only **`transactions.py`** changed in production; `production.patch` records the complete diff. Simulation, offense, spatial, forecast, GUI and research sources and all canonical/baseline data were preserved.

### Dependency findings before implementation

The starting profile was `output/market-repeat-pass/diagnostic-after/profile.txt`: 39,288 player-feature calls, 15,111 spatial profiles and 51,096 offensive profiles. These cumulative costs overlap. Two narrow seed-17 diagnostics, separate from wall timing, established the opportunity:

- Existing feature caches already returned 19,555 hits in snapshot-bearing contexts. Among misses, 9,080 calls shared stable trait/body/prior inputs, but their 0.84 nested seconds also included dynamic usage and other output preparation; that is not a wholly reusable budget.
- Offensive facets depend on actual numeric traits, physical attributes, position and frozen offensive priors. Within snapshots, repeated exact inputs accounted for only **0.30 nested diagnostic seconds**. Another cache/key/copy layer was not justified by that ceiling. Spatial and scalar callers also intentionally have different zero/default trait semantics, so player identity alone would be unsafe.
- Whole spatial profiles depend on role minutes, age, shot samples, trait values and offensive inputs. Team profiles additionally depend on lineup/health/weights. They must remain fresh where consumed.
- The stronger opportunity was **unused output construction**: eight valuation builds requested 5,528 full player zone expansions, while 240 team-needs calls requested another 5,885 player profiles and 240 team spatial profiles. Valuation reads only scalar features through `player_on_court_value`, development, scarcity and offensive valuation adjustment. Needs reads only named scalar thresholds and position counts. `flatten_spatial_profile` adds only the separate `sp_*` namespace, never overwriting those scalar inputs.

Before editing, the stated plausible addressable cost was roughly **1–1.5 seconds per busy action**, requiring real paired measurement. This pass reuses the already-supported lean feature path instead of speculatively caching the stable fragments.

### Implementation and full reference

`build_player_asset_valuations(..., _full_features=True)` and `team_needs_and_excesses(..., _full_features=True)` retain the prior full-feature calculation. The flag propagates through strategic-state construction. `full_transaction_context_reference` / `build_transaction_context(..., _full_reference=True)` retain eager needs and full spatial feature preparation for differential checks. All current-state valuations, league-relative ranks, plans, wants, contracts/dead salary, pick safeguards and participant approvals are still freshly calculated. Search approval is never substituted for settlement approval.

Public `sim.player_feature_vector` and `team_feature_vector` defaults remain full. Actual games, health-adjusted lineups, player cards, charts, spatial-fit calculations and actual human/AI rotations retain their existing paths. Existing full/lean cache keys remain distinct. Eight fresh transaction contexts, five sequential settlements and the entire market search still execute; no quota, order, breadth, RNG or animation change was made.

### Sequential unprofiled app-action timings

Two samples per version/workload, ordered before/after then after/before, using the normal exported disposable checkpoints and `benchmark_advance_speed.py` timer via response capture. No diagnostic, profile, memory or regression job overlapped the wall samples. No UI/research hold or server restart was requested. Background desktop load remains a limitation of short single-machine samples. All wall sampling finished at **17:33:21 America/Toronto on October 31**; timestamp records are in `wall-window-*.json`.

| Workload | Before median seconds (range) | Current median seconds (range) | Saved seconds |
| --- | ---: | ---: | ---: |
| Feb 3–4, seed 17 | 17.69 (17.683–17.699) | 16.16 (16.136–16.193) | 1.53 |
| Feb 3–4, seed 29 | 16.97 (16.908–17.036) | 15.76 (15.720–15.799) | 1.21 |
| Oct 28–Nov 1, seed 17 | 16.45 (16.445–16.452) | 15.35 (15.289–15.408) | 1.10 |

All six pairs improve, by **1.04–1.56 seconds**. These are backend app-action times, not a new browser/playback study or a guaranteed universal percentage.

### Separate attribution and call counts

The lightweight before/after diagnostic uses equivalent disposable seed-17 states. The valuation and needs owner rows below do not overlap each other; nested feature/profile rows must not be added to their owners.

| Measurement | Before | Current |
| --- | ---: | ---: |
| Eight valuation builds, owner seconds | 1.393 | 0.398 |
| 240 needs calculations, owner seconds | 0.760 | 0.239 |
| Player-feature requests in those owners | 5,528 / 3,588 | 5,528 / 3,588 |
| Valuation / needs player spatial-profile calls | 5,528 / 5,885 | 0 / 0 |
| Needs team spatial-profile calls | 240 | 0 |
| Remaining required player / team spatial profiles | 3,698 / 46 | 3,698 / 46 |
| All offensive-profile calls | 51,096 | 39,683 |

Some work moves to genuine consumers: their nested player-spatial time increases **0.187 → 0.545 seconds** because unused valuation/needs work previously warmed that cache. That row overlaps genuine team-spatial work and is not added again. The unprofiled wall results include this cost; the claim is not simply the sum of removed nested rows.

The current standalone cProfile is **`output/feature-input-pass/profile-after/profile.txt`**. It retains 39,288 player-feature requests, 3,804 evaluation snapshots, 7,107 participant evaluations, 638 package queries, 831 strategic rotation views, 1,074 role selections and eight full context builds. Reduced feature construction does not mean reduced trade exploration. The profile totals 44.06 seconds with instrumentation overhead; it is separate from the wall table and is not compared as an end-to-end speed ratio to the older wrapped profile.

### Exact outcomes, mutation checks and memory gate

**88 focused tests pass**: 13 feature/spatial tests and 75 roster/context/settlement/market-review/investment/premium/human-rotation tests. Five new tests cover no unused zone expansion, full-reference execution, bit-for-bit scalar equality across minutes/roles/zero traits/offensive priors, fresh snapshots after trait/health/rotation/prior/ownership edits, and existing full/lean cache separation. The broader checks cover all 30 starting teams, representative mature/injured/oversized/center-heavy rosters, the archived 2036 fixture without advancing it, pending protections/swaps, league-relative changes, sequential/stale settlements and authoritative-save purity. No production or test failure occurred.

All six timing pairs match meaningful saved state, offers/proposals, approvals, transactions, complete explanations and ordered progress events. Full responses replace only the established incidental `dashboard_snapshot.revision` and `result.save`; all other values remain compared. Repeats within each version match too. Busy dates retain eight frames/seven games. Daily/bulk and October 30 midpoint export/reload reach the same November 1 state and all 32 frames/28 games. Source manifests remain unchanged.

Two additional disposable **new-career v10** captures match complete meaningful saved state, payroll reports and the entire real `player_card` response. `new-career-parity.json` records the state check. The corrected Portland contract, Milwaukee reserve, pending player option, October 20 entry date and startup behavior remain intact. No existing career was migrated.

Three busy actions per backend ran in the **same process**, with equivalent restored states, normal invalidation, discarded responses/events and no GC between actions. Initial/final GC is diagnostic only. All **42/42** forecast snapshots per version, plus sampled trial views, completed responses and events release before GC. Read contexts remain bounded to two entries. Feature/attribute cache limits remain 8,192/4,096; observed peaks are **2,675/1,157 in both versions**.

| Whole-process memory | Before | Current |
| --- | ---: | ---: |
| Completion RSS, actions 1–3, MB | 538.7, 683.9, 682.1 | 549.1, 533.5, 674.2 |
| Process peak RSS, MB | 768.3 | 724.8 |
| Allocated Python blocks, action 2 → 3 | 4,980,022 → 4,980,377 | 4,646,488 → 4,646,765 |

Allocation counts plateau after warm-up, with bounded probe/report growth. The lower peak and block count are observations from this series, not a universal memory guarantee. Current RSS still jumps between the second and third actions, and final collection does not materially change it. The broader RSS high-water question remains unresolved; this evidence does not label it harmless allocator behavior or a retained career-graph leak. No new cache or production GC was introduced.

### Reproduction and verified backend

Evidence root: `output/feature-input-pass/`. `comparison.json` asserts every timing/response/event/checkpoint/memory/new-career gate before reporting savings; `feature-inputs.json`, `feature-demand.json`, `profile-counts.json`, test logs, `production.patch` and the frozen reference record attribution and scope. Initial non-keyed diagnostic timing buckets were explicitly excluded from repeated-input claims; the raw exploratory counter report is retained separately.

Run serially; the runners skip completed evidence:

```sh
.venv/bin/python scripts/run_feature_input_benchmarks.py
.venv/bin/python scripts/verify_feature_demand_pass.py
.venv/bin/python scripts/summarize_feature_demand_pass.py
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest \
  test_transaction_feature_demand test_spatial test_roster_forecast_performance \
  test_settlement_materialization test_context_demand_performance \
  test_market_review_performance test_trade_roster test_pick_investment \
  test_premium_trade_returns test_user_rotation_roster -v
```

For fresh leaf runs, select `PYTHONPATH=output/feature-input-pass/reference/src:scripts` versus `PYTHONPATH=src:scripts`, then run `capture_benchmark_response.py --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json --target 2027-02-04 --output UNUSED`. Use the existing task-1 seed-29 `trade_year.json` with the same endpoint and month-17 `trade_month.json` targeting `2026-11-01` for the other cases. Run `diagnose_feature_demand.py` with the same leaf arguments **without** profiling to reproduce caller clocks; `diagnose_feature_inputs.py` is the separate bounded dependency/repeat probe. Use `capture_benchmark_response.py --profile` separately for cProfile. `probe_feature_demand_memory.py --actions 3 --output UNUSED` reproduces the memory gate with the selected backend. `verify_market_review_checkpoints.py --bulk-reference output/feature-input-pass/after-month17-1 --output UNUSED` reproduces daily/bulk/reload. No full-season or ten-season study was launched.

The remaining profile is dominated by participant evaluation, roster outlook/rotation selection and package construction. Their cumulative timings overlap. The small remaining stable offensive-profile reuse budget was left alone; this pass stops after eliminating unused feature outputs.

The verified latest backend runs at **http://127.0.0.1:8796/**, PID 56446, with `output/feature-input-pass/preview-saves`. HTTP dashboard verification reaches the verified November 1 endpoint. A second disposable v10 career retains October 20 entry, and its complete Lillard card matches the verified capture. `preview.json` records actual URL, process and loaded-source hashes. The older 8795/8794 previews and all other active previews were left running; no GUI or active simulation was interrupted.

## October 31: residual roster/role repeat probe — no optimization retained

Finished the next bounded pass without changing production. One narrow real seed-17 action measured the remaining cache misses and dependency boundaries. It does **not** demonstrate a worthwhile new exact-result cache. No speedup is claimed, and no speculative context framework, cross-transaction reuse or rotation/search change was introduced.

Evidence is `output/role-roster-pass/`. The fresh `reference/src/` and `pre-edit.json` preserve the complete current backend, including scalar-only feature requests, protection quotes, all earlier speed fixes, October 20 startup and v10 contract separation. Every recorded Python/canonical/registry hash remains unchanged. The only additions are the external diagnostic script, evidence and these notes; GUI/research files and playable source saves were not edited.

### Probe and measured limits

`scripts/diagnose_role_roster_repeats.py` instruments only the selected roster/role/package paths. Snapshot serials distinguish all 14 fresh owners. Rotation signatures include the ordered complete normalized player records, removing only the minutes overwritten by `strategic_rotation_view`; role signatures include roster records, the actual canonical records used for attributes and priors. They are scoped by the existing immutable snapshot, not player IDs or dates alone. Signature tables are capped at 4,096 entries. The probe adds no production cache and retains no career graphs in its counters.

| Selected work | Calls / outcome | Nested diagnostic seconds |
| --- | --- | ---: |
| Empty-flow before-roster projections, batch hits | 1,023 | 0.0106 |
| Before-roster calls without a batch hit | 41: 38 compute, 3 signature-cache hits | 0.1715 |
| After-roster projections, batch hits | 646 | 0.0089 |
| After-roster calls without a batch hit | 558: 553 compute, 5 signature-cache hits | 2.0800 |
| Strategic rotation views | 831; 814 distinct snapshot/roster signatures | 2.0032 |
| Repeated rotation signatures | 17 | 0.0313 |
| Snapshot-owned role targets | 1,066; 1,049 distinct signatures | 0.9614 |
| Repeated role-target signatures | 17 | 0.0133 |
| Other role-target calls | 8 | 0.3327 |
| Destination-role cache hits | 8,939 | 0.0145 |
| Destination-role misses | 8,989 | 0.3877 |
| Destination-role calls without that cache | 37 | 0.0014 |
| Package-value components | 17,895 | 0.9101 |
| Tracked repeated package signatures | 3,777 | 0.1076 |

These rows overlap and include nested diagnostic overhead; they must not be added together or treated as uninstrumented wall savings. In particular, rotation time includes role/feature work, projections include rotation work, and package time includes destination-role work. Destination misses also include empty-player inputs that return immediately. The package signature set reaches its cap, so its repeat count is incomplete. Its key records ordered assets/outgoing flows, the strategic state, pick rows and offered swap records, but **does not prove complete swap-leaf equivalence**; those signatures are provisional observations, never an acceptance/price cache key.

The existing before-roster batch cache already handles **1,023 of 1,064** empty-flow calls. Most remaining rotation work is on a different roster or a fresh snapshot, including retained/cut membership changes. Reusing across settlement states would violate the freshness boundary. Even ideal extra rotation memoization could remove only the measured 0.031 seconds of repeated rotation work in this case; role repetition is contained in that budget. Another table/key/copy layer is not justified.

The alternatives do not establish a larger exact reuse opportunity either. The entire destination-miss path is under 0.39 nested seconds before any new key/copy cost. All package components together cost 0.91 nested seconds, while tracked repeated signatures account for only 0.108 seconds and require a further terms/leaf dependency audit before reuse. These are ceilings/observations, not promised gains. The small offensive-profile budget from the previous pass was left alone.

### Concrete remaining target and stopping boundary

The substantial remaining work is **unique** rotation calculation, not unchanged-before-roster recomputation. A concrete next algorithm experiment would be inside `save.ai_role_targets`: defer creation of a candidate assignment list/tuple until its DP score actually improves a state, preserving the current mask visitation, strict `>` tie rule and exact floating additions. The existing profile attributes only 0.850 self seconds to the entire role-target function under cProfile, so even this has limited headroom and is **not** a demonstrated one-second wall opportunity. A larger change would need new evidence on exact five-slot assignment versus the 8/9/10-player strength candidates. No such redesign or low-return tweak was begun in this pass.

### Verification and current backend

The fresh diagnostic advances only the existing February 3–4 disposable seed-17 fixture. Its complete meaningful state, full response and all eight ordered date/game events match the previously verified `output/feature-input-pass/after-seed17-1` result. Only established response metadata (`dashboard_snapshot.revision`, `result.save`) is normalized. The source manifest remains unchanged. `verification.json` records the assertions.

No production change or new owner/cache was introduced, so no new paired speedup, seed-29/month benchmark series, daily/bulk/reload suite or memory series is claimed. Those verified results for the **byte-identical** feature-input backend remain in the preceding section. Repeating them would measure unchanged code rather than validate an implementation. The diagnostic's 17.43-second total includes fingerprint/timer overhead and is not a headline wall baseline.

Reproduce the narrow probe separately from any timing or other simulation job, with an unused output directory:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/diagnose_role_roster_repeats.py \
  --save output/pick-investment-2026-10-28/stable17/saves/trade_year.json \
  --target 2027-02-04 --output output/role-roster-new-probe
```

The actual latest backend remains **http://127.0.0.1:8796/**, PID 56446. HTTP/session/status checks succeeded, and all previously recorded loaded-backend hashes still match the current files. `preview-verification.json` records that read-only verification. No server was restarted, no save action was sent to the preview and no active simulation was interrupted. This pass stops at the demonstrated lack of meaningful extra exact reuse.

## November 2: exact algorithm design checkpoint — no production change

See [SIMULATION_ALGORITHM_DESIGN_2026_11_02.md](SIMULATION_ALGORITHM_DESIGN_2026_11_02.md) and `output/algorithm-design-2026-11-02/` for disjoint real-action wall attribution, exact packed role-DP tests, and fresh-input serial versus two-worker replay experiments. Market work is 9.207 s of a 14.709 s diagnostic action; nested profile rows are not added to that partition. This is not a new uninstrumented speedup baseline.

The dense role prototype matches 49 real/synthetic cases and improves its warm-input microbenchmark by 31.6%, extrapolating to approximately **0.24 s**, not a large action reduction. Fresh 96-candidate replay medians including preparation/transfer/lifetime are **0.627 s serial versus 1.050 s two-worker**; compact trait inputs reduce payload/memory but remain **0.475 versus 0.724 s**. Repeated-job warm-cache throughput is explicitly excluded from playable-gain claims. No worker pool, native dependency, cache or production solver change was installed. The design recommends no larger production rewrite on this evidence; it gives a bounded small-solver implementation gate and the separate native-kernel/build decision needed to investigate a larger exact-output gain.

Both disposable action captures match meaningful state, complete response and all eight ordered events; 67 production/canonical hashes are unchanged. Previous verified seed-29/month/daily-bulk/reload evidence still applies to the byte-identical backend. No GUI/research files or playable saves were edited, no broad suite was rerun, and no preview was restarted. Actual latest backend remains **http://127.0.0.1:8796/**, PID 56446. Reproduction commands and experimental limitations are in the design note. The brief research probe finished before timing; the quiet measurement window is released. This checkpoint stops at the design/prototype handoff.

## November 2: isolated compiled hot-path experiment — no production integration

The approved native experiment is complete: [COMPILED_HOTPATH_EXPERIMENT_2026_11_02.md](COMPILED_HOTPATH_EXPERIMENT_2026_11_02.md), with retained C source, binary, adapter and evidence under `output/compiled-hotpath-experiment/`. An independently installed Command Line Tools compiler worked; no Xcode license/environment/dependency was changed. Only the exact five-slot DP executes natively; all features, score/minutes arithmetic, policy and safeguards remain on existing Python paths.

Three sequential disposable busy-17 app-action pairs measure **14.938 s Python → 14.530 s native median**, saving **0.408 s / 2.73%**, including per-call packing/FFI/reconstruction. Ranges: **14.937–15.090 / 14.409–14.584 s**. A separate audit measures only **0.490 s** of DP work across all 1,074 role calls; a large microbenchmark percentage cannot remove several seconds from this action. First observed library load **0.595 s** is disclosed separately; later loads are ~1 ms. This is backend app dispatch, not a new HTTP/browser/playback measurement.

Exact parity holds for 71 roster cases, 90 numeric cases with 702 prefix checks, 96 captured participants (pending terms/swaps/human cases), protected actual rotations and all seven real-action state/full-response/event comparisons. All 67 production/canonical hashes are unchanged. Native buffers release before GC; short same-process allocations plateau, without a whole-server RSS claim. UBSan passes; ASan stalls in installed runtime initialization before `main`, was stopped and remains an explicit validation gap. Intel/Windows/frozen packaging are untested.

Recommendation is **NO-GO for production native integration as the next material latency project**: this is a genuine small saving, with unresolved release-validation costs. No broader kernel was ported to inflate scope. Production, GUI/data/playable saves and preview servers remain untouched; **8796 runs the unchanged verified backend, not the experiment**. See the separate note for commands, memory figures and production approval gates. Stop at the experiment handoff.

## November 2: adjacent-review market investigation — no implementation recommended

[Cross-review evidence](CROSS_REVIEW_MARKET_EVIDENCE_2026_11_02.md), `output/cross-review-investigation/`: one disposable seed-17 February 3–5 interval traces two real reviews, 1,276 generation queries and 6,946 bilateral/multi-team evaluations. A corrected observer rerun asserts nonempty normalized directed flows; the initial faulty flow signature is excluded from repeat claims. Both runs have identical state/full response/17 ordered events and normal deadline stop. All 67 production/canonical hashes are unchanged; October 20 entry and the fresh settlement reference are preserved. No preview or production/native integration changed.

On the second date, **1,010 evaluations / 976 flow-and-terms packages** recur, costing **1.462 diagnostic seconds**. **Zero** match the conservative complete source/proposal key. Two distinct former rejections become approvals and two approvals become rejections; proposal-date personality draws and fresh state matter. Three new packages are approved after all earlier alternatives for that buyer/target failed, including Kelley-for-Niang reaching the inbox. Target blacklists and cross-date failure reuse would change behavior. Generation has 331 date-free query matches / 0.848 s, but 157 direct shortlists change; identical direct lists do not establish equivalent facilitator side outputs.

Existing legality/premium failures together cost only **0.113 s across both dates**; thousands of other failures already stop at authoritative preliminary net/core checks before roster forecasts. Same-review exact generation/evaluation duplicates provide only **0.423 / 0.339 s** raw combined ceilings before cache/copy/bookkeeping costs. No demonstrated large exact cache or earlier failure classification is recommended. Persistent negotiation memory requires a separate gameplay-policy decision with fresh alternatives and scheduled reevaluation; skipped calls are not themselves end-to-end savings. The note separates diagnostic attribution from wall baselines, documents dependencies/limits/counterexamples and gives reproduction commands. Stop at this evidence handoff.

## November 2: Team Wants post-result reads — implemented bounded context reuse

[Team Wants read report](TEAM_WANTS_READ_PERFORMANCE_2026_11_02.md), `output/team-wants-read-pass/`: `team_wants_action` reads now use the existing two-entry revision-owned dashboard/transaction context. Edit/ack paths keep fresh private validation; reads join the existing per-save lock group. Returned cached match lists are copied so callers cannot mutate later responses. No new cache, GUI, market, RNG, settlement, native or dependency change was made.

Three real HTTP samples per warm case: post-action two-read median **0.806 → 0.046 s** (ranges **0.798–0.819 / 0.042–0.049**), saving about **0.760 s of request tail**. Post-dashboard pair **0.787 → 0.040 s**. Cold contexts remain about **0.39 s**; first process read **0.647 / 0.637 s** is separate. Real ordinary-action-plus-reads median **2.257 → 1.567 s**; advancement alone did not improve. Attribution confirms post-dashboard overlays/full context builds **2 → 0**. Browser control-unlock time was not measured or claimed; duplicate frontend reads/busy sequencing remain a narrow UI-owned follow-up.

**24 tests**, **25 real-fixture full-response differential cases**, all 18 HTTP Wants responses and three real action state/full-response/ordered-event comparisons pass. Changes cover edit/reorder, stale targets/revisions, acquisitions/reminders, contracts, injury, date, planning, permissions and alternating careers. Reads preserve saved state/RNG/events. Same-process ownership stays at two entries; ten sampled roots release after revision/eviction/clear, with small warm allocation growth and no production GC. Broader RSS behavior is not declared resolved.

Only `src/nba_gm_data/app_actions.py` changes among the 67 recorded production/data files. The frozen pre-edit backend, commands, timing/memory limitations and ownership audit are retained in the report. Measurement servers were stopped. **8796 remains the pre-change loaded preview; it was not restarted.** Updated backend source was verified through the isolated HTTP servers. No playable save or shared frontend file was edited.


## November 3: latest preview integration and browser verification

[Consolidated status](PERFORMANCE_STATUS_2026_11_03.md), `output/performance-live-2026-11-03/`: existing preview **8796** was refreshed only after idle socket/thread/stack checks, keeping its binary, flags and `output/feature-input-pass/preview-saves`. Actual loaded latest-source PID is **85369**; startup code fingerprints, unchanged backend/GUI source manifests and served GUI hashes are retained. It includes Team Wants context reuse; native experiments remain uninstalled. Other previews, active simulations and playable source saves were preserved. No production or GUI file changed in this integration pass.

Native current-browser streaming/playback: two ordinary game-day samples receive final bytes at **1.353–1.610 s**, controls usable **1.582–1.859 s**; two busy seed-17 samples at **15.257–16.308 s**, controls **15.513–16.578 s**. Busy medians are **15.782 / 16.046 s**. Post-result Wants pairs span **47–50 / 70–77 ms**. Both complete game/busy repeats match state/full response/ordered events; busy also matches the verified feature-input reference exactly. The native cutdown probe sends no advance request and preserves the date. Playback is ordered and finishes before final result receipt; another playback queue is not justified.

One retained ordinary off-day sample receives final bytes at **1.938 s**, but delayed first-run tutorial setup invalidates its control-unlock timestamp. A separate read-only reload confirms functional controls. One earlier completed off-day observer attempt lost its row; no third simulation was run. Cold-server first-use and a perfectly exclusive server window are not claimed. Raw logs preserve favicon 404/aborted resource and stream notifications despite confirmed results, plus unrelated global simulation-conflict replies. The status note separates these limits from functional success. No broad tests, month/reload campaign, optimization or packaging pass was added to unchanged code.

The single final idle RSS observation is ~**826 MiB**; it does not settle the previous process high-water/retention question. Earlier bounded ownership gates still apply, not a new memory-stability claim. Reproduce analysis only with `PYTHONPATH=src:scripts .venv/bin/python output/performance-live-2026-11-03/summarize.py`; do not overwrite retained timing evidence or rerun the old-PID refresh script. The bounded timing window is released. **http://127.0.0.1:8796/** runs the latest verified backend.


## November 9: correctness correction, no new performance optimization

[Historical narrative correction and minutes/OVR audit](NARRATIVE_SIMULATION_CORRECTION_2026_11_09.md), `output/narrative-correction-2026-11-09/`: historical preseason keywords no longer grant persistent live-game feature bonuses/penalties. Only `sim.py` changes among the production source manifest; all prior optimizations, GUI files and preseason write-ups are preserved. The correction intentionally changes scores/career outcomes; do not apply older exact state digests to this new numerical behavior. Five new tests fail against the frozen reference and pass after, 45 relevant regression tests pass, and 12/13 selected foundation tests pass before/after with the same pre-existing rebound-range failure. Real-action prose variants now match exactly, and daily/bulk/midway reload match state and 16 ordered events across Oct 30–Nov 1; required cutdown still blocks without mutation. Small paired matchup scores/runtime and the separately disclosed setup outlier are in the handoff. No speedup is claimed, no server/preview was restarted and no live career changed. A separate stale free-agent MPG/retention comparison defect was reproduced read-only; signing/OVR/development correction is outside this pass.


## November 9: released-player opportunity correction

[Signing correction handoff](RELEASED_FA_OPPORTUNITY_CORRECTION_2026_11_09.md), `output/released-fa-opportunity-2026-11-09/`: the released-player comparison now grades outgoing-before and incoming-after under neutral destination role forecasts, pricing the actual proposed contract. Old MPG 0/30/42 no longer manufactures an upgrade. Existing eight-point and guaranteed-cut-cost gates remain. Only `save.py` changes from this pass's fresh reference, which already includes the narrative fix. Eleven final opportunity tests and the relevant suite's **119 checks pass**, including financially legal real cut/signing, guarantees/dead salary, injuries, priorities, context invalidation and snapshot release. Real daily/bulk/midway-reload actions match state/transactions/all 16 ordered events with an actual Cam Thomas→UTA signing and Trey Alexander cut. The separate redundant signing is intentionally removed; old/new global outcome parity is not claimed.

A three-rejection micro-batch costs **2.831 → 6.331 ms median**, not a speedup: one shared before roster plus three after rosters, while active materialization and healthy-context builds remain one each. Contexts release after settlement without production GC and never enter saves. No thresholds, quotas, ratings, development, actual rotations, GUI or dependencies change. Following idle verification, **http://127.0.0.1:8796/** was gracefully refreshed with the same launch flags/save directory, now PID **73225**. A real authenticated dashboard read succeeds; startup source/function fingerprints confirm both narrative and signing fixes, source-manifest revision `e3972b59c718253acfd4199eec12aa164eb081720f0108430850e4569f63257d`. Other previews and playable saves are preserved. No long-season or follow-on optimization was started.

## November 10: shared defensive correction, no performance optimization

[Implemented defensive correction](DEFENSIVE_ALIGNMENT_CORRECTION_2026_11_10.md), `output/defensive-alignment-correction-2026-11-10/`: shared activity/rim skill, a monotone high-rim shoulder, direct headline DEF and explicit effective-rim semantics replace the earlier isolated experiment. Raw v11 player/prospect/contract inputs remain unchanged; generated valuation/strategy/contract/team-board projections are refreshed. All earlier performance work is preserved. This intentionally changes numerical game/economic behavior: old-versus-new outcome parity is not claimed. Final fresh-model daily/bulk/midpoint reload matches meaningful state and 16 ordered events; 147 checks pass and 24 new paired games reuse the recorded baseline. No offensive batch, GUI, development, search-policy, quota, RNG algorithm or legacy migration framework is introduced.

Three short warm fresh-start action samples measure **2.781 → 2.710 seconds median** (ranges **2.725–2.791 / 2.695–2.731**), not a material-speedup claim. First-use outliers are separate. A 100-player warm function workload costs **5.877 → 6.510 ms**; allocation tracing runs separately. All sampled private roots release and post-diagnostic-GC traced retention matches, but the four-action current RSS peak is higher (**764 versus 677 MB**) and broad process stability remains unresolved. No new persistent cache or production GC was added. Timing windows are finished/released. Full commands, ownership findings, synthetic-versus-production financial results and limits are in the correction report.

The newly verified backend is **http://127.0.0.1:8797/**, PID **95084**, with isolated `output/defensive-alignment-correction-2026-11-10/preview-saves-final`. Startup code/canonical fingerprints and real HTTP fresh-save/card checks are recorded. Only this task's idle provisional server was replaced; pre-existing 8796 and other previews remain running and were not interrupted. **8796 is not the newly corrected defensive backend.** No release packaging or additional optimization was started.


## November 10: common rating scale and bounded defensive comparison

[Completed scale/comparison report](DEFENSIVE_SCALE_COMPARISON_2026_11_10.md), `output/defensive-scale-comparison-2026-11-10/`: all player OFF/DEF/OVR/subratings now display direct model grades; cards/Finder/Wants/previews and streamed opponent rows share units. This removes mixed display inflation, not engine ability. Autogenerated old-unit Wants cutoffs are translated; no GUI, market-policy, rotation or development change. A post-alignment Wembanyama rim **99→100** input preserves all other abilities, player/development/prospect/contract inputs and confidence. Broader impact remains unresolved: six inferred centers already share raw100, and unchanged Wembanyama activity/scheme inputs still leave him slightly behind Gobert in one matched center control. No forced rank or broad trait buff is claimed.

Three warm short backend-action samples per version measure **2.782 → 2.772 s median**, ranges **2.757–2.810 / 2.731–2.810**; first use is separate. This is not a material speedup. Incidental four-action peak RSS **767 / 692 MB** does not resolve long-lived memory behavior. No new persistent cache/production GC. Timing window complete/released; no long-season study. All prior performance work remains.

Scale-only engine/features/replacements and 14 complete financial controls match exactly. Final legal financial decisions/prices, separate Curry/Luka complete controls, seven real profiles, eleven projected-FA results and eight guarded trade decisions match. Four paired games have identical boxes/scores with a small continuous expected-rating change. New-model daily/bulk/midpoint reload matches state and all 16 ordered events. **65 final regression checks pass**, with overlapping scale/profile groups; the full fantasy suite retains one Giannis/Luka draft-order failure reproduced pre-edit. Report includes exact inputs, caveats and reproducible commands; evidence-only consolidation is `.venv/bin/python output/defensive-scale-comparison-2026-11-10/summarize.py`.

**http://127.0.0.1:8798/**, PID **2594**, is the latest verified isolated backend, with real HTTP-created fresh career/cards and loaded source/canonical fingerprints. Existing 8796/8797 and playable saves were preserved; neither is this pass’s latest backend. No packaging or next implementation pass was started.

## November 11: offline defensive-role prototype, production unchanged

[Working prototype report](DEFENSIVE_ROLE_PROTOTYPE_2026_11_11.md), `output/defensive-role-prototype-2026-11-11/`: isolated six-job estimates for all 691 players plus deterministic, fixed-budget hybrid lineup allocation are implemented outside runtime. Seventeen focused tests pass. Roles, exposure and current DEF remain separate; missing evidence, source-proxy uncertainty, sheltering and duplicate-credit constraints are explicit. A minutes/offensive-role-derived stamina proxy was rejected as an intrinsic chaser limit. An older held Castle input pair is tested only in private; no production trait correction or new game/economic campaign is claimed while the specific player-input research sheet is pending.

Offline scoring median **26.23 ms per 691-player sweep**, range 25.72–27.08 ms; five-player assignment/summary **0.613 ms**, range 0.605–0.840 ms. These are prototype overhead observations, not app speed gains. Separate traced output-batch ownership is documented; no new cache, production GC or process-memory claim. All 71 tracked pre-existing source/GUI/input hashes remain equal. No market policy, coach, rotation, prospect/development, UI or performance optimization changed. **8798 remains the existing verified production backend; the role prototype is not installed there.** No preview restart or long simulation was needed. Stop at this milestone; finish input calibration before proposing engine integration.
