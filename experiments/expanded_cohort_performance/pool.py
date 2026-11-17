"""Pinned evidence-first cohort; operational controls never become observations."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from nba_gm_data.experimental_inputs import InterpretedInputs,InputInterpretation,SCENARIO_GEOMETRY,CAPACITY_SCALE
from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.offense_response import compile_offense
from nba_gm_data.creation_passing import compile_interaction
from nba_gm_data.interior_defense import compile_profile
from nba_gm_data.screen_navigation import compile_screen
from experiments.action_choice_consistency.fixtures import pinned_pilot

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'output/expanded-cohort-action-performance-2026-11-15'
REFERENCE=BASE/'reference'
PACKET_SHA='e61a71e7b1225f83c0e357386b98a08ce2a449c310e99f5846b80b00a32755d2'
IDS={'curry':'player_gsw-stephen-curry','brunson':'player_nyk-jalen-brunson','wemb':'player_sas-victor-wembanyama',
    'jokic':'player_den-nikola-jokic','turner':'player_mil-myles-turner','barnes':'player_tor-scottie-barnes',
    'white':'player_bos-derrick-white','castle':'player_sas-stephon-castle'}


def load_pool():
    raw=(REFERENCE/'EXPANDED_ACTION_COHORT_2026_11_14.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PACKET_SHA:raise ValueError('Frozen cohort evidence hash mismatch')
    packet=json.loads(raw)
    for key in ('merged_source_input_section','proposed_source_input_section','operational_input_section'):validate_input_section(packet[key])
    contract=InputInterpretation(**packet['compiler_snapshot']['interpretation_contract'])
    documents=packet['operational_input_section']['players'];views={pid:InterpretedInputs(PlayerInputs(doc),contract) for pid,doc in documents.items()}
    roles={r['player_id']:r['role_plan'] for r in packet['readiness']}
    prior=pinned_pilot()
    for alias in ('white','castle'):
        view=prior['views'][IDS[alias]]
        if view.contract!=contract:raise ValueError('Partner interpretation differs from cohort')
        views[view.player_id]=view;roles[view.player_id]={'base':True,'interior':False,'screens':['navigator']}
    for pid,source in packet['proposed_source_input_section']['players'].items():
        for key,row in source['inputs'].items():
            if row['status']!='unknown' and documents[pid]['inputs'][key]!=row:raise ValueError('Operational layer overwrote evidence')
    return {'version':'expanded_action_adapter_2026_11_15_v1','packet':packet,'packet_sha256':PACKET_SHA,
        'views':views,'contract':contract,'roles':roles,'overrides':[],'scenario':'pinned_central_inputs',
        'partner_sources':{IDS[a]:deepcopy(prior['source_documents'][IDS[a]]) for a in ('white','castle')}}


def compile_audit(pool):
    """Observe actual getter dependencies, not a stale hand-maintained union."""
    original=InterpretedInputs.to_dict;seen={};active=[None]
    class Rows(dict):
        def __getitem__(self,key):
            if active[0] is not None:seen[active[0]].add(key)
            return super().__getitem__(key)
        def get(self,key,default=None):
            if active[0] is not None:seen[active[0]].add(key)
            return super().get(key,default)
    def traced(view):
        doc=original(view);doc['inputs']=Rows(doc['inputs']);return doc
    rows=[]
    for readiness in pool['packet']['readiness']:
        pid=readiness['player_id'];view=pool['views'][pid];roles=readiness['role_plan'];profiles={};dependencies={}
        calls=[('offense',lambda:compile_offense(view)),('interaction',lambda:compile_interaction(view))]
        if roles['interior']:calls.append(('interior',lambda:compile_profile(view)))
        if roles['screens']:calls.append(('screen',lambda:compile_screen(view,roles=tuple(roles['screens']))))
        for name,fn in calls:
            active[0]=(pid,name);seen[active[0]]=set()
            with patch.object(InterpretedInputs,'to_dict',traced):profile=fn()
            keys=seen[active[0]]-{'S42','S43'};dependencies[name]=sorted(keys)
            profiles[name]={'compiled':True,'revision':profile.revision,'same_authoritative_view':profile.inputs is view}
        active[0]=None;actual=set().union(*(set(v) for v in dependencies.values()));declared=set(readiness['required_ids'])
        rows.append({'player_id':pid,'name':readiness['name'],'roles':roles,'profiles':profiles,'dependencies':dependencies,
            'actual_required_ids':sorted(actual),'declared_required_ids':sorted(declared),
            'new_required_ids':sorted(actual-declared),'declared_unused_ids':sorted(declared-actual),
            'supported_required':sum(pool['packet']['proposed_source_input_section']['players'][pid]['inputs'][k]['status']!='unknown' for k in actual),
            'control_required':sum(pool['packet']['proposed_source_input_section']['players'][pid]['inputs'][k]['status']=='unknown' for k in actual)})
    return rows


def scenario(pool,name,changes,*,kind='control'):
    """Prespecified range/control overlay, separate from frozen source records."""
    views=dict(pool['views']);overrides=deepcopy(pool['overrides']);new={}
    estimates={(r['player_id'],r['design_id']):r for r in pool['packet']['new_estimates']}
    for alias,fields in changes.items():
        pid=IDS.get(alias,alias);doc=views[pid].to_dict()
        for key,value in fields.items():
            before=deepcopy(doc['inputs'][key]);row=deepcopy(before)
            proposed=pool['packet']['proposed_source_input_section']['players'].get(pid,{}).get('inputs',{}).get(key)
            if proposed is None:proposed=pool['partner_sources'].get(pid,{}).get('inputs',{}).get(key)
            if kind=='source_range':
                estimate=estimates.get((pid,key))
                if estimate is None or not isinstance(estimate.get('range'),list) or value not in estimate['range']:raise ValueError('Use an explicit pinned evidence-range endpoint')
            elif proposed is None or proposed['status']!='unknown':raise ValueError('Control overlay cannot overwrite researched evidence')
            if key.startswith(('S','F')):row['value']['grade']=value
            elif key in ('T07','T15'):row['value']['probability']=value
            elif key in ('P08','P09'):
                row['value']={'measurements':[],'display_grade':{'grade':value*100,'scale':CAPACITY_SCALE}}
            elif key=='P03':
                row['value']={'measurements':[{'metric':'scenario_standing_reach','value':value,'unit':'cm','protocol':SCENARIO_GEOMETRY}]}
            elif key.startswith('P'):
                for measurement in row['value']['measurements']:measurement['value']=value
            else:raise ValueError('Unsupported sensitivity axis')
            doc['inputs'][key]=row;overrides.append({'scenario':name,'player_id':pid,'design_id':key,'before':before,'after':deepcopy(row),
                'origin':'pinned evidence range, not a new estimate' if kind=='source_range' else 'explicit uncertain control alternative',
                'source_packet_unchanged':True})
        new[pid]=InterpretedInputs(PlayerInputs(doc),pool['contract'])
    views.update(new)
    return {**pool,'views':views,'overrides':overrides,'scenario':name}


def export(pool):
    return {'version':pool['version'],'scenario':pool['scenario'],'packet_sha256':pool['packet_sha256'],
        'interpretation':asdict(pool['contract']),'contract_revision':pool['contract'].revision,
        'merged_source_input_section':deepcopy(pool['packet']['merged_source_input_section']),
        'proposed_source_input_section':deepcopy(pool['packet']['proposed_source_input_section']),
        'partner_source_documents':deepcopy(pool['partner_sources']),
        'operational_documents':{pid:v.to_dict() for pid,v in pool['views'].items()},
        'operational_completions':deepcopy(pool['packet']['operational_completions']),
        'overrides':deepcopy(pool['overrides']),'partner_policy':'White/Castle pinned accepted milestone7; separate authoritative views, no new evidence'}
