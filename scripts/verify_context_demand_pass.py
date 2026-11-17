"""Sequential attribution, regression and endpoint consistency after timing."""
import os
from pathlib import Path
import subprocess
import sys

BASE = Path('output/context-demand-pass')
env = {**os.environ, 'PYTHONPATH': 'src:tests:scripts'}
folder = BASE/'attribution-after'
if not (folder/'context-builds.json').exists():
    assert not folder.exists(), folder
    print('Attributing after', flush=True)
    with (BASE/'attribution-after.log').open('w') as log:
        subprocess.run([sys.executable, 'scripts/diagnose_context_builds.py', '--save',
            'output/pick-investment-2026-10-28/stable17/saves/trade_year.json', '--target','2027-02-04',
            '--output',str(folder)], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
modules = '''test_context_demand_performance test_roster_forecast_performance test_salary_search_stage_b
test_trade_package_search test_market_review_performance test_multi_team_trades test_trade_presentation
test_trade_search_performance test_trade_payloads test_trade_pick_terms test_trade_wants test_trade_market_analysis
test_trade_calendar test_trade_impact_stress test_draft_sources test_roster_space test_pick_investment
test_trade_roster test_trade_roles test_contract_protection test_team_planning test_trade_salary_application
test_trade_salary_boundaries test_pick_horizon test_trade_discretion test_premium_trade_returns
test_summer_trade_reviews test_simulation_progress test_simulation_consistency test_simulation_memory
test_roster_retention test_user_rotation_roster test_save_recovery'''.split()
print('Running focused regressions', flush=True)
with (BASE/'regression.txt').open('w') as log:
    subprocess.run([sys.executable,'-m','unittest',*modules], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
print('Daily/bulk and midpoint reload', flush=True)
subprocess.run([sys.executable,'scripts/verify_market_review_checkpoints.py','--output',str(BASE/'checkpoints'),
                '--bulk-reference',str(BASE/'after-month17-1')], env=env, check=True)
subprocess.run([sys.executable,'scripts/summarize_context_demand_speed.py'], env=env, check=True)
