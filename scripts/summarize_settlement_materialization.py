"""Verify exact parity before summarizing separate timing/ownership evidence."""
from pathlib import Path
import hashlib,json,re,statistics

base=Path('output/settlement-materialization-pass')
def read(folder,name='report.json'):return json.loads((base/folder/name).read_text())
def response(folder):
    r=read(folder,'response.json');r['dashboard_snapshot']['revision']='<file-revision>';r['result']['save']='<disposable-path>';return r
summary={'cases':{},'response_incidental_fields':['dashboard_snapshot.revision','result.save']}
summary['tests']={}
for name in ('regression.txt','pick-only-test.txt','additional-regression.txt'):
    log=(base/name).read_text();assert log.rstrip().endswith('OK') and 'FAILED' not in log
    summary['tests'][name]=int(re.search(r'Ran (\d+) test',log).group(1))
assert sum(summary['tests'].values())==201
for case in ('seed17','seed29','month17'):
    row={}
    for version in ('before','after'):
        reports=[read(f'{version}-{case}-{i}') for i in (1,2)]
        assert all(r['source_unchanged'] and not r['profiled'] and not r['reference_search'] for r in reports)
        times=[r['seconds'] for r in reports];row[version]={'samples_seconds':times,'median_seconds':statistics.median(times),'range_seconds':[min(times),max(times)]}
        assert read(f'{version}-{case}-1','business.json')==read(f'{version}-{case}-2','business.json')
        assert reports[0]['progress_digest']==reports[1]['progress_digest']
    for i in (1,2):
        a,b=f'before-{case}-{i}',f'after-{case}-{i}'
        assert read(a,'business.json')==read(b,'business.json'),case
        assert read(a)['progress_digest']==read(b)['progress_digest'],case
        assert response(a)==response(b),case
    row['saved_seconds']=row['before']['median_seconds']-row['after']['median_seconds']
    row['reduction_percent']=100*row['saved_seconds']/row['before']['median_seconds']
    row.update(meaningful_state_equal=True,ordered_full_events_equal=True,exact_response_pairs=2)
    summary['cases'][case]=row
summary['attribution']={}
summary['memory']={}
for version in ('before','after'):
    a=read('attribution-'+version,'settlements.json');summary['attribution'][version]=a
    action=read('attribution-'+version);expected=read('before-seed17-1')
    assert action['digest']==expected['digest'] and action['progress_digest']==expected['progress_digest']
    assert len(a['settlements'])==5 and a['all_context_builds']==8
    assert all(r['builds']==1 and r['status']=='applied' and not r['live_settlement_owners_after_return'] for r in a['settlements'])
    assert a['all_overlays']==(21 if version=='before' else 11)
    assert all(r['overlays']==(3 if version=='before' else 1) for r in a['settlements'])
    a['total_settlement_seconds']=sum(r['seconds'] for r in a['settlements'])
    m=read('memory-'+version,'memory-series.json');l=read('memory-'+version,'settlement-lifetimes.json')
    assert m['source_unchanged'] and len(m['actions'])==4
    expected=read('before-seed17-1')
    for r in m['actions']:
        assert r['business_digest']==expected['digest'] and r['events_digest']==expected['progress_digest']
        assert r['read_cache_entries']<=2
        assert all(not r['live_before_gc'].get(k,0) for k in ('snapshot','trial','response','event'))
    assert all(not r['live_owners'] and not r['live_active_graphs'] for r in l)
    if version=='after':assert all(r['owner_samples']==r['active_graph_samples']==5 for r in l)
    blocks=[r['completion_allocated_blocks'] for r in m['actions'][1:]]
    assert max(blocks)-min(blocks)<10000
    retention=read('retention-'+version,'retention.json')
    assert max(r['retained_python_bytes'] for r in retention['replays'])<100000
    summary['memory'][version]={'whole_actions':m,'settlement_lifetimes':l,'traced_replays':retention}
assert summary['memory']['before']['traced_replays']['digest']==summary['memory']['after']['traced_replays']['digest']
summary['checkpoints']=read('checkpoints','checkpoints.json')
assert all(r['business_equal'] and r['ordered_events_equal'] for r in summary['checkpoints'].values())
old=read('.','pre-edit.json')['backend_sources']
summary['changed_backend_files']=[p for p,h in old.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
assert set(summary['changed_backend_files'])=={'src/nba_gm_data/transactions.py','src/nba_gm_data/trade_roster.py'}
summary['backend_sources']={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in old}
(base/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'cases':summary['cases'],'settlement_attribution':{v:r['total_settlement_seconds'] for v,r in summary['attribution'].items()}},indent=2))
