"""Introductory mechanism/accounting tests; no league calibration assertions."""
from copy import deepcopy
from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path
import unittest
import weakref
from unittest.mock import patch

from nba_gm_data import sim
from nba_gm_data.interior_defense import (
    Anchor, ArrivalContext, Coefficients, InteriorExperiment, compile_profile,
    interior_response, reference_report,
)
from nba_gm_data.interior_game import expected_environment, validate_accounting
from nba_gm_data.player_model import PlayerInputs, validate_input_section
from nba_gm_data.player_model_registry import definition_registry, validate_registry
from nba_gm_data.schema import to_plain
from experiments.interior_defense.fixtures import game_fixture, scenario_document, scenario_profile

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT/'docs/ratings-evidence-2026-10-29/INTERIOR_DEFENSE_EXPERIMENT_INPUTS_2026_11_13.json'
REFERENCE=ROOT/'output/interior-defense-experiment-2026-11-13/sim-reference.py'


def config(profile=None,context=ArrivalContext()):
    return InteriorExperiment((Anchor('team_a',profile or scenario_profile('team_a_4'),context),),('team_b',))


def result(context=None,experiment=None,seed=17):
    return sim.sim_game_with_context(context or game_fixture(),'interior_fixture',seed=seed,interior_experiment=experiment)


class InteriorMechanismTests(unittest.TestCase):
    def test_equal_tools_positioning_and_technique_are_distinct(self):
        low=interior_response(scenario_profile(positioning=25),ArrivalContext())
        high=interior_response(scenario_profile(positioning=90),ArrivalContext())
        self.assertGreater(high['contest_quality'],low['contest_quality'])
        self.assertLess(high['travel_s'],low['travel_s'])
        tech=interior_response(scenario_profile(technique=95),ArrivalContext())
        self.assertGreater(tech['block_probability'],high['block_probability']*.8)
        a=interior_response(scenario_profile(technique=25),ArrivalContext())
        b=interior_response(scenario_profile(technique=90),ArrivalContext())
        self.assertEqual(a['arrival_s'],b['arrival_s'])
        self.assertGreater(b['conversion_reduction'],a['conversion_reduction'])

    def test_equal_technique_reach_changes_coverage_without_height_stack(self):
        small=interior_response(scenario_profile(reach=235,jump=25),ArrivalContext())
        tall=interior_response(scenario_profile(reach=290,jump=25),ArrivalContext())
        self.assertGreater(tall['block_probability'],small['block_probability'])
        a=scenario_document();b=deepcopy(a)
        # Unused identity/geometry observations do not get added to standing reach.
        from experiments.interior_defense.fixtures import estimate
        b['inputs']['P01']=estimate({'measurements':[{'metric':'height','value':230,'unit':'cm','protocol':'test'}]})
        b['inputs']['P02']=estimate({'measurements':[{'metric':'span','value':250,'unit':'cm','protocol':'test'}]})
        ra=interior_response(compile_profile(PlayerInputs(a)),ArrivalContext())
        rb=interior_response(compile_profile(PlayerInputs(b)),ArrivalContext())
        for key in ('conversion_reduction','block_probability','avoidance_probability'):self.assertEqual(ra[key],rb[key])

    def test_good_recognition_cannot_rescue_late_physical_arrival(self):
        response=interior_response(scenario_profile(acceleration=2),ArrivalContext(distance_m=6,window_s=.5,recognition_delay_s=.02,poa_containment=0))
        for key in ('coverage_available','block_probability','conversion_reduction','avoidance_probability','foul_probability'):self.assertEqual(response[key],0)
        slow_read=interior_response(scenario_profile(acceleration=6),ArrivalContext(distance_m=.1,window_s=.5,recognition_delay_s=1,poa_containment=0))
        self.assertEqual(slow_read['coverage_available'],0)

    def test_choice_and_legal_execution_have_separate_consequences(self):
        ctx=ArrivalContext();aggressive=scenario_profile(legal=25,choices=(.9,.05,.05));careful=scenario_profile(legal=25,choices=(.1,.3,.6))
        a=interior_response(aggressive,ctx);b=interior_response(careful,ctx)
        self.assertGreater(a['block_probability'],b['block_probability']);self.assertGreater(a['foul_probability'],b['foul_probability'])
        legal=interior_response(scenario_profile(legal=95,choices=(.9,.05,.05)),ctx)
        self.assertEqual(legal['block_probability'],a['block_probability']);self.assertLess(legal['foul_probability'],a['foul_probability'])

    def test_unavailable_or_remote_defender_does_not_change_any_attempt(self):
        p=scenario_profile()
        for ctx in (ArrivalContext(anchor_available=0),ArrivalContext(distance_m=12,window_s=.2,poa_containment=0)):
            a=expected_environment(p,ctx);b=expected_environment(None,ctx)
            for key in ('expected_points_per_100_possessions','expected_blocks_per_100_possessions','expected_shooting_fouls_per_100_possessions','zone_shares'):self.assertEqual(a[key],b[key])
        response=interior_response(p,ArrivalContext(),zone='perimeter')
        self.assertEqual(response['block_probability'],0);self.assertEqual(response['conversion_reduction'],0)

    def test_context_interactions_are_explicit_sensitivities(self):
        p=scenario_profile()
        crowded=ArrivalContext(distance_m=.8,window_s=.9,spacing=0,poa_containment=0)
        spaced=replace(crowded,spacing=1)
        strong_poa=replace(spaced,poa_containment=1)
        self.assertGreater(interior_response(p,crowded)['coverage_available'],interior_response(p,spaced)['coverage_available'])
        self.assertGreater(interior_response(p,strong_poa)['coverage_available'],interior_response(p,spaced)['coverage_available'])
        rim=expected_environment(p,ArrivalContext(),rim_share=.6,three_share=.15)
        pullup=expected_environment(p,ArrivalContext(),rim_share=0,three_share=1)
        control=expected_environment(None,ArrivalContext(),rim_share=0,three_share=1)
        self.assertEqual(pullup['expected_points_per_100_possessions'],control['expected_points_per_100_possessions'])
        self.assertGreater(rim['expected_blocks_per_100_possessions'],pullup['expected_blocks_per_100_possessions'])

    def test_c36_is_only_a_readout_and_r18_is_partial(self):
        r=reference_report(scenario_profile());self.assertEqual(r['R18']['status'],'partial_not_a_role_grade')
        baseline=result(experiment=config())
        from nba_gm_data.interior_game import reference_report as original
        def misleading(*args,**kwargs):
            r=original(*args,**kwargs);r['C36']['conversion_points_prevented_per_100_rim_fga']=99999;return r
        with patch('nba_gm_data.interior_game.reference_report',side_effect=misleading):changed=result(experiment=config())
        self.assertEqual(baseline.player_lines,changed.player_lines)
        for a,b in zip(baseline.team_lines,changed.team_lines):self.assertEqual(a['interior_experiment']['offense_attack_ledger'],b['interior_experiment']['offense_attack_ledger'])

    def test_missing_inputs_units_protocols_and_scales_fail_explicitly(self):
        for mutate in (lambda d:d['inputs'].pop('S36'),lambda d:d['inputs']['P03']['value']['measurements'][0].update(unit='inches'),lambda d:d['inputs']['P05']['value']['measurements'][0].update(protocol='unknown provider test'),lambda d:d['inputs']['S37']['value'].update(scale='unknown_scale'),lambda d:d['inputs']['P08']['value'].pop('display_grade'),lambda d:d['inputs']['T16']['value']['rows'][0].update(condition='unknown_condition')):
            doc=scenario_document();mutate(doc)
            with self.assertRaises(ValueError):compile_profile(PlayerInputs(doc))
        with self.assertRaises(ValueError):ArrivalContext(window_s=float('nan'))
        with self.assertRaises(ValueError):ArrivalContext(anchor_available=2)
        with self.assertRaises(ValueError):Coefficients(max_block_probability=2)

    def test_research_scenarios_preserve_raw_documents_unknowns_and_provenance(self):
        packet=json.loads(PACKET.read_text());before=deepcopy(packet)
        validate_input_section(packet['player_input_section'])
        for scenario in packet['scenarios']:
            validate_input_section(scenario['input_section'])
            for doc in scenario['input_section']['players'].values():
                profile=compile_profile(PlayerInputs(doc),research_scenario=True)
                self.assertEqual(reference_report(profile)['raw_inputs'],doc)
        for doc in packet['player_input_section']['players'].values():
            with self.assertRaises(ValueError):compile_profile(PlayerInputs(doc),research_scenario=True)
            self.assertEqual(doc['inputs']['P03']['status'],'unknown')
        self.assertEqual(before,packet)
        validate_registry();r=definition_registry();self.assertEqual((len(r['inputs']),len(r['outputs'])),(94,59))

    def test_input_coefficient_and_context_revisions_are_snapshot_owned(self):
        doc=scenario_document();p=compile_profile(PlayerInputs(doc));before=reference_report(p)
        doc['inputs']['S37']['value']['grade']=5
        self.assertEqual(reference_report(p),before)
        changed=compile_profile(PlayerInputs(doc));self.assertNotEqual(changed.revision,p.revision)
        coef=compile_profile(p.inputs,replace(Coefficients(),max_avoidance=.2));self.assertNotEqual(coef.revision,p.revision)
        self.assertNotEqual(config(context=ArrivalContext(spacing=0)).revision,config(context=ArrivalContext(spacing=1)).revision)


class InteriorGameTests(unittest.TestCase):
    def test_points_shots_blocks_fouls_and_rebounds_are_linked_before_score(self):
        blocks=0
        for seed in (17,29,31,43):
            r=result(experiment=config(),seed=seed);validate_accounting(r)
            self.assertNotEqual(r.home_score,r.away_score)
            blocks+=sum(t['blocks'] for t in r.team_lines)
            for row in r.player_lines:
                self.assertEqual(row['points'],2*row['fgm']+row['fg3m']+row['ftm'])
                self.assertLessEqual(row['fg3m'],row['fgm']);self.assertLessEqual(row['fg3a'],row['fga'])
        self.assertGreater(blocks,0)

    def test_game_scoring_changes_and_default_mode_remains_off(self):
        control=InteriorExperiment((),('team_a','team_b'))
        a=result(experiment=control);b=result(experiment=config())
        self.assertNotEqual(a.player_lines,b.player_lines)
        self.assertNotEqual((a.home_score,a.away_score),(b.home_score,b.away_score))
        with patch('nba_gm_data.interior_game.simulate_interior_game',side_effect=AssertionError('must remain off')):
            normal=result();explicit=result(experiment=None)
        self.assertEqual(to_plain(normal),to_plain(explicit))

    def test_frozen_pre_edit_default_path_matches_complete_results(self):
        spec=importlib.util.spec_from_file_location('nba_gm_data._interior_pre_edit_sim',REFERENCE)
        reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                a=sim.sim_game_with_context(game_fixture(),'interior_fixture',mode,seed)
                b=reference.sim_game_with_context(game_fixture(),'interior_fixture',mode,seed)
                self.assertEqual(to_plain(a),to_plain(b))

    def test_legacy_rim_and_defensive_composites_do_not_leak_into_experimental_scores(self):
        a=game_fixture();b=game_fixture()
        for row in b['canonical']['traits']:
            if row['trait_key']=='rim_deterrence':row['value']=1
        self.assertEqual(to_plain(result(a,config())),to_plain(result(b,config())))

    def test_health_absence_and_ownership_changes_are_fresh(self):
        c=game_fixture();sim.game_player_pool(c,'interior_fixture',c['canonical']['teams'][0],'replay-real-minutes',game_date='2026-11-13')
        pool=c['sim_cache']['player_pools'][('interior_fixture','team_a','replay-real-minutes','2026-11-13')]
        for item in pool:
            if item['player']['id']=='team_a_4':item['health_fatigue']=100;item['health_rust']=25
        unhealthy=result(c,config());normal=result(experiment=config())
        ua=unhealthy.team_lines[0]['interior_experiment']['defense_report']['C27']['responses']['rim'];na=normal.team_lines[0]['interior_experiment']['defense_report']['C27']['responses']['rim']
        self.assertLess(ua['context']['capacity_factor'],na['context']['capacity_factor'])
        self.assertNotEqual(unhealthy.team_lines[0]['interior_experiment']['revision'],normal.team_lines[0]['interior_experiment']['revision'])
        no=game_fixture();no['canonical']['players'][4]['minutes_projection']=0
        absent=result(no,config());self.assertEqual(absent.team_lines[0]['interior_experiment']['defense_report']['C27']['responses']['rim']['coverage_available'],0)
        stale=game_fixture();stale['canonical']['players'][4]['team_id']='team_b'
        with self.assertRaisesRegex(ValueError,'ownership'):result(stale,config())

    def test_explicit_deployment_required_no_missing_player_fallback(self):
        with self.assertRaises(ValueError):result(experiment=InteriorExperiment(()))
        with self.assertRaises(ValueError):InteriorExperiment((Anchor('team_a',scenario_profile()),),('team_a',))
        with self.assertRaises(ValueError):InteriorExperiment((),('team_a','team_b'),121)

    def test_context_game_and_response_ownership_no_authoritative_mutation(self):
        context=game_fixture();before=deepcopy(context['canonical']);p=scenario_profile('team_a_4');x=config(p)
        first=result(context,x)
        # Existing normal feature caches are snapshot-owned derived metadata.
        plain=lambda c:{k:v for k,v in c.items() if not k.startswith('_')}
        self.assertEqual(plain(context['canonical']),plain(before))
        first.team_lines[0]['interior_experiment']['defense_report']['raw_inputs']['inputs']['S36']['value']['grade']=1
        second=result(context,x)
        self.assertEqual(second.team_lines[0]['interior_experiment']['defense_report']['raw_inputs'],p.inputs.to_dict())
        ref=weakref.ref(x);pr=weakref.ref(p);del x,p
        self.assertIsNone(ref());self.assertIsNone(pr())

    def test_source_section_alone_cannot_enable_experiment_or_consume_global_rng(self):
        import random
        from nba_gm_data.player_model import put_player_inputs
        context=game_fixture()
        put_player_inputs(context['canonical'],scenario_profile('team_a_4').inputs)
        before=random.getstate()
        with patch('nba_gm_data.interior_game.simulate_interior_game',side_effect=AssertionError('must remain off')):
            normal=result(context)
        self.assertEqual(before,random.getstate())
        self.assertNotIn('interior_experiment',normal.team_lines[0])

    def test_overtime_retains_event_accounting_without_forcing_a_winner(self):
        r=result(experiment=replace(config(),possessions=1),seed=1)
        self.assertEqual(r.possessions,11)
        validate_accounting(r)
        for tid in ('team_a','team_b'):
            self.assertAlmostEqual(sum(row['minutes'] for row in r.player_lines if row['team_id']==tid),265)

    def test_reconstructed_input_and_sequence_repeat_not_an_app_action_claim(self):
        p=scenario_profile('team_a_4');x=config(p)
        sequence=[result(experiment=x,seed=seed) for seed in (17,29)]
        restored=compile_profile(PlayerInputs(json.loads(json.dumps(p.inputs.to_dict()))))
        replay=[result(experiment=config(restored),seed=seed) for seed in (17,29)]
        self.assertEqual([to_plain(r) for r in sequence],[to_plain(r) for r in replay])


class InteriorConsumerTests(unittest.TestCase):
    def test_read_only_legacy_quote_probe_and_unwired_retention_are_explicit(self):
        from experiments.interior_defense.consumers import consumer_probe
        canonical=json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text())
        canonical['_allow_internal_caches']=True
        doc=json.loads(PACKET.read_text())['scenarios'][0]['input_section']['players']['player_mil-myles-turner']
        profile=compile_profile(PlayerInputs(doc),research_scenario=True)
        # Snapshot just the authoritative numerical/economic inputs, not caches.
        tracked=('players','traits','player_asset_valuations','player_contract_market_profiles','player_contract_preferences','team_strategic_states')
        before={k:deepcopy(canonical[k]) for k in tracked}
        report=consumer_probe(canonical,profile)
        self.assertNotEqual(*report['on_court_before_after'])
        self.assertNotEqual(report['contract_before_after'][0]['model_aav'],report['contract_before_after'][1]['model_aav'])
        self.assertNotEqual(report['negotiation_quote_before_after'][0]['player_score'],report['negotiation_quote_before_after'][1]['player_score'])
        self.assertEqual(*report['retention_before_after'])
        self.assertIn('retention/card DEF/OVR',report['unwired'])
        self.assertEqual({k:canonical[k] for k in tracked},before)


if __name__=='__main__':unittest.main()
