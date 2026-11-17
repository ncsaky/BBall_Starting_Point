# Q1: Three small GUI behavior fixes (Claude subagent, 2026-11-17)

Status: **review**. Nothing committed. No browser check yet.

## What changed for the player

1. **Next Opponent card after a game.** The W/L banner now stays on the game that was just played. When the banner ends, the card moves to the actual next opponent. If the sim hasn't sent that team's details yet, the card shows the next scheduled team, its date and record, and the line "Rotation updates as the sim reaches this game." If there is no next game, the card says "No upcoming game on the schedule." This covers a finished season, elimination, or a next game the browser doesn't know yet ("Waiting for the next game on the schedule"). If the sim ends or is stopped during a banner, the banner finishes first, then the final dashboard shows the real next opponent.
2. **S then E/W/M shortcut.** The 1.5-second timeout is gone, so you can pause as long as you like between the keys. The prefix is cancelled by:
   - a mouse click anywhere
   - Escape
   - focus moving into a text field
   - any other non-shortcut key, as before.

   Holding S, pressing Shift alone, or using Cmd/Ctrl shortcuts no longer cancels it, and none of them is blocked. Typing in inputs is never taken over. The G prefix works the same way, because both share one mechanism.
3. **Draft lottery grid.** Pick 1 is now at the top left and pick 14 at the bottom right. The reveal order is unchanged: 14 comes first and 1 comes last.

## Where

- `src/nba_gm_data/gui/interface.js`, in `GameInterface` (`keydown`, `clearPrefix`, `init`). The shortcut code lives here, not in app.js, so this file had to change.
- `src/nba_gm_data/gui/app.js`:
  - `updateOpponentDuringSimulation`
  - new `renderSimulationOpponentPanel`, `nextScheduledTeamGame`, `showSimulationNextOpponentPreview`, `finishSimulationOpponentResult`
  - `showSimulationOpponentResult`
  - `advanceSave` and `advance` (sim start and end bookkeeping)
  - `seasonOpponentCard` (no-next-game and preview states)
  - new `draftLotteryGridPicks`, used by `draftLotteryRevealWorkspace`
- New test file: `tests/gui_small_fixes.test.cjs` (5 tests). All of them fail on the old code and pass now.
- Checks:
  - `node --check` passes for both JS files.
  - Core suite (`scripts/run_core_tests.sh`): 329 tests OK, 9 skipped.
  - The other `tests/*.test.cjs` files fail exactly the same tests as with the original app.js and interface.js. Those failures were already there.

## Resume state / notes

- Root cause of item 1: the server streams the next opponent only at the start of the next simulated day, which can be several seconds after the game when the AI trade market runs. A cleaner long-term fix would attach the next opponent to the user's game event in `save.py` (`simulation_live_card_progress` with the just-played game excluded). That was out of scope here.
- Needs a visual check in the running game:
  - the banner, then the switch to the next opponent, during a week sim
  - the preview card's look (header without ranks, placeholder row)
  - the no-next-game message at the end of the season
  - S, wait 5+ seconds, then W
  - S, then a click, then E (should do nothing)
  - the lottery grid in both the default and the unified skin
