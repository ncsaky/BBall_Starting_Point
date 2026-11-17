"""Proof-first interval classifier; no promotion or selected-action hook.

Keep the optimized reference's exact quadrature node/weight order. Refine only
an interval's conservative reach certificate, never infer absent interior
branches from endpoint agreement. Unproven nodes use the original resolver.
"""
from collections import Counter
from contextlib import contextmanager
import math
from unittest.mock import patch
from nba_gm_data import action_choice,creation_passing,pass_recovery
from nba_gm_data.action_choice import _cdf,_late_interval

MODE='certified_interval_recovery_v1'
MAX_DEPTH=2
MAX_CERTIFICATES=128
EXACT_CANDIDATE=action_choice.project_candidate
EXACT_CHOICES=action_choice.project_choices
FULL_RESOLVER=creation_passing.resolve_candidate


class IntervalResolver:
    def __init__(self):
        self.counts=Counter();self.reasons=Counter();self.certificates={};self.roots={};self.max_depth=0

    def fallback(self,reason,*args,**kwargs):
        self.counts['full_resolver_calls']+=1;self.reasons[reason]+=1
        return FULL_RESOLVER(*args,**kwargs)

    def terminal(self,frame,option,error,direction):
        """Same pointwise represented terminal cause/time, without a search."""
        c=frame['spec'].recovery;b=frame['_recovery_geometry_basis'];v=b['axes'][direction]
        point=(option['target'][0]+error*v[0],option['target'][1]+error*v[1]);z0=b['height']+error*v[2]
        if not pass_recovery.inside(point,c):return 'pass_out_of_bounds',.05
        if z0<c.minimum_ball_height_m:return 'pass_grounded',.05
        floor=(c.downward_velocity_m_s+math.sqrt(c.downward_velocity_m_s**2+2*c.gravity_m_s2*(z0-c.minimum_ball_height_m)))/c.gravity_m_s2
        exit_time=float('inf')
        for pos,velocity,low,high in ((point[0],b['vx'],-c.court_half_width_m,c.court_half_width_m),(point[1],b['vy'],c.court_back_y_m,c.court_front_y_m)):
            if velocity>0:exit_time=min(exit_time,(high-pos)/velocity)
            elif velocity<0:exit_time=min(exit_time,(low-pos)/velocity)
        horizon=min(c.horizon_s,floor);horizon=min(horizon,exit_time)
        cause='pass_out_of_bounds' if exit_time<=min(c.horizon_s,floor) else 'pass_grounded' if floor<c.horizon_s else 'pass_unreachable'
        return cause,.05+max(0,horizon)

    def interval(self,frame,name,option,direction,error):
        """Recover the original panel, with explicit membership validation."""
        if direction not in self.roots:
            scale=option['delivery']['error_scale_m'];lo,hi=_late_interval(frame,name,option);c=frame['spec'].recovery
            if not pass_recovery.inside(option['target'],c) or hi<=lo:lo=hi=0.0
            qlo,qhi=_cdf(lo,scale),_cdf(hi,scale);intervals=[(0,qlo),(qhi,1)] if qhi>qlo else [(0,1)]
            limit=_cdf(pass_recovery.max_error(frame,name,option,direction),scale)
            self.roots[direction]=[(left,min(right,limit)) for left,right in intervals if min(right,limit)>left]
        scale=option['delivery']['error_scale_m'];q=_cdf(error,scale);panels=frame['spec'].recovery.integration_panels
        for left,end in self.roots[direction]:
            if not left<=q<=end:continue
            index=min(panels-1,max(0,int((q-left)/(end-left)*panels)))
            a=left+(end-left)*index/panels;b=left+(end-left)*(index+1)/panels
            if b>=1:return None
            elo=-math.log1p(-a)*scale;ehi=-math.log1p(-b)*scale
            if elo<=error<=ehi:return a,b,q
        return None

    def certificate(self,frame,option,direction,left,right):
        key=(direction,left,right)
        if key in self.certificates:return self.certificates[key]
        if self.counts['certificate_checks']>=MAX_CERTIFICATES:
            self.counts['proof_budget_exhaustions']+=1;return None
        self.counts['certificate_checks']+=1
        scale=option['delivery']['error_scale_m']
        if right>=1:return False
        lo=-math.log1p(-left)*scale;hi=-math.log1p(-right)*scale
        if not math.isfinite(lo+hi):return False
        b=frame['_recovery_geometry_basis'];c=frame['spec'].recovery;axis=b['axes'][direction];horizon=c.horizon_s;receiver=b['receiver'];target=option['target']
        x0=target[0]+lo*axis[0];x1=target[0]+hi*axis[0];y0=target[1]+lo*axis[1];y1=target[1]+hi*axis[1]
        xmin=min(x0,x1)+min(0,b['vx']*horizon);xmax=max(x0,x1)+max(0,b['vx']*horizon)
        ymin=min(y0,y1)+min(0,b['vy']*horizon);ymax=max(y0,y1)+max(0,b['vy']*horizon)
        padding=1e-9*max(1,abs(xmin),abs(xmax),abs(ymin),abs(ymax),abs(receiver[0]),abs(receiver[1]))
        dx=max(0,xmin-receiver[0],receiver[0]-xmax);dy=max(0,ymin-receiver[1],receiver[1]-ymax)
        distance=max(0,math.hypot(dx,dy)-b['half_span']-3*padding)
        optimistic=c.reaction_s+creation_passing.motion_time(distance,b['m'].acceleration_m_s2,b['speed'])
        certified=optimistic>horizon+1e-9*max(1,abs(horizon))
        self.certificates[key]=certified;self.counts['certified_intervals' if certified else 'unproven_intervals']+=1
        return certified

    def __call__(self,frame,name,options,draws,record,**kwargs):
        self.counts['reference_node_requests']+=1;args=(frame,name,options,draws,record)
        if frame.get('_legacy_delivery') or kwargs.get('include_details',True) or kwargs.get('delivery_error_override') is None:
            return self.fallback('clean_or_full_details',*args,**kwargs)
        option=options[name];error=kwargs['delivery_error_override'];direction=min(5,int(draws[44]*6));c=frame['spec'].recovery;b=frame['_recovery_geometry_basis']
        # Within-radius nodes can be late, but can also remain accepted clean.
        # Preserve that channel, irrespective of the new directional geometry.
        if error<=option['delivery']['window_radius_m']:
            original=creation_passing.prepare_delivery(frame,name,option,error)
            if original['outcome'] is None and pass_recovery.inside(original['target'],c):return self.fallback('clean_guard',*args,**kwargs)
        axis=b['axes'][direction];point=(option['target'][0]+error*axis[0],option['target'][1]+error*axis[1]);z0=b['height']+error*axis[2]
        immediate=not pass_recovery.inside(point,c) or z0<c.minimum_ball_height_m
        certified=immediate
        if not immediate:
            interval=self.interval(frame,name,option,direction,error)
            if interval is None:return self.fallback('unbounded_or_rounding_interval',*args,**kwargs)
            left,right,q=interval
            for depth in range(MAX_DEPTH+1):
                self.max_depth=max(self.max_depth,depth);proof=self.certificate(frame,option,direction,left,right)
                if proof:certified=True;break
                if proof is None:return self.fallback('proof_budget',*args,**kwargs)
                if depth<MAX_DEPTH:
                    mid=(left+right)/2
                    if q<mid:right=mid
                    else:left=mid
        if not certified:return self.fallback('unresolved_leaf',*args,**kwargs)
        cause,delay=self.terminal(frame,option,error,direction);elapsed=frame['elapsed'];elapsed+=option.get('wait_s',0);elapsed=elapsed+option['delivery']['flight_s']+delay
        if abs(elapsed-frame['remaining_s'])<=1e-8*max(1,abs(frame['remaining_s'])):return self.fallback('clock_boundary',*args,**kwargs)
        self.counts['fast_terminal_nodes']+=1;self.counts['immediate_terminal_nodes' if immediate else 'interval_certified_nodes']+=1
        return {'kind':'turnover','outcome':cause,'record':{'receipt_category':'lost'},'elapsed_s':elapsed}

    def audit(self):return {'mode':MODE,**dict(self.counts),'fallback_reasons':dict(self.reasons),'max_depth':self.max_depth,'limits':{'depth':MAX_DEPTH,'certificate_checks':MAX_CERTIFICATES}}


def candidate(frame,name,options,*,order=4):
    if name=='finish' or not getattr(frame['spec'],'receipt_policy',None):return EXACT_CANDIDATE(frame,name,options,order=order)
    resolver=IntervalResolver()
    with patch.object(creation_passing,'resolve_candidate',resolver):result=EXACT_CANDIDATE(frame,name,options,order=order)
    return {**result,'policy':MODE,'boundary_solver':resolver.audit(),'reference_node_counter_semantics':'retained original quadrature requests; boundary_solver reports actual full resolver calls separately'}


def choices(frame,options,*,order=4):
    if not getattr(frame['spec'],'receipt_policy',None):return EXACT_CHOICES(frame,options,order=order)
    return {**EXACT_CHOICES(frame,options,order=order),'decision_projection':MODE,'choice_rule':'unchanged optimized-reference imperfect recognition/risk/bad-choice rule'}


@contextmanager
def enabled():
    with patch.object(action_choice,'project_candidate',candidate),patch.object(action_choice,'project_choices',choices):yield
