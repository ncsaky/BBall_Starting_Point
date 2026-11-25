# S2-LAST-POSSESSION (Stage 2, eighth piece): the last possession of close games, totals, player props

_Owner: Claude (Opus session), worktree branch `claude/s2-last-possession-6afa88`. 2026-11-25. Status: **review**._

Progress: 7/7 - report written, committed on the branch (not pushed)

## TL;DR
- Close games now finish like real ones. Games decided by 1-3 points: 15.1% → **12.6%** (real 12.7%). From within three
  points with 24 seconds left, Stage 2 now matches real play almost exactly. Overtime rose a little, 3.9% → **4.0%**
  (real 4.4-4.7%); what's left of that gap happens before the last minute.
- The cause was late shooting, not luck: trailing teams' last-minute threes went in 33% of the time against a real 25%,
  and leaders weren't fouled on purpose often enough with 10-24 seconds left. Both are now fitted to real play-by-play,
  and twos, threes and turnovers each have their own late-game number.
- Betting test: win probability unchanged within seed noise (.1970, today's engine .2012), spreads level (4.02 vs
  4.03), totals better (5.99 → 5.93, today's 5.78). The whole remaining totals gap is that Stage 2's single games swing
  more (closer to real than today's engine, but the test's 20-run average punishes it). On market props the two engines tie; on every
  player's scoring across the season today's engine is still better. Several role players look under-rated as scorers
  (list below) — flagged, not changed.

## Goals and boundaries
1. Last possessions of close games, fitted on real play-by-play (2023-24 and 2024-25 fit, 2025-26 held back as the
   check). 2. The totals gap. 3. Player props, measured for the first time.
Touched only `src/nba_gm_data/stage2/`, `scripts/research/`, Stage 2 tests and this file. Today's engine is untouched
(byte-identical); Stage 2 stays off in normal gameplay. No player rating changed.

## 1. The last possessions

### What was wrong (compared possession by possession with real games)
A new extractor (`scripts/research/s2_lastposs_pbp.py`) pulls every real possession that starts in the last five
minutes of the 4th quarter or an overtime, with the exact score, clock, points, twos, threes, free throws, turnovers and
deliberate fouls (79,662 possessions over three seasons). `s2_lastposs_sim.py` records the same thing for Stage 2 and
`s2_lastposs_compare.py` compares them. Three things stood out:

1. **Late threes went in far too often.** In the last minute, a trailing or tied team made 33% of its threes in Stage 2
   against a real 25%. The previous piece had one "shot quality" number per situation, fitted to points per possession.
   Points came out right only because too-good threes offset too-poor twos, and that mix is exactly what decides ties
   (a tying three) against 1-3 point finishes.
2. **Leaders weren't fouled enough with 10-24 seconds left.** Real trailing teams foul about once per leader possession
   there; Stage 2 about 0.7 times. So leaders up 3 too rarely stretched the lead to 4-5 at the line (real 53%,
   Stage 2 30%).
3. **Situation-specific defence.** A team up three in the last 24 seconds guards the line and gives up twos: real
   teams down three make about 64% of their twos there (Stage 2 35%). Teams down two turn it over about 5% of the time
   (Stage 2 14%). A leader up 4-10 with 24-60 seconds left often lets the shot clock run out (real 15-26% turnovers a
   possession, Stage 2 8-9%).

### What changed
- **Each late-game situation now has six numbers instead of four** (`stage2/finishes.py`, `finishes_table.py`): possession
  length, lean toward threes, shooting fouls, a make shift for twos, an extra make shift for threes, and a turnover
  shift. Situations are the same as before: four time bands (2-5 minutes, 1-2 minutes, 24-60 seconds, last 24 seconds)
  by nine score bands.
- **Down exactly 1, 2 or 3 in the last minute** gets its own three-point lean, two-point make shift and turnover shift
  on top of its band (before, only the three-point lean).
- **Deliberate fouls by exact lead** (1, 2, 3, 4, 5, 6, 7-10, 11+) and time (last 10 s, 10-24 s, 24-60 s), fitted to
  the leader's real free throws per possession (`TAKE_LATE`). With 10-24 seconds left a team up 1-4 is now fouled
  86-97% of the time. A team up three fouls rather than allow a tying three 26% / 21% of the time (last 10 s / 10-24 s;
  was 18% / 11%).
- The blowout run-out and concede chances were refitted (.377 → .398, .444 → .431).
- Fitter: `scripts/research/s2_lastposs_fit.py` (24 rounds in all, 4 replays of 2025-26 per round). Who shoots and how
  well still comes from each player's own ratings; these numbers only describe what the situation does to everyone.

### Late shooting, last minute, trailing or tied team
| | Real 2023-25 (fit) | Real 2025-26 (check) | Stage 2 before | **Stage 2 now** |
|---|---|---|---|---|
| Three-point % | 25.3% | 24.8% | 32.9% | **25.8%** |
| Two-point % | 54.4% | 54.5% | 54.8% | **55.0%** |
| Points per possession | 1.02 | 1.00 | 1.03 | **0.99** |

### End of games (19,696 replayed 2025-26 games, 16 runs each; `s2_endgame_states.py`)
| | Before | **Now** | Real 2025-26 | Real 3 seasons |
|---|---|---|---|---|
| Overtime | 3.9% | **4.0%** | 4.4% | 4.7% |
| Decided by 1-3 points | 15.1% | **12.6%** | 12.7% | 12.7% |
| Decided by 4-5 points | 9.4% | **9.9%** | 8.8% | 8.7% |
| Decided by 13+ points | 40.3% | **40.8%** | 44.2% | 41.8% |
| Within 3 with a minute left | 19.9% | **19.4%** | | 19.3% |
| Within 3 with 24 seconds left | 20.5% | **19.3%** | | 19.4% |
| From within 3 at 24 s: tie (overtime) | 18.3% | **19.8%** | 20.3% | 21.7% |
| From within 3 at 24 s: 1-3 points | 61.7% | **54.7%** | 57.3% | 54.9% |
| From within 3 at 24 s: 4-5 points | 16.5% | **19.2%** | 18.5% | 19.4% |

On the held-back 2025-26 season alone (8 replays): from within 3 with 24 seconds left, overtime 20.2% against a real
20.3% and 1-3 points 57.0% against 57.3%.

## 2. The totals gap
Broken down like the spread check (`scripts/research/s2_totals_check.py`, every 2025-26 game, 8 runs; "miss" is the
betting test's average distance from the market total, predicted at its 20 runs).

| | Today's engine | Stage 2 before | **Stage 2 now** |
|---|---|---|---|
| Predicted total miss at 20 runs | 5.79 | 5.95 | **5.89** |
| Average total minus the market | +1.54 | +0.78 | **+0.20** |
| Systematic miss (what more runs wouldn't fix) | 6.04 | 6.27 | **6.22** |
| Game-to-game spread of one game's total | 15.6 | 16.6 | **16.6** |
| Correlation of expected totals with the market | .618 | .567 | **.562** |
| Team-by-team total error (spread across teams) | 2.86 | 3.20 | **3.20** |
| Team offensive rating, correlation with real | .90 | .82 | **.82** |
| Team pace, correlation with real / spread (real 2.05) | .84 / 1.15 | .77 / 1.33 | **.76 / 1.32** |

What it means:
- **All of the remaining gap is game-to-game randomness.** The test averages 20 simulated games and compares that with
  the market, so an engine whose single games swing more scores worse even when the swing is realistic. Real totals
  land about 18.5 points from the market line game to game (a little of that is the market's own error). Stage 2's
  16.6 is closer to real than today's 15.6. With today's engine's swing, Stage 2's numbers would predict 5.79, the
  same as today's engine. I did not shrink the randomness to win the test.
- **The late-game fit took away a small scoring surplus** (+0.78 → +0.20 points against the market), which is why the
  betting test's total miss improved from 5.99 to 5.93.
- **Systematic part:** Stage 2's team offenses line up a little less well with real (.82 against .90). Today's engine's
  per-team scoring leans on rates fitted to this same season, so some of that edge is expected.
- **Tried and rejected:** making team pace follow players' pace habits 1.5 times more strongly raised the correlation
  with market totals (.56 → .61) but added more unrelated swing; the predicted miss got worse (5.88 → 6.15). Pace stays
  as fitted.

## 3. Player props (first measurement; `scripts/research/s2_props.py`)
**What exists.** The betting test records a prop comparison per game but never scores it. The odds file holds points
lines for only 40 games (21-31 October 2025, 381 usable lines, over price only, from Fox Sports articles). I scored
those, and, because 40 games is thin, also every player's expected points, rebounds, assists and threes in every 2025-26
game against what he really did. Caveat for both: the betting test replays each player's real minutes, which the
market didn't know, so both engines beat the market's own line here; compare the engines with each other.

| Market props (40 games, 200 runs each) | **Stage 2** | Today's engine | Market |
|---|---|---|---|
| Win-probability error on over/under (Brier) | **.2151** | .2158 | .2497 |
| Log loss | **.6183** | .6173 | .6926 |
| Engine's average points minus the line | +0.33 | +0.27 | |
| Average miss from the line (points) | 2.31 | 2.28 | |
| Correlation with the line | **.905** | .873 | |

| Every game, every player with 10+ minutes (22,829 player-games, 8 runs) | **Stage 2** | Today's engine |
|---|---|---|
| Points: miss per game / correlation | 4.37 / .735 | 4.09 / .771 |
| Rebounds | 1.86 / .678 | 1.83 / .685 |
| Assists | 1.43 / .679 | 1.41 / .691 |
| Threes made | 0.94 / .544 | 0.91 / .577 |
| Season points off by (average, players with 50+ points) | 11.4% | 9.7% |
| Season threes off by | 10.4% | 6.7% |

So: on the market lines the engines tie (Stage 2 tracks the line more closely); across the whole season today's engine
splits points, assists and threes between teammates better. Today's engine's per-player rates were fitted straight to
real 2025-26 per-36 numbers (`box_rates.py`); Stage 2 builds them from the ratings through the possession loop, so this
is the fairer test of the ratings and the harder one. I found no clear engine cause to fix inside this piece.

## Speed (400 games, best of three)
Before 7.66 ms per replayed game and 8.21 ms per generated game; now 7.62 and 8.30. No change.

## Scorecard 2: real-stat targets
Quick scorecard (150 generated games, seed 1): **18/18 in range**; average distance from target .33 → .29 (in units of
the real team-to-team spread).

## Scorecard 1: betting odds
20 runs × 2 seeds, 1,018 games with market odds; average of the two seeds (each seed in brackets: 1001 / 2001).
Run locally (the Azure copy step was too slow; see weak spots).

| | Stage 2 before this piece | **Stage 2 now** | Today's engine | Market |
|---|---|---|---|---|
| Win-probability error (Brier, lower is better) | .1965 (.1990 / .1940) | **.1970** (.2003 / .1937) | .2012 | .1962 |
| Log loss | .5809 (.5850 / .5769) | **.5823** (.5892 / .5753) | .5910 | .5740 |
| Spread miss against the market (points) | 4.01 (3.97 / 4.04) | **4.02** (4.02 / 4.02) | 4.03 | |
| Total-points miss against the market | 5.99 (6.00 / 5.99) | **5.93** (5.92 / 5.93) | 5.78 | |

The win-probability numbers moved by less than the gap between the two seeds (one seed slightly better, one slightly
worse), so I read them as unchanged; Stage 2 stays ahead of today's engine on win probability and log loss and level on
spreads. Totals improved but still trail today's engine for the reason in section 2.

## Weak spots (honest list)
1. **Overtime is still a bit low** (4.0% against 4.4-4.7%). The last minute now matches; what's left is earlier: from
   within three with two minutes left, Stage 2 ties 14.4% of the time against a real 16.2%.
2. **Real late possessions get more shots** (about 0.06 more per possession for trailing teams in the last minute,
   likely offensive rebounds and scrambles). Not modelled; trailing teams score about 0.05 points a possession less
   than real there.
3. **Situation numbers are league-wide.** A team with great late-game shooters gets no extra credit beyond its players'
   own ratings.
4. **The fit is noisy at the edges.** Exact-deficit cells have 100-400 real possessions each; overtime moved ±0.4
   points between fit rounds at 4 replays.
5. **Infrastructure:** the Azure copy step re-uploads everything from a fresh worktree (about 650 MB per machine),
   because a new worktree's file timestamps don't match the worker's base copy. Three final jobs sat in the copy step
   for over 30 minutes, so I ran the betting pair and the totals file locally instead. Cancelling those Azure jobs was
   blocked by the permission check; they were left to finish and switch their machines off themselves. Worth checking
   `azure_worker.py status` (and a `--checksum` or size-only copy for worktrees).

## Ratings questions (flagged, nothing changed)
Season points, Stage 2 against real, players with 400+ real points (8 replays of every game):
- **Too low:** Gary Payton II −31%, Russell Westbrook −26%, Jaylon Tyson −25%, Jusuf Nurkić −25%, Toumani Camara −24%,
  Jaden McDaniels −22%, Pelle Larsson −22%, Josh Hart −21%, Collin Murray-Boyles −21%, Peyton Watson −20%. Mostly
  cutters, transition finishers and putback scorers: worth checking their finishing, cutting and offensive-rebound
  inputs (and how often Stage 2 gives them the ball) with evidence.
- **Too high:** Nolan Traoré +40% (today's engine +30% too), Kristaps Porziņģis +22%, Zion Williamson +21%, Myles
  Turner +21%, Anfernee Simons +19%, Anthony Davis +18%, Jaren Jackson Jr. +18%, DeMar DeRozan +18%, Brandon Ingram +18%.
  Mostly big men and isolation scorers: usage weights or their shooting inputs.

## Files
- New: `scripts/research/s2_lastposs_pbp.py`, `s2_lastposs_sim.py`, `s2_lastposs_compare.py`, `s2_lastposs_fit.py`,
  `s2_props.py`.
- Changed: `src/nba_gm_data/stage2/finishes.py` (six numbers per situation, exact-deficit terms, deliberate-foul table),
  `finishes_table.py` (refitted), `game.py` (make shift for threes, turnover shift, new foul tables, blowout numbers),
  `tests/test_stage2_finishes.py`; `s2_endgame_states.py` and `s2_finishes_fit.py` (notes: the old fitter is
  superseded).
- Data (git-ignored): `output/s2last/` (real rows, fits, probes, props); copies of the play-by-play in
  `output/rotation-evidence/`.

## Resume state
- [x] Real extraction, probes, three fit passes (`output/s2last/lastposs_fit{1,2,3}.json`), table written from fit 3.
- [x] End-of-games (16 runs), scorecard 18/18, speed, props, all 76 Stage 2 tests pass.
- [x] Final betting pair (local: `output/s2last/odds_local_{1001,2001}.json`), totals file
  (`output/stage2/totals_games_stage2_lpfinal_local.json`), report, commit. Coordinator: review and merge.
