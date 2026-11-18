# Month speed (claude/month-speed, overnight 2026-11-18)

**TL;DR**
- **November month (GUI advance action):** about **143 s → 31 s** (legacy ratings) and **144 s → 40 s** (new ratings), on a heavily loaded machine. In CPU time: 128 → 28 s and 116 → 35 s.
- **Trade-deadline month** (Jan 10 → Feb 10, 35 AI trades): about **549 s → 275 s** (CPU 459 → 220 s). Still far above the 10–20 s target.
- **Results unchanged:** every commit gives the same save and the same history rows as `bba9a83` in all three test scenarios (two seeds, both ratings models). The last commit is labeled "behavior-sensitive" for review, and it also came out identical.

## What changed, in plain words

Almost all of a month was the AI front office looking for trades. Three things made it slow:

1. **Pick rights were re-explained thousands of times.** For every trade package it considered, the engine rebuilt the description of every pick swap and protected pick in the league, and each rebuild compared every swap against every other swap. Now each rebuild does a single pass. Inside one trade search the answers are also remembered, with a check that no pick changed owner and no swap changed status.
2. **Searches ran on days when nothing could come of them.** On most autumn market days the calendar opens a "listening" review with zero trade slots and zero offer slots. The engine still ran two full trade searches and then threw both results away. Those days now write the same "reviewed" record directly. A second, separately labeled commit also skips the AI-to-AI search on days that only have offer slots for the user.
3. **The league was copied too slowly.** The game copies the whole league many times a day for safety. Those copies now use a faster method that gives the same result. The starting league is serialized once per advance instead of on every rebuild. The game-sim reference tables (schedule, box scores, odds) are loaded once per advance instead of every day.

Nothing about ratings, the game simulation, the coach model or AI decision rules changed.

## Commits (oldest first)

| Commit | Kind | What |
|---|---|---|
| `82990a4` | exact | Pick presentation: one-pass grouping and one baseline per ranked-pool call, plus a guarded memo inside a trade-search context. Market review compares its inputs by pickle first and uses the JSON digest only when pickles differ. `copy_plain` (pickle copy) for hot deep copies. New-ratings rebuild reuses derived traits for unchanged inputs; the registry is parsed once and trait weights cached. Pick-term previews snapshot only the picks they refer to. Adds `scripts/check_month_parity.py` and `tests/test_month_speed_exact.py`. |
| `751eb2f` | exact | Both searches skipped on empty listening days, and so is the protective league copy on those days. Sim reference tables loaded once per advance, without the redundant index build. Memo uses LRU and skips re-validation for nested calls. Preview cache stores pickle bytes. Rotation assignment builds candidate tuples only when they improve. Injury model resolves its data root once. |
| `e196fa8` | exact | Cache the deterministic court-pocket hash (`spatial._stable_unit`, typed LRU). |
| `5b0c8dc` | exact | Serialize the starting universe once per advance call (`canonical_with_save`). |
| `f0db820` | exact | Fallback valuations built only when a player has no valuation; role-multiplier loop no longer rebuilds a set per league player. |
| `8466f06` | **behavior-sensitive** | On days with offer slots for the user but no AI-to-AI slot, skip the AI-to-AI search, whose result can never be chosen. It is labeled because the user-offer search then starts without the caches that the first search used to warm. Some of those caches are shared between the base league and pick-term previews (see below), so in principle the offers found could differ. Measured identical on all three scenarios, twice. If in doubt, revert this commit alone. |

Leftover local branches `claude/month-speed-unordered` and `claude/month-speed-unordered2` came from reordering commits so the labeled one is last. They hold the same final tree and are safe to delete.

## Timings (final, paired)

Machine: 10 cores shared all night with full test suites, Codex, a betting-odds validation and other jobs (load average 40–200), so absolute times are pessimistic. Each run is one GUI `advance_save` action through `dispatch_app_action`: save load, AI front office, games, history archive, save write and dashboard refresh. Runs were interleaved (base, exact, final) per scenario and repeated twice. Values below are the mean of the 2 runs, wall / CPU seconds.

| Scenario | Before `bba9a83` | Exact commits `f0db820` | All commits `8466f06` |
|---|---|---|---|
| November, legacy ratings (BOS, seed 55) | 143 / 128 | 48 / 41 | **31 / 27** |
| November, new ratings (LAL, seed 7) | 144 / 116 | 42 / 35 | **40 / 35** |
| Jan 10 → Feb 10 with deadline stop (BOS, seed 55) | 549 / 459 | 340 / 255 | **275 / 220** |

Individual runs: `output/month-speed/final_round.log`. Seed 7's November has no offer-only days, which is why the last commit doesn't change it.

## Profile, before and after (legacy November, cProfile)

| | Before (`bba9a83`) | After (`751eb2f`) |
|---|---|---|
| Whole month under cProfile | 966 s | 129 s |
| AI trade searches | 688 s (15 searches) | 67 s (8 searches) |
| Pick entitlement and label rebuilds (inside searches) | ~300 s | ~10 s |
| Market-review input digest and context builds | 60 s | 9 s |
| Daily lifecycle | 52 s | 19 s |

What remains (unprofiled phase timers, `output/month-speed/phase_timer.py`):
- **November:** trade searches on the 1–5 days that have slots (the largest part), game simulation ~8 s, lifecycle including team-plan refresh ~6 s, garbage collection ~3 s, dashboard refresh ~2 s.
- **Deadline month (~220 CPU s):** trade searches ~140 s, league rebuilds ~27 s (121 rebuilds), applying 35 AI trades ~24 s, waivers ~14 s, garbage collection ~8 s.

## Parity evidence

`scripts/check_month_parity.py` can be rerun:

```
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py prepare        # starting saves, once
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py run --label before --ref bba9a83 \
    --scenario nov-legacy --scenario nov-inputs --scenario deadline-legacy
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py run --label after \
    --scenario nov-legacy --scenario nov-inputs --scenario deadline-legacy
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py compare before after \
    --scenario nov-legacy --scenario nov-inputs --scenario deadline-legacy
```

**Scenarios:**
- `nov-legacy`: BOS, seed 55, old ratings, Nov 1 → Dec 1.
- `nov-inputs`: LAL, seed 7, new ratings, Nov 1 → Dec 1.
- `deadline-legacy`: BOS, seed 55, Jan 10 → Feb 5 deadline stop, then confirmed → Feb 10. 35 AI trades.

The starting saves are fresh GUI saves advanced to the start date. `--ref` extracts that commit's `src/` under `output/month-speed/code/<ref>` and runs it against the same data. Seeds live in `output/month-speed/seeds/` (git-ignored; `prepare` rebuilds them).

**What is compared:**
- Save JSON, with only these removed: `meta.save_snapshot_id`, `history_store.snapshot_id` and `history_store.path` (random per write).
- Every history table, row by row (only the random `history_commits.snapshot_id` is left out).
- The GUI response, without absolute paths and the dashboard cache `revision` (file modification time).

**Results.** Every comparison against `bba9a83` was **IDENTICAL** on save, history and GUI response:
- `bba9a83` against itself, three times (the determinism check).
- Each exact stage on all three scenarios: `82990a4`, `751eb2f`, `e196fa8` and `5b0c8dc` (via `--ref`), and `f0db820` (via `--ref`, twice).
- `8466f06` (all commits), all three scenarios, twice.

That is 18 of 18 in the final round alone.

**Extra checks:**
- The pick-presentation fast paths were shadow-run against the original module over Nov 1–6: about a million calls, all equal.
- The shared sim reference tables and the shared starting universe were byte-identical before and after full months, both the deadline month and new-ratings November. The reuse-per-advance changes depend on that.

## Tests

- New `tests/test_month_speed_exact.py` (8 tests) checks that:
  - the memo returns the plain results, follows owner, status and term changes, and hands out private copies;
  - `copy_plain` matches `deepcopy`, including shared references;
  - the review input comparison behaves like sorted JSON;
  - trait weights return fresh dicts.
- `bash scripts/run_core_tests.sh` on the final commit: **330 tests OK** (2 skips). This needs the git-ignored `output/settlement-materialization-pass/inputs` linked from the main checkout; without it, one setUpClass errors.
- **Full suite** on `751eb2f` and on `bba9a83`, run side by side in snapshot folders: 14 failures and 19–20 errors each, and **the failure lists are identical**. The base run's one extra error is the new test module, which cannot import on old code. The failures are pre-existing and environmental: missing git-ignored `output/` fixtures for experiment tests, a subprocess hash-seed test, frozen prospect-learning and development references, Windows packaging preflight. The later commits (`e196fa8` through `8466f06`) were covered by core tests and the parity runs, not by another full-suite run.
- **Real-stat scorecard** (`calibration_report.py --games 1230 --mode replay-real-minutes`, new ratings): **18/18 league metrics in band**. The betting-odds run was not repeated: game results are byte-identical in every parity run, so neither scorecard can move.

## Not done, and notes for the coordinator

- **Still above the 10–20 s target.** November is now roughly 30–40 s on this loaded machine, probably about 20–30 s on a quiet one. The deadline month is several times over. What remains is real trade-search work on days that have slots: about 2.5 ms per package evaluated, with 5,000–30,000 evaluations a month. Reaching the target needs one of two things:
  - a cheaper evaluation pipeline (the roster-projection and valuation rebuilds inside each evaluation), or
  - fewer evaluations, for example narrower search breadth, or not running the user-offer search at depth 2 every day. This option changes AI behavior.
- **A latent order dependence in existing code.** `trade_wants.asset_matches` and `wants_for_team` keep caches in dicts that pick-term preview copies share with the base search context (`{**canonical}` copies the cache reference). A pick match computed on a preview can be returned for the base league. It is deterministic today, but any change to search order can change results through it. Worth fixing before more speed work in the search: key those caches by league view, or give previews their own.
- **The pick memo guard** costs about 50 µs per lookup. It checks owners, statuses, rights holders, nested anchors and field counts, not every field. That fits how a search context is used today (nothing edits it during a search). A future in-place edit of other pick or term fields during a search would not be noticed.
- `save._copy_runtime_tree` and `utils.copy_plain` now do the same thing; one could replace the other.
- **Ideas considered but not done:**
  - `gc.freeze()` after loading the universe. Garbage collection is about 4–5% of a month.
  - Reusing the lifecycle's transaction context for that day's market review. Not exact: the inputs differ by that day's team plans.
  - Indexing `pick_by_id` and `resolve_player`, which are linear scans called tens of thousands of times. Not exact if ids ever repeat.
- `scripts/run_core_tests.sh` was edited locally to use the main checkout's `.venv`. That edit is not committed.
