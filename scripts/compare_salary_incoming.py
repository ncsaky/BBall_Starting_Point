"""Explain lost real incoming offers using the exact pre-market snapshot, not later rosters."""
import json
from pathlib import Path
from nba_gm_data import transactions as tx
from nba_gm_data.multi_team_trades import evaluate_multi_team_trade,transfers_for_revalidation
BASE=Path('output/salary-search-stage-b')
def read(p):return json.loads(p.read_text())
def signature(o):
    return json.dumps([sorted((e['from_team_id'],e['to_team_id'],sorted((a['kind'],a['id']) for a in e['assets']))
        for e in tx.trade_transfers(o['proposal'])),o.get('pick_obligation_terms',[])],sort_keys=True)
source=read(BASE/'incoming-snapshot/canonical.json')
active=tx.with_spatial_fit_context(tx.with_transaction_context(source))
old=read(BASE/'incoming-stage-a.json');new=read(BASE/'incoming-stage-b.json')
original=read(Path('output/pick-investment-2026-10-28/stable17/saves/trade_year.json'))
original_ids={o['proposal']['id'] for o in original['user_trade_offers']}
for version,data in (('stage-a',old),('stage-b',new)):
    actual=read(BASE/f'{version}-seed17-1/business.json')
    offers=[o for o in actual['user_trade_offers'] if o['proposal']['id'] not in original_ids]
    assert {signature(o) for o in offers}=={signature(o) for o in data['offers']},version
old_map={signature(o):o for o in old['offers']};new_map={signature(o):o for o in new['offers']}
old_frontier={(r['proposal'].get('from_team_id'),r['proposal'].get('to_team_id')) for r in old['frontier']}
new_frontier={(r['proposal'].get('from_team_id'),r['proposal'].get('to_team_id')) for r in new['frontier']}
lost=[]
for key,o in old_map.items():
    if key in new_map:continue
    p=o['proposal']
    if p.get('transfers'):
        fresh=evaluate_multi_team_trade(active,transfers_for_revalidation(o),pick_rules=o.get('pick_rules'),
            seed=o.get('evaluation_seed',17),date=p['date'],proposal_id=p['id'],include_presentation=False)
    else:
        view=tx.canonical_with_pending_pick_terms(active,o.get('pick_obligation_terms'))
        fresh=tx._evaluate_trade_snapshot(view,p['from_team_id'],p['to_team_id'],
            [{'kind':a['kind'],'value':a['id']} for a in p['from_assets']],
            [{'kind':a['kind'],'value':a['id']} for a in p['to_assets']],seed=o.get('evaluation_seed',17),date=p['date'],config=None,
            context_ready=True,include_presentation=False,proposal_id=o.get('evaluation_proposal_id') or p['id'])
        fresh=tx.candidate_from_decision(fresh)
    valid=tx.ai_trade_candidate_accepted(active,fresh)
    assert valid,(o.get('summary'),fresh)
    first=tx.trade_transfers(p)[0]
    pair=(first['from_team_id'],first['to_team_id'])
    chosen=[r for r in new['selected_frontier'] if (r['proposal'].get('from_team_id'),r['proposal'].get('to_team_id'))==pair]
    probed=[r for r in new['frontier'] if (r['proposal'].get('from_team_id'),r['proposal'].get('to_team_id'))==pair]
    if signature(o) in {signature(c) for c in new['all_proposals']}:
        reason='Offer-capacity displacement: the approved graph remains in the returned candidates, outside the shown offer slots.'
    elif not chosen:
        reason='Frontier displacement: this directed team pair is outside the new bounded 16-pair repair frontier.'
    elif not probed:
        reason='Repair-budget displacement: the pair is retained, but earlier seeds consume the unchanged 64-completion budget.'
    else:
        reason='Repair-seed displacement: the pair is probed from a different quoted package; its bounded completions do not reproduce the old graph.'
    lost.append({'offer':o,'fresh_existing_policy_approved':valid,'fresh_evaluations':fresh['evaluations'],
        'pair':pair,'new_selected_seed':chosen,'pair_probed':bool(probed),'reason':reason})
report={'actual_offer_sets_reproduced':True,'date':source['meta']['current_date'],
        'old_count':len(old['offers']),'new_count':len(new['offers']),
        'old_multi':sum(bool(o['proposal'].get('transfers')) for o in old['offers']),
        'new_multi':sum(bool(o['proposal'].get('transfers')) for o in new['offers']),
        'lost':lost,'gained':[o for key,o in new_map.items() if key not in old_map],
        'old_frontier_pairs':sorted(old_frontier),'new_frontier_pairs':sorted(new_frontier)}
(BASE/'incoming-comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('lost','gained','old_frontier_pairs','new_frontier_pairs')}))
