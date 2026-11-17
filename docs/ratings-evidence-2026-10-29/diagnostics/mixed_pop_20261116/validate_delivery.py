"""Validate research deliverables independently of their builder. No engine/saves."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[4]
R=ROOT/'docs/ratings-evidence-2026-10-29'
D=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.player_model_registry import definition_registry

p=json.loads((R/'MIXED_POP_INPUT_UPDATES_2026_11_16.json').read_text())
prior=json.loads((ROOT/p['inheritance']['packet']).read_text())
s=json.loads((D/'source_ledger.json').read_text())
ledger=json.loads((D/'inheritance_ledger.json').read_text())['rows']
validation=json.loads((D/'validation.json').read_text())
defs={d['id']:d for d in definition_registry()['inputs']}
ids=[x['player_id'] for x in p['cohort']]
assert len(set(ids))==4 and len(defs)==94
assert len(ledger)==376 and len({(x['player_id'],x['design_id']) for x in ledger})==376
passing={f'F{i:02d}.{stage}' for i in range(1,10) for stage in ['recognition','execution']}
changes=[]
for layer in ['base_source_input_section','proposed_source_input_section']:
    validate_input_section(p[layer])
    assert set(p[layer]['players'])==set(ids)
for pid in ids:
    b=p['base_source_input_section']['players'][pid]
    a=p['proposed_source_input_section']['players'][pid]
    assert b==prior['proposed_source_input_section']['players'][pid]
    assert PlayerInputs(a).to_dict()==a
    assert set(a['inputs'])==set(defs)
    assert {k for k in a['inputs'] if k.startswith('F')}==passing
    for k,rec in b['inputs'].items():
        new=a['inputs'][k]
        if rec!=new:
            assert rec['status']=='unknown'
            assert defs[k]['kind']=='grade'
            changes.append((pid,k))
        if k in passing or k=='T11' or defs[k]['kind']=='physical':assert new==rec
    assert a['inputs']['T11']['status']=='unknown'
assert set(changes)=={(u['player_id'],u['design_id']) for u in p['new_estimates']}
assert len(changes)==9
claims={c['id']:c for c in s['claims']}
for u in p['new_estimates']:
    rec=p['proposed_source_input_section']['players'][u['player_id']]['inputs'][u['design_id']]
    assert rec==u['record'] and rec['value']==u['reference']
    assert u['range'][0]<=u['reference']['grade']<=u['range'][1]
    assert u['reference']['grade']==sum(u['range'])/2
    assert u['reference']['scale']==p['technique_scale']['id']
    assert u['counterevidence_and_limits'] and u['direct_or_inferred'] and u['confidence']
    assert rec['uncertainty']['confidence']=='low'
    for ref in u['evidence_claim_ids']:
        c=claims[ref]
        assert c.get('player_id')==u['player_id'] or u['player_id'] in c.get('player_ids',[])
        source=s['sources'][c['source_id']]
        assert source['date']<'2026-10-20'
    for e in rec['evidence']:
        if not e['source'].startswith('https://'):
            assert (ROOT/e['source']).exists() or (R/e['source']).exists()
for c in claims.values():
    source=s['sources'][c['source_id']]
    assert c['locator'] and c['direct_or_inferred'] and c['confounds']
    if 'path' in source:
        raw=(R/source['path']).read_text()
        for start in re.findall(r'(\d\d:\d\d:\d\d)[–-]',c['locator']):
            assert start[:6] in raw  # exact range boundary may lie between subtitle cues
map_text=(ROOT/'docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md').read_text()
for k in ['S01','S08','S09','S14','S26','S27','S28','T11']:
    assert f'| {k} |' in map_text
assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in p['source_hashes'].items())
links=0
report=R/'MIXED_POP_INPUT_UPDATES_2026_11_16.md'
for link in re.findall(r'\]\(([^)]+)\)',report.read_text()):
    if not link.startswith('https://'):
        assert (report.parent/link.split('#')[0]).exists(),link
        links+=1
assert p['operational_input_section'] is None
assert not p['proposed_corrections'] and not p['human_questions_required']
assert not p['independence']['milestone11_outcomes_inspected'] and not p['independence']['backend_implementation_inspected']
validation['independent_delivery_check']={'status':'PASS','changed_cells_exactly_match_nine_proposals':True,'all_supported_physical_passing_T11_records_preserved':True,'source_dates_pre_start':True,'retained_source_starting_minutes_present':True,'approved_priority_ID_rows_present':True,'new_evidence_paths_resolve':True,'local_markdown_links_resolved':links,'all_source_hashes_unchanged':True,'new_range_midpoints_recomputed':True,'scope':'Artifact validation, not basketball recertification or runtime testing.'}
(D/'validation.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':'PASS','new_cells':len(changes),'local_links':links,'schema_roundtrips':4,'simulations':0}))
