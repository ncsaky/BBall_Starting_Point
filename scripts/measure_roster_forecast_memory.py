"""Unprofiled app-action RSS, without recursive cache-inventory instrumentation."""
import json
from pathlib import Path
import resource
import runpy
import sys

output = Path(sys.argv[sys.argv.index('--output') + 1])
runpy.run_path(str(Path(__file__).with_name('benchmark_advance_speed.py')), run_name='__main__')
report = {'max_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          'profiled': False, 'recursive_inventory': False}
(output / 'memory.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
