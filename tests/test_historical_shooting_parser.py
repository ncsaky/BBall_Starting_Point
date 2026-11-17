from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data.research import parse_boxscore_stat_row, parse_made_attempt, parse_espn_summary_boxscore, fetch_game_boxscores
from nba_gm_data.historical_shooting import PARSER_VERSION, historical_shooting_view

ROOT=Path(__file__).resolve().parents[1]
SAMPLES=ROOT/'docs/ratings-evidence-2026-10-29/diagnostics/milestone2_20261113'


def sample():
    raw=(SAMPLES/'espn_summary_401809243.json').read_text()
    schedule={'externalGameId':'401809243','gameDate':'2025-10-21','phase':'regular','homeTeamId':'25','awayTeamId':'10'}
    return raw,schedule


def row(**overrides):
    return {'FG':'7-15','3PT':'2-6','FT':'0-0','PTS':'16','MIN':'31','REB':'8','AST':'3',**overrides}


class HistoricalShootingParserTests(unittest.TestCase):
    def test_long_key_and_legacy_aliases_are_total_field_goals(self):
        for key in ('fieldGoalsMade-fieldGoalsAttempted','fg','FG'):
            d=row();d.pop('FG');d[key]='7-15';r=parse_boxscore_stat_row(d)
            self.assertEqual((r['fgm'],r['fga'],r['fg3m']),(7,15,2))
            self.assertTrue(r['shooting_validation']['row_usable'])
            self.assertEqual(r['shooting_validation']['fg']['source_key'],key)

    def test_genuine_zero_missing_invalid_and_dnp_remain_distinct(self):
        for value,status,expected in [('0-0','observed',(0,0)),('0-4','observed',(0,4)),(None,'missing',(None,None)),('--','missing',(None,None)),('','missing',(None,None)),('bogus','invalid',(None,None)),('4-2','invalid',(None,None)),('1.2-4','invalid',(None,None)),('NaN-4','invalid',(None,None)),(False,'invalid',(None,None))]:
            with self.subTest(value=value):
                r=parse_boxscore_stat_row(row(FG=value))
                self.assertEqual((r['fgm'],r['fga']),expected);self.assertEqual(r['shooting_validation']['fg']['status'],status)
                self.assertEqual((r['rebounds'],r['assists']),(8,3))
        r=parse_boxscore_stat_row(row(FG='0-0'),dnp=True)
        self.assertIsNone(r['fgm']);self.assertEqual(r['shooting_validation']['fg']['status'],'dnp')
        self.assertEqual(parse_made_attempt(' 0 – 6 '),(0,6))

    def test_long_alias_wins_and_conflicts_are_not_hidden(self):
        r=parse_boxscore_stat_row(row(**{'fieldGoalsMade-fieldGoalsAttempted':'8-17'}))
        self.assertEqual(r['fgm'],8);self.assertIn('conflicting_shooting_aliases',r['shooting_validation']['issues'])
        self.assertFalse(r['shooting_validation']['row_usable'])
        r=parse_boxscore_stat_row(row(**{'fieldGoalsMade-fieldGoalsAttempted':None}))
        self.assertEqual(r['fgm'],7)
        r=parse_boxscore_stat_row(row(**{'fieldGoalsMade-fieldGoalsAttempted':'bad'}))
        self.assertIsNone(r['fgm'])

    def test_inconsistent_row_is_preserved_with_issues_never_clamped(self):
        r=parse_boxscore_stat_row(row(FG='1-3'))
        self.assertEqual((r['fgm'],r['fg3m']),(1,2));self.assertFalse(r['shooting_validation']['row_usable'])
        self.assertIn('three_makes_exceed_total_fg',r['shooting_validation']['issues'])
        r=parse_boxscore_stat_row(row(PTS='17'))
        self.assertIn('scoring_identity_mismatch',r['shooting_validation']['issues'])

    def test_retained_70_rows_match_authoritative_values_by_identity(self):
        qa=json.loads((SAMPLES/'historical_shooting_qa_results.json').read_text())
        count=0
        for game_id in ('401809243','401810557','401869187'):
            raw=(SAMPLES/f'espn_summary_{game_id}.json').read_text();d=json.loads(raw);header=d['header'];comp=header['competitions'][0]
            competitors={r['homeAway']:r['team']['id'] for r in comp['competitors']}
            schedule={'externalGameId':game_id,'gameDate':comp['date'][:10],'phase':'playoffs' if header['season']['type']==3 else 'regular','homeTeamId':competitors['home'],'awayTeamId':competitors['away']}
            game=parse_espn_summary_boxscore(raw,schedule);view=historical_shooting_view(game)
            self.assertEqual(game['source_identity']['issues'],[])
            by_id={(r['espn_player_id'],r['team_abbrev']):r for r in view['players']}
            for expected in qa['direct_normalized_samples']:
                if expected['game_id']!=game_id:continue
                parsed=by_id[(expected['pid'],expected['team'])];count+=1
                if parsed['dnp']:
                    self.assertIsNone(parsed['fgm']);self.assertFalse(parsed['historical_shooting']['usable_complete_shooting'])
                    for family,fields in [('fg',('fgm','fga')),('three',('fg3m','fg3a')),('ft',('ftm','fta'))]:
                        self.assertEqual(parse_made_attempt(parsed['shooting_validation'][family]['raw_value']),tuple(expected[k] for k in fields))
                else:
                    for field in ('fgm','fga','fg3m','fg3a','ftm','fta'):self.assertEqual(parsed[field],expected[field])
                    self.assertTrue(parsed['historical_shooting']['usable_complete_shooting'])
        self.assertEqual(count,70)

    def test_game_identity_season_phase_and_final_status_gate_calibration(self):
        raw,schedule=sample();source=json.loads(raw)
        for mutate in (lambda d:d['header'].update(id='other'),lambda d:d['header']['season'].update(year=2027),lambda d:d['header']['season'].update(type=3),lambda d:d['header']['competitions'][0].update(date='2025-10-22T00:00Z'),lambda d:d['header']['competitions'][0]['status']['type'].update(name='STATUS_SCHEDULED')):
            d=deepcopy(source);mutate(d);game=parse_espn_summary_boxscore(json.dumps(d),schedule)
            self.assertFalse(any(r['historical_shooting']['usable_complete_shooting'] for r in historical_shooting_view(game)['players']))
        self.assertEqual(parse_espn_summary_boxscore(raw,schedule)['source_identity']['source']['season_year'],2026)

    def test_stat_alignment_duplicate_and_missing_player_identity_are_quarantined(self):
        raw,schedule=sample();source=json.loads(raw)
        source['boxscore']['players'][0]['statistics'][0]['athletes'][0]['stats'].pop()
        game=parse_espn_summary_boxscore(json.dumps(source),schedule)
        self.assertFalse(game['players'][0]['shooting_validation']['row_usable'])
        game=parse_espn_summary_boxscore(raw,schedule);game['players'].append(deepcopy(game['players'][0]))
        view=historical_shooting_view(game)
        self.assertTrue(view['players'][0]['historical_shooting']['duplicate_identity'])
        self.assertFalse(view['players'][0]['historical_shooting']['usable_complete_shooting'])
        game=parse_espn_summary_boxscore(raw,schedule);game['players'][0]['espn_player_id']=None
        self.assertFalse(historical_shooting_view(game)['players'][0]['historical_shooting']['usable_complete_shooting'])

    def test_dnp_is_identity_preserving_and_does_not_invent_attempts(self):
        raw,schedule=sample();data=json.loads(raw)
        athlete=data['boxscore']['players'][0]['statistics'][0]['athletes'][0];pid=athlete['athlete']['id'];athlete['didNotPlay']=True
        game=parse_espn_summary_boxscore(json.dumps(data),schedule)
        player=next(r for r in game['players'] if r['espn_player_id']==pid)
        self.assertTrue(player['dnp']);self.assertIsNone(player['fga'])
        self.assertEqual(player['shooting_validation']['fg']['status'],'dnp')

    def test_legacy_views_are_private_quarantined_and_only_reconstruct_fgm(self):
        raw,schedule=sample();game=parse_espn_summary_boxscore(raw,schedule)
        game.pop('shooting_parser_version');game.pop('source_identity')
        for r in game['players']:r['fgm']=0;r['fga']=0
        before=deepcopy(game)
        view=historical_shooting_view(game)
        self.assertTrue(all(r['fgm'] is None and r['fga'] is None for r in view['players']))
        recovered=historical_shooting_view(game,allow_reconstructed_fgm=True)
        active=[r for r in recovered['players'] if not r['dnp']]
        self.assertTrue(all(r['fgm'] is not None and r['fga'] is None for r in active))
        self.assertFalse(any(r['historical_shooting']['usable_complete_shooting'] for r in recovered['players']))
        self.assertEqual(game,before)
        self.assertEqual(historical_shooting_view(view),view)
        for r,old in zip(recovered['players'],game['players']):self.assertEqual(r['rebounds'],old['rebounds'])
        # Repeated fresh normalization/viewing never doubles threes or aliases.
        fresh=parse_espn_summary_boxscore(raw,schedule)
        self.assertEqual(historical_shooting_view(historical_shooting_view(fresh)),historical_shooting_view(fresh))

    def test_seven_unresolved_final_team_groups_cannot_recover(self):
        games=json.loads((ROOT/'data/research/game_boxscores_2025_26.json').read_text())['games']
        bad={'401810150','401810372','401810547','401810560','401810577','401810633','401810760'}
        failed=0
        for game in games:
            if game['game_id'] not in bad:continue
            view=historical_shooting_view(game,allow_reconstructed_fgm=True)
            for check in view['historical_shooting_view']['teams'].values():
                if not check['reconstructed_fgm_reconciles']:failed+=1
            self.assertFalse(any(r['historical_shooting']['usable_complete_shooting'] for r in view['players']))
        self.assertEqual(failed,7)

    def test_legacy_zero_minutes_do_not_become_observed_zero_attempt_samples(self):
        raw,schedule=sample();game=parse_espn_summary_boxscore(raw,schedule);game.pop('shooting_parser_version')
        for player in game['players']:player['fgm']=0;player['fga']=0;player['minutes']=0
        view=historical_shooting_view(game,allow_reconstructed_fgm=True)
        self.assertTrue(all(r['fgm'] is None and r['fga'] is None for r in view['players']))

    def test_team_reconciliation_never_distributes_or_clamps_difference(self):
        raw,schedule=sample();game=parse_espn_summary_boxscore(raw,schedule)
        game['players'][0]['fgm']+=1
        view=historical_shooting_view(game)
        self.assertFalse(view['players'][0]['historical_shooting']['usable_complete_shooting'])
        self.assertEqual(view['players'][0]['fgm'],game['players'][0]['fgm'])

    def test_missing_only_refresh_does_not_certify_or_reparse_stale_rows(self):
        raw,schedule=sample();existing={'401809243':{'game_id':'401809243','date':'2025-10-21','players':[{'fgm':0,'fga':0}]}}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'NBA Schedule').mkdir();(root/'NBA Schedule/schedule_v2025_2026.json').write_text(json.dumps({'games':[schedule]}))
            with patch('nba_gm_data.research.existing_game_boxscores',return_value=existing),patch('nba_gm_data.research.fetch_espn_scoreboard_events',return_value=[]),patch('nba_gm_data.research.fetch_url',side_effect=AssertionError('No refetch')):
                result=fetch_game_boxscores(root)
        self.assertEqual(result['games'],list(existing.values()))
        self.assertEqual(result['legacy_shooting_game_count'],1)
        self.assertEqual(result['new_record_shooting_parser_version'],PARSER_VERSION)


if __name__=='__main__':unittest.main()
