"""Bounded V9 verification in a frozen local runtime, then guarded publication."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/interior-offense-v9-2026-10-27'
BATCH = Path.home()/'.cache/nba-gm-audits/interior-offense-v9-2026-10-27'


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
    temp.replace(path)


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def local_read_path(value):
    raw = os.fsdecode(value)
    parsed = urlsplit(raw)
    if parsed.scheme == 'file':
        raw = unquote(parsed.path)
    return Path(os.path.abspath(raw)).resolve()


def install_read_guard():
    blocked = [Path(p).resolve() for p in read(ROOT/'local-runtime.json')['blocked_roots']]
    def guard(event, args):
        if event not in {'open', 'sqlite3.connect', 'os.chdir'} or not args:
            return
        value = args[0]
        if isinstance(value, (str, bytes, os.PathLike)):
            path = local_read_path(value)
            if any(path == parent or path.is_relative_to(parent) for parent in blocked):
                raise PermissionError(f'Frozen V9 replay refused workspace access: {path}')
    sys.addaudithook(guard)


def prepare():
    from nba_gm_data.ingest import build_universe
    from nba_gm_data.storage import write_outputs
    from nba_gm_data.schema import to_plain
    from nba_gm_data.offense import VERSION
    import overnight_market_health as audit
    assert not BATCH.exists(), 'Preserve previous verification evidence'
    runtime = BATCH/'runtime'
    selected = set(audit.inputs()) | set((ROOT/'scripts').glob('*.py'))
    for source in selected:
        target = runtime/source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    universe = build_universe(ROOT)
    candidate = to_plain(universe)
    before = read(ROOT/'data/canonical/universe_2026_27_offseason.json')
    for key in ('players', 'traits', 'contracts', 'draft_picks', 'player_health_profiles',
                'player_health_states', 'injury_events', 'draft_classes', 'draft_prospects', 'draft_prospect_traits'):
        assert before[key] == candidate[key], key
    write_outputs(universe, OUT/'candidate')
    write_outputs(universe, runtime/'data/canonical')
    directory = runtime/'data/canonical/baselines'
    with gzip.open(directory/f'{VERSION}.json.gz', 'wt') as handle:
        json.dump(candidate, handle)
    registry = read(directory/'registry.json')
    registry['versions'][VERSION] = f'{VERSION}.json.gz'
    write(directory/'registry.json', registry)
    write(runtime/'local-runtime.json', {'blocked_roots': [str(ROOT)], 'purpose': 'Seven-day V9 replay only'})
    shutil.copy2(OUT/'legacy-golden.json', runtime/'legacy-golden.json')
    shutil.copy2(OUT/'before-sim.py', runtime/'before-sim.py')
    fingerprints = {str(p.relative_to(ROOT)): sha(p) for p in selected}
    write(OUT/'verification-inputs.json', fingerprints)
    print(runtime, flush=True)


def worker():
    from audit_specialist_impact import make_lineup
    from nba_gm_data.app_actions import dispatch_app_action
    from nba_gm_data.save import canonical_with_save, load_save, set_save_date_phase, write_save
    from nba_gm_data.save_recovery import create_export, restore_export
    from nba_gm_data.sim import distribute_player_lines, player_feature_vector, lineup_feature_vector, simulate_team_line
    from nba_gm_data.transactions import build_player_asset_valuations
    from nba_gm_data.save import player_attribute_summary
    import verify_imported_skills as replay
    from verify_simulation_consistency import differences, digest, business_state
    import random
    install_read_guard()
    replay.TARGET = '2026-11-04'
    candidate = read(ROOT/'data/canonical/universe_2026_27_offseason.json')
    with gzip.open(ROOT/'data/canonical/baselines/2026-10-26-rotation-profiles-v8.json.gz', 'rt') as handle:
        old = json.load(handle)
    golden = read(ROOT/'legacy-golden.json')
    spec = importlib.util.spec_from_file_location('nba_gm_data.sim_reference', ROOT/'before-sim.py')
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    for entry in golden['lineups']:
        local, pool = make_lineup(old, entry['name'], guard=entry['name'] == 'Jamal Shead')
        assert entry['features'] == player_feature_vector(local, pool[0]['player']).features
        assert entry['attrs'] == player_attribute_summary(local, pool[0]['player']['id'])
        assert entry['lines'] == [distribute_player_lines(local, {'id': 'audit_home', 'abbrev': 'AUH'}, pool,
                                 114, 100, random.Random(seed)) for seed in (17, 29, 913)]
        feat = lineup_feature_vector(local, pool)
        assert feat == reference.lineup_feature_vector(local, pool)
        for seed in range(16):
            args = (local, {'id': 'audit_home', 'abbrev': 'AUH'}, {'id': 'opponent', 'abbrev': 'OPP'},
                    pool, feat, feat, None, None)
            assert simulate_team_line(*args, random.Random(seed)) == reference.simulate_team_line(*args, random.Random(seed))
    assert golden['valuations'] == [vars(v) for v in build_player_asset_valuations(old)]
    report = {'legacy_golden_exact': True, 'cases': [], 'scope': 'Seven days across a month boundary; no season run.'}
    def fresh(canonical, directory, seed):
        result = dispatch_app_action('create_save', {'team': 'GSW', 'seed': seed, 'save_name': 'offense'},
                                    root=ROOT, save_dir=directory, canonical=deepcopy(canonical))
        path = Path(result['save_path'])
        saved = load_save(path)
        set_save_date_phase(saved, replay.START)
        write_save(path, saved)
        return create_export(path)
    for seed in (17, 29):
        archive = fresh(candidate, ROOT/f'output/{seed}-source', seed)
        states = {}
        for mode in ('bulk', 'daily', 'reload'):
            path = ROOT/f'output/{seed}-{mode}/career.json'
            restore_export(path, archive)
            if mode == 'reload':
                replay.TARGET = '2026-10-31'
                replay.advance(deepcopy(candidate), path, seed, 'bulk', root=ROOT)
                midway = create_export(path)
                path = ROOT/f'output/{seed}-{mode}-restored/career.json'
                restore_export(path, midway)
                replay.TARGET = '2026-11-04'
            state, metrics = replay.advance(deepcopy(candidate), path, seed, mode if mode != 'reload' else 'bulk', root=ROOT)
            states[mode] = state
            report['cases'].append({'seed': seed, 'mode': mode, **metrics})
            print(json.dumps({'seed': seed, 'mode': mode, 'games': metrics['games'], 'seconds': metrics['seconds']}), flush=True)
            write(ROOT/'verification-progress.json', report)
        for mode in ('daily', 'reload'):
            assert not differences(states['bulk'], states[mode]), differences(states['bulk'], states[mode])
        dispatch_app_action('advance_save', {'save_path': str(path), 'to_date': replay.TARGET, 'seed': seed},
                            root=ROOT, save_dir=path.parent, canonical=deepcopy(candidate))
        from nba_gm_data.history_store import hydrate_save_history
        repeated = business_state(hydrate_save_history(path, load_save(path)))
        assert not differences(states['reload'], repeated), differences(states['reload'], repeated)
        report[f'seed_{seed}_digest'] = digest(states['bulk'])
    archive = fresh(old, ROOT/'output/legacy-source', 29)
    states = []
    for label, entry_point in (('old', old), ('new', candidate)):
        path = ROOT/f'output/legacy-{label}/career.json'
        restore_export(path, archive)
        state, metrics = replay.advance(deepcopy(entry_point), path, 29, 'bulk', root=ROOT)
        states.append(state)
        report['cases'].append({'legacy': label, **metrics})
    assert not differences(*states), differences(*states)
    report.update(status='passed', daily_bulk_reload_identical=True, repeat_call_identical=True,
                  legacy_app_replay_identical=True, games_checked=sum(c['games'] for c in report['cases']))
    write(ROOT/'verification.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}), flush=True)


def publish():
    from nba_gm_data.ingest import build_universe
    from nba_gm_data.offense import VERSION
    from nba_gm_data.schema import to_plain
    from nba_gm_data.storage import write_outputs
    from verify_roster_alignment import archive_candidate
    report = read(BATCH/'runtime/verification.json')
    assert report['status'] == 'passed'
    fingerprints = read(OUT/'verification-inputs.json')
    assert all(sha(ROOT/name) == value for name, value in fingerprints.items()), 'Inputs changed during verification'
    for path, value in read(OUT/'legacy-golden.json')['protected'].items():
        assert sha(Path(path)) == value, f'Protected save/archive changed: {path}'
    universe = build_universe(ROOT)
    assert to_plain(universe) == read(OUT/'candidate/universe_2026_27_offseason.json')
    archive_candidate(to_plain(universe))
    registry_path = ROOT/'data/canonical/baselines/registry.json'
    registry = read(registry_path)
    assert VERSION not in registry['versions'], 'Do not overwrite published baselines'
    registry['versions'][VERSION] = f'{VERSION}.json.gz'
    write(registry_path, registry)
    # Readers keep their current in-memory universe; individual files replace
    # atomically, without restarting or terminating the development server.
    with tempfile.TemporaryDirectory(dir=ROOT/'data/canonical') as directory:
        paths = write_outputs(universe, directory)
        for path in paths.values():
            os.replace(path, ROOT/'data/canonical'/path.name)
    shutil.copy2(BATCH/'runtime/verification.json', OUT/'verification.json')
    write(OUT/'publication.json', {'version': VERSION, 'status': 'published',
          'existing_saves_and_archives_unchanged': True, 'games_checked': report['games_checked'],
          'server_restarted': False})
    print(f'Published {VERSION}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'worker', 'publish'))
    args = parser.parse_args()
    {'prepare': prepare, 'worker': worker, 'publish': publish}[args.mode]()
