"""Read-only comparison against an isolated copy of a completed live draft."""
import hashlib
import json
from pathlib import Path

from nba_gm_data import app_actions as aa, play
from nba_gm_data.draft import draft_board_report
from nba_gm_data.save import player_display_attribute_summary

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/prospect-rating-parity-2026-10-25'


def main():
    path = OUT / 'saves/memphis.json'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    canonical = aa.load_app_canonical(ROOT)
    context = aa.dashboard_read_context(canonical,path)
    save, active = context['save'], aa.transaction_read_active(context)
    team = save['meta']['user_team_id']
    year = str(int(save['meta']['season'][:4])+1)
    room = aa.dispatch_app_action('draft_room',{'save_path':str(path),'year':year},root=ROOT,save_dir=path.parent,canonical=canonical)
    upcoming = aa.enrich_draft_board_scouting(active,save,team,draft_board_report(active,team,year))
    by_id = {row['prospect']['id']:row for row in upcoming['entries']}
    players = {row['prospect_id']:row['player_id'] for row in save.get('incoming_rookies',[]) if row.get('player_id') and str(row.get('draft_year'))==year}
    evidence = []
    for row in room['draft_board']['entries']:
        prospect = row['prospect']
        if prospect['id'] not in players:
            continue
        scout = row['scout_display']
        actual = player_display_attribute_summary(active,players[prospect['id']])
        assert scout['now']==actual['overall'], (prospect['name'],scout['now'],actual['overall'])
        assert all(value==actual[key] for key,value in scout['ratings'].items()), prospect['name']
        preview = by_id[prospect['id']]['scout_display']
        assert preview['now']==scout['now']
        assert preview['ratings']==scout['ratings']
        if len(evidence)<6:
            card = aa.prospect_card_payload(canonical,path,prospect['id'],year)
            assert card['overall']==actual['overall'] and card['ratings']==scout['ratings']
            report = play.scouting_report_for(active,prospect['id'],team)
            evidence.append({'name':prospect['name'],'old_raw_now':(report.get('estimated_current') or {}).get('mid',prospect['current_ability']),
                             'upcoming_now':preview['now'],'draft_now':scout['now'],'prospect_card_now':card['overall'],
                             'signed_player_now':actual['overall'],'revealed_ratings':len(scout['ratings']),
                             'shooting':actual['shooting'],'defense':actual['defense']})
    assert len(players)==60
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before==after
    result = {'compared_signed_rookies':len(players),'save_unchanged':before==after,'examples':evidence}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
