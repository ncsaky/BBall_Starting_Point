"""Paired fixed-context games: accounting, variability, scoring identity and runtime."""
import argparse
import json
from pathlib import Path
import statistics
import time
from unittest.mock import patch

from nba_gm_data.sim import load_sim_context, sim_game_with_context
from nba_gm_data.schema import to_plain
from audit_basketball_accounting import game_errors

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--games', type=int, default=240)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    canonical = json.loads((ROOT / 'data/canonical/universe_2026_27_offseason.json').read_text())
    context = load_sim_context(ROOT, canonical)
    games = [str(g['externalGameId']) for g in context['schedule'] if g.get('phase') == 'regular'][:8]
    old, new = [], []
    seconds = {'before': 0., 'after': 0.}
    for seed in range(args.games):
        gid = games[seed % len(games)]
        start = time.perf_counter()
        with patch('nba_gm_data.box_variation.vary_box_score'):
            before = to_plain(sim_game_with_context(context, gid, mode='sandbox-sim', seed=seed))
        seconds['before'] += time.perf_counter() - start
        start = time.perf_counter()
        after = to_plain(sim_game_with_context(context, gid, mode='sandbox-sim', seed=seed))
        seconds['after'] += time.perf_counter() - start
        assert not game_errors(after), (seed, game_errors(after))
        assert [(t['points'], t['possessions']) for t in before['team_lines']] == [(t['points'], t['possessions']) for t in after['team_lines']]
        old.extend(before['team_lines'])
        new.extend(after['team_lines'])
    report = {'games': args.games, 'accounting_errors': 0, 'score_changes': 0, 'seconds': seconds, 'stats': {}}
    for key in ('fga', 'rebounds', 'assists', 'turnovers', 'steals', 'blocks', 'fg_pct', 'fg3_pct'):
        def values(rows):
            return [(r['fgm'] / max(1, r['fga']) if key == 'fg_pct' else r['fg3m'] / max(1, r['fg3a']) if key == 'fg3_pct' else r[key]) for r in rows]
        report['stats'][key] = {name: {'mean': round(statistics.mean(values(rows)), 4),
                                     'sd': round(statistics.pstdev(values(rows)), 4),
                                     'min': min(values(rows)), 'max': max(values(rows))}
                                for name, rows in [('before', old), ('after', new)]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
