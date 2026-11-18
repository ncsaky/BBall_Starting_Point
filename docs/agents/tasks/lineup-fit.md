# Lineup chemistry from real lineups (LINEUP-FIT)

**TL;DR**
- **What real lineups say.** Once each player's own impact is held fixed, real lineups show only modest chemistry, 1 to 3 points per 100 possessions. Three effects held up whichever way players were described. (1) Each shooter is worth more next to a ball-dominant creator. (2) The fifth shooter adds less than the fourth. (3) Lineups with three or more non-shooters give up more points at the *other* end. Most other ideas could not be told apart from noise in one half-season of data: rim protection covering weak perimeter defenders, defensive versatility, and a big offensive cliff for the third non-shooter.
- **What the game already did.** It already matched the evidence on creator overlap (a second ball-dominant creator adds less) and on lead playmakers. It had essentially none of the three effects above. Its built-in "spacing × creation" bonus almost never fires at team level.
- **What changed.** A new evidence-fitted lineup-fit term (`lineup_fit.py`) adds those three effects. It is shrunk toward zero for noise and sized to what the game was missing. For whole teams it moves offense by −0.4 to +0.4 points per 100 possessions and defense by −0.1 to +0.2. For extreme lineups the effect is a few points. Both scorecards are unchanged within noise (see Scorecards).

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
  - Because every player has his own effect, anything that is a plain sum over the five players is absorbed, e.g. counting shooters one by one. Only the **non-additive** part is measured, which is "fit beyond the sum of its players" by construction.
  - Linear counts stay in as nuisance controls.
- **Two descriptions of the same players.**
  - (a) The game's own ratings: non-shooter = spacing < 35; creator = projected usage ≥ 74, about 25% usage. These are what the engine uses.
  - (b) Basketball Index measures: non-shooter = mean 3PT / catch-and-shoot talent z < −0.75; creator = usage ≥ 25%.
  - They agree on 90% (non-shooter) and 88% (creator) of possessions.
- **Uncertainty.** A bootstrap over teams (100 resamples; all of a team's lineups move together). Also: an alternative control (summed O-/D-LEBRON instead of player effects), the non-shooter threshold from z −1.0 to −0.5, capped weights, ridge strength, and 5-fold out-of-sample checks.
- **Selection.** Coaches give good-fit lineups more minutes, and lineups that start hot get more minutes. Capping weights at 300 possessions (so small lineups count more) changed nothing material: third+ non-shooter +1.40 vs +1.33 on offense and +3.02 vs +2.96 on defense; creator overlap −1.82 vs −1.47.
- **Adoption rule (fixed before looking at the game's numbers).** A term changes the game only if all three hold:
  1. It has the same sign under both player descriptions.
  2. It is ≥ 1.5 standard errors from zero on actual or expected points.
  3. The shrunk evidence target differs from what the game already does by ≥ 0.5 per 100.

  The target is the estimate × prior shrinkage (prior spread 2 points) × 0.70. The game adds only the gap.

## Effect sizes (points per 100 xPoints possessions; ± = team-bootstrap standard error)
Offense, + = more points scored:

| Make-up term (beyond the players' own effects) | Game ratings | Basketball Index | Expected points (game ratings) | Game before | Game after |
|---|---|---|---|---|---|
| Each shooter beside a ball-dominant creator | **+1.63 ± 0.98** | +1.39 ± 0.91 | +1.01 ± 0.46 | +0.02 | **+0.92** |
| All five are shooters (the 5th shooter adds less) | −1.68 ± 2.17 | −2.05 ± 1.99 | −1.79 ± 0.81 | +0.38 | **−0.54** |
| Each non-shooter beyond two | +1.39 ± 2.30 | −3.65 ± 1.74 | +1.30 ± 1.47 | +0.54 | +0.54 (signs disagree: no change) |
| Second+ ball-dominant creator (simpler model) | −1.47 ± 1.49 | −1.82 | −1.27 ± 0.84 | −1.47 | −1.36 (already right) |
| Lead playmaker present (simpler model) | +0.74 ± 1.90 | +1.18 | +1.66 ± 0.68 | +1.14 | +1.19 (already right) |
| Two centers together | −2.94 ± 2.56 | −1.92 ± 2.16 | −2.26 ± 1.20 | −0.32 | −0.32 (gap 0.46 < 0.5) |
| Non-shooting big × other non-shooters | +0.85 ± 1.80 | +2.35 ± 1.25 | +0.23 ± 0.72 | −0.26 | no change |
| Lead playmaker × shooters | +0.23 ± 1.16 | +1.59 ± 0.81 | +0.25 ± 0.72 | −0.15 | no change |

Defense, + = more points allowed:

| Make-up term | Game ratings | Basketball Index | Expected points | Game before | Game after |
|---|---|---|---|---|---|
| Each non-shooter beyond two (bad offense leaks at the other end) | **+2.96 ± 1.92** | +2.18 ± 1.22 | +0.95 ± 0.95 | +0.05 | **+1.08** |
| At least one rim protector (vs. a second one adding less) | −3.56 ± 1.94 | +0.16 ± 2.74 | −0.94 ± 1.32 | −0.05 | no change (signs disagree) |
| Rim protector × weak perimeter defenders ("covering") | +0.15 ± 1.07 | −0.60 ± 0.76 | −0.01 ± 0.66 (BBI: −0.57 ± 0.33) | +0.04 | no change |
| Second+ weak perimeter defender | +2.09 ± 1.52 | −0.49 ± 1.36 | −1.10 ± 0.72 | +0.18 | no change |
| Second+ low-versatility defender | +1.44 ± 2.54 | −1.10 ± 2.05 | +0.94 ± 0.77 | −0.06 | no change |
| Two centers together | −0.58 ± 1.63 | +1.37 ± 2.23 | −1.44 ± 1.02 | +0.53 | no change |

"Simpler model" rows come from the fit without the two shooter-interaction terms, which share information with them. "Game after" is the same regression rerun on the game's ratings after the change (`--engine --tag _after`). The three adopted terms land exactly on their targets (−0.54, +0.92, +1.08), and creator overlap stays where it was (−1.36 vs −1.47 before; evidence −1.47).

Plain-language answers to the questions in the brief:
- **Diminishing returns for shooters?** Yes for the fifth: an all-shooter lineup gets about 1.7 per 100 less than the sum (1.8 on expected points). There was no clear cliff at the third non-shooter on offense: Basketball Index's description says −3.7 per extra, the game's says +1.4, and the threshold sweep gives −0.9 to −4.5. The cost of piling up non-shooters shows up more consistently on **defense**, +2 to +3 per 100 per extra non-shooter. That is likely transition after misses and empty possessions. Net per extra non-shooter beyond two: −1.6 ± 2.2 (game description) to −5.8 ± 1.6 (Basketball Index).
- **Does rim protection cover weak perimeter defense?** Not measurably. The game-rating version is +0.15 ± 1.07. The Basketball Index version is −0.6 ± 0.8 (−0.57 ± 0.33 on expected points), which is suggestive but small. Note: the game's perimeter-defense ratings agree with Basketball Index's perimeter/isolation defense only 71% of the time (no better than chance at that share), so this question is limited by the ratings, not only the data.
- **Usage overlap?** Yes. Each ball-dominant creator beyond the first costs about 1.3 to 1.8 per 100, and the game already did this (−1.47).
- **Creators and shooters together?** The clearest chemistry in the data. With a creator on the floor, each shooter is worth about +1.0 to +1.6 more per 100 xPoints possessions. The game had none of it at the lineup level.
- **Size?** Two centers together look worse on offense (−2 to −3, not significant on actual points). Real coaches rarely do it: 7% of possessions, about a third of what chance would give. So it barely matters at team level; not changed.

## Other checks
- **Out-of-sample** (5 folds × 2 repeats, game ratings).
  - With all make-up terms at once, held-out error gets *worse* (offense +1.06 ± 0.44, defense +0.80 ± 0.51). The full set overfits one half-season. That is why only terms passing the adoption rule went in, and shrunk.
  - Per term: "two centers" helps on offense (+0.34 ± 0.14). The non-shooter terms are neutral (offense −0.08 ± 0.04, defense +0.02 ± 0.21). With Basketball Index's description, the offensive non-shooter term helps (+0.60 ± 0.20). Creator × shooters is neutral (−0.03 to +0.19 ± 0.3 across thresholds).
  - Squared error on lineup outcomes is dominated by possession noise, so these are weak tests either way.
- **Summed-LEBRON control instead of player effects:** same picture. Third+ non-shooter: offense −2.16 ± 1.78 (BBI) / +1.32 ± 2.08 (game), defense +2.53 ± 1.21 / +3.21 ± 1.74.
- **Lineup Explorer** (Basketball Index, 61,037 lineups, 2013-26).
  - Its ratings are Basketball Index's *stabilized* estimates. Net rating spreads ~8 points whatever the sample size. They correlate 0.75–0.81 with the players' summed LEBRON. Their correlation with 2025-26 actual results, beyond that talent sum, is only 0.1–0.2. So they reflect Basketball Index's model, not raw outcomes.
  - Fitted the same way, they show creator overlap (−1.59) and a lead-playmaker bonus (+1.83), like the game. They show essentially no spacing or creator×shooter chemistry (all within ±0.1).
  - Reported for comparison only; not used for the coefficients.
- **From lineups to rotations.** The game term uses each player's on-floor share (minutes / 48) and treats players as independent. Against the real 2025-26 lineups, this predicts team make-up well (team-level r 0.95–0.99). Coaches stagger non-shooters, so three-plus non-shooter lineups happen 0.55× as often as chance; all-shooter lineups 0.78×. The fit file carries these ratios.

## The change in the game
- `src/nba_gm_data/lineup_fit.py` (new): game-rating flags (non-shooter: spacing < 35; creator: usage ≥ 74). Exact expected terms over a rotation (Poisson-binomial). Coefficients from `data/canonical/lineup_fit.json`.
  - Offense: +0.90 per shooter beside a creator, counted from the usual 3.80 and only while a creator plays. A team without a creator gets nothing from this term, since a creator's own value is already in his ratings. Also −0.92 when all five are shooters.
  - Defense: +1.03 allowed per non-shooter beyond two.
  - Everything is centered on the league's average lineup, so league scoring doesn't move.
- `sim.py`.
  - `team_feature_vector` and `lineup_feature_vector` add `lineup_fit_offense` / `lineup_fit_defense`.
  - `mean_off_rating` adds own offense fit + opponent defense fit.
  - The game's `feature_context` shows both deltas.
  - `mean_off_rating` / `neutral_off_rating` were split out of `simulate_team_line` as a pure refactor, checked bit-identical on 60 games in both modes before the fit was added.
- **Team-level size** (2026-27 projected rotations): offense −0.36 (DAL) to +0.42 (IND), defense −0.07 to +0.24 (TOR, DAL).
  - A single lineup of five non-shooters gives up about +3.1 more per 100 than one with two.
  - A creator with four shooters gets +1.1 from the creator term and −0.7 from the five-shooter term.
- **Switch.** `NBA_GM_LINEUP_FIT=off` restores the old game exactly (scorecard A/B).
- **Speed.** One small product over ≤ 15 players per team-feature build (cached); the 1,230-game replay took 19.3 s vs 18.3 s with the fit switched off, which is within noise on a shared machine.
- **What the user sees vs what the engine uses.** The flags come from ratings the engine already uses: the spacing feature and projected usage. Nothing new is displayed yet. The per-game deltas are in `feature_context`. A team-page "lineup fit" readout would be a natural GUI follow-up.

## Scorecards
| | Before (fit off) | After |
|---|---|---|
| Real-stat replay, 1,230 games | 18/18 in band; off. rating 113.23; pts/game 115.95; player pts/36 error 2.595 | 18/18; 113.29; 116.05; 2.598 |
| Betting odds, 100 runs | Brier 0.1955, log loss 0.5786, spread error 5.04, totals error 5.51 (today's baseline from the brief; not rerun) | ODDS_AFTER |

## Tests
`tests/test_lineup_fit.py` (13 tests):
- Mechanics: exact five-man counts; rotation expectations match enumeration; the rotation ratio applies to rotations but not to single lineups; the creator term is a slope; the league-average lineup is neutral; the fit enters the offensive rating one for one.
- Fitted behaviour:
  - Only adopted terms change the game.
  - **Five non-shooters vs two are penalized by the evidence amount**: the per-extra-non-shooter total equals the shrunk target of about 1.08 per 100 allowed.
  - One more shooter beside a creator adds the fitted slope.
  - The sim's team features carry the fit.

Focused: FOCUSED_TESTS. Core suite: CORE_TESTS.

## Reproduce
```
PYTHONPATH=src .venv/bin/python scripts/fit_lineup_fit.py --flags bbi --boot 100 --engine --engine-cache output/lineup-fit/engine_lineups_before.json
PYTHONPATH=src .venv/bin/python scripts/fit_lineup_fit.py --flags game --boot 100 --engine --engine-cache output/lineup-fit/engine_lineups_before.json --write
# checks: --cv (out-of-sample), --sensitivity, --control lebron, --shooter-z, --explorer (Lineup Explorer), --tag
```
The engine-ratings cache must be built with the fit switched off (`NBA_GM_LINEUP_FIT=off`) when refitting from scratch. Otherwise "game before" already includes the fit. The script writes derived coefficients only; no Basketball Index rows are committed. Run logs are in `output/lineup-fit/` (git-ignored).

## Caveats
- **One half-season.** One half-season of real lineup outcomes (2025-26 xPoints, ~240k possessions) is thin for interaction effects. Standard errors are 1–2.5 points per 100, and the full term set does not beat player effects alone out of sample. The adopted effects are shrunk and small on purpose. More seasons of real lineup data would tighten them; the Lineup Explorer is model-based and can't substitute. This could be lineups with possessions from NBA.com or pbpstats, which would need a download the user approves.
- **Possession conversion.** The 0.70 conversion from xPoints possessions is an assumption: fit effects are taken to apply only to the possessions xPoints counts.
- **Inconclusive.** The offensive non-shooter cliff and rim-protector effects are inconclusive, because the two player descriptions disagree in sign. They are left unchanged in the game, not set to zero.
- **Weak-perimeter ratings.** The game's weak-perimeter-defender ratings track Basketball Index poorly (71% agreement). That is a ratings question for track B.
- **Independent on-floor model.** The rotation translation assumes independent on-floor time, corrected by measured ratios. Real coaches' staggering differs by team.
- **Spacing display.** The player card's "Spacing" display is a composite (shooting/range/release/versatility), and two screens compute it differently. The engine's spacing feature is range × three-point volume. They mostly agree but are not the same number; this was there before this task and is unchanged.
