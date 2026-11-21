# Stage 2: retiring the old ratings system (plan for review)

_Drafted overnight 2026-11-21 by Claude (coordinator) from a read-only code survey. Not started. Needs the user's decisions below._

## TL;DR
- **Stage 2 is really two jobs.**
  - **(A) Remove the old-ratings switch.** It's mostly mechanical, and games don't change.
  - **(B) Replace the 15 hidden "traits" that the engine still runs on.** Since Stage 1 they're computed from the new 94 ratings, but the simulation, AI valuation, injuries, development and the draft all read them. Removing them changes results, so both scorecards have to be re-checked.
- **One problem found on the way (rule 4):** the player card and the tables may show different overall numbers for the same player. The readiness notes had Jokić at 95.4 on the card and 77.9 in tables. This needs checking and fixing either way.
- **Recommendation:** do job A plus the display fix first, which is safe and quick. Then do job B one area at a time, each step with both scorecards.

## What the survey found (details in the coordinator session, 2026-11-21)
- **The switch.** The old system can still be chosen per save, by an environment variable, or by a command-line flag (`ratings_model.py`, `save.py`, `cli.py`, `app_actions.py`).
  - A save with no recorded choice falls back to the OLD system (`ratings_model_for`). That's a trap for hand-built test data.
- **Old-only branches.** These already have new-system twins:
  - development (`save.py` helpers, `health.py` volatility, `development_outlook.py`);
  - simulation stat formulas and assist model (`sim.py`, `box_rates.py`);
  - injury-fill scales (`absence_fill.py`);
  - AI valuation ordering (`transactions.py`);
  - the old player card (`gui/app.js`).
- **The 15 traits are still the engine's working currency.** About 30 modules read them directly: health and injury hazards, spatial and offense features, development focus, draft and prospect generation (rookies are seeded from old-style traits), roster forecasting, coach cards, narrative and others.
- **The overall rating is anchored to the old formula.** The new value is mapped onto the old overall formula's league distribution, so every threshold written for it still works: superstar cutoffs, max-contract and extension triggers, trade breakpoints, draft boards, waivers and minutes. That's about 75 call sites.
- **The new model's fit uses the old trait table as its target scale** (`install_inputs_model` / `fit_adapter`). Changing that shifts every tuned constant (offense calibration, box-rate fits and others).
- **Tests and fixtures pinned to the old system:**
  - about 11 test files (`test_foundation` in three places, `test_forward_tuning`, `test_imported_rookie_ratings`, `test_imported_tail`, `test_player_tuning`, `test_player_lifecycle`, `test_player_profile`, `test_ratings_model`, `test_advance_runtime_reuse`);
  - the 2036 ten-season fixture, which was built on old ratings only;
  - several scripts.

## Suggested order
1. **Make the old system unreachable.** No result change for new-system saves.
   - Remove the flag and the environment variable.
   - Make the default always new.
   - Rewrite the pinned tests.
   - Gate: core tests, and byte-identical results for a new-system save.
2. **Delete the dead old-only branches.**
   - Gate: both scorecards unchanged.
3. **Display (rule 4).**
   - One overall number everywhere: card, tables and AI.
   - Remove the old card.
   - Decide whether the 15 hidden traits should still appear anywhere (the league trait leaders and the ratings guide show them today).
4. **Replace the traits as the engine's currency (job B), one area per task, each with both scorecards and an odds check:**
   1. injuries and health;
   2. draft and prospect generation, using the 94-input generator only;
   3. offense and spatial features;
   4. the overall formula itself, re-expressing every threshold as a league percentile.

   Only after all four: drop the trait table, the old inference code and the old fixtures, and refit the tuned constants.

## Decisions for the user
1. **Do Stage 2 now, or after more playtesting?** Steps 1–3 are safe now. Step 4 changes how the game plays, so it may be better after your playtest notes.
2. **Old saves:** reject them with a clear message, or migrate them? Rule 5 says old saves don't matter, so rejecting is simplest.
3. **Hidden traits on screen:** should the league trait leaders and the ratings guide (which show the 15 internal traits) go away entirely? The 94-input player card would then be the only ratings view.
4. **Job B scope:** all four areas, or only the ones that measurably improve realism (injuries and the draft first)?

## User decisions (2026-11-21, night)
- **The overall rating scale** (applies to overalls; individual skill ratings keep a wider range):
  1. **Real players represented accurately, and the distances between them accurate. This is the top priority.**
  2. **Intuitive for a new user:** 90+ means elite and stays rare (no 2K-style inflation, where 90s lose their meaning). Most rotation players sit in the 70s and 80s, extending into the low 70s and a little into the high 60s.
  3. If the ratings are realistic, the engine will be roughly realistic.
- **Start Stage 2:** build small parts, spot-check them, and estimate how each area would integrate.

## Scheduled
- **OVERALL-SCALE:** one overall scale everywhere (card, tables, lists), linear in the engine's value, with the anchors above. Display only; the AI keeps its internal value. Running now as a light job.
- **STAGE2-A:** steps 1–2 (old system unreachable, dead branches deleted; gate: byte-identical new-system games and unchanged scorecards). Starts at the next free heavy slot.
- **STAGE2-B-PROBE:** measurement-only prototype of injury risk read from the 94 inputs instead of the traits, plus an integration estimate for each job-B area. After STAGE2-A.

## User correction (2026-11-21, night): Stage 2 is a new engine
"We're starting a new engine largely from the ground up. I don't expect byte for byte identical results at all. But if we get lucky, perhaps we could get even better results than we were getting before."
- Stage 2's goal is a new engine driven by the 94 inputs. It is judged by beating today's results on both scorecards (real-stat targets and the betting test), not by matching today's games.
- The byte-identical gate is dropped. Retiring the old switch (job A) becomes housekeeping done along the way.
- Next: survey the experimental possession engine (Track C) and the engine roadmap, then write a revised plan with small first components, each spot-checked against real data on its own before full games.

## Revised plan (2026-11-21, after the engine survey)
The user's framing: build on what exists (roles, coaches, injuries and rust, ratings, data), keep speed realistic, and beat the simpler engine on both scorecards.

**What exists:**
- **The experimental engine (Track C)** has good physics pieces:
  - shooting and finishing by mode and zone (`offense_response.py`, which reads all 15 shooting/finishing skills);
  - rim defense (`interior_defense.py`, `shot_geometry.py`);
  - screens (`screen_navigation.py`);
  - drives, help, kick-outs and passes (`creation_passing.py`);
  - choices (`action_choice.py`);
  - a shared 94-input reader (`experimental_inputs.py`).
- **Its limits:**
  - It has never been scored against real stats or betting odds. Its own reviews call it uncalibrated.
  - It runs on hand-made 6-12 player packets, not the league's 691 estimated players.
  - It lacks lineups, substitutions, a clock, transition, post play, rebounding skill (S29-S32), off-ball movement and 12 of 18 passing inputs.
  - It costs about 0.3-1.5 s a game, against about 0.01 s today. The budget allows roughly 0.02-0.04 s a game.

**The approach: a fast possession engine, built in pieces, each measured.**
1. **Seam and side-by-side scoring.** Add an `engine=` choice where the game sim branches (`sim_game_with_context`, sim.py:606), and pass it through `calibration_report.py` and the betting test. From day one, every new piece is scored next to today's engine on both scorecards.
2. **League input bridge.** Compile all 691 players' 94 inputs (estimated, prior or unknown) into the typed profiles the physics pieces need, with one documented rule for unknown cells (the prior with its uncertainty, never a hand control).
3. **Spot-check each component against real data before full games:**
   - shooting and finishing by zone and mode against real 2025-26 per-player shooting;
   - turnovers and steals;
   - rebounding (built new from S29-S32 and T12/T13);
   - fouls and free throws.

   Each one is compared with how well today's engine does the same.
4. **Fast rules fitted to the exact pieces** (roadmap S2.4). The exact physics stay as the reference, and live games use cheap fitted rules. The target is about 0.2-0.4 ms per possession.
5. **Whole-game frame.** Five-man lineups, a clock and quarters, substitutions through the existing coach model (`game_minutes`, foul trouble, fatigue, blowouts, the user's minutes targets), injuries and rust, bonus and foul-outs, and end-game. Roles and coach usage decide who initiates and which action.
6. **Gate (roadmap S2.6).** Beats today's engine on both scorecards, meets the speed budget, and survives a multi-season run. Only then does it become the default. Today's engine stays selectable.

**First tasks:**
- **S2-SEAM-SHOOTING:** the seam (step 1), the input bridge (step 2) and the shooting/finishing spot-check (step 3, first part).
- **S2-REBOUND-FOULS:** the rebound and foul spot-checks.
- **Then** the first fast possession loop.
