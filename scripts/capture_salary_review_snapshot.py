"""Capture the exact pre-market input on an isolated Stage-A app action."""
import argparse,hashlib,json
from pathlib import Path
from unittest.mock import patch
from nba_gm_data.app_actions import load_app_canonical,dispatch_app_action
from nba_gm_data.save import load_save
from nba_gm_data.save_recovery import create_export,restore_export
from nba_gm_data import transactions as tx

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--save',type=Path,required=True);parser.add_argument('--target',required=True)
parser.add_argument('--output',type=Path,required=True)
a=parser.parse_args();a.output.mkdir(parents=True)
original_hash=hashlib.sha256(a.save.read_bytes()).hexdigest()
archive=create_export(a.save);path=a.output/'career.json';restore_export(path,archive)
saved=load_save(path);canonical=load_app_canonical(ROOT)
class Captured(Exception):pass

def capture(source,from_date,through_date,**kw):
    inputs={k:v for k,v in source.items() if not k.startswith('_') or k in
            ('_human_team_ids','_trade_planning_save','_strategy_model_version')}
    (a.output/'canonical.json').write_text(json.dumps(inputs,sort_keys=True))
    (a.output/'call.json').write_text(json.dumps({'from':from_date,'through':through_date,'seed':kw.get('seed')},indent=2))
    raise Captured()
with patch.object(tx,'simulate_ai_trades',capture):
    try:dispatch_app_action('advance_save',{'save_path':str(path.resolve()),'to_date':a.target,
             'seed':saved['meta']['seed'],'checkpoint_days':31},root=ROOT,save_dir=a.output.resolve(),canonical=canonical)
    except Captured:pass
assert (a.output/'canonical.json').exists()
# Leave even this disposable copy playable after the diagnostic interruption.
restore_export(path,archive,replace=True)
assert original_hash==hashlib.sha256(a.save.read_bytes()).hexdigest()
print('Captured pre-market canonical input; source unchanged and disposable copy restored',flush=True)
