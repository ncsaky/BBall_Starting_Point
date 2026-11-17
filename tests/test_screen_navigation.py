"""Bounded screen/roll/slip response and shared-accounting acceptance checks."""
from copy import deepcopy
from dataclasses import fields,replace
from importlib.machinery import SourceFileLoader
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data import sim
from nba_gm_data.creation_passing import resolve_drive,compile_interaction
from nba_gm_data.interior_defense import compile_profile
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.offense_response import compile_offense
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.schema import to_plain
from nba_gm_data.screen_navigation import (compile_screen,ScreenExperiment,ScreenCall,ScreenCoefficients,resolve_screen,receiver_position,coverage_position)
from experiments.screen_navigation.fixtures import screen_fixture
from experiments.creation_passing.fixtures import action_state

ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'output/screen-navigation-2026-11-13/reference'


def draws():
    d=[0.0]*48;d[24]=.999;d[28]=.999;d[32]=.999;d[41]=.5;d[42]=.999
    return d


def action(config,d=None,*,allowed=True):
    return resolve_drive(action_state(config),'team_b_0','team_b','team_a',draws() if d is None else d,24,screen_allowed=allowed)


def phase(config,d=None):
    state=action_state(config)
    return resolve_screen(state['screens'],state['profiles']['team_b_0'],state['setups']['team_b_0'],draws() if d is None else d)


def call_change(config,**kwargs):
    spec=config.offense.creation.screens
    calls=tuple(replace(c,**kwargs) if c.creator_id=='team_b_0' else c for c in spec.calls)
    return replace(config,offense=replace(config.offense,creation=replace(config.offense.creation,screens=replace(spec,calls=calls))))


def families(config,enabled):
    s=config.offense.creation
    return replace(config,offense=replace(config.offense,creation=replace(s,setups=tuple(replace(z,enabled_pass_families=enabled) for z in s.setups))))


def run(context,config,seed=17,mode='replay-real-minutes'):
    return sim.sim_game_with_context(context,'interior_fixture',mode,seed,interior_experiment=config)


def events(result):return [e for t in result.team_lines for e in t['interior_experiment']['offense_attack_ledger']]


def frozen(name):
    spec=importlib.util.spec_from_loader('nba_gm_data._screen_reference_'+name,SourceFileLoader('nba_gm_data._screen_reference_'+name,str(REF/(name+'.py.reference'))))
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m


def prior_modules():return {f'nba_gm_data.{name}':frozen(name) for name in ('creation_passing','offense_response','interior_defense','shot_geometry')}


def frozen_config(config,modules):
    # Rebuild the frozen dataclasses, including nested configuration. Imports
    # use the frozen package map during execution; no shared changed resolver.
    defense=modules['nba_gm_data.interior_defense'];offense=modules['nba_gm_data.offense_response'];creation=modules['nba_gm_data.creation_passing']
    anchors=tuple(defense.Anchor(a.team_id,a.profile,a.context) for a in config.anchors)
    off=config.offense
    if off is not None:
        c=off.creation
        if c is not None:c=creation.CreationExperiment(**{f.name:getattr(c,f.name) for f in fields(creation.CreationExperiment)})
        off=offense.CombinedOffense(**({f.name:getattr(off,f.name) for f in fields(offense.CombinedOffense)}|{'creation':c}))
    return defense.InteriorExperiment(**({f.name:getattr(config,f.name) for f in fields(defense.InteriorExperiment)}|{'anchors':anchors,'offense':off}))


class ScreenMechanismTests(unittest.TestCase):
    def test_technique_and_body_tools_are_separate_contact_components(self):
        results={}
        for skill in (10,95):
            for mass in (75,135):
                _,x=screen_fixture(changes={'team_b_1':{'S27':skill,'P04':mass}})
                # Put intended screen exactly on the defender's path.
                x=call_change(x,screen_position=(1.43636,4.5),screener_start=(1.43636,4.5));d=draws();d[41]=1
                results[skill,mass]=phase(x,d)
        self.assertLess(results[95,75]['placement_error_m'],results[10,135]['placement_error_m'])
        self.assertGreater(results[95,75]['navigation_delay_s'],results[10,135]['navigation_delay_s'])
        self.assertGreater(results[95,135]['contact_hold_s'],results[95,75]['contact_hold_s'])
        # Height changes obstacle geometry; mass changes inertia, not technique.
        _,a=screen_fixture(changes={'team_b_1':{'P01':175}});_,b=screen_fixture(changes={'team_b_1':{'P01':220}})
        self.assertLess(phase(a)['obstacle_radius_m'],phase(b)['obstacle_radius_m'])
        self.assertEqual(phase(a)['placement_error_m'],phase(b)['placement_error_m'])

    def test_navigation_reduces_screen_delay_without_perfect_containment(self):
        _,a=screen_fixture(changes={'team_a_0':{'S35':5}});_,b=screen_fixture(changes={'team_a_0':{'S35':95}})
        low,high=phase(a),phase(b)
        self.assertGreater(low['navigation_delay_s'],high['navigation_delay_s'])
        self.assertEqual(low['guard_recognition_s'],high['guard_recognition_s'])
        x=action(a)['record']['containment'];y=action(b)['record']['containment']
        self.assertGreater(x['beat_probability'],y['beat_probability']);self.assertGreater(y['beat_probability'],.05)
        _,slow=screen_fixture(changes={'team_a_0':{'P07':1}});_,fast=screen_fixture(changes={'team_a_0':{'P07':4}})
        self.assertGreater(phase(slow)['guard_arrival_s'],phase(fast)['guard_arrival_s'])
        self.assertEqual(phase(slow)['navigation_detour_m'],phase(fast)['navigation_detour_m'])

    def test_anticipation_attention_and_action_read_are_not_physical_speed(self):
        _,a=screen_fixture(changes={'team_a_0':{'S41':10,'S44':10}});_,b=screen_fixture(changes={'team_a_0':{'S41':95,'S44':95}})
        self.assertGreater(phase(a)['guard_recognition_s'],phase(b)['guard_recognition_s'])
        self.assertEqual(phase(a)['navigation_detour_m'],phase(b)['navigation_detour_m'])
        _,a=screen_fixture(route='slip',changes={'team_b_1':{'S28':5}});_,b=screen_fixture(route='slip',changes={'team_b_1':{'S28':95}})
        d=draws();d[40]=.5
        low,high=phase(a,d),phase(b,d)
        self.assertEqual(low['preferred'],high['preferred']);self.assertEqual(low['route'],'roll');self.assertEqual(high['route'],'slip')
        self.assertGreater(low['release_s'],high['release_s'])
        d[40]=0
        low,high=phase(a,d),phase(b,d)
        self.assertEqual(low['route'],high['route']);self.assertGreater(low['window_start_s'],high['window_start_s'])

    def test_slip_has_no_contact_screen_bonus_or_illegal_contact(self):
        results=[]
        for skill,mass in ((5,70),(95,140)):
            _,x=screen_fixture(route='slip',changes={'team_b_1':{'S27':skill,'S28':100,'P04':mass}});d=draws();d[42]=0
            results.append(phase(x,d))
        for r in results:
            self.assertEqual(r['route'],'slip');self.assertEqual(r['kind'],'screen')
            for key in ('contact_overlap','contact_hold_s','navigation_detour_m','navigation_delay_s','illegal_probability'):self.assertEqual(r[key],0)
        self.assertEqual(results[0]['guard_arrival_s'],results[1]['guard_arrival_s'])

    def test_preference_and_recognition_have_distinct_effects_and_pop_is_rejected(self):
        _,hold=screen_fixture(route='screen');_,roll=screen_fixture(route='roll');_,slip=screen_fixture(route='slip')
        self.assertEqual(phase(hold)['route'],'screen');self.assertEqual(phase(roll)['route'],'roll');self.assertEqual(phase(slip)['route'],'slip')
        self.assertNotIn('F03',action(hold)['record']['noticed_options'])
        with self.assertRaisesRegex(ValueError,'Pop routes deferred'):screen_fixture(changes={'team_b_1':{'T11':{'screen':0,'roll':0,'slip':0,'pop':1}}})

    def test_stay_can_deny_the_roll_but_show_has_a_physical_recovery_cost(self):
        _,stay=screen_fixture(route='slip',coverage='stay');_,show=screen_fixture(route='slip',coverage='show_then_recover')
        a,b=phase(stay),phase(show)
        self.assertLess(a['window_end_s'],a['attacker_clear_s']);self.assertGreater(b['window_end_s'],b['window_start_s'])
        self.assertNotIn('F03',action(stay)['record']['noticed_options']);self.assertIn('F03',action(show)['record']['noticed_options'])
        self.assertEqual(a['attacker_clear_s'],b['attacker_clear_s'])
        self.assertGreater(b['coverage_release_s'],a['coverage_release_s'])

    def test_screen_position_away_from_guard_path_cannot_create_contact_delay(self):
        _,x=screen_fixture();x=call_change(x,screen_position=(8,4.5),screener_start=(8,4.5))
        r=phase(x)
        self.assertEqual(r['contact_overlap'],0);self.assertEqual(r['navigation_delay_s'],0);self.assertEqual(r['illegal_probability'],0)

    def test_unarrived_screener_cannot_create_contact_or_an_illegal_contact_foul(self):
        _,x=screen_fixture(changes={'team_b_1':{'S27':10}});x=call_change(x,screener_start=(7,6));d=draws();d[42]=0
        r=phase(x,d);self.assertGreater(r['planned_contact_overlap'],0)
        self.assertEqual(r['contact_overlap'],0);self.assertEqual(r['navigation_delay_s'],0);self.assertEqual(r['illegal_probability'],0)
        self.assertEqual(r['kind'],'screen')

    def test_roll_window_and_moving_target_are_derived_from_actual_participants(self):
        _,x=screen_fixture(route='slip');s=action_state(x);p=s['screens']['profiles']['team_b_1'];r=phase(x)
        early=receiver_position(r,r['release_s'],p);late=receiver_position(r,r['receiver_route_end_s'],p)
        self.assertEqual(early,r['receiver_start']);self.assertNotEqual(early,late)
        _,faster=screen_fixture(route='slip',changes={'team_b_1':{'P05':8}})
        self.assertLess(phase(faster)['window_start_s'],r['window_start_s'])
        a=action(families(x,('F03',)))
        self.assertEqual(a['kind'],'shot');self.assertIn('moving_receiver_error_m',a['record']['pass'])
        self.assertIn('receiver_defender_at_catch_m',a['record']);self.assertIn('contest_defender_id',a['plan'])
        self.assertEqual(a['plan']['contest_defender_id'],'team_a_1')

    def test_recovering_roller_defender_can_contest_without_being_the_helper(self):
        # Explicit late-creator boundary gives the recovering long defender
        # time to enter reach; these grades are controls, not player estimates.
        _,x=screen_fixture(route='slip',changes={'team_b_0':{'S16':0,'S19':0,'S20':0,'F03.execution':95},'team_a_1':{'P03':290,'P10':60,'P07':4,'S40':95}})
        r=action(families(x,('F03',)));self.assertEqual(r['kind'],'shot')
        self.assertEqual(r['plan']['contest_defender_id'],'team_a_1')
        self.assertGreater(r['plan']['response']['block_probability'],0)
        self.assertGreater(r['plan']['response']['conversion_reduction'],0)
        self.assertIn('never summed',r['plan']['details']['contest_policy'])

    def test_derived_window_expiry_prevents_a_finish_after_sampled_catch_delay(self):
        _,x=screen_fixture(route='slip',changes={'team_b_0':{'S16':50,'S19':50,'F03.execution':100},'team_a_1':{'P07':4}})
        x=families(x,('F03',));d=draws();d[34]=.8
        r=action(x,d)
        self.assertIn(r['kind'],('shot','turnover'))
        if r['kind']=='turnover':self.assertIn(r['outcome'],('inaccurate_delivery','late_delivery'))
        # Force an accurate placement with an incompatible catch delay through
        # the actual receiving gate, rather than manufacturing an FGA.
        with patch('nba_gm_data.creation_passing.sample_delivery',return_value={'accurate':True,'error_m':0,'quality':1,'catch_delay_s':5}):r=action(x)
        self.assertEqual(r['outcome'],'late_delivery');self.assertNotIn('plan',r);self.assertIsNone(r['steal_by'])

    def test_gifted_screen_and_roll_controls_do_not_affect_the_new_route(self):
        c,x=screen_fixture(route='slip');x=families(x,('F03','F04'));spec=x.offense.creation
        y=replace(x,offense=replace(x.offense,creation=replace(spec,setups=tuple(replace(s,screen_separation_m=9,roll_window_s=.01,roll_x_m=9,roll_y_m=8,receiver_defender_gap_m=9) for s in spec.setups))))
        a,b=run(c,x),run(c,y)
        self.assertEqual(a.player_lines,b.player_lines)
        self.assertEqual([t['interior_experiment']['offense_attack_ledger'] for t in a.team_lines],[t['interior_experiment']['offense_attack_ledger'] for t in b.team_lines])

    def test_no_call_and_continuation_have_no_gifted_screen_or_roller(self):
        _,x=screen_fixture();spec=x.offense.creation
        y=replace(x,offense=replace(x.offense,creation=replace(spec,screens=replace(spec.screens,calls=()))))
        for r in (action(y),action(x,allowed=False)):
            self.assertEqual(r['record']['screen_action']['kind'],'none')
            self.assertFalse({'F03','F04'}&set(r['record']['noticed_options']))
            d=draws();d[25]=.999
        r=action(x,d,allowed=False);self.assertNotIn('finish',r['record']['available_choices'])

    def test_screen_geometry_is_court_side_symmetric(self):
        _,x=screen_fixture();base=phase(x);spec=x.offense.creation.screens
        mirror=lambda p:(-p[0],p[1])
        calls=tuple(replace(c,**{key:mirror(getattr(c,key)) for key in ('creator_start','screener_start','screen_position','guard_start','screener_defender_start','roll_end')}) for c in spec.calls)
        setups=tuple(replace(s,drive_x_m=-s.drive_x_m) for s in x.offense.creation.setups)
        y=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,setups=setups,screens=replace(spec,calls=calls))))
        d=draws();d[41]=.9;a,b=phase(x,d),phase(y,d)
        for key in ('attacker_clear_s','guard_arrival_s','navigation_delay_s','window_start_s','window_end_s','illegal_probability'):self.assertAlmostEqual(a[key],b[key])
        self.assertEqual(mirror(a['placement_m']),b['placement_m'])


class ScreenKernelTests(unittest.TestCase):
    def test_short_game_recovery_contests_reach_the_actual_shot_kernel(self):
        controls={f'{team}_{i}':{'S16':0,'S19':0,'S20':0,'F03.execution':95,'P03':290,'P10':60,'P07':4,'S40':95,'T15':0} for team in ('team_a','team_b') for i in range(5)}
        c,x=screen_fixture(route='slip',changes=controls);r=run(c,families(x,('F03',)))
        contested=[e for e in events(r) if e.get('contest_defender_id') and e.get('contest_defender_id')==e['creation_chain']['screen_action'].get('roller_defender_id') and e['coupled_opportunity']['defense_response']['coverage_available']>0]
        self.assertTrue(contested)
        for e in contested:self.assertEqual(e['contest_defender_id'],e['creation_chain']['screen_action']['roller_defender_id'])
        validate_accounting(r)

    def test_research_packet_keeps_sparse_sources_separate_from_fixture_assumptions(self):
        path=ROOT/'docs/ratings-evidence-2026-10-29/SCREEN_NAVIGATION_INPUTS_2026_11_13.json'
        if not path.exists():self.skipTest('Independent research packet not delivered')
        raw=path.read_bytes();packet=json.loads(raw);validate_input_section(packet['player_input_section'])
        self.assertEqual(sum(v['status']=='unknown' for d in packet['player_input_section']['players'].values() for v in d['inputs'].values()),949)
        for scenario in packet['scenarios']:validate_input_section(scenario['input_section'])
        for doc in packet['player_input_section']['players'].values():
            self.assertEqual(len(doc['inputs']),94)
            with self.assertRaises(ValueError):compile_screen(PlayerInputs(doc))
        self.assertEqual(raw,path.read_bytes())

    def test_short_seeded_combined_games_execute_roll_slip_and_existing_chains(self):
        routes=set();choices=set();losses=set()
        for route in ('roll','slip','screen'):
            c,x=screen_fixture(route=route,changes={'team_b_1':{'S28':95}})
            for seed in (17,29):
                r=run(c,x,seed);validate_accounting(r)
                for e in events(r):
                    s=e['creation_chain']['screen_action'];routes.add(s.get('route'));choices.add(e['creation_chain'].get('choice'));losses.add(e['outcome'])
                    if e['continuation']>0:self.assertEqual(s['kind'],'none')
                    if e.get('contest_defender_id') and e['outcome']=='block':self.assertEqual(e['block_by'],e['contest_defender_id'])
        self.assertTrue({'roll','slip','screen'}<=routes);self.assertTrue({'finish','reset','F03','F04','F06'}<=choices)
        self.assertTrue({'failed_catch','handling_loss','inaccurate_delivery','made_fg','shooting_foul'}<=losses)

    def test_illegal_screen_is_one_offensive_foul_and_loss_without_ft_or_steal(self):
        c,x=screen_fixture(changes={'team_b_1':{'S27':10}})
        x=call_change(x,screener_start=(1.4,5.0));d=draws();d[42]=0
        r=action(x,d);self.assertEqual(r['outcome'],'illegal_screen');self.assertEqual(r['responsible'],'team_b_1');self.assertIsNone(r['steal_by'])
        # Force the same actual illegal-screen resolver branch in seeded games.
        original=resolve_drive
        def force(state,pid,tid,opp,d,remaining,**kwargs):
            d=list(d);d[42]=0
            return original(state,pid,tid,opp,d,remaining,**kwargs)
        with patch('nba_gm_data.creation_passing.resolve_drive',side_effect=force):result=run(c,x)
        illegal=[e for e in events(result) if e['outcome']=='illegal_screen'];self.assertTrue(illegal)
        for e in illegal:
            self.assertEqual(e['turnover_by'],e['offensive_foul_by']);self.assertNotIn('fta',e);self.assertNotIn('steal_by',e)
        for p in result.player_lines:
            self.assertEqual(p['personal_fouls'],sum(e.get('offensive_foul_by')==p['player_id'] or e.get('foul_by')==p['player_id'] for e in events(result)))

    def test_spacing_help_and_passing_are_combined_with_the_same_screen_chain(self):
        rows=[]
        for willing,commit in ((.05,0),(.05,1),(.95,1)):
            c,x=screen_fixture(route='slip',changes={'team_b_4':{'T01':willing},'team_a_4':{'T15':commit,'S38':95,'S44':95,'P05':8}})
            r=run(c,x);validate_accounting(r);rows.append(r)
        self.assertNotEqual(rows[0].player_lines,rows[1].player_lines)
        self.assertNotEqual(rows[1].team_lines[0]['interior_experiment']['combined_offense']['anchor_position_m'],rows[2].team_lines[0]['interior_experiment']['combined_offense']['anchor_position_m'])
        c,weak=screen_fixture(route='slip',changes={'team_b_0':{'F03.execution':5,'F04.execution':5}})
        _,strong=screen_fixture(route='slip',changes={'team_b_0':{'F03.execution':95,'F04.execution':95}})
        a=action(families(weak,('F03',)));b=action(families(strong,('F03',)));self.assertEqual(a['record']['noticed_options'],b['record']['noticed_options'])
        self.assertLess(a['record']['pass']['accuracy_probability'],b['record']['pass']['accuracy_probability'])

    def test_missing_inputs_and_stale_or_unavailable_participants_rejected(self):
        _,x=screen_fixture();doc=x.offense.profiles[0].inputs.to_dict()
        for key in ('S27','S28','S35','P01','P04','P07','P08','T11'):
            d=deepcopy(doc);del d['inputs'][key]
            with self.assertRaises(ValueError):compile_screen(PlayerInputs(d))
        for change in ({'screener_id':'not_active'},{'screener_id':'team_a_1'},{'screener_id':'team_b_4'}):
            with self.assertRaises(ValueError):action_state(call_change(x,**change))
        spec=x.offense.creation.screens;p=spec.profiles[0];d=p.inputs.to_dict();d['inputs']['S27']['value']['grade']=1
        bad=replace(spec,profiles=(compile_screen(PlayerInputs(d)),)+spec.profiles[1:])
        y=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=bad)))
        with self.assertRaisesRegex(ValueError,'one authoritative'):action_state(y)
        with self.assertRaises(ValueError):ScreenCall('a','b',[0,1],(0,1),(0,1),(0,2),(0,2),(0,0))
        with self.assertRaises(ValueError):ScreenCoefficients(contact_hold_s=-1)

    def test_role_projection_does_not_impute_unused_skills_and_rejects_forged_state(self):
        _,x=screen_fixture();doc=x.offense.profiles[0].inputs.to_dict()
        for key in ('S27','S28','T11'):del doc['inputs'][key]
        nav=compile_screen(PlayerInputs(doc),roles=('navigator',))
        self.assertIsNone(nav.screen);self.assertIsNone(nav.read);self.assertEqual(nav.preferences,())
        with self.assertRaises(ValueError):compile_screen(PlayerInputs(doc),roles=('screener',))
        spec=x.offense.creation.screens;p=spec.profiles[0]
        forged=replace(spec,profiles=(replace(p,screen=.01),)+spec.profiles[1:])
        y=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=forged)))
        with self.assertRaisesRegex(ValueError,'Stale or mutated'):action_state(y)

    def test_bad_units_scales_and_zero_exposure_are_rejected(self):
        _,x=screen_fixture();doc=x.offense.profiles[0].inputs.to_dict()
        for key,field,value in (('P04','unit','cm'),('P01','protocol','unidentified'),('S27','scale','generic_grade')):
            d=deepcopy(doc)
            if key.startswith('P'):d['inputs'][key]['value']['measurements'][0][field]=value
            else:d['inputs'][key]['value'][field]=value
            with self.assertRaises(ValueError):compile_screen(PlayerInputs(d))
        # The prepared role participants must have positive active exposure.
        from nba_gm_data.creation_passing import prepare_creation
        from nba_gm_data.offense_response import prepare_coupled
        pools={tid:[{'player':{'id':p.player_id},'minutes':0 if p.player_id=='team_b_1' else 48} for p in x.offense.profiles if p.player_id.startswith(tid)] for tid in ('team_a','team_b')}
        anchors={tid:x.anchor(tid) for tid in pools};contexts={tid:a.context if a else None for tid,a in anchors.items()}
        coupled=prepare_coupled(x.offense,pools,anchors,contexts)
        with self.assertRaisesRegex(ValueError,'Unavailable'):prepare_creation(x.offense.creation,coupled,pools,anchors,contexts)
        _,missing_span=screen_fixture(changes={'team_a_1':{'P02':None}})
        with self.assertRaisesRegex(ValueError,'P02'):action_state(missing_span)

    def test_clock_expiry_does_not_count_a_screen_foul_after_the_clock(self):
        c,x=screen_fixture(possessions=8)
        def expire(state,pid,tid,opp,d,remaining,**kwargs):
            d=list(d)
            if tid=='team_b':d[42]=0
            r=resolve_drive(state,pid,tid,opp,d,remaining,**kwargs)
            if tid=='team_b':r['elapsed_s']=remaining+1
            return r
        with patch('nba_gm_data.creation_passing.resolve_drive',side_effect=expire):r=run(c,x)
        own=r.team_lines[1]['interior_experiment']['offense_attack_ledger']
        self.assertTrue(all(e['outcome']=='shot_clock_turnover' for e in own));self.assertEqual(r.team_lines[1]['turnovers'],r.possessions)
        self.assertTrue(all('offensive_foul_by' not in e and 'steal_by' not in e for e in own))

    def test_revisions_json_reconstruction_mutation_and_root_release(self):
        c,x=screen_fixture();a=run(c,x);doc=x.offense.profiles[0].inputs.to_dict();doc['inputs']['S27']['value']['grade']=0
        self.assertEqual(to_plain(a),to_plain(run(c,x)))
        y=call_change(x,coverage='stay');self.assertNotEqual(x.revision,y.revision);self.assertNotEqual(a.id,run(c,y).id)
        spec=x.offense.creation.screens
        y=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=replace(spec,coefficients=replace(spec.coefficients,contact_hold_s=.7)))))
        self.assertNotEqual(x.revision,y.revision)
        inputs=[PlayerInputs(json.loads(json.dumps(p.inputs.to_dict()))) for p in x.offense.profiles]
        creation=replace(x.offense.creation,profiles=tuple(compile_interaction(p) for p in inputs),screens=replace(spec,profiles=tuple(compile_screen(p) for p in inputs)))
        y=replace(x,offense=replace(x.offense,profiles=tuple(compile_offense(p) for p in inputs),creation=creation))
        self.assertEqual(to_plain(a),to_plain(run(c,y)))
        expected=to_plain(a);a.team_lines[0]['interior_experiment']['offense_attack_ledger'][0]['creation_chain']['screen_action']['route']='corrupt'
        self.assertEqual(expected,to_plain(run(c,x)))
        refs=[weakref.ref(y),weakref.ref(creation),weakref.ref(creation.screens),weakref.ref(a)];del y,creation,a
        self.assertTrue(all(r() is None for r in refs))

    def test_complete_prior_modes_match_frozen_modules_with_screens_off(self):
        modules=prior_modules()
        with patch.dict(sys.modules,modules):old_kernel=frozen('interior_game');old_sim=frozen('sim')
        self.assertIsNone(type(screen_fixture()[1].offense.creation).__dataclass_fields__['screens'].default)
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                c,x=screen_fixture();x=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=None)))
                for config in (None,replace(x,offense=None),replace(x,offense=replace(x.offense,creation=None)),x):
                    actual=run(c,config,seed,mode)
                    with patch.dict(sys.modules,modules):
                        if config is None:prior=old_sim.sim_game_with_context(c,'interior_fixture',mode,seed)
                        else:
                            a,b=c['canonical']['teams'];g=c['schedule'][0];pools=[sim.game_player_pool(c,'interior_fixture',t,mode,game_date=g['gameDate']) for t in (a,b)]
                            prior=old_kernel.simulate_interior_game(c['canonical'],g,a,b,*pools,mode,seed,frozen_config(config,modules))
                    self.assertEqual(to_plain(actual),to_plain(prior))


if __name__=='__main__':unittest.main()
