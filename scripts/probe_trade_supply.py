"""Read-only candidate search comparison on an audit-owned saved career."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.save import load_save, canonical_with_save
from nba_gm_data.transactions import simulate_ai_trades


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    saved = load_save(args.save)
    canonical = load_app_canonical(root)
    stamp = saved['state']['current_date']
    report = {'evidence_kind': 'candidate search only; no transactions applied, not a season-frequency estimate',
              'date': stamp, 'cases': {}}
    for private in (False, True):
        active = canonical_with_save(canonical, deepcopy(saved))
        started = time.monotonic()
        result = simulate_ai_trades(active, stamp, stamp, seed=saved['meta']['seed'], limit=35,
                                    search_depth=2, reserve_assets=True, include_private_targets=private)
        report['cases']['private' if private else 'listed_only'] = {
            'seconds': round(time.monotonic()-started, 3),
            'count': result['proposal_count'], 'diagnostics': result['search_diagnostics'],
            'private_count': sum(r.get('target_source') == 'private_non_core_rotation_inquiry' for r in result['proposals']),
            'proposals': result['proposals']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: {a: b for a, b in v.items() if a != 'proposals'} for k, v in report['cases'].items()}, indent=2))


if __name__ == '__main__':
    main()
