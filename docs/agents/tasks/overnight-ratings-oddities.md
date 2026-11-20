# OVERNIGHT-RATINGS: the rating oddities flagged by the last four reports

Owner: Claude (Opus agent), worktree branch, pushed as `overnight/ratings-oddities`. Status: **review**. Rules 1, 2, 3, 4,
7 and 9 apply. No number was typed by hand: every change goes through `scripts/build_player_inputs.py` and the evidence
modules.

## TL;DR

1. The defensive-rebound positioning rating was built mostly from a Basketball Index number that is measured against a
   position baseline, so it ranked the best rebounding centres (Jokić, Gobert, Zubac) near the bottom and the Thompson
   twins near the top. It now leads with Basketball Index's overall defensive rebounding grade, for everyone.
2. The strength rating no longer punishes long arms: combine bench-press reps are adjusted for wingspan (measured on the
   league's own tested players, kept modest by a physics check). Kawhi Leonard also gets the hosts' "physicality" claim.
3. Kennard and Robinson are not a pipeline problem: last season was their best shooting season, and older seasons
   predict next season better, not worse. Simulated rebounds got clearly closer to real ones; everything else held.

## Resume state (done)

- [x] Worktree symlinks, baseline rebuild (byte-identical to the committed inputs), baseline scorecards.
- [x] Shooting recency study; rebounding diagnosis; bench-press study; league outlier scan.
- [x] Mapping change, arm-length adjustment, one attributed analyst claim, rebuild, rebound refit, scorecards, tests.
- Local working files (git-ignored): `output/overnight-ratings/` (inputs before, calibration and odds before/after,
  fit output, who-moved lists `diff1.txt` / `diff2.txt`). Analysis scripts were scratch only; their method and numbers
  are below.

## 1. Kennard and Robinson shooting (oddity 1): sample skew, no pipeline change

**What the game uses.** A player's starting shooting percentages come from his shooting profile, frozen when the
universe is built (`offense.build_priors`, called from `ingest.py`): the last two seasons, the latest at full weight and
the one before at half, plus a 60-attempt pull toward the league average (35% from three, 54% inside). The input grades
only move these percentages as the player develops.

**The two players.** Luke Kennard shot .478 from three and .601 inside in 2025-26, his best seasons on both (2024-25:
.433 / .547; career about .44 from three). Duncan Robinson shot .410 / .605 (2024-25: .393 / .556; his inside .605 is a
career best by far). The profile sits between, so the replay (which scores against 2025-26 itself) has them below their
real true shooting.

**Is there a general recency problem?** Tested on every current player's career (ESPN, 2015-16 on): predict each
season from the seasons before it, compare with what happened (attempt-weighted squared error, 1,250 player-seasons
for threes, 1,440 for twos, 1,190 for free throws).

| Shooting | Current profile | Last season only (best pull) | Best tested weights |
|---|---:|---:|---:|
| Threes | 13.95 | 13.34 | **12.33**: last three seasons at 1 / 0.7 / 0.6, pull of 300 attempts |
| Twos | 16.43 | 18.00 | **15.97**: 1 / 0.6 / 0.4, pull of 100 attempts |
| Free throws | 22.76 | 26.91 | **21.62**: 1 / 1 / 0.5, pull of 30 attempts |

The answer is the opposite of a recency problem: next season is predicted better with *more* older seasons and *more*
pull toward a baseline. A player-specific baseline (from his free-throw shooting and three-point volume) helps threes
further (12.15 vs 12.75 for the flat league average, on held-out seasons 2023-24 to 2025-26); for twos the flat
baseline was better.

**Decision.** Kind: **sample skew** (one hot season). Nothing changed. Moving toward 2025-26 would chase the season the
replay scores against and make the 2026-27 forecast worse. For the profile owner: a three-season, more-regressed
profile would forecast next season about 11% better for threes, but it lives in ingest-time engine code
(`offense.build_priors`) and needs a universe rebuild, and it would widen the replay gap for hot shooters, so it is a
recommendation, not done here.

Per-36 rates other than shooting, by age (same method, 2021-22 to 2025-26): the inputs' season weights (1 / 0.6 /
0.35) are within 1-3% of the best weights for every stat and age group, except young players' assists and turnovers
(23 and under: last season alone is best, current weights 12% / 5% worse). Those follow role growth (involvement and
pass choices, which are measured habits), not skill; young players' steals are 3% off (Ausar Thompson and Cason Wallace
steal more than the game gives them). Not changed: the gain for skills is small.

## 2. Jokić's defensive-rebound positioning 41.7 (oddity 2): measurement problem, fixed for everyone

**Cause.** The positioning grade took Basketball Index's "defensive rebounding crashing skill" as its main measure. That
number is chances won *beyond what the player's spot on the floor gives him*: it is measured against a position
baseline. Across players with 1,000+ minutes it has no link to actual defensive rebounding (rank correlation with
defensive rebounds per 75: -0.10 in 2024-25, +0.01 in 2025-26), runs against height (-0.37), and averages -1.3 for
centres and +0.3 for guards. (The offensive version does track rebounds, +0.44 to +0.48, and stays as it is.)
Jokić is 3rd-7th percentile on it every season while 94th-97th on Basketball Index's overall defensive rebounding grade,
95th-97th in chances, and 96th in contested rebounds won. The same number put Gobert at 9th-13th, Zubac 7th-9th, and
the Thompsons at 91st-99th.

**Fix** (`data/research/bbi/bbi_input_mapping.json`, now v4). The overall defensive rebounding grade ("talent": chances
created plus conversion; rank correlation 0.84-0.87 with defensive rebounds per 75) is the main measure; crashing skill
stays only as a weak nudge, with the reason written into the mapping. Rebound control keeps its own conversion measures.

**Who moved (league percentile among rotation players, before -> after):** Jokić 41.7 -> 79.9 (32nd -> 95th),
Wembanyama 49 -> 84 (47th -> 98th), Adebayo 37 -> 72 (24th -> 87th), Zubac 47 -> 74 (42nd -> 89th), Robert Williams
(39th -> 89th), Vučević (28th -> 81st), Valančiūnas (28th -> 80th), Okongwu (31st -> 78th), Gobert 43 -> 68 (35th ->
78th), Claxton 57 -> 73 (63rd -> 88th). Down: small guards who leak out (Davion Mitchell 44th -> 16th, Tyus Jones
36th -> 14th, Malik Monk, Nickeil Alexander-Walker, Reed Sheppard), Amen Thompson 98th -> 93rd, Ausar 97th -> 90th.
566 players changed; nothing else in the inputs moved.

**Engine consequence (separate commit, one constant in `box_rates.py`).** The rebound share formula was fitted to the
old grade. With the old weights the corrected grade would over-reward bigs, so the formula was refitted with the
existing script (`scripts/fit_box_stat_rates.py`, same inputs, same method): positioning weight 0.0047 -> 0.0072 per
point, box-out 0.0095 -> 0.0061, control 0.0046 -> 0.0024, the pursue habit 0.08 -> -0.02 (about nothing), height a
little less. Out-of-fold correlation with real 2025-26 rebounds per 36: 0.94 -> **0.951**. This file belongs to the
box-score owner, so it is its own commit (`Rebound weights refit ...`): drop it if they refit rebounds themselves, but
then refit, because the new grade with the old weights over-feeds centres.

## 3. Amen and Ausar Thompson (oddity 3): partly measurement (fixed), partly a role change

Their 96th-98th percentile positioning came from the crashing number above (they are the league's best at flying in
from the perimeter). Now 93rd / 90th, from the overall grade. Simulated rebounds per 36: Amen 9.78 -> 9.52 (real 7.48),
Ausar 9.26 -> 8.71 (real 7.93).

What is left is a role change, not a rating error: Amen's rebounds per 36 went 10.6 -> 9.1 -> 7.5 over three seasons as
Houston moved him on the ball, Ausar's 9.2 -> 8.2 -> 7.9. Their per-chance skills (conversion 87th-97th percentile)
did not fall; their chances did (Amen 71st -> 51st percentile). For players 23 and under, older seasons still help
predict next season's rebounding (best weights 1 / 1 / 0.2), so chasing 2025-26 would worsen the 2026-27 forecast.
Kind: **context** (deployment). No further change.

## 4. Nic Claxton (oddity 4): context, no rating change

Simulated 10.59 -> 10.74 per 36 (real 8.97). His rebounds per 36 fell 12.0 -> 9.9 -> 9.0 over three seasons while his
per-chance numbers held; his chances per 75 fell from 96th to 76th percentile. His positioning rose with the corrected
measure (63rd -> 88th), which is what Basketball Index's own grade says over three seasons. Kind: **context**
(deployment and Brooklyn's 2025-26 roster). The engine part was fixed in the last task. No change; flagged for the
next season's data.

## 5. Strength from the bench press (oddity 5): measurement problem, fixed for everyone

**Evidence.** The combine bench is reps to failure at 185 lb. A longer arm moves the bar further every rep. Among the 74
tested players in the league, at the same body mass, log reps fall with log wingspan at an elasticity of **-7.4**
(standard error 3.0); once wingspan is in, height adds nothing (-0.3, se 3.6). Work per rep alone (bar travel
proportional to arm length) gives -1, the smallest effect physics allows.

**Fix** (`physical_evidence.arm_length_adjusted_reps`). The fitted elasticity is blended with the physics value by
precision (a deliberately wide physics prior, standard deviation 3), giving **-4.2**; each tested player's reps are moved
to the tested players' average wingspan (208 cm) before the age adjustment. Body mass keeps its effect (more muscle is
real strength). After the adjustment, the size model's wingspan weight falls from -1.6 to 0.0: the arm penalty is gone.
Only the 74 players with a combine bench move (plus three untested players by under a point, through the analyst
step's league scale: Brandon Miller, Kevin Durant, Dylan Harper); untested players keep their estimate.

**Who moved (grade, rotation percentile):** up: Gobert 45 -> 61 (9th -> 91st), Thomas Bryant 49 -> 63, Vučević 52 -> 61,
Andre Drummond 63 -> 74, Brook Lopez 44 -> 51 (7th -> 48th), Jarrett Allen 38 -> 46 (4th -> 14th), Jaxson Hayes,
Daniel Gafford. Down (short arms helped them): Jevon Carter 69 -> 52 (97th -> 54th), CJ McCollum 62 -> 53, Donte
DiVincenzo 67 -> 56, Kyle Kuzma 63 -> 55, Kenrich Williams, Svi Mykhailiuk, Jalen Brunson 42 -> 34. Khris Middleton
barely moves (37 -> 38): his arms are not long for his height; the low score is his reps.

**Kawhi Leonard (genuine disagreement, attributed evidence added).** Even arm-adjusted, his 3 reps at 19 (2011, fifteen
years and a full NBA career ago) only reach 40. Both Nerd Sesh hosts cite his "physicality / bully-ball inside the arc"
(Top 10 small forwards, 2026-08-19, 01:30:18-01:35:48; already in the claims file for finishing and foul drawing). The
same claim is now also recorded for strength (`ns179p` in `data/research/analyst_claims_2026.json`, level "strong",
paraphrased, with the reason in its notes) and goes through the normal analyst step: 37.8 -> **50.5** (4th -> 42nd
percentile). Jump and strength stay off the box score as before (no extra effect beyond the skills), so neither
scorecard reads them.

## 6. Other large outliers (oddity 6): sorted by kind

From the replay calibration's per-player output (150 heaviest-minute players) and a fit-versus-real scan of all 377
rotation players.

| Outlier | Real vs simulated | Cause | Kind | Action |
|---|---|---|---|---|
| Wembanyama, Clingan, Diabaté, Ware, Adebayo rebounds (under) | Wemby 14.2 vs 10.2 | Same crashing-skill problem (Wemby was 47th percentile in positioning) | measurement | **Fixed** with section 2: Wemby 10.2 -> 11.2, Diabaté 9.6 -> 10.8, Clingan 12.1 -> 12.8, Ware 12.6 -> 13.1 |
| Brook Lopez, Myles Turner blocks (over) | Lopez 1.9 vs 3.3 | Steady decline with age (Lopez 2.9 -> 2.8 -> 2.1 -> 1.9 per 36; Turner 2.8 -> 2.2); the three-season blend sits above the last season | sample / aging | None; the game's aging curve applies from here |
| Deni Avdija free throws (under) | 10.0 vs 6.4 | Real jump every season (2.9 -> 4.4 -> 6.2 -> 10.0 per 36); a fast improver lags any multi-season blend | genuine change, sample | None; the young-player recency result above says the gain from heavier recency is small overall |
| Ausar Thompson, Cason Wallace steals (under) | Ausar 2.8 vs 1.9 | Both rose each season (Ausar 1.6 -> 2.7 -> 2.8) | same | None (young players' steals: 3% better with more recency) |
| Draymond Green, Giddey, Dončić, Westbrook, Carrington turnovers (under) | Draymond 3.5 vs 2.2 | The turnover formula's weights date from before ball security became "per play used or created" (analyst-first). Fit with stored weights: spread 0.52 vs real 0.77; residual rises with assists (r 0.39) | stale fit (engine) | **Not changed.** Refit tried: league turnovers 13.2 -> 13.7 per 100 (target 14.1) but per-player miss unchanged (0.327 -> 0.329) and Draymond worse; it is box-score code with no per-player gain, so left to the box-score owner with the numbers |

## 7. Scorecards

**Real-stat targets** (`calibration_report.py --games 1230 --mode replay-real-minutes`, seed 1): **18/18 before and
after.** Player per-36 errors (150 players, sim minus real; mean miss in brackets):

| Stat | Before | After |
|---|---:|---:|
| Rebounds | -0.048 (0.677) | **-0.006 (0.563)** |
| Points | -0.415 (1.172) | -0.416 (1.176) |
| Shots | -0.378 (0.890) | -0.384 (0.897) |
| Threes attempted | -0.083 (0.282) | -0.083 (0.283) |
| Free throws attempted | -0.062 (0.606) | -0.060 (0.605) |
| Assists | +0.053 (0.461) | +0.052 (0.461) |
| Turnovers | -0.054 (0.327) | -0.054 (0.327) |
| Steals | -0.029 (0.180) | -0.028 (0.179) |
| Blocks | +0.007 (0.190) | +0.008 (0.190) |
| True shooting | +0.002 (0.022) | +0.002 (0.022) |

**Betting odds** (`validate-season-probabilities --runs 20 --seed 1`, 1,231 games, 1,018 with market odds):

| | Brier | Log loss | Spread error | Totals error |
|---|---:|---:|---:|---:|
| Before | 0.2009 | 0.5911 | 5.342 | 5.916 |
| After | 0.2009 | 0.5911 | 5.332 | 5.909 |
| Market | 0.1962 | 0.5740 | | |

Win accuracy is unchanged to four decimals and the spread and totals errors are a hair better: the changed inputs
mainly decide who gets the rebounds, not who wins (strength feeds development and the card, not the box score).
20 runs per game is a short check; the 100-run main baseline is Brier 0.1959.

**Tests:** core suite (`scripts/run_core_tests.sh`) 337 OK (2 skipped); input estimator, player profile, Basketball
Index evidence, analyst evidence, unused-ratings 2, win-pick/shooters and the new overnight tests: 122 OK (2 skipped).
Full suite not run (no save or game-flow code changed).

## Files

- `data/research/bbi/bbi_input_mapping.json` (v4: defensive-rebound positioning), `src/nba_gm_data/physical_evidence.py`
  (arm-length adjustment), `data/research/analyst_claims_2026.json` (one claim), rebuilt
  `data/canonical/player_inputs_2026_27.json.gz` and the generated tables in `docs/agents/tasks/e2-input-estimator.md`.
- `src/nba_gm_data/box_rates.py`: rebound weights only (separate commit; box-score owner's file).
- Tests: `tests/test_overnight_ratings.py` (new: arm-length adjustment, rebound weights), `tests/test_bbi_evidence.py`
  (positioning mapping).
