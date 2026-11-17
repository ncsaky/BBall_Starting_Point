"""Bounded dependency/repeat probe; separate from uninstrumented wall timing."""
from collections import Counter
from contextlib import ExitStack
import hashlib,json,runpy,sys,time
from pathlib import Path
from unittest.mock import patch
from nba_gm_data import save,transactions as tx,trade_roster as tr
from nba_gm_data.roster_forecast import ForecastSnapshot

output=Path(sys.argv[sys.argv.index('--output')+1]);counts=Counter();seconds=Counter();duplicate_seconds=Counter()
seen={};serial=0;scopes=[];projection_stack=[]

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).digest()
def scope(c):return getattr(c.get('_roster_forecast_snapshot'),'_role_probe_serial',None)
def timed(label,key,fn):
    table=seen.setdefault(label,set());duplicate=key is not None and key in table
    if key is not None and len(table)<4096:table.add(key)
    counts[label]+=1
    if duplicate:counts[label+'.duplicate_inputs']+=1
    start=time.perf_counter()
    try:return fn()
    finally:
        elapsed=time.perf_counter()-start;seconds[label]+=elapsed
        if duplicate:duplicate_seconds[label]+=elapsed

with ExitStack() as patches:
    initialize=ForecastSnapshot.__init__
    def initialized(s,*a,**kw):
        global serial
        initialize(s,*a,**kw);serial+=1;s._role_probe_serial=serial
    patches.enter_context(patch.object(ForecastSnapshot,'__init__',new=initialized))
    project=tr.roster_projection
    def projected(c,team,outgoing_ids=(),incoming_ids=()):
        out,inc=set(outgoing_ids),set(incoming_ids);key=(team,tuple(sorted(out)),tuple(sorted(inc)))
        cache=c.get('_trade_search_rosters');kind='before' if not out|inc else 'after'
        if cache is not None and key in cache:label='projection.'+kind+'.batch_hit'
        else:label='projection.'+kind+'.no_batch_hit'
        record={'computed':False};projection_stack.append(record)
        try:return timed(label,None,lambda:project(c,team,out,inc))
        finally:
            projection_stack.pop()
            if record['computed']:counts['projection.'+kind+'.computed']+=1
            elif not label.endswith('batch_hit') or label.endswith('no_batch_hit'):counts['projection.'+kind+'.signature_hit']+=1
    patches.enter_context(patch.object(tr,'roster_projection',new=projected))
    rotation=tx.strategic_rotation_view
    def rotated(c,team):
        if projection_stack:projection_stack[-1]['computed']=True
        owner=scope(c);players=[{**p,'minutes_projection':24} for p in c.get('players',[]) if p.get('team_id')==team and not p.get('_inactive_player')]
        key=(owner,team,fingerprint(players)) if owner is not None else None
        return timed('rotation.snapshot' if owner is not None else 'rotation.other',key,lambda:rotation(c,team))
    patches.enter_context(patch.object(tx,'strategic_rotation_view',new=rotated))
    roles=save.ai_role_targets
    def targeted(c,roster,priors):
        owner=scope(c);ids={p['id'] for p in roster}
        indexed=[p for p in c.get('players',[]) if p['id'] in ids]
        key=(owner,fingerprint([roster,indexed,priors])) if owner is not None else None
        return timed('role_targets.snapshot' if owner is not None else 'role_targets.other',key,lambda:roles(c,roster,priors))
    patches.enter_context(patch.object(save,'ai_role_targets',new=targeted))
    multiplier=tx.destination_role_multipliers
    def multiplied(c,incoming,team,outgoing=None):
        key=(team,tuple(sorted((a.get('id') for a in incoming if a.get('kind')=='player'),key=str)),
             tuple(sorted({a.get('id') for a in outgoing or [] if a.get('kind')=='player'},key=str)))
        cache=c.get('_trade_search_roles')
        label='destination.'+('hit' if cache is not None and key in cache else 'miss' if cache is not None else 'no_cache')
        return timed(label,None,lambda:multiplier(c,incoming,team,outgoing))
    patches.enter_context(patch.object(tx,'destination_role_multipliers',new=multiplied))
    package=tx.package_value_components
    def valued(c,assets,team,outgoing=None):
        owner=scope(c);state=next((s for s in c.get('team_strategic_states',[]) if s.get('team_id')==team),{})
        pick_ids={a.get('id') for a in assets if a.get('kind')=='pick'}
        swap_ids={a.get('id') for a in assets if a.get('kind')=='pick_swap'}
        picks=[p for p in c.get('draft_picks',[]) if p.get('id') in pick_ids]
        swaps=[s for s in c.get('pick_obligations',[]) if s.get('id') in swap_ids]
        key=(owner,fingerprint([assets,team,outgoing,state,picks,swaps])) if owner is not None else None
        return timed('package.snapshot' if owner is not None else 'package.other',key,lambda:package(c,assets,team,outgoing))
    patches.enter_context(patch.object(tx,'package_value_components',new=valued))
    runpy.run_path('scripts/capture_benchmark_response.py',run_name='__main__')
(output/'role-roster-repeats.json').write_text(json.dumps({'calls':counts,'nested_seconds':seconds,
    'nested_duplicate_seconds':duplicate_seconds,'distinct_inputs':{k:len(v) for k,v in seen.items() if v},'snapshots':serial,
    'note':'Tables capped at4096 signatures; timings overlap. Snapshot serials distinguish fresh states; normalized rotation keys remove only overwritten minutes. Package duplicates are provisional (full swap-leaf dependency audit still required before reuse).'},indent=2)+'\n')
