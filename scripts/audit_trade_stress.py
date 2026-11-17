"""Audit-only date-driven market pressure through real app actions."""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from nba_gm_data import transactions as tx, play, trade_calendar as calendar
from trade_market_observer import MarketObserver
from verify_trade_year import run, engine_fingerprint


def package_shape(report):
    proposal = report.get('proposal') or {}
    assets = tx.trade_assets(proposal)
    kinds = Counter(a.get('kind') for a in assets)
    return '+'.join(f'{n} {k}' for k, n in sorted(kinds.items()))


class SearchObserver:
    def __init__(self, output, pressure=1, depth=2, limit=60):
        self.output, self.pressure, self.depth, self.limit = Path(output), pressure, depth, limit
        self.calls, self.shapes, self.issues, self.decisions = [], Counter(), Counter(), Counter()
        self.evaluations = self.term_packages = self.swap_packages = 0
        self.original_search, self.original_evaluate = tx.simulate_ai_trades, tx.evaluate_trade
        self.original_day, self.original_summer = calendar.market_day, calendar.summer_offer_slots

    def evaluate(self, *args, **kwargs):
        report = self.original_evaluate(*args, **kwargs)
        self.evaluations += 1
        self.shapes[package_shape(report)] += 1
        self.issues.update(report.get('legality', {}).get('issues', []))
        self.decisions.update(e.get('decision', 'unknown') for e in report.get('evaluations', []))
        self.swap_packages += 'pick_swap' in package_shape(report)
        return report

    def search(self, *args, **kwargs):
        kwargs['search_depth'] = max(kwargs.get('search_depth', 1), self.depth)
        kwargs['limit'] = max(kwargs.get('limit', 10), self.limit)
        started = time.monotonic()
        result = self.original_search(*args, **kwargs)
        accepted = result.get('proposals', [])
        self.term_packages += sum(bool(c.get('pick_obligation_terms')) for c in accepted)
        record = {'date': args[2] if len(args) > 2 else kwargs.get('through_date'),
                  'seconds': round(time.monotonic()-started, 3),
                  'diagnostics': result.get('search_diagnostics'),
                  'accepted': len(accepted), 'accepted_shapes': dict(Counter(package_shape(c) for c in accepted)),
                  'human_candidates': sum(bool(set((args[0].get('_human_team_ids') or [])) &
                      set(tx.trade_team_ids(c))) for c in accepted)}
        self.calls.append(record)
        with (self.output/'search-calls.jsonl').open('a') as handle:
            handle.write(json.dumps(record)+'\n')
        return result

    def day(self, *args, **kwargs):
        result = self.original_day(*args, **kwargs)
        if not result.get('review'):
            return result
        # Pressure multiplies existing date opportunities, never acceptance.
        return {**result, 'slots': min(72, result['slots']*self.pressure),
                'offer_slots': min(12, result['offer_slots']*self.pressure)}

    def summer(self, *args, **kwargs):
        return min(12, self.original_summer(*args, **kwargs)*self.pressure)

    def report(self):
        return {'pressure': self.pressure, 'search_depth': self.depth, 'proposal_limit': self.limit,
                'evaluated_packages': self.evaluations, 'evaluated_shapes': dict(self.shapes),
                'evaluated_swap_packages': self.swap_packages, 'accepted_packages_with_new_terms': self.term_packages,
                'legality_issues': dict(self.issues), 'decisions': dict(self.decisions), 'search_calls': self.calls,
                'limits': ['Audit-only pressure, not production frequency calibration.',
                           'Summer applications retain production phase capacity.',
                           'Accepted candidates can conflict; durable application counts are in trade-year.json.',
                           'Automatic facilitator search is bounded; not an exhaustive graph search.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-save', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--end-date', required=True)
    parser.add_argument('--pressure', type=int, default=3, choices=range(1, 5))
    parser.add_argument('--depth', type=int, default=3, choices=range(1, 4))
    parser.add_argument('--seconds', type=int, default=1200)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new disposable output directory.')
    source_hash = hashlib.sha256(args.from_save.read_bytes()).hexdigest()
    engine = engine_fingerprint()
    args.output.mkdir(parents=True)
    observer = SearchObserver(args.output, args.pressure, args.depth)
    try:
        with ExitStack() as stack:
            stack.enter_context(MarketObserver(Path(__file__).resolve().parents[1], args.output))
            stack.enter_context(patch.object(tx, 'simulate_ai_trades', observer.search))
            stack.enter_context(patch.object(tx, 'evaluate_trade', observer.evaluate))
            stack.enter_context(patch.object(play, 'evaluate_trade', observer.evaluate))
            stack.enter_context(patch.object(calendar, 'market_day', observer.day))
            stack.enter_context(patch.object(calendar, 'summer_offer_slots', observer.summer))
            run(argparse.Namespace(output=args.output, seed=args.seed, resume=False,
                observer_directory_created=True, from_save=args.from_save,
                end_date=args.end_date, seconds=args.seconds))
    finally:
        report = observer.report()
        report['engine_unchanged'] = engine == engine_fingerprint()
        report['source_save_unchanged'] = source_hash == hashlib.sha256(args.from_save.read_bytes()).hexdigest()
        (args.output/'stress.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: v for k, v in report.items() if k not in {'search_calls', 'legality_issues'}}), flush=True)


if __name__ == '__main__':
    main()
