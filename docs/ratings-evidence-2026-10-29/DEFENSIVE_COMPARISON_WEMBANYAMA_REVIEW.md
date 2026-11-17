# Wembanyama defensive comparison — 2026-11-10

## Findings for the backend

**The concern is supported as a relative defensive-calibration problem, not as evidence that Wembanyama lacks an elite rim rating.** His current raw rim99 becomes98.724, effectively level with Gobert99.01→98.727. His activity78.696 is also almost identical to Gobert78.698, and below Chet, Bam, Davis, Barnes and Flagg. Consequently current DEF86.7 ties Gobert and trails several of those players. The strong official and expert evidence calls that overall defensive separation into question.

Changing the .60 activity/.40 rim weights alone cannot put Wembanyama above Gobert: both of Wembanyama's present component values are fractionally lower. This is primarily an **input/representation separation** issue between those two, alongside a **summary interpretation** issue across defensive roles. The corrected rim function is monotone; the former hard99 plateau is no longer the current explanation.

Do not automatically give Wembanyama elite navigation, guard containment or every defensive trait because he won DPOY. The episode explicitly notes difficulty switched into space. Diagnose the old manual activity/mobility calibration and the model's limited way of expressing exceptional reach/range and prevention before broad buffs. His within-position overall plausibility is better: canonical presentation OVR95.3 is above Jokić93.6 and the other compared centers.

## Award verification and cutoff

The NBA's **April20,2026 official release** names Wembanyama the **2025–26 Defensive Player of the Year**, the award's first unanimous winner, selected by a100-person media panel. Its official voting materials show every first-place selection for him: **100 of100 first-place votes**. This is established before the October20,2026 game start; it is not later-season information or a claim that he won the award this week. [NBA Communications award release](https://pr.nba.com/victor-wembanyama-2025-26-kia-nba-defensive-player-of-the-year/), [official voting hub, published May27](https://pr.nba.com/voting-results-2025-26-nba-regular-season-awards/), [individual official ballots](https://ak-static.cms.nba.com/wp-content/uploads/sites/46/2026/05/2025-26-Kia-NBA-Defensive-Player-of-the-Year-Voter-Selections.pdf).

The same release reports3.08 blocks/game, San Antonio third in defensive rating, and10.1 fewer points allowed per100 possessions with him on court than off. Those are substantial prevention/team-impact corroboration; the on/off difference is not a clean isolated causal effect or a target individual rating. The award supports exceptional overall defense, not measured values for every subskill.

## Current input, code and scope

This review uses the installed [DEFENSIVE_ALIGNMENT_CORRECTION_2026_11_10.md](../DEFENSIVE_ALIGNMENT_CORRECTION_2026_11_10.md), not its rejected prototypes. Canonical version remains2026-11-10-five-player-scouting-v11, with refreshed derived projections; current SHA-256 is **e4d99897f15bc161a8fcdda14a7605405d991a59ebfa1ac7fe8af788f9029dfc**. The label alone does not identify the old formula or old derived fields.

[Frozen input](probe_artifacts/wembanyama_review_input_20261110.json.gz), [all player traits/provenance/features and code hashes](probe_artifacts/wembanyama_review_snapshot_20261110.json), [private diagnostic results](probe_artifacts/wembanyama_private_diagnostics_20261110.json), and [full relevant retained cues](probe_artifacts/wembanyama_full_relevant_cues_20261110.txt) preserve this pass. Six inspected sources were copied with the wembanyama_source_ prefix; hashes matched the snapshot when diagnostics ran. Future concurrent edits must be distinguished from this recorded state.

All ratings below are **canonical fixed-minute summaries/crosswalks**, not new observed player-card responses. Wembanyama's canonical minutes are29.3. No save, server, game, market, financial probe or production edit ran. Mixed-source dates, health/availability and projected growth remain distinct. Six independent offensive proposals stay queued and are outside this pass.

## Full relevant centers discussion, checked in retained text

Episode4 was published **September2,2026**, before start. Reviewed the full relevant01:35:07–01:45:37 text continuously, including the intervening Jokić rebuttal; this is targeted rechecking of already reviewed source, not a new audiovisual review. Speakers remain unidentified local turns. [Existing complete extraction](EPISODE_4_CENTERS_EXTRACTION.md).

| Interval | Supporting claim | Counterargument / limitation |
|---|---|---|
| 01:35:07–01:35:38 | One turn calls his rim protection/deterrence historically valuable, emphasizing unusual range, ground covered and otherwise unreachable contests. | Explicitly says he can struggle switched into space. Reach is not the same as guard-like foot speed or screen traversal. |
| 01:35:38–01:36:54 | Already strong offense plus transcendent defense motivates #1. | Offensive polish, being pushed out of paint/swarmed and Finals letdown; Jokić is still the better offensive player with a legitimate #1 case. |
| 01:36:54–01:38:45 | Other turn accepts Jokić's historically great offense and carry job as a reasonable rival case. | Says recent series was unusually poor but rejects exaggeration of his whole playoff history. Context/supporting talent matters; do not flatten this into unanimous certainty about absolute player impact. |
| 01:38:45–01:40:50 | Prefers Wembanyama's recent season and three strong playoff series; describes defense against OKC as the dominant factor. | Next-season improvement is part of the ranking. Spurs support/young roster and Denver construction differ; these are not controlled comparisons. |
| 01:40:50–01:42:32 | Claims average team off versus +16 net on, historic defense, strong efficient scoring and roll/paint gravity; calls him clearly best defender. | +16/history claims remain podcast claims, not independently reproduced here. Offensive gravity opening teammate floaters/corner threes is distinct from defensive deterrence. |
| 01:42:32–01:45:37 | Both endorse #1, continued development and a strong postseason overall. | Rapid future growth is prediction; Finals closing/finishing issues are assigned partly to him. They openly acknowledge enthusiasm for Wembanyama and Jokić. No detailed new medical diagnosis is established. |

Thus the meaningful external check is Wembanyama/Jokić at the top, with Wembanyama's defense providing the separation and Jokić's offense the countercase. It does not identify exact OVR spacing, a DEF95 target, or a guaranteed future leap.

## Current within-position and defensive comparisons

The full snapshot retains stable IDs; Wembanyama is **player_sas-victor-wembanyama**. E=engine OVR/OFF/DEF; D=presentation OVR/OFF/DEF. DEF is now direct skill-scale display; OFF/OVR retain the other presentation curve. Their numeric levels are therefore not interchangeable impact units.

| Player | E OVR/OFF/DEF | D OVR/OFF/DEF | Activity / effective rim |
|---|---|---|---|
| Wembanyama |81.0/79.1/86.7|95.3/94.4/86.7|78.696 /98.724|
| Jokić |78.0/81.7/61.6|93.6/95.5/61.6|60.040 /64.000|
| Davis |77.7/68.4/90.9|93.4/86.7/90.9|85.803 /98.474|
| Bam |77.4/66.5/90.3|93.2/85.2/90.3|86.802 /95.531|
| Embiid |76.6/75.2/81.2|92.6/91.6/81.2|69.504 /98.632|
| Chet |74.5/64.2/89.4|91.2/83.4/89.4|83.194 /98.597|
| Towns |72.3/68.7/75.0|89.6/87.0/75.0|60.891 /96.066|
| Gobert |69.6/57.5/86.7|87.7/77.5/86.7|78.698 /98.727|
| Duren |68.1/60.6/77.9|86.5/80.5/77.9|67.158 /93.895|
| Allen |67.8/55.4/83.7|86.2/75.4/83.7|74.203 /97.945|
| Kessler |67.7/58.2/82.9|86.2/78.2/82.9|72.668 /98.188|
| White |69.0/64.1/73.8|87.2/83.3/73.8|84.391 /58.000|
| Castle |68.2/63.9/78.8|86.6/83.1/78.8|78.368 /79.353|
| Barnes |74.1/66.9/88.5|90.9/85.5/88.5|84.782 /94.140|
| Flagg |72.2/66.0/86.3|89.5/84.8/86.3|82.161 /92.592|
| Kawhi |78.3/74.6/86.1|93.8/91.2/86.1|93.008 /75.815|

Top-two within-position OVR broadly reflects the lists. Middle ordering does not reproduce them: Towns #3 on both lists trails Davis/Bam/Embiid/Chet here; availability, projection and sustainability are explicitly mixed in that episode. Retain this as a future comparative concern, rather than dismissing ranks or changing healthy traits to duplicate every placement. Current card OVR must eventually be compared at actual runtime roles before declaring an exact inversion.

### What the sources distinguish

- **Wembanyama versus Gobert/Kessler/Allen/Duren:** unusual reach and ground coverage, not simply more recorded blocks. C00:51:38–00:59:07 gives Gobert strong independent anchoring/consistency and some space defense; C00:08:12–00:10:48 flags Kessler's slower feet/drop limits; C00:03:08–00:04:48 gives Allen dependable protection rather than singular dominance; C00:32:03–00:32:29 calls Duren improved/pretty good. Duren's positive early independent rim data in the prior review remains counterevidence to aggressive cuts.
- **Chet/Bam/Davis:** C00:59:07–01:13:07 explicitly contrasts Chet's rim protection with Bam's switching/playmaking; Chet's offensive pressure/release limits and Wembanyama matchup are meaningful. Davis's C00:38:58–00:51:38 healthy two-way skill is contrasted with health/physical-return risk, not proof that he is the best current defender. A healthy ability rating need not follow availability-weighted list order.
- **White/Castle:** SG01:34–01:44 supports White's anticipation/guard help and blocks; PG00:18:37–00:22:05 supports Castle's containment but questions secondary rim/off-ball disruption. White73.8 versus Castle78.8 is still an input-shape concern, not fixed by direct display.
- **Barnes/Gobert and Flagg:** PF01:10–01:17:38 credits Barnes with switching, hands, help and boards; C00:51:38–00:59:07 emphasizes Gobert's continuous rim anchoring/team dependence. Barnes88.5 above Gobert86.7 need not be forbidden by position, but the current scalar mixes those jobs without measuring their relative possession value. Flagg's SF01:03:29–01:15:15 case contains substantial forecast; do not use that to validate an already near-Wembanyama DEF.
- **Kawhi control:** his high activity reflects effort96.36/lateral88.02/navigation94.77. The current SF scoring/ball-security praise does not establish those magnitudes. Corrected Durant attribution stays intact. Do not lower others or inflate Wembanyama simply to preserve this control's current ordering.

## Wembanyama input lineage: a specific diagnostic

Current defensive traits: **effort82, lateral70, navigation86.62, scheme82, rim99**. These are estimates, not five observed skill tests.

Rim inference already includes height/block/impact and defensive-role priors. Current rim99 is an explicit manual calibration whose note says opponent shot selection changes, not just blocks. Effort82 and lateral70 are also manual decisions. Their metadata show pre-preservation June-calibrated values93.59 and84.78, respectively, but those larger prior outputs are not automatically truer. Lateral's manual note says unusual mobility for his size but not guard-like navigation; this cross-skill rationale deserves scrutiny because navigation itself remains86.62. Scheme82 has an age/maturation note. Detailed raw components and all15 current traits are retained in the snapshot.

Activity combines .42 effort + .36 lateral + .22 navigation. Lateral70 therefore depresses activity despite reach/range, and no distinct coverage-range variable restores that advantage. Scheme affects spatial help but is absent from headline DEF. That can be defensible for a generic activity grade; it does not automatically establish the value of Wembanyama's defensive role.

Private sensitivities, **not approved player targets**:

| Diagnostic | Activity / rim / DEF |
|---|---|
| Current |78.696 /98.724 /86.708|
| Rim99→100 only |78.696 /99.000 /86.818|
| Effort82→90 only |82.056 /98.724 /88.724|
| Both |82.056 /99.000 /88.834|

A single extra rim point barely changes the summary. To force DEF above all compared centers by effort alone would require approximately99 effort with the other components fixed. That is an algebraic warning against chasing the ranking, not evidence of99 effort. Do not indiscriminately raise lateral/navigation and erase the source's switched-in-space limitation.

## Gameplay prevention: present but limited

[defense.py](../../src/nba_gm_data/defense.py) now supplies the monotone rim response, activity and skill to cards/features/spatial defense. [save.py](../../src/nba_gm_data/save.py) directly displays DEF; the old generic display inflation does not explain the current Wembanyama/Gobert tie.

[sim.py](../../src/nba_gm_data/sim.py) team_shot_diet **already models shot avoidance**: opponent rim above60 subtracts .0028 per feature point from initial rim share, subject to clamps and normalization. It also reduces shot quality and applies separate defensive-rim/context terms to offense. [spatial.py](../../src/nba_gm_data/spatial.py) spatial_matchup_adjustment shifts zone shares and quality using modeled suppression. Blocks/rebounds have additional rim-related terms. Thus “the engine only counts blocks” is false.

However this is a generic, bounded, minutes-weighted team/zone representation. Equal effective rim values cannot express Wembanyama's exceptional radius/avoidance relative to another99-level anchor through an extra reach channel. There is no independent measured avoidance/range input here. Suppression is modeled, not observed opponent decisions; frequency and quality clamps can compress strong-defense differences. No game was run, so this review cannot establish that his simulated Spurs defense is too weak or quantify the missing team impact. The official10.1 on/off difference must not be inserted as a trait or directly reproduced by a one-player formula.

## Implementation recommendations

1. **Preserve the current correction:** direct DEF meaning, no neutral integrity in skill, shared component ownership, monotone upper rim response and removal of a second defensive height bonus. Do not revert to legacy prototypes or invent another height bonus to rescue one player.
2. **Treat Wembanyama as the strongest pre-start rim/prevention anchor in the next calibration comparison.** If the current scalar requires a single top raw anchor,100 is a defensible candidate relative to Gobert99.01, but its measured effect is only about0.11 DEF; it is not a sufficient remedy. Confidence high on exceptional role, low on exact point spacing. No global average or DEF95 target is supported.
3. **Audit the manual effort82/lateral70 decisions together with their meanings.** The preserved lower values, high navigation and source emphasis on coverage create a specific inconsistency to resolve. Effort90 is a useful bounded diagnostic, not an award-derived measurement. Keep the explicit space-containment weakness; do not automatically restore all June prior values.
4. **Evaluate whether the .60/.40 number is being asked to represent defensive impact rather than general skill.** It downweights a specialist's exceptional rim role relative to high activity, but a different fixed blend alone cannot separate Wembanyama from Gobert with current component inputs. A role-sensitive interpretation or a properly evidenced range/prevention distinction may be needed; this source does not choose weights or authorize a new taxonomy. Backend should choose the smallest coherent change, not a hidden Wembanyama-specific formula.
5. **Use existing backend controls before any further raw cuts:** White/Castle helper-versus-containment; Barnes/Flagg helper-versus-center; Chet/Bam switch/rim tradeoff; installed Duren/Kawhi. Reassess held Castle/Paolo defensive parts after that decision. Preserve six independent offensive parts in their separate queue.
6. **Maintain the within-position ranking check:** Wembanyama/Jokić currently pass the broad top-tier ordering. Record middle-list deviations and their health/projection/role explanations; do not convert ranks to exact OVR or use one postseason to flatten counterarguments.

No unconditional broad Wembanyama buff is recommended from this pass. The precise next action is to resolve the identified manual activity/coverage semantics and top-rim separation with the backend's shared controls. No additional human identity/date question or approval framework is needed. No production files, saves, games, finances, servers or UI were changed.
