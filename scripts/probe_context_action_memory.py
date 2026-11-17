"""Repeated bounded real actions in one process; never retain their payloads.

GC below is diagnostic only. Weak sentinels sample response/event/context/trial
lifetimes without keeping their owning graphs. No production collection policy
is changed. Identical archived busy days isolate lifetime drift from career size.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import gc
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from unittest.mock import patch
import weakref

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data import app_actions as aa
from nba_gm_data import transactions as tx
from nba_gm_data.save import load_save
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.simulation_progress import progress_listener
from verify_simulation_consistency import business_state, digest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--actions', type=int, default=6)
parser.add_argument('--gc-each', action='store_true', help='Separate diagnostic variant; default collects only after the last action.')
parser.add_argument('--same-path', action='store_true', help='Restore/revise one disposable career instead of visiting distinct careers.')
args = parser.parse_args()
assert 3 <= args.actions <= 8
args.output.mkdir(parents=True, exist_ok=False)
root = Path(__file__).resolve().parents[1]
source = root / 'output/pick-investment-2026-10-28/stable17/saves/trade_year.json'
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
archive = create_export(source)
canonical = load_app_canonical(root)
probes = defaultdict(list)
rows = []


class Lifetime:
    pass


def mark(value, kind):
    if len(probes[kind]) < 256:
        token = Lifetime()
        value['_memory_probe'] = token
        probes[kind].append(weakref.ref(token))
    return value


def rss():
    return int(subprocess.check_output(['ps', '-p', str(os.getpid()), '-o', 'rss='], text=True).strip()) * 1024


with ExitStack() as patches:
    build = tx.build_transaction_context

    def building(*a, **kw):
        return mark(build(*a, **kw), 'context')
    patches.enter_context(patch.object(tx, 'build_transaction_context', building))
    try:
        from nba_gm_data.roster_forecast import ForecastSnapshot
    except ImportError:
        ForecastSnapshot = None
    if ForecastSnapshot is not None:
        initialize, view = ForecastSnapshot.__init__, ForecastSnapshot.view

        def initializing(snapshot, *a, **kw):
            initialize(snapshot, *a, **kw)
            if len(probes['snapshot']) < 256:
                probes['snapshot'].append(weakref.ref(snapshot))

        def viewing(*a, **kw):
            return mark(view(*a, **kw), 'trial')
        patches.enter_context(patch.object(ForecastSnapshot, '__init__', initializing))
        patches.enter_context(patch.object(ForecastSnapshot, 'view', viewing))
    gc.collect()
    start_rss, start_blocks = rss(), sys.getallocatedblocks()
    for i in range(args.actions):
        probes.clear()
        folder = args.output / ('career' if args.same_path else f'action-{i+1}')
        folder.mkdir(exist_ok=args.same_path)
        path = folder / 'career.json'
        restore_export(path, archive, replace=path.exists())
        event_hashes = []  # At most eight small digests, not event payloads.

        def progress(event):
            event_hashes.append(digest(event))
            mark(event, 'event')
        started = time.perf_counter()
        with progress_listener(progress):
            result = dispatch_app_action('advance_save', {'save_path': str(path.resolve()),
                'to_date': '2027-02-04', 'seed': 17, 'checkpoint_days': 31},
                root=root, save_dir=folder.resolve(), canonical=canonical)
        seconds = time.perf_counter() - started
        status = result.get('status')
        mark(result, 'response')
        del result
        complete_rss, complete_blocks = rss(), sys.getallocatedblocks()
        complete_live = {k: sum(r() is not None for r in refs) for k, refs in probes.items()}
        def read_owners():
            return [{'path': k, 'fields': sorted(v),
                     'holds_current_context_probe': any(
                         (v.get('dashboard_active') or {}).get('_memory_probe') is ref()
                         for ref in probes.get('context', ()) if ref() is not None)}
                    for k, v in aa._READ_CACHE.items()]
        owners = read_owners()
        collected = None
        after_gc_rss = after_gc_blocks = gc_live = None
        if args.gc_each or i == args.actions - 1:
            collected = gc.collect()
            after_gc_rss, after_gc_blocks = rss(), sys.getallocatedblocks()
            gc_live = {k: sum(r() is not None for r in refs) for k, refs in probes.items()}
        # Verification is after memory sampling; discard the full comparison
        # payload before the next action, keeping only a digest in the report.
        # A child verifies persisted history/state so comparison copies cannot
        # inflate this long-lived parent's resident-memory series.
        fingerprint_code = ('import sys,json; from nba_gm_data.save import load_save; '
            'from verify_simulation_consistency import business_state,digest; '
            's=load_save(sys.argv[1],include_history=True); '
            'print(json.dumps({"date":s["state"]["current_date"],"digest":digest(business_state(s))}))')
        fingerprint = json.loads(subprocess.check_output([sys.executable, '-c', fingerprint_code, str(path)], text=True))
        assert fingerprint['date'] == '2027-02-04'
        state_digest = fingerprint['digest']
        row = {'action': i+1, 'seconds_instrumented': seconds, 'status': status,
               'completion_rss_bytes': complete_rss, 'after_gc_rss_bytes': after_gc_rss,
               'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               'completion_allocated_blocks': complete_blocks, 'after_gc_allocated_blocks': after_gc_blocks,
               'collected_diagnostic': collected, 'live_before_gc': complete_live, 'live_after_gc': gc_live,
               'sampled_probes': {k: len(v) for k, v in probes.items()},
               'read_cache_entries': len(aa._READ_CACHE), 'read_cache_owners': owners,
               'business_digest': state_digest, 'events_digest': digest(event_hashes),
               'event_count': len(event_hashes)}
        rows.append(row)
        report = {'source_unchanged': hashlib.sha256(source.read_bytes()).hexdigest() == source_hash,
                  'initial_rss_bytes': start_rss, 'initial_allocated_blocks': start_blocks, 'actions': rows,
                  'gc_is_diagnostic_only': True, 'gc_each_action': args.gc_each,
                  'payloads_retained_by_harness': False, 'same_career_path': args.same_path}
        (args.output / 'memory-series.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(row), flush=True)
assert len({r['business_digest'] for r in rows}) == len({r['events_digest'] for r in rows}) == 1
