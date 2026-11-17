"""Separately attributed final research trial after the bounded original run.

PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_mixed_pop_research_comparison.py
"""
import json
import math
from pathlib import Path
import statistics
import time

from experiments.mixed_pop_validation.fixtures import build_pool,final_research_pool,fixture,ACTORS,BASE
from experiments.mixed_pop_validation import sampling
from experiments.mixed_pop_validation.scenarios import export_inputs
from scripts.run_mixed_pop_validation import write,audit


def final_kernel_checks(out,p):
    from nba_gm_data.interior_game import validate_accounting
    from nba_gm_data.schema import to_plain
    from experiments.expanded_cohort_performance.checks import traced
    from experiments.mixed_pop_validation.diagnosis import digest
    rows=[]
    for actor in ACTORS[:-1]:
        _,c,x=fixture(p,actor);a,ta=traced(c,x,17);b,tb=traced(c,x,17)
        assert to_plain(a)==to_plain(b) and ta==tb;validate_accounting(a)
        write(out,f'final-research-kernel-{actor}-17.json',to_plain(a));rows.append({'actor':actor,'seed':17,'mode':'replay-real-minutes',
            'accounting_and_determinism_passed':True,'actual_possessions_per_side':a.possessions,'result_sha256':digest(a),'rng_domains':ta})
    write(out,'separate-final-research-kernel-accounting.json',rows)


def main():
    out=BASE/'verified';budget=json.loads((out/'natural-budget-consumption.json').read_text());before=build_pool();after=final_research_pool(before)
    if budget['supplied_possessions_including_interrupted_work']+4096>60000:raise ValueError('Insufficient prespecified natural-trial budget')
    if budget['event_attempts_including_interrupted_work']+4096*20>180000:raise ValueError('Insufficient conservative event budget')
    write(out,'separate-final-research-inputs.json',{'layers':export_inputs(after),'new_evidence_updates':after['research_updates'],'source_packet_sha256':after['final_packet_sha256']})
    write(out,'separate-final-research-compile-audit.json',audit(after))
    rows=[];events=0;started=time.perf_counter()
    for actor in ACTORS[:-1]:
        acc=[];results=[]
        for p in (before,after):
            s,_,_=fixture(p,actor);a=sampling.accumulator();sampling.add_trials(s,a,0,256);acc.append(a);results.append(sampling.finish(a));events+=a['event_count']
        differences=[b-a for a,b in zip(acc[0]['points'],acc[1]['points'],strict=True)];mean=statistics.mean(differences);se=statistics.stdev(differences)/math.sqrt(len(differences))
        rows.append({'actor':actor,'context':'reference_show','before':results[0],'after':results[1],
            'paired_mean_possession_point_difference':mean,'nominal_paired_MC95':[mean-1.96*se,mean+1.96*se],
            'source_updates':[r for r in after['research_updates'] if r['actor']==actor],
            'scope':'same512 supplied initial-creator possessions and draws per leg; independent new evidence replaces old unknown controls; choice/opportunity changes confound any post-selection accuracy-only comparison'})
    wall=time.perf_counter()-started
    assert budget['wall_s_including_interruption']+wall<180
    assert all(r['before']['truncated']==r['after']['truncated']==0 for r in rows)
    write(out,'separate-final-research-paired-results.json',rows)
    write(out,'optional-research-budget-consumption.json',{'additional_supplied_possessions':4096,'additional_event_attempts':events,'wall_s':wall,
        'aggregate_possessions_including_interruption':budget['supplied_possessions_including_interrupted_work']+4096,
        'aggregate_events_including_interruption':budget['event_attempts_including_interrupted_work']+events,
        'aggregate_natural_wall_s_including_interruption':budget['wall_s_including_interruption']+wall,'original_caps_preserved':True})
    summary=json.loads((out/'summary.json').read_text());summary.update(final_research_integration='Finished versioned packet pinned; all9 independent unknown-cell additions tested in separate4096-possession paired comparison',
        final_research_packet_sha256=after['final_packet_sha256'],new_tests=16,total_tests=273,final_test_log='tests-final.txt')
    write(out,'summary.json',summary)
    final_kernel_checks(out,after)
    print('final research separate paired comparison complete:',4096,'possessions',events,'events',round(wall,3),'seconds')


if __name__=='__main__':main()
