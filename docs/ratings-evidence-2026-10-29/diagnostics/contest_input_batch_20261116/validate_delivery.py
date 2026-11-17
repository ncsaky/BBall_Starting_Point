"""Independent contest-proposal artifact checks; no engine/adapters/save calls."""
from pathlib import Path
import hashlib,json,re,sys

ROOT=Path(__file__).resolve().parents[4]
R=ROOT/'docs/ratings-evidence-2026-10-29';D=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.player_model_registry import definition_registry

p=json.loads((R/'CONTEST_INPUT_BATCH_2026_11_16.json').read_text())
snap=json.loads((ROOT/p['inheritance']['snapshot']).read_text())
rows=json.loads((D/'lineage_ledger.json').read_text())['rows']
v=json.loads((D/'validation.json').read_text())
reg=definition_registry();defs={x['id']:x for x in reg['inputs']}
outputs={x['id']:x for x in reg['outputs']}
ids=list(p['base_source_input_section']['players'])
assert len(ids)==7 and len(defs)==94
assert len(rows)==658 and len({(r['player_id'],r['input_id']) for r in rows})==658
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
for section in ['base_source_input_section','proposed_source_input_section']:
 validate_input_section(p[section])
 assert set(p[section]['players'])==set(ids)
changed=[];known_before=0
passing={f'F{i:02d}.{stage}' for i in range(1,10) for stage in ['recognition','execution']}
for pid in ids:
 b=p['base_source_input_section']['players'][pid];a=p['proposed_source_input_section']['players'][pid]
 assert b==snap['players'][pid]
 assert set(a['inputs'])==set(defs) and {k for k in a['inputs'] if k.startswith('F')}==passing
 assert PlayerInputs(a).to_dict()==a
 for k,before in b['inputs'].items():
  after=a['inputs'][k]
  if before['status']!='unknown':known_before+=1;assert after==before
  if k.startswith(('P','F','T')):assert after==before
  if before!=after:
   assert before['status']=='unknown' and defs[k]['kind']=='grade'
   changed.append((pid,k))
assert known_before==104
assert len(changed)==9 and set(changed)=={(u['player_id'],u['design_id']) for u in p['new_estimates']}
assert sum(k in ['S37','S40','S45'] for _,k in changed)==8
assert ('player_tor-scottie-barnes','S46') in changed
assert all(pid!='player_gsw-stephen-curry' for pid,k in changed)
claims={x['id']:x for x in p['claims']}
assert len(claims)==11
for c in claims.values():
 assert c['source_id'] in p['sources']
 assert c['date']==p['sources'][c['source_id']]['date']
 src=p['sources'][c['source_id']]
 if 'path'in src:
  raw=(R/src['path']).read_text()
  for minute in re.findall(r'(\d\d:\d\d):\d\d[–-]',c['locator']):assert minute+':' in raw
for u in p['new_estimates']:
 rec=p['proposed_source_input_section']['players'][u['player_id']]['inputs'][u['design_id']]
 assert rec==u['record'] and rec['value']==u['reference']
 assert u['old_record']==p['base_source_input_section']['players'][u['player_id']]['inputs'][u['design_id']]
 assert 0<=u['range'][0]<=u['reference']['grade']<=u['range'][1]<=100
 assert u['reference']['grade']==sum(u['range'])/2 and u['reference']['scale']==p['technique_scale']['id']
 assert u['direct_or_inferred'] and u['counterevidence'] and u['confidence']['numeric_magnitude']=='low'
 assert set(u['claim_ids'])<=set(claims)
 for e in rec['evidence']:
  if not e['source'].startswith('https://'):assert (R/e['source']).exists() or (ROOT/e['source']).exists()
  assert e['as_of']<'2026-10-20'
for row in rows:
 b=p['base_source_input_section']['players'][row['player_id']]['inputs'][row['input_id']]
 assert digest(b)==row['base_record_sha256']
checks={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in p['source_hashes'].items()}
assert all(checks.values())
links=0;report=R/'CONTEST_INPUT_BATCH_2026_11_16.md'
for link in re.findall(r'\]\(([^)]+)\)',report.read_text()):
 if not link.startswith('https://'):
  assert (report.parent/link.split('#')[0]).exists(),link
  links+=1
assert not p['correction_proposals'] and not p['revision_proposals']
assert p['operational_input_section'] is None and not p['operational_completions'] and not p['response_coefficients']
assert not p['independence']['new_backend_outcomes_inspected'] and p['independence']['simulations']==0
c37=outputs['C37']['dependencies']
supported=sum(p['proposed_source_input_section']['players'][pid]['inputs'][k]['status']!='unknown' for pid in ids for k in c37)
assert supported==20 and 70-supported==50
v['independent_delivery_check']={'status':'PASS','seven_profiles_658_base_records_recompared':True,'104_supported_records_exact':True,'nine_unknown_only_changes_match_proposals':True,'all_physical_passing_tendency_records_preserved':True,'source_dates_ranges_scale_and_claims_valid':True,'C37_supported_cells_after':20,'C37_unknown_cells_after':50,'local_links_resolved':links,'source_hashes_unchanged':all(checks.values()),'scope':'Research schema/lineage/provenance validation only; no runtime compile or numerical effect test.'}
(D/'validation.json').write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':'PASS','new_proposals':9,'inherited_supported_unchanged':104,'source_hashes':len(checks),'links':links}))
