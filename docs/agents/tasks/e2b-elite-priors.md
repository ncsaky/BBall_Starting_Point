# E2b hierarchical family priors

TL;DR: Related skills now share player evidence through family priors; all inferred cells keep wide bands and prior labels.
Spread/ranking gates pass and game-odds errors improve, but assists and three-point attempts regress: the real-stat gate FAILS.
The three named stars improve modestly; this proposal does not resolve front-office readiness and must not be treated as accepted.

## Objective and boundaries

Use each player's observed related skills, retained impact metrics, workload and weak legacy evidence to infer related unobserved technique. No named-player overrides, outcome fitting, adapter edits, engine changes, GUI changes or commits. Owned files are the estimator, estimator tests, regenerated canonical JSON/gzip, this report and the E2b board row.

## What changed

The old position/role prior and weak personal context remain the starting point. Missing techniques now receive a further shift from that player's related observed techniques and retained provider evidence. The new family step operates only on missing technique grades. It keeps shooting, finishing, creation, post play, routes/screens, rebounding, perimeter defense, interior defense, defensive recognition, passing recognition and passing execution separate. Free throws have a different scale and are excluded. Physical tools, choice tendencies and prospect generation are unchanged.

There are still **691 players × 94 inputs**, **13,317 player-evidence estimates** and **51,637 priors**. The family step labels 26,061 prior cells; 25,842 values change. **Zero existing direct-estimate values change.** All changed records retain `reason: prior`, low confidence and a plausibility envelope at least as broad as the old one. Native schema `status` remains `estimated`, as documented by E2; `reason` is the evidence distinction.

Each inferred record retains its original attribution plus a `family_talent` evidence entry containing the assumed loading, latent mean/variance, actual source fields, exposure, connected source groups and any broad context superseded by more specific evidence. No player-name exceptions, market ranks, simulation outcomes or runtime random numbers enter the estimator.

## Declared statistical assumptions

These are reviewable working assumptions, **not correlations measured from an independent skill dataset or calibrated confidence intervals**. Numeric assumptions were fixed before checking the new outputs and were not fitted to the market report or scorecards.

- The family talent factor has a unit-normal prior. The missing-skill loading is **0.65**, on a **0.8 log-odds** scale (about 20 grade points per unit around grade 50). Positive and negative evidence transfer symmetrically. The smooth logistic transformation avoids clipping values at 100.
- A directly estimated family input contributes `(grade - position/role mean) / 20`. Its weight is `exposure_reliability / (1 + (band_radius / 20)^2)`. Exposure reliability is `n / (n + 750)` for minutes, `n / (n + 250)` for other retained opportunities, or **0.25** for qualitative assessments without event counts. These are conservative working weights: an already-shrunk estimate is not reverse-engineered into invented raw observations.
- Shared source paths and evidence-group IDs form connected groups. Group signals are averaged and their precision is the maximum individual weight, rather than their sum. Copying the same underlying passing or shooting sample into several inputs cannot multiply its precision. All groups are built from a snapshot of direct records; a newly inferred prior cannot teach another prior.
- The newest usable provider window supplies observed **CraftedOPM/CraftedDPM** (or their numeric COPM/CDPM aliases) and **OLEBRON/DLEBRON**. Correlated impact models are averaged as one clue, with fixed units of **2 offensive** or **1.5 defensive points per 100**. Projected impact, aggregate impact, percentiles and imputed IQ are excluded. Missing or nonpositive provider minutes give no new context weight.
- Provider precision is at most **2 × MP/(MP+750)** for impact, **0.5 × MP/(MP+750)** for BBallIQ and **0.15 × MP/(MP+750)** for workload/usage. IQ uses `(IQ-50)/20`; minutes/game and usage use `(minutes-24)/12` and `(usage-20)/12`. Correlated context votes are averaged and keep only their maximum precision.
- The family context loadings are declared in `FAMILY_CONTEXT`: offense loading is 0.25 for shooting, 1 for finishing/creation/post, 0.5 for routes/screens and passing; defense loading is 0.35 for rebounding and 1 for defensive families. IQ applies only to creation, routes/screens, interior/recognition defense and passing. Workload/usage applies only to finishing/creation/post. Effective impact is never labeled measured technique or physical capacity.
- More specific family evidence supersedes broad impact/IQ/workload from the same source. Existing legacy traits retain the old weak, bounded local contribution; they are not counted again as independent family observations. The existing local legacy/statistical context remains correlated with provider evidence, so the resulting bands remain deliberately broad rather than claiming independent likelihoods.
- For retained groups with signals `z` and working precisions `w`, the family mean is `sum(w*z)/(1+sum(w))`. The stored working variance is `1/(1+sum(w))`; the prior shift is `0.8*0.65*family_mean` in log-odds. Every band covers the old prior envelope and at least a 40-point radius around the new mean, bounded only at interval endpoints. These are plausibility bands, with no nominal coverage guarantee.

Basketball Index remains a dimension-specific weak provider proxy under its existing importer contract. Its observations are applied after family pooling, so adding one screen-navigation proxy does not implicitly measure adjacent skills. Other explicitly defined dimension observations can inform their related family. No paid BBI captures are present in this build.

## Acceptance results

The on-court numbers below are the engine's `on_court_value` from `scripts/market_sanity_report.py --top 691 --json-out ...`, with and without `NBA_GM_RATINGS_MODEL=inputs_v1`. They are not the card's overall rating or an estimator-created substitute.

| Check | Before E2b | E2b | Result |
|---|---:|---:|---|
| SD across the same top 50 legacy on-court players | 4.2614 | **4.5506** | Pass: legacy SD is **3.6914**, required minimum **2.9531**; E2b retains **123.27%** |
| Spearman rank correlation, projected minutes ≥15 | 0.8526 | **0.8306** | Pass: **365 players**, threshold 0.7; ties use average ranks |
| No-worse real statistics | baseline below | assists and 3PA worse | **FAIL** |
| Existing estimator, BBI and player-model checks | — | **124 pass** | Pass; determinism also verified below |

**The first two gates already passed before this change.** Their passage does not establish that star compression is fixed. Across these same 50 players, the mean on-court value is legacy **76.5782**, previous inputs **71.2556**, E2b **70.5232**. Thus the overall mean gap worsens even though the named examples improve and the spread remains wide. Legacy is a comparator, not ground truth, but this is a material unresolved warning.

| Player | Legacy on-court | Before inputs | E2b inputs | Market rank: legacy → before → E2b |
|---|---:|---:|---:|---|
| Nikola Jokić | 83.7 | 73.9 | 76.1 | 3 → 28 → 16 |
| Victor Wembanyama | 87.5 | 72.4 | 73.4 | 1 → 40 → 35 |
| Giannis Antetokounmpo | 78.6 | 68.8 | 69.9 | 23 → 66 → 54 |

## Real-stat scorecard

Both runs use the unchanged engine and adapter, **1,230 games, seed 1**, and the same **150 high-minute players**. The reproduced baseline agrees with the supplied errors. Lower average absolute error per 36 minutes is better; true shooting is a fraction.

| Metric | Before E2b | E2b | Assessment |
|---|---:|---:|---|
| Points | 3.187 | 3.156 | improves |
| Field-goal attempts | 2.369 | 2.340 | improves |
| Three-point attempts | 0.504 | 0.506 | **worsens** |
| Rebounds | 1.286 | 1.237 | improves |
| Assists | 1.018 | 1.072 | **worsens** |
| Free-throw attempts | 1.664 | 1.664 | unchanged at shown precision |
| Turnovers | 0.607 | 0.620 | worsens |
| Steals | 0.659 | 0.667 | worsens |
| Blocks | 0.656 | 0.636 | improves |
| True shooting | 0.032 | 0.033 | worsens |

League metrics remain **13/18 in band**. The first implementation gave points 3.093, FGA 2.286, 3PA 0.501, rebounds 1.263 and assists 1.072. Its source-overlap handling averaged broad impact with specific evidence from the same provider. Review changed that rule to specific-evidence precedence and preserved BBI's per-dimension contract; numeric coefficients were not tuned. The revised build still fails the no-worse gate. No further coefficient search was performed to chase the acceptance numbers.

## Fifteen largest rotation-player rank changes

Rank 1 is the highest engine on-court value **within the 365-player rotation cohort**, with average ranks for ties. These compare E2b with legacy, not E2b with the previous inputs build. Reasons describe the retained evidence and adapter changes, not validated corrections to the legacy rankings.

| Player | Legacy rank → E2b | On-court legacy → E2b | One-line reason |
|---|---:|---:|---|
| Ace Bailey | 90 → 283 | 66.24 → 52.99 | Crafted offense/defense impact is −0.7/−1.5; derived scoring versatility and defensive recognition fall well below legacy, with IQ missing. |
| Bennedict Mathurin | 131 → 305 | 62.98 → 51.35 | Derived release/range fall by 26.6/23.2; defense priors also reflect −1.4 defensive impact and IQ 30. |
| Trae Young | 100.5 → 272 | 65.06 → 53.77 | Derived scoring breadth/release are much lower; the negative defensive signal has only 384 retained provider minutes and remains uncertain. |
| DeMar DeRozan | 146 → 313 | 61.85 → 51.02 | His estimated three-point attempt share is 16.3%; derived release/range and lateral capacity are lower than legacy. |
| Javon Small | 269 → 103 | 53.48 → 64.28 | Catch-three estimate 69.7 and a 48.4% three-point share lift scoring/spacing relative to legacy; provider exposure is only 627 minutes. |
| Kyle Kuzma | 178 → 343 | 59.51 → 46.70 | Defense priors reflect −1.7 defensive impact and IQ 25; derived rim defense, recognition and effort all fall. |
| Brandin Podziemski | 303.5 → 140 | 50.82 → 61.15 | Defensive impact +1.6 and IQ 68 support higher defensive priors; derived rim defense, fit across lineups and passing rise. |
| Kasparas Jakučionis | 264 → 104 | 53.75 → 64.11 | Catch-three estimate 70.3 and a 59.4% three-point share raise derived release/range; the provider window is only 764 minutes. |
| Keon Ellis | 278.5 → 131 | 52.82 → 62.25 | Catch-three estimate 68.4, a 61.5% three-point share and +1.9 defensive impact support higher spacing and defensive priors. |
| Collin Gillespie | 164 → 23 | 60.45 → 71.84 | Provider offense/defense impact +1.5/+1.3 and IQ 77 support higher recognition/navigation; his high shooting estimate also raises spacing. |
| Ryan Rollins | 219 → 82 | 56.71 → 65.52 | Catch-three estimate 71.5 and attack-recognition estimate 69.3 raise the derived lineup-fit, scoring-translation and passing ratings. |
| Alex Sarr | 88 → 224 | 66.50 → 56.14 | Catch-three estimate 40.7, IQ 36 and −0.4 defensive impact leave derived scoring translation, rim defense and passing lower. |
| Micah Potter | 183 → 317 | 59.30 → 50.70 | Derived lineup fit drops sharply; low recognition/defensive priors reflect IQ 25 and −0.6 defensive impact over only 652 minutes. |
| Craig Porter Jr. | 317 → 186 | 49.62 → 58.24 | Defensive impact +0.9 and IQ 68 support higher recognition/effort priors and derived lineup fit than legacy. |
| Jose Alvarado | 273 → 142 | 53.12 → 61.00 | Defensive impact +0.8, IQ 61 and the retained passing evidence raise derived recognition, passing and lineup fit. |

## Betting-odds scorecard

Paired production probability validation: **1,231 scored games**, including **1,018 with market odds**, **100 runs per game**, seed 1, previous inputs versus E2b. The old inputs are isolated in an in-memory model cache; neither canonical file is overwritten during comparison. Both versions use the same engine, actual minutes, games and no-vig market probabilities. Four ordinary Python simulation processes finish in **535.1 seconds**. The before result exactly reproduces the board's full-season baseline.

| Metric (lower is better) | Before E2b | E2b | Market benchmark |
|---|---:|---:|---:|
| Brier error | 0.2114 | **0.2029** | 0.1962 |
| Log loss | 0.6177 | **0.5975** | 0.5740 |
| Average absolute spread error versus market | 5.250 | **5.207** | — |
| Average absolute total error versus market | 6.210 | **6.200** | — |

The production summary scores Brier/log loss across all 1,231 games with actual results; market-only benchmarks use the 1,018 available odds rows. This improvement does not override the real-stat failures or prove that individual player ratings are correct.

**Player-prop limitation:** both runs retain **396 prop lines**, of which **381 match simulated players/markets** and **15 are unmatched**. None has the two-sided prices needed for a no-vig over/under probability comparison. Per-line simulated distributions are retained in the audit JSON, but no passing prop-probability calibration result is claimed.

## Verification and artifacts

- Read `AGENTS.md`, the board's T3 diagnosis/readiness notes, `STAGE1_DESIGN.md` and the E2 report before implementation; assigned only E2b on the board.
- `PYTHONPATH=src .venv/bin/python scripts/build_player_inputs.py --no-report`: regenerated both canonical JSON and reproducible gzip without changing the historical E2 report or build script. Final build/comparison **10.764 s**; JSON **105,854,683 bytes**, gzip **5,340,826 bytes**. Gzip decompresses exactly to the JSON. Technique-grade range stays **19.588–90.438**; no maximum pile-up.
- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_input_estimator tests.test_bbi_import tests.test_player_model_schema tests.test_trait_adapter tests.test_ratings_model tests.test_player_profile`: **124 tests pass in 54.245 s**. The seven new synthetic tests cover positive/negative family transfer, sample-size shrinkage, missing exposure, qualitative assessment units, channel separation, wide prior bands, direct-estimate preservation and source overlap. Existing BBI per-dimension and absent-cache checks pass unchanged. A final verification build also matches both canonical files byte for byte after correcting qualitative assessment units; that correction changes no canonical values.
- `tests.test_input_estimator.ProcessDeterminismTests` also rerun after extending it to check gzip bytes: pass in **22.322 s**. JSON and gzip are identical across separate processes with different hash seeds. The seeded engine replay is identical on repeat and does not change Python's global random state. Outcomes intentionally change because inputs change; no engine RNG stream code was edited.
- Baseline/final market and calibration JSON/text, the acceptance calculation and the paired odds audit are retained under `output/e2b/`. Large artifacts remain outside docs. No engine/save code was edited; verification is the requested focused model suite and both scorecards, not the unrelated known-failing full repository suite.
- No dependency, adapter, ratings-model, transactions or GUI edits; no commits. New inference runs only during input generation. The canonical artifact is about 14 MB larger uncompressed and 0.82 MB larger compressed, so loading has that additional data cost; no new per-possession work is added.
- Concurrent changes to `.gitignore` and `scripts/bbi_capture_receiver.py` appeared during the task; neither was edited or reverted by E2b.

## Resume state and recommendation

Implementation, regeneration, 124 focused tests, market comparisons and both full-season scorecards are complete. Board status: **review**. No commits. Do not mark acceptance complete: assists/3PA fail, rotation rank agreement falls and the top-50 mean gap worsens, despite better game-odds results. Keep normal gameplay on legacy mode. Coordinator review should decide whether this partial-pooling design is useful evidence infrastructure or needs a different family observation model. A concrete evidence-focused follow-up is to retain underlying family observation likelihoods, rather than reuse already-shrunk input midpoints, and check those against independent dimension-level evidence before rerunning the engine gates. This report does not authorize changing the adapter or fitting ratings to market/simulation results.
