"""Bounded geometric C27 response for the combined experiment, not motion simulation."""
from dataclasses import asdict,dataclass,fields
import math
from .interior_defense import FORMULA_VERSION,clamp


@dataclass(frozen=True)
class GeometryCoefficients:
    vertical_transition_cm: float=35.0
    residual_lateral_fraction: float=.25
    trailing_quality: float=.35

    def __post_init__(self):
        if type(self.vertical_transition_cm) not in (int,float) or not math.isfinite(self.vertical_transition_cm) or self.vertical_transition_cm<=0:raise ValueError('Positive geometric transition required')
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in (self.residual_lateral_fraction,self.trailing_quality)):raise ValueError('Finite geometric fractions required')
        if not 0<=self.residual_lateral_fraction<=1 or not 0<=self.trailing_quality<=1:raise ValueError('Invalid geometric fractions')


@dataclass(frozen=True)
class ShotGeometry:
    shot_x_m: float
    shot_y_m: float
    release_height_cm: float
    defender_x_m: float=0.0
    defender_y_m: float=1.0
    approach_angle_deg: float=0.0
    attack_time_s: float=.9
    preparation_s: float=.3
    contact: float=0.0
    coefficients: GeometryCoefficients=GeometryCoefficients()

    def __post_init__(self):
        for field in fields(self):
            key=field.name
            if key=='coefficients':continue
            value=getattr(self,key)
            if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Finite dimensional geometry required')
        if self.release_height_cm<=0 or min(self.attack_time_s,self.preparation_s)<0 or not 0<=self.contact<=1:raise ValueError('Invalid shot time/height/contact')


@dataclass(frozen=True)
class ContestBasis:
    profile: object
    quality_base: float
    direction_rad: float | None
    trailing_quality: float
    influence: float
    commitment: float
    late: float
    contact: float


def contest_at_angle(basis,approach_angle_deg):
    """Same contest arithmetic, with decision-local kinematics reused exactly."""
    p=basis.profile;c=p.coefficients
    angle=(basis.trailing_quality+(1-basis.trailing_quality)/math.pi if basis.direction_rad is None else
        basis.trailing_quality+(1-basis.trailing_quality)*max(0,math.cos(math.radians(approach_angle_deg)-basis.direction_rad)))
    quality=basis.quality_base*angle;influence=basis.influence;commitment=basis.commitment
    return {'contest_alignment':angle,'contest_quality':quality*influence,
        'conversion_reduction':c.max_conversion_reduction*quality*commitment*influence,
        'block_probability':c.max_block_probability*quality*p.jump_choice*influence,
        'foul_probability':clamp(c.max_contest_foul*influence*(1-p.legal)*commitment*(1+basis.contact*.5)+c.late_foul*basis.late*p.jump_choice*(1-p.legal)),
        'avoidance_probability':c.max_avoidance*quality*commitment*influence}


def vertical_access(profile,capacity_factor,release_height_cm,coefficients):
    """Authoritative scalar reach calculation, shared by numerical projection."""
    if profile.wingspan_cm is None:raise ValueError('P02: explicit supported wingspan observation required for varied geometry')
    g=coefficients
    reach=profile.standing_reach_cm+profile.jump_cm*capacity_factor
    spare=max(0,reach-release_height_cm)
    # A continuous access response over varied release heights; no current-
    # player min-max scale or hard full-credit ceiling at one release height.
    vertical=1-math.exp(-spare/g.vertical_transition_cm)
    lateral=profile.wingspan_cm/200*(g.residual_lateral_fraction+(1-g.residual_lateral_fraction)*vertical)
    return reach,vertical,lateral


STABLE_BEARING_POLICY='stable_route_bearing_v2'


def stable_bearing(shot,route_origin=None):
    """Numerical coincidence only: 32 coordinate ULPs, capped at 1e-10 m.

    Use actual separation whenever resolved, then the last represented route
    segment. With neither direction defined, use the rotation mean of alignment
    (not a marginalized score and not a calibrated basketball distance).
    """
    coordinates=(shot.shot_x_m,shot.shot_y_m,shot.defender_x_m,shot.defender_y_m)
    if route_origin is not None:
        if not isinstance(route_origin,(tuple,list)) or len(route_origin)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in route_origin):raise ValueError('Finite route origin required')
        coordinates+=tuple(route_origin)
    unit=math.ulp(max(1.0,*(abs(v) for v in coordinates)));tolerance=min(1e-10,32*unit)
    dx=shot.defender_x_m-shot.shot_x_m;dy=shot.defender_y_m-shot.shot_y_m
    separation=math.hypot(dx,dy);route_separation=None;direction=None;source='rotation_mean_undefined'
    if separation>tolerance:direction=math.atan2(dy,dx);source='current_separation';reference=separation
    else:
        reference=0.0
        if route_origin is not None:
            rx=route_origin[0]-shot.shot_x_m;ry=route_origin[1]-shot.shot_y_m;route_separation=math.hypot(rx,ry)
            if route_separation>tolerance:direction=math.atan2(ry,rx);source='last_route_segment';reference=route_separation
    return direction,{'policy':STABLE_BEARING_POLICY,'source':source,'tolerance_m':tolerance,'coordinate_ulp_m':unit,
        'current_separation_m':separation,'route_separation_m':route_separation,'reference_separation_m':reference,
        'undefined_convention':'rotation mean of directional alignment; not marginalized scoring'}


def geometry_response(profile,context,zone,shot,*,arrival_override_s=None,defender_route_origin_m=None,diagnostics=True,bearing_policy='legacy_bearing_v1'):
    c=profile.coefficients;g=shot.coefficients
    reach,vertical,lateral=vertical_access(profile,context.capacity_factor,shot.release_height_cm,g)
    separation=math.hypot(shot.shot_x_m-shot.defender_x_m,shot.shot_y_m-shot.defender_y_m)
    distance=max(0,separation-lateral)+(1-profile.positioning)*c.position_distance_m
    travel=math.sqrt(2*distance/(profile.acceleration_m_s2*max(.05,context.capacity_factor)))
    arrival=context.recognition_delay_s+travel
    if arrival_override_s is not None:
        if type(arrival_override_s) not in (int,float) or not math.isfinite(arrival_override_s) or arrival_override_s<0:raise ValueError('Invalid upstream arrival')
        arrival=arrival_override_s
    window=shot.attack_time_s+shot.preparation_s+context.poa_containment*c.poa_extra_window_s
    timely=clamp((window-arrival)/c.arrival_margin_s)
    direction=math.atan2(shot.defender_y_m-shot.shot_y_m,shot.defender_x_m-shot.shot_x_m)
    if defender_route_origin_m is not None:
        if not isinstance(defender_route_origin_m,(tuple,list)) or len(defender_route_origin_m)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in defender_route_origin_m):raise ValueError('Finite helper route origin required')
        ox,oy=defender_route_origin_m
        # The current position can coincide with the endpoint. Retain the
        # supplied route bearing instead of resetting atan2(0,0) to zero.
        if (ox,oy)!=(shot.shot_x_m,shot.shot_y_m):direction=math.atan2(oy-shot.shot_y_m,ox-shot.shot_x_m)
    bearing=None
    if bearing_policy==STABLE_BEARING_POLICY:direction,bearing=stable_bearing(shot,defender_route_origin_m)
    elif bearing_policy!='legacy_bearing_v1':raise ValueError('Unknown bearing policy')
    influence=context.anchor_available*timely if zone!='perimeter' else 0.0
    control=.5+.25*profile.strength_capacity+.25*profile.balance_capacity
    quality_base=profile.technique*vertical*control*(.5+.5*profile.positioning)
    commitment=profile.jump_choice+profile.conservative_choice*.65+profile.stay_down_choice*.10
    late=context.anchor_available*(1-timely)*clamp(1-abs(arrival-window)/c.arrival_margin_s) if zone!='perimeter' else 0
    basis=ContestBasis(profile,quality_base,direction,g.trailing_quality,influence,commitment,late,shot.contact)
    contest=contest_at_angle(basis,shot.approach_angle_deg)
    result={'formula_version':FORMULA_VERSION+'+varied_geometry_v1','input_revision':profile.revision,
        **({'context':asdict(context),'geometry':asdict(shot)} if diagnostics else {}),'zone':zone,
        'reachable_height_cm':reach,'geometry_fraction':vertical,'horizontal_reach_m':lateral,'travel_distance_m':distance,'travel_s':travel,'arrival_s':arrival,
        'window_s':window,'timely_fraction':timely,'coverage_available':influence,**contest}
    if defender_route_origin_m is not None:
        result.update(formula_version=result['formula_version']+'+helper_route_bearing_v1',defender_route_origin_m=tuple(defender_route_origin_m))
    if bearing is not None:result.update(formula_version=FORMULA_VERSION+'+varied_geometry_v1+'+STABLE_BEARING_POLICY,bearing=bearing)
    if not diagnostics:result['_contest_basis']=basis
    return result
