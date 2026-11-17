# Defensive scale and semantics review — 2026-11-10

**Finding:** currently high displayed DEF can be misleading when read as a universal measure of defensive impact or as equivalent gameplay effectiveness. Several causes combine: correlated and partly subjective source calibration, a summary that blends distinct defensive jobs, and a presentation mapping that raises/compresses values. Separately, the scalar gameplay rim channel genuinely saturates at the top. Fixing one does not fix the others.

**Rim deterrence currently represents inferred effective rim capacity incorporating size and role, not physical-independent technique.** The spatial model then adds height again. Therefore two players with the same rim rating do not necessarily have identical interior defense throughout the game. This is a semantic/calibration issue to make explicit, not proof that every height contribution is automatically erroneous.

This supports the backend's shared correction. It does not prescribe exact weights, probabilities, universal cross-position rankings or a league-average target. The six independent offensive subparts in [the current decision sheet](NEXT_RATING_BATCH_DECISION_SHEET.md) remain ready. Castle/Paolo defensive proposals still require reassessment after the shared correction. This document is supporting evidence, not an additional approval gate.

## Frozen evidence and scope

Read [DEFENSIVE_ALIGNMENT_REVIEW_2026_11_10.md](../DEFENSIVE_ALIGNMENT_REVIEW_2026_11_10.md), which reports isolated legacy/linear/smooth/shared-card prototypes, fixed-game and fresh economic checks. Those experiments are backend evidence, not experiments repeated here. In particular the shared-card prototype's large card reductions are not accepted calibration simply because its numbers are lower.

Private calculations use canonical **2026-11-10-five-player-scouting-v11**, SHA-256 **0733a2c0ab62faf893c07d9240c23f6a47bed057205bda4bb13c08ea1b07332d**. [Results and source hashes](probe_artifacts/defensive_semantics_results_20261110.json), [frozen compressed input](probe_artifacts/defensive_semantics_input_20261110.json.gz) and [runner](probe_artifacts/defensive_semantics_20261110.py) retain the analysis. Six inspected Python sources are copied beside those artifacts with the defensive_semantics_source_ prefix. Their hashes stayed identical during the calculation. A concurrent later backend edit does not retroactively change these findings.

Only private summary/feature/spatial-profile calculations ran. No games, markets, saves, UI, server, dependency or production changes occurred. Current data are mixed-date: March skill inputs, June subjective priors, preserved released traits, later roster/career/profile adjustments and the v11 scouting overlay. They are not uniformly July measurements.

October 20, 2026 remains the start cutoff. Offseason scouting is eligible subject to dated material events; opening-week anecdotes and later injuries are not backdated. Transcript opinions remain opinions, even when useful. All existing aliases and the corrected Durant attribution remain resolved. No new human clarification is necessary.

## Where physical size and role enter

| Stage | Inspected implementation | Meaning and limitation |
|---|---|---|
| Initial rim inference | [traits.py](../../src/nba_gm_data/traits.py), build_traits_for_player: weighted block-percentile .55, height-percentile .24, CraftedDPM .15, DARKO .06; rim-protector role adds16 if block/height percentile reaches82, otherwise6 | Size is explicitly embedded. Block rate also reflects physical tools, opportunity, scheme and role. This is not a height-neutral assessment of timing/technique. Weights describe code, not weights validated by podcasts. |
| Subsequent calibration | Same file: subjective June league ratings are quantile-mapped/blended, then composite OFF/DEF/REB/OVR nudges act. Released values may be restored; manual/scouting layers can alter them later. | A current rating cannot be reconstructed from height alone. CSV65 can map to a near100 target because of the reference distribution. Confidence may rise from processing rather than more observation. |
| Scalar game rim channel | [sim.py](../../src/nba_gm_data/sim.py), player_feature_vector: nonlinear_high(raw rim,68); no new height/position term in that scalar itself | Equal raw rim yields equal scalar rim. It feeds team rim suppression, blocks, rebounds and anchor/strength calculations. This is one channel, not the complete defender. |
| Spatial paint defense | [spatial.py](../../src/nba_gm_data/spatial.py), player_spatial_profile: paint contest includes .55×rim + .14×effort + .8×max(height−78,0); suppression includes .58×rim + .12×scheme + the same height term, plus stable jitter | Height independently adds reach/paint effect even when the trait is held equal. A second size contribution is real in the code. Whether it is appropriate residual reach or excessive repetition needs outcome calibration and a declared meaning. |
| Midrange/perimeter spatial defense | Same function: midrange uses scheme/lateral/effort; perimeter uses navigation/lateral/effort/scheme | The model distinguishes different tools by zone. Position label alone does not create a perimeter defensive bonus in these formulas. |
| Position/role effects | [talent.py](../../src/nba_gm_data/talent.py) role weights; sim player_impact_score; [save.py](../../src/nba_gm_data/save.py) starting-slot fit and hard violations | Labels do have basketball consequences through skill weighting, impact, eligibility and lineup assignment. They are not a pure cosmetic label. But changing SG to C does not itself turn equal raw rim into a higher scalar rim channel. |
| Headline and display | save player_attribute_summary → player_display_attribute_summary | Current DEF means average effort/scheme/navigation/rim, not height-adjusted total impact. It does not directly use lateral agility in that mean, although lateral enters other summaries/game channels. |

Role labels used in trait inference are not interchangeable with roster position. A descriptive “Rim Protector” input can add a prior bonus; a player record's “C” label can alter role weights/lineup assignment. Neither substitutes for verified containment, screen navigation or help recognition.

The spatial artifact's official_spatial_priors currently returns no matched profiles. Zone outputs here are modeled from traits/physical data, not direct player tracking measurements. Stable player-ID jitter also changes some values across real players. A comparison that changes both identity and height cannot attribute every difference to height.

## The 6-foot-5 versus 7-foot thought experiment

The private diagnostic holds the **same player ID, all other traits, minutes and context fixed**, sets raw rim to80, and independently changes height77→84 inches and position SG→C. It uses White's remaining traits merely as a fixed input vector; it is not a scouting estimate for a hypothetical real player.

| Height / label | Engine DEF | Scalar rim feature | Activity | Restricted-area contest / suppression | Engine OVR / impact |
|---|---:|---:|---:|---:|---:|
| 77in / SG | 82.0 | 83.378 | 84.391 | 75.98 / 77.60 | 71.0 / 73.887 |
| 84in / SG | 82.0 | 83.378 | 84.391 | 80.78 / 82.40 | 71.0 / 73.887 |
| 77in / C | 82.0 | 83.378 | 84.391 | 75.98 / 77.60 | 72.9 / 75.738 |
| 84in / C | 82.0 | 83.378 | 84.391 | 80.78 / 82.40 | 72.9 / 75.738 |

Height alone increases these paint spatial values by **4.8**, with equal scalar rim/activity/headline DEF. Position alone changes OVR/impact through enabled role weighting, not those spatial defensive values. Label changes can also alter actual lineup deployment; no rotation or game was run here.

Thus “same80 means same overall rim effectiveness regardless of size” is false for this implementation. “The taller player necessarily wins every defensive matchup” is also unsupported: lateral movement, positioning, coverage, teammates and opponent actions remain relevant. The numbers are model units, not percentage-point changes in opponent shooting.

There are two legitimate possible concepts: a size-neutral technique rating with size applied downstream, or a rating for effective rim prevention already incorporating physical tools. Current inference is closer to the latter, while spatial treatment retains an additional physical modifier. The backend should document that relationship and calibrate it once per channel; this review does not call for a second physical-neutral skill system or a role taxonomy redesign.

## Integrity is targeting risk, not a skill grade

Legacy activity is .42×effort + .36×lateral + .22×navigation. Weak-link targeting is 50 + .55×max(48−activity,0)^1.15, bounded1–99. Integrity is100 minus that value.

| Activity | Weak-link signal | Integrity |
|---|---:|---:|
| 30 | 65.273 | 34.727 |
| 48 | 50 | 50 |
| 70 | 50 | 50 |
| 90 | 50 | 50 |

At activity48 and above, integrity stops changing. Its neutral50 means no extra targeting penalty in this path; it does not say a90-activity defender has only50 defensive skill. Averaging it into a skill headline depresses adequate and great defenders toward the same neutral reference and blurs excellence with absence of a weakness.

The prior shared-card prototype averaged activity, rim, anchor and integrity. Because anchor itself contains integrity and general impact, its effective integrity weight was .275 and general-impact weight .0375. That makes it an outcome/context rollup with duplicated neutral-risk contribution, not an authoritative defensive-skill scale. Keep targeting risk available to matchup logic. For a skill summary, either exclude this neutral term or explicitly translate a penalty relative to its neutral baseline; do not average50 as though it measured mediocre skill. This statement does not select an exact replacement weight or redesign targeting behavior.

General impact can also include offense. Do not let a scoring improvement silently become evidence of better defensive skill merely because impact enters a defensive rollup.

## Saturation versus presentation compression

These independent channels must be checked separately:

| Raw rim value | Legacy scalar game rim | Presentation transform of that raw value |
|---|---:|---:|
| 60 | 60.000 | 80.0 |
| 68 | 68.000 | 86.4 |
| 78 | 80.724 | 93.6 |
| 88 | 94.173 | 97.4 |
| 90 | 96.908 | 98.0 |
| 92 | 99.000 | 98.2 |
| 94 | 99.000 | 98.4 |
| 97 | 99.000 | 98.8 |
| 99 | 99.000 | 99.0 |

The last column illustrates the presentation transform on one scalar; actual card DEF transforms its **DEF summary**, not raw rim alone. Values92–99 remain distinguishable in display while their scalar rim channel is identical. Conversely, a large change in one game feature may produce a tiny displayed DEF change after averaging and upper-tail compression.

Backend's frozen v11 comparison shows Gobert/Kessler/Allen scalar rim all99, but their restricted-area spatial contests still differ:92.63/92.00/88.19. Therefore saturation erases a scalar distinction, not every distinction throughout gameplay. A high-tail correction should preserve meaningful ordering without claiming that all bigs were previously identical. The curve's exact shoulder cannot be inferred from ordinal scouting language.

## Qualitative basketball anchors and counterevidence

Source dates: SG Aug14, PG Aug5, PF Aug28, SF Aug19, C Sep2,2026. See the [source ledger](SOURCE_INDEX.md), [cue checks](probe_artifacts/next_batch_decisive_cues_20261110.txt) and [five-player checks](probe_artifacts/decisive_cue_checks_20261109.txt). These anchors constrain plausible behavior, not exact weights.

| Group/control | Supported expectation and dated cues | Counterevidence / what is not established |
|---|---|---|
| White / Castle | [SG01:34–01:44](SHOOTING_GUARDS_TOP_10_FULL_EXTRACTION.md): White anticipation, positioning, guard help/blocks. [PG00:18:37–00:22:05](POINT_GUARDS_FULL_EXTRACTION.md): Castle strong star-guard containment, size/strength, weaker off-ball/rim disruption. | Castle has fouling/turnover limits and Wemby context. Neither deflections nor those opinions measure exact screen-traversal skill. White's help reputation does not imply center-like paint prevention. |
| Barnes / Flagg | [PF01:10–01:17:38](POWER_FORWARD_FULL_EXTRACTION.md): Barnes switching, hands, help/rim play and boards. [SF01:03:29–01:15:15](SMALL_FORWARDS_FULL_EXTRACTION.md): Flagg broad connective/two-way rookie baseline. | Barnes jumper/lead-scoring ceiling and Flagg workload/growth uncertainty remain. They can help at the rim without being full-time rim anchors; Flagg's projected leap is not present proof. |
| Gobert / Kessler / Allen | [C00:51:38–00:59:07;00:08:12–00:10:48;00:03:08–00:04:48](EPISODE_4_CENTERS_EXTRACTION.md): Gobert sustained anchoring/consistency; Kessler large drop/rim presence and boards; Allen dependable rim/finish floor. | Kessler foot speed/coverage limits; Allen lacks some standout dominance; Gobert offensive limits. No source identifies exact relative deterrence probabilities or universal superiority against every action. |
| Installed v11 Duren | [C00:32:03–00:32:29](EPISODE_4_CENTERS_EXTRACTION.md): improved/pretty good defender and rim protector; independent early-season positive rim evidence is retained in the five-player review. | Offensive playoff failure is not defensive evidence. Current raw90→scalar96.908 already separates him modestly; reassess on the new shared channel before any further cut. OREB remains separate. |
| Installed v11 Kawhi | [SF01:32:24–01:34:20](SMALL_FORWARDS_FULL_EXTRACTION.md): efficient physical scorer, handle and ball security. v11 rim74.25 removes much of the old center-like channel. | No current navigation/continuous-engagement estimate follows from those offensive claims. “Solid passer/defender” at01:31:19 describes Durant. Kawhi's historic awards do not establish every contemporary subskill. |
| Luka / Curry / Herro controls | [PG01:27:17–01:37:18](POINT_GUARDS_FULL_EXTRACTION.md): Luka elite offense with defensive targeting. [SG00:25–00:30](SHOOTING_GUARDS_TOP_10_FULL_EXTRACTION.md): Herro targeting/pressure limitations. Curry's PG01:11:36–01:25:46 case chiefly concerns offense/availability. | A weak defender must remain vulnerable where evidence supports it, but offense/age/size alone cannot identify all defensive tools. Curry should not become equivalent to Luka merely because both lack center rim impact. |
| Edwards / Vassell controls | [SG02:03:14–02:03:38;00:23:53–00:24:30](SHOOTING_GUARDS_TOP_10_FULL_EXTRACTION.md): Edwards has not shown the hoped-for sustained plus impact; Vassell occasional blocks versus disputed consistent help impact. | Athletic tools and positive bursts remain real counterevidence. Installed v11 judgments are not instructions to repeat reductions after a formula change. |

Containment, navigation, recognition and deterrence are different jobs. Box steals/blocks can support an activity/paint account but do not identify every one. Role and teammate context affect opportunities. Repeated host evaluations remain one commentary lineage; they are not multiple independent statistical confirmations.

## Why high DEF appears widespread

1. **Source/calibration:** event/impact inputs recur across traits. Role bonuses and subjective quantile mapping can push several related traits high; preservation retains them. This creates correlated high inputs but alone does not prove repeated gameplay counting or a bad defender.
2. **Summary meaning:** equal averaging of effort/scheme/navigation/rim mixes perimeter, recognition and interior jobs while omitting lateral from headline DEF. An eye-catching card can conceal the actual specialization.
3. **Display:** the mapping turns engine60 into80 and80 into95. That makes many values look excellent on a familiar sports-game scale. It is not a percentile label and not an effectiveness probability.
4. **Game response:** the nonlinear rim bonus/saturation adds a separate upper-end problem. It does not directly cause legacy headline DEF to be high, because that summary uses raw traits.
5. **Context:** spatial height and role-weighted impact add effects absent from the headline. One replacement average cannot automatically represent all contexts.

A downward DEF correction can be justified by a better definition or calibration. It is not inherently a regression. It becomes suspect if selected merely to make the histogram look normal, if it destroys supported specialist behavior, or if it silently changes gameplay/economic incentives beyond the intended correction. Do not target a league average, fixed cross-position ordering or desired OVR rank for appearance.

## Backend preservation/change checklist

- State whether headline DEF summarizes defensive capability or a context-specific outcome. Share authoritative skill inputs with gameplay while keeping targeting risk and offense-derived impact conceptually separate.
- Preserve explicit size/role semantics: rim inference already includes height/role; spatial paint adds height. Keep or revise that extra modifier deliberately, rather than assuming equal raw scores imply physical equivalence.
- Remove genuine high-tail scalar flattening without moving unrelated low/mid channels merely to lower cards. Demonstrate the shape and relevant scarcity/role boundaries; smoothness alone is not basketball calibration.
- Preserve qualitative specialization: White help versus Castle containment, helper forwards versus centers, and weak-link controls. Do not demand a universal positional ordering.
- Check scalar and spatial channels separately. Avoid compensating with dozens of player edits when a shared definition or source mapping is the problem.
- Reassess **Castle effort/rim** and **Paolo rim** after the shared correction. Do not automatically apply their held targets. Recheck current v11 Duren/Kawhi and helper Barnes/Flagg for changed scale meaning; this is not a request for further raw cuts.
- Keep six independent offensive subparts ready: Bane/Reaves versatility, Herro rim pressure, Brown reads, Durant/Garland handling. Herro handling and Paolo reads remain separately held for evidence/overlap reasons.
- Use the backend's already-owned fresh valuations/FA profiles, bids, legal extension/negotiation and retention checks. Display/OVR changes can have economic consequences even with fixed game channels; stored asks alone cannot show neutrality. No duplicate financial or game campaign is requested here.
- User clarified old careers are disposable. Do not add compatibility/version frameworks as a prerequisite or expand this work into career preservation infrastructure. Existing reports' older compatibility recommendations are superseded by that instruction.

There is no unresolved human identity/date question or necessary new approval bottleneck. The backend can proceed within its ownership using these constraints and record which meaning changed. This review ends at semantics, qualitative anchors and private calculations.
