"""Conditional action measurements of existing functions, never a score engine.

Sampling uncertainty describes repeated events at fixed parameter choices.
Source/prior ranges are separate scenario alternatives, not confidence bands.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import math
import random
import statistics

from nba_gm_data.experimental_inputs import InterpretedInputs,common_reader
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.creation_passing import (compile_interaction,containment_response,helper_response,delivery_response,sample_delivery,handling_loss,DriveSetup,resolve_drive)
from nba_gm_data.screen_navigation import compile_screen,resolve_screen,ScreenCall,ScreenExperiment
from nba_gm_data.interior_defense import compile_profile,interior_response,ArrivalContext
from nba_gm_data.shot_geometry import ShotGeometry
from experiments.screen_navigation.fixtures import screen_fixture
from .pilot import IDS,ROLES,variant,capacity_variant,review_alternative,prepared


PROBE_VERSION='conditional_action_probes_2026_11_14_v1'


def wilson(count,n):
    if n==0:return None
    p=count/n;z=1.96;d=1+z*z/n
    c=(p+z*z/(2*n))/d;r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-r),min(1,c+r)]


def controls(pilot,settings):
    _,fixture=screen_fixture(possessions=2);template=fixture.offense.profiles[0].inputs.to_dict()
    result={};motion=settings.get('motion',(3,6,2.5));capacity=settings.get('capacity',(.5,2/3))
    for name in ('creator','screener','navigator','coverage'):
        doc=deepcopy(template);doc['player_id']='synthetic_control_'+name
        for key,value in zip(('P05','P06','P07'),motion,strict=True):doc['inputs'][key]['value']['measurements'][0]['value']=value
        for key,value in zip(('P08','P09'),capacity,strict=True):doc['inputs'][key]['value']['display_grade']['grade']=value*100
        w=InterpretedInputs(PlayerInputs(doc),pilot['contract'])
        result[name]=compile_interaction(w) if name=='creator' else compile_screen(w,roles=('screener','navigator','coverage'))
    return result


def containment(pilot,settings=None):
    settings=settings or {};reference=controls(pilot,settings)['creator'];rows={}
    for alias in ('castle','luka'):
        defender=compile_interaction(pilot['views'][IDS[alias]])
        setup=DriveSetup(reference.player_id,defender.player_id,None,None,screen_separation_m=0)
        rows[alias]=containment_response(reference,defender,setup)
    return {'scope':'same synthetic creator, no screen, matched geometry; not total defense', 'actors':rows,
        'castle_advantage_probability_points':rows['luka']['beat_probability']-rows['castle']['beat_probability']}


def help_probe(pilot,settings=None,n=4096):
    settings=settings or {};rows={};window=settings.get('help_window',1.25)
    for alias in ('white','castle'):
        p=compile_interaction(pilot['views'][IDS[alias]]);rng=random.Random(1401)
        outcome=Counter();last=None
        for _ in range(n):
            last=helper_response(p,(2,1),(.8,1.5),window,rng.random(),rng.random())
            for key in ('noticed','committed','timely'):outcome[key]+=bool(last[key])
        exact=last['recognition_probability']*p.help_commitment*(last['arrival_s']<=window)
        rows[alias]={'n':n,'events':dict(outcome),'timely_wilson95':wilson(outcome['timely'],n),'exact_timely_probability':exact,
            'recognition_probability':last['recognition_probability'],'recognition_delay_s':last['recognition_delay_s'],'arrival_s':last['arrival_s'],'revision':p.revision}
    return {'scope':'same responsibility/start/window; S38/S44/position and dimensional movement remain distinct','window_s':window,'actors':rows,
        'white_advantage_probability_points':rows['white']['exact_timely_probability']-rows['castle']['exact_timely_probability']}


def passing(pilot,settings=None,n=4096):
    settings=settings or {};families={};distance=settings.get('distance',4);pressure=settings.get('pressure',.4);opening=settings.get('opening',.7);receiving=settings.get('receiving',.7)
    for family in ('F03','F04'):
        rows={};paired={}
        for alias in ('luka','harper'):
            p=compile_interaction(pilot['views'][IDS[alias]]);notice=.05+.95*p.pass_skill(family,'recognition')
            delivery=delivery_response(p,family,distance,pressure,opening);rng=random.Random(1402);count=Counter();received=[]
            for _ in range(n):
                nr,dr,cr=rng.random(),rng.random(),rng.random()
                seen=nr<notice;count['noticed']+=seen
                if not seen:count['missed_read']+=1;received.append(0);continue
                placed=sample_delivery(delivery,dr);accurate=placed['accurate'];count['accurate_delivery']+=accurate
                if not accurate:count['inaccurate_delivery']+=1;received.append(0);continue
                caught=cr<placed['quality']*(.5+.5*receiving);count['caught']+=caught;count['failed_catch']+=not caught;received.append(int(caught))
            rows[alias]={'n':n,'events':dict(count),'notice_probability':notice,'delivery_given_notice_probability':delivery['accuracy_probability'],
                'caught_rate':count['caught']/n,'caught_wilson95':wilson(count['caught'],n),'delivery_response':delivery,'revision':p.revision,
                'typed_loss_policy':'missed read is not a loss; inaccurate delivery belongs to passer; failed catch belongs to common receiver'}
            paired[alias]=received
        differences=[a-b for a,b in zip(paired['luka'],paired['harper'],strict=True)];mean=statistics.mean(differences);se=statistics.stdev(differences)/math.sqrt(n)
        families[family]={'actors':rows,'luka_notice_advantage':rows['luka']['notice_probability']-rows['harper']['notice_probability'],
            'luka_delivery_advantage':rows['luka']['delivery_given_notice_probability']-rows['harper']['delivery_given_notice_probability'],
            'paired_catch_difference':mean,'paired_catch_sampling95':[mean-1.96*se,mean+1.96*se]}
    return {'scope':'fixed available window and anonymous receiver; no shot/make or NBA forecast','controls':{'distance_m':distance,'pressure':pressure,'opening':opening,'receiver_S14_index':receiving},'families':families}


def security_probe(pilot,n=4096):
    rows={}
    for alias in ('luka','harper'):
        p=compile_interaction(pilot['views'][IDS[alias]]);probability=handling_loss(p,.8,1);rng=random.Random(1405)
        count=sum(rng.random()<probability for _ in range(n))
        rows[alias]={'n':n,'handling_losses':count,'probability':probability,'wilson95':wilson(count,n),
            'S17_response_index':p.skill('S17'),'S17_source_status':pilot['source_documents'][IDS[alias]]['inputs']['S17']['status']}
    return {'scope':'matched imposed pressure .8 and one second exposure; source-unknown Luka alternatives cannot establish a security ranking','actors':rows,
        'harper_lower_loss_difference':rows['luka']['probability']-rows['harper']['probability']}


def screen_pair(pilot,first,second,*,role='screener',settings=None,n=512):
    settings=settings or {};fixed=controls(pilot,settings);rows={};paired={}
    for alias in (first,second):
        actor=compile_screen(pilot['views'][IDS[alias]],roles=('screener',) if role=='screener' else ('navigator',))
        creator=fixed['creator'];screener=actor if role=='screener' else fixed['screener'];navigator=actor if role=='navigator' else fixed['navigator'];coverage=fixed['coverage']
        setup=DriveSetup(creator.player_id,navigator.player_id,None,screener.player_id,screen_separation_m=0)
        call=ScreenCall(creator.player_id,screener.player_id,(2,5.5),(1.4,4.5),(1.4,4.5),(1.5,4.8),(.8,2.8),(.6,1),settings.get('coverage','show_then_recover'))
        spec=ScreenExperiment((screener,navigator,coverage),(call,));state={'spec':spec,'profiles':{p.player_id:p for p in (screener,navigator,coverage)},'calls':{creator.player_id:call},'roller_defenders':{screener.player_id:coverage.player_id}}
        rng=random.Random(1403);count=Counter();values=[];arrivals=[];windows=[]
        for _ in range(n):
            draws=[rng.random() for _ in range(48)]
            if settings.get('stratum','called_roll')=='called_roll':draws[39]=screener.preferences[0]+screener.preferences[1]*.5 if screener.preferences[1] else 0
            result=resolve_screen(state,creator,setup,draws)
            count[result['route']]+=1;count['illegal_screen']+=result['kind']=='illegal_screen';count['contact']+=result['contact_overlap']>0
            values.append(result['navigation_delay_s'] if result['kind']!='illegal_screen' else 0)
            arrivals.append(result['guard_arrival_s']);windows.append(max(0,result['window_end_s']-max(result['window_start_s'],result['attacker_clear_s'])))
        rows[alias]={'n':n,'events':dict(count),'illegal_screen_wilson95':wilson(count['illegal_screen'],n),'mean_legal_effective_navigation_delay_s':statistics.mean(values),
            'mean_guard_arrival_s':statistics.mean(arrivals),'mean_remaining_receiver_interval_at_handler_arrival_s':statistics.mean(windows),'revision':actor.revision}
        paired[alias]=values
    differences=[a-b for a,b in zip(paired[first],paired[second],strict=True)];mean=statistics.mean(differences);se=statistics.stdev(differences)/math.sqrt(n)
    return {'actors':rows,'role':role,'contrast':[first,second],'stratum':settings.get('stratum','called_roll'),'scope':'screen/navigation phase only; remaining interval is not guaranteed passability',
        'first_minus_second_delay_s':mean,'paired_delay_sampling95':[mean-1.96*se,mean+1.96*se]}


def geometry_probe(pilot):
    rows={}
    for alias in ('zubac','gobert'):
        p=compile_profile(pilot['views'][IDS[alias]])
        response=interior_response(p,ArrivalContext(anchor_available=1,poa_containment=0,recognition_delay_s=0),geometry=ShotGeometry(.6,1,320,.6,1.2,attack_time_s=0,preparation_s=.1),arrival_override_s=.02)
        rows[alias]={'standing_reach_cm':p.standing_reach_cm,'jump_control_cm':p.jump_cm,'block_probability':response['block_probability'],'conversion_reduction':response['conversion_reduction'],'source_revision':p.revision}
    return {'scope':'matched single contest, common arrival/release/jump where declared; no defender rank','actors':rows}


def coupled_actions(pilot,n=64):
    state=prepared(pilot);result={};examples=[]
    for alias,tid,opp in (('luka','pilot_a','pilot_b'),('harper','pilot_b','pilot_a')):
        rng=random.Random(1404);counts=Counter();choices=Counter();stages=Counter()
        for i in range(n):
            response=resolve_drive(state,IDS[alias],tid,opp,[rng.random() for _ in range(48)],24)
            counts[response.get('outcome',response['kind'])]+=1;choices[response['record'].get('choice','before_choice_loss')]+=1
            record=response['record'];stages['beat_defender']+=bool(record.get('beat_defender'));stages['bad_choice']+=bool(record.get('bad_choice'))
            for key in ('noticed','committed','timely'):stages['help_'+key]+=bool(record.get('help',{}).get(key))
            for family,noticed in record.get('noticed_options',{}).items():stages['noticed_'+family]+=bool(noticed)
            stages['pass_selected']+='pass' in record;stages['accurate_delivery']+=bool(record.get('pass',{}).get('accurate'))
            if i<3:examples.append({'actor':alias,'record':response['record'],'kind':response['kind']})
        result[alias]={'n':n,'outcomes':dict(counts),'choices':dict(choices),'stages':dict(stages),'reception_gate':'not sampled by this first-action resolver; sampled separately in fixed-receiver probes and toy kernel'}
    return {'scope':'coupled feasibility only; named receivers differ, so not an isolated creator ranking or made-FG forecast; pressure/windows are derived here rather than imposed analytic pass controls','actors':result,'examples':examples}


def scenarios(base):
    result=[{'name':'reference','pilot':base,'groups':{'containment','help','passing','security','screen','navigation','geometry','coupled'},'controls':{}}]
    def add(name,changes,groups,**controls):result.append({'name':name,'pilot':variant(base,changes,name=name),'groups':set(groups),'controls':controls})
    for name,motion in (('common_slow',(2.5,5.5,2.2)),('common_fast',(3.5,6.5,2.8))):
        changes={a:{key:value for key,value in zip(('P05','P06','P07'),motion,strict=True) if base['documents'][IDS[a]]['inputs'][key]['status']!='unknown'} for a in IDS}
        add(name,changes,('containment','help','screen','navigation'),motion=motion)
    add('containment_narrow_source_contrast',{'castle':{'S33':85,'S34':78,'S41':54},'luka':{'S33':58}},('containment',))
    add('containment_wide_source_contrast',{'castle':{'S33':96,'S34':92,'S41':77},'luka':{'S33':35}},('containment',))
    add('containment_countervailing_mobility',{'castle':{'P05':2.5,'P06':5.5,'P07':2.2,'S33':85,'S34':78,'S41':54},'luka':{'P05':3.5,'P06':6.5,'P07':2.8,'S33':58}},('containment',))
    add('common_help_attention',{'white':{'S44':80},'castle':{'S44':80}},('help',))
    add('castle_read_limited',{'castle':{'S38':65,'S44':85}},('help',))
    add('castle_attention_limited',{'castle':{'S38':80,'S44':65}},('help',))
    add('help_narrow_source_contrast',{'white':{'S38':80,'S39':79,'S44':77},'castle':{'S38':75,'S39':74,'S44':78}},('help',))
    add('help_countervailing_mobility',{'white':{'P05':2.5,'P06':5.5,'P07':2.2},'castle':{'P05':3.5,'P06':6.5,'P07':2.8}},('help',),help_window=1.2)
    for window in (1.1,1.5):add('help_window_'+str(window),{},('help',),help_window=window)
    for family in ('F03','F04'):
        for label,read,execution in (('read_limited',65,80),('delivery_limited',78,65)):
            add(f'harper_{family}_{label}',{'harper':{family+'.recognition':read,family+'.execution':execution}},('passing',))
    add('pass_narrow_F03_source',{'luka':{'F03.recognition':88,'F03.execution':85},'harper':{'F03.recognition':78,'F03.execution':83}},('passing',))
    add('lob_unknown_Harper_strong',{'luka':{'F04.recognition':84,'F04.execution':80},'harper':{'F04.recognition':85,'F04.execution':85}},('passing',))
    for receive in (.5,.85):add('common_receiving_'+str(receive),{},('passing',),receiving=receive)
    for security in (80,90):add('luka_security_prior_'+str(security),{'luka':{'S17':security}},('security','coupled'))
    for risk in (.35,.65):add('common_passing_risk_'+str(risk),{'luka':{'T07':risk},'harper':{'T07':risk}},('coupled',))
    for pressure,opening in ((.2,.85),(.65,.5)):add(f'pass_window_{pressure}',{},('passing',),pressure=pressure,opening=opening)
    for label,capacity in (('common_capacity_low',(.35,.55)),('common_capacity_high',(.65,.75))):
        result.append({'name':label,'pilot':capacity_variant(base,*capacity,name=label),'groups':{'screen','navigation','geometry'},'controls':{'capacity':capacity}})
    for gain in (.85,1.15):result.append({'name':'technique_mapping_gain_'+str(gain),'pilot':variant(base,{},name='mapping_gain',contract=replace(base['contract'],research_gain=gain)),'groups':{'containment','help','passing','screen','navigation'},'controls':{}})
    add('matched_body_screen',{'zubac':{'P01':200,'P04':100},'caruso':{'P01':200,'P04':100},'gobert':{'P01':200,'P04':100},'davion':{'P01':200,'P04':100},'ajay':{'P01':200,'P04':100}},('screen','navigation'))
    add('screen_overlap_source_ranges',{'zubac':{'S27':80,'S28':62},'caruso':{'S27':90,'S28':88}},('screen',))
    add('navigation_overlap_source_ranges',{'davion':{'S35':82},'ajay':{'S35':83}},('navigation',))
    add('navigation_countervailing_lateral',{'davion':{'P07':2.2},'ajay':{'P07':2.8}},('navigation',))
    add('navigation_overlap_and_lateral',{'davion':{'S35':82,'P07':2.2},'ajay':{'S35':83,'P07':2.8}},('navigation',))
    policies={'roll_led':{'screen':.15,'roll':.75,'pop':0,'slip':.10},'slip_seeking':{'screen':.10,'roll':.45,'pop':0,'slip':.45},'hold_led':{'screen':.65,'roll':.30,'pop':0,'slip':.05}}
    for label,mix in policies.items():add(label,{a:{'T11':mix} for a in ('zubac','gobert','caruso')},('screen',),stratum='conditional_preference')
    proposed=review_alternative(base);result.append({'name':'separate_proposed_review','pilot':proposed,'groups':{'screen','geometry','coupled'},'controls':{}})
    for reach in (292.1,297.18):result.append({'name':'dated_reach_'+str(reach),'pilot':review_alternative(base,historical_reach=reach),'groups':{'geometry'},'controls':{}})
    result.append({'name':'proposed_screen_overlap','pilot':variant(proposed,{'zubac':{'S27':80},'gobert':{'S27':92,'S28':85}},name='proposed_overlap'), 'groups':{'screen'},'controls':{}})
    for jump in (25,55):add('common_jump_'+str(jump),{'zubac':{'P10':jump},'gobert':{'P10':jump}},('geometry',))
    # Coherent coupled stresses perturb a few linked mechanisms, not all 94 axes.
    add('crowded_pressure_reading_stress',{'luka':{'S17':80},'harper':{'F03.recognition':65,'F03.execution':80},'zubac':{'S14':50},'gobert':{'S14':50}},('passing','coupled'),pressure=.65,opening=.5,receiving=.5)
    add('help_reading_and_slow_travel',{'white':{'P05':2.5,'P06':5.5,'P07':2.2},'castle':{'S38':80,'S44':65,'P05':2.5,'P06':5.5,'P07':2.2}},('help',),motion=(2.5,5.5,2.2))
    return result


def run_scenario(row,*,pass_n=4096,screen_n=512):
    pilot=row['pilot'];settings=row['controls'];groups=row['groups'];out={'name':row['name'],'controls':settings,'contract_revision':pilot['contract'].revision,
        'overrides':pilot.get('overrides',[]),'interpretation':{'version':PROBE_VERSION,'sampling95':'conditional event Monte Carlo only; parameter alternatives are not confidence intervals'}}
    if 'containment' in groups:out['containment']=containment(pilot,settings)
    if 'help' in groups:out['help']=help_probe(pilot,settings,n=pass_n)
    if 'passing' in groups:out['passing']=passing(pilot,settings,n=pass_n)
    if 'security' in groups:out['security']=security_probe(pilot,n=pass_n)
    if 'screen' in groups:
        out['screen_zubac_caruso']=screen_pair(pilot,'zubac','caruso',settings=settings,n=screen_n)
        out['screen_zubac_gobert_prior_sensitive']=screen_pair(pilot,'zubac','gobert',settings=settings,n=screen_n)
    if 'navigation' in groups:out['navigation']=screen_pair(pilot,'davion','ajay',role='navigator',settings=settings,n=screen_n)
    if 'geometry' in groups:out['geometry']=geometry_probe(pilot)
    if 'coupled' in groups:out['coupled_actions']=coupled_actions(pilot)
    return out
