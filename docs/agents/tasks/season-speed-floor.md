# SEASON-SPEED-FLOOR

Progress: 7/7 - done, ready for review

## Objective
1. Speed: a month of regular season (AI front offices included) inside 10-20 s in season 1, and no slower in later
   seasons. Cut the once-per-day league rebuild (`canonical_with_save`: ratings-model fit, estimated roles) by caching
   with invalidation; prune save data nobody reads (old injury events, long-retired players) without hiding anything the
   user can see. Prove the same seeded month gives the same results.
2. Eight-player floor: rest and shutdown decisions keep at least eight players available, healthiest rested first.
   Injured players stay out. Changes late-season outcomes (labelled).

## Boundaries
Season loop, save, health and caching code, tests, this file. Not `src/nba_gm_data/stage2/`, ratings, or the board.

## Steps (M = 7)
1. Read context, runner, notes
2. Profile a month at season 1 and season 3 starts
3. Cache the per-day league rebuild
4. Prune save data (check every reader first)
5. Eight-player floor in rest/shutdown
6. Measure: speed s1-s4 before/after, save size per season, floor run, determinism
7. Focused tests, full suite (`--workers 2`), browser tests if GUI-read data changed; one commit, not pushed

## Working data
- Season starts copied from the S2-MULTISEASON run into `output/ssf/run/phase_saves/` (rollover saves = Oct 1 of
  seasons 2-4; season 1 is a fresh save).

## Resume state
- Probe: `scripts/season_month_probe.py` (one season start, Oct 20 -> Nov 30, timing, optional cProfile, `--compare A B`
  for exact save equality, `--no-floor` for cache-only proof runs). `output/ssf/run_pair.sh <code dir> <tag> 1 2 3 4`
  runs seasons two at a time. Baseline code copy: `output/ssf/base_code` (HEAD 043644b7).
- Baseline (laptop, s/30 days): s1 28.1, s2 37.8, s3 47.2, s4 42.0.
- Round 1 (role cache + injury index + floor): s1 26.4, s2 35.0, s3 43.1, s4 38.2. s1, s2, s4 identical saves; s3
  differs only because the floor recalled two players (CLE, Oct 26-27 2028).
- Done: draftee-role cache (role_estimate.py), injury events by player (health.py), eight-player floor (health.py
  `eight_player_floor`), waiver-wire pruning at rollover (save.py `prune_settled_waiver_entries`), tests in
  tests/test_season_speed_floor.py (7 pass).
- Round 2 (+ one-batch copies of season stats and generated rows): proof runs with the floor off are identical to
  the baseline in all four seasons (`output/ssf/nf2.compare`). Side-by-side timing, old vs new at the same moment
  (`output/ssf/ab.summary`): s1 31.0 -> 29.1, s2 40.5 -> 36.6, s3 46.9 -> 40.6, s4 41.4 -> 37.2 s per 30 days.
- Azure four-season run with the new code: `output/ssf/floor4` (job ssf-floor4, seed 20261125, MIA), compare with
  `../s2-multiseason-c06763/output/s2ms/current` for short-handed games and save size per season.
- Readers checked: injury events stay (injury model history, team page injury timeline); past schedules stay
  (opening-night and season-window readers); waiver wire: only pending / running-contract / last-season entries read.

## Report

**TL;DR**
- **Eight-player floor works:** AI teams no longer play short-handed because of rest. In four seasons, AI team-games
  with fewer than eight players getting minutes fell from 21 to 2, and both of those were injuries (a 12-man Denver
  roster with four hurt; a Toronto playoff game, where nobody rests). This changes late-season results, as intended.
- **A month is 6-13% faster, with identical results:** side by side on the same machine, s/30 days: season 1
  31.0 -> 29.1, season 2 40.5 -> 36.6, season 3 46.9 -> 40.6, season 4 41.4 -> 37.2. **The 10-20 s target is not
  met:** the league rebuild turned out to be a smaller share than the earlier estimate; most of a month now is the
  games themselves and the AI front offices, both outside this task.
- **Save growth is mostly real history** the user can see; I pruned only settled waiver-wire entries (season-4 save
  27.7 MB vs 28.4 MB before).

### What changed
1. **Draftee roles are remembered** (`role_estimate.py`). Every full league rebuild re-ran the "which veterans is this
   draftee most like" search; by season 3 that was half of each rebuild. The answer now is kept per exact set of
   veteran ratings, heights and roles and per draftee's own ratings; any change makes a new key. 0.27 s -> 0.003 s.
2. **Injury history looked up by player** (`health.py`). Each injury draw scanned every injury record in the league
   (5,000 by season 4); the records are now grouped by player once. Same history, same order.
3. **Season stats and generated players/traits/picks copied in one batch** (`save.py`) instead of ~900-3,000
   separate copies per rebuild or daily refresh. Same data.
4. **Eight-player floor** (`health.py`, `eight_player_floor`). The day's health pass now decides who is hurt and who
   the coach rests first, then checks the count. If fewer than eight players are available, the coach brings back
   the healthiest players he rested or shut down (least fatigue and rust, then his usual minutes), one at a time
   until eight are available; a recalled player's shutdown ends. Injured players stay out. Players the GM chose to
   rest stay out (the user's call). The rest log records each recall ("recalled to keep eight players available").
   When the floor doesn't bind, results are identical to before (same per-player random draws).
5. **Settled waiver-wire entries dropped at the season rollover** (`save.py`, `prune_settled_waiver_entries`):
   entries resolved before the season that just ended, for contracts with no season left. Nothing reads them: the
   waiver room and waiver processing read pending entries, stretch elections need a running contract, camp bonuses
   and the recently-claimed trade rule look only at recent ones, and the transaction log keeps every release.

### What I checked and did not prune
- **Old injury events stay.** The injury model uses each player's past injuries (decaying with time) for his
  future risk, and the team page's injury timeline lists past injuries, retired players' included.
- **Past seasons' schedules stay.** Opening-night and season-window helpers read them for any season label.
- **Retired players' data is small** (1.3 MB of 28 MB by season 4) and feeds their player pages.
- Where the growth really is (season 1 -> 4 rollover): season history +4.0 MB, injury events +2.8, generated
  players' ratings +1.9, waiver wire +1.0 (now held at ~300 entries), schedules +0.9, season recaps +0.9, playoff
  stats +0.8, game summaries +0.7. All user-visible or engine inputs.

### Speed: where a month goes now
In a profiled season-1 month: games ~31%, AI front offices ~30% (the October extension passes alone ~16%, AI trade
search ~14%), daily team planning ~7%, full rebuilds ~9%, daily refreshes ~7%. Full rebuilds happen ~27-33 times a
month (roster moves, AI checks), not once a day; the daily path already carries the league over and refreshes it.
Later seasons are slower for many small reasons (bigger tables to copy and encode, more players, larger save writes),
not one big one. Note the measured window (Oct 20 - Nov 30) includes the rookie-extension deadline, so it is heavier
than a mid-season month. Suggested follow-up (outside this task): the game engine's per-player feature vectors are
recomputed ~350 times a day because minutes change daily (memo misses), and the AI extension/trade passes.

### Evidence
- **Determinism:** with the floor switched off (`--no-floor`, proof runs only), the end-of-month save is identical
  to the old code's in all four seasons (everything except the random snapshot id and the canonical-data
  fingerprint, which depends on the folder the data was loaded from). With the floor on, seasons 1, 2 and 4 are
  identical too; season 3 differs only because the floor recalled two players for Cleveland on Oct 26-27, 2028.
- **Speed table** (`output/ssf/ab.summary`, old and new run at the same time, laptop shared with other sessions):

  | Season start | Old s/30 days | New s/30 days |
  |---|---|---|
  | 2026 | 31.0 | 29.1 |
  | 2027 | 40.5 | 36.6 |
  | 2028 | 46.9 | 40.6 |
  | 2029 | 41.4 | 37.2 |

- **Four-season run** (Azure, seed 20261125, MIA, `output/ssf/floor4`), against the earlier run:

  | | Old code | New code |
  |---|---|---|
  | AI team-games with < 8 players getting minutes | 21 | 2 (both injuries only) |
  | Floor recalls per season | - | 33, 38, 31, 28 |
  | Save at each rollover (MB) | 12.1, 17.2, 22.6, 28.4 | 12.1, 17.4, 22.4, 27.7 |
  | Waiver-wire entries at rollover | 108, 324, 529, 755 | 110, 299, 301, 302 |

  The user team (MIA) still had short games (2 before, 9 now): the test run gives it a fixed nine-man minutes plan
  with everyone else locked at zero, so injuries inside the nine leave six or seven. That's the GM's plan, not rest;
  a "fill to eight when the plan runs short" rule for the user's team would be a separate decision.
- **Tests:** new `tests/test_season_speed_floor.py` (7 tests: floor recalls healthiest first, no recall at eight,
  short roster, GM rest left alone; role cache follows every input; injury index; waiver pruning). Focused health,
  rest, injury and role tests pass (69). Full suite (`--all --workers 2 --js`): 2,592 tests, 17 failures, and the
  `startup_video` browser test fails; all 18 fail the same way on the old code (missing output files in a worktree,
  ratings/pilot fixtures, packaging, two GUI concept checks).
- New tool: `scripts/season_month_probe.py` (time one season-start month, `--profile`, `--compare`, `--no-floor`).
