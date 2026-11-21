"""Replay frozen trades and inspect live inboxes without writing a career."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace
from unittest.mock import patch

from nba_gm_data import transactions as tx
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.multi_team_trades import evaluate_multi_team_trade, transfers_for_revalidation
from nba_gm_data.save import load_save, canonical_with_save
from nba_gm_data.trade_roster import trade_roster_outlook
from analyze_trade_market import all_logs


def replay(context, candidate, *, recorded_personality=False):
    proposal = candidate['proposal']
    seed = int(candidate.get('evaluation_seed', candidate.get('ui_pick_rule_seed', 17)))
    if recorded_personality:
        recorded = {e['perspective_team_id']: e['personality_adjustments'] for e in candidate['evaluations']}
        with patch.object(tx, 'personality_trade_adjustment', side_effect=lambda c, tid, pid, s, **kw: deepcopy(recorded[tid])):
            return replay(context, candidate)
    if proposal.get('transfers'):
        return evaluate_multi_team_trade(context, transfers_for_revalidation(candidate), pick_rules=candidate.get('pick_rules'),
            seed=seed, date=proposal['date'], proposal_id=proposal['id'])
    context = tx.canonical_with_pending_pick_terms(context, candidate.get('pick_obligation_terms'))
    obj = SimpleNamespace(**{**proposal, 'id': candidate.get('evaluation_proposal_id') or proposal['id']})
    config = tx.default_transaction_model_config()
    legality = tx.trade_legality(context, obj, config)
    evaluations = [tx.trade_evaluation_payload(context, e, config)
                   for e in tx.evaluate_trade_participants(context, obj, legality, seed, config)]
    return {'proposal': proposal, 'legality': legality, 'evaluations': evaluations,
            'accepted_by_all': legality['status'] == 'legal' and all(e['accepted'] for e in evaluations)}


def outlooks(context, candidate):
    context = tx.canonical_with_pending_pick_terms(context, candidate.get('pick_obligation_terms'))
    result = []
    for tid, outgoing, incoming in tx.trade_team_flows(candidate):
        outlook = trade_roster_outlook(context, tid, incoming, outgoing)
        if outlook:
            result.append({'team_id': tid, **outlook})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    path = args.directory/'saves/trade_year.json'
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    saved = load_save(path)
    frozen = []
    for source in sorted(args.directory.glob('context-*.json.gz')):
        record = json.load(gzip.open(source, 'rt'))
        context, candidate = record['canonical'], record['candidate']
        context['_allow_internal_caches'] = True
        context['_trade_planning_save'] = {'meta': deepcopy(saved['meta']),
            'state': {'current_date': record['date']}, 'season_schedules': saved.get('season_schedules', {}),
            'team_plans': context.get('team_plans', {}), 'health_states': context.get('player_health_states', [])}
        fresh = replay(context, candidate, recorded_personality=True)
        frozen.append({'source': str(source), 'proposal': candidate['proposal'], 'historical_evaluations': candidate['evaluations'],
            'new_evaluations': fresh['evaluations'], 'accepted_by_all': fresh['accepted_by_all'], 'outlooks': outlooks(context, candidate)})
    canonical = load_app_canonical(Path(__file__).resolve().parents[1])
    active = tx.with_transaction_context(canonical_with_save(canonical, deepcopy(saved)))
    offers = []
    for candidate in saved.get('user_trade_offers', []):
        status = (candidate.get('offer_context') or {}).get('status')
        row = {'proposal_id': candidate['proposal']['id'], 'status': status, 'date': candidate['proposal']['date']}
        if status == 'pending_user_review':
            try:
                fresh = replay(active, candidate)
                row.update(current_legality=fresh['legality'], new_evaluations=fresh['evaluations'],
                           outlooks=outlooks(active, candidate))
            except (KeyError, ValueError) as error:
                row['current_revalidation_error'] = str(error)
        offers.append(row)
    logs = all_logs(path, saved)
    releases = []
    for log in logs:
        if log.get('transaction_type') != 'roster_cut' or log.get('date', '') < '2027-02-01':
            continue
        pid = (log.get('assets') or {}).get('player_id')
        tid = log.get('teams', [None])[0]
        acquisitions = [r for r in logs if r.get('transaction_type') == 'trade' and r.get('date', '') <= log['date']
            and any(t == tid and any(a.get('id') == pid for a in incoming) for t, _, incoming in tx.transaction_log_flows(r))]
        releases.append({'player_id': pid, 'name': log['assets'].get('name'), 'team': tid, 'date': log['date'],
                         'recent_acquisition': max((r['date'] for r in acquisitions), default=None)})
    report = {'source_save': str(path), 'source_save_unchanged': original_hash == hashlib.sha256(path.read_bytes()).hexdigest(),
              'frozen_trades': frozen, 'inbox': offers, 'releases': releases,
              'seconds': round(time.monotonic()-started, 3),
              'limits': ['Frozen trades use their preserved roster/skills/contracts and the same season schedule; recorded personality adjustments are held fixed.',
                         'Inbox results use the final saved date, not an invented historical offer-time roster.',
                         'Roster forecasts are healthy planning estimates, not measured title probabilities.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'seconds': report['seconds'], 'source_save_unchanged': report['source_save_unchanged'],
        'frozen': [{'source': r['source'], 'accepted': r['accepted_by_all'],
            'decisions': [(e['perspective_team_id'], e['decision'], e['net_value']) for e in r['new_evaluations']]} for r in frozen],
        'inbox': len(offers), 'pending': sum(r['status'] == 'pending_user_review' for r in offers),
        'same_day_trade_then_cut': [r for r in releases if r['recent_acquisition'] == r['date']]}, indent=2))


if __name__ == '__main__':
    main()
