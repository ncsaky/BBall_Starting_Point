"""One bounded real-action regular season, not a multi-year soak."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from ten_season_soak import SoakRunner
from league_health_audit import select_advance, regular_complete
from nba_gm_data.save import set_save_date_phase, write_save
from nba_gm_data.history_store import load_history_records

ROOT = Path(__file__).resolve().parents[1]


def season_summary(saved, save_path=None):
    logs = {r['id']: r for r in (load_history_records(save_path, saved, 'transaction_logs') if save_path else [])}
    logs.update({r['id']: r for r in saved.get('transaction_logs', [])})
    trades = [r for r in logs.values() if r.get('transaction_type') == 'trade']
    offers = saved.get('user_trade_offers', [])
    return {'date': saved['state']['current_date'],
            'games': sum(r.get('wins', 0) for r in saved.get('team_records', {}).values()),
            'trade_count': len(trades), 'monthly_trades': dict(sorted(Counter(r['date'][:7] for r in trades).items())),
            'deadline_day': sum(r['date'] == '2027-02-05' for r in trades),
            'deadline_week': sum('2027-01-30' <= r['date'] <= '2027-02-05' for r in trades),
            'user_offers': len(offers),
            'monthly_user_offers': dict(sorted(Counter(str((r.get('offer_context') or {}).get('created_date') or (r.get('proposal') or {}).get('date') or '')[:7] for r in offers).items())),
            'offer_statuses': dict(Counter((r.get('offer_context') or {}).get('status') for r in offers))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=29)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=900)
    args = parser.parse_args()
    out = args.output.resolve()
    if (out / 'trade-season.json').exists() or out == ROOT / 'saves' or ROOT / 'saves' in out.parents:
        raise ValueError('Use a new audit-owned output directory outside playable saves.')
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(out), seed=args.seed, team='GSW'))
    created = runner.action('create_save', team='GSW', seed=args.seed, save_name='trade_season')
    runner.payload['save_path'] = created['save_path']
    saved = runner.load()
    set_save_date_phase(saved, '2026-10-01')
    write_save(created['save_path'], saved)
    started = time.monotonic()
    report = {'seed': args.seed, 'policy': 'Hands-off GSW, no user trades; required cutdowns and staff decisions only.',
              'source_hashes': {name: hashlib.sha256((ROOT / 'src/nba_gm_data' / name).read_bytes()).hexdigest()
                                for name in ('save.py', 'trade_calendar.py', 'roster_space.py')}, 'calls': []}
    while runner.load()['state']['current_date'] < '2027-04-12':
        if time.monotonic() - started > args.seconds:
            report['status'] = 'bounded_stop'
            break
        runner.resolve_user_staff_retention()
        runner.resolve_user_roster_cutdown()
        saved = runner.load()
        before = saved['state']['current_date']
        payload = select_advance(saved, 31)
        payload['to_date'] = min(payload['to_date'], '2027-04-12')
        result = runner.action('advance_save', save_path=runner.payload['save_path'], **payload, seed=args.seed)
        saved = runner.load()
        reached = saved['state']['current_date']
        if reached <= before:
            raise RuntimeError(f'Unexpected decision stop: {result}')
        row = {'from': before, 'date': reached, 'status': result.get('status'),
               'seconds': round(time.monotonic() - started, 2)}
        report['calls'].append(row)
        print(json.dumps(row), flush=True)
    else:
        regular_complete(runner.load())
        report['status'] = 'completed_regular_season'
    saved = runner.load()
    report.update(**season_summary(saved, runner.payload['save_path']), seconds=round(time.monotonic() - started, 2))
    (out / 'trade-season.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
