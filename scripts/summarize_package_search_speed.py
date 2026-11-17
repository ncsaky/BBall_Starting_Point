"""Verify Stage-A ordered packages, business state, events and diagnostic counts."""
import json
from pathlib import Path
import pstats
from statistics import median
BASE=Path('output/package-search-task-3')
def read(folder,name='report.json'):
    return json.loads((BASE/folder/name).read_text())
summary={'stage_b':'design handoff only; no enabled search-policy change','cases':{},'timing':{}}
for case in ('seed17','seed17-repeat','seed29','seed29-repeat','month17','month17-repeat'):
    b,a=read('before-'+case),read('stage-a-'+case)
    assert read('before-'+case,'business.json')==read('stage-a-'+case,'business.json'),case
    assert b['progress_digest']==a['progress_digest'],case
    assert b['source_unchanged'] and a['source_unchanged']
    summary['cases'][case]={'before_seconds':b['seconds'],'stage_a_seconds':a['seconds'],
        'business_equal':True,'ordered_events_equal':True,'frames':a['progress_frames']}
for version in ('before','stage-a'):
    summary['timing'][version]={}
    for case in ('seed17','seed29','month17'):
        values=[read(version+'-'+name)['seconds'] for name in (case,case+'-repeat')]
        summary['timing'][version][case]={'median':median(values),'range':[min(values),max(values)]}
    folder='profile-'+version
    summary[folder]={'seconds':read(folder)['seconds'],'diagnostics':read(folder,'package-diagnostics.json')}
    stats=pstats.Stats(str(BASE/folder/'advance.prof'))
    summary[folder]['calls']={}
    for name in ('buyer_offer_packages_for_value','package_value_for_team','package_value_components',
                 'pick_asset_value','far_future_pick_risk','evaluate_trade_decision','trade_value_breakdown','trade_legality'):
        rows=[v for k,v in stats.stats.items() if k[2]==name]
        summary[folder]['calls'][name]={'calls':sum(v[1] for v in rows),'cumulative_seconds':sum(v[3] for v in rows)}
assert read('profile-before','business.json')==read('profile-stage-a','business.json')
assert read('profile-before')['progress_digest']==read('profile-stage-a')['progress_digest']
b=summary['profile-before']['diagnostics'];a=summary['profile-stage-a']['diagnostics']
for key in ('generator_calls','player_groups','pick_variants','group_variant_pairs','generated_packages','unique_packages','shortlisted_packages','full_evaluations_observed'):
    assert b[key]==a[key],(key,b[key],a[key])
summary['markets']=[]
for old,new in zip(read('markets-before'),read('markets-stage-a')):
    assert (old['phase'],old['seed'])==(new['phase'],new['seed'])
    case=f"{new['phase']}-{new['seed']}"
    assert read('markets-before/'+case,'packages.json')==read('markets-stage-a/'+case,'packages.json'),case
    assert read('markets-before/'+case,'proposals.json')==read('markets-stage-a/'+case,'proposals.json'),case
    assert old['rejections']==new['rejections']
    assert old['source_unchanged'] and new['source_unchanged'] and new['participants_valid']
    summary['markets'].append({k:new[k] for k in ('phase','seed','date','direct_offers','multi_team_offers','accepted_packages',
        'protected_rights','swap_rights','shortlisted_protected_variants','shortlisted_swap_variants','search_diagnostics','rejections','metrics')})
    summary['markets'][-1].update(ordered_packages_equal=True,visible_offers_equal=True,lost=[],gained=[])
summary['app_discovery']={}
inputs={'seed17':'output/pick-investment-2026-10-28/stable17/saves/trade_year.json',
        'seed29':'output/trade-presentation-task-1/fixtures/seed29/trade_year.json',
        'month17':'output/trade-presentation-task-1/fixtures/month17/trade_month.json'}
for case,path in inputs.items():
    source=json.loads(Path(path).read_text()); final=read('stage-a-'+case,'business.json')
    old_offers={o['proposal']['id'] for o in source.get('user_trade_offers',[])}
    offers=[o for o in final.get('user_trade_offers',[]) if o['proposal']['id'] not in old_offers]
    old_logs={o['id'] for o in source.get('transaction_logs',[])}
    logs=[o for o in final.get('transaction_logs',[]) if o['id'] not in old_logs and o.get('transaction_type')=='trade']
    summary['app_discovery'][case]={'new_direct_offers':sum(not bool(o['proposal'].get('transfers')) for o in offers),
        'new_multi_team_offers':sum(bool(o['proposal'].get('transfers')) for o in offers),
        'new_transactions':len(logs),'new_multi_team_transactions':sum(bool(o.get('assets',{}).get('transfers')) for o in logs),
        'offer_examples':offers[:2],'transaction_examples':logs[:2]}
summary['checkpoints']=json.loads((BASE/'checkpoints/checkpoints.json').read_text())
assert all(row['business_equal'] and row['ordered_events_equal'] for row in summary['checkpoints'].values())
(BASE/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
