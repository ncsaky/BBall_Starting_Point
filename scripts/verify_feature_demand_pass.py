"""Serial post-timing attribution, memory, presentation and endpoint checks."""
import json,os,subprocess,sys
from pathlib import Path
base=Path('output/feature-input-pass')
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
args=['--save','output/pick-investment-2026-10-28/stable17/saves/trade_year.json','--target','2027-02-04']
run('diagnose_feature_demand.py',args,'after','demand-after','feature-demand.json')
run('capture_benchmark_response.py',[*args,'--profile'],'after','profile-after','profile.txt')
for version in ('before','after'):
    run('probe_feature_demand_memory.py',['--actions','3'],version,'memory-'+version,'feature-release.json')
run('verify_market_review_checkpoints.py',['--bulk-reference',str(base/'after-month17-1')],'after','checkpoints','checkpoints.json')
for version in ('before','after'):
    run('capture_contract_separation.py',['--canonical','data/canonical/universe_2026_27_offseason.json'],version,'new-career-'+version,'financial.json')
assert read(base/'new-career-before','financial.json')==read(base/'new-career-after','financial.json')
assert read(base/'new-career-before','player-card.json')==read(base/'new-career-after','player-card.json')
code = ('import json,sys; from nba_gm_data.save import load_save; '
        'from verify_simulation_consistency import business_state,digest; '
        'print(json.dumps([digest(business_state(load_save(p,include_history=True))) for p in sys.argv[1:]]))')
digests=json.loads(subprocess.check_output([sys.executable,'-c',code,
    str(base/'new-career-before/career.json'),str(base/'new-career-after/career.json')],
    env={**os.environ,'PYTHONPATH':'src:scripts'},text=True))
assert digests[0]==digests[1]
(base/'new-career-parity.json').write_text(json.dumps({'business_digests':dict(zip(('before','after'),digests)),
    'business_equal':True},indent=2)+'\n')
subprocess.run([sys.executable,'scripts/summarize_feature_demand_pass.py'],check=True)
