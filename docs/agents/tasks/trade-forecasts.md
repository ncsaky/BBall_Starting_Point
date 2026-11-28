# TRADE-FORECASTS: four factors for any roster, morale after a trade

Progress: 7/7 - done, ready for the coordinator's review

Owner: Claude (side session, branch `claude/dreamy-goldwasser-0f64ba`). Coordinator reviews and merges.

## Objective
1. `project_four_factors(canonical, save, team_id, roster)`: projected eFG%, turnover %, offensive rebound % and
   free-throw rate, offense and defense, on the Profile tab's scale, from the engine's own player inputs and the
   coach's projected minutes. Checked against real 2025-26 (real rosters, real minutes) and against today's
   preseason fallback; if clearly better it becomes the fallback in `dashboard_four_factors`.
2. Trades move stored morale and chemistry; `project_trade_morale(canonical, save, proposal)` returns exactly the
   before/after numbers the stored effect applies.
3. Tests, full suite on Azure (`--workers 2`), message the UI polish session with the two names and shapes.

## Boundaries
Identity, four-factor, rotation-projection and morale code; display-data helpers in `app_actions.py`; tests; this
file. Not `gui/`, `stage2/`, coach or free-agency code, or the board.

## Steps
1. Read rules and engine code
2. Build the roster four-factor projection
3. Check it against real 2025-26
4. Trades move stored morale and chemistry
5. `project_trade_morale`
6. Tests (focused, then full suite on Azure)
7. Report, message UI session, commit

## Report

**TL;DR**
- Any roster now gets projected Four Factors (offense and defense) worked out from the engine's own box-score rules
  and the coach's minutes. It matches what the engine produces within about 0.1-0.4 points and tracks the real
  2025-26 season far better than the old preseason formula, which it now replaces on the Profile tab.
- Every trade now moves stored morale and chemistry once, and the trade room can show the same numbers beforehand.

### Four Factors for any roster
`project_four_factors(canonical, save, team_id, roster=None)` and `project_league_four_factors(canonical, save)` in
`src/nba_gm_data/four_factor_projection.py` (also importable from `app_actions`). It doesn't simulate games. It takes
the engine's own steps in the same order: team features over tonight's pool (the coach's projected minutes, top 14,
scaled to 240), expected possessions and points against every other team at home and away, each player's share of the
points, his free throws, threes and own two-point misses, turnovers moved by the opponent's pressure and his team's
passing, the miss fill toward the possessions left, and the offensive rebound share. One measured factor:
the engine keeps 95.2% of the free throws a player's points imply (on a night his made threes need the room, free
throws give way).

Checks (script and results: `output/trade-forecasts/check_real.py`, `check_real.json`):

| Real 2025-26 rosters, real minutes | eFG% | turnover % | off. rebound % | FT rate |
|---|---|---|---|---|
| Projection vs real: correlation | .87 | .74 | .78 | .87 |
| Old preseason formula vs real | .55 | .67 | .73 | .59 |
| Projection vs real: average miss (points) | 1.4 | 0.7 | 1.8 | 1.8 |
| Old formula vs real: average miss | 1.9 | 2.1 | 2.5 | 2.0 |
| Projection vs the engine playing the same pools (6,960 games) | within 0.3 | 0.2 | 0.1 | 0.2 |

The old formula also squeezed teams together (its spread was a third to a quarter of the real one). Most of the
projection's remaining miss is the engine's: it runs eFG% about 1.4 high and free-throw rate about 1.6 low against the
real league. The projection's job is to show what the engine will do (rule 4), so it keeps that. On the defensive side
the engine has two gaps: a defense never changes its opponents' offensive rebound % (only the shooting team's
rebounding counts), and opponents' free-throw rate barely depends on the defense (correlation with real .26). Both
are engine follow-ups, not changed here.

`dashboard_four_factors` uses the projection for any team without games yet (the identity formula stays only for the
old rating set). Cost: about 0.6 s the first time the Profile tab is built before opening night.

### Morale after a trade
`src/nba_gm_data/trade_morale.py`: `project_trade_morale(canonical, save, proposal)` returns before/after numbers;
the two-team and multi-team trade paths (`transactions._apply_trade_to_state`,
`multi_team_trades.apply_multi_team_trade_to_state`) work out the same effect on the league before the trade and
store its "after" values. A test applies a real trade and checks the stored numbers equal the projection.

What each effect is based on:
1. **Role:** players whose projected minutes change by 2+ move 60% of the way along the save's own opening
   minutes-to-role scale (28+ minutes 60, 18+ 56, 10+ 51, less 46), and overall morale by that scale's 0.35 weight.
   Basis: role and playing time are what players most often cite when they want out; the size is the save's own scale
   (judgment).
2. **Traded player:** overall -1.0, and his confidence in his team moves halfway to his new team's morale (judgment,
   kept small).
3. **Chemistry:** -8 points times the share of rotation minutes that changed hands (a starter swap about -1, a
   blockbuster about -3). Basis: roster continuity is a small real early-season edge in NBA results; games then move
   chemistry as before.
4. **Stars:** one of a team's two best players (24+ projected minutes) leaving costs the team 1.5 morale and 2.0
   confidence and each staying teammate 2.0 confidence and 0.7 morale; an arriving star does the opposite (judgment,
   modest).

Not possible: the morale model has no friendships or other player-to-player links, so a traded close friend changes
nothing. Morale is stored and shown but the game engine does not read it, so game results are unchanged and no random
numbers move. Cost: about 0.2 s per applied trade (AI trades included).

### UI hand-over
The session "UI polish pass Stage A" was not reachable from here (not listed among live sessions), so the two function
names and their output shapes are in the shared notes folder: `side-session-notes/.../trade-forecasts.md`. Short
version: `project_four_factors(...)` -> `{offense: {efg, tov, oreb, ftr}, defense: {...}, offensive_rating,
defensive_rating, net_rating, minutes: [...]}`; `project_trade_morale(...)` -> `{teams: [{team_id, before, after,
rotation_turnover, reasons}], players: [{player_id, name, minutes_before, minutes_after, before, after, reasons}]}`.

### Tests
`tests/test_trade_forecasts.py` (7 tests): projection vs the engine on the same rosters; payload shape and a roster
change; the preseason Profile tab uses the projection; the role scale; every proposal shape; a star trade's effects;
an applied trade stores exactly the projected morale. Nearby suites pass (multi-team trades, trade application audit,
Profile/dashboard). Full suite on Azure (`--workers 2`): worker 1 ran 1,367 tests, all passing; worker 2 was killed
by the machine (out of memory, exit -9, the known problem with ~130 modules in one process) after a burst of 59
errors, so its 130 modules were rerun one process each: 1,351 tests, all passing (one module skips itself at import:
packaging build tools absent). Total 2,718 tests, no failures.
