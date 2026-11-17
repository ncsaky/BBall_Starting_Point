"""Report measured results only after exact paired state/response/memory gates."""
import hashlib,json,re,statistics
from pathlib import Path
base=Path('output/feature-input-pass')
def read(name,file='report.json'):return json.loads((base/name/file).read_text())
def response(name):
    value=read(name,'response.json');value['dashboard_snapshot']['revision']='<file-revision>';value['result']['save']='<disposable-path>';return value
summary={'cases':{},'response_incidental_fields':['dashboard_snapshot.revision','result.save']}
for case in ('seed17','seed29','month17'):
    result={}
    for version in ('before','after'):
        reports=[read(f'{version}-{case}-{i}') for i in (1,2)]
        assert all(not r['profiled'] and not r['reference_search'] and r['source_unchanged'] for r in reports)
        times=[r['seconds'] for r in reports];result[version]={'seconds':times,'median':statistics.median(times),'range':[min(times),max(times)]}
        assert read(f'{version}-{case}-1','business.json')==read(f'{version}-{case}-2','business.json')
        assert reports[0]['progress_digest']==reports[1]['progress_digest']
    for i in (1,2):
        old,new=f'before-{case}-{i}',f'after-{case}-{i}'
        assert read(old,'business.json')==read(new,'business.json'),case
        assert read(old)['progress_digest']==read(new)['progress_digest'],case
        assert response(old)==response(new),case
    result['saved_seconds']=result['before']['median']-result['after']['median']
    result['state_offers_transactions_explanations_events_equal']=True;summary['cases'][case]=result
summary['attribution']={v:read('demand-'+v,'feature-demand.json') for v in ('before','after')}
for v in ('before','after'):
    assert read('demand-'+v)['digest']==read('before-seed17-1')['digest']
    assert read('demand-'+v)['progress_digest']==read('before-seed17-1')['progress_digest']
assert read('profile-after')['digest']==read('before-seed17-1')['digest']
summary['memory']={}
for version in ('before','after'):
    memory=read('memory-'+version,'memory-series.json');release=read('memory-'+version,'feature-release.json')
    assert memory['source_unchanged'] and len(memory['actions'])==3
    for action in memory['actions']:
        assert action['business_digest']==read('before-seed17-1')['digest']
        assert action['events_digest']==read('before-seed17-1')['progress_digest']
        assert action['read_cache_entries']<=2
        assert all(not action['live_before_gc'].get(k,0) for k in ('snapshot','trial','response','event'))
    assert all(not r['live_snapshots_after_return'] for r in release)
    assert all(s.get('features.peak',0)<=8192 and s.get('attributes.peak',0)<=4096 for r in release for s in r['forecast_cache_stats'])
    assert abs(memory['actions'][2]['completion_allocated_blocks']-memory['actions'][1]['completion_allocated_blocks'])<10000
    summary['memory'][version]={'actions':memory,'forecast_release':release}
summary['checkpoints']=read('checkpoints','checkpoints.json');assert all(r['business_equal'] and r['ordered_events_equal'] for r in summary['checkpoints'].values())
summary['tests']={}
for filename in ('feature-tests.txt','regression.txt'):
    log=(base/filename).read_text();assert log.rstrip().endswith('OK')
    summary['tests'][filename]=int(re.search(r'Ran (\d+) tests',log).group(1))
assert sum(summary['tests'].values())==88
assert read('new-career-before','financial.json')==read('new-career-after','financial.json')
assert read('new-career-before','player-card.json')==read('new-career-after','player-card.json')
summary['new_career_financials_and_card_equal']=True
summary['new_career_meaningful_state_equal']=read('.','new-career-parity.json')['business_equal']
assert summary['new_career_meaningful_state_equal']
old=read('.','pre-edit.json');changed=[p for p,h in old.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
assert changed==['src/nba_gm_data/transactions.py'],changed
summary['changed_production_files']=changed
(base/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary['cases'],indent=2))
