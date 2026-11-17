"""Opt-in poor-delivery recovery; bounded hypotheses, not calibrated tracking.

Accepted clean windows retain their existing meaning. For misses of that
window only, the radial error is oriented along/against/across the pass or
vertically, then a short ballistic continuation and receiver/defender race are
evaluated. All six axes are an explicit finite prior, not observed frequencies.
"""
from dataclasses import dataclass,asdict,fields,replace,field
import math

from .creation_passing import CreationExperiment,DriveSetup,CHOICE_POLICY,motion_time
from .experimental_inputs import common_reader,ALIASES
from .interior_defense import clamp,fingerprint
from .offense_response import ActionShotContext

POLICY='poor_receipt_recovery_v1'
DIRECTIONS=('over','short','left','right','high','low')


@dataclass(frozen=True)
class RecoveryCoefficients:
    horizon_s: float=.65
    reaction_s: float=.14  # explicit timing control; not another S14 time bonus
    horizontal_reach_fraction: float=.60  # fraction of half-span, not extra size
    residual_velocity_fraction: float=.25
    downward_velocity_m_s: float=-1.0
    gravity_m_s2: float=9.81
    minimum_ball_height_m: float=.20
    normal_height_m: float=1.50
    pocket_height_m: float=1.15
    lob_height_m: float=3.10
    gather_s: float=.15
    balance_settle_s: float=.10
    jump_takeoff_s: float=.12
    court_half_width_m: float=7.5
    court_back_y_m: float=-1.5
    court_front_y_m: float=12.5
    search_steps: int=16
    search_bisections: int=10
    integration_panels: int=4

    def __post_init__(self):
        for f in fields(self):
            v=getattr(self,f.name)
            if f.name in ('search_steps','search_bisections','integration_panels'):
                if type(v) is not int or not 1<=v<=32:raise ValueError('Bounded positive integer recovery resolution required')
            elif type(v) not in (int,float) or not math.isfinite(v):raise ValueError('Finite recovery geometry required')
        if min(self.horizon_s,self.gravity_m_s2,self.court_half_width_m,self.minimum_ball_height_m)<=0 or self.court_back_y_m>=self.court_front_y_m:raise ValueError('Positive recovery horizons/geometry required')
        if not 0<self.horizontal_reach_fraction<=1 or not 0<=self.residual_velocity_fraction<=1:raise ValueError('Bounded reach/velocity fraction required')
        if min(self.reaction_s,self.gather_s,self.balance_settle_s,self.jump_takeoff_s)<0:raise ValueError('Nonnegative reaction/preparation required')


@dataclass(frozen=True)
class RecoveryCreationExperiment(CreationExperiment):
    recovery: RecoveryCoefficients=RecoveryCoefficients()
    projection_backend: str='compact_python_v1'
    bearing_policy: str='legacy_bearing_v1'
    geometry_provider: object=field(default=None,repr=False,compare=False)

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.recovery,RecoveryCoefficients):raise ValueError('Explicit immutable recovery coefficients required')
        if self.choice_policy!=CHOICE_POLICY:raise ValueError('Recovery requires shared downstream outcome choices')
        if self.projection_backend not in ('compact_python_v1','detailed_python_v1'):raise ValueError('Explicit supported recovery evaluator required')
        if self.bearing_policy not in ('legacy_bearing_v1','stable_route_bearing_v2'):raise ValueError('Explicit supported action bearing policy required')
        if self.geometry_provider is not None:
            if self.projection_backend!='compact_python_v1' or not callable(self.geometry_provider) or not isinstance(getattr(self.geometry_provider,'revision',None),str) or not self.geometry_provider.revision:raise ValueError('Named geometry provider requires scoped compact evaluator')
            if getattr(self.geometry_provider,'required_bearing_policy',self.bearing_policy)!=self.bearing_policy:raise ValueError('Geometry provider requires its declared bearing model')

    @property
    def receipt_policy(self):return POLICY

    @property
    def revision(self):
        data={'base':super().revision,'receipt_policy':POLICY,'recovery':asdict(self.recovery),
            'draw_schema':'existing48:34 radial,44 six-axis direction,15 actual securing;43 retained wait hazard'}
        # Computation backend is separately reported; only the named model
        # revision changes the physical configuration fingerprint.
        if self.bearing_policy!='legacy_bearing_v1':data['bearing_policy']=self.bearing_policy
        return fingerprint(data)


@dataclass(frozen=True)
class RecoveryDriveSetup(DriveSetup):
    origin_x_m: float=0.0
    origin_y_m: float=0.0
    defender_x_m: float=0.0
    defender_y_m: float=0.0


@dataclass(frozen=True)
class RecoveredShotContext(ActionShotContext):
    @property
    def recovered_receipt(self):return True


def recovery_containment(attacker,defender,setup,c):
    origin=(setup.origin_x_m,setup.origin_y_m);target=(setup.drive_x_m,setup.drive_y_m);start=(setup.defender_x_m,setup.defender_y_m)
    clear=motion_time(max(.9,math.dist(origin,target)),attacker.acceleration_m_s2,attacker.speed_m_s)*(1+.35*(1-attacker.skill('S16'))+.25*(1-attacker.skill('S19')))
    recovery=motion_time(math.dist(start,target),defender.acceleration_m_s2,min(defender.speed_m_s,defender.lateral_m_s))+.20*(1-defender.skill('S41'))+.12*(1-defender.skill('S33'))+.08*(1-defender.skill('S34'))
    z=clamp((recovery-clear)/c.beat_transition_s,-20,20);beat=.05+.90/(1+math.exp(-z));pressure=clamp(1-beat)
    from .creation_passing import handling_loss,_point_on_path
    return {'beat_probability':beat,'handling_loss_probability':handling_loss(attacker,pressure,clear,c),'attacker_clear_s':clear,'defender_recovery_s':recovery,
        'pressure':pressure,'source_revisions':[attacker.revision,defender.revision],'actual_continuation_origin_m':origin,'ball_endpoint_m':target,
        'defender_origin_m':start,'defender_position_at_decision_m':_point_on_path(start,target,clear,0,defender),'continuation_policy':POLICY}


def prepare_receiving(state):
    """P02 is an explicit new receiving geometry dependency; never infer it."""
    spans={}
    for pid,p in state['profiles'].items():
        reader=common_reader(p.inputs)
        if reader:value=reader.measurement('P02')
        else:
            row=p.inputs.to_dict()['inputs']['P02']
            if row['status']=='unknown':raise ValueError('P02: recovery requires explicit wingspan, not a role penalty')
            measures=row['value']['measurements']
            if len(measures)!=1 or (measures[0]['metric'],measures[0]['unit'],measures[0]['protocol']) not in ALIASES['P02']:raise ValueError('P02: declared recovery reach quantity required')
            value=measures[0]['value']
        if value<=0:raise ValueError('P02: positive recovery reach required')
        spans[pid]=value/100
    state['receiving_spans_m']=spans;state['recovery_count']=0


def inside(point,c):return -c.court_half_width_m<=point[0]<=c.court_half_width_m and c.court_back_y_m<=point[1]<=c.court_front_y_m


def axis(frame,option,direction):
    dx=option['target'][0]-frame['ball'][0];dy=option['target'][1]-frame['ball'][1];length=math.hypot(dx,dy)
    forward=(dx/length,dy/length,0) if length else (0,1,0)
    return (forward,tuple(-v for v in forward),(-forward[1],forward[0],0),(forward[1],-forward[0],0),(0,0,1),(0,0,-1))[direction]


def receiving_positions(frame,choice,option):
    from .screen_navigation import receiver_position,coverage_position
    from .creation_passing import _point_on_path
    state=frame['state'];rid=option['receiver_id'];did=state['setups'][rid].defender_id
    t=frame['elapsed']+option.get('wait_s',0)+option['delivery']['flight_s']+.05
    if frame['screen'] and choice in ('F03','F04','pop'):
        receiver=receiver_position(frame['screen'],t,state['screens']['profiles'][rid])
        defender=coverage_position(frame['screen'],t,state['screens']['profiles'][did])
    else:
        receiver=option['target'];defender=option['coverage_position']
        # A committed helper is already moving away from the fixed outlet.
        if frame['helper'] and did==frame['helper'].player_id and frame['helped']['committed']:
            helper=frame['helper'];extra=.6*(1-helper.skill('S39'))
            defender=_point_on_path(frame['start'],frame['ball'],t,frame['helped']['recognition_delay_s'],helper,route_extra_m=extra)
        else:
            defender=_point_on_path(defender,option['target'],option['delivery']['flight_s']+.05,0,state['profiles'][did])
    return receiver,defender,did


def geometry_basis(frame,choice,option):
    """One candidate snapshot; never attached to possession/config/global state.

    Its owner is a single project_candidate call. A new time, route, creator,
    defender or continuation therefore necessarily builds a fresh basis.
    """
    c=frame['spec'].recovery;state=frame['state'];rid=option['receiver_id'];p=frame['coupled']['profiles'][rid];m=state['profiles'][rid]
    receiver,defender,did=receiving_positions(frame,choice,option);d=state['profiles'][did];body=frame['coupled']['profiles'][did]
    return {'receiver':receiver,'defender':defender,'did':did,'rid':rid,'m':m,'d':d,
        'axes':tuple(axis(frame,option,i) for i in range(6)),
        'height':c.lob_height_m if choice=='F04' else c.pocket_height_m if choice=='F03' else c.normal_height_m,
        'vx':(option['target'][0]-frame['ball'][0])/max(1e-9,option['delivery']['flight_s'])*c.residual_velocity_fraction,
        'vy':(option['target'][1]-frame['ball'][1])/max(1e-9,option['delivery']['flight_s'])*c.residual_velocity_fraction,
        'standing':p.standing_reach_cm/100,'jump':p.jump_cm/100,
        'half_span':state['receiving_spans_m'][rid]/2*c.horizontal_reach_fraction,
        'speed':min(m.speed_m_s,m.lateral_m_s),'defender_speed':min(d.speed_m_s,d.lateral_m_s),
        'defender_reaction':.08+.25*(1-d.skill('S41')*d.skill('S44')),
        'defender_standing':body.standing_reach_cm/100,'defender_jump':body.jump_cm/100,
        'gather':c.gather_s+c.balance_settle_s*(1-p.balance)}


def horizontal_unreachable(receiver,point,vx,vy,horizon,reaction,span,acceleration,speed):
    """Conservative lower bound, not an approximate capture decision.

    Every searched ball xy lies in its swept bounding rectangle. Distance to
    that rectangle is <= distance to every trajectory point. Ignore vertical
    constraints/takeoff and grant full span plus the entire horizon to travel:
    if even this optimistic case fails, all original samples fail. Padding
    expands the rectangle/lifetime to keep roundoff away from a hard boundary.
    Survivors still run the unchanged search; false negatives only cost work.
    """
    end=(point[0]+vx*horizon,point[1]+vy*horizon)
    padding=1e-9*max(1,abs(receiver[0]),abs(receiver[1]),abs(point[0]),abs(point[1]),abs(end[0]),abs(end[1]))
    dx=max(0,min(point[0],end[0])-receiver[0],receiver[0]-max(point[0],end[0]))
    dy=max(0,min(point[1],end[1])-receiver[1],receiver[1]-max(point[1],end[1]))
    travel=max(0,math.hypot(dx,dy)-span-3*padding)
    return reaction+motion_time(travel,acceleration,speed)>horizon+1e-9*max(1,abs(horizon))


def projection_plan_evaluator(owner):
    """Exact compact-plan memo scoped to one candidate, with immutable keys.

    Only draws16..19 enter plan_attack. Coupled snapshot ownership is explicit;
    every action/context/anchor input is keyed. Return a fresh outer plan since
    the resolver attaches its selected contest fields. Nested offense/response
    values are read-only in that resolver and the angular integrator.
    """
    from .offense_response import plan_attack
    cache={}
    def evaluate_plan(state,pid,zone,draws,defending_team,anchor,context,*,outlet=False,action_context=None,include_details=True):
        if state is not owner:raise ValueError('Projection plan belongs to a different coupled snapshot')
        if include_details:return plan_attack(state,pid,zone,draws,defending_team,anchor,context,outlet=outlet,action_context=action_context)
        key=(pid,zone,tuple(draws[16:20]),defending_team,id(anchor.profile) if anchor else None,context,outlet,action_context)
        plan=cache.get(key)
        if plan is None:
            plan=plan_attack(state,pid,zone,draws,defending_team,anchor,context,outlet=outlet,action_context=action_context,include_details=False);cache[key]=plan
        return dict(plan)
    return evaluate_plan


def max_error(frame,choice,option,direction):
    c=frame['spec'].recovery;vector=axis(frame,option,direction);target=option['target'];rid=option['receiver_id'];p=frame['coupled']['profiles'][rid]
    height=c.lob_height_m if choice=='F04' else c.pocket_height_m if choice=='F03' else c.normal_height_m
    if vector[2]<0:return max(0,height-c.minimum_ball_height_m)
    if vector[2]>0:return max(0,(p.standing_reach_cm+p.jump_cm)/100-height-c.downward_velocity_m_s*c.horizon_s+.5*c.gravity_m_s2*c.horizon_s**2)
    limits=[]
    for pos,v,low,high in ((target[0],vector[0],-c.court_half_width_m,c.court_half_width_m),(target[1],vector[1],c.court_back_y_m,c.court_front_y_m)):
        if v>1e-12:limits.append((high-pos)/v)
        elif v<-1e-12:limits.append((low-pos)/v)
    return max(0,min(limits))


def recovery_geometry(frame,choice,option,error,direction):
    """First feasible capture along a moving ball; no bounce/rotation planner."""
    from .creation_passing import _point_on_path
    c=frame['spec'].recovery;state=frame['state'];b=frame.get('_recovery_geometry_basis')
    if b is None:b=geometry_basis(frame,choice,option)
    rid=b['rid'];m=b['m'];receiver=b['receiver'];defender=b['defender'];did=b['did'];d=b['d'];vector=b['axes'][direction]
    z0=b['height']+error*vector[2]
    point=(option['target'][0]+error*vector[0],option['target'][1]+error*vector[1])
    base={'direction':DIRECTIONS[direction],'endpoint_m':(*point,z0),'receiver_at_nominal_receipt_m':receiver,'defender_at_nominal_receipt_m':defender,
        'clean_window_was_missed':True,'receiver_id':rid,'defender_id':did,'capture_s':None}
    if not inside(point,c):return {**base,'lost':'pass_out_of_bounds','delay_s':.05}
    if z0<c.minimum_ball_height_m:return {**base,'lost':'pass_grounded','delay_s':.05}
    vx=b['vx'];vy=b['vy']
    floor=(c.downward_velocity_m_s+math.sqrt(c.downward_velocity_m_s**2+2*c.gravity_m_s2*(z0-c.minimum_ball_height_m)))/c.gravity_m_s2
    horizon=min(c.horizon_s,floor);exit_time=float('inf')
    for pos,v,low,high in ((point[0],vx,-c.court_half_width_m,c.court_half_width_m),(point[1],vy,c.court_back_y_m,c.court_front_y_m)):
        if v>0:exit_time=min(exit_time,(high-pos)/v)
        elif v<0:exit_time=min(exit_time,(low-pos)/v)
    horizon=min(horizon,exit_time)
    reaction=c.reaction_s
    standing=b['standing'];jump=b['jump'];half_span=b['half_span'];speed=b['speed']
    def candidate(t):
        ball=(point[0]+vx*t,point[1]+vy*t,z0+c.downward_velocity_m_s*t-.5*c.gravity_m_s2*t*t)
        if ball[2]<c.minimum_ball_height_m or ball[2]>standing+jump or not inside(ball,c):return None
        if ball[2]<=standing:vertical=0.0;reach=half_span
        else:
            vertical=max(0,ball[2]-standing)/max(jump,1e-9)
            reach=half_span*math.sqrt(max(0,1-vertical*vertical))
        distance=math.dist(receiver,ball[:2]);travel=max(0,distance-reach)
        if reaction+c.jump_takeoff_s*vertical+motion_time(travel,m.acceleration_m_s2,speed)>t:return None
        fraction=travel/max(1e-9,distance);feet=tuple(receiver[i]+fraction*(ball[i]-receiver[i]) for i in (0,1))
        if not inside(feet,c):return None
        return ball,feet,travel,reach
    left=reaction;found=None;capture=None
    if horizon>=reaction and not horizontal_unreachable(receiver,point,vx,vy,horizon,reaction,half_span,m.acceleration_m_s2,speed):
        for step in range(c.search_steps+1):
            t=reaction+(horizon-reaction)*step/c.search_steps
            value=candidate(t)
            if value is not None:
                right=t
                for _ in range(c.search_bisections):
                    mid=(left+right)/2
                    if candidate(mid) is None:left=mid
                    else:right=mid
                capture=right;found=candidate(capture) or value;break
            left=t
    if found is None:
        reason='pass_out_of_bounds' if exit_time<=min(c.horizon_s,floor) else 'pass_grounded' if floor<c.horizon_s else 'pass_unreachable'
        return {**base,'lost':reason,'delay_s':.05+max(0,horizon),'searched_horizon_s':horizon}
    ball,feet,travel,reach=found
    defender_reaction=b['defender_reaction'];defender_standing=b['defender_standing'];defender_jump=b['defender_jump']
    defender_vertical=max(0,ball[2]-defender_standing)/max(1e-9,defender_jump)
    defender_reach=state['receiving_spans_m'][did]/2*c.horizontal_reach_fraction*math.sqrt(max(0,1-defender_vertical**2))
    defender_time=None if ball[2]>defender_standing+defender_jump else defender_reaction+c.jump_takeoff_s*defender_vertical+motion_time(max(0,math.dist(defender,ball[:2])-defender_reach),d.acceleration_m_s2,b['defender_speed'])
    if defender_time is not None and defender_time<=capture:
        return {**base,'lost':'recovery_defended','delay_s':.05+defender_time,'capture_s':capture,'defender_arrival_s':defender_time}
    gather=b['gather']
    required_jump=max(0,ball[2]-standing);landing=math.sqrt(2*required_jump/c.gravity_m_s2)
    delay=max(.05+error*.25,.05+capture)+landing+gather
    defender_at_control=_point_on_path(defender,feet,delay-.05,defender_reaction,d)
    return {**base,'lost':None,'delay_s':delay,'capture_s':capture,'ball_at_capture_m':ball,'receiver_feet_m':feet,'receiver_travel_m':travel,
        'horizontal_reach_m':reach,'reaction_s':reaction,'defender_arrival_s':defender_time,'defender_position_m':defender_at_control,
        'gather_s':gather,'required_jump_m':required_jump,'landing_s':landing,'feet_meaning':'ground projection; jump landing time paid before next action','searched_horizon_s':horizon}


def delivery(frame,choice,option,error,direction):
    from .creation_passing import prepare_delivery,delivery_at_error
    original=prepare_delivery(frame,choice,option,error)
    c=frame['spec'].recovery
    if original['outcome'] is None and inside(original['target'],c):
        original['extra'].update(receipt_category='clean',receipt_policy=POLICY,delivery_plan_complete=True,actual_receipt_secured=None)
        return original
    geometry=recovery_geometry(frame,choice,option,error,direction)
    return delivery_from_geometry(frame,choice,option,error,original,geometry)


def delivery_from_geometry(frame,choice,option,error,original,geometry):
    """Shared post-geometry receipt semantics for detailed/numeric adapters."""
    c=frame['spec'].recovery
    passed=original['passed'];extra={'receipt_category':'lost' if geometry['lost'] else 'recovered','receipt_policy':POLICY,
        'delivery_plan_complete':not bool(geometry['lost']),'actual_receipt_secured':None,'recovery_geometry':geometry}
    result={'outcome':geometry['lost'],'passed':passed,'extra':extra,'quality':.5,'target':geometry.get('receiver_feet_m',option['target']),
        'flight_s':option['delivery']['flight_s'],'catch_delay_s':geometry['delay_s']}
    if geometry['lost']:return result
    # Original lob/dunk execution is lost; a grounded feasible finish or an
    # actually located jumper uses its own existing execution response once.
    distance=math.hypot(*result['target']);deadline=frame['screen']['window_end_s'] if frame['screen'] and choice in ('F03','F04','pop') else frame['setup'].roll_window_s if choice in ('F03','F04') else float('inf')
    expired=frame['elapsed']+option.get('wait_s',0)+result['flight_s']+result['catch_delay_s']>=deadline
    if expired or (choice in ('F03','F04') and distance>3.5):result['recovery_reset']=True
    elif choice in ('F06','pop'):
        result.update(zone_override='perimeter' if distance>=6.7 else 'short_paint',finish_override=None if distance>=6.7 else 'midrange')
    else:result.update(zone_override='rim' if distance<=1.6 else 'short_paint',finish_override='layup' if distance<=1.6 else 'floater')
    return result


def complete_receipt(action,draw,remaining):
    """Actual securing gate once, after choice; projector never samples it."""
    if action.get('receipt_finalized'):return action
    probability=action.get('receipt_probability')
    if probability is None:return action
    record=action['record']
    if action['elapsed_s']>=remaining:
        record.update(actual_receipt_secured=None,receipt_state='unresolved_before_whole_action_clock',completed_pass=False)
        record.get('pass',{}).update(actual_receipt_secured=None);action['receipt_finalized']=True;return action
    secured=draw<probability;record.update(actual_receipt_secured=secured,completed_pass=secured,receipt_state='secured' if secured else 'failed_catch')
    record.get('pass',{}).update(actual_receipt_secured=secured)
    if not secured:
        return {'kind':'turnover','outcome':'failed_catch','responsible':record['receiver_id'],'steal_by':None,'record':record,'elapsed_s':action['elapsed_s'],'receipt_finalized':True}
    if action['kind']=='shot':action['plan']['reception']=1.0
    action['receipt_finalized']=True
    return action


def reset_action(frame,choice,option,delivered,record,elapsed):
    rid=option['receiver_id'];p=frame['coupled']['profiles'][rid];g=delivered['extra']['recovery_geometry'];time=elapsed+delivered['flight_s']+delivered['catch_delay_s']+frame['spec'].reset_cost_s
    record.update(delivered['extra'],planned_pass_complete=True,completed_pass=False,receiver_id=rid,receipt_state='planned_recovered_reset')
    from .creation_passing import _point_on_path
    helper_position=frame['helper_position'];helper=frame['helper']
    if helper and frame['helped']['committed']:helper_position=_point_on_path(helper_position,delivered['target'],delivered['flight_s']+delivered['catch_delay_s'],frame['c'].recovery_delay_s,helper)
    return {'kind':'reset','reason':'recovered_ball_original_opportunity_lost','record':record,'elapsed_s':time,
        'receipt_probability':.5*(.5+.5*p.skill(14)),'continuation_creator_id':rid,
        'recovery_continuation':{'receiver_id':rid,'ball_position_m':delivered['target'],'defender_id':g['defender_id'],
            'defender_position_m':g['defender_position_m'],'defender_extra_time_s':frame['spec'].reset_cost_s,
            'defending_team':frame['opponent_id'],'helper_position_m':helper_position,'helper_moving':bool(helper and frame['helped']['committed']),'elapsed_s':time}}


def apply_continuation(state,payload):
    """Scoped possession state only; source/config snapshots never mutate."""
    from .creation_passing import _point_on_path
    rid=payload['receiver_id'];setup=state['setups'][rid];d=state['profiles'][payload['defender_id']];ball=payload['ball_position_m']
    defender=_point_on_path(payload['defender_position_m'],ball,payload['defender_extra_time_s'],0,d)
    new={**state,'setups':dict(state['setups']),'coupled':{**state['coupled'],'positions':dict(state['coupled']['positions'])},'recovery_count':state.get('recovery_count',0)+1}
    new['setups'][rid]=RecoveryDriveSetup(**asdict(setup),origin_x_m=ball[0],origin_y_m=ball[1],defender_x_m=defender[0],defender_y_m=defender[1]) if not isinstance(setup,RecoveryDriveSetup) else replace(setup,origin_x_m=ball[0],origin_y_m=ball[1],defender_x_m=defender[0],defender_y_m=defender[1])
    helper=state['anchors'].get(payload['defending_team'])
    if helper and payload.get('helper_moving',True):
        hp=state['profiles'][helper.profile.inputs.player_id]
        new['coupled']['positions'][payload['defending_team']]=_point_on_path(payload['helper_position_m'],ball,payload['defender_extra_time_s'],0,hp)
    return new


def advance_after_reset(state,action,creator_id):
    setup=state['setups'][creator_id]
    if not isinstance(setup,RecoveryDriveSetup):return state
    team=state['coupled']['team_for'][setup.defender_id];target=(setup.drive_x_m,setup.drive_y_m)
    return apply_continuation(state,{'receiver_id':creator_id,'ball_position_m':target,'defender_id':setup.defender_id,
        'defender_position_m':(setup.defender_x_m,setup.defender_y_m),'defender_extra_time_s':action['elapsed_s'],
        'defending_team':team,'helper_position_m':state['coupled']['positions'][team],'helper_moving':bool(action['record'].get('help',{}).get('committed'))})


def project_candidate(frame,name,options,*,order=4,node_resolver=None):
    """Fixed quadrature over the accepted clean channel and six poor axes.

    Retained resets score0 at this first event; their actual continuation is
    charged/simulated by the event kernel. No recursive future planner or
    uncalibrated possession-value bonus is added.
    """
    from .action_choice import G4,G8,_cdf,_empty,_failure,_shot,_late_interval,_clock_interval
    from .creation_passing import resolve_candidate
    if node_resolver is not None:resolve_candidate=node_resolver
    from .shot_geometry import contest_at_angle
    if order not in (4,8):raise ValueError('Bounded quadrature order4/8 required')
    option=options[name];frame={**frame,'_recovery_geometry_basis':geometry_basis(frame,name,option),
        '_recovery_plan_evaluator':projection_plan_evaluator(frame['coupled'])}
    c=frame['spec'].recovery;result=_empty();nodes=G4 if order==4 else G8;draws=[.5]*48;draws[43]=1.0
    result.update(recovery_geometry_evaluations=0,receipt_planned_probabilities={'clean':0.0,'recovered':0.0,'lost':0.0,'not_launched':0.0},
        secured_receipt_probability=0.0,retained_reset_probability=0.0)
    wait=option.get('wait_s',0);loss=option.get('waiting_loss_probability',0) if wait else 0;survival=1-loss
    if loss:
        _failure(result,'shot_clock_turnover' if frame['elapsed']+wait>=frame['remaining_s'] else 'waiting_loss',loss)
        result['receipt_planned_probabilities']['not_launched']+=loss
    def evaluate(action,mass,category):
        mass*=survival;result['receipt_planned_probabilities'][category]+=mass
        if action['elapsed_s']>=frame['remaining_s']:_failure(result,'shot_clock_turnover',mass);return
        if action['kind']=='turnover':_failure(result,action['outcome'],mass);return
        reception=action.get('receipt_probability',action.get('plan',{}).get('reception',1))
        result['secured_receipt_probability']+=mass*reception
        if action['kind']=='reset':
            _failure(result,'failed_catch',mass*(1-reception));_failure(result,'recovery_reset',mass*reception)
            result['retained_reset_probability']+=mass*reception;return
        plan=action['plan'];result['shot_plan_evaluations']+=3 if frame['screen'] and name in ('F03','F04') else 1
        angles=nodes if plan['zone']!='perimeter' and (plan['response'] or plan.get('_projection_contests')) else ((.5,1.0),)
        for angle,weight in angles:
            responses=plan.get('_projection_contests',(plan['response'],));chosen=None;strength=-1
            for response in responses:
                rotated=contest_at_angle(response['_contest_basis'],angle*180) if response else None
                value=rotated['conversion_reduction']+rotated['block_probability'] if rotated else 0
                if value>=strength:chosen=rotated;strength=value
            _shot(result,{**action,'plan':{**plan,'response':chosen}},mass*weight);result['angle_evaluations']+=1
    def resolve(error,direction,legacy=False):
        draws[44]=(direction+.5)/6
        f={**frame,'_legacy_delivery':True} if legacy else frame
        a=resolve_candidate(f,name,options,draws,{},delivery_error_override=error,include_details=False)
        result['candidate_resolution_calls']+=1
        if not legacy:result['recovery_geometry_evaluations']+=1
        return a
    radius=option['delivery']['window_radius_m'];scale=option['delivery']['error_scale_m']
    lo,hi=_late_interval(frame,name,option)
    if not inside(option['target'],c) or hi<=lo:lo=hi=0.0
    qlo,qhi=_cdf(lo,scale),_cdf(hi,scale)
    # Accepted clean geometry/time channel uses its original exact deadline
    # cuts and G4/G8 integration. New directions have no invented meaning here.
    if hi>lo:
        elapsed=frame['elapsed']+wait;catch_limit=max(0,min(hi,4*(frame['remaining_s']-elapsed-option['delivery']['flight_s']-.05)))
        good_hi=_clock_interval(frame,name,option,lo,catch_limit,result) if catch_limit>lo else lo
        qgood=max(qlo,min(qhi,_cdf(good_hi,scale)))
        clock_mass=(qhi-qgood)*survival
        _failure(result,'shot_clock_turnover',clock_mass);result['receipt_planned_probabilities']['clean']+=clock_mass
        for node,weight in nodes:
            if qgood<=qlo:break
            q=qlo+(qgood-qlo)*node;error=-math.log1p(-q)*scale
            evaluate(resolve(error,0,legacy=True),(qgood-qlo)*weight,'clean')
    intervals=[(0,qlo),(qhi,1)] if qhi>qlo else [(0,1)]
    for direction in range(6):
        maximum=max_error(frame,name,option,direction);qlimit=_cdf(maximum,scale)
        for left,right in intervals:
            end=min(right,qlimit)
            if end>left:
                for panel in range(c.integration_panels):
                    a=left+(end-left)*panel/c.integration_panels;b=left+(end-left)*(panel+1)/c.integration_panels
                    for node,weight in nodes:
                        q=a+(b-a)*node;error=-math.log1p(-q)*scale;action=resolve(error,direction)
                        category=action['record'].get('receipt_category','lost')
                        evaluate(action,(b-a)*weight/6,category)
            tail=right-max(left,qlimit)
            if tail>0:
                # Beyond the court/vertical bound every poor trajectory on
                # this axis has the same terminal cause/time; integrate exactly.
                action=resolve(max(maximum+.001,radius+1),direction)
                if action['kind']!='turnover':raise AssertionError('Recovery tail bound must be terminal')
                evaluate(action,tail/6,'lost')
    result.update(policy=POLICY,quadrature_order=order,integration_panels=c.integration_panels,direction_prior={k:1/6 for k in DIRECTIONS},
        conditional_on='current handling/access/help/read retained; no future outcome draws',rebound_continuation_credit=0.0,
        recovery_reset_continuation_credit=0.0,receiver_id=option['receiver_id'],
        source_revisions={'creator':frame['creator'].revision,'receiver':frame['coupled']['profiles'][option['receiver_id']].revision},
        preference_weight=frame['coupled']['profiles'][option['receiver_id']].willingness if name in ('F06','pop') else 1.0)
    return result
