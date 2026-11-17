"""Isolated event-accounted game consumer for the interior experiment.

Existing game preparation supplies availability and minutes. Legacy offense
features are a temporary test environment. No team score is assigned first;
points, blocks, fouls and rebounds are sums of resolved attack events. This
branch does not call legacy rim/shot-diet/box normalization/plus-minus code.
"""
from __future__ import annotations

import random
from dataclasses import replace,asdict

from .interior_defense import FORMULA_VERSION, InteriorExperiment, clamp, fingerprint, interior_response, reference_report
from .schema import SimGameResult
from .utils import stable_id

STATS=('points','fgm','fga','fg3m','fg3a','ftm','fta','rim_attempts','rebounds','offensive_rebounds','defensive_rebounds','assists','turnovers','steals','blocks','personal_fouls')


def _pick(items,weights,draw):
    total=sum(weights)
    if total<=0:raise ValueError('Positive participation weights required')
    target=draw*total
    for item,weight in zip(items,weights,strict=True):
        target-=weight
        if target<0:return item
    return items[-1]


def _offense(features):
    """Only selected non-rim-defense legacy channels enter this environment.

    No impact/usage/old rim/anchor/defensive spatial rating is consumed, even
    indirectly through scoring weights. New S01..S35/C31 are NOT implemented.
    """
    spacing=features['spacing'];creation=features['shot_creation'];pressure=features['rim_pressure']
    return {
        'weight':max(.1,.5+creation/100+pressure/200),
        'rim_share':clamp(.335+(pressure-50)*.002,.18,.48),
        'three_share':clamp(.30+(spacing-50)*.003,.15,.52),
        'rim_pct':clamp(.56+(pressure-50)*.0016,.45,.78),
        'mid_pct':clamp(.40+(creation-50)*.0012,.30,.55),
        'three_pct':clamp(.30+max(0,spacing-50)*.0017+max(0,creation-72)*.0009,.25,.45),
        'ft_pct':clamp(.70+max(0,spacing-55)*.0022+max(0,creation-65)*.0012,.58,.92),
        'passing':features['passing'],'oreb':features['offensive_rebounding'],
    }



def shot_probabilities(off,response,zone):
    foul_extra=response['foul_probability'] if response else 0.0
    foul=clamp((.035 if zone=='rim' else .012)+foul_extra)
    block=response['block_probability'] if response else 0.0
    conversion=off['rim_pct'] if zone=='rim' else off['three_pct'] if zone=='perimeter' else off['mid_pct']
    make=clamp(conversion-(response['conversion_reduction'] if response else 0.0))
    shots=3 if zone=='perimeter' else 2
    return {'foul':foul,'block_given_no_foul':block,'make_given_unblocked':make,
            'expected_points':foul*shots*off['ft_pct']+(1-foul)*(1-block)*make*shots,
            'rebound_probability':foul*(1-off['ft_pct'])+(1-foul)*(1-(1-block)*make)}


def expected_environment(profile,context,*,rim_share=.45,three_share=.30,oreb_probability=.284):
    """Analytic controlled sensitivity using the same probabilities as games.

    Legacy offense environment is held explicit. No new spacing/POA/creation
    implementation is implied by varying these declared conditions.
    """
    if not 0<=rim_share<=1 or not 0<=three_share<=1-rim_share or not 0<=oreb_probability<1:
        raise ValueError('Invalid controlled opportunity distribution')
    responses={zone:interior_response(profile,context,zone=zone) for zone in ('rim','short_paint','perimeter')} if profile else {z:None for z in ('rim','short_paint','perimeter')}
    avoid=responses['rim']['avoidance_probability'] if profile else 0.0
    shares={'rim':rim_share*(1-avoid),'perimeter':three_share+rim_share*avoid*.65,'short_paint':1-rim_share-three_share+rim_share*avoid*.35}
    off={'rim_pct':.65,'mid_pct':.42,'three_pct':.36,'ft_pct':.77}
    probs={zone:shot_probabilities(off,responses[zone],zone) for zone in shares}
    points=sum(shares[z]*probs[z]['expected_points'] for z in shares)
    rebound=sum(shares[z]*probs[z]['rebound_probability'] for z in shares)
    # The game chooses another shooter after each OREB; this controlled
    # environment has identical reference shooters, so geometric continuation
    # is exact. Turnover rate .12 is the same as the experimental game.
    attacks_per_possession=1/(1-.88*rebound*oreb_probability)
    return {'zone_shares':shares,'probabilities':probs,'expected_points_per_100_possessions':100*.88*points*attacks_per_possession,
            'expected_blocks_per_100_possessions':100*.88*sum(shares[z]*(1-probs[z]['foul'])*probs[z]['block_given_no_foul'] for z in shares)*attacks_per_possession,
            'expected_shooting_fouls_per_100_possessions':100*.88*sum(shares[z]*probs[z]['foul'] for z in shares)*attacks_per_possession,
            'expected_reboundable_misses_per_100_possessions':100*.88*rebound*attacks_per_possession,
            'rim_response':responses['rim']}


def simulate_interior_game(canonical,game,home_team,away_team,home_pool,away_pool,mode,seed,experiment: InteriorExperiment):
    from .sim import player_feature_vector, health_adjusted_player_features
    if not isinstance(experiment,InteriorExperiment):raise ValueError('Explicit InteriorExperiment required')
    pools={home_team['id']:home_pool,away_team['id']:away_pool}; teams={t['id']:t for t in (home_team,away_team)}
    lines={}; attacks={}; reports={}; responses={}; expected={}; anchor_ids={}; anchors={}; contexts={}
    coupled=None
    if experiment.offense is not None:
        from .offense_response import CombinedOffense,baseline,prepare_coupled,plan_attack,choose_outlet
        if not isinstance(experiment.offense,CombinedOffense):raise ValueError('Explicit CombinedOffense required')
        offensive_profiles={p.player_id:p for p in experiment.offense.profiles}
    for team_id,pool in pools.items():
        if not pool or sum(float(p['minutes']) for p in pool)<=0:raise ValueError('Experimental game requires active players')
        lines[team_id]={};attacks[team_id]=[]
        for item in pool:
            p=item['player'];pid=p['id']
            if experiment.offense is None:
                feat=health_adjusted_player_features(player_feature_vector(canonical,p,include_spatial=False).features,item)
                expected[pid]=_offense(feat)
            else:
                if pid not in offensive_profiles:raise ValueError(f'{pid}: explicit offensive scenario required')
                expected[pid]=baseline(offensive_profiles[pid])
            lines[team_id][pid]={'player_id':pid,'player_name':p['name'],'team_id':team_id,'team_abbrev':teams[team_id]['abbrev'],
                'minutes':item['minutes'],'health_status':item.get('health_status','actual_or_untracked'),
                'health_fatigue':item.get('health_fatigue',0),'health_rust':item.get('health_rust',0),**{key:0 for key in STATS}}
        anchor=experiment.anchor(team_id)
        anchors[team_id]=anchor
        anchor_ids[team_id]=anchor.profile.inputs.player_id if anchor else None
        if anchor is None:
            reports[team_id]={'status':'explicit_no_anchor_counterfactual','R18':'not_assessed'}
            responses[team_id]=None
            contexts[team_id]=None
        else:
            # Ownership changes invalidate the configured deployment. Absence
            # from the active pool gates availability, never stale approval.
            player=next((p for p in canonical['players'] if p['id']==anchor_ids[team_id]),None)
            if player is None or player['team_id']!=team_id:raise ValueError('Stale experimental anchor ownership')
            item=next((p for p in pool if p['player']['id']==player['id']),None)
            minutes=0.0 if item is None else float(item['minutes'])
            fatigue=0.0 if item is None else float(item.get('health_fatigue') or 0)
            rust=0.0 if item is None else float(item.get('health_rust') or 0)
            capacity=clamp(1-fatigue*.002-rust*.001,.65,1)
            context=replace(anchor.context,anchor_available=anchor.context.anchor_available*clamp(minutes/48),capacity_factor=anchor.context.capacity_factor*capacity)
            contexts[team_id]=context
            reports[team_id]=reference_report(anchor.profile,context)
            responses[team_id]={zone:interior_response(anchor.profile,context,zone=zone) for zone in ('rim','short_paint','perimeter')}
    if experiment.offense is not None:
        coupled=prepare_coupled(experiment.offense,pools,anchors,contexts)
    creation=None
    if coupled and experiment.offense.creation is not None:
        from .creation_passing import CreationExperiment,prepare_creation,resolve_drive
        if not isinstance(experiment.offense.creation,CreationExperiment):raise ValueError('Explicit CreationExperiment required')
        creation=prepare_creation(experiment.offense.creation,coupled,pools,anchors,contexts)
    specification_revision=experiment.revision
    evaluation_revision=fingerprint({'specification_revision':specification_revision,
        'offense':expected,'participation':[(tid,[(r['player_id'],r['minutes'],r['health_fatigue'],r['health_rust']) for r in roster.values()]) for tid,roster in lines.items()],
        'deployed_contexts':{tid:(response['rim']['context'] if response else None) for tid,response in responses.items()}})
    game_id=str(game['externalGameId'])
    # One regulation budget shared by the teams; overtime adds 10 possessions
    # per side using the same accounting. No score/box reconciliation follows.
    def segment(start,count,period):
        for team_id,opp_id in ((home_team['id'],away_team['id']),(away_team['id'],home_team['id'])):
            own=list(lines[team_id].values());opp=list(lines[opp_id].values())
            shooter_weights=[r['minutes']*expected[r['player_id']]['weight'] for r in own]
            defender_weights=[r['minutes'] for r in opp]
            for possession in range(start,start+count):
                attempt=0
                possession_creation=creation
                clock_remaining=creation['spec'].possession_budget_s if creation else None
                pending_creator_id=None
                while True:
                    # Each attempt owns its RNG domain. Changed rebounds do
                    # not shift unrelated subsequent possession draws.
                    rng=random.Random(f'{seed}:{game_id}:{mode}:{FORMULA_VERSION}:{team_id}:{possession}:{attempt}')
                    draws=[rng.random() for _ in range(48 if creation else 24 if coupled else 16)]
                    shooter=lines[team_id][pending_creator_id] if pending_creator_id else _pick(own,shooter_weights,draws[0]);off=expected[shooter['player_id']]
                    event={'period':period,'possession':possession,'continuation':attempt,'shooter_id':shooter['player_id']}
                    if not creation and draws[1]<.12:
                        shooter['turnovers']+=1;event['outcome']='turnover'
                        if draws[2]<.50:
                            defender=_pick(opp,defender_weights,draws[3]);defender['steals']+=1;event['steal_by']=defender['player_id']
                        attacks[team_id].append(event);break
                    rim_share=off['rim_share'];three_share=off['three_share']
                    zone='rim' if draws[2]<rim_share else 'perimeter' if draws[2]<rim_share+three_share else 'short_paint'
                    event['initial_zone']=zone
                    if coupled:
                        if creation:
                            if 'screens' in creation:
                                action=resolve_drive(possession_creation,shooter['player_id'],team_id,opp_id,draws,clock_remaining,screen_allowed=attempt==0)
                            else:action=resolve_drive(possession_creation,shooter['player_id'],team_id,opp_id,draws,clock_remaining)
                            event['initial_zone']='drive';event['creation_chain']=action['record']
                            clock_remaining-=action['elapsed_s'];event['clock_remaining_s']=clock_remaining
                            if clock_remaining<=0:
                                shooter['turnovers']+=1;event.update(outcome='shot_clock_turnover',points=0,turnover_by=shooter['player_id'])
                                attacks[team_id].append(event);break
                            if action['kind']=='reset':
                                event.update(outcome='reset',points=0);attacks[team_id].append(event)
                                pending_creator_id=action.get('continuation_creator_id',shooter['player_id'])
                                if 'recovery_continuation' in action:
                                    from .pass_recovery import apply_continuation
                                    possession_creation=apply_continuation(possession_creation,action['recovery_continuation'])
                                elif getattr(creation['spec'],'receipt_policy',None):
                                    from .pass_recovery import advance_after_reset
                                    possession_creation=advance_after_reset(possession_creation,action,pending_creator_id)
                                attempt+=1;continue
                            if action['kind']=='turnover':
                                lines[team_id][action['responsible']]['turnovers']+=1
                                event.update(outcome=action['outcome'],points=0,turnover_by=action['responsible'])
                                if action.get('offensive_foul_by'):
                                    fouler=action['offensive_foul_by'];lines[team_id][fouler]['personal_fouls']+=1;event['offensive_foul_by']=fouler
                                if action.get('steal_by'):
                                    lines[opp_id][action['steal_by']]['steals']+=1;event['steal_by']=action['steal_by']
                                attacks[team_id].append(event);break
                            plan=action['plan'];shooter=lines[team_id][plan['player_id']];event['shooter_id']=shooter['player_id']
                            if action['passer_id']:event['passer_id']=action['passer_id']
                            response=plan['response'];zone=plan['zone']
                        else:
                            plan=plan_attack(coupled,shooter['player_id'],zone,draws,opp_id,anchors[opp_id],contexts[opp_id])
                        response=plan['response'];zone=plan['zone']
                        if not creation and zone=='rim' and response and draws[21]<response['avoidance_probability']:
                            outlet=choose_outlet(coupled,team_id,draws[20])
                            if outlet is not None:
                                event['avoided_interior_opportunity']=plan['details']
                                shooter=lines[team_id][outlet]
                                plan=plan_attack(coupled,outlet,'perimeter',draws,opp_id,anchors[opp_id],contexts[opp_id],outlet=True)
                                event['redirected']=True;event['original_shooter_id']=event['shooter_id'];event['shooter_id']=outlet
                                response=plan['response'];zone=plan['zone']
                        off=plan['off'];event['coupled_opportunity']=plan['details']
                        if draws[15]>=plan['reception']:
                            shooter['turnovers']+=1;event.update(zone=zone,outcome='failed_catch' if creation else 'reception_turnover',points=0)
                            if creation:event['turnover_by']=shooter['player_id']
                            attacks[team_id].append(event);break
                    else:
                        response=responses[opp_id][zone] if responses[opp_id] else None
                        if zone=='rim' and response and draws[3]<response['avoidance_probability']:
                            zone='perimeter' if draws[4]<.65 else 'short_paint'
                            response=responses[opp_id][zone]
                            event['redirected']=True
                    event['zone']=zone
                    defender=lines[opp_id].get(anchor_ids[opp_id])
                    if creation and 'contest_defender_id' in plan:
                        event['contest_defender_id']=plan['contest_defender_id'];defender=lines[opp_id].get(plan['contest_defender_id'])
                    foul_extra=response['foul_probability'] if response else 0
                    probabilities=shot_probabilities(off,response,zone)
                    foul=probabilities['foul'];block=probabilities['block_given_no_foul'];make=probabilities['make_given_unblocked']
                    shots=3 if zone=='perimeter' else 2
                    event['probabilities']={key:probabilities[key] for key in ('foul','block_given_no_foul','make_given_unblocked')}
                    event['expected_points_before_rebounds']=probabilities['expected_points']
                    last_ft_miss=False
                    if draws[5]<foul:
                        # These are unsuccessful shooting-foul attempts: no
                        # counted FGA, 2/3 FT. And-ones/nonshooting fouls deferred.
                        fouler=defender if defender and draws[5]<foul_extra else _pick(opp,defender_weights,draws[6])
                        fouler['personal_fouls']+=1;event['foul_by']=fouler['player_id']
                        shooter['fta']+=shots
                        made=sum(draws[8+i]<off['ft_pct'] for i in range(shots))
                        shooter['ftm']+=made;shooter['points']+=made
                        last_ft_miss=draws[8+shots-1]>=off['ft_pct']
                        event.update(outcome='shooting_foul',fta=shots,ftm=made,points=made)
                        if not last_ft_miss:
                            attacks[team_id].append(event);break
                    else:
                        shooter['fga']+=1
                        if zone=='perimeter':shooter['fg3a']+=1
                        if zone=='rim':shooter['rim_attempts']+=1
                        if draws[6]<block:
                            assert defender is not None
                            defender['blocks']+=1;event.update(outcome='block',block_by=defender['player_id'],points=0)
                        elif draws[7]<make:
                            shooter['fgm']+=1
                            if zone=='perimeter':shooter['fg3m']+=1
                            shooter['points']+=shots;event.update(outcome='made_fg',points=shots)
                            passers=[r for r in own if r is not shooter]
                            if creation:
                                if event.get('passer_id') and action['record']['assist_eligible']:
                                    lines[team_id][event['passer_id']]['assists']+=1;event['assist_by']=event['passer_id']
                            elif passers and draws[11]<(coupled['spec'].assist_credit_probability if coupled else .58):
                                passer=_pick(passers,[r['minutes']*max(1,expected[r['player_id']]['passing']) for r in passers],draws[12])
                                passer['assists']+=1;event['assist_by']=passer['player_id']
                            attacks[team_id].append(event);break
                        else:event.update(outcome='missed_fg',points=0)
                    event['reboundable_miss']=True
                    # The next shot exists only after a real offensive rebound.
                    oreb=clamp(.20+sum(r['minutes']*expected[r['player_id']]['oreb'] for r in own)/sum(r['minutes'] for r in own)*.0012,.18,.34)
                    if coupled:oreb=coupled['spec'].offensive_rebound_probability
                    if draws[13]<oreb:
                        rebounder=_pick(own,[r['minutes']*max(1,expected[r['player_id']]['oreb']) for r in own],draws[14])
                        rebounder['rebounds']+=1;rebounder['offensive_rebounds']+=1
                        event['rebound_side']='offense';event['rebound_by']=rebounder['player_id']
                        attacks[team_id].append(event);attempt+=1
                        if creation:
                            clock_remaining=creation['spec'].rebound_budget_s;pending_creator_id=rebounder['player_id']
                            if getattr(creation['spec'],'receipt_policy',None):
                                possession_creation=creation
                                event['continuation_position_policy']='existing supplied rebound context; rebound positions are not tracked'
                    else:
                        rebounder=_pick(opp,defender_weights,draws[14]);rebounder['rebounds']+=1;rebounder['defensive_rebounds']+=1
                        event['rebound_side']='defense';event['rebound_by']=rebounder['player_id']
                        attacks[team_id].append(event);break
    segment(0,experiment.possessions,'regulation')
    total_possessions=experiment.possessions;over=0
    while sum(r['points'] for r in lines[home_team['id']].values())==sum(r['points'] for r in lines[away_team['id']].values()):
        over+=1
        if over>8:raise ValueError('Experimental overtime safety bound reached; no forced winner')
        segment(total_possessions,10,f'overtime_{over}');total_possessions+=10
    if over:
        # Keep actual regulation minutes intact; allocate 25 OT minutes by
        # original exposure. No new rotation policy or foul-out substitution.
        for roster in lines.values():
            total=sum(r['minutes'] for r in roster.values())
            for row in roster.values():row['minutes']+=row['minutes']/total*25*over
    team_lines=[]
    for team_id in pools:
        team_lines.append({'team_id':team_id,'team_abbrev':teams[team_id]['abbrev'],**{key:sum(r[key] for r in lines[team_id].values()) for key in STATS},
            'possessions':total_possessions,'off_rating':sum(r['points'] for r in lines[team_id].values())/total_possessions*100,
            'interior_experiment':{'formula_version':FORMULA_VERSION,'revision':evaluation_revision,'specification_revision':specification_revision,'status':'isolated_mechanism_not_calibrated',
                'defense_report':reports[team_id],'offense_attack_ledger':attacks[team_id],
                'legacy_dependencies':['selected offense features','passing/OREB proxies','availability and regulation minutes'],
                'unwired':['app actions','full C26/C29/R18','new C31 offense','live contracts/retention','plus-minus tracking','foul-out rotation changes']}})
    if coupled:
        for team in team_lines:
            metadata=team['interior_experiment']
            opponent_id=next(tid for tid in pools if tid!=team['team_id'])
            response_rows=[]
            for event in attacks[opponent_id]:
                detail=event.get('avoided_interior_opportunity') or event.get('coupled_opportunity')
                response=detail.get('defense_response') if detail else None
                if response is not None and response['zone']!='perimeter' and event.get('contest_defender_id',anchor_ids[team['team_id']])==anchor_ids[team['team_id']]:response_rows.append(response)
            if anchors[team['team_id']] is not None:
                report=reports[team['team_id']]
                report['legacy_scalar_reference']={key:report[key] for key in ('C27','C32','C36')}
                report['C27']={'status':'partial_varied_geometry','response_source':'opponent ledger coupled/avoided interior opportunities','sample_count':len(response_rows)}
                report['C32']={'status':'partial_deployed_interior_slice','by_region':{zone:{'opportunities':sum(r['zone']==zone for r in response_rows)} for zone in ('rim','short_paint')}}
                report['C36']={'status':'same_response_deployed_readout_only','sample_count':len(response_rows),
                    'mean_conditional_conversion_reduction':sum(r['conversion_reduction'] for r in response_rows)/len(response_rows) if response_rows else None,
                    'mean_block_probability':sum(r['block_probability'] for r in response_rows)/len(response_rows) if response_rows else None,
                    'mean_attempt_avoidance_probability':sum(r['avoidance_probability'] for r in response_rows)/len(response_rows) if response_rows else None,
                    'scope':'synthetic deployed opportunity sample, not a calibrated reference grade or extra game bonus'}
            metadata['combined_offense']={'version':experiment.offense.revision,'spatial_profiles':coupled['spatial'][team['team_id']],
                'anchor_position_m':coupled['positions'][team['team_id']],'controlled_support':{'assist_credit_probability':coupled['spec'].assist_credit_probability,'offensive_rebound_probability':coupled['spec'].offensive_rebound_probability,'attribution':'equal minutes exposure, no inferred passing/rebound talent'},'status':'partial_coupled_shooting_finish_chain_not_calibrated'}
            metadata['legacy_dependencies']=['availability and regulation minutes']
            metadata['unwired']=['app actions','complete creation/passing/routes','new POA/help/perimeter defense','complete C31/C32/R18','live economics/development','plus-minus','foul-out substitutions']
    if creation:
        for team in team_lines:
            team['interior_experiment']['creation_passing']={'revision':creation['spec'].revision,'status':'drive_finish_kick_supplied_roll_lob_experiment',
                'removed_controls':['generic turnover roll','gifted paint access','fixed pass quality','fixed POA/help arrival','random assist credit','automatic rim-avoidance outlet'],
                'remaining_controls':['touch assignment','screen displacement','roll route/window','defensive matchups','rebound support','clock/reset setup','unsupported actions']}
            if 'screens' in creation:
                team['interior_experiment']['creation_passing']['status']='drive_finish_kick_screen_derived_roll_slip_experiment'
                team['interior_experiment']['creation_passing']['remaining_controls']=['touch assignment','call/initial geometry','coverage policy','route endpoint','rebound support','clock/reset setup','unsupported actions']
                team['interior_experiment']['screen_navigation']={'revision':creation['screens']['spec'].revision,'status':'bounded_on_ball_screen_roll_slip_default_off',
                    'remaining_controls':['call/initial geometry','stay/show coverage policy','route endpoint','touch exposure','clock/reset/rebound policy','one helper','unsupported actions'],
                    'removed_controls':['screen displacement','roll deadline','roll defender gap'],'screen_reuse':'initial action only; no rescreen after reset or rebound'}
                from .screen_navigation import PopScreenExperiment
                if isinstance(creation['screens']['spec'],PopScreenExperiment):
                    team['interior_experiment']['creation_passing']['status']='screen_roll_slip_pop_shared_outcomes_default_off'
                    team['interior_experiment']['screen_navigation'].update(status='bounded_screen_to_pop_default_off',
                        route_policy='screen_to_pop_v1',timing_policy=creation['screens']['spec'].timing_policy,
                        pop_pass_context='F06 same-side drive exit; F01 return and cross-court routes unsupported',
                        new_dependency='S26 screener relocation; explicit completion when unknown')
            if getattr(creation['spec'],'receipt_policy',None):
                team['interior_experiment']['creation_passing'].update(receipt_policy=creation['spec'].receipt_policy,
                    receipt_diagnostics='planned delivery and actual secured catch distinct; recovered reset transfers to receiver at actual position',
                    recovery_assumptions=asdict(creation['spec'].recovery))
                if getattr(creation['spec'],'projection_backend','detailed_python_v1')!='detailed_python_v1' or getattr(creation['spec'],'bearing_policy','legacy_bearing_v1')!='legacy_bearing_v1':
                    team['interior_experiment']['creation_passing'].update(projection_backend=creation['spec'].projection_backend,
                        bearing_policy=creation['spec'].bearing_policy,
                        geometry_provider_revision=getattr(creation['spec'].geometry_provider,'revision',None))
    result=SimGameResult(id=stable_id('interior_experiment',game_id,mode,seed,evaluation_revision),game_id=game_id,mode=mode,seed=seed,
        home_team_id=home_team['id'],away_team_id=away_team['id'],home_score=team_lines[0]['points'],away_score=team_lines[1]['points'],
        possessions=total_possessions,player_lines=list(lines[home_team['id']].values())+list(lines[away_team['id']].values()),team_lines=team_lines,
        source_ids=[FORMULA_VERSION],notes='Isolated default-off interior experiment. Scoring sums resolved attacks; R18 partial. No league calibration; no app-action activation.')
    validate_accounting(result)
    return result


def validate_accounting(result):
    for team in result.team_lines:
        players=[r for r in result.player_lines if r['team_id']==team['team_id']]
        opponent=next(t for t in result.team_lines if t['team_id']!=team['team_id'])
        events=team['interior_experiment']['offense_attack_ledger']
        for key in STATS:
            assert team[key]==sum(r[key] for r in players),(key,team)
        assert team['points']==2*team['fgm']+team['fg3m']+team['ftm']
        assert team['fg3m']<=team['fg3a']<=team['fga'] and team['fgm']-team['fg3m']<=team['fga']-team['fg3a']
        assert team['ftm']<=team['fta'] and team['fgm']<=team['fga']
        assert team['assists']<=team['fgm'] and team['blocks']<=opponent['fga']-opponent['fgm']
        assert team['steals']<=opponent['turnovers']
        misses=sum(bool(e.get('reboundable_miss')) for e in events)
        assert misses==team['offensive_rebounds']+opponent['defensive_rebounds']
        assert team['fga']-team['fgm']+sum(e['outcome']=='shooting_foul' and e.get('reboundable_miss',False) for e in events)==misses
        assert len({e['possession'] for e in events})==team['possessions']
        assert sum('block_by' in e for e in events)==opponent['blocks']
        opponent_events=opponent['interior_experiment']['offense_attack_ledger']
        assert sum('foul_by' in e for e in events)+sum('offensive_foul_by' in e for e in opponent_events)==opponent['personal_fouls']
        assert sum(e.get('points',0) for e in events)==team['points']
        # Ledger ownership, including creation's replacement loss causes.
        loss_outcomes={'turnover','reception_turnover','handling_loss','inaccurate_delivery','late_delivery','failed_catch','shot_clock_turnover','illegal_screen','waiting_loss',
            'pass_out_of_bounds','pass_grounded','pass_unreachable','recovery_defended'}
        assert sum(e['outcome'] in loss_outcomes for e in events)==team['turnovers']
        assert sum(e['outcome']=='made_fg' for e in events)==team['fgm']
        assert sum(e['outcome'] in {'made_fg','missed_fg','block'} for e in events)==team['fga']
        assert sum(e.get('fta',0) for e in events)==team['fta']
        assert sum(e.get('ftm',0) for e in events)==team['ftm']
        assert sum('assist_by' in e for e in events)==team['assists']
        assert sum('steal_by' in e for e in events)==opponent['steals']
        for event in events:
            if 'assist_by' in event:
                assert event['outcome']=='made_fg' and event['assist_by']!=event['shooter_id']
            if 'steal_by' in event:assert event['outcome'] in loss_outcomes
            if 'offensive_foul_by' in event:
                assert event['outcome']=='illegal_screen' and event['offensive_foul_by']==event['turnover_by']
                assert event.get('points',0)==0 and not any(k in event for k in ('fta','foul_by','steal_by','rebound_by','assist_by'))
        if 'creation_passing' in team['interior_experiment']:
            for player in players:
                pid=player['player_id']
                assert sum(e.get('turnover_by')==pid for e in events)==player['turnovers']
                assert sum(e.get('assist_by')==pid for e in events)==player['assists']
            for event in events:
                assert not event['creation_chain']['generic_loss_roll_used']
                if 'assist_by' in event:
                    assert event['assist_by']==event['passer_id'] and event['creation_chain']['assist_eligible']
