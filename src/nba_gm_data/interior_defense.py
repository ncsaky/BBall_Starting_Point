"""Introductory interior-defense experiment. No production calibration/activation.

C27/C32 use raw technique, explicit physical observations and deployed context.
C36 reads the same response. Nothing here edits talents or infers missing tests.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields

from .player_model import PlayerInputs
from .experimental_inputs import common_reader,interpretation_revision,VERSION as INPUT_INTERPRETATION_VERSION

FORMULA_VERSION = 'interior_experiment_2026_11_13_v1'
CAPACITY_SCALE = 'interior_capacity_scenario_v1'
SKILL_SCALE = 'interior_technique_provisional_v1'


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Coefficients:
    """Explicit experimental constants, not fitted/approved NBA coefficients."""
    position_distance_m: float = .65
    spacing_distance_m: float = 1.2
    poa_extra_window_s: float = .35
    arrival_margin_s: float = .25
    reach_transition_cm: float = 55.0
    max_conversion_reduction: float = .24
    max_block_probability: float = .24
    max_avoidance: float = .30
    max_contest_foul: float = .16
    late_foul: float = .06
    synthetic_force_reference_n: float = 1000.0
    synthetic_balance_reference_s: float = 1.0

    def __post_init__(self):
        for key,value in asdict(self).items():
            if type(value) not in (int,float) or not math.isfinite(value) or value < 0:
                raise ValueError(f'Invalid experimental coefficient {key}')
        if min(self.arrival_margin_s,self.reach_transition_cm,self.synthetic_force_reference_n,self.synthetic_balance_reference_s) <= 0:
            raise ValueError('Response transitions must be positive')
        if max(self.max_conversion_reduction,self.max_block_probability,self.max_avoidance,self.max_contest_foul,self.late_foul)>1:
            raise ValueError('Response probability coefficients cannot exceed one')


@dataclass(frozen=True)
class ArrivalContext:
    """Declared deployment/opportunity conditions; not permanent new talents.

    Recognition delay is supplied explicitly (possibly from a separate S38
    scenario). This does not implement the complete C26/helper family.
    """
    distance_m: float = 0.0
    window_s: float = 1.5
    recognition_delay_s: float = .15
    anchor_available: float = 1.0
    spacing: float = .5
    poa_containment: float = .5
    release_height_cm: float = 305.0
    capacity_factor: float = 1.0
    reference: str = 'declared synthetic reference; not tracking data'

    def __post_init__(self):
        for field in fields(self):
            key=field.name;value=getattr(self,key)
            if key=='reference':
                if not isinstance(value,str) or not value.strip():raise ValueError('Reference conditions required')
            elif type(value) not in (int,float) or not math.isfinite(value) or value<0:
                raise ValueError(f'Invalid arrival context {key}')
        if max(self.anchor_available,self.spacing,self.poa_containment,self.capacity_factor)>1 or self.release_height_cm<=0:
            raise ValueError('Context probabilities/capacity must be in [0,1] and height positive')


@dataclass(frozen=True)
class InteriorProfile:
    inputs: PlayerInputs
    positioning: float
    technique: float
    legal: float
    standing_reach_cm: float
    acceleration_m_s2: float
    strength_capacity: float
    balance_capacity: float
    jump_cm: float
    jump_choice: float
    conservative_choice: float
    stay_down_choice: float
    coefficients: Coefficients
    revision: str
    input_contract: str
    wingspan_cm: float | None = None


def compile_profile(inputs: PlayerInputs, coefficients: Coefficients = Coefficients(), *, research_scenario: bool = False) -> InteriorProfile:
    """Reject incomplete inputs; do not silently insert 50s or guessed SI units."""
    doc=inputs.to_dict(); rows=doc['inputs']
    reader=common_reader(inputs,doc)
    if reader and research_scenario:raise ValueError('Do not mix common interpretation and legacy research flag')
    if reader and (coefficients.synthetic_force_reference_n!=1000 or coefficients.synthetic_balance_reference_s!=1):raise ValueError('Common interpretation owns capacity references; do not mix legacy coefficient overrides')
    def value(key):
        row=rows.get(key)
        if row is None or row['status']=='unknown':raise ValueError(f'{key}: explicit estimate/observation required for this scenario')
        return row['value']
    def skill(key):
        if reader:return reader.grade(key)
        item=value(key)
        expected_scale='research_technique_reference_v0_2026_11_13' if research_scenario else SKILL_SCALE
        if item['scale']!=expected_scale:raise ValueError(f'{key}: declare the provisional experimental skill scale')
        return item['grade']/100
    def measurement(key,metric,unit):
        if reader:return reader.measurement(key)
        if research_scenario:
            contracts={
                'P03':(('hypothetical_standing_reach','H1 anthropometric fixture: height+70cm+0.5*(span-height); unvalidated, not inferred player measurement'),
                       ('normalized_reach','equal-geometry experimental control, not actual player measurement')),
                'P05':(('reference_acceleration','DIMENSIONAL FIXTURE ONLY; no actual player/protocol test performed'),),
                'P10':(('reference_jump_reach_gain','DIMENSIONAL FIXTURE ONLY; no actual player/protocol test performed'),),
            }
            matches=[m for m in value(key)['measurements'] if (m['metric'],m['protocol']) in contracts[key] and m['unit']==unit and rows[key]['status']=='estimated']
        else:
            matches=[m for m in value(key)['measurements'] if m['metric']==metric and m['unit']==unit and m['protocol']=='interior_scenario_reference_v1']
        if len(matches)!=1:raise ValueError(f'{key}: one supported {metric} in {unit} with a declared scenario protocol is required')
        return matches[0]['value']
    def capacity(key):
        if reader:return reader.capacity(key)
        if research_scenario:
            metric,unit=('reference_contact_force','N') if key=='P08' else ('reference_balance_recovery_time','s')
            measures=[m for m in value(key)['measurements'] if m['metric']==metric and m['unit']==unit and m['protocol']=='DIMENSIONAL FIXTURE ONLY; no actual player/protocol test performed']
            if len(measures)!=1 or rows[key]['status']!='estimated':raise ValueError(f'{key}: explicit research synthetic fixture protocol required')
            number=measures[0]['value']
            return number/(number+coefficients.synthetic_force_reference_n) if key=='P08' else coefficients.synthetic_balance_reference_s/(number+coefficients.synthetic_balance_reference_s)
        item=value(key).get('display_grade')
        if item is None or item['scale']!=CAPACITY_SCALE:
            raise ValueError(f'{key}: explicit scenario capacity assessment required; not an inferred physical test')
        return item['grade']/100
    choices=value('T16')
    expected_condition='reference_opportunity' if research_scenario else 'available_interior_contest'
    if not reader and (len(choices['rows'])!=1 or choices['rows'][0]['condition']!=expected_condition):
        raise ValueError('T16: this partial consumer supports one declared available_interior_contest condition')
    p=reader.distribution('T16') if reader else choices['rows'][0]['probabilities']
    profile=InteriorProfile(inputs,skill('S36'),skill('S37'),skill('S45'),
        measurement('P03','standing_reach','cm'),measurement('P05','acceleration','m/s2'),
        capacity('P08'),capacity('P09'),measurement('P10','vertical_jump','cm'),
        p['jump'],p['conservative_contest'],p['stay_down'],coefficients,
        fingerprint(interpretation_revision({'formula':FORMULA_VERSION,'inputs':doc,'coefficients':asdict(coefficients),'research_scenario':research_scenario},inputs)),
        INPUT_INTERPRETATION_VERSION if reader else 'research_explicit_synthetic_v1' if research_scenario else 'controlled_synthetic_v1')
    if profile.acceleration_m_s2<=0:raise ValueError('Positive acceleration required for travel-time resolution')
    span=rows.get('P02')
    if span and span['status']!='unknown':
        matches=[{'value':reader.measurement('P02')}] if reader else [m for m in span['value']['measurements'] if m['unit']=='cm' and m['metric'] in ('wingspan','reported_wingspan','normalized_span')]
        if len(matches)==1:
            from dataclasses import replace
            profile=replace(profile,wingspan_cm=matches[0]['value'])
    return profile


def interior_response(profile: InteriorProfile, context: ArrivalContext, *, zone: str = 'rim', geometry=None, arrival_override_s=None, defender_route_origin_m=None, diagnostics=True, bearing_policy='legacy_bearing_v1') -> dict:
    """C27 at a location, with partial deployed C32 availability/choices.

    Height/span are not added to supplied standing reach. Positioning determines
    the route; acceleration determines travel; technique/control determine the
    quality of a reachable contest. No C36 input or legacy effective rim grade.
    """
    if zone not in ('rim','short_paint','perimeter'):raise ValueError('Unsupported experimental spatial zone')
    if geometry is not None:
        from .shot_geometry import geometry_response
        return geometry_response(profile,context,zone,geometry,arrival_override_s=arrival_override_s,bearing_policy=bearing_policy,
            **({'defender_route_origin_m':defender_route_origin_m} if defender_route_origin_m is not None else {}),
            **({'diagnostics':False} if not diagnostics else {}))
    if defender_route_origin_m is not None:raise ValueError('Route bearing requires declared shot geometry')
    c=profile.coefficients
    distance=context.distance_m+(1-profile.positioning)*c.position_distance_m+context.spacing*c.spacing_distance_m
    travel=math.sqrt(2*distance/(profile.acceleration_m_s2*max(.05,context.capacity_factor)))
    arrival=context.recognition_delay_s+travel
    window=context.window_s+context.poa_containment*c.poa_extra_window_s
    timely=clamp((window-arrival)/c.arrival_margin_s)
    availability=context.anchor_available*timely if zone!='perimeter' else 0.0
    reach=profile.standing_reach_cm+profile.jump_cm*context.capacity_factor
    geometry=clamp((reach-context.release_height_cm+c.reach_transition_cm)/c.reach_transition_cm)
    control=(.5+.25*profile.strength_capacity+.25*profile.balance_capacity)
    alignment=.5+.5*profile.positioning
    quality=profile.technique*geometry*control*alignment
    commitment=profile.jump_choice+profile.conservative_choice*.65+profile.stay_down_choice*.10
    # Spacing affects access context, not raw contest skill. Its opposing pull
    # and POA effects are supplied by the caller's declared distance/window.
    zone_weight=1.0 if zone=='rim' else .35 if zone=='short_paint' else 0.0
    influence=availability*zone_weight
    late=context.anchor_available*(1-timely)*clamp(1-abs(arrival-window)/c.arrival_margin_s)*zone_weight
    response={
        'formula_version':FORMULA_VERSION,'input_revision':profile.revision,'context':asdict(context),
        'zone':zone,'arrival_s':arrival,'window_s':window,'travel_s':travel,'timely_fraction':timely,
        'coverage_available':influence,'reachable_height_cm':reach,'geometry_fraction':geometry,
        'contest_alignment':alignment,'contest_quality':quality*influence,
        'conversion_reduction':c.max_conversion_reduction*quality*commitment*influence,
        'block_probability':c.max_block_probability*quality*profile.jump_choice*influence,
        'foul_probability':clamp(c.max_contest_foul*influence*(1-profile.legal)*commitment
                            +c.late_foul*late*profile.jump_choice*(1-profile.legal)),
        'avoidance_probability':c.max_avoidance*quality*commitment*influence,
    }
    return response


def reference_report(profile: InteriorProfile, context: ArrivalContext = ArrivalContext()) -> dict:
    responses={zone:interior_response(profile,context,zone=zone) for zone in ('rim','short_paint','perimeter')}
    rim=responses['rim']
    # Readout only. This number is never passed back into game resolution.
    saved=2*(.65-(1-rim['block_probability'])*clamp(.65-rim['conversion_reduction']))
    return {'formula_version':FORMULA_VERSION,'input_revision':profile.revision,
        'raw_inputs':profile.inputs.to_dict(),'input_contract':profile.input_contract,'coefficients':asdict(profile.coefficients),
        'C27':{'status':'experimental_partial','responses':responses},
        'C32':{'status':'interior_slice_only','reference_conditions':asdict(context),'zones':responses},
        'C36':{'status':'derived_readout_only','conversion_points_prevented_per_100_rim_fga':100*saved,
               'reference_avoidance_probability':rim['avoidance_probability'],
               'scope':'conditional conversion/block readout; foul/redirect costs reported separately, not net overall defense'},
        'R18':{'status':'partial_not_a_role_grade','represented':['interior positioning','contest execution','legal contest risk','declared arrival availability'],
               'unimplemented':['C21 defensive rebounding','C22 box-out support','full C29 responsibility/communication','full C32 defense']}}


@dataclass(frozen=True)
class Anchor:
    team_id: str
    profile: InteriorProfile
    context: ArrivalContext = ArrivalContext()


@dataclass(frozen=True)
class InteriorExperiment:
    """Explicit caller-owned switch; never read from careers or global settings.

    Each team must be explicitly configured with one anchor or a documented
    no-anchor counterfactual. No implicit league-wide unknown-player fallback.
    """
    anchors: tuple[Anchor,...]
    no_anchor_team_ids: tuple[str,...] = ()
    possessions: int = 96
    offense: object | None = None

    def __post_init__(self):
        ids=[a.team_id for a in self.anchors]+list(self.no_anchor_team_ids)
        if len(set(ids))!=len(ids):raise ValueError('Duplicate experimental team coverage')
        if type(self.possessions) is not int or not 1<=self.possessions<=120:raise ValueError('Bounded 1–120 regulation possessions required')
        if not isinstance(self.anchors,tuple) or not isinstance(self.no_anchor_team_ids,tuple):raise ValueError('Immutable tuples required')

    def anchor(self,team_id):
        for anchor in self.anchors:
            if anchor.team_id==team_id:return anchor
        if team_id not in self.no_anchor_team_ids:raise ValueError(f'{team_id}: explicitly configure an anchor or no-anchor control')
        return None

    @property
    def revision(self):
        data={'formula':FORMULA_VERSION,'anchors':[(a.team_id,a.profile.revision,asdict(a.context)) for a in self.anchors],
              'no_anchor':self.no_anchor_team_ids,'possessions':self.possessions}
        if self.offense is not None:data['combined_offense_revision']=self.offense.revision
        return fingerprint(data)
