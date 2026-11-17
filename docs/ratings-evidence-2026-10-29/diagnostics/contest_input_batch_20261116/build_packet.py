"""Source-first seven-player proposals. No engine or save calls."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,sys

ROOT=Path(__file__).resolve().parents[4]
R=ROOT/'docs/ratings-evidence-2026-10-29';D=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from nba_gm_data.player_model_registry import definition_registry
from nba_gm_data.player_model import PlayerInputs,validate_input_section

VERSION='contest_input_batch_v1_2026_11_16'
SCALE='research_technique_reference_v0_2026_11_13'
PREVIOUS='docs/ratings-evidence-2026-10-29/PERIMETER_CONTEST_EVIDENCE_2026_11_16.json'
SNAP='docs/ratings-evidence-2026-10-29/diagnostics/perimeter_contest_20261116/inherited_source_snapshot.json'
MAP='docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md'
def read(p):return json.loads((ROOT/p).read_text())
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

prior=read(PREVIOUS);snapshot=read(SNAP)
manifest=read('docs/ratings-evidence-2026-10-29/diagnostics/perimeter_contest_20261116/delivery_manifest.json')
for p in [PREVIOUS,SNAP]:assert sha(p)==next(f['sha256'] for f in manifest['files'] if f['path']==p)
reg=definition_registry();defs={x['id']:x for x in reg['inputs']}
assert len(defs)==94
lineage=[deepcopy(x) for x in prior['source_profile_lineage'] if 'defender' in x['roles_in_this_review']]
assert len(lineage)==7
ids=[x['player_id'] for x in lineage];names={x['player_id']:x['name'] for x in lineage}
base={k:snapshot[k] for k in ['version','registry_version']}
base['players']={pid:deepcopy(snapshot['players'][pid]) for pid in ids}
proposed=deepcopy(base)
sources={k:deepcopy(prior['sources'][k]) for k in ['SG','PG','PF','CE']}
sources.update({
 'KATZ2026':{'url':'https://www.nba.com/news/all-perimeter-defense-first-team','date':'2026-04-08','author':'Fred Katz, The Athletic, publicly hosted by NBA','reviewed':'Derrick White and Scottie Barnes sections, written reporting only','kind':'original interview and specific action analysis','summary':'White prioritizes foul avoidance/timing and controls closeout braking; Barnes makes anticipatory coverage calls.','correlation_group':'katz_2026_selected_defense','limits':'Selected positive examples/team roles; provider contextual stats not independently acquired. No embedded video review or timed athlete measurement.'},
 'BRUNSON2024':{'url':'https://www.nba.com/mavs/taking-the-charge','date':'2024-01-10','author':'Eddie Sefko','reviewed':'charge-taking reporting and coaching explanations','kind':'original team reporting','summary':'Brunson is identified as a skilled, frequent charge-taker.','correlation_group':'brunson_2024_charge_reporting','limits':'Historical narrow contact context; no charge-attempt/failure denominator or perimeter landing/hand timing sample. No count-to-grade conversion.'},
 'CURRY2019':{'url':'https://www.nba.com/news/film-study-warriors-get-burned','date':'2019-06-07','author':'John Schuhmann','reviewed':'Getting caught flat-footed, first Curry example','kind':'original written film analysis','summary':'A flat-footed Curry lapse leaves a corner shot unchallenged.','correlation_group':'curry_2019_selected_breakdown','limits':'One old sequence, not a stable2026 skill estimate or evidence of measured speed/legality. No video review.'},
})

claims=[deepcopy(c) for c in prior['claims'] if c['id'] in ['CC01','CC02','CC03','CC04','CC05','CC06','CC07']]
claims += [
 {'id':'CB08','source_id':'KATZ2026','date':'2026-04-08','locator':'Derrick White section: interview, vertical help and Ball closeout paragraphs','support':'See compact source card; stronger task-specific corroboration than prior role-only S40 inference.','cannot_establish':'No isolated foul/closeout rate, millisecond preparation/braking time or scheme-independent impact. Selected good examples.','direct_or_inferred':'direct technique assessment and described action; numeric S45 magnitude inferred','correlation_group':'katz_2026_selected_defense'},
 {'id':'CB09','source_id':'KATZ2026','date':'2026-04-08','locator':'Scottie Barnes section: mid-March Phoenix triple-switch sequence','support':'See compact source card; explicit defensive coverage-call context for S46.','cannot_establish':'No communication-success denominator, universal scheme transfer, personality grade or independent S40 measurement.','direct_or_inferred':'direct call/recognition assessment; numeric S46 magnitude inferred','correlation_group':'katz_2026_selected_defense'},
 {'id':'CB10','source_id':'BRUNSON2024','date':'2024-01-10','locator':'Brunson/Hardaway charge-taking and coaching discussion','support':'See compact source card; useful counterevidence to treating all defensive execution as weak.','cannot_establish':'Charge counts alone do not establish foul control; inferred technique does not directly identify jump-contest discipline.','direct_or_inferred':'historical narrow-context assessment; cross-context S45 magnitude inferred','correlation_group':'brunson_2024_charge_reporting'},
 {'id':'CB11','source_id':'CURRY2019','date':'2019-06-07','locator':'Getting caught flat-footed, first Curry sequence','support':'See compact source card; a concrete failure rather than an offensive-defense proxy.','cannot_establish':'A seven-year-old error cannot establish a current low contest/closeout grade; no inferred persistent decline or poor legal technique.','direct_or_inferred':'specific historical action, not a current skill measure','correlation_group':'curry_2019_selected_breakdown'},
]
claim_ids={c['id'] for c in claims}
new=[]

def add(pid,k,bounds,refs,explanation,limits,shared):
 assert base['players'][pid]['inputs'][k]['status']=='unknown' and defs[k]['kind']=='grade'
 ev=[]
 for ref in refs:
  c=next(c for c in claims if c['id']==ref);s=sources[c['source_id']]
  ev.append({'source':s.get('path',s.get('url')),'as_of':s['date'],'method':'trusted explicit scouting/action context plus labeled raw-technique inference','shared_evidence_id':shared if 'path' in s else s['correlation_group'],'notes':ref+'; '+c['locator']+'; direct claim/inference/counterevidence in contest-input claim ledger.'})
 value={'grade':sum(bounds)/2,'scale':SCALE}
 record={'status':'estimated','value':value,'evidence':ev,'uncertainty':{'confidence':'low','notes':f'Provisional range{bounds[0]}–{bounds[1]}, not probability, percentile or statistical CI. {explanation} {limits}'}}
 proposed['players'][pid]['inputs'][k]=record
 new.append({'player_id':pid,'name':names[pid],'design_id':k,'old_record':deepcopy(base['players'][pid]['inputs'][k]),'range':bounds,'reference':value,'record':record,'claim_ids':refs,'direct_or_inferred':'Technique assessment may be direct; all numeric magnitudes and context transfer are analyst inferences.','inference':explanation,'counterevidence':limits,'confidence':{'direction':'moderate where explicit; lower for cross-context transfer','numeric_magnitude':'low'},'shared_evidence_group':shared})

white='player_bos-derrick-white';castle='player_sas-stephon-castle';barnes='player_tor-scottie-barnes';wemb='player_sas-victor-wembanyama';gobert='player_min-rudy-gobert';curry='player_gsw-stephen-curry';brunson='player_nyk-jalen-brunson'
add(white,'S45',[76,92],['CB08','CC01'],'Strong-to-exceptional legal-execution hypothesis, supported beyond low aggregate fouls by explicit technique context.','Role/exposure and selected examples remain; no universal no-foul promise, no statistical success probability. Existing S37/S40 unchanged.','katz_2026_selected_defense')
add(castle,'S37',[70,88],['CC02'],'Strong contest-technique hypothesis from effective star-guard containment and staying in front, not a size or block-count award.','Contest timing/hand pose not isolated. Perimeter evidence leads; interior execution transfer uncertain. Existing foul concern stays in S45, not a second full contest penalty.','m4_scout_player_sas-stephon-castle')
add(castle,'S40',[62,84],['CC02'],'Functional-to-strong controlled-arrival hypothesis from physical on-ball stance/angle execution; rotational transfer is tentative.','POA is not a clean closeout test. Do not independently penalize S40 for the same off-ball weakness already used in S38/S39/S44. Movement capacity remains unknown.','m4_scout_player_sas-stephon-castle')
add(barnes,'S40',[70,90],['CC03'],'Strong arrival-angle/control hypothesis from useful guard/wing coverage and secondary help.','Effective coverage includes tools, recognition and starting position. Broad decomposition, not timed braking; do not count the same range twice as technique and measured speed.','expanded_scout_player_tor-scottie-barnes')
add(barnes,'S46',[78,94],['CB09'],'Strong-to-exceptional defensive coverage-communication hypothesis using a specific call sequence.','One positively selected scheme example plus broad assessment, not measured universal communication or a generic intelligence/leadership bonus. Keep S38 and S46 as linked stages, not two complete recognition benefits.','katz_2026_selected_defense')
add(wemb,'S40',[60,86],['CC04'],'Broad functional-to-strong approach-control hypothesis from extreme effective coverage, with interior-to-perimeter transfer uncertainty.','Reach and route capacity may explain much of the result. Space-switching caveat is a boundary, not a new measured slow-motion grade or another full S33 penalty. Existing high shared S37 is preserved.','expanded_scout_player_sas-victor-wembanyama')
add(gobert,'S37',[78,94],['CC05'],'Strong-to-exceptional contest technique inferred from repeated rim/post and varied-coverage execution, rather than height, awards or blocks alone.','Interior-leading evidence; shared S37 does not certify equal perimeter performance. Do not force a cut to separate Wembanyama. Geometry and timing still matter.','m4_scout_player_min-rudy-gobert')
add(gobert,'S40',[60,84],['CC05'],'Broad useful controlled-arrival hypothesis from successful space/coverage execution, not a claim of elite guard-like pursuit.','Different assignments and starts could explain effectiveness. No isolated stopping/slowing sample; no numeric mobility inferred and no automatic zero from center role.','m4_scout_player_min-rudy-gobert')
add(brunson,'S45',[55,80],['CB10','CC07'],'Tentative legal body-position/contact-control hypothesis from a narrow successful defensive craft, despite broader limitations.','Willingness/exposure and referee decisions also determine charge totals; no conversion from count/rank. Historical contact-to-jump-contest transfer is weak, so broad range; S37/S40 stay unknown.','brunson_2024_charge_reporting')

summary=[];ledger=[]
target=['S37','S40','S45']
for pid in ids:
 b=base['players'][pid]['inputs'];a=proposed['players'][pid]['inputs']
 changed=[u['design_id'] for u in new if u['player_id']==pid]
 summary.append({'player_id':pid,'name':names[pid],'before_target':{k:deepcopy(b[k]) for k in target},'new_ids':changed,'known_before':sum(v['status']!='unknown' for v in b.values()),'known_after':sum(v['status']!='unknown' for v in a.values()),'target_unknown_after':[k for k in target if a[k]['status']=='unknown']})
 for k in defs:
  ledger.append({'player_id':pid,'input_id':k,'base_status':b[k]['status'],'proposed_status':a[k]['status'],'base_record_sha256':digest(b[k]),'origin':'new_proposal' if k in changed else 'inherited_unchanged','proposed_record_pointer':f'/proposed_source_input_section/players/{pid}/inputs/{k}'})
supplemental=[{'player_id':white,'design_ids':['S37','S40'],'claim_ids':['CB08'],'action':'More specific positive corroboration, but existing ranges/records remain plausible and are not numerically revised.'}]
sources_paths=[PREVIOUS,SNAP,MAP,'src/nba_gm_data/player_model_registry.py','src/nba_gm_data/player_model.py','docs/ratings-evidence-2026-10-29/PERIMETER_CONTEST_EVIDENCE_2026_11_16.md','docs/ratings-evidence-2026-10-29/diagnostics/perimeter_contest_20261116/readiness_ledger.json']
sources_paths += ['docs/ratings-evidence-2026-10-29/'+s['path'] for s in sources.values() if 'path'in s]
hashes={p:sha(p) for p in sources_paths}
counts={'players':7,'dimensions_per_player':94,'passing_dimensions_per_player':18,'base_records':658,'inherited_supported':sum(x['known_before'] for x in summary),'new_unknown_cell_proposals':len(new),'supported_after':sum(x['known_after'] for x in summary),'target_cells':21,'target_new_proposals':sum(x['design_id'] in target for x in new),'target_unknown_after':sum(len(x['target_unknown_after']) for x in summary),'corrections':0,'operational_defaults':0}
counts['unknown_after']=658-counts['supported_after']
packet={'packet_version':VERSION,'input_version':base['version'],'registry_version':base['registry_version'],'production_import_authorized':False,'date_policy':'October2026 pre-opener healthy ability. Retained offseason scouting eligible; Apr2026 reporting is pre-start;2024 contact craft and2019 error are separately historical. No post-opener results, injury discount or development forecast converted to current technique.','technique_scale':{'id':SCALE,'anchors':{'50':'functional reference','75':'strong reference','90':'exceptional reference'},'meaning':'Inherited research decomposition scale, not production ratings, percentile, probability or statistical CI. Endpoints are analyst judgments; midpoints not measurement precision.'},'counts':counts,'cohort_lineage':lineage,'inheritance':{'packet':PREVIOUS,'snapshot':SNAP,'snapshot_sha256':hashes[SNAP],'policy':'Seven complete profiles copied exactly in base; all supported/physical/passing/tendency records preserved in proposed. Only nine unknown skill cells filled.'},'base_source_input_section':base,'proposed_source_input_section':proposed,'new_estimates':new,'supplemental_evidence_without_overwrite':supplemental,'correction_proposals':[],'revision_proposals':[],'before_proposed_unknown':summary,'sources':sources,'claims':claims,'examined_but_not_graded':[{'player_id':curry,'target_ids':target,'claim_ids':['CC06','CB11'],'decision':'Leave unknown; offensive motion is not defensive technique, and one old flat-footed event cannot characterize present skill.'},{'player_id':brunson,'target_ids':['S37','S40'],'claim_ids':['CC07','CB10'],'decision':'Broad defensive weakness and historical charge craft do not identify current shot-contest/closeout magnitude; no short-height or liability-to-zero conversion.'},{'player_ids':[barnes,wemb,gobert],'target_ids':['S45'],'claim_ids':['CC03','CC04','CC05'],'decision':'Useful coverage execution lacks legal-contact versus role/choice exposure detail. No foul-control grade merely from anchor/versatility praise.'}],'shared_trait_policy':'One S37 retained across shot contexts; context-specific evidence limitations belong in reference action/geometry and uncertainty, not a new trait or outcome-fitted shared-grade overwrite.','correlation_policy':'Same commentary and same effective play constrain several stages without independently identifying all raw grades. Change one correlated estimate at a time in later comparisons; report joint uncertainty.','source_hashes':hashes,'readiness_ledger_path':'diagnostics/contest_input_batch_20261116/lineage_ledger.json','operational_input_section':None,'operational_completions':[],'response_coefficients':[],'human_questions_required':[],'independence':{'new_backend_outcomes_inspected':False,'backend_implementation_inspected':False,'profile_compilations':0,'simulations':0,'production_or_save_writes':0},'acquisition_limits':'Three bounded search rounds, then specific accessible written sections. No subscriptions, media review, failed-request loops or current game/dashboard calibration. Closeout-game headlines, offense-only/injury/AI summaries and social comments not used.','validation_scope':'Input schema,94/18-ID preservation, exact base/supported-record lineage, ranges/scales, source hashes and private roundtrips; not compiled consumers or effect calibration.'}
dump(R/'CONTEST_INPUT_BATCH_2026_11_16.json',packet)
dump(D/'lineage_ledger.json',{'packet_version':VERSION,'rows':ledger})
validate_input_section(base);validate_input_section(proposed)
for pid in ids:
 assert base['players'][pid]==snapshot['players'][pid]
 assert set(proposed['players'][pid]['inputs'])==set(defs)
 assert PlayerInputs(proposed['players'][pid]).to_dict()==proposed['players'][pid]
 for k,b in base['players'][pid]['inputs'].items():
  a=proposed['players'][pid]['inputs'][k]
  if b['status']!='unknown' or k.startswith(('P','F','T')):assert a==b
 assert sum(k.startswith('F') for k in proposed['players'][pid]['inputs'])==18
for u in new:
 assert 0<=u['range'][0]<=u['reference']['grade']<=u['range'][1]<=100
 assert u['reference']['scale']==SCALE and set(u['claim_ids'])<=claim_ids
assert all(sha(p)==h for p,h in hashes.items())
dump(D/'validation.json',{'packet_version':VERSION,'status':'PASS','counts':counts,'schema_layers':['base_source_input_section','proposed_source_input_section'],'roundtrips':7,'all658_base_records_exact':True,'all104_supported_records_unchanged':counts['inherited_supported']==104,'physical_passing_tendency_records_exact':True,'only_unknown_grade_cells_filled':True,'declared_ranges_scales_verified':True,'source_hash_checks':{p:sha(p)==h for p,h in hashes.items()},'simulations':0,'profile_compilations':0,'scope':'Research source/schema/lineage validation only.'})
print(json.dumps({'status':'PASS','counts':counts,'new':[(x['name'],x['design_id'],x['range']) for x in new]},ensure_ascii=False))
