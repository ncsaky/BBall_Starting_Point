# RATINGS-FOLLOWUPS: the five follow-ups from the Golden State ratings audit

Progress: 6/9 - checkpoint commit, then merging the rookie-season shot fix for the new rookie-involvement step

_Status: **in progress**. Claude Opus agent, worktree branch `worktree-agent-a7aab1745f3a463f5`, started 2026-11-22._

## Objective
Carry out the five follow-ups the user approved from RATINGS-AUDIT-GSW (`docs/agents/tasks/ratings-audit-gsw.md`):
1. Thin-sample players pulled toward the real level of players with the same evidence (minutes and years in the league).
2. A measured return-from-injury step for Achilles and knee-ligament tears in a player's 30s.
3. High-usage scorers' value (Brunson 39th of 104 against analysts' 6th): fix the value formula at its cause.
4. Aging also moves physical tools, where evidence supports it.
5. Replay scorecards (betting test, real-stat scorecard) undo the opening-day projection, so they judge 2025-26 ratings.
Plus a light check of the Warriors' gaps (Lendeborg vs Payton II, Horford, Podziemski, Green), no individual edits.

## Boundaries
- May edit: `scripts/build_player_inputs.py`, `src/nba_gm_data/input_estimator.py`, the player value fit and
  `ratings_model.py` value code, the two scorecards' replay code, research data and scripts, the rebuilt
  `data/canonical/player_inputs_2026_27.json.gz`, the value fit file, tests, this report.
- Not: `ratings_model.apply_input_deltas`, `health.py`, development, coach, rotation or simulation code (ROOKIE-SEASON),
  `draft.py`, `draft_scouting.py`. No Azure. At most one heavy job of mine at a time (ROOKIE-SEASON has priority).

## Plan (8 steps)
1. Read the audit and set up the worktree.
2. Step 5 first in time (it has to be checked before steps 1-4 exist): replay scorecards undo the opening-day
   projection; show both return to their pre-audit values.
3. Step 1: thin-sample players.
4. Step 2: return from major injury.
5. Step 3: high-usage scorers' value.
6. Step 4: aging moves physical tools.
7. Warriors check and gates.
8. Report.

## Resume state
- Worktree links (git-ignored, never commit): `.venv`, missing BBI files under `data/research/bbi/` linked from the
  main checkout.
- Outputs: `output/ratings-followups/` (`run_gates.sh <tag>` runs both scorecards; `summ.py <tag>` summarises).
  Also linked: `output/ratings-consensus/raw`, `output/ratings-audit-gsw/bbref` from the main checkout.
- Step 5 done: `ratings_model.replay_last_season_inputs` + `install_inputs_model(..., replay_last_season=True)` from
  `sim.load_sim_context`'s replay branch; builder records `replay_undo` in each shifted record's evidence notes.
  Pre-audit inputs on this branch reproduce the audit's "before" exactly (tags `preaudit`, `step5`).
- Step 1 done in builder (`thin_sample_targets`, evidence `data/research/thin_sample_level_2026_27.json`).
- Step 2 done in builder (`injury_return_targets`, evidence `data/research/major_injury_return_2026_27.json`).
- Step 4 research: `data/research/physical_aging_2026_27.json` - tracked speed shows no age decline, dunk share no
  age pattern, blocks -3%/yr at 27-32, rebounds -4%/yr at 33+. Too small to move physical tools (under half a grade
  point a season); cards already show the age gap via the physical prior. Decision: no physical move.
- Step 3 suspects: defense weight on involvement (-0.217, usage lowers defensive value), analyst gap split 70/30 by
  league proportion (scorers get 30% of their analyst gap on defense they can't reach), ridge shrinkage.
