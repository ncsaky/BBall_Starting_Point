"""Exact frozen/current checks with complete event-domain RNG traces."""
from contextlib import nullcontext
from dataclasses import replace
import hashlib
import random
import struct
from unittest.mock import patch

from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from nba_gm_data.creation_passing import CHOICE_POLICY,HELP_RESPONSE_POLICY
from experiments.screen_navigation.fixtures import screen_fixture
from experiments.action_choice_consistency.fixtures import pinned_pilot,make_case
from .pool import load_pool
from .fixtures import fixture
from .probes import SCREEN,conditional
from .verification import reference_modules,reference_config,use_reference,prepare


def benchmarks(pool=None):
    c,x=screen_fixture(possessions=16)
    x=replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,help_response_policy=HELP_RESPONSE_POLICY,choice_policy=CHOICE_POLICY)))
    _,h,hx=make_case(pinned_pilot(),coverage='show_then_recover',start=None)
    _,e,ex=fixture(pool or load_pool(),**SCREEN)
    return [('native10',c,x),('helper6',h,hx),('expanded6',e,ex)]


def traced(context,config,seed=17,mode='replay-real-minutes',simulator=sim):
    real=random.Random;trace=[]
    class Traced(real):
        def __init__(self,*args,**kwargs):
            self.digest=hashlib.sha256();self.entry={'seed':repr(args),'draws':0,'digest':self.digest.hexdigest()};trace.append(self.entry)
            super().__init__(*args,**kwargs)
        def random(self):
            value=super().random();self.entry['draws']+=1;self.digest.update(struct.pack('!d',value));self.entry['digest']=self.digest.hexdigest();return value
    with patch.object(random,'Random',Traced):
        result=simulator.sim_game_with_context(context,context['schedule'][0]['externalGameId'],mode,seed,interior_experiment=config)
    return result,trace


def digest(value):return hashlib.sha256(__import__('json').dumps(to_plain(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def kernel_parity(items=None,modules=None):
    modules=modules or reference_modules();rows=[]
    for label,context,config in items or benchmarks():
        with use_reference(modules):old=reference_config(config,modules) if config else None
        for seed in (17,29):
            for mode in ('replay-real-minutes','sandbox-sim'):
                a,ta=traced(context,config,seed,mode)
                with use_reference(modules):b,tb=traced(context,old,seed,mode,modules['nba_gm_data.sim'])
                assert to_plain(a)==to_plain(b),(label,seed,mode,'result')
                assert ta==tb,(label,seed,mode,'RNG')
                rows.append({'fixture':label,'seed':seed,'mode':mode,'full_result_equal':True,'full_rng_equal':True,
                    'result_sha256':digest(a),'rng_domains':ta,'possessions':a.possessions})
    return rows


def candidate_parity(pool,modules=None):
    from .probes import cases
    modules=modules or reference_modules();rows=[]
    for name,kwargs in cases():
        state,context,config=fixture(pool,**kwargs)
        current={str(d):conditional(state,route_draw=d) for d in (.1,.5,.95)}
        with use_reference(modules):
            old=reference_config(config,modules);s=prepare(context,old,modules,kwargs.get('start'))
            s['audit_context']=state['audit_context']
            # conditional's imported functions point at current functions, so invoke
            # frozen choice/preparation directly instead of sharing changed code.
            from experiments.action_choice_consistency.fixtures import observed_draws
            previous={}
            for draw in (.1,.5,.95):
                draws=observed_draws();draws[39]=draw
                d=modules['nba_gm_data.creation_passing'].prepare_drive_decision(s,state['audit_context']['ids'][0],'response_a','response_b',draws,24)
                previous[str(draw)]={'terminated':d} if 'kind' in d else {'record':d['record'],'projection':modules['nba_gm_data.action_choice'].project_choices(d['frame'],d['options'])}
        assert current==previous,name
        rows.append({'case':name,'full_candidate_probabilities_scores_weights_records_equal':True,'sha256':digest(current)})
    return rows
