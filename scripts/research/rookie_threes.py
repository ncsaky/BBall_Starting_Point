#!/usr/bin/env python3
"""ROOKIE-THREES research: do drafted and generated players shoot and turn it over like real players of their type?

  real    Real evidence: first- and second-year players against everyone else, by season, position and role
          (ESPN career totals in data/research/player_career_stats.json; positions and roles from the 2026-27 universe).
  habits  Generated players' habits (inputs) against the 24 nearest real players (ability and position) and against
          the real 2025 and 2026 draft classes, from a save of a multi-season run (default: last season's end).
  league  League three-point share, turnovers, assists, fouls, free throws and points per 100 possessions, season by
          season, for any number of run folders side by side (regular season, from the games log).
  run     Shot mix and turnovers by origin (generated vs opening-day players), age band and position, season by season,
          from a run folder written by scripts/s2_multiseason.py (its games log plus one phase save for who is who).

  PYTHONPATH=src .venv/bin/python scripts/research/rookie_threes.py real
  PYTHONPATH=src .venv/bin/python scripts/research/rookie_threes.py habits output/rt/current_after
  PYTHONPATH=src .venv/bin/python scripts/research/rookie_threes.py run output/rt/current_after output/rt/stage2_after
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

POSITIONS = ("PG", "SG", "SF", "PF", "C")


def line(label: str, rows: list[dict]) -> str:
    fga = sum(r["fga"] for r in rows)
    f3 = sum(r["fg3a"] for r in rows)
    minutes = sum(r["min"] for r in rows)
    tov = sum(r["tov"] for r in rows)
    fta = sum(r["fta"] for r in rows)
    plays = fga + .44 * fta + tov
    return (f"| {label} | {len(rows)} | {minutes:,.0f} | {f3 / max(1, fga):.3f} | {36 * tov / max(1, minutes):.2f} | "
            f"{tov / max(1, plays):.3f} |")


HEADER = "| Group | Player-seasons | Minutes | Share of shots from three | Turnovers per 36 | Turnovers per play |\n|---|---|---|---|---|---|"


def real(args: argparse.Namespace) -> None:
    careers = json.loads((ROOT / "data/research/player_career_stats.json").read_text())["players"]
    universe = json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text())
    meta = {str(p.get("espn_player_id") or ""): p for p in universe["players"]}
    rows = []
    for pid, career in careers.items():
        drafted = career.get("draft_year")
        player = meta.get(str(career.get("espn_player_id") or "")) or {}
        for season in career["seasons"]:
            start = int(season["season"][:4])
            rows.append(dict(season=season["season"], year=(start - int(drafted) + 1) if drafted else None,
                             pos=str(player.get("position") or "").split("/")[0],
                             role=str(player.get("primary_off_role") or ""),
                             min=season["minutes"] or 0, fga=season["fga"] or 0, fg3a=season["fg3a"] or 0,
                             fta=season["fta"] or 0, tov=season["turnovers"] or 0))
    rows = [r for r in rows if r["min"] > 0]
    young = lambda r: r["year"] in (1, 2)
    print("## Real players: first and second NBA seasons against everyone else\n")
    print(HEADER)
    for season in ("2023-24", "2024-25", "2025-26"):
        group = [r for r in rows if r["season"] == season]
        print(line(f"{season} all players", group))
        print(line(f"{season} first and second years", [r for r in group if young(r)]))
        print(line(f"{season} everyone else", [r for r in group if not young(r)]))
    print("\n## By position, three seasons pooled\n")
    print(HEADER)
    for pos in POSITIONS:
        print(line(f"{pos} first and second years", [r for r in rows if r["pos"] == pos and young(r)]))
        print(line(f"{pos} everyone else", [r for r in rows if r["pos"] == pos and not young(r)]))
    print("\n## By offensive role (2026-27 universe), three seasons pooled, roles with 40+ young player-seasons\n")
    print(HEADER)
    roles = collections.Counter(r["role"] for r in rows if young(r))
    for role, count in roles.most_common():
        if count < 40 or not role:
            continue
        print(line(f"{role} first and second years", [r for r in rows if r["role"] == role and young(r)]))
        print(line(f"{role} everyone else", [r for r in rows if r["role"] == role and not young(r)]))


def load_active(run: Path, phase: str):
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.save import canonical_with_save, ensure_league_save_defaults, load_save
    canonical = load_app_canonical(ROOT)
    save = ensure_league_save_defaults(load_save(str(run / "phase_saves" / f"{phase}.json")), canonical)
    return canonical_with_save(canonical, save)


def habits(args: argparse.Namespace) -> None:
    from nba_gm_data.box_rates import flatten_inputs
    from nba_gm_data.input_estimator import _get, _position, _real_reference_players
    from nba_gm_data.ratings_model import _GENERATED_CACHE, MODEL_KEY
    from nba_gm_data.resource_paths import game_resource_root
    from nba_gm_data.stage2.cards import TURNOVER
    active = load_active(Path(args.run), args.phase)
    players = {p["id"]: p for p in active["players"]}
    generated = {pid: flatten_inputs(_GENERATED_CACHE[(pid, key)]) for pid, key in active[MODEL_KEY]["generated"].items()}
    real = [(p, ability, _position(p), flatten_inputs(inputs))
            for _, p, ability, _, inputs in _real_reference_players(str(game_resource_root()))]
    young = [r for r in real if str(r[0].get("draft_year")) in ("2025", "2026")]
    neighbours = {}
    for pid in generated:
        p = players[pid]
        ability, pos = _get(p, "current_ability") or 45.0, _position(p)
        neighbours[pid] = sorted(real, key=lambda r: ((r[1] - ability) / 8) ** 2 + 2 * (r[2] != pos))[:24]
    keys = ("T02.three", "T02.rim", "T02.short_paint", "T02.midrange", "T01.drive", "T01.pass", "T06", "T07", "T08",
            "T04", "T09", "T18")
    print(f"## Generated players' habits ({len(generated)} players) against real players of their type\n")
    print("| Habit | Position | Generated | 24 nearest real players | Real 2025-26 draftees |\n|---|---|---|---|---|")
    for key in keys:
        for pos in ("guard", "wing", "big"):
            ids = [pid for pid in generated if _position(players[pid]) == pos]
            g = statistics.mean(generated[pid][key] for pid in ids)
            n = statistics.mean(statistics.mean(r[3][key] for r in neighbours[pid]) for pid in ids)
            y = statistics.mean(r[3][key] for r in young if r[2] == pos)
            print(f"| {key} | {pos} | {g:.3f} | {n:.3f} | {y:.3f} |")

    def to_logit(flat):
        total = 0.0
        for k, coef in TURNOVER.items():
            if k == "constant":
                continue
            value = flat.get(k[4:] if k.startswith("log ") else k)
            total += coef * (math.log(max(1e-4, value)) if k.startswith("log ") else value)
        return total
    gap = statistics.mean(to_logit(generated[pid]) - statistics.mean(to_logit(r[3]) for r in neighbours[pid])
                          for pid in generated)
    print(f"\nStage 2 turnover rule (log-odds per used play), generated minus their 24 nearest real players: {gap:+.3f}")


def season_rows(run: Path, info: dict) -> list[dict]:
    stats = collections.defaultdict(collections.Counter)
    with gzip.open(run / "games.jsonl.gz", "rt") as handle:
        for raw in handle:
            game = json.loads(raw)
            if game["kind"] != "regular":
                continue
            year, month = int(game["date"][:4]), int(game["date"][5:7])
            season = year if month >= 8 else year - 1
            for l in game["lines"]:
                c = stats[(season, l[0])]
                for i, name in ((3, "min"), (9, "tov"), (10, "fga"), (12, "fg3a"), (13, "fg3m"), (14, "fta")):
                    c[name] += l[i]
    return [dict(season=s, pid=pid, **info.get(pid, {}), **c) for (s, pid), c in stats.items() if c["min"] > 0]


def run_report(args: argparse.Namespace) -> None:
    from nba_gm_data.ratings_model import MODEL_KEY
    for folder in args.runs:
        run = Path(folder)
        phases = sorted(p.stem for p in (run / "phase_saves").glob("season_*_regular_end.json"))
        active = load_active(run, phases[-1])
        generated = set(active[MODEL_KEY].get("generated") or {})
        start = int(str(active.get("meta", {}).get("season_start_year") or 0) or 0)
        info = {}
        for p in active["players"]:
            info[p["id"]] = dict(gen=p["id"] in generated, pos=str(p.get("position") or "").split("/")[0],
                                 age=p.get("age"), base=p.get("age_base_start_year"), born=p.get("birthdate"))
        rows = season_rows(run, info)
        print(f"\n## {run.name}: share of shots from three and turnovers, by origin\n")
        print(HEADER)
        for season in sorted({r["season"] for r in rows}):
            group = [r for r in rows if r["season"] == season]
            print(line(f"{season} all", group))
            print(line(f"{season} generated", [r for r in group if r.get("gen")]))
            print(line(f"{season} opening-day players", [r for r in group if not r.get("gen")]))
        last = max(r["season"] for r in rows)
        group = [r for r in rows if r["season"] == last]
        print(f"\n### {run.name}, season {last}: generated vs opening-day players by position\n")
        print(HEADER)
        for pos in POSITIONS:
            print(line(f"{pos} generated", [r for r in group if r.get("gen") and r.get("pos") == pos]))
            print(line(f"{pos} opening-day", [r for r in group if not r.get("gen") and r.get("pos") == pos]))
        def age(r):
            """Age on 1 February of the season."""
            if r.get("born"):
                return last + 1 - int(str(r["born"])[:4]) - (1 if str(r["born"])[5:10] > "02-01" else 0)
            if isinstance(r.get("age"), (int, float)) and r.get("base"):
                return r["age"] + (last - int(r["base"]))
            return None
        print(f"\n### {run.name}, season {last}: by age band\n")
        print(HEADER)
        for low, high in ((19, 22), (23, 24), (25, 29), (30, 45)):
            for gen, label in ((True, "generated"), (False, "opening-day")):
                rows_band = [r for r in group if bool(r.get("gen")) == gen and age(r) is not None and low <= age(r) <= high]
                if rows_band:
                    print(line(f"age {low}-{high} {label}", rows_band))


def league(args: argparse.Namespace) -> None:
    table = {}
    for folder in args.runs:
        totals = collections.defaultdict(collections.Counter)
        with gzip.open(Path(folder) / "games.jsonl.gz", "rt") as handle:
            for raw in handle:
                game = json.loads(raw)
                if game["kind"] != "regular":
                    continue
                year, month = int(game["date"][:4]), int(game["date"][5:7])
                season = year if month >= 8 else year - 1
                for team in game["teams"].values():
                    for key in ("points", "fga", "fg3a", "fta", "turnovers", "assists", "personal_fouls"):
                        totals[season][key] += team.get(key) or 0
                    totals[season]["poss"] += float(game.get("possessions") or 0)
                    totals[season]["games"] += 1
        table[folder] = totals
    rows = [("Share of shots from three", lambda t: t["fg3a"] / t["fga"], "{:.3f}", "0.415"),
            ("Turnovers per 100", lambda t: 100 * t["turnovers"] / t["poss"], "{:.1f}", "14.1"),
            ("Points per 100", lambda t: 100 * t["points"] / t["poss"], "{:.1f}", "112.7"),
            ("Free-throw tries per shot", lambda t: t["fta"] / t["fga"], "{:.3f}", "0.264"),
            ("Assists per 100", lambda t: 100 * t["assists"] / t["poss"], "{:.1f}", "26.1"),
            ("Fouls per 100", lambda t: 100 * t["personal_fouls"] / t["poss"], "{:.1f}", "19.4")]
    for name, fn, fmt, real in rows:
        print(f"\n{name} (real 2025-26 {real})\n")
        print("| Run | " + " | ".join(f"Season {i + 1}" for i in range(4)) + " |\n|---|---|---|---|---|")
        for folder, totals in table.items():
            cells = [fmt.format(fn(totals[s])) if totals[s]["poss"] else "-" for s in sorted(totals)][:4]
            print(f"| {Path(folder).name} | " + " | ".join(cells) + " |")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("real")
    p_h = sub.add_parser("habits")
    p_h.add_argument("run")
    p_h.add_argument("--phase", default="season_04_regular_end")
    p_l = sub.add_parser("league")
    p_l.add_argument("runs", nargs="+")
    p_r = sub.add_parser("run")
    p_r.add_argument("runs", nargs="+")
    args = parser.parse_args()
    {"real": real, "habits": habits, "league": league, "run": run_report}[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
