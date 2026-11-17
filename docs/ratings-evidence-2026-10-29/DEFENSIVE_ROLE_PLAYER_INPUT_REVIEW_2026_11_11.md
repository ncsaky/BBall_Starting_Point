# Defensive role / player input review — 2026-11-11

**Delivered research sheet for the backend prototype. No production changes.** October immediately before the regular season is the target; retained pre-start offseason assessments are eligible evidence. Opening-week results remain separately dated. This sheet reuses existing extractions rather than claiming a new audiovisual or full-transcript review.

## Decision table first

These are **reviewable calibration candidates**, not measured coefficients, automatic approval or a demand to reproduce a podcast ranking. Decimal precision in current inputs is bookkeeping; proposed ranges express uncertainty. Confidence concerns basketball support, distinct from stored pipeline confidence.

| Player | Proposed underlying input | Reason and counterevidence | Confidence / action |
|---|---|---|---|
| Wembanyama | Effort **82 → 88**, defensible working band **86–90**. Keep rim100, lateral70, navigation86.62 and scheme82 for now. | Repeated ground-coverage/activity evidence is stronger than an effort grade below White/Barnes/Gobert/Mobley implies. Existing manual effort82 was not a measured hustle rate. Space/switch limitations remain; the award does not warrant every-tool boosts. | Moderate direction, low exact magnitude. Candidate for isolated backend comparison. Do not simultaneously restore all pre-override priors. |
| White | Navigation **83.29 → 87**, band **85–89**; scheme **79.20 → 84**, band **82–86**. Keep rim58, lateral83.70, effort85.56. | Retained evidence emphasizes screen work, positioning, anticipation and guard help. Navigation should sit above Castle78.38; scheme moves toward, still below, Gobert87.25/Mobley90.20. Guard blocks do not make him a center anchor. Direct screen-frequency/outcome measurements absent. | Moderate profile, moderate-low numbers. Keep the two subparts separable. |
| Castle | Effort **79.44 → 85.5**, band **83–87**; rim **76.96 → 62**, band **58–64**. Hold lateral77.11/navigation78.38/scheme73.41. | POA physicality/engagement is corroborated; secondary rim/help is explicitly weaker. Effort approaches White85.56 without declaring superior all-role defense. Rim band spans White58 and reviewed Vassell60.94, far below true anchors. Fouls and team help qualify the containment evidence. | Moderate direction, moderate-low magnitude. Paired profile candidate supersedes the prior deferred Castle numbers for review, not implementation. |
| Gobert | **Hold** all reviewed traits; rim99.01. | Strong anchor evidence; block volume alone understates positioning/deterrence. No reason to cut him solely to separate Wembanyama. | Moderate-high hold; no current deployment shares acquired. |
| Barnes | **Hold** all reviewed traits; rim90.32. Flag rim magnitude and scheme75.13 for later discrimination. | Switch/help/hands evidence supports a strong broad profile. A 90.32 anchor-like rim number is not independently verified, but neither a forced cut nor an IQ boost is established. | Moderate hold; exact rim value unresolved. |
| Mobley | **Hold**; rim97.51, lateral85.16, effort90.09. | Elite switch-plus-rim evidence supports dual big jobs. Headline DEF above Wembanyama does not itself prove an input error. | Moderate hold. No ranking repair. |
| Curry / Luka | **Hold**. Curry's Hidden label and stamina92 are not defensive ability observations. Luka's manual lateral32/effort42/nav36/rim42 remain. | Offensive workload, steals and generic impact must not turn into automatic defense. Existing evidence does not independently establish more precise defensive targets. | Moderate hold; cross-role counterfactuals low confidence. |
| Six inferred rim100 centers | **No batch cut.** Stewart and Huff have substantial counterevidence to a reflex downgrade; Richards/Capela/Lopez/Turner lack enough current rim-specific evidence here to assign replacement numbers. | Equal endpoints have different inference/calibration lineages. Full findings below. | All six endpoints need validation; none is a new approved target. |

Pure current-function sensitivity, with every other trait fixed: Wembanyama DEF **86.818 → 88.330**; White **73.835 → 74.324**; Castle **78.762 → 73.348**. Castle's stronger activity and lower aggregate DEF are intentional consequences of the paired role profile, not a calculation failure. White's scheme proposal affects spatial/help and IQ consumers, not the present scalar DEF formula. OFF/OVR and economic/game effects were **not** recomputed; defensive-only traits imply no direct OFF change, while scheme also has nondefensive consumers. No prediction of exact OVR is made. See the private component calculation artifact. The candidate Wembanyama value still does not force him above every defender.

## Frozen baseline and scope

Captured version **2026-11-10-five-player-scouting-v11**, canonical anchor July28; canonical SHA-256 **dd993731ab5411066ea1f8d7e7053e9718deefa08758f5f51a274a3aef1a8e31**. Full raw rows, player IDs/ESPN IDs, trait records/components/notes, final-season ESPN comparison rows, overrides and hashes are retained in [frozen input snapshot](probe_artifacts/defensive_role_input_snapshot_20261111.json). This is a lightweight research capture, not a save. The version label alone is insufficient: earlier Wembanyama99 captures used the same v11 label with a different hash.

Current backend semantics are documented in [shared-scale verification](../DEFENSIVE_SCALE_COMPARISON_2026_11_10.md): direct bounded model grades, activity=.42 effort+.36 lateral+.22 navigation; DEF=.60 activity+.40 effective rim. Rim includes physical tools already; no second defensive height bonus is justified. Scheme has spatial/IQ consumers. A monotone response cannot separate identical raw100 values. OVR retains position/role/minutes context. No formula or potential/growth change is proposed here.

The backend's recorded actual fresh cards are Wembanyama81.8/79.1/86.8, Gobert70.3/57.5/86.7, White68.2/64.1/73.8, Castle67.6/63.9/78.8, Barnes74.0/66.9/88.5 and Mobley78.2/65.7/91.6 (OVR/OFF/DEF). These are inherited November10 action captures, **not fresh probes by this task**. The old November2 inflated display values in earlier dossiers are historical.

## Current raw inputs

E=effort, L=lateral agility, N=screen navigation, R=rim deterrence, Q=scheme IQ, S=stamina. All are current raw 0–100 model inputs, not percentiles, observed job shares or defensive impact. Stable team-prefixed IDs in the frozen artifact are identity keys, not proof of historical team membership.

| Player | E | L | N | R | Q | S |
|---|---:|---:|---:|---:|---:|---:|
| Victor Wembanyama | 82.00 | 70.00 | 86.62 | 100.00 | 82.00 | 59.87 |
| Rudy Gobert | 89.84 | 66.97 | 76.62 | 99.01 | 87.25 | 60.03 |
| Derrick White | 85.56 | 83.70 | 83.29 | 58.00 | 79.20 | 61.69 |
| Stephon Castle | 79.44 | 77.11 | 78.38 | 76.96 | 73.41 | 54.92 |
| Scottie Barnes | 86.53 | 85.00 | 81.09 | 90.32 | 75.13 | 61.61 |
| Evan Mobley | 90.09 | 85.16 | 85.25 | 97.51 | 90.20 | 61.15 |
| Stephen Curry | 68.47 | 67.83 | 66.22 | 36.09 | 88.00 | 92.00 |
| Luka Dončić | 42.00 | 32.00 | 36.00 | 42.00 | 70.00 | 54.68 |
| Nick Richards | 60.26 | 40.88 | 49.73 | 100.00 | 59.81 | 35.36 |
| Isaiah Stewart | 72.82 | 51.62 | 59.16 | 100.00 | 70.12 | 49.50 |
| Clint Capela | 57.29 | 48.00 | 49.70 | 100.00 | 63.96 | 39.82 |
| Jay Huff | 30.98 | 28.04 | 29.48 | 100.00 | 56.62 | 46.75 |
| Brook Lopez | 56.28 | 36.86 | 37.95 | 100.00 | 53.65 | 72.28 |
| Myles Turner | 38.31 | 35.54 | 36.37 | 100.00 | 47.56 | 81.22 |

## What is observed locally, and what is inferred?

| Local source / layer | Evidence actually retained | What it does not establish |
|---|---|---|
| March11 skill input, 526 rows | GP/box rates, block/steal percentages, deflections, height, provider aggregate MatchupDifficulty/VersatilityRating, impact fields, role workbook labels; per-row March5 augmentation metadata | No opponent-ID-by-defender-ID assignment table, guarded possessions/minutes by player, screen-action responsibility or sample denominator for the aggregate matchup fields was found in the inspected artifacts. Exact strict-source as-of dates and aggregate units remain undocumented. |
| `primaryDefRole` and `roleSource=role_workbook` | Every selected row has `defRoleFeaturesUsed=0`. White and Luka are Mobile Forward; Curry Hidden; Castle Versatile Stopper; Barnes Mobile Forward; remaining selected bigs Rim Protector. | These are provider/workbook assignments carried into canonical data, not reconstructed current observed usage. Not the BBI seven-role taxonomy and not a suitability grade. |
| `augment.matchup_fg_pct` | A named scalar, source balldontlie, sampleCount1, pulled March5; e.g. Wembanyama55.161 | No defender/opponent keys, defended FGA, action context or query lineage in that object. sampleCount1 is one augmentation record, not one game. Cannot verify it as matchup defense or infer containment from it. |
| `Player Stats/player_stats.json` | CraftedNBA player-stat fetch April5, 535 rows, with request metadata and aggregate statistics | Different fetch from the March model input; not a uniform full-season October skill refresh or retained raw matchup deployment. |
| Tracking registry | `data/research/tracking_sources_2025_26.json` lists future dashboard categories and explicitly says v0 uses canonical traits/public proxies | Registry entry is not fetched tracking observations. |
| ESPN career snapshot | Retrieved October14; athlete-ID keyed, seasontype2, final 2025–26 regular-season totals | Blocks/steals/minutes are observed season output, not difficulty-adjusted matchup success, rim avoidance or screen navigation. Source shares lineage with some canonical refreshes, so it is a later comparison rather than independent validation of the entire pipeline. |
| Simulation assignment/feature outputs | Model-produced roles, features and contextual defensive outputs | Generated deployment is not observed NBA deployment. Do not feed it back as independent evidence of ability. |

Inventory finding is bounded to the inspected canonical/raw/research sources and relevant code; it is not a claim that no matchup file could exist anywhere on the computer. Provider aggregate matchup fields may incorporate tracking, but their raw assignment provenance and denominators were not retained here.

### Inference and confidence traps

Initial rim inference is .55 block-percentile + .24 height-percentile + .15 CraftedDPM-percentile + .06 DARKO-percentile, then a Rim Protector role bonus of16 when block or height percentile is at least82 (otherwise6), clamped at100. This is an effective ability proxy already containing size, role and impact. DARKO is not a pure rim measure. A role bonus and a high block percentile can erase differences before any runtime response is applied.

Effort averages deflection/steal/DPM percentiles plus a role boost. Lateral and navigation reuse almost the same event/impact/versatility inputs with different weights and role boosts. They are correlated estimates, not three independent measurements of engagement, feet and screen technique. Scheme also uses passing/BBallIQ/DPM: offensive intelligence is not proof of help execution. Stored rim confidence.82 mostly reflects populated fields; it does not certify elite endpoint accuracy. Navigation inference caps at.48 before later prior/calibration confidence handling; current .732 records should not be mistaken for newly acquired screen-tracking evidence.

Stamina is inferred from projected/prior minutes and a movement-offense role bonus. **Do not use this as an intrinsic chaser ceiling.** It would penalize a defensive specialist for offensive usage and coach opportunity. Offensive workload may affect in-game fatigue separately, but current minutes, Hidden labels, steal rates or generic impact are similarly circular substitutes for role capability. Missing or inapplicable job measurements require uncertainty, not zero skill.

Pipeline inspected: build raw inferred traits → subjective June20 full-health quantile mapping and composite nudges → preserve released returning-player values by normalized name → manual overrides → roster alignment/health and later post-alignment overrides → bounded imported-skill/rotation corrections → reviewed v11 overlay. Exact ordering is in ingest.py; per-trait metadata is authoritative about which layers affected a particular value. A rerun of the initial formula alone will not reproduce all canonical outputs.

## Selected trait lineage audit

Values below are recorded initial inference → subjective calibrated result → preserved/current result; final manual overrides are explicit. Stored confidence is an input-model annotation, not empirical reliability. No uniform retrospective full-season defense refresh is established.

| Player | Effort lineage | Rim lineage | Current E / N / R confidence |
|---|---|---|---|
| Victor Wembanyama | 82.49 → 93.59 → 82.00 → manual82.00 | 100.00 → 98.08 → 99.00 → manual100.00 | 0.76 / 0.732 / 0.9 |
| Rudy Gobert | 52.94 → 89.74 → 89.84 | 100.00 → 98.94 → 99.01 | 0.74 / 0.732 / 0.82 |
| Derrick White | 50.52 → 85.58 → 85.56 | 63.84 → 88.41 → 58.00 → manual58.00 | 0.74 / 0.732 / 0.76 |
| Stephon Castle | 71.30 → 79.47 → 79.44 | 45.64 → 77.02 → 76.96 | 0.74 / 0.732 / 0.82 |
| Scottie Barnes | 64.14 → 86.53 → 86.53 | 70.10 → 90.81 → 90.32 | 0.74 / 0.732 / 0.82 |
| Evan Mobley | 65.18 → 90.08 → 90.09 | 100.00 → 97.51 → 97.51 | 0.74 / 0.732 / 0.82 |
| Stephen Curry | 62.33 → 68.45 → 68.47 | 47.22 → 36.48 → 36.09 | 0.74 / 0.732 / 0.82 |
| Luka Dončić | 73.63 → 66.33 → 42.00 → manual42.00 | 59.51 → 53.45 → 42.00 → manual42.00 | 0.72 / 0.72 / 0.68 |

Wembanyama lateral59.69 →84.78 →manual70 contrasts with navigation60.94 →86.69 →86.62 (no manual navigation review). White navigation59.30 →83.31 →83.29 and scheme75.17 →79.22 →79.20 are prior-calibrated proxies. Castle navigation73.04 →78.41 →78.38 is distinct from his calibrated rim inflation. These paths motivate targeted review; restoring every earlier value would compound different proxies.

## Rim ceiling audit

“Preclip” reconstructs the initial weighted inputs plus role bonus **before** the 100 cap; it is a diagnostic of clipping, not a proposed skill scale. “Calibrated” is the recorded subjective-prior result where present; the next column is the preserved value. None of these six has a reviewed manual rim override in the frozen record.

| Player | Initial preclip → capped | Recorded calibrated | Preserved / current rim | Final-season GP / minutes / blocks per36 | Decision |
|---|---:|---:|---:|---:|---|
| Nick Richards | 95.33 → 95.33 | 100.0 | 100.00 / 100.00 | 48 / 700.8 / 1.64 | Endpoint not validated; replacement number unsupported. |
| Isaiah Stewart | 101.91 → 100.00 | 100.0 | 100.00 / 100.00 | 58 / 1316.6 / 2.54 | Strong rim-specific counterevidence to cut; retain pending endpoint calibration. |
| Clint Capela | 106.70 → 100.00 | Not applied/recorded | 100.00 / 100.00 | 75 / 922.5 / 2.46 | Clipping + limited role; no justified exact replacement. |
| Jay Huff | 108.51 → 100.00 | Not applied/recorded | 100.00 / 100.00 | 82 / 1722.0 / 3.20 | Strong block season; no arbitrary bench/small-sample cut. |
| Brook Lopez | 103.46 → 100.00 | Not applied/recorded | 100.00 / 100.00 | 75 / 1635.0 / 1.92 | Clipping; mobility limitations must not automatically cut rim skill. |
| Myles Turner | 103.26 → 100.00 | Not applied/recorded | 100.00 / 100.00 | 71 / 1909.9 / 2.17 | Clipping; block value remains, current all-role skill uncertain. |

**Richards:** initial95.33 becomes100 after a subjective CSV rim67 maps to target100, DEF/REB/OVR nudges and preservation. This demonstrates a transformation-driven endpoint, not a measured match to Wembanyama. The 700.8-minute season limits certainty; low minutes alone do not prove poor rim skill. No full defended-FGA/avoidance sample or substantive retained individual segment was located. A replacement such as90 or95 would be an unvalidated calibration choice; hold implementation.

**Stewart:** the raw model reaches101.91 before clipping, but this is not merely a height story. NBA analysis dated June25 reports opponents106/242 at the rim (43.8%) in 2025–26, versus148/322 (46.0%) in 2024–25. That supports genuinely exceptional contest outcomes across two seasons. The same analysis gives poorer team net results with him on and limited playoff pairing with Duren; net offense/role constraints do not refute rim defense. These are contest results, not causal shot-avoidance measures. [NBA analysis](https://cdn-uat.nba.com/news/early-player-movement-2026)

Team review supports perimeter flexibility; its within-six-foot .429 differs from rim-only .438. These definitions should not be silently merged. [Pistons review](https://www.nba.com/pistons/news/pistons-2025-26-rewind-stewart-synonymous-with-teams-blue-collar-toughness)

**Huff:** his retained final row is82 games/1722 minutes/153 blocks, not just a brief bench cameo. Pacers' May6 review independently confirms82 games and153 blocks. [Pacers review](https://www.nba.com/pacers/news/player-review-2026-jay-huff) The raw11.1 block%/height proxy can justify substantial rim skill; it cannot measure Wembanyama-equivalent deterrence, decisions, range or mobility. The very low inferred effort30.98/navigation29.48 alongside rim100 is a reason to audit job-biased inputs, not automatically raise them. No exact replacement is supported.

**Capela, Lopez, Turner:** strong block percentiles and the same role bonus generate initial106.70/103.46/103.26. Final-season samples and blocks remain nontrivial. Bench usage, age or low event/versatility proxies do not by themselves distinguish lost rim ability from restricted deployment. This pass did not acquire sufficiently specific contemporary matchup/rim tracking or independent player scouting to set replacements for either rim or low mobility/effort/navigation. **Unsupported numerical cases remain explicit holds.** No inference that all six should be below an arbitrary96 cap.

## Priority-player evidence and limitations

| Player | Retained dated passage and supported distinction | Corroboration / counterevidence | Result |
|---|---|---|---|
| Wembanyama | Sep2 centers01:35:07–01:45:37: exceptional reach, prevention and ground coverage; weaker switching in space, offensive polish/Finals discussion and growth forecast remain separate. | April20 official release supports outstanding league impact; raw deflections3.7 vs White2.2/Mobley2.0 is descriptive same-source activity support. On/off is contextual, not an isolated causal coefficient. | Effort candidate; keep lateral70 pending actual containment evidence. Navigation86.62 is already high and inferred, so no award-based navigation increase. |
| Gobert | Sep2 centers00:51:38–00:59:07: positioning, coverage and dependable anchor value, with some space/post defense; offensive/playoff limitations. | Retained final124 blocks in2378.8 minutes does not capture avoidance. Award/source context supports elite anchor, not equal POA aptitude. | Hold all raw values. Neither generic rank nor block totals warrants a cut. |
| White | Aug14 SG01:34–01:44: anticipation, positioning, screen/guard defense, help blocks and connective decisions; limited interior creation and poor shooting year are separate. | Independent recognition N2 below supports overall defense, not exact navigation87. Raw block percentile77.47 despite height17.4 illustrates special guard timing; rim58 already reflects context rather than center responsibility. | Navigation/scheme candidates; no extra height penalty or center-rim boost. |
| Castle | Aug5 PG00:18:37–00:22:05 and00:26:37–00:29:26: physical POA defense, but weaker secondary rim/help/disruption and fouls; Wembanyama/team context. | Independent game-specific report N3 below; final19 blocks/2040min (0.34/36), versus White1.34/36 and Barnes1.56/36. These support the distinction, not precise causal containment grades. Steal counts do not resolve help positioning. | Paired effort/rim candidate. No automatic agility/navigation/IQ increase; those need distinct support. |
| Barnes | Aug28 PF01:10:00–01:17:38: guards/wings POA, hands, help/rim versatility; scoring/three-point ceiling is separate. | N4 recognition; final116 blocks/2680min. Rim initial70.10 maps toward100 through the subjective prior and ends90.32. This inflation deserves scrutiny but doesn't negate real help/rim value. | Hold, with rim magnitude unresolved. Not proven a full-time center anchor or merely a helper. |
| Mobley | Aug28 PF00:57:31–01:09:58: switch-plus-rim versatility, consistency; offensive aggression/shot concerns separate. | Current lateral85.16/effort90.09/scheme90.20/rim97.51 broadly fits; no independently acquired current assignment shares. | Dual mobile/anchor suitability; no cut to manufacture a Wembanyama headline lead. |
| Curry | Aug5 PG01:11:36–01:25:46 mainly establishes offense/age/availability, not comprehensive defensive jobs. | Manual scheme88 can coexist with modest physical containment and rim36.09. Offensive movement stamina92 is not chaser ability. | Hold; do not turn Hidden into either elite low-activity skill or inability in every real job. |
| Luka | Aug5 PG01:27:17–01:37:18 contrasts offensive engine with defensive targeting. | Raw inference lateral79.16/effort73.63 was heavily driven by events/impact/versatility; manual32/42 now overrides it. Size/steals/offense are counterweights, not evidence of good screen navigation. | Hold; exact severity remains uncertain without current matchup/action data. |

All podcast descriptions above are inherited transcript-only observations by unidentified speakers. Source links and full surrounding disagreements are in [centers](EPISODE_4_CENTERS_EXTRACTION.md), [SG](SHOOTING_GUARDS_TOP_10_FULL_EXTRACTION.md), [PF](POWER_FORWARD_FULL_EXTRACTION.md) and [PG](POINT_GUARDS_FULL_EXTRACTION.md). No persistent panelist identity is assumed. Prior-season performance, pre-start assessment and ceiling forecast are distinct; no post-start box score is used to set these targets.

**N1:** April20 NBA release: Wembanyama was unanimous DPOY, averaged3.08 blocks, and San Antonio allowed10.1 fewer points/100 with him. That supports exceptional impact without proving every underlying tool or converting10.1 into a trait delta. [NBA release](https://pr.nba.com/victor-wembanyama-2025-26-kia-nba-defensive-player-of-the-year/)

**N2:** May22 team release identifies White as the lone guard on All-Defensive First Team. [Celtics release](https://www.nba.com/celtics/news/sideabar-offseason-20260522-derrick-white-named-lone-guard-on-2025-26-nba-all-defensive-first-team)

**N3:** May25 NBA report identifies Castle as primary SGA stopper, with team help and depleted opposition. [NBA Starting5](https://www.nba.com/news/starting-5-may-25-2026)

**N4:** May23 official announcement lists Gobert first team and Barnes second team. Awards are corroborative assessments, not independent measurements of each skill. [NBA announcement](https://www.nba.com/news/2025-26-all-defensive-teams-announced)

## Six nonexclusive defensive jobs

Keep these meanings distinct: **raw input** is a model estimate (some already include tools); **effective ability** combines relevant skill and physical constraints without double counting; **suitability** is ability to execute a particular job; **observed deployment** is what assignment was actually given and how often; **impact** is possession/team value in context. A usage-weighted overall may be explored later but is not a formula instruction or a substitute for the six profiles.

BBI defines roles using matchup time by opposing position/offensive role plus rim-defense involvement. Its labels describe deployment and can change with usage. POA handles smaller creators; chasers follow shooters/cutters; stoppers take wing creators; helpers rotate; mobile bigs switch/hedge; anchors protect deep/drop. Low Activity denotes reduced assignment/help burden, potentially with communication value. It is **not** a seventh elite skill. These definitions inform our job names; no BBI assignment or coefficient is imported. [BBI methodology](https://www.bball-index.com/defensive-roles/)

Use nonexclusive0–100 **suitability** anchors:0–20 clearly unsuitable for sustained NBA duty in that job;25–40 emergency/limited duty;45–60 workable with constraints;65–80 good regular execution;85–95 specialist/high-level capability;96–100 exceptional ceiling with strong job-specific evidence. These are proposed descriptive anchors, not league percentiles or new gameplay ratings. Unknown is **unknown**, not50 or0. A player can be strong in several jobs; the numbers need not sum to100.

| Job | High-grade evidence should show | Constraints / misleading proxies | Priority examples |
|---|---|---|---|
| POA | Repeated creator containment through screens/isolations, recovery, discipline and difficult guard assignments | Steals/size/effort alone; one possession or teammate help presented as solo containment | Castle stronger claim than his secondary-rim role; White strong guard comparator |
| Chaser | Screen-route recognition, attachment/recovery against movement shooting, repeated execution | Offensive movement label, minutes-based stamina, being assigned an easy stationary shooter | White candidate high suitability; Castle/Curry exact chaser bands unknown |
| Wing stopper | Creator defense across wing size/strength, lateral containment, switching and recovery | Positions guarded without difficulty/context; height alone | Barnes strong multi-job example; Castle smaller-wing scope needs matchup evidence |
| Helper | Timely tags, stunts, rotations, coverage recovery and weakside contests without excessive breakdowns | Blocks/steals alone, generic passing IQ | Wembanyama/Barnes/Mobley strong; White guard helper; Castle lower relative evidence |
| Mobile big | Switching/hedging/recovering in space while retaining usable interior responsibility | Calling every tall fast player a POA guard; double counting reach | Mobley strong; Wembanyama range plus space limitation; Gobert not automatically zero |
| Anchor big | Drop depth/timing, deterrence, contest results and volume, rim avoidance, rebounding/communication in context | Block% alone or rawrim100 as measured proof; team DRtg as personal causal effect | Wembanyama/Gobert high; Stewart/Huff need complete deterrence/usage validation |

Only selected bands are defensible here: Wembanyama anchor**95–100**, helper**90–100**; Gobert anchor**90–100**; White POA/chaser/helper broadly**80–95**; Castle POA**85–95**, helper**45–65**; Barnes wing/helper**85–95**, mobile big**70–90**; Mobley mobile/anchor**85–100**. These are low-to-moderate-confidence scouting bands, **not current observed assignments or backend inputs**. Exact other player/job cells—including Curry/Luka chaser capability—remain unknown; fabricating a complete eight-by-six numerical grid would add unsupported precision. Coverage of a guard helper is not equivalent to center anchoring, even within the same suitability band.

## Free source access and gaps ledger

| Source checked November11 | Accessible result | Season / units / confidence limit |
|---|---|---|
| Official NBA player matchup page, `Season=2025-26` | Browser fetch unavailable; public team matchup page returned only shell/navigation, no rows. No repeated endpoint hammering. | Need defender/opponent NBA IDs, matchup time/possessions and context, not shooting% alone. No full-season deployment claims made. |
| NBA defense dashboards, `<6ft` and overall, same season | Browser fetch unavailable; no rows acquired. | Rim-only vs6ft, FGM/FGA/DFG%, attempts/possessions and distance definition needed. Official article's Stewart table is usable narrower evidence. |
| BBI Defensive Roles | Public methodology read. | Definitions only, not current player assignments. |
| BBI Defensive Role Lab landing + free preview | Public text read. **Preview is2019–20**, not2025–26 observed assignments. | Landing describes multiple seasons/projections; controls are not proof of accessible player data. No current player rows/exports acquired. |
| BBI LEBRON dashboard | Public landing read; iframe links to Fanspo. | No current metric row, IDs, season filter or downloadable dataset verified in this pass. Impact metric would not by itself resolve deployment. |
| NBA primary reports N1–N4, Stewart analysis, Huff review | Narrow corroboration above, pre-start publications | Team reports/awards have selection/context limits. No inference of independent screen or matchup success rates. |

Official access distinction: the [NBA team matchup surface](https://www.nba.com/stats/team/1610612756/matchups?dir=A&sort=OFF_PLAYER_NAME) is publicly reachable, but this tool received no matchup rows. The [NBA glossary](https://www.nba.com/stats/help/glossary) was readable; the requested partial-possession definition was not located. Availability of a public page is not verified acquisition of a season-specific dataset. Raw NBA player IDs can be joined only after a future row-level acquisition; ESPN IDs alone are insufficient.

The [Role Lab preview](https://www.bball-index.com/wp-content/uploads/2026/09/drl-lite-v3-index.html) explicitly warns that its explanatory skill weights are correlational and collinear, that size penalties outside observed bodies are judgment priors, and that player-specific role weights worsened forward prediction. It distinguishes model projections from its explanatory approximation and emphasizes noisy single-season ratings. The page also contains differing envelope/buffer descriptions across sections, further reason not to transplant constants. We borrow the questions, **not its coefficients, size penalties or counterfactual grades**. Its2019–20 free scope cannot establish current deployment.

The [public landing](https://www.bball-index.com/defensive-role-lab/) advertises membership access to covered seasons,2026–27 projections and career blends. Paid access/export has **not** been verified. Free evidence suffices to proceed with bounded candidates and holds. No paid acquisition or account action is requested or required for this personal project. A month would be useful only if access is first confirmed to supply the actual missing fields: player-season IDs/team/as-of date; observed role and minutes/possession shares; opponent position/offensive-role shares; matchup difficulty and versatility definitions; ball-screen/chaser workload; rim opportunity/avoidance and defended-FGA denominators; help/passing-lane measurements; plus uncertainty/sample thresholds and historical seasons for stability. Metric availability and export formats remain unknown, rather than promised.

## Handoff and stopping point

Backend can review the three player candidates independently and compare the unchanged baselines; no automatic Wembanyama-first ordering constraint. Leave the six rim100 replacements and precise full role matrices unsupported until discriminating evidence exists. Do not use chaser stamina caps or generated deployment as fresh observations. Raw skill changes and role/overall presentation remain different decisions.

Six independent offensive subparts remain queued without alteration: Bane versatility59.93; Reaves versatility57.28; Herro rim pressure73.95; Brown reads68.74; Durant handle72.60; Garland handle78.91. Herro handling and Paolo reads remain held. Paolo defense remains unresolved; Castle's earlier deferred defense is replaced only by the candidate reasoning above. No coach/development/offense edits or new ratings formula are included.

Artifacts: frozen input snapshot; [component sensitivities](probe_artifacts/defensive_role_component_sensitivities_20261111.json); this sheet; notebook/checkpoint references. No game/save probe, market calculation, season simulation, browser performance test, server, dependency install or production write occurred. Free source failures are recorded; unavailable content was not reviewed. End-of-task hash recheck is recorded in the snapshot and does not overwrite concurrent backend work.
