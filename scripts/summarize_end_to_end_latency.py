"""Analyze captured latency evidence without advancing any careers."""
from collections import Counter,defaultdict
import argparse,hashlib,json,statistics
from pathlib import Path
from nba_gm_data.save import load_save
from verify_simulation_consistency import business_state,digest,differences

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base',type=Path,default=root/'output/end-to-end-latency')
base=parser.parse_args().base.resolve()
rows=json.loads((base/'wall-control/browser.json').read_text());result={'browser':[],'diagnostics':{},'parity':{}}
for row in rows:
    f=row['frontend'];start=f['requestStart'];events=[e for e in f['parsed'] if e['kind'] in ('date','game')]
    summary={'case':row['name'],'sample':row['sample'],'preflight_seconds':(start-f['clickStart'])/1000,
        'first_meaningful_seconds':(events[0]['at']-start)/1000,
        'max_meaningful_gap_seconds':max([0]+[(b['at']-a['at'])/1000 for a,b in zip(events,events[1:])]),
        'final_bytes_received_seconds':row['network']['chunks'][-1]['at'],
        'result_parsed_seconds':(f['parsedResult']-start)/1000,
        'playback_complete_seconds':(max(e['end'] for e in f['playback'])-start)/1000,
        'advance_return_seconds':(f['advanceReturned']-start)/1000,
        'controls_usable_seconds':(f['usable']-start)/1000,
        'meaningful_events':len(events),'errors':row['errors']}
    assert not f['flags']['busy'] and not f['flags']['sim'] and not f['flags']['hydrating']
    assert not f['reducedMotion'] and not f['flags']['modal']
    assert any(c['visible'] and not c['disabled'] for c in f['controls'])
    assert not row['errors']
    result['browser'].append(summary)
result['wall_time_statistics']={}
for name in ('offday','game','busy','month'):
    warm=[r for r in result['browser'] if r['case']==name and r['sample']!='first-use']
    result['wall_time_statistics'][name]={key:{'median':statistics.median(r[key] for r in warm),
        'range':[min(r[key] for r in warm),max(r[key] for r in warm)],'samples':len(warm)}
        for key in ('first_meaningful_seconds','final_bytes_received_seconds','controls_usable_seconds')}

for path in sorted((base/'diagnostic-server').glob('diag-*.json')):
    d=json.loads(path.read_text());spans=d['nested_spans'];nested=Counter();counts=Counter()
    for span in spans:nested[span['name']]+=span['end']-span['start'];counts[span['name']]+=1
    overlays=[s for s in spans if s['name']=='canonical_with_save'];assert len(overlays)==len(d['overlays'])
    groups=defaultdict(list)
    for o,s in zip(d['overlays'],overlays):groups[o['complete_input_sha256']].append((o,s))
    duplicate_time=sum(s['end']-s['start'] for group in groups.values() for o,s in group[1:])
    summary={'exclusive_phases_seconds':d['exclusive_phases_seconds'],'raw_marks_including_diagnostic_overhead':d['marks'],
        'nested_attribution_not_additive':{k:{'calls':counts[k],'seconds':v} for k,v in nested.items()},
        'overlay_input_groups':len(groups),'duplicate_overlay_calls':sum(len(g)-1 for g in groups.values()),
        'duplicate_overlay_seconds':duplicate_time,'duplicate_groups':[[{'owner':o['owner'],'callers':o['callers'],
            'seconds':s['end']-s['start']} for o,s in group] for group in groups.values() if len(group)>1]}
    total=sum(d['exclusive_phases_seconds'].values());assert abs(total-d['marks']['stream_handler_complete'])<.001
    summary['exclusive_work_seconds_excluding_hashing']=total-d['exclusive_phases_seconds'].get('diagnostic_overhead',0)
    result['diagnostics'][path.stem]=summary

# Resolve the sole complete seven-action restore group. The extra one-action
# controls-tail probe has a different restore prefix and is deliberately separate.
groups=defaultdict(list)
for path in (base/'wall-server/saves').glob('latency_*.json'):
    groups[path.stem.rsplit('_',1)[0]].append(path)
complete=[g for g in groups.values() if len(g)==7];assert len(complete)==1
paths=sorted(complete[0],key=lambda p:int(p.stem.rsplit('_',1)[1]))
expected={}
for name in ('offday','busy','month'):
    reports=[json.loads(p.read_text()) for p in (base/'http-diagnostics').glob(f'diag-{name}-*.json')]
    assert len({r['state_digest'] for r in reports})==1
    expected[name]=reports[0]['state_digest']
state_digests=defaultdict(list)
for row,path in zip(rows,paths):
    state_digests[row['name']].append(digest(business_state(load_save(path,include_history=True))))
first=business_state(load_save(paths[0],include_history=True));warm=business_state(load_save(paths[1],include_history=True))
result['first_use_setup_difference']=differences(first,warm)
assert [d['path'] for d in result['first_use_setup_difference']] in ([],['.starting_lineups.team_gsw'])
result['first_use_setup_difference_note']='Initial browser setup also read team_dashboard, materializing default starting_lineups before timing. Exclude this initial sample from equivalent-state repeat comparisons; do not discard that meaningful field.'
state_digests['offday']=state_digests['offday'][1:]
for name,hashes in state_digests.items():
    assert len(set(hashes))==1
    if name in expected:assert hashes[0]==expected[name]
    result['parity'][name]={'state_digest':hashes[0],'browser_repeats':len(hashes),'http_compared':name in expected,
                           'http_equal':True if name in expected else None}
for name,reference in (('busy','after-seed17-1'),('month','after-month17-1')):
    ref=json.loads((root/'output/context-demand-pass'/reference/'report.json').read_text())
    replay=json.loads(next((base/'http-diagnostics').glob(f'diag-{name}-*.json')).read_text())
    assert replay['state_digest']==ref['digest'] and replay['progress_digest']==ref['progress_digest']
    result['parity'][name]['prior_state_and_ordered_full_events_equal']=True
cases=json.loads((base/'cases.json').read_text())
assert all(hashlib.sha256(Path(c['source']).read_bytes()).hexdigest()==c['source_sha256'] for c in cases.values())
old=json.loads((root/'output/context-demand-pass/comparison.json').read_text())['backend_sources']
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in old.items())
result['source_saves_unchanged']=True;result['backend_sources_equal_completed_pass']=True
(base/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'wall_time_statistics':result['wall_time_statistics'],'parity':result['parity']},indent=2))
