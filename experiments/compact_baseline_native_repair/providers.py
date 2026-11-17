"""Caller-owned experimental native providers; runtime imports none of this."""
from dataclasses import dataclass
import math
from .native_adapter import GeometryBatch


@dataclass(frozen=True)
class ArithmeticProvider:
    revision: str='native_geometry_arithmetic_v2'
    required_bearing_policy: str='legacy_bearing_v1'

    def __call__(self,frame,name,option,order):return GeometryBatch(frame,name,option,order)



class StableBatch(GeometryBatch):
    def geometry(self,frame,name,option,error,direction):
        g=super().geometry(frame,name,option,error,direction)
        if self.last_was_reference or g['lost']:return g
        def near(a,b):return math.isfinite(b) and abs(a-b)<=128*math.ulp(max(1.,abs(a),abs(b)))
        radius=math.hypot(*g['receiver_feet_m'])
        deadline=frame['screen']['window_end_s'] if frame['screen'] and name in ('F03','F04','pop') else frame['setup'].roll_window_s if name in ('F03','F04') else math.inf
        total=frame['elapsed']+option.get('wait_s',0)+option['delivery']['flight_s']+g['delay_s']
        if any(near(radius,v) for v in (1.6,3.5,6.7)) or near(total,deadline):
            self.counts['zone_or_route_window_repairs']=self.counts.get('zone_or_route_window_repairs',0)+1
            return self.repair(frame,name,option,error,direction)
        return g

@dataclass(frozen=True)
class StableProvider:
    revision: str='native_geometry_stable_route_v2'
    required_bearing_policy: str='stable_route_bearing_v2'

    def __call__(self,frame,name,option,order):return StableBatch(frame,name,option,order)

    def repair_reason(self,frame,action):
        """Recompute the same model node when geometry-to-response is ill-conditioned."""
        def near(a,b):return abs(a-b)<=128*math.ulp(max(1.,abs(a),abs(b)))
        if near(action['elapsed_s'],frame['remaining_s']):return 'clock boundary'
        if action['kind']!='shot':return None
        plan=action['plan'];responses=(plan.get('response'),*plan.get('_projection_contests',()))
        for r in responses:
            if not r:continue
            b=r.get('bearing')
            if b:
                tolerance=b['tolerance_m'];sep=b['current_separation_m'];route=b['route_separation_m']
                if abs(sep-tolerance)<=tolerance/2 or (route is not None and sep<=tolerance and abs(route-tolerance)<=tolerance/2):return 'bearing source boundary'
                if b['source']!='rotation_mean_undefined' and b['reference_separation_m']<=32*b['coordinate_ulp_m']/1e-10:return 'conditioned bearing vector'
            if near(r['arrival_s'],r['window_s']) or near(r['window_s']-r['arrival_s'],r['_contest_basis'].profile.coefficients.arrival_margin_s):return 'contest window boundary'
        return None
