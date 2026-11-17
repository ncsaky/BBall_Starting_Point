"""Bounded roster/context attribution; run separately from wall-time samples."""
from collections import Counter
from contextlib import ExitStack
import gc
import json
from pathlib import Path
import resource
import runpy
import sys
import time
from unittest.mock import patch
import weakref

from nba_gm_data import transactions as tx, trade_roster as tr, sim, save, contract_protection
from nba_gm_data.trade_review import MarketReview

output = Path(sys.argv[sys.argv.index('--output') + 1])
counts, seconds, rows = Counter(), Counter(), Counter()
stack_names, lifetimes = [], []
cache_sizes = Counter()
snapshot_probes = []


def measure(module, name, patches):
    original = getattr(module, name)
    label = module.__name__.rsplit('.', 1)[-1] + '.' + name

    def call(*args, **kwargs):
        scope = 'settlement' if 'trade_roster.live_roster_issues' in stack_names else 'other'
        key = scope + ':' + label
        counts[key] += 1
        if args and isinstance(args[0], dict):
            for collection in ('players', 'traits', 'contracts'):
                rows[key + '.' + collection] += len(args[0].get(collection, ()))
        started = time.perf_counter()
        stack_names.append(label)
        try:
            before = None
            if module is sim and name == 'canonical_sim_cache':
                c = args[0]
                before = c.get('_sim_feature_cache') if c.get('_allow_internal_caches') else sim._SIM_FEATURE_CACHE.get(id(c))
            result = original(*args, **kwargs)
            if module is sim and name == 'canonical_sim_cache' and result is not before:
                counts[key + '.index_builds'] += 1
                counts[key + '.trait_rows_indexed'] += len(args[0].get('traits', ()))
            return result
        finally:
            stack_names.pop()
            seconds[key] += time.perf_counter() - started
    patches.enter_context(patch.object(module, name, call))


def size(obj, seen):
    if id(obj) in seen:
        return 0
    seen.add(id(obj))
    result = sys.getsizeof(obj)
    if isinstance(obj, dict):
        result += sum(size(k, seen) + size(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        result += sum(size(v, seen) for v in obj)
    elif hasattr(obj, '__dict__'):
        result += size(vars(obj), seen)
    return result


class Lifetime:
    pass


with ExitStack() as patches:
    for module, names in (
        (tr, ('roster_projection', 'constrain_center_opportunity', 'live_roster_issues', 'deepcopy')),
        (tx, ('strategic_rotation_view', 'with_transaction_context', 'build_transaction_context',
              'build_team_strategic_states', 'build_player_asset_valuations', 'apply_trade_to_state')),
        (sim, ('canonical_sim_cache', 'player_feature_vector', 'team_feature_vector')),
        (save, ('canonical_with_save', 'ai_role_targets', 'ai_roster_retention_score',
                'player_attribute_summary', '_uncached_player_attribute_summary',
                'trait_values_by_player', 'players_by_id_index')),
        (contract_protection, ('season_window', '_uncached_season_window', 'waiver_projection')),
    ):
        for name in names:
            if hasattr(module, name):
                measure(module, name, patches)
    try:
        from nba_gm_data.roster_forecast import ForecastSnapshot
    except ImportError:
        ForecastSnapshot = None
    if ForecastSnapshot is not None:
        initialize = ForecastSnapshot.__init__

        def initializing(snapshot, canonical):
            initialize(snapshot, canonical)
            scope = 'settlement' if 'trade_roster.live_roster_issues' in stack_names else 'other'
            counts[scope + ':snapshot_builds'] += 1
            if len(snapshot_probes) < 256:
                # Counters and weak refs only: neither retains the input graph.
                snapshot_probes.append((scope, weakref.ref(snapshot), snapshot.stats))
        patches.enter_context(patch.object(ForecastSnapshot, '__init__', initializing))
    close = MarketReview.close

    def closing(review):
        active = review.active
        if active is not None:
            stats = active.get('_roster_forecast_stats', {})
            counts.update({'forecast.' + k: v for k, v in stats.items()})
            snapshot = active.get('_roster_forecast_snapshot')
            if snapshot is not None:
                cache_sizes['forecast_bytes_at_close'] = size(snapshot, set())
                seen = set()
                for collection in ('players', 'traits', 'contracts'):
                    size(active.get(collection, []), seen)
                size((active.get('_trade_planning_save') or {}).get('health_states', []), seen)
                cache_sizes['added_forecast_bytes_at_close'] = size(snapshot, seen)
                cache_sizes['feature_entries_at_close'] = len(snapshot.features)
                cache_sizes['attribute_entries_at_close'] = len(snapshot.attributes)
                lifetimes.append(weakref.ref(snapshot))
            token = Lifetime()
            active['_diagnostic_lifetime'] = token
            lifetimes.append(weakref.ref(token))
        close(review)
    patches.enter_context(patch.object(MarketReview, 'close', closing))
    # Opt-in counters are diagnostic only, never persisted in a save.
    prepare = tx.trade_search_context

    def context(canonical):
        active = prepare(canonical)
        active.setdefault('_roster_forecast_stats', Counter())
        return active
    patches.enter_context(patch.object(tx, 'trade_search_context', context))
    runpy.run_path(str(Path(__file__).with_name('benchmark_advance_speed.py')), run_name='__main__')
gc.collect()
for scope, ref, stats in snapshot_probes:
    counts.update({scope + ':snapshot.' + k: v for k, v in stats.items()})
report = {'calls': dict(counts), 'inclusive_seconds': dict(seconds),
          'input_rows_available': dict(rows), 'cache_inventory': dict(cache_sizes),
          'release_probes': len(lifetimes), 'released': sum(r() is None for r in lifetimes),
          'snapshot_release_probes': len(snapshot_probes),
          'snapshots_released': sum(ref() is None for _, ref, _ in snapshot_probes),
          'max_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
(output / 'roster-diagnostics.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report), flush=True)
