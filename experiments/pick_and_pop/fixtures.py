"""Frozen Turner context and private synthetic causal overlays, never ratings."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.experimental_inputs import InterpretedInputs
from nba_gm_data.screen_navigation import PopScreenCall,PopScreenExperiment,compile_screen
from nba_gm_data.creation_passing import CHOICE_POLICY,HELP_RESPONSE_POLICY
from experiments.expanded_cohort_performance.pool import IDS,load_pool as prior_pool,ROOT
from experiments.expanded_cohort_performance.fixtures import fixture as base_fixture
from experiments.action_choice_consistency.fixtures import prepare
from experiments.interior_defense.fixtures import estimate

BASE=ROOT/'output/pick-and-pop-2026-11-15'
REFERENCE=BASE/'reference'


def pool(*,synthetic=False,changes=None,pop_share=.5):
    p=prior_pool();frozen=json.loads((REFERENCE/'frozen-input-layers.json').read_text())
    assert {pid:v.to_dict() for pid,v in p['views'].items()}==frozen['operational_documents']
    p={**p,'views':dict(p['views'])};ledger=[]
    # New dependencies are unknown in the frozen Turner source. Completion is
    # explicit fixture policy, not evidence about his actual screen/pop talent.
    completions={'turner':{'S26':65,'S27':65,'S28':65}}
    if synthetic:completions['turner'].update({'S01':75,'S08':65,'S09':65,'S14':65})
    for alias,fields in completions.items():
        doc=p['views'][IDS[alias]].to_dict()
        for key,value in fields.items():
            before=deepcopy(doc['inputs'][key]);raw=p['packet']['proposed_source_input_section']['players'][IDS[alias]]['inputs'][key]
            if not synthetic and raw['status']!='unknown':raise ValueError('New role completion must not replace researched evidence')
            if before['value'] is None:doc['inputs'][key]=estimate({'grade':value,'scale':'research_technique_reference_v0_2026_11_13'},method='explicit unknown screen/pop role control, not an athlete estimate')
            else:doc['inputs'][key]['value']['grade']=value
            ledger.append({'player_id':IDS[alias],'design_id':key,'before':before,'after':deepcopy(doc['inputs'][key]),'origin':'synthetic causal reference' if synthetic else 'explicit unknown new-role completion'})
        p['views'][IDS[alias]]=InterpretedInputs(PlayerInputs(doc),p['contract'])
    # T11 has no observed numerical deployment frequency. Keep its source row
    # unchanged; this separate operational mix is the declared opportunity policy.
    changes={'turner':{'T11':{'screen':.2,'roll':(.8-pop_share)*.8,'slip':(.8-pop_share)*.2,'pop':pop_share}},**(changes or {})}
    # Merge nested Turner changes without losing the opportunity policy.
    changes['turner']={'T11':{'screen':.2,'roll':(.8-pop_share)*.8,'slip':(.8-pop_share)*.2,'pop':pop_share},**changes.get('turner',{})}
    for alias,fields in changes.items():
        doc=p['views'][IDS[alias]].to_dict()
        for key,value in fields.items():
            before=deepcopy(doc['inputs'][key]);row=doc['inputs'][key]
            if key.startswith(('S','F')):
                if row['value'] is None:row=estimate({'grade':value,'scale':'research_technique_reference_v0_2026_11_13'},method='explicit synthetic causal control')
                else:row['value']['grade']=value
            elif key in ('T11','T01'):
                if row['value'] is None:
                    row=estimate({'reference_conditions':'explicit screen/pop opportunity control, not observed deployment',
                        'rows':[{'condition':'on_ball_screen' if key=='T11' else 'reference_opportunity','probabilities':{}}]},method='separate experimental opportunity policy')
                row['value']['rows'][0]['probabilities']=value if key=='T11' else {'shoot':value,'drive':1-value,'pass':0,'post':0,'reset':0}
            elif key.startswith('P'):
                for m in row['value']['measurements']:m['value']=value
            else:raise ValueError('Unsupported fixture axis')
            raw=p['packet']['proposed_source_input_section']['players'].get(IDS[alias],p['partner_sources'].get(IDS[alias],{}))['inputs'][key]
            if raw['status']!='unknown' and not synthetic:raise ValueError('Named evidence fixed; use a separately labeled synthetic causal fixture')
            doc['inputs'][key]=row;ledger.append({'player_id':IDS[alias],'design_id':key,'before':before,'after':deepcopy(row),
                'origin':'synthetic causal contrast' if synthetic else 'explicit operational context control'})
        p['views'][IDS[alias]]=InterpretedInputs(PlayerInputs(doc),p['contract'])
    p['control_ledger']=ledger;p['synthetic']=synthetic
    return p


def fixture(p=None,*,action='pop',coverage='show_then_recover',timing='bounded_wait_v1',creator_start=(2,5.5),
            pop_end=(3,7.4),coverage_start=(.8,2.8),possessions=16):
    p=p or pool()
    state,c,x=base_fixture(p,creator='curry',receiver='white',partner='turner',poa='castle',helper='barnes',other='wemb',families=('F03','F04','F06'),possessions=possessions)
    roles=(('turner','screener'),('castle','navigator'),('wemb','coverage'))
    profiles=tuple(compile_screen(p['views'][IDS[a]],roles=(role,),**({'pop_routes':True} if role=='screener' else {})) for a,role in roles)
    call=PopScreenCall(IDS['curry'],IDS['turner'],creator_start,(1.4,4.5),(1.4,4.5),(1.5,4.8),coverage_start,(.6,1),coverage,pop_end=pop_end,action_call=action)
    screens=PopScreenExperiment(profiles,(call,),timing_policy=timing)
    creation=replace(x.offense.creation,screens=screens,choice_policy=CHOICE_POLICY,help_response_policy=HELP_RESPONSE_POLICY)
    x=replace(x,offense=replace(x.offense,creation=creation))
    s=prepare(c,x,None);s['audit_context']={**state['audit_context'],'screen':coverage,'control_ledger':p['control_ledger'],
        'synthetic':p['synthetic'],'new_role':'Turner supplied screener/pop; S26/S27/S28 are unknown controls',
        'missing_mechanisms':['post','general Curry relocation/handoffs','F01 stationary return','full defensive scheme/C37']}
    return s,c,x


def research_pool():
    """Separately attributed final-delivery Turner trial; original run retained.

    Only independently supplied new S26/S28 records fill old unknowns. This
    does not apply a changing packet or alter any inherited supported value.
    """
    path=REFERENCE/'screen-pop-research/SCREEN_POP_INPUTS_2026_11_15.json'
    if hashlib.sha256(path.read_bytes()).hexdigest()!='161b9d9e0761699e9f2358a0a020494b62aca0580639926ae40c42ad86ba7ee2':raise ValueError('Final research packet hash mismatch')
    packet=json.loads(path.read_text());p=pool();doc=p['views'][IDS['turner']].to_dict();updates=[]
    for key in ('S26','S28'):
        original=p['packet']['proposed_source_input_section']['players'][IDS['turner']]['inputs'][key]
        new=packet['proposed_source_input_section']['players'][IDS['turner']]['inputs'][key]
        if original['status']!='unknown' or new['status']=='unknown':raise ValueError('Only independent new unknown-cell evidence may be added')
        updates.append({'design_id':key,'original_source':deepcopy(original),'old_operational_control':deepcopy(doc['inputs'][key]),'new_proposed_source':deepcopy(new),
            'origin':'final independent research trial; historical carry-forward hypothesis, no source correction'})
        doc['inputs'][key]=deepcopy(new)
    p['views'][IDS['turner']]=InterpretedInputs(PlayerInputs(doc),p['contract']);p['research_packet']=packet;p['research_updates']=updates
    p['control_ledger']=[r for r in p['control_ledger'] if r['design_id'] not in ('S26','S28')]
    return p
