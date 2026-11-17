"""Separate instrumented app-action profile and memory measurement."""
from collections import Counter
from contextlib import ExitStack
import json
from pathlib import Path
import resource
import runpy
import sys
from package_search_diagnostics import instrument

output=Path(sys.argv[sys.argv.index('--output')+1])
metrics=Counter()
with instrument(metrics):
    runpy.run_path(str(Path(__file__).with_name('benchmark_advance_speed.py')),run_name='__main__')
metrics['max_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
(output/'package-diagnostics.json').write_text(json.dumps(dict(metrics),indent=2)+'\n')
print(json.dumps(dict(metrics)),flush=True)
