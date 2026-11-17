"""Reproduce accepted failures before any proposed engine correction."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random

from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from nba_gm_data.interior_defense import FORMULA_VERSION
from nba_gm_data.creation_passing import resolve_drive,prepare_drive_decision
from experiments.pick_and_pop.fixtures import pool,research_pool,fixture,ROOT,IDS

BASE=ROOT/'output/mixed-pop-validation-2026-11-16'
REFERENCE=BASE/'reference'


def digest(value):return hashlib.sha256(json.dumps(to_plain(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def plain(value):return json.loads(json.dumps(to_plain(value)))


def reproduce():
    rows=[];kernels=[]
    for path in sorted(REFERENCE.glob('pop-accounting-*.json')):
        old=json.loads(path.read_text());trial='final_research' if 'final_research' in path.name else 'original_controls'
        p=research_pool() if trial=='final_research' else pool();state,context,config=fixture(p)
        now=sim.sim_game_with_context(context,old['game_id'],old['mode'],old['seed'],interior_experiment=config)
        assert plain(now)==old,path.name
        kernels.append({'path':path.name,'full_accepted_result_equal':True,'sha256':digest(now)})
        for team in old['team_lines']:
            for event in team['interior_experiment']['offense_attack_ledger']:
                r=event.get('creation_chain',{})
                if r.get('choice')!='pop':continue
                domain=f"{old['seed']}:{old['game_id']}:{old['mode']}:{FORMULA_VERSION}:{team['team_id']}:{event['possession']}:{event['continuation']}"
                rng=random.Random(domain);draws=[rng.random() for _ in range(48)]
                action=resolve_drive(state,IDS['curry'],'response_a','response_b',draws,r['remaining_before_s'],screen_allowed=event['continuation']==0)
                assert plain(action['record'])==r,(path.name,event['possession'])
                decision=prepare_drive_decision(state,IDS['curry'],'response_a','response_b',draws,r['remaining_before_s'],screen_allowed=event['continuation']==0)
                option=decision['options']['pop'];frame=decision['frame'];screen=r['screen_action'];passed=r.get('pass',{});projection=r['choice_projection']['candidates']['pop']
                shot_mass=sum(projection['branches'].get(k,0) for k in ('shooting_foul','block','made_fg','missed_fg'))
                rows.append({'trial':trial,'seed':old['seed'],'mode':old['mode'],'rng_domain':domain,'possession':event['possession'],
                    'continuation':event['continuation'],'outcome':event['outcome'],'record_reproduced_exactly':True,
                    'called_intent':screen['effective_intent'],'screen_read':screen['recognized'],'pass_read':r['noticed_options']['pop'],
                    'choice_probability':r['choice_projection']['effective_choice_probabilities']['pop'],'draws':{str(k):draws[k] for k in (15,31,33,34,39,40,43)},
                    'wait':r.get('wait'),'drive_exit_m':frame['ball'],'target_m':option['target'],'pop_destination_m':screen['pop_end'],
                    'handler_decision_s':frame['elapsed'],'launch_s':frame['elapsed']+option['wait_s'],
                    'flight_s':passed.get('flight_s'),'receiving_interval_s':[screen['window_start_s'],screen['window_end_s']],
                    'intended_catch_s':frame['elapsed']+option['wait_s']+option['delivery']['flight_s']+.05,
                    'delivery_error_m':passed.get('error_m'),'delivery_radius_m':passed.get('window_radius_m'),
                    'error_scale_m':passed.get('error_scale_m'),'accuracy_probability':passed.get('accuracy_probability'),
                    'delivery_quality':passed.get('quality'),'accurate':passed.get('accurate'),
                    'catch_probability':action.get('plan',{}).get('reception'),'catch_gate_reached':action['kind']=='shot',
                    'catch_failed':event['outcome']=='failed_catch','shot_stage_reached':False,
                    'closeout_arrival_after_catch_s':r.get('derived_primary_arrival_s'),
                    'closeout_note':'unreached after delivery loss' if action['kind']=='turnover' else 'prepared shot/closeout exists, but catch gate failed before shot sampling',
                    'elapsed_to_failure_or_plan_s':action['elapsed_s'],'clock_remaining_after_s':event['clock_remaining_s'],
                    'projected_branches':projection['branches'],'projected_shot_stage_probability':shot_mass,
                    'record':r})
    assert len(rows)==10 and len({r['rng_domain'] for r in rows})==5
    summaries=[]
    for trial in ('original_controls','final_research'):
        selected=[r for r in rows if r['trial']==trial];branches=set().union(*(r['projected_branches'] for r in selected))
        summaries.append({'trial':trial,'selected_attempts':len(selected),'unique_domains':len({r['rng_domain'] for r in selected}),
            'observed_outcomes':dict(Counter(r['outcome'] for r in selected)),
            'sum_predicted_counts':{k:sum(r['projected_branches'].get(k,0) for r in selected) for k in sorted(branches)},
            'expected_shot_stage_count':sum(r['projected_shot_stage_probability'] for r in selected),
            'probability_no_shot_stage_given_selected_states':math.prod(1-r['projected_shot_stage_probability'] for r in selected),
            'scope':'five independent attempt RNG domains conditional on observed stages within this trial; original/research share draws and must not be multiplied as ten independent failures'})
    return {'kernels':kernels,'attempts':rows,'summaries':summaries,
        'runtime_change_required_by_ten_attempts':False,
        'semantics':'inaccurate delivery is a hard turnover; accurate placement has a separate quality/S14 catch gate. Recoverable bad passes/loose-ball/reset are not modeled; do not infer calibrated real NBA rates.'}
