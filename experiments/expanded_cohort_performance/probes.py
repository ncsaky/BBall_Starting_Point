"""Bounded, prespecified opportunity probes; no player ranking or outcome fitting."""
from collections import Counter
from dataclasses import asdict
import math
import random
import statistics

from nba_gm_data.creation_passing import resolve_drive,prepare_drive_decision
from nba_gm_data.action_choice import project_choices
from nba_gm_data.offense_response import ActionShotContext,plan_attack
from nba_gm_data.interior_game import shot_probabilities
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.action_choice_consistency.empirical import first_event
from .fixtures import fixture
from .pool import IDS,scenario


SCREEN=dict(creator='curry',receiver='white',partner='jokic',poa='castle',helper='barnes',other='wemb',
    families=('F03','F04','F06'),screen='show_then_recover',creator_start=(3,6))
LOB=dict(creator='jokic',receiver='curry',partner='wemb',poa='turner',helper='barnes',other='brunson',
    families=('F04',),screen_separation=.5,ball=(1.2,2.7))


def cases():
    """Fixed before outcomes; supplied scene assignments are not NBA lineups."""
    return [
        ('brunson_curry_outlet',{}),
        ('brunson_turner_outlet',dict(receiver='turner',other='curry')),
        ('curry_creator',dict(creator='curry',receiver='turner',other='brunson')),
        ('barnes_creator',dict(creator='barnes',poa='brunson')),
        ('jokic_supplied_lob',LOB),
        ('jokic_screen_show',SCREEN),
        ('jokic_screen_stay',{**SCREEN,'screen':'stay'}),
        ('jokic_screen_early',{**SCREEN,'creator_start':(2,5.5)}),
        ('turner_screen_coverage',{**SCREEN,'other':'turner'}),
        ('barnes_navigation',dict(creator='curry',receiver='turner',partner='jokic',poa='barnes',helper=None,other='wemb',screen='stay',families=('F03','F04','F06'))),
        ('castle_navigation',dict(creator='curry',receiver='turner',partner='jokic',poa='castle',helper=None,other='wemb',screen='stay',families=('F03','F04','F06'))),
        ('wemb_help',dict(poa='castle',helper='wemb',other='barnes',start=(1,1.5))),
        ('turner_help',dict(poa='castle',helper='turner',other='barnes',start=(1,1.5))),
        ('barnes_help',dict(poa='castle',helper='barnes',other='turner',start=(1,1.5))),
        ('wemb_late',dict(poa='castle',helper='wemb',other='barnes',start=(10,10))),
        ('wemb_unavailable',dict(poa='castle',helper='wemb',other='barnes',help_available=0)),
    ]


def conditional(state,*,route_draw=.5,remaining=24):
    draws=observed_draws();draws[39]=route_draw
    d=prepare_drive_decision(state,state['audit_context']['ids'][0],'response_a','response_b',draws,remaining)
    if 'kind' in d:return {'terminated':d}
    return {'record':d['record'],'projection':project_choices(d['frame'],d['options'])}


def sample(state,n=256,seeds=(17,29),remaining=24):
    choices=Counter();events=Counter();stages=Counter();routes=Counter();points=[];counts=Counter();responses=[]
    for seed in seeds:
        rng=random.Random(seed)
        for _ in range(n):
            draws=[rng.random() for _ in range(48)]
            action=resolve_drive(state,state['audit_context']['ids'][0],'response_a','response_b',draws,remaining)
            record=action['record'];outcome,value,_=first_event(action,draws,remaining)
            points.append(value);events[outcome]+=1;choices[record.get('choice','before_choice_loss')]+=1
            for key in ('noticed','committed','timely'):stages['help_'+key]+=bool(record.get('help',{}).get(key))
            stages['beat_defender']+=bool(record.get('beat_defender'))
            for key,value in record.get('noticed_options',{}).items():stages['noticed_'+key]+=bool(value)
            for key in record.get('available_choices',[]):stages['available_'+key]+=1
            routes[record.get('screen_action',{}).get('route',record.get('screen_action',{}).get('kind','no_screen'))]+=1
            for key in ('candidate_count','candidate_resolution_calls','shot_plan_evaluations','clock_boundary_evaluations'):
                counts[key]+=record.get('choice_projection',{}).get(key,0)
            response=action.get('plan',{}).get('response')
            if response is not None:responses.append({k:response[k] for k in ('coverage_available','conversion_reduction','block_probability','foul_probability')})
    total=len(points);mean=statistics.mean(points);se=statistics.stdev(points)/math.sqrt(total)
    return {'n':total,'seeds':list(seeds),'per_seed':n,'choices':dict(choices),'events':dict(events),'stages':dict(stages),
        'screen_routes':dict(routes),'mean_first_event_points':mean,'sampling95':[mean-1.96*se,mean+1.96*se],
        'projection_counts':dict(counts),'selected_response_count':len(responses),
        'selected_response_means':{k:statistics.mean(r[k] for r in responses) for k in responses[0]} if responses else {},
        'scope':'paired first-action opportunities; no reset/rebound continuation points or workload forecast'}


def run_case(pool,name,kwargs,n=256):
    state,_,_=fixture(pool,**kwargs)
    return {'name':name,'scenario':pool['scenario'],'assignments':state['audit_context'],'configuration':kwargs,
        'sample':sample(state,n), 'conditional_routes':{str(d):conditional(state,route_draw=d) for d in (.1,.5,.95)}}


def shooting(pool):
    """Same supplied distance/pressure/preparation geometry, not generated routes."""
    rows=[]
    for alias in ('curry','brunson','turner','barnes','wemb'):
        # Common partner/defender IDs; create one valid same-role scene per actor.
        kwargs=dict(creator=alias,receiver='white',partner='jokic',poa='castle',helper=None,other='wemb' if alias!='wemb' else 'turner')
        # helper=None assigns Brunson to White; Brunson creator needs a different sixth actor.
        if alias=='brunson':kwargs=dict(creator='curry',receiver='brunson',partner='jokic',poa='castle',helper='barnes',other='wemb')
        state,_,_=fixture(pool,**kwargs);coupled=state['coupled']
        for mode in ('catch','pull_up','movement'):
            action=ActionShotContext(shot_mode=mode,primary_pressure=.35,primary_arrival_s=.65,delivery_quality=.8,received_pass=mode!='pull_up')
            plan=plan_attack(coupled,IDS[alias],'perimeter',observed_draws(),'response_b',None,None,action_context=action)
            probabilities=shot_probabilities(plan['off'],None,'perimeter')
            rows.append({'actor':alias,'mode':mode,'probabilities':probabilities,'reception':plan['reception'],
                'first_event_EP':plan['reception']*(probabilities['foul']*3*plan['off']['ft_pct']+(1-probabilities['foul'])*(1-probabilities['block_given_no_foul'])*probabilities['make_given_unblocked']*3),
                'details':plan['details'],'context':asdict(action),'input_scenario':pool['scenario']})
    return rows


def alternatives(pool):
    """Declared independently of measured results; no Cartesian best/worst actors."""
    aliases=tuple(IDS)
    for label,values in [('slow',(2.5,5.5,2.2)),('fast',(3.5,6.5,2.8))]:
        changes={a:dict(zip(('P05','P06','P07'),values)) for a in aliases}
        yield scenario(pool,'common_motion_'+label,changes),('wemb_help','turner_help','jokic_screen_show')
    for delta in (-10,10):
        changes={a:{'P03':pool['views'][IDS[a]].to_dict()['inputs']['P03']['value']['measurements'][0]['value']+delta} for a in aliases}
        yield scenario(pool,'H1_reach_'+str(delta),changes),('wemb_help','turner_help','barnes_help')
    for jump in (25,55):
        yield scenario(pool,'common_jump_'+str(jump),{a:{'P10':jump} for a in aliases}),('wemb_help','turner_help','barnes_help')
    for label,values in [('lower',(.35,.55)),('higher',(.65,.75))]:
        yield scenario(pool,'common_capacity_'+label,{a:dict(zip(('P08','P09'),values)) for a in aliases}),('wemb_help','turner_help','barnes_help')
    for grade in (40,85):
        yield scenario(pool,'curry_unknown_security_'+str(grade),{'curry':{'S17':grade}}),('curry_creator',)
        changes={a:{'S14':grade} for a in aliases if pool['packet']['proposed_source_input_section']['players'].get(IDS[a],pool['partner_sources'].get(IDS[a],{}))['inputs']['S14']['status']=='unknown'}
        yield scenario(pool,'unknown_receiving_'+str(grade),changes),('brunson_curry_outlet','brunson_turner_outlet','jokic_supplied_lob')
    # One evidenced component at a time; recognition and execution never stacked.
    for alias,key,ends,case_names in [
        ('curry','S08',(75,95),('curry_creator',)),('brunson','S02',(76,92),('brunson_curry_outlet',)),
        ('jokic','S27',(76,92),('jokic_screen_show',)),('jokic','S28',(80,95),('jokic_screen_show',)),
        ('jokic','F04.recognition',(86,98),('jokic_supplied_lob',)),('jokic','F04.execution',(86,98),('jokic_supplied_lob',)),
        ('turner','S36',(50,85),('turner_help','turner_screen_coverage')),
        ('wemb','S38',(80,95),('wemb_help',)),('wemb','S39',(76,92),('wemb_help',))]:
        for endpoint in ends:
            yield scenario(pool,alias+'_'+key+'_'+str(endpoint),{alias:{key:endpoint}},kind='source_range'),case_names
    # Turner's source criticizes drop while crediting speed. Do not assume both poor.
    for grade,motion in [(50,(3.5,6.5,2.8)),(85,(2.5,5.5,2.2))]:
        p=scenario(pool,'turner_joint_position_'+str(grade),{'turner':{'S36':grade}},kind='source_range')
        p=scenario(p,p['scenario'],{'turner':dict(zip(('P05','P06','P07'),motion))})
        yield p,('turner_help','turner_screen_coverage')
