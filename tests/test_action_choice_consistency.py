"""Causal choices, empirical first events and bounded ownership/RNG checks."""
from copy import deepcopy
from dataclasses import replace
import json
import math
import random
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data.action_choice import project_choices,project_candidate,choice_probabilities,G4
from nba_gm_data.creation_passing import resolve_drive,resolve_candidate,CHOICE_POLICY,HELP_RESPONSE_POLICY
from nba_gm_data.interior_game import validate_accounting,shot_probabilities
from nba_gm_data import sim
from nba_gm_data.shot_geometry import contest_at_angle
from experiments.action_choice_consistency.fixtures import pinned_pilot,make_case,decision,observed_draws
from experiments.action_choice_consistency.empirical import validate_candidate


class ActionChoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pilot=pinned_pilot()

    def prepared(self,**kwargs):
        state,context,config=make_case(self.pilot,**kwargs)
        return state,decision(state,kwargs.get('remaining',24)),context,config

    def test_projection_does_not_peek_at_outcome_draws_or_call_rng_or_sampler(self):
        s,_,_,_=self.prepared(families=('F03','F04','F06'))
        a=observed_draws();b=list(a)
        for index in (5,6,7,8,9,10,15,16,17,18,19,34,35,37):b[index]=.999999
        da=decision(s,draws=a);db=decision(s,draws=b)
        with (patch('random.Random',side_effect=AssertionError('projection RNG')),
              patch('nba_gm_data.creation_passing.sample_delivery',side_effect=AssertionError('projection sampling'))):
            x=project_choices(da['frame'],da['options']);y=project_choices(db['frame'],db['options'])
        self.assertEqual(x,y)

    def test_probabilities_normalize_and_point_moments_are_bounded(self):
        _,d,_,_=self.prepared(families=('F03','F04','F06'))
        for name in d['options']:
            p=project_candidate(d['frame'],name,d['options'])
            self.assertAlmostEqual(sum(p['branches'].values()),1)
            self.assertTrue(all(-1e-12<=v<=1+1e-12 for v in p['branches'].values()))
            self.assertTrue(0<=p['expected_points']<=3);self.assertTrue(0<=p['points_second_moment']<=9)
            self.assertTrue(0<=p['zero_points_probability']<=1)

    def test_actual_finish_mixture_and_dunk_strength_replace_layup_standin(self):
        values=[]
        for grade in (10,90):
            _,d,_,_=self.prepared(families=(),available=0,finish_mix=(0,0,0,1,0),changes={'creator':{'S12':grade}})
            values.append(project_candidate(d['frame'],'finish',d['options'])['expected_points'])
        self.assertGreater(values[1],values[0]+.5)
        individual=[]
        for mix in ((1,0,0,0,0),(0,0,0,1,0),(.4,0,0,.6,0)):
            _,d,_,_=self.prepared(families=(),finish_mix=mix)
            individual.append(project_candidate(d['frame'],'finish',d['options'])['expected_points'])
        self.assertAlmostEqual(individual[2],.4*individual[0]+.6*individual[1])

    def test_foul_and_ft_value_are_counted_once(self):
        rows=[];ft=[]
        for grade in (10,95):
            _,d,_,_=self.prepared(families=(),start=(1,1.5),changes={'creator':{'S07':grade},'helper':{'S45':10}})
            rows.append(project_candidate(d['frame'],'finish',d['options']));ft.append(d['frame']['coupled']['profiles'][d['frame']['creator_id']].ft_probability)
        self.assertAlmostEqual(rows[0]['branches']['shooting_foul'],rows[1]['branches']['shooting_foul'])
        self.assertAlmostEqual(rows[1]['expected_points']-rows[0]['expected_points'],2*rows[0]['branches']['shooting_foul']*(ft[1]-ft[0]))

    def test_receiver_coverage_is_used_instead_of_reference_shooting_context(self):
        points=[]
        for grade in (10,95):
            _,d,_,_=self.prepared(families=('F06',),commitment=0,start=(3,6.8),changes={'helper':{'S40':grade}})
            points.append(project_candidate(d['frame'],'F06',d['options'])['expected_points'])
        self.assertGreater(points[0],points[1])

    def test_recognition_execution_and_receiving_are_distinct_stages(self):
        rows=[]
        for execution,receiving in ((20,70),(95,70),(95,95)):
            _,d,_,_=self.prepared(families=('F03',),changes={'creator':{'F03.execution':execution},'roller':{'S14':receiving}})
            rows.append(project_candidate(d['frame'],'F03',d['options']))
        self.assertGreater(rows[0]['branches']['inaccurate_delivery'],rows[1]['branches']['inaccurate_delivery'])
        self.assertEqual(rows[1]['branches']['inaccurate_delivery'],rows[2]['branches']['inaccurate_delivery'])
        self.assertGreater(rows[2]['expected_points'],rows[1]['expected_points'])
        state,_,_,_=self.prepared(families=('F03',),changes={'creator':{'F03.recognition':0}})
        draws=observed_draws();draws[29]=.99
        self.assertNotIn('F03',decision(state,draws=draws)['options'])

    def test_willingness_is_selection_preference_not_a_false_physical_failure(self):
        rows=[]
        for willingness in (.1,.9):
            _,d,_,_=self.prepared(families=('F06',),start=(2,1),shoot_probability=willingness)
            rows.append(project_choices(d['frame'],d['options']))
        a,b=rows
        self.assertAlmostEqual(a['candidates']['F06']['expected_points'],b['candidates']['F06']['expected_points'])
        self.assertGreater(b['scores']['F06'],a['scores']['F06'])
        _,d,_,_=self.prepared(families=('F06',),shoot_probability=0)
        self.assertNotIn('F06',d['options'])

    def test_spacing_still_moves_the_helper_and_changes_actual_chances(self):
        rows=[]
        for grade,willing in ((50,.1),(90,.85)):
            _,d,_,_=self.prepared(families=('F06',),start=None,shooter_grade=grade,shoot_probability=willing)
            rows.append(d)
        self.assertNotEqual(rows[0]['frame']['start'],rows[1]['frame']['start'])
        self.assertNotEqual(project_candidate(rows[0]['frame'],'F06',rows[0]['options'])['expected_points'],project_candidate(rows[1]['frame'],'F06',rows[1]['options'])['expected_points'])

    def test_early_late_and_unavailable_help_use_actual_contests(self):
        values=[]
        for control in ({'start':(1,1.5)},{'start':(10,10)},{'available':0}):
            _,d,_,_=self.prepared(families=(),finish_mix=(1,0,0,0,0),**control)
            values.append(project_candidate(d['frame'],'finish',d['options'])['expected_points'])
        self.assertLess(values[0],values[1]);self.assertAlmostEqual(values[1],values[2])

    def test_late_window_failure_is_exposed_before_receiver_catch_probability(self):
        _,base,_,_=self.prepared(families=('F03',))
        option=base['options']['F03'];end=base['frame']['elapsed']+option['delivery']['flight_s']+.05+.25*option['delivery']['window_radius_m']*.3
        _,d,_,_=self.prepared(families=('F03',),roll_window=end)
        p=project_candidate(d['frame'],'F03',d['options'])
        self.assertGreater(p['branches']['late_delivery'],0)
        self.assertLess(p['expected_points'],project_candidate(base['frame'],'F03',base['options'])['expected_points'])
        self.assertTrue(validate_candidate(d,'F03',n=4096)['all_passed'])

    def test_clock_has_priority_over_inaccurate_delivery_as_in_kernel(self):
        _,d,_,_=self.prepared(families=('F03',))
        d['frame']['remaining_s']=d['frame']['elapsed']+d['options']['F03']['delivery']['flight_s']-1e-6
        p=project_candidate(d['frame'],'F03',d['options'])
        self.assertAlmostEqual(p['branches']['shot_clock_turnover'],1);self.assertEqual(p['expected_points'],0)
        self.assertTrue(validate_candidate(d,'F03',n=1024)['all_passed'])

    def test_short_clock_integrates_only_finish_types_that_can_complete(self):
        _,d,_,_=self.prepared(families=(),finish_mix=(.5,0,0,.5,0),remaining=1.25)
        p=project_candidate(d['frame'],'finish',d['options'])
        self.assertAlmostEqual(p['branches']['shot_clock_turnover'],.5)
        self.assertTrue(validate_candidate(d,'finish',n=2048)['all_passed'])

    def test_reset_is_bounded_clock_aware_and_cannot_manufacture_value(self):
        values=[]
        for clock in (24,12,6,2):
            _,d,_,_=self.prepared(families=('F06',),remaining=clock)
            p=project_choices(d['frame'],d['options']);r=p['candidates']['reset'];values.append(r['expected_points'])
            self.assertEqual(r['continuation_depth'],1);self.assertFalse(r['windowed_roll_reused'])
            self.assertLessEqual(r['expected_points'],max(v['expected_points'] for k,v in p['candidates'].items() if k!='reset'))
        self.assertTrue(all(a>=b for a,b in zip(values,values[1:])))
        self.assertEqual(values[-1],0)

    def test_handling_is_sunk_once_and_reset_charges_only_the_future_exposure(self):
        rows=[]
        for security in (20,95):
            _,d,_,_=self.prepared(families=('F06',),changes={'creator':{'S17':security}})
            rows.append(project_choices(d['frame'],d['options']))
        a,b=rows
        self.assertEqual(a['candidates']['finish']['expected_points'],b['candidates']['finish']['expected_points'])
        self.assertEqual(a['candidates']['F06']['expected_points'],b['candidates']['F06']['expected_points'])
        self.assertGreater(a['current_handling_probability'],b['current_handling_probability'])
        self.assertGreater(b['candidates']['reset']['expected_points'],a['candidates']['reset']['expected_points'])
        s,_,_,_=self.prepared();d=observed_draws();d[24]=0
        with patch('nba_gm_data.action_choice.project_choices',side_effect=AssertionError('loss must precede choice')):
            r=resolve_drive(s,s['audit_context']['ids'][0],'response_a','response_b',d,24)
        self.assertEqual(r['outcome'],'handling_loss');self.assertNotIn('choice_projection',r['record'])

    def test_imperfect_choice_and_risk_survive_without_rewarding_guaranteed_failure(self):
        s,_,_,_=self.prepared(families=('F06',));pid=s['audit_context']['ids'][0]
        d=observed_draws();good=resolve_drive(s,pid,'response_a','response_b',d,24)
        d[32]=0;bad=resolve_drive(s,pid,'response_a','response_b',d,24)
        self.assertTrue(bad['record']['bad_choice']);self.assertEqual(bad['record']['choice'],min(bad['record']['choice_scores'],key=bad['record']['choice_scores'].get))
        d=observed_draws();d[33]=1-1e-15;other=resolve_drive(s,pid,'response_a','response_b',d,24)
        self.assertNotEqual(good['record']['choice'],other['record']['choice'])
        rows=[]
        for risk in (0,1):
            _,q,_,_=self.prepared(changes={'creator':{'T07':risk}},remaining=.1)
            rows.append(project_choices(q['frame'],q['options']))
        self.assertTrue(all(v<=0 for v in rows[1]['scores'].values()))

    def test_negative_utilities_stay_ordered_instead_of_flattening_all_passes(self):
        probabilities=choice_probabilities({'better':-.1,'worse':-.4})
        self.assertGreater(probabilities['better'],probabilities['worse'])
        self.assertAlmostEqual(sum(probabilities.values()),1)
        shifted=choice_probabilities({'better':3.9,'worse':3.6})
        self.assertAlmostEqual(probabilities['better'],shifted['better'])
        rows=[]
        for execution in (20,95):
            _,d,_,_=self.prepared(families=('F03',),changes={'creator':{'F03.execution':execution}})
            rows.append(project_choices(d['frame'],d['options']))
        self.assertGreater(rows[1]['good_choice_probabilities']['F03'],rows[0]['good_choice_probabilities']['F03'])

    def test_good_and_deliberately_bad_choice_mixture_is_explicit(self):
        _,d,_,_=self.prepared(families=('F06',));p=project_choices(d['frame'],d['options'])
        self.assertAlmostEqual(sum(p['effective_choice_probabilities'].values()),1)
        worst=min(p['scores'],key=p['scores'].get)
        for key,prob in p['good_choice_probabilities'].items():
            self.assertGreater(prob,0)
            self.assertAlmostEqual(p['effective_choice_probabilities'][key],(1-p['bad_choice_probability'])*prob+p['bad_choice_probability']*(key==worst))

    def test_local_angular_reuse_matches_full_candidate_resolution_including_primary_contest(self):
        for coverage in (None,'show_then_recover'):
            _,d,_,_=self.prepared(coverage=coverage,families=('F03','F04','F06'))
            for name in d['options']:
                option=d['options'][name];error=None if name=='finish' else option['delivery']['window_radius_m']*.3
                for angle,_ in G4:
                    draws=[.5]*48;draws[19]=angle
                    light=resolve_candidate(d['frame'],name,d['options'],[.5]*48,{},delivery_error_override=error,finish_kind_override='layup' if name=='finish' else None,include_details=False)
                    full=resolve_candidate(d['frame'],name,d['options'],draws,{},delivery_error_override=error,finish_kind_override='layup' if name=='finish' else None)
                    if full['kind']!='shot':continue
                    responses=light['plan'].get('_projection_contests',(light['plan']['response'],));chosen=None;strength=-1
                    for response in responses:
                        value=contest_at_angle(response['_contest_basis'],angle*180) if response else None
                        power=value['conversion_reduction']+value['block_probability'] if value else 0
                        if power>=strength:chosen=value;strength=power
                    for key in ('conversion_reduction','block_probability','foul_probability'):
                        self.assertEqual(chosen[key] if chosen else 0,full['plan']['response'][key] if full['plan']['response'] else 0)

    def test_projection_cost_is_structurally_bounded_without_recursive_reset(self):
        _,d,_,_=self.prepared(coverage='show_then_recover',families=('F03','F04','F06'))
        p=project_choices(d['frame'],d['options'])
        self.assertLessEqual(p['candidate_count'],5);self.assertLessEqual(p['candidate_resolution_calls'],16)
        self.assertLessEqual(p['shot_plan_evaluations'],32);self.assertLessEqual(p['clock_boundary_evaluations'],66)
        self.assertEqual(p['candidates']['reset']['continuation_depth'],1)

    def test_sampled_delayed_catch_still_uses_the_shared_physical_gate(self):
        _,d,_,_=self.prepared(coverage='show_then_recover',families=('F03',))
        self.assertIn('F03',d['options'])
        with patch('nba_gm_data.creation_passing.sample_delivery',return_value={'accurate':True,'error_m':0,'quality':1,'catch_delay_s':5}):
            r=resolve_candidate(d['frame'],'F03',d['options'],observed_draws(),{})
        self.assertEqual(r['outcome'],'late_delivery');self.assertNotIn('plan',r)

    def test_empirical_first_event_checks_cover_finish_pass_and_screen_contexts(self):
        for kwargs,name in [({'families':()},'finish'),({'families':('F06',),'start':(3,6.8),'commitment':0},'F06'),
                ({'families':('F03',)},'F03'),({'families':('F04',),'changes':{'roller':{'S14':30}}},'F04'),
                ({'coverage':'show_then_recover','families':('F03','F04')},'F03')]:
            with self.subTest(name=name,kwargs=kwargs):
                _,d,_,_=self.prepared(**kwargs);self.assertTrue(validate_candidate(d,name,n=2048)['all_passed'])

    def test_revision_source_ownership_mutation_and_release(self):
        source=deepcopy(self.pilot['source_documents']);s,d,c,x=self.prepared(families=('F06',))
        _,_,old=make_case(self.pilot,consistent=False)
        self.assertNotEqual(x.revision,old.revision)
        with self.assertRaisesRegex(ValueError,'helper'):replace(x.offense.creation,help_response_policy='legacy_timely_v1')
        before={pid:p.inputs.to_dict() for pid,p in s['profiles'].items()};expected=project_choices(d['frame'],d['options'])
        mutated=deepcopy(expected);mutated['candidates']['finish']['expected_points']=999
        self.assertEqual(project_choices(d['frame'],d['options']),expected)
        json.dumps(expected);self.assertNotIn('_contest_basis',str(expected))
        self.assertEqual(before,{pid:p.inputs.to_dict() for pid,p in s['profiles'].items()});self.assertEqual(source,self.pilot['source_documents'])
        refs=[weakref.ref(x),weakref.ref(x.offense.creation),weakref.ref(s['profiles'][s['audit_context']['ids'][0]].inputs)]
        del s,d,c,x
        self.assertTrue(all(ref() is None for ref in refs))

    def test_resets_spend_clock_and_continuation_never_rescreens(self):
        s,_,_,_=self.prepared(coverage='show_then_recover',families=('F06',));d=observed_draws()
        for index in (28,29,30,31):d[index]=.999
        d[25]=.999;clock=24;count=0
        while clock>0:
            r=resolve_drive(s,s['audit_context']['ids'][0],'response_a','response_b',d,clock,screen_allowed=count==0)
            self.assertEqual(r['kind'],'reset');self.assertEqual(r['record']['choice_projection']['candidates']['reset']['expected_points'],0)
            clock-=r['elapsed_s'];count+=1
            if count>1:self.assertEqual(r['record']['screen_action']['reason'],'continuation_no_rescreen')
            self.assertLessEqual(count,6)

    def test_small_kernel_accounting_both_policies_and_screen_coverages(self):
        for consistent in (False,True):
            for coverage in ('stay','show_then_recover'):
                _,c,x=make_case(self.pilot,consistent=consistent,coverage=coverage,start=None,possessions=8)
                r=sim.sim_game_with_context(c,'response_fixture',seed=17,interior_experiment=x);validate_accounting(r)
                events=[e for t in r.team_lines for e in t['interior_experiment']['offense_attack_ledger']]
                self.assertTrue(any('choice_projection' in e.get('creation_chain',{}) for e in events) if consistent else all('choice_projection' not in e.get('creation_chain',{}) for e in events))


if __name__=='__main__':unittest.main()
