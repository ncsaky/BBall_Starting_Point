"""Bounded Stage-B diagnostics, timings and cache inventory; separate from wall samples."""
from collections import Counter
from contextlib import ExitStack
import gc,json,resource,runpy,sys,time,weakref
from pathlib import Path
from unittest.mock import patch
from nba_gm_data import transactions as tx
from nba_gm_data.trade_review import MarketReview
from package_search_diagnostics import instrument

categories=Counter()
full_categories=Counter();partial_categories=Counter();pricing_categories=Counter();team_calls=Counter();frames=[]
output=Path(sys.argv[sys.argv.index('--output')+1]);metrics=Counter();timings=Counter();searches=[];refs=[]
class Lifetime:pass

def size(obj,seen):
    if id(obj) in seen:return 0
    seen.add(id(obj));total=sys.getsizeof(obj)
    if isinstance(obj,dict):total+=sum(size(k,seen)+size(v,seen) for k,v in obj.items())
    elif isinstance(obj,(tuple,list,set,frozenset)):total+=sum(size(v,seen) for v in obj)
    elif hasattr(obj,'__dataclass_fields__'):total+=size(vars(obj),seen)
    return total

with ExitStack() as stack:
    original=tx.simulate_ai_trades
    def search(*a,**kw):
        start=time.perf_counter();result=original(*a,**kw)
        searches.append({'seconds':time.perf_counter()-start,'proposals':len(result['proposals']),
            'diagnostics':result['search_diagnostics']})
        return result
    stack.enter_context(patch.object(tx,'simulate_ai_trades',search))
    try:
        from nba_gm_data import trade_finance_search as finance
    except ImportError:finance=None
    if finance:
        original_classify=finance.classify_movements
        def classify(*a,**kw):
            start=time.perf_counter()
            try:return original_classify(*a,**kw)
            finally:timings['classification_seconds']+=time.perf_counter()-start
        stack.enter_context(patch.object(finance,'classify_movements',classify))
    team_evaluation=tx.evaluate_trade_for_team
    def team(*a,**kw):
        if frames:
            frame=frames[-1];tid=a[2];frame['teams'].add(tid)
            team_calls[frame['category']]+=1
            cache=kw.get('_calculation_cache')
            if cache is None or tid not in cache:pricing_categories[frame['category']]+=1
        return team_evaluation(*a,**kw)
    stack.enter_context(patch.object(tx,'evaluate_trade_for_team',team))
    approval=tx.evaluate_trade_participants
    def participants(*a,**kw):
        start=time.perf_counter()
        legality=a[2]
        proposal=a[1]
        issues=legality.get('issues',[])
        if kw.get('include_presentation',True):category='presentation'
        elif (getattr(proposal,'transfers',None) or (proposal.get('transfers') if isinstance(proposal,dict) else None)):category='repairable'
        elif legality['status']=='legal':category='unresolved' if legality.get('manual_review') else 'legal'
        elif legality.get('manual_review') or any('unresolved' in i for i in issues):category='unresolved'
        elif any(not any(term in i for term in ('matching tolerance','hard-cap','roster hard maximum','roster minimum')) for i in issues):category='terminal'
        else:category='repairable'
        categories[category]+=1
        frame={'category':category,'teams':set()};frames.append(frame)
        try:return approval(*a,**kw)
        finally:
            frames.pop()
            expected=set(tx.trade_team_ids(proposal))
            (full_categories if frame['teams']==expected else partial_categories)[category]+=1
            timings['participant_seconds']+=time.perf_counter()-start
    stack.enter_context(patch.object(tx,'evaluate_trade_participants',participants))
    close=MarketReview.close
    def measured_close(review):
        active=review.active or {}
        keys=('_trade_financial_facts','_trade_movement_classes')
        caches=[active[k] for k in keys if k in active]
        metrics['added_cache_bytes']=max(metrics['added_cache_bytes'],size(caches,set()) if caches else 0)
        for k in keys:metrics[k+'.entries_at_close']=max(metrics[k+'.entries_at_close'],len(active.get(k,{})))
        token=Lifetime();active['_diagnostic_lifetime']=token;refs.append(weakref.ref(token))
        close(review)
    stack.enter_context(patch.object(MarketReview,'close',measured_close))
    with instrument(metrics):
        runpy.run_path(str(Path(__file__).with_name('benchmark_advance_speed.py')),run_name='__main__')
gc.collect()
report={'metrics':dict(metrics),'timings':dict(timings),'participant_calls_observed':dict(categories),'all_participants_priced':dict(full_categories),
        'truncated_participant_pricing':dict(partial_categories),'pricing_body_calls':dict(pricing_categories),
        'team_method_calls':dict(team_calls),'searches':searches,
        'released_reviews':sum(r() is None for r in refs),'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
(output/'salary-diagnostics.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
