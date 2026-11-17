"""Offline conditional event sampling; never called by the runtime projector."""
from collections import Counter
import math
import random
import statistics

from nba_gm_data.creation_passing import resolve_candidate
from nba_gm_data.interior_game import shot_probabilities
from nba_gm_data.action_choice import project_candidate


def first_event(action,draws,remaining):
    """Same first-event order as the shared kernel, including clock precedence."""
    if action['elapsed_s']>=remaining:return 'shot_clock_turnover',0,False
    if action['kind']=='turnover':return action['outcome'],0,False
    if action['kind']=='reset':return 'reset',0,False
    plan=action['plan']
    if draws[15]>=plan['reception']:return 'failed_catch',0,False
    p=shot_probabilities(plan['off'],plan['response'],plan['zone']);shots=3 if plan['zone']=='perimeter' else 2
    if draws[5]<p['foul']:
        return 'shooting_foul',sum(draws[8+k]<plan['off']['ft_pct'] for k in range(shots)),draws[8+shots-1]>=plan['off']['ft_pct']
    if draws[6]<p['block_given_no_foul']:return 'block',0,True
    if draws[7]<p['make_given_unblocked']:return 'made_fg',shots,False
    return 'missed_fg',0,True


def sample_candidate(decision,name,n=8192,seed=1801):
    frame=decision['frame'];rng=random.Random(seed);counts=Counter();points=[];reboundable=0
    for _ in range(n):
        draws=[rng.random() for _ in range(48)]
        action=resolve_candidate(frame,name,decision['options'],draws,{})
        outcome,value,rebound=first_event(action,draws,frame['remaining_s']);reboundable+=rebound
        counts[outcome]+=1;points.append(value)
    mean=statistics.mean(points);se=statistics.stdev(points)/math.sqrt(n)
    return {'n':n,'seed':seed,'events':dict(counts),'mean_points':mean,'mean_sampling95':[mean-1.96*se,mean+1.96*se],
        'mean_standard_error':se,'zero_points_probability':points.count(0)/n,'reboundable_probability':reboundable/n,
        'scope':'first event conditional on retained handling/observed access/help/notice; no subsequent rebound or reset game'}


def validate_candidate(decision,name,n=8192,seed=1801):
    p4=project_candidate(decision['frame'],name,decision['options']);p8=project_candidate(decision['frame'],name,decision['options'],order=8)
    observed=sample_candidate(decision,name,n,seed);convergence=abs(p4['expected_points']-p8['expected_points'])
    # Four SE is a conservative simultaneous sampling check. Deterministic
    # quadrature error has a separate numerical convergence allowance.
    tolerance=4*observed['mean_standard_error']+convergence+.01
    error=abs(observed['mean_points']-p4['expected_points'])
    branch_checks={}
    for key,p in p4['branches'].items():
        rate=observed['events'].get(key,0)/n
        delta=abs(rate-p);bound=4*math.sqrt(max(0,p*(1-p))/n)+4/n+abs(p-p8['branches'][key])+.003
        branch_checks[key]={'predicted':p,'observed_count':observed['events'].get(key,0),'observed_rate':rate,'difference':delta,'tolerance':bound,'passed':delta<=bound}
    return {'candidate':name,'projection':p4,'higher_order_projection':p8,'observed':observed,
        'quadrature_EP_difference':convergence,'absolute_mean_error':error,'mean_tolerance':tolerance,
        'mean_check_passed':error<=tolerance,'branch_checks':branch_checks,'all_passed':error<=tolerance and all(v['passed'] for v in branch_checks.values())}
