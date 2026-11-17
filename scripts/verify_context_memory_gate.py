"""Sequential controls for same-career lifetime and pre-existing read retention."""
import os
from pathlib import Path
import subprocess
import sys

BASE = Path('output/context-demand-pass')
jobs = [
    ('same-path-before', 'probe_context_action_memory.py', str(BASE/'reference/src'), ['--actions','3','--same-path'], 'memory-series.json'),
    ('same-path-after', 'probe_context_action_memory.py', 'src', ['--actions','3','--same-path'], 'memory-series.json'),
    ('read-retention-roster-parent', 'probe_read_context_retention.py', 'output/roster-forecast-pass/reference/src', ['--reads','3'], 'retention.json'),
    ('read-retention-after', 'probe_read_context_retention.py', 'src', [], 'retention.json'),
]
for label, script, path, extra, marker in jobs:
    folder = BASE / label
    if (folder / marker).exists():
        continue
    assert not folder.exists(), folder
    print(label, flush=True)
    with (BASE/(label+'.log')).open('w') as log:
        subprocess.run([sys.executable, 'scripts/'+script, '--output', str(folder), *extra],
                       env={**os.environ,'PYTHONPATH':path+':scripts'}, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
