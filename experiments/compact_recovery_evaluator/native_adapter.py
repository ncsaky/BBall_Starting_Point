"""Candidate-owned validated batched C geometry with authoritative fallback."""
import ctypes as C
import math
from nba_gm_data import pass_recovery
from nba_gm_data.action_choice import _cdf,_late_interval,G4,G8
from .build_native import LIB

_LIBRARY=None
_LOAD_ERROR=None
NIN=48;NOUT=16


def library():
    global _LIBRARY,_LOAD_ERROR
    if _LIBRARY is not None:return _LIBRARY
    try:
        lib=C.PyDLL(str(LIB));lib.compact_geometry_abi.restype=C.c_int
        if lib.compact_geometry_abi()!=1:raise ValueError('Unsupported compact geometry ABI')
        f=lib.compact_geometry_batch;f.argtypes=[C.POINTER(C.c_double),C.c_size_t,C.c_double,C.c_double,C.POINTER(C.c_double),C.POINTER(C.c_int32),C.c_size_t,C.POINTER(C.c_double),C.c_size_t];f.restype=C.c_int
        _LIBRARY=lib;return lib
    except (OSError,ValueError,AttributeError) as exc:_LOAD_ERROR=str(exc);return None


class GeometryBatch:
    def __init__(self,frame,name,option,order):
        self.frame=frame;self.name=name;self.option=option;self.counts={'native_geometry_nodes':0,'python_geometry_repairs':0,'native_batches':0};self.ready=False;self.reason=None
        b=frame.get('_recovery_geometry_basis') or pass_recovery.geometry_basis(frame,name,option);self.basis=b;c=frame['spec'].recovery;state=frame['state'];did=b['did'];receiver=b['receiver'];defender=b['defender'];m=b['m'];d=b['d']
        values=[*receiver,*defender,b['height'],b['vx'],b['vy'],b['standing'],b['jump'],b['half_span'],m.acceleration_m_s2,b['speed'],b['defender_standing'],b['defender_jump'],state['receiving_spans_m'][did]/2*c.horizontal_reach_fraction,d.acceleration_m_s2,b['defender_speed'],b['defender_reaction'],c.reaction_s,c.horizon_s,c.downward_velocity_m_s,c.gravity_m_s2,c.minimum_ball_height_m,b['gather'],c.jump_takeoff_s,c.court_half_width_m,c.court_back_y_m,c.court_front_y_m,c.search_steps,c.search_bisections,*[v for axis in b['axes'] for v in axis]]
        if len(values)!=NIN or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):self.reason='invalid numeric geometry packet';return
        # Bound the prototype's numerical-ambiguity guards/ABI domain. Broader
        # valid Python scenarios keep the authoritative Python calculation.
        if max(abs(v) for v in values)>1e4 or c.horizon_s>10 or c.gravity_m_s2<1 or min(m.acceleration_m_s2,b['speed'],d.acceleration_m_s2,b['defender_speed'])<.01:self.reason='outside compiled numeric prototype domain';return
        lib=library()
        if lib is None:self.reason=_LOAD_ERROR or 'native unavailable';return
        self.inputs=(C.c_double*NIN)(*values);nodes=G4 if order==4 else G8;scale=option['delivery']['error_scale_m'];lo,hi=_late_interval(frame,name,option)
        if not pass_recovery.inside(option['target'],c) or hi<=lo:lo=hi=0.0
        qlo,qhi=_cdf(lo,scale),_cdf(hi,scale);intervals=[(0,qlo),(qhi,1)] if qhi>qlo else [(0,1)];keys=[]
        for direction in range(6):
            maximum=pass_recovery.max_error(frame,name,option,direction);qlimit=_cdf(maximum,scale)
            for left,right in intervals:
                end=min(right,qlimit)
                if end>left:
                    for panel in range(c.integration_panels):
                        a=left+(end-left)*panel/c.integration_panels;bq=left+(end-left)*(panel+1)/c.integration_panels
                        for node,weight in nodes:
                            q=a+(bq-a)*node;keys.append((direction,-math.log1p(-q)*scale))
                if right-max(left,qlimit)>0:keys.append((direction,max(maximum+.001,option['delivery']['window_radius_m']+1)))
        if not keys or len(keys)>404:self.reason='unsupported batch node count';return
        self.keys={key:i for i,key in enumerate(keys)};n=len(keys);self.errors=(C.c_double*n)(*[k[1] for k in keys]);self.directions=(C.c_int32*n)(*[k[0] for k in keys]);self.output=(C.c_double*(n*NOUT))()
        rc=lib.compact_geometry_batch(self.inputs,NIN,option['target'][0],option['target'][1],self.errors,self.directions,n,self.output,n*NOUT)
        if rc:self.reason='native validation rejected packet '+str(rc);return
        self.counts['native_batches']=1;self.ready=True

    def geometry(self,frame,name,option,error,direction):
        if frame['coupled'] is not self.frame['coupled'] or name!=self.name:raise ValueError('Native geometry packet belongs to another snapshot')
        index=self.keys.get((direction,error)) if self.ready else None
        if index is None:return self.repair(frame,name,option,error,direction)
        o=self.output;start=index*NOUT;status=int(o[start])
        if status==5:return self.repair(frame,name,option,error,direction)
        if status not in (0,1,2,3,4):return self.repair(frame,name,option,error,direction)
        self.counts['native_geometry_nodes']+=1
        result={'lost':(None,'pass_out_of_bounds','pass_grounded','pass_unreachable','recovery_defended')[status],'delay_s':o[start+1]}
        def optional(i):v=o[start+i];return None if math.isnan(v) else v
        if optional(2) is not None:result['capture_s']=o[start+2]
        if status!=4 and optional(14) is not None:result['searched_horizon_s']=o[start+14]
        if optional(12) is not None:result['defender_arrival_s']=o[start+12]
        if status==0:result.update(receiver_feet_m=(o[start+3],o[start+4]),defender_position_m=(o[start+5],o[start+6]),ball_at_capture_m=(o[start+7],o[start+8],o[start+9]),receiver_travel_m=o[start+10],horizontal_reach_m=o[start+11],landing_s=o[start+13],gather_s=o[start+15])
        return result

    def repair(self,frame,name,option,error,direction):
        self.counts['python_geometry_repairs']+=1
        return pass_recovery.recovery_geometry(frame,name,option,error,direction)
