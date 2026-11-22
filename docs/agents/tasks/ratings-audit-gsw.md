# RATINGS-AUDIT-GSW: is Lendeborg underrated, and what does it say about the league's ratings?

_Status: **in progress**. Claude Opus agent, worktree branch `worktree-agent-ae9d0da15fccdd0ec`, started 2026-11-22._

## Objective
Check Yaxel Lendeborg and Golden State's rotation against journalism, scouting and analyst reports and against real use,
then sweep the league for players far from analyst consensus. Correct only what independent evidence supports, with
attribution. Never move a rating to hit a minutes or outcome target.

## Boundaries
- May edit: analyst claims and evidence data, `input_estimator.py`, `scripts/build_player_inputs.py`, rebuilt
  `data/canonical/player_inputs_2026_27.json.gz`, research data and scripts, tests, this report.
- Not: development / coach / rotation / simulation code (ROOKIE-SEASON), `draft.py`, `draft_scouting.py` (Codex).
- No Azure. Laptop load: `nice -n 10`, check `uptime`, at most one heavy job of mine.

## Resume state
- [x] Worktree links: `.venv`, BBI normalized data and captures, `output/ratings-consensus/raw` (git-ignored; never commit them).
- [x] Snapshot before: `output/ratings-audit-gsw/snapshot_before.json` (`rookie_fit_check.py snapshot`).
- [x] Real 2026-27 pages copied to `output/ratings-audit-gsw/bbref/` (from ROOKIE-FIT-2, fetched 2026-11-22).
- [x] Research script `scripts/research/ratings_audit_gsw.py` (team table).
- [x] Journalism sweep for Golden State (subagent; notes below).
- [x] League sweep (`ratings_audit_gsw.py league|lag|thin`): two systematic builder problems found:
  1. no age projection: veterans start at their 2023-26 measured level (new careers start on opening day, no
     development before) -> young under, old over; analyst top-100 gap by age +14 (19-21) ... -14 (34+);
  2. players with no NBA minutes 2023-26 sit at role-average priors (mean value +0.81, above measured bench players).
- [x] Fixes in `scripts/build_player_inputs.py` (`project_veterans`, after the rookie step): age curve
  `data/research/age_projection_2026_27.json` (500 players), no-track-record level
  `data/research/no_track_record_level_2026_27.json` (68 players). Lendeborg claims (6) added to analyst claims.
- [x] First age-only build checked (`output/ratings-audit-gsw/snapshot_age.json`); found Jr./III name-match bug
  (Butler skipped) -> fixed with `_evidence_name`.
- [ ] Combined build -> `output/ratings-audit-gsw/inputs_v2.json` (running), snapshot, then copy to canonical.
- [ ] Tests (`tests/test_veteran_levels.py`), gates, short sim, report.
