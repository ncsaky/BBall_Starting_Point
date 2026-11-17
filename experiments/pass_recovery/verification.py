"""Authenticated accepted milestone11; new receipt policy is never shared in."""
from contextlib import ExitStack
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import json
import sys
from unittest.mock import patch
from experiments.mixed_pop_validation.verification import reference_config as _config,use_reference,prepare
from .fixtures import REFERENCE


def reference_modules():
    hashes=json.loads((REFERENCE/'hashes.json').read_text());modules={}
    with ExitStack() as stack:
        for name in ('experimental_inputs','interior_defense','offense_response','creation_passing','screen_navigation','shot_geometry','action_choice','interior_game','sim'):
            path=REFERENCE/(name+'.py.reference');assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[f'src/nba_gm_data/{name}.py']
            full='nba_gm_data._receipt_frozen_'+name;spec=importlib.util.spec_from_loader(full,SourceFileLoader(full,str(path)))
            module=importlib.util.module_from_spec(spec);sys.modules[full]=module;spec.loader.exec_module(module);key='nba_gm_data.'+name;modules[key]=module;stack.enter_context(patch.dict(sys.modules,{key:module}))
    return modules


def reference_config(config,modules):
    if config and config.offense and config.offense.creation and getattr(config.offense.creation,'receipt_policy',None):raise ValueError('New recovery configuration cannot masquerade as an untouched reference')
    return _config(config,modules)
