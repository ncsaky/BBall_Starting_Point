# S2-TOTALS-MATCHUPS (Stage 2, fourth piece): checkpoint

_Owner: Claude (Opus agent), worktree branch `worktree-agent-ada70276d8f65497d`. Started 2026-11-21._

## Objective
1. Game totals: Stage 2 team pace and scoring level against real 2025-26 and the market totals; find why totals miss
   by 7.5 points; fit fixes on the first half of the season, check on the second; report the total miss before/after.
2. Player-on-player matchups and closeouts: who guards whom, defender skills on make/foul/turnover chances, closeouts,
   rim help on drives, steals off ball pressure; fix free throws for high-volume foul drawers and star turnovers.

## Boundaries
`src/nba_gm_data/stage2/`, `scripts/research/`, tests. Not `sim.py` (default engine byte-identical), not health,
ratings, talent, input estimator, contracts, gui.

## Resume state
- [x] Read board, plan and the three earlier Stage 2 reports; worktree data linked.
- [ ] Totals diagnostic (`scripts/research/s2_totals_check.py collect/report`).

### Totals diagnosis (2026-11-21, 8 runs a game Stage 2, 4 runs today's engine; all 1,231 games)
- League level is close (Stage 2 bias -1.9 vs market; OT rate 2.1% vs real 5.7% in both engines).
- The miss is the game-to-game pattern: Stage 2's expected totals correlate .26 with the market (today's .53).
- A team-level "oracle" (first-half real pace and ratings) correlates .68 with second-half market totals; its pace
  part alone .67, its efficiency part .08. So market totals are about pace.
- Stage 2 team pace spread 0.64 possessions (real 2.05, today's 1.14), corr .55 (today's .84). Pace slope on the two
  lineups' pace habit (T05 summed): Stage 2 37, real 77 (first half) / 102 (second), today's 55.
- Stage 2's team efficiency sum (offense + defense rating) spreads 4.4 vs real 2.8 (noise in totals).
- Fix 1 under way: the defending lineup's pace habit also sets the half-court length (`k_pace_def`), refit k_pace.

### Part 1 done (commit d7eb4a5)
- Both fives' pace habit sets the half-court length (k_pace = k_pace_def = 1.6, fitted to the first-half slope).
- Recent form at today's engine's own strength (k_form_off = k_form_pace = 1).
- Last-shot play when tied or down 1-3 in the last 24 s (.8); overtime 2.1% -> 2.5% (real 4.4%). Small.
- Generated games centre the pace habit on projected minutes (like today's engine). Scorecard 18/18, pace 102.1.
- 8-run replay: expected totals corr with market .26 -> .54; predicted 20-run miss 7.54 -> 6.51; team pace corr
  .55 -> .75; team total error spread 4.7 -> 4.0 (today 2.9). Defense rating spread still too wide (4.3 vs 3.4).
- Odds runs for part 1 (seeds 1001, 2001) running locally -> output/stage2/odds_stage2_totals_*.json.

### Part 2 plan
- matchups.py: assignment (size, stopper on top scorer, rim protector hides on non-spacer); fit to BBI Avg Height
  Guarded and Guarded USG% (s2_matchups_fit.py).
- game.py `matchups` switch: closeouts on catch jumpers, on-ball contest on pull-ups, drive beat chance (burst vs
  containment) on make and foul, post defense, own-man ball pressure + passing lanes on turnovers.
- Turnover card refit with S18/S19/P08/P09 (held-out .74 -> .81 offline).
- Then refit team-strength numbers on first-half spreads; free-throw split check per player.
