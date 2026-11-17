"""One bounded sequential mixed-pop diagnosis/validation workload.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_mixed_pop_validation.py
"""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace,asdict
import argparse
import cProfile
import gc
import hashlib
import json
from pathlib import Path
import pstats
import statistics
import subprocess
import sys
import time
import tracemalloc
import weakref
from unittest.mock import patch

from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.experimental_inputs import InterpretedInputs,InputReader
from nba_gm_data.creation_passing import compile_interaction
from nba_gm_data.offense_response import compile_offense
from nba_gm_data.screen_navigation import compile_screen
from nba_gm_data.interior_game import validate_accounting
from experiments.mixed_pop_validation.diagnosis import ROOT,BASE,REFERENCE,reproduce,digest,plain
from experiments.mixed_pop_validation.fixtures import build_pool,fixture,ACTORS,IDS,REQUIRED,contexts,MIX
from experiments.mixed_pop_validation.scenarios import sensitivities,export_inputs
from experiments.mixed_pop_validation import sampling
from experiments.mixed_pop_validation.verification import reference_modules,reference_config,use_reference,prepare
from experiments.expanded_cohort_performance.checks import benchmarks,traced
from experiments.expanded_cohort_performance.pool import load_pool
from experiments.expanded_cohort_performance.fixtures import fixture as supplied
from experiments.pick_and_pop.fixtures import fixture as prior_fixture,pool as prior_pool,research_pool
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.action_choice_consistency.empirical import validate_candidate
from scripts.run_expanded_cohort_performance import costs
from scripts.run_player_input_pilot import core


def write(out,name,data):(out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def audit(p):
    original=InterpretedInputs.to_dict;seen=set();rows=[]
    class Rows(dict):
        def __getitem__(self,key):seen.add(key);return super().__getitem__(key)
        def get(self,key,default=None):seen.add(key);return super().get(key,default)
    def traced_doc(v):
        d=original(v);d['inputs']=Rows(d['inputs']);return d
    for actor in ACTORS:
        seen.clear();v=p['views'][IDS[actor]]
        with patch.object(InterpretedInputs,'to_dict',traced_doc):profiles=(compile_offense(v),compile_interaction(v),compile_screen(v,roles=('screener',),pop_routes=True))
        actual=seen-{'S42','S43'};assert actual==REQUIRED,(actor,actual^REQUIRED)
        src=p['source_documents'].get(v.player_id)
        rows.append({'actor':actor,'compiled_profiles':3,'same_authoritative_view':all(profile.inputs is v for profile in profiles),
            'actual_required_ids':sorted(actual),'source_supported_required':sum(src['inputs'][k]['status']!='unknown' for k in actual) if src else 0,
            'explicit_controls_required':sum(src['inputs'][k]['status']=='unknown' for k in actual) if src else len(actual),
            'synthetic':src is None,'offense_revision':profiles[0].revision,'interaction_revision':profiles[1].revision,'screen_revision':profiles[2].revision})
    return rows


def parity(out,p,modules):
    items=benchmarks(load_pool());_,c,x=prior_fixture(prior_pool());items.append(('milestone10_original_pop',c,x));_,c,x=prior_fixture(research_pool());items.append(('milestone10_research_pop',c,x))
    _,c,x=items[0];legacy=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,choice_policy='legacy_scores_v1',help_response_policy='legacy_timely_v1')))
    items.extend([('ordinary',c,None),('prior_legacy',c,legacy),('offense_without_creation',c,replace(x,offense=replace(x.offense,creation=None))),('interior_only',c,replace(x,offense=None))])
    for actor in ('turner','jokic'):
        _,c,x=fixture(p,actor);items.append(('new_mixed_'+actor,c,x))
    rows=[]
    for label,c,x in items:
        with use_reference(modules):old=reference_config(x,modules) if x else None
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                a,ta=traced(c,x,seed,mode)
                with use_reference(modules):b,tb=traced(c,old,seed,mode,modules['nba_gm_data.sim'])
                assert to_plain(a)==to_plain(b) and ta==tb,(label,seed,mode)
                rows.append({'case':label,'seed':seed,'mode':mode,'full_result_and_rng_equal':True,'result_sha256':digest(a),'rng_domains':ta,'possessions':a.possessions})
    write(out,'accepted-path-full-result-rng-parity.json',rows)
    return len(rows)


def conditional_diagnosis(out,p):
    saved=out/'original-selected-state-resampling.json'
    if saved.exists():
        cached=json.loads(saved.read_text());assert len(cached)==10 and all(r['observed']['n']==2048 and r['all_passed'] for r in cached)
        return
    rows=[]
    for seed,mode,index in [(17,'replay-real-minutes',3),(17,'sandbox-sim',7),(17,'sandbox-sim',23),(29,'replay-real-minutes',8),(29,'replay-real-minutes',10)]:
        import random
        from nba_gm_data.interior_defense import FORMULA_VERSION
        from nba_gm_data.creation_passing import prepare_drive_decision
        s,_,_=prior_fixture(prior_pool());rng=random.Random(f'{seed}:expanded_fixture:{mode}:{FORMULA_VERSION}:response_a:{index}:0');draws=[rng.random() for _ in range(48)]
        d=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',draws,24)
        for sample_seed in (17,29):
            r=validate_candidate(d,'pop',n=2048,seed=sample_seed);assert r['all_passed'];rows.append({'original_domain':[seed,mode,index],'independent_resample_seed':sample_seed,**r})
    write(out,'original-selected-state-resampling.json',rows)


def measured_batches(out,p,modules):
    rows=[]
    for actor in ACTORS[:-1]:
        s,c,x=fixture(p,actor)
        variants=[('current',s,None)]
        if actor in ('turner','jokic'):
            with use_reference(modules):old=reference_config(x,modules);st=prepare(c,old,modules)
            st['audit_context']=s['audit_context'];variants.insert(0,('accepted',st,modules))
        versions={}
        for label,state,m in variants:
            scope=use_reference(m) if m else nullcontext();hook=patch.object(sampling,'resolve_drive',m['nba_gm_data.creation_passing'].resolve_drive) if m else nullcontext()
            def batch():
                a=sampling.accumulator();sampling.add_trials(state,a,0,32);return sampling.finish(a)
            with scope,hook:
                batch();wall=[];serial=[]
                for _ in range(7):
                    t=time.perf_counter();r=batch();wall.append((time.perf_counter()-t)*1000)
                    t=time.perf_counter();payload=json.dumps(r,separators=(',',':'));serial.append((time.perf_counter()-t)*1000)
                prof=cProfile.Profile();prof.enable();batch();prof.disable()
            prof.dump_stats(str(out/f'batch-{actor}-{label}.pstats'))
            with (out/f'batch-{actor}-{label}-profile.txt').open('w') as f:pstats.Stats(prof,stream=f).sort_stats('cumulative').print_stats(55)
            stats=pstats.Stats(prof).stats
            calls={name:{'calls':sum(v[1] for k,v in stats.items() if k[2]==name),'inclusive_ms':1000*sum(v[3] for k,v in stats.items() if k[2]==name)} for name in ('resolve_drive','project_choices','project_candidate','resolve_candidate','plan_attack','screen_interception')}
            versions[label]={'median_ms':statistics.median(wall),'samples_ms':wall,'range_ms':[min(wall),max(wall)],'median_serialization_ms':statistics.median(serial),
                'diagnostic_payload_bytes':len(payload.encode()),'n':r['n'],'event_count':r['event_count'],'pop_selected':r['stages']['pop_selected'],'pop_shot_stage':r['stages']['pop_caught_and_shot_stage'],
                'profiled_calls':calls,'batch_sha256':digest(r),'projection_counts':r['projection_counts']}
        if 'accepted' in versions:assert versions['accepted']['batch_sha256']==versions['current']['batch_sha256']
        rows.append({'actor':actor,'versions':versions,'baseline_unavailable_reason':None if 'accepted' in versions else 'accepted compiler rejects exact reported protocol; never rewrite source to fabricate baseline',
            'scope':'fixed64 supplied possessions including resets/rebounds and audit counters, seven warm samples; not pure production kernel time or cross-player workload equivalence'})
    return rows


def release():
    refs=[];live=[];gc.collect();tracemalloc.start()
    for _ in range(4):
        p=build_pool();s,c,x=fixture(p,'towns');a=sampling.accumulator();sampling.add_trials(s,a,0,4)
        refs.extend(weakref.ref(v) for v in (x,x.offense.creation,x.offense.creation.screens,*p['views'].values()))
        del p,s,c,x,a;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
    cur,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert all(r() is None for r in refs)
    return {'cycles':4,'roots':len(refs),'released_roots':sum(r() is None for r in refs),'post_cycle_live_bytes':live,'final_bytes':cur,'peak_bytes':peak,'scope':'audit GC only; no runtime global cache/GC or diagnostic deletion'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=BASE/'verified');out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    p=build_pool();modules=reference_modules()
    prespec={'main_actors':list(ACTORS),'contexts':contexts(),'T11_shared_context_control':MIX,'seeds':[17,29],
        'minimum_possessions_per_seed_context':256,'adaptive_increment_per_seed':128,'maximum_per_seed_context':768,'target_selected_pops_per_context':40,
        'adaptation':'stop at target, maximum, no observed eligibility at minimum, or global cap; never adapt on makes or named ordering',
        'main_maximum':46080,'sensitivity_fixed_contexts':16,'sensitivity_possessions_per_context':256,'passing_contexts':2,'passing_possessions_per_context':256,
        'optional_finished_research_max_possessions':4096,'aggregate_natural_trial_cap':60000,'aggregate_continuation_event_cap':180000,'natural_wall_cap_s':180,
        'attempt_audit_abort_cap':20,'original_state_conditional_resampling':10*2048,'preflight_and_regression':'separately bounded functional checks; not inference samples'}
    write(out,'prespecified-budget-and-contexts.json',prespec);write(out,'original-failure-trace.json',reproduce());write(out,'input-layers-and-control-ledger.json',export_inputs(p));write(out,'actual-compiler-dependencies.json',audit(p))
    conditional_diagnosis(out,p);print('original ten traces and conditional resampling complete',flush=True)
    interrupted_path=BASE/'interrupted-work.json';interrupted=json.loads(interrupted_path.read_text()) if interrupted_path.exists() else {}
    natural_start=time.perf_counter();total=interrupted.get('discarded_possessions',0);events=0;previous_wall=interrupted.get('wall_s',0);main_rows=[];capped=[];discarded_events=0
    def budget_ok(minimum=256):return total+minimum<=60000 and events<180000 and previous_wall+time.perf_counter()-natural_start<180
    for actor in ACTORS:
        for name,kw in contexts():
            if not budget_ok(512):capped.append([actor,name]);continue
            s,_,x=fixture(p,actor,**kw);r=sampling.run_case(s,remaining_seconds=max(0,180-previous_wall-(time.perf_counter()-natural_start)))
            total+=r['n'];events+=r['event_count'];main_rows.append({'actor':actor,'context':name,'controls':kw,'configuration_revision':x.revision,'result':r})
            if [actor,name] in interrupted.get('discarded_contexts',[]):
                # Exact deterministic replay recovers the interrupted event
                # count; only zero-counter serialization changed after failure.
                events+=r['event_count'];discarded_events+=r['event_count']
            write(out,'natural-mixed-possession-results.json',main_rows)
            print(actor,name,r['n'],'selected',r['stages']['pop_selected'],'shot_stage',r['stages']['pop_caught_and_shot_stage'],flush=True)
    write(out,'natural-mixed-possession-results.json',main_rows)
    sensitivity=[]
    for name,actor,q,kw in sensitivities(p):
        if not budget_ok():capped.append(['sensitivity',name]);continue
        s,_,_=fixture(q,actor,**kw);r=sampling.run_case(s,adaptive=False,minimum_per_seed=128)
        total+=r['n'];events+=r['event_count'];sensitivity.append({'name':name,'actor':actor,'context':kw,'overrides':q['overrides'],'result':r})
    write(out,'source-versus-control-sensitivity.json',sensitivity)
    passing=[]
    for name,start in [('available',(1.2,2.7)),('later_pressure',(1.2,1.7))]:
        if not budget_ok():capped.append(['passing',name]);continue
        s,c,x=supplied(p,creator='jokic',receiver='curry',partner='wemb',poa='turner',helper='barnes',other='brunson',families=('F04','F06'),screen_separation=.5,ball=start)
        r=sampling.run_case(s,adaptive=False,minimum_per_seed=128);total+=r['n'];events+=r['event_count'];passing.append({'context':name,'scope':'supplied Jokic high-post/short-advance lob and outlet; no post establishment or guard-diet ranking','result':r})
    write(out,'supplied-jokic-passing-contrasts.json',passing)
    write(out,'natural-budget-consumption.json',{'supplied_possessions_including_interrupted_work':total,'discarded_interrupted_possessions':interrupted.get('discarded_possessions',0),
        'event_attempts_including_interrupted_work':events,'discarded_interrupted_events':discarded_events,'wall_s_including_interruption':previous_wall+time.perf_counter()-natural_start,
        'capped_or_unrun':capped,'truncated_possessions':sum(r['result']['truncated'] for r in main_rows+sensitivity+passing)})
    print('natural mixed and sensitivity workload complete',flush=True)
    parity_count=parity(out,p,modules)
    new_kernel=[]
    for actor in ACTORS[:-1]:
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                _,c,x=fixture(p,actor);a,ta=traced(c,x,seed,mode);b,tb=traced(c,x,seed,mode);assert to_plain(a)==to_plain(b) and ta==tb;validate_accounting(a)
                write(out,f'kernel-{actor}-{seed}-{mode}.json',to_plain(a));new_kernel.append({'actor':actor,'seed':seed,'mode':mode,'accounting_and_determinism_passed':True,'actual_possessions_per_side':a.possessions,'result_sha256':digest(a),'rng_domains':ta})
    write(out,'four-actor-kernel-accounting-rng.json',new_kernel)
    write(out,'legacy-equivalent-budget-costs.json',costs(out,load_pool(),modules));write(out,'fixed-mixed-possession-costs.json',measured_batches(out,p,modules));write(out,'ownership-release.json',release())
    suites=['test_action_choice_consistency','test_pilot_response_calibration','test_experimental_input_pilot','test_screen_navigation','test_creation_passing','test_offense_interior_interaction','test_interior_defense_experiment','test_player_model_schema','test_defensive_alignment','test_narrative_simulation','test_historical_shooting_parser','test_guarantee_research','test_expanded_cohort_performance','test_pick_and_pop','test_mixed_pop_validation']
    check=subprocess.run([sys.executable,'-m','unittest',*suites,'-q'],cwd=ROOT,text=True,capture_output=True);(out/'tests.txt').write_text(check.stdout+check.stderr);assert check.returncode==0,check.stdout+check.stderr
    write(out,'summary.json',{'status':'mixed-pop bounded run finished; review outcomes and final research integration before handoff','main_contexts':len(main_rows),
        'main_possessions':sum(r['result']['n'] for r in main_rows),'sensitivity_contexts':len(sensitivity),'passing_contexts':len(passing),
        'natural_total_possessions':total,'natural_total_events':events,'capped':capped,'original_unique_selected_domains':5,'original_reported_attempts':10,
        'accepted_full_result_rng_comparisons':parity_count,'new_kernel_cases':len(new_kernel),'baseline_tests':257,'new_tests':16,'total_tests':273,
        'runtime_change':'exact reported cm/kg protocol alias only; no outcome or rating changes','activation':'default OFF','final_research_integration':'not inspected until final delivered checkpoint check; no polling/hotload'})
    print('bounded run and273 tests complete',flush=True)


if __name__=='__main__':main()
