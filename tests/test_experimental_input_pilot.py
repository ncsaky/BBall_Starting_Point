"""Common interpretation semantics, ownership and unchanged historical paths."""
from copy import deepcopy
from dataclasses import FrozenInstanceError,asdict,replace
import json
import unittest
import weakref
from unittest.mock import patch

from nba_gm_data import sim
from nba_gm_data.experimental_inputs import (InputInterpretation,InterpretedInputs,common_reader,same_input_snapshot,FT_PROXY,RESEARCH_TECHNIQUE,CAPACITY_SCALE)
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.offense_response import compile_offense
from nba_gm_data.creation_passing import compile_interaction,prepare_creation
from nba_gm_data.interior_defense import compile_profile,Coefficients
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.screen_navigation import compile_screen
from nba_gm_data.schema import to_plain
from experiments.player_input_pilot.pilot import build_pilot,variant,export_layer,named_config,prepared,IDS,ROLES,packet,READINESS
from experiments.player_input_pilot.verification import reference_modules,reference_config,use_reference,pre_optimization_module,pre_optimization_config,traced_game
from experiments.screen_navigation.fixtures import screen_fixture


def view(p,alias):return p['views'][IDS[alias]]


class CommonInterpretationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pilot=build_pilot()

    def changed(self,alias,key,mutate,contract=None):
        old=view(self.pilot,alias);d=old.to_dict();mutate(d['inputs'][key]);return InterpretedInputs(PlayerInputs(d),contract or old.contract)

    def test_all_prior_contract_rejections_are_reproduced_then_resolved_explicitly(self):
        ready,_=packet(READINESS)
        for alias in ('white','castle','zubac','gobert'):
            raw=PlayerInputs(ready['operational_input_section']['players'][IDS[alias]])
            with self.assertRaises(ValueError):compile_screen(raw,roles=ROLES[alias])
            result=compile_screen(view(self.pilot,alias),roles=ROLES[alias]);self.assertEqual(result.player_id,IDS[alias])
        state=prepared(self.pilot)
        for alias in ('zubac','gobert'):
            pid=IDS[alias];s=state['screens']['profiles'][pid];i=state['screens']['interior_profiles'][pid]
            self.assertIs(s.inputs,i.inputs);self.assertIs(i.inputs,view(self.pilot,alias))
            self.assertEqual(s.strength,i.strength_capacity);self.assertEqual(s.balance,i.balance_capacity)
            self.assertTrue(i.input_contract.startswith('experimental_input_interpretation'))

    def test_response_mapping_is_declared_and_raw_grade_labels_survive(self):
        w=view(self.pilot,'castle');raw=w.to_dict();baseline=compile_interaction(w)
        other=InterpretedInputs(w.source,replace(w.contract,research_gain=.85))
        changed=compile_interaction(other)
        grade=raw['inputs']['S33']['value']['grade']/100
        self.assertAlmostEqual(changed.skill('S33'),.65+.85*(grade-.65))
        self.assertNotEqual(baseline.revision,changed.revision);self.assertEqual(raw,other.to_dict())
        self.assertEqual(raw['inputs']['S33']['value']['scale'],RESEARCH_TECHNIQUE)

    def test_ft_proxy_is_probability_and_not_native_skill_curve_or_gain(self):
        w=view(self.pilot,'castle');a=compile_offense(w)
        self.assertAlmostEqual(a.ft_probability,.734)
        self.assertNotAlmostEqual(a.ft_probability,.45+.5*.734)
        self.assertEqual(a.ft_probability,compile_offense(InterpretedInputs(w.source,replace(w.contract,research_gain=1.2))).ft_probability)
        bad=self.changed('castle','S07',lambda row:row['value'].update(scale=RESEARCH_TECHNIQUE))
        with self.assertRaisesRegex(ValueError,'FT'):compile_offense(bad)
        from experiments.offense_interior.fixtures import offensive_document
        native=InterpretedInputs(PlayerInputs(offensive_document('native',free_throw=75)),InputInterpretation())
        self.assertAlmostEqual(compile_offense(native).ft_probability,.825)

    def test_reported_cm_kg_aliases_do_not_convert_twice(self):
        w=view(self.pilot,'luka');r=common_reader(w);d=w.to_dict()
        self.assertEqual(r.measurement('P01'),d['inputs']['P01']['value']['measurements'][0]['value'])
        self.assertEqual(r.measurement('P04'),d['inputs']['P04']['value']['measurements'][0]['value'])
        self.assertAlmostEqual(r.measurement('P01'),203.2)
        self.assertAlmostEqual(r.measurement('P04'),104.326245)
        for alias in ('castle','caruso','davion','ajay'):self.assertGreater(common_reader(view(self.pilot,alias)).measurement('P01'),100)

    def test_matching_aliases_count_once_and_conflicts_are_rejected(self):
        w=view(self.pilot,'luka');r=common_reader(w);self.assertEqual(len(w.to_dict()['inputs']['P03']['value']['measurements']),2)
        self.assertEqual(r.measurement('P03'),277.01)
        bad=self.changed('luka','P03',lambda row:row['value']['measurements'][1].update(value=280))
        with self.assertRaisesRegex(ValueError,'conflicting'):compile_offense(bad)
        bad=self.changed('luka','P05',lambda row:row['value']['measurements'][1].update(value=4))
        with self.assertRaisesRegex(ValueError,'conflicting'):compile_interaction(bad)

    def test_units_protocols_unknowns_and_observed_synthetic_controls_are_strict(self):
        mutations=[('P05',lambda r:r['value']['measurements'][0].update(protocol='unverified protocol')),
                   ('P01',lambda r:r['value']['measurements'][0].update(unit='inches')),
                   ('P05',lambda r:r.update(status='observed'))]
        for key,mutate in mutations:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):compile_interaction(self.changed('luka',key,mutate)) if key=='P05' else compile_screen(self.changed('zubac',key,mutate),roles=('screener',))
        d=view(self.pilot,'luka').to_dict();d['inputs']['P05']['value']={'measurements':[],'display_grade':{'grade':80,'scale':'descriptor_only'}}
        with self.assertRaisesRegex(ValueError,'dimensional'):compile_interaction(InterpretedInputs(PlayerInputs(d),self.pilot['contract']))
        d=view(self.pilot,'luka').to_dict();d['inputs']['S17']=deepcopy(self.pilot['source_documents'][IDS['luka']]['inputs']['S17'])
        with self.assertRaises(ValueError):compile_interaction(InterpretedInputs(PlayerInputs(d),self.pilot['contract']))

    def test_capacity_is_shared_without_inventing_measured_values(self):
        w=view(self.pilot,'zubac');s=compile_screen(w,roles=('screener','coverage'));o=compile_offense(w);i=compile_profile(w)
        self.assertEqual((o.strength,s.strength,i.strength_capacity),(.5,.5,.5))
        self.assertEqual((o.balance,s.balance,i.balance_capacity),(2/3,2/3,2/3))
        other=InterpretedInputs(w.source,replace(w.contract,force_reference_n=1600,balance_reference_s=.5))
        self.assertEqual(compile_offense(other).strength,compile_profile(other).strength_capacity)
        self.assertEqual(compile_screen(other,roles=('screener',)).balance,compile_profile(other).balance_capacity)
        with self.assertRaisesRegex(ValueError,'capacity references'):compile_profile(w,replace(Coefficients(),synthetic_force_reference_n=1600))
        bad=self.changed('zubac','P08',lambda r:r['value'].update(display_grade={'grade':80,'scale':CAPACITY_SCALE}))
        with self.assertRaisesRegex(ValueError,'disagree'):compile_screen(bad,roles=('screener',))

    def test_nonzero_pop_requires_explicit_supported_action_policy(self):
        w=view(self.pilot,'zubac');reject=InterpretedInputs(w.source,replace(w.contract,screen_action_policy='reject_pop'))
        with self.assertRaisesRegex(ValueError,'pop'):compile_screen(reject,roles=('screener',))
        r=common_reader(w);mix=r.distribution('T11')
        self.assertAlmostEqual(mix['roll'],.4/.9);self.assertAlmostEqual(sum(mix.values()),1)
        self.assertEqual(r.audit['T11']['excluded_pop_mass'],.1)
        self.assertEqual(w.to_dict()['inputs']['T11']['value']['rows'][0]['probabilities']['pop'],.1)
        all_pop=self.changed('zubac','T11',lambda r:r['value']['rows'][0].update(probabilities={'screen':0,'roll':0,'pop':1,'slip':0}))
        with self.assertRaisesRegex(ValueError,'no supported'):compile_screen(all_pop,roles=('screener',))

    def test_location_split_and_legacy_arguments_are_explicit(self):
        w=view(self.pilot,'luka');a=compile_offense(w);b=compile_offense(InterpretedInputs(w.source,replace(w.contract,two_point_rim_fraction=.4)))
        self.assertEqual(a.locations[2],b.locations[2]);self.assertGreater(a.locations[0],b.locations[0]);self.assertNotEqual(a.revision,b.revision)
        for fn in (compile_offense,compile_interaction,compile_profile):
            with self.assertRaises(ValueError):fn(w,research_scenario=True)
        with self.assertRaises(ValueError):compile_offense(w,two_point_rim_fraction=.7)

    def test_roles_leave_unused_unknown_inputs_unknown(self):
        w=view(self.pilot,'davion');self.assertEqual(w.to_dict()['inputs']['S27']['status'],'unknown')
        nav=compile_screen(w,roles=('navigator',));self.assertIsNone(nav.screen);self.assertEqual(nav.preferences,())
        with self.assertRaises(ValueError):compile_screen(w,roles=('screener',))
        self.assertIsNone(compile_interaction(view(self.pilot,'luka')).skill('S42'))

    def test_source_rows_and_completion_ledger_preserve_all_origins(self):
        p=self.pilot;layer=export_layer(p);validate_input_section(layer['source_section']);validate_input_section(layer['pilot_section'])
        self.assertEqual(len(p['ledger']),319);self.assertEqual(sum(r['source_status']=='unknown' for r in p['ledger']),241)
        self.assertTrue(all(r['origin'] and r['interpretation'] for r in p['ledger']))
        for pid,doc in p['source_documents'].items():
            self.assertEqual(len(doc['inputs']),94)
            for key,row in doc['inputs'].items():
                if row['status']!='unknown':self.assertEqual(row,p['documents'][pid]['inputs'][key])
        self.assertEqual(p['source_documents'][IDS['gobert']]['inputs']['S27']['status'],'unknown')
        self.assertEqual(p['documents'][IDS['gobert']]['inputs']['S27']['value']['grade'],65)

    def test_mixed_interpretations_or_raw_and_view_snapshots_are_rejected(self):
        self.assertFalse(same_input_snapshot(view(self.pilot,'luka'),view(self.pilot,'luka').source))
        c,x=named_config(self.pilot);changed=InterpretedInputs(view(self.pilot,'luka').source,replace(self.pilot['contract'],research_gain=.9))
        profiles=tuple(compile_interaction(changed) if p.player_id==IDS['luka'] else p for p in x.offense.creation.profiles)
        y=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,profiles=profiles)))
        with self.assertRaisesRegex(ValueError,'interpretation'):sim.sim_game_with_context(c,'pilot_action_fixture',seed=17,interior_experiment=y)
        spec=x.offense.creation.screens;changed=InterpretedInputs(view(self.pilot,'white').source,replace(self.pilot['contract'],force_reference_n=1100))
        profiles=tuple(compile_screen(changed,roles=p.roles) if p.player_id==IDS['white'] else p for p in spec.profiles)
        y=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=replace(spec,profiles=profiles))))
        with self.assertRaisesRegex(ValueError,'interpretation'):sim.sim_game_with_context(c,'pilot_action_fixture',seed=17,interior_experiment=y)

    def test_ownership_mutation_json_reconstruction_and_release(self):
        p=build_pilot();w=view(p,'luka');raw=w.to_dict();a=compile_interaction(w)
        raw['inputs']['S33']['value']['grade']=0;self.assertEqual(a,compile_interaction(w))
        with self.assertRaises(FrozenInstanceError):w.contract.research_gain=2
        layer=export_layer(p);layer['pilot_section']['players'][IDS['luka']]['inputs']['S33']['value']['grade']=0
        self.assertNotEqual(layer['pilot_section']['players'][IDS['luka']],w.to_dict())
        p['documents'][IDS['luka']]['inputs']['S33']['value']['grade']=0
        successor=variant(p,{'luka':{'S17':90}},name='explicit_override_only')
        self.assertEqual(view(successor,'luka').to_dict()['inputs']['S33'],w.to_dict()['inputs']['S33'])
        restored=InterpretedInputs(PlayerInputs(json.loads(json.dumps(w.to_dict()))),InputInterpretation(**json.loads(json.dumps(asdict(w.contract)))))
        self.assertEqual(a,compile_interaction(restored))
        ref=weakref.ref(w);source=weakref.ref(w.source);del p,w,a,restored;self.assertIsNone(ref());self.assertIsNone(source())

    def test_counterfactual_overrides_are_separate_and_revisioned(self):
        p=variant(self.pilot,{'luka':{'S17':90}},name='security_prior_90')
        self.assertEqual(self.pilot['source_documents'][IDS['luka']]['inputs']['S17']['status'],'unknown')
        self.assertEqual(p['overrides'][0]['origin'],'uncertain_prior_alternative')
        self.assertNotEqual(view(p,'luka').revision,view(self.pilot,'luka').revision)
        self.assertEqual(p['source_documents'],self.pilot['source_documents'])


class PilotBoundaryTests(unittest.TestCase):
    def test_action_probe_sampling_is_seeded_and_intervals_are_conditional(self):
        from experiments.player_input_pilot.probes import run_scenario,scenarios
        p=build_pilot();row=scenarios(p)[0]
        a=run_scenario(row,pass_n=64,screen_n=16);b=run_scenario(row,pass_n=64,screen_n=16)
        self.assertEqual(a,b)
        for family,data in a['passing']['families'].items():
            for actor in data['actors'].values():
                events=actor['events'];self.assertEqual(events['missed_read']+events['noticed'],64)
                self.assertEqual(events['accurate_delivery']+events['inaccurate_delivery'],events['noticed'])
                self.assertEqual(events['caught']+events['failed_catch'],events['accurate_delivery'])
                self.assertLessEqual(actor['caught_wilson95'][0],actor['caught_rate']);self.assertGreaterEqual(actor['caught_wilson95'][1],actor['caught_rate'])

    def test_review_layer_and_geometry_controls_remain_explicit_alternatives(self):
        from experiments.player_input_pilot.pilot import review_alternative
        p=build_pilot();r=review_alternative(p,historical_reach=297.18)
        self.assertEqual(p['source_documents'],r['source_documents']);self.assertEqual(p['documents'][IDS['gobert']]['inputs']['S27']['value']['grade'],65)
        self.assertEqual(common_reader(view(r,'gobert')).measurement('P03'),297.18)
        self.assertEqual(len(r['overrides']),4);self.assertTrue(all(x['evidence_update'] for x in r['overrides']))
        changed=variant(r,{'gobert':{'S28':85}},name='proposed_read_alternative')
        self.assertEqual(len(changed['overrides']),5);self.assertEqual(len(export_layer(changed)['overrides']),5)
        body=variant(p,{'zubac':{'P01':200}},name='matched_body_control')
        self.assertIn('not a reported athlete',view(body,'zubac').to_dict()['inputs']['P01']['value']['measurements'][0]['protocol'])

    def test_exact_local_validation_reuse_preserves_full_results_and_rng(self):
        before=pre_optimization_module()
        for name in ('native','interpreted'):
            c,x=screen_fixture(possessions=8) if name=='native' else named_config(build_pilot())
            prior=pre_optimization_config(x,before)
            for seed in (17,29):
                a,ta=traced_game(c,x,seed);b,tb=traced_game(c,prior,seed,pre_optimization=before)
                self.assertEqual(to_plain(a),to_plain(b));self.assertEqual(ta,tb)

    def test_every_immutable_actor_is_validated_once_and_roles_still_checked_per_call(self):
        import nba_gm_data.screen_navigation as screen
        from experiments.creation_passing.fixtures import action_state
        c,x=screen_fixture(possessions=8)
        with patch.object(screen,'compile_screen',wraps=screen.compile_screen) as calls:action_state(x)
        self.assertEqual(calls.call_count,10)
        spec=x.offense.creation.screens
        bad=replace(spec,profiles=tuple(replace(p,roles=('coverage',)) if p.player_id=='team_a_0' else p for p in spec.profiles))
        y=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=bad)))
        with self.assertRaises(ValueError):action_state(y)

    def test_small_counterfactual_kernel_checks_accounting_not_game_forecasts(self):
        p=build_pilot();c,x=named_config(p)
        before=deepcopy(c['canonical']);r=sim.sim_game_with_context(c,'pilot_action_fixture',seed=17,interior_experiment=x);validate_accounting(r)
        self.assertTrue(any(e.get('creation_chain',{}).get('screen_action',{}).get('kind')=='screen' for t in r.team_lines for e in t['interior_experiment']['offense_attack_ledger']))
        self.assertEqual({k:v for k,v in before.items() if not k.startswith('_')},{k:v for k,v in c['canonical'].items() if not k.startswith('_')})

    def test_complete_historical_paths_use_authenticated_frozen_compilers(self):
        modules,old_kernel,old_sim=reference_modules()
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                c,x=screen_fixture(possessions=8)
                prior_creation=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=None)))
                configs=(None,replace(x,offense=None),replace(x,offense=replace(x.offense,creation=None)),prior_creation,x)
                for config in configs:
                    now=sim.sim_game_with_context(c,'interior_fixture',mode,seed,interior_experiment=config)
                    with use_reference(modules):
                        if config is None:before=old_sim.sim_game_with_context(c,'interior_fixture',mode,seed)
                        else:
                            a,b=c['canonical']['teams'];g=c['schedule'][0];pools=[sim.game_player_pool(c,'interior_fixture',t,mode,game_date=g['gameDate']) for t in (a,b)]
                            before=old_kernel.simulate_interior_game(c['canonical'],g,a,b,*pools,mode,seed,reference_config(config,modules))
                    self.assertEqual(to_plain(now),to_plain(before))


if __name__=='__main__':unittest.main()
