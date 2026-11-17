# Simulation performance status — November 3, 2026

The current backend is live at **http://127.0.0.1:8796/**, PID **85369**, serving `output/feature-input-pass/preview-saves`. It includes the Team Wants read improvement. The isolated native experiment is **not** installed. This pass refreshed and verified the existing preview; it introduced no production, GUI, ratings or market changes.

## What is active

The backend retains compact trade evaluation with snapshot-correct presentation, review-local exact reuse, exact package-generation improvements, salary-aware direct/repair search, indexed roster forecasts, demand-specific fresh contexts, bounded read-context ownership, one privately owned bilateral settlement materialization, exact protection previews and scalar-only player features. Multi-team settlement retains its full fallback; approvals remain fresh after preceding transactions. Stage B intentionally changed package discovery. The historical busy-day progression from roughly **36–37 seconds to ~16 seconds** is checkpoint/benchmark-specific, spans several passes and is **not** one exact-outcome before/after experiment or a universal user latency claim.

The latest implemented change lets read-only Team Wants requests use the existing revision-owned two-entry dashboard context. Edits/acknowledgements retain private fresh validation, reads share the save lock, and returned match lists are copied. Its prior isolated HTTP test measured the warm two-read tail **0.806 → 0.046 s** (three samples), while cold reads remained ~0.39 s. That report contains 24 selected tests, 25 complete-response differential cases, 18 equal HTTP responses and three equal real actions; these tests were not broadly rerun during this integration-only pass. See [Team Wants evidence](TEAM_WANTS_READ_PERFORMANCE_2026_11_02.md).

## Current native-browser measurements

Headless installed Chrome, normal motion, real current GUI and streaming action path, real games/AI, loopback HTTP. Starting archives were restored as new disposable careers outside each action clock, using normal invalidation. The observer called the native `advance` flow and did not replace playback or animation implementations. After completion it tested the visible Sim to… trigger and Next Event menu option without advancing again. All seconds below start at the streaming request; native preflight adds **0.09–0.13 s**. Final receipt is Chrome's final response-data chunk, independently observed from the animation-awaiting JSON parser; it is not a new pure backend CPU measure.

| Case | Retained samples | First meaningful date/game | Final-result bytes received | Wants complete | Controls usable |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordinary off-day, Oct 30–31 | 1 | 0.387 | 1.938 | 2.135 | Not measured reliably¹ |
| User game day, Oct 29–30 | 2 | 0.265 (0.263–0.267) | 1.481 (1.353–1.610) | 1.713 (1.577–1.850) | 1.721 (1.582–1.859) |
| Busy seed 17, Feb 3–4 | 2 | 0.604 (0.603–0.605) | 15.782 (15.257–16.308) | 16.035 (15.501–16.568) | 16.046 (15.513–16.578) |

Two-sample entries are medians (ranges), not statistical confidence bounds. The busy samples each simulate seven games and apply five trades. Game-day samples simulate four games. The off-day simulates eight league games with no GSW game and no trades.

¹ Two off-day simulations completed in total. The first observer lost its timing row during an optional menu check; the second preserved raw timings but the normal delayed first-run tutorial opened during the action and prevented a valid control-unlock timing. No third off-day simulation was run. Later game/busy setup waited for and skipped that tutorial through its normal button **before** timing. This is an observer/setup limitation; the off-day does not supply a clean control latency or a paired Wants-tail measurement. A separate read-only reload confirms the off-day menu option is actionable after the tutorial is skipped; it supplies no retrospective unlock timestamp.

Playback callbacks finish **0.72 s off-day, 0.88–0.95 s game day and 0.87–0.99 s busy day**, before final bytes. Finite observed animations likewise finish before the result. Callback sequence equals the complete received start/date/game sequence, with callbacks serialized in order. **Asynchronous playback already works.** The busy-day quiet interval after its games is computation, not playback: roughly 14.5–15.3 seconds remain before the final result. The largest gap *between* meaningful events is only 0.09–0.25 s and must not conceal this trailing wait.

Both normal post-result Wants reads remain present on game/busy samples. Their combined elapsed span is **47–50 ms / 70–77 ms**, and controls become usable ~**0.23–0.27 s after final-result receipt**, including final rendering. The menu option passed Chrome's actionability check for all four game/busy samples. This verifies the updated flow live; the previous HTTP-only saving cannot be presented as a paired browser improvement because no pre-change browser series was run here.

There is no controlled cold-server first-use observation. The server was already used by another client before the retained series. The global log also contains simulation-conflict **409** replies outside this observer's API responses, so this is not claimed as an exclusively owned server window. No other preview was stopped. These are practical integration samples, not a replacement for earlier isolated sequential backend timings.

## Correctness, source identity and errors

The two game samples have identical meaningful saved state, complete responses and ordered events. The two busy samples also match each other and the verified `feature-input-pass/after-seed17-1` business state, complete response and eight ordered event hashes exactly. Only established disposable response path and dashboard revision metadata is normalized; explanations, transactions, offers and lineup data are retained. The off-day business-state digest also matches the earlier fixture result. No new backend change required another daily/bulk/reload campaign; previous verified results remain applicable to byte-identical simulation sources.

A native required-cutdown guard probe shows the decision card, sends **zero** simulation requests and leaves October 30 unchanged. Its immediate capture still has a read-only Wants request in flight; a later read-only revisit confirms busy=false/depth=0 while the cutdown remains required. No guard was bypassed.

Loaded backend function/source fingerprints were captured inside the replacement server at import. Before/after backend hashes and GUI source hashes match; captured HTTP GUI resource bodies match disk. Original checkpoint hashes are unchanged. The previous idle preview was gracefully replaced with its same binary, flags, host, port and save directory after socket/thread/stack checks showed no request worker or active simulation. Other previews and the unrelated `ind_2078409942` career were preserved.

No browser JavaScript exceptions or non-success observed API response statuses occurred in the retained game/busy series. Logs retain a missing favicon **404**, an aborted startup-video request, and three Chrome `net::ERR_ABORTED` stream notifications despite complete parsed results, matching saved state and successful control recovery. Their transport-notification cause is not established; do not describe the console/network log as error-free or silently discard these records. Global 409 conflicts are the separate shared-server limitation above.

Evidence: `output/performance-live-2026-11-03/summary.json`, raw per-action JSON, `decision-stop.json`, `browser-errors.json`, `loaded-backend.json`, `loaded-gui.json`, `refresh.json`, and source manifests. Observer failures are retained in `browser-final.log`/`browser.log`; successful subsequent samples are in `browser-final-2.log`.

## Remaining cost and rejected experiments

The latest separate diagnostic partitions a **14.709 s** real action into non-overlapping owners: market **9.207**, settlement **2.239**, lifecycle/games **1.912**, persistence **0.244**, response/dashboard **0.790**, other **0.317 s**. This is attribution, not an uninstrumented timing sample or the current browser clock. Within market, participant evaluation is 3.030 s including roster forecasts, and package generation is 2.023 s. These nested figures must not be added to the owner budget. See [algorithm evidence](SIMULATION_ALGORITHM_DESIGN_2026_11_02.md).

Further exact repeat caches have not demonstrated large headroom. Remaining rotation signatures are mostly different rosters/snapshots. The native five-slot DP experiment saved **0.408 s / 2.73%** across three paired busy actions including packing/FFI, with **0.595 s** initial library load; production integration was rejected as the next material latency project. UBSan passed, ASan stalled before `main`, and Intel/Windows/frozen builds remain unvalidated. See [compiled experiment](COMPILED_HOTPATH_EXPERIMENT_2026_11_02.md).

Adjacent-review evidence found **1.462 diagnostic seconds** of recurring evaluations, but **zero** conservative complete-input key matches. Two former rejected packages became approved and new valid alternatives emerged. A cross-date rejection cache or target blacklist is unsafe for identical behavior. Same-review exact duplicates have only sub-second raw ceilings before bookkeeping. See [cross-review findings](CROSS_REVIEW_MARKET_EVIDENCE_2026_11_02.md).

Memory ownership gates passed for the bounded read cache and snapshot release. A real earlier unbounded retention source was fixed; subsequent whole-process RSS/high-water variation is **not fully attributed**. Team Wants' ordinary 90-read diagnostic holds two entries with ~33–38 KB warm traced growth, and sampled roots release. That does not resolve earlier ~0.5–0.7 GB server peaks. After this integration/reload series, a single idle `ps` reading is 845,648 KiB (~826 MiB); without a paired baseline or repeated ownership trace it establishes neither a leak nor harmless allocator behavior. This pass adds no cache and makes no RSS stabilization claim. Current timings are macOS/ARM64/Python 3.14; packaged Python, Intel and Windows performance are separate validation gaps.

## One next design decision, requiring separate approval

If a material further reduction is required, commission a **bounded, explicit negotiation-review policy experiment**, rather than another exact-result cache. Its target is the measured **9.207 s market owner**, specifically repeated exploration across nearby reviews. The existing evidence establishes only a **1.462 s gross repeated-evaluation observation**, not a safe saving: no complete deterministic key repeats, and replacement exploration could consume that entire budget. No gain is promised.

Affected areas would be `save.queue_ai_recommendations`, `transactions.simulate_ai_trades`, package-generation callers and the multi-team facilitator frontier. A separately approved design would specify which prior failures influence exploration, when fresh alternatives and forced fresh reevaluation occur, the bounded revision-owned metadata and schema/migration behavior. It must explicitly allow changed discovery; it **cannot** promise identical old outcomes. Fresh settlement legality, approvals, premium/core/pick-investment safeguards, transaction frequency, user stops and animations must remain intact.

Before implementation, define a small acceptance gate over the existing ordinary/deadline/offseason checkpoints and seeds 17/29, including known reject→approve counterexamples, lost/gained valid proposals and daily/bulk/reload determinism. Compare whole action wall time sequentially and retained memory, not skipped call counts. Reject the experiment if discovery quality or total latency worsens. No negotiation memory or policy change was implemented by this pass, and there is currently no demonstrated large exact-output architectural shortcut to substitute for that explicit product decision.

## Reproduction and stopping point

Raw samples are immutable evidence; do not rerun the retained scripts over their original output files or count more than two simulations per case. For a new approved campaign, use a fresh evidence directory/run prefix and retain the normal 450 ms tutorial handling before measurement. No full-season, month-boundary rerun, broad suite, packaging or GUI work was performed here.

Read-only analysis:

```sh
PYTHONPATH=src:scripts .venv/bin/python output/performance-live-2026-11-03/summarize.py
```

The browser observer uses installed Chrome and Playwright from `/Users/noahtyler/.npm/_npx/e41f203b7505f1fb/node_modules`; it preserves real animations. `browser.cjs` records the remaining-case continuation after the documented exploratory attempts and is not a fresh-series driver. Do not rerun `refresh_preview.py`: it deliberately identifies the replaced old PID. The verified latest-source preview is **http://127.0.0.1:8796/**; the measurement window is released.
