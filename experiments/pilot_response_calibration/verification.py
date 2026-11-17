"""Authenticated milestone-6 modules, including their own compilers/kernel."""
from contextlib import contextmanager
from dataclasses import fields
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
REFERENCE=ROOT/'output/pilot-response-calibration-2026-11-14/reference'


def load(name):
    path=REFERENCE/(name+'.py.reference')
    digest=json.loads((REFERENCE/'hashes.json').read_text())[f'src/nba_gm_data/{name}.py']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    module_name='nba_gm_data._response_frozen_'+name
    spec=importlib.util.spec_from_loader(module_name,SourceFileLoader(module_name,str(path)))
    module=importlib.util.module_from_spec(spec);sys.modules[module_name]=module;spec.loader.exec_module(module)
    return module


def reference_modules():
    modules={f'nba_gm_data.{name}':load(name) for name in
        ('creation_passing','offense_response','interior_defense','screen_navigation','shot_geometry')}
    with patch.dict(sys.modules,modules):
        modules['nba_gm_data.interior_game']=load('interior_game')
        modules['nba_gm_data.sim']=load('sim')
    return modules


@contextmanager
def use_reference(modules):
    with patch.dict(sys.modules,modules):yield


def reference_config(config,modules):
    """Recompile raw snapshots through frozen code; never reuse new projections."""
    from nba_gm_data.experimental_inputs import InterpretedInputs
    d=modules['nba_gm_data.interior_defense'];o=modules['nba_gm_data.offense_response']
    c=modules['nba_gm_data.creation_passing'];s=modules['nba_gm_data.screen_navigation']
    def research(p):return not isinstance(p.inputs,InterpretedInputs) and p.inputs.to_dict()['inputs']['S16']['value']['scale'].startswith('research_')
    anchors=tuple(d.Anchor(a.team_id,d.compile_profile(a.profile.inputs,a.profile.coefficients,
        research_scenario=a.profile.input_contract.startswith('research_')),a.context) for a in config.anchors)
    off=config.offense
    if off:
        profiles=tuple(o.compile_offense(p.inputs,p.coefficients,**({'research_scenario':True,'two_point_rim_fraction':.7} if p.input_contract.startswith('research_') else {})) for p in off.profiles)
        creation=off.creation
        if creation:
            screen=creation.screens
            if screen:screen=s.ScreenExperiment(tuple(s.compile_screen(p.inputs,roles=p.roles) for p in screen.profiles),screen.calls,screen.coefficients)
            creation=c.CreationExperiment(**({f.name:getattr(creation,f.name) for f in fields(c.CreationExperiment)}|
                {'profiles':tuple(c.compile_interaction(p.inputs,research_scenario=research(p)) for p in creation.profiles),'screens':screen}))
        off=o.CombinedOffense(**({f.name:getattr(off,f.name) for f in fields(o.CombinedOffense)}|{'profiles':profiles,'creation':creation}))
    return d.InteriorExperiment(**({f.name:getattr(config,f.name) for f in fields(d.InteriorExperiment)}|{'anchors':anchors,'offense':off}))
