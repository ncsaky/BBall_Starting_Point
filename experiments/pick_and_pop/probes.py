"""Supplied opportunities and declared single-component causal contrasts."""
from dataclasses import replace,fields
from nba_gm_data.screen_navigation import ScreenCall,ScreenExperiment,compile_screen
from nba_gm_data.creation_passing import prepare_drive_decision
from nba_gm_data.action_choice import project_choices
from experiments.expanded_cohort_performance.probes import sample
from experiments.action_choice_consistency.fixtures import observed_draws
from .fixtures import pool,fixture,IDS


def central_cases():
    for action in ('screen','roll','slip','pop'):
        for coverage in ('stay','show_then_recover'):
            for label,start in [('early',(1.4,4.6)),('reference',(2,5.5)),('late',(4.5,8))]:
                yield f'{action}_{coverage}_{label}',dict(action=action,coverage=coverage,creator_start=start)


def causal_cases():
    for actor,key,values in [('turner','S01',(10,95)),('turner','S08',(10,95)),('turner','S09',(10,95)),
        ('turner','S14',(10,95)),('turner','S26',(10,95)),('turner','S27',(10,95)),('turner','S28',(10,95)),
        ('turner','T01',(.1,.9)),('curry','F06.recognition',(10,95)),('curry','F06.execution',(10,95)),
        ('curry','S17',(10,95)),('wemb','S40',(10,95))]:
        for value in values:
            yield f'synthetic_{actor}_{key}_{value}',{actor:{key:value}},dict(coverage='stay' if key in ('S08','S40') else 'show_then_recover')
    yield 'synthetic_zero_willingness',{'turner':{'T01':0}},{}
    yield 'synthetic_nonspacing_pop',{'turner':{'S01':10,'T01':.1}},{}
    yield 'synthetic_close_stay',{},dict(coverage='stay',coverage_start=(3,7.4))
    yield 'synthetic_deep_pop',{},dict(pop_end=(3,8.5))


def decision(state,remaining=24,draws=None):
    return prepare_drive_decision(state,IDS['curry'],'response_a','response_b',observed_draws() if draws is None else draws,remaining)


def run_case(p,name,kwargs,n=256,remaining=24):
    s,c,x=fixture(p,**kwargs);d=decision(s,remaining);record=d.get('record',{})
    projection=project_choices(d['frame'],d['options']) if 'frame' in d else None
    return {'name':name,'configuration':kwargs,'remaining_s':remaining,'audit':s['audit_context'],
        'sample':sample(s,n=n,remaining=remaining),'conditional_record':record,'projection':projection,
        'conditional_options':d.get('options',{}),'configuration_revision':x.revision}


def legacy_turner():
    """Explicit called-roll baseline, not a pop preference renormalization.

    Same pod and old-source values/role completions as initial named trial;
    T11 is a separate all-roll tactical control. This is an intentionally
    different route fixture, never an exact-behavior or grade-correction claim.
    """
    p=pool(changes={'turner':{'T11':{'screen':0,'roll':1,'slip':0,'pop':0}}})
    _,c,x=fixture(p,action='roll');new=x.offense.creation.screens
    profiles=tuple(compile_screen(v.inputs,roles=v.roles) for v in new.profiles)
    calls=tuple(ScreenCall(**{f.name:getattr(call,f.name) for f in fields(ScreenCall)}) for call in new.calls)
    screens=ScreenExperiment(profiles,calls)
    return c,replace(x,offense=replace(x.offense,creation=replace(x.offense.creation,screens=screens)))


def scripted_accounting(outcome):
    """Exercise actual kernel made-three/three-FT ledgers without fitting inputs.

    Explicit branch-test draws, not empirical or player-performance evidence.
    The bounded seeded games can have very few pop selections. This check
    forces the event branch while retaining all actual route/catch/shot code.
    """
    import random
    from unittest.mock import patch
    from nba_gm_data import sim
    from nba_gm_data.interior_game import validate_accounting
    if outcome not in ('made_fg','shooting_foul'):raise ValueError('Explicit accounting branch required')
    s,c,x=fixture(pool(),possessions=2);draws=observed_draws();draws[0]=0;draws[15]=0;draws[34]=0;draws[43]=.999
    draws[5]=0 if outcome=='shooting_foul' else .999;draws[6]=.999;draws[7]=0
    draws[8]=draws[9]=draws[10]=0
    d=decision(s,draws=draws);probabilities=project_choices(d['frame'],d['options'])['good_choice_probabilities']
    cumulative=0
    for name,value in probabilities.items():
        if name=='pop':draws[33]=cumulative+value/2;break
        cumulative+=value
    class Scripted(random.Random):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self.index=0;self.draws=list(draws)
            if ':response_b:' in str(args[0]):self.draws[33]=0
        def random(self):
            if self.index>=48:raise AssertionError('Unexpected RNG domain consumption')
            value=self.draws[self.index];self.index+=1;return value
    with patch.object(random,'Random',Scripted):r=sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x)
    validate_accounting(r);return r
