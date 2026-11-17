Headless month advancement is faster, with the mid-season case now inside the 10–20 second target.
All three tested months produce exactly the same saved results and history row counts.
Early-season months still exceed the target; game simulation and AI decisions are unchanged.

| Scenario | Before runs (s) | Before median | After runs (s) | After median | Seconds saved |
|---|---:|---:|---:|---:|---:|
| Mid-season legacy | 22.25 / 23.41 | 22.83 | 16.39 / 17.37 | 16.88 | 5.95 |
| Fresh early-season legacy | 62.49 / 63.70 | 63.10 | 60.86 / 55.99 | 58.42 | 4.67 |
| Fresh early-season new ratings | 88.19 / 89.38 | 88.78 | 61.21 / 59.33 | 60.27 | 28.51 |

Timings are headless wall time, two runs per version, without profiling. Fresh saves start October 20, 2026 and finish November 20; the legacy seed-103 month runs February 15–March 15, 2027. Fresh legacy and new-ratings saves use BOS seed 55. Each pair uses identical starting JSON and SQLite files and the same scratch filename. The before version includes Claude's earlier two optimizations.

Changes in `save.py`:
- Carry a guarded league view between days within one advance call; refresh health, statistics, minutes, plans and staff. Rebuild after materialized roster/contract/free-agent, generated-player, pick, development, season or phase changes, and after waiver resolutions.
- Isolate mutable league tables before possible AI reviews, discard derived indexes, and rebuild the date-sensitive planning view. Quiet days avoid that protective copy. Existing roster-change checks already prevent unnecessary role reassessments, so their decision rule stays intact.
- Reuse attribute summaries only when all formula inputs match (including workload, traits, physical measurements, offensive priors and the new ratings model); cap this memo and release it at the end of the call. The neutral role view now owns read-only indexes instead of rescanning the whole league for each player.

Maintenance: future AI review-window changes must update the isolation guard, and new summary formula inputs must be included in its memo signature. Reuse is confined to one advance call.

Verification:
- All four final outputs per scenario (two before/two after) are equal after removing only `meta.save_snapshot_id`, `history_store.snapshot_id` and `history_store.path`. No other differences were excluded. Canonical JSON encodings also match byte for byte for all 12 outputs (including numeric representation).
- SQLite counts match: mid-season 19,912 history records / 5 commits; fresh legacy 4,432 / 1; new ratings 4,435 / 1. The original seed-103 JSON and SQLite family remain hash-equal to the initial copies.
- 18 focused checks pass, including fresh daily versus reused bulk advancement across a month boundary for both models, fewer rebuilds, fresh-call rebuilding, nested guard changes, date boundaries, summary invalidation and exception/reentrant cleanup.
- `bash scripts/run_core_tests.sh`: 329 tests in 188.913 s, OK (3 skips). Full diagnostic (`PYTHONPATH=src:scripts:tests .venv/bin/python -m unittest discover -s tests`): 1,741 tests in 2,851.795 s; 57 failures, 5 errors, 4 skips. It is not green. Largest group: 34 foundation failures/errors, followed by imported-rookie and other rating snapshots. Other issues include frozen simulation references expecting older box scores, recent draft-rank changes, a mismatched written input artifact, and a 45-second input-builder timeout. Two representative frozen-reference/draft-rank failures reproduce with `save_before.py`; this is not an exhaustive attribution of all broad-suite failures. No broader-suite fixes were made.

Evidence: `output/spd/summary.json`, `before-*/`, `after-*/`, `focused.log`, `core.log`, `full.log`, `full-summary.json`, `baseline-failures.json`, `originals-check.json`, `normalized-bytes-check.json`, `handoff-source-check.json`, the month/compare harnesses, and frozen `save_before.py` / `save_after.py`. The first conservative whole-universe copy was exact but slower; `profile-mid.prof` records that discarded prototype and identified the copying and repeated trait scans.

## Resume state

Complete and ready for coordinator review: all three byte-equality/timing campaigns, 18 focused checks and 329 core tests pass. Full diagnostic completed with the failures/errors above. SPD marked review; changes are uncommitted. Only SPD's save.py, new test, board row and report were edited; concurrent draft/play/storage, ratings and unrelated test changes belong to other work. During the full diagnostic, the coordinator also added returning-player rust display to `player_health_label`; that change was retained. Excluding only that identified display change, the SPD source matches the timed snapshot exactly. Timings/equality refer to the retained snapshots, not subsequent ratings/data work.
