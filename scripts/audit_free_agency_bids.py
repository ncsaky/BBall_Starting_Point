"""Explain missing FA bids using a disposable snapshot, without advancing it."""
import json
from pathlib import Path
from nba_gm_data import app_actions as aa, play
from nba_gm_data.save import load_save, canonical_with_save, player_display_attribute_summary, player_attribute_summary, team_cap_summary

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/free-agency-bids-2026-10-25'


def audit():
    canonical=aa.load_app_canonical(ROOT)
    save=load_save(OUT/'saves/day5.json')
    active=canonical_with_save(canonical,save)
    state=save['free_agency_state']; day=int(state['day']); seed=7  # GUI action seed.
    pool=[p for p in active['players'] if p['id'] in set(save['free_agent_player_ids'])]
    pool.sort(key=lambda p:play.free_agency_player_priority(active,save,p),reverse=True)
    humans=play.human_controlled_team_ids(save)
    teams=[t for t in active['teams'] if t['id'] not in humans]
    markets=play.canonical_free_agent_market_by_id(canonical)
    report={'date':save['state']['current_date'],'day':day,'pool':len(pool),'all_offers':len(save.get('free_agent_offers',[])),
            'offer_statuses':{},'players':[],'teams':[]}
    for offer in save.get('free_agent_offers',[]):
        status=offer.get('status');report['offer_statuses'][status]=report['offer_statuses'].get(status,0)+1
    for t in teams:
        cap=team_cap_summary(active,save,t['id'],season=play.contract_start_season_for_signing(save))
        report['teams'].append({'team':t['abbrev'],'roster':sum(p.get('team_id')==t['id'] for p in active['players']),
            'tax_space':cap.get('tax_space_millions'),'hard_space':cap.get('hard_cap_space_millions'),
            'reserved':play.active_bid_commitment(save,t['id'])})
    for rank,p in enumerate(pool,1):
        if not any(name in p['name'].lower() for name in ('cason wallace','jimmy butler','cameron johnson')):continue
        ask=state['player_asks_millions'][p['id']]; market=markets.get(p['id']) or {}
        suitors=play.ai_free_agency_suitors(active,save,p,teams,market,seed,day)
        eligible=[]
        for index,t in enumerate(suitors,1):
            reserve=play.active_bid_commitment(save,t['id'],exclude_player_id=p['id'])
            check=play.signing_cap_check(active,save,t['abbrev'],ask,reserved_millions=reserve)
            eligible.append({'rank':index,'team':t['abbrev'],'can_fund_ask':check['ok'],'reason':check.get('message')})
        report['players'].append({'name':p['name'],'age':p['age'],'overall':player_display_attribute_summary(active,p['id'])['overall'],
            'engine_overall':player_attribute_summary(active,p['id'])['overall'],'minutes':play.display_minutes_projection(p),
            'ask':ask,'pool_priority_rank':rank,'desired_bids':play.desired_ai_offer_count(p,ask,day,seed),
            'safe_contract_years':play.extension_safe_year_limit(p,play.contract_start_season_for_signing(save),4),
            'offers':[o for o in save.get('free_agent_offers',[]) if o['player_id']==p['id']], 'suitors':eligible})
    (OUT/'before.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({**{k:v for k,v in report.items() if k not in ('teams','players')},'players':[
        {k:v for k,v in p.items() if k!='suitors'}|{'first_choices':p['suitors'][:p['desired_bids']],
         'funded_teams':[t['team'] for t in p['suitors'] if t['can_fund_ask']]} for p in report['players']]},indent=2),flush=True)


if __name__=='__main__':audit()
