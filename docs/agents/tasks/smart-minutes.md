# Smart minutes: who plays when someone is out, and how hard each coach rides his stars

## TL;DR

- When a player is out, the coach now decides who replaces him: like-for-like backups first (a center for a center, a point guard for a point guard), the other starters a little more (about 1.2-1.5 minutes each, as in real games), more when the backup is thin, and a call-up from the end of the bench when needed. Against a big front line or a guard-led team, the fill-in minutes lean toward size or toward guards.
- Each head coach now has a "star workload" trait, measured from real coaches (Nick Nurse rides his stars, about +2.8 minutes; Steve Kerr, Taylor Jenkins and Brian Keefe limit them, about -2 to -2.7). It sets his two best players' planned minutes and is shown on the coach card.
- Season shape now matches real 2025-26: 63-69 players at 30+ minutes (real 70), 14-19 at 34+ (18), 2-4 at 36+ (3, was 0-2). The top end is still about 36.5 (real 38). Both scorecards unchanged (18/18; Brier 0.1941, log loss 0.5744).

## What the real games show

From the 1,235 real 2025-26 regular-season box scores (`output/smart-minutes/fill_analysis.py`, `real_fill.json`). A "one-out" game is a game where exactly one of a team's five regular starters was unavailable (693 games). "Healthy minutes" are each player's average in that team's full-strength games, counting a dressed-but-unused game as zero. The average starter who sat had 28.5 healthy minutes.

Average change per available player:

| Who | Real change (minutes) | Share of the missing minutes |
|---|---:|---:|
| Each other starter | +1.5 | 19% |
| The main backup at the same position | +4.7 | 10% |
| Other bench players at the same position | +4.2 each | 10% |
| Bench players one position away (for example a power forward when the center sits) | +2.9 each | 23% |
| Other bench players | +1.6 each | 19% |
| Players who don't play at full strength (end of the bench) | +7.7 each | 19% |

- **It depends on the position.** A missing point guard's backups gain the most (main backup +8.5, other point guards +7.4) and the other starters only +0.9; a missing center works the same way (+5.9 and +7.6). On the wings (shooting guard to power forward) positions blur: the starters gain +1.8-1.9 and the like-for-like backup has no special claim.
- **Depth matters.** With a solid backup (16+ healthy minutes) he gains +3.3 and the other starters +1.1. With a thin backup (8-16) he gains +6.7 and the starters +2.1; with none the starters gain +1.7.
- **Quality matters.** When two or more bench players share the position, the better-rated one gains +5.8 and the others +3.6.
- **Who starts in his place.** The main same-position backup started 38% of the time he played. Of the replacement starters, 20% were that backup, 29% a player one position away and 45% a player two or more positions away (often a sixth man).
- **Two starters out** (320 games): each other starter +2.25 (not double the one-out +1.5), and somebody passed 42 minutes in only 4 games.

## The rule in plain words

`src/nba_gm_data/absence_fill.py`. When a player is out, his healthy minutes belong to the spot he plays (point guard through center; a player who slides between spots spreads them). The coach hands those minutes out in two parts:

1. **The other starters take a modest share**: 14% of the minutes with a solid backup at that spot, up to 22% when there is no backup. The share is split among the remaining starters, more to those who play fewer minutes and to those who fit the spot. With several starters out, each absence's share is smaller (divided by the number of starters out to the power 0.75), because the coach goes deeper instead of riding three starters to 40.
2. **The bench takes the rest.** Each bench player's claim is his fit at that spot (position, height and the skills the starting-lineup scoring already uses: handling and passing at the point, shooting and defense on the wing, rebounding and rim protection up front), times the coach's value of him (his overall rating against the team's average), times his role: a player who already plays a lot can stretch only so far, and a player outside the rotation is the last resort; the coach calls up at most two of those. Part of each spot's minutes is position-free: 11% at point guard and center (specialist jobs) and 54% on the wings. That is how a team with no real backup center goes smaller (its power forwards take the most), and how a big wing slides up.
3. **Small context on top**: a like-for-like role (ball handler for ball handler, rim protector for rim protector) adds a little; a rebuilding team leans toward its players 23 and under, and a team at its peak leans toward proven players; a star-riding coach leans a little more on his other starters.
4. **Limits.** Filling in never pushes a player past 39 minutes (or past his own healthy plan, if that is higher) unless the team cannot place the minutes any other way, and never past 42 (a team down to five players aside).
5. **In the game itself** (`sim.py`, generated games only), the fill-in minutes lean toward size against an unusually big, physical front line (offensive rebounding and rim protection) and toward guards and wings against a team built on creators. The lean moves at most 3 minutes for any player and never touches the healthy plan.

Every team still plays 240 minutes. The blowout rest and foul trouble from the earlier fix are unchanged.

**The user's team.** When the GM has set minutes, every healthy player keeps at least his target; only the minutes of unavailable players are placed, by the same coach decision, among the players the GM gave minutes to. A player the GM left at zero stays benched unless fewer than eight players with minutes are available. The minutes come out as whole numbers summing to 240. (Before, the missing minutes were handed out one at a time to the players with the biggest targets.) A GM who hasn't set minutes gets the same coach decision on the default plan.

**Fitted versus judgment.** Fitted to the real numbers above (`output/smart-minutes/fit_fill.py`): the starters' share and its depth boost, the position-free shares, how sharply a missing player's minutes stay at his own spot, the role curve and the value weight. The fit scores the rule on the game's own rosters (each AI team's five starters out in turn, with its healthy plan, both rating sets) and, at lower weight, on the real 2025-26 rosters. Judgment calls: role likeness (+20%; its best fit was zero), how much an adjacent position fits (the fit could not tell a sharp from a soft setting, so I kept a soft one so that a big wing can slide up), the at-most-two call-ups, the 39-minute soft cap, the team-phase factors, the star tilt and the opponent lean.

How the rule does on the game's rosters versus the real games (per player, minutes):

| Who | Real | Rule on the game's rosters |
|---|---:|---:|
| Each other starter | +1.5 | +1.3 |
| Main same-position backup | +4.7 | +4.2 |
| Other same-position bench | +4.2 | +4.6 |
| Bench one position away | +2.9 | +1.9 |
| Other bench | +1.6 | +1.3 |
| End of the bench (each) | +7.7 | +4.2 |
| Starters, solid / thin / no backup | +1.1 / +2.1 / +1.7 | +1.1 / +1.3 / +1.5 |
| Point guard out: main backup / starters | +8.5 / +0.9 | +6.5 / +1.3 |
| Better-rated vs other same-position backup | +5.8 / +3.6 | +5.9 / +4.5 |

The end-of-bench gap is deliberate: real "dressed but unused" players gain a lot on average partly because coaches pick the best of them, and letting a player who never plays outrank a bench player who plays a little made the backups look wrong.

## Coach star workload

Measured (`output/smart-minutes/coach_trait.py`, `coach_trait.json`) from 91 real team-seasons 2021-22 to 2025-26: the average minutes per game of each team's two biggest minute-getters (40+ games), minus that season's league average. Earlier seasons use the career stats of players still in the game, and a team-season counts only when those players cover 75% of its minutes. Each coach's average is shrunk toward zero by his number of seasons. Coaches really differ: the spread between coaches is about 1.7 minutes, and one season varies about 1.25 around a coach's norm.

| Rides stars | Minutes | Middle | Minutes | Limits stars | Minutes |
|---|---:|---|---:|---|---:|
| Nick Nurse | +2.8 | Billy Donovan | +0.5 | Mitch Johnson | -1.3 |
| JJ Redick | +1.7 | Tyronn Lue | +0.5 | Jordi Fernandez | -1.5 |
| David Adelman | +1.6 | Jamahl Mosley | +0.4 | Doug Christie | -1.6 |
| Ime Udoka | +1.4 | Darko Rajakovic | 0.0 | Rick Carlisle | -1.6 |
| Quin Snyder | +1.3 | Erik Spoelstra | -0.1 | Steve Kerr | -2.0 |
| Joe Mazzulla | +1.3 | Jordan Ott | -0.4 | Tuomas Iisalo | -2.1 |
| Mike Brown | +0.8 | Chauncey Billups | -0.4 | Taylor Jenkins | -2.3 |
| Chris Finch | +0.8 | Will Hardy | -0.4 | Brian Keefe | -2.7 |
| Jason Kidd | +0.7 | J.B. Bickerstaff | -0.5 | | |
| | | Charles Lee, Mark Daigneault, Kenny Atkinson | -0.9 to -1.0 | | |

Caveats: one-season coaches (Redick, Adelman, Ott, Iisalo, Keefe) are mostly shrinkage; part of Keefe's and Iisalo's low numbers is their teams' situation (young, rebuilding rosters). Coaches not in the table (generated or market hires) draw from the measured spread (standard deviation 1.66 minutes, capped at ±3.5), fixed per person.

**In the engine.** The healthy plan for an average coach is now 36 / 33.2 / 31.5 / 30 / 28 / 26 / 21 / 16.3 / 10 / 5 / 2 / 1 minutes by rotation rank. A coach's trait moves his top two players by 1.25 x the trait and his third by half that, and the next three rotation players give the minutes back (`save.star_workload_curve`). The 1.25 makes up for the plan being blended with last season's minutes before it is used; with it, each trait minute moves a team's top-two minutes by about 1.0 over a season (measured in the four seasons below). Team-to-team spread of top-two minutes went from 0.9-1.0 to 1.6-1.8 (real 1.9). I also moved 2.3 minutes from the top three ranks to ranks 6-8: the old top (37/34/32) was set while missing players' minutes went almost all to the bench, and with the real share now going to the other starters, it put 21-27 players at 34+ (real 18).

**Shown to the user.** On the coach card, under Working Style: "Star workload", on the 0-100 scale (50 = average coach, 12 points = one minute), with a tooltip in plain words, for example "Limits his stars' minutes: plans about 2.0 fewer minutes a game for each of his two best players than an average coach." The head coach's effect list (staff page and contract window) has the same row. Both read the same value the engine uses (`staff.coach_star_workload`); it does not change the staff grade.

## Before and after (full seasons, all 30 teams AI-coached, injuries on, opening rosters)

"Before" is the merged heavy-minutes engine (`main` at `fccaac0`).

| | Real 2025-26 | Before (4 seasons) | After (4 seasons) |
|---|---:|---|---|
| Players at 30+ mpg (40+ games) | 70 | 64 / 67 / 68 / 70 | 63 / 63 / 68 / 69 |
| Players at 34+ | 18 | 13 / 15 / 14 / 20 | 14 / 18 / 16 / 19 |
| Players at 36+ | 3 | 0 / 2 / 0 / 0 | 2 / 3 / 2 / 4 |
| Most minutes per game | 38.0 | 35.3 / 36.0 / 35.7 / 35.9 | 36.3 / 36.5 / 36.7 / 36.2 |
| Top-30 average | 34.6 | 33.7 / 34.1 / 33.9 / 34.3 | 34.1 / 34.3 / 34.2 / 34.4 |
| Regulars' season average | 31.7 | 31.0-31.4 | 31.1-31.2 |

(Order: 94-input seeds 17 and 29, then older ratings seeds 17 and 29.)

Fill-in when one starter is out (per available player, minutes):

| Who | Real | Before | After |
|---|---:|---|---|
| Each other starter | +1.5 | +0.6 / +1.0 / +0.9 / +1.1 | +1.2 / +1.4 / +1.4 / +1.5 |
| Main same-position backup | +4.7 | +3.6 / +3.9 / +4.3 / +4.0 | +4.4 / +4.4 / +5.9 / +5.5 |
| Other same-position bench | +4.2 | +1.9 / +1.0 / +2.4 / +1.8 | +4.7 / +4.5 / +5.5 / +4.9 |
| Bench one position away | +2.9 | +2.5 / +2.6 / +2.5 / +2.5 | +1.3 / +1.6 / +1.3 / +1.2 |
| Other bench | +1.6 | +2.6 / +2.8 / +2.9 / +2.7 | +0.9 / +1.0 / +0.9 / +1.1 |
| Point guard out: main backup | +8.5 | +3.2 / +4.2 / +3.2 / +3.9 | +5.5 / +6.8 / +7.3 / +7.8 |
| Center out: main backup | +5.9 | +5.3 / +4.3 / +4.6 / +3.2 | +6.7 / +5.8 / +8.0 / +8.0 |
| Starters with no backup / solid backup | +1.7 / +1.1 | +0.6-1.3 / +0.7-1.0 | +1.4-1.9 / +0.8-1.1 |
| Two starters out: each other starter | +2.25 | +0.9 / +1.9 / +1.9 / +1.6 | +1.5 / +2.4 / +2.3 / +2.2 |
| Two starters out: games with someone past 42 | 4 of 320 | 1-4 | 3-9 |

(Here "real" counts are per season; the simulated seasons have somewhat fewer one-out and two-out games.) Who starts in the missing starter's place now looks like real: the like-for-like backup 14-21% (real 20%), a player one position away 30-35% (29%), farther away 45-49% (45%).

Remaining gaps: bench players one position away gain less than real (+1.3 vs +2.9) and same-position bench a bit more; end-of-bench players gain less on average (by design, above); point guard backups gain somewhat less than real.

## Five cases from the game (94-input ratings, opening rosters)

From `output/smart-minutes/demo.py`; full tables in `output/smart-minutes/cases/`. "Healthy" is the AI coach's plan with everyone available, "out" the plan that day, "game" one game against the named opponent.

1. **Starting center out: Minnesota without Rudy Gobert (28 minutes).** Minnesota has no real backup center in this roster, so the minutes go to its three young centers: Rocco Zikarsky 4 -> 10.4, Drew Timme 0 -> 6.5 and Joan Beringer 0 -> 5.6 (both called up). Because the backup is thin, the starters take more than usual: Edwards +1.5, Ball +1.5, McDaniels +1.9, DiVincenzo +1.1. Against Houston (about average size) the game plan barely changes; against the Lakers (built on creators) a few of the centers' minutes shift to the guards (Zikarsky 10.4 -> 9.1, Edwards 37.5 -> 38.1).
2. **Point guard out: New York without Jalen Brunson (34).** The point guards take the job: Jose Alvarado 19 -> 24.8, and Tyler Kolek, unused at full strength, is called up for 10.8; Jaden Akins (a ball handler) +3.8. The starters get +0.9 to +1.7 each; Miles McBride, already at 24, +1.1.
3. **Star wing out: Boston without Jayson Tatum (29).** On the wing positions blur, so the minutes spread: Paul George +3.1, the wing bench (Walsh +3.9, Scheierman +1.3, two call-ups about +4 each), the other starters +1.0 to +1.4, and the big men a little (Robinson +3.0, Garza +2.7). Nobody passes 37.4.
4. **Two starters out: New York without Brunson and Karl-Anthony Towns (64).** The center job goes to Andre Drummond 6 -> 18.7 and Drew Eubanks (called up, 12.2); the point guard job to Alvarado 19 -> 25.6 and Kolek 12.3. The other starters gain +1.6 to +2.6 each, less per missing starter than in case 2.
5. **Short-handed: Boston without White, Tatum, George, Queta and Hauser (147).** The rotation goes 12 deep. Mitchell Robinson becomes the starting center (11 -> 30.7), Luka Garza 22.5, Payton Pritchard tops out at 39.0, and four end-of-bench players get real minutes (Milos Uzan 24.1, Hayden Gray 18.1). Against guard-led New York the plan shades toward the guards, at most 3 minutes per player.

## Scorecards

- Real-minutes replay, 94-input (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**. Replay games don't use the coach's plan.
- Betting-odds test, 94-input, 100 runs (`validate-season-probabilities`): **Brier 0.1941, log loss 0.5744**, spread error 4.546, totals error 5.465 (1,231 games, 1,018 with market odds). Identical to before: these games use real minutes, not the coach's plan.

## Speed

The coach decision runs only for teams with someone out, on numbers already computed for the plan. Full-season wall time was 38-44 s after versus 39-50 s before on a loaded machine; game-sim CPU 25.9-26.9 s versus 26.8-29.2 s. No measurable cost per simulated month.

## Tests

- New `tests/test_absence_fill.py` (16): like-for-like backups take the spot, starters' gain, thin depth (the team goes smaller), better backup gets more, call-up limit, short-handed team under 42, two starters out, star workload (plan curve, real coaches, generated coaches, what the card shows equals what the engine uses, grade unchanged), rebuilding team, opponent lean (moves only fill-in minutes, total unchanged), and the user's targets (kept, benched player stays benched, backup center takes the spot).
- `tests/test_game_minutes.py`: the old bench-first share tests were removed (that function is gone). `tests/test_ai_roles.py`: reads the plan curve from the code.
- Rotation, coach, staff and box modules (`test_absence_fill`, `test_game_minutes`, `test_ai_roles`, `test_rotation_profile_calibration`, `test_coaching_effects`, `test_box_star_stats`, `test_box_variation`, `test_rotation_comparison_*`, `test_narrative_simulation`, `test_forward_tuning`, `test_calibration_targets`, `test_staff_lifecycle`, `test_user_rotation_roster`, `test_deadline_speed_exact`): 122 OK.
- Core suite `scripts/run_core_tests.sh`: 337 run, OK (2 skipped).
- The staff, coach and rotation tests in `test_foundation` (25): OK. The full suite was not run (other agents were using the machine).

## What's left

1. **Top end still a bit low**: most minutes about 36.5 (real 38). The 36+ count is right; the remaining gap is the in-game rest (blowouts, foul trouble) taking about 1.5 minutes off a 38-minute plan, which real stars also lose. Raising it further would push the 36+ count past real.
2. **Bench players one position away** gain about half of what they do in real games; the rule moves those minutes to same-position bench players instead.
3. **The healthy plan.** Some AI plans look odd before any absence (for example Denver gives Jonas Valanciunas 3 minutes and Marvin Bagley 12), which the fill-in then inherits. That belongs to the role builder.
4. **Coach data.** Staff data lists Jamahl Mosley as head coach of both Orlando and New Orleans, and Taylor Jenkins at Milwaukee (his measured value comes from Memphis). Real coaches' traits come from the table above, so a real coach who changes teams keeps his trait.
5. **Opponent lean** uses two simple team measures (front-line rebounding and rim protection versus shot creation); it is a judgment call and only shades minutes.

## Files

- New: `src/nba_gm_data/absence_fill.py`, `tests/test_absence_fill.py`.
- Changed: `save.py` (`fill_vacated_minutes`, `user_override_coach_fill`, `team_rotation_projection`, `apply_save_rotation_projection`, `star_workload_curve`, `team_head_coach`, real coaches get their trait in `align_real_head_coach_names`; removed `spread_vacated_minutes`), `sim.py` (opponent lean hook, generated games only), `staff.py` (trait table, `coach_star_workload`, effect row), `coach_cards.py` (card trait and tooltip), tests.
- Harness (git-ignored): `output/smart-minutes/` (`fill_analysis.py`, `fit_fill.py`, `synth_cases.py`, `coach_trait.py`, `sim_season.py`, `run4.sh`, `cmp_fill.py`, `demo.py`, `top_list.py`, `coach_effect_sim.py`, tables `table_base.txt` and `table_v9.txt`).

## Resume state

- Done: research, rule, trait, display, four-season before/after (`table_base.txt`, `table_v9.txt`), cases, calibration 18/18, odds test identical, focused tests, core suite. Committed on the worktree branch (not pushed or merged). Ready for coordinator review.
- Not checked in the running app (GUI coach card and a user-team month with someone injured); covered by unit tests only.
