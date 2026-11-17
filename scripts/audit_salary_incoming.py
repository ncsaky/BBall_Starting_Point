"""Reproduce the actual incoming review and reapprove lost offers from its captured snapshot."""
import argparse,json,inspect
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy
from nba_gm_data import transactions as tx,multi_team_trades as mt
from nba_gm_data.trade_calendar import market_day

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'output/salary-search-stage-b'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--version',choices=('stage-a','stage-b'),required=True)
a=parser.parse_args()
source=json.loads((BASE/'incoming-snapshot/canonical.json').read_text());call=json.loads((BASE/'incoming-snapshot/call.json').read_text())
seed=call['seed'];current=call['through'];year=tx.season_start_from_label(source['meta']['active_season'])
from nba_gm_data.save import trade_deadline_date
market=market_day(current,seed,year,trade_deadline_date(year))
frontier=[];selected=[];original=mt.facilitator_candidates

def probe(c,blocked,**kw):
    if not selected:
        frame=inspect.currentframe().f_back
        retained=frame.f_locals.get('blocked')
        rows=sorted(retained.values(),key=lambda r:r['_repair_rank']) if isinstance(retained,dict) else list(frame.f_locals.get('distinct',{}).values())[:16]
        selected.extend({'proposal':deepcopy(r['proposal']),'rank':r.get('_repair_rank')} for r in rows)
        del frame
    frontier.append({'proposal':deepcopy(blocked['proposal']),'legality':deepcopy(blocked['legality']),
                     'rank':blocked.get('_repair_rank'),'score':blocked.get('combined_score')})
    return original(c,blocked,**kw)
with patch.object(mt,'facilitator_candidates',probe):
    result=tx.simulate_ai_trades(source,current,current,seed=seed,limit=max(12,market['offer_slots']*4),search_depth=2,
        involving_team_ids=set(source['_human_team_ids']))
offers=[o for o in result['proposals'] if set(source['_human_team_ids']) & set(tx.trade_team_ids(o))][:market['offer_slots']]
from nba_gm_data.save import queue_user_trade_offers
queued=json.loads((ROOT/'output/pick-investment-2026-10-28/stable17/saves/trade_year.json').read_text())
old_ids={o['proposal']['id'] for o in queued['user_trade_offers']}
queue_user_trade_offers(queued,deepcopy(offers),current)
new_offers=[o for o in queued['user_trade_offers'] if o['proposal']['id'] not in old_ids]
report={'offers':new_offers,'raw_selected_offers':offers,'all_proposals':result['proposals'],'frontier':frontier,'selected_frontier':selected,'diagnostics':result['search_diagnostics']}
(BASE/f'incoming-{a.version}.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'version':a.version,'offers':len(new_offers),'frontier_seeds':len(frontier),'proposals':len(result['proposals'])}),flush=True)
