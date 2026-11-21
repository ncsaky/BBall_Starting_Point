# S2-SEAM-SHOOTING (Stage 2, first piece): report

_Owner: Claude (Opus agent), branch `worktree-agent-af77db31e56e7d239`. 2026-11-21. Light job (no season sims). Status: **review**._

## TL;DR
- The game sim now has an engine switch. Today's engine is the default and plays identically. A Stage 2 placeholder runs through both scorecards end to end. All 691 players' 94 inputs now compile into the physics pieces (shooting, finishing, rim defense), cached; none fail.
- As built, the shooting kernel ranks shooters well, but it is about 6 points too cold on threes and at the rim and 16 points too hot on floaters. League effective FG% comes out 49.0% against a real 54.5%.
- Refitting only the kernel's conversion numbers (one floor and slope per shot family, checked on players the fit never saw) brings every shot type to within about 1 point of real. Threes then match within sampling noise. No player rating was touched.

## 1. The seam
- `sim_game_with_context(..., engine="current" | "stage2")` (`sim.py`). `DEFAULT_ENGINE = "current"`.
  - The branch sits at the existing experimental branch point, after tonight's player pools are built. The Stage 2 engine therefore receives the game, both teams and both pools.
  - An unknown engine raises an error.
- Threaded through both scorecards:
  - `scripts/calibration_report.py --engine`;
  - `validate_game_probabilities[_with_context](engine=)`, `validate_season_probabilities(engine=)`, and the CLI `validate-game-probabilities --engine` and `validate-season-probabilities --engine`.
  - Reports now carry `"engine"`.
- The stub is `src/nba_gm_data/stage2/engine.py`. It runs today's engine on the same game and adds "Stage 2 engine stub" to the notes.
- **Proof that the default is unchanged:**
  - 40 seeded games (10 games × both modes × seeds 1 and 7) hashed before and after the change: identical (`3a3695e2…`).
  - Default and explicit `"current"` give the same hash.
  - The stub equals today's engine field for field (notes aside) on 20 more games.
- **Both scorecards run through the stub:**
  - Calibration report, 150 games: JSON byte-identical between engines. 18/18 league metrics in band, effective FG% .541 vs .546.
  - Betting test (`--runs 5 --limit 200`, nice): Brier .2030 and log loss .5872 on both engines.
- **Normal gameplay never selects it.** Saves, play and the app never pass `engine`, and a test checks this.
- **One packaging note for the coordinator:** `pyproject.toml` lists `packages = ["nba_gm_data"]`, so an installed build would not include `nba_gm_data.stage2`. Gameplay never imports it, but add it to the package list (or switch to package discovery) before anyone runs `--engine stage2` from an installed build. I left `pyproject.toml` alone because it is outside this task's files.

## 2. League input bridge (`src/nba_gm_data/stage2/league_inputs.py`)
- **Coverage:** **691 of 691 players compile** for offense (`offense_response.compile_offense`) and for rim defense (`interior_defense.compile_profile`), with 0 errors. Both go through the shared reader (`experimental_inputs.InterpretedInputs`).
- **Speed:**
  - The full league compiles in about 6 s once.
  - The cached load (`output/stage2/league_profiles.json`, keyed by the inputs file, the bridge version and the kernel versions) takes 0.05 s.
  - Rebuilding all 691 kernel profiles takes 1.5 ms.
- **The one rule for non-evidence cells** (documented in the module):
  - *Prior* cells (the estimator's position, role and body prior for that player) are used at their stored value. Their uncertainty interval is kept beside the value.
  - *Unknown* cells get the median of the player's position group (guard, wing or big) for that input. Their uncertainty is the group's 10th-90th percentile range, with reason "prior", confidence "low", and provenance naming the rule.
  - There are no unknown cells in today's file. A test plants two and checks the rule.
  - Values are never moved.
- **Unit conversion.** The rim-defense piece needs acceleration in m/s². The league file has only a grade for it. The bridge takes the player's league rank on that grade, finds the same rank in the 2000-2025 combine three-quarter-court sprint times, and converts with a = 2d/t². This is stored under its own explicit label; values run from 3.2 to 5.4 m/s², with a median of 4.3.
- **Small marked additions to `experimental_inputs.py`:**
  - It accepts the league file's scale and protocol labels as the same named quantities.
  - Its technique index is grade/100, the same rule as the native index.
  - Its four shot regions map onto the kernel's three: short paint plus midrange becomes the kernel's short-paint zone.
  - It accepts the league's shot-mode condition.
  - Existing experiment paths are unchanged, and their tests pass.
- **Data finding:** 517 of 691 player documents fail the player model's own validator. Their choice mixes add up to 1 ± 0.000001, a rounding effect of 6-decimal storage. The bridge puts the leftover on the largest choice, only up to 0.00001; larger gaps still fail. **Suggested fix at the source:** re-normalise after rounding in `input_estimator`.
- **How much of what the kernels read is prior (share of 691 players):**

  | Skill or input | Prior share | What it covers |
  |---|---|---|
  | Three-point shooting (catch, pull-up, movement) | 21-23% | |
  | Free throws | 22% | |
  | Layup touch | 24% | |
  | Floater | 45% | |
  | Dunk | 44% | |
  | **Midrange catch and movement** | **93%** | (midrange pull-up 52%) |
  | Release speed | 99.7% | |
  | Lob finishing | 100% | |
  | Catching | 99.7% | |
  | Contact finishing | 92% | |
  | Standing reach | 100% | |
  | Balance | 100% | |
  | Strength | 89% | |
  | Vertical | 57% | |
  | Shot-region habit | 21% | |
  | Shot-mode habit | 32% | |
  | Rim contest choice | 93% | |

  League-wide, by family:

  | Family | Prior share |
  |---|---|
  | Skills | 62% |
  | Physical | 73% |
  | Tendencies | 38% |
  | Passing | 58% |

## 3. Shooting and finishing spot-check
`src/nba_gm_data/stage2/shooting_check.py`; driver `scripts/research/s2_shooting_spot_check.py`, which takes about 50 s and runs no game sims. The full output is in `output/stage2/shooting_check.json`.

**Real data available and used:**
- Basketball Index Leaderboards, 2025-26 values (local capture):
  - make rates: rim, short mid, long mid, corner 3, above-the-break 3, catch-and-shoot 3, pull-up 3, midrange pull-up, floater;
  - attempt rates per 75 possessions: rim, midrange, 3, pull-up 3, midrange pull-up;
  - the corner-to-above-the-break ratio;
  - openness ratings per shot type.
- Basketball-Reference shooting: 0-3 ft attempts and dunk share, corner-3 share and percentage, 2024-2026.
- ESPN season totals (two-point, three-point and free-throw makes and attempts).
- The targets file: league effective FG% .5456 and three-point attempt rate .4151.

**Not available:**
- shot-level tracking or defender distance per shot (only openness ratings);
- floater attempt counts (weighted by short-mid attempts instead);
- the short-mid versus long-mid attempt split (solved from midrange makes, or the player's observed shot-region split when that solve is unreliable);
- off-movement shooting percentages.

**How it was run:**
- 376 rotation players (500+ minutes), weighted by attempts.
- The kernel runs at its own reference defense: perimeter pressure .35, defender arrival .65 s, finishes uncontested.
- Each player's shot context comes from his real shot selection: corner/above-the-break split, pull-up shares, and dunk share at the rim.
- "Error beyond noise" is the root-mean-square error after removing the sampling noise in the real percentage. 0.0 means the remaining differences are indistinguishable from luck.
- Today's engine resolves only 2P/3P/FT per player. Its numbers come from the engine's own player features.

### Kernel as built vs today's engine vs real (all 376 players)

| Shot type | Attempts | Real | Kernel | Kernel bias | Kernel error beyond noise | Kernel corr | Today | Today bias | Today error beyond noise | Today corr |
|---|---|---|---|---|---|---|---|---|---|---|
| Rim (under 4 ft) | 59,501 | 67.4 | 61.4 | -6.0 | 6.8 | .76 | — | | | |
| Short mid (4-14 ft) | 43,988 | 44.8 | 49.2 | +4.3 | 5.3 | .62 | — | | | |
| Long mid (14 ft to arc) | 20,516 | 41.7 | 36.2 | -5.5 | 6.1 | .52 | — | | | |
| Corner 3 | 11,116 | 40.1 | 30.8 | -9.3 | 7.2 | .62 | — | | | |
| Above-the-break 3 | 76,414 | 35.0 | 28.8 | -6.2 | 7.1 | .70 | — | | | |
| Catch-and-shoot 3 | 63,680 | 37.3 | 29.0 | -8.3 | 8.6 | .79 | — | | | |
| Pull-up 3 | 23,847 | 33.1 | 29.2 | -3.9 | 4.1 | .64 | — | | | |
| Midrange pull-up | 30,050 | 43.3 | 38.5 | -4.8 | 5.3 | .67 | — | | | |
| Floater | 43,988 | 44.3 | 60.4 | +16.1 | 18.2 | .61 | — | | | |
| All twos | 121,158 | 55.1 | 52.9 | -2.2 | 2.9 | .83 | 54.6 | -0.5 | 0.0 | .95 |
| All threes | 85,138 | 36.1 | 29.0 | -7.1 | 7.6 | .79 | 36.2 | +0.0 | 0.0 | .92 |
| Free throws | 54,660 | 78.5 | 78.1 | -0.4 | 0.5 | .94 | 78.1 | -0.3 | 0.0 | .97 |
| Effective FG% | 206,296 | 54.7 | 49.0 | -5.7 | 6.5 | .78 | — | | | |

### The prototype fix, on the held-out half (188 players the refit never saw)

| Shot type | Real | Kernel as built (error beyond noise) | Kernel refit (error beyond noise) | Today (error beyond noise) |
|---|---|---|---|---|
| Rim | 67.2 | 61.1 (6.7) | 67.5 (0.8) | — |
| Short mid | 44.5 | 49.1 (5.6) | 44.2 (2.8) | — |
| Long mid | 42.2 | 36.4 (6.5) | 43.1 (2.7) | — |
| Corner 3 | 40.8 | 30.9 (7.7) | 37.7 (0.0) | — |
| Above-the-break 3 | 35.0 | 28.8 (7.1) | 35.4 (1.0) | — |
| Catch-and-shoot 3 | 37.3 | 29.0 (8.6) | 37.0 (0.0) | — |
| Pull-up 3 | 33.4 | 29.3 (4.2) | 32.3 (0.0) | — |
| Midrange pull-up | 43.3 | 38.7 (5.4) | 43.4 (2.9) | — |
| Floater | 43.8 | 60.2 (18.5) | 44.8 (8.7) | — |
| All twos | 54.5 | 52.3 (3.1) | 54.7 (1.7) | 54.2 (0.0) |
| All threes | 36.2 | 29.1 (7.6) | 35.7 (0.0) | 36.2 (0.0) |
| Free throws | 78.7 | 78.1 (0.7) | 78.1 (0.7) | 78.2 (0.0) |
| Effective FG% | 54.4 | 48.9 (6.4) | 54.2 (1.6) | — |

### League level (rotation players, real attempts)

| | Real | Kernel's shot-region inputs | Today's engine (150-game calibration run) | Targets file |
|---|---|---|---|---|
| Rim / short mid / long mid / three | 28.1 / 20.8 / 9.7 / 41.4% | 27.6 / 17.5 / 13.9 / 41.0% | — | three-point attempt rate 41.5% |
| Effective FG% | 54.5% | **49.0%** as built, **54.6%** refit | 54.1% | 54.6% |

The inputs put about 4 points of shots in long mid that real data has in short mid. The short/long split of real attempts is inferred, so treat that as approximate.

### Reading today's engine fairly
Today's engine does not predict shooting from ratings. It reads each player's actual 2025-26 box-score percentages, plus half of 2024-25, lightly shrunk (`offense.build_priors`). On this same season it is a lookup, so its per-player 2P/3P/FT error is pure sampling noise by construction. It also cannot tell a corner three from a pull-up or a floater from a dunk.

The 94-input skills are built from the same seasons' data, so both sides are in sample. A truly fair judgement needs 2026-27 games, or a ratings rebuild that holds out 2025-26.

Within that, the refit kernel matches today's per-player accuracy on threes and free throws (both indistinguishable from noise). It is 1.4 points beyond noise on twos. It adds the shot-type detail.

### 20 biggest kernel misses each way (as built; season field-goal points on his real attempts; kernel/real % by zone)
Over-predicted:
1. Zion Williamson +63 (short mid 53.9/40.1)
2. Jalen Brunson +59 (short mid 59.5/47.3)
3. Brandon Ingram +28
4. Nick Richards +24
5. Daniel Gafford +23
6. Luka Dončić +21 (rim 67.2/81.5, short 59.4/52.4)
7. Amen Thompson +21
8. Norman Powell +14
9. Lauri Markkanen +14
10. Jonathan Isaac +10
11. Ivica Zubac +10
12. Ja Morant +7
13. Jaxson Hayes +6
14. Stephen Curry +3
15. Brandon Miller +3
16. Anthony Davis +2
17. Karl-Anthony Towns 0
18. Tyus Jones 0
19. Moussa Cisse 0
20. Cam Thomas -2

All 20 come from floaters that are too easy, plus a few dunkers.

Under-predicted:
1. Russell Westbrook -272 (above-the-break 3 16.9/32.8, rim 51.8/65.1)
2. Toumani Camara -259 (above-the-break 25.4/39.1)
3. Deni Avdija -236
4. Jalen Johnson -172
5. Matas Buzelis -168
6. Scottie Barnes -164
7. Jeremiah Fears -163
8. Wendell Carter Jr. -163
9. Bam Adebayo -162
10. Draymond Green -159 (rim 47.7/70.0)
11. Onyeka Okongwu -157
12. Alperen Şengün -155
13. Andrew Nembhard -154
14. Ayo Dosunmu -153
15. Jay Huff -152
16. Kevin Huerter -150
17. RJ Barrett -148
18. Saddiq Bey -147
19. Paolo Banchero -144
20. Josh Hart -143

All 20 are weaker or average shooters, whom the kernel's steep line sends down to 15-25% from three.

After the refit:
- **Biggest remaining over-predictions:** Zion +112 (rim and short mid), Ingram +106, Brunson +101, Towns +98 (long mid 44/29), D. White +88, LaMelo Ball +81, Siakam +77, A. Thompson +70, Markkanen +70, Porter Jr. +61, N. Powell +59, B. Miller +58, DiVincenzo +56, Naz Reid +55, Maxey +53, Wembanyama +53, Alexander-Walker +52, G. Allen +51, Randle +51, LeBron +50.
- **Biggest remaining under-predictions:** Westbrook -112, **Ayton -103 (short mid 41.7/54.8)**, **Raynaud -98 (44.2/54.5)**, Camara -79, Kennard -66 (mid 46/56), Hachimura -63, Garza -63, Şengün -62, Nembhard -61, Carrington -60, D. Mitchell -58, **Queta -55 (38.0/50.7)**, Nurkić -52, C. Spencer -52, Dosunmu -52, Collier -52, K. Dunn -49, Avdija -47, J. Hart -46, Landale -46.

The full tables, with per-zone numbers, are in `output/stage2/shooting_check.json` (`misses`, `misses_refit`).

## 4. Timing
Microseconds per call on all 691 profiles, best of 3, on a busy laptop:

| Call | Time |
|---|---|
| One jumper (`shooting_response`) | 1.8 µs |
| One finish | 1.0 µs |
| One shot resolved (zone pick + make probability) | 2.2 µs |
| Rim contest (`interior_response`), with or without shot geometry | 4.5-4.7 µs |

A shot plus a rim contest costs about 0.005-0.007 ms per possession, roughly 2-3% of the 0.2-0.4 ms budget. Shooting and finishing are not a speed risk. In the earlier experiments the expense came from pass recovery and route evaluation, not from these kernels.

## 5. What the kernel gets right and wrong; proposed fixes
**Right:**
- It ranks players sensibly. Correlation with real is .76 at the rim, .79 on catch-and-shoot threes, .70 above the break, and .94 on free throws.
- Corner threes come out easier than above-the-break threes.
- Free throws are exact (the input is the free-throw percentage itself).
- It is fast.

**Wrong** (kernel-level; no rating was changed):
1. **One conversion line for every jumper, too steep and too low.** Shooting comes out at 0.12 + 0.36 × skill. Below-average shooters drop to 15-25% from three when real is about 31-34%. Predicted spread on threes is 6.6 points per player against a real 4.2.
   - **Fix (prototyped):** each shot family gets its own floor and slope, fitted by attempt-weighted least squares on half the players and checked on the other half.

   | Family | Refit conversion |
   |---|---|
   | Catch-and-shoot 3 | .27 + .21 × skill |
   | Pull-up 3 | .215 + .22 × skill (a pull-up is about 4 points harder) |
   | Catch-and-shoot 2 | .32 + .10 × skill |
   | Pull-up 2 | .14 + .385 × skill |

   Range cost per metre goes from .07 to .029. The mode skill, balance, range, release timing and contest structure all stay as they are.
2. **Floaters share the layup's floor and slope**, so a floater is as easy as a layup (60% vs real 44%).
   - **Fix:** a separate floater family (.17 + .49 × floater skill).
   - Layups go to .41 + .45 × layup skill.
3. **Dunk line too low** (.50 + .45 × dunk skill), and the kernel's own finish mix gives everyone 12.5% dunks. With that mix the rim comes out at 58.6% vs 67.4%.
   - **Fix:** dunks become .62 + .21 × dunk skill.
   - Stage 2 needs a dunk and lob selection rule built from reach, vertical and the finish habit. This check used each player's real dunk share as context.
4. **Contact-layup penalty fits to zero** on these data. That is because the check assumes one rim attempt in three is a contact finish. Leave contact to the foul piece rather than to make rates.
5. **No hook or post shot in the short-paint zone.** Bigs are under-predicted in short mid by 10-13 points: Ayton, Raynaud, Queta, Nurkić, Landale, Garza.
   - **Fix:** a post/hook finish from the post skills.
6. **Shot openness is missing.** At the kernel's fixed reference contest, the leftover error correlates with Basketball Index's openness ratings:
   - catch-and-shoot 3: +.50 as built, +.24 after the refit;
   - midrange pull-up: +.25;
   - floaters: +.28.

   Wide-open shooters (Westbrook, Draymond, Camara) beat their skill; tightly guarded ones (Curry, Ingram) fall short of it. This is the perimeter contest and closeout piece. It is the first missing mechanic on the roadmap list.
7. **Midrange shooting skills are 93% priors** (catch and movement), so long mid correlates only .52 even after the refit. This is a ratings-evidence gap, not a kernel defect.
   - Basketball Index has midrange shot-making metrics that are not mapped to these skills.
   - It needs its own ratings task with independent evidence. Nothing was changed here (rule 1).

The refit conversion lives in `shooting_check.refit_families` as a prototype. It is not yet wired into anything, and `offense_response.py` is unchanged, so experiment hashes stay stable.

## 6. Recommended next component
**S2-REBOUND-FOULS**, as planned. Rebounding is built new from the rebounding skills and the crash/box-out habits; fouls and free throws come with it. The first possession loop cannot run without them, and both have rich real targets (rebound chances, foul rates).

Fold two shooting follow-ups into the first possession-loop task:
- adopt the per-family conversion as Stage 2's shooting rule;
- add the hook/post finish.

Schedule the perimeter contest/openness piece right after, because it needs defensive matchups. Separately, queue a ratings-evidence task for the midrange skills.

## Files
- **Changed:**
  - `src/nba_gm_data/sim.py` (seam);
  - `src/nba_gm_data/cli.py` and `scripts/calibration_report.py` (flags);
  - `src/nba_gm_data/experimental_inputs.py` (marked league-bridge block).
- **New:**
  - `src/nba_gm_data/stage2/` (`engine.py`, `league_inputs.py`, `shooting_check.py`);
  - `scripts/research/s2_shooting_spot_check.py`;
  - `tests/test_stage2_seam.py`, `tests/test_stage2_league_inputs.py`.

## Checks
- New tests pass: `tests.test_stage2_seam`, `tests.test_stage2_league_inputs`, 15 tests.
- Core tests: see the result below.
- Focused parallel set: see the result below.

## Resume state
- [x] Seam + flags; [x] bridge; [x] spot-check; [x] tests; [x] report.
- Board row set to **review**.
