"""Separate bounded attribution of settlement owners and their nested work."""
from collections import Counter
from contextlib import ExitStack
import json,runpy,sys,time,weakref
from pathlib import Path
from unittest.mock import patch
from nba_gm_data import transactions as tx,save as sv

output=Path(sys.argv[sys.argv.index('--output')+1]);records=[];stack=[];totals=Counter();counts=Counter();refs=[]
with ExitStack() as patches:
    apply=tx.apply_trade_to_state
    def applying(*a,**kw):
        record={'overlays':0,'overlay_seconds':0.,'builds':0,'build_seconds':0.};stack.append(record)
        start=time.perf_counter()
        try:
            result=apply(*a,**kw);record['status']=result['status'];return result
        finally:
            record['seconds']=time.perf_counter()-start;stack.pop();records.append(record)
            record['live_settlement_owners_after_return']=sum(r() is not None for r in refs)
    patches.enter_context(patch.object(tx,'apply_trade_to_state',new=applying))
    for module,name,key in ((sv,'canonical_with_save','overlay'),(tx,'build_transaction_context','build')):
        original=getattr(module,name)
        def counted(*a,_original=original,_key=key,**kw):
            start=time.perf_counter()
            try:return _original(*a,**kw)
            finally:
                seconds=time.perf_counter()-start;totals[_key]+=seconds;counts[_key]+=1
                if stack:stack[-1][_key+'s']+=1;stack[-1][_key+'_seconds']+=seconds
        for loaded in list(sys.modules.values()):
            if loaded is not None and getattr(loaded,'__name__','').startswith('nba_gm_data'):
                for alias,value in list(vars(loaded).items()):
                    if value is original:patches.enter_context(patch.object(loaded,alias,new=counted))
    kind=getattr(tx,'_BilateralSettlementMaterialization',None)
    if kind:
        init=kind.__init__
        def initialized(obj,*a,**kw):
            init(obj,*a,**kw);refs.append(weakref.ref(obj))
        patches.enter_context(patch.object(kind,'__init__',new=initialized))
    runpy.run_path('scripts/benchmark_advance_speed.py',run_name='__main__')
report={'settlements':records,'all_overlays':counts['overlay'],'all_overlay_seconds':totals['overlay'],
        'all_context_builds':counts['build'],'all_context_seconds':totals['build'],
        'owners_created':len(refs),'live_owners_after_action':sum(r() is not None for r in refs),
        'nested_costs_are_not_additive':True}
(output/'settlements.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
