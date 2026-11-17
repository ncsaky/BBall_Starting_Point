"""Bounded elite-player searches and frozen-package replays; never writes source saves."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from nba_gm_data import transactions as tx
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.save import load_save, canonical_with_save, player_display_attribute_summary
from audit_trade_quality import replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--targets', type=int, default=4)
    parser.add_argument('--buyer', help='Optional alternative controlled buyer for a bounded Finder probe.')
    args = parser.parse_args()
    started = time.monotonic()
    digest = hashlib.sha256(args.save.read_bytes()).hexdigest()
    saved = load_save(args.save)
    root = Path(__file__).resolve().parents[1]
    active = tx.with_transaction_context(canonical_with_save(load_app_canonical(root), deepcopy(saved)))
    players = {p['id']: p for p in active['players']}
    teams = {t['id']: t['abbrev'] for t in active['teams']}
    elite = []
    for p in active['players']:
        if p.get('team_id') not in teams or p.get('_inactive_player'):
            continue
        attrs = player_display_attribute_summary(active, p['id'])
        if float(attrs.get('overall') or 0) >= 90:
            elite.append({'id': p['id'], 'name': p['name'], 'team': teams[p['team_id']],
                          'overall': attrs['overall'], 'valuation': tx.player_asset_values_by_id(active).get(p['id'])})
    elite.sort(key=lambda p: (-p['overall'], p['id']))
    # Use the real Finder. Selling-team approval remains mandatory; user consent is manual.
    user = args.buyer or teams[saved['meta']['user_team_id']]
    targets = [p for p in elite if p['team'] != user][:args.targets]
    searches = []
    for target in targets:
        tick = time.monotonic()
        attempts = []
        original = tx.evaluate_trade
        def observe(*a, **kw):
            row = original(*a, **kw)
            attempts.append(row)
            return row
        with patch.object(tx, 'evaluate_trade', side_effect=observe):
            result = tx.find_trade_for_assets(active, target['team'], [{'kind': 'player', 'value': target['id']}],
                                             user, seed=saved['meta']['seed'], limit=4)
        searches.append({'target': target, 'seconds': round(time.monotonic()-tick, 3), 'result': result, 'attempts': attempts})
        print(json.dumps({'target': target['name'], 'overall': target['overall'],
                          'offers': result['candidate_count'], 'seconds': searches[-1]['seconds']}), flush=True)
    frozen = []
    for path in sorted((root/'output/premium-trade-review-2026-10-27').glob('seed*/context-*.json.gz')):
        with gzip.open(path, 'rt') as handle:
            record = json.load(handle)
        context, candidate = record['canonical'], record['candidate']
        context['_allow_internal_caches'] = True
        fresh = replay(context, candidate, recorded_personality=True)
        # Separately test today's classifier on the same historical player data.
        from nba_gm_data.schema import PlayerAssetValuation, to_plain
        context['team_strategic_states'] = [to_plain(s) for s in tx.build_team_strategic_states(
            context, [PlayerAssetValuation(**v) for v in context['player_asset_valuations']])]
        rebuilt = replay(context, candidate, recorded_personality=True)
        frozen.append({'source': str(path), 'proposal': candidate['proposal'],
                       'original_evaluations': candidate['evaluations'], 'current': fresh,
                       'rebuilt_strategy': rebuilt})
    report = {'source': str(args.save), 'source_unchanged': digest == hashlib.sha256(args.save.read_bytes()).hexdigest(),
              'date': saved['state']['current_date'], 'buyer': user, 'elite': elite, 'searches': searches, 'frozen': frozen,
              'seconds': round(time.monotonic()-started, 3),
              'limits': ['Finder candidates are proposals, not completed trades.',
                         'Frozen packages retain historical player data, not newly calibrated ratings.',
                         'Only the specified number of elite targets is searched; absence is not proof of fair pricing.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'seconds': report['seconds'], 'elite_count': len(elite),
                      'source_unchanged': report['source_unchanged'],
                      'frozen_approved': [r['current']['accepted_by_all'] for r in frozen]}), flush=True)


if __name__ == '__main__':
    main()
