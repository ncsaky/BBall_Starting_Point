"""Small traced-allocation control, separate from full-action RSS and timings."""
from copy import deepcopy
import argparse,gc,gzip,json,resource,tracemalloc
from pathlib import Path
from nba_gm_data import transactions as tx
from verify_simulation_consistency import digest,business_state

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
inputs=Path('output/settlement-materialization-pass/inputs')
source=json.load(gzip.open(inputs/'canonical.json.gz','rt'))
case=json.load(gzip.open(inputs/'settlement-0.json.gz','rt'))
def run():
    saved=deepcopy(case['saved'])
    result=tx.apply_trade_to_state(saved,*case['args'],canonical=source,**case['kwargs'])
    assert result['status']=='applied'
    return digest(business_state(saved))
expected=run();gc.collect()  # Warm immutable source/config loading; keep no trial graph.
tracemalloc.start(1);rows=[]
for i in range(4):
    assert run()==expected
    gc.collect()  # Diagnostic only, outside production and headline wall runs.
    current,peak=tracemalloc.get_traced_memory()
    rows.append({'replay':i+1,'retained_python_bytes':current,'peak_traced_bytes':peak,
                 'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
report={'replays':rows,'digest':expected,'forced_gc_is_diagnostic_only':True,
        'purpose':'Check retained allocation sizes after completed single-settlement replays; not a full-action RSS substitute.'}
(args.output/'retention.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
