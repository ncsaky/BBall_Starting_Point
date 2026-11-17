# New-career pre-opening-day entry — October 30, 2026

New standard careers now start **October 20, 2026**, one day before the earliest **league-wide** regular-season game in their generated 2026–27 schedule (**October 21**). The date comes from the generated schedule, not the selected team's opener or a claim about the real NBA calendar. The current schedule is generated from the existing corrected 2025–26 template; this task does not replace that template.

`save.py:_create_league_save` generates the schedule once, derives the entry date and uses it for current date, phase, legal actions, creation metadata and the welcome item. `meta.gameplay_start_date` distinguishes these new saves from existing careers. `meta.source_snapshot_date` retains the historical `CANONICAL_START_DATE` anchor of **July 28, 2026**. The constant, canonical files, source verification dates and imported contracts/rosters/traits remain unchanged.

Creation sets the lifecycle cursor to the entry date. It initializes current roles and plans with the existing deterministic algorithms; it does **not** advance calendar days, run games/health simulation, apply monthly development, search the market or execute AI transactions. All 30 opening rosters currently contain 15 players after the existing source-roster normalization. That normalization policy is unchanged. Additional human roster overflow still blocks advancement before opening games, and the new first-season guard uses the schedule-derived opening gate.

Health is projected to the entry date only for current availability: an injury whose explicit return date has already elapsed is cleared; a future return date or unresolved ongoing injury remains. Injury history and its dated evidence are retained. No games missed, fatigue/rust decay or development is fabricated for the skipped offseason. Contracts retain their source salary/guarantee/option terms; the existing protection logic evaluates them at the actual gameplay date. Calendar movement does not update the underlying evidence.

New fantasy careers remain in mandatory draft setup at the same pre-opening date. Completion initializes the drafted rosters' opening roles/plans and enters preseason on October 20. All **450 draft selections and scores** match the captured pre-change setup, and source contracts/contract overrides are unchanged. Repeated finalization is a no-op, preventing a completed career from being rewound. Legacy fantasy setups without the new marker keep their dates; loading no longer unconditionally forces a valid fantasy date back to July. Missing dates still use the appropriate new marker or legacy July fallback.

Existing standard careers are not advanced or migrated. No new runtime initialization is invoked by their load/repair path. An archived busy checkpoint retained its date, games, transactions, development, injury history and schedule state, and its source file hash remained unchanged.

## Verification

Evidence root: `output/preopening-career-start/`. `pre-edit.json` and `reference/src/` preserve the **post-settlement-optimization backend before this startup change**. Completed settlement performance measurements, comparisons and checkpoint fixtures were not rewritten or rerun against changed new-save defaults. That reference can be selected with PYTHONPATH when reproducing the completed performance backend.

**126 focused tests passed**, including eight new real-action startup tests. They cover:

- Earliest regular game selection from an unsorted schedule, excluding exhibitions and rejecting an empty schedule.
- New create actions for different teams, deterministic role/planning initialization, zero hidden games/trades/development and correct dates/legal actions.
- First next-event reaching only the league's opening games, exact opening game/health IDs, no duplicate games on a repeated endpoint, and the following next-event.
- Export/restore/reload determinism at matching first-game endpoints, including full ordered progress events.
- User roster cutdown stops before games, preserving the on-disk save on rejection.
- Past/future/unresolved injury handling and unchanged source contract/guarantee/option records.
- Existing checkpoint date/history preservation, legacy fantasy dates, missing-date repair, new fantasy completion and finalization idempotence.

Three wider regression checks fail **identically on the captured pre-edit backend** and are explicitly excluded from the focused runner, not silently relaxed:

1. `test_full_fantasy_draft_replaces_rosters_and_preserves_contracts`: its existing first-round Giannis/Luka expectation fails under the current source/model. The independent 450-pick before/after comparison is exact; no draft scoring was changed to satisfy the stale expectation.
2. `test_identityless_legacy_first_write_remains_supported_and_rejects_stale_copy`.
3. `test_legacy_embedded_history_migrates_without_loss_and_keeps_original`.

The latter two observe the pre-existing `staff_season_changes: {}` read repair. Their behavior was left unchanged. `preexisting-failure-check.txt` records all three against pre-edit code; `targeted-regression.txt` records the wider current run. `tests.json` lists the exclusions and focused result.

The first broad regression selection accidentally included a full-year, no-games lifecycle unit and was interrupted; it is not the final verification suite. A subsequent test-runner attempt needed a `__main__` guard for existing multiprocessing persistence tests and was stopped/corrected. These exploratory logs are retained separately. The final runner excludes full-year lifecycle tests. No full-season game simulation or ten-season study was launched; real new-career advancement checks cover only the first two game dates.

Reproduce serially from the repository root:

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python scripts/verify_new_career_start.py
PYTHONPATH=src:scripts .venv/bin/python scripts/capture_new_career_setup.py \
  --output output/new-career-setup-current
PYTHONPATH=output/preopening-career-start/reference/src:scripts \
  .venv/bin/python scripts/capture_new_career_setup.py \
  --output output/new-career-setup-reference
```

The setup capture refuses existing output directories. It creates standard and fantasy saves and completes only the setup draft; it deliberately does **not** advance the old July career across months. Compare `setup.json`'s fantasy selection arrays and contract hashes. The current capture under `setup-after/` starts both modes October 20; the reference under `setup-before/` starts July 28. `verification.json` records the comparison and production-source scope: only `save.py` and `fantasy_draft.py` changed in this task. Shared GUI files and the completed settlement implementation were untouched.

## Remaining dated-data gaps

This is a gameplay entry-date change, **not a refreshed opening-night dataset**. July-anchored rosters, contracts, medical evidence, staff/source metadata and preseason research can still omit later real-world moves or contain differently dated evidence. In particular, the previously identified Lillard contract-accounting issue and later roster-event reconciliation remain separate work; no inferred transaction, guarantee waiver, trait retuning or roster rewrite was applied here. Historical injury event status/text remains source evidence even when its explicit return date makes current availability healthy. Fatigue/rust are not extrapolated through unplayed months. Existing general season/phase calendars still use their established calendar rules; only the new first-season entry/cutdown gate is schedule-derived.

The verified isolated preview is **http://127.0.0.1:8793/**. It runs the new backend against `output/preopening-career-start/preview-saves`, with a newly created October 20 career. HTTP creation/dashboard verification, PID and source hashes are recorded in `preview.json`. Older previews, including the completed settlement preview on 8792, were preserved.
