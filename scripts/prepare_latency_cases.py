"""Existing short checkpoints; one ordinary-day setup advance, outside timing."""
import argparse,hashlib,json
from pathlib import Path
from nba_gm_data.app_actions import dispatch_app_action,load_app_canonical
from nba_gm_data.save_recovery import create_export,restore_export

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=root/'output/end-to-end-latency')
base=parser.parse_args().output.resolve();base.mkdir(parents=True,exist_ok=True)
sources={
 'offday':root/'output/context-demand-pass/checkpoints/midway-reload/career.json',
 'game':root/'output/trade-presentation-task-1/fixtures/month17/trade_month.json',
 'busy':root/'output/pick-investment-2026-10-28/stable17/saves/trade_year.json',
 'month':root/'output/trade-presentation-task-1/fixtures/month17/trade_month.json'}
report={}
for name,path in sources.items():
    sha=hashlib.sha256(path.read_bytes()).hexdigest();archive=create_export(path)
    if name=='game':
        folder=base/'setup-game';folder.mkdir();copy=folder/'career.json';restore_export(copy,archive)
        dispatch_app_action('advance_save',{'save_path':str(copy),'to_date':'2026-10-29','seed':17},
                           root=root,save_dir=folder,canonical=load_app_canonical(root))
        archive=create_export(copy)
    target={'offday':'2026-10-31','game':'2026-10-30','busy':'2027-02-04','month':'2026-11-01'}[name]
    (base/(name+'.zip')).write_bytes(archive)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    report[name]={'source':str(path),'source_sha256':sha,'target':target,'archive':str(base/(name+'.zip'))}
(base/'cases.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
