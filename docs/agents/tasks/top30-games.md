# TOP30-GAMES: why the best players play too many games (2026-11-20)

Branch: `worktree-agent-a18f9fc0e71116db0`. Scratch and harness: `output/top30-games/` (git-ignored).

## TL;DR
- Over five real seasons, the 30 best players get hurt about a third more often per game than other heavy-minute players. They do not stay out longer for the same injury, and they don't sit for multi-game rest.
- The game gives its stars too little injury risk for two reasons: it counts a player's own injury history at about half the strength the real data supports, and its stars start the game with about a third less recorded injury history, because Basketball Index logged only about a third of 2025-26.
- I tested a fix (count real injury history at its measured strength). It barely moved the stars' games played and made some groups slightly worse, so **I did not keep it**. The engine is unchanged. The real fix needs a fuller 2025-26 injury history first (see "What's left").

## 1. The real measurements (2021-22 to 2025-26)

**Who counts as the top 30.** These are the 30 best players by the previous season's Game Score per game (a public box-score composite from ESPN stats, 30+ games). The players are chosen on what was known before the season, the same way the game picks its top 30 by rating at the start of a season, so the group is not selected on that season's own health. As a check, I also used the same-season pick (20+ games), and for 2025-26 the game's own top 30.

Sources:
- ESPN league stats, player game logs and team schedules (public, cached under `output/top30-games/espn/`).
- Basketball Index's injury tracker (local only, not committed) for the reasons.

Script: `scripts/research/top30_real_seasons.py`.

**Games played and games missed per player, by where they fall** (prior-season pick):

| Season | Median | Mean | Under 60 | Season start | Single games | 2-10 game stretches | 11+ game stretches | After last game | Whole season |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021-22 | 61 | 56.1 | 14 | 1.2 | 2.3 | 7.4 | 4.5 | 5.1 | 5.5 |
| 2022-23 | 66 | 62.6 | 11 | 0.5 | 3.7 | 6.0 | 7.2 | 1.8 | 0 |
| 2023-24 | 70 | 64.8 | 9 | 1.0 | 3.2 | 5.6 | 3.7 | 3.9 | 0 |
| 2024-25 | 66.5 | 60.3 | 11 | 1.5 | 3.1 | 5.6 | 6.4 | 3.3 | 0 |
| 2025-26 | 64 | 50.6 | 12 | 3.4 | 2.4 | 5.1 | 8.0 | 5.2 | 8.2 |
| **Pooled** | **65.5** | **58.9** | | **1.5** | **2.9** | **5.9** | **6.0** | **3.9** | **2.7** |
| Game's own top 30, real 2025-26 | 66 | 56.6 | 11 | 3.3 | 2.9 | 6.7 | 7.2 | 3.3 | 2.7 |

- The same-season pick gives a pooled median of 67 and a mean of 63.1, with 6.6 games missed in 2-10 game stretches.
- Without 2021-22, when health-and-safety protocols (COVID) caused a quarter of the 2-10 game absences, the 2-10 game figure is 5.6.
- **2025-26 was not typical:** in 2-10 game stretches, the stars' 7.0 that season compares with 5.6-6.0 over five seasons.

**Why they missed games.** These are the tracker's reasons, using the two seasons it covers fully (2023-24 and 2024-25):
- **All missed games:** injuries 71-79%, illness 3%, no tracker entry 18-25%.
- **2-10 game stretches:** injuries 81-89%, illness 5-6%, no entry 5-12%, and nothing logged as rest.
- **The 2025-26 box scores** list no rest at all in the stars' 2-10 game stretches.

**Days out on the same diagnosis, stars against others:** see cause (a) below.

## 2. The cause, with numbers

`scripts/research/top30_causes.py`, `scripts/research/injury_history_weight.py` and `scripts/research/top30_inputs_compare.py`. All use real player-seasons from 2021-22 to 2024-25 in the tracker.

**(a) Teams are more careful with stars on the same injury: no.**
- On the same diagnosis, stars are out x0.99 as long as other heavy-minute players (90% range 0.89-1.18; 69 diagnoses, 419 star injuries).
- Against all other players, stars are out x0.85 as long, so stars come back sooner if anything.
- The ratio is the same for injuries that cost at least one game (x0.99).
- By body part the pattern is mixed and the samples are small: knee x1.15, foot x1.34, calf x1.22, hip x0.58.
- Basketball Index's own per-player recovery speed puts the stars 6.6% faster than average, against +1.6% for other heavy-minute players.

**(b) Stars get hurt more often per game: yes. That is the gap.**

Absences of 1+ games per 82 games played:

| Group | Minutes | Real | Model's prediction | Real / model |
|---|---:|---:|---:|---:|
| Stars | 34.7 | 4.53 | 4.69 | 0.97 |
| Other heavy-minute players | 31.8 | 3.31 | 4.07 | 0.81 |
| Others 20+ minutes | 24.3 | 2.78 | 3.60 | 0.77 |
| Under 20 minutes | 14.8 | 2.15 | 3.20 | 0.67 |

The model predicts every tracker entry, including ones that cost no game, so read the last column as relative. With the league level matched, the model under-predicts stars by 23%.
- By length, stars have 2.19 one-game absences, 1.80 absences of 2-10 games (7.4 games) and 0.54 absences of 11+ games (16.4 games) per 82 played. Other heavy-minute players have 1.40, 1.56 (6.3 games) and 0.34 (9.6 games).
- Minutes don't explain it. Stars at 32-35 minutes still have 1.00 against 0.88 for non-stars at the same minutes.
- What does explain it is the injury model's history weight. The engine counts a player's own injury history at 0.55 of the strength the fit found (set so risk matched Basketball Index's 2026-27 forecasts evenly by age). Fitted against what really happened, the best weight is 0.95 (90% range about 0.90-1.00). The log-likelihood is 46-58 points better than at 0.55.

| History weight | Stars, real / model | Ages 29-31 | 32+ | Under 25 | Left over per unit of on-ball load | Per 4 years of age |
|---|---:|---:|---:|---:|---:|---:|
| 0.55 (current) | 1.23 | 1.20 | 1.18 | 0.89 | x1.10 | x1.12 |
| 1.0 | 1.03 | 1.14 | 0.99 | 0.98 | x1.05 | x1.02 |

On-ball load is points/1.15 plus turnovers per 36 minutes, and "per unit" means per standard deviation (about 5).

Usage ("on-ball load") looked like a cause at first: the top third by load is under-predicted by 12%, stars or not. Once history counts at full strength, most of that disappears: x1.04-1.05 per standard deviation is left, too small to act on now.

**(c) Multi-game rest or "injury management" stretches: no.**
- In the tracker's well-covered seasons, the stars' 2-10 game stretches are 81-89% logged injuries.
- The tracker logs no rest entries since 2021.
- The 2025-26 box scores show no rest in those stretches. "Injury management" appears 0.03 times per star in single games, and never in 2-10 game stretches.

**(d) The game's top 30 differ from the real ones: partly.** The model's chance of injury per 82 games at the current settings:

| Group | Age | Minutes | Recorded injury history (time-decayed) | Model chance per 82 (own minutes / at 33) |
|---|---:|---:|---:|---:|
| Real top 30, 2021-22 to 2024-25 (120 player-seasons) | 28.6 | 34.6 | 4.59 | 4.75 / 4.65 |
| Game's top 30, 2026-27 start | 30.2 | 32.9 | 3.06 | 3.96 / 3.97 |
| Same 30, a season later (2027-28 start) | 31.2 | 32.9 | 3.31 | 3.99 / 3.99 |

- Minutes account for about 2% of the difference.
- The rest is injury history: the game's stars start with a third less.

**(e) The tracker's 2025-26 season is two-thirds missing.** This is the "something else".
- In 2023-24 and 2024-25 the tracker logged 50-55 entries per 1,000 games played. In 2025-26 it logged 18.5, and only 10.7 that cost a game, against 40-43.
- By month, 2025-26 has about a third of 2024-25's entries in every month, so this is thin coverage, not a season cut short.
- The game's starting history for every real player comes from these entries, and last season's injuries weigh the most (they fade over about 18 months).
- The real players' 2025-26 absences did happen: the tracker's own games-missed total is the highest of any season. They just weren't logged as entries.

**Putting it together.** The game's stars get hurt about 3.0-3.7 times per 82 games played. Real stars get hurt 4.5 times. The shortfall has two roughly equal parts, and they multiply:
- the history discount (about x1.2 for stars);
- the thin 2025-26 history (about x1.2 at the current weight, x1.37 at the fitted one).

## 3. What I tried, and why it is not kept

**Tried:** real recorded injury history counts at its fitted strength, 0.95. The league rate is re-anchored through `scripts/build_injury_model.py`; only the per-part base rates changed (x0.78-0.93).

**Problem 1: the league rate climbs over seasons.** If the game's own simulated injuries also count at 0.95, the league rate rises season after season. I checked four seasons back to back with fixed rosters (`scripts/research/injury_multiseason_check.py`). Spells costing a game, per team:

| Setting | 2026-27 | 2027-28 | 2028-29 | 2029-30 |
|---|---:|---:|---:|---:|
| 0.95 for everything | 36 | 40 | 39 | 42 |
| Current (0.55) | 36 | 38 | 37 | 38 |
| Split: game's own injuries at 0.55 | 34 | 34 | 33 | 32 |
| Split: game's own injuries at 0.75 | 35 | 37 | 35 | 36 |

The reason: a real recorded injury tells us something about a player's hidden frailty, but an injury the game draws from its own model does not. So the version I tested counted the game's own injuries at 0.75. That keeps the league rate steady, and seed 29 shows the same shape as the current model, 1-2 spells lower.

**Problem 2: in full seasons it didn't help the stars.** These are full seasons with all 30 teams AI-coached and fixed opening rosters, seeds 17 / 29:

| | Real (5 seasons) | Current | Tried fix |
|---|---:|---:|---:|
| Top 30: median / mean games | 65.5 / 58.9 | 70 / 67.6, 67.5 / 60.3 | 70.5 / 67.2, 67.5 / 60.3 |
| Top 30: missed in 2-10 game stretches | 5.9 | 4.2 / 4.3 | 4.3 / 4.1 |
| Top 30: missed in 11+ game stretches | 6.0 | 3.3 / 3.9 | 3.7 / 3.9 |
| Top 30: injuries of 1+ games per 82 played | 4.5 (tracker) | 2.9 / 3.6 | 3.0 / 3.7 |

The fix barely moves the stars because their recorded histories are thin (cause e).

**Problem 3: it moved other groups the wrong way.** Injury rates per 82 played, against the tracker:

| | Tracker | Current | Tried fix |
|---|---:|---:|---:|
| Under 10 minutes | 2.47 | 1.56 / 1.48 | 1.28 / 1.30 |
| 10-20 minutes | 2.13 | 2.62 / 2.66 | 2.38 / 2.40 |
| 20-30 minutes | 2.85 | 3.17 / 3.36 | 3.37 / 3.42 |
| 30+ minutes | 3.67 | 3.53 / 3.70 | 3.47 / 3.70 |
| Under 23 | 2.46 | 2.42 / 2.61 | 2.08 / 2.33 |
| 23-25 | 2.75 | 2.33 / 2.37 | 2.20 / 2.22 |
| 26-28 | 3.26 | 3.01 / 3.15 | 2.97 / 3.09 |
| 29-31 | 3.55 | 2.82 / 3.09 | 2.98 / 3.03 |
| 32+ | 3.61 | 2.68 / 2.61 | 2.74 / 2.71 |

An earlier version (0.95 for everything) moved the stars a little more: median 67 / 67.5, 11+ game stretches 4.2 / 3.9. But it is the version whose league rate climbs.

**Decision.** A change that leaves the stars where they were and makes the under-10-minute and young groups worse is not worth shipping. The engine, the model file and the builder are unchanged on this branch. The tried patch is saved as `output/top30-games/tried_model.diff` and `tried_health.diff` for the follow-up.

**These stayed where the last two tasks left them,** current engine, seeds 17 / 29 (identical to INJURY-FOLLOWUPS' "after" runs):
- length bands 39.9 / 35.9 / 11.4 / 7.4 / 5.5% and 39.0 / 35.6 / 11.4 / 6.5 / 7.5% (tracker 40 / 35 / 11 / 7 / 6.5);
- spells per team 35.2 / 36.0;
- heavy-minute players' median games 66 / 67.5 (real 68).

## 4. Speed and tests
- **No engine change, so no speed change.** For reference, the fixed-roster season took 51.7-52.4 s wall and 31.3-31.8 s of game simulation. Health-only seasons ran 2.1-2.4 s each, about 0.35 s per simulated month.
- Focused modules `test_injuries_2`, `test_injury_followups`, `test_injury_model`, `test_overnight_tv_rest`, `test_smart_rest`, `test_fatigue_rest` and `test_new_career_start`: all pass.
  - `test_new_career_start` needs `scripts/` on the path (`PYTHONPATH=src:scripts`), as in the core script.
- Core suite `scripts/run_core_tests.sh`: 338 run, OK (2 skipped).
- Real-stat scorecard: not rerun, since the engine is unchanged from main (last result 18/18).

## 5. What's left
1. **Fill in 2025-26 injury history.**
   - **What to do:** give every real player a complete 2025-26 injury record before any history-weight change. The 2025-26 box scores (`data/research/game_boxscores_2025_26.json`) show every regular's absence stretches; the reason is listed for about 15% of missed games.
   - **What to decide:** how unlisted stretches count (for example, as an "other part" entry). Adding fractional extra weight to the existing entries does not work: weighting the 2025-26 entries x2.8 to match coverage nearly doubles the league rate (3.2 to 5.9 per 82), because each entry multiplies risk.
   - **Where it lives:** the builder writes the git-ignored evidence file. In a worktree that file is a symlink to main's copy, so the rebuild must happen in main or on a real copy.
2. **Then revisit the history weight** (real history 0.95, the game's own draws about 0.75; patch saved). Check it in full seasons against the tables above.
3. **Long term: a persistent frailty trait.** History stands in for hidden frailty. A persistent per-player injury-proneness (from real history for real players, drawn for generated ones), kept separate from the true re-injury effect, would let stars keep their real risk without the league rate drifting. This is a design change for its own task.
4. **Minutes (outside my files):** the game's top 30 play 32.9 minutes against the real stars' 34.6. That is worth about 2% of injury risk here, and it is the known minutes gap at the top (`sim.py` / rotation code).
5. **Absences at the start and end of the season are real-data driven in the first season.** Real stars average 1.5 games out before their first game and 2.7 whole seasons lost per player (Kawhi 2021-22, Haliburton 2025-26). The sim's first season uses the real 2026-27 opening-night list, so it has none of the second kind. Later seasons get them from the game's own carry-over injuries; this was not measured here.

## Files
- New research scripts (committed):
  - `scripts/research/top30_real_seasons.py`: real multi-season games played, stretches and reasons;
  - `scripts/research/top30_causes.py`: causes (a), (b) and (c);
  - `scripts/research/injury_history_weight.py`: profile fit of the history weight;
  - `scripts/research/top30_inputs_compare.py`: who the stars are and what the model sees;
  - `scripts/research/injury_multiseason_check.py`: four seasons back to back.
- Harness and results (`output/top30-games/`, git-ignored):
  - `sim_season.py` and `run2.sh LABEL`;
  - runs `base_s17/29` (current), `hw95_s17/29` (0.95 for everything) and `fix_s17/29` (split weights);
  - logs `real.log`, `causes.log`, `history_weight.log`, `inputs_compare.log`;
  - the ESPN cache `espn/`;
  - the tried patches.
- Engine, model file and builder: unchanged.

## Resume state
Done. The research scripts and this report are committed on the branch, and the board row is set to review. Nothing was pushed.
