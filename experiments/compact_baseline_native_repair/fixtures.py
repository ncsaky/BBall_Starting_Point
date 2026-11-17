"""Current scoped configuration; historical fixtures retain detailed explicitly."""
from dataclasses import replace
from experiments.pass_recovery.fixtures import pool,fixture as historical,IDS,ROOT
from experiments.action_choice_consistency.fixtures import prepare


def fixture(p=None,actor='turner',*,backend='compact_python_v1',bearing='legacy_bearing_v1',provider=None,**kw):
    state,c,x=historical(p or pool(),actor,**kw);old=x.offense.creation
    if not getattr(old,'receipt_policy',None):return state,c,x
    creation=replace(old,projection_backend=backend,bearing_policy=bearing,geometry_provider=provider)
    x=replace(x,offense=replace(x.offense,creation=creation));s=prepare(c,x,None);s['audit_context']={**state['audit_context'],'projection_backend':backend,'bearing_policy':bearing,'geometry_provider':getattr(provider,'revision',None)}
    return s,c,x


def converted(frame,backend='compact_python_v1',bearing='legacy_bearing_v1',provider=None):
    """Same supplied state, scoped numerical/model config; no input rewrites."""
    return {**frame,'spec':replace(frame['spec'],projection_backend=backend,bearing_policy=bearing,geometry_provider=provider)}
