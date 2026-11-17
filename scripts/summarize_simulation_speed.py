"""Validate outcome/animation parity before reporting measured speed differences."""
import json
from pathlib import Path

from verify_simulation_consistency import differences


def main():
    directory = Path(__file__).resolve().parents[1]/'output/simulation-speed-2026-10-29'
    rows = []
    for label, reference, optimized in [('deadline17', 'stream-reference', 'stream-after'),
                                         ('month_boundary17', 'month-reference', 'month-after'),
                                         ('deadline29', 'seed29-reference', 'seed29-after')]:
        before = json.loads((directory/reference/'report.json').read_text())
        after = json.loads((directory/optimized/'report.json').read_text())
        left = json.loads((directory/reference/'business.json').read_text())
        right = json.loads((directory/optimized/'business.json').read_text())
        assert left == right, differences(left, right)
        assert before['progress_digest'] == after['progress_digest'], label
        assert before['source_unchanged'] and after['source_unchanged']
        assert before['through'] == after['through']
        rows.append({'workload': label, 'before_seconds': before['seconds'], 'after_seconds': after['seconds'],
                     'reduction_percent': round((1-after['seconds']/before['seconds'])*100, 1),
                     'exact_business_match': True, 'exact_progress_match': True,
                     'progress_frames': after['progress_frames'], 'progress_kinds': after['progress_kinds']})
    report = {'cases': rows, 'limits': ['Single-machine samples, not a repeated isolated benchmark.',
        'The month and seed29 optimized runs overlapped; their timings are not isolated CPU measurements.',
        'Historical paths and incidental revisions/timestamps are excluded; gameplay and progress are compared.',
        'No animation timing, market quotas, search breadth or acceptance policy was reduced.']}
    (directory/'comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
