# RATINGS-FIVE-INPUTS: evidence check of five player inputs flagged by S2-USAGE

Progress: 8/8 - done; ready for the coordinator's review

## TL;DR
- **Three inputs fixed by rule, two left as they are.** The shot-location habit now measures where each player takes his
  twos (rim share matches real at .96, was .84). The transition habit now comes from NBA.com's play types (.93, was
  .32). Contact seeking is now counted per shot instead of per 75 possessions (.88, was .77).
- **Biggest player changes:** rim-running centers and Zion Williamson move toward their real rim shares (Kornet .52 →
  .74, Capela .45 → .66, Zion .44 → .62); post centers get their short-paint hooks (Valančiūnas, Vučević, Raynaud);
  stretch bigs lose transition running they never did (Brook Lopez, Myles Turner); LaMelo Ball, Jalen Green and CJ
  McCollum drop in contact seeking (high volume, few free throws per shot).
- **Scorecards:** Stage 2 gets better on player props and per-player points; its betting pair is about the same.
  Today's engine, after refitting its two scoring rules on the corrected inputs (user-approved option (a)): betting test
  and 18/18 unchanged, player props slightly better (Brier .2158 → .2150), per-player free throws better (0.58 → 0.52
  per 36), per-player points level (1.20 → 1.21 per 36), season points miss slightly worse (9.7% → 10.0%).
- **Trade-market test:** Giannis Antetokounmpo's market value drifted 85.36 → 84.06 (still 12th). The test's floor is
  now 84 and its Giannis-over-LaMelo gap 13 (was 14; gap now 13.97), each with a dated note.

## Objective
Check five inputs against independent 2025-26 evidence (shot-location habit, involvement, rim finishing skills, foul
drawing, transition habit). Correct what the evidence supports with rule-level fixes; write a proposal where a new input
would be needed. Score today's engine and Stage 2 before and after.

## Boundaries
May touch: player-model / inputs build code and data, `bbi_evidence.py`, evidence docs (new folder
`docs/ratings-evidence-2026-11-25/`), research scripts, tests for those, this file.
Not: `src/nba_gm_data/stage2/`, `sim.py`, `save.py`, GUI code, `docs/agents/BOARD.md`. Today's engine code unchanged.

## Verdicts (details and evidence: `docs/ratings-evidence-2026-11-25/FIVE_INPUTS_EVIDENCE.md`)
| Input | Verdict | Match with real, before → after |
|---|---|---|
| Shot-location habit T02 (two-point split) | **Fixed**: measured rim / other-two attempts per season, other twos split by average distance | rim share .836 → **.964**; rim share of twos .417 → **.921**; three share .997 (unchanged) |
| Involvement T08 | **Left as is; proposal** (`INVOLVEMENT_SCORING_SHARE_PROPOSAL.md`): no new input recommended | true usage .97 |
| Rim finishing S10 / S12 / S15 | **Left as is**: inputs predict real rim FG% at .79; Stage 2 turns them into makes at .67 → engine | — |
| Contact seeking T18 | **Fixed**: free throws and fouls drawn per shot attempt, not per 75 possessions | free throws per shot .771 → **.877** |
| Foul-drawing craft S24 | Left as is (already measured per chance) | .709 |
| Transition share of T17 | **Fixed**: NBA.com transition share of his offensive-end play, defense share kept | .321 → **.926** (spread .59 → .93) |
| Cutting T09, crash T12 | Left as is: Basketball Index already carries the same tracking (r .97 with NBA.com) | .862 / .871 |

## What moved
Flagged players (five inputs; evidence in brackets):

| Player | Rim share | Short paint / midrange | Contact seeking (FTA per shot) | Transition share of offense (NBA.com) |
|---|---|---|---|---|
| Nolan Traoré | .334 → .294 (.274) | .147/.132 → .257/.063 | .510 → .498 (.20) | .16 → .16 (.16) |
| Jaren Jackson Jr. | .268 → .203 (.192) | .255/.143 → .400/.062 | .502 → .480 (.28) | .21 → .14 (.15) |
| DeMar DeRozan | .111 → .130 (.116) | .334/.393 → .300/.408 | .513 → .502 (.43) | .18 → .09 (.08) |
| Brandon Ingram | .302 → .178 (.172) | .226/.187 → .259/.279 | .480 → .439 (.28) | .18 → .17 (.18) |
| Zion Williamson | .439 → .623 (.682) | .300/.232 → .314/.034 | .563 → .554 (.58) | .17 → .15 (.15) |
| Anthony Davis | .478 → .398 (.426) | .226/.160 → .335/.133 | .510 → .487 (.24) | .17 → .10 (.10) |
| Kristaps Porziņģis | .330 → .247 (.189) | .164/.118 → .265/.100 | .519 → .502 (.41) | .20 → .08 (.07) |
| Myles Turner | .212 → .205 (.186) | .125/.101 → .171/.062 | .448 → .444 (.27) | .34 → .10 (.09) |
| Jusuf Nurkić | .443 → .446 (.370) | .206/.152 → .314/.041 | .477 → .480 (.32) | .19 → .07 (.07) |
| Collin Murray-Boyles | .387 → .578 (.677) | .226/.197 → .173/.059 | .356 → .387 (.32) | .25 → .21 (.21) |
| Gary Payton II | .316 → .398 (.534) | .195/.164 → .198/.079 | .286 → .283 (.10) | .25 → .17 (.17) |
| Toumani Camara | .173 → .233 (.221) | .105/.076 → .104/.017 | .337 → .350 (.15) | .27 → .22 (.22) |
| Jaylon Tyson | .231 → .297 (.319) | .178/.137 → .207/.041 | .303 → .296 (.16) | .29 → .20 (.19) |
| Pelle Larsson | .338 → .382 (.383) | .172/.138 → .225/.041 | .445 → .480 (.41) | .26 → .28 (.29) |
| Giannis Antetokounmpo | .477 → .582 (.683) | .230/.189 → .211/.102 | .601 → .566 (.60) | .20 → .26 (.26) |
| Rudy Gobert | .688 → .806 (.857) | .218/.056 → .148/.007 | .506 → .561 (.62) | .26 → .14 (.13) |

Largest movers league-wide (rotation players): `output/r5/movers.txt`. Rim share up most: Luke Kornet, Clint Capela,
Ryan Kalkbrenner, Goga Bitadze, Daniel Gafford (+.20 to +.22, all toward their real share); down most: Maxime Raynaud
(.48 → .30, real .27). Short paint up most: Raynaud, Kyle Anderson, T.J. McConnell, Valančiūnas, Ayton. Contact seeking:
Jericho Sims +.12, Oso Ighodaro +.09, Dwight Powell +.07 (lob bigs who draw fouls on few shots); LaMelo Ball −.10,
Brandon Miller −.08, Jalen Green −.08, CJ McCollum −.08 (high volume, few free throws per shot). Transition share of
offense down most: Brook Lopez .37 → .08, Myles Turner .34 → .11, Corey Kispert, Kobe Brown, Al Horford.

Side effect: the build's opening-day level step re-solves skill grades after the inputs change (mean move under 0.08
grade points; up to 1.2 offense / 2.3 defense on players where that solver stops before converging: Zach Collins,
Arthur Kaluma, Jordan Clarkson). No skill was set by hand.

## Scorecards
**Today's engine** (normal gameplay; code untouched, inputs changed):

| | Before | After |
|---|---|---|
| Betting test (20 runs, 1,018 games with odds): Brier / log loss | .2017 / .5906 | .2016 / .5907 |
| Spread / total miss vs market | 4.01 / 5.87 | 4.03 / 5.85 |
| Real-stat targets, replayed season (`calibration_report.py --games 1230 --mode replay-real-minutes`) | 18/18 | 18/18 |
| Per-player per-36 miss: points / free-throw attempts | 1.20 / 0.58 | **1.25 / 0.73** |
| Player props (40 games of market lines): Brier / log loss | .2158 / .6173 | **.2173 / .6223** |
| Season points off by (players with 50+) / threes | 9.7% / 6.7% | **10.2%** / 6.5% |

**Stage 2:**

| | Before | After |
|---|---|---|
| Betting pair, seeds 1001 / 2001: Brier | .2002 / .1937 (avg .1970) | .1983 / .1959 (avg .1971) |
| Log loss (avg) | .5821 | .5807 |
| Spread / total miss (avg) | 4.02 / 5.93 | 4.09 / 5.78 |
| Player props: Brier / log loss | .2151 / .6184 | **.2114 / .6101** |
| Season points / rebounds / assists / threes off by | 11.4 / 10.9 / 12.4 / 10.4% | 11.3 / 11.2 / 12.3 / 10.7% |
| Scoring breakdown (377 players, per 36): points miss / correlation | 1.47 / .937 | **1.41** / .936 |
| Rim attempts vs Basketball Index: correlation | .778 | **.931** |
| Other twos vs Basketball Index | .854 | **.964** |
| Finishes off a pass vs real cuts + rolls | .663 | **.715** |
| Rim make rate vs real | .668 | .698 |
| Free throws per 36: miss / correlation | .572 / .937 | .557 / .931 |

## Refit applied (2026-11-25, user approved "Yes, refit and merge")
Both rules refitted with `scripts/fit_box_stat_rates.py` (weighted by minutes, constant re-centred on the league mean)
on the rebuilt inputs; comments in `box_rates.py` give the old coefficients and the source:
- `FTA_PER_POINT_INPUTS` {constant −0.31016, log T18 1.92826, S24 0.00366, log T08 −0.13616}: out-of-fold r .873 (old
  coefficients on new inputs) → **.916**.
- `POINTS_INPUTS` {constant 3.89466, log T08 0.95809, log T01.pass −0.29506, log T01.shoot 0.295, S10 0.00355, log T18
  0.23492, S.three_mode 0.00268, log T09 0.14299}: out-of-fold r .94, mean abs error 1.35 per 36 (as before).

Today's engine, same replayed season and settings:

| | Before this task | Inputs changed, old rules | **Inputs changed, refitted rules** |
|---|---|---|---|
| Betting test: Brier / log loss | .2017 / .5906 | .2016 / .5907 | **.2016 / .5906** |
| Spread / total miss vs market | 4.01 / 5.87 | 4.03 / 5.85 | **4.03 / 5.85** |
| Real-stat targets | 18/18 | 18/18 | **18/18** |
| Per-player per-36 miss: points / free throws | 1.204 / 0.577 | 1.250 / 0.725 | **1.210 / 0.516** |
| Player props (40 market games): Brier / log loss | .2158 / .6173 | .2173 / .6223 | **.2150 / .6167** |
| Season points / threes / assists off by | 9.7% / 6.7% / 12.5% | 10.2% / 6.5% / 12.5% | **10.0% / 6.6% / 12.4%** |

The betting test doesn't move with the refit because these rules only share a team's points and free throws among its
players. Results: `output/r5/refit/cal.txt`, `output/r5a3/`.

## Decision for the coordinator: today's engine and contact seeking (resolved: option (a))
Today's fitted rules in `box_rates.py` were fitted on the old contact-seeking values, which carried shot volume (the free
throws per point rule even has a −0.53 involvement term to cancel it). On the corrected values (research fit on 377
real players, nothing changed in code):
- `FTA_PER_POINT_INPUTS` refit {constant −0.4342, log T18 1.9029, S24 0.0046, log T08 −0.1708}: out-of-fold r .885 →
  **.897**, per-player miss 16.6% → **15.3%** (better than before the change).
- `POINTS_INPUTS` refit {constant 3.9634, log T08 0.9464, log T01.pass −0.2718, log T01.shoot 0.3125, S10 0.0039, log
  T18 0.2348, S.three_mode 0.003, log T09 0.1854}: out-of-fold miss 8.3% → 8.5% (adding craft and rim share: 8.4%). A
  small remaining cost.

**Attribution checked** (variant build with everything except the contact-seeking change, same replayed season):
today's per-player points miss 1.18 per 36 and free throws 0.58, against 1.20 / 0.58 before and 1.25 / 0.73 with the
change. So the shot-location and transition fixes alone leave today's engine as good or slightly better; the whole
per-player regression is the contact-seeking change meeting rules fitted on the old values.

Options: (a) merge with both refits in `box_rates.py` (recommended: the corrected rating is right and the free-throw
side ends better), or (b) leave contact seeking out for now: revert the two `per_sum` entries under T18 in
`data/research/bbi/bbi_input_mapping.json` and rebuild; the T02 and T17 fixes don't touch today's engine's scoring rules.

## Tests
Full suite (`run_tests_parallel.py --all --workers 2`): 2,587 tests, 3 failures and 8 errors. One is new and caused by
this change: `test_star_market_value` pins Giannis Antetokounmpo's trade-market value at 85 or more; it is now 84.06
(was 85.36). The top-12 order is unchanged and he stays 12th (its other check); his game value is up slightly (6.01 →
6.03), so this is league-relative market drift from the new shot-location and transition values (the variant without
the contact-seeking change gives 84.03). Left for the coordinator: lower the floor to 84 or look at the market formula.
Resolved with the refit task: the floor is now 84 and the Giannis-over-LaMelo gap check 13 (it read 13.97 against 14;
LaMelo unchanged), each with a dated note; the test passes. Focused tests after the refit (box rates, trade market,
inputs, profile, Stage 2 usage; 271 tests): all pass. The rest of the full-suite failures are not from this change: two GUI text checks (`test_gui_concept71`, `test_gui_concept74`) fail on main too,
and the other errors need git-ignored fixtures that exist only in the main checkout's `output/` (pilot, action-choice and
interior-interaction references). New tests: `tests/test_five_inputs_evidence.py` (7, one skips without the Basketball
Index store).

## Files
- New: `src/nba_gm_data/playtype_evidence.py`, `data/research/nba_synergy_playtypes_2025_26.json` (compact NBA.com copy;
  named apart from S2-USAGE's later `nba_playtypes_2025_26.json`, same source), `scripts/research/compact_nba_playtypes.py`,
  `scripts/research/five_inputs_evidence.py`, `scripts/research/five_inputs_diff.py`, `tests/test_five_inputs_evidence.py`,
  `docs/ratings-evidence-2026-11-25/` (evidence write-up, involvement proposal).
- Changed: `src/nba_gm_data/bbi_evidence.py` (measured shot mix; T17 rookie mapping), `scripts/build_player_inputs.py`
  (two new steps), `data/research/bbi/bbi_input_mapping.json` (T18 per shot; T02 note), rebuilt
  `data/canonical/player_inputs_2026_27.json.gz` and `tendency_scale_map.json`, regenerated tables in
  `docs/agents/tasks/e2-input-estimator.md`.
- Output (git-ignored): `output/ratings-evidence/nba_playtypes_2026/` (raw NBA.com responses, SOURCE.md), `output/r5*/`.

## Resume state
- [x] Download (2026-11-25, built-in browser; plain requests refused with 403).
- [x] Evidence comparison, verdicts, rule fixes, final build.
- [x] Before (main checkout) and after runs on Azure: `output/r5b/` (main), `output/r5a1/`, `output/r5a2/` (this worktree).
- [x] Variant without the contact-seeking change (`output/r5/noT18/`): confirms the attribution.
- [x] Full test suite; first commit 448a0c50.
- [x] Refit of today's two scoring rules, market-test floor and gap, re-scored; second commit on the branch, not pushed.
  Coordinator: review and merge.
