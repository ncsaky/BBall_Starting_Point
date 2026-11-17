"""Frozen, bounded two-season V7/candidate comparison using real GUI actions."""
import argparse
import gc
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/rotation-profiles-v8-2026-10-26'
BATCH = Path.home()/'.cache/nba-gm-audits/rotation-profiles-v8-2026-10-26'
SEEDS = (29, 913)
VERSION = '2026-10-26-rotation-profiles-v8'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    temp.replace(path)


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def read_gzip(path):
    with gzip.open(path,'rt') as handle:
        return json.load(handle)


def candidate_archive(runtime, candidate):
    directory = runtime/'data/canonical/baselines'
    target = directory/f'{VERSION}.json.gz'
    if target.exists():
        assert read_gzip(target)==candidate
    else:
        with gzip.open(target,'wt',compresslevel=3) as handle:
            json.dump(candidate,handle,separators=(',',':'))
    registry_path = directory/'registry.json'
    registry = json.loads(registry_path.read_text())
    registry['versions'][VERSION] = target.name
    write(registry_path,registry)
    return {str(p.relative_to(runtime)):sha(p) for p in (target,registry_path)}


def prepare(batch):
    import overnight_market_health as audit
    from nba_gm_data.ingest import build_universe
    from nba_gm_data.schema import to_plain
    from nba_gm_data.storage import write_outputs
    from audit_replacement_calibration import profile_rows
    from verify_imported_tail import protection, DERIVED
    assert not batch.exists() and not OUT.exists(), 'Preserve existing experiment evidence'
    assert shutil.disk_usage(batch.parent).free > 12*1024**3, 'Need 12 GiB free'
    candidate = build_universe(ROOT)
    new = to_plain(candidate)
    old = read_gzip(ROOT/'data/canonical/baselines/2026-10-26-imported-skills-v7.json.gz')
    assert new['meta']['starting_data_version']==VERSION
    for key in old.keys()-DERIVED-{'meta','sources','traits'}:
        assert old[key]==new[key], key
    a = {(t['player_id'],t['trait_key']):t for t in old['traits']}
    b = {(t['player_id'],t['trait_key']):t for t in new['traits']}
    assert a.keys()==b.keys()
    automatic = {(p['player_id'],k) for p in new['meta']['rotation_profile_report']['players'] for k in p['trait_changes']}
    names = {p['id']:p['name'] for p in new['players']}
    changes = []
    for key in a:
        if 'manual_calibration' in a[key]['components']:
            assert a[key]['value']==b[key]['value'], key
        if a[key]['value']!=b[key]['value']:
            assert key in automatic or names[key[0]] in {'Amir Coffey','Deandre Ayton'}, key
            changes.append({'name':names[key[0]],'player_id':key[0],'trait':key[1],
                            'before':a[key]['value'],'after':b[key]['value']})
    selected = set(audit.inputs()) | set((ROOT/'scripts').glob('*.py')) | set((ROOT/'data/overrides').glob('*.csv'))
    runtime = batch/'runtime'
    hashes = {}
    for source in sorted(selected):
        target = runtime/source.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        hashes[str(source.relative_to(ROOT))] = sha(source)
        assert sha(target)==sha(source)
    # Nested draft trades may load the default canonical before resolving a
    # save's version. Register the unpublished candidate inside the test copy.
    hashes.update(candidate_archive(runtime,new))
    marker = runtime/'local-runtime.json'
    write(marker,{'blocked_roots':[str(ROOT),str(Path.home()/'Documents')],
                  'purpose':'Bounded two-season disposable comparison; no playable saves'})
    hashes['local-runtime.json'] = sha(marker)
    records = {name:value for name,value in hashes.items() if name in {str(p.relative_to(ROOT)) for p in audit.inputs()}}
    records['local-runtime.json'] = sha(marker)
    records.update({name:value for name,value in hashes.items() if name.startswith('data/canonical/baselines/')})
    for arm, canonical in (('control',old),('candidate',new)):
        out = runtime/f'output/comparison/{arm}'
        out.mkdir(parents=True)
        frozen = {**canonical,'_baseline_directory':str(runtime/'data/canonical/baselines')}
        with gzip.open(out/'canonical.json.gz','wt',compresslevel=3) as handle:
            json.dump(frozen,handle,separators=(',',':'))
        write(out/'inputs.json',records)
    manifest = {'version':VERSION,'seasons':2,'target':'2028-10-01','seeds':list(SEEDS),
                'source_hashes':hashes,'protected_files':protection(),
                'policy':'Hands-off GSW, auto-draft, no discretionary bids/trades/extensions. Existing explicit phase confirmations, legal low-role cutdowns and staff retention. Same policy, not forced identical AI outcomes.',
                'scope':'Identical frozen runtime, prospect generation and development. Only starting ratings differ. Initial stored 2027 draft class is shared, so paired seeds are not independent first classes.',
                'changes':changes}
    write(batch/'manifest.json',manifest)
    OUT.mkdir()
    write_outputs(candidate,OUT/'candidate')
    write(OUT/'candidate-review.json',{'changes':changes,'automatic':new['meta']['rotation_profile_report'],
        'profiles':{label:[r for r in profile_rows(data) if r['id'] in {c['player_id'] for c in changes}]
                    for label,data in (('v7',old),('v8',new))}})
    print(json.dumps({'prepared':str(batch),'changed_players':len({r['player_id'] for r in changes}),
                      'changed_traits':len(changes)}),flush=True)


def worker(batch, arm, seed):
    import overnight_market_health as audit
    assert (ROOT/'local-runtime.json').exists() and ROOT.is_relative_to(batch)
    audit.install_local_read_guard(ROOT)
    gc.disable()
    out = ROOT/f'output/comparison/{arm}'
    began = time.monotonic()
    for _ in range(80):
        path = out/f'career-{seed}/run.json'
        if path.exists():
            run = json.loads(path.read_text())
            if run['status']=='completed':
                return
        if time.monotonic()-began > 2100:
            raise RuntimeError('35-minute worker budget reached; checkpoint preserved')
        audit.step(argparse.Namespace(output_dir=str(out),seed=seed,short_days=0))
        run = json.loads(path.read_text())
        if not run['actions']:
            run.update(target='2028-10-01',target_seasons=2)
            write(path,run)
    raise RuntimeError('Bounded action count exceeded; checkpoint preserved')


def run(batch):
    from background_league_health import process_memory
    manifest = json.loads((batch/'manifest.json').read_text())
    runtime = batch/'runtime'
    assert all(sha(runtime/name)==value for name,value in manifest['source_hashes'].items())
    started = time.monotonic()
    jobs = {}
    # Each paired seed runs together, at most two workers and four careers total.
    for seed in SEEDS:
        active = []
        try:
            for arm in ('control','candidate'):
                log = (batch/f'{arm}-{seed}.log').open('a')
                cmd = [sys.executable,'-u','-B',str(runtime/'scripts/compare_rotation_profiles.py'),
                       'worker','--batch',str(batch),'--arm',arm,'--seed',str(seed)]
                process = subprocess.Popen(cmd,cwd=runtime,stdout=log,stderr=subprocess.STDOUT)
                active.append((arm,process,log))
            while any(p.poll() is None for _,p,_ in active):
                if shutil.disk_usage(batch).free < 8*1024**3:
                    raise RuntimeError('Disk safety floor reached')
                if process_memory([p.pid for _,p,_ in active if p.poll() is None]) > 6144:
                    raise RuntimeError('6 GiB worker memory safety ceiling reached')
                progress = {}
                for arm,p,_ in active:
                    path = runtime/f'output/comparison/{arm}/career-{seed}/run.json'
                    r = json.loads(path.read_text()) if path.exists() else {}
                    progress[arm] = {'endpoint':r.get('endpoint'),'complete_seasons':r.get('complete_seasons',0),
                                     'actions':len(r.get('actions',[])),'exit_code':p.poll()}
                write(batch/'status.json',{'status':'running','seed':seed,'progress':progress,
                    'seconds':round(time.monotonic()-started,1),'jobs':jobs})
                time.sleep(5)
            for arm,p,_ in active:
                jobs[f'{arm}-{seed}'] = p.returncode
                if p.returncode:
                    raise RuntimeError(f'{arm} seed {seed} failed; inspect its log and saved checkpoint')
        finally:
            for _,p,log in active:
                if p.poll() is None:
                    p.terminate()
                p.wait()
                log.close()
    write(batch/'status.json',{'status':'completed','jobs':jobs,'seconds':round(time.monotonic()-started,1)})
    print(json.dumps({'status':'completed','jobs':jobs,'seconds':round(time.monotonic()-started,1)}),flush=True)


def finish(batch):
    jobs = {}
    for seed in SEEDS:
        for arm in ('control','candidate'):
            directory = batch/f'runtime/output/comparison/{arm}/career-{seed}'
            run = json.loads((directory/'run.json').read_text())
            assert run['status']=='completed' and run['endpoint']=='2028-10-01' and run['complete_seasons']==2
            assert not (directory/'pending-action.json').exists()
            saved = json.loads(Path(run['save_path']).read_text())
            assert saved['state']['current_date']=='2028-10-01' and len(saved['season_history'])==2
            jobs[f'{arm}-{seed}'] = {'status':'completed','actions':len(run['actions'])}
    write(batch/'status.json',{'status':'completed','jobs':jobs,
        'configuration_repair':(batch/'archive-setup-repair.json').exists()})
    print(json.dumps({'status':'completed','jobs':jobs}),flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','run','worker','finish'))
    parser.add_argument('--batch',type=Path,default=BATCH)
    parser.add_argument('--arm',choices=('control','candidate'))
    parser.add_argument('--seed',type=int)
    args = parser.parse_args()
    if args.mode=='prepare':
        prepare(args.batch)
    elif args.mode=='run':
        try:
            run(args.batch)
        except BaseException as exc:
            write(args.batch/'status.json',{'status':'failed','error':repr(exc)})
            raise
    elif args.mode=='finish':
        finish(args.batch)
    else:
        worker(args.batch,args.arm,args.seed)
