# Exact-output simulation algorithm checkpoint — November 2, 2026

**Recommendation: no larger production rewrite is justified by this checkpoint.** The one demonstrated implementation candidate is a small, exact dense role-assignment solver. Its extrapolated saving is roughly **0.24 seconds per busy action**, not several seconds. The two-worker sampled evaluator loses on short fresh-review replays once preparation, transfer and process lifetime are included. Compact numeric inputs reduce transfer/memory substantially, but have not demonstrated a corresponding playable speedup. Obtaining a larger exact-output gain now requires a separately approved computational-kernel experiment and its packaging obligations; neither multiprocessing nor another cache is a demonstrated answer.

Production, canonical data and the verified preview were left unchanged. Evidence and runnable prototypes: `output/algorithm-design-2026-11-02/`. No dependencies were installed. Experiments used the existing arm64 macOS CPython 3.14.4 environment; packaged Python versions differ.

## Addressable wall budget

The existing **uninstrumented paired baseline** remains the feature-input pass: busy-17 **16.16 s**, busy-29 **15.76 s**, month boundary **15.35 s** medians. No new production speedup or repeated whole-action timing campaign is claimed.

One fresh disposable February 3–4 seed-17 real app action collected disjoint wall clocks without cProfile or input capture. It took **14.709 s**, including wrapper overhead. This is attribution on a different measurement occasion, **not evidence of an improvement over 16.16 s**. Instrumented child elapsed time is subtracted from its enclosing block; totals reconcile. A separate capture action took 17.920 s, including 2.439 s of observer work; it is excluded from the table.

| Disjoint action work | Seconds |
| --- | ---: |
| Lifecycle/games, excluding market/settlement | 1.912 |
| Market search | 9.207 |
| Fresh sequential settlement | 2.239 |
| Persistence | 0.244 |
| Dashboard/response | 0.790 |
| Other dispatch work | 0.317 |
| Total | **14.709** |

The **9.207 s market block** partitions into: package generation **2.023**, pick previews **0.642**, candidate legality **0.587**, participant scalar work **1.085**, participant roster forecasts **1.944**, remaining candidate preparation **1.094**, full fresh context **0.184**, and remaining search/control work **1.649**. These are disjoint. Package generation includes its financial classifications. Candidate preparation includes work outside participant/legality blocks. It is not all replaceable by a numeric kernel.

Nested clocks, **not additive to that partition**: 3,892 participant calls **3.030 s** including forecasts; 828 market role assignments **0.646 s**; 599 market rotations **0.927 s**; 2,238 projections **1.573 s**. Across all phases, 1,074 role assignments take **1.171 s**. Eight full context builds total **1.503 s**, including league-relative strategy, values and rotations; five follow successive actual trades. The latest cProfile (`output/feature-input-pass/profile-after/profile.txt`) remains useful for call attribution, not wall-time sums.

Consequences: perfectly free role assignment cannot save more than its 1.171 s inclusive budget. Perfectly balanced two-worker participant execution could save at most **1.515 s / 10.3% of this action**, before setup, IPC, extra work or cache duplication. It cannot halve the 9.207 s market block. Parallelizing the entire market would require a different dependency design.

## Ranked options and experiments

| Rank | Concrete option | Evidence / decision |
| --- | --- | --- |
| 1 | Exact dense 32-state role DP, invariant scores once per roster, allocate assignments only on winning updates | Measured **31.6%** kernel reduction; small, bounded implementation candidate. Estimated action saving ~0.24 s; no integrated gain proven. |
| 2 | Compact snapshot-owned numerical inputs for a future participant/roster kernel | Trait rows reduced to ordered player/key/value inputs halve worker payload and reduce RSS. This establishes transport feasibility, not a faster current evaluator. Do not replace public canonical records or undertake a context-framework rewrite. |
| 3 | Ordered two-worker candidate batches using stdlib spawn | Exact sampled outputs, but **slower fresh-review totals**, higher memory, and dependency/early-stop constraints. Do not implement. |

### Exact role solver

`prototypes/roles.py` clones the existing function as a reference and supplies the actual captured warm attribute inputs to both implementations. Packing IDs, calculating scores, DP, minutes allocation and output reconstruction are inside both timers. Canonical attribute extraction is excluded for both; this is not a complete roster benchmark.

The prototype retains sorted player order, mask insertion order, strict `>` updates, score addition order and final tie choice. Every player iteration snapshots both scores and assignments before updating states, preventing accidental use of that player twice. Five positional scores are calculated once and reused for the second group. Public output remains ordinary dictionaries/lists.

**49/49 cases match**: 31 real rosters of 14–17 players and 18 synthetic empty/short/oversized, reversed-order, all-position ties and adjacent-float cases. Both group masks, assignment IDs and score `float.hex()` values match; final minutes/order match. Real cases include 19 injury-tagged memberships, seven oversized rosters and one human-owned team's *hypothetical healthy forecast*. This does not test or change actual human rotation overrides.

Five alternating samples, 372 calls each:

| Solver | Median seconds | Range |
| --- | ---: | ---: |
| Existing exact DP | 0.2632 | 0.2610–0.2705 |
| Packed dense DP | 0.1801 | 0.1786–0.1835 |

Extrapolating the per-call difference to 1,074 calls gives **0.240 s**, with representativeness uncertainty: real cases deliberately include uncommon rosters and neither timing includes attribute extraction. Even the 31.6% ratio applied to the entire inclusive role clock is only 0.370 s and overstates the removable scope. No one-second claim is supported. Temporary inputs are per-call O(roster × five + 32 states), without a retained cache.

### Compact inputs and ordered batching

Captured 96 actual participant calls from one immutable review, 25 reaching roster work; ten involve a human-controlled team. Assets include 239 player occurrences, 101 picks and 13 swaps. Forty-six calls have actual pending pick-state deltas; only draft picks, obligations and locked assets differ from the frozen base. All sampled legal reports are legal; this is not coverage of terminal/unresolved classification. Early-rejected calls can legitimately return no reports. Remaining reports include accept, pick-investment and roster-plan rejection.

Full public/allowed planning source is **19,815,058 bytes** in pickle protocol 5. Of that, traits account for 9.85 MB, primarily evidence fields. Experimental compact traits retain ordered `player_id`, `trait_key`, `value` records; all other source fields, league strategy, player records, health, plans, control, financial and pick inputs remain. Payload becomes **9,967,543 bytes**. Preparing those compact rows costs **0.0089 s** in the transport probe. This is an isolated calculation source, not a replacement for presentation/source provenance. The original authoritative source would still exist in a real server; compact worker RSS is not a claim that the main save graph disappears.

All **96 complete outputs** match captured results exactly for serial full/compact and ordered worker execution, including decisions, reasons and roster/pick conclusions. JSON float round trips preserve double values; the separate role probe additionally checks intermediate float bits. This finite sample is not a complete dependency audit authorizing production compaction.

Fresh-review timings below are three sequential samples per input form. Restore/decompress source outside timing; include compacting/packing, fresh decoding/indexing, IPC, result reconstruction and worker shutdown. Eight waves of twelve sampled candidates run sequentially, with six per worker. This deliberately avoids pretending all 96 are available at once, but these are **sampled cohorts, not the real search's buyer waves**. The serial transport reference also pays packing/decode it does not need in production, favoring the worker comparison.

| Fresh review replay | Serial median (range), s | Two workers median (range), s |
| --- | ---: | ---: |
| Full inputs | 0.627 (0.618–0.644) | **1.050 (1.028–1.087)** |
| Compact traits | 0.475 (0.471–0.482) | **0.724 (0.704–0.733)** |

A complete 3,892-call review could amortize startup better than this 96-call sample. This experiment does **not** prove workers would be slower for that full review. It also does not establish a playable gain: the ideal participant-only saving is capped at 1.515 s, realistic small waves add transfer/straggler costs, and fresh workers add roughly 220–320 MiB of observed resident memory. A full integration would still need an early-stop/dependency proof.

Even excluding shutdown, worker receipt totals are **0.720 / 0.578 s** (full/compact), slower than those serial references. First twelve results take **0.406 / 0.314 s** including startup/packing. Parent-only fresh calculation for 96 calls is separately **0.436 / 0.390 s** median, excluding transport initialization. Full/compact serial measurements were separate sequences, so their difference is not a paired production speedup.

Warm repeated-job waves reach about **0.213 / 0.182 s** medians, but those hit caches on the *same 96 jobs again*. Actual unique-roster work does not have that reuse; the prior repeat probe found only 0.031 s of repeated rotations. These are throughput diagnostics, excluded from claimed playable gains. Batch-48 throughput is also recorded but exceeds ordinary/deadline per-buyer width and is not a valid search replacement.

Idle simultaneous RSS samples after the batch-12 probe: parent **307 MiB + workers 159/159 MiB** full; parent **201 MiB + workers 111/109 MiB** compact. Parent sizes include this diagnostic's decoded inputs and source, not an app server. Workers retain their own bounded snapshot caches until executor shutdown; all exit afterward. Shutdown alone adds roughly 0.15–0.33 s here. No whole-game memory stabilization claim follows from these short runs. Existing server RSS concerns remain open.

## Dependency and platform boundary

Current search is serial for reasons beyond Python execution: package loops stop on the first approval; reserved assets, quotas and subsequent target/buyer exploration depend on prior results. Ordinary/deadline buyer breadth is five/twelve, not an arbitrary large work queue. Speculatively computing a whole wave can waste work; consuming results early or out of order changes discovery. Per-proposal personality RNG is deterministic/local, but that alone does not make the overall search graph independent. Pick deltas must be job-specific. Fresh settlement stays serial and revalidates every participant against the preceding trade's changed league state.

Relevant boundaries: `save.ai_role_targets`; `transactions.evaluate_trade_participants`, `evaluate_trade_for_team`, `strategic_rotation_view`, `package_value_components`, `buyer_offer_packages_for_value`; `trade_roster.roster_projection`; `roster_forecast.ForecastSnapshot`. Existing player/trait indexes already remove many scans. Repacking every forecast cannot be presumed cheaper than indexed dictionaries, and numeric packing alone does not execute Python arithmetic faster. A native kernel would need a measured, complete input boundary before adoption.

The runtime currently has **no declared third-party dependencies**. Stdlib workers avoid a new runtime but add spawn imports, serialization, duplicated caches and memory. A frozen executable also needs verified `freeze_support`/entry-point behavior before GUI argument parsing. macOS arm64 and Intel/Rosetta build Python 3.12; Windows packaging uses x64 Python 3.13 and needs separate executable testing. This arm64 Python 3.14 source test validates none of those artifacts. Limit workers explicitly to avoid oversubscription; no pool attached to saves/responses or persistent career graphs.

A C/Rust/other compiled numeric backend would add compiler/build/ABI and distribution tests for those platforms. No native prototype or speed measurement was performed. No reassociation, fast-math, fused multiply-add substitutions, lower-precision storage or different rounding is permissible. The **3.030 s participant** and **2.023 s generation** blocks are separate coarse ceilings for a potential broader kernel, not 5.053 seconds of proven compilable arithmetic. Many branches still consult protections, swaps, wants, finances and mutable proposal data. Do not promise a multi-second gain from this table.

## Bounded next step and gates

If another fraction of a second is useful, approve **only the dense exact role solver**:

1. Modify only `save.ai_role_targets`, with the existing implementation retained as a private differential fallback; no caller/context/search changes.
2. Expand exact tests to all 30 starting teams plus mature checkpoints, ties/short rosters, injuries, oversized retention/cuts and actual human rotation boundaries. Compare intermediate assignments and floating scores as well as final forecasts.
3. Preserve core/premium/pick-investment outcomes, sequential fresh settlements and pending terms. Require full state, explanations and ordered events on both busy seeds/month boundary; daily/bulk and midpoint reload checks.
4. Run short sequential paired uninstrumented timings, profile separately; retain only a repeatable worthwhile gain. Verify no mutation and per-call temporary release with same-process memory checks.

For a materially larger target, the separate user decision is whether to fund a **strict-arithmetic compact native-kernel prototype plus the three-platform build/testing obligation**, with a rejection gate for packing-inclusive speed/memory, before any production integration. Current evidence does not justify a larger exact-output implementation, a worker pool, a broad state rewrite or weaker market logic.

Reproduce sequentially, without other simulations/browser action tests:

```sh
PYTHONPATH=src:scripts .venv/bin/python output/algorithm-design-2026-11-02/prototypes/budget_only.py
PYTHONPATH=src .venv/bin/python output/algorithm-design-2026-11-02/prototypes/roles.py
PYTHONPATH=src .venv/bin/python output/algorithm-design-2026-11-02/prototypes/batching.py
PYTHONPATH=src .venv/bin/python output/algorithm-design-2026-11-02/prototypes/batching.py --compact
PYTHONPATH=src .venv/bin/python output/algorithm-design-2026-11-02/prototypes/cold_waves.py
.venv/bin/python output/algorithm-design-2026-11-02/prototypes/verify.py
```

The capture source is `output/pick-investment-2026-10-28/stable17/saves/trade_year.json`; it is never advanced in place. Real action runners need an unused output directory (edit their diagnostic `ROOT` first for a new campaign); microprobes consume the retained bounded inputs. `capture_budget.py` regenerates them separately from clean clocks. Both real actions match the previously verified meaningful state, complete response (only established revision/disposable-path metadata normalized) and eight ordered events. All **67 recorded production/canonical hashes** match. No broad suite was rerun for unchanged production. Latest verified backend remains **http://127.0.0.1:8796/**, PID 56446; it was not restarted. The research probe completed before timing; the measurement window is now released.
