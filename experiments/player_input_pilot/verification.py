"""Authenticated pre-milestone module comparisons; no changed compiler reuse."""
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
REFERENCE=ROOT/'output/player-input-pilot-2026-11-14/reference'


def load_reference(name):
    path=REFERENCE/(name+'.py.reference');expected=json.loads((REFERENCE/'hashes.json').read_text())[f'src/nba_gm_data/{name}.py']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
    spec=importlib.util.spec_from_loader('nba_gm_data._pilot_frozen_'+name,SourceFileLoader('nba_gm_data._pilot_frozen_'+name,str(path)))
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


def reference_modules():
    modules={f'nba_gm_data.{name}':load_reference(name) for name in ('offense_response','creation_passing','interior_defense','screen_navigation','shot_geometry')}
    with patch.dict(sys.modules,modules):
        kernel=load_reference('interior_game');modules['nba_gm_data.interior_game']=kernel
        simulator=load_reference('sim')
    return modules,kernel,simulator


def reference_config(config,modules):
    defense=modules['nba_gm_data.interior_defense'];offense=modules['nba_gm_data.offense_response'];creation=modules['nba_gm_data.creation_passing'];screen=modules['nba_gm_data.screen_navigation']
    anchors=tuple(defense.Anchor(a.team_id,defense.compile_profile(a.profile.inputs,a.profile.coefficients,research_scenario=a.profile.input_contract.startswith('research_')),a.context) for a in config.anchors)
    off=config.offense
    if off is not None:
        profiles=tuple(offense.compile_offense(p.inputs,p.coefficients,**({'research_scenario':True,'two_point_rim_fraction':.7} if p.input_contract.startswith('research_') else {})) for p in off.profiles)
        c=off.creation
        if c is not None:
            profiles_c=tuple(creation.compile_interaction(p.inputs,research_scenario=p.inputs.to_dict()['inputs']['S16']['value']['scale'].startswith('research_')) for p in c.profiles)
            s=c.screens
            if s is not None:s=screen.ScreenExperiment(tuple(screen.compile_screen(p.inputs,roles=p.roles) for p in s.profiles),s.calls,s.coefficients)
            c=creation.CreationExperiment(**({f.name:getattr(c,f.name) for f in fields(creation.CreationExperiment)}|{'profiles':profiles_c,'screens':s}))
        off=offense.CombinedOffense(**({f.name:getattr(off,f.name) for f in fields(offense.CombinedOffense)}|{'profiles':profiles,'creation':c}))
    return defense.InteriorExperiment(**({f.name:getattr(config,f.name) for f in fields(defense.InteriorExperiment)}|{'anchors':anchors,'offense':off}))


@contextmanager
def use_reference(modules):
    with patch.dict(sys.modules,modules):yield


def pre_optimization_module():
    base=ROOT/'output/player-input-pilot-2026-11-14/cost-audit';path=base/'screen_navigation.pre-optimization.py'
    expected=json.loads((base/'pre-optimization-source.json').read_text())['sha256']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
    spec=importlib.util.spec_from_file_location('nba_gm_data._pilot_before_exact_validation_reuse',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


def pre_optimization_config(config,module):
    from dataclasses import replace
    c=config.offense.creation;s=c.screens
    previous=module.ScreenExperiment(tuple(module.compile_screen(p.inputs,roles=p.roles) for p in s.profiles),s.calls,s.coefficients)
    return replace(config,offense=replace(config.offense,creation=replace(c,screens=previous)))


def traced_game(context,config,seed=17,mode='replay-real-minutes',*,pre_optimization=None):
    import random
    import struct
    from contextlib import nullcontext
    from nba_gm_data import sim
    real=random.Random;trace=[]
    class TracedRandom(real):
        def __init__(self,*args,**kwargs):
            self.entry={'seed':repr(args),'draws':0,'digest':hashlib.sha256(b'').hexdigest()};self.digest=hashlib.sha256();trace.append(self.entry)
            super().__init__(*args,**kwargs)
        def random(self):
            value=super().random();self.entry['draws']+=1;self.digest.update(struct.pack('!d',value));self.entry['digest']=self.digest.hexdigest();return value
    hook=patch('nba_gm_data.screen_navigation.prepare_screens',pre_optimization.prepare_screens) if pre_optimization else nullcontext()
    game_id=context['schedule'][0]['externalGameId']
    with hook,patch('nba_gm_data.interior_game.random.Random',TracedRandom):
        result=sim.sim_game_with_context(context,game_id,mode,seed,interior_experiment=config)
    return result,trace
