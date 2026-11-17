"""Timing/position/coverage probes with downstream actions, no player forecasts."""
from collections import Counter
from dataclasses import replace
import math
import random
import statistics

from nba_gm_data.creation_passing import resolve_drive,containment_response
from nba_gm_data.interior_game import shot_probabilities
from experiments.player_input_pilot.probes import wilson
from .fixtures import fixture,boundary_start,fixed_draws

POLICY='projected_contest_v1'


def choice_probability(scores,name='finish'):
    weights={k:max(.001,v-.25)**3 for k,v in scores.items()}
    return weights.get(name,0)/sum(weights.values())


def boundary_sweep(pilot,resolver=resolve_drive,policy='legacy_timely_v1'):
    rows=[]
    for alias in ('white','castle'):
        for window in (.9,1.1,1.3):
            for angle in (0,math.pi/2,math.pi):
                state,_,_=fixture(pilot,alias,window=window,policy=policy,commitment=1)
                for delta in (-.30,-.10,-.01,-1e-6,1e-6,.01,.10,.30):
                    elapsed=boundary_start(state,delta,angle)
                    r=resolver(state,state['audit_context']['ids'][0],'response_a','response_b',fixed_draws(),24)
                    rec=r['record'];response=r.get('plan',{}).get('response')
                    rows.append({'actor':alias,'window_control_s':window,'start_angle_rad':angle,'requested_arrival_delta_s':delta,
                        'actual_arrival_delta_s':rec['help']['arrival_s']-elapsed,'start_m':state['coupled']['positions']['response_b'],
                        'timely':rec['help']['timely'],'finish_choice_score':rec['choice_scores'].get('finish'),
                        'finish_choice_probability_given_notices_good_choice':choice_probability(rec['choice_scores']),
                        'selected_choice':rec['choice'],'kind':r['kind'],'actual_contest':response,
                        'projection':rec.get('help_finish_projection')})
    return rows


def path_endpoint_sweep(pilot,resolver=resolve_drive,policy='legacy_timely_v1'):
    rows=[]
    for alias in ('white','castle'):
        for window in (.9,1.1,1.3):
            state,_,_=fixture(pilot,alias,policy=policy,window=window,commitment=1)
            ids=state['audit_context']['ids'];a=state['profiles'][ids[0]];h=state['profiles'][ids[4]];setup=state['setups'][ids[0]]
            elapsed=containment_response(a,state['profiles'][setup.defender_id],setup)['attacker_clear_s']+state['spec'].coefficients.decision_delay_s*(1-a.skill('S20'))
            delay=.08+.45*(1-h.skill('S38'));t=max(0,elapsed-delay);speed=min(h.speed_m_s,h.lateral_m_s)
            covered=.5*h.acceleration_m_s2*t*t if t<=speed/h.acceleration_m_s2 else speed*(t-speed/(2*h.acceleration_m_s2))
            for angle in (0,math.pi/2,math.pi):
                for endpoint in ('direct_path','positioning_adjusted_path'):
                    offset=0 if endpoint=='direct_path' else .6*(1-h.skill('S39'))
                    for delta in (-1e-6,1e-6):
                        radius=covered-offset+delta;state['coupled']['positions']['response_b']=(.8+radius*math.cos(angle),1.5+radius*math.sin(angle))
                        r=resolver(state,ids[0],'response_a','response_b',fixed_draws(),24)
                        rows.append({'actor':alias,'window_control_s':window,'start_angle_rad':angle,'endpoint_reference':endpoint,
                            'boundary_center_radius_m':covered-offset,'path_endpoint_delta_m':delta,
                            'finish_choice_score':r['record']['choice_scores']['finish'],'help':r['record']['help'],
                            'helper_position_m':r['record']['help_position_at_pass_m'],'actual_contest':r['plan']['response']})
    return rows


CONTEXTS=(
    {'name':'early_near','start':(1.2,1.5),'window':1.3},
    {'name':'marginal_common','start':(2,1),'window':1.1},
    {'name':'longer_approach','start':(2,1),'window':1.3},
    {'name':'far_late','start':(3.5,2),'window':.9},
    {'name':'unavailable','start':(1.2,1.5),'window':1.3,'available':0},
    {'name':'declines_help','start':(1.2,1.5),'window':1.3,'commitment':0},
    {'name':'weak_spacer','start':None,'window':1.1,'shooter_grade':50,'shoot_probability':.10},
    {'name':'strong_spacer','start':None,'window':1.1,'shooter_grade':90,'shoot_probability':.85},
    {'name':'low_finish','start':(2,1),'window':1.1,'finish_grade':50},
    {'name':'high_finish','start':(2,1),'window':1.1,'finish_grade':90},
    {'name':'balanced_near','start':(1.2,1.5),'window':1.1,'finish_grade':50,'shooter_grade':90,'shoot_probability':.85},
    {'name':'mixed_deadline_choices','start':(2,1),'window':1.25,'finish_grade':50,'shooter_grade':90,'shoot_probability':.85},
    {'name':'screen_show','start':(2,1),'window':1.1,'coverage':'show_then_recover','families':('F03','F04','F06')},
    {'name':'screen_stay','start':(2,1),'window':1.1,'coverage':'stay','families':('F03','F04','F06')},
)


def context_sweep(pilot,resolver=resolve_drive,policy='legacy_timely_v1',n=512):
    rows=[]
    for context in CONTEXTS:
        actors={};paired={}
        for alias in ('white','castle'):
            state,_,_=fixture(pilot,alias,policy=policy,**{k:v for k,v in context.items() if k!='name'})
            rng=random.Random(1701);counts=Counter();choices=Counter();sums=Counter();observed=Counter();indicators=[]
            examples=[]
            for index in range(n):
                d=[rng.random() for _ in range(48)]
                r=resolver(state,state['audit_context']['ids'][0],'response_a','response_b',d,24)
                rec=r['record'];counts[r.get('outcome',r['kind'])]+=1;choices[rec.get('choice','before_choice_loss')]+=1
                for key in ('noticed','committed','timely'):counts['help_'+key]+=bool(rec.get('help',{}).get(key))
                counts['beat_defender']+=bool(rec.get('beat_defender'))
                for family,seen in rec.get('noticed_options',{}).items():counts['noticed_'+family]+=bool(seen)
                counts['accurate_pass']+=bool(rec.get('pass',{}).get('accurate'))
                if 'plan' in r:
                    plan=r['plan'];response=plan['response']
                    probs=shot_probabilities(plan['off'],response,plan['zone'])
                    for key,value in [('shot_expected_points',probs['expected_points']),
                                      ('conversion_reduction',response['conversion_reduction'] if response else 0),
                                      ('block_probability',response['block_probability'] if response else 0),
                                      ('primary_arrival_s',rec['derived_primary_arrival_s'])]:
                        sums[key]+=value;observed[key]+=1
                    # A separate conditional observation; the shared kernel owns
                    # shot/FT/rebound accounting, checked in small kernel calls.
                    counts['secured_reception']+=d[15]<plan['reception']
                indicators.append(int(rec.get('choice')=='finish'))
                if len(examples)<3 and (rec.get('help',{}).get('committed') or index==n-1):
                    examples.append({'kind':r['kind'],'record':rec,'plan':r.get('plan')})
            # An exact conditional choice readout complements sparse realized
            # beats in the unconditional sample. It does not become an estimate
            # of notice/commit frequency or a replacement for event counts.
            fixed=resolver(state,state['audit_context']['ids'][0],'response_a','response_b',fixed_draws(),24)
            scores=fixed['record'].get('choice_scores',{})
            conditional={'scope':'forced retained/access/read draws and commit when eligible; good-choice weights at this context',
                'finish_selection_probability':choice_probability(scores) if scores else None,'choice_scores':scores,
                'record':fixed['record'],'selected_finish_contest':fixed.get('plan',{}).get('response')}
            actors[alias]={'n':n,'events':dict(counts),'choices':dict(choices),
                'finish_wilson95':wilson(choices['finish'],n),
                'conditional_on_shot_means':{key:sums[key]/observed[key] for key in sums},
                'shot_mean_denominators':dict(observed),'starting_context':state['audit_context'],'examples':examples,
                'conditional_choice_probe':conditional}
            paired[alias]=indicators
        diff=[a-b for a,b in zip(paired['white'],paired['castle'],strict=True)]
        mean=statistics.mean(diff);se=statistics.stdev(diff)/math.sqrt(n)
        rows.append({'context':context,'actors':actors,'paired_white_minus_castle_finish_selection':mean,
            'paired_sampling95':[mean-1.96*se,mean+1.96*se],
            'scope':'same synthetic creator/receiver/POA; actual choices and conditional contests, not NBA player value'})
    return rows


def containment_sweep(pilot,resolver=resolve_drive,policy='legacy_timely_v1',n=512):
    rows=[]
    for spacing in (0,.3,.6):
        for lateral in (2.2,2.5,2.8):
            actors={}
            for alias in ('castle','luka'):
                # Named technique is varied separately from a shared synthetic
                # lateral control; original source records remain untouched.
                from experiments.player_input_pilot.pilot import variant
                p=variant(pilot,{alias:{'P07':lateral}},name='matched containment lateral response sweep')
                state,_,_=fixture(p,alias,role='poa',policy=policy,start=(2,1),window=1.1)
                pid=state['audit_context']['ids'][0];setup=replace(state['setups'][pid],screen_separation_m=spacing)
                state['setups'][pid]=setup
                response=containment_response(state['profiles'][pid],state['profiles'][setup.defender_id],setup)
                rng=random.Random(1702);outcomes=Counter();choices=Counter()
                for _ in range(n):
                    r=resolver(state,pid,'response_a','response_b',[rng.random() for _ in range(48)],24)
                    outcomes[r.get('outcome',r['kind'])]+=1;choices[r['record'].get('choice','before_choice_loss')]+=1
                actors[alias]={'response':response,'n':n,'outcomes':dict(outcomes),'choices':dict(choices)}
            rows.append({'screen_separation_control_m':spacing,'common_lateral_control_m_s':lateral,'actors':actors,
                'castle_advantage_probability_points':actors['luka']['response']['beat_probability']-actors['castle']['response']['beat_probability']})
    return rows


def named_receiving(pilot,n=4096):
    """Fixed delivery context; separately type notice, placement and named catch."""
    from nba_gm_data.creation_passing import compile_interaction,delivery_response,sample_delivery
    from nba_gm_data.offense_response import compile_offense
    from experiments.player_input_pilot.pilot import IDS
    rows=[]
    for creator in ('luka','harper'):
        passer=compile_interaction(pilot['views'][IDS[creator]])
        for receiver in ('zubac','gobert'):
            target=compile_offense(pilot['views'][IDS[receiver]])
            for family in ('F03','F04'):
                notice=.05+.95*passer.pass_skill(family,'recognition')
                delivery=delivery_response(passer,family,4,.4,.7)
                rng=random.Random(1703);events=Counter()
                for _ in range(n):
                    seen,placed,caught=rng.random(),rng.random(),rng.random()
                    if seen>=notice:events['missed_read']+=1;continue
                    events['noticed']+=1;result=sample_delivery(delivery,placed)
                    if not result['accurate']:events['inaccurate_delivery']+=1;continue
                    events['accurate_delivery']+=1
                    events['secured_catch' if caught<result['quality']*(.5+.5*target.skill(14)) else 'failed_catch']+=1
                rows.append({'creator':creator,'receiver':receiver,'family':family,'n':n,'events':dict(events),
                    'notice_probability':notice,'accuracy_probability_given_notice':delivery['accuracy_probability'],
                    'receiver_S14_index':target.skill(14),'catch_rate':events['secured_catch']/n,
                    'catch_wilson95':wilson(events['secured_catch'],n),
                    'scope':'4m/.4 pressure/.7 opening; no late route or FG sampled; typed conditional action only'})
    return rows
