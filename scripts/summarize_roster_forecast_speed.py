"""Require exact app-action parity before reporting this pass's timings."""
import hashlib
import json
from pathlib import Path
import pstats
from statistics import median

BASE = Path('output/roster-forecast-pass')


def read(folder, name='report.json'):
    return json.loads((BASE / folder / name).read_text())


summary = {'cases': {}, 'profiles': {}}
for case in ('seed17', 'seed29', 'month17'):
    row = {}
    for version in ('before', 'after'):
        folders = [f'{version}-{case}-{i}' for i in (1, 2)]
        reports = [read(f) for f in folders]
        assert all(r['source_unchanged'] and not r['profiled'] and not r['reference_search'] for r in reports)
        assert read(folders[0], 'business.json') == read(folders[1], 'business.json')
        assert reports[0]['progress_digest'] == reports[1]['progress_digest']
        values = [r['seconds'] for r in reports]
        row[version] = {'median_seconds': median(values), 'range_seconds': [min(values), max(values)],
                        'samples_seconds': values, 'repeat_business_equal': True, 'repeat_events_equal': True}
    for i in (1, 2):
        old, new = f'before-{case}-{i}', f'after-{case}-{i}'
        assert read(old, 'business.json') == read(new, 'business.json'), case
        assert read(old)['progress_digest'] == read(new)['progress_digest'], case
        assert read(old)['through'] == read(new)['through'] == ('2026-11-01' if case == 'month17' else '2027-02-04')
    row.update(business_equal=True, ordered_events_equal=True,
               progress_frames=read(f'after-{case}-1')['progress_frames'],
               reduction_percent=(row['before']['median_seconds'] - row['after']['median_seconds']) / row['before']['median_seconds'] * 100)
    summary['cases'][case] = row

for version in ('before', 'after'):
    folder = 'profile-final-' + version
    report = read(folder)
    assert report['source_unchanged'] and report['profiled']
    assert read(folder, 'business.json') == read(f'{version}-seed17-1', 'business.json')
    assert report['progress_digest'] == read(f'{version}-seed17-1')['progress_digest']
    diagnostic = read(folder, 'roster-diagnostics.json')
    assert diagnostic['released'] == diagnostic['release_probes']
    assert diagnostic['snapshots_released'] == diagnostic['snapshot_release_probes']
    stats = pstats.Stats(str(BASE / folder / 'advance.prof'))
    names = ('roster_projection', 'constrain_center_opportunity', 'live_roster_issues', 'strategic_rotation_view',
             'build_transaction_context', 'build_team_strategic_states', 'with_transaction_context',
             'apply_trade_to_state', 'player_feature_vector', 'team_feature_vector', 'ai_role_targets',
             'player_attribute_summary', '_uncached_player_attribute_summary', 'season_window',
             '_uncached_season_window', 'evaluate_trade_decision', 'trade_value_breakdown')
    calls = {}
    for name in names:
        rows = [v for key, v in stats.stats.items() if key[2] == name]
        calls[name] = {'calls': sum(v[1] for v in rows), 'cumulative_seconds': sum(v[3] for v in rows)}
    summary['profiles'][version] = {'seconds': report['seconds'], 'calls': calls, 'diagnostic': diagnostic}
for name in ('roster_projection', 'constrain_center_opportunity', 'strategic_rotation_view',
             'build_transaction_context', 'apply_trade_to_state', 'evaluate_trade_decision', 'trade_value_breakdown'):
    assert summary['profiles']['before']['calls'][name]['calls'] == summary['profiles']['after']['calls'][name]['calls'], name
summary['checkpoints'] = read('checkpoints', 'checkpoints.json')
assert all(r['business_equal'] and r['ordered_events_equal'] for r in summary['checkpoints'].values())
summary['memory'] = {}
for version in ('before', 'after'):
    folder = 'memory-' + version
    assert read(folder, 'business.json') == read(f'{version}-seed17-1', 'business.json')
    assert read(folder)['progress_digest'] == read(f'{version}-seed17-1')['progress_digest']
    assert read(folder)['source_unchanged']
    summary['memory'][version] = read(folder, 'memory.json')
summary['source_after_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(Path('src/nba_gm_data').rglob('*.py'))}
(BASE / 'comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary['cases'], indent=2))
