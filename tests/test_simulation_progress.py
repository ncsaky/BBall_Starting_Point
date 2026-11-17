from copy import deepcopy
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from nba_gm_data.simulation_progress import progress_listener, progress_listener_active, emit_progress
from nba_gm_data import save as save_module
from nba_gm_data.save import simulation_live_card_progress, simulation_month_calendar_progress, simulation_rotation_progress
import test_postseason_calendar as fixtures


class SimulationProgressTests(unittest.TestCase):
    def test_observation_does_not_change_games_health_or_development(self):
        fixture = fixtures.PostseasonCalendarTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        baseline, observed = deepcopy(fixture.save), deepcopy(fixture.save)
        fixture.advance(baseline,'2027-05-14')
        events = []
        with progress_listener(events.append):
            fixture.advance(observed,'2027-05-14')
        self.assertEqual(observed,baseline)
        games = [e for e in events if e['kind']=='game']
        self.assertEqual(len(games),len(observed['playoff_state']['games']))
        self.assertTrue(all(e.get('playoffs') for e in games))
        original = deepcopy(observed)
        games[0]['playoffs']['series'].clear()
        self.assertEqual(observed,original)

    def test_listener_is_request_local_and_failure_cannot_abort_simulation(self):
        events = []
        saved = {'state':{'current_date':'2027-05-01'}}
        with progress_listener(events.append):
            worker = threading.Thread(target=lambda:emit_progress(saved,'date'))
            worker.start(); worker.join()
            self.assertEqual(events,[])
            emit_progress(saved,'date')
            with progress_listener(lambda event:(_ for _ in ()).throw(OSError('Browser closed'))):
                emit_progress(saved,'date')
            emit_progress(saved,'date')
        emit_progress(saved,'date')
        self.assertEqual(len(events),2)

    def test_rotation_snapshot_is_transient_progress_only(self):
        events = []
        saved = {'state':{'current_date':'2027-01-02','phase':'regular_season'}}
        rotation = [{'id':'player_1','rotation_target_minutes':24,'health':{'status':'ok','fatigue':12.0}}]
        signals = {'ranks': {'overall': 5}}
        opponent = {'team': {'id': 'team_2'}, 'next_game': {'game_id': 'game_2'}}
        calendar = {'from_date': '2027-02-01', 'through_date': '2027-02-28', 'games': []}
        self.assertFalse(progress_listener_active())
        with progress_listener(events.append):
            self.assertTrue(progress_listener_active())
            emit_progress(saved,'date',rotation=rotation,team_signals=signals,opponent=opponent,calendar=calendar)
        self.assertFalse(progress_listener_active())
        self.assertEqual(events[0]['rotation'],rotation)
        self.assertEqual(events[0]['team_signals'],signals)
        self.assertEqual(events[0]['opponent'],opponent)
        self.assertEqual(events[0]['calendar'],calendar)
        self.assertEqual(saved,{'state':{'current_date':'2027-01-02','phase':'regular_season'}})

    def test_live_card_payload_contains_exact_team_signals_and_next_opponent(self):
        active = {
            'teams': [{'id':'team_user','abbrev':'USR'}, {'id':'team_opp','abbrev':'OPP'}],
            'players': [{'id':'p1','team_id':'team_opp','name':'Opponent One','minutes_projection':24}],
        }
        saved = {
            'meta': {'user_team_id':'team_user'},
            'state': {'current_date':'2027-01-04'},
            'team_records': {'team_opp': {'team_id':'team_opp','wins':12,'losses':8}},
            'team_game_logs': [{'team_id':'team_opp','date':'2027-01-03','result':'W'}],
            'player_season_stats': {'p1': {'games':2,'points':30,'rebounds':10,'assists':8}},
            'health_states': [],
        }
        identities = {
            'team_user': {'metrics': {'overall':81.2,'offense':82.1,'defense':80.3}, 'ranks': {'overall':4,'offense':3,'defense':8}, 'league_team_count':30},
            'team_opp': {'metrics': {}, 'ranks': {'overall':14,'offense':12,'defense':16}, 'league_team_count':30},
        }
        game = {'game_id':'game-next','date':'2027-01-05','opponent_team_id':'team_opp','is_home':False}
        with (
            patch.object(save_module, 'team_identity_report', return_value=identities),
            patch.object(save_module, 'next_team_games', return_value=[game]) as next_games,
            patch.object(save_module, 'team_rotation_projection', return_value={'p1':24}),
            patch.object(save_module, 'player_attribute_summary', return_value={'overall':78,'shooting':70,'creation':72,'passing':68}),
            patch.object(save_module, 'player_health_label', return_value={'status':'ok','fatigue':9}),
        ):
            payload = simulation_live_card_progress(Path('/tmp'), active, saved)

        self.assertEqual(payload['team_signals'], identities['team_user'])
        self.assertEqual(payload['opponent']['team']['id'], 'team_opp')
        row = payload['opponent']['rotation'][0]
        self.assertEqual(row['display_ratings'],row['attributes'])
        self.assertEqual(row['rating_scale'],'model_skill_1_99')
        self.assertEqual(payload['opponent']['next_game'], game)
        self.assertEqual(payload['opponent']['record']['wins'], 12)
        self.assertEqual(payload['opponent']['rotation'][0]['overall'], 78)
        self.assertEqual(payload['opponent']['rotation'][0]['points_per_game'], 15)
        self.assertEqual(payload['opponent']['last_games'][0]['result'], 'W')
        next_games.assert_called_once_with(Path('/tmp'), active, saved, 'team_user', limit=1, include_current=True)

    def test_month_boundary_calendar_snapshot_covers_entire_month(self):
        expected = {'from_date': '2028-02-01', 'through_date': '2028-02-29', 'games': []}
        with patch.object(save_module, 'calendar_view', return_value=expected) as calendar:
            result = simulation_month_calendar_progress(Path('/league'), {'teams': []}, {}, '2028-02-01')
        self.assertEqual(result, expected)
        calendar.assert_called_once_with(
            Path('/league'), {'teams': []}, Path('/league'),
            from_date='2028-02-01', through_date='2028-02-29', prepared_save={},
        )

    def test_rotation_snapshot_reflects_the_live_user_roster_without_mutation(self):
        active = {'players':[{'id':'player_1','team_id':'team_A','name':'One','minutes_projection':24}]}
        saved = {
            'meta':{'user_team_id':'team_A'},
            'state':{'current_date':'2027-01-02'},
            'rotation_overrides':{'team_A':{'player_1':24}},
            'rotation_locked_player_ids':{'team_A':['player_1']},
            'health_states':[{'player_id':'player_1','availability_status':'out','current_injury_id':'injury_1','return_date':'2027-01-06','fatigue':35}],
        }
        before_active, before_saved = deepcopy(active), deepcopy(saved)
        rows = simulation_rotation_progress(active, saved)
        self.assertEqual(rows[0]['id'],'player_1')
        self.assertEqual(rows[0]['rotation_target_minutes'],0.0)
        self.assertEqual(rows[0]['health']['status'],'out')
        self.assertFalse(rows[0]['rotation_user_set'])
        self.assertEqual(active,before_active)
        self.assertEqual(saved,before_saved)


if __name__ == '__main__':
    unittest.main()
