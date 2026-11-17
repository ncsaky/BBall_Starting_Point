"""Bounded real-action verification on disposable saves, never playable careers."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save import create_league_save, load_save, set_save_date_phase, write_save, canonical_with_save
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data import transactions as tx, trade_wants as wants
from verify_simulation_consistency import business_state, differences

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seeds', default='17,29')
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    canonical = load_app_canonical(ROOT)
    report = {'cases': [], 'source_hashes': {name: hashlib.sha256((ROOT/'src/nba_gm_data'/name).read_bytes()).hexdigest()
        for name in ('trade_wants.py', 'team_planning.py', 'transactions.py', 'trade_roster.py')}}
    for seed in map(int, args.seeds.split(',')):
        folder = output/str(seed); folder.mkdir()
        baseline = folder/'baseline.json'
        create_league_save(ROOT, canonical, 'MIN', baseline, seed=seed)
        saved = load_save(baseline); set_save_date_phase(saved, '2027-01-30'); write_save(baseline, saved)
        rows = [{'id': 'youth', 'kind': 'player', 'positions': ['SG', 'SF'], 'conditions': [
                    {'field': 'age', 'op': '<=', 'value': 25}, {'field': 'overall', 'op': '>=', 'value': 75}]},
                {'id': 'draft', 'kind': 'picks', 'round': 1, 'from': 1, 'through': 3, 'quality': 'any', 'protection': 'any'}]
        def action(name, path, **payload):
            return dispatch_app_action(name, {'save_path': str(path), **payload}, root=ROOT, save_dir=folder, canonical=canonical)
        action('set_team_wants', baseline, team='MIN', entries=rows, revision=0)
        archive = create_export(baseline)
        snapshots, runs = {}, {}
        for mode in ('daily_reload', 'bulk'):
            path = folder/f'{mode}.json'; restore_export(path, archive)
            started = time.monotonic()
            if mode == 'bulk':
                action('advance_save', path, to_date='2027-02-01', seed=seed)
            else:
                action('advance_save', path, days=1, seed=seed)
                midway_archive = create_export(path)
                reloaded = folder/'midway-reloaded.json'; restore_export(reloaded, midway_archive)
                path = reloaded
                action('advance_save', path, days=1, seed=seed)
            saved = load_save(path, include_history=True)
            assert saved['state']['current_date'] == '2027-02-01'
            before_read = business_state(saved)
            payload = action('team_wants', path, team='MIN')
            assert before_read == business_state(load_save(path, include_history=True)), 'Reading wants mutated the save.'
            assert len(payload['entries']) == 2
            snapshots[mode] = before_read
            # Replaying a completed endpoint may write a new revision, not new league activity.
            action('advance_save', path, to_date='2027-02-01', seed=seed)
            replay = business_state(load_save(path, include_history=True))
            keys = ('team_trade_wants', 'transaction_logs', 'user_trade_offers', 'roster_overrides',
                    'contract_overrides', 'player_season_stats', 'development_events', 'health_states', 'team_records')
            repeat_equal = all(replay.get(k) == before_read.get(k) for k in keys)
            assert repeat_equal, 'Duplicate or missing business activity on repeated endpoint.'
            runs[mode] = {'seconds': round(time.monotonic()-started, 3), 'offers': len(saved.get('user_trade_offers', [])),
                'transactions': dict(Counter(row.get('transaction_type') for row in saved.get('transaction_logs', []))),
                'games': len(saved.get('schedule_state', {}).get('simulated_game_ids', [])), 'repeat_equal': repeat_equal}
        equal = snapshots['daily_reload'] == snapshots['bulk']
        row = {'seed': seed, 'from': '2027-01-30', 'through': '2027-02-01', 'equal': equal,
               'differences': differences(snapshots['daily_reload'], snapshots['bulk']), 'runs': runs}
        report['cases'].append(row)
        (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(row), flush=True)
    # Use the real baseline to compare published matching with the Finder's display fields.
    active = tx.with_transaction_context(canonical_with_save(canonical, saved))
    summary = []
    for name in ('Rudy Gobert', 'Ivica Zubac'):
        player = next((p for p in active['players'] if p.get('name') == name), None)
        if player:
            summary.append({'name': name, 'facts': wants.player_facts(active, player)})
    report['center_facts'] = summary
    from nba_gm_data.trade_roster import roster_projection, role_opportunity_outlook
    named = {p['name']: p for p in active['players']}
    if all(name in named for name in ('Rudy Gobert', 'Ivica Zubac', 'Andrew Nembhard')):
        gobert, zubac, guard = [named[name] for name in ('Rudy Gobert', 'Ivica Zubac', 'Andrew Nembhard')]
        tid = zubac['team_id']; before = roster_projection(active, tid)
        outcomes = {}
        for label, outgoing in [('zubac_retained', {guard['id']}), ('zubac_replaced', {zubac['id']})]:
            after = roster_projection(active, tid, outgoing, {gobert['id']})
            outcomes[label] = {'strength_delta': round(after['strength']-before['strength'], 4),
                'center_minutes': {pid: after['rotation'].get(pid, 0) for pid in (gobert['id'], zubac['id'])},
                'opportunity': role_opportunity_outlook(active, tid, {gobert['id']}, outgoing, before, after)}
        active['_trade_planning_save']['health_states'] = [{'player_id': zubac['id'], 'availability_status': 'out', 'return_date': '2027-05-01'}]
        after = roster_projection(active, tid, {guard['id']}, {gobert['id']})
        outcomes['zubac_injured'] = role_opportunity_outlook(active, tid, {gobert['id']}, {guard['id']}, before, after)
        report['center_scenarios'] = outcomes
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return 0 if all(row['equal'] for row in report['cases']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
