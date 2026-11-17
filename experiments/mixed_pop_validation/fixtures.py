"""Four pinned evidence snapshots; complete only actual consumer unknowns."""
from copy import deepcopy
from dataclasses import replace,asdict
import hashlib
import json

from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.experimental_inputs import InterpretedInputs,RESEARCH_TECHNIQUE,FT_PROXY,SCENARIO_GEOMETRY
from nba_gm_data.screen_navigation import compile_screen,PopScreenCall,PopScreenExperiment
from experiments.expanded_cohort_performance.pool import load_pool as old_pool,IDS as OLD_IDS
from experiments.expanded_cohort_performance.fixtures import fixture as base_fixture
from experiments.action_choice_consistency.fixtures import prepare
from experiments.player_input_pilot.pilot import BASE as BASE_REQUIRED,assumption
from .diagnosis import ROOT,BASE,REFERENCE

IDS={**OLD_IDS,'towns':'player_nyk-karl-anthony-towns','holmgren':'player_okc-chet-holmgren','nonspacing':'synthetic_nonspacing_reference'}
ACTORS=('turner','towns','holmgren','jokic','nonspacing')
REQUIRED=set(BASE_REQUIRED)|{'S26','S27','S28','P01','P04','T11'}
MIX={'screen':.20,'roll':.35,'slip':.10,'pop':.35}
PACKET_SHA='161b9d9e0761699e9f2358a0a020494b62aca0580639926ae40c42ad86ba7ee2'


def build_pool():
    raw=(REFERENCE/'SCREEN_POP_INPUTS_2026_11_15.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PACKET_SHA:raise ValueError('Pinned source packet changed')
    packet=json.loads(raw);validate_input_section(packet['proposed_source_input_section'])
    p=old_pool();p={**p,'views':dict(p['views']),'roles':deepcopy(p['roles'])}
    frozen=json.loads((REFERENCE/'named-inputs-and-completions.json').read_text())
    donor=frozen['original_operational_documents'][IDS['turner']]['inputs']
    sources={};ledger=[];docs={}
    for actor in ACTORS[:-1]:
        pid=IDS[actor];source=deepcopy(packet['proposed_source_input_section']['players'][pid]);sources[pid]=deepcopy(source);doc=deepcopy(source)
        for key in sorted(REQUIRED):
            before=deepcopy(doc['inputs'][key])
            if before['status']!='unknown':continue
            notes='Prespecified common mixed-pop control; not a named-player estimate or new source evidence'
            if key=='T11':row=assumption({'reference_conditions':'common mixed called opportunity, not observed player preference','rows':[{'condition':'screen_followup_trial','probabilities':dict(MIX)}]},notes)
            elif key=='S07':row=assumption({'grade':80,'scale':FT_PROXY},notes+'; .80 FT probability control, not a generic accuracy curve')
            elif key.startswith(('S','F')):row=assumption({'grade':65,'scale':RESEARCH_TECHNIQUE},notes)
            elif key=='P03':
                height=doc['inputs']['P01']['value']['measurements'][0]['value'];span=doc['inputs']['P02']['value']['measurements'][0]['value']
                row=assumption({'measurements':[{'metric':'scenario_standing_reach','value':height+70+.5*(span-height),'unit':'cm','protocol':SCENARIO_GEOMETRY}]},notes+'; hypothetical H1 reach, not a measurement')
            else:
                row=deepcopy(donor[key]);row['evidence']=[{'source':'mixed_pop_common_controls_2026_11_16','method':notes}]
                row['uncertainty']={'confidence':'low','notes':notes}
            doc['inputs'][key]=row;ledger.append({'actor':actor,'player_id':pid,'design_id':key,'source_record':before,'operational_record':deepcopy(row),'origin':'explicit operational control; source unknown retained'})
        docs[pid]=doc;p['views'][pid]=InterpretedInputs(PlayerInputs(doc),p['contract']);p['roles'][pid]={'base':True,'interior':False,'screens':['screener']}
    # Synthetic reference is fully labeled; no real-player evidence is claimed.
    doc=deepcopy(docs[IDS['turner']]);doc['player_id']=IDS['nonspacing']
    doc['inputs']['S01']['value']['grade']=20
    doc['inputs']['T01']['value']['rows'][0]['probabilities']={'shoot':.1,'drive':.3,'pass':.4,'post':0,'reset':.2}
    for row in doc['inputs'].values():
        if row['status']=='unknown':continue
        row['evidence']=[{'source':'synthetic_nonspacing_reference_2026_11_16','method':'synthetic reference values only; no athlete evidence'}]
        row['uncertainty']={'confidence':'low','notes':'entirely synthetic comparator, not a proposed named-player profile'}
    p['views'][IDS['nonspacing']]=InterpretedInputs(PlayerInputs(doc),p['contract']);p['roles'][IDS['nonspacing']]={'base':True,'interior':False,'screens':['screener']}
    inherited=json.loads((REFERENCE/'EXPANDED_ACTION_COHORT_2026_11_14.json').read_text())
    ranges={(r['player_id'],r['design_id']):r['range'] for r in inherited['new_estimates']+packet['new_estimates'] if isinstance(r.get('range'),list)}
    p.update(source_documents=sources,completion_ledger=ledger,source_packet=packet,source_ranges=ranges,scenario='fixed_mixed_pop_source_and_explicit_controls',overrides=[])
    for pid,source in sources.items():
        for key,row in source['inputs'].items():
            if row['status']!='unknown':assert p['views'][pid].to_dict()['inputs'][key]==row
    return p


def overlay(p,name,changes,*,kind='control'):
    if kind not in ('control','source_range'):raise ValueError('Explicit control or pinned source range required')
    p={**p,'views':dict(p['views']),'overrides':deepcopy(p['overrides']),'scenario':name}
    for actor,fields in changes.items():
        pid=IDS[actor];doc=p['views'][pid].to_dict();source=p['source_documents'].get(pid)
        if source is None:
            source=p['packet']['proposed_source_input_section']['players'].get(pid,p['partner_sources'].get(pid))
        for key,value in fields.items():
            if kind=='control' and source['inputs'][key]['status']!='unknown':raise ValueError('Control must not replace evidence-backed input')
            if kind=='source_range' and value not in p['source_ranges'].get((pid,key),[]):raise ValueError('Use an exact pinned evidence range endpoint')
            row=deepcopy(doc['inputs'][key]);before=deepcopy(row)
            if key.startswith(('S','F')):row['value']['grade']=value
            elif key in ('P05','P06','P07','P10'):
                for m in row['value']['measurements']:m['value']=value
            else:raise ValueError('Unsupported declared sensitivity axis')
            doc['inputs'][key]=row;p['overrides'].append({'actor':actor,'design_id':key,'before':before,'after':deepcopy(row),'origin':kind,'scenario':name})
        p['views'][pid]=InterpretedInputs(PlayerInputs(doc),p['contract'])
    return p


def fixture(p,actor='turner',*,coverage='show_then_recover',creator_start=(2,5.5),clock=24,action='preference',possessions=16):
    pid=IDS[actor]
    base,c,x=base_fixture(p,creator='curry',receiver='white',partner=pid,poa='castle',helper='barnes',other='wemb',families=('F03','F04','F06'),possessions=possessions,creator_start=creator_start)
    profiles=tuple(compile_screen(p['views'][actor_id],roles=(role,),**({'pop_routes':True} if role=='screener' else {})) for actor_id,role in ((pid,'screener'),(IDS['castle'],'navigator'),(IDS['wemb'],'coverage')))
    call=PopScreenCall(IDS['curry'],pid,creator_start,(1.4,4.5),(1.4,4.5),(1.5,4.8),(.8,2.8),(.6,1),coverage,pop_end=(3,7.4),action_call=action)
    creation=replace(x.offense.creation,screens=PopScreenExperiment(profiles,(call,)),possession_budget_s=clock)
    x=replace(x,offense=replace(x.offense,creation=creation));s=prepare(c,x,None)
    s['audit_context']={**base['audit_context'],'actor':actor,'actor_id':pid,'input_scenario':p['scenario'],'overrides':p['overrides'],
        'context':'supplied Curry initial creator; mixed screen preference with actual imperfect choice; not a player workload forecast'}
    return s,c,x


def contexts():
    return [('early_show',dict(creator_start=(1.4,4.6))),('reference_show',{}),('reference_stay',dict(coverage='stay')),
        ('late_stay',dict(coverage='stay',creator_start=(4.5,8))),('late_show_clock6',dict(creator_start=(4.5,8),clock=6)),
        ('reference_show_clock3',dict(clock=3))]


def final_research_pool(p=None):
    """Final delivered unknown-cell additions in a separately attributed trial."""
    p=p or build_pool();path=REFERENCE/'final-research/MIXED_POP_INPUT_UPDATES_2026_11_16.json';raw=path.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if sha!='dbabcc349525b440d703e96f24af9ae562633ff904574bc88efd7abb8b060eba':raise ValueError('Final independent research hash mismatch')
    packet=json.loads(raw);validate_input_section(packet['proposed_source_input_section']);updates=[]
    q={**p,'views':dict(p['views']),'source_documents':deepcopy(packet['proposed_source_input_section']['players']),
        'source_ranges':dict(p['source_ranges']),'source_packet':packet,'scenario':'separate_final_research_update','final_packet_sha256':sha}
    for actor in ACTORS[:-1]:
        pid=IDS[actor];before_source=p['source_documents'][pid]
        if packet['base_source_input_section']['players'][pid]!=before_source:raise ValueError('Final research base differs from frozen source')
        doc=p['views'][pid].to_dict()
        for key,new in q['source_documents'][pid]['inputs'].items():
            old=before_source['inputs'][key]
            if old['status']!='unknown':
                if new!=old:raise ValueError('Final research must preserve supported records')
            elif new['status']!='unknown':
                updates.append({'actor':actor,'player_id':pid,'design_id':key,'old_source':deepcopy(old),'old_operational_control':deepcopy(doc['inputs'][key]),'new_source':deepcopy(new),'origin':'final independent unknown-cell estimate, not an engine correction'})
                doc['inputs'][key]=deepcopy(new)
        q['views'][pid]=InterpretedInputs(PlayerInputs(doc),p['contract'])
    changed={(r['player_id'],r['design_id']) for r in updates}
    if len(changed)!=9:raise ValueError('Unexpected final research addition count')
    q['completion_ledger']=[deepcopy(r) for r in p['completion_ledger'] if (r['player_id'],r['design_id']) not in changed]
    for r in packet['new_estimates']:q['source_ranges'][(r['player_id'],r['design_id'])]=r['range']
    q['research_updates']=updates
    return q
