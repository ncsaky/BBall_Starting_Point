"""Actual first-event sampling after the one-time securing boundary."""
from collections import Counter
import math
import random
import statistics
from nba_gm_data.creation_passing import resolve_candidate
from nba_gm_data.action_choice import project_candidate
from nba_gm_data.pass_recovery import complete_receipt
from experiments.action_choice_consistency.empirical import first_event


def event(action,draws,remaining):
    action=complete_receipt(action,draws[15],remaining)
    outcome,points,rebound=first_event(action,draws,remaining)
    if outcome=='reset' and action['record'].get('receipt_category')=='recovered':outcome='recovery_reset'
    return outcome,points,rebound,action


def check(decision,name,*,n=4096,seed=17):
    frame=decision['frame'];p4=project_candidate(frame,name,decision['options']);p8=project_candidate(frame,name,decision['options'],order=8)
    rng=random.Random(seed);counts=Counter();categories=Counter();points=[];secured=0
    for _ in range(n):
        draws=[rng.random() for _ in range(48)]
        action=resolve_candidate(frame,name,decision['options'],draws,{})
        outcome,value,_,a=event(action,draws,frame['remaining_s']);counts[outcome]+=1;points.append(value)
        categories[a['record'].get('receipt_category','not_launched')]+=1;secured+=a['record'].get('actual_receipt_secured') is True
    se=statistics.stdev(points)/math.sqrt(n);convergence=abs(p4['expected_points']-p8['expected_points']);mean=statistics.mean(points)
    branches={}
    for key in set(p4['branches'])|set(counts):
        probability=p4['branches'].get(key,0);rate=counts[key]/n
        tolerance=4*math.sqrt(probability*(1-probability)/n)+4/n+abs(probability-p8['branches'].get(key,0))+.003
        branches[key]={'predicted':probability,'observed_count':counts[key],'observed_rate':rate,'difference':rate-probability,'tolerance':tolerance,'passed':abs(rate-probability)<=tolerance}
    mean_tolerance=4*se+convergence+.01
    return {'candidate':name,'n':n,'seed':seed,'projection':p4,'higher_order':p8,'observed':dict(counts),'observed_receipt_plans':dict(categories),
        'observed_secured':secured,'mean_points':mean,'standard_error':se,'nominal_MC95':[mean-1.96*se,mean+1.96*se],
        'G4_G8_EP_difference':convergence,'mean_tolerance':mean_tolerance,'mean_passed':abs(mean-p4['expected_points'])<=mean_tolerance,
        'branch_checks':branches,'all_passed':abs(mean-p4['expected_points'])<=mean_tolerance and all(v['passed'] for v in branches.values()),
        'scope':'conditional retained access/help/notice; first event only, paid recovery reset scores0; no future-reset/rebound credit'}
