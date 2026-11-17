"""Record real standard/fantasy setup only; never advance historical calendars."""
import argparse,hashlib,json
from pathlib import Path
from nba_gm_data.app_actions import dispatch_app_action,load_app_canonical
from nba_gm_data.save import load_save

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    b=p.parse_args().output.resolve();b.mkdir(parents=True,exist_ok=False);root=Path.cwd();canonical=load_app_canonical(root)
    source_hash=hashlib.sha256(json.dumps(canonical['contracts'],sort_keys=True).encode()).hexdigest();rows={}
    for mode in ('standard','fantasy_draft'):
        result=dispatch_app_action('create_save',{'team':'GSW','seed':17,'game_mode':mode,'save_name':mode},root=root,save_dir=b,canonical=canonical)
        path=Path(result['save_path']);saved=load_save(path,include_history=True)
        row={'created_date':saved['state']['current_date'],'initial_phase':saved['state']['phase'],
             'welcome_date':saved['inbox_items'][0]['date'],'source_snapshot_date':saved['meta'].get('source_snapshot_date'),
             'first_league_game':min(g['gameDate'] for g in saved['season_schedules']['2026-27']['games']),
             'initial_game_count':len(saved['game_results']),'initial_transactions':len(saved['transaction_logs']),
             'initial_development_count':len(saved['development_events']),'initial_plan_count':len(saved.get('team_plans',{}))}
        if mode=='fantasy_draft':
            dispatch_app_action('fantasy_draft_sim_all',{'save_path':str(path)},root=root,save_dir=b,canonical=canonical)
            saved=load_save(path,include_history=True)
            row['completion_date']=saved['state']['current_date'];row['selections']=saved['fantasy_draft_state']['selections']
            row['contract_overrides_after_draft']=saved['contract_overrides']
        rows[mode]=row
    assert source_hash==hashlib.sha256(json.dumps(canonical['contracts'],sort_keys=True).encode()).hexdigest()
    rows['source_contracts_sha256']=source_hash
    (b/'setup.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps({m:{k:v for k,v in r.items() if k!='selections'} if isinstance(r,dict) else r for m,r in rows.items()}))

if __name__=='__main__':main()
