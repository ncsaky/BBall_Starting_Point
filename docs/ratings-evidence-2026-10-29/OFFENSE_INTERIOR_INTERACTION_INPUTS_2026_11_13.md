# Offensive/interior interaction evidence packet — November 13, 2026

This bounded packet supports the backend's isolated, default-OFF shooting/spacing/finishing work. It supplies twelve contrasting profiles, actual-schema source inputs, separate hypothetical controls and source-count validation. It does not recommend production ratings or establish final player, role or league calibration.

The gameplay target is **October immediately before the regular season**, as settled by the user. Completed 2025–26/2024–25 performance and pre-start offseason assessments are eligible, subject to material intervening events. July is retained provenance, not an alternative start target. This packet reuses dated assessments without a fresh trade/injury/signing audit; healthy technique, availability, role forecasts and post-start results remain separate. See [the October policy](OCTOBER_START_EVIDENCE_POLICY.md). No new episode extraction or audiovisual review occurred.

## Delivery and schema contract

[Machine-readable packet](OFFENSE_INTERIOR_INTERACTION_INPUTS_2026_11_13.json) contains `player_input_section`, eleven separate `scenarios[].input_section` objects, observed constraints, scouting ranges and context metadata. The wrapper itself is not a production player-input document. Validate its nested sections with `PlayerInputs` / `validate_input_section` using `player_performance_inputs_v1` and `player_performance_registry_v1`.

All twelve sections pass the actual pure schema utility; twelve source player documents round-trip exactly. Each source player has 35 explicit IDs: S01–S15, P01–P12, T01–T04, T09–T11 and T18. Of 420 records, 36 are reported-tool conversions, 20 scouting technique estimates, 12 FT conversion proxies and 352 explicit unknowns. The other 59 approved IDs per player remain unknown by omission. The approved full model still has **94 inputs**, including separate passing recognition/execution; this packet does not replace it with a shortlist.

[Validation results](diagnostics/milestone3_20261113/input_validation.json), [source section](diagnostics/milestone3_20261113/source_player_input_section.json) and [reproducible builder](diagnostics/milestone3_20261113/build_offense_packet.py) are retained. Acceptance verifies storage/provenance/arithmetic, not physical validity, formula behavior or basketball calibration. Production import is explicitly unauthorized.

## Shooting denominators and scale boundaries

Twenty-three player-seasons match retained ESPN career **raw totals** for all six FG/3P/FT made/attempted counts. All satisfy count bounds and `PTS = 2×FGM + 3PM + FTM`. Harper's missing 2024–25 NBA season is expected, not zero-filled. Multi-team seasons use the combined total once, or sum stints only when no combined total exists; Garland and Zubac are not counted twice. [The denominator report](diagnostics/milestone3_20261113/career_shooting_denominator_validation.json) retains row selection, endpoint provenance and hashes. No damaged historical game-cache FGA supplies any denominator.

Season aggregates describe realized outcomes and opportunity. Three-attempt share is not intrinsic T02, overall 3P% is not three independent catch/pull-up/movement samples, and FTA/FGA does not isolate contact technique or willingness. A zero-attempt category stays unobserved.

The twenty technique estimates use provisional `research_technique_reference_v0_2026_11_13`: 50 functional, 75 strong, 90 exceptional reference anchors. These are scouting judgments, not calibrated percentiles, conversion probabilities or measured coefficients. Midpoints serialize broad ranges; range endpoints are not statistical confidence intervals. Directional profile confidence can exceed confidence in isolated magnitude. Shared episode claims are correlated evidence.

S07 instead uses **`research_FT_conversion_percent_proxy_v1`**, equal to 100×validated FTM/FTA rounded to one decimal. It is an explicitly labeled conversion proxy requiring a consumer mapping, not an assertion that 90% FT equals a generic technique grade of 90. Wilson intervals in notes quantify conversion sampling uncertainty only; they do not isolate technique from form/health/history. Do not silently treat its scale as interchangeable with the other grades. FT receives no preparation-speed bonus.

## Twelve contrasts and retained evidence

Counts below are completed **2025–26 regular-season** totals, independently checked against retained career raw totals. Timestamp windows refer to the existing transcript-only extractions; speakers remain unidentified/local turns. Each JSON cohort entry retains its source date, assessment, inference and limits.

| Player | Source window and useful contrast | 3PM/3PA; FTM/FTA | Counterevidence or boundary |
|---|---|---|---|
| Stephen Curry | PG, Aug 5, 01:11:36–01:25:46: off-ball gravity and strong shooting across modes | 190/484; 204/221 | Age/availability; mode grades share evidence, no timed release observation |
| Desmond Bane | SG, Aug 14, 00:50–01:00 and 01:06–01:10: movement/spot-up/pull-up shooting and straight-line force | 167/427; 314/346 | Pressure, separation and interior finishing limit primary creation |
| Devin Vassell | SG, Aug 14, 00:22–00:24: difficult catch/movement/pull-up shotmaking | 166/432; 106/130 | Disagreement: solid rather than elite, jump-shot-dependent; user-confirmed alias stays resolved |
| Derrick White | SG, Aug 14, 01:34–01:44: high-volume shooting with a poor recent season | 209/640; 184/204 | Bounce-back is forecast; limited inside creation; no supported timed-release claim |
| Luka Dončić | PG, Aug 5, 01:27:17–01:37:18: on-ball shotmaking/P&R versus settling farther out | 254/694; 503/645 | Reduced rim access and health context; passing is not supplied by S02 |
| Darius Garland | PG, Aug 5, 00:10:42–00:12:15 and 00:22:05–00:29:26: on/off-ball shooting plus explicit floater praise | 122/308; 105/122 | Small-guard rim/FT limitations and injury/role changes; floater touch does not create access |
| Zion Williamson | PF, Aug 28, 00:16:19–00:19:58: exceptional paint pressure, touch and body control | 1/4; 333/465 | Availability separate from healthy skill; strength/first step cannot be credited twice as technique |
| Dylan Harper | PG, Aug 5, 00:29:26–00:39:09: size, pace and varied paint finishes | 61/178; 90/119 | Shooting/advanced reads still developing; superstar language is ceiling, not present ability |
| Rudy Gobert | Centers, Sep 2, 00:51:38–00:59:07: limited spacing and creator-dependent offensive involvement | 0/5; 159/302 | Roll opportunity is not self-creation; no inferred dunk/catch grade from assisted makes |
| Ivica Zubac | Centers, Sep 2, 00:17:18–00:38:52, interleaved Duren: dependable paint touch, screens/post work | 0/0; 101/142 | No 3P sample; pace/team fit uncertain; future S23 hooks must not duplicate S10 accuracy |
| Bam Adebayo | Centers, Sep 2, 01:06:54–01:13:07: willingness versus inefficient jump-heavy offense | 127/400; 329/423 | All-jumper discussion cannot identify separate S04/S05; new-role benefits are projected |
| Victor Wembanyama | Centers, Sep 2, 01:35:07–01:45:37: stretch threat and extraordinary tools versus unfinished paint polish | 122/350; 372/450 | Reach does not guarantee touch; growth forecasts are not current finishing technique |

Sources: [PG extraction](POINT_GUARDS_FULL_EXTRACTION.md), [SG extraction](SHOOTING_GUARDS_TOP_10_FULL_EXTRACTION.md), [PF extraction](POWER_FORWARD_FULL_EXTRACTION.md), [center extraction](EPISODE_4_CENTERS_EXTRACTION.md). These are reused source windows, not newly reviewed entire episodes.

## What can and cannot be populated

S01/S02/S03 receive overlapping but separately uncertain shooting hypotheses for Curry/Bane/Vassell, plus selected White/Luka/Garland estimates. The same shot can involve movement and a catch; do not add full accuracy bonuses for each descriptive label. S04–S06 remain unknown rather than extrapolated from global jumpers. S07 has the separate proxy above. S08 preparation and S09 extension mechanics remain unknown for every source player: no measured milliseconds, exact release point or deep-distance mechanics curve is available.

S10 receives broad close-touch hypotheses for Zion, Harper, Zubac and Wembanyama; S11 a Garland floater hypothesis; S15 Zion/Harper contact-control hypotheses. These effective observations incompletely separate physical tools and context, hence low magnitude confidence. S12 dunk execution, S13 aerial receive-to-finish and S14 catch control remain unknown. Lob makes do not measure catch failures, and rim FG% cannot independently identify layup, dunk and contact execution.

P01/P02/P04 convert reported height/span/mass to cm/kg; they are estimates with unknown original measurement protocol/date/footwear. Conversion precision adds no measurement precision. No observed P03 standing reach, exact shooting release height, jump/capacity test or recovery protocol is invented. All source tendencies remain unknown. T09/T10/T11 add cutting/relocation/screen-context preferences only as declared experimental controls; they are not newly inferred player propensities.

## Separate experimental controls and expected checks

The reference scenario retains source estimates while filling unknowns with visibly synthetic controls. Unknown skills use 70; a hypothetical standing-reach fixture is `height_cm + 70 + 0.5×(span−height)`; jump gain is 40 cm. Other dimensional fixtures use 3 m/s² acceleration, 6 m/s speed, 2.5 m/s lateral speed, 1000 N force and 0.5 s balance. Conditioning/recovery use display-only 50 proxies. None is an observed protocol, measured shot release point or adopted physiology model.

T01 supplies a normalized action distribution; T02 supplies a declared two-bin 2pt/3pt spatial reference; T03 supplies catch/pull-up/movement branches conditional on a selected shooting context; T11 supplies screen/roll/pop/slip alternatives. Other included propensities use 0.5 at a declared eligible opportunity. These mutually exclusive fixture branches are an experiment convention, not a claim that source shot labels never overlap.

The eleven complete scenario sections are reference; high-skill/low-willingness, high-skill/high-willingness, low-skill/high-willingness; slow/fast preparation; limited/strong extension; and separate floater, contact-control and aerial-coordination changes. Single-input axes additionally exercise S01–S03, S08–S15, T18 and standing-reach uncertainty.

| Check | Interpretation to preserve |
|---|---|
| Skill × willingness | High accuracy and low appetite differ from high volume with weak conversion; spacing credibility needs both and defensive response |
| Preparation × arrival | Faster preparation can shorten a contest window; no universal flat accuracy boost or FT benefit |
| Range extension | Change mechanics preservation at distance, not a second global shooting bonus or unlimited deep accuracy |
| Floater/contact/dunk/lob | Supply matched access and pass quality; vary only the relevant execution mechanism |
| Catch/control and finish | A failed receive prevents the finish; do not stack independent full-probability bonuses for catch, aerial and dunk labels |
| Spacing × POA × anchor position | Crowding, first-line resistance and pulling the anchor away change opportunities and help cost; isolated player ordering need not persist |

Contexts explicitly vary arrival delay 0/0.25/0.75 s, approach angle 0/45/90°, reach ±10 cm, credible five-out/crowded paint, strong/weak POA support and anchor at rim/pulled away. Finish contexts supply access and absent/accurate/difficult lobs. Passing/creation and coaching remain supplied context, not secretly implemented talents. No response results are claimed: this research ran no engine games or simulations.

## Residual source check and remaining acquisition gaps

One retained ESPN recheck of Chicago's November 29, 2025 game (`401810150`) leaves the source discrepancy unresolved: nine identified playing rows sum to 38 FGM, while the team row lists 39; player scoring components imply 99 versus team 101. There are also two DNP rows and one unidentified zero-stat row. This is not twelve successfully identified player joins. Identified scoring rows agree with retained points/3PM/FTM. The source itself disagrees at team/player level; attribution and cause remain unknown. Do not assign the residual to a player. Other six mismatches remain unverified/quarantined. [Corrected bounded-check notes](diagnostics/milestone3_20261113/residual_coverage_correction.json) preserve this limitation. Backend owns parser/cache repair; research did not modify it or retry additional games.

The existing [BBI plan](BBI_ACQUISITION_PLAN_2026_11_11.md) remains the acquisition route. Optional grouped sample: these twelve players over two completed seasons with shooting mode/distance/openness counts, floater/contact subsets and role/opportunity metadata, preserving provider definitions and overlapping categories. Actual current export/access/denominators remain unverified. Timed preparation, distance-preservation mechanics, aerial catch failures and exact release geometry are not promised provider fields. Aggregate FT evidence is already usable; unavailable tracking does not block synthetic exploration or conservative scouting estimates. No purchase, credentials or broad new request campaign is needed for this delivery.

**Whole-model calibration gate:** connected offense/defense, passing/creation, coaching/deployment and downstream AI/development validation must precede final whole-model calibration. No final isolated player/role/league tuning, OVR targets, growth changes or production activation follows from this packet. The next implementation step belongs to the backend; this research increment stops here.
