# OVERALL-SCALE: one OVR / OFF / DEF scale everywhere

Owner: Claude (Opus agent), worktree branch `worktree-agent-a51c9b4f11d2d9b84`. Status: **in progress**.
User decision: `docs/agents/tasks/stage2-plan.md`, "User decisions (2026-11-21, night)".

## Objective
Card and tables showed different overall numbers for the same player (same order, different scales). Build one display
scale for OVR / OFF / DEF, a straight line in the engine's fitted impact, with anchors chosen so 90+ is rare, rotation
players sit in the 70s and 80s and the end of the bench reaches the high 60s. Display only; AI unchanged.

## Boundaries
`player_profile.py`, `save.py` display functions, `impact_value.py` helpers, display parts of `app_actions.py` / `play.py`
and other modules that show ratings, `gui/app.js` rating rendering only, tests, this file. No AI decision values.

## Resume state
- [x] Worktree symlinks; league distribution studied; anchors chosen (overall 71.5 + 3 x impact, offense 75 + 3 x,
      defense 72 + 6 x).
- [x] Core: `impact_value.DISPLAY_LINES` + helpers; `save.player_display_attribute_summary` on the new scale;
      `save.player_engine_attribute_summary` (old behaviour) for AI matching; card = tables.
- [x] Switched: card, rotation/live payload, development trend lines, prospect cards and draft board (now / potential /
      floor / ceiling), fantasy growth outlook, extension projections, season slides, trade-wants thresholds, CLI tables.
- [x] tests/test_overall_scale.py, tests/test_player_profile.py updated.
- [ ] Focused + core test suites, scorecard run, GUI screenshots, report.
