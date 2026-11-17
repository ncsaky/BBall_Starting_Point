"""Bounded deterministic-choice verification; no NBA calibration/live activation.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_action_choice_consistency.py
"""
import argparse
from collections import Counter
from contextlib import nullcontext
from dataclasses import replace
import gc
import hashlib
import json
from pathlib import Path
import pstats
import random
import statistics
import time
import tracemalloc
import weakref

from nba_gm_data import sim
from nba_gm_data.creation_passing import CHOICE_POLICY,HELP_RESPONSE_POLICY,resolve_drive
from nba_gm_data.action_choice import project_choices
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.schema import to_plain
from nba_gm_data.interior_defense import fingerprint
from experiments.action_choice_consistency.fixtures import pinned_pilot,make_case,decision,prepare,observed_draws,PIN,REFERENCE
from experiments.action_choice_consistency.scenarios import scenarios,coupled
from experiments.action_choice_consistency.empirical import validate_candidate
from experiments.action_choice_consistency.verification import reference_modules,reference_config,use_reference
from experiments.player_input_pilot.verification import pre_optimization_module,pre_optimization_config,traced_game
from experiments.screen_navigation.fixtures import screen_fixture
from scripts.run_pilot_response_calibration import parity as prior_parity
from scripts.run_player_input_pilot import profile_partition,core

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/action-choice-consistency-2026-11-14'


def write(out,name,data):(out/name).write_text(json.dumps(to_plain(data),indent=2,allow_nan=False)+'\n')


def run(context,config,seed=17,mode='replay-real-minutes'):
    return sim.sim_game_with_context(context,context['schedule'][0]['externalGameId'],mode,seed,interior_experiment=config)


def baseline_audit(out,pilot,modules):
    rows=[]
    cases=[('dunk_weak',{'families':(),'available':0,'finish_mix':(0,0,0,1,0),'changes':{'creator':{'S12':10}}},'finish'),
        ('dunk_strong',{'families':(),'available':0,'finish_mix':(0,0,0,1,0),'changes':{'creator':{'S12':95}}},'finish'),
        ('closeout_low',{'families':('F06',),'start':(3,6.8),'commitment':0,'changes':{'helper':{'S40':10}}},'F06'),
        ('closeout_high',{'families':('F06',),'start':(3,6.8),'commitment':0,'changes':{'helper':{'S40':95}}},'F06')]
    for name,controls,candidate in cases:
        draws=observed_draws()
        if candidate!='finish':draws[28]=1
        current,_,_=make_case(pilot,**controls);d=decision(current,draws=draws);projected=project_choices(d['frame'],d['options'])
        with use_reference(modules):
            old,_,_=make_case(pilot,consistent=False,**controls)
            result=modules['nba_gm_data.creation_passing'].resolve_drive(old,old['audit_context']['ids'][0],'response_a','response_b',draws,24)
        assert set(result['record']['choice_scores'])==set(projected['scores'])
        rows.append({'case':name,'controls':controls,'old_choice_scores':result['record']['choice_scores'],
            'new_candidate_projection':projected['candidates'][candidate],'new_choice_scores':projected['scores']})
    for clock in (24,.7):
        with use_reference(modules):
            old,_,_=make_case(pilot,consistent=False,families=());draws=observed_draws();draws[33]=1-1e-15
            result=modules['nba_gm_data.creation_passing'].resolve_drive(old,old['audit_context']['ids'][0],'response_a','response_b',draws,clock)
        assert result['kind']=='reset'
        new,_,_=make_case(pilot,families=());d=decision(new,clock,draws)
        rows.append({'case':'reset_clock_'+str(clock),'old_choice_scores':result['record']['choice_scores'],
            'old_reset_expired_clock':result['elapsed_s']>=clock,'new_reset':project_choices(d['frame'],d['options'])['candidates']['reset']})
    write(out,'authenticated-mismatch-audit.json',rows)


def compatibility(out,pilot,modules):
    rows=prior_parity(out,modules)
    for label in ('native_m7','helper_m7'):
        if label=='native_m7':
            context,config=screen_fixture(possessions=16)
            config=replace(config,offense=replace(config.offense,creation=replace(config.offense.creation,help_response_policy=HELP_RESPONSE_POLICY)))
        else:_,context,config=make_case(pilot,consistent=False,start=None,coverage='show_then_recover')
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                now=run(context,config,seed,mode)
                with use_reference(modules):old=run(context,reference_config(config,modules),seed,mode)
                assert to_plain(now)==to_plain(old)
                rows.append({'path':label,'seed':seed,'mode':mode,'full_result_equal':True,'digest':fingerprint(to_plain(now))})
    write(out,'authenticated-parity.json',rows);return rows


def held_candidates(out,pilot,modules):
    rows=[]
    for label,controls,names in [('finish_mixture',{'families':()},('finish',)),
        ('pass_and_help',{'families':('F03','F04','F06')},('F03','F04','F06')),
        ('screen_show',{'coverage':'show_then_recover','families':('F03','F04','F06')},('F03','F04','F06'))]:
        current,_,_=make_case(pilot,**controls)
        with use_reference(modules):old,_,_=make_case(pilot,consistent=False,**controls)
        for candidate in names:
            rng=random.Random(1803);equal=0
            for _ in range(64):
                d=[rng.random() for _ in range(48)]
                for key in (24,32,42):d[key]=.999
                for key in (25,26,27,33,40):d[key]=0
                d[39]=.5;d[41]=.5
                for key in (28,29,30,31):d[key]=1
                d[{'finish':28,'F03':29,'F04':30,'F06':31}[candidate]]=0
                a=resolve_drive(current,current['audit_context']['ids'][0],'response_a','response_b',d,24)
                with use_reference(modules):b=modules['nba_gm_data.creation_passing'].resolve_drive(old,old['audit_context']['ids'][0],'response_a','response_b',d,24)
                for key in ('kind','outcome','elapsed_s','plan','passer_id','steal_by'):
                    assert to_plain(a.get(key))==to_plain(b.get(key)),(label,candidate,key)
                assert a['record'].get('choice')==b['record'].get('choice')
                equal+=1
            rows.append({'context':label,'candidate':candidate,'same_conditional_trials':equal,'selected_outcomes_full_plans_equal':True})
    write(out,'held-candidate-outcome-parity.json',rows);return rows


def validation_reuse(out,pilot):
    before=pre_optimization_module();rows=[]
    for label in ('native','helper'):
        if label=='native':
            context,config=screen_fixture(possessions=16)
            config=replace(config,offense=replace(config.offense,creation=replace(config.offense.creation,help_response_policy=HELP_RESPONSE_POLICY,choice_policy=CHOICE_POLICY)))
        else:_,context,config=make_case(pilot,coverage='show_then_recover',start=None)
        previous=pre_optimization_config(config,before)
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                a,ta=traced_game(context,config,seed,mode);b,tb=traced_game(context,previous,seed,mode,pre_optimization=before)
                assert to_plain(a)==to_plain(b) and ta==tb
                rows.append({'fixture':label,'seed':seed,'mode':mode,'full_result_equal':True,'rng_stream_equal':True,
                    'domains':len(ta),'draws':sum(v['draws'] for v in ta),'trace_digest':fingerprint(ta)})
    write(out,'retained-validation-reuse-parity.json',rows);return rows


def accounting(out,pilot):
    rows=[]
    for consistent in (False,True):
        for coverage in ('stay','show_then_recover'):
            _,context,config=make_case(pilot,consistent=consistent,coverage=coverage,start=None)
            for seed in (17,29):
                result=run(context,config,seed);validate_accounting(result)
                write(out,f'kernel-{consistent}-{coverage}-{seed}.json',result)
                rows.append({'new_choice':consistent,'coverage':coverage,'seed':seed,'regulation_budget':16,
                    'realized_possessions':result.possessions,'accounting_passed':True,'digest':fingerprint(to_plain(result))})
    write(out,'accounting-checks.json',rows);return rows


def projection_counts(result):
    rows=[e['creation_chain']['choice_projection'] for t in result.team_lines for e in t['interior_experiment']['offense_attack_ledger'] if 'choice_projection' in e.get('creation_chain',{})]
    return {'projected_decisions':len(rows),'candidate_total':sum(r['candidate_count'] for r in rows),
        'candidate_max':max((r['candidate_count'] for r in rows),default=0),
        'resolution_total':sum(r['candidate_resolution_calls'] for r in rows),
        'resolution_max':max((r['candidate_resolution_calls'] for r in rows),default=0),
        'shot_plan_total':sum(r['shot_plan_evaluations'] for r in rows),'shot_plan_max':max((r['shot_plan_evaluations'] for r in rows),default=0)}


def cost(out,pilot,modules):
    fixtures={}
    for label in ('native10','helper6'):
        if label=='native10':
            context,old_spec=screen_fixture(possessions=16)
            old_spec=replace(old_spec,offense=replace(old_spec.offense,creation=replace(old_spec.offense.creation,help_response_policy=HELP_RESPONSE_POLICY)))
        else:_,context,old_spec=make_case(pilot,consistent=False,coverage='show_then_recover',start=None)
        new_spec=replace(old_spec,offense=replace(old_spec.offense,creation=replace(old_spec.offense.creation,choice_policy=CHOICE_POLICY)))
        with use_reference(modules):old_spec=reference_config(old_spec,modules)
        measurements={}
        for label_engine,config in [('accepted_m7',old_spec),('consistent_choice',new_spec)]:
            hook=lambda:use_reference(modules) if label_engine=='accepted_m7' else nullcontext()
            with hook():run(context,config)
            wall=[];serialization=[];compact=[]
            for _ in range(5):
                with hook():t=time.perf_counter();result=run(context,config);wall.append(time.perf_counter()-t)
                t=time.perf_counter();full=json.dumps(to_plain(result),separators=(',',':'));serialization.append(time.perf_counter()-t)
                t=time.perf_counter();small=json.dumps(core(result),separators=(',',':'));compact.append(time.perf_counter()-t)
            with hook():profiler,partition=profile_partition(context,config)
            profiler.dump_stats(str(out/f'cost-{label}-{label_engine}.pstats'))
            with (out/f'cost-{label}-{label_engine}.txt').open('w') as f:pstats.Stats(profiler,stream=f).sort_stats('cumulative').print_stats(35)
            measurements[label_engine]={'warm_wall_samples_s':wall,'median_s':statistics.median(wall),'range_s':[min(wall),max(wall)],
                'regulation_budget':16,'realized_possessions':result.possessions,'json_median_s':statistics.median(serialization),
                'core_json_median_s':statistics.median(compact),'json_bytes_full_core':[len(full.encode()),len(small.encode())],
                'projection_counts':projection_counts(result),'instrumented_partition':partition}
        fixtures[label]={'scope':'same frozen inputs, seed17, 16 regulation possessions/side; action choices/outcomes may intentionally differ',
            'measurements':measurements}
    write(out,'bounded-costs.json',fixtures);return fixtures


def release(out,pilot):
    refs=[];samples=[];gc.collect();tracemalloc.start()
    for iteration in range(4):
        state,context,config=make_case(pilot,coverage='show_then_recover',start=None)
        result=run(context,config,17+iteration)
        for item in (config,config.offense,config.offense.creation,config.offense.creation.screens,state['profiles'][state['audit_context']['ids'][0]].inputs,result):refs.append(weakref.ref(item))
        del item,state,context,config,result
        current,peak=tracemalloc.get_traced_memory();samples.append({'iteration':iteration+1,'current_bytes':current,'peak_bytes':peak,'live_roots':sum(r() is not None for r in refs)})
    before=tracemalloc.get_traced_memory()[0];gc.collect();after=tracemalloc.get_traced_memory()[0];tracemalloc.stop()
    assert not any(r() is not None for r in refs)
    data={'probed_roots':len(refs),'all_released':True,'samples':samples,'current_before_diagnostic_gc':before,'current_after_diagnostic_gc':after,
        'new_production_gc_or_global_cache':False,'scope':'four fresh fixture/config/kernel calls with prebuilt pinned pilot; not whole-app stability'}
    write(out,'bounded-release.json',data);return data


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=BASE/'verified')
    parser.add_argument('--trials',type=int,default=8192);args=parser.parse_args()
    if not 1024<=args.trials<=16384:parser.error('Bounded 1024–16384 conditional trials required')
    out=args.output;out.mkdir(parents=True,exist_ok=True);pilot=pinned_pilot();modules=reference_modules();matrix=scenarios(pilot)
    baseline_audit(out,pilot,modules);empirical=[];before=[];after=[];absent=[]
    for row in matrix:
        state,_,_=make_case(pilot,**row['controls']);d=decision(state,row['controls'].get('remaining',24))
        for candidate in row['conditional_candidates']:
            if candidate not in d['options']:
                absent.append({'context':row['name'],'candidate':candidate,'reason':'not physically available/eligible in this supplied context'});continue
            check=validate_candidate(d,candidate,n=args.trials);check['context']=row['name'];empirical.append(check)
            assert check['all_passed'],(row['name'],candidate,check['absolute_mean_error'],check['branch_checks'])
        with use_reference(modules):before.append(coupled(pilot,row,modules['nba_gm_data.creation_passing'].resolve_drive,consistent=False))
        after.append(coupled(pilot,row))
        print(row['name'],'verified',flush=True)
    write(out,'conditional-projection-vs-events.json',empirical);write(out,'unavailable-candidates.json',absent)
    write(out,'coupled-before.json',before);write(out,'coupled-after.json',after)
    paired=[{'context':a['name'],'n':a['n'],'seed':a['seed'],'old_choices':a['choices'],'new_choices':b['choices'],
        'old_first_event_mean':a['mean_first_event_points'],'new_first_event_mean':b['mean_first_event_points'],
        'scope':'paired seeded opportunities; not a causal NBA player ranking; reset continuation not included in first-event points'} for a,b in zip(before,after,strict=True)]
    write(out,'paired-choice-comparison.json',paired)
    parity=compatibility(out,pilot,modules);held=held_candidates(out,pilot,modules);reuse=validation_reuse(out,pilot)
    accounts=accounting(out,pilot);costs=cost(out,pilot,modules);memory=release(out,pilot)
    initial=json.loads((REFERENCE/'hashes.json').read_text());changed=[];external=[]
    for name,digest in initial.items():
        assert (ROOT/name).exists(),name
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            (external if name=='docs/PLAYER_MODEL_IMPLEMENTATION_STATUS_2026_11_12.md' else changed).append(name)
    allowed={'src/nba_gm_data/creation_passing.py','src/nba_gm_data/offense_response.py','src/nba_gm_data/interior_defense.py',
        'src/nba_gm_data/shot_geometry.py','docs/ACTION_CHOICE_CONSISTENCY_ACTIVE_TASK.md'}
    assert not set(changed)-allowed,changed
    files=[ROOT/n for n in allowed|{'src/nba_gm_data/action_choice.py','tests/test_action_choice_consistency.py'}]+list((ROOT/'experiments/action_choice_consistency').glob('*.py'))+[Path(__file__)]
    write(out,'source-manifest.json',{'initial_files_checked':len(initial),'changed_owned_existing':changed,'independent_coordinator_changes':external,'unexpected_changes':[],
        'hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
    assert hashlib.sha256((REFERENCE/'targeted-input-overlay.json').read_bytes()).hexdigest()==PIN
    summary={'default_off':True,'choice_policy':CHOICE_POLICY,'pinned_input_sha256':PIN,'new_cohort_consumed':False,
        'contexts':len(matrix),'conditional_candidates_checked':len(empirical),'conditional_trials_per_candidate':args.trials,
        'all_empirical_checks_passed':all(r['all_passed'] for r in empirical),'maximum_mean_error':max(r['absolute_mean_error'] for r in empirical),
        'maximum_quadrature_difference':max(r['quadrature_EP_difference'] for r in empirical),
        'ordinary_full_result_parity':sum(r['path']=='ordinary_default_off' for r in parity),
        'previous_experimental_full_result_parity':sum(r['path']!='ordinary_default_off' for r in parity),
        'held_candidate_trials_equal':sum(r['same_conditional_trials'] for r in held),'reuse_full_result_rng_cases':len(reuse),
        'accounting_checks':len(accounts),'released_roots':memory['probed_roots'],
        'continuation_limits':'zero rebound continuation credit; reset is a discounted one-attempt proxy, not calibrated possession value',
        'no_nba_forecasts_rankings_or_activation':True}
    write(out,'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
