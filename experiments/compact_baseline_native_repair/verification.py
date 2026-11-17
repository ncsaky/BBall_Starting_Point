"""Authenticated milestone13 modules, including its detailed recovery policy."""
from contextlib import ExitStack
from dataclasses import fields,replace,asdict
from importlib.machinery import SourceFileLoader
import importlib.util
import hashlib
import json
import sys
from unittest.mock import patch
from experiments.mixed_pop_validation.verification import reference_config as base_config
from experiments.expanded_cohort_performance.verification import use_reference,prepare
from experiments.pass_recovery.fixtures import ROOT
BASE=ROOT/'output/compact-baseline-native-repair-2026-11-16';REFERENCE=BASE/'reference';OUT=BASE/'verified'


def reference_modules():
    modules={};hashes=json.loads((REFERENCE/'hashes.json').read_text())
    with ExitStack() as stack:
        for name in ('experimental_inputs','interior_defense','offense_response','creation_passing','screen_navigation','shot_geometry','pass_recovery','action_choice','interior_game','sim'):
            p=REFERENCE/(name+'.py.reference');assert hashlib.sha256(p.read_bytes()).hexdigest()==hashes['src/nba_gm_data/'+name+'.py']
            full='nba_gm_data._repair_frozen_'+name;spec=importlib.util.spec_from_loader(full,SourceFileLoader(full,str(p)));module=importlib.util.module_from_spec(spec);sys.modules[full]=module;spec.loader.exec_module(module)
            key='nba_gm_data.'+name;modules[key]=module;stack.enter_context(patch.dict(sys.modules,{key:module}))
    return modules


def reference_config(config,modules):
    if config is None:return None
    old=base_config(config,modules);creation=config.offense.creation if config.offense else None
    if creation and getattr(creation,'receipt_policy',None):
        c=old.offense.creation;r=modules['nba_gm_data.pass_recovery'];new=r.RecoveryCreationExperiment(**{f.name:getattr(c,f.name) for f in fields(c)},recovery=r.RecoveryCoefficients(**asdict(creation.recovery)))
        old=replace(old,offense=replace(old.offense,creation=new))
    return old
