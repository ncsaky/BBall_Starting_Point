"""Bounded default-OFF screen/navigation evidence; no app actions or saves.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_screen_navigation_experiment.py --output output/screen-navigation-2026-11-13/verified
"""
from collections import Counter
from dataclasses import fields,replace
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
import argparse

from nba_gm_data import sim
from nba_gm_data.interior_defense import fingerprint
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.player_model import validate_input_section
from nba_gm_data.schema import to_plain
from nba_gm_data.screen_navigation import resolve_screen
from experiments.screen_navigation.fixtures import screen_fixture
from experiments.creation_passing.fixtures import action_state
from scripts.run_interior_defense_experiment import make_context

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/screen-navigation-2026-11-13'
REF=BASE/'reference'
PACKET=ROOT/'docs/ratings-evidence-2026-10-29/SCREEN_NAVIGATION_INPUTS_2026_11_13.json'


def write(out,name,data):(out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def frozen(name):
    spec=importlib.util.spec_from_loader('nba_gm_data._screen_runner_'+name,SourceFileLoader('nba_gm_data._screen_runner_'+name,str(REF/(name+'.py.reference'))))
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m


def frozen_config(config,modules):
    defense=modules['nba_gm_data.interior_defense'];offense=modules['nba_gm_data.offense_response'];creation=modules['nba_gm_data.creation_passing']
    anchors=tuple(defense.Anchor(a.team_id,a.profile,a.context) for a in config.anchors);off=config.offense
    if off is not None:
        c=off.creation
        if c is not None:c=creation.CreationExperiment(**{f.name:getattr(c,f.name) for f in fields(creation.CreationExperiment)})
        off=offense.CombinedOffense(**({f.name:getattr(off,f.name) for f in fields(offense.CombinedOffense)}|{'creation':c}))
    return defense.InteriorExperiment(**({f.name:getattr(config,f.name) for f in fields(defense.InteriorExperiment)}|{'anchors':anchors,'offense':off}))


def run(c,x,seed=17,mode='replay-real-minutes'):return sim.sim_game_with_context(c,'interior_fixture',mode,seed,interior_experiment=x)


def events(r):return [e for t in r.team_lines for e in t['interior_experiment']['offense_attack_ledger']]


def summary(r):
    ev=events(r)
    return {'scores':[r.home_score,r.away_score],'possessions':r.possessions,'outcomes':dict(Counter(e['outcome'] for e in ev)),
        'choices':dict(Counter(e['creation_chain'].get('choice','before_choice_loss') for e in ev)),
        'routes':dict(Counter(e['creation_chain']['screen_action'].get('route','no_screen') for e in ev)),
        'timely_help':sum(e['creation_chain'].get('help',{}).get('timely',False) for e in ev),
        'selected_roller_contests':sum(e.get('contest_defender_id') is not None and e.get('contest_defender_id')==e['creation_chain']['screen_action'].get('roller_defender_id') and e['coupled_opportunity']['defense_response']['coverage_available']>0 for e in ev if e.get('coupled_opportunity')),
        'stats':[{k:t[k] for k in ('team_id','points','possessions','fga','fgm','fg3a','fg3m','fta','ftm','turnovers','personal_fouls','steals','blocks','assists','rebounds','offensive_rebounds','defensive_rebounds')} for t in r.team_lines],
        'accounting_passed':True,'digest':fingerprint(to_plain(r))}


def core(r):return to_plain({f.name:getattr(r,f.name) for f in fields(r) if f.name!='team_lines'}|{'team_lines':[{k:v for k,v in t.items() if k!='interior_experiment'} for t in r.team_lines]})


def configuration():
    cases=[]
    recovery_controls={f'{team}_{i}':{'S16':0,'S19':0,'S20':0,'F03.execution':95,'F04.execution':95,'P03':290,'P10':60,'P07':4,'S40':95,'T15':0} for team in ('team_a','team_b') for i in range(5)}
    for label,kwargs in [('roll',{}),('slip',{'route':'slip'}),('hold',{'route':'screen'}),('stay',{'route':'slip','coverage':'stay'}),
        ('near_help',{'route':'slip','changes':{'team_b_4':{'T01':.05},'team_a_4':{'T15':1,'S38':95,'S44':95,'P05':8}}}),
        ('no_help',{'route':'slip','changes':{'team_b_4':{'T01':.05},'team_a_4':{'T15':0,'S38':95,'S44':95,'P05':8}}}),
        ('weak_pass',{'route':'slip','changes':{'team_b_0':{'F03.execution':5,'F04.execution':5}}}),
        ('strong_pass',{'route':'slip','changes':{'team_b_0':{'F03.execution':95,'F04.execution':95}}}),
        ('near_recovery',{'route':'slip','changes':recovery_controls})]:
        c,x=screen_fixture(**kwargs)
        if label=='near_recovery':x=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,setups=tuple(replace(s,enabled_pass_families=('F03',)) for s in x.offense.creation.setups))))
        cases.append((label,c,x))
    c,x=screen_fixture();s=x.offense.creation;cases.append(('no_call',c,replace(x,offense=replace(x.offense,creation=replace(s,screens=replace(s.screens,calls=()))))))
    c,x=screen_fixture(changes={f'{team}_{i}':{'S27':10} for team in ('team_a','team_b') for i in range(5)})
    s=x.offense.creation;screens=replace(s.screens,calls=tuple(replace(call,screener_start=(1.4 if call.creator_start[0]>0 else -1.4,5.0)) for call in s.screens.calls))
    cases.append(('late_screen',c,replace(x,offense=replace(x.offense,creation=replace(s,screens=screens)))))
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=BASE/'verified');out=ap.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    start=json.loads((REF/'hashes.json').read_text())
    authenticated={}
    for name in ('creation_passing','interior_game','offense_response','shot_geometry','interior_defense','sim'):
        digest=hashlib.sha256((REF/(name+'.py.reference')).read_bytes()).hexdigest();assert digest==start[f'src/nba_gm_data/{name}.py'];authenticated[name]=digest
    cases=configuration();games=[];branches=Counter();outcomes=Counter();choices=Counter()
    for label,c,x in cases:
        for seed in (17,29):
            r=run(c,x,seed);validate_accounting(r);row=summary(r);games.append({'case':label,'seed':seed,**row})
            branches.update(row['routes']);outcomes.update(row['outcomes']);choices.update(row['choices']);write(out,f'game-{label}-{seed}.json',to_plain(r))
    assert {'roll','slip','screen','no_screen'}<=set(branches)
    assert {'illegal_screen','handling_loss','failed_catch','inaccurate_delivery','made_fg','shooting_foul','reset'}<=set(outcomes)
    assert {'F03','F04','F06','finish','reset'}<=set(choices)
    assert sum(g['timely_help'] for g in games if g['case']=='near_help')>0
    assert sum(g['selected_roller_contests'] for g in games if g['case']=='near_recovery')>0
    write(out,'short-games.json',games)
    # One-at-a-time causal phase samples. Complete fixtures are synthetic; source
    # packet records are validated separately and never filled in place.
    causal=[]
    for pid,key,values in [('team_b_1','S27',(10,95)),('team_b_1','S28',(10,95)),('team_b_1','P04',(75,135)),('team_b_1','P01',(175,220)),('team_a_0','S35',(5,95)),('team_a_0','P07',(1,4)),('team_a_0','S41',(10,95)),('team_a_0','S44',(10,95))]:
        for value in values:
            _,x=screen_fixture(changes={pid:{key:value}});state=action_state(x);d=[.5]*48;d[42]=.999
            phase=resolve_screen(state['screens'],state['profiles']['team_b_0'],state['setups']['team_b_0'],d)
            causal.append({'actor':pid,'input':key,'value':value,'screen_response':phase,'scope':'synthetic response control, not calibrated player estimate'})
    write(out,'causal-responses.json',causal)
    modules={f'nba_gm_data.{name}':frozen(name) for name in ('creation_passing','offense_response','interior_defense','shot_geometry')}
    with patch.dict(sys.modules,modules):old_kernel=frozen('interior_game');old_sim=frozen('sim')
    parity=[];prior=[]
    canonical=json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text());canonical['_allow_internal_caches']=True
    for home,away in (('SAS','MIN'),('GSW','BOS')):
        name=f'screen_disabled_{home}_{away}';ctx=make_context(canonical,home,away,name)
        for mode in sorted(sim.SIM_MODES):
            for seed in (17,29):
                now=sim.sim_game_with_context(ctx,name,mode,seed)
                with patch.dict(sys.modules,modules):before=old_sim.sim_game_with_context(ctx,name,mode,seed)
                assert to_plain(now)==to_plain(before)
                parity.append({'teams':[home,away],'seed':seed,'mode':mode,'complete_result_equal':True,'digest':fingerprint(to_plain(now))})
    del canonical,ctx,now,before
    c,x=screen_fixture();off=replace(x.offense,creation=replace(x.offense.creation,screens=None));prior_creation=replace(x,offense=off)
    for label,config in [('interior',replace(x,offense=None)),('coupled',replace(x,offense=replace(x.offense,creation=None))),('creation',prior_creation)]:
        for mode in sorted(sim.SIM_MODES):
            for seed in (17,29):
                now=run(c,config,seed,mode);a,b=c['canonical']['teams'];g=c['schedule'][0]
                pools=[sim.game_player_pool(c,'interior_fixture',t,mode,game_date=g['gameDate']) for t in (a,b)]
                with patch.dict(sys.modules,modules):before=old_kernel.simulate_interior_game(c['canonical'],g,a,b,*pools,mode,seed,frozen_config(config,modules))
                assert to_plain(now)==to_plain(before)
                prior.append({'path':label,'seed':seed,'mode':mode,'complete_result_equal':True,'digest':fingerprint(to_plain(now))})
    write(out,'parity.json',{'authenticated_references':authenticated,'full_module_reference_swap':True,'ordinary_disabled':parity,'prior_experiments':prior})
    timing={}
    for label,config in [('ordinary_default',None),('interior',replace(x,offense=None)),('coupled',replace(x,offense=replace(x.offense,creation=None))),('prior_creation',prior_creation),('screen_navigation',x)]:
        r=run(c,config);del r;samples=[];serialization=[];core_serialization=[];sizes=[];core_sizes=[]
        for _ in range(5):
            t=time.perf_counter();r=run(c,config);samples.append(time.perf_counter()-t)
            t=time.perf_counter();data=json.dumps(to_plain(r),separators=(',',':'));serialization.append(time.perf_counter()-t);sizes.append(len(data.encode()));del data
            t=time.perf_counter();data=json.dumps(core(r),separators=(',',':'));core_serialization.append(time.perf_counter()-t);core_sizes.append(len(data.encode()));del data,r
        timing[label]={'samples_s':samples,'median_s':statistics.median(samples),'range_s':[min(samples),max(samples)],'full_json_median_s':statistics.median(serialization),'core_json_median_s':statistics.median(core_serialization),'full_bytes':sizes[-1],'core_bytes':core_sizes[-1],
            'scope':'game timing includes profile/snapshot gates, diagnostic construction and accounting; serialization outside game timing; ordinary path has its existing full-game budget, all experimental paths have 16 regulation possessions per side'}
    write(out,'timings-and-payload.json',timing)
    gc.collect();tracemalloc.start();refs=[];memory=[]
    for i in range(6):
        ctx,config=screen_fixture()
        for root in (config,config.offense,config.offense.creation,config.offense.creation.screens,config.offense.creation.screens.profiles[0],config.offense.creation.screens.profiles[0].inputs):refs.append(weakref.ref(root))
        del root
        r=run(ctx,config,17+i);refs.append(weakref.ref(r));del r,config,ctx
        current,peak=tracemalloc.get_traced_memory();memory.append({'iteration':i+1,'current_bytes':current,'peak_bytes':peak,'rss_kib':int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())],text=True).strip()),'live_probed_roots':sum(w() is not None for w in refs)})
    before_gc=tracemalloc.get_traced_memory()[0];gc.collect();after_gc=tracemalloc.get_traced_memory()[0];tracemalloc.stop();assert not any(w() is not None for w in refs)
    write(out,'memory-release.json',{'samples':memory,'probed_roots':len(refs),'all_released':True,'before_diagnostic_gc':before_gc,'after_diagnostic_gc':after_gc,'production_gc_added':False,'scope':'six fresh-fixture short same-process calls, not server/long-career stability'})
    packet_summary={'status':'not_required_for_synthetic_mechanism'}
    if PACKET.exists():
        raw=PACKET.read_bytes();packet=json.loads(raw);validate_input_section(packet['player_input_section'])
        for scenario in packet['scenarios']:validate_input_section(scenario['input_section'])
        unknown=sum(r['status']=='unknown' for d in packet['player_input_section']['players'].values() for r in d['inputs'].values())
        packet_summary={'packet_sha256':hashlib.sha256(raw).hexdigest(),'source_players':len(packet['player_input_section']['players']),'source_unknowns':unknown,'synthetic_sections':len(packet['scenarios']),'no_source_or_pilot_completion_performed':True,'compiler_contract':'screen compiler consumes explicit interior synthetic technique/capacity/dimensional protocols; no unreviewed source-scale or m/s adapter added'}
        assert raw==PACKET.read_bytes()
    write(out,'research-preservation.json',packet_summary)
    write(out,'configuration.json',{'scope':'source-independent complete synthetic fixture','authoritative_inputs':{p.player_id:p.inputs.to_dict() for p in x.offense.profiles},'screen_calls':[vars(call) for call in x.offense.creation.screens.calls],'screen_coefficients':vars(x.offense.creation.screens.coefficients),'screen_revision':x.offense.creation.screens.revision,'roles':{p.player_id:p.roles for p in x.offense.creation.screens.profiles},'unsupported':['off-ball screens','pop','rescreens','switch/drop policy engine','overlapping helper/roller-defender role','full rotations','source-scale/movement calibration']})
    changed=[p for p,h in start.items() if Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    external=[p for p in changed if p.startswith('docs/ratings-evidence-2026-10-29/')]
    owned={'src/nba_gm_data/creation_passing.py','src/nba_gm_data/interior_game.py','docs/SCREEN_NAVIGATION_ACTIVE_TASK.md','docs/SCREEN_NAVIGATION_EXPERIMENT_2026_11_13.md'}
    unexpected=[p for p in changed if p not in owned and p not in external];assert not unexpected,unexpected
    tracked=['src/nba_gm_data/screen_navigation.py','src/nba_gm_data/creation_passing.py','src/nba_gm_data/interior_game.py','tests/test_screen_navigation.py','experiments/screen_navigation/fixtures.py','scripts/run_screen_navigation_experiment.py']
    write(out,'source-manifest.json',{'changed_existing':changed,'research_owned_external_changes':external,'unexpected_changes':unexpected,'hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in tracked}})
    final={'default_off':True,'short_combined_games':len(games),'regulation_possessions_per_side':16,'causal_responses':len(causal),'routes_exercised':dict(branches),'choices_exercised':dict(choices),'outcomes_exercised':dict(outcomes),'ordinary_real_roster_complete_comparisons':len(parity),'prior_experiment_complete_comparisons':len(prior),'released_roots':len(refs),'research':packet_summary,'app_daily_bulk_economic_parity':'unwired; not claimed','no_activation_or_calibration':True}
    write(out,'summary.json',final);print(json.dumps(final,indent=2))


if __name__=='__main__':main()
