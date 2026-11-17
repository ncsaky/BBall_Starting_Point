"""Short disposable real-action free-agency replay; no season simulation."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save import create_league_save, load_save, set_save_date_phase, write_save
from verify_simulation_consistency import business_state, digest, differences

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', default='17,29')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--through-cutdown', action='store_true')
    parser.add_argument('--skip-unplanned', action='store_true')
    parser.add_argument('--modes', default='daily,bulk')
    parser.add_argument('--waiver-days', type=int, default=0)
    args = parser.parse_args()
    canonical = load_app_canonical(ROOT)
    report = []
    for seed in map(int, args.seeds.split(',')):
        snapshots = {}
        case = {'seed': seed, 'runs': {}}
        with TemporaryDirectory(prefix='nba-guarantee-replay-') as folder:
            base = Path(folder)/'base.json'
            create_league_save(ROOT, canonical, 'TOR', base, seed=seed)
            initial = load_save(base)
            set_save_date_phase(initial, '2027-07-01')
            modes = args.modes.split(',') + ([] if args.skip_unplanned else ['unplanned'])
            for mode in modes:
                path = Path(folder)/(mode+'.json')
                write_save(path, deepcopy(initial))
                def act(mode):
                    return dispatch_app_action('advance_free_agency', {'save_path': str(path), 'mode': mode, 'seed': seed},
                                               root=ROOT, save_dir=folder, canonical=canonical)
                started = time.perf_counter()
                if mode == 'daily':
                    for _ in range(5): act('day')
                    act('end')
                elif mode == 'unplanned':
                    with patch('nba_gm_data.contract_protection.roster_signing_plan', return_value={'ok': True, 'reason': 'comparison_only'}):
                        act('end')
                else:
                    act('end')
                if args.through_cutdown:
                    from nba_gm_data.save import advance_lifecycle_to, refresh_roster_cutdowns
                    saved = load_save(path)
                    advance_lifecycle_to(canonical, saved, '2027-10-01', seed, ROOT)
                    refresh_roster_cutdowns(canonical, saved)
                    if args.waiver_days:
                        from datetime import date, timedelta
                        through = (date(2027, 10, 1) + timedelta(days=args.waiver_days)).isoformat()
                        advance_lifecycle_to(canonical, saved, through, seed, ROOT)
                    write_save(path, saved)
                saved = load_save(path, include_history=True)
                snapshots[mode] = business_state(saved)
                offers = saved.get('free_agent_offers', [])
                row = {'seconds': round(time.perf_counter()-started, 2), 'date': saved['state']['current_date'],
                       'offers': len(offers), 'statuses': dict(Counter(o['status'] for o in offers)),
                       'transactions': dict(Counter(t.get('transaction_type') for t in saved.get('transaction_logs', []))),
                       'obligations': len(saved.get('waived_salary_obligations', [])),
                       'roster_space_sales': sum(any('Roster-space opportunity credit:' in str(e.get('notes') or '')
                                                     for e in log.get('evaluations', []))
                                                for log in saved.get('transaction_logs', []) if log.get('transaction_type') == 'trade'),
                       'roster_space_details': [
                           {'proposal_id': item.get('proposal_id'), 'date': item.get('date'), 'teams': item.get('teams'),
                            'assets': item.get('assets'), 'intent': item.get('free_agency_context'),
                            'evaluations': item.get('evaluations')}
                           for item in saved.get('transaction_logs', [])
                           if item.get('free_agency_context', {}).get('kind') == 'roster_space_sale'],
                       'target_pursuits': saved.get('free_agency_state', {}).get('roster_space_pursuits', {}),
                       'pursuit_offers': [o for o in offers if any(
                           o.get('team_id') == tid and o.get('player_id') == target.get('player_id')
                           for tid, target in saved.get('free_agency_state', {}).get('roster_space_pursuits', {}).items())],
                       'waivers': [{'player': r['player_name'], 'status': r['status'], 'from': r['team_id'],
                                    'claimed_by': r.get('claimed_by_team_id'), 'clearance_date': r['clearance_date']}
                                   for r in saved.get('waiver_wire', [])],
                       'window_phases': dict(Counter(p.get('window_phase') for p in saved.get('team_plans', {}).values())),
                       'core_sizes': dict(Counter(len(p.get('core_ids') or []) for p in saved.get('team_plans', {}).values())),
                       'digest': digest(snapshots[mode])}
                case['runs'][mode] = row
                print(json.dumps({'seed': seed, 'mode': mode, **row}), flush=True)
            case['equal'] = snapshots['daily'] == snapshots['bulk'] if {'daily','bulk'} <= snapshots.keys() else None
            case['differences'] = differences(snapshots['daily'], snapshots['bulk']) if case['equal'] is not None else []
            report.append(case)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2)+'\n')
        if case['equal'] is False:
            print(json.dumps(case['differences']), flush=True)
            return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
