"""Pinned milestone-7 inputs and explicit synthetic coupled action contrasts."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path

from nba_gm_data.experimental_inputs import InterpretedInputs
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.creation_passing import CHOICE_POLICY,HELP_RESPONSE_POLICY
from experiments.player_input_pilot.pilot import build_pilot
from experiments.pilot_response_calibration.overlay import apply_overlay
from experiments.pilot_response_calibration.fixtures import fixture

ROOT=Path(__file__).resolve().parents[2]
REFERENCE=ROOT/'output/action-choice-consistency-2026-11-14/reference'
PIN='2ea987d06cabd45ce370fd6b35426bab28d8808938f564d7b9579788fa297a63'


def pinned_pilot():return apply_overlay(build_pilot(),REFERENCE/'targeted-input-overlay.json',PIN)[0]


def prepare(context,config,start):
    from nba_gm_data.offense_response import prepare_coupled
    from nba_gm_data.creation_passing import prepare_creation
    pools={t['id']:[{'player':p,'minutes':48} for p in context['canonical']['players'] if p['team_id']==t['id']] for t in context['canonical']['teams']}
    anchors={tid:config.anchor(tid) for tid in pools};contexts={tid:a.context if a else None for tid,a in anchors.items()}
    coupled=prepare_coupled(config.offense,pools,anchors,contexts)
    state=prepare_creation(config.offense.creation,coupled,pools,anchors,contexts)
    if start is not None:state['coupled']['positions']['response_b']=start
    return state


def make_case(pilot,*,consistent=True,changes=None,finish_mix=None,remaining=24,gap=None,roll_window=None,**kwargs):
    from nba_gm_data.creation_passing import compile_interaction
    from nba_gm_data.offense_response import compile_offense
    from nba_gm_data.interior_defense import compile_profile
    from nba_gm_data.screen_navigation import compile_screen
    kwargs={'policy':HELP_RESPONSE_POLICY,**kwargs}
    initial,context,config=fixture(pilot,**kwargs);ids=initial['audit_context']['ids']
    role_ids=dict(zip(('creator','shooter','roller','guard','helper','coverage'),ids,strict=True))
    views={p.player_id:p.inputs for p in config.offense.profiles};ledger=[]
    for role,fields in (changes or {}).items():
        pid=role_ids.get(role,role);doc=views[pid].to_dict()
        for key,value in fields.items():
            before=deepcopy(doc['inputs'][key]);row=doc['inputs'][key]
            if key.startswith(('S','F')):row['value']['grade']=value
            elif key in ('T07','T15'):row['value']['probability']=value
            elif key=='T11':row['value']['rows'][0]['probabilities']=value
            elif key.startswith('P'):
                for measurement in row['value']['measurements']:measurement['value']=value
            else:raise ValueError('Unsupported explicit synthetic contrast')
            ledger.append({'role':role,'player_id':pid,'design_id':key,'before':before,'after':deepcopy(row),
                'origin':'declared synthetic mechanism contrast; not research/production evidence'})
        views[pid]=InterpretedInputs(PlayerInputs(doc),views[pid].contract)
    profiles=tuple(compile_offense(views[p.player_id],p.coefficients) for p in config.offense.profiles)
    creation=config.offense.creation
    interactions=tuple(compile_interaction(views[p.player_id]) for p in creation.profiles)
    setups=tuple(replace(s,**({'receiver_defender_gap_m':gap} if gap is not None else {}),
        **({'roll_window_s':roll_window} if roll_window is not None else {})) for s in creation.setups)
    screens=creation.screens
    if screens:screens=replace(screens,profiles=tuple(compile_screen(views[p.player_id],roles=p.roles) for p in screens.profiles))
    creation=replace(creation,profiles=interactions,setups=setups,screens=screens,
        **({'choice_policy':CHOICE_POLICY} if consistent else {}))
    offense=replace(config.offense,profiles=profiles,creation=creation,**({'finish_mix':finish_mix} if finish_mix is not None else {}))
    config=replace(config,offense=offense,anchors=tuple(replace(a,profile=compile_profile(views[a.profile.inputs.player_id],a.profile.coefficients)) for a in config.anchors))
    state=prepare(context,config,kwargs.get('start',(2,1)))
    state['audit_context']={**initial['audit_context'],'control_overrides':ledger,'clock_s':remaining,'consistent_choice_policy':consistent}
    return state,context,config


def observed_draws():
    d=[.5]*48
    for key in (25,26,27,28,29,30,31,40):d[key]=0
    d[24]=.999;d[32]=.999;d[33]=0;d[39]=.5;d[41]=.5;d[42]=.999
    return d


def decision(state,remaining=24,draws=None):
    from nba_gm_data.creation_passing import prepare_drive_decision
    pid=state['audit_context']['ids'][0]
    result=prepare_drive_decision(state,pid,'response_a','response_b',observed_draws() if draws is None else draws,remaining)
    if 'kind' in result:raise ValueError('Conditional fixture terminated before its decision')
    return result
