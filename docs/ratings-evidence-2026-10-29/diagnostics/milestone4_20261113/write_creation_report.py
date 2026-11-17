"""Render the bounded research handoff from its retained packet; no production imports."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[2];d=json.loads((R/'CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.json').read_text());ranges={(x['name'],x['design_id']):x['range'] for x in d['scouting_ranges']}
assert d['counts']['scouting_estimate_records_this_pass']==109 and d['counts']['estimated_source_records']==164 and d['counts']['unknown_source_records']==964, 'Update report counts before rendering changed packet'
def band(name,id):
 v=ranges.get((name,id));return f'{v[0]}–{v[1]}' if v else 'unknown'
text='''# Creation, passing, containment and help inputs — November 13, 2026

This implementation-support packet offers **109 prioritized scouting estimates across twelve players**, rather than another missing-data inventory. They are actionable broad hypotheses for the backend's default-OFF drive/finish, drive-and-kick and pocket/roll/lob experiment. They are not production rating changes or final calibrated response coefficients.

[JSON packet](CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.json) has a full94-input source document for each player, separate recognition/execution fields, dated ranges, direct commentary and labeled implications. It reuses source estimates from earlier offense/interior packets, never their synthetic completed profiles. All **1,128 source records** remain inspectable:164 estimated,964 explicitly unknown. Of the109 priority estimates,105 populate previously unknown cells and four reaffirm prior ranges (Castle/White/Barnes S38, Bam S33). Fifty-three records were inherited before these reaffirmations; this is a lineage count, not an additional independent sample. No earlier supported range was narrowed on the same evidence. There are17 separate synthetic scenario sections, each with one research actor. Together with the source section, all18 sections pass the actual unchanged schema utility and all12 source player documents round-trip exactly.

Versions: `creation_passing_defense_research_v1_2026_11_13`, `player_performance_inputs_v1`, `player_performance_registry_v1`. [Validation](diagnostics/milestone4_20261113/input_validation.json), [exposure checks](diagnostics/milestone4_20261113/exposure_validation.json), [source-only section](diagnostics/milestone4_20261113/source_player_input_section.json) and [offline builder](diagnostics/milestone4_20261113/build_creation_packet.py) are retained. Schema acceptance is storage/arithmetic evidence, not verified causal gameplay or production authorization.

## Evidence date and estimation method

October immediately before the regular season is the settled target. Completed2025–26/2024–25 outcomes and pre-start offseason assessments are eligible under the [October policy](OCTOBER_START_EVIDENCE_POLICY.md), subject to material injury/trade/signing changes. Healthy ability, current restrictions, projected growth and post-start results stay separate. This pass did not re-audit every material event or reacquire transcripts. No post-start game result was added.

All sources below are existing transcript-only reviews. Speaker identities remain unidentified/local turns. The player's direct assessment and this packet's raw-skill implication are separate fields in every estimate. Same-episode repetition and cross-family overlap are correlated evidence, not independent corroboration. Prior official defense recognition/assignment reporting is retained in the [defensive review](DEFENSIVE_ROLE_PLAYER_INPUT_REVIEW_2026_11_11.md), especially its White/Castle/Barnes rows; it supports the broad contrast, not each isolated number, and was not freshly retrieved here.

The provisional technique scale is the prior packet's `research_technique_reference_v0_2026_11_13`:50 functional reference,75 strong,90 exceptional. Midpoints serialize broad judgment ranges, not measured coefficients, percentiles, success probabilities or statistical confidence intervals. Directional profile confidence is generally moderate; isolated magnitude/decomposition confidence is low. Equal recognition/execution ranges mean no supported split, not merged skills. Unequal ranges are explicitly uncertain hypotheses, with overlap and competing causes stated below.

## Human comparison: what each player reads, delivers and creates

Each timestamp is an exact retained extraction window, not a newly isolated action sample. PG=Aug5 [point guards](POINT_GUARDS_FULL_EXTRACTION.md); SG=Aug14 [shooting guards](SHOOTING_GUARDS_TOP_10_FULL_EXTRACTION.md); PF=Aug28 [power forwards](POWER_FORWARD_FULL_EXTRACTION.md); C=Sep2 [centers](EPISODE_4_CENTERS_EXTRACTION.md).

| Player / source window | Notices and delivers | Advantage and pressure response | Counterevidence / confidence boundary |
|---|---|---|---|
| Luka — PG01:27:17–01:37:18 | Explicit every-pass/P&R praise supports broad roll, lob and kick repertoire; family numbers are implications | Manipulation, physical imposition and shot counters create choices | Island coverage can suppress team offense; reduced rim access/health; no separate handle-loss sample, so S17 unknown |
| SGA — PG01:32:08–01:43:34 | Improving passing supports roll/kick competence; read/delivery split not established | Exceptional isolation/P&R drive craft and explicit turnover suppression | Loaded playoff defenses reduced dominance; scoring quality is clearer than route-specific passing |
| Brunson — PG01:06:18–01:17:50 | Strong scoring decisions, but less engine passing than elite peers; simple kick pair inferred | Scoring craft/security supported by volume, clutch work and suppression commentary | Team infrastructure matters; limited passing breadth is not inability to deliver any pass; defensive liability does not prove inattention |
| Cade — PG01:16:54–01:27:17 | High-load creation amid poor spacing supports useful roll/kick reads | Physical/craft advantage creation plus difficult defensive assignment | Turnovers are explicit; lower delivery midpoint is a testable attribution hypothesis, not typed-pass-error evidence; could instead be handling/choice |
| Garland — PG00:10:42–00:12:15;00:22:05–00:29:26 | Explicit passing/P&R supports roll/kick pair | Elite handle/change of pace, quickness and floater/shooting threats | Rim/FT ceiling, health and physical playoff translation; S17 unknown rather than copied from broad handle praise |
| Harper — PG00:29:26–00:39:09 | Stable decisions/security, but advanced reads need development; simple delivery plausibly ahead of breadth | Pace, size, craft and varied paint scoring | Read/delivery split is not directly measured; projection/ceiling excluded; a delivery miss could still explain a given loss |
| Bane — SG00:50–01:00;01:06–01:10 | Secondary passing supports connector pair only | Physical straight-line drive and shooting threat | Pressure/switching/separation limits are explicit; difficult opponents counterweight; no automatic poor S17 or kick-delivery grade |
| Castle — PG00:14:56–00:22:05;00:26:37–00:29:26 | Useful secondary playmaking, limited creation; connector pair broad | Strong downhill play and elite star-guard POA containment | Turnovers, high fouls and weaker off-ball/help dimension; Wembanyama/team help matters; losses not typed |
| White — SG01:34–01:44 | Good decisions/passing/low losses support connector and simple kick pair | Secure continuation and defensive anticipation/positioning/POA pressure | Limited inside self-creation; poor shooting season separate; anticipation does not by itself measure closeout control |
| Barnes — PF01:10–01:17:38 | Elite passing/lead-creator growth supports connector/kick hypotheses | Size/craft, short scoring and POA/help versatility | Inconsistent jumper and lead-scoring ceiling; no automatic elite lob/skip/pocket grid from generic passing praise |
| Gobert — C00:51:38–00:59:07 | No route-specific passer estimate; reliable coverage broadly supports helper-positioning hypotheses | Pass-dependent offensive involvement; creator quality changes opportunities | Offensive limits do not prove poor attack recognition/catch skill; anchor reputation is not elite perimeter containment |
| Bam — C01:06:54–01:13:07 | Playmaking/creator praise supports broad connector pair only | Strong switch containment/contact hypotheses | Inefficient jump-heavy offense and future fit uncertain; switching mixes technique and movement, not direct acceleration evidence |

## Actionable creator and security ranges

S16 manipulation, S17 security, S18 separation craft, S19 driving craft and S20 action recognition stay separate. A shooting make uses its existing shot skill; improved creation must produce an opportunity, not add a second shot-accuracy bonus. Paint access is not finishing conversion. Unsupported cells remain unknown, not ordinary or zero.

| Player | S16 | S17 | S18 | S19 | S20 |
|---|---:|---:|---:|---:|---:|
'''
for c in d['cohort']:
 name=c['name'];text+='| '+name+' | '+' | '.join(band(name,id) for id in ['S16','S17','S18','S19','S20'])+' |\n'
text+='''
Harper's S17 relative to Castle/Cade has explicit security/turnover commentary behind it; these are still broad ranges with unmatched roles/exposures. Cade/Castle S17 is a **conditional hypothesis**: high total turnovers could instead reflect passing, offensive fouls, workload or decisions. Do not use both the inferred security reduction and a second blanket turnover penalty derived from the same total. Luka/Garland handle repertoire alone does not establish security; their S17 stays unknown. Gobert's S20 remains unknown because limited skills and weak reads are different possible causes of limited offense.

## Passing pairs: reads are not deliveries

Each cell below is **recognition range / execution range**. F01 connector is an explicit supporting family for Bane/White/Barnes/Bam/Castle; it does not substitute for the requested F03 roll, F04 lob, F06 kick or F07 cross-court fields. Both fields of every approved F family remain in storage, even when unknown.

| Player | F01 connector | F03 roll | F04 lob | F06 kick | F07 cross-court |
|---|---|---|---|---|---|
'''
for c in d['cohort']:
 name=c['name'];cells=[]
 for f in ['F01','F03','F04','F06','F07']:
  a=band(name,f+'.recognition');b=band(name,f+'.execution');cells.append('unknown' if a==b=='unknown' else a+' / '+b)
 text+='| '+name+' | '+' | '.join(cells)+' |\n'
text+='''
Luka's broad every-pass assessment supports repertoire breadth but not a distinct cross-court read/delivery comparison; F07 remains unknown for every source player. The synthetic skip route can still be tested without claiming a researched player estimate. His wider/lower lob delivery ranges express missing route-specific precision evidence, not a verified delivery defect. Garland's explicit P&R/passing praise supports F03/F06, but no specific lob evidence is supplied. Harper's lower read than delivery midpoint follows explicit advanced-read development versus stable simpler execution; overlapping ranges reflect that the split remains unverified. Cade's lower delivery midpoint is even less identified: it is a hypothesis to vary against alternative handling/read explanations, not a causal finding. Equal SGA/Brunson pairs are intentional because no isolated split is supported.

Barnes' elite passing supports a restricted connector/kick decomposition with wide uncertainty; slight offsets are estimation judgments, not recorded misdeliveries. Generic Bam playmaking is not enough to populate every P&R/lob family. F05 short-roll skill remains unknown in this packet; possession in a supplied short-roll location does not prove its reads. No assist or turnover aggregate is mechanically converted into any of these grades.

## Containment and help ranges

Physical movement, containment technique, recognition, starting position, controlled arrival and attention are distinct. The following ranges concern technique/recognition hypotheses constrained by effective scouting evidence. Their physical/context separation remains incomplete; do not count observed switching success once as S33 and again as a fully identified physical tool.

| Player | S33 contain | S34 contact | S38 rotation | S39 off-ball position | S40 arrival | S41 anticipate | S44 attention | S45 foul control |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
'''
for c in d['cohort']:
 name=c['name'];text+='| '+name+' | '+' | '.join(band(name,id) for id in ['S33','S34','S38','S39','S40','S41','S44','S45'])+' |\n'
text+='''
Castle versus White/Barnes is the clearest supported contrast: strong POA containment is not equivalent to early/off-ball help. Castle's S39/S44 split is weakly identified: poor off-ball outcomes could reflect recognition, responsibility attention, positioning or scheme. Those broad estimates share the same evidence and must be varied separately before blaming one mechanism. His S45 concern follows explicit foul criticism, but the source does not classify tactical, offensive or assignment-driven fouls. Do not multiply penalties across all four fields as if four independent flaws were observed.

White S40 is an especially tentative implication from positioning/pressure, not an observed closeout-control sample. Gobert S38/S39 is a broad coverage-awareness hypothesis, not a claim he is an elite perimeter helper in every starting position. S41 hands/anticipation and S38 rotations overlap, so they must enter distinct causal steps without complete duplicate bonuses. S44 is responsibility awareness, not personality, voluntary effort or a generic IQ score. Blocks, height, steals and offensive usage independently prove none of these inputs.

## Tools, tendencies and observed exposure

Reported height/span/mass retain cm/kg conversions and unknown original protocols. Garland P05 adds one **descriptor-only** broad80–94 healthy-quickness estimate using a distinct physical-descriptor scale; it has no measured m/s²/time. Backend must require an explicit response mapping or leave its quantitative acceleration unknown. It is partly effective evidence shared with handle/change-of-pace, so adding a complete physical and dribble bonus would double-count it. Other actual movement tests remain unavailable; do not invent timed motion from defensive reputation.

T01 action choice, T06 probing persistence, T07 passing risk, T14 disruption gamble and T15 help commitment are explicitly present but unknown as source probabilities. Ball dominance, assists, steals or playing a help role do not independently identify intrinsic preferences under a standardized opportunity. Their numerical alternatives are supplied below as experiment controls; this does not block implementation. T01 is a normalized action distribution, not a scalar. High recognition still permits a risky or persistent choice.

[Raw exposure validation](diagnostics/milestone4_20261113/exposure_validation.json) checks23 player-seasons of assists/turnovers/points against retained career raw totals, selecting a combined total once or summing stints once. Personal-foul totals are retained directly from the same source; they are **not offensive-foul counts**. Harper has no expected prior NBA season. Games and approximate minutes supply exposure context; stored minutes use rounded per-game averages×games, not precise pressure possessions.

| 2025–26 regular season | Games | Assists | Total turnovers | All personal fouls |
|---|---:|---:|---:|---:|
'''
for v in d['observed_exposure']:
 if v.get('season')=='2025-26':text+=f"| {v['name']} | {v['games']} | {int(v['assists'])} | {int(v['turnovers'])} | {int(v['personal_fouls'])} |\n"
text+='''
All twelve also retain existing `touches`, `PASSES_MADE`, `PASSES_RECEIVED`, per-game/p75 labels and provider passing/turnover fields **as originally stored** in the March11 mixed-source skill file. Per-field query windows/filters/units are not verified; they cannot be joined to completed-season totals as matching denominators. `cTOVpct`, `raDTOV`, passer ratings and added ratings are provider/context fields, not verified handling/pass/offensive-foul subtype counts or independent raw skills. No loss-per-touch or pass-success percentage was manufactured. All handling/passing/offensive-foul exposure cells remain null with reasons. An assist needs a receiver make; an unsuccessful pass need not be a turnover. The historical damaged cache supplies no absent attempts, and its seven mismatches remain quarantined outside this task.

## Separate synthetic scenarios and integration assumptions

Seventeen source-independent one-actor sections supply: reference; high-read/low-delivery and low-read/high-delivery for F03/F04/F06; low/high security; low/high help recognition; slow/fast lateral movement; low/high receiving control; low/high risk appetite. The actor is a reusable role fixture, not a complete lineup; use independent creator/receiver/defender instances and declare which input belongs to which action participant. These are never substituted silently into named-player source documents.

Controls retain synthetic dimensions with explicit protocols (e.g.3m/s² acceleration,6m/s speed,2.5m/s lateral speed,270cm reach), not measured athletes or observed travel times. S07 uses a separately labeled synthetic80% FT conversion proxy requiring its own mapping. Common technique70 is a response-test reference, not a calibrated NBA average. Remaining unneeded fields stay unknown; the backend must declare its tested action dependencies/fallbacks rather than assume all94 fields are integrated.

| Axis | Hold fixed / vary | Causal check for backend |
|---|---|---|
| Recognition versus delivery | Same receiver/window/coverage; vary one F component | Notice/select a window separately from placing the ball; a missed read need not force a turnover |
| Pressure versus security | Matched dribble exposure/contact/time and opponent | S17 changes handling-loss risk, S16 move quality; do not also impose total-TOV penalties |
| Help recognition versus movement | Same responsibility/start geometry, separate S38 from P05/P07 | Early recognition may still arrive late; speed cannot rescue every missed read |
| Receiving reliability | Same intended receiver and delivery quality | Failed catch prevents a finish; account for the loss once, with attribution policy explicit |
| Risk and commitment | Same eligible windows/reads; vary T07 and contextual T06/T14/T15 | Appetite changes choice/exposure, not raw accuracy or intelligence |

Screen quality, screen routes, hold/slip/roll availability, receiver route and coverage assignments remain supplied contexts where unsupported. Do not call them researched S27/S28 facts. Reuse prior shooting/spacing/finishing/interior source inputs by ID; unknown receiving or lob execution still needs a visible experimental control. Do not turn all assisted finishes into lobs.

In the selected action chain, first resolve advantage creation/containment, then help/arrival and window recognition, then intended delivery/receiving and the applicable finish. A kick can also be a skip; a roll feed can also be a lob. Declare a shared baseline/context residual or another nonadditive rule, rather than stacking full F-family talents. Keep steal/loss, foul/free-throw, assist/made-FG and receiver/creator attribution coherent. These are integration requirements, not claims this research tested engine behavior.

## Prioritized evidence queue and stop

1. **Typed pressure losses:** a small clip/event sample for Castle/Cade versus Harper/Brunson, with matched touches/pressure and handling/pass/offensive-foul cause. This could reverse S17 or tentative delivery-versus-read attribution.
2. **Available-read and delivery tags:** pocket/lob/kick/skip opportunities for Luka/Garland/Harper/Cade, recording available target, selected read, ball placement, coverage and receiver result. This would most improve F-family separation and Harper/Cade midpoint offsets.
3. **POA/help responsibility clips:** White/Barnes/Castle with scheme, start position, recognition, movement and arrival. This would separate S38/S39/S40/S44 without four copies of helper reputation.
4. **Existing field definitions/windows:** verify retained touches/pass counts and a typed-loss source before computing rates. No subscription purchase or mandatory human questionnaire is requested; none blocks this handoff.

**Decision:** evidence packet ready for default-OFF integration support; source magnitudes remain provisional and several causal decompositions remain competing hypotheses. Whole-model player/role/league calibration waits for connected offense/defense, passing/creation, coaching/deployment and downstream AI/development validation. No production code, raw-source, ratings, saves, architecture or coordinator edits, network requests or games/simulations were performed. Stop at this bounded packet.
'''
(R/'CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.md').write_text(text)
print('Report written:',len(text.split()),'words')
