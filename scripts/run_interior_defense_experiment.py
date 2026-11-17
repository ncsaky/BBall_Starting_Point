"""Bounded introductory interior experiment: no server, saves or calibration.

PYTHONPATH=src:. .venv/bin/python scripts/run_interior_defense_experiment.py
Timing and allocation tracing are separate. Writes only to --output.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import asdict, replace
import gc
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import pstats
import cProfile
import resource
import statistics
import subprocess
import sys
import time
import tracemalloc
import weakref

from nba_gm_data import sim
from nba_gm_data.interior_defense import Anchor, ArrivalContext, Coefficients, InteriorExperiment, compile_profile, fingerprint, reference_report
from nba_gm_data.interior_game import expected_environment, validate_accounting
from nba_gm_data.player_model import PlayerInputs, validate_input_section
from nba_gm_data.schema import to_plain
from experiments.interior_defense.fixtures import scenario_profile
from experiments.interior_defense.consumers import consumer_probe

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT/'docs/ratings-evidence-2026-10-29/INTERIOR_DEFENSE_EXPERIMENT_INPUTS_2026_11_13.json'


def write(output,name,value):
    (output/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def make_context(canonical,home,away,name):
    teams=[next(t for t in canonical['teams'] if t['abbrev']==abbrev) for abbrev in (home,away)]
    game={'externalGameId':name,'gameDate':'2026-11-13','homeTeamId':'1','awayTeamId':'2'}
    return {'canonical':canonical,'schedule':[game],'boxscores':[],'real_minutes':{},'manifestos':{},'odds':{},'sim_cache':{},
            'indices':{'schedule_by_game_id':{name:game},'teams_by_espn_id':{'1':teams[0],'2':teams[1]}}}


def summary(result):
    return {'scores':[result.home_score,result.away_score],'input_revisions':[t['interior_experiment']['revision'] for t in result.team_lines],
            'stats':[{key:t[key] for key in ('team_abbrev','points','possessions','fga','fgm','fg3a','fg3m','fta','ftm','rim_attempts','blocks','personal_fouls','rebounds','offensive_rebounds','defensive_rebounds','turnovers','steals','assists')} for t in result.team_lines],
            'redirected_attacks':[sum(bool(e.get('redirected')) for e in t['interior_experiment']['offense_attack_ledger']) for t in result.team_lines],
            'ledger_attacks':[len(t['interior_experiment']['offense_attack_ledger']) for t in result.team_lines]}


def rss_kib():
    return int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())],text=True).strip())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output/interior-defense-experiment-2026-11-13')
    args=parser.parse_args();output=args.output;output.mkdir(parents=True,exist_ok=True)
    source=RESEARCH.read_bytes();packet=json.loads(source);validate_input_section(packet['player_input_section'])
    scenarios={row['scenario_id']:row for row in packet['scenarios']}
    compiled={};cohort=[];reference_reports={}
    for scenario_id,scenario in scenarios.items():
        validate_input_section(scenario['input_section'])
        for player_id,doc in scenario['input_section']['players'].items():
            profile=compile_profile(PlayerInputs(doc),research_scenario=True)
            compiled[(scenario_id,player_id)]=profile
            recognition=doc['inputs']['S38']
            assert recognition['status']!='unknown'
            # Explicit provisional map to declared arrival context, not full C26.
            delay=.08+.42*(1-recognition['value']['grade']/100)
            context=ArrivalContext(distance_m=.8,window_s=.9,recognition_delay_s=delay,reference='synthetic weak-side arrival; provisional S38->delay .08+.42*(1-grade/100)')
            environment=expected_environment(profile,context)
            cohort.append({'scenario':scenario_id,'player_id':player_id,'name':packet['identities'][player_id],'input_revision':profile.revision,
                'source_unknowns_preserved':packet['player_input_section']['players'][player_id]['inputs']['P03']['status']=='unknown',
                'scope':'scenario sensitivity, NOT player forecast/ranking','reference_C36':reference_report(profile)['C36'],
                'available_environment':expected_environment(profile,ArrivalContext()),
                'near_boundary_help_environment':expected_environment(profile,replace(context,window_s=1.1)),
                'arrival_environment':environment})
            if scenario_id=='reference_assumptions_v1':reference_reports[player_id]=reference_report(profile,context)
    write(output,'cohort-sensitivity.json',{'packet_sha256':hashlib.sha256(source).hexdigest(),'scenarios':cohort})
    write(output,'reference-responses.json',reference_reports)
    profile=scenario_profile()
    matrix=[]
    for spaced,rim_attack,strong_poa,available,timely in itertools.product((False,True),repeat=5):
        context=ArrivalContext(distance_m=.8,window_s=.9,recognition_delay_s=.1 if timely else 1.6,
            spacing=1 if spaced else 0,poa_containment=1 if strong_poa else 0,anchor_available=1 if available else 0,
            reference='controlled geometry/threat/POA/assignment/timing; these families are not implemented')
        share=.6 if rim_attack else .1;three=.15 if rim_attack else .7
        baseline=expected_environment(None,context,rim_share=share,three_share=three)
        changed=expected_environment(profile,context,rim_share=share,three_share=three)
        matrix.append({'spaced':spaced,'rim_attacks':rim_attack,'strong_poa':strong_poa,'anchor_available':available,'timely_help':timely,
            'baseline':baseline,'experimental':changed,'delta_expected_points_per_100':changed['expected_points_per_100_possessions']-baseline['expected_points_per_100_possessions']})
    write(output,'interaction-matrix.json',matrix)
    sensitivity=[]
    for field in ('max_conversion_reduction','max_block_probability','max_avoidance','max_contest_foul'):
        for multiplier in (.75,1.25):
            coefficients=replace(Coefficients(),**{field:getattr(Coefficients(),field)*multiplier})
            for player_id in packet['identities']:
                doc=scenarios['reference_assumptions_v1']['input_section']['players'][player_id]
                p=compile_profile(PlayerInputs(doc),coefficients,research_scenario=True)
                response=expected_environment(p,ArrivalContext())
                sensitivity.append({'player_id':player_id,'coefficient':field,'multiplier':multiplier,'input_revision':p.revision,
                    'expected_points_per_100':response['expected_points_per_100_possessions'],'blocks_per_100':response['expected_blocks_per_100_possessions'],
                    'shooting_fouls_per_100':response['expected_shooting_fouls_per_100_possessions']})
    write(output,'coefficient-sensitivity.json',sensitivity)
    # Deliberately widen unknown geometry assumptions, rather than tune a name
    # to rank first. Original research documents remain unmodified.
    geometry=[]
    for player_id in packet['identities']:
        doc=scenarios['reference_assumptions_v1']['input_section']['players'][player_id]
        for reach_delta in (-10,10):
            d=json.loads(json.dumps(doc));measure=d['inputs']['P03']['value']['measurements'][0]
            measure['value']+=reach_delta
            if 'interval' in measure:measure['interval']=[x+reach_delta for x in measure['interval']]
            d['inputs']['P03']['uncertainty']['notes']+=' Additional explicit ±10cm mechanism sensitivity, not player evidence.'
            p=compile_profile(PlayerInputs(d),research_scenario=True)
            response=expected_environment(p,ArrivalContext())
            geometry.append({'player_id':player_id,'reach_delta_cm':reach_delta,'expected_points_per_100':response['expected_points_per_100_possessions'],'coverage':response['rim_response']['geometry_fraction']})
    write(output,'geometry-sensitivity.json',geometry)
    canonical=json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text());canonical['_allow_internal_caches']=True
    cases=[]
    for home,away,home_id,away_id in [('SAS','MIN','player_sas-victor-wembanyama','player_min-rudy-gobert'),('GSW','BOS','player_gsw-draymond-green','player_bos-derrick-white')]:
        name=f'interior_exhibition_{home}_{away}';context=make_context(canonical,home,away,name)
        team_ids=[context['indices']['teams_by_espn_id'][k]['id'] for k in ('1','2')]
        active=InteriorExperiment(tuple(Anchor(tid,compiled[('reference_assumptions_v1',pid)]) for tid,pid in zip(team_ids,(home_id,away_id),strict=True)))
        control=InteriorExperiment((),tuple(team_ids))
        cases.append((name,context,control,active))
    games=[]
    for name,context,control,active in cases:
        for seed in (17,29):
            a=sim.sim_game_with_context(context,name,'sandbox-sim',seed,interior_experiment=control)
            b=sim.sim_game_with_context(context,name,'sandbox-sim',seed,interior_experiment=active)
            validate_accounting(a);validate_accounting(b)
            write(output,f'game-{name}-{seed}-control.json',to_plain(a))
            write(output,f'game-{name}-{seed}-experimental.json',to_plain(b))
            games.append({'case':name,'seed':seed,'control':summary(a),'experimental':summary(b)})
    write(output,'games.json',games)
    # Default-off differential reference: full real-roster response, both seeds,
    # both original modes. No experimental result is compared for old parity.
    reference_path=ROOT/'output/interior-defense-experiment-2026-11-13/sim-reference.py'
    spec=importlib.util.spec_from_file_location('nba_gm_data._interior_run_reference',reference_path)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    parity=[]
    for name,context,_,_ in cases:
        for mode in sorted(sim.SIM_MODES):
            for seed in (17,29):
                before=to_plain(old.sim_game_with_context(context,name,mode,seed))
                after=to_plain(sim.sim_game_with_context(context,name,mode,seed))
                assert before==after
                parity.append({'case':name,'mode':mode,'seed':seed,'complete_result_equal':True,'digest':fingerprint(after)})
    write(output,'default-off-parity.json',parity)
    # Input serialization/reconstruction only. This is NOT app advancement or
    # daily/bulk career verification: no action path enables this experiment.
    name,context,control,active=cases[0]
    original=to_plain(sim.sim_game_with_context(context,name,'sandbox-sim',29,interior_experiment=active))
    restored=InteriorExperiment(tuple(Anchor(a.team_id,compile_profile(PlayerInputs(json.loads(json.dumps(a.profile.inputs.to_dict()))),research_scenario=True),a.context) for a in active.anchors))
    assert original==to_plain(sim.sim_game_with_context(context,name,'sandbox-sim',29,interior_experiment=restored))
    del original,restored
    economics=[consumer_probe(canonical,compiled[('reference_assumptions_v1',pid)]) for pid in packet['identities']]
    write(output,'economic-consumers.json',economics)
    # Unprofiled wall samples; no retained game batches, no forced GC.
    timings={}
    for label,experiment in [('experimental_no_anchor_control',control),('experimental_anchor',active),('ordinary_default',None)]:
        t=time.perf_counter();r=sim.sim_game_with_context(context,name,'sandbox-sim',17,interior_experiment=experiment)
        first=time.perf_counter()-t;del r
        samples=[];serialization=[]
        for _ in range(5):
            t=time.perf_counter();r=sim.sim_game_with_context(context,name,'sandbox-sim',17,interior_experiment=experiment);samples.append(time.perf_counter()-t)
            t=time.perf_counter();encoded=json.dumps(to_plain(r),separators=(',',':'));serialization.append(time.perf_counter()-t);del r,encoded
        timings[label]={'first_observed_s':first,'samples_s':samples,'median_s':statistics.median(samples),'range_s':[min(samples),max(samples)],'serialization_median_s':statistics.median(serialization),'scope':'warm prepared unchanged game inputs; NOT HTTP/app-action latency or comparable old-outcome speedup'}
    write(output,'timings.json',timings)
    # Separate attribution, not added to wall samples.
    profiler=cProfile.Profile();profiler.enable();r=sim.sim_game_with_context(context,name,'sandbox-sim',17,interior_experiment=active);profiler.disable();del r
    profiler.dump_stats(str(output/'profile.pstats'))
    with (output/'profile.txt').open('w') as handle:pstats.Stats(profiler,stream=handle).sort_stats('cumulative').print_stats(35)
    # Bounded same-process retained ownership probe; discard every response.
    tracemalloc.start();memory=[];rss_start=rss_kib();weak=[]
    for i in range(8):
        local=InteriorExperiment(tuple(Anchor(a.team_id,compile_profile(a.profile.inputs,research_scenario=True),a.context) for a in active.anchors))
        weak.extend(weakref.ref(a.profile) for a in local.anchors);weak.append(weakref.ref(local))
        r=sim.sim_game_with_context(context,name,'sandbox-sim',17+i,interior_experiment=local)
        weak.append(weakref.ref(r));del r,local
        current,peak=tracemalloc.get_traced_memory();memory.append({'iteration':i+1,'traced_current_bytes':current,'traced_peak_bytes':peak,'rss_kib':rss_kib(),'remaining_probe_roots':sum(ref() is not None for ref in weak)})
    before_gc=tracemalloc.get_traced_memory()[0];gc.collect();after_gc=tracemalloc.get_traced_memory()[0];tracemalloc.stop()
    assert not any(ref() is not None for ref in weak)
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform=='darwin':peak/=1024
    write(output,'memory.json',{'scope':'eight same-process short games after warm-up; prior cohort/quote results intentionally held, not a whole-server leak audit','rss_start_kib':rss_start,'samples':memory,'traced_before_diagnostic_gc':before_gc,'traced_after_diagnostic_gc':after_gc,'process_peak_rss_kib':peak,'all_probe_roots_released':True,'production_gc_added':False})
    assert RESEARCH.read_bytes()==source
    write(output,'summary.json',{'research_packet_sha256':hashlib.sha256(source).hexdigest(),'research_scenarios_compiled':len(compiled),'interaction_cases':len(matrix),'coefficient_cases':len(sensitivity),'geometry_cases':len(geometry),'short_game_pairs':len(games),'default_off_complete_result_cases':len(parity),'input_reload_equal':True,'app_daily_bulk_reload':'not reached; no app-action activation','production_population':False,'calibration_status':'introductory only; no tuning against legacy offense or named OVR targets','timings':timings})
    print(json.dumps({'games':games,'timings':timings,'memory_last':memory[-1],'default_off_cases':len(parity),'research_scenarios':len(compiled)},indent=2))


if __name__=='__main__':main()
