"""Authenticated pre-optimization code, including its input types/validators."""
from contextlib import ExitStack,contextmanager
from dataclasses import asdict,fields
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import json
import sys
from unittest.mock import patch

from .pool import REFERENCE


def load(name):
    path=REFERENCE/(name+'.py.reference')
    expected=json.loads((REFERENCE/'hashes.json').read_text())[f'src/nba_gm_data/{name}.py']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Frozen source hash mismatch')
    full_name='nba_gm_data._expanded_frozen_'+name
    spec=importlib.util.spec_from_loader(full_name,SourceFileLoader(full_name,str(path)))
    module=importlib.util.module_from_spec(spec);sys.modules[full_name]=module;spec.loader.exec_module(module)
    return module


def reference_modules():
    modules={}
    with ExitStack() as stack:
        for name in ('experimental_inputs','interior_defense','offense_response','creation_passing',
                     'screen_navigation','shot_geometry','action_choice','interior_game','sim'):
            module=load(name);key='nba_gm_data.'+name;modules[key]=module
            stack.enter_context(patch.dict(sys.modules,{key:module}))
    return modules


@contextmanager
def use_reference(modules):
    import nba_gm_data
    with ExitStack() as stack:
        stack.enter_context(patch.dict(sys.modules,modules))
        for key,module in modules.items():stack.enter_context(patch.object(nba_gm_data,key.split('.')[-1],module,create=True))
        yield


def reference_config(config,modules):
    """Recompile same serialized values through fully frozen view/classes.

    One old immutable view per current view is retained across its projections;
    current optimized snapshot comparison/arrival constructors are not reused.
    """
    from nba_gm_data.experimental_inputs import InterpretedInputs
    e=modules['nba_gm_data.experimental_inputs'];d=modules['nba_gm_data.interior_defense']
    o=modules['nba_gm_data.offense_response'];c=modules['nba_gm_data.creation_passing'];s=modules['nba_gm_data.screen_navigation']
    views={}
    def inputs(value):
        if hasattr(value,'contract') and hasattr(value,'source'):
            key=id(value)
            if key not in views:views[key]=e.InterpretedInputs(value.source,e.InputInterpretation(**asdict(value.contract)))
            return views[key]
        return value
    def research(value):return not hasattr(value,'contract') and value.to_dict()['inputs']['S16']['value']['scale'].startswith('research_')
    anchors=tuple(d.Anchor(a.team_id,d.compile_profile(inputs(a.profile.inputs),a.profile.coefficients,
        research_scenario=a.profile.input_contract.startswith('research_')),d.ArrivalContext(**asdict(a.context))) for a in config.anchors)
    off=config.offense
    if off:
        profiles=tuple(o.compile_offense(inputs(p.inputs),p.coefficients,
            **({'research_scenario':True,'two_point_rim_fraction':.7} if p.input_contract.startswith('research_') else {})) for p in off.profiles)
        creation=off.creation
        if creation:
            screen=creation.screens
            if screen:screen=s.ScreenExperiment(tuple(s.compile_screen(inputs(p.inputs),roles=p.roles) for p in screen.profiles),screen.calls,screen.coefficients)
            creation=c.CreationExperiment(**({f.name:getattr(creation,f.name) for f in fields(c.CreationExperiment)}|
                {'profiles':tuple(c.compile_interaction(inputs(p.inputs),research_scenario=research(p.inputs)) for p in creation.profiles),'screens':screen}))
        off=o.CombinedOffense(**({f.name:getattr(off,f.name) for f in fields(o.CombinedOffense)}|{'profiles':profiles,'creation':creation}))
    return d.InteriorExperiment(**({f.name:getattr(config,f.name) for f in fields(d.InteriorExperiment)}|{'anchors':anchors,'offense':off}))


def prepare(context,config,modules,start=None):
    pools={t['id']:[{'player':p,'minutes':48} for p in context['canonical']['players'] if p['team_id']==t['id']] for t in context['canonical']['teams']}
    anchors={tid:config.anchor(tid) for tid in pools};contexts={tid:a.context if a else None for tid,a in anchors.items()}
    coupled=modules['nba_gm_data.offense_response'].prepare_coupled(config.offense,pools,anchors,contexts)
    state=modules['nba_gm_data.creation_passing'].prepare_creation(config.offense.creation,coupled,pools,anchors,contexts)
    if start is not None:state['coupled']['positions']['response_b']=start
    return state
