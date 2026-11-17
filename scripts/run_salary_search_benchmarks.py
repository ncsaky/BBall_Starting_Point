"""Interleaved sequential Stage-A/Stage-B samples from disposable exports."""
import os
import json
from pathlib import Path
import subprocess
import sys
BASE=Path('output/salary-search-stage-b')
SAVES={'seed17':('output/pick-investment-2026-10-28/stable17/saves/trade_year.json','2027-02-04'),
       'seed29':('output/trade-presentation-task-1/fixtures/seed29/trade_year.json','2027-02-04'),
       'month17':('output/trade-presentation-task-1/fixtures/month17/trade_month.json','2026-11-01')}
for case,(save,target) in SAVES.items():
    for sample in (1,2):
        for version in ('stage-a','stage-b'):
            output=BASE/f'{version}-{case}-{sample}'
            if (output/'report.json').exists():continue
            if output.exists():raise RuntimeError(f'Incomplete output: {output}')
            ref=BASE/'reference'
            script=ref/'scripts/benchmark_advance_speed.py' if version=='stage-a' else Path('scripts/benchmark_advance_speed.py')
            env={**os.environ,'PYTHONPATH':f'{ref}/src:{ref}/scripts' if version=='stage-a' else 'src:scripts'}
            print(f'Starting {version} {case} sample {sample}',flush=True)
            subprocess.run([sys.executable,str(script),'--save',save,'--target',target,'--output',str(output)],env=env,check=True)
            report=json.loads((output/'report.json').read_text())
            assert report['through']==target, ('Endpoint stop requires inspection',output,report['through'],target)
