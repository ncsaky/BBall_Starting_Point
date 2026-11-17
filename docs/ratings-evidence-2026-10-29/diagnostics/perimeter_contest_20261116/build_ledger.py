"""Fixed catalogue/source readiness; no experimental consumers or engine imports."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[4]
R=ROOT/'docs/ratings-evidence-2026-10-29'
D=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from nba_gm_data.player_model_registry import definition_registry
from nba_gm_data.player_model import PlayerInputs,validate_input_section

VERSION='perimeter_contest_evidence_v1_2026_11_16'
MAP='docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md'
NAV='docs/ratings-evidence-2026-10-29/SCREEN_NAVIGATION_INPUTS_2026_11_13.json'
EXP='docs/ratings-evidence-2026-10-29/EXPANDED_ACTION_COHORT_2026_11_14.json'
MIX='docs/ratings-evidence-2026-10-29/MIXED_POP_INPUT_UPDATES_2026_11_16.json'

def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

reg=definition_registry()
defs={d['id']:d for d in reg['inputs']};outs={d['id']:d for d in reg['outputs']}
assert len(defs)==94
c37=outs['C37']['dependencies']
assert set(c37)=={'S37','S40','S45','P02','P03','P05','P06','P07','P09','P10'}
nav=read(NAV);exp=read(EXP);mix=read(MIX)
manifest=read('docs/ratings-evidence-2026-10-29/diagnostics/mixed_pop_20261116/delivery_manifest.json')
assert sha(MIX)==next(x['sha256'] for x in manifest['files'] if x['path']==MIX)
assert sha(EXP)=='e61a71e7b1225f83c0e357386b98a08ce2a449c310e99f5846b80b00a32755d2'
actors=[
 ('Derrick White','player_bos-derrick-white',NAV,'player_input_section',['defender']),
 ('Stephon Castle','player_sas-stephon-castle',NAV,'player_input_section',['defender']),
 ('Scottie Barnes','player_tor-scottie-barnes',EXP,'proposed_source_input_section',['defender']),
 ('Victor Wembanyama','player_sas-victor-wembanyama',EXP,'proposed_source_input_section',['defender']),
 ('Rudy Gobert','player_min-rudy-gobert',NAV,'player_input_section',['defender']),
 ('Stephen Curry','player_gsw-stephen-curry',EXP,'proposed_source_input_section',['defender','shooter']),
 ('Jalen Brunson','player_nyk-jalen-brunson',EXP,'proposed_source_input_section',['defender','shooter']),
 ('Chet Holmgren','player_okc-chet-holmgren',MIX,'proposed_source_input_section',['shooter']),
 ('Karl-Anthony Towns','player_nyk-karl-anthony-towns',MIX,'proposed_source_input_section',['shooter']),
]
packets={NAV:nav,EXP:exp,MIX:mix}
snapshot={'version':mix['input_version'],'registry_version':mix['registry_version'],'players':{}}
lineage=[]
for name,pid,path,section,roles in actors:
 pl=deepcopy(packets[path][section]['players'][pid]);snapshot['players'][pid]=pl
 lineage.append({'name':name,'player_id':pid,'roles_in_this_review':roles,'packet':path,'packet_version':packets[path]['packet_version'],'section':section,'profile_sha256':digest(pl),'policy':'One complete inherited source profile, copied exactly; no merge/relabel/operational-control imports.'})
dump(D/'inherited_source_snapshot.json',snapshot)

sources={
 'SG':{'path':'captions/Ckufse6eWsM.en.vtt','date':'2026-08-14','video_id':'Ckufse6eWsM','reviewed':'01:37:09–01:37:34;01:39:41–01:39:58','kind':'retained auto-captions, selected White clauses only','correlation_group':'nerd_sesh_commentary'},
 'PG':{'path':'transcripts/episode8_transcript.txt','date':'2026-08-05','reviewed':'Castle00:16:24–00:16:53;00:20:59–00:21:46; Brunson01:08:43–01:09:31; Curry01:14:13–01:14:38','kind':'user-retained timestamped transcript, selected passages','correlation_group':'nerd_sesh_commentary'},
 'PF':{'path':'transcripts/episode5_transcript.txt','date':'2026-08-28','reviewed':'Barnes01:11:45–01:12:16','kind':'user-retained timestamped transcript, selected passage','correlation_group':'nerd_sesh_commentary'},
 'CE':{'path':'transcripts/episode4_transcript.txt','date':'2026-09-02','reviewed':'Gobert00:52:59–00:53:25; Wembanyama01:35:07–01:35:38; Holmgren01:03:46–01:04:23; Towns01:21:18–01:22:06','kind':'retained original transcript; selected clauses and prior retained shooting contexts','correlation_group':'nerd_sesh_commentary'},
 'GLOSSARY':{'url':'https://www.nba.com/stats/help/glossary','date':None,'retrieved_on':'2026-11-16','kind':'official metric definitions, undated','locator':'Contested Shot (Tracking) versus Contested Shots (Hustle)','summary':'Tracking uses nearest defender within3.5feet; hustle counts hand-up closeouts before release.','correlation_group':'nba_definitions','limit':'Different definitions, not causal quality or detailed hand/ball geometry measurements.'},
 'SHOT_BINS':{'url':'https://www.nba.com/news/open-shots-key-entering-game-6-of-bucks-celtics-and-warriors-grizzlies','date':'2022-05-13','author':'Brian Martin','kind':'NBA original historical shot analysis/table','locator':'first BOS/MIL closest-defender table and accompanying outside10feet description','summary':'BOS open39/100, wide-open44/102; firstfive2022MIL-series games, shots beyond10feet.','correlation_group':'nba_2022_selected_shots','limit':'Selected attempted jumpers, shooter/shot/location mix and bin protocols; not2026 skill or isolated defender effects.'},
 'RULE12':{'url':'https://official.nba.com/rule-no-12-fouls-and-penalties/','date':None,'retrieved_on':'2026-11-16','kind':'official rules reference, undated current page','locator':'B.Personal Foul, SectionI.Types and SectionIV.Flagrant','summary':'Illegal contact and unnecessary/excessive contact have distinct consequences.','correlation_group':'nba_rules','limit':'No probability or actor foul grade measured.'},
 'LEGAL_COMMON':{'url':'https://videorulebook.nba.com/archive/defensive-foul-defender-makes-lower-body-contact-with-shooter/','date':None,'retrieved_on':'2026-11-16','kind':'official written case narration only; video not reviewed','locator':'Kevin Durant/Kyle Kuzma landing-space narration,25_Other_505','summary':'The described leg-to-leg landing-space contact is a defensive foul, not flagrant.','correlation_group':'nba_rules','limit':'One interpreted example; do not infer foul frequency or re-rate its participants.'},
 'LEGAL_FLAGRANT':{'url':'https://videorulebook.nba.com/archive/flagrant-foul-penalty-1-defender-reckless-contest-into-landing-space-shooter-turns-ankle/','date':None,'retrieved_on':'2026-11-16','kind':'official written case narration only; video not reviewed','locator':'Jaylen Brown/Jalen Brunson reckless landing-space narration,25_Other_895','summary':'The described reckless foot intrusion is Flagrant1, including when unintentional.','correlation_group':'nba_rules','limit':'Case distinction, not an always-flagrant rule for all closeout contact or an injury model.'},
}

def claim(i,source,loc,support,limits,ids,mechanism):
 return {'id':i,'source_id':source,'date':sources[source]['date'],'locator':loc,'support':support,'cannot_establish':limits,'approved_input_ids':ids,'mechanism_implication':mechanism,'numeric_effect':None,'confidence':'qualitative direction or definition; isolated magnitude not established','correlation_group':sources[source]['correlation_group']}

claims=[
 claim('CC01','SG','01:37:09–01:37:34;01:39:41–01:39:58','White positioning, anticipation, timely help, POA and guard shot-blocking praised.','Not a timed closeout/landing sample; existing S40 is a tentative transfer. Adjacent01:34 passage is Reaves, not White.',['S38','S39','S40','S41','S37'],'Contrast early help/arrival with established on-ball assignments; no automatic perimeter timing grade from guard blocks.'),
 claim('CC02','PG','00:16:24–00:16:53;00:20:59–00:21:46','Castle strong star-guard POA defense, with high fouls/weaker off-ball contribution and Wembanyama context.','No specific closeout violation rate; do not turn one critique into independent recognition/attention/positioning/foul penalties.',['S33','S38','S39','S44','S45'],'Strong containment need not imply early rotational closeouts. Separate arrival and legal contest from total defense.'),
 claim('CC03','PF','01:11:45–01:12:16','Barnes covers noncenter assignments and ground, with defensive hands/secondary rim contribution.','Broad effective coverage, not measured acceleration/braking or full-time-anchor/perimeter-contest equivalence.',['S33','S37','S38','S39','S40','P05','P07'],'Use role-matched off-ball versus on-ball tests; preserve the possibility that tools and starting position explain observed effectiveness.'),
 claim('CC04','CE','01:35:07–01:35:38','Wembanyama extraordinary interior range/deterrence with some space-switching problems.','Reach does not teleport an out-of-position defender; interior S37 support transfers imperfectly to C37.',['S37','S40','S45','P02','P03','P05','P07','P10'],'Resolve reachable geometry at actual arrival/release and approach control separately.'),
 claim('CC05','CE','00:52:59–00:53:25','Gobert anchor coverage plus successful switching/space contexts described.','Not proof of universally poor or elite perimeter closeouts; exact P07/S40/S37 task decomposition unknown.',['S37','S38','S39','S40','P07'],'Use big-versus-guard task context rather than declaring all centers incapable or all anchors excellent at C37.'),
 claim('CC06','PG','01:14:13–01:14:38','Curry constant movement/shooting threat changes defensive demands.','No stopwatch release measurement or independent defensive closeout evidence for Curry.',['S01','S03','S08','S26','S35','S41'],'Movement changes arrival opportunities; route execution and navigation precede one shot response, not an extra gravity/movement bonus.'),
 claim('CC07','PG','01:08:43–01:09:31','Brunson defensive limitations/infrastructure support discussed.','No specific hand timing, controlled-closeout or causal fouling magnitude. Offensive craft cannot fill defensive unknowns.',['S33','S37','S40','S45'],'A sheltered assignment can change exposure without changing underlying closeout or contest ability.'),
 claim('CC08','CE','01:03:46–01:04:23','Holmgren good open shooter but slow-release access; speakers dispute historical mechanics.','No milliseconds/height measurement; do not independently lower S01 and preparation for one same contest-access issue.',['S01','S08','S37','S40'],'At identical defender trajectory, release preparation can decide whether the contest arrives before the shot.'),
 claim('CC09','CE','01:21:18–01:22:06','Towns catch/deep contested shooting praised; peak-repeatability questioned.','No universal immunity to contests, exact release speed or independent range-plus-accuracy-plus-contest-resistance bonuses.',['S01','S08','S09','S37'],'Separate shot type/distance and available preparation; retain same underlying source record.'),
 claim('CC10','GLOSSARY','Contested Shot / Contested Shots','See source summary: metric definitions differ.','No proof nearest distance measures hand location, readiness or legal contest timing.',['S37','S40','P02','P03'],'Label distance-at-release separately from active pre-release contest; do not use them as identical training targets.'),
 claim('CC11','SHOT_BINS','first BOS/MIL closest-defender table','See compact historical count card.','Not a controlled monotonic law or2026 coefficient. Actual attempts exclude opportunities passed up and can vary by shooter/type/clock.',['S01','S08','S09','S37'],'Use explicit attempt denominators for descriptive checks; do not fit C37 from pooled opponentFG%.'),
 claim('CC12','LEGAL_COMMON','written landing-space case narration','See source summary.','No video review or probability; not a legal high-quality contest merely because the shooter releases.',['S40','S45','S37'],'Arrival quality must include post-release landing/contact consequences, not only make suppression.'),
 claim('CC13','LEGAL_FLAGRANT','written reckless landing-space case narration','See source summary; RULE12 supplies the broader contact framework.','Do not treat every contact as this category or reward reckless hand proximity.',['S40','S45'],'Record legal state jointly with contest outcome; contest aggression is not automatically better.'),
]

stages=[
 {'id':'recognize','derived_ids':['C26','C29'],'inputs':['S38','S41','S44','S46'],'state':['assignment','ball/receiver threat','communication already delivered','decision time'],'support_claims':['CC01','CC02','CC03'],'gap':'No isolated recognition latency/communication timing; choose one recognition process, not four full speed bonuses. S46 only when team calls are actually modeled.'},
 {'id':'start_and_path','derived_ids':['C26','C25','C23'],'inputs':['S39','S35','S33','P05','P06','P07','P09'],'state':['initial position/velocity','screen/route obstruction','intended approach angle'],'support_claims':['CC01','CC02','CC03','CC06'],'gap':'Navigation applies with an actual obstacle; containment applies to the live drive threat, not an automatic additional closeout grade. Starting geometry belongs in state.'},
 {'id':'approach_control','derived_ids':['C26','C37'],'inputs':['S40','P05','P06','P07','P09'],'state':['distance remaining','approach velocity/angle','braking/control state'],'support_claims':['CC01','CC03','CC04'],'gap':'S40 technique and measured braking capacity are not interchangeable. No source actor has complete measured motion/balance here.'},
 {'id':'contest_at_release','derived_ids':['C37'],'inputs':c37,'state':['actual release time and ball position','hand/reach pose','jump/grounded state','line of approach'],'support_claims':['CC04','CC05','CC08','CC10'],'gap':'C37 shares S37 with C27 but not a second full interior response. No height+span+standing-reach+rim-summary stack.'},
 {'id':'shooter_response','derived_ids':['C01','C02','C03','C05','C07','C13','C17'],'inputs':['S01','S02','S03','S04','S05','S06','S08','S09','S14','S16','S18','S20','S26','P09'],'state':['shot type/distance','catch readiness','pump/pass/drive choice','shot clock','preparation and balance'],'support_claims':['CC06','CC08','CC09'],'gap':'Use only the relevant mode/branch, not the union as a compulsory full-profile requirement. FT skill is excluded. A delayed/abandoned shot is not necessarily a miss.'},
 {'id':'legal_resolution','derived_ids':['C37','C29','C15'],'inputs':['S37','S40','S45','S24'],'state':['contact timing/location','landing space','attacker movement','rule outcome'],'support_claims':['CC12','CC13'],'gap':'S24 only when shooter contact craft is modeled. S45 is legal execution, not T16 willingness. Joint make/block/foul result must be coherent, including made-and-fouled cases.'},
 {'id':'recover','derived_ids':['C26','C23','C30'],'inputs':['S38','S39','S40','S33','P05','P06','P07','P09','P11','P12','T17'],'state':['post-contest position/velocity','landing/control state','continuing assignment','fatigue','new offensive action'],'support_claims':['CC02','CC03','CC06'],'gap':'Immediate spatial recovery uses movement/control; P12 is between-effort physiological recovery, not instantaneous teleporting or a second foot-speed bonus. Workload branch only when state is modeled.'},
]

shooter_modes={
 'player_gsw-stephen-curry':{'mode':'catch / optional movement','ids':['S01','S08','S09','P09'],'optional_branch_ids':['S03','S26']},
 'player_nyk-jalen-brunson':{'mode':'pull-up','ids':['S02','S08','S09','P09'],'optional_branch_ids':['S16','S18','S20']},
 'player_okc-chet-holmgren':{'mode':'catch','ids':['S01','S08','S09','P09'],'optional_branch_ids':[]},
 'player_nyk-karl-anthony-towns':{'mode':'catch','ids':['S01','S08','S09','P09'],'optional_branch_ids':[]},
}
readiness=[]
rows=[]
upstream=['S38','S39','S41','S44','S46','S35','T15','T16','T17']
for l in lineage:
 pid=l['player_id'];inp=snapshot['players'][pid]['inputs']
 known=lambda keys:[k for k in keys if inp[k]['status']!='unknown']
 row={'name':l['name'],'player_id':pid,'roles':l['roles_in_this_review'],'known_all94':len(known(defs)),'defender_C37':None,'shooter_branch':None}
 if 'defender' in l['roles_in_this_review']:
  row['defender_C37']={'direct_ids':c37,'supported':known(c37),'unknown':[k for k in c37 if k not in known(c37)],'upstream_supported':known(upstream),'upstream_unknown':[k for k in upstream if k not in known(upstream)],'status':'partial source only; no complete named direct projection claimed'}
 if 'shooter' in l['roles_in_this_review']:
  mode=shooter_modes[pid];row['shooter_branch']={**mode,'supported':known(mode['ids']),'unknown':[k for k in mode['ids'] if k not in known(mode['ids'])],'status':'partial mode-specific source; readiness/geometry still require declared context'}
 readiness.append(row)
 for k,d in defs.items():
  rows.append({'player_id':pid,'input_id':k,'name':d['name'],'kind':d['kind'],'status':inp[k]['status'],'source_packet':l['packet'],'source_section':l['section'],'source_record_sha256':digest(inp[k]),'C37_direct_for_declared_defender':'defender' in l['roles_in_this_review'] and k in c37,'changed':False})

constraints=[
 {'id':'CN01','kind':'definition_only','source_id':'GLOSSARY','population':'metric definitions, not a shot sample','window':'undated current page retrieved2026-11-16','denominator':None,'value':3.5,'unit':'feet, tracking Contested Shot definition','meaning':'A metric threshold only; not C37 physical reach radius or a make-probability discontinuity.','causal_response_calibration':False},
 {'id':'CN02','kind':'observed_descriptive_counts','source_id':'SHOT_BINS','population':'BOS attempted shots beyond10ft, firstfive2022 Eastern semifinals games versusMIL','window':'through Game5; article2022-05-13','denominator_definition':'actual FGA in each nearest-defender bin, not all closeout opportunities or all possessions','rows':[{'label':'4-6 Feet - Open','made':39,'attempted':100,'derived_FG_pct':39.0},{'label':'6+ Feet - Wide Open','made':44,'attempted':102,'derived_FG_pct':44/102*100}],'derivation':'100*FGM/FGA; no rounding per-game counts reconstructed','unit':'percent made, pooled2/3point attempts','limits':'Historical selected attempts; shooter quality, shot mix, distance, clock, approach direction and passes/shots avoided unconditioned. No causal defender coefficient.','causal_response_calibration':False},
 {'id':'CN03','kind':'provider_bin_labels','source_id':'SHOT_BINS','population':'the same published nearest-defender categorization','window':'2022 article','denominator':None,'labels':['0-2 Feet - Very Tight','2-4 Feet - Tight','4-6 Feet - Open','6+ Feet - Wide Open'],'meaning':'Retain labels exactly; do not invent boundary-inclusion protocol, hand-to-ball distance, behind/in-front equivalence or a hard gameplay step function.','causal_response_calibration':False},
]
tests=[
 {'id':'CT01','focus':'recognition versus travel','hold':'same start/velocity, capacity, shooter release process and responsibility','vary':'earlier/later decision, then movement capacity separately','expectation':'Earlier recognition can permit earlier controlled arrival; do not attribute all delay to speed. No fixed millisecond target.'},
 {'id':'CT02','focus':'proximity versus active geometry','hold':'same closest body distance and release time','vary':'hand up/down, front/side/behind approach, contest timing and reach separately','expectation':'Near does not guarantee useful pre-release contest. A late hand cannot retroactively suppress an already released shot; later contact may still matter legally.'},
 {'id':'CT03','focus':'arrival/braking tradeoff','hold':'same recognition/start and shooter options','vary':'controlled approach versus excessive momentum at declared physical capacity','expectation':'Closer arrival may cost blow-by exposure or foul/recovery control; better S40 need not maximize blocks. Do not fit a universal all-out sprint advantage.'},
 {'id':'CT04','focus':'shooter preparation/mode','hold':'same defender trajectory and delivery readiness','vary':'S08, then catch/pull-up/movement branch and shot distance separately','expectation':'Available release window and contest can change; do not double-charge inherited accuracy for the same access problem. Midpoints are not measured release times.'},
 {'id':'CT05','focus':'reach and timing','hold':'same arrival/control and technique','vary':'standing reach, jump state, then timing separately','expectation':'Physical access must be feasible; no triple height/span/reach bonus, no C36 extra multiplier, no automatic big-over-guard contest order.'},
 {'id':'CT06','focus':'legal contest and attacker reaction','hold':'same start/skill and initial threat','vary':'shot, pump/drive, pass and landing/contact context','expectation':'Report selection, legal/illegal contact, attempt/make/block and post-action recovery consistently. No mandatory shot or independent contradictory block/make/foul draws.'},
 {'id':'CT07','focus':'evidence comparisons and selection','hold':'matched responsibility, start, shooter mix and exposure definition','vary':'White/Castle help versus attached POA; Barnes secondary help versus big anchor; source shooter alternatives','expectation':'A broad scouting rank is not the target. Include all threats, declined shots and later recovery costs alongside per-attemptFG%; identify unknown controls when order reverses.'},
]
paths=[MAP,'docs/PLAYER_SKILL_DEPENDENCY_MAP_2026_11_11.md','src/nba_gm_data/player_model_registry.py','src/nba_gm_data/player_model.py',NAV,EXP,MIX,'docs/ratings-evidence-2026-10-29/DEFENSIVE_ROLE_PLAYER_INPUT_REVIEW_2026_11_11.md','docs/ratings-evidence-2026-10-29/PILOT_PROFILE_READINESS_2026_11_13.md','docs/ratings-evidence-2026-10-29/CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.md','docs/ratings-evidence-2026-10-29/EXPANDED_ACTION_COHORT_2026_11_14.md','docs/ratings-evidence-2026-10-29/PASS_RECOVERY_EVIDENCE_2026_11_16.json']
paths+=['docs/ratings-evidence-2026-10-29/'+s['path'] for s in sources.values() if 'path'in s]
hashes={p:sha(p) for p in paths}
counts={'actors':9,'declared_defenders':7,'declared_shooters':4,'records_preserved':len(rows),'dimensions_each':94,'passing_dimensions_each':18,'all_source_known':sum(x['known_all94'] for x in readiness),'C37_direct_ids':len(c37),'defender_direct_cells':7*len(c37),'defender_direct_supported':sum(len(x['defender_C37']['supported']) for x in readiness if x['defender_C37']),'claims':len(claims),'dependency_stages':len(stages),'controlled_comparisons':len(tests)}
counts['defender_direct_unknown']=counts['defender_direct_cells']-counts['defender_direct_supported']
counts['all_source_unknown']=len(rows)-counts['all_source_known']
ledger={'ledger_version':VERSION,'production_import_authorized':False,'date_policy':'October2026 pre-opener; pre-start scouting and explicitly historical tables eligible. Undated current rules/definition pages retrievedNov16 are normative references, not fresh player performance. No opening-week results or projections converted to current skill.','counts':counts,'approved_C37_definition':deepcopy(outs['C37']),'definition_status':'Fixed catalogue dependency transcription; no claim about current runtime implementation or actual compile contract.','sources':sources,'claims':claims,'dependency_stages':stages,'constraints':constraints,'source_profile_lineage':lineage,'readiness':readiness,'controlled_comparisons':tests,'snapshot_path':'diagnostics/perimeter_contest_20261116/inherited_source_snapshot.json','readiness_ledger_path':'diagnostics/perimeter_contest_20261116/readiness_ledger.json','minimum_additional_inputs':{'for_direct_C37':'Missing source geometry/motion/balance/jump and relevant S37/S40/S45 per declared defender, or explicit isolated controls; never generic hidden completions.','for_rotation':'Threat/assignment, recognition/start state, path and approach velocity, with uncertain C26 ingredients; communication only if modeled.','for_shot':'Actual shooter readiness, release/mode/distance, trajectory; source-unknown preparation/range/balance controlled openly.','for_legal_recovery':'Contact/landing geometry, continuing assignment, post-contest velocity/control; workload only if fatigue state modeled.','physical_recovery_warning':'P12 is physiological recovery between efforts, not spatial recovery movement.'},'player_input_additions':[],'proposed_corrections':[],'operational_completions':[],'numeric_effect_coefficients':[],'human_questions_required':[],'source_hashes':hashes,'independence':{'new_backend_outcomes_inspected':False,'backend_implementation_inspected':False,'profile_compilations':0,'simulations':0,'production_or_save_writes':0},'retrieval_limits':[{'url':'https://api-hub-dev.nba.com/news/which-teams-are-creating-and-converting-open-looks-in-the-conference-semifinals','result':'461 on open; no retry or numeric use from inaccessible body; a different historical article supplied verified counts.'},{'source':'current player shot-dashboard search rows','result':'Not adopted for numeric effects: rounded per-game values and incomplete verified filter/window context; no denominator reconstruction or endpoint campaign.'}],'coverage':'Selected retained clauses and public written definitions/case narrations/tables; no full episode, full video or new experimental outcome review.'}
dump(R/'PERIMETER_CONTEST_EVIDENCE_2026_11_16.json',ledger)
dump(D/'readiness_ledger.json',{'ledger_version':VERSION,'rows':rows})
validate_input_section(snapshot)
for name,pid,path,section,roles in actors:
 assert snapshot['players'][pid]==packets[path][section]['players'][pid]
 assert len(snapshot['players'][pid]['inputs'])==94
 assert set(snapshot['players'][pid]['inputs'])==set(defs)
 assert PlayerInputs(snapshot['players'][pid]).to_dict()==snapshot['players'][pid]
 assert sum(k.startswith('F') for k in snapshot['players'][pid]['inputs'])==18
for claimrow in claims:
 assert set(claimrow['approved_input_ids'])<=set(defs)
for stage in stages:
 assert set(stage['inputs'])<=set(defs) and set(stage['derived_ids'])<=set(outs)
 assert all(c in {x['id'] for x in claims} for c in stage['support_claims'])
assert all(sha(p)==h for p,h in hashes.items())
dump(D/'validation.json',{'ledger_version':VERSION,'status':'PASS','counts':counts,'schema_roundtrips':9,'all846_source_records_exact':True,'all18_passing_fields_each':True,'C37_dependencies_match_registry':True,'all_input_output_references_registered':True,'historical_numeric_rows_recomputed':True,'source_hash_checks':{p:sha(p)==h for p,h in hashes.items()},'new_grades':0,'profile_compilations':0,'simulations':0,'scope':'Fixed source/catalogue readiness and artifact validation only; not actual consumer compilation or outcome testing.'})
print(json.dumps({'status':'PASS','counts':counts},ensure_ascii=False))
