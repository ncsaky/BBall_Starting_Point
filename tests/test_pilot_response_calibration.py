"""Causal timing/contest checks for the explicit milestone-7 policy."""
from copy import deepcopy
from dataclasses import replace
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
import weakref

from nba_gm_data.creation_passing import resolve_drive,HELP_RESPONSE_POLICY
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from experiments.player_input_pilot.pilot import build_pilot,variant,IDS
from experiments.pilot_response_calibration.fixtures import fixture,boundary_start,fixed_draws
from experiments.pilot_response_calibration.probes import choice_probability,path_endpoint_sweep
from experiments.pilot_response_calibration.verification import reference_modules,use_reference,reference_config
from experiments.pilot_response_calibration.overlay import apply_overlay,VERSION as OVERLAY_VERSION


def action(state,draws=None):
    return resolve_drive(state,state['audit_context']['ids'][0],'response_a','response_b',fixed_draws() if draws is None else draws,24)


class ResponseCausalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pilot=build_pilot()

    def test_arrival_deadline_label_can_change_without_a_choice_score_cliff(self):
        for alias in ('white','castle'):
            for window in (.9,1.1,1.3):
                pairs={}
                for policy in ('legacy_timely_v1',HELP_RESPONSE_POLICY):
                    s,_,_=fixture(self.pilot,alias,window=window,policy=policy,commitment=1)
                    results=[]
                    for delta in (-1e-6,1e-6):
                        boundary_start(s,delta);results.append(action(s))
                    a,b=results
                    self.assertTrue(a['record']['help']['timely']);self.assertFalse(b['record']['help']['timely'])
                    pairs[policy]=b['record']['choice_scores']['finish']-a['record']['choice_scores']['finish']
                    self.assertLess(abs(b['plan']['response']['conversion_reduction']-a['plan']['response']['conversion_reduction']),1e-5)
                self.assertAlmostEqual(pairs['legacy_timely_v1'],.675)
                self.assertLess(abs(pairs[HELP_RESPONSE_POLICY]),1e-4)

    def test_projected_effect_is_the_existing_c27_conversion_and_block_cost(self):
        s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY,commitment=1)
        boundary_start(s,.05);r=action(s);p=r['record']['help_finish_projection']
        self.assertFalse(r['record']['help']['timely'])
        expected=(1-p['block_probability'])*max(0,p['base_conversion_probability']-p['conversion_reduction'])
        self.assertAlmostEqual(p['make_probability_given_no_foul'],expected)
        self.assertAlmostEqual(p['contest_failure_increment'],p['base_conversion_probability']-expected)
        self.assertGreater(p['contest_failure_increment'],0)
        self.assertEqual(p['policy'],HELP_RESPONSE_POLICY)

    def test_no_physical_vertical_contest_means_no_bonus_from_timely_label(self):
        p=variant(self.pilot,{'white':{'P03':150,'P10':0}},name='explicit unreachable contest control')
        s,_,_=fixture(p,policy=HELP_RESPONSE_POLICY,commitment=1)
        boundary_start(s,-.2);r=action(s)
        self.assertTrue(r['record']['help']['timely'])
        self.assertEqual(r['record']['help_finish_projection']['contest_failure_increment'],0)
        self.assertEqual(r['plan']['response']['conversion_reduction'],0)
        self.assertEqual(r['plan']['response']['block_probability'],0)

    def test_early_marginal_late_effect_tracks_coverage_and_keeps_deadline(self):
        s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY,commitment=1);costs=[]
        for delta in (-.3,0,.1,.3):
            boundary_start(s,delta);r=action(s);costs.append(r['record']['help_finish_projection']['contest_failure_increment'])
        self.assertGreaterEqual(costs[0],costs[1]);self.assertGreater(costs[1],costs[2]);self.assertEqual(costs[3],0)

    def test_actual_selected_finish_contest_is_unchanged_and_not_applied_twice(self):
        for delta in (-.2,.05,.3):
            results=[]
            for policy in ('legacy_timely_v1',HELP_RESPONSE_POLICY):
                s,_,_=fixture(self.pilot,policy=policy,commitment=1)
                boundary_start(s,delta);results.append(action(s))
            a,b=results
            self.assertEqual(a['record']['choice'],'finish');self.assertEqual(b['record']['choice'],'finish')
            self.assertEqual(a['plan']['off'],b['plan']['off'])
            for key in ('conversion_reduction','block_probability','foul_probability','coverage_available'):
                self.assertAlmostEqual(a['plan']['response'][key],b['plan']['response'][key])
            self.assertEqual(a['record']['help'],b['record']['help'])

    def test_helper_route_bearing_does_not_reset_at_the_exact_endpoint(self):
        rows=path_endpoint_sweep(self.pilot,policy=HELP_RESPONSE_POLICY)
        for a,b in zip(rows[::2],rows[1::2],strict=True):
            self.assertLess(abs(a['actual_contest']['contest_alignment']-b['actual_contest']['contest_alignment']),1e-8)
            self.assertLess(abs(a['actual_contest']['conversion_reduction']-b['actual_contest']['conversion_reduction']),1e-5)
            self.assertLess(abs(a['finish_choice_score']-b['finish_choice_score']),1e-4)
            self.assertIn('defender_route_origin_m',a['actual_contest'])

    def test_effective_positioning_route_position_agrees_with_its_arrival(self):
        import math
        s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY,commitment=1)
        for delta in (-.05,.05):
            boundary_start(s,delta);r=action(s);position=r['record']['help_position_at_pass_m']
            distance=math.dist(position,(.8,1.5))
            if delta<0:self.assertLess(distance,1e-9)
            else:self.assertGreater(distance,0)
            self.assertEqual(r['record']['help']['timely'],delta<0)

    def test_route_origin_is_explicit_and_invalid_values_are_rejected(self):
        from nba_gm_data.offense_response import HelpShotContext
        from nba_gm_data.interior_defense import interior_response
        s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY)
        with self.assertRaisesRegex(ValueError,'route origin'):HelpShotContext(defender_route_origin_m=(float('nan'),0))
        with self.assertRaisesRegex(ValueError,'immutable'):HelpShotContext(defender_route_origin_m=[1,1])
        with self.assertRaisesRegex(ValueError,'shot geometry'):interior_response(s['anchors']['response_b'].profile,s['contexts']['response_b'],defender_route_origin_m=(1,1))

    def test_frozen_reference_context_uses_its_own_screen_classes(self):
        modules=reference_modules()
        with use_reference(modules):
            s,_,_=fixture(self.pilot,coverage='show_then_recover')
            self.assertIsInstance(s['screens']['spec'],modules['nba_gm_data.screen_navigation'].ScreenExperiment)
            r=modules['nba_gm_data.creation_passing'].resolve_drive(s,s['audit_context']['ids'][0],'response_a','response_b',fixed_draws(),24)
            self.assertIn(r['kind'],('shot','turnover','reset'))

    def test_unavailable_uncommitted_or_unnoticed_helper_has_no_projection_bonus(self):
        for controls in ({'available':0},{'commitment':0},{}):
            s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY,**controls)
            d=fixed_draws()
            if not controls:d[26]=.999
            r=action(s,d)
            self.assertFalse(r['record']['help']['committed'])
            self.assertEqual(r['record']['help_finish_projection']['contest_failure_increment'],0)
            self.assertEqual(r['plan']['response']['conversion_reduction'] if r['plan']['response'] else 0,0)

    def test_contained_drive_does_not_get_a_finish_or_emergency_help(self):
        s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY);d=fixed_draws();d[25]=.999
        r=action(s,d)
        self.assertNotIn('finish',r['record']['choice_scores']);self.assertFalse(r['record']['help']['committed'])
        self.assertNotIn('help_finish_projection',r['record'])

    def test_policy_revision_is_explicit_and_default_legacy_is_authentic(self):
        s,_,x=fixture(self.pilot);_,_,y=fixture(self.pilot,policy=HELP_RESPONSE_POLICY)
        self.assertNotEqual(x.revision,y.revision)
        self.assertEqual(x.offense.creation.help_response_policy,'legacy_timely_v1')
        with self.assertRaisesRegex(ValueError,'policy'):replace(x.offense.creation,help_response_policy='automatic')
        modules=reference_modules()
        with use_reference(modules):old=reference_config(x,modules)
        self.assertEqual(x.revision,old.revision)
        a=action(s)
        with use_reference(modules):b=modules['nba_gm_data.creation_passing'].resolve_drive(s,s['audit_context']['ids'][0],'response_a','response_b',fixed_draws(),24)
        self.assertEqual(to_plain(a),to_plain(b))

    def test_projection_uses_no_extra_draws_and_inspection_cannot_mutate_inputs(self):
        s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY);before={k:v.inputs.to_dict() for k,v in s['profiles'].items()}
        d=fixed_draws();original=list(d);a=action(s,d);expected=deepcopy(a)
        self.assertEqual(d,original)
        a['record']['help_finish_projection']['contest_failure_increment']=999
        self.assertEqual(action(s,d),expected)
        self.assertEqual(before,{k:v.inputs.to_dict() for k,v in s['profiles'].items()})

    def test_named_extra_role_dependencies_are_separate_common_controls(self):
        before=deepcopy(self.pilot['source_documents']);s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY)
        rows=s['audit_context']['extra_role_completions'];self.assertTrue(rows)
        self.assertTrue(all(r['original_record']['status']=='unknown' for r in rows))
        self.assertTrue(all('not player evidence' in r['origin'] for r in rows))
        self.assertEqual(before,self.pilot['source_documents'])
        helper=s['profiles'][IDS['white']];self.assertIs(helper.inputs,s['anchors']['response_b'].profile.inputs)

    def test_combined_shooting_and_passing_changes_choices_without_free_help_bonus(self):
        results=[]
        for grade,willing in ((50,.1),(90,.85)):
            s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY,shooter_grade=grade,shoot_probability=willing,finish_grade=50,start=(1.2,1.5))
            results.append(action(s))
        a,b=results
        self.assertEqual(a['record']['help'],b['record']['help'])
        self.assertEqual(a['record']['choice_scores']['finish'],b['record']['choice_scores']['finish'])
        self.assertGreater(b['record']['choice_scores']['F06'],a['record']['choice_scores']['F06'])

    def test_spacer_threat_changes_actual_start_and_travel_through_existing_pipeline(self):
        results=[]
        for grade,willing in ((50,.1),(90,.85)):
            s,_,_=fixture(self.pilot,policy=HELP_RESPONSE_POLICY,shooter_grade=grade,shoot_probability=willing,start=None)
            results.append(action(s))
        a,b=results
        self.assertGreater(b['record']['help']['arrival_s'],a['record']['help']['arrival_s'])
        self.assertNotEqual(a['record']['help']['start_m'],b['record']['help']['start_m'])

    def test_small_kernel_accounting_both_policies_and_independent_screen_coverage(self):
        for policy in ('legacy_timely_v1',HELP_RESPONSE_POLICY):
            for coverage in ('stay','show_then_recover'):
                _,c,x=fixture(self.pilot,policy=policy,coverage=coverage,possessions=8,start=None)
                r=sim.sim_game_with_context(c,'response_fixture',seed=17,interior_experiment=x)
                validate_accounting(r)
                self.assertTrue(any(e.get('creation_chain',{}).get('screen_action',{}).get('kind')=='screen' for t in r.team_lines for e in t['interior_experiment']['offense_attack_ledger']))

    def test_prepared_and_result_roots_release_without_new_global_cache(self):
        s,c,x=fixture(self.pilot,policy=HELP_RESPONSE_POLICY,possessions=4)
        r=sim.sim_game_with_context(c,'response_fixture',seed=17,interior_experiment=x)
        refs=[weakref.ref(x),weakref.ref(x.offense.creation),weakref.ref(r),weakref.ref(s['profiles'][IDS['white']].inputs)]
        del s,c,x,r
        self.assertTrue(all(ref() is None for ref in refs))


class EvidenceOverlayTests(unittest.TestCase):
    def overlay(self):
        base_path=Path(__file__).resolve().parents[1]/'output/player-input-pilot-2026-11-14/verified/initial-readiness-completion-layer.json'
        base=json.loads(base_path.read_text());pid=IDS['luka'];key='S17'
        before=deepcopy(base['pilot_section']['players'][pid]['inputs'][key]);after=deepcopy(before);after['value']['grade']=84
        proposed=deepcopy(base['pilot_section']);proposed['players'][pid]['inputs'][key]=after
        return {'version':OVERLAY_VERSION,'scenario':'test proposed estimate','base_artifact':str(base_path),
            'base_sha256':hashlib.sha256(base_path.read_bytes()).hexdigest(),'source_section':base['source_section'],
            'pilot_section':proposed,'contract':base['contract'],'contract_revision':base['contract_revision'],
            'new_targeted_record_count':1,'inherited_record_count':0,'overrides':[{'player_id':pid,'design_id':key,
            'baseline_record':before,'scenario_record':after,'source_record':base['source_section']['players'][pid]['inputs'][key],
            'origin':'new_targeted_estimate','range':[76,92],'shared_evidence_group':'test only'}]}

    def apply(self,pilot,data,digest=None):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'overlay.json';path.write_text(json.dumps(data))
            return apply_overlay(pilot,path,digest or hashlib.sha256(path.read_bytes()).hexdigest())

    def test_pinned_overlay_is_separate_source_preserving_idempotent_and_shared(self):
        p=build_pilot();source=deepcopy(p['source_documents']);data=self.overlay();q,_=self.apply(p,data)
        self.assertEqual(q['source_documents'],source);self.assertEqual(p['views'][IDS['luka']].input('S17')['value']['grade'],65)
        self.assertEqual(q['views'][IDS['luka']].input('S17')['value']['grade'],84)
        r,_=self.apply(q,data);self.assertEqual(len(r['overrides']),len(q['overrides']))
        self.assertEqual(r['overlay_audit']['already_identical_fields'],[[IDS['luka'],'S17']])

    def test_pin_and_conflicting_prior_cannot_be_silently_overwritten(self):
        p=build_pilot();data=self.overlay()
        with self.assertRaisesRegex(ValueError,'SHA256'):self.apply(p,data,'0'*64)
        changed=variant(p,{'luka':{'S17':90}},name='independent newer estimate')
        with self.assertRaisesRegex(ValueError,'rebase'):self.apply(changed,data)

    def test_undeclared_changes_and_changed_source_are_rejected(self):
        p=build_pilot();data=self.overlay();data['pilot_section']['players'][IDS['luka']]['inputs']['S16']['value']['grade']=1
        with self.assertRaisesRegex(ValueError,'Undeclared'):self.apply(p,data)
        data=self.overlay();data['source_section']['players'][IDS['luka']]['inputs']['S16']['value']['grade']=1
        with self.assertRaisesRegex(ValueError,'source records'):self.apply(p,data)


if __name__=='__main__':unittest.main()
