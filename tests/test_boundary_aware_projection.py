"""Sealed proof-first experiment; reference fallback and physics stay explicit."""
from copy import deepcopy
from types import SimpleNamespace
import math
import gc
import unittest
from unittest.mock import patch
import weakref
from nba_gm_data import action_choice,creation_passing,pass_recovery,sim
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.schema import to_plain
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.expanded_cohort_performance.checks import traced
from experiments.pass_recovery.fixtures import fixture,pool,IDS
from experiments.boundary_aware_projection import predictor
from experiments.boundary_aware_projection.states import states


# Retired experimental engine (Track C). These tests compare against frozen reference snapshots in output/, which were
# never kept in git and were removed in the 2026-11-21 disk cleanup; they cannot be rebuilt exactly. Skip, with the
# reason, when a snapshot is missing rather than failing. Normal gameplay does not use this engine.
_RETIRED_SNAPSHOTS = ['mixed-pop-validation-2026-11-16', 'expanded-cohort-action-performance-2026-11-15']


def setUpModule():
    from pathlib import Path
    missing = [n for n in _RETIRED_SNAPSHOTS if not (Path(__file__).resolve().parents[1] / "output" / n).exists()]
    if missing:
        raise unittest.SkipTest("retired experimental engine: reference snapshot missing (deleted 2026-11-21, never in git): "
                                + ", ".join(missing))


class BoundaryAwareProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pool=pool()

    def decision(self,**kw):
        s,c,x=fixture(self.pool,action='pop',**kw);d=creation_passing.prepare_drive_decision(s,IDS['curry'],'response_a','response_b',observed_draws(),24);return d,s,c,x

    def same_numbers(self,a,b):
        self.assertEqual(a['effective_choice_probabilities'],b['effective_choice_probabilities']);self.assertEqual(a['scores'],b['scores'])
        for k,r in a['candidates'].items():
            self.assertEqual(r['expected_points'],b['candidates'][k]['expected_points']);self.assertEqual(r.get('branches'),b['candidates'][k].get('branches'))

    def test_reference_nodes_values_and_choices_are_preserved(self):
        d,s,c,x=self.decision();exact=action_choice.project_choices(d['frame'],d['options'])
        with predictor.enabled():method=action_choice.project_choices(d['frame'],d['options'])
        self.same_numbers(exact,method);self.assertEqual(method['decision_projection'],predictor.MODE)
        for r in method['candidates'].values():
            if 'boundary_solver' not in r:continue
            audit=r['boundary_solver'];self.assertLessEqual(audit.get('certificate_checks',0),128);self.assertLessEqual(audit['max_depth'],2)
            self.assertEqual(audit['reference_node_requests'],audit.get('full_resolver_calls',0)+audit.get('fast_terminal_nodes',0))

    def test_narrow_interior_opportunity_cannot_be_removed_by_endpoint_agreement(self):
        d,s,c,x=self.decision();f=d['frame'];o=dict(d['options']['pop']);basis=pass_recovery.geometry_basis(f,'pop',o)
        # Both ends are far from the receiver; the continuous interval crosses
        # its position. A whole-interval bound must refuse a loss certificate.
        basis={**basis,'receiver':(0,0),'vx':0,'vy':0,'half_span':.5,'axes':((1,0,0),)*6}
        f={**f,'_recovery_geometry_basis':basis};o={**o,'target':(-2,0),'delivery':{**o['delivery'],'error_scale_m':1}}
        self.assertFalse(predictor.IntervalResolver().certificate(f,o,0,0,1-math.exp(-4)))

    def test_uniform_horizontal_impossibility_has_a_certificate(self):
        d,s,c,x=self.decision();f=d['frame'];o=dict(d['options']['pop']);basis=pass_recovery.geometry_basis(f,'pop',o)
        basis={**basis,'receiver':(-3,0),'vx':0,'vy':0,'axes':((1,0,0),)*6}
        f={**f,'_recovery_geometry_basis':basis};o={**o,'target':(3,5),'delivery':{**o['delivery'],'error_scale_m':1}}
        self.assertTrue(predictor.IntervalResolver().certificate(f,o,0,1-math.exp(-.2),1-math.exp(-.3)))

    def test_exhausted_proof_budget_falls_back_without_losing_mass(self):
        d,s,c,x=self.decision();exact=action_choice.project_choices(d['frame'],d['options'])
        with patch.object(predictor,'MAX_CERTIFICATES',0),predictor.enabled():method=action_choice.project_choices(d['frame'],d['options'])
        self.same_numbers(exact,method)
        audits=[p['boundary_solver'] for p in method['candidates'].values() if 'boundary_solver' in p]
        self.assertTrue(any(p['fallback_reasons'].get('proof_budget',0)>0 for p in audits));self.assertTrue(all(p.get('certificate_checks',0)==0 for p in audits))

    def test_near_clock_terminal_node_uses_full_reference(self):
        d,s,c,x=self.decision();f=d['frame'];o=d['options']['pop'];b=pass_recovery.geometry_basis(f,'pop',o);error=20;draws=observed_draws();draws[44]=3.5/6
        t=f['elapsed'];t+=o.get('wait_s',0);t=t+o['delivery']['flight_s']+.05
        f={**f,'_recovery_geometry_basis':b,'remaining_s':t};solver=predictor.IntervalResolver();kw={'delivery_error_override':error,'include_details':False}
        a=solver(f,'pop',d['options'],draws,{},**kw);old=predictor.FULL_RESOLVER(f,'pop',d['options'],draws,{},**kw)
        self.assertEqual(a,old);self.assertEqual(solver.reasons['clock_boundary'],1)

    def test_prior_heldout_towns_clock_defender_branch_is_retained(self):
        meta,f,o=next(r for r in states('held_out') if r[0]['actor']=='towns' and r[0]['family']=='F03' and r[0]['context']=='clock_boundary')
        a=action_choice.project_choices(f,o)
        with predictor.enabled():b=action_choice.project_choices(f,o)
        self.same_numbers(a,b);self.assertGreater(b['candidates']['F04']['branches']['recovery_defended'],.005)

    def test_no_rng_or_future_outcome_draw_knowledge(self):
        d,s,c,x=self.decision();draws=observed_draws()
        for k in (15,34,35,44):draws[k]=.999
        other=creation_passing.prepare_drive_decision(s,IDS['curry'],'response_a','response_b',draws,24)
        with predictor.enabled(),patch('random.Random',side_effect=AssertionError('predictor RNG')):
            self.assertEqual(action_choice.project_choices(d['frame'],d['options']),action_choice.project_choices(other['frame'],other['options']))

    def test_selected_full_resolution_is_unchanged(self):
        d,s,c,x=self.decision(coverage='stay');draws=observed_draws();draws[44]=.25
        a=creation_passing.resolve_candidate(d['frame'],'pop',d['options'],draws,{},delivery_error_override=.9)
        with predictor.enabled():b=creation_passing.resolve_candidate(d['frame'],'pop',d['options'],draws,{},delivery_error_override=.9)
        self.assertEqual(a,b);self.assertIn('recovery_continuation',b)

    def test_exception_restores_hooks_and_projection_releases_owned_state(self):
        d,s,c,x=self.decision();original=creation_passing.resolve_candidate;original_choices=action_choice.project_choices;keys=set(d['frame']);before={k:v.to_dict() for k,v in self.pool['views'].items()}
        with self.assertRaises(RuntimeError):
            with predictor.enabled(),patch.object(predictor,'FULL_RESOLVER',side_effect=RuntimeError('controlled')):action_choice.project_choices(d['frame'],d['options'])
        self.assertIs(creation_passing.resolve_candidate,original);self.assertIs(action_choice.project_choices,original_choices)
        with predictor.enabled():r=action_choice.project_choices(d['frame'],d['options'])
        self.assertEqual(keys,set(d['frame']));self.assertEqual(before,{k:v.to_dict() for k,v in self.pool['views'].items()});refs=[weakref.ref(x),weakref.ref(x.offense.creation)];del d,s,c,x,r
        gc.collect()  # controlled mock exception can retain traceback cycles
        self.assertTrue(all(ref() is None for ref in refs))

    def test_actual_kernel_reproducibility_rng_and_accounting(self):
        s,c,x=fixture(self.pool,possessions=4);old,told=traced(c,x,17)
        with predictor.enabled():a,ta=traced(c,x,17);b,tb=traced(c,x,17)
        self.assertEqual(to_plain(a),to_plain(b));self.assertEqual(ta,tb);self.assertEqual(ta,told);validate_accounting(a)

    def test_nonrecovery_policy_full_result_rng_unchanged_even_inside_scope(self):
        s,c,x=fixture(self.pool,enabled=False,possessions=4);old,told=traced(c,x,17)
        with predictor.enabled():new,tnew=traced(c,x,17)
        self.assertEqual(to_plain(old),to_plain(new));self.assertEqual(told,tnew)


if __name__=='__main__':unittest.main()
