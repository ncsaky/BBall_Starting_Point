"""Capture bounded pre-edit settlement inputs, outside any timing comparison."""
import gzip,json,runpy,sys
from pathlib import Path
from unittest.mock import patch
from nba_gm_data import transactions as tx

base=Path('output/settlement-materialization-pass/inputs');base.mkdir(exist_ok=False)
apply=tx.apply_trade_to_state;count=0
def capture(saved,*a,**kw):
    global count
    assert count<12
    canonical=kw.get('canonical')
    if count==0:
        with gzip.open(base/'canonical.json.gz','wt') as f:
            json.dump({k:v for k,v in canonical.items() if not k.startswith('_')},f)
    with gzip.open(base/f'settlement-{count}.json.gz','wt') as f:
        json.dump({'saved':saved,'args':a,'kwargs':{k:v for k,v in kw.items() if k!='canonical'}},f)
    count+=1
    return apply(saved,*a,**kw)
with patch.object(tx,'apply_trade_to_state',capture):
    sys.argv=['scripts/benchmark_advance_speed.py','--save','output/pick-investment-2026-10-28/stable17/saves/trade_year.json',
        '--target','2027-02-04','--output','output/settlement-materialization-pass/reference-capture']
    runpy.run_path('scripts/benchmark_advance_speed.py',run_name='__main__')
print('Captured settlements:',count)
