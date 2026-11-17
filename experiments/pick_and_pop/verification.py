"""Authentic accepted-milestone9 comparison, never shared changed functions."""
from contextlib import ExitStack
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import json
import sys
from unittest.mock import patch

from experiments.expanded_cohort_performance.verification import reference_config,use_reference,prepare
from .fixtures import REFERENCE


def reference_modules():
    modules={};hashes=json.loads((REFERENCE/'hashes.json').read_text())
    with ExitStack() as stack:
        for name in ('experimental_inputs','interior_defense','offense_response','creation_passing','screen_navigation','shot_geometry','action_choice','interior_game','sim'):
            path=REFERENCE/(name+'.py.reference');assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[f'src/nba_gm_data/{name}.py']
            full='nba_gm_data._pop_frozen_'+name
            spec=importlib.util.spec_from_loader(full,SourceFileLoader(full,str(path)));m=importlib.util.module_from_spec(spec);sys.modules[full]=m;spec.loader.exec_module(m)
            key='nba_gm_data.'+name;modules[key]=m;stack.enter_context(patch.dict(sys.modules,{key:m}))
    return modules
