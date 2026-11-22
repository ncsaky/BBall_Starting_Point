#!/usr/bin/env python3
"""ROOKIE-SEASON: the same development-minutes measurement as rookie_dev_minutes.py, on simulated seasons.

For each finished probe save (scripts/research/rookie_season_probe.py): every player with 10+ games, ranked within his
team by the engine's own value (impact per 100, the game's counterpart of box plus-minus); veterans (fourth season or
later) give the minutes per game a coach hands each rank and value on each kind of team, and young players' extra
minutes are measured against that. Team kinds by simulated winning share (rebuilding under .400, contending .580 and
up) and by the team's own plan (rebuilding / entering / peak / exiting). Several saves are pooled.

    PYTHONPATH=src .venv/bin/python scripts/research/rookie_dev_minutes_sim.py DIR [DIR ...] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
from rookie_dev_minutes import fit_line, kind  # noqa: E402

PHASE_KIND = {"rebuilding": "rebuilding", "peak": "contending", "entering": "middle", "exiting": "middle"}


def season_rows(probe_dir: Path) -> list[dict]:
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.player_profile import engine_header
    from nba_gm_data.save import canonical_with_save, load_save
    save = load_save(probe_dir / "saves/league.json")
    active = canonical_with_save(load_app_canonical(ROOT), save)
    season_year = int(str((save.get("meta") or {}).get("season") or "2026")[:4])
    records = save.get("team_records") or {}
    plans = save.get("team_plans") or {}
    players = {p["id"]: p for p in active["players"]}
    rows = []
    for pid, s in (save.get("player_season_stats") or {}).items():
        games, minutes = float(s.get("games") or 0), float(s.get("minutes") or 0)
        team = s.get("team_id")
        p = players.get(pid)
        if games < 10 or not p or team not in records:
            continue
        head = engine_header(active, pid) or {}
        value = (head.get("impact") or {}).get("ovr")
        if value is None:
            continue
        rec = records[team]
        win = rec["wins"] / max(1, rec["wins"] + rec["losses"])
        draft_year = p.get("draft_year")
        try:
            exp = season_year - int(draft_year) + 1
        except (TypeError, ValueError):
            exp = None
        pick = p.get("draft_pick") or p.get("draft_position")
        rows.append({"id": pid, "name": p.get("name"), "team": team, "g": games, "mpg": minutes / games,
                     "steady": float(value), "win": win, "kind": kind(win),
                     "phase_kind": PHASE_KIND.get(((plans.get(team) or {}).get("window_phase")), "middle"),
                     "exp": exp, "pick": int(pick) if pick else None, "dir": str(probe_dir)})
    by_team: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        by_team.setdefault((r["dir"], r["team"]), []).append(r)
    for roster in by_team.values():
        roster.sort(key=lambda r: -r["steady"])
        for rank, r in enumerate(roster, 1):
            r["rank"] = rank
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dirs", type=Path, nargs="+")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    data = [r for d in args.dirs for r in season_rows(d)]
    vets = [r for r in data if r["exp"] is None or r["exp"] >= 4]
    young_hi = [r for r in data if r["exp"] in (1, 2) and r["pick"] and r["pick"] <= 10]
    young_other = [r for r in data if r["exp"] in (1, 2) and not (r["pick"] and r["pick"] <= 10)]

    def expected(r: dict, key: str) -> float | None:
        group = [v for v in vets if v[key] == r[key] and v["rank"] == min(r["rank"], 12)]
        if len(group) < 8:
            group = [v for v in vets if v["rank"] == min(r["rank"], 12)]
        if len(group) < 8:
            return None
        a, b = fit_line([(v["steady"], v["mpg"], v["g"]) for v in group])
        return a + b * r["steady"]

    out = {"groups": {}, "named": []}
    print("Simulated: extra minutes per game over a veteran of the same team rank and value on the same kind of team")
    for label, group in (("top-10 picks, years 1-2", young_hi), ("other young players, years 1-2", young_other),
                         ("veterans (check)", vets)):
        for key in ("kind", "phase_kind"):
            row = {}
            for k in ("rebuilding", "middle", "contending"):
                members = [(r, expected(r, key)) for r in group if r[key] == k]
                members = [(r, e) for r, e in members if e is not None]
                if not members:
                    continue
                w = sum(r["g"] for r, _ in members)
                row[k] = {"n": len(members), "extra_mpg": round(sum((r["mpg"] - e) * r["g"] for r, e in members) / w, 2),
                          "mpg": round(sum(r["mpg"] * r["g"] for r, _ in members) / w, 1),
                          "mean_rank": round(sum(r["rank"] for r, _ in members) / len(members), 1)}
            out["groups"][f"{label} | {key}"] = row
            print(f"  {label:32s} by {'record' if key == 'kind' else 'team plan'}: " + "; ".join(
                f"{k} n {v['n']} mpg {v['mpg']} rank {v['mean_rank']} extra {v['extra_mpg']:+.1f}" for k, v in row.items()))
    print("\nFirst-round picks by band and season (simulated), team plan rebuilding vs other: mpg (n) extra")
    young_any = [r for r in data if r["exp"] in (1, 2, 3) and r["pick"]]
    bands = {}
    for lo, hi in ((1, 10), (11, 20), (21, 30)):
        for exp in (1, 2, 3):
            cell = {}
            for k, kinds in (("rebuilding", ("rebuilding",)), ("other", ("middle", "contending"))):
                members = [(r, expected(r, "phase_kind")) for r in young_any
                           if lo <= r["pick"] <= hi and r["exp"] == exp and r["phase_kind"] in kinds]
                members = [(r, e) for r, e in members if e is not None]
                if members:
                    w = sum(r["g"] for r, _ in members)
                    cell[k] = {"n": len(members), "mpg": round(sum(r["mpg"] * r["g"] for r, _ in members) / w, 1),
                               "extra_mpg": round(sum((r["mpg"] - e) * r["g"] for r, e in members) / w, 2)}
            bands[f"picks {lo}-{hi} year {exp}"] = cell
            print(f"  picks {lo}-{hi} year {exp}: " + "; ".join(f"{k} {v['mpg']} ({v['n']}) extra {v['extra_mpg']:+.1f}"
                                                            for k, v in cell.items()))
    out["by_pick_band"] = bands
    print("\nTop-10 picks, years 1-2 (simulated):")
    for r in sorted(young_hi, key=lambda r: (r["exp"], r["pick"], r["dir"])):
        e = expected(r, "phase_kind")
        out["named"].append({k: r[k] for k in ("name", "pick", "exp", "team", "mpg", "steady", "rank", "phase_kind", "win")})
        print(f"  {r['name'][:22]:22s} pick {r['pick']:2d} year {r['exp']} {r['team'][5:].upper():4s} {r['phase_kind']:10s} "
              f"win {r['win']:.2f} rank {r['rank']:2d} value {r['steady']:+.2f} mpg {r['mpg']:4.1f} "
              f"(veteran same rank {e:4.1f})" if e is not None else "")
    if args.json:
        args.json.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
