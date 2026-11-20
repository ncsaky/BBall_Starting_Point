"""New-career-only calendar entry through real create/advance actions."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import date,timedelta
import hashlib,json
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from nba_gm_data import save as sv
from nba_gm_data.app_actions import dispatch_app_action,load_app_canonical
from nba_gm_data.save_recovery import create_export,restore_export
from nba_gm_data.simulation_progress import progress_listener
from nba_gm_data.schema import CANONICAL_START_DATE

ROOT=Path(__file__).resolve().parents[1]

class NewCareerStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.canonical=load_app_canonical(ROOT)
    def action(self,name,payload,folder,canonical=None):
        return dispatch_app_action(name,payload,root=ROOT,save_dir=Path(folder),canonical=canonical or self.canonical)
    def create(self,folder,name='career',team='GSW',mode='standard',canonical=None):
        r=self.action('create_save',{'team':team,'seed':17,'save_name':name,'game_mode':mode},folder,canonical)
        return Path(r['save_path'])

    def test_start_uses_earliest_league_regular_game_not_order_or_exhibition(self):
        def g(day,phase='regular'):return {'gameDate':day,'phase':phase,'externalGameId':day}
        self.assertEqual(sv.new_career_start_date({'games':[g('2026-10-29'),g('2026-10-10','preseason'),g('2026-10-23')]}),'2026-10-22')
        with self.assertRaises(ValueError):sv.new_career_start_date({'games':[]})

    def test_new_real_actions_do_not_replay_offseason_and_initialize_deterministically(self):
        with tempfile.TemporaryDirectory() as folder,ExitStack() as patches:
            for name in ('advance_save','advance_lifecycle_to','simulate_health','advance_development','queue_ai_recommendations','process_ai_actions_in_memory'):
                patches.enter_context(patch.object(sv,name,side_effect=AssertionError('Creation ran '+name)))
            a,b=self.create(folder,'a'),self.create(folder,'b')
            left,right=sv.load_save(a,include_history=True),sv.load_save(b,include_history=True)
            start=left['meta']['gameplay_start_date'];games=left['season_schedules']['2026-27']['games']
            opener=min(g['gameDate'] for g in games if g['phase']=='regular')
            self.assertEqual(start,(date.fromisoformat(opener)-timedelta(days=1)).isoformat())
            self.assertEqual(start,'2026-10-20');self.assertEqual(left['state']['phase'],'preseason')
            self.assertEqual(left['meta']['source_snapshot_date'],CANONICAL_START_DATE)
            self.assertEqual(left['inbox_items'][0]['date'],start)
            self.assertEqual(left['lifecycle_state'],{'through_date':start,'health_game_ids':[]})
            for k in ('transaction_logs','game_results','development_events','applied_development_months','pending_ai_actions'):
                self.assertFalse(left[k],k)
            self.assertEqual(left['schedule_state']['simulated_game_ids'],[])
            self.assertEqual(left['team_plans'],right['team_plans']);self.assertEqual(len(left['team_plans']),30)
            self.assertEqual(left['ai_role_state'],right['ai_role_state'])
            self.assertEqual(left['state']['legal_actions'],sv.save_legal_actions_for_date(left,start))
            other=sv.load_save(self.create(folder,'bos',team='BOS'))
            self.assertEqual(other['state']['current_date'],start)

    def test_first_next_event_plays_only_opening_games_without_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            path=self.create(folder);saved=sv.load_save(path);opener=min(g['gameDate'] for g in sv.schedule_for_save(ROOT,saved))
            ids={str(g['externalGameId']) for g in sv.schedule_for_save(ROOT,saved) if g['gameDate']==opener}
            frames=[]
            with progress_listener(lambda e:frames.append(deepcopy(e))):
                result=self.action('advance_save',{'save_path':str(path),'next_event':True},folder)
            final=sv.load_save(path)
            self.assertEqual(result['result']['through_date'],opener)
            self.assertEqual(set(final['schedule_state']['simulated_game_ids']),ids)
            self.assertEqual(set(final['lifecycle_state']['health_game_ids']),ids)
            self.assertEqual([e['date'] for e in frames if e['kind']=='date'],[opener])
            self.assertFalse(final['applied_development_months'])
            again=self.action('advance_save',{'save_path':str(path),'to_date':opener},folder)
            self.assertEqual(again['result']['games_simulated'],0)
            self.assertEqual(sv.load_save(path)['schedule_state']['simulated_game_ids'],final['schedule_state']['simulated_game_ids'])
            self.action('advance_save',{'save_path':str(path),'next_event':True},folder)
            more=sv.load_save(path)['schedule_state']['simulated_game_ids']
            self.assertEqual(len(more),len(set(more)));self.assertTrue(ids<set(more))

    def test_reload_same_seed_preserves_first_advance_and_events(self):
        from verify_simulation_consistency import business_state,digest
        with tempfile.TemporaryDirectory() as folder:
            a=self.create(folder);b=Path(folder)/'reloaded.json';restore_export(b,create_export(a));states=[];events=[]
            for path in (a,b):
                frames=[]
                with progress_listener(lambda e:frames.append(digest(e))):
                    self.action('advance_save',{'save_path':str(path),'next_event':True},folder)
                states.append(business_state(sv.load_save(path,include_history=True)));events.append(frames)
            self.assertEqual(states[0],states[1]);self.assertEqual(events[0],events[1])

    def test_user_roster_overflow_still_stops_before_opening_games(self):
        with tempfile.TemporaryDirectory() as folder:
            path=self.create(folder);s=sv.load_save(path);pid=s['free_agent_player_ids'][0]
            s['roster_overrides'][pid]=s['meta']['user_team_id'];s['free_agent_player_ids'].remove(pid);sv.write_save(path,s)
            before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'Cut to 15 before opening night'):
                self.action('advance_save',{'save_path':str(path),'next_event':True},folder)
            self.assertEqual(path.read_bytes(),before)

    def test_health_return_dates_and_source_contracts_are_preserved_without_hidden_time(self):
        source=deepcopy(self.canonical);rows=source['player_health_states'][:3]
        for i,row in enumerate(rows):
            row.update(current_injury_id='startup-test-'+str(i),availability_status='out',return_date=['2026-10-10','2027-01-01',None][i],fatigue=2.5,rust=9.)
        contracts=json.dumps(source['contracts'],sort_keys=True);history=deepcopy(source['injury_events'])
        with tempfile.TemporaryDirectory() as folder:
            s=sv.load_save(self.create(folder,canonical=source),include_history=True);states={h['player_id']:h for h in s['health_states']}
            self.assertEqual(states[rows[0]['player_id']]['availability_status'],'active')
            self.assertIsNone(states[rows[0]['player_id']]['current_injury_id'])
            self.assertEqual(states[rows[1]['player_id']]['return_date'],'2027-01-01')
            self.assertEqual(states[rows[2]['player_id']]['availability_status'],'out')
            self.assertEqual(states[rows[0]['player_id']]['rust'],9.)
            self.assertEqual(states[rows[0]['player_id']]['fatigue'],2.5)
            # The source history is kept as is; the only additions are the opening night's season-start injuries
            # (OVERNIGHT-REST-GAMES), which never touch players already out.
            started=[e for e in s['injury_events'] if e.get('status')=='season_start_injury']
            self.assertEqual([e for e in s['injury_events'] if e.get('status')!='season_start_injury'],sorted(history,key=lambda e:e['id']))
            self.assertTrue(all(e['source_ids']==['src_season_start_injuries'] for e in started))
            self.assertFalse({e['player_id'] for e in started}&{r['player_id'] for r in rows[1:]})
            self.assertEqual(json.dumps(source['contracts'],sort_keys=True),contracts)
            self.assertFalse(s['contract_overrides'])

    def test_existing_checkpoint_and_legacy_fantasy_dates_are_not_migrated(self):
        from verify_simulation_consistency import business_state
        fixture=ROOT/'tests/fixtures/trade_year_seed17.nbagm.zip'
        if not fixture.exists():self.skipTest(f'{fixture} is missing; regenerate it')
        holder=tempfile.TemporaryDirectory();self.addCleanup(holder.cleanup)
        source=Path(holder.name)/'trade_year.json';restore_export(source,fixture.read_bytes())
        sha=hashlib.sha256(source.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'old.json';restore_export(path,create_export(source));before=sv.load_save(path,include_history=True)
            after=sv.ensure_league_save_defaults(deepcopy(before),self.canonical)
            self.assertEqual(after['state']['current_date'],before['state']['current_date'])
            for key in ('transaction_logs','game_results','development_events','injury_events','schedule_state','season_history'):
                self.assertEqual(after[key],before[key],key)
            legacy=sv.load_save(self.create(folder,'fantasy',mode='fantasy_draft'))
            missing=deepcopy(legacy);missing['state']['current_date']=None
            sv.ensure_league_save_defaults(missing,self.canonical)
            self.assertEqual(missing['state']['current_date'],'2026-10-20')
            legacy['meta'].pop('gameplay_start_date');legacy['state']['current_date']=CANONICAL_START_DATE
            sv.ensure_league_save_defaults(legacy,self.canonical)
            self.assertEqual(legacy['state']['current_date'],CANONICAL_START_DATE)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),sha)

    def test_real_fantasy_completion_enters_same_preopening_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path=self.create(folder,mode='fantasy_draft')
            self.assertEqual(sv.load_save(path)['state']['phase'],'fantasy_draft')
            self.action('fantasy_draft_sim_all',{'save_path':str(path)},folder)
            s=sv.load_save(path,include_history=True)
            self.assertEqual(s['state']['current_date'],'2026-10-20');self.assertEqual(s['state']['phase'],'preseason')
            self.assertEqual(s['fantasy_draft_state']['completed_date'],'2026-10-20')
            self.assertEqual(len(s['team_plans']),30);self.assertFalse(s['development_events']);self.assertFalse(s['game_results'])
            result=self.action('advance_save',{'save_path':str(path),'next_event':True},folder)
            self.assertEqual(result['result']['through_date'],'2026-10-21')
            from nba_gm_data.fantasy_draft import finalize_fantasy_draft
            progressed=sv.load_save(path,include_history=True);before=deepcopy(progressed)
            finalize_fantasy_draft(self.canonical,progressed)
            self.assertEqual(progressed,before)
