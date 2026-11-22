"""Exact candidate-local optimization, compared to authenticated milestone12."""
from dataclasses import replace
import math
import unittest
from unittest.mock import patch
import weakref
from nba_gm_data import pass_recovery as recovery
from nba_gm_data.creation_passing import prepare_drive_decision,resolve_candidate
from nba_gm_data.action_choice import project_candidate,project_choices
from experiments.pass_recovery.fixtures import pool,fixture,IDS
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.recovery_projection_cost.verification import reference_modules,use_reference


# Retired experimental engine (Track C). These tests compare against frozen reference snapshots in output/, which were
# never kept in git and were removed in the 2026-11-21 disk cleanup; they cannot be rebuilt exactly. Skip, with the
# reason, when a snapshot is missing rather than failing. Normal gameplay does not use this engine.
_RETIRED_SNAPSHOTS = ['mixed-pop-validation-2026-11-16']


def setUpModule():
    from pathlib import Path
    missing = [n for n in _RETIRED_SNAPSHOTS if not (Path(__file__).resolve().parents[1] / "output" / n).exists()]
    if missing:
        raise unittest.SkipTest("retired experimental engine: reference snapshot missing (deleted 2026-11-21, never in git): "
                                + ", ".join(missing))


class RecoveryProjectionCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pool=pool();cls.modules=reference_modules()

    def decision(self,actor='turner',action='pop',**kwargs):
        s,c,x=fixture(self.pool,actor,action=action,**kwargs);draws=observed_draws()
        return prepare_drive_decision(s,IDS['curry'],'response_a','response_b',draws,x.offense.creation.possession_budget_s),s,c,x,draws

    def states(self):
        for actor in ('turner','towns','holmgren','jokic'):
            for action,name in [('pop','pop'),('roll','F03'),('slip','F04')]:
                for kw in ({},{'clock':3}):
                    d,s,c,x,draws=self.decision(actor,action,**kw)
                    yield d,name

    def test_2304_geometry_results_match_frozen_exactly_including_boundaries(self):
        errors=(0,.01,.3,.5,.7,.9,1.1,1.5,2,3,4,6,10,20,math.nextafter(.9,0),math.nextafter(.9,math.inf));count=0
        for d,name in self.states():
            frame=d['frame'];option=d['options'][name];cached={**frame,'_recovery_geometry_basis':recovery.geometry_basis(frame,name,option)}
            for direction in range(6):
                for error in errors:
                    a=recovery.recovery_geometry(cached,name,option,error,direction)
                    with use_reference(self.modules):b=self.modules['nba_gm_data.pass_recovery'].recovery_geometry(frame,name,option,error,direction)
                    self.assertEqual(a,b,(name,error,direction));count+=1
        self.assertEqual(count,2304)

    def test_48_order4_and8_projections_match_frozen_exactly(self):
        for d,name in self.states():
            for order in (4,8):
                a=project_candidate(d['frame'],name,d['options'],order=order)
                with use_reference(self.modules):b=self.modules['nba_gm_data.action_choice'].project_candidate(d['frame'],name,d['options'],order=order)
                self.assertEqual(a,b,(name,order));self.assertAlmostEqual(sum(a['branches'].values()),1)

    def test_basis_is_built_once_and_never_attached_to_input_frame_or_state(self):
        d,s,c,x,draws=self.decision();keys=set(d['frame']);statekeys=set(s)
        with patch.object(recovery,'geometry_basis',wraps=recovery.geometry_basis) as build:project_candidate(d['frame'],'pop',d['options'])
        self.assertEqual(build.call_count,1);self.assertEqual(set(d['frame']),keys);self.assertEqual(set(s),statekeys)

    def test_new_time_position_defender_and_creator_always_rebuild_basis(self):
        d,s,c,x,draws=self.decision();frame=d['frame'];option=d['options']['pop'];before=recovery.geometry_basis(frame,'pop',option)
        project_candidate(frame,'pop',d['options'])
        moved={**frame,'elapsed':frame['elapsed']+.37,'ball':(1.7,2.1),'helper_position':(2.2,2.4)}
        a=project_candidate(moved,'pop',d['options'])
        with use_reference(self.modules):b=self.modules['nba_gm_data.action_choice'].project_candidate(moved,'pop',d['options'])
        self.assertEqual(a,b);self.assertNotEqual(before['axes'],recovery.geometry_basis(moved,'pop',option)['axes'])
        other,_,_,_,_=self.decision('jokic');self.assertNotEqual(before['rid'],recovery.geometry_basis(other['frame'],'pop',other['options']['pop'])['rid'])

    def test_actual_selected_resolution_keeps_full_geometry_diagnostics(self):
        d,s,c,x,draws=self.decision(coverage='stay');draws[44]=.25
        a=resolve_candidate(d['frame'],'pop',d['options'],draws,{},delivery_error_override=.9)
        with use_reference(self.modules):b=self.modules['nba_gm_data.creation_passing'].resolve_candidate(d['frame'],'pop',d['options'],draws,{},delivery_error_override=.9)
        self.assertEqual(a,b);self.assertIn('recovery_geometry',a['record']);self.assertIn('recovery_continuation',a)

    def test_reset_transferred_creator_has_no_previous_candidate_cache(self):
        d,s,c,x,draws=self.decision(coverage='stay');draws[44]=.25
        a=resolve_candidate(d['frame'],'pop',d['options'],draws,{},delivery_error_override=.9);new=recovery.apply_continuation(s,a['recovery_continuation']);creator=a['continuation_creator_id']
        decision=prepare_drive_decision(new,creator,'response_a','response_b',draws,18,screen_allowed=False)
        if 'frame' in decision:
            current=project_choices(decision['frame'],decision['options'])
            with use_reference(self.modules):old=self.modules['nba_gm_data.action_choice'].project_choices(decision['frame'],decision['options'])
            self.assertEqual(current,old)
        self.assertNotIn('_recovery_geometry_basis',new);self.assertNotIn('_recovery_geometry_basis',s)

    def test_pruning_only_rejects_optimistically_unreachable_horizontal_envelope(self):
        self.assertTrue(recovery.horizontal_unreachable((0,0),(10,10),1,1,.5,.14,.6,3,4))
        self.assertFalse(recovery.horizontal_unreachable((0,0),(.5,0),0,0,.5,.14,.6,3,4))
        self.assertFalse(recovery.horizontal_unreachable((0,0),(.6,0),0,0,.14,.14,.6,3,4))

    def test_alternative_trajectory_controls_keep_exact_geometry(self):
        for changes in ({'downward_velocity_m_s':2},{'horizon_s':.45},{'horizon_s':.8},{'residual_velocity_fraction':.4}):
            d,s,c,x,draws=self.decision(coefficients=replace(recovery.RecoveryCoefficients(),**changes));f=d['frame'];o=d['options']['pop']
            for direction in range(6):
                for error in (.1,.6,.9,1.1,2,5):
                    a=recovery.recovery_geometry(f,'pop',o,error,direction)
                    with use_reference(self.modules):b=self.modules['nba_gm_data.pass_recovery'].recovery_geometry(f,'pop',o,error,direction)
                    self.assertEqual(a,b)

    def test_projection_never_samples_outcome_draws_and_releases_ownership(self):
        d,s,c,x,draws=self.decision()
        with patch('random.Random',side_effect=AssertionError('projection RNG')):r=project_choices(d['frame'],d['options'])
        self.assertNotIn('_recovery_geometry_basis',str(r));refs=[weakref.ref(x),weakref.ref(x.offense.creation)];del d,s,c,x,draws,r
        self.assertTrue(all(ref() is None for ref in refs))

    def test_plan_cache_reuses_only_identical_inputs_and_copies_outer_plan(self):
        from nba_gm_data import offense_response
        d,s,c,x,draws=self.decision();owner=d['frame']['coupled'];action=offense_response.ActionShotContext(shot_mode='catch',received_pass=True)
        with patch.object(offense_response,'plan_attack',wraps=offense_response.plan_attack) as build:
            evaluate=recovery.projection_plan_evaluator(owner)
            args=(owner,IDS['turner'],'perimeter',draws,'response_b',None,None)
            first=evaluate(*args,action_context=action,include_details=False);first['contest_defender_id']='private mutation'
            second=evaluate(*args,action_context=action,include_details=False)
            self.assertEqual(build.call_count,1);self.assertNotIn('contest_defender_id',second)
            evaluate(*args,action_context=replace(action,primary_arrival_s=.27),include_details=False)
            self.assertEqual(build.call_count,2)
            changed=list(draws);changed[18]=.8
            evaluate(owner,IDS['turner'],'perimeter',changed,'response_b',None,None,action_context=action,include_details=False)
            self.assertEqual(build.call_count,3)

    def test_plan_cache_rejects_other_coupled_snapshot(self):
        d,s,c,x,draws=self.decision();owner=d['frame']['coupled'];evaluate=recovery.projection_plan_evaluator(owner)
        with self.assertRaises(ValueError):evaluate(dict(owner),IDS['turner'],'perimeter',draws,'response_b',None,None,include_details=False)

    def test_plan_cache_does_not_key_future_delivery_or_catch_outcomes(self):
        from nba_gm_data import offense_response
        d,s,c,x,draws=self.decision();owner=d['frame']['coupled']
        with patch.object(offense_response,'plan_attack',wraps=offense_response.plan_attack) as build:
            evaluate=recovery.projection_plan_evaluator(owner);a=evaluate(owner,IDS['turner'],'perimeter',draws,'response_b',None,None,include_details=False)
            changed=list(draws)
            for key in (15,34,35,44):changed[key]=.999
            b=evaluate(owner,IDS['turner'],'perimeter',changed,'response_b',None,None,include_details=False)
            self.assertEqual(a,b);self.assertEqual(build.call_count,1)

    def test_coarse_experiment_is_explicit_and_scoped_to_predictor(self):
        from nba_gm_data import action_choice
        from experiments.recovery_projection_cost import approximation
        d,s,c,x,draws=self.decision();original=action_choice.project_candidate;spec=d['frame']['spec']
        with approximation.enabled():
            r=action_choice.project_choices(d['frame'],d['options']);self.assertEqual(r['decision_projection'],approximation.MODE)
            self.assertEqual(r['candidates']['pop']['integration_panels'],1)
            self.assertIs(d['frame']['spec'],spec);self.assertEqual(spec.recovery.integration_panels,4)
        self.assertIs(action_choice.project_candidate,original)

    def test_coarse_prediction_changes_no_selected_pass_physics_or_diagnostics(self):
        from experiments.recovery_projection_cost import approximation
        d,s,c,x,draws=self.decision(coverage='stay');draws[44]=.25
        a=resolve_candidate(d['frame'],'pop',d['options'],draws,{},delivery_error_override=.9)
        with approximation.enabled():b=resolve_candidate(d['frame'],'pop',d['options'],draws,{},delivery_error_override=.9)
        self.assertEqual(a,b);self.assertIn('recovery_geometry',b['record'])

    def test_coarse_prediction_uses_no_future_outcome_draws_or_rng(self):
        from experiments.recovery_projection_cost import approximation
        from nba_gm_data import action_choice
        d,s,c,x,draws=self.decision();changed=list(draws)
        for key in (15,34,35,44):changed[key]=.99
        other=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',changed,24)
        with approximation.enabled(),patch('random.Random',side_effect=AssertionError('coarse RNG')):
            self.assertEqual(action_choice.project_choices(d['frame'],d['options']),action_choice.project_choices(other['frame'],other['options']))

    def test_coarse_exception_restores_exact_policy(self):
        from experiments.recovery_projection_cost import approximation
        from nba_gm_data import action_choice
        original=action_choice.project_choices
        with self.assertRaises(RuntimeError):
            with approximation.enabled():raise RuntimeError('controlled test')
        self.assertIs(action_choice.project_choices,original)

    def test_coarse_actual_kernel_is_reproducible_and_accounted(self):
        from experiments.recovery_projection_cost import approximation
        from nba_gm_data import sim
        from nba_gm_data.schema import to_plain
        from nba_gm_data.interior_game import validate_accounting
        s,c,x=fixture(self.pool,possessions=4)
        with approximation.enabled():
            a=sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x)
            b=sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x)
        self.assertEqual(to_plain(a),to_plain(b));validate_accounting(a)


if __name__=='__main__':unittest.main()
