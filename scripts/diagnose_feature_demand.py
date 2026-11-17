"""Lightweight caller attribution for feature outputs; no production instrumentation."""
from collections import Counter
from contextlib import ExitStack
import json,runpy,sys,time
from pathlib import Path
from unittest.mock import patch
from nba_gm_data import transactions as tx,sim,spatial,offense

output=Path(sys.argv[sys.argv.index('--output')+1]);owners=[];calls=Counter();seconds=Counter()

def wrapper(original,name,owner=False):
    def measured(*a,**kw):
        label=(owners[-1] if owners else 'other')+':'+name
        if owner:owners.append(name);label=name
        calls[label]+=1;start=time.perf_counter()
        try:return original(*a,**kw)
        finally:
            seconds[label]+=time.perf_counter()-start
            if owner:owners.pop()
    return measured

with ExitStack() as patches:
    for name in ('build_player_asset_valuations','team_needs_and_excesses'):
        patches.enter_context(patch.object(tx,name,new=wrapper(getattr(tx,name),name,True)))
    for module,name in ((sim,'player_feature_vector'),(sim,'team_feature_vector'),
                        (offense,'offensive_profile'),(spatial,'team_spatial_profile')):
        patches.enter_context(patch.object(module,name,new=wrapper(getattr(module,name),name)))
    # sim imported these functions directly; count the underlying operation once.
    player=wrapper(spatial.player_spatial_profile,'player_spatial_profile')
    patches.enter_context(patch.object(spatial,'player_spatial_profile',new=player))
    patches.enter_context(patch.object(sim,'player_spatial_profile',new=player))
    patches.enter_context(patch.object(sim,'team_spatial_profile',new=spatial.team_spatial_profile))
    runpy.run_path('scripts/capture_benchmark_response.py',run_name='__main__')
(output/'feature-demand.json').write_text(json.dumps({'calls':calls,'nested_seconds':seconds,
    'note':'Ownership rows are disjoint. Nested feature/spatial/offense rows overlap and must not be summed.'},indent=2)+'\n')
