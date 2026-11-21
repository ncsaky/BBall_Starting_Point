"""Explicit interpretation of experimental inputs; never rewrites player facts.

The view owns one immutable PlayerInputs snapshot and a trial response contract.
Aliases describe one quantity, not extra observations/bonuses. Historical callers
without this view retain their existing strict compiler contracts.
"""
from dataclasses import asdict,dataclass,field
import hashlib
import json
import math
from .player_model import PlayerInputs

VERSION='experimental_input_interpretation_2026_11_14_v1'
NATIVE_TECHNIQUE='interior_technique_provisional_v1'
RESEARCH_TECHNIQUE='research_technique_reference_v0_2026_11_13'
CAPACITY_SCALE='interior_capacity_scenario_v1'
FT_PROXY='research_FT_conversion_percent_proxy_v1'
NATIVE_PROTOCOL='interior_scenario_reference_v1'
DIMENSIONAL='DIMENSIONAL FIXTURE ONLY; no actual player/protocol test performed'
OFFENSE_CAPACITY='DIMENSIONAL FIXTURE ONLY, not observed protocol'
MOVEMENT='synthetic dimensional fixture, no human measurement'
REPORTED='canonical report; original physical measurement/date/footwear unknown, conversion only'
REPORTED_SCREEN='reported canonical dimensions; original date/footwear/protocol unknown; conversion only'
REPORTED_CREATION='canonical report, original measurement/footwear/date unverified; exact unit conversion only'
REPORTED_POP='Canonical reported value; original measurement date, footwear and protocol unknown; unit conversion only.'
H1='H1 anthropometric fixture: height+70cm+0.5*(span-height); unvalidated, not inferred player measurement'
OFFENSE_REACH='unvalidated H1 dimensional fixture, not measured reach or shooting release point'


def _hash(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class InputInterpretation:
    # Trial, not a calibrated identity between independently measured scales.
    technique_mapping: str='research_reference_linear_index_trial_v1'
    research_gain: float=1.0
    research_anchor: float=.65
    two_point_rim_fraction: float=.7
    force_reference_n: float=1000.0
    balance_reference_s: float=1.0
    screen_action_policy: str='reject_pop'

    def __post_init__(self):
        if self.technique_mapping!='research_reference_linear_index_trial_v1':raise ValueError('Unsupported technique response interpretation')
        for v in (self.research_gain,self.research_anchor,self.two_point_rim_fraction,self.force_reference_n,self.balance_reference_s):
            if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('Finite numeric interpretation controls required')
        if self.research_gain<=0 or not 0<=self.research_anchor<=1 or not 0<=self.two_point_rim_fraction<=1 or min(self.force_reference_n,self.balance_reference_s)<=0:raise ValueError('Invalid interpretation response controls')
        if self.screen_action_policy not in ('reject_pop','condition_on_supported'):raise ValueError('Explicit supported-action screen policy required')

    @property
    def revision(self):return _hash({'version':VERSION,'contract':asdict(self)})


@dataclass(frozen=True)
class InterpretedInputs:
    source: PlayerInputs
    contract: InputInterpretation
    revision: str=field(init=False)

    def __post_init__(self):
        if not isinstance(self.source,PlayerInputs) or not isinstance(self.contract,InputInterpretation):raise ValueError('One validated source snapshot and explicit interpretation required')
        object.__setattr__(self,'revision',_hash({'source':self.source.to_dict(),'interpretation':self.contract.revision}))

    @property
    def player_id(self):return self.source.player_id
    def to_dict(self):return self.source.to_dict()
    def input(self,key):return self.source.input(key)


def common_reader(inputs,document=None):
    if isinstance(inputs,LeagueInterpretedInputs):return LeagueInputReader(inputs,document)  # Stage 2 league bridge
    return InputReader(inputs,document) if isinstance(inputs,InterpretedInputs) else None


def interpretation_revision(data,inputs):
    return {**data,'common_input_interpretation':inputs.revision} if isinstance(inputs,InterpretedInputs) else data


def same_input_snapshot(a,b):
    # These types own immutable serialized inputs. Self-comparison cannot
    # differ, and need not decode two identical private document copies.
    if a is b and isinstance(a,(PlayerInputs,InterpretedInputs)):return True
    if isinstance(a,InterpretedInputs) or isinstance(b,InterpretedInputs):
        return isinstance(a,InterpretedInputs) and isinstance(b,InterpretedInputs) and a.contract==b.contract and a.to_dict()==b.to_dict()
    return a.to_dict()==b.to_dict()


# Each accepted tuple is a named semantic quantity with units already stored by
# the schema. The old *_inches/*_lbs labels below already contain cm/kg, so no
# second inch/lb conversion occurs. Unsupported protocols are not guessed.
ALIASES={
 'P01':{('height','cm',NATIVE_PROTOCOL),('height_inches','cm',REPORTED)},
 'P02':{('wingspan','cm',NATIVE_PROTOCOL),('wingspan_inches','cm',REPORTED),('reported_wingspan','cm','alias of same converted canonical report, not independent measurement'),('normalized_span','cm','equal-geometry experimental control, not actual player measurement')},
 'P03':{('standing_reach','cm',NATIVE_PROTOCOL),('hypothetical_standing_reach','cm',OFFENSE_REACH),('hypothetical_standing_reach','cm',H1),('normalized_reach','cm','equal-geometry experimental control, not actual player measurement')},
 'P04':{('body_mass','kg',NATIVE_PROTOCOL),('weight_lbs','kg',REPORTED)},
 'P05':{('acceleration','m/s2',NATIVE_PROTOCOL),('fixture_acceleration','m/s2',MOVEMENT),('reference_acceleration','m/s2',DIMENSIONAL)},
 'P06':{('straight_line_speed','m/s',NATIVE_PROTOCOL),('fixture_speed','m/s',MOVEMENT)},
 'P07':{('lateral_speed','m/s',NATIVE_PROTOCOL),('fixture_lateral_speed','m/s',MOVEMENT),('fixture_lateral_speed','m/s','synthetic movement axis, not observed speed')},
 'P08':{('synthetic_reference_capacity','N',OFFENSE_CAPACITY),('reference_contact_force','N',DIMENSIONAL)},
 'P09':{('synthetic_reference_capacity','s',OFFENSE_CAPACITY),('reference_balance_recovery_time','s',DIMENSIONAL)},
 'P10':{('vertical_jump','cm',NATIVE_PROTOCOL),('hypothetical_jump_gain','cm','synthetic reference, no jump test performed'),('reference_jump_reach_gain','cm',DIMENSIONAL)},
}
for _key,_metric,_unit in (('P01','height_inches','cm'),('P02','wingspan_inches','cm'),('P04','weight_lbs','kg')):
    ALIASES[_key].add((_metric,_unit,REPORTED_SCREEN))
    # Final screen/pop packet uses the same already-converted quantities and
    # explicit uncertainty with this exact protocol label. Do not reconvert.
    ALIASES[_key].add((_metric,_unit,REPORTED_POP))
for _key,_metric,_unit in (('P01','listed_height','cm'),('P02','reported_wingspan','cm'),('P04','listed_body_mass','kg')):
    ALIASES[_key].add((_metric,_unit,REPORTED_CREATION))
# Explicit counterfactual quantities and dated alternatives keep their meaning;
# they are not relabeled as current athlete measurements or H1 formula outputs.
SCENARIO_GEOMETRY='explicit action-pilot geometry control; not a reported athlete measurement'
for _key,_metric,_unit in (('P01','scenario_height','cm'),('P02','scenario_wingspan','cm'),('P03','scenario_standing_reach','cm'),('P04','scenario_body_mass','kg')):
    ALIASES[_key].add((_metric,_unit,SCENARIO_GEOMETRY))
ALIASES['P03'].update({('historical_standing_reach','cm','2013 NBA combine historical report; proposed geometry anchor, not measured2026 current reach'),
    ('historical_standing_reach','cm','2021 reported historical reach alternative; not measured 2026 current reach')})
CONDITIONS={
 'T01':{'available_opportunity','reference_opportunity'},'T02':{'available_opportunity','reference_opportunity'},
 'T03':{'available_opportunity','reference_shot'},'T16':{'available_interior_contest','reference_opportunity'},
 'T11':{'on_ball_screen','screen_followup_trial'},
}


class InputReader:
    def __init__(self,inputs,document=None):
        self.inputs=inputs;self.contract=inputs.contract;self.rows=(document if document is not None else inputs.to_dict())['inputs']
        self.audit={}

    def value(self,key):
        row=self.rows.get(key)
        if row is None or row['status']=='unknown':raise ValueError(f'{key}: explicit common-interpretation input required')
        return row['value']

    def grade(self,key):
        v=self.value(key);scale=v['scale'];index=v['grade']/100
        if key=='S07':
            if scale not in (FT_PROXY,NATIVE_TECHNIQUE):raise ValueError('S07: FT percentage proxy or explicit native FT technique required')
            rule='FT proxy probability' if scale==FT_PROXY else 'native FT technique index'
        elif scale==NATIVE_TECHNIQUE:rule='historical native index grade/100'
        elif scale==RESEARCH_TECHNIQUE:
            index=max(0,min(1,self.contract.research_anchor+self.contract.research_gain*(index-self.contract.research_anchor)))
            rule=self.contract.technique_mapping
        else:raise ValueError(f'{key}: unsupported common technique scale {scale}')
        self.audit[key]={'rule':rule,'raw_value':v,'response_index':index,'claim':'declared experimental response, not measured scale equivalence'}
        return index

    def free_throw(self):
        index=self.grade('S07');proxy=self.value('S07')['scale']==FT_PROXY
        probability=index if proxy else .45+.50*index
        self.audit['S07']['conversion_probability']=probability
        self.audit['S07']['conversion_rule']='percent/100' if proxy else '.45 + .50 * native technique index'
        return probability

    def measurement(self,key):
        v=self.value(key);measures=v.get('measurements',[])
        if not measures:raise ValueError(f'{key}: explicit dimensional quantity required; grades are not measurements')
        accepted=[]
        for m in measures:
            if (m['metric'],m['unit'],m['protocol']) not in ALIASES.get(key,set()):raise ValueError(f'{key}: unsupported quantity/unit/protocol alias')
            if m['value']<=0 and key not in ('P09','P10'):raise ValueError(f'{key}: positive dimensional control required')
            # Synthetic protocols must not be mislabeled observed athlete tests.
            if m['protocol'] not in (REPORTED,REPORTED_SCREEN,REPORTED_CREATION,'alias of same converted canonical report, not independent measurement') and self.rows[key]['status']!='estimated':raise ValueError(f'{key}: synthetic dimensional control must remain estimated')
            accepted.append(m['value'])
        if any(not math.isclose(x,accepted[0],rel_tol=1e-12,abs_tol=1e-9) for x in accepted[1:]):raise ValueError(f'{key}: conflicting dimensional aliases for one input')
        self.audit[key]={'rule':'quantity alias consensus in stored units; no extra measurement bonus','aliases':measures,'value':accepted[0],'unit':measures[0]['unit']}
        return accepted[0]

    def capacity(self,key):
        v=self.value(key);display=v.get('display_grade');from_measure=None
        if v.get('measurements'):
            number=self.measurement(key)
            from_measure=number/(number+self.contract.force_reference_n) if key=='P08' else self.contract.balance_reference_s/(number+self.contract.balance_reference_s)
        from_display=None
        if display is not None:
            if display['scale']!=CAPACITY_SCALE:raise ValueError(f'{key}: unsupported capacity response scale')
            from_display=display['grade']/100
        if from_measure is None and from_display is None:raise ValueError(f'{key}: explicit capacity representation required')
        if from_measure is not None and from_display is not None and not math.isclose(from_measure,from_display,rel_tol=1e-12,abs_tol=1e-9):raise ValueError(f'{key}: force/time and display response disagree')
        result=from_measure if from_measure is not None else from_display
        self.audit.setdefault(key,{}).update(response=result,rule='F/(F+reference N)' if key=='P08' and from_measure is not None else 'reference s/(time+reference s)' if from_measure is not None else 'declared native capacity index; no inferred N or seconds')
        return result

    def distribution(self,key,*,allow_pop=False):
        v=self.value(key);rows=v['rows']
        if len(rows)!=1 or rows[0]['condition'] not in CONDITIONS[key]:raise ValueError(f'{key}: unsupported scenario condition')
        probabilities=dict(rows[0]['probabilities']);rule='declared matched-opportunity condition; raw preference not rewritten'
        if key=='T02' and set(probabilities)=={'two_point','three_point'}:
            if v.get('spatial_reference')!='two_bin_experimental_2pt_3pt_v1':raise ValueError('T02: unsupported two-bin spatial reference')
            q=probabilities['two_point'];r=self.contract.two_point_rim_fraction
            probabilities={'rim':q*r,'short_paint':q*(1-r),'perimeter':probabilities['three_point']};rule='explicit controlled rim split within two-point opportunity'
        if key=='T11' and not allow_pop:
            excluded=probabilities['pop']
            if excluded and self.contract.screen_action_policy!='condition_on_supported':raise ValueError('T11: nonzero pop requires explicit supported-action conditioning')
            supported=1-excluded
            if supported<=0:raise ValueError('T11: no supported screen action mass')
            probabilities={k:probabilities[k]/supported for k in ('screen','roll','slip')}
            rule='condition on supported screen/roll/slip; pop remains in raw snapshot'
        self.audit[key]={'rule':rule,'condition':rows[0]['condition'],'raw_probabilities':rows[0]['probabilities'],'response_probabilities':probabilities}
        if key=='T11':self.audit[key]['excluded_pop_mass']=0 if allow_pop else excluded
        return probabilities


# --- Stage 2 league bridge (S2-SEAM-SHOOTING, 2026-11-21) -----------------------------------------------------
# The league's estimated inputs (data/canonical/player_inputs_2026_27.json, built by input_estimator) use their own
# scale and protocol labels. Snapshots wrapped as LeagueInterpretedInputs (by stage2.league_inputs) are read by
# LeagueInputReader, which accepts those labels as the SAME named quantities and otherwise defers to InputReader.
# Nothing is converted except the declared technique index (grade/100, the native index rule). Unit conversions the
# league file does not carry (P05 acceleration) are added by stage2.league_inputs under their own protocol label.
# InputReader, InterpretedInputs and the experiment snapshots are unchanged (their source is pinned by tests).
LEAGUE_TECHNIQUE='e2_technique_reference_v1_50_functional_75_strong_90_exceptional'
LEAGUE_REPORTED='listed report; measurement date/protocol unverified'
LEAGUE_PRIOR='uncertain positional/anthropometric prior; not a measurement'
LEAGUE_JUMP_COMBINE='NBA Draft Combine standing vertical, age-adjusted, blended with in-game proxies'
LEAGUE_JUMP_PROXY='size, position and in-game proxy estimate; no jump test'
LEAGUE_ACCELERATION='stage2 bridge: league rank of the P05 grade on the 2000-2025 combine three-quarter sprint times; a = 2d/t^2; not a test of this player'
LEAGUE_T02_REGIONS='rim <4ft; short_paint 4-14ft; midrange 14ft to arc; three beyond arc; coarse regions, no measured heatmap'
# Additive aliases: league protocol labels for the same quantities (distinct labels; no existing entry changes).
ALIASES['P01'].add(('standing_height','cm',LEAGUE_REPORTED))
ALIASES['P02'].update({('arm_span','cm',LEAGUE_REPORTED),('arm_span','cm',LEAGUE_PRIOR)})
ALIASES['P03'].add(('standing_reach','cm',LEAGUE_PRIOR))
ALIASES['P04'].update({('body_mass','kg',LEAGUE_REPORTED),('body_mass','kg',LEAGUE_PRIOR)})
ALIASES['P05'].add(('acceleration','m/s2',LEAGUE_ACCELERATION))
ALIASES['P10'].update({('jump_height','cm',LEAGUE_JUMP_COMBINE),('jump_height','cm',LEAGUE_JUMP_PROXY)})


class LeagueInterpretedInputs(InterpretedInputs):
    """A league snapshot (stage2.league_inputs); same contract and revision rule as InterpretedInputs."""


class LeagueInputReader(InputReader):
    def grade(self,key):
        v=self.value(key)
        if key=='S07' or v.get('scale')!=LEAGUE_TECHNIQUE:return super().grade(key)
        index=v['grade']/100
        self.audit[key]={'rule':'Stage 2 league bridge: league e2 reference grade/100 (same index rule as native)','raw_value':v,'response_index':index,
                         'claim':'declared experimental response, not measured scale equivalence'}
        return index

    def capacity(self,key):
        v=self.value(key);display=v.get('display_grade')
        if v.get('measurements') or not display or display.get('scale')!=LEAGUE_TECHNIQUE:return super().capacity(key)
        result=display['grade']/100
        self.audit.setdefault(key,{}).update(response=result,rule='Stage 2 league bridge: league e2 capacity grade/100; no inferred N or seconds')
        return result

    def distribution(self,key,*,allow_pop=False):
        v=self.value(key);rows=v['rows']
        if len(rows)!=1 or rows[0]['condition']!='reference_opportunity' or key not in ('T02','T03'):return super().distribution(key,allow_pop=allow_pop)
        probabilities=dict(rows[0]['probabilities'])
        if key=='T02':
            # The league's four observed regions onto the kernel's three: the kernel's short_paint zone resolves both
            # floaters and two-point jumpers (4-14 ft and 14 ft to the arc).
            if set(probabilities)!={'rim','short_paint','midrange','three'} or v.get('spatial_reference')!=LEAGUE_T02_REGIONS:
                return super().distribution(key,allow_pop=allow_pop)
            probabilities={'rim':probabilities['rim'],'short_paint':probabilities['short_paint']+probabilities['midrange'],'perimeter':probabilities['three']}
            rule='league four regions: short_paint+midrange -> kernel short_paint; three -> perimeter'
        else:
            rule='league reference_opportunity shot-mode condition; raw preference not rewritten'
        self.audit[key]={'rule':rule,'condition':rows[0]['condition'],'raw_probabilities':rows[0]['probabilities'],'response_probabilities':probabilities}
        return probabilities
# --- end Stage 2 league bridge ----------------------------------------------------------------------------------
