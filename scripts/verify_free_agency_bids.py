"""Verify current-day catch-up and settlement using real app-action paths."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from nba_gm_data import app_actions as aa
from nba_gm_data.save import load_save
from nba_gm_data.save_recovery import restore_export

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/free-agency-bids-2026-10-25'


def verify(path):
    canonical=aa.load_app_canonical(ROOT)
    before=load_save(path)
    payload={'save_path':str(path),'team':'MEM','seed':7}
    started=perf_counter()
    room=aa.dispatch_app_action('free_agency_room',payload,root=ROOT,save_dir=path.parent,canonical=canonical)
    generated=load_save(path)
    elapsed=perf_counter()-started
    assert generated['state']['current_date']==before['state']['current_date']
    assert generated.get('contract_overrides')==before.get('contract_overrides')
    assert generated.get('transaction_logs')==before.get('transaction_logs')
    assert len(generated['free_agency_state']['ai_days_processed'])==len(before['free_agency_state']['ai_days_processed'])
    assert list(generated['free_agency_state']['ai_bid_model_versions'])==['2026-27:5']
    report={'catch_up_seconds':round(elapsed,3),'new_bids':len(generated['free_agent_offers'])-len(before['free_agent_offers']),
            'players':[]}
    for name in ('Cason Wallace','Jimmy Butler III','Cameron Johnson'):
        candidate=next(p for p in room['candidates'] if p['name']==name)
        offers=[o for o in generated['free_agent_offers'] if o['player_id']==candidate['id'] and o['status']=='active']
        assert offers,(name,candidate)
        report['players'].append({'name':name,'ask':candidate['ask_millions'],'bids':[
            {'team':o['team_id'],'aav':o['aav_millions'],'years':o['years'],'interest':o['interest_score']} for o in offers]})
    marker=path.read_bytes()
    aa.dispatch_app_action('free_agency_room',payload,root=ROOT,save_dir=path.parent,canonical=canonical)
    assert path.read_bytes()==marker
    started=perf_counter()
    result=aa.dispatch_app_action('advance_free_agency',payload,root=ROOT,save_dir=path.parent,canonical=canonical)
    resolved=load_save(path)
    report['resolution_seconds']=round(perf_counter()-started,3)
    report['signed_on_last_day']=result['result']['accepted_count']
    for row in report['players']:
        ids={o['team'] for o in row['bids']}
        accepted=[o for o in resolved['free_agent_offers'] if o['status']=='accepted' and any(
            p['id']==o['player_id'] and p['name']==row['name'] for p in room['candidates'])]
        assert len(accepted)==1,(row['name'],accepted)
        row['signed_with']=accepted[0]['team_id']
        assert row['signed_with'] in ids
    report['repeat_read_idempotent']=True
    (OUT/'verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)


def main():
    with TemporaryDirectory(prefix='bid-verification-',dir=OUT/'saves') as directory:
        path=Path(directory)/'day5.json'
        restore_export(path,(OUT/'original-day5.nbagm.zip').read_bytes())
        verify(path)


if __name__=='__main__':main()
