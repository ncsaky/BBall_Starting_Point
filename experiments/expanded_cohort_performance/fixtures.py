"""Role-specific counterfactual action contexts, never live roster forecasts."""
from nba_gm_data.creation_passing import (compile_interaction,DriveSetup,CreationExperiment,
    prepare_creation,CHOICE_POLICY,HELP_RESPONSE_POLICY)
from nba_gm_data.offense_response import compile_offense,Deployment,CombinedOffense,prepare_coupled
from nba_gm_data.interior_defense import compile_profile,Anchor,ArrivalContext,InteriorExperiment
from nba_gm_data.screen_navigation import compile_screen,ScreenCall,ScreenExperiment
from .pool import IDS


def fixture(pool,*,creator='brunson',receiver='curry',partner='jokic',poa='barnes',helper='wemb',other='turner',
            families=('F06',),screen=None,help_available=1,start=None,ball=(.8,1.5),
            screen_separation=0,roll_window=2.5,possessions=16,creator_start=(2,5.5)):
    """Each scene explicitly supplies opportunity/assignments and a central actor.

    partner is the roll receiver only when that supplied route is enabled.
    A screen uses partner as screener and other as its distinct coverage defender.
    helper=None is a documented no-helper context; other actors keep their role.
    """
    # Resolve active module classes for authenticated reference construction.
    from nba_gm_data.creation_passing import compile_interaction,DriveSetup,CreationExperiment,prepare_creation
    from nba_gm_data.offense_response import compile_offense,Deployment,CombinedOffense,prepare_coupled
    from nba_gm_data.interior_defense import compile_profile,Anchor,ArrivalContext,InteriorExperiment
    from nba_gm_data.screen_navigation import compile_screen,ScreenCall,ScreenExperiment
    defender_receiver=helper or 'brunson'
    aliases=(creator,receiver,partner,poa,defender_receiver,other);ids=tuple(IDS.get(a,a) for a in aliases)
    if len(set(ids))!=6:raise ValueError('Six distinct actors/assignments required')
    views=[pool['views'][pid] for pid in ids]
    profiles=tuple(compile_offense(v) for v in views);interactions=tuple(compile_interaction(v) for v in views)
    setups=[]
    for index,pid in enumerate(ids):
        j=index%3;own=ids[:3] if index<3 else ids[3:];opponent=ids[j+3] if index<3 else ids[j]
        setups.append(DriveSetup(pid,opponent,own[(j+1)%3],own[(j+2)%3],
            screen_separation_m=screen_separation,drive_x_m=ball[0],drive_y_m=ball[1],roll_x_m=.6,roll_y_m=.8,
            roll_window_s=roll_window,enabled_pass_families=tuple(families)))
    screens=None
    if screen:
        required=((ids[2],'screener'),(ids[3],'navigator'),(ids[5],'coverage'))
        if any(role not in pool['roles'][pid]['screens'] for pid,role in required):raise ValueError('Requested screen role is unsupported by frozen operational packet; no forced replacement')
        screen_profiles=tuple(compile_screen(pool['views'][pid],roles=(role,)) for pid,role in required)
        call=ScreenCall(ids[0],ids[2],creator_start,(1.4,4.5),(1.4,4.5),(1.5,4.8),(.8,2.8),(.6,1),screen)
        screens=ScreenExperiment(screen_profiles,(call,))
    creation=CreationExperiment(interactions,tuple(setups),screens=screens,help_response_policy=HELP_RESPONSE_POLICY,choice_policy=CHOICE_POLICY)
    offense=CombinedOffense(profiles,tuple(Deployment(pid,3,6.8) for pid in ids),
        (('response_b',ids[1]),) if helper else (),creation=creation)
    if helper:
        if not pool['roles'][ids[4]]['interior']:raise ValueError('No completed interior role for requested helper')
        anchors=(Anchor('response_b',compile_profile(pool['views'][ids[4]]),ArrivalContext(anchor_available=help_available)),)
    else:anchors=()
    config=InteriorExperiment(anchors,('response_a',) if helper else ('response_a','response_b'),possessions=possessions,offense=offense)
    teams=[{'id':tid,'abbrev':str(i),'name':'Counterfactual expanded action pod '+str(i)} for i,tid in enumerate(('response_a','response_b'))]
    players=[{'id':pid,'name':aliases[i],'team_id':teams[i//3]['id'],'position':('PG','SG','C')[i%3],
        'minutes_projection':48,'age':27,'height_inches':78,'weight_lbs':220,'wingspan_inches':82,'rotation_priority':'starter'} for i,pid in enumerate(ids)]
    canonical={'teams':teams,'players':players,'traits':[],'staff_profiles':[],'_allow_internal_caches':True}
    game={'externalGameId':'expanded_fixture','gameDate':'2026-11-15','homeTeamId':'1','awayTeamId':'2'}
    context={'canonical':canonical,'schedule':[game],'boxscores':[],'real_minutes':{},'manifestos':{},'odds':{},'sim_cache':{},
        'indices':{'schedule_by_game_id':{'expanded_fixture':game},'teams_by_espn_id':{'1':teams[0],'2':teams[1]}}}
    pools={tid:[{'player':p,'minutes':48} for p in players if p['team_id']==tid] for tid in ('response_a','response_b')}
    anchor_map={tid:config.anchor(tid) for tid in pools};contexts={tid:a.context if a else None for tid,a in anchor_map.items()}
    coupled=prepare_coupled(offense,pools,anchor_map,contexts)
    state=prepare_creation(creation,coupled,pools,anchor_map,contexts)
    if start is not None:state['coupled']['positions']['response_b']=start
    state['audit_context']={'ids':ids,'aliases':aliases,'central_creator':creator,'screen':screen,'families':families,
        'helper':helper,'role_policy':'supplied opportunity/assignments; not complete player value or live roster',
        'missing_mechanisms':['post establishment/F08','pop','off-ball route generation','full workload/role system'],
        'input_scenario':pool['scenario'],'overrides':pool['overrides']}
    return state,context,config
