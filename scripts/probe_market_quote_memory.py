"""Existing three-action memory gate plus bounded weak quote-view probes."""
from contextlib import ExitStack
import json,runpy,sys,weakref
from pathlib import Path
from unittest.mock import patch
from nba_gm_data import transactions as tx,app_actions as aa

output=Path(sys.argv[sys.argv.index('--output')+1]);refs=[];rows=[];count=0
class Token: pass
with ExitStack() as patches:
    quote=getattr(tx,'_protection_quote_view',None)
    if quote is not None:
        def quoted(*a,**kw):
            global count
            view=quote(*a,**kw);count+=1
            if len(refs)<256:
                token=Token();view['_quote_release_probe']=token;refs.append(weakref.ref(token))
            return view
        patches.enter_context(patch.object(tx,'_protection_quote_view',new=quoted))
    dispatch=aa.dispatch_app_action
    def dispatched(*a,**kw):
        global count
        refs.clear();count=0
        result=dispatch(*a,**kw)
        rows.append({'quotes':count,'sampled_views':len(refs),'live_views_after_return':sum(ref() is not None for ref in refs)})
        return result
    patches.enter_context(patch.object(aa,'dispatch_app_action',new=dispatched))
    runpy.run_path('scripts/probe_context_action_memory.py',run_name='__main__')
(output/'quote-release.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(not r['live_views_after_return'] for r in rows)
