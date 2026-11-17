# Local beta save reliability and recovery

Implemented and verified on October 3, 2026. All save fixtures were created in temporary directories. Real user saves were not modified, migrated, overwritten, or deleted. The repository already contained extensive unrelated changes; this work preserves them.

## Using recovery

- **Export Backup** downloads one `.nbagm.zip` containing the manifest and, when required, its SQLite history. Move this ZIP between computers.
- **Restore Backup…** imports a validated ZIP into a newly named save. Existing names, including names that normalize to the same filename, are rejected.
- **Recover Previous** restores the previous complete local snapshot after confirmation. The current valid save is staged separately before replacement; the recovery source stays intact until the restored manifest is published. If the current manifest is unreadable, its bytes are retained separately and the existing good backup is kept.
- Unreadable saves remain listed with their error. Loading and export are disabled until repaired; recovery remains available when a previous archive exists. A missing manifest is still listed when its previous backup remains.

Do not move only the JSON of a history-backed save. The manifest's `history_store.path` identifies the required database; a restored save can reference a unique generated database filename.

## Implementation and files

| File | Changes for this task |
| --- | --- |
| `src/nba_gm_data/save.py` | Exclusive creation, validation on load, previous-snapshot preservation, stale-writer checks, copy-before-write, durable JSON publication, and rollover history staging. |
| `src/nba_gm_data/history_store.py` | Read-only validation, required-component errors, versioned history rows, checkpoint validation, v1 migration, and forced archival of rollover box scores and team/player logs. |
| `src/nba_gm_data/save_locking.py` | New reentrant thread/process lock and directory synchronization helper. |
| `src/nba_gm_data/save_recovery.py` | New portable exports, ZIP validation, previous backups, and atomic restore publication. |
| `src/nba_gm_data/app_actions.py` | Collision-safe creation, export/restore/recover actions, recovery availability, missing-manifest discovery, and history validation even for cached dashboard reads. |
| `src/nba_gm_data/gui/app.js` | Visible failed saves, actionable picker errors, export/import/recovery handlers, and recovery fallback after failed manual or automatic loading. |
| `src/nba_gm_data/gui/index.html` | Minimal save-picker controls. |
| `src/nba_gm_data/gui/startup.css` | Picker layout using the established beveled button styling. |
| `tests/test_save_persistence.py` | New persistence, validation, migration, stale-writer, and interruption regressions. |
| `tests/test_save_recovery.py` | New collision, concurrency, archive, WAL, recovery, cached-read, and HTTP regressions. |
| `tests/test_rollover_history.py` | New rollover preservation and interruption regressions. |
| `tests/save_recovery_ui.test.cjs` | New JavaScript behavior tests for the picker. |
| `docs/SAVE_RECOVERY.md` | This implementation and verification record. |
| `artifacts/save-reliability/` | Test logs and actual browser screenshots. |

The earlier collision finding was reproduced before modification: `A-B` followed by `A B` left one `a_b.json` containing the second save. The earlier rollover loss was also reproduced: 25 complete results became 15 after rollover. The missing-sidecar empty-history behavior and the UI's unreadable-save filter were confirmed in the current source before changing them.

## Persistence boundary

Cooperating writers, creation, exports, and restores share a per-save lock, including across processes. Lock files remain on disk so waiters cannot split across different lock-file inodes.

Before updating an existing save, the writer captures and atomically publishes `<save>.json.previous.nbagm.zip`. SQLite's backup API captures committed WAL frames. The exact copied database is validated, and abandoned rows beyond the manifest revision are removed from the copy only. JSON-only legacy saves need no database member.

History v2 stores `(kind, record_id, revision)` versions instead of overwriting the previous record. Each manifest identifies its committed revision and history checkpoint. Readers select the latest row version visible to that manifest. Interrupted newer rows remain invisible and are discarded before a retry. The writer works on a deep copy so a failed write does not trim the caller's only remaining hot rows.

SQLite uses `synchronous=FULL`; manifest and archive temporary files are flushed and synchronized before same-directory replacement. Directory entries are synchronized on supported POSIX systems. The JSON replacement is the publication point. Rollover stages all departing box scores, player logs, and team logs for that same commit rather than clearing the final hot tail before archival.

Restore verifies the ZIP member inventory, sizes, checksums, manifest version, history schema, integrity, inventory, and checkpoint before changing the destination. It rejects unexpected or duplicate members, traversal/absolute/nested paths, NUL filenames, symlinks, encrypted entries, unsupported compression, missing components, and unsupported future formats. No archive paths are extracted directly. The archive limit is 128 MiB compressed and 512 MiB expanded.

Restore writes history to a new generated filename, then atomically switches the manifest to it. Old component files remain intact. A fresh manifest snapshot identity prevents a save opened before restoration from subsequently overwriting the restored state, even when revision numbers match.

## Focused review fixes — October 3, 2026

The independent review reproduced two defects: failed Recover Previous publication could overwrite its own recovery source, and accepted legacy manifests without `meta.id`, revision, or checkpoint metadata could bypass stale-writer checks. Both reproductions were added as regressions and failed against the implementation before these fixes. The normally generated save regression already passed and remains covered. The separate prospect identifier mismatch was unchanged in that review; it is resolved by the identifier follow-up below.

When replacing a valid save A with recovery snapshot B, restore now publishes `<save>.json.restore-pending.nbagm.zip` first. This self-contained archive preserves A's JSON and SQLite history using the existing WAL-aware backup path. An optional `restore_snapshot_id` field in `backup.json` records the checkpoint of the intended restored manifest. The previous archive continues to contain B while its new history file and manifest are staged.

- Before manifest replacement, an exception or process exit leaves A current and B's source archive unchanged. Retry discards the uncommitted pending intent and restores B, including its SQLite history.
- After manifest replacement, B is current. The pending archive remains until A has been atomically published as the previous snapshot. Retry completes this promotion and reports the committed recovery; it does not restore A over B.
- Removing the pending archive completes the operation. A later, separate Recover Previous request can intentionally restore A. Subsequent writes and restores also resolve pending intent under the existing save lock before starting another commit. Read-only loads do not perform this cleanup.

The pending archive is retained if validation or backup promotion fails. Keep it with the save files when resuming an interrupted operation, and use a build with these fixes to resume it. If the current pair or pending archive is damaged, validation stops further mutation and preserves the available archives; an intact archive can still be imported into a new save name. Interruption can leave unused generated history files or temporary files; automatic history-generation cleanup remains outside this task. Staging and promotion temporarily require additional archive disk space and use the existing backup size limits.

Legacy manifests with an absent `meta` section or without `meta.id` remain readable without migration. Their first successful write or restore publishes the existing revision/checkpoint metadata. All subsequent writers must match the current manifest checkpoint, regardless of save ID or supplied revision. A copy opened before that publication must be reloaded before saving. No ID requirement or manifest, history, or portable-backup format version change was introduced.

Focused follow-up validation:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -m unittest test_save_persistence test_save_recovery test_rollover_history -v
node --test tests/save_recovery_ui.test.cjs
```

**50 Python tests and 9 picker tests passed.** New coverage checks the source archive's bytes and restored contents after ordinary failures; retry with all SQLite history; promotion and cleanup errors; actual child-process exits at ten boundaries around pending-archive, history, manifest, previous-archive publication, and cleanup; retry in a fresh process; a write after interrupted recovery; identity-less legacy manifests with present or absent metadata; supported first legacy writes; and normally generated saves. Process-exit tests bypass exception cleanup. They do not establish physical power-loss or storage-device durability. The original acceptance logs and counts below describe the earlier implementation run.

## Acceptance results

| Criterion | Result |
| --- | --- |
| Duplicate and normalized-name collisions | Passed, including one-winner thread and spawned-process creation races. |
| Final ten results and all logs through rollover | Passed for pending results, repeated rollovers, and failure/retry during publication. |
| Missing/corrupt/incompatible components remain actionable | Passed for JSON, SQLite, missing rows/checkpoints, unsafe references, future versions, and cached reads. Legacy v1 limitations are below. |
| Complete portable export/restore | Passed for full history, JSON-only saves, WAL frames, concurrent writer/export, and export after interruption. |
| Restore validation and previous-save preservation | Passed, including malformed archives, unsafe members, interruption before manifest publication, and damaged current saves. |
| Minimal save-picker recovery controls | Passed in JavaScript behavior tests and actual browser interactions. |
| Relevant existing tests all green | Earlier run: six identifier errors plus the additional rollover/postseason/free-agency errors below. All nine affected checks pass after the identifier follow-up below. The entire application suite was not rerun. |

## Exact checks and results

Commands below ran from the repository root. `pytest` was unavailable in the existing virtual environment, so the repository's unittest tests were run directly.

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest test_save_persistence test_save_recovery test_rollover_history -v
```

**43 passed.** This includes a child process deliberately exiting with code 71 after the SQLite commit and before JSON publication, transaction failure, manifest-publication failure and retry, restore-publication failure, and backup-publication failure. These are failure-path checks, not an inference from normal writes.

```sh
node --test tests/*.test.cjs
node --check src/nba_gm_data/gui/app.js
DEVELOPER_DIR=/Library/Developer/CommandLineTools /usr/bin/git diff --check
```

**75 JavaScript tests passed**, including 9 new picker behavior tests and 66 existing checks. Syntax and whitespace checks passed. JavaScript suites mix source-pattern checks with executed functions in a mocked DOM/API; they are not browser tests.

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest \
  test_foundation.DataFoundationTests.test_save_writes_replace_atomically_for_concurrent_gui_reads \
  test_foundation.DataFoundationTests.test_new_save_seeds_startup_free_agents_and_event_collections \
  test_foundation.DataFoundationTests.test_app_action_layer_creates_local_save_and_serves_core_payloads \
  test_foundation.DataFoundationTests.test_local_gui_server_serves_static_assets_and_json_actions \
  test_foundation.DataFoundationTests.test_league_save_creation_advancement_and_views \
  test_fantasy_draft test_dashboard_metrics test_team_block -v
```

**29 ran: 23 passed, 6 errors.** Failures were the app-action/core-payload test, GUI-server JSON-action test, league advancement test, and three fantasy-draft tests (`test_multiplayer_fantasy_draft_stops_on_human_turns`, `test_single_player_fantasy_actions_start_before_dashboard_and_advance_explicitly`, `test_untouched_malformed_fantasy_save_repairs_to_current_draft`). The server test surfaced HTTP 400; the underlying creation/defaults path and the other errors encounter the same missing prospect `id`.

Additional existing checks:

```sh
PYTHONPATH=src:tests python3 -m unittest test_foundation.DataFoundationTests.test_rollover_generates_future_schedule_and_future_games_simulate -v
PYTHONPATH=src:tests python3 -m unittest test_foundation.DataFoundationTests.test_league_save_creation_advancement_and_views test_foundation.DataFoundationTests.test_playoff_and_offseason_scaffolds_use_save_state -v
PYTHONPATH=src:tests python3 -m unittest test_foundation.DataFoundationTests.test_save_writes_replace_atomically_for_concurrent_gui_reads test_foundation.DataFoundationTests.test_free_agency_day_advances_with_one_save_commit -v
```

The rollover check errored; the advancement/postseason pair both errored; the last pair had the atomic-read test pass and the free-agency test error. All failures reach the existing prospect-ranking mismatch: `draft.board_entry_payload` supplies `prospect.prospect_id`, while `ensure_league_save_defaults` expects `prospect.id`. Reconstructing the original read/write functions in a temporary package reproduced the rollover and advancement failures; replacing persistence with plain JSON reads/writes also reproduced the free-agency failure. No gameplay change was made to address this unrelated defect.

Actual browser checks used the Codex in-app browser against a loopback server with an explicit temporary save directory. Verified unreadable-save visibility, actionable missing-history/JSON errors, disabled loading/export, previous-backup recovery, ZIP upload into a new named save, and malformed-upload rejection. A restored history fixture was checked on disk: original marker, 15 box scores, 15 player logs, and 15 team logs. Two browser-produced downloads matched the exact temporary fixture manifest and passed portable restoration; those test downloads were moved from Downloads into the temporary fixture directory for cleanup. The browser download-event helper timed out, so the downloaded files were verified directly instead. Screenshots record the failed-save and successful-restore picker states.

## Compatibility and remaining risks

- JSON manifests retain `league_save_v1`. Embedded-history saves and SQLite history v1 remain readable without migration during reads. The first successful history write migrates to v2 and preserves a complete previous archive. The existing `.pre-history-v1.bak` is also retained where applicable.
- History v2 and generated restore filenames require this implementation. Opening upgraded saves with older builds is unsupported; use a compatible build and a portable export. No real saves were migrated as part of this work.
- Legacy v1 lacks reliable identity/checkpoint metadata and sometimes overcounted repeated UPSERTs. Validation detects missing files, bad schemas, corrupt payloads, and wholly missing declared categories, but cannot reliably distinguish every preexisting partial loss or same-shaped substituted v1 database. Migration cannot recreate history already lost by an earlier rollover or overwrite.
- An actual process exit and injected persistence failures were tested. Physical power loss, storage-device failure, filesystem-specific durability, Windows locks, and Windows/macOS-to-Windows portability have not been tested. Locks coordinate this implementation; external or older writers that ignore them are outside that guarantee.
- Complete backups and integrity checks add save latency and disk use. Mature multi-decade save performance was not benchmarked. Archives above the stated limits are rejected; because the previous backup is mandatory, an over-limit or failed backup prevents the next save from publishing.
- Old history generations and unreadable manifests are retained intentionally. Repeated restoration can increase disk usage; automated deletion/compaction was not added.
- The prospect field mismatch is resolved by the follow-up below. No claim is made that the entire application test suite is green.
- API security, packaging, simulation balance, dashboard redesign, cloud storage, and multiplayer development were outside this task.

## Prospect identifier follow-up — October 3, 2026

`board_entry_payload` exposed the real canonical prospect identifier only as `prospect.prospect_id`. `ensure_league_save_defaults` and the saved rank-change display consume `prospect.id`. This caused a `KeyError` when creating a preseason baseline and caused existing baselines to be ignored by the display. Generated fallback boards already expose canonical `id`.

The producer now also exposes `prospect.id`, with the exact same value as `prospect.prospect_id` and the canonical prospect record's `id`. The existing `prospect_id` API field remains available. No identifiers are synthesized, entries skipped, rank values recomputed, or existing baseline maps rewritten. Scouting, ranking, simulation, and recovery implementations are unchanged.

`tests/test_prospect_identifiers.py` uses the actual canonical-board payload producer and preseason-baseline consumer with temporary saves. It checks every stored rank key against the source board entries and real canonical prospects, both identifier fields, persistence/reload, preservation of existing baseline maps, and use of those maps by the rank-change display. Before the fix its two tests reproduced one `KeyError` and one display assertion failure; after the fix both pass.

All commands used `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests` and the existing `.venv/bin/python -B`. All save/database fixtures were temporary. No real saves were modified, no long season soak ran, and no subagents were used.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_prospect_identifiers test_save_persistence test_save_recovery test_rollover_history -v
```

**52 tests passed in 22.973s** (2 new identifier regressions and all 50 existing focused persistence/recovery/rollover tests).

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_foundation.DataFoundationTests.test_app_action_layer_creates_local_save_and_serves_core_payloads \
  test_foundation.DataFoundationTests.test_local_gui_server_serves_static_assets_and_json_actions \
  test_foundation.DataFoundationTests.test_league_save_creation_advancement_and_views \
  test_fantasy_draft.FantasyDraftTests.test_multiplayer_fantasy_draft_stops_on_human_turns \
  test_fantasy_draft.FantasyDraftTests.test_single_player_fantasy_actions_start_before_dashboard_and_advance_explicitly \
  test_fantasy_draft.FantasyDraftTests.test_untouched_malformed_fantasy_save_repairs_to_current_draft -v
```

**All 6 previously failing checks passed in 70.503s.** The HTTP save-creation request returned 200.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -m unittest \
  test_foundation.DataFoundationTests.test_rollover_generates_future_schedule_and_future_games_simulate \
  test_foundation.DataFoundationTests.test_playoff_and_offseason_scaffolds_use_save_state \
  test_foundation.DataFoundationTests.test_free_agency_day_advances_with_one_save_commit -v
```

**All 3 previously blocked checks passed in 37.693s.** Whitespace validation also passed. There are no remaining blockers for these requested checks; broader application testing was outside this follow-up.

Logs: `artifacts/save-reliability/prospect-identifiers-before.log`, `prospect-identifiers-focused.log`, `prospect-identifiers-six-checks.log`, and `prospect-identifiers-additional-checks.log`. The earlier acceptance logs above are retained unchanged as historical evidence.
