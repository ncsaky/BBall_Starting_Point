#!/usr/bin/env python3
"""SEASON-SPEED-FLOOR probe: play Oct 20 -> Nov 30 (or --from/--to) of one season start (a fresh save, or a copied rollover save) and
report seconds, optionally under cProfile, plus a fingerprint of the resulting save for before/after comparisons.

  PYTHONPATH=src .venv/bin/python scripts/season_month_probe.py --folder output/ssf/p1 [--save start.json] [--profile]
  PYTHONPATH=src .venv/bin/python scripts/season_month_probe.py --compare output/ssf/base_s1 output/ssf/new_s1

--compare checks two finished probe folders' final saves for exact equality, except the random snapshot id, the
history-store bookkeeping, and the canonical-data fingerprint (it depends on the folder the data was loaded from).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Save keys whose content is random by design (snapshot ids, wall-clock stamps) or bookkeeping of the history store.
VOLATILE = {"history_store"}


def comparable(save: dict[str, Any]) -> dict[str, Any]:
    out = {key: value for key, value in save.items() if key not in VOLATILE}
    out["meta"] = {key: value for key, value in (save.get("meta") or {}).items()
                   if key not in {"save_snapshot_id", "canonical_hash"}}
    return out


def final_save(folder: Path) -> dict[str, Any]:
    paths = [p for p in folder.glob("*.json") if p.name != "fingerprint.json"]
    return json.loads(paths[0].read_text())


def compare(a: Path, b: Path) -> int:
    left, right = comparable(final_save(a)), comparable(final_save(b))
    differing = sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))
    if differing and "meta" in differing:
        meta = sorted(k for k in set(left["meta"]) | set(right["meta"]) if left["meta"].get(k) != right["meta"].get(k))
        differing = [f"meta.{k}" for k in meta] + [k for k in differing if k != "meta"]
    print(json.dumps({"identical": not differing, "differing": differing}))
    return 0 if not differing else 1


def fingerprint(save: dict[str, Any]) -> dict[str, str]:
    out = {}
    for key in sorted(save):
        if key in VOLATILE:
            continue
        out[key] = hashlib.sha1(json.dumps(save[key], sort_keys=True, default=str).encode()).hexdigest()[:12]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder")
    parser.add_argument("--compare", nargs=2)
    parser.add_argument("--save")
    parser.add_argument("--seed", type=int, default=20261125)
    parser.add_argument("--team", default="MIA")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--from", dest="start", default="10-20", help="month-day the timed window starts")
    parser.add_argument("--to", default="11-30")
    parser.add_argument("--no-floor", action="store_true",
                        help="proof runs only: switch the eight-player floor off, to compare caches with older code")
    args = parser.parse_args()
    if args.compare:
        return compare(Path(args.compare[0]), Path(args.compare[1]))
    from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
    from nba_gm_data.save import load_save
    from nba_gm_data import save as save_module
    if args.no_floor:
        from nba_gm_data import health
        health.MIN_AVAILABLE_PLAYERS = 0
    save_module.lottery_seed = lambda seed=None: int(seed) if seed is not None else 20270622
    canonical = load_app_canonical(ROOT)
    folder = Path(args.folder).resolve()
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)

    def act(name: str, **payload: Any) -> dict[str, Any]:
        return dispatch_app_action(name, payload, root=ROOT, save_dir=folder, canonical=canonical)

    if args.save:
        start = Path(args.save).resolve()
        shutil.copy2(start, folder / start.name)
        db = (json.loads(start.read_text()).get("history_store") or {}).get("path")
        if db:
            shutil.copy2(start.parent / db, folder / db)
        save_path = folder / start.name
    else:
        created = act("create_save", team=args.team, seed=args.seed, save_name="speed")
        save_path = Path(created["save_path"])
        act("set_starting_five", save_path=str(save_path), team=args.team, auto=True)

    import ten_season_soak as soak
    soak.markdown_report = lambda payload: ""
    runner = soak.SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(folder / "runner"), seed=args.seed,
                                                team=args.team))
    runner.payload["save_path"] = str(save_path)
    runner.save_dir = folder

    def advance_to(target: str) -> int:
        games = 0
        for _ in range(12):
            runner.resolve_user_staff_retention()
            runner.resolve_user_roster_cutdown()
            save = load_save(save_path)
            if save["state"]["current_date"] >= target:
                break
            before = len((save.get("schedule_state") or {}).get("simulated_game_ids") or [])
            act("advance_save", save_path=str(save_path), to_date=target, checkpoint_days=31, seed=args.seed)
            after = load_save(save_path)
            games += len((after.get("schedule_state") or {}).get("simulated_game_ids") or []) - before
        return games

    year = int(load_save(save_path)["state"]["current_date"][:4])
    advance_to(f"{year}-{args.start}")
    size_start = save_path.stat().st_size
    profiler = None
    if args.profile:
        import cProfile
        profiler = cProfile.Profile()
        profiler.enable()
    started = time.monotonic()
    games = advance_to(f"{year}-{args.to}")
    seconds = time.monotonic() - started
    if profiler is not None:
        profiler.disable()
        profiler.dump_stats(str(folder / "prof.out"))
    final = load_save(save_path)
    from datetime import date
    days = (date.fromisoformat(final["state"]["current_date"]) - date.fromisoformat(f"{year}-{args.start}")).days or 1
    (folder / "fingerprint.json").write_text(json.dumps(fingerprint(final), indent=1) + "\n")
    print(json.dumps({"from": f"{year}-{args.start}", "to": final["state"]["current_date"], "games": games,
                      "seconds": round(seconds, 1), "seconds_per_30_days": round(seconds * 30 / days, 1),
                      "save_mb_at_oct20": round(size_start / 1e6, 1), "save_mb_end": round(save_path.stat().st_size / 1e6, 1)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
