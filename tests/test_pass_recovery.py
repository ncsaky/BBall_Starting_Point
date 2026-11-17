"""Bounded recovery geometry/outcomes; controlled branches are not calibration."""
from copy import deepcopy
from dataclasses import replace
import json
import math
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data.creation_passing import prepare_drive_decision,resolve_candidate,resolve_drive
from nba_gm_data.action_choice import project_candidate,project_choices
from nba_gm_data.pass_recovery import (RecoveryCoefficients,complete_receipt,recovery_geometry,apply_continuation,RecoveryDriveSetup,advance_after_reset)
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from experiments.pass_recovery.fixtures import pool,fixture,synthetic,BASE,IDS
from experiments.action_choice_consistency.fixtures import observed_draws


class PassRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pool=pool()

    def prepared(self,*,p=None,**kwargs):
        s,c,x=fixture(p or self.pool,**{'action':'pop',**kwargs});d=observed_draws()
        v=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',d,24)
        return s,c,x,v,d

    def candidate(self,*,error=.9,direction=1,name='pop',secure=None,**kwargs):
        s,c,x,v,d=self.prepared(**kwargs);d[44]=(direction+.5)/6
        a=resolve_candidate(v['frame'],name,v['options'],d,{},delivery_error_override=error)
        if secure is not None:a=complete_receipt(a,secure,24)
        return a,s,c,x,v,d

    def test_coefficients_are_finite_bounded_and_immutable(self):
        for kw in ({'horizon_s':0},{'reaction_s':-.1},{'horizontal_reach_fraction':2},{'search_steps':0},{'integration_panels':True},{'gravity_m_s2':float('nan')}):
            with self.assertRaises(ValueError):RecoveryCoefficients(**kw)

    def test_all_source_records_and_views_are_preserved_by_policy_enable(self):
        before={k:v.to_dict() for k,v in self.pool['views'].items()};s,c,x=fixture(self.pool)
        self.assertEqual(before,{k:v.to_dict() for k,v in self.pool['views'].items()})
        self.assertEqual(set(s['receiving_spans_m']),set(s['profiles']))
        for pid,p in s['profiles'].items():self.assertIs(p.inputs,s['coupled']['profiles'][pid].inputs)

    def test_new_reach_dependency_uses_stored_wingspan_without_unit_conversion(self):
        s,_,_=fixture(self.pool)
        for pid,v in self.pool['views'].items():
            if pid not in s['receiving_spans_m']:continue
            raw=v.to_dict()['inputs']['P02']['value']['measurements'][0]['value']
            self.assertEqual(s['receiving_spans_m'][pid],raw/100)

    def test_clean_candidate_physics_and_probabilities_match_old_channel(self):
        a,_,_,_,v,d=self.candidate(error=.1)
        old=resolve_candidate({**v['frame'],'_legacy_delivery':True},'pop',v['options'],d,{},delivery_error_override=.1)
        self.assertEqual(a['record']['receipt_category'],'clean')
        self.assertEqual(a['elapsed_s'],old['elapsed_s']);self.assertEqual(a['plan'],old['plan'])
        self.assertFalse(a['record']['completed_pass']);self.assertIsNone(a['record']['actual_receipt_secured'])

    def test_actual_securing_occurs_once_and_updates_planning_diagnostics(self):
        a,_,_,_,_,_=self.candidate(error=.1,secure=0)
        self.assertTrue(a['record']['actual_receipt_secured']);self.assertTrue(a['record']['completed_pass']);self.assertEqual(a['plan']['reception'],1)
        self.assertTrue(a['record']['pass']['actual_receipt_secured'])
        self.assertIs(complete_receipt(a,1,24),a)
        b,_,_,_,_,_=self.candidate(error=.1,secure=1);self.assertEqual(b['outcome'],'failed_catch');self.assertFalse(b['record']['completed_pass'])

    def test_direction_changes_recovery_and_loss_at_fixed_radial_error(self):
        over=self.candidate(error=.9,direction=0)[0];short=self.candidate(error=.9,direction=1)[0]
        self.assertEqual(over['kind'],'turnover');self.assertEqual(short['record']['receipt_category'],'recovered')
        self.assertEqual(over['record']['pass']['error_m'],short['record']['pass']['error_m'])

    def test_unreachable_high_ball_is_not_automatically_saved(self):
        a,_,_,_,_,_=self.candidate(error=8,direction=4)
        self.assertEqual(a['kind'],'turnover');self.assertEqual(a['outcome'],'pass_unreachable');self.assertFalse(a['record']['actual_receipt_secured'])

    def test_out_of_bounds_remains_a_real_loss(self):
        a,_,_,_,_,_=self.candidate(error=20,direction=3)
        self.assertEqual(a['outcome'],'pass_out_of_bounds');self.assertNotIn('plan',a)

    def test_ground_ball_followup_is_explicitly_outside_bounded_airborne_model(self):
        a,_,_,_,_,_=self.candidate(error=2,direction=5)
        self.assertEqual(a['outcome'],'pass_grounded')
        self.assertEqual(a['record']['receipt_category'],'lost')

    def test_ball_and_receiver_do_not_teleport_or_hold_airborne_forever(self):
        a,s,_,_,v,_=self.candidate(error=.9,direction=1);g=a['record']['recovery_geometry']
        self.assertGreater(g['capture_s'],0);self.assertGreater(g['delay_s'],g['capture_s'])
        self.assertNotEqual(g['endpoint_m'],g['ball_at_capture_m'])
        rid=g['receiver_id'];m=s['profiles'][rid]
        from nba_gm_data.creation_passing import motion_time
        self.assertLessEqual(g['reaction_s']+motion_time(g['receiver_travel_m'],m.acceleration_m_s2,m.speed_m_s),g['capture_s']+1e-4)

    def test_hands_do_not_become_a_second_physical_speed_or_reaction_grade(self):
        p1=synthetic(self.pool,{'turner':{'S14':10}});p2=synthetic(self.pool,{'turner':{'S14':95}})
        a=self.candidate(p=p1)[0];b=self.candidate(p=p2)[0]
        self.assertEqual(a['record']['recovery_geometry']['capture_s'],b['record']['recovery_geometry']['capture_s'])
        self.assertLess(a['receipt_probability'],b['receipt_probability'])

    def test_recovery_pays_time_and_changes_actual_shot_geometry(self):
        clean=self.candidate(error=.1)[0];bad=self.candidate(error=.9)[0]
        self.assertGreater(bad['elapsed_s'],clean['elapsed_s'])
        g=bad['record']['recovery_geometry'];self.assertEqual(tuple(g['receiver_feet_m']),tuple(bad['plan']['details']['derived_action_context']['shot_position_m']))
        self.assertLessEqual(bad['plan']['off']['three_pct'],clean['plan']['off']['three_pct'])

    def test_expired_pop_recovers_to_paid_reset_and_actual_recipient(self):
        a,s,_,_,_,_=self.candidate(coverage='stay',secure=0)
        self.assertEqual(a['kind'],'reset');self.assertEqual(a['continuation_creator_id'],IDS['turner'])
        self.assertGreater(a['elapsed_s'],s['spec'].reset_cost_s)
        new=apply_continuation(s,a['recovery_continuation']);setup=new['setups'][IDS['turner']]
        self.assertIsInstance(setup,RecoveryDriveSetup)
        self.assertEqual((setup.origin_x_m,setup.origin_y_m),a['recovery_continuation']['ball_position_m'])
        self.assertNotIn('origin_x_m',vars(s['setups'][IDS['turner']]))

    def test_receiving_failure_on_recovered_reset_loses_ball_instead_of_free_reset(self):
        a,_,_,_,_,_=self.candidate(coverage='stay',secure=1)
        self.assertEqual((a['kind'],a['outcome']),('turnover','failed_catch'));self.assertEqual(a['responsible'],IDS['turner'])

    def test_followup_attack_pays_actual_origin_to_drive_distance(self):
        a,s,_,_,_,_=self.candidate(coverage='stay',secure=0);new=apply_continuation(s,a['recovery_continuation'])
        draws=observed_draws();r=resolve_drive(new,IDS['turner'],'response_a','response_b',draws,24-a['elapsed_s'],screen_allowed=False)
        self.assertIn('actual_continuation_origin_m',r['record']['containment'])
        self.assertGreater(r['record']['containment']['attacker_clear_s'],2)
        self.assertEqual(r['record']['screen_action']['kind'],'none')

    def test_repeated_paid_reset_updates_scoped_origin_and_advances_defense(self):
        a,s,_,_,_,_=self.candidate(coverage='stay',secure=0);new=apply_continuation(s,a['recovery_continuation']);rid=IDS['turner']
        again=advance_after_reset(new,{'elapsed_s':5,'record':{'help':{'committed':False}}},rid);setup=again['setups'][rid]
        self.assertEqual((setup.origin_x_m,setup.origin_y_m),(setup.drive_x_m,setup.drive_y_m))
        self.assertNotEqual((new['setups'][rid].origin_x_m,new['setups'][rid].origin_y_m),(setup.origin_x_m,setup.origin_y_m))

    def test_supported_arm_span_changes_reachable_capture_timing_once(self):
        p1=synthetic(self.pool,{'turner':{'P02':210}});p2=synthetic(self.pool,{'turner':{'P02':240}})
        a=self.candidate(p=p1,error=1.3)[0];b=self.candidate(p=p2,error=1.3)[0]
        self.assertEqual(a['record']['receipt_category'],'recovered');self.assertEqual(b['record']['receipt_category'],'recovered')
        self.assertLess(b['record']['recovery_geometry']['capture_s'],a['record']['recovery_geometry']['capture_s'])

    def test_defender_race_can_prevent_recovery(self):
        p=synthetic(self.pool,{'wemb':{'S41':100,'S44':100,'S43':95}})
        s,c,x,v,d=self.prepared(p=p);o=deepcopy(v['options']['pop']);o['coverage_position']=o['target']
        # Supply a close actual coverage route, rather than editing named skill.
        frame={**v['frame'],'screen':None};g=recovery_geometry(frame,'F06',o,.9,4)
        self.assertEqual(g['lost'],'recovery_defended')
        d[44]=.75;d[35]=0
        a=resolve_candidate(frame,'F06',{'F06':o},d,{},delivery_error_override=.9)
        self.assertEqual(a['steal_by'],IDS['wemb'])

    def test_unknown_receiving_reach_is_rejected_not_imputed(self):
        p=synthetic(self.pool,{'turner':{'P02':None}})
        fixture(p,enabled=False)
        with self.assertRaisesRegex(ValueError,'P02'):fixture(p)

    def test_recovered_midrange_uses_actual_location_and_catch_two_point_skill(self):
        from nba_gm_data.pass_recovery import RecoveredShotContext
        from nba_gm_data.offense_response import plan_attack
        s,c,x,v,d=self.prepared();context=RecoveredShotContext(finish_kind='midrange',shot_mode='catch',received_pass=True,delivery_quality=.5,shot_position_m=(3,5.8))
        d[17]=0
        a=plan_attack(s['coupled'],IDS['turner'],'short_paint',d,'response_b',None,None,action_context=context)
        self.assertEqual(a['details']['shooting']['skill_id'],'S04')
        self.assertAlmostEqual(a['details']['shooting']['distance_m'],math.hypot(3,5.8))

    def test_lob_recovery_does_not_preserve_a_lob_or_dunk_finish(self):
        s,c,x,v,d=self.prepared(action='slip');found=False
        for direction in range(6):
            d[44]=(direction+.5)/6
            a=resolve_candidate(v['frame'],'F04',v['options'],d,{},delivery_error_override=1.1)
            if a['record'].get('receipt_category')=='recovered':
                found=True
                if a['kind']=='shot':self.assertNotIn(a['plan']['details']['finish']['finish'],('lob','dunk'))
        self.assertTrue(found)

    def test_bad_moving_roll_has_real_window_and_ground_finish_costs(self):
        s,c,x,v,d=self.prepared(action='roll');d[44]=.75
        a=resolve_candidate(v['frame'],'F03',v['options'],d,{},delivery_error_override=.9)
        self.assertIn(a['record']['receipt_category'],('recovered','lost'))
        if a['kind']=='shot':self.assertNotEqual(a['plan']['details']['finish']['finish'],'dunk')

    def test_clock_precedes_unsecured_receipt_and_points(self):
        a,_,_,_,_,_=self.candidate();b=complete_receipt(a,0,1)
        self.assertIsNone(b['record']['actual_receipt_secured']);self.assertFalse(b['record']['completed_pass'])

    def test_projection_normalizes_clean_recovered_lost_and_reset_mass(self):
        for action,name in [('pop','pop'),('roll','F03'),('slip','F04')]:
            s,c,x,v,d=self.prepared(action=action);p=project_candidate(v['frame'],name,v['options'])
            self.assertAlmostEqual(sum(p['branches'].values()),1);self.assertAlmostEqual(sum(p['receipt_planned_probabilities'].values()),1)
            self.assertGreater(p['receipt_planned_probabilities']['recovered'],0)
            self.assertLessEqual(p['candidate_resolution_calls'],208)
            self.assertEqual(p['recovery_reset_continuation_credit'],0)

    def test_projection_does_not_peek_at_delivery_direction_or_catch_draws(self):
        s,c,x,v,d=self.prepared();a=project_choices(v['frame'],v['options']);other=list(d)
        for key in (15,34,35,44):other[key]=.999
        b=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',other,24)
        with patch('random.Random',side_effect=AssertionError('projection RNG')),patch('nba_gm_data.creation_passing.sample_delivery',side_effect=AssertionError('projection sampler')):
            self.assertEqual(a,project_choices(b['frame'],b['options']))

    def test_willingness_changes_selection_without_changing_receipt_physics(self):
        rows=[]
        for value in (.1,.9):
            p=synthetic(self.pool,{'turner':{'T01':value}});s,c,x,v,d=self.prepared(p=p)
            rows.append(project_choices(v['frame'],v['options']))
        self.assertEqual(rows[0]['candidates']['pop']['branches'],rows[1]['candidates']['pop']['branches'])
        self.assertLess(rows[0]['scores']['pop'],rows[1]['scores']['pop'])
        p=synthetic(self.pool,{'turner':{'T01':0}});s,c,x,v,d=self.prepared(p=p);self.assertNotIn('pop',v['options'])

    def test_preexisting_waiting_loss_ledger_omission_is_corrected_without_recounting(self):
        data=json.loads((BASE/'pre-existing-wait-loss-accounting-reproduction.json').read_text());self.assertTrue(data['validator_failed'])
        r=SimpleNamespace(**data['result']);validate_accounting(r)
        self.assertTrue(any(e['outcome']=='waiting_loss' for t in r.team_lines for e in t['interior_experiment']['offense_attack_ledger']))

    def test_actual_recovery_reset_transfers_receiver_and_pays_next_drive_in_kernel(self):
        from experiments.pass_recovery.fixtures import scripted_reset_kernel
        r=scripted_reset_kernel();validate_accounting(r)
        events=r.team_lines[0]['interior_experiment']['offense_attack_ledger'];first=events[0];second=events[1]
        self.assertEqual(first['outcome'],'reset');self.assertEqual(first['creation_chain']['receipt_category'],'recovered')
        self.assertTrue(first['creation_chain']['actual_receipt_secured'])
        self.assertEqual(second['creation_chain']['creator_id'],IDS['turner'])
        self.assertGreater(second['creation_chain']['containment']['attacker_clear_s'],2)

    def test_new_policy_kernel_is_deterministic_and_accounted(self):
        s,c,x=fixture(self.pool,possessions=8)
        a=sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x);b=sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x)
        self.assertEqual(to_plain(a),to_plain(b));validate_accounting(a)

    def test_source_mutation_diagnostics_and_state_release(self):
        before={k:v.to_dict() for k,v in self.pool['views'].items()};s,c,x,v,d=self.prepared();p=project_choices(v['frame'],v['options'])
        self.assertNotIn('_contest_basis',json.dumps(p));self.assertEqual(before,{k:v.to_dict() for k,v in self.pool['views'].items()})
        refs=[weakref.ref(x),weakref.ref(x.offense.creation)];del s,c,x,v,d,p
        self.assertTrue(all(r() is None for r in refs))


if __name__=='__main__':unittest.main()
