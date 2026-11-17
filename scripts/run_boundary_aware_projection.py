"""Bounded milestone14 experiment, exact reference retained; never activation.
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_boundary_aware_projection.py STAGE
"""
from contextlib import nullcontext
from dataclasses import replace
from collections import Counter
import argparse
import csv
import difflib
import gc
import hashlib
import json
import pstats
import statistics
import subprocess
import sys
import time
import tracemalloc
import weakref
from unittest.mock import patch
from nba_gm_data import action_choice,creation_passing,sim
from nba_gm_data.schema import to_plain
from nba_gm_data.interior_game import validate_accounting
from experiments.pass_recovery.fixtures import fixture,pool,IDS
from experiments.pass_recovery import sampling
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.boundary_aware_projection import predictor
from experiments.boundary_aware_projection.states import states
from experiments.boundary_aware_projection.verification import BASE,REFERENCE,OUT,ROOT,reference_modules,reference_config
import scripts.run_pass_recovery as prior_measure
import scripts.run_recovery_projection_cost as prior_cost


def write(name,data):(OUT/name).write_text(json.dumps(to_plain(data),indent=2,allow_nan=False)+'\n')
def read(name):return json.loads((OUT/name).read_text())
def plain(v):return json.loads(json.dumps(to_plain(v)))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def seal():
    if (OUT/'method-seal.json').exists():raise RuntimeError('Method already sealed')
    write('method-seal.json',{'mode':predictor.MODE,'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'experiments/boundary_aware_projection').glob('*.py')},'prespecification_sha256':sha(OUT/'prespecification.json'),'held_out_not_evaluated_yet':True})


def predictions(group):
    if group=='held_out':
        pin=read('method-seal.json');assert all(sha(ROOT/p)==h for p,h in pin['source_sha256'].items());assert sha(OUT/'prespecification.json')==pin['prespecification_sha256']
    rows=[]
    for meta,frame,options in states(group):
        exact=action_choice.project_choices(frame,options)
        with predictor.enabled():method=action_choice.project_choices(frame,options)
        errors=[];missing=[]
        for name,a in exact['candidates'].items():
            b=method['candidates'][name];ab=a.get('branches',{});bb=b.get('branches',{});keys=set(ab)|set(bb)
            err={k:abs(ab.get(k,0)-bb.get(k,0)) for k in keys};missing.extend([[name,k,v] for k,v in ab.items() if v>=.005 and not bb.get(k,0)])
            errors.append({'candidate':name,'EP_error':abs(a['expected_points']-b['expected_points']),'max_branch_error':max(err.values(),default=0),'branch_errors':err})
        delta={k:method['effective_choice_probabilities'].get(k,0)-v for k,v in exact['effective_choice_probabilities'].items()};tv=.5*sum(abs(v) for v in delta.values())
        normalized=all(abs(sum(c['branches'].values())-1)<=1e-12 for c in method['candidates'].values() if 'branches' in c)
        passed=max(v['EP_error'] for v in errors)<=.01 and max(v['max_branch_error'] for v in errors)<=.01 and max(abs(v) for v in delta.values())<=.01 and tv<=.02 and not missing and normalized
        rows.append({**meta,'exact':exact,'method':method,'errors':errors,'effective_choice_differences':delta,'choice_TV':tv,'material_missing_branches':missing,'normalized':normalized,'passed':passed})
        write('predictions-'+group+'.json',rows)
    summary={'mode':predictor.MODE,'group':group,'states':len(rows),'passed_states':sum(r['passed'] for r in rows),'max_EP_error':max(e['EP_error'] for r in rows for e in r['errors']),'max_branch_error':max(e['max_branch_error'] for r in rows for e in r['errors']),'max_effective_choice_error':max(abs(v) for r in rows for v in r['effective_choice_differences'].values()),'max_choice_TV':max(r['choice_TV'] for r in rows),'omitted_material_branches':sum(len(r['material_missing_branches']) for r in rows)}
    write('prediction-summary-'+group+'.json',summary);print(summary,flush=True)


def higher_resolution():
    selected={('towns','F03','clock_boundary'),('towns','pop','defender_close'),('turner','F04','defender_close'),('holmgren','F04','clock_boundary')};rows=[]
    for group in ('development','held_out'):
        for meta,f,o in states(group):
            if (meta['actor'],meta['family'],meta['context']) not in selected:continue
            base=action_choice.project_choices(f,o);higher={**f,'spec':replace(f['spec'],recovery=replace(f['spec'].recovery,integration_panels=8))};refined=action_choice.project_choices(higher,o,order=8);errors=[]
            for k,a in base['candidates'].items():
                b=refined['candidates'][k];ab=a.get('branches',{});bb=b.get('branches',{})
                errors.append({'candidate':k,'EP_difference':abs(a['expected_points']-b['expected_points']),'max_branch_difference':max((abs(ab.get(t,0)-bb.get(t,0)) for t in set(ab)|set(bb)),default=0)})
            rows.append({**meta,'reference_G4_panels4':base,'offline_G8_panels8':refined,'differences':errors,'scope':'finer deterministic resolution only; same outcome rules, not basketball ground truth or measured convergence proof'})
    assert len(rows)==4;write('higher-resolution-offline.json',rows)


def parity():
    with patch.object(prior_cost,'OUT',OUT),patch.object(prior_cost,'reference_modules',reference_modules),patch.object(prior_cost,'reference_config',reference_config):prior_cost.parity()


def mixed():
    if (OUT/'mixed-started.json').exists():raise RuntimeError('Natural budget consumed')
    write('mixed-started.json',read('prespecification.json')['natural']);p=pool();n=events=0;active=0.;rows=[]
    for actor in ('turner','towns','holmgren','jokic'):
        for context,kw in [('show',{}),('stay',{'coverage':'stay'}),('clock3',{'clock':3})]:
            s,c,x=fixture(p,actor,**kw);variants={}
            for version in ('exact','method'):
                assert n+32<=1024 and events<4096 and active<60
                with predictor.enabled() if version=='method' else nullcontext():
                    start=time.perf_counter();r=sampling.run(s,per_seed=16,seeds=(17,29),max_events=4096-events,deadline=start+60-active);active+=time.perf_counter()-start
                n+=r['n'];events+=r['event_attempts'];variants[version]=r
            checked=('n','events','choices','stages','planned_receipts','secured_receipts','receipt_event_breakdown','receipt_by_choice','points','event_attempts','maximum_attempts','truncated','per_seed')
            delta=[b-a for a,b in zip(variants['exact']['points'],variants['method']['points'])];mean=statistics.mean(delta);se=statistics.stdev(delta)/len(delta)**.5
            rows.append({'actor':actor,'context':context,'versions':variants,'physical_outcome_summaries_equal':all(variants['exact'][k]==variants['method'][k] for k in checked),'paired_point_difference':mean,'paired_MC95':[mean-1.96*se,mean+1.96*se]});write('mixed-results.json',rows)
    write('mixed-budget-final.json',{'n':n,'events':events,'active_s':active,'caps':{'n':1024,'events':4096,'active_s':60},'optional_reset_natural_followup_used':0,'all_physical_summaries_equal':all(r['physical_outcome_summaries_equal'] for r in rows),'scope':'paired supplied contexts with resets/rebounds; method diagnostics differ, no league calibration'})


def measure(fn,name):
    t=time.perf_counter();fn();cold=1000*(time.perf_counter()-t)
    with patch.object(prior_measure,'OUT',OUT):result=prior_measure.measure(fn,name)
    stats=pstats.Stats(str(OUT/(name+'.pstats'))).stats
    solver={name:sum(v[1] for k,v in stats.items() if k[2]==name and 'boundary_aware_projection/predictor.py' in k[0]) for name in ('__call__','certificate','terminal','fallback','candidate')}
    return {**result,'profiled_solver_calls':solver,'first_no_projection_cache_call_ms':cold,'boundary':'each candidate-local cache starts empty every call; five sequential warm samples include all certificate attempts/fallback, full diagnostics serialized separately'}


def costs():
    p=pool();rows=[]
    for actor in ('turner','jokic'):
        prep=time.perf_counter();s,c,x=fixture(p,actor);prepared_ms=1000*(time.perf_counter()-prep);versions={}
        hard,_,_=fixture(p,actor,enabled=False)
        versions['hard_window']=measure(lambda:sampling.run(hard,per_seed=16,seeds=(17,)),actor+'-hard')
        for version in ('exact','method'):
            with predictor.enabled() if version=='method' else nullcontext():versions[version]=measure(lambda:sampling.run(s,per_seed=16,seeds=(17,)),actor+'-'+version)
        rows.append({'fixture':actor+'_supplied16','preparation_ms':prepared_ms,'versions':versions,'speedup':versions['exact']['median_ms']/versions['method']['median_ms'],'vs_hard_window':versions['method']['median_ms']/versions['hard_window']['median_ms']});write('costs.json',rows)
    allstates=list(states('development'))+list(states('held_out'))
    boundary=[r for r in allstates if r[0]['origin']=='prior48' and r[0]['family']=='pop' and r[0]['context']!='reference']
    fallback=[r for r in allstates if r[0]['origin']=='prior48' and r[0]['family'] in ('F03','F04') and r[0]['context'] in ('clock_boundary','defender_close')][:12]
    actual=[r for r in allstates if r[0]['origin']=='prior48' and r[0]['context']=='reference']
    def resolve_held():
        values=[]
        for meta,f,o in actual:
            for error in (.1,.9):
                draws=observed_draws();draws[44]=.25;values.append(creation_passing.resolve_candidate(f,meta['family'],o,draws,{},delivery_error_override=error))
        return values
    for label,items in [('boundary12',boundary),('fallback12',fallback),('held24',actual)]:
        versions={}
        for version in ('exact','method'):
            with predictor.enabled() if version=='method' else nullcontext():versions[version]=measure(resolve_held if label=='held24' else lambda:[action_choice.project_choices(f,o) for _,f,o in items],label+'-'+version)
        if label=='held24':assert versions['exact']['result_sha256']==versions['method']['result_sha256']
        rows.append({'fixture':label,'versions':versions,'speedup':versions['exact']['median_ms']/versions['method']['median_ms']});write('costs.json',rows)
    for name,c,x in prior_cost.benchmarks():
        versions={}
        for version in ('exact','method'):
            with predictor.enabled() if version=='method' else nullcontext():versions[version]=measure(lambda:sim.sim_game_with_context(c,c['schedule'][0]['externalGameId'],seed=17,interior_experiment=x),name+'-'+version)
        assert versions['exact']['result_sha256']==versions['method']['result_sha256']
        rows.append({'fixture':name,'versions':versions});write('costs.json',rows)


def memory_release():
    p=pool();s,c,x=fixture(p,action='pop');d=creation_passing.prepare_drive_decision(s,IDS['curry'],'response_a','response_b',observed_draws(),24);memory=[]
    for version in ('exact','method'):
        with predictor.enabled() if version=='method' else nullcontext():
            action_choice.project_choices(d['frame'],d['options']);gc.collect();tracemalloc.start();live=[]
            for _ in range(4):r=action_choice.project_choices(d['frame'],d['options']);del r;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
            final,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        memory.append({'version':version,'post_cycle_live_bytes':live,'final_bytes':final,'peak_bytes':peak})
    del p,s,c,x,d;refs=[];live=[];gc.collect();tracemalloc.start()
    for _ in range(4):
        p=pool();s,c,x=fixture(p)
        with predictor.enabled():r=sampling.run(s,per_seed=2,seeds=(17,))
        refs.extend(weakref.ref(v) for v in (x,x.offense.creation,*p['views'].values()));del p,s,c,x,r;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
    final,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert all(ref() is None for ref in refs)
    write('memory-release.json',{'local_warm_projection':memory,'fixture_cycles':4,'tracked_roots':len(refs),'released_roots':sum(ref() is None for ref in refs),'post_cycle_live_bytes':live,'final_bytes':final,'peak_bytes':peak,'scope':'symmetric warm source/frame preparation outside projection trace; runtime has no GC changes or global cache'})


def tests():
    names='test_action_choice_consistency test_pilot_response_calibration test_experimental_input_pilot test_screen_navigation test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research test_expanded_cohort_performance test_pick_and_pop test_mixed_pop_validation test_pass_recovery test_recovery_projection_cost test_boundary_aware_projection'.split()
    with (OUT/'tests.txt').open('w') as f:r=subprocess.run([sys.executable,'-m','unittest',*names,'-q'],stdout=f,stderr=subprocess.STDOUT)
    assert r.returncode==0

def high_order_method():
    selected={('towns','F03','clock_boundary'),('towns','pop','defender_close'),('turner','F04','defender_close'),('holmgren','F04','clock_boundary')};rows=[]
    for group in ('development','held_out'):
        for meta,f,o in states(group):
            if (meta['actor'],meta['family'],meta['context']) not in selected:continue
            exact=action_choice.project_choices(f,o,order=8)
            with predictor.enabled():method=action_choice.project_choices(f,o,order=8)
            equal=exact['scores']==method['scores'] and exact['effective_choice_probabilities']==method['effective_choice_probabilities'] and all(v.get('branches')==method['candidates'][k].get('branches') and v['expected_points']==method['candidates'][k]['expected_points'] for k,v in exact['candidates'].items())
            assert equal;rows.append({**meta,'reference_order8_panels4':exact,'method_order8_panels4':method,'numerical_values_equal':equal})
    assert len(rows)==4;write('high-order-method-parity.json',rows)

def preparation():
    start=time.perf_counter();p=pool();pool_ms=1000*(time.perf_counter()-start);rows=[]
    for actor in ('turner','towns','holmgren','jokic'):
        start=time.perf_counter();s,c,x=fixture(p,actor);rows.append({'actor':actor,'fixture_config_profile_preparation_ms':1000*(time.perf_counter()-start),'configuration_revision':x.revision})
    write('preparation-costs.json',{'fixed_source_pool_load_ms':pool_ms,'fixtures':rows,'scope':'one first source/pool/config preparation outside forecast timings; no assertion of steady-state or app startup latency'})

def finalize():
    initial=json.loads((REFERENCE/'hashes.json').read_text());assert all(sha(ROOT/f)==h for f,h in initial.items())
    pins=json.loads((REFERENCE/'input-pins.json').read_text());assert all(sha(ROOT/f)==h for f,h in pins.items())
    sealed=read('method-seal.json');assert all(sha(ROOT/f)==h for f,h in sealed['source_sha256'].items());assert sha(OUT/'prespecification.json')==sealed['prespecification_sha256']
    test=(OUT/'tests.txt').read_text();assert 'Ran 331 tests' in test and test.rstrip().endswith('OK')
    rows=read('predictions-development.json')+read('predictions-held_out.json');totals=Counter();fallback=Counter();candidate_rows=[];state_rows=[]
    audits=[]
    for r in rows:
        a=[(name,v['boundary_solver']) for name,v in r['method']['candidates'].items() if 'boundary_solver' in v];audits.extend(v for _,v in a)
        for name,v in a:
            for key,value in v.items():
                if isinstance(value,int) and key!='max_depth':totals[key]+=value
            fallback.update(v['fallback_reasons'])
            candidate_rows.append({**{k:r[k] for k in ('group','actor','family','context')},'candidate':name,**{k:v.get(k,0) for k in ('reference_node_requests','full_resolver_calls','fast_terminal_nodes','certificate_checks','proof_budget_exhaustions','max_depth')},'fallback_reasons':json.dumps(v['fallback_reasons'],sort_keys=True)})
        state_rows.append({**{k:r[k] for k in ('group','actor','family','context')},'max_EP_error':max(e['EP_error'] for e in r['errors']),'max_branch_error':max(e['max_branch_error'] for e in r['errors']),'max_choice_error':max(abs(v) for v in r['effective_choice_differences'].values()),'choice_TV':r['choice_TV'],'omitted_material_branches':len(r['material_missing_branches']),'passed':r['passed']})
    for file,data in [('state-errors.csv',state_rows),('candidate-fallback-work.csv',candidate_rows)]:
        with (OUT/file).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    high=[v['boundary_solver'] for r in read('high-order-method-parity.json') for v in r['method_order8_panels4']['candidates'].values() if 'boundary_solver' in v]
    write('solver-work-summary.json',{'pass_candidate_forecasts':len(audits),'totals':dict(totals),'fallback_reasons':dict(fallback),'worst_default_reference_nodes':max(a['reference_node_requests'] for a in audits),'worst_high_order_reference_nodes':max(a['reference_node_requests'] for a in high),'worst_certificate_evaluations':max(a.get('certificate_checks',0) for a in audits+high),'worst_depth':max(a['max_depth'] for a in audits+high),'higher_order_states_checked':4,'scope':'node requests include retained original quadrature; unique certificate evaluations exclude repeated cache lookup requests, whose cost is included and separately profiled'})
    cost=read('costs.json');representative=cost[:2];accuracy=all(r['passed'] for r in rows);cost_pass=all(r['speedup']>=2.5 and r['vs_hard_window']<=4 for r in representative)
    budget=read('mixed-budget-final.json');assert budget['n']<=1024 and budget['events']<=4096 and budget['active_s']<=60
    assert len(read('full-result-rng-parity.json'))==48
    failure={'recommendation':'REJECT_FOR_PROMOTION','reference_accuracy_passed':accuracy,'cost_passed':cost_pass,'cost_failures':[{'fixture':r['fixture'],'speedup_actual':r['speedup'],'speedup_required':2.5,'hard_window_ratio_actual':r['vs_hard_window'],'hard_window_ratio_maximum':4} for r in representative],'offline_warning':'one accepted-reference versus refined branch difference exceeds.01; reference equality is not continuous-probability or basketball calibration','method_or_tolerances_changed_after_seal':False}
    assert accuracy and not cost_pass;write('failure-and-fallback-decision.json',failure)
    write('summary.json',{'milestone':14,'method':predictor.MODE,'recommendation':'REJECT_FOR_PROMOTION;retain milestone13 optimized exact','tests_passed':331,'baseline_tests':320,'new_tests':11,'held_out_and_development_states':64,'accuracy':{'development':read('prediction-summary-development.json'),'held_out':read('prediction-summary-held_out.json')},'full_result_rng_untouched_comparisons':48,'budget':budget,'solver_work':read('solver-work-summary.json'),'memory_release':read('memory-release.json'),'cost_acceptance':failure,'runtime_source_changes':0,'supported_input_changes':0,'outcome_coefficient_changes':0,'default_activation':False,'stop':'Coordinator review; no next algorithm/campaign/activation'})
    owned=list((ROOT/'experiments/boundary_aware_projection').glob('*.py'))+[ROOT/'scripts/run_boundary_aware_projection.py',ROOT/'tests/test_boundary_aware_projection.py',ROOT/'docs/BOUNDARY_AWARE_PROJECTION_ACTIVE_TASK.md',ROOT/'docs/BOUNDARY_AWARE_PROJECTION_REVIEW_2026_11_16.md']
    delta=[]
    for p in owned:
        if p.suffix=='.py':delta.extend(difflib.unified_diff([],p.read_text().splitlines(True),fromfile='/dev/null',tofile=str(p.relative_to(ROOT))))
    (OUT/'owned-code.diff').write_text(''.join(delta))
    write('integrity-audit.json',{'preedit_files':len(initial),'all_preedit_files_unchanged':True,'runtime_source_changes':0,'prior_accepted_pins':len(pins),'pins_unchanged':True,'method_seal_unchanged':True,'all94_dimensions_preserved':True,'git_unavailable':'existing host Xcode license; independent SHA256 used'})
    def files(folder):return {str(p.relative_to(ROOT)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p!=OUT/'handoff-manifest.json'}
    write('handoff-manifest.json',{'milestone':14,'status':'COMPLETE_FOR_REVIEW','recommendation':'reject experiment, retain optimized exact','owned_files':{str(p.relative_to(ROOT)):sha(p) for p in owned},'references':files(REFERENCE),'verified_outputs':files(OUT),'root_run_records':{str(p.relative_to(ROOT)):sha(p) for p in sorted(BASE.glob('*')) if p.is_file()},'stop':'No promotion, C37, activation or new work'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('development','seal','held_out','higher_resolution','high_order_method','parity','mixed','costs','preparation','memory_release','tests','finalize'));stage=parser.parse_args().stage;OUT.mkdir(exist_ok=True)
    predictions(stage) if stage in ('development','held_out') else globals()[stage]()
