"""Bounded daily/bulk/midway-export-reload parity on the archived month fixture."""
import argparse
import json
from pathlib import Path
from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save import load_save
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.simulation_progress import progress_listener
from verify_simulation_consistency import business_state, digest, differences

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=root/'output/market-review-task-2')
parser.add_argument('--bulk-reference',type=Path,default=root/'output/market-review-task-2/after-month17')
args=parser.parse_args()
base=args.output.resolve()
base.mkdir(parents=True,exist_ok=True)
source=root/'output/trade-presentation-task-1/fixtures/month17/trade_month.json'
archive=create_export(source)
expected=json.loads((args.bulk_reference/'business.json').read_text())
events=json.loads((args.bulk_reference/'report.json').read_text())
report={}
for mode in ('daily','midway-reload'):
    folder=base/mode
    folder.mkdir()
    path=folder/'career.json'
    restore_export(path,archive)
    canonical=load_app_canonical(root)
    frames=[]
    with progress_listener(lambda e:frames.append(digest(e))):
        for endpoint in (['2026-10-29','2026-10-30','2026-10-31','2026-11-01'] if mode=='daily' else ['2026-10-30','2026-11-01']):
            saved=load_save(path)
            dispatch_app_action('advance_save',{'save_path':str(path),'to_date':endpoint,'seed':saved['meta']['seed'],
                'checkpoint_days':31},root=root,save_dir=folder,canonical=canonical)
            assert load_save(path)['state']['current_date']==endpoint
            if mode=='midway-reload' and endpoint=='2026-10-30':
                exported=create_export(path)
                path=folder/'reloaded.json'
                restore_export(path,exported)
                canonical=load_app_canonical(root)
    state=business_state(load_save(path,include_history=True))
    row={'business_equal':state==expected,'ordered_events_equal':digest(frames)==events['progress_digest'],
         'progress_frames':len(frames),'differences':differences(expected,state)}
    report[mode]=row
    (folder/'business.json').write_text(json.dumps(state,sort_keys=True))
    print(json.dumps({mode:row}),flush=True)
(base/'checkpoints.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(r['business_equal'] and r['ordered_events_equal'] for r in report.values()),report
