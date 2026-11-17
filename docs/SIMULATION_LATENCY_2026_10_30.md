# Bounded end-to-end latency investigation, October 29–30, 2026

Investigation only. No simulation optimization, market-policy change, production instrumentation or GUI edit was made. All Python backend sources still match the hashes in `output/context-demand-pass/comparison.json`. The UI chat explicitly paused browser/simulation tests for the measurement windows and was explicitly released afterward. Playable previews 8780/8781 and original checkpoint saves were preserved.

Evidence: `output/end-to-end-latency/summary.json`, `wall-control/browser.json`, `control-tail/browser.json`, `diagnostic-server/diag-*.json`, and `http-diagnostics/`. The earlier `browser.json`/`server/` series is exploratory: another existing backend on 8776 was observed consuming CPU. It was never stopped by this investigation. Its first busy action took 47.64 backend seconds and is **not** a headline warm timing. A later clean control window had no competing simulation benchmark or UI browser test; other desktop applications and idle previews remained running.

## Cases and method

All cases use seed 17 and normal AI, quotas, approvals, progress events and animations. Archives include save components and are restored through `restore_save` to distinct disposable careers **before** timing. New paths/revisions and normal view invalidation prevent stale read-context reuse. No old context is injected into an action.

| Case | Starting date → endpoint | Work |
| --- | --- | --- |
| User off-day, no market | Oct 30 → Oct 31 | Eight league games; GSW does not play |
| Ordinary user game day | Oct 29 → Oct 30 | Four league games, including GSW |
| Busy market day | Feb 3 → Feb 4 | Seven games, two market searches, five applied trades |
| Short month boundary | Oct 28 → Nov 1 | Four days, 28 games, one trade search; other AI review work also occurs Nov 1 |

`cases.json` records archive paths and source hashes. Sources are the existing context-demand midpoint, task-1 month fixture and stable17 busy checkpoint. Creating the game-day archive requires one disposable setup day outside measurement. No season study was run.

Two **separate** servers served a byte-for-byte frozen copy of the existing GUI. The wall control used the normal HTTP handlers with attribution disabled. The diagnostic process installed wrappers only in that process. There is no cProfile in these wall samples. Headless Chrome used the native `advance`, streaming reader, progress display and controls, normal motion, and a 1440×1000 viewport. External browser requests were blocked; local app requests and AI were enabled. JS observers recorded timestamps without replacing playback. Chrome network data-receipt events recorded final bytes independently of the animation-awaiting parser. This bounds final-result receipt to the final response data chunk; it does not infer receipt from when playback permits JSON parsing.

## User-visible wall time

Seconds from the streaming request, excluding untimed restore/dashboard setup. Generic `start` is excluded from first meaningful progress. The busy/month rows are medians of two sequential equivalent-state samples; ordinary rows have one clean warm sample. Parentheses are ranges. These are short samples, not universal latency bounds.

| Case | First meaningful event | Largest meaningful-event gap | Final result bytes received | Last playback callback complete | Controls usable |
| --- | ---: | ---: | ---: | ---: | ---: |
| Off-day, warm | 0.26 | 0.12 | 1.65 | 0.56 | 2.81 |
| Game day, warm | 0.32 | 0.08 | 1.54 | 0.96 | 2.80 |
| Busy market | 0.76 (0.74–0.78) | 0.08 | 18.95 (18.83–19.07) | 0.98 | 20.53 (20.49–20.57) |
| Month boundary | 3.00 (2.94–3.06) | 9.21 (9.11–9.30) | 17.91 (17.73–18.09) | 14.66 | 19.18 (19.01–19.36) |

Warm click-to-request preparation adds 0.08–0.11 seconds, mostly `loadSimulationPlayerRatings`/`player_finder`. A separate newly opened browser's tail probe took 0.84 seconds in that preflight; do not assume it is always free. No modal/user-decision stop was bypassed; these cases completed without a pending decision modal. Visible “Sim to…” controls were enabled at each recorded usable endpoint. Browser page-error logs are empty.

The busy day emits its games early, then spends roughly 18 seconds with no additional meaningful progress while market/settlement work completes. The tiny inter-game gaps therefore **do not** mean the whole action is responsive. In the month interval, a roughly nine-second gap follows the Oct 29 games before Oct 30 progress. These are computation gaps, not slow streaming writes.

### First use is separate and partly unresolved

The clean wall server's initial browser off-day received final bytes at **33.50 seconds**, versus 1.65 on the repeat. Its first meaningful event arrived at 1.64 seconds, followed by a 30.46-second gap before games. This large initial delay was not reproduced in the next fresh diagnostic server: its first HTTP off-day took 2.68 seconds including 0.27 seconds of diagnostic hashing, versus 1.96 including 0.27 on the repeat. Reference loading there took 0.245 → 0.051 seconds, far too little to explain 30 seconds. The earlier exploratory first market sample also had an unusually large uninstrumented interval before games, under background CPU activity. **The large first-use delay remains unattributed; it is not established as deterministic initialization, a leak, or a removable 30-second CPU cost.**

The first browser sample also has a setup difference: the initial dashboard/preflight path materialized `.starting_lineups.team_gsw`, while the equivalent warm case did not. This meaningful field is retained in the comparison and explicitly reported in `summary.json`; that first sample is excluded from equivalent-state warm comparisons. The observer now lists restored saves before loading their dashboard, matching the normal restore/load flow and resolving the listed team consistently. That harness-only adjustment received syntax checks, not another simulation series after the quiet window was released. The recorded warm busy/month pairs have no such mismatch.

## Exclusive backend attribution

Separate real HTTP replays; these are **not** replacements for uninstrumented wall times above. Owner phases are mutually exclusive. Nested overlay/copy/context work remains inside its owning lifecycle, market, settlement or dashboard phase. “Load” includes preflight, checkpoint/control work outside those owners. Market includes `queue_ai_recommendations`; settlement includes `process_ai_actions_in_memory`. All phases, plus transport and diagnostic hashing, reconcile to the recorded handler duration within 1 ms.

| Replay | Load/materialize/control | Lifecycle and games | Market/AI review | Settlement | Persistence | Response/dashboard | Work total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Warm off-day | 0.061 | 0.657 | <0.001 | <0.001 | 0.178 | 0.783 | 1.680 |
| Busy market | 0.082 | 2.212 | 10.966 | 4.902 | 0.255 | 0.955 | 19.373 |
| Month boundary | 1.293 | 5.694 | 9.646 | <0.001 | 0.171 | 0.942 | 17.748 |

Work totals include approximately 0.001/0.001/0.003 seconds of stream transport; rounding can obscure the sum. Full-public-canonical plus whole-save hashing and shape inspection add a separately owned **0.273/1.738/0.987 seconds**. They are excluded from the phase/work table, and were never installed in the wall-control process.

Raw timestamps since diagnostic stream entry, **including** that separately recorded observer overhead:

| Replay | Last day's computation complete | Save/checkpoint returned | Backend result prepared | Final serialized write started |
| --- | ---: | ---: | ---: | ---: |
| Warm off-day | 0.916 | 1.093 | 1.948 | 1.953 |
| Busy market | 19.817 | 20.072 | 21.104 | 21.111 |
| Month boundary | 17.531 | 17.702 | 18.730 | 18.735 |

Persistence is about 0.17–0.26 seconds here; dashboard/response preparation about 0.78–0.96. These do matter on ordinary days, but are not the main busy-day wait. Ordinary game-day phase capture in the earlier lightweight run was 0.072 load, 0.604 lifecycle/games, <0.001 market/settlement, 0.172 persistence and 0.731 response, with computation complete at 0.677 and backend result ready at 1.574. Keep that separate from the later wall control rather than combining samples into a fictitious single timeline.

### Playback and post-result controls

`simulation-presentation.js:readStream` awaits native progress playback, while the HTTP thread continues computing. In **every clean warm case**, all animation callbacks finished before final bytes arrived. Result parsing followed final receipt by only a few milliseconds. Synchronous server writes/flushes totaled approximately 1–3 ms per action. No material stream backpressure or serial compute-then-animation delay was demonstrated. **Asynchronous playback already works; another playback queue is not justified by these measurements.**

There is a distinct control-lock tail. A separate normal off-day probe logged:

- Stream result received 1.590 s; `advance` returned 1.776 s.
- At return: `simulationRunning=false`, `hydrating=false`, but `busyDepth=2`.
- Two native `team_wants` reads ran approximately 1.771–2.780 s; controls became usable at 2.783 s.

Both the wants surface (`wireTeamWants`) and acquisition reminder (`maybeShowWantReminder`) can request wants after final rendering; `action` uses the shared busy counter. The backend `team_wants_action` independently loads/overlays/builds full transaction context. This is a measured roughly one-second post-result wait, **not animation time**. It is recorded as another finding, not included in the backend action phase totals or proposed as a second implementation task.

### Materialization and nested costs

The busy replay made **21 `canonical_with_save` calls, 3.243 s total**, including **2.243 s** in 22 runtime-tree copies (one copy occurs outside these overlays). Eight full transaction-context builds consumed 3.260 s. These are nested attribution: do not add them to market, settlement or each other. Two `simulate_ai_trades` calls consumed 10.956 s within the 10.966-second market owner. The month case made 12 overlays/1.703 s and eight context builds/2.965 s. Game-context loading/index rebuilding was only approximately 0.048/0.004 seconds on the warm busy case; it does not explain its market wait.

Hashing the **whole save and all public canonical fields**, with the same authoritative source object, found five distinct settlement snapshots. Each appeared three times before that trade's transfers: `saved_trade_salary_legality`, `live_roster_issues`, then entitlement validation inside `apply_trade_to_state`. The ten duplicate overlays cost **1.525 seconds**. Successive transactions had different hashes, so reuse across the five trades would be incorrect. There were no duplicate whole-input overlays on the off-day; one duplicate, 0.136 seconds, in the month interval was outside this settlement opportunity.

Each canonical copy includes approximately 15.8 MB of serialized public source data: about 9.5 MB of traits, 1.56 MB of 1,800 scouting reports, and 0.61 MB of 1,800 draft-board entries. This demonstrates traversal/copying of broad collections, not their retained in-memory size or proof that every field can safely be deleted. The default overlay also copies transaction logs/plans/wants; salary and roster validation separately deep-copy the saved career. The next task should first remove identical full materializations, rather than introduce a narrower universe without a complete dependency audit. No memory-retention study or memory-reduction claim is made in this investigation.

Market work dominates the busy action and over half of this four-day boundary interval; it does not dominate the selected two ordinary days. There was one trade-search date in the four-day interval. This small sample cannot estimate season-wide market frequency or justify moving causal trade decisions to a background job.

## One recommended next implementation task

**Prepare one fresh, isolated settlement snapshot per bilateral proposal and share its authoritative materialization among salary, roster and entitlement validation. Discard it before the next transaction.** Keep current full construction as a differential fallback; leave multi-team application on that fallback until explicitly covered.

The demonstrated addressable portion is **1.53 seconds on the five-trade busy checkpoint**, roughly 8% of its measured backend work. This is an upper bound on removed duplicate overlay work before adapter/isolation costs, not a promised net speedup, a 25% claim, or removal of the entire 4.90-second settlement phase. It offers essentially no benefit on a day without settlements. The larger 10.97-second market cost is necessary search work in this evidence; no architecture that removes that entire cost while preserving causal outcomes was demonstrated.

Affected areas:

- `transactions.py:apply_trade_to_state` and `saved_trade_salary_legality` — create/pass an explicit private, current-state validation input instead of separately materializing the same source.
- `trade_roster.py:live_roster_issues` — accept that owned input while still constructing fresh league-wide valuations, ranks, strategic states and pick-investment checks.
- `save.py:canonical_with_save` — retain the full reference path and audit its save-side rotation/health normalization effects; no general cache API or broad state rewrite is needed.

Identical outcomes appear achievable because the complete public source/save inputs match within each trade. This investigation does **not** prove shared mutable outputs are interchangeable. Full context construction, pending protected/swap terms, current health/contracts/dead salary, wants/plans/control permissions, participant approval and authoritative financial checks must remain fresh. Cached search approval is never sufficient.

The main risks are aliasing/mutation of the shared active universe, stale indexes, and lost save-side normalization from `canonical_with_save` (its copied-save and authoritative-save callers have different side-effect boundaries). Keep a private owned save copy, explicit ownership for derived views, and preserve required authoritative effects in their existing order. Do not retain the snapshot in proposals, responses, global caches or the save. Sharing one object may shorten peak live graphs, but memory improvement requires measurement, not inference from serialized byte counts.

Bounded plan: retain the three-builder reference; differentially compare each consumer's inputs/outputs and save effects on captured settlement states; add sequential/stale-trade, injury/contract/ownership/plan/wants changes, protected terms, swaps, human rotations, premium/core/pick-investment and rejection-no-mutation cases. Completed multi-team routes keep full validation. Then repeat the existing two busy seeds and month action parity, including explanations, full ordered events, daily/bulk and midpoint reload. Run short sequential wall samples separately from attribution and a bounded same-process memory/release probe. Keep the change only if net wall time improves without changing outcomes or ownership. No policy, quota, RNG, animation, concurrency or negotiation-memory work belongs in it.

## Reproduction and cleanup

Diagnostic scripts remain outside production so the measurements are reviewable. Coordinate a quiet window first. Use fresh output directories and unused ports; never replace an active preview. Example setup from the repository root:

```sh
RUN=output/latency-rerun
PYTHONPATH=src .venv/bin/python scripts/prepare_latency_cases.py --output "$RUN"
mkdir -p "$RUN/wall-control"
cp "$RUN/cases.json" "$RUN/wall-control/cases.json"
PYTHONPATH=src .venv/bin/python scripts/investigate_latency_server.py \
  --output "$RUN/wall-server" --port 8792 --wall-only
```

In a second shell, after the server has finished starting:

```sh
NODE_PATH=/Users/noahtyler/.npm/_npx/e41f203b7505f1fb/node_modules \
  node scripts/measure_frontend_latency.cjs http://127.0.0.1:8792 "$RUN/wall-control"
```

The Chrome/Playwright paths are host-specific. `LATENCY_RUNS` can select a bounded subset, e.g. `[["offday","warm"]]`. Complete the browser run **before** starting attribution work. Start a second server with a fresh output directory and the same frozen GUI:

```sh
PYTHONPATH=src .venv/bin/python scripts/investigate_latency_server.py \
  --output "$RUN/diagnostic-server" --port 8793 \
  --gui-snapshot "$RUN/wall-server/gui"
```

Then, serially in the client shell:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/replay_latency_http.py \
  --url http://127.0.0.1:8793 --cases "$RUN/cases.json" \
  --output "$RUN/http-diagnostics" --names offday,offday,busy,month
PYTHONPATH=src:scripts .venv/bin/python scripts/summarize_end_to_end_latency.py --base "$RUN"
```

This investigation's state/event checks pass for both busy repeats, both month repeats, and warm off-day browser versus HTTP. Busy/month full saved-state and ordered event digests also exactly match the prior context-demand evidence. The ordinary user-game sample is recorded, not claimed as an independently repeated parity pair. The one first-use lineup mismatch is explicitly retained above. All original source hashes remain unchanged. Script syntax checks passed; production behavior was untouched, so no broad test-suite rerun was performed.

After checking no action/client remained active, only the investigation's servers were stopped. Their measured URLs were 8792 (wall control) and 8793 (attribution); these are not advertised as production previews. Existing playable previews were not refreshed or interrupted. GUI-file ownership stayed with the UI chat throughout.
