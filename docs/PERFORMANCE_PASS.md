# Local Performance Pass: 2026-10-03

## Changes

The starting-five optimizer still searches every permutation of its original nine-player candidate pool, in the same order, with the same scoring, floating-point summation order and strict greater-than tie breaking. It now calculates each player/position score once per invocation: at most 45 calls rather than 75,600. A complete, healthy stored lineup no longer performs an unused autofill search. Partial and injured lineups still autofill, retaining a user's stored choices for injury recovery. There is no cross-call lineup cache.

The dashboard no longer requests asset valuations for hidden windows. Roster, statistics, contracts, payroll, draft assets and trade-block windows request the shared payload when opened or restored. Matching current data is reused; saved visible windows fetch on resume, while minimized windows wait until restoration. Gallery previews and tutorial previews do not fetch it. Failed requests show Retry; stale requests and errors cannot overwrite or block a newer dashboard. This changes loading timing, not valuation or basketball rules.

## Measurements

All measurements used disposable copies of the isolated first-hour Warriors save, not real user saves. Python 3.12.11 and headless Chrome ran on this Apple Silicon Mac. Timings are not guarantees for other machines.

| Measurement | Previous algorithm | Optimized |
| --- | --- | --- |
| Cold dashboard snapshot, median of three unprofiled reads | 0.920 s | 0.771 s |
| Warm dashboard snapshot, median of three reads | 0.0080 s | 0.0077 s |
| Seven-day advancement, one unprofiled sample each | 6.006 s | 4.941 s |
| Browser Enter Save to usable dashboard, one sample each | 2.866 s | 1.462 s |

The cold backend median improved about 16%. The browser improvement includes deferring the formerly automatic 690 ms asset read; it is a single before/after sample, not a percentile benchmark. The first time an asset window is opened, its valuation work still needs to run. Canonical loading, deep copies, rendering and AI contract comparisons remain measurable costs; this pass does not claim to solve all performance problems.

A 30-step pointer drag consumed about 73 ms total browser task time before changes, roughly 2.4 ms per step. No drag behavior was changed because it was not the reproduced bottleneck. Earlier cProfile timings include profiler overhead and are not used as the speedup baseline above.

## Verification

- All 30 real team lineup outputs matched the retained reference algorithm exactly.
- Old/new full dashboard snapshots matched exactly. A seeded seven-day advance matched team records, player season statistics, health states and starting lineups exactly. This is not a full-season or full-save equivalence claim.
- Nine targeted Python tests passed: five differential/performance tests and four existing lineup regressions. The OKC/SAS test now uses separate save paths, respecting existing overwrite protection.
- 102 focused JavaScript tests and four static-media Python tests passed. New cases cover deferred reads, deduplication, stale completions, dashboard changes in flight, retry recovery, focus preservation and window restoration hooks.
- The asset-loading browser runner passed on the source server and frozen beta.5 Apple Silicon app, with external requests blocked and no browser page errors. Five checks cover no hidden-window requests, shared data reuse, minimized and visible resume, and injected failure/retry.
- The source first-hour browser workflow passed all nine checks, including tutorial, persisted minutes, injected autosave failure, reports, trade search and five simulated games with a real box score.
- Both extracted beta.5 architecture ZIPs passed packaging smoke tests: offline video/fallback, first game, backup/export/restore, restart, duplicate launch and byte-for-byte preservation of stored data after app replacement. Intel execution was under Rosetta, not on a physical Intel Mac. Both reports at `dist/macos/verification-0.1.0-beta.5-{arm64,x86_64}.json` have `checks.complete: true`. Downloads remain ad-hoc signed and unnotarized.

Evidence is under `dist/macos/performance-beta.5/`: `backend.json`, `browser-entry.json`, and source/frozen browser reports and screenshots. First-hour evidence is at `dist/macos/first-hour-beta.5/`.

The older GUI concept suite still has documented stale expectations; the complete repository suite was not asserted green. This pass did not test physical Intel hardware, Safari/Firefox, a full season, hosted multiplayer or Windows packaging.

## Repeat

The benchmark copies the fixture's entire directory into a temporary directory before reading or advancing it:

```sh
PYTHONPATH=src python -B scripts/benchmark_local_performance.py /path/to/test-save.json --output /tmp/nba-performance.json
```

The browser runner refuses a server containing any saves. Start a server with an empty isolated save directory, then run:

```sh
node scripts/verify_assets_loading_browser.cjs http://127.0.0.1:8790/ /tmp/nba-assets-evidence
```

Playwright and Chrome are verification dependencies only; neither is required by the downloaded game.
