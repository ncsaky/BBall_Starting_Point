# DEV-CURVE: fit player development and aging to real NBA evidence

_Owner: Claude (Opus agent, worktree branch `worktree-agent-a1caf3189f4cf1a6f`). Started 2026-11-21. User approved._

## Objective
Make development and aging match the real-NBA evidence (`development-evidence.md`, `data/research/development_evidence.json`):
growth by age and starting level (biggest at 19-21, peak 25-26), decline after 30 (stars vs others at 33-35),
about one first-time top-five player a year, about two of five top spots changing hands a season, young-player and
draft-slot star odds, late bloomers and busts. Fix the two causes named by RATING-CEILING: stars stop growing at 23-24
(and `cap_room` slows any hidden rating at 88+ to 8%), and physical inputs over-react to development.

Measure like with like: the game's own box-score impact (a BPM-style estimate from simulated season totals, same
1,000-minute filter, same thirds) against the real table. Ratings first: change development rules, never players.

## Boundaries
May touch: `health.py` (development functions only), `development_outlook.py`, `ratings_model.py` (development-to-inputs
mapping and `GRADE_POINTS_PER_TRAIT_POINT` only), `talent.py` if a draftee ceiling binds, `scripts/research/`, tests,
this file. Not: `trait_adapter.py`, `impact_value.py`, `stage2/`, `sim.py`, injuries.

## Gates
- Real-stat scorecard 18/18 (`scripts/calibration_report.py --games 1230 --mode replay-real-minutes`).
- Betting test short runs, seeds 1001 and 2001 (`validate-season-probabilities --runs 20`).
- Five-season run before/after on the Azure worker, compared against the evidence tables.

## Resume state
- Worktree data symlinked; inputs unpacked.
- Before run (HEAD 7b05da8, clean copy in scratchpad `dev-curve-before`) launched on Azure:
  `output/dev-curve/before` (seed 17, GSW hands-off, 5 seasons). Laptop was at load ~200, swap nearly full at start:
  no heavy local jobs until it clears.
- Done (committed aacac33 + later): `scripts/research/dev_curve_box.py` (box-score BPM estimate, fit R2 0.87 on
  2,323 real seasons; `prior` prints real growth with the level taken one season earlier), `dev_curve_report.py`
  (`real`, `talent <dir>`, `game <run dir>`), `dev_curve_talent.py` (development-only probe, `--params` JSON overrides
  health/ratings_model constants for tuning), `dev_curve_spread.py` (writes the spread table).
- Code: `ratings_model` routes by league spread (`_development_steps`, needs `data/canonical/development_input_spread.json`
  from dev_curve_spread.py), no grade clamp at 100. `health`: `curve=` keyword (INPUTS_CURVE default / LEGACY_CURVE);
  inputs curve has no cap_room and no 84+ focus penalty; tunable INPUTS_AGE_FACTOR, INPUTS_YOUTH_END/SPAN,
  INPUTS_ROLE_FLOOR, INPUTS_DECLINE (initial guesses, not yet tuned). development_outlook passes the curve.
- Key evidence finding: with the starting level taken from the season BEFORE, real growth barely depends on level
  (ages 21-22: bottom +0.76, top +0.88; 23-24: +0.32 / +0.28). Same-season thirds look level-dependent only because
  of regression to the mean. Talent target = Basketball Index LEBRON "all" curve (engine impact is in LEBRON units):
  19 +1.05, 20 +0.77, 21 +0.52, 22 +0.28, 23 +0.13, 24 +0.21, 25-27 ~0, 28-29 -0.1, 30-32 -0.21, 33-35 -0.47, 36+ -0.65.
- Next: when laptop load allows: (1) talent probe on HEAD code: `PYTHONPATH=<before copy>/src:scripts/research`
  -> output/dev-curve/talent-before; (2) build spread table; (3) tune; (4) after run on Azure.
