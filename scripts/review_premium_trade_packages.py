"""Reprice unchanged packages in frozen pre-trade audit contexts."""
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path

from nba_gm_data import transactions as tx
from nba_gm_data.schema import PlayerAssetValuation, TradeProposal, to_plain


def price(active, candidate, seed):
    proposal = TradeProposal(**candidate['proposal'])
    config = tx.default_transaction_model_config()
    legality = tx.trade_legality(active, proposal, config)
    evaluations = []
    for tid, incoming, outgoing in [(proposal.from_team_id, proposal.to_assets, proposal.from_assets),
                                    (proposal.to_team_id, proposal.from_assets, proposal.to_assets)]:
        evaluations.append(to_plain(tx.evaluate_trade_for_team(active, proposal, tid, incoming, outgoing, legality, seed, config)))
    report = {'proposal': candidate['proposal'], 'legality': legality, 'evaluations': evaluations,
              'accepted_by_all': all(r['accepted'] for r in evaluations)}
    report['automatic_execution_eligible'] = tx.ai_trade_candidate_accepted(active, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contexts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rebuild-strategy', action='store_true')
    args = parser.parse_args()
    rows = []
    for path in sorted(args.contexts.glob('seed*/context-*.json.gz')):
        with gzip.open(path, 'rt') as handle:
            record = json.load(handle)
        active, candidate = record['canonical'], record['candidate']
        original_states = deepcopy(active['team_strategic_states'])
        if args.rebuild_strategy:
            values = [PlayerAssetValuation(**v) for v in active['player_asset_valuations']]
            active['team_strategic_states'] = [to_plain(s) for s in tx.build_team_strategic_states(active, values)]
        seed = int(path.parent.name.removeprefix('seed'))
        evaluation_seed = seed
        if (candidate.get('free_agency_context') or {}).get('kind') == 'general_market_trade':
            evaluation_seed += int(candidate['proposal']['date'][8:10])*17
        result = price(active, candidate, evaluation_seed)
        teams = {candidate['proposal']['from_team_id'], candidate['proposal']['to_team_id']}
        rows.append({'seed': seed, 'proposal_id': candidate['proposal']['id'],
            'date': record['original_event']['date'], 'context': str(path), 'evaluation_seed': evaluation_seed,
            'original_evaluations': record['original_event']['evaluations'],
            'original_states': [s for s in original_states if s['team_id'] in teams],
            'states': [s for s in active['team_strategic_states'] if s['team_id'] in teams],
            'result': result,
            'pick_values': [{**a, 'value': tx.pick_asset_value(tx.pick_by_id(active, a['id']), 'retooling')}
                            for side in ('from_assets', 'to_assets') for a in candidate['proposal'][side] if a['kind'] == 'pick']})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'cases': rows}, indent=2)+'\n')
    for r in rows:
        print(json.dumps({'seed': r['seed'], 'date': r['date'], 'proposal_id': r['proposal_id'],
            'eligible': r['result']['automatic_execution_eligible'],
            'phases': {s['team_id']: s.get('window_phase') for s in r['states']},
            'evaluations': [{k: e[k] for k in ('perspective_team_id', 'incoming_value', 'outgoing_value', 'net_value', 'accepted', 'notes')}
                            for e in r['result']['evaluations']]}), flush=True)


if __name__ == '__main__':
    main()
