"""Synthetic controlled inputs; not estimates of unnamed or NBA players."""
from dataclasses import replace
from experiments.interior_defense.fixtures import scenario_document,estimate,game_fixture
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.interior_defense import SKILL_SCALE,compile_profile,Anchor,InteriorExperiment,ArrivalContext
from nba_gm_data.offense_response import compile_offense,CombinedOffense,Deployment


def offensive_document(pid,*,shooting=75,free_throw=75,willingness=.75,release=70,extension=70,layup=75,floater=70,dunk=75,aerial=70,receiving=80,contact=70,reach=270,jump=50):
    doc=scenario_document(pid,reach=reach,jump=jump)
    for i in range(1,16):
        value=shooting if i<=6 else free_throw if i==7 else release if i==8 else extension if i==9 else {10:layup,11:floater,12:dunk,13:aerial,14:receiving,15:contact}[i]
        doc['inputs'][f'S{i:02d}']=estimate({'grade':value,'scale':SKILL_SCALE})
    doc['inputs']['P02']=estimate({'measurements':[{'metric':'wingspan','value':220,'unit':'cm','protocol':'interior_scenario_reference_v1'}]})
    for key,probs in [('T01',{'shoot':willingness,'drive':1-willingness,'pass':0,'post':0,'reset':0}),('T02',{'rim':.40,'short_paint':.20,'perimeter':.40}),('T03',{'catch':.4,'pull_up':.3,'movement':.3})]:
        value={'reference_conditions':'synthetic available controlled opportunity','rows':[{'condition':'available_opportunity','probabilities':probs}]}
        if key=='T02':value['spatial_reference']='synthetic_rim_paint_perimeter_v1'
        doc['inputs'][key]=estimate(value)
    return doc


def combined_fixture(*,shooting=75,willingness=.75,poa=.5,anchor=True,finish_mix=(.40,.20,.20,.10,.10),offense_coefficients=None):
    context=game_fixture();profiles=[];places=[]
    for player in context['canonical']['players']:
        pid=player['id'];attacking=player['team_id']=='team_b'
        doc=offensive_document(pid,shooting=shooting if attacking else 70,willingness=willingness if attacking else .6,reach=290 if pid=='team_a_4' else 270,jump=60 if pid=='team_a_4' else 50)
        profiles.append(compile_offense(PlayerInputs(doc),**({'coefficients':offense_coefficients} if offense_coefficients else {})))
        index=int(pid[-1]);places.append(Deployment(pid,(-1 if index%2 else 1)*(2.0+index*.5),6.8))
    defender=compile_profile(next(p.inputs for p in profiles if p.player_id=='team_a_4'))
    offense=CombinedOffense(tuple(profiles),tuple(places),(('team_a','team_b_4'),),finish_mix=finish_mix)
    config=InteriorExperiment((Anchor('team_a',defender,ArrivalContext(poa_containment=poa)),) if anchor else (),
        ('team_b',) if anchor else ('team_a','team_b'),offense=offense)
    return context,config
