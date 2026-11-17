"""Bounded field mapping and direct node/kernel differential diagnostics."""
import ctypes as C
import math
import struct
from nba_gm_data import pass_recovery
from experiments.boundary_aware_projection.states import states
from .python_core import CompactResolver
from .native_adapter import GeometryBatch,library,NIN,NOUT
from .verification import reference_modules,use_reference


def normalized_response(response):
    if response is None:return None
    result={k:v for k,v in response.items() if k!='_contest_basis'};basis=response.get('_contest_basis')
    if basis is not None:result['_contest_basis']={k:(v.revision if k=='profile' else v) for k,v in vars(basis).items()}
    return result


def packet(action):
    r={'kind':action['kind'],'elapsed_s':action['elapsed_s'],'receipt_category':action['record'].get('receipt_category','clean')}
    if action['kind']=='turnover':r['outcome']=action['outcome']
    else:r['receipt_probability']=action.get('receipt_probability',action.get('plan',{}).get('reception'))
    if action['kind']=='shot':
        p=action['plan'];r['plan']={k:p.get(k) for k in ('player_id','zone','off','reception','preparation_s','contest_defender_id')};r['plan']['response']=normalized_response(p['response'])
        r['plan']['projection_contests']=[normalized_response(v) for v in p.get('_projection_contests',())]
    return r


def direct_pairs(write):
    modules=reference_modules();rows=[];physical=[];fails=[];n=0;field_max=0.;bitdiff=0;native_count=repairs=0
    errors=(0,.1,.3,.5,.7,.9,1.1,1.5,2,3,4,6,10,20,math.nextafter(.9,0),math.nextafter(.9,math.inf))
    for meta,f,options in states('development'):
        if meta['origin']!='prior48' or meta['context']!='reference':continue
        for name in dict.fromkeys((meta['family'],'F06')):
            if name not in options:continue
            o=options[name];f={**f,'_recovery_geometry_basis':pass_recovery.geometry_basis(f,name,o)};compact=CompactResolver();nodes=[(direction,error) for direction in range(6) for error in errors]
            batch=GeometryBatch(f,name,o,4);lib=library()
            if lib is not None and batch.ready:
                size=len(nodes);batch.errors=(C.c_double*size)(*[e for d,e in nodes]);batch.directions=(C.c_int32*size)(*[d for d,e in nodes]);batch.output=(C.c_double*(size*NOUT))();batch.keys={key:i for i,key in enumerate(nodes)}
                rc=lib.compact_geometry_batch(batch.inputs,NIN,o['target'][0],o['target'][1],batch.errors,batch.directions,size,batch.output,size*NOUT);assert rc==0
            for direction,error in nodes:
                draws=[.5]*48;draws[44]=(direction+.5)/6
                a=compact(f,name,options,draws,{},delivery_error_override=error,include_details=False)
                with use_reference(modules):b=modules['nba_gm_data.creation_passing'].resolve_candidate(f,name,options,draws,{},delivery_error_override=error,include_details=False)
                equal=packet(a)==packet(b);n+=1
                rows.append({**{k:meta[k] for k in ('actor','family','context')},'candidate':name,'error_m':error,'direction':direction,'kind':a['kind'],'category':a['record']['receipt_category'],'exact_packet_equal':equal})
                if not equal:fails.append({'case':rows[-1],'compact':packet(a),'detailed':packet(b)})
                ref=pass_recovery.recovery_geometry(f,name,o,error,direction);native=batch.geometry(f,name,o,error,direction);ok=ref['lost']==native['lost'];maxdiff=0.;different=0
                for key in ('delay_s','capture_s','receiver_feet_m','defender_position_m','ball_at_capture_m','receiver_travel_m','horizontal_reach_m','defender_arrival_s','landing_s','gather_s','searched_horizon_s'):
                    x=ref.get(key);y=native.get(key)
                    if x is None or y is None:
                        if x!=y:ok=False
                        continue
                    xs=x if isinstance(x,tuple) else (x,);ys=y if isinstance(y,tuple) else (y,)
                    for vx,vy in zip(xs,ys):
                        delta=abs(vx-vy);maxdiff=max(maxdiff,delta);different+=struct.pack('!d',vx)!=struct.pack('!d',vy)
                field_max=max(field_max,maxdiff);bitdiff+=different;ok=ok and maxdiff<=1e-10
                physical.append({'actor':meta['actor'],'candidate':name,'error_m':error,'direction':direction,'passed':ok,'max_field_difference':maxdiff,'nonbitwise_fields':different})
                if not ok:fails.append({'geometry_case':physical[-1],'python_geometry':ref,'native_geometry':native})
            native_count+=batch.counts['native_geometry_nodes'];repairs+=batch.counts['python_geometry_repairs']
    assert n<=4096
    write('direct-node-pairs.json',rows);write('native-physical-field-pairs.json',physical);write('direct-pair-failures.json',fails)
    write('direct-pair-summary.json',{'python_pairs':n,'python_exact_equal':sum(r['exact_packet_equal'] for r in rows),'native_physical_pairs':len(physical),'max_native_field_difference':field_max,'native_nonbitwise_field_comparisons':bitdiff,'native_nodes_executed':native_count,'python_geometry_repairs':repairs,'failures':len(fails),'scope':'authoritative packet mapping, scalar geometry fields; native repairs counted, never normalize away nonbitwise values'})
    assert not fails
