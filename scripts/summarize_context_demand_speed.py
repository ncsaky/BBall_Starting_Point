"""Verify state/events, exact public responses and long-lived memory evidence."""
import hashlib
import json
from pathlib import Path
from statistics import median

BASE = Path('output/context-demand-pass')


def read(folder, name='report.json'):
    return json.loads((BASE / folder / name).read_text())


def response(folder):
    value = read(folder, 'response.json')
    # Precisely scoped file metadata. Preserve every key/type and every other
    # response value, including save status dictionaries and wants revisions.
    value['dashboard_snapshot']['revision'] = '<file-revision>'
    value['result']['save'] = '<isolated-save-path>'
    return value


summary = {'cases': {}, 'responses_normalized_paths': ['dashboard_snapshot.revision', 'result.save']}
for case in ('seed17', 'seed29', 'month17'):
    row = {}
    for version in ('before', 'after'):
        folders = [f'{version}-{case}-{i}' for i in (1, 2)]
        reports = [read(f) for f in folders]
        assert all(r['source_unchanged'] and not r['profiled'] and not r['reference_search'] for r in reports)
        assert read(folders[0], 'business.json') == read(folders[1], 'business.json')
        assert reports[0]['progress_digest'] == reports[1]['progress_digest']
        values = [r['seconds'] for r in reports]
        row[version] = {'median_seconds': median(values), 'range_seconds': [min(values), max(values)], 'samples': values}
    compared = 0
    for i in (1, 2):
        old, new = f'before-{case}-{i}', f'after-{case}-{i}'
        assert read(old, 'business.json') == read(new, 'business.json'), case
        assert read(old)['progress_digest'] == read(new)['progress_digest'], case
        assert read(old)['through'] == read(new)['through'] == ('2026-11-01' if case == 'month17' else '2027-02-04')
        if (BASE / old / 'response.json').exists():
            assert response(old) == response(new), case
            compared += 1
    assert compared
    row.update(business_equal=True, ordered_events_equal=True, exact_response_pairs=compared,
               reduction_percent=(1-row['after']['median_seconds']/row['before']['median_seconds'])*100)
    summary['cases'][case] = row

summary['attribution'] = {}
for version in ('before', 'after'):
    r = read('attribution-'+version, 'context-builds.json')
    groups = {}
    for b in r['builds']:
        callers = ' '.join(b['callers'])
        group = ('planning' if 'refresh_team_plans' in callers else
                 'settlement' if 'live_roster_issues' in callers else
                 'market' if 'trade_review.py:prepare' in callers else
                 'dashboard' if 'transaction_read_active' in callers else 'other')
        row = groups.setdefault(group, {'builds': 0, 'seconds': 0., 'components': {}})
        row['builds'] += 1
        row['seconds'] += b['build_seconds']
        for name, seconds in b['components_seconds'].items():
            row['components'][name] = row['components'].get(name, 0) + seconds
    summary['attribution'][version] = {'callers': groups, 'builds': len(r['builds']),
        'needs_calculations': sum(b['component_calls'].get('team_needs_and_excesses', 0) for b in r['builds']),
        'distinct_inputs': len({b['input_sha256'] for b in r['builds']})}
assert summary['attribution']['before']['builds'] == 9
assert summary['attribution']['after']['builds'] == 8
assert summary['attribution']['after']['callers']['settlement']['builds'] == 5

summary['memory'] = {}
expected = read('before-seed17-1')
for name in ('memory-before', 'memory-after', 'same-path-before', 'same-path-after'):
    r = read(name, 'memory-series.json')
    assert r['source_unchanged']
    assert all(a['business_digest'] == expected['digest'] and a['events_digest'] == expected['progress_digest'] for a in r['actions'])
    assert all(not a['live_before_gc'].get(kind, 0) for a in r['actions'] for kind in ('snapshot','trial','event','response'))
    summary['memory'][name] = r
for name in ('read-retention-before', 'read-retention-after', 'read-retention-roster-parent'):
    summary['memory'][name] = read(name, 'retention.json')
after = summary['memory']['memory-after']['actions']
assert all(a['read_cache_entries'] <= 2 for a in after)
# The report rows/weak-reference samples add a few hundred blocks. A full
# retained career costs about a million blocks, so this is a meaningful gate.
assert max(a['completion_allocated_blocks'] for a in after[2:])-min(a['completion_allocated_blocks'] for a in after[2:]) < 10000
reads = summary['memory']['read-retention-after']['reads']
assert all(r['read_cache_entries'] <= 2 for r in reads)
assert max(r['traced_retained_bytes_after_gc'] for r in reads[2:])-min(r['traced_retained_bytes_after_gc'] for r in reads[2:]) < 1_000_000
summary['checkpoints'] = read('checkpoints', 'checkpoints.json')
assert all(r['business_equal'] and r['ordered_events_equal'] for r in summary['checkpoints'].values())
summary['backend_sources'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('src/nba_gm_data').rglob('*.py'))}
(BASE / 'comparison.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps({'cases': summary['cases'], 'attribution': summary['attribution']}, indent=2))
