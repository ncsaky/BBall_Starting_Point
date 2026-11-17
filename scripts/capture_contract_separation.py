"""Disposable real player-card and cap evidence; no simulation."""
import argparse,json
from pathlib import Path
from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.save import load_save,canonical_with_save,team_cap_summary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--canonical',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False);c=json.loads(args.canonical.read_text());root=Path.cwd()
    created=dispatch_app_action('create_save',{'team':'POR','seed':17,'save_name':'career'},root=root,save_dir=args.output,canonical=c)
    path=Path(created['save_path']);s=load_save(path);a=canonical_with_save(c,s)
    card=dispatch_app_action('player_card',{'save_path':str(path),'player_id':'player_por-damian-lillard'},root=root,save_dir=args.output,canonical=c)
    (args.output/'player-card.json').write_text(json.dumps(card,indent=2)+'\n')
    caps={tid:{season:team_cap_summary(a,s,tid,season) for season in ('2026-27','2027-28','2028-29','2029-30','2030-31')} for tid in ('team_por','team_mil')}
    report={'version':s['meta']['starting_data_version'],'date':s['state']['current_date'],'caps':caps,
        'player_contract':next(r for r in a['contracts'] if r['player_id']=='player_por-damian-lillard'),
        'player_team':next(p['team_id'] for p in a['players'] if p['id']=='player_por-damian-lillard'),
        'obligations':[r for r in s.get('waived_salary_obligations',[]) if r.get('player_id')=='player_por-damian-lillard']}
    (args.output/'financial.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'version':report['version'],'player_team':report['player_team'],'obligations':len(report['obligations'])}))

if __name__=='__main__':main()
