"""Bounded market diagnostics; wrap benchmark_advance_speed arguments unchanged."""
import gc
import weakref
from collections import Counter
from contextlib import ExitStack
import json
from pathlib import Path
import resource
import runpy
import sys
from unittest.mock import patch
from nba_gm_data import transactions as tx, trade_roster as tr

counts = Counter()
seen = {}
lifetimes = []
class Lifetime:
    pass
output = Path(sys.argv[sys.argv.index('--output')+1])
def observe(name, key):
    bucket = seen.setdefault(name, set())
    counts[name+'.calls'] += 1
    if key in bucket:
        counts[name+'.repeated'] += 1
    elif len(bucket) < 8192:
        bucket.add(key)
    else:
        counts[name+'.capacity'] += 1

def pending(original):
    def call(c, terms):
        observe('pick_previews', json.dumps(terms, sort_keys=True))
        return original(c, terms)
    return call

def forecast(original):
    def call(c, tid, outgoing_ids=(), incoming_ids=()):
        key=(tid, tuple(sorted(set(outgoing_ids))), tuple(sorted(set(incoming_ids))))
        observe('roster_flows', key)
        cache=c.get('_trade_search_rosters', {})
        counts['roster_cache.hit' if key in cache else 'roster_cache.miss'] += 1
        return original(c, tid, outgoing_ids, incoming_ids)
    return call

def wrap(name, original):
    def call(*a, **kw):
        counts[name] += 1
        return original(*a, **kw)
    return call

with ExitStack() as stack:
    stack.enter_context(patch.object(tx, 'canonical_with_pending_pick_terms', pending(tx.canonical_with_pending_pick_terms)))
    stack.enter_context(patch.object(tr, 'roster_projection', forecast(tr.roster_projection)))
    try:
        from nba_gm_data.trade_review import MarketReview
    except ImportError:
        MarketReview = None
    if MarketReview:
        close = MarketReview.close
        def measured_close(review):
            counts.update(review.stats)
            active = review.active or {}
            for key in ('_trade_search_roles', '_trade_search_rosters', '_trade_search_pick_previews'):
                counts[key+'.peak_entries'] = max(counts[key+'.peak_entries'], len(active.get(key, {})))
            # Count retained cache objects once without retaining their references.
            visited = set()
            def size(obj):
                if id(obj) in visited:
                    return 0
                visited.add(id(obj))
                total = sys.getsizeof(obj)
                if isinstance(obj, dict):
                    total += sum(size(k)+size(v) for k,v in obj.items())
                elif isinstance(obj, (list, tuple, set)):
                    total += sum(map(size,obj))
                return total
            counts['review_cache_bytes'] = max(counts['review_cache_bytes'], size([active.get(k, {}) for k in
                ('_trade_search_roles', '_trade_search_rosters', '_trade_search_pick_previews')]))
            marker = Lifetime()
            active['_diagnostic_lifetime'] = marker
            lifetimes.append(weakref.ref(marker))
            close(review)
            counts['closed_contexts'] += review.active is None
        stack.enter_context(patch.object(MarketReview, 'close', measured_close))
    for name in ['build_transaction_context' , 'trade_search_context', 'annotate_pick_obligation_context', 'strategic_rotation_view', 'traits_by_player']:
        stack.enter_context(patch.object(tx, name, wrap(name, getattr(tx,name))))
    try:
        runpy.run_path(str(Path(__file__).with_name('benchmark_advance_speed.py')), run_name='__main__')
    finally:
        gc.collect()
        counts['released_review_graphs'] = sum(ref() is None for ref in lifetimes)
        counts['max_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        output.mkdir(parents=True,exist_ok=True)
        (output/'diagnostics.json').write_text(json.dumps(dict(counts), indent=2)+'\n')
        print(json.dumps(dict(counts)),flush=True)
