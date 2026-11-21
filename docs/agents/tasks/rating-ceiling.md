# RATING-CEILING: remove the hidden top-end ceiling

_Owner: Claude (Opus agent, worktree branch `worktree-agent-a080338aa9203d993`). Started 2026-11-21._

## Objective
The ten-season check (`ten-season-findings.md`) showed the top of the league flattening and top values bunching onto
exact repeated numbers. Confirm where elite players stop rising, then remove the ceiling at its source without
clipping and without changing anyone's current rating.

## Boundaries
May touch: `trait_adapter.py`, `ratings_model.py`, development functions in `save.py` / `health.py`, `impact_value.py`,
tests, this file. Not: trade, free agency, offseason, GUI, `stage2/`.

## Resume state
- [x] Worktree set up (symlinks, inputs unzipped). `_before_src/` = copy of the package with HEAD's three engine
      files, used only to run "before" measurements (delete before the final commit; never commit it).
- [x] Probe (scratch `probe.py`): cause confirmed, see below.
- [x] Fix in `impact_value.py`, `trait_adapter.py`, `health.py`; tests added.
- [x] Today's league: all 691 players identical (traits, value, sim impact, display).
- [ ] Scorecards before/after (running locally, sequential, background).
- [ ] Five-season run on the Azure worker (job `rating-ceiling`, queued behind `ten-season`), fetch to
      `output/rating-ceiling/run`; compare with `output/ten-season-partial/league_health.json`.
- [ ] Core tests + match suite, final commit, report, board row to review.

## Findings (probe: uniform development of +2..+30 hidden-rating points, routed onto the inputs)
1. **The AI's player value stopped at the opening-day best.** `impact_value.mapped` placed each player's fitted
   impact on the old summary scale by league rank, using a step function over the baseline table with a hard top.
   Nobody could be valued above 78.0 (Jokić's opening value). Wembanyama hit it after +6; Jokić and
   Gilgeous-Alexander were already at or next to it. The fitted impact itself (and the display OVR, linear in it)
   kept rising: Wembanyama impact 7.1 -> 12.5, display 92.8 -> 108.9, value frozen at 78.0.
2. **The game sim's player strength stopped the same way.** `impact_value.sim_impact` uses the same map onto the
   sim's own impact scale: hard top 82.05.
3. **Exact repeated values.** The step map sent every prediction between two baseline players to the midpoint of
   their values, so developed players landed on a handful of numbers: 73.8 = (73.6+73.9)/2, 74.1, 75.0 =
   (74.2+75.7)/2, 76.8 = (75.7+78.0)/2. Those are exactly the repeated numbers in the ten-season run. The baseline
   table is also rounded to 0.1 with ties (two players at 74.2, two at 73.9), which gives flat stretches even with
   interpolation.
4. **The 15 hidden ratings stopped at the old trait table's top.** Input -> percentile and composite -> trait were
   step maps clamped to [0, 1], so inputs past the league's best changed nothing (4-8 of 15 traits pinned for the
   top players at +18..+30).
5. **Development stopped one rating outright.** `monthly_trait_delta` tapered gains to zero at hidden rating 100
   (a guard for the older ratings' stored 0-100 bound). Wembanyama's rim deterrence is 105.5 (the uncensored table
   goes to 106.6), so he could never grow it. Soft slowdowns remain by design: `cap_room` (growth x0.08 at 88+) and
   the x0.68 focus at 84+. Wembanyama's expected yearly gain averages 0.78x an average young starter's.
6. Not binding: the input grade clamp at 100 (league max grade 92.5), the summary's 1-99 clamp (value max ~78).

## Fix
- `impact_value.mapped`: continuous piecewise-linear map (`_carry`, the same map `impact_from_summary` already
  inverts), straight-line continuation past either end (last 25 players). Summary target tables are "unrounded":
  tied runs spread evenly inside their 0.1 rounding interval, so baseline values are unchanged after rounding.
- `trait_adapter._percentile` / `_value_at`: continuous mid-rank interpolation, straight-line continuation past
  either end fitted to the top/bottom 5% (at least 10 players). League members map exactly as before.
- `health.monthly_trait_delta`: the taper toward 100 applies only to the older ratings (`stored_bound=100.0`
  passed by `advance_development` in legacy mode).
