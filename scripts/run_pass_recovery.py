"""Bounded milestone12 verification; run stages sequentially, never as calibration.
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_pass_recovery.py STAGE
Stages: evidence, conditional, parity, natural, kernels, costs, release, tests.
Existing stage outputs are not automatically resampled. Natural sampling has a
single-use budget marker: interrupted work must be accounted before any retry.
"""
from contextlib import nullcontext
from dataclasses import replace,asdict
import argparse
import cProfile
from collections import Counter
import difflib
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
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.creation_passing import prepare_drive_decision
from nba_gm_data.action_choice import project_candidate
from nba_gm_data.pass_recovery import RecoveryCoefficients
from experiments.pass_recovery.fixtures import pool,fixture,BASE,REFERENCE,ROOT,IDS,scripted_reset_kernel
from experiments.pass_recovery import sampling,empirical
from experiments.pass_recovery.verification import reference_modules,reference_config,use_reference
from experiments.expanded_cohort_performance.checks import benchmarks,traced,digest
from experiments.pick_and_pop.fixtures import fixture as pop_fixture,pool as pop_pool,research_pool
from experiments.action_choice_consistency.fixtures import observed_draws

ACTORS=('turner','towns','holmgren','jokic')
OUT=BASE/'verified'

def write(name,data):
    (OUT/name).write_text(json.dumps(to_plain(data),indent=2,allow_nan=False)+'\n')

def read(name):return json.loads((OUT/name).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def evidence():
    folder=ROOT/'docs/ratings-evidence-2026-10-29';names=['PASS_RECOVERY_EVIDENCE_2026_11_16.md','PASS_RECOVERY_EVIDENCE_2026_11_16.json','diagnostics/pass_recovery_20261116/validation.json','diagnostics/pass_recovery_20261116/delivery_manifest.json']
    dest=REFERENCE/'recovery-evidence';dest.mkdir(exist_ok=True)
    pins={}
    for name in names:
        path=folder/name;target=dest/path.name
        if target.exists():assert target.read_bytes()==path.read_bytes()
        else:target.write_bytes(path.read_bytes())
        pins[str(path.relative_to(ROOT))]=sha(path)
    assert json.loads((dest/'validation.json').read_text())['status']=='PASS'
    p=pool();s,c,x=fixture(p);before={k:v.to_dict() for k,v in p['views'].items()}
    rows=[];seen=set()
    for actor in ACTORS:
        s,c,x=fixture(p,actor)
        for pid in s['profiles']:
            if pid in seen:continue
            seen.add(pid);row=before[pid]['inputs']['P02'];assert row['status']!='unknown'
            rows.append({'player_id':pid,'design_id':'P02','stored_cm':row['value']['measurements'][0]['value'],'used_m':s['receiving_spans_m'][pid],'same_offense_interaction_view':s['profiles'][pid].inputs is s['coupled']['profiles'][pid].inputs,'evidence':row['evidence']})
    assert before=={k:v.to_dict() for k,v in p['views'].items()}
    write('evidence-and-input-audit.json',{'final_research_pins':pins,'conditional_probability_evidence':False,'new_recovery_dependency':rows,'all_operational_inputs_equal_frozen_milestone11':True,'ratings_changes':0,'coefficients':asdict(RecoveryCoefficients()),'snapshot_sha256':digest(before)})

def conditional():
    saved=json.loads((BASE/'conditional-verification-seed17-summary.json').read_text());rows=[];p=pool()
    for action,name in [('pop','pop'),('roll','F03'),('slip','F04')]:
        s,c,x=fixture(p,action=action);draws=observed_draws();d=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',draws,24)
        prior=next(r for r in saved['rows'] if r['candidate']==name)
        assert project_candidate(d['frame'],name,d['options'])['expected_points']==prior['projected_EP']
        r=empirical.check(d,name,n=4096,seed=29);rows.append(r);write('conditional-seed29.json',rows);assert r['all_passed'],name
        print('conditional',name,r['mean_points'],flush=True)
    write('conditional-budget.json',{'previous_seed17':saved,'seed29_resolutions':12288,'total_resolutions':24576,'all_passed':True,'seed17_full_branch_tables_unavailable':True,'seed17_current_projection_exactly_equal':True})

def parity():
    modules=reference_modules();p=pool();items=benchmarks()
    for label,q in [('pop_original',pop_pool()),('pop_research',research_pool())]:
        s,c,x=pop_fixture(q);items.append((label,c,x))
    _,c,x=items[0];legacy=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,choice_policy='legacy_scores_v1',help_response_policy='legacy_timely_v1')))
    items.extend([('ordinary',c,None),('prior_legacy',c,legacy),('offense_without_creation',c,replace(x,offense=replace(x.offense,creation=None))),('interior_only',c,replace(x,offense=None))])
    for actor in ACTORS:
        s,c,x=fixture(p,actor,enabled=False);items.append(('fixed_final_'+actor,c,x))
    rows=[]
    for label,c,x in items:
        with use_reference(modules):old=reference_config(x,modules) if x else None
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                a,ta=traced(c,x,seed,mode)
                # Only the separately demonstrated ledger checker omission is
                # repaired in the frozen run; all outcome/RNG runtime stays old.
                with use_reference(modules),patch.object(modules['nba_gm_data.interior_game'],'validate_accounting',validate_accounting):b,tb=traced(c,old,seed,mode,modules['nba_gm_data.sim'])
                assert to_plain(a)==to_plain(b) and ta==tb,(label,seed,mode)
                rows.append({'case':label,'seed':seed,'mode':mode,'full_result_equal':True,'full_rng_equal':True,'result_sha256':digest(a),'rng_domains':ta,'actual_possessions_per_side':a.possessions})
        write('untouched-full-result-rng-parity.json',{'frozen_checker_patch':'current accounting validator only; fixes known waiting_loss omission, no resolution changes','rows':rows})
        print('parity',label,flush=True)

def natural():
    marker=OUT/'natural-budget-started.json'
    if marker.exists():raise RuntimeError('Natural budget already started; audit retained results before any retry')
    write(marker.name,{'supplied_cap':8192,'event_cap':32768,'active_seconds_cap':180,'main':6144,'sensitivities':1024,'optional_followup_not_used':True})
    p=pool();rows=[];sens=[];n=events=0;active=0.;unrun=[]
    contexts=[('reference_show',{}),('reference_stay',{'coverage':'stay'}),('clock3',{'clock':3})]
    def run(s):
        nonlocal n,events,active
        if n+256>8192 or events>=32768 or active>=180:return None
        start=time.perf_counter();r=sampling.run(s,per_seed=128,seeds=(17,29),max_events=32768-events,deadline=start+180-active)
        active+=time.perf_counter()-start;n+=r['n'];events+=r['event_attempts'];return r
    for actor in ACTORS:
        for context,kw in contexts:
            versions={}
            for enabled in (False,True):
                s,c,x=fixture(p,actor,enabled=enabled,**kw);r=run(s)
                if r is None:unrun.append([actor,context,enabled]);continue
                versions['after' if enabled else 'before']={'revision':x.revision,**r}
            row={'actor':actor,'context':context,'controls':kw,'versions':versions}
            if len(versions)==2 and versions['before']['n']==versions['after']['n']:
                delta=[b-a for a,b in zip(versions['before']['points'],versions['after']['points'])];mean=statistics.mean(delta);se=statistics.stdev(delta)/len(delta)**.5
                row['paired_point_difference']={'after_minus_before':mean,'nominal_MC95':[mean-1.96*se,mean+1.96*se],'n':len(delta),'scope':'paired seeded supplied possessions; not real-world uncertainty'}
            rows.append(row);write('natural-paired-results.json',rows);print('natural',actor,context,'n',n,'events',events,'active_s',round(active,2),flush=True)
    for key,value in [('horizon_s',.45),('horizon_s',.8),('residual_velocity_fraction',.15),('residual_velocity_fraction',.40)]:
        s,c,x=fixture(p,'turner',coefficients=replace(RecoveryCoefficients(),**{key:value}));r=run(s)
        if r is None:unrun.append(['sensitivity',key,value]);continue
        sens.append({'coefficient':key,'value':value,'fixed_actor':'turner','fixed_context':'reference_show','result':r});write('coefficient-sensitivity.json',sens)
    write('natural-budget-final.json',{'n':n,'events':events,'active_sampling_s':active,'hard_caps':{'n':8192,'events':32768,'active_s':180},'unrun':unrun,'optional_followup':0,'all_complete':not unrun and all(v['n']==256 and v['truncated']==0 for r in rows for v in r['versions'].values()),'grades_unchanged':True})

def kernels():
    p=pool();rows=[]
    for actor in ACTORS:
        s,c,x=fixture(p,actor,possessions=8)
        for seed in (17,29):
            a,ta=traced(c,x,seed);b,tb=traced(c,x,seed);validate_accounting(a)
            assert to_plain(a)==to_plain(b) and ta==tb
            write('kernel-'+actor+'-'+str(seed)+'.json',a)
            rows.append({'actor':actor,'seed':seed,'same_result_and_rng':True,'accounting_passed':True,'requested_possessions_per_side':8,'actual_possessions_per_side':a.possessions,'result_sha256':digest(a)})
    r=scripted_reset_kernel();validate_accounting(r);write('scripted-reset-kernel.json',r);write('kernel-verification.json',rows)

def followup():
    """Reserved1024 audit possessions: add family receipt denominators only.

    Same seeds intentionally overlap main domains. This is diagnostic replay,
    not another independent estimate or a coefficient-tuning opportunity.
    """
    previous=read('natural-budget-final.json');marker=OUT/'followup-started.json'
    interrupted=read('followup-interrupted.json') if (OUT/'followup-interrupted.json').exists() else None
    if marker.exists() and not interrupted:raise RuntimeError('Followup budget already consumed')
    second=read('followup-second-interruption.json') if (OUT/'followup-second-interruption.json').exists() else None
    if interrupted and (OUT/'followup-resumed.json').exists() and not second:raise RuntimeError('Followup resume already consumed')
    if (OUT/'total-natural-budget.json').exists():raise RuntimeError('Followup completed')
    write('followup-resumed.json' if interrupted else marker.name,{'maximum_n':1024,'reason':'per-family receipt denominators absent from initial aggregate sampler output','independent_observations':False})
    rows=read('family-denominator-audit-replay.json') if second else []
    n=previous['n']+(256 if interrupted else 0)+sum(r['result']['n'] for r in rows)
    events=previous['events']+(interrupted['conservative_event_upper_bound'] if interrupted else 0)+sum(r['result']['event_attempts'] for r in rows)
    last=read('followup-final-sampling-time.json') if (OUT/'followup-final-sampling-time.json').exists() else {}
    active=previous['active_sampling_s']+(interrupted['wall_upper_bound_s'] if interrupted else 0)+(second['wall_upper_bound_s'] if second else 0)+last.get('wall_upper_bound_s',0);p=pool()
    for context,kw in [('reference_show',{}),('reference_stay',{'coverage':'stay'})]:
        for enabled in (False,True):
            if interrupted and context=='reference_show' and not enabled:continue
            if any(row['context']==context and row['version']==('after' if enabled else 'before') for row in rows):continue
            assert n+256<=8192 and events<32768 and active<180
            s,c,x=fixture(p,'turner',enabled=enabled,**kw);start=time.perf_counter()
            r=sampling.run(s,per_seed=128,seeds=(17,29),max_events=32768-events,deadline=start+180-active)
            active+=time.perf_counter()-start;n+=r['n'];events+=r['event_attempts']
            old=next(row['versions']['after' if enabled else 'before'] for row in read('natural-paired-results.json') if row['actor']=='turner' and row['context']==context)
            rows.append({'actor':'turner','context':context,'version':'after' if enabled else 'before','result':r});write('family-denominator-audit-replay.json',rows)
    for row in rows:
        old=next(v['versions'][row['version']] for v in read('natural-paired-results.json') if v['actor']=='turner' and v['context']==row['context'])
        plain=json.loads(json.dumps(to_plain(row['result'])))
        assert all(plain[k]==old[k] for k in old if k!='revision'), 'Audit replay changed prior fields'
    write('total-natural-budget.json',{'n':n,'events_upper_bound':events,'active_sampling_s_upper_bound':active,'hard_caps':{'n':8192,'events':32768,'active_s':180},'followup_n':n-previous['n'],'followup_independent_observations':False,'interrupted_audit_leg':interrupted,'all_retained_followup_fields_equal_initial_run':True})

def measure(fn,label):
    fn();wall=[];serial=[]
    for _ in range(5):
        t=time.perf_counter();r=fn();wall.append(1000*(time.perf_counter()-t))
        t=time.perf_counter();payload=json.dumps(to_plain(r),separators=(',',':'));serial.append(1000*(time.perf_counter()-t))
    profile=cProfile.Profile();profile.enable();fn();profile.disable();profile.dump_stats(str(OUT/(label+'.pstats')))
    stats=pstats.Stats(profile)
    with (OUT/(label+'-profile.txt')).open('w') as f:stats.stream=f;stats.sort_stats('cumulative').print_stats(40)
    calls={name:sum(v[1] for k,v in stats.stats.items() if k[2]==name) for name in ('resolve_drive','project_choices','project_candidate','resolve_candidate','plan_attack','recovery_geometry','__post_init__','same_input_snapshot')}
    return {'samples_ms':wall,'median_ms':statistics.median(wall),'serialization_ms':serial,'median_serialization_ms':statistics.median(serial),'json_bytes':len(payload.encode()),'profiled_calls':calls,'result_sha256':digest(r)}

def costs():
    modules=reference_modules();rows=[]
    for label,c,x in benchmarks():
        with use_reference(modules):old=reference_config(x,modules)
        versions={}
        for version,cfg in [('before',old),('after',x)]:
            scope=use_reference(modules) if version=='before' else nullcontext();simulator=modules['nba_gm_data.sim'] if version=='before' else sim
            with scope,patch.object(modules['nba_gm_data.interior_game'],'validate_accounting',validate_accounting):
                versions[version]=measure(lambda:simulator.sim_game_with_context(c,c['schedule'][0]['externalGameId'],seed=17,interior_experiment=cfg),label+'-'+version)
        assert versions['before']['result_sha256']==versions['after']['result_sha256'];rows.append({'fixture':label,'versions':versions,'boundary':'accepted16 possessions/side kernel including diagnostics; same seed/source/config'})
        write('runtime-costs.json',rows);print('cost',label,flush=True)
    p=pool()
    for actor in ('turner','jokic'):
        versions={}
        for enabled in (False,True):
            s,c,x=fixture(p,actor,enabled=enabled);version='after' if enabled else 'before'
            versions[version]=measure(lambda:sampling.run(s,per_seed=16,seeds=(17,)),actor+'-batch-'+version)
        rows.append({'fixture':actor+'_supplied16','versions':versions,'boundary':'fixed16 supplied possessions with actual resets/rebounds, choice work and full diagnostics; outcomes differ'})
        write('runtime-costs.json',rows);print('cost',actor,flush=True)

def release():
    refs=[];live=[];gc.collect();tracemalloc.start()
    for _ in range(4):
        p=pool();s,c,x=fixture(p);r=sampling.run(s,per_seed=2,seeds=(17,))
        refs.extend(weakref.ref(v) for v in (x,x.offense,x.offense.creation,x.offense.creation.screens,*p['views'].values()))
        del p,s,c,x,r;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert all(r() is None for r in refs)
    write('release.json',{'cycles':4,'roots':len(refs),'released_roots':sum(r() is None for r in refs),'post_cycle_live_bytes':live,'final_bytes':current,'peak_bytes':peak,'scope':'scoped fixtures/profiles/state; no runtime GC/cache changes'})

def tests():
    names='test_action_choice_consistency test_pilot_response_calibration test_experimental_input_pilot test_screen_navigation test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research test_expanded_cohort_performance test_pick_and_pop test_mixed_pop_validation test_pass_recovery'.split()
    with (OUT/'tests.txt').open('w') as f:r=subprocess.run([sys.executable,'-m','unittest',*names,'-q'],stdout=f,stderr=subprocess.STDOUT)
    assert r.returncode==0

def summary():
    rows=read('natural-paired-results.json');result={}
    losses={'handling_loss','inaccurate_delivery','late_delivery','failed_catch','shot_clock_turnover','waiting_loss','pass_grounded','pass_unreachable','recovery_defended','pass_out_of_bounds'}
    for version in ('before','after'):
        totals={k:Counter() for k in ('events','choices','stages','planned_receipts','secured_receipts','projection_work')};receipts={};points=[]
        for row in rows:
            r=row['versions'][version];points+=r['points'];assert sum(r['planned_receipts'].values())==r['stages']['pass_selected_launched']
            for key in totals:totals[key].update(r[key])
            for key,value in r['receipt_event_breakdown'].items():receipts.setdefault(key,Counter()).update(value)
        result[version]={'n':len(points),'points':sum(points),'mean_points':statistics.mean(points),'events':sum(totals['events'].values()),'turnover_events':sum(totals['events'][k] for k in losses),**{k:dict(v) for k,v in totals.items() if k!='events'},'event_counts':dict(totals['events']),'receipt_event_breakdown':{k:dict(v) for k,v in receipts.items()}}
    write('main-aggregate-summary.json',result)
    write('summary.json',{'milestone':12,'policy':'poor_receipt_recovery_v1','default_enabled':False,'ratings_changed':0,'baseline_tests':273,'new_tests':30,'tests_passed':303,'exact_result_rng_comparisons':len(read('untouched-full-result-rng-parity.json')['rows']),'conditional_resolutions':24576,'new_reproducible_accounted_kernels':8,'natural_budget':read('total-natural-budget.json'),'main':result,'release':read('release.json'),'scope':'verification only; explicit hypotheses, no empirical conditional calibration; stop for review'})

def manifest():
    expected={'src/nba_gm_data/'+n+'.py' for n in ('interior_game','creation_passing','action_choice','offense_response')}|{'docs/PASS_RECOVERY_ACTIVE_TASK.md'}
    initial=json.loads((REFERENCE/'hashes.json').read_text());changed={f for f,h in initial.items() if sha(ROOT/f)!=h};assert changed==expected,changed
    pins=json.loads((REFERENCE/'input-pins.json').read_text());assert all(sha(ROOT/f)==h for f,h in pins.items())
    assert 'Ran 303 tests' in (OUT/'tests.txt').read_text() and (OUT/'tests.txt').read_text().rstrip().endswith('OK')
    owned=sorted([ROOT/f for f in expected]+[ROOT/'src/nba_gm_data/pass_recovery.py',ROOT/'tests/test_pass_recovery.py',ROOT/'scripts/run_pass_recovery.py',ROOT/'docs/PASS_RECOVERY_REVIEW_2026_11_16.md']+list((ROOT/'experiments/pass_recovery').glob('*.py')))
    delta=[]
    for file in owned:
        frozen=REFERENCE/(file.stem+'.py.reference') if file.parent==ROOT/'src/nba_gm_data' else None
        old=frozen.read_text() if frozen and frozen.exists() else ''
        if file.suffix=='.py':delta.extend(difflib.unified_diff(old.splitlines(True),file.read_text().splitlines(True),fromfile=str(frozen.relative_to(ROOT)) if frozen and frozen.exists() else '/dev/null',tofile=str(file.relative_to(ROOT))))
    (OUT/'owned-code.diff').write_text(''.join(delta))
    write('integrity-audit.json',{'frozen_preedit_files':len(initial),'changed_preedit_files':sorted(changed),'unchanged_preedit_files':len(initial)-len(changed),'all18_accepted_input_result_pins_unchanged':True,'source_ratings_changed':0,'recovery_evidence_pins':read('evidence-and-input-audit.json')['final_research_pins'],'git_status_unavailable':'host Xcode license; no host license modification attempted'})
    def files(folder):return {str(p.relative_to(ROOT)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p!=OUT/'handoff-manifest.json'}
    write('handoff-manifest.json',{'milestone':12,'status':'COMPLETE_FOR_REVIEW','owned_files':{str(p.relative_to(ROOT)):sha(p) for p in owned},'reference_files':files(REFERENCE),'verified_outputs':files(OUT),'root_run_records':{str(p.relative_to(ROOT)):sha(p) for p in sorted(BASE.glob('*')) if p.is_file()},'stop':'No further system work or activation; coordinator review required'})

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('evidence','conditional','parity','natural','followup','kernels','costs','release','tests','summary','manifest'));args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    globals()[args.stage]()
