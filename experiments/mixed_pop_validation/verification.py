"""Fully frozen accepted milestone10, including pop input/profile/call types."""
from contextlib import ExitStack
from dataclasses import asdict,fields
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import json
import sys
from unittest.mock import patch
from experiments.expanded_cohort_performance.verification import use_reference,prepare
from .diagnosis import REFERENCE


def reference_modules():
    result={};hashes=json.loads((REFERENCE/'hashes.json').read_text())
    with ExitStack() as stack:
        for name in ('experimental_inputs','interior_defense','offense_response','creation_passing','screen_navigation','shot_geometry','action_choice','interior_game','sim'):
            path=REFERENCE/(name+'.py.reference');assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[f'src/nba_gm_data/{name}.py']
            full='nba_gm_data._mixed_pop_frozen_'+name;spec=importlib.util.spec_from_loader(full,SourceFileLoader(full,str(path)))
            m=importlib.util.module_from_spec(spec);sys.modules[full]=m;spec.loader.exec_module(m);key='nba_gm_data.'+name;result[key]=m;stack.enter_context(patch.dict(sys.modules,{key:m}))
    return result


def reference_config(config,modules):
    e=modules['nba_gm_data.experimental_inputs'];d=modules['nba_gm_data.interior_defense'];o=modules['nba_gm_data.offense_response'];c=modules['nba_gm_data.creation_passing'];s=modules['nba_gm_data.screen_navigation'];views={}
    def view(v):
        if not hasattr(v,'contract'):return v
        if id(v) not in views:views[id(v)]=e.InterpretedInputs(v.source,e.InputInterpretation(**asdict(v.contract)))
        return views[id(v)]
    anchors=tuple(d.Anchor(a.team_id,d.compile_profile(view(a.profile.inputs),a.profile.coefficients,research_scenario=a.profile.input_contract.startswith('research_')),d.ArrivalContext(**asdict(a.context))) for a in config.anchors)
    off=config.offense
    if off:
        profiles=tuple(o.compile_offense(view(p.inputs),p.coefficients,**({'research_scenario':True,'two_point_rim_fraction':.7} if p.input_contract.startswith('research_') else {})) for p in off.profiles)
        creation=off.creation
        if creation:
            screen=creation.screens
            if screen:
                pop=hasattr(screen,'timing_policy')
                profiles_s=tuple(s.compile_screen(view(p.inputs),roles=p.roles,**({'pop_routes':True} if hasattr(p,'relocation') else {})) for p in screen.profiles)
                calls=tuple((s.PopScreenCall if hasattr(call,'pop_end') else s.ScreenCall)(**asdict(call)) for call in screen.calls)
                screen=s.PopScreenExperiment(profiles_s,calls,screen.coefficients,screen.timing_policy) if pop else s.ScreenExperiment(profiles_s,calls,screen.coefficients)
            def research(v):return not hasattr(v,'contract') and v.to_dict()['inputs']['S16']['value']['scale'].startswith('research_')
            creation=c.CreationExperiment(**({f.name:getattr(creation,f.name) for f in fields(c.CreationExperiment)}|{'profiles':tuple(c.compile_interaction(view(p.inputs),research_scenario=research(p.inputs)) for p in creation.profiles),'screens':screen}))
        off=o.CombinedOffense(**({f.name:getattr(off,f.name) for f in fields(o.CombinedOffense)}|{'profiles':profiles,'creation':creation}))
    return d.InteriorExperiment(**({f.name:getattr(config,f.name) for f in fields(d.InteriorExperiment)}|{'anchors':anchors,'offense':off}))
