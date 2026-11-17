"""Fixed attribution replay of existing prefixes; no new engine/skill changes.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_mixed_pop_family_audit.py
"""
from collections import Counter
import json
import time
from unittest.mock import patch

from experiments.mixed_pop_validation.fixtures import build_pool,fixture,ACTORS,BASE
from experiments.mixed_pop_validation import sampling
from experiments.expanded_cohort_performance.fixtures import fixture as supplied
from experiments.action_choice_consistency.empirical import first_event
from scripts.run_mixed_pop_validation import write


def run(state):
    real=sampling.resolve_drive;choices={};notice=Counter()
    def observed(*args,**kwargs):
        action=real(*args,**kwargs);draws=args[4];remaining=args[5];record=action['record'];name=record.get('choice','before_choice_loss')
        outcome,points,_=first_event(action,draws,remaining)
        r=choices.setdefault(name,{'selections':0,'launched':0,'accurate_delivery':0,'catch_and_shot_stage':0,'points':0,'events':Counter(),'projected_EP_sum':0.0,'projected_branches':Counter()})
        r['selections']+=1;r['points']+=points;r['events'][outcome]+=1;passed=record.get('pass')
        r['launched']+=passed is not None;r['accurate_delivery']+=bool(passed and passed['accurate']);r['catch_and_shot_stage']+=outcome in sampling.SHOT_EVENTS
        for key,value in record.get('noticed_options',{}).items():
            notice[key+'_eligible']+=1;notice[key+'_noticed']+=bool(value)
        # Reset prediction is a future proxy; do not compare it to current0.
        projection=record.get('choice_projection',{}).get('candidates',{}).get(name)
        if projection and name!='reset':
            r['projected_EP_sum']+=projection['expected_points']
            r['projected_branches'].update(projection['branches'])
        return action
    a=sampling.accumulator()
    with patch.object(sampling,'resolve_drive',observed):sampling.add_trials(state,a,0,128)
    result=sampling.finish(a)
    assert sum(v['selections'] for v in choices.values())==result['event_count']
    assert sum(v['points'] for v in choices.values())==sum(a['points'])
    assert {k:v['selections'] for k,v in choices.items()}==result['choices']
    for row in choices.values():
        row['events']=dict(row['events']);row['projected_branches']=dict(row['projected_branches'])
    return {'n':result['n'],'event_attempts':result['event_count'],'per_choice':choices,'pass_window_notices':dict(notice),
        'scope':'observes the actual unchanged resolver/first-event stream; fixed256-possession prefix already present in main trials, not additional independent evidence',
        'consistency_checks':'choices/event counts and all points reconcile with the continuation harness'}


def main():
    out=BASE/'verified';p=build_pool();budget=json.loads((out/'optional-research-budget-consumption.json').read_text());rows=[];started=time.perf_counter()
    assert budget['aggregate_possessions_including_interruption']+1536<=60000
    assert budget['aggregate_events_including_interruption']+1536*20<=180000
    write(out,'family-attribution-replay-prespec.json',{'purpose':'complete per-route delivery/catch/shot attribution during final result review','fixed_contexts':6,'fixed_possessions_per_context':256,
        'total_replayed_possessions':1536,'new_independent_inference_samples':0,'source_or_engine_changes':False,'original_aggregate_caps_preserved':True})
    for actor in ACTORS[:-1]:
        s,_,_=fixture(p,actor);rows.append({'actor':actor,'context':'reference_show',**run(s)})
    for name,ball in [('available',(1.2,2.7)),('later_pressure',(1.2,1.7))]:
        s,_,_=supplied(p,creator='jokic',receiver='curry',partner='wemb',poa='turner',helper='barnes',other='brunson',families=('F04','F06'),screen_separation=.5,ball=ball)
        rows.append({'actor':'jokic_supplied_creator','context':name,**run(s)})
    wall=time.perf_counter()-started;events=sum(r['event_attempts'] for r in rows)
    assert budget['aggregate_natural_wall_s_including_interruption']+wall<180
    write(out,'per-route-delivery-catch-outcome-audit.json',rows)
    write(out,'final-aggregate-budget.json',{'supplied_possessions_including_interrupted_and_attribution_replay':budget['aggregate_possessions_including_interruption']+1536,
        'event_attempts_including_all_replay':budget['aggregate_events_including_interruption']+events,
        'active_natural_wall_s_including_all_replay':budget['aggregate_natural_wall_s_including_interruption']+wall,
        'inference_possessions':34816,'interrupted_discarded_possessions':3584,'attribution_only_replayed_possessions':1536,'no_caps_increased':True})
    print('family attribution replay complete:',1536,'charged possessions',events,'events',round(wall,3),'seconds')


if __name__=='__main__':main()
