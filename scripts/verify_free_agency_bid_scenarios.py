"""Controlled first-day/day-five bid generation across several seeds."""
from copy import deepcopy
import json
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile
from nba_gm_data import app_actions as aa, play
from nba_gm_data.save import canonical_with_save

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/free-agency-bids-2026-10-25'


def main():
    with ZipFile(OUT/'original-day5.nbagm.zip') as archive:
        name=next(n for n in archive.namelist() if n.endswith('save.json'))
        original=json.loads(archive.read(name))
    canonical=aa.load_app_canonical(ROOT)
    results=[]
    for day,seed in ((1,17),(1,29),(5,17),(5,29)):
        save=deepcopy(original)
        state=save['free_agency_state'];state['day']=day;state.pop('ai_bid_model_versions',None)
        active=canonical_with_save(canonical,save)
        if day==1:
            markets=play.canonical_free_agent_market_by_id(canonical)
            state['player_asks_millions']={p['id']:play.free_agency_initial_ask(p,markets.get(p['id']) or {})
                                         for p in active['players'] if p['id'] in set(save['free_agent_player_ids'])}
        baseline=deepcopy(save)
        started=perf_counter()
        result=play.process_ai_free_agency_offers_for_day_state(canonical,save,'MEM',seed,prepared_active=active)
        elapsed=perf_counter()-started
        new=[o for o in save['free_agent_offers'] if o['status']=='active']
        humans=play.human_controlled_team_ids(save)
        assert not any(o['team_id'] in humans for o in new)
        teams={t['id']:t for t in active['teams']}
        for offer in new:
            reserve=play.active_bid_commitment(save,offer['team_id'],exclude_player_id=offer['player_id'])
            assert play.signing_cap_check(active,save,teams[offer['team_id']]['abbrev'],offer['aav_millions'],reserved_millions=reserve)['ok']
        target=next(p for p in active['players'] if p['name']=='Cason Wallace')
        bids=[o for o in new if o['player_id']==target['id']]
        assert len(bids)>=2,(day,seed,bids)
        replay=deepcopy(baseline)
        play.process_ai_free_agency_offers_for_day_state(canonical,replay,'MEM',seed)
        assert save==replay
        loaded=json.loads(json.dumps(save))
        assert play.process_ai_free_agency_offers_for_day_state(canonical,loaded,'MEM',seed)['created_count']==0
        assert loaded==save
        results.append({'day':day,'seed':seed,'new_bids':result['created_count'],'generation_seconds':round(elapsed,3),
                        'wallace_bids':[(teams[o['team_id']]['abbrev'],o['aav_millions'],o['years']) for o in bids],
                        'funded':True,'repeat_and_reload_equal':True})
        print(results[-1],flush=True)
    (OUT/'scenario-verification.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
