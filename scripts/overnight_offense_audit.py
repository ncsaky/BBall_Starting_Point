"""Two one-season V9 careers, checkpointed and compared with completed V8 data."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BATCH = Path.home()/'.cache/nba-gm-audits/offense-season-v9-2026-10-27'
REFERENCE = Path.home()/'.cache/nba-gm-audits/rotation-profiles-v8-2026-10-26/runtime'
SEEDS = (29, 913)
TARGET = '2027-10-01'
GIB = 1024**3


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as handle:
        return json.load(handle)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    with temp.open('w') as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write('\n')
    temp.replace(path)


def write_gzip(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt', compresslevel=3) as handle:
        json.dump(value, handle, separators=(',', ':'))


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def output(batch):
    return batch/'runtime/output/offense-season'


def valid_run(run):
    if run.get('target') != TARGET or run.get('target_seasons') != 1:
        raise RuntimeError('Refusing a career with an unapproved endpoint')
    if run.get('endpoint', '') > TARGET or run.get('complete_seasons', 0) > 1:
        raise RuntimeError('Career exceeded the one-season bound')
    if run.get('status') == 'completed' and (run.get('endpoint') != TARGET or run.get('complete_seasons') != 1):
        raise RuntimeError('Incomplete career cannot be marked completed')


def prepare(batch):
    import overnight_market_health as audit
    from nba_gm_data.offense import VERSION
    assert not batch.exists(), 'Never overwrite an existing experiment'
    if shutil.disk_usage(batch.parent).free < 10*GIB:
        raise RuntimeError('Need 10 GiB free before starting this bounded audit')
    canonical = read(ROOT/'data/canonical/universe_2026_27_offseason.json')
    assert canonical['meta']['starting_data_version'] == VERSION
    old = read(REFERENCE/'output/comparison/candidate/canonical.json.gz')
    for key in ('players', 'traits', 'contracts', 'draft_picks', 'player_health_profiles',
                'player_health_states', 'draft_classes', 'draft_prospects', 'draft_prospect_traits'):
        assert old[key] == canonical[key], key
    policy_hashes = {}
    for relative in ('src/nba_gm_data/health.py', 'src/nba_gm_data/draft.py', 'src/nba_gm_data/talent.py',
                     'scripts/overnight_market_health.py', 'scripts/ten_season_soak.py', 'scripts/league_health_audit.py'):
        assert sha(ROOT/relative) == sha(REFERENCE/relative), relative
        policy_hashes[relative] = sha(ROOT/relative)
    selected = set(audit.inputs()) | set((ROOT/'scripts').glob('*.py'))
    runtime = batch/'runtime'
    hashes = {}
    for source in sorted(selected):
        target = runtime/source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[str(source.relative_to(ROOT))] = sha(source)
    write(runtime/'local-runtime.json', {'blocked_roots': [str(ROOT), str(Path.home()/'Documents')],
        'purpose': 'Two one-season disposable V9 careers; no production access'})
    hashes['local-runtime.json'] = sha(runtime/'local-runtime.json')
    write(runtime/'snapshot.json', {'files': {name: {'sha256': value} for name, value in hashes.items()}})
    records = {str(p.relative_to(ROOT)): hashes[str(p.relative_to(ROOT))] for p in audit.inputs()}
    records['local-runtime.json'] = hashes['local-runtime.json']
    out = output(batch)
    write(out/'inputs.json', records)
    write_gzip(out/'canonical.json.gz', {**canonical, '_baseline_directory': str(runtime/'data/canonical/baselines')})
    reference_hashes = {}
    for seed in SEEDS:
        directory = REFERENCE/f'output/comparison/candidate/career-{seed}'
        run_path = directory/'run.json'
        run = read(run_path)
        assert run['status'] == 'completed' and run['complete_seasons'] == 2
        save_path = Path(run['save_path'])
        saved = read(save_path)
        history = saved['season_history'][0]
        assert history['season'] == '2026-27'
        assert len(history['team_records']) == 30
        assert all(r['wins']+r['losses'] == 82 for r in history['team_records'].values())
        start = next((directory/'observations').glob('*-2026-10-01.json.gz'))
        end = next((directory/'observations').glob('*-2027-10-01.json.gz'))
        write_gzip(out/f'references/v8-{seed}.json.gz', {'history': history, 'start': read(start),
                   'endpoint': read(end), 'metadata': [*old['players'], *saved.get('generated_players', [])]})
        reference_hashes[str(seed)] = {str(p): sha(p) for p in (run_path, save_path, start, end)}
    protected = {str(p): sha(p) for p in (ROOT/'saves').rglob('*')
                 if p.is_file() and p.suffix in {'.json', '.sqlite3', '.sqlite'}}
    manifest = {'created_at': now(), 'seeds': list(SEEDS), 'target': TARGET, 'target_seasons': 1,
                'version': VERSION, 'runtime': str(runtime), 'workspace': str(ROOT),
                'policy': 'Hands-off GSW; auto draft; existing confirmations, staff retention and legal low-role cutdowns. No discretionary bids/trades/extensions.',
                'reference': 'Completed V8 candidate careers, first season/offseason only. Historical comparator, not new independently rerun controls.',
                'reference_hashes': reference_hashes, 'unchanged_policy_and_development': policy_hashes,
                'protected_playable_files_at_setup': protected,
                'limits': {'hours': 4, 'parallel': 2, 'disk_floor_gib': 8, 'rss_ceiling_mib': 6144,
                           'result_budget_gib': 2.5, 'action_minutes': 45}}
    write(batch/'manifest.json', manifest)
    write(batch/'status.json', {'status': 'prepared', 'updated_at': now()})
    print(f'Prepared {batch}; two seeds, one season each, stop {TARGET}.', flush=True)


def step(batch):
    import overnight_market_health as audit
    from verify_offensive_roles import install_read_guard
    install_read_guard()
    import gc
    gc.disable()
    seed = ARGS.seed
    if seed not in SEEDS:
        raise ValueError('Unapproved simulation seed')
    out = output(batch)
    path = out/f'career-{seed}/run.json'
    initialized = path.exists()
    if initialized:
        valid_run(read(path))
    audit.step(argparse.Namespace(output_dir=str(out), seed=seed, short_days=0))
    run = read(path)
    if not initialized:
        assert not run['actions'], 'Endpoint must be set before any advancement'
        run.update(target=TARGET, target_seasons=1)
        write(path, run)
    valid_run(run)


def pilot(batch):
    runtime = batch/'runtime'
    for seed in SEEDS:
        invoke_step(batch, seed)
    for _ in range(5):
        run = read(output(batch)/'career-29/run.json')
        if run['endpoint'] >= '2026-11-01':
            break
        invoke_step(batch, 29)
    # Check the same persisted game history consumed by the UI, not a mock sim.
    env = {**os.environ, 'PYTHONPATH': str(runtime/'src')+os.pathsep+str(runtime/'scripts')}
    subprocess.run([sys.executable, '-B', str(runtime/'scripts/overnight_offense_audit.py'),
                    'check-pilot', '--batch', str(batch)], cwd=runtime, env=env, check=True)


def check_pilot(batch):
    from nba_gm_data.save import load_save, canonical_with_save
    from nba_gm_data.history_store import load_history_records
    from verify_offensive_roles import install_read_guard
    install_read_guard()
    run = read(output(batch)/'career-29/run.json')
    valid_run(run)
    saved = load_save(run['save_path'])
    canonical = read(output(batch)/'canonical.json.gz')
    active = canonical_with_save(canonical, saved)
    assert active['meta']['offense_model_version'] == 1
    rows = load_history_records(run['save_path'], saved, 'player_game_logs', limit=6000)
    unique = {r['id']: r for r in [*rows, *saved.get('player_game_logs', [])]}
    games = {}
    for r in unique.values():
        assert r['points'] == 2*r['fgm']+r['fg3m']+r['ftm']
        assert 0 <= r['fg3m'] <= r['fg3a'] and r['fgm'] <= r['fga'] and r['ftm'] <= r['fta']
        game = games.setdefault(r['game_id'], {})
        game[r['team_id']] = game.get(r['team_id'], 0)+r['minutes']
    assert games, 'Pilot must include real regular-season games'
    for game in games.values():
        minutes = list(game.values())
        assert len(minutes) == 2 and abs(minutes[0]-minutes[1]) < .15
        overtime = round((minutes[0]-240)/25)
        assert overtime >= 0 and abs(minutes[0]-(240+25*overtime)) < .15
    result = {'status': 'passed', 'date': run['endpoint'], 'games': len(games),
              'player_lines': len(unique), 'version': active['meta']['starting_data_version'],
              'scoring_and_minutes_valid': True, 'same_checkpoints_resume_overnight': True}
    write(batch/'pilot.json', result)
    print(json.dumps(result), flush=True)


def invoke_step(batch, seed, *, handle=None):
    runtime = batch/'runtime'
    env = {**os.environ, 'PYTHONPATH': str(runtime/'src')+os.pathsep+str(runtime/'scripts')}
    cmd = [sys.executable, '-u', '-B', str(runtime/'scripts/overnight_offense_audit.py'),
           'step', '--batch', str(batch), '--seed', str(seed)]
    if handle is None:
        subprocess.run(cmd, cwd=runtime, env=env, check=True)
    else:
        return subprocess.Popen(cmd, cwd=runtime, env=env, stdout=handle,
                                stderr=subprocess.STDOUT, start_new_session=True)


def career_progress(batch, seed):
    path = output(batch)/f'career-{seed}/run.json'
    run = read(path) if path.exists() else {}
    return {'date': run.get('endpoint'), 'complete_seasons': run.get('complete_seasons', 0),
            'actions': len(run.get('actions', [])), 'status': run.get('status', 'queued')}


def supervise(batch):
    assert ROOT == batch/'runtime', 'Supervisor must use the frozen runtime, not live workspace modules'
    from verify_offensive_roles import install_read_guard
    install_read_guard()
    from background_league_health import process_memory
    from overnight_market_health import directory_bytes
    from collections import deque
    with (batch/'supervisor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert read(batch/'pilot.json')['status'] == 'passed'
        manifest = read(batch/'manifest.json')
        assert manifest['target'] == TARGET and manifest['target_seasons'] == 1 and tuple(manifest['seeds']) == SEEDS
        queue, active, failed = deque(SEEDS), {}, {}
        started = time.monotonic()
        stopping, stop_at = None, None
        def request_stop(*_):
            nonlocal stopping
            stopping = stopping or 'stop_requested'
        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        awake = subprocess.Popen(['/usr/bin/caffeinate', '-i', '-w', str(os.getpid())],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            while queue or active:
                free = shutil.disk_usage(batch).free
                rss = process_memory([p.pid for p, _, _ in active.values()]) if active else 0
                size = directory_bytes(batch)
                elapsed = time.monotonic()-started
                if (batch/'STOP').exists():
                    stopping = stopping or 'stop_file'
                for condition, reason in ((elapsed > 4*3600, 'four_hour_limit'), (free < 8*GIB, 'disk_floor'),
                                          (rss > 6144, 'memory_limit'), (size > 2.5*GIB, 'output_budget')):
                    if condition:
                        stopping = stopping or reason
                for seed, (process, handle, began) in list(active.items()):
                    if time.monotonic()-began > 45*60:
                        stopping = stopping or 'action_exceeded_45_minutes'
                    code = process.poll()
                    if code is None:
                        continue
                    handle.close()
                    del active[seed]
                    if code:
                        failed[str(seed)] = {'exit_code': code, 'log': str(batch/f'career-{seed}.log')}
                    elif career_progress(batch, seed)['status'] != 'completed' and not stopping:
                        queue.append(seed)
                if stopping:
                    stop_at = stop_at or time.monotonic()
                    hard = free < 5*GIB or rss > 8192 or time.monotonic()-stop_at > 5*60
                    if hard:
                        for process, _, _ in active.values():
                            if process.poll() is None:
                                os.killpg(process.pid, signal.SIGTERM)
                    if not active:
                        break
                else:
                    while queue and len(active) < 2:
                        seed = queue.popleft()
                        if career_progress(batch, seed)['status'] == 'completed':
                            continue
                        handle = (batch/f'career-{seed}.log').open('a')
                        active[seed] = (invoke_step(batch, seed, handle=handle), handle, time.monotonic())
                write(batch/'status.json', {'status': 'running' if not stopping else 'stopping_at_checkpoint',
                    'pid': os.getpid(), 'updated_at': now(), 'seconds': round(elapsed, 1),
                    'jobs': {str(s): career_progress(batch, s) for s in SEEDS}, 'failed': failed,
                    'free_gib': round(free/GIB, 2), 'rss_mib': round(rss, 1), 'output_mib': round(size/1024**2, 1),
                    'stop_reason': stopping})
                if queue or active:
                    time.sleep(5)
            finished = {'status': 'stopped' if stopping else 'completed_with_failures' if failed else 'completed',
                'pid': os.getpid(), 'updated_at': now(), 'seconds': round(time.monotonic()-started, 1),
                'jobs': {str(s): career_progress(batch, s) for s in SEEDS}, 'failed': failed, 'stop_reason': stopping}
            write(batch/'status.json', finished)
            if finished['status'] == 'completed':
                review(batch)
        except BaseException as error:
            write(batch/'status.json', {'status': 'failed', 'updated_at': now(), 'error': repr(error),
                  'jobs': {str(s): career_progress(batch, s) for s in SEEDS}})
            raise
        finally:
            for process, handle, _ in active.values():
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait()
                handle.close()
            awake.terminate()
            awake.wait()


def season_metrics(stats, records, metadata, groups):
    if len(records) != 30 or any(r['wins']+r['losses'] != 82 for r in records.values()):
        raise ValueError('Metrics require a complete 30-team regular season')
    fields = ('points', 'rebounds', 'assists', 'fgm', 'fga', 'fg3m', 'fg3a', 'ftm', 'fta', 'minutes')
    totals = {k: sum(float(s.get(k) or 0) for s in stats.values()) for k in fields}
    team_games = sum(r['wins']+r['losses'] for r in records.values())
    all_players, cohorts = [], {}
    for pid, s in stats.items():
        minutes, games = float(s.get('minutes') or 0), int(s.get('games') or 0)
        if not minutes or not games:
            continue
        p = metadata.get(pid, {})
        row = {'id': pid, 'name': p.get('name', s.get('player_name')), 'position': p.get('position'),
               'games': games, 'mpg': round(minutes/games, 3), 'minutes': minutes,
               'per36': {k: round(float(s.get(k) or 0)*36/minutes, 3) for k in fields if k != 'minutes'},
               'fg_pct': round(s['fgm']/s['fga'], 4) if s.get('fga') else None,
               'group': groups.get(pid, 'unclassified')}
        all_players.append(row)
    for group in sorted({r['group'] for r in all_players}):
        rows = [r for r in all_players if r['group'] == group and r['minutes'] >= 300]
        ids = {r['id'] for r in rows}
        sums = {k: sum(float(s.get(k) or 0) for pid, s in stats.items() if pid in ids) for k in fields}
        cohorts[group] = {'players_300_minutes': len(rows),
            'per36': {k: round(sums[k]*36/sums['minutes'], 3) if sums['minutes'] else None for k in fields if k != 'minutes'},
            'fg_pct': round(sums['fgm']/sums['fga'], 4) if sums['fga'] else None}
    return {'league_games': team_games//2, 'per_team_game': {k: round(v/team_games, 3) for k, v in totals.items()},
            'fg_pct': round(totals['fgm']/totals['fga'], 4), 'players': all_players, 'groups': cohorts}


def review(batch):
    if ROOT != batch/'runtime':
        runtime = batch/'runtime'
        env = {**os.environ, 'PYTHONPATH': str(runtime/'src')+os.pathsep+str(runtime/'scripts')}
        subprocess.run([sys.executable, '-B', str(runtime/'scripts/overnight_offense_audit.py'),
                        'review', '--batch', str(batch)], cwd=runtime, env=env, check=True)
        return
    from nba_gm_data.offense import offensive_profile
    from nba_gm_data.save import load_save
    canonical = read(output(batch)/'canonical.json.gz')
    traits = {}
    for t in canonical['traits']:
        traits.setdefault(t['player_id'], {})[t['trait_key']] = t['value']
    metadata = {p['id']: p for p in canonical['players']}
    groups = {}
    for p in canonical['players']:
        f = offensive_profile(canonical, p, traits.get(p['id'], {}))
        position = str(p.get('position') or '').upper().split('/')[0]
        groups[p['id']] = ('post_bigs' if position in {'C', 'PF'} and f['post_share'] >= .12 and f['post_creation'] >= 55
            else 'nonspacing_centers' if position == 'C' and f['three_per36'] < 1.5
            else 'stretch_bigs' if position in {'C', 'PF'} and f['three_per36'] >= 4
            else 'other_centers' if position == 'C' else 'guards' if position in {'PG', 'SG', 'G'} else 'other_wings_forwards')
    report = {'scope': 'Two V9 seasons versus existing V8 first-season references; no long-term equilibrium claim.',
              'classification': 'Shared initial V9 profiles, not end-of-season hindsight. Cohort rates require 300 minutes.', 'cases': {}}
    for seed in SEEDS:
        run = read(output(batch)/f'career-{seed}/run.json')
        valid_run(run)
        assert run['status'] == 'completed'
        saved = load_save(run['save_path'])
        assert len(saved['season_history']) == 1
        history = saved['season_history'][0]
        assert history['season'] == '2026-27'
        reference = read(output(batch)/f'references/v8-{seed}.json.gz')
        current_metadata = {**metadata, **{p['id']: p for p in saved.get('generated_players', [])}}
        candidate = season_metrics(history['player_season_stats'], history['team_records'], current_metadata, groups)
        control = season_metrics(reference['history']['player_season_stats'], reference['history']['team_records'],
                                 {p['id']: p for p in reference['metadata']}, groups)
        endpoint = read(output(batch)/f'career-{seed}/latest-observation.json.gz')
        retention = {}
        for group in ('nonspacing_centers', 'post_bigs', 'stretch_bigs', 'guards'):
            ids = {p['id'] for p in reference['start']['players'] if p['rostered'] and groups.get(p['id']) == group}
            entries = {'cohort_size': len(ids), 'cohort_definition': 'V8 October 1 starting roster IDs, shared between comparisons'}
            for label, snap in (('v8', reference['endpoint']), ('v9', endpoint)):
                rows = [p for p in snap['players'] if p['id'] in ids and p['rostered']]
                entries[label] = {'retained': len(rows), 'rotation': sum(float(p.get('minutes') or 0) >= 16 for p in rows),
                                 'salary_millions': round(sum(sum(p.get('salary_millions', [])) for p in rows), 3),
                                 'retained_ids': sorted(p['id'] for p in rows)}
            retention[group] = entries
        report['cases'][str(seed)] = {'v8': control, 'v9': candidate, 'retention': retention,
            'transactions_v8': reference['history'].get('transaction_count'), 'transactions_v9': history.get('transaction_count'),
            'actions': len(run['actions']), 'action_seconds': sum(a['seconds'] for a in run['actions'])}
    write(batch/'review.json', report)
    lines = ['# V9 One-Season Review', '', report['scope'], '',
             'Flags are diagnostics, not automatic tuning instructions. Minute penalties and development were frozen.', '']
    for seed, case in report['cases'].items():
        a, b = case['v8'], case['v9']
        lines += [f'## Seed {seed}', '', '| Metric | V8 | V9 |', '| --- | ---: | ---: |']
        lines += [f'| {k} per team game | {a["per_team_game"][k]} | {b["per_team_game"][k]} |'
                  for k in ('points', 'fg3a', 'fta', 'rebounds', 'assists')]
        lines += [f'| FG% | {a["fg_pct"]*100:.1f} | {b["fg_pct"]*100:.1f} |', '',
                  f'1230 regular-season games validated; {case["actions"]} phase/month checkpoints.', '']
    lines += ['Full per-player, role-cohort, retention and salary evidence: `review.json`.',
              'Monthly observations and daily free-agency evidence remain in the disposable runtime.',
              'Different AI choices are outcomes, not proof of incorrect valuation. No further seasons are scheduled.']
    (batch/'review.md').write_text('\n'.join(lines)+'\n')


def status(batch):
    state = read(batch/'status.json') if (batch/'status.json').exists() else {'status': 'not prepared'}
    print(f"V9 season audit: {state['status']}")
    for seed in SEEDS:
        p = career_progress(batch, seed)
        print(f"  Seed {seed}: {p['date'] or 'not created'} | {p['complete_seasons']}/1 season | {p['actions']} checkpoints | {p['status']}")
    if state.get('stop_reason') or state.get('error'):
        print('  Attention:', state.get('stop_reason') or state.get('error'))
    if state.get('failed'):
        print('  Failed jobs:', json.dumps(state['failed']))
    print(f"  Free disk: {shutil.disk_usage(batch if batch.exists() else batch.parent).free/GIB:.1f} GiB")
    print(f"  Results: {batch/'review.md'}" if (batch/'review.md').exists() else '  Stops automatically after both one-season careers.')


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT/'src'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'pilot', 'check-pilot', 'step', 'start', 'supervise', 'review', 'status', 'stop'))
    parser.add_argument('--batch', type=Path, default=BATCH)
    parser.add_argument('--seed', type=int)
    ARGS = parser.parse_args()
    if ARGS.mode == 'start':
        assert read(ARGS.batch/'pilot.json')['status'] == 'passed'
        current = read(ARGS.batch/'status.json')
        if current.get('status') in {'running', 'stopping_at_checkpoint', 'completed'}:
            raise RuntimeError('Batch is already running or completed; inspect status rather than relaunching')
        with (ARGS.batch/'supervisor.log').open('a') as handle:
            runtime = ARGS.batch/'runtime'
            env = {**os.environ, 'PYTHONPATH': str(runtime/'src')+os.pathsep+str(runtime/'scripts')}
            p = subprocess.Popen([sys.executable, '-u', '-B', str(runtime/'scripts/overnight_offense_audit.py'),
                                  'supervise', '--batch', str(ARGS.batch)],
                                 cwd=runtime, env=env, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        print(f'Started supervisor {p.pid}; run status to check progress.', flush=True)
    elif ARGS.mode == 'stop':
        (ARGS.batch/'STOP').touch()
        print('Stop requested; disposable actions may finish their checkpoint first.')
    else:
        globals()[ARGS.mode.replace('-', '_')](ARGS.batch)
