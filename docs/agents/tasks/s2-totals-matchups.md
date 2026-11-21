# S2-TOTALS-MATCHUPS (Stage 2, fourth piece): report

_Owner: Claude (Opus agent), worktree branch `worktree-agent-ada70276d8f65497d`. 2026-11-21. Status: **review**._

## TL;DR
- **Stage 2 now beats today's engine at picking winners**, on both test seeds. Brier score averages .1972 against
  today's .2007, and log loss .5816 against .5892. It is still behind on how far its point spreads and game totals sit
  from the market: spreads miss by 4.41 points against today's 4.01, and totals by 6.34 against 5.53.
- **Game totals:** the miss went from 7.54 to 6.34 points.
  - The main cause was pace. Market totals follow how fast the two teams play, and Stage 2 hardly told fast teams from
    slow ones.
  - Now both teams' pace habits set the game's speed.
  - Today's engine's "recent form" term is in too, at today's own strength.
- **Matchups:** each scorer now has his own defender.
  - Who guards whom follows size, puts the best on-ball stopper on the top scorer, and hides the rim protector on the
    weakest shooter. It matches Basketball Index's record of whom each defender actually guarded.
  - That defender's closeouts, on-ball contests, containment on drives, post defense and ball pressure now change
    the shot, the foul and the turnover.
  - Per player, turnovers (.85) and steals (.83) now track real stats better than today's engine does (.77 and .73).
  - Free throws improved a little (.86, today .91). Guards who live at the line are still under-predicted.
- **Speed:** 5.9 thousandths of a second per game, well inside the budget of 20-40.

## What changed
All changes are in `src/nba_gm_data/stage2/`, the research scripts and the tests. `sim.py` and every other shared file
are untouched, so today's engine plays exactly as before.

### Part 1: game totals
**Why totals missed by 7.5 points.** The check is `scripts/research/s2_totals_check.py`. It replays every 2025-26 game
8 times on each engine and compares with the market and the real box scores.

- **League level was fine.** Stage 2 sat 1.9 points under the market on average.
- **Overtime was rare.** It came up in 2.1% of games against a real 4.4%, in both engines. That is worth under half a
  point.
- **The miss was the game-to-game pattern.** Stage 2's expected totals followed the market's with a correlation of
  only .26 (today's engine .53).
  - A simple "oracle" built from each team's real first-half pace and ratings follows second-half market totals at
    .68.
  - Its pace part alone reaches .67. Its scoring-efficiency part reaches only .08.
  - So market totals are mostly about pace.
- **Stage 2's teams barely differed in pace.**
  - The spread across teams was 0.6 possessions a game against a real 2.1.
  - The correlation with real team pace was .55.
  - Only the offense's pace habit counted, and weakly: game pace rose by 37 possessions per unit of the two lineups'
    combined pace habit, against a real 77.

**Fixes.** Each was fitted on the first half of the season and checked on the second (`scripts/research/s2_totals_fit.py`):
1. **Both fives' pace habit sets the length of a half-court possession**, the defending five's as well as the
   offense's. Pace is a game-level thing.
   - The weight was set so that the slope matches the real first-half slope: 80 against a real 77. On the second half
     it was 89 against a real 102.
   - Team pace now correlates .78 with real (was .55) and spreads 1.3 possessions (was 0.6).
2. **Recent form**, from both teams' last ten games before tonight. This is today's engine's own term, at today's own
   strength.
   - A stronger setting fitted the market a little better. It was kept at today's strength because, in a saved
     season, a stronger term would let the sim's own scoring feed back into its pace.
   - It is the one term here not built from player inputs.
   - Without it, the final engine's total miss is 6.78 instead of 6.20 (seed 1001), and win-picking is unchanged
     (Brier .1995 either way).
3. **Last-shot play.** A team that is tied or behind by 1-3 points in the last 24 seconds holds for the last shot, and
   takes a three when down three. Overtime rose only to 2.4%: this is a small piece.
4. **Generated games** center the pace habit on projected minutes, as today's engine does. Coaches give quicker
   players more minutes than real 2025-26 minutes did, which would otherwise add two possessions to every game.
5. **A league scoring level** was re-centered once the matchups were in.

### Part 2: player-on-player matchups and closeouts
**Who guards whom** (`stage2/matchups.py`).
- Each time either five changes, the defense picks the best of the 120 possible pairings. It weighs:
  - size: like guards like;
  - stoppers: the best on-ball stopper (containment, contact leverage, anticipation, lateral quickness) goes to the
    scorer who ends the most possessions, scaled by the head coach's matchup rating;
  - hiding: the rim protector takes the scorer who spaces the floor least.
- **The weights were fitted to Basketball Index's 2025-26 per-defender data**, "Avg Height Guarded" and "Guarded
  USG%", on half the defenders and checked on the other half (`scripts/research/s2_matchups_fit.py`).
  - On held-out defenders, the usage of the players each one guards now correlates .65 with real. The old rule,
    tallest guards tallest, managed .25.
  - Height guarded stays at .85.
- Rebound positions keep their own height-matched rule, which the rebound piece was fitted with.

**The defender's skills, by action.** These live in `game.py` (`_pair_terms`, `_shot`, `_pressure`).

| Action | What the defender brings |
|---|---|
| Catch-and-shoot jumpers | His closeout (closeout technique, lateral quickness, attention), plus the five's rotation |
| Pull-ups and short jumpers | His on-ball contest (containment, contest technique), his length, and his height over the shooter |
| Drives | The chance the driver gets past him: burst, dribble manipulation and separation against containment, contact leverage, anticipation and lateral quickness. Past him, the driver meets the help (the five's rim protection) and draws more fouls; the defender's foul control decides how many. |
| Post-ups | His post defense: contact leverage, strength and height |
| Turnovers | Half his own ball pressure, half the five's, plus the five's passing-lane defense |

The fast rules stand in for the exact physics pieces: `creation_passing.containment_response` and `helper_response`,
and the closeout parts of `shot_geometry`. Those stay as the references.

**Fitted numbers** (no player rating touched anywhere):
- **Team strength:**
  - The defense numbers were found by a coordinate search on how closely the engine's expected margins follow the
    market's spreads, first half of 2025-26 (`scripts/research/s2_matchups_tune.py strength`).
  - Then one common scale (0.8), chosen by the first half's miss against the spreads.
  - Then the defense alone ×0.85, because teams' defensive ratings spread 4.9 points per 100 against a real 3.4.
  - Second half: correlation with the spreads .743 → .776.
- **Free throws by action** (`scripts/research/s2_foul_fit.py`):
  - Every shot try in replayed games is recorded with its foul terms, so the numbers are fitted on expected free
    throws instead of noisy replays. The fit uses half the players, with league free throws held at the real level.
  - Result: drives draw the most contact; finishing a teammate's pass draws far less. Foul-drawing craft counts most
    on drives and pull-ups, and getting past your man draws fouls.
  - Held-out players: miss in free throws per shot .0707 → .0622, correlation .825 → .858.
- **Turnovers:** the rule was refit with separation, strength and balance added. A balanced body protects the ball.
  - Held-out players: correlation .74 → .81.
  - In games, the high-usage creators come down. Cunningham went from 6.2 to 5.5 per 36 (real 3.9), Edwards from 4.9
    to under 4.

## Scorecards side by side
### Betting test (20 runs a game, 1,231 games, 1,018 with market odds)

| | Today's engine | Stage 2 loop version | Stage 2 after part 1 (totals) | **Stage 2 final** |
|---|---|---|---|---|
| Brier, seed 1001 | .2041 | .2009 | .1990 | **.1995** |
| Brier, seed 2001 | .1972 | .2020 | .2008 | **.1948** |
| **Brier, average** (market .1962) | .2007 | .2015 | .1999 | **.1972** |
| Log loss, seed 1001 | .5975 | .5896 | .5875 | **.5854** |
| Log loss, seed 2001 | .5808 | .5952 | .5895 | **.5777** |
| **Log loss, average** (market .5740) | .5892 | .5924 | .5885 | **.5816** |
| Spread miss vs market, average (points) | **4.01** | 4.55 | 4.57 | 4.41 |
| Total miss vs market, average (points) | **5.53** | 7.54 | 6.42 | 6.34 |
| Total miss, seed 1001 / 2001 | 5.51 / 5.55 | 7.49 / 7.60 | 6.40 / 6.44 | 6.20 / 6.47 |

- **Plainly:** Stage 2 now beats today's engine at picking winners on both seeds, by about .0035 on Brier and .008 on
  log loss. It does not beat it on spreads or totals.
- **Why totals still trail:**
  1. Team scoring levels are less exact. Offensive rating correlates .79 with real (today's .89), defensive rating
     .87 (today's .91).
  2. Stage 2's games vary more around their own expectation: a 16.4-point spread in totals against today's 13.6
     (real games vary about 18.5 around the market). That adds noise to a 20-run average.
- Today's numbers for seed 1001 were reproduced by the loop piece; seed 2001 comes from the rating-ceiling report
  (same code, default engine untouched).

### What makes up the total miss (8 runs a game, all games)

| | Today | Loop version | After part 1 | Final |
|---|---|---|---|---|
| Expected totals: correlation with the market | .53 | .26 | .54 | .55 |
| Team pace: correlation with real | .84 | .55 | .75 | .78 |
| Team pace: spread across teams (real 2.05) | 1.14 | 0.64 | 1.38 | 1.34 |
| Offensive rating: correlation with real | .89 | .76 | .77 | .79 |
| Defensive rating: correlation with real | .91 | .83 | .85 | .87 |
| Team-by-team total error spread (points) | 2.9 | 4.7 | 4.0 | 3.7 |
| Overtime rate (real 4.4%) | 2.1% | 2.1% | 2.6% | 2.4% |

### Real-stat targets (`calibration_report.py --engine stage2`, 150 generated games, seed 1)

| | Today | Loop version | Final |
|---|---|---|---|
| League numbers in range | 18 / 18 | 18 / 18 | **18 / 18** |
| Average distance from the real average (team spreads) | .38 | .24 | **.20** |
| Largest distance | .86 | .62 | **.57** (assists) |
| Pace | | | 102.2 (real 102.0) |

### Per player, replayed games (600 games, real minutes, seed 1): correlation with real per-36 (all / held-out half)

| Stat | Today's engine | Stage 2 loop version | **Stage 2 final** |
|---|---|---|---|
| Points | **.945 / .944** | .924 / .924 | .921 / .916 |
| Free throws | **.912 / .914** | .846 / .856 | .858 / .861 |
| Threes attempted | **.989 / .989** | .952 / .954 | .948 / .942 |
| Assists | **.940 / .934** | .893 / .909 | .905 / .919 |
| **Turnovers** | .773 / .786 | .793 / .785 | **.845 / .833** |
| **Steals** | .728 / .747 | .793 / .826 | **.831 / .836** |
| Blocks | .842 / .837 | .851 / .837 | **.858 / .847** |
| Rebounds | .943 / .959 | .925 / .935 | .942 / .949 |

Today's engine reads each player's real 2025-26 rates through fits made on this same season, so on this season it is
close to a lookup. Stage 2 builds them from what each player does on each possession.

### Speed

| | Stage 2 final | Loop version | Today |
|---|---|---|---|
| Per game (600 replayed games) | **5.9 ms** | 4.5 ms | 12.3 ms |

The full betting run took 135 s for 24,620 games on the busy laptop. Choosing who guards whom (120 pairings) runs only
when a five changes.

## The weak spots left (named players)
- **Free throws, under:** Avdija (.38 per shot against a real .57), Dončić, Castle, Reaves, Mathurin, Harden.
  - Their foul-drawing craft grades (65-81) do not set them apart from the big men who draw fewer fouls.
  - Avdija's 68 sits well below what his real free-throw rate implies. That is a question for the ratings team (rule
    1), not something to tune here.
- **Free throws, over:** Flagg, Ingram, Duren, Şengün, Barnes. They are mostly rim-heavy players with mid-60s craft.
- **Star turnovers:** still high for Banchero (5.1 per 36 against a real 3.2), Brown (5.4 against 3.8) and
  Cunningham (5.5 against 3.9).
  - The loop now matches each player's card. The card itself is off, because these players' handle-security grades
    are low (Banchero 42, Brown 46, Cunningham 49, Avdija 44) while their real turnover rates are average for their
    usage.
  - Worth a ratings-evidence check of whether handle security was estimated from raw turnover counts without
    adjusting for usage.
- **Defensive ratings** still spread 4.3 points per 100 across teams against a real 3.4.

## What is still a stand-in
- **Switching and schemes:** the coach inputs hold no switching habit or defensive scheme. The coach's matchup rating
  only scales how hard he chases the stopper matchup. There are no switches on screens, no drop or hedge coverages, and
  no double teams.
- **Unfitted matchup numbers.** These are documented stand-ins, checked only through the league numbers:
  - the drive numbers, i.e. the beat-chance level and slope and the defender's foul control;
  - the length term on pull-ups;
  - the passing-lane term;
  - the half-and-half split of ball pressure.
- **Help on drives** is the five's rim protection as a whole, not the nearest helper's arrival time.
- **Rebound positions** still use height matching, not the new assignments.
- **Recent form** is today's engine's term, not something built from the players.
- **End-game:** run out the clock, foul when behind, play for the last shot. There are no timeouts, no advancing the
  ball, no fouling up three. Overtime is 2.4% against a real 4.4%.
- **Substitutions:** still today's planned minutes plus the simple live rotation from the loop piece.
- **Fitted on the same season:** the team-strength and pace numbers were fitted on the first half of 2025-26 and
  checked on the second half, the same season the ratings come from.

## Recommended next piece
**A proper coach: rotations and in-game decisions from the coach model.** The remaining spread and total misses are
team-level: scoring levels and how much games swing. Today's engine still has the better team-level picture because
its minutes and lineup choices come from the coach model with matchups, foul trouble, hot hands and blowouts.

Fold in two pieces with it:
1. **Screens and switching:** pick-and-roll coverages from the screen-navigation piece, so stars meet switches and
   help, not only their assigned man.
2. **A ratings-evidence check** for the creators whose foul-drawing and handle-security grades disagree with their
   real free-throw and turnover rates (listed above). Rule 1: that check belongs to the ratings team, with its own
   evidence.

## Files
- **New:**
  - `src/nba_gm_data/stage2/matchups.py`;
  - research scripts `s2_totals_check.py`, `s2_totals_fit.py`, `s2_matchups_fit.py`, `s2_matchups_tune.py`,
    `s2_foul_fit.py` and `s2_odds.py`, all in `scripts/research/`;
  - `tests/test_stage2_totals_matchups.py` (8 tests).
- **Changed:**
  - `stage2/game.py`: pace from both fives, recent form, last shot, matchup terms, fouls by action and craft, the
    research trace hook (off in play), refit numbers;
  - `stage2/cards.py`: matchup indices and the turnover refit;
  - `stage2/engine.py`: league centers, the coach matchup scale, recent form and the generated-game pace center;
  - `stage2/loop_fit.py`: turnover terms;
  - `scripts/research/s2_possession_loop_check.py`: an `--engines` option and per-player rows.
- **Not changed:** `sim.py`, `calibration_report.py`, `cli.py`, ratings and inputs files, and everything outside
  Stage 2. Today's engine is byte-identical by construction; the seam test still checks that the default engine equals
  an explicit "current".
- **Output (git-ignored):**
  - `output/stage2/odds_stage2_{totals,matchups,noform}_*.json`;
  - `totals_games_*.json` and `totals_report.json`;
  - `check_final.json`, `cal_stage2_final.json`, `matchups_fit.json`, `foul_fit.json`;
  - scratch scripts in `output/stage2/tm/`.

## Checks
- **Stage 2 tests:**
  - `tests.test_stage2_totals_matchups` (new: assignment by size and by stopper, defender indices, drive beat chance
    and fouls, matchups on and off both play deterministically, both fives set the pace, trace off in play, recent
    form is today's term);
  - plus `test_stage2_possession_loop`, `test_stage2_seam`, `test_stage2_rebound_fouls` and
    `test_stage2_league_inputs`.
- **Core tests:** `bash scripts/run_core_tests.sh`: 338 tests OK (2 skipped). Stage 2 tests: 46 OK.
- **Laptop:** one heavy job at a time, all `nice -n 10`. Runs waited while the 1-minute load was above 20 (it peaked
  at 41 from other agents). The odds runs ran locally, about 2.3 minutes each, because the Azure worker was busy with
  another job.

## Resume state
- [x] Totals diagnosis and fixes (commit d7eb4a5); part-1 odds runs.
- [x] Matchups, fouls, turnovers and strength fits (938623d, e7c1eda); final odds runs (both seeds), no-form ablation,
  per-player check, totals decomposition, scorecard 18/18.
- [x] Report. Board row set to review.
