"""Bounded coupled contexts; changed controls are separate from engine effects."""
from collections import Counter
import math
import random
import statistics

from nba_gm_data.creation_passing import resolve_drive
from .fixtures import make_case,decision
from .empirical import first_event


def scenarios(pilot):
    all_passes=('F03','F04','F06')
    rows=[
        ('reference',{'families':all_passes},all_passes+('finish',)),
        ('weak_dunk',{'families':(),'available':0,'finish_mix':(.5,0,0,.5,0),'changes':{'creator':{'S12':10}}},('finish',)),
        ('strong_dunk',{'families':(),'available':0,'finish_mix':(.5,0,0,.5,0),'changes':{'creator':{'S12':95}}},('finish',)),
        ('contact_finish',{'families':(),'start':(1,1.5),'finish_mix':(0,1,0,0,0),'changes':{'creator':{'S15':30},'helper':{'S45':10}}},('finish',)),
        ('floater_finish',{'families':(),'finish_mix':(0,0,1,0,0),'changes':{'creator':{'S11':90}}},('finish',)),
        ('covered_weak_shooter',{'families':('F06',),'start':(3,6.8),'commitment':0,'shooter_grade':50,'shoot_probability':.1},('F06',)),
        ('abandoned_strong_shooter',{'families':('F06',),'start':(3,6.8),'commitment':1,'shooter_grade':90,'shoot_probability':.85},('F06',)),
        ('low_receiving',{'families':('F03','F04'),'changes':{'roller':{'S14':20}}},('F03','F04')),
        ('high_receiving',{'families':('F03','F04'),'changes':{'roller':{'S14':95}}},('F03','F04')),
        ('low_delivery',{'families':('F03',),'changes':{'creator':{'F03.execution':20}}},('F03',)),
        ('high_delivery',{'families':('F03',),'changes':{'creator':{'F03.execution':95}}},('F03',)),
        ('short_clock',{'families':all_passes,'remaining':1.25},all_passes+('finish',)),
        ('screen_show',{'families':all_passes,'coverage':'show_then_recover'},all_passes+('finish',)),
        ('screen_stay',{'families':all_passes,'coverage':'stay'},all_passes+('finish',)),
        ('help_unavailable',{'families':all_passes,'available':0},all_passes+('finish',)),
        ('help_late',{'families':(),'start':(10,10)},('finish',)),
        ('spacer_low',{'families':('F06',),'start':None,'shooter_grade':50,'shoot_probability':.1},('F06','finish')),
        ('spacer_high',{'families':('F06',),'start':None,'shooter_grade':90,'shoot_probability':.85},('F06','finish')),
    ]
    state,_,_=make_case(pilot,families=('F03',));d=decision(state);o=d['options']['F03']
    end=d['frame']['elapsed']+o['delivery']['flight_s']+.05+.25*o['delivery']['window_radius_m']*.3
    rows.append(('tight_roll_window',{'families':('F03',),'roll_window':end},('F03',)))
    return [{'name':name,'controls':controls,'conditional_candidates':candidates} for name,controls,candidates in rows]


def coupled(pilot,row,resolver=resolve_drive,n=512,*,consistent=True,prepare_reference=None):
    state,context,config=make_case(pilot,consistent=consistent,**row['controls'])
    if prepare_reference:state=prepare_reference(context,config,row['controls'].get('start',(2,1)),state['audit_context'])
    rng=random.Random(1802);events=Counter();choices=Counter();stages=Counter();points=[];node_counts=[];examples=[]
    remaining=row['controls'].get('remaining',24)
    for index in range(n):
        draws=[rng.random() for _ in range(48)]
        action=resolver(state,state['audit_context']['ids'][0],'response_a','response_b',draws,remaining)
        record=action['record'];outcome,value,_=first_event(action,draws,remaining);events[outcome]+=1;points.append(value)
        choices[record.get('choice','before_choice_loss')]+=1
        for key in ('noticed','committed','timely'):stages['help_'+key]+=bool(record.get('help',{}).get(key))
        stages['beat_defender']+=bool(record.get('beat_defender'))
        for name,noticed in record.get('noticed_options',{}).items():stages['noticed_'+name]+=bool(noticed)
        if 'choice_projection' in record:
            p=record['choice_projection'];node_counts.append({k:p[k] for k in ('candidate_count','candidate_resolution_calls','shot_plan_evaluations','clock_boundary_evaluations')})
        if len(examples)<2 and 'choice' in record:examples.append({'event':outcome,'points':value,'record':record})
    mean=statistics.mean(points);se=statistics.stdev(points)/math.sqrt(n)
    return {'name':row['name'],'n':n,'seed':1802,'controls':row['controls'],'choices':dict(choices),'events':dict(events),'stages':dict(stages),
        'mean_first_event_points':mean,'sampling95':[mean-1.96*se,mean+1.96*se],'node_counts':node_counts,'examples':examples,
        'scope':'same seeded first-action opportunities before/after; resets score zero here, continuation is separately approximated; not NBA forecast'}
