"""Paired supplied-creator possessions with actual recipient reset state."""
from collections import Counter
import math
import random
import statistics
import time
from nba_gm_data.creation_passing import resolve_drive
from nba_gm_data.pass_recovery import apply_continuation,advance_after_reset
from nba_gm_data.interior_game import _pick
from experiments.action_choice_consistency.empirical import first_event


def run(state,*,per_seed=128,seeds=(17,29),max_events=32768,deadline=None):
    ids=state['audit_context']['ids'];own=ids[:3];events=Counter();choices=Counter();stages=Counter();plans=Counter();secured=Counter();receipt_events={};receipt_by_choice={};points=[];attempts=[];examples=[];work=Counter();truncated=0;per_seed_rows=[]
    for seed in seeds:
        seed_points=0;seed_attempts=0
        for index in range(per_seed):
            if sum(events.values())>=max_events or (deadline is not None and time.perf_counter()>=deadline):break
            current=state;creator=own[0];remaining=state['spec'].possession_budget_s;total=0
            for attempt in range(20):
                if sum(events.values())>=max_events or (deadline is not None and time.perf_counter()>=deadline):
                    truncated+=1;break
                rng=random.Random(f'{seed}:pass_recovery_validation:{index}:{attempt}');draws=[rng.random() for _ in range(48)]
                action=resolve_drive(current,creator,'response_a','response_b',draws,remaining,screen_allowed=attempt==0)
                record=action['record'];outcome,value,rebound=first_event(action,draws,remaining);events[outcome]+=1;total+=value;seed_attempts+=1
                choice=record.get('choice','before_choice_loss');choices[choice]+=1
                passed=record.get('pass')
                if passed:
                    category=record.get('receipt_category','clean' if passed.get('accurate') and action['kind']=='shot' else 'lost')
                    plans[category]+=1;stages['pass_selected_launched']+=1
                    caught=record.get('actual_receipt_secured') is True if 'actual_receipt_secured' in record else outcome in {'shooting_foul','block','made_fg','missed_fg'}
                    if caught:secured[category]+=1
                    family=receipt_by_choice.setdefault(choice,{'plans':Counter(),'secured':Counter(),'events':Counter()})
                    family['plans'][category]+=1;family['events'][outcome]+=1
                    if caught:family['secured'][category]+=1
                    row=receipt_events.setdefault(category,Counter());row[outcome]+=1
                    stages['receipt_shot_stage']+=outcome in {'shooting_foul','block','made_fg','missed_fg'}
                    stages['receipt_unresolved_clock']+=outcome=='shot_clock_turnover'
                    stages['recovered_paid_reset']+=category=='recovered' and outcome=='reset' and caught
                    if len(examples)<3 and category=='recovered':examples.append({'seed':seed,'index':index,'attempt':attempt,'outcome':outcome,'record':record})
                for key in ('candidate_resolution_calls','shot_plan_evaluations','clock_boundary_evaluations','recovery_geometry_evaluations'):
                    work[key]+=record.get('choice_projection',{}).get(key,0)
                remaining-=action['elapsed_s']
                if remaining<=0:break
                if action['kind']=='reset':
                    stages['reset_continuations']+=1
                    if 'recovery_continuation' in action:
                        current=apply_continuation(current,action['recovery_continuation']);creator=action['continuation_creator_id']
                    elif getattr(state['spec'],'receipt_policy',None):current=advance_after_reset(current,action,creator)
                    continue
                if action['kind']=='turnover' or outcome=='failed_catch':break
                if rebound and draws[13]<state['coupled']['spec'].offensive_rebound_probability:
                    creator=_pick(list(own),[48.0]*len(own),draws[14]);remaining=state['spec'].rebound_budget_s;stages['offensive_rebound_continuations']+=1;current=state
                    continue
                break
            else:truncated+=1
            points.append(total);seed_points+=total;attempts.append(attempt+1)
        per_seed_rows.append({'seed':seed,'n':len(points)-sum(r['n'] for r in per_seed_rows),'points':seed_points,'event_attempts':seed_attempts})
    n=len(points);mean=statistics.mean(points);se=statistics.stdev(points)/math.sqrt(n) if n>1 else 0
    return {'n':n,'events':dict(events),'choices':dict(choices),'stages':dict(stages),'planned_receipts':dict(plans),'secured_receipts':dict(secured),
        'receipt_event_breakdown':{k:dict(v) for k,v in receipt_events.items()},'receipt_by_choice':{k:{a:dict(b) for a,b in v.items()} for k,v in receipt_by_choice.items()},'mean_possession_points':mean,'nominal_MC95_points':[mean-1.96*se,mean+1.96*se],
        'points':points,'event_attempts':sum(events.values()),'maximum_attempts':max(attempts),'truncated':truncated,'per_seed':per_seed_rows,
        'projection_work':dict(work),'recovered_examples':examples,'scope':'supplied initial creator; imperfect choices/receipt/shot draws, actual resets and rebounds; other actors remain supplied locations'}
