"""Require all exact pairs before reporting unprofiled timing or memory results."""
import hashlib,json,re,statistics
from pathlib import Path
base=Path('output/market-repeat-pass')
def read(name,file='report.json'):return json.loads((base/name/file).read_text())
def response(name):
    value=read(name,'response.json')
    value['dashboard_snapshot']['revision']='<file-revision>'
    value['result']['save']='<disposable-path>'
    return value
summary={'cases':{},'response_incidental_fields':['dashboard_snapshot.revision','result.save']}
for case in ('seed17','seed29','month17'):
    result={}
    for version in ('before','after'):
        reports=[read(f'{version}-{case}-{i}') for i in (1,2)]
        assert all(not r['profiled'] and not r['reference_search'] and r['source_unchanged'] for r in reports)
        times=[r['seconds'] for r in reports]
        result[version]={'seconds':times,'median':statistics.median(times),'range':[min(times),max(times)]}
        assert read(f'{version}-{case}-1','business.json')==read(f'{version}-{case}-2','business.json')
        assert reports[0]['progress_digest']==reports[1]['progress_digest']
    for i in (1,2):
        old,new=f'before-{case}-{i}',f'after-{case}-{i}'
        assert read(old,'business.json')==read(new,'business.json'),case
        assert read(old)['progress_digest']==read(new)['progress_digest'],case
        assert response(old)==response(new),case
    result['saved_seconds']=result['before']['median']-result['after']['median']
    result['state_offers_transactions_explanations_events_equal']=True
    summary['cases'][case]=result
summary['attribution']={v:read('diagnostic-'+v,'repeat-diagnostics.json') for v in ('before','after')}
for v in ('before','after'):
    assert read('diagnostic-'+v)['digest']==read('before-seed17-1')['digest']
    assert read('diagnostic-'+v)['progress_digest']==read('before-seed17-1')['progress_digest']
summary['memory']={}
for version in ('before','after'):
    memory=read('memory-'+version,'memory-series.json');quotes=read('memory-'+version,'quote-release.json')
    assert memory['source_unchanged'] and len(memory['actions'])==3
    for action in memory['actions']:
        assert action['business_digest']==read('before-seed17-1')['digest']
        assert action['events_digest']==read('before-seed17-1')['progress_digest']
        assert action['read_cache_entries']<=2
        assert all(not action['live_before_gc'].get(k,0) for k in ('snapshot','trial','response','event'))
    assert all(not q['live_views_after_return'] for q in quotes)
    assert abs(memory['actions'][2]['completion_allocated_blocks']-memory['actions'][1]['completion_allocated_blocks'])<10000
    summary['memory'][version]={'actions':memory,'quotes':quotes}
summary['checkpoints']=read('checkpoints','checkpoints.json')
assert all(r['business_equal'] and r['ordered_events_equal'] for r in summary['checkpoints'].values())
log=(base/'regression.txt').read_text();assert log.rstrip().endswith('OK')
summary['focused_tests']=int(re.search(r'Ran (\d+) tests',log).group(1))
old=read('.','pre-edit.json');changed=[p for p,h in old.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
assert set(changed)=={'src/nba_gm_data/transactions.py','src/nba_gm_data/trade_pick_terms.py'},changed
summary['changed_production_files']=changed
(base/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary['cases'],indent=2))
