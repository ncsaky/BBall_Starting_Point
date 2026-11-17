"""Replay one saved July market through real daily and bulk app actions."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save import load_save
from nba_gm_data.save_recovery import create_export, restore_export
from verify_simulation_consistency import business_state, differences, digest
from verify_trade_year import engine_fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists():
        raise ValueError('Choose a new disposable output directory.')
    root = Path(__file__).resolve().parents[1]
    archive = create_export(args.snapshot)
    baseline = load_save(args.snapshot)
    if baseline['state']['phase'] != 'free_agency' or baseline['free_agency_state']['day'] != 1:
        raise ValueError('Use a preserved first-day summer checkpoint.')
    seed, team = baseline['meta']['seed'], baseline['meta']['user_team_id']
    canonical = load_app_canonical(root)
    team = next(t['abbrev'] for t in canonical['teams'] if t['id'] == team)
    args.output.mkdir(parents=True)
    fingerprints = engine_fingerprint()
    report, snapshots = {'source': str(args.snapshot), 'seed': seed, 'runs': {}}, {}
    for mode in ('daily', 'bulk'):
        path = args.output/f'{mode}.json'
        restore_export(path, archive)
        calls, started = [], time.monotonic()
        for _ in range(10):
            saved = load_save(path)
            if saved['state']['phase'] != 'free_agency':
                break
            step = 'end' if mode == 'bulk' or saved['free_agency_state']['status'] == 'completed' else 'day'
            result = dispatch_app_action('advance_free_agency', {'save_path': str(path), 'team': team,
                'seed': seed, 'mode': step}, root=root, save_dir=args.output, canonical=canonical)
            calls.append({'date': saved['state']['current_date'], 'mode': step, 'status': result['status']})
        else:
            raise AssertionError('Summer failed to finish within its decision window.')
        saved = load_save(path, include_history=True)
        snapshots[mode] = business_state(saved)
        logs = [r for r in saved.get('transaction_logs', []) if r.get('transaction_type') == 'trade'
                and r['date'].startswith('2027-07')]
        report['runs'][mode] = {'date': saved['state']['current_date'], 'seconds': round(time.monotonic()-started, 3),
            'calls': calls, 'july_trades': len(logs), 'by_date': dict(Counter(r['date'] for r in logs)),
            'general_trades': saved['free_agency_state'].get('ai_general_trade_count', 0),
            'business_digest': digest(snapshots[mode])}
        print(json.dumps({'mode': mode, **report['runs'][mode]}), flush=True)
    report['equal'] = snapshots['daily'] == snapshots['bulk']
    report['differences'] = differences(snapshots['daily'], snapshots['bulk'])
    report['engine_unchanged'] = fingerprints == engine_fingerprint()
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'runs'}), flush=True)
    return 0 if report['equal'] and report['engine_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
