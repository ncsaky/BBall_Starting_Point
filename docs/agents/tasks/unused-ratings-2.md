# UNUSED-RATINGS-2: the last ignored ratings, development for the newly used ones, screen assists on screen, spot-up shooters

_Claude (Opus agent), 2026-11-19, branch `worktree-agent-a69638def74bcddc7`. Rules 1, 2, 3, 4, 7 and 9 apply. No skill or habit rating was changed; strength and jump capacity were rebuilt from new evidence through the normal inputs build (user request mid-task)._

**TL;DR**
- Foul control, steal gambling and contest habits now set each player's fouls and foul trouble (match with real fouls per 36: 0.09 -> 0.77); the pace habit now sets team pace; the shooting-mode and cutting habits now shape how many points a player scores.
- Strength and jumping are now built from NBA Draft Combine tests (age-adjusted) plus in-game evidence; they now age with the game's own curves, as do screen setting, defensive rebounding, steal technique and foul control. They add nothing to the box score beyond the skills, so they stay out of it (documented).
- Screen assists now appear in the box score, the player's season line, the playoff stats table and league leaders; spot-up shooters keep more of their made threes (AJ Green true shooting .499 -> .530, real .627: better, not fixed). Both scorecards hold: {SCORECARD_LINE}

## Resume state

Done; ready for review. Commits on this branch: two checkpoints plus a final one (code, data, tests, this report, board row); not pushed or merged. Scratch scripts and outputs: `output/unused-ratings-2/` (git-ignored; a real folder in this worktree, copy it to main's `output/` before removing the worktree): `replay_dump.py` (one full-season replay -> per-player totals, team pace, calibration report), `dump_before/after.json`, `calib_*.txt`, `fit_explore.py` / `fit_fouls.py` / `fit_points.py` / `fit_physical.py` (fits), `team_evidence.py` (team pace, gambling, box-out), `shooters.py`, `fouls_check.py`, `reb_outliers.py`, `aging_curves.py` (Basketball Index aging by age), `dev_check.py` (two-season development), `phys_diag.py` / `phys_diff.txt` (combine evidence and who moved), `sensitivity.py` + `sensitivity_after.json/.txt` (the sweep), `usage_table2.py` (builds the table below). Worktree data symlinks (`.venv`, Barttorvik, sqlite, injury evidence, Basketball Index files, `output/settlement-materialization-pass`, `output/unused-ratings`) are untracked and were not committed.

## 1. Inputs that still did nothing

How each was checked: a fit to real 2025-26 data (377 rotation players with 500+ minutes; fouls from `data/research/game_boxscores_2025_26.json`, other stats from the calibration targets), out-of-fold correlation like the other box rates (`scripts/fit_box_stat_rates.py` method), then a full-season replay with real minutes before and after (`replay_dump.py`).

### Foul control, steal gambling -> fouls and foul trouble (wired in)

- **Evidence.** Personal fouls per 36, log-linear fit: foul control (S45) -1.7% per grade point, steal gambling (T14) elasticity +0.69, contest technique (S37) +0.4% per point (the players who contest the most shots foul more), jump-contest share (T16) elasticity +0.23. Out-of-fold r **0.84** (foul control alone 0.64, plus gambling 0.71). Height, strength and jumping add nothing once these are in. `box_rates.FOULS_INPUTS`.
- **Now.** Each player fouls at his own rate, in replayed games (`sim.assign_personal_fouls`) and in generated games, where fouls drive the coach's foul-trouble decisions (`game_minutes.manage_game_minutes` takes per-player rates; `sim.player_foul_multipliers`). Replayed games also use the generated games' "fouls slow down once a player has four or five" rule; a plain count at the same rate fouled regulars out in 4% of games vs 1.4% real.
- **Before -> after (full-season replay, 377 players):** correlation of simulated with real fouls per 36 **0.09 -> 0.77**; mean error 0.67 -> 0.41; spread 0.28 -> 0.73 (real 0.82). Foul-outs per game for 24+ minute players 4.1% -> **1.9%** (real 1.4%). League fouls per 100 possessions 19.10 -> 19.30 (real 19.37). Most foul-prone real players now foul like it (Cardwell 2.4 -> 5.4 per 36, real 6.4; Bitadze 2.7 -> 5.5, real 5.0); the cleanest too (Tyus Jones 3.2 -> 1.2, real 1.1; Kawhi Leonard 3.1 -> 2.0, real 1.3).
- **Generated games (normal gameplay, 1,230 games):** fouls per 36 vs real 0.08 -> **0.78**. Foul-outs for regulars 0.33% -> 0.37% of games, against 1.4% real: the coach's foul-trouble benching (from the heavy-minutes task) keeps almost everyone under six. That gap predates this task; tuning it would move the minutes shape that task fitted, so it is left for the minutes owner (suggestion: bench a player in foul trouble for less of the time he is ahead of pace).
- **Steals.** Gambling adds nothing to steals at the same steal technique (r 0.915 -> 0.922, wrong sign: the technique grades are built from the same steal record), so it is not in the steals fit. Steals unchanged (r 0.79).
- **Defensive breakdowns.** No penalty added: teams that gamble more defended *better* in 2025-26 (team gambling vs defensive rating r -0.69), so 30 teams cannot separate a gambling cost from the anticipation and effort behind it. Where it should matter: the possession engine (a missed gamble leaves a man open), or a lineup-level study.

### Pace habit -> team pace (wired in; moves scores)

- **Evidence.** For the 30 teams, real pace (Basketball Index possession lengths) minus the engine's replayed pace rose with the team's minutes-weighted pace habit (T05): 56.6 possessions per unit of the habit on the engine's scale (se 15, r 0.57). One team standard deviation of the habit is about one possession a game. `team_evidence.py`.
- **Now.** `sim.pace_habit_possessions`: both teams' possessions move by the sum of the two teams' departures from the league habit (pace is a game-level thing), bounded at +-4. Replayed games centre on the real-minutes league habit (0.4035); generated games centre on the league's projected-minutes habit (0.416), because the coaches' rotations favour quicker-paced players and would otherwise add a possession to every game (the habit should spread teams, not move the league). Old-ratings saves are unchanged.
- **Generated-game check (1,230 games, healthy rotations):** league pace 102.6 without the habit, 103.6 with a fixed centre, **102.2** with the league centre (real 102.0); points 118.6 (was about 119.1; real 115.6, a separate known gap).
- **Before -> after:** correlation of simulated with real team pace **0.74 -> 0.84**; the engine's team pace spread 0.92 -> 1.45 possessions (real about 2.1); the leftover link to the habit 50.6 -> 7.2 (not significant). League pace 101.9 -> 101.7 (real 102.0).

### Shooting-mode habit (catch / pull-up / movement) -> points share (wired in)

- The box score has no shot types, and real players' three-point percentages come from their own record (which already reflects their mix), so the habit cannot honestly change efficiency. It now decides **which shooting skill counts**: the catch-and-shoot, pull-up and movement three grades weighted by how often he takes each (`S.three_mode` in `box_rates.flatten_inputs`) enter the points-per-36 fit, so a spot-up shooter is handed more of his team's points. Points fit out-of-fold r 0.933 -> 0.938.

### Cutting habit -> points share (wired in, small)

- Cutters score more off the ball at the same involvement: adding the cutting habit (T09, elasticity 0.14) to the points fit lifts it to r **0.940** (error 1.37 -> 1.35 points per 36). The box score does not split shots by zone, so this is the only honest place for it; where it should matter more: assisted shots at the rim once the box score tracks zones.

### Crash versus box-out (T13): documented, no new effect

- Already in the rebound share since the first pass (pursue share). A team effect was tested: team box-out emphasis vs real defensive-rebound rate r 0.17 (not significant), so nothing was added. Where it should matter: who secures rebounds in the possession engine.

### Strength and jumping: rebuilt from real evidence, documented as having no extra box-score effect

User request mid-task: "something better" than size-and-position estimates.

- **New evidence** (`src/nba_gm_data/physical_evidence.py`, called by `scripts/build_player_inputs.py`, every source attributed in each record's evidence list):
  - **NBA Draft Combine** strength and agility tables 2000-2025 (`data/research/draft_combine_2000_2025.json`, built by `scripts/research/draft_combine.py`). stats.nba.com refuses scripted requests from this machine, so the table comes from a public mirror of the NBA.com export (github.com/nkal22/combine_score); a second, independent NBA.com pull (github.com/davidmilitaru/NBA_draft_combine, 2013-2019, with NBA player ids) agrees on **1,300 of 1,300** overlapping values. Matched to 391 current players (name plus a combine year that fits his draft year and age): 295 with a standing vertical, only 74 with a bench press (the combine dropped the bench after 2019, and many top picks skip testing).
  - **Age adjustment:** each test is moved to the player's current age along the game's own expected development curve (`health.monthly_trait_delta`, expected changes only): jumping on the athletic curve (foot speed and agility), strength on the general curve; rating points become inches or reps through the league spread of each.
  - **In-game proxies, against size:** dunks per close attempt (Basketball-Reference), blocks per 36 and offensive-rebound rate (2025-26), and Basketball Index contact-finish rate, drive foul-drawn rate and putback scoring (local captures only; nothing raw committed).
  - **Blend by reliability:** a precision-weighted mean of the combine result (error: test noise of a third of a standard deviation plus 0.06 per year since the combine), the proxy model (its out-of-fold error) and the size-and-position estimate (the previous estimate used as a regressor, fitted on tested players).
- **What the evidence says.**
  - Jumping: standing vertical is predicted by size and the old estimate at r 0.30 and by the proxies at r **0.40** (dunk rate is the strong one). Jump capacity is stored in cm as before; the league spread grew from 2.95 to 5.28 cm, and the scale moved to the combine's (mean 69.2 -> 77.9 cm).
  - Strength: among NBA players the combine bench does **not** follow body mass (r 0.08) or any in-game proxy (|r| <= 0.17), so only the 74 tested players move (combine weight 0.5-0.77, the rest the old estimate); everyone else keeps the old size-and-position estimate, low confidence.
- **Who moved most** (`phys_diff.txt`). Jumping up: Jericho Sims 64.6 -> 94.1 cm (37-inch standing vertical, 2021), Drake Powell +26.5, Oso Ighodaro +25.8, Harrison Barnes +24.0 (38 inches in 2012, aged), Julian Phillips, Adem Bona, E.J. Liddell, Olivier-Maxence Prosper (+22-23). Jumping down: Alex Karaban -7.5 cm, Cam Spencer -7.2, Danny Wolf, Tristen Newton (-5). Strength up: Grant Williams 53.7 -> 86.1 (20 reps), Bruce Brown +30, Dillon Brooks +25, Lu Dort, John Collins, Steven Adams (+19-22). Strength down: Naz Reid 60.4 -> 31.2 (3 reps), De'Anthony Melton, Anfernee Simons, Ty Jerome (-27), Kawhi Leonard 59.5 -> 37.8, Jarrett Allen, Khris Middleton, Bobby Portis (about -20).
- **Box score.** With the improved values, neither adds anything to any box-score fit once the skills are in: rebounds r 0.939 -> 0.942 with jumping taking a *negative* weight; blocks, fouls, free throws, points, screen assists all unchanged or worse; the offensive-rebounding and rim-protection rating recipes (`scripts/fit_offensive_rebounding.py`, `fit_rim_protection.py`) still do not pick them. The skill grades are built from those same outcomes, so the tools' contribution is already inside them; adding the tools would count it twice. So they are not wired into the box score. They now matter through **development** (below: a player's skills no longer age while his tools stay frozen) and are shown on the card. Where they should matter: the possession engine (reach plus jump for contests and rebounds) and draft prospects without an NBA record.
- **Only these two inputs changed:** a full rebuild before the change reproduced the committed inputs file byte for byte; after it, 0 records changed outside strength and jumping (691 players). The value formula does not read either, so player values are unchanged.

## 2. Development for the newly used ratings

`ratings_model.route_trait_deltas`. Inputs outside the 15 blended ratings never changed over a career. Each now follows the skill whose real aging it matches, measured on Basketball Index's year-to-year talent grades by age (`aging_curves.py`, change per season in league standard deviations at 19-22 / 23-25 / 26-28 / 29-31 / 32+):

| Input | Develops like | Evidence |
|---|---|---|
| Defensive-rebound positioning, box-out, rebound control | offensive-rebounding technique | defensive rebounding +.11 / -.01 / -.07 / -.11 / -.20 vs offensive +.10 / +.01 / -.06 / -.08 / -.18 |
| Screen setting | screen-action reads (an experience skill) | screening +.05 / +.03 / +.08 / -.03 / -.02 |
| On-ball steals, passing-lane steals | defensive anticipation | steals per 75 +.09 / .00 / .00 / -.05 / +.01 |
| Foul control | attention / responsibility | fouls per 75 -.12 / -.06 / -.01 / +.02 / +.04 (fewer fouls while young) |
| Strength | the general aging curve (rim protection) | same curve used to age the combine bench |
| Jump capacity (cm) | the athletic curve (foot speed); 1.30 cm per grade point (league spreads 5.28 cm / 4.05) | same curve used to age the combine vertical |

Two-season check (`dev_check.py`: 24 months of the normal development model on the league, 445 players with 10+ minutes; mean change by age): every routed input moved for every player, and each matches the input it follows (defensive rebounding +1.1 / +0.2 / -0.3 / -1.3 / -3.7 grade points across the age groups; screen setting +1.4 ... -0.1; steal technique +1.0 ... -2.2; foul control +1.1 ... -1.5; strength +0.9 ... -1.7; jump capacity +1.6 cm ... -2.7 cm). No new curves were invented. Habits stay fixed (by design: development moves skills and tools, not choices), except involvement as before.

## 3. Screen assists on screen

- `save.STAT_FIELDS` gains `screen_assists`, so season, playoff and game-log totals carry it (a one-line change outside the development functions; old saves read 0).
- Box score: an **SAST** column after AST (with a tooltip), shown only when the game tracked screen assists (new ratings); same table style.
- Player card season line: **SAST** per game between AST and STL (only when the save tracks them; `app_actions` adds `screen_assists_per_game` to the season block).
- Playoff stats table: an SAST column (sortable like the others); league leaders: "Screen Assists" in the stat picker.
- Draft-board code untouched. JS tests: the playoff table test now expects the new column. Not checked by eye in the running app.

## 4. Low-usage three-point shooters

- **Cause.** Points are handed out first; made threes were then drawn at the player's percentage and cut to fit his points. On quiet nights he lost made threes (half their attempts stayed as misses); on big nights his extra points became two-pointers. Spot-up shooters (3PA share >= .55, usage <= 18, 39 players) ran 2.15 made threes per 36 vs 2.73 real and 6.47 attempts vs 7.17.
- **Fix** (`offense.night_three_pct`, box score only, same random draws): tonight's made-three chance follows tonight's points relative to his normal output, solved so the expected makes after the points cap equal his usual makes scaled by that ratio; over a season it averages his own percentage; his attempts are kept. Plus the points-share fit now reads three-point shooting (as he shoots it) and cutting (section 1). The fill of team two-point misses no longer gives a player with no two-point shots tonight an automatic claim.
- **Before -> after:** spot-up group made threes 2.15 -> **2.57** per 36 (real 2.73), attempts 6.47 -> 7.08 (7.17), true shooting .550 -> **.562** (real .583). AJ Green .499 -> .530 (real .627), Duncan Robinson .507 -> .558 (.629), Luke Kennard .602 -> .629 (.689), Sam Merrill .559 -> .597 (.644), Max Christie .530 -> .577 (.601). High-usage creators unaffected: top-usage quarter .601 -> .598 (real .590); Ingram-type tough-shot scorers keep the first pass's fix. League three-point attempt rate .390 -> .406 (real .415); player shot attempts error 1.07 -> 0.93 per 36, threes 0.36 -> 0.28.
- **Still short:** pure shooters are still handed fewer points than their threes need (AJ Green 11.3 per 36 vs 12.8 real), so the cap still binds; their two-point percentage also runs ~3 points under their own (.506 vs .522; the team miss fill). Next step: a points floor from a shooter's own record, or the possession engine.

## 5. Rating oddities for the next ratings review (nothing changed)

- **Jokić's defensive-rebound positioning is 41.7** (32nd percentile). His box-out (76.9) and rebound control (85.5) carry his rebounding (simulated 13.2 per 36, real 13.3), but the positioning grade itself looks wrong for the league's best defensive rebounder.
- **Amen Thompson** (fit 12.1 per 36, simulated 9.8, real 7.5) and **Ausar Thompson** (fit 9.9, real 7.9): their defensive-rebounding grades are 96th-98th percentile (positioning 83 / 80, control 79 / 78) with a 95th-percentile pursue habit. That is the inputs, not the fit (among bigs the fit is unbiased: real/fit +3%, no input correlates with the error beyond |r| 0.21).
- **Nic Claxton** (fit 11.3, simulated 12.7 -> **11.7**, real 9.0). Part was the engine: rebounds were drawn with a flat +0.45 and wide noise, then shared with a power of 1.32 that over-concentrated them on the top rebounders (Claxton, Davis, Antetokounmpo, Duren all ~1.5 over their fitted rate). **Fixed:** rebounds are now a Poisson count around each player's own rate from the same random number, shared in plain proportion (player rebounds bias -0.09 -> -0.01 per 36). What is left is his inputs (crash habit 90th, box-out 88th percentile) against a down 2025-26.
- **Strength from the bench press** penalises long arms (Kawhi Leonard 37.8, Jarrett Allen 38.5, Khris Middleton 37.1): 185-lb reps measure strength endurance, and the NBA export shows a 0-rep bench as untested (Durant). Consider an arm-length adjustment or a different strength source.
- **AJ Green's points share** (11.3 per 36 vs 12.8 real) and **Duncan Robinson's** keep their true shooting low; worth checking their involvement grades.

## The 94 inputs now

Columns: blended ratings each input feeds (share); what reads it directly (NEW = this pass); how it develops; the +15 sweep (120 rotation players bumped +15 grade points, habits x1.3, habit mixes +10 points per outcome, body sizes +5%; same 400 replayed games; average change of a team's points per game / winners flipped out of 400 / biggest change in the bumped players' per-36 box rates), first pass vs now.

| Input | Blended ratings it feeds | Read directly | Develops | Sweep, first pass (team pts / flips / biggest box change) | Sweep now |
|---|---|---|---|---|---|
| P01 Height | rim protection 14%, playoff translation 2% | rebounds | body size (fixed) | 1.06 / 11 / rebounds 0.34 | 0.91 / 6 / rebounds 0.34 |
| P02 Wingspan | rim protection 4%, offensive rebounding 4%, playoff translation 2% | rebounds | body size (fixed) | 0.23 / 5 / rebounds 0.07 | 0.20 / 2 / rebounds 0.08 |
| P03 Standing reach | playoff translation 2% | - | body size (fixed) | 0.01 / 0 / fga 0.01 | 0.06 / 1 / points 0.01 |
| P04 Body mass | playoff translation 2% | screen assists, Screening rating | body size (fixed) | 0.04 / 0 / screen_assists 0.24 | 0.06 / 1 / screen_assists 0.25 |
| P05 Acceleration / first step | rim pressure 5%, foot speed 25%, screen navigation 15% | - | with its blended ratings | 0.43 / 5 / ftm 0.03 | 0.57 / 5 / rebounds 0.02 |
| P06 Straight-line speed | foot speed 15% | - | with its blended ratings | 0.32 / 3 / ftm 0.02 | 0.23 / 1 / rebounds 0.01 |
| P07 Lateral mobility / change of direction | foot speed 45%, screen navigation 15% | - | with its blended ratings | 0.95 / 8 / rebounds 0.05 | 0.94 / 7 / points 0.07 |
| P08 Functional strength | - | - | general curve | 0.00 / 0 / no box change | 0.00 / 0 / no box change |
| P09 Physical balance / stability | handle 5% | - | with its blended ratings | 0.02 / 0 / fga 0.01 | 0.07 / 1 / no box change |
| P10 Vertical / jump capacity | - | - | athletic curve (cm) | 0.00 / 0 / no box change | 0.00 / 0 / no box change |
| P11 Conditioning | stamina 60% | - | with its blended ratings | 0.32 / 1 / points 0.03 | 0.26 / 1 / points 0.03 |
| P12 Recovery between efforts | stamina 40% | - | with its blended ratings | 0.17 / 0 / assists 0.01 | 0.18 / 1 / points 0.02 |
| S01 Catch-and-shoot three-point execution | shot release 10%, three-point range 10%, shot versatility 5%, portability 20% | NEW points share (via shooting mode) | with its blended ratings | 2.50 / 34 / fg3a 0.33 | 2.66 / 39 / fg3a 0.35 |
| S02 Pull-up three-point execution | shot release 10%, three-point range 10%, shot versatility 15% | NEW points share (via shooting mode) | with its blended ratings | 2.75 / 38 / fg3a 0.39 | 2.98 / 47 / fg3a 0.43 |
| S03 Movement three-point execution | shot release 10%, three-point range 5%, shot versatility 5% | NEW points share (via shooting mode) | with its blended ratings | 1.89 / 27 / fg3a 0.23 | 2.13 / 31 / fg3a 0.24 |
| S04 Catch-and-shoot midrange execution | shot versatility 5% | - | with its blended ratings | 0.14 / 1 / points 0.02 | 0.30 / 3 / turnovers 0.02 |
| S05 Pull-up midrange execution | shot versatility 15% | - | with its blended ratings | 0.28 / 2 / points 0.03 | 0.43 / 5 / points 0.03 |
| S06 Movement midrange execution | shot versatility 5% | - | with its blended ratings | 0.13 / 1 / points 0.02 | 0.26 / 2 / turnovers 0.01 |
| S07 Free-throw execution | three-point range 5% | - | with its blended ratings | 2.20 / 33 / fg3a 0.31 | 2.15 / 35 / fg3a 0.34 |
| S08 Release / preparation technique | shot release 30% | - | with its blended ratings | 1.59 / 26 / fg3a 0.21 | 1.62 / 29 / fg3a 0.21 |
| S09 Distance-extension technique | three-point range 15% | - | with its blended ratings | 2.85 / 44 / fg3a 0.45 | 2.89 / 46 / fg3a 0.50 |
| S10 Layup / close-touch execution | shot versatility 5%, rim pressure 5%, playoff translation 5% | points share | with its blended ratings | 1.20 / 10 / points 0.65 | 1.71 / 22 / points 0.58 |
| S11 Floater / short-paint touch | shot versatility 10%, playoff translation 5% | - | with its blended ratings | 0.22 / 1 / rebounds 0.02 | 0.32 / 4 / points 0.03 |
| S12 Dunk execution | rim pressure 5%, playoff translation 5% | - | with its blended ratings | 0.22 / 1 / rebounds 0.03 | 0.45 / 5 / points 0.02 |
| S13 Aerial catch-to-finish execution | rim pressure 5%, playoff translation 5% | - | with its blended ratings | 0.60 / 5 / points 0.05 | 0.82 / 11 / points 0.07 |
| S14 Receiving / catch control | portability 10%, playoff translation 5% | - | with its blended ratings | 0.03 / 0 / fga 0.01 | 0.10 / 2 / no box change |
| S15 Contact finishing technique | rim pressure 5%, playoff translation 5% | - | with its blended ratings | 0.33 / 1 / points 0.02 | 0.52 / 5 / points 0.03 |
| S16 Dribble manipulation | handle 20%, playoff translation 5% | turnovers | with its blended ratings | 0.54 / 6 / turnovers 0.16 | 0.76 / 10 / turnovers 0.11 |
| S17 Handle security | handle 25%, playoff translation 5% | turnovers | with its blended ratings | 0.32 / 1 / turnovers 0.34 | 0.41 / 4 / turnovers 0.30 |
| S18 Perimeter separation craft | handle 10%, playoff translation 5% | - | with its blended ratings | 0.18 / 0 / points 0.02 | 0.24 / 2 / points 0.01 |
| S19 Driving craft | rim pressure 10%, playoff translation 5% | - | with its blended ratings | 0.74 / 5 / points 0.05 | 1.01 / 13 / points 0.07 |
| S20 Attack recognition | handle 10%, passing 10%, basketball IQ 15%, playoff translation 5% | - | with its blended ratings | 0.44 / 2 / points 0.04 | 0.42 / 3 / points 0.04 |
| S21 Post establishment / sealing | playoff translation 5% | - | with its blended ratings | 0.06 / 0 / points 0.01 | 0.18 / 3 / assists 0.01 |
| S22 Post moves / counters | playoff translation 5% | - | with its blended ratings | 0.08 / 0 / points 0.01 | 0.20 / 3 / fga 0.01 |
| S23 Post-specific finish execution | playoff translation 5% | - | with its blended ratings | 0.08 / 0 / points 0.01 | 0.21 / 3 / points 0.01 |
| S24 Foul-drawing craft | rim pressure 15%, playoff translation 5% | free throws | with its blended ratings | 0.95 / 8 / fta 0.51 | 1.09 / 16 / fta 0.52 |
| S25 Cutting-route execution | portability 10% | - | with its blended ratings | 0.02 / 0 / fga 0.01 | 0.11 / 2 / turnovers 0.01 |
| S26 Relocation / shooting-route execution | portability 10% | - | with its blended ratings | 0.02 / 0 / no box change | 0.08 / 1 / fga 0.01 |
| S27 Screen execution | - | screen assists, Screening rating, team offence | like S28 | 0.05 / 0 / screen_assists 0.30 | 0.09 / 1 / screen_assists 0.30 |
| S28 Screen-action recognition | passing 5%, basketball IQ 10% | screen assists, Screening rating, team offence | with its blended ratings | 0.62 / 4 / screen_assists 0.61 | 0.72 / 9 / screen_assists 0.61 |
| S29 Offensive rebound reading / pursuit technique | offensive rebounding 32% | - | with its blended ratings | 0.45 / 2 / fga 0.06 | 0.49 / 6 / rebounds 0.07 |
| S30 Defensive rebound reading / positioning | - | rebounds | like S29 | 0.03 / 0 / rebounds 0.29 | 0.11 / 2 / rebounds 0.27 |
| S31 Box-out technique | - | rebounds | like S29 | 0.03 / 0 / rebounds 0.59 | 0.11 / 2 / rebounds 0.52 |
| S32 Rebound control | - | rebounds | like S29 | 0.03 / 0 / rebounds 0.28 | 0.11 / 2 / rebounds 0.26 |
| S33 On-ball containment technique | foot speed 15%, portability 15% | - | with its blended ratings | 0.17 / 3 / ftm 0.02 | 0.10 / 1 / fga 0.01 |
| S34 Contact resistance / leverage technique | screen navigation 15% | - | with its blended ratings | 0.15 / 3 / ftm 0.01 | 0.12 / 0 / points 0.02 |
| S35 Screen-navigation technique | screen navigation 55%, portability 10% | - | with its blended ratings | 0.45 / 6 / ftm 0.03 | 0.39 / 3 / points 0.02 |
| S36 Interior positioning | rim protection 23% | - | with its blended ratings | 1.30 / 11 / points 0.07 | 1.20 / 7 / points 0.12 |
| S37 Contest technique | rim protection 52%, playoff translation 1% | NEW fouls | with its blended ratings | 1.91 / 17 / points 0.14 | 1.80 / 10 / points 0.19 |
| S38 Rotation recognition | basketball IQ 15%, rim protection 7% | - | with its blended ratings | 0.30 / 4 / rebounds 0.03 | 0.32 / 3 / points 0.03 |
| S39 Off-ball coverage positioning | basketball IQ 12%, portability 10% | - | with its blended ratings | 0.18 / 0 / fga 0.02 | 0.22 / 2 / points 0.02 |
| S40 Closeout / arrival control | defensive effort 15%, playoff translation 1% | - | with its blended ratings | 0.30 / 3 / ftm 0.03 | 0.21 / 1 / fga 0.02 |
| S41 Defensive anticipation | defensive effort 10% | - | with its blended ratings | 0.23 / 4 / ftm 0.02 | 0.14 / 1 / rebounds 0.01 |
| S42 On-ball steal technique | - | steals | like S41 | 0.04 / 0 / steals 0.10 | 0.06 / 1 / steals 0.10 |
| S43 Passing-lane interception technique | playoff translation 1% | steals | like S41 | 0.04 / 0 / steals 0.18 | 0.11 / 2 / steals 0.17 |
| S44 Attention / responsibility execution | defensive effort 25%, basketball IQ 12%, playoff translation 1% | - | with its blended ratings | 0.61 / 5 / rebounds 0.04 | 0.47 / 4 / fga 0.03 |
| S45 Foul-control technique | playoff translation 1% | NEW fouls and foul trouble | like S44 | 0.04 / 0 / steals 0.01 | 0.11 / 2 / personal_fouls 0.57 |
| S46 Defensive communication | defensive effort 10%, basketball IQ 11%, playoff translation 1% | - | with its blended ratings | 0.16 / 1 / fga 0.02 | 0.13 / 1 / fga 0.02 |
| F01.recognition Connector / swing / reversal — recognition | passing 4%, basketball IQ 3%, playoff translation 1% | - | with its blended ratings | 0.15 / 0 / assists 0.02 | 0.17 / 2 / rebounds 0.01 |
| F01.execution Connector / swing / reversal — execution | passing 2%, portability 15% | assists (passing delivery) | with its blended ratings | 0.10 / 1 / assists 0.17 | 0.21 / 3 / assists 0.14 |
| F02.recognition Post entry — recognition | passing 4%, basketball IQ 3%, playoff translation 1% | - | with its blended ratings | 0.13 / 0 / assists 0.02 | 0.15 / 2 / rebounds 0.01 |
| F02.execution Post entry — execution | passing 2% | assists (passing delivery) | with its blended ratings | 0.03 / 0 / assists 0.15 | 0.06 / 1 / assists 0.14 |
| F03.recognition Pocket / roll feed — recognition | passing 4%, basketball IQ 3%, playoff translation 1% | - | with its blended ratings | 0.13 / 0 / assists 0.02 | 0.16 / 2 / rebounds 0.01 |
| F03.execution Pocket / roll feed — execution | passing 2% | assists (passing delivery) | with its blended ratings | 0.05 / 0 / assists 0.15 | 0.06 / 1 / assists 0.14 |
| F04.recognition Lob — recognition | passing 4%, basketball IQ 3%, playoff translation 1% | - | with its blended ratings | 0.13 / 0 / assists 0.02 | 0.15 / 2 / rebounds 0.01 |
| F04.execution Lob — execution | passing 2% | assists (passing delivery) | with its blended ratings | 0.03 / 0 / assists 0.15 | 0.06 / 1 / assists 0.14 |
| F05.recognition Short-roll playmaking — recognition | passing 4%, basketball IQ 3%, playoff translation 1% | - | with its blended ratings | 0.13 / 0 / assists 0.02 | 0.16 / 2 / rebounds 0.01 |
| F05.execution Short-roll playmaking — execution | passing 2% | assists (passing delivery) | with its blended ratings | 0.04 / 0 / assists 0.15 | 0.01 / 0 / assists 0.15 |
| F06.recognition Drive-and-kick — recognition | passing 4%, basketball IQ 3%, playoff translation 1% | - | with its blended ratings | 0.13 / 0 / assists 0.02 | 0.16 / 2 / assists 0.01 |
| F06.execution Drive-and-kick — execution | passing 2% | assists (passing delivery) | with its blended ratings | 0.05 / 0 / assists 0.15 | 0.06 / 1 / assists 0.14 |
| F07.recognition Skip / cross-court — recognition | passing 4%, basketball IQ 3%, playoff translation 1% | - | with its blended ratings | 0.13 / 0 / assists 0.02 | 0.15 / 2 / rebounds 0.01 |
| F07.execution Skip / cross-court — execution | passing 2% | assists (passing delivery) | with its blended ratings | 0.03 / 0 / assists 0.15 | 0.06 / 1 / assists 0.14 |
| F08.recognition Post playmaking — recognition | passing 4%, basketball IQ 3%, playoff translation 1% | - | with its blended ratings | 0.13 / 0 / assists 0.02 | 0.15 / 2 / rebounds 0.01 |
| F08.execution Post playmaking — execution | passing 2% | assists (passing delivery) | with its blended ratings | 0.04 / 0 / assists 0.15 | 0.06 / 1 / assists 0.14 |
| F09.recognition Transition / outlet / advance — recognition | passing 4%, basketball IQ 3%, playoff translation 1% | - | with its blended ratings | 0.13 / 0 / assists 0.02 | 0.16 / 2 / assists 0.01 |
| F09.execution Transition / outlet / advance — execution | passing 2% | assists (passing delivery) | with its blended ratings | 0.10 / 1 / assists 0.17 | 0.15 / 2 / assists 0.14 |
| T01 Shoot / drive / pass / post / reset choices | rim pressure 15%, passing 15% | points share, assists | habit (fixed) | 2.76 / 37 / points 1.98 | 2.63 / 38 / points 1.83 |
| T02 Shot-location preferences | shot release 25%, three-point range 55%, rim pressure 20% | - | habit (fixed) | 3.86 / 51 / fg3a 0.65 | 3.84 / 54 / fg3a 0.70 |
| T03 Shooting-mode preferences | - | NEW points share (weights the three-point grades) | habit (fixed) | 0.00 / 0 / no box change | 0.09 / 1 / points 0.02 |
| T04 Shot difficulty tolerance | shot versatility 10% | share of team shooting luck | habit (fixed) | 0.24 / 1 / fga 0.15 | 0.41 / 5 / fga 0.08 |
| T05 Pace / early-attack preference | - | NEW team pace | habit (fixed) | 0.00 / 0 / no box change | 4.04 / 19 / points 0.50 |
| T06 Dribble / possession persistence | handle 10% | - | habit (fixed) | 0.03 / 0 / fga 0.01 | 0.08 / 1 / fga 0.01 |
| T07 Passing risk appetite | - | turnovers, assists | habit (fixed) | 0.00 / 0 / turnovers 0.57 | 0.00 / 0 / turnovers 0.56 |
| T08 Offensive involvement preference | shot versatility 25%, rim pressure 15%, handle 20%, passing 15% | points share, turnovers, assists, free throws; player value | follows offensive skill | 3.24 / 39 / points 2.63 | 3.39 / 46 / points 2.61 |
| T09 Cutting frequency | - | NEW points share | habit (fixed) | 0.00 / 0 / no box change | 0.78 / 11 / points 0.35 |
| T10 Relocation / off-ball movement frequency | shot release 15% | - | habit (fixed) | 1.01 / 12 / fg3a 0.14 | 0.99 / 16 / fg3a 0.14 |
| T11 Screen / roll / pop / slip preferences | - | screen assists, Screening rating, team offence | habit (fixed) | 0.04 / 0 / screen_assists 0.18 | 0.05 / 1 / screen_assists 0.17 |
| T12 Offensive crash versus retreat | offensive rebounding 64% | rebounds | habit (fixed) | 0.82 / 5 / rebounds 0.57 | 0.84 / 6 / rebounds 0.51 |
| T13 Defensive pursuit versus box-out emphasis | - | rebounds (pursue share) | habit (fixed) | 0.00 / 0 / rebounds 0.03 | 0.00 / 0 / rebounds 0.03 |
| T14 Steal / disruption gamble frequency | - | NEW fouls and foul trouble | habit (fixed) | 0.00 / 0 / no box change | 0.00 / 0 / personal_fouls 0.52 |
| T15 Help commitment | defensive effort 15% | - | habit (fixed) | 0.40 / 4 / rebounds 0.04 | 0.45 / 3 / points 0.02 |
| T16 Contest commitment / stay-down preference | - | blocks; NEW fouls (jump-contest share) | habit (fixed) | 0.00 / 0 / blocks 0.38 | 0.00 / 0 / blocks 0.37 |
| T17 Effort allocation | defensive effort 25% | - | habit (fixed) | 0.65 / 8 / points 0.04 | 0.59 / 5 / fga 0.04 |
| T18 Contact-seeking preference | - | points share, free throws | habit (fixed) | 0.89 / 10 / fta 3.25 | 1.41 / 25 / fta 3.28 |

**Every input either moves the game or has a documented reason:**
- **Moves the game now (new this pass):** foul control and steal gambling (fouls +0.57 / +0.52 per 36 for a +15 / x1.3 bump), contest technique and jump-contest habit (also fouls), pace habit (team pace: x1.3 on half the rotation players moves a team's points 4.0 a game), cutting habit (points share +0.35 per 36), shooting-mode habit and the three-point grades (points share).
- **No box-score effect, documented: strength and jump capacity.** Rebuilt from combine tests and in-game evidence, they add nothing to any box-score fit beyond the skills that already contain their effect (section 1); they now develop with age and show on the card. Where they should matter: the possession engine and draft prospects without an NBA record.
- **Small but real:** box-out vs pursue habit (rebound share +0.03 per 36; no team effect found), screen setting and defensive-rebounding skills (box score only, plus development now).
- Every other input moves the box score or team strength as in the first pass.

## Scorecards

{SCORECARDS}

## Speed

The full 1,230-game replay ran in 15.8 s after vs 15.7 s before (a few look-ups per player per game; the foul draws are per player either way), so a simulated month is unchanged within noise.

## Value formula

`impact_value.py` was not touched. It reads skill groups and involvement, not strength, jumping or the habits wired in here, so player values do not move from the inputs change. Development of the defensive-rebounding, steal and foul-control skills now feeds its rebounding and defence groups over a career (it already read their values).

## Files

- `src/nba_gm_data/physical_evidence.py` (new), `scripts/research/draft_combine.py` (new), `data/research/draft_combine_2000_2025.json` (new, public NBA.com combine data), `scripts/build_player_inputs.py` (calls the new evidence), `data/canonical/player_inputs_2026_27.json.gz` (strength and jumping only).
- `src/nba_gm_data/box_rates.py` (fouls fit, points fit with shooting mode and cutting, `S.three_mode`), `sim.py` (foul rates, pace habit, rebound draw, expected points for the shooting line), `offense.py` (`night_three_pct`), `box_variation.py` (miss-fill claim), `game_minutes.py` (per-player foul rates), `ratings_model.py` (development routing).
- `save.py` (`STAT_FIELDS` gains `screen_assists`), `app_actions.py` (season block), `gui/app.js` (box score, season line, playoff table, league leaders).
- `scripts/fit_box_stat_rates.py` (points spec), `tests/test_unused_ratings_2.py` (new, 11 tests), `tests/playoff_stats_table.test.cjs` (new column).
- Not touched: draft code, trade code, the value formula, the experimental possession engine, any skill or habit rating.

## Tests

- New `tests/test_unused_ratings_2.py` (11 tests): foul rate follows foul control and gambling; replayed fouls follow each player's rate with rare foul-outs; foul-prone players lose more minutes to foul trouble; the pace term is game-level, symmetric and bounded; the shooting-mode grade lies between the three-point grades; the night made-three chance keeps the season percentage and the capped expectation; a pure shooter's made threes track his percentage; the newly routed inputs develop exactly like the skill they follow; jump capacity moves in cm; the aging curve grows young and declines old; combine matching needs a plausible year.
- Focused modules (box score, box variation, coaching effects, game minutes, ratings model, first-pass unused ratings, fatigue, development coverage, input caches, player profile, rotation calibration, inputs build, prospect development, rating scale, user rotation): all pass except one check that needs a reference file from main's ignored `output/` folder (`test_rating_scale_consistency`, environment only).
- Core suite (`scripts/run_core_tests.sh`): **337 OK** (2 skips).
- JS (`tests/*.test.cjs`, 30 files): all pass except `startup_video.test.cjs`, which needs a startup video not present in a fresh worktree (environment only). `playoff_stats_table.test.cjs` updated for the new column.
