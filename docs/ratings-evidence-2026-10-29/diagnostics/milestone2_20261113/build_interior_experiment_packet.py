"""Build research-only schema packets and synthetic scenarios. No saves or gameplay calls."""
from pathlib import Path
import json,copy,hashlib,sys
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent;RESEARCH=OUT.parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nba_gm_data.player_model import PlayerInputs,validate_input_section,INPUT_VERSION
from nba_gm_data.player_model_registry import definition_registry,REGISTRY_VERSION
prior=json.loads((RESEARCH/'INTERIOR_DEFENSE_CALIBRATION_PACKET_2026_11_12.json').read_text())
registry=definition_registry();defs={x['id']:x for x in registry['inputs']}
focus=[f'P{i:02}' for i in range(1,13)]+['S30','S31','S32','S33','S34','S35','S36','S37','S38','S39','S40','S41','S44','S45','S46','T13','T15','T16','T17']
assert len(focus)==31 and set(focus)<=set(defs)
scale='research_technique_reference_v0_2026_11_13'
def ev(source,method,date=None,shared=None,notes=None):
 d={'source':source,'method':method}
 if date:d['as_of']=date
 if shared:d['shared_evidence_id']=shared
 if notes:d['notes']=notes
 return d
def unknown(id):return {'status':'unknown','value':None,'reason':f'{id}: no defensible player-specific input value supplied in this bounded packet; approved input retained. Missing physical protocol or technique/preference decomposition is not inferred from legacy effective ratings.','evidence':[],'uncertainty':{'confidence':'unknown','notes':'Unknown player fact; synthetic exploration values are separate scenario assumptions, never silently substituted here.'}}
def estimate(value,evidence,notes,confidence='low'):
 return {'status':'estimated','value':value,'evidence':evidence,'uncertainty':{'confidence':confidence,'notes':notes}}
def physical(metric,val,unit,protocol,interval=None):
 m={'metric':metric,'value':val,'unit':unit,'protocol':protocol}
 if interval:m['interval']=interval
 return {'measurements':[m]}
section={'version':INPUT_VERSION,'registry_version':REGISTRY_VERSION,'players':{}};ranges={};identities={}
for c in prior['cohort']:
 pid=c['canonical_player_id'];ins={id:unknown(id) for id in focus};t=c['reported_physical_tools'];identities[pid]=c['name']
 for id,factor,unit,label in [('P01',2.54,'cm','listed_height'),('P02',2.54,'cm','reported_wingspan'),('P04',.45359237,'kg','listed_body_mass')]:
  val=round(t[id]*factor,6);ins[id]=estimate(physical(label,val,unit,'canonical report, original measurement/footwear/date unverified; exact unit conversion only'),[ev('probe_artifacts/interior_cohort_source_snapshot_20261112.json','convert reported inches×2.54 or pounds×0.45359237; not new anthropometric test','2026-11-12','canonical_reported_tools',f'Original report {t[id]} '+('lb' if id=='P04' else 'in'))],'Copied report with unit conversion; extra decimal places are conversion precision, not body-measurement accuracy. Original measure method/date unknown.','medium')
 for a in c['provisional_input_ranges']:
  id=a['design_id'];lo,hi=a['range'];mid=(lo+hi)/2;ranges.setdefault(pid,{})[id]=a
  ins[id]=estimate({'grade':mid,'scale':scale},[ev(c['scouting']['path'],a['basis'],c['scouting']['published_on'],f'scouting_{pid}',f"Timestamp {c['scouting']['timestamp']}; range {lo}-{hi}. Reasoned technique implication, not independent measurement.")],f'Representative midpoint of provisional range{lo}-{hi}; not a statistical CI or calibrated player fact. Physical/context attribution uncertain. {a["confidence"]}')
 section['players'][pid]={'version':INPUT_VERSION,'registry_version':REGISTRY_VERSION,'player_id':pid,'inputs':ins}
validate_input_section(section)
for doc in section['players'].values():assert PlayerInputs(doc).to_dict()==doc

assumption_source='diagnostics/milestone2_20261113/build_interior_experiment_packet.py'
def assumption(value,note):return estimate(value,[ev(assumption_source,'explicit synthetic mechanism assumption, not observed or scouting-estimated measurement','2026-11-13','synthetic_reference_v1',note)],'EXPERIMENT ONLY. Not a player measurement or production prior. '+note)
def grade(g):return {'grade':g,'scale':scale}
def fixture_physical(id,doc):
 if id=='P03':
  ht=doc['inputs']['P01']['value']['measurements'][0]['value'];sp=doc['inputs']['P02']['value']['measurements'][0]['value'];v=round(ht+70+.5*(sp-ht),3)
  return physical('hypothetical_standing_reach',v,'cm','H1 anthropometric fixture: height+70cm+0.5*(span-height); unvalidated, not inferred player measurement',[v-10,v+10])
 vals={'P05':('reference_acceleration',3.0,'m/s2'),'P06':('reference_running_speed',6.0,'m/s'),'P07':('reference_lateral_speed',2.5,'m/s'),'P08':('reference_contact_force',1000,'N'),'P09':('reference_balance_recovery_time',.5,'s'),'P10':('reference_jump_reach_gain',40,'cm')}
 if id in vals:
  metric,v,unit=vals[id];return physical(metric,v,unit,'DIMENSIONAL FIXTURE ONLY; no actual player/protocol test performed')
 return {'measurements':[],'display_grade':{'grade':50,'scale':'synthetic_capacity_display_proxy_only_v1'}}
def make_reference():
 s=copy.deepcopy(section)
 for doc in s['players'].values():
  for id,record in list(doc['inputs'].items()):
   if record['status']!='unknown':continue
   if defs[id]['kind']=='physical':value=fixture_physical(id,doc)
   elif defs[id]['kind']=='grade':value=grade(70)
   elif id=='T13':value={'reference_conditions':'synthetic controlled defensive miss; opportunity available; not observed preference','rows':[{'condition':'reference_opportunity','probabilities':{'pursue':.5,'box_out':.5}}]}
   elif id=='T15':value={'probability':.5,'reference_conditions':'synthetic eligible help opportunity; scheme held constant, not observed tendency'}
   elif id=='T16':value={'reference_conditions':'synthetic eligible contest; same threat/arrival, not observed preference','rows':[{'condition':'reference_opportunity','probabilities':{'jump':.4,'conservative_contest':.4,'stay_down':.2}}]}
   elif id=='T17':value={'reference_conditions':'synthetic workload allocation, fresh reference state, not observed effort','rows':[{'condition':'reference_workload','probabilities':{'offense':.4,'defense':.4,'transition':.2}}]}
   else:raise ValueError(id)
   doc['inputs'][id]=assumption(value,'Generic controlled reference; no individual inference. Standing reach formula is an unvalidated fixture; conditioning/recovery use display proxies, not invented VO2/rest tests.')
 return s
ref=make_reference();scenarios=[]
def add(id,s,desc):
 validate_input_section(s)
 scenarios.append({'scenario_id':id,'purpose':desc,'classification':'synthetic mechanism exploration, not player calibration','input_section':s})
add('reference_assumptions_v1',ref,'Reported P01/P02/P04 plus8 scouting midpoints; missing inputs filled with transparent common fixtures. H1 reach is not validated anatomy; outcome ranking is hypothesis-dependent.')
equal=copy.deepcopy(ref)
for doc in equal['players'].values():
 for id,metric,v,unit in [('P01','normalized_height',200,'cm'),('P02','normalized_span',210,'cm'),('P03','normalized_reach',280,'cm'),('P04','normalized_mass',100,'kg')]:doc['inputs'][id]=assumption(physical(metric,v,unit,'equal-geometry experimental control, not actual player measurement'),'All players normalized for technique/control comparison; original reports remain in base evidence section.')
add('equal_geometry_control_v1',equal,'Normalize size/reach/mass, preserve technique hypotheses; no real-world player ranking interpretation.')
for suffix,g in [('low_missing_technique',40),('high_missing_technique',90)]:
 s=copy.deepcopy(ref)
 for pid,doc in s['players'].items():
  for id in focus:
   if defs[id]['kind']=='grade' and section['players'][pid]['inputs'][id]['status']=='unknown':doc['inputs'][id]=assumption(grade(g),'Unidentified technique bound for sensitivity; not a player-specific estimate.')
 add(suffix+'_v1',s,'Bound sensitivity to unidentified techniques while preserving sourced/scouted entries.')
for suffix,bound in [('scouting_lower',0),('scouting_upper',1)]:
 s=copy.deepcopy(ref)
 for pid,rr in ranges.items():
  for id,a in rr.items():
   value=a['range'][bound];rec=copy.deepcopy(section['players'][pid]['inputs'][id]);rec['value']['grade']=value;rec['uncertainty']['notes']+=' Experimental scenario selects range endpoint, not a separate fact.';s['players'][pid]['inputs'][id]=rec
 add(suffix+'_v1',s,'Explore documented8 scouting interval endpoints; others remain common assumptions.')
for suffix,probs in [('conservative_contest',{'jump':.1,'conservative_contest':.3,'stay_down':.6}),('aggressive_contest',{'jump':.7,'conservative_contest':.2,'stay_down':.1})]:
 s=copy.deepcopy(ref)
 for doc in s['players'].values():doc['inputs']['T16']=assumption({'reference_conditions':'synthetic matched contest choice under fixed threat/arrival','rows':[{'condition':'reference_opportunity','probabilities':probs}]},'Policy sensitivity only; not observed player preference or foul-control skill.')
 add(suffix+'_v1',s,'Contest-choice sensitivity under matched legal technique and arrival; not intrinsic player labels.')
contexts=[
 {'id':'crowded_paint','conditions':'high interior occupancy; fewer open relocation outlets; matched attacker specified','scouting':'EPISODE_4_CENTERS_EXTRACTION.md 00:17:18-00:38:52 (packed-paint Duren discussion)','claim_type':'offensive context explicit; defending-anchor implications inferred','constraint':'Interior opportunity/shot quality changes; do not hold offense fixed and declare universal anchor dominance.'},
 {'id':'spaced_lineup','conditions':'credible perimeter outlets and open driving lanes, same defender inputs','scouting':'EPISODE_4_CENTERS_EXTRACTION.md 01:35:07-01:45:37 switched-space limit;01:06:54-01:13:07 Bam switching contrast','claim_type':'explicit profile contrasts; lineup effect is reasoned implication','constraint':'Removing paint crowding may change entry frequency, help cost and fouling; new shooting/spacing not yet integrated means magnitude unknown.'},
 {'id':'strong_POA_support','conditions':'primary defender limits initial advantage; anchor source values fixed','scouting':'POINT_GUARDS_FULL_EXTRACTION.md 00:18:37-00:22:05 Castle/Wembanyama context','claim_type':'explicit context; opportunity sensitivity inferred','constraint':'Fewer anchor contests/blocks can accompany equal ability; no raw technique penalty for lower work.'},
 {'id':'weak_POA_support','conditions':'more penetrations/earlier disadvantages; same anchor inputs','scouting':'POINT_GUARDS_FULL_EXTRACTION.md 01:06:18-01:11:36;TEAM_RANKING_FULL_EXTRACTION.md 03:25:17-03:27:02 shielding Brunson','claim_type':'team protection explicit; increased anchor duty inferred','constraint':'More contests/blocks may coexist with worse team outcomes; results not pure anchor talent.'},
 {'id':'pulled_away_from_rim','conditions':'anchor has declared perimeter starting responsibility; recovery path specified','scouting':'EPISODE_4_CENTERS_EXTRACTION.md 01:35:07-01:45:37;01:06:54-01:13:07','claim_type':'space/switch distinctions explicit; scenario-specific effect inferred','constraint':'Starting position reduces available rim coverage without rewriting S36/S37/P03. Bam mobile job and Wembanyama anchor coverage need not keep same ordering.'},
 {'id':'late_help','conditions':'separate recognition delay, start position, travel and controlled arrival','scouting':'POWER_FORWARD_FULL_EXTRACTION.md 01:10:00-01:17:38;SHOOTING_GUARDS_TOP_10_FULL_EXTRACTION.md 01:34-01:44;PG Castle00:18:37-00:22:05','claim_type':'help profiles explicit; timing parameterization hypothetical','constraint':'Grade changes, motion changes and forced delay are different causes. No unsupported observed millisecond delays assigned.'},
 {'id':'threat_mix','conditions':'small quick finisher vs powerful contact finisher vs roller/lob vs shooting center, attacker ability declared','scouting':'EPISODE_4_CENTERS_EXTRACTION.md Zubac/Duren00:17:18-00:38:52 and Chet/Bam00:59:07-01:13:07','claim_type':'profiles explicit, controlled offensive threats synthetic','constraint':'No one universal cohort ordering. New handling/finishing/passing/shooting not implemented means numerical cross-threat calibration deferred.'}]
counts={'players':len(section['players']),'explicit_inputs_per_player':len(focus),'explicit_records':sum(len(x['inputs']) for x in section['players'].values()),'reported_physical_estimates':36,'scouting_technique_estimates':8,'unknown_records':sum(v['status']=='unknown' for d in section['players'].values() for v in d['inputs'].values()),'other_approved_inputs_omitted_as_unknown_per_player':94-len(focus),'scenario_sections':len(scenarios),'context_conditions':len(contexts)}
packet={'packet_version':'research_interior_experiment_inputs_2026_11_13_v1','purpose':'introductory isolated/default-OFF mechanism exploration; not final player/role/league calibration','production_import_authorized':False,'input_version':INPUT_VERSION,'registry_version':REGISTRY_VERSION,'schema_validation_target':'validate_input_section(packet.player_input_section) and every scenarios[].input_section; wrapper is research metadata, not a save section','identities':identities,'counts':counts,'reference_scale':{'id':scale,'meaning':'provisional technique0-100:50 functional reference,75 strong,90 exceptional; not empirical percentile or approved coefficients'},'player_input_section':section,'scouting_ranges':ranges,'unknown_policy':'31 relevant IDs explicitly present; other63 approved IDs absent means unknown under schema, not removed. No numeric defaults in source section.','minimum_dependencies':{'position_contest':['S36','S37','S45','P01','P02','P03','P05','P08','P09','P10','T16'],'arrival':['S38','S39','S40','S41','S44','S46','P02','P03','P05','P06','P07','P09','T15'],'support':['S30','S31','S32','S33','S34','S35','P04','P11','P12','T13','T17'],'note':'approved dependencies retained; fresh reference state may bypass unvalidated physiology, but no field deleted'},'scenarios':scenarios,'context_conditions':contexts,'limits':['Synthetic dimensional fixtures/proxies are not observed protocol tests.','Scouting grade midpoints are uncertain decompositions, not isolated measurements.','No game simulation, final defense-only scale fitting or universal role ordering.','Every context conclusion depends partly on new offense/spacing/other-defense mechanisms; magnitude/calibration remains open.','No BBI paid access or new physical measurements.']}
packet['sensitivity_axes']=[{'id':id,'values':values,'unit':unit,'rule':'change one approved input at a time; hold others/context fixed; synthetic, not observed player range'} for id,values,unit in [('S36',[40,70,90],'grade'),('S37',[40,70,90],'grade'),('S38',[40,70,90],'grade'),('S45',[40,70,90],'grade'),('P03',[-10,0,10],'cm delta to H1 fixture'),('P10',[20,40,60],'cm hypothetical jump reach'),('P05',[1.5,3,4.5],'m/s2 synthetic acceleration')]]
packet['context_sensitivity_axis']={'forced_arrival_delay_seconds':[0,.25,.75],'status':'hypothetical controlled delay, not observed recognition time or fitted relationship'}
(RESEARCH/'INTERIOR_DEFENSE_EXPERIMENT_INPUTS_2026_11_13.json').write_text(json.dumps(packet,indent=2))
(OUT/'source_player_input_section.json').write_text(json.dumps(section,indent=2))
report={'accepted':True,'utility':'nba_gm_data.player_model.PlayerInputs + validate_input_section','version':INPUT_VERSION,'registry_version':REGISTRY_VERSION,'counts':counts,'sections_accepted':1+len(scenarios),'source_section_roundtrip_exact':True,'all94_registry_ids_preserved':len(defs)==94,'registry_sha256':hashlib.sha256((ROOT/'src/nba_gm_data/player_model_registry.py').read_bytes()).hexdigest(),'validator_sha256':hashlib.sha256((ROOT/'src/nba_gm_data/player_model.py').read_bytes()).hexdigest(),'no_save_or_game_calls':True,'meaning':'validation proves storage contract only, not physics, coefficients or player accuracy'}
(OUT/'input_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
