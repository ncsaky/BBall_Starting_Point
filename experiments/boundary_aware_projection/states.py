"""Frozen design: prior48 regressions plus16 prospectively declared scenes."""
from nba_gm_data.creation_passing import prepare_drive_decision,resolve_candidate
from nba_gm_data.pass_recovery import complete_receipt,apply_continuation
from experiments.pass_recovery.fixtures import fixture,pool,synthetic,IDS
from experiments.action_choice_consistency.fixtures import observed_draws
from experiments.recovery_projection_cost.stage_b import states as prior_states


def states(group):
    for metadata,frame,options in prior_states():
        if metadata['group']==group:yield {**metadata,'origin':'prior48'},frame,options
    p=pool();actors=('turner','jokic') if group=='development' else ('towns','holmgren')
    for actor in actors:
        for context in ('changed_start_clock6','recovery_reset_creator','slow_preparation','fast_preparation'):
            q=synthetic(p,{actor:{'S26':10 if context=='slow_preparation' else 95}}) if context in ('slow_preparation','fast_preparation') else p
            kw={'creator_start':(4.5,8),'clock':6,'coverage':'stay'} if context=='changed_start_clock6' else {'coverage':'stay','action':'pop'}
            s,c,x=fixture(q,actor,**kw);draws=observed_draws();d=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',draws,x.offense.creation.possession_budget_s)
            if context=='recovery_reset_creator':
                draws[44]=.25;a=resolve_candidate(d['frame'],'pop',d['options'],draws,{},delivery_error_override=.9);a=complete_receipt(a,0,24)
                assert a['kind']=='reset' and a['record']['actual_receipt_secured'] is True
                new=apply_continuation(s,a['recovery_continuation']);d=prepare_drive_decision(new,a['continuation_creator_id'],'response_a','response_b',draws,24-a['elapsed_s'],screen_allowed=False)
            assert 'frame' in d, (actor,context,d.get('outcome'))
            yield {'actor':actor,'group':group,'family':'all_offered','context':context,'origin':'new16','synthetic_changes':q.get('synthetic_changes',[])},d['frame'],d['options']
