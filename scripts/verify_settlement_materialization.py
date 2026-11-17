"""Serial attribution, memory and targeted checks, separate from wall timings."""
import os,subprocess,sys
from pathlib import Path

base=Path('output/settlement-materialization-pass')
for version,source in (('before',str(base/'reference/src')),('after','src')):
    env={**os.environ,'PYTHONPATH':source+':scripts:tests'}
    jobs=[('attribution-'+version,'diagnose_settlement_materialization.py',[
        '--save','output/pick-investment-2026-10-28/stable17/saves/trade_year.json',
        '--target','2027-02-04'],'settlements.json'),
        ('memory-'+version,'probe_settlement_action_memory.py',['--actions','4'],'settlement-lifetimes.json')]
    for label,script,extra,marker in jobs:
        folder=base/label
        if (folder/marker).exists():continue
        assert not folder.exists(),folder
        print(label,flush=True)
        with (base/(label+'.log')).open('w') as log:
            subprocess.run([sys.executable,'scripts/'+script,'--output',str(folder),*extra],
                           env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
