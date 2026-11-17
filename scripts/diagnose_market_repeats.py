"""Bounded duplicate-input attribution; never use this run as wall-time evidence."""
from collections import Counter
from contextlib import ExitStack
import json
from pathlib import Path
import runpy
import sys
import time
from unittest.mock import patch
from nba_gm_data import transactions as tx
from nba_gm_data.trade_review import MarketReview

output = Path(sys.argv[sys.argv.index('--output') + 1])
seen, counts, seconds, duplicate_seconds = {}, Counter(), Counter(), Counter()
reviews = []

def key_for(name, args, kwargs):
    canonical = args[0]
    if name == 'ai_pick_protection_options':
        return (id(canonical), args[1]['id'], args[2]['id'], args[3]['id'], args[4] if len(args)>4 else kwargs.get('phase','neutral'))
    if name == 'tradeable_picks_for_team':
        return (id(canonical), args[1])
    if name == 'canonical_with_pending_pick_terms':
        return (id(canonical), json.dumps(args[1] if len(args)>1 else kwargs.get('terms'),sort_keys=True))
    if name == 'package_value_components':
        return (id(canonical), json.dumps([args[1:],kwargs],sort_keys=True))
    return None  # The generator is timed, not treated as an equivalent query.

with ExitStack() as patches:
    for name in ('ai_pick_protection_options','tradeable_picks_for_team','canonical_with_pending_pick_terms','package_value_components','buyer_offer_packages_for_value'):
        original = getattr(tx,name)
        seen[name] = set()
        def measured(*args, _name=name, _original=original, **kwargs):
            key = key_for(_name,args,kwargs)
            repeated = key is not None and key in seen[_name]
            if key is not None and len(seen[_name]) < 4096: seen[_name].add(key)
            counts[_name] += 1
            if repeated: counts[_name+'.duplicate_inputs'] += 1
            started = time.perf_counter()
            try: return _original(*args,**kwargs)
            finally:
                elapsed = time.perf_counter()-started
                seconds[_name] += elapsed
                if repeated: duplicate_seconds[_name] += elapsed
        patches.enter_context(patch.object(tx,name,new=measured))
    close = MarketReview.close
    def closed(review):
        reviews.append({'stats':dict(review.stats), 'pick_preview_entries':len((review.active or {}).get('_trade_search_pick_previews',{}))})
        return close(review)
    patches.enter_context(patch.object(MarketReview,'close',new=closed))
    runpy.run_path('scripts/capture_benchmark_response.py',run_name='__main__')
(output/'repeat-diagnostics.json').write_text(json.dumps({'calls':counts,'nested_seconds':seconds,'nested_duplicate_seconds':duplicate_seconds,'distinct_inputs':{k:len(v) for k,v in seen.items()},'reviews':reviews,'note':'Nested durations overlap; input identity scopes are the immutable review bases, not a same-date equivalence claim.'},indent=2)+'\n')
