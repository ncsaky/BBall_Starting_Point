"""Bounded milestone-7 comparisons; offline, no production activation.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_pilot_response_calibration.py
"""
import argparse
from contextlib import ExitStack,nullcontext
from dataclasses import replace
import gc
import hashlib
import json
from pathlib import Path
import pstats
import statistics
import time
import tracemalloc
import weakref
from unittest.mock import patch

from nba_gm_data import sim
from nba_gm_data.creation_passing import resolve_drive
from nba_gm_data.interior_defense import fingerprint
from nba_gm_data.interior_game import validate_accounting
from nba_gm_data.schema import to_plain
from experiments.player_input_pilot import probes as named
from experiments.player_input_pilot.pilot import build_pilot,export_layer,prepared,named_config,IDS,variant
from experiments.player_input_pilot.verification import pre_optimization_module,pre_optimization_config,traced_game
from experiments.screen_navigation.fixtures import screen_fixture
from experiments.pilot_response_calibration import probes
from experiments.pilot_response_calibration.fixtures import fixture
from experiments.pilot_response_calibration.verification import reference_modules,reference_config,use_reference,REFERENCE
from experiments.pilot_response_calibration.overlay import apply_overlay,selected_fields
from scripts.run_player_input_pilot import profile_partition,core,comparisons
from scripts.run_interior_defense_experiment import make_context

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'output/pilot-response-calibration-2026-11-14'


def write(out,name,data):
    (out/name).write_text(json.dumps(to_plain(data),indent=2,allow_nan=False)+'\n')


def run(context,config,seed=17,mode='replay-real-minutes'):
    return sim.sim_game_with_context(context,context['schedule'][0]['externalGameId'],mode,seed,interior_experiment=config)


def same_named(pilot,modules,corrected):
    resolver=resolve_drive if corrected else modules['nba_gm_data.creation_passing'].resolve_drive
    def state(p):
        if corrected:
            s=prepared(p);s['spec']=replace(s['spec'],help_response_policy=probes.POLICY)
            return s
        context,config=named_config(p);config=reference_config(config,modules)
        pools={tid:[{'player':row,'minutes':48} for row in context['canonical']['players'] if row['team_id']==tid] for tid in ('pilot_a','pilot_b')}
        anchors={tid:None for tid in pools};contexts={tid:None for tid in pools}
        coupled=modules['nba_gm_data.offense_response'].prepare_coupled(config.offense,pools,anchors,contexts)
        return modules['nba_gm_data.creation_passing'].prepare_creation(config.offense.creation,coupled,pools,anchors,contexts)
    with ExitStack() as stack:
        if not corrected:
            stack.enter_context(use_reference(modules))
            bindings={}
            for module,names in [('creation_passing',('compile_interaction','containment_response','helper_response','delivery_response','sample_delivery','handling_loss','DriveSetup')),
                                 ('screen_navigation',('compile_screen','resolve_screen','ScreenCall','ScreenExperiment')),
                                 ('interior_defense',('compile_profile','interior_response','ArrivalContext')),
                                 ('shot_geometry',('ShotGeometry',))]:
                bindings.update({key:getattr(modules['nba_gm_data.'+module],key) for key in names})
            stack.enter_context(patch.multiple(named,**bindings))
        stack.enter_context(patch.object(named,'resolve_drive',resolver))
        stack.enter_context(patch.object(named,'prepared',state))
        return [named.run_scenario(row) for row in named.scenarios(pilot)]


def parity(out,modules):
    rows=[]
    canonical=json.loads((ROOT/'data/canonical/universe_2026_27_offseason.json').read_text());canonical['_allow_internal_caches']=True
    for home,away in (('SAS','MIN'),('GSW','BOS')):
        name=f'response_off_{home}_{away}';context=make_context(canonical,home,away,name)
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                actual=sim.sim_game_with_context(context,name,mode,seed)
                with use_reference(modules):old=modules['nba_gm_data.sim'].sim_game_with_context(context,name,mode,seed)
                assert to_plain(actual)==to_plain(old)
                rows.append({'path':'ordinary_default_off','teams':[home,away],'seed':seed,'mode':mode,'full_result_equal':True,'digest':fingerprint(to_plain(actual))})
    context,x=screen_fixture(possessions=16)
    for label,config in [('interior',replace(x,offense=None)),('coupled',replace(x,offense=replace(x.offense,creation=None))),
        ('legacy_creation',replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=None)))),('legacy_screen',x)]:
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                actual=run(context,config,seed,mode)
                with use_reference(modules):old=modules['nba_gm_data.sim'].sim_game_with_context(context,'interior_fixture',mode,seed,interior_experiment=reference_config(config,modules))
                assert to_plain(actual)==to_plain(old)
                rows.append({'path':label,'seed':seed,'mode':mode,'full_result_equal':True,'digest':fingerprint(to_plain(actual))})
    write(out,'authenticated-parity.json',rows)
    return rows


def retained_reuse(out,pilot):
    before=pre_optimization_module();rows=[]
    for label in ('native','interpreted_separate_helper'):
        if label=='native':
            context,config=screen_fixture(possessions=16)
            config=replace(config,offense=replace(config.offense,creation=replace(config.offense.creation,help_response_policy=probes.POLICY)))
        else:_,context,config=fixture(pilot,policy=probes.POLICY,coverage='show_then_recover',start=None)
        previous=pre_optimization_config(config,before)
        for seed in (17,29):
            for mode in sorted(sim.SIM_MODES):
                a,ta=traced_game(context,config,seed,mode);b,tb=traced_game(context,previous,seed,mode,pre_optimization=before)
                assert to_plain(a)==to_plain(b) and ta==tb
                rows.append({'fixture':label,'seed':seed,'mode':mode,'full_result_equal':True,'full_rng_stream_equal':True,
                    'draws':sum(r['draws'] for r in ta),'rng_digest':fingerprint(ta),'result_digest':fingerprint(to_plain(a))})
    write(out,'preserved-validation-reuse-parity.json',rows)
    return rows


def accounting(out,pilot,modules):
    rows=[]
    for alias in ('white','castle'):
        for policy in ('legacy_timely_v1',probes.POLICY):
            for seed in (17,29):
                _,context,config=fixture(pilot,alias,policy=policy,coverage='show_then_recover',families=('F03','F04','F06'),start=None)
                result=run(context,config,seed);validate_accounting(result)
                events=[e for team in result.team_lines for e in team['interior_experiment']['offense_attack_ledger']]
                rows.append({'actor':alias,'policy':policy,'seed':seed,'accounting_passed':True,'budget':16,'realized_possessions_per_side':result.possessions,
                    'actions':len(events),'digest':fingerprint(to_plain(result))})
                write(out,f'counterfactual-kernel-{alias}-{policy}-{seed}.json',result)
    write(out,'accounting-checks.json',rows)
    return rows


def costs(out,pilot,modules):
    rows={}
    for label in ('native_screen_10','interpreted_helper_6'):
        if label=='native_screen_10':context,legacy=screen_fixture(possessions=16)
        else:_,context,legacy=fixture(pilot,start=None,coverage='show_then_recover')
        corrected=replace(legacy,offense=replace(legacy.offense,creation=replace(legacy.offense.creation,help_response_policy=probes.POLICY)))
        with use_reference(modules):old=reference_config(legacy,modules)
        measurements={}
        for engine,config in [('old_engine',old),('corrected_policy',corrected)]:
            hook=lambda:use_reference(modules) if engine=='old_engine' else nullcontext()
            with hook():run(context,config)
            wall=[];serial=[];compact=[];realized=[];sizes=[]
            for _ in range(5):
                with hook():t=time.perf_counter();result=run(context,config);wall.append(time.perf_counter()-t)
                realized.append(result.possessions)
                t=time.perf_counter();payload=json.dumps(to_plain(result),separators=(',',':'));serial.append(time.perf_counter()-t)
                t=time.perf_counter();small=json.dumps(core(result),separators=(',',':'));compact.append(time.perf_counter()-t)
                sizes.append([len(payload.encode()),len(small.encode())]);del result,payload,small
            with hook():profiler,partition=profile_partition(context,config)
            profiler.dump_stats(str(out/f'cost-{label}-{engine}.pstats'))
            with (out/f'cost-{label}-{engine}.txt').open('w') as f:pstats.Stats(profiler,stream=f).sort_stats('cumulative').print_stats(35)
            measurements[engine]={'wall_samples_s':wall,'median_s':statistics.median(wall),'range_s':[min(wall),max(wall)],
                'realized_possessions_per_side':realized,'json_median_s':statistics.median(serial),'core_json_median_s':statistics.median(compact),
                'json_bytes_full_core':sizes[-1],'instrumented_partition':partition}
        rows[label]={'scope':'same input/config/seed17, 16 regulation possessions/side; policy changes can intentionally change action counts/results',
            'measurements':measurements}
    write(out,'bounded-costs.json',rows)
    return rows


def release(out,pilot):
    refs=[];rows=[];gc.collect();tracemalloc.start()
    for k in range(4):
        state,context,config=fixture(pilot,policy=probes.POLICY,start=None,coverage='show_then_recover')
        result=run(context,config,17+k)
        for item in (config,config.offense,config.offense.creation,config.offense.creation.screens,
                     state['profiles'][IDS['white']],state['profiles'][IDS['white']].inputs,result):refs.append(weakref.ref(item))
        del item,state,context,config,result
        current,peak=tracemalloc.get_traced_memory();rows.append({'iteration':k+1,'current_bytes':current,'peak_bytes':peak,'live_roots':sum(r() is not None for r in refs)})
    before=tracemalloc.get_traced_memory()[0];gc.collect();after=tracemalloc.get_traced_memory()[0];tracemalloc.stop()
    assert not any(r() is not None for r in refs)
    data={'samples':rows,'probed_roots':len(refs),'all_released':True,'current_before_diagnostic_gc':before,'current_after_diagnostic_gc':after,
        'production_gc_or_cache_added':False,'scope':'four fresh small corrected-policy calls; not whole-app or long-career stability'}
    write(out,'bounded-release.json',data);return data


def targeted_ranges(out,base,proposed):
    rows=[]
    for label,changes,groups in [
        ('security_low',{'luka':{'S17':76}},('security',)),('security_high',{'luka':{'S17':92}},('security',)),
        ('harper_F03_low',{'harper':{'F03.recognition':65,'F03.execution':68}},('passing',)),
        ('harper_F03_high',{'harper':{'F03.recognition':85,'F03.execution':86}},('passing',)),
        ('harper_F04_low',{'harper':{'F04.recognition':65,'F04.execution':68}},('passing',)),
        ('harper_F04_high',{'harper':{'F04.recognition':85,'F04.execution':88}},('passing',)),
        ('F03_source_overlap',{'luka':{'F03.recognition':88,'F03.execution':85},'harper':{'F03.recognition':85,'F03.execution':86}},('passing',)),
        ('F04_source_overlap',{'luka':{'F04.recognition':84,'F04.execution':80},'harper':{'F04.recognition':85,'F04.execution':88}},('passing',)),
        ('gobert_screen_low',{'gobert':{'S27':75,'S28':75}},('screen',)),
        ('gobert_screen_high',{'gobert':{'S27':92,'S28':92}},('screen',)),
        ('receiving_overlap',{'zubac':{'S14':68},'gobert':{'S14':76}},()),
        ('receiving_opposed',{'zubac':{'S14':86},'gobert':{'S14':50}},()),
    ]:
        p=variant(proposed,changes,name=label)
        row=named.run_scenario({'name':label,'pilot':p,'groups':set(groups),'controls':{}})
        if label.startswith('receiving'):row['named_receiving']=probes.named_receiving(p)
        rows.append(row)
    write(out,'targeted-range-alternatives.json',rows)
    creator_keys={(u['player_id'],u['design_id']) for u in proposed['overrides'] if u['player_id'] in (IDS['luka'],IDS['harper'])}
    receiver_keys={(u['player_id'],u['design_id']) for u in proposed['overrides'] if u['design_id']=='S14'}
    components={label:probes.named_receiving(p) for label,p in [('old_inputs',base),
        ('creator_updates_only',selected_fields(base,proposed,creator_keys,'creator-only attribution')),
        ('receiver_updates_only',selected_fields(base,proposed,receiver_keys,'receiver-only attribution')),
        ('all_proposed_inputs',proposed)]}
    write(out,'typed-delivery-receiving-attribution.json',components)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=BASE/'verified')
    parser.add_argument('--overlay',type=Path);parser.add_argument('--overlay-sha256');args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    modules=reference_modules();base=build_pilot();inputs={'old_inputs':base};overlay_status={'pending':True,'reason':'No explicitly pinned finished overlay supplied'}
    if args.overlay or args.overlay_sha256:
        if not(args.overlay and args.overlay_sha256):parser.error('--overlay and --overlay-sha256 are required together')
        proposed,overlay=apply_overlay(base,args.overlay,args.overlay_sha256);inputs['proposed_inputs']=proposed
        overlay_status={'pending':False,**proposed['overlay_audit']};write(out,'consumed-targeted-overlay.json',overlay)
        write(out,'proposed-effective-completion-layer.json',export_layer(proposed));targeted_ranges(out,base,proposed)
    write(out,'overlay-status.json',overlay_status)
    quadrants={}
    for input_label,pilot in inputs.items():
        for corrected in (False,True):
            engine='corrected_policy' if corrected else 'old_engine';label=engine+'__'+input_label
            policy=probes.POLICY if corrected else 'legacy_timely_v1';resolver=resolve_drive if corrected else modules['nba_gm_data.creation_passing'].resolve_drive
            hook=nullcontext() if corrected else use_reference(modules)
            with hook:
                data={'named_same_47':same_named(pilot,modules,corrected),
                    'help_boundaries':probes.boundary_sweep(pilot,resolver,policy),
                    'path_endpoint_boundaries':probes.path_endpoint_sweep(pilot,resolver,policy),
                    'downstream_contexts':probes.context_sweep(pilot,resolver,policy),
                    'containment_contexts':probes.containment_sweep(pilot,resolver,policy),
                    'named_receiving':probes.named_receiving(pilot)}
            if label=='old_engine__old_inputs':
                retained=json.loads((REFERENCE/'milestone6-action-probes.json').read_text())
                assert json.loads(json.dumps(data['named_same_47']))==retained
            write(out,label+'.json',data);write(out,label+'-sensitivity.json',comparisons(data['named_same_47']))
            quadrants[label]={'named_scenarios':len(data['named_same_47']),'boundary_rows':len(data['help_boundaries']),
                'path_endpoint_rows':len(data['path_endpoint_boundaries']),
                'downstream_contexts':len(data['downstream_contexts']),'containment_contexts':len(data['containment_contexts'])}
            print(label,'complete',flush=True)
    role_controls=[]
    for grade in (50,90):
        p=variant(base,{a:{'S36':grade,'S37':grade} for a in ('white','castle')},name='common synthetic C27 role-control sensitivity')
        role_controls.append({'common_C27_positioning_contest_grade':grade,'origin':'shared uncertain role control, not research evidence',
            'overrides':p['overrides'],'contexts':probes.context_sweep(p,policy=probes.POLICY,n=256)})
    write(out,'help-role-control-sensitivity.json',role_controls)
    historical=parity(out,modules);reuse=retained_reuse(out,base);checks=accounting(out,inputs.get('proposed_inputs',base),modules)
    cost=costs(out,base,modules);memory=release(out,base)
    initial=json.loads((REFERENCE/'hashes.json').read_text());changed=[];missing=[]
    for name,digest in initial.items():
        p=ROOT/name
        if not p.exists():missing.append(name)
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=digest:changed.append(name)
    allowed={'src/nba_gm_data/creation_passing.py','src/nba_gm_data/offense_response.py','src/nba_gm_data/interior_defense.py',
        'src/nba_gm_data/shot_geometry.py','docs/PILOT_RESPONSE_CALIBRATION_ACTIVE_TASK.md'}
    assert not set(changed)-allowed and not missing,(changed,missing)
    files=[ROOT/name for name in allowed]+list((ROOT/'experiments/pilot_response_calibration').glob('*.py'))+[Path(__file__),ROOT/'tests/test_pilot_response_calibration.py']
    write(out,'source-manifest.json',{'initial_files_checked':len(initial),'changed_owned_existing':changed,'unexpected_changes':[],
        'hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
    summary={'default_off':True,'new_policy_explicit_opt_in':probes.POLICY,'previous_default_policy_and_revisions_preserved':True,
        'old_47_scenarios_exactly_reproduced':True,'quadrants':quadrants,'overlay':overlay_status,
        'ordinary_full_result_parity_cases':sum(r['path']=='ordinary_default_off' for r in historical),
        'previous_experimental_full_result_parity_cases':sum(r['path']!='ordinary_default_off' for r in historical),
        'preserved_reuse_full_result_rng_cases':len(reuse),'kernel_accounting_cases':len(checks),'released_roots':memory['probed_roots'],
        'sampling':'512 per actor/context, 4096 fixed pass/security/catch trials, 512 screen phase samples; conditional event uncertainty only',
        'no_player_rankings_nba_forecasts_or_production_activation':True}
    write(out,'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
