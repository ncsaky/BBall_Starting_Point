# Interior-defense experimental inputs — November 13, 2026

**Milestone2 delivered: a versioned, schema-accepted12-player input packet plus separate synthetic scenarios. This is introductory mechanism evidence, not final ratings, role rankings or league calibration.** The full approved model still requires64 skills,12 physical families and18 tendencies. The new offense, spacing and remaining defense are not implemented together yet; no one-family result can calibrate the complete player model.

The [packet JSON](INTERIOR_DEFENSE_EXPERIMENT_INPUTS_2026_11_13.json) uses actual registry IDs and versions. Its `player_input_section` is the strict schema section; the surrounding object is research metadata, not a save. The [standalone source section](diagnostics/milestone2_20261113/source_player_input_section.json) is directly consumable by `validate_input_section`. No section was attached to a save or production player.

## Validation and exact coverage

The actual `PlayerInputs` and `validate_input_section` utilities accept the source section and **all8 scenario sections**. All12 source player documents round-trip exactly. [Validation evidence](diagnostics/milestone2_20261113/input_validation.json) records utility/registry hashes and versions: `player_performance_inputs_v1` / `player_performance_registry_v1`.

| Item | Count / status |
|---|---|
| Cohort |12, unchanged from milestone1; canonical IDs retained|
| Relevant explicit design IDs per source player |31|
| Source-section records |372|
| Converted physical reports |36: P01/P02/P04 for each player|
| Scouting-supported technique estimates |8 representative midpoints, with original ranges/provenance|
| Explicit unknowns |328|
| Other approved inputs |63 per player omitted as unknown under the sparse schema, not deleted|
| Synthetic input scenarios / cross-context conditions |8 /7|
| Schema sections accepted |9: source plus8 scenarios|

Validation establishes the storage/units/provenance contract only. It does not validate physics, response coefficients, player accuracy, downstream consumers or experiment outcomes. No game simulations, engine tests or long downloads ran.

## Source values versus exploratory assumptions

**Reported physical tools:** existing height/span in inches become cm by×2.54; listed mass in pounds becomes kg by×0.45359237. The records are `estimated`, confidence medium, with original units/source and unverified measurement/footwear/date explicitly noted. Conversion precision is not anthropometric measurement precision. These are sourced reports, not new standing-height or span tests.

**Scouting-supported technique:** the eight milestone1 ranges are retained. The strict grade container stores a representative midpoint; range endpoints remain in `scouting_ranges` and uncertainty notes. All are low-confidence isolated decompositions, not statistically identified pure technique or measured percentages. Their scale ID is `research_technique_reference_v0_2026_11_13`, not an adopted production scale.

| Player | Design ID | Range / representative midpoint |
|---|---|---|
|Gobert|S36 interior positioning|86–96 /91|
|Zubac|S36 interior positioning|76–90 /83|
|Wembanyama|S37 contest technique|80–94 /87|
|White|S37 contest technique|78–92 /85|
|White|S38 rotation recognition|80–92 /86|
|Barnes|S38 rotation recognition|78–92 /85|
|Castle|S38 rotation recognition|55–75 /65|
|Bam|S33 containment technique|78–92 /85|

Their timestamped source assessments, reasoned implications and counterevidence are in the [milestone1 packet](INTERIOR_DEFENSE_CALIBRATION_PACKET_2026_11_12.md). Midpoints are convenient representative values for exploration, not evidence more precise than the ranges. Guard timing can overlap big-man timing; effective rim coverage still depends on reach, jump, arrival and opportunity. No old rim100, generic IQ or effort rating is copied into these new skills.

**Unknown facts remain unknown in the source section:** P03 and P05–P12 have no supported physical-unit player observations supplied here. Most S36/S37/S38 and all relevant S39/S40/S41/S44/S45/S46 and tendency records remain unknown unless one of the eight ranges applies. That does not erase any approved input. S30–S35 remain relevant rebound/contact/navigation support with no new narrow player estimates. Conditioning is not inferred from minutes, and offensive workload is not a defensive-laziness label.

## Minimum missing inputs and safe experimental substitutes

| Mechanism | Approved inputs to keep visible | What remains missing | Allowed exploration route |
|---|---|---|---|
| Position/contest C27 |S36/S37/S45; P01–P03/P05/P08–P10; T16|Standing reach, jump/movement/contact protocols, many isolated technical estimates, contest-choice probabilities|Explicit synthetic geometry/tools and broad technical/policy assumptions, with independent axes. Do not label these measurements.|
| Help/arrival C26 |S38–S41/S44/S46; P02/P03/P05–P07/P09; T15|Recognition-delay, route/start-position, controlled-arrival, communication and help-choice observations|Declare starting responsibility and forced delay separately; vary technique and motion independently. A late arrival need not mean poor movement.|
| Legal/foul choice |S45 plus T16, attacker threat and actual contest opportunity|Comparable legal contests, tactical-foul exclusions and individual jump/stay-down choice samples|Hold technique fixed while varying synthetic T16; then vary S45 separately. No foul-rate-to-technique shortcut.|
| Possession/work support |S30–S35; P04/P11/P12; T13/T17|Box-out/collection opportunities, conditioning and rest response, workload preference|Fresh reference state and explicit support assumptions; no invented physiological observation or fatigue calibration.|

The packet does not demand perfect data before mechanisms can run. It provides complete, nonmissing **scenario** records for the31 relevant IDs. These are controlled fixtures, distinct from evidence-filled player documents. Any consumer must declare how it interprets the recorded metric/protocol; schema acceptance does not make arbitrary protocol values interchangeable.

## Eight versioned scenario sections

| Scenario ID | Changes / intended use |
|---|---|
|`reference_assumptions_v1`|Keeps reported P01/P02/P04 and8 scout midpoints. Missing technique uses common70; missing preferences use declared reference distributions. These are generic test assumptions, not player priors.|
|`equal_geometry_control_v1`|Normalizes height/span/reach/mass across the cohort to isolate technique hypotheses from geometry. Not a real-world ranking.|
|`low_missing_technique_v1` / `high_missing_technique_v1`|Changes unidentified technique to40/90 while preserving supported entries. Wide sensitivity bounds, not claimed player ranges.|
|`scouting_lower_v1` / `scouting_upper_v1`|Selects the eight stated range endpoints; preserves other common assumptions. Joint bound sensitivity is not a single-variable causal test.|
|`conservative_contest_v1` / `aggressive_contest_v1`|T16 jump/conservative/stay-down mixes .1/.3/.6 versus .7/.2/.1, with other inputs held. Policies are hypothetical, not actual player preferences.|

The reference P03 fixture is **H1: height_cm+70+.5×(span_cm−height_cm)** with a±10cm experimental interval. This is unvalidated anatomical scaffolding, **not an estimated measured reach for these players**. It must not become a production conversion. P10=40cm jump gain and fixed acceleration/speed/contact/balance values are dimensional test controls with explicit synthetic protocols. P11/P12 use separate synthetic display proxies; no VO2, fatigue or rest test is invented. All scenario substitutions are `estimated`, never `observed`.

The packet also names independent axes: S36/S37/S38/S45 at40/70/90; hypothetical P03 delta−10/0/+10cm; P10 at20/40/60cm; synthetic P05 at1.5/3/4.5m/s². A forced-arrival-delay context axis0/.25/.75s is hypothetical, not a measured recognition time. Change one axis at a time when interpreting mechanism direction. No such experiment or game was run by research.

Uniform T13 pursuit/box-out, T15 help and T17 workload reference choices exist only in scenarios. The source section supplies none as facts. If geometry already uses P03/P10, do not add height/span as duplicate coverage bonuses. P01/P02 can retain other separately declared roles, but shared information is counted once.

## Cross-context scouting constraints

These seven conditions are in machine-readable `context_conditions`. They are task environments, not hidden intrinsic talent changes. Exact offensive/spacing coefficients and quantitative player ordering remain unresolved until the complete relevant new mechanisms exist.

| Context | Retained evidence / implication | Constraint on introductory interpretation |
|---|---|---|
|Crowded paint|Centers Sep2,00:17:18–00:38:52: Duren/packed-paint offensive limitations; defensive implication is labeled inference.|Paint occupancy changes opportunity and shot quality. A packed paint is not automatically easy defense against every powerful finisher.|
|Credibly spaced lineup|Centers01:35:07–01:45:37 Wembanyama space limitations;01:06:54–01:13:07 Bam switching contrast.|Open lanes/outlets change help cost and entry attempts. Do not calibrate the anchor around the old offense's fixed shot mix.|
|Strong POA support|PG Aug5,00:18:37–00:22:05 Castle/Wembanyama context.|Fewer contests/blocks can mean less work, not lower ability.|
|Weak POA support|PG01:06:18–01:11:36; team Oct7,03:25:17–03:27:02 Brunson shielding.|More emergency contests may coexist with worse team results. Workload and talent are different.|
|Pulled away from rim|Centers Wembanyama/Bam contrasts above.|Starting assignment can remove an anchor from one drive without changing S36/S37. Mobile coverage and paint-contest ordering need not coincide.|
|Late help|PF Aug28,01:10:00–01:17:38 Barnes; SG Aug14,01:34–01:44 White; Castle PG passage.|Recognition, starting position, physical travel and controlled arrival are separate. No source-derived millisecond values claimed.|
|Different threats|Centers Zubac/Duren00:17:18–00:38:52; Chet/Bam00:59:07–01:13:07.|Quick guard, contact finisher, roller/lob and shooting center impose different demands. No universal cohort ranking under unimplemented new handling/finishing/passing/shooting.|

See the existing [centers](EPISODE_4_CENTERS_EXTRACTION.md), [PG](POINT_GUARDS_FULL_EXTRACTION.md), [PF](POWER_FORWARD_FULL_EXTRACTION.md) and [SG](SHOOTING_GUARDS_TOP_10_FULL_EXTRACTION.md) extractions. No hours of transcript were re-extracted. Explicit expert assessments remain substantive evidence; scenario implications are labeled reasoning, not attributed quotes.

## What is usable now, and what is not

**Usable for exploration:** accepted schema sections, reported-tool contrasts, scouting range endpoints, independent sensitivity axes and declared context conditions. Physical-data gaps do not halt controlled synthetic mechanism work. Preserve default-OFF isolation; this packet authorizes no activation.

**Supported enough to retain for eventual calibration:** reported physical sources with units/provenance; actual regular-season outcomes from the separate career snapshot; explicit scouting strengths/weaknesses and qualified technical ranges. These constrain calibration without proving pure attribution.

**Not final calibration:** the representative midpoints, synthetic reach equation/protocols, common70 techniques, reference choice distributions, capacity proxies or numerical cohort ordering. Any scoring/attempt/block/foul result depends on the still incomplete offense/spacing/other-defense context. Do not tune the whole new model around this family, fit awards/on-off as raw skills, or declare league balance established.

The historical QA diagnosis is separate: [shooting QA](HISTORICAL_SHOOTING_DATA_QA_2026_11_13.md) confirms a missing total-FG alias in imported history, not a generated-box defect. No corrupted game-cache FGM/FGA was used as new technique evidence in this packet.

## One grouped human-input queue

No human answer blocks this delivery or synthetic exploration. If later BBI access is chosen, a permitted sample for these12 players across completed2025–26/2024–25, with contest/help/opportunity fields, units, filters and actual sample counts where exposed, would improve the effective constraints. Any already available trustworthy standing-reach/testing reports can travel with that evidence; collecting perfect physical measurements is not a prerequisite. No purchase, credential request or paid-access claim is made.

Reproduce packet construction/validation using `PYTHONDONTWRITEBYTECODE=1 python3 docs/ratings-evidence-2026-10-29/diagnostics/milestone2_20261113/build_interior_experiment_packet.py`. It calls only pure schema validation/serialization; no save or game APIs. Original source/canonical/registry/architecture records are preserved. All writes are research outputs and diagnostics.
