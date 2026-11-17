# Five-player calibration review

**2026-11-09 — research only; coordinator review precedes implementation.** This bounded review covers Anthony Edwards, Devin Vassell, Jalen Duren, Cedric Coward and Kawhi Leonard. All changes below are proposals, not edits to game data. It supersedes the five corresponding recommendations in [SYNTHESIZED_RATING_ADJUSTMENTS.md](SYNTHESIZED_RATING_ADJUSTMENTS.md). The other seven players are outside this review.

## Findings and approval table

Several current magnitudes deserve correction even though the game already represents the relevant skill. The clearest problems are Edwards' consistency/effort calibration, Vassell's offensive-versus-defensive shape, and the use of an especially strong rim-protection prior for Kawhi. Duren's 98.99 needs an explicit ceiling review: its lineage and effect cannot be validated by the existence of other highly rated centers. Coward's low defensive/connective profile reflects subjective prior calibration as well as incomplete inputs; a box-stat refresh alone does not fix it.

**“Ready” below means a concrete provisional scouting adjustment ready for coordinator judgment, not authorization to implement.** Numbers are estimates on this game's current trait scale. They are not measured percentages, podcast rank conversions, or statistically identified optimums. Confidence concerns the proposed magnitude, not merely transcription accuracy.

| Status | Player / decision | Exact proposed delta → target | Confidence / gate |
|---|---|---|---|
| **Ready** | Edwards — reduce consistent defensive activity while preserving athletic tools | `defensive_effort −10 → 73.89`; other traits unchanged | Medium. Direct current-skill criticism plus independent consistency reporting. No rim or screen-specific downgrade inferred from it. |
| **Ready** | Vassell — modestly more shooting flexibility, less consistent defensive impact | `shot_versatility +4 → 52.36`; `defensive_effort −6 → 75.80`; `rim_deterrence −8 → 60.94`; others unchanged | Medium on direction, low–medium on exact size. The episode explicitly disputes degree of defense and distinguishes occasional blocks from consistent help impact. |
| **Ready, provisional** | Duren — move below the effectively identical top rim-defense ceiling without an offensive downgrade | `rim_deterrence −8.99 → 90.00`; others unchanged, including OREB 99.40 | Low–medium. Strong early-season rim results counter an aggressive cut. A 90 trait still produces a 96.908 rim-defense feature; this is a conservative tier separation in the current nonlinear model. |
| **Ready, provisional** | Coward — recognize defensive activity/help awareness; replace the earlier passing-only proposal | `defensive_effort +5 → 63.99`; `rim_deterrence +6 → 60.89`; `scheme_iq +3 → 56.25`; `passing_reads` unchanged 58.83 | Low–medium. Expert judgments and retained independent scouting support a positive defensive/helper profile. This is a scouting overlay, not a correction mechanically implied by missing fields or awards. |
| **Ready, provisional** | Kawhi — modest scoring/handle increase and lower center-like rim influence | `shot_versatility +4 → 67.89`; `handle_pressure +2 → 76.44`; `rim_deterrence −15 → 74.25`; others unchanged | Medium on offensive direction, low–medium on rim magnitude. The large rim-feature/anchor effect is explicitly exposed below; approve these subparts separately if desired. |
| **Conditional on input-refresh policy** | Any later stat-derived adjustment to these five | No additional numerical delta approved by this review | Read the backend dry run before choosing which preserved baseline entries a measured update supersedes. It changes **0/15 final traits for every player** under the current pipeline. Do not stack raw-inference differences or these scouting overlays twice. |
| **Needs specific evidence** | Edwards' rim/screen subskills; Vassell's screen navigation; Kawhi's pursuit, screen navigation and all-game defensive engagement | Leave these specific traits unchanged for now; this is not validation of their exact current magnitudes | A short dated film/assignment review or a reliable focused scouting account can resolve these. Full-season tracking is useful but not mandatory. Kawhi's 94.77 navigation/96.36 effort are especially open; his historical reputation is insufficient evidence. |

The ready proposals produce the following **canonical fixed-minutes** results. These are production-function calculations on private in-memory copies, not observed runtime player-card payloads:

| Player | Engine OVR / OFF / DEF before → proposed | Presentation crosswalk OVR / OFF / DEF before → proposed |
|---|---|---|
| Edwards | 78.3 / 78.3 / 78.5 → **77.9 / 78.3 / 76.0** | 93.8 / 93.8 / 94.0 → **93.5 / 93.8 / 92.2** |
| Vassell | 67.5 / 62.4 / 74.7 → **67.2 / 63.2 / 71.2** | 86.0 / 81.9 / 91.3 → **85.8 / 82.6 / 88.8** |
| Duren | 67.1 / 60.6 / 73.4 → **66.3 / 60.6 / 71.2** | 85.7 / 80.5 / 90.4 → **85.0 / 80.5 / 88.8** |
| Coward | 55.5 / 55.4 / 56.6 → **56.5 / 55.4 / 60.1** | 75.5 / 75.4 / 76.6 → **76.5 / 75.4 / 80.1** |
| Kawhi | 79.3 / 73.6 / 92.0 → **78.8 / 74.6 / 88.2** | 94.5 / 90.5 / 98.2 → **94.2 / 91.2 / 97.5** |

## Baseline, dates and reproducibility

The intended game start is **2026-10-20**. Offseason episodes are eligible current-skill evidence at that date, subject to material intervening events. Episode 7 is dated 2026-08-14; episode 4, 2026-09-02; episode 6, 2026-08-19. No post-start game or injury is used to change opening ability. Availability and healthy ability remain separate.

The inspected canonical file is `data/canonical/universe_2026_27_offseason.json`, version `2026-10-30-contract-separation-v10`, talent model 2 / offense model 1, SHA-256 `ddd8e2b0bb9887105c621878cc2e411874dacde5b9cb159e3df166ba790c37fd`. It is a **mixed-date composite**: March 11 skill inputs and March 5 augmentation, a June 20 subjective league prior, preserved released traits with July 28 metadata, an October 13 roster snapshot, October 14 retained 2025–26 career totals, and later bounded alignment/calibration/profile updates. July metadata does not establish the observation date of every field. The individual lineages below identify which relevant values were preserved or later adjusted. See [source audit](IMPORTED_INPUT_SOURCE_AUDIT.md) and the backend's [completed input-refresh preview](../IMPORTED_RATING_REFRESH_PREVIEW_2026_11_09.md).

The backend preview rebuilt the original 526-player reference population and refreshed 515 matched full-season box-stat rows, then ran the existing import stages. All 15 final numerical traits and all engine/presentation summary fields remained unchanged for these five. Raw input/inference changes exist, but preservation and existing later evidence passes retain final values. That result supports **neither** automatic buffs nor automatic downgrades. Missing touches, IQ, play-type samples and defensive tracking cannot be manufactured from box totals. This review read the completed preview and its JSON outputs; it did not rerun or duplicate that pipeline.

Canonical source-minute projections are Edwards 35.5, Vassell 30.6, Duren 27.8, Coward 26.1 and Kawhi 28.0. These minutes, roster, health, offense-profile anchors and all unaffected traits were held fixed during recomputation. No save was created or loaded, and no rotation projection or `player_card` action was dispatched. The presentation mapping uses the verified `player_display_attribute_summary()` transform; frontend headline card fields in the previously traced path are `ratings.overall`, `ratings.offense`, `ratings.defense`, but **none of these five has a new observed runtime-card response in this review**. Do not relabel this canonical crosswalk as one.

Artifacts: [exact baseline traits, provenance and peer snapshots](probe_artifacts/five_player_calibration_baseline_20261109.json), [recomputation runner](probe_artifacts/five_player_calibration_recompute_20261109.py), [complete before/after summaries and feature differences](probe_artifacts/five_player_calibration_recompute_20261109.json), and [decisive local cue checks](probe_artifacts/decisive_cue_checks_20261109.txt). The recomputation artifact records identical canonical-file hashes before/after. All writes for this review are inside the research directory.

## Current exact underlying traits

All numbers below are current canonical trait values, not presentation ratings. Stable IDs are `player_min-anthony-edwards`, `player_sas-devin-vassell`, `player_det-jalen-duren`, `player_mem-cedric-coward`, and `player_tor-kawhi-leonard`. Team codes identify the current canonical records and do not independently verify transaction history.

| Trait | Edwards | Vassell | Duren | Coward | Kawhi |
|---|---:|---:|---:|---:|---:|
| shooting_range | 84.77 | 79.27 | 55.44 | 58.40 | 80.25 |
| release_speed | 90.81 | 82.77 | 49.88 | 57.24 | 84.45 |
| shot_versatility | 63.20 | 48.36 | 48.58 | 49.48 | 63.89 |
| rim_pressure | 87.24 | 55.56 | 61.24 | 54.20 | 72.76 |
| handle_pressure | 78.98 | 60.60 | 55.42 | 54.96 | 74.44 |
| passing_reads | 73.05 | 62.97 | 60.52 | 58.83 | 73.84 |
| foot_speed_lateral_agility | 87.73 | 77.94 | 67.14 | 62.04 | 88.02 |
| stamina_cardio | 64.70 | 58.72 | 59.41 | 44.06 | 55.04 |
| defensive_effort | 83.89 | 81.80 | 71.96 | 58.99 | 96.36 |
| scheme_iq | 74.43 | 69.02 | 64.71 | 53.25 | 87.62 |
| rim_deterrence | 74.53 | 68.94 | 98.99 | 54.89 | 89.25 |
| screen_navigation | 81.21 | 79.03 | 58.02 | 59.42 | 94.77 |
| offensive_rebounding | 61.22 | 52.63 | 99.40 | 60.19 | 69.62 |
| portability | 83.87 | 84.98 | 68.04 | 53.93 | 92.07 |
| playoff_translation | 74.45 | 64.04 | 61.63 | 54.44 | 83.72 |

## What these traits actually do

The current code labels are imperfect measurement descriptions. In [traits.py](../../src/nba_gm_data/traits.py), effort is inferred from deflections, steal percentage, defensive impact and role; lateral agility and screen navigation use overlapping event/impact/versatility proxies. They are not direct speed, screen-traversal or continuous-effort measurements. Their confidence fields can be raised by subjective-prior calibration, so `.74` is not an empirical 74% certainty.

`rim_deterrence` is inferred from cohort percentiles: **55% block rate, 24% height, 15% CraftedDPM and 6% DARKO**, with a rim-protector role bonus of 16 when block/height percentile reaches 82, otherwise 6. It is intended as interior deterrence, rather than overall defense. Source `BLKpct` lacks a retained exact provider query/cutoff. A block total is relevant counterevidence but cannot alone reproduce the opponent-shot denominator or establish deterrence.

The June prior then quantile-maps CSV player ratings into the engine distribution, blends them, and applies composite OFF/DEF/REB/OVR nudges. A CSV 65 therefore can map to a 100 rim target; neither number is an observed deterrence percentage. Composite nudges can also alter traits outside the intuitively intended category. For example REB nudges include rim deterrence. Preservation later restores released values, which can differ slightly from the calibration stage's `final_value`. Coward subsequently receives roster alignment from later NBA-season evidence.

In [save.py](../../src/nba_gm_data/save.py), engine DEF is the mean of effort, scheme IQ, screen navigation and rim deterrence. Lateral agility does **not** directly enter that headline DEF mean; it does enter athleticism, block/steal summaries and game features. Rim deterrence contributes **18%** to the rebounding summary. These formulas mean a lower rim trait also lowers rebounding and OVR despite unchanged offensive boards. OFF follows [offense.py](../../src/nba_gm_data/offense.py), with shooting/creation and size/interior facets plus frozen, season-weighted evidence anchors. OFF and DEF are constructed differently; their difference is not a measured offensive-versus-defensive impact statistic and should not be forced to zero.

[sim.py](../../src/nba_gm_data/sim.py) uses `0.42×effort + 0.36×lateral + 0.22×navigation` as defensive activity. Its rim feature is `clamp(rim + 0.18×max(0,rim−68)^1.18,1,99)`. High raw values saturate: Duren 98.99 and the 92.99 sensitivity both yield **99**. The feature affects interior suppression, blocks, rebounds, matchup/strength calculations and the defensive-anchor score (45% rim, 30% activity, 15% impact, 10% integrity). Spatial profiles also consume traits. These are implemented effects, not merely player-card labels.

AI implications are broader than a displayed rating. `roster_cut_score()` in `save.py` includes `0.72×engine OVR`; retention scoring also consumes OVR. Simulated creator/anchor strength uses feature values, and the impact composite can slightly alter projected usage even when only defense changes. The measurements below hold salaries, ages, minutes and team composition fixed; they do not assert a transaction, rotation change or win-total result.

## Anthony Edwards

**Evidence checked.** Episode 7 (2026-08-14), [02:03:14–02:03:38](https://youtu.be/Ckufse6eWsM?t=7394), says meaningful playmaking progression has been limited and asks whether Edwards can become a clear positive defender; the speaker says the hoped-for Wade-like defensive impact has not appeared. This is criticism of current defensive impact, not a request to avoid a defense buff. At [02:06:36–02:07:13](https://youtu.be/Ckufse6eWsM?t=7596), another passage recognizes improved finishing/intermediate scoring and says an injury affected his latest playoffs; do not use that postseason as a clean healthy-ability downgrade. Athletic scoring and defense potential are counterevidence to indiscriminate tool reductions. Locally numbered/unidentified turns are used; no persistent speaker identity is inferred.

Independent reporting dated February 27, 2026 also describes defensive relaxation, supporting a consistency concern rather than a specific rim downgrade. [NBA/The Athletic report](https://www.nba.com/news/the-athletic-anthony-edwards-owns-crunch-time-for-wolves).

**Lineage.** The March input labels his defensive role `Hidden`, with 2.3 deflections, 1.2 STL%, 1.9 BLK% and positive CraftedDPM. The effort proxy before the league prior was 49.08; calibration made it 83.98 and preservation retains 83.89. Rim proxy 57.94 became 73.08, with released/preserved 74.53. Navigation 53.79 became 81.30, preserved 81.21. Neither the low proxy nor high calibrated value independently proves skill; the large prior-induced rise makes current expert disagreement worth acting on. Later final box totals show 61 games versus the input's 52 but do not measure engagement. The backend box refresh leaves all current values unchanged.

**Small comparison group, current underlying traits:**

| Player | Effort / lateral / navigation / rim / scheme | Engine DEF; presentation DEF |
|---|---|---|
| Edwards | 83.89 / 87.73 / 81.21 / 74.53 / 74.43 | 78.5; 94.0 |
| Derrick White | 85.56 / 83.70 / 83.29 / 58.00 / 79.20 | 76.5; 92.5 |
| Desmond Bane | 83.75 / 79.54 / 79.95 / 48.00 / 80.69 | 73.1; 90.2 |
| Jaylen Brown | 81.97 / 84.22 / 76.65 / 70.85 / 73.74 | 75.8; 92.1 |

The current profile gives Edwards a higher headline DEF than all three, helped by unusually high guard rim deterrence. Peer ratings do not prove these players' true order. They show what the proposed magnitude means: effort **73.89** places sustained activity below these established two-way comparables while retaining Edwards' superior lateral tools. It does not claim he cannot defend hard assignments in bursts.

**Recommendation:** effort −10 only; no offensive change, and no simultaneous screen/rim reduction from a generic consistency critique. Confidence medium; a plausible scouting band is −6 to −12, with −10 the preferred explicit candidate. This changes engine DEF 78.5→76.0 and presentation DEF 94.0→92.2, still slightly above Brown and below White. That residual ordering is a property of the other inputs, not proof of remaining accuracy; rim 74.53 and navigation 81.21 remain specific review questions.

**Measured effect:** defensive activity 84.683→80.483; anchor 76.544→75.209; engine block 82.0→78.7 and steal 81.8→79.3 despite unchanged rim/navigation traits. OFF stays 78.3. Impact falls 0.506 and projected scoring usage falls 0.060, an unintended small offensive-opportunity effect. Roster-cut score falls 0.288. This is a consistency correction, not a health penalty or scoring downgrade. Source-refresh dependency: preserve/rebase this manual judgment once if a later version actually recalculates effort; no automatic extra delta follows from 52→61 GP.

## Devin Vassell

**Identity and evidence checked.** The user confirmed `“Devin Vel” = Devin Vassell` on 2026-11-05, HRQ-E7-DV-001; the caption spelling is retained as an alias. Episode 7 (2026-08-14), [00:22:25–00:23:52](https://youtu.be/Ckufse6eWsM?t=1345), praises catch, pull-up, movement and difficult-shot shooting, plus size and defensive plays. The counterturn at [00:23:53–00:24:30](https://youtu.be/Ckufse6eWsM?t=1433) agrees on difficult releases/contested jumpers but calls defense only a slight positive and says occasional playoff blocks are not consistent high-impact off-ball defense. Both prefer him to Powell while citing offensive limitations. The positive turn calls him a real defensive plus, so the disagreement is preserved; the source does not establish that he is a negative defender. This specific disagreement is usable scouting evidence without requiring a new tracking campaign.

**Lineage.** The March role is also `Hidden`. Current effort 81.80, navigation 79.03 and rim 68.94 are preserved calibrated values; pre-prior proxies were 67.58, 63.23 and 56.26. Shot versatility 43.65 became 48.36. The versatility formula partly rewards availability/breadth of play-type fields rather than directly measuring contested shotmaking. This supports a small scouting correction to its current magnitude without interpreting the current 48.36 as an observed shooting percentile. Final retained totals show 67 games, 166/432 threes (38.4%) and 25 blocks; they support shooting and some defensive events, not elite help defense or a precise navigation score. The unchanged pipeline's measured box refresh changes none of the final traits.

| Current peer | Versatility / range / release | Effort / rim / navigation | Engine OFF / DEF; presentation OFF / DEF |
|---|---|---|---|
| Vassell | 48.36 / 79.27 / 82.77 | 81.80 / 68.94 / 79.03 | 62.4 / 74.7; 81.9 / 91.3 |
| Bane | 54.93 / 74.25 / 77.67 | 83.75 / 48.00 / 79.95 | 68.3 / 73.1; 86.6 / 90.2 |
| White | 50.00 / 70.00 / 76.00 | 85.56 / 58.00 / 83.29 | 64.1 / 76.5; 83.3 / 92.5 |
| Brown | 62.10 / 75.34 / 83.54 | 81.97 / 70.85 / 76.65 | 72.3 / 75.8; 89.6 / 92.1 |

**Recommendation:** versatility +4, effort −6, rim −8. Versatility 52.36 lands between White and Bane while leaving Vassell's handle/rim pressure well below lead-creator levels. Effort 75.80 and rim 60.94 reduce the “high-impact helper” implication while retaining size, on-ball tools and a modest positive defensive profile. Navigation stays 79.03 because the source does not isolate that subskill. The peer values locate the scale; they are not independent proof that 52.36/60.94 are correct. Preferred bands: versatility +2 to +6, effort −4 to −8, rim −5 to −10. Exact candidate above is a middle judgment, not precision claimed by the source.

**Actual recomputation resolves the old +1.5 question.** Versatility +1.5 alone is not literally ineffective: engine OFF 62.4→62.7, presentation OFF 81.9→82.2, scoring usage +0.630. It is simply a smaller correction than the difficult-shot account supports. +4 alone yields engine OFF 63.2 and presentation OFF 82.6, with scoring usage +1.302. Adding the defensive corrections gives **67.2 / 63.2 / 71.2** engine and **85.8 / 82.6 / 88.8** presentation. Overall declines despite improved shooting; do not describe this as an OVR buff.

**Game/AI and spillovers:** activity falls 2.520, rim feature 69.107→60.940, anchor 70.541→65.980, while primary-creator score rises 0.583. Engine rebounding falls 56.5→55.1 and block 76.2→71.6 despite unchanged OREB. Shot versatility also changes modeled post creation (+0.540), assisted finishing (+0.095), shot diet and midrange/three-point spatial efficiency; it is not an isolated pull-up switch. No season outcome was simulated. Refresh dependency: the proposed shooting correction is about shot repertoire; the defensive correction is about consistency. Rebase either if later play-type or defensive evidence actually supersedes it, not simply because GP changes.

## Jalen Duren

**Evidence checked.** Episode 4 (2026-09-02), [00:32:03–00:32:29](https://youtu.be/CbartUy6cMY?t=1923), calls Duren an improved, pretty good defender and rim protector. At [00:36:24–00:36:46](https://youtu.be/CbartUy6cMY?t=2184), another turn also credits defensive improvement but emphasizes extraordinary rebounding. Offensive playoff limitations in [00:30–00:36](https://youtu.be/CbartUy6cMY?t=1800) concern crowded rolls, physical finishing, touch and confidence; they are **not** used as evidence against rim defense. The same episode treats Gobert as an elite rim anchor in [00:51:38–00:59:07](https://youtu.be/CbartUy6cMY?t=3098), providing a qualitative tier comparison rather than a rank-to-trait conversion.

**Independent counterevidence:** NBA's 2025–26 Week 4 analysis placed Duren third among 53 qualifying rim defenders; this is strong early-season evidence. [NBA Week 4](https://www.nba.com/news/power-rankings-2025-26-week-4). A separate film analysis dated 2025-12-03 praises Duren's communication, pick-and-roll activity and improved awareness, while noting closeout/transition lapses and a continuing gap from elite switching. Its statistical window is through December 1, not a complete season. [Brennan Sims' film analysis](https://www.detroitbadboys.com/detroit-pistons-analysis/48437/jalen-duren-dictates-dominant-detroit-pistons-defense). These support positive defense and caution against a large downgrade. They do not independently measure a 98.99 full-season trait.

**Meaning and full lineage.** March input: GP50/MP1383, BLK 0.8, `BLKpct=4.1`, height 82.25 inches, defensive role `Rim Protector`. The rim formula uses percentile components **87.3518 / 83.4000 / 59.7303 / 81.9066** for block%, height, CraftedDPM and DARKO. The weighted mean plus the 16-point role bonus yields **97.93** before the subjective league prior. Thus this is not chiefly an OREB mixup or a one-player override. The June CSV rim value **65** quantile-maps to **100**, and blending/composite nudges yield **98.64**; preservation retains released **98.99**. Current OREB 99.40 is a separate trait. The role/height/block proxy and percentile mapping are substantial structural contributors. The source metadata do not retain the exact BLK% denominator/query window; box blocks alone cannot establish it as erroneous.

| Current center peer | Rim trait → sim rim feature | Effort / navigation / scheme | Engine DEF; presentation DEF |
|---|---|---|---|
| Duren | 98.99 → 99.000 | 71.96 / 58.02 / 64.71 | 73.4; 90.4 |
| Zubac | 98.58 → 99.000 | 79.92 / 61.68 / 77.54 | 79.4; 94.6 |
| Kessler | 97.43 → 99.000 | 85.78 / 68.12 / 74.67 | 81.5; 95.5 |
| Gobert | 99.01 → 99.000 | 89.84 / 76.62 / 87.25 | 88.2; 97.5 |
| Chet Holmgren | 98.59 → 99.000 | 91.04 / 77.68 / 80.77 | 87.0; 97.1 |

Peers expose **saturation**, not correctness. Duren already has weaker general-defense inputs than these anchors, but its rim channel gives him the same ceiling output. The episode's “pretty good, improving” account plus the early strong results supports a high-but-not-identical anchor channel. **Recommend rim 90.00 (−8.99)**, with a provisional band 88–93. Prefer 90 over a token reduction: the explicit −6 sensitivity changes raw DEF but leaves the sim rim feature at **99**. At 90 it remains **96.908**, only 2.092 below the ceiling. That preserves strong regular-season rim value while introducing a limited separation from elite rim specialists. This is a scout calibration judgment with low–medium confidence, not a statistically estimated ranking from the early defender table.

**Effects:** engine DEF 73.4→71.2, presentation DEF 90.4→88.8, OVR 67.1→66.3. OFF remains 60.6 and OREB remains 99.40. Engine rebounding nevertheless falls **92.9→91.3**, block 79.4→76.4, impact 71.131→69.768 and anchor 80.367→79.221; projected usage falls 0.218. These spillovers mean the proposed reduction also slightly lowers non-rim opportunity/value. If the coordinator rejects those coupled effects, defer this trait edit and review the model channel separately; do not compensate by inventing an OREB/ability buff. Source-refresh dependency: full-season box refresh does not alter the unsupported BLK%/tracking field or current preserved traits. It cannot validate 98.99, nor independently derive 90. Leave the other defensive/mobility and offensive traits unchanged.

## Cedric Coward

**Evidence checked.** Episode 7 (2026-08-14), [00:10:23–00:10:48](https://youtu.be/Ckufse6eWsM?t=623), describes polished connective skills and prefers his shooting/efficiency/defense to Edgecombe's current versions while giving Edgecombe higher upside. At [00:11:58–00:12:39](https://youtu.be/Ckufse6eWsM?t=718), the second turn praises size/frame, defensive versatility, rebounding, solid passing and off-ball feel. This is current-skill evidence plus explicit ceiling disagreement, not a measured top-ten ability grade. Episode 3 repeats the general case but is the same commentary lineage and adds no independent corroboration.

Retained independent evidence in the [source diagnosis](RESEARCH_NOTEBOOK.md#cedric-coward-source-window-root-cause-not-a-trait-edit) includes a dated January 21, 2026 Ringer scouting account of weakside help, body flexibility, movement and a shallow handle. Its reported defended-rim differential lacks a reproduced denominator and is not treated as a full-season metric. The official All-Rookie selection is recognition, not proof of any subskill. Full-season retained stats show 62 GP, 2.76 APG, 33.8% 3P; the March row has 49 GP, 2.9 APG, missing touches and BBallIQ. The later assist rate does not by itself support raising passing reads.

**Lineage matters more than “stale data.”** Current effort **58.99** comes from a **71.95** event/role proxy → **56.09** after the low June prior → released **56.11** → **+2.88** NBA alignment. Scheme **53.25** follows 57.87→49.45→49.47→+3.78. Rim **54.89** follows 39.99→50.06→50.19→+4.70. Passing **58.83** follows 64.24→53.32→53.33→+5.50. Alignment used later 1,599.6-minute NBA evidence and moves these traits upward; it does not cause the low prior. Recorded `.58` confidence is an alignment processing cap, not a measured uncertainty interval. Missing touches/IQ affect proxy construction, but do not logically imply a positive correction of a known size.

| Current young wing/guard peer | Effort / lateral / navigation / rim / scheme | Passing | Engine DEF; presentation DEF |
|---|---|---:|---|
| Coward | 58.99 / 62.04 / 59.42 / 54.89 / 53.25 | 58.83 | 56.6; 76.6 |
| Edgecombe | 68.87 / 71.33 / 65.70 / 58.60 / 54.58 | 67.43 | 61.9; 81.5 |
| Knueppel | 59.38 / 63.96 / 60.12 / 57.04 / 57.16 | 62.08 | 58.4; 78.4 |
| Wells | 51.56 / 53.86 / 50.37 / 47.28 / 45.32 | 49.67 | 48.6; 68.6 |

**Recommendation:** replace the passing-only +1.5 proposal with effort +5, rim +6, scheme +3. These encode activity, help positioning and connective awareness supported by the expert descriptions. They place effort below Edgecombe, rim slightly above these rookie peers, and scheme between Edgecombe and Knueppel. That balances the positive Coward judgment with higher Edgecombe athletic upside and uncertainty; the peers locate scale without proving the judgment. Leave lateral/navigation unchanged because the current evidence is broader than a movement-specific comparative claim. Leave shooting/handle/passing unchanged because the finishing/shooting praise coexists with 33.8% threes, limited handle and an already useful connector projection. Preferred bands: effort +3 to +7, rim +4 to +8, scheme +2 to +4.

**Effects and refresh dependency:** engine 55.5/55.4/56.6→56.5/55.4/60.1; presentation 75.5/75.4/76.6→76.5/75.4/80.1. Activity +2.100, rim feature +6, anchor +3.536. Engine rebound +1.0, block +3.7, steal +2.0. Although the passing **trait** is unchanged, scheme IQ raises the sim **passing feature 56.04→57.54** and primary-creator score +0.465. OFF summary stays 55.4. This is an actual cross-category effect to accept deliberately. The old passing +1.5 sensitivity would have produced only engine OFF +0.4 and presentation OFF +0.4; it has no privileged evidentiary status. The new defense proposal is an explicit scout override, not a claim that stale rows mechanically caused under-rating. After any approved input refresh, compare the new baseline and apply/rebase this overlay once; the completed dry run currently changes no final traits, so waiting for unsupported full-season tracking is not required to assess this judgment.

## Kawhi Leonard

**Source correction and evidence checked.** The prior extraction/synthesis over-attributed a defensive claim. In the raw episode 6 transcript, **01:31:17–01:31:24 “solid passer / solid defender” describes Durant**, continuing the Durant segment. It is not a Kawhi defensive evaluation. Do not use it as evidence for either Kawhi defensive excellence or decline. This correction is marked in the extraction and supersedes the older five-player synthesis.

The actual Kawhi case (2026-08-19), [01:32:24–01:33:47](https://youtu.be/HM0tNscRN4k?t=5544), emphasizes physical scoring inside the arc, efficient shotmaking, free throws and higher three-point volume. At [01:33:50–01:34:20](https://youtu.be/HM0tNscRN4k?t=5630), the speaker explicitly prefers his ball protection to Brown/Durant, acknowledges passing limits and praises handle plus on/off-ball scoring. Availability risk is discussed at [01:31:27–01:32:24](https://youtu.be/HM0tNscRN4k?t=5487); that risk does not justify reducing healthy subskills. The #1 rank and historical defensive reputation do not establish current rim deterrence or navigation.

Retained 2025–26 ESPN totals describe the **seasonal output**, and these same-source totals also feed current offensive priors: 65 GP, 27.89 PPG, 172/445 threes (38.7%), 371/416 FT (89.2%), 2.05 turnovers, 1.88 steals and 0.42 blocks per game. They support efficient high-volume scoring and active hands, but low blocks alone do not prove poor rim deterrence. Current offense profiles already use weighted 2024–25/2025–26 evidence (three-volume weight .98, two-point weight .85, play-type weight .35); a second blanket scoring-stat buff would double count much of that evidence.

**Lineage:** effort's pre-prior proxy was already **100**, reflecting steal/deflection/role information; the prior leaves a current 96.36. Navigation 92.76 becomes 94.77 from overlapping event/role proxies. Rim is different: pre-prior **61.57** → calibrated **89.04** → preserved **89.25**, because CSV rim 70 maps to a **100** engine target. This does not independently establish center-like rim influence. The raw rim percentile components are block 58.70, height 44.80, DPM 83.62 and DARKO 99.81; broad impact contributes despite rim being a distinct channel. Current shooting versatility 63.89 and handle 74.44 are preserved, after the subjective prior and composite OFF/OVR nudges. Neither high recorded confidence nor healthy status settles magnitude.

| Current wing/forward peer | Versatility / handle / rim pressure | Effort / navigation / rim | Engine OFF / DEF; presentation OFF / DEF |
|---|---|---|---|
| Kawhi | 63.89 / 74.44 / 72.76 | 96.36 / 94.77 / 89.25 | 73.6 / 92.0; 90.5 / 98.2 |
| Durant | 68.28 / 78.60 / 67.43 | 66.00 / 56.00 / 62.00 | 75.2 / 65.0; 91.6 / 84.0 |
| Brown | 62.10 / 71.85 / 71.71 | 81.97 / 76.65 / 70.85 | 72.3 / 75.8; 89.6 / 92.1 |
| McDaniels | 44.39 / 56.00 / 53.18 | 93.01 / 86.88 / 80.54 | 54.1 / 83.6; 74.1 / 96.1 |

This comparison exposes a very strong defensive shape relative to contemporary wings, but does not prove that Durant's low defensive values or McDaniels' high ones are accurate. It also exposes an offensive shape only modestly above Brown and below Durant despite the episode's specific physical/ball-security case. The remedy should concern those components, not force Kawhi's OFF to equal or exceed DEF or force his podcast rank into OVR.

**Recommendation:** versatility +4 and handle +2; keep range/release/rim pressure and passing unchanged because observed offense profiles already reflect much of the scoring evidence. The targets 67.89 and 76.44 move repertoire/pressure control toward Durant's scale without automatically copying it. Separately recommend rim −15→74.25 as a provisional reduction of a largely prior-induced high rim channel. It retains substantial wing help defense, above Brown's current 70.85 and below McDaniels' 80.54. This is deliberately smaller than reversing the entire 27.68-point increase from the original proxy; it recognizes length, anticipation and disruptive hands as counterevidence. Confidence is low–medium on this exact rim target; plausible scouting band 70–80, not a precise measured rate. Effort and navigation are left unchanged pending a specific present-day pursuit/screen/assignment assessment. The source correction removes the justification previously offered for simply retaining the entire defensive profile.

**Measured effects warrant separate approval of offense and rim.** Offense-only: engine OVR 79.3→79.9, OFF 73.6→74.6, DEF remains 92.0; presentation 94.5/90.5/98.2→94.9/91.2/98.2. Rim-only: engine DEF 92.0→88.2 and presentation DEF 98.2→97.5, but sim rim influence **95.881→75.815**, and anchor **88.583→79.385**. The small displayed DEF change therefore hides a **20.066-point** rim-feature and **9.198-point** anchor drop. It also lowers engine rebounding 70.8→68.1 and block 91.2→86.2. The raw block-generation formula adds an extra term above rim feature 88; current Kawhi triggers that term, while this candidate does not. These are consequential changes before team normalization, not a forecast of final blocks per game. Do not call this an inconsequential −0.7 display adjustment.

Combined: engine **78.8/74.6/88.2**, presentation **94.2/91.2/97.5**; primary creator +0.778, anchor −9.139, usage +1.524, scoring usage +1.313, roster-cut score −0.360. Defensive activity is unchanged; the proposal does not reduce elite hands/effort or claim an injury penalty. The summary still strongly favors defense because effort/navigation/scheme remain high and presentation compresses the top end. That remaining balance is an open component-calibration question, not resolved by the overall rank or this modest offensive increase. Refresh dependency: retained final totals already influence offense profiles, and box refresh alone changes no final traits. Reconcile any future recalibration against both frozen anchors and these scouting deltas; never apply them twice.

## Review limits and disposition

All decisive passages above were checked against retained local VTT/supplied transcripts, not merely prior summaries. The full supplied episode spans were already reviewed; this task did not restart extraction. Speaker identity remains unidentified/local-turn based. Repeated host opinions are not counted as independent sources. Targeted external reading checked Edwards consistency and Duren's positive defensive countercase; no new caption fetch or rate-limited endpoint retry was made. The current Clippers PDF returned post-start game notes and was not used as pre-start evidence. No new medical, transaction or contract conclusion is made.

The exact recomputation artifact includes every changed summary and full spatial feature field, including unintended changes omitted from compact tables. No save/action probe, game simulation, server restart, dependency install or production test ran. The only calculations were canonical summaries/features and read-only scoring functions on private copies. Production code, canonical/imported files, contracts, playable saves, UI, prospect growth and rating formulas were not changed.

Coordinator decisions can approve individual subparts rather than entire bundles. A later implementation should record these as source-backed calibration decisions with evidence dates and preserve career histories; that implementation and its required regression checks are outside this research delivery.
