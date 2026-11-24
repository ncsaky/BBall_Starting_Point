# S2-COACH (Stage 2, fifth piece): a proper coach, plus pick-and-roll coverages and switching

_Owner: Claude (Opus agent), worktree branch `claude/awesome-jepsen-e7b395`. 2026-11-24. Status: **review**._

Progress: 8/8 - report written; committed on the branch (not merged, not pushed)

## TL;DR
- **Stage 2 now has a real coach.** At every stoppage it decides who plays, starting from tonight's planned minutes
  (today's coach model, unchanged) and reacting the way real coaches did in about 3,700 real games: how long stints and
  rests last, starters opening each half and returning to close it, foul trouble (who gets pulled after which foul and
  for how long), blowouts (starters leave for good at the real rate for the score and clock), close finishes (the stars
  play them), cold shooting, tired legs, rust and injuries during the game.
- **Minutes now look like real rotations.** In a full AI-coached season, stints, rests, minutes by quarter, how many
  players get in, blowout and close-game minutes and the response to cold shooting all land close to real 2025-26.
  Regulars fouled out in 6.8% of their games under the old Stage 2 rotation (real 1.6%); now about 1.8%.
- **Pick-and-roll and switching are in.** A scorer's own shot often comes off a ball screen. The defense switches (at
  the real league rate, 26% of screens), drops, shows or traps, so a star meets the big he was switched onto or the rim
  protector waiting in a drop, not only his own defender. Screen assists now appear in Stage 2 box scores at the real
  rate.
- **Scorecards.**
  - **Betting test:** winner-picking improves a little again: Brier .1977 against .1987 before this piece (today's
    engine .2012), log loss .5832 against .5857 (today's .5910). Point spreads are about even (4.35 against 4.39;
    today's 4.03).
  - **Totals miss** is slightly worse (6.60 against 6.48; today's 5.78). The engine's expected totals now follow the
    market more closely (correlation .57 to .59), but replayed games score about 3 points a game above both the real
    games and the market. More overtime adds part of that. Generated games still score at the real level, so I did not
    re-center it (details below).
  - **Real-stat targets:** still 18 of 18 in range.
- **Speed:** about 8 ms per replayed game and 10 ms per generated game (today's engine 8-12 ms; budget 20-40).

## What changed

### 1. The coach (`stage2/coach.py`)
Before the game nothing changes: tonight's planned minutes still come from today's coach model (replacement minutes
for absent players, matchup minutes, the ramp-up after an absence, the human team's game-day variation; in replayed
games, the real minutes). That plan is what a player would play in a close game. The new part is the coach during the
game. He looks at the floor at every dead ball (fouls, free throws, turnovers out of bounds) and at the two mandatory
timeouts of each quarter, about 120 looks a game, and makes about 22 changes per team, as real coaches do.

What he reacts to, and where each rule comes from (real-data numbers are from the 2023-26 play-by-play rotation study,
`data/research/rotation_evidence.json`; a test checks the copies):

| Reason | What the coach does | Evidence |
|---|---|---|
| Rhythm | Each stint gets a length drawn around his role's usual stint (star, starter, sixth man, bench); the player furthest behind his plan comes back once he has rested. Starters open both halves and come back with about 7:30 left in the 2nd quarter to close the half. | Fitted by simulation to the real stint, rest, opening-stint and minutes-by-quarter numbers |
| Fatigue | Conditioning (P11) lengthens stints, recovery (P12) shortens rests; tired legs from the schedule shorten stints and cost about 0.6 minutes on the second night of a back-to-back. | The back-to-back cost is the real paired comparison; the conditioning and recovery weights are stand-ins |
| Foul trouble | On a 2nd foul in the 1st quarter, a 3rd before halftime, or a 4th or 5th, he is pulled with the real chance for that foul, quarter and role, and comes back after the real bench time (a 3rd foul before halftime: the start of the 3rd quarter). Players in foul trouble also foul less. | Held-out fits from the study; the caution numbers were fitted to the real foul-out rate |
| Blowouts | In the 4th quarter each regular on the floor leaves for good with the real per-minute chance for the time left and the margin; a regular already sitting in a 20-point game stays seated unless the game tightens. Players with tiny plans, then players outside the rotation (generated games), mop up. | Held-out fits; garbage-time thresholds are stand-ins mirroring today's coach |
| Close finishes | From the 7:00 timeout of a close 4th quarter the four most-trusted players (largest plans) stay on and come back early from rest; the 5th and 6th share the last spot; in the last three minutes a closer sitting in foul trouble returns. | Fitted to the real close-finish shares (starters 74% of the floor time, stars 94%) |
| Hot and cold hands | Tonight's plan moves with his shooting so far: cold nights cost minutes, hot nights add little. | Measured here on real 2025-26 box scores (regulars in close games) |
| Injuries and rust | A player hurt during a generated game (today's health model) leaves after his share of the plan and does not return; a player back from an absence gets shorter stints. | Today's health model; the shorter stints are a stand-in |
| Depth | Players with a plan under 6 minutes play only in garbage time or when the coach is short. | Real teams give 10.8 players a minute or more a night |

Two smaller game-management changes ride along (coach on only):
- **End of game.** A trailing team now fouls on purpose at the real rate for its deficit and the time left (down 1-3:
  about 5% before the last 24 seconds, 60-75% inside them), a team up three sometimes fouls rather than allow a tying
  three, and intentional fouls come from a player with fouls to give. The old rule fouled 75% of the time anywhere in
  the last 45 seconds and let the leader run out the clock first.
- **Replayed games** (the betting test) keep each player's real minutes as the plan, and by default the coach keeps to
  them and decides only when each plays (no blowout exits or spot players): `COACH["replay_faithful"]`. The full coach
  in replays scored within noise of it (table below).

The old rotation stays selectable (`LOOP["coach"] = 0`) for comparisons.

### 2. Pick-and-roll coverages and switching (`stage2/screens.py`)
The loop already decides who ends a possession and what he tries (both fitted to real data); this layer adds where the
shot came from, so those fits do not move:
- **Which shots come off a screen.** 70% of self-created half-court shots (drives, floaters, pull-ups, short jumpers;
  2025-26 play types: pick-and-roll ball-handler endings 29.4 per 100 possessions against isolations 7.4 and handoffs
  4.5) and a big's finish off a pass in the share his habits give to rolls and slips (T11) over cuts (T09).
- **Who screens.** Teammates by the existing screen-assist fit (screen execution S27, screen reads S28, screen and roll
  habits, body mass), leaning toward the teammate whose defender the offense wants in the action (the weakest on-ball
  defender).
- **The coverage**, from the two defenders involved:
  - **switch**: likelier when they are of a size, when the screener's defender can stay in front, and on guard-guard
    screens; the level is fitted to the real league share (26% of ball screens);
  - **drop**: likelier with a rim-protecting, slower big, less likely against a pull-up shooter;
  - **trap**: rare, mostly for the night's highest-usage scorers;
  - **show / at-level** otherwise.
  The resulting mix is switch 26%, drop 43%, show 28%, trap 3%.
- **What it does.**
  - On a switch, the shot is played against the screener's defender with all of that pairing's matchup terms. A star
    switched onto a slow big gets past him more often; a switch onto a long wing contests his jumper better. A roll
    after a switch is finished over the smaller defender.
  - On a drop, the ball's defender loses part of his contest. How much depends on the screen edge: screen quality,
    strength, balance and body mass against screen navigation (S35), lateral quickness, anticipation and attention,
    which are the inputs the screen-navigation physics piece reads. The drive meets the screener's defender waiting at
    the rim, and the roller meets his own big.
  - Shows make pull-ups and drives harder and cause a few more turnovers, but leave the roller open unless the five
    rotates.
  - Traps cause more turnovers.
- **Screen assists** are credited when the handler scores straight off the screen, fitted to the league's 7.29 per 100
  possessions. They are now in Stage 2 box scores (before, the stat was left out because the engine did not produce
  it).

League levels did not move with screens on (effective FG%, turnovers, free throws and points per 100 all within a few
tenths).

## Scorecards side by side

### Betting test (20 runs a game, 1,231 games, 1,018 with market odds; average of seeds 1001 and 2001)

| | Brier | Log loss | Spread miss (pts) | Total miss (pts) |
|---|---|---|---|---|
| Market | .1962 | .5740 | | |
| Today's engine (re-run after the ratings follow-up) | .2012 (.2047 / .1978) | .5910 | **4.03** | **5.78** |
| Stage 2 before this piece (re-run) | .1987 (.2000 / .1974) | .5857 | 4.39 | 6.48 |
| + coach, faithful in replays | .1974 (.1974 / .1974) | .5818 | 4.35 | 6.48 |
| + coach, full in replays | .1966 (.1938 / .1994) | .5789 | 4.34 | 6.55 |
| + coach (faithful) + screens | .1979 (.1971 / .1987) | .5838 | 4.35 | 6.41 |
| + coach (full) + screens | .1978 (.1971 / .1985) | .5846 | 4.23 | 6.56 |
| **Final** (faithful + screens + end-of-game fouling) | **.1977** (.1967 / .1987) | **.5832** | 4.35 | 6.60 |

- **Plainly:** Stage 2 keeps its lead over today's engine at picking winners (Brier .1977 against .2012, log loss
  .5832 against .5910) and gains a little on its own previous version. It still trails today's engine on spreads (4.35
  against 4.03) and totals (6.60 against 5.78).
- **Why totals got slightly worse.** Breakdown from `s2_totals_check.py`, 8 runs a game, before → after:
  - The expected totals follow the market better: correlation .568 → .593, slope .77 → .83, systematic error 6.67 →
    6.56.
  - The scoring level rose: +2.4 → +3.0 points over the market. Overtime went 2.5% → 3.4% and possessions 102.4 →
    102.7.
  - Re-centering the league scoring level to the real replayed totals (230.7 points) would remove the bias. But
    generated games already score at the real level, and their shooting efficiency would fall to 0.9-1.1 team spreads
    below real. The scorecard's average distance would go .36 → .49-.52.
  - I left the level alone. Why replayed and generated games differ by about 3 points is a question for the next
    piece.
- The seeds disagree by up to .006 Brier, so differences under about .003 between Stage 2 versions are noise.
- Re-baselining mattered: the ratings follow-up (RATINGS-FT-TOV) moved both engines. Today's engine's totals miss went
  5.53 → 5.78; Stage 2 went from .1972 Brier / 6.34 totals (last report) to .1987 / 6.48 before this piece.

### Real-stat targets (`calibration_report.py --engine stage2`, 150 generated games, seed 1)

| | In range | Average distance (team spreads) | Largest |
|---|---|---|---|
| Stage 2 before this piece (re-run) | 18 / 18 | .33 | .75 (turnover rate) |
| **Final** | **18 / 18** | .36 | .93 (turnover rate, low) |

Turnovers sit a little low (13.4 per 100 against 14.1) and fouls a little high, both inside the real range.

### Per player in replayed games (600 games, real minutes, seed 1; correlation with real per 36, all / held-out half)

| Stat | Before (coach and screens off) | **Final** | Today's engine |
|---|---|---|---|
| Points | .926 / .925 | .926 / .924 | .949 / .947 |
| Shots | .934 / .929 | .926 / .923 | .932 / .922 |
| Threes attempted | .946 / .937 | .946 / .941 | .989 / .989 |
| Free throws | .914 / .923 | .912 / .925 | .925 / .927 |
| Rebounds | .924 / .928 | .936 / .937 | .940 / .951 |
| Assists | .882 / .902 | .891 / .911 | .935 / .930 |
| Turnovers | .850 / .863 | **.871 / .865** | .846 / .863 |
| Steals | .834 / .843 | .824 / .837 | .726 / .728 |
| Blocks | .875 / .844 | .859 / .853 | .817 / .821 |

Rates per 36 hardly move. The coach changes when and how much players play, not how well.

## Minutes against real 2025-26

### A full AI-coached season (2026-27 rosters, injuries on, all 30 teams; seeds 17 and 29)
Real numbers come from the 2025-26 box scores. The season is a different roster year, so this compares shape, not
players.

| | Real 2025-26 | Today's engine | Stage 2 old rotation | **Stage 2 coach** |
|---|---|---|---|---|
| Players averaging 30+ / 34+ / 36+ minutes, per team | 2.5 / .60 / .10 | 2.2 / .62 / .13 | 2.9 / .97 / .37 | 2.9 / .55 / .07 |
| Average of the top 30 / the most | 34.6 / 38.0 | 34.5 / 37.6 | 35.7 / 39.9 | 34.2 / 36.5 |
| Starters' share of minutes | .615 | .611 | .635 | .631 |
| Players with 5+ / 1+ minutes a game | 10.1 / 10.8 | 11.1 / 13.7 | 10.9 / 13.0 | **10.5 / 11.9** |
| Game-to-game spread of a regular's minutes | 5.3 | 4.3 | 4.2 | 5.7 |
| Regulars' foul-outs (share of their games) | 1.55% | 1.55% | 6.8% | **1.7-1.8%** |
| Regulars' fouls a game | 2.29 | 2.22 | 2.50 | 2.40 |
| Regulars' minutes, close (0-5) minus blowout (21+) | 5.2 | 5.1 | 2.1 | 5.8 |
| ... by final margin 0-5 / 6-10 / 11-15 / 16-20 / 21+ | +1.5 / +1.1 / +0.2 / -1.4 / -3.8 | +1.6 / +1.2 / +0.4 / -1.0 / -3.5 | +0.4 / +0.4 / +0.2 / -0.3 / -1.7 | +2.0 / +1.3 / -0.1 / -1.5 / -3.8 |
| Cold night (-4 field-goal points per 10 min) vs an average night, close games | -3.1 | -0.6 | -1.7 | -2.3 |
| Overtime | 4.4% | 2.0% | 2.9% | 3.2% |

Rotation rhythm (seconds; mean / median; real = the rotation study, 2023-26):

| | Real | Stage 2 coach, generated season | Stage 2 coach, replayed 2025-26 |
|---|---|---|---|
| Stint: star / starter | 586/528, 465/427 | 546/521, 443/424 | 600/550, 452/436 |
| Stint: sixth man / bench | 431/403, 341/313 | 379/360, 269/236 | 443/426, 307/282 |
| Rest: star / starter | 248/239, 304/277 | 258/215, 316/257 | 276/237, 369/303 |
| Rest: sixth man / bench | 368/317, 508/412 | 385/330, 513/416 | 366/312, 537/430 |
| Opening stint: star / starter | 543/548, 452/449 | 540/533, 436/434 | 594/551, 458/456 |
| Star minutes by quarter | 582, 470, 588, 421 | 552, 501, 534, 418 | 578, 497, 554, 485 |
| Starter minutes by quarter | 488, 430, 478, 374 | 473, 443, 458, 365 | 480, 425, 428, 374 |
| Close finishes: starters' / stars' share of the floor | .74 / .94 | .79 / .88 | .73 / .91 |

The old rotation kept no lineup log, so its rhythm cannot be measured the same way. Its three checkpoints a quarter
allowed only 3-minute steps.

### Replayed games (real minutes as the plan)
- Average gap between a player's minutes and his real minutes: 1.7 (old rotation), 2.5 (coach, faithful), 3.4 (coach,
  full). The coach moves minutes to follow the simulated game: its foul trouble, its close finishes, and with the full
  coach its blowouts.
- Foul-outs: 6.0% for the old rotation; 2.0% faithful; 1.5% full (real 1.55%).
- Overtime: 2.4% for the old rotation; 3.1% faithful; 2.9% full (real 4.4%).

### Speed (warm, quiet laptop)

| | Per game |
|---|---|
| Stage 2 final, replayed games | 8.0-8.3 ms (coach decisions 2.4 ms, lineup bookkeeping 1.9 ms) |
| Stage 2 final, generated games (with today's pre-game steps) | 9.8 ms |
| Stage 2 before this piece, replayed | 6.3 ms |
| Today's engine, replayed (same run) | 8.0 ms |

A full betting run (24,620 games) takes about 5 minutes on a cloud worker (was about 4). The coach checks about 120
times a game and changes the lineup about 45 times. Each five's numbers and each pairing of fives are cached, because
the same fives recur all game.

## What is still a stand-in, and weak spots
- **Coverage mix and effect sizes.** Only the switch share is fitted to a league number. The drop/show/trap split and
  how much each coverage changes a shot are stand-ins, checked through league levels and the betting test. There are
  no public team-level coverage frequencies; the scheme study's team aggression index cannot be turned into
  percentages.
- **No team or coach schemes.** Coverages follow the personnel on the floor. The coach inputs hold no switching habit,
  so Miami-style switching or Boston-style dropping is not a team trait yet.
- **The screen edge** is a fast rule built from the same inputs as the screen-navigation physics piece, not fitted to
  it. The league input bridge does not yet convert the speed measurements that piece needs (P06, P07 in m/s).
- **Not modeled:** off-ball screens for shooters (their screen assists are folded into ball screens), handoffs, and a
  trap's pass-out leading to a 4-on-3.
- **Overtime** is still low: 3.1-3.2% against a real 4.4% (today's engine about 2%). Still missing at the end of games:
  timeouts that advance the ball, two-for-ones, quick-two decisions.
- **Heavy foulers.** 17 regulars foul 4.5+ times per 36 minutes in the generated season against 4 in real 2025-26.
  They are mostly stoppers assigned to stars (McDaniels, Brooks, Jaren Jackson Jr., Duren, Poeltl). This comes from
  the foul and matchup model, not the coach. It is the main reason foul-outs sit at 1.7-1.8% instead of 1.55%. A
  follow-up: the defender's foul terms when the assignment puts a stopper on a high-usage scorer.
- **Small tuning gaps.**
  - Bench stints run short in generated seasons (median 236 s against a real 313) while they match in replays (282
    against 313). AI plans give the 8th-10th men small minutes that end their stints early.
  - Close-game minutes for regulars run about half a minute high.
  - The top end is slightly compressed: no generated player passes about 36.6 minutes a game (real 38).
- **Hot hands.** The response is fitted to a box-score proxy (field-goal points against his own rate). A cold night may
  partly be an injury or illness the box score cannot see.
- **Conditioning and recovery** (P11, P12) shape stints only lightly. Both are mostly position priors today, and there
  is no direct evidence for the weight.

## Ratings questions (rule 1)
None raised by the coach. The heavy-fouler tail above is first a model question (stopper assignments and foul terms).
If it survives a model fix, it would be worth checking whether foul control (S45) for McDaniels, Brooks, Jaren Jackson
Jr. and Duren matches their real fouls per 36.

## Recommended next piece
**Team and coach defensive schemes plus the end of games.**
1. Give each coaching staff a scheme preference fitted to the scheme study's team aggression and versatility, so teams
   differ in how often they switch, drop or trap.
2. Add the missing end-of-game plays (timeouts that advance the ball, two-for-ones) to bring overtime toward 4.4%.
3. Check the stopper foul tail.
4. Find why replayed games score about 3 points a game above real while generated games do not. Real availability
   and minutes put different lineups on the floor than healthy rotations do, so the level cannot simply be
   re-centered.

Spreads (4.35 against today's 4.03) and totals (6.4 against 5.8) are still the gap to close before Stage 2 can become
the default. Team scoring levels and per-game noise were the main causes in the last report, and they remain so.

## Files
- **New:** `src/nba_gm_data/stage2/coach.py`, `src/nba_gm_data/stage2/screens.py`, `scripts/research/s2_coach_check.py`
  (generated seasons, replayed seasons, report against real 2025-26 and the rotation study),
  `tests/test_stage2_coach.py` (16 tests).
- **Changed:**
  - `stage2/game.py`: coached loop, substitution chances at dead balls and timeouts, foul caution, screens, screen
    assists, end-of-game fouling, caches;
  - `stage2/engine.py`: the coach, garbage-time reserves, research hook;
  - `stage2/cards.py`: screen numbers;
  - `stage2/__init__.py`: notes;
  - `scripts/research/s2_odds.py`: `loop.KEY=V` / `coach.KEY=V` overrides.
- **Not changed:** `sim.py`, `game_minutes.py`, `calibration_report.py`, the GUI, ratings and inputs files. Today's
  engine is byte-identical by construction; the seam test still checks default = explicit "current".
- **Output (git-ignored):** `output/s2coach/` (betting runs `odds_*`, seasons `season_*`, replays `coach_*`, scorecard
  `cal_*`, per-player `check_*`, reports `report_*.txt`).

## Checks
- `tests.test_stage2_coach` 16 OK. Existing Stage 2 tests (seam, possession loop, totals and matchups, rebound and
  fouls, league inputs) 46 OK.
- Core suite (`scripts/run_core_tests.sh` modules, run with the shared venv): 342 run, 339 OK. The three that fail
  have nothing to do with this work:
  - `test_gui_concept71`: the settings modal now has a font choice, from the parallel GUI work;
  - `test_gui_concept74`: the prospect table no longer uses `performanceBarStyle`;
  - `test_settlement_materialization`: needs an `output/` fixture that this worktree does not have.
  None of their files were touched.
- Laptop: one heavy job at a time, `nice -n 10`. All betting runs went to the Azure pool, two at a time.

## Resume state
- [x] Baselines; coach built and tuned (seasons v1-v8); replay versions; screens and calibration; end-of-game fouling;
  tests; core suite; per-player check; final seasons on two seeds; final betting pair (`s2c-final-a`, `s2c-final-b`).
- [x] Report; commit on the branch. Board row left to the coordinator.
