"""Bounded M16 qualification; no process-global runtime backend dispatch."""
from collections import Counter
from dataclasses import replace
import csv
import gc
import hashlib
import json
import math
import statistics
import struct
import subprocess
import sys
import time
import tracemalloc
import weakref
from unittest.mock import patch
from nba_gm_data import action_choice,creation_passing,pass_recovery,sim
from nba_gm_data.schema import to_plain
from nba_gm_data.compact_recovery import CompactResolver
from nba_gm_data.shot_geometry import ShotGeometry,stable_bearing,geometry_response
from nba_gm_data.interior_defense import ArrivalContext
from experiments.boundary_aware_projection.states import states
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.pass_recovery import sampling
from experiments.compact_recovery_evaluator.diagnostics import packet
from .fixtures import fixture,pool,converted,IDS
from .providers import ArithmeticProvider,StableProvider
from .native_adapter import GeometryBatch,library,NIN,NOUT
from .verification import BASE,OUT,ROOT,REFERENCE,reference_modules,reference_config

MODES={
 'legacy_compact':('legacy_bearing_v1',None),
 'legacy_arithmetic_native':('legacy_bearing_v1',ArithmeticProvider()),
 'stable_compact':('stable_route_bearing_v2',None),
 'stable_native':('stable_route_bearing_v2',StableProvider()),
}

def write(name,data):(OUT/name).write_text(json.dumps(to_plain(data),indent=2,allow_nan=False)+'\n')
def read(name):return json.loads((OUT/name).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def compare(a,b,limit):
    ep=branch=0.;missing=[]
    for k,v in a['candidates'].items():
        w=b['candidates'][k];ep=max(ep,abs(v['expected_points']-w['expected_points']));ab=v.get('branches',{});bb=w.get('branches',{})
        branch=max(branch,max((abs(ab.get(t,0)-bb.get(t,0)) for t in set(ab)|set(bb)),default=0.))
        missing.extend((k,t,p) for t,p in ab.items() if p>=.005 and not bb.get(t,0))
    differences=[abs(v-b['effective_choice_probabilities'].get(k,0)) for k,v in a['effective_choice_probabilities'].items()];choice=max(differences);tv=sum(differences)/2
    normalized=all(abs(sum(v['branches'].values())-1)<=1e-12 for v in b['candidates'].values() if 'branches' in v)
    return {'max_EP_error':ep,'max_branch_error':branch,'max_effective_choice_error':choice,'choice_TV':tv,'material_omissions':missing,'normalized':normalized,'strict_passed':max(ep,branch,choice,tv)<=limit and not missing and normalized}


def predictions(group):
    if group=='held_out':check_seal()
    rows=[];deltas=[]
    for meta,f,o in states(group):
        refs={p:action_choice.project_choices(converted(f,'detailed_python_v1',bearing=p),o) for p in ('legacy_bearing_v1','stable_route_bearing_v2')}
        for mode,(p,provider) in MODES.items():
            result=action_choice.project_choices(converted(f,bearing=p,provider=provider),o);c=compare(refs[p],result,0 if provider is None else 1e-9)
            rows.append({**meta,'mode':mode,**c,'reference':refs[p],'method':result})
        delta=compare(refs['legacy_bearing_v1'],refs['stable_route_bearing_v2'],0)
        deltas.append({**meta,**delta,'meaning':'Deliberate shared model change; not computational error'})
    write('predictions-'+group+'.json',rows);write('model-differences-'+group+'.json',deltas)
    print(group,{m:{'passed':sum(r['strict_passed'] for r in rows if r['mode']==m),'max_EP_error':max(r['max_EP_error'] for r in rows if r['mode']==m)} for m in MODES},flush=True)
    if group=='held_out':acceptance()


def acceptance():
    rows=read('predictions-development.json')+read('predictions-held_out.json');summary={}
    for mode in MODES:
        selected=[r for r in rows if r['mode']==mode];exercised=mode.endswith('compact') or any((c.get('compact_evaluator',{}).get('native_geometry') or {}).get('native_geometry_nodes',0) for r in selected for c in r['method']['candidates'].values())
        summary[mode]={'states':len(selected),'passed_states':sum(r['strict_passed'] for r in selected),'passed':all(r['strict_passed'] for r in selected) and exercised,'native_exercised':exercised,**{k:max(r[k] for r in selected) for k in ('max_EP_error','max_branch_error','max_effective_choice_error','choice_TV')},'failures':[{k:v for k,v in r.items() if k not in ('reference','method')} for r in selected if not r['strict_passed']]}
    assert summary['legacy_compact']['passed'] and summary['stable_compact']['passed']
    for mode,policy in [('legacy_arithmetic_native','legacy_bearing_v1'),('stable_native','stable_route_bearing_v2')]:
        summary[mode]['direct_mapped_passed']=read('mapped-native-summary.json')[policy]['passed'];summary[mode]['passed']=summary[mode]['passed'] and summary[mode]['direct_mapped_passed']
    write('numerical-acceptance.json',summary)
    table=[{k:v for k,v in r.items() if k not in ('reference','method')} for r in rows];write('strict-error-table.json',table)
    with (OUT/'strict-error-table.csv').open('w',newline='') as f:
        keys=['actor','family','context','group','origin','mode','max_EP_error','max_branch_error','max_effective_choice_error','choice_TV','strict_passed'];w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(table)


def geometries():
    p=pool();s,c,x=fixture(p);d=creation_passing.prepare_drive_decision(s,IDS['curry'],'response_a','response_b',observed_draws(),24);profile=d['frame']['anchor'].profile;rows=[]
    for center in ((0.,0.),(4.,7.),(-5.,3.)):
        for radius in (0.,-0.,1e-16,1e-14,1e-7,1e-4):
            for angle in range(0,360,60):
                theta=math.radians(angle);cx,cy=center;shot=ShotGeometry(cx,cy,300,cx+radius*math.cos(theta),cy+radius*math.sin(theta),angle)
                for origin in (center,(cx,cy+2)):
                    direction,b=stable_bearing(shot,origin);r=geometry_response(profile,ArrivalContext(),'rim',shot,defender_route_origin_m=origin,bearing_policy='stable_route_bearing_v2')
                    if b['current_separation_m']>b['tolerance_m']:assert b['source']=='current_separation'
                    elif b['route_separation_m']>b['tolerance_m']:assert b['source']=='last_route_segment'
                    else:assert direction is None and r['contest_alignment']==.35+.65/math.pi
                    rows.append({'center':center,'radius':radius,'angle':angle,'route_origin':origin,'direction':direction,'bearing':b,'contest_alignment':r['contest_alignment']})
    assert len(rows)<=256;write('geometric-degeneracies.json',rows)


def direct():
    import ctypes as C
    rows=[];physical=[];summary={};errors=(0.,.1,.3,.5,.7,.9,1.1,1.5,2.,3.,4.,6.,10.,20.,math.nextafter(.9,0),math.nextafter(.9,math.inf))
    selected=[r for r in states('development') if r[0]['origin']=='prior48' and r[0]['context']=='reference']
    for policy in ('legacy_bearing_v1','stable_route_bearing_v2'):
        count=0;fail=0;maximum=0.;physicalmax=0.;nonbitwise=0;native=repairs=0
        for meta,base,options in selected:
            for name in dict.fromkeys((meta['family'],'F06')):
                if name not in options or name=='finish':continue
                f=converted(base,bearing=policy);o=options[name];f={**f,'_recovery_geometry_basis':pass_recovery.geometry_basis(f,name,o)};resolver=CompactResolver();batch=GeometryBatch(f,name,o,4);nodes=[(di,e) for di in range(6) for e in errors]
                if batch.ready:
                    size=len(nodes);batch.errors=(C.c_double*size)(*[e for di,e in nodes]);batch.directions=(C.c_int32*size)(*[di for di,e in nodes]);batch.output=(C.c_double*(size*NOUT))();batch.keys={key:i for i,key in enumerate(nodes)}
                    assert library().compact_geometry_batch(batch.inputs,NIN,o['target'][0],o['target'][1],batch.errors,batch.directions,size,batch.output,size*NOUT)==0
                for di,e in nodes:
                    draws=observed_draws();draws[44]=(di+.5)/6
                    a=resolver(f,name,options,draws,{},delivery_error_override=e,include_details=False);b=creation_passing.resolve_candidate(f,name,options,draws,{},delivery_error_override=e,include_details=False)
                    equal=packet(a)==packet(b);fail+=not equal;count+=1;rows.append({**meta,'policy':policy,'candidate':name,'direction':di,'error_m':e,'exact_packet_equal':equal,'kind':a['kind'],'category':a['record']['receipt_category']})
                    ref=pass_recovery.recovery_geometry(f,name,o,e,di);g=batch.geometry(f,name,o,e,di);delta=0.;bits=0;status=ref['lost']==g['lost']
                    for key in ('delay_s','capture_s','receiver_feet_m','defender_position_m','ball_at_capture_m','receiver_travel_m','horizontal_reach_m','defender_arrival_s','landing_s','gather_s','searched_horizon_s'):
                        x=ref.get(key);y=g.get(key)
                        if x is None or y is None:status=status and x==y;continue
                        for vx,vy in zip(x if isinstance(x,tuple) else (x,),y if isinstance(y,tuple) else (y,)):
                            delta=max(delta,abs(vx-vy));bits+=struct.pack('!d',vx)!=struct.pack('!d',vy)
                    physicalmax=max(physicalmax,delta);nonbitwise+=bits;physical.append({'policy':policy,'actor':meta['actor'],'candidate':name,'error_m':e,'direction':di,'max_field_difference':delta,'nonbitwise_fields':bits,'passed':status and delta<=1e-10})
                native+=batch.counts['native_geometry_nodes'];repairs+=batch.counts['python_geometry_repairs']
        assert count<=2048 and fail==0
        summary[policy]={'pairs':count,'python_exact':count-fail,'native_max_physical_field_error':physicalmax,'nonbitwise_fields':nonbitwise,'native_nodes':native,'python_geometry_repairs':repairs,'physical_passed':all(r['passed'] for r in physical if r['policy']==policy)}
    write('direct-node-pairs.json',rows);write('native-physical-field-pairs.json',physical);write('direct-pair-summary.json',summary)


def mapped_native():
    import ctypes as C
    rows=[];summary={}
    errors=(0.,.1,.3,.5,.7,.9,1.1,1.5,2.,3.,4.,6.,10.,20.,math.nextafter(.9,0),math.nextafter(.9,math.inf))
    def difference(a,b):
        if isinstance(a,dict) and isinstance(b,dict):
            if a.keys()!=b.keys():return math.inf
            return max((difference(a[k],b[k]) for k in a),default=0.)
        if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
            return max((difference(x,y) for x,y in zip(a,b)),default=0.) if len(a)==len(b) else math.inf
        if isinstance(a,(int,float)) and isinstance(b,(int,float)):return abs(a-b)
        return 0. if a==b else math.inf
    selected=[r for r in states('development') if r[0]['origin']=='prior48' and r[0]['context']=='reference']
    for policy,provider in [('legacy_bearing_v1',ArithmeticProvider()),('stable_route_bearing_v2',StableProvider())]:
        for meta,base,options in selected:
            name=meta['family'];o=options[name];f=converted(base,bearing=policy);f={**f,'_recovery_geometry_basis':pass_recovery.geometry_basis(f,name,o)};batch=provider(f,name,o,4);nodes=[(di,e) for di in range(6) for e in errors]
            if batch.ready:
                size=len(nodes);batch.errors=(C.c_double*size)(*[e for di,e in nodes]);batch.directions=(C.c_int32*size)(*[di for di,e in nodes]);batch.output=(C.c_double*(size*NOUT))();batch.keys={key:i for i,key in enumerate(nodes)}
                assert library().compact_geometry_batch(batch.inputs,NIN,o['target'][0],o['target'][1],batch.errors,batch.directions,size,batch.output,size*NOUT)==0
            class DirectProvider:
                revision=provider.revision
                def __call__(self,*args):return batch
                def repair_reason(self,frame,action):return provider.repair_reason(frame,action) if hasattr(provider,'repair_reason') else None
            resolver=CompactResolver(DirectProvider())
            for di,e in nodes:
                draws=observed_draws();draws[44]=(di+.5)/6
                a=resolver(f,name,options,draws,{},delivery_error_override=e,include_details=False);b=creation_passing.resolve_candidate(f,name,options,draws,{},delivery_error_override=e,include_details=False);delta=difference(packet(a),packet(b))
                rows.append({**meta,'policy':policy,'candidate':name,'error_m':e,'direction':di,'max_mapped_field_error':delta if math.isfinite(delta) else None,'structural_equal':math.isfinite(delta),'passed':delta<=1e-10})
        selectedrows=[r for r in rows if r['policy']==policy];summary[policy]={'pairs':len(selectedrows),'total_with_python_direct_pairs':len(selectedrows)+read('direct-pair-summary.json')[policy]['pairs'],'passed':all(r['passed'] for r in selectedrows),'max_mapped_field_error':max(r['max_mapped_field_error'] or 0 for r in selectedrows)}
        assert summary[policy]['total_with_python_direct_pairs']<=2048
    write('mapped-native-node-pairs.json',rows);write('mapped-native-summary.json',summary)


def seal():
    assert not (OUT/'method-seal.json').exists();assert all(r['strict_passed'] for r in read('predictions-development.json'));assert all(v['physical_passed'] for v in read('direct-pair-summary.json').values())
    files=[p for root in ('src/nba_gm_data','experiments/compact_baseline_native_repair') for p in (ROOT/root).rglob('*') if p.suffix in ('.py','.c')]+[ROOT/'tests/test_compact_baseline_native_repair.py',ROOT/'scripts/run_compact_baseline_native_repair.py']
    write('method-seal.json',{'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},'prespecification_sha256':sha(OUT/'prespecification.json'),'held_out_not_evaluated_yet':True,'scope':'Shared bearing, scoped adapters, native guard and harness frozen before corrected held-out qualification'})


def check_seal():
    pin=read('method-seal.json');assert all(sha(ROOT/f)==h for f,h in pin['source_sha256'].items());assert sha(OUT/'prespecification.json')==pin['prespecification_sha256']


def high_order():
    check_seal();selected={('towns','F03','clock_boundary'),('towns','pop','defender_close'),('turner','F04','defender_close'),('holmgren','F04','clock_boundary')};rows=[]
    for group in ('development','held_out'):
        for meta,f,o in states(group):
            if (meta['actor'],meta['family'],meta['context']) not in selected:continue
            f=converted(f,'detailed_python_v1',bearing='stable_route_bearing_v2');base=action_choice.project_choices(f,o);hi={**f,'spec':replace(f['spec'],recovery=replace(f['spec'].recovery,integration_panels=8))};ref=action_choice.project_choices(hi,o,order=8);compact=action_choice.project_choices(converted(hi,bearing='stable_route_bearing_v2'),o,order=8);assert compare(ref,compact,0)['strict_passed']
            rows.append({**meta,'G4_panels4':base,'G8_panels8':ref,'compact_G8_exact':True,'grid_difference':compare(base,ref,0),'scope':'Quadrature sensitivity remains; neither grid is measured basketball truth/convergence proof'})
    assert len(rows)==4;write('higher-resolution-offline.json',rows)


def parity():
    import scripts.run_recovery_projection_cost as old
    with patch.object(old,'OUT',OUT),patch.object(old,'reference_modules',reference_modules),patch.object(old,'reference_config',reference_config):old.parity()


def mixed():
    check_seal();assert not (OUT/'mixed-started.json').exists();write('mixed-started.json',read('prespecification.json')['natural']);gate=read('numerical-acceptance.json');p=pool();n=events=0;active=0.;rows=[]
    versions=[('legacy_detailed','detailed_python_v1','legacy_bearing_v1',None),('legacy_compact','compact_python_v1','legacy_bearing_v1',None),('stable_detailed','detailed_python_v1','stable_route_bearing_v2',None),('stable_compact','compact_python_v1','stable_route_bearing_v2',None)]
    for key in ('legacy_arithmetic_native','stable_native'):
        if gate[key]['passed']:policy,provider=MODES[key];versions.append((key,'compact_python_v1',policy,provider))
    checked=('n','events','choices','stages','planned_receipts','secured_receipts','receipt_event_breakdown','receipt_by_choice','points','event_attempts','maximum_attempts','truncated','per_seed')
    for actor in ('turner','towns','holmgren','jokic'):
        for context,kw in [('show',{}),('stay',{'coverage':'stay'}),('3s',{'clock':3})]:
            result={}
            for label,backend,policy,provider in versions:
                assert n+16<=1536 and events<6144 and active<60
                s,c,x=fixture(p,actor,backend=backend,bearing=policy,provider=provider,**kw);start=time.perf_counter();r=sampling.run(s,per_seed=8,seeds=(17,29),max_events=6144-events,deadline=start+60-active);active+=time.perf_counter()-start;n+=r['n'];events+=r['event_attempts'];result[label]=r
            equal={label:all(r[k]==result['stable_detailed' if label.startswith('stable') else 'legacy_detailed'][k] for k in checked) for label,r in result.items()};assert all(equal.values()),(actor,context,equal)
            rows.append({'actor':actor,'context':context,'versions':result,'same_model_physical_summaries_equal':equal,'deliberate_model_point_differences':[b-a for a,b in zip(result['legacy_detailed']['points'],result['stable_detailed']['points'])]});write('mixed-results.json',rows)
    write('mixed-budget-final.json',{'n':n,'events':events,'active_s':active,'caps':{'n':1536,'events':6144,'active_s':60},'optional_followup_used':0,'variants':[v[0] for v in versions],'all_same_model_summaries_equal':True,'scope':'Paired supplied contexts with actual resets/creator transfers/rebounds; fixedseed implementation checks, not independent calibration'})


def measure(fn,label):
    import scripts.run_pass_recovery as prior
    t=time.perf_counter();fn();cold=(time.perf_counter()-t)*1000
    with patch.object(prior,'OUT',OUT):r=prior.measure(fn,label)
    return {**r,'first_call_ms':cold,'scope':'Fresh scoped packets on every forecast; packing, repair/discarded attempts and full diagnostics included; serialization separate'}


def cost_versions():
    return [('legacy_detailed','detailed_python_v1','legacy_bearing_v1',None),('legacy_compact','compact_python_v1','legacy_bearing_v1',None),('legacy_arithmetic_native','compact_python_v1','legacy_bearing_v1',ArithmeticProvider()),('stable_detailed','detailed_python_v1','stable_route_bearing_v2',None),('stable_compact','compact_python_v1','stable_route_bearing_v2',None),('stable_native','compact_python_v1','stable_route_bearing_v2',StableProvider())]


def costs():
    check_seal();p=pool();rows=[]
    for actor in ('turner','jokic'):
        versions={};s,_,_=fixture(p,actor,enabled=False);versions['hard_window']=measure(lambda:sampling.run(s,per_seed=16,seeds=(17,)),actor+'-hard')
        for label,backend,policy,provider in cost_versions():
            t=time.perf_counter();s,c,x=fixture(p,actor,backend=backend,bearing=policy,provider=provider);prep=1000*(time.perf_counter()-t);versions[label]={**measure(lambda:sampling.run(s,per_seed=16,seeds=(17,)),actor+'-'+label),'preparation_ms':prep}
        rows.append({'fixture':actor+'16','versions':versions});write('costs.json',rows)
    allstates=list(states('development'))+list(states('held_out'));boundary=[r for r in allstates if r[0]['origin']=='prior48' and r[0]['family']=='pop' and r[0]['context']!='reference'];fallback=[r for r in allstates if r[0]['origin']=='prior48' and r[0]['family'] in ('F03','F04') and r[0]['context'] in ('clock_boundary','defender_close')][:12];held=[r for r in allstates if r[0]['origin']=='prior48' and r[0]['context']=='reference']
    for name,items in [('boundary12',boundary),('fallback12',fallback),('held24',held)]:
        versions={}
        for label,backend,policy,provider in cost_versions():
            frames=[(meta,converted(f,backend,bearing=policy,provider=provider),o) for meta,f,o in items]
            def run():
                if name!='held24':return [action_choice.project_choices(f,o) for _,f,o in frames]
                result=[]
                for meta,f,o in frames:
                    for error in (.1,.9):
                        draws=observed_draws();draws[44]=.25;result.append(creation_passing.resolve_candidate(f,meta['family'],o,draws,{},delivery_error_override=error))
                return result
            versions[label]=measure(run,name+'-'+label)
        if name=='held24':
            for prefix in ('legacy','stable'):assert len({v['result_sha256'] for k,v in versions.items() if k.startswith(prefix)})==1
        rows.append({'fixture':name,'versions':versions});write('costs.json',rows)
    from experiments.expanded_cohort_performance.checks import benchmarks
    for name,c,x in benchmarks():
        r=measure(lambda:sim.sim_game_with_context(c,c['schedule'][0]['externalGameId'],seed=17,interior_experiment=x),name+'-ordinary');rows.append({'fixture':name,'versions':{'unaffected':r}});write('costs.json',rows)
    goals=[]
    for r in rows[:2]:
        v=r['versions']
        for mode in MODES:
            ref='stable_detailed' if mode.startswith('stable') else 'legacy_detailed';speed=v[ref]['median_ms']/v[mode]['median_ms'];hard=v[mode]['median_ms']/v['hard_window']['median_ms'];goals.append({'fixture':r['fixture'],'mode':mode,'speedup_vs_detailed':speed,'cost_vs_hard':hard,'speedup_vs_compact':v['stable_compact' if mode.startswith('stable') else 'legacy_compact']['median_ms']/v[mode]['median_ms'],'passed':speed>=2.5 and hard<=4})
    write('performance-gates.json',goals)


def memory():
    check_seal();p=pool();s,c,x=fixture(p,action='pop');d=creation_passing.prepare_drive_decision(s,IDS['curry'],'response_a','response_b',observed_draws(),24);rows=[]
    for label,backend,policy,provider in cost_versions():
        f=converted(d['frame'],backend,bearing=policy,provider=provider);action_choice.project_choices(f,d['options']);gc.collect();tracemalloc.start();live=[]
        for _ in range(4):r=action_choice.project_choices(f,d['options']);del r;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
        final,peak=tracemalloc.get_traced_memory();tracemalloc.stop();rows.append({'mode':label,'cycle_live_bytes':live,'retained_bytes':final,'peak_bytes':peak})
    del p,s,c,x,d,f;refs=[];live=[];gc.collect();tracemalloc.start()
    for _ in range(4):
        p=pool();s,c,x=fixture(p,bearing='stable_route_bearing_v2',provider=StableProvider());r=sampling.run(s,per_seed=2,seeds=(17,));refs.extend(weakref.ref(v) for v in (x,x.offense.creation,*p['views'].values()));del p,s,c,x,r;gc.collect();live.append(tracemalloc.get_traced_memory()[0])
    final,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert all(r() is None for r in refs);write('memory-release.json',{'local':rows,'cycles':4,'roots':len(refs),'released_roots':sum(r() is None for r in refs),'cycle_live_bytes':live,'retained_bytes':final,'peak_bytes':peak,'scope':'Static native code handle retained, no owned input/result graph after candidate; no runtime GC changes'})


def tests():
    import scripts.run_compact_recovery_evaluator as old
    with patch.object(old,'OUT',OUT):old.tests()
    (OUT/'baseline349-tests.txt').write_bytes((OUT/'tests.txt').read_bytes())
    with (OUT/'new-tests.txt').open('w') as f:r=subprocess.run([sys.executable,'-m','unittest','test_compact_baseline_native_repair','-q'],stdout=f,stderr=subprocess.STDOUT)
    assert r.returncode==0


def adapter():
    import scripts.run_compact_recovery_evaluator as old
    import experiments.compact_recovery_evaluator.native_adapter as oldadapter
    import experiments.compact_recovery_evaluator.build_native as oldbuild
    from . import native_adapter,build_native
    with patch.object(old,'OUT',OUT),patch.object(old,'fixture',fixture),patch.object(oldadapter,'library',native_adapter.library),patch.object(oldadapter,'GeometryBatch',GeometryBatch),patch.object(oldbuild,'LIB',build_native.LIB):old.adapter_costs()


def finalize():
    check_seal();initial=json.loads((REFERENCE/'hashes.json').read_text());pins=read_reference_pins();changed=[f for f,h in initial.items() if sha(ROOT/f)!=h]
    for file,h in pins.items():assert sha(ROOT/file)==h
    write('integrity-audit.json',{'preedit_files':len(initial),'changed_preedit_files':changed,'unchanged_preedit_files':len(initial)-len(changed),'input_result_binary_pins':len(pins),'pins_unchanged':True,'source_seal_unchanged':True,'git_status':'Independent SHA256; existing host Xcode license issue not modified','supported_rating_changes':0,'new_dimensions':0})
    paths=[p for root in ('src/nba_gm_data','experiments/compact_baseline_native_repair') for p in (ROOT/root).rglob('*') if p.suffix in ('.py','.c')]+[ROOT/'scripts/run_compact_baseline_native_repair.py',ROOT/'tests/test_compact_baseline_native_repair.py',ROOT/'experiments/pass_recovery/fixtures.py']
    write('source-hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in paths})
    write('summary.json',{'milestone':16,'compact_baseline':'Accepted: scoped opt-in recovery default, exact within each model; detailed and selected diagnostics retained','normal_gameplay_activation':False,'bearing_revision':'stable_route_bearing_v2 explicit opt-in; legacy remains default','numerical_acceptance':read('numerical-acceptance.json'),'performance':read('performance-gates.json'),'baseline_tests':349,'new_tests':18,'untouched_result_rng_comparisons':len(read('full-result-rng-parity.json')),'mixed_budget':read('mixed-budget-final.json'),'direct_pairs':read('direct-pair-summary.json'),'supported_rating_changes':0,'new_dimensions':0,'stop':'Bounded pass complete; coordinator review; no perimeter-defense implementation'})


def read_reference_pins():
    p=json.loads((REFERENCE/'input-pins.json').read_text());return p
