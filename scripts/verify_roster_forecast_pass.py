"""Run attribution, regressions and checkpoints sequentially after wall samples."""
import os
from pathlib import Path
import subprocess
import sys

BASE = Path('output/roster-forecast-pass')
source = 'output/pick-investment-2026-10-28/stable17/saves/trade_year.json'
for version in ('before', 'after'):
    folder = BASE / f'profile-final-{version}'
    if (folder / 'roster-diagnostics.json').exists():
        continue
    assert not folder.exists(), folder
    ref = BASE / 'reference'
    env = {**os.environ, 'PYTHONPATH': f'{ref}/src:scripts' if version == 'before' else 'src:scripts'}
    print('Profiling ' + version, flush=True)
    with (BASE / f'profile-final-{version}.log').open('w') as log:
        subprocess.run([sys.executable, 'scripts/diagnose_roster_forecasts.py', '--save', source,
                        '--target', '2027-02-04', '--output', str(folder), '--profile'],
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
modules = '''test_roster_forecast_performance test_salary_search_stage_b test_trade_package_search
test_market_review_performance test_multi_team_trades test_trade_presentation test_trade_search_performance
test_trade_payloads test_trade_pick_terms test_trade_wants test_trade_market_analysis test_trade_calendar
test_trade_impact_stress test_draft_sources test_roster_space test_pick_investment test_trade_roster
test_trade_roles test_contract_protection test_team_planning test_trade_salary_application test_trade_salary_boundaries
test_pick_horizon test_trade_discretion test_premium_trade_returns test_summer_trade_reviews
test_simulation_progress test_simulation_consistency test_simulation_memory test_roster_retention
test_user_rotation_roster'''.split()
env = {**os.environ, 'PYTHONPATH': 'src:tests:scripts'}
print('Running full focused regressions', flush=True)
with (BASE / 'regression.txt').open('w') as log:
    subprocess.run([sys.executable, '-m', 'unittest', *modules], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
for version in ('before', 'after'):
    folder = BASE / f'memory-{version}'
    if (folder / 'memory.json').exists():
        continue
    assert not folder.exists(), folder
    ref = BASE / 'reference'
    memory_env = {**os.environ, 'PYTHONPATH': f'{ref}/src:scripts' if version == 'before' else 'src:scripts'}
    print('Measuring unprofiled RSS ' + version, flush=True)
    with (BASE / f'memory-{version}.log').open('w') as log:
        subprocess.run([sys.executable, 'scripts/measure_roster_forecast_memory.py', '--save', source,
                        '--target', '2027-02-04', '--output', str(folder)], env=memory_env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
print('Verifying daily/bulk and midpoint reload', flush=True)
subprocess.run([sys.executable, 'scripts/verify_market_review_checkpoints.py', '--output', str(BASE / 'checkpoints'),
                '--bulk-reference', str(BASE / 'after-month17-1')], env=env, check=True)
subprocess.run([sys.executable, 'scripts/summarize_roster_forecast_speed.py'], env=env, check=True)
