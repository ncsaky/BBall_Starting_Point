# Historical shooting import fix — November 13, 2026

Stage A is implemented and separately verified before Stage B. The importer recognizes ESPN's `fieldGoalsMade-fieldGoalsAttempted` as **total** FG, followed by supported `fg`/`FG` aliases. It does not add threes to total makes, clamp contradictions, infer attempts from points or rewrite retained evidence.

## Changes and caller audit

`research.py: parse_boxscore_stat_row` is called only by `parse_espn_summary_boxscore`. `parse_made_attempt` had no other production callers. Both now use strict observed integer pairs, returning `null` for absent/invalid/DNP shooting values. Genuine `0-0` or `0-4` from a played record remains numeric. The three-point and FT pairs use the same contract. Independent minutes, points, rebounds, assists, etc. retain their prior parsing behavior; this is not a general ingestion rewrite.

Each shooting family carries raw value, selected source key, observed/missing/invalid/DNP status and alias conflicts. Long keys take precedence; malformed long values cannot be hidden by a valid conflicting alias. Row flags detect impossible total/three/two relationships and scoring identities without changing the observed counts. A summary stat-key/value length mismatch is flagged rather than silently certified. DNP preserves identity and raw source strings, with nullable shooting fields.

Parsed games carry `espn_game_shooting_v2_2026_11_13` and source game/date/ending-year season/type checks. `historical_shooting.py: historical_shooting_view` adds a **private** calibration view: final status, source identity, unique player/team identity, valid row arithmetic and independently reconciled team shooting are required for complete shooting eligibility. Missing source headers, nonfinal records, duplicate/missing identities and unresolved team differences fail that gate. Repeated fresh/legacy views preserve provenance rather than reinterpreting totals.

Current imported-history consumers use availability/minutes, scores, outcomes and other independent fields; no current game path performs arithmetic on these newly nullable imported shooting pairs. Generated game/save box-score fields remain numeric and unchanged. The career-season/offense-prior parser is a separate source path and is not migrated by this fix. Raw historical readers remain compatible; new shooting-calibration consumers must use the explicit eligibility view rather than treating legacy numeric zero as observed data.

## Cache version and recovery

No cache was overwritten and no network request ran. A future missing-only refresh preserves existing records exactly and reports their legacy count; its `new_record_shooting_parser_version` labels newly parsed records, **not the whole mixed cache**. Preserved old games do not silently acquire the new per-game version or repaired values.

The explicit legacy view quarantines FGM/FGA regardless of whether their old zeros happen to equal the truth. Original FG values remain in metadata, other fields remain available, and FGA stays unknown. `allow_reconstructed_fgm=True` separately permits a derived FGM only when integer/nonnegative scoring components and independent final-team FGM reconcile. It never qualifies that row as complete shooting data. DNP rows are excluded rather than becoming observed zero-attempt samples. This is conditional recovery, not a claim that independent team reconciliation proves every individual attribution.

All seven unresolved final-team groups remain blocked: CHI in games 401810150, 401810372, 401810547, 401810560, 401810577, 401810633 and 401810760. No residual was distributed among players. A follow-up audit during Stage B found 60 otherwise algebraically eligible zero-minute legacy rows. The opt-in recovery gate now also requires positive recorded minutes, keeping those ambiguous old zeros unknown; this conservative Stage A follow-up was separately retested. Six nonfinal games also remain excluded. No blanket refetch or derived FGA was attempted.

## Evidence

**17 focused tests pass**: 13 new parser/view tests plus four existing research checks. Retained raw responses for games 401809243, 401810557 and 401869187 match all **70** research-normalized rows by ESPN athlete ID and team. Of these, **69 played rows** pass complete source/row/team gates; the remaining row is Chris Youngblood's explicit DNP with source `0-0` strings. Those strings parse as zeros in provenance, while DNP output shooting values remain null. This distinction intentionally refines the earlier research wording “70 usable rows.”

The unchanged 1,310-game cache contains 34,325 player rows. Its FG values remain quarantined. The opt-in view can conditionally reconstruct FGM for 28,129 positive-minute, non-DNP rows; this count excludes DNP, ambiguous zero-minute legacy records and nonfinal rows and is therefore narrower than research's earlier 34,216 record-level recovery count. Every such view still has null FGA and false complete-shooting eligibility. The raw cache SHA-256 remains `9a4cf3b1bfcc4b9b605a09d4d744e5a7779a7b031ad35fc97337245a5d66339f`.

Evidence: `output/historical-shooting-import-fix-2026-11-13/` retains the pre-edit parser, file hashes, exact diff, tests, three parsed source views and audit JSON. Only `research.py` changes among the tracked pre-existing source/GUI/canonical/cache/approval files at Stage A completion; the new strict/view helper is separate. There are no simulation, GUI, save, source-cache or preview changes in this stage. An initial existing-test import failed because `scripts` was absent from PYTHONPATH; the documented command includes it and all 17 pass.

Reproduce offline:

```sh
PYTHONPATH=src:tests:scripts .venv/bin/python -m unittest test_historical_shooting_parser test_guarantee_research -v
PYTHONPATH=src .venv/bin/python scripts/verify_historical_shooting_fix.py --output output/historical-shooting-fix-recheck
```

The second command writes only the selected output directory, never the cache/research sources, and uses no network. This parser correction provides cleaner future evidence; it does not calibrate the next experimental model or repair the historical dataset in place.
