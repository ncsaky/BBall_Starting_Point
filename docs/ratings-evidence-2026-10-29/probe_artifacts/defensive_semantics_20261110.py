from pathlib import Path
import json,copy,hashlib,gzip
from nba_gm_data.save import player_attribute_summary,presentation_rating_value
from nba_gm_data.sim import player_feature_vector,nonlinear_high,nonlinear_low,invalidate_sim_cache
from nba_gm_data.spatial import player_spatial_profile,invalidate_spatial_cache
R=Path('docs/ratings-evidence-2026-10-29/probe_artifacts');root=Path('src/nba_gm_data');files=['traits.py','save.py','sim.py','spatial.py','talent.py','offense.py']
source={f:(root/f).read_bytes() for f in files};b=Path('data/canonical/universe_2026_27_offseason.json').read_bytes();c=json.loads(b)
(R/'defensive_semantics_input_20261110.json.gz').write_bytes(gzip.compress(b))
for f,data in source.items():(R/('defensive_semantics_source_'+f)).write_bytes(data)
out={'version':c['meta']['starting_data_version'],'canonical_sha256':hashlib.sha256(b).hexdigest(),'code_sha256':{f:hashlib.sha256(v).hexdigest() for f,v in source.items()},'thought_experiment':{},'tail':{},'integrity':{}}
for h,pos in [(77,'SG'),(84,'SG'),(77,'C'),(84,'C')]:
 u=copy.deepcopy(c);p=next(p for p in u['players'] if p['name']=='Derrick White');p['height_inches']=h;p['position']=pos
 for t in u['traits']:
  if t['player_id']==p['id'] and t['trait_key']=='rim_deterrence':t['value']=80
 e=player_attribute_summary(u,p['id']);f=player_feature_vector(u,p).features;sp=player_spatial_profile(u,p)
 out['thought_experiment'][f'{h}_{pos}']={'height':h,'position':pos,'engine_def':e['defense'],'engine_ovr':e['overall'],'rim_feature':f['rim_deterrence'],'activity':f['defensive_events'],'impact':f['impact'],'spatial_defense':sp['defense']}
 invalidate_sim_cache(u);invalidate_spatial_cache(u)
for r in [60,68,78,88,90,92,94,97,99]:out['tail'][r]={'rim_feature':nonlinear_high(r,68),'presentation_value':presentation_rating_value(r)}
for a in [30,48,70,90]:out['integrity'][a]={'weak_link':nonlinear_low(a,48),'integrity':100-nonlinear_low(a,48)}
out['code_unchanged_during_calculation']=all((root/f).read_bytes()==v for f,v in source.items())
(R/'defensive_semantics_results_20261110.json').write_text(json.dumps(out,indent=2))
print(out['version'],out['canonical_sha256'],'stable code',out['code_unchanged_during_calculation'])
for k,v in out['thought_experiment'].items():print(k,{x:y for x,y in v.items() if x!='spatial_defense'},v['spatial_defense'].get('restricted_area'))
print('tail',out['tail']);print('integrity',out['integrity'])
