"""Causal screen/pop timing and shared-outcome verification; no target ranks."""
import ast
from copy import deepcopy
from dataclasses import replace
import inspect
import json
import math
import random
import unittest
import weakref

from nba_gm_data.creation_passing import prepare_drive_decision,resolve_candidate,resolve_drive
from nba_gm_data.action_choice import project_candidate,project_choices
from nba_gm_data.screen_navigation import (compile_screen,PopScreenProfile,PopScreenCall,PopScreenExperiment,
    receiver_position,coverage_position,ScreenExperiment)
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data import sim
from experiments.pick_and_pop.fixtures import pool,fixture,research_pool,IDS,REFERENCE
from experiments.pick_and_pop.verification import reference_modules,reference_config,use_reference,prepare
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.action_choice_consistency.empirical import validate_candidate
from experiments.expanded_cohort_performance.checks import benchmarks,kernel_parity,candidate_parity
from experiments.expanded_cohort_performance.fixtures import fixture as old_fixture
from experiments.expanded_cohort_performance.pool import load_pool


# Retired experimental engine (Track C): its reference snapshot in output/ was never kept in git and was removed in the
# 2026-11-21 disk cleanup. Skip, with the reason, when it is missing. Normal gameplay does not use this engine.
_RETIRED_SNAPSHOTS = ['expanded-cohort-action-performance-2026-11-15']


def setUpModule():
    from pathlib import Path
    missing = [n for n in _RETIRED_SNAPSHOTS if not (Path(__file__).resolve().parents[1] / "output" / n).exists()]
    if missing:
        raise unittest.SkipTest("retired experimental engine: reference snapshot missing (deleted 2026-11-21, never in git): "
                                + ", ".join(missing))


def decision(state,remaining=24,draws=None):
    return prepare_drive_decision(state,IDS['curry'],'response_a','response_b',observed_draws() if draws is None else draws,remaining)


class PickAndPopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.named=pool();cls.synthetic=pool(synthetic=True);cls.old=reference_modules()

    def d(self,*,changes=None,remaining=24,**kw):
        p=pool(synthetic=True,changes=changes) if changes else self.synthetic
        s,c,x=fixture(p,**kw);return decision(s,remaining),s,c,x

    def project(self,**kwargs):
        d,_,_,_=self.d(**kwargs);self.assertIn('pop',d['options']);return project_candidate(d['frame'],'pop',d['options'])

    def shot(self,**kwargs):
        d,_,_,_=self.d(**kwargs);return resolve_candidate(d['frame'],'pop',d['options'],observed_draws(),{},delivery_error_override=0)

    def test_new_role_dependencies_are_explicit_and_unknown_not_weak(self):
        raw=load_pool()['views'][IDS['turner']]
        with self.assertRaisesRegex(ValueError,'S27|S28|S26|T11'):compile_screen(raw,roles=('screener',),pop_routes=True)
        p=compile_screen(self.named['views'][IDS['turner']],roles=('screener',),pop_routes=True)
        self.assertIsInstance(p,PopScreenProfile);self.assertEqual(p.relocation,.65)
        self.assertEqual({v['design_id'] for v in self.named['control_ledger']},{'S26','S27','S28','T11'})
        for row in self.named['control_ledger']:self.assertEqual(row['before']['status'],'unknown')

    def test_named_supported_rows_and_all94_records_preserved(self):
        p=self.named
        for pid,doc in p['packet']['proposed_source_input_section']['players'].items():
            operational=p['views'][pid].to_dict();self.assertEqual(len(operational['inputs']),94)
            for k,row in doc['inputs'].items():
                if row['status']!='unknown':self.assertEqual(row,operational['inputs'][k])
        with self.assertRaisesRegex(ValueError,'Named evidence'):pool(changes={'turner':{'S01':10}})

    def test_final_independent_packet_is_separate_and_shares_one_view(self):
        p=research_pool();self.assertEqual(len(p['research_updates']),2)
        s,c,x=fixture(p);v=p['views'][IDS['turner']]
        self.assertIs(s['profiles'][IDS['turner']].inputs,v)
        self.assertIs(s['coupled']['profiles'][IDS['turner']].inputs,v)
        self.assertIs(s['screens']['profiles'][IDS['turner']].inputs,v)
        for k in ('S26','S28'):self.assertEqual(v.to_dict()['inputs'][k],p['research_packet']['proposed_source_input_section']['players'][IDS['turner']]['inputs'][k])
        self.assertEqual({v['design_id'] for v in p['control_ledger']},{'S27','T11'})
        self.assertEqual(self.named['views'][IDS['turner']].to_dict()['inputs']['S26']['value']['grade'],65)

    def test_pop_preference_is_retained_and_call_is_distinct(self):
        p=pool(synthetic=True,changes={'turner':{'T11':{'screen':0,'roll':0,'slip':0,'pop':1}}})
        s,_,_=fixture(p,action='preference');d=decision(s)
        self.assertEqual(d['record']['screen_action']['preferred'],'pop');self.assertEqual(d['record']['screen_action']['route'],'pop')
        self.assertIn('pop',d['options']);self.assertNotIn('F03',d['options'])
        s,_,_=fixture(p,action='roll');r=decision(s)['record']['screen_action']
        self.assertEqual((r['preferred'],r['called_action'],r['route']),('pop','roll','roll'))

    def test_zero_pop_preference_does_not_create_pop_but_explicit_call_can(self):
        p=pool(synthetic=True,changes={'turner':{'T11':{'screen':0,'roll':1,'slip':0,'pop':0}}})
        s,_,_=fixture(p,action='preference');self.assertNotIn('pop',decision(s)['options'])
        s,_,_=fixture(p,action='pop');self.assertIn('pop',decision(s)['options'])

    def test_failed_pop_read_holds_screen_instead_of_gifting_a_route(self):
        d,s,_,_=self.d();draws=observed_draws();draws[40]=.999
        r=decision(s,draws=draws)
        self.assertEqual(r['record']['screen_action']['route'],'screen');self.assertNotIn('pop',r['options'])
        self.assertEqual(r['record']['screen_action']['read_failure'],'hold_screen_no_pop')

    def test_pop_requires_tactical_destination_and_matching_compiler_policy(self):
        with self.assertRaisesRegex(ValueError,'perimeter'):fixture(self.named,pop_end=(.6,1))
        s,c,x=fixture(self.named);screens=x.offense.creation.screens
        bad=ScreenExperiment(screens.profiles,screens.calls)
        with self.assertRaisesRegex(ValueError,'policy|experiment'):
            from experiments.action_choice_consistency.fixtures import prepare as prep
            prep(c,replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=bad))),None)

    def test_pop_moves_to_endpoint_without_teleport_or_permanent_open_window(self):
        d,s,_,_=self.d();r=d['record']['screen_action'];p=s['screens']['profiles'][IDS['turner']]
        self.assertEqual(receiver_position(r,0,p),r['receiver_start'])
        mid=receiver_position(r,(r['release_s']+r['receiver_route_end_s'])/2,p)
        self.assertNotEqual(mid,r['receiver_start']);self.assertNotEqual(mid,r['pop_end'])
        self.assertEqual(receiver_position(r,r['receiver_route_end_s']+10,p),r['pop_end'])
        cover=s['screens']['profiles'][IDS['wemb']]
        self.assertNotEqual(coverage_position(r,r['release_s'],cover),coverage_position(r,r['window_end_s'],cover))
        self.assertGreater(r['window_end_s'],r['window_start_s'])

    def test_pop_is_F06_drive_exit_not_a_roll_pass(self):
        d,_,_,_=self.d();o=d['options']['pop']
        self.assertEqual(o['delivery']['family'],'F06');self.assertNotIn('F03',d['options']);self.assertNotIn('F04',d['options'])
        a=self.shot();self.assertEqual(a['record']['pass']['recognition_input'],'F06.recognition')
        self.assertEqual(a['plan']['zone'],'perimeter');self.assertEqual(a['plan']['details']['mode'],'catch')

    def test_actual_pop_location_sets_range_and_geometry(self):
        a=self.shot(pop_end=(4,8));p=a['plan'];self.assertAlmostEqual(p['details']['shooting']['distance_m'],math.hypot(4,8))
        self.assertEqual((p['details']['geometry']['shot_x_m'],p['details']['geometry']['shot_y_m']),(4,8))
        self.assertNotEqual(math.hypot(4,8),math.hypot(3,6.8))

    def test_weak_strong_execution_changes_shot_not_route_timing(self):
        pairs=[self.d(changes={'turner':{'S01':grade}})[0] for grade in (10,95)]
        for k in ('release_s','window_start_s','window_end_s'):self.assertEqual(pairs[0]['record']['screen_action'][k],pairs[1]['record']['screen_action'][k])
        v=[project_candidate(d['frame'],'pop',d['options']) for d in pairs]
        self.assertGreater(v[1]['expected_points'],v[0]['expected_points'])

    def test_willingness_changes_utility_not_conditional_execution(self):
        rows=[]
        for v in (.1,.9):
            d,_,_,_=self.d(changes={'turner':{'T01':v}});rows.append(project_choices(d['frame'],d['options']))
        self.assertEqual(rows[0]['candidates']['pop']['branches'],rows[1]['candidates']['pop']['branches'])
        self.assertGreater(rows[1]['scores']['pop'],rows[0]['scores']['pop'])
        d,_,_,_=self.d(changes={'turner':{'T01':0}});self.assertNotIn('pop',d['options'])

    def test_release_and_range_cost_use_shared_shooting_once(self):
        slow=self.shot(changes={'turner':{'S08':10}},coverage='stay');fast=self.shot(changes={'turner':{'S08':95}},coverage='stay')
        self.assertLess(fast['elapsed_s'],slow['elapsed_s'])
        self.assertGreater(fast['plan']['off']['three_pct'],slow['plan']['off']['three_pct'])
        short=self.shot(pop_end=(3,7));deep=self.shot(pop_end=(3,8.5))
        self.assertGreater(short['plan']['off']['three_pct'],deep['plan']['off']['three_pct'])
        strong=self.shot(pop_end=(3,8.5),changes={'turner':{'S09':95}})
        self.assertGreater(strong['plan']['off']['three_pct'],deep['plan']['off']['three_pct'])

    def test_closeout_and_coverage_costs_are_actual(self):
        stay=self.shot(coverage='stay');show=self.shot(coverage='show_then_recover')
        self.assertLess(stay['record']['derived_primary_arrival_s'],show['record']['derived_primary_arrival_s'])
        self.assertLess(stay['plan']['off']['three_pct'],show['plan']['off']['three_pct'])
        weak=self.shot(coverage='stay',changes={'wemb':{'S40':10}});strong=self.shot(coverage='stay',changes={'wemb':{'S40':95}})
        self.assertLess(strong['plan']['off']['three_pct'],weak['plan']['off']['three_pct'])

    def test_relocation_changes_availability_not_shooting_talent(self):
        a=self.d(changes={'turner':{'S26':10}})[0];b=self.d(changes={'turner':{'S26':95}})[0]
        self.assertGreater(a['record']['screen_action']['window_start_s'],b['record']['screen_action']['window_start_s'])
        self.assertGreater(a['options']['pop']['wait_s'],b['options']['pop']['wait_s'])

    def test_screen_execution_changes_legal_contact_and_pop_release(self):
        a=self.d(changes={'turner':{'S27':10}})[0]['record']['screen_action']
        b=self.d(changes={'turner':{'S27':95}})[0]['record']['screen_action']
        self.assertGreater(a['illegal_probability'],b['illegal_probability'])
        self.assertGreater(a['set_s'],b['set_s'])

    def test_receiving_and_passing_execution_are_separate_failures(self):
        low=self.project(changes={'turner':{'S14':10}});high=self.project(changes={'turner':{'S14':95}})
        self.assertEqual(low['branches']['inaccurate_delivery'],high['branches']['inaccurate_delivery'])
        self.assertGreater(low['branches']['failed_catch'],high['branches']['failed_catch'])
        a=self.project(changes={'curry':{'F06.execution':10}});b=self.project(changes={'curry':{'F06.execution':95}})
        self.assertGreater(a['branches']['inaccurate_delivery'],b['branches']['inaccurate_delivery'])

    def test_pass_read_is_distinct_from_delivery_execution(self):
        draws=observed_draws();draws[31]=.6
        p=pool(synthetic=True,changes={'curry':{'F06.recognition':10}});s,_,_=fixture(p);self.assertNotIn('pop',decision(s,draws=draws)['options'])
        p=pool(synthetic=True,changes={'curry':{'F06.recognition':95}});s,_,_=fixture(p);self.assertIn('pop',decision(s,draws=draws)['options'])

    def test_early_roll_reproduction_and_opt_in_delayed_catch(self):
        # Authentic accepted milestone9 scene, without any grade modification.
        s,c,x=old_fixture(load_pool(),creator='curry',receiver='white',partner='jokic',poa='castle',helper='barnes',other='wemb',screen='show_then_recover',families=('F03','F04','F06'))
        current=decision(s)
        with use_reference(self.old):
            old=reference_config(x,self.old);prev=prepare(c,old,self.old)
            d=self.old['nba_gm_data.creation_passing'].prepare_drive_decision(prev,IDS['curry'],'response_a','response_b',observed_draws(),24)
        self.assertNotIn('F03',current['options']);self.assertEqual(current['record'],d['record'])
        immediate=self.d(action='roll',timing='immediate_v1')[0];delayed=self.d(action='roll')[0]
        self.assertNotIn('F03',immediate['options']);self.assertIn('F03',delayed['options'])
        self.assertGreater(delayed['options']['F03']['wait_s'],0)
        stay=self.d(action='roll',coverage='stay')[0];self.assertNotIn('F03',stay['options'])

    def test_wait_consumes_time_security_and_defender_recovery(self):
        d,s,_,_=self.d(creator_start=(1.4,4.6));o=d['options']['pop'];self.assertGreater(o['wait_s'],0)
        self.assertGreater(o['waiting_loss_probability'],0);self.assertGreater(o['waiting_pressure'],d['frame']['drive']['pressure'])
        draws=observed_draws();draws[43]=0;a=resolve_candidate(d['frame'],'pop',d['options'],draws,{})
        self.assertEqual(a['outcome'],'waiting_loss');self.assertAlmostEqual(a['elapsed_s'],d['frame']['elapsed']+o['wait_s'])
        draws[43]=1;b=resolve_candidate(d['frame'],'pop',d['options'],draws,{},delivery_error_override=0)
        self.assertGreater(b['elapsed_s'],a['elapsed_s']);self.assertIn('wait',b['record'])

    def test_expired_windows_and_crosscourt_are_not_gifted(self):
        d,_,_,_=self.d(coverage='stay',coverage_start=(3,7.4));self.assertNotIn('pop',d['options'])
        d,_,_,_=self.d(pop_end=(-3,7.4));self.assertNotIn('pop',d['options']);self.assertIn('F07_cross_court_pop',d['record']['unsupported_routes'])

    def test_short_clock_precedes_wait_delivery_catch_and_release(self):
        for remaining in (.1,1,2.6,2.9):
            d,_,_,_=self.d(remaining=remaining);p=project_candidate(d['frame'],'pop',d['options'])
            self.assertAlmostEqual(sum(p['branches'].values()),1)
            self.assertGreater(p['branches']['shot_clock_turnover'],0)
        self.assertAlmostEqual(self.project(remaining=.1)['branches']['shot_clock_turnover'],1)

    def test_projection_matches_sampled_events_pop_wait_roll_and_short_clock(self):
        for kwargs,name in [({},'pop'),({'coverage':'stay'},'pop'),({'action':'roll'},'F03'),({'remaining':2.9},'pop')]:
            d,_,_,_=self.d(**kwargs)
            with self.subTest(kwargs=kwargs):self.assertTrue(validate_candidate(d,name,n=4096,seed=17)['all_passed'])

    def test_projection_does_not_read_future_draws_or_allocate_rng(self):
        d,s,_,_=self.d();a=project_choices(d['frame'],d['options']);draws=observed_draws()
        for k in (5,6,7,8,9,15,17,19,34,35,43):draws[k]=.999
        b=decision(s,draws=draws)
        from unittest.mock import patch
        with patch('random.Random',side_effect=AssertionError('projection RNG')):self.assertEqual(a,project_choices(b['frame'],b['options']))

    def test_pop_kernel_accounting_determinism_and_actual_shots(self):
        s,c,x=fixture(self.named)
        a=sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x);b=sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x)
        from nba_gm_data.schema import to_plain
        self.assertEqual(to_plain(a),to_plain(b));validate_accounting(a)
        events=[e for t in a.team_lines for e in t['interior_experiment']['offense_attack_ledger']]
        pop=[e for e in events if e.get('creation_chain',{}).get('choice')=='pop'];self.assertTrue(pop)
        self.assertTrue(all(e['creation_chain']['pass']['family']=='F06' for e in pop if 'pass' in e['creation_chain']))

    def test_scripted_actual_pop_three_point_and_free_throw_accounting(self):
        from experiments.pick_and_pop.probes import scripted_accounting
        for outcome in ('made_fg','shooting_foul'):
            r=scripted_accounting(outcome)
            events=[e for t in r.team_lines for e in t['interior_experiment']['offense_attack_ledger'] if e.get('creation_chain',{}).get('choice')=='pop']
            self.assertEqual(len(events),2)
            for e in events:
                self.assertEqual(e['outcome'],outcome);self.assertEqual(e['zone'],'perimeter');self.assertEqual(e['points'],3)
                if outcome=='made_fg':self.assertEqual(e['assist_by'],IDS['curry'])
                else:self.assertEqual(e['fta'],3);self.assertNotIn('assist_by',e)
            line=next(p for p in r.player_lines if p['player_id']==IDS['turner'])
            self.assertEqual(line['fg3m'],2 if outcome=='made_fg' else 0)
            self.assertEqual(line['fta'],6 if outcome=='shooting_foul' else 0)

    def test_source_mutation_and_local_graph_release(self):
        before={k:v.to_dict() for k,v in self.named['views'].items()};s,c,x=fixture(self.named);d=decision(s);p=project_choices(d['frame'],d['options'])
        p['candidates']['pop']['expected_points']=999;self.assertNotEqual(project_choices(d['frame'],d['options'])['candidates']['pop']['expected_points'],999)
        self.assertEqual(before,{k:v.to_dict() for k,v in self.named['views'].items()})
        refs=[weakref.ref(x),weakref.ref(x.offense.creation),weakref.ref(x.offense.creation.screens)]
        del s,c,x,d,p;self.assertTrue(all(r() is None for r in refs))

    def test_exact_retention_of_milestone9_validation_optimizations(self):
        from nba_gm_data import shot_geometry,interior_defense,experimental_inputs
        for module,qualname in [(shot_geometry,'ShotGeometry'),(interior_defense,'ArrivalContext'),(experimental_inputs,'same_input_snapshot')]:
            old=ast.parse((REFERENCE/(module.__name__.split('.')[-1]+'.py.reference')).read_text())
            new=ast.parse(inspect.getsource(module));oldnode=next(n for n in old.body if getattr(n,'name',None)==qualname);newnode=next(n for n in new.body if getattr(n,'name',None)==qualname)
            self.assertEqual(ast.dump(oldnode),ast.dump(newnode))

    def test_authenticated_all_legacy_outputs_probabilities_rng_unchanged(self):
        self.assertEqual(len(kernel_parity(benchmarks(load_pool()),self.old)),12)
        self.assertEqual(len(candidate_parity(load_pool(),self.old)),16)


if __name__=='__main__':unittest.main()
