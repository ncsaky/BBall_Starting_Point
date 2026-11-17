"""Fixed accepted milestone11 final inputs; policy-only comparisons."""
from copy import deepcopy
from dataclasses import fields,replace
import json

from nba_gm_data.creation_passing import CreationExperiment
from nba_gm_data.pass_recovery import RecoveryCreationExperiment,RecoveryCoefficients
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.experimental_inputs import InterpretedInputs,CAPACITY_SCALE,RESEARCH_TECHNIQUE
from experiments.mixed_pop_validation.fixtures import final_research_pool,fixture as mixed_fixture,IDS,ROOT
from experiments.action_choice_consistency.fixtures import prepare

BASE=ROOT/'output/pass-recovery-2026-11-16';REFERENCE=BASE/'reference'


def pool():
    p=final_research_pool();frozen=json.loads((REFERENCE/'separate-final-research-inputs.json').read_text())['layers']['operational_documents']
    assert {pid:v.to_dict() for pid,v in p['views'].items()}==frozen
    return p


def synthetic(p,changes):
    p={**p,'views':dict(p['views']),'synthetic_changes':[]}
    for actor,values in changes.items():
        pid=IDS[actor];doc=p['views'][pid].to_dict()
        for key,value in values.items():
            before=deepcopy(doc['inputs'][key]);row=doc['inputs'][key]
            if value is None:
                row={'status':'unknown','value':None,'reason':'explicit synthetic dependency removal, not a source change','evidence':[],'uncertainty':{'confidence':'unknown','notes':'explicit synthetic dependency removal, not a source change'}}
                doc['inputs'][key]=row
            elif key.startswith(('S','F')):
                if row['value'] is None:
                    row={'status':'estimated','value':{'grade':value,'scale':RESEARCH_TECHNIQUE},'evidence':[{'source':'pass_recovery_synthetic_control','method':'explicit synthetic causal contrast, not athlete evidence'}],
                        'uncertainty':{'confidence':'low','notes':'synthetic control'}}
                    doc['inputs'][key]=row
                else:row['value']['grade']=value
            elif key in ('P08','P09'):row['value']={'measurements':[],'display_grade':{'scale':CAPACITY_SCALE,'grade':value}}
            elif key.startswith('P'):
                for m in row['value']['measurements']:m['value']=value
            elif key=='T01':row['value']['rows'][0]['probabilities']={'shoot':value,'drive':1-value,'pass':0,'post':0,'reset':0}
            else:raise ValueError('Explicit supported synthetic axis required')
            p['synthetic_changes'].append({'actor':actor,'design_id':key,'before':before,'after':deepcopy(row),'origin':'private synthetic causal contrast, not a named source estimate'})
        p['views'][pid]=InterpretedInputs(PlayerInputs(doc),p['contract'])
    return p


def fixture(p=None,actor='turner',*,enabled=True,coefficients=None,**kwargs):
    p=p or pool();old,c,x=mixed_fixture(p,actor,**kwargs)
    if enabled:
        creation=x.offense.creation
        # Historical milestones explicitly retain their detailed reference.
        # New RecoveryCreationExperiment callers default to scoped compact.
        new=RecoveryCreationExperiment(**{f.name:getattr(creation,f.name) for f in fields(CreationExperiment)},recovery=coefficients or RecoveryCoefficients(),projection_backend='detailed_python_v1')
        x=replace(x,offense=replace(x.offense,creation=new));s=prepare(c,x,None)
    else:s=old
    s['audit_context']={**old['audit_context'],'receipt_policy':'poor_receipt_recovery_v1' if enabled else 'accepted_hard_window',
        'synthetic_changes':p.get('synthetic_changes',[]),'source_packet_sha256':p['final_packet_sha256']}
    return s,c,x


def scripted_reset_kernel():
    """Controlled actual-kernel transfer/clock test, never natural-rate evidence."""
    import math,random
    from unittest.mock import patch
    from nba_gm_data import sim
    from nba_gm_data.creation_passing import prepare_drive_decision
    from nba_gm_data.action_choice import project_choices
    from experiments.action_choice_consistency.fixtures import observed_draws
    s,c,x=fixture(action='pop',coverage='stay',possessions=2);draws=observed_draws();draws[0]=0;draws[15]=0;draws[44]=.25
    draws[5]=.999;draws[6]=.999;draws[7]=0;draws[43]=1
    d=prepare_drive_decision(s,IDS['curry'],'response_a','response_b',draws,24);weights=project_choices(d['frame'],d['options'])['good_choice_probabilities'];total=0
    for name,value in weights.items():
        if name=='pop':draws[33]=total+value/2;break
        total+=value
    draws[34]=1-math.exp(-.9/d['options']['pop']['delivery']['error_scale_m'])
    class Scripted(random.Random):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self.index=0;self.draws=list(draws);domain=str(args[0])
            if ':response_b:' in domain:self.draws[33]=0
            elif ':response_a:' in domain and int(domain.rsplit(':',1)[-1])>0:self.draws[33]=.999999
        def random(self):
            value=self.draws[self.index];self.index+=1;return value
    with patch.object(random,'Random',Scripted):return sim.sim_game_with_context(c,'expanded_fixture',seed=17,interior_experiment=x)
