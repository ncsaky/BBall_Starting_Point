"""Paired bounded market probes, with ordered packages and discovery ledgers."""
import argparse
from collections import Counter
import hashlib,json
from pathlib import Path
import resource,time
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.save import canonical_with_save,load_save
from nba_gm_data.save_recovery import create_export,restore_export
from nba_gm_data import transactions as tx
from nba_gm_data.trade_review import MarketReview
from package_search_diagnostics import instrument

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();args.output.mkdir(parents=True)
base=load_app_canonical(ROOT)
fixtures=[('regular',seed,ROOT/'output/trade-presentation-task-1/fixtures/month17/trade_month.json') for seed in (17,29)]
fixtures += [('deadline',17,ROOT/'output/pick-investment-2026-10-28/stable17/saves/trade_year.json'),
             ('deadline',29,ROOT/'output/trade-presentation-task-1/fixtures/seed29/trade_year.json')]
fixtures += [('offseason',seed,ROOT/f'output/full-year-market-2026-10-27/seed{seed}/phase_saves/summer_before.json') for seed in (17,29)]
report=[]
for phase,seed,source in fixtures:
    folder=args.output/f'{phase}-{seed}';folder.mkdir()
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    path=folder/'career.json';restore_export(path,create_export(source))
    saved=load_save(path);saved['meta']['seed']=seed
    active=canonical_with_save(base,saved)
    metrics=Counter();rejections=Counter();queries=[];review=MarketReview()
    current=saved['state']['current_date'];started=time.perf_counter()
    with instrument(metrics,queries,rejections):
        result=tx.simulate_ai_trades(active,current,current,seed=seed,limit=6,search_depth=2,reserve_assets=True,review=review)
    review.close()
    offers=result['proposals']
    assert all(not tx.multi_team_participation_issues(active,o['proposal']) for o in offers)
    assert all(o['accepted_by_all'] and o['legality']['status']=='legal' for o in offers)
    (folder/'proposals.json').write_text(json.dumps(offers,sort_keys=True))
    (folder/'packages.json').write_text(json.dumps(queries,sort_keys=True))
    row={'phase':phase,'seed':seed,'date':current,'source':str(source),'probe_seconds':time.perf_counter()-started,
         'direct_offers':sum(not bool(o['proposal'].get('transfers')) for o in offers),
         'multi_team_offers':sum(bool(o['proposal'].get('transfers')) for o in offers),
         'accepted_packages':sum(o['accepted_by_all'] for o in offers),
         'shortlisted_protected_variants':sum(any(t.get('type')=='protected_pick' for t in o.get('pick_obligation_terms',[])) for q in queries for o in q['packages']),
         'shortlisted_swap_variants':sum(any(a.get('kind')=='pick_swap' for a in o.get('assets',[])) for q in queries for o in q['packages']),
         'protected_rights':sum(t.get('type')=='protected_pick' for o in offers for t in o.get('pick_obligation_terms',[])),
         'swap_rights':sum(a.get('kind')=='pick_swap' for o in offers for a in tx.trade_assets(o['proposal'])),
         'rejections':dict(rejections),'metrics':dict(metrics),'examples':offers[:2],
         'participants_valid':True,'search_diagnostics':result['search_diagnostics'],'source_unchanged':before==hashlib.sha256(source.read_bytes()).hexdigest()}
    report.append(row);(args.output/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in row.items() if k not in ('examples','rejections')}),flush=True)
report[-1]['max_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
(args.output/'report.json').write_text(json.dumps(report,indent=2))
