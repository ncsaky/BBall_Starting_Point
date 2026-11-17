"""Frozen evidence, causal stages and exact optimization (no target rankings)."""
from copy import deepcopy
from dataclasses import asdict,replace,fields
import json
import math
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data.experimental_inputs import InterpretedInputs,InputInterpretation,same_input_snapshot
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.shot_geometry import ShotGeometry
from nba_gm_data.interior_defense import ArrivalContext
from nba_gm_data.offense_response import compile_offense,free_throw_response
from experiments.expanded_cohort_performance.pool import load_pool,compile_audit,scenario,export,IDS
from experiments.expanded_cohort_performance.fixtures import fixture
from experiments.expanded_cohort_performance.probes import conditional,shooting,alternatives,LOB,SCREEN
from experiments.expanded_cohort_performance.verification import reference_modules
from experiments.expanded_cohort_performance.checks import benchmarks,kernel_parity,candidate_parity


class ExpandedCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pool=load_pool();cls.old=reference_modules()

    def test_packet_source_and_controls_preserved(self):
        e=export(self.pool);p=self.pool['packet']
        for k in ('merged_source_input_section','proposed_source_input_section'):self.assertEqual(e[k],p[k])
        self.assertEqual(sum(len(d['inputs']) for d in p['proposed_source_input_section']['players'].values()),564)
        self.assertEqual(len(e['operational_completions']),224)
        for pid,doc in p['proposed_source_input_section']['players'].items():
            for key,row in doc['inputs'].items():
                if row['status']!='unknown':self.assertEqual(e['operational_documents'][pid]['inputs'][key],row)

    def test_actual_role_compilation_dependencies_and_shared_ownership(self):
        a=compile_audit(self.pool)
        self.assertEqual(sum(len(r['profiles']) for r in a),20)
        self.assertEqual(sum(r['supported_required'] for r in a),68)
        self.assertEqual(sum(r['control_required'] for r in a),224)
        for r in a:
            self.assertFalse(r['new_required_ids']);self.assertFalse(r['declared_unused_ids'])
            self.assertTrue(all(v['same_authoritative_view'] for v in r['profiles'].values()))

    def test_control_overlay_refuses_evidence_and_wrong_ranges(self):
        with self.assertRaises(ValueError):scenario(self.pool,'bad',{'jokic':{'S14':40}})
        with self.assertRaises(ValueError):scenario(self.pool,'bad',{'turner':{'S36':51}},kind='source_range')
        with self.assertRaises(ValueError):scenario(self.pool,'bad',{'curry':{'S17':40}},kind='source_range')
        with self.assertRaises(ValueError):scenario(self.pool,'bad',{'jokic':{'S07':80}},kind='source_range')

    def test_private_alternatives_preserve_source_and_units(self):
        before=export(self.pool)
        for p,_ in alternatives(self.pool):
            self.assertEqual(p['packet'],self.pool['packet'])
            for override in p['overrides']:self.assertTrue(override['source_packet_unchanged'])
        self.assertEqual(before,export(self.pool))
        p=scenario(self.pool,'capacity',{'white':{'P08':.35,'P09':.55}})
        prof=compile_offense(p['views'][IDS['white']])
        self.assertAlmostEqual(prof.strength,.35);self.assertAlmostEqual(prof.balance,.55)

    def test_ft_probability_is_not_an_execution_curve(self):
        for alias in ('brunson','jokic','turner','barnes'):
            v=self.pool['views'][IDS[alias]];grade=v.to_dict()['inputs']['S07']['value']['grade']
            self.assertAlmostEqual(free_throw_response(compile_offense(v)),grade/100)

    def test_unknown_or_missing_roles_are_not_silently_filled(self):
        with self.assertRaisesRegex(ValueError,'screen role'):fixture(self.pool,partner='turner',other='jokic',screen='stay')
        state,_,_=fixture(self.pool,**SCREEN)
        self.assertIn('pop',state['audit_context']['missing_mechanisms'])
        for alias,key in [('curry','S26'),('jokic','F08.recognition')]:
            audit=next(r for r in compile_audit(self.pool) if r['player_id']==IDS[alias])
            self.assertNotIn(key,audit['actual_required_ids'])

    def test_exact_scalar_validators_match_frozen_valid_and_invalid_values(self):
        for current,old,base in [(ShotGeometry,self.old['nba_gm_data.shot_geometry'].ShotGeometry,dict(shot_x_m=.8,shot_y_m=1.5,release_height_cm=310)),
                                 (ArrivalContext,self.old['nba_gm_data.interior_defense'].ArrivalContext,{})]:
            def result(cls,kwargs):
                try:return ('valid',asdict(cls(**kwargs)))
                except Exception as exc:return (type(exc).__name__,str(exc))
            self.assertEqual(result(current,base),result(old,base))
            for f in fields(current):
                if f.name=='coefficients':continue
                for value in (None,True,'bad',float('nan'),float('inf'),-1,0,1,2):
                    kw={**base,f.name:value}
                    with self.subTest(cls=current.__name__,field=f.name,value=value):self.assertEqual(result(current,kw),result(old,kw))

    def test_identical_immutable_snapshot_skips_only_redundant_decoding(self):
        v=self.pool['views'][IDS['curry']]
        with patch.object(InterpretedInputs,'to_dict',side_effect=AssertionError('redundant decode')):self.assertTrue(same_input_snapshot(v,v))
        with patch.object(PlayerInputs,'to_dict',side_effect=AssertionError('redundant raw decode')):self.assertTrue(same_input_snapshot(v.source,v.source))
        self.assertTrue(same_input_snapshot(v,InterpretedInputs(PlayerInputs(v.to_dict()),v.contract)))
        self.assertFalse(same_input_snapshot(v,InterpretedInputs(v.source,replace(v.contract,research_gain=.9))))
        p=scenario(self.pool,'security',{'curry':{'S17':40}})
        self.assertFalse(same_input_snapshot(v,p['views'][IDS['curry']]))
        self.assertFalse(same_input_snapshot(v,v.source))

    def test_conditional_projection_is_normalized_and_not_mutable_input(self):
        s,_,_=fixture(self.pool,**SCREEN);before={k:v.to_dict() for k,v in self.pool['views'].items()}
        x=conditional(s);p=x['projection']
        self.assertAlmostEqual(sum(p['effective_choice_probabilities'].values()),1)
        for name,c in p['candidates'].items():
            if name=='reset':continue
            self.assertAlmostEqual(sum(c['branches'].values()),1)
        x['projection']['scores']['finish']=999
        self.assertNotEqual(conditional(s)['projection']['scores']['finish'],999)
        self.assertEqual(before,{k:v.to_dict() for k,v in self.pool['views'].items()})
        self.assertNotIn('_contest_basis',json.dumps(conditional(s)))

    def test_lob_read_and_execution_ranges_remain_separate_stages(self):
        rows=[]
        for key in ('F04.recognition','F04.execution'):
            pair=[]
            for grade in (86,98):
                p=scenario(self.pool,'lob',{'jokic':{key:grade}},kind='source_range');s,_,_=fixture(p,**LOB)
                pair.append(conditional(s)['projection']['candidates']['F04'])
            rows.append(pair)
        self.assertEqual(rows[0][0]['branches'],rows[0][1]['branches'])
        self.assertGreater(rows[1][0]['branches']['inaccurate_delivery'],rows[1][1]['branches']['inaccurate_delivery'])

    def test_late_unavailable_help_has_no_guaranteed_contest(self):
        s,_,_=fixture(self.pool,help_available=0);d=conditional(s)
        self.assertFalse(d['record']['anchor_available_for_action'])
        s,_,_=fixture(self.pool,start=(10,10));self.assertFalse(conditional(s)['record']['help']['timely'])

    def test_all_expanded_candidate_probabilities_weights_and_records_equal_reference(self):
        self.assertEqual(len(candidate_parity(self.pool,self.old)),16)

    def test_full_result_and_rng_equal_in_all_three_benchmarks(self):
        self.assertEqual(len(kernel_parity(benchmarks(self.pool),self.old)),12)

    def test_default_off_and_prior_experimental_paths_match_reference(self):
        label,c,x=benchmarks(self.pool)[0]
        legacy=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,choice_policy='legacy_scores_v1',help_response_policy='legacy_timely_v1')))
        off=replace(x,offense=replace(x.offense,creation=None))
        defense=replace(x,offense=None)
        self.assertEqual(len(kernel_parity([('ordinary',c,None),('legacy_screen',c,legacy),('offense_only',c,off),('interior_only',c,defense)],self.old)),16)

    def test_local_config_state_and_results_release(self):
        s,c,x=fixture(self.pool,**SCREEN);d=conditional(s)
        refs=[weakref.ref(x),weakref.ref(x.offense),weakref.ref(x.offense.creation)]
        del s,c,x,d
        self.assertTrue(all(r() is None for r in refs))


if __name__=='__main__':unittest.main()
