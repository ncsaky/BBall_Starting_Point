"""Validate fixed evidence/dependency/readiness artifacts without any engine calls."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[4]
R=ROOT/'docs/ratings-evidence-2026-10-29'
D=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from nba_gm_data.player_model_registry import definition_registry
from nba_gm_data.player_model import PlayerInputs,validate_input_section

p=json.loads((R/'PERIMETER_CONTEST_EVIDENCE_2026_11_16.json').read_text())
s=json.loads((D/'inherited_source_snapshot.json').read_text())
rows=json.loads((D/'readiness_ledger.json').read_text())['rows']
v=json.loads((D/'validation.json').read_text())
reg=definition_registry();defs={d['id']:d for d in reg['inputs']};outs={d['id']:d for d in reg['outputs']}
assert len(defs)==94
assert set(p['approved_C37_definition']['dependencies'])==set(outs['C37']['dependencies'])
assert p['approved_C37_definition']==outs['C37']
validate_input_section(s)
assert len(s['players'])==9 and len(rows)==846
assert len({(r['player_id'],r['input_id']) for r in rows})==846
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
for l in p['source_profile_lineage']:
 source=json.loads((ROOT/l['packet']).read_text())
 pl=s['players'][l['player_id']]
 assert pl==source[l['section']]['players'][l['player_id']]
 assert set(pl['inputs'])==set(defs)
 assert sum(k.startswith('F') for k in pl['inputs'])==18
 assert PlayerInputs(pl).to_dict()==pl
 assert digest(pl)==l['profile_sha256']
for row in rows:
 rec=s['players'][row['player_id']]['inputs'][row['input_id']]
 assert row['source_record_sha256']==digest(rec) and row['status']==rec['status']
 assert not row['changed']
claims={c['id']:c for c in p['claims']}
assert len(claims)==13
for c in claims.values():
 assert set(c['approved_input_ids'])<=set(defs)
 assert c['source_id'] in p['sources'] and c['locator'] and c['cannot_establish']
 assert c['date']==p['sources'][c['source_id']]['date'] and c['numeric_effect'] is None
 src=p['sources'][c['source_id']]
 if 'path' in src:
  raw=(R/src['path']).read_text()
  for minute in re.findall(r'(\d\d:\d\d):\d\d[–-]',c['locator']):assert minute+':' in raw
for stage in p['dependency_stages']:
 assert set(stage['inputs'])<=set(defs) and set(stage['derived_ids'])<=set(outs)
 assert set(stage['support_claims'])<=set(claims)
defenders=[x for x in p['readiness'] if x['defender_C37']]
shooters=[x for x in p['readiness'] if x['shooter_branch']]
assert len(defenders)==7 and len(shooters)==4
supported=0
for r in p['readiness']:
 inp=s['players'][r['player_id']]['inputs']
 for name in ['defender_C37','shooter_branch']:
  if not r[name]:continue
  x=r[name];keys=x['direct_ids'] if name=='defender_C37' else x['ids']
  assert set(x['supported'])=={k for k in keys if inp[k]['status']!='unknown'}
  assert set(x['unknown'])=={k for k in keys if inp[k]['status']=='unknown'}
  if name=='defender_C37':supported+=len(x['supported'])
assert supported==12 and 70-supported==58
cn={c['id']:c for c in p['constraints']}
assert cn['CN01']['value']==3.5 and cn['CN01']['kind']=='definition_only'
for row in cn['CN02']['rows']:
 assert 0<=row['made']<=row['attempted'] and row['attempted']>0
 assert abs(row['derived_FG_pct']-100*row['made']/row['attempted'])<1e-12
assert [round(x['derived_FG_pct'],1) for x in cn['CN02']['rows']]==[39.0,43.1]
assert all(not x['causal_response_calibration'] for x in cn.values())
checks={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h for path,h in p['source_hashes'].items()}
assert all(checks.values())
links=0
report=R/'PERIMETER_CONTEST_EVIDENCE_2026_11_16.md'
for link in re.findall(r'\]\(([^)]+)\)',report.read_text()):
 if not link.startswith('https://'):
  assert (report.parent/link.split('#')[0]).exists(),link
  links+=1
assert not p['player_input_additions'] and not p['proposed_corrections'] and not p['operational_completions'] and not p['numeric_effect_coefficients']
assert not p['independence']['new_backend_outcomes_inspected'] and not p['independence']['backend_implementation_inspected']
v['independent_delivery_check']={'status':'PASS','846_source_records_recompared':True,'all_passing_fields_retained':True,'C37_and_all_stage_references_checked':True,'seven_defender_four_shooter_roles_checked':True,'12_supported_58_unknown_direct_cells_recomputed':True,'historical_percentages_recomputed':[39.0,43.1],'local_links_resolved':links,'source_hashes_unchanged':all(checks.values()),'scope':'Source/schema/ledger arithmetic validation; no actual profile compilation, mechanism coefficients or simulations.'}
(D/'validation.json').write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':'PASS','records':846,'source_hashes':len(checks),'links':links,'C37_supported':12,'C37_unknown':58}))
