"""Explicit synthetic scenarios and research sensitivity envelopes, never imports.

Unknown research fields stay unknown in the source packet. Completing a
scenario is a counterfactual assumption for a mechanism test, not a measured
player estimate. No function here writes a save or canonical player.
"""
from __future__ import annotations

from nba_gm_data.interior_defense import CAPACITY_SCALE, SKILL_SCALE, compile_profile
from nba_gm_data.player_model import INPUT_VERSION, PlayerInputs
from nba_gm_data.player_model_registry import REGISTRY_VERSION


def estimate(value,method='synthetic mechanism fixture; not a player estimate'):
    return {'status':'estimated','value':value,
        'evidence':[{'source':'interior-defense isolated experiment','method':method,'shared_evidence_id':'explicit_scenario_assumptions_v1'}],
        'uncertainty':{'confidence':'low','notes':'Assumption for controlled mechanism testing; not a measurement or production talent'}}


def scenario_document(player_id='fixture_anchor', *, positioning=75,technique=75,legal=75,reach=270,acceleration=4,strength=65,balance=65,jump=50,choices=(.55,.35,.10)):
    skills={key:estimate({'grade':grade,'scale':SKILL_SCALE}) for key,grade in [('S36',positioning),('S37',technique),('S45',legal)]}
    physical={key:estimate({'measurements':[{'metric':metric,'value':value,'unit':unit,'protocol':'interior_scenario_reference_v1'}]})
              for key,metric,value,unit in [('P03','standing_reach',reach,'cm'),('P05','acceleration',acceleration,'m/s2'),('P10','vertical_jump',jump,'cm')]}
    physical.update({key:estimate({'measurements':[],'display_grade':{'grade':grade,'scale':CAPACITY_SCALE}}) for key,grade in [('P08',strength),('P09',balance)]})
    tendency=estimate({'reference_conditions':'declared available interior contest, synthetic baseline choice',
        'rows':[{'condition':'available_interior_contest','probabilities':dict(zip(('jump','conservative_contest','stay_down'),choices,strict=True))}]})
    return {'version':INPUT_VERSION,'registry_version':REGISTRY_VERSION,'player_id':player_id,'inputs':{**skills,**physical,'T16':tendency}}


def scenario_profile(player_id='fixture_anchor',**kwargs):
    return compile_profile(PlayerInputs(scenario_document(player_id,**kwargs)))


def game_fixture():
    """Ten unnamed players, fixed full-game exposure; no league calibration."""
    teams=[{'id':'team_a','abbrev':'AAA','name':'Synthetic A'},{'id':'team_b','abbrev':'BBB','name':'Synthetic B'}]
    players=[{'id':f'{team["id"]}_{i}','name':f'Fixture {team["abbrev"]} {i}','team_id':team['id'],'position':('PG','SG','SF','PF','C')[i],
              'minutes_projection':48,'age':27,'height_inches':78,'weight_lbs':220,'wingspan_inches':82,'rotation_priority':'starter'} for team in teams for i in range(5)]
    keys=('defensive_effort','scheme_iq','screen_navigation','foot_speed_lateral_agility','rim_deterrence','shooting_range','shot_versatility',
          'handle_pressure','rim_pressure','passing_reads','portability','playoff_translation','offensive_rebounding','stamina_cardio','release_speed')
    c={'teams':teams,'players':players,'traits':[{'player_id':p['id'],'trait_key':key,'value':70} for p in players for key in keys],
       'staff_profiles':[],'_allow_internal_caches':True}
    game={'externalGameId':'interior_fixture','gameDate':'2026-11-13','homeTeamId':'1','awayTeamId':'2'}
    context={'canonical':c,'schedule':[game],'boxscores':[],'real_minutes':{},'manifestos':{},'odds':{},'sim_cache':{},
             'indices':{'schedule_by_game_id':{'interior_fixture':game},'teams_by_espn_id':{'1':teams[0],'2':teams[1]}}}
    return context
