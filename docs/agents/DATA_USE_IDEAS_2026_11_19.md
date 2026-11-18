# Using the data we have but don't use yet (brainstorm, 2026-11-19 night)

Ranked by (value to the game) x (how much the data supports it). "Effort" is rough: S = a session, M = a few, L = a project.

## Already in use
Leaderboards (664 metrics) -> player inputs/ratings; LEBRON history -> player value fit; playoff box stats -> playoff
translation; injury tracker -> injury model v2; growth curve -> Codex DEV-TUNE (aging, running now).

## High value

1. **Lineup synergy (Lineup Explorer: 61,037 real lineups with talent grades and net rating; xPoints lineups with exact
   possessions).** Fit how a five-man unit's grades (spacing, rim protection, creation, ball movement, defense) turn
   into net rating beyond the sum of its players: does a second shooter matter more than a fifth? does rim protection
   cover bad perimeter defense? Use it to calibrate the engine's lineup/spacing interaction terms and to validate the
   sim's lineup net ratings. This is the "distinguishing players by fit" goal at the team level. Effort M.
2. **Player value from several impact metrics (Progression: EPM, RAPM variants, DRIP, DPM, estimated RAPTOR, BPM per
   player-season).** Fit the impact-value model to a blend instead of LEBRON alone: less single-metric bias (e.g. LEBRON's
   box prior), multi-year stability, and a direct check on players we suspect (Brunson, Trae, Embiid). Effort S.
3. **Prospects from NCAA data (blocked on sign-in).** College box/impact profiles by archetype -> realistic generated
   prospects (what a #3 pick's college profile looks like), and -> how college profiles translate to NBA inputs and
   growth (with Growth Curve projections for recent draftees). Fixes the "generated prospects look like veterans" class
   of problems at the source. Effort M-L.
4. **Role Labs (11,402 player-season entries + model coefficients): estimated impact of moving a player to another
   offensive/defensive role.** Let coaches/AI pick better roles (a Shot Creator miscast as a Stationary Shooter), and let
   trade AI value role fit. Ties to the coaching overhaul (head coach rotation/role decisions). Effort M.
5. **Team-level calibration targets (Team Leaderboards: 30 teams x 321 measures x 13 seasons; xPoints game database:
   1,230 team box scores with FGA, fouls by type, paint/second-chance/fast-break points, expected points).** Our real
   box-score file lacks FGA; this fills it. Calibrate game-to-game spreads (team FG% sd, turnovers, fouls), shot mix by
   team style, and add multi-season targets for the stat scorecard. Effort S-M.
6. **Playoff talent grades (4,344 three-year playoff windows x 386 measures).** Refit "playoff translation" on these
   talent grades instead of box Game Score (fixes the Brunson gap the box score misses), and add playoff-specific
   modifiers (hunted defenders, shot-diet changes). Effort S.

## Medium value

7. **Hot/cold form (Daily LEBRON game-by-game; value trends).** Measure how much real players' game-to-game impact varies
   and how streaky it is; calibrate the "hot or cold hands" part of the coach's in-game minutes (project rule 8). Effort S.
8. **Coach development effects (Growth Curve per-coach actual-minus-projected, 56 coaches).** Calibrate real head
   coaches' player-relations/development ratings from evidence instead of reputation lists (noisy: system and roster
   effects; use shrinkage). Effort S.
9. **Shooting projections with uncertainty (Fanspo shooting talent).** Regression of shooting ratings toward true talent;
   development ranges for shooting; scouting uncertainty displays. Effort S.
10. **Minutes and availability grid (2026-27).** Check the coach model's minutes and games-missed against Basketball
    Index's projections team by team; seed the AI's preseason expectations (used by staff reputation now). Effort S.
11. **Matchup data (matchup difficulty, guarded-by data in the Leaderboards).** Who-guards-whom assignment in the sim and
    hiding weak defenders (defensive coordinator "matchup scheming" now has an effect to calibrate). Effort M.
12. **Expected points vs actual (xPoints).** Separate shooting luck from skill: regress over-performing teams in AI
    evaluation; calibrate the sim's shooting variance. Effort S.

## Lower value / flavor
13. Referees (84 officials with game logs): referee crews nudging foul rates and pace; mostly flavor. Effort S.
14. Similarity (not captured yet): "plays like" comps on player cards and for generated prospects. Effort S after capture.
15. Injury tracker extras (body-part history views, durability labels on player cards). Effort S (GUI).

## Fable 5.2: where the expensive model would earn its keep
Not for routine building (Opus handles that well, per the user). Best fits, in order:
1. **One adversarial "realism review" once the overhauls settle** (after DEV-TUNE, NCAA prospects and lineup synergy
   land): give it the scorecards, the player-model doc, the engine roadmap and these data notes, and ask it to find
   where the simulation will feel wrong to a Nerd Sesh / Basketball Index viewer, what we are measuring badly, and what
   evidence would settle each doubt. One reset, high leverage, little code.
2. **Design of the prospect generator from NCAA + growth data** (a hard modeling problem: college-to-NBA translation,
   uncertainty, archetype mix by draft slot). Use the second reset here, after NCAA data is captured.
Recommendation: save both resets until NCAA data is in and the current overhauls are validated (a few days).
