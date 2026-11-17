"""Two paired samples per bounded checkpoint; run only in a quiet window."""
import json,os,subprocess,sys
from pathlib import Path

base=Path('output/settlement-materialization-pass')
cases={'seed17':('output/pick-investment-2026-10-28/stable17/saves/trade_year.json','2027-02-04'),
       'seed29':('output/trade-presentation-task-1/fixtures/seed29/trade_year.json','2027-02-04'),
       'month17':('output/trade-presentation-task-1/fixtures/month17/trade_month.json','2026-11-01')}
for case,(source,target) in cases.items():
    for sample,order in ((1,('before','after')),(2,('after','before'))):
        for version in order:
            folder=base/f'{version}-{case}-{sample}'
            if (folder/'report.json').exists():continue
            assert not folder.exists(),folder
            path=str(base/'reference/src') if version=='before' else 'src'
            print(folder,flush=True)
            subprocess.run([sys.executable,'scripts/capture_benchmark_response.py','--save',source,
                '--target',target,'--output',str(folder)],env={**os.environ,'PYTHONPATH':path+':scripts'},check=True)
    for i in (1,2):
        old,new=base/f'before-{case}-{i}',base/f'after-{case}-{i}'
        assert json.loads((old/'business.json').read_text())==json.loads((new/'business.json').read_text())
        a,b=[json.loads((p/'report.json').read_text()) for p in (old,new)]
        assert a['progress_digest']==b['progress_digest'] and a['through']==b['through']==target
