"""Bounded supplied-creator possessions using accepted outcome/continuation rules.

Initial actor assignment is context, not an outcome draw. Choice, placement,
reception, shooting, resets and rebounds remain sampled. No forced pop success.
"""
from collections import Counter
import math
import random
import statistics
import time

from nba_gm_data.creation_passing import resolve_drive
from nba_gm_data.interior_game import _pick
from experiments.action_choice_consistency.empirical import first_event

SHOT_EVENTS={'shooting_foul','block','made_fg','missed_fg'}


def wilson(count,n):
    if not n:return [None,None]
    z=1.959963984540054;p=count/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,mid-half),min(1,mid+half)]


def accumulator():
    stages=('initial_possessions','intended_pop','pop_screen_read','positive_pop_receiving_window','pop_pass_eligible','pop_pass_read',
        'pop_selected','pop_wait_loss','pop_launched','pop_accurate_delivery','pop_caught_and_shot_stage','pop_made_field_goal','reset_continuations','offensive_rebound_continuations')
    return {'n':0,'events':Counter(),'choices':Counter(),'stages':Counter(dict.fromkeys(stages,0)),'routes':Counter(),'terminations':Counter(),
        'pop_events':Counter(),'pass_by_family':Counter(),'predicted_pop':Counter(),'predicted_variance':Counter(),
        'points':[],'pop_points':[],'predicted_pop_EP':[],'attempt_counts':[],'example_pop':[], 'per_seed':{},
        'projection_counts':Counter(),'truncated':0,'event_count':0}


def one_possession(state,seed,index,acc,*,draw_source=None):
    ids=state['audit_context']['ids'];own=ids[:3];creator=own[0];remaining=state['spec'].possession_budget_s
    total=0;last='audit_abort';attempts=0
    for attempt in range(20):
        if draw_source is None:
            rng=random.Random(f'{seed}:mixed_pop_validation:possession:{index}:attempt:{attempt}')
            draws=[rng.random() for _ in range(48)]
        else:draws=draw_source(seed,index,attempt)
        attempts+=1;acc['event_count']+=1
        action=resolve_drive(state,creator,'response_a','response_b',draws,remaining,screen_allowed=attempt==0)
        record=action['record'];outcome,value,rebound=first_event(action,draws,remaining);total+=value;acc['events'][outcome]+=1
        choice=record.get('choice','before_choice_loss');acc['choices'][choice]+=1
        if attempt==0:
            screen=record.get('screen_action',{});route=screen.get('route',screen.get('kind','no_screen'));acc['routes'][route]+=1
            acc['stages']['initial_possessions']+=1
            acc['stages']['intended_pop']+=screen.get('effective_intent')=='pop'
            acc['stages']['pop_screen_read']+=route=='pop'
            acc['stages']['positive_pop_receiving_window']+=route=='pop' and screen['window_end_s']>screen['window_start_s']
            acc['stages']['pop_pass_eligible']+='pop' in record.get('noticed_options',{})
            acc['stages']['pop_pass_read']+=bool(record.get('noticed_options',{}).get('pop'))
        for key in ('candidate_count','candidate_resolution_calls','shot_plan_evaluations','clock_boundary_evaluations'):
            acc['projection_counts'][key]+=record.get('choice_projection',{}).get(key,0)
        passed=record.get('pass')
        if passed:acc['pass_by_family'][passed['family']]+=1
        if choice=='pop':
            acc['stages']['pop_selected']+=1;acc['pop_events'][outcome]+=1;acc['pop_points'].append(value)
            acc['stages']['pop_wait_loss']+=outcome=='waiting_loss'
            acc['stages']['pop_launched']+=passed is not None
            acc['stages']['pop_accurate_delivery']+=bool(passed and passed['accurate'])
            acc['stages']['pop_caught_and_shot_stage']+=outcome in SHOT_EVENTS
            acc['stages']['pop_made_field_goal']+=outcome=='made_fg'
            projection=record['choice_projection']['candidates']['pop'];acc['predicted_pop_EP'].append(projection['expected_points'])
            for key,probability in projection['branches'].items():acc['predicted_pop'][key]+=probability;acc['predicted_variance'][key]+=probability*(1-probability)
            if len(acc['example_pop'])<3:acc['example_pop'].append({'seed':seed,'index':index,'attempt':attempt,'outcome':outcome,'points':value,'record':record})
        remaining-=action['elapsed_s']
        if remaining<=0:last='shot_clock_turnover';break
        if action['kind']=='reset':
            acc['stages']['reset_continuations']+=1;continue
        if action['kind']=='turnover' or outcome=='failed_catch':last=outcome;break
        if rebound:
            if draws[13]<state['coupled']['spec'].offensive_rebound_probability:
                # Accepted baseline has equal48-minute exposure and oreb1.0.
                # Use the same weighted selector; no rebound skill is inferred.
                creator=_pick(list(own),[48.0]*len(own),draws[14]);remaining=state['spec'].rebound_budget_s
                acc['stages']['offensive_rebound_continuations']+=1;continue
            last='defensive_rebound';break
        last=outcome;break
    else:acc['truncated']+=1
    acc['n']+=1;acc['points'].append(total);acc['attempt_counts'].append(attempts);acc['terminations'][last]+=1
    seed_stats=acc['per_seed'].setdefault(str(seed),{'n':0,'points':0,'pop_selected':0,'pop_shot_stage':0})
    seed_stats['n']+=1;seed_stats['points']+=total
    return total


def add_trials(state,acc,start,count,seeds=(17,29)):
    for seed in seeds:
        before_selected=acc['stages']['pop_selected'];before_shot=acc['stages']['pop_caught_and_shot_stage']
        for index in range(start,start+count):one_possession(state,seed,index,acc)
        acc['per_seed'][str(seed)]['pop_selected']+=acc['stages']['pop_selected']-before_selected
        acc['per_seed'][str(seed)]['pop_shot_stage']+=acc['stages']['pop_caught_and_shot_stage']-before_shot


def finish(acc):
    n=acc['n'];selected=acc['stages']['pop_selected'];caught=acc['stages']['pop_caught_and_shot_stage'];made=acc['stages']['pop_made_field_goal']
    mean=statistics.mean(acc['points']);se=statistics.stdev(acc['points'])/math.sqrt(n) if n>1 else 0
    branches={}
    for key,predicted in acc['predicted_pop'].items():
        observed=acc['pop_events'][key];sd=math.sqrt(acc['predicted_variance'][key]);tolerance=4*sd+4+.01*selected
        branches[key]={'observed':observed,'predicted_count':predicted,'observed_rate':observed/selected if selected else None,
            'predicted_rate':predicted/selected if selected else None,'difference_count':observed-predicted,
            'MC_and_numerical_tolerance_count':tolerance,'within_prespecified_tolerance':abs(observed-predicted)<=tolerance}
    return {**{k:dict(v) if isinstance(v,Counter) else v for k,v in acc.items() if k not in ('points','pop_points','predicted_pop_EP','attempt_counts','predicted_variance')},
        'mean_possession_points':mean,'nominal_MC95_points':[mean-1.96*se,mean+1.96*se],
        'pop_completion_rate':caught/selected if selected else None,'pop_completion_Wilson95':wilson(caught,selected),
        'pop_make_rate_per_selected':made/selected if selected else None,'pop_make_Wilson95':wilson(made,selected),
        'pop_mean_first_event_points':statistics.mean(acc['pop_points']) if selected else None,
        'pop_mean_projected_EP':statistics.mean(acc['predicted_pop_EP']) if selected else None,'pop_branch_comparisons':branches,
        'mean_event_attempts':statistics.mean(acc['attempt_counts']),'maximum_event_attempts':max(acc['attempt_counts']),
        'scope':'supplied initial creator, actual reset/oreb continuation, natural error/catch/shot draws; nominal Monte Carlo uncertainty, not player parameter certainty'}


def run_case(state,*,adaptive=True,remaining_seconds=180,minimum_per_seed=256):
    acc=accumulator();start=0;started=time.perf_counter();reason='fixed_minimum'
    while start<768:
        count=minimum_per_seed if start==0 else 128
        add_trials(state,acc,start,count);start+=count
        if not adaptive:break
        if acc['stages']['pop_pass_eligible']==0:reason='no_pop_eligibility_in_minimum';break
        if acc['stages']['pop_selected']>=40:reason='selected_pop_target_met';break
        if time.perf_counter()-started>=remaining_seconds:reason='wall_cap';break
        reason='per_context_trial_cap'
    result=finish(acc);result.update(per_seed_count=start,adaptive_stopping_reason=reason,wall_s=time.perf_counter()-started)
    return result
