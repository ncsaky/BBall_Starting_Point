# Energy bigs (Diabaté, Queta, Kornet) and the two overrated scorers (Ingram, Vučević)

Owner: Claude (worker session, 2026-11-18), worktree branch `worktree-agent-a0cb3c66dd408aaf2`. Status: **review**.
Follows `docs/agents/tasks/ratings-audit.md` (open questions 2 and 6).

## TL;DR

- **Why the game underrated them:** the game's player value missed them against its *own* target (Basketball Index
  multi-year LEBRON ranks them 67th, 16th and 78th of 278; the game had them 209th, 110th and 135th). The missing
  piece is offensive rebounding: how many extra possessions a big creates. Two things hid it: the engine's
  offensive-rebounding rating was a hand-written recipe that tracked real offensive rebounds poorly among bigs, and the
  value model read that rating on a rank scale where a 5-8 per 75 crasher looks barely better than a 3 per 75 one.
- **What changed:** (1) the offensive-rebounding rating is now fitted to Basketball Index offensive-rebounding evidence
  (its own evidence and attribution, not the impact target); (2) the value model reads it as "offensive rebounds per 75"
  on the real scale, offense only. Diabaté 209th → 152nd, Queta 110th → 83rd, Kornet 135th → 114th. Fit to its own
  target improved (out-of-fold offense 0.902 → 0.910, overall 0.870 → 0.878) and agreement with the six-measure
  consensus, which the fit never sees, rose (overall 0.807 → 0.817, offense 0.787 → 0.805, defense unchanged).
- **Scorecards:** real-stat targets 18/18 for both rating sets (older ratings identical; new ratings: rebounds closer
  to real, points and shot attempts a hair further). Betting odds, new ratings: spread error 4.655 → 4.546 and totals
  5.535 → 5.465 better, but win-probability accuracy slightly worse (Brier 0.1939 → 0.1941, log loss 0.5738 →
  0.5744). That last part is a small real cost, stated plainly; nothing was tuned to the odds test.

## 1. Diagnosis: what these players do

Basketball Index, 2025-26 (percentile among 500+ minute players):

| | Diabaté | Queta | Kornet |
|---|---|---|---|
| Offensive rebounds per 75 | 97.6 (5.4) | 94.9 (4.5) | 94.9 (4.5) |
| Screen assists per 75 | 94 | 99 | 100 |
| True shooting relative to league | 92 (+6.9) | 95 (+9.2) | 97 (+9.9) |
| Turnovers per 100 touches (lower is better) | 23 | 28 | 1 |
| Rim shots defended per 75 | 99 | 92 | 98 |
| Help defensive activity | 89 | 97 | 99.7 |
| True usage | 7 | 16 | 6 |

Low-usage, no-jumper bigs who crash the glass, set screens, finish efficiently, rarely turn it over and protect the rim.

**Which impact measures like them, and where:**

| | Consensus (box / on-off) | Multi-year LEBRON (the value model's target) | Game before |
|---|---|---|---|
| Diabaté | 31 (43 / 22) | 67 (offense 138, defense 32) | 209 |
| Queta | 16 (20 / 14) | 16 (offense 100, defense 4) | 110 |
| Kornet | 41 (51 / 29) | 78 (offense 159, defense 31) | 135 |

- **Defense:** every measure rates them well (box-score z-scores +1.1 to +2.1). The game already did on defense.
- **Offense:** box-score measures see them as about average (z -0.5 to +0.6); the on/off measures (luck-adjusted RAPM)
  see them as clearly positive (z +0.7 to +1.6). So part of the consensus gap is the on/off family seeing more than
  any box-score model can; the game follows the box-score view by design (its value model is fitted to LEBRON).
- **But the bigger part was the game's own miss:** before this change the value model predicted their offense at
  -0.5 / -0.1 / -0.4 against real multi-year O-LEBRON +0.65 / +1.19 / +0.37, and their totals 1.1 to 2.7 points
  below their own target.

## 2. Which of (a) mis-measured input, (b) value-model form, (c) defensible disagreement?

**Both (a) and (b), for one skill: offensive rebounding.** Evidence:

- Among non-shooting bigs (28 players) the value model's offensive miss tracked real offensive rebounds per 75
  (r +0.60) and turnovers per touch (r -0.40), not screen assists (0.00) or true shooting (-0.13).
- A diagnostic upper bound (real offensive rebounds per 75 added as a predictor, *not* a proposal) improved the
  out-of-fold offense fit 0.902 → 0.917, the most of any single measure tested; screen assists, efficiency and
  turnovers added 0.000-0.004 to offense.
- (a) **The engine's offensive-rebounding rating was mis-measured for this archetype.** Its hand-written recipe
  (pursuit technique S29 0.40, crash tendency T12 0.20, vertical, reach, rebound control and strength 0.10 each)
  followed the offensive-rebounding evidence at r 0.83 league-wide and only 0.71 among bigs: Diabaté (97th percentile
  in offensive rebounds per 75) rated in the 83rd percentile of the recipe, 78 on the engine scale, below Bobby Portis
  (90) and Jabari Smith Jr. (94).
  The inputs themselves are fine: the crash tendency alone follows real offensive rebounds per 75 at r 0.94.
- (b) **Form:** even a good rating is read on a rank scale, where the 90th and 99th percentile sit a few points
  apart while real production goes from about 3 to 5-8 per 75. A linear value fit cannot credit that tail. Tested
  alone, the production scale on the *old* rating barely helped (+0.002); together with the fitted rating it does.
- Tested and rejected (each 0.000-0.004 out-of-fold, or it lowered agreement with the consensus): separate pursuit
  technique, screening, cutting, rim finishing, lob finishing, low-usage x efficiency/off-ball/screening/finishing
  terms, the box-score profile facets, crash x pursuit products, a split interior/perimeter defense (better LEBRON fit,
  worse consensus defense: fitting LEBRON quirks), help commitment, handle security. Using the crash tendency (T12)
  directly in the value model fits about as well, but it would pay a *choice* as value and it also picked up defensive
  weight as a stand-in for "plays center"; the fitted rating keeps the tendency inside the engine's production
  rating where the sim already uses it.
- **Not (c) for most of it:** the game missed its own target. What remains after the change is partly (c): the
  on/off family's offensive view and their defense (Queta's real defense is +3.2, predicted +1.8; the model shrinks
  all elite defenders, Gobert and Wembanyama included).

## 3. What changed

1. **Offensive-rebounding rating fitted to evidence** (`trait_adapter.ADAPTER_SPEC["offensive_rebounding"]`, new
   script `scripts/fit_offensive_rebounding.py`). Evidence: mean z-score of Stable Offensive Rebounds Per 75 and
   Offensive Rebounding Talent, 2023-24..2025-26, season weights 1.0 / 0.6 / 0.35 x minutes, 491 players. Non-negative
   ridge over league percentiles of rebounding technique (S29, S31, S32), the crash tendency (T12) and body inputs.
   Result: **T12 0.64, S29 0.32, wingspan 0.04**, out-of-fold r 0.87 (hand-written recipe 0.83; among bigs 0.71 → 0.78).
   Production = how often he crashes x how well he pursues. Like the other engine ratings it is quantile-mapped onto
   the same league scale, so team-level calibrations keep their meaning. This is a rating correction with its own
   evidence; it was not fitted to impact. Examples of rating moves: Diabaté 78 → 98, Collin Sexton 25 → 43, Bobby Portis
   90 → 73, Jabari Smith Jr. 94 → 74, Kentavious Caldwell-Pope 35 → 19, Dyson Daniels 91 → 72.
2. **Value model reads offensive rebounding on its production scale** (`impact_value.orb_per75`, knots in
   `data/canonical/offensive_rebound_scale.json` from the same script: the rating's league rank matched to real
   offensive rebounds per 75 among 445 players; rank correlation 0.96). Beyond the end knots the end segments continue
   (no clipping). **Offense only:** the fit holds the defensive weight of both the rating and its production scale at
   zero. Refit with `scripts/fit_impact_value.py --write` (version `impact_value_fit_v5_offensive_rebound_scale`).
   Since the ratings audit, the sim's player impact reads this value, so the change reaches game results.
3. Tests: `tests/test_impact_value.py` (offensive rebounding raises offense monotonically, adds no defense, the scale
   keeps rising past the top knot).

### Value model, before → after

| | Before | After |
|---|---:|---:|
| Out-of-fold vs multi-year LEBRON (offense / defense / overall), 454 players | 0.902 / 0.868 / 0.870 | **0.910** / 0.868 / **0.878** |
| Agreement with the consensus, 278 players (overall / offense / defense) | 0.807 / 0.787 / 0.843 | **0.817 / 0.805** / 0.843 |
| Mean absolute overall gap to the consensus (percentile points) | 13.3 | 13.3 |
| Players closer to / further from the consensus (by more than half a point) | | 107 / 104 |

Attribution (each piece alone, same refit): rating fit alone 0.874 overall out-of-fold, consensus 0.812; production
scale alone 0.871, consensus 0.808; both 0.878 and 0.817.

### Biggest movers (game rank among the 278; consensus rank in brackets)

Up: Diabaté 209 → 152 (31), Jock Landale 224 → 173 (152), Yves Missi 197 → 149 (221), Luka Garza 150 → 109 (117),
Jordan Goodwin 180 → 144 (71), Josh Okogie 182 → 154 (69), Adem Bona 176 → 148 (193), Queta 110 → 83 (16), Collin
Sexton 193 → 166 (209), Andre Drummond 147 → 120 (161), Day'Ron Sharpe 72 → 46 (93), Kornet 135 → 114 (41).

Down: Deandre Ayton 136 → 184 (198), Nic Claxton 161 → 194 (216), Oso Ighodaro 130 → 159 (89), Naji Marshall 109 → 137
(201), Kris Dunn 86 → 111 (43), P.J. Washington 159 → 181 (141), Rudy Gobert 51 → 72 (13), Jarrett Allen 24 → 35 (25).

Trade-offs to know about: Gobert and Allen slip because other crashers pass them and the refit leans a little more on
shooting (Gobert's predicted total 2.7 → 2.3 against a real 3.3; he crashes often but Basketball Index rates his
crashing skill low, so his rating rises only 68 → 75). Gobert's main gap is defense, which this change does not touch. Missi, Bona and
Drummond rise further above the consensus: they rebound a lot, but the impact measures rate them lower than that
suggests (offensive rebounding is one piece of value, not all of it).

## 4. Does the sim credit these skills? (card vs engine)

- **Offensive rebounding: yes.** The rating drives each team's offensive rebound rate and extra possessions, every
  player's rebound share and putback finishing. The card shows the same rating. It now follows the evidence.
- **Screening: the card and the sim agree with each other, but neither reads the screening skill.** The engine's
  "Screening" (`offense.offensive_profile`: 0.45 size + 0.35 scheme IQ + 0.20 stamina) is what the card shows and
  what team offense uses, but it never reads screen execution (S27) or screen-action recognition (S28). Among bigs it
  does not follow real screening at all (rank correlation -0.07 with Screening Talent, -0.15 with screen assists),
  while S27 follows Screening Talent at 0.95. Queta (S27 82, 99th percentile on Screening Talent) shows 65,
  below Gobert's 71. The sim effect is small (team screening moves offense by 0.025 points per 100 per point), and
  screening did not explain the value-model miss, so it was **not changed here**. Suggested follow-up task: rebuild
  the new-ratings screening facet from S27/S28 (fitted to Screening Talent and screen assists, quantile-mapped onto
  the current facet scale), then re-run both scorecards.
- **Rim running:** "Assisted finishing" (rim pressure, size, foot speed, blended with real roll-man efficiency when
  known) and roll share feed putbacks and feeding. Assisted finishing follows real roll-man points per possession at
  0.72 among bigs. No change.

## 5. Ingram and Vučević

| | Consensus (box / on-off) | Multi-year LEBRON rank | Game before → after |
|---|---|---|---|
| Brandon Ingram | 207 (153 / 253) | 156 (offense 86, defense 217) | 98 → 105 |
| Nikola Vučević | 170 (177 / 160) | 92 (offense 95, defense 115) | 73 → 81 |

- **Vučević is (c).** The value model hits its own target for him (predicted +2.1 vs real +2.0 multi-year LEBRON).
  The gap is between impact measures: multi-year LEBRON (which still carries his better earlier seasons; he is 35)
  ranks him 92nd, while DPM and the 2025-26 on/off numbers are much lower. Leaning on one metric family over another
  would be choosing a target, not fixing a rating.
- **Ingram is mostly (c), partly a known gap.** The model overrates him against LEBRON by about 0.8 points (offense
  +0.4, defense +0.4). Why: his shot-making technique is genuinely elite (catch-and-shoot and pull-up midrange both
  97th percentile, shots made against their difficulty), but he takes the hardest shot diet in the league (shot
  difficulty tolerance 100th percentile; Basketball Index shot quality 0th percentile), so his real efficiency is
  average (relative true shooting -1.2) and he turns it over a lot (89th percentile per touch). The value model credits
  "involvement x shooting technique" and has no term for shot diet. Adding the shot-difficulty tendency or handle
  security improved the fit by 0.001 at most and moved him 98 → 110-120; not worth a new moving part. The sim side is
  consistent with this: his simulated true shooting is 0.64 vs a real 0.57, the shot-difficulty tendency does not cost
  him enough efficiency in the sim. That is an engine question (how shot difficulty sets make rates), not a rating one.
- Every impact measure is lukewarm on Ingram's defense (LEBRON defense 217th); the game's defense for him (card 54)
  is near average, carried by his length and size inputs.

## 6. Scorecards

Baselines were re-run on main's code in the same session (they reproduce main's published numbers exactly).

**Betting odds** (`validate-season-probabilities --runs 100`, new ratings, 1,231 games, 1,018 with market odds):

| | Brier | Log loss | Spread error | Totals error |
|---|---:|---:|---:|---:|
| Main | 0.1939 | 0.5738 | 4.655 | 5.535 |
| This branch | 0.1941 | 0.5744 | **4.546** | **5.465** |
| Market | 0.1962 | 0.5740 | | |

The win-probability part is slightly worse (+0.0002 Brier, +0.0006 log loss; the ratings audit measured seed-to-seed
noise at about 0.0001, so treat it as real but small). Margins and totals both got closer to the market. The sim still
beats the market on Brier. Older ratings do not use either changed piece (both apply only to the new ratings), and
their real-stat report is identical to main's to the last digit, so their odds result is unchanged.

**Real-stat targets** (`calibration_report.py --games 1230 --mode replay-real-minutes`):

| | Main (new ratings) | This branch (new ratings) | Main / branch (older ratings) |
|---|---:|---:|---:|
| League metrics in band | 18/18 | 18/18 | 18/18 / 18/18 |
| Points per game (real 115.6) | 115.50 | 115.36 | identical |
| Offensive rebound % (real 26.0) | 25.7 | 25.2 | identical |
| Points per 36, average miss | 1.264 | 1.283 | identical |
| Shot attempts per 36 | 1.117 | 1.126 | identical |
| Rebounds per 36 | 1.197 | **1.156** | identical |
| Assists / turnovers / steals / blocks per 36 | 0.461 / 0.334 / 0.193 / 0.214 | 0.470 / 0.328 / 0.195 / 0.217 | identical |

Rebounding follows players better (Diabaté 7.9 → 8.9 per 36, real 12.0; Gobert 10.2 → 11.0, real 13.2). League
offensive rebound percentage drifts 0.5 down (still well inside the band); the other small moves come from
rotations shifting with the new values.

Tests: `test_impact_value`, `test_trait_adapter`, `test_ratings_model`, `test_box_stat_tiebreak` pass. Full suite:
1,705 tests, no failures; 18 errors, all missing git-ignored files in this worktree (experimental-engine reference
fixtures under `output/` and the startup video), none touching the changed code.

## 7. Open questions for the user

1. Rebuild the engine's "Screening" from the screening skill inputs (section 4)? Small sim effect, fixes what the
   card shows.
2. The energy bigs' remaining gap is mostly the on/off measures' view of their offense and the model's shrinkage of
   elite defenders. Accept, or try a defense model that separates rim/interior defense from perimeter defense? (It fit
   LEBRON better but agreed less with the other measures, so it was left out.)
3. Ingram's simulated efficiency (0.64 vs real 0.57): look at how the shot-difficulty tendency sets make rates?

## Files

- `src/nba_gm_data/trait_adapter.py` (offensive_rebounding recipe, adapter version v4)
- `src/nba_gm_data/impact_value.py` (`orb_per75`, offense-only predictors)
- `scripts/fit_offensive_rebounding.py` (new), `scripts/fit_impact_value.py` (offense-only columns, version v5)
- `data/canonical/offensive_rebound_scale.json` (new, derived numbers only), `data/canonical/impact_value_fit.json`
- `tests/test_impact_value.py`
