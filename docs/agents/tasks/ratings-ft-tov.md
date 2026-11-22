# RATINGS-FT-TOV: foul drawing and ball security, evidence check

Owner: Claude (Opus agent), worktree branch `worktree-agent-a5435b0fa15dc4040`. Status: **review** (committed on the
branch; not pushed, not merged). Asked by the Stage 2 engine report ("Ratings questions to flag").

## TL;DR

1. **Foul drawing was measured the wrong way, and that is fixed for everyone.** It is now "free throws earned per
   chance": a player's free throws against what an average player earns from the same drives, rim shots, other twos
   and threes. The lead guards who live at the line now grade as elite (Harden 81 -> 90, Dončić 76 -> 89, Avdija 68 ->
   86, Reaves 77 -> 86, Castle 65 -> 77, Trae Young 68 -> 84); Anthony Davis drops (72 -> 64) and Ayton stays low
   (27 -> 18). On a held-out season it predicts free throws clearly better than the old measure.
2. **Ball security: the suspicion did not hold.** The grade was already per play used (not raw counts), and even after
   a full adjustment for creation load and usage, Banchero, Brown, Cunningham and Avdija really do turn it over more
   than an average player with their load (8-23% more). The analysts say the same. Their grades stay low (28-41).
   The new measure is still better on held-out data and spreads the league more (safest: Tyus Jones, SGA, Brunson,
   Haliburton, Butler, Maxey). **Stage 2 over-produces their turnovers by 50-70% (Brown 6.5 per 36 against a real
   3.8), far beyond what any evidence-based card says. That gap is in the engine, not the cards.**
3. Gates: real-stat scorecards hold 18/18 on both engines. Today's engine gets better per player on both turnovers and
   free throws (correlation with real .868 -> .896 and .929 -> .936), but its league free-throw level rises (23.6 ->
   24.7 per 100, still in band). Stage 2 gets better on free throws (.890 -> .926, misses .74 -> .69) but its turnovers
   rise (league 14.3 -> 15.0 per 100, still in band; per-player miss .37 -> .47). Betting test: winner-picking
   unchanged (Brier .204 / .1972 on the two seeds, same as before); spreads and totals 0.06-0.10 points further from
   the market. Two tests move: Giannis drops to 10th in trade value (the test wants top 8) and a noisy Stage 2 pace
   test flips; details in section 6. Rebuild command: section 7.

## 1. How each rating was built before

**Foul drawing** (the foul-drawing craft input) went through four layers:
1. The estimator's prior: position and role, nudged by the old "rim pressure" trait and the raw free-throw rate
   (free throws per shot) from the Crafted NBA snapshot.
2. The Basketball Index overlay (80% weight for a full-time player): the season percentile of fouls drawn per drive
   (primary), a second "drive foul rate" column (which turns out to be an exact copy of the first), the three-point
   foul rate, and the isolation foul rate (all zeros in 2025-26, already weighted out).
3. Analyst claims, last.

The weakness: fouls per drive covers only part of how a player earns free throws (Avdija earned about half of his on
drives; the rest came from post-ups, rim shots, transition and the bonus), and it repeats only 0.62-0.67 from one
season to the next. Big men who drive a few times a game could post high per-drive rates (Davis 94th percentile).

**Handle security** had the same layers. The overlay used turnovers per play used or created (shots + turnovers +
shot-creating passes; the analyst-first fix from Nov 19), plus lost-ball, live-ball, out-of-bounds and travel
turnovers on the same denominator, and isolation turnover rate (weighted out for low repeatability). So the Stage 2
agent's guess ("raw turnover counts without usage") was not the case. What it lacked: no adjustment for how hard a
creator's plays are, and percentiles against every 500-minute player.

**Contact seeking** (the tendency) was ranked by free throws per 75 possessions, fouls drawn per 75, and a
"shooting fouls drawn" column that is **zero for every player in every season**. Because every player tied, its
repeatability check read the tie order as perfect, so the dead column got full weight and pulled every player toward
the middle.

## 2. The new method (applies to every player with NBA minutes)

Module `src/nba_gm_data/foul_security_evidence.py`, run in `scripts/build_player_inputs.py` right after the Basketball
Index overlay (analyst claims still run last, unchanged). Source: the same Basketball Index Leaderboards Values cache
(2023-24, 2024-25, 2025-26), counts = per-75 values x minutes.

1. **Expected counts.** One league rate per kind of chance, fitted on every player-season with 250+ minutes:
   - Free throws: 0.071 per drive, 0.41 per rim shot, 0.28 per other two, 0.032 per three.
     (Offensive rebounds were tested as an extra chance and add nothing.)
   - All turnovers: 0.049 per shot, 0.035 per shot-creating pass, 0.017 per touch, times a usage factor.
   - Balls lost without a pass or a foul (lost balls, strips, travels, stepping out; offensive fouls and bad passes
     excluded): 0.005 per touch, 0.029 per drive, 0.043 per paint touch, 0.029 per shot, times a usage factor.
   - **Usage factor:** (true usage / league average) to the power 0.21 (all turnovers) or 0.26 (balls lost). A
     player who uses more of the offense draws more attention, so the same load is harder. This is the creation and
     usage adjustment the Stage 2 agent asked for, fitted from the league data. Free throws get no such factor (a
     star's extra free throws are not a difficulty to remove).
2. **Ratio, stabilised.** Observed over expected, pooled over three seasons (weights 1, 0.6, 0.35), then pulled toward
   the player's position-group average by an amount set by the data (gamma-Poisson: the spread of true ratios is the
   observed spread minus counting noise). A player with 60 minutes ends near his role's average; a three-season
   starter keeps his own number.
3. **Grade.** Rank among players with about a season of minutes, turned into a normal score, then
   100 x logistic(1.31 x score), the same scale as every other Basketball Index skill (50 average, 75 about the 80th
   percentile, 90 about the 97th). Handle security averages two signals: all turnovers (weight 1) and balls lost
   (weight 0.5).
4. **Blend** with the estimator's own value by evidence weight (80% evidence for a full-time player), as the overlay
   does. The overlay now skips these two inputs (`measured_by` in the mapping), so the data is not counted twice.
5. **Contact seeking:** the dead all-zero column is removed from its mapping, and the overlay now ignores any column
   that has one value for everyone. Nothing else about that tendency changed.

**Skill vs tendency (rule 7):** how often he drives, shoots at the rim or handles the ball sets the *expected* count,
so it stays in the tendencies (drive share, shot locations, involvement). The grade is only how well he does per
chance.

**Why all turnovers lead handle security:** on the held-out season, all-turnovers-first predicts turnovers best
(table below), and no passing input carries bad-pass turnovers, so dropping them would remove them from the cards.
Balls lost keeps the handle itself visible. A future passing-execution measure could take over the bad passes.

Sources: Basketball Index Leaderboards (Values) for drives, rim attempts, field-goal and three-point attempts, true
shot attempts, potential assists, touches, paint touches, free-throw attempts, turnovers and the turnover-type split
(bad pass, offensive fouls, non-pass); ESPN box scores for the held-out check.

## 3. Held-out check (fit on 2023-24 and 2024-25, scored on 2025-26)

227 players with about a season in the fit years and 1,000+ minutes in 2025-26. Every method, including the old one,
is rebuilt from the two fit seasons only. "Card plus chances" = the grade, calibrated on the fit seasons, times the
held-out season's own chances, compared with the real ESPN rate (the closest test of what an engine does with a card).
Script: `scripts/research/ft_tov_evidence.py validate`.

**Foul drawing**

| | New | Old method | Raw free-throw rate | Today's card (has seen 2025-26) |
|---|---:|---:|---:|---:|
| Rank correlation with 2025-26 free throws per chance | **.742** | .584 | .502 | .702 |
| Rank correlation with 2025-26 free throws per shot (raw) | .540 | .498 | **.825** | .664 |
| Card plus chances: average miss in free throws per shot | **.048** | .058 | .055 | .050 |
| Card plus chances: rank correlation | **.859** | .794 | .801 | .859 |

The raw free-throw rate predicts next season's raw rate best because it also contains how often a player attacks,
which repeats strongly. That part belongs to the tendencies; as a skill measure the raw rate is the worst of the four.

**Handle security**

| | New | Old method | Raw turnovers per play | Today's card (has seen 2025-26) |
|---|---:|---:|---:|---:|
| Rank correlation with 2025-26 turnovers per chance | **.700** | .638 | .691 | .745 |
| Rank correlation with 2025-26 balls lost per chance | **.591** | .523 | .503 | .614 |
| Rank correlation with 2025-26 turnovers per used possession (raw) | .553 | .406 | **.636** | .453 |
| Card plus chances: average miss in turnover rate | .0147 | .0147 | **.0145** | .0123 |
| Card plus chances: rank correlation | .826 | .805 | **.833** | .878 |

Honest reading: the new handle security beats the old method on every skill test and ties it on the outcome test.
The plain "turnovers per play" (no usage adjustment) is a hair better at predicting the raw turnover rate, because the
raw rate itself rises with usage; the usage adjustment moves that part out of the skill on purpose. Variants tried
(balls lost only; all turnovers only; with and without the usage factor) are listed in the resume notes.

## 4. Named players

**What the data says per chance (three seasons, before the blend):**

| Player | Free throws vs expected | Turnovers vs expected (usage-adjusted) | Balls lost vs expected |
|---|---:|---:|---:|
| Deni Avdija | 1.56x | 1.23x | 1.17x |
| Luka Dončić | 1.77x | 1.07x | 0.86x (bad passes 1.54x) |
| Stephon Castle | 1.29x | 1.22x | 1.23x |
| Austin Reaves | 1.59x | 1.06x | 1.03x |
| James Harden | 1.89x | 1.25x | 1.07x (bad passes 1.40x) |
| Anthony Davis | 1.10x | 0.89x | 0.93x |
| Deandre Ayton | 0.54x | 1.14x | 1.04x |
| Paolo Banchero | 1.44x | 1.08x | 1.17x |
| Jaylen Brown | 1.04x | 1.17x | 1.22x |
| Cade Cunningham | 0.93x | 1.12x | 1.00x (bad passes 1.22x) |

**Final grades (after the estimator blend and the analyst claims):**

| Player | Foul drawing before -> after | Handle security before -> after |
|---|---:|---:|
| Deni Avdija | 68 -> **86** | 44 -> 28 |
| Luka Dončić | 76 -> **89** | 72 -> 60 |
| Stephon Castle | 65 -> **77** | 51 -> 42 |
| Austin Reaves | 77 -> **86** | 54 -> 50 |
| James Harden | 81 -> **90** | 52 -> 33 |
| Anthony Davis | 72 -> 64 | 52 -> 65 |
| Deandre Ayton | 27 -> 18 | 28 -> 36 |
| Paolo Banchero | 80 -> 84 | 42 -> 40 |
| Jaylen Brown | 61 -> 60 | 46 -> 30 |
| Cade Cunningham | 60 -> 50 | 49 -> 41 |
| Shai Gilgeous-Alexander | 73 -> 80 | 81 -> 90 |
| Jimmy Butler III | 75 -> 86 | 79 -> 88 |
| Joel Embiid | 85 -> 87 | 50 -> 29 |
| Trae Young | 68 -> 84 | 52 -> 38 |
| Kawhi Leonard | 68 -> 72 | 61 -> 73 |
| Jalen Brunson | 65 -> 67 | 79 -> 88 |

Notes: Cunningham's free throws per chance are below average over three seasons (0.83x in the fit years, 1.09x in
2025-26), so his grade falls; one host's playoff claim ("draws many free throws") moved it up two points. The analysts'
turnover claims (Banchero "turnovers and weak traffic handling", both hosts; Brown and Avdija below average; Cunningham
weak in the playoffs) agree with the data, so they changed little.

## 5. League spread and the top and bottom (players with about a season of minutes, 430)

| | Before | After |
|---|---|---|
| Foul drawing: spread (SD) / 10th-90th percentile / max | 15.0 / 29-69 / 84.9 | **19.1** / 24-77 / 90.1 |
| Handle security: spread / 10th-90th / max | 13.5 / 34-69 / 82.3 | **19.6** / 25-78 / 91.0 |
| Contact seeking (tendency): spread / 10th-90th | .063 / .33-.49 | .076 / .31-.50 |

No value at or near 100 (league max 90.1 and 91.0); nothing clipped; the spread widened (the old percentile blends
compressed both).

**Foul drawing, top 15 after (before -> after):** Harden 81->90, Dončić 76->89, Embiid 85->87, Butler 75->86,
Reaves 77->86, Avdija 68->86, Keyonte George 79->86, Noah Clowney 75->85, Porziņģis 75->85, Dwight Powell 72->85,
Mathurin 75->84, Trae Young 68->84, Banchero 80->84, Tim Hardaway Jr. 80->84, Rudy Gobert 52->84.
**Top 15 before:** Embiid 85, Harden 81, Nick Richards 80, Aaron Gordon 80, Edwards 80, Hardaway 80, Banchero 80,
Towns 79, George 79, Giannis 78, Jerami Grant 78, Markkanen 78, Wembanyama 77, Reaves 77, Garrison Mathews 77.
**Bottom 10 after:** Cason Wallace 13, T.J. McConnell 13, Tyus Jones 14, Dyson Daniels 14, Gary Payton II 15,
Vučević 15, Portis 15, Davion Mitchell 16, Mikal Bridges 17, Sam Hauser 17.
**Bottom 10 before:** Luke Kornet 19, Jericho Sims 20, Spencer Jones 21, Jalen Pickett 21, Mitchell Robinson 23,
Finney-Smith 23, Dylan Cardwell 23, McConnell 24, Jamison Battle 24, Jordan Goodwin 24 (several bigs who rarely drive,
now graded on their rim shots instead).

Analyst read: the new top is the league's known foul-drawing guards (Harden, Dončić, Butler, Trae, Reaves, Avdija,
Embiid, SGA 80). Worth a look: **Rudy Gobert 84 and Dwight Powell 85** (rim runners who really do earn more free
throws per rim shot than average; they are not craftsmen in the Harden sense) and Garrison Mathews / Tim Hardaway Jr.
(three-point foul specialists; real). The bottom is low-foul guards and floater players (McConnell, Tyus Jones, Bridges),
which matches their reputations.

**Handle security, top 15 after:** Tyus Jones 82->91, Hardaway Jr. 81->90, Pritchard 80->90, SGA 81->90, Sam Hauser
76->90, McBride 79->89, Quickley 82->89, Butler 79->88, Brunson 79->88, DeRozan 80->88, Maxey 76->87, Sam Merrill
78->87, Haliburton 80->86, Isaiah Joe 76->86, Tre Jones 78->86.
**Top 15 before:** Tyus Jones 82, Quickley 82, SGA 81, Jamal Murray 81, Hardaway 81, Haliburton 80, DeRozan 80,
Pritchard 80, Butler 79, McBride 79, Brunson 79, Merrill 78, Cam Spencer 78, Tre Jones 78, VanVleet 78.
**Bottom 10 after:** Jericho Sims 9, Adem Bona 11, Nick Richards 12, Hukporti 14, Sharpe 15, Vanderbilt 15, Nurkić 16,
Cissoko 16, Ronald Holland II 17, Vukcevic 17. **Bottom 10 before:** Sims 16, Bona 19, Hukporti 20, Powell 20,
Plumlee 24, Richards 24, Vanderbilt 25, Biyombo 25, Sharpe 25, Gobert 25.

Analyst read: the safe high-usage handlers (SGA, Brunson, Haliburton, Maxey, Butler, DeRozan, Quickley, VanVleet) are
all near the top, as the analysts say. Worth a look: low-usage shooters (Hauser, Merrill, Isaiah Joe, Hardaway) grade
elite because per chance they almost never lose the ball; their handle is rarely tested under pressure.

## 6. Gates (locally rebuilt inputs; the committed inputs file is untouched)

**Real-stat scorecard, 1,230 games, real minutes:**

| | Today's engine before | after | Stage 2 before | after |
|---|---:|---:|---:|---:|
| League targets in band | 18/18 | **18/18** | 18/18 | **18/18** |
| Free throws per 100 (real 22.9) | 23.6 | 24.7 | 22.8 | 22.8 |
| Turnovers per 100 (real 14.1) | 13.1 | 13.6 | 14.3 | 15.0 |
| Offensive rating (real 112.8) | 113.0 | 112.8 | 112.2 | 111.3 |
| Free throws per 36, average bias (sim minus real) | -0.09 | +0.14 | -0.12 | -0.12 |
| Free throws per 36, average miss per player | 0.61 | 0.72 | 0.74 | **0.69** |
| Free throws per 36, correlation with real | .929 | **.936** | .890 | **.926** |
| Turnovers per 36, average bias | -0.06 | +0.05 | +0.15 | +0.28 |
| Turnovers per 36, average miss per player | 0.30 | **0.29** | 0.37 | 0.47 |
| Turnovers per 36, correlation with real | .868 | **.896** | .877 | **.900** |

Named players, free throws per 36 (real / today's engine before -> after / Stage 2 before -> after): Avdija 10.0 /
6.4 -> 8.6 / 5.8 -> 6.7; Dončić 10.1 / 8.8 -> 12.1 / 7.3 -> 8.7; Castle 6.8 / 5.0 -> 6.3 / 5.4 -> 6.3; Reaves 7.6 /
6.4 -> 7.8 / 4.7 -> 5.2; Harden 7.7 / 7.2 -> 9.2 / 5.9 -> 6.7; Ayton 2.6 / 2.7 -> 2.1 / 4.5 -> 3.7; Ingram 4.9 / 5.9 -> 5.4
/ 6.8 -> 5.5; Barnes 4.0 / 4.0 -> 3.9 / 5.9 -> 4.9; Flagg 5.3 / 4.9 -> 4.5 / 7.4 -> 6.4.
Turnovers per 36 (real / today before -> after / Stage 2 before -> after): Banchero 3.2 / 3.4 -> 3.7 / 5.0 -> 4.6;
Brown 3.8 / 3.0 -> 3.4 / 5.4 -> 6.5; Cunningham 3.9 / 4.0 -> 4.0 / 5.2 -> 5.7; Avdija 4.1 / 3.8 -> 4.2 / 5.0 -> 6.1;
Harden 3.6 / 3.4 -> 4.2 / 4.2 -> 5.2; Dončić 4.0 / 3.1 -> 3.2 / 4.3 -> 5.1.

What it means:
- **Free throws:** both engines now order players' free throws better. Today's engine overshoots the league level a
  little (its free-throw response to the craft grade was tuned on the old, compressed grades); Stage 2 keeps the level
  and cuts its per-player misses. The under-shoot for the guards closes most of the way in today's engine; Stage 2
  still under-shoots them (Reaves 5.2 against 7.6), so part of that gap is in Stage 2's drive and pull-up foul terms.
- **Turnovers:** both engines order players better. Stage 2's level rises because the grades now spread wider and its
  turnover curve is steep for low grades; its high-usage stars were already 30-70% too high before this change and the
  evidence says their cards should be only 8-23% worse than average. Re-centring and flattening Stage 2's turnover
  response (involvement terms) is engine work, not a ratings question (rule 1).

**Betting test** (today's engine, 20 runs a game, 1,231 games, 1,018 with market odds; baseline = the same runs on
the committed inputs, from the rating-ceiling and Stage 2 reports):

| | Seed 1001 before | after | Seed 2001 before | after |
|---|---:|---:|---:|---:|
| Brier (market .1962) | .2041 | .204 | .1972 | .1972 |
| Log loss (market .5740) | .5975 | .598 | .5808 | .5813 |
| Spread miss vs market (points) | 4.10 | 4.16 | 3.92 | 4.00 |
| Total miss vs market (points) | 5.51 | 5.61 | 5.55 | 5.62 |

Picking winners is unchanged (within rounding). Spreads and totals are 0.06-0.10 points further from the market,
consistent with today's engine now producing about one more free throw per 100 possessions (section above).

**Tests** (full suite, `scripts/run_tests_parallel.py --all --workers 2`, rebuilt inputs in place): 2,391 tests,
3 failures, 19 errors. Sorted out by rerunning on the committed inputs:
- **Caused by this change (2), left for the coordinator, tests not edited:**
  1. `test_star_market_value`: Giannis is 10th in trade value (the test wants 8th or better). His handle security
     fell 60 -> 52 (his turnovers run 7% over expected at his load, balls lost 19% over), and Haliburton (ball
     security 80 -> 86) and Derrick White (74 -> 85) passed him; his value 88.3 -> 86.0, 0.3 behind 9th. Cade
     Cunningham also falls from 5th to outside the top 12 (foul drawing 60 -> 50, handle security 49 -> 41). The trade
     value formula leans on these two grades; whether the threshold or the formula should move is the value owner's
     call (rule 1: the grades follow the evidence).
  2. `test_stage2_totals_matchups.test_both_fives_set_the_pace`: compares the spread of possessions over 20 games with
     the pace weights doubled vs zeroed. With the new inputs, seeds 1-2 give 4.7 vs 8.8; on other seeds the order
     flips back and forth (3-4: 4.7 vs 2.7; 5-6: 4.8 vs 4.8; 7-8: 5.6 vs 3.2; seeds 1-12 together: 5.1 vs 5.2). The
     test is dominated by game-to-game noise; it needs more games or seeds (Stage 2 owns it).
- **Already failing on the committed inputs (1):** `test_neutral_coordinators.test_identity_and_personality_stay`.
- **Worktree environment (19 errors):** missing git-ignored reference files under `output/` (experimental-engine
  reference runs), missing GUI video assets for packaging tests, and a `teams` lookup in season slides that needs a
  file not linked into the worktree. None touch these inputs.
- New tests: `tests/test_foul_security_evidence.py` (7) and `tests/test_bbi_evidence.py` pass.

## 7. Rebuild command (for the coordinator, after merging this and ROOKIE-FIT)

```
PYTHONPATH=src .venv/bin/python scripts/build_player_inputs.py
```
It needs the git-ignored Basketball Index cache (`data/research/bbi/normalized.json` and `values_recent.json.gz`).
Expected effect: only foul drawing, handle security and contact seeking change (checked: 568, 567 and 496 players;
every other input is byte-identical to the committed file). `data/canonical/tendency_scale_map.json` is rewritten
unchanged. The command also refreshes the generated tables in `docs/agents/tasks/e2-input-estimator.md`.

## 8. Open questions for the coordinator
1. Stage 2 turnovers for high-usage creators (Brown 6.5 vs 3.8, Avdija 6.1 vs 4.1): an engine-side fit of the
   involvement and persistence terms against real turnovers per chance; the cards are now evidence-based.
2. Today's engine free-throw level (24.7 vs 22.9 per 100): its craft coefficient was fitted on the narrower old grades.
3. Contact seeking still cannot be separated from foul-drawing skill with the data we have (free throws per 75 mixes
   both with usage). It is no longer squeezed to the middle, but it deserves its own evidence pass.
4. Bad-pass turnovers have no home in the passing inputs; they ride in handle security for now.
5. Trade value: Giannis 8th -> 10th and Cunningham 5th -> outside the top 12 (section 6); the star-market test
   threshold or the value formula's weight on these two grades needs a decision.
6. Noted, not mine: the effort-allocation tendency uses "Movement Distance Rating", which is zero for 96% of players.

## Resume state (done)
- [x] Worktree symlinks, inputs unzipped; traced the current method.
- [x] Research script `scripts/research/ft_tov_evidence.py` (validate / compare); outputs in `output/ratings-ft-tov/`
      (validation.json, compare.json, scorecard logs, odds logs, before.json and after/ inputs).
- [x] Variants checked for handle security on the held-out season (rank correlation with turnovers per chance /
      balls lost / raw rate, card-plus-chances miss): balls lost only .58/.67/.47/.0164; all turnovers only
      .70/.50/.55/.0143; balls lost 1 + all 0.5 .66/.65/.52/.0155; **all 1 + balls lost 0.5 .70/.59/.55/.0147 (chosen)**;
      balls lost 1 + all 0.5 without the usage factor .69/.66/.57/.0151; all turnovers only without it
      .72/.52/.58/.0145.
- [x] Module, build wiring, mapping v6, overlay guard, tests (`tests/test_foul_security_evidence.py`, 7 tests).
- [x] Local rebuild, scorecards, odds runs, core tests, report, board row, commit on the branch.
