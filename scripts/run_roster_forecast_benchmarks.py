"""Sequential paired wall samples preserving Stage B as the pre-edit reference."""
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = Path('output/roster-forecast-pass')
cases = {
    'seed17': ('output/pick-investment-2026-10-28/stable17/saves/trade_year.json', '2027-02-04'),
    'seed29': ('output/trade-presentation-task-1/fixtures/seed29/trade_year.json', '2027-02-04'),
    'month17': ('output/trade-presentation-task-1/fixtures/month17/trade_month.json', '2026-11-01'),
}
for case, (source, target) in cases.items():
    for sample in (1, 2):
        for version in ('before', 'after'):
            folder = BASE / f'{version}-{case}-{sample}'
            if (folder / 'report.json').exists():
                continue
            assert not folder.exists(), f'Incomplete sample: {folder}'
            ref = BASE / 'reference'
            script = ref / 'scripts/benchmark_advance_speed.py' if version == 'before' else Path('scripts/benchmark_advance_speed.py')
            env = {**os.environ, 'PYTHONPATH': f'{ref}/src:{ref}/scripts' if version == 'before' else 'src:scripts'}
            print(f'Starting {version} {case} sample {sample}', flush=True)
            subprocess.run([sys.executable, str(script), '--save', source, '--target', target,
                            '--output', str(folder)], env=env, check=True)
            report = json.loads((folder / 'report.json').read_text())
            assert report['through'] == target and report['source_unchanged'], report
            if version == 'after':
                old = BASE / f'before-{case}-{sample}'
                assert json.loads((old / 'business.json').read_text()) == json.loads((folder / 'business.json').read_text()), case
                assert json.loads((old / 'report.json').read_text())['progress_digest'] == report['progress_digest'], case
