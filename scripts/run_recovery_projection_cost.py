"""Sequential milestone13 exact-cost experiment. Stages baseline/costs/parity/mixed/release/tests/finalize.
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_recovery_projection_cost.py STAGE
"""
from contextlib import nullcontext
from dataclasses import replace
import argparse
import difflib
import gc
import hashlib
import json
import statistics
import subprocess
import sys
import time
import tracemalloc
import weakref
from unittest.mock import patch
from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.creation_passing import prepare_drive_decision
from nba_gm_data.action_choice import project_choices
from experiments.pass_recovery.fixtures import pool,fixture,IDS
from experiments.pass_recovery import sampling
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.expanded_cohort_performance.checks import benchmarks,traced,digest
from experiments.recovery_projection_cost.verification import BASE,REFERENCE,OUT,ROOT,reference_modules,reference_config,use_reference,prepare
import scripts.run_pass_recovery as prior

ACTORS=('turner','towns','holmgren','jokic')

def write(name,data):(OUT/name).write_text(json.dumps(to_plain(data),indent=2,allow_nan=False)+'\n')
def read(name):return json.loads((OUT/name).read_text())
def plain(value):return json.loads(json.dumps(to_plain(value)))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(state,context,config,modules):
    with use_reference(modules):
        old=reference_config(config,modules);st=prepare(context,old,modules)
    st['audit_context']=state['audit_context'];return st,old


def hooks(modules):
    from contextlib import ExitStack
    scope=ExitStack();scope.enter_context(use_reference(modules))
    for name,module in [('resolve_drive','creation_passing'),('apply_continuation','pass_recovery'),('advance_after_reset','pass_recovery')]:scope.enter_context(patch.object(sampling,name,getattr(modules['nba_gm_data.'+module],name)))
    return scope


def costs(baseline=False):
    modules=reference_modules();p=pool();rows=[]
    with patch.object(prior,'OUT',OUT):
        for name,c,x in benchmarks():
            versions={}
            for version in (('reference',) if baseline else ('reference','current')):
                with use_reference(modules):old=reference_config(x,modules)
                scope=use_reference(modules) if version=='reference' else nullcontext();simulator=modules['nba_gm_data.sim'] if version=='reference' else sim;cfg=old if version=='reference' else x
                with scope:versions[version]=prior.measure(lambda:simulator.sim_game_with_context(c,c['schedule'][0]['externalGameId'],seed=17,interior_experiment=cfg),name+'-'+('baseline' if baseline else version))
            rows.append({'fixture':name,'versions':versions,'boundary':'same accepted16-per-side kernel; preparation outside; complete diagnostics and serialization'})
            write('baseline-costs.json' if baseline else 'costs.json',rows);print('cost',name,flush=True)
        for name,actor,enabled,kw in [('turner_hard','turner',False,{}),('jokic_hard','jokic',False,{}),('turner_recovery','turner',True,{}),('jokic_recovery','jokic',True,{}),('clock3_recovery','turner',True,{'clock':3})]:
            s,c,x=fixture(p,actor,enabled=enabled,**kw);old,oldx=frozen(s,c,x,modules);versions={}
            for version in (('reference',) if baseline else ('reference','current')):
                state=old if version=='reference' else s;scope=hooks(modules) if version=='reference' else nullcontext()
                with scope:versions[version]=prior.measure(lambda:sampling.run(state,per_seed=16,seeds=(17,)),name+'-'+('baseline' if baseline else version))
            if not baseline:assert versions['reference']['result_sha256']==versions['current']['result_sha256'],name
            rows.append({'fixture':name,'versions':versions,'boundary':'same seed17 fixed16 supplied possessions with actual resets/rebounds/diagnostics; preparation outside'})
            write('baseline-costs.json' if baseline else 'costs.json',rows);print('cost',name,flush=True)


def parity():
    modules=reference_modules();p=pool();items=benchmarks();rows=read('full-result-rng-parity.json') if (OUT/'full-result-rng-parity.json').exists() else []
    for actor in ACTORS:
        for enabled in (False,True):
            s,c,x=fixture(p,actor,enabled=enabled,possessions=8);items.append((actor+('_recovery' if enabled else '_hard'),c,x))
    _,c,x=items[0];items.append(('ordinary',c,None))
    for name,c,x in items:
        with use_reference(modules):old=reference_config(x,modules)
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                if any(r['fixture']==name and r['seed']==seed and r['mode']==mode for r in rows):continue
                a,ta=traced(c,x,seed,mode)
                with use_reference(modules):b,tb=traced(c,old,seed,mode,modules['nba_gm_data.sim'])
                assert to_plain(a)==to_plain(b) and ta==tb,(name,seed,mode)
                if x is not None:validate_accounting(a)
                rows.append({'fixture':name,'seed':seed,'mode':mode,'complete_result_and_rng_equal':True,'result_sha256':digest(a),'rng_domains':ta,'possessions_per_side':a.possessions})
        write('full-result-rng-parity.json',rows);print('parity',name,flush=True)


def mixed():
    if (OUT/'mixed-budget-started.json').exists():raise RuntimeError('Mixed budget already consumed')
    write('mixed-budget-started.json',read('prespecified-budget.json'));p=pool();modules=reference_modules();rows=[];n=events=0;active=0
    for actor in ACTORS:
        for context,kw in [('show',{}),('stay',{'coverage':'stay'}),('clock3',{'clock':3})]:
            s,c,x=fixture(p,actor,**kw);old,oldx=frozen(s,c,x,modules);variants={}
            for version,st in [('reference',old),('current',s)]:
                assert n+64<=2048 and events<8192 and active<60
                scope=hooks(modules) if version=='reference' else nullcontext()
                with scope:
                    start=time.perf_counter();r=sampling.run(st,per_seed=32,seeds=(17,29),max_events=8192-events,deadline=start+60-active);active+=time.perf_counter()-start
                n+=r['n'];events+=r['event_attempts'];variants[version]=r
            assert plain(variants['reference'])==plain(variants['current']),(actor,context)
            rows.append({'actor':actor,'context':context,'results_equal':True,'result':variants['current']});write('mixed-parity.json',rows)
    write('mixed-budget-final.json',{'n':n,'events':events,'active_s':active,'all_results_equal':True,'boundary_followup_not_used':True,'caps':{'n':2048,'events':8192,'active_s':60}})


def release():
    refs=[];live=[];gc.collect();tracemalloc.start()
    for _ in range(4):
        p=pool();s,c,x=fixture(p);r=sampling.run(s,per_seed=2,seeds=(17,));refs.extend(weakref.ref(v) for v in (x,x.offense.creation,*p['views'].values()));del p,s,c,x,r;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
    final,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert all(r() is None for r in refs);write('release.json',{'cycles':4,'tracked_roots':len(refs),'released_roots':sum(r() is None for r in refs),'live_bytes_after_cycles':live,'final_bytes':final,'peak_bytes':peak})


def tests():
    names='test_action_choice_consistency test_pilot_response_calibration test_experimental_input_pilot test_screen_navigation test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research test_expanded_cohort_performance test_pick_and_pop test_mixed_pop_validation test_pass_recovery test_recovery_projection_cost'.split()
    with (OUT/'tests.txt').open('w') as f:r=subprocess.run([sys.executable,'-m','unittest',*names,'-q'],stdout=f,stderr=subprocess.STDOUT)
    assert r.returncode==0

def approximation():
    from experiments.recovery_projection_cost import stage_b
    stage_b.predictions(write,read)
    with patch.object(prior,'OUT',OUT):stage_b.costs(write,prior.measure)
    stage_b.mixed(write,read)

def detail_costs():
    """Same-state prediction versus full selected resolution, separately timed."""
    from experiments.recovery_projection_cost.stage_b import states
    from nba_gm_data.creation_passing import resolve_candidate
    modules=reference_modules();items=list(states());boundary=[(meta,f,o) for meta,f,o in items if meta['family']=='pop' and meta['context']!='reference']
    actual=[(meta,f,o) for meta,f,o in items if meta['context']=='reference'];rows=[]
    def selected(resolver):
        result=[]
        for meta,frame,options in actual:
            for error in (.1,.9):
                draws=observed_draws();draws[44]=.25;result.append(resolver(frame,meta['family'],options,draws,{},delivery_error_override=error))
        return result
    with patch.object(prior,'OUT',OUT):
        for name in ('boundary12_predictions','selected24_full_resolution'):
            versions={}
            for version in ('reference','current'):
                scope=use_reference(modules) if version=='reference' else nullcontext()
                predictor=modules['nba_gm_data.action_choice'].project_choices if version=='reference' else project_choices
                resolver=modules['nba_gm_data.creation_passing'].resolve_candidate if version=='reference' else resolve_candidate
                fn=(lambda:[predictor(f,o) for meta,f,o in boundary]) if name=='boundary12_predictions' else (lambda:selected(resolver))
                with scope:versions[version]=prior.measure(fn,name+'-'+version)
            assert versions['reference']['result_sha256']==versions['current']['result_sha256']
            rows.append({'fixture':name,'versions':versions,'boundary':'prepared48 design states reused;12 boundary predictions or24 full actual candidate resolutions,5 samples; complete returned diagnostics serialized'})
            write('detail-costs.json',rows)

def local_memory():
    p=pool();s,c,x=fixture(p,action='pop');d=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',observed_draws(),24);modules=reference_modules();rows=[]
    for version in ('reference','current'):
        scope=use_reference(modules) if version=='reference' else nullcontext();predictor=modules['nba_gm_data.action_choice'].project_choices if version=='reference' else project_choices
        with scope:
            predictor(d['frame'],d['options'])  # symmetric warm boundary, excludes lazy imports
            gc.collect();tracemalloc.start();live=[]
            for _ in range(4):
                result=predictor(d['frame'],d['options']);del result;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
            retained,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        rows.append({'version':version,'post_projection_live_bytes':live,'retained_bytes':retained,'peak_bytes':peak,'boundary':'one symmetric warm call then four same prepared Turner/pop choice projections; prepared source/frame intentionally retained outside tracing, returned projections deleted; no runtime GC changes'})
    write('local-projection-memory.json',rows)

def finalize():
    initial=json.loads((REFERENCE/'hashes.json').read_text());changed={f for f,h in initial.items() if sha(ROOT/f)!=h}
    expected={'src/nba_gm_data/pass_recovery.py','src/nba_gm_data/creation_passing.py'};assert changed==expected,changed
    pins=json.loads((REFERENCE/'input-pins.json').read_text());assert all(sha(ROOT/f)==h for f,h in pins.items())
    test=(OUT/'tests.txt').read_text();assert 'Ran 320 tests' in test and test.rstrip().endswith('OK')
    assert len(read('full-result-rng-parity.json'))==48 and read('mixed-budget-final.json')['all_results_equal']
    stageb=read('stage-B-prediction-summary.json');assert not stageb['all_passed']
    budget=read('total-mixed-budget.json');assert budget['n']<=2048 and budget['events']<=8192 and budget['active_s']<=60
    write('summary.json',{'milestone':13,'stage_A':'exact optimization proposed for review','stage_B':'REJECTED; experiment-only predictor, not promoted','tests_passed':320,'baseline_tests':303,'new_tests':17,'complete_result_rng_comparisons':48,'exact_mixed':read('mixed-budget-final.json'),'all_sampling':budget,'stage_B_errors':stageb,'release':read('release.json'),'local_memory':read('local-projection-memory.json'),'ratings_changes':0,'outcome_coefficient_changes':0,'default_activation':False,'remaining_performance_gate':'unmet; exact recovery about10.5-10.7x same hard-window batch despite17-20% gains','stop':'coordinator review; no automatic next work'})
    owned=[ROOT/f for f in sorted(expected)]+[ROOT/'tests/test_recovery_projection_cost.py',ROOT/'scripts/run_recovery_projection_cost.py',ROOT/'docs/RECOVERY_PROJECTION_COST_ACTIVE_TASK.md',ROOT/'docs/RECOVERY_PROJECTION_COST_REVIEW_2026_11_16.md']+list((ROOT/'experiments/recovery_projection_cost').glob('*.py'))
    delta=[]
    for p in owned:
        if p.suffix!='.py':continue
        old=REFERENCE/(p.stem+'.py.reference') if p.parent==ROOT/'src/nba_gm_data' else None
        delta.extend(difflib.unified_diff(old.read_text().splitlines(True) if old and old.exists() else [],p.read_text().splitlines(True),fromfile=str(old.relative_to(ROOT)) if old and old.exists() else '/dev/null',tofile=str(p.relative_to(ROOT))))
    (OUT/'owned-code.diff').write_text(''.join(delta))
    write('integrity-audit.json',{'initial_files':len(initial),'changed_files':sorted(changed),'unchanged_files':len(initial)-len(changed),'accepted_input_result_pins':len(pins),'pins_unchanged':True,'player_schema_registry_map_and_milestone12_evidence_unchanged':True,'git_unavailable':'existing host Xcode-license condition; independent hashes used'})
    def files(folder):return {str(p.relative_to(ROOT)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p!=OUT/'handoff-manifest.json'}
    write('handoff-manifest.json',{'milestone':13,'status':'COMPLETE_FOR_REVIEW','owned_files':{str(p.relative_to(ROOT)):sha(p) for p in owned},'references':files(REFERENCE),'verified_outputs':files(OUT),'root_run_records':{str(p.relative_to(ROOT)):sha(p) for p in sorted(BASE.glob('*')) if p.is_file()},'stop':'No approximation promotion, production activation, C37 or next-system work'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('baseline','costs','parity','mixed','approximation','detail_costs','local_memory','release','tests','finalize'));stage=parser.parse_args().stage;OUT.mkdir(exist_ok=True)
    costs(True) if stage=='baseline' else globals()[stage]()
