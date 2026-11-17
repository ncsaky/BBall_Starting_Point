"""Build milestone11 research artifacts only; no adapters, engines or save access."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
R = ROOT/'docs/ratings-evidence-2026-10-29'
D = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from nba_gm_data.player_model_registry import definition_registry
from nba_gm_data.player_model import PlayerInputs, validate_input_section

VERSION = 'mixed_pop_input_updates_v1_2026_11_16'
SCALE = 'research_technique_reference_v0_2026_11_13'
PREVIOUS = 'docs/ratings-evidence-2026-10-29/SCREEN_POP_INPUTS_2026_11_15.json'
EXPANDED = 'docs/ratings-evidence-2026-10-29/EXPANDED_ACTION_COHORT_2026_11_14.json'
CANONICAL = 'data/canonical/universe_2026_27_offseason.json'
MAP = 'docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md'

def read(p):
    return json.loads((ROOT/p).read_text())

def sha(p):
    return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()

def dump(p,x):
    p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

previous = read(PREVIOUS)
manifest = read('docs/ratings-evidence-2026-10-29/diagnostics/screen_pop_20261115/delivery_manifest.json')
assert sha(PREVIOUS) == next(x['sha256'] for x in manifest['files'] if x['path']==PREVIOUS)
assert sha(EXPANDED) == 'e61a71e7b1225f83c0e357386b98a08ce2a449c310e99f5846b80b00a32755d2'
defs = {d['id']:d for d in definition_registry()['inputs']}
assert len(defs)==94
ids = ['player_mil-myles-turner','player_nyk-karl-anthony-towns','player_okc-chet-holmgren','player_den-nikola-jokic']
names = {x['player_id']:x['name'] for x in previous['cohort']}
canonical = read(CANONICAL)
base = {k:previous['proposed_source_input_section'][k] for k in ['version','registry_version']}
base['players'] = {pid:deepcopy(previous['proposed_source_input_section']['players'][pid]) for pid in ids}
proposed = deepcopy(base)
focus = ['S01','S08','S09','S14','S26','S27','S28','T11']

sources = {
 'CE': {'path':'transcripts/episode4_transcript.txt','date':'2026-09-02','video_id':'CbartUy6cMY','kind':'retained user-supplied timestamped transcript','coverage_this_task':'selected windows, not a new complete episode review','independence_group':'nerd_sesh_retained_commentary'},
 'T30': {'path':'transcripts/episode3_transcript.txt','date':'2026-09-30','kind':'retained user-supplied timestamped transcript','coverage_this_task':'selected Turner context','independence_group':'nerd_sesh_retained_commentary'},
 'T20': {'path':'captions/ZaA4usLpBWI.en.vtt','date':'2026-10-02','video_id':'ZaA4usLpBWI','kind':'retained auto-captions','coverage_this_task':'selected Jokic context','independence_group':'nerd_sesh_retained_commentary'},
 'T10': {'path':'captions/J6STkjbVuUg.en.vtt','date':'2026-10-07','video_id':'J6STkjbVuUg','kind':'retained auto-captions','coverage_this_task':'selected Holmgren context','independence_group':'nerd_sesh_retained_commentary'},
 'TURNER2015': {'url':'https://hoopshabit.com/2015/06/11/scouting-report-myles-turner/','date':'2015-06-11','date_basis':'dated URL/search metadata; college2014–15 context explicit','author':'Ed Isaacson','kind':'original draft scouting, written offense sections reviewed','coverage_this_task':'Post Offense and Perimeter Offense; no media review','independence_group':'isaacson_2015_college_scouting','temporal_limit':'Eleven-year-old college evidence; current continuity is an assumption, not a fresh 2026 observation.'},
 'CHET2024': {'url':'https://www.nba.com/news/what-weve-seen-from-chet-holmgren-this-season','date':'2024-04-11','date_basis':'page Updated on; statistics state through March13','author':'John Schuhmann','kind':'NBA original written action analysis','coverage_this_task':'Film room famous: pop/roll examples; no embedded video review','independence_group':'schuhmann_2024_chet_actions','temporal_limit':'Rookie-season actions, corroborated only broadly by retained2026 role assessment.'},
 'JOKIC2025': {'url':'https://www.nba.com/nuggets/news/first-round-series-preview-4-nuggets-vs-5-clippers','date':'2025-04-17','author':'Matt Brooks','kind':'team-published original written action analysis; opinions not front-office conclusions','coverage_this_task':'three-point/pick-and-pop section; no media review','independence_group':'brooks_nuggets_offense','temporal_limit':'2024–25 season; opportunity quality is a confound, not preparation-speed proof.'},
 'JOKIC2026': {'url':'https://www.nba.com/nuggets/news/first-round-series-preview-3-nuggets-vs-6-timberwolves','date':'2026-04-16','author':'Matt Brooks','kind':'team-published original written action analysis; opinions not front-office conclusions','coverage_this_task':'Chicago-action and jumper sections; no media review','independence_group':'brooks_nuggets_offense','temporal_limit':'Pre-start2025–26 evidence, not post-opener2026–27 performance.'},
 'CATCH_TABLE': {'url':'https://www.nba.com/news/best-shooters-of-the-2024-25-season','date':'2025-04-02','author':'John Schuhmann','kind':'dated NBA tracking-stat table','coverage_this_task':'catch-and-shoot table only; through April1,2025','independence_group':'nba_2025_catch_tracking','correlation':'Earlier cutoff of the same season discussed in JOKIC2025; not an independent skill experiment.'},
 'TOWNS2025': {'url':'https://shaxnba.substack.com/p/anatomy-of-a-possession','date':'2025-12-15','author':'Shax','kind':'original analyst single-possession classification/explanation','coverage_this_task':'public written article; no embedded video or spreadsheet reviewed','independence_group':'shax_single_possession_2025','temporal_limit':'One selected prior-season possession; not1987 Towns screening samples or proof of adaptive reading.'},
}

claims = [
 {'id':'MP01','player_id':ids[0],'source_id':'T30','locator':'00:11:44–00:12:33','direct_assessment':'Turner two-point efficiency reportedly declined outside elite playmaking/infrastructure; contract criticism is separate.','direct_or_inferred':'direct commentator assessment; speaker statistics not independently verified','decision':'counterevidence only; no hands, screen or release deduction from aggregate efficiency','confounds':'pass quality, shot diet, teammates and finishing technique are not isolated'},
 {'id':'MP02','player_id':ids[1],'source_id':'CE','locator':'01:28:30–01:28:53','direct_assessment':'Towns hands praised in high-drop defensive activity/rim-protection context.','direct_or_inferred':'direct defensive assessment, not offensive receiving','decision':'reject transfer to S14; no numerical addition from this passage','confounds':'same word hands refers to a different responsibility'},
 {'id':'MP03','player_id':ids[2],'source_id':'CE','locator':'01:00:07–01:00:35;01:03:46–01:04:23','direct_assessment':'Fluid roller, good open shooter; slow-release access concerns. Speakers disagree about when mechanics changed.','direct_or_inferred':'direct role/shot-access assessment; no timed motion','decision':'retain S01/S08 exactly; corroboration for broad role only','confounds':'catch radius is not independent catch-control skill; lack of time differs from missed open shots'},
 {'id':'MP04','player_id':ids[2],'source_id':'T10','locator':'03:38:49–03:39:50','direct_assessment':'Spurs mismatch and missing secondary creators left Holmgren in an unsuitable advantage-creation responsibility.','direct_or_inferred':'direct matchup/context assessment','decision':'counterevidence to universal offensive downgrade; not independent catch/screen measurement','confounds':'same commentary channel as CE; broad corroboration is correlated'},
 {'id':'MP05','player_id':ids[3],'source_id':'T20','locator':'01:23:38–01:24:14','direct_assessment':'Jokic pulling Wembanyama into space and touch scoring described as a favorable matchup.','direct_or_inferred':'direct broad matchup assessment','decision':'do not infer catch-three grade or S09 from space alone','confounds':'post touch, self-created shots and preparation not separated'},
 {'id':'MP06','player_id':ids[0],'source_id':'TURNER2015','locator':'Post Offense, last paragraphs; Perimeter Offense, first two paragraphs','direct_assessment':'Draft scouting credits generally good hands and perimeter screening, with rushed catching/mechanics errors and a pop-oriented college role.','direct_or_inferred':'direct historical scouting; current S14/S27 continuity is inferred','decision':'new broad S14/S27 hypotheses; S08/S09 remain unknown; qualitative historical tendency only','confounds':'college-to-NBA distance, age, development and scheme; independent of2016 reporting but neither is current2026 evidence'},
 {'id':'MP07','player_id':ids[2],'source_id':'CHET2024','locator':'Film room famous: pick-and-pop and finishing-at-rim examples','direct_assessment':'Holmgren pops against drop and rolls against higher coverage, including a reverse alley-oop.','direct_or_inferred':'written action descriptions; S14/S26/S28 raw decomposition inferred','decision':'three stage-specific broad hypotheses; not a direct screening-contact grade','confounds':'selected successful actions; teammate delivery/coaching and role remain confounds; no media reviewed'},
 {'id':'MP08','player_id':ids[3],'source_id':'JOKIC2025','locator':'pick-and-pop section','direct_assessment':'Jokic catch-three accuracy reported47.3%, mostly pick-and-pop, with an ample-time example.','direct_or_inferred':'reported performance and action context; not measured release speed','decision':'new S01 hypothesis; qualitative context; no S08 or T11 distribution','confounds':'single-season shot quality; no isolated pressure or distance denominator; same underlying season as MP10'},
 {'id':'MP09','player_id':ids[3],'source_id':'JOKIC2026','locator':'Chicago-action section and X factor: jumper section','direct_assessment':'Jokic supplies handoff screens and uses pindowns to reach catch threes.','direct_or_inferred':'written action description; S26 technique magnitude inferred','decision':'new S26 hypothesis; existing S27/S28 receive supplementary provenance without record overwrite','confounds':'same Matt Brooks author as MP08, team perspective, selected actions, not independent universal route samples'},
 {'id':'MP10','player_ids':[ids[1],ids[3]],'source_id':'CATCH_TABLE','locator':'catch-and-shoot table, through April1,2025','direct_assessment':'Through April1,2025: Towns126/268 catch threes; Jokic97/215; league37.4%.','direct_or_inferred':'reported mode-specific realized counts; raw technique remains inferred','decision':'corroborate existing Towns S01 and new Jokic S01; no arithmetic grade conversion','confounds':'historical cutoff, location, pressure and preparation; overlaps MP08 rather than independent confirmation'},
 {'id':'MP11','player_id':ids[1],'source_id':'TOWNS2025','locator':'The Brain, final paragraph; The Heart, example bullet list','direct_assessment':'After ball-screen actions, Towns leaves the dunker spot to set Anunoby a corner pindown; a lightly contested short jumper follows and misses.','direct_or_inferred':'one analyst-described sequence; S27/S28 grades inferred','decision':'broad execution/sequence-reading hypotheses, not shot-outcome grading','confounds':'called set versus adaptive read; no legal-contact success rate; passing/shot belong to Brunson/Anunoby, not Towns'},
]
by_claim={c['id']:c for c in claims}
source_paths = [PREVIOUS,EXPANDED,CANONICAL,MAP,'src/nba_gm_data/player_model.py','src/nba_gm_data/player_model_registry.py','docs/ratings-evidence-2026-10-29/SCREEN_POP_INPUTS_2026_11_15.md','docs/ratings-evidence-2026-10-29/SCREEN_POP_READINESS_2026_11_15.md','docs/ratings-evidence-2026-10-29/diagnostics/screen_pop_20261115/source_ledger.json','docs/ratings-evidence-2026-10-29/diagnostics/screen_pop_20261115/readiness_ledger.json']
source_paths += ['docs/ratings-evidence-2026-10-29/'+s['path'] for s in sources.values() if 'path' in s]
source_hashes={p:sha(p) for p in source_paths}
updates=[]

def add(pid,k,bounds,refs,inference,limits):
    assert base['players'][pid]['inputs'][k]['status']=='unknown'
    assert defs[k]['kind']=='grade'
    value={'grade':sum(bounds)/2,'scale':SCALE}
    evidence=[]
    for ref in refs:
        c=by_claim[ref];s=sources[c['source_id']]
        evidence.append({'source':s.get('path',s.get('url')),'as_of':s['date'],'method':'specific dated source context with explicit provisional raw-technique inference','shared_evidence_id':s['independence_group'],'notes':ref+'; '+c['locator']+'; claim/limits in mixed_pop_20261116 source ledger.'})
    record={'status':'estimated','value':value,'evidence':evidence,'uncertainty':{'confidence':'low','notes':f'Provisional range{bounds[0]}–{bounds[1]}, not probability/percentile/statistical CI. {inference} {limits}'}}
    proposed['players'][pid]['inputs'][k]=record
    updates.append({'player_id':pid,'name':names[pid],'design_id':k,'prior_status':'unknown','range':bounds,'reference':value,'evidence_claim_ids':refs,'direct_or_inferred':'inferred raw magnitude from specified direct action/scouting context','inference':inference,'counterevidence_and_limits':limits,'confidence':'low; historical continuity/single-action decomposition explicit','record':record})

add(ids[0],'S14',[55,80],['MP06','MP01'],'Tentative catch-control continuity hypothesis; this is not a total-turnover or finishing grade.','Historical-only positive raw support with rushing caveat; no current receiving-denial sample. Current role context does not verify hands. No assumption that immature errors persisted unchanged.')
add(ids[0],'S27',[50,80],['MP06'],'Functional-to-strong screening hypothesis with unusually broad uncertainty.','2015 assessment is not proof of present contact/legality. Prior2016 whiff/endurance caveats remain in inherited evidence; no mass-derived technique and no inferred developmental improvement.')
add(ids[1],'S27',[55,80],['MP11'],'Broad placement/timing execution hypothesis from an actual described screening sequence.','One called off-ball screen, not a measured on-ball contact/legality rate. Shared field spans contexts, so transfer to ball screening is tentative. The miss is not a negative screen grade.')
add(ids[1],'S28',[55,80],['MP11'],'Broad follow-up sequencing hypothesis; executing the next screen at the right phase can support functional recognition.','Called sequence is not proof of autonomous coverage adaptation or pop selection. Shares one observation with S27; not two independent measurements. No top-tier magnitude or universal timing claim.')
add(ids[2],'S14',[65,87],['MP07','MP03'],'Broad useful-reception hypothesis from an aerial action plus retained effective-roll context, rather than from height.','Reception inferred within a described play, not an isolated hands assessment; pass quality and successful-example selection confound magnitude. Difficult-pass reliability remains uncertain; no finishing bonus from S14.')
add(ids[2],'S26',[60,82],['MP07'],'Shooting-route timing/arrival hypothesis; movement capacity and shot accuracy are separate.','Historical selected action and current general-role continuity, not measured route disguise or speed. Do not raise S08 to erase the independently retained release-access concern.')
add(ids[2],'S28',[60,84],['MP07','MP04'],'Broad conditional-follow-up hypothesis across coverage contexts.','Coaching and creator availability confound autonomy. No recognition latency, optimal decision rate or numeric tendency inferred. S27 contact remains unknown.')
add(ids[3],'S01',[75,93],['MP08','MP10'],'Strong-to-exceptional reference catch-shot hypothesis on the inherited research scale.','Selected past-season performance is not a current calibrated probability. Source counts overlap season context; not independent trials. No rank-to-grade or percentage-to-grade formula and no guaranteed advantage over Towns.')
add(ids[3],'S26',[70,90],['MP09'],'Useful-to-exceptional shooting-route technique hypothesis; not a physical-speed or movement-shot accuracy grade.','Specific pre-start action support; screener, passer and defender contribute. Selected examples do not measure universal route success, release speed or range extension.')

qualitative_tendencies=[
 {'player_id':ids[0],'claim_ids':['MP06'],'date':'2015-06-11','observation':'College-era pop favored over roll in this scouting account.','scope':'historical qualitative deployment only; no asserted current2026 preference or numerical distribution'},
 {'player_id':ids[1],'claim_ids':['MP11'],'date':'2025-12-15','observation':'Layered off-ball screening appears in one set.','scope':'evidence of a called role, not a screen/roll/pop/slip preference ordering'},
 {'player_id':ids[2],'claim_ids':['MP07'],'date':'2024-04-11','observation':'Coverage-conditioned alternatives documented.','scope':'conditional repertoire, not observed action shares or an innate pop-first preference'},
 {'player_id':ids[3],'claim_ids':['MP08','MP09'],'date':'2026-04-16','observation':'Historical pop and shooting-route contexts are usable roles.','scope':'catch-shot exposure is not the denominator for all screen follow-ups; no numeric T11 estimate'},
]

ledger=[];summary=[]
for pid in ids:
    new=[u['design_id'] for u in updates if u['player_id']==pid]
    inp=proposed['players'][pid]['inputs']
    summary.append({'player_id':pid,'name':names[pid],'before_known':sum(v['status']!='unknown' for v in base['players'][pid]['inputs'].values()),'new_ids':new,'after_known':sum(v['status']!='unknown' for v in inp.values()),'still_unknown_focus':[k for k in focus if inp[k]['status']=='unknown']})
    for k,d in defs.items():
        b=base['players'][pid]['inputs'][k];a=inp[k]
        origin='new_inference' if k in new else 'inherited_supported' if b['status']!='unknown' else 'source_unknown'
        ledger.append({'player_id':pid,'design_id':k,'meaning':d['meaning'],'kind':d['kind'],'before_status':b['status'],'after_status':a['status'],'origin':origin,'focus':k in focus,'before_record_sha256':hashlib.sha256(json.dumps(b,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'after_record_pointer':f'/proposed_source_input_section/players/{pid}/inputs/{k}'})
counts={'players':4,'dimensions_per_player':94,'passing_dimensions_per_player':18,'records_per_layer':376,'inherited_supported':sum(s['before_known'] for s in summary),'new_estimates':len(updates),'known_after':sum(s['after_known'] for s in summary),'source_claims':len(claims),'numeric_tendency_additions':0,'operational_completions':0}
counts['unknown_after']=376-counts['known_after']
packet={'packet_version':VERSION,'input_version':base['version'],'registry_version':base['registry_version'],'production_import_authorized':False,'date_policy':{'target':'October2026 immediately before regular-season opener','cutoff':'No post-opener2026–27 performance used; dated2015/2024/2025 history kept distinct from2026 corroboration. No hidden July restart or forecast-to-skill conversion.','health':'healthy ability only; no new availability/medical audit'},'technique_scale':deepcopy(previous['technique_scale']),'cohort':[deepcopy(x) for x in previous['cohort'] if x['player_id'] in ids],'counts':counts,'inheritance':{'packet':PREVIOUS,'packet_version':previous['packet_version'],'sha256':source_hashes[PREVIOUS],'section':'proposed_source_input_section','policy':'All376 inherited records copied exactly into base; supported records unchanged in proposed. Only nine unknown grade cells are filled.'},'base_source_input_section':base,'proposed_source_input_section':proposed,'new_estimates':updates,'supplemental_evidence_without_record_overwrite':[{'player_id':ids[1],'design_ids':['S01'],'claim_ids':['MP10'],'purpose':'additional dated support only'},{'player_id':ids[2],'design_ids':['S01','S08'],'claim_ids':['MP03','MP04'],'purpose':'retain open-shot versus preparation distinction; source history disagreement explicit'},{'player_id':ids[3],'design_ids':['S27','S28'],'claim_ids':['MP09'],'purpose':'additional action context, correlated with new route evidence; no grade revision'}],'qualitative_tendencies':qualitative_tendencies,'proposed_corrections':[],'human_questions_required':[],'operational_input_section':None,'source_ledger_path':'diagnostics/mixed_pop_20261116/source_ledger.json','inheritance_ledger_path':'diagnostics/mixed_pop_20261116/inheritance_ledger.json','before_new_unknown':summary,'source_hashes':source_hashes,'independence':{'milestone11_outcomes_inspected':False,'backend_implementation_inspected':False,'source_schema_and_registry_only':True,'profile_compilations':0,'simulations':0,'production_or_save_writes':0},'validation_scope':'Sparse source-schema validation, immutable roundtrips, approved IDs/semantics, provenance, ranges and frozen hashes only; no runtime compilation or consumer-readiness claim.'}
dump(R/'MIXED_POP_INPUT_UPDATES_2026_11_16.json',packet)
dump(D/'source_ledger.json',{'packet_version':VERSION,'sources':sources,'claims':claims,'coverage':'Targeted transcript windows and written sections only; no new complete episode or audiovisual review. Speakers unidentified/local turns.','correlation_policy':'Same-channel commentary is not independent replication. Brooks2025/2026 share author/publisher; same-season NBA catch counts overlap. Shared groups stay correlated across receiving/route/read inferences.','lookup_limits':{'search_rounds':3,'failed':[{'url':'https://sports.yahoo.com/the-knicks-two-man-game-of-karl-anthony-towns-and-jalen-brunson-is-all-out-frightening-171232563.html','status':'429; no retry; unavailable body not used for numerical estimates'}],'not_used':'Search-only social comments, unrelated injury/defensive-hands stories, generic secondary estimates, post-start game pages and inaccessible bodies. No subscription, downloads or broad campaign.','stop':'Targeted acquisition ended before packet construction.'}})
dump(D/'inheritance_ledger.json',{'packet_version':VERSION,'rows':ledger})

validate_input_section(base);validate_input_section(proposed)
for pid in ids:
    assert sum(p['id']==pid for p in canonical['players'])==1
    assert set(proposed['players'][pid]['inputs'])==set(defs)
    assert base['players'][pid]==previous['proposed_source_input_section']['players'][pid]
    assert PlayerInputs(proposed['players'][pid]).to_dict()==proposed['players'][pid]
    for k,b in base['players'][pid]['inputs'].items():
        a=proposed['players'][pid]['inputs'][k]
        if b['status']!='unknown' or k.startswith('F') or k=='T11':assert a==b
    assert sum(k.startswith('F') for k in proposed['players'][pid]['inputs'])==18
for u in updates:
    assert 0<=u['range'][0]<=u['reference']['grade']<=u['range'][1]<=100
    assert u['reference']['scale']==SCALE
    assert all(c in by_claim for c in u['evidence_claim_ids'])
checks={p:sha(p)==h for p,h in source_hashes.items()}
assert all(checks.values())
validation={'packet_version':VERSION,'status':'PASS','counts':counts,'schema_layers':['base_source_input_section','proposed_source_input_section'],'immutable_roundtrips':4,'canonical_ids_unique':True,'all94_and18_passing_fields_retained':True,'all376_base_records_exact':True,'all35_supported_records_unchanged':counts['inherited_supported']==35,'passing_and_T11_records_exact':True,'grades_fill_unknowns_only':True,'range_scale_type_unit_checks':True,'source_hash_checks':checks,'profile_compilations':0,'simulations':0,'actual_consumer_interface_verified':False,'scope':'Source-schema and research-artifact checks only.'}
dump(D/'validation.json',validation)
print(json.dumps({'status':'PASS','counts':counts,'per_player':summary},ensure_ascii=False))
