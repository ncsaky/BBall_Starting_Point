"""Sequential bounded paired wall samples against this pass's frozen backend."""
import argparse
from datetime import datetime
import json,os,subprocess,sys
from pathlib import Path
from zoneinfo import ZoneInfo

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--case',choices=('seed17','seed29','month17'))
p.add_argument('--samples',type=int,choices=(1,2),default=2)
a=p.parse_args();base=Path('output/feature-input-pass')
cases={'seed17':('output/pick-investment-2026-10-28/stable17/saves/trade_year.json','2027-02-04'),
       'seed29':('output/trade-presentation-task-1/fixtures/seed29/trade_year.json','2027-02-04'),
       'month17':('output/trade-presentation-task-1/fixtures/month17/trade_month.json','2026-11-01')}
window={'start':datetime.now(ZoneInfo('America/Toronto')).isoformat(),'mode':'Sequential wall samples, separated from diagnostic/regression jobs. No UI or research hold requested.'}
(base/'wall-window-running.json').write_text(json.dumps(window,indent=2)+'\n')
for case,(source,target) in cases.items():
    if a.case and a.case!=case:continue
    for sample in range(1,a.samples+1):
        for version in (('before','after') if sample==1 else ('after','before')):
            folder=base/f'{version}-{case}-{sample}'
            if (folder/'report.json').exists():continue
            assert not folder.exists(),folder
            print(str(folder),flush=True)
            subprocess.run([sys.executable,'scripts/capture_benchmark_response.py','--save',source,'--target',target,'--output',str(folder)],
                env={**os.environ,'PYTHONPATH':str(base/'reference/src')+':scripts' if version=='before' else 'src:scripts'},check=True)
        paths=[base/f'{v}-{case}-{sample}' for v in ('before','after')]
        reports=[json.loads((x/'report.json').read_text()) for x in paths]
        assert json.loads((paths[0]/'business.json').read_text())==json.loads((paths[1]/'business.json').read_text()),case
        assert reports[0]['progress_digest']==reports[1]['progress_digest'],case
        print(json.dumps({'case':case,'sample':sample,'seconds':[r['seconds'] for r in reports],'saved':reports[0]['seconds']-reports[1]['seconds'],'state_events_equal':True}),flush=True)
window['end']=datetime.now(ZoneInfo('America/Toronto')).isoformat()
(base/f'wall-window-{a.case or "all"}-{a.samples}.json').write_text(json.dumps(window,indent=2)+'\n')
(base/'wall-window-running.json').unlink()
