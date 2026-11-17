"""Offline construction hypotheses; never imported by production runtime."""
from __future__ import annotations
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping
import math
from nba_gm_data.utils import maybe_float

KEYS = ('defensive_effort','foot_speed_lateral_agility','screen_navigation','scheme_iq','rim_deterrence')
FIELDS = ('DEFLECTIONS','STLpct','VersatilityRating','CraftedDPM','BBallIQ','passerRating','BLKpct','HeightSocks','DARKO')
# Fixed declared reference transform, not annual max normalization.
VERSION = 'offline_defensive_inputs_2026_11_11_v1'


def finite(value):
    v = maybe_float(value)
    return v if v is not None and math.isfinite(v) else None


def tail_scale(x: float) -> float:
    """Fixed anchors 0->0,50->50,80->80,100->90,120->95,140->97.5.

    Strictly increasing for normal finite >=0 inputs; only negative values hit
    the safety floor. No new roster member can change the transform.
    """
    if not math.isfinite(x): raise ValueError('Nonfinite scale input')
    if x <= 80: return max(0.0,x)
    return 80.0 + 20.0*(-math.expm1(-math.log(2)*(x-80)/20))


def infer(row: Mapping, percentile: Callable[[str],float|None]) -> dict:
    """Exactly replay the five current inference equations, retaining preclip.

    Important: current role_boost tests BOTH offensive and defensive role text.
    The current `mean(...) or50` also treats a real zero as the fallback.
    """
    text = (str(row.get('primaryOffRole') or row.get('O_Role') or '')+' '+
            str(row.get('primaryDefRole') or row.get('d_role') or '')).lower()
    role_def = str(row.get('primaryDefRole') or row.get('d_role') or '').lower()
    pos = str(row.get('position') or row.get('Pos') or '')
    def boost(needles, amount): return amount if any(n in text for n in needles) else 0.
    specs = {
        'defensive_effort': ([('DEFLECTIONS',1/3),('STLpct',1/3),('CraftedDPM',1/3)], boost(('disruptor','on-ball','versatile'),12)),
        'foot_speed_lateral_agility': ([('DEFLECTIONS',.24),('STLpct',.24),('VersatilityRating',.22),('CraftedDPM',.30)],boost(('on-ball guard','disruptor','versatile stopper'),10)+boost(('mobile forward',),4)),
        'screen_navigation': ([('DEFLECTIONS',.24),('STLpct',.24),('VersatilityRating',.20),('CraftedDPM',.32)],9. if any(n in role_def for n in ('guard','disruptor','stopper')) and pos!='C' else 0.),
        'scheme_iq': ([('BBallIQ',1/3),('passerRating',1/3),('CraftedDPM',1/3)],boost(('connector','rim protector','primary ball handler'),8)),
        'rim_deterrence': ([('BLKpct',.55),('HeightSocks',.24),('CraftedDPM',.15),('DARKO',.06)],(16. if max(percentile('BLKpct') or 0,percentile('HeightSocks') or 0)>=82 else 6.) if 'rim protector' in role_def else 0.),
    }
    result={}
    for key,(spec,bonus) in specs.items():
        values=[(field,finite(row.get(field)) if field=='BBallIQ' else percentile(field),w) for field,w in spec]
        present=[(field,v,w) for field,v,w in values if v is not None]
        denom=sum(w for _,_,w in present)
        base=sum(v*w for _,v,w in present)/denom if denom else None
        contributions={field:v*w/denom for field,v,w in present} if denom else {}
        uncapped=(base or 50.)+bonus
        result[key]={
            'preclip':uncapped,'capped':round(max(0,min(100,uncapped)),2),
            'base':base,'role_bonus':bonus,'fallback_50':not bool(base),
            'known_zero_replaced_by_50':base==0,'source_contributions':contributions,
            'normalized_source_weights':{field:w/denom for field,_,w in present} if denom else {},
            'missing_fields':[field for field,v,_ in values if v is None],
            'source_values':{field:v for field,v,_ in values},
            'observed_weight_coverage':sum(w for _,_,w in present),
        }
    return result


def freeze_reference(rows: list[dict], source_sha: str) -> dict:
    """Freeze once, version/hash and reuse; never regenerate for each cohort."""
    return {'version':VERSION,'source_sha256':source_sha,
            'fields':{f:sorted(v for row in rows if (v:=finite(row.get(f))) is not None) for f in FIELDS}}


def fixed_lookup(reference: dict, field: str, value) -> float|None:
    """Equal raw inputs get equal midrank against an immutable source reference.

    Reference observations occupy 1..99, leaving a smooth 0..1/99..100 tail
    beyond its actual extrema. No current-roster ranks or position percentiles.
    """
    v=finite(value); xs=reference['fields'].get(field,[])
    if v is None or not xs: return None
    span=max(xs[-1]-xs[0],abs(xs[0])*.05,1.)
    if len(xs)==1:
        return 50*math.exp((v-xs[0])/span) if v<xs[0] else 100-50*math.exp(-(v-xs[0])/span)
    low_grade=1+98*((bisect_right(xs,xs[0])-1)/2)/(len(xs)-1)
    high_grade=1+98*((bisect_left(xs,xs[-1])+len(xs)-1)/2)/(len(xs)-1)
    if v < xs[0]: return low_grade*math.exp((v-xs[0])/span)
    if v > xs[-1]: return 100.-(100-high_grade)*math.exp(-(v-xs[-1])/span)
    lo,hi=bisect_left(xs,v),bisect_right(xs,v)
    if lo!=hi:return 1+98*((lo+hi-1)/2)/(len(xs)-1)
    # Interpolate between neighboring actual observations; stable to input order.
    a,b=xs[lo-1],xs[lo]
    left=1+98*((bisect_left(xs,a)+bisect_right(xs,a)-1)/2)/(len(xs)-1)
    right=1+98*((bisect_left(xs,b)+bisect_right(xs,b)-1)/2)/(len(xs)-1)
    return left+(right-left)*(v-a)/(b-a)


def experiment(row: dict, reference: dict) -> dict:
    """A keeps the existing proxy/role equations; B separates evidence channels.

    B does not pretend steals measure effort, lateral feet AND navigation.
    Sample denominators/as-of windows are not aligned, so no fake shrinkage
    from final-season minutes is applied to March rates.
    """
    lookup=lambda f:fixed_lookup(reference,f,row.get(f))
    a=infer(row,lookup)
    candidates={key:tail_scale(v['preclip']) for key,v in a.items()}
    block,height=lookup('BLKpct'),lookup('HeightSocks')
    protection=None if block is None or height is None else .85*block+.15*height
    steal,deflection=lookup('STLpct'),lookup('DEFLECTIONS')
    # Report missing; do not reweight a single present component into certainty.
    disruption=None if steal is None or deflection is None else (steal+deflection)/2
    return {'A_fixed_reference':candidates,'A_uncapped':a,
            'B_channels':{'protection_proxy':protection,'event_disruption_proxy':disruption,
                'general_defensive_impact_context':lookup('CraftedDPM'),
                'containment':None,'screen_technique':None,'help_execution':None,
                'sample_reliability':None},
            'B_rim_hypothesis':tail_scale(protection) if protection is not None else None,
            'B_limit':'85% block/15% height are sensitivity weights, not validated deterrence. No role/impact bonus. Other four skills are NOT reconstructed from these channels.',
            'sample':{k:finite(row.get(k)) for k in ('GP','MP','minutes','2025minutes')},
            'sample_limit':'Raw rate denominators/query windows not established. GP/MP and final-season minutes are context only, not an aligned posterior sample.'}


def reapply_overrides(candidate: Mapping[str,float|None], current: Mapping[str,float],
                      reviewed: set[str]) -> tuple[dict,dict]:
    """Absolute reviewed overrides survive; unavailable estimates are held, flagged."""
    output={};status={}
    for key in KEYS:
        v=candidate.get(key)
        if key in reviewed:
            output[key]=current[key];status[key]='reviewed_absolute_override_reapplied'
        elif v is None:
            output[key]=current[key];status[key]='held_no_identifiable_new_estimate'
        else:
            output[key]=v;status[key]='experimental_estimate_not_validated'
    return output,status


def source_overlap(weights: Mapping[str,Mapping[str,float]]) -> dict:
    """Exact shared dependency mass, not correlations or independent validation."""
    names=list(weights)
    return {a:{b:sum(min(weights[a].get(f,0),weights[b].get(f,0))
                         for f in set(weights[a])|set(weights[b])) for b in names} for a in names}
