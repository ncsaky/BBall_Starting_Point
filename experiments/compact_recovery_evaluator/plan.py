"""Projection-only numeric shot packet, using authoritative scalar responses.

No selected event/detail objects. The geometry tuple exposes exactly the
scalar attributes used by geometry_response(diagnostics=False).
"""
from typing import NamedTuple
import math
from nba_gm_data.offense_response import (_select,shooting_response,finishing_response,finish_preparation,receiving_preparation,free_throw_response)
from nba_gm_data.shot_geometry import GeometryCoefficients,geometry_response,vertical_access

G=GeometryCoefficients()


class NumericGeometry(NamedTuple):
    shot_x_m: float
    shot_y_m: float
    release_height_cm: float
    defender_x_m: float
    defender_y_m: float
    approach_angle_deg: float
    attack_time_s: float
    preparation_s: float
    contact: float
    coefficients: object=G


class NumericPlan(NamedTuple):
    plan: dict
    geometry: NumericGeometry


class Planner:
    """One candidate owner; immutable input views, no cross-call/global cache."""
    def __init__(self,state,pid,name,draws):
        self.owner=state;self.pid=pid;self.name=name;self.p=state['profiles'][pid];self.location=state['deployments'][pid]
        self.draws=tuple(draws[16:20]);self.memo={};self.defense_memo={};self.plan_builds=0;self.contest_builds=0
        self.mode='catch' if name in ('F06','pop') else _select(('catch','pull_up','movement'),self.p.modes,self.draws[0])
        self.requested=_select(('layup','contact_layup','floater','dunk','lob'),state['spec'].finish_mix,self.draws[1])

    def contest(self,profile,context,zone,geometry,arrival):
        key=(id(profile),context,zone,geometry,arrival)
        response=self.defense_memo.get(key)
        if response is None:
            response=geometry_response(profile,context,zone,geometry,arrival_override_s=arrival,diagnostics=False);self.defense_memo[key]=response;self.contest_builds+=1
        return response

    def plan(self,zone,kind,quality,pressure,primary_arrival,defender_position,interior_arrival,target,override_position,recovered,anchor,context):
        key=(zone,kind,quality,pressure,primary_arrival,defender_position,interior_arrival,target,override_position,recovered,id(anchor.profile) if anchor else None,context)
        cached=self.memo.get(key)
        if cached is not None:return cached
        p=self.p;mode=self.mode;requested=kind if kind is not None else self.requested;draw17,draw18,draw19=self.draws[1:]
        off={'rim_pct':0.0,'mid_pct':0.0,'three_pct':0.0,'ft_pct':free_throw_response(p)};shot=None
        if zone=='perimeter':
            distance=math.hypot(*(target if override_position else (self.location.perimeter_x_m,self.location.perimeter_y_m)))
            shot=shooting_response(p,mode=mode,distance_m=distance,pressure=pressure,defender_arrival_s=primary_arrival)
            x,y=self.location.perimeter_x_m,self.location.perimeter_y_m;height=p.standing_reach_cm+p.jump_cm*.25
            prep=shot['preparation_s'];contact=0;off['three_pct']=shot['make_probability']
        elif zone=='short_paint':
            x=(-1 if draw19<.5 else 1)*(2.0+draw18);y=3.5
            if (draw17<.5 and not(recovered and kind=='midrange')) or (recovered and kind=='floater'):
                requested='floater';finish=finishing_response(p,requested);off['mid_pct']=finish['make_probability'];prep=.2
            else:
                requested='midrange';distance=math.hypot(*(target if recovered and kind=='midrange' and override_position else (x,y)))
                shot=shooting_response(p,mode=mode,distance_m=distance,pressure=pressure,defender_arrival_s=primary_arrival);off['mid_pct']=shot['make_probability'];prep=shot['preparation_s']
            height=p.standing_reach_cm+p.jump_cm*.70+(20 if requested=='floater' else 0);contact=0
        else:
            contact=1.0 if requested=='contact_layup' else 0.0;finish=finishing_response(p,requested,contact=contact,delivery_quality=quality);used=finish['finish']
            if used=='floater':zone='short_paint';off['mid_pct']=finish['make_probability'];radius=2.0+draw18*1.5
            else:off['rim_pct']=finish['make_probability'];radius=.2+draw18*1.0
            theta=(draw19-.5)*2.4;x,y=math.sin(theta)*radius,math.cos(theta)*radius
            height=320 if used in ('dunk','lob') else p.standing_reach_cm+p.jump_cm*.35 if used!='floater' else p.standing_reach_cm+p.jump_cm*.7+20
            prep=finish_preparation(used)
        if override_position:x,y=target
        reception=quality*(.5+.5*p.skill(14));receiving_delay=receiving_preparation(p,quality);prep+=receiving_delay
        if shot is not None:
            shot=shooting_response(p,mode=mode,distance_m=distance,pressure=pressure,defender_arrival_s=max(0,primary_arrival-receiving_delay));off['three_pct' if zone=='perimeter' else 'mid_pct']=shot['make_probability']
        geometry=NumericGeometry(x,y,height,defender_position[0],defender_position[1],draw19*180,0.0,prep,contact)
        response=self.contest(anchor.profile,context,zone,geometry,interior_arrival) if anchor else None
        result=NumericPlan({'player_id':self.pid,'zone':zone,'off':off,'response':response,'reception':reception,'preparation_s':prep},geometry)
        self.memo[key]=result;self.plan_builds+=1;return result
