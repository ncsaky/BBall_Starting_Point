"""One bounded sequential milestone10 verification/measurement workload.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_pick_and_pop.py
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
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

from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from nba_gm_data.player_model import validate_input_section
from nba_gm_data.experimental_inputs import InterpretedInputs
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.creation_passing import resolve_candidate
from nba_gm_data.action_choice import project_choices
from experiments.pick_and_pop.fixtures import ROOT,BASE,REFERENCE,pool,fixture,research_pool,IDS
from experiments.pick_and_pop.probes import central_cases,causal_cases,run_case,decision,legacy_turner,scripted_accounting
from experiments.pick_and_pop.verification import reference_modules,reference_config,use_reference,prepare
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.action_choice_consistency.empirical import validate_candidate
from experiments.expanded_cohort_performance.pool import load_pool
from experiments.expanded_cohort_performance.fixtures import fixture as old_fixture
from experiments.expanded_cohort_performance.checks import benchmarks,kernel_parity,candidate_parity,digest,traced
from scripts.run_expanded_cohort_performance import costs
from scripts.run_player_input_pilot import core


def write(out,name,data):(out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def run(c,x,seed=17,mode='replay-real-minutes',simulator=sim):
    return simulator.sim_game_with_context(c,c['schedule'][0]['externalGameId'],mode,seed,interior_experiment=x)


def dependency_audit(p):
    """Capture actual row access for the new screener projection."""
    from unittest.mock import patch
    from nba_gm_data.screen_navigation import compile_screen
    original=InterpretedInputs.to_dict;seen=set()
    class Rows(dict):
        def __getitem__(self,key):seen.add(key);return super().__getitem__(key)
        def get(self,key,default=None):seen.add(key);return super().get(key,default)
    def traced_doc(view):
        d=original(view);d['inputs']=Rows(d['inputs']);return d
    v=p['views'][IDS['turner']]
    with patch.object(InterpretedInputs,'to_dict',traced_doc):profile=compile_screen(v,roles=('screener',),pop_routes=True)
    expected={'S26','S27','S28','P01','P04','P05','P06','P08','P09','T11'}
    assert seen==expected,(seen,expected)
    return {'consumer':'pop-capable screener','actual_required_ids':sorted(seen),'declared_required_ids':sorted(expected),
        'new_vs_existing_screener':['S26'],'same_input_view':profile.inputs is v,'profile_revision':profile.revision,
        'readiness_scope':'actual screener projection; whole action also consumes existing offense/interaction/coverage/interior consumers',
        'controls':p['control_ledger'],'research_updates':p.get('research_updates',[])}


def early_reproduction(out,modules):
    s,c,x=old_fixture(load_pool(),creator='curry',receiver='white',partner='jokic',poa='castle',helper='barnes',other='wemb',screen='show_then_recover',families=('F03','F04','F06'))
    current=decision(s)
    with use_reference(modules):
        cfg=reference_config(x,modules);state=prepare(c,cfg,modules)
        old=modules['nba_gm_data.creation_passing'].prepare_drive_decision(state,IDS['curry'],'response_a','response_b',observed_draws(),24)
    assert current['record']==old['record'] and 'F03' not in old['options']
    # Opt in using the same source snapshots; only S26 (unused on a roll) is
    # separately completed, and T11 stays the existing Jokić trial distribution.
    from nba_gm_data.screen_navigation import PopScreenCall,PopScreenExperiment,compile_screen
    from experiments.interior_defense.fixtures import estimate
    p=load_pool();v=p['views'][IDS['jokic']];doc=v.to_dict();doc['inputs']['S26']=estimate({'grade':65,'scale':'research_technique_reference_v0_2026_11_13'},method='unused-on-roll explicit pop capability control')
    view=InterpretedInputs(__import__('nba_gm_data.player_model',fromlist=['PlayerInputs']).PlayerInputs(doc),v.contract)
    p['views'][IDS['jokic']]=view
    base,context,new=old_fixture(p,creator='curry',receiver='white',partner='jokic',poa='castle',helper='barnes',other='wemb',screen='show_then_recover',families=('F03','F04','F06'))
    spec=new.offense.creation.screens;profiles=tuple(compile_screen(v.inputs,roles=v.roles,pop_routes=v.player_id==IDS['jokic']) for v in spec.profiles)
    calls=tuple(PopScreenCall(**__import__('dataclasses').asdict(v),pop_end=(3,7.4),action_call='preference') for v in spec.calls)
    variants={}
    for timing in ('immediate_v1','bounded_wait_v1'):
        screens=PopScreenExperiment(profiles,calls,timing_policy=timing)
        config=replace(new,offense=replace(new.offense,creation=replace(new.offense.creation,screens=screens)))
        from experiments.action_choice_consistency.fixtures import prepare as prep
        st=prep(context,config,None);d=decision(st);variants[timing]={'record':d['record'],'options':d['options'],'projection':project_choices(d['frame'],d['options'])}
    assert 'F03' not in variants['immediate_v1']['options'] and 'F03' in variants['bounded_wait_v1']['options']
    write(out,'early-window-reproduction.json',{'frozen_milestone9_record':old['record'],'frozen_current_legacy_record_equal':True,
        'opt_in_variants':variants,'attribution':'same Jokić source grades; only unused-on-roll S26 completion; timing/route policy intentionally differs, no source correction'})


def feature_cost(out,modules):
    old_c,old_current=legacy_turner()
    with use_reference(modules):old=reference_config(old_current,modules)
    _,c,x=fixture(pool())
    _,rc,rx=fixture(research_pool())
    rows=[]
    for label,ctx,cfg,simulator,reference in [('milestone9_same_pod_called_roll',old_c,old,modules['nba_gm_data.sim'],True),
        ('milestone10_original_controls_called_pop',c,x,sim,False),('milestone10_final_research_called_pop',rc,rx,sim,False)]:
        from contextlib import nullcontext
        with use_reference(modules) if reference else nullcontext():
            run(ctx,cfg,simulator=simulator);wall=[];serial=[];core_ms=[]
            for _ in range(7):
                t=time.perf_counter();r=run(ctx,cfg,simulator=simulator);wall.append((time.perf_counter()-t)*1000)
                t=time.perf_counter();payload=json.dumps(to_plain(r),separators=(',',':'));serial.append((time.perf_counter()-t)*1000)
                t=time.perf_counter();minimal=json.dumps(core(r),separators=(',',':'));core_ms.append((time.perf_counter()-t)*1000)
            validate_accounting(r);assert r.possessions==16,(label,r.possessions)
            prof=cProfile.Profile();prof.enable();run(ctx,cfg,simulator=simulator);prof.disable()
        prof.dump_stats(str(out/(label+'.pstats')))
        with (out/(label+'-profile.txt')).open('w') as f:pstats.Stats(prof,stream=f).sort_stats('cumulative').print_stats(65)
        stats=pstats.Stats(prof).stats
        counts={name:sum(v[1] for k,v in stats.items() if k[2]==name) for name in ('resolve_drive','project_choices','project_candidate','resolve_candidate','plan_attack','screen_interception','prepare_screens','compile_screen')}
        rows.append({'fixture':label,'warm_ms':wall,'median_ms':statistics.median(wall),'range_ms':[min(wall),max(wall)],
            'serialization_ms':serial,'median_serialization_ms':statistics.median(serial),'median_core_serialization_ms':statistics.median(core_ms),
            'full_json_bytes':len(payload.encode()),'core_json_bytes':len(minimal.encode()),'actual_possessions_per_side':r.possessions,
            'profiled_calls':counts,'configuration_revision':cfg.revision,'result_sha256':digest(r)})
    return {'fixtures':rows,'scope':'seven sequential warm samples, seed17,16 actual possessions/side; different called route/T11 context and final independent evidence trial explicitly differ; no result parity/speedup claim for the feature contrast'}


def release():
    refs=[];tracemalloc.start();live=[]
    for _ in range(4):
        p=pool();s,c,x=fixture(p);r=run(c,x)
        refs.extend(weakref.ref(v) for v in (x,x.offense,x.offense.creation,x.offense.creation.screens,*p['views'].values()))
        del p,s,c,x,r;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert all(r() is None for r in refs)
    return {'cycles':4,'roots':len(refs),'released':sum(r() is None for r in refs),'post_cycle_live_bytes':live,'final_bytes':current,'peak_bytes':peak,
        'scope':'audit-only explicit GC; no runtime global cache or GC-policy change; metadata/allocator residue retained separately from owned graphs'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=BASE/'verified');out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    p=pool();rp=research_pool();modules=reference_modules()
    write(out,'named-inputs-and-completions.json',{'original_cohort_packet_sha256':p['packet_sha256'],
        'original_operational_documents':{k:v.to_dict() for k,v in p['views'].items()},'explicit_new_role_controls':p['control_ledger'],
        'separate_final_research_documents':{k:v.to_dict() for k,v in rp['views'].items()},'final_research_updates':rp['research_updates'],
        'remaining_role_controls':rp['control_ledger'],'source_section':p['packet']['proposed_source_input_section'],
        'new_packet_source_section':rp['research_packet']['proposed_source_input_section'],'not_a_source_correction':True})
    write(out,'compiler-dependency-audit.json',{'original_controls':dependency_audit(p),'final_research':dependency_audit(rp),
        'passing_context':'existing F06 recognition/execution only; no F03 or summed F01 surrogate; stationary/cross-court return excluded',
        'uncompiled_new_packet_actors':'Other seven require separate complete role contexts/controls; no zero talent or full-player comparison inferred'})
    early_reproduction(out,modules)
    named=[run_case(p,name,kw) for name,kw in central_cases()];write(out,'named-route-coverage-timing-probes.json',named)
    final=[run_case(rp,'final_research_'+name,kw) for name,kw in central_cases() if kw['action']=='pop'];write(out,'separate-final-research-turner-probes.json',final)
    print('named central and separately pinned research probes complete',flush=True)
    causal=[]
    for name,changes,kw in causal_cases():
        synthetic=pool(synthetic=True,changes=changes);causal.append(run_case(synthetic,name,kw,n=128))
    for remaining in (.1,2.6,2.9,3.2):causal.append(run_case(pool(synthetic=True),'short_clock_'+str(remaining),{},n=128,remaining=remaining))
    write(out,'synthetic-causal-probes.json',causal);print('causal probes complete',flush=True)
    empirical=[]
    for kw,name in [({},'pop'),({'coverage':'stay'},'pop'),({'action':'roll'},'F03'),({'action':'slip'},'F04')]:
        s,_,_=fixture(pool(synthetic=True),**kw);d=decision(s)
        for seed in (17,29):
            r=validate_candidate(d,name,n=4096,seed=seed);assert r['all_passed'];empirical.append({'configuration':kw,'seed':seed,**r})
    for remaining in (2.6,2.9):
        s,_,_=fixture(pool(synthetic=True));d=decision(s,remaining)
        r=validate_candidate(d,'pop',n=4096,seed=17);assert r['all_passed'];empirical.append({'remaining':remaining,'seed':17,**r})
    write(out,'projection-versus-actual.json',empirical)
    write(out,'legacy-exact-result-rng-parity.json',kernel_parity(benchmarks(load_pool()),modules));write(out,'legacy-exact-candidate-parity.json',candidate_parity(load_pool(),modules))
    _,c,x=benchmarks(load_pool())[0];legacy=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,choice_policy='legacy_scores_v1',help_response_policy='legacy_timely_v1')))
    write(out,'ordinary-prior-exact-parity.json',kernel_parity([('ordinary',c,None),('legacy',c,legacy),('offense_only',c,replace(x,offense=replace(x.offense,creation=None))),('interior_only',c,replace(x,offense=None))],modules))
    kernels=[]
    for label,pp in [('original_controls',p),('final_research',rp)]:
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                _,ctx,cfg=fixture(pp);a,ta=traced(ctx,cfg,seed,mode);b,tb=traced(ctx,cfg,seed,mode);assert to_plain(a)==to_plain(b) and ta==tb;validate_accounting(a)
                write(out,f'pop-accounting-{label}-{seed}-{mode}.json',to_plain(a))
                kernels.append({'trial':label,'seed':seed,'mode':mode,'accounting_passed':True,'deterministic_result_and_rng':True,'result_sha256':digest(a),'rng_domains':ta,'possessions':a.possessions})
    write(out,'pop-kernel-accounting-rng.json',kernels);print('projection, accounting, and authentic old-path comparisons complete',flush=True)
    write(out,'scripted-pop-accounting.json',{'scope':'controlled draw branch checks, not empirical performance evidence',
        'cases':{name:to_plain(scripted_accounting(name)) for name in ('made_fg','shooting_foul')}})
    # Sequential old-fixture timing, followed by intentionally different route
    # fixture timing. No tests/profile workload runs concurrently.
    write(out,'legacy-same-input-costs.json',costs(out,load_pool(),modules));write(out,'feature-costs.json',feature_cost(out,modules));write(out,'ownership-release.json',release())
    suites=['test_action_choice_consistency','test_pilot_response_calibration','test_experimental_input_pilot','test_screen_navigation','test_creation_passing','test_offense_interior_interaction','test_interior_defense_experiment','test_player_model_schema','test_defensive_alignment','test_narrative_simulation','test_historical_shooting_parser','test_guarantee_research','test_expanded_cohort_performance','test_pick_and_pop']
    r=subprocess.run([sys.executable,'-m','unittest',*suites,'-q'],cwd=ROOT,text=True,capture_output=True);(out/'tests.txt').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
    summary={'status':'Milestone10 bounded backend complete; stop for coordinator review','baseline_tests':228,'new_tests':29,
        'named_contexts':len(named),'named_trials':sum(r['sample']['n'] for r in named),'separate_research_contexts':len(final),'separate_research_trials':sum(r['sample']['n'] for r in final),
        'synthetic_contexts':len(causal),'synthetic_trials':sum(r['sample']['n'] for r in causal),'conditional_empirical_checks':len(empirical),'empirical_trials':len(empirical)*4096,
        'legacy_result_rng_comparisons':28,'legacy_conditional_candidate_tables':48,'pop_determinism_accounting_comparisons':len(kernels),
        'source_ratings_changed':False,'research_integration':'Only final-delivery Turner S26/S28 independently sourced unknown fills in separate trial; remaining seven not force-completed',
        'activation':'default OFF','timing':'bounded feasible catch; clock, continued movement, pressure, independent wait loss draw43',
        'passing_context':'F06 drive-exit same-side pop; F03/F04 remain roll/lob only','limitations':['full C37 contest','post','general off-ball/handoffs','stationary F01 return','complete role/workload','multi-step future planner']}
    write(out,'summary.json',summary);print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
