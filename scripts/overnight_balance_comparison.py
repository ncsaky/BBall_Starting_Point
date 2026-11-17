"""Freeze and supervise a bounded paired league-health experiment."""
import argparse
import ast
from collections import deque
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
BATCH = Path.home()/".cache/nba-gm-audits/paired-balance-2026-10-26"
SEEDS = (29, 913)
ARMS = ("control", "tuned")
REL_OUT = "output/balance"
OLD_HEALTH = Path.home()/".cache/nba-gm-audits/market-lifecycle-2026-10-25/runtime/src/nba_gm_data/health.py"


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_name(path.name+".tmp")
    temporary.write_text(json.dumps(value,indent=2)+"\n")
    temporary.replace(path)


def control_health(current, original):
    before = {n.name:n for n in ast.parse(original).body if isinstance(n,ast.FunctionDef)}
    after = {n.name:n for n in ast.parse(current).body if isinstance(n,ast.FunctionDef)}
    assert before.keys() == after.keys()
    assert all(ast.dump(before[k]) == ast.dump(after[k]) for k in before if k!="monthly_trait_delta")
    node = after["monthly_trait_delta"]
    lines = current.splitlines(keepends=True)
    return "".join(lines[:node.lineno-1])+ast.get_source_segment(original,before[node.name])+"\n"+"".join(lines[node.end_lineno:])


def prepare(args):
    if args.batch.exists():
        raise FileExistsError("Experiment already exists; inspect it instead of overwriting")
    if shutil.disk_usage(args.batch.parent).free < 12*1024**3:
        raise RuntimeError("Need 12 GiB free to prepare paired careers")
    sys.path[:0] = [str(ROOT/"src"),str(ROOT/"scripts")]
    import overnight_market_health as audit
    selected = set(audit.inputs()) | set((ROOT/"scripts").glob("*.py")) | {ROOT/"pyproject.toml"}
    selected = sorted(p for p in selected if p.is_file())
    source_hashes = {str(p.relative_to(ROOT)):sha(p) for p in selected}
    original = OLD_HEALTH.read_text()
    manifest = {"created_at":now(),"hours":args.hours,"seasons":args.seasons,"seeds":list(SEEDS),
        "arms":list(ARMS),"parallel":2,"disk_floor_gib":8,"result_budget_gib":6,
        "memory_ceiling_mib":6144,"source_root":str(ROOT),"source_hashes":source_hashes,
        "old_health_sha256":sha(OLD_HEALTH),"scope":"Paired seeds and identical initial V5 baseline/decision policy. Control reverts only selective monthly learning and added rare latent tail; all other current fixes, role reassessment, retention, ratings and medicals identical. Tuned retains learning plus rare-tail/scouting boundary. This measures their combined effect, not separate causal contributions.",
        "policy":"Hands-off GSW; auto-draft; explicit deadline/postseason decisions; no discretionary trades/bids/extensions; legal low-role user cutdowns and staff retention via existing runner. AI decisions may diverge as a consequence of talent changes.",
        "metrics":"Monthly fixed-24 OVR, age, origin, actual draft slot, games/minutes, contracts/salaries, roster/free-agent state, injuries, development events, entry/departure flow and retirement/league exits; daily free-agency snapshots. Keep all draft entries including later cuts, not only survivors."}
    for arm in ARMS:
        runtime = args.batch/arm/"runtime"
        for source in selected:
            relative = source.relative_to(ROOT)
            target = runtime/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            assert sha(target) == source_hashes[str(relative)]
        changes = {}
        if arm == "control":
            path = runtime/"src/nba_gm_data/health.py"
            path.write_text(control_health(path.read_text(),original))
            changes[str(path.relative_to(runtime))] = sha(path)
            path = runtime/"src/nba_gm_data/draft.py"
            text = path.read_text()
            line = "hidden_tail = .012 + .012 * quality if talent_model else .004"
            assert text.count(line) == 1
            path.write_text(text.replace(line,"hidden_tail = .004",1))
            changes[str(path.relative_to(runtime))] = sha(path)
        write(runtime/"local-runtime.json",{"blocked_roots":[str(ROOT),str(Path.home()/"Documents")],
              "purpose":"Frozen paired balance experiment; no playable or cloud-workspace reads"})
        # The input inventory includes the local guard itself.
        files = {name:{"sha256":sha(runtime/name)} for name in source_hashes}
        files["local-runtime.json"] = {"sha256":sha(runtime/"local-runtime.json")}
        write(runtime/"snapshot.json",{"status":"verified","files":files,"arm":arm,"intentional_changes":changes})
        canonical = json.loads(gzip.decompress((runtime/"data/canonical/baselines/2026-10-23-forward-tuning-v5.json.gz").read_bytes()))
        canonical["_baseline_directory"] = str(runtime/"data/canonical/baselines")
        out = runtime/REL_OUT
        out.mkdir(parents=True)
        with gzip.open(out/"canonical.json.gz","wt",compresslevel=3) as handle:
            json.dump(canonical,handle,separators=(",",":"))
        write(out/"manifest.json",{**manifest,"arm":arm})
        write(out/"inputs.json",{str(p.relative_to(ROOT)):sha(runtime/p.relative_to(ROOT))
              for p in audit.inputs()})
        # audit.inputs() above ran in the source root, where no guard exists.
        recorded = json.loads((out/"inputs.json").read_text())
        recorded["local-runtime.json"] = sha(runtime/"local-runtime.json")
        write(out/"inputs.json",recorded)
    assert all(sha(ROOT/name) == value for name,value in source_hashes.items()), "Source changed during freeze"
    write(args.batch/"manifest.json",manifest)
    print(f"Frozen paired experiment at {args.batch}",flush=True)


def step(args):
    # This mode runs ONLY from a frozen arm, not from the user's workspace.
    if not (ROOT/"local-runtime.json").exists() or not ROOT.is_relative_to(args.batch):
        raise RuntimeError("Worker must run inside the isolated frozen runtime")
    sys.path[:0] = [str(ROOT/"src"),str(ROOT/"scripts")]
    import overnight_market_health as audit
    audit.install_local_read_guard(ROOT)
    out = ROOT/REL_OUT
    path = out/f"career-{args.seed}/run.json"
    created = not path.exists()
    audit.step(argparse.Namespace(output_dir=str(out),seed=args.seed,short_days=args.short_days))
    if created:
        run = json.loads(path.read_text())
        seasons = json.loads((args.batch/"manifest.json").read_text())["seasons"]
        run["target"] = f"{int(run['starting_date'][:4])+seasons}-10-01"
        run["target_seasons"] = seasons
        write(path,run)


def worker_command(batch, arm, seed, short_days=0):
    runtime = batch/arm/"runtime"
    return runtime,[sys.executable,"-u","-B",str(runtime/"scripts"/Path(__file__).name),
        "step","--batch",str(batch),"--seed",str(seed),"--short-days",str(short_days)]


def progress(batch, arm, seed):
    path = batch/arm/"runtime"/REL_OUT/f"career-{seed}/run.json"
    if not path.exists():
        return {"endpoint":"not created","complete_seasons":0,"actions":0}
    run = json.loads(path.read_text())
    return {"endpoint":run["endpoint"],"complete_seasons":run["complete_seasons"],
            "actions":len(run["actions"]),"target":run["target"],"checkpoint_status":run["status"]}


def result_bytes(batch):
    total = 0
    for arm in ARMS:
        for path in (batch/arm/"runtime"/REL_OUT).rglob("*"):
            try:
                if path.is_file(): total += path.stat().st_size
            except FileNotFoundError:
                # Workers replace backups and checkpoints atomically.
                continue
    return total


def smoke(args):
    manifest = json.loads((args.batch/"manifest.json").read_text())
    for seed in SEEDS:
        for arm in ARMS:
            for _ in range(2):
                runtime,command = worker_command(args.batch,arm,seed,short_days=1)
                subprocess.run(command,cwd=runtime,check=True,timeout=600)
            run = progress(args.batch,arm,seed)
            assert run["actions"] == 1 and run["complete_seasons"] == 0
            assert run["target"] == f"{2026+manifest['seasons']}-10-01"
        left = progress(args.batch,"control",seed)
        right = progress(args.batch,"tuned",seed)
        assert left["endpoint"] == right["endpoint"]
    write(args.batch/"smoke.json",{"status":"passed","finished_at":now(),
        "scope":"Each of four disposable careers created and advanced one day via real app actions, inside frozen read-guarded runtimes; paired endpoints match. No claim of long-run balance."})
    print("All four disposable careers passed the short launch check.",flush=True)


def work(args):
    sys.path.insert(0,str(ROOT/"scripts"))
    from background_league_health import process_memory
    manifest = json.loads((args.batch/"manifest.json").read_text())
    with (args.batch/"supervisor.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        os.nice(10)
        queue = deque((arm,seed) for seed in SEEDS for arm in ARMS)
        report = {"status":"running","pid":os.getpid(),"started_at":now(),
                  "supervisor_sha256":sha(Path(__file__)),
                  "jobs":{f"{a}:{s}":{"status":"queued"} for a,s in queue}}
        active = {}
        requested = None
        stop_at = None
        began = time.monotonic()
        awake = subprocess.Popen(["/usr/bin/caffeinate","-i","-w",str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

        def stop(signum, frame):
            nonlocal requested
            requested = requested or "user_stop"

        signal.signal(signal.SIGTERM,stop)
        signal.signal(signal.SIGINT,stop)
        try:
            while queue or active:
                elapsed = time.monotonic()-began
                free = shutil.disk_usage(args.batch).free/1024**3
                rss = process_memory([p.pid for p,h,t in active.values()]) if active else 0
                used = result_bytes(args.batch)/1024**3
                if (args.batch/"STOP").exists(): requested = requested or "user_stop_file"
                if elapsed >= manifest["hours"]*3600: requested = requested or "time_limit"
                if free < manifest["disk_floor_gib"]: requested = requested or "disk_floor"
                if rss > manifest["memory_ceiling_mib"]: requested = requested or "memory_ceiling"
                if used > manifest["result_budget_gib"]: requested = requested or "result_budget"
                for key,(process,handle,started) in list(active.items()):
                    if time.monotonic()-started > 2700: requested = requested or "action_over_45_minutes"
                    if process.poll() is None: continue
                    handle.close()
                    del active[key]
                    arm,seed = key
                    job = report["jobs"][f"{arm}:{seed}"]
                    state = progress(args.batch,arm,seed)
                    job.update(state,exit_code=process.returncode,updated_at=now())
                    if process.returncode:
                        job["status"] = "failed"
                        # Do not continue the partner as if the comparison were complete.
                        requested = requested or "worker_failed"
                    elif state.get("checkpoint_status") == "completed": job["status"] = "completed"
                    elif requested: job["status"] = "checkpointed"
                    else:
                        job["status"] = "queued"
                        queue.append(key)
                if requested:
                    stop_at = stop_at or time.monotonic()
                    if time.monotonic()-stop_at > 900:
                        for process,handle,started in active.values():
                            if process.poll() is None: os.killpg(process.pid,signal.SIGTERM)
                    if time.monotonic()-stop_at > 960:
                        for process,handle,started in active.values():
                            if process.poll() is None: os.killpg(process.pid,signal.SIGKILL)
                    if not active: break
                else:
                    while queue and len(active)<2:
                        arm,seed = queue.popleft()
                        runtime,command = worker_command(args.batch,arm,seed)
                        handle = (args.batch/f"{arm}-{seed}.log").open("a")
                        process = subprocess.Popen(command,cwd=runtime,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
                        active[(arm,seed)] = (process,handle,time.monotonic())
                        report["jobs"][f"{arm}:{seed}"].update(status="running",pid=process.pid,action_started_at=now())
                report.update(updated_at=now(),elapsed_hours=round(elapsed/3600,3),stop_reason=requested,
                              free_gib=round(free,2),result_gib=round(used,3),worker_rss_mib=round(rss,1))
                for key,job in report["jobs"].items():
                    arm,seed = key.split(":")
                    job.update(progress(args.batch,arm,int(seed)))
                write(args.batch/"status.json",report)
                time.sleep(5)
            report.update(status="stopped" if requested else "completed",finished_at=now(),stop_reason=requested)
            for job in report["jobs"].values():
                if job["status"] == "queued": job["status"] = "checkpointed"
            write(args.batch/"status.json",report)
        except BaseException as exc:
            report.update(status="failed",error=repr(exc),finished_at=now())
            write(args.batch/"status.json",report)
            raise
        finally:
            for process,handle,started in active.values():
                if process.poll() is None: os.killpg(process.pid,signal.SIGTERM)
                try: process.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL)
                    process.wait()
                handle.close()
            awake.terminate()
            awake.wait()


def status(args):
    manifest = json.loads((args.batch/"manifest.json").read_text())
    path = args.batch/"status.json"
    report = json.loads(path.read_text()) if path.exists() else {"status":"prepared","jobs":{}}
    print(f"League balance: {report['status']} | {report.get('elapsed_hours',0):.2f} hours elapsed | limit {manifest['hours']:g} hours")
    for seed in SEEDS:
        for arm in ARMS:
            state = progress(args.batch,arm,seed)
            job = report["jobs"].get(f"{arm}:{seed}",{})
            print(f"{arm:7} seed {seed:3} | {state['complete_seasons']}/{manifest['seasons']} seasons | {state['endpoint']} | {job.get('status','prepared')}")
    print(f"Free disk: {shutil.disk_usage(args.batch).free/1024**3:.1f} GiB | stop reason: {report.get('stop_reason') or 'none'}")
    if report.get("status") == "running":
        try: os.kill(report["pid"],0)
        except ProcessLookupError: print("WARNING: supervisor is no longer running; checkpoints remain available.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("prepare","smoke","start","work","step","status","stop"))
    parser.add_argument("--batch",type=Path,default=BATCH)
    parser.add_argument("--hours",type=float,default=10)
    parser.add_argument("--seasons",type=int,default=8)
    parser.add_argument("--seed",type=int,default=29)
    parser.add_argument("--short-days",type=int,default=0)
    args = parser.parse_args()
    if not 0<args.hours<=12 or not 1<=args.seasons<=10 or args.seed not in SEEDS:
        parser.error("hours in (0,12], seasons 1..10, and a paired seed required")
    if args.mode == "start":
        assert json.loads((args.batch/"smoke.json").read_text())["status"] == "passed"
        if (args.batch/"status.json").exists(): raise FileExistsError("Already started; inspect progress")
        with (args.batch/"supervisor.log").open("a") as log:
            process = subprocess.Popen([sys.executable,"-u","-B",__file__,"work","--batch",str(args.batch)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        print(f"Started overnight supervisor {process.pid}")
    elif args.mode == "stop":
        (args.batch/"STOP").touch()
        print("Stop requested; current actions may finish and checkpoint first.")
    else:
        globals()[args.mode](args)
