"""Trace retained Python allocations from real dashboard reads across careers."""
import argparse
import gc
import json
from pathlib import Path
import resource
import tracemalloc
from nba_gm_data import app_actions as aa
from nba_gm_data.save_recovery import create_export, restore_export

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--reads', type=int, default=6)
args = parser.parse_args()
assert 3 <= args.reads <= 8
args.output.mkdir(parents=True, exist_ok=False)
root = Path(__file__).resolve().parents[1]
source = root / 'output/pick-investment-2026-10-28/stable17/saves/trade_year.json'
archive = create_export(source)
canonical = aa.load_app_canonical(root)
paths = []
for i in range(args.reads):
    folder = args.output / str(i+1)
    folder.mkdir()
    path = folder / 'career.json'
    restore_export(path, archive)
    paths.append(path)
gc.collect()
tracemalloc.start(1)
rows = []
for i, path in enumerate(paths):
    result = aa.dispatch_app_action('dashboard_snapshot', {'save_path': str(path.resolve())},
                                  root=root, save_dir=path.parent.resolve(), canonical=canonical)
    del result
    gc.collect()  # Diagnostic: distinguish strongly retained objects from cycles.
    current, peak = tracemalloc.get_traced_memory()
    rows.append({'read': i+1, 'traced_retained_bytes_after_gc': current, 'traced_peak_bytes': peak,
                 'read_cache_entries': len(aa._READ_CACHE),
                 'retained_full_contexts': sum('dashboard_active' in c for c in aa._READ_CACHE.values())})
    print(json.dumps(rows[-1]), flush=True)
snapshot = tracemalloc.take_snapshot()
top = [{'location': str(s.traceback[0]), 'bytes': s.size, 'allocations': s.count}
       for s in snapshot.statistics('lineno')[:12]]
report = {'reads': rows, 'retained_allocation_sites': top,
          'cache_paths': list(aa._READ_CACHE), 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          'gc_is_diagnostic_only': True, 'action_responses_retained_by_harness': False}
(args.output / 'retention.json').write_text(json.dumps(report, indent=2)+'\n')
tracemalloc.stop()
