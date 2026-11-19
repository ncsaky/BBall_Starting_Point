# Injuries, return to play and rest (INJURY-REST, 2026-11-19)

## TL;DR

- Players now get hurt about as often as Basketball Index records (34 injuries per team instead of 25), about a third of injuries happen during a game (the player leaves partway through and his teammates finish his minutes), and the absence starts with the next game.
- Players coming back from 2+ missed games now return on a minutes limit and with a little rust (97% of them, up from 18%); the minutes in their first games back match the real 2025-26 box scores.
- AI coaches now rest players the way real teams did in 2025-26 (back-to-backs, older players, the stretch run, tanking teams shutting players down), so heavy-minute players play a median 68-69 games (real 68, was 73-75). Your own coach only suggests rest. **Question for you at the end.**

## What was wrong (measured first)

The research report this task started from (`inj-injuries-vs-bbi.md`) was written against the older injury model. The per-body-part model that replaced it (Nov 17-18) had already fixed injury lengths: before this task a full season gave days out of 2 / 5 / 12-14 / 32-39 (25th / 50th / 75th / 90th percentile) against Basketball Index's 2 / 5 / 14 / 46. So "injuries are too short" was no longer true. What was still wrong, in a full headless season with all 30 AI coaches (two seeds, both rating sets):

1. **Too few injuries.** 25 per team against Basketball Index's 30-37 plus illness. Rotation players were hurt 2.2-2.8 times per 82 games played against Basketball Index's 3.3-4.3 at every workload. The model had been checked with every player at 4+ minutes exposed all season; the AI coaches' real rotations are narrower.
2. **The injury game counted as missed.** A player drawn as injured in a game sat that whole game, so no one ever left a game hurt (0 early exits; real regulars leave under half their usual minutes in 0.9% of close games). It also added one missed game to every injury.
3. **Almost no rust, and a weak minutes limit.** Rust faded by calendar day (and twice on game days), so it was gone before the player's first game back unless he had missed 6+ games: only 18% of returns after 2+ missed games carried any. A counting slip (the injury game was not counted as missed, and the first game back was counted as already played) made the coach's minutes limit start late and small: after 2 missed games players came back at +0.5% minutes (real: -7%).
4. **No rest at all.** Heavy-minute players (30+ a game) had 0.6 single-game absences a season against 2.4 in the real box scores. Real single-game absences triple on the second night of a back-to-back, rise with age and late in the season, and the eight worst teams shut their regulars down for the last weeks (6.8 games each on average). None of that existed.
5. **Back-to-backs were invisible to fatigue.** The save runs the health pass one day at a time, and each day started from "two days' rest", so back-to-backs never added fatigue.

## What changed

All in `health.py`, `injury_model.py`, `game_minutes.py`, `sim.py` (return and injury hooks), `save.py` (health functions only) and the player-name markers in the GUI.

1. **Injuries happen in games.** When the injury model draws an injury from a game's minutes, the player plays that game. About 30% of the time it happens during play: he leaves after a random share of his minutes (more often the longer the injury: 15% of one-day knocks, 45% of two-week injuries, 70-80% of two-month-plus injuries; illness never). The coach gives his remaining minutes to the bench first and to players at his position first, he does not return for overtime, and the box score line says why (`in_game_injury`). The rest are found after the game. Either way the absence starts with the team's next game and is listed as soon as the day's games end. Days out are measured from the injury date, as Basketball Index does.
2. **More injuries.** The league rate calibration goes from 1.0 to 1.35, which brings rotation players to 3.3-3.6 injuries per 82 games played (Basketball Index 3.3-4.3). This is the model's league-level scale only: no player's ratings or injury-proneness inputs changed.
3. **Rust by games missed, fading per game played.** 0 after one missed game, then 4 / 8 / 12 / 16 / 20 rust points after 2 / 3-5 / 6-10 / 11-20 / 21+ missed games (0.3 to 1.6 rating points), losing 7.5 per game played, so it lasts one to three games. Kept small on purpose: real players score about the same points per minute in their first three games back (pooled, within a few percent either way) and Basketball Index's shooting change after a return is small with every interval spanning zero.
4. **Minutes limit fitted to the real box scores.** The coach's planned cut for the first game back is now 2% / 10% / 16% / 25% / 32% / 42% by games missed, fading to normal over 6-10 games (a better rotation manager is a little more careful, a poor one rushes). The planned cut is larger than what shows up in the box score because teammates' minutes are renormalized around it. The counting slip is fixed.
5. **AI coaches rest players** (`health.rest_chance`), healthy regulars (24+ planned minutes) only:
   - second night of a back-to-back: 5% under 25, 7% at 25-29, 9.5% at 30-33, 11% at 34+; other nights 1-3% by age (this also stands in for one-game absences that never reach an injury report: personal reasons, minor knocks);
   - a player just back from injury: +15% on back-to-backs (judgment call, common practice);
   - last 15 games: +3% (+0.8% more for the eight best teams); last two games: 35% for winning teams ("rest before the playoffs"), 25% for others;
   - the eight worst teams in their last 25 games shut regulars down for the season (3% a game);
   - league rules: at most one regular rested per game (the 2023 player participation policy), no rest nights once a player has missed 14 games (65-game award rule), none while three regulars are already out.
   Rest decisions are seeded per game and player, like injuries.
6. **Your team: suggestions only.** Each day the game works out, by the same rule and the same seeded draw, whether your coach would rest someone in your next game, and shows a small blue "zZ" next to the name in Minutes + Availability (hover: "Coach suggests resting him on 2026-12-03: second night of a back-to-back. Set his minutes to 0 to follow it."). Nothing is applied.
7. **The rust marker** now says how many games the rust lasts and the minutes limit ("about 75% of his usual minutes next game, back to full over 8 games").
8. **Back-to-backs count for fatigue**: the date of the team's last game is kept on each player's health record.

Determinism: everything is seeded. Generated games and seasons change (more injuries, rest nights, exits). The real-minutes replay and the betting-odds replay do not use these paths.

## Before and after against real

Four full seasons each (both rating sets x seeds 17 and 29; fixed opening rosters, all teams AI-coached). Ranges are across the four. "Real" is the 2025-26 regular-season box scores unless marked Basketball Index (BBI). Harness and analysis: `output/injury-rest/`.

**Injuries**

| | Before | After | Real / BBI |
|---|---|---|---|
| Injuries per team-season (incl. illness) | 24.9-25.7 | 32.9-35.5 | BBI 30-37 injuries, 35-43 with illness |
| Injuries per 82 games played, 28+ minute players | 2.8 | 3.4-3.6 | BBI 3.4-4.3 |
| Days out, 25th / 50th / 75th / 90th | 2 / 5 / 12-14 / 32-39 | 2 / 5 / 13-14 / 33-39 | BBI 2 / 5 / 14 / 46 |
| Injuries that happen during a game | 0% | 30-31% | (no direct figure) |
| Regulars leaving a close game under half their minutes | 0% | 0.53-0.66% | 0.88% (70% of them then miss games; sim 70-81%) |
| Minutes in the game a 2+ game absence starts (vs the 5 before), 2 / 3-5 / 6-10 / 11-20 / 21+ missed | +1 / -1 / -1 / 0 / 0% | -9 / -12 / -21 / -36 / -26% | -13 / -15 / -25 / -27 / -38% |

**Returns** (players at 15+ minutes; first game back and first five, against the five before the absence)

| Games missed | Before: first / five | After: first / five | Real: first / five | BBI first game |
|---|---|---|---|---|
| 2 | +0.5 / +0.6% | -9.3 / -7.3% | -7.4 / -7.0% | -7.2% |
| 3-5 | -5.4 / -3.8% | -12.2 / -8.1% | -13.7 / -9.2% | -9.9% |
| 6-10 | -11.2 / -6.3% | -19.4 / -14.3% | -19.4 / -14.5% | -16.2% |
| 11-20 | -15.4 / -12.9% | -27.5 / -21.6% | -26.4 / -22.2% | -21.2% |
| 21+ | -21.2 / -14.0% | -31.3 / -21.6% | -34.3 / -29.9% | -29.9% |
| Returns with rust in the first game (2+ missed) | 18% | 97% | | |

**Games played and rest**

| | Before | After | Real |
|---|---|---|---|
| Players at 30+ minutes: median / mean games | 73-75 / 66-70 | 68-69 / 64-65 | 68 / 61.7 |
| 30 best-rated players: median / mean games | 74-77 / 65.6-70 | 66.5-69.5 / 62.3-67.6 | 64.5 / 57.3 |
| Single-game absences per 30+ minute player | 0.6-0.7 | 2.4-2.7 | 2.4 |
| Single-game absence rate, regulars: all / back-to-back / other nights | 0.8 / 1.0 / 0.8% | 3.2 / 7.3 / 2.2% | 3.2 / 7.2 / 2.4% |
| Back-to-backs by age: under 25 / 25-29 / 30-33 / 34+ | ~1% each | 6.0 / 6.7 / 9.6 / 9.5% | 5.2 / 7.4 / 10.0 / 11.4% |
| Last 15 games, best eight / middle teams | 0.8 / 1.3% | 5.8 / 5.1% | 5.3 / 4.7% |
| Worst eight teams' regulars: final games missed (mean, % missing 5+) | 1.0, 7% | 7.0, 47% | 6.8, 46% |
| Rest nights per team-season | 0 | 25-27 | |

Where the gap closed (94-input ratings, seed 17): heavy-minute players' median went 73 -> 71.5 with the injury changes alone (more injuries, but the injury game is no longer missed) -> 68 with rest. Rest is the larger lever. The remaining gap to the real top 30 comes from a handful of season-long real injuries carried over from 2024-25 (Tatum, Haliburton, Lillard-type cases) that one simulated season rarely produces: the real top 30 had 10 players under 60 games, the sim 6-10.

**Minutes** (players with 40+ games; target: stay at the current 63-69 / 14-19 / 2-4)

| | Before | After | Real |
|---|---|---|---|
| 30+ / 34+ / 36+ minutes a game | 61-69 / 13-19 / 2-4 | 62-66 / 14-17 / 2-4 | 70 / 18 / 3 |
| Most minutes a game | 36.2-36.7 | 36.5-36.6 | 38.0 |

## Scorecards

- Real-minutes replay, 94-input (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**.
- Betting-odds test, 94-input, 100 runs (`validate-season-probabilities`): **Brier 0.1937, log loss 0.5734** (market 0.1962 / 0.5740), spread error 4.50, totals error 5.44, 1,231 games (1,018 with odds). Same as main: these games replay real minutes and do not use the health, rest or in-game coach paths.

## Speed

Headless seasons: 46-61 s wall after vs 47-60 s before on a heavily loaded machine (load average 12-59 from other agents); game simulation CPU 31.0-33.9 s vs 29.8-31.2 s per 1,230 games, about +2 s a season (+0.4 s a simulated month), from the in-game exits and extra reserves. The save's extra daily work (rest suggestions for your team, listing tonight's injuries) is one pass over the schedule and the health records, a few milliseconds a day. I did not run an app-path month benchmark because of the machine load.

## Tests

- New `tests/test_injury_rest.py` (17): the hurt player plays his game and misses from the next; the save lists him as out once the games end; in-game exits (the bench and his position absorb the minutes, 240 total, no change when nobody is hurt); in-game share by severity; rust by games missed and fading per game played; minutes limit grows with the absence; display fields; rest by back-to-back, age, late season, shutdowns, the one-per-game, 65-game and short-handed rules; seeded decisions; a rested player is out for that night only; standings context; your team gets a suggestion, never a rest.
- `tests/test_injury_model.py`: the ramp test now checks the fitted first-game cut.
- `tests/gui_small_fixes.test.cjs`: rust wording now in games plus the minutes limit; new check for the rest note (11 pass; the two trade JS files that share the name markers pass too).
- Focused modules (`test_injury_rest`, `test_injury_model`, `test_game_minutes`, `test_absence_fill`, `test_ai_roles`, `test_long_term_health`, `test_background_league_health`, `test_prospect_injury_report`, and the two health-simulation tests in `test_foundation`): 82 OK.
- Core suite `scripts/run_core_tests.sh`: 337 run, OK (2 skipped).

## What's left

1. **Early exits are a little rare**: 0.53-0.66% of regulars' close games against 0.88% real. About a third of the real ones are not followed by an absence (ejections, a knock he plays through the next night, illness), which the sim models only partly.
2. **2-game and 6-10-game absences** are a bit rarer than real (0.37 and 0.2 a season per heavy-minute player against 0.6 and 0.34); one-game and long absences match.
3. **Bench players get hurt less than real**: players under 12 minutes 1.5 injuries per 82 games played against Basketball Index's 3.4. That is the fitted model's workload term; I left it.
4. **Points per minute after a return** in the sim are flat (as the real pooled data mostly are); the rust is visible on the card but small by design.
5. **Fewer last-game rests for good teams**: 37% of the best eight teams' regulars sat at least one final game (real 60%; middle teams 27% vs 46%). The worst teams' shutdowns match (7.0 games, 47% missing 5+, against 6.8 and 46%).
6. **Not checked in the running app**: the "zZ" note and the new rust tooltip were tested in code, not clicked through in a live save. Real playoff resting and trades are outside this task's harness (fixed rosters).

## Question for you: rest on your own team

Right now your coach only **suggests** rest (a small "zZ" next to the player for the next game), and you would have to set the player's minutes to 0 and then back again yourself. How would you like it to work?

- **A. Keep it as a suggestion** (current), maybe with a one-click "rest him next game" that restores his minutes afterwards.
- **B. Let the coach decide by default**, with a team setting to switch it off (like the AI teams).
- **C. Never rest** your players unless you set it yourself, and hide the suggestion.

## Resume state

- Done: measurement, all fixes, four-season before/after (labels `base_*` and `final2_*` in `output/injury-rest/`), no-rest decomposition (`norest_inputs_s17`), calibration 18/18, odds test, focused tests.
- Harness: `output/injury-rest/sim_season.py` (with standings so rest is active; `--no-rest`), `run4.sh LABEL`, `summary.py`, `compare.py base final2`, `rest_table.py`, `absences.py` (returns, exits, absence spells; real when run without a label), `real_rest.py` (single-game absences by context, season-end tails).
- Commits on branch `worktree-agent-a9b9ae2514db279bf`; nothing pushed or merged.
