"""Counterfactual audit of all lost checkpoint offers against their exact input snapshot."""
import json
from pathlib import Path
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.save import canonical_with_save,load_save
from nba_gm_data import transactions as tx
from nba_gm_data.trade_finance_search import TradeSearchIntent,classify_movements
from nba_gm_data.multi_team_trades import evaluate_multi_team_trade,transfers_for_revalidation

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'output/salary-search-stage-b'
def read(path):return json.loads(path.read_text())
def signature(offer):
    legs=[(t['from_team_id'],t['to_team_id'],sorted((a['kind'],a['id']) for a in t['assets']))
          for t in tx.trade_transfers(offer['proposal'])]
    return json.dumps([sorted(legs),offer.get('pick_obligation_terms',[])],sort_keys=True)
def asset_signature(assets,terms):
    return json.dumps([sorted((a['kind'],a['id']) for a in assets),terms],sort_keys=True)

before=read(BASE/'markets-stage-a/report.json');after=read(BASE/'markets-stage-b/report.json')
canonical=load_app_canonical(ROOT);report=[]
for old,new in zip(before,after):
    assert (old['phase'],old['seed'])==(new['phase'],new['seed'])
    case=f"{old['phase']}-{old['seed']}";seed=old['seed'];current=old['date']
    old_offers=read(BASE/f'markets-stage-a/{case}/proposals.json');new_offers=read(BASE/f'markets-stage-b/{case}/proposals.json')
    old_map={signature(o):o for o in old_offers};new_map={signature(o):o for o in new_offers}
    lost=[o for key,o in old_map.items() if key not in new_map];gained=[o for key,o in new_map.items() if key not in old_map]
    saved=load_save(Path(old['source']));saved['meta']['seed']=seed
    active=tx.with_spatial_fit_context(tx.with_transaction_context(canonical_with_save(canonical,saved)))
    queries=read(BASE/f'markets-stage-b/{case}/packages.json')
    samples=[]
    for offer in lost: # Six original retained offers per case is the fixed bound.
        p=offer['proposal'];evaluation_seed=offer.get('evaluation_seed',seed)
        if p.get('transfers'):
            fresh=evaluate_multi_team_trade(active,transfers_for_revalidation(offer),pick_rules=offer.get('pick_rules'),
                seed=evaluation_seed,date=current,proposal_id=p['id'],include_presentation=False)
            financial='repairable';matched=[];shortlisted=False
        else:
            terms=offer.get('pick_obligation_terms') or offer.get('pick_trade_terms')
            view=tx.canonical_with_pending_pick_terms(active,terms)
            fresh=tx._evaluate_trade_snapshot(view,p['from_team_id'],p['to_team_id'],
                [{'kind':a['kind'],'value':a['id']} for a in p['from_assets']],
                [{'kind':a['kind'],'value':a['id']} for a in p['to_assets']],seed=evaluation_seed,date=current,
                config=None,context_ready=True,include_presentation=False,
                proposal_id=offer.get('evaluation_proposal_id') or p['id'])
            if terms:fresh=tx.trade_result_with_pick_terms(fresh,terms)
            intent=TradeSearchIntent(p['from_team_id'],p['to_team_id'],tuple(p['from_assets']),current)
            financial=classify_movements(active,intent,p['to_assets']).category
            target=sorted(a['id'] for a in p['from_assets'] if a['kind']=='player')
            matched=[q for q in queries if q['buyer']==p['to_team_id'] and q['seller']==p['from_team_id'] and q['target_player_ids']==target]
            wanted=asset_signature(p['to_assets'],terms or [])
            shortlisted=False
            for q in matched:
                for option in q['packages']:
                    specs=option['assets']
                    option_view=tx.canonical_with_pending_pick_terms(active,option.get('pick_obligation_terms'))
                    normalized=tx.normalize_assets(option_view,tx.team_by_id(active,p['to_team_id']),specs)
                    if asset_signature(normalized,option.get('pick_obligation_terms',[]))==wanted:shortlisted=True
        candidate=tx.candidate_from_decision(fresh) if not p.get('transfers') else fresh
        valid=tx.ai_trade_candidate_accepted(active,candidate)
        if not matched:reason='Exploration displacement: another approved offer filled the target/market capacity before this buyer query.'
        elif shortlisted:reason='Selection displacement: the old package remains shortlisted; an earlier approved or reserved package was selected.'
        elif financial=='legal':reason='Shortlist displacement: financially feasible capacity was refilled, including eligible replacement players and legal absorption packages.'
        else:reason='CLASSIFICATION REQUIRES INSPECTION: old valid offer was classified '+financial
        sample={'old_offer':offer,'fresh_legal':fresh['legality'],'fresh_existing_ai_policy_approved':valid,
            'fresh_all_participants_accepted':fresh['accepted_by_all'],
            'fresh_evaluations':fresh['evaluations'],'financial_category':financial,'buyer_query_explored':bool(matched),
            'still_shortlisted':shortlisted,'reason':reason}
        samples.append(sample)
        assert valid,(case,offer.get('summary'),fresh)
        assert financial=='legal' or p.get('transfers'),(case,sample)
    gained_validation=[]
    for offer in gained:
        p=offer['proposal'];evaluation_seed=offer.get('evaluation_seed',seed)
        if p.get('transfers'):
            view=active
            fresh=evaluate_multi_team_trade(view,transfers_for_revalidation(offer),pick_rules=offer.get('pick_rules'),
                seed=evaluation_seed,date=current,proposal_id=p['id'],include_presentation=False)
            candidate=fresh
        else:
            terms=offer.get('pick_obligation_terms') or offer.get('pick_trade_terms')
            view=tx.canonical_with_pending_pick_terms(active,terms)
            fresh=tx._evaluate_trade_snapshot(view,p['from_team_id'],p['to_team_id'],
                [{'kind':a['kind'],'value':a['id']} for a in p['from_assets']],
                [{'kind':a['kind'],'value':a['id']} for a in p['to_assets']],seed=evaluation_seed,date=current,
                config=None,context_ready=True,include_presentation=False,proposal_id=offer.get('evaluation_proposal_id') or p['id'])
            if terms:fresh=tx.trade_result_with_pick_terms(fresh,terms)
            candidate=tx.candidate_from_decision(fresh)
        valid=tx.ai_trade_candidate_accepted(view,candidate)
        assert valid,(case,offer.get('summary'),fresh)
        values=tx.player_asset_values_by_id(view)
        def player_details(assets):
            rows=[]
            for asset in assets:
                if asset['kind']!='player':continue
                player=tx.player_by_id(view,asset['id']);value=values.get(asset['id'],{})
                rows.append({'name':player['name'],'age':player.get('display_age',player.get('age')),
                    **{k:value.get(k) for k in ('on_court_value','playoff_value','health_risk','contract_surplus','development_upside','player_value')}})
            return rows
        guards=[{'team_id':tid,'premium_issue':tx.premium_return_issue(view,tid,incoming,outgoing),
                 'outgoing_players':player_details(outgoing),'incoming_players':player_details(incoming)}
                for tid,outgoing,incoming in tx.trade_team_flows(p)]
        gained_validation.append({'summary':offer.get('summary'),'fresh_existing_policy_approved':valid,
            'fresh_all_participants_accepted':fresh['accepted_by_all'],'evaluations':fresh['evaluations'],'guard_inputs':guards})
    row={'phase':old['phase'],'seed':seed,'date':current,'lost_count':len(lost),'gained_count':len(gained),
         'unchanged_count':len(old_map.keys() & new_map.keys()),'lost':samples,'gained':gained,'gained_validation':gained_validation,
         'before_counts':{k:old[k] for k in ('direct_offers','multi_team_offers','accepted_packages','protected_rights','swap_rights')},
         'after_counts':{k:new[k] for k in ('direct_offers','multi_team_offers','accepted_packages','protected_rights','swap_rights')}}
    report.append(row);(BASE/'discovery-comparison.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in row.items() if k not in ('lost','gained','gained_validation')}),flush=True)
