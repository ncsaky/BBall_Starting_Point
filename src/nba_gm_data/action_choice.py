"""Bounded deterministic decision aid for the existing experimental action set.

No RNG, future-draw access, recursive possession search or independent talents.
Selected candidates use creation_passing.resolve_candidate, then the same event
kernel samples reception, fouls, shots and rebounds. Physical inputs stay shared.
"""
import math
from dataclasses import replace

from .interior_defense import clamp

VERSION='downstream_outcomes_v1'
G4=((.06943184420297371,.17392742256872693),(.33000947820757187,.32607257743127307),
    (.6699905217924281,.32607257743127307),(.9305681557970262,.17392742256872693))
G8=((.019855071751231884,.05061426814518813),(.10166676129318664,.11119051722668724),
    (.2372337950418355,.15685332293894366),(.4082826787521751,.18134189168918099),
    (.5917173212478248,.18134189168918099),(.7627662049581645,.15685332293894366),
    (.8983332387068134,.11119051722668724),(.9801449282487681,.05061426814518813))
BRANCHES=('inaccurate_delivery','late_delivery','shot_clock_turnover','failed_catch','shooting_foul','block','made_fg','missed_fg')


def choice_probabilities(scores):
    """Luce choice with a declared one-point utility unit, not a fitted grade.

    Unlike the historical clipped cubic, negative utility remains ordered.
    Every noticed choice has positive probability; this is not an argmax rule.
    """
    if not scores or any(not math.isfinite(v) for v in scores.values()):raise ValueError('Finite nonempty choice utilities required')
    top=max(scores.values());weights={k:math.exp(v-top) for k,v in scores.items()};total=sum(weights.values())
    return {k:v/total for k,v in weights.items()}


def _cdf(error,scale):return -math.expm1(-max(0,error)/scale)


def _empty():
    return {'expected_points':0.0,'points_second_moment':0.0,'zero_points_probability':0.0,
        'reboundable_miss_probability':0.0,'branches':{k:0.0 for k in BRANCHES},
        'candidate_resolution_calls':0,'shot_plan_evaluations':0,'clock_boundary_evaluations':0,'angle_evaluations':0}


def _failure(result,kind,mass):
    result['branches'][kind]=result['branches'].get(kind,0)+mass;result['zero_points_probability']+=mass


def _shot(result,action,mass):
    from .interior_game import shot_probabilities
    plan=action['plan'];reception=plan['reception'];shot_mass=mass*reception
    _failure(result,'failed_catch',mass-shot_mass)
    p=shot_probabilities(plan['off'],plan['response'],plan['zone'])
    foul=p['foul'];block=p['block_given_no_foul'];make=p['make_given_unblocked']
    points=3 if plan['zone']=='perimeter' else 2;ft=plan['off']['ft_pct']
    result['expected_points']+=shot_mass*p['expected_points']
    result['points_second_moment']+=shot_mass*(foul*(points*ft*(1-ft)+(points*ft)**2)+(1-foul)*(1-block)*make*points*points)
    result['zero_points_probability']+=shot_mass*(foul*(1-ft)**points+(1-foul)*(block+(1-block)*(1-make)))
    result['reboundable_miss_probability']+=shot_mass*p['rebound_probability']
    for name,prob in [('shooting_foul',foul),('block',(1-foul)*block),
                      ('made_fg',(1-foul)*(1-block)*make),('missed_fg',(1-foul)*(1-block)*(1-make))]:
        result['branches'][name]+=shot_mass*prob


def _late_interval(frame,name,option):
    """Exact one-dimensional catch-time/route interval, before shot preparation."""
    radius=option['delivery']['window_radius_m'];flight=option['delivery']['flight_s'];base=frame['elapsed']+option.get('wait_s',0)+flight+.05
    lo=0.0;hi=radius
    if name in ('F03','F04','pop'):
        if name!='pop':hi=min(hi,4*(frame['setup'].roll_window_s-base))
        if frame['screen']:
            from .screen_navigation import distance_time
            screen=frame['screen'];profile=frame['state']['screens']['profiles'][option['receiver_id']]
            end=screen.get('receiver_end',screen['roll_end']);length=math.dist(screen['receiver_start'],end)
            unit=tuple((end[i]-screen['receiver_start'][i])/length for i in (0,1))
            progress=sum((option['target'][i]-screen['receiver_start'][i])*unit[i] for i in (0,1))
            start_time=screen['window_start_s']
            if progress-radius>0:start_time=max(start_time,screen['release_s']+distance_time(progress-radius,profile))
            end_time=screen['window_end_s']
            if progress+radius<length+screen['receiving_exit_m']:
                end_time=min(end_time,screen['release_s']+distance_time(max(0,progress+radius),profile))
            lo=max(lo,4*(start_time-base));hi=min(hi,4*(end_time-base))
    return max(0,min(radius,lo)),max(0,min(radius,hi))


def _clock_interval(frame,name,option,lo,hi,stats):
    from .creation_passing import prepare_delivery,delivery_preparation
    profile=frame['coupled']['profiles'][option['receiver_id']]
    def duration(error):
        stats['clock_boundary_evaluations']+=1
        delivery=prepare_delivery(frame,name,option,error)
        return frame['elapsed']+option.get('wait_s',0)+delivery['flight_s']+delivery['catch_delay_s']+delivery_preparation(profile,name,delivery['quality'])
    # Evaluate inside the open interval. This numerical tolerance affects the
    # integration boundary only, not actual deadlines or sampled resolution.
    inset=(hi-lo)*1e-9
    if duration(lo+inset)>=frame['remaining_s']:return lo
    if duration(hi-inset)<frame['remaining_s']:return hi
    left,right=lo,hi
    for _ in range(20):
        mid=(left+right)/2
        if duration(mid)<frame['remaining_s']:left=mid
        else:right=mid
    return (left+right)/2


def project_candidate(frame,name,options,*,order=4):
    """Expected first resolved event, conditional on current observed stages.

    Only fixed quadrature nodes are supplied to shared candidate resolution.
    The independent future approach-angle prior remains the resolver's uniform
    prior. Rebounds are exposed but receive zero continuation credit here.
    """
    from .creation_passing import resolve_candidate
    from .offense_response import finishing_response,finish_preparation
    if name!='finish' and getattr(frame['spec'],'receipt_policy',None):
        if getattr(frame['spec'],'projection_backend','detailed_python_v1')=='compact_python_v1':
            from .compact_recovery import project_candidate as compact_projection
            return compact_projection(frame,name,options,order=order)
        from .pass_recovery import project_candidate as recovery_projection
        return recovery_projection(frame,name,options,order=order)
    if order not in (4,8):raise ValueError('Bounded quadrature order 4 or 8 required')
    if name not in options:raise ValueError('Only noticed, supported candidates can be projected')
    if not math.isfinite(frame['remaining_s']) or frame['remaining_s']<0:raise ValueError('Finite nonnegative clock required')
    nodes=G4 if order==4 else G8;result=_empty();draws=[.5]*48
    survival=1.0
    if name!='finish' and options[name].get('wait_s',0):
        option=options[name];loss=option['waiting_loss_probability'];survival=1-loss;draws[43]=1.0
        _failure(result,'shot_clock_turnover' if frame['elapsed']+option['wait_s']>=frame['remaining_s'] else 'waiting_loss',loss)
    def fail(kind,mass):_failure(result,kind,mass*survival)
    angle_nodes=((.5,1.0),) if name in ('F06','pop') or (frame['anchor'] is None and not(frame['screen'] and name in ('F03','F04'))) else nodes
    def evaluate(weight,error=None,kind=None):
        from .shot_geometry import contest_at_angle
        action=resolve_candidate(frame,name,options,draws,{},finish_kind_override=kind,
            delivery_error_override=error,include_details=False)
        result['candidate_resolution_calls']+=1
        result['shot_plan_evaluations']+=3 if frame['screen'] and name in ('F03','F04') and action['kind']=='shot' else int(action['kind']=='shot')
        for angle,angle_weight in angle_nodes:
            mass=weight*angle_weight*survival
            if action['elapsed_s']>=frame['remaining_s']:_failure(result,'shot_clock_turnover',mass)
            elif action['kind']=='turnover':_failure(result,action['outcome'],mass)
            else:
                plan=action['plan'];responses=plan.get('_projection_contests',(plan['response'],));chosen=None;strength=-1
                for response in responses:
                    rotated=contest_at_angle(response['_contest_basis'],angle*180) if response else None
                    candidate_strength=rotated['conversion_reduction']+rotated['block_probability'] if rotated else 0
                    if candidate_strength>=strength:chosen=rotated;strength=candidate_strength
                _shot(result,{**action,'plan':{**plan,'response':chosen}},mass);result['angle_evaluations']+=1
    if name=='finish':
        weights=frame['coupled']['spec'].finish_mix[:4];total=sum(weights)
        for kind,weight in zip(('layup','contact_layup','floater','dunk'),weights,strict=True):
            if not weight:continue
            used=finishing_response(frame['coupled']['profiles'][frame['creator_id']],kind)['finish']
            if frame['elapsed']+finish_preparation(used)>=frame['remaining_s']:_failure(result,'shot_clock_turnover',weight/total)
            else:evaluate(weight/total,kind=kind)
    else:
        option=options[name];delivery=option['delivery'];radius=delivery['window_radius_m'];scale=delivery['error_scale_m']
        accurate=_cdf(radius,scale)
        elapsed=frame['elapsed']+option.get('wait_s',0)
        fail('shot_clock_turnover' if elapsed+delivery['flight_s']>=frame['remaining_s'] else 'inaccurate_delivery',1-accurate)
        catch_limit=max(0,min(radius,4*(frame['remaining_s']-elapsed-delivery['flight_s']-.05)))
        catch_in_time=_cdf(catch_limit,scale);fail('shot_clock_turnover',accurate-catch_in_time)
        lo,hi=_late_interval(frame,name,option);hi=min(hi,catch_limit)
        if hi<=lo:fail('late_delivery',catch_in_time)
        else:
            mass=_cdf(hi,scale)-_cdf(lo,scale);fail('late_delivery',catch_in_time-mass)
            clock_hi=_clock_interval(frame,name,option,lo,hi,result)
            qlo,qhi=_cdf(lo,scale),_cdf(clock_hi,scale)
            fail('shot_clock_turnover',mass-(qhi-qlo))
            for node,weight in nodes:
                q=qlo+(qhi-qlo)*node
                error=-math.log1p(-q)*scale
                evaluate((qhi-qlo)*weight,error=error)
    result.update(policy=VERSION,conditional_on='current handling retained; access/help and this option already observed',
        quadrature_order=order,rebound_continuation_credit=0.0,
        receiver_id=options[name].get('receiver_id'),
        source_revisions={'creator':frame['creator'].revision,'receiver':frame['coupled']['profiles'][options[name]['receiver_id']].revision if name!='finish' else None},
        preference_weight=frame['coupled']['profiles'][options[name]['receiver_id']].willingness if name in ('F06','pop') else 1.0)
    return result


def reset_projection(frame,candidates):
    """Bounded one-fresh-attempt proxy; no recursive planning or rescreen."""
    from .creation_passing import containment_response
    from .offense_response import finish_preparation,finishing_response,release_preparation,receiving_preparation
    remaining=frame['remaining_s']-frame['elapsed'];after=remaining-frame['spec'].reset_cost_s
    available={k:v for k,v in candidates.items() if k in ('finish','F06')}
    result={'policy':'one_attempt_discounted_proxy_v1','continuation_depth':1,'expected_points':0.0,'zero_points_probability':1.0,
        'remaining_after_reset_s':after,'windowed_roll_reused':False,'new_opportunities_assumed':False,
        'rebound_continuation_credit':0.0,'reference_candidate':None,'approximation':'reuse a currently noticed nonwindowed chance; no guaranteed future discovery or possession value'}
    if after<=0 or not available:return result
    name=max(available,key=lambda k:available[k]['expected_points']);reference=available[name]
    next_drive=containment_response(frame['creator'],frame['defender'],replace(frame['setup'],screen_separation_m=0),frame['c'])
    if name=='finish':
        profile=frame['coupled']['profiles'][frame['creator_id']]
        prep=min(finish_preparation(finishing_response(profile,kind)['finish']) for kind,w in zip(('layup','contact_layup','floater','dunk'),frame['coupled']['spec'].finish_mix[:4],strict=True) if w)
        notice=next_drive['beat_probability']*(.10+.85*frame['creator'].skill('S20'))
    else:
        profile=frame['coupled']['profiles'][reference['receiver_id']]
        prep=release_preparation(profile)+receiving_preparation(profile,1)+.05
        # Do not grant zero-cost instantaneous re-delivery in the proxy.
        from .creation_passing import delivery_response
        location=frame['coupled']['deployments'][profile.player_id]
        prep+=delivery_response(frame['creator'],'F06',math.dist(frame['ball'],(location.perimeter_x_m,location.perimeter_y_m)),next_drive['pressure'],1,frame['c'])['flight_s']
        notice=frame['c'].bad_read_floor+(1-frame['c'].bad_read_floor)*frame['creator'].pass_skill('F06','recognition')
    required=next_drive['attacker_clear_s']+frame['c'].decision_delay_s*(1-frame['creator'].skill('S20'))+prep
    result.update(reference_candidate=name,minimum_future_completion_s=required,future_handling_probability=next_drive['handling_loss_probability'])
    if after<=required:return result
    opportunity=clamp(after/remaining)*notice*(1-frame['c'].wrong_choice*(1-frame['creator'].skill('S20')))*(1-next_drive['handling_loss_probability'])
    result.update(expected_points=opportunity*reference['expected_points'],zero_points_probability=1-opportunity*(1-reference['zero_points_probability']),
        opportunity_discount=opportunity,reference_expected_points=reference['expected_points'])
    return result


def project_choices(frame,options,*,order=4):
    candidates={name:project_candidate(frame,name,options,order=order) for name in options}
    candidates['reset']=reset_projection(frame,candidates)
    scores={name:value['expected_points']*value.get('preference_weight',1)-(1-frame['creator'].risk)*.85*value['zero_points_probability'] for name,value in candidates.items()}
    probabilities=choice_probabilities(scores);bad_probability=frame['c'].wrong_choice*(1-frame['creator'].skill('S20'));worst=min(scores,key=scores.get)
    result={'policy':VERSION,'candidates':candidates,'scores':scores,'good_choice_probabilities':probabilities,
        'bad_choice_probability':bad_probability,
        'effective_choice_probabilities':{k:(1-bad_probability)*v+bad_probability*(k==worst) for k,v in probabilities.items()},
        'current_handling_sunk':True,'current_handling_probability':frame['drive']['handling_loss_probability'],
        'risk_policy':'risk appetite reduces downside aversion; zero-point failure is never an upside reward',
        'willingness_policy':'F06 willingness shapes selection utility separately from predicted conditional conversion',
        'candidate_count':len(candidates),'candidate_resolution_calls':sum(v.get('candidate_resolution_calls',0) for v in candidates.values()),
        'clock_boundary_evaluations':sum(v.get('clock_boundary_evaluations',0) for v in candidates.values()),
        'shot_plan_evaluations':sum(v.get('shot_plan_evaluations',0) for v in candidates.values())}
    if getattr(frame['spec'],'receipt_policy',None):result.update(receipt_policy=frame['spec'].receipt_policy,
        recovery_geometry_evaluations=sum(v.get('recovery_geometry_evaluations',0) for v in candidates.values()))
    if getattr(frame['spec'],'projection_backend','detailed_python_v1')=='compact_python_v1':
        result['projection_backend']='compact_python_v1'
        provider=frame.get('_geometry_provider_override',getattr(frame['spec'],'geometry_provider',None))
        if provider is not None:
            ordered=sorted(scores.values())
            if any(abs(a-b)<=1e-9 for a,b in zip(ordered,ordered[1:])):
                attempt={k:v.get('compact_evaluator') for k,v in candidates.items() if 'compact_evaluator' in v}
                result=project_choices({**frame,'_geometry_provider_override':None},options,order=order)
                result.update(geometry_provider_revision=provider.revision,native_choice_tie_python_fallback=True,native_attempt_before_choice_fallback=attempt)
            else:result.update(geometry_provider_revision=provider.revision,native_choice_tie_python_fallback=False)
    return result


def resolve_projected_choice(frame,options,draws,record):
    from .creation_passing import resolve_candidate
    projection=project_choices(frame,options);scores=projection['scores'];creator=frame['creator'];c=frame['c']
    if draws[32]<c.wrong_choice*(1-creator.skill('S20')):
        choice=min(scores,key=scores.get);record['bad_choice']=True
    else:
        names=list(scores);target=draws[33];choice=names[-1]
        for key in names:
            weight=projection['good_choice_probabilities'][key]
            target-=weight
            if target<0:choice=key;break
    record.update(choice=choice,choice_scores=scores,choice_projection=projection,missed_reads=[k for k,v in record['noticed_options'].items() if not v])
    if choice=='reset':return {'kind':'reset','record':record,'elapsed_s':frame['elapsed']+frame['spec'].reset_cost_s,
        'reason':'missed_read_or_contained' if not options else 'clock_context_continuation_or_imperfect_choice'}
    return resolve_candidate(frame,choice,options,draws,record)
