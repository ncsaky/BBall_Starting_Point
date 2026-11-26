#!/usr/bin/env python3
"""COACHES-FREE-AGENTS: from one or more season runs' calendar snapshots (season_almanac_run.py), report each season's
head-coach firings, what became of franchise icons, and whether every free-agent departure states its reason.

  PYTHONPATH=src .venv/bin/python scripts/coaches_free_agents_check.py output/cfa/seed-a output/cfa/seed-b
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data import franchise_ties as ties  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.save import canonical_with_save  # noqa: E402

SIGNINGS = {"free_agent_signing", "ai_free_agent_signing", "ai_re_signing", "auto_depth_signing", "camp_signing"}


def read(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def offseason(canonical: dict, save: dict, season: str) -> dict:
    year = int(season[:4]) + 1
    active = canonical_with_save(canonical, save)
    players = {p["id"]: p for p in active["players"]}
    origins = {pid: row["team_id"] for pid, row in (save.get(ties.ORIGIN_KEY) or {}).items()
               if row.get("season") == season}
    signed: dict[str, dict] = {}
    for log in save.get("transaction_logs", []):
        if f"{year}-06-01" <= str(log.get("date")) <= f"{year}-10-01" and log.get("transaction_type") in SIGNINGS:
            pid = (log.get("assets") or {}).get("player_id")
            if pid:
                signed[pid] = log
    counts: Counter = Counter()
    reasons: Counter = Counter()
    silent: Counter = Counter()
    icons, notable = [], []
    for pid, origin in sorted(origins.items()):
        log = signed.get(pid)
        player = players.get(pid) or {"id": pid}
        tie = ties.franchise_tie(save, player, origin)
        team = log["teams"][0] if log else None
        departed = (log.get("assets") or {}).get("departure") if log else None
        if team:
            kind = "stayed" if team == origin else "left"
            counts[kind] += 1
            if tie["loyal"]:
                counts[f"loyal_{kind}"] += 1
            if kind == "left":
                if departed:
                    reasons[departed["key"]] += 1
                else:
                    silent[log["transaction_type"]] += 1
        clause = ties.departure_clause(departed) if departed else ""
        if tie["icon"]:
            icons.append(f"{player.get('name')} {origin[5:].upper()} ({tie['seasons']} seasons, {player.get('age')}): "
                         + (("re-signed" if team == origin else f"to {team[5:].upper()} {clause}") if team else
                            "unsigned or retired"))
        salary = float(((log or {}).get("assets") or {}).get("contract", {}).get("annual_salary") or 0)
        if departed and salary >= 10_000_000:
            notable.append(f"{player.get('name')} ${salary / 1e6:.1f}M to {team[5:].upper()}, {clause}")
    return {"counts": dict(counts), "reasons": dict(reasons), "departures_without_reason": dict(silent),
            "icons": icons, "notable": notable}


def main() -> int:
    canonical = load_app_canonical(ROOT)
    totals: list[int] = []
    for run in (Path(arg) for arg in sys.argv[1:]):
        snaps = sorted((run / "snapshots").glob("*.json.gz"))
        print(f"\n===== {run}")
        final = read(snaps[-1])
        seasons = sorted({path.name.split("_")[1] for path in snaps})
        for season in seasons:
            year = int(season[:4]) + 1
            ended = [p for p in snaps if f"_{season}_" in p.name and "training_camp" in p.name]
            if not ended:
                continue
            summer = int(season[:4]) + 1
            firings = [r for r in final.get("staff_firing_history", [])
                       if r.get("season") == season and r.get("slot") == "head_coach"]
            totals.append(len(firings))
            in_season = sum(r.get("review_period") == "in_season" for r in firings)
            print(f"\n--- {season}: {len(firings)} head coaches fired ({in_season} in season, "
                  f"{len(firings) - in_season} in the summer of {summer})")
            for r in firings:
                print(f"   {r['date']} {r['team_id'][5:].upper()} {r['staff_name']}: {r['reason']}")
            # The summer's signings: the next preseason's save (camp deals and the last fill-ins), plus the training-camp
            # save's older rows, which that one may already have moved to the history file.
            camp = read(ended[-1])
            after = [p for p in snaps if p.name > ended[-1].name]
            save = read(after[0]) if after else camp
            logs = {r["id"]: r for r in [*camp.get("transaction_logs", []), *save.get("transaction_logs", [])]}
            save["transaction_logs"] = sorted(logs.values(), key=lambda r: str(r.get("date")))
            row = offseason(canonical, save, season)
            print(f"   free agents who signed: {row['counts']}")
            print(f"   stated reasons: {row['reasons']}; departures without one: {row['departures_without_reason']}")
            for line in row["icons"]:
                print("   icon:", line)
            for line in row["notable"]:
                print("   moved:", line)
    if totals:
        print(f"\nhead-coach firings per season: {totals}, mean {sum(totals) / len(totals):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
