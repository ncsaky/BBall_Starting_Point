"""Evidence/adapter diagnosis and natural mixed-possession verification."""
import ast
from collections import Counter
from copy import deepcopy
from dataclasses import asdict,replace
import inspect
import json
import random
import unittest
import weakref

from nba_gm_data.experimental_inputs import InterpretedInputs,InputReader
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.offense_response import compile_offense
from nba_gm_data.creation_passing import compile_interaction,prepare_drive_decision,resolve_drive
from nba_gm_data.screen_navigation import compile_screen
from nba_gm_data.interior_defense import FORMULA_VERSION
from nba_gm_data.schema import to_plain
from nba_gm_data import sim
from experiments.mixed_pop_validation.fixtures import build_pool,final_research_pool,fixture,overlay,IDS,ACTORS,REQUIRED
from experiments.mixed_pop_validation.diagnosis import reproduce,REFERENCE,plain
from experiments.mixed_pop_validation.sampling import accumulator,one_possession,run_case,finish,wilson
from experiments.mixed_pop_validation.verification import reference_modules,reference_config,use_reference
from experiments.pick_and_pop.fixtures import pool as old_pool,fixture as old_fixture
from experiments.expanded_cohort_performance.checks import traced,benchmarks


class MixedPopValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pool=build_pool();cls.old=reference_modules()

    def test_original_ten_attempts_are_five_replayed_domains_not_ten_independent_trials(self):
        d=reproduce();self.assertEqual(len(d['attempts']),10);self.assertEqual(len({r['rng_domain'] for r in d['attempts']}),5)
        self.assertTrue(all(r['full_accepted_result_equal'] for r in d['kernels']))
        for row in d['summaries']:
            self.assertEqual(row['observed_outcomes'],{'inaccurate_delivery':4,'failed_catch':1})
            self.assertTrue(0<row['probability_no_shot_stage_given_selected_states']<1)

    def test_source_rows_and94_fields_remain_exact_for_all_four_actors(self):
        self.assertEqual(len(self.pool['completion_ledger']),173)
        for actor in ACTORS[:-1]:
            pid=IDS[actor];src=self.pool['source_documents'][pid];doc=self.pool['views'][pid].to_dict();self.assertEqual(len(doc['inputs']),94)
            for key,row in src['inputs'].items():
                if row['status']!='unknown':self.assertEqual(doc['inputs'][key],row)
                elif key not in REQUIRED:self.assertEqual(doc['inputs'][key],row)
        self.assertTrue(all(r['source_record']['status']=='unknown' for r in self.pool['completion_ledger']))

    def test_all_five_conditions_compile_and_share_one_authoritative_view(self):
        for actor in ACTORS:
            s,c,x=fixture(self.pool,actor);v=self.pool['views'][IDS[actor]]
            self.assertIs(s['profiles'][IDS[actor]].inputs,v);self.assertIs(s['coupled']['profiles'][IDS[actor]].inputs,v);self.assertIs(s['screens']['profiles'][IDS[actor]].inputs,v)
        self.assertEqual(len(REQUIRED),50)

    def test_exact_reported_protocol_correction_preserves_stored_cm_and_kg(self):
        for actor in ('towns','holmgren'):
            v=self.pool['views'][IDS[actor]];reader=InputReader(v)
            for key in ('P01','P02','P04'):
                raw=v.to_dict()['inputs'][key]['value']['measurements'][0]['value'];self.assertEqual(reader.measurement(key),raw)
            e=self.old['nba_gm_data.experimental_inputs'];old=e.InterpretedInputs(v.source,e.InputInterpretation(**asdict(v.contract)))
            with self.assertRaisesRegex(ValueError,'unsupported quantity/unit/protocol'):e.InputReader(old).measurement('P01')

    def test_alias_does_not_accept_other_units_or_undeclared_protocols(self):
        v=self.pool['views'][IDS['towns']]
        for field,value in [('protocol','trust me'),('unit','in')]:
            doc=v.to_dict();doc['inputs']['P01']['value']['measurements'][0][field]=value
            with self.assertRaises(ValueError):InputReader(InterpretedInputs(PlayerInputs(doc),v.contract)).measurement('P01')

    def test_hypothetical_reach_is_distinct_from_reported_measurement(self):
        for actor in ACTORS[:-1]:
            d=self.pool['views'][IDS[actor]].to_dict()['inputs'];h=d['P01']['value']['measurements'][0]['value'];span=d['P02']['value']['measurements'][0]['value']
            self.assertAlmostEqual(d['P03']['value']['measurements'][0]['value'],h+70+.5*(span-h))
            self.assertIn('not a reported athlete measurement',d['P03']['value']['measurements'][0]['protocol'])

    def test_control_sensitivity_cannot_overwrite_supported_grades(self):
        with self.assertRaises(ValueError):overlay(self.pool,'bad',{'jokic':{'S14':40}})
        with self.assertRaises(ValueError):overlay(self.pool,'bad',{'towns':{'S01':65}})
        with self.assertRaises(ValueError):overlay(self.pool,'bad',{'holmgren':{'S08':61}},kind='source_range')
        p=overlay(self.pool,'range',{'holmgren':{'S08':35}},kind='source_range');self.assertEqual(p['source_documents'],self.pool['source_documents'])
        self.assertEqual(self.pool['views'][IDS['holmgren']].to_dict()['inputs']['S08']['value']['grade'],47.5)

    def test_final_independent_research_fills_only_nine_unknowns_in_separate_views(self):
        p=final_research_pool(self.pool);self.assertEqual(len(p['research_updates']),9);self.assertEqual(len(p['completion_ledger']),164)
        for actor in ACTORS[:-1]:
            pid=IDS[actor];old=self.pool['source_documents'][pid];new=p['source_documents'][pid]
            for key,row in old['inputs'].items():
                if row['status']!='unknown':self.assertEqual(row,new['inputs'][key])
            s,c,x=fixture(p,actor);self.assertIs(s['profiles'][pid].inputs,p['views'][pid])
        self.assertEqual(self.pool['views'][IDS['jokic']].to_dict()['inputs']['S01']['value']['grade'],65)
        self.assertEqual(p['views'][IDS['jokic']].to_dict()['inputs']['S01']['value']['grade'],84)
        from nba_gm_data.interior_game import validate_accounting
        _,c,x=fixture(p,'jokic');a=sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x);b=sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x)
        self.assertEqual(to_plain(a),to_plain(b));validate_accounting(a)

    def test_inaccurate_delivery_semantics_is_hard_loss_not_reset(self):
        from experiments.action_choice_consistency.fixtures import observed_draws
        s,c,x=fixture(self.pool,action='pop');draws=observed_draws();draws[34]=.999999
        d=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',draws,24)
        from nba_gm_data.creation_passing import resolve_candidate
        a=resolve_candidate(d['frame'],'pop',d['options'],draws,{})
        self.assertEqual((a['kind'],a['outcome']),('turnover','inaccurate_delivery'));self.assertNotIn('plan',a)

    def test_offline_continuations_match_accepted_kernel_event_streams(self):
        s,c,x=old_fixture(old_pool());checked=0
        for seed in (17,29):
            saved=json.loads((REFERENCE/f'pop-accounting-original_controls-{seed}-replay-real-minutes.json').read_text())
            events=saved['team_lines'][0]['interior_experiment']['offense_attack_ledger'];groups={}
            for e in events:groups.setdefault(e['possession'],[]).append(e)
            def draws(seed,index,attempt):
                rng=random.Random(f'{seed}:expanded_fixture:replay-real-minutes:{FORMULA_VERSION}:response_a:{index}:{attempt}')
                return [rng.random() for _ in range(48)]
            for index,group in groups.items():
                if group[0]['creation_chain']['creator_id']!=IDS['curry']:continue
                acc=accumulator();points=one_possession(s,seed,index,acc,draw_source=draws)
                self.assertEqual(points,sum(e['points'] for e in group));self.assertEqual(acc['events'],Counter(e['outcome'] for e in group));self.assertEqual(acc['event_count'],len(group));checked+=1
        self.assertGreaterEqual(checked,4)

    def test_natural_mixed_sampling_is_deterministic_and_records_continuations(self):
        s,_,_=fixture(self.pool,'turner');a=run_case(s,adaptive=False,minimum_per_seed=32);b=run_case(s,adaptive=False,minimum_per_seed=32)
        a.pop('wall_s');b.pop('wall_s');self.assertEqual(a,b);self.assertEqual(a['n'],64)
        self.assertGreater(a['event_count'],a['n']);self.assertEqual(a['truncated'],0)
        self.assertEqual(sum(a['terminations'].values()),a['n']);self.assertEqual(sum(a['pop_events'].values()),a['stages']['pop_selected'])

    def test_reported_denominators_and_uncertainty_handle_zero_selections(self):
        self.assertEqual(wilson(0,0),[None,None]);self.assertGreater(wilson(0,5)[1],0)
        s,_,_=fixture(self.pool,'turner',coverage='stay',creator_start=(4.5,8))
        r=run_case(s,adaptive=False,minimum_per_seed=16);self.assertIsNone(r['pop_completion_rate']);self.assertEqual(r['n'],32)
        self.assertEqual(r['stages']['pop_selected'],0);self.assertEqual(r['stages']['pop_caught_and_shot_stage'],0)

    def test_synthetic_nonspacer_is_not_a_named_source_profile(self):
        v=self.pool['views'][IDS['nonspacing']];self.assertNotIn(v.player_id,self.pool['source_documents'])
        for row in v.to_dict()['inputs'].values():
            if row['status']!='unknown':self.assertEqual(row['evidence'][0]['source'],'synthetic_nonspacing_reference_2026_11_16')

    def test_input_ownership_and_local_graph_release(self):
        before={k:v.to_dict() for k,v in self.pool['views'].items()};s,c,x=fixture(self.pool)
        run_case(s,adaptive=False,minimum_per_seed=4);self.assertEqual(before,{k:v.to_dict() for k,v in self.pool['views'].items()})
        refs=[weakref.ref(x),weakref.ref(x.offense.creation),weakref.ref(x.offense.creation.screens)];del s,c,x
        self.assertTrue(all(r() is None for r in refs))

    def test_accepted_optimization_ast_and_all_other_runtime_modules_unchanged(self):
        from nba_gm_data import experimental_inputs
        old=ast.parse((REFERENCE/'experimental_inputs.py.reference').read_text());new=ast.parse(inspect.getsource(experimental_inputs))
        for name in ('same_input_snapshot','InterpretedInputs','InputReader'):
            self.assertEqual(ast.dump(next(n for n in old.body if getattr(n,'name',None)==name)),ast.dump(next(n for n in new.body if getattr(n,'name',None)==name)))

    def test_authentic_frozen_pop_path_keeps_complete_results_and_rng(self):
        s,c,x=old_fixture(old_pool());a,ta=traced(c,x,17)
        with use_reference(self.old):old=reference_config(x,self.old);b,tb=traced(c,old,17,simulator=self.old['nba_gm_data.sim'])
        self.assertEqual(to_plain(a),to_plain(b));self.assertEqual(ta,tb)


if __name__=='__main__':unittest.main()
