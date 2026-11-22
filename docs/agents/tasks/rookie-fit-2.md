# ROOKIE-FIT-2: 2026 rookies' day-one ratings, redone

_Status: in progress. Claude Opus agent, worktree branch `worktree-agent-a1a01f15e16d6caf4`, started 2026-11-22._

## Objective
Redo the 2026 rookie class's day-one level so it measures ability, not playing time:
- fit from rookies who played (per-possession impact, corrected for who gets minutes; no shrink toward a floor by minutes),
- college stats + age + draft slot / consensus rank, weights from history (fit old drafts, check later ones),
- public draft rankings and scouting notes recorded with attribution as labelled evidence,
- this season's real games (2026-27, small sample) as a check with light weight at most.

## Boundaries
- May touch: `src/nba_gm_data/input_estimator.py` rookie path, `scripts/build_player_inputs.py` rookie step,
  `scripts/research/rookie_*`, `data/research/rookie_*`, rebuilt `data/canonical/player_inputs_2026_27.json(.gz)`,
  rookie tests, this file, board row.
- Keep: college skill-shape mapping, rookie step last, veterans byte-identical, analyst claims last, potential unchanged.
- No Azure (paid data stays on the laptop). Max two heavy jobs, `nice -n 10`, load average under 20.

## Resume state
- Git-ignored inputs linked into the worktree: `data/research/barttorvik` and `data/research/bbi/captures/fanspo_tools`
  (symlinks), injury evidence v2-v4 and the sqlite (symlinks); `data/canonical/player_inputs_2026_27.json` written from
  the committed .gz (main checkout's copy is the pre-ROOKIE-FIT one; never symlink it, the builder writes it).
- Step 1 (reading) done.
