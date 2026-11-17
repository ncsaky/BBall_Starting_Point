# Player-model evidence coverage — November 12, 2026

**Milestone1 complete at the schema/evidence-mapping level.** The [approved map](../PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md) was read in full. All **94 approved inputs** are retained:46 non-passing skills,18 passing skills,12 physical families and18 tendency families. The old21-field shortlist is obsolete. Sparse evidence changes estimation/confidence, not the approved catalogue.

The [machine-readable ledger](PLAYER_MODEL_EVIDENCE_COVERAGE_2026_11_12.json) has one entry per actual input, including separate `F01.recognition`/`F01.execution` through `F09.recognition`/`F09.execution`. These are research design IDs, **not backend canonical-key choices**. Each entry carries its approved definition, available/planned sources and seasons, evidence type, denominators, inference method, physical/context confounding, uncertainty and gaps.37 derived objects and22 role/contribution/output references are preserved separately; they are not additional raw inputs or verified formulas.

Completed coverage does **not** mean94 independent measurements,94 production ratings per player or a complete engine integration. This pass assigns **no league-wide player values**. The separate [interior packet](INTERIOR_DEFENSE_CALIBRATION_PACKET_2026_11_12.md) contains12 contrasting players and8 explicitly provisional technique ranges. No production/backend registry/architecture/code/UI/save changes or simulations occurred.

## Actual roster-wide source availability

Counts below are a fresh local inventory against691 canonical players, not a claim that a provider has no other data. Explicit ID matches are distinguished from name matches. Full hashes/counts and source caveats are in [source inventory](probe_artifacts/player_model_source_inventory_20261112.json). The architecture/canonical and original source files were not edited.

| Source ID | Retained evidence / coverage now | Important limit |
|---|---|---|
| L1 |526 skill rows, all526 match canonical names uniquely. Generated March11,2026; hybrid/provider/augmentation/workbook data. | Mixed windows and observed summaries/models/context; not an October complete skill census. Missing means unavailable, not low ability. |
| L2 |679 retained ESPN profiles;616 of691 canonical players match a profile by explicit ESPN ID. Positive regular-season rows:539 for2025–26,455 for2024–25,372 for2023–24. | Profile count is not current-player-season coverage. Name-only additional matches require separate identity QA. Totals do not identify action-specific technique. |
| L3 |1310 game records:1235 regular,75 playoffs;539 canonical players have positive-minute rows. | Mixed box/minutes sources have16050 positive-minute rows with3PM>FGM. Shot opportunities are not calibration-ready until reconciled. This flag does not prove all minutes/fouls/rebounds false; cross-check specific fields. |
| L4 |32 matched observed2024–25 aggregate shot-zone reference profiles. | Purposeful archetype sample, not league census or current2025–26 chart. No movement/catch/contest labels. |
| L5 |Canonical reported height680, wingspan427, mass651; ESPN IDs622. Legacy15 effective traits broadly populated. | Populated does not prove measured tools/date. No inspected standing-reach or acceleration/jump/conditioning trials. Old ratings cannot be renamed as pure technique. |
| L6 |All11 retained episode text intervals reviewed; cross-video index/notebook and user-corrected identities retained. | Transcript-only limits, conflicting claims, caption ambiguities and post-start EP10 stay visible. Expert judgments remain legitimate evidence. |
| L7 |Public BBI dictionary/access documentation and four2019–20 demo rows;114 planned requests across13 groups. | **Zero acquired current2025–26/2024–25 BBI player rows.** Paid feasibility/export/denominators unverified. Historical demo is not last season. |
| L8 |60 real2026 prospect cache records with college/international stats/physicals/scouting. | Not NBA observations; rankings are not skills. Same approved input definitions, uncertain competition conversion. |
| L9 |Official2025–26 matched shot-zone cache contains **0 profiles**; tracking registry describes intended sources. | Fitted `shot_chart_model` and runtime fallbacks are estimates, not an additional observed dataset. |

Selected L1 nonmissing counts among canonical matches: FT%504; close-shot efficiency505; blocks%507; deflections505; OREB%506/DREB%507; touches278; passes made/received505; ball-handler usage286; off-screen usage173; cut usage312; post usage131; roll-man usage249; transition usage326. Provider aggregate defended-position shares are present for403 players. They may describe deployment, but have no retained opponent-ID pairing, denominator or uniform games-through date. They are not evidence that assignments succeeded. `PF` is a foul-rate-like field; `PF%`/`dPFpct` are positional context and must not be confused with fouls.

## Evidence-to-input contract

1. **Observed/aggregated metrics:** retain makes, attempts, totals, rates and their actual window/denominator. They constrain what happened; they rarely isolate a technique.
2. **Effective provider/model estimates:** keep the provider model, skill/context definition and shared-component lineage. A grade that includes reach, movement, role or impact cannot simply become a technique-only skill.
3. **Technique/recognition inference:** estimate the approved raw dimension with explicit uncertainty, conditioning on tools/opportunity where support exists. If separation is not identified, retain the effective observation as a derived-capability constraint and a broad, separately labeled raw prior. Do not pretend that choosing a number solves identification.
4. **Physical reports/inferences:** preserve inches/pounds and source/date. Estimated standing reach is not a measurement; height/span/reach are not three independent bonuses. Without-ball COD is P07, not dribble control or effective navigation.
5. **Tendencies:** observed behavior is influenced by assignments/opportunities. Estimate preferences conditionally with uncertainty; do not turn usage, rebound totals or defensive events into innate willingness or effort.

Shared estimates are allowed and useful. Distinct fields can initially have similar means and correlated uncertainty, with different definitions and residual evidence. They remain separate approved inputs; they are not silently merged, independently "measured" or given multiple full bonuses. For passing, a short-roll skip combines context/route non-additively; recognition and execution have separate priors and evidence, even when the same broad passing data informs both.

## Complete input index

The JSON is the detailed per-input ledger. Numbers in parentheses below are **populated source fields across canonical matches**, not independently identified technique counts. L7 means prospective BBI evidence only; L6 permits explicit scouting plus clearly reasoned implications for every relevant field.

### 46 non-passing skill dimensions

| Design ID | Approved input | Current evidence handle | Estimation / gap |
|---|---|---|---|
| S01 | Catch-and-shoot three-point execution | 3P%(504); 3PAp75(508); L2 totals539 | no retained current catch-only shot sample |
| S02 | Pull-up three-point execution | 3P%(504); PrbhPPP(286); L2 totals539 | no retained current pull-up-specific sample |
| S03 | Movement three-point execution | OffScreenPPP(173); HandoffPPP(226); L2 totals539 | no conditional movement-three shot table |
| S04 | Catch-and-shoot midrange execution | FG%(504); SpotUpPPP(359); L2 totals539 | no current catch-midrange split |
| S05 | Pull-up midrange execution | PrbhPPP(286); IsoPPP(240); L2 totals539 | no current midrange pull-up sample |
| S06 | Movement midrange execution | OffScreenPPP(173); HandoffPPP(226); L2 totals539 | no movement-midrange-specific measurement |
| S07 | Free-throw execution | FT%(504); FTM(509); L2 totals539 | technique mechanics not isolated, near-direct conversion evidence available |
| S08 | Release / preparation technique | L6 scouting / uncertain prior | no timed release observations, old release_speed is inferred effective proxy |
| S09 | Distance-extension technique | 3PAp75(508); 3P%(504); L2 totals539 | no mechanics-preservation or current deep-shot curve |
| S10 | Layup / close-touch execution | LT_06_PCT(505); FG%(504); L2 totals539 | rim aggregate does not independently isolate layup touch |
| S11 | Floater / short-paint touch | LT_06_PCT(505); PrbhPPP(286); L2 totals539 | no retained floater-specific sample |
| S12 | Dunk execution | LT_06_PCT(505); PnrrPPP(216); L2 totals539 | no current dunk-tagged attempts, close FG not dunk technique |
| S13 | Aerial catch-to-finish execution | PnrrPPP(216); LT_06_PCT(505) | no aerial receive-to-finish player table |
| S14 | Receiving / catch control | PASSES_RECEIVED(505); cTOVpct(481) | received-pass counts do not report catch failures |
| S15 | Contact finishing technique | FTr(484); LT_06_PCT(505); L2 totals539 | and-one rate covers only fouled2pt subset, not isolated technique |
| S16 | Dribble manipulation | boxCreationEst(488); PrbhPPP(286); L2 totals539 | no move-tagged dribble-control sample |
| S17 | Handle security | cTOVpct(481); TOVpct(505); L2 totals539 | aggregate turnover rates do not identify pressure security alone |
| S18 | Perimeter separation craft | IsoPPP(240); PrbhPPP(286) | no footwork/deception-only success sample |
| S19 | Driving craft | FTr(484); Prbh%(286); L2 totals539 | no lane/pace/hip-use technique coding |
| S20 | Attack recognition | BBallIQ(444); passerRating(488); L2 totals539 | generic IQ is not a direct shoot-drive-reset recognition measure |
| S21 | Post establishment / sealing | Post%(131); PostPPP(131) | no seal-specific opportunities or success |
| S22 | Post moves / counters | PostPPP(131); IsoPPP(240) | post scoring does not identify move/counter technique alone |
| S23 | Post-specific finish execution | PostPPP(131); LT_06_PCT(505) | no post-specific release outcome split |
| S24 | Foul-drawing craft | FTr(484); FTA(509); L2 totals539 | foul rate is not pure craft or universal whistle guarantee |
| S25 | Cutting-route execution | Cut%(312); CutPPP(312) | cut scoring/frequency do not isolate timing/deception |
| S26 | Relocation / shooting-route execution | OffScreen%(173); OffScreenPPP(173) | no direct route technique coding |
| S27 | Screen execution | Pnrr%(249); PnrrPPP(216) | screen assists combine technique and teammates, model not technique-only |
| S28 | Screen-action recognition | Pnrr%(249); PnrrPPP(216) | no hold-rescreen-slip-roll-pop read sample |
| S29 | Offensive rebound reading / pursuit technique | ORBpct(506); ORBp75(508); L2 totals539 | rebound counts/model include tools and pursuit opportunity |
| S30 | Defensive rebound reading / positioning | DRBpct(507); DRBp75(508); L2 totals539 | no isolated defensive trajectory-reading sample |
| S31 | Box-out technique | ORBpct(506); DRBpct(507) | no current box-out tagged observations |
| S32 | Rebound control | ORBpct(506); DRBpct(507); L2 totals539 | aggregate rebounds do not isolate ball-control technique |
| S33 | On-ball containment technique | VersatilityRating(454); STLpct(507) | events/assignment balance are not direct stance/angle technique |
| S34 | Contact resistance / leverage technique | L6 scouting / uncertain prior | no contact-resistance technique measurement |
| S35 | Screen-navigation technique | DEFLECTIONS(505); VersatilityRating(454) | legacy navigation is recycled event/impact proxy, not independent technique |
| S36 | Interior positioning | BLKpct(507); MatchupDifficulty(454) | no interior positioning-only sample or standalone verified technical grade |
| S37 | Contest technique | BLKpct(507); BLKp75(508); L2 totals539 | blocks and old rim score are effective outcomes, not pure contest technique |
| S38 | Rotation recognition | BBallIQ(444); DEFLECTIONS(505) | generic IQ/offense or team impact cannot identify rotation recognition alone |
| S39 | Off-ball coverage positioning | dCpct(403); dPFpct(403) | position mix not coverage execution, no spatial event table |
| S40 | Closeout / arrival control | L6 scouting / uncertain prior | contest count does not identify controlled arrival |
| S41 | Defensive anticipation | DEFLECTIONS(505); STLpct(507); L2 totals539 | steals/deflections overlap execution and selection |
| S42 | On-ball steal technique | STLpct(507); STLp75(508); L2 totals539 | no steal-attempt or on-ball vs lane split locally |
| S43 | Passing-lane interception technique | DEFLECTIONS(505); STLpct(507); L2 totals539 | no interception-specific opportunities locally |
| S44 | Attention / responsibility execution | L6 scouting / uncertain prior | no attention/responsibility error table, minutes do not measure attention |
| S45 | Foul-control technique | PF(509); rPF(505) | foul rates do not independently identify technique, mixed game logs require QA |
| S46 | Defensive communication | L6 scouting / uncertain prior | no verified communication events, requires explicit scouting not leadership reputation |

### 18 separate passing dimensions

| Design ID | Approved input | Current evidence handle | Estimation / gap |
|---|---|---|---|
| F01.recognition | Connector / swing / reversal — recognition | passerRating(488); ASTp75(508); L2 totals539 | Recognizing this window, not risk appetite; shared recognition prior + context residual. |
| F01.execution | Connector / swing / reversal — execution | passerRating(488); ASTp75(508); L2 totals539 | Placing this delivery, not noticing window; shared execution prior + context residual. |
| F02.recognition | Post entry — recognition | passerRating(488); ASTp75(508); L2 totals539 | Recognizing this window, not risk appetite; shared recognition prior + context residual. |
| F02.execution | Post entry — execution | passerRating(488); ASTp75(508); L2 totals539 | Placing this delivery, not noticing window; shared execution prior + context residual. |
| F03.recognition | Pocket / roll feed — recognition | passerRating(488); ASTp75(508); L2 totals539 | Recognizing this window, not risk appetite; shared recognition prior + context residual. |
| F03.execution | Pocket / roll feed — execution | passerRating(488); ASTp75(508); L2 totals539 | Placing this delivery, not noticing window; shared execution prior + context residual. |
| F04.recognition | Lob — recognition | passerRating(488); ASTp75(508); L2 totals539 | Recognizing this window, not risk appetite; shared recognition prior + context residual. |
| F04.execution | Lob — execution | passerRating(488); ASTp75(508); L2 totals539 | Placing this delivery, not noticing window; shared execution prior + context residual. |
| F05.recognition | Short-roll playmaking — recognition | passerRating(488); ASTp75(508); L2 totals539 | Recognizing this window, not risk appetite; shared recognition prior + context residual. |
| F05.execution | Short-roll playmaking — execution | passerRating(488); ASTp75(508); L2 totals539 | Placing this delivery, not noticing window; shared execution prior + context residual. |
| F06.recognition | Drive-and-kick — recognition | passerRating(488); ASTp75(508); L2 totals539 | Recognizing this window, not risk appetite; shared recognition prior + context residual. |
| F06.execution | Drive-and-kick — execution | passerRating(488); ASTp75(508); L2 totals539 | Placing this delivery, not noticing window; shared execution prior + context residual. |
| F07.recognition | Skip / cross-court — recognition | passerRating(488); ASTp75(508); L2 totals539 | Recognizing this window, not risk appetite; shared recognition prior + context residual. |
| F07.execution | Skip / cross-court — execution | passerRating(488); ASTp75(508); L2 totals539 | Placing this delivery, not noticing window; shared execution prior + context residual. |
| F08.recognition | Post playmaking — recognition | passerRating(488); ASTp75(508); L2 totals539 | Recognizing this window, not risk appetite; shared recognition prior + context residual. |
| F08.execution | Post playmaking — execution | passerRating(488); ASTp75(508); L2 totals539 | Placing this delivery, not noticing window; shared execution prior + context residual. |
| F09.recognition | Transition / outlet / advance — recognition | passerRating(488); ASTp75(508); L2 totals539 | Recognizing this window, not risk appetite; shared recognition prior + context residual. |
| F09.execution | Transition / outlet / advance — execution | passerRating(488); ASTp75(508); L2 totals539 | Placing this delivery, not noticing window; shared execution prior + context residual. |

### 12 physical families

| Design ID | Approved input | Current evidence handle | Estimation / gap |
|---|---|---|---|
| P01 | Height | height_inches(680) | reported listed height, variable footwear/source conventions; not verified standing measurement |
| P02 | Wingspan | wingspan_inches(427) | reported span; row measurement provenance/age not uniformly retained |
| P03 | Standing reach | L6 scouting / uncertain prior | no retained standing reach; infer from anthropometrics only with explicit uncertainty, never add height/span again |
| P04 | Body mass | weight_lbs(651) | listed body mass/date may be stale; not functional strength |
| P05 | Acceleration / first step | L6 scouting / uncertain prior | no without-ball acceleration trial; drive success includes craft and spacing |
| P06 | Straight-line speed | L6 scouting / uncertain prior | no sprint test; movement-distance/speed ratings are role-relative workload/effectiveness |
| P07 | Lateral mobility / change of direction | L6 scouting / uncertain prior | legacy lateral score is event/impact proxy; no direct movement-capacity measurement |
| P08 | Functional strength | L6 scouting / uncertain prior | mass/contact outcomes do not independently measure functional strength |
| P09 | Physical balance / stability | L6 scouting / uncertain prior | no physical-balance trial; craft and moving-shot outcomes confounded |
| P10 | Vertical / jump capacity | L6 scouting / uncertain prior | no retained vertical test; blocks/dunks contain timing/reach/opportunity |
| P11 | Conditioning | L6 scouting / uncertain prior | minutes/offensive role and availability are not intrinsic conditioning |
| P12 | Recovery between efforts | L6 scouting / uncertain prior | no repeated-effort/rest recovery series; not medical injury recovery |

### 18 tendency families

| Design ID | Approved input | Current evidence handle | Estimation / gap |
|---|---|---|---|
| T01 | Shoot / drive / pass / post / reset choices | Prbh%(286); Iso%(240) | coach/teammate/opponent opportunity; reset events absent |
| T02 | Shot-location preferences | 3PAr(473); LT_06_%(499); L4 zones32 | 32-player sample and prior season; geometry/access and coach system |
| T03 | Shooting-mode preferences | OffScreen%(173); Handoff%(226) | labels overlap; no retained catch/pullup split |
| T04 | Shot difficulty tolerance | SQ(470) | defender difficulty and late-clock need, not bad judgment automatically |
| T05 | Pace / early-attack preference | Transition%(326); TransitionPPP(326) | team pace and turnover opportunities confound preference |
| T06 | Dribble / possession persistence | touches(278); PASSES_MADE(505) | role, assignment and available creators; counts not possession persistence |
| T07 | Passing risk appetite | cTOVpct(481); passerRating(488) | recognition, execution and teammate routes confound turnover risk |
| T08 | Offensive involvement preference | USGpct(508); touches(278) | coach workload and teammates, not intrinsic selfishness |
| T09 | Cutting frequency | Cut%(312) | play design, spacing and receiving supply |
| T10 | Relocation / off-ball movement frequency | OffScreen%(173); Handoff%(226) | coach system and capacity; movement rating not intrinsic preference |
| T11 | Screen / roll / pop / slip preferences | Pnrr%(249); PnrrPPP(216) | skills/shooting, coach calls and teammates; missing follow-up mix |
| T12 | Offensive crash versus retreat | ORBpct(506); ORBp75(508) | team crash instruction, tools and box-out opportunity; OREB results not preference |
| T13 | Defensive pursuit versus box-out emphasis | DRBpct(507); DRBp75(508) | team collection assignments and tool advantages; no boxout attempts |
| T14 | Steal / disruption gamble frequency | STLpct(507); DEFLECTIONS(505) | good execution/anticipation and scheme; high steals not gambling proof |
| T15 | Help commitment | dCpct(403); dPFpct(403) | starting position and coach responsibility; assignment shares not help willingness |
| T16 | Contest commitment / stay-down preference | BLKpct(507); PF(509) | reach/timing/difficulty; block or foul rate not pure commitment |
| T17 | Effort allocation | DEFLECTIONS(505); minutes(526) | conditioning, health, instructions; offensive usage not defensive laziness |
| T18 | Contact-seeking preference | FTr(484); FTA(509) | foul craft, strength, drives and defender behavior |

## Efficient whole-league population method

**First join and quality-tag existing data.** Use stable canonical/ESPN IDs where available, preserve raw names and team-season/stint context, then review ambiguous/name-only cases. Keep season totals separate from stints and regular season separate from playoffs. Do not equate the679-profile cache,526 skill rows and691 players. Roster controls include guards/wings/bigs, stars/low-minute players, rookies, free agents and no-NBA-history prospects; do not use a position label as a hard skill cap.

**Then build shared family estimators without collapsing approved dimensions.** Broad shooting/creation/rebound/defense/passing estimators give common baselines and source covariance. Skill-specific observation and scouting residuals differentiate approved fields. FT makes/attempts provide a comparatively direct sampled conversion constraint for S07; catch/pullup/movement splits require conditional data or explicit uncertain priors. A global three-point percentage is not three independently measured shot skills. A total passer grade is not18 independently measured passing talents.

**Separate tools, technique and preferences jointly.** For S36/S37, keep observed contest outcomes and spatial opportunity as constraints on C27 while making any raw decomposition explicit. Estimated reach or jump must carry its own uncertainty, not magically turn residual blocks into measured timing. For P05–P12, broad provisional tool priors are more honest than copying the old event/impact-based lateral or minutes-based stamina. For tendencies, infer conditional distributions where opportunities are known; use source/scouting-led priors elsewhere, keeping coach orders separate.

**Use trusted scouting for actual calibration, not merely footnotes.** Preserve explicit claims, labeled reasonable implications, reasons, disagreements and numerical-judgment provenance. They can support a directional change or a useful range without impossible causal measurement. A forecast remains a forecast; ambiguous captions can hold the narrow claim while clear surrounding assessments remain usable. Existing corrected identities—Devin Vel=Devin Vassell; Owe Dunu=Ayo Dosunmu—and corrected Durant/Kawhi attribution stay resolved. No new stable panelist identities are introduced.

**Review exceptions and strata, not94 inputs×691 players by hand.** Prioritize contradictory outcomes, inferred ceilings, unusual physical profiles, explicit scouting conflicts and sparse samples. A versioned shared rule handles most players; targeted expert residuals handle supported exceptions. Preserve every approved dimension for uncertain players rather than declaring it absent or zero. Generated prospects use the same meanings, with competition/age and no-NBA-observation uncertainty; rank and projected growth are not current ability.

**Attach uncertainty and reason codes at every stage.** Report source population and denominators separately from posterior precision. Similar means with shared evidence must not masquerade as independent confidence. Leave data gaps explicit; a prior is an estimate, not failed schema coverage. Grade anchors remain fixed reference judgments, not annual min/max, percentile-to-OVR or "best current player=100."

**Preserve the approved downstream catalogue.** The JSON references all37 C objects and22 R outputs. R01–R13 offensive jobs draw on the relevant split skills/tools/preferences; R14–R20 defensive jobs use the interior/perimeter/help/rebound contrasts. R21/R22 are reference contribution/summaries. They are not new editable raw talents or bonus layers. No formulas/weights or role scores were validated here, and no separate recovery ratings were added. A communication or box-out field being sparse does not permit deletion.

## What is ready, provisional and still missing

| Status | Completed / remaining |
|---|---|
| **Completed evidence coverage** |94 unique input definitions and source/inference/gap entries;18 passing entries; roster-wide source counts;37 derived/22 output references;12-player interior source packet. |
| **Provisional estimates** |8 scouting-supported raw technique ranges in the separate packet. Broad/shared league estimators are specified as a method, not secretly run or installed. |
| **Not independently identified** |Most technique/tool decompositions, latent opportunity-conditioned preferences, all18 context-specific passing pairs, standing reach/testing and communication/attention events. All approved entries remain required. |
| **Actual access gap** |Current BBI rows/paid feasibility/export/sample metadata not verified. The local milestone is complete without them. |
| **Data-quality gap** |Mixed game-log shot counts must be reconciled before using them as attempted-shot denominators; current official zone cache empty. |
| **Backend-owned next work** |Canonical keys, storage/serialization, verified dependency formulas, complete C27→spatial→role→game consumer chain and integration validation. None is claimed complete by a research ledger. |

## Small human queue / next evidence

If BBI access is chosen, the smallest useful interior feasibility sample is the12 packet players in completed2025–26 and2024–25, season-total versus stint distinguished, with the listed contest/help/opportunity fields, minutes and any event counts/units/as-of/filter metadata. No purchase, credentials or paid access is requested/performed here. [Existing acquisition plan](BBI_ACQUISITION_PLAN_2026_11_11.md) then expands to broad league coverage, not a permanent12-player study. BBI can improve effective contest/help/work estimates; it cannot independently measure pure timing versus reach/jump, communication, intrinsic conditioning or all18 passing pairs.

No human answer blocks this completed milestone. A permitted sample, if the user later obtains it, is the one grouped useful request. Missing standing reach and technique detail remain explicit priors/uncertainty rather than a demand for impossible measurements or a reason to stop schema work.

Durable evidence: [coverage JSON](PLAYER_MODEL_EVIDENCE_COVERAGE_2026_11_12.json), [source inventory](probe_artifacts/player_model_source_inventory_20261112.json), [cohort snapshot](probe_artifacts/interior_cohort_source_snapshot_20261112.json), [interior packet](INTERIOR_DEFENSE_CALIBRATION_PACKET_2026_11_12.md), [cross-video index](CROSS_VIDEO_CLAIM_INDEX.md), [coverage ledger](FULL_EPISODE_COVERAGE_LEDGER.md), [cumulative notebook](RESEARCH_NOTEBOOK.md), [BBI plan](BBI_ACQUISITION_PLAN_2026_11_11.md). Original source records and earlier findings remain intact.

## Milestone2 resolution — November13

[Experimental packet](INTERIOR_DEFENSE_EXPERIMENT_INPUTS_2026_11_13.md)/JSON now uses actual registry IDs and accepted schema shapes:12 players,372 relevant records,36 reported-tool estimates,8 scout estimates and328 explicit unknowns;8 separately synthetic scenario sections and7 contexts. These support introductory default-OFF mechanism exploration, not final player/rank/league calibration before new offense/spacing/other defense exist.

[Historical shooting QA](HISTORICAL_SHOOTING_DATA_QA_2026_11_13.md) resolves the original16050-row flag: all cached player FGM/FGA are false zeros because the parser omits ESPN's long FG key. Three representative source games validate70 shooting rows and ending-year/phase semantics; no global2PM reinterpretation or join error demonstrated. Research-only conditional totalFGM recovery covers34216 rows; FGA remains unknown outside direct samples. Seven final-team discrepancies and nonfinal records stay quarantined. Original cache/canonical/source records are unchanged; imported history is distinct from generated boxes.


## Offensive/interior interaction research — November 13 delivered

[OFFENSE_INTERIOR_INTERACTION_INPUTS_2026_11_13.md](OFFENSE_INTERIOR_INTERACTION_INPUTS_2026_11_13.md) and matching JSON cover twelve contrasts across shooting modes, spacing, floaters, contact finishing and creator-dependent roll/lob opportunities. Actual-schema source section plus eleven separate experimental sections pass pure validation; twelve source documents round-trip.420 explicit records:36 reported-tool conversions,20 low-confidence scouting technique midpoints/ranges,12 separately scaled FT conversion proxies,352 unknowns. Other59 approved inputs/player remain unknown by omission; all94 model distinctions remain intact.

Twenty-three career player-seasons match retained raw FG/3P/FT totals and scoring identities; Harper's prior NBA row is expected absent. Combined totals and stints are not double-counted. Historical damaged FGA is never a denominator. Source preferences remain unknown; realized volume does not become latent willingness. No timed release, deep-mechanics curve, dunk-specific, aerial-catch/drop or measured reach protocol is invented. Scouting claims are reused, dated and correlated where shared; this is not fresh audiovisual review or material-event reconciliation. October pre-opener target is settled, forecasts and post-start evidence stay separate.

One bounded Chicago source check retains a team/player two-point discrepancy. Corrected coverage is nine identified playing rows, two DNP rows and one unidentified zero-stat row, not twelve verified joins. Upstream cause/attribution remains unknown; other six exceptions remain quarantined. Backend owns repair. No production/data/saves/registry/architecture writes or games/simulations; no broad acquisition. Whole-model calibration waits for connected offense/defense, passing/creation, coaching/deployment and downstream AI/development validation. Research stops at this handoff.


## Creation/passing/containment/help milestone4 — November13 delivered

[CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.md](CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.md) and matching JSON supply12 contrasted players: Luka, SGA, Brunson, Cade, Garland, Harper, Bane, Castle, White, Barnes, Gobert and Bam.109 priority estimates across22 input IDs comprise108 technique/recognition ranges and one descriptor-only physical estimate (105 newly populated cells and four reaffirmed prior ranges); all have provenance, explicit-commentary versus inference separation, uncertainty and counterevidence.53 prior source records are reused before selective overrides; no prior synthetic completed profiles are imported as player facts. All94 approved inputs/player, including18 passing fields, are explicit:1128 source records,164 estimated,964 unknown. Source plus17 synthetic one-actor sections pass actual schema validation;12 source documents round-trip.

Useful contrasts: Harper's explicit security versus advanced-read development; Castle's POA strength versus weaker help/off-ball/foul-control evidence; White/Barnes help recognition versus pressure/arrival uncertainty; Bane's shooting versus pressure separation limits; SGA/Brunson suppression versus Cade/Castle total-loss concerns; Gobert's creator-dependent finishing versus Bam's switching. Source totals cannot type handling/pass/offensive-foul losses. Cade/Harper recognition/delivery offsets are overlapping causal hypotheses, not proved dissociations. Luka/Garland S17 and all source F07 values remain unknown where specific evidence is insufficient; F07 is preserved, not merged or deleted.

Twenty-three career player-seasons of assists/turnovers/points match retained raw totals; all-personal-foul counts are retained without mislabeling offensive fouls. Twelve mixed-window touch/pass/provider records are preserved as stored, with unknown per-field exposure/filter, not joined to completed-season totals. No fabricated pressure-loss rates, motion timings or offensive-foul subtypes. Synthetic controls independently vary recognition/delivery, security, help reading/movement, receiver reliability and risk appetite. Screen routes/roll availability remain declared context. Prioritized queue: typed pressure losses, tagged available-read/delivery samples, help-responsibility clips, and existing exposure definitions/windows. No subscription or mandatory questionnaire.

October pre-opener policy remains settled. No new transcript acquisition, audiovisual review, network request, production/code/data/save/architecture/coordinator edit or game simulation. Seven historical exceptions remain quarantined and outside this pass. Whole-model calibration awaits connected offense/defense, passing/creation, coaching/deployment and downstream AI/development validation. Research stops at this bounded implementation-support handoff.
