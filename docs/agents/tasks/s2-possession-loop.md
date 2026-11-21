# S2-POSSESSION-LOOP (Stage 2, third piece): report

_Owner: Claude (Opus agent), branch `worktree-agent-aad27ad88396dd23e`. 2026-11-21. Status: **review**._

## TL;DR
- **Stage 2 now plays whole games itself.** Every possession is played: who has the ball, what he tries (drive,
  jumper, pull-up, post-up, roll or cut, putback, transition), turnovers and steals, fouls and free throws, rebounds,
  a real game clock with quarters, team fouls and the bonus, and a live substitution pattern. It writes the same box
  score as today's engine, so both scorecards run on it. It stays off for normal gameplay.
- **Real-stat scorecard:** 18 of 18 league numbers in range, and closer to the real averages than today's engine (it
  was tuned to them, so this is partly expected). Player by player it is close to today's engine on shot volume,
  rebounds, steals and turnovers, better on steals and turnovers, and still behind on points, threes attempted and
  free throws.
- **Betting test:** BETTING_TLDR
- **Speed:** about 4.5 thousandths of a second per game (0.02 ms per possession), about a tenth of the budget and
  three times faster than today's engine.

## What was built
All new code is in `src/nba_gm_data/stage2/`. Nothing in `sim.py`, the scorecard scripts, the ratings or the default
engine changed, so today's engine plays exactly as before.

**Player cards (`cards.py`).** Each player's numbers for the loop, built once from his 94 inputs:
- **How often he ends a possession** (usage): fitted to real 2025-26 usage from his habits (involvement, shoot / drive /
  pass / post choices, shot-difficulty tolerance, dribble persistence) and a few creation skills. Players the fit never
  saw: correlation .95.
- **How often he turns it over** when he ends one: fitted to real turnovers per used possession from passing risk,
  pass and drive choices, dribble persistence, handle security, dribble skill, passing delivery and attack reads. Held
  out: correlation .74.
- **What he tries (the action menu).** His shot-location habit picks the floor area; within it, his habits pick the
  action: at the rim, a drive (drive choice) or finishing a teammate's pass (cutting, rolling and slipping habits) or a
  post finish; in the short paint, a floater (drive choice), a hook (post choice) or a short jumper (shoot choice);
  from midrange and three, a pull-up (pull-up habit) or a catch-and-shoot (a quarter of catch threes from the corner).
  Transition possessions use a transition menu (rim or early three); offensive rebounds can lead to putbacks.
- **His make chance on each shot**, from the shooting kernel with the per-family conversion fitted in the shooting
  piece (each jumper family, layups, floaters and dunks its own floor and slope), plus two new rules:
  - **hooks / post finishes:** post-finish skill and reach. On Basketball Index's short-midrange make rates, players the
    fit never saw: correlation .61 -> .65; for post-heavy players the bias went from -3.1 to +0.8 points;
  - **dunk share** of rim attempts: reach + vertical and dunk skill (none below 310 cm). Real Basketball-Reference dunk
    shares, held out: correlation .90. Drives are dunked less than rolls, cuts, putbacks and transition finishes.
- **Defense:** perimeter contest (containment, contest, closeouts, screen navigation), rim protection (interior
  positioning, contest, reach), ball pressure (anticipation, on-ball and passing-lane steals, gambling habit), and
  weights for who gets the steals and blocks (block weight fitted to real blocks per 36, held out .88).
- **Rebounding and fouls** come from the rebound and foul kernels built in the previous piece.

**The loop (`game.py`).** One possession:
1. How the last one ended (defensive rebound, steal, made basket, dead ball) and the lineup's pace and transition habits
   set whether it is a transition possession and how long it takes.
2. A non-shooting foul can come first (side out, or two free throws once the offense is in the bonus).
3. The finisher is drawn by usage among the five; he may turn it over (his turnover odds plus the defense's ball
   pressure). A turnover can be a steal (who steals: steal weights, his own defender first) or an offensive foul.
4. Otherwise he takes a shot from his action menu. The action sets the shot area, the make chance, the shooting-foul
   chance (drives draw the most contact; rolls, cuts and putbacks less; catch jumpers least), the assist chance and
   where a miss bounces.
5. Misses go to the rebound kernel; an offensive rebound continues the possession (an immediate putback or a reset).
6. End of game: a team ahead runs out the last seconds; a team behind by 1-8 in the last 45 seconds fouls.

**The clock.** Four 12-minute quarters and 5-minute overtimes while tied. Possession length depends on the possession
type (half court about 16 s, transition about 6 s, a reset after an offensive rebound about 8 s), the lineup's pace
habit and the coach's tempo. Team fouls count per quarter (bonus from the 5th, or the 2nd in the last two minutes).
Personal fouls are tracked; six fouls and he is out.

**Substitutions (stand-in).** Tonight's planned minutes come from today's minutes model: the real minutes in replayed
games; in generated games, today's pre-game steps (replacement minutes for absent players, the coach's matchup
minutes, the ramp-up after an absence, human teams' game-day rotation). Stage 2's own coach then decides who is on
the floor at each stoppage: who is owed the most of his planned minutes, kept on for continuity, rested after a long
stint, benched in foul trouble (2 fouls in the 1st quarter, 3 in the 2nd ...), out after six fouls, starters rested in
a fourth-quarter blowout, starters opening each half, at most three bigs or three guards. Played minutes land within
about 1.1-1.6 minutes of the plan on average.

**Team terms built on what exists.** Home court (today's fitted home-court points), the coach's offense, defense and
tempo ratings (today's coach model), rest days, and tired legs or rust (today's health penalty points), all as small
make-chance or pace terms.

**Team strength.** How much the ratings move results is set by five engine numbers (perimeter contest, rim protection,
ball pressure, and the lineup's creation and spacing), fitted so the engine's expected margins follow the betting
market's spreads on the first half of the season (checked on the second half). A "score effect" (the leading team's
shots get slightly harder as the lead grows: effort, garbage time, the trailing team's urgency) brings the game-to-game
spread of margins to the real level (13.3 points around the engine's own expectation; today's engine 13.1; it was 17.4
without it).

**Fits and checks (`loop_fit.py`, `scripts/research/s2_possession_loop_check.py`).** Every rule fit uses a fixed half
of the rotation players and is checked on the other half (the same split as the shooting and rebound pieces). No
player rating was changed anywhere.

## Scorecards, side by side
### Real-stat targets (`calibration_report.py`, 150 generated games, seed 1)
| | Stage 2 | Today's engine |
|---|---|---|
| League numbers in range | 18 / 18 | 18 / 18 |
| Average distance from the real league average (in team spreads) | **0.24** | 0.38 |
| Largest distance | **0.62** (fouls) | 0.86 (free throws) |
| Per-player mean miss, points per 36 | 2.99 | **2.04** |
| ... shots per 36 | 1.71 | 1.70 |
| ... threes attempted per 36 | 0.94 | **0.38** |
| ... free throws per 36 | 1.15 | **0.83** |
| ... rebounds per 36 | 1.04 | 1.04 |
| ... assists per 36 | 0.99 | **0.88** |
| ... turnovers per 36 | 0.66 | **0.56** |
| ... steals per 36 | 0.47 | **0.40** |
| ... blocks per 36 | 0.38 | 0.34 |
| ... true shooting | 0.060 | **0.048** |

Stage 2's league numbers were tuned to these same targets (so its edge there is partly by construction).

### Per player in replayed games (600 games, real minutes, seed 1; 350 rotation players; correlation with real per-36)
| Stat | Stage 2 (all / held-out half) | Today's engine (all / held-out half) |
|---|---|---|
| Points | .924 / .924 | **.945 / .944** |
| Shots | .930 / .927 | .937 / .931 |
| Threes attempted | .952 / .954 | **.989 / .989** |
| Free throws | .846 / .856 | **.912 / .914** |
| Rebounds | .925 / .935 | .943 / .959 |
| Assists | .893 / .909 | **.940 / .934** |
| **Turnovers** | **.793 / .785** | .773 / .786 |
| **Steals** | **.793 / .826** | .728 / .747 |
| Blocks | .851 / .837 | .842 / .837 |
| True shooting | .49 / .48 | **.61 / .61** |

Today's engine reads players' real 2025-26 rates through fits made on this same season (points, assists, rebounds,
free throws and turnovers per 36, and shooting percentages taken almost directly from the box score), so on this
season it is close to a lookup. Stage 2 has to produce them from what each player does on each possession.

### Turnover and steal spot-check (the new component check)
- **Real data:** 2025-26 turnovers and steals per 36 (targets file), and turnovers per used possession.
- **The rule on its own:** turnovers per used possession, players the fit never saw, correlation .74 (bias 0.0).
- **In games** (table above): turnovers .79 (today .77), steals .79-.83 (today .73-.75). Error size is similar for
  turnovers (0.58 vs 0.50 per 36) because Stage 2 gives high-usage stars too many: Banchero 5.7 vs 3.2 per 36, Jaylen
  Brown 5.8 vs 3.8, Wembanyama 4.6 vs 3.0, Cunningham 5.5 vs 3.9; and too few to some passers: Draymond Green 2.0 vs 3.5,
  Nurkić 1.8 vs 3.4, D'Angelo Russell 2.4 vs 3.6.
- **Steals:** over for Paul Reed, Shai Gilgeous-Alexander, Drummond, Lonzo Ball; under for Dalen Terry, Konchar,
  Kyshawn George, Quickley.
- League: turnovers 14.3 per 100 (real 14.1), steals 8.4 (real 8.2).

### Betting test (`validate-season-probabilities`, 20 runs a game, 1,231 games, 1,018 with market odds)
BETTING_TABLE

### Speed
| | Stage 2 | Today's engine |
|---|---|---|
| Per game (600 replayed games, quiet laptop) | **4.5 ms** | 13.4 ms |
| Per possession | **0.022 ms** | — |
| Per game on the busy laptop (load 100-250) | 17-25 ms | — |

The budget was 0.2-0.4 ms per possession (0.02-0.04 s per game). Building a player's card takes about 0.1 ms once.

## Shooting and shot mix (Stage 2, replayed games)
| Area | Share of shots (real) | Make rate (real) |
|---|---|---|
| Rim | 29.4% (28.1) | 66.9% (67.4) |
| Short paint | 15.3% (20.8) | 43.2% (44.8) |
| Midrange | 13.5% (9.7) | 42.5% (41.7) |
| Three | 41.9% (41.4) | 35.0% (36.1) |

The short-paint vs midrange split comes from the players' shot-location habits, which put about 4 points of shots in
long midrange that real data has in the short paint (noted in the shooting piece; a ratings-evidence question, not
changed here).

## What is still a stand-in
- **Substitutions:** today's planned minutes, followed by a simple live rotation (owed minutes, stint length, foul
  trouble, blowouts). Not yet the coach model's own game-by-game decisions or hot/cold hands.
- **Lineups in generated games** follow those minutes; no coach matchup lineups in the loop yet.
- **Shot creation and defense** are lineup averages (one perimeter, rim and pressure index each; creation and spacing
  for the offense), not player-on-player matchups. No screens, closeouts or help rotations yet, and no screen assists
  in the box score (left out rather than shown as a number the engine does not produce).
- **Action menu weights** within each shot area (how much rim offense is drives vs cuts vs rolls, the corner share,
  transition shot mix) are documented stand-ins checked only against league totals.
- **Assisted shares by action** are stand-ins scaled to the league assist rate; who assists uses today's assist fit.
- **Free throws by player** are still the weakest part: ball-handlers who live at the line (Avdija, Luka, Harden,
  Reaves, Coby White) are under, rim-running bigs (Anthony Davis, Ayton, Isaiah Jackson) are over. A refit of the
  foul rules against the action menu did not fix it (held-out correlation stayed about .87).
- **End-game play** is two simple rules (run out the clock, foul when behind); no timeouts, two-for-ones or
  advancing the ball.
- **Score effect** is one number standing in for effort, garbage time and urgency.
- **Players without inputs** (replayed players no longer in the league) get the league-median card.
- **Team-strength numbers** were fitted to market spreads on 2025-26, the same season the ratings come from.

## Recommended next piece
**Player-on-player matchups and closeouts.** Today the defense is a lineup average, so a great perimeter defender does
not take away a specific star, and shot quality does not depend on how the shot was created. Assign each defender a
man (coach scheme plus size and skill), let drives, screens and kick-outs create a defender's arrival time, and resolve
contests with the existing closeout and contest pieces as fast fitted rules. This is also where free throws by action
should improve (drives against a specific defender), and where the betting test should gain most, since matchups are
what separates good teams from good-on-paper teams. Fold in a proper coach rotation (the coach model's minutes and
in-game decisions instead of today's plan) as a second step.

## Files
- **New:** `src/nba_gm_data/stage2/cards.py`, `game.py`, `loop_fit.py`; `scripts/research/s2_possession_loop_check.py`;
  `tests/test_stage2_possession_loop.py`.
- **Changed:** `src/nba_gm_data/stage2/engine.py` (the stub now plays Stage 2 games), `stage2/__init__.py` (docs),
  `tests/test_stage2_seam.py` (the two stub tests now check the real Stage 2 engine).
- **Not changed:** `sim.py`, `calibration_report.py`, `cli.py` (the engine flags from the seam piece already existed),
  ratings data, `trait_adapter.py`, `ratings_model.py`, `impact_value.py`, `health.py`.
- Output (git-ignored): `output/stage2/possession_loop_check.json`, `output/stage2/cal_*_sandbox.json`,
  `output/stage2/odds_*.json`, scratch scripts in `output/stage2/scratch/`.

## Checks
CHECKS

## Resume state
- [x] Cards, loop, clock, rotation, engine hook; fits; league calibration; team-strength fit; score effect.
- [x] Replay spot-check script and results; tests.
- [ ] ODDS_STATE
