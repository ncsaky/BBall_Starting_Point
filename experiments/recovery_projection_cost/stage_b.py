"""Prospectively bounded single-candidate approximation tradeoff; no tuning."""
from contextlib import nullcontext
from dataclasses import replace
import math
import time
from unittest.mock import patch
from nba_gm_data.creation_passing import prepare_drive_decision,delivery_preparation
from nba_gm_data import action_choice
from experiments.pass_recovery.fixtures import fixture,pool,IDS
from experiments.pass_recovery import sampling
from experiments.action_choice_consistency.fixtures import observed_draws
from . import approximation
from .verification import OUT


def states():
    p=pool()
    for actor in ('turner','jokic','towns','holmgren'):
        group='development' if actor in ('turner','jokic') else 'held_out'
        for action,name in [('pop','pop'),('roll','F03'),('slip','F04')]:
            s,c,x=fixture(p,actor,action=action);d=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',observed_draws(),24)
            assert name in d['options']
            for context in ('reference','clock_boundary','sideline','defender_close'):
                frame=dict(d['frame']);options={k:dict(v) for k,v in d['options'].items()}
                if context=='clock_boundary':
                    o=options[name];p_receiver=frame['coupled']['profiles'][o['receiver_id']]
                    frame['remaining_s']=frame['elapsed']+o.get('wait_s',0)+o['delivery']['flight_s']+.05+.25*o['delivery']['window_radius_m']+delivery_preparation(p_receiver,name,.5)
                elif context=='sideline':
                    # Rigid scene translation; court/rim stay fixed. This is a
                    # counterfactual opportunity, not an altered player grade.
                    shift=4.4
                    def moved(v):return (v[0]+shift,v[1])
                    screen=dict(frame['screen'])
                    for key in ('receiver_start','roll_end','body_position_at_contact_m','coverage_release_position','coverage_start','receiver_end','pop_end'):
                        if key in screen:screen[key]=moved(screen[key])
                    coupled={**frame['coupled'],'positions':{k:moved(v) for k,v in frame['coupled']['positions'].items()},'deployments':{k:replace(v,perimeter_x_m=v.perimeter_x_m+shift) for k,v in frame['coupled']['deployments'].items()}}
                    frame.update(screen=screen,coupled=coupled,state={**frame['state'],'coupled':coupled},ball=moved(frame['ball']),start=moved(frame['start']),helper_position=moved(frame['helper_position']))
                    for o in options.values():
                        if 'target' in o:o['target']=moved(o['target']);o['coverage_position']=moved(o['coverage_position'])
                elif context=='defender_close':
                    target=options[name]['target'];frame['screen']={**frame['screen'],'coverage_release_position':(target[0]+.3,target[1]),'coverage_release_s':0}
                yield {'actor':actor,'family':name,'group':group,'context':context},frame,options


def predictions(write,read):
    criteria=read('stage-B-prespecified-criteria.json');rows=[]
    for metadata,frame,options in states():
        exact=action_choice.project_choices(frame,options)
        with approximation.enabled():coarse=action_choice.project_choices(frame,options)
        per=[];missing=[]
        for name,a in exact['candidates'].items():
            b=coarse['candidates'][name];ab=a.get('branches',{});bb=b.get('branches',{});branches=set(ab)|set(bb)
            errors={k:abs(ab.get(k,0)-bb.get(k,0)) for k in branches}
            missing.extend([[name,k,ab[k]] for k in ab if ab[k]>=.005 and not bb.get(k,0)])
            per.append({'candidate':name,'EP_error':abs(a['expected_points']-b['expected_points']),'max_branch_error':max(errors.values(),default=0),'branch_errors':errors})
        delta={k:coarse['effective_choice_probabilities'].get(k,0)-v for k,v in exact['effective_choice_probabilities'].items()};tv=.5*sum(abs(v) for v in delta.values())
        normalized=all(abs(sum(c['branches'].values())-1)<=1e-12 for c in coarse['candidates'].values() if 'branches' in c)
        passed=max(v['EP_error'] for v in per)<=.01 and max(v['max_branch_error'] for v in per)<=.01 and max(abs(v) for v in delta.values())<=.01 and tv<=.02 and not missing and normalized
        rows.append({**metadata,'exact':exact,'coarse':coarse,'errors':per,'effective_choice_differences':delta,'choice_TV':tv,'missing_material_branches':missing,'normalized':normalized,'passed':passed})
    write('stage-B-predictions.json',rows)
    summary={'mode':approximation.MODE,'states':len(rows),'all_passed':all(r['passed'] for r in rows),'failed_states':[{k:r[k] for k in ('actor','family','context','group')} for r in rows if not r['passed']],
        'max_EP_error':max(v['EP_error'] for r in rows for v in r['errors']),'max_branch_error':max(v['max_branch_error'] for r in rows for v in r['errors']),'max_effective_choice_error':max(abs(v) for r in rows for v in r['effective_choice_differences'].values()),'max_choice_TV':max(r['choice_TV'] for r in rows),'material_missing_branches':sum(len(r['missing_material_branches']) for r in rows),'development_passed':all(r['passed'] for r in rows if r['group']=='development'),'held_out_passed':all(r['passed'] for r in rows if r['group']=='held_out'),'tolerances_changed':False}
    write('stage-B-prediction-summary.json',summary)


def costs(write,measure):
    p=pool();rows=[]
    for actor in ('turner','jokic'):
        s,c,x=fixture(p,actor);variants={}
        for version in ('exact','coarse'):
            with approximation.enabled() if version=='coarse' else nullcontext():variants[version]=measure(lambda:sampling.run(s,per_seed=16,seeds=(17,)),actor+'-stageB-'+version)
        rows.append({'actor':actor,'versions':variants,'exact_to_coarse_speedup':variants['exact']['median_ms']/variants['coarse']['median_ms']});write('stage-B-costs.json',rows)


def mixed(write,read):
    if (OUT/'stage-B-mixed-started.json').exists():raise RuntimeError('StageB mixed budget consumed')
    previous=read('mixed-budget-final.json');write('stage-B-mixed-started.json',{'maximum_n':256,'previous_n':previous['n'],'previous_events':previous['events'],'previous_active_s':previous['active_s']});n=previous['n'];events=previous['events'];active=previous['active_s'];p=pool();rows=[]
    for actor in ('turner','towns','holmgren','jokic'):
        for context,kw in [('show',{}),('stay',{'coverage':'stay'})]:
            s,c,x=fixture(p,actor,**kw);variants={}
            for version in ('exact','coarse'):
                assert n+16<=2048 and events<8192 and active<60
                with approximation.enabled() if version=='coarse' else nullcontext():
                    start=time.perf_counter();r=sampling.run(s,per_seed=8,seeds=(17,29),max_events=8192-events,deadline=start+60-active);active+=time.perf_counter()-start
                n+=r['n'];events+=r['event_attempts'];variants[version]=r
            rows.append({'actor':actor,'context':context,'versions':variants,'paired_point_difference':sum(b-a for a,b in zip(variants['exact']['points'],variants['coarse']['points']))/len(variants['exact']['points'])});write('stage-B-mixed.json',rows)
    write('total-mixed-budget.json',{'n':n,'events':events,'active_s':active,'caps':{'n':2048,'events':8192,'active_s':60},'approximate_outcomes_expected_to_diverge':True})
