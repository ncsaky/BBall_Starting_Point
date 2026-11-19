# VALUE-REFIT: player value formula refitted (defense groups, analysts first)

Owner: Claude (Opus agent), worktree branch `worktree-agent-a6e7e4c894eef2108`. Status: **review** (committed on the
branch; not pushed or merged). Follows `ratings-consensus.md`, `analyst-first.md` and `energy-bigs.md`.

## TL;DR

1. The value formula now reads defense as three groups (rim/interior, perimeter, help) and pays extra for elite rim
   protection, and it is fitted to a 60/40 blend of analyst rankings and impact numbers. Wembanyama goes 6th -> 3rd
   (card 86.6 -> 92.4, Jokić 97.8, Gilgeous-Alexander 96.8); Holmgren 26th -> 15th, Mobley 34th -> 25th, Gobert 101st -> 79th.
2. The formula follows the analysts only where the ratings give it something to read. Brunson rises (57th -> 46th) and
   Young rises (292nd -> 176th), but both stay far below the analysts. Edwards, Maxey and Brown slip a few places
   because the rim protectors passed them. Their value didn't change; the ratings don't show what the analysts credit them for.
3. Real-stat targets hold 18/18. Betting-odds accuracy is a hair worse (Brier 0.1959 -> 0.1963, log loss 0.5786 ->
   0.5796). The new defense structure alone costs almost nothing. The analyst blend costs the rest: it moves value
   away from what the betting market prices.

## Resume state (done)
- [x] Worktree links, baseline consensus comparison (`output/value-refit/consensus_before.json`).
- [x] Experiments (scratch scripts; results summarised in section 2), new value formula, new fit script, refit written.
- [x] Consensus after, top-of-league before/after, AI trade-market values before/after, both scorecards, a run with
  impact numbers only (to split the odds change), tests.
- Local working files (git-ignored) are in `output/value-refit/`. They include the consensus files, the fit files
  (before, impact-numbers-only, final), top-of-league lists, market values and scorecard logs. The worktree links were
  removed before committing.
- The coordinator does not need to rebuild any data. The fit reads the analyst lists from the main checkout's
  `output/ratings-consensus/raw/`, so `scripts/fit_impact_value.py` only reruns where that folder exists.

## 1. What changed in the formula (`src/nba_gm_data/impact_value.py`)

**Defense in three groups** (was one average of all 14 defensive skills):

| Group | Skills |
|---|---|
| Interior / rim | interior positioning, contest technique, foul control |
| Perimeter / on-ball | containment, contact leverage, screen navigation, on-ball steals |
| Help / rotation | rotation reading, off-ball position, closeouts, anticipation, passing-lane interceptions, attention, communication |

**Two elite rim-protection terms.** Each is zero at or below the league middle and grows with the square of the
distance above it. One applies to the interior skill group (middle = 50), the other to the rim-deterrence rating
(middle = 50). With non-negative weights, a better defender never loses value, and nothing is capped. Wembanyama's
rim-deterrence rating of 105.5 keeps counting past 100.
Why the curve: a straight line still under-predicted every elite rim protector (Wembanyama's defense +2.7 predicted vs
+4.2 real). In testing, the squared terms lifted the out-of-sample defensive fit from 0.885 to 0.901. Hinges at 60, 65
or 70 and a "best defensive group" term were also tested; they were no better.

**Layers kept separate.** The defensive groups and the elite terms count only toward defense. Before, the old single
defensive average carried some offensive weight as a stand-in for "plays center." The card's OFF and DEF now come
from separate skills.

**Playmaking (tested, not added).** I gave the fit an involvement x passing term, a separate playmaking group (passing
reads, passing execution, attack recognition), passing folded into creation, and an off-the-dribble shooting split.
Every time, the fit gave passing zero weight or got worse (offense 0.925 -> 0.914 when passing was folded into creation).
Among players with the same involvement and self-creation, better passing grades don't predict more impact in this
data. I did not force a weight by hand. Young's rise comes from the new target and the defense changes, not from a
passing bonus.

All 94 inputs still feed the model. No player's inputs changed.

## 2. Fitting target (`scripts/fit_impact_value.py`)

- **Analyst side.** Three sources: ESPN NBA Rank 2026, The Ringer Top 100 and the Nerd Sesh redraft (the
  ratings-consensus sources). A player's analyst rank is the mean of his ESPN and Ringer ranks (110 if one top-100
  list leaves him out) plus his redraft pick if he was picked. The analysts' order is placed on the impact scale: the
  analysts' Nth player gets the multi-year LEBRON total of the Nth best player in the fit sample.
  Basketball Index impact is left out of the analyst side because it is already the other half of the blend.
- **Blend.** Target = impact + 0.6 x (analyst value - impact). The difference is split between offense and defense in
  the league's own proportion: 70% offense, from regressing each side's LEBRON on the total.
- **Why 0.6.** You asked for analysts first, so the weight is above half. The analyst-first report recommended 50-65%.
  0.6 sits inside that range without going to its edge, and no scorecard picked it. The fit barely moves between 0.5
  and 0.65. Game ranks at 0.5 / 0.65 / 1.0: Brunson 45 / 44 / 43, Edwards 16 / 16 / 14, Young 206 / 196 / 173.
- **Impact only:**
  - Players no analyst list ranks.
  - Players the analysts rank below their impact because of age or availability. The rule is: age 35+ or under
    1,000 minutes in 2025-26, and only when analysts rank him lower. This covers Kawhi Leonard, Jimmy Butler, James
    Harden, Anthony Davis, Domantas Sabonis and Dejounte Murray. Analysts mark these players down for expected missed
    games and decline, which the injury and aging models already handle. The value measures ability when playing.
- **Left out of the fit: 46 players drafted in 2025.** Their analyst rank is a projection, their LEBRON covers one
  rookie season, and their inputs are still mostly priors. Their value still comes from the same formula. Leaving
  them out raised the out-of-sample fit (offense 0.917 -> 0.925).
- **Fit honesty.** Ridge regression as before: minutes-weighted, non-negative except body measures and involvement,
  5-fold cross-validation, 408 players.

| Out-of-sample correlation | Offense | Defense | Overall |
|---|---:|---:|---:|
| Old formula refitted on current inputs, impact target | 0.913 | 0.873 | 0.878 |
| New formula, impact target only | 0.920 | 0.899 | 0.893 |
| New formula, blended target (shipped): vs its target | 0.925 | 0.901 | 0.901 |
| New formula, blended target: vs plain impact numbers | 0.920 | 0.899 | 0.890 |

The new formula predicts plain impact numbers better than the old one, even while it aims at the blend.
Coefficients (standardized) are in `data/canonical/impact_value_fit.json`.
- Largest offensive weights: involvement 0.53, involvement x creation 0.55, offensive rebounds 0.34, involvement x
  shooting 0.23, involvement x two-point efficiency 0.21, three-point volume 0.19.
- Largest defensive weights: help group 0.37, elite rim-deterrence term 0.21, involvement -0.22, rim deterrence 0.13,
  rebounding 0.13, elite interior term 0.09, perimeter group 0.09, interior group 0.05.

## 3. Before / after

**Agreement with the analyst consensus** (`scripts/research/ratings_consensus.py`; the consensus includes Basketball
Index impact as one of its four sources). Each cell is correlation / rank correlation / median gap.

| | Before | After |
|---|---|---|
| Top 50 | 0.676 / 0.757 / 8 | **0.692 / 0.762 / 8** |
| Top 80 | 0.618 / 0.743 / 14 | **0.680 / 0.744** / 16 |

Part of this is in-sample: the target uses the analyst lists.

**Named players** (game rank before -> after; the blended target's rank in brackets):
Wembanyama 6 -> **3** (1), Edwards 14 -> 17 (11), Brunson 57 -> **46** (14), Maxey 27 -> 30 (20),
Jaylen Brown 36 -> 44 (32), Trae Young 292 -> **176** (61), Holmgren 26 -> **15** (9), Gobert 101 -> **79** (45),
Adebayo 54 -> 60 (19), Mobley 34 -> **25** (18).

- **Edwards, Maxey, Brown.** Their net value barely moved (Edwards +4.42 before and after). The new defense structure
  pulled them down a little and the analyst blend pushed them back up (Edwards +0.34 vs the impact-only fit). They
  slipped because rim protectors moved past them. The formula can't follow the target further from their ratings:
  Edwards is predicted near +4.4 against a target of +4.7.
- **Brunson** is predicted +4.3 on offense against a target of +5.35. None of the shooting or creation splits I
  tested closed that gap.
- **Adebayo** is a switch defender, not a rim protector. The help group carries most of the defensive weight, and his
  passing reads are still middling, so he lost a little ground.
- **Other moves.** Up: Zubac 109 -> 73, Garland 111 -> 83, Jarrett Allen 52 -> 39, Kessler 65 -> 54. Down: Franz
  Wagner 40 -> 58, Anunoby 42 -> 57, Zion 31 -> 45, Suggs 24 -> 35, Bridges 87 -> 106.

**Top 15 by the engine's value** (card OVR):

| # | Before | After |
|---:|---|---|
| 1 | Jokić 97.8 | Jokić 97.8 |
| 2 | Gilgeous-Alexander 96.3 | Gilgeous-Alexander 96.8 |
| 3 | Dončić 91.5 | **Wembanyama 92.4** |
| 4 | Giannis 86.9 | Dončić 90.6 |
| 5 | Kawhi Leonard 86.6 | Giannis 87.9 |
| 6 | Wembanyama 86.6 | Kawhi Leonard 85.9 |
| 7 | Mitchell 81.0 | Mitchell 80.6 |
| 8 | LeBron James 80.8 | LeBron James 80.5 |
| 9 | Cunningham 79.6 | Cunningham 79.4 |
| 10 | Curry 78.8 | Haliburton 79.1 |
| 11 | Tatum 78.8 | Embiid 78.8 |
| 12 | Haliburton 78.2 | Curry 78.3 |
| 13 | Embiid 76.0 | Tatum 77.8 |
| 14 | Edwards 76.0 | Porziņģis 77.3 |
| 15 | Barnes 74.8 | Holmgren 76.3 |

**The card.** The top three are now Jokić 97.8, Gilgeous-Alexander 96.8 and Wembanyama 92.4. In impact units that is
+7.65 / +7.52 / +6.89. Wembanyama's real multi-year LEBRON is +7.66; the formula still under-predicts his defense by
about 0.9, so the top three are close but not fully tied. His DEF shows 97.8, the league's best defense. No value is
clipped: the card is a straight line through the engine's value, and the best players on OVR, OFF and DEF all sit at
97.8 by construction.

## 4. Scorecards

**Real-stat targets** (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**. Average per-36
bias vs real is essentially the same as main after the analyst-first change:

| Stat | Bias per 36 |
|---|---:|
| Points | -0.50 |
| Shots | -0.49 |
| Rebounds | -0.10 |
| Turnovers | -0.03 |
| True shooting | +0.002 |

Largest misses are the familiar ones: AJ Green's shooting, Draymond Green's turnovers, Wembanyama's blocks.

**Betting odds** (`validate-season-probabilities --runs 100`, 1,231 games, 1,018 with market odds):

| | Brier | Log loss | Spread error | Totals error |
|---|---:|---:|---:|---:|
| Main (before; coordinator's figure) | 0.1959 | 0.5786 | 4.566 | 5.472 |
| New formula, impact target only | 0.1960 | 0.5790 | **4.541** | 5.471 |
| New formula, 60% analysts (shipped) | 0.1963 | 0.5796 | 4.567 | 5.493 |
| Market | 0.1962 | 0.5740 | | |

**Why it is worse.**
- The formula change itself (defense groups, elite rim protection, rookies out of the fit) is neutral for win
  probability. It slightly improves the point-spread error.
- The analyst blend adds +0.0003 Brier and +0.0006 log loss. Team strength in the sim reads this value. Compared with
  the impact-only fit, the blend moves value (relative to the league) toward high-usage scorers and creators:
  Durant +0.43, Ingram +0.36, Edwards +0.34, Cunningham +0.30, Maxey +0.28, Booker +0.26. It moves value away from
  low-usage rim-running bigs, who look better in impact numbers than in analyst lists: Clingan -0.38, Mitchell
  Robinson -0.32, Jarrett Allen -0.28, Gobert -0.28, Kornet -0.23, Hartenstein -0.22. The market prices something
  close to the impact view, so the sim's odds drift from the market's.
- This is the same tradeoff the analyst-first change made, now much smaller: +0.0004 Brier against +0.0022 there.
  Seed-to-seed noise is about 0.0001. Nothing was tuned to this test.
- If you want the odds back, set the analyst weight to 0 (`--analyst-weight 0`). That keeps the defense fix and costs
  the analyst lean.

## 5. AI trade values

The AI trade market reads this value (through `transactions.py`, which was not edited). Market value before -> after
(market rank):
- Wembanyama 94.9 -> 95.2 (4th, unchanged)
- Giannis 90.4 -> 88.0 (6th)
- Holmgren 77.7 -> 81.0 (23 -> 17)
- Mobley 75.0 -> 77.0 (27 -> 23)
- Gobert 59.1 -> 62.1 (148 -> 104)
- Brunson 74.1 -> 75.9 (33 -> 26)
- Young 42.8 -> 48.3 (307 -> 270)
- Edwards 79.2 -> 77.9 (18 -> 20)

The top three are unchanged: Gilgeous-Alexander 113.9, Jokić 107.0, Dončić 104.3. LeBron's fixed value is untouched.
The star market-value tests pass unchanged. Giannis vs LaMelo is 19.2 points against a required 18.

## 6. Tests

All of these pass:

| Suite | Result |
|---|---|
| Core suite (`scripts/run_core_tests.sh`) | 337 OK (2 skipped) |
| Value-model tests (one new) | 7 OK |
| Card / profile (`tests.test_player_profile`), exact-cache parity (`tests.test_inputs_caches`), star market value, multi-team / premium / summer trade tests | 57 OK |
| All `tests/test_trade_*` modules | 151 OK (1 skipped) |

Four trade-script tests only import when `scripts/` (and, for one, `tests/`) is on the import path. Run that way,
they pass: 13 + 4 OK. No trade test pinned an old value, and no trade code was edited. The full suite was not run.
This change only touches the value formula and its data file, and the core suite covers the save and engine paths
that read it.

## Files

- `src/nba_gm_data/impact_value.py`: three defensive groups, elite rim-protection terms, defense-only columns.
- `scripts/fit_impact_value.py`: blended target, impact-only rules, rookies out, cross-validation against both targets.
- `data/canonical/impact_value_fit.json`: refit, version `impact_value_fit_v6_analyst_blend_defense_groups_2026_11_19`.
- `tests/test_impact_value.py`: new test. Defensive groups don't touch offense; better is never worse; elite steps are
  worth more; no cap; an elite interior specialist beats an all-rounder with the same defensive average.
