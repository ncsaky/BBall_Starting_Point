# PO01 Playoff Stats card (replaces the playoff "league leaders" list)

Status: **review** (Claude subagent, 2026-11-17). Code and tests only; not checked in the browser yet. Nothing committed.

## What changed

The playoff leaders card (a top-nine list with a stat dropdown) is now a **Playoff Stats** table listing every player who has played a playoff game. It opens sorted by points per game, and clicking any column heading sorts by that column. Clicking the same heading again flips the direction.

- `src/nba_gm_data/save.py` `playoff_leaders`: each row now carries the player's full playoff line: every box-score total, the per-game average for each, FG%/3P%/FT% (blank when there were no attempts), plus `player_id`, `player_name` and `headshot_url`. Averages divide by **playoff games only**. The old single-stat fields and sort are unchanged, so the CLI and terminal menus still work. No simulation logic was touched.
- `src/nba_gm_data/gui/app.js`: `playoffDashboardWorkspace` renders the table in the same card slot. New helpers sit right after it: `PLAYOFF_STATS_COLUMNS`, `nextPlayoffStatsSort`, `playoffStatsOrderedRows`, `playoffStatsTable` and `wirePlayoffStatsTable`. Sorting happens in place, so the window, scroll position and keyboard focus are kept. The card is renamed "Playoff Stats" in `seasonalClipboardCards` and gets a 660x430 default size, with a new sizing key so the old narrow size is dropped. The dropdown and `playoffLeaderStat` are removed. The data request asks for all players (`PLAYOFF_STATS_LIMIT` = 500) instead of 9.
- `src/nba_gm_data/gui/card-board.css`: a "Playoff Stats card" block at the end, using the same colors and rules as the Next Opponent and Stats tables. `index.html` cache versions were bumped.

Columns: Player (portrait, rank, name; opens the player card), Team, GP, MIN, PTS, REB, AST, STL, BLK, 3PM, FG%, 3P%, FT%. Counting stats are per game. Rows with no value for the sorted column (for example 3P% with no attempts) always stay at the bottom.

## Tests

- `tests/playoff_stats_table.test.cjs`: 6/6 pass (columns, default sort, toggling, missing values last, accent-insensitive names, markup and aria-sort, style rules).
- `tests/test_playoff_stats_view.py`: 3/3 pass (playoff-only denominators, percentages, old contract).
- The existing `test_foundation` playoff leaders test passes. `scripts/run_core_tests.sh`: 329 tests OK.
- The other JS suites show the same failure counts as the committed version (checked against a `git archive HEAD` copy). There are no new failures.

## Check visually (start or sim into the playoffs)

1. The "Playoff Stats" window appears where "Playoff Leaders" was. It is about 660 px wide, and the top row is the playoff points-per-game leader.
2. Double rule under the headings, small bold heading text, alternating row shading, whole-row hover highlight, and the sorted column shaded from the heading down. Arrows (↓/↑) show the sort direction.
3. Portraits sit on each row's bottom edge and fill the row's height.
4. Click a few headings (and Tab+Enter on them): the order changes, scroll position stays, and clicking again reverses the order.
5. Clicking a player name opens their player card.

## Notes for the coordinator

- **Play-in games count as playoff stats.** `update_playoff_player_stats` records play-in games the same way as playoff games, so a play-in team's players have one or two extra "playoff" games. The real NBA keeps play-in stats separate. Fixing this changes stat recording in `save.py` (and `test_postseason_calendar`'s 7-seed check), so I left it alone.
- **PO02 not done.** Opening Playoff Stats and Minutes automatically at playoff entry means changing `CardBoard.enterPhase`, and `postseason_ui.test.cjs` asserts that only the bracket opens. That is a separate decision.
