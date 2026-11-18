# Season speed (claude/hungry-sinoussi-b6f0a0, started 2026-11-18)

**Objective:** make a whole simulated season (regular season, playoffs, offseason, with AI front offices) much
faster without changing results. Exact speedups first; anything that changes outcomes goes in separate, labelled
commits with the scorecards re-run.

**Boundaries:** no edits to `ratings_model.py`, `health.py`, the `draft.py` generator, `trait_adapter.py`,
`impact_value.py` (another branch is merging there). LeBron's trade exception stays. Commit on this branch only.

## Resume state

- Harness: `scripts/check_month_parity.py season-prepare|season-run|compare --season` (see "How to rerun").
- Checkpoints: `output/month-speed/season/{legacy,inputs}/seeds/NN/` (history DB gzipped).
- Baseline runs: label `base` (`--ref 580e38f`).
- Disk was full on 2026-11-18 (2 GB free; the main session's scratch folder holds 12 GB). Keep `--jobs` at 2.

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
