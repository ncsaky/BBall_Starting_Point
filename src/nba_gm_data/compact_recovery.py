"""Compact projection-only candidate adapter; selected actions stay detailed.

Field correspondence:
kind/outcome/category <- authoritative delivery; elapsed <- original ordered
clock additions; receipt_probability <- one existing control gate; plan <-
scalar execution/contest formulas, without event/pass/action/detail objects.
"""
from collections import Counter
from dataclasses import replace
import math
from . import creation_passing,pass_recovery
from .interior_defense import ArrivalContext
from .screen_navigation import coverage_position
from .shot_geometry import vertical_access
from .recovery_numeric_plan import Planner

MODE='compact_python_v1'


class CompactResolver:
    def __init__(self,geometry_provider=None,order=4):self.counts=Counter();self.owner=None;self.provider=geometry_provider;self.order=order;self.native=None

    def pack(self,f,name,o,draws):
        self.owner=f['coupled'];self.name=name;self.pid=o['receiver_id'];self.planner=Planner(self.owner,self.pid,name,draws,getattr(f['spec'],'bearing_policy','legacy_bearing_v1'))
        self.state=f['state'];self.c=f['c'];self.helper=f['helper'];self.anchor=f['anchor'];self.anchor_id=f['anchor_id'];self.opponent=f['opponent_id']
        self.defender=f['profiles'][self.state['setups'][self.pid].defender_id];self.defspeed=min(self.defender.speed_m_s,self.defender.lateral_m_s)
        self.delay2=self.c.recovery_delay_s*(2-self.defender.skill('S40'));self.delay1=self.c.recovery_delay_s*(1-self.defender.skill('S40'))
        self.pressure=.20+.65*self.defender.skill('S40');self.is_helper=self.helper is not None and self.defender.player_id==self.helper.player_id
        self.base_helper=f['helper_position'];wait=o.get('wait_s',0)
        if wait and self.helper and f['helped']['committed']:
            self.base_helper=creation_passing._point_on_path(f['start'],f['ball'],f['elapsed']+wait,f['helped']['recognition_delay_s'],self.helper,route_extra_m=.6*(1-self.helper.skill('S39')))
        context=self.state['contexts'][self.opponent]
        if self.anchor:
            available=context.anchor_available if self.anchor_id==f['setup'].defender_id or (self.helper and f['helped']['committed']) else 0.0
            context=replace(context,anchor_available=available,poa_containment=0,recognition_delay_s=0)
        self.context=context
        self.uncommitted_receiver=self.helper and not f['helped']['committed'] and dict(self.owner['spec'].anchor_assignments).get(self.opponent)==self.pid
        self.primary=self.state['screens']['interior_profiles'][self.defender.player_id] if f['screen'] and name in ('F03','F04') else None
        self.primary_context=ArrivalContext(anchor_available=1,spacing=0,poa_containment=0,recognition_delay_s=0) if self.primary else None
        self.counts['candidate_packs']+=1
        if self.provider is not None:
            self.native=self.provider(f,name,o,self.order)
            self.native.last_was_reference=True

    def __call__(self,f,name,options,draws,record,**kwargs):
        if self.native is not None:self.native.last_was_reference=True
        action=self._evaluate(f,name,options,draws,record,**kwargs)
        guard=getattr(self.provider,'repair_reason',None)
        if guard and self.native is not None and not self.native.last_was_reference:
            reason=guard(f,action)
            if reason:
                self.counts['conditioned_node_repairs']+=1;self.counts['repair_reason:'+reason]+=1
                if not hasattr(self,'reference_resolver'):self.reference_resolver=CompactResolver(None,self.order)
                action=self.reference_resolver(f,name,options,draws,record,**kwargs)
        return action

    def _evaluate(self,f,name,options,draws,record,**kwargs):
        if kwargs.get('include_details',True) or kwargs.get('delivery_error_override') is None or name=='finish':
            self.counts['detailed_fallback_calls']+=1;return creation_passing.resolve_candidate(f,name,options,draws,record,**kwargs)
        self.counts['logical_node_requests']+=1;o=options[name]
        if self.owner is None:self.pack(f,name,o,draws)
        elif f['coupled'] is not self.owner or name!=self.name:raise ValueError('Compact numeric packet belongs to another candidate snapshot')
        error=kwargs['delivery_error_override'];legacy=f.get('_legacy_delivery',False)
        if legacy:d=creation_passing.prepare_delivery(f,name,o,error)
        elif self.native is None:d=pass_recovery.delivery(f,name,o,error,min(5,int(draws[44]*6)))
        else:
            original=creation_passing.prepare_delivery(f,name,o,error)
            if original['outcome'] is None and pass_recovery.inside(original['target'],f['spec'].recovery):
                original['extra'].update(receipt_category='clean',receipt_policy=pass_recovery.POLICY,delivery_plan_complete=True,actual_receipt_secured=None);d=original
            else:
                geometry=self.native.geometry(f,name,o,error,min(5,int(draws[44]*6)))
                d=pass_recovery.delivery_from_geometry(f,name,o,error,original,geometry)
        category='clean' if legacy else d['extra']['receipt_category'];flight=d['flight_s'];delay=d['catch_delay_s'];elapsed=f['elapsed'];elapsed+=o.get('wait_s',0)
        result_record={'receipt_category':category}
        if d['outcome']:
            self.counts['loss_nodes']+=1;time=elapsed+flight if d['outcome']=='inaccurate_delivery' else elapsed+flight+delay
            return {'kind':'turnover','outcome':d['outcome'],'elapsed_s':time,'record':result_record}
        if d.get('recovery_reset'):
            self.counts['reset_nodes']+=1
            return {'kind':'reset','elapsed_s':elapsed+flight+delay+f['spec'].reset_cost_s,'record':result_record,'receipt_probability':.5*(.5+.5*self.planner.p.skill(14))}
        recovered=category=='recovered';target=d['target'];zone=d.get('zone_override','perimeter' if name in ('F06','pop') else 'rim')
        kind=d.get('finish_override','lob' if name=='F04' else 'dunk' if name=='F03' else None)
        helper_position=self.base_helper
        stable=self.planner.bearing_policy=='stable_route_bearing_v2'
        helper_origin=f['start'] if self.helper else None;primary_origin=None
        if self.uncommitted_receiver:helper_position=creation_passing._point_on_path(f['start'],target,elapsed,0,self.helper)
        if recovered:
            defender_position=d['extra']['recovery_geometry']['defender_position_m']
            primary_origin=(f.get('_recovery_geometry_basis') or pass_recovery.geometry_basis(f,name,o))['defender']
            primary_arrival=self.delay2+creation_passing.motion_time(math.dist(defender_position,target),self.defender.acceleration_m_s2,self.defspeed)
            if self.helper and f['helped']['committed']:
                helper_origin=helper_position
                helper_position=creation_passing._point_on_path(helper_position,target,flight+delay,self.c.recovery_delay_s,self.helper)
        else:
            defender_position=o['coverage_position']
            if f['screen'] and name in ('F03','F04','pop'):
                if self.is_helper and f['helped']['committed']:defender_position=creation_passing._point_on_path(helper_position,target,flight+delay,self.c.recovery_delay_s,self.defender)
                else:defender_position=coverage_position(f['screen'],elapsed+flight+delay,self.state['screens']['profiles'][self.defender.player_id])
                primary_origin=helper_position if self.is_helper and f['helped']['committed'] else tuple(f['screen']['coverage_release_position'])
                primary_arrival=self.delay2+creation_passing.motion_time(math.dist(defender_position,target),self.defender.acceleration_m_s2,self.defspeed)
            else:
                recovery=self.delay2+creation_passing.motion_time(math.hypot(defender_position[0]-target[0],defender_position[1]-target[1]),self.defender.acceleration_m_s2,self.defspeed)
                primary_arrival=max(0,recovery-flight-delay)
        interior_arrival=None
        if self.anchor:
            if self.anchor_id==f['setup'].defender_id:
                helper_origin=None
                helper_position=(f['ball'][0],f['ball'][1]+1.0);interior_arrival=max(0,f['drive']['defender_recovery_s']-elapsed-flight-delay)
            elif self.helper and f['helped']['committed']:
                arrival=self.c.recovery_delay_s*(2-self.helper.skill('S38'))+creation_passing.motion_time(math.hypot(helper_position[0]-target[0],helper_position[1]-target[1]),self.helper.acceleration_m_s2,min(self.helper.speed_m_s,self.helper.lateral_m_s))
                interior_arrival=max(0,arrival) if recovered else max(0,arrival-flight-delay)
            else:interior_arrival=0.0
        override=zone!='perimeter' or name=='pop' or recovered
        packet=self.planner.plan(zone,kind,d['quality'],self.pressure,primary_arrival,helper_position,interior_arrival,target,override,recovered,self.anchor,self.context,helper_origin if stable else None)
        plan=dict(packet.plan)
        if self.primary:
            # The first primary plan is used only for horizontal reach. Its
            # height/preparation/execution match the base finish plan; reach is
            # the shared scalar formula, independent of arrival/defender xy.
            distance=max(0,math.dist(defender_position,target)-vertical_access(self.primary,self.primary_context.capacity_factor,packet.geometry.release_height_cm,packet.geometry.coefficients)[2])
            primary_arrival=self.delay1+creation_passing.motion_time(distance,self.defender.acceleration_m_s2,self.defspeed)
            geometry=packet.geometry._replace(defender_x_m=defender_position[0],defender_y_m=defender_position[1])
            response=self.planner.contest(self.primary,self.primary_context,plan['zone'],geometry,primary_arrival,primary_origin if stable else None)
            base=plan['response'];strength=lambda r:r['conversion_reduction']+r['block_probability'] if r else 0
            use_primary=self.defender.player_id==self.anchor_id or strength(response)>=strength(base)
            plan['_projection_contests']=(response,) if self.defender.player_id==self.anchor_id else (base,response)
            if use_primary:plan['response']=response
            plan['contest_defender_id']=self.defender.player_id if use_primary else self.anchor_id
        self.counts['shot_nodes']+=1
        return {'kind':'shot','elapsed_s':elapsed+flight+delay+plan['preparation_s'],'record':result_record,'plan':plan,'receipt_probability':plan['reception']}

    def audit(self):
        return {'mode':MODE if self.provider is None else self.provider.revision,**dict(self.counts),'numeric_plan_builds':self.planner.plan_builds if self.owner is not None else 0,'numeric_contest_builds':self.planner.contest_builds if self.owner is not None else 0,'native_geometry':self.native.counts if self.native is not None else None,'native_unavailable_reason':self.native.reason if self.native is not None else None,'exact_node_repair_work':self.reference_resolver.audit() if hasattr(self,'reference_resolver') else None,'full_event_constructions':self.counts['detailed_fallback_calls'],'actual_selected_resolution':'unchanged detailed path'}



def project_candidate(frame,name,options,*,order=4):
    """Scoped opt-in dispatch; no process-global function replacement."""
    provider=frame.get('_geometry_provider_override',getattr(frame['spec'],'geometry_provider',None))
    resolver=CompactResolver(provider,order)
    result=pass_recovery.project_candidate(frame,name,options,order=order,node_resolver=resolver)
    return {**result,'policy':MODE if provider is None else provider.revision,'compact_evaluator':resolver.audit(),
        'node_count_semantics':'reference quadrature requests retained; compact_evaluator reports actual constructions'}
