"""Source-independent synthetic on-ball screen participants and coaching calls."""
from dataclasses import replace
from experiments.creation_passing.fixtures import creation_fixture
from experiments.interior_defense.fixtures import estimate
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.interior_defense import SKILL_SCALE,compile_profile
from nba_gm_data.offense_response import compile_offense
from nba_gm_data.creation_passing import compile_interaction
from nba_gm_data.screen_navigation import compile_screen,ScreenExperiment,ScreenCall


def screen_fixture(*,changes=None,route='roll',coverage='show_then_recover',possessions=16,call_all=True):
    context,config=creation_fixture(possessions=possessions);profiles=[];interactions=[];screens=[]
    changes=changes or {}
    for p in config.offense.profiles:
        doc=p.inputs.to_dict();pid=p.player_id
        for key in ('S27','S28','S35'):doc['inputs'][key]=estimate({'grade':75,'scale':SKILL_SCALE},method='explicit screen/navigation synthetic role control')
        for key,metric,val,unit in [('P01','height',200,'cm'),('P04','body_mass',100,'kg')]:
            doc['inputs'][key]=estimate({'measurements':[{'metric':metric,'value':val,'unit':unit,'protocol':'interior_scenario_reference_v1'}]},method='synthetic dimensional screen fixture; no athlete measurement')
        mix={'screen':0,'roll':1 if route=='roll' else 0,'slip':1 if route=='slip' else 0,'pop':0}
        if route=='screen':mix['screen']=1
        doc['inputs']['T11']=estimate({'reference_conditions':'synthetic called on-ball screen','rows':[{'condition':'on_ball_screen','probabilities':mix}]})
        for key,value in changes.get(pid,{}).items():
            if value is None:del doc['inputs'][key]
            elif key.startswith('S') or key.startswith('F'):doc['inputs'][key]['value']['grade']=value
            elif key=='T11':doc['inputs'][key]['value']['rows'][0]['probabilities']=value
            elif key=='T01':doc['inputs'][key]['value']['rows'][0]['probabilities']={'shoot':value,'drive':1-value,'pass':0,'post':0,'reset':0}
            elif key.startswith('T'):doc['inputs'][key]['value']['probability']=value
            elif key in ('P08','P09'):doc['inputs'][key]['value']['display_grade']['grade']=value
            else:doc['inputs'][key]['value']['measurements'][0]['value']=value
        inputs=PlayerInputs(doc);profiles.append(compile_offense(inputs));interactions.append(compile_interaction(inputs));screens.append(compile_screen(inputs))
    calls=[]
    for setup in config.offense.creation.setups:
        if not call_all and setup.creator_id!='team_b_0':continue
        sign=-1 if int(setup.creator_id[-1])%2 else 1
        # Placement is near the guard's line to the supplied drive destination.
        calls.append(ScreenCall(setup.creator_id,setup.roller_id,(sign*2,5.5),(sign*1.4,4.5),(sign*1.4,4.5),
            (sign*1.5,4.8),(sign*.8,2.8),(sign*.6,1.0),coverage))
    creation=replace(config.offense.creation,profiles=tuple(interactions),screens=ScreenExperiment(tuple(screens),tuple(calls)))
    offense=replace(config.offense,profiles=tuple(profiles),creation=creation)
    anchors=tuple(replace(a,profile=compile_profile(next(p.inputs for p in profiles if p.player_id==a.profile.inputs.player_id))) for a in config.anchors)
    return context,replace(config,offense=offense,anchors=anchors)
