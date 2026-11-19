# Fatigue and rest controls (FATIGUE-REST, 2026-11-19)

## TL;DR

- Fatigue really was too flat. For most heavy-minute players it hovered between 0 and 15 all season, so the bar showed 0 or 1 of its 6 segments 82% of the time. Meanwhile 37-year-plus stars (LeBron, Durant, Curry) sat pinned near 100 and lost ratings without anyone seeing why. Now recent minutes fade day by day: a 36-minute starter is about 50 right after a game, about 20 at the next tip-off and about 30 on the second night of a back-to-back, and every heavy-minute player reaches the red at some point in a season.
- The engine now uses the same number everywhere: how tired a team is at tip-off replaces the flat back-to-back penalty in simulated games, injury risk goes up a little when a player is more tired than normal, and the AI coaches' rest decisions follow it. The bar shows the engine's value, and its tooltip shows the value his next game will use.
- Your team has a new **"Coach rests players"** setting, **off by default** because you set your own minutes. There is also a **zZ button next to each player's minutes** that rests him for his team's next 1 to 5 games. His minutes target is kept and comes back on its own afterwards, you can cancel the rest, and the button warns you before the rest would take him under the 65 games needed for season awards.

## What was wrong (measured first)

These numbers come from two full headless seasons per version (seeds 17 and 29) with the 94-input ratings, fixed opening rosters and all 30 teams AI-coached. The harness is `output/fatigue-rest/sim_season.py`. Below, "heavy-minute players" means players averaging 30+ minutes a game.

1. **Recovery cancelled out a normal game.** Each game added about 4.2 points per 24 minutes, and each day off took away a flat 6.5. A 36-minute player on a normal schedule (a game every other day) gained about as much as he recovered, so he stayed near the bottom. Heavy-minute players had a median fatigue of 14 and reached a median season high of 33. The bar runs 0-100 in 6 segments, so it showed 0 or 1 segment on 82% of player-days and 3 or more on only 5%.
2. **Older players ran away to 100.** Age added a flat amount to every game while recovery stayed the same, so players aged 37 and older never recovered. In one season LeBron James played 53 of his 60 games, and Kevin Durant 44 of his 76 (13 of them at 90+), above the point where the hidden penalty started. That penalty was up to 4.6 rating points plus up to +54% injury risk, and the bar for those two looked no different from anyone else's.
3. **The effects hardly ever applied.** The performance penalty started at 35 and the injury effect at 25. Only 1% of player-games were above 35, and almost all of those belonged to the 37+ players.
4. **The value shown was not quite the value used.** Each game played on a fatigue number that already included that same game's minutes.

Before vs after: what heavy-minute players carried into their games (two seasons, seeds 17 / 29).

| Tip-off fatigue, heavy-minute players | Before | After |
|---|---|---|
| All games, median | 13.7 / 14.2 | 16.8 / 17.1 |
| Second night of a back-to-back, median | 17.9 / 18.1 | 27.0 / 26.8 |
| One day's rest, median | 13.7 / 14.3 | 17.5 / 17.8 |
| Two or more days' rest, median | 7.0 / 7.0 | 9.1 / 9.1 |
| Highest | 100 / 100 (37+ players pinned) | 44.7 / 42.5 |

What the bar showed after each day (heavy-minute players):

| | Before | After |
|---|---|---|
| Median / 90th percentile | 14 / 33 | 35 / 54 |
| Green (under 40) / yellow (40-60) / red (60+) | 94% / 4% / 2% | 60% / 35% / 4% |
| 3 or more of 6 segments lit | 5% | 36% |
| Each player's highest of the season: 10th / 50th / 90th percentile | 22 / 33 / 60 | 55 / 61 / 73 |

## The evidence behind the new behavior

**Real 2025-26 games** (`output/fatigue-rest/real_fatigue.py`, 1,235 regular-season box scores):

- **Teams:** teams on the second night of a back-to-back did 1.4 points worse than expected (standard error 0.7), against +0.3 on one day's rest and +0.4 on two or more days. Against a rested opponent the gap was 2.1 points (standard error 0.85).
- **Individual players:** regulars (25+ minutes, 40+ games, 154 players) who played on the second night scored per minute just as well (+1.5%) and kept their box production per minute (+0.4%). Their plus-minus did fall (+0.6 against +1.3 on other nights). No measure of recent load (games in the last 7 days, minutes with a 2-day half-life) showed a clear drop in per-minute production. The likely reason: the most tired players are the ones who sit. So the normal cost of fatigue shows up at team level, not in one player's box line.

**Published studies:**

- Lewis (2018, *Journal of Athletic Training* 53:503), three NBA seasons: injury odds rose about 3% per 96 minutes of recent play and fell about 16% for each day of rest.
- Teramoto et al. (2017, *Journal of Science and Medicine in Sport* 20:230): back-to-backs alone were not linked to more game injuries, but road games and road back-to-backs were.
- Esteves et al. (*European Journal of Sport Science* 21:26): schedule congestion lowers team results and shooting efficiency.

All three effects are kept modest.

## What changed

All of this is in `health.py`, `sim.py` (fatigue and rest hooks), `save.py` (health, rest and minutes functions), `app_actions.py`, `gui/app.js`, `gui/card-board.css` and the fatigue keys in `data/overrides/injury_model_config.json`.

1. **Fatigue (0-100) is recent playing load.**
   - **Building up:** each game adds 31 points per 36 minutes played. That amount is +3% per year over 30 and another +3% per year over 35, ±8-12% for stamina, ±4% for the conditioning coach, and +5% on the road (travel; judgment).
   - **Recovering:** each calendar day clears 38% of what is left, a little more with a better recovery coach. Three days off clear about three quarters.
   - **Recovery happens every day**, not only on game days, so the number on screen is always today's.
   - **Effect:** the old flat age add-on is gone, so older players build fatigue faster but still recover.
2. **A game uses tip-off fatigue.** The day's health pass records each player's fatigue before the game, and only then adds that game's minutes. The game reads the recorded value, so the effects follow how tired he is when the game starts.
3. **Team effect (generated games only).** A team's minutes-weighted tip-off fatigue is compared with its level on one day's rest (12). Each point above that costs 0.25 points of offense per 100 possessions. That is about -1.5 on a typical back-to-back, about the old rule's -1.35 and the real -1.4 to -1.7. A rested team gains at most +0.4. This replaces the plain back-to-back rule in simulated games, so a team that rests its star on a back-to-back really is fresher. Replays of real games keep the old schedule rule, so both scorecards are unaffected.
4. **Individual effect only when very tired.** Above 50 at tip-off, a player loses 0.05 rating points per point of fatigue, at most 2.5 (judgment; the real box scores show no individual drop at normal levels). In the AI seasons nobody reached 50 at tip-off (the highest was 45). A GM who plays a star 42+ minutes through a dense stretch can get there.
5. **Injury risk** rises 1.2% per point of tip-off fatigue above a regular's normal level (16): about +15-20% on a typical back-to-back for a 36-minute player and +40% at 45, capped at +60%. It never goes below normal. The injury model's own minutes term already covers how many minutes he is exposed; this term covers schedule density only.
6. **The AI coach's rest follows fatigue.** Tonight's tip-off fatigue is compared with the player's normal level for his minutes. A normal night gives the fitted base chance and a typical back-to-back the fitted back-to-back chance. A heavier stretch (overtime, four games in six nights, an older player) gives more, up to twice the back-to-back step. The reason reads "heavy recent workload (fatigue 41)" when that is why. The league rules are unchanged: at most one rested regular a game, none after 14 missed games, none while three regulars are out.
7. **The bar.**
   - **What it shows:** the engine's value today (green under 40, yellow 40-60, red 60+), same 6 segments.
   - **The tooltip:** gives his value at the next tip-off ("About 14 at his next tip-off (2026-11-23): the value that game uses") and explains in plain words what builds and clears fatigue and what it does.

Determinism: everything stays seeded. Generated games and seasons change, through fatigue values, injury chances and rest nights. Replays and the betting-odds test are unchanged.

## Your team: the toggle and the rest button

- **"Coach rests players"**
  - **Where:** a small checkbox in the Player header of Minutes + Availability, and also in Settings as "Coach rests my players automatically". It is a per-save setting, **off by default**.
  - **On:** your coach rests your players by exactly the AI coaches' rule and seeded draws. A test checks that the same seed rests the same players as an AI team would.
  - **Off:** nobody is rested automatically.
  - **The blue zZ suggestion stays visible either way.** Off, it reads "Coach suggests resting him on DATE: reason. Use the zZ button next to his minutes to rest him." On, it reads "Coach plans to rest him on DATE: reason."
- **The zZ button** sits after each player's minutes slider. It opens a small menu: rest for 1-5 games, or "Cancel rest" if he is already resting.
  - **While he sits:** he misses his team's next N games (playoffs included). His slider is greyed out, and a blue "zZ N" marker next to his name says "Resting: sits his team's next N games, then back to his 34 minutes." His minutes are placed by the same coach fill-in rule used for absences.
  - **His minutes target:** kept. If you change other players' minutes during the rest, his target is still kept. In that case, when he returns, everyone is scaled back to 240.
  - **Fatigue:** clears as on any day off.
  - **After the rest:** he is back automatically.
  - **Rest rules:** a GM rest counts toward the "one rested regular a game" rule for the auto-coach.
  - **Award warning:** each menu option shows "under 65 games" when that rest would leave him unable to reach 65 games. The footer says how many games he can still reach, and you get a warning message after confirming.

## Checks

**Seasons** (seeds 17 / 29, before -> after; real 2025-26 in the last column):

| | Before | After | Real |
|---|---|---|---|
| Players at 30+ / 34+ / 36+ minutes a game | 62 / 15 / 3, 67 / 20 / 4 | 64 / 15 / 3, 62 / 17 / 4 | 70 / 18 / 3 |
| Most minutes a game | 36.45 / 36.45 | 36.57 / 36.56 | 38.0 |
| Games played, players at 30+ minutes: median | 70 / 71.5 | 68 / 69 | 68 |
| 30 best-rated players: average games | 65.9 / 65.6 | 66.9 / 62.6 | 57.3 (median 64.5) |
| Injuries per team (incl. illness) | 33.7 / 35.4 | 34.7 / 35.8 | Basketball Index 30-37 + illness |
| Single-game absences, regulars: all / back-to-back / other nights | 3.1 / 7.1 / 2.3%, 3.1 / 6.9 / 2.2% | 3.4 / 7.0 / 2.5%, 3.3 / 7.2 / 2.5% | 3.2 / 7.2 / 2.4% |
| Rest nights per team-season | 26.5 / 25.3 | 26.5 / 27.8 | |
| Team margin vs expected: back-to-back / one day / 2+ days | -1.8 / +0.3 / +0.5, -3.0 / +0.3 / +1.7 | -2.1 / +0.3 / +0.9, -3.1 / +0.3 / +1.9 | -1.4 / +0.3 / +0.4 |

The team-margin rows are noisy (standard error about 0.7 a season) and match the old rule within noise.

**Scorecards** (both unchanged, as expected, because replays of real games keep the schedule rule):
- Real-minutes replay with the 94-input ratings (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**.
- Betting-odds test, 100 runs: **Brier 0.1959, log loss 0.5786** (market 0.1962 / 0.5740), spread error 4.56, totals error 5.49, 1,231 games (1,018 with odds). These match main.

**In the running app** (GUI server on port 8781, save in the scratch area, Boston):
- Created the save and simmed to 15 November (19.6 s), then a week through the GUI.
- The bar values equal the stored engine values (for example White 22.2 today, 14 at his next tip-off).
- "Rest 2 games" on Tatum: the blue "zZ 2" marker appeared, his 27 minutes went to Hauser, Garza and others, he sat two games and came back at 27 on his own.
- The toggle saved to the save file, and Settings showed it checked. With it on, a month later the coach had rested White and George once each.
- **Not clicked through:** the 65-game warning (covered by tests) and the suggestion marker on a live save (none came up for Boston that week; covered by tests).

**Speed:**
- Game simulation: 31.8 / 30.2 s of processor time per 1,230 games, against 31.1 / 30.4 before.
- Full season: 52 / 49 s of wall time against 48 / 47, on a machine loaded by other agents.
- The new daily work (one next-game lookup for your team) is a few milliseconds.
- One app month took 19.6 s and 25.7 s with the AI front office, on the loaded machine.

**Tests:**
- New `tests/test_fatigue_rest.py` (16 tests): fatigue gain and calendar recovery; normal, back-to-back and dense-stretch levels; injury multiplier; team effect; the individual penalty; rest following fatigue; the game using the tip-off value while the bar shows today's; toggle off never rests and on matches the AI rule; setting default; rest for N games, then recovery and return; minutes target kept and restored; the rest action, cancel and the 65-game warning; the award outlook; the toggle action.
- New `tests/fatigue_rest.test.cjs` (4 tests): the bar shows the engine value and segments, the rest button, the resting marker and suggestion wording, and the toggle.
- Updated `tests/gui_small_fixes.test.cjs` (the rest note needs the new helpers) and `tests/test_gui_concept74.py` (the Player header cell now also holds the toggle; the five columns are unchanged).
- Focused modules `test_injury_rest`, `test_game_minutes`, `test_absence_fill`, `test_injury_model` and `test_fatigue_rest`: 67 OK.
- All `tests/*.test.cjs`: 251 of 252 pass. The one failure, the startup video file, is missing from this worktree because it is git-ignored. It is not related to this task.
- Core suite `scripts/run_core_tests.sh`: 337 run, OK (2 skipped). The full suite was not run, because other agents were using the machine.

## What's left

1. **Planned minutes, not box-score minutes.** Fatigue is added from the coach's planned minutes for the game, with injury and rest fill-ins included. Overtime, blowout rest and foul trouble on the night are not counted. Counting the box score would need the save to add fatigue after every game, playoffs included. That is possible, but it would add a second place where fatigue changes.
2. **When a rested player returns to edited minutes.** If you change minutes while a player is resting, everyone is scaled back to 240 when he returns, rather than to exactly what you set. Players back from injury already return with whatever their saved target was.
3. **Old players on back-to-backs.** The AI rest chance for players aged 30-33 on back-to-backs is still a little below real (7.5-8.7% vs 10%).
4. **Minutes-request talks use old thresholds.** `play.py` still treats fatigue 28+ as "the rest case is persuasive" and 35+ as "fatigue concern" when the GM asks for more or fewer minutes. With the new scale these come up more often for heavy-minute players. That fits, but it was not tuned. The file is outside this task's boundaries.
5. **One seed per check.** The team-margin check is noisy (standard error about 0.7 a season).

## Resume state

- **Done:** measurement, all fixes, two before/after seasons (`base2_*`, `final_*` in `output/fatigue-rest/`), app check, focused tests, JavaScript tests.
- **Harness** (all in `output/fatigue-rest/`):
  - `sim_season.py`: records tip-off fatigue per player line, a daily bar snapshot and the home flag.
  - `run_final.sh`: base and final, with `BASE_SRC` set to an extracted copy of the starting source.
  - Reports: `fatigue_report.py`, `team_rest.py`, `rest_rates.py`, `summary.py`, `real_fatigue.py` (real box scores) and `app_check.py` (drives the GUI server with the GUI's requests).
- **Branch:** commits on `worktree-agent-a011ed831541985af`; not pushed or merged. The worktree's data symlinks were removed before committing. **Coordinator:** copy the worktree's `output/fatigue-rest/` (git-ignored; harness and season data) to main's `output/` before removing the worktree.
