# Box scores: stars' turnovers, assists, steals and free throws

TL;DR: Ball handlers now turn it over ~3.5-4.3 times per 36 (was ~2), Jokic averages ~10 assists per 36 (was 6.5), steal specialists stand out, and rim attackers get more of their free throws.
Each player's share now comes from his own evidence-based inputs, fitted to real 2025-26 per-36 rates and checked on players the fit did not see. Game scores are unchanged, to the point.
Still open: points themselves are flattened (stars score too little, role players too much), and that drags free throws for stars like Wembanyama and Avdija. Not touched here.

Task BOX-STAR (Claude subagent, overnight 2026-11-18), branch `claude/box-star-stats`. Blocks and the rim-deterrence mapping were left alone (another agent owns them).

## What changed, in plain terms

1. **Each player has his own rate for four box-score stats** (new file `src/nba_gm_data/box_rates.py`):
   - Turnovers: how much the player seeks the ball (involvement) and how risky his passes are push them up; dribble manipulation and handle security bring them down at the same involvement.
   - Assists: how often he chooses to pass, involvement, passing delivery (average of the nine passing families' execution grades), passing risk appetite, and how often he decides from the post. The post term is what was missing for Jokic and Sengun.
   - Steals: passing-lane interception technique and on-ball steal technique.
   - Free-throw attempts per point scored: contact seeking and foul-drawing craft (high-involvement scorers take relatively more of their points from the field).
   - Old-ratings saves (and generated draftees without inputs) use simpler fits on the 15 legacy traits: passing reads, rim pressure and IQ for turnovers; effort, screen navigation and (negatively) rim deterrence for steals; rim pressure and shooting range for free throws. The old-ratings assist formula is kept.
   - All fits: `scripts/fit_box_stat_rates.py` (standard library; reprints coefficients and out-of-fold checks).
2. **The noise no longer flattens players.** The old formulas added rounding noise that gave every bench player an almost fixed extra assist/turnover/steal, then rescaled the team total, which shrank the stars. Counts are now drawn as a Poisson count around each player's own rate, using the same single random number the old formula used, so the random stream and therefore every score is unchanged.
3. **Team totals follow the team's talent.** A team of good passers keeps its extra assists instead of being pulled back to the league average (that cost Jokic ~12% of his assists). Steals likewise.
4. **Turnovers in the final box** now start from the player's own expected rate (they used to take the larger of a noisy draw and a usage formula).
5. **Free throws**: the per-point rate comes from the fit (the old rate was capped at 0.34 and mostly flat). The fix for odd point totals no longer adds a free throw to about half of all lines; it adds or removes one at random, so attempts keep their expected value.

## Scorecard: real-stat targets (real minutes replay, 1,230 games, 150 rotation players)

Mean absolute error per 36 minutes (spread = sim spread / real spread; 1.0 means stars are as distinct as in the real NBA).

**New ratings (inputs mode)**

| Stat | Before | After | Correlation with real | Spread |
|---|---|---|---|---|
| Turnovers | 0.583 | **0.340** | 0.28 → 0.85 | 0.27 → 0.96 |
| Free-throw attempts | 1.145 | **0.688** | 0.75 → 0.90 | 0.58 → 0.78 |
| Assists | 0.697 | **0.454** | 0.91 → 0.96 | 0.78 → 0.95 |
| Steals | 0.280 | **0.177** | 0.53 → 0.82 | 0.94 → 1.01 |
| Rebounds (not targeted) | 1.160 | 1.170 | 0.83 | 0.87 → 0.88 |
| Blocks (not touched) | 0.320 | 0.323 | 0.69 | 1.11 → 1.12 |
| Points (not touched) | 2.595 | 2.595 | 0.79 | 0.70 |

Named players (per 36, real → before → after): turnovers Giddey 4.07: 2.09 → 3.05; Westbrook 4.05: 2.17 → 3.45; LaMelo 3.61: 1.84 → 4.29; Luka 4.01: 2.38 → 3.83; Cade 3.92: 2.25 → 4.36; Castle 3.83: 2.02 → 3.77; Jaylen Brown 3.82: 2.10 → 3.69; Avdija 4.14: 2.43 → 3.86; Gobert 1.60: 2.00 → 1.29. Assists Jokic 11.09: 6.53 → 10.13; Giddey 10.26: 7.48 → 8.50; Cade 10.52: 8.50 → 9.20; Luka 8.33: 7.51 → 9.31. Steals Reed Sheppard 2.04: 1.05 → 1.77; Dyson Daniels 2.13: 1.73 → 2.23; Jokic 1.46: 0.73 → 1.65. Free throws Avdija 9.99: 4.10 → 5.60; Wembanyama 8.67: 4.24 → 5.98; Banchero 8.48: 4.48 → 6.27; Gilgeous-Alexander 9.79: 9.44 → 9.69.

**Old ratings (default for new careers)**

| Stat | Before | After | Correlation | Spread |
|---|---|---|---|---|
| Turnovers | 0.602 | **0.430** | 0.23 → 0.69 | 0.25 → 0.76 |
| Free-throw attempts | 1.222 | **1.162** | 0.70 → 0.69 | 0.64 → 0.87 |
| Assists | 1.091 | 1.115 | 0.74 → 0.74 | 0.70 → 0.76 |
| Steals | 0.313 | **0.292** | 0.35 → 0.31 | 0.91 → 0.62 |

The old traits carry little steal or free-throw signal (best fit out-of-fold correlation 0.44 for steals, 0.55 for free throws per point), so the old-ratings steal leaderboard is now flatter but closer to reality on average. Old-ratings assists are about unchanged (slightly worse error, slightly better spread).

## League metrics (sim vs 2025-26 NBA; all 18 in band before and after, both modes)

| Metric | Target | New ratings before → after | Old ratings before → after |
|---|---|---|---|
| Assists per 100 | 26.08 | 24.97 → 25.92 | 25.52 → 25.74 |
| Assist rate | 0.637 | 0.589 → 0.621 | 0.609 → 0.626 |
| Steals per 100 | 8.21 | 7.54 → 8.11 | 7.58 → 8.13 |
| Turnovers per 100 | 14.13 | 13.95 → 13.63 | 14.00 → 13.50 |
| Free-throw attempts per 100 | 22.90 | 21.58 → 23.01 | 21.30 → 23.24 |
| Free-throw rate | 0.264 | 0.248 → 0.265 | 0.244 → 0.267 |
| TS% | 0.581 | 0.586 → 0.584 | 0.578 → 0.575 |
| eFG% | 0.546 | 0.552 → 0.546 | 0.544 → 0.536 |
| Pace | 102.0 | 102.17 → 102.00 | 101.92 → 101.74 |
| Points per game | 115.61 | 115.95 → 115.95 | 114.19 → 114.19 |

Turnovers per 100 sit ~0.5 under the NBA on purpose: players are at their real per-36 rates, and real team totals also include team turnovers (shot clock, 5 seconds) that no player is charged with. `sim.TURNOVER_LEVEL` is the one knob if the league total should match instead (1.035 matched it but put rotation players +0.15 per 36 high).

## Betting-odds scorecard

Game scores are bit-identical to before (checked directly: 206 games × 2 sim modes × 2 ratings modes; scores, every player's points and minutes identical). So Brier score, log loss, spread and total errors cannot move. The odds data's player props are all points props (381 lines), and points are unchanged, so the prop scorecard is identical too (sim Brier 0.2730 before and after). A full `validate-season-probabilities --runs 100` run was also made; see the result line below.

`validate-season-probabilities --runs 100`, new ratings, 1,231 games, run on the code before and after this branch: Brier 0.1955 → 0.1955, log loss 0.5786 → 0.5786, spread error 5.036 → 5.036, total error 5.511 → 5.511 (identical, as expected). The run used the branch code just before the final steal-level tweak (team steal base 8.0 → 8.4), which touches only steals, not scores or props.

## What else changes in the box score

- Plus-minus values move (they are built from each line's makes, and free-throw makes changed). Scores do not.
- Three-pointers made can drop slightly for heavy free-throw shooters (a line's threes are capped by its points left after free throws). Not measured as a problem: 3PA per 36 error unchanged.
- The box-variation step's own random stream is consumed differently (turnover draws depend on the new means), so later draws in that step (two-point misses, rebound and block team totals) land on different but equally likely values. Block allocation logic is unchanged.
- No measurable speed change (1,230-game replay ran in 24-29 s, same as before on this machine).

## Tests

- New `tests/test_box_star_stats.py` (9 tests): fitted-rate ordering and rough sizes for named players (Luka/Cade/Giddey turnovers, Jokic assists > 9.5, Gobert/Avdija/Pritchard free throws per point, Dyson Daniels steals), bounds for all 691 players, old-ratings fallback ordering, Poisson draw mean/spread/determinism, team rescaling keeps a star's share over 1,500 games, and doubling the turnover/steal/free-throw levels changes the box but not a single point or minute (plus same-seed determinism).
- `tests/test_box_variation.py`: the "variance grows" check no longer applies to turnovers (they are realistic Poisson counts before that step); it now checks the team-turnover spread is NBA-like (3.3-5.2 per game; measured 4.28).
- Core suite (`scripts/run_core_tests.sh`): 320 tests pass (one fixture needed a local symlink to `output/settlement-materialization-pass`, git-ignored).
- Focused: box-score reconciliation, accounting, calibration targets, free-throw split, tie-break, specialist audit: pass.
- `tests.test_foundation` (214 tests, ~36 min): one failure, `test_monthly_development_is_trait_level_and_deterministic` (LeBron's monthly development delta above 0.12). It fails identically on the unchanged code from before this branch, so it is pre-existing and unrelated (development, not box scores). The old-ratings assist checks (Curry, Luka, Trae) pass.

## Caveats and open questions

1. **Points are the biggest remaining flattening** (new ratings: spread 0.70 of real). Wembanyama 20.5 vs 30.8 per 36, Porter Jr. 18.6 vs 26.8, Avdija 19.4 vs 26.2, Jaylen Brown 23.8 vs 30.0; role players like Sion James 16.6 vs 8.6, Dort 18.8 vs 11.2, Davion Mitchell 18.5 vs 11.8. The main cause looks like the scoring caps: `plausible_point_cap` (used as a soft expectation by `scoring_expectations_with_caps`) gives Porter Jr. 18 points at his real 32.5 minutes (real 24.2 a game), Wembanyama 17 (real 25.0), Avdija 19 (24.2), Siakam 19 (24.0), LaMelo 16 (20.1), because their trait-based `scoring_usage` is only ~58-63. Gilgeous-Alexander (scoring usage 77) is capped at 33 and lands right. Replacing the hand-tuned scoring weights and caps with a fit to real points per 36 (like the four stats here) is the natural next task. It changes the random stream and therefore scores, so it needs the odds check.
   - Knock-on effect, a small **regression in this task**: field-goal attempts per 36 error rose 1.92 → 2.08 (new ratings; old ratings 1.86 → 1.87). Stars now take more of their (too few) points at the line, so their shot attempts fall further below real (Wembanyama FGA 14.9 → 13.4 vs 20.8 real), while low-free-throw role players with too many points take more shots. Fixing points fixes this too. 3PA error 0.40 → 0.41; TS% error 0.025 → 0.024.
2. Fits shrink extremes a little (that is what makes them accurate on unseen players): Giddey 3.05 turnovers vs 4.07 real, Wembanyama 4.28 vs 2.99. No player's ratings were changed.
3. Some inputs used here were themselves estimated from related box-score evidence (e.g. contact seeking from foul exposure, involvement from usage). That is how the approved inputs are built; it means these fits mostly confirm the inputs carry the signal rather than adding new evidence.
4. Fits use one season (2025-26, 377 players with 500+ minutes); validation is out-of-fold, not a separate season.
5. The old-ratings mode keeps a few mode-specific settings (assist team reference 29.3, assist sharing power 1.2) because its hand-tuned assist formula runs ~10% higher than the fitted one. Refitting old-ratings assists on traits scored better on average but flattened LaMelo, Cade and Trae, so it was not adopted.
