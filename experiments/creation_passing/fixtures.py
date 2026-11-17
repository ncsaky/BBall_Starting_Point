"""Complete synthetic role fixtures; never fill unknown named-player fields."""
from dataclasses import replace
from experiments.offense_interior.fixtures import combined_fixture
from experiments.interior_defense.fixtures import estimate
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.interior_defense import SKILL_SCALE,compile_profile
from nba_gm_data.offense_response import compile_offense,prepare_coupled
from nba_gm_data.creation_passing import SKILLS,FAMILIES,compile_interaction,CreationExperiment,DriveSetup,prepare_creation


def creation_fixture(*,families=FAMILIES,possessions=12,changes=None):
    context,config=combined_fixture();profiles=[];interactions=[];setups=[]
    changes=changes or {}
    for old in config.offense.profiles:
        pid=old.player_id;doc=old.inputs.to_dict()
        for key in SKILLS:
            doc['inputs'][key]=estimate({'grade':70,'scale':SKILL_SCALE})
        for family in FAMILIES:
            for part in ('recognition','execution'):
                doc['inputs'][family+'.'+part]=estimate({'grade':70,'scale':SKILL_SCALE})
        for key,metric,value in [('P06','straight_line_speed',6),('P07','lateral_speed',2.5)]:
            doc['inputs'][key]=estimate({'measurements':[{'metric':metric,'value':value,'unit':'m/s','protocol':'interior_scenario_reference_v1'}]})
        for key,value in [('T07',.5),('T15',.75)]:
            doc['inputs'][key]=estimate({'probability':value,'reference_conditions':'synthetic matched opportunity'})
        for key,value in changes.get(pid,{}).items():
            if value is None:del doc['inputs'][key]
            elif key.startswith(('S','F')):doc['inputs'][key]['value']['grade']=value
            elif key=='T01':doc['inputs'][key]['value']['rows'][0]['probabilities']={'shoot':value,'drive':1-value,'pass':0,'post':0,'reset':0}
            elif key.startswith('T'):doc['inputs'][key]['value']['probability']=value
            else:doc['inputs'][key]['value']['measurements'][0]['value']=value
        inputs=PlayerInputs(doc);profiles.append(compile_offense(inputs));interactions.append(compile_interaction(inputs))
        team=pid[:-2];i=int(pid[-1]);other='team_b' if team=='team_a' else 'team_a'
        kick=(3 if i==1 else 1) if i%2 else (2 if i==4 else 4)
        roller=next(j for j in range(5) if j not in (i,kick))
        setups.append(DriveSetup(pid,f'{other}_{i}',f'{team}_{kick}',f'{team}_{roller}',drive_x_m=-.8 if i%2 else .8,
            roll_x_m=-.6 if i%2 else .6,enabled_pass_families=families))
    offense=replace(config.offense,profiles=tuple(profiles),creation=CreationExperiment(tuple(interactions),tuple(setups)))
    anchors=tuple(replace(a,profile=compile_profile(next(p.inputs for p in profiles if p.player_id==a.profile.inputs.player_id))) for a in config.anchors)
    return context,replace(config,anchors=anchors,offense=offense,possessions=possessions)


def action_state(config):
    pools={tid:[{'player':{'id':p.player_id},'minutes':48} for p in config.offense.profiles if p.player_id.startswith(tid)] for tid in ('team_a','team_b')}
    anchors={tid:config.anchor(tid) for tid in pools}
    contexts={tid:a.context if a else None for tid,a in anchors.items()}
    coupled=prepare_coupled(config.offense,pools,anchors,contexts)
    return prepare_creation(config.offense.creation,coupled,pools,anchors,contexts)
