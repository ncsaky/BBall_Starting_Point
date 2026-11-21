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
- Next: box-score impact estimator + measurement script; fast development-only talent probe.
