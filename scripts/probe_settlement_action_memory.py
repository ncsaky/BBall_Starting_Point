"""Use the existing same-process action memory gate with weak settlement probes."""
from contextlib import ExitStack
import json,runpy,sys,weakref
from pathlib import Path
from unittest.mock import patch
from nba_gm_data import transactions as tx,app_actions as aa

output=Path(sys.argv[sys.argv.index('--output')+1]);owners=[];graphs=[];rows=[]
class Token:pass
with ExitStack() as patches:
    kind=getattr(tx,'_BilateralSettlementMaterialization',None)
    if kind:
        init,active=kind.__init__,kind.active
        def initialized(obj,*a,**kw):
            init(obj,*a,**kw);owners.append(weakref.ref(obj))
        def materialized(obj):
            value=active(obj)
            if '_settlement_lifetime_probe' not in value:
                token=Token();value['_settlement_lifetime_probe']=token;graphs.append(weakref.ref(token))
            return value
        patches.enter_context(patch.object(kind,'__init__',new=initialized))
        patches.enter_context(patch.object(kind,'active',new=materialized))
    dispatch=aa.dispatch_app_action
    def dispatched(*a,**kw):
        owners.clear();graphs.clear()
        result=dispatch(*a,**kw)
        rows.append({'owner_samples':len(owners),'active_graph_samples':len(graphs),
            'live_owners':sum(r() is not None for r in owners),'live_active_graphs':sum(r() is not None for r in graphs)})
        return result
    patches.enter_context(patch.object(aa,'dispatch_app_action',new=dispatched))
    runpy.run_path('scripts/probe_context_action_memory.py',run_name='__main__')
(output/'settlement-lifetimes.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(not r['live_owners'] and not r['live_active_graphs'] for r in rows)
