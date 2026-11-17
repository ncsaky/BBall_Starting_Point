"""Separately owned, versioned operational completion for conditional probes.

Supported source rows are copied exactly. Unknowns are completed only for the
explicit consumer/role envelope, with a per-field ledger; packets are read-only.
"""
from copy import deepcopy
from dataclasses import asdict,replace
import hashlib
import json
from pathlib import Path

from nba_gm_data.player_model import PlayerInputs,validate_input_section
from nba_gm_data.player_model_registry import REGISTRY_VERSION
from nba_gm_data.experimental_inputs import InterpretedInputs,InputInterpretation,common_reader,RESEARCH_TECHNIQUE,CAPACITY_SCALE,SCENARIO_GEOMETRY
from nba_gm_data.offense_response import compile_offense,CombinedOffense,Deployment
from nba_gm_data.creation_passing import compile_interaction,CreationExperiment,DriveSetup
from nba_gm_data.screen_navigation import compile_screen,ScreenExperiment,ScreenCall
from nba_gm_data.interior_defense import InteriorExperiment,compile_profile

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=ROOT/'docs/ratings-evidence-2026-10-29'
VERSION='player_input_pilot_completion_2026_11_14_v1'
READINESS='PILOT_PROFILE_READINESS_2026_11_13.json'
SCREEN='SCREEN_NAVIGATION_INPUTS_2026_11_13.json'
CREATION='CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.json'
IDS={'luka':'player_lal-luka-doncic','harper':'player_sas-dylan-harper','white':'player_bos-derrick-white','castle':'player_sas-stephon-castle','zubac':'player_ind-ivica-zubac','gobert':'player_min-rudy-gobert',
     'caruso':'player_okc-alex-caruso','davion':'player_mia-davion-mitchell','ajay':'player_okc-ajay-mitchell'}
ROLES={'white':('navigator',),'castle':('navigator',),'zubac':('screener','coverage'),'gobert':('screener','coverage'),
       'caruso':('screener',),'davion':('navigator',),'ajay':('navigator',)}
SCREEN_REQUIREMENTS={'screener':{'S27','S28','P01','P04','P05','P06','P08','P09','T11'},
 'navigator':{'S35','S41','S44','P01','P04','P05','P06','P07','P08','P09'},'coverage':{'S41','S44','P05','P06','P07'}}
BASE={f'S{i:02d}' for i in range(1,18)}|{'S19','S20','S33','S34','S38','S39','S40','S41','S44','P03','P05','P06','P07','P08','P09','P10','T01','T02','T03','T07','T15'}|{f'{f}.{part}' for f in ('F03','F04','F06') for part in ('recognition','execution')}
INTERIOR={'S36','S37','S45','P02','P03','P05','P08','P09','P10','T16'}


def packet(name):
    raw=(EVIDENCE/name).read_bytes();return json.loads(raw),hashlib.sha256(raw).hexdigest()


def assumption(value,notes):
    return {'status':'estimated','value':value,'evidence':[{'source':VERSION,'method':'explicit action-pilot assumption/control, not athlete measurement','shared_evidence_id':'pilot_common_controls_20261114','notes':notes}],
        'uncertainty':{'confidence':'low','notes':notes+' Source unknown remains preserved in source section.'}}


def required_inputs(alias):
    required=set(BASE) if alias in ('luka','harper','white','castle','zubac','gobert') else set()
    if alias in ('zubac','gobert'):required|=INTERIOR
    for role in ROLES.get(alias,()):required|=SCREEN_REQUIREMENTS[role]
    return required


def build_pilot(*,contract=None):
    readiness,rhash=packet(READINESS);screen,shash=packet(SCREEN);creation,chash=packet(CREATION)
    contract=contract or InputInterpretation(screen_action_policy='condition_on_supported')
    sources=deepcopy(readiness['source_player_input_section']['players'])
    for alias in ('caruso','davion','ajay'):sources[IDS[alias]]=deepcopy(screen['player_input_section']['players'][IDS[alias]])
    operational=readiness['operational_input_section']['players'];docs={};ledger=[]
    old_ledger={(r['player_id'],r['design_id']):r for r in readiness['completion_ledger']}
    donor=operational[IDS['white']]['inputs']
    for alias,pid in IDS.items():
        doc=deepcopy(sources[pid]);required=required_inputs(alias)
        for key in sorted(required):
            source=doc['inputs'][key];origin='scouting_estimate' if key.startswith(('S','F')) and key!='S07' else 'sourced'
            completion=None
            if source['status']=='unknown':
                candidate=operational.get(pid,{}).get('inputs',{}).get(key)
                if candidate and candidate['status']!='unknown':
                    doc['inputs'][key]=deepcopy(candidate);completion=old_ledger.get((pid,key))
                    origin='scenario_policy' if key.startswith('T') else 'uncertain_prior'
                elif key.startswith(('S','F')):
                    doc['inputs'][key]=assumption({'grade':65,'scale':RESEARCH_TECHNIQUE},'Common 65 unknown-skill control; vary 40–85. Not equal real-player talent.');origin='uncertain_prior'
                elif key in ('P05','P06','P07','P08','P09'):
                    doc['inputs'][key]=deepcopy(donor[key]);origin='uncertain_prior';completion={'category':'common physical control copied from disclosed readiness control; not player measurement'}
                elif key=='T11':
                    doc['inputs'][key]=assumption({'reference_conditions':'matched called on-ball branch policy, not intrinsic preference','rows':[{'condition':'screen_followup_trial','probabilities':{'screen':.35,'roll':.40,'pop':.10,'slip':.15}}]},'Scenario policy retains pop .10; interpreter explicitly conditions on supported actions.');origin='scenario_policy'
                else:raise ValueError(f'{pid}/{key}: no justified pilot completion')
            if doc['inputs'][key]['status']=='unknown':raise AssertionError((pid,key))
            ledger.append({'player_id':pid,'alias':alias,'design_id':key,'origin':origin,'source_status':source['status'],
                'source_record':deepcopy(source),'operational_record':deepcopy(doc['inputs'][key]),'inherited_completion':completion,
                'source_packet':READINESS if alias not in ('caruso','davion','ajay') else SCREEN,'consumer_roles':ROLES.get(alias,())})
        docs[pid]=doc
    views={pid:InterpretedInputs(PlayerInputs(doc),contract) for pid,doc in docs.items()}
    # Every source row which was already supported remains byte-for-byte equal.
    for pid,source in sources.items():
        for key,row in source['inputs'].items():
            if row['status']!='unknown':assert docs[pid]['inputs'][key]==row,(pid,key)
    for row in ledger:
        view=views[row['player_id']];reader=common_reader(view);key=row['design_id']
        if key.startswith(('S','F')):
            reader.free_throw() if key=='S07' else reader.grade(key)
        elif key in ('P08','P09'):reader.capacity(key)
        elif key.startswith('P'):reader.measurement(key)
        elif key in ('T01','T02','T03','T11','T16'):reader.distribution(key)
        else:reader.value(key)
        row['interpretation']=reader.audit.get(key,{'rule':'explicit raw propensity, unchanged'})
        row['interpretation_origin']='measurement_alias/conversion' if key.startswith('P') else 'response_mapping' if key.startswith(('S','F')) else 'scenario_policy'
    return {'version':VERSION,'contract':contract,'views':views,'documents':docs,'source_documents':sources,'ledger':ledger,
        'evidence_hashes':{READINESS:rhash,SCREEN:shash,CREATION:chash},'ranges':creation['scouting_ranges']+screen['scouting_ranges']}


def variant(pilot,changes,*,name,contract=None):
    """Independent scenario snapshot; each override records baseline and origin."""
    docs={pid:view.to_dict() for pid,view in pilot['views'].items()};overrides=deepcopy(pilot.get('overrides',[]))
    for alias,fields in changes.items():
        pid=IDS.get(alias,alias)
        for key,value in fields.items():
            before=deepcopy(docs[pid]['inputs'][key]);row=deepcopy(before)
            if key.startswith(('S','F')):
                if row['status']=='unknown':row=assumption({'grade':value,'scale':RESEARCH_TECHNIQUE},'Explicit sensitivity prior, not a source estimate.')
                else:row['value']['grade']=value
            elif key in ('T07','T15'):row['value']['probability']=value
            elif key=='T11':row['value']['rows'][0]['probabilities']=value
            elif key in ('P08','P09'):
                for measurement in row['value']['measurements']:measurement['value']=value
            elif key.startswith('P'):
                if key in ('P01','P02','P03','P04'):
                    metric={'P01':'scenario_height','P02':'scenario_wingspan','P03':'scenario_standing_reach','P04':'scenario_body_mass'}[key]
                    row=assumption({'measurements':[{'metric':metric,'value':value,'unit':'kg' if key=='P04' else 'cm','protocol':SCENARIO_GEOMETRY}]},'Explicit counterfactual geometry; source report/H1 formula is not rewritten as this alternative.')
                else:
                    for measurement in row['value']['measurements']:measurement['value']=value
            else:raise ValueError('Unsupported explicit variant axis')
            docs[pid]['inputs'][key]=row
            overrides.append({'scenario':name,'player_id':pid,'design_id':key,'baseline_record':before,'scenario_record':deepcopy(row),
                'origin':'scenario_policy' if key.startswith('T') or pilot['source_documents'][pid]['inputs'][key]['status']!='unknown' else 'uncertain_prior_alternative',
                'claim':'counterfactual sensitivity, source packet unchanged'})
    chosen=contract or pilot['contract']
    return {**pilot,'documents':docs,'views':{pid:InterpretedInputs(PlayerInputs(doc),chosen) for pid,doc in docs.items()},'contract':chosen,'scenario':name,'overrides':overrides}


def capacity_variant(pilot,strength,balance,*,name):
    """Dimensionless response controls, without inventing athlete force tests."""
    docs={pid:view.to_dict() for pid,view in pilot['views'].items()};overrides=deepcopy(pilot.get('overrides',[]))
    for pid,doc in docs.items():
        for key,number in (('P08',strength),('P09',balance)):
            if doc['inputs'][key]['status']=='unknown':continue
            before=deepcopy(doc['inputs'][key]);after=assumption({'measurements':[],'display_grade':{'grade':number*100,'scale':CAPACITY_SCALE}},'Common dimensionless capacity-response sensitivity; no inferred measured force/time.')
            doc['inputs'][key]=after;overrides.append({'scenario':name,'player_id':pid,'design_id':key,'baseline_record':before,'scenario_record':deepcopy(after),'origin':'uncertain_prior_alternative'})
    return {**pilot,'documents':docs,'views':{pid:InterpretedInputs(PlayerInputs(doc),pilot['contract']) for pid,doc in docs.items()},'scenario':name,'overrides':overrides}


def review_alternative(pilot,*,historical_reach=None):
    """Explicitly opt into the separately delivered proposed-estimate layer."""
    review,digest=packet('PILOT_ASSUMPTION_REVIEW_2026_11_14.json');docs={pid:view.to_dict() for pid,view in pilot['views'].items()};overrides=deepcopy(pilot.get('overrides',[]))
    for update in review['proposed_updates']:
        pid,key=update['player_id'],update['design_id'];before=deepcopy(docs[pid]['inputs'][key]);after=deepcopy(update['record'])
        if key=='P03' and historical_reach is not None:
            if historical_reach not in (292.1,297.18):raise ValueError('Choose a dated alternative, not an invented historical average')
            after['value']['measurements'][0]['value']=historical_reach
            if historical_reach==297.18:after['value']['measurements'][0]['protocol']='2021 reported historical reach alternative; not measured 2026 current reach'
        docs[pid]['inputs'][key]=after
        overrides.append({'scenario':'separate_proposed_evidence_layer','player_id':pid,'design_id':key,'baseline_record':before,'scenario_record':deepcopy(after),
            'origin':'uncertain_prior' if key in ('S27','P03') else 'scouting_estimate','evidence_update':True,'review_sha256':digest,'range':update['range'],'claim':'proposed, not verified current talent'})
    return {**pilot,'documents':docs,'views':{pid:InterpretedInputs(PlayerInputs(doc),pilot['contract']) for pid,doc in docs.items()},'scenario':'proposed_review_alternative',
        'overrides':overrides,'supplementary_review_hash':digest}


def export_layer(pilot):
    # Separate source/completion sections make every unchanged unknown visible.
    version=next(iter(pilot['documents'].values()))['version']
    documents={pid:v.to_dict() for pid,v in pilot['views'].items()};ledger=deepcopy(pilot['ledger'])
    readers={pid:common_reader(view) for pid,view in pilot['views'].items()}
    for row in ledger:
        pid,key=row['player_id'],row['design_id'];reader=readers[pid]
        row['origin_chain']=[row['origin']]+[x['origin'] for x in pilot.get('overrides',[]) if x['player_id']==pid and x['design_id']==key]
        row['origin']=row['origin_chain'][-1];row['operational_record']=deepcopy(documents[pid]['inputs'][key])
        if key.startswith(('S','F')):reader.free_throw() if key=='S07' else reader.grade(key)
        elif key in ('P08','P09'):reader.capacity(key)
        elif key.startswith('P'):reader.measurement(key)
        elif key in ('T01','T02','T03','T11','T16'):reader.distribution(key)
        else:reader.value(key)
        row['interpretation']=deepcopy(reader.audit.get(key,{'rule':'explicit raw propensity, unchanged'}))
    return deepcopy({'version':VERSION,'purpose':'conditional action pilot; not ratings, rosters or forecasts','contract':asdict(pilot['contract']),'contract_revision':pilot['contract'].revision,
        'evidence_hashes':pilot['evidence_hashes'],'source_section':{'version':version,'registry_version':REGISTRY_VERSION,'players':pilot['source_documents']},
        'pilot_section':{'version':version,'registry_version':REGISTRY_VERSION,'players':documents},'ledger':ledger,
        'scenario':pilot.get('scenario','initial_readiness_baseline'),'overrides':pilot.get('overrides',[])})


def named_config(pilot,*,possessions=8):
    """Counterfactual three-versus-three pod, no claim of live-team ownership."""
    aliases=('luka','white','zubac','harper','castle','gobert');views=[pilot['views'][IDS[a]] for a in aliases]
    offense_profiles=tuple(compile_offense(v) for v in views);interactions=tuple(compile_interaction(v) for v in views)
    guards={'luka':'castle','white':'harper','zubac':'gobert','harper':'white','castle':'luka','gobert':'zubac'}
    kick={'luka':'white','white':'luka','zubac':'white','harper':'castle','castle':'harper','gobert':'castle'}
    setups=tuple(DriveSetup(IDS[a],IDS[guards[a]],IDS[kick[a]],IDS['zubac' if a in ('luka','white') else 'gobert'] if a in ('luka','white','harper','castle') else None) for a in aliases)
    screen_profiles=tuple(compile_screen(pilot['views'][IDS[a]],roles=ROLES[a]) for a in ('white','castle','zubac','gobert'))
    calls=tuple(ScreenCall(IDS[a],IDS[s],(2,5.5),(1.4,4.5),(1.4,4.5),(1.5,4.8),(.8,2.8),(.6,1)) for a,s in (('luka','zubac'),('harper','gobert')))
    screen=ScreenExperiment(screen_profiles,calls)
    creation=CreationExperiment(interactions,setups,screens=screen)
    dep=tuple(Deployment(IDS[a],2.5+(i%3)*.5,6.8) for i,a in enumerate(aliases))
    offense=CombinedOffense(offense_profiles,dep,(),creation=creation)
    config=InteriorExperiment((),('pilot_a','pilot_b'),possessions=possessions,offense=offense)
    teams=[{'id':'pilot_a','abbrev':'PA','name':'Counterfactual pilot A'},{'id':'pilot_b','abbrev':'PB','name':'Counterfactual pilot B'}]
    players=[{'id':IDS[a],'name':a,'team_id':teams[i//3]['id'],'position':('PG','SG','C')[i%3],'minutes_projection':48,'age':27,'height_inches':78,'weight_lbs':220,'wingspan_inches':82,'rotation_priority':'starter'} for i,a in enumerate(aliases)]
    canonical={'teams':teams,'players':players,'traits':[],'staff_profiles':[],'_allow_internal_caches':True}
    game={'externalGameId':'pilot_action_fixture','gameDate':'2026-11-14','homeTeamId':'1','awayTeamId':'2'}
    context={'canonical':canonical,'schedule':[game],'boxscores':[],'real_minutes':{},'manifestos':{},'odds':{},'sim_cache':{},'indices':{'schedule_by_game_id':{'pilot_action_fixture':game},'teams_by_espn_id':{'1':teams[0],'2':teams[1]}}}
    return context,config


def prepared(pilot):
    from nba_gm_data.offense_response import prepare_coupled
    from nba_gm_data.creation_passing import prepare_creation
    context,config=named_config(pilot)
    pools={tid:[{'player':p,'minutes':48} for p in context['canonical']['players'] if p['team_id']==tid] for tid in ('pilot_a','pilot_b')}
    anchors={tid:None for tid in pools};contexts={tid:None for tid in pools}
    coupled=prepare_coupled(config.offense,pools,anchors,contexts)
    return prepare_creation(config.offense.creation,coupled,pools,anchors,contexts)
