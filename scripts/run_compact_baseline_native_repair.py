"""Milestone16 scoped compact integration, arithmetic and versioned bearing.
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_compact_baseline_native_repair.py STAGE
"""
from contextlib import nullcontext
from dataclasses import replace
import argparse
import hashlib
import json
import time
from unittest.mock import patch
from nba_gm_data import action_choice,creation_passing,sim
from nba_gm_data.schema import to_plain
from experiments.boundary_aware_projection.states import states
from experiments.compact_baseline_native_repair.fixtures import fixture,pool,converted,IDS
from experiments.compact_baseline_native_repair.verification import BASE,REFERENCE,OUT,ROOT,reference_modules,reference_config
from experiments.action_choice_consistency.fixtures import observed_draws
import scripts.run_pass_recovery as prior


def write(name,data):(OUT/name).write_text(json.dumps(to_plain(data),indent=2,allow_nan=False)+'\n')
def read(name):return json.loads((OUT/name).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def integration():
    rows=[];functions=(action_choice.project_candidate,action_choice.project_choices,creation_passing.resolve_candidate)
    for group in ('development','held_out'):
        for meta,f,o in states(group):
            detailed=action_choice.project_choices(converted(f,'detailed_python_v1'),o);compact=action_choice.project_choices(converted(f),o)
            equal=detailed['scores']==compact['scores'] and detailed['effective_choice_probabilities']==compact['effective_choice_probabilities'] and all(v['expected_points']==compact['candidates'][k]['expected_points'] and v.get('branches')==compact['candidates'][k].get('branches') for k,v in detailed['candidates'].items())
            assert equal,(meta,detailed,compact);rows.append({**meta,'numerical_exact':True,'detailed':detailed,'compact':compact})
            assert functions==(action_choice.project_candidate,action_choice.project_choices,creation_passing.resolve_candidate)
    write('pre-correction-scoped-integration.json',rows);write('integration-summary.json',{'states':len(rows),'all_numeric_exact':True,'global_function_identities_unchanged':True,'geometry_model':'legacy_bearing_v1','normal_gameplay_activation':False})


if __name__=='__main__':
    from experiments.compact_baseline_native_repair import study
    stages=('integration','development','geometries','direct','mapped_native','seal','held_out','high_order','parity','mixed','costs','memory','tests','adapter','finalize')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=stages);args=parser.parse_args();OUT.mkdir(exist_ok=True)
    if args.stage=='integration':integration()
    elif args.stage in ('development','held_out'):study.predictions(args.stage)
    else:getattr(study,args.stage)()
