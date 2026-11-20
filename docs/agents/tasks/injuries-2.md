# Injuries 2: real opening night, and injury lengths counted the way the source counts them (INJURIES-2, 2026-11-20)

Plan: `docs/agents/tasks/injuries-2-plan.md`. Branch: `worktree-agent-a45df998af62440a4`.

## TL;DR
- A new career now opens with the 65 players who were really out on the 2026-27 opening night (why, and for how many games), and nobody else; later seasons keep the random model.
- The game was misreading how Basketball Index counts days out (two days per missed game, from the first missed game), so short injuries often cost no game; fixed, and injuries now come in the real mix of lengths.
- Heavy-minute players now miss 2-10 game stretches about as often as real players (5.3 games a season, real 5.6; was 4.0); the 30 best players still play a few more games than real.

## 1. Real opening-night injuries for new careers

**What the game does now.** `create_league_save` applies `data/canonical/opening_night_injuries_2026_27.json` instead of the random season-start draws (`health.opening_night_injuries`, `save.apply_opening_night_injuries`). Each listed player, matched by id and on the same team, misses exactly his real number of his team's games in the save's own schedule (the whole season when it ran that long). Nobody else starts hurt. Rollovers still draw the random offseason injuries as before. If a later list is ever missing for the season, the old random draws are used.

**The list** (`scripts/research/opening_night_injuries.py --capture 2026-11-20 --write`):
- 226 final games from opening night (Oct 20) to Nov 19, and 30 official NBA injury reports (each game day's 9:30 PM report).
- 68 players were out injured on their team's opening night; **65 applied**, 3 skipped and recorded in the save:
  - Tacko Fall (PHI) and Khalifa Diop (CLE) are not in the game's 2026-27 player pool;
  - Tony Bradley played for Utah but is on the Knicks in the game's rosters.
- Kept apart, never applied: 15 G League two-way assignments, 1 personal reason, 1 not with team, and 6 players listed "available" who didn't play (coach's decisions).
- Lengths: 11 players missed 1 game, 11 missed 2-5, 12 missed 6-10, 16 missed 11-20 and 15 missed 21 or more (1,154 games in all). By body part: knee 18, foot 8, hamstring 8, ankle 7, calf 6, back 5, Achilles 4, shoulder 3, illness 3, then hip, thumb and head 1 each.
- Notable: Jimmy Butler (ACL, 33 games), Donte DiVincenzo (Achilles, 75), Shaedon Sharpe (meniscus surgery, 60), Mark Williams (shoulder surgery, 47), Tobias Harris (calf, 23), Bradley Beal (knee, 19), Jusuf Nurkic (foot, 19), Dereck Lively II (foot surgery, 18), Brandon Ingram (heel surgery, 15), Jonathan Isaac (knee, 15), T.J. McConnell (9), Kon Knueppel (8), Nic Claxton (8), Coby White (7), Max Strus (6). Ariel Hukporti and Henri Veesaar are out for the season. Tatum and Haliburton played on opening night, so they start healthy.
- 29 applied players had still not played by Nov 20. Their totals use ESPN's estimated return date (26), ESPN's "out for the season" note (2), or, for Ben Simmons (torn Achilles, no published date), the median real Achilles absence at least as long as his so far (80 games).
- Each record carries its sources with dates: the official report (status and reason), the opener box score, the first-game-back box score, and ESPN's injury report for players still out.

**How "out" and "games missed" are decided.**
- Out = didn't play in his team's first game *and* was on that day's official report with an "Injury/Illness" reason.
- Games missed = his team's games from the opener to the last game he missed while listed with an injury, before his first game played. A healthy scratch after the injury is not counted.
- An injury from his real record within 400 days before opening night (last season's surgery, say) keeps its real date, so his injury history isn't counted twice.

**Sources** (plain HTTP, small delays, no personal data in requests; raw responses cached in `output/injuries-2/`):
- NBA official injury reports: `https://ak-static.cms.nba.com/referee/injury/Injury-Report_YYYY-MM-DD_09_30PM.pdf` (Oct 20 - Nov 19, 2026). I parsed them with the standard library; no packages added.
- ESPN scoreboard and game summaries (`site.api.espn.com/.../nba/scoreboard?dates=`, `.../summary?event=`), fetched 2026-11-20.
- ESPN injury report (`.../nba/injuries`) and team schedules (`.../teams/{id}/schedule`), fetched 2026-11-20.
- ESPN's box scores list almost no injured players (Steven Adams was the only one on opening night), so the official report is the reason source.

## 2. Injury kinds and lengths against real

### What I measured first (current main, two full seasons, seeds 17 and 29)
`scripts/research/injury_lengths.py` (new), with fixed opening rosters and all 30 teams AI-coached:
- Simulated injuries were too long against Basketball Index's tracker. In games missed: 1 game 27-30% (BBI 40%), 11+ games 19-20% (BBI 14%).
- Heavy-minute players (30+ minutes) had too few 2-10 game stretches (3.8-4.2 games a season, real 5.6) and too many 11+ (5.0-6.5, real 4.0).
- A third of simulated injuries cost no game at all (BBI: 23%).

### Three causes, each with its own evidence
1. **Days out are Basketball Index's own unit: two days per missed game.**
   - In the tracker, games missed = days // 2 in 5,967 of 5,987 entries with a logged return: 2 days is 1 game, 8 is 4, 30 is 15, 90 is 45, and 0-1 days is no game.
   - Days count from the first game missed: of the 260 2025-26 absences that start on a team game day, 258 start on a game he did not play.
   - The game read the days as calendar days from the injury game, so most 2-3 day absences ended before the next game.
   - **Fix** (`health.injury_return_date`): a drawn absence is days // 2 of his team's games, starting with the next game. Past the end of the known schedule (playoffs, offseason) each remaining game counts as two days.
   - The expected-games figures behind the player card's body map and the AI's injury-risk score now use the same conversion (`injury_model._mean_games_out`), so what's shown matches what the sim uses.
2. **Recovery times now come from records since 2015** (`scripts/build_injury_model.py`, `RECOVERY_FIRST_YEAR = 2015`), the same seasons the injury-rate models are fitted on.
   - Older records describe a different reporting world. Median return: 28 days in 2000-05 (the injured list then had a 5-game minimum, and half the records have no logged return), 10 days in 2006-14, 5 in 2015-20, 4 in 2021-26.
   - Even with older records weighted down, the pool's long tail was too heavy against the tracker's 2021-25 absences: 90th percentile 45 days against 28.
   - Only the recovery tables changed in the rebuild; injury rates and every other part of `injury_model_v2.json` are byte-identical.
   - Changes by body part (25th/50th/75th/90th percentile days):
     - knee 2/6/21/71 → 2/4/14/56;
     - foot 2/7/23/71 → 2/5/17/54;
     - ankle 2/6/14/37 → 2/5/12/31;
     - back 2/4/11/35 → 2/3/9/25;
     - Achilles 2/6/19/118 → 2/4/13/212 (modern records hold the ruptures rather than minor flare-ups).
3. **League injury rate 1.35 → 1.52** (`injury_model.LEAGUE_RATE_SCALE`).
   - The tracker logs four to eight times more entries a season in 2021-25 than in 2015-17, so a fit pooled over all those seasons has a low base rate.
   - Run on the same 2021-25 player-seasons (their real ages, bodies, minutes and histories), the fitted model predicts 1 recorded injury for every 1.52 the tracker logged: 1.56 for players at 20+ minutes, 1.37-1.71 across minutes bands (`output/injuries-2/workload_check.py`).
   - The old 1.35 had been set from the low end of the tracker's range while a third of injuries were still costing no game.

**Follow-on recalibration: coach rest 1.02 → 0.78** (`rest_model.REST_COACH_SHARE`).
- This constant exists to subtract the injury model's one-game absences from the rest rates fitted to real single-game absences (which include one-game injuries).
- With one-game injuries now at Basketball Index's share, regulars' single-game absences would have risen from 4.0% to 4.6% (real 3.8%). At 0.78 they are back where they were: 3.97 / 4.01% (before 3.99 / 4.05%).

### Before and after (seeds 17 / 29; "before" is current main)

**Length bands, every injury in the sim against the tracker** (share of injuries by games missed; the sim counts games on each team's schedule):

| | 1 | 2-5 | 6-10 | 11-20 | 21+ | Injuries per team | Still out at the last game |
|---|---|---|---|---|---|---|---|
| Basketball Index 2021-25 | 40% | 35% | 11% | 7% | 6.5% | 30-37 (35-43 with illness)* | 5.4-7.6%* |
| Before | 30 / 27% | 37 / 41% | 13 / 13% | 12 / 10% | 8 / 9% | 24.0 / 25.4 | 11.0 / 10.6% |
| After | 39 / 39% | 35 / 35% | 12 / 12% | 7.5 / 6.6% | 5.7 / 7.2% | 34.7 / 35.5 | 8.9 / 8.6% |

\*Spells per team and the season-end share are from the injuries-vs-Basketball Index report (`inj-injuries-vs-bbi.md`; 2023-24 and 2024-25). The tracker's own player panel has 24 a team.

**By body part** (after, share of injuries 1 / 2-5 / 6-10 / 11-20 / 21+ games; Basketball Index in brackets):
- ankle/foot/toe: 35/39/12/7/7 [36/34/14/8/7]
- knee: 40/30/13/7/11 [40/37/8/6/10]
- thigh: 37/33/19/7/4 [36/36/15/8/5]
- calf/Achilles: 31/38/13/11/10 [38/36/13/6/6]
- hip/groin: 37/39/17/6/3 [34/41/15/6/4]
- back: 47/35/7/8/5 [44/36/8/7/5]
- arm/hand: 29/36/14/13/10 [37/28/10/14/11]
- head: 26/55/12/2/5 [23/57/12/4/4]
- illness: 67/29/3/0/2 [64/32/2/1/1]

The body-part mix matches as well: for example, ankle/foot/toe is 26-27% of injuries in both.

**Injuries per 82 games played, by minutes** (absences of 1+ games; Basketball Index 2021-25 tracker in brackets):

| Minutes | Before | After | BBI |
|---|---|---|---|
| 30+ | 2.6 / 2.7 | 3.6 / 3.7 | 3.7 |
| 20-30 | 2.3 / 2.5 | 3.2 / 3.4 | 2.9 |
| 10-20 | 1.8 / 1.7 | 2.5 / 2.6 | 2.2 |
| under 10 | 0.8 / 1.0 | 1.4 / 1.4 | 2.5 (small sample) |

**Games played: heavy-minute players (30+ minutes), missed games a season by where they happen** (the TV-rest report's measure; real 2025-26 box scores):

| | Real | Before | After |
|---|---|---|---|
| Single games (rest and one-game injuries) | 2.4 | 3.0 / 2.6 | 2.7 / 2.8 |
| 2-10 game stretches | 5.6 | 3.8 / 4.2 | 4.9 / 5.6 |
| 11+ game stretches | 4.0 | 6.5 / 5.0 | 6.1 / 4.6 |
| Absences of 2+ games per 82 played | 2.25 | 1.73 / 1.70 | 2.10 / 1.94 |
| Median games played | 68 | 68.5 / 67 | 66.5 / 67 |
| Season start, per player | 3.95 | 0.18 / 2.61 | 0.77 / 0.54 (real 2026-27 list) |

**The 30 best-rated players:**

| | Real 2025-26 | Before | After |
|---|---|---|---|
| Median / mean games | 64.5 / 55.4 | 68 / 66.3, 68 / 59.9 | 70 / 67.6, 67 / 59.9 |
| Missed in 2-10 game stretches | 7.0 | 3.7 / 3.6 | 4.2 / 4.3 |
| Missed in 11+ game stretches | 6.8 | 5.3 / 6.4 | 3.3 / 4.3 |
| Missed at the season start | 3.3 | 0.2 / 4.8 (random) | 1.1 (real 2026-27 list) |

The top-30 median is still 2.5-5.5 games high. Thirty players is a small sample, and the real 2025-26 top 30 had an unusually injured year: Haliburton missed the whole season and Tatum 62 games from opening night. Heavy-minute players as a group (about 75 a season) now match real games played. I did not tune anything toward the top-30 number.

## Speed
- Health simulation alone (a full regular season, fixed rosters): 0.37-0.47 s per simulated month, against 0.37-0.38 before. The difference is within the noise of a shared machine.
- Full headless season: 51.7-54.8 s wall and 31.4-31.7 s of game simulation, against 48.5-49.1 s and 29.3-29.6 s before.
  - That is about +2 s of simulation a season, roughly +0.35 s per simulated month.
  - It comes from 40% more injuries: more in-game exits and more reserve minutes.
- New career: the opening-night list takes a few milliseconds.

## Tests and scorecard
- New `tests/test_injuries_2.py` (11):
  - the list's shape and sources;
  - the official-report reader (a synthetic PDF) and reason rules;
  - the new career applies the list exactly (return date = the team's Nth game; diagnosis and part; the 3 skips recorded);
  - nobody else starts hurt, and Tatum and Haliburton are active;
  - no list for 2027-28 (the random model stays, and the rollover call is unchanged);
  - two days per game from the next game, including past the schedule's end;
  - drawn injuries use the team schedule;
  - the length-band and event-view measures;
  - expected games use the same conversion.
- `tests/test_new_career_start.py`: the startup-health test now expects the opening-night list's source id.
- Focused modules: 128 tests OK. They are `test_injury_model`, `test_overnight_tv_rest`, `test_fatigue_rest`, `test_smart_rest`, `test_new_career_start`, `test_injury_rest`, `test_injuries_2`, `test_long_term_health`, `test_background_league_health`, `test_prospect_injury_report`, `test_absence_fill` and `test_game_minutes`.
- Core `scripts/run_core_tests.sh`: 337 run, OK (2 skipped).
- `tests.test_foundation`: 215 run. Two tests needed updating, and both now pass on a rerun:
  - The health replay's evidence range (injuries per team) goes from 24-46 to 24-52. That replay exposes every 4+ minute player all season with no rest nights, and it counts injuries that cost no game, so it now gives 46.5. Full seasons give 35 a team that cost a game (Basketball Index 30-37, 35-43 with illness). The days-out percentile checks are unchanged and pass.
  - A narrative fixture has Ingram playing 6 of 6 games, but he now opens the career injured (his real heel surgery). The fixture now marks him healthy.
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**.
- Not run: the betting test. It replays real games with real availability.

## Determinism
Everything stays seeded, and no RNG stream changed: the same draws happen in the same order. What changes is what a draw means:
- return dates now count the team's games;
- more draws come up injuries (rate 1.52);
- rest nights are a little rarer;
- recovery days come from the newer pool.

Generated seasons therefore differ from main. A new career's opening injuries no longer depend on the seed.

## What's left
1. **The 30 best players' median games** is still above real (67-70 against 64.5), as discussed above. One next step backed by the evidence: the injury-rate fit pools seasons whose tracker coverage differs four- to eightfold. A refit with a separate base rate per season would fix the workload and age slopes at the source. The rate by minutes band is still uneven after the uniform 1.52: the 20-30 minute group is 10-15% above the tracker, players under 10 minutes are below it. That is a bigger change (all hazards, the AI risk scores and the body map), so I left it for its own task.
2. **Too many single-game absences for heavy-minute players** (2.7-2.8 a season against 2.4 real), while regulars overall match (4.0% against 3.8%). This is the rest model's split by minutes, not injuries.
3. **The injury label "~Ng"** in Minutes + Availability still estimates games left as calendar days / 2.4 (`save.py` display, outside this task's files). Counting the team's remaining games before the return date would match the engine exactly.
4. **Fantasy-draft careers** apply the list before the draft. Injured players keep their real return dates on whatever team drafts them.
5. **Optional follow-ups not done** (time): `transactions.player_health_risk` still reads the legacy fields (blocked while trade files are owned); no body-part history view on the player card.
6. **Refreshing the list:** rerun `opening_night_injuries.py --capture <date> --write`. Players still out keep moving toward their real totals.

## Files
- New:
  - `data/canonical/opening_night_injuries_2026_27.json`;
  - `scripts/research/opening_night_injuries.py` and `scripts/research/injury_lengths.py`;
  - `tests/test_injuries_2.py`.
- Changed:
  - `health.py`: opening-night list, two-days-per-game return dates, team schedule lookup;
  - `injury_model.py`: rate 1.52, expected games conversion, comment;
  - `rest_model.py`: rest calibration 0.78;
  - `save.py`: new-career hook and `apply_opening_night_injuries`;
  - `scripts/build_injury_model.py`: recovery pools since 2015;
  - `data/canonical/injury_model_v2.json`: rebuilt by its script; only the recovery tables changed;
  - `tests/test_new_career_start.py` and `tests/test_foundation.py` (two tests, see above).
- Harness (git-ignored, `output/injuries-2/`):
  - `sim_season.py LABEL --seed N [--random-start]`;
  - `heavy_runs.py`, `heavy_events.py`, `top30_split.py`, `compare_smart.py`, `singles.py`;
  - `workload_check.py`, `days_games_map.py`, `tracker_start_check.py`, `obs_by_era.py`, `pool_vs_tracker.py`;
  - `health_speed.py`, `new_save_check.py`;
  - runs `base_s17/29` (before) and `final_s17/29` (after).
  - The coordinator should copy `output/injuries-2/` to main's `output/` before removing the worktree.

## Resume state
Done: committed on the branch, board row set to review. Nothing pushed or merged.
