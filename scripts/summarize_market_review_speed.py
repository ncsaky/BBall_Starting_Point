"""Verify task-2 state/event parity and report bounded timing/cache evidence."""
import json
from pathlib import Path
import pstats
from statistics import median
BASE=Path('output/market-review-task-2')
def read(folder,name='report.json'):
    return json.loads((BASE/folder/name).read_text())
summary={'cases':{},'timing':{}}
for case in ('seed17','seed17-repeat','seed29','seed29-repeat','month17','month17-repeat'):
    before,after=read('before-'+case),read('after-'+case)
    assert read('before-'+case,'business.json')==read('after-'+case,'business.json'),case
    assert before['progress_digest']==after['progress_digest'],case
    assert before['source_unchanged'] and after['source_unchanged']
    summary['cases'][case]={'before_seconds':before['seconds'],'after_seconds':after['seconds'],
        'business_equal':True,'ordered_events_equal':True,'frames':after['progress_frames']}
for version in ('before','after'):
    summary['timing'][version]={}
    for case in ('seed17','seed29','month17'):
        values=[read(version+'-'+name)['seconds'] for name in (case,case+'-repeat')]
        summary['timing'][version][case]={'median':median(values),'range':[min(values),max(values)]}
for version in ('before','after'):
    folder='profile-'+version
    summary[folder]={'seconds':read(folder)['seconds'],'diagnostics':read(folder,'diagnostics.json')}
    stats=pstats.Stats(str(BASE/folder/'advance.prof'))
    summary[folder]['calls']={}
    for name in ('canonical_with_pending_pick_terms','annotate_pick_obligation_context','build_transaction_context',
                 'strategic_rotation_view','roster_projection','compile_pick_rules','buyer_offer_packages_for_value',
                 'evaluate_trade_decision','trade_value_breakdown','trade_legality','simulate_ai_trades','apply_trade_to_state'):
        rows=[v for k,v in stats.stats.items() if k[2]==name]
        summary[folder]['calls'][name]={'calls':sum(v[1] for v in rows),'cumulative_seconds':sum(v[3] for v in rows)}
assert read('profile-before','business.json')==read('profile-after','business.json')
assert read('profile-before')['progress_digest']==read('profile-after')['progress_digest']
summary['checkpoints']=json.loads((BASE/'checkpoints.json').read_text())
assert all(row['business_equal'] and row['ordered_events_equal'] for row in summary['checkpoints'].values())
(BASE/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
