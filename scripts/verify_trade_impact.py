"""Reprice frozen summer counterexamples and inspect isolated roster forecasts."""
import argparse
from copy import deepcopy
from dataclasses import replace
import gzip
import json
from pathlib import Path

from nba_gm_data import transactions as tx
from nba_gm_data.schema import PlayerAssetValuation, to_plain
from review_premium_trade_packages import price


def review(path, seed):
    with gzip.open(path, 'rt') as handle:
        record = json.load(handle)
    active, candidate = record['canonical'], record['candidate']
    original = deepcopy(active)
    values = [PlayerAssetValuation(**v) for v in active['player_asset_valuations']]
    states = tx.build_team_strategic_states(active, values)
    active['team_strategic_states'] = [to_plain(s) for s in states]
    active['_strategy_model_version'] = tx.STRATEGY_MODEL_VERSION
    proposal = candidate['proposal']
    owners = {a['id']: tid for side, tid in [('from_assets', proposal['to_team_id']),
                                          ('to_assets', proposal['from_team_id'])]
              for a in proposal[side] if a['kind'] == 'player'}
    trial = {k: v for k, v in active.items() if not k.startswith('_')}
    trial['players'] = [dict(p, team_id=owners.get(p['id'], p.get('team_id'))) for p in active['players']]
    after_values = [replace(v, team_id=owners.get(v.player_id, v.team_id)) for v in values]
    after = tx.build_team_strategic_states(trial, after_values)
    evaluation_seed = seed
    if (candidate.get('free_agency_context') or {}).get('kind') == 'general_market_trade':
        evaluation_seed += int(record['date'][8:10])*17
    priced = price(active, candidate, evaluation_seed)
    result = {'context': str(path), 'proposal_id': proposal['id'], 'date': record['date'],
              'original_evaluations': candidate.get('evaluations'),
              'result': priced, 'teams': {}}
    for tid in (proposal['from_team_id'], proposal['to_team_id']):
        old = next(s for s in original['team_strategic_states'] if s['team_id'] == tid)
        before = next(s for s in states if s.team_id == tid)
        new = next(s for s in after if s.team_id == tid)
        result['teams'][tid] = {'original_strength': old['contention_ceiling'],
            'strength': before.contention_ceiling, 'after_strength': new.contention_ceiling,
            'delta': round(new.contention_ceiling-before.contention_ceiling, 3),
            'phase': before.window_phase, 'after_phase': new.window_phase,
            'original_rank': old.get('league_rank'), 'rank': before.league_rank, 'after_rank': new.league_rank}
    assert record['canonical']['players'] == original['players']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = [review(p, int(p.parent.name.removeprefix('before')))
             for p in sorted(args.root.glob('before*/context*.json.gz'))]
    args.output.write_text(json.dumps({'cases': cases}, indent=2)+'\n')
    for c in cases:
        print(json.dumps({'proposal': c['proposal_id'], 'eligible': c['result']['automatic_execution_eligible'],
                          'teams': c['teams'], 'decisions': [(e['perspective_team_id'], e['decision']) for e in c['result']['evaluations']]}))


if __name__ == '__main__':
    main()
