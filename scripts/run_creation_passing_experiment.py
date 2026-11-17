"""Bounded milestone-4 evidence; offline, default OFF, no saves or live wiring.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_creation_passing_experiment.py --output output/creation-passing-defense-2026-11-13/verified
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict,fields,replace
import gc
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import tracemalloc
import weakref
from unittest.mock import patch

from nba_gm_data import sim
from nba_gm_data.creation_passing import compile_interaction,containment_response,delivery_response,handling_loss,helper_response,FAMILIES
from nba_gm_data.interior_defense import fingerprint
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.schema import to_plain
from experiments.creation_passing.fixtures import creation_fixture,action_state
from scripts.run_interior_defense_experiment import make_context

ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'output/creation-passing-defense-2026-11-13'
PACKET=ROOT/'docs/ratings-evidence-2026-10-29/CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.json'


def write(out,name,data):(out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def reference(name):
    spec=importlib.util.spec_from_loader('nba_gm_data._m4_runner_'+name,SourceFileLoader('nba_gm_data._m4_runner_'+name,str(REF/(name+'.py.reference'))))
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m


def run(context,config,seed=17,mode='replay-real-minutes'):
    return sim.sim_game_with_context(context,'interior_fixture',mode,seed,interior_experiment=config)


def summary(result):
    events=[e for t in result.team_lines for e in t['interior_experiment']['offense_attack_ledger']]
    return {'scores':[result.home_score,result.away_score],'possessions':result.possessions,
        'outcomes':dict(Counter(e['outcome'] for e in events)),
        'choices':dict(Counter(e['creation_chain'].get('choice','before_choice_loss') for e in events)),
        'timely_help_events':sum(e['creation_chain'].get('help',{}).get('timely',False) for e in events),
        'committed_help_events':sum(e['creation_chain'].get('help',{}).get('committed',False) for e in events),
        'stats':[{k:t[k] for k in ('team_id','points','fga','fgm','fg3a','fg3m','fta','ftm','turnovers','steals','assists','rebounds','offensive_rebounds','defensive_rebounds','personal_fouls','blocks')} for t in result.team_lines],
        'accounting_passed':True,'result_sha256':fingerprint(to_plain(result))}


def core(result):
    # Filter before conversion so diagnostics are not traversed in this cost.
    return to_plain({f.name:getattr(result,f.name) for f in fields(result) if f.name!='team_lines'}|{'team_lines':[{k:v for k,v in t.items() if k!='interior_experiment'} for t in result.team_lines]})


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=REF/'verified');out=ap.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    raw=PACKET.read_bytes();packet=json.loads(raw);validate_input_section(packet['player_input_section']);research=[]
    rejected=[]
    for pid,doc in packet['player_input_section']['players'].items():
        try:compile_interaction(PlayerInputs(doc),research_scenario=True)
        except ValueError as e:rejected.append({'player_id':pid,'missing_dependency':str(e)})
        else:raise AssertionError('Named sparse source unexpectedly compiled as complete actor')
    for scenario in packet['scenarios']:
        validate_input_section(scenario['input_section'])
        for pid,doc in scenario['input_section']['players'].items():
            p=compile_interaction(PlayerInputs(doc),research_scenario=True)
            assert p.inputs.to_dict()==doc
            research.append({'scenario':scenario['scenario_id'],'actor':pid,'revision':p.revision,'scope':'source-independent synthetic actor only',
                'unknown_disruption':{k:p.skill(k) for k in ('S42','S43')},'handling_at_pressure_0_8':handling_loss(p,.8,1),
                'help_from_4m':helper_response(p,(4,1),(0,1),2,.1,.1),
                'passing':{f:delivery_response(p,f,4,.4,.7) for f in FAMILIES}})
    write(out,'research-scenario-responses.json',{'packet_sha256':hashlib.sha256(raw).hexdigest(),'named_sources_not_completed':rejected,'source_unknowns':sum(r['status']=='unknown' for d in packet['player_input_section']['players'].values() for r in d['inputs'].values()),'scenarios':research})
    games=[];all_choices=set();all_outcomes=set()
    for label,families in [('all',FAMILIES)]+[(f,(f,)) for f in FAMILIES]:
        c,x=creation_fixture(families=families,possessions=16)
        for seed in (17,29):
            r=run(c,x,seed);validate_accounting(r);row=summary(r);games.append({'families':label,'seed':seed,**row})
            all_choices.update(row['choices']);all_outcomes.update(row['outcomes']);write(out,f'game-{label}-{seed}.json',to_plain(r))
    assert set(FAMILIES)|{'finish','reset'}<=all_choices
    assert {'handling_loss','inaccurate_delivery','failed_catch','made_fg','shooting_foul'}<=all_outcomes
    write(out,'short-games.json',games)
    help_games=[]
    for commitment in (0,1):
        c,h=creation_fixture(possessions=16,changes={'team_b_4':{'T01':.05},'team_a_4':{'S38':95,'S44':95,'P05':8,'P07':4,'T15':commitment}})
        for seed in (17,29):
            r=run(c,h,seed);validate_accounting(r);row=summary(r)
            help_games.append({'commitment':commitment,'seed':seed,**row});write(out,f'game-near-help-{commitment}-{seed}.json',to_plain(r))
    assert sum(g['timely_help_events'] for g in help_games if g['commitment']==1)>0
    assert sum(g['timely_help_events'] for g in help_games if g['commitment']==0)==0
    write(out,'near-help-games.json',help_games)
    # Causal response samples use the same mechanism; no named-player grading.
    causal=[]
    for pid,key,values in [('team_b_0','S17',(10,95)),('team_b_0','S19',(10,95)),('team_a_0','S33',(10,95)),('team_a_4','S38',(10,95)),('team_a_4','P07',(1,4)),('team_b_4','S14',(10,95)),('team_b_0','T07',(0,1))]:
        for value in values:
            c,x=creation_fixture(changes={pid:{key:value}},possessions=16);state=action_state(x)
            r=run(c,x);validate_accounting(r)
            causal.append({'player':pid,'input':key,'value':value,'containment':containment_response(state['profiles']['team_b_0'],state['profiles']['team_a_0'],state['setups']['team_b_0']),
                'helper_response':helper_response(state['profiles']['team_a_4'],(4,1),(0,1),2,.1,.1),'game':summary(r),
                'interpretation':'one short seeded mechanism exposure, not an NBA rank or estimate'})
    write(out,'causal-controls.json',causal)
    old_sim=reference('sim');old_kernel=reference('interior_game');old_offense=reference('offense_response');parity=[];prior=[]
    canonical=json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text());canonical['_allow_internal_caches']=True
    for home,away in (('SAS','MIN'),('GSW','BOS')):
        name=f'm4_disabled_{home}_{away}';ctx=make_context(canonical,home,away,name)
        for mode in sorted(sim.SIM_MODES):
            for seed in (17,29):
                a=to_plain(sim.sim_game_with_context(ctx,name,mode,seed));b=to_plain(old_sim.sim_game_with_context(ctx,name,mode,seed));assert a==b
                parity.append({'teams':[home,away],'mode':mode,'seed':seed,'complete_result_equal':True,'sha256':fingerprint(a)})
    del canonical,ctx,a,b
    c,x=creation_fixture(possessions=16);disabled=replace(x,offense=replace(x.offense,creation=None))
    for label,config in [('prior_interior',replace(x,offense=None)),('prior_coupled',disabled)]:
        for mode in sorted(sim.SIM_MODES):
            for seed in (17,29):
                a,b=c['canonical']['teams'];g=c['schedule'][0]
                pools=[sim.game_player_pool(c,'interior_fixture',t,mode,game_date=g['gameDate']) for t in (a,b)]
                now=run(c,config,seed,mode)
                frozen_config=config
                if config.offense is not None:
                    frozen_config=replace(config,offense=old_offense.CombinedOffense(**{f.name:getattr(config.offense,f.name) for f in fields(old_offense.CombinedOffense)}))
                with patch.dict(sys.modules,{'nba_gm_data.offense_response':old_offense}):
                    before=old_kernel.simulate_interior_game(c['canonical'],g,a,b,*pools,mode,seed,frozen_config)
                assert to_plain(now)==to_plain(before)
                prior.append({'path':label,'mode':mode,'seed':seed,'complete_result_equal':True,'sha256':fingerprint(to_plain(now))})
    write(out,'parity.json',{'ordinary_disabled_real_rosters':parity,'prior_experimental_modes':prior,'reference_hashes':{n:hashlib.sha256((REF/(n+'.py.reference')).read_bytes()).hexdigest() for n in ('sim','interior_game','offense_response','shot_geometry')}})
    # Warm game calls include report construction; serialization is separate.
    # Do not mislabel these as an uninstrumented kernel-only benchmark.
    timings={}
    for label,config in [('ordinary_default',None),('interior_only',replace(x,offense=None)),('coupled',disabled),('creation',x)]:
        r=run(c,config);del r;samples=[];full_json=[];core_json=[];full_bytes=[];core_bytes=[]
        for _ in range(5):
            t=time.perf_counter();r=run(c,config);samples.append(time.perf_counter()-t)
            t=time.perf_counter();data=json.dumps(to_plain(r),separators=(',',':'));full_json.append(time.perf_counter()-t);full_bytes.append(len(data.encode()));del data
            t=time.perf_counter();data=json.dumps(core(r),separators=(',',':'));core_json.append(time.perf_counter()-t);core_bytes.append(len(data.encode()));del data,r
        timings[label]={'samples_s':samples,'median_s':statistics.median(samples),'range_s':[min(samples),max(samples)],'full_json_median_s':statistics.median(full_json),'core_json_median_s':statistics.median(core_json),'full_bytes':full_bytes,'core_bytes':core_bytes,'diagnostic_bytes':full_bytes[-1]-core_bytes[-1],
            'scope':'game call includes diagnostic construction and accounting; JSON preparation measured separately; ordinary path has its existing full-game possession budget, experimental paths have 16 regulation possessions per team'}
    write(out,'timings-and-payload.json',timings)
    # New owned configs/inputs each call; weak roots should release without a
    # production collection policy. Diagnostic GC only after the sample window.
    gc.collect();tracemalloc.start();mem=[];refs=[]
    for i in range(6):
        context,config=creation_fixture(possessions=16)
        for root in (config,config.offense,config.offense.creation,config.offense.creation.profiles[0],config.offense.creation.profiles[0].inputs):refs.append(weakref.ref(root))
        del root
        r=run(context,config,17+i);refs.append(weakref.ref(r));del r,config,context
        current,peak=tracemalloc.get_traced_memory()
        mem.append({'iteration':i+1,'current_bytes':current,'peak_bytes':peak,'rss_kib':int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())],text=True).strip()),'live_probed_roots':sum(w() is not None for w in refs)})
    before_gc=tracemalloc.get_traced_memory()[0];gc.collect();after_gc=tracemalloc.get_traced_memory()[0];tracemalloc.stop();assert not any(w() is not None for w in refs)
    write(out,'memory-release.json',{'samples':mem,'probed_roots':len(refs),'all_released':True,'before_diagnostic_gc_bytes':before_gc,'after_diagnostic_gc_bytes':after_gc,'production_gc_added':False,'scope':'six short same-process calls including fixture creation; not long-career/server stability'})
    assert raw==PACKET.read_bytes()
    write(out,'configuration.json',{'authoritative_inputs':{p.player_id:p.inputs.to_dict() for p in x.offense.profiles},'creation_coefficients':asdict(x.offense.creation.coefficients),'drive_setups':[asdict(s) for s in x.offense.creation.setups],'revision':x.revision,'scope':'complete synthetic fixtures, never named-player completion','retained_controls':['touch exposure','screen separation','roll path/window','receiver defender gap','matchups','rebound support','clock budget/reset/rebound clock','missing T06/T14/full coaching/routes']})
    start=json.loads((REF/'recovery-audit/start-hashes.json').read_text());changed=[p for p,h in start.items() if Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    owned={'src/nba_gm_data/creation_passing.py','src/nba_gm_data/offense_response.py','src/nba_gm_data/interior_game.py','docs/CREATION_PASSING_RECOVERY_CHECKPOINT.md','docs/CREATION_PASSING_DEFENSE_EXPERIMENT_2026_11_13.md'}
    unexpected=[p for p in changed if p not in owned]
    assert not unexpected,unexpected
    write(out,'source-manifest.json',{'changed_since_recovery_snapshot':changed,'unexpected_changes':unexpected,'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/nba_gm_data/creation_passing.py',ROOT/'src/nba_gm_data/interior_game.py',ROOT/'src/nba_gm_data/offense_response.py',ROOT/'src/nba_gm_data/shot_geometry.py',ROOT/'tests/test_creation_passing.py',Path(__file__).resolve()]}})
    final={'default_off':True,'short_games':len(games),'near_help_games':len(help_games),'causal_control_games':len(causal),'research_scenarios':len(research),'named_source_players_left_sparse':len(rejected),'source_unknowns_preserved':964,'full_real_roster_disabled_comparisons':len(parity),'prior_mode_comparisons':len(prior),'choices_exercised':sorted(all_choices),'outcomes_exercised':sorted(all_outcomes),'memory_roots_released':len(refs),'app_daily_bulk_live_economic_parity':'unwired; not claimed','no_calibration_or_activation':True}
    write(out,'summary.json',final);print(json.dumps(final,indent=2))


if __name__=='__main__':main()
