"""Bounded default-off coupled mechanism evidence, not league calibration.

PYTHONPATH=src:. .venv/bin/python scripts/run_offense_interior_interaction.py
No network, save writes, server changes, seasons or market actions.
"""
from __future__ import annotations
import argparse
import cProfile
from dataclasses import asdict,replace
import gc
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import itertools
import json
import math
import os
from pathlib import Path
import pstats
import random
import statistics
import subprocess
import time
import tracemalloc
import weakref

from nba_gm_data import sim
from nba_gm_data.interior_defense import ArrivalContext,compile_profile,interior_response,fingerprint
from nba_gm_data.interior_game import validate_accounting,shot_probabilities
from nba_gm_data.offense_response import (compile_offense,shooting_response,free_throw_response,finishing_response,credibility,
    OffenseCoefficients,offensive_spatial_profile,prepare_coupled,plan_attack)
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.schema import to_plain
from nba_gm_data.shot_geometry import ShotGeometry
from experiments.offense_interior.fixtures import offensive_document,combined_fixture
from scripts.run_interior_defense_experiment import make_context

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT/'docs/ratings-evidence-2026-10-29/OFFENSE_INTERIOR_INTERACTION_INPUTS_2026_11_13.json'


def write(out,name,data):(out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')

def rss():return int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())],text=True).strip())

def run(context,config,seed=17):return sim.sim_game_with_context(context,'interior_fixture',seed=seed,interior_experiment=config)


def stats(result):
    return {'score':[result.home_score,result.away_score],'possessions':result.possessions,
        'regulation_score':[sum(e.get('points',0) for e in t['interior_experiment']['offense_attack_ledger'] if e['period']=='regulation') for t in result.team_lines],
        'regulation_perimeter_fga':[sum(e['period']=='regulation' and e.get('zone')=='perimeter' and e['outcome'] in ('made_fg','missed_fg','block') for e in t['interior_experiment']['offense_attack_ledger']) for t in result.team_lines],'teams':[{k:t[k] for k in ('team_id','fga','fgm','fg3a','fg3m','fta','ftm','blocks','personal_fouls','rebounds','offensive_rebounds','defensive_rebounds','turnovers')} for t in result.team_lines],
        'anchor_xy':[t['interior_experiment']['combined_offense']['anchor_position_m'] for t in result.team_lines],
        'redirects':[sum(bool(e.get('redirected')) for e in t['interior_experiment']['offense_attack_ledger']) for t in result.team_lines],
        'failed_receptions':[sum(e['outcome']=='reception_turnover' for e in t['interior_experiment']['offense_attack_ledger']) for t in result.team_lines]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'output/offense-interior-interaction-2026-11-13');out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    source=PACKET.read_bytes();packet=json.loads(source);validate_input_section(packet['player_input_section'])
    research=[]
    for scenario in packet['scenarios']:
        validate_input_section(scenario['input_section'])
        for pid,doc in scenario['input_section']['players'].items():
            p=compile_offense(PlayerInputs(doc),research_scenario=True,two_point_rim_fraction=.65)
            research.append({'scenario':scenario['scenario_id'],'player_id':pid,'source_revision':p.revision,'source_document_unchanged':p.inputs.to_dict()==doc,
                'scope':'scenario, not real player forecast/ranking','controlled_two_point_rim_fraction':.65,
                'credible_points_per_perimeter_opportunity':credibility(p),'shooting':{m:shooting_response(p,mode=m) for m in ('catch','pull_up','movement')},
                'free_throw_probability':free_throw_response(p),'finishes':{k:finishing_response(p,k,contact=1 if k=='contact_layup' else 0) for k in ('layup','contact_layup','floater','dunk','lob')}})
    write(out,'research-sensitivity.json',{'packet_sha256':hashlib.sha256(source).hexdigest(),'compiled_scenario_profiles':len(research),'responses':research})
    examples=[]
    for skill,will in ((90,.9),(90,.1),(35,.9)):
        context,config=combined_fixture(shooting=skill,willingness=will)
        for seed in (17,29):
            result=run(context,config,seed);validate_accounting(result)
            examples.append({'shooting':skill,'willingness':will,'seed':seed,**stats(result)})
            write(out,f'game-skill-{skill}-willingness-{will}-seed-{seed}.json',to_plain(result))
    write(out,'game-examples.json',examples)
    # Controlled interaction matrix: same shared event kernel, a few short
    # fixtures. No adjustment of grades to make a named player rank first.
    matrix=[]
    for skill,will,poa in itertools.product((35,90),(.1,.9),(0,1)):
        context,config=combined_fixture(shooting=skill,willingness=will,poa=poa)
        result=run(context,config,17);matrix.append({'shooting':skill,'willingness':will,'controlled_poa':poa,**stats(result)})
    write(out,'interaction-games.json',matrix)
    # Geometry and local conversion sensitivities use the exact response
    # functions consumed by the kernel, not a second scoring simulator.
    defender=compile_profile(PlayerInputs(offensive_document('defender',reach=290,jump=60)))
    geometry=[]
    for height,position,angle,delay in itertools.product((280,320,370),((0,1),(3,1)),(0,45,90),(0,.25,.75)):
        g=ShotGeometry(0,1,height,*position,approach_angle_deg=angle,attack_time_s=.8,preparation_s=.2)
        response=interior_response(defender,ArrivalContext(recognition_delay_s=delay),geometry=g)
        geometry.append({'release_height_cm':height,'defender_position_m':position,'approach_angle_deg':angle,'recognition_delay_s':delay,'response':response})
    write(out,'geometry-matrix.json',geometry)
    local=[]
    base=compile_offense(PlayerInputs(offensive_document('local')))
    for number in (1,2,3,7,8,9,10,11,12,13,14,15):
        for grade in (40,90):
            doc=base.inputs.to_dict();doc['inputs'][f'S{number:02d}']['value']['grade']=grade;p=compile_offense(PlayerInputs(doc))
            local.append({'input':f'S{number:02d}','grade':grade,'shooting_7m':{m:shooting_response(p,mode=m,pressure=.8,defender_arrival_s=.4) for m in ('catch','pull_up','movement')},
                'shooting_9m':shooting_response(p,distance_m=9),'free_throw_probability':free_throw_response(p),
                'finishes':{k:finishing_response(p,k,contact=1 if k=='contact_layup' else 0) for k in ('layup','contact_layup','floater','dunk','lob')}})
    write(out,'single-input-sensitivity.json',local)
    sensitivity=[]
    for field in ('shooting_skill_span','range_penalty_per_m','positioning_pull_points','contact_penalty'):
        for factor in (.75,1.25):
            coefficients=replace(OffenseCoefficients(),**{field:getattr(OffenseCoefficients(),field)*factor})
            context,config=combined_fixture(offense_coefficients=coefficients);result=run(context,config,17)
            sensitivity.append({'coefficient':field,'factor':factor,**stats(result)})
    write(out,'coefficient-sensitivity.json',sensitivity)
    # Full default-off comparison across actual current rosters, without
    # installing experimental profiles into any canonical player or save.
    canonical=json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text());canonical['_allow_internal_caches']=True
    path=ROOT/'output/offense-interior-interaction-2026-11-13/sim.py.reference'
    spec=importlib.util.spec_from_loader('nba_gm_data._offense_reference_sim',SourceFileLoader('nba_gm_data._offense_reference_sim',str(path)))
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    parity=[]
    for home,away in (('SAS','MIN'),('GSW','BOS')):
        name=f'off_default_{home}_{away}';context=make_context(canonical,home,away,name)
        for seed,mode in itertools.product((17,29),sorted(sim.SIM_MODES)):
            a=to_plain(sim.sim_game_with_context(context,name,mode,seed));b=to_plain(old.sim_game_with_context(context,name,mode,seed));assert a==b
            parity.append({'teams':[home,away],'seed':seed,'mode':mode,'complete_result_equal':True,'sha256':fingerprint(a)})
    write(out,'default-off-parity.json',parity)
    # One authoritative input map; both derived projections bind to it.
    _,reference_config=combined_fixture()
    write(out,'configuration.json',{
        'scope':'explicit unnamed synthetic reference, not production player data',
        'authoritative_player_inputs':{p.player_id:p.inputs.to_dict() for p in reference_config.offense.profiles},
        'anchors':[{'team_id':a.team_id,'player_id':a.profile.inputs.player_id,'context':asdict(a.context)} for a in reference_config.anchors],
        'deployments':[asdict(d) for d in reference_config.offense.deployments],
        'anchor_assignments':reference_config.offense.anchor_assignments,'finish_mix':reference_config.offense.finish_mix,
        'controlled_delivery_quality':reference_config.offense.delivery_quality,
        'controlled_primary_pressure':reference_config.offense.primary_perimeter_pressure,
        'controlled_primary_arrival_s':reference_config.offense.primary_arrival_s,
        'controlled_assist_probability':reference_config.offense.assist_credit_probability,
        'controlled_oreb_probability':reference_config.offense.offensive_rebound_probability,
        'offense_coefficients':asdict(OffenseCoefficients()),'research_two_point_rim_fraction':.65})
    # Exposed-boundary input reconstruction; this does NOT exercise app-day
    # advancement, daily/bulk or a saved career's midpoint reload.
    context,config=combined_fixture();before=to_plain(run(context,config,29))
    restored=replace(config,offense=replace(config.offense,profiles=tuple(compile_offense(PlayerInputs(json.loads(json.dumps(p.inputs.to_dict())))) for p in config.offense.profiles)))
    assert before==to_plain(run(context,restored,29));del before,restored
    # Sequential warm wall samples, separately from profiler/allocation work.
    timing={}
    for label,active in (('interior_only',replace(config,offense=None)),('coupled',config),('ordinary_default',None)):
        t=time.perf_counter();r=run(context,active);first=time.perf_counter()-t;del r
        samples=[];serialization=[]
        for _ in range(5):
            t=time.perf_counter();r=run(context,active);samples.append(time.perf_counter()-t)
            t=time.perf_counter();text=json.dumps(to_plain(r),separators=(',',':'));serialization.append(time.perf_counter()-t);del r,text
        timing[label]={'first_observed_s':first,'median_s':statistics.median(samples),'range_s':[min(samples),max(samples)],'samples_s':samples,'json_median_s':statistics.median(serialization),'scope':'warm short fixture engine calls, NOT HTTP or equivalent-outcome speedup'}
    write(out,'timings.json',timing)
    profiler=cProfile.Profile();profiler.enable();r=run(context,config);profiler.disable();del r
    profiler.dump_stats(str(out/'profile.pstats'))
    with (out/'profile.txt').open('w') as h:pstats.Stats(profiler,stream=h).sort_stats('cumulative').print_stats(30)
    tracemalloc.start();memory=[];references=[]
    for i in range(6):
        local=replace(config,offense=replace(config.offense));references.append(weakref.ref(local));references.append(weakref.ref(local.offense))
        r=run(context,local,17+i);references.append(weakref.ref(r));del r,local
        current,peak=tracemalloc.get_traced_memory();memory.append({'iteration':i+1,'current_bytes':current,'peak_bytes':peak,'rss_kib':rss(),'live_probe_roots':sum(x() is not None for x in references)})
    before_gc=tracemalloc.get_traced_memory()[0];gc.collect();after_gc=tracemalloc.get_traced_memory()[0];tracemalloc.stop();assert not any(x() is not None for x in references)
    write(out,'memory.json',{'samples':memory,'before_diagnostic_gc':before_gc,'after_diagnostic_gc':after_gc,'all_probe_roots_released':True,'production_gc':False,'scope':'six warm fixed-fixture calls; no full-server or long-career claim'})
    assert PACKET.read_bytes()==source
    write(out,'summary.json',{'stage':'B','research_packet_sha256':hashlib.sha256(source).hexdigest(),'compiled_research_scenarios':len(research),'paired_boundary_seeds':[17,29],
        'sample_games':len(examples),'interaction_cases':len(matrix),'geometry_cases':len(geometry),'single_input_cases':24,
        'coefficient_cases':len(sensitivity),'default_off_complete_result_cases':len(parity),'input_reconstruction_equal':True,'app_daily_bulk_reload':'not reached/not claimed',
        'runtime':timing,'no_production_calibration_or_activation':True})
    print(json.dumps({'examples':examples,'timings':timing,'memory_final':memory[-1],'research_scenario_profiles':len(research),'default_off_parity_cases':len(parity)},indent=2))


if __name__=='__main__':main()
