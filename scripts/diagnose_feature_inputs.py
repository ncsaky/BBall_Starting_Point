"""Narrow immutable-input repeats; instrumentation is separate from wall samples."""
from collections import Counter
from contextlib import ExitStack
import hashlib,json,runpy,sys,time
from pathlib import Path
from unittest.mock import patch
from nba_gm_data import sim,offense,spatial,save
from nba_gm_data.roster_forecast import ForecastSnapshot

output=Path(sys.argv[sys.argv.index('--output')+1])
counts,seconds,repeated_seconds=Counter(),Counter(),Counter();seen={};next_scope=0;snapshots=[]

def scope(c):
    s=c.get('_roster_forecast_snapshot')
    return getattr(s,'_feature_probe_scope',None)

def signature(c,p,traits):
    # Complete stable offensive inputs, including the caller's actual numeric
    # trait semantics. Spatial maps intentionally treat zero differently.
    return (scope(c),p.get('id'),p.get('position'),float(p.get('height_inches') or 78),
            float(p.get('weight_lbs') or 215),tuple(sorted((k,float(v)) for k,v in traits.items())),
            json.dumps(c.get('meta',{}).get('offensive_profiles',{}).get(p.get('id'),{}),sort_keys=True))

def timed(label,key,call):
    bucket=seen.setdefault(label,set());repeat=key is not None and key in bucket
    if key is not None and len(bucket)<16384:bucket.add(key)
    counts[label]+=1
    if repeat:counts[label+'.repeated']+=1
    start=time.perf_counter()
    try:return call()
    finally:
        elapsed=time.perf_counter()-start;seconds[label]+=elapsed
        if repeat:repeated_seconds[label]+=elapsed

with ExitStack() as patches:
    initialize=ForecastSnapshot.__init__
    def initializing(s,*a,**kw):
        global next_scope
        initialize(s,*a,**kw);next_scope+=1;s._feature_probe_scope=next_scope
    patches.enter_context(patch.object(ForecastSnapshot,'__init__',new=initializing))
    feature=sim.player_feature_vector
    def featured(c,p,**kw):
        cache=sim.canonical_sim_cache(c)
        fk=(p.get('id'),p.get('rotation_priority'),float(p.get('minutes_projection') or 0),float(p.get('actual_points') or 0),kw.get('include_spatial',True))
        hit=fk in cache['player_features'];own=scope(c) is not None
        label='player_feature.'+('snapshot' if own else 'other')+('.hit' if hit else '.miss')
        rows=cache['traits_by_player'].get(p['id'],{})
        traits={k:float(r['value']) for k,r in rows.items()}
        key=(signature(c,p,traits),bool(sim.talent_enabled(c))) if own and not hit else None
        return timed(label,key,lambda:feature(c,p,**kw))
    patches.enter_context(patch.object(sim,'player_feature_vector',new=featured))
    profile=offense.offensive_profile
    def offensive(c,p,t):
        own=scope(c) is not None;label='offensive_profile.'+('snapshot' if own else 'other')
        key=signature(c,p,t) if own else None
        return timed(label,key,lambda:profile(c,p,t))
    patches.enter_context(patch.object(offense,'offensive_profile',new=offensive))
    spatial_profile=spatial.player_spatial_profile
    def spatialized(c,p,**kw):
        label='spatial_profile.'+('snapshot' if scope(c) is not None else 'other')
        # Existing spatial signatures also include role minutes, age, shot sample
        # and offensive profile. Do not equate complete profiles by player ID.
        return timed(label,None,lambda:spatial_profile(c,p,**kw))
    patches.enter_context(patch.object(spatial,'player_spatial_profile',new=spatialized))
    patches.enter_context(patch.object(sim,'player_spatial_profile',new=spatialized))
    runpy.run_path('scripts/capture_benchmark_response.py',run_name='__main__')
report={'calls':counts,'nested_seconds':seconds,'nested_repeated_seconds':repeated_seconds,
        'distinct_stable_inputs':{k:len(v) for k,v in seen.items() if k.endswith('snapshot') or k.endswith('snapshot.miss')},
        'snapshots':next_scope,'note':'Nested durations overlap. Repeats are counted only within snapshot scopes. Non-keyed hit/other/spatial buckets are timings, not repeated-input evidence.'}
(output/'feature-inputs.json').write_text(json.dumps(report,indent=2)+'\n')
