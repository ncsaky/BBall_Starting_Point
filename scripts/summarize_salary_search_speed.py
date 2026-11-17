"""Verify bounded Stage-B evidence, without requiring old/new discovery parity."""
import hashlib
import json
from pathlib import Path
import pstats
from statistics import median

BASE = Path('output/salary-search-stage-b')


def read(folder, name='report.json'):
    return json.loads((BASE / folder / name).read_text())


summary = {'discovery_boundary': 'Stage B intentionally changes search discovery.',
           'timings': {}, 'repeat_consistency': {}, 'profiles': {}, 'instrumented': {}}
sources = {
    'seed17': ('output/pick-investment-2026-10-28/stable17/saves/trade_year.json', '2027-02-04'),
    'seed29': ('output/trade-presentation-task-1/fixtures/seed29/trade_year.json', '2027-02-04'),
    'month17': ('output/trade-presentation-task-1/fixtures/month17/trade_month.json', '2026-11-01'),
}
for case, (source, target) in sources.items():
    summary['timings'][case] = {}
    for version in ('stage-a', 'stage-b'):
        folders = [f'{version}-{case}-{sample}' for sample in (1, 2)]
        reports = [read(f) for f in folders]
        assert all(r['source_unchanged'] and r['through'] == target and not r['profiled'] for r in reports)
        assert read(folders[0], 'business.json') == read(folders[1], 'business.json')
        assert reports[0]['progress_digest'] == reports[1]['progress_digest']
        times = [r['seconds'] for r in reports]
        summary['timings'][case][version] = {'median_seconds': median(times),
            'range_seconds': [min(times), max(times)], 'samples_seconds': times}
        summary['repeat_consistency'][f'{version}-{case}'] = {
            'business_equal': True, 'ordered_events_equal': True,
            'progress_frames': reports[0]['progress_frames']}
    old = summary['timings'][case]['stage-a']['median_seconds']
    new = summary['timings'][case]['stage-b']['median_seconds']
    summary['timings'][case]['median_reduction_percent'] = (old - new) / old * 100
    summary['timings'][case]['cross_version_business_equal'] = (
        read(f'stage-a-{case}-1', 'business.json') == read(f'stage-b-{case}-1', 'business.json'))

names = ('simulate_ai_trades', 'evaluate_trade_decision', 'evaluate_trade_for_team',
         'buyer_offer_packages_for_value', 'trade_value_breakdown', 'roster_projection',
         'build_transaction_context', 'apply_trade_to_state', 'canonical_with_pending_pick_terms')
for version in ('stage-a', 'stage-b'):
    folder = f'profile-{version}'
    report = read(folder)
    assert report['source_unchanged']
    assert read(folder, 'business.json') == read(f'{version}-seed17-1', 'business.json')
    assert report['progress_digest'] == read(f'{version}-seed17-1')['progress_digest']
    stats = pstats.Stats(str(BASE / folder / 'advance.prof'))
    summary['profiles'][version] = {'seconds': report['seconds'],
        'diagnostics': read(folder, 'salary-diagnostics.json'), 'calls': {}}
    for name in names:
        rows = [v for k, v in stats.stats.items() if k[2] == name]
        summary['profiles'][version]['calls'][name] = {
            'calls': sum(v[1] for v in rows), 'cumulative_seconds': sum(v[3] for v in rows)}
    folder = f'evaluation-counts-{version}'
    report = read(folder)
    assert not report['profiled'] and report['source_unchanged']
    assert read(folder, 'business.json') == read(f'{version}-seed17-1', 'business.json')
    summary['instrumented'][version] = {'seconds': report['seconds'],
        'diagnostics': read(folder, 'salary-diagnostics.json')}

summary['checkpoints'] = read('checkpoints', 'checkpoints.json')
assert all(r['business_equal'] and r['ordered_events_equal'] for r in summary['checkpoints'].values())
discovery = json.loads((BASE / 'discovery-comparison.json').read_text())
summary['markets'] = []
for old, new, delta in zip(read('markets-stage-a'), read('markets-stage-b'), discovery):
    assert (old['phase'], old['seed']) == (new['phase'], new['seed']) == (delta['phase'], delta['seed'])
    assert old['source_unchanged'] and new['source_unchanged'] and new['participants_valid']
    assert all(r['fresh_existing_ai_policy_approved'] and r['financial_category'] == 'legal'
               for r in delta['lost'])
    assert all(r['fresh_existing_policy_approved'] for r in delta['gained_validation'])
    summary['markets'].append({k: delta[k] for k in ('phase', 'seed', 'lost_count',
        'gained_count', 'unchanged_count', 'before_counts', 'after_counts')})
summary['incoming'] = json.loads((BASE / 'incoming-comparison.json').read_text())
assert summary['incoming']['actual_offer_sets_reproduced']
summary['app_discovery'] = {}
for case, (source, _) in sources.items():
    original = json.loads(Path(source).read_text())
    old_offers = {o['proposal']['id'] for o in original.get('user_trade_offers', [])}
    old_logs = {o['id'] for o in original.get('transaction_logs', [])}
    summary['app_discovery'][case] = {}
    for version in ('stage-a', 'stage-b'):
        final = read(f'{version}-{case}-1', 'business.json')
        offers = [o for o in final.get('user_trade_offers', []) if o['proposal']['id'] not in old_offers]
        logs = [o for o in final.get('transaction_logs', []) if o['id'] not in old_logs
                and o.get('transaction_type') == 'trade']
        summary['app_discovery'][case][version] = {
            'new_direct_offers': sum(not bool(o['proposal'].get('transfers')) for o in offers),
            'new_multi_team_offers': sum(bool(o['proposal'].get('transfers')) for o in offers),
            'new_transactions': len(logs),
            'new_multi_team_transactions': sum(bool(o.get('assets', {}).get('transfers')) for o in logs)}

manifest = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path('src/nba_gm_data').rglob('*.py'))}
(BASE / 'source-after-sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
(BASE / 'comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k not in ('profiles', 'instrumented', 'incoming')}, indent=2))
