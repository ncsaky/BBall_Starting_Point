"""Bounded existing action-memory gate, with scalar-only forecast cache probes."""
from contextlib import ExitStack
import json,runpy,sys,weakref
from pathlib import Path
from unittest.mock import patch
from nba_gm_data import app_actions as aa
from nba_gm_data.roster_forecast import ForecastSnapshot

output=Path(sys.argv[sys.argv.index('--output')+1]);refs=[];stats=[];rows=[]
with ExitStack() as patches:
    initialize=ForecastSnapshot.__init__
    def initialized(snapshot,*a,**kw):
        initialize(snapshot,*a,**kw)
        if len(refs)<64:
            refs.append(weakref.ref(snapshot))
            # Counters contain numbers and no back-reference to the owner.
            stats.append(snapshot.stats)
    patches.enter_context(patch.object(ForecastSnapshot,'__init__',new=initialized))
    dispatch=aa.dispatch_app_action
    def dispatched(*a,**kw):
        refs.clear();stats.clear()
        result=dispatch(*a,**kw)
        cached=[]
        for context in aa._READ_CACHE.values():
            for label in ('active','dashboard_active'):
                memo=((context.get(label) or {}).get('_sim_feature_cache') or {}).get('player_features',{})
                cached.append({'view':label,'vectors':len(memo),
                    'full':sum(isinstance(k,tuple) and len(k)>4 and bool(k[4]) for k in memo)})
        rows.append({'snapshots':len(refs),'live_snapshots_after_return':sum(r() is not None for r in refs),
                     'forecast_cache_stats':[dict(s) for s in stats],'read_cache_vectors':cached})
        return result
    patches.enter_context(patch.object(aa,'dispatch_app_action',new=dispatched))
    runpy.run_path('scripts/probe_context_action_memory.py',run_name='__main__')
(output/'feature-release.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(not r['live_snapshots_after_return'] for r in rows)
assert all(s.get('features.peak',0)<=8192 and s.get('attributes.peak',0)<=4096 for r in rows for s in r['forecast_cache_stats'])
