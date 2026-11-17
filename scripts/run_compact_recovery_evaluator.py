"""Milestone15 compact numerical evaluator; bounded sequential experiment.
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_compact_recovery_evaluator.py STAGE
"""
from collections import Counter
from contextlib import nullcontext
from dataclasses import replace
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
from nba_gm_data import creation_passing,action_choice,sim
from nba_gm_data.schema import to_plain
from experiments.pass_recovery.fixtures import pool,fixture,IDS
from experiments.pass_recovery import sampling
from experiments.compact_recovery_evaluator.verification import BASE,REFERENCE,OUT,ROOT,reference_modules,reference_config
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.boundary_aware_projection.states import states
from experiments.expanded_cohort_performance.checks import benchmarks,digest
from nba_gm_data.interior_game import validate_accounting
import scripts.run_pass_recovery as prior
import scripts.run_boundary_aware_projection as m14


def write(name,data):(OUT/name).write_text(json.dumps(to_plain(data),indent=2,allow_nan=False)+'\n')
def read(name):return json.loads((OUT/name).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def measure(fn,name):
    with patch.object(prior,'OUT',OUT):return prior.measure(fn,name)


def baseline():
    rows=[];p=pool()
    for actor in ('turner','jokic'):
        s,c,x=fixture(p,actor);r=measure(lambda:sampling.run(s,per_seed=16,seeds=(17,)),actor+'-baseline')
        stats=pstats.Stats(str(OUT/(actor+'-baseline.pstats'))).stats
        exclusive={}
        for name,path in [('resolver','creation_passing.py'),('geometry','pass_recovery.py'),('shot_planning','offense_response.py'),('contest','shot_geometry.py'),('dataclass_machinery','dataclasses.py'),('interpretation','experimental_inputs.py')]:
            exclusive[name]={'self_ms':1000*sum(v[2] for k,v in stats.items() if k[0].endswith(path)),'calls':sum(v[1] for k,v in stats.items() if k[0].endswith(path))}
        original=creation_passing.resolve_candidate;counts=Counter();times=Counter()
        def observed(frame,name,options,draws,record,**kw):
            t=time.perf_counter();result=original(frame,name,options,draws,record,**kw);elapsed=time.perf_counter()-t
            key=('hypothetical' if not kw.get('include_details',True) else 'selected')+':'+result['kind']+':'+result['record'].get('receipt_category','finish_or_old')
            counts[key]+=1;times[key]+=elapsed;return result
        with patch.object(creation_passing,'resolve_candidate',observed):
            t=time.perf_counter();sampling.run(s,per_seed=16,seeds=(17,));attribution_wall=time.perf_counter()-t
        rows.append({'actor':actor,'benchmark':r,'exclusive_profile_groups':exclusive,'mutually_exclusive_node_categories':{k:{'calls':v,'inclusive_ms':times[k]*1000} for k,v in counts.items()},'attribution_wall_ms':attribution_wall*1000,'scope':'category node times do not overlap each other; category totals include nested geometry/planning, so never add them to exclusive profile totals; diagnostic attribution overhead not a performance sample'})
        write('baseline-attribution.json',rows);print('baseline',actor,flush=True)

def development():
    from experiments.compact_recovery_evaluator import python_core
    folder=OUT/'python';folder.mkdir(exist_ok=True)
    with patch.object(m14,'OUT',folder),patch.object(m14,'predictor',python_core):m14.predictions('development')

def native_development():
    from experiments.compact_recovery_evaluator import python_core
    class Native:
        MODE='compact_native_geometry_v1'
        enabled=staticmethod(python_core.native_enabled)
    folder=OUT/'native';folder.mkdir(exist_ok=True)
    with patch.object(m14,'OUT',folder),patch.object(m14,'predictor',Native):m14.predictions('development')
    s=json.loads((folder/'prediction-summary-development.json').read_text());assert max(s[k] for k in ('max_EP_error','max_branch_error','max_effective_choice_error','max_choice_TV'))<=1e-9 and not s['omitted_material_branches']

def native_costs():
    from experiments.compact_recovery_evaluator import python_core
    p=pool();rows=[]
    for actor in ('turner','jokic'):
        s,c,x=fixture(p,actor);versions={}
        for version,scope in [('exact',nullcontext),('compact_python',python_core.enabled),('compact_native',python_core.native_enabled)]:
            with scope():versions[version]=measure(lambda:sampling.run(s,per_seed=16,seeds=(17,)),actor+'-second-'+version)
        rows.append({'actor':actor,'versions':versions,'native_vs_exact':versions['exact']['median_ms']/versions['compact_native']['median_ms'],'native_vs_python':versions['compact_python']['median_ms']/versions['compact_native']['median_ms']});write('initial-native-compact-costs.json',rows)

def compact_costs():
    from experiments.compact_recovery_evaluator import python_core
    p=pool();rows=[]
    for actor in ('turner','jokic'):
        s,c,x=fixture(p,actor);versions={}
        for version in ('exact','compact_python'):
            with python_core.enabled() if version=='compact_python' else nullcontext():versions[version]=measure(lambda:sampling.run(s,per_seed=16,seeds=(17,)),actor+'-'+version)
        rows.append({'actor':actor,'versions':versions,'speedup':versions['exact']['median_ms']/versions['compact_python']['median_ms']});write('initial-python-compact-costs.json',rows)

def build_native():
    from experiments.compact_recovery_evaluator.build_native import build
    print(build())

def direct_pairs():
    from experiments.compact_recovery_evaluator.diagnostics import direct_pairs as run
    run(write)

def sanitize():
    from experiments.compact_recovery_evaluator.build_native import sanitize
    print(sanitize())

def seal():
    assert read('direct-pair-summary.json')['failures']==0
    assert not (OUT/'method-seal.json').exists()
    files=[p for p in (ROOT/'experiments/compact_recovery_evaluator').rglob('*') if p.suffix in ('.py','.c')]
    pin={'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},'shared_runtime_sha256':{f'src/nba_gm_data/{n}.py':sha(ROOT/f'src/nba_gm_data/{n}.py') for n in ('shot_geometry','pass_recovery')},'prespecification_sha256':sha(OUT/'prespecification.json'),'held_out_not_evaluated_yet':True}
    write('method-seal.json',pin)
    for mode in ('python','native'):
        folder=OUT/mode;folder.mkdir(exist_ok=True);(folder/'prespecification.json').write_bytes((OUT/'prespecification.json').read_bytes());(folder/'method-seal.json').write_text(json.dumps(pin,indent=2)+'\n')

def held_out():
    from experiments.compact_recovery_evaluator import python_core
    pin=read('method-seal.json');assert all(sha(ROOT/f)==h for f,h in {**pin['source_sha256'],**pin['shared_runtime_sha256']}.items())
    class Native:
        MODE='compact_native_geometry_v1'
        enabled=staticmethod(python_core.native_enabled)
    for mode,implementation in [('python',python_core),('native',Native)]:
        folder=OUT/mode
        with patch.object(m14,'OUT',folder),patch.object(m14,'predictor',implementation):m14.predictions('held_out')
        s=json.loads((folder/'prediction-summary-held_out.json').read_text());maximum=max(s[k] for k in ('max_EP_error','max_branch_error','max_effective_choice_error','max_choice_TV'))
        assert maximum<=(0 if mode=='python' else 1e-9) and not s['omitted_material_branches']

def native_failure_trace():
    from experiments.compact_recovery_evaluator import python_core
    from experiments.compact_recovery_evaluator.diagnostics import packet
    from experiments.boundary_aware_projection.states import states
    meta,f,o=next(r for r in states('held_out') if r[0]['actor']=='holmgren' and r[0]['family']=='F04' and r[0]['context']=='reference')
    original=python_core.CompactResolver.__call__;runs={}
    for backend in ('python','native'):
        records={}
        def observed(self,frame,name,options,draws,record,**kwargs):
            a=original(self,frame,name,options,draws,record,**kwargs);key=(kwargs.get('delivery_error_override'),min(5,int(draws[44]*6)))
            records[key]={'packet':packet(a),'legacy':bool(frame.get('_legacy_delivery'))}
            return a
        with patch.object(python_core.CompactResolver,'__call__',observed),patch.object(action_choice,'project_candidate',lambda frame,name,options,order=4:python_core.candidate(frame,name,options,order=order,backend=backend)):
            result=python_core.candidate(f,'F04',o,backend=backend)
        runs[backend]={'result':result,'nodes':records}
    differences=[]
    for key,a in runs['python']['nodes'].items():
        b=runs['native']['nodes'][key]
        if a['packet']!=b['packet']:
            differences.append({'error_m':key[0],'direction':key[1],'python':a,'native':b})
    write('native-heldout-failure-trace.json',{'scene':meta,'different_nodes':differences,'python_projection':runs['python']['result'],'native_projection':runs['native']['result'],'scope':'repeated known failing state to diagnose, no sealed code/threshold/input changes'})

def acceptance():
    pin=read('method-seal.json');assert all(sha(ROOT/f)==h for f,h in {**pin['source_sha256'],**pin['shared_runtime_sha256']}.items());out={}
    for mode in ('python','native'):
        rows=[]
        for group in ('development','held_out'):rows+=json.loads((OUT/mode/('predictions-'+group+'.json')).read_text())
        records=[];limit=0 if mode=='python' else 1e-9
        for r in rows:
            ep=max(e['EP_error'] for e in r['errors']);branch=max(e['max_branch_error'] for e in r['errors']);choice=max(abs(v) for v in r['effective_choice_differences'].values());tv=r['choice_TV']
            records.append({**{k:r[k] for k in ('actor','family','context','group','origin')},'max_EP_error':ep,'max_branch_error':branch,'max_effective_choice_error':choice,'choice_TV':tv,'omissions':len(r['material_missing_branches']),'strict_passed':max(ep,branch,choice,tv)<=limit and not r['material_missing_branches'] and r['normalized']})
        available=mode=='python' or (read('native-build.json')['available'] and any(v.get('compact_evaluator',{}).get('native_geometry',{}).get('native_geometry_nodes',0)>0 for r in rows for v in r['method']['candidates'].values() if v.get('compact_evaluator',{}).get('native_geometry') is not None))
        result={'mode':mode,'states':len(records),'strict_limit':limit,'strict_passed_states':sum(r['strict_passed'] for r in records),'numerical_passed':all(r['strict_passed'] for r in records),'native_available_and_exercised':available,'passed':all(r['strict_passed'] for r in records) and available,'failures':[r for r in records if not r['strict_passed']],'max_EP_error':max(r['max_EP_error'] for r in records),'max_branch_error':max(r['max_branch_error'] for r in records),'max_choice_error':max(r['max_effective_choice_error'] for r in records),'max_TV':max(r['choice_TV'] for r in records),'source_seal_unchanged':True}
        write(mode+'/strict-acceptance.json',result);write(mode+'/strict-error-table.json',records);out[mode]=result
    assert out['python']['passed'];write('numerical-acceptance.json',out)

def parity():
    with patch.object(m14,'OUT',OUT),patch.object(m14,'reference_modules',reference_modules),patch.object(m14,'reference_config',reference_config):m14.parity()

def high_order():
    from experiments.compact_recovery_evaluator import python_core
    selected={('towns','F03','clock_boundary'),('towns','pop','defender_close'),('turner','F04','defender_close'),('holmgren','F04','clock_boundary')};rows=[]
    for group in ('development','held_out'):
        for meta,f,o in states(group):
            if (meta['actor'],meta['family'],meta['context']) not in selected:continue
            exact=action_choice.project_choices(f,o,order=8)
            with python_core.enabled():compact=action_choice.project_choices(f,o,order=8)
            equal=exact['scores']==compact['scores'] and exact['effective_choice_probabilities']==compact['effective_choice_probabilities'] and all(v.get('branches')==compact['candidates'][k].get('branches') and v['expected_points']==compact['candidates'][k]['expected_points'] for k,v in exact['candidates'].items());assert equal
            rows.append({**meta,'exact':exact,'compact_python':compact,'numerical_values_exactly_equal':equal})
    write('high-order-python-parity.json',rows)
    with patch.object(m14,'OUT',OUT):m14.higher_resolution()

def mixed():
    from experiments.compact_recovery_evaluator import python_core
    gate=read('numerical-acceptance.json');assert gate['python']['passed']
    if (OUT/'mixed-started.json').exists():raise RuntimeError('New natural budget already consumed')
    versions=[('exact',nullcontext),('compact_python',python_core.enabled)]
    if gate['native']['passed']:versions.append(('compact_native',python_core.native_enabled))
    write('mixed-started.json',{'prespecification':read('prespecification.json')['natural'],'native_included':gate['native']['passed'],'native_exclusion_reason':None if gate['native']['passed'] else 'failed prespecified1e-9 numerical gate; no native inference campaign'})
    p=pool();n=events=0;active=0.;rows=[]
    for actor in ('turner','towns','holmgren','jokic'):
        for context,kw in [('show',{}),('stay',{'coverage':'stay'}),('clock3',{'clock':3})]:
            s,c,x=fixture(p,actor,**kw);result={}
            for version,scope in versions:
                assert n+32<=1536 and events<6144 and active<60
                with scope():
                    start=time.perf_counter();r=sampling.run(s,per_seed=16,seeds=(17,29),max_events=6144-events,deadline=start+60-active);active+=time.perf_counter()-start
                n+=r['n'];events+=r['event_attempts'];result[version]=r
            a=result['exact'];checked=('events','choices','stages','planned_receipts','secured_receipts','receipt_event_breakdown','receipt_by_choice','points','event_attempts','per_seed');equal={k:all(a[f]==r[f] for f in checked) for k,r in result.items() if k!='exact'}
            differences={}
            for k,r in result.items():
                if k=='exact':continue
                delta=[b-v for v,b in zip(a['points'],r['points'])];mean=statistics.mean(delta);se=statistics.stdev(delta)/len(delta)**.5;differences[k]={'mean':mean,'nominal_paired_MC95':[mean-1.96*se,mean+1.96*se]}
            rows.append({'actor':actor,'context':context,'versions':result,'physical_summary_equal':equal,'paired_points':differences});write('mixed-results.json',rows)
    write('mixed-budget-final.json',{'n':n,'events':events,'active_s':active,'caps':{'n':1536,'events':6144,'active_s':60},'native_included':gate['native']['passed'],'optional_followup_n':0,'all_python_physical_summaries_equal':all(r['physical_summary_equal']['compact_python'] for r in rows)})

def final_measure(fn,label):
    t=time.perf_counter();fn();cold=1000*(time.perf_counter()-t);r=measure(fn,label)
    return {**r,'first_call_ms':cold,'scope':'all candidate packing,conversion,reconstruction,fallback and full retained diagnostics inside; serialization separate; no candidate cache reused between forecasts'}

def costs():
    from experiments.compact_recovery_evaluator import python_core
    scopes=[('exact',nullcontext),('compact_python',python_core.enabled),('compact_native_rejected',python_core.native_enabled)];p=pool();rows=[]
    for label,actor,kw in [('turner16','turner',{}),('jokic16','jokic',{}),('clock3_16','turner',{'clock':3})]:
        t=time.perf_counter();s,c,x=fixture(p,actor,**kw);prep=1000*(time.perf_counter()-t);versions={}
        if label!='clock3_16':
            hard,_,_=fixture(p,actor,enabled=False,**kw);versions['hard_window']=final_measure(lambda:sampling.run(hard,per_seed=16,seeds=(17,)),label+'-hard')
        for version,scope in scopes:
            with scope():versions[version]=final_measure(lambda:sampling.run(s,per_seed=16,seeds=(17,)),label+'-'+version)
        rows.append({'fixture':label,'preparation_ms':prep,'versions':versions,'native_purpose':'timing failed prototype only; native excluded from inference campaign'});write('final-costs.json',rows)
    allstates=list(states('development'))+list(states('held_out'));boundary=[v for v in allstates if v[0]['origin']=='prior48' and v[0]['family']=='pop' and v[0]['context']!='reference'];fallback=[v for v in allstates if v[0]['origin']=='prior48' and v[0]['family'] in ('F03','F04') and v[0]['context'] in ('clock_boundary','defender_close')][:12];held=[v for v in allstates if v[0]['origin']=='prior48' and v[0]['context']=='reference']
    def held_actions():
        result=[]
        for meta,f,o in held:
            for error in (.1,.9):
                draws=observed_draws();draws[44]=.25;result.append(creation_passing.resolve_candidate(f,meta['family'],o,draws,{},delivery_error_override=error))
        return result
    for label,items in [('boundary12',boundary),('fallback12',fallback),('held24',held)]:
        versions={}
        for version,scope in scopes:
            with scope():versions[version]=final_measure(held_actions if label=='held24' else lambda:[action_choice.project_choices(f,o) for _,f,o in items],label+'-'+version)
        if label=='held24':assert len({v['result_sha256'] for v in versions.values()})==1
        rows.append({'fixture':label,'versions':versions});write('final-costs.json',rows)
    for label,c,x in benchmarks():
        versions={}
        for version,scope in scopes:
            with scope():versions[version]=final_measure(lambda:sim.sim_game_with_context(c,c['schedule'][0]['externalGameId'],seed=17,interior_experiment=x),label+'-'+version)
        assert len({v['result_sha256'] for v in versions.values()})==1;rows.append({'fixture':label,'versions':versions});write('final-costs.json',rows)

def memory_release():
    from experiments.compact_recovery_evaluator import python_core
    p=pool();s,c,x=fixture(p,action='pop');d=creation_passing.prepare_drive_decision(s,IDS['curry'],'response_a','response_b',observed_draws(),24);local=[]
    for mode,scope in [('exact',nullcontext),('compact_python',python_core.enabled),('compact_native_rejected',python_core.native_enabled)]:
        with scope():
            action_choice.project_choices(d['frame'],d['options']);gc.collect();tracemalloc.start();live=[]
            for _ in range(4):r=action_choice.project_choices(d['frame'],d['options']);del r;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
            final,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        local.append({'mode':mode,'post_cycle_live_bytes':live,'retained_bytes':final,'peak_bytes':peak})
    del p,s,c,x,d;refs=[];live=[];gc.collect();tracemalloc.start()
    for _ in range(4):
        p=pool();s,c,x=fixture(p)
        with python_core.enabled():r=sampling.run(s,per_seed=2,seeds=(17,))
        refs.extend(weakref.ref(v) for v in (x,x.offense.creation,*p['views'].values()));del p,s,c,x,r;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
    final,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert all(ref() is None for ref in refs)
    write('memory-release.json',{'local_projection':local,'cycles':4,'roots':len(refs),'released_roots':sum(ref() is None for ref in refs),'post_cycle_live_bytes':live,'retained_bytes':final,'peak_bytes':peak,'scope':'symmetric warm preparation outside local trace; native static code handle retained, no native input/result graph; runtime no GC changes'})

def tests():
    names='test_action_choice_consistency test_pilot_response_calibration test_experimental_input_pilot test_screen_navigation test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research test_expanded_cohort_performance test_pick_and_pop test_mixed_pop_validation test_pass_recovery test_recovery_projection_cost test_boundary_aware_projection test_compact_recovery_evaluator'.split()
    with (OUT/'tests.txt').open('w') as f:r=subprocess.run([sys.executable,'-m','unittest',*names,'-q'],stdout=f,stderr=subprocess.STDOUT)
    assert r.returncode==0

def adapter_costs():
    from experiments.compact_recovery_evaluator import native_adapter
    observations=[];p=pool()
    for actor,action,name in [('turner','pop','pop'),('jokic','slip','F04')]:
        s,c,x=fixture(p,actor,action=action);d=creation_passing.prepare_drive_decision(s,IDS['curry'],'response_a','response_b',observed_draws(),24);frame=d['frame'];option=d['options'][name];lib=native_adapter.library();samples=[]
        if lib is None:write('adapter-costs.json',{'available':False,'reason':'native unavailable'});return
        class Timed:
            def compact_geometry_batch(self,*args):
                nonlocal ffi_s
                t=time.perf_counter();r=lib.compact_geometry_batch(*args);ffi_s+=time.perf_counter()-t;return r
        for _ in range(5):
            ffi_s=0.
            with patch.object(native_adapter,'library',return_value=Timed()):
                t=time.perf_counter();batch=native_adapter.GeometryBatch(frame,name,option,4);total=time.perf_counter()-t
            t=time.perf_counter()
            for direction,error in batch.keys:batch.geometry(frame,name,option,error,direction)
            decode=time.perf_counter()-t
            samples.append({'candidate_pack_and_batch_ms':total*1000,'ffi_and_C_ms':ffi_s*1000,'packing_validation_CDF_arrays_except_ffi_ms':(total-ffi_s)*1000,'reconstruction_plus_Python_repairs_ms':decode*1000,'nodes':len(batch.keys),'counts':dict(batch.counts),'owned_numeric_buffer_bytes':sum(__import__('ctypes').sizeof(v) for v in (batch.inputs,batch.errors,batch.directions,batch.output))})
        observations.append({'actor':actor,'candidate':name,'samples':samples,'scope':'same prepared candidate,5fresh input/output packets; nested C duration shown separately, do not add it to inclusive pack+batch; reconstruction includes all marked Python repairs, not claimed pure conversion'});
    write('adapter-costs.json',{'available':True,'observations':observations})
    from experiments.compact_recovery_evaluator.build_native import LIB
    child='import ctypes,json,time; t=time.perf_counter(); lib=ctypes.PyDLL('+repr(str(LIB))+'); print(json.dumps({"load_s":time.perf_counter()-t,"abi":lib.compact_geometry_abi()}))'
    loads=[]
    for _ in range(3):
        t=time.perf_counter();run=subprocess.run([sys.executable,'-c',child],capture_output=True,text=True,timeout=10);run.check_returncode();loads.append({**json.loads(run.stdout),'child_wall_s':time.perf_counter()-t})
    metadata={}
    for key,args in [('file',['/usr/bin/file',str(LIB)]),('links',['/Library/Developer/CommandLineTools/usr/bin/otool','-L',str(LIB)]),('build_version',['/Library/Developer/CommandLineTools/usr/bin/otool','-l',str(LIB)])]:
        result=subprocess.run(args,capture_output=True,text=True,timeout=10)
        if key=='build_version':
            lines=result.stdout.splitlines();i=next((i for i,v in enumerate(lines) if 'LC_BUILD_VERSION' in v),None);metadata[key]='\n'.join(lines[i:i+8]) if i is not None else result.stderr
        else:metadata[key]=result.stdout+result.stderr
    write('native-load-platform.json',{'fresh_process_observations':loads,'initial_build_load':read('native-build.json')['first_observed_load_s'],'metadata':metadata,'scope':'no cachepurge/hostchanges; first observed load differs from later OS-cache observations; arm64macOS prototype only, packaging/Windows/Intel/ASan unverified'})

def preparation():
    t=time.perf_counter();p=pool();load=1000*(time.perf_counter()-t);rows=[]
    for actor in ('turner','towns','holmgren','jokic'):
        t=time.perf_counter();s,c,x=fixture(p,actor);rows.append({'actor':actor,'fixture_profile_config_ms':1000*(time.perf_counter()-t),'configuration_revision':x.revision})
    write('preparation-costs.json',{'source_pool_load_ms':load,'fixtures':rows,'scope':'outside execution timers,one first observation,no app startup claim'})

def finalize():
    initial=json.loads((REFERENCE/'hashes.json').read_text());changed={f for f,h in initial.items() if sha(ROOT/f)!=h};assert changed=={'src/nba_gm_data/shot_geometry.py','src/nba_gm_data/pass_recovery.py'},changed
    pins=json.loads((REFERENCE/'input-pins.json').read_text());assert all(sha(ROOT/f)==h for f,h in pins.items())
    seal=read('method-seal.json');assert all(sha(ROOT/f)==h for f,h in {**seal['source_sha256'],**seal['shared_runtime_sha256']}.items());assert sha(OUT/'prespecification.json')==seal['prespecification_sha256']
    from experiments.compact_recovery_evaluator.build_native import LIB,SOURCE
    build=read('native-build.json');assert sha(LIB)==build['binary_sha256'] and sha(SOURCE)==build['source_sha256']
    test=(OUT/'tests.txt').read_text();assert 'Ran 349 tests' in test and test.rstrip().endswith('OK')
    gate=read('numerical-acceptance.json');assert gate['python']['passed'] and not gate['native']['passed'];assert read('direct-pair-summary.json')['failures']==0
    rows=[];work=[]
    for mode in ('python','native'):
        rows.extend({'mode':mode,**r} for r in read(mode+'/strict-error-table.json'))
        for group in ('development','held_out'):
            for r in read(mode+'/predictions-'+group+'.json'):
                for name,c in r['method']['candidates'].items():
                    if 'compact_evaluator' not in c:continue
                    a=c['compact_evaluator'];n=a.get('native_geometry') or {}
                    work.append({'mode':mode,'evaluation_stage':'final_forecast','implementation':a['mode'],'actor':r['actor'],'family':r['family'],'context':r['context'],'candidate':name,'logical_nodes':a.get('logical_node_requests',0),'full_event_constructions':a['full_event_constructions'],'numeric_plan_builds':a['numeric_plan_builds'],'numeric_contest_builds':a['numeric_contest_builds'],'native_geometry_nodes':n.get('native_geometry_nodes',0),'python_geometry_repairs':n.get('python_geometry_repairs',0),'native_choice_tie_fallback':r['method'].get('native_choice_tie_python_fallback',False)})
                for name,a in r['method'].get('native_attempt_before_choice_fallback',{}).items():
                    n=a.get('native_geometry') or {}
                    work.append({'mode':mode,'evaluation_stage':'discarded_native_attempt_before_python_tie_fallback','implementation':a['mode'],'actor':r['actor'],'family':r['family'],'context':r['context'],'candidate':name,'logical_nodes':a.get('logical_node_requests',0),'full_event_constructions':a['full_event_constructions'],'numeric_plan_builds':a['numeric_plan_builds'],'numeric_contest_builds':a['numeric_contest_builds'],'native_geometry_nodes':n.get('native_geometry_nodes',0),'python_geometry_repairs':n.get('python_geometry_repairs',0),'native_choice_tie_fallback':True})
    for name,data in [('strict-error-table.csv',rows),('construction-work-table.csv',work)]:
        with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    costs=read('final-costs.json');goals={}
    for mode in ('compact_python','compact_native_rejected'):
        results=[]
        for row in costs[:2]:
            v=row['versions'];speed=v['exact']['median_ms']/v[mode]['median_ms'];ratio=v[mode]['median_ms']/v['hard_window']['median_ms'];results.append({'fixture':row['fixture'],'speedup_vs_exact':speed,'ratio_vs_hard_window':ratio,'passed':speed>=2.5 and ratio<=4})
        goals[mode]={'benchmarks':results,'practical_gate_passed':all(r['passed'] for r in results)}
    write('performance-gates.json',goals)
    write('numerical-field-mapping.json',{'kind_outcome_category':'authoritative prepare_delivery/delivery_from_geometry; native packed geometry status decoded only in hypothetical path','elapsed':'same ordered elapsed+wait+flight+catch_delay+preparation or reset_cost; clock decision stays existing integrator','receipt':'quality*(.5+.5*S14),existing receiving_preparation once; actual complete_receipt remains detailed','shot_geometry':'NumericGeometry attributes correspond exactly to ShotGeometry fields read with diagnostics=False; actual detailed ShotGeometry unchanged','offense':'shared shooting_response/finishing_response/free_throw_response/receiving_preparation; no generic completion scaling','contest':'shared geometry_response and vertical_access; one strongest eligible contest, same angular quadrature','primary_plan_reduction':'F03/F04 ground/lob/finish execution and release height/preparation independent of primary arrival; first primary plan used only for shared vertical_access reach, final primary contest reuses execution packet','moments_branches':'same action_choice._shot and interior_game.shot_probabilities including foul,FT,block,FG,miss/rebound moments','reset':'same paid time,control probability,current-event zero credit; actual selected continuation payload and creator transfer detailed','diagnostics':'logical node/plan requests retained; compact_evaluator reports actual packet/contest/event construction, native attempt+Python repair/tie fallback work'})
    write('native-source-arithmetic-audit.json',{'python_motion':'ramp=speed*speed/(2*acceleration); sqrt(2*d/a) if d<=ramp else speed/acceleration+(d-ramp)/speed','native_motion':'ramp_time=v/a; edge=.5*a*ramp_time*ramp_time; sqrt(2*d/a) if d<=edge else ramp_time+(d-edge)/v','finding':'Algebraically equivalent movement law but source-level FP grouping differs; no claim of bitwise native replacement. Compiler flags disable unsafe reassociation, not this source regrouping. Retained/rejected without post-holdout correction.','distance':'Python receiver math.dist versus native hypot can differ in rounding; direct nonbitwise comparisons recorded.','observed_amplifier':'Tiny receiver-foot changes create a near-coincident helper/shot residual; existing atan2 changes0 to-pi/2 and affects contest/FG probabilities. Native remains rejected, no smoothing or tolerance change.'})
    budget=read('mixed-budget-final.json');assert budget['n']<=1536 and budget['events']<=6144 and budget['active_s']<=60 and not budget['native_included'];assert len(read('full-result-rng-parity.json'))==48
    assert read('memory-release.json')['roots']==read('memory-release.json')['released_roots']==52
    write('summary.json',{'milestone':15,'recommendation':'Retain exact compact Python as opt-in prototype for review; reject native qualification; practical performance goals unmet','default_activation':False,'tests_passed':349,'baseline_tests':331,'new_tests':18,'exact_untouched_result_rng_comparisons':48,'numerical_acceptance':gate,'direct_pairs':read('direct-pair-summary.json'),'performance_gates':goals,'mixed_budget':budget,'memory_release':read('memory-release.json'),'shared_runtime_changes':'Two authoritative scalar helper extractions only; detailed results/RNG exact','supported_input_changes':0,'all94_dimensions_preserved':True,'native':{'build':build,'ubsan':read('native-ubsan.json'),'ASan_passed':False,'ASan_status':'not attempted/retried; earlier toolchain initialization stall retained as limitation','portable_release':False},'stop':'Coordinator review; no automatic rollout/new algorithm/season/research task'})
    runtime=[ROOT/f for f in changed];owned=runtime+[p for p in (ROOT/'experiments/compact_recovery_evaluator').rglob('*') if p.suffix in ('.py','.c')]+[ROOT/'scripts/run_compact_recovery_evaluator.py',ROOT/'tests/test_compact_recovery_evaluator.py',ROOT/'docs/COMPACT_RECOVERY_EVALUATOR_ACTIVE_TASK.md',ROOT/'docs/COMPACT_RECOVERY_EVALUATOR_REVIEW_2026_11_16.md'];delta=[]
    for p in owned:
        if p.suffix not in ('.py','.c'):continue
        old=REFERENCE/(p.stem+'.py.reference') if p in runtime else None
        delta.extend(difflib.unified_diff(old.read_text().splitlines(True) if old and old.exists() else [],p.read_text().splitlines(True),fromfile=str(old.relative_to(ROOT)) if old and old.exists() else '/dev/null',tofile=str(p.relative_to(ROOT))))
    (OUT/'owned-code.diff').write_text(''.join(delta));write('integrity-audit.json',{'preedit_files':len(initial),'changed_preedit_files':sorted(changed),'unchanged_preedit_files':len(initial)-len(changed),'accepted_pins':len(pins),'pins_unchanged':True,'sealed_algorithm_and_runtime_helpers_unchanged_after_heldout':True,'source_grades_registry_map_unchanged':True,'git_unavailable':'existing host Xcode license; independent SHA256 used'})
    def files(folder):return {str(p.relative_to(ROOT)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p!=OUT/'handoff-manifest.json'}
    write('handoff-manifest.json',{'milestone':15,'status':'COMPLETE_FOR_REVIEW','recommendation':'Python opt-in partial exact gain; native rejected; no practical-gate/production claim','owned_files':{str(p.relative_to(ROOT)):sha(p) for p in owned},'references':files(REFERENCE),'verified_outputs':files(OUT),'native_build_artifacts':files(BASE/'native-build'),'root_run_records':{str(p.relative_to(ROOT)):sha(p) for p in sorted(BASE.glob('*')) if p.is_file()},'stop':'No activation,C37,host changes,new research or next algorithm'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('baseline','development','native_development','compact_costs','native_costs','build_native','direct_pairs','sanitize','seal','held_out','native_failure_trace','acceptance','parity','high_order','mixed','costs','memory_release','tests','adapter_costs','preparation','finalize'));args=parser.parse_args();OUT.mkdir(exist_ok=True)
    globals()[args.stage]()
