"""Independent artifact checks. Does not call any engine or write a save."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
RESEARCH = ROOT/'docs/ratings-evidence-2026-10-29'
DIAG = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from nba_gm_data.player_model import validate_input_section
from nba_gm_data.player_model_registry import definition_registry

packet = json.loads((RESEARCH/'SCREEN_POP_INPUTS_2026_11_15.json').read_text())
sources = json.loads((DIAG/'source_ledger.json').read_text())
ledger = json.loads((DIAG/'readiness_ledger.json').read_text())
validation = json.loads((DIAG/'validation.json').read_text())
frozen = json.loads((ROOT/packet['inheritance']['packet']).read_text())
canonical = json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text())
defs = {d['id']:d for d in definition_registry()['inputs']}
actors = [a['player_id'] for a in packet['cohort']]
assert len(set(actors)) == 8
assert len(ledger['rows']) == 752
assert len({(r['player_id'],r['design_id']) for r in ledger['rows']}) == 752
for layer in ['base_source_input_section','proposed_source_input_section']:
    section = packet[layer]
    validate_input_section(section)
    assert set(section['players']) == set(actors)
    for pid,p in section['players'].items():
        assert set(p['inputs']) == set(defs) and len(p['inputs']) == 94
        assert sum(cp['id']==pid for cp in canonical['players']) == 1
for pid in actors:
    before = packet['base_source_input_section']['players'][pid]['inputs']
    after = packet['proposed_source_input_section']['players'][pid]['inputs']
    if pid in frozen['proposed_source_input_section']['players']:
        assert before == frozen['proposed_source_input_section']['players'][pid]['inputs']
    for k in defs:
        if before[k]['status'] != 'unknown': assert before[k] == after[k]
        if k.startswith('F'): assert before[k] == after[k]
    assert after['T11']['status'] == 'unknown'
    for k in ['P03','P05','P06','P07','P08','P09']:
        assert after[k]['status'] == 'unknown'
for e in packet['new_estimates']:
    rec = packet['proposed_source_input_section']['players'][e['player_id']]['inputs'][e['design_id']]
    assert rec == e['record']
    if 'range' in e:
        assert e['range'][0] <= rec['value']['grade'] <= e['range'][1]
        assert rec['value']['grade'] == sum(e['range'])/2
        assert rec['value']['scale'] == packet['technique_scale']['id']
    if e['origin'] == 'new_reported_conversion':
        assert rec['value']['measurements'][0]['value'] == round(e['raw_value']*e['conversion_factor'],6)
    for ev in rec['evidence']:
        if not ev['source'].startswith('https://'):
            assert (ROOT/ev['source']).exists() or (RESEARCH/ev['source']).exists()
for path,digest in packet['source_hashes'].items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest
resolved_links = 0
for name in ['SCREEN_POP_INPUTS_2026_11_15.md','SCREEN_POP_READINESS_2026_11_15.md']:
    p = RESEARCH/name
    for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
        if not link.startswith('https://'):
            assert (p.parent/link.split('#')[0]).exists(), link
            resolved_links += 1
for c in sources['claims']:
    assert c['player_id'] in actors and c['source'] in sources['sources']
    s = sources['sources'][c['source']]
    if 'path' in s:
        raw = (RESEARCH/s['path']).read_text()
        # Each starting cue is represented in the retained material (fractional cue exactness is not required).
        start = re.search(r'\d\d:\d\d:\d\d',c['window']).group(0)
        # Broad extraction windows can begin between cues; require a cue in the same minute.
        assert start[:6] in raw
assert packet['operational_input_section'] is None
assert not packet['operational_completions'] and not packet['proposed_source_corrections']
assert not packet['independence']['milestone10_outcomes_inspected']
assert packet['independence']['simulations'] == packet['independence']['profile_compilations'] == 0
validation['independent_delivery_validation'] = {
    'status':'PASS', 'local_markdown_links_resolved':resolved_links,
    'unique_player_field_ledger_rows':752,
    'canonical_id_uniqueness_checked':True,
    'new_record_evidence_paths_resolve':True,
    'transcript_starting_minutes_present':True,
    'unmeasured_physical_controls_not_inserted':True,
    'all_supported_and_passing_records_unchanged':True,
    'grade_midpoints_and_reported_conversions_recomputed':True,
    'scope':'Artifact/schema/reference checks only; not independent basketball recertification, compilation or simulation.'
}
(DIAG/'validation.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':'PASS','local_links':resolved_links,'rows':752,'simulations':0}))
