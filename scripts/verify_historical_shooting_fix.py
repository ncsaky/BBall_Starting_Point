"""Offline retained-source proof and legacy quarantine audit; never writes source cache."""
import argparse
import hashlib
import json
from pathlib import Path
from nba_gm_data.research import parse_espn_summary_boxscore
from nba_gm_data.historical_shooting import historical_shooting_view,PARSER_VERSION,strict_pair

ROOT=Path(__file__).resolve().parents[1]
SAMPLES=ROOT/'docs/ratings-evidence-2026-10-29/diagnostics/milestone2_20261113'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'output/historical-shooting-import-fix-2026-11-13');out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    path=ROOT/'data/research/game_boxscores_2025_26.json';raw_cache=path.read_bytes();cache=json.loads(raw_cache)
    samples=[];source_matches=0;dnp=0;active=0
    qa=json.loads((SAMPLES/'historical_shooting_qa_results.json').read_text())
    for gid in ('401809243','401810557','401869187'):
        file=SAMPLES/f'espn_summary_{gid}.json';raw=file.read_text();source=json.loads(raw);comp=source['header']['competitions'][0]
        teams={r['homeAway']:r['team']['id'] for r in comp['competitors']}
        schedule={'externalGameId':gid,'gameDate':comp['date'][:10],'phase':'playoffs' if source['header']['season']['type']==3 else 'regular','homeTeamId':teams['home'],'awayTeamId':teams['away']}
        game=parse_espn_summary_boxscore(raw,schedule);view=historical_shooting_view(game)
        by_id={(r['espn_player_id'],r['team_abbrev']):r for r in view['players']}
        for expected in qa['direct_normalized_samples']:
            if expected['game_id']!=gid:continue
            row=by_id[(expected['pid'],expected['team'])]
            for family,fields in [('fg',('fgm','fga')),('three',('fg3m','fg3a')),('ft',('ftm','fta'))]:assert strict_pair(row['shooting_validation'][family]['raw_value'])==tuple(expected[k] for k in fields)
            source_matches+=1
            if row['dnp']:dnp+=1;assert row['fgm'] is None
            else:active+=1;assert row['historical_shooting']['usable_complete_shooting']
        samples.append({'game_id':gid,'raw_sample_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'parsed':view})
    counts={'games':len(cache['games']),'legacy_player_rows':0,'final_team_fgm_mismatch':[],'explicit_reconstructed_active_fgm':0,'nonfinal_games':0}
    for game in cache['games']:
        view=historical_shooting_view(game,allow_reconstructed_fgm=True)
        counts['legacy_player_rows']+=len(game['players'])
        if game.get('status')!='STATUS_FINAL':counts['nonfinal_games']+=1
        else:
            for team,check in view['historical_shooting_view']['teams'].items():
                if not check['reconstructed_fgm_reconciles']:counts['final_team_fgm_mismatch'].append({'game_id':game['game_id'],'team':team})
        for row in view['players']:
            assert row['fga'] is None and not row['historical_shooting']['usable_complete_shooting']
            if row['historical_shooting']['status']=='fgm_conditionally_reconstructed_fga_unknown':counts['explicit_reconstructed_active_fgm']+=1
    assert source_matches==70 and active==69 and dnp==1
    assert len(counts['final_team_fgm_mismatch'])==7
    assert path.read_bytes()==raw_cache
    result={'parser_version':PARSER_VERSION,'source_cache_sha256':hashlib.sha256(raw_cache).hexdigest(),'source_cache_unchanged':True,'retained_source_rows_matched':source_matches,'active_complete_rows':active,'explicit_dnp_rows':dnp,'network_requests':0,'audit':counts}
    (out/'sample-parsing.json').write_text(json.dumps(samples,indent=2)+'\n');(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
