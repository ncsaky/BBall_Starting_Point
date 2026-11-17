"""Read-only live market search, followed by isolated settlement of found graphs."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import time
from unittest.mock import patch

from nba_gm_data import transactions as tx, multi_team_trades as multi
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.save import canonical_with_save, load_save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    saved = load_save(args.save)
    canonical = load_app_canonical(Path(__file__).resolve().parents[1])
    active = canonical_with_save(canonical, deepcopy(saved))
    original = multi.evaluate_multi_team_trade
    attempts = []
    def observe(*a, **kw):
        result = original(*a, **kw)
        attempts.append(result)
        return result
    stamp = saved['state']['current_date']
    started = time.monotonic()
    with patch.object(multi, 'evaluate_multi_team_trade', side_effect=observe):
        market = tx.simulate_ai_trades(active, stamp, stamp, seed=saved['meta']['seed'], limit=60,
            search_depth=3, reserve_assets=True)
    settlements = []
    seen = set()
    for candidate in market['proposals']+[r for r in attempts if r['accepted_by_all']]:
        if not candidate['proposal'].get('transfers'):
            continue
        if candidate['proposal']['id'] in seen:
            continue
        seen.add(candidate['proposal']['id'])
        isolated = deepcopy(saved)
        isolated['pending_trade_proposals'] = [candidate]
        result = tx.apply_trade_to_state(isolated, candidate['proposal']['id'], date=stamp, canonical=canonical)
        settlements.append({'candidate': candidate, 'status': result['status'], 'result': result,
                            'source_save_was_not_written': True})
    report = {'date': stamp, 'seconds': round(time.monotonic()-started, 3),
              'diagnostics': market['search_diagnostics'], 'settlements': settlements,
              'attempts': attempts, 'market': market}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'seconds': report['seconds'], 'diagnostics': report['diagnostics'],
        'settlements': [r['status'] for r in settlements],
        'legal_attempts': sum(r['legality']['status'] == 'legal' for r in attempts),
        'rejections': dict(Counter(e['perspective_team_id'] for r in attempts for e in r['evaluations'] if not e['accepted']))}, indent=2))


if __name__ == '__main__':
    main()
