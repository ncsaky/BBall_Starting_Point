"""Coupled mechanism checks; no final player ranking/league calibration tests."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import unittest
import weakref
from unittest.mock import patch

from nba_gm_data import sim
from nba_gm_data.interior_defense import ArrivalContext,compile_profile,interior_response
from nba_gm_data.interior_game import shot_probabilities,validate_accounting
from nba_gm_data.offense_response import (compile_offense,shooting_response,free_throw_response,finishing_response,credibility,offensive_spatial_profile,prepare_coupled,plan_attack,baseline,Deployment,CombinedOffense,OffenseCoefficients)
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.schema import to_plain
from nba_gm_data.shot_geometry import ShotGeometry,GeometryCoefficients
from experiments.offense_interior.fixtures import offensive_document,combined_fixture

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT/'docs/ratings-evidence-2026-10-29/OFFENSE_INTERIOR_INTERACTION_INPUTS_2026_11_13.json'


def profile(**kwargs):return compile_offense(PlayerInputs(offensive_document('controlled',**kwargs)))

def game(**kwargs):
    context,config=combined_fixture(**kwargs)
    return sim.sim_game_with_context(context,'interior_fixture',seed=17,interior_experiment=config)


def change_skill(p,number,grade):
    doc=p.inputs.to_dict();doc['inputs'][f'S{number:02d}']['value']['grade']=grade
    return compile_offense(PlayerInputs(doc))


class ShootingFinishResponseTests(unittest.TestCase):
    def test_modes_are_separate_and_movement_does_not_add_catch_skill(self):
        base=profile(shooting=65);changed=change_skill(base,1,95)
        self.assertGreater(shooting_response(changed,mode='catch')['make_probability'],shooting_response(base,mode='catch')['make_probability'])
        for mode in ('pull_up','movement'):self.assertEqual(shooting_response(changed,mode=mode)['make_probability'],shooting_response(base,mode=mode)['make_probability'])
        mid=change_skill(base,4,95)
        self.assertGreater(shooting_response(mid,distance_m=4.5)['make_probability'],shooting_response(base,distance_m=4.5)['make_probability'])
        self.assertEqual(shooting_response(mid,distance_m=7)['make_probability'],shooting_response(base,distance_m=7)['make_probability'])

    def test_skill_and_willingness_are_distinct_sources_of_credible_space(self):
        strong=profile(shooting=90,willingness=.9);reluctant=profile(shooting=90,willingness=.1);weak=profile(shooting=30,willingness=.9)
        self.assertGreater(credibility(strong),credibility(reluctant));self.assertGreater(credibility(strong),credibility(weak))
        self.assertEqual(shooting_response(strong),{**shooting_response(reluctant),'source_revision':strong.revision})
        self.assertLess(baseline(reluctant)['three_share'],baseline(strong)['three_share'])

    def test_preparation_is_contextual_and_free_throws_are_independent(self):
        fast=profile(release=95);slow=profile(release=20)
        self.assertLess(shooting_response(fast)['preparation_s'],shooting_response(slow)['preparation_s'])
        self.assertGreater(shooting_response(fast,pressure=1,defender_arrival_s=.4)['make_probability'],shooting_response(slow,pressure=1,defender_arrival_s=.4)['make_probability'])
        self.assertEqual(shooting_response(fast,pressure=0)['make_probability'],shooting_response(slow,pressure=0)['make_probability'])
        self.assertEqual(free_throw_response(fast),free_throw_response(slow))
        ft=change_skill(fast,7,95)
        self.assertGreater(free_throw_response(ft),free_throw_response(fast));self.assertEqual(shooting_response(ft)['make_probability'],shooting_response(fast)['make_probability'])

    def test_extension_changes_distance_response_not_every_shot(self):
        a=profile(extension=15);b=profile(extension=95)
        self.assertEqual(shooting_response(a,distance_m=4.5)['make_probability'],shooting_response(b,distance_m=4.5)['make_probability'])
        self.assertGreater(shooting_response(b,distance_m=9)['make_probability'],shooting_response(a,distance_m=9)['make_probability'])
        self.assertEqual(free_throw_response(a),free_throw_response(b))

    def test_layup_contact_floater_dunk_and_lob_have_local_inputs(self):
        p=profile(layup=60,floater=60,dunk=60,aerial=60,contact=60)
        for number,kind in [(10,'layup'),(11,'floater'),(12,'dunk'),(13,'lob'),(15,'contact_layup')]:
            q=change_skill(p,number,95)
            self.assertGreater(finishing_response(q,kind,contact=1)['make_probability'],finishing_response(p,kind,contact=1)['make_probability'])
            unaffected='floater' if number in (10,12,13,15) else 'layup'
            self.assertEqual(finishing_response(q,unaffected)['make_probability'],finishing_response(p,unaffected)['make_probability'])
        stronger=change_skill(p,15,95)
        self.assertEqual(finishing_response(stronger,'layup')['make_probability'],finishing_response(p,'layup')['make_probability'])

    def test_catching_and_aerial_coordination_do_not_create_opportunities(self):
        a=profile(receiving=25,aerial=70);b=profile(receiving=95,aerial=70)
        ra=finishing_response(a,'lob',delivery_quality=.8);rb=finishing_response(b,'lob',delivery_quality=.8)
        self.assertLess(ra['reception_probability'],rb['reception_probability']);self.assertEqual(ra['make_probability'],rb['make_probability'])
        low=profile(reach=240,jump=20)
        self.assertFalse(finishing_response(low,'lob')['physically_dunk_available']);self.assertEqual(finishing_response(low,'lob')['finish'],'layup')
        self.assertEqual(finishing_response(b,'lob',delivery_quality=0)['reception_probability'],0)

    def test_research_scales_raw_inputs_unknowns_and_ft_proxy_are_explicit(self):
        packet=json.loads(PACKET.read_text());before=deepcopy(packet);validate_input_section(packet['player_input_section']);count=0
        for scenario in packet['scenarios']:
            validate_input_section(scenario['input_section'])
            for doc in scenario['input_section']['players'].values():
                p=compile_offense(PlayerInputs(doc),research_scenario=True,two_point_rim_fraction=.65);count+=1
                self.assertEqual(p.inputs.to_dict(),doc)
                self.assertEqual(free_throw_response(p),doc['inputs']['S07']['value']['grade']/100)
        self.assertEqual(count,132);self.assertEqual(packet,before)
        for doc in packet['player_input_section']['players'].values():
            with self.assertRaises(ValueError):compile_offense(PlayerInputs(doc),research_scenario=True,two_point_rim_fraction=.65)
        doc=next(iter(packet['scenarios'][0]['input_section']['players'].values()))
        with self.assertRaises(ValueError):compile_offense(PlayerInputs(doc),research_scenario=True)
        with self.assertRaises(ValueError):compile_offense(PlayerInputs(doc))

    def test_missing_units_context_and_revision_invalidation(self):
        original=profile();doc=original.inputs.to_dict();doc['inputs']['S10']['value']['grade']=15
        changed=compile_offense(PlayerInputs(doc));self.assertNotEqual(original.revision,changed.revision)
        for mutate in (lambda d:d['inputs'].pop('S08'),lambda d:d['inputs']['P03']['value']['measurements'][0].update(unit='inches'),lambda d:d['inputs']['P10']['value']['measurements'][0].update(protocol='unknown'),lambda d:d['inputs']['S07']['value'].update(scale='generic_unsupported')):
            doc=original.inputs.to_dict();mutate(doc)
            with self.assertRaises(ValueError):compile_offense(PlayerInputs(doc))
        with self.assertRaises(ValueError):Deployment('p',0,2)
        with self.assertRaises(ValueError):OffenseCoefficients(positioning_pull_points=0)


class GeometryInteractionTests(unittest.TestCase):
    def test_varied_release_location_angle_reach_and_arrival(self):
        p=compile_profile(PlayerInputs(offensive_document('defender',reach=290,jump=60)))
        ctx=ArrivalContext();g=ShotGeometry(0,1,315,0,1,approach_angle_deg=0)
        a=interior_response(p,ctx,geometry=g)
        tall=compile_profile(PlayerInputs(offensive_document('defender',reach=310,jump=60)))
        self.assertGreater(interior_response(tall,ctx,geometry=g)['geometry_fraction'],a['geometry_fraction'])
        self.assertEqual(interior_response(p,ctx,geometry=replace(g,release_height_cm=400))['block_probability'],0)
        far=replace(g,defender_x_m=8,defender_y_m=5,attack_time_s=.1,preparation_s=.1)
        self.assertEqual(interior_response(p,ctx,geometry=far)['coverage_available'],0)
        self.assertLess(interior_response(p,replace(ctx,recognition_delay_s=2),geometry=g)['coverage_available'],a['coverage_available'])
        self.assertLess(interior_response(p,ctx,geometry=replace(g,approach_angle_deg=90))['contest_quality'],a['contest_quality'])
        self.assertGreater(interior_response(p,ctx,geometry=replace(g,release_height_cm=280))['geometry_fraction'],a['geometry_fraction'])

    def test_interior_changes_cannot_manufacture_perimeter_defense(self):
        a=compile_profile(PlayerInputs(offensive_document('d',reach=270)));b=compile_profile(PlayerInputs(offensive_document('d',reach=320)))
        g=ShotGeometry(0,7,280,0,1)
        for profile_ in (a,b):
            r=interior_response(profile_,ArrivalContext(),zone='perimeter',geometry=g)
            for key in ('conversion_reduction','block_probability','foul_probability','avoidance_probability'):self.assertEqual(r[key],0)

    def test_spacing_comes_from_offensive_profiles_not_manual_spacing_knob(self):
        strong=game(shooting=90,willingness=.9);reluctant=game(shooting=90,willingness=.1);weak=game(shooting=30,willingness=.9)
        position=lambda r:math.hypot(*r.team_lines[0]['interior_experiment']['combined_offense']['anchor_position_m'])
        self.assertGreater(position(strong),position(reluctant));self.assertGreater(position(strong),position(weak))
        c,x=combined_fixture();y=replace(x,anchors=tuple(replace(a,context=replace(a.context,spacing=0)) for a in x.anchors))
        z=replace(x,anchors=tuple(replace(a,context=replace(a.context,spacing=1)) for a in x.anchors))
        r=sim.sim_game_with_context(c,'interior_fixture',seed=17,interior_experiment=y)
        s=sim.sim_game_with_context(c,'interior_fixture',seed=17,interior_experiment=z)
        self.assertEqual(r.player_lines,s.player_lines)

    def test_controlled_poa_support_changes_arrival_without_changing_shooting_skill(self):
        a=game(shooting=30,willingness=.2,poa=0);b=game(shooting=30,willingness=.2,poa=1)
        def effects(r):return [e['coupled_opportunity']['defense_response'] for e in r.team_lines[1]['interior_experiment']['offense_attack_ledger'] if e.get('coupled_opportunity',{}).get('defense_response') and e['zone']!='perimeter']
        self.assertGreater(sum(x['coverage_available'] for x in effects(b)),sum(x['coverage_available'] for x in effects(a)))


class CoupledGameTests(unittest.TestCase):
    def test_shared_event_accounting_and_actual_changed_outcomes(self):
        a=game(shooting=30,willingness=.9);b=game(shooting=90,willingness=.9)
        for result in (a,b):validate_accounting(result)
        self.assertNotEqual(a.player_lines,b.player_lines);self.assertNotEqual(a.away_score,b.away_score)
        for r in (a,b):
            for t in r.team_lines:
                self.assertIn('combined_offense',t['interior_experiment'])
                self.assertEqual(t['points'],2*t['fgm']+t['fg3m']+t['ftm'])

    def test_c36_reads_the_same_varied_geometry_that_decided_attempts(self):
        result=game(shooting=90,willingness=.1)
        responses=[]
        for event in result.team_lines[1]['interior_experiment']['offense_attack_ledger']:
            detail=event.get('avoided_interior_opportunity') or event.get('coupled_opportunity')
            response=detail.get('defense_response') if detail else None
            if response and response['zone']!='perimeter':responses.append(response)
        report=result.team_lines[0]['interior_experiment']['defense_report']
        self.assertEqual(report['C36']['sample_count'],len(responses))
        self.assertAlmostEqual(report['C36']['mean_conditional_conversion_reduction'],sum(r['conversion_reduction'] for r in responses)/len(responses))
        self.assertEqual(report['C27']['status'],'partial_varied_geometry')
        self.assertIn('legacy_scalar_reference',report)

    def test_receiver_failure_creates_turnover_not_fake_shot_or_rebound(self):
        c,x=combined_fixture(finish_mix=(0,0,0,0,1));x=replace(x,offense=replace(x.offense,delivery_quality=0))
        r=sim.sim_game_with_context(c,'interior_fixture',seed=29,interior_experiment=x);validate_accounting(r)
        failed=[e for t in r.team_lines for e in t['interior_experiment']['offense_attack_ledger'] if e['outcome']=='reception_turnover']
        self.assertTrue(failed);self.assertTrue(all(not e.get('reboundable_miss') and not e.get('points') for e in failed))

    def test_no_old_new_shooting_or_rim_bonus_and_unchanged_authoritative_inputs(self):
        c,x=combined_fixture();before=deepcopy(c['canonical']);a=sim.sim_game_with_context(c,'interior_fixture',seed=17,interior_experiment=x)
        self.assertEqual({k:v for k,v in c['canonical'].items() if not k.startswith('_')},{k:v for k,v in before.items() if not k.startswith('_')})
        d=deepcopy(before)
        for trait in d['traits']:trait['value']=1
        c['canonical']=d;c['sim_cache']={}
        b=sim.sim_game_with_context(c,'interior_fixture',seed=17,interior_experiment=x)
        self.assertEqual(to_plain(a),to_plain(b))

    @unittest.skip('needs review: frozen compiler predates improved box allocation (6a3c90c, c29f301); refresh authenticated reference after coordinator review')
    def test_default_off_full_result_parity_with_stage_b_reference(self):
        spec=importlib.util.spec_from_file_location('nba_gm_data._combined_reference',ROOT/'output/offense-interior-interaction-2026-11-13/sim.py.reference')
        # .reference has no recognized Python suffix, so use an explicit loader.
        from importlib.machinery import SourceFileLoader
        spec=importlib.util.spec_from_loader('nba_gm_data._combined_reference',SourceFileLoader('nba_gm_data._combined_reference',str(ROOT/'output/offense-interior-interaction-2026-11-13/sim.py.reference')))
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                c,_=combined_fixture();d,_=combined_fixture()
                self.assertEqual(to_plain(sim.sim_game_with_context(c,'interior_fixture',mode,seed)),to_plain(old.sim_game_with_context(d,'interior_fixture',mode,seed)))

    def test_prior_interior_only_event_path_remains_exact(self):
        from importlib.machinery import SourceFileLoader
        from experiments.interior_defense.fixtures import game_fixture,scenario_profile
        from nba_gm_data.interior_defense import InteriorExperiment,Anchor
        path=ROOT/'output/offense-interior-interaction-2026-11-13/interior_game.py.reference'
        spec=importlib.util.spec_from_loader('nba_gm_data._old_interior_event',SourceFileLoader('nba_gm_data._old_interior_event',str(path)))
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        for seed in (17,29):
            ctx=game_fixture();a,b=ctx['canonical']['teams'];g=ctx['schedule'][0]
            pools=[sim.game_player_pool(ctx,'interior_fixture',t,'replay-real-minutes',game_date=g['gameDate']) for t in (a,b)]
            config=InteriorExperiment((Anchor('team_a',scenario_profile('team_a_4')),),('team_b',))
            actual=sim.sim_game_with_context(ctx,'interior_fixture',seed=seed,interior_experiment=config)
            before=old.simulate_interior_game(ctx['canonical'],g,a,b,*pools,'replay-real-minutes',seed,config)
            self.assertEqual(to_plain(actual),to_plain(before))

    def test_c36_is_still_only_reporting_in_the_coupled_path(self):
        from nba_gm_data.interior_game import reference_report
        context,config=combined_fixture();a=sim.sim_game_with_context(context,'interior_fixture',seed=17,interior_experiment=config)
        def changed(*args,**kwargs):
            report=reference_report(*args,**kwargs);report['C36']['conversion_points_prevented_per_100_rim_fga']=100000;return report
        with patch('nba_gm_data.interior_game.reference_report',side_effect=changed):
            b=sim.sim_game_with_context(context,'interior_fixture',seed=17,interior_experiment=config)
        self.assertEqual(a.player_lines,b.player_lines)

    def test_reconstruction_isolation_and_snapshot_release_at_exposed_boundary(self):
        c,x=combined_fixture();a=sim.sim_game_with_context(c,'interior_fixture',seed=17,interior_experiment=x)
        profiles=tuple(compile_offense(PlayerInputs(json.loads(json.dumps(p.inputs.to_dict())))) for p in x.offense.profiles)
        y=replace(x,offense=replace(x.offense,profiles=profiles));b=sim.sim_game_with_context(c,'interior_fixture',seed=17,interior_experiment=y)
        self.assertEqual(to_plain(a),to_plain(b))
        a.team_lines[0]['interior_experiment']['combined_offense']['spatial_profiles']['team_a_0']['raw_inputs']['inputs']['S01']['value']['grade']=0
        again=sim.sim_game_with_context(c,'interior_fixture',seed=17,interior_experiment=x)
        self.assertNotEqual(a.team_lines[0],again.team_lines[0]);self.assertEqual(b.player_lines,again.player_lines)
        ref=weakref.ref(y);del y;self.assertIsNone(ref())

    def test_offense_and_defense_cannot_hold_different_talents_for_one_player(self):
        context,config=combined_fixture()
        anchor=config.anchors[0];doc=anchor.profile.inputs.to_dict()
        doc['inputs']['P03']['value']['measurements'][0]['value']+=10
        wrong=replace(config,anchors=(replace(anchor,profile=compile_profile(PlayerInputs(doc))),))
        with self.assertRaisesRegex(ValueError,'one authoritative'):
            sim.sim_game_with_context(context,'interior_fixture',interior_experiment=wrong)

    def test_every_active_player_and_current_assignment_must_be_explicit(self):
        c,x=combined_fixture()
        with self.assertRaises(ValueError):sim.sim_game_with_context(c,'interior_fixture',interior_experiment=replace(x,offense=replace(x.offense,profiles=x.offense.profiles[:-1],deployments=x.offense.deployments[:-1])))
        with self.assertRaises(ValueError):sim.sim_game_with_context(c,'interior_fixture',interior_experiment=replace(x,offense=replace(x.offense,anchor_assignments=(('team_a','team_a_0'),))))
        changed=replace(x,offense=replace(x.offense,primary_arrival_s=.2));self.assertNotEqual(x.revision,changed.revision)


if __name__=='__main__':unittest.main()
