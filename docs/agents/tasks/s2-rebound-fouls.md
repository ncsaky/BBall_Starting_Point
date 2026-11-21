# S2-REBOUND-FOULS (Stage 2, second piece): report

_Owner: Claude (Opus agent), branch `worktree-agent-aad4424d8db3ab016`. 2026-11-21. Light job: no season simulations. Status: **review**._

## TL;DR
- Stage 2 now has a rebound kernel (who gets each miss among the ten players, from rebounding skills, reach, crash/box-out habits, floor spot and miss type) and a foul/free-throw kernel (shooting fouls, and-ones, non-shooting fouls, the bonus). Both are fast, about 6 and 2 microseconds per event.
- After refitting only the kernels' own conversion numbers, the league levels match real (offensive rebounds 26.0%, fouls 19.3 per 100, free throws 22.3 per 100). Per player, rebounding is about as good as today's engine, and it adds the offensive/defensive split today's engine lacks. Fouls and free throws per player are a bit worse than today's engine.
- The main weakness: free throws depend on how a shot is created (drive vs. roll or putback), which only the possession loop will know. Guards who live at the line are under-predicted; rim-running centers are over-predicted. Recommended next: the first fast possession loop, with action type passed to these kernels.

## What was built
**New modules** in `src/nba_gm_data/stage2/`. None are imported by normal gameplay, and a test checks this.
- **`rebounding.py`** (the rebound kernel). For each missed shot, each player gets a "pull" built from four things:
  - **Taking part:** crash vs. retreat (crash habit), and box-out vs. pursue on defense (box-out habit).
  - **Nearness:** how close he is to where the ball lands.
    - On offense, his working spot comes from his shot-region habit; the shooter stands where he shot.
    - On defense, he stands between his height-matched man and the rim.
    - Landing distance and spread depend on the miss type: rim, short, mid, three or free throw. Long misses from three land farther out.
  - **Ability:** offensive or defensive rebounding technique, rebound control and standing reach.
  - **Box-outs:** a seal on the crasher, decided by box-out technique and strength against his pursuit technique.

  The defense keeps an inside-position edge. Free-throw misses use fixed lane spots. Each player's chance of the rebound is his pull divided by everyone's.
- **`fouls.py`** (the foul kernel).
  - **Shooting-foul chance** comes from the shot zone plus:
    - the shooter's side: foul-drawing craft, contact seeking, contact finishing, strength and drive share;
    - the contesting defender's side: foul control, contest technique and how often he jumps at shots;
    - optionally, a rim-protector help defender.
  - **And-ones:** made shots that are fouled earn one free throw. Fouled misses earn two free throws (three on a three) and do not count as a field-goal attempt.
  - **Non-shooting fouls:** drawn by involvement, craft and contact seeking; committed by the matched defender (foul control, steal gambling). A share of them falls in the bonus and earns two free throws.
  - **Offensive and loose-ball fouls:** loose-ball fouls follow each player's share of rebounds.
  - **The bonus:** `bonus_share_from_rule` applies the NBA rule (bonus from the 5th team foul of a quarter, or the 2nd foul inside the last two minutes) at the league foul rate. That gives 0.274, which the kernel uses.
- **`game_contexts.py`** (data). It reads the 1,231 real 2025-26 regular-season box scores and draws 49,240 five-on-five lineups, with each player weighted by his real minutes that night.
  - Players without inputs fill 1.15% of minutes; they get the league-median profile.
  - Real per-player rebound percentages use the Basketball-Reference method. They match Crafted NBA's offensive rebound % at r = .996.
  - It also loads ESPN raw season totals for the held-out 2022-23 season.
- **`rebound_check.py` and `foul_check.py`:** scoring, refits, today's-engine numbers and timing.
- **Driver:** `scripts/research/s2_rebound_foul_spot_check.py` (about 30 s; `--refit` re-runs the fits, which take several minutes; `--replay N` runs today's engine on N real games). Output: `output/stage2/rebound_foul_check.json`.
- **Tests:** `tests/test_stage2_rebound_fouls.py` (15 tests).

## Real data used, and what's available
- **Box scores 2025-26** (`data/research/game_boxscores_2025_26.json`): per-player offensive and defensive rebounds, fouls, free-throw attempts and minutes, plus team totals.
  - Player field-goal attempts in this file are zero (a known parser bug), so FGA comes from ESPN season totals.
- **Targets file:** league offensive-rebound % 26.0, fouls 19.37 per 100, free throws 22.90 per 100, free-throw rate .2635. It also carries Crafted's per-player offensive and defensive rebound percentages.
- **Basketball Index tables** (`data/research/bbi`, values for 2023-24 to 2025-26).
  - Rebounding:
    - offensive and defensive rebounding chances per 75, rebounds per 75, adjusted success rates;
    - crashing, conversion and talent skills;
    - average rebound distance from the rim;
    - percentage of rebounds contested;
    - free-throw rebounds;
    - self-rebound percentage.
  - Fouls:
    - shooting, non-shooting-in-bonus, offensive, loose-ball and charge fouls committed and drawn per 75;
    - and-ones per 75;
    - 3PT foul rate;
    - drive foul drawn rate;
    - contact finish rate.
  - Used for: the foul composition (shooting 52%, offensive 6%, loose-ball 7%); the free-throw share of rebounds (5.3%); the three-point foul rate (1.1%); and a position check. The kernel's offensive spot correlates .58 with BBI's average offensive-rebound distance.
- **Held-out season:** `data/research/espn_career_raw/` 2022-23 totals (offensive and defensive rebounds, fouls, FGA, FTA). That is 276 players with 500+ minutes who are still in the league file.

**Being honest about "in sample":**
- The 94 inputs were built from 2023-24 to 2025-26 Basketball Index data plus Crafted 2025-26 stats. That includes the same rebound and foul rates, for example offensive rebound % feeds offensive rebound technique and the crash habit, and free-throw rate feeds contact seeking. So any 2025-26 per-player check is partly in sample.
- Today's engine is a direct fit to 2025-26 per-36 rates (`box_rates.REBOUNDS_INPUTS`, `FOULS_INPUTS`, `FTA_PER_POINT_INPUTS`). On 2025-26 it is in sample twice over. It is not a lookup of real rates, but close to one.
- Two fairer checks:
  1. Kernel refits are fitted on half the players (a fixed hash) and scored on the other half.
  2. Both engines predict **2022-23**, which is outside the inputs' evidence window. Some inputs carry a weak legacy-trait prior that may include older seasons. The kernels run in neutral lineups there, because 2022-23 lineups aren't in the repo, and levels are matched.

## Piece 1: rebounding
"Error" is the root-mean-square error after removing sampling noise. "Held" is the 202 players the refit never saw.

**Per-chance rates, 2025-26:**

| Rate | Real | Kernel as built: bias / error / corr | Kernel refit: bias / error / corr | Today's engine |
|---|---|---|---|---|
| Offensive rebound %, all 378 | 5.1 | -1.1 / 1.8 / .917 | +0.0 / 1.3 / .923 | no per-player split |
| Defensive rebound %, all 378 | 14.9 | +1.3 / 3.0 / .908 | +0.1 / 1.8 / .931 | no per-player split |
| Offensive rebound %, held | 5.0 | -1.0 / 1.6 / .921 | +0.1 / 1.2 / .926 | — |
| Defensive rebound %, held | 14.9 | +1.1 / 2.9 / .913 | -0.1 / 1.7 / .938 | — |

**Per 36:** the kernel's rates are converted at the league's rebound chances per minute.

| Players | Stat | Real | Kernel built: error / corr | Kernel refit: error / corr | Today: error / corr |
|---|---|---|---|---|---|
| All | Rebounds | 6.53 | 1.07 / .926 | 0.77 / .950 | **0.73 / .954** |
| All | Offensive | 1.68 | 0.58 / .914 | 0.43 / .921 | — |
| All | Defensive | 4.85 | 0.98 / .900 | 0.61 / .924 | — |
| Held | Rebounds | 6.50 | 1.03 / .934 | 0.72 / .955 | **0.65 / .962** |
| **2022-23 (held-out season)** | Rebounds | 6.66 | 1.48 / .877 | 1.23 / .906 | **1.12 / .922** |
| 2022-23 | Offensive | 1.61 | 0.57 / .895 | 0.52 / .894 | — |
| 2022-23 | Defensive | 5.06 | 1.24 / .807 | 1.06 / .841 | — |

**League and team checks:**

| | Real | Kernel built | Kernel refit | Today's engine |
|---|---|---|---|---|
| League offensive rebound % | 26.0 | 20.4 | **26.0** | 25.0 (150-game real-minutes replay) |
| Team offensive rebound %: correlation across teams | — | .82 | **.83** | .73 (only about 10 replayed games per team, so noisy) |
| Team offensive rebound %: error / predicted spread | spread 3.1 | 5.9 / 2.5 | 1.7 / 2.4 | — |

**Offensive rebound % by miss type (refit):**

| Miss type | Offensive rebound % |
|---|---|
| Rim | 31.8 |
| Short | 24.3 |
| Mid | 23.7 |
| Three | 26.0 |
| Free throw | 20.0 |

Long misses from three now come back to the offense slightly more often than midrange misses, as in real tracking. The real free-throw figure is about 11%, so free-throw rebounds are still too offense-friendly; see the fixes below.

**15 biggest misses each way** (refit; season rebounds on his real chances; offensive and defensive rebound %, kernel/real):
- **Over-predicted:**
  1. Amen Thompson +127 (OR 9.3/8.9, DR 18.5/14.1)
  2. Jaden McDaniels +126 (DR 14.8/10.9)
  3. Naji Marshall +120
  4. Jabari Smith Jr. +118
  5. Cooper Flagg +117
  6. John Collins +92
  7. Wendell Carter Jr. +91 (OR 12.3/7.8)
  8. Mouhamed Gueye +83
  9. Julius Randle +80
  10. Lauri Markkanen +76
  11. Kelly Oubre Jr. +71
  12. Toumani Camara +68
  13. Kevin Durant +68
  14. Scottie Barnes +67
  15. Kris Dunn +63

  These are almost all long, athletic forwards and wings on defense.
- **Under-predicted:**
  1. Clint Capela -123 (OR 9.7/19.3)
  2. Donovan Clingan -107
  3. Kel'el Ware -105
  4. Mitchell Robinson -100 (OR 15.2/24.7)
  5. Draymond Green -97 (DR 13.8/19.9)
  6. Rudy Gobert -96
  7. Robert Williams III -94
  8. Marvin Bagley III -82
  9. Steven Adams -79 (OR 15.2/22.5)
  10. Kevin Love -66 (DR 19.3/29.9)
  11. Russell Westbrook -64
  12. Moussa Cissé -63
  13. Jaylin Williams -60
  14. Jalen Johnson -59
  15. Ivica Zubac -59

  These are almost all rim-running, non-shooting centers and elite glass-eaters.

## Piece 2: fouls and free throws
**Per player, 2025-26** (369 rotation players with 150+ FGA):

| Stat | Scope | Real | Kernel built: bias / error / corr | Kernel refit: bias / error / corr | Today: bias / error / corr |
|---|---|---|---|---|---|
| FTA per FGA | All | .264 | -.118 / .138 / .866 | -.011 / .062 / .849 | **-.002 / .050 / .891** |
| Fouls per 36 | All | 2.91 | -0.72 / 0.89 / .636 | -0.00 / 0.37 / .808 | **+0.09 / 0.32 / .848** |
| FTA per FGA | Held | .264 | -.123 / .142 / .866 | -.007 / .065 / .847 | **-.004 / .051 / .891** |
| Fouls per 36 | Held | 2.91 | -0.74 / 0.91 / .629 | -0.04 / 0.40 / .796 | **+0.07 / 0.33 / .843** |
| **FTA per FGA** | **2022-23, 268 players** | .278 | 0.077 / **.751** | 0.091 / .726 | 0.084 / .750 |
| **Fouls per 36** | **2022-23** | 2.90 | 0.58 / .666 | 0.50 / .758 | **0.48 / .773** |

(The 2022-23 rows show error / corr, with levels matched.)

**League level** (kernel = expected values over the real-game lineups; today = 150-game real-minutes replay):

| Per 100 possessions | Real (targets) | Kernel built | Kernel refit | Today's engine |
|---|---|---|---|---|
| Personal fouls | 19.37 | 14.42 | **19.26** | 19.17 |
| Free-throw attempts | 22.90 | 13.36 | **22.32** | 23.79 |
| Free-throw rate (FTA/FGA) | .2635 | .154 | **.257** | .275 |
| Shooting fouls (BBI share 52% → about 10.05) | ~10.05 | 5.08 | **9.95** | not modelled |

**15 biggest misses each way** (refit):
- **Free throws over-predicted** (season FTA; kernel/real FTA per FGA):
  1. Jalen Duren +145 (.72/.54)
  2. Alperen Şengün +141
  3. Alex Sarr +116
  4. Nic Claxton +110
  5. Brandon Ingram +103
  6. Scottie Barnes +97
  7. Maxime Raynaud +95
  8. Nikola Vučević +90
  9. Cooper Flagg +89
  10. Ivica Zubac +80
  11. Derik Queen +78
  12. Jaren Jackson Jr. +75
  13. Joel Embiid +75
  14. Anthony Davis +73
  15. Jarrett Allen +73

  These are rim-zone bigs.
- **Free throws under-predicted:**
  1. Deni Avdija -236 (.35/.57)
  2. Luka Dončić -203
  3. Austin Reaves -128
  4. James Harden -118
  5. Desmond Bane -103
  6. Stephon Castle -95
  7. Zion Williamson -91
  8. Keyonte George -91
  9. Bennedict Mathurin -90
  10. Norman Powell -86
  11. Coby White -83
  12. Jamal Murray -81
  13. Devin Booker -81
  14. Pelle Larsson -77
  15. Brandon Williams -71

  These are guards and wings who draw fouls off the dribble and on jumpers.
- **Fouls over-predicted** (season fouls; kernel/real per 36):
  1. Bam Adebayo +71 (2.9/1.9)
  2. Rudy Gobert +64
  3. Kawhi Leonard +61
  4. Jalen Duren +59
  5. Bobby Portis +46
  6. Amen Thompson +45
  7. Donovan Clingan +40
  8. Baylor Scheierman +40
  9. Will Riley +39
  10. Nic Claxton +39
  11. Payton Pritchard +39
  12. LaMelo Ball +38
  13. Kel'el Ware +38
  14. Karl-Anthony Towns +35
  15. Moussa Diabaté +35
- **Fouls under-predicted:**
  1. Ace Bailey -59 (2.4/3.5)
  2. Cade Cunningham -54
  3. Sidy Cissoko -53
  4. Andrew Wiggins -52
  5. Kyshawn George -51
  6. Sion James -49
  7. Desmond Bane -49
  8. Dylan Cardwell -45
  9. Stephon Castle -45
  10. Spencer Jones -38
  11. Isaiah Collier -38
  12. Hugo González -35
  13. Bruce Brown -34
  14. Jamir Watkins -34
  15. Jonas Valančiūnas -33

  Many are rookies and young players.

Full tables, with every player, are in `output/stage2/rebound_foul_check.json` (`misses_built`, `misses_fit`).

## Timing
Pure Python, on the busy laptop:

| Call | Time |
|---|---|
| One rebound resolved (ten players, matchups precomputed) | 6.0 µs |
| One shot attempt's foul chance, with help and and-one | 1.6 µs |
| One possession's non-shooting foul weights | 1.3 µs |

**Per possession:** about one shot, 0.5 rebound and the foul draws come to roughly **0.006 ms**, about 2-3% of the 0.2-0.4 ms budget. Together with the shooting kernels (about 0.006 ms), that is still well under 5% of the budget.

## Kernel fixes made (no rating touched)
1. **Rebounds: conversion refit.**
   - Defense edge 0.70 → 0.56: the league offensive rebound % was 20.4%; the refit takes it to 26.0%.
   - Skill and reach slopes lowered.
   - Box-out seal smaller.
   - Distances tighter.
2. **Rebounds: structural changes.** A residual check showed over-crediting of athletic wings and under-crediting of box-out bigs.
   - Jump capacity and standing reach now have separate slopes.
   - Body mass enters the box-out contest.
   - A defender whose seal holds keeps more of his own chance.
   - A paint-anchor term, so helpers stand near the rim.
   - The refit wanted jump and mass slightly negative, which has no physical meaning, so both are pinned at zero. Held-out error was unchanged to within 0.1 point. The paint-anchor term fitted to zero.
3. **Fouls: staged, bounded refit.**
   - A first free-form fit drifted to nonsense: three-point shooting-foul rates near 6%, and a bonus share of .59 that traded shooting fouls for bonus free throws.
   - Now the free-throw side and the foul side are fitted separately with sign bounds.
   - The bonus share comes from the NBA rule (.274).
   - The three-point foul chance is pinned to Basketball Index's 1.1%.
   - The league shooting-foul share is a target.
   - Fitted to zero: help-defender share, jump-contest effect, strength, illegal-screen fouls.

## Proposed kernel fixes (next)
1. **Free throws by action, not only by zone.** This is the main free-throw defect.
   - The kernel should take the action from the possession loop: drive, post, roll/cut, putback or jumper.
   - Drives use Basketball Index's drive foul drawn rate. Putbacks, rolls and lobs draw far fewer fouls than drives.
   - This should fix both lists above at once: rim-zone bigs over, ball-handlers under.
2. **Rebounds: defensive spots from role, not height-matching.**
   - The non-shooting rim-runners (Capela, Robinson, Adams, Clingan) and help-side wings are the misses.
   - Defensive positions should come from the coverage and who is guarding whom in the possession loop. A drop big stays near the rim; a wing guarding a corner shooter is out on the perimeter.
   - Offensive spots for roll men should be at the rim, not the T02 average.
3. **Free-throw miss rebounds:** refit the lane spots (kernel 20% vs real about 11% for the offense).
4. **Young players' fouls:** rookies are under-predicted.
   - Foul control (S45) for rookies leans on priors.
   - This is a ratings-evidence question (rule 1), not a kernel one. Note it for the ratings team.

## Recommended next component
**The first fast possession loop** (roadmap step 4 and the start of step 5).
- Five-man lineups from real minutes. The `game_contexts` sampler is already a working stand-in.
- An action choice per possession: drive, pick-and-roll, post, spot-up or transition, from tendencies and roles.
- Then shot (refit shooting kernel), foul (this kernel, keyed by action), rebound (this kernel) and turnover.
- A clock and the real bonus count.

Fold in the shooting follow-ups (per-family conversion, hook/post finish) and fix 1 above. A turnovers/steals spot-check is the one component left from the plan, and it can ride along in the same task: the box-score turnover and steal fits already exist to compare against. The perimeter contest/closeout piece should follow once matchups exist in the loop.

## Checks
- `tests/test_stage2_rebound_fouls.py`: 15 tests, all OK. They cover:
  - kernel properties: probabilities sum to 1; technique, crash and box-out push the right way; long misses favor perimeter players; foul accounting;
  - helpers;
  - "stage2 pieces stay out of normal gameplay";
  - a data smoke test: real environment, fitted league levels, deterministic contexts.
- `bash scripts/run_core_tests.sh`: 338 tests OK (2 skipped).
- `scripts/run_tests_parallel.py --workers 2 --match "stage2|experimental_input|calibration"`: see below.
- No changes to `sim.py`, `save.py`, `play.py`, ratings files or `experimental_inputs.py`. The default engine is untouched.

## Resume state
- [x] Kernels, checks, refits, driver, tests, report. Board row set to **review**.
