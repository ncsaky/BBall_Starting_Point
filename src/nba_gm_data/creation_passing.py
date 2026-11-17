"""Default-off drive/read/delivery versus containment/help mechanism.

A decision stage for the existing event kernel, not another scoring engine.
Setup geometry/assignments/screens/roll paths remain explicit context. Only
F03/F04/F06 are consumed; no universal passing grade or cross-court surrogate.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass,replace
import math

from .interior_defense import SKILL_SCALE,clamp,fingerprint
from .player_model import PlayerInputs
from .experimental_inputs import common_reader,interpretation_revision,same_input_snapshot

VERSION='creation_passing_defense_2026_11_13_v2'
HELP_RESPONSE_POLICY='projected_contest_v1'
CHOICE_POLICY='downstream_outcomes_v1'
SKILLS=('S16','S17','S19','S20','S33','S34','S38','S39','S40','S41','S42','S43','S44')
FAMILIES=('F03','F04','F06')


@dataclass(frozen=True)
class CreationCoefficients:
    beat_transition_s: float=.25
    handling_floor: float=.008
    pressure_loss: float=.22
    wrong_choice: float=.45
    bad_read_floor: float=.05
    delivery_error_floor_m: float=.10
    delivery_error_skill_m: float=.85
    delivery_distance_error: float=.035
    recovery_delay_s: float=.12
    decision_delay_s: float=.25
    assist_window_s: float=2.0

    def __post_init__(self):
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in asdict(self).values()):raise ValueError('Invalid exploratory creation coefficient')
        if self.beat_transition_s<=0 or self.delivery_error_floor_m<=0 or max(self.handling_floor,self.pressure_loss,self.wrong_choice,self.bad_read_floor)>1:raise ValueError('Invalid probability/time scale')


@dataclass(frozen=True)
class InteractionProfile:
    inputs: PlayerInputs
    player_id: str
    skills: tuple[float | None,...]
    passing: tuple[tuple[float,float],...]
    acceleration_m_s2: float
    speed_m_s: float
    lateral_m_s: float
    risk: float
    help_commitment: float
    revision: str

    def skill(self,key):return self.skills[SKILLS.index(key)]
    def pass_skill(self,family,part):
        if family not in FAMILIES:raise ValueError(f'{family}: unsupported route, not a universal passing input')
        return self.passing[FAMILIES.index(family)][('recognition','execution').index(part)]


def compile_interaction(inputs: PlayerInputs,*,research_scenario=False):
    doc=inputs.to_dict();rows=doc['inputs'];scale='research_technique_reference_v0_2026_11_13' if research_scenario else SKILL_SCALE
    reader=common_reader(inputs,doc)
    if reader and research_scenario:raise ValueError('Do not mix common interpretation and legacy research flag')
    def value(key):
        r=rows.get(key)
        if r is None or r['status']=='unknown':raise ValueError(f'{key}: explicit interaction input required')
        return r['value']
    def grade(key):
        # Unknown disruption technique disables steal attribution, not handling
        # or passing losses. Never impute it from total turnovers or reputation.
        if key in ('S42','S43') and (key not in rows or rows[key]['status']=='unknown'):return None
        if reader:return reader.grade(key)
        v=value(key)
        if v['scale']!=scale:raise ValueError(f'{key}: unsupported interaction skill scale')
        return v['grade']/100
    def measurement(key,metric,unit):
        if reader:return reader.measurement(key)
        protocols={'interior_scenario_reference_v1'}
        if research_scenario:
            metric={'P05':'fixture_acceleration','P06':'fixture_speed','P07':'fixture_lateral_speed'}[key]
            protocols={'synthetic dimensional fixture, no human measurement'}
            if key=='P07':protocols.add('synthetic movement axis, not observed speed')
        candidates=[m for m in value(key)['measurements'] if m['metric']==metric and m['unit']==unit and m['protocol'] in protocols]
        if len(candidates)!=1 or candidates[0]['value']<=0:raise ValueError(f'{key}: positive {metric}/{unit} under the declared scenario protocol required')
        return candidates[0]['value']
    return InteractionProfile(inputs,doc['player_id'],tuple(grade(k) for k in SKILLS),tuple((grade(f+'.recognition'),grade(f+'.execution')) for f in FAMILIES),
        measurement('P05','acceleration','m/s2'),measurement('P06','straight_line_speed','m/s'),measurement('P07','lateral_speed','m/s'),
        value('T07')['probability'],value('T15')['probability'],fingerprint(interpretation_revision({'version':VERSION,'inputs':doc,'research_scenario':research_scenario},inputs)))


def motion_time(distance_m,acceleration,speed):
    if distance_m<0 or min(acceleration,speed)<=0:raise ValueError('Invalid dimensional movement')
    ramp=speed*speed/(2*acceleration)
    return math.sqrt(2*distance_m/acceleration) if distance_m<=ramp else speed/acceleration+(distance_m-ramp)/speed


def handling_loss(profile,pressure,exposure_s,coefficients=CreationCoefficients()):
    if not 0<=pressure<=1 or exposure_s<0:raise ValueError('Invalid pressure/exposure')
    return clamp(coefficients.handling_floor+coefficients.pressure_loss*pressure*(1-profile.skill('S17'))*(1+.15*exposure_s))


@dataclass(frozen=True)
class DriveSetup:
    creator_id: str
    defender_id: str
    kick_receiver_id: str | None
    roller_id: str | None
    screen_separation_m: float=.5
    drive_x_m: float=.8
    drive_y_m: float=1.5
    roll_x_m: float=.6
    roll_y_m: float=.8
    roll_window_s: float=2.5
    # Supplied receiver/coverage route context, NOT S25/S27/S28 execution.
    receiver_defender_gap_m: float=.8
    enabled_pass_families: tuple[str,...]=FAMILIES

    def __post_init__(self):
        if not self.creator_id or not self.defender_id:raise ValueError('Current creator/defender assignments required')
        for key,value in asdict(self).items():
            if key.endswith('_id') or key=='enabled_pass_families':continue
            if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Finite setup geometry required')
        if min(self.screen_separation_m,self.receiver_defender_gap_m)<0 or self.roll_window_s<=0:raise ValueError('Nonnegative displacement/gap and positive roll window required')
        if self.kick_receiver_id==self.creator_id or self.roller_id==self.creator_id:raise ValueError('Cannot deliver a pass to oneself')
        if self.kick_receiver_id is not None and self.kick_receiver_id==self.roller_id:raise ValueError('Kick and supplied roll receivers must be distinct')
        if not isinstance(self.enabled_pass_families,tuple) or len(set(self.enabled_pass_families))!=len(self.enabled_pass_families) or not set(self.enabled_pass_families)<=set(FAMILIES):raise ValueError('Only explicit F03/F04/F06 route contexts are supported')


@dataclass(frozen=True)
class CreationExperiment:
    profiles: tuple[InteractionProfile,...]
    setups: tuple[DriveSetup,...]
    coefficients: CreationCoefficients=CreationCoefficients()
    possession_budget_s: float=24.0
    reset_cost_s: float=4.0
    rebound_budget_s: float=14.0
    screens: object | None = None
    # Explicit experiment variant; existing callers/revisions remain reproducible.
    # The new pilot opts in. Neither policy is a production activation.
    help_response_policy: str = 'legacy_timely_v1'
    choice_policy: str = 'legacy_scores_v1'

    def __post_init__(self):
        if not isinstance(self.profiles,tuple) or not isinstance(self.setups,tuple):raise ValueError('Immutable interaction configuration required')
        for ids in ([p.player_id for p in self.profiles],[s.creator_id for s in self.setups]):
            if len(set(ids))!=len(ids):raise ValueError('Duplicate interaction player/setup')
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (self.possession_budget_s,self.reset_cost_s,self.rebound_budget_s)):raise ValueError('Positive finite experimental clock controls required')
        if self.help_response_policy not in ('legacy_timely_v1',HELP_RESPONSE_POLICY):raise ValueError('Unsupported experimental help response policy')
        if self.choice_policy not in ('legacy_scores_v1',CHOICE_POLICY):raise ValueError('Unsupported experimental action choice policy')
        if self.choice_policy==CHOICE_POLICY and self.help_response_policy!=HELP_RESPONSE_POLICY:raise ValueError('Consistent action choices require the projected helper response')

    @property
    def revision(self):
        data={'version':VERSION,'profiles':[(p.player_id,p.revision) for p in self.profiles],'setups':[asdict(s) for s in self.setups],
            'coefficients':asdict(self.coefficients),'clock':[self.possession_budget_s,self.reset_cost_s,self.rebound_budget_s]}
        if self.screens is not None:data['screens']=self.screens.revision
        if self.help_response_policy!='legacy_timely_v1':data['help_response_policy']=self.help_response_policy
        if self.choice_policy!='legacy_scores_v1':data['choice_policy']=self.choice_policy
        return fingerprint(data)


def containment_response(attacker,defender,setup,coefficients=CreationCoefficients()):
    if hasattr(setup,'origin_x_m'):
        from .pass_recovery import recovery_containment
        return recovery_containment(attacker,defender,setup,coefficients)
    # Without-ball capacities are dimensional inputs; dribble manipulation and
    # craft add execution time. S17/security and S20/read do not create speed.
    clear=motion_time(.9,attacker.acceleration_m_s2,attacker.speed_m_s)*(1+.35*(1-attacker.skill('S16'))+.25*(1-attacker.skill('S19')))
    recovery=(.8+setup.screen_separation_m)/defender.lateral_m_s*(1+.65*(1-defender.skill('S33'))+.25*(1-defender.skill('S34')))+.20*(1-defender.skill('S41'))
    z=clamp((recovery-clear)/coefficients.beat_transition_s,-20,20)
    beat=.05+.90/(1+math.exp(-z))
    pressure=clamp(1-beat)
    return {'beat_probability':beat,'handling_loss_probability':handling_loss(attacker,pressure,clear,coefficients),
        'attacker_clear_s':clear,'defender_recovery_s':recovery,'pressure':pressure,'source_revisions':[attacker.revision,defender.revision]}


def helper_response(helper,start,ball,drive_time,noticed_draw,commit_draw):
    recognition=.05+.90*helper.skill('S38')*helper.skill('S44')
    noticed=noticed_draw<recognition
    committed=noticed and commit_draw<helper.help_commitment
    delay=.08+.45*(1-helper.skill('S38'))
    # Off-ball positioning changes the starting route; not a flat global bonus.
    distance=math.hypot(start[0]-ball[0],start[1]-ball[1])+.6*(1-helper.skill('S39'))
    arrival=delay+motion_time(distance,helper.acceleration_m_s2,min(helper.speed_m_s,helper.lateral_m_s))
    return {'noticed':noticed,'committed':committed,'recognition_probability':recognition,'recognition_delay_s':delay,
        'arrival_s':arrival,'timely':committed and arrival<=drive_time,'start_m':start,'help_destination_m':ball,
        'source_revision':helper.revision}


def delivery_response(profile,family,distance_m,pressure,opening,coefficients=CreationCoefficients()):
    execution=profile.pass_skill(family,'execution')
    radius={'F03':.65,'F04':.85,'F06':.90}[family]*clamp(opening,.10,1)
    error_scale=coefficients.delivery_error_floor_m+coefficients.delivery_error_skill_m*(1-execution)+coefficients.delivery_distance_error*distance_m+.25*pressure
    flight=distance_m/(12+profile.speed_m_s*.5)+(.22 if family=='F04' else .05)
    return {'accuracy_probability':1-math.exp(-radius/error_scale),'window_radius_m':radius,'error_scale_m':error_scale,
        'flight_s':flight,'family':family,'execution_input':family+'.execution'}


def sample_delivery(response,draw):
    error=-math.log(max(1e-12,1-draw))*response['error_scale_m']
    return delivery_at_error(response,error)


def delivery_at_error(response,error):
    """Same physical branch for actual sampling and deterministic projection."""
    if type(error) not in (int,float) or not math.isfinite(error) or error<0:raise ValueError('Finite nonnegative delivery error required')
    accurate=error<=response['window_radius_m']
    return {'accurate':accurate,'error_m':error,'quality':clamp(1-error/(2*response['window_radius_m']),.5,1) if accurate else 0,
        'catch_delay_s':.05+error*.25}


def prepare_delivery(frame,choice,option,error,*,sampled_delivery=None):
    """Resolve placement/window geometry before catch or shot outcome sampling."""
    from .screen_navigation import receiver_position
    passed=delivery_at_error(option['delivery'],error) if sampled_delivery is None else sampled_delivery
    target=option['target'];quality=passed['quality'];flight=option['delivery']['flight_s'];extra={};outcome=None
    deadline=frame['screen']['window_end_s'] if choice=='pop' else frame['setup'].roll_window_s
    if not passed['accurate']:outcome='inaccurate_delivery'
    elif choice in ('F03','F04','pop') and frame['elapsed']+option.get('wait_s',0)+flight+passed['catch_delay_s']>=deadline:
        outcome='late_delivery';extra['failure_reason']='derived screen receiving window expired before catch' if frame['screen'] else 'supplied receiving window expired before catch'
    elif frame['screen'] and choice in ('F03','F04','pop'):
        catch_time=frame['elapsed']+option.get('wait_s',0)+flight+passed['catch_delay_s']
        actual=receiver_position(frame['screen'],catch_time,frame['state']['screens']['profiles'][option['receiver_id']])
        timing_error=math.dist(actual,target);extra['moving_receiver_error_m']=timing_error
        if timing_error>option['delivery']['window_radius_m'] or catch_time<frame['screen']['window_start_s']:
            outcome='late_delivery';extra['failure_reason']='moving receiver outside derived catch window'
        else:
            quality*=clamp(1-timing_error/(2*option['delivery']['window_radius_m']),.5,1);target=actual
    return {'outcome':outcome,'passed':passed,'extra':extra,'quality':quality,'target':target,'flight_s':flight,'catch_delay_s':passed['catch_delay_s']}


def delivery_preparation(profile,choice,quality):
    from .offense_response import release_preparation,receiving_preparation,finish_preparation,finishing_response
    base=release_preparation(profile) if choice in ('F06','pop') else finish_preparation(finishing_response(profile,'lob' if choice=='F04' else 'dunk')['finish'])
    return base+receiving_preparation(profile,quality)


def screen_interception(screen,receiver,creator,family,ball,elapsed,pressure,coefficients):
    """Bounded earliest feasible catch; waiting consumes actual possession time.

    Ball is held at the supplied drive exit. Receiver/coverage keep moving;
    this is not a general future-possession planner or a guaranteed completion.
    """
    from .screen_navigation import receiver_position
    waiting=screen.get('timing_policy')=='bounded_wait_v1'
    arrival=max(elapsed+.10,screen['window_start_s']+1e-6) if waiting else elapsed+.10
    wait=0.0
    for _ in range(12):
        target=receiver_position(screen,arrival,receiver)
        flight=delivery_response(creator,family,math.dist(ball,target),pressure,1,coefficients)['flight_s']
        wait=max(0,screen['window_start_s']+1e-6-elapsed-flight-.05) if waiting else 0.0
        updated=elapsed+wait+flight+.05
        if abs(updated-arrival)<1e-8:break
        arrival=updated
    arrival=updated;target=receiver_position(screen,arrival,receiver)
    if not screen['window_start_s']<=arrival<screen['window_end_s']:return None
    return {'target':target,'wait_s':wait,'minimum_catch_s':arrival}


def prepare_creation(spec,coupled,pools,anchors,contexts):
    profiles={p.player_id:p for p in spec.profiles};setups={s.creator_id:s for s in spec.setups}
    active=set(coupled['team_for'])
    if not active<=set(profiles) or not active<=set(setups):raise ValueError('Every active creator and defender requires explicit interaction inputs/setup')
    for pid in active:
        if not same_input_snapshot(profiles[pid].inputs,coupled['profiles'][pid].inputs):raise ValueError('Interaction/offense/defense must share one authoritative input snapshot and interpretation')
        s=setups[pid]
        if s.defender_id not in active or coupled['team_for'][s.defender_id]==coupled['team_for'][pid]:raise ValueError('Stale on-ball defender assignment')
        for receiver in (s.kick_receiver_id,s.roller_id):
            if receiver is not None and (receiver not in active or coupled['team_for'][receiver]!=coupled['team_for'][pid]):raise ValueError('Stale receiver assignment')
    if len({setups[pid].defender_id for pid in active})!=len(active):raise ValueError('One current assignment per defender required; switches are not modeled')
    for tid,anchor in anchors.items():
        if anchor is not None:
            assigned=dict(coupled['spec'].anchor_assignments)[tid]
            if setups[assigned].defender_id!=anchor.profile.inputs.player_id:raise ValueError('Helper and on-ball assignments disagree')
    # Rebuild the spatial reference from the assigned new defenders, rather
    # than retaining the old externally supplied pressure/arrival controls.
    from .offense_response import offensive_spatial_profile
    for pid in active:
        guard=profiles[setups[pid].defender_id]
        reference_pressure=.20+.65*guard.skill('S40')
        reference_arrival=.12+.18*(1-guard.skill('S40'))
        coupled['spatial'][coupled['team_for'][pid]][pid]=offensive_spatial_profile(coupled['profiles'][pid],coupled['deployments'][pid],pressure=reference_pressure,defender_arrival_s=reference_arrival)
    assignments=dict(coupled['spec'].anchor_assignments)
    for tid,anchor in anchors.items():
        if anchor is None:continue
        pid=assignments[tid];p=coupled['profiles'][pid];dep=coupled['deployments'][pid]
        threat=coupled['spatial'][coupled['team_for'][pid]][pid]['perimeter_expected_points_per_opportunity']
        pull=1-math.exp(-threat/p.coefficients.positioning_pull_points)
        coupled['positions'][tid]=(dep.perimeter_x_m*pull,1+(dep.perimeter_y_m-1)*pull)
        coupled['spatial'][coupled['team_for'][pid]][pid]['anchor_assignment_response']={'defending_team_id':tid,'pull_fraction':pull,'defender_position_m':coupled['positions'][tid]}
    state={'spec':spec,'coupled':coupled,'profiles':profiles,'setups':setups,'anchors':anchors,'contexts':contexts}
    if spec.screens is not None:
        from .screen_navigation import prepare_screens
        state['screens']=prepare_screens(spec.screens,state,pools)
    if getattr(spec,'receipt_policy',None):
        from .pass_recovery import prepare_receiving
        prepare_receiving(state)
    return state


def _point_on_path(start,end,elapsed,delay,profile,*,route_extra_m=0.0):
    time=max(0,elapsed-delay)
    speed=min(profile.speed_m_s,profile.lateral_m_s)
    covered=.5*profile.acceleration_m_s2*time*time if time<=speed/profile.acceleration_m_s2 else speed*(time-speed/(2*profile.acceleration_m_s2))
    distance=math.hypot(end[0]-start[0],end[1]-start[1])
    fraction=clamp(covered/max(distance+route_extra_m,1e-9))
    return (start[0]+fraction*(end[0]-start[0]),start[1]+fraction*(end[1]-start[1]))


def _lane_distance(point,start,end):
    dx,dy=end[0]-start[0],end[1]-start[1]
    t=clamp(((point[0]-start[0])*dx+(point[1]-start[1])*dy)/max(1e-9,dx*dx+dy*dy))
    return math.hypot(point[0]-start[0]-t*dx,point[1]-start[1]-t*dy)


def prepare_drive_decision(state,creator_id,team_id,opponent_id,draws,remaining_s,*,screen_allowed=True):
    from .offense_response import ActionShotContext,HelpShotContext,finishing_response,shooting_response,plan_attack
    coupled=state['coupled'];spec=state['spec'];c=spec.coefficients;profiles=state['profiles'];setup=state['setups'][creator_id]
    creator=profiles[creator_id];defender=profiles[setup.defender_id]
    screen=None
    if 'screens' in state:
        from .screen_navigation import resolve_screen,receiver_position,coverage_position
        # New mode never falls back to gifted screen meters/roll windows.
        setup=replace(setup,screen_separation_m=0,roller_id=None)
        screen=resolve_screen(state['screens'],creator,setup,draws) if screen_allowed else {'kind':'none','reason':'continuation_no_rescreen'}
        if screen['kind']=='screen' and screen['route'] not in ('screen','pop'):
            setup=replace(setup,roller_id=screen['screener_id'],roll_x_m=screen['roll_end'][0],roll_y_m=screen['roll_end'][1],roll_window_s=screen['window_end_s'])
    drive=containment_response(creator,defender,setup,c)
    if screen and screen['kind']=='screen':
        clear=screen['attacker_clear_s'];recovery=screen['guard_arrival_s']+.12*(1-defender.skill('S33'))+.06*(1-defender.skill('S34'))
        beat=.05+.90/(1+math.exp(-clamp((recovery-clear)/c.beat_transition_s,-20,20)))
        drive={**drive,'attacker_clear_s':clear,'defender_recovery_s':recovery,'beat_probability':beat,'pressure':1-beat,
            'handling_loss_probability':handling_loss(creator,1-beat,clear,c),'screen_separation_control_used':False}
    record={'version':VERSION,'creator_id':creator_id,'on_ball_defender_id':setup.defender_id,'containment':drive,'remaining_before_s':remaining_s,'generic_loss_roll_used':False}
    if screen is not None:
        record['screen_action']=screen
        if screen['kind']=='illegal_screen':
            return {'kind':'turnover','outcome':'illegal_screen','responsible':screen['screener_id'],'offensive_foul_by':screen['screener_id'],
                'steal_by':None,'record':record,'elapsed_s':screen['contact_s']}
    if draws[24]<drive['handling_loss_probability']:
        technique=defender.skill('S42')
        record['steal_attribution_available']=technique is not None
        steal=setup.defender_id if technique is not None and draws[37]<.10+.75*technique else None
        return {'kind':'turnover','outcome':'handling_loss','responsible':creator_id,'steal_by':steal,'record':record,'elapsed_s':drive['attacker_clear_s']}
    beat=draws[25]<drive['beat_probability'];record['beat_defender']=beat
    ball=(setup.drive_x_m,setup.drive_y_m);elapsed=drive['attacker_clear_s']+c.decision_delay_s*(1-creator.skill('S20'))
    anchor=state['anchors'][opponent_id]
    # The previous interior path gates unavailable anchors. They cannot become
    # ghost helpers/interceptors merely because a setup still references them.
    if anchor and state['contexts'][opponent_id].anchor_available==0:anchor=None
    anchor_id=anchor.profile.inputs.player_id if anchor else None
    record['anchor_available_for_action']=anchor is not None
    helper=None;helped={'noticed':False,'committed':False,'timely':False,'arrival_s':None}
    if anchor and anchor_id!=setup.defender_id:
        helper=profiles[anchor_id]
        help_start=screen['coverage_start'] if screen and screen.get('roller_defender_id')==anchor_id else coupled['positions'][opponent_id]
        helped=helper_response(helper,help_start,ball,elapsed,draws[26],draws[27]) if beat else {**helped,'reason':'drive_contained_no_emergency_help'}
    record['help']=helped
    start=screen['coverage_start'] if screen and anchor_id is not None and screen.get('roller_defender_id')==anchor_id else coupled['positions'][opponent_id] if anchor else (0.0,1.0)
    helper_position=start
    if helper and helped['committed']:
        # helper_response already includes this positioning route inefficiency.
        # The new policy uses the same effective path for displayed/used position;
        # it must not reach the body before its own declared arrival time.
        extra=.6*(1-helper.skill('S39')) if spec.help_response_policy==HELP_RESPONSE_POLICY else 0.0
        helper_position=_point_on_path(start,ball,elapsed,helped['recognition_delay_s'],helper,route_extra_m=extra)
    # Candidate existence comes from setup/geometry. Recognition gates whether
    # a useful window is seen, independently of delivery accuracy.
    options={};notices={};unsupported=[]
    if beat:
        noticed=draws[28]<.10+.85*creator.skill('S20');notices['finish']=noticed
        if noticed:
            finish_value=2*finishing_response(coupled['profiles'][creator_id],'layup')['make_probability']-(.55 if helped['timely'] else 0)
            options['finish']={'value':finish_value,'danger':.15 if not helped['timely'] else .65}
            if spec.help_response_policy==HELP_RESPONSE_POLICY and spec.choice_policy=='legacy_scores_v1':
                projection={'policy':HELP_RESPONSE_POLICY,'candidate':'layup; downstream finish mix remains explicit',
                    'timely_is_diagnostic_only':True,'contest_failure_increment':0.0}
                if helper and helped['committed']:
                    # Anticipate the existing C27 effect on this candidate. A
                    # body-arrival label must not award a second flat bonus.
                    # The actual selected-shot contest is still applied once,
                    # downstream; this projection only informs action selection.
                    preview_context=replace(state['contexts'][opponent_id],poa_containment=0,recognition_delay_s=0)
                    preview_action=HelpShotContext(defender_route_origin_m=start,finish_kind='layup',primary_pressure=drive['pressure'],
                        primary_arrival_s=max(0,drive['defender_recovery_s']-elapsed),defender_position_m=helper_position,
                        interior_arrival_s=max(0,helped['arrival_s']-elapsed),shot_position_m=ball)
                    preview=plan_attack(coupled,creator_id,'rim',draws,opponent_id,anchor,preview_context,action_context=preview_action)
                    response=preview['response'];base=preview['off']['rim_pct']
                    make=(1-response['block_probability'])*clamp(base-response['conversion_reduction'])
                    cost=max(0,base-make)
                    options['finish']={'value':2*make,'danger':clamp(.15+cost)}
                    projection.update(contest_failure_increment=cost,base_conversion_probability=base,
                        make_probability_given_no_foul=make,coverage_available=response['coverage_available'],
                        conversion_reduction=response['conversion_reduction'],block_probability=response['block_probability'],
                        arrival_s=response['arrival_s'],window_s=response['window_s'],
                        expected_points_scope='two-point conversion/block only; foul/rebound value not calibrated')
                else:
                    # No eligible helper: preserve the prior unhelped score.
                    options['finish']={'value':2*finishing_response(coupled['profiles'][creator_id],'layup')['make_probability'],'danger':.15}
                    projection['reason']='no committed eligible helper'
                record['help_finish_projection']=projection
    for family,receiver in (('F06',setup.kick_receiver_id),('F03',setup.roller_id),('F04',setup.roller_id)):
        if family not in setup.enabled_pass_families:unsupported.append(family+'_disabled');continue
        if receiver is None:continue
        target_profile=coupled['profiles'][receiver]
        if family=='F06':
            loc=coupled['deployments'][receiver];target=(loc.perimeter_x_m,loc.perimeter_y_m)
            if ball[0]*target[0]<0:unsupported.append('F07_cross_court');continue
            if target_profile.willingness==0:continue
        else:
            if not screen and not beat and setup.screen_separation_m<=0:continue
            if family=='F04' and target_profile.standing_reach_cm+target_profile.jump_cm<310:continue
            target=(setup.roll_x_m,setup.roll_y_m)
            if elapsed>=setup.roll_window_s:continue
            if screen:
                roller_profile=state['screens']['profiles'][receiver]
                if screen.get('route_policy')=='screen_to_pop_v1':
                    intercept=screen_interception(screen,roller_profile,creator,family,ball,elapsed,drive['pressure'],c)
                    if intercept is None:continue
                    target=intercept['target']
                else:
                    # Preserve the accepted immediate-only moving interception.
                    # No supplied roll gap/deadline is used.
                    arrival=elapsed+.10
                    for _ in range(4):
                        target=receiver_position(screen,arrival,roller_profile)
                        flight=delivery_response(creator,family,math.dist(ball,target),drive['pressure'],1,c)['flight_s']
                        arrival=elapsed+flight+.05
                    if not screen['window_start_s']<=arrival<screen['window_end_s']:continue
        receiver_defender=profiles[state['setups'][receiver].defender_id]
        is_helper=helper is not None and receiver_defender.player_id==helper.player_id
        defender_position=helper_position if is_helper else (target[0]+setup.receiver_defender_gap_m,target[1])
        if is_helper and not helped['committed']:
            defender_position=_point_on_path(start,target,elapsed,0,helper)
        if screen and family in ('F03','F04') and not (is_helper and helped['committed']):
            launch=elapsed+intercept['wait_s'] if screen.get('route_policy')=='screen_to_pop_v1' else elapsed
            defender_position=coverage_position(screen,launch,state['screens']['profiles'][receiver_defender.player_id])
        gap=math.hypot(defender_position[0]-target[0],defender_position[1]-target[1])
        opening=clamp(.25+.15*gap,.25,.95)
        distance=math.hypot(target[0]-ball[0],target[1]-ball[1]);delivery=delivery_response(creator,family,distance,drive['pressure'],opening,c)
        if family!='F06' and elapsed+delivery['flight_s']>=setup.roll_window_s:continue
        idx={'F03':29,'F04':30,'F06':31}[family]
        noticed=draws[idx]<c.bad_read_floor+(1-c.bad_read_floor)*creator.pass_skill(family,'recognition')
        notices[family]=noticed
        if not noticed:continue
        potential=(3*shooting_response(target_profile)['make_probability']*target_profile.willingness if family=='F06'
                   else 2*finishing_response(target_profile,'lob' if family=='F04' else 'dunk')['make_probability'])
        danger=1-delivery['accuracy_probability']
        value=potential*delivery['accuracy_probability']*(.5+.5*target_profile.skill(14))
        options[family]={'value':value,'danger':danger,'receiver_id':receiver,'target':target,'delivery':delivery,'opening':opening,'coverage_position':defender_position}
        if family in ('F03','F04') and screen and screen.get('route_policy')=='screen_to_pop_v1':
            _apply_wait(options[family],intercept['wait_s'],creator,drive,c,math.dist(ball,target))
    if screen and screen.get('route')=='pop' and 'F06' in setup.enabled_pass_families:
        receiver=screen['screener_id'];target_profile=coupled['profiles'][receiver]
        intercept=screen_interception(screen,state['screens']['profiles'][receiver],creator,'F06',ball,elapsed,drive['pressure'],c)
        if intercept is not None and ball[0]*intercept['target'][0]>=0 and target_profile.willingness>0:
            receiver_defender=profiles[state['setups'][receiver].defender_id]
            defender_position=coverage_position(screen,elapsed+intercept['wait_s'],state['screens']['profiles'][receiver_defender.player_id])
            opening=clamp(.25+.15*math.dist(defender_position,intercept['target']),.25,.95)
            delivery=delivery_response(creator,'F06',math.dist(ball,intercept['target']),drive['pressure'],opening,c)
            noticed=draws[31]<c.bad_read_floor+(1-c.bad_read_floor)*creator.pass_skill('F06','recognition');notices['pop']=noticed
            if noticed:
                options['pop']={'value':3*shooting_response(target_profile,distance_m=math.hypot(*intercept['target']))['make_probability']*target_profile.willingness*delivery['accuracy_probability'],
                    'danger':1-delivery['accuracy_probability'],'receiver_id':receiver,'target':intercept['target'],'delivery':delivery,
                    'opening':opening,'coverage_position':defender_position,'family':'F06','route':'screen_to_pop'}
                _apply_wait(options['pop'],intercept['wait_s'],creator,drive,c,math.dist(ball,intercept['target']))
        elif intercept is not None and ball[0]*intercept['target'][0]<0:unsupported.append('F07_cross_court_pop')
    record.update(noticed_options=notices,unsupported_routes=unsupported,available_choices=list(options),
        pass_family_policy='exclusive supplied route: F04 lob replaces F03 roll feed; no stacked talents; cross-court F07 disabled',
        windows={k:{'opening':v['opening'],'target':v['target'],'coverage_position':v['coverage_position']} for k,v in options.items() if k!='finish'})
    if screen:
        record['pass_family_policy']='exclusive screen-derived route: F04 replaces F03 feed; no stacked talents; cross-court F07 disabled'
        if screen.get('route_policy')=='screen_to_pop_v1':
            record['pass_family_policy']='roll F03 or lob F04; same-side drive-exit pop uses F06, distinct from the fixed F06 outlet; no passing talents summed'
            for key,option in options.items():
                if 'wait_s' in option:record['windows'][key].update(wait_s=option['wait_s'],waiting_loss_probability=option['waiting_loss_probability'])
    frame={'state':state, 'creator_id':creator_id, 'opponent_id':opponent_id, 'coupled':coupled, 'spec':spec, 'c':c, 'profiles':profiles, 'setup':setup, 'creator':creator, 'defender':defender, 'screen':screen, 'drive':drive, 'ball':ball, 'elapsed':elapsed, 'anchor':anchor, 'anchor_id':anchor_id, 'helper':helper, 'helped':helped, 'start':start, 'helper_position':helper_position, 'remaining_s':remaining_s}
    return {'frame':frame,'options':options,'record':record}


def _apply_wait(option,wait,creator,drive,c,distance):
    """Conditional additional hold risk; initial handling loss was already sunk."""
    pressure=drive['pressure']+(1-drive['pressure'])*(-math.expm1(-wait/c.beat_transition_s))
    option.update(wait_s=wait,waiting_pressure=pressure,
        waiting_loss_probability=-math.expm1(-c.pressure_loss*pressure*(1-creator.skill('S17'))*wait))
    # Placement is harder after the on-ball defender has recovered. Recompute
    # the one family response, never stack a second passing talent bonus.
    option['delivery']=delivery_response(creator,option.get('family',option['delivery']['family']),distance,pressure,option['opening'],c)
    option['danger']=1-option['delivery']['accuracy_probability']


def resolve_drive(state,creator_id,team_id,opponent_id,draws,remaining_s,*,screen_allowed=True):
    decision=prepare_drive_decision(state,creator_id,team_id,opponent_id,draws,remaining_s,screen_allowed=screen_allowed)
    if 'kind' in decision:return decision
    frame=decision['frame'];options=decision['options'];record=decision['record']
    creator=frame['creator'];c=frame['c'];elapsed=frame['elapsed'];spec=frame['spec']
    notices=record['noticed_options']
    if spec.choice_policy==CHOICE_POLICY:
        from .action_choice import resolve_projected_choice
        action=resolve_projected_choice(frame,options,draws,record)
        if getattr(spec,'receipt_policy',None):
            from .pass_recovery import complete_receipt
            return complete_receipt(action,draws[15],remaining_s)
        return action
    wrong=draws[32]<c.wrong_choice*(1-creator.skill('S20'))
    # A conservative player may reset rather than force a dangerous delivery;
    # risk appetite changes selection only, never read or placement competence.
    scores={name:option['value']-(1-creator.risk)*option['danger']*.85+creator.risk*option['danger']*.35 for name,option in options.items()}
    scores['reset']=.40
    if wrong:
        choice=min(scores,key=scores.get);record['bad_choice']=True
    else:
        choices=list(scores);weights=[max(.001,scores[k]-.25)**3 for k in choices]
        target=draws[33]*sum(weights);choice=choices[-1]
        for key,weight in zip(choices,weights,strict=True):
            target-=weight
            if target<0:choice=key;break
    record.update(choice=choice,choice_scores=scores,missed_reads=[k for k,v in notices.items() if not v])
    if choice=='reset':
        return {'kind':'reset','record':record,'elapsed_s':elapsed+spec.reset_cost_s,'reason':'missed_read_or_contained' if not options else 'conservative_or_bad_choice'}
    return resolve_candidate(frame,choice,options,draws,record)


def resolve_candidate(frame,choice,options,draws,record,*,finish_kind_override=None,delivery_error_override=None,include_details=True):
    """Resolve one supported candidate; projection supplies deterministic branches."""
    from .offense_response import ActionShotContext,HelpShotContext,StableBearingActionContext,plan_attack
    if not include_details:plan_attack=frame.get('_recovery_plan_evaluator',plan_attack)
    from .screen_navigation import receiver_position,coverage_position
    state=frame['state'];creator_id=frame['creator_id'];opponent_id=frame['opponent_id'];coupled=frame['coupled'];spec=frame['spec'];c=frame['c'];profiles=frame['profiles'];setup=frame['setup'];creator=frame['creator'];defender=frame['defender'];screen=frame['screen'];drive=frame['drive'];ball=frame['ball'];elapsed=frame['elapsed'];anchor=frame['anchor'];anchor_id=frame['anchor_id'];helper=frame['helper'];helped=frame['helped'];start=frame['start'];helper_position=frame['helper_position'];remaining_s=frame['remaining_s']
    stable=getattr(spec,'bearing_policy',None)=='stable_route_bearing_v2'
    helper_origin=start if helper else None;primary_origin=None
    passer=None;shot_pid=creator_id;quality=1.0;catch_delay=0.0;flight=0.0
    target=ball;finish_kind=None;zone='rim'
    if choice!='finish':
        option=options[choice];shot_pid=option['receiver_id'];target=option['target']
        wait=option.get('wait_s',0)
        if wait:
            record['wait']={'duration_s':wait,'pressure':option['waiting_pressure'],'conditional_handling_loss_probability':option['waiting_loss_probability'],
                'receiver_and_defender_continue_moving':True,'ball_hold_position_m':ball}
            if draws[43]<option['waiting_loss_probability']:
                return {'kind':'turnover','outcome':'waiting_loss','responsible':creator_id,'steal_by':None,'record':record,'elapsed_s':elapsed+wait}
            # Help follows its existing route over the additional elapsed time.
            if helper and helped['committed']:
                helper_position=_point_on_path(start,ball,elapsed+wait,helped['recognition_delay_s'],helper,route_extra_m=.6*(1-helper.skill('S39')))
        elapsed+=wait
        sampled=sample_delivery(option['delivery'],draws[34]) if delivery_error_override is None else None
        error=sampled['error_m'] if sampled is not None else delivery_error_override
        recovery_active=getattr(spec,'receipt_policy',None) and not frame.get('_legacy_delivery')
        if recovery_active:
            from .pass_recovery import delivery
            delivered=delivery(frame,choice,option,error,min(5,int(draws[44]*6)))
        else:delivered=prepare_delivery(frame,choice,option,error,sampled_delivery=sampled)
        passed=delivered['passed'];flight=delivered['flight_s']
        record['pass']={**option['delivery'],**passed,'receiver_id':shot_pid,'recognition_input':option.get('family',choice)+'.recognition'}
        if recovery_active:
            record.update(delivered['extra'],completed_pass=False,planned_pass_complete=not bool(delivered['outcome']),actual_receipt_secured=False if delivered['outcome'] else None)
            record['pass']['receipt_control_quality']=delivered['quality']
        if delivered['outcome']=='inaccurate_delivery':
            lane=_lane_distance(helper_position,ball,target) if helper else None
            reach=anchor.profile.wingspan_cm/200 if helper else 0
            technique=helper.skill('S43') if helper else None
            record['steal_attribution_available']=technique is not None
            interceptor=anchor_id if technique is not None and lane<=reach and draws[35]<technique*option['danger'] else None
            record['pass']['interceptor_lane_distance_m']=lane
            return {'kind':'turnover','outcome':'inaccurate_delivery','responsible':creator_id,'steal_by':interceptor,'record':record,'elapsed_s':elapsed+flight}
        record['pass'].update(delivered['extra'])
        quality=delivered['quality'];catch_delay=delivered['catch_delay_s'];passer=creator_id
        if delivered['outcome']:
            interceptor=None
            if recovery_active and delivered['outcome']=='recovery_defended':
                pid=delivered['extra']['recovery_geometry']['defender_id'];technique=profiles[pid].skill('S43')
                interceptor=pid if technique is not None and draws[35]<technique else None
            return {'kind':'turnover','outcome':delivered['outcome'],'responsible':creator_id,'steal_by':interceptor,'record':record,'elapsed_s':elapsed+flight+catch_delay}
        target=delivered['target']
        zone='perimeter' if choice in ('F06','pop') else 'rim';finish_kind='lob' if choice=='F04' else 'dunk' if choice=='F03' else None
        if recovery_active:
            record.update(delivered['extra'],planned_pass_complete=True,completed_pass=False,receiver_id=shot_pid,receipt_state='planned')
            if delivered.get('recovery_reset'):
                from .pass_recovery import reset_action
                return reset_action(frame,choice,option,delivered,record,elapsed)
            zone=delivered.get('zone_override',zone);finish_kind=delivered.get('finish_override',finish_kind)
    elif finish_kind_override is not None:
        if finish_kind_override not in ('layup','contact_layup','floater','dunk'):raise ValueError('Unsupported projected finish branch')
        finish_kind=finish_kind_override
    else:
        # No self-lob gift. Existing contextual finish alternatives are retained.
        kinds=('layup','contact_layup','floater','dunk');weights=coupled['spec'].finish_mix[:4]
        target_draw=draws[17]*sum(weights);finish_kind=kinds[-1]
        for name,weight in zip(kinds,weights,strict=True):
            target_draw-=weight
            if target_draw<0:finish_kind=name;break
    # Helper commitment removes coverage from its original shooter. Passage
    # time and catch delay allow physical recovery; no flat help multiplier.
    if passer and helper and not helped['committed'] and dict(coupled['spec'].anchor_assignments).get(opponent_id)==shot_pid:
        helper_position=_point_on_path(start,target,elapsed,0,helper)
    if passer:
        receiver_defender=profiles[state['setups'][shot_pid].defender_id]
        is_helper=helper is not None and receiver_defender.player_id==helper.player_id
        defender_position=options[choice]['coverage_position']
        recovery=c.recovery_delay_s*(2-receiver_defender.skill('S40'))+motion_time(math.hypot(defender_position[0]-target[0],defender_position[1]-target[1]),receiver_defender.acceleration_m_s2,min(receiver_defender.speed_m_s,receiver_defender.lateral_m_s))
        primary_arrival=max(0,recovery-flight-catch_delay)
        if screen and choice in ('F03','F04','pop'):
            if is_helper and helped['committed']:
                defender_position=_point_on_path(helper_position,target,flight+catch_delay,c.recovery_delay_s,receiver_defender)
            else:defender_position=coverage_position(screen,elapsed+flight+catch_delay,state['screens']['profiles'][receiver_defender.player_id])
            primary_origin=helper_position if is_helper and helped['committed'] else tuple(screen['coverage_release_position'])
            primary_arrival=c.recovery_delay_s*(2-receiver_defender.skill('S40'))+motion_time(math.dist(defender_position,target),receiver_defender.acceleration_m_s2,min(receiver_defender.speed_m_s,receiver_defender.lateral_m_s))
        pressure=.20+.65*receiver_defender.skill('S40')
        if recovery_active and delivered['extra']['receipt_category']=='recovered':
            defender_position=delivered['extra']['recovery_geometry']['defender_position_m']
            primary_origin=delivered['extra']['recovery_geometry'].get('defender_at_nominal_receipt_m')
            primary_arrival=c.recovery_delay_s*(2-receiver_defender.skill('S40'))+motion_time(math.dist(defender_position,target),receiver_defender.acceleration_m_s2,min(receiver_defender.speed_m_s,receiver_defender.lateral_m_s))
            if helper and helped['committed']:
                helper_origin=helper_position
                helper_position=_point_on_path(helper_position,target,flight+catch_delay,c.recovery_delay_s,helper)
    else:
        primary_arrival=max(0,drive['defender_recovery_s']-elapsed);pressure=drive['pressure']
    interior_arrival=None;context=state['contexts'][opponent_id]
    if anchor:
        available=context.anchor_available
        if anchor_id==setup.defender_id:
            helper_origin=None
            helper_position=(ball[0],ball[1]+1.0);interior_arrival=max(0,drive['defender_recovery_s']-elapsed-flight-catch_delay)
        elif helper and helped['committed']:
            if passer:
                arrival=c.recovery_delay_s*(2-helper.skill('S38'))+motion_time(math.hypot(helper_position[0]-target[0],helper_position[1]-target[1]),helper.acceleration_m_s2,min(helper.speed_m_s,helper.lateral_m_s))
                interior_arrival=max(0,arrival) if recovery_active and delivered['extra']['receipt_category']=='recovered' else max(0,arrival-flight-catch_delay)
            else:interior_arrival=max(0,helped['arrival_s']-elapsed)
        else:available=0.0;interior_arrival=0.0
        context=replace(context,anchor_available=available,poa_containment=0,recognition_delay_s=0)
    use_route_origin=spec.help_response_policy==HELP_RESPONSE_POLICY and helper and helped['committed'] and passer is None
    action_type=HelpShotContext if use_route_origin else ActionShotContext
    if passer and recovery_active and delivered['extra']['receipt_category']=='recovered':
        from .pass_recovery import RecoveredShotContext
        action_type=RecoveredShotContext
    action_kwargs={'defender_route_origin_m':start} if use_route_origin else {}
    if stable:
        action_type=StableBearingActionContext
        action_kwargs={'defender_route_origin_m':helper_origin,'recovered_receipt':bool(passer and recovery_active and delivered['extra']['receipt_category']=='recovered')}
    action=action_type(**action_kwargs,finish_kind=finish_kind,shot_mode='catch' if choice in ('F06','pop') else None,
        delivery_quality=quality,primary_pressure=pressure,primary_arrival_s=primary_arrival,
        defender_position_m=helper_position,interior_arrival_s=interior_arrival,receiver_delay_s=catch_delay,
        received_pass=passer is not None,shot_position_m=target if zone!='perimeter' or choice=='pop' or (passer and recovery_active and delivered['extra']['receipt_category']=='recovered') else None)
    plan=plan_attack(coupled,shot_pid,zone,draws,opponent_id,anchor,context,action_context=action,**({'include_details':False} if not include_details else {}))
    if screen and passer and choice in ('F03','F04'):
        from .interior_defense import Anchor,ArrivalContext
        pid=receiver_defender.player_id
        primary_anchor=Anchor(opponent_id,state['screens']['interior_profiles'][pid])
        primary_context=ArrivalContext(anchor_available=1,spacing=0,poa_containment=0,recognition_delay_s=0)
        primary_action=replace(action,defender_position_m=defender_position,interior_arrival_s=primary_arrival,**({'defender_route_origin_m':primary_origin} if stable else {}))
        primary_plan=plan_attack(coupled,shot_pid,zone,draws,opponent_id,primary_anchor,primary_context,action_context=primary_action,**({'include_details':False} if not include_details else {}))
        # Reuse C27's actual reachable geometry; arrival means entering contest
        # reach, not travelling all the way to the receiver's body. The override
        # replaces C27 travel, so this reach effect is not added twice.
        contest_distance=max(0,math.dist(defender_position,target)-primary_plan['response']['horizontal_reach_m'])
        primary_arrival=c.recovery_delay_s*(1-receiver_defender.skill('S40'))+motion_time(contest_distance,receiver_defender.acceleration_m_s2,min(receiver_defender.speed_m_s,receiver_defender.lateral_m_s))
        primary_action=replace(primary_action,primary_arrival_s=primary_arrival,interior_arrival_s=primary_arrival)
        primary_plan=plan_attack(coupled,shot_pid,zone,draws,opponent_id,primary_anchor,primary_context,action_context=primary_action,**({'include_details':False} if not include_details else {}))
        def contest_strength(p):
            r=p['response'];return r['conversion_reduction']+r['block_probability'] if r else 0
        use_primary=pid==anchor_id or contest_strength(primary_plan)>=contest_strength(plan)
        projection_contests=(primary_plan['response'],) if pid==anchor_id else (plan['response'],primary_plan['response'])
        alternative=plan['response'] if use_primary else primary_plan['response']
        plan=primary_plan if use_primary else plan
        plan['contest_defender_id']=pid if use_primary else anchor_id
        if include_details:
            plan['details'].update(contest_policy='single strongest eligible C27 contest; never summed',alternative_defense_response=alternative)
            plan['details']['controlled_dependencies']=['call/initial coordinates','stay/show coverage policy','route endpoint','helper assignment','rebound/clock support']
        else:plan['_projection_contests']=projection_contests
        record['receiver_defender_at_catch_m']=defender_position
        record['primary_contest_distance_m']=contest_distance
    preparation=plan['details']['geometry']['preparation_s'] if include_details else plan['preparation_s']
    record.update(completed_pass=passer is not None,receiver_id=shot_pid,help_position_at_pass_m=helper_position,
        derived_primary_pressure=pressure,derived_primary_arrival_s=primary_arrival,
        assist_eligible=passer is not None and catch_delay+preparation<c.assist_window_s)
    result={'kind':'shot','plan':plan,'passer_id':passer,'record':record,
            'elapsed_s':elapsed+flight+catch_delay+preparation}
    if passer and recovery_active:
        record.update(completed_pass=False,planned_pass_complete=True,actual_receipt_secured=None,receipt_state='planned')
        result['receipt_probability']=plan['reception']
    return result
