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
Done; in review. Measurements: `output/rating-ceiling/run` (new code, Azure) and `output/rating-ceiling/control`
(pre-change code, local), same seed 17 / Golden State hands-off / five seasons.

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
- `trait_adapter`: input -> percentile and composite -> trait interpolate between league values (league members map
  exactly as before). Past either end of a table they continue on the normal-score scale: each table's outer 5%
  (at least 10 values) is fitted as value = a + b z; an input k tail-SDs past the league's best moves the composite
  k tail-SDs along the composite's own tail, and a composite past the end moves the trait the same number of tail-SDs
  along the target's tail. (A first version continued in a straight line in rank space. Both versions give similar
  numbers; the normal-score one measures distance in each table's own tail spread instead of stacking two rank
  densities, and it is the shape `uncensor_top` already uses.)
- Remaining amplification is inherited from the in-range maps, not the tail: development moves every grade by
  0.41 points per hidden-rating point, but physical capacity grades (conditioning P11, recovery P12, agility P06)
  have a league spread of about 3.6 grade points against about 14 for skill grades, so +2 development moves
  stamina by a median +2.3 but +12.5 at the 90th percentile already inside today's range.
- `health.monthly_trait_delta`: the taper toward 100 applies only to the older ratings (`stored_bound=100.0`
  passed by `advance_development` in legacy mode).

## Results
**Today's league is unchanged.** Fresh save: all 691 players' 15 hidden ratings, engine value (overall / offense /
defense), sim impact and display overall are identical before and after (0 of 10,365 ratings changed). Made-up
draftees (two generated classes, 120 players) move by a mean 0.04 hidden-rating points (step map -> interpolation;
largest single rating 3.7), engine value mean 0.015.

**Scorecards: byte-identical.** Real-stat report 18/18 before and after (same file). Betting test seed 1001: Brier
0.2041, log loss 0.5975, spread error 4.097, totals error 5.513 (before = after). Seed 2001: 0.1972 / 0.5808 / 3.923 /
5.545 (before = after). Both modes replay opening-day ratings, so this is expected.

**Five seasons (2026-27 to 2030-31, first regular-season snapshot each year):**

| Season | Best before / after | Top 5 | Top 10 | Top-15 players sharing an exact value, before / after |
|---|---|---|---|---|
| 2026-27 | 78.0 / 78.0 | 75.2 / 75.2 | 74.2 / 74.2 | 6 / 6 (opening-day data, unchanged by design) |
| 2027-28 | 76.8 / 77.8 | 75.4 / 75.5 | 74.3 / 74.4 | 7 / 4 |
| 2028-29 | 76.8 / 76.5 | 75.2 / 75.0 | 74.0 / 73.9 | 8 / 2 |
| 2029-30 | 75.0 / 74.9 | 74.4 / 74.3 | 73.9 / 73.8 | 9 / 4 |
| 2030-31 | 75.0 / 75.7 | 74.3 / 74.5 | 73.3 / 73.4 | 12 / 2 |

- The midpoint bunching is gone (remaining shared values are ordinary 0.1 coincidences, e.g. two players at 71.3).
- **The top barely moves, because nobody reached the old top.** In both runs the best players' uncapped fitted impact
  (the display OVR) is flat: Wembanyama display 92.8 -> 93.3 (after) vs 92.8 -> 93.1 (before) from 22 to 26; nobody's
  engine value passed 78.0 at any season start, and at the end nobody's sim impact was above 82.05 (best:
  Gilgeous-Alexander 81.0). At the end of the new run only five
  hidden ratings sit above their old top, each by about 1 point (Amen Thompson foot speed 101.0 and screen navigation
  101.8, Maxey portability 101.2, Boozer stamina 92.8, Gilgeous-Alexander playoff 92.1). No input grade reached 95.
- **So the flat top in a real career comes from development, not the map.** Wembanyama's total development over
  five seasons averages +2.9 hidden-rating points (Flagg +5.5, Holmgren +2.3, Dybantsa +13.5 from 19). The league
  aging curve (identical in both runs: about +1.1 at 22, +0.5 at 23, 0 from 24 to 30) peaks at 23-24 for everyone,
  stars included, and `cap_room` slows any rating already at 88+ to 8% of normal growth.
- **One development fix did matter: the rim-protection ratchet.** With the old taper, a rating above 100 could only
  fall (bad years still applied, good years were zeroed). Five-season rim deterrence development: Wembanyama -8.4
  before vs -2.5 after, Holmgren -6.1 before vs +3.1 after.

## What's left (not in this task's files)
1. **Elite development curve.** Stars stop growing at 23-24 like everyone else, and ratings at 88+ grow at 8%. If
   the user wants Wembanyama/Flagg-type players to keep rising into their mid-20s, that is a development-model
   decision (evidence: Basketball Index growth by starting level for top-decile young players).
2. **Physical inputs over-react to development.** Development adds the same grade points to physical capacity grades
   (league spread about 3.6) as to skill grades (about 14), so stamina can jump 10+ points in a season inside today's
   range (`ratings_model.GRADE_POINTS_PER_TRAIT_POINT`). Scaling each input's move by its league spread would fix it,
   but it changes everyone's development and needs its own scorecard pass.
3. **The AI value scale is anchored to a lumpy table.** The old summary formula's league top is a cluster
   (73.6-74.2) then 75.7 and 78.0, so between those players a full point of real impact moves the AI's value only
   about 0.4. The display OVR (linear) does not have this. Stage 2 step 4 (re-express thresholds) removes it.
4. Latent clamps outside this task's files: `save._uncached_player_attribute_summary` clamps overall and several
   subratings to 1-99 (not binding today; value max about 78), and `sim.nonlinear_high` clamps spacing / rim
   pressure / offensive rebounding features to 99; `talent._trait_ceiling` caps a draftee's skill capacity at 97.
   None bound in the five-season run.
5. Dybantsa enters at 50.4 engine value (72.6 display) and reaches 60.1 by 23 in both runs: prospect entry level,
   not a ceiling.
