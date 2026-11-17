"""One explicitly named, never-promoted coarse decision experiment.

The scoped harness replaces prediction only. Actual selected-pass resolution
receives the original frame/config and detailed geometry, gates and costs.
"""
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch
from nba_gm_data import action_choice

MODE='coarse_recovery_decision_panel1_v1'
EXACT_CANDIDATE=action_choice.project_candidate
EXACT_CHOICES=action_choice.project_choices


def candidate(frame,name,options,*,order=4):
    if name=='finish' or not getattr(frame['spec'],'receipt_policy',None):return EXACT_CANDIDATE(frame,name,options,order=order)
    numerical=replace(frame['spec'].recovery,integration_panels=1)
    prediction_frame={**frame,'spec':replace(frame['spec'],recovery=numerical)}
    result=EXACT_CANDIDATE(prediction_frame,name,options,order=order)
    return {**result,'policy':MODE,'selected_pass_resolution':'unchanged detailed poor_receipt_recovery_v1','reference_integration_panels':frame['spec'].recovery.integration_panels}


def choices(frame,options,*,order=4):
    return {**EXACT_CHOICES(frame,options,order=order),'decision_projection':MODE}


@contextmanager
def enabled():
    with patch.object(action_choice,'project_candidate',candidate),patch.object(action_choice,'project_choices',choices):yield
