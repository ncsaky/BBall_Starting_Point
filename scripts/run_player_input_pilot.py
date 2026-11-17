"""Bounded common-input/named-action evidence; no app, save, season or ratings work.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_player_input_pilot.py --output output/player-input-pilot-2026-11-14/verified
"""
import argparse
from collections import Counter
from contextlib import nullcontext
import cProfile
from dataclasses import fields,replace
import gc
import hashlib
import json
import os
from pathlib import Path
import pstats
import statistics
import subprocess
import time
import weakref
import tracemalloc
from unittest.mock import patch

from nba_gm_data import sim
from nba_gm_data.interior_defense import fingerprint
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.offense_response import compile_offense
from nba_gm_data.creation_passing import compile_interaction
from nba_gm_data.interior_defense import compile_profile
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.schema import to_plain
from experiments.player_input_pilot.pilot import build_pilot,export_layer,review_alternative,named_config,IDS,packet,READINESS
from experiments.player_input_pilot.probes import scenarios,run_scenario
from experiments.player_input_pilot.verification import (reference_modules,reference_config,use_reference,pre_optimization_module,pre_optimization_config,traced_game,REFERENCE)
from experiments.screen_navigation.fixtures import screen_fixture
from scripts.run_interior_defense_experiment import make_context

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/player-input-pilot-2026-11-14'


def write(out,name,data):(out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def run(context,config,seed=17,mode='replay-real-minutes'):
    return sim.sim_game_with_context(context,context['schedule'][0]['externalGameId'],mode,seed,interior_experiment=config)


def core(result):return to_plain({f.name:getattr(result,f.name) for f in fields(result) if f.name!='team_lines'}|{'team_lines':[{k:v for k,v in t.items() if k!='interior_experiment'} for t in result.team_lines]})


def legacy_comparison(modules):
    ready,_=packet(READINESS);rows=[]
    old_o=modules['nba_gm_data.offense_response'];old_c=modules['nba_gm_data.creation_passing'];old_i=modules['nba_gm_data.interior_defense']
    for pid,doc in ready['operational_input_section']['players'].items():
        p=PlayerInputs(doc)
        pairs=[('offense',compile_offense(p,research_scenario=True,two_point_rim_fraction=.7),old_o.compile_offense(p,research_scenario=True,two_point_rim_fraction=.7)),
               ('interaction',compile_interaction(p,research_scenario=True),old_c.compile_interaction(p,research_scenario=True))]
        if pid in (IDS['zubac'],IDS['gobert']):pairs.append(('interior',compile_profile(p,research_scenario=True),old_i.compile_profile(p,research_scenario=True)))
        for consumer,a,b in pairs:
            assert to_plain(a)==to_plain(b),(pid,consumer)
            rows.append({'player_id':pid,'consumer':consumer,'full_profile_equal':True,'revision':a.revision})
    return rows


def complete_parity(out,pilot):
    modules,old_kernel,old_sim=reference_modules();prior=[];ordinary=[]
    canonical=json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text());canonical['_allow_internal_caches']=True
    for home,away in (('SAS','MIN'),('GSW','BOS')):
        name=f'input_pilot_off_{home}_{away}';c=make_context(canonical,home,away,name)
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                a=sim.sim_game_with_context(c,name,mode,seed)
                with use_reference(modules):b=old_sim.sim_game_with_context(c,name,mode,seed)
                assert to_plain(a)==to_plain(b)
                ordinary.append({'teams':[home,away],'seed':seed,'mode':mode,'full_result_equal':True,'digest':fingerprint(to_plain(a))})
    c,x=screen_fixture(possessions=16)
    creation=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=None)))
    for label,config in [('interior',replace(x,offense=None)),('coupled',replace(x,offense=replace(x.offense,creation=None))),('creation',creation),('screen',x)]:
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                now=run(c,config,seed,mode);a,b=c['canonical']['teams'];g=c['schedule'][0]
                pools=[sim.game_player_pool(c,'interior_fixture',t,mode,game_date=g['gameDate']) for t in (a,b)]
                with use_reference(modules):old=old_kernel.simulate_interior_game(c['canonical'],g,a,b,*pools,mode,seed,reference_config(config,modules))
                assert to_plain(now)==to_plain(old)
                prior.append({'path':label,'seed':seed,'mode':mode,'full_result_equal':True,'digest':fingerprint(to_plain(now))})
    legacy=legacy_comparison(modules)
    write(out,'historical-parity.json',{'ordinary_real_rosters':ordinary,'prior_experimental_modes':prior,'legacy_research_profile_calls':legacy,'all_changed_consumers_use_frozen_reference_compilers':True})
    return len(ordinary),len(prior),len(legacy)


def optimization_parity(out,pilot):
    before=pre_optimization_module();rows=[]
    for label in ('native','interpreted'):
        c,x=screen_fixture(possessions=16) if label=='native' else named_config(pilot,possessions=16)
        old_config=pre_optimization_config(x,before)
        for mode in sorted(sim.SIM_MODES):
            for seed in (17,29):
                a,ta=traced_game(c,x,seed,mode);b,tb=traced_game(c,old_config,seed,mode,pre_optimization=before)
                assert to_plain(a)==to_plain(b) and ta==tb
                rows.append({'fixture':label,'seed':seed,'mode':mode,'full_result_equal':True,'full_rng_stream_equal':True,'result_digest':fingerprint(to_plain(a)),
                    'rng_domains':len(ta),'draws':sum(e['draws'] for e in ta),'rng_trace_digest':fingerprint(ta)})
    write(out,'exact-optimization-parity.json',rows);return len(rows)


def profile_partition(context,config,*,before=None):
    hook=patch('nba_gm_data.screen_navigation.prepare_screens',before.prepare_screens) if before else nullcontext()
    profiler=cProfile.Profile()
    with hook:
        profiler.enable();result=run(context,config);profiler.disable()
    stats=pstats.Stats(profiler).stats
    def keys(name,filename):return [k for k in stats if k[2]==name and filename in k[0]]
    def total(name,filename):return sum(stats[k][3] for k in keys(name,filename))
    spatial=total('offensive_spatial_profile','offense_response');essential=0
    for key in keys('credibility','offense_response'):
        for caller,data in stats[key][4].items():
            if caller[2]=='offensive_spatial_profile':essential+=data[3]
    preparation=total('prepare_coupled','offense_response')+total('prepare_creation','creation_passing')
    diagnostic=spatial-essential+total('reference_report','interior_defense')
    prep_net=preparation-spatial+essential;event=total('segment','interior_game');account=total('validate_accounting','interior_game');boundary=total('simulate_interior_game','interior_game')
    action_keys=keys('resolve_drive','creation_passing');count=sum(stats[k][1] for k in action_keys);action=sum(stats[k][3] for k in action_keys)
    return profiler,{'instrumented_interior_boundary_s':boundary,'realized_possessions_per_side':result.possessions,'preparation_validation_required_spatial_s':prep_net,
        'known_diagnostic_construction_s':diagnostic,'event_kernel_with_mandatory_ledger_s':event,'final_accounting_s':account,
        'other_boundary_and_final_report_mixed_s':boundary-prep_net-diagnostic-event-account,
        'screen_preparation_nested_s':total('prepare_screens','screen_navigation'),'resolve_drive_inclusive_s':action,'action_calls':count,'mean_action_s':action/count,
        'compile_screen_calls':sum(stats[k][1] for k in keys('compile_screen','screen_navigation')),
        'scope':'instrumented cumulative groups form a partition; nested screen/action values are readouts, not additive. Diagnostic group isolates spatial report work excluding its required credibility calculation plus reference_report. Other boundary/report residual and mandatory event ledger remain mixed; no pure uninstrumented kernel claim.'}


def cost(out,pilot):
    before=pre_optimization_module();c,x=screen_fixture(possessions=16);old=pre_optimization_config(x,before)
    run(c,x)
    with patch('nba_gm_data.screen_navigation.prepare_screens',before.prepare_screens):run(c,old)
    times={};partitions={}
    for label,config,module in [('before',old,before),('after',x,None)]:
        samples=[];serial=[];small=[];sizes=[]
        for _ in range(5):
            hook=patch('nba_gm_data.screen_navigation.prepare_screens',module.prepare_screens) if module else nullcontext()
            with hook:t=time.perf_counter();r=run(c,config);samples.append(time.perf_counter()-t)
            t=time.perf_counter();payload=json.dumps(to_plain(r),separators=(',',':'));serial.append(time.perf_counter()-t)
            t=time.perf_counter();compact=json.dumps(core(r),separators=(',',':'));small.append(time.perf_counter()-t);sizes.append([len(payload.encode()),len(compact.encode())]);del r,payload,compact
        times[label]={'samples_s':samples,'median_s':statistics.median(samples),'range_s':[min(samples),max(samples)],'full_json_median_s':statistics.median(serial),'core_json_median_s':statistics.median(small),'bytes':sizes[-1]}
        profile,partitions[label]=profile_partition(c,config,before=module);profile.dump_stats(str(out/f'cost-{label}.pstats'))
        with (out/f'cost-{label}.txt').open('w') as f:pstats.Stats(profile,stream=f).sort_stats('cumulative').print_stats(40)
    assert times['before']['bytes']==times['after']['bytes']
    assert partitions['before']['compile_screen_calls']==30 and partitions['after']['compile_screen_calls']==10
    # The new interpreted path did not exist before this milestone. Measure
    # its own before/after-reuse pair at the same possession budget; do not
    # call the native-vs-named difference pure interpretation overhead.
    named_context,named_after=named_config(pilot,possessions=16);named_before=pre_optimization_config(named_after,before)
    interpreted={}
    for label,config,module in [('before',named_before,before),('after',named_after,None)]:
        hook=lambda:patch('nba_gm_data.screen_navigation.prepare_screens',module.prepare_screens) if module else nullcontext()
        with hook():run(named_context,config)
        samples=[]
        for _ in range(5):
            with hook():t=time.perf_counter();r=run(named_context,config);samples.append(time.perf_counter()-t)
            del r
        profiler,partition=profile_partition(named_context,config,before=module)
        profiler.dump_stats(str(out/f'interpreted-cost-{label}.pstats'))
        interpreted[label]={'samples_s':samples,'median_s':statistics.median(samples),'range_s':[min(samples),max(samples)],'instrumented_partition':partition}
    assert interpreted['before']['instrumented_partition']['compile_screen_calls']==6
    assert interpreted['after']['instrumented_partition']['compile_screen_calls']==4
    write(out,'cost-attribution.json',{'fixture':'identical native 10-player, 16 regulation possessions/side, seed17, same full diagnostics and outputs','warm_wall_and_serialization':times,'instrumented_partitions':partitions,
        'interpreted_same_budget_fixture':{'scope':'six-actor counterfactual interpreted pod, 16 regulation possessions/side, same source/controls before and after local reuse; not comparable native-vs-named interpretation-only overhead','measurements':interpreted},
        'optimization':'reuse only immutable participant validation within one preparation; all per-call role/ownership/availability checks retained','global_cache_or_gc_added':False,
        'next_opportunity':'measure duplicate spatial-profile construction and raw diagnostic payload conversion before any future change; neither is removed here'})
    return times,partitions


def memory(out):
    gc.collect();tracemalloc.start();refs=[];rows=[]
    for iteration in range(4):
        p=build_pilot();c,x=named_config(p);v=p['views'][IDS['zubac']]
        for obj in (p['contract'],v,v.source,x,x.offense,x.offense.creation,x.offense.creation.screens):refs.append(weakref.ref(obj))
        del obj
        r=run(c,x,17+iteration);refs.append(weakref.ref(r));del r,p,c,x,v
        current,peak=tracemalloc.get_traced_memory();rows.append({'iteration':iteration+1,'current_bytes':current,'peak_bytes':peak,'live_roots':sum(w() is not None for w in refs),'rss_kib':int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())],text=True).strip())})
    before=tracemalloc.get_traced_memory()[0];gc.collect();after=tracemalloc.get_traced_memory()[0];tracemalloc.stop();assert not any(w() is not None for w in refs)
    write(out,'memory-release.json',{'samples':rows,'probed_roots':len(refs),'all_released':True,'before_diagnostic_gc':before,'after_diagnostic_gc':after,'production_gc_added':False,'scope':'four fresh pilot-layer + small kernel calls; not whole-app or long-career stability'})
    return len(refs)


def comparisons(rows):
    table=[]
    for r in rows:
        values={}
        if 'containment' in r:values['castle_containment_advantage']=r['containment']['castle_advantage_probability_points']
        if 'help' in r:values['white_timely_help_advantage']=r['help']['white_advantage_probability_points']
        if 'security' in r:values['harper_lower_handling_loss_difference']=r['security']['harper_lower_loss_difference']
        if 'passing' in r:
            for family,p in r['passing']['families'].items():
                values[f'luka_{family}_notice_advantage']=p['luka_notice_advantage'];values[f'luka_{family}_delivery_advantage']=p['luka_delivery_advantage']
        if 'screen_zubac_caruso' in r:values['zubac_caruso_extra_delay_s']=r['screen_zubac_caruso']['first_minus_second_delay_s']
        if 'screen_zubac_gobert_prior_sensitive' in r:values['zubac_gobert_extra_delay_s']=r['screen_zubac_gobert_prior_sensitive']['first_minus_second_delay_s']
        if 'navigation' in r:values['davion_minus_ajay_delay_s']=r['navigation']['first_minus_second_delay_s']
        table.append({'scenario':r['name'],'metrics':values})
    summary={}
    for key in {k for row in table for k in row['metrics']}:
        values=[r['metrics'][key] for r in table if key in r['metrics']]
        summary[key]={'minimum':min(values),'maximum':max(values),'scenario_count':len(values),'signs_observed':sorted(set('positive' if x>1e-12 else 'negative' if x<-1e-12 else 'zero' for x in values)),
            'interpretation':'conditional sensitivity across declared alternatives, not a named player rank or statistical parameter interval'}
    return {'rows':table,'ranges':summary}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=BASE/'verified');out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    t=time.perf_counter();pilot=build_pilot();build_s=time.perf_counter()-t
    t=time.perf_counter();base_layer=export_layer(pilot);export_s=time.perf_counter()-t
    t=time.perf_counter();setup_context,setup_config=named_config(pilot);compile_config_s=time.perf_counter()-t;del setup_context,setup_config
    write(out,'initial-setup-cost.json',{'first_observed_completion_and_audit_s':build_s,'effective_ledger_export_s':export_s,'compile_six_actor_config_s':compile_config_s,
        'scope':'separate one-off setup observations including local packet reads/validation; not a cold-start guarantee or per-action cost'})
    validate_input_section(base_layer['source_section']);validate_input_section(base_layer['pilot_section']);write(out,'initial-readiness-completion-layer.json',base_layer)
    proposed=review_alternative(pilot);write(out,'separate-proposed-evidence-layer.json',export_layer(proposed))
    results=[]
    for row in scenarios(pilot):results.append(run_scenario(row))
    write(out,'action-probes.json',results);write(out,'sensitivity-summary.json',comparisons(results))
    # Small counterfactual kernel accounting only: do not publish a winner model.
    kernel=[]
    for seed in (17,29):
        c,x=named_config(pilot);r=run(c,x,seed);validate_accounting(r)
        kernel.append({'seed':seed,'regulation_possessions_per_side':8,'accounting_passed':True,'purpose':'counterfactual three-versus-three contract/accounting check; no forecast','events':dict(Counter(e['outcome'] for t in r.team_lines for e in t['interior_experiment']['offense_attack_ledger']))})
        write(out,f'counterfactual-accounting-{seed}.json',to_plain(r))
    write(out,'counterfactual-accounting-checks.json',kernel)
    ordinary,prior,legacy=complete_parity(out,pilot);optimized=optimization_parity(out,pilot)
    times,partitions=cost(out,pilot);roots=memory(out)
    for filename,digest in pilot['evidence_hashes'].items():assert hashlib.sha256((ROOT/'docs/ratings-evidence-2026-10-29'/filename).read_bytes()).hexdigest()==digest
    review_path=ROOT/'docs/ratings-evidence-2026-10-29/PILOT_ASSUMPTION_REVIEW_2026_11_14.json';assert hashlib.sha256(review_path.read_bytes()).hexdigest()==proposed['supplementary_review_hash']
    initial=json.loads((REFERENCE/'hashes.json').read_text());changed=[];external=[]
    for name,digest in initial.items():
        p=Path(name)
        if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
            (external if name.startswith('docs/ratings-evidence-2026-10-29/') else changed).append(name)
    allowed={'src/nba_gm_data/offense_response.py','src/nba_gm_data/interior_defense.py','src/nba_gm_data/creation_passing.py','src/nba_gm_data/screen_navigation.py','docs/PLAYER_INPUT_PILOT_ACTIVE_TASK.md','docs/PLAYER_INPUT_PILOT_REVIEW_2026_11_14.md'}
    assert not set(changed)-allowed,changed
    files=sorted(allowed|{'src/nba_gm_data/experimental_inputs.py','experiments/player_input_pilot/pilot.py','experiments/player_input_pilot/probes.py','experiments/player_input_pilot/verification.py','tests/test_experimental_input_pilot.py','scripts/run_player_input_pilot.py'})
    write(out,'source-manifest.json',{'changed_owned_existing':changed,'independent_research_changes':external,'unexpected_changes':[],'hashes':{name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in files if Path(name).exists()}})
    summary={'default_off':True,'actors':len(pilot['views']),'full_base_actors':6,'role_only_screen_navigation_actors':3,'required_cells':len(pilot['ledger']),'source_unknown_completions':sum(r['source_status']=='unknown' for r in pilot['ledger']),
        'scenario_count':len(results),'pass_help_trials_per_actor_scenario':4096,'screen_phase_samples_per_actor_scenario':512,'coupled_first_actions_per_creator_scenario':64,
        'toy_accounting_checks':len(kernel),'ordinary_full_result_comparisons':ordinary,'prior_experiment_full_result_comparisons':prior,'legacy_research_profile_comparisons':legacy,'exact_optimization_full_result_rng_cases':optimized,
        'released_roots':roots,'evidence_hashes':pilot['evidence_hashes'],'supplementary_review_hash':proposed['supplementary_review_hash'],
        'optimization_median_wall_s':{k:v['median_s'] for k,v in times.items()},'unwired':'no app/calendar/daily-bulk/reload/economic activation or parity claim','no_nba_rankings_forecasts_or_calibration':True}
    write(out,'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
