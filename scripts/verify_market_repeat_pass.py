"""Serial attribution, lifetime and bounded endpoint checks after wall samples."""
import json,os,subprocess,sys
from pathlib import Path
base=Path('output/market-repeat-pass')
def read(folder,name):return json.loads((folder/name).read_text())
pairs=[]
for case in ('seed17','seed29','month17'):
    for i in (1,2):
        paths=[base/f'{v}-{case}-{i}' for v in ('before','after')]
        responses=[read(p,'response.json') for p in paths]
        for r in responses:
            r['dashboard_snapshot']['revision']='<file-revision>'
            r['result']['save']='<disposable-path>'
        assert responses[0]==responses[1],(case,i)
        pairs.append({'case':case,'sample':i,'full_response_equal':True})
        del responses
(base/'response-parity.json').write_text(json.dumps(pairs,indent=2)+'\n')
def run(script,arguments,version,output,marker):
    path=base/output
    if (path/marker).exists():return
    assert not path.exists(),path
    print(output,flush=True)
    with (base/(output+'.log')).open('w') as log:
        subprocess.run([sys.executable,'scripts/'+script,*arguments,'--output',str(path)],
            env={**os.environ,'PYTHONPATH':str(base/'reference/src')+':scripts' if version=='before' else 'src:scripts'},
            stdout=log,stderr=subprocess.STDOUT,check=True)
run('diagnose_market_repeats.py',['--save','output/pick-investment-2026-10-28/stable17/saves/trade_year.json','--target','2027-02-04','--profile'],'after','diagnostic-after','repeat-diagnostics.json')
for version in ('before','after'):
    run('probe_market_quote_memory.py',['--actions','3'],version,'memory-'+version,'quote-release.json')
run('verify_market_review_checkpoints.py',['--bulk-reference',str(base/'after-month17-1')],'after','checkpoints','checkpoints.json')
subprocess.run([sys.executable,'scripts/summarize_market_repeat_pass.py'],check=True)
