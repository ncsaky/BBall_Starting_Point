"""Join stress-search attempts, committed interval trades and user inboxes."""
import argparse
from collections import Counter
import json
from pathlib import Path

from analyze_trade_market import analyze, all_logs
from audit_trade_stress import package_shape
from nba_gm_data.save import load_save


def summarize(directory, start):
    directory = Path(directory)
    raw = json.loads((directory/'trade-year.json').read_text())
    pressure = json.loads((directory/'stress.json').read_text())
    market = analyze(directory, int(start[:4]))
    saved_path = directory/'saves/trade_year.json'
    saved = load_save(saved_path)
    logs = [r for r in all_logs(saved_path, saved) if start <= r.get('date', '') <= raw['date']]
    durable = {r['proposal_id'] for r in logs if r.get('transaction_type') == 'trade'}
    events = {r['proposal_id']: r for line in (directory/'market-events.jsonl').read_text().splitlines()
              for r in [json.loads(line)] if r.get('kind') == 'trade' and r['proposal_id'] in durable}
    offers = [o for o in raw['all_offers'] if start <= o.get('offer_context', {}).get('created_date', '') <= raw['date']]
    assert len(events) == len(durable), 'Missing committed trade-time evidence'
    assert len(offers) == len({o['proposal']['id'] for o in offers}), 'Duplicate delivered offers'
    debts = {r['id']: r for r in saved.get('waived_salary_obligations', [])}
    for entry in saved.get('waiver_wire', []):
        if entry['date'] < start or entry['status'] != 'claimed':
            continue
        debt = debts[entry['id']]
        assert debt['relief_status'] == 'existing_contract_assumed_by_claimant'
        assert all(r['salary'] == 0 for r in debt['seasons'])
    from nba_gm_data.transactions import trade_assets
    rights = [a for e in events.values() for a in trade_assets(e['proposal']) if a['kind'] != 'player']
    obligations = {o['id']: o for o in saved.get('pick_obligations', [])}
    assert len(obligations) == len(saved.get('pick_obligations', [])), 'Duplicate obligation IDs'
    for right in rights:
        if right['kind'] == 'pick_swap':
            assert right['id'] in obligations, 'Committed swap lost its defining obligation'
    new_grants = [o for o in obligations.values() if str(o.get('id', '')).startswith('ai_pick_swap_')
                  and start <= o.get('date_created', '') <= raw['date']]
    protections = [a for e in events.values() for a in e['before']['assets']
                   if a.get('kind') == 'pick' and (a.get('protection_summary') or a.get('nested_entitlement'))]
    calls = pressure['search_calls']
    return {'directory': str(directory), 'seed': raw['seed'], 'from': start, 'through': raw['date'],
        'completed': raw.get('status') == 'completed_interval', 'seconds': raw['seconds'],
        'engine_unchanged': pressure['engine_unchanged'] and raw['engine_unchanged'],
        'source_save_unchanged': pressure['source_save_unchanged'],
        'pressure': pressure['pressure'], 'depth': pressure['search_depth'],
        'committed_trades': len(events), 'trade_shapes': dict(Counter(package_shape(e) for e in events.values())),
        'quality': dict(Counter(e['classification']['quality_class'] for e in events.values())),
        'trade_rights': dict(Counter(a['kind'] for a in rights)), 'protected_pick_transfers': len(protections),
        'new_swap_grants_committed': len(new_grants),
        'incoming_offers': len(offers), 'offer_shapes': dict(Counter(package_shape(o) for o in offers)),
        'offer_statuses': dict(Counter(o['offer_context']['status'] for o in offers)),
        'evaluated_packages': pressure['evaluated_packages'],
        'evaluated_swap_packages': pressure['evaluated_swap_packages'],
        'new_term_candidates': pressure['accepted_packages_with_new_terms'],
        'search_diagnostics': dict(sum((Counter(c['diagnostics']) for c in calls), Counter())),
        'decision_counts': pressure['decisions'],
        'top_legality_issues': Counter(pressure['legality_issues']).most_common(12),
        'search_seconds': round(sum(c['seconds'] for c in calls), 3),
        'max_search_seconds': max((c['seconds'] for c in calls), default=0),
        'transactions': dict(Counter(r['transaction_type'] for r in logs)),
        'target_follow_through': [p for p in market['free_agency_pursuits'] if p['date'] >= start],
        'buyouts': [r for r in market['releases'] if r['date'] >= start and r['buyout']],
        'trades': [t for t in market['trades'] if t['date'] >= start],
        'limits': pressure['limits']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', nargs=2, action='append', required=True, metavar=('DIRECTORY', 'START'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = [summarize(d, start) for d, start in args.case]
    args.output.write_text(json.dumps({'cases': cases}, indent=2)+'\n')
    for case in cases:
        print(json.dumps({k: v for k, v in case.items() if k not in {'trades', 'buyouts', 'top_legality_issues'}}))


if __name__ == '__main__':
    main()
