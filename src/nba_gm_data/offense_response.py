"""Default-off coupled shooting/finishing response, NOT league calibration.

This supplies opportunities/probabilities to the existing interior event kernel.
Creation, passing, routes, POA and primary perimeter defense remain controlled
context. No stored old/new talent conversion or extra gravity/role bonus.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
import math

from .interior_defense import CAPACITY_SCALE,SKILL_SCALE,clamp,fingerprint
from .player_model import PlayerInputs
from .experimental_inputs import common_reader,interpretation_revision,same_input_snapshot,VERSION as INPUT_INTERPRETATION_VERSION

VERSION='offense_interior_mechanism_2026_11_13_v1'


@dataclass(frozen=True)
class OffenseCoefficients:
    shooting_floor: float=.12
    shooting_skill_span: float=.36
    range_penalty_per_m: float=.07
    release_fast_s: float=.24
    release_slow_extra_s: float=.55
    perimeter_pressure_penalty: float=.12
    positioning_pull_points: float=.45
    finish_floor: float=.35
    finish_skill_span: float=.45
    contact_penalty: float=.30

    def __post_init__(self):
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in asdict(self).values()):raise ValueError('Invalid exploratory offense coefficient')
        if self.positioning_pull_points<=0 or self.release_fast_s<=0:raise ValueError('Positive threat/time reference required')
        if max(self.shooting_floor+self.shooting_skill_span,self.finish_floor+self.finish_skill_span)>1:raise ValueError('Conversion probabilities out of bounds')


@dataclass(frozen=True)
class OffensiveProfile:
    inputs: PlayerInputs
    player_id: str
    skills: tuple[float,...]
    willingness: float
    locations: tuple[float,float,float]
    modes: tuple[float,float,float]
    standing_reach_cm: float
    jump_cm: float
    strength: float
    balance: float
    coefficients: OffenseCoefficients
    revision: str
    ft_probability: float
    input_contract: str

    def skill(self,number):return self.skills[number-1]


def compile_offense(inputs,coefficients=OffenseCoefficients(),*,research_scenario=False,two_point_rim_fraction=None):
    doc=inputs.to_dict();rows=doc['inputs']
    reader=common_reader(inputs,doc)
    if reader and (research_scenario or two_point_rim_fraction is not None):raise ValueError('Common interpretation owns scales and T02; do not mix legacy research arguments')
    def value(key):
        row=rows.get(key)
        if row is None or row['status']=='unknown':raise ValueError(f'{key}: explicit offensive scenario input required')
        return row['value']
    skills=[]
    for i in range(1,16):
        if reader:
            skills.append(reader.grade(f'S{i:02d}'));continue
        v=value(f'S{i:02d}')
        expected_scale='research_technique_reference_v0_2026_11_13' if research_scenario else SKILL_SCALE
        if i==7 and research_scenario:expected_scale='research_FT_conversion_percent_proxy_v1'
        if v['scale']!=expected_scale:raise ValueError('Explicit provisional technique/FT-proxy scale required')
        skills.append(v['grade']/100)
    def measure(key,metric):
        if reader:return reader.measurement(key)
        if research_scenario:
            metric,protocol={'P03':('hypothetical_standing_reach','unvalidated H1 dimensional fixture, not measured reach or shooting release point'),'P10':('hypothetical_jump_gain','synthetic reference, no jump test performed')}[key]
        else:protocol='interior_scenario_reference_v1'
        matches=[m for m in value(key)['measurements'] if m['metric']==metric and m['unit']=='cm' and m['protocol']==protocol]
        if len(matches)!=1:raise ValueError(f'{key}: declared synthetic {metric}/cm protocol required')
        return matches[0]['value']
    def capacity(key):
        if reader:return reader.capacity(key)
        if research_scenario:
            unit='N' if key=='P08' else 's'
            matches=[m for m in value(key)['measurements'] if m['metric']=='synthetic_reference_capacity' and m['unit']==unit and m['protocol']=='DIMENSIONAL FIXTURE ONLY, not observed protocol']
            if len(matches)!=1:raise ValueError('Explicit synthetic capacity protocol required')
            n=matches[0]['value']
            return n/(n+1000) if key=='P08' else 1/(1+n)
        v=value(key).get('display_grade')
        if v is None or v['scale']!=CAPACITY_SCALE:raise ValueError(f'{key}: declared synthetic capacity assessment required')
        return v['grade']/100
    def distribution(key,condition):
        if reader:return reader.distribution(key)
        v=value(key)
        if len(v['rows'])!=1 or v['rows'][0]['condition']!=condition:raise ValueError(f'{key}: unsupported conditional scenario')
        return v['rows'][0]['probabilities']
    condition='reference_opportunity' if research_scenario else 'available_opportunity'
    t01=distribution('T01',condition);loc=distribution('T02',condition);modes=distribution('T03','reference_shot' if research_scenario else condition)
    if research_scenario:
        if set(loc)!={'two_point','three_point'} or type(two_point_rim_fraction) not in (int,float) or not 0<=two_point_rim_fraction<=1:raise ValueError('Declare a controlled rim fraction within the two-point opportunity; it is not a player input estimate')
        loc={'rim':loc['two_point']*two_point_rim_fraction,'short_paint':loc['two_point']*(1-two_point_rim_fraction),'perimeter':loc['three_point']}
    elif set(loc)!={'rim','short_paint','perimeter'}:raise ValueError('T02 requires declared rim/short_paint/perimeter scenario regions')
    return OffensiveProfile(inputs,doc['player_id'],tuple(skills),t01['shoot'],tuple(loc[k] for k in ('rim','short_paint','perimeter')),
        tuple(modes[k] for k in ('catch','pull_up','movement')),measure('P03','standing_reach'),measure('P10','vertical_jump'),capacity('P08'),capacity('P09'),coefficients,
        fingerprint(interpretation_revision({'version':VERSION,'inputs':doc,'coefficients':asdict(coefficients),'research_scenario':research_scenario,'controlled_two_point_rim_fraction':two_point_rim_fraction},inputs)),
        reader.free_throw() if reader else skills[6] if research_scenario else .45+.50*skills[6],
        INPUT_INTERPRETATION_VERSION if reader else 'research_synthetic_explicit_FT_probability_proxy_v1' if research_scenario else 'controlled_synthetic_technique_v1')


def shooting_response(profile,*,mode='catch',distance_m=7.0,pressure=.35,defender_arrival_s=.65):
    if mode not in ('catch','pull_up','movement'):raise ValueError('Unknown shooting mode')
    if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in (distance_m,pressure,defender_arrival_s)) or pressure>1:raise ValueError('Invalid declared shooting context')
    c=profile.coefficients;three=distance_m>=6.7
    # Select ONE mode-specific execution skill; movement does not add a catch
    # talent. Technique/balance affect response, not physical unimpeded speed.
    skill=profile.skill((1 if three else 4)+('catch','pull_up','movement').index(mode))
    reference=6.7 if three else 4.5
    extension=max(0,distance_m-reference)
    range_cost=extension*c.range_penalty_per_m*(1-profile.skill(9))
    preparation=release_preparation(profile)
    timely=clamp((defender_arrival_s-preparation+.20)/.40)
    contest=pressure*(1-timely)*c.perimeter_pressure_penalty
    conversion=clamp(c.shooting_floor+c.shooting_skill_span*skill*(.90+.10*profile.balance)+(.07 if not three else 0)-range_cost-contest,.02,.90)
    return {'mode':mode,'skill_id':f'S{((1 if three else 4)+("catch","pull_up","movement").index(mode)):02d}',
        'distance_m':distance_m,'preparation_s':preparation,'range_cost':range_cost,'controlled_primary_contest_cost':contest,
        'make_probability':conversion,'shot_value':3 if three else 2,'source_revision':profile.revision}


def free_throw_response(profile):
    # S08/release and S09/range cannot affect free-throw talent.
    return profile.ft_probability


def release_preparation(profile):
    return profile.coefficients.release_fast_s+(1-profile.skill(8))*profile.coefficients.release_slow_extra_s


def receiving_preparation(profile,quality):
    return .18*(1-profile.skill(14))+.25*(1-quality)


def finish_preparation(kind):
    return .1 if kind in ('dunk','lob') else .25


def finishing_response(profile,kind,*,contact=0.0,delivery_quality=1.0):
    if kind not in ('layup','contact_layup','floater','dunk','lob'):raise ValueError('Unknown finish')
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in (contact,delivery_quality)) or not 0<=contact<=1 or not 0<=delivery_quality<=1:raise ValueError('Invalid controlled finish context')
    c=profile.coefficients;requested=kind
    reachable=profile.standing_reach_cm+profile.jump_cm>=310
    if kind in ('dunk','lob') and not reachable:kind='layup'
    if kind=='floater':conversion=c.finish_floor+c.finish_skill_span*profile.skill(11);skill='S11'
    elif kind in ('dunk','lob'):
        conversion=.50+.45*profile.skill(12);skill='S12'
        if kind=='lob':conversion*=.60+.40*profile.skill(13);skill='S12 with S13 coordination constraint'
    else:
        conversion=c.finish_floor+c.finish_skill_span*profile.skill(10)*(.90+.10*profile.balance);skill='S10'
        if kind=='contact_layup':conversion*=1-contact*c.contact_penalty*(1-profile.skill(15))*(1.25-.25*profile.strength);skill='S10 with S15 contact constraint'
    reception=1.0
    if requested=='lob':reception=delivery_quality*(.50+.50*profile.skill(14))
    return {'requested_finish':requested,'finish':kind,'skill':skill,'make_probability':clamp(conversion,.02,.98),
            'reception_probability':reception,'physically_dunk_available':reachable,'creation':'opportunity supplied by controlled context, not by this execution skill'}


def credibility(profile,*,distance_m=7.0,pressure=.35,defender_arrival_s=.65):
    probability=sum(weight*shooting_response(profile,mode=mode,distance_m=distance_m,pressure=pressure,defender_arrival_s=defender_arrival_s)['make_probability'] for mode,weight in zip(('catch','pull_up','movement'),profile.modes,strict=True))
    # Units are expected perimeter points per declared shooting opportunity.
    # This is a readout of ability/preference, never an additional score bonus.
    return profile.willingness*profile.locations[2]*3*probability


@dataclass(frozen=True)
class Deployment:
    player_id: str
    perimeter_x_m: float
    perimeter_y_m: float

    def __post_init__(self):
        if not self.player_id or any(not math.isfinite(x) for x in (self.perimeter_x_m,self.perimeter_y_m)):raise ValueError('Invalid offensive deployment')
        if math.hypot(self.perimeter_x_m,self.perimeter_y_m)<6.7:raise ValueError('Perimeter deployment must be at a declared three-point distance')


@dataclass(frozen=True)
class CombinedOffense:
    profiles: tuple[OffensiveProfile,...]
    deployments: tuple[Deployment,...]
    # (defending team ID, assigned opposing player ID). Assignment itself is
    # controlled context; the response to credible shooting is endogenous.
    anchor_assignments: tuple[tuple[str,str],...]
    finish_mix: tuple[float,...]=(.40,.20,.20,.10,.10)
    delivery_quality: float=.95
    primary_perimeter_pressure: float=.35
    primary_arrival_s: float=.65
    assist_credit_probability: float=.58
    offensive_rebound_probability: float=.26
    creation: object | None = None

    def __post_init__(self):
        if not all(isinstance(x,tuple) for x in (self.profiles,self.deployments,self.anchor_assignments,self.finish_mix)):raise ValueError('Immutable scenario tuples required')
        ids=[p.player_id for p in self.profiles];places=[p.player_id for p in self.deployments]
        if len(set(ids))!=len(ids) or set(ids)!=set(places) or len(places)!=len(ids):raise ValueError('Each profile requires exactly one deployment')
        if len({t for t,p in self.anchor_assignments})!=len(self.anchor_assignments):raise ValueError('Duplicate controlled anchor assignments')
        if len(self.finish_mix)!=5 or any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in self.finish_mix) or not math.isclose(sum(self.finish_mix),1):raise ValueError('Five finish probabilities must sum to one')
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in (self.assist_credit_probability,self.offensive_rebound_probability,self.delivery_quality,self.primary_perimeter_pressure,self.primary_arrival_s)):raise ValueError('Finite numeric controlled probabilities/times required')
        if not 0<=self.assist_credit_probability<=1 or not 0<=self.offensive_rebound_probability<1:raise ValueError('Invalid controlled support probabilities')
        if not 0<=self.delivery_quality<=1 or not 0<=self.primary_perimeter_pressure<=1 or not math.isfinite(self.primary_arrival_s) or self.primary_arrival_s<0:raise ValueError('Invalid controlled delivery/perimeter context')

    @property
    def revision(self):
        data={'version':VERSION,'profiles':[(p.player_id,p.revision) for p in self.profiles],'deployments':[asdict(p) for p in self.deployments],
        'assignments':self.anchor_assignments,'finish_mix':self.finish_mix,'delivery':self.delivery_quality,'pressure':self.primary_perimeter_pressure,'arrival':self.primary_arrival_s,'controlled_assist_probability':self.assist_credit_probability,'controlled_oreb_probability':self.offensive_rebound_probability}
        if self.creation is not None:data['creation_revision']=self.creation.revision
        return fingerprint(data)


def offensive_spatial_profile(profile,deployment,*,pressure=.35,defender_arrival_s=.65):
    return {'status':'partial_C31_shooting_finish_slice','input_revision':profile.revision,'input_contract':profile.input_contract,'raw_inputs':profile.inputs.to_dict(),'reference_conditions':{'controlled_primary_pressure':pressure,'controlled_primary_arrival_s':defender_arrival_s},'perimeter_location_m':(deployment.perimeter_x_m,deployment.perimeter_y_m),
        'perimeter_expected_points_per_opportunity':credibility(profile,distance_m=math.hypot(deployment.perimeter_x_m,deployment.perimeter_y_m),pressure=pressure,defender_arrival_s=defender_arrival_s),'willingness':profile.willingness,'conditional_location_weights':dict(zip(('rim','short_paint','perimeter'),profile.locations,strict=True)),'shot_mode_weights':dict(zip(('catch','pull_up','movement'),profile.modes,strict=True)),
        'shooting_responses':{mode:shooting_response(profile,mode=mode,distance_m=math.hypot(deployment.perimeter_x_m,deployment.perimeter_y_m),pressure=pressure,defender_arrival_s=defender_arrival_s) for mode in ('catch','pull_up','movement')},
        'finishes':{kind:finishing_response(profile,kind,contact=1 if kind=='contact_layup' else 0) for kind in ('layup','contact_layup','floater','dunk','lob')},
        'free_throw_probability':free_throw_response(profile),'unimplemented':['creation/access','passing delivery skill','routes/screens','complete C31','role/OVR calibration']}


def baseline(profile):
    rim,mid,perimeter=profile.locations
    willing_perimeter=perimeter*profile.willingness
    willing_mid=mid*profile.willingness
    total=rim+willing_mid+willing_perimeter
    if total<=0:raise ValueError('Scenario offers no willing action; explicit creation/reset context required')
    return {'weight':1.0,'rim_share':rim/total,'three_share':willing_perimeter/total,
        'rim_pct':finishing_response(profile,'layup')['make_probability'],'mid_pct':shooting_response(profile,distance_m=4.5)['make_probability'],
        'three_pct':shooting_response(profile)['make_probability'],'ft_pct':free_throw_response(profile),
        'passing':1.0,'oreb':1.0}  # Equal exposure weights, NOT unknown-player talent grades.


def prepare_coupled(spec,pools,anchors,contexts):
    from dataclasses import replace
    profiles={p.player_id:p for p in spec.profiles};deployments={p.player_id:p for p in spec.deployments}
    actual={item['player']['id'] for pool in pools.values() for item in pool}
    if not actual<=set(profiles):raise ValueError('Every active player needs explicit combined offensive inputs; no fallback')
    locations={};spatial={};team_for={};weights={}
    for tid,pool in pools.items():
        spatial[tid]={}
        for item in pool:
            pid=item['player']['id'];team_for[pid]=tid;weights[pid]=item['minutes']/48
            locations[pid]=deployments[pid]
            spatial[tid][pid]=offensive_spatial_profile(profiles[pid],deployments[pid],pressure=spec.primary_perimeter_pressure,defender_arrival_s=spec.primary_arrival_s)
    positions={};assignment=dict(spec.anchor_assignments)
    for tid,anchor in anchors.items():
        if anchor is None:positions[tid]=(0.0,1.0);continue
        anchor_pid=anchor.profile.inputs.player_id
        if anchor_pid not in profiles or not same_input_snapshot(anchor.profile.inputs,profiles[anchor_pid].inputs):raise ValueError('Offensive and defensive projections must share one authoritative player input snapshot and interpretation')
        pid=assignment.get(tid)
        if pid not in actual or team_for[pid]==tid:raise ValueError('Declare current opposing assignment for each anchor')
        threat=spatial[team_for[pid]][pid]['perimeter_expected_points_per_opportunity']
        pull=1-math.exp(-threat/profiles[pid].coefficients.positioning_pull_points)
        dep=deployments[pid]
        positions[tid]=(dep.perimeter_x_m*pull,1+(dep.perimeter_y_m-1)*pull)
        # The old manually supplied spacing knob is not used in combined mode.
        contexts[tid]=replace(contexts[tid],spacing=0)
        spatial[team_for[pid]][pid]['anchor_assignment_response']={'defending_team_id':tid,'pull_fraction':pull,'defender_position_m':positions[tid]}
    return {'spec':spec,'profiles':profiles,'deployments':locations,'team_for':team_for,'weights':weights,'spatial':spatial,'positions':positions}


def _select(names,weights,draw):
    target=draw*sum(weights)
    for name,w in zip(names,weights,strict=True):
        target-=w
        if target<0:return name
    return names[-1]



@dataclass(frozen=True)
class ActionShotContext:
    """Derived action state, not a second talent store or fixed setup quality."""
    finish_kind: str | None = None
    shot_mode: str | None = None
    delivery_quality: float = 1.0
    primary_pressure: float = .35
    primary_arrival_s: float = .65
    defender_position_m: tuple[float,float] = (0.0,1.0)
    interior_arrival_s: float | None = None
    receiver_delay_s: float = 0.0
    received_pass: bool = False
    shot_position_m: tuple[float,float] | None = None

    def __post_init__(self):
        for value in (self.delivery_quality,self.primary_pressure,self.primary_arrival_s,self.receiver_delay_s,*self.defender_position_m):
            if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Finite derived action geometry required')
        if not 0<=self.delivery_quality<=1 or not 0<=self.primary_pressure<=1 or min(self.primary_arrival_s,self.receiver_delay_s)<0:raise ValueError('Invalid derived delivery/arrival')
        if self.interior_arrival_s is not None and (not math.isfinite(self.interior_arrival_s) or self.interior_arrival_s<0):raise ValueError('Invalid derived interior arrival')


@dataclass(frozen=True,kw_only=True)
class HelpShotContext(ActionShotContext):
    """Existing helper route origin retains its bearing at the route endpoint."""
    defender_route_origin_m: tuple[float,float]

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.defender_route_origin_m,tuple) or len(self.defender_route_origin_m)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in self.defender_route_origin_m):raise ValueError('Finite immutable helper route origin required')


@dataclass(frozen=True,kw_only=True)
class StableBearingActionContext(ActionShotContext):
    defender_route_origin_m: tuple[float,float] | None=None
    bearing_policy: str='stable_route_bearing_v2'
    recovered_receipt: bool=False

    def __post_init__(self):
        super().__post_init__()
        if self.bearing_policy!='stable_route_bearing_v2':raise ValueError('Unknown stable bearing policy')
        origin=self.defender_route_origin_m
        if origin is not None and (not isinstance(origin,tuple) or len(origin)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in origin)):raise ValueError('Finite immutable route origin required')


def plan_attack(state,pid,zone,draws,defending_team,anchor,context,*,outlet=False,action_context=None,include_details=True):
    from .shot_geometry import ShotGeometry
    from .interior_defense import interior_response
    spec=state['spec'];p=state['profiles'][pid];location=state['deployments'][pid]
    mode=_select(('catch','pull_up','movement'),p.modes,draws[16])
    requested=_select(('layup','contact_layup','floater','dunk','lob'),spec.finish_mix,draws[17])
    if action_context and action_context.finish_kind is not None:requested=action_context.finish_kind
    if action_context and action_context.shot_mode is not None:mode=action_context.shot_mode
    dx,dy=action_context.defender_position_m if action_context else state['positions'][defending_team]
    delivery=action_context.delivery_quality if action_context else spec.delivery_quality
    pressure=action_context.primary_pressure if action_context else spec.primary_perimeter_pressure
    primary_arrival=action_context.primary_arrival_s if action_context else spec.primary_arrival_s
    off=baseline(p) if include_details else {'rim_pct':0.0,'mid_pct':0.0,'three_pct':0.0,'ft_pct':free_throw_response(p)}
    reception=1.0;finish=None;shot=None
    if zone=='perimeter':
        distance=math.hypot(location.perimeter_x_m,location.perimeter_y_m)
        if action_context and action_context.shot_position_m is not None:distance=math.hypot(*action_context.shot_position_m)
        shot=shooting_response(p,mode=mode,distance_m=distance,pressure=pressure,defender_arrival_s=primary_arrival)
        x,y=location.perimeter_x_m,location.perimeter_y_m;height=p.standing_reach_cm+p.jump_cm*.25
        if action_context and action_context.shot_position_m is not None:x,y=action_context.shot_position_m
        prep=shot['preparation_s'];window=.05;contact=0
        off['three_pct']=shot['make_probability']
        if mode in ('catch','movement') or outlet:reception=delivery*(.5+.5*p.skill(14))
    elif zone=='short_paint':
        x=(-1 if draws[19]<.5 else 1)*(2.0+draws[18]);y=3.5
        # Conditional midrange jumper versus floater: mode execution and touch
        # are distinct, not two complete shot bonuses.
        recovered=getattr(action_context,'recovered_receipt',False)
        if (draws[17]<.5 and not(recovered and action_context.finish_kind=='midrange')) or (recovered and action_context.finish_kind=='floater'):
            requested='floater';finish=finishing_response(p,requested)
            off['mid_pct']=finish['make_probability'];prep=.2
        else:
            requested='midrange'
            distance=math.hypot(*(action_context.shot_position_m if recovered and action_context.finish_kind=='midrange' and action_context.shot_position_m is not None else (x,y)))
            shot=shooting_response(p,mode=mode,distance_m=distance,pressure=pressure,defender_arrival_s=primary_arrival)
            off['mid_pct']=shot['make_probability'];prep=shot['preparation_s']
        height=p.standing_reach_cm+p.jump_cm*.70+(20 if requested=='floater' else 0)
        window=.5;contact=0
    else:
        # Execution does not create a drive/lob. The available chance and mix
        # are explicitly controlled; new handling/passing/routes remain absent.
        contact=1.0 if requested=='contact_layup' else 0.0
        finish=finishing_response(p,requested,contact=contact,delivery_quality=delivery)
        used=finish['finish']
        if used=='floater':zone='short_paint';off['mid_pct']=finish['make_probability'];radius=2.0+draws[18]*1.5
        else:off['rim_pct']=finish['make_probability'];radius=.2+draws[18]*1.0
        theta=(draws[19]-.5)*2.4
        x,y=math.sin(theta)*radius,math.cos(theta)*radius
        height=320 if used in ('dunk','lob') else p.standing_reach_cm+p.jump_cm*.35 if used!='floater' else p.standing_reach_cm+p.jump_cm*.7+20
        prep=finish_preparation(used)
        window=.55+draws[18]*.45;reception=finish['reception_probability']
    if action_context:
        if action_context.shot_position_m is not None:x,y=action_context.shot_position_m
        window=0.0
        reception=1.0
        if action_context.received_pass:
            reception=delivery*(.5+.5*p.skill(14))
            # One catch gate; control/placement also change time to prepare.
            # Re-evaluate the same shooting response, never add an accuracy bonus.
            receiving_delay=receiving_preparation(p,delivery)
            prep+=receiving_delay
            if shot is not None:
                shot=shooting_response(p,mode=mode,distance_m=distance,pressure=pressure,defender_arrival_s=max(0,primary_arrival-receiving_delay))
                off['three_pct' if zone=='perimeter' else 'mid_pct']=shot['make_probability']
                shot={**shot,'receiving_preparation_s':receiving_delay}
    geometry=ShotGeometry(x,y,height,dx,dy,approach_angle_deg=draws[19]*180,attack_time_s=window,preparation_s=prep,contact=contact)
    route_origin=getattr(action_context,'defender_route_origin_m',None)
    response=interior_response(anchor.profile,context,zone=zone,geometry=geometry,bearing_policy=getattr(action_context,'bearing_policy','legacy_bearing_v1'),arrival_override_s=action_context.interior_arrival_s if action_context else None,
        **({'defender_route_origin_m':route_origin} if route_origin is not None else {}),
        **({'diagnostics':False} if not include_details else {})) if anchor else None
    if not include_details:return {'player_id':pid,'zone':zone,'off':off,'response':response,'reception':reception,'preparation_s':prep}
    details={'offense_revision':p.revision,'mode':mode,'finish':finish,'shooting':shot,'geometry':asdict(geometry),'reception_probability':reception,
             'defense_response':response,'controlled_dependencies':['creation/access','passing quality','routes','POA support','primary perimeter contest']}
    if action_context:
        details['derived_action_context']=asdict(action_context)
        details['controlled_dependencies']=['supplied routes/screens','defensive assignments','receiver defender route gap','rebound support']
    return {'player_id':pid,'zone':zone,'off':off,'response':response,'details':details,'reception':reception}


def choose_outlet(state,team_id,draw):
    ids=[pid for pid,tid in state['team_for'].items() if tid==team_id]
    weights=[state['weights'][pid]*state['spatial'][team_id][pid]['perimeter_expected_points_per_opportunity'] for pid in ids]
    return _select(ids,weights,draw) if sum(weights)>0 else None
