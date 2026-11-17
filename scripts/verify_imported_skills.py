"""Bounded gameplay validation and publication of imported-skill baseline V7."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import time

from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.history_store import hydrate_save_history
from nba_gm_data.imported_skill_calibration import MARKER
from nba_gm_data.ingest import build_universe
from nba_gm_data.roster_alignment import STARTING_DATA_VERSION
from nba_gm_data.save import canonical_with_save, load_save, set_save_date_phase, write_save
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.schema import to_plain
from nba_gm_data.storage import write_outputs
from audit_replacement_calibration import profile_rows, summarize
from verify_imported_tail import protection, read_baseline, sha, write, DERIVED
from verify_roster_alignment import archive_candidate
from verify_simulation_consistency import business_state, digest, differences

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/imported-skills-v7-2026-10-26'
VERSION = '2026-10-26-imported-skills-v7'
START, TARGET = '2026-10-28', '2026-11-11'


def scope(old, new):
    before = {(t['player_id'], t['trait_key']): t for t in old['traits']}
    after = {(t['player_id'], t['trait_key']): t for t in new['traits']}
    assert before.keys() == after.keys()
    changed = {k for k in before if before[k]['value'] != after[k]['value']}
    report = new['meta']['imported_skill_report']
    reported = {(row['player_id'], key) for row in report['players'] for key in row['trait_changes']}
    assert changed == reported
    assert all(MARKER in after[k]['components'] and abs(after[k]['value']-before[k]['value']) <= 10.000001 for k in changed)
    protected = {pid for (pid, _), t in before.items() if any(k in t['components'] for k in ('manual_calibration', 'imported_rookie_prior'))}
    assert not protected & {pid for pid, _ in changed}
    for key in old.keys()-DERIVED-{'traits', 'sources', 'meta'}:
        assert old[key] == new[key], key
    return {'examined_players': report['examined_players'], 'changed_players': len({pid for pid, _ in changed}),
            'changed_traits': len(changed), 'by_trait': dict(Counter(key for _, key in changed)),
            'protected_profiles_medicals_contracts_prospects_preserved': True}


def advance(canonical, path, seed, mode, *, root=ROOT):
    calls, started = [], time.perf_counter()
    while (current := load_save(path)['state']['current_date']) < TARGET:
        payload = {'save_path': str(path), 'seed': seed}
        if mode == 'daily':
            payload['days'] = 1
        else:
            payload.update(to_date=TARGET, checkpoint_days=31)
        result = dispatch_app_action('advance_save', payload, root=root, save_dir=path.parent, canonical=canonical)
        reached = load_save(path)['state']['current_date']
        assert current < reached <= TARGET, (current, reached, result.get('status'))
        calls.append({'from': current, 'through': reached, 'status': result.get('status')})
    saved = hydrate_save_history(path, load_save(path))
    assert saved['state']['current_date'] == TARGET
    active = canonical_with_save(canonical, saved)
    expected = {t['player_id'] for t in canonical['traits']}
    assert expected <= {t['player_id'] for t in active['traits']}
    logs = [row for row in saved['player_game_logs'] if START < row['date'] <= TARGET]
    games = defaultdict(lambda: defaultdict(float))
    for row in logs:
        games[row['game_id']][row['team_id']] += row['minutes']
    assert games and all(len(teams) == 2 for teams in games.values())
    for teams in games.values():
        minutes = list(teams.values())
        assert abs(minutes[0]-minutes[1]) < .15, 'Unequal team minutes'
        overtime = round((minutes[0]-240)/25)
        assert overtime >= 0 and abs(minutes[0]-(240+25*overtime)) < .15, 'Invalid team minutes'
    assert all(r['points'] == 2*r['fgm']+r['fg3m']+r['ftm'] for r in logs), 'Invalid scoring line'
    for key in ('game_results', 'player_game_logs', 'transaction_logs', 'injury_events'):
        ids = [r['id'] for r in saved[key] if r.get('id')]
        assert len(ids) == len(set(ids)), f'Duplicate {key}'
    assert all(0 <= row['fatigue'] <= 100 for row in saved['health_states'])
    affected = {row['player_id'] for row in canonical['meta'].get('imported_skill_report', {}).get('players', [])}
    sampled = {pid: saved['player_season_stats'][pid] for pid in affected if pid in saved['player_season_stats']}
    state = business_state(saved)
    metrics = {'seconds': round(time.perf_counter()-started, 3), 'calls': calls,
               'games': len(games), 'player_game_logs': len(logs), 'date': TARGET,
               'team_game_ppg': round(sum(row['points'] for row in logs)/(2*len(games)), 3),
               'transactions': dict(Counter(r.get('transaction_type') for r in saved['transaction_logs'])),
               'injury_events': len(saved['injury_events']), 'state_digest': digest(state),
               'affected_player_season_stats': sampled, 'minutes_and_unique_history_valid': True}
    return state, metrics


def gameplay(old, previous, new):
    report = {'scope': 'Disposable 14-day regular-season windows crossing a month boundary; not long-term balance proof.', 'cases': []}
    states = {}
    for seed in (17, 29):
        for label, canonical in (('v5', old), ('v7', new)):
            directory = OUT/f'gameplay/{seed}-{label}'
            created = dispatch_app_action('create_save', {'team': 'TOR', 'seed': seed, 'save_name': label},
                root=ROOT, save_dir=directory, canonical=deepcopy(canonical))
            path = Path(created['save_path'])
            saved = load_save(path)
            assert saved['meta']['starting_data_version'] == canonical['meta']['starting_data_version']
            set_save_date_phase(saved, START)
            write_save(path, saved)
            if label == 'v7' and seed == 17:
                archive = create_export(path)
                daily = OUT/'gameplay/17-v7-daily/career.json'
                restore_export(daily, archive)
            state, metrics = advance(deepcopy(canonical), path, seed, 'bulk')
            states[(seed, label)] = state
            report['cases'].append({'seed': seed, 'baseline': label, **metrics})
            write(OUT/'gameplay-progress.json', report)
            print(json.dumps({'seed': seed, 'baseline': label, 'games': metrics['games'], 'seconds': metrics['seconds']}), flush=True)
    state, metrics = advance(deepcopy(new), daily, 17, 'daily')
    diff = differences(states[(17, 'v7')], state)
    assert not diff, diff
    report['daily_bulk_same_business_state'] = True
    report['daily_replay'] = metrics
    # Loading the identical V6 career through V7 must still use the archived V6.
    directory = OUT/'gameplay/legacy'
    created = dispatch_app_action('create_save', {'team': 'GSW', 'seed': 17, 'save_name': 'legacy'},
        root=ROOT, save_dir=directory, canonical=deepcopy(previous))
    path = Path(created['save_path'])
    saved = load_save(path)
    set_save_date_phase(saved, START)
    write_save(path, saved)
    archive = create_export(path)
    a, b = directory/'old-entry/career.json', directory/'new-entry/career.json'
    for target in (a, b):
        restore_export(target, archive)
    left, _ = advance(deepcopy(previous), a, 17, 'bulk')
    right, _ = advance(deepcopy(new), b, 17, 'bulk')
    assert not differences(left, right), differences(left, right)
    report['legacy_v6_gameplay_identical_through_v7'] = True
    report['legacy_digest'] = digest(left)
    report['same_seed_games_changed_between_v5_and_v7'] = {
        str(seed): states[(seed, 'v5')]['player_season_stats'] != states[(seed, 'v7')]['player_season_stats']
        for seed in (17, 29)}
    assert all(report['same_seed_games_changed_between_v5_and_v7'].values()), 'Skills are not reaching gameplay'
    return report


def main(publish):
    assert STARTING_DATA_VERSION == VERSION
    OUT.mkdir(parents=True, exist_ok=False)
    protected = protection()
    old = read_baseline('2026-10-23-forward-tuning-v5')
    previous = read_baseline('2026-10-26-imported-tail-v6')
    universe = build_universe(ROOT)
    new = to_plain(universe)
    checks = scope(previous, new)
    assert new == to_plain(build_universe(ROOT))
    write_outputs(universe, OUT/'candidate')
    populations = {label: profile_rows(data) for label, data in (('v5', old), ('v6', previous), ('v7', new))}
    by_name = {label: {p['name']: p for p in rows} for label, rows in populations.items()}
    changes = [{**row, 'before': by_name['v6'][row['name']]['overall'],
                'after': by_name['v7'][row['name']]['overall']}
               for row in new['meta']['imported_skill_report']['players']]
    report = {'version': VERSION, 'scope': checks, 'changes': changes,
              'populations': {k: summarize(v) for k, v in populations.items()}}
    write(OUT/'candidate-review.json', report)
    report['gameplay'] = gameplay(old, previous, new)
    assert all(sha(p) == value for p, value in protected.items()), 'Protected save/archive changed'
    if publish:
        archive_candidate(new)
        registry_path = ROOT/'data/canonical/baselines/registry.json'
        registry = json.loads(registry_path.read_text())
        assert VERSION not in registry['versions']
        registry['versions'][VERSION] = f'{VERSION}.json.gz'
        write(registry_path, registry)
        write_outputs(universe, ROOT/'data/canonical')
        assert read_baseline(VERSION) == new
    assert all(sha(p) == value for p, value in protected.items())
    report.update(status='passed', published=publish, protected_files=protected, protected_files_unchanged=True)
    write(OUT/'verification.json', report)
    print(json.dumps({'status': 'passed', 'published': publish, 'scope': checks}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    main(parser.parse_args().publish)
