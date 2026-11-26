# SEASON-ARCHIVE

Progress: 7/7 - done, ready for review

## Objective
Move finished seasons out of the live save so it stays about the same size every season. At each season rollover the
finished season's detail goes to a compressed archive file beside the save (one per season); the live save keeps what
the live game reads. History readers load archives on demand with a small cache. Normal play never needs an archive.
Prove: same seeded four-season results (Azure), same history page/API content, save and archive sizes per season,
month speed per season before and after.

## Boundaries
`save.py`, rollover and season-transition code, history readers in `app_actions.py`/`app_server.py` (only the ones
that must be redirected; a Fable GUI session may edit display parts), the game-history database code, tests, this file.
Not `src/nba_gm_data/gui/`, `src/nba_gm_data/stage2/`, ratings, or `docs/agents/BOARD.md`. One commit, not pushed.

## Steps (M = 7)
1. Read rules, prior task notes, sibling notes
2. Map the save: tables, sizes, readers
3. Design the split; implement archive module and the rollover split
4. Redirect the history readers
5. Tests (split, readers, rollover)
6. Prove: Azure four-season before/after, history response parity, sizes, month speed
7. Full suite (`--all --workers 2 --js`), report, commit

## Save map (season-4 rollover save, old code run `output/s2ms/current`, MB at rollovers 1-4)
| Table | s1 | s2 | s3 | s4 | Per season | Readers |
|---|---|---|---|---|---|---|
| season_history | 1.29 | 2.55 | 3.80 | 5.05 | +1.25 | engine: only the latest finished season (prior-season minutes for options, award baselines, staff review, waiver priority uses team_records); display: career table (all seasons), recaps, dynasty records (team_records) |
|  - of which player_season_stats | | | | | 1.15 (78% is per-game id lists nobody reads) | |
| injury_events | 0.73 | 1.54 | 2.41 | 3.32 | +0.85 | engine: every past event of a player (decaying risk weights, no cutoff), current-season counts, active injury by date; display: team page injury timeline (full rows) |
| generated_traits | 0.61 | 1.21 | 1.81 | 2.40 | +0.6 | live players (draft classes); not history |
| season_schedules | 0.58 | 0.87 | 1.16 | 1.45 | +0.29 | engine: current season; season-window/opening-night helpers for any label (first/last regular dates) |
| season_slideshows.outlooks | 0.26 | 0.53 | 0.79 | 1.06 | +0.26 | display only (slideshow reopen list) |
| playoff_player_stats | 0.30 | 0.54 | 0.79 | 1.04 | +0.25 | cumulative across seasons (never reset: bug, see report); per-game id lists only used to skip a game counted twice |
| game_result_summaries | 0.23 | 0.45 | 0.68 | 0.90 | +0.22 | lookups by game id (current schedule, playoffs, player game logs = current + previous season) |
| award_preseason_baselines | 0.05 | 0.11 | 0.18 | 0.24 | +0.065 | current season's award race only |
| transaction_logs, development_events, news... | | | | | flat | already moved to the game-history database (sqlite) |
| waiver_wire | | | | | held at ~300 entries by SEASON-SPEED-FLOOR pruning | |
| contract_overrides, camp, waived_salary_obligations | | | | | +0.13-0.17 each | live contract/camp state |

## Design
- Rule: the latest finished season stays whole in the live save (the engine reads it); seasons older than that are
  archived at the first save write after the rollover (inside `write_save`, like the sqlite history step).
- Archive file: `<save stem>.season-<label>.<hash>.json.gz`, write-once, content-addressed; manifest in the save under
  `season_archive` (file name, sha256, sizes, what it holds).
- Moves per archived season: history entry detail (player stats, playoff bracket, draft order, recap); schedule (stub
  keeps metadata and the first and last regular-season game so season-window answers are unchanged); preseason outlook;
  game score summaries; award preseason baselines; the playoff per-game id lists of that season; injury events
  (full rows to the archive, a compact row with every field the engine reads stays live).
- Readers redirected: player career table, slideshow reopen/list, team page injury timeline.

## Resume state
- Done: `season_archive.py` (split, write, readers, cache), hook in `write_save`, readers redirected (career table
  `career_stats.player_career_seasons(save_path)`, slideshows `stored_recap/stored_outlook/available_slideshows`,
  team injury timeline `weekly_efficiency_events`), export/restore carry archives (`save_recovery.py`), run tools
  copy archives, tests `tests/test_season_archive.py` (9) + updated `tests/test_rollover_history.py`.
- Parity tool: `scripts/season_archive_parity.py dump/compare` (old code = `output/sa/base_code/src`).
  Old run's season-4 regular-season-end save: 101 views identical (`output/sa/parity/*_re4.json`).
- Smoke on the old run's rollover saves (`output/sa/smoke`): live save MB 12.1, 15.0, 17.8, 21.0 (was 12.1, 17.2,
  22.6, 28.4); archives 0.20-0.29 MB each.
- Bug found and fixed in the archive merge: a view that loads the whole history database (social feed) and then
  writes rebuilds old playoff score lines; they were archived again as duplicates and rewrote three archive files.
  The merge now replaces same-key rows and skips the write when nothing changed (test added). Old-run season-4
  rollover save: 102 views identical.
- Azure after2 run (final code): job `sa-after2`, out `output/sa/after2`. Speed pairs: `output/sa/run_speed.sh
  output/sa/after2 1 2 3 4` (November, old vs new side by side) once before/after2 phase saves are back.
- Full suite (`--all --workers 2 --js`): 2,608 tests, 6 failures + 12 errors, all 18 identical on the baseline code
  (`output/sa/base_failing.log`); browser: only `startup_video` (video absent in worktrees).
- Azure after run (first code version): job `sa-after`, out `output/sa/after` (log `output/sa/after.log`). It ran the split before a
  pure speed-up of the per-write screening (same eligibility; checked equal on the old run's rollover saves).
- Baseline code copy: `output/sa/base_code` (HEAD 21c499b6). Azure "before" run: job `sa-before`, out
  `output/sa/before` (log `output/sa/before.log`).

## Report

**TL;DR**
- **Finished seasons now move out of the save.** At each new season, the detail of every season older than last
  season goes to one small compressed file beside the save (0.2-0.3 MB per season). The save now grows about
  2.7 MB a season instead of about 5.1 MB; at the start of season 5 it is 20.2 MB instead of 27.5 MB.
- **Nothing changes in play or in what you see.** A seeded four-season run on Azure gives exactly the same 5,262
  games, box scores and saves as the old code once the archived rows are put back. Every history page I checked
  (102 views: player career tables, team injury timelines, every recap and outlook, standings, leaders, playoffs,
  box score) returns exactly the same data.
- **Speed: no real change yet.** November takes 27-29 s per 30 days in seasons 2-4 with old and new code alike
  (season 3: 29.3 to 28.6). The benefit is that history no longer piles up in the file the game reads and rewrites
  every day; it does not make today's months faster.

### Save size per season (start of each season, MB; same seed, Azure)
| Season starting | Old save | New save | Archive files beside it |
|---|---|---|---|
| 2027-28 (after 1 season) | 12.2 | 12.2 | none (last season stays in the save) |
| 2028-29 | 17.2 | 14.9 | 2026-27: 0.20 |
| 2029-30 | 22.2 | 17.3 | + 2027-28: 0.28 |
| 2030-31 | 27.5 | 20.2 | + 2028-29: 0.28 |

End of each regular season: old 10.4, 21.8, 26.4, 31.9; new 10.4, 21.8, 24.2, 27.0.

### What moved where
The latest finished season stays whole in the save, because the game itself reads it: last season's minutes for
option decisions, last season's stats for the award race baselines and the preseason outlook, the staff review and
waiver order. Each older season moves to `<save>.season-<season>.<hash>.json.gz`:
- its player season stats, playoff bracket, draft order and year-end recap (the season keeps its standings, awards
  and draft result in the save);
- its schedule (the save keeps the schedule's details plus its first and last regular-season games, the only dates
  the game still asks about for old seasons);
- its preseason outlook, its award-race baselines and its game score lines;
- the per-game lists inside the playoff stat totals (only used to avoid counting a game twice);
- the full write-up of its finished injuries (diagnosis, notes, context). A short version with every field the game
  reads (dates, body part, severity, sources, games missed) stays, so the injury model's weighting of each player's
  past injuries is exactly the same.

History screens read the archive files when needed and keep the last few in memory. Normal play never opens one: if
a file went missing, only the old-season detail on history screens would be blank. Exports carry the archive files
and restores put them back under the new save's name. The automatic "previous save" backup leaves them out, because
they are written once and never change.

### Readers I redirected
- Player page career table (`career_stats.player_career_seasons`, now given the save path).
- Slideshows: reopening an old recap or outlook, and the list of slideshows you can reopen (`season_slides`).
- Team page injury timeline (`app_actions.weekly_efficiency_events`).
All other readers of these tables only look at the current or last season (checked one by one: see the save map
above), and the parity check covers the rest.

### Found along the way
- **Bug (not fixed, needs your call): playoff stats are never reset between seasons.** `playoff_player_stats` keeps
  adding up across every postseason, so the playoff leaders page shows career playoff totals by season 2, and the
  Finals MVP is picked from the champion's Finals games summed across every Finals the player has played in. A reset
  at the rollover (the finished season's totals going to the archive) is the natural fix, but it changes Finals
  MVP results, so I left it out of this change.
- **Run-to-run variation in the AI trade search** (see Evidence): same seed and code, a negotiation once took a
  different path; outcomes and games were unaffected in this run.
- Fixed in my own code before the final run: the social feed loads the whole game-history database, and the next
  write rebuilt old playoff score lines. The archive step filed them a second time. It now replaces rows with the
  same game id and writes nothing when nothing changed (test added).

### Still growing (about 2.7 MB a season), and why I left it
Generated players' trait rows (+0.6 MB a season: live draft classes replacing real players, each trait row repeating
the player's whole career-capacity block), the short injury rows (+0.6), contract overrides (+0.17), training-camp
logs (+0.13), dead-money records (+0.13) and several smaller tables. These are live state or are read by the engine
or the offseason code in ways I couldn't prove safe to move in this task. A follow-up could compact the trait rows and
move finished camp and dead-money records.

### Evidence
- Same results: `output/sa/before` (old code, HEAD 21c499b6) vs `output/sa/after` (new code), seed 20261125, MIA,
  4 seasons on Azure: games identical; all 8 season saves and the final save identical after putting archived rows
  back (`scripts/season_archive_parity.py saves`). Final-code run (`output/sa/after2`): games, all season-start
  saves and the final save identical too; one mid-run snapshot (end of season 4's regular season) differs in one AI
  trade negotiation (MIN-OKC over Aday Mara) that ended without a trade. The first new-code run matched the old code
  exactly there, and the two new-code runs differ from each other, so it is run-to-run variation in the AI trade
  search (its cache hit counts differ between runs), not the archive. Worth a separate look: same seed, same code,
  slightly different negotiation path.
- History views: `scripts/season_archive_parity.py dump/compare`, old code vs new code on the same save: 101 views
  identical (season-4 regular-season end), 102 identical (season-5 start, three seasons archived).
- Month speed (November, old and new side by side on the laptop, seconds per 30 days; end-of-month saves identical
  after putting archives back): s1 18.0 / 18.0, s2 27.2 / 27.2, s3 29.3 / 28.6, s4 26.8 / 26.7.
- Tests: `tests/test_season_archive.py` (10: split, engine answers unchanged, write, rewrites, duplicates, export and
  restore, previous-save recovery, missing and damaged files); `tests/test_rollover_history.py` updated (score lines
  of old seasons are in the archive). Full suite (`--all --workers 2 --js`): 2,608 tests, 18 failing, all 18 fail
  the same way on the old code (ratings and pilot fixtures, packaging, two GUI concept checks, one asset-valuation
  check); browser: only the start-screen video test (video file absent in worktrees).
