"""Sequential bounded task-2 comparisons against its preserved backend."""
import os
from pathlib import Path
import subprocess
import sys
BASE=Path('output/market-review-task-2')
SAVES={'seed17':('output/pick-investment-2026-10-28/stable17/saves/trade_year.json','2027-02-04'),
       'seed29':('output/trade-presentation-task-1/fixtures/seed29/trade_year.json','2027-02-04'),
       'month17':('output/trade-presentation-task-1/fixtures/month17/trade_month.json','2026-11-01')}
for version in ('before','after'):
    for case in ('seed17','seed17-repeat','seed29','seed29-repeat','month17','month17-repeat'):
        save,target=SAVES[case.replace('-repeat','')]
        output=BASE/f'{version}-{case}'
        if (output/'report.json').exists():
            continue
        if output.exists():
            raise RuntimeError(f'Incomplete output: {output}; move it aside before retrying')
        ref=BASE/'reference'
        script=ref/'scripts/benchmark_advance_speed.py' if version=='before' else Path('scripts/benchmark_advance_speed.py')
        env={**os.environ,'PYTHONPATH':f'{ref}/src:{ref}/scripts' if version=='before' else 'src:scripts'}
        print(f'Starting {version} {case}',flush=True)
        subprocess.run([sys.executable,str(script),'--save',save,'--target',target,'--output',str(output)],env=env,check=True)
