"""Verify the accounting repair against existing games; no season simulation."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from nba_gm_data.box_score import reconcile_box_score
from nba_gm_data.history_store import validate_save_components
from audit_basketball_accounting import game_errors
from review_offense_season import BATCH, OLD, history, read, sha


PROTECTED = ('points', 'minutes', 'fgm', 'fga', 'fg3m', 'fg3a', 'ftm', 'fta', 'personal_fouls')


def verify(games):
    before, after, deltas = Counter(), Counter(), Counter()
    changed = 0
    for original in games:
        before.update(e[0] for e in game_errors(original))
        result = deepcopy(original)
        reconcile_box_score(result['player_lines'], result['team_lines'])
        after.update(e[0] for e in game_errors(result))
        for a, b in zip(original['player_lines'], result['player_lines'], strict=True):
            assert all(a.get(k) == b.get(k) for k in PROTECTED), 'Scoring, minutes or fouls changed'
        for a, b in zip(original['team_lines'], result['team_lines'], strict=True):
            for k in ('rebounds', 'assists', 'steals', 'blocks'):
                deltas[k] += b[k]-a[k]
        changed += original != result
        once = deepcopy(result)
        reconcile_box_score(result['player_lines'], result['team_lines'])
        assert once == result, 'Reconciliation must be idempotent'
    if after:
        raise AssertionError(dict(after))
    return {'games': len(games), 'changed': changed, 'before_errors': dict(before),
            'after_errors': dict(after), 'scoring_minutes_and_fouls_unchanged': True,
            'idempotent': True, 'per_team_game_mean_changes': {k: v/(2*len(games)) for k, v in deltas.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Preserve prior evidence; choose a new output file')
    report, signatures = {'scope': 'Read-only repair of saved game copies, not new seasons or rewritten history.', 'cases': {}}, {}
    for seed in (29, 913):
        for label, directory in (('v8', OLD/f'career-{seed}'), ('v9', BATCH/f'runtime/output/offense-season/career-{seed}')):
            path = Path(read(directory/'run.json')['save_path'])
            saved = read(path)
            validate_save_components(path, saved)
            for component in (path, path.parent/saved['history_store']['path']):
                signatures[str(component)] = sha(component)
            dates = {r['game_id']: r['date'] for r in history(path, saved, 'team_game_logs')}
            games = [g for g in history(path, saved, 'game_results')
                     if '2026-10-01' <= dates.get(g['game_id'], '') <= '2027-04-12']
            assert len(games) == 1230
            report['cases'][f'{label}-{seed}'] = verify(games)
            print(f'{label}-{seed}: {len(games)} saved games verified', flush=True)
    report['input_hashes_unchanged'] = all(sha(Path(p)) == digest for p, digest in signatures.items())
    assert report['input_hashes_unchanged']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
