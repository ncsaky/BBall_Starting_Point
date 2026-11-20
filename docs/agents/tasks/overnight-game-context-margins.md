# OVERNIGHT-MARGINS: game-context effects refit, shared pace, real starters

_Claude (Opus agent), 2026-11-20, branch `overnight/game-context-margins` (not merged). Rules 1, 4, 7, 9 apply. No player rating was changed. The experimental possession engine, trade, free-agency and waiver code were not touched._

**TL;DR**
- Game-day effects were too strong. Home court, back-to-back rest and the "old team wears down" penalty were bigger than the betting market and the real results say. The extra "missing star" penalty counted every absence twice, because the lineup already lacked him. The replayed-season test was also judging absences against next season's rosters. All of these were refit from evidence. The engine's game-to-game swings in expected margin went from 1.7x the market's to 1.2x.
- Both teams now share the game's pace, as in real games. Margins swing less (within a game 14.6 -> 13.5 points) and totals swing more (14.9 -> 17.1; real at most 18.5). Simulated team records and margins now match the real season's spread (records .159 -> .168, real .166; game margins 18.9 -> 16.8, real 16.4).
- Box scores record the five starters: the real ones in replayed games, the coach's lineup in saves. Sixth Man counts real starts (it can be switched back to the old rule). Betting test, 100 runs: Brier 0.1974 -> 0.1971, log loss 0.5813 -> 0.5793, spread error 4.61 -> 3.37, totals error 5.33 -> 4.91. The market's 0.1962 is still not beaten (0.0009 short, about the test's own sampling noise).

## Resume state

Done; ready for review. Commits on the branch: aed8b09 (replay rotation), 7695656 (context refit, shared pace, starters, Sixth Man), 56b0b28 (test fix), e21f597 (speed fix), plus the final report/board commit. Scratch work is in `output/overnight-margins/` (git-ignored; copy it to main's `output/` before removing the worktree). Key scripts: `terms.py` splits each game's expected margin into named terms (no dice); `analyze_terms.py` / `subterms.py` regress each term on the market and on real margins; `rest_groups.py` covers back-to-back situations; `offline_brier.py` is a dice-free proxy for the betting test; `real_facts.py` holds real possessions/margins/totals; `spread_check.py` measures within-game spread; `odds_dump.py` / `compare_odds.py` / `calib_slope.py` are copied from the winpick task. Engine snapshots: `base_src` (this branch's base), `ctx1_src` (refit only), `ctx2_src` (final, proven identical to the committed engine on 240 games).

## 1. Which game-context effects were too strong

Method: for every 2025-26 regular-season game, the engine's expected home margin was split exactly into its terms (no dice), then compared with the market's expected margin (the spread) and the real result. A term the engine has right should get weight 1. "Game-specific" means the part left after a season-long team strength plus home court.

| | Before | After | Market |
|---|---|---|---|
| Spread of expected margins across games | 11.97 | 10.26 | 8.46 |
| Season-long team strength spread | 6.77 | 6.29 | 5.19 |
| Game-specific swings (rest, absences, matchups) | 7.18 (1.7x) | 5.10 (1.2x) | 4.20 |
| Average home edge | +2.65 | +2.02 | +1.93 (real +1.74, all games) |
| Agreement with the market, game by game (correlation) | 0.899 | 0.919 | |
| Real margins per point of engine margin (1.0 = right) | 0.71 | 0.83 | market 1.03 |

Term by term (weights from multi-term fits on 1,017 games with market lines; real-result weights are noisier):

| Term | Evidence | Change |
|---|---|---|
| Home court | Engine gap 2.3 points per 100 gave +2.6 expected home margin. Market +1.9; real +1.6 (se 0.4) on these games. | Gap 2.3 -> 1.75 (home +1.625, away -0.125). The sum is unchanged, so league scoring is unchanged. |
| Back-to-back rest | With one team on the second night, the engine's rest terms gave the rested team +2.41. The market's game-specific edge was +2.08 (se 0.27); real +1.68 (se 0.99). The engine's total edge on those nights was +3.87, but the extra came from the absence penalty (below). | Rest effects x0.8 (back-to-back -1.35 -> -1.08 per 100; also the fatigue-based rule in saves). After: +1.95, total edge +2.73. |
| Old-core wear (old teams penalized) | Market weight 0.10 (se 0.06); real 0.33 (se 0.30). The ratings already describe how these players actually played. | x0.2. |
| Missing-player penalty | The test judged absences against the 2026-27 offseason roster, so every offseason signing counted as missing from every 2025-26 game. Fixed first (replays now use each team's real rotation on that date; a player counts as missing only if he did not play). With the right roster the market weight was -0.14 (se 0.04) and real +0.06 (se 0.19). Every bit of the penalty made win-picks worse (dice-free check: 0.2031 with it, 0.1995 without). Tonight's lineup already lacks the player (his minutes go to whoever actually plays), so the extra penalty double-counted. | Off (scale 0.0; the code stays for experiments). League offense level 107.9 -> 105.9 per 100, because the old penalties had been pulling scoring down about 2 points per 100 and the level had been tuned with them on. |
| Recent form (last 10 games' scoring) | The market weights it about 2.4x more than the engine does (real 1.8, se 0.6). It is information from real results that a save cannot have. **Bug found:** in a save, "recent form" read the real 2025-26 box scores, so every team carried its April 2026 form as a fixed bonus or penalty all season, every season. | Weight unchanged. Only games from the last 45 days count (replays unchanged; saves no longer get stale form). |
| Coach effects | Market weight 0.38 (se 0.06), real 0.11 (se 0.29). **Not changed:** the betting test uses the older reputation-based coach ratings and formula, while saves use the staff model. The test may also use 2026-27 staffs for 2025-26 games. That is not evidence about the gameplay formula. | Flagged (see section 6). |
| Overall team strength from player ratings | Market weight 0.66, real 0.80 (se 0.06) after the refit. Tested a 0.9 scale on the gap: win-picks slightly worse (paired +0.0007 and +0.0002, se 0.0004), spread error better (4.16 -> 3.86, 3.96 -> 3.64), team records narrower (.168 -> .161). | Not adopted; the switch stays at 1.0 (the same result the winpick task found at 0.85). |

## 2. Shared pace

Real 2025-26 box scores (1,018 games): the two teams' possession counts correlate 0.86 and differ by about 3 (estimated counts; true differences are smaller). Game pace varies 5.5 possessions. The teams' scores, measured against the market, correlate +0.26: shared pace moves both scores together. The engine drew each team's possessions on its own (spread 4.2), so the two teams' possessions were unrelated.

Now: tonight's pace is drawn once around the average of both teams' expected possessions (spread 4.8). Each team then departs from it a little (spread 1.5). Both are switches in `sim.py` (`SHARED_PACE`, `POSSESSION_SHARED_SD`, `POSSESSION_OWN_SD`). The game uses one extra random number at the start, which deliberately changes every score.

| Within a game (120 games x 40 runs, replayed) | Before | After | Real |
|---|---|---|---|
| Margin spread | 14.64 | 13.47 | at most 14.1 (around the spread; includes the market's own error) |
| Total spread | 14.89 | 17.08 | at most 18.5 (around the total line) |
| Correlation of the teams' possessions | 0.18 | 0.92 | 0.86 |
| Gap between the teams' possessions | 6.0 | 2.1 | ~3.0 (estimated) |
| Average total | 231.7 | 231.6 | |

| Full replayed season (3 seeds) | Before | After | Real |
|---|---|---|---|
| Team win% spread | .159 | .168 | .166 |
| Game margin spread | 18.94 | 16.84 | 16.40 |
| Average winning margin | 15.29 | 13.64 | 13.27 |
| Home win% | .556 | .546 | .555 |

## 3. Starters and Sixth Man

- `sim.game_starters` marks each box-score line `starter: true/false`, five per team. Replayed games use the real box score's starters. In saves, starters are the stored starting five (`save.starting_lineups`, passed to the sim by `save.saved_starting_lineups`) among players available tonight; an open spot goes to the healthy player with the most planned minutes. Teams with no stored lineup (most AI teams) start their five biggest planned minutes. No random numbers are used, and no score changes.
- Season lines count `games_started` / `games_off_bench`; the old top-five-minutes counters stay.
- Sixth Man (`save.SIXTH_MAN_BENCH_RULE = "starts"`) needs more games off the bench than starts. Set it to `"top_minutes"` for the old rule; season lines without start counts fall back automatically. The award text and the slideshow line ("Off the bench in 58 games, started 12.") say which rule applied.

## 4. Scorecards

Betting test, 20 runs a game, all 1,230 games, seeds 1001 and 2001 (no shared runs). Before = this branch's base, which matches the winpick task's runs exactly.

| Engine | Seed 1001: Brier / log loss / spread error / totals error | Seed 2001 | Two seeds pooled (40 runs), Brier |
|---|---|---|---|
| Before | 0.2017 / 0.5940 / 5.22 / 5.84 | 0.2054 / 0.6029 / 5.11 / 5.72 | 0.2007 |
| Context refit only (before the level fix) | 0.2020 / 0.5914 / 4.28 / 6.62 | 0.2051 / 0.5984 / 4.13 / 6.67 | 0.2005 |
| **Final (refit + level + shared pace)** | **0.2047 / 0.5991 / 4.16 / 5.69** | **0.1980 / 0.5830 / 3.96 / 5.72** | **0.1987** |
| Final + 0.9 strength scale (not adopted) | 0.2053 / 0.5992 / 3.86 / 5.69 | 0.1983 / 0.5821 / 3.64 / 5.71 | 0.1990 |

(Market: Brier 0.1962, log loss 0.574. Single 20-run numbers carry about 0.006 of sampling noise, and the final engine deals new dice, so its paired error bar against before is about 0.0035. Seed 1001 moved +0.0030 and seed 2001 -0.0074. Read the pooled column.) Probability calibration (pooled): the engine's slope was 0.79 (1.0 = right); it is now 0.86.

100-run confirmation (seed 1, the user's original setting; before = the winpick task's final run on this base):

| | Brier | Log loss | Spread error | Totals error |
|---|---|---|---|---|
| Before | 0.1974 | 0.5813 | 4.61 | 5.33 |
| **After** | **0.1971** | **0.5793** | **3.37** | **4.91** |
| Market | 0.1962 | 0.5740 | | |

The paired Brier change is -0.0003 (se 0.0023; new dice). Calibration slope 0.82 -> 0.87, and the spread of the engine's log-odds is 1.38 -> 1.28 (market 1.07). **The target "Brier at or under 0.1962" is not met.** At 100 runs the test carries about 0.0011 of its own sampling noise, so the engine's underlying Brier is about level with the market. Spread and totals errors are clearly better, and log loss is better.

Real-stat targets (`calibration_report.py --games 1230`):

| | Before | After |
|---|---|---|
| Replayed season | 18/18 (true shooting .583, points 115.5) | **18/18** (.579, 115.6) |
| Generated games | 18/18 (true shooting .600, points 118.6, offensive rating 116.0) | **18/18** (.589, 116.6, 114.1; real .581, 115.6, 112.8) |

Generated games were scoring 3 points a game too much; they are now 1 too much, because the league level was re-centred.

## 5. Speed

CPU for 400 games: generated 4.35 -> 4.39 s, replayed 4.70 -> 4.91 s (the real-rotation lookup). The first version of shared pace was 32% slower: it computed each team's shot diet twice. Fixed, with identical results (240 game-seeds checked score by score, including starters).

## 6. What's left

1. **Brier still above the market's 0.1962.** The remaining gap is discrimination (who is better), not confidence: recalibrating the engine's probabilities would buy only about 0.0005. Two levers were measured and not pulled. (a) Recent form: the market leans on it much more. It is real-results information that a save does not have, so boosting it would tune the test, not the game. (b) Coach effects measure about half-strength in the test, but the test uses the older coach formula. Next step: give the betting test the save's staff model and the 2025-26 staffs, then refit.
2. Player-based team strength still converts to margin about 20% too steeply against real results (weight 0.80). A flat scale does not help win-picks, so the fix belongs in specific matchup terms. Those terms were too correlated to separate with one season.
3. AI teams have no stored starting five, so their starters are their five biggest planned minutes. Storing an automatic lineup for every team needs the costly automatic starting-five search (~15,000 options a team); not done.
4. Replayed-season absences now come from each team's real rotation. A player hurt from opening night, or for the rest of the season, is not counted as missing (no appearance on that side of the date). The lineup still lacks him either way.

## Tests

- New `tests/test_game_context_margins.py` (15): shared pace (correlated possessions, wider totals, narrower margins, average expected pace, determinism), home court gap and sum, rest/age scales, absence penalty off, stale recent form ignored, real-season rotation, five starters per team in both modes, real starters in replays, coach lineup with a next-man-up fill, stored lineup order, Sixth Man by starts with a switch and a fallback, and the slideshow text.
- Updated `tests/test_fatigue_rest.py` (back-to-back cost follows the rest scale).
- Focused (box score, box variation, accounting, game minutes, lineup fit, simulation narrative, rotation comparison and calibration, user rotation, slideshows, winpick, fatigue/injury/smart rest): 173 OK.
- Core suite (`scripts/run_core_tests.sh`): **337 OK** (2 skipped).

## Files

- `src/nba_gm_data/sim.py`: `HOME_COURT_RATING`/`AWAY_COURT_RATING`, `REST_EFFECT_SCALE`, `AGE_FATIGUE_SCALE`, `ABSENCE_PENALTY_SCALE`, `REPLAY_SEASON_ROTATION` + `replay_expected_rotation`, `RECENT_FORM_WINDOW_DAYS`, `BASE_OFF_RATING` 105.9, shared pace (`SHARED_PACE`, `expected_team_possessions`, `draw_both_scores`), `game_starters`.
- `src/nba_gm_data/save.py`: `saved_starting_lineups` (sim context in both game paths), start counters in `count_award_game`, `SIXTH_MAN_BENCH_RULE` + `sixth_man_bench_counts`, Sixth Man criteria text.
- `src/nba_gm_data/season_slides.py`: Sixth Man line.
- `tests/test_game_context_margins.py` (new), `tests/test_fatigue_rest.py`.
