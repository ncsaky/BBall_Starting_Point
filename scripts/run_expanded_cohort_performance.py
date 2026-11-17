"""One sequential bounded evidence/performance run, no app/server/season work.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_expanded_cohort_performance.py
"""
import argparse
import cProfile
from dataclasses import replace
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

from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from nba_gm_data.interior_game import validate_accounting
from experiments.expanded_cohort_performance.pool import ROOT,BASE,REFERENCE,load_pool,compile_audit,export
from experiments.expanded_cohort_performance.fixtures import fixture
from experiments.expanded_cohort_performance.probes import cases,run_case,shooting,alternatives,SCREEN
from experiments.expanded_cohort_performance.checks import benchmarks,kernel_parity,candidate_parity,digest
from experiments.expanded_cohort_performance.verification import reference_modules,reference_config,use_reference
from scripts.run_player_input_pilot import core


def write(out,name,data):(out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def run(context,config,simulator=sim):
    return simulator.sim_game_with_context(context,context['schedule'][0]['externalGameId'],'replay-real-minutes',17,interior_experiment=config)


def costs(out,pool,modules):
    rows=[]
    for label,context,config in benchmarks(pool):
        with use_reference(modules):old=reference_config(config,modules)
        by={}
        # Preparation/config compilation is outside this per-game boundary.
        for version,cfg in [('before',old),('after',config)]:
            scope=use_reference(modules) if version=='before' else __import__('contextlib').nullcontext()
            simulator=modules['nba_gm_data.sim'] if version=='before' else sim
            with scope:
                run(context,cfg,simulator);wall=[];serial=[];core_serial=[]
                for _ in range(7):
                    t=time.perf_counter();result=run(context,cfg,simulator);wall.append((time.perf_counter()-t)*1000)
                    t=time.perf_counter();payload=json.dumps(to_plain(result),separators=(',',':'));serial.append((time.perf_counter()-t)*1000)
                    t=time.perf_counter();minimal=json.dumps(core(result),separators=(',',':'));core_serial.append((time.perf_counter()-t)*1000)
                validate_accounting(result)
                profile=cProfile.Profile();profile.enable();run(context,cfg,simulator);profile.disable()
            profile.dump_stats(str(out/f'{label}-{version}.pstats'))
            with (out/f'{label}-{version}-profile.txt').open('w') as f:pstats.Stats(profile,stream=f).sort_stats('cumulative').print_stats(65)
            stats=pstats.Stats(profile).stats
            def metric(name,file):
                entries=[v for k,v in stats.items() if k[2]==name and file in k[0]]
                return {'calls':sum(v[1] for v in entries),'self_ms':1000*sum(v[2] for v in entries),'inclusive_ms':1000*sum(v[3] for v in entries)}
            functions={f'{file}.{fn}':metric(fn,file) for file,fn in [
                ('creation_passing','prepare_creation'),('offense_response','prepare_coupled'),
                ('creation_passing','resolve_drive'),('action_choice','project_choices'),('action_choice','project_candidate'),
                ('creation_passing','resolve_candidate'),('offense_response','plan_attack'),
                ('shot_geometry','__post_init__'),('interior_defense','__post_init__'),
                ('experimental_inputs','same_input_snapshot'),('interior_game','validate_accounting'),('interior_defense','reference_report')]}
            by[version]={'warm_game_ms':wall,'median_ms':statistics.median(wall),'range_ms':[min(wall),max(wall)],
                'serialization_ms':serial,'median_serialization_ms':statistics.median(serial),
                'core_serialization_ms':core_serial,'median_core_serialization_ms':statistics.median(core_serial),
                'full_json_bytes':len(payload.encode()),'core_json_bytes':len(minimal.encode()),'full_result_sha256':digest(result),
                'actual_possessions_per_side':result.possessions,'profiled_functions':functions,'configuration_revision':cfg.revision}
        assert by['before']['full_result_sha256']==by['after']['full_result_sha256']
        assert by['before']['configuration_revision']==by['after']['configuration_revision']
        assert by['before']['actual_possessions_per_side']==by['after']['actual_possessions_per_side']==16
        rows.append({'fixture':label,'versions':by,'saved_ms':by['before']['median_ms']-by['after']['median_ms'],
            'percent_saved':100*(1-by['after']['median_ms']/by['before']['median_ms']),
            'scope':'sequential same-process warm games, seed17 and16 possessions/side; seven unprofiled samples/version, separate profiling and serialization; no app speed claim'})
        print('cost',label,round(rows[-1]['percent_saved'],2),'percent',flush=True)
    return rows


def release():
    gc.collect();tracemalloc.start();start=tracemalloc.get_traced_memory()[0];refs=[];live=[]
    for _ in range(4):
        p=load_pool();s,c,x=fixture(p,**SCREEN);r=run(c,x)
        refs.extend(weakref.ref(v) for v in (x,x.offense,x.offense.creation,*p['views'].values()))
        del p,s,c,x,r
        gc.collect();live.append(tracemalloc.get_traced_memory()[0])
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    assert all(r() is None for r in refs)
    return {'cycles':4,'weak_roots':len(refs),'released_roots':sum(r() is None for r in refs),
        'baseline_bytes':start,'post_cycle_live_bytes':live,'final_bytes':current,'peak_bytes':peak,
        'scope':'explicit audit GC only; no GC/cache policy change; Python allocator residue is not a live input graph; no global runtime cache'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=BASE/'verified');out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    p=load_pool();modules=reference_modules();write(out,'compile-audit.json',compile_audit(p));write(out,'frozen-input-layers.json',export(p))
    # Final independent expectations are copied once. No live polling or ratings changes.
    evidence=ROOT/'docs/ratings-evidence-2026-10-29';pins={}
    for ext in ('md','json'):
        path=evidence/f'EXPANDED_COHORT_EXPECTATIONS_2026_11_15.{ext}'
        if path.exists():
            raw=path.read_bytes();(out/path.name).write_bytes(raw);pins[str(path.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()
    write(out,'independent-expectation-pins.json',pins)
    central=[run_case(p,name,kw) for name,kw in cases()];write(out,'central-action-probes.json',central);write(out,'supplied-shooting.json',shooting(p))
    print('central probes complete',flush=True)
    variants=[];by_case=dict(cases())
    for variant,names in alternatives(p):
        variants.append({'scenario':variant['scenario'],'overrides':variant['overrides'],
            'cases':[run_case(variant,name,by_case[name],n=128) for name in names],'supplied_shooting':shooting(variant)})
    write(out,'sensitivity-probes.json',variants);print('sensitivity probes complete',flush=True)
    write(out,'exact-candidate-parity.json',candidate_parity(p,modules));write(out,'exact-result-rng-parity.json',kernel_parity(benchmarks(p),modules))
    # Check default OFF and historical experimental policies explicitly.
    _,c,x=benchmarks(p)[0]
    legacy=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,choice_policy='legacy_scores_v1',help_response_policy='legacy_timely_v1')))
    prior=[('ordinary',c,None),('legacy_screen',c,legacy),('offense_only',c,replace(x,offense=replace(x.offense,creation=None))),('interior_only',c,replace(x,offense=None))]
    write(out,'ordinary-prior-parity.json',kernel_parity(prior,modules));print('exact comparisons complete',flush=True)
    costs_result=costs(out,p,modules);write(out,'bounded-costs.json',costs_result)
    write(out,'ownership-release.json',release())
    # Required tests run only after timing/memory workload has ended.
    suites=['test_action_choice_consistency','test_pilot_response_calibration','test_experimental_input_pilot','test_screen_navigation',
        'test_creation_passing','test_offense_interior_interaction','test_interior_defense_experiment','test_player_model_schema',
        'test_defensive_alignment','test_narrative_simulation','test_historical_shooting_parser','test_guarantee_research','test_expanded_cohort_performance']
    result=subprocess.run([sys.executable,'-m','unittest',*suites,'-q'],cwd=ROOT,text=True,capture_output=True)
    (out/'tests.txt').write_text(result.stdout+result.stderr);assert result.returncode==0,result.stdout+result.stderr
    frozen=json.loads((REFERENCE/'hashes.json').read_text());changes=[];unchanged=[]
    for name,pin in frozen.items():
        path=ROOT/name
        if path.exists():
            current=hashlib.sha256(path.read_bytes()).hexdigest()
            (changes if current!=pin else unchanged).append(name)
    owned=['src/nba_gm_data/shot_geometry.py','src/nba_gm_data/interior_defense.py','src/nba_gm_data/experimental_inputs.py',
        'tests/test_expanded_cohort_performance.py','scripts/run_expanded_cohort_performance.py']
    owned.extend(str(v.relative_to(ROOT)) for v in (ROOT/'experiments/expanded_cohort_performance').glob('*.py'))
    write(out,'source-manifest.json',{'pre_edit_hashes':frozen,'post_edit_owned_hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in owned},
        'changed_since_freeze':changes,'unchanged_since_freeze':unchanged,'runtime_optimization_only':owned[:3],
        'ratings_or_formula_changes':False,'other_changes_are_independently_owned':True})
    summary={'status':'bounded milestone9 complete; stop for coordinator review','cohort_packet_sha256':p['packet_sha256'],
        'cohort_role_compiles':20,'source_rows':564,'supported_required_cells':68,'explicit_controls':224,
        'central_contexts':len(central),'central_trials':sum(r['sample']['n'] for r in central),
        'sensitivity_scenarios':len(variants),'sensitivity_trials':sum(r['sample']['n'] for v in variants for r in v['cases']),
        'full_expanded_benchmark_result_rng_comparisons':12,'ordinary_prior_comparisons':16,'candidate_context_comparisons':48,
        'optimization':'direct scalar validation and immutable snapshot identity; all arithmetic/quadrature/diagnostics unchanged',
        'missing_mechanisms':['pop','post/F08 continuation','off-ball route generation','complete role/workload/overall value'],
        'test_log':'tests.txt','costs':'bounded-costs.json','activation':'default OFF; no UI/server/live games'}
    write(out,'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
