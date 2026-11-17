"""Matched conditional contexts; synthetic controls are never player estimates."""
from copy import deepcopy
from dataclasses import replace
import math

from nba_gm_data.experimental_inputs import InterpretedInputs
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.creation_passing import (compile_interaction,CreationExperiment,
    CreationCoefficients,DriveSetup,prepare_creation,helper_response)
from nba_gm_data.offense_response import compile_offense,CombinedOffense,Deployment,prepare_coupled
from nba_gm_data.interior_defense import compile_profile,InteriorExperiment,Anchor,ArrivalContext
from nba_gm_data.screen_navigation import compile_screen,ScreenExperiment,ScreenCall
from experiments.screen_navigation.fixtures import screen_fixture
from experiments.player_input_pilot.pilot import IDS,BASE,INTERIOR


def fixture(pilot,alias='white',*,role='helper',policy='legacy_timely_v1',window=1.1,
            start=(2,1),families=('F06',),available=1,commitment=None,
            shooter_grade=70,shoot_probability=.45,finish_grade=70,coverage=None,
            possessions=16):
    """Counterfactual 3v3, one separate helper, matched primary/receiver defenders.

    Named actors keep their IDs and authoritative interpreted snapshot. Additional
    C27 dependencies for White/Castle are explicit common scenario completions,
    not evidence about their interior skill. All other actors are synthetic.
    """
    # Resolve the active module map so authenticated old-engine runs construct
    # the old ScreenExperiment class rather than mixing class identities.
    from nba_gm_data.creation_passing import compile_interaction,CreationExperiment,DriveSetup,prepare_creation
    from nba_gm_data.offense_response import compile_offense,CombinedOffense,Deployment,prepare_coupled
    from nba_gm_data.interior_defense import compile_profile,InteriorExperiment,Anchor,ArrivalContext
    from nba_gm_data.screen_navigation import compile_screen,ScreenExperiment,ScreenCall
    _,native=screen_fixture(possessions=2)
    template=native.offense.profiles[0].inputs.to_dict()
    ids=['response_creator','response_shooter','response_roller',
         'response_guard','response_helper','response_coverage']
    named_index={'helper':4,'poa':3}[role];ids[named_index]=IDS[alias]
    docs={};completions=[]
    for index,pid in enumerate(ids):
        doc=pilot['views'][pid].to_dict() if index==named_index else deepcopy(template)
        doc['player_id']=pid
        # Full offense/interaction controls plus only the helper's actual C27 role.
        needed=BASE | (INTERIOR if index==4 else set())
        for key in sorted(needed):
            if doc['inputs'][key]['status']=='unknown':
                original=deepcopy(doc['inputs'][key]);doc['inputs'][key]=deepcopy(template['inputs'][key])
                completions.append({'actor':pid,'design_id':key,'original_record':original,
                    'operational_record':deepcopy(doc['inputs'][key]),'origin':'matched synthetic role control; not player evidence'})
        if index==0:
            # Set a declared synthetic approach duration through dimensional
            # acceleration; do not replace a named athlete's movement input.
            clear=window-.25*(1-doc['inputs']['S20']['value']['grade']/100)
            craft=1+.35*(1-doc['inputs']['S16']['value']['grade']/100)+.25*(1-doc['inputs']['S19']['value']['grade']/100)
            acceleration=1.8/(clear/craft)**2
            for m in doc['inputs']['P05']['value']['measurements']:m['value']=acceleration
            for key in ('S10','S11','S12','S13'):doc['inputs'][key]['value']['grade']=finish_grade
        if index==1:
            doc['inputs']['S01']['value']['grade']=shooter_grade
            doc['inputs']['T01']['value']['rows'][0]['probabilities']={'shoot':shoot_probability,'drive':1-shoot_probability,'pass':0,'post':0,'reset':0}
        if index==4 and commitment is not None:doc['inputs']['T15']['value']['probability']=commitment
        docs[pid]=doc
    views={pid:InterpretedInputs(PlayerInputs(doc),pilot['contract']) for pid,doc in docs.items()}
    offense=tuple(compile_offense(views[pid]) for pid in ids)
    interactions=tuple(compile_interaction(views[pid]) for pid in ids)
    setups=[]
    for index,pid in enumerate(ids):
        j=index%3;opposing=j+3 if index<3 else j
        own=ids[:3] if index<3 else ids[3:]
        kick=own[(j+1)%3];roller=own[(j+2)%3]
        setups.append(DriveSetup(pid,ids[opposing],kick,roller,screen_separation_m=0,
            drive_x_m=.8,drive_y_m=1.5,roll_x_m=.6,roll_y_m=.8,enabled_pass_families=families))
    spec=CreationExperiment(interactions,tuple(setups))
    if policy!='legacy_timely_v1':spec=replace(spec,help_response_policy=policy)
    if coverage:
        screen_profiles=tuple(compile_screen(views[ids[j]],roles=roles) for j,roles in
            ((2,('screener',)),(3,('navigator',)),(5,('coverage',))))
        call=ScreenCall(ids[0],ids[2],(2,5.5),(1.4,4.5),(1.4,4.5),(1.5,4.8),(.8,2.8),(.6,1),coverage)
        spec=replace(spec,screens=ScreenExperiment(screen_profiles,(call,)))
    dep=tuple(Deployment(pid,3,6.8) for pid in ids)
    off=CombinedOffense(offense,dep,(('response_b',ids[1]),),creation=spec)
    anchor=Anchor('response_b',compile_profile(views[ids[4]]),ArrivalContext(anchor_available=available))
    config=InteriorExperiment((anchor,),('response_a',),possessions=possessions,offense=off)
    pools={tid:[{'player':{'id':pid},'minutes':48} for pid in ids[3*k:3*k+3]] for k,tid in enumerate(('response_a','response_b'))}
    anchors={'response_a':None,'response_b':anchor};contexts={'response_a':None,'response_b':anchor.context}
    coupled=prepare_coupled(off,pools,anchors,contexts)
    state=prepare_creation(spec,coupled,pools,anchors,contexts)
    automatic_start=state['coupled']['positions']['response_b']
    if start is not None:state['coupled']['positions']['response_b']=start
    state['audit_context']={'alias':alias,'role':role,'ids':ids,'window_control_s':window,
        'helper_start_policy':'explicit matched coordinates' if start is not None else 'derived shooting/spacing assignment',
        'automatic_start_m':automatic_start,'extra_role_completions':completions,'source_records_unchanged':True}
    # Minimal standalone context for the same shared kernel, never a live roster.
    teams=[{'id':tid,'abbrev':str(k),'name':'Counterfactual response control '+str(k)} for k,tid in enumerate(pools)]
    players=[{'id':pid,'name':alias if pid==IDS[alias] else pid,'team_id':teams[index//3]['id'],
        'position':('PG','SG','C')[index%3],'minutes_projection':48,'age':27,'height_inches':78,
        'weight_lbs':220,'wingspan_inches':82,'rotation_priority':'starter'} for index,pid in enumerate(ids)]
    canonical={'teams':teams,'players':players,'traits':[],'staff_profiles':[],'_allow_internal_caches':True}
    game={'externalGameId':'response_fixture','gameDate':'2026-11-14','homeTeamId':'1','awayTeamId':'2'}
    context={'canonical':canonical,'schedule':[game],'boxscores':[],'real_minutes':{},'manifestos':{},'odds':{},'sim_cache':{},
        'indices':{'schedule_by_game_id':{'response_fixture':game},'teams_by_espn_id':{'1':teams[0],'2':teams[1]}}}
    return state,context,config


def boundary_start(state,delta,angle=0):
    """Solve using the actual helper movement function, including capped speed."""
    from nba_gm_data.creation_passing import containment_response
    pid=state['audit_context']['ids'][0];s=state['setups'][pid]
    a=state['profiles'][pid];h=state['profiles'][state['audit_context']['ids'][4]]
    drive=containment_response(a,state['profiles'][s.defender_id],s,state['spec'].coefficients)
    elapsed=drive['attacker_clear_s']+state['spec'].coefficients.decision_delay_s*(1-a.skill('S20'))
    ball=(s.drive_x_m,s.drive_y_m);lo,hi=0.0,20.0
    def at(radius):return (ball[0]+radius*math.cos(angle),ball[1]+radius*math.sin(angle))
    for _ in range(60):
        mid=(lo+hi)/2
        if helper_response(h,at(mid),ball,elapsed,0,0)['arrival_s']<elapsed+delta:lo=mid
        else:hi=mid
    state['coupled']['positions']['response_b']=at((lo+hi)/2)
    return elapsed


def fixed_draws(choice=0):
    d=[.0]*48;d[24]=.999;d[32]=.999;d[33]=choice
    return d
