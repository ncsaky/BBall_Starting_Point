"""M16 scoped dispatch and explicitly versioned bearing behavior."""
from dataclasses import replace
import math
import unittest
from unittest.mock import patch
from nba_gm_data import action_choice,creation_passing,pass_recovery
from nba_gm_data.shot_geometry import ShotGeometry,stable_bearing,geometry_response,contest_at_angle
from nba_gm_data.interior_defense import ArrivalContext
from nba_gm_data.offense_response import StableBearingActionContext
from nba_gm_data.compact_recovery import CompactResolver
from experiments.compact_baseline_native_repair.fixtures import fixture,pool,converted,IDS
from experiments.compact_baseline_native_repair.providers import StableProvider,ArithmeticProvider
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.compact_recovery_evaluator.diagnostics import packet


class CompactBaselineRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s,cls.c,cls.x=fixture(pool(),action='slip');d=creation_passing.prepare_drive_decision(cls.s,IDS['curry'],'response_a','response_b',observed_draws(),24);cls.f=d['frame'];cls.o=d['options']
        cls.profile=cls.f['anchor'].profile

    def shot(self,x=0,y=0,dx=0,dy=0,angle=0):return ShotGeometry(x,y,300,dx,dy,angle)
    def test_new_optin_default_and_legacy_model(self):
        self.assertEqual(self.x.offense.creation.projection_backend,'compact_python_v1');self.assertEqual(self.x.offense.creation.bearing_policy,'legacy_bearing_v1')
    def test_backend_does_not_change_physical_revision(self):
        c=self.f['spec'];self.assertEqual(c.revision,replace(c,projection_backend='detailed_python_v1').revision);self.assertNotEqual(c.revision,replace(c,bearing_policy='stable_route_bearing_v2').revision)
    def test_provider_requires_named_scoped_and_correct_model(self):
        for kw in ({'geometry_provider':lambda *a:None},{'geometry_provider':ArithmeticProvider(),'projection_backend':'detailed_python_v1'},{'geometry_provider':StableProvider()}):
            with self.assertRaises(ValueError):replace(self.f['spec'],**kw)
    def test_signed_zero_undefined_is_angle_independent(self):
        for x in (0.,-0.):
            d,b=stable_bearing(self.shot(dx=x,dy=x));self.assertIsNone(d);self.assertEqual(b['source'],'rotation_mean_undefined')
        for angle in (-180,-90,0,45,90,180,360):
            r=geometry_response(self.profile,ArrivalContext(), 'rim',self.shot(angle=angle),bearing_policy='stable_route_bearing_v2');self.assertEqual(r['contest_alignment'],.35+.65/math.pi)
    def test_roundoff_perturbations_preserve_actual_route(self):
        for angle in range(0,360,45):
            r=math.radians(angle);d,b=stable_bearing(self.shot(dx=1e-16*math.cos(r),dy=1e-16*math.sin(r)),(0.,2.));self.assertEqual(d,math.pi/2);self.assertEqual(b['source'],'last_route_segment')
    def test_meaningful_separation_uses_current_not_route(self):
        d,b=stable_bearing(self.shot(dx=1e-7),(0.,2.));self.assertEqual(d,0.);self.assertEqual(b['source'],'current_separation')
    def test_coincident_route_is_undefined(self):
        d,b=stable_bearing(self.shot(),(0.,0.));self.assertIsNone(d);self.assertEqual(b['reference_separation_m'],0)
    def test_threshold_is_numerical_and_capped(self):
        _,b=stable_bearing(self.shot());self.assertEqual(b['tolerance_m'],32*math.ulp(1.));_,b=stable_bearing(self.shot(x=1e6,dx=1e6));self.assertEqual(b['tolerance_m'],1e-10)
    def test_rotation_and_translation_when_resolved(self):
        d,b=stable_bearing(self.shot(dx=1,dy=1));e,c=stable_bearing(self.shot(x=7,y=-3,dx=6,dy=-2));self.assertAlmostEqual(e-d,math.pi/2)
    def test_legacy_response_retains_zero_angle_and_no_v2_fields(self):
        r=geometry_response(self.profile,ArrivalContext(),'rim',self.shot());self.assertNotIn('bearing',r);self.assertEqual(r['contest_alignment'],1.)
    def test_corrected_context_validates_real_origin(self):
        with self.assertRaises(ValueError):StableBearingActionContext(defender_route_origin_m=(math.nan,0))
    def test_scoped_interleaving_never_changes_global_functions(self):
        ids=(action_choice.project_candidate,creation_passing.resolve_candidate)
        for bearing in ('legacy_bearing_v1','stable_route_bearing_v2'):
            a=action_choice.project_choices(converted(self.f,'detailed_python_v1',bearing=bearing),self.o);b=action_choice.project_choices(converted(self.f,bearing=bearing),self.o);self.assertEqual(a['scores'],b['scores']);self.assertEqual(a['effective_choice_probabilities'],b['effective_choice_probabilities'])
        self.assertEqual(ids,(action_choice.project_candidate,creation_passing.resolve_candidate))
    def test_node_packet_with_real_route_matches_corrected_detailed(self):
        f=converted(self.f,bearing='stable_route_bearing_v2');draws=observed_draws();draws[44]=.25
        for name in self.o:
            if name=='finish':continue
            for e in (.1,.9,2.):
                a=CompactResolver()(f,name,self.o,draws,{},delivery_error_override=e,include_details=False);b=creation_passing.resolve_candidate(f,name,self.o,draws,{},delivery_error_override=e,include_details=False);self.assertEqual(packet(a),packet(b))
    def test_selected_diagnostics_equal_within_model(self):
        for bearing in ('legacy_bearing_v1','stable_route_bearing_v2'):
            a=creation_passing.resolve_candidate(converted(self.f,'detailed_python_v1',bearing=bearing),'F04',self.o,observed_draws(),{},delivery_error_override=.9);b=creation_passing.resolve_candidate(converted(self.f,bearing=bearing),'F04',self.o,observed_draws(),{},delivery_error_override=.9);self.assertEqual(a,b)
    def test_missing_native_falls_back_to_same_model(self):
        from experiments.compact_baseline_native_repair import native_adapter
        f=converted(self.f,bearing='stable_route_bearing_v2');a=action_choice.project_choices(f,self.o)
        with patch.object(native_adapter,'library',return_value=None):b=action_choice.project_choices(converted(self.f,bearing='stable_route_bearing_v2',provider=StableProvider()),self.o)
        self.assertEqual(a['scores'],b['scores']);self.assertEqual(a['effective_choice_probabilities'],b['effective_choice_probabilities'])
    def test_conditioned_guard_requests_recompute_not_smoothing(self):
        r=geometry_response(self.profile,ArrivalContext(),'rim',self.shot(dx=1e-6),diagnostics=False,bearing_policy='stable_route_bearing_v2');a={'kind':'shot','elapsed_s':1.,'plan':{'response':r}}
        self.assertEqual(StableProvider().repair_reason({'remaining_s':24},a),'conditioned bearing vector')
    def test_compact_has_no_experiment_import_or_mock_dispatch(self):
        import inspect,nba_gm_data.compact_recovery as c,nba_gm_data.recovery_numeric_plan as p
        for module in (c,p):
            self.assertNotIn('from experiments',inspect.getsource(module));self.assertNotIn('unittest.mock',inspect.getsource(module))
    def test_provider_does_not_enter_selected_action(self):
        f=converted(self.f,bearing='stable_route_bearing_v2',provider=StableProvider())
        with patch.object(StableProvider,'__call__',side_effect=AssertionError('selected action must be detailed')):
            a=creation_passing.resolve_candidate(f,'F04',self.o,observed_draws(),{},delivery_error_override=.1)
        self.assertIn('details',a['plan'])
