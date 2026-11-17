"""Default-OFF bounded on-ball screen/navigation phase, not a scoring engine.

Initial positions/call and stay/show policy are supplied. Technique, movement,
contact and action reads produce delay and a moving roll/slip receiving window.
All maps are exploratory synthetic response contracts, not measured NBA rates.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
import math
from .interior_defense import CAPACITY_SCALE,SKILL_SCALE,clamp,fingerprint
from .creation_passing import motion_time
from .player_model import PlayerInputs
from .experimental_inputs import common_reader,interpretation_revision,same_input_snapshot

VERSION='screen_navigation_2026_11_13_v1'


@dataclass(frozen=True)
class ScreenProfile:
    inputs: PlayerInputs
    player_id: str
    screen: float
    read: float
    navigation: float
    anticipation: float
    attention: float
    height_cm: float
    mass_kg: float
    acceleration: float
    speed: float
    lateral: float
    strength: float
    balance: float
    preferences: tuple[float,...]
    roles: tuple[str,...]
    revision: str


@dataclass(frozen=True)
class PopScreenProfile(ScreenProfile):
    relocation: float


def compile_screen(inputs,*,roles=('screener','navigator','coverage'),pop_routes=False):
    doc=inputs.to_dict();rows=doc['inputs']
    reader=common_reader(inputs,doc)
    if not isinstance(roles,tuple) or not roles or len(set(roles))!=len(roles) or not set(roles)<={'screener','navigator','coverage'}:raise ValueError('Explicit immutable screen participant roles required')
    required=set()
    for role in roles:
        required.update({'screener':('S27','S28','P01','P04','P05','P06','P08','P09','T11'),
            'navigator':('S35','S41','S44','P01','P04','P05','P06','P07','P08','P09'),
            'coverage':('S41','S44','P05','P06','P07')}[role])
    if type(pop_routes) is not bool or (pop_routes and 'screener' not in roles):raise ValueError('Pop route capability requires an explicit screener role')
    if pop_routes:required.add('S26')
    def value(key):
        r=rows.get(key)
        if r is None or r['status']=='unknown':raise ValueError(f'{key}: explicit screen/navigation dependency required')
        return r['value']
    def grade(key):
        if key not in required:return None
        if reader:return reader.grade(key)
        v=value(key)
        if v['scale']!=SKILL_SCALE:raise ValueError(f'{key}: unsupported screen technique scale')
        return v['grade']/100
    def measure(key,metric,unit):
        if key not in required:return None
        if reader:return reader.measurement(key)
        candidates=[m for m in value(key)['measurements'] if m['metric']==metric and m['unit']==unit and m['protocol']=='interior_scenario_reference_v1']
        if len(candidates)!=1 or candidates[0]['value']<=0:raise ValueError(f'{key}: positive {metric}/{unit} with explicit scenario protocol required')
        return candidates[0]['value']
    def capacity(key):
        if key not in required:return None
        if reader:return reader.capacity(key)
        v=value(key).get('display_grade')
        if v is None or v['scale']!=CAPACITY_SCALE:raise ValueError(f'{key}: explicit synthetic capacity scale required')
        return v['grade']/100
    preferences=()
    if 'screener' in roles:
        t=value('T11')
        if not reader and (len(t['rows'])!=1 or t['rows'][0]['condition']!='on_ball_screen'):raise ValueError('T11: declare one on_ball_screen condition')
        mix=reader.distribution('T11',**({'allow_pop':True} if pop_routes else {})) if reader else t['rows'][0]['probabilities']
        if not reader and mix['pop']!=0 and not pop_routes:raise ValueError('Pop routes deferred; do not rename a pop as F03')
        preferences=tuple(mix[k] for k in (('screen','roll','slip','pop') if pop_routes else ('screen','roll','slip')))
    data={'version':VERSION,'inputs':doc,'roles':roles}
    if pop_routes:data['route_policy']='screen_to_pop_v1'
    args=(inputs,doc['player_id'],*(grade(k) for k in ('S27','S28','S35','S41','S44')),
        measure('P01','height','cm'),measure('P04','body_mass','kg'),measure('P05','acceleration','m/s2'),measure('P06','straight_line_speed','m/s'),measure('P07','lateral_speed','m/s'),
        capacity('P08'),capacity('P09'),preferences,roles,
        fingerprint(interpretation_revision(data,inputs)))
    return PopScreenProfile(*args,grade('S26')) if pop_routes else ScreenProfile(*args)


@dataclass(frozen=True)
class ScreenCoefficients:
    placement_error_m: float=.65
    body_radius_intercept_m: float=.12
    body_radius_per_cm: float=.0007
    set_floor_s: float=.08
    set_skill_extra_s: float=.35
    read_floor_s: float=.05
    read_extra_s: float=.30
    contact_hold_s: float=.35
    release_floor_s: float=.06
    release_extra_s: float=.40
    receiving_approach_m: float=.65
    receiving_exit_m: float=.35

    def __post_init__(self):
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in asdict(self).values()):raise ValueError('Invalid screen response coefficient')
        if min(self.body_radius_intercept_m,self.receiving_approach_m,self.receiving_exit_m)<=0:raise ValueError('Positive obstacle/window geometry required')


@dataclass(frozen=True)
class ScreenCall:
    creator_id: str
    screener_id: str
    creator_start: tuple[float,float]
    screener_start: tuple[float,float]
    screen_position: tuple[float,float]
    guard_start: tuple[float,float]
    screener_defender_start: tuple[float,float]
    roll_end: tuple[float,float]
    coverage: str='show_then_recover'

    def __post_init__(self):
        if not self.creator_id or not self.screener_id or self.creator_id==self.screener_id:raise ValueError('Distinct creator and screener required')
        for point in (self.creator_start,self.screener_start,self.screen_position,self.guard_start,self.screener_defender_start,self.roll_end):
            if not isinstance(point,tuple) or len(point)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in point):raise ValueError('Immutable finite screen coordinates required')
        if self.coverage not in ('stay','show_then_recover'):raise ValueError('Unsupported supplied screen coverage policy')
        if math.dist(self.screen_position,self.roll_end)<.1:raise ValueError('A nonzero receiver route is required')


@dataclass(frozen=True,kw_only=True)
class PopScreenCall(ScreenCall):
    pop_end: tuple[float,float]
    action_call: str='preference'

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.pop_end,tuple) or len(self.pop_end)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in self.pop_end):raise ValueError('Finite immutable tactical pop destination required')
        if math.hypot(*self.pop_end)<6.7 or math.dist(self.screen_position,self.pop_end)<.1:raise ValueError('Pop must relocate to a perimeter destination')
        if self.action_call not in ('preference','screen','roll','slip','pop'):raise ValueError('Explicit supported tactical screen call required')


@dataclass(frozen=True)
class ScreenExperiment:
    profiles: tuple[ScreenProfile,...]
    calls: tuple[ScreenCall,...]
    coefficients: ScreenCoefficients=ScreenCoefficients()

    def __post_init__(self):
        if not isinstance(self.profiles,tuple) or not isinstance(self.calls,tuple):raise ValueError('Immutable screen configuration required')
        if len({p.player_id for p in self.profiles})!=len(self.profiles) or len({c.creator_id for c in self.calls})!=len(self.calls):raise ValueError('Duplicate screen profile/call')

    @property
    def revision(self):return fingerprint({'version':VERSION,'profiles':[(p.player_id,p.revision) for p in self.profiles],'calls':[asdict(c) for c in self.calls],'coefficients':asdict(self.coefficients)})


@dataclass(frozen=True)
class PopScreenExperiment(ScreenExperiment):
    timing_policy: str='bounded_wait_v1'

    def __post_init__(self):
        super().__post_init__()
        if self.timing_policy not in ('immediate_v1','bounded_wait_v1'):raise ValueError('Explicit bounded receiving timing policy required')
        if any(not isinstance(c,PopScreenCall) for c in self.calls):raise ValueError('Pop-capable experiment requires explicit tactical pop destinations')

    @property
    def revision(self):return fingerprint({'base':super().revision,'route_policy':'screen_to_pop_v1','timing_policy':self.timing_policy})


def prepare_screens(spec,state,pools):
    from .interior_defense import compile_profile
    if not isinstance(spec,ScreenExperiment):raise ValueError('Explicit ScreenExperiment required')
    if isinstance(spec,PopScreenExperiment) and state['spec'].choice_policy!='downstream_outcomes_v1':raise ValueError('Pop routes require the shared downstream outcome choice policy')
    profiles={p.player_id:p for p in spec.profiles};calls={c.creator_id:c for c in spec.calls};active=set(state['coupled']['team_for'])
    minutes={p['player']['id']:p['minutes'] for pool in pools.values() for p in pool}
    validated=set()
    for call in spec.calls:
        pop_enabled=isinstance(spec,PopScreenExperiment)
        if pop_enabled!=isinstance(profiles.get(call.screener_id),PopScreenProfile):raise ValueError('Screen route policy and compiled screener capability must agree')
        if isinstance(call,PopScreenCall) and not pop_enabled:raise ValueError('Pop call requires its explicit route experiment')
        participants=(call.creator_id,call.screener_id)
        if not set(participants)<=active:raise ValueError('Unavailable screen creator/screener')
        if state['coupled']['team_for'][call.creator_id]!=state['coupled']['team_for'][call.screener_id]:raise ValueError('Screen participants must be teammates')
        role_for=((call.screener_id,'screener'),(state['setups'][call.creator_id].defender_id,'navigator'),(state['setups'][call.screener_id].defender_id,'coverage'))
        required={pid for pid,role in role_for}
        if not required<=set(profiles) or not required<=active or any(minutes[pid]<=0 for pid in required|{call.creator_id}):raise ValueError('Unavailable screen participant or missing screen profile')
        if any(role not in profiles[pid].roles for pid,role in role_for):raise ValueError('Screen projection missing its required participant role')
        if state['setups'][call.creator_id].kick_receiver_id==call.screener_id:raise ValueError('Screen roller cannot also be the perimeter kick assignment')
        tid=state['coupled']['team_for'][state['setups'][call.screener_id].defender_id]
        anchor=state['anchors'][tid]
        if anchor and anchor.profile.inputs.player_id==state['setups'][call.screener_id].defender_id:raise ValueError('Bounded screen coverage requires a separate configured helper and roller defender')
        for pid in required:
            # Profiles/snapshots are immutable and the counterpart is fixed for
            # this preparation. Revalidate each actor once, while keeping all
            # per-call ownership/availability/role checks above. No global cache.
            if pid in validated:continue
            if not same_input_snapshot(profiles[pid].inputs,state['profiles'][pid].inputs):raise ValueError('Screen/creation must share one authoritative input snapshot and interpretation')
            if profiles[pid]!=compile_screen(profiles[pid].inputs,roles=profiles[pid].roles,**({'pop_routes':True} if isinstance(profiles[pid],PopScreenProfile) else {})):raise ValueError('Stale or mutated compiled screen projection')
            validated.add(pid)
    defenders={call.screener_id:state['setups'][call.screener_id].defender_id for call in spec.calls}
    interior_profiles={pid:compile_profile(profiles[pid].inputs) for pid in set(defenders.values())}
    if any(p.wingspan_cm is None or p.wingspan_cm<=0 for p in interior_profiles.values()):raise ValueError('P02: explicit supported wingspan required for roller contests')
    return {'spec':spec,'profiles':profiles,'calls':calls,'roller_defenders':defenders,
        'interior_profiles':interior_profiles}


def distance_time(distance,profile,*,lateral=False):
    return motion_time(distance,profile.acceleration,min(profile.speed,profile.lateral) if lateral else profile.speed)


def point_at(start,end,time,delay,profile,*,lateral=False,extra_m=0):
    speed=min(profile.speed,profile.lateral) if lateral else profile.speed
    dt=max(0,time-delay);a=profile.acceleration
    travelled=.5*a*dt*dt if dt<=speed/a else speed*(dt-speed/(2*a))
    distance=math.dist(start,end);fraction=min(distance+extra_m,travelled)/max(distance,1e-9)
    return tuple(start[i]+fraction*(end[i]-start[i]) for i in (0,1))


def receiver_position(response,time,profile):
    return point_at(response['receiver_start'],response.get('receiver_end',response['roll_end']),time,response['release_s'],profile,extra_m=response['receiving_exit_m'])


def coverage_position(response,time,profile):
    return point_at(response['coverage_release_position'],response.get('receiver_end',response['roll_end']),time,response['coverage_release_s'],profile,lateral=True)


def resolve_screen(screen_state,creator,setup,draws):
    call=screen_state['calls'].get(creator.player_id)
    if call is None:return {'kind':'none','reason':'no_screen_call','version':VERSION}
    profiles=screen_state['profiles'];c=screen_state['spec'].coefficients
    screener=profiles[call.screener_id];guard=profiles[setup.defender_id]
    # The screener's defender is recorded by preparation from current matchups.
    roll_defender=profiles[screen_state['roller_defenders'][call.screener_id]]
    preferred='slip';draw=draws[39]
    pop_enabled=isinstance(screen_state['spec'],PopScreenExperiment)
    for name,weight in zip(('screen','roll','slip','pop') if pop_enabled else ('screen','roll','slip'),screener.preferences,strict=True):
        draw-=weight
        if draw<0:preferred=name;break
    recognized=draws[40]<.05+.90*screener.read
    intent=call.action_call if pop_enabled and call.action_call!='preference' else preferred
    route='screen' if intent=='pop' and not recognized else 'roll' if intent=='slip' and not recognized else intent
    destination=(setup.drive_x_m,setup.drive_y_m)
    dx,dy=destination[0]-call.guard_start[0],destination[1]-call.guard_start[1];length=max(1e-9,math.hypot(dx,dy))
    normal=(-dy/length,dx/length)
    side=1 if call.creator_start[0]>=0 else -1
    error=side*c.placement_error_m*(1-screener.screen)*(2*draws[41]-1) if route!='slip' else 0
    placement=tuple(call.screen_position[i]+normal[i]*error for i in (0,1))
    radius=c.body_radius_intercept_m+c.body_radius_per_cm*screener.height_cm
    guard_radius=c.body_radius_intercept_m+c.body_radius_per_cm*guard.height_cm
    projection=clamp(((placement[0]-call.guard_start[0])*dx+(placement[1]-call.guard_start[1])*dy)/(length*length))
    nearest=tuple(call.guard_start[i]+projection*(destination[i]-call.guard_start[i]) for i in (0,1))
    clearance=math.dist(placement,nearest);planned_overlap=clamp(1-clearance/(radius+guard_radius*.5)) if route!='slip' else 0
    set_s=distance_time(math.dist(call.screener_start,placement),screener)+c.set_floor_s+c.set_skill_extra_s*(1-screener.screen)
    recognition=c.read_floor_s+c.read_extra_s*(1-guard.anticipation*guard.attention)
    contact_s=distance_time(math.dist(call.guard_start,nearest),guard,lateral=True)+recognition
    body_at_contact=point_at(call.screener_start,placement,contact_s,0,screener)
    overlap=clamp(1-math.dist(body_at_contact,nearest)/(radius+guard_radius*.5)) if route!='slip' else 0
    late=clamp((set_s-contact_s)/max(set_s,.001))
    illegal_probability=overlap*(.015*(1-screener.screen)+late*(.30+.60*(1-screener.screen)))
    illegal=route!='slip' and draws[42]<illegal_probability
    stability=.5+.25*screener.strength+.25*screener.balance
    resistance=.5+.25*guard.strength+.25*guard.balance
    hold=c.contact_hold_s*overlap*screener.screen*math.sqrt(screener.mass_kg/guard.mass_kg)*stability/resistance*(1-.6*guard.navigation)*(1-late)
    detour=2*(radius+guard_radius*.5)*overlap*(1-.75*guard.navigation)*(1-late)
    nav_delay=hold+detour/min(guard.speed,guard.lateral)
    dribble_factor=1+.35*(1-creator.skill('S16'))+.25*(1-creator.skill('S19'))
    clear=motion_time(math.dist(call.creator_start,call.screen_position)+math.dist(call.screen_position,destination),creator.acceleration_m_s2,creator.speed_m_s)*dribble_factor
    guard_arrival=distance_time(math.dist(call.guard_start,destination),guard,lateral=True)+recognition+nav_delay
    release=(0 if route=='slip' else max(contact_s,set_s))+c.release_floor_s+c.release_extra_s*(1-screener.read)
    receiver_start=call.screener_start if route=='slip' else placement
    receiver_end=call.pop_end if route=='pop' else call.roll_end
    exit_m=0 if route=='pop' else c.receiving_exit_m
    relocation_delay=.30*(1-screener.relocation)+.20*(1-screener.balance) if route=='pop' else 0
    release+=relocation_delay
    route_distance=math.dist(receiver_start,receiver_end)
    window_start=release+distance_time(route_distance if route=='pop' else max(0,route_distance-c.receiving_approach_m),screener)
    route_end_s=release+distance_time(route_distance+exit_m,screener)
    cover_delay=c.read_floor_s+c.read_extra_s*(1-roll_defender.anticipation*roll_defender.attention)
    coverage_release_s=cover_delay
    coverage_release_position=call.screener_defender_start
    if call.coverage=='show_then_recover':
        # Supplied show policy: pursue handler until it reaches the screen,
        # then recognize/recover. Duration follows the handler's actual travel.
        show_until=motion_time(math.dist(call.creator_start,call.screen_position),creator.acceleration_m_s2,creator.speed_m_s)*dribble_factor
        coverage_release_position=point_at(call.screener_defender_start,call.screen_position,show_until,0,roll_defender,lateral=True)
        coverage_release_s=show_until+cover_delay
    # Receiver can present at the route endpoint until its defender recovers.
    # A stay defender may close before the receiver arrives: no gifted window.
    catch_end=point_at(receiver_start,receiver_end,route_end_s,release,screener,extra_m=exit_m)
    window_end=coverage_release_s+distance_time(math.dist(coverage_release_position,catch_end),roll_defender,lateral=True)
    result={'kind':'illegal_screen' if illegal else 'screen','version':VERSION,'screener_id':screener.player_id,'roller_defender_id':roll_defender.player_id,
        'preferred':preferred,'recognized':recognized,'route':route,'placement_m':placement,'placement_error_m':abs(error),'obstacle_radius_m':radius,
        'planned_contact_overlap':planned_overlap,'body_position_at_contact_m':body_at_contact,'contact_overlap':overlap,
        'set_s':set_s,'contact_s':contact_s,'illegal_probability':illegal_probability,'contact_hold_s':hold,'navigation_detour_m':detour,'navigation_delay_s':nav_delay,
        'guard_recognition_s':recognition,'guard_arrival_s':guard_arrival,'attacker_clear_s':clear,'release_s':release,'receiver_start':receiver_start,'roll_end':call.roll_end,
        'window_start_s':window_start,'window_end_s':window_end,'receiver_route_end_s':route_end_s,'receiving_exit_m':exit_m,'coverage_policy':call.coverage,
        'coverage_release_s':coverage_release_s,'coverage_release_position':coverage_release_position,'coverage_start':call.screener_defender_start,
        'source_revisions':[creator.revision,screener.revision,guard.revision,roll_defender.revision],
        'remaining_controls':['coaching call','initial coordinates','coverage policy','route endpoint','partial action set']}
    if pop_enabled:result.update(route_policy='screen_to_pop_v1',timing_policy=screen_state['spec'].timing_policy,called_action=call.action_call,
        effective_intent=intent,receiver_end=receiver_end,pop_end=call.pop_end,relocation_delay_s=relocation_delay,
        read_failure='hold_screen_no_pop' if intent=='pop' and not recognized else None)
    return result
