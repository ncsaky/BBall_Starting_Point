# Season speed (claude/hungry-sinoussi-b6f0a0, 2026-11-18)

**TL;DR**
- **A full season is about 20% faster** with results unchanged: old ratings 609 s → 485 s, new 94-input ratings 819 s → 661 s (paired runs, same machine and load).
- **Offseason and playoffs got 30–45% faster**; regular-season months got 5–15% faster. The trade-deadline run is nearly unchanged (126 → 122 s), because what remains there is ~20,000 genuine AI trade evaluations.
- **Every one of the 46 phases (23 per rating mode) produced an identical save, history database and GUI response** to the original code, twice.

## What changed, in plain words

1. **Saving was slow for a silly reason.** The save file was written with Python's slow, pure-Python JSON writer. The fast built-in writer produces the exact same text in a fraction of the time (2–3 s → ~0.3 s per save). The automatic "previous save" backup also no longer re-reads the file the writer had just read.
2. **Offseason and playoff actions now reuse the same helpers regular-season months already had.** Each GUI action shares one copy of the starting league (serialized once), the game simulation's reference tables (loaded once, not per playoff game) and the remembered player rating summaries.
3. **Playoff rounds stopped deep-copying the whole league on entry** (about a second per round, and it defeated the shared copy above).
4. **Free agency, re-signing and waiver claims ask "would this signing make our final 15?" hundreds of times a day.** Each check rebuilt a league-wide ratings index from scratch and scored every player twice. It now reuses the league's index and scores each player once.
5. **Team contention strength is remembered by its exact inputs.** Each AI "front-office context" recomputed all 30 teams' strength even when most rosters had not changed (83% of those recomputations are now skipped in a regular month).
6. **The same save file is parsed once per action** instead of 7–34 times (kept by file identity; a new save always has a new file).
7. **Labelled, not a game change:** the automatic previous-save backup now uses fast compression (~0.6 s saved per write; that backup file is ~40% larger, about 10 MB instead of 7 MB). Portable exports are unchanged. Revert `bb94721` alone if backup size matters more.

Nothing about ratings, the game simulation, the coach model or AI decision rules changed.

## Before / after per phase (paired, wall seconds)

Each phase was replayed from the same checkpoint with the original engine (`580e38f`) and then the new one (`5faaed3`), back to back, one process per rating mode.

| Phase | Old ratings before → after | New ratings before → after |
|---|---|---|
| Preseason to Nov 20 | 35 → 28 | 50 → 40 |
| Regular months (Nov 20 → Jan 21, 2 actions) | 57 → 53 | 78 → 75 |
| Deadline run (Jan 21 → Feb 5) | 126 → 122 | 135 → 127 |
| After deadline (Feb 5 → Mar 8) | 29 → 26 | 58 → 50 |
| Rest of regular season (Mar 8 → Apr 13, 3 actions) | 30 → 28 | 47 → 42 |
| **Playoffs (play-in + sim all)** | **64 → 39** | **94 → 52** |
| Playoffs exit to Jun 22 | 8 → 6 | 16 → 11 |
| Lottery + enter draft | 11 → 8 | 17 → 14 |
| Draft sim-all | 20 → 16 | 28 → 30 (noise; cpu 27 → 26) |
| After draft (waivers, to Jun 27) | 21 → 16 | 32 → 25 |
| **Re-signing / open market** | **21 → 12** | **26 → 17** |
| **Free agency, 5 day clicks** | **126 → 85** | **143 → 99** |
| Free agency end (to Sep 1) | 19 → 13 | 32 → 22 |
| Training camp | 12 → 9 | 22 → 16 |
| Preseason Oct → Nov 1 | 30 → 25 | 43 → 40 |
| **Season** | **609 → 485** | **819 → 661** |

Machine: 10 cores, shared with other sessions (load 15–30), so absolute numbers are pessimistic; CPU time moved the same way (587 → 466 s and 792 → 638 s).

**Against the 10–20 s month target:** a normal month is now ~24–29 s (old ratings) and ~34–50 s (new ratings) on this loaded machine; free-agency days 12–24 s; playoffs 39–52 s for the whole postseason.

## Parity evidence

- `scripts/check_month_parity.py` gained a whole-season mode: `season-prepare` plays one season through the real GUI actions and keeps the save right before every action; `season-run` replays each action from its checkpoint in a fresh process; `compare --season` checks the save JSON (only random snapshot ids removed), every history-database row and the GUI response.
- Season: GSW, seed 17, new save in Oct 2026 played to Nov 1, 2027 (23 actions), in both rating modes.
- Results: original vs new **IDENTICAL on all 46 phases**, in two separate rounds (`base`/`a3` and the paired `tb`/`tn` pass). Batch 1 alone was also identical on the 42 phases that completed before the disk filled.
- The original engine is deterministic on every phase except the GUI's lottery reveal, which draws from system randomness on purpose (`seed=None`). The harness pins that draw for both engines.
- `NBA_GM_RUNTIME_AUDIT=1` re-checks the riskier caches at run time: the shared starting league is re-serialized and compared on every rebuild, and every contention-memo hit is recomputed and compared. Playoffs and a regular month ran clean and identical with it on.

## Tests

- `bash scripts/run_core_tests.sh`: **334 tests OK** (2 skips).
- New `tests/test_season_speed_exact.py` (8 tests): save encoder matches the streaming writer, parsed-save cache hands out private copies and follows replacement, action scope sharing, contention memo keys follow every input and match fresh results.
- Four save tests hooked `json.dump` to simulate a crash mid-write; they now hook the new `encode_save_json` seam (same failure points).
- `tests.test_foundation`: 6 failures with **both** the original and the new code, the same list (pick-swap sweeteners, a free-agency rating-label check, trade-block explanation). Pre-existing.

## Commits

| Commit | Kind | What |
|---|---|---|
| `9994575` | exact | Fast save encoder; archive reuses the writer's parse; per-action shared caches; signing checks share the ratings index and score once; season harness |
| `59fd51e` | exact | Contention-strength memo; parsed-save cache |
| `dcee51e` | exact | Playoff entry points stop deep-copying the league; harness pins the lottery draw |
| `bb94721` | **labelled** (backup file bytes only) | Fast compression for the automatic previous-save backup |
| `5faaed3` | tests | `tests/test_season_speed_exact.py` |

## What is left, and options for the coordinator

- **The deadline run and in-season trade days are now almost entirely real AI trade evaluations**: ~20,000 package evaluations at ~3 ms each over Jan 21 → Feb 5, spread evenly across roster forecasts, pick valuations and legality checks. No single exact fix left there is worth much; I checked whether the same roster forecasts recur across contexts (42 of 7,601 do).
- **To reach 10–20 s months, fewer evaluations are needed, which changes AI behavior.** The levers are in `transactions.simulate_ai_trades`: buyers per target (6 / 12 / 18 by search depth), packages per buyer (5 / 12 / 24) and the 120-entry trade block. Halving deadline breadth would cut that run by roughly 40%. The betting-odds and real-stat scorecards would not measure this (they replay games, not AI trades); it needs its own multi-season league-health check. Not done here.
- **Possible inconsistency found (not changed):** `roster_forecast.ForecastSnapshot.view` drops every league key starting with `_`, including `_ratings_model`. So in new-ratings saves, the AI's hypothetical-roster forecasts (contention strength, trade roster outlooks) use the old hand-weighted impact instead of the fitted value the card shows. This may conflict with rule 4 (what the user sees should match what the engine uses). Fixing it changes AI decisions.
- **Smaller exact ideas not done:** league rebuilds still cost ~0.2 s each (125 in a postseason, one per game); the development-application and rotation-projection steps inside them could be tightened. Regular-season game simulation is ~20% of a month.
- **Disk:** the drive was at 99–100% for much of this session (down to 230 MB free at one point); several parity runs failed with "no space left" and had to be rerun. The main session's scratch folder holds ~12 GB.

## Resume state

- Harness: `scripts/check_month_parity.py season-prepare|season-run|compare --season` (see "How to rerun").
- Checkpoints: `output/month-speed/season/{legacy,inputs}/seeds/NN/` (history DB gzipped).
- Baseline runs: label `base` (`--ref 580e38f`).
- Done; awaiting coordinator review. Runs: labels `base`, `a3`, `tb` (original), `tn` (new) under `output/month-speed/runs/`.
- Keep `--jobs` at 2 or less: each replay needs ~150 MB of temporary files.

## Season shape (GSW, seed 17, one action per GUI click, as `build_mature_fixture.py` plays it)

| # | Phase | Action | Legacy s | New ratings s |
|---|---|---|---|---|
| 0 | preseason | advance to Nov 20 | 28 | 40 |
| 1–2 | regular season | month | 27–30 | 38–39 |
| 3 | deadline run | Jan 21 → Feb 5 | 140 | 138 |
| 4 | after deadline | Feb 5 → Mar 8 | 30 | 56 |
| 5–7 | regular season | Mar 8 → Apr 13 | 30 | 41 |
| 8 | playoffs | play-in + sim all | 67 | 97 |
| 9 | playoffs exit | to Jun 22 | 9 | 14 |
| 10–11 | lottery, enter draft | | 10 | 14 |
| 12 | draft | sim all | 20 | 28 |
| 13 | after draft | to Jun 27 (waivers) | 24 | 31 |
| 14 | re-signing | open market | 23 | 29 |
| 15–19 | free agency | 5 days | 135 | 143 |
| 20 | free agency end | to Sep 1 | 27 | 30 |
| 21 | training camp | to Oct 1 | 15 | 21 |
| 22 | preseason | to Nov 1 | 31 | — |
| | **season** | | **645** | **~760** |

(Unprofiled `season-prepare` runs, two seasons playing side by side on a loaded machine.)

## Top costs (cProfile, legacy, original code)

Profiled times are ~2× wall time; shares are what matter.

**Cross-cutting**
- **Save writes:** 2.5–5 s per write. The save JSON was streamed through Python's slow pure-Python JSON encoder
  (`json.dump`), the previous save is re-parsed twice for the recovery archive, and the archive deflates ~60 MB.
  10–25% of every offseason action; ~40 writes a season.
- **League rebuilds** (`canonical_with_save`): 0.3–0.4 s each, 125 in the playoffs, 59 in the post-draft waiver
  run. Outside regular-season advances nothing reused the serialized starting league.
- **Transaction context builds:** ~1 s each (team strategies, player valuations, pick values); 45 at the deadline,
  16 in the draft, 19 in a regular month.

**Deadline run (Jan 21 → Feb 5), 309 s profiled:** AI trade searches 230 s (75%): roster outlook per package 72 s,
two-deep rotation forecasts 53 s, offer-package building 41 s, transaction contexts 41 s, applying 26 trades 38 s
(of which re-checking the live roster 31 s).

**Playoffs (play-in + all rounds), 134 s profiled:** league rebuilds 48 s (one per game day plus one per game),
save writes 29 s (one per round), rating summaries 15 s, sim reference tables re-read per game 8 s.

**Draft sim-all, 51 s:** draft-night AI trade checks 30 s (transaction contexts 17 s), save writes 13 s.

**After the draft (to Jun 27), 53 s:** waiver claims 37 s: one league rebuild per waived player (59) and, for each
of 30 teams, a "would he make our final 15" counterfactual that rebuilt a league-wide ratings index every time.

**Re-signing 55 s / free-agency day 62 s:** the same signing counterfactual (`roster_signing_plan`) 21 s, of
which rebuilding the ratings index ~10 s; role targets 12–14 s; save writes 6–17 s; free-agency AI trades 12–19 s.

## How to rerun

```
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py season-prepare --model legacy   # ~12 min
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py season-run --model legacy --label base --ref 580e38f --jobs 2
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py season-run --model legacy --label after --jobs 2
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py compare base after --season legacy
```

Each step replays one GUI action from the save as it was right before that action, in a fresh process, and
compares the saved JSON, every history-database row and the GUI response.
