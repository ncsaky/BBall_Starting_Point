# Injury follow-ups

## TL;DR

- Minutes + Availability counts the team's scheduled games before a player's return.
- Players injured on opening night miss the same number of games for the team that drafts them.
- The new injury rates brought deep reserves closer to real rates. Players who play 20–30 minutes still get hurt too often, and the 30 best players still play a few games more than real.

## What changed

- The Minutes + Availability countdown uses the team's unplayed games from its regular-season schedule. It includes today's game if pending and excludes the return date, when the player is eligible to play. It updates in the live rotation feed as well. The countdown covers the games already on the regular-season schedule.
- At fantasy-draft completion, the game recalculates each drafted player's opening-night return date using the recorded games missed and his new team's schedule. The event and health state get the same date. Season-ending injuries still run through the end of the season. Undrafted players have no team schedule on which to count their games.
- The builder fits a separate starting rate for each season and body part. A player's minutes and age now affect the fit through comparisons with players in the same season. The tracker recorded 168 entries in 2015–16 and 660–1,340 a season in 2021–25. Earlier seasons still inform the slopes.
- For gameplay, the builder sets each body part's base rate from the tracker totals in 2021–22 through 2024–25, using the same discount for past injuries as the engine. This replaces the single 1.52 multiplier. The fit includes 2,621 player-seasons and 152,536 games played. It uses the tracker's injury counts and games played as exposure.
- The ankle and knee workload slopes fell by about one-sixth, while the back and hamstring slopes rose slightly. At typical age, the age slope weakened for back and hamstring injuries and became more negative for ankles and hips. The aggregate match to the 2021–25 counts is by construction. The two simulated seasons check how those rates translate into gameplay.

## Injury rates by minutes and age

New and old models each ran a 1,230-game regular season at seeds 17 and 29, with the same opening-night list, fixed rosters and AI coaches. Rates below count injury or illness spells that cost one or more games during the season, per 82 games actually played. Groups require at least 10 games played. The tracker estimates minutes from on-court possessions. Its age table uses players whose birth dates could be matched to the game's data.

| Minutes per game | Tracker 2021–25 | Before 17 / 29 | After 17 / 29 |
|---|---:|---:|---:|
| Under 10 | 2.47 | 1.39 / 1.36 | 1.56 / 1.48 |
| 10 to under 20 | 2.13 | 2.54 / 2.57 | 2.63 / 2.66 |
| 20 to under 30 | 2.85 | 3.22 / 3.40 | 3.17 / 3.36 |
| 30+ | 3.67 | 3.62 / 3.72 | 3.53 / 3.70 |

| Age | Tracker 2021–25 | Before 17 / 29 | After 17 / 29 |
|---|---:|---:|---:|
| Under 23 | 2.46 | 2.26 / 2.41 | 2.42 / 2.61 |
| 23–25 | 2.75 | 2.29 / 2.34 | 2.33 / 2.37 |
| 26–28 | 3.26 | 2.95 / 3.14 | 3.01 / 3.15 |
| 29–31 | 3.55 | 2.97 / 3.13 | 2.82 / 3.09 |
| 32+ | 3.61 | 2.70 / 2.66 | 2.68 / 2.61 |

The reserve gap narrowed by about 0.15 injuries per 82 played. The 20–30 minute group's surplus narrowed by about 0.05 and still ranges from 11% to 18%. On the tracker's own player-seasons, the fitted rate for all entries at 0–15 minutes increased from 2.93 to 3.07 per 82 against 2.76 observed. The low under-10 rate in the sim persists even as the model predicts more entries when given real exposure. The sim's injury draw requires at least four projected minutes. About half of the under-10 group's appearances had a plan below four minutes after the health pass (49% and 51%), despite averaging 6.2–6.3 actual minutes. The 20–30 group averaged 1.5 more planned than actual minutes. Those differences point to workload exposure as a separate source of error. The under-10 tracker band also has just 3,387 games across four years. The 32+ gap remains around one spell per 82, and the 29–31 gap widened. Age bands blend across workloads and across different cohorts in the tracker and 2026–27 sim.

## Injury lengths and volume

Length counts scheduled games before return. The sim excludes opening-night injuries, which are already in progress, and events that cost no game in the measured season.

| Share of recorded spells | Tracker 2021–25 | Before 17 / 29 | After 17 / 29 |
|---|---:|---:|---:|
| 1 game | 40.4% | 39.3 / 39.1% | 39.9 / 39.0% |
| 2–5 games | 35.2% | 35.4 / 35.4% | 35.9 / 35.6% |
| 6–10 games | 10.8% | 12.2 / 11.7% | 11.4 / 11.4% |
| 11–20 games | 7.2% | 7.5 / 6.6% | 7.4 / 6.5% |
| 21+ games | 6.5% | 5.7 / 7.2% | 5.5 / 7.5% |
| Spells per team, including illness | 24.3 in tracker panel | 34.7 / 35.5 | 35.2 / 36.0 |

The earlier full-team comparison in [INJURIES-2](injuries-2.md) found 35–43 spells per team including illness for 2023–25, using a different coverage window than the tracker panel above. The health-only replay, which also counts events with zero games missed, rose from 44.3 / 46.2 to 45.1 / 47.0 spells per team. Its median duration stayed four tracker days, and its 90th percentile went from 30 / 34 to 30 / 32 days. With the same recovery tables, changes in which body parts get hurt and who gets hurt can move the overall length distribution.

## Games played

Heavy-minute players averaged at least 30 minutes over at least 10 games. The 30 best-rated players use the prior report's group in each source. Real games played and absence patterns come from 2025–26 box scores. The game uses its real 2026–27 opening-night list in both sim runs.

| Metric | Real | Before 17 / 29 | After 17 / 29 |
|---|---:|---:|---:|
| Heavy-minute median games played | 68 | 66.5 / 67 | 66 / 67.5 |
| Heavy-minute mean games played | 61.7 | 62.8 / 62.8 | 63.1 / 63.1 |
| Heavy-minute games missed in single-game stretches | 2.40 | 2.66 / 2.83 | 2.61 / 2.78 |
| Heavy-minute games missed in 2–10 game stretches | 5.60 | 4.91 / 5.64 | 4.87 / 5.78 |
| Heavy-minute games missed in 11+ game stretches | 4.02 | 6.14 / 4.62 | 5.65 / 4.43 |
| Top-30 median games played | 64.5 | 70 / 67 | 70 / 67.5 |
| Top-30 mean games played | 55.4 | 67.6 / 59.9 | 67.6 / 60.3 |
| Top-30 games missed in 2–10 game stretches | 7.00 | 4.23 / 4.27 | 4.20 / 4.30 |
| Top-30 opening games missed | 3.27 | 1.10 / 1.10 | 1.10 / 1.10 |

The refit barely moved games played. The top-30 group still misses about four games a season in 2–10 game stretches, compared with seven in the real box scores. Opening-night availability also differs across years, including two long absences for Tatum and Haliburton in real 2025–26. Games played here is an evaluation of the simulated season. The fit itself uses injury counts and time at risk.

## Coach rest

I grouped the same 10,895 chances from SMART-REST's 2025–26 box-score sample by minutes. Players at 25 to under 30 minutes missed 220 of 5,778 games (3.81%), and players at 30+ missed 194 of 5,117 (3.79%). Only 2 and 9, respectively, were explicitly labeled rest. The reason was missing from 154 and 139 absences. Coach rest accounts for 1.68 / 1.62 isolated absences per heavy-minute player in the new sim. The real box scores count isolated injuries and other absences alongside rest, and they don't support a new coach-rest coefficient.

## Speed

| Measure | Before 17 / 29 | After 17 / 29 |
|---|---:|---:|
| Health-only seconds per simulated month | 0.38 / 0.38 | 0.40 / 0.40 |
| Fixed-roster full season, seconds elapsed | 54.0 / 52.7 | 54.4 / 53.6 |
| Fixed-roster season, seconds of game simulation | 32.36 / 31.88 | 32.82 / 31.99 |

Health time is about 0.4 seconds a month either way. The fit runs offline and adds no season-specific lookup at runtime. Injury and rest draws remain seeded. Some draws now have different outcomes because the injury probabilities changed.

## Checks

The synthetic fit test checks that the workload effect comes from within-season comparisons even when season coverage differs eightfold. The countdown test covers a pending game on the current day, a played game on the current day, another team's game and the return game. The fantasy-draft test runs the normal completion action and checks the injury event and player state against the new team's schedule.

- Focused unittest run, including all six requested modules and the injury follow-up tests. 112 passed.
- Core suite. 338 run, two skipped.
- Full suite. 2,082 tests run, 27 skipped, zero assertion failures and 19 errors. Seventeen errors came from missing ignored reference files under `output/`. Two Windows packaging checks needed the ignored startup video. The foundation tests for seeded injury behavior and the evidence-based injury range passed.
- Real-stat replay over 1,230 games with real minutes. **18/18** league measures within range. Runtime was 16.2 seconds.

## What's left

- Measure injury draws against actual on-court exposure before changing the rates again. Review the remaining gap for players aged 29 and up with a matched workload and age sample.
- The 30 best players still have fewer medium-length absences than the 2025–26 comparison group. Additional seasons would give a steadier comparison, especially at opening night.
- The coach-rest minutes split needs a sample that identifies more of the reasons players sat.

## Resume state

The code, tests and generated model are ready for review on `codex/injury-followups`. Paired fixed-roster and health-only runs, tests and the real-stat replay are complete. Validation logs and tables are in `output/injury-followups/`. The rate tables come from `scripts/research/injury_rate_bands.py`. The length and games-played tables use `scripts/research/injury_lengths.py` and the INJURIES-2 harness. The run files with prefixes `followup_before_` and `followup_after_` are in shared `output/injuries-2/`. Rebuild the tracked model with `PYTHONPATH=src .venv/bin/python scripts/build_injury_model.py --write --model-only`.
