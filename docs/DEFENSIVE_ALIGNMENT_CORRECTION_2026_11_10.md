# Defensive alignment correction — November 10, 2026

**Historical scale/preview notice:** the follow-on [rating-scale comparison](DEFENSIVE_SCALE_COMPARISON_2026_11_10.md) supersedes this report’s mixed display convention and preview URL. All player ratings now use direct model grades; Wembanyama has a later post-alignment rim 99→100 correction. This report retains the original measurements and input claims as historical evidence. Latest verified isolated backend: **http://127.0.0.1:8798/**.

**Implemented:** shared defensive abilities, a bounded monotone rim response, effective-rim semantics and a defined headline DEF. Production uses this correction; the earlier prototypes remain reference evidence. Raw player traits are unchanged. No offensive batch, Castle/Paolo trait patch, GUI redesign, role taxonomy, prospect ability, development, market-policy or quota change was made.

**Current-task checkpoint:** this is the defensive correction, not the completed settlement optimization. Implementation and final verification are complete. Evidence: `output/defensive-alignment-correction-2026-11-10/`; pre-edit backend: `reference/src`; original input: `canonical-before.json.gz`. Do not restart the audit or repeat baseline games. Existing careers are disposable development saves: no legacy defensive-version gate, migration framework or save deletion was added. Stop after this correction.

The verified new isolated preview is **http://127.0.0.1:8797/**, PID **95084**, with a genuinely new career created through HTTP. Existing previews, including 8796, were preserved. **8796 is not the newly corrected backend.**

## Meaning and shared implementation

`defense.py` supplies pure, uncached calculations to `sim.py`, `save.py` and `spatial.py`. The backend ratings guide in `play.py` describes the new meaning. Team, matchup, health and minutes calculations remain distinct from a player's headline grade.

| Quantity | Definition / use |
|---|---|
| Raw rim deterrence | Estimated **effective rim ability**, already informed by block rate, height, impact and defensive-role priors. Subsequent calibration/scouting can replace it. It is not size-neutral technique. |
| Activity | `.42 effort + .36 lateral agility + .22 navigation`, the established normalized gameplay calculation. Three 70s produce 70. |
| Effective rim response | Existing low/mid response through raw 80, followed by the monotone shoulder below. Shared by scalar features and spatial paint abilities. |
| DEF skill | `.60 activity + .40 effective rim`, bounded 1–99. These are the existing matchup defender-grading weights, not a positional ranking target. |
| Card DEF | Directly displays that skill grade, rounded to one decimal. Other ratings retain their presentation curve. DEF is not a shooting percentage or percentile. |
| Scheme IQ | Continues to affect spatial help/contests, passing, IQ and team context; it is not another independent event-creation observation in DEF. |
| Weak-link integrity | Retained as neutral-relative matchup targeting information. Its neutral 50 is **not** averaged into DEF skill. Existing contextual rollups/anchors remain separate, including their general-impact contribution. |

Engine OVR retains its existing weights and role-skill blend, consuming shared DEF. Role-aware impact uses the same defensive skill definition. Retention, role and valuation consequences propagate normally; this is not a display-only cut. No new physical or positional bonus was invented.

Source uncertainty remains: effort/navigation/agility share correlated deflection, steal, impact and role proxies; subjective calibration can elevate several related traits. No independent evidence or higher confidence was invented. Research's [semantic review](ratings-evidence-2026-10-29/DEFENSIVE_SCALE_SEMANTICS_REVIEW.md) supports the effective-rim interpretation, while distinguishing containment, navigation, help and anchoring. It does not establish exact weights or universal positional ordering.

## Size, labels and opportunity

Controlled comparisons hold identity, traits and context fixed. Before editing, raw rim 80 at heights **77/84 inches** gave identical scalar rim **83.378**, but spatial paint contest **73.80/78.60**: an extra **4.8** from height. Inference already embeds size, while spatial defense independently rewards height on the same prevention outcomes. The correction resolves this ambiguity by treating rim as effective ability, removing the second defensive height term and using the shared response in paint defense. Existing perimeter/help coefficients and stable texture remain.

Afterward, the same effective traits give equal paint contest **75.66** at either height. This is a deliberate semantic choice, not a claim that height never matters. All six controlled **offensive spatial profiles remain exactly unchanged**. Height still affects offensive geometry, starting-slot fit and hard deployment restrictions. Position alone does not grant DEF, but enabled role weighting can change OVR and assignment. Minutes do not change intrinsic DEF; lineup minutes reweight team abilities. Health/fatigue/rust still degrade game features.

Tests cover same-trait/different-height, same-height/different-rim, position-only, minutes, scheme-only and offensive-reputation changes. Better rim increases paint contest/suppression and reduces an unchanged opponent's expected spatial shot quality. Raising offense alone does not raise headline DEF.

## Rim shoulder and preserved boundaries

Through raw 80, retain `r + .18*max(0,r-68)^1.18`. Above 80, a cubic Hermite shoulder keeps the **same value and derivative at 80**, reaches **99 at raw 100**, and ends with slope **.25**. Its derivative stays positive: no elite plateau. These anchors preserve the usable low/mid scale and scarcity meaning, reserving headroom for stronger estimates. They are bounded model calibration, not empirically measured deterrence probabilities.

| Raw / example | Old game rim | New game rim |
|---|---:|---:|
| 58 / White | 58.000 | 58.000 |
| 74.25 / Kawhi | 75.815 | 75.815 |
| 76.96 / Castle | 79.353 | 79.353 |
| 80 / join | 83.378 | 83.378 |
| 90 / Duren | 96.908 | 93.895 |
| 96.82 / Allen | 99.000 | 97.945 |
| 97.43 / Kessler | 99.000 | 98.188 |
| 99.01 / Gobert | 99.000 | 98.727 |
| 100 / endpoint | 99.000 | 99.000 |

The three anchors retain their source-supported ordering without exaggerating small raw gaps. Helpers Barnes/Flagg remain distinct without center bonuses. The **78 rim-scarcity classification is unchanged throughout the tested 1–100 grid**; Castle retains its existing scarcity component, unlike the previous broad smooth control. No scarcity, premium/core, pick-investment, salary or negotiation threshold was changed to restore old prices.

## Actual cards and separation of scale effects

These are actual fresh-save `player_card` dispatches; baseline cards are the retained v11 evidence. Final HTTP verification independently confirms Kawhi DEF 86.1.

| Player | DEF before → after | OVR before → after |
|---|---:|---:|
| White | 92.5 → 73.8 | 87.1 → 86.6 |
| Castle | 92.9 → 78.8 | 85.8 → 86.1 |
| Kawhi | 97.5 → 86.1 | 94.7 → 94.3 |
| Barnes | 96.0 → 88.5 | 89.8 → 90.8 |
| Flagg | 95.4 → 86.3 | 88.6 → 89.5 |
| Gobert | 97.5 → 86.7 | 88.4 → 88.2 |
| Kessler | 95.5 → 82.9 | 86.0 → 86.4 |
| Allen | 96.0 → 83.7 | 86.9 → 86.8 |
| Duren | 88.8 → 77.9 | 85.1 → 86.7 |
| Curry | 83.8 → 55.1 | 94.8 → 93.5 |
| Luka | 67.5 → 39.0 | 88.6 → 87.1 |

These headline reductions are not equal-sized gameplay nerfs. Among **428 players projected for at least 12 minutes**, engine DEF median is **60.0 → 59.95**, while displayed DEF median is **80.0 → 59.95**. Display 10th/90th values change **63.8/93.9 → 40.9/78.9**; 90+ headlines fall **65 → 4**. The generic curve previously raised engine60 to display80 and compressed the upper tail. The new definition independently changes individual engine values/OVR; direct display separately removes that inflation/compression. No histogram target or desired player rank was imposed.

Retention scores and price components are retained in `verification.json`. They move through existing OVR/salary/age/core formulas. No actual player was cut to force a headline rank. Human rotation ownership and opportunity/retention regressions pass. Defensive subtrait cells retain their older display transforms and are not interchangeable with headline DEF; further UI explanations are outside this backend pass.

## Games and trade guardrails

The previous baseline is reused. **24 new paired games** use the same three healthy fixed-roster matchups and eight seeds (17/29/41/53/67/79/83/97). Diagnostic coach matchup minute nudges are disabled exactly as in that baseline; this is not normal dynamic-rotation career evidence.

| Matchup | Old mean points | New mean points |
|---|---:|---:|
| TOR–HOU | 107.625–115.625 | 109.375–116.500 |
| DET–BOS | 106.625–110.750 | 106.875–111.125 |
| MIN–GSW | 111.875–113.125 | 112.000–113.000 |

All new player/team boxes satisfy made/attempt bounds, nonnegative tracked stats and scoring identity. These small paired samples exercise actual gameplay but do not establish league scoring calibration or an individual causal effect: both teams' components and role-aware impact can change. Rim makes are not separately tracked; paint FG% is not claimed. Controlled component tests establish directional suppression independently of noisy scores.

Six financially legal controlled trades evaluate Kawhi/Duren/Gobert against Curry or Pat Spencer under identical known contracts and explicit core commitments. Participant decisions match the baseline; none has bilateral approval. Kawhi-for-Curry remains blocked by TOR's core commitment despite positive net value. Weak centerpiece returns retain premium rejection. Existing premium, pick-investment and application tests cover additional safeguards. Search policy, quotas, consideration and fresh settlement checks are untouched. Changed values can still change future discovery naturally.

## Contracts and negotiation

The known-legal fixture supplies identical guaranteed expiring $1.9M contracts, original ownership and a 14-player HOU roster. These are **synthetic controls**, not real terms or immediate save signings. Profiles are freshly rebuilt. All eleven opening offers are legal; first decisions and final FA/extension agreement outcomes match the old model. Accepted money can change. Duren still reaches round two; Kawhi/Gobert extensions still walk away. No agreement is applied to a save.

| Player | FA ask $M before → after | Opening bid $M | Accepted FA AAV $M |
|---|---:|---:|---:|
| Castle | 29.686 → 29.709 | 24.638 → 24.638 | 24.638 → 24.638 |
| Kawhi | 45.731 → 45.579 | 37.527 → 37.402 | 37.527 → 37.402 |
| Duren | 27.062 → 27.165 | 20.565 → 20.643 | 22.877 → 22.964, round2 |
| Curry | 31.857 → 31.803 | 25.421 → 25.378 | 25.421 → 25.378 |
| Luka | 43.790 → 41.752 | 33.127 → 31.585 | 33.127 → 31.585 |

Accepted extension AAV includes Duren **21.306 → 21.387M**, Curry **28.536 → 28.488M**, Luka **36.549 → 34.849M**. Money, years/security, role promises, fit, winning context and player/team thresholds still participate. The broad prototype's earlier Curry increase and Luka first-offer rejection do **not** recur here. Cohort/comparison effects still exist; changes to Curry's terms are not proof of a direct change to his low rim channel.

**Unmodified production contracts/rosters were checked separately.** Fresh profile FA asks move Curry **48.067 → 47.970M**, Kawhi **46.381 → 46.303M**, Luka **50.854 → 50.595M**, Castle **30.403 → 30.425M**. Their role tiers and extension eligibility gates remain unchanged. Eleven real projected-FA cases retain legality/agreement classifications: Black and Wallace legally agree, Lillard legally walks away, eight keep manual-review guards. Example opening bids: Black **22.127 → 22.469M**, Wallace **24.823 → 24.799M**. These are projections, not executed contracts; projected FA does not authorize immediately signing an already-contracted player. Save application permissions remain independent.

## Projection refresh and verification

Compiled starting projections were regenerated for consistency. Nine top-level groups change: player valuations, team strategy, contract profiles, FA/extension candidates, trade blocks, team-specific draft boards, and their metadata/coverage counts. Trade-block count becomes **108 → 100**, a derived result, not an activity-budget change. **167/1,800** team-board rows change fit/rank. All player/prospect identities, abilities, raw traits, contracts, ownership, reports and development inputs remain identical, with unchanged input mapping order preserved. Prior performance optimizations remain installed.

The canonical SHA changes from `0733a2c0ab62faf893c07d9240c23f6a47bed057205bda4bb13c08ea1b07332d`; final SHA/field changes are in `derived-refresh.json`. The v11 label identifies the unchanged trait dataset. Baseline archives/registry are untouched; no legacy framework was added. Earlier research hashes describe the preserved before input.

**147 successful checks:** 14 new component/physical tests plus 133 existing spatial, premium/core, investment, human rotation, retention, feature/context performance, presentation, contract protection, FA bid, extension identity, transaction application and v11 calibration/rebuild checks. An initial command guessed three invalid module names; its 54 executed checks passed, and correctly named remaining modules then passed. Harness stale-revision restoration and relative-path timing setup were also corrected without bypassing production protections. Initial logs remain retained.

Final fresh-model Oct20–22 **bulk/daily/midpoint reload** matches meaningful state and all **16 ordered events**, using installed production code rather than monkeypatches. Normal revision invalidation updates the card after a disposable trait-total edit; restoring the field with the current revision restores its original card. Final evidence is `final-actions-ordered/`, not provisional pre-refresh runs. Existing-career arithmetic compatibility is neither required nor claimed.

## Runtime and memory limits

Three unprofiled warm one-day fresh-start actions per backend run sequentially, restoring equivalent disposable starts outside timing. Before median/range: **2.781s (2.725–2.791)**; final after: **2.710s (2.695–2.731)**. Small sequential samples do not justify a speedup claim. First process action **23.223/3.295s** is separate; that old first-use delay remains unattributed. App dispatch is not HTTP/browser playback timing.

A separate 100-player warm attributes/features/spatial workload measures **5.877 → 6.510ms** median (five unprofiled samples): about **0.63ms more per workload**, not an end-to-end regression estimate. Tracemalloc is separate. All eight private roots release before GC. Both versions retain **1,056 bytes** after final diagnostic GC in this probe; no new cache or whole-career owner was introduced.

Four same-process action completions including warm-up show RSS MB **363/476/562/491 before**, **368/534/656/593 after**; peaks **677/764MB**. Python blocks plateau after the second read-context entry. The higher current peak remains unresolved: this does not prove long-term memory stability or harmless allocator behavior. No production GC was added. Timing windows are explicitly completed/released in JSON; UI/research work was not held throughout development.

## Remaining tuning and reproduction

- Reassess correlated raw effort/navigation/rim estimates on this scale. Castle/Paolo defensive proposals and six independent offensive proposals remain unimplemented.
- Contract comps, retention and team-specific fits can move nonlocally. Nothing here justifies restoring old prices or weakening safeguards. Broader market tuning remains separate.
- Rim anchors and the headline blend are explicit bounded choices, not tracking probabilities. More coverage/opponent samples can refine them without inventing universal positional ranks.
- Contextual anchor/targeting rollups, raw uncertainty and subtrait presentation remain distinct issues. No broad defense or GUI rewrite was attempted.
- Long-lived RSS remains open. Passing private-root release is not full-server stability.

Read-only consolidation and focused tests:

```sh
.venv/bin/python output/defensive-alignment-correction-2026-11-10/summarize.py
PYTHONPATH=src:tests .venv/bin/python -m unittest test_defensive_alignment
```

Use fresh output paths and a new quiet window for independent samples:

```sh
PYTHONPATH=output/defensive-alignment-correction-2026-11-10/reference/src:scripts \
  .venv/bin/python output/defensive-alignment-correction-2026-11-10/action_timing.py \
  --canonical output/defensive-alignment-correction-2026-11-10/canonical-before.json.gz \
  --output output/defense-new-before-timing
PYTHONPATH=src:scripts \
  .venv/bin/python output/defensive-alignment-correction-2026-11-10/action_timing.py \
  --output output/defense-new-after-timing
```

Run sequentially. `runtime_memory.py --output UNUSED.json` is separate from timing. `actions.py --output UNUSED_DIRECTORY` creates fresh careers and checks partitions. Financial/trade runners overwrite local evidence: copy them into a new directory before rerunning. The 24 new games already have a retained baseline; do not launch another baseline campaign unnecessarily. Do not rerun the preview launcher over existing directories.

Startup source/canonical fingerprints and real HTTP create/card checks are in `preview.json`/`loaded-backend.json`. Only this task's idle provisional 8797 process was gracefully replaced after checking connected requests. No pre-existing preview or active user simulation was stopped. No release packaging or follow-on batch was started.
