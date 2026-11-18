# Lineup chemistry from real lineups (LINEUP-FIT)

**TL;DR**
- **What real lineups say.** Once each player's own impact is held fixed, real 2025-26 lineups show only modest chemistry, about 1 to 3 points per 100 possessions. The steadiest effects:
  - The fifth shooter adds less than the fourth.
  - Lineups with three or more non-shooters give up more points at the *other* end.
  - A second ball-dominant creator adds less than the first.
  - Shooters seem worth more beside a creator.
- **What the game already did.** It was mostly about right. It already had the creator overlap and the lead-playmaker effect. It lacked the other three. Its built-in "spacing × creation" bonus almost never fires.
- **What changed.** A small evidence-fitted lineup-fit term now covers the fifth shooter and non-shooter pile-ups on defense. Shooters-beside-a-creator was held back: it pushed team strengths away from the betting market. For whole teams the change is within ±0.25 points per 100. Extreme lineups move more: five non-shooters give up about +3 points per 100. Both scorecards hold (see Scorecards).

Branch `claude/lineup-fit`. Status: **review** (coordinator).

## What the game does with fit (before)
The game simulates each team-game from its rotation, weighting every player by minutes. It does not simulate lineup by lineup. Its fit-type terms:
- `spatial.team_spatial_profile`: a rim-efficiency penalty when more than 38% of rotation minutes go to non-shooters (perimeter gravity < 48, about 14% of players). There is also a small three-point gravity bonus from perimeter gravity and creators beyond two, plus the playmaking lift.
- `sim.spacing_creation_interaction`: up to −2.5/+4.2 points per 100 from team-average spacing × top creation. On 2026-27 projected rotations it ranges only from −0.53 to +0.33 (spread 0.13), so it rarely fires.
- `unsupported_creation_effect` and `creator_advantage`: convex creator/star terms. `scaled_coach_effect` scales the coordinators' spacing and creator ratings by roster spacing and primary creator. That only matters for coaches away from 3 stars, and lineup data can't test it.

To compare like with like, the fit script runs the **same regression on the game's own expected ratings** (`sim.neutral_off_rating`, a new pure refactor) for the same 10,248 real lineups, with the players' game ratings and a league-average opponent.

## Evidence and method
- **Data.**
  - Basketball Index xPoints lineups, 2025-26: 12,481 real five-man lineups, 576 players, 240,860 possessions (both ends). About half of each team's season was captured (38–98% of team minutes).
  - xPoints counts possessions its own way. Its lineup possessions are about 70% of standard possessions, with lower points per possession, so effects are quoted "per 100 xPoints possessions" and multiplied by 0.70 before entering the game. This is conservative: it assumes the uncounted possessions carry no fit effect.
  - Player descriptions are per season: the Basketball Index progression table (3PT and catch-and-shoot 3PT talent, usage, playmaking, rim protection, perimeter defense, position).
- **Model.** Each lineup's points per 100 = intercept + one effect per player (shrunk, RAPM-style) + make-up terms, weighted by possessions, offense and defense separately.
  - Because every player has his own effect, anything that is a plain sum over the five players is absorbed, e.g. counting shooters one by one. Only the **non-additive** part is measured: fit beyond the sum of its players.
  - Linear counts stay in as nuisance controls.
- **Two descriptions of the same players.**
  - (a) The game's own ratings: non-shooter = spacing < 35, where the engine's spacing = shooting range × three-point volume; creator = projected usage ≥ 74, about 25% usage. These are what the engine uses.
  - (b) Basketball Index measures: non-shooter = mean 3PT / catch-and-shoot talent z < −0.75; creator = usage ≥ 25%.
  - They agree on 90% (non-shooter) and 88% (creator) of possessions. The disagreements are borderline players such as Bam Adebayo, Stephon Castle, Bruce Brown and Jalen Johnson.
- **Uncertainty and robustness.**
  - A bootstrap over teams (100 resamples; all of a team's lineups move together).
  - Summed O-/D-LEBRON as the control instead of player effects.
  - The non-shooter threshold swept from z −1.0 to −0.5.
  - Weights capped at 300 possessions.
  - Ridge strength 500 to 8,000.
  - 5-fold out-of-sample checks.
- **Selection.** Coaches give good-fit lineups more minutes, and lineups that start hot get more minutes. Capping weights at 300 possessions (so small lineups count more) changed nothing material: third+ non-shooter +1.40 vs +1.33 on offense and +3.02 vs +2.96 on defense; creator overlap −1.82 vs −1.47.
- **Adoption rule (written before looking at the game's numbers, except step 4).** A term changes the game only if:
  1. It has the same sign under both player descriptions.
  2. It is ≥ 1.5 standard errors from zero on actual or expected points.
  3. The shrunk evidence target differs from what the game already does by ≥ 0.5 per 100. The target is the estimate × prior shrinkage (prior spread 2 points) × 0.70.
  4. **Market check.** The adopted terms together must not widen the game's average 2025-26 gap to the betting market (spread or total) by more than 0.02 points. If they do, drop the term whose removal narrows the spread gap most, and repeat. Step 4 was added after the first full odds run showed the spread and total errors growing by about 0.1 point with all three effects in.

  The game adds only the gap between the target and what it already does.

## Effect sizes (points per 100 xPoints possessions; ± = team-bootstrap standard error)
Offense, + = more points scored:

| Make-up term (beyond the players' own effects) | Game ratings | Basketball Index | Expected points (game ratings) | Game before | Decision |
|---|---|---|---|---|---|
| All five are shooters (the 5th shooter adds less) | −1.68 ± 2.17 | −2.05 ± 1.99 | −1.79 ± 0.81 | +0.38 | **added −0.92 → game −0.54** |
| Each shooter beside a ball-dominant creator | +1.63 ± 0.98 | +1.39 ± 0.91 | +1.01 ± 0.46 | +0.02 | passed evidence, **held back by the market check** |
| Each non-shooter beyond two | +1.39 ± 2.30 | −3.65 ± 1.74 | +1.30 ± 1.47 | +0.54 | signs disagree: no change |
| Second+ ball-dominant creator (simpler model) | −1.47 ± 1.49 | −1.82 | −1.27 ± 0.84 | −1.47 | already right |
| Lead playmaker present (simpler model) | +0.74 ± 1.90 | +1.18 | +1.66 ± 0.68 | +1.14 | already right |
| Two centers together | −2.94 ± 2.56 | −1.92 ± 2.16 | −2.26 ± 1.20 | −0.32 | gap 0.46 < 0.5: no change |
| Non-shooting big × other non-shooters | +0.85 ± 1.80 | +2.35 ± 1.25 | +0.23 ± 0.72 | −0.26 | no change |
| Lead playmaker × shooters | +0.23 ± 1.16 | +1.59 ± 0.81 | +0.25 ± 0.72 | −0.15 | no change |

Defense, + = more points allowed:

| Make-up term | Game ratings | Basketball Index | Expected points | Game before | Decision |
|---|---|---|---|---|---|
| Each non-shooter beyond two (bad offense leaks at the other end) | +2.96 ± 1.92 | +2.18 ± 1.22 | +0.95 ± 0.95 | +0.05 | **added +1.03 → game +1.08** |
| At least one rim protector (vs. a second one adding less) | −3.56 ± 1.94 | +0.16 ± 2.74 | −0.94 ± 1.32 | −0.05 | signs disagree: no change |
| Rim protector × weak perimeter defenders ("covering") | +0.15 ± 1.07 | −0.60 ± 0.76 | −0.01 ± 0.66 (BBI: −0.57 ± 0.33) | +0.04 | no change |
| Second+ weak perimeter defender | +2.09 ± 1.52 | −0.49 ± 1.36 | −1.10 ± 0.72 | +0.18 | no change |
| Second+ low-versatility defender | +1.44 ± 2.54 | −1.10 ± 2.05 | +0.94 ± 0.77 | −0.06 | no change |
| Two centers together | −0.58 ± 1.63 | +1.37 ± 2.23 | −1.44 ± 1.02 | +0.53 | no change |

"Simpler model" rows come from the fit without the two shooter-interaction terms, which share information with them. "Game after" values come from rerunning the same regression on the game's ratings with the fit on (`--engine --engine-with-fit --tag _after`).

### Plain-language answers to the questions in the brief
- **Diminishing returns for shooters?** Yes for the fifth. An all-shooter lineup gets about 1.7 per 100 less than the sum of its players (1.8 on expected points, the steadier measure). The game now charges 0.54.
- **Is the 4th shooter worth less, or is there a cliff at the third non-shooter?** On offense the data can't tell. Basketball Index's description says −3.7 per extra non-shooter, the game's description says +1.4, and the threshold sweep gives −0.9 to −4.5. The cost of piling up non-shooters shows up more consistently on **defense**: +2 to +3 per 100 per extra non-shooter, likely transition after misses and empty trips. The game now charges +1.08 there. Net per extra non-shooter beyond two: −1.6 ± 2.2 (game description) to −5.8 ± 1.6 (Basketball Index).
- **Does rim protection cover weak perimeter defense?** Not measurably. The game-rating version is +0.15 ± 1.07. The Basketball Index version is −0.6 ± 0.8 (−0.57 ± 0.33 on expected points), which is suggestive but small. The game's perimeter-defense ratings agree with Basketball Index's perimeter/isolation defense only 71% of the time (no better than chance at that share), so this question is limited by the ratings as much as by the data.
- **Usage overlap?** Yes. Each ball-dominant creator beyond the first costs about 1.3 to 1.8 per 100. The game already did this (−1.47).
- **Creators and shooters together?** The clearest chemistry in the lineup data: with a creator on the floor, each extra shooter is worth about +1.0 to +1.6 per 100 xPoints possessions. The game has none of it at lineup level.
  - Added at team level, though, it pushed the game's team strengths *away* from the betting market: its margin contribution correlates −0.20 with the market-minus-game gap, and the spread error rose by 0.10.
  - Against actual game results it was neutral (−0.04).
  - Two readings, both open: the game may already overrate creator-plus-shooters teams through its player values, or the lineup estimate is noise (its out-of-sample check was neutral). It is implemented and documented but switched off (coefficient 0) until the user decides.
- **Size?** Two centers together look worse on offense (−2 to −3, not significant on actual points). Real coaches rarely do it: 7% of possessions, about a third of what chance would give. So it barely matters at team level; not changed.

## Other checks
- **Out-of-sample** (5 folds × 2 repeats, game ratings).
  - With all make-up terms at once, held-out error gets *worse* (offense +1.06 ± 0.44, defense +0.80 ± 0.51). The full set overfits one half-season, which is why only rule-passing terms went in, and shrunk.
  - Per term: "two centers" helps on offense (+0.34 ± 0.14). The non-shooter terms are neutral (offense −0.08 ± 0.04, defense +0.02 ± 0.21). With Basketball Index's description, the offensive non-shooter term helps (+0.60 ± 0.20). Creator × shooters is neutral (−0.03 to +0.19 ± 0.3 across thresholds).
  - Squared error on lineup outcomes is dominated by possession noise, so these are weak tests either way.
- **Summed-LEBRON control instead of player effects:** same picture. Third+ non-shooter: offense −2.16 ± 1.78 (BBI) / +1.32 ± 2.08 (game), defense +2.53 ± 1.21 / +3.21 ± 1.74.
- **Market check, term by term** (1,021 games, game's expected margins with real minutes; change in mean gap to the market).

  | Term | Spread gap | Total gap | Correlation with the market gap |
  |---|---|---|---|
  | Fifth shooter | −0.021 | −0.053 | +0.15 |
  | Creator × shooters | +0.099 | +0.161 | −0.20 |
  | Non-shooters on defense | +0.033 | −0.046 | −0.23 |
  | Fifth shooter + non-shooters (kept) | +0.011 | −0.099 | |
- **Lineup Explorer** (Basketball Index, 61,037 lineups, 2013-26).
  - Its ratings are Basketball Index's *stabilized* estimates. Net rating spreads ~8 points whatever the sample size. They correlate 0.75–0.81 with the players' summed LEBRON. Their correlation with 2025-26 actual results, beyond that talent sum, is only 0.1–0.2. So they reflect Basketball Index's model more than raw outcomes.
  - Fitted the same way, they show creator overlap (−1.59) and a lead-playmaker bonus (+1.83), like the game. They show essentially no spacing or creator × shooter chemistry (all within ±0.1).
  - Reported for comparison only; not used for the coefficients.
- **From lineups to rotations.** The game term uses each player's on-floor share (minutes / 48) and treats players as independent. Against the real 2025-26 lineups, this predicts team make-up well (team-level r 0.95–0.99). Coaches stagger non-shooters, so three-plus non-shooter lineups happen 0.55× as often as chance; all-shooter lineups 0.78×. The fit file carries these ratios.

## The change in the game
- `src/nba_gm_data/lineup_fit.py` (new): game-rating flags (non-shooter: spacing < 35; creator: usage ≥ 74). Exact expected terms over a rotation (Poisson-binomial with the measured rotation ratios). Coefficients from `data/canonical/lineup_fit.json`. Current coefficients:
  - −0.92 offense when all five on the floor are shooters.
  - +1.03 points allowed per non-shooter beyond two.
  - Both are centered on the league's average lineup, so league scoring doesn't move.
  - The creator × shooter slope is implemented but set to 0 by the market check. It is counted as a slope (shooters beyond the usual 3.80 beside a creator, only while a creator plays), so it would not penalize teams without a creator.
- `sim.py`.
  - `team_feature_vector` and `lineup_feature_vector` add `lineup_fit_offense` / `lineup_fit_defense`.
  - `mean_off_rating` adds own offense fit + opponent defense fit.
  - The game's `feature_context` shows both deltas.
  - `mean_off_rating` / `neutral_off_rating` were split out of `simulate_team_line` as a pure refactor, checked bit-identical on 60 games in both modes before the fit was added.
- **Size.**
  - Teams on 2026-27 projected rotations: offense −0.13 (IND) to +0.13 (TOR/DAL); points allowed −0.07 to +0.24 (TOR, DAL).
  - A single five-non-shooter lineup gives up about +3.1 more per 100 than one with two.
  - An all-shooter lineup gets −0.74 against the league-average unit.
- **Switch.** `NBA_GM_LINEUP_FIT=off` restores the old game exactly (scorecard A/B).
- **Speed.** One small product over ≤ 15 players per team-feature build (cached); 1,230-game replay 18–26 s either way on a heavily shared machine (noise).
- **What the user sees vs what the engine uses.** The flags come from features the engine already uses: the spacing feature and projected usage. Nothing new is displayed yet. The per-game deltas are in `feature_context`. A team-page "lineup fit" readout would be a natural GUI follow-up.

## Scorecards
| | Before (fit off) | After (final fit) |
|---|---|---|
| Real-stat replay, 1,230 games | 18/18; off. rating 113.23; pts/game 115.95; player pts/36 error 2.595 | 18/18; 113.22; 115.91; 2.602 |
| Betting odds, 100 runs | Brier 0.1955, log loss 0.5786, spread error 5.036, totals error 5.511 | ODDS_AFTER |
| (first attempt, all three effects) | | Brier 0.1954, log loss 0.5790, spread 5.154, totals 5.615: regressed, hence the market check |

## Tests
`tests/test_lineup_fit.py` (13 tests):
- Mechanics: exact five-man counts; rotation expectations match enumeration; the rotation ratio applies to rotations but not to single lineups; the creator term is a slope; the league-average lineup is neutral; the fit enters the offensive rating one for one.
- Fitted behaviour:
  - Only terms passing all four rules change the game.
  - **A five-non-shooter lineup is charged, beyond its players' ratings, an amount inside the real-lineup evidence's 95% range at both ends.**
  - The sim's team features carry the fit: the all-shooter unit gets exactly the fitted fifth-shooter charge.
  - The rotation ratios are measured.

Core suite (`scripts/run_core_tests.sh`): all pass. One module needed a local fixture symlinked into the worktree; it passes then. Focused (foundation, narrative simulation, spatial, coaching effects, lineup fit): one failure, `test_foundation...test_monthly_development_is_trait_level_and_deterministic`. It fails identically with the fit switched off: pre-existing, development code (see DEV-TUNE on the board).

## Reproduce
```
PYTHONPATH=src .venv/bin/python scripts/fit_lineup_fit.py --flags bbi --boot 100 --engine --engine-cache output/lineup-fit/engine_lineups_before.json
PYTHONPATH=src .venv/bin/python scripts/fit_lineup_fit.py --flags game --boot 100 --engine --engine-cache output/lineup-fit/engine_lineups_before.json --write
# checks: --cv (out-of-sample), --sensitivity, --control lebron, --shooter-z, --explorer (Lineup Explorer), --engine-with-fit --tag _after
```
"Before" engine ratings are always measured with the fit switched off. The script writes derived coefficients only; no Basketball Index rows are committed. Run logs are in `output/lineup-fit/` (git-ignored).

## Caveats and open questions
- **Thin data.** One half-season of real lineup outcomes (2025-26 xPoints, ~240k possessions) is thin for interaction effects. Standard errors are 1–2.5 points per 100, and the full term set does not beat player effects alone out of sample. More seasons of real lineup data with possessions (NBA.com or pbpstats) would settle the open effects. That needs a download the user approves.
- **Creator × shooters.** Lineup data says yes; the betting market says the game's teams don't get closer. User call: leave it off, or switch it on and accept a ~0.1-point worse spread error.
- **Possession conversion.** The 0.70 conversion from xPoints possessions is an assumption: fit effects are taken to apply only to the possessions xPoints counts.
- **Weak-perimeter ratings.** The game's weak-perimeter-defender ratings track Basketball Index poorly (71% agreement). That is a ratings question for track B.
- **Spacing display.** The player card's "Spacing" display is a composite (shooting/range/release/versatility), and two screens compute it differently. The engine's spacing is range × three-point volume. They mostly agree but are not the same number. This was there before this task and is unchanged.
