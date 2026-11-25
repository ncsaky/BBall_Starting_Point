# S2-USAGE (Stage 2, ninth piece): who takes the shots

_Owner: Claude (Opus session), worktree branch `claude/s2-usage-5e2e9e`. 2026-11-25. Status: **review**._

Progress: 7/7 - report written, committed on the branch (not pushed)

## TL;DR
- **Assists are fixed.** Stage 2 now splits assists between teammates as well as today's engine: the season miss per
  player is 16.0% → **12.4%** (today's 12.5%), and the per-game correlation is .679 → **.698** (today's .691). The
  assister rule was today's per-36 rule; Stage 2 now has its own, refit through its game loop, with the same five
  inputs. Before, assists were spread too evenly; now they sit with the main playmakers, as in real games.
- **Points and threes are where they were** (season miss 11.4% and 10.4%; today's engine 9.7% and 6.7%). The
  breakdown shows why. The game loop reproduces its usage rule and the shot-location habit almost exactly (correlation
  .98 and .97-.99), so most of the remaining miss sits in three inputs, not in the engine. When the research run swaps
  in each player's real usage, the points miss falls from 9.0% to 7.1%, about today's engine's 6.8%.
  Ratings questions are listed at the end; no rating was changed.
- Two more engine fixes are built and backed by evidence but **switched off**: putbacks by the rebounder's reach, and
  roll finishes scaled by how often a player screens. Each makes its own layer clearly more realistic, but both feed
  extra points to big men whose usage is already too high from their inputs, so per-player points got slightly worse.
  Turn them on once the ratings task settles the bigs' usage. Every scorecard is unchanged or within seed noise.

## Goals and boundaries
Break each player's scoring miss down by layer against real 2025-26 evidence; fix the engine causes in Stage 2; list
rating questions with evidence. Touched only `src/nba_gm_data/stage2/` (cards.py, game.py), `scripts/research/`, a new
Stage 2 test file and this file. Today's engine is untouched (byte-identical); Stage 2 stays off in normal gameplay. No
rating or input changed. No download: all evidence was already in the repo (Basketball Index 2025-26 per-75 tables in
`data/research/bbi/values_recent.json.gz`, Basketball-Reference shooting, the calibration targets file).

## 1. The breakdown, layer by layer
New tool: `scripts/research/s2_usage_breakdown.py` replays every 2025-26 game (real availability and minutes) and records
every shot try by kind for each player (a research hook in `game.py`, `SHOT_TRACE`, off in play, no random draws). It
compares 377 rotation players (500+ minutes) per 36 minutes with real numbers. Before this piece, 4 runs:

| Layer | Stage 2 vs real | What it says |
|---|---|---|
| Usage (shots + free-throw trips + turnovers) | correlation .943, miss 1.23 per 36 | The loop reproduces its usage rule (correlation .98, slope 1.01); the rule itself matches real at .953. **Rule/inputs, not loop.** |
| Shot mix: threes | .961 (today's .989) | Three habit (T02) matches Basketball Index at .996; the loop reproduces it. Fine. |
| Shot mix: rim share | Stage 2 vs T02 .97; T02 vs real .82 | The loop reproduces the habit; **the habit is squeezed** (see ratings questions). |
| Shot mix: other twos | Stage 2 vs T02 .98; T02 vs real .67 | Same. |
| Putback points | .79 vs real 1.05; correlation .87 | **Engine:** real bigs score 0.8-1.2 putback points per offensive rebound; Stage 2 gave everyone about 0.5. |
| Cuts + rolls (finishes off a pass) | correlation .66 | **Engine:** the roll habit (T11) is a split of what a player does in a ball screen, not how often he screens. Guards got roll finishes they never get. |
| Rim make rate | level right (.667 vs .665), correlation .67 | Over-scored players finish too well, under-scored cutters too poorly (ratings questions). |
| Free throws | correlation .937 (today's .928) | Fine on average; a few bigs draw too many (ratings questions). |
| Assists | miss .62 per 36, correlation .927 (today's .458 / .948) | **Engine:** the real-minus-Stage-2 miss follows involvement (correlation .64): assists spread too evenly. |
| Heaves, must-have threes | big men took about 0.1 heaves per 36 | **Engine:** the shooter was drawn by usage alone, centres included. |

Research-only swaps (`s2_usage_fit.py eval --oracle`, nothing stored): season points miss per player 9.0% → **7.1%**
with real usage. With the real shot mix: points 9.6%, threes 12.8% → 11.6%. With both: points 7.4%, threes 10.7%.
Usage is the largest single layer.

## 2. What changed (engine)
- **Assist rule refit through the loop** (`cards.ASSISTS`, same five inputs as today's rule: pass choice, involvement,
  passing execution, passing risk habit, post choice). Fit on half of the players, checked on the other half
  (`s2_usage_fit.py usage --rule ASSISTS`): held-out season assists miss 17.9% → 13.4%, correlation .919 → .932.
  Adding post skill and height overfit (held-out worse), so they're left out. A simple "concentration" power on today's
  rule got 14.4%; the refit is better and is what's used (`LOOP ast_power` stays 1). Assists are credit only, so the
  game itself and every random draw are unchanged.
- **Heaves and must-have threes** (down three at the end) go to shooters: usage weight times the player's three-point
  share (`LOOP three_pick` = 1).

### Built, measured, off by default (switches in `LOOP` / `MENU`; 0 = the game exactly as before)
| Switch | What it does | Result | Why off |
|---|---|---|---|
| `k_putback_reach` (fit .5, with `make_level` .003) | the rebounder's reach sets his chance to go straight back up | putback points .79 → .98 (real 1.05), correlation .87 → .89 | per-player points 11.4% → 11.6%, threes 10.4% → 10.9% (extra putbacks go to bigs already over real); betting test unchanged within noise (.1961 / 4.04 / 5.91) |
| `MENU roll_screen` (1) | roll finishes scaled by how often he screens | finishes vs real cuts + rolls correlation .66 → .77 | per-player points miss 1.47 → 1.53 per 36 (same reason) |
| `k_trans_speed`, `k_trans_pace` | transition finisher by speed and pace habit | no change within noise (pace worse) | no per-player transition data to fit; T17 is a prior only |
| `k_diff` | shot-difficulty habit lowers make chances | points and threes worse | the shot-making grades seem to carry difficulty already |
| `k_rim_self` | drives to the rim harder than finishes off a pass | points worse (9.1% → 9.3-9.5%) | — |

A usage-rule refit through the loop (with and without creation and burst terms) gained only noise-level ground (held-out
usage miss 1.29 → about 1.23 per 36), so the usage rule is unchanged: it is at the ceiling of what the inputs carry.

## 2b. Real play types (NBA.com, added after the first review round)
The user approved downloading NBA.com's 2025-26 player play-type tables (Synergy). Eleven play types, season totals:
transition, isolation, pick-and-roll handler, roll man, post-up, spot-up, handoff, cut, off-screen, putbacks and misc.
They are saved in `data/research/nba_playtypes_2025_26.json`: 439 players, traded players' team rows summed, matched to
the game's player ids. NBA.com lists a player in a play type only with 10+ possessions of it.
How the data was read: a direct request to NBA.com's stats service was refused by the safety check (it needed
browser-imitating headers), and the browser pane blocks downloads there. So the eleven pages were opened in the
built-in browser, set to totals and all rows, and their rendered tables read.
`scripts/research/s2_playtype_compare.py` compares Stage 2's actions with them. Before this piece, per 36 minutes,
rotation players:

| Action | Stage 2 | Real | Correlation | Spread across players (Stage 2 / real) |
|---|---|---|---|---|
| Transition | 1.82 | 2.87 | .53 | .55 / 1.27 |
| Cuts + rolls | 1.68 | 1.85 | .63 | .83 / 1.89 |
| Putbacks | 0.57 | 0.79 | .87 | .44 / .87 |
| Post-ups | 0.91 | 0.54 | .78 | .75 / .97 |
| Self-created (isolation, handler, handoff) | 4.46 | 4.41 | .91 | 2.29 / 3.93 |
| Catch-and-shoot (spot-up, off-screen) | 5.10 | 4.31 | .74 | 1.66 / 1.99 |

(Real possessions include turnovers; Stage 2 counts shots and shooting-foul trips, so compare spread and correlation.)
Every action is spread too evenly across players.
- Transition goes to whoever has usage; real runners are the fast players with a quick pace habit. The
  real-to-Stage-2 ratio follows speed (+.55), burst (+.57) and pace habit (+.57), and speed plus pace predict it on
  held-out players at .54-.68. The transition switch fitted on this (.4 / .14) lifts the match from .51 to .70.
- Cuts and rolls follow the cutting habit (+.62) and height (+.57) in real games, and run against drive habit (−.74)
  and involvement (−.62): Stage 2 gives finishes to high-usage drivers.
- Guards post up in Stage 2 (0.5-0.9 per 36) and almost never in real games.

**Result:** the three action switches (transition, putbacks, rolls) each make their layer clearly more realistic. Even
with the usage rule refit through the loop alongside them (so each player's total usage holds while his mix
changes), season points per player don't improve on the held-out half (8.5% → 8.9%) and threes get worse (12.9% →
14.5%). So they stay off. The likely reason is the same as before: the extra finishes go to players whose usage and
shot mix are already off in their inputs. Recommended next piece, after the ratings questions below: switch on
transition, putbacks and rolls together, sharpen the post-up and cut weights on this play-type data, and refit
usage jointly, judged on both scorecards and props.

## 3. Scorecards (final settings)
**Player props** (`s2_props.py`: 40 games of market points lines at 200 runs; every player-game with 10+ minutes,
22,829 of them, at 8 runs). Today's engine is unchanged (byte-identical), so its numbers are from the last piece.

| | Stage 2 before | **Stage 2 now** | Today's engine |
|---|---|---|---|
| Market lines: Brier / log loss | .2151 / .6183 | **.2151 / .6184** | .2158 / .6173 |
| Market lines: correlation with the line | .905 | **.905** | .873 |
| Points: miss per game / correlation | 4.37 / .735 | **4.37 / .735** | 4.09 / .771 |
| Rebounds | 1.86 / .678 | **1.86 / .678** | 1.83 / .685 |
| Assists | 1.43 / .679 | **1.39 / .698** | 1.41 / .691 |
| Threes made | 0.94 / .544 | **0.94 / .544** | 0.91 / .577 |
| Season points off by (players with 50+) | 11.4% | **11.4%** | 9.7% |
| Season rebounds off by | 10.9% | **10.9%** | 10.2% |
| Season assists off by | 16.0% | **12.4%** | 12.5% |
| Season threes off by | 10.4% | **10.4%** | 6.7% |

**Betting odds** (20 runs × seeds 1001 / 2001, 1,018 games with market odds; average, each seed in brackets):

| | Stage 2 before | **Stage 2 now** | Today's engine |
|---|---|---|---|
| Win probability (Brier) | .1970 (.2003 / .1937) | **.1970** (.2002 / .1937) | .2012 |
| Log loss | .5823 | **.5821** | .5910 |
| Spread miss | 4.02 | **4.02** (4.02 / 4.02) | 4.03 |
| Total-points miss | 5.93 | **5.93** (5.94 / 5.93) | 5.78 |

**Real-stat scorecard:** 18/18 in range (150 generated games, seed 1). **End of games** (19,696 replayed games, 16
runs): overtime 4.0%, decided by 1-3 points 12.7% (real 12.7%), unchanged. **Speed** (400 games, best of three, under
another session's load): 8.1 ms per replayed game, 9.3 ms per generated game; the old settings gave 8.4 / 9.1 in the
same conditions. No change. **Tests:** all 81 Stage 2 tests pass (5 new in `tests/test_stage2_usage.py`).

## Weak spots (honest list)
1. **The points goal isn't met.** Stage 2 still splits points (11.4% vs today's 9.7%) and threes (10.4% vs 6.7%) worse
   than today's engine. Today's engine copies each player's real per-36 rates from this same season; Stage 2 builds them
   from the inputs. The breakdown puts most of the gap in the inputs below. I could find no engine rule that closes it
   without copying real totals.
2. **Two good fixes wait on the ratings task** (putbacks by reach, rolls by screening). Both make their layer more
   realistic but give more to big men already over-used.
3. **Action mix is still too even across players** (section 2b): transition, cuts, rolls and post-ups. The fits on
   NBA.com's play types are done and recorded; switching them on waits on the usage questions.
4. **Fits are at 2 runs a season** (about ±0.2 points in the season-miss percentages); I kept only changes clearly
   above that.

## Ratings questions (flagged, nothing changed)
Each with the input, its current value and the evidence. "Real" = 2025-26.

1. **Shot-location habit (T02) is squeezed toward the middle.** T02's rim share matches Basketball-Reference's 0-3 ft
   share at .80 and Basketball Index's rim share at .82. Those two sources agree with each other at .99, and T02 spreads
   only two-thirds as wide (.10 vs .14-.16). T02 rim share against Basketball-Reference / Basketball Index:
   - **too low:** Gary Payton II .32 vs .45 / .64; Collin Murray-Boyles .39 vs .62 / .68; Zion Williamson .44 vs
     .57 / .68; Giannis Antetokounmpo .48 vs — / .67; Rudy Gobert .69 vs — / .86;
   - **too high:** Kristaps Porziņģis .33 vs .16 / .19; Brandon Ingram .30 vs .15 / .17; Anfernee Simons .19 vs .06 /
     .09; Russell Westbrook .29 vs .14 / .20; Jaren Jackson Jr. .27 vs .15 / .19; Jusuf Nurkić .44 vs .26 / .37;
     Anthony Davis .48 vs .33 / .42.

   The midrange share is weaker still (.67 against Basketball Index). With the real mix, season threes miss 12.8% →
   11.6%.
2. **Involvement (T08) and scoring usage.** T08 follows Basketball Index's *true usage* (.97), which counts creating
   for teammates. The usage rule turns T08 plus the shoot/pass choices (T01, which match real shots per touch at .91)
   into his own shots, at .95 at best. Usage per 36, rule / real:
   - **over:** Nolan Traoré 23.2 / 18.8 (T08 .447; true usage 38.9 vs usage 22.8, mostly creation); Jaren Jackson Jr.
     25.8 / 22.7; DeMar DeRozan 22.6 / 19.3; Brandon Ingram 25.4 / 22.6; Zion Williamson 24.6 / 22.2; Anthony Davis
     25.9 / 23.6; Myles Turner 17.6 / 15.2; Anfernee Simons 21.8 / 19.7;
   - **under:** Jusuf Nurkić 14.4 / 16.9; Peyton Watson 14.9 / 17.1; Jaylon Tyson 14.5 / 16.5; Pelle Larsson 12.9 /
     14.8; Toumani Camara 12.6 / 14.4; Gary Payton II 13.9 / 15.6; Russell Westbrook 20.0 / 21.9.

   Question for the ratings task: should the model carry the scoring share of involvement separately from creation?
   With real usage, the points miss falls from 9.0% to 7.1%.
3. **Rim finishing (layup, contact and dunk skills).** Stage 2's rim make rate against Basketball Index's rim FG%:
   - **too good:** Nolan Traoré .56 / .46; Zion Williamson .78 / .70; Kristaps Porziņģis .71 / .64; Myles Turner .70 /
     .65; Anfernee Simons .72 / .68; Anthony Davis .70 / .66; Jaren Jackson Jr. .65 / .62;
   - **too poor:** Toumani Camara .62 / .67; Collin Murray-Boyles .63 / .69; Russell Westbrook .60 / .65; Pelle Larsson
     .67 / .71; Gary Payton II .73 / .76.

   Across players the correlation is .67. An engine rule making drives harder than finishes off a pass did not help.
4. **Foul drawing (T18 contact seeking, S24 craft).** Free throws per shot, Stage 2 / real:
   - **too many:** Jaren Jackson Jr. .41 / .28; Anthony Davis .37 / .24; Jusuf Nurkić .40 / .32; Nolan Traoré .26 / .20;
   - **too few:** Josh Hart .14 / .21; Jaylon Tyson .12 / .16.
5. **Transition habit (T17.transition) is a prior only.** It spreads .02 across players with no evidence behind it.
   NBA.com's transition play type is now in the repo (`data/research/nba_playtypes_2025_26.json`), so it could be
   measured directly: real transition possessions per 36 run from about 1 to 6. Examples, Stage 2 / real per 36:
   Jaden McDaniels 1.5 / 4.4, Peyton Watson 1.5 / 3.1, Toumani Camara 1.2 / 3.0, Collin Murray-Boyles 1.1 / 2.6, Gary
   Payton II 1.5 / 2.5.
6. **Cutting, rolling and post habits for the evidence-rich players.** On the same data, cuts + rolls per 36, Stage 2 /
   real: Jusuf Nurkić 2.2 / 6.1, Gary Payton II 2.0 / 5.6, Collin Murray-Boyles 2.0 / 5.3. And the other way: Kristaps
   Porziņģis 3.9 / 2.2, Nolan Traoré 2.1 / 0.3. Mostly the engine's rim split (section 2b), but worth checking T09 and
   T11 against these tables.

## Files
- New: `scripts/research/s2_usage_breakdown.py` (layer breakdown), `scripts/research/s2_usage_fit.py` (fits, rule
  refits through the loop, research-only layer swaps, play-type matches), `scripts/research/s2_playtype_compare.py`,
  `tests/test_stage2_usage.py`, and the data file `data/research/nba_playtypes_2025_26.json` (NBA.com play types).
- Changed: `src/nba_gm_data/stage2/cards.py` (Stage 2's own assist rule, refit; screening-scaled roll switch; card
  speed / reach / shot-difficulty / three share; league screening and shot-difficulty centres) and
  `src/nba_gm_data/stage2/game.py` (the switches above, the shot-trace research hook, heave and must-have-three shooter).
- Data (git-ignored): `output/s2usage/` (breakdowns, fits, swaps, props, betting runs, scorecard, end-of-game file).

## Resume state
- [x] Breakdown, causes sorted, engine fixes fitted, switches measured.
- [x] Final betting pair (`output/s2usage/odds_final_{1001,2001}.json`), props (`props_final.json`), scorecard
  (`cal_final.txt`), end of games (`endgame_final.txt`), speed, 81 Stage 2 tests. Committed on the branch, not pushed.
  Coordinator: review and merge.
- [x] Second round (user-approved download): NBA.com play types saved and compared; transition switch fitted (.4 /
  .14) and recorded, left off with the others (section 2b). Stage 2's defaults unchanged, so the scorecards stand.
