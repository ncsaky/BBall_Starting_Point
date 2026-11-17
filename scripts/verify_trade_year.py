"""One real-action calendar-year trade census, including draft and summer."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from ten_season_soak import SoakRunner
from league_health_audit import select_advance
from nba_gm_data.save import set_save_date_phase, write_save, postseason_exit_required
from nba_gm_data.history_store import load_history_records

ROOT = Path(__file__).resolve().parents[1]


def engine_fingerprint():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'src/nba_gm_data').glob('*.py'))}


def census(saved, save_path=None, previous=None):
    logs = {r['id']: r for r in (load_history_records(save_path, saved, 'transaction_logs') if save_path else [])}
    logs.update({r['id']: r for r in saved.get('transaction_logs', [])})
    trades = [r for r in logs.values() if r.get('transaction_type') == 'trade']
    offers = {(r.get('proposal') or {}).get('id') or r.get('id'): r
              for r in (previous or {}).get('all_offers', [])}
    offers.update({(r.get('proposal') or {}).get('id') or r.get('id'): r for r in saved.get('user_trade_offers', [])})
    rows = []
    for trade in trades:
        assets = trade.get('assets') or {}
        from nba_gm_data.transactions import trade_assets
        kinds = [a.get('kind') for a in trade_assets(assets)]
        rows.append({'date': trade['date'], 'id': trade.get('id'),
                     'kind': 'player_involved' if 'player' in kinds else 'picks_only',
                     'teams': trade.get('teams'), 'asset_count': len(kinds)})
    return {'date': saved['state']['current_date'], 'all_trades': sorted(rows, key=lambda r: (r['date'], r['id'])),
            'all_offers': list(offers.values()),
            'monthly_trades': dict(sorted(Counter(r['date'][:7] for r in rows).items())),
            'monthly_player_trades': dict(sorted(Counter(r['date'][:7] for r in rows if r['kind'] == 'player_involved').items())),
            'monthly_pick_trades': dict(sorted(Counter(r['date'][:7] for r in rows if r['kind'] == 'picks_only').items())),
            'monthly_offers': dict(sorted(Counter(str((r.get('offer_context') or {}).get('created_date') or '')[:7] for r in offers.values()).items())),
            'release_counts': dict(Counter(r['transaction_type'] for r in logs.values()
                                          if r.get('transaction_type') in {'buyout_agreement', 'salary_stretch', 'waiver_claim'}))}


def run(args):
    out = args.output.resolve()
    if (out.exists() and not args.resume and not getattr(args, 'observer_directory_created', False)) or ROOT/'saves' == out or ROOT/'saves' in out.parents:
        raise ValueError('Choose a NEW disposable output directory.')
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(out), seed=args.seed, team='GSW'))
    hashes = {p: hashlib.sha256((ROOT/'src/nba_gm_data'/p).read_bytes()).hexdigest()
              for p in ('save.py', 'transactions.py', 'play.py', 'waivers.py', 'release_planning.py', 'trade_calendar.py')}
    if args.resume:
        report = json.loads((out/'trade-year.json').read_text())
        if report['seed'] != args.seed:
            raise ValueError('Resume must use the same seed.')
        runner.payload['save_path'] = str(out/'saves/trade_year.json')
        report.setdefault('resumes', []).append({'date': runner.load()['state']['current_date'], 'source_hashes': hashes})
    else:
        if args.from_save:
            from nba_gm_data.save_recovery import create_export, restore_export
            target = out/'saves/trade_year.json'
            restore_export(target, create_export(args.from_save))
            runner.payload['save_path'] = str(target)
        else:
            created = runner.action('create_save', team='GSW', seed=args.seed, save_name='trade_year')
            runner.payload['save_path'] = created['save_path']
            saved = runner.load()
            set_save_date_phase(saved, '2026-10-01')
            write_save(created['save_path'], saved)
        report = {'seed': args.seed, 'calls': [], 'source_hashes': hashes,
                  'engine_fingerprint': engine_fingerprint(),
                  'policy': 'Required cutdowns/staff retained; user drafts automatically, ignores all trade offers, no voluntary user signings.'}
    started = time.monotonic()-float(report.get('seconds') or 0)
    while runner.load()['state']['current_date'] < args.end_date:
        if time.monotonic()-started > args.seconds:
            report['status'] = 'bounded_stop'
            break
        runner.resolve_user_staff_retention()
        runner.resolve_user_roster_cutdown()
        saved = runner.load()
        stamp, phase = saved['state']['current_date'], saved['state']['phase']
        if postseason_exit_required(saved):
            result = runner.action('advance_save', save_path=runner.payload['save_path'], postseason_exit=True, seed=args.seed)
        elif phase == 'draft_lottery':
            runner.action('draft_reveal_lottery', save_path=runner.payload['save_path'], team='GSW', seed=args.seed)
            result = runner.action('advance_save', save_path=runner.payload['save_path'], draft_enter=True, seed=args.seed)
        elif phase in ('play_in', 'playoffs') and saved.get('playoff_state', {}).get('status') != 'completed':
            result = runner.action('simulate_playoff_all', save_path=runner.payload['save_path'], seed=args.seed)
        elif phase == 'draft' and saved.get('draft_state', {}).get('status') != 'completed':
            result = runner.action('draft_sim_all', save_path=runner.payload['save_path'], team='GSW', seed=args.seed)
        elif phase == 're_signing':
            result = runner.action('advance_re_signing', save_path=runner.payload['save_path'], team='GSW', mode='open_market', seed=args.seed)
        elif phase == 'free_agency' and saved.get('free_agency_state', {}).get('status') != 'completed':
            runner.snapshot_save('summer_before.json')
            result = runner.action('advance_free_agency', save_path=runner.payload['save_path'], team='GSW', mode='end', seed=args.seed)
        elif phase in ('regular_season', 'preseason'):
            payload = select_advance(saved, 31)
            payload['to_date'] = min(payload['to_date'], args.end_date)
            result = runner.action('advance_save', save_path=runner.payload['save_path'], **payload, seed=args.seed)
        else:
            result = runner.action('advance_save', save_path=runner.payload['save_path'], next_event=True, seed=args.seed)
        after = runner.load()
        row = {'from': stamp, 'phase': phase, 'date': after['state']['current_date'],
               'status': result.get('status'), 'seconds': round(time.monotonic()-started, 2)}
        report['calls'].append(row)
        report.setdefault('team_plan_checkpoints', []).append({'date': after['state']['current_date'],
            'phase': after['state']['phase'], 'plans': after.get('team_plans', {})})
        report.update(census(after, runner.payload['save_path'], report), seconds=row['seconds'])
        (out/'trade-year.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(row), flush=True)
        if len(report['calls']) > 150:
            raise RuntimeError('Unexpected repeated decision stop; inspect the disposable report.')
    else:
        report['status'] = 'completed_calendar_year' if args.end_date.endswith('12-31') else 'completed_interval'
    report.update(census(runner.load(), runner.payload['save_path'], report))
    report['engine_unchanged'] = report.get('engine_fingerprint') == engine_fingerprint()
    (out/'trade-year.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in {
        'calls', 'all_trades', 'all_offers', 'source_hashes', 'engine_fingerprint', 'team_plan_checkpoints'}}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=29)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=2400)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--from-save', type=Path)
    parser.add_argument('--end-date', default='2027-12-31')
    parser.add_argument('--observe-market', action='store_true')
    parser.add_argument('--capture-player', action='append', default=[])
    args = parser.parse_args()
    # Validate before the observer creates its output directory.
    if args.output.exists() and not args.resume:
        raise ValueError('Choose a NEW disposable output directory.')
    if args.observe_market:
        from trade_market_observer import MarketObserver
        with MarketObserver(ROOT, args.output, capture_players=args.capture_player) as observer:
            # Observer directory creation is not a previous career.
            args.observer_directory_created = True
            run(args)
    else:
        run(args)


if __name__ == '__main__':
    main()
