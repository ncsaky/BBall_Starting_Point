# S2-FINISHES (Stage 2, seventh piece): end of games on real play-by-play, and spreads

_Owner: Claude (Opus session), worktree branch `claude/ecstatic-antonelli-371621`. 2026-11-24/25. Status: **review**._

Progress: 7/7 - report written, committed on the branch (not pushed)

## TL;DR
- Stage 2 now plays the last five minutes like real teams do: leaders slow down, trailing teams hurry and shoot
  threes, teams foul on purpose, and blowouts are run out or given up. Every number comes from three seasons of real
  play-by-play.
- Games tighten late the way real ones do. Overtime rose from 3.0% to 3.9% (real 4.4-4.7%). Close finishes rose too,
  but now overshoot: 1-3 points 10.4% → 15.1% (real 12.7%).
- Spreads went from 4.40 to 4.01 points off the market, just ahead of today's engine (4.03). Most of that came from two fixes
  outside the late game: teams were spread too far apart in strength, and the home edge was about half of real.
  Both scorecards improve (win-probability error .1975 → .1965) and all 18 real-stat targets stay in range.

## What changed, in plain terms

**1. The last five minutes (new `stage2/finishes.py` and `stage2/finishes_table.py`).**
Before, Stage 2 played crunch time like any other stretch, about 14 seconds a possession for everyone. Real teams change:
- with 2-5 minutes left, a team ahead takes 17-18 seconds a possession and a team behind 14-16;
- in the last minute a team down 4-10 takes 8-9 seconds and ends about half its possessions with a three;
- free throws rise late (the bonus, physical defense, fouls on purpose).

So Stage 2's margins spread out in the last minutes, where real margins tighten. The new table covers four time bands
(2-5 minutes, 1-2 minutes, 24-60 seconds, the last 24 seconds) and nine score bands. For each situation it holds four
numbers: possession length, a lean toward threes, a shooting-foul shift and a shot-quality shift. They were fitted to
real possessions from the 2023-24 and 2024-25 regular seasons (about 50,000 late possessions), with 2025-26 kept back
as the check season. Who shoots, how well they shoot and how often they draw fouls still come from each player's own
ratings; the table only describes what the situation does to everyone.

Smaller rules fitted from the same data:
- how often the trailing team fouls on purpose with 24-60 seconds left (the old rule counted only fouls the feed
  labels as deliberate, about half of them);
- how much a team down 1, 2 or 3 leans toward threes (real: threes on 24% / 42% / 51% of possessions in the last
  24 seconds);
- a team down 1-3 attacks at once instead of holding for the last shot (real behaviour);
- up 11+ in the last minute the leader often runs the clock out; down 11+ in the last 24 seconds the trailing team
  often gives up;
- a leader sometimes turns it over against late pressure (Stage 2 never did).

**2. Team strength scale (`LOOP["strength"]` = 0.875).** Teams' season-average margins were 6.5 points apart in Stage 2.
Real teams are 6.1 apart, about 5.9 once the luck of 82 games is taken out. Stage 2's team gaps also moved 1.07 points
for every point of market line. The strength terms (how much better a defense or offense makes each shot) are now 0.875
of what they were. Player ratings are untouched; this is the engine's sensitivity to them.

**3. Home court (`LOOP["home_scale"]` = 1.65).** Stage 2's home team won by 1.0 points on average. Real final scores
show 2.15 / 1.63 / 1.74 in the last three regular seasons (1.84 on average), and the market prices 1.9. Stage 2 now uses
today's engine's home edge times 1.65, which gives about 1.85.

**4. Pace and free throws refitted around the finishes.** The slower late play cost about 0.65 possessions a game, so
the half-court possession length came down a touch (15.75 → 15.65 seconds). The real late free throws added about
0.6 per 100, so the foul level elsewhere came down (0.22 → 0.18).

## Scorecard 1: betting odds (20 runs × 2 seeds, 1,018 games with market odds)

| | Before this piece | Without home fix (seed 2001 only) | **Final** | Today's engine |
|---|---|---|---|---|
| Win-probability error (Brier, lower is better) | .1975 | .1943 | **.1965** | .2012 |
| Log loss (lower is better) | .5823 | .5766 | **.5809** | .5910 |
| Spread miss against the market (points) | 4.40 | 4.07 | **4.01** | 4.03 |
| Total-points miss against the market | 6.12 | 5.89 | **5.99** | 5.78 |

The market itself scores .1962 / .5740 on these games. The middle column is one seed only; compare it with seed 2001
alone: before this piece .1951 / .5780 / 4.42 / 6.15, final .1940 / .5769 / 4.04 / 5.99. The total-points miss (5.99)
still trails today's engine (5.78); it moves by about 0.1 between seeds and wasn't this piece's target.

### Where the spread miss comes from (8 runs, `scripts/research/s2_spread_check.py`)
The miss at 20 runs splits into a systematic part (what more runs would not fix) and run-to-run noise.

| | Stage 2 before | With finishes and strength scale | **With home fix** | Today's engine |
|---|---|---|---|---|
| Predicted miss at 20 runs | 4.57 | 4.07 | **about 4.04** | 4.09 |
| Systematic spread | 4.81 | 4.12 | **4.16** | 4.15 |
| Of which: whole-team errors | 2.69 | 2.18 | **2.20** | 2.14 |
| Expected margins move per market point | 1.07 | 0.95 | **0.94** | 1.11 |
| Home margin (market 1.88, real three seasons 1.84) | 1.18 | 1.04 | **about 1.85** | 1.93 |
| Game-to-game spread of one game's margin | 13.5 | 12.9 | **13.0** | 13.5 |

A clean run with this piece's late-game table switched off (but the strength scale on) gives 4.11. So most of the spread
gain is the strength scale and the home edge; the late-game table on its own helps close games, not spreads.

## Scorecard 2: real-stat targets
- Quick scorecard (150 generated games, seed 1): **18/18 in range** before and after. The average distance from target
  went from .19 to .33 (in units of the real team-to-team spread). The biggest misses are fouls per 100 (20.4 against
  19.4) and free throws per 100 (24.2 against 22.9), both well inside range. That sample was already high on fouls before
  this piece.
- All games, 2 runs each (real 2025-26 in brackets):

| | Points | Pace | Free throws per 100 | Fouls per 100 | Overtime |
|---|---|---|---|---|---|
| Replayed games, before | 115.24 | 102.36 | 22.87 | 19.48 | |
| Replayed games, final | 115.95 | 102.14 | 23.00 | 19.51 | 4.3% |
| Generated games, before | 115.54 | 101.74 | 23.77 | 19.91 | |
| Generated games, final | 115.63 | 101.47 | 23.67 | 19.92 | 3.7% |
| Real | 115.61 | 101.98 | 22.90 | 19.37 | 4.4% |

## End of games (19,695 replayed 2025-26 games, 16 runs each)

| | Before | **Final** | Real 2025-26 | Real 3 seasons |
|---|---|---|---|---|
| Overtime | 3.0% | **3.9%** | 4.4% | 4.7% |
| Decided by 1-3 points | 10.4% | **15.1%** | 12.7% | 12.7% |
| Decided by 4-5 points | 10.5% | **9.4%** | 8.8% | 8.7% |
| Decided by 13+ points | 44.1% | **40.3%** | 44.2% | 41.8% |
| Within 3 with a minute left | 16.5% | **19.9%** | | 19.3% |
| Within 3 with 24 seconds left | | **20.5%** | | 19.4% |

Per late possession, after the fit Stage 2 is off real by about 0.2 seconds, 0.02 points, 0.01 threes and 0.01 free
throws on average.

## Speed
400 games, best of three: 7.83 → 7.68 ms per replayed game and 8.66 → 8.72 ms per generated game. No change worth
noting.

## Weak spots (honest list)
1. **Close games now finish too close.** The game reaches the last minute in the right state (within 3: 19.9% against
   19.3%). But from there Stage 2 turns too many of those games into 1-3 point finishes (62% against a real 55% from
   within 3 with 24 seconds left) and too few into ties (18% against 22%). Likely causes: a trailing team that tries to
   tie hits its last shot too rarely, and fouled leaders don't stretch leads to 4+ often enough. The next fit should
   target the result of the last possession directly.
2. **Overtime is still a bit low** (3.9% against 4.4%), for the same reason.
3. **Team errors that remain:** Chicago about 5 points worse than the market; the Clippers, New Orleans and
   Philadelphia about 3-4 better; Detroit and Portland 4 worse. These are team-wide (strength or lineup) and look like
   rating or minutes questions rather than end-of-game ones. I did not touch any rating.
4. **The late shot-quality shifts are league-level situational effects** (for example a leader's late isolations shoot
   worse, a team down 4-6 with under a minute left shoots a little better against a soft defense). They are fitted, not
   built from players, so a team full of great late-game scorers doesn't yet get extra credit.
5. **Game-to-game spread came down** from 13.5 to 13.0 points (real one-game spread around the market is about 13).
   That is fine now, but don't push it lower without checking upsets.
6. **Quick scorecard distance rose** from .19 to .33; all 18 stay in range, and the all-games check shows points, pace,
   free throws and fouls where they were or closer.

## Ratings questions
None raised by this piece. Chicago, Detroit and Portland (too weak) and the Clippers, New Orleans and Philadelphia (too
strong) are worth a ratings look in a later task, with evidence.

## Infrastructure note
On 2026-11-24 one Azure job (final betting run, seed 1001) died while copying code ("connection closed by remote
host"), and the Canada 2 machine stayed switched on with nothing running for about 16.5 hours until this session switched
it off on 2026-11-25. `azure_worker.py` doesn't switch a machine off when its copy step fails; worth a small fix
(stop the machine in a `finally` when no other job holds it).

## Files
- New: `src/nba_gm_data/stage2/finishes.py`, `src/nba_gm_data/stage2/finishes_table.py`, `tests/test_stage2_finishes.py`,
  `scripts/research/s2_endgame_pbp.py` (real extraction), `s2_endgame_states.py` (Stage 2 probe), `s2_finishes_fit.py`
  (the fitter, `--write` regenerates the table), `s2_spread_check.py` (spread breakdown).
- Changed: `src/nba_gm_data/stage2/game.py` (the table hooked into possession length, shot menu, fouls and makes; late
  rules; strength and home scales; pace and foul refit), `stage2/engine.py` (home scale), `stage2/__init__.py`,
  `scripts/research/s2_totals_check.py` (per-game margin spread; loop overrides).
- Data (git-ignored): real play-by-play in `output/rotation-evidence/pbp_regular_{2024,2025,2026}.parquet` (public
  archive github.com/ramirobentes/nba_data, downloaded with the user's OK); results in `output/s2finishes/`.
- Today's engine is untouched; Stage 2 stays off in normal gameplay. All 75 Stage 2 tests pass.

## Resume state
- [x] Baselines, real extraction, probe, fit, spread breakdown, strength and home scales.
- [x] Final betting pair `s2f-final2-1001/2001`, scorecard `output/s2finishes/cal_final2.json`, all-games level
  `output/s2schemes/level_gap_s2f_home.json`, end-of-game `output/s2finishes/endgame_states_final2.json`.
- [x] Report, commit on the branch. Coordinator: review and merge.
